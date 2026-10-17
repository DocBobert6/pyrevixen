#!/usr/bin/env python3
"""
PyreVixen: Hard-case fixes that run AFTER scrub-glean.py.
These use simple, robust brace-balancing instead of fragile regexes.
"""
import os
import re
import sys


def gut_function(content, func_pattern, comment):
    """Replace a function body with a no-op comment. Returns new content."""
    import sys
    m = re.search(func_pattern, content)
    if not m:
        print(f"DEBUG gut_function: pattern did not match", file=sys.stderr)
        return content, False
    start = m.start()
    print(f"DEBUG gut_function: matched at {start}", file=sys.stderr)
    # Find the opening brace: first look within the match, then after it.
    brace_in_match = m.group(0).rfind("{")
    if brace_in_match != -1:
        brace_idx = m.start() + brace_in_match
        print(f"DEBUG gut_function: brace in match at {brace_idx}", file=sys.stderr)
    else:
        # Brace is after the match (multi-line signature).
        try:
            brace_idx = content.index("{", m.end())
            print(f"DEBUG gut_function: brace after match at {brace_idx}", file=sys.stderr)
        except ValueError:
            print(f"DEBUG gut_function: no brace found after match", file=sys.stderr)
            return content, False
    # Balance to the closing brace to bound the body.
    depth = 1
    i = brace_idx + 1
    while depth > 0 and i < len(content):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
        i += 1
    body = content[brace_idx:i]
    print(f"DEBUG gut_function: body len={len(body)}, has PYREVIXEN={'PYREVIXEN' in body}", file=sys.stderr)
    if "PYREVIXEN" in body:
        return content, False  # Already gutted, skip.
    # Replace body.
    new_func = content[start:brace_idx + 1] + f"\n        // {comment}\n    }}\n"
    print(f"DEBUG gut_function: replacing {len(body)} chars with stub", file=sys.stderr)
    return content[:start] + new_func + content[i:], True
    # Balance to the closing brace to bound the body.
    depth = 1
    i = brace_idx + 1
    while depth > 0 and i < len(content):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
        i += 1
    body = content[brace_idx:i]
    if "PYREVIXEN" in body:
        return content, False  # Already gutted, skip.
    # Replace body.
    new_func = content[start:brace_idx + 1] + f"\n        // {comment}\n    }}\n"
    return content[:start] + new_func + content[i:], True


def add_when_else(content, when_subject_pattern):
    """
    Find a `when (subject)` and add `else -> Unit` before its closing brace.
    Returns (new_content, changed).
    """
    m = re.search(when_subject_pattern, content)
    if not m:
        return content, False
    # Find the opening brace.
    brace_idx = content.index("{", m.end())
    # Balance to find the closing brace.
    depth = 1
    i = brace_idx + 1
    while depth > 0 and i < len(content):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
        i += 1
    # i is after the closing `}`. Insert `else` before it.
    # Find the indent of the closing brace.
    close_idx = i - 1
    line_start = content.rfind("\n", 0, close_idx) + 1
    indent = content[line_start:close_idx]
    # The branches are indented one level more.
    branch_indent = indent + "    "
    else_branch = f"{branch_indent}else -> Unit\n"
    new_content = content[:close_idx] + else_branch + content[close_idx:]
    return new_content, True


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    java_root = os.path.join(
        root,
        "mobile/android/fenix/app/src/main/java",
    )
    fixed = 0

    # 1. (Moved to delete-telemetry-funcs.py)
    # 2. StorageStatsMetrics.reportSync
    p = os.path.join(java_root, "org/mozilla/fenix/perf/StorageStatsMetrics.kt")
    if os.path.exists(p):
        with open(p) as f:
            c = f.read()
        c, changed = gut_function(
            c,
            r"    fun reportSync\(context: Context\) \{\n",
            "PYREVIXEN: telemetry removed.",
        )
        if changed:
            with open(p, "w") as f:
                f.write(c)
            print(f"gutted StorageStatsMetrics.reportSync")
            fixed += 1

    # 3. MetricController.track: gut the big event-mapping when.
    p = os.path.join(
        java_root, "org/mozilla/fenix/components/metrics/MetricController.kt"
    )
    if os.path.exists(p):
        with open(p) as f:
            c = f.read()
        # Gut ReleaseMetricController.track(event).
        c, changed = gut_function(
            c,
            r"    override fun track\(event: Event\) \{\n",
            "PYREVIXEN: telemetry removed.",
        )
        if changed:
            with open(p, "w") as f:
                f.write(c)
            print(f"gutted MetricController.track")
            fixed += 1

    # 4. DebugDrawerNavigationMiddleware: add else to the when.
    p = os.path.join(
        java_root,
        "org/mozilla/fenix/debugsettings/store/DebugDrawerNavigationMiddleware.kt",
    )
    if os.path.exists(p):
        with open(p) as f:
            c = f.read()
        c, changed = add_when_else(c, r"when \(.*action.*\)")
        if changed:
            with open(p, "w") as f:
                f.write(c)
            print(f"added else to DebugDrawerNavigationMiddleware")
            fixed += 1

    # 5. Activity: add else to the BrowserDirection when.
    p = os.path.join(java_root, "org/mozilla/fenix/ext/Activity.kt")
    if os.path.exists(p):
        with open(p) as f:
            c = f.read()
        c, changed = add_when_else(c, r"when \(.*direction.*\)")
        if changed:
            with open(p, "w") as f:
                f.write(c)
            print(f"added else to Activity")
            fixed += 1

    # 6. RecentSyncedTabFeature: remove syncStartId usages (structure-preserving).
    p = os.path.join(
        java_root,
        "org/mozilla/fenix/home/recentsyncedtabs/RecentSyncedTabFeature.kt",
    )
    if os.path.exists(p):
        with open(p) as f:
            c = f.read()
        orig = c
        # Delete the field.
        c = re.sub(
            r"^[ \t]*private var syncStartId:.*\n", "", c, flags=re.M
        )
        # Delete usages: syncStartId?.let { ... } blocks and assignments.
        c = re.sub(
            r"^[ \t]*syncStartId\?\.let \{\n(?:[ \t]*[^\n]*\n)*?[ \t]*\}\n",
            "", c, flags=re.M
        )
        c = re.sub(r"^[ \t]*syncStartId = .*\n", "", c, flags=re.M)
        c = re.sub(r"^[ \t]*syncStartId\?\..*\n", "", c, flags=re.M)
        if c != orig:
            with open(p, "w") as f:
                f.write(c)
            print(f"cleaned RecentSyncedTabFeature")
            fixed += 1

    # 7. SummarizationTelemetryMiddleware: remove timerId usages.
    p = os.path.join(
        java_root,
        "org/mozilla/fenix/summarization/SummarizationTelemetryMiddleware.kt",
    )
    if os.path.exists(p):
        with open(p) as f:
            c = f.read()
        orig = c
        c = re.sub(r"^[ \t]*private var timerId:.*\n", "", c, flags=re.M)
        c = re.sub(
            r"^[ \t]*timerId\?\.let \{\n(?:[ \t]*[^\n]*\n)*?[ \t]*\}\n",
            "", c, flags=re.M
        )
        c = re.sub(r"^[ \t]*timerId = .*\n", "", c, flags=re.M)
        c = re.sub(r"^[ \t]*timerId\?\..*\n", "", c, flags=re.M)
        if c != orig:
            with open(p, "w") as f:
                f.write(c)
            print(f"cleaned SummarizationTelemetryMiddleware")
            fixed += 1

    print(f"hard-fix: {fixed} files")


if __name__ == "__main__":
    main()
