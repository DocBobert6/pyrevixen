#!/usr/bin/env python3
"""
fix-ai-translations.py — PyreVixen: disable AI Translations by default.

Robert requested (2026-10-15): AI Controls can stay, but AI Translations
should be toggled OFF by default.

The TranslationsAIControllableFeature is dynamically registered via
TranslationsAIControllableFeatureRegistrar in HomeActivity. By not
instantiating the registrar, the feature is never registered, so the
toggle will not appear as enabled.

Idempotent: safe to re-run.
"""

import sys
from pathlib import Path

def main():
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    activity_file = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/HomeActivity.kt"
    content = activity_file.read_text(encoding="utf-8")

    if "PYREVIXEN_NO_AI_TRANSLATIONS" in content:
        print("    HomeActivity.kt already fixed, skipping")
        return

    # Find the lazy property and replace it with a no-op
    # The registrar is a LifecycleObserver; we replace it with a dummy that does nothing
    old_property = """    private val translationsAIControllableFeatureRegistrar by lazy {
        with(components) {
            TranslationsAIControllableFeatureRegistrar(
                aiRegistry = aiFeatureRegistry,
                browserStore = core.store,
                translationsEnabledSettings = TranslationsEnabledSettings.dataStore(this@HomeActivity),
                scope = lifecycleScope,
            )
        }
    }"""

    # Instead of null, we keep the type but make it a no-op by not registering anything.
    # The simplest safe approach: create the registrar but never add it to lifecycle.
    # We do this by replacing the usage site, not the property.
    # For now, keep the property but make it lazy-initialized to a dummy.
    # Actually, the cleanest is to just remove it from the observers list below.
    
    # Let's do a different approach: comment out the registrar from the observers list
    observers_pattern = "            translationsAIControllableFeatureRegistrar,"
    
    if observers_pattern in content:
        content = content.replace(
            observers_pattern,
            "            // PYREVIXEN_NO_AI_TRANSLATIONS: registrar not added to lifecycle\n",
            1
        )
        # Also mark the property as unused to avoid warnings
        if "PYREVIXEN_NO_AI_TRANSLATIONS" not in content:
            content = content.replace(
                "    private val translationsAIControllableFeatureRegistrar by lazy {",
                "    // PYREVIXEN_NO_AI_TRANSLATIONS: AI Translations disabled by default.\n    @Suppress(\"unused\")\n    private val translationsAIControllableFeatureRegistrar by lazy {",
                1
            )
        activity_file.write_text(content, encoding="utf-8")
        print("    removed registrar from lifecycle observers")
    else:
        print("    WARNING: observers pattern not found", file=sys.stderr)
        if "PYREVIXEN_NO_AI_TRANSLATIONS" in content:
            print("    Already fixed, skipping")
        return

if __name__ == "__main__":
    main()
