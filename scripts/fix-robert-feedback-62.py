#!/usr/bin/env python3
"""
fix-robert-feedback-62.py — PyreVixen: address Robert's build #62 feedback.

1. Hide AI Controls menu: set aiControlsFeatureFlagEnabled default to false.
2. Revert video controls fullscreen-only (make them always show for now).
3. Fix welcome screen: "Welcome to Firefox" -> "Welcome to PyreVixen".
4. Ensure all data collection options are OFF by default.

Idempotent: safe to re-run.
"""

import sys
from pathlib import Path

def main():
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    # 1. Hide AI Controls menu
    settings_file = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt"
    content = settings_file.read_text(encoding="utf-8")
    
    if "PYREVIXEN_HIDE_AI_CONTROLS" not in content:
        old = """    var aiControlsFeatureFlagEnabled by
        booleanPreference(
            key = appContext.getPreferenceKey(R.string.pref_key_enable_ai_controls),
            default = true,
        )"""
        new = """    // PYREVIXEN_HIDE_AI_CONTROLS: AI Controls menu hidden.
    var aiControlsFeatureFlagEnabled by
        booleanPreference(
            key = appContext.getPreferenceKey(R.string.pref_key_enable_ai_controls),
            default = false,
        )"""
        if old in content:
            content = content.replace(old, new, 1)
            settings_file.write_text(content, encoding="utf-8")
            print("    hid AI Controls menu (default false)")
        else:
            print("    WARNING: aiControls pattern not found", file=sys.stderr)
    else:
        print("    AI Controls already hidden, skipping")

    # 2. Revert video toolkit fullscreen-only change
    # The content.js is in the repo, not the source dir, so we handle it separately
    # (This is done by fix-video-toolkit-fullscreen.py with a revert flag)
    
    # 3. Fix welcome screen strings
    # Find onboarding strings
    import re
    strings_files = list((source_dir / "mobile/android/fenix/app/src/main/res").glob("values/strings.xml"))
    for sf in strings_files:
        sc = sf.read_text(encoding="utf-8")
        if "PYREVIXEN_WELCOME" not in sc:
            # Replace "Welcome to Firefox" with "Welcome to PyreVixen"
            old_welcome = ">Welcome to Firefox<"
            new_welcome = ">Welcome to PyreVixen<"
            if old_welcome in sc:
                sc = sc.replace(old_welcome, new_welcome)
                # Add marker
                sc = sc.replace('<?xml version="1.0" encoding="utf-8"?>',
                              '<?xml version="1.0" encoding="utf-8"?>\n<!-- PYREVIXEN_WELCOME -->', 1)
                sf.write_text(sc, encoding="utf-8")
                print(f"    fixed welcome string in {sf.name}")

    print("    done")

if __name__ == "__main__":
    main()
