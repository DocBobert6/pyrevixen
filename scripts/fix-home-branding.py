#!/usr/bin/env python3
"""
fix-home-branding.py — PyreVixen: replace Firefox wordmark/logo on home screen.

Problem: The home screen shows the Firefox logo and "Firefox" wordmark images,
not PyreVixen branding. The 010 patch changed the `firefox` string but the
home screen uses image drawables (ic_wordmark_logo, ic_wordmark_text_normal).

Fix: Modify WordmarkAndLogo.kt to display "PyreVixen" as text with the
PyreVixen launcher icon, instead of the Firefox image assets.

Idempotent: safe to re-run.
"""

import sys
from pathlib import Path

def main():
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not source_dir or not source_dir.is_dir():
        print(f"ERROR: invalid source dir: {source_dir}", file=sys.stderr)
        sys.exit(1)

    wordmark_file = source_dir / "mobile/android/fenix/app/src/main/java/org/mozilla/fenix/home/ui/WordmarkAndLogo.kt"
    content = wordmark_file.read_text(encoding="utf-8")

    if "PYREVIXEN_BRANDING" in content:
        print("    WordmarkAndLogo.kt already fixed, skipping")
        return

    # Add necessary imports for Text composable
    old_imports = """import androidx.compose.ui.unit.dp
import org.mozilla.fenix.R"""

    new_imports = """import androidx.compose.material3.Text
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.mozilla.fenix.R"""

    if old_imports in content:
        content = content.replace(old_imports, new_imports, 1)
        print("    added Text imports")
    else:
        print("    WARNING: import pattern not found", file=sys.stderr)
        return

    # Replace the Wordmark composable to use text instead of image
    old_wordmark = """@Composable
internal fun Wordmark(color: Color?) {
    Image(
        modifier =
            Modifier.semantics {
                    testTagsAsResourceId = true
                    testTag = HOMEPAGE_WORDMARK_TEXT
                }
                .height(dimensionResource(R.dimen.wordmark_text_height)),
        painter = painterResource(getAttr(R.attr.fenixWordmarkText)),
        colorFilter = color?.let { ColorFilter.tint(it) },
        contentDescription = stringResource(R.string.app_name),
    )
}"""

    new_wordmark = """// PYREVIXEN_BRANDING: Show "PyreVixen" as text instead of Firefox wordmark image.
@Composable
internal fun Wordmark(color: Color?) {
    Text(
        text = "PyreVixen",
        color = color ?: Color.White,
        fontSize = 24.sp,
        fontWeight = FontWeight.Bold,
        modifier = Modifier.semantics {
            testTagsAsResourceId = true
            testTag = HOMEPAGE_WORDMARK_TEXT
        },
    )
}"""

    if old_wordmark in content:
        content = content.replace(old_wordmark, new_wordmark, 1)
        print("    replaced Wordmark image with PyreVixen text")
    else:
        print("    WARNING: Wordmark pattern not found", file=sys.stderr)
        return

    # Replace the Logo composable to use the launcher icon
    old_logo = """@Composable
internal fun Logo() {
    Image(
        modifier =
            Modifier.height(LOGO_HEIGHT)
                .semantics {
                    testTagsAsResourceId = true
                    testTag = HOMEPAGE_WORDMARK_LOGO
                    resourceId = R.attr.fenixWordmarkLogo
                }
                .padding(end = LOGO_PADDING),
        painter = painterResource(getAttr(R.attr.fenixWordmarkLogo)),
        contentDescription = null,
    )
}"""

    new_logo = """// PYREVIXEN_BRANDING: Use PyreVixen launcher icon instead of Firefox logo.
@Composable
internal fun Logo() {
    Image(
        modifier =
            Modifier.height(LOGO_HEIGHT)
                .semantics {
                    testTagsAsResourceId = true
                    testTag = HOMEPAGE_WORDMARK_LOGO
                }
                .padding(end = LOGO_PADDING),
        painter = painterResource(R.drawable.ic_launcher_foreground),
        contentDescription = null,
    )
}"""

    if old_logo in content:
        content = content.replace(old_logo, new_logo, 1)
        print("    replaced Logo with PyreVixen launcher icon")
    else:
        print("    WARNING: Logo pattern not found", file=sys.stderr)

    wordmark_file.write_text(content, encoding="utf-8")
    print("    fixed WordmarkAndLogo.kt")

if __name__ == "__main__":
    main()
