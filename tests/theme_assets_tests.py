"""
Unit tests for THEME ASSET PATHS — where the files a THEME.md names are read from.

A theme names files in three places: the `## Fonts` list, an emoji `Font:`, and
any `Background image:`. A relative one resolves BESIDE THE THEME.md first, so a
theme can live in its own folder with its fonts and images, as the Claude
plugins' `theme` setting lets a user keep it anywhere on disk. When nothing is
beside the theme, the path is left as written and resolves against the working
directory — the checkout — which is also how a theme kept
elsewhere names the fonts the checkout ships.

Pinned here, through `session.load_theme` (the one entry both shells and both MCP
servers use):

  * a font, an emoji font, a root background and a button-variant background
    beside the theme all resolve to that folder;
  * a relative path with nothing beside the theme is left exactly as written;
  * a URL and an absolute path are never rewritten;
  * the resolved font actually loads — the family resolves, not a fallback.

Run with: uv run python tests/theme_assets_tests.py
"""

import tempfile
import unittest
from pathlib import Path

from md2ui import session
from md2ui.pipeline.theme_assets import resolve_asset
from md2ui.utils.font_loader import load_custom_fonts

ROOT = Path(__file__).resolve().parent.parent
INTER = ROOT / "assets" / "fonts" / "Inter_18pt-Regular.ttf"


def _theme(folder: Path, body: str) -> Path:
    path = folder / "THEME.md"
    path.write_text(body)
    return path


def test_assets_beside_the_theme_resolve_there():
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name in ("fonts/Face.ttf", "fonts/Emoji.ttf", "img/bg.png", "img/pill.png"):
            (folder / name).parent.mkdir(exist_ok=True)
            (folder / name).write_bytes(b"")
        theme = session.load_theme(
            _theme(
                folder,
                "## Fonts\n- fonts/Face.ttf\n\n"
                "## Styling & Spacing\n\n### Root\nBackground image: img/bg.png\n\n"
                "## Links\n\n### Primary\nBackground image: img/pill.png\n\n"
                "## Emoji styles\nFont: fonts/Emoji.ttf\n",
            )
        )
        assert theme.font_paths == [str(folder / "fonts/Face.ttf")], theme.font_paths
        assert theme.emojis.font_path == str(folder / "fonts/Emoji.ttf")
        assert theme.root.bg_image == str(folder / "img/bg.png"), theme.root.bg_image
        pill = theme.links.primary.bg_image
        assert pill == str(folder / "img/pill.png"), pill
    print("  ✓  fonts, emoji font and background images beside the theme resolve there")


def test_nothing_beside_the_theme_keeps_the_path():
    with tempfile.TemporaryDirectory() as tmp:
        theme = session.load_theme(
            _theme(
                Path(tmp),
                "## Fonts\n- assets/fonts/Inter_18pt-Regular.ttf\n\n"
                "## Styling & Spacing\n\n### Root\nBackground image: img/none.png\n",
            )
        )
        assert theme.font_paths == ["assets/fonts/Inter_18pt-Regular.ttf"]
        assert theme.root.bg_image == "img/none.png", theme.root.bg_image
    print("  ✓  a relative path with nothing beside the theme is left as written")


def test_urls_and_absolute_paths_are_untouched():
    with tempfile.TemporaryDirectory() as tmp:
        url = "https://example.com/Face-Regular.ttf"
        theme = session.load_theme(_theme(Path(tmp), f"## Fonts\n- {url}\n- {INTER}\n"))
        assert theme.font_paths == [url, str(INTER)], theme.font_paths
        assert resolve_asset(url, Path(tmp)) == url
    print("  ✓  URLs and absolute paths are used as written")


def test_a_font_beside_the_theme_loads():
    if not INTER.is_file():
        raise unittest.SkipTest("assets/fonts/Inter_18pt-Regular.ttf is not fetched")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "fonts").mkdir()
        (folder / "fonts" / "Inter.ttf").write_bytes(INTER.read_bytes())
        theme = session.load_theme(_theme(folder, "## Fonts\n- fonts/Inter.ttf\n"))
        loaded = load_custom_fonts(theme.font_paths)
        families = {family for family, _weight, _italic in loaded}
        assert any("inter" in family for family in families), families
    print("  ✓  a font beside the theme loads, wherever the process runs")


TESTS = [
    test_assets_beside_the_theme_resolve_there,
    test_nothing_beside_the_theme_keeps_the_path,
    test_urls_and_absolute_paths_are_untouched,
    test_a_font_beside_the_theme_loads,
]

if __name__ == "__main__":
    print("Theme Asset Path Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
