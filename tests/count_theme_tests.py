"""
Unit tests for a count's own theme parameters, ``### Count Button`` under
``## Drawing elements`` (ADR-405).

A count is a slider, so its round ➖/➕ buttons are a drawing element painted by
the drawing-element painter (``render_element_paint._paint_style``) as a slider
handle is. Pinned here, on ``data/markdown/tests/count-theme-parameters``:

  * the block parses into ``theme.datapoints.counts`` (its paint and its
    ``Symbol color``), and a theme without it leaves the count unkeyed;
  * keyed, the buttons take its fill, not the quieter button's; on a coloured
    section the fill is replaced as a handle's is; its stroke lies inside, as
    ``Stroke align: inside`` says; its outer shadow is cast; the sign takes
    ``Symbol color``;
  * a keyed button that cannot step is the same button at the default mute.

Without the keys the count keeps the quieter button's paint: the render
snapshot and ``choice_paint_tests`` pin that.

Run with: uv run python tests/count_theme_tests.py
"""

import contextlib
import io
from pathlib import Path

import skia

from md2ui import session
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.render_counts import count_rects
from md2ui.pipeline.theme import Theme
from md2ui.pipeline.theme_model import MUTED_OPACITY
from md2ui.utils.image_cache import ImageCache

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data/markdown/tests/count-theme-parameters"
AMBER, BROWN, GREEN = (0xFD, 0xE6, 0x8A), (0xB4, 0x53, 0x09), (0x34, 0xD3, 0x99)
SHADOW, SIGN = (0x92, 0x40, 0x0E), (0x78, 0x35, 0x0F)
_PAGE = None


def _page():
    """The sample painted at 600: its pixels, boxes, nodes and theme."""
    global _PAGE
    if _PAGE is None:
        with contextlib.redirect_stdout(io.StringIO()):
            theme = session.load_theme(SAMPLE / "THEME.md")
            fonts = session.load_fonts(theme)
            kit = session.load_grouping_kit()
            ast = session.group_markdown((SAMPLE / "content.md").read_text(), kit)
            assert ast is not None
            root, index = session.prepare(ast, theme)
            scene = session.build_scene(
                LayoutGenerator(), root, index, theme, fonts, 600.0
            )
            image = session.render_image(
                scene, index, theme, fonts, ImageCache(), {}, 1.0
            )
        pixels = image.toarray(colorType=skia.kRGBA_8888_ColorType)
        _PAGE = pixels, scene.boxes, index, theme
    return _PAGE


def _rgb(x: float, y: float) -> tuple[int, int, int]:
    """The colour at layout point (x, y), inside the root padding."""
    pixels, _boxes, _index, theme = _page()
    pad = theme.root.padding
    r, g, b, _a = pixels[int(y + pad.top), int(x + pad.left)]
    return int(r), int(g), int(b)


def _count(which: int):
    """The ➖ and ➕ rects of the *which*-th count, top to bottom."""
    _pixels, boxes, index, theme = _page()
    hits = [
        b
        for b in boxes
        if b.content_id
        and (index.get(b.content_id, {}).get("drawing_element") or {}).get("count")
    ]
    box = sorted(hits, key=lambda b: b.y)[which]
    return count_rects(box, index[box.content_id]["drawing_element"], theme)


def _near(got: tuple[int, ...], want: tuple[int, ...], slack: int = 2) -> bool:
    return all(abs(a - b) <= slack for a, b in zip(got, want))


def test_count_button_parses_into_the_count_theme():
    counts = _page()[3].datapoints.counts
    assert counts.button.bg_colors == [0xFFFDE68A], counts.button.bg_colors
    assert counts.button.stroke_align == "inside"
    assert counts.button.stroke_width == 3.0
    assert len(counts.button.shadows) == 1
    assert counts.symbol_color == 0xFF78350F
    bare = Theme().datapoints.counts
    assert not bare.button.is_active() and bare.symbol_color is None
    print("  ✓  ### Count Button parses into the count theme")


def test_a_keyed_count_paints_its_own_button():
    minus, plus = _count(0)
    cx, cy, r = plus[0] + plus[2] / 2, plus[1] + plus[3] / 2, plus[2] / 2
    assert _rgb(cx - r * 0.4, cy - r * 0.4) == AMBER, _rgb(cx - r * 0.4, cy - r * 0.4)
    assert _rgb(plus[0] + 1, cy) == BROWN, "the stroke lies inside"
    assert min(_rgb(plus[0] - 1, cy)) >= 250, _rgb(plus[0] - 1, cy)
    assert _rgb(cx, plus[1] + plus[3] + 1) == SHADOW, "the outer shadow is cast"
    assert _near(_rgb(cx - 1, cy), SIGN), (
        "the sign takes Symbol color",
        _rgb(cx - 1, cy),
    )
    print("  ✓  a keyed count paints its own button, stroke, shadow and sign")


def test_on_a_coloured_section_the_button_is_replaced():
    _minus, plus = _count(2)
    cx, cy, r = plus[0] + plus[2] / 2, plus[1] + plus[3] / 2, plus[2] / 2
    assert _rgb(cx - r * 0.4, cy - r * 0.4) == GREEN, _rgb(cx - r * 0.4, cy - r * 0.4)
    assert _rgb(plus[0] + 1, cy) == (0xFF, 0xFF, 0xFF), _rgb(plus[0] + 1, cy)
    print("  ✓  on a coloured section the count's button is replaced")


def test_a_keyed_button_that_cannot_step_is_muted():
    minus, _plus = _count(1)  # Guests: 0/9 -- the minus cannot step
    cx, cy, r = minus[0] + minus[2] / 2, minus[1] + minus[3] / 2, minus[2] / 2
    faded = tuple(round(c * MUTED_OPACITY + 255 * (1 - MUTED_OPACITY)) for c in AMBER)
    got = _rgb(cx - r * 0.4, cy - r * 0.4)
    assert _near(got, faded), (got, faded)
    print("  ✓  a keyed button that cannot step is the same button, muted")


TESTS = [
    test_count_button_parses_into_the_count_theme,
    test_a_keyed_count_paints_its_own_button,
    test_on_a_coloured_section_the_button_is_replaced,
    test_a_keyed_button_that_cannot_step_is_muted,
]

if __name__ == "__main__":
    print("Count theme")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 -- report every test
            failed += 1
            print(f"  ✗  {test.__name__}: {exc!r}")
    raise SystemExit(1 if failed else 0)
