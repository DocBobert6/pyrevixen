#!/usr/bin/env bash
#
# fetch-source.sh — fetch the pinned Firefox source and verify it.
#
# Reads the pinned upstream version from ../VERSION, then shallow-clones
# Mozilla's official firefox monorepo at the matching FIREFOX-ANDROID
# release tag. Fenix now lives in mozilla-central (the old standalone
# firefox-android repo was archived in June 2024), so there is no separate
# Fenix source tarball to download.
#
# Verification: the clone comes over TLS from github.com/mozilla-firefox
# (Mozilla's official GitHub org) and we assert the checkout is EXACTLY the
# expected release tag — `git describe --exact-match` refuses anything else.
# A tag mismatch (or a repo that someone retagged) fails the build loudly
# rather than building unknown source.
#
# Usage:
#   ./scripts/fetch-source.sh            # run from the repo root
#
# Environment overrides:
#   PYREVIXEN_VERSION_OVERRIDE   fetch this version instead of ../VERSION
#   PYREVIXEN_DOWNLOAD_DIR       where to clone (default: .source/)
#
# Layout produced:
#   .source/               clone scratch dir (git-ignored)
#   .source/SOURCE_DIR     file holding the extracted top-level source dir
#   The Fenix Gradle project root is then <SOURCE_DIR>/mobile/android/fenix.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# --- Knobs (top of file) ----------------------------------------------------
VERSION="$(tr -d '[:space:]' < "${REPO_ROOT}/VERSION")"
if [[ -n "${PYREVIXEN_VERSION_OVERRIDE:-}" ]]; then
    VERSION="${PYREVIXEN_VERSION_OVERRIDE}"
    echo "NOTE: PYREVIXEN_VERSION_OVERRIDE is set; fetching '${VERSION}' instead of the VERSION file."
fi
[[ -n "${VERSION}" ]] || { echo "ERROR: VERSION file is empty." >&2; exit 1; }

# 158.0 -> FIREFOX-ANDROID_158_0_RELEASE
TAG="FIREFOX-ANDROID_${VERSION//./_}_RELEASE"

# Mozilla's official monorepo (the firefox-android repo is archived;
# Fenix lives at mobile/android in mozilla-central).
UPSTREAM_URL="https://github.com/mozilla-firefox/firefox"

DOWNLOAD_DIR="${PYREVIXEN_DOWNLOAD_DIR:-${REPO_ROOT}/.source}"
CLONE_DIR="${DOWNLOAD_DIR}/firefox-${VERSION}"
# --- end knobs ---------------------------------------------------------------

die() { echo "ERROR: $*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || die "git is required but not installed."

mkdir -p "${DOWNLOAD_DIR}"

if [[ -d "${CLONE_DIR}/.git" ]]; then
    echo "==> Source clone already on disk at ${CLONE_DIR}; re-verifying tag ..."
else
    echo "==> Cloning ${UPSTREAM_URL} at tag ${TAG} (shallow) ..."
    # The mozilla-central clone is several GB; GitHub occasionally resets the
    # connection mid-transfer ("early EOF"). Retry a few times before giving up.
    attempt=1
    while [[ "${attempt}" -le 3 ]]; do
        echo "    clone attempt ${attempt}/3 ..."
        if git -c http.postBuffer=524288000 clone --depth 1 --branch "${TAG}" \
                "${UPSTREAM_URL}" "${CLONE_DIR}"; then
            break
        fi
        echo "    clone attempt ${attempt} failed; cleaning up and retrying in 15s ..."
        rm -rf "${CLONE_DIR}"
        attempt=$((attempt + 1))
        sleep 15
    done
    [[ -d "${CLONE_DIR}/.git" ]] \
        || die "clone failed for tag ${TAG} after 3 attempts. Check that VERSION is a released Firefox for Android version."
fi

# Verify: HEAD must be exactly the commit the expected tag points at.
# (Several Mozilla tags can point at the same commit — e.g. ..._RELEASE and
# ..._BUILD1 — so we compare SHAs instead of asking `git describe` to pick
# one tag name.)
EXPECTED_SHA="$(git -C "${CLONE_DIR}" rev-list -n 1 "${TAG}" 2>/dev/null || true)"
ACTUAL_SHA="$(git -C "${CLONE_DIR}" rev-parse HEAD 2>/dev/null || true)"
[[ -n "${EXPECTED_SHA}" && "${EXPECTED_SHA}" == "${ACTUAL_SHA}" ]] \
    || die "tag verification failed: tag '${TAG}' does not point at the checked-out commit. Refusing to build unknown source."
echo "==> Tag verified: ${TAG} (${ACTUAL_SHA:0:12})"

# Sanity: the Fenix Gradle project must be where the patches expect it.
[[ -x "${CLONE_DIR}/mobile/android/fenix/gradlew" ]] \
    || die "no gradlew at mobile/android/fenix in the cloned tree; upstream layout changed."

echo "${CLONE_DIR}" > "${DOWNLOAD_DIR}/SOURCE_DIR"
echo "==> Source ready at ${CLONE_DIR} (recorded in .source/SOURCE_DIR)"
