/*
 * PyreVixen Video Toolkit — content script
 * ========================================
 * In-place pinch-to-zoom, drag-to-pan and framing presets for <video>
 * elements. Zoom is a CSS transform (translate + scale) applied to the
 * video element itself inside Gecko's rendering — playback, DRM, blob:
 * URLs and MSE (HLS/DASH) streams are never touched. The page itself is
 * never transformed.
 *
 * All state is local. No network calls, no extension APIs, no permissions.
 * The same core ships verbatim inside pyrevixen-video-toolkit.user.js.
 */
(function () {
  'use strict';

  /* ------------------------------- configuration ------------------------------- */
  var MIN_SIZE = 120;        // videos smaller than this (either dimension) are ignored by default
  var MIN_ZOOM = 1.0;
  var MAX_ZOOM = 4.0;
  var ZOOM_STEP = 1.25;      // +/- button step multiplier
  var DBL_TAP_MS = 320;      // max ms between taps to count as a double-tap
  var DBL_TAP_PX = 32;       // max px between taps to count as a double-tap
  var PAN_THRESHOLD_PX = 6;  // drag distance before a touch becomes a pan
  var FADE_MS = 2500;        // control bar auto-collapse delay
  var MEM_PREFIX = 'pvt:remember:'; // localStorage key prefix for per-site memory

  var PRESETS = [
    { id: 'fit',     label: 'Fit',     zoom: 1,    fit: 'contain' },
    { id: 'fill',    label: 'Fill',    zoom: 1,    fit: 'cover'   },
    { id: 'stretch', label: 'Stretch', zoom: 1,    fit: 'fill'    },
    { id: 'one',     label: '1:1',     zoom: 1,    fit: 'contain' },
    { id: 'p125',    label: '125%',    zoom: 1.25, fit: 'contain' },
    { id: 'p150',    label: '150%',    zoom: 1.5,  fit: 'contain' },
    { id: 'p200',    label: '200%',    zoom: 2,    fit: 'contain' }
  ];

  /* --------------------------------- helpers --------------------------------- */
  function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }

  function touchDist(a, b) {
    var dx = a.clientX - b.clientX, dy = a.clientY - b.clientY;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function touchMid(a, b) {
    return { x: (a.clientX + b.clientX) / 2, y: (a.clientY + b.clientY) / 2 };
  }

  function presetById(id) {
    for (var i = 0; i < PRESETS.length; i++) {
      if (PRESETS[i].id === id) return PRESETS[i];
    }
    return null;
  }

  function readMemory() {
    // Returns the stored per-site entry, or null. Never throws.
    try {
      var raw = localStorage.getItem(MEM_PREFIX + location.hostname);
      if (!raw) return null;
      var o = JSON.parse(raw);
      return (o && o.remember) ? o : null;
    } catch (e) {
      return null;
    }
  }

  /* --------------------------------- registry -------------------------------- */
  var managed = new WeakSet();      // videos already handled
  var controllers = new WeakMap();  // video -> VideoController
  var allControllers = new Set();    // for repositioning on scroll/resize
  var pendingSmall = new Set();      // videos skipped for being too small (retried on later scans)

  function repositionAll() {
    try {
      allControllers.forEach(function (c) { c.positionOverlay(); });
    } catch (e) { /* defensive */ }
  }

  /* ------------------------------- controller -------------------------------- */
  function VideoController(video) {
    this.video = video;
    this.zoom = MIN_ZOOM;
    this.tx = 0;   // translate X in client px (applied after scale: p' = z*p + t)
    this.ty = 0;
    this.fit = 'contain';
    this.presetId = 'fit';
    this.lastZoom = 2;   // last zoom > 1, for double-tap toggle
    this.memOn = false;

    this._pinch = null;        // active pinch gesture state
    this._pan = null;          // active pan gesture state
    this._lastTap = null;      // previous single tap, for double-tap detection
    this._tapCand = null;      // candidate first tap position
    this._dblTapPending = null;
    this._fadeTimer = 0;

    // Remember original inline styles so destroy() restores the page exactly.
    var s = video.style;
    this._orig = {
      transform: s.transform, transformOrigin: s.transformOrigin,
      objectFit: s.objectFit, touchAction: s.touchAction
    };

    this._buildOverlay();
    this._bindEvents();
    this._loadMemory();
    this.apply();
    this.positionOverlay();
    controllers.set(video, this);
  }

  /* ----- transform + framing ----- */

  // Untransformed (layout) box origin in client coordinates. With
  // transform-origin: 0 0 and transform: translate(tx,ty) scale(z), the
  // rendered box origin is (ux + tx, uy + ty), so ux = rect.left - tx.
  VideoController.prototype._origin = function () {
    var r = this.video.getBoundingClientRect();
    return {
      x: r.left - this.tx,
      y: r.top - this.ty,
      w: this.video.offsetWidth,
      h: this.video.offsetHeight
    };
  };

  // Keep the scaled video covering its layout box: never pan into empty space.
  VideoController.prototype._clampPan = function () {
    var w = this.video.offsetWidth || 0;
    var h = this.video.offsetHeight || 0;
    var mx = Math.max(0, (this.zoom - 1) * w);
    var my = Math.max(0, (this.zoom - 1) * h);
    this.tx = clamp(this.tx, -mx, 0);
    this.ty = clamp(this.ty, -my, 0);
  };

  VideoController.prototype.apply = function () {
    var v = this.video;
    try {
      v.style.transformOrigin = '0 0';
      v.style.transform =
        'translate(' + this.tx + 'px,' + this.ty + 'px) scale(' + this.zoom + ')';
      v.style.objectFit = this.fit;
      // When zoomed, let the page still scroll from the video but disable the
      // browser's own pinch-zoom over it; at 1x leave touch handling alone.
      v.style.touchAction = this.zoom > MIN_ZOOM ? 'pan-x pan-y' : '';
    } catch (e) { /* defensive */ }
    this._updateChrome();
  };

  // Zoom to z, keeping the layout point under client (cx, cy) stationary.
  VideoController.prototype.setZoom = function (z, cx, cy) {
    z = clamp(z, MIN_ZOOM, MAX_ZOOM);
    var o = this._origin();
    if (cx == null || cy == null) { cx = o.x + o.w / 2; cy = o.y + o.h / 2; }
    var z0 = this.zoom;
    if (z0 <= 0) z0 = MIN_ZOOM;
    var lx = (cx - o.x - this.tx) / z0;
    var ly = (cy - o.y - this.ty) / z0;
    this.zoom = z;
    this.tx = (cx - o.x) - z * lx;
    this.ty = (cy - o.y) - z * ly;
    if (z === MIN_ZOOM) { this.tx = 0; this.ty = 0; }
    this._clampPan();
    if (z > MIN_ZOOM) this.lastZoom = z;
    this.presetId = null; // manual zoom -> "Custom" in the preset cycler
    this.apply();
    this._persist();
  };

  VideoController.prototype.applyPreset = function (p) {
    this.zoom = p.zoom;
    this.fit = p.fit;
    this.tx = 0; this.ty = 0;
    this.presetId = p.id;
    if (p.zoom > MIN_ZOOM) this.lastZoom = p.zoom;
    this.apply();
    this._persist();
  };

  VideoController.prototype.cyclePreset = function () {
    var idx = -1;
    for (var i = 0; i < PRESETS.length; i++) {
      if (PRESETS[i].id === this.presetId) { idx = i; break; }
    }
    this.applyPreset(PRESETS[(idx + 1) % PRESETS.length]);
  };

  VideoController.prototype.reset = function () {
    this.applyPreset(PRESETS[0]); // exact Fit
  };

  VideoController.prototype.toggleZoom = function (x, y) {
    if (this.zoom > MIN_ZOOM + 0.0001) {
      this.zoom = MIN_ZOOM; this.tx = 0; this.ty = 0;
      this.fit = 'contain'; this.presetId = 'fit';
      this.apply();
      this._persist();
    } else {
      this.setZoom(this.lastZoom || 2, x, y);
    }
  };

  /* ----- per-site memory ----- */

  VideoController.prototype._loadMemory = function () {
    var m = readMemory();
    if (m) {
      this.memOn = true;
      if (typeof m.zoom === 'number' && m.zoom > MIN_ZOOM) {
        this.zoom = clamp(m.zoom, MIN_ZOOM, MAX_ZOOM);
        this.lastZoom = this.zoom;
      }
      if (typeof m.fit === 'string') this.fit = m.fit;
      this.presetId = (typeof m.presetId === 'string') ? m.presetId : null;
      this.tx = 0; this.ty = 0; // always start centred; pan is not persisted
    }
  };

  VideoController.prototype._persist = function () {
    if (!this.memOn) return;
    try {
      localStorage.setItem(MEM_PREFIX + location.hostname, JSON.stringify({
        remember: true,
        zoom: this.zoom,
        fit: this.fit,
        presetId: this.presetId
      }));
    } catch (e) { /* storage may be unavailable; not fatal */ }
  };

  VideoController.prototype._toggleMemory = function () {
    this.memOn = !this.memOn;
    try {
      if (this.memOn) {
        this._persist();
      } else {
        localStorage.removeItem(MEM_PREFIX + location.hostname);
      }
    } catch (e) { /* defensive */ }
    this._updateChrome();
  };

  /* ----- overlay UI ----- */

  VideoController.prototype._buildOverlay = function () {
    var self = this;
    var root = document.createElement('div');
    root.className = 'pvt-root';

    var bar = document.createElement('div');
    bar.className = 'pvt-bar';

    function mkBtn(label, act, cls, title) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'pvt-btn' + (cls ? ' ' + cls : '');
      b.textContent = label;
      b.setAttribute('data-act', act);
      if (title) b.title = title;
      return b;
    }

    bar.appendChild(mkBtn('\u2212', 'zout', '', 'Zoom out'));
    bar.appendChild(mkBtn('+', 'zin', '', 'Zoom in'));
    this._presetBtn = mkBtn('Fit', 'preset', 'pvt-preset', 'Cycle framing preset');
    bar.appendChild(this._presetBtn);
    bar.appendChild(mkBtn('\u27F2', 'reset', '', 'Reset to Fit'));
    this._memBtn = mkBtn('\u2606', 'mem', 'pvt-mem', 'Remember zoom for this site');
    bar.appendChild(this._memBtn);

    var fab = document.createElement('button');
    fab.type = 'button';
    fab.className = 'pvt-fab';
    fab.setAttribute('aria-label', 'Video zoom controls');
    fab.title = 'Video zoom controls';
    this._badge = document.createElement('span');
    this._badge.className = 'pvt-badge';
    fab.appendChild(this._badge);

    root.appendChild(bar);
    root.appendChild(fab);
    document.documentElement.appendChild(root);

    this._root = root;
    this._bar = bar;
    this._fab = fab;

    fab.addEventListener('click', function () {
      if (bar.classList.contains('pvt-open')) self._hideBar();
      else self._showBar();
    });

    bar.addEventListener('click', function (e) {
      var btn = e.target && e.target.closest ? e.target.closest('[data-act]') : null;
      if (!btn) return;
      var act = btn.getAttribute('data-act');
      var o = self._origin();
      var cx = o.x + o.w / 2, cy = o.y + o.h / 2;
      if (act === 'zin') self.setZoom(self.zoom * ZOOM_STEP, cx, cy);
      else if (act === 'zout') self.setZoom(self.zoom / ZOOM_STEP, cx, cy);
      else if (act === 'preset') self.cyclePreset();
      else if (act === 'reset') self.reset();
      else if (act === 'mem') self._toggleMemory();
      self._pokeFade();
    });

    // Any interaction with the bar keeps it alive.
    bar.addEventListener('pointerdown', function () { self._pokeFade(); }, { passive: true });
    bar.addEventListener('touchstart', function () { self._pokeFade(); }, { passive: true });
  };

  VideoController.prototype._showBar = function () {
    this._bar.classList.add('pvt-open');
    this._pokeFade();
  };

  VideoController.prototype._hideBar = function () {
    this._bar.classList.remove('pvt-open');
    if (this._fadeTimer) { clearTimeout(this._fadeTimer); this._fadeTimer = 0; }
  };

  VideoController.prototype._pokeFade = function () {
    var self = this;
    if (this._fadeTimer) clearTimeout(this._fadeTimer);
    this._fadeTimer = setTimeout(function () { self._hideBar(); }, FADE_MS);
  };

  VideoController.prototype._updateChrome = function () {
    try {
      var z = this.zoom;
      var label = (Math.round(z * 100) / 100).toString() + '\u00D7';
      this._badge.textContent = label;
      var p = this.presetId ? presetById(this.presetId) : null;
      this._presetBtn.textContent = p ? p.label : 'Custom';
      this._memBtn.textContent = this.memOn ? '\u2605' : '\u2606';
      if (this.memOn) this._memBtn.classList.add('pvt-on');
      else this._memBtn.classList.remove('pvt-on');
    } catch (e) { /* defensive */ }
  };

  // Bottom-right of the video's layout box, in client coordinates.
  VideoController.prototype.positionOverlay = function () {
    try {
      var v = this.video;
      if (!v.isConnected) { this.destroy(); return; }
      var w = v.offsetWidth, h = v.offsetHeight;
      if (w <= 0 || h <= 0) { this._root.style.display = 'none'; return; }
      var r = v.getBoundingClientRect();
      if (r.bottom < 0 || r.top > window.innerHeight ||
          r.right < 0 || r.left > window.innerWidth) {
        this._root.style.display = 'none';
        return;
      }
      this._root.style.display = '';
      var ux = r.left - this.tx;
      var uy = r.top - this.ty;
      // PYREVIXEN_CENTER_RIGHT: Position at video's right edge, vertical center
      // (avoids covering player's bottom controls)
      this._root.style.left = (ux + w - 8) + 'px';
      this._root.style.top = (uy + h / 2) + 'px';
    } catch (e) { /* defensive */ }
  };

  /* ----- touch gestures ----- */

  VideoController.prototype._bindEvents = function () {
    var self = this;
    var v = this.video;
    // Non-passive: we must be able to preventDefault, but we only do so when
    // actually intercepting (zoomed pan, or two fingers down). At 1x, single
    // finger touches are left alone so page scroll keeps working.
    this._onTS = function (e) { self._touchStart(e); };
    this._onTM = function (e) { self._touchMove(e); };
    this._onTE = function (e) { self._touchEnd(e); };
    this._onTC = function () { self._pinch = null; self._pan = null; self._dblTapPending = null; };
    v.addEventListener('touchstart', this._onTS, { passive: false });
    v.addEventListener('touchmove', this._onTM, { passive: false });
    v.addEventListener('touchend', this._onTE, { passive: true });
    v.addEventListener('touchcancel', this._onTC, { passive: true });
  };

  VideoController.prototype._touchStart = function (e) {
    try {
      var t = e.touches;
      if (t.length === 2) {
        // Two fingers down: take over the gesture for pinch-to-zoom.
        e.preventDefault();
        var o = this._origin();
        var m = touchMid(t[0], t[1]);
        var z0 = this.zoom > 0 ? this.zoom : MIN_ZOOM;
        this._pinch = {
          d0: touchDist(t[0], t[1]),
          z0: z0,
          ux: o.x,               // untransformed box origin (client px), cached
          uy: o.y,
          lx: (m.x - o.x - this.tx) / z0,  // layout point under the midpoint
          ly: (m.y - o.y - this.ty) / z0
        };
        this._pan = null;
        this._dblTapPending = null;
        this._lastTap = null;
      } else if (t.length === 1) {
        var now = (typeof performance !== 'undefined' && performance.now) ?
          performance.now() : Date.now();
        var lt = this._lastTap;
        if (this.zoom <= MIN_ZOOM + 0.0001 && lt &&
            (now - lt.t) < DBL_TAP_MS &&
            Math.hypot(t[0].clientX - lt.x, t[0].clientY - lt.y) < DBL_TAP_PX) {
          // Second tap of a double-tap: take over so the site's own
          // double-tap action (e.g. seek) does not also fire.
          e.preventDefault();
          this._dblTapPending = { x: t[0].clientX, y: t[0].clientY };
          this._lastTap = null;
          this._tapCand = null;
        } else if (this.zoom > MIN_ZOOM + 0.0001) {
          // Zoomed: arm a potential pan. Taps (no drag) are NOT intercepted,
          // so the site's tap-to-play/pause keeps working.
          this._pan = {
            sx: t[0].clientX, sy: t[0].clientY,
            tx: this.tx, ty: this.ty, moved: false
          };
        } else {
          this._tapCand = { x: t[0].clientX, y: t[0].clientY };
        }
      }
    } catch (err) { /* defensive */ }
  };

  VideoController.prototype._touchMove = function (e) {
    try {
      var t = e.touches;
      if (this._pinch && t.length === 2) {
        e.preventDefault();
        var p = this._pinch;
        var d1 = touchDist(t[0], t[1]);
        if (p.d0 > 0 && d1 > 0) {
          var z1 = clamp(p.z0 * d1 / p.d0, MIN_ZOOM, MAX_ZOOM);
          var m = touchMid(t[0], t[1]);
          this.zoom = z1;
          // Keep the original layout point under the moving midpoint.
          this.tx = (m.x - p.ux) - z1 * p.lx;
          this.ty = (m.y - p.uy) - z1 * p.ly;
          if (z1 === MIN_ZOOM) { this.tx = 0; this.ty = 0; }
          this._clampPan();
          this.presetId = null;
          this.apply();
        }
      } else if (this._pan && t.length === 1) {
        // Zoomed single-finger drag: our pan owns it (page scroll is reached
        // via taps / drags that start outside the video).
        e.preventDefault();
        var dx = t[0].clientX - this._pan.sx;
        var dy = t[0].clientY - this._pan.sy;
        if (!this._pan.moved && Math.hypot(dx, dy) > PAN_THRESHOLD_PX) {
          this._pan.moved = true;
        }
        if (this._pan.moved) {
          this.tx = this._pan.tx + dx;
          this.ty = this._pan.ty + dy;
          this._clampPan();
          this.apply();
        }
      }
      // At 1x with one finger: deliberately no preventDefault — page scroll
      // and the site's own touch handling keep working untouched.
    } catch (err) { /* defensive */ }
  };

  VideoController.prototype._touchEnd = function (e) {
    try {
      var t = e.touches;
      if (this._pinch) {
        if (t.length < 2) {
          if (this.zoom > MIN_ZOOM) this.lastZoom = this.zoom;
          this._pinch = null;
          this._persist();
          // A finger left down after pinching becomes a pan if still zoomed.
          if (t.length === 1 && this.zoom > MIN_ZOOM + 0.0001) {
            this._pan = {
              sx: t[0].clientX, sy: t[0].clientY,
              tx: this.tx, ty: this.ty, moved: false
            };
          }
        }
        return;
      }
      if (this._pan) {
        this._pan = null;
        this._persist();
        return;
      }
      if (this._dblTapPending) {
        var p = this._dblTapPending;
        this._dblTapPending = null;
        this.toggleZoom(p.x, p.y);
        return;
      }
      // Record single taps so the next tap can complete a double-tap.
      if (this._tapCand && e.changedTouches && e.changedTouches.length >= 1) {
        this._lastTap = {
          t: (typeof performance !== 'undefined' && performance.now) ?
            performance.now() : Date.now(),
          x: this._tapCand.x, y: this._tapCand.y
        };
        this._tapCand = null;
      }
    } catch (err) { /* defensive */ }
  };

  VideoController.prototype.destroy = function () {
    try {
      var v = this.video;
      v.removeEventListener('touchstart', this._onTS);
      v.removeEventListener('touchmove', this._onTM);
      v.removeEventListener('touchend', this._onTE);
      v.removeEventListener('touchcancel', this._onTC);
      // Restore the page exactly as we found it.
      v.style.transform = this._orig.transform;
      v.style.transformOrigin = this._orig.transformOrigin;
      v.style.objectFit = this._orig.objectFit;
      v.style.touchAction = this._orig.touchAction;
      if (this._fadeTimer) clearTimeout(this._fadeTimer);
      if (this._root && this._root.parentNode) {
        this._root.parentNode.removeChild(this._root);
      }
    } catch (e) { /* defensive */ }
    controllers.delete(this.video);
    managed.delete(this.video);
    allControllers.delete(this);
    pendingSmall.delete(this.video);
  };

  /* ------------------------------ attach / scan ------------------------------ */

  function maybeAttach(video) {
    try {
      if (!video || video.tagName !== 'VIDEO') return;
      if (managed.has(video)) return;
      if (!video.isConnected) return;
      var w = video.offsetWidth, h = video.offsetHeight;
      if (w < MIN_SIZE || h < MIN_SIZE) {
        // Small video (ad/thumbnail): only attach if per-site memory already
        // holds a zoom for this host — i.e. the user explicitly zoomed here.
        var mem = readMemory();
        if (!(mem && typeof mem.zoom === 'number' && mem.zoom > MIN_ZOOM + 0.0001)) {
          pendingSmall.add(video);
          return;
        }
      }
      pendingSmall.delete(video);
      managed.add(video);
      var c = new VideoController(video);
      allControllers.add(c);
    } catch (e) { /* defensive */ }
  }

  function scan(root) {
    try {
      var vids = root.querySelectorAll ? root.querySelectorAll('video') : [];
      for (var i = 0; i < vids.length; i++) maybeAttach(vids[i]);
      // Retry videos that were too small on earlier scans (late layout, etc.).
      if (pendingSmall.size) {
        var retry = Array.from(pendingSmall);
        for (var j = 0; j < retry.length; j++) {
          if (retry[j].isConnected) maybeAttach(retry[j]);
          else pendingSmall.delete(retry[j]);
        }
      }
    } catch (e) { /* defensive */ }
  }

  function boot() {
    try {
      scan(document);

      var observer = new MutationObserver(function (mutations) {
        try {
          for (var i = 0; i < mutations.length; i++) {
            var m = mutations[i];
            var added = m.addedNodes;
            for (var a = 0; a < added.length; a++) {
              var n = added[a];
              if (!n || n.nodeType !== 1) continue;
              if (n.tagName === 'VIDEO') {
                maybeAttach(n);
              } else if (n.querySelectorAll) {
                var vids = n.querySelectorAll('video');
                for (var k = 0; k < vids.length; k++) maybeAttach(vids[k]);
              }
            }
            var removed = m.removedNodes;
            for (var r = 0; r < removed.length; r++) {
              var rn = removed[r];
              if (!rn || rn.nodeType !== 1) continue;
              var doomed = [];
              if (rn.tagName === 'VIDEO') doomed.push(rn);
              else if (rn.querySelectorAll) {
                var rv = rn.querySelectorAll('video');
                for (var q = 0; q < rv.length; q++) doomed.push(rv[q]);
              }
              for (var d = 0; d < doomed.length; d++) {
                var c = controllers.get(doomed[d]);
                if (c) c.destroy();
              }
            }
          }
        } catch (e) { /* defensive */ }
      });
      observer.observe(document.documentElement, { childList: true, subtree: true });

      document.addEventListener('scroll', repositionAll, { capture: true, passive: true });
      window.addEventListener('resize', repositionAll, { passive: true });

      // HTML5 fullscreen: the video element stays in the DOM, but layout and
      // the overlay anchor change — rescan and reposition.
      // In fullscreen, overlays must be moved into the fullscreen element
      // to be visible (document.documentElement is hidden behind fullscreen).
      function onFsChange() {
        var fsEl = document.fullscreenElement || document.webkitFullscreenElement;
        allControllers.forEach(function (c) {
          if (c._root) {
            if (fsEl) {
              // Move overlay into fullscreen element
              if (c._root.parentNode !== fsEl) {
                fsEl.appendChild(c._root);
              }
            } else {
              // Move back to document
              if (c._root.parentNode !== document.documentElement) {
                document.documentElement.appendChild(c._root);
              }
            }
          }
        });
        scan(document);
        repositionAll();
      }
      document.addEventListener('fullscreenchange', onFsChange);
      document.addEventListener('webkitfullscreenchange', onFsChange);

      // Late-loading players: one more sweep after layout settles.
      setTimeout(function () { scan(document); repositionAll(); }, 2000);
    } catch (e) { /* defensive: never break the host page */ }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
