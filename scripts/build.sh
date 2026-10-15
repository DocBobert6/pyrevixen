#!/usr/bin/env bash
#
# build.sh — local/CI build entry point for PyreVixen.
#
# Stages:
#   1. scripts/fetch-source.sh   shallow-clone the pinned source at its
#                                release tag (verified with git describe)
#   2. scripts/apply-patches.sh  apply patches/ in order (any failure aborts)
#   3. scripts/apply-branding-assets.sh
#                                install binary branding assets (launcher icon
#                                PNGs) that GNU patch can't carry
#   4. scripts/mach-configure.sh ./mach configure (+ partial export) so the
#                                Gradle scripts can read config.status.json
#                                (required since Fenix moved to mozilla-central)
#   5. Gradle                    one :app:assemble<Release|Debug>; Fenix's ABI
#                                splits produce the per-ABI APKs automatically.
#
# Unsigned/debug builds need NO secrets. Release signing is a separate step
# (scripts/release.sh), so the signing key never touches the build.
#
# The finished APKs land in <repo>/dist/ as pyrevixen-<version>-<abi>.apk.
#
# Environment:
#   BUILD_TYPE=debug|release   default: debug (unsigned). 'release' also
#                              produces UNSIGNED apks here; sign them later
#                              with scripts/release.sh.
#   PYREVIXEN_SOURCE_DIR        override the source tree location.
#   SKIP_FETCH=1               skip stage 1 (source already fetched).
#   SKIP_PATCHES=1             skip stage 2 (patches already applied).
#   SKIP_BRANDING_ASSETS=1     skip stage 3 (branding assets already installed).
#   SKIP_MACH_CONFIGURE=1      skip stage 4 (tree already configured).
#   PYREVIXEN_GRADLE_ARGS       extra args passed to the Gradle invocation.
#   PYREVIXEN_GRADLE_TASK       Gradle task override
#                              (default: :app:assembleRelease / :app:assembleDebug).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

die() { echo "ERROR: $*" >&2; exit 1; }

BUILD_TYPE="${BUILD_TYPE:-debug}"
[[ "${BUILD_TYPE}" == "debug" || "${BUILD_TYPE}" == "release" ]] \
    || die "BUILD_TYPE must be 'debug' or 'release' (got '${BUILD_TYPE}')."

VERSION="$(tr -d '[:space:]' < "${REPO_ROOT}/VERSION")"
[[ -n "${VERSION}" ]] || die "VERSION file is empty."

# --- Stage 1: fetch + verify source -------------------------------------------
if [[ "${SKIP_FETCH:-0}" != "1" ]]; then
    echo "==================== STAGE 1/5: fetch source ===================="
    "${REPO_ROOT}/scripts/fetch-source.sh"
else
    echo "---- SKIP_FETCH=1: skipping source fetch."
fi

# --- Stage 2: apply patches ----------------------------------------------------
if [[ "${SKIP_PATCHES:-0}" != "1" ]]; then
    echo "==================== STAGE 2/5: apply patches ===================="
    "${REPO_ROOT}/scripts/apply-patches.sh"
else
    echo "---- SKIP_PATCHES=1: skipping patch application."
fi

# --- Stage 3: branding assets ----------------------------------------------------
# Binary artwork (launcher icon) that the text patches can't carry.
if [[ "${SKIP_BRANDING_ASSETS:-0}" != "1" ]]; then
    echo "==================== STAGE 3/5: branding assets ===================="
    "${REPO_ROOT}/scripts/apply-branding-assets.sh"
else
    echo "---- SKIP_BRANDING_ASSETS=1: skipping branding assets."
fi

# --- Stage 4: mach configure ---------------------------------------------------
# Since Fenix moved into mozilla-central, Gradle evaluation requires
# config.status.json from a configured objdir (see scripts/mach-configure.sh).
# Gradle's mozconfig.gradle locates it by running `./mach environment`,
# which honors MOZCONFIG and MOZ_OBJDIR from the environment — export both
# here so configure and Gradle agree on the locations.
if [[ "${SKIP_MACH_CONFIGURE:-0}" != "1" ]]; then
    echo "==================== STAGE 4/5: mach configure ===================="
    _sdir="${PYREVIXEN_SOURCE_DIR:-}"
    if [[ -z "${_sdir}" && -f "${REPO_ROOT}/.source/SOURCE_DIR" ]]; then
        _sdir="$(tr -d '[:space:]' < "${REPO_ROOT}/.source/SOURCE_DIR")"
    fi
    export MOZCONFIG="${MOZCONFIG_PATH:-${REPO_ROOT}/.source/pyrevixen.mozconfig}"
    export MOZ_OBJDIR="${MOZ_OBJDIR:-${_sdir}/obj-pyrevixen}"
    # Pin the build ID to the official Firefox 158.0 release build ID so the
    # GeckoView dependency version (158.0.<buildid>) matches the AAR published
    # on maven.mozilla.org. Build ID 20261007201254 = 2026-10-07 20:12:54 UTC.
    export MOZ_BUILD_DATE="20261007201254"
    "${REPO_ROOT}/scripts/mach-configure.sh"
else
    echo "---- SKIP_MACH_CONFIGURE=1: skipping mach configure."
fi

# --- locate the source tree (same convention as apply-patches.sh) --------------
SOURCE_DIR="${PYREVIXEN_SOURCE_DIR:-}"
if [[ -z "${SOURCE_DIR}" && -f "${REPO_ROOT}/.source/SOURCE_DIR" ]]; then
    SOURCE_DIR="$(tr -d '[:space:]' < "${REPO_ROOT}/.source/SOURCE_DIR")"
fi
[[ -n "${SOURCE_DIR}" && -d "${SOURCE_DIR}" ]] || die "no source tree. Run scripts/fetch-source.sh first."

# --- Stage 4: Gradle ------------------------------------------------------------
echo "==================== STAGE 5/5: Gradle build (${BUILD_TYPE}) ===================="

# Toolchain preflight — fail loudly with actionable messages, not Gradle soup.
command -v java >/dev/null 2>&1 || die "java not found. Install a JDK (the pinned tree needs the version in its README; recent trees use JDK 17)."
ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
[[ -n "${ANDROID_HOME}" && -d "${ANDROID_HOME}" ]] \
    || die "Android SDK not found. Set ANDROID_HOME (or ANDROID_SDK_ROOT) to your SDK dir."
[[ -x "${SOURCE_DIR}/gradlew" ]] || die "gradlew not found in ${SOURCE_DIR}; the source tree looks wrong."

# --- Per-ABI APKs ---------------------------------------------------------------
# Fenix uses ABI *splits* (not product flavors): one Gradle invocation builds
# every ABI, and the split APKs land under app/build/outputs/apk/<type>/ as
# app-<abi>-release.apk. *** VERIFY the task name against the pinned tree
# before trusting it: ./gradlew :app:tasks --all | grep -i '^assembleRelease' ***
BT_CAP="$(tr '[:lower:]' '[:upper:]' <<< "${BUILD_TYPE:0:1}")${BUILD_TYPE:1}"  # debug->Debug
DEFAULT_TASK=":app:assemble${BT_CAP}"
TASK="${PYREVIXEN_GRADLE_TASK:-${DEFAULT_TASK}}"

GRADLE_ROOT="${SOURCE_DIR}/mobile/android/fenix"
[[ -x "${GRADLE_ROOT}/gradlew" ]] \
    || die "gradlew not found at ${GRADLE_ROOT}; upstream layout changed."
APK_OUT_DIR="${GRADLE_ROOT}/app/build/outputs/apk/${BUILD_TYPE}"

DIST_DIR="${REPO_ROOT}/dist"
mkdir -p "${DIST_DIR}"

echo "==> Building (${BUILD_TYPE}, Gradle task: ${TASK}) ..."
pushd "${GRADLE_ROOT}" >/dev/null
# shellcheck disable=SC2086
./gradlew "${TASK}" ${PYREVIXEN_GRADLE_ARGS:-} \
    || die "Gradle build FAILED (task ${TASK}). See output above."
popd >/dev/null

# Collect the per-ABI split APKs -> pyrevixen-<version>-<abi>.apk
# Firefox redirects Gradle outputs to the objdir (obj-*/gradle/...), not the source tree.
# Search broadly for the APKs by filename only.
APK_SEARCH_ROOT="$(dirname "${SOURCE_DIR}")"
mapfile -t SPLIT_APKS < <(find "${APK_SEARCH_ROOT}" -name 'app-*-'"${BUILD_TYPE}"'.apk' 2>/dev/null | LC_ALL=C sort || true)
((${#SPLIT_APKS[@]} > 0)) || die "Gradle reported success but no APKs found under ${APK_SEARCH_ROOT}."
for apk in "${SPLIT_APKS[@]}"; do
    base="$(basename "${apk}")"                       # app-arm64-v8a-release.apk
    abi="$(sed -n 's/^app-\(.*\)-'"${BUILD_TYPE}"'\.apk$/\1/p' <<< "${base}")"
    [[ -n "${abi}" ]] || die "cannot parse ABI from APK name '${base}'."
    dest="${DIST_DIR}/pyrevixen-${VERSION}-${abi}.apk"
    cp "${apk}" "${dest}"
    echo "    -> ${dest}"
done

echo "==> Build complete. APKs in ${DIST_DIR}/:"
ls -1 "${DIST_DIR}"/pyrevixen-*.apk
if [[ "${BUILD_TYPE}" == "release" ]]; then
    echo "    NOTE: these are UNSIGNED release APKs. Sign them with scripts/release.sh."
fi
