"""
A ring's unit label inside the circle: it wraps onto up to two lines that each fit the
clear inside at that line's height, shrinks no further than 80% of its
``Ring Unit`` size, and ends in an ellipsis when it still does not fit. The
leaf's measured box (``_leaf_height`` / ``_leaf_natural_width``) reads the same
layout the painter draws (ADR-400).

Theme: data/markdown/tests/THEME.md (diameter 148, stroke 12, value 28, unit 13),
so the clear inside is 116px across.

Run with: uv run python tests/ring_text_tests.py
"""

from pathlib import Path

import skia  # type: ignore[import-untyped]

from md2ui import session
from md2ui.pipeline.render_measure import (
    LINE_SCALE,
    _leaf_height,
    _leaf_natural_width,
)
from md2ui.pipeline.theme import parse_theme
from md2ui.utils.font_loader import make_font

_THEME = parse_theme(Path(__file__).parent.parent / "data/markdown/tests/THEME.md")
_FONTS = session.load_fonts(_THEME)
_UNIT = 13.0


def _unit(text: str) -> dict:
    return {"ring_role": "unit", "ring_text": text}


def _plan(text: str):
    from md2ui.pipeline.render_ring_text import ring_text

    return ring_text(_unit(text), _FONTS, _THEME)


def _inside(line: str, i: int, count: int, font: skia.Font) -> bool:
    """Whether label line *i* of *count* keeps its ink inside the clear circle
    (baseline one size below the line's top, centred on its advance), worked
    out here independently of the module under test."""
    radius = (148 - 2 * 12 - 2 * 4) / 2
    size = font.getSize()
    value_h, line_h = 28 * LINE_SCALE, size * LINE_SCALE
    base = -(value_h + count * line_h) / 2 + value_h + i * line_h + size
    ink = skia.Rect()
    adv = font.measureText(line, skia.TextEncoding.kUTF8, ink)
    dy = max(abs(base + ink.top()), abs(base + ink.bottom()))
    dx = max(adv / 2 - ink.left(), ink.right() - adv / 2)
    return dx**2 + dy**2 <= radius**2


def test_a_label_wider_than_the_ring_wraps_whole():
    rp = _unit("Structured cards and actions")
    assert _leaf_height(None, 148.0, _FONTS, _THEME, rp) == 2 * _UNIT * LINE_SCALE
    plan = _plan("Structured cards and actions")
    assert plan.lines == ("Structured cards", "and actions"), plan.lines
    assert plan.size == _UNIT
    print("  ✓  a label wider than the ring wraps onto two lines, whole")


def test_each_line_fits_the_clear_inside_at_its_height():
    """One line under the diameter but over the clear inside would run over
    the stroke."""
    rp = _unit("Weekly active sessions")
    assert _leaf_height(None, 148.0, _FONTS, _THEME, rp) == 2 * _UNIT * LINE_SCALE
    plan = _plan("Weekly active sessions")
    font = make_font(plan.fonts.typeface, plan.size)
    for i, line in enumerate(plan.lines):
        assert _inside(line, i, len(plan.lines), font), line
        assert not _inside(" ".join(plan.lines), 0, 1, font), "would have fit whole"
    width = _leaf_natural_width(None, 148.0, _FONTS, _THEME, rp)
    assert width == max(font.measureText(ln) for ln in plan.lines)
    print("  ✓  each label line fits the clear inside at its own height")


def test_two_lines_that_do_not_fit_shrink_before_anything_is_cut():
    # "Live data with reliable images" was this label until the fit read exact
    # outlines: its second line's ink reaches 57.095 from the centre against a
    # radius of 58, so it fits at 13px, and only the ink rounded out to whole
    # pixels (59.34 on macOS) made it shrink. "pictures" really overflows.
    plan = _plan("Live data with reliable pictures")
    assert " ".join(plan.lines) == "Live data with reliable pictures"
    assert _UNIT * 0.8 <= plan.size < _UNIT, plan.size
    print("  ✓  a label that two lines cannot hold shrinks, whole")


def test_past_the_floor_the_label_ends_in_an_ellipsis():
    plan = _plan("Average weekly sessions per active member")
    assert plan.size == _UNIT * 0.8
    assert len(plan.lines) == 2 and plan.lines[-1].endswith("…"), plan.lines
    rp = _unit("Average weekly sessions per active member")
    assert _leaf_height(None, 148.0, _FONTS, _THEME, rp) == 2 * plan.size * LINE_SCALE
    print("  ✓  past the 80% floor the label ends in an ellipsis")


def test_a_short_label_and_the_value_keep_one_themed_line():
    assert (
        _leaf_height(None, 148.0, _FONTS, _THEME, _unit("Kcal")) == _UNIT * LINE_SCALE
    )
    value = {"ring_role": "value", "ring_text": "4/10"}
    assert _leaf_height(None, 148.0, _FONTS, _THEME, value) == 28 * LINE_SCALE
    print("  ✓  a short label and the value keep their one themed line")


TESTS = [
    test_a_label_wider_than_the_ring_wraps_whole,
    test_each_line_fits_the_clear_inside_at_its_height,
    test_two_lines_that_do_not_fit_shrink_before_anything_is_cut,
    test_past_the_floor_the_label_ends_in_an_ellipsis,
    test_a_short_label_and_the_value_keep_one_themed_line,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
