# PyreVixen release gate

**No gate, no release.** Every box below must be checked on the exact APKs
being shipped before a GitHub Release is published. A waived item goes into
the release notes under "Known issues" with its reason — never silently.

## 1. Video matrix (video-toolkit)

Test on **YouTube and Vimeo**, each:

- [ ] Pinch-to-zoom changes the video scale smoothly, no tearing
- [ ] Pan clamps at the video edges (no black void, no overscroll)
- [ ] Every zoom preset applies correctly (fit / fill / 2x / …)
- [ ] Double-tap resets zoom and pan to default
- [ ] Fullscreen entry and exit both work, player state survives the round trip
- [ ] A DRM-protected site still plays (e.g. a Widevine title)
- [ ] A live / HLS stream still plays (seek, pause, resume)

## 2. Immersive fullscreen

- [ ] Launch: no status bar, no nav bar
- [ ] Tabs tray: no status bar, no nav bar
- [ ] Settings screens: no status bar, no nav bar
- [ ] Fullscreen video: no status bar, no nav bar
- [ ] After an edge swipe, bars appear then **auto-hide** again

## 3. Custom homepage

- [ ] Mode 1 — Firefox Home: shows the standard home content
- [ ] Mode 2 — blank page: shows a blank page, no network requests
- [ ] Mode 3 — custom URL: loads the configured URL
- [ ] Choice **persists across a full app restart** (force-stop, relaunch)
- [ ] Home button routes to the chosen homepage
- [ ] New-tab homepage toggle: ON opens homepage in new tabs, OFF does not

## 4. Privacy

- [ ] Fresh install + fresh profile: capture network traffic for 5 minutes of
      normal browsing — **no** requests to telemetry, AI, sponsored-content,
      or experiment endpoints
- [ ] AI features are absent after a restart **and** after an update install
      (not just hidden — no UI, no background service)
- [ ] Every setting matches `config/default-prefs.js`, line by line
      (telemetry off, studies off, sponsored off, AI off)

## 5. Everyday use

- [ ] Saved logins persist across restart and across an update install
- [ ] A file download completes and opens
- [ ] uBlock Origin works in a normal tab **and** a private tab
- [ ] Firefox Sync is **opt-in only** (never signed in by default)
- [ ] Strict Enhanced Tracking Protection: the per-site shield toggle fixes
      a broken site (breakage is expected sometimes; the escape hatch must work)

## 6. Install / update

- [ ] Installing over the previous version keeps tabs, bookmarks, history,
      logins, and settings (same signing key — see RUNBOOK.md)
- [ ] `sha256sum -c SHA256SUMS` passes for every APK in the release
- [ ] Release notes render with no leftover `{{PLACEHOLDERS}}`
