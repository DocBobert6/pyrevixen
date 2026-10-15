#!/usr/bin/env python3
"""Re-add Glean SDK dependencies after 020 patch removes them.
Glean is kept so the code compiles, but GleanHelper.initializeGlean is no-op'd
so Glean never initializes and cannot collect/upload data."""
import sys
import os

source_dir = sys.argv[1]
build_gradle = os.path.join(
    source_dir,
    "mobile/android/fenix/app/build.gradle"
)

with open(build_gradle) as f:
    content = f.read()

# 1. Re-add the glean plugin and config block.
# The 020 patch replaced them with "// PYREVIXEN: Glean SDK removed..."
if '// PYREVIXEN: Glean SDK removed' in content:
    content = content.replace(
        '// PYREVIXEN: Glean SDK removed - no telemetry framework is shipped.',
        '''// Generate Kotlin code for the Fenix Glean metrics.
ext {
    // Enable expiration by major version.
    gleanExpireByVersion = Config.majorVersion(project)
    gleanNamespace = "mozilla.telemetry.glean"
    gleanPythonEnvDir = gradle.mozconfig.substs.GRADLE_GLEAN_PARSER_VENV
}
apply plugin: "org.mozilla.telemetry.glean-gradle-plugin"'''
    )
    print("Re-added Glean plugin", file=sys.stderr)

# 2. Re-add service-glean dependency.
if "project(':components:service-glean')" not in content:
    # Insert after service-firefox-relay.
    content = content.replace(
        '    implementation project(":components:service-firefox-relay")',
        '    implementation project(":components:service-firefox-relay")\n    implementation project(\':components:service-glean\')'
    )
    print("Re-added service-glean", file=sys.stderr)

# 3. Re-add libs.mozilla.glean.
if "libs.mozilla.glean" not in content or "implementation libs.mozilla.glean" not in content:
    # Insert before libs.play.review.
    content = content.replace(
        "    implementation libs.play.review",
        "    implementation libs.mozilla.glean\n    implementation libs.play.review"
    )
    print("Re-added libs.mozilla.glean", file=sys.stderr)

# 4. Re-add glean forUnitTests.
if "libs.mozilla.glean.forUnitTests" not in content:
    content = content.replace(
        "    testImplementation libs.robolectric",
        "    testImplementation libs.mozilla.glean.forUnitTests\n    testImplementation libs.robolectric"
    )
    print("Re-added glean forUnitTests", file=sys.stderr)

with open(build_gradle, "w") as f:
    f.write(content)

print("Done", file=sys.stderr)
