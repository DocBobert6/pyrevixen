# PyreVixen

<img src="branding/icon/ic_launcher_foreground.png" alt="PyreVixen launcher icon" width="128">

A privacy-forward Android browser based on Firefox for Android — the full Firefox UI you know, with the surveillance stripped out.

- **Full Firefox UI** — tabs, address bar, menus, extensions (uBlock Origin), Sync (opt-in only). Nothing to relearn.
- **No AI features** — removed, not just toggled off.
- **No telemetry** — no experiments, no sponsored content, no Pocket, no Adjust, no InstallReferrer. Glean initializes minimally (to prevent crashes) with upload **forced off** — no data ever leaves your device.
- **Custom video toolkit** — pinch-to-zoom (1x-4x), pan with clamping, zoom presets (Fit/Fill/Stretch/1:1/125%/150%/200%), double-tap reset. Works on YouTube, Vimeo, and HTML5 video everywhere.
- **Immersive fullscreen** — status and nav bars auto-hide.
- **Custom homepage** — Firefox Home, blank page, or your own URL; persists across restarts.

> **Package:** `org.pyrevixen.browser`

## Install

### From GitHub Releases (recommended)

1. Go to the [Releases](../../releases) page
2. Download the APK for your device:
   - **arm64-v8a** — modern phones (Pixel, Samsung Galaxy S series, etc.)
   - **armeabi-v7a** — older 32-bit devices
   - **x86_64** — emulators, Chromebooks
   - **universal** — all architectures (larger file)
3. Verify the download (recommended):
   ```
   sha256sum -c SHA256SUMS
   ```
4. Open the APK to install. Updates install over the previous version, keeping your tabs, bookmarks, and settings.

### Via Obtainium

Add the Releases page URL (`https://github.com/DocBobert6/pyrevixen/releases`) to [Obtainium](https://obtainium.imranr.dev/) and it will notify you of new versions automatically.

## App Verification

Verify you're installing the genuine PyreVixen build:

**Package ID:** `org.pyrevixen.browser`

**SHA-256 of signing certificate:**
```
A6:6B:43:A6:BB:F4:1B:1D:52:D8:70:3E:0E:42:DA:24:17:A2:AC:A9:58:1F:51:F3:FA:59:96:84:8B:15:15:45
```

To check: install the APK, then run:
```
apksigner verify --print-certs pyrevixen-*.apk
```
The SHA-256 digest should match the above.

## FAQ

### Is PyreVixen just Firefox with a different icon?

No. PyreVixen is built from Firefox source with 8 source patches that remove AI features, telemetry, experiments, sponsored content, and tracking integrations. The Glean analytics SDK is present (to keep the app stable) but initializes with upload permanently disabled — it cannot send data.

### Does PyreVixen phone home to Mozilla or Google?

No. On first launch, PyreVixen does not contact Mozilla telemetry, Adjust, or Google services for analytics. Standard browser functions (like Safe Browsing lookups, if enabled) work as in Firefox, but no usage data is collected or uploaded.

### Can I use Firefox Sync?

Yes. Sync is opt-in — sign in with your Mozilla account in Settings if you want it. It's disabled by default.

### Do extensions work?

Yes. PyreVixen supports Firefox for Android extensions, including uBlock Origin. Install them from the Add-ons Manager.

### Why is the APK so large (134MB)?

Firefox for Android includes the full Gecko rendering engine as native libraries. The arm64 build is 134MB; this is normal for a Firefox-based browser.

### How do I update?

Download the new APK from Releases and install it over the old version. Your data is preserved (same signing key). Or use Obtainium for automatic update notifications.

### What Android versions are supported?

Android 8.0 (API 26) and above, same as Firefox for Android 158.

## Privacy Details

What PyreVixen removes or disables:

| Feature | Status |
|---------|--------|
| AI chatbots / AI features | Removed |
| Glean telemetry upload | Disabled (SDK initializes minimally to prevent crashes, `uploadEnabled=false`) |
| Mozilla experiments (Nimbus) | Disabled |
| Sponsored content / Pocket | Removed |
| Adjust attribution SDK | Removed |
| InstallReferrer | Removed |
| Crash reporting to Mozilla | Disabled |

What PyreVixen keeps:

| Feature | Status |
|---------|--------|
| Full Firefox UI | Intact |
| Gecko rendering engine | Intact |
| Extensions (uBlock Origin, etc.) | Supported |
| Firefox Sync | Opt-in |
| Private browsing | Intact |

## How the cloud build works

You never need a computer for any of this:

1. The pinned upstream version lives in [VERSION](VERSION) (currently `158.0`).
2. Push to `main` → GitHub Actions runs [.github/workflows/build.yml](.github/workflows/build.yml):
   fetch + verify Firefox source → apply `patches/` in order → run fix scripts → Gradle builds per-ABI APKs → sign with encrypted CI key → publish GitHub Release.
3. Install the APK from the Release. That's the whole pipeline.

## Repo layout

```
VERSION                     pinned Firefox base version
scripts/
  fetch-source.sh           download + verify upstream source
  apply-patches.sh          apply patches/ 010->080 + run fix scripts
  build.sh                  per-ABI Gradle build
  release.sh                sign APKs + checksums + notes
  fix-glean-crash.py        minimal Glean init (upload=false) to prevent crash
  fix-dangling-refs.py      fix refs to deleted tracker files
  delete-adjust-referrer.py delete Adjust/InstallReferrer wrappers
  readd-glean.py            re-add Glean SDK deps (kept inert)
  apply-branding-assets.sh  install launcher icon
patches/                    010-branding … 080-custom-homepage
config/                     privacy-default preferences
video-toolkit/              in-app video zoom/pan component
branding/                   icon, colors, rename guide
.github/workflows/
  build.yml                 cloud build -> signed Release
  rebase-check.yml          weekly patch compat check
```

## Docs

- [RUNBOOK.md](RUNBOOK.md) — how to ship an update. **Read the signing-key backup warning.**
- [TESTING.md](TESTING.md) — release-gate checklist.

## License

Mozilla's code stays under the **Mozilla Public License 2.0** (see [LICENSE](LICENSE)). Our additions (patches, scripts, branding, docs) are also under MPL 2.0.
