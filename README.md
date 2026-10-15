# PyreVixen

<img src="branding/icon/ic_launcher_foreground.png" alt="PyreVixen launcher icon" width="128">

A privacy-forward Android browser based on Fennec (Firefox for Android) —
the full Firefox UI you know, with the surveillance stripped out.

- **Full Firefox UI** — tabs, address bar, menus, extensions (uBlock Origin),
  Sync (opt-in only). Nothing to relearn.
- **No AI features** — removed, not just toggled off; verified absent after
  restarts and updates.
- **No telemetry** — no experiments, no sponsored content, no Pocket, no
  Adjust, no InstallReferrer. Glean's SDK ships but is never initialized
  (the init call is a no-op), so it cannot collect or upload anything.
  A fresh install phones home to nobody.
- **Custom video toolkit** — in-app component (no userscript): pinch-to-zoom,
  pan with clamping, zoom presets, double-tap reset, on YouTube, Vimeo,
  DRM sites, and live/HLS streams. Design: video-toolkit/IN_APP_DESIGN.md.
- **Immersive fullscreen** — status and nav bars hidden; they auto-hide
  again after an edge swipe.
- **Custom homepage** — Firefox Home, blank page, or your own URL; persists
  across restarts; optional new-tab routing.

> **Name:** PyreVixen (`org.pyrevixen.browser`) — decided 2026-10-14.
> Rename guide (if it ever changes): [branding/BRANDING.md](branding/BRANDING.md).

## Install (no PC needed)

1. Open the [Releases](../../releases) page and download the APK for your
   ABI — **arm64-v8a** for modern phones (e.g. Pixel 10a); armeabi-v7a for
   older 32-bit devices; x86_64 for emulators/Chromebooks.
2. Verify it (optional but recommended):
   `sha256sum -c SHA256SUMS` against the `SHA256SUMS` file in the release.
3. Install the APK. Updates install over the previous version and keep your
   tabs, bookmarks, and settings (same signing key — see RUNBOOK.md).

**Obtainium:** add the Releases page URL to Obtainium and it will track new
PyreVixen versions for you automatically.

## How the cloud build works

You never need a computer for any of this:

1. The pinned upstream version lives in [VERSION](VERSION)
   (currently `158.0`).
2. Push to `main` (or bump `VERSION`) → GitHub Actions runs
   [.github/workflows/build.yml](.github/workflows/build.yml):
   fetch + SHA-verify the Firefox source → apply `patches/` in order
   (010→080, any failure aborts the build) → Gradle builds per-ABI APKs
   (arm64-v8a first) → signs them with the encrypted CI key → publishes a
   GitHub Release with APKs, `SHA256SUMS`, and release notes.
3. Install the APK from the Release. That's the whole pipeline.

Weekly, [rebase-check.yml](.github/workflows/rebase-check.yml) dry-runs the
patches against the *latest* Firefox release and reports which ones need
work before the next rebase.

## Repo layout

```
VERSION                     pinned Firefox base version (single line)
scripts/
  fetch-source.sh           download + SHA-verify upstream source
  apply-patches.sh          apply patches/ 010->080 (fails loudly)
  build.sh                  fetch -> patch -> per-ABI Gradle build (no secrets)
  release.sh                sign APKs (env/CI secrets only) + checksums + notes
  readd-glean.py            re-add Glean SDK deps after 020 (kept inert)
  delete-adjust-referrer.py delete Adjust/InstallReferrer wrapper files
  fix-dangling-refs.py      fix refs to deleted tracker files + UTMParams stub
patches/                    010-branding … 080-custom-homepage (numbered order)
config/                     default-prefs.js, search-engines.json (privacy defaults)
video-toolkit/              in-app video component sources (IN_APP_DESIGN.md)
branding/                   BRANDING.md (rename guide), icon-master.svg,
                            icon/ (launcher foreground + monochrome),
                            colours.md, strings.md
templates/                  release-notes.md template
.github/workflows/
  build.yml                 cloud build -> signed GitHub Release
  rebase-check.yml          weekly dry-run of patches vs latest Firefox
README.md  TESTING.md  RUNBOOK.md  LICENSE
```

`patches/`, `config/`, and `video-toolkit/` are maintained alongside this
repo; the scripts and workflows above are what turn them into a browser.

## Docs

- [RUNBOOK.md](RUNBOOK.md) — how to ship an update (bump VERSION, fix
  patches, run the gate, release). **Read the signing-key backup warning.**
- [TESTING.md](TESTING.md) — the release-gate checklist. No gate, no release.

## License

Mozilla's code stays under the **Mozilla Public License 2.0** (see
[LICENSE](LICENSE)); Mozilla's trademarks are removed from the product.
Our own additions (patches, scripts, branding, docs) are also under MPL 2.0.
