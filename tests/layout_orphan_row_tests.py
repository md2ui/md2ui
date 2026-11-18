"""
Unit tests for THEME.md ``Orphan row`` — what a repeated-item grid's RAGGED
final row (fewer cells than columns) does with the width the missing cells
would have used.

    left      one column's width, packed from the left edge (the default)
    center    that same width, with the leftover split either side
    stretch   the cells that are there share the whole row

``stretch`` is settled in the GENERATOR, not the renderer: ``_grid_rows`` builds
each cell at the width it hands down, so a cell arranged as a narrow card cannot
be widened afterwards without painting a wide box around a narrow interior.
``center`` never changes a width, so it is a placement shift in
``_layout_grid_row``. The mode is read from the style of the section that owns
the grid, a fixed style included, which replaces its heading level whole.

Run with: uv run python tests/layout_orphan_row_tests.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "tests")

from markdown_datapoint_split_tests import _processed_with_criteria

from md2ui.pipeline import render_place as RPL
from md2ui.pipeline import render_style as RST
from md2ui.pipeline import layout_render as LR
from md2ui.pipeline import render_measure as RMS
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.theme import Theme, parse_theme
from md2ui.utils.font_loader import (
    load_custom_fonts,
    resolve_typeface,
    weight_from_str,
)

TOL = 1.0  # px

# Five same-kind sections, laid out at a width that fits two: they grid 2+2+1,
# leaving a ONE-cell ragged row — the widest gap the three modes can show.
#
# The width matters. A wider one grids 3+2 (the last-row fill rule,
# `_balance_cols` / `_balance_kind_cols`, refuses a lone cell after a wider row),
# which is not ragged enough to tell the modes apart. A 2-column grid ending in
# one cell is exactly the fill floor and is deliberately allowed, so it is the
# stable fixture for this key; 335 sits in the narrow band where it holds.
# The lines are colon columns: a `Key: value` line is one text (ADR-205), and a
# card of plain lines is built alike at any width, so a stretched cell could not
# show it was arranged wider.
_RUN = "\n\n".join(
    f"### Item {i}\n\nQuantity : {i} kg\n\nPrice : ${i}0.00" for i in range(1, 6)
)


# The theme this fixture needs, and nothing else: element group spacing and
# padding decide that five items grid 2+2+1 at the fixture width. Inline, so a
# change to the shipped THEME.md cannot move it.
_FIXTURE_THEME = """## Styling & Spacing
### Elements
Group spacing: 24
Padding: 16
"""


def _fixture_theme():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "THEME.md"
        path.write_text(_FIXTURE_THEME)
        return parse_theme(path)


def _themed(mode: str | None):
    theme = _fixture_theme()
    if mode is not None:
        theme.root.orphan_row = mode
    custom = load_custom_fonts(theme.font_paths)
    bw = weight_from_str(theme.text.font_weight)

    def tf(w, i):
        return resolve_typeface(theme.text.font_name or "Arial", w, i, custom)

    return theme, RST.FontSet(
        tf(bw, False),
        tf(700, False),
        tf(bw, True),
        tf(700, True),
        tf(bw, False),
        None,
        {},
    )


def _ragged_row(mode: str | None, width: float = 335.0):
    """``(row, available, placements)`` for the run's ragged final grid row."""
    theme, fonts = _themed(mode)
    ast = _processed_with_criteria(_RUN)
    idx: dict = {}
    LR._walk(ast.to_dict(), idx)
    w = LR._content_width(width)
    layout = LayoutGenerator().generate(
        ast,
        w,
        theme,
        measure=LR.make_layout_measurer(idx, fonts, theme),
        measure_width=LR.make_width_measurer(fonts, theme),
        measure_line=LR.make_line_width_measurer(fonts, theme),
        measure_marker=LR.make_marker_measurer(fonts, theme),
    )
    RPL.bake_render_cascade(layout, theme=theme)

    def walk(n):
        yield n
        for c in n.children:
            yield from walk(c)

    grids = [n for n in walk(layout) if n.type == "row" and n.grid]
    assert grids, "fixture must grid"
    ragged = [g for g in grids if len(g.children) == 1]
    assert len(ragged) == 1, [(len(g.children), g.grid_cols) for g in grids]
    row = ragged[0]
    # The grid fills whatever its parent hands it; the full rows and the ragged
    # one share that width, so measure it off a FULL row's own arithmetic.
    full = next(g for g in grids if len(g.children) > 1)
    placements, _h, _gaps = RMS._layout_grid_row(row, w, idx, fonts, theme)
    return row, full, w, placements


def test_left_is_the_default_and_packs_from_zero():
    row, full, w, placements = _ragged_row(None)
    assert Theme().root.orphan_row == "left"
    assert row.grid_cols == full.grid_cols, (row.grid_cols, full.grid_cols)
    assert (row.render_properties or {}).get("orphan_row") is None, (
        "the default must stamp nothing — it has to stay byte-for-byte inert"
    )
    _child, offset, cell_w, *_rest = placements[0]
    assert abs(offset) < TOL, offset
    assert cell_w < w / 2, (cell_w, w)
    print(f"  ✓  left: one column ({cell_w:.0f} of {w:.0f}), offset 0")


def test_center_splits_the_leftover_either_side():
    row, _full, w, placements = _ragged_row("center")
    assert (row.render_properties or {}).get("orphan_row") == "center"
    _child, offset, cell_w, *_rest = placements[0]
    _lrow, _lfull, _lw, left_placements = _ragged_row(None)
    assert abs(cell_w - left_placements[0][2]) < TOL, "width must not change"
    assert abs(offset - (w - cell_w) / 2.0) < TOL, (offset, w, cell_w)
    assert offset > TOL, "the cell really moved"
    print(f"  ✓  center: same width, offset {offset:.0f} = half the slack")


def test_stretch_rebuilds_the_ragged_row_at_full_width():
    row, full, w, placements = _ragged_row("stretch")
    assert row.grid_cols == 1, row.grid_cols
    assert full.grid_cols > 1, "the FULL rows keep their column count"
    assert len(row.ratios) == 1, row.ratios
    _child, offset, cell_w, *_rest = placements[0]
    assert abs(offset) < TOL, offset
    assert abs(cell_w - w) < TOL, (cell_w, w)
    print(f"  ✓  stretch: the lone cell owns the row ({cell_w:.0f} of {w:.0f})")


def test_stretch_is_decided_before_the_cell_is_built():
    """The point of doing it in the generator: the ragged cell is ARRANGED at
    the wider width, so its interior re-wraps. A renderer-only stretch would
    paint a wide box around a narrow card's layout."""
    narrow, _f1, _w1, _p1 = _ragged_row(None)
    wide, _f2, _w2, _p2 = _ragged_row("stretch")

    def shape(n):
        return (n.type, len(n.children), tuple(c.type for c in n.children))

    assert shape(narrow.children[0]) != shape(wide.children[0]) or (
        narrow.children[0].ratios != wide.children[0].ratios
    ), "the stretched cell must be built differently, not merely placed wider"
    print("  ✓  stretch changes how the cell is BUILT, not just where it sits")


def test_mode_resolves_without_a_theme():
    """Hand-built fixtures run with ``_theme = None``."""
    gen = LayoutGenerator()
    assert gen._orphan_row_mode(0) == "left"
    assert gen._orphan_row_mode(3) == "left"
    theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    gen._theme = theme
    theme.root.orphan_row = "stretch"
    assert gen._orphan_row_mode(0) == "stretch"
    st = theme.sections.get(2)
    if st is not None:
        st.orphan_row = "center"
        assert gen._orphan_row_mode(2) == "center", "a level beats the root"
    print("  ✓  the mode resolves with no theme, and a level beats the root")


_BAND_THEME = """## Styling & Spacing
### Root
Padding: 24
### Fixed styles
#### Band
Padding: 24
Orphan row: Center
"""

_BAND = "# {#band-1}\n\n" + "\n\n".join(
    f"#### {title}\n{line}\n[`Open`](/x)"
    for title, line in (
        (
            "Become a Dasher",
            "As a delivery driver, make money and work on your own schedule.",
        ),
        (
            "Become a Merchant",
            "Attract new customers and grow your sales, starting today.",
        ),
        (
            "Get the app",
            "Experience the best your neighbourhood has to offer, in one app.",
        ),
    )
)


def test_a_fixed_style_owns_its_grids_orphan_row():
    # The band's own fixed style decides, not the first card's (which has none) nor
    # `### Heading 1`, which the fixed style replaces.
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "THEME.md"
        path.write_text(_BAND_THEME)
        theme = parse_theme(path)
    _theme, fonts = _themed(None)
    ast = _processed_with_criteria(_BAND)
    idx: dict = {}
    LR._walk(ast.to_dict(), idx)
    w = LR._content_width(767.0)
    layout = LayoutGenerator().generate(
        ast,
        w,
        theme,
        measure=LR.make_layout_measurer(idx, fonts, theme),
        measure_width=LR.make_width_measurer(fonts, theme),
        measure_line=LR.make_line_width_measurer(fonts, theme),
        measure_marker=LR.make_marker_measurer(fonts, theme),
    )

    def walk(n):
        yield n
        for c in n.children:
            yield from walk(c)

    grids = [n for n in walk(layout) if n.type == "row" and n.grid]
    ragged = [g for g in grids if len(g.children) < (g.grid_cols or 0)]
    assert ragged, [(len(g.children), g.grid_cols) for g in grids]
    modes = [(g.render_properties or {}).get("orphan_row") for g in ragged]
    assert modes == ["center"], modes
    print("  ✓  a fixed style states its grid's orphan row, as a heading level does")


TESTS = [
    test_left_is_the_default_and_packs_from_zero,
    test_center_splits_the_leftover_either_side,
    test_stretch_rebuilds_the_ragged_row_at_full_width,
    test_stretch_is_decided_before_the_cell_is_built,
    test_mode_resolves_without_a_theme,
    test_a_fixed_style_owns_its_grids_orphan_row,
]

if __name__ == "__main__":
    print("Orphan-Row (ragged grid row) Tests")
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
