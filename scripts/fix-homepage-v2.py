#!/usr/bin/env python3
"""
fix-homepage-v2.py — PyreVixen: robust homepage fix using regex.

Instead of fragile exact-string matching, this uses regex to find and replace
the homepage URL resolution logic. It ensures resolveHomepageUrl() reads from
SharedPreferences directly, bypassing any null settings issues.
"""

import re
import sys
from pathlib import Path

def main():
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    usecases_file = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/usecases/FenixBrowserUseCases.kt"
    if not usecases_file.exists():
        print(f"ERROR: not found: {usecases_file}", file=sys.stderr)
        sys.exit(1)

    content = usecases_file.read_text(encoding="utf-8")

    if "PYREVIXEN_HOMEPAGE_V2" in content:
        print("    Already fixed (v2), skipping")
        return

    # Step 1: Ensure we have a context field
    # Find the class declaration and add context if not present
    if "private val appContext" not in content and "val context" not in content:
        # Add context as first constructor param
        content = re.sub(
            r'class FenixBrowserUseCases\(\n',
            'class FenixBrowserUseCases(\n    private val appContext: android.content.Context,\n',
            content,
            count=1
        )
        print("    Added appContext to constructor")

    # Step 2: Replace resolveHomepageUrl with a robust version
    # Match the entire function
    pattern = r'    fun resolveHomepageUrl\(\): String \{.*?\n    \}'
    
    new_func = '''    // PYREVIXEN_HOMEPAGE_V2: Robust homepage URL resolution.
    // Reads directly from SharedPreferences to avoid null settings issues.
    fun resolveHomepageUrl(): String {
        return try {
            val prefs = appContext.getSharedPreferences(
                "fenix_preferences",
                android.content.Context.MODE_PRIVATE,
            )
            val mode = prefs.getString("pref_key_homepage_mode", "default") ?: "default"
            val customUrl = prefs.getString("pref_key_homepage_custom_url", "") ?: ""
            when (mode) {
                "blank" -> "about:blank"
                "custom" -> {
                    val raw = customUrl.trim()
                    when {
                        raw.isEmpty() -> mozilla.components.concept.engine.utils.ABOUT_HOME_URL
                        "://" in raw -> raw
                        else -> "https://$raw"
                    }
                }
                else -> mozilla.components.concept.engine.utils.ABOUT_HOME_URL
            }
        } catch (e: Exception) {
            mozilla.components.concept.engine.utils.ABOUT_HOME_URL
        }
    }'''
    
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, new_func, content, count=1, flags=re.DOTALL)
        print("    Replaced resolveHomepageUrl with robust version")
    else:
        print("    WARNING: resolveHomepageUrl not found, adding it", file=sys.stderr)
        # Add before the closing brace of the class
        content = content.rstrip()
        if content.endswith('}'):
            content = content[:-1] + '\n' + new_func + '\n}\n'

    # Step 3: Ensure the call sites use resolveHomepageUrl()
    # Replace ABOUT_HOME_URL in addNewHomepageTab and navigateToHomepage
    content = content.replace(
        'url = ABOUT_HOME_URL,',
        'url = resolveHomepageUrl(),'
    )
    content = content.replace(
        'loadUrlUseCase.invoke(url = ABOUT_HOME_URL)',
        'loadUrlUseCase.invoke(url = resolveHomepageUrl())'
    )
    print("    Updated call sites to use resolveHomepageUrl()")

    usecases_file.write_text(content, encoding="utf-8")
    print("    done")

    # Step 4: Update UseCases.kt to pass context
    # FenixBrowserUseCases is instantiated in UseCases.kt, not Components.kt
    usecases_wrapper_file = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/UseCases.kt"
    if usecases_wrapper_file.exists():
        c_content = usecases_wrapper_file.read_text(encoding="utf-8")
        if "PYREVIXEN_HOMEPAGE_V2" not in c_content:
            # Find FenixBrowserUseCases instantiation and add appContext
            # Pattern: FenixBrowserUseCases(
            pattern = r'(FenixBrowserUseCases\(\n)'
            if re.search(pattern, c_content):
                c_content = re.sub(
                    pattern,
                    r'\1            appContext = context,\n',
                    c_content,
                    count=1
                )
                # Add marker
                c_content = c_content.replace(
                    'val fenixBrowserUseCases by lazyMonitored {',
                    '// PYREVIXEN_HOMEPAGE_V2\n    val fenixBrowserUseCases by lazyMonitored {',
                    1
                )
                usecases_wrapper_file.write_text(c_content, encoding="utf-8")
                print("    Updated UseCases.kt to pass appContext")
            else:
                print("    WARNING: FenixBrowserUseCases instantiation not found", file=sys.stderr)

    # Step 5: Disable Remote Improvements (rollouts) by default
    settings_file = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt"
    if settings_file.exists():
        s_content = settings_file.read_text(encoding="utf-8")
        if "PYREVIXEN_NO_ROLLOUTS" not in s_content:
            old_rollout = """    var isRolloutsEnabled by
        booleanPreference(
            key = appContext.getPreferenceKey(R.string.pref_key_rollouts),
            default = { appContext.components.nimbus.sdk.rolloutParticipation },
        )"""
            new_rollout = """    // PYREVIXEN_NO_ROLLOUTS: Remote Improvements disabled by default.
    var isRolloutsEnabled by
        booleanPreference(
            key = appContext.getPreferenceKey(R.string.pref_key_rollouts),
            default = false,
        )"""
            if old_rollout in s_content:
                s_content = s_content.replace(old_rollout, new_rollout, 1)
                settings_file.write_text(s_content, encoding="utf-8")
                print("    Disabled Remote Improvements by default")
            else:
                print("    WARNING: isRolloutsEnabled pattern not found", file=sys.stderr)

if __name__ == "__main__":
    main()
