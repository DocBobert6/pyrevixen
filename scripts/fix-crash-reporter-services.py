#!/usr/bin/env python3
"""
fix-crash-reporter-services.py — PyreVixen: add no-op crash service.

Build #54 crashed on launch with:
  java.lang.IllegalArgumentException: No crash reporter services defined

Root cause: patch 020 removed SentryService and MozillaSocorroService,
leaving the services list empty. CrashReporter requires at least one service.

Fix: create a no-op CrashReporterService that does nothing, and add it to
the services list in Analytics.kt. Crash reports are handled by our own
PyreVixenCrashReporter (saves to Downloads), not by Mozilla's infrastructure.

Idempotent: safe to re-run.
"""

import sys
from pathlib import Path

NOOP_SERVICE_KT = '''package org.mozilla.fenix.components

import mozilla.components.concept.base.crash.Breadcrumb
import mozilla.components.lib.crash.Crash
import mozilla.components.lib.crash.service.CrashReporterService

/**
 * PyreVixen no-op crash service.
 * The CrashReporter requires at least one service to be defined, but we don't
 * want to send crashes to Mozilla (Sentry/Socorro). This service does nothing.
 * Actual crash reporting is handled by PyreVixenCrashReporter (saves to Downloads).
 */
class PyreVixenNoOpCrashService : CrashReporterService {
    override val id: String = "pyrevixen-noop"
    override val name: String = "PyreVixen (no-op)"

    override fun createCrashReportUrl(identifier: String): String? = null

    override fun report(crash: Crash.UncaughtExceptionCrash): String? = null
    override fun report(crash: Crash.NativeCodeCrash): String? = null
    override fun report(throwable: Throwable, breadcrumbs: ArrayList<Breadcrumb>): String? = null
}
'''

def main():
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    components_dir = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components"
    
    # 1. Create the no-op service file
    service_file = components_dir / "PyreVixenNoOpCrashService.kt"
    if not service_file.exists():
        service_file.write_text(NOOP_SERVICE_KT, encoding="utf-8")
        print("    created PyreVixenNoOpCrashService.kt")
    else:
        print("    PyreVixenNoOpCrashService.kt already exists, skipping")

    # 2. Add it to the services list in Analytics.kt
    analytics_file = components_dir / "Analytics.kt"
    content = analytics_file.read_text(encoding="utf-8")

    if "PyreVixenNoOpCrashService()" in content:
        print("    Analytics.kt already uses no-op service, skipping")
        return

    # Find where services list is created and add our service
    # After 020, the list is empty: "val services = mutableListOf<CrashReporterService>()"
    # We add our service right after the list creation
    old = "val services = mutableListOf<CrashReporterService>()"
    new = """val services = mutableListOf<CrashReporterService>()
        // PYREVIXEN: No-op service - CrashReporter requires at least one service.
        // We don't send crashes to Mozilla; PyreVixenCrashReporter handles local reports.
        services.add(PyreVixenNoOpCrashService())"""

    if old not in content:
        print("    WARNING: services list pattern not found", file=sys.stderr)
        return

    content = content.replace(old, new, 1)
    analytics_file.write_text(content, encoding="utf-8")
    print("    added PyreVixenNoOpCrashService to Analytics.kt services list")

if __name__ == "__main__":
    main()
