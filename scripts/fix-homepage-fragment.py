#!/usr/bin/env python3
"""
fix-homepage-fragment.py — PyreVixen: Homepage via HomeFragment.

BETTER METHOD: Instead of patching FenixBrowserUseCases (fragile),
patch HomeFragment to check the homepage pref on creation.
If custom URL is set, open it in a new tab instead of showing Firefox Home.
This handles ALL entry points: launch, Home button, new tab.

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

    fragment_file = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/home/HomeFragment.kt"
    if not fragment_file.exists():
        print(f"ERROR: not found: {fragment_file}", file=sys.stderr)
        sys.exit(1)

    content = fragment_file.read_text(encoding="utf-8")

    if "PYREVIXEN_HOMEPAGE_FRAGMENT" in content:
        print("    Already fixed, skipping")
        return

    # Find onViewCreated and add homepage check at the start
    # Pattern: override fun onViewCreated(view: View, savedInstanceState: Bundle?)
    pattern = r'(override fun onViewCreated\(view: View, savedInstanceState: Bundle\?\) \{\n)'
    
    homepage_check = '''    // PYREVIXEN_HOMEPAGE_FRAGMENT: Check for custom homepage.
    // If user has set a custom homepage URL, open it instead of Firefox Home.
    try {
        val prefs = requireContext().getSharedPreferences(
            "fenix_preferences",
            android.content.Context.MODE_PRIVATE,
        )
        val mode = prefs.getString("pref_key_homepage_mode", "default") ?: "default"
        if (mode == "custom") {
            val customUrl = prefs.getString("pref_key_homepage_custom_url", "") ?: ""
            val raw = customUrl.trim()
            if (raw.isNotEmpty()) {
                val url = if ("://" in raw) raw else "https://$raw"
                // Open custom URL in new tab
                requireComponents.useCases.fenixBrowserUseCases.loadUrlOrSearch(url, newTab = true)
                return
            }
        } else if (mode == "blank") {
            requireComponents.useCases.fenixBrowserUseCases.loadUrlOrSearch("about:blank", newTab = true)
            return
        }
    } catch (e: Exception) {
        // Fall through to normal home screen on error
    }

'''
    
    if re.search(pattern, content):
        content = re.sub(pattern, r'\1' + homepage_check, content, count=1)
        fragment_file.write_text(content, encoding="utf-8")
        print("    Added homepage check to HomeFragment.onViewCreated")
    else:
        print("    WARNING: onViewCreated pattern not found", file=sys.stderr)
        # Try alternative pattern
        print("    Searching for onViewCreated...", file=sys.stderr)
        if "onViewCreated" in content:
            idx = content.find("onViewCreated")
            print(f"    Found at: {content[idx:idx+100]}", file=sys.stderr)

    print("    done")

if __name__ == "__main__":
    main()
