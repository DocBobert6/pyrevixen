# PyreVixen Video Toolkit

In-place pinch-to-zoom, drag-to-pan, and framing presets for `<video>` elements —
a **real in-app component** of the PyreVixen browser (bundled via patch 060,
designed in `IN_APP_DESIGN.md`). No Tampermonkey, no userscript in the product
path.

## What it does

- **Pinch-to-zoom 1.0×–4.0×** on any video, zooming around the midpoint between
  your two fingers (the point under your fingers stays put).
- **Drag-to-pan** while zoomed, clamped so the video frame can never be panned
  into empty space (pan limits are computed from the zoom level and element size).
- **Framing presets:** Fit (whole picture, `object-fit: contain`), Fill
  (`object-fit: cover`), Stretch (`object-fit: fill`), 1:1, 125%, 150%, 200%.
- **Double-tap** toggles between 1× and your last zoom, centred on the tap.
- **Native controls:** a small floating button (bottom-right of the video) that
  opens a bottom sheet with the 7 presets, reset (exact Fit), and a per-site
  memory toggle (★). No in-page DOM overlay — the controls are app UI.
- **Per-site memory (optional):** the ★ toggle remembers the last zoom + preset
  per hostname in the page's `localStorage` and re-applies it to videos on that
  site.
- **Scroll-safe:** at 1× zoom, single-finger touches are never intercepted, so
  page scrolling and the site's own controls work untouched. Gestures are only
  captured when zoomed or when two fingers are down.
- **Fullscreen-safe:** survives HTML5 fullscreen; the native overlay sits above
  the engine view and stays interactive, coordinating with the existing
  fullscreen delegate.
- **Dynamic players:** a `MutationObserver` picks up videos added later by
  JavaScript (SPAs, lazy players); `all_frames: true` covers videos inside
  iframes, including cross-origin ones.
- Videos smaller than ~120 px (ads, thumbnails) are ignored — unless per-site
  memory already holds a zoom for that host, which counts as you explicitly
  opting in.

Zoom is a CSS `transform` (`translate` + `scale`, origin top-left) plus
`object-fit` on the video element itself — this is a hard platform constraint
(GeckoView renders to a `SurfaceView`, which Android cannot transform), so the
transform must live in the page. Playback, DRM, `blob:` URLs and MSE
(HLS/DASH) streams are never touched — the media pipeline is unaware the zoom
exists. The page is never transformed.

Privacy: all files are local, no remote code, no permissions in the manifest,
no network calls, no analytics. Per-site memory lives in the page's own
`localStorage`. Native code never sees a video frame, a URL, or a byte of media.

## Files

| File | Purpose |
|---|---|
| `IN_APP_DESIGN.md` | **The component design spec** — architecture, engine-hook mechanism, gesture layer, message protocol, controls UI, Settings keys, fullscreen coordination, and what needs the first build to confirm. Read this first. |
| `manifest.json` | WebExtension manifest (v2, GeckoView/Firefox-Android compatible). Content script on `<all_urls>`, `document_idle`, `all_frames: true`, no permissions. `gecko.id` is `pyrevixen-video-toolkit@pyrevixen.browser` — the ID patch 060 registers. |
| `content.js` | The full toolkit logic: transform math, attach/detach registry, per-site memory, gesture state machines. **Reference implementation** — the build ports it per `IN_APP_DESIGN.md` §4 (engine kept; touch handlers and the `pvt-*` DOM overlay removed; `connectNative` bridge added). |
| `controls.css` | Overlay styles for the reference DOM UI in `content.js`. Not shipped in the product build (controls are native); kept for the dev userscript below. |
| `pyrevixen-video-toolkit.user.js` | **Dev/tuning tool only** — standalone userscript build (`controls.css` inlined + the `content.js` core). NOT on the product path. See below. |

## The userscript is a dev tool, not the product

`pyrevixen-video-toolkit.user.js` exists so the transform math, presets, pan
clamping, and per-site memory can be **tuned and feel-tested today in any
Firefox** (via Tampermonkey/Violentmonkey) without waiting for a full browser
build. It is explicitly **off the critical path**: Tampermonkey is not part of
the product, and nothing about the shipped browser depends on the userscript
working.

To use it as a tuning rig:

1. Install **Tampermonkey** (or Violentmonkey) in Firefox.
2. Open the dashboard → **Create a new script**, delete the template, paste the
   entire contents of `pyrevixen-video-toolkit.user.js`.
3. Save (the `@match *://*/*` and `@run-at document-idle` header is already set).
4. Open any page with a video: pinch to zoom, drag to pan, double-tap to
   toggle, tap the floating button for presets.

Tune `content.js` (then rebuild the userscript from it — edit `content.js`,
not the `.user.js` directly), and the ported in-app component inherits the
tuning. On desktop Firefox you can test with touch emulation (responsive
design mode); the gestures themselves are touch-driven.

## Validation happens in the first built APK

The plan's old Phase 1 "feel test" (Tampermonkey in stock Firefox) is replaced
by validation in the first real PyreVixen build. When the APK exists, verify:

1. The extension installs at startup (logcat: no install failure; gated by
   the `pyrevixen.video.toolkit.enabled` pref).
2. `pvt.ready` / `pvt.state` handshake completes on a page with a video.
3. Pinch 1–4× anchors on the finger midpoint; pan clamps at edges; double-tap
   toggles; the 7 presets + reset + ★ all round-trip through the message
   bridge.
4. Page scroll, tap-to-play, and site controls are untouched when no toolkit
   gesture is in progress (the overlay must be behaviourally invisible).
5. HTML5 fullscreen: overlay stays interactive, state re-syncs on exit.
6. Per-site memory persists per hostname; master toggle in Settings disables
   everything.

The full checklist of what cannot be confirmed without compiling is
`IN_APP_DESIGN.md` §10 ("NEEDS FIRST BUILD TO CONFIRM").

## Known limits

- **Canvas-based custom players have no `<video>` element**, so there is nothing
  to attach to — no controls appear. (If a page renders video to `<canvas>`,
  the toolkit cannot help.)
- **DRM framing only:** zoom/pan is purely presentational (CSS). The stream
  itself is untouched, which is exactly why DRM keeps working — but it also
  means zoom cannot increase source resolution.
- **Double-tap is claimed by the toolkit** on managed videos in the reference
  implementation (the second tap's default is suppressed so the site's own
  double-tap action, e.g. seek ±10 s, does not fire alongside the zoom
  toggle). In the native component this suppression is not possible —
  documented as an honest limitation in `IN_APP_DESIGN.md` §9, severity to be
  assessed on device.
- **Small videos (< ~120 px)** get no controls unless per-site memory already
  has a zoom saved for that host.
- `localStorage` may be unavailable in some private-browsing configurations;
  per-site memory then silently does nothing (all other features keep working).
