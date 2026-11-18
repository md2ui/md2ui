"""
Unit tests for MarkdownGrouper._subgroup_tables_walk, _parse_table,
and _parse_row_cells.
Run with: uv run markdown_table_tests.py
"""

from md2ui import session
from md2ui.pipeline.grouper_block_splits import _split_blank_lines
from md2ui.pipeline.grouper_displays import _flag_table_groups
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.markdown_grouper import MarkdownGrouper

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def assert_node(
    node: MarkdownGroupNode,
    label: str,
    content: str = "",
    n_children: int = 0,
    ctx: str = "",
) -> None:
    prefix = f"[{ctx}] " if ctx else ""
    assert node.type == label, f"{prefix}label: got {node.type!r}, expected {label!r}"
    assert node.content == content, (
        f"{prefix}content: got {node.content!r}, expected {content!r}"
    )
    assert len(node.children) == n_children, (
        f"{prefix}n_children: got {len(node.children)}, expected {n_children}"
    )


def after_table_walk(text: str) -> MarkdownGroupNode:
    """Run to_ast + blank-split + table-walk (matches pipeline order)."""
    g = MarkdownGrouper(text)
    g.to_ast()
    assert g.ast is not None
    g._subgroup_content(g.ast, _split_blank_lines)
    g._subgroup_tables_walk(g.ast)
    return g.ast


def make_grouper() -> MarkdownGrouper:
    g = MarkdownGrouper("")
    g.to_ast()
    return g


# ---------------------------------------------------------------------------
# Group A — _parse_row_cells isolation
# ---------------------------------------------------------------------------


def test_parse_row_cells_with_outer_pipes():
    result = MarkdownGrouper._parse_row_cells("| A | B | C |")
    assert result == ["A", "B", "C"], f"Got {result!r}"
    print("  ✓  _parse_row_cells: outer pipes stripped → 3 cells")


def test_parse_row_cells_no_outer_pipes():
    result = MarkdownGrouper._parse_row_cells("A | B | C")
    assert result == ["A", "B", "C"], f"Got {result!r}"
    print("  ✓  _parse_row_cells: no outer pipes → 3 cells")


def test_parse_row_cells_whitespace_stripped():
    result = MarkdownGrouper._parse_row_cells("|  foo  |  bar  |")
    assert result == ["foo", "bar"], f"Got {result!r}"
    print("  ✓  _parse_row_cells: internal whitespace stripped")


def test_parse_row_cells_single_cell():
    result = MarkdownGrouper._parse_row_cells("| only |")
    assert result == ["only"], f"Got {result!r}"
    print("  ✓  _parse_row_cells: single cell")


# ---------------------------------------------------------------------------
# Group B — _parse_table isolation
# ---------------------------------------------------------------------------

_TABLE_2COL_1ROW = "| A | B |\n|---|---|\n| 1 | 2 |"
_TABLE_3ROW = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"


def test_parse_table_basic_structure():
    g = make_grouper()
    rows = g._parse_table(_TABLE_2COL_1ROW)
    assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
    assert_node(rows[0], NodeType.TABLE_HEADER, n_children=2, ctx="header")
    assert_node(rows[1], NodeType.TABLE_ROW, n_children=2, ctx="row")
    print("  ✓  _parse_table: 2-col/1-row → [TABLE_HEADER(2), TABLE_ROW(2)]")


def test_parse_table_alignment_separator_skipped():
    """The separator is read for its alignments and still emits no row."""
    g = make_grouper()
    block = "| A | B | C |\n|:---|:---:|---:|\n| 1 | 2 | 3 |"
    rows = g._parse_table(block)
    assert len(rows) == 2, f"Expected 2 rows (sep skipped), got {len(rows)}"
    assert rows[0].type == NodeType.TABLE_HEADER
    assert rows[1].type == NodeType.TABLE_ROW
    want = ["left", "center", "right"]
    for row, ctx in ((rows[0], "header"), (rows[1], "body")):
        got = [c.table_align for c in row.children]
        assert got == want, f"[{ctx}] got {got}, expected {want}"
    print("  ✓  _parse_table: separator skipped, its alignments kept")


def test_parse_col_aligns_reads_each_form():
    """`:---` left, `:---:` center, `---:` right, `---` unset — and the
    surrounding whitespace of a hand-aligned delimiter row is irrelevant."""
    f = MarkdownGrouper._parse_col_aligns
    assert f("| :--- | :---: | ---: |") == ["left", "center", "right"]
    assert f("|---|---|") == [None, None]
    assert f("| :---    |     :---:    |     ---: |") == ["left", "center", "right"]
    assert f("|:-|:-:|-:|") == ["left", "center", "right"]
    print("  ✓  _parse_col_aligns: every delimiter form reads correctly")


def test_a_colonless_column_stays_unset():
    """GFM's "no alignment specified": a colon-less column writes nothing, so it
    inherits the theme / the enclosing cascade instead of being forced left."""
    g = make_grouper()
    rows = g._parse_table("| A | B |\n|---|---|\n| 1 | 2 |")
    for row in rows:
        assert all(c.table_align is None for c in row.children), [
            c.table_align for c in row.children
        ]
    print("  ✓  a colon-less column stays unset (inherits, never forced left)")


def test_a_mixed_delimiter_row_leaves_only_its_bare_column_unset():
    g = make_grouper()
    rows = g._parse_table("| A | B | C |\n|:---|---|---:|\n| 1 | 2 | 3 |")
    want = ["left", None, "right"]
    for row in rows:
        got = [c.table_align for c in row.children]
        assert got == want, f"got {got}, expected {want}"
    print("  ✓  a mixed delimiter row leaves only its bare column unset")


def test_a_short_delimiter_row_leaves_the_extra_columns_unset():
    """Malformed input must not raise: fewer delimiter cells than columns
    simply leaves the uncovered columns unaligned."""
    g = make_grouper()
    rows = g._parse_table("| A | B | C |\n|:---:|:---:|\n| 1 | 2 | 3 |")
    want = ["center", "center", None]
    for row in rows:
        got = [c.table_align for c in row.children]
        assert got == want, f"got {got}, expected {want}"
    print("  ✓  a short delimiter row leaves the extra columns unset")


def test_table_align_round_trips():
    g = make_grouper()
    rows = g._parse_table("| A | B |\n|:---:|---:|\n| 1 | 2 |")
    back = MarkdownGroupNode.from_dict(rows[0].to_dict())
    assert [c.table_align for c in back.children] == ["center", "right"]
    # An AST without the key reads back unaligned.
    d = rows[0].to_dict()
    for cell in d["children"]:
        cell.pop("table_align", None)
    legacy = MarkdownGroupNode.from_dict(d)
    assert all(c.table_align is None for c in legacy.children)
    print("  ✓  table_align round-trips, and a legacy AST reads back unset")


def test_parse_table_three_rows():
    g = make_grouper()
    rows = g._parse_table(_TABLE_3ROW)
    assert len(rows) == 3, f"Expected 3, got {len(rows)}"
    assert rows[0].type == NodeType.TABLE_HEADER
    assert rows[1].type == NodeType.TABLE_ROW
    assert rows[2].type == NodeType.TABLE_ROW
    print(
        "  ✓  _parse_table: header + sep + 2 rows → TABLE_HEADER + TABLE_ROW + TABLE_ROW"
    )


def test_parse_table_cell_content_correct():
    g = make_grouper()
    rows = g._parse_table(_TABLE_2COL_1ROW)
    assert rows[0].children[0].type == NodeType.TABLE_CELL, (
        "header cells should be TABLE_CELL"
    )
    assert rows[0].children[0].content == "A", f"Got {rows[0].children[0].content!r}"
    assert rows[0].children[1].content == "B", f"Got {rows[0].children[1].content!r}"
    assert rows[1].children[0].content == "1", f"Got {rows[1].children[0].content!r}"
    assert rows[1].children[1].content == "2", f"Got {rows[1].children[1].content!r}"
    print("  ✓  _parse_table: cell content matches header names and row values")


# ---------------------------------------------------------------------------
# Group C — no table present → no-op
# ---------------------------------------------------------------------------


def test_no_table_plain_text_unchanged():
    root = after_table_walk("Just some plain text.")
    assert root.content == "Just some plain text.", (
        f"Expected content unchanged, got {root.content!r}"
    )
    assert len(root.children) == 0, f"Expected no children, got {len(root.children)}"
    print("  ✓  table walk: plain text → node unchanged")


def test_no_table_empty_content_unchanged():
    root = after_table_walk("")
    assert root.content == "", f"Got {root.content!r}"
    assert len(root.children) == 0
    print("  ✓  table walk: empty content → node unchanged")


# ---------------------------------------------------------------------------
# Group D — pure table content
# ---------------------------------------------------------------------------


def test_pure_table_children_and_label_unchanged():
    root = after_table_walk("| A | B |\n|---|---|\n| 1 | 2 |")
    assert root.content == "", f"Expected content cleared, got {root.content!r}"
    assert root.type == "root", f"Label should stay 'root', got {root.type!r}"
    assert len(root.children) == 2, f"Expected 2 children, got {len(root.children)}"
    assert root.children[0].type == NodeType.TABLE_HEADER
    assert root.children[1].type == NodeType.TABLE_ROW
    print("  ✓  table walk: pure table → TABLE_HEADER + TABLE_ROW, label unchanged")


def test_pure_table_two_data_rows():
    root = after_table_walk("| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |")
    assert len(root.children) == 3, f"Expected 3 children, got {len(root.children)}"
    assert root.children[0].type == NodeType.TABLE_HEADER
    assert root.children[1].type == NodeType.TABLE_ROW
    assert root.children[2].type == NodeType.TABLE_ROW
    print(
        "  ✓  table walk: table with 2 data rows → TABLE_HEADER + TABLE_ROW + TABLE_ROW"
    )


def test_pure_table_three_columns():
    root = after_table_walk("| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |")
    assert len(root.children) == 2
    header = root.children[0]
    row = root.children[1]
    assert len(header.children) == 3, (
        f"Expected 3 header cells, got {len(header.children)}"
    )
    assert len(row.children) == 3, f"Expected 3 row cells, got {len(row.children)}"
    assert all(c.type == NodeType.TABLE_CELL for c in header.children)
    assert all(c.type == NodeType.TABLE_CELL for c in row.children)
    print("  ✓  table walk: 3-column table → each row has 3 TABLE_CELL children")


# ---------------------------------------------------------------------------
# Group E — mixed content (text and table in a single node, no blank separator)
# ---------------------------------------------------------------------------


def test_mixed_text_before_table():
    root = after_table_walk("before\n| A | B |\n|---|---|\n| 1 | 2 |")
    assert len(root.children) == 3, f"Expected 3 children, got {len(root.children)}"
    assert_node(root.children[0], NodeType.TEXT, content="before", ctx="text before")
    assert root.children[1].type == NodeType.TABLE_HEADER
    assert root.children[2].type == NodeType.TABLE_ROW
    print("  ✓  table walk: text before table → [TEXT, TABLE_HEADER, TABLE_ROW]")


def test_mixed_text_after_table():
    root = after_table_walk("| A | B |\n|---|---|\n| 1 | 2 |\nafter")
    assert len(root.children) == 3, f"Expected 3 children, got {len(root.children)}"
    assert root.children[0].type == NodeType.TABLE_HEADER
    assert root.children[1].type == NodeType.TABLE_ROW
    assert_node(root.children[2], NodeType.TEXT, content="after", ctx="text after")
    print("  ✓  table walk: text after table → [TABLE_HEADER, TABLE_ROW, TEXT]")


def test_mixed_text_around_table():
    root = after_table_walk("before\n| A | B |\n|---|---|\n| 1 | 2 |\nafter")
    assert len(root.children) == 4, f"Expected 4 children, got {len(root.children)}"
    assert_node(root.children[0], NodeType.TEXT, content="before", ctx="text before")
    assert root.children[1].type == NodeType.TABLE_HEADER
    assert root.children[2].type == NodeType.TABLE_ROW
    assert_node(root.children[3], NodeType.TEXT, content="after", ctx="text after")
    print("  ✓  table walk: text, table, text → [TEXT, TABLE_HEADER, TABLE_ROW, TEXT]")


# ---------------------------------------------------------------------------
# Group F — heading AST integration
# ---------------------------------------------------------------------------


def test_heading_body_pure_table():
    root = after_table_walk("# H\n\n| A | B |\n|---|---|\n| 1 | 2 |")
    group = root.children[0]
    body = group.children[1]
    assert body.type == NodeType.TEXT, f"Label should stay TEXT, got {body.type!r}"
    assert body.content == "", f"Expected content cleared, got {body.content!r}"
    assert len(body.children) == 2
    assert body.children[0].type == NodeType.TABLE_HEADER
    assert body.children[1].type == NodeType.TABLE_ROW
    print(
        "  ✓  table walk: heading body is table → body node gets TABLE_HEADER+TABLE_ROW, label stays TEXT"
    )


def test_heading_body_intro_then_table():
    root = after_table_walk("# H\n\nIntro.\n\n| A | B |\n|---|---|\n| 1 | 2 |")
    group = root.children[0]
    # Blank-split splices as [heading1, TEXT("Intro."), GROUP(table)];
    # table walk fills the GROUP with TABLE_HEADER + TABLE_ROW.
    assert len(group.children) == 3, (
        f"Expected 3 heading-group children, got {len(group.children)}"
    )
    assert_node(group.children[0], "heading1", content="H", ctx="heading node")
    assert_node(group.children[1], NodeType.TEXT, content="Intro.", ctx="intro node")
    table_container = group.children[2]
    assert len(table_container.children) == 2, (
        f"Expected 2 children in table container, got {len(table_container.children)}"
    )
    assert table_container.children[0].type == NodeType.TABLE_HEADER
    assert table_container.children[1].type == NodeType.TABLE_ROW
    print(
        "  ✓  table walk: heading body intro+table → [heading1, TEXT(intro), container[TABLE_HEADER, TABLE_ROW]]"
    )


def test_heading_only_no_body_noop():
    root = after_table_walk("# H")
    group = root.children[0]
    assert len(group.children) == 1, (
        f"Expected 1 child (heading only), got {len(group.children)}"
    )
    assert_node(group.children[0], "heading1", content="H", ctx="heading node")
    print("  ✓  table walk: heading only → no-op")


# ---------------------------------------------------------------------------
# Group G — recursion across nested headings
# ---------------------------------------------------------------------------


def test_nested_only_h2_has_table():
    root = after_table_walk(
        "# H1\n\nPlain body.\n\n## H2\n\n| A | B |\n|---|---|\n| 1 | 2 |"
    )
    h1_group = root.children[0]
    h1_body = h1_group.children[1]
    assert h1_body.content == "Plain body.", (
        f"Expected H1 body unchanged, got {h1_body.content!r}"
    )
    h2_group = h1_group.children[2]
    h2_body = h2_group.children[1]
    assert h2_body.content == "", (
        f"Expected H2 body content cleared, got {h2_body.content!r}"
    )
    assert len(h2_body.children) == 2
    assert h2_body.children[0].type == NodeType.TABLE_HEADER
    assert h2_body.children[1].type == NodeType.TABLE_ROW
    print(
        "  ✓  table walk: nested H1+H2, only H2 table → H1 body unchanged, H2 body processed"
    )


def test_both_headings_have_tables():
    root = after_table_walk(
        "# H1\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n## H2\n\n| C | D |\n|---|---|\n| 3 | 4 |"
    )
    h1_group = root.children[0]
    h1_body = h1_group.children[1]
    assert h1_body.content == "", f"H1 body content: {h1_body.content!r}"
    assert len(h1_body.children) == 2
    assert h1_body.children[0].type == NodeType.TABLE_HEADER
    assert h1_body.children[1].type == NodeType.TABLE_ROW
    h2_group = h1_group.children[2]
    h2_body = h2_group.children[1]
    assert h2_body.content == "", f"H2 body content: {h2_body.content!r}"
    assert len(h2_body.children) == 2
    assert h2_body.children[0].type == NodeType.TABLE_HEADER
    assert h2_body.children[1].type == NodeType.TABLE_ROW
    print("  ✓  table walk: H1 and H2 both have tables → both processed independently")


# ---------------------------------------------------------------------------
# Group H — table_role stamping + _flag_table_groups + serialization
# ---------------------------------------------------------------------------


def test_parse_table_roles_stamped():
    g = make_grouper()
    rows = g._parse_table(_TABLE_2COL_1ROW)
    assert all(c.table_role == "header" for c in rows[0].children), (
        f"Header roles: {[c.table_role for c in rows[0].children]}"
    )
    assert all(c.table_role == "body" for c in rows[1].children), (
        f"Body roles: {[c.table_role for c in rows[1].children]}"
    )
    print("  ✓  _parse_table: cells stamped table_role header/body")


def test_flag_table_groups_all_children_in_place():
    root = after_table_walk("| A | B |\n|---|---|\n| 1 | 2 |")
    _flag_table_groups(root)
    # root's children are exactly the table run and root has no content →
    # flagged in place, no wrapper inserted.
    assert root.table_group, "container should be flagged in place"
    assert len(root.children) == 2
    print("  ✓  _flag_table_groups: run == all children → flagged in place")


def test_flag_table_groups_mixed_run_wrapped():
    root = after_table_walk("before\n| A | B |\n|---|---|\n| 1 | 2 |\nafter")
    _flag_table_groups(root)
    assert not root.table_group, "mixed container must not be flagged"
    assert len(root.children) == 3, (
        f"Expected [TEXT, wrapper, TEXT], got {[c.type for c in root.children]}"
    )
    wrapper = root.children[1]
    assert wrapper.type == NodeType.GROUP and wrapper.table_group, (
        "table run should be wrapped in a flagged group"
    )
    assert [c.type for c in wrapper.children] == [
        NodeType.TABLE_HEADER,
        NodeType.TABLE_ROW,
    ]
    print("  ✓  _flag_table_groups: mixed run → wrapped in flagged group")


def test_flag_table_groups_back_to_back_tables_split():
    node = MarkdownGroupNode(type=NodeType.GROUP)
    g = make_grouper()
    node.children = g._parse_table(_TABLE_2COL_1ROW) + g._parse_table(
        "| C | D |\n|---|---|\n| 3 | 4 |"
    )
    root = MarkdownGroupNode(type="root")
    root.children = [node]
    _flag_table_groups(root)
    assert not node.table_group, "two-table container must not be flagged whole"
    assert len(node.children) == 2, (
        f"Expected 2 wrappers, got {[c.type for c in node.children]}"
    )
    assert all(
        w.table_group and w.children[0].type == NodeType.TABLE_HEADER
        for w in node.children
    ), "each table should get its own flagged wrapper"
    print("  ✓  _flag_table_groups: back-to-back tables → one wrapper each")


def test_flag_table_groups_split_cell_inherits_role():
    root = after_table_walk("| A | B |\n|---|---|\n| $29/mo | 2 |")
    # Simulate a datapoint split: the cell becomes a group whose pieces are
    # NEW nodes without a table_role (as _separate_structured_content_walk
    # produces), one of them with a pre-set role that must not be overwritten.
    cell = root.children[1].children[0]
    dp = MarkdownGroupNode(type=NodeType.DATAPOINT, content="$29")
    rest = MarkdownGroupNode(type=NodeType.TABLE_CELL, content="/mo")
    preset = MarkdownGroupNode(type=NodeType.TEXT, content="x")
    preset.table_role = "header"
    dp.children = [preset]
    cell.children = [dp, rest]
    cell.content = ""
    _flag_table_groups(root)
    assert dp.table_role == "body", f"dp role: {dp.table_role}"
    assert rest.table_role == "body", f"rest role: {rest.table_role}"
    assert preset.table_role == "header", "pre-set role must not be overwritten"
    rt = MarkdownGroupNode.from_dict(root.to_dict())
    rt_cell = rt.children[1].children[0]
    assert all(c.table_role == "body" for c in rt_cell.children), (
        "inherited roles must survive to_dict/from_dict"
    )
    print(
        "  ✓  _flag_table_groups: split-cell pieces inherit role (no overwrite) + round-trip"
    )


def test_table_flags_serialization_round_trip():
    root = after_table_walk("| A | B |\n|---|---|\n| 1 | 2 |")
    _flag_table_groups(root)
    rt = MarkdownGroupNode.from_dict(root.to_dict())
    assert rt.table_group, "table_group should survive to_dict/from_dict"
    header = rt.children[0]
    assert all(c.table_role == "header" for c in header.children)
    assert all(c.table_role == "body" for c in rt.children[1].children)
    print("  ✓  serialization: table_group + table_role round-trip")


def test_parse_row_cells_keeps_an_escaped_pipe_in_its_cell():
    """GFM: ``\\|`` is no delimiter. It stays in its cell, a declined separator
    whose backslash Phase 6.17 drops, and in a code span it is the pipe alone."""
    cells = MarkdownGrouper._parse_row_cells
    assert cells(r"| a \| b | c |") == [r"a \| b", "c"], cells(r"| a \| b | c |")
    assert cells(r"| `a \| b` | c |") == ["`a | b`", "c"]
    assert cells(r"| [S](/s) \| [M](/m) |") == [r"[S](/s) \| [M](/m)"]
    assert cells(r"| ends in \|") == [r"ends in \|"], "an escaped last pipe stays"
    print("  ✓  _parse_row_cells: an escaped pipe stays in its cell, literal")


def test_an_escaped_pipe_is_drawn_as_a_pipe_in_its_cell():
    """Through the real pipeline: two cells, as the header has, and ``a | b``
    drawn with no backslash, as text or as one code chip."""
    ast = session.group_markdown(
        "| Left | Right |\n|---|---|\n| a \\| b | c |\n| `a \\| b` | d |\n",
        session.load_grouping_kit(),
    )
    assert ast is not None

    def rows(nd: dict) -> list[dict]:
        own = [nd] if nd["type"] == "table_row" else []
        return own + [r for kid in nd.get("children", []) for r in rows(kid)]

    def drawn(cell: dict) -> str:
        return cell.get("content") or "".join(drawn(k) for k in cell["children"])

    shapes = [[drawn(c) for c in r["children"]] for r in rows(ast.to_dict())]
    assert shapes == [["a | b", "c"], ["a | b", "d"]], shapes
    print("  ✓  an escaped pipe is a pipe in its one cell, in text and in code")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS = [
    # Group A — _parse_row_cells isolation
    test_parse_row_cells_with_outer_pipes,
    test_parse_row_cells_no_outer_pipes,
    test_parse_row_cells_whitespace_stripped,
    test_parse_row_cells_single_cell,
    test_parse_row_cells_keeps_an_escaped_pipe_in_its_cell,
    test_an_escaped_pipe_is_drawn_as_a_pipe_in_its_cell,
    # Group B — _parse_table isolation
    test_parse_table_basic_structure,
    test_parse_table_alignment_separator_skipped,
    test_parse_col_aligns_reads_each_form,
    test_a_colonless_column_stays_unset,
    test_a_mixed_delimiter_row_leaves_only_its_bare_column_unset,
    test_a_short_delimiter_row_leaves_the_extra_columns_unset,
    test_table_align_round_trips,
    test_parse_table_three_rows,
    test_parse_table_cell_content_correct,
    # Group C — no table present → no-op
    test_no_table_plain_text_unchanged,
    test_no_table_empty_content_unchanged,
    # Group D — pure table content
    test_pure_table_children_and_label_unchanged,
    test_pure_table_two_data_rows,
    test_pure_table_three_columns,
    # Group E — mixed content
    test_mixed_text_before_table,
    test_mixed_text_after_table,
    test_mixed_text_around_table,
    # Group F — heading AST integration
    test_heading_body_pure_table,
    test_heading_body_intro_then_table,
    test_heading_only_no_body_noop,
    # Group G — recursion across nested headings
    test_nested_only_h2_has_table,
    test_both_headings_have_tables,
    # Group H — table_role stamping + _flag_table_groups + serialization
    test_parse_table_roles_stamped,
    test_flag_table_groups_all_children_in_place,
    test_flag_table_groups_mixed_run_wrapped,
    test_flag_table_groups_back_to_back_tables_split,
    test_flag_table_groups_split_cell_inherits_role,
    test_table_flags_serialization_round_trip,
]

if __name__ == "__main__":
    print("Markdown Table Tests")
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
