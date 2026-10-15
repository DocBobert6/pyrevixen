#!/usr/bin/env python3
"""
fix-homepage-routing.py — PyreVixen: fix homepage settings not taking effect.

Problem: The 080 patch threads Settings through Components -> UseCases ->
FenixBrowserUseCases as a nullable param. If settings is null at any point,
resolveHomepageUrl() falls back to ABOUT_HOME_URL, ignoring user preferences.

Fix: Make FenixBrowserUseCases read homepage prefs directly from
SharedPreferences via the application context, bypassing the fragile
constructor threading. This is robust and always works.

Idempotent: safe to re-run.
"""

import sys
from pathlib import Path

def main():
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    usecases_file = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/usecases/FenixBrowserUseCases.kt"
    content = usecases_file.read_text(encoding="utf-8")

    # Check if already fixed
    if "PYREVIXEN_HOMEPAGE_FIX" in content:
        print("    FenixBrowserUseCases.kt already fixed, skipping")
        return

    # Find the resolveHomepageUrl function and replace it with a version
    # that reads directly from SharedPreferences
    old_resolve = """    fun resolveHomepageUrl(): String {
        return when (settings?.homepageMode) {"""

    new_resolve = """    // PYREVIXEN_HOMEPAGE_FIX: Read homepage prefs directly from SharedPreferences
    // instead of relying on the nullable settings param, which may be null.
    fun resolveHomepageUrl(): String {
        // Fenix uses "fenix_preferences" (see Settings.kt FENIX_PREFERENCES).
        val prefs = context.getSharedPreferences(
            "fenix_preferences",
            android.content.Context.MODE_PRIVATE,
        )
        // The pref keys are stored as string resources; get the actual key names.
        // Default values match those in Settings.kt.
        val mode = prefs.getString("pref_key_homepage_mode", "default") ?: "default"
        val customUrl = prefs.getString("pref_key_homepage_custom_url", "") ?: ""
        return when (mode) {"""

    if old_resolve not in content:
        print("    WARNING: resolveHomepageUrl pattern not found", file=sys.stderr)
        # Try alternative pattern
        print("    Content preview:", content[content.find("resolveHomepageUrl"):content.find("resolveHomepageUrl")+200] if "resolveHomepageUrl" in content else "NOT FOUND", file=sys.stderr)
        return

    content = content.replace(old_resolve, new_resolve, 1)

    # Also fix the custom URL branch which references settings.homepageCustomUrl
    old_custom = """            "custom" -> {
                val raw = settings.homepageCustomUrl.trim()"""

    new_custom = """            "custom" -> {
                val raw = customUrl.trim()"""

    if old_custom in content:
        content = content.replace(old_custom, new_custom, 1)
        print("    fixed custom URL branch")

    # Add context parameter to constructor if not present
    old_constructor = """class FenixBrowserUseCases(
    private val appStore: AppStore,
    private val tabsUseCases: TabsUseCases,
    private val loadUrlUseCase: SessionUseCases.DefaultLoadUrlUseCase,
    private val searchUseCases: SearchUseCases,
    private val homepageTitle: String,
    private val profiler: Profiler?,"""

    new_constructor = """class FenixBrowserUseCases(
    private val context: android.content.Context,
    private val appStore: AppStore,
    private val tabsUseCases: TabsUseCases,
    private val loadUrlUseCase: SessionUseCases.DefaultLoadUrlUseCase,
    private val searchUseCases: SearchUseCases,
    private val homepageTitle: String,
    private val profiler: Profiler?,"""

    if old_constructor in content:
        content = content.replace(old_constructor, new_constructor, 1)
        print("    added context to FenixBrowserUseCases constructor")
    elif "private val context:" in content:
        print("    context already in constructor")
    else:
        print("    WARNING: constructor pattern not found", file=sys.stderr)
        return

    usecases_file.write_text(content, encoding="utf-8")
    print("    fixed FenixBrowserUseCases.resolveHomepageUrl() to read prefs directly")

    # Also update UseCases.kt to pass context to FenixBrowserUseCases
    usecases_kt = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/UseCases.kt"
    uc_content = usecases_kt.read_text(encoding="utf-8")

    if "PYREVIXEN_HOMEPAGE_FIX" not in uc_content:
        old_init = """    val fenixBrowserUseCases by lazyMonitored {
        FenixBrowserUseCases(
            appStore = appStore.value,"""
        new_init = """    // PYREVIXEN_HOMEPAGE_FIX: pass context for direct pref access
    val fenixBrowserUseCases by lazyMonitored {
        FenixBrowserUseCases(
            context = context,
            appStore = appStore.value,"""
        if old_init in uc_content:
            uc_content = uc_content.replace(old_init, new_init, 1)
            usecases_kt.write_text(uc_content, encoding="utf-8")
            print("    updated UseCases.kt to pass context")
        else:
            print("    WARNING: UseCases.kt pattern not found", file=sys.stderr)

if __name__ == "__main__":
    main()
