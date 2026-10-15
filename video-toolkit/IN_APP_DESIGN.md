# PyreVixen Video Toolkit — In-App Component Design

**Status:** design spec for the first real build. The video toolkit is a REAL
in-app component of the PyreVixen browser: page-side logic ships as a bundled
WebExtension asset, gestures and controls are native Android, and the two sides
talk over the same built-in-extension message bridge Fenix itself uses for
Reader View. No Tampermonkey, no userscript anywhere in the product path.

**Sources this design is grounded in:**
- `/tmp/pyrevixen-survey.md` — survey of the real `FIREFOX-ANDROID_158_0_RELEASE`
  tree at `~/workspace/pyrevixen-source/` (all class/method/file names below
  were verified there; anything not verified is marked).
- `video-toolkit/content.js` — the proven 630-line transform/gesture/memory
  logic. The logic is kept; only its **delivery** changes.

---

## 1. The hard constraint

**GeckoView renders web content into a `SurfaceView`. Android cannot apply a
`View` transform (`setScaleX`, `ViewPropertyAnimator`, etc.) to a `SurfaceView`'s
surface** — the surface is composited by SurfaceFlinger independently of the
view hierarchy, so any transform applied to the `GeckoView` widget itself would
move the whole window's contents or do nothing at all. There is no native
"zoom this rectangle of the page" API.

Therefore the zoom/pan transform itself **MUST remain a CSS transform on the
in-page `<video>` element** (`translate(tx,ty) scale(z)`, origin top-left, plus
`object-fit`) — exactly what `content.js` already does, and the only layer that
can move the video without moving the page.

**Playback, DRM, `blob:` URLs and MSE (HLS/DASH) streams never leave Gecko.**
The CSS transform is applied by Gecko's own compositor, downstream of the
media pipeline: the decoder, the DRM module (Widevine) and the MSE source
buffers are completely unaware the element is transformed. That is precisely
why DRM keeps working (nothing in the protected path is touched) — and it is
also why zoom is purely presentational and can never increase source
resolution. This is unchanged from the userscript behaviour and is the
property the whole design preserves: **native code never sees a video frame,
a URL, or a byte of media.**

What moves native is everything *around* the transform: gesture recognition
(`ScaleGestureDetector`/`GestureDetector`), the controls UI (presets, reset,
per-site memory toggle), and Settings. The page-side engine keeps the
transform math, the video attach/detach registry, and per-site memory.

---

## 2. Architecture

```
 ┌─ PAGE (Gecko, per tab) ─────────────────────────────────────────┐
 │  video-toolkit/ (bundled extension asset)                        │
 │   manifest.json ── content_scripts: [ ported content.js ]        │
 │   ported content.js = VideoController engine (transform math,    │
 │     MutationObserver attach, per-site localStorage memory)       │
 │     + connectNative("pyrevixenVideoToolkit") bridge shim        │
 │   NO touch handlers · NO pvt-* DOM overlay (both go native)     │
 └──────────────┬──────────────────────────────────────────────────┘
                │  mozac built-in-extension port
                │  (BuiltInWebExtensionController; same pattern as
                │   ReaderViewFeature / WebCompatFeature)
 ┌──────────────▼──────────────────────────────────────────────────┐
 │  APP NATIVE                                                     │
 │                                                                 │
 │  VideoToolkitFeature (org.mozilla.fenix.pyrevixen, new)         │
 │   · install(runtime) at Core engine init (WebCompat pattern)    │
 │   · registerContentMessageHandler(engineSession, …) per tab    │
 │   · sendContentMessage(JSONObject, engineSession, PORT)         │
 │        ↕ JSON protocol §5                                       │
 │  VideoGestureOverlay (new, transparent ViewGroup above          │
 │   BaseBrowserFragment.binding.engineView)                       │
 │   · ScaleGestureDetector + GestureDetector                      │
 │   · onInterceptTouchEvent: only steals classified toolkit       │
 │     gestures; everything else falls through to Gecko untouched  │
 │  Native controls: FAB + bottom sheet (7 presets, reset, ★)      │
 │  Settings: pyrevixen.video.toolkit.* prefs (§7)                │
 └─────────────────────────────────────────────────────────────────┘
```

Data flow for a pinch: finger touches → `VideoGestureOverlay` (above
`GeckoView`) → classified as pinch on a managed video → `sendContentMessage`
`pvt.pinch/update` → page-side engine applies the **existing** midpoint-anchored
`setZoom` math → replies `pvt.state` → overlay refreshes its rect cache and
the native controls UI.

---

## 3. Engine-hook mechanism: bundled WebExtension (CHOSEN)

**Chosen: the bundled-extension route** — `BuiltInWebExtensionController`
(`android-components/components/support/webextensions/.../BuiltInWebExtensionController.kt`)
with a new `src/main/assets/extensions/video-toolkit/` dir, following the
ReaderView/WebCompat pattern. **Rejected: "direct content-script injection"** —
no such API exists anywhere in the surveyed tree. GeckoView exposes page-code
injection only through the WebExtension mechanism; inventing a direct-injection
API would be fabrication. The bundled-extension route is the *only* verified
mechanism, and it is the one Fenix itself uses for `readerview`, `webcompat`,
`search`, `accounts`, and `icons` (all under
`<component>/src/main/assets/extensions/<name>/`).

Why it also wins on merit:
- **Install API is real:** `WebExtensionRuntime.installBuiltInWebExtension(id, url, …)`
  (`concept/engine/.../webextension/WebExtensionRuntime.kt`); the controller
  wrapper's `install(runtime)` dedupes via its `installedBuiltInExtensions` map.
- **The bridge comes free.** `registerContentMessageHandler(engineSession, handler, name)`,
  `sendContentMessage(msg: JSONObject, engineSession, name)`, and
  `portConnected(engineSession, name)` are exactly the native↔page channel the
  gesture layer needs, and the content-side half is the verified
  `browser.runtime.connectNative("<port>")` + `port.onMessage` /
  `port.postMessage` pattern from `readerview-content.js` (line 48).
- **No AMO, no signing, no permissions.** The manifest needs no permissions
  (`content_scripts` on `<all_urls>` is sufficient); everything is local.
- **Per-session scoping is solved:** register the handler per selected tab via
  `store.state.selectedTab?.engineState?.engineSession`
  (`TabSessionState.engineState.engineSession` — the exact accessor
  `ReaderViewFeature.connectReaderViewContentScript` uses), and guard every
  send with `portConnected(engineSession, PORT)` before
  `sendContentMessage(...)` (the exact `ReaderViewFeature.checkReaderState` guard).

### Exact registration call site (startup)

`fenix/app/src/main/java/org/mozilla/fenix/components/Core.kt`, in the
`engine` lazy property (~line 260–268), the same `.also` block where upstream
installs WebCompat:

```kotlin
GeckoEngine(
    context = context,
    defaultSettings = defaultSettings,
    runtime = geckoRuntime,
)
.also {
    WebCompatFeature.install(it)   // upstream, ~line 267
    // PyreVixen: VideoToolkitFeature(...).install(it)
}
```

Constants (all CONFIDENT — read from the real files):
- `VIDEO_TOOLKIT_EXTENSION_ID = "pyrevixen-video-toolkit@pyrevixen.browser"`
  — verbatim from `browser_specific_settings.gecko.id` in
  `video-toolkit/manifest.json`.
- `VIDEO_TOOLKIT_EXTENSION_URL = "resource://android/assets/extensions/video-toolkit/"`
  — the `resource://android/assets/extensions/<name>/` convention
  (`READER_VIEW_EXTENSION_URL = "resource://android/assets/extensions/readerview/"`,
  `ReaderViewFeature.kt:317`).
- `VIDEO_TOOLKIT_CONTENT_PORT = "pyrevixenVideoToolkit"` — our port name,
  mirroring `READER_VIEW_CONTENT_PORT = "mozacReaderview"`.

The assets themselves: copy `video-toolkit/` **verbatim** (ported per §4)
into the build at `src/main/assets/extensions/video-toolkit/` so the Android
Gradle plugin packages them and the `resource://android/...` URL resolves.
(Which module owns the assets dir — a new PyreVixen location vs an existing
component — is build-plumbing; the URL contract is what matters.)

> Note: the previous 060 draft called
> `runtime.webExtensionController.installBuiltIn(...)`. That method name does
> **not** exist in the surveyed tree and has been removed. The verified names
> are `WebExtensionRuntime.installBuiltInWebExtension(id, url, …)` and
> `BuiltInWebExtensionController.install(runtime)`.

---

## 4. Page-side port: what changes in `content.js`

The proven logic is kept; the port is mechanical. (`content.js` in this folder
is the reference implementation — the port itself is applied at build time
from this spec.)

**KEEP verbatim (the "engine"):** `VideoController` transform math
(`setZoom` midpoint anchoring, `_clampPan`, `apply`, `applyPreset`,
`cyclePreset`, `reset`, `toggleZoom`), the 7 `PRESETS`, `MIN_ZOOM`/`MAX_ZOOM`
clamping, per-site memory (`localStorage`, `pvt:remember:` prefix),
`MutationObserver` attach/detach (`maybeAttach`, `scan`, `destroy`,
`pendingSmall` retry), `MIN_SIZE` gating, the `fullscreenchange` rescan.

**REMOVE:** all direct touch handling (`_bindEvents`, `_touchStart`,
`_touchMove`, `_touchEnd`, `_onTC` — gestures now arrive as messages) and the
entire `pvt-*` DOM overlay (`_buildOverlay`, `_showBar`/`_hideBar`,
`_pokeFade`, `_updateChrome`, `positionOverlay`, `controls.css` — controls are
native now).

**ADD — bridge shim** (content script of the bundled extension):
```js
var port = browser.runtime.connectNative("pyrevixenVideoToolkit");
port.onMessage.addListener(onNativeMessage);   // §5, native → content
function reportState() {
  port.postMessage({ type: "pvt.state", hasVideo: ..., viewportScale:
    (window.visualViewport && window.visualViewport.scale) || 1,
    videos: [ { x, y, w, h, zoom, presetId, memOn } ... ] });  // rects in CSS px
}
port.postMessage({ type: "pvt.ready" });
```
`onNativeMessage` dispatches into the existing engine entry points:
`pvt.pinch` → the old `_touchStart/_touchMove` pinch math refactored as
`pinchBegin(cx,cy) / pinchUpdate(scaleFactor,cx,cy) / pinchEnd()`;
`pvt.pan` → the old pan math as `panBegin/panUpdate/panEnd`;
`pvt.doubletap` → `toggleZoom(x, y)`; `pvt.preset` → `applyPreset(presetById(id))`;
`pvt.reset` → `reset()`; `pvt.memory` → `_toggleMemory()`/set;
`pvt.setEnabled` → attach/detach all; `pvt.setDefaults` → defaults for new videos.

`reportState()` is called on attach, detach, every transform commit,
`fullscreenchange`, and throttled on scroll/resize — it is how the native side
learns video rects, zoom state, and ★ state.

**Manifest delta (ported):** keep `content_scripts` with `js: ["content.js"]`,
`matches: ["<all_urls>"]`, `all_frames: true`, no permissions; **drop** the
`css: ["controls.css"]` entry (no DOM UI remains). `gecko.id` stays
`pyrevixen-video-toolkit@pyrevixen.browser`.

---

## 5. Gesture layer (native)

**`VideoGestureOverlay`** — a transparent full-screen `ViewGroup` added as a
sibling **above** `binding.engineView` in `BaseBrowserFragment` (near the
`fullScreenFeature.set(...)` setup, ~line 1407). It owns a
`ScaleGestureDetector` and a `GestureDetector` and implements the one Android
pattern that preserves the toolkit's scroll-safety: **`onInterceptTouchEvent`
observes every touch but consumes nothing until the gesture is classified.**

Interception rules (mirror the proven `content.js` semantics):
- **Second pointer down inside a managed video rect → intercept immediately**,
  `pvt.pinch/begin`. (At 1× or zoomed — same as the old two-finger takeover.)
- **Single-finger move beyond touch slop, touch started inside a *zoomed*
  (`>1×`) video rect → intercept**, `pvt.pan/begin`. Taps are never
  intercepted, so tap-to-play/pause and page scroll keep working untouched.
- **Double-tap** via `GestureDetector.OnDoubleTapListener` inside a managed
  video rect → `pvt.doubletap` message. No interception is involved (the taps
  have already been delivered) — see the honest limitation in §9.
- **Everything else: never intercept.** No managed video under the touch, or
  an unclassified gesture → the touch falls through to `GeckoView` exactly as
  if the overlay weren't there.

**Targeting & hit-testing:** the overlay keeps the latest `pvt.state` video
rects, converted CSS px → view px. The gesture's focal video is the topmost
managed rect containing the focal point at `begin`. The port is per-session
(selected tab), so page-side routes each message to that video's controller —
no element IDs cross the bridge.

**Coordinate conversion:** gesture payloads carry view pixels plus density
(`vx, vy, density`); page-side converts to client CSS px as
`vx / density / (visualViewport.scale || 1)` using its *live* viewport scale.
(Rationale: page pinch-zoom can change mid-gesture; the page always knows the
current scale, the native side would be working from a stale `pvt.state`.)

### Message protocol

Port: `"pyrevixenVideoToolkit"`. Native→content via
`BuiltInWebExtensionController.sendContentMessage(JSONObject, engineSession, port)`
(guarded by `portConnected`); content→native via `port.postMessage`
(`browser.runtime.connectNative`), received by the `MessageHandler`
(`mozilla.components.concept.engine.webextension.MessageHandler`) registered
with `registerContentMessageHandler(engineSession, handler, port)`.

| Direction | `type` | Payload |
|---|---|---|
| N→C | `pvt.hello` | `{}` — handshake; content replies `pvt.ready` + `pvt.state` |
| N→C | `pvt.pinch` | `{phase:"begin"\|"update"\|"end", scale, vx, vy, density}` — `scale` = cumulative factor since begin; focal point = pinch midpoint |
| N→C | `pvt.pan` | `{phase:"begin"\|"update"\|"end", vx, vy, density}` — absolute current point; page-side diffs from begin |
| N→C | `pvt.doubletap` | `{vx, vy, density}` — toggles 1× ↔ last zoom at tap point |
| N→C | `pvt.preset` | `{id:"fit"\|"fill"\|"stretch"\|"one"\|"p125"\|"p150"\|"p200"}` |
| N→C | `pvt.reset` | `{}` — exact Fit |
| N→C | `pvt.memory` | `{on: bool}` — set per-site memory for the current host |
| N→C | `pvt.setEnabled` | `{enabled: bool}` — master kill switch from Settings |
| N→C | `pvt.setDefaults` | `{preset:"fit", memoryDefault:false, maxZoom:4.0}` — applied to newly attached videos |
| C→N | `pvt.ready` | `{}` — bridge alive |
| C→N | `pvt.state` | `{hasVideo, viewportScale, videos:[{x,y,w,h,zoom,presetId,memOn}]}` — rects in page CSS px |

---

## 6. Controls UI (native)

The `pvt-*` DOM overlay is gone. In its place, app-native UI styled to the
PyreVixen theme:

- **FAB:** a small native floating button shown only while `pvt.state.hasVideo`
  is true and a managed video rect is on screen, anchored near the active
  video's bottom-right (rect from the state cache, converted to view px).
  Hidden in immersive fullscreen unless the user summons it (see §8).
- **Bottom sheet:** tap the FAB → sheet with the **7 framing presets**
  (Fit / Fill / Stretch / 1:1 / 125% / 150% / 200% — same ids as `PRESETS`),
  a **Reset** button (exact Fit), a **per-site ★ memory toggle** reflecting
  `memOn` from the latest `pvt.state`, and a zoom readout. Every control sends
  the matching §5 message; state changes come back via `pvt.state`, so the UI
  can never disagree with the page.
- No WebView, no DOM, no remote assets in the controls.

---

## 7. Settings integration

Pref keys follow the `pyrevixen.*` convention in `config/default-prefs.js`
(PyreVixen-specific keys consumed by our own code; the build step maps them
into the app's default `SharedPreferences` — they are *not* Gecko prefs):

| Key | Default | Meaning |
|---|---|---|
| `pyrevixen.video.toolkit.enabled` | `true` | Master on/off. **Already declared** in `config/default-prefs.js`. `VideoToolkitFeature.install()` reads it from the default `SharedPreferences` and skips install when false; `pvt.setEnabled` propagates a runtime toggle without reinstall. |
| `pyrevixen.video.toolkit.default_preset` | `"fit"` | Preset id applied to newly attached videos (one of the 7 `PRESETS` ids). Sent via `pvt.setDefaults`. |
| `pyrevixen.video.toolkit.remember_sites_default` | `false` | When true, per-site memory starts ON for new videos (user can still toggle ★ per site). Sent via `pvt.setDefaults`. |
| `pyrevixen.video.toolkit.max_zoom` | `4.0` | Upper clamp for `MAX_ZOOM`. Sent via `pvt.setDefaults`; page-side clamps. |

Settings UI: a `SwitchPreference` (master toggle) plus a `ListPreference`
(default preset) on an existing Fenix settings screen, wired to these keys —
the keys are the contract; the exact screen placement is build-time UI work
(same minimal philosophy as the rest of this patch: the native wiring is
small, the pref keys are stable).

---

## 8. Fullscreen coordination (existing delegate — no changes to it)

The surveyed chain stays exactly as-is: `GeckoEngineSession`'s
`onFullScreen` → `EngineSession.Observer.onFullScreenChange` → browser-state
`ContentState.fullScreen` → `FullScreenFeature`
(`feature/session/FullScreenFeature.kt`, an `open` class) →
`BaseBrowserFragment.fullScreenChanged(inFullScreen)` (~line 2283) →
`activity.enterImmersiveMode(...)` / `exitImmersiveMode(...)`
(`mozilla.components.support.ktx.android.view`, `Activity.kt`), with the
sibling `MediaSessionFullscreenFeature` (~line 677) covering
media-session-driven fullscreen. **The toolkit does not modify any of this.**

Toolkit behaviour around it:
- The overlay lives in the activity window **above** `GeckoView`, so it stays
  interactive when a page goes HTML5 fullscreen (the `<video>` stays in the
  DOM; its CSS transform keeps applying — the ported `fullscreenchange`
  rescan + `pvt.state` re-report keeps the native rect cache correct).
- On `fullScreenChanged(true)`: dismiss any open bottom sheet (immersive =
  no chrome), keep the FAB available, keep the overlay intercepting.
- On `fullScreenChanged(false)`: send `pvt.hello` to re-sync state (layout
  changed under us).
- With patch 070's sticky-immersive default, the FAB/sheet must respect
  `WindowInsets` (transient system bars on edge swipe) — position from insets,
  not raw screen edges.

---

## 9. Honest limitations (carried over / new, stated plainly)

- **Native double-tap cannot suppress the site's own double-tap handler.**
  Page-side `content.js` called `preventDefault()` on the second tap-down;
  natively, `GestureDetector` only confirms a double-tap on the second tap's
  UP, by which time the page has already seen both taps (e.g. YouTube seek
  ±10 s may fire alongside the zoom toggle). Severity to be assessed on
  device — §10.
- **Canvas-based players have no `<video>` element** — nothing to attach to,
  unchanged from the userscript.
- **Zoom is presentational** (CSS) — DRM-safe by construction, but never adds
  source resolution.
- **Small videos (< ~120 px)** get no controls unless per-site memory already
  holds a zoom for the host — unchanged rule from `content.js`.

---

## 10. NEEDS FIRST BUILD TO CONFIRM

What cannot be verified without compiling and running on device:

1. **Install path choice at runtime:** whether `BuiltInWebExtensionController(...).install(runtime)`
   or a direct `runtime.installBuiltInWebExtension(id, url, …)` (both verified
   in-tree — `WebExtensionRuntime` interface and `WebCompatFeature.install`)
   is the one that actually completes inside Core's engine `.also` block.
2. **`resource://android/assets/extensions/video-toolkit/` resolution** when the
   assets ship from our chosen module (AGP merges all modules' assets, but the
   URL mapping must be seen working in logcat).
3. **`browser.runtime.connectNative("pyrevixenVideoToolkit")` from a built-in
   extension content script on GeckoView 158** — the pattern is verified in
   `readerview-content.js`, but the live handshake needs the built APK.
4. **Exact `MessageHandler` functional signature**
   (`mozilla.components.concept.engine.webextension.MessageHandler`) — read
   the interface at build time; the design only assumes "receives content
   messages".
5. **`store.state.selectedTab?.engineState?.engineSession`** resolving from
   `BaseBrowserFragment` with the same imports `ReaderViewFeature` uses.
6. **Touch-interception interplay with `GeckoView`:** that
   `onInterceptTouchEvent` on an overlay above the engine view reliably sees
   the stream, and that *not* intercepting leaves site touch handling
   bit-identical (scroll, tap, site pinch-zoom).
7. **Pinch-begin race:** intercepting on the second pointer-down vs Gecko's
   own gesture handling — confirm no stuck-gesture state on either side.
8. **Coordinate conversion accuracy** across page zoom (`visualViewport.scale`
   changes mid-gesture), device density buckets, and dynamic viewport resize.
9. **Double-tap site-handler race** (§9) — measure how bad it is on real
   sites; decide whether to mitigate (e.g. optional "double-tap claims
   gestures" mode) or document.
10. **Immersive-fullscreen insets vs FAB/sheet positioning** (patch 070
    interplay) and overlay behaviour under `MediaSessionFullscreenFeature`.
11. **`<all_urls>` + `all_frames: true` content-script injection for a
    built-in extension with zero permissions** on GeckoView 158 — the current
    `manifest.json` already declares this shape; confirm it installs silently.
12. **Per-session handler registration timing:** when to call
    `registerContentMessageHandler` for a new/selected tab so no `pvt.state`
    is ever lost (mirror `ReaderViewFeature`'s reader-connect flow and verify).
