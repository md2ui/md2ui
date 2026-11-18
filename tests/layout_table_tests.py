"""
Unit tests for the generator's deterministic table layout: a ``table_group``
container becomes a ``table`` col of ``table_row`` rows (equal-ratio cells).
The theme's icon aside is consulted on it like any other group (the gate is
node-kind agnostic) but cannot disturb the rows: an aside needs
a lone-emoji child, first or last, which a table's row structure never is.
Run with: uv run layout_table_tests.py
"""

from layout_bento_tests import _ast, _group, _leaf
from layout_decision_scope_tests import RecordingGenerator, aside_theme
from md2ui.pipeline.layout_generator import LayoutGenerator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cell(content: str, role: str, align: str | None = None) -> dict:
    d = _leaf(content, "one_word")
    d["type"] = "table_cell"
    d["table_role"] = role
    if align is not None:
        d["table_align"] = align
    return d


def _table_row(row_type: str, *cells: str, aligns: tuple | None = None) -> dict:
    """*aligns*, when given, is the per-column alignment the grouper read off
    the markdown delimiter row (None for a colon-less column)."""
    role = "header" if row_type == "table_header" else "body"
    cols = aligns or (None,) * len(cells)
    d = _group(*[_cell(c, role, a) for c, a in zip(cells, cols)])
    d["type"] = row_type
    return d


def _table(*rows: dict, **flags) -> dict:
    d = _group(*rows, table_group=True, **flags)
    return d


def _doc_table(**flags):
    return _ast(
        _group(
            _table(
                _table_row("table_header", "Name", "Price", "Stock"),
                _table_row("table_row", "Widget", "$9", "12"),
                _table_row("table_row", "Gadget", "$19", "3"),
                **flags,
            )
        )
    )


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def _find_table(layout):
    tables = [n for n in _walk(layout) if getattr(n, "table", False)]
    assert len(tables) == 1, f"expected 1 table col, got {len(tables)}"
    return tables[0]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_table_group_builds_table_col_of_rows():
    layout = LayoutGenerator().generate(_doc_table(), 1280.0)
    table = _find_table(layout)
    assert table.type == "col", f"table container should be col, got {table.type}"
    assert [r.table_row for r in table.children] == ["header", "body", "body"]
    assert all(r.type == "row" for r in table.children)
    print("  ✓  table_group → col(table) of row(table_row=header/body/body)")


def test_table_cells_equal_ratios_and_roles():
    layout = LayoutGenerator().generate(_doc_table(), 1280.0)
    table = _find_table(layout)
    for row in table.children:
        assert row.ratios == [1.0] * 3, f"ratios: {row.ratios}"
        assert len(row.children) == 3
        assert all(c.in_table == row.table_row for c in row.children), (
            f"cell roles: {[c.in_table for c in row.children]}"
        )
    print("  ✓  rows keep equal ratios; cells carry in_table role")


def test_table_structure_survives_an_aside_source():
    """A table group is consulted like any other, but its row structure must
    survive.

    The gate does not refuse table groups outright. What protects the table is
    the aside's own eligibility rule — it needs a lone-emoji child, first or
    last — which a header/body row structure does not satisfy, so the node
    falls back to the rules with its rows intact.
    """
    gen = RecordingGenerator()
    layout = gen.generate(
        _doc_table(glued_content_group=True), 1280.0, theme=aside_theme()
    )
    assert gen.consulted, "the aside was never consulted at all"
    table = _find_table(layout)
    assert [r.table_row for r in table.children] == ["header", "body", "body"]
    print("  ✓  table group consulted, rows intact (aside ineligible)")


def test_single_row_table_keeps_table_identity():
    doc = _ast(_group(_table(_table_row("table_header", "Only", "Header"))))
    layout = LayoutGenerator().generate(doc, 1280.0)
    table = _find_table(layout)
    assert len(table.children) == 1
    assert table.children[0].table_row == "header"
    print("  ✓  single-row table: no passthrough, table identity kept")


def test_table_min_width_is_per_column_maxima():
    # Wide cells sit in DIFFERENT rows: per-row sums are 110 each, but the
    # column-aligned min is 100 + 100 = 200 (each column must fit its widest
    # cell). The grid packer must see 200, or it grants cells less than the
    # renderer's stacking threshold.
    from md2ui.pipeline.generator_units import _measured_min_width

    doc = _doc_table()  # header: Name/Price/Stock — 3 cols
    table = doc.children[0]

    def fake_measure(node):
        return {"Widget": 100.0, "$9": 10.0, "Gadget": 10.0, "$19": 100.0}.get(
            node.content, 10.0
        )

    per_col = _measured_min_width(table, fake_measure, None, {})
    row_mins = [_measured_min_width(r, fake_measure, None, {}) for r in table.children]
    assert per_col == 100.0 + 100.0 + 10.0, f"per-column min: {per_col}"
    assert per_col > max(row_mins), (
        f"container min {per_col} must exceed widest row sum {max(row_mins)}"
    )
    print("  ✓  table min = per-column maxima sum, not widest row sum")


def test_column_alignment_reaches_the_cell_as_content_align():
    """The delimiter row's `:---` / `:---:` / `---:` arrives on the built cell as
    ``content_align`` — the channel every leaf kind already resolves through
    (render_style._resolve_h_align). A colon-less column writes nothing, so it
    keeps inheriting the theme / the enclosing section's cascade."""
    aligns = ("left", None, "right")
    doc = _ast(
        _group(
            _table(
                _table_row("table_header", "Name", "Price", "Stock", aligns=aligns),
                _table_row("table_row", "Widget", "$9", "12", aligns=aligns),
            )
        )
    )
    table = _find_table(LayoutGenerator().generate(doc, 900.0))

    for row in table.children:
        got = [(c.render_properties or {}).get("content_align") for c in row.children]
        assert got == list(aligns), (
            f"[{row.table_row}] got {got}, expected {list(aligns)}"
        )
    print("  ✓  a column's authored alignment reaches the cell as content_align")


def test_an_unaligned_table_writes_no_content_align():
    """No colons, no render property: an unaligned table keeps the theme's
    cascade."""
    table = _find_table(LayoutGenerator().generate(_doc_table(), 900.0))
    for row in table.children:
        for cell in row.children:
            assert not (cell.render_properties or {}).get("content_align"), (
                cell.render_properties
            )
    print("  ✓  an unaligned table writes no content_align at all")


TESTS = [
    test_table_group_builds_table_col_of_rows,
    test_table_cells_equal_ratios_and_roles,
    test_table_structure_survives_an_aside_source,
    test_single_row_table_keeps_table_identity,
    test_table_min_width_is_per_column_maxima,
    test_column_alignment_reaches_the_cell_as_content_align,
    test_an_unaligned_table_writes_no_content_align,
]

if __name__ == "__main__":
    print("Layout Table Tests")
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
