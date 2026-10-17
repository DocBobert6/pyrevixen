#!/usr/bin/env python3
"""
fix-video-toolkit-fullscreen.py — PyreVixen: video controls only in fullscreen.

Robert requested (2026-10-15): The video toolkit controls (FAB/buttons) should
ONLY appear when in fullscreen mode, not before. Currently they appear on all
videos.

Fix: Modify content.js positionOverlay() to hide the overlay unless the
document is in fullscreen mode (document.fullscreenElement or webkit equivalent).

Idempotent: safe to re-run.
"""

import sys
from pathlib import Path

def main():
    repo_root = Path(__file__).parent.parent
    content_js = repo_root / "video-toolkit" / "content.js"
    
    if not content_js.exists():
        print(f"ERROR: content.js not found: {content_js}", file=sys.stderr)
        sys.exit(1)

    content = content_js.read_text(encoding="utf-8")

    if "PYREVIXEN_FULLSCREEN_ONLY" in content:
        print("    content.js already fixed, skipping")
        return

    # Add fullscreen check at the start of positionOverlay
    old = """  VideoController.prototype.positionOverlay = function () {
    try {
      var v = this.video;
      if (!v.isConnected) { this.destroy(); return; }"""

    new = """  // PYREVIXEN_FULLSCREEN_ONLY: Controls only visible in fullscreen mode.
  function isFullscreen() {
    return !!(document.fullscreenElement || document.webkitFullscreenElement ||
              document.mozFullScreenElement || document.msFullscreenElement);
  }

  VideoController.prototype.positionOverlay = function () {
    try {
      // Hide controls unless in fullscreen
      if (!isFullscreen()) { this._root.style.display = 'none'; return; }
      var v = this.video;
      if (!v.isConnected) { this.destroy(); return; }"""

    if old not in content:
        print("    WARNING: positionOverlay pattern not found", file=sys.stderr)
        return

    content = content.replace(old, new, 1)
    content_js.write_text(content, encoding="utf-8")
    print("    modified content.js: controls only in fullscreen")

if __name__ == "__main__":
    main()
