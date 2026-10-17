#!/usr/bin/env python3
"""
fix-privacy-defaults-extra.py — PyreVixen: additional privacy defaults.

Based on Robert's screenshot review (2026-10-15):
- "Tell websites not to share & sell data" (Global Privacy Control) was OFF.
  For a privacy-forward browser, this should default to ON.

Fix: Change shouldEnableGlobalPrivacyControl default from false to true.

Idempotent: safe to re-run.
"""

import sys
from pathlib import Path

def main():
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    settings_file = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt"
    content = settings_file.read_text(encoding="utf-8")

    if "PYREVIXEN_GPC_DEFAULT" in content:
        print("    Settings.kt already fixed, skipping")
        return

    old = """    var shouldEnableGlobalPrivacyControl by
        booleanPreference(
            appContext.getPreferenceKey(R.string.pref_key_privacy_enable_global_privacy_control),
            false,
        )"""

    new = """    // PYREVIXEN_GPC_DEFAULT: Global Privacy Control is on by default.
    var shouldEnableGlobalPrivacyControl by
        booleanPreference(
            appContext.getPreferenceKey(R.string.pref_key_privacy_enable_global_privacy_control),
            true,
        )"""

    if old not in content:
        print("    WARNING: pattern not found", file=sys.stderr)
        return

    content = content.replace(old, new, 1)
    settings_file.write_text(content, encoding="utf-8")
    print("    enabled Global Privacy Control by default")

if __name__ == "__main__":
    main()
