"""
Unit tests for how a segmented run and a count are painted: as a button pill is
(ADR-400, ADR-405).

Pinned here, on ``data/markdown/tests/choice-paint-theme-rules`` (a pale
secondary button with a 3px inside stroke; on a navy section its fill turns blue
and its stroke amber):

  * on a coloured section, a run's surface and a count's round buttons take the
    secondary pill's REPLACED colours, as the pill beside them does;
  * their strokes lie where ``Stroke align`` puts a pill's: inside the shape;
  * a disabled option inside a run is drawn inside its segment, its label in
    the disabled ink on the run's surface, never a pill of its own;
  * the surface is the control's: a disabled first option leaves it as a
    disabled second one does (``segmented-disabled-first``).

Run with: uv run python tests/choice_paint_tests.py
"""

import contextlib
import io
from pathlib import Path

import skia

from md2ui import session
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_render import _link_pill_rect
from md2ui.pipeline.render_counts import count_rects
from md2ui.pipeline.render_segmented import _INSET, choice_style
from md2ui.pipeline.render_style import _resolve_link
from md2ui.utils.image_cache import ImageCache

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data/markdown/tests/choice-paint-theme-rules"
DISABLED_FIRST = ROOT / "data/markdown/tests/segmented-disabled-first"
BLUE, AMBER, WHITE = (0x3B, 0x82, 0xF6), (0xFB, 0xBF, 0x24), (0xFF, 0xFF, 0xFF)
_PAGES: dict = {}


def _page(sample: Path = SAMPLE):
    """*sample* painted at 600: its pixels, boxes, nodes, theme and fonts."""
    if sample not in _PAGES:
        with contextlib.redirect_stdout(io.StringIO()):
            theme = session.load_theme(sample / "THEME.md")
            fonts = session.load_fonts(theme)
            kit = session.load_grouping_kit()
            ast = session.group_markdown((sample / "content.md").read_text(), kit)
            assert ast is not None
            root, index = session.prepare(ast, theme)
            scene = session.build_scene(
                LayoutGenerator(), root, index, theme, fonts, 600.0
            )
            image = session.render_image(
                scene, index, theme, fonts, ImageCache(), {}, 1.0
            )
        pixels = image.toarray(colorType=skia.kRGBA_8888_ColorType)
        _PAGES[sample] = pixels, scene.boxes, index, theme, fonts
    return _PAGES[sample]


def _rgb(x: float, y: float, sample: Path = SAMPLE) -> tuple[int, int, int]:
    """The colour at layout point (x, y): the page is painted inside the root
    padding."""
    pixels, _boxes_, _index, theme, _fonts = _page(sample)
    pad = theme.root.padding
    r, g, b, _a = pixels[int(y + pad.top), int(x + pad.left)]
    return int(r), int(g), int(b)


def _boxes(pick, sample: Path = SAMPLE) -> list:
    """The placed boxes whose node *pick* accepts, top to bottom."""
    _pixels, boxes, index, _theme, _fonts = _page(sample)
    hits = [b for b in boxes if b.content_id and pick(index.get(b.content_id, {}))]
    return sorted(hits, key=lambda b: b.y)


def _pill(
    label: str, which: int, sample: Path = SAMPLE
) -> tuple[float, float, float, float]:
    """The pill rect of the *which*-th button labelled *label* (0 root, 1 navy)."""
    _pixels, _boxes_, index, theme, fonts = _page(sample)
    box = _boxes(lambda nd: nd.get("link_label") == label, sample)[which]
    return _link_pill_rect(box, index[box.content_id], fonts, theme)


def _count(which: int):
    _pixels, _boxes_, index, theme, _fonts = _page()
    box = _boxes(lambda nd: (nd.get("drawing_element") or {}).get("count"))[which]
    return count_rects(box, index[box.content_id]["drawing_element"], theme)


def test_on_a_coloured_section_a_run_and_a_count_take_the_pills_paint():
    x, y, w, h = _pill("Pill", 1)
    assert _rgb(x + w / 2, y + 5) == BLUE, "the pill beside them is replaced"
    x, y, w, h = _pill("L", 1)  # an unchosen segment: the surface shows through
    assert _rgb(x + 4, y + h / 2) == BLUE, _rgb(x + 4, y + h / 2)
    assert _rgb(x + w + _INSET - 1, y + h / 2) == AMBER, "its stroke is replaced"
    minus, _plus = _count(1)
    cx, cy, r = minus[0] + minus[2] / 2, minus[1] + minus[3] / 2, minus[2] / 2
    assert _rgb(cx, cy - r * 0.55) == BLUE, _rgb(cx, cy - r * 0.55)
    assert _rgb(minus[0] + 1, cy) == AMBER, _rgb(minus[0] + 1, cy)
    print("  ✓  on a coloured section a run and a count take the pill's paint")


def _clear(x: float, y: float) -> bool:
    """Nothing painted at (x, y) on the white root, up to antialiasing."""
    return min(_rgb(x, y)) >= 250


def test_their_strokes_follow_stroke_align():
    x, y, w, h = _pill("Pill", 0)
    assert _clear(x - 1, y + h / 2), "a pill's inside stroke stays inside"
    x, y, w, h = _pill("S", 0)
    left = x - _INSET
    assert _clear(left - 1, y + h / 2), _rgb(left - 1, y + h / 2)
    minus, _plus = _count(0)
    cy = minus[1] + minus[3] / 2
    assert _clear(minus[0] - 1, cy), _rgb(minus[0] - 1, cy)
    print("  ✓  a run's and a count's strokes follow Stroke align")


def test_a_disabled_option_is_drawn_inside_its_segment():
    _pixels, _boxes_, index, theme, _fonts = _page()
    (node,) = [
        nd
        for nd in index.values()
        if nd.get("link_label") == "M" and "size?" in nd.get("content", "")
    ]
    assert node.get("link_disabled")
    style = _resolve_link(node, theme)[3]
    shown = choice_style({**node, "segment": True}, style, theme)
    assert not (shown.fill_color or 0) >> 24 and not shown.stroke_width, "no pill"
    assert shown.text_style is not None and style.text_style is not None
    assert shown.text_style.color == style.text_style.color, "the disabled ink"
    x, y, w, h = _pill("M", 0)
    surface = _rgb(_pill("L", 0)[0] + 4, y + h / 2)
    assert _rgb(x + 4, y + h / 2) == surface, "the run's surface shows through"
    print("  ✓  a disabled option is drawn inside its segment, not as a pill")


def test_a_runs_surface_is_the_controls_not_its_first_options():
    # The two runs differ only in which option is disabled, the first or the
    # second: the surface behind the run, its fill and its stroke, is the same.
    def surface(which: int) -> tuple:
        x, y, w, h = _pill("L", which, DISABLED_FIRST)  # unchosen: surface shows
        stroke = _rgb(x + w / 2, y - _INSET + 1, DISABLED_FIRST)
        return _rgb(x + 4, y + h / 2, DISABLED_FIRST), stroke

    assert surface(0) == surface(1), (surface(0), surface(1))
    print("  ✓  a run's surface is the control's, whichever option is disabled")


TESTS = [
    test_on_a_coloured_section_a_run_and_a_count_take_the_pills_paint,
    test_their_strokes_follow_stroke_align,
    test_a_disabled_option_is_drawn_inside_its_segment,
    test_a_runs_surface_is_the_controls_not_its_first_options,
]

if __name__ == "__main__":
    print("Choice paint")
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
    print(f"All {len(TESTS)} tests passed.")
