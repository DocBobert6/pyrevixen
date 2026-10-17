#!/usr/bin/env python3
"""
fix-data-collection-defaults.py — PyreVixen: all Data Collection options OFF by default.

Robert's request (2026-10-15): every option on the Data Collection settings
screen defaults to OFF. Full removal of the menu comes later, after he
confirms this build.

Fix:
1. Settings.kt: isTelemetryEnabled default true -> false. The daily usage
   ping and Studies (experimentation) defaults are defined as
   `default = isTelemetryEnabled`, so they follow automatically.
   Marketing data already defaults to false. Crash report choice default
   Ask -> Never (PyreVixen crash reports are local-only anyway).
2. FenixApplication.kt: one-time migration that applies the same values to
   installs predating the new defaults (prefs already persisted as true on
   upgraded devices would otherwise ignore the new defaults). Runs in the
   main process before any metrics/Glean initialization reads the prefs.

Idempotent: safe to re-run.
"""

import sys
from pathlib import Path

SETTINGS_REL = "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/Settings.kt"
APP_REL = "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt"


def patch_settings(path: Path):
    content = path.read_text(encoding="utf-8")
    if "PYREVIXEN_DATA_DEFAULTS" in content:
        print("    Settings.kt already patched, skipping")
        return

    old_telemetry = """    var isTelemetryEnabled by
        booleanPreference(
            appContext.getPreferenceKey(R.string.pref_key_telemetry),
            default = true,
        )"""
    new_telemetry = """    // PYREVIXEN_DATA_DEFAULTS: usage and technical data are off by default.
    var isTelemetryEnabled by
        booleanPreference(
            appContext.getPreferenceKey(R.string.pref_key_telemetry),
            default = false,
        )"""
    if old_telemetry not in content:
        print("    WARNING: isTelemetryEnabled pattern not found", file=sys.stderr)
        return
    content = content.replace(old_telemetry, new_telemetry, 1)

    old_crash = """    var crashReportChoice by
        stringPreference(
            appContext.getPreferenceKey(R.string.pref_key_crash_reporting_choice),
            default = CrashReportOption.Ask.toString(),
        )"""
    new_crash = """    // PYREVIXEN_DATA_DEFAULTS: crash reports default to never (local-only anyway).
    var crashReportChoice by
        stringPreference(
            appContext.getPreferenceKey(R.string.pref_key_crash_reporting_choice),
            default = CrashReportOption.Never.toString(),
        )"""
    if old_crash not in content:
        print("    WARNING: crashReportChoice pattern not found", file=sys.stderr)
        return
    content = content.replace(old_crash, new_crash, 1)

    path.write_text(content, encoding="utf-8")
    print("    Settings.kt: telemetry default off, crash reports default never")


def patch_application(path: Path):
    content = path.read_text(encoding="utf-8")
    if "PYREVIXEN_DATA_DEFAULTS" in content:
        print("    FenixApplication.kt already patched, skipping")
        return

    anchor = """        runOnlyInMainProcess {
            // Start loading the SharedPreferences file from disk on a background thread immediately."""
    call = """        runOnlyInMainProcess {
            // PYREVIXEN_DATA_DEFAULTS: apply Data Collection opt-outs once, before
            // metrics or Glean initialization read the prefs.
            applyPyrevixenDataCollectionDefaults()
            // Start loading the SharedPreferences file from disk on a background thread immediately."""
    if anchor not in content:
        print("    WARNING: runOnlyInMainProcess anchor not found", file=sys.stderr)
        return
    content = content.replace(anchor, call, 1)

    func_anchor = "    private fun applySecretSettingsOverrides(context: Context) {"
    func = """    /**
     * One-time migration applying the Data Collection opt-out defaults to installs that
     * predate them (already-persisted opt-ins would otherwise ignore the new defaults).
     * New installs get the same values from the Settings defaults.
     */
    private fun applyPyrevixenDataCollectionDefaults() {
        val prefs = getSharedPreferences(Settings.FENIX_PREFERENCES, MODE_PRIVATE)
        if (prefs.getBoolean("pref_pyrevixen_data_defaults_v1", false)) return
        prefs.edit {
            putBoolean("pref_key_telemetry", false)
            putBoolean("pref_key_daily_usage_ping", false)
            putBoolean("pref_key_experimentation_v2", false)
            putBoolean("pref_key_marketing_telemetry", false)
            putString("pref_key_crash_reporting_choice", CrashReportOption.Never.label)
            putBoolean("pref_pyrevixen_data_defaults_v1", true)
        }
    }

"""
    if func_anchor not in content:
        print("    WARNING: function anchor not found", file=sys.stderr)
        return
    content = content.replace(func_anchor, func + func_anchor, 1)

    old_imports = "import org.mozilla.fenix.utils.Settings\n"
    if "mozilla.components.lib.crash.store.CrashReportOption" not in content:
        if old_imports not in content:
            print("    WARNING: Settings import not found for import anchor", file=sys.stderr)
            return
        content = content.replace(
            old_imports,
            old_imports + "import mozilla.components.lib.crash.store.CrashReportOption\n",
            1,
        )

    path.write_text(content, encoding="utf-8")
    print("    FenixApplication.kt: one-time data-collection defaults migration added")


def main():
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    patch_settings(source_dir / SETTINGS_REL)
    patch_application(source_dir / APP_REL)


if __name__ == "__main__":
    main()
