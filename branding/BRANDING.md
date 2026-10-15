# PyreVixen branding & rename guide

**"PyreVixen" is the decided product name** (chosen 2026-10-14):
fire-and-fox lineage without touching Mozilla's trademarks, package id
`org.pyrevixen.browser`. The table below is kept so a future rename —
which is still possible before the first public release — stays a small,
mechanical job. Renaming *after* release costs every user a fresh install
(see below).

## Exact one-line rename points

A rename touches exactly these spots, one line each. Nothing else carries
the name.

| # | File | Line / field |
|---|------|--------------|
| 1 | `patches/010-branding.patch` | patch header (`Subject:`) and every `s/PyreVixen/...` hunk |
| 2 | `branding/strings.md` | `app_name`, `app_tagline`, description strings |
| 3 | `patches/010-branding.patch` | `applicationId "org.pyrevixen.browser"` (the app's package id) |
| 4 | `templates/release-notes.md` | title line `# PyreVixen {{VERSION}}` |
| 5 | `README.md` | title and intro paragraph |
| 6 | `branding/icon-master.svg` | only if the new name needs a monogram (the placeholder mark has none — safe) |
| 7 | `scripts/build.sh`, `scripts/release.sh` | the `pyrevixen-` APK filename prefix (keep or change consistently) |
| 8 | `.github/workflows/build.yml` | release `name:` and the `pyrevixen-` artifact prefix (optional, cosmetic) |

## How to rename safely

1. **Pick the name.** Then sanity-check it: web-search the name + "browser"
   and "trademark" for collisions. Do NOT pick anything containing Mozilla
   marks (Firefox, Mozilla, Fenix, Fennec, Gecko, Pocket) — see Trademark
   hygiene below.
2. **Search, don't guess.** Run `grep -ri "pyrevixen" --include='*' .`
   (excluding `.source/`, `dist/`, `release/`) and change ONLY the files in
   the table above. Stray references in comments or docs are harmless but
   sloppy — fix them while you're there.
3. **applicationId is identity.** Changing `org.pyrevixen.browser` makes
   Android treat it as a *different app*: users must uninstall/reinstall,
   and tabs, logins, and settings do NOT migrate. Decide the applicationId
   at the same time as the name, ideally before the first release.
4. **Icons.** If the new name suggests a monogram, redraw
   `branding/icon-master.svg` (keep the palette in `colours.md`) and
   re-export every density below.
5. **Re-verify.** A rename edits patch 010, so re-run the full
   [TESTING.md](../TESTING.md) gate — no gate, no release.

## Launcher icons

`branding/icon-master.svg` is the 512×512 master (original geometric mark:
fox-ear hexagon in PyreVixen Ember on Haven Night — NOT the Firefox logo, no
Mozilla marks). Export PNGs at these Android densities:

| Density | PNG size |
|---------|----------|
| mdpi    | 48×48    |
| hdpi    | 72×72    |
| xhdpi   | 96×96    |
| xxhdpi  | 144×144  |
| xxxhdpi | 192×192  |

(Export with e.g. `rsvg-convert -w 192 icon-master.svg -o ic_launcher-xxxhdpi.png`.
The 512×512 master itself is the Play listing icon.)

**Adaptive icons (API 26+):** provide a foreground layer at 108×108dp with
all artwork inside the 72dp-diameter safe circle, over a background layer of
solid Haven Night `#101828` (see `colours.md`). The SVG's ember/gold mark on
the dark rounded square works as the foreground; use the flat `#101828` as
the background.

## Trademark hygiene

- Mozilla's trademarks (Firefox, Mozilla, Fenix, Fennec, Gecko, GeckoView,
  Pocket, the Firefox logo) are REMOVED from all product-facing surfaces by
  patch 010. Our own additions ship under MPL 2.0 (see LICENSE).
- Factual references to the upstream base in docs and release notes
  ("based on Firefox 158.0") are nominative — they describe what the code
  *is*, they don't brand the product — and they stay.
