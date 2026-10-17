#!/usr/bin/env python3
"""
fix-sponsored-content.py — PyreVixen: Remove sponsored content options.

Hides:
- Sponsored shortcuts (Contile) from Homepage settings
- Sponsored stories (Pocket) from Homepage settings
- Sponsored suggestions from Search settings

Idempotent: safe to re-run.
"""

import re
import sys
from pathlib import Path

def hide_preference(content, key_string, marker):
    """Add app:isPreferenceVisible="false" to a preference with the given key."""
    if marker in content:
        return content, False
    
    # Pattern to find the preference tag
    pattern = rf'(<androidx\.preference\.(?:SwitchPreferenceCompat|CheckBoxPreference|Preference)[^>]*android:key="@string/{key_string}"[^>]*>)'
    
    def add_hidden(m):
        tag = m.group(1)
        if 'isPreferenceVisible' not in tag:
            # Handle both self-closing ("/>" ) and regular (">") tags
            if tag.endswith('/>'):
                # Self-closing: insert before "/>"
                tag = tag[:-2] + ' app:isPreferenceVisible="false"/>'
            else:
                # Regular: insert before ">"
                tag = tag[:-1] + ' app:isPreferenceVisible="false">'
        return tag + f'<!-- {marker} -->'
    
    new_content, count = re.subn(pattern, add_hidden, content, count=1)
    return new_content, count > 0

def main():
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    # 1. Homepage preferences: hide sponsored shortcuts and stories
    home_prefs = source_dir / "mobile/android/fenix/app/src/main/res/xml/home_preferences.xml"
    if home_prefs.exists():
        content = home_prefs.read_text(encoding="utf-8")
        
        # Sponsored shortcuts (Contile)
        content, changed = hide_preference(content, "pref_key_enable_contile", "PYREVIXEN_HIDE_SPONSORED_SHORTCUTS")
        if changed:
            print("    Hid Sponsored shortcuts (Contile)")
        
        # Sponsored stories (Pocket)
        content, changed = hide_preference(content, "pref_key_pocket_sponsored_stories", "PYREVIXEN_HIDE_SPONSORED_STORIES")
        if changed:
            print("    Hid Sponsored stories (Pocket)")
        
        home_prefs.write_text(content, encoding="utf-8")
    else:
        print(f"    WARNING: not found: {home_prefs}", file=sys.stderr)

    # 2. Search preferences: hide sponsored suggestions
    search_prefs = source_dir / "mobile/android/fenix/app/src/main/res/xml/search_settings_preferences.xml"
    if search_prefs.exists():
        content = search_prefs.read_text(encoding="utf-8")
        
        content, changed = hide_preference(content, "pref_key_show_sponsored_suggestions", "PYREVIXEN_HIDE_SPONSORED_SUGGESTIONS")
        if changed:
            print("    Hid Sponsored suggestions (Search)")
        
        search_prefs.write_text(content, encoding="utf-8")

    print("    done")

if __name__ == "__main__":
    main()
