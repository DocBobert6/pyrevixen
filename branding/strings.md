# PyreVixen user-facing strings

Working strings for the decided name "PyreVixen". If the name ever changes,
update these together with the rename points in BRANDING.md.

```properties
app_name=PyreVixen
app_tagline=A private haven for the open web.
app_description_short=A privacy-forward Android browser with the full Firefox UI — no AI, no telemetry.
app_description_long=PyreVixen is a Fennec-based Android browser that keeps the complete Firefox interface and adds a privacy-first posture: no AI features, no telemetry, no sponsored content, no experiments. Custom video player with zoom and pan, immersive fullscreen, and your choice of homepage.
homepage_title=PyreVixen Home
private_tab_title=Private Haven
```

## Trademark hygiene

User-facing strings MUST NOT use Mozilla marks: Firefox, Mozilla, Fenix,
Fennec, Gecko, GeckoView, Pocket, or the Firefox logo. (The one exception
is factual attribution where the license or honesty requires it — e.g.
"based on Firefox 158.0" in release notes — which is nominative reference
to the upstream base, not branding.)

Internal code identifiers that reference upstream components (Maven
coordinates, class names) are not user-facing and stay as-is.
