#!/usr/bin/env python3
"""Fix dangling references after deleting Adjust/InstallReferrer files."""
import sys
import os
import re

source_dir = sys.argv[1]
fenix_java = os.path.join(
    source_dir,
    "mobile/android/fenix/app/src/main/java/org/mozilla/fenix"
)

def fix_file(rel_path, replacements):
    path = os.path.join(fenix_java, rel_path)
    if not os.path.exists(path):
        print(f"Not found: {rel_path}", file=sys.stderr)
        return
    with open(path) as f:
        content = f.read()
    orig = content
    for old, new in replacements:
        content = content.replace(old, new)
    if content != orig:
        with open(path, "w") as f:
            f.write(content)
        print(f"Fixed {rel_path}", file=sys.stderr)

# HomeActivity.kt: remove InstallReferrerHandlingService usage.
# Find the line and comment it out or remove.
path = os.path.join(fenix_java, "HomeActivity.kt")
if os.path.exists(path):
    with open(path) as f:
        lines = f.readlines()
    # Remove lines referencing InstallReferrerHandlingService.
    new_lines = [l for l in lines if "InstallReferrerHandlingService" not in l]
    if len(new_lines) != len(lines):
        with open(path, "w") as f:
            f.writelines(new_lines)
        print(f"Fixed HomeActivity.kt (removed {len(lines)-len(new_lines)} lines)", file=sys.stderr)

# InstallReferrerMetricsService.kt: remove InstallReferrerWorker usage.
path = os.path.join(fenix_java, "components/metrics/InstallReferrerMetricsService.kt")
if os.path.exists(path):
    with open(path) as f:
        lines = f.readlines()
    new_lines = [l for l in lines if "InstallReferrerWorker" not in l]
    if len(new_lines) != len(lines):
        with open(path, "w") as f:
            f.writelines(new_lines)
        print(f"Fixed InstallReferrerMetricsService.kt", file=sys.stderr)
    else:
        # If the reference is not on its own line, we need a different approach.
        # For now, delete the file if it's broken.
        with open(path) as f:
            content = f.read()
        if "InstallReferrerWorker" in content:
            os.remove(path)
            print(f"Deleted InstallReferrerMetricsService.kt (broken)", file=sys.stderr)

# DistributionTools.kt
path = os.path.join(fenix_java, "debugsettings/distributions/DistributionTools.kt")
if os.path.exists(path):
    with open(path) as f:
        lines = f.readlines()
    new_lines = [l for l in lines if "InstallReferrerHandlingService" not in l]
    if len(new_lines) != len(lines):
        with open(path, "w") as f:
            f.writelines(new_lines)
        print(f"Fixed DistributionTools.kt", file=sys.stderr)

# OnboardingFragment.kt
path = os.path.join(fenix_java, "onboarding/OnboardingFragment.kt")
if os.path.exists(path):
    with open(path) as f:
        lines = f.readlines()
    new_lines = [l for l in lines if "InstallReferrerHandlingService" not in l]
    if len(new_lines) != len(lines):
        with open(path, "w") as f:
            f.writelines(new_lines)
        print(f"Fixed OnboardingFragment.kt", file=sys.stderr)

# UTMParams: Create stub unconditionally (the grep check was unreliable).
print("Creating UTMParams stub", file=sys.stderr)
stub_path = os.path.join(fenix_java, "components/metrics/UTMParams.kt")
with open(stub_path, "w") as f:
    f.write("""package org.mozilla.fenix.components.metrics

// PyreVixen stub: UTM attribution disabled.
data class UTMParams(
    val campaign: String? = null,
    val content: String? = null,
    val medium: String? = null,
    val source: String? = null,
    val term: String? = null,
)

fun parseUTMParameters(params: Map<String, String>): UTMParams = UTMParams()

const val UTM_CONTENT = "utm_content"
const val UTM_CAMPAIGN = "utm_campaign"
const val UTM_MEDIUM = "utm_medium"
const val UTM_SOURCE = "utm_source"
const val UTM_TERM = "utm_term"
""")
print("Created UTMParams stub", file=sys.stderr)

# Delete files that are broken beyond simple repair.
# NOTE: RtamoAttributionHandler is NOT deleted — OnboardingFragment needs it.
# Instead, we stub it below.
for rel_path in [
    "components/metrics/InstallReferrerMetricsService.kt",
    "components/metrics/ReferralAttribution.kt",
]:
    path = os.path.join(fenix_java, rel_path)
    if os.path.exists(path):
        os.remove(path)
        print(f"Deleted {rel_path}", file=sys.stderr)

# Stub RtamoAttributionHandler (OnboardingFragment references it).
# Use vararg constructor to accept any arguments.
stub_path = os.path.join(fenix_java, "components/metrics/RtamoAttributionHandler.kt")
with open(stub_path, "w") as f:
    f.write("""package org.mozilla.fenix.components.metrics

// PyreVixen stub: RTAMO attribution disabled.
class RtamoAttributionHandler(vararg args: Any?) {
    fun handleAttribution() {
        // No-op.
    }
}
""")
print("Created RtamoAttributionHandler stub", file=sys.stderr)

# CustomAttributeProvider.kt: remove UTM-related code (stub import wasn't working).
path = os.path.join(fenix_java, "messaging/CustomAttributeProvider.kt")
if os.path.exists(path):
    with open(path) as f:
        lines = f.readlines()
    # Remove lines referencing UTMParams or UTM.
    new_lines = [l for l in lines if "UTMParams" not in l and "utm" not in l.lower() and "UTM_" not in l]
    if len(new_lines) != len(lines):
        with open(path, "w") as f:
            f.writelines(new_lines)
        print(f"Fixed CustomAttributeProvider.kt (removed {len(lines)-len(new_lines)} lines)", file=sys.stderr)

# DistributionIdManager.kt: replace updateDistributionIdFromUtmParams with no-op.
# The method uses utmParams.campaign.contains() where campaign is String?.
# Since we're disabling attribution, make it a no-op.
path = os.path.join(fenix_java, "distributions/DistributionIdManager.kt")
if os.path.exists(path):
    with open(path) as f:
        content = f.read()
    orig = content
    # Replace the method body with a no-op.
    import re
    # Find the method and replace its body.
    pattern = r'fun updateDistributionIdFromUtmParams\(utmParams: UTMParams\) \{.*?\n    \}'
    replacement = 'fun updateDistributionIdFromUtmParams(utmParams: UTMParams) {\n        // PyreVixen: UTM attribution disabled.\n    }'
    new_content = re.sub(pattern, replacement, content, flags=re.S)
    if new_content != content:
        with open(path, "w") as f:
            f.write(new_content)
        print(f"Fixed DistributionIdManager.kt (no-op'd updateDistributionIdFromUtmParams)", file=sys.stderr)
    else:
        print(f"DistributionIdManager.kt pattern not matched", file=sys.stderr)

print("Done", file=sys.stderr)
