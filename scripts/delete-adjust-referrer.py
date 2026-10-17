#!/usr/bin/env python3
"""Delete Adjust SDK and InstallReferrer wrapper files.
The 020 patch removes the Adjust and InstallReferrer dependencies;
these files are the wrappers that depend on those SDKs."""
import sys
import os

source_dir = sys.argv[1]
metrics_dir = os.path.join(
    source_dir,
    "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/components/metrics"
)

files_to_delete = [
    "AdjustMetricsService.kt",
    "AdjustSdkController.kt",
    "AdjustThirdPartySharingController.kt",
    "DefaultInstallReferrerClient.kt",
    "InstallReferrerClientWrapper.kt",
    "InstallReferrerHandlingService.kt",
    "InstallReferrerWorker.kt",
]

for fname in files_to_delete:
    path = os.path.join(metrics_dir, fname)
    if os.path.exists(path):
        os.remove(path)
        print(f"Deleted {fname}", file=sys.stderr)
    else:
        print(f"Not found: {fname}", file=sys.stderr)

print("Done", file=sys.stderr)
