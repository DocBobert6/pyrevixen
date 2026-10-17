#!/usr/bin/env bash
#
# apply-branding-assets.sh — install the PyreVixen launcher icon artwork
# into the fetched source tree.
#
# The 010-branding.patch deliberately leaves @mipmap/ic_launcher pointing at
# the stock adaptive-icon XML and says to "replace the drawables in place".
# GNU patch can't carry binary files, so this script does that step:
#
#   branding/icon/ic_launcher_foreground.png  ->  res/drawable/ic_launcher_foreground.png
#       (replaces the vector ic_launcher_foreground.xml)
#   branding/icon/ic_launcher_monochrome.png  ->  res/drawable/ic_launcher_monochrome.png
#       (replaces the vector ic_launcher_monochrome.xml; themed-icon layer)
#   res/values/colors.xml: ic_launcher_background -> #FF000000
#       (the logo is designed on black; the adaptive-icon background must be
#       black for the disc to look seamless)
#
# The adaptive-icon XML (mipmap-anydpi/ic_launcher.xml) is unchanged: its
# @drawable/ic_launcher_foreground reference now resolves to the PNG.
#
# Run from the repo root, after scripts/apply-patches.sh. Idempotent:
# re-running just overwrites the same files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

die() { echo "ERROR: $*" >&2; exit 1; }

SOURCE_DIR="${PYREVIXEN_SOURCE_DIR:-}"
if [[ -z "${SOURCE_DIR}" && -f "${REPO_ROOT}/.source/SOURCE_DIR" ]]; then
    SOURCE_DIR="$(tr -d '[:space:]' < "${REPO_ROOT}/.source/SOURCE_DIR")"
fi
[[ -n "${SOURCE_DIR}" && -d "${SOURCE_DIR}" ]] || die "no source tree. Run scripts/fetch-source.sh first."

RES_DIR="${SOURCE_DIR}/mobile/android/fenix/app/src/main/res"
DRAWABLE_DIR="${RES_DIR}/drawable"
[[ -d "${DRAWABLE_DIR}" ]] || die "drawable dir missing: ${DRAWABLE_DIR}"

install_png() {
    local src="$1" dest_name="$2"
    [[ -f "${src}" ]] || die "branding asset missing: ${src}"
    # Remove the stock vector drawable (same resource name, .xml) so the
    # PNG is the unambiguous winner at build time.
    rm -f "${DRAWABLE_DIR}/${dest_name}.xml"
    cp "${src}" "${DRAWABLE_DIR}/${dest_name}.png"
    echo "    installed ${dest_name}.png"
}

echo "==> Installing PyreVixen launcher artwork ..."
install_png "${REPO_ROOT}/branding/icon/ic_launcher_foreground.png" "ic_launcher_foreground"
install_png "${REPO_ROOT}/branding/icon/ic_launcher_monochrome.png" "ic_launcher_monochrome"

# Also update src/release/res/ — the release build type overlays its own
# launcher icons that override src/main/res/. Without this, the release
# APK keeps the stock Firefox icon.
for variant in release beta nightly debug; do
    VARIANT_RES="${SOURCE_DIR}/mobile/android/fenix/app/src/${variant}/res"
    if [[ -d "${VARIANT_RES}/drawable" ]]; then
        rm -f "${VARIANT_RES}/drawable/ic_launcher_foreground.xml"
        cp "${REPO_ROOT}/branding/icon/ic_launcher_foreground.png" "${VARIANT_RES}/drawable/ic_launcher_foreground.png"
        rm -f "${VARIANT_RES}/drawable/ic_launcher_monochrome.xml"
        cp "${REPO_ROOT}/branding/icon/ic_launcher_monochrome.png" "${VARIANT_RES}/drawable/ic_launcher_monochrome.png"
        echo "    installed ${variant}/drawable/ic_launcher_foreground.png"
    fi
    for dpi in hdpi mdpi xhdpi xxhdpi xxxhdpi; do
        MIPMAP_DIR="${VARIANT_RES}/mipmap-${dpi}"
        if [[ -d "${MIPMAP_DIR}" ]]; then
            rm -f "${MIPMAP_DIR}/ic_launcher.webp" "${MIPMAP_DIR}/ic_launcher.png"
            rm -f "${MIPMAP_DIR}/ic_launcher_round.webp" "${MIPMAP_DIR}/ic_launcher_round.png"
            cp "${REPO_ROOT}/branding/icon/ic_launcher_foreground.png" "${MIPMAP_DIR}/ic_launcher.png"
            cp "${REPO_ROOT}/branding/icon/ic_launcher_foreground.png" "${MIPMAP_DIR}/ic_launcher_round.png"
            echo "    installed ${variant}/mipmap-${dpi}/ic_launcher.png"
        fi
    done
    # Also check mipmap-anydpi in variant
    if [[ -d "${VARIANT_RES}/mipmap-anydpi" ]]; then
        echo "    (variant ${variant} has mipmap-anydpi, using main's adaptive icon)"
    fi
done

# Background must be black for the circular logo to sit seamlessly.
COLORS_XML="${RES_DIR}/values/colors.xml"
[[ -f "${COLORS_XML}" ]] || die "colors.xml missing: ${COLORS_XML}"
if grep -q '<color name="ic_launcher_background">#[0-9A-Fa-f]*</color>' "${COLORS_XML}"; then
    sed -i 's|<color name="ic_launcher_background">#[0-9A-Fa-f]*</color>|<color name="ic_launcher_background">#FF000000</color>|' "${COLORS_XML}"
    echo "    ic_launcher_background -> #FF000000"
else
    die "ic_launcher_background entry not found in ${COLORS_XML}"
fi

echo "==> Branding assets installed."
