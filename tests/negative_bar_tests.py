"""
A single drawn bar below zero (``Key: -1.55%``) fills from the right.

A value's bar paints its share of the whole from the left of its track. Below
zero the track is read the other way: zero is its right edge and the fill runs
left from it, the way a chart of losses only does. ``Negative color`` on the
bar's own block paints it; unset, it keeps the bar's colour. A ring has no side
to go below zero on, so it stays empty.

Run with: uv run tests/negative_bar_tests.py
"""

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.render_bars import _bar_fraction, _bar_ratio, _paint_bar
from md2ui.pipeline.theme import BarTheme

FILL = 0xFF00CC58
GREY = 0xFFB4B4BB
TRACK = 0xFFE5F9EE


def _pixel(surface: skia.Surface, x: int, y: int) -> int:
    rgba = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    r, g, b, a = (int(v) for v in rgba[y, x])
    return (a << 24) | (r << 16) | (g << 8) | b


def _bar(negative: int | None = None) -> BarTheme:
    bar = BarTheme(thickness=10.0, negative_color=negative)
    bar.bar.bg_colors = [FILL]
    bar.track.bg_colors = [TRACK]
    return bar


def _painted(bar: BarTheme, frac: float) -> skia.Surface:
    surface = skia.Surface(100, 10)
    _paint_bar(surface.getCanvas(), 0, 0, 100, bar, frac)
    return surface


def test_the_ratio_keeps_its_sign_and_stops_at_the_whole():
    assert _bar_ratio({"percent": -1.55}) == -0.0155
    assert _bar_ratio({"percent": -150.0}) == -1.0
    assert _bar_ratio({"value": -3.0, "max": 4.0}) == -0.75
    assert _bar_ratio({"percent": 40.0}) == 0.4


def test_a_ring_below_zero_stays_empty():
    assert _bar_fraction({"percent": -40.0}) == 0.0
    assert _bar_fraction({"percent": 40.0}) == 0.4


def test_a_negative_fill_runs_left_from_the_right_edge():
    s = _painted(_bar(), -0.5)
    assert _pixel(s, 45, 5) == TRACK, "a half-share starts half way"
    assert _pixel(s, 55, 5) == FILL
    assert _pixel(s, 98, 5) == FILL


def test_a_whole_negative_fills_the_track():
    s = _painted(_bar(), -1.0)
    assert _pixel(s, 1, 5) == FILL
    assert _pixel(s, 98, 5) == FILL


def test_a_tiny_negative_keeps_the_thickness_floor_at_the_right():
    s = _painted(_bar(), -0.01)
    assert _pixel(s, 92, 5) == FILL
    assert _pixel(s, 85, 5) == TRACK


def test_negative_color_paints_only_below_zero():
    assert _pixel(_painted(_bar(GREY), -0.5), 60, 5) == GREY
    assert _pixel(_painted(_bar(GREY), 0.5), 40, 5) == FILL


def test_a_positive_bar_still_fills_from_the_left():
    s = _painted(_bar(), 0.5)
    assert _pixel(s, 1, 5) == FILL
    assert _pixel(s, 60, 5) == TRACK


TESTS = [
    test_the_ratio_keeps_its_sign_and_stops_at_the_whole,
    test_a_ring_below_zero_stays_empty,
    test_a_negative_fill_runs_left_from_the_right_edge,
    test_a_whole_negative_fills_the_track,
    test_a_tiny_negative_keeps_the_thickness_floor_at_the_right,
    test_negative_color_paints_only_below_zero,
    test_a_positive_bar_still_fills_from_the_left,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
    print(f"{len(TESTS)} passed")
