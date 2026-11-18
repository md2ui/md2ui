"""
``Line align`` on an authored ``:::`` row — the vertical axis, per level.

``Line align`` is ``Align``'s vertical twin: it takes
``top`` / ``baseline`` (the default) / ``center`` / ``bottom``, lives on
``### Root`` / ``### Heading 1``…``6`` / ``### Elements`` / ``### Image Cards``,
and inherits the same way. It reaches only authored rows, same-line
(``node.line_split``) and ``:::``, so a theme value never restacks a card grid
the author did not ask for.

This is the PROPORTIONED row -- one with a number (``:::1``). A row with no
number is laid out as a same-line row is (``line_split``), so it aligns as one:
``test_an_unnumbered_row_aligns_as_a_line``.

One difference from a same-line row: **``baseline`` reads as ``top`` here.** A
same-line row's cells are the words of one line and share a text baseline; a
``:::`` row's cells come from different source lines and mostly stack, so there
is no shared line to hang them from. That is the same answer the baseline branch
already gives a row whose cells all stack.

Two things that are NOT alignment and are easy to mistake for a bug when
writing probes for this: an image leaf and a heading-section cell are both
STRETCHED to the row height, so they have no slack and never move in any mode.
A row of only those two is identical under every value.

Run with: uv run python tests/layout_column_valign_tests.py
"""

from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.markdown_grouper import ASTPatternAnalyzer, MarkdownGrouper
from md2ui.pipeline.render_measure import _box_valign_offsets, _row_valign_offsets
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import Theme


def a_row(weights: str = ":::1") -> LayoutNode:
    """The ``column_row`` LayoutNode for a two-cell document."""
    g = MarkdownGrouper(f"Alpha\n{weights}\nBeta\n")
    g.to_ast()
    assert g.ast is not None
    ASTPatternAnalyzer(g.ast).fingerprints(include_unique=True)
    lay = LayoutGenerator().generate(g.ast, 900.0, None)

    def walk(n):
        yield n
        for c in n.children:
            yield from walk(c)

    return next(n for n in walk(lay) if getattr(n, "column_row", False))


def offsets(node: LayoutNode, mode: str | None, heights: list[float]) -> list[float]:
    """``_row_valign_offsets`` for *node* under a root ``Line align`` of *mode*."""
    theme = Theme()
    if mode is not None:
        theme.root.line_align = mode
    children = node.children
    return _row_valign_offsets(
        node,
        children,
        [100.0] * len(children),
        heights,
        [None] * len(children),
        {},
        FontSet.__new__(FontSet),
        theme,
    )


# ---------------------------------------------------------------------------
# 1 — the gate admits a column row
# ---------------------------------------------------------------------------


def test_a_column_row_is_aligned_by_the_level():
    row = a_row()
    assert offsets(row, "bottom", [40.0, 10.0]) == [0.0, 30.0]


def test_center_splits_the_slack():
    assert offsets(a_row(), "center", [40.0, 10.0]) == [0.0, 15.0]


def test_top_moves_nothing():
    assert offsets(a_row(), "top", [40.0, 10.0]) == [0.0, 0.0]


def test_baseline_reads_as_top_on_a_column_row():
    # A `:::` row's cells are blocks from different source lines, so there is no
    # shared text line to hang a baseline from. The DEFAULT must therefore be
    # inert here, exactly as `top` is.
    row = a_row()
    assert offsets(row, "baseline", [40.0, 10.0]) == [0.0, 0.0]
    assert offsets(row, "baseline", [40.0, 10.0]) == offsets(row, "top", [40.0, 10.0])


def test_the_default_is_inert():
    # No `Line align` written anywhere == baseline == top, on a column row.
    assert offsets(a_row(), None, [40.0, 10.0]) == [0.0, 0.0]


# ---------------------------------------------------------------------------
# 2 — it reaches a column row without touching anything else
# ---------------------------------------------------------------------------


def test_an_unflagged_row_is_still_ignored():
    # The gate is `line_split or column_row`. A plain row — a card grid, a
    # gutter-marker row — must still be untouched by the theme, which is why
    # the key is scoped this narrowly.
    row = a_row()
    row.column_row = False
    assert offsets(row, "bottom", [40.0, 10.0]) == [0.0, 0.0]


def test_a_single_cell_row_moves_nothing():
    # `n < 2` guard: nothing to align against.
    row = a_row()
    row.children = row.children[:1]
    assert offsets(row, "bottom", [40.0]) == [0.0]


def test_the_arithmetic_is_the_shared_one():
    # `center`/`bottom` go through `_box_valign_offsets`, the same helper the
    # per-cell `content_valign` hint uses, so the two channels can never
    # disagree about what "bottom" means.
    heights = [40.0, 10.0]
    assert offsets(a_row(), "bottom", heights) == _box_valign_offsets(
        "bottom", heights, [False, False]
    )


def test_an_unnumbered_row_aligns_as_a_line():
    # No number: the row is a line of blocks, like `A - B`, so it takes the
    # line's gate and its baseline default rather than the column row's.
    g = MarkdownGrouper("Alpha\n:::\nBeta\n")
    g.to_ast()
    assert g.ast is not None
    ASTPatternAnalyzer(g.ast).fingerprints(include_unique=True)
    lay = LayoutGenerator().generate(g.ast, 900.0, None)
    row = lay.children[0]
    assert row.type == "row" and row.line_split, row
    assert not getattr(row, "column_row", False)
    assert offsets(row, "bottom", [40.0, 10.0]) == [0.0, 30.0]


TESTS = [
    test_a_column_row_is_aligned_by_the_level,
    test_center_splits_the_slack,
    test_top_moves_nothing,
    test_baseline_reads_as_top_on_a_column_row,
    test_the_default_is_inert,
    test_an_unnumbered_row_aligns_as_a_line,
    test_an_unflagged_row_is_still_ignored,
    test_a_single_cell_row_moves_nothing,
    test_the_arithmetic_is_the_shared_one,
]

if __name__ == "__main__":
    print("Layout Column Valign Tests")
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
