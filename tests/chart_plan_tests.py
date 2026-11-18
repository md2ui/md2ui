"""
Unit tests for the renderer's chart geometry decisions (_chart_plan_for):
orientation from row count + available width (few → horizontal rows, many +
wide → vertical bars, many + narrow → stacked columns), percent scaling,
legend reservation, and height accounting shared with _leaf_height — and
where vertical bars go (_chart_vertical_bars), fixed or filling the width. A
value below zero turns the scale into the data's range, and bars of either
orientation run from the zero inside it (_chart_span); rows that mix gains and
losses centre that zero, so all-negative rows run right to left from the right
edge and mixed rows both ways from the middle. A vertical chart's
### Chart Grid ticks round its scale and may take a gutter for their labels.

Run with: uv run tests/chart_plan_tests.py
"""

import skia

from md2ui.pipeline.render_chart import (
    ChartPlan,
    _CHART_VERTICAL_H,
    _chart_plan_for,
    _chart_vertical_bars,
    _chart_vertical_min_width,
)
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.render_measure import _leaf_height
from md2ui.pipeline.theme import Theme

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fonts() -> FontSet:
    tf = skia.Typeface.MakeDefault()
    return FontSet(tf, tf, tf, tf, tf)


def _data(n: int, series: list[str] | None = None, width_values: int = 1):
    return {
        "series": series,
        "unit": "%",
        "rows": [
            {
                "label": f"Row {i}",
                "values": [10.0 * (i + 1)] * width_values,
            }
            for i in range(n)
        ],
    }


def _plan(data, width: float) -> ChartPlan:
    return _chart_plan_for(data, width, _fonts(), Theme())


# ---------------------------------------------------------------------------
# Orientation
# ---------------------------------------------------------------------------


def test_few_rows_horizontal():
    plan = _plan(_data(3), 800.0)
    assert plan.orientation == "horizontal" and plan.columns == 1


def test_many_rows_wide_vertical():
    plan = _plan(_data(8), 800.0)
    assert plan.orientation == "vertical", plan.orientation


def test_many_rows_narrow_columns():
    # Wide labels rule out vertical bars; enough width for two columns.
    data = _data(10)
    for i, r in enumerate(data["rows"]):
        r["label"] = f"Long metric label {i}"
    plan = _plan(data, 500.0)
    assert plan.orientation == "columns", plan.orientation
    assert plan.columns == 2


def test_many_rows_very_narrow_single_column():
    plan = _plan(_data(10), 230.0)
    assert plan.orientation == "horizontal" and plan.columns == 1


# ---------------------------------------------------------------------------
# Scaling / legend / values
# ---------------------------------------------------------------------------


def test_percent_scale_is_100():
    plan = _plan(_data(3), 800.0)
    assert plan.scale_max == 100.0


def test_over_100_scales_to_peak():
    data = _data(3)
    data["rows"][0]["values"] = [250.0]
    plan = _plan(data, 800.0)
    assert plan.scale_max == 250.0


def test_series_legend_reserved():
    plan = _plan(_data(5, series=["A", "B"], width_values=2), 800.0)
    assert plan.series == ["A", "B"]
    assert plan.legend_h > 0.0
    no_series = _plan(_data(5), 800.0)
    assert no_series.legend_h == 0.0


def test_multi_series_values_shape():
    plan = _plan(_data(4, series=["A", "B"], width_values=2), 800.0)
    assert all(len(v) == 2 for v in plan.values)


# ---------------------------------------------------------------------------
# Height accounting
# ---------------------------------------------------------------------------


def test_horizontal_height_accounts_rows_and_gaps():
    plan = _plan(_data(3), 800.0)
    from md2ui.pipeline.render_chart import _CHART_ROW_GAP

    assert plan.height == 3 * plan.row_h + 2 * _CHART_ROW_GAP


def test_horizontal_height_accounts_for_track_inner_padding():
    theme = Theme()
    plain = _chart_plan_for(_data(3), 800.0, _fonts(), theme)
    theme.charts.track.padding.top = theme.charts.track.padding.bottom = 5.0
    padded = _chart_plan_for(_data(3), 800.0, _fonts(), theme)
    assert padded.row_h == plain.row_h + 10.0
    assert padded.height == plain.height + 30.0


def test_vertical_height_uses_chart_area():
    plan = _plan(_data(8), 800.0)
    assert plan.height == _CHART_VERTICAL_H + 4.0 + plan.label_line_h


def test_leaf_height_uses_plan():
    data = _data(3)
    h = _leaf_height(
        None,
        800.0,
        _fonts(),
        Theme(),
        {"chart": data},
    )
    assert h == _plan(data, 800.0).height


# ---------------------------------------------------------------------------


def test_the_flip_point_is_the_width_the_plan_flips_at():
    """``_chart_vertical_min_width`` is the SAME number the orientation is
    decided by, not a second estimate of it.

    It exists because a chart is a filler by width — it spans whatever column it
    is handed — while its picture is not: below this width the bars turn on
    their side. Whoever sizes a block holding a chart (the ``Stack sections``
    measure) needs the flip point, and a copy of the rule would drift.
    """
    data = _data(6)
    flip = _chart_vertical_min_width(data, _fonts(), Theme())
    assert flip is not None
    assert _plan(data, flip).orientation == "vertical"
    assert _plan(data, flip - 1.0).orientation != "vertical"


def test_a_chart_that_never_goes_vertical_has_no_flip_point():
    """Four rows or fewer read best as horizontal bars and are drawn that way at
    any width, so there is nothing for a block to protect and no minimum to
    report."""
    assert _chart_vertical_min_width(_data(4), _fonts(), Theme()) is None
    assert _plan(_data(4), 4000.0).orientation == "horizontal"


def test_the_flip_point_grows_with_the_labels():
    """A row's slot is as wide as its own label, so longer labels flip later —
    which is why the number cannot be a constant per row count."""
    theme, fonts = Theme(), _fonts()
    short = _data(6)
    long = _data(6)
    for row in long["rows"]:
        row["label"] = "Wednesday afternoon"
    wide_labels = _chart_vertical_min_width(long, fonts, theme)
    narrow_labels = _chart_vertical_min_width(short, fonts, theme)
    assert wide_labels is not None and narrow_labels is not None
    assert wide_labels > narrow_labels


def _fill_theme(thickness: float = 22.0, spacing: float = 10.0) -> Theme:
    t = Theme()
    t.charts.bar_width = "fill"
    t.charts.bar_thickness = thickness
    t.charts.bar_spacing = spacing
    return t


def _xywh(r) -> tuple[float, float, float, float]:
    return (r.x(), r.y(), r.width(), r.height())


def test_fixed_bars_stay_thin_and_centred():
    """The default: groups of Bar thickness centred in equal slots, a bar never
    shorter than it is wide."""
    plan = _plan(_data(5), 600.0)
    bars, spans = _chart_vertical_bars(plan, 0.0, 600.0, 140.0, Theme())
    assert [s for s in spans] == [(i * 120.0, 120.0) for i in range(5)]
    assert _xywh(bars[0][2]) == (53.0, 126.0, 14.0, 14.0), "10% floors at its width"
    assert all(r.width() == 14.0 for _, _, r in bars)


def test_filled_bars_span_the_width_with_bar_spacing():
    plan = _chart_plan_for(_data(5), 600.0, _fonts(), _fill_theme())
    bars, spans = _chart_vertical_bars(plan, 0.0, 600.0, 140.0, _fill_theme())
    w = (600.0 - 4 * 10.0) / 5
    assert [round(r.x(), 6) for _, _, r in bars] == [
        round(i * (w + 10.0), 6) for i in range(5)
    ]
    assert all(abs(r.width() - w) < 1e-9 for _, _, r in bars)
    assert abs(bars[-1][2].right() - 600.0) < 1e-9, "the last bar reaches the edge"
    assert spans[2] == (bars[2][2].x(), bars[2][2].width()), "labels centre on bars"


def test_a_filled_bar_floors_at_bar_thickness():
    data = _data(5)
    data["rows"][0]["values"] = [1.0]
    theme = _fill_theme()
    plan = _chart_plan_for(data, 600.0, _fonts(), theme)
    bars, _ = _chart_vertical_bars(plan, 0.0, 600.0, 140.0, theme)
    assert bars[0][2].height() == 22.0, "not a square as wide as the bar"


def test_filled_bars_never_go_under_bar_thickness():
    """At the flip width the bars still fit at their minimum, spacing included."""
    theme = _fill_theme(thickness=60.0, spacing=20.0)
    data = _data(6, width_values=2)
    flip = _chart_vertical_min_width(data, _fonts(), theme)
    assert flip is not None and flip >= 6 * (2 * 60.0 + 2.0) + 5 * 20.0
    plan = _chart_plan_for(data, flip, _fonts(), theme)
    assert plan.orientation == "vertical"
    bars, _ = _chart_vertical_bars(plan, 0.0, flip, 140.0, theme)
    assert min(r.width() for _, _, r in bars) >= 60.0 - 1e-9


def test_bar_width_parses_fill_and_ignores_the_rest():
    import tempfile
    from pathlib import Path

    from md2ui.pipeline.theme import parse_theme

    def parsed(value: str) -> str:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "THEME.md"
            path.write_text(f"## Charts\nBar width: {value}\n")
            return parse_theme(path).charts.bar_width

    assert parsed("fill") == "fill" and parsed("Fill") == "fill"
    assert parsed("fixed") == "fixed" and parsed("wide") == "fixed"


# ---------------------------------------------------------------------------
# Values below zero
# ---------------------------------------------------------------------------


def _changes(*values: float):
    return {
        "series": None,
        "unit": "%",
        "rows": [{"label": f"R{i}", "values": [v]} for i, v in enumerate(values)],
    }


def test_a_chart_without_negatives_still_scales_from_zero():
    plan = _plan(_data(5), 800.0)
    assert (plan.scale_min, plan.scale_max) == (0.0, 100.0)


def test_negatives_scale_the_chart_to_the_data_range():
    plan = _plan(_changes(-1.0, 3.0, 1.0, -1.0, 2.0), 800.0)
    assert plan.orientation == "vertical"
    assert (plan.scale_min, plan.scale_max) == (-1.0, 3.0)
    plan = _plan(_changes(-3.0, -1.0, -2.0), 800.0)
    assert (plan.scale_min, plan.scale_max) == (-3.0, 0.0), "zero stays on the scale"


def test_mixed_rows_centre_their_zero():
    plan = _plan(_changes(-1.55, 2.10, -0.40), 800.0)
    assert plan.orientation == "horizontal"
    assert (plan.scale_min, plan.scale_max) == (-2.10, 2.10)


def test_vertical_bars_diverge_from_the_zero_line():
    plan = _plan(_changes(-1.0, 3.0, 1.0, -1.0, 2.0), 800.0)
    assert plan.orientation == "vertical"
    bars, _ = _chart_vertical_bars(plan, 0.0, 800.0, 140.0, Theme())
    zero_y = 105.0  # three quarters down: the scale runs -1 .. 3
    down, up = bars[0][2], bars[1][2]
    assert (down.top(), down.bottom()) == (zero_y, 140.0), "a loss hangs below zero"
    assert (up.top(), up.bottom()) == (0.0, zero_y), "a gain rises from zero"


def test_a_horizontal_loss_ends_at_zero():
    from unittest.mock import patch

    from md2ui.pipeline import render_chart

    plan = _plan(_changes(-1.0, 1.0, 0.5), 220.0)
    assert plan.orientation == "horizontal"
    with patch.object(render_chart, "_chart_bar_rect") as drawn:
        render_chart._draw_chart_rows(
            skia.Surface(240, 240).getCanvas(),
            0.0,
            0.0,
            200.0,
            plan,
            range(3),
            _fonts(),
            Theme(),
            (),
        )
    loss, gain, half = (c.args[1] for c in drawn.call_args_list)
    assert (loss.left(), loss.right()) == (0.0, 100.0)
    assert (gain.left(), gain.right()) == (100.0, 200.0)
    assert (half.left(), half.right()) == (100.0, 150.0)


def test_all_negative_rows_run_from_the_right_edge():
    from unittest.mock import patch

    from md2ui.pipeline import render_chart

    plan = _plan(_changes(-2.0, -1.0), 220.0)
    with (
        patch.object(render_chart, "_chart_bar_rect") as drawn,
        patch.object(render_chart, "_chart_line") as line,
    ):
        render_chart._draw_chart_rows(
            skia.Surface(240, 240).getCanvas(),
            0.0,
            0.0,
            200.0,
            plan,
            range(2),
            _fonts(),
            Theme(),
            (),
        )
    whole, half = (c.args[1] for c in drawn.call_args_list)
    assert (whole.left(), whole.right()) == (0.0, 200.0)
    assert (half.left(), half.right()) == (100.0, 200.0)
    assert not line.called, "zero is the track's own edge"


def test_negative_color_paints_only_bars_below_zero():
    from md2ui.pipeline.render_chart import _chart_bar_color, _chart_series_color

    theme = Theme()
    assert _chart_bar_color(theme, 0, -1.0, ()) == _chart_series_color(theme, 0)
    theme.charts.negative_color = 0xFFE5484D
    assert _chart_bar_color(theme, 0, -1.0, ()) == 0xFFE5484D
    assert _chart_bar_color(theme, 0, 1.0, ()) == _chart_series_color(theme, 0)


# ---------------------------------------------------------------------------
# Chart Grid: tick labels and lines (vertical charts)
# ---------------------------------------------------------------------------


def _grid_theme(labels: bool = True, lines: bool = False) -> Theme:
    t = Theme()
    t.charts.grid.axis_labels = labels
    t.charts.grid.horizontal = lines
    return t


def test_a_chart_without_a_grid_reserves_nothing_for_one():
    plan = _plan(_data(6), 800.0)
    assert plan.orientation == "vertical"
    assert (plan.ticks, plan.axis_w, plan.top_pad) == ([], 0.0, 0.0)


def test_axis_labels_take_a_gutter_and_tick_the_percent_scale():
    theme = _grid_theme()
    plan = _chart_plan_for(_data(6), 800.0, _fonts(), theme)
    assert plan.ticks == [0.0, 25.0, 50.0, 75.0, 100.0]
    assert plan.axis_w > 0.0
    assert plan.height == plan.top_pad + _CHART_VERTICAL_H + 4.0 + plan.label_line_h
    assert plan.top_pad > 0.0, "room for the top label's upper half"


def test_the_gutter_is_part_of_the_flip_width():
    plain = _chart_vertical_min_width(_data(6), _fonts(), Theme())
    theme = _grid_theme()
    gutter = _chart_plan_for(_data(6), 800.0, _fonts(), theme).axis_w
    assert plain is not None
    assert _chart_vertical_min_width(_data(6), _fonts(), theme) == plain + gutter


def test_ticks_round_the_scale_and_keep_zero():
    data = _changes(-1.55, 2.10, -0.40, 1.0, 0.5)
    plan = _chart_plan_for(data, 800.0, _fonts(), _grid_theme(labels=False, lines=True))
    assert plan.axis_w == 0.0, "lines alone take no gutter"
    assert plan.ticks == [-2.0, -1.0, 0.0, 1.0, 2.0, 3.0]
    assert (plan.scale_min, plan.scale_max) == (-2.0, 3.0), "bars meet the lines"


def test_a_horizontal_chart_ignores_the_grid():
    plan = _chart_plan_for(_data(3), 800.0, _fonts(), _grid_theme(lines=True))
    assert plan.orientation == "horizontal"
    assert (plan.ticks, plan.axis_w, plan.scale_max) == ([], 0.0, 100.0)


def test_chart_grid_parses():
    import tempfile
    from pathlib import Path

    from md2ui.pipeline.theme import parse_theme

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(
            "## Charts\n### Chart Grid\nAxis labels: yes\nTicks: 5\n"
            "Horizontal lines: yes\nVertical lines: yes\nLine dash: 4 3\n"
            "- Font size: 10\n"
        )
        grid = parse_theme(path).charts.grid
    assert grid.axis_labels and grid.horizontal and grid.vertical
    assert grid.ticks == 5 and grid.dash == [4.0, 3.0]
    assert grid.text is not None and grid.text.font_size == 10.0


TESTS = [
    test_a_chart_without_a_grid_reserves_nothing_for_one,
    test_axis_labels_take_a_gutter_and_tick_the_percent_scale,
    test_the_gutter_is_part_of_the_flip_width,
    test_ticks_round_the_scale_and_keep_zero,
    test_a_horizontal_chart_ignores_the_grid,
    test_chart_grid_parses,
    test_a_chart_without_negatives_still_scales_from_zero,
    test_negatives_scale_the_chart_to_the_data_range,
    test_vertical_bars_diverge_from_the_zero_line,
    test_a_horizontal_loss_ends_at_zero,
    test_mixed_rows_centre_their_zero,
    test_all_negative_rows_run_from_the_right_edge,
    test_negative_color_paints_only_bars_below_zero,
    test_fixed_bars_stay_thin_and_centred,
    test_filled_bars_span_the_width_with_bar_spacing,
    test_a_filled_bar_floors_at_bar_thickness,
    test_filled_bars_never_go_under_bar_thickness,
    test_bar_width_parses_fill_and_ignores_the_rest,
    test_few_rows_horizontal,
    test_many_rows_wide_vertical,
    test_many_rows_narrow_columns,
    test_many_rows_very_narrow_single_column,
    test_percent_scale_is_100,
    test_over_100_scales_to_peak,
    test_series_legend_reserved,
    test_multi_series_values_shape,
    test_horizontal_height_accounts_rows_and_gaps,
    test_horizontal_height_accounts_for_track_inner_padding,
    test_vertical_height_uses_chart_area,
    test_leaf_height_uses_plan,
    test_the_flip_point_is_the_width_the_plan_flips_at,
    test_a_chart_that_never_goes_vertical_has_no_flip_point,
    test_the_flip_point_grows_with_the_labels,
]

if __name__ == "__main__":
    print("Chart Plan Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓ {test.__name__}")
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} of {len(TESTS)} tests FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
