#!/usr/bin/env python3
"""
fix-glean-crash.py — PyreVixen: minimal Glean init to prevent launch crash.

Build #46 crashed on launch because 020-geckoview-lite-no-glean.patch no-op'd
GleanHelper.initializeGlean entirely. The Glean SDK crashes if metrics are
recorded without the SDK being initialized.

This script replaces the no-op with a MINIMAL Glean.initialize() call that:
  - Initializes the SDK (prevents crash)
  - Forces uploadEnabled=false (no telemetry ever leaves the device)
  - Skips ping registration, Nimbus config, and debug tools

Idempotent: safe to re-run.
"""

import sys
from pathlib import Path

def main():
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    glean_helper = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/GleanHelper.kt"
    if not glean_helper.is_file():
        print(f"ERROR: GleanHelper.kt not found: {glean_helper}", file=sys.stderr)
        sys.exit(1)

    content = glean_helper.read_text(encoding="utf-8")

    # --- Restore imports stripped by 020 ---
    # 020 removed the Glean SDK imports. We need them for Glean.initialize().
    imports_fixed = False
    if "import mozilla.telemetry.glean.Glean" not in content:
        # Find the import block and add our imports
        # Look for the package line and first import
        lines = content.split("\n")
        new_lines = []
        for i, line in enumerate(lines):
            new_lines.append(line)
            # After the package declaration, add imports
            if line.startswith("package ") and i+1 < len(lines):
                # Check if next line is already an import
                pass
        # Simpler: add imports after package line
        content = content.replace(
            "package org.mozilla.fenix.components\n",
            "package org.mozilla.fenix.components\n\nimport mozilla.telemetry.glean.Glean\nimport org.mozilla.fenix.GleanMetrics.GleanBuildInfo\n",
            1
        )
        imports_fixed = True
        print("    restored Glean imports")

    old = '    logger.debug("PyreVixen: Glean telemetry is disabled; initialization skipped.")\n}'
    new = '''    // PYREVIXEN: Minimal Glean initialization to prevent crashes.
    // The SDK must be initialized or the app crashes on launch when
    // metrics are recorded. Upload is FORCED OFF - no telemetry leaves the device.
    // We skip ping registration, Nimbus config, and debug tools.
    logger.debug("PyreVixen: Glean initialized with upload DISABLED (privacy mode).")
    Glean.initialize(
        applicationContext = applicationContext,
        uploadEnabled = false,
        buildInfo = GleanBuildInfo.buildInfo,
    )
}'''

    if old not in content:
        # Already fixed or 020 not applied yet
        if "PyreVixen: Glean initialized with upload DISABLED" in content:
            print("    already fixed, skipping")
        else:
            print("    WARNING: expected no-op line not found, skipping", file=sys.stderr)
        return

    content = content.replace(old, new)
    glean_helper.write_text(content, encoding="utf-8")
    print("    fixed GleanHelper.initializeGlean: minimal init with upload=false")

if __name__ == "__main__":
    main()
