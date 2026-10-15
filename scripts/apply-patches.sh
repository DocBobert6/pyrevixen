#!/usr/bin/env bash
#
# apply-patches.sh — apply patches/ in numbered order onto the fetched source.
#
# Run from the repo root. Applies every patches/[0-9]*.patch with `patch -p1`
# in lexicographic order (010 -> 080). FAILS LOUDLY: the first patch that
# does not apply cleanly aborts the whole run with a non-zero exit and names
# the offending patch file.
#
# NOTE: applying is idempotent — patches already applied are skipped, so
# re-running against a fully-patched tree is safe. If a run FAILS halfway,
# though, the tree is half-patched: re-run fetch-source.sh first (it
# re-verifies the tag on a clean tree), then run this script again.
#
# Environment:
#   PYREVIXEN_SOURCE_DIR   path to the extracted source tree
#                         (default: read from .source/SOURCE_DIR, written by
#                         scripts/fetch-source.sh)
#   PATCH_DRY_RUN=1       pass --dry-run to patch(1): check only, modify
#                         nothing. Used by the weekly rebase check.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PATCH_DIR="${REPO_ROOT}/patches"

die() { echo "ERROR: $*" >&2; exit 1; }

# --- locate the source tree ---------------------------------------------------
SOURCE_DIR="${PYREVIXEN_SOURCE_DIR:-}"
if [[ -z "${SOURCE_DIR}" && -f "${REPO_ROOT}/.source/SOURCE_DIR" ]]; then
    SOURCE_DIR="$(tr -d '[:space:]' < "${REPO_ROOT}/.source/SOURCE_DIR")"
fi
[[ -n "${SOURCE_DIR}" ]] || die "no source tree found. Run scripts/fetch-source.sh first, or set PYREVIXEN_SOURCE_DIR."
[[ -d "${SOURCE_DIR}" ]] || die "source dir does not exist: ${SOURCE_DIR}"

[[ -d "${PATCH_DIR}" ]] || die "patches/ directory missing at ${PATCH_DIR}."

shopt -s nullglob
UNSORTED=("${PATCH_DIR}"/[0-9]*.patch)
shopt -u nullglob
((${#UNSORTED[@]} > 0)) || die "no numbered patches in ${PATCH_DIR} — refusing to continue with an unpatched tree."
mapfile -t PATCHES < <(printf '%s\n' "${UNSORTED[@]}" | LC_ALL=C sort)

PATCH_ARGS=()
if [[ "${PATCH_DRY_RUN:-0}" == "1" ]]; then
    PATCH_ARGS+=(--dry-run)
    echo "==> DRY RUN: checking only, no files will be modified."
fi

echo "==> Applying ${#PATCHES[@]} patch(es) to ${SOURCE_DIR}, in order ..."
for p in "${PATCHES[@]}"; do
    name="$(basename "${p}")"
    echo "---- ${name}"
    # Idempotency: if the patch is already applied (reverse dry-run succeeds),
    # skip it. This lets the script be re-run safely and lets build.sh run
    # after the workflow's own apply-patches step without double-applying.
    if patch -p1 --directory="${SOURCE_DIR}" --dry-run -R -s < "${p}" >/dev/null 2>&1; then
        echo "    already applied, skipping: ${name}"
        continue
    fi
    if patch -p1 --directory="${SOURCE_DIR}" "${PATCH_ARGS[@]}" < "${p}"; then
        echo "    OK: ${name}"
    else
        echo "ERROR: patch FAILED: ${name}" >&2
        echo "  Fix ${p} (or the source tree) and re-run from a fresh tree:" >&2
        echo "    ./scripts/fetch-source.sh && ./scripts/apply-patches.sh" >&2
        exit 1
    fi
done

echo "==> All ${#PATCHES[@]} patch(es) applied cleanly."

# --- Glean call-site scrub -----------------------------------------------------
# The 020 patch removes the Glean SDK and glean-gradle-plugin, which stops
# generation of org.mozilla.fenix.GleanMetrics. This script deletes all
# Glean/Adjust/InstallReferrer call sites so the tree compiles. Idempotent.
# Scrub scripts disabled: Glean SDK is now kept (never initialized) so call sites compile.
# echo "==> Scrubbing Glean/Adjust/InstallReferrer call sites ..."
# python3 "${REPO_ROOT}/scripts/scrub-glean.py" "${SOURCE_DIR}"
# echo "==> Applying hard-case fixes ..."
# python3 "${REPO_ROOT}/scripts/fix-hard-cases.py" "${SOURCE_DIR}"
# echo "==> Deleting telemetry functions ..."
# python3 "${REPO_ROOT}/scripts/delete-telemetry-funcs.py" "${SOURCE_DIR}/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/FenixApplication.kt"

echo "==> Re-adding Glean SDK (kept inert, never initialized) ..."
python3 "${REPO_ROOT}/scripts/readd-glean.py" "${SOURCE_DIR}"
echo "==> Deleting Adjust/InstallReferrer wrappers ..."
python3 "${REPO_ROOT}/scripts/delete-adjust-referrer.py" "${SOURCE_DIR}"
echo "==> Fixing dangling references ..."
python3 "${REPO_ROOT}/scripts/fix-dangling-refs.py" "${SOURCE_DIR}"
echo "==> Applying Glean crash fix (minimal init, upload=false) ..."
python3 "${REPO_ROOT}/scripts/fix-glean-crash.py" "${SOURCE_DIR}"
echo "==> Installing PyreVixen crash reporter (saves to Downloads) ..."
python3 "${REPO_ROOT}/scripts/add-crash-reporter.py" "${SOURCE_DIR}"
echo "==> Adding no-op crash service (CrashReporter requires at least one) ..."
python3 "${REPO_ROOT}/scripts/fix-crash-reporter-services.py" "${SOURCE_DIR}"
echo "==> Disabling AI Translations ..."
python3 "${REPO_ROOT}/scripts/fix-ai-translations.py" "${SOURCE_DIR}"
echo "==> Applying Robert's feedback fixes ..."
python3 "${REPO_ROOT}/scripts/fix-robert-feedback-62.py" "${SOURCE_DIR}"
echo "==> Applying homepage v2 (robust) + rollouts fix ..."
python3 "${REPO_ROOT}/scripts/fix-homepage-v2.py" "${SOURCE_DIR}"
echo "==> Bundling video toolkit WebExtension ..."
python3 "${REPO_ROOT}/scripts/bundle-video-toolkit.py" "${SOURCE_DIR}"
echo "==> Fixing homepage routing (direct pref access) ..."
python3 "${REPO_ROOT}/scripts/fix-homepage-routing.py" "${SOURCE_DIR}"
echo "==> Removing AI Controls and Remote Improvements from settings ..."
python3 "${REPO_ROOT}/scripts/fix-settings-cleanup.py" "${SOURCE_DIR}"
echo "==> Fixing home screen branding (PyreVixen wordmark) ..."
python3 "${REPO_ROOT}/scripts/fix-home-branding.py" "${SOURCE_DIR}"
echo "==> Applying extra privacy defaults (GPC on) ..."
python3 "${REPO_ROOT}/scripts/fix-privacy-defaults-extra.py" "${SOURCE_DIR}"
