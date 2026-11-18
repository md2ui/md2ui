"""
Tests for an image with no picture: ``![alt]()``, or ``![alt]( )``.

An empty source is how an author writes "this item has no picture" and keeps
the item's place in a run of pictures. Pinned here:

  * the grouper reads both spellings as an ``image``, never as text that draws
    its own Markdown;
  * the box measures exactly as a picture box with the same params, and an
    item that carries one stays in its run, so the run's ratio reaches it;
  * nothing is fetched for it, so it never counts as loading;
  * it paints a quiet empty box in the picture background: neither the loading
    placeholder, nor the broken one, nor the fallback cross and alt label.

Run with: uv run python tests/image_no_picture_tests.py
"""

import contextlib
import io
import sys
from pathlib import Path

import numpy as np
import skia  # type: ignore[import-untyped]

from md2ui import session
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_render import IMAGE_DECO_COLOR
from md2ui.pipeline.render_settings import VIEW
from md2ui.utils.image_cache import ImageCache

_THEME = Path("data/markdown/tests/THEME.md")
_KIT: list = []
_RATIO = "?md2ui.aspect_ratio=4:3"
_SPELLINGS = ("![Cacaluta Bay]()", "![Cacaluta Bay]( )")


def _kit():
    if not _KIT:
        with contextlib.redirect_stdout(io.StringIO()):
            theme = session.load_theme(_THEME)
            _KIT.extend([session.load_grouping_kit(), theme, session.load_fonts(theme)])
    return _KIT


def _scene(markdown: str, width: float = 1024.0):
    kit, theme, fonts = _kit()
    grouped = session.group_markdown(markdown, kit)
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, width)
    return scene, index


def _image_boxes(markdown: str, width: float = 1024.0):
    scene, index = _scene(markdown, width)
    return [
        b for b in scene.boxes if index.get(b.content_id, {}).get("type") == "image"
    ]


def _types(markdown: str) -> list[str]:
    kit = _kit()[0]
    grouped = session.group_markdown(markdown, kit)
    assert grouped is not None
    found, stack = [], [grouped.to_dict()]
    while stack:
        n = stack.pop()
        if not n.get("children"):
            found.append((n.get("type"), n.get("content")))
        stack.extend(n.get("children", []))
    return found


def test_an_empty_source_groups_as_an_image():
    for spelling in _SPELLINGS:
        leaves = _types(f"## Bay\n\n{spelling}\nSecluded, by boat.\n")
        assert ("image", spelling) in leaves, (spelling, leaves)
        assert not any(spelling in str(c) for t, c in leaves if t != "image"), leaves
    print("  ✓  `![alt]()` and `![alt]( )` group as an image")


def test_the_box_measures_as_a_picture_box():
    pairs = [
        ("![Bay](https://example.com/bay.jpg)", s) for s in ("![Bay]()", "![Bay]( )")
    ] + [
        (f"![Bay](https://example.com/bay.jpg{_RATIO})", f"![Bay]({_RATIO})"),
        (f"![Bay](https://example.com/bay.jpg{_RATIO})", f"![Bay]( {_RATIO})"),
    ]
    for real, empty in pairs:
        picture = _image_boxes(f"## Bay\n\n{real}\nText.\n")
        nothing = _image_boxes(f"## Bay\n\n{empty}\nText.\n")
        assert len(picture) == 1, picture
        assert [(b.width, b.height) for b in nothing] == [
            (b.width, b.height) for b in picture
        ], (empty, nothing, picture)
    print("  ✓  a box with no picture measures as a picture box with the same params")


def _run(middle: str) -> str:
    def item(picture: str, name: str) -> str:
        return f"- {picture}\n  :::1\n  **{name}**\n  A line about {name}.\n  :::2\n\n"

    return (
        "## Bays\n\n"
        + item(f"![A](https://example.com/a.jpg{_RATIO})", "A")
        + item(middle, "B")
        + item("![C](https://example.com/c.jpg)", "C")
    )


def test_an_item_with_no_picture_keeps_its_run():
    for spelling in ("![B]()", "![B]( )"):
        boxes = _image_boxes(_run(spelling))
        assert len(boxes) == 3, boxes
        ratios = [b.render_properties.get("aspect_ratio") for b in boxes]
        assert ratios == ["4:3"] * 3, (spelling, ratios)
        assert len({(b.width, b.height) for b in boxes}) == 1, boxes
    print("  ✓  an item with no picture keeps its run, and the run's ratio")


def test_nothing_is_fetched_and_nothing_loads():
    _, index = _scene(_run("![B]()"))
    images = [n for n in index.values() if n.get("type") == "image"]
    assert len(images) == 3, images
    cache = ImageCache()
    with contextlib.redirect_stdout(io.StringIO()):
        cache.fetch(index)
    assert len(cache._futures) == 2, cache._futures  # A and C, never B
    _, empty_only = _scene("## Bay\n\n![Bay]()\nText.\n")
    assert any(n.get("type") == "image" for n in empty_only.values()), empty_only
    cache = ImageCache()
    cache.fetch(empty_only)
    assert not cache._futures, cache._futures
    assert not cache.failed(""), "an empty source reads as a failure"
    print("  ✓  an empty source is never fetched and never loading")


def _sentinel(rgb: tuple[int, int, int]) -> skia.Image:
    pixels = np.zeros((8, 8, 4), dtype=np.uint8)
    pixels[:, :] = (*rgb, 255)
    return skia.Image.fromarray(pixels, colorType=skia.kRGBA_8888_ColorType)


def _mask(rgb: np.ndarray, colour) -> np.ndarray:
    return np.abs(rgb - np.array(colour)[:3]).sum(axis=2) < 6


def test_it_paints_a_quiet_empty_box():
    """The picture background fills the box; no placeholder, no cross, no
    label. The I key, which forces loading placeholders, leaves it alone: it
    is not loading."""
    from md2ui.pipeline.render_placeholders import NO_PICTURE_COLOR

    loading, broken = (255, 0, 255), (0, 255, 255)
    deco = skia.Color4f(IMAGE_DECO_COLOR)
    deco_rgb = tuple(round(c * 255) for c in (deco.fR, deco.fG, deco.fB))
    quiet = skia.Color4f(NO_PICTURE_COLOR)
    quiet_rgb = tuple(round(c * 255) for c in (quiet.fR, quiet.fG, quiet.fB))
    kit, theme, fonts = _kit()
    saved = (VIEW.placeholder_raster, VIEW.placeholder_broken, VIEW.placeholder_images)
    VIEW.placeholder_raster = _sentinel(loading)
    VIEW.placeholder_broken = _sentinel(broken)
    try:
        for spelling in _SPELLINGS:
            for forced in (False, True):
                VIEW.placeholder_images = forced
                scene, index = _scene(f"## Bay\n\n{spelling}\nSecluded.\n", 600.0)
                [box] = [
                    b
                    for b in scene.boxes
                    if index.get(b.content_id, {}).get("type") == "image"
                ]
                image = session.render_image(
                    scene, index, theme, fonts, ImageCache(), {}, 1.0
                )
                rgb = image.toarray(colorType=skia.kRGBA_8888_ColorType)
                rgb = rgb[:, :, :3].astype(int)
                assert not _mask(rgb, loading).any(), (spelling, forced, "loading")
                assert not _mask(rgb, broken).any(), (spelling, forced, "broken")
                quiet_px = _mask(rgb, quiet_rgb)
                # The box: the rows and columns the fill spans, not a glyph's
                # anti-aliased edge that happens to pass through its colour.
                ys = np.nonzero(quiet_px.sum(axis=1) > 100)[0]
                xs = np.nonzero(quiet_px.sum(axis=0) > 100)[0]
                inside = rgb[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
                assert not _mask(inside, deco_rgb).any(), (spelling, forced, "cross")
                filled = int(quiet_px.sum())
                assert filled >= 0.95 * box.width * box.height, (
                    spelling,
                    forced,
                    filled,
                    box.width * box.height,
                )
    finally:
        VIEW.placeholder_raster, VIEW.placeholder_broken, VIEW.placeholder_images = (
            saved
        )
    print("  ✓  an empty source paints a quiet box in the picture background")


def test_the_quiet_box_fills_its_box_whatever_the_fit():
    """A picture left out has nothing to fit: with
    ``fit=contain``, ``fit=cover`` or no fit, the quiet box fills the whole box
    its ratio gives, never a square contained in it."""
    from md2ui.pipeline.render_placeholders import NO_PICTURE_COLOR

    quiet = skia.Color4f(NO_PICTURE_COLOR)
    quiet_rgb = tuple(round(c * 255) for c in (quiet.fR, quiet.fG, quiet.fB))
    kit, theme, fonts = _kit()
    for fit in ("&md2ui.fit=contain", "&md2ui.fit=cover", ""):
        source = f"?md2ui.aspect_ratio=16:9{fit}"
        scene, index = _scene(f"## Logo\n\n![Logo]({source})\n", 600.0)
        [box] = [
            b for b in scene.boxes if index.get(b.content_id, {}).get("type") == "image"
        ]
        image = session.render_image(scene, index, theme, fonts, ImageCache(), {}, 1.0)
        rgb = image.toarray(colorType=skia.kRGBA_8888_ColorType)[:, :, :3].astype(int)
        filled = int(_mask(rgb, quiet_rgb).sum())
        assert filled >= 0.95 * box.width * box.height, (
            fit,
            filled,
            box.width * box.height,
        )
    print("  ✓  the quiet box fills its box whatever the fit")


TESTS = [
    test_an_empty_source_groups_as_an_image,
    test_the_box_measures_as_a_picture_box,
    test_an_item_with_no_picture_keeps_its_run,
    test_nothing_is_fetched_and_nothing_loads,
    test_it_paints_a_quiet_empty_box,
    test_the_quiet_box_fills_its_box_whatever_the_fit,
]

if __name__ == "__main__":
    print("Image No Picture Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    sys.exit(1 if failed else 0)
