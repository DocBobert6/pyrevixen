#!/usr/bin/env bash
#
# mach-configure.sh — run ./mach configure (+ partial export) so that the
# Gradle build can read config.status.json.
#
# Background: since Fenix moved into mozilla-central (mobile/android/fenix),
# its Gradle scripts (mobile/android/gradle/mozconfig.gradle) REQUIRE a
# configured objdir: they read <topobjdir>/config.status.json at evaluation
# time and fail with "Run ./mach configure first" without it.
#
# This mirrors what Mozilla's own automation does in
# taskcluster/scripts/builder/build-android.sh:
#   - a configure-only mozconfig (no native Gecko compilation; GeckoView
#     arrives as a Maven artifact, exactly like upstream Fenix builds),
#   - no API keyfiles (we don't have Mozilla's /builds/*.key files),
#   - ./mach configure, then ./mach build pre-export export so that
#     moz.build-generated code is in place for Gradle.
#
# Run from the repo root, after scripts/fetch-source.sh and
# scripts/apply-patches.sh. Idempotent: re-running configure on an already
# configured tree is safe.
#
# Environment:
#   PYREVIXEN_SOURCE_DIR   path to the source tree (default: .source/SOURCE_DIR)
#   MOZ_OBJDIR             objdir location (default: <source>/obj-pyrevixen)
#   MOZCONFIG_PATH         where to write the generated mozconfig
#                          (default: <repo>/.source/pyrevixen.mozconfig)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

die() { echo "ERROR: $*" >&2; exit 1; }

# --- locate the source tree (same convention as the other scripts) ------------
SOURCE_DIR="${PYREVIXEN_SOURCE_DIR:-}"
if [[ -z "${SOURCE_DIR}" && -f "${REPO_ROOT}/.source/SOURCE_DIR" ]]; then
    SOURCE_DIR="$(tr -d '[:space:]' < "${REPO_ROOT}/.source/SOURCE_DIR")"
fi
[[ -n "${SOURCE_DIR}" && -d "${SOURCE_DIR}" ]] || die "no source tree. Run scripts/fetch-source.sh first."
[[ -x "${SOURCE_DIR}/mach" ]] || die "mach not found in ${SOURCE_DIR}; the source tree looks wrong."

MOZ_OBJDIR="${MOZ_OBJDIR:-${SOURCE_DIR}/obj-pyrevixen}"
# Honor an already-exported MOZCONFIG (build.sh sets it so Gradle agrees).
MOZCONFIG_PATH="${MOZCONFIG_PATH:-${MOZCONFIG:-${REPO_ROOT}/.source/pyrevixen.mozconfig}}"
mkdir -p "$(dirname "${MOZCONFIG_PATH}")"

# --- resolve the Android SDK ----------------------------------------------------
# mach's Android configure requires --with-android-sdk (it does not read
# ANDROID_HOME). The CI workflow sets ANDROID_HOME to the runner's SDK.
if [[ -z "${ANDROID_SDK_ROOT:-}" && -n "${ANDROID_HOME:-}" ]]; then
    ANDROID_SDK_ROOT="${ANDROID_HOME}"
fi
[[ -n "${ANDROID_SDK_ROOT:-}" && -d "${ANDROID_SDK_ROOT}" ]] \
    || die "Android SDK not found: set ANDROID_SDK_ROOT (or ANDROID_HOME)."

# --- write the configure-only mozconfig ---------------------------------------
# NOTE: deliberately NOT sourcing mobile/android/config/mozconfigs/common:
# it hardcodes Mozilla automation paths ($MOZ_FETCHES_DIR, /builds/*.key)
# that don't exist outside Taskcluster. The defaults from
# mobile/android/gradle.configure give us the public Maven repos
# (maven.mozilla.org, maven.google.com, ...), which is where the
# GeckoView Release AAR comes from.
cat > "${MOZCONFIG_PATH}" <<EOF
# PyreVixen CI mozconfig — configure-only.
# No native Gecko compilation (GeckoView arrives via Maven, like upstream
# Fenix); no Mozilla API keyfiles (not available outside Mozilla automation).

ac_add_options --enable-project=mobile/android
ac_add_options --target=aarch64-linux-android
ac_add_options --with-android-sdk="${ANDROID_SDK_ROOT}"

# Disables the compile environment (CC/CXX/etc.); configure still produces
# a full config.status.json for Gradle to read.
. "\$topsrcdir/build/mozconfig.no-compile"

ac_add_options --without-mozilla-api-keyfile
ac_add_options --without-google-safebrowsing-api-keyfile

# Skip the host codegen tools (uniffi-bindgen, nimbus-fml): they generate
# Gecko-internal bindings during a native build, which we don't do
# (GeckoView arrives via Maven). The moz.configure template explicitly
# supports --without-{prog} for unusual jobs like this one.
ac_add_options --without-embedded-uniffi-bindgen
ac_add_options --without-nimbus-fml
# Update channel "release": makes Gradle resolve the published release
# GeckoView (artifact "geckoview-omni[-<arch>]") instead of a "-default"
# channel artifact that is never published.
ac_add_options --with-update-channel=release
# Mark this an official-style build so Gradle drops the "-SNAPSHOT" suffix
# from the GeckoView version and requests the published release AAR.
export MOZILLA_OFFICIAL=1
EOF
echo "==> Wrote mozconfig to ${MOZCONFIG_PATH}"

# --- SDK version shims ----------------------------------------------------------
# Firefox 158's configure expects SDK components newer than the GitHub runner
# ships (cmdline-tools 23.0, build-tools 37.0.0, platforms android-37.2).
# We never compile Gecko natively — configure only checks these exist — so
# symlink the newest installed components into the expected locations.
shim_sdk_dir() {
    local expected="$1" pattern="$2" desc="$3"
    if [[ -e "${ANDROID_SDK_ROOT}/${expected}" ]]; then return 0; fi
    local newest
    newest="$(ls -d "${ANDROID_SDK_ROOT}"/${pattern} 2>/dev/null | LC_ALL=C sort -V | tail -1)"
    if [[ -n "${newest}" ]]; then
        mkdir -p "$(dirname "${ANDROID_SDK_ROOT}/${expected}")"
        ln -s "${newest}" "${ANDROID_SDK_ROOT}/${expected}"
        echo "==> SDK shim: ${expected} -> $(basename "${newest}") (${desc})"
    else
        echo "WARNING: no ${desc} found under ${ANDROID_SDK_ROOT}; configure may fail." >&2
    fi
}
shim_sdk_dir "cmdline-tools/23.0" "cmdline-tools/*" "cmdline-tools"
shim_sdk_dir "build-tools/37.0.0" "build-tools/*" "build-tools"
shim_sdk_dir "platforms/android-37.2" "platforms/android-*" "android platform"

# The emulator binary is checked but never used by our build; stub it if the
# emulator package isn't installed.
if [[ ! -x "${ANDROID_SDK_ROOT}/emulator/emulator" ]]; then
    mkdir -p "${ANDROID_SDK_ROOT}/emulator"
    printf '#!/bin/sh\nexit 0\n' > "${ANDROID_SDK_ROOT}/emulator/emulator"
    chmod +x "${ANDROID_SDK_ROOT}/emulator/emulator"
    echo "==> Created emulator stub (not used by the build)"
fi

# --- Bundletool stub ------------------------------------------------------------
# mach's Android configure demands a bundletool.jar (used only when building
# .aab bundles, which we don't). Point it at a stub so configure doesn't try
# to bootstrap-download one.
BUNDLETOOL_STUB="${HOME}/.mozbuild/bundletool.jar"
if [[ ! -f "${BUNDLETOOL_STUB}" ]]; then
    mkdir -p "$(dirname "${BUNDLETOOL_STUB}")"
    : > "${BUNDLETOOL_STUB}"
    echo "==> Created bundletool stub at ${BUNDLETOOL_STUB}"
fi
export ANDROID_BUNDLETOOL_PATH="${BUNDLETOOL_STUB}"

# --- mach's JDK -----------------------------------------------------------------
# ./mach configure insists on a JDK at ~/.mozbuild/jdk/jdk-<ver>/bin and
# suggests ./mach bootstrap to download one. The CI runner already has a
# JDK 17 (JAVA_HOME); symlink it into the expected layout instead of
# downloading ~200MB.
MOZBUILD_JDK_DIR="${HOME}/.mozbuild/jdk"
if [[ ! -d "${MOZBUILD_JDK_DIR}/jdk-17.0.20.1+1/bin" ]]; then
    if [[ -n "${JAVA_HOME:-}" && -d "${JAVA_HOME}/bin" ]]; then
        mkdir -p "${MOZBUILD_JDK_DIR}"
        ln -sfn "${JAVA_HOME}" "${MOZBUILD_JDK_DIR}/jdk-17.0.20.1+1"
        echo "==> Symlinked JAVA_HOME into ${MOZBUILD_JDK_DIR}/jdk-17.0.20.1+1"
    else
        echo "WARNING: no JAVA_HOME JDK found; ./mach configure may try to download one." >&2
    fi
fi

# --- configure -----------------------------------------------------------------
export MOZCONFIG="${MOZCONFIG_PATH}"
export MOZ_OBJDIR="${MOZ_OBJDIR}"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT}"

echo "==> Running ./mach configure (objdir: ${MOZ_OBJDIR}) ..."
pushd "${SOURCE_DIR}" >/dev/null
./mach configure || die "./mach configure failed."
echo "==> Running ./mach build pre-export export (generated code for Gradle) ..."
# Best-effort: this generates Gecko-internal code (e.g. GeckoView JNI
# bindings) that the app build usually doesn't need — we get GeckoView from
# Maven. If it fails, warn and let the Gradle build be the judge.
if ! ./mach build pre-export export; then
    echo "WARNING: ./mach build pre-export export failed; continuing anyway." >&2
fi
popd >/dev/null

[[ -f "${MOZ_OBJDIR}/config.status.json" ]] \
    || die "config.status.json missing after configure at ${MOZ_OBJDIR}."
echo "==> mach configure complete: ${MOZ_OBJDIR}/config.status.json"
