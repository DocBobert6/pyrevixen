#!/usr/bin/env python3
"""
scrub-glean.py — PyreVixen: remove all Glean telemetry call sites.

The 020 patch removes the Glean SDK, glean-gradle-plugin, Sentry, Adjust and
InstallReferrer dependencies. That stops generation of org.mozilla.fenix.GleanMetrics,
which ~144 files reference. This script scrubs those references so the tree compiles.

It is idempotent: re-running on an already-scrubbed tree is a no-op.

WHAT IT DOES
  1. Deletes pure-telemetry files (Adjust, InstallReferrer, Glean service wrappers,
     Glean debug tools) that are no longer wired into Analytics.kt.
  2. Removes `import org.mozilla.fenix.GleanMetrics.*` lines.
  3. Removes `import mozilla.telemetry.glean.*` lines (NoExtras, Glean, etc.).
  4. Deletes standalone Glean metric statements (record/set/add/submit/...),
     including multi-line calls.
  5. Rewrites `when` branches `X -> Glean...` as `X -> Unit`.
  6. Deletes single-line `if (cond) Glean...` telemetry guards.
  7. Reports files it could not fully handle for manual follow-up.
"""

import os
import re
import sys

FENIX_JAVA = "mobile/android/fenix/app/src/main/java"

# Files that exist only to wrap removed SDKs. They are no longer referenced
# from Analytics.kt (020 patch); remaining references are scrubbed separately.
DELETE_FILES = [
    "org/mozilla/fenix/components/metrics/AdjustMetricsService.kt",
    "org/mozilla/fenix/components/metrics/AdjustSdkController.kt",
    "org/mozilla/fenix/components/metrics/AdjustThirdPartySharingController.kt",
    "org/mozilla/fenix/components/metrics/DefaultInstallReferrerClient.kt",
    "org/mozilla/fenix/components/metrics/InstallReferrerClientWrapper.kt",
    "org/mozilla/fenix/components/metrics/InstallReferrerHandlingService.kt",
    "org/mozilla/fenix/components/metrics/InstallReferrerWorker.kt",
    "org/mozilla/fenix/components/metrics/InstallReferrerMetricsService.kt",
    "org/mozilla/fenix/components/metrics/GleanMetricsService.kt",
    "org/mozilla/fenix/components/metrics/GleanUsageReporting.kt",
    "org/mozilla/fenix/components/metrics/GleanUsageReportingApi.kt",
    "org/mozilla/fenix/components/metrics/GleanUsageReportingLifecycleObserver.kt",
    "org/mozilla/fenix/components/metrics/GleanUsageReportingMetricsService.kt",
    "org/mozilla/fenix/components/metrics/ActivationPing.kt",
    "org/mozilla/fenix/components/metrics/FirstSessionMetricsService.kt",
    # RTAMO attribution depends on InstallReferrer (deleted above); its only
    # caller is OnboardingFragment (scrubbed below).
    "org/mozilla/fenix/components/metrics/RtamoAttributionHandler.kt",
    # Glean-only helpers (custom server URL); GleanHelper is now a no-op.
    "org/mozilla/fenix/ext/Configuration.kt",
]

DELETE_DIRS = [
    "org/mozilla/fenix/debugsettings/gleandebugtools",
]

GLEANMETRICS_IMPORT = re.compile(r"^import org\.mozilla\.fenix\.GleanMetrics\.[\w.]+(?: as \w+)?$")
GLEAN_SDK_IMPORT = re.compile(r"^import mozilla\.telemetry\.glean\.")
# Also catch the private/internal subpackages.
GLEAN_SDK_IMPORT2 = re.compile(r"^import mozilla\.telemetry\.glean\.(private|internal|config|debug)\.")


def find_glean_aliases(content):
    """Return set of local names imported from org.mozilla.fenix.GleanMetrics."""
    aliases = set()
    for m in re.finditer(
        r"^import org\.mozilla\.fenix\.GleanMetrics\.([\w.]+?)(?: as (\w+))?$",
        content, re.M,
    ):
        full = m.group(1)
        # For `import ...GleanMetrics.Events` -> alias "Events".
        # For `import ...GleanMetrics.Pings.fxAccounts` -> alias "fxAccounts"
        #    (the usable name is the LAST segment).
        # For `import ...GleanMetrics.Events.foo as Bar` -> alias "Bar".
        if m.group(2):
            aliases.add(m.group(2))
        else:
            aliases.add(full.split(".")[-1])
    # Bare `Glean` SDK calls (Glean.updateDistribution, etc.) are also scrubbed.
    if re.search(r"^import mozilla\.telemetry\.glean\.Glean$", content, re.M):
        aliases.add("Glean")
    return aliases


def remove_balanced(lines, start):
    """
    Remove a statement starting at lines[start], consuming following lines until
    parens/braces/brackets balance. Returns (new_lines, removed_count).
    """
    depth = 0
    i = start
    in_str = False
    str_ch = ""
    while i < len(lines):
        line = lines[i]
        j = 0
        while j < len(line):
            ch = line[j]
            if in_str:
                if ch == "\\":
                    j += 1
                elif ch == str_ch:
                    in_str = False
            elif ch in "\"'":
                in_str = True
                str_ch = ch
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            j += 1
        i += 1
        # Statement ends when balanced and we've seen at least one opener,
        # or the line ends without any openers (single-line statement).
        if depth <= 0:
            break
    return lines[:start] + lines[i:], i - start


def scrub_file(path):
    """Scrub one Kotlin file. Returns (changed: bool, notes: list)."""
    with open(path) as f:
        content = f.read()

    aliases = find_glean_aliases(content)
    has_glean_sdk = bool(re.search(r"^import mozilla\.telemetry\.glean\.", content, re.M))
    # Files referencing deleted InstallReferrer/RTAMO classes need the post-pass
    # even without Glean imports.
    has_deleted_refs = bool(re.search(
        r"InstallReferrerHandlingService|RtamoAttributionHandler", content))

    if not aliases and not has_glean_sdk and not has_deleted_refs:
        # Still run the post-pass for the InstallReferrer cleanups below.
        new_content, changed = post_pass(content)
        if changed:
            with open(path, "w") as f:
                f.write(new_content)
        return changed, []

    notes = []
    lines = content.split("\n")
    out = []
    i = 0
    changed = False

    # Pre-pass: remove GleanTimerId variable declarations and orphaned timer
    # scaffolding left behind when the metric calls were deleted.
    cleaned = []
    j = 0
    while j < len(lines):
        line = lines[j]
        stripped = line.strip()
        # `private var timerId: GleanTimerId? = null` -> delete
        if re.match(r"^(\s*)(private\s+)?var\s+\w+\s*:\s*GleanTimerId\?\s*=.*$", line):
            changed = True
            j += 1
            continue
        # `timerId = AiSummarize.duration.start()` / `syncStartId = ...start()`
        # -> delete (variable now unused; the ?.let blocks below are removed too)
        if re.match(r"^\s*\w+\s*=\s*\w+\.\w+\.start\(\)\s*$", stripped):
            # Only if it looks like a Glean timer (RHS category was a Glean alias
            # or the line is a bare timer start).
            changed = True
            j += 1
            continue
        # Orphaned `x?.let {\n x = null\n }` after the Glean call inside was removed.
        if re.match(r"^\s*\w+\?\.let\s*\{\s*$", line):
            if j + 2 < len(lines) and re.match(r"^\s*\w+\s*=\s*null\s*$", lines[j + 1].strip()) \
                    and re.match(r"^\s*\}\s*$", lines[j + 2].strip()):
                changed = True
                j += 3
                continue
        cleaned.append(line)
        j += 1
    lines = cleaned

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 1. Remove Glean imports.
        if GLEANMETRICS_IMPORT.match(stripped) or GLEAN_SDK_IMPORT.match(stripped) \
                or GLEAN_SDK_IMPORT2.match(stripped):
            changed = True
            i += 1
            continue

        # Skip pure comment lines (may mention metric names in docs).
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            out.append(line)
            i += 1
            continue

        # 2. `when` branch: `X -> GleanAlias...` -> `X -> Unit`
        # Also handles `X ->` at end of line with the Glean call on the next line(s).
        m = re.match(r"^(\s*)(.*?\s+->\s*)", line)
        if m:
            rest = line[m.end():]
            handled = False
            for alias in aliases:
                if re.match(r"^" + re.escape(alias) + r"\.", rest.strip()):
                    # Glean call on the same line: replace RHS with Unit.
                    prefix = line[:m.end()]
                    tmp = [line] + lines[i + 1:]
                    _, consumed = remove_balanced(tmp, 0)
                    out.append(prefix + "Unit")
                    changed = True
                    i += consumed
                    handled = True
                    break
            if not handled:
                # Check: line ends with `->` and next line starts with Glean alias.
                if re.match(r"^.*?\s+->\s*$", line):
                    # Peek at next non-empty line.
                    k = i + 1
                    while k < len(lines) and not lines[k].strip():
                        k += 1
                    if k < len(lines):
                        nxt = lines[k].strip()
                        for alias in aliases:
                            if re.match(r"^" + re.escape(alias) + r"\.", nxt):
                                # Replace `X ->` with `X -> Unit`, delete Glean stmt.
                                tmp = lines[k:]  # from the Glean line onward
                                _, consumed = remove_balanced(tmp, 0)
                                out.append(line.rstrip() + " Unit")
                                changed = True
                                i = k + consumed
                                handled = True
                                break
            if handled:
                continue
            out.append(line)
            i += 1
            continue

        # 3. Single-line `if (cond) GleanAlias...` -> delete the whole line.
        # (A bare `if (cond)` with the call on the next line is handled by the
        # standalone-statement rule below.)
        m_if = re.match(r"^\s*if\s*\([^)]*\)\s*\S", line)
        if m_if:
            after = re.sub(r"^\s*if\s*\([^)]*\)\s*", "", line).strip()
            for alias in aliases:
                if re.match(r"^" + re.escape(alias) + r"\.", after):
                    tmp = [line] + lines[i + 1:]
                    _, consumed = remove_balanced(tmp, 0)
                    changed = True
                    i += consumed
                    break
            else:
                out.append(line)
                i += 1
            continue

        # 4. Lambda `{ GleanAlias... },` -> `{ },`
        m_lam = re.match(r"^(\s*)\{\s*", line)
        if m_lam:
            rest = line[m_lam.end():].strip()
            for alias in aliases:
                if re.match(r"^" + re.escape(alias) + r"\.", rest):
                    # Find closing `},` — replace whole lambda body with empty.
                    # Simple case: `{ X.record(...) },` possibly multi-line.
                    tmp = [line] + lines[i + 1:]
                    # Reconstruct: find where the statement ends, keep trailing `},`
                    depth = 0
                    j = 0
                    full = "\n".join(tmp)
                    # Locate the matching close brace for the lambda.
                    k = line.index("{") + 1
                    brace = 1
                    while brace > 0 and j < len(tmp):
                        for ch in tmp[j][k:]:
                            if ch == "{":
                                brace += 1
                            elif ch == "}":
                                brace -= 1
                                if brace == 0:
                                    break
                        else:
                            j += 1
                            k = 0
                            continue
                        break
                    # j is the line with the closing brace; keep from there.
                    closing = tmp[j][tmp[j].index("}", k if j == 0 else 0):]
                    indent = line[:len(line) - len(line.lstrip())]
                    out.append(indent + "{ }" + closing[1:])
                    changed = True
                    i += j + 1
                    break
            else:
                out.append(line)
                i += 1
            continue

        # 4b. `onX = { GleanAlias... },` (lambda argument) -> `onX = { },`.
        m_arg = re.match(r"^(\s*\w+\s*=\s*)\{\s*", line)
        if m_arg:
            rest = line[m_arg.end():].strip()
            for alias in aliases:
                if re.match(r"^" + re.escape(alias) + r"\.", rest):
                    # Replace lambda body with empty, preserving trailing `},`.
                    tmp = [line] + lines[i + 1:]
                    depth = 0
                    j = 0
                    # Find matching close brace.
                    k = line.index("{", m_arg.start()) + 1
                    brace = 1
                    done = False
                    while not done and j < len(tmp):
                        s = tmp[j]
                        start_k = k if j == 0 else 0
                        for idx in range(start_k, len(s)):
                            ch = s[idx]
                            if ch == "{":
                                brace += 1
                            elif ch == "}":
                                brace -= 1
                                if brace == 0:
                                    closing = s[idx:]
                                    out.append(line[:m_arg.end()] + " }" + closing[1:])
                                    changed = True
                                    i += j + 1
                                    done = True
                                    break
                        if not done:
                            j += 1
                            k = 0
                    if done:
                        break
            else:
                out.append(line)
                i += 1
            continue
        # Also: `x?.let { Alias... }` telemetry wrappers -> delete whole line.
        hit = False
        for alias in aliases:
            if re.match(r"^" + re.escape(alias) + r"\.", stripped):
                tmp = [line] + lines[i + 1:]
                _, consumed = remove_balanced(tmp, 0)
                changed = True
                i += consumed
                hit = True
                break
            # `something?.let { Alias.foo(...) }` — pure telemetry wrapper.
            if re.search(r"\?\.let\s*\{[^}]*\b" + re.escape(alias) + r"\.", stripped):
                tmp = [line] + lines[i + 1:]
                _, consumed = remove_balanced(tmp, 0)
                changed = True
                i += consumed
                hit = True
                break
        if hit:
            continue

        # 6. `val x = GleanAlias...` or `= GleanAlias...` (return position) -> note.
        for alias in aliases:
            if re.search(r"\b" + re.escape(alias) + r"\.", stripped):
                notes.append(f"{path}:{i+1}: unhandled Glean usage: {stripped[:100]}")
                break
        out.append(line)
        i += 1

    new_content = "\n".join(out)
    new_content, pp_changed = post_pass(new_content)
    if pp_changed:
        changed = True

    if changed:
        with open(path, "w") as f:
            f.write(new_content)

    # Re-scan the FINAL content: only report Glean references that survived.
    final_aliases = find_glean_aliases(new_content)
    final_notes = []
    for i, line in enumerate(new_content.split("\n")):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        if re.match(r"^import org\.mozilla\.fenix\.GleanMetrics\.", stripped):
            final_notes.append(f"{path}:{i+1}: leftover Glean import: {stripped[:80]}")
            continue
        if re.match(r"^import mozilla\.telemetry\.glean\.", stripped):
            final_notes.append(f"{path}:{i+1}: leftover Glean SDK import: {stripped[:80]}")
            continue
        for alias in final_aliases:
            if re.search(r"\b" + re.escape(alias) + r"\.", stripped):
                # Allow the androidx SplashScreen (not Glean's).
                if "androidx." in stripped:
                    break
                final_notes.append(f"{path}:{i+1}: unhandled Glean usage: {stripped[:100]}")
                break
    return changed, final_notes


def post_pass(content):
    """Targeted fixes for patterns the generic rules miss. Returns (new, changed)."""
    new_content = content
    # 1. getShareToAppSafeExtra() returns a Glean Extra type; its only caller
    #    (the telemetry record call) was deleted. Remove the function.
    new_content = re.sub(
        r"\ninternal fun getShareToAppSafeExtra\(\n(?:.*\n)*?^\}\n",
        "\n", new_content, flags=re.M,
    )
    # 2. Preference default using Glean UUID -> plain random UUID.
    new_content = new_content.replace(
        "default = { TopSites.contextId.generateAndSet().toString() },",
        "default = { java.util.UUID.randomUUID().toString() },",
    )
    # 3. InstallReferrerHandlingService was deleted: remove its usages.
    # 3a. HomeActivity: `if (shouldShowOnboarding) { InstallReferrerHandlingService(...).start() }`
    new_content = re.sub(
        r"\n[ \t]*if \(shouldShowOnboarding\) \{\n[ \t]*InstallReferrerHandlingService\(applicationContext\)\.start\(\)\n[ \t]*\}\n",
        "\n", new_content,
    )
    new_content = re.sub(
        r"^import org\.mozilla\.fenix\.components\.metrics\.InstallReferrerHandlingService\n",
        "", new_content, flags=re.M,
    )
    # 3b. OnboardingFragment: rtamo handler (its class was deleted too).
    new_content = re.sub(
        r"\n[ \t]*private val rtamoAttributionHandler by lazy \{\n[ \t]*RtamoAttributionHandler\(requireContext\(\), requireComponents\.settings, requireComponents\.addonsProvider\)\n[ \t]*\}\n",
        "\n", new_content,
    )
    new_content = re.sub(
        r"\n[ \t]*rtamoAttributionHandler\.handleReferrer\(InstallReferrerHandlingService\.response\)\n",
        "\n", new_content,
    )
    new_content = re.sub(
        r"^import org\.mozilla\.fenix\.components\.metrics\.RtamoAttributionHandler\n",
        "", new_content, flags=re.M,
    )
    # 3c. DistributionTools: debug display of the referrer response.
    new_content = new_content.replace(
        "rawValue: ${InstallReferrerHandlingService.response}",
        "rawValue: n/a (install referrer removed)",
    )
    # 3d. HomeActivity: Glean debug-view tag persistence (debug tools deleted).
    new_content = re.sub(
        r"\n[ \t]*// Persist or clear a Glean debug view tag across restarts \(Nightly/Debug only\)\.\n"
        r"[ \t]*DefaultGleanDebugToolsStorage\.persistDebugViewTagIfRequested\(intent, components\.settings\)\n",
        "\n", new_content,
    )
    new_content = re.sub(
        r"^import org\.mozilla\.fenix\.debugsettings\.gleandebugtools\.DefaultGleanDebugToolsStorage\n",
        "", new_content, flags=re.M,
    )
    # 4. Stale comment referencing the deleted InstallReferrerWorker.
    new_content = new_content.replace(
        "in `InstallReferrerWorker.handleSuccess`",
        "in the (removed) install-referrer handler",
    )
    # 5. ColdStartupDurationTelemetry: the `metric` in `val (metric, typeForLog)`
    #    was a Glean metric. Keep only the log label.
    new_content = re.sub(
        r"val \(metric, typeForLog\) =\n([ \t]*)when \(safeIntent\.action\) \{\n"
        r"[ \t]*Intent\.ACTION_MAIN -> Pair\(PerfStartup\.coldMainAppToFirstFrame, \"MAIN\"\)\n"
        r"[ \t]*Intent\.ACTION_VIEW -> Pair\(PerfStartup\.coldViewAppToFirstFrame, \"VIEW\"\)\n"
        r"[ \t]*else -> Pair\(PerfStartup\.coldUnknwnAppToFirstFrame, \"UNKNOWN\"\)\n"
        r"[ \t]*\}",
        r"val typeForLog =" + "\n" + r"\1when (safeIntent.action) {" + "\n"
        r'\1    Intent.ACTION_MAIN -> "MAIN"' + "\n"
        r'\1    Intent.ACTION_VIEW -> "VIEW"' + "\n"
        r'\1    else -> "UNKNOWN"' + "\n"
        r"\1}",
        new_content,
    )
    # And drop the now-meaningless accumulateSamples on the removed metric.
    new_content = re.sub(
        r"\n[ \t]*metric\.accumulateSamples\(listOf\(durationMillis\)\)\n",
        "\n", new_content,
    )
    # 6. Debug drawer Glean tools UI (the gleandebugtools dir was deleted).
    # 6a. DebugDrawerRoute: remove the GleanDebugTools route.
    new_content = re.sub(
        r"^import org\.mozilla\.fenix\.debugsettings\.gleandebugtools\.GleanDebugToolsStore\n",
        "", new_content, flags=re.M,
    )
    new_content = re.sub(
        r"^import org\.mozilla\.fenix\.debugsettings\.gleandebugtools\.ui\.GleanDebugToolsScreen\n",
        "", new_content, flags=re.M,
    )
    new_content = re.sub(
        r"\n[ \t]*GleanDebugTools\(\n[ \t]*route = \"glean_debug_tools\",\n[ \t]*title = R\.string\.glean_debug_tools_title,\n[ \t]*\),\n",
        "\n", new_content,
    )
    new_content = re.sub(
        r"\n[ \t]*GleanDebugTools -> \{\n[ \t]*onClick = \{\n[ \t]*debugDrawerStore\.dispatch\(DebugDrawerAction\.NavigateTo\.GleanDebugTools\)\n[ \t]*\}\n[ \t]*content = \{\n[ \t]*GleanDebugToolsScreen\(gleanDebugToolsStore = gleanDebugToolsStore\)\n[ \t]*\}\n[ \t]*\}\n",
        "\n", new_content,
    )
    # Remove the gleanDebugToolsStore parameter (keep other params).
    new_content = re.sub(
        r"\n([ \t]*)gleanDebugToolsStore: GleanDebugToolsStore,\n",
        "\n", new_content,
    )
    # 6b. FenixOverlay: remove gleanDebugToolsStore assignments.
    # Find `gleanDebugToolsStore =` and delete to the matching `),`.
    while True:
        m = re.search(r"^([ \t]*)gleanDebugToolsStore =\n", new_content, re.M)
        if not m:
            break
        start = m.start()
        # Find the GleanDebugToolsStore( and balance to its closing ).
        store_start = new_content.index("GleanDebugToolsStore(", m.end())
        depth = 0
        i = store_start + len("GleanDebugToolsStore(")
        depth = 1
        while depth > 0 and i < len(new_content):
            if new_content[i] == "(":
                depth += 1
            elif new_content[i] == ")":
                depth -= 1
            i += 1
        # i is after the closing `)`; consume trailing `,` and newline.
        end = i
        if end < len(new_content) and new_content[end] == ",":
            end += 1
        if end < len(new_content) and new_content[end] == "\n":
            end += 1
        new_content = new_content[:start] + new_content[end:]
    # Remove now-unused imports.
    new_content = re.sub(
        r"^import org\.mozilla\.fenix\.debugsettings\.gleandebugtools\..*\n",
        "", new_content, flags=re.M,
    )
    # 6c. Any remaining DefaultGleanDebugToolsStorage lines (all call sites).
    new_content = re.sub(
        r"^[ \t]*DefaultGleanDebugToolsStorage[^\n]*\n",
        "", new_content, flags=re.M,
    )
    # 6d. DataChoicesMiddleware: clearPersistedDebugViewTag on the deleted storage.
    new_content = re.sub(
        r"^[ \t]*DefaultGleanDebugToolsStorage\(settings\)\.clearPersistedDebugViewTag\(\)\n",
        "", new_content, flags=re.M,
    )
    # 7. RecordedNimbusContext.record(): the whole body is Glean telemetry.
    # Replace with an empty override.
    new_content = re.sub(
        r"    override fun record\(\) \{\n(?:.*\n)*?    \}\n",
        "    override fun record() {\n        // PYREVIXEN: telemetry removed.\n    }\n",
        new_content,
    )
    # 8. StorageStatsMetrics: Metrics.queryStatsDuration.measure { } -> run { }.
    new_content = new_content.replace(
        "Metrics.queryStatsDuration.measure {",
        "run {",
    )
    # 9. (Moved to fix-hard-cases.py)
    # 10. FenixApplication.setTermsOfUseStartUpMetrics: Glean TermsOfUse.
    new_content = re.sub(
        r"    private fun setTermsOfUseStartUpMetrics\(settings: Settings\) \{\n(?:.*\n)*?    \}\n",
        "    private fun setTermsOfUseStartUpMetrics(settings: Settings) {\n"
        "        // PYREVIXEN: telemetry removed.\n"
        "    }\n",
        new_content,
    )
    # 11. (Replaced by #20 below: robust brace-balancing version.)
    # 12. Functions left as `fun name() =` with the RHS deleted (was a Glean
    # call). Give them an empty body.
    new_content = re.sub(
        r"^([ \t]*fun \w+\([^)]*\) =\s*)\n(?=[ \t]*(?:/\*\*|fun |val |var |private |public |internal |override |\}))",
        r"\1{}\n",
        new_content, flags=re.M,
    )
    # More robust: `fun x() =` followed by blank line then a non-expression.
    new_content = re.sub(
        r"^([ \t]*fun (\w+)\([^)]*\) =)[ \t]*\n[ \t]*\n",
        r"\1 {}\n",
        new_content, flags=re.M,
    )
    # 13. Debug drawer: remove the NavigateTo.GleanDebugTools branch.
    new_content = re.sub(
        r"^[ \t]*is DebugDrawerAction\.NavigateTo\.GleanDebugTools ->\n"
        r"[ \t]*navController\.navigate\(route = DebugDrawerRoute\.GleanDebugTools\.route\)\n",
        "", new_content, flags=re.M,
    )
    # 14. Activity: remove the FromGleanDebugToolsFragment direction.
    new_content = re.sub(
        r"^[ \t]*BrowserDirection\.FromGleanDebugToolsFragment -> GleanDebugToolsFragmentDirections\.actionGlobalBrowser\(\)\n",
        "", new_content, flags=re.M,
    )
    # 15. Glean timer IDs: replace usages with no-ops (preserve structure).
    # Field declarations: private var x: GleanTimerId? = null -> private var x: Any? = null
    new_content = re.sub(
        r"private var (\w+): GleanTimerId\? = null",
        r"private var \1: Any? = null",
        new_content,
    )
    # Glean timer start/cancel calls -> null assignment or no-op.
    new_content = re.sub(
        r"\w+ = \w+\.\w+\.start\(\)",
        "null",
        new_content,
    )
    # 16. HomeSettingsFragment: remove customizeHomeMetrics field and its record calls.
    new_content = re.sub(
        r"^[ \t]*@VisibleForTesting internal var customizeHomeMetrics: CustomizeHome = CustomizeHome\n",
        "", new_content, flags=re.M,
    )
    # Remove customizeHomeMetrics.preferenceToggled.record( ... ) blocks.
    new_content = re.sub(
        r"[ \t]*customizeHomeMetrics\.preferenceToggled\.record\(\n(?:[^\n]*\n)*?[ \t]*\)\n",
        "", new_content,
    )
    # 17. Settings: TopSites.contextId (Glean) used as a preference default.
    # Replace with a plain UUID.
    new_content = new_content.replace(
        "TopSites.contextId.generateAndSet().toString()",
        "java.util.UUID.randomUUID().toString()",
    )
    # 18. (Handled in fix-hard-cases.py: proper else insertion.)
    # 19. FenixOverlay call sites: remove gleanDebugToolsStore argument.
    new_content = re.sub(
        r"^[ \t]*gleanDebugToolsStore =[^\n]*,\n",
        "",
        new_content, flags=re.M,
    )
    # 20. StorageStatsMetrics.reportSync: use brace balancing (robust).
    m = re.search(r"    fun reportSync\(context: Context\) \{\n", new_content)
    if m:
        start = m.start()
        depth = 1
        i = m.end()
        while depth > 0 and i < len(new_content):
            if new_content[i] == "{":
                depth += 1
            elif new_content[i] == "}":
                depth -= 1
            i += 1
        new_func = (
            "    fun reportSync(context: Context) {\n"
            "        // PYREVIXEN: telemetry removed.\n"
            "    }\n"
        )
        new_content = new_content[:start] + new_func + new_content[i:]
    return new_content, new_content != content


def preserve_utm_params(worker_path, java_root):
    """
    Write a minimal UTMParams.kt. The original in InstallReferrerWorker.kt
    mixes pure data/parsing with Glean telemetry (recordInstallReferrer).
    Only the data class, constants, and pure parsing are preserved;
    DistributionIdManager and ReferralAttribution use just those.
    """
    out = """package org.mozilla.fenix.components.metrics

// PYREVIXEN: Minimal UTMParams preserved from the deleted
// InstallReferrerWorker.kt. Pure data holder + parsing; the Glean-dependent
// recordInstallReferrer() was removed with the telemetry.

data class UTMParams(
    val source: String,
    val medium: String,
    val campaign: String,
    val content: String,
    val term: String,
) {

    companion object {
        const val UTM_SOURCE = "utm_source"
        const val UTM_MEDIUM = "utm_medium"
        const val UTM_CAMPAIGN = "utm_campaign"
        const val UTM_CONTENT = "utm_content"
        const val UTM_TERM = "utm_term"

        /** Try and unpack the install referrer response. */
        fun parseInstallReferrer(installReferrerResponse: String): Map<String, String> {
            val params = mutableMapOf<String, String>()
            for (param in installReferrerResponse.split("&")) {
                val keyValue = param.split("=", limit = 2)
                if (keyValue.size == 2) {
                    params[keyValue[0]] = keyValue[1]
                }
            }
            return params
        }

        /** Extract the [UTMParams] from the install referrer response. */
        fun parseUTMParameters(installReferrerResponse: String): UTMParams {
            val utmParams = parseInstallReferrer(installReferrerResponse)
            return UTMParams(
                source = utmParams[UTM_SOURCE] ?: "",
                medium = utmParams[UTM_MEDIUM] ?: "",
                campaign = utmParams[UTM_CAMPAIGN] ?: "",
                content = utmParams[UTM_CONTENT] ?: "",
                term = utmParams[UTM_TERM] ?: "",
            )
        }
    }

    /**
     * Check if this UTM param is empty
     *
     * @return [Boolean] true if none of the utm params are set.
     */
    fun isEmpty(): Boolean {
        return source.isBlank() && medium.isBlank() && campaign.isBlank() && term.isBlank() && content.isBlank()
    }
}
"""
    dest = os.path.join(java_root, "org/mozilla/fenix/components/metrics/UTMParams.kt")
    with open(dest, "w") as f:
        f.write(out)
    print("preserved UTMParams.kt (minimal)")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    java_root = os.path.join(root, FENIX_JAVA)

    # Step 1: delete pure-telemetry files/dirs.
    for rel in DELETE_FILES:
        p = os.path.join(java_root, rel)
        if os.path.exists(p):
            # InstallReferrerWorker.kt contains the UTMParams data class, which
            # is still used by DistributionIdManager and ReferralAttribution.
            # Preserve it as a standalone file instead of deleting.
            if rel.endswith("InstallReferrerWorker.kt"):
                preserve_utm_params(p, java_root)
            os.remove(p)
            print(f"deleted {rel}")
    for rel in DELETE_DIRS:
        p = os.path.join(java_root, rel)
        if os.path.isdir(p):
            import shutil
            shutil.rmtree(p)
            print(f"deleted dir {rel}")

    # Step 2: scrub remaining files.
    all_notes = []
    changed_count = 0
    for dirpath, _, filenames in os.walk(java_root):
        for fn in filenames:
            if not fn.endswith(".kt"):
                continue
            p = os.path.join(dirpath, fn)
            changed, notes = scrub_file(p)
            if changed:
                changed_count += 1
            all_notes.extend(notes)

    print(f"scrubbed {changed_count} files")
    if all_notes:
        print(f"\n{len(all_notes)} usages need manual review:")
        for n in sorted(set(all_notes))[:50]:
            print(f"  {n}")
        if len(set(all_notes)) > 50:
            print(f"  ... and {len(set(all_notes)) - 50} more")


if __name__ == "__main__":
    main()
