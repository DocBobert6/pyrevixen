#!/usr/bin/env bash
#
# release.sh — sign built APKs and assemble the release bundle.
#
# Takes the per-ABI (unsigned) APKs produced by scripts/build.sh, zipaligns
# and signs each with apksigner, writes SHA-256 checksums, and renders the
# release notes from templates/release-notes.md. Everything lands in
# <repo>/release/.
#
# SIGNING CREDENTIALS COME ONLY FROM THE ENVIRONMENT. They are never
# committed, never echoed, never written to disk by this script, and never
# passed on a command line where `ps` could see them (apksigner reads them
# via the env: scheme):
#   PYREVIXEN_KEYSTORE            path to the release .jks/.keystore file
#   PYREVIXEN_KEYSTORE_PASSWORD   keystore password
#   PYREVIXEN_KEY_ALIAS           key alias
#   PYREVIXEN_KEY_PASSWORD        key password
# In CI these are GitHub Actions *secrets* (see .github/workflows/build.yml).
# The script FAILS LOUDLY if any of them is missing.
#
# Environment:
#   APKS_DIR   dir with unsigned per-ABI APKs (default: <repo>/dist)
#   OUT_DIR    release bundle dir (default: <repo>/release)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

die() { echo "ERROR: $*" >&2; exit 1; }

# --- credentials: env only, all required, never echoed --------------------------
require_env() {
    local var="$1" why="$2"
    if [[ -z "${!var:-}" ]]; then
        echo "ERROR: missing required signing credential: ${var}" >&2
        echo "  ${why}" >&2
        echo "  (value not shown here and never printed by this script)" >&2
        exit 1
    fi
}
require_env "PYREVIXEN_KEYSTORE" \
    "Path to the release keystore file. In CI: secrets.ANDROID_KEYSTORE_BASE64 decoded to a file."
require_env "PYREVIXEN_KEYSTORE_PASSWORD" \
    "Keystore password. In CI: secrets.ANDROID_KEYSTORE_PASSWORD."
require_env "PYREVIXEN_KEY_ALIAS" \
    "Key alias. In CI: secrets.ANDROID_KEY_ALIAS."
require_env "PYREVIXEN_KEY_PASSWORD" \
    "Key password. In CI: secrets.ANDROID_KEY_PASSWORD."
[[ -f "${PYREVIXEN_KEYSTORE}" ]] || die "keystore file not found at PYREVIXEN_KEYSTORE."

VERSION="$(tr -d '[:space:]' < "${REPO_ROOT}/VERSION")"
[[ -n "${VERSION}" ]] || die "VERSION file is empty."
# PyreVixen tracks the upstream version; override only for a rebuild suffix.
PYREVIXEN_VERSION="${PYREVIXEN_VERSION:-${VERSION}}"
FIREFOX_BASE="${VERSION}"
RELEASE_DATE="$(date -u +%Y-%m-%d)"

APKS_DIR="${APKS_DIR:-${REPO_ROOT}/dist}"
OUT_DIR="${OUT_DIR:-${REPO_ROOT}/release}"
TEMPLATE="${REPO_ROOT}/templates/release-notes.md"

[[ -d "${APKS_DIR}" ]] || die "APKS_DIR not found: ${APKS_DIR}. Run scripts/build.sh first."
[[ -f "${TEMPLATE}" ]] || die "release notes template missing: ${TEMPLATE}."
mkdir -p "${OUT_DIR}"

# --- build-tools preflight -------------------------------------------------------
ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
[[ -n "${ANDROID_HOME}" && -d "${ANDROID_HOME}" ]] \
    || die "Android SDK not found. Set ANDROID_HOME (or ANDROID_SDK_ROOT)."
LATEST_BT="$(ls -d "${ANDROID_HOME}"/build-tools/*/ 2>/dev/null | LC_ALL=C sort -V | tail -n 1 || true)"
[[ -n "${LATEST_BT}" ]] || die "no build-tools found under ${ANDROID_HOME}/build-tools."
APKSIGNER="${LATEST_BT}/apksigner"
ZIPALIGN="${LATEST_BT}/zipalign"
[[ -x "${APKSIGNER}" ]] || die "apksigner not executable: ${APKSIGNER}"
[[ -x "${ZIPALIGN}" ]] || die "zipalign not executable: ${ZIPALIGN}"
command -v sha256sum >/dev/null 2>&1 || die "sha256sum is required but not installed."

# --- sign each APK ----------------------------------------------------------------
shopt -s nullglob
APKS=("${APKS_DIR}"/pyrevixen-*.apk)
shopt -u nullglob
((${#APKS[@]} > 0)) || die "no pyrevixen-*.apk files in ${APKS_DIR}. Run scripts/build.sh first."

echo "==> Signing ${#APKS[@]} APK(s) ..."
for apk in "${APKS[@]}"; do
    base="$(basename "${apk}" .apk)"
    aligned_tmp="$(mktemp --suffix=.apk)"
    signed="${OUT_DIR}/${base}-signed.apk"
    echo "---- ${base}.apk"
    "${ZIPALIGN}" -f 4 "${apk}" "${aligned_tmp}" \
        || die "zipalign failed for ${apk}."
    # Passwords travel via the env: scheme — never on the command line, never echoed.
    "${APKSIGNER}" sign \
        --ks "${PYREVIXEN_KEYSTORE}" \
        --ks-pass "env:PYREVIXEN_KEYSTORE_PASSWORD" \
        --ks-key-alias "${PYREVIXEN_KEY_ALIAS}" \
        --key-pass "env:PYREVIXEN_KEY_PASSWORD" \
        --out "${signed}" \
        "${aligned_tmp}" \
        || die "signing FAILED for ${apk}."
    rm -f "${aligned_tmp}"
    "${APKSIGNER}" verify "${signed}" >/dev/null \
        || die "signature verification FAILED for ${signed}."
    echo "    signed + verified: ${signed}"
done

# --- SHA-256 checksums --------------------------------------------------------------
echo "==> Writing SHA-256 checksums ..."
(cd "${OUT_DIR}" && sha256sum pyrevixen-*-signed.apk > SHA256SUMS) \
    || die "could not write SHA256SUMS."
[[ -s "${OUT_DIR}/SHA256SUMS" ]] || die "SHA256SUMS is empty; refusing to ship."
cat "${OUT_DIR}/SHA256SUMS"

# --- release notes -------------------------------------------------------------------
echo "==> Rendering release notes ..."
sed -e "s/{{VERSION}}/${PYREVIXEN_VERSION}/g" \
    -e "s/{{FIREFOX_BASE}}/${FIREFOX_BASE}/g" \
    -e "s/{{DATE}}/${RELEASE_DATE}/g" \
    -e "/{{CHECKSUMS}}/r ${OUT_DIR}/SHA256SUMS" \
    -e "/{{CHECKSUMS}}/d" \
    "${TEMPLATE}" > "${OUT_DIR}/RELEASE_NOTES.md"
if grep -Eq '{{[A-Z_]+}}' "${OUT_DIR}/RELEASE_NOTES.md"; then
    echo "ERROR: unrendered placeholders remain in RELEASE_NOTES.md:" >&2
    grep -Eo '{{[A-Z_]+}}' "${OUT_DIR}/RELEASE_NOTES.md" | sort -u >&2
    exit 1
fi

echo "==> Release bundle ready in ${OUT_DIR}/:"
ls -1 "${OUT_DIR}"
