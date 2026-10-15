#!/usr/bin/env python3
"""
add-crash-reporter.py — PyreVixen: save crash reports to Downloads folder.

Creates a standalone PyreVixenCrashReporter.kt file and adds a single
initialization line to FenixApplication.onCreate(). This is safer than
injecting a large code block directly into FenixApplication.kt.

When the app crashes, saves to Downloads as PyreVixen-crash-YYYYMMDD-HHMMSS.txt

Idempotent: safe to re-run.
"""

import sys
from pathlib import Path

CRASH_REPORTER_KT = '''package org.mozilla.fenix

import android.content.ContentValues
import android.content.Context
import android.os.Build
import android.provider.MediaStore
import android.util.Log
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * PyreVixen crash reporter: saves crash logs to Downloads folder.
 * Install via PyreVixenCrashReporter.install(context) in Application.onCreate().
 */
object PyreVixenCrashReporter {
    fun install(context: Context) {
        val defaultHandler = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                val timestamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
                val filename = "PyreVixen-crash-$timestamp.txt"

                val report = buildString {
                    appendLine("PyreVixen Crash Report")
                    appendLine("======================")
                    appendLine("Time: ${Date()}")
                    @Suppress("DEPRECATION")
                    appendLine("Thread: ${thread.name} (id=${thread.id})")
                    appendLine("Device: ${Build.MANUFACTURER} ${Build.MODEL}")
                    appendLine("Android: ${Build.VERSION.RELEASE} (SDK ${Build.VERSION.SDK_INT})")
                    appendLine()
                    appendLine("Stack trace:")
                    appendLine(Log.getStackTraceString(throwable))
                }

                val values = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, filename)
                    put(MediaStore.MediaColumns.MIME_TYPE, "text/plain")
                    put(MediaStore.MediaColumns.RELATIVE_PATH, "Download/")
                }
                val uri = context.contentResolver.insert(
                    MediaStore.Downloads.EXTERNAL_CONTENT_URI,
                    values
                )
                uri?.let {
                    context.contentResolver.openOutputStream(it)?.use { out ->
                        out.write(report.toByteArray())
                    }
                }
            } catch (e: Exception) {
                Log.e("PyreVixen", "Failed to write crash report", e)
            } finally {
                defaultHandler?.uncaughtException(thread, throwable)
            }
        }
    }
}
'''

def main():
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    fenix_dir = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix"
    
    # 1. Create the standalone reporter file
    reporter_file = fenix_dir / "PyreVixenCrashReporter.kt"
    if not reporter_file.exists():
        reporter_file.write_text(CRASH_REPORTER_KT, encoding="utf-8")
        print("    created PyreVixenCrashReporter.kt")
    else:
        print("    PyreVixenCrashReporter.kt already exists, skipping")

    # 2. Add init call to FenixApplication.onCreate()
    app_file = fenix_dir / "FenixApplication.kt"
    content = app_file.read_text(encoding="utf-8")

    if "PyreVixenCrashReporter.install" in content:
        print("    FenixApplication already calls crash reporter, skipping")
        return

    old = "override fun onCreate() {"
    new = "override fun onCreate() {\n        PyreVixenCrashReporter.install(this) // PYREVIXEN: crash reports to Downloads"
    
    if old not in content:
        print("    WARNING: onCreate not found", file=sys.stderr)
        return

    content = content.replace(old, new, 1)
    app_file.write_text(content, encoding="utf-8")
    print("    added PyreVixenCrashReporter.install(this) to FenixApplication.onCreate()")

if __name__ == "__main__":
    main()
