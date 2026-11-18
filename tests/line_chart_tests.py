"""
A value written as an arrow chain draws a line: ``Price: $710 → $713 → $720``.

The grouper stamps ``line_chart`` on a ``Key: value`` pair whose whole value is
three or more values joined by ``→``, all in one unit -- `%`, a currency, or
numbers with or without a magnitude -- each optionally followed by a ``(tick)``
that names its point: words, a date, a time, `(Q1)`, `(FY2020)`, `(2025)`. Plain numbers draw only when the key declares their unit,
``Users (count): 900 → 1.2K``, as a bar chart's run does (ADR-204). Anything else in the
value keeps it text: a tick holding a second value (`$412M (49%)`), mixed units,
an ellipsis, a word chain, or a before-and-after of two values. `->` is no
arrow: the chain stays text and ``check`` says to write `→`. It draws with no
theme at all, like every display, in the line's own default paint; ``Enabled: no``
under ``### Line Chart`` turns it off. The generator
then draws the key with the last value as written, over a line leaf; the
renderer spreads the points across the width against the data's own range.

Run with: uv run tests/line_chart_tests.py
"""

import sys
from pathlib import Path

import skia  # type: ignore[import-untyped]

sys.path.insert(0, str(Path(__file__).parent))

from datapoint_layout_tests import _ast, _generate, _props, _walk
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_line_chart import (
    _line_points,
    _shown_ticks,
    draw_line_chart,
    line_chart_height,
)
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import Theme, parse_theme


def _lines(text: str) -> list[dict]:
    return [
        n.datapoint_payload or {}
        for n in _walk(_ast(text))
        if n.datapoint_display == "line_chart"
    ]


def _points(text: str) -> list[dict] | None:
    found = _lines(text)
    return found[0]["points"] if found else None


def _line_theme() -> Theme:
    t = Theme()
    t.charts.line.enabled = True
    return t


# ---------------------------------------------------------------------------
# What draws a line (grouper)
# ---------------------------------------------------------------------------


def test_an_arrow_chain_of_one_unit_is_a_line():
    pts = _points("Price: $710.14 → $713.94 → $720.65 → $777.24")
    assert pts is not None
    assert [p["value"] for p in pts] == [710.14, 713.94, 720.65, 777.24]
    assert pts[-1]["text"] == "$777.24", "the value as written"


def test_plain_numbers_and_magnitudes_share_one_kind():
    assert _points("Users (count): 120 → 340 → 910") is not None
    assert _points("Users (count): 900 → 1.2K → 5K") is not None
    assert _points("Users: 5K → 7K → 9K") is not None, "a magnitude stands alone"


def test_plain_numbers_need_a_declared_unit():
    assert _points("Users: 120 → 340 → 910") is None
    assert _points("Users: 900 → 1.2K → 5K") is None


def test_a_unit_outside_the_inline_forms_is_declared():
    assert _points("Weight: 82 kg → 80.5 kg → 79 kg") is None
    assert _points("Weight (kg): 82 → 80.5 → 79") is not None


def test_ticks_are_words_or_a_date():
    pts = _points("SPY: $710.14 (Apr 13) → $713.94 → $720.65 (May) → $777.24 (Now)")
    assert pts is not None
    assert [p["tick"] for p in pts] == ["Apr 13", None, "May", "Now"]


def test_a_numeric_parenthesis_keeps_the_text():
    assert _points("Revenue: $412M (49%) → $430M → $450M") is None
    assert _points("Price: $1 (1.2K) → $2 → $3") is None
    assert _points("Price: $1 (+5) → $2 → $3") is None
    assert _points("Price: $1 (5 kg) → $2 → $3") is None


def test_a_label_with_a_digit_names_its_point():
    def ticks(text: str) -> list:
        pts = _points(text)
        assert pts is not None, text
        return [p["tick"] for p in pts]

    assert ticks("Users (count): 900 (Q1) → 1.2K (Q2) → 3.4K (Q3)") == [
        "Q1",
        "Q2",
        "Q3",
    ]
    assert ticks("Sales: $274.5B (FY2020) → $365.8B → $394.3B (FY2022)") == [
        "FY2020",
        None,
        "FY2022",
    ]
    assert ticks("Temp (°C): 26 (6 PM) → 25 → 21 (12 AM)") == ["6 PM", None, "12 AM"]
    assert ticks("Price: $1 (2025) → $2 → $3 (2027)") == ["2025", None, "2027"]


def test_an_ascii_arrow_draws_no_line_and_check_says_so():
    from md2ui import check_charts

    assert _points("Price: $10 -> $12 -> $14") is None
    ((pair, advice),) = check_charts.lines_left_text(_ast("Price: $10 -> $12 -> $14\n"))
    assert pair.startswith("Price") and "`→`" in advice
    quiet = "Path: a -> b -> c\n\nChange: $10 -> $12\n\nCode: `$10 -> $12 -> $14`\n"
    assert not check_charts.lines_left_text(_ast(quiet))


def test_a_chain_without_its_key_on_the_line_is_named():
    # A label line with the values under it (the chart rows' layout) draws
    # text, so check names it; the fix reuses the label right above as the key.
    from md2ui import check_charts

    under = "Temperature (°C):\n20 (2 PM) → 20 (3 PM) → 19 (4 PM) → 18 (5 PM)\n"
    ((chain, _, fix),) = check_charts.chains_without_key(_ast(under))
    assert chain.startswith("20 (2 PM)"), chain
    assert fix == "`Temperature (°C): 20 (2 PM) → 20 (3 PM) → 19 (4 PM) → …`", fix
    ((_, _, alone),) = check_charts.chains_without_key(_ast("$710 → $713 → $777\n"))
    assert alone == "`Key: $710 → $713 → $777`", alone
    for quiet in ("Price: $10 → $12 → $14\n", "Home → Settings → Privacy\n"):
        assert not check_charts.chains_without_key(_ast(quiet)), quiet
    # The key is on the line but the values carry `°`, a unit a line does not
    # take: the fix moves the unit into the key, never a `Key:` in front.
    keyed = "Temperature: 26° (6 PM) → 25° (7 PM) → 23° (8 PM) → 21° (9 PM)\n"
    ((_, why, fix),) = check_charts.chains_without_key(_ast(keyed))
    assert "name it in the key" in why, why
    assert fix == "`Temperature (°): 26 (6 PM) → 25 (7 PM) → 23 (8 PM) → …`", fix
    drawn = fix.strip("`").replace(" → …", " → 21 (9 PM)") + "\n"
    assert any(n.datapoint_display == "line_chart" for n in _walk(_ast(drawn))), drawn


def test_a_lines_unit_goes_in_its_key_not_above_it():
    # `20°` is in no chart unit. A unit declared ABOVE serves a run of rows,
    # never one line, so the note names only the key form, from what was
    # written.
    from md2ui import check_charts

    text = "Temperature: 20° (2 PM) → 20° → 19° → 18° (5 PM)\n"
    ((_, advice),) = check_charts.lines_left_text(_ast(text))
    assert "above" not in advice and "Storage (GB)" not in advice, advice
    assert advice.endswith("`Temperature (°): 20 (2 PM) → 20 → 19 → …`"), advice


def test_mixed_units_keep_the_text():
    assert _points("Cost: $200 → 200 EUR → $210") is None
    assert _points("Mix: 4% → $5 → 6%") is None


def test_two_values_are_a_change_not_a_line():
    assert _points("Price: $702 → $720") is None


def test_an_ellipsis_or_words_keep_the_text():
    assert _points("Price: $702 → … → $720 → $730") is None
    assert _points("State: registered → active → deprecated") is None
    assert _points("Price: $702 → $715 → $720 and rising") is None


def test_only_the_arrow_joins_a_chain():
    assert _points("Price: $702 -> $715 -> $720") is None
    assert _points("Price: $702, $715, $720") is None


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


def test_a_theme_styles_the_line():
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(
            "## Charts\n### Line Chart\nHeight: 60\nLine width: 3\n"
            "Line color: #123456\nPoint size: 0\nPoints: last\n"
        )
    lt = parse_theme(Path(f.name)).charts.line
    assert lt.enabled
    assert (lt.height, lt.width, lt.color, lt.point_size, lt.points) == (
        60.0,
        3.0,
        0xFF123456,
        0.0,
        "last",
    )
    assert Theme().charts.line.enabled, "on with no theme, like every display"


# ---------------------------------------------------------------------------
# Layout (generator)
# ---------------------------------------------------------------------------

CHAIN = "Price: $710.14 → $713.94 → $777.24 (Now)"


def test_without_a_theme_the_chain_draws_a_line():
    # Consistent with every other display: the built-in defaults draw it.
    assert _props(_generate(CHAIN, Theme()), "line_chart")


def test_a_theme_turns_the_line_off():
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write("## Charts\n### Line Chart\nEnabled: no\n")
    assert not _props(_generate(CHAIN, parse_theme(Path(f.name))), "line_chart")


def test_the_line_sits_under_the_key_and_last_value():
    layout = _generate(CHAIN, _line_theme())
    lines = _props(layout, "line_chart")
    assert len(lines) == 1
    overrides = [rp for _, rp in _props(layout, "text_override")]
    assert overrides == ["$777.24"], "the last value as written, without its tick"


# ---------------------------------------------------------------------------
# Drawing (renderer)
# ---------------------------------------------------------------------------


def _data(*values: float, ticks: dict | None = None) -> dict:
    ticks = ticks or {}
    return {
        "points": [
            {"value": v, "text": str(v), "tick": ticks.get(i)}
            for i, v in enumerate(values)
        ]
    }


def test_the_axis_fits_the_data_range():
    t = _line_theme()
    t.charts.line.point_size = 0.0
    t.charts.line.width = 2.0
    pts = _line_points(_data(700.0, 750.0, 800.0), 0.0, 0.0, 202.0, t)
    xs = [round(x, 6) for x, _ in pts]
    ys = [round(y, 6) for _, y in pts]
    assert xs == [1.0, 101.0, 201.0], "evenly spread, inset by half the stroke"
    h = t.charts.line.height
    assert ys == [h - 1.0, h / 2.0, 1.0], "lowest at the bottom, highest at the top"


def test_a_flat_line_sits_mid_area():
    t = _line_theme()
    ys = {y for _, y in _line_points(_data(5.0, 5.0, 5.0), 0.0, 0.0, 100.0, t)}
    assert ys == {t.charts.line.height / 2.0}


def _fonts() -> FontSet:
    face = skia.Typeface.MakeDefault()
    return FontSet(face, face, face, face, face)


def test_ticks_add_a_label_line_to_the_height():
    t = _line_theme()
    plain = line_chart_height(_data(1.0, 2.0, 3.0), 100.0, _fonts(), t)
    ticked = line_chart_height(
        _data(1.0, 2.0, 3.0, ticks={2: "Now"}), 100.0, _fonts(), t
    )
    assert plain == t.charts.line.height
    assert ticked > plain


def test_crowded_labels_keep_the_ends_first():
    roomy = [(0.0, 20.0), (40.0, 60.0), (80.0, 100.0)]
    assert _shown_ticks(roomy) == [0, 1, 2]
    crowded = [(0.0, 30.0), (20.0, 50.0), (40.0, 70.0), (60.0, 90.0), (80.0, 110.0)]
    assert _shown_ticks(crowded) == [0, 2, 4], "the middle one, then gaps"
    assert _shown_ticks([(0.0, 50.0), (30.0, 80.0)]) == [1], "the last one wins"
    assert _shown_ticks([]) == []


def test_the_line_paints_in_its_color():
    t = _line_theme()
    t.charts.line.color = 0xFF123456
    t.charts.line.width = 4.0
    surface = skia.Surface(100, 60)
    box = LayoutBox(x=0.0, y=0.0, width=100.0, height=60.0)
    face = skia.Typeface.MakeDefault()
    fonts = FontSet(face, face, face, face, face)
    draw_line_chart(surface.getCanvas(), box, _data(1.0, 1.0, 1.0), fonts, t)
    rgba = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    mid = int(t.charts.line.height / 2.0)
    assert tuple(int(c) for c in rgba[mid, 50]) == (0x12, 0x34, 0x56, 255)


def test_points_last_keeps_only_the_last_dot():
    t = _line_theme()
    t.charts.line.color = 0xFF123456
    t.charts.line.width = 1.0
    t.charts.line.point_size = 10.0
    data = _data(1.0, 1.0, 1.0, ticks={0: "Apr"})
    face = skia.Typeface.MakeDefault()
    fonts = FontSet(face, face, face, face, face)
    mid = int(t.charts.line.height / 2.0)

    def first_dot(points: str) -> bool:
        t.charts.line.points = points
        surface = skia.Surface(100, 80)
        surface.getCanvas().clear(skia.ColorWHITE)
        box = LayoutBox(x=0.0, y=0.0, width=100.0, height=80.0)
        draw_line_chart(surface.getCanvas(), box, data, fonts, t)
        rgba = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
        return tuple(int(c) for c in rgba[mid - 3, 5][:3]) == (0x12, 0x34, 0x56)

    assert first_dot("labelled"), "a labelled point has a dot"
    assert not first_dot("last"), "`Points: last` keeps only the last point's"
    assert Theme().charts.line.points == "labelled"


def test_value_format_shows_the_declared_unit_on_the_last_value():
    t = _line_theme()
    t.charts.value_format = "1unit"
    layout = _generate("High (°C): 24 (Wed) → 23 (Thu) → 21 (Fri)", t)
    assert [rp for _, rp in _props(layout, "text_override")] == ["21°C"]
    bare = _generate("High (°C): 24 (Wed) → 23 (Thu) → 21 (Fri)", _line_theme())
    assert [rp for _, rp in _props(bare, "text_override")] == ["21"]


def test_the_area_takes_the_background_keys():
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(
            "## Charts\n### Line Chart\nLine color: #123456\n"
            "Background color:\n- #11223344\n- #55667788\n"
            "Background gradient:\n- Colors:\n  - #FF000080\n  - #FF000000\n"
        )
    lt = parse_theme(Path(f.name)).charts.line
    assert lt.color == 0xFF123456, "the line keeps its own keys"
    assert lt.fill.bg_colors == [0x44112233, 0x88556677]
    assert lt.fill.gradient is not None and len(lt.fill.gradient.colors) == 2
    assert not Theme().charts.line.fill.bg_colors, "no area until declared"


def _area_pixel(t: Theme, data: dict, y: int, x: int = 50) -> tuple[int, ...]:
    surface = skia.Surface(100, 80)
    surface.getCanvas().clear(skia.ColorWHITE)
    box = LayoutBox(x=0.0, y=0.0, width=100.0, height=80.0)
    draw_line_chart(surface.getCanvas(), box, data, _fonts(), t)
    rgba = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    return tuple(int(c) for c in rgba[y, x][:3])


def test_the_area_under_the_line_fills():
    t = _line_theme()
    t.charts.line.point_size = 0.0
    bottom = int(t.charts.line.height) - 2
    rising = _data(1.0, 2.0, 3.0)
    assert _area_pixel(t, rising, bottom) == (255, 255, 255), "no fill by default"
    t.charts.line.fill.bg_colors = [0xFF00FF00]
    assert _area_pixel(t, rising, bottom) == (0, 255, 0), "under the line"
    assert _area_pixel(t, rising, 2, x=5) == (255, 255, 255), "never above it"


def test_the_area_follows_color_replacements():
    t = _line_theme()
    t.charts.line.point_size = 0.0
    t.charts.line.fill.bg_colors = [0xFF00FF00]
    t.color_replacements = {0xFF18181B: {"fill": {0xFF00FF00: 0xFF0000FF}}}
    surface = skia.Surface(100, 80)
    box = LayoutBox(x=0.0, y=0.0, width=100.0, height=80.0, bg_stack=(0xFF18181B,))
    draw_line_chart(surface.getCanvas(), box, _data(1.0, 2.0, 3.0), _fonts(), t)
    rgba = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    y = int(t.charts.line.height) - 2
    assert tuple(int(c) for c in rgba[y, 50][:3]) == (0, 0, 255)


TESTS = [
    test_a_chain_without_its_key_on_the_line_is_named,
    test_a_lines_unit_goes_in_its_key_not_above_it,
    test_plain_numbers_need_a_declared_unit,
    test_a_label_with_a_digit_names_its_point,
    test_an_ascii_arrow_draws_no_line_and_check_says_so,
    test_a_unit_outside_the_inline_forms_is_declared,
    test_an_arrow_chain_of_one_unit_is_a_line,
    test_plain_numbers_and_magnitudes_share_one_kind,
    test_ticks_are_words_or_a_date,
    test_a_numeric_parenthesis_keeps_the_text,
    test_mixed_units_keep_the_text,
    test_two_values_are_a_change_not_a_line,
    test_an_ellipsis_or_words_keep_the_text,
    test_only_the_arrow_joins_a_chain,
    test_a_theme_styles_the_line,
    test_without_a_theme_the_chain_draws_a_line,
    test_a_theme_turns_the_line_off,
    test_the_line_sits_under_the_key_and_last_value,
    test_the_axis_fits_the_data_range,
    test_a_flat_line_sits_mid_area,
    test_ticks_add_a_label_line_to_the_height,
    test_crowded_labels_keep_the_ends_first,
    test_the_line_paints_in_its_color,
    test_points_last_keeps_only_the_last_dot,
    test_value_format_shows_the_declared_unit_on_the_last_value,
    test_the_area_takes_the_background_keys,
    test_the_area_under_the_line_fills,
    test_the_area_follows_color_replacements,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
        print(f"  ✓ {t.__name__}")
    print(f"{len(TESTS)} passed")
