"""Chart text and code blocks follow ``## Color Replacements``.

A chart's labels, values, legend and tick labels resolve against the surface the
chart sits on, as its bars do. A code block is a pill: its fill resolves
against what it sits on, and its runs, fade and copy button then against that
replaced fill.
"""

import sys
from unittest.mock import MagicMock

sys.path.insert(0, "tests")

from chart_plan_tests import _data, _fonts, _grid_theme, _plan
from line_chart_tests import _data as _line_data
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_chart import (
    _chart_plan_for,
    _draw_chart_grid,
    _draw_chart_legend,
    _draw_chart_rows,
)
from md2ui.pipeline.render_code_blocks import draw_code_block
from md2ui.pipeline.render_fills import _paint_layered_fill
from md2ui.pipeline.render_line_chart import draw_line_chart
from md2ui.pipeline.theme import Theme

DARK = 0xFF18181B
INK = 0xFF7C7C84
WHITE = 0xFFFFFFFF
CODE = 0xFF002B0A
RED = 0xFFFF0000
BLUE = 0xFF0000FF
GREEN = 0xFF00FF00


def _text_inks(canvas: MagicMock) -> set[int]:
    return {c.args[4].getColor() for c in canvas.drawString.call_args_list}


def _ink_theme(theme: Theme) -> Theme:
    theme.labels.color = INK
    theme.color_replacements = {DARK: {"text": {INK: WHITE}}}
    return theme


def test_chart_rows_labels_and_values_are_replaced():
    canvas = MagicMock()
    plan = _plan(_data(3), 220.0)
    theme = _ink_theme(Theme())
    _draw_chart_rows(canvas, 0.0, 0.0, 200.0, plan, range(3), _fonts(), theme, (DARK,))
    assert _text_inks(canvas) == {WHITE}
    print("  ✓  chart row labels and values follow the dark card's rule")


def test_chart_legend_is_replaced():
    canvas = MagicMock()
    plan = _plan(_data(2, series=["A", "B"], width_values=2), 220.0)
    theme = _ink_theme(Theme())
    _draw_chart_legend(canvas, 0.0, 0.0, plan, _fonts(), theme, (DARK,))
    assert _text_inks(canvas) == {WHITE}
    print("  ✓  a chart legend follows the dark card's rule")


def test_chart_tick_labels_are_replaced():
    canvas = MagicMock()
    theme = _ink_theme(_grid_theme())
    plan = _chart_plan_for(_data(6), 800.0, _fonts(), theme)
    _draw_chart_grid(
        canvas, plan, 40.0, 700.0, 200.0, [], _data(6), _fonts(), theme, (DARK,)
    )
    assert _text_inks(canvas) == {WHITE}
    print("  ✓  chart tick labels follow the dark card's rule")


def test_line_chart_ticks_are_replaced():
    canvas = MagicMock()
    theme = _ink_theme(Theme())
    box = LayoutBox(x=0.0, y=0.0, width=200.0, height=120.0, bg_stack=(DARK,))
    data = _line_data(1.0, 2.0, 3.0, ticks={0: "Apr", 2: "Jun"})
    draw_line_chart(canvas, box, data, _fonts(), theme)
    assert _text_inks(canvas) == {WHITE}
    print("  ✓  line chart tick labels follow the dark card's rule")


def _code_block(theme: Theme) -> MagicMock:
    canvas = MagicMock()
    box = LayoutBox(x=0.0, y=0.0, width=300.0, height=80.0, bg_stack=(DARK,))
    face = _fonts().typeface
    draw_code_block(
        canvas, box, "x = 1", "python", face, theme, paint_fill=_paint_layered_fill
    )
    return canvas


def test_code_block_fill_and_runs_are_replaced():
    theme = Theme()
    theme.code_blocks.background_color = CODE
    theme.code_blocks.copy_icon = None
    theme.color_replacements = {
        DARK: {"fill": {CODE: RED}},
        RED: {"text": {None: BLUE}},
    }
    canvas = _code_block(theme)
    assert canvas.drawRoundRect.call_args_list[0].args[3].getColor() == RED
    assert _text_inks(canvas) == {BLUE}, "runs key on the replaced fill"
    print("  ✓  a code block's fill and runs follow the surface it sits on")


def test_copy_button_stroke_is_replaced_against_the_block():
    theme = Theme()
    theme.code_blocks.background_color = CODE
    theme.code_blocks.copy_icon = "C"
    theme.code_blocks.copy_button.stroke_width = 2.0
    theme.code_blocks.copy_button.stroke_color = WHITE
    theme.color_replacements = {CODE: {"stroke": {WHITE: GREEN}}}
    canvas = _code_block(theme)
    stroke = canvas.drawRoundRect.call_args_list[-1].args[3]
    assert stroke.getColor() == GREEN, "block fill, button fill, then its stroke"
    print("  ✓  the copy button's stroke follows the code block's fill")


TESTS = [
    test_chart_rows_labels_and_values_are_replaced,
    test_chart_legend_is_replaced,
    test_chart_tick_labels_are_replaced,
    test_line_chart_ticks_are_replaced,
    test_code_block_fill_and_runs_are_replaced,
    test_copy_button_stroke_is_replaced_against_the_block,
]
