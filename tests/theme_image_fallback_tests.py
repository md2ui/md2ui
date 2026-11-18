"""
Tests for a THEME.md background image that fails to load.

Declaring a background image chooses the colours over it
(``On background color: image``) whether or not the image arrives, so a failed
one must not leave that text on a bare fill. Pinned here:

  * a failed image paints the broken placeholder in its place, at every theme
    site that can carry one, cover-fitted and clipped as the image would be;
  * a remote image a server never fetched (fetching off) has not failed and
    paints nothing;
  * a photo card whose own photo is still loading, over a theme fallback that
    failed, shows the loading placeholder; the broken one only once its own
    photo fails. A fallback that loaded stands in while the photo is in flight.

Run with: uv run python tests/theme_image_fallback_tests.py
"""

import tempfile
from pathlib import Path

import numpy as np
import skia  # type: ignore[import-untyped]

from md2ui import session
from md2ui.pipeline import layout_render as LR
from md2ui.pipeline import render_element_paint as REP
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.render_settings import VIEW
from md2ui.pipeline.theme import Theme, parse_theme
from md2ui.utils.fetch_policy import POLICY
from md2ui.utils.image_cache import ImageCache

# Sentinels the corpus never paints, standing in for the placeholder assets
# and for a theme image that loads, so their pixels can be counted exactly.
_LOADING = (255, 0, 255)
_BROKEN = (0, 255, 255)
_LOADED = (255, 255, 0)

# Failures that need no network: a missing local file, and a refused port.
_MISSING_FILE = "/nonexistent/md2ui-missing-theme.png"
_REFUSED = "http://127.0.0.1:9/md2ui-missing-theme.png"
# Never resolves (RFC 6761); only ever asked for with fetching off.
_UNFETCHED = "https://example.invalid/section-photo.png"
_MISSING_PHOTO = "file:///nonexistent/md2ui-missing-photo.png"


def _sentinel(rgb: tuple[int, int, int]) -> skia.Image:
    pixels = np.zeros((8, 8, 4), dtype=np.uint8)
    pixels[:, :] = (*rgb, 255)
    return skia.Image.fromarray(pixels, colorType=skia.kRGBA_8888_ColorType)


def _mask(rgb: np.ndarray, colour: tuple[int, int, int]) -> np.ndarray:
    return np.abs(rgb - np.array(colour)).sum(axis=2) < 6


def _paint(
    markdown: str, theme: Theme, *, remote: bool = True, wait: bool = True
) -> np.ndarray:
    """Render *markdown*, with the theme images resolved as a shell does:
    placeholders first, then the background images, under one fetch policy."""
    root = session.group_markdown(markdown, session.load_grouping_kit())
    assert root is not None
    root, index = session.prepare(root, theme)
    fonts = session.load_fonts(theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 400.0)
    saved = VIEW.placeholder_raster, VIEW.placeholder_broken, POLICY.remote
    VIEW.placeholder_raster = _sentinel(_LOADING)
    VIEW.placeholder_broken = _sentinel(_BROKEN)
    POLICY.remote = remote
    try:
        cache = ImageCache()
        if wait:
            session.wait_for_images(cache, index)
        backgrounds = LR.load_background_images(theme)
        image = session.render_image(
            scene, index, theme, fonts, cache, backgrounds, 1.0
        )
    finally:
        VIEW.placeholder_raster, VIEW.placeholder_broken, POLICY.remote = saved
    return image.toarray(colorType=skia.kRGBA_8888_ColorType)[:, :, :3].astype(int)


def _section_theme(source: str) -> Theme:
    theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    theme.sections[2].bg_image = source
    return theme


_SECTION = "## Trip notes\n\nThis section's background image fails to load.\n"


def test_a_failed_section_image_paints_the_broken_placeholder():
    """A heading level's image that fails, local or
    remote, paints the broken placeholder under the text, not nothing."""
    for source in (_MISSING_FILE, _REFUSED):
        rgb = _paint(_SECTION, _section_theme(source))
        broken = int(_mask(rgb, _BROKEN).sum())
        assert broken > 2000, f"{source}: only {broken} broken placeholder pixels"
    print("  ✓  a failed section image paints the broken placeholder")


def test_an_unfetched_section_image_paints_nothing():
    """With fetching off nothing was asked for, so nothing failed."""
    rgb = _paint(_SECTION, _section_theme(_UNFETCHED), remote=False)
    assert not _mask(rgb, _BROKEN).any(), "an unfetched image drew as broken"
    assert not _mask(rgb, _LOADING).any(), "an unfetched image drew as loading"
    print("  ✓  a theme image never fetched paints no placeholder")


def test_every_theme_image_site_takes_the_placeholder():
    """One rule for every site THEME_GUIDE §Backgrounds lists: the decoded
    slots, the element sources, and the sites decoded at paint."""
    theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    for style in (
        theme.root,
        theme.image_cards,
        theme.unordered_lists,
        theme.task_lists,
        theme.numbered_lists,
        theme.quotes,
        theme.tables.header,
        theme.tables.cells,
        theme.tables.table,
        theme.sections[2],
        theme.links.primary,
    ):
        style.bg_image = _MISSING_FILE
    saved = VIEW.placeholder_broken
    VIEW.placeholder_broken = broken = _sentinel(_BROKEN)
    try:
        images = LR.load_background_images(theme)
        painted = REP._style_image(_MISSING_FILE)
        bar = LR.theme_picture(_MISSING_FILE)
    finally:
        VIEW.placeholder_broken = saved
    for key in (0, -5, -6, -9, -7, -8, -2, -3, -4, 2, ("element", _MISSING_FILE)):
        assert images.get(key) is broken, f"slot {key!r}: {images.get(key)!r}"
    assert painted is broken, "a task control or chart style painted nothing"
    assert bar is broken, "a bar or chart bar painted nothing"
    print("  ✓  every theme image site takes the broken placeholder")


def _card(fallback: str, *, wait: bool) -> tuple[int, int, int]:
    theme = Theme()
    theme.image_cards.bg_image = fallback
    md = f"![\n## Payday\nGet paid early.\n]({_MISSING_PHOTO})\n"
    rgb = _paint(md, theme, wait=wait)
    return tuple(int(_mask(rgb, c).sum()) for c in (_LOADING, _BROKEN, _LOADED))  # type: ignore[return-value]


def test_a_card_over_a_failed_fallback_loads_then_breaks():
    """Nothing has failed for a card whose photo is in flight: it shows the
    loading placeholder over a failed fallback, the broken one once its own
    photo fails."""
    loading, broken, _ = _card(_MISSING_FILE, wait=False)
    assert loading > 2000 and broken == 0, f"in flight: {loading=} {broken=}"
    loading, broken, _ = _card(_MISSING_FILE, wait=True)
    assert broken > 2000 and loading == 0, f"failed: {loading=} {broken=}"
    print("  ✓  a card over a failed fallback shows loading, then broken")


def test_a_card_over_a_loaded_fallback_is_unchanged():
    """A fallback that loaded still stands in while the photo is in flight."""
    path = Path(tempfile.gettempdir()) / "md2ui-theme-fallback-loaded.png"
    path.write_bytes(bytes(_sentinel(_LOADED).encodeToData()))
    loading, broken, loaded = _card(str(path), wait=False)
    assert loaded > 2000 and loading == 0 and broken == 0, (loading, broken, loaded)
    print("  ✓  a card over a loaded fallback shows the fallback while it waits")


def test_a_remote_theme_image_is_fetched_once_and_kept():
    """A theme background is kept in the disk cache document pictures share:
    fetched the first time, then the same bytes on every run, as a CDN that
    serves one photo in two encodings would otherwise change the page
    (findings/remote-image-renders-are-not-deterministic). A server reads
    neither the network nor that cache."""
    from unittest.mock import patch

    from md2ui.pipeline import render_placeholders as RP
    from md2ui.utils import image_cache
    from md2ui.utils.fetch_policy import POLICY

    jpeg = _sentinel((10, 120, 200)).encodeToData(skia.kJPEG, 90).bytes()
    url = "https://example.com/background.jpg"
    asked: list[str] = []

    def fetch(u: str) -> bytes:
        asked.append(u)
        return jpeg

    real_dir = image_cache._CACHE_DIR
    with tempfile.TemporaryDirectory() as tmp:
        image_cache._CACHE_DIR = Path(tmp)
        try:
            with patch.object(RP, "fetch_remote", fetch):
                first = RP.decode_theme_image(url)
                second = RP.decode_theme_image(url)
                was, POLICY.remote = POLICY.remote, False
                try:
                    served = RP.decode_theme_image(url)
                finally:
                    POLICY.remote = was
        finally:
            image_cache._CACHE_DIR = real_dir
    assert asked == [url], asked
    assert first is not None and second is not None
    assert first.tobytes() == second.tobytes()
    assert served is None, "a server reads no cache"
    print("  ✓  a remote theme image is fetched once and kept")


TESTS = [
    test_a_remote_theme_image_is_fetched_once_and_kept,
    test_a_failed_section_image_paints_the_broken_placeholder,
    test_an_unfetched_section_image_paints_nothing,
    test_every_theme_image_site_takes_the_placeholder,
    test_a_card_over_a_failed_fallback_loads_then_breaks,
    test_a_card_over_a_loaded_fallback_is_unchanged,
]

if __name__ == "__main__":
    print("Theme Image Fallback Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
