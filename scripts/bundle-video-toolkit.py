#!/usr/bin/env python3
"""
bundle-video-toolkit.py — PyreVixen: bundle video toolkit WebExtension.

Copies the video toolkit WebExtension files into the Fenix assets directory
so they're bundled into the APK and installed via BuiltInWebExtensionController.

Source: video-toolkit/ (manifest.json, content.js, controls.css)
Dest: mobile/android/fenix/app/src/main/assets/extensions/video-toolkit/

Idempotent: safe to re-run.
"""

import shutil
import sys
from pathlib import Path

def main():
    repo_root = Path(__file__).parent.parent
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    src_ext_dir = repo_root / "video-toolkit"
    dest_ext_dir = source_dir / "mobile/android/fenix/app/src/main/assets/extensions/video-toolkit"
    
    if not src_ext_dir.is_dir():
        print(f"ERROR: video-toolkit source not found: {src_ext_dir}", file=sys.stderr)
        sys.exit(1)

    dest_ext_dir.mkdir(parents=True, exist_ok=True)
    
    for filename in ["manifest.json", "content.js", "controls.css"]:
        src = src_ext_dir / filename
        dest = dest_ext_dir / filename
        if src.exists():
            shutil.copy2(src, dest)
            print(f"    copied {filename}")
        else:
            print(f"    WARNING: {filename} not found in {src_ext_dir}", file=sys.stderr)

    print(f"    bundled to {dest_ext_dir}")

if __name__ == "__main__":
    main()
