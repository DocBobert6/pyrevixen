#!/usr/bin/env python3
"""
fix-settings-cleanup.py — PyreVixen: remove AI Controls and Remote Improvements from settings.

Problem: 
- AI Controls screen still appears in Settings with "Block AI Enhancements" toggle
  and "AI Translations" toggle. Patch 030 emptied the aiFeatureRegistry but the
  settings entry and Translations feature remain.
- "Remote improvements" (Nimbus experiments remote config) is ON by default.
  For a privacy browser with no experiments, this should not be present.

Fix: Remove both preference entries from preferences.xml so they don't appear
in Settings at all.

Idempotent: safe to re-run.
"""

import re
import sys
from pathlib import Path

def main():
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    prefs_file = source_dir / "mobile/android/fenix/app/src/main/res/xml/preferences.xml"
    content = prefs_file.read_text(encoding="utf-8")

    if "PYREVIXEN_SETTINGS_CLEANUP" in content:
        print("    preferences.xml already cleaned, skipping")
        return

    original_len = len(content)

    # Remove AI Controls preference entry
    # Pattern: <Preference ... android:key="@string/pref_key_ai_controls" ... />
    ai_pattern = r'\s*<Preference[^>]*android:key="@string/pref_key_ai_controls"[^>]*/?>.*?(?:</Preference>)?'
    content, ai_count = re.subn(ai_pattern, '', content, flags=re.DOTALL)
    
    # Remove Remote Improvements preference entry
    remote_pattern = r'\s*<Preference[^>]*android:key="@string/pref_key_remote_improvements"[^>]*/?>.*?(?:</Preference>)?'
    content, remote_count = re.subn(remote_pattern, '', content, flags=re.DOTALL)

    # Add marker comment
    content = content.replace(
        '<?xml version="1.0" encoding="utf-8"?>',
        '<?xml version="1.0" encoding="utf-8"?>\n<!-- PYREVIXEN_SETTINGS_CLEANUP: AI Controls and Remote Improvements removed -->',
        1
    )

    prefs_file.write_text(content, encoding="utf-8")
    print(f"    removed AI Controls ({ai_count}) and Remote Improvements ({remote_count}) from preferences.xml")
    print(f"    size: {original_len} -> {len(content)}")

    # Also remove sponsored toggles from home_preferences.xml
    home_prefs_file = source_dir / "mobile/android/fenix/app/src/main/res/xml/home_preferences.xml"
    if home_prefs_file.exists():
        hp_content = home_prefs_file.read_text(encoding="utf-8")
        if "PYREVIXEN_SPONSORED_CLEANUP" not in hp_content:
            hp_original = len(hp_content)
            # Remove sponsored shortcuts checkbox
            hp_content, sc_count = re.subn(
                r'\s*<CheckBoxPreference[^>]*android:key="@string/pref_key_sponsored_shortcuts"[^>]*/?>.*?(?:</CheckBoxPreference>)?',
                '', hp_content, flags=re.DOTALL
            )
            # Remove sponsored stories checkbox  
            hp_content, ss_count = re.subn(
                r'\s*<CheckBoxPreference[^>]*android:key="@string/pref_key_sponsored_stories"[^>]*/?>.*?(?:</CheckBoxPreference>)?',
                '', hp_content, flags=re.DOTALL
            )
            hp_content = hp_content.replace(
                '<?xml version="1.0" encoding="utf-8"?>',
                '<?xml version="1.0" encoding="utf-8"?>\n<!-- PYREVIXEN_SPONSORED_CLEANUP: sponsored toggles removed -->',
                1
            )
            home_prefs_file.write_text(hp_content, encoding="utf-8")
            print(f"    removed sponsored shortcuts ({sc_count}) and stories ({ss_count}) from home_preferences.xml")

if __name__ == "__main__":
    main()
