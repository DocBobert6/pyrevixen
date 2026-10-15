/* =============================================================================
 * PyreVixen — config/default-prefs.js
 *
 * EVERY default preference this browser sets, in one auditable file.
 *
 * FORMAT:  // reason: <one line>
 *          pref("name", value);
 *
 * HOW IT IS APPLIED (build-time, rebase-proof):
 *   This file is consumed by the build (NOT shipped to users). A build step
 *   injects these as Gecko DEFAULT prefs for the GeckoView runtime used by
 *   the app — e.g. via the engine's default-preferences file or the
 *   GeckoRuntime default-prefs hook wired in by the privacy patches. Because
 *   they are DEFAULTS (not user prefs), the user can still change any of
 *   them in about:config; a fresh profile always starts from these values.
 *   That is deliberate: defaults harden the browser, user choice overrides.
 *
 * KEY CONVENTIONS:
 *   * Standard Gecko prefs use pref("...", ...).
 *   * pyrevixen.* keys are PyreVixen-specific settings consumed by our own
 *     code/patches (060 video toolkit, 070 immersive fullscreen, 080 custom
 *     homepage). They are NOT Gecko prefs; the build step maps them into the
 *     app's default SharedPreferences / Settings store.
 *   * Lines tagged [BEST-EFFORT] use a pref key whose exact name must be
 *     verified against the Gecko 158 source on the first real CI build.
 *     Everything else uses long-stable, well-documented Gecko pref keys.
 *
 * AUDIT MAP (which patch each section enforces):
 *   telemetry/crash ............ patch 020 (020 removes the SDKs; these
 *                                prefs silence the built-in Gecko paths)
 *   studies/nimbus .............. patch 040
 *   AI .......................... patch 030
 *   sponsored/pocket/suggest .... patch 040
 *   tracking/https-only/cookies . patch 050
 *   homepage keys ............... patch 080 (custom homepage; reads
 *                                pyrevixen.homepage.*)
 *   video toolkit key ........... patch 060 (reads pyrevixen.video.toolkit.enabled)
 *   fullscreen immersive key .... patch 070 (reads pyrevixen.fullscreen.immersive)
 * ========================================================================== */

/* ---------------- Telemetry: everything off (supports patch 020) -------- */
// reason: master switch for legacy Telemetry — no pings are ever assembled.
pref("toolkit.telemetry.enabled", false);
// reason: unified Telemetry off — no upload path, no saved-telemetry archive.
pref("toolkit.telemetry.unified", false);
// reason: do not archive telemetry pings locally for later upload.
pref("toolkit.telemetry.archive.enabled", false);
// reason: no "new profile" ping on first run.
pref("toolkit.telemetry.newProfilePing.enabled", false);
// reason: no shutdown ping sender — nothing queued at shutdown.
pref("toolkit.telemetry.shutdownPingSender.enabled", false);
// reason: no update ping — update events are not reported.
pref("toolkit.telemetry.updatePing.enabled", false);
// reason: no background-hang ping — hang telemetry disabled.
pref("toolkit.telemetry.bhrPing.enabled", false);
// reason: no first-shutdown ping for new profiles.
pref("toolkit.telemetry.firstShutdownPing.enabled", false);
// reason: health report (about:healthreport data) is never uploaded.
pref("datareporting.healthreport.uploadEnabled", false);
// reason: the data-submission policy master switch — user data never submitted.
pref("datareporting.policy.dataSubmissionEnabled", false);
// reason: legacy usage-data upload path disabled.
pref("datareporting.usage.uploadEnabled", false);
// reason: Normandy (remote recipe runner) off — no remote actions ever.
pref("app.normandy.enabled", false);
// reason: no stable client id is minted, so even local telemetry cannot be
// reason: correlated across sessions. (single logical entry, two lines)
pref("toolkit.telemetry.cachedClientId", "");

/* ---------------- Crash reporting: off, no endpoint (patch 020) --------- */
// reason: built-in Gecko crash reporter disabled — no crash UI, no upload.
pref("toolkit.crashreporter.enabled", false);
// reason: no crash-report endpoint configured — nowhere to send reports even
// reason: if a reporter path were re-enabled. (single logical entry)
pref("breakpad.reportURL", "");

/* ---------------- Studies / Nimbus: off (patch 040) ---------------------- */
// reason: Shield opt-out studies disabled — no silent experiment enrollment.
pref("app.shield.optoutstudies.enabled", false);
// reason: [BEST-EFFORT] Nimbus experiment loader gets no remote URL.
// reason: Belt-and-suspenders with patch 040's init removal.
pref("nimbus.remote-settings.url", "");

/* ---------------- Generative AI: off (patch 030) ------------------------- */
// reason: [BEST-EFFORT] on-device ML backend switch off — no local AI runs.
pref("browser.ml.enable", false);
// reason: [BEST-EFFORT] AI chatbot entry points disabled.
pref("browser.ml.chat.enabled", false);
// reason: [BEST-EFFORT] chatbot shortcuts/entry affordances disabled.
pref("browser.ml.chat.shortcuts", false);
// reason: [BEST-EFFORT] no AI provider configured — empty means unreachable.
pref("browser.ml.chat.provider", "");
// reason: [BEST-EFFORT] AI page summarisation / page-assist disabled.
pref("browser.ml.chat.pageAssist", false);
// reason: [BEST-EFFORT] AI-powered automatic tab grouping disabled.
pref("browser.tabs.groups.ai.enabled", false);

/* ---------------- Tracking protection: STRICT (patch 050) ---------------- */
// reason: Enhanced Tracking Protection category = Strict for all profiles.
pref("browser.contentblocking.category", "strict");
// reason: tracking protection enforced in normal windows.
pref("privacy.trackingprotection.enabled", true);
// reason: tracking protection enforced in private windows too.
pref("privacy.trackingprotection.pbmode.enabled", true);
// reason: cryptominer and fingerprinting blocking at strict level.
pref("privacy.trackingprotection.cryptomining.enabled", true);
pref("privacy.trackingprotection.fingerprinting.enabled", true);

/* ---------------- HTTPS-Only mode (patch 050) ---------------------------- */
// reason: HTTPS-Only mode on — http:// upgrades automatically, warns otherwise.
pref("dom.security.https_only_mode", true);
// reason: HTTPS-Only mode also enforced in private browsing.
pref("dom.security.https_only_mode_pbm", true);
// reason: HTTPS-Only applies to local-network addresses as well.
pref("dom.security.https_only_mode.upgrade_local", true);

/* ---------------- Total Cookie Protection (patch 050) -------------------- */
// reason: cookieBehavior=5 — third-party cookies rejected and storage
// reason: partitioned per first party (Total Cookie Protection). (one entry)
pref("network.cookie.cookieBehavior", 5);
// reason: same Total Cookie Protection policy in private browsing mode.
pref("network.cookie.cookieBehavior.pbmode", 5);
// reason: lifetime policy keeps cookies to the session unless the site needs
// reason: persistence — limits long-term tracking state. (one entry)
pref("network.cookie.lifetimePolicy", 2);

/* ---------------- Signals: DNT + GPC on ---------------------------------- */
// reason: send Do Not Track header — a request signal, honored where supported.
pref("privacy.donottrackheader.enabled", true);
// reason: send Global Privacy Control signal — legal opt-out signal.
pref("privacy.globalprivacycontrol.enabled", true);
// reason: GPC also exposed to the page via the functionality API.
pref("privacy.globalprivacycontrol.functionality.enabled", true);

/* ---------------- Search / Suggest / Sponsored: off (patch 040) ---------- */
// reason: search suggestions off — keystrokes never leave the device.
pref("browser.search.suggest.enabled", false);
// reason: urlbar never offers search suggestions.
pref("browser.urlbar.suggest.searches", false);
// reason: Firefox Suggest quick-suggest entirely off.
pref("browser.urlbar.quicksuggest.enabled", false);
// reason: sponsored Suggest results off (no ad partners in the urlbar).
pref("browser.urlbar.suggest.quicksuggest.sponsored", false);
// reason: non-sponsored Suggest results off as well — zero Suggest traffic.
pref("browser.urlbar.suggest.quicksuggest.nonsponsored", false);
// reason: sponsored Top Sites tiles (Contile) off — no sponsored shortcuts.
pref("browser.topsites.contile.enabled", false);

/* ---------------- Pocket / promotional content: off (patch 040) ---------- */
// reason: Pocket integration disabled — no Pocket stories, no Pocket API use.
pref("extensions.pocket.enabled", false);
// reason: no sponsored content on the home screen / new tab page.
pref("browser.newtabpage.activity-stream.showSponsored", false);
// reason: no sponsored Top Sites on the home screen.
pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);
// reason: no Pocket/Discovery-Stream story feed on the home screen.
pref("browser.newtabpage.activity-stream.discoverystream.enabled", false);
// reason: no "top stories" section feed on the home screen.
pref("browser.newtabpage.activity-stream.feeds.section.topstories", false);

/* ---------------- Network / fingerprinting hardening --------------------- */
// reason: WebRTC disabled — prevents local IP leaks via ICE candidates.
// reason: (video-toolkit patch 060 does not need WebRTC; re-enable only if a
// reason: user-facing feature requires it). (single logical entry)
pref("media.peerconnection.enabled", false);
// reason: geolocation API disabled — sites cannot request location.
pref("geo.enabled", false);
// reason: Battery Status API disabled — a known fingerprinting vector.
pref("dom.battery.enabled", false);
// reason: Beacon API disabled — no fire-and-forget analytics on unload.
pref("beacon.enabled", false);
// reason: clipboard events not exposed to pages — blocks paste-jacking probes.
pref("dom.event.clipboardevents.enabled", false);
// reason: referrer trimmed to origin on cross-origin navigations.
pref("network.http.referer.XOriginPolicy", 2);
// reason: hyperlink auditing (ping tracking) disabled.
pref("browser.send_pings", false);
// reason: DNS-over-HTTPS enabled (mode 3 = TRR only) — encrypts DNS.
// reason: [BEST-EFFORT] confirm TRR endpoint default on Gecko 158; the mode
// reason: value itself is stable. (single logical entry)
pref("network.trr.mode", 3);
// reason: prefetching disabled — no speculative connections leaking intent.
pref("network.prefetch-next", false);
pref("network.dns.disablePrefetch", true);
pref("network.predictor.enabled", false);
// reason: speculative parallel connections at startup disabled.
pref("network.http.speculative-parallel-limit", 0);

/* ---------------- PyreVixen-specific keys (patches 060 / 070 / 080) -------- */
// NOTE: pyrevixen.* are NOT Gecko prefs. The build step maps them into the
// app's default settings store. Documented here so the whole default
// configuration stays in one auditable file.
// reason: video toolkit (patch 060) is enabled by default; user can toggle.
pref("pyrevixen.video.toolkit.enabled", true);
// reason: video toolkit (patch 060) — default framing preset for newly
// reason: attached videos; one of fit|fill|stretch|one|p125|p150|p200.
pref("pyrevixen.video.toolkit.default_preset", "fit");
// reason: video toolkit (patch 060) — per-site memory starts ON for new
// reason: videos when true; the per-site star toggle still overrides per host.
pref("pyrevixen.video.toolkit.remember_sites_default", false);
// reason: video toolkit (patch 060) — maximum pinch zoom factor.
pref("pyrevixen.video.toolkit.max_zoom", 4.0);
// reason: immersive fullscreen (patch 070) — status + nav bars hidden in
// reason: fullscreen video by default. (single logical entry)
pref("pyrevixen.fullscreen.immersive", true);
// reason: homepage mode for patch 080 — "custom" uses the URL below;
// reason: other modes ("blank", "default") are the user's choice in Settings.
pref("pyrevixen.homepage.mode", "custom");
// reason: default custom homepage URL for patch 080 (about:blank keeps first
// reason: run free of any network fetch; user can set any URL in Settings).
pref("pyrevixen.homepage.custom_url", "about:blank");
// reason: custom homepage also used for new tabs when homepage mode is custom.
pref("pyrevixen.homepage.use_for_new_tabs", false);
