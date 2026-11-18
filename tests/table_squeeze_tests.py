"""
Unit tests for the renderer's table width fallback (``_table_plan``) when the
grid does not fit its container.

Three regimes, narrowest container last: natural widths fit, chrome (per-cell
padding.x + column gaps) squeezes to ``TABLE_SQUEEZE_FLOOR`` to buy the fit, and
past that floor the grid keeps every column at its minimum-unbreakable width and
OVERFLOWS. That last one is the regression guard: scaling the columns down to
fit would hand a chip a cell narrower than itself, and a pill does not shrink at
draw time, so neighbouring chips would draw on top of each other.

Run with: uv run tests/table_squeeze_tests.py
"""

import skia

from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.render_measure import (
    TABLE_SQUEEZE_FLOOR,
    _table_cell_min_width,
    _table_plan,
)
from md2ui.pipeline.render_place import _place_table_boxes
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import Theme

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COLS = ("Mon", "Tue", "Wed")
DAYS = (("29", "30", "31"), ("5", "6", "7"))


def _fonts() -> FontSet:
    tf = skia.Typeface.MakeDefault()
    return FontSet(tf, tf, tf, tf, tf)


def _theme(*, stacking: bool = False, cell_pad: float = 0.0) -> Theme:
    """A table theme with rounded chips, like the calendar card's."""
    t = Theme()
    t.tables.stacking = stacking
    t.tables.table.row_spacing = 4.0
    t.inline_code.corner_radius = 20.0
    t.inline_code.padding.left = 12.0
    t.inline_code.padding.right = 12.0
    for style in (t.tables.header, t.tables.cells):
        style.padding.left = cell_pad
        style.padding.right = cell_pad
    return t


def _node_index() -> dict:
    idx = {}
    for name in COLS:
        idx[f"h-{name}"] = {"type": "text", "content": name, "table_role": "header"}
    for row in DAYS:
        for day in row:
            idx[f"d-{day}"] = {
                "type": "inline_code",
                "content": day,
                "table_role": "body",
            }
    return idx


def _cell(content_id: str) -> LayoutNode:
    return LayoutNode(type="-", ratios=[], children=[], content_id=content_id)


def _table() -> LayoutNode:
    rows = [
        LayoutNode(
            type="row",
            ratios=[],
            children=[_cell(f"h-{c}") for c in COLS],
            table_row="header",
        )
    ]
    rows += [
        LayoutNode(
            type="row",
            ratios=[],
            children=[_cell(f"d-{d}") for d in row],
            table_row="body",
        )
        for row in DAYS
    ]
    return LayoutNode(type="col", ratios=[], children=rows, table=True)


def _col_mins(table: LayoutNode, node_index: dict, fonts, theme) -> list[float]:
    """Per-column minimum-unbreakable width + that role's cell padding.x —
    the same maxima ``_table_plan`` folds into ``mins``."""
    n_cols = max(len(r.children) for r in table.children)
    mins = [0.0] * n_cols
    for r in table.children:
        pad = (
            theme.tables.header if r.table_row == "header" else theme.tables.cells
        ).padding
        for j, cell in enumerate(r.children):
            c_min = _table_cell_min_width(cell, node_index, fonts, theme, 10_000.0)
            mins[j] = max(mins[j], c_min + pad.x)
    return mins


def test_zebra_stripe_color_reaches_each_cells_background_stack():
    theme = _theme()
    first, stripe = 0xFF111111, 0xFFEEEEEE
    theme.tables.cells.bg_colors = [first, stripe]
    boxes = _place_table_boxes(
        _table(),
        0,
        0,
        300,
        _node_index(),
        _fonts(),
        theme,
        None,
        None,
        None,
        frozenset(),
        [],
        0,
    )
    body = [box for box in boxes if box.content_id and box.content_id.startswith("d-")]
    assert [box.bg_stack[0] for box in body] == [first] * 3 + [stripe] * 3


def _cell_widths(plan) -> list[float]:
    """The first body row's placed cell widths, in column order."""
    n = len(COLS)
    return [c[3] for c in plan.cells[n : 2 * n]]


def _fits(table, node_index, fonts, theme) -> float:
    """The container width at which the columns' minima exactly fit."""
    mins = _col_mins(table, node_index, fonts, theme)
    return sum(mins) + (len(mins) - 1) * theme.tables.table.row_spacing


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_wide_table_spreads_to_fill():
    """Room to spare: the columns take their natural widths and the surplus is
    distributed, so the table fills the width it was given."""
    fonts, theme, node_index = _fonts(), _theme(), _node_index()
    table = _table()
    available = _fits(table, node_index, fonts, theme) * 3
    plan = _table_plan(table, available, node_index, fonts, theme)
    assert plan.mode == "grid", plan.mode
    assert abs(plan.width - available) < 0.5, (plan.width, available)
    print(f"  ✓  a wide table fills its width ({plan.width:.1f} of {available:.1f})")


def test_squeeze_stage_never_goes_under_a_column_minimum():
    """Between the natural and minimum totals the chrome compresses — but every
    column still gets at least its widest unbreakable unit."""
    fonts, theme, node_index = _fonts(), _theme(cell_pad=16.0), _node_index()
    table = _table()
    mins = _col_mins(table, node_index, fonts, theme)
    # Just inside the squeeze stage: below the minima, above the chrome floor.
    available = _fits(table, node_index, fonts, theme) - 8.0
    plan = _table_plan(table, available, node_index, fonts, theme)
    assert plan.mode == "grid", plan.mode
    widths = _cell_widths(plan)
    content_mins = [m - theme.tables.cells.padding.x for m in mins]
    for j, (w, c) in enumerate(zip(widths, content_mins)):
        assert w + 0.01 >= c, f"col {j}: cell {w:.1f} < content min {c:.1f}"
    print("  ✓  the squeeze stage holds every column at its content minimum")


def test_below_the_floor_the_grid_overflows_instead_of_scaling():
    """THE regression guard. Handed far less than its minimum, the grid keeps
    each column at its unbreakable width and overflows — it must never scale a
    cell under the pill that has to be drawn in it."""
    fonts, theme, node_index = _fonts(), _theme(), _node_index()
    table = _table()
    mins = _col_mins(table, node_index, fonts, theme)
    available = _fits(table, node_index, fonts, theme) * 0.6  # well under the floor
    plan = _table_plan(table, available, node_index, fonts, theme)

    assert plan.mode == "grid", f"stacking is off; expected grid, got {plan.mode}"
    widths = _cell_widths(plan)
    assert len(widths) == len(COLS), widths
    for j, (w, m) in enumerate(zip(widths, mins)):
        assert w + 0.01 >= m, f"col {j}: cell {w:.1f} scaled under its min {m:.1f}"
    assert plan.width > available, (
        f"expected the grid to overflow, got {plan.width:.1f} in {available:.1f}"
    )
    print(
        f"  ✓  under the floor the grid overflows ({plan.width:.1f} in "
        f"{available:.1f}) with no column under its minimum"
    )


def test_below_the_floor_stacking_theme_still_stacks():
    """The overflow is the fallback only when the theme forbids stacking cards;
    a stacking theme still reaches cards mode at the same point."""
    fonts, theme, node_index = _fonts(), _theme(stacking=True), _node_index()
    table = _table()
    available = _fits(table, node_index, fonts, theme) * 0.6
    plan = _table_plan(table, available, node_index, fonts, theme)
    assert plan.mode == "cards", plan.mode
    print("  ✓  a stacking theme still stacks below the floor")


def test_squeeze_floor_is_a_chrome_floor_only():
    """``TABLE_SQUEEZE_FLOOR`` bounds the chrome, never the glyphs: with zero
    cell padding and zero column gaps there is no chrome to squeeze, and the
    columns come out at exactly their content minima."""
    fonts, node_index = _fonts(), _node_index()
    theme = _theme()
    theme.tables.table.row_spacing = 0.0
    table = _table()
    mins = _col_mins(table, node_index, fonts, theme)
    plan = _table_plan(table, sum(mins) * 0.5, node_index, fonts, theme)
    for j, (w, m) in enumerate(zip(_cell_widths(plan), mins)):
        assert abs(w - m) < 0.01, f"col {j}: {w:.1f} != min {m:.1f}"
    print(f"  ✓  with no chrome the floor ({TABLE_SQUEEZE_FLOOR}) changes nothing")


TESTS = [
    test_zebra_stripe_color_reaches_each_cells_background_stack,
    test_wide_table_spreads_to_fill,
    test_squeeze_stage_never_goes_under_a_column_minimum,
    test_below_the_floor_the_grid_overflows_instead_of_scaling,
    test_below_the_floor_stacking_theme_still_stacks,
    test_squeeze_floor_is_a_chrome_floor_only,
]


if __name__ == "__main__":
    for t in TESTS:
        t()
    print(f"\n{len(TESTS)} tests passed")
