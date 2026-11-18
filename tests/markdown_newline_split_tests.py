"""
Unit tests for _split_newlines and the newline-split pass.
Run with: uv run markdown_newline_split_tests.py
"""

from md2ui.pipeline.grouper_block_splits import _split_blank_lines, _split_newlines
from md2ui.pipeline.markdown_grouper import MarkdownGrouper, MarkdownGroupNode, NodeType

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


def after_newline_split(text: str) -> MarkdownGroupNode:
    """Run full Phase 1: to_ast + blank-split + table-walk + newline-split."""
    g = MarkdownGrouper(text)
    g.to_ast()
    assert g.ast is not None
    g._subgroup_content(g.ast, _split_blank_lines)
    g._subgroup_tables_walk(g.ast)
    g._subgroup_content(g.ast, _split_newlines)
    return g.ast


# ---------------------------------------------------------------------------
# Group A — _split_newlines isolation (6 tests)
# ---------------------------------------------------------------------------


def test_split_newlines_empty_string():
    result = _split_newlines("")
    assert result is None, f"Expected None, got {result!r}"
    print("  ✓  _split_newlines: empty string → None")


def test_split_newlines_single_line():
    result = _split_newlines("single line")
    assert result is None, f"Expected None, got {result!r}"
    print("  ✓  _split_newlines: single line → None")


def test_split_newlines_whitespace_only_around_content():
    result = _split_newlines("  text  ")
    assert result is None, f"Expected None (1 line after strip), got {result!r}"
    print("  ✓  _split_newlines: whitespace around single line → None")


def test_split_newlines_two_lines():
    result = _split_newlines("line1\nline2")
    assert result == [(NodeType.TEXT, "line1"), (NodeType.TEXT, "line2")], (
        f"Got {result!r}"
    )
    print("  ✓  _split_newlines: 'line1\\nline2' → [(TEXT,'line1'),(TEXT,'line2')]")


def test_split_newlines_three_lines():
    result = _split_newlines("line1\nline2\nline3")
    assert result is not None
    assert len(result) == 3, f"Expected 3 items, got {len(result)}"
    assert all(label == NodeType.TEXT for label, _ in result), (
        f"All labels should be TEXT, got {result!r}"
    )
    assert [text for _, text in result] == ["line1", "line2", "line3"]
    print("  ✓  _split_newlines: 3 lines → 3-element list, all TEXT")


def test_split_newlines_embedded_blank_filtered():
    result = _split_newlines("a\n\nb")
    assert result == [(NodeType.TEXT, "a"), (NodeType.TEXT, "b")], (
        f"Expected blank filtered, got {result!r}"
    )
    print("  ✓  _split_newlines: 'a\\n\\nb' → [(TEXT,'a'),(TEXT,'b')] (blank filtered)")


# ---------------------------------------------------------------------------
# Group B — no-heading documents (3 tests)
# ---------------------------------------------------------------------------


def test_no_heading_single_line_unchanged():
    root = after_newline_split("single line")
    assert root.content == "single line", f"Got {root.content!r}"
    assert len(root.children) == 0, f"Expected no children, got {len(root.children)}"
    print("  ✓  no-heading single line → root unchanged")


def test_no_heading_two_lines_split():
    root = after_newline_split("line1\nline2")
    assert root.type == "root", f"Root label: got {root.type!r}"
    assert root.content == "", f"Root content cleared: got {root.content!r}"
    assert len(root.children) == 2, f"Expected 2 children, got {len(root.children)}"
    assert_node(root.children[0], NodeType.TEXT, content="line1", ctx="child0")
    assert_node(root.children[1], NodeType.TEXT, content="line2", ctx="child1")
    print("  ✓  no-heading 'line1\\nline2' → root[TEXT('line1'), TEXT('line2')]")


def test_no_heading_three_lines_split():
    root = after_newline_split("line1\nline2\nline3")
    assert len(root.children) == 3, f"Expected 3 children, got {len(root.children)}"
    assert all(c.type == NodeType.TEXT for c in root.children), (
        "All children should be TEXT"
    )
    assert [c.content for c in root.children] == ["line1", "line2", "line3"]
    print("  ✓  no-heading 3 lines → root[TEXT, TEXT, TEXT]")


# ---------------------------------------------------------------------------
# Group C — GROUP nodes from blank-split get their content split (2 tests)
# ---------------------------------------------------------------------------


def test_group_from_blank_split_gets_children():
    root = after_newline_split("Multi\nline\n\nSingle")
    assert len(root.children) == 2, f"Expected 2 children, got {len(root.children)}"
    first = root.children[0]
    assert first.type == NodeType.GROUP, f"First child label: got {first.type!r}"
    assert len(first.children) == 2, (
        f"First child should have 2 children, got {len(first.children)}"
    )
    assert_node(first.children[0], NodeType.TEXT, content="Multi", ctx="Multi")
    assert_node(first.children[1], NodeType.TEXT, content="line", ctx="line")
    assert_node(root.children[1], NodeType.TEXT, content="Single", ctx="Single")
    print(
        "  ✓  blank-split GROUP gets newline-split → GROUP[TEXT('Multi'),TEXT('line')] + TEXT('Single')"
    )


def test_heading_group_with_multiline_paragraph():
    root = after_newline_split("# H\n\nMulti\nline\n\nSingle para")
    heading_group = root.children[0]
    # Blank-split splices the pieces as siblings of heading1:
    #   [heading1, GROUP("Multi\nline"), TEXT("Single para")]
    # Newline-split then splits the inner GROUP into 2 TEXT children.
    assert len(heading_group.children) == 3, (
        f"Expected 3 children, got {len(heading_group.children)}"
    )
    assert_node(heading_group.children[0], "heading1", content="H", ctx="heading node")
    inner_group = heading_group.children[1]
    assert inner_group.type == NodeType.GROUP, (
        f"Inner group label: got {inner_group.type!r}"
    )
    assert len(inner_group.children) == 2, (
        f"Inner group should have 2 children, got {len(inner_group.children)}"
    )
    assert_node(inner_group.children[0], NodeType.TEXT, content="Multi", ctx="Multi")
    assert_node(inner_group.children[1], NodeType.TEXT, content="line", ctx="line")
    assert_node(
        heading_group.children[2],
        NodeType.TEXT,
        content="Single para",
        ctx="Single para",
    )
    print(
        "  ✓  heading body: [heading1, GROUP[TEXT('Multi'),TEXT('line')], TEXT('Single para')]"
    )


# ---------------------------------------------------------------------------
# Group D — leaf TEXT splits splice into heading group (2 tests)
# ---------------------------------------------------------------------------


def test_heading_body_text_relabeled_group():
    root = after_newline_split("# H\n\nMulti\nline")
    heading_group = root.children[0]
    # Leaf TEXT("Multi\nline") splits and splices as siblings of heading1
    assert len(heading_group.children) == 3, (
        f"Expected 3 children, got {len(heading_group.children)}"
    )
    assert_node(heading_group.children[0], "heading1", content="H", ctx="heading node")
    assert_node(heading_group.children[1], NodeType.TEXT, content="Multi", ctx="Multi")
    assert_node(heading_group.children[2], NodeType.TEXT, content="line", ctx="line")
    print("  ✓  heading body 'Multi\\nline' → 2 TEXT siblings of heading1")


def test_heading_body_three_lines_relabeled_group():
    root = after_newline_split("# H\n\nline1\nline2\nline3")
    heading_group = root.children[0]
    assert len(heading_group.children) == 4, (
        f"Expected 4 children, got {len(heading_group.children)}"
    )
    assert_node(heading_group.children[0], "heading1", content="H", ctx="heading node")
    assert [c.content for c in heading_group.children[1:]] == [
        "line1",
        "line2",
        "line3",
    ]
    assert all(c.type == NodeType.TEXT for c in heading_group.children[1:])
    print("  ✓  heading body 3 lines → 3 TEXT siblings of heading1")


# ---------------------------------------------------------------------------
# Group E — no-op cases (3 tests)
# ---------------------------------------------------------------------------


def test_table_cells_unchanged():
    root = after_newline_split("# H\n\n| A | B |\n|---|---|\n| 1 | 2 |")
    heading_group = root.children[0]
    body = heading_group.children[1]
    # body contains TABLE_HEADER + TABLE_ROW
    cells = body.children[0].children  # TABLE_HEADER cells
    for cell in cells:
        assert cell.type == NodeType.TABLE_CELL, (
            f"Expected TABLE_CELL, got {cell.type!r}"
        )
        assert len(cell.children) == 0, "TABLE_CELL should have no children"
    print("  ✓  TABLE_CELL nodes unchanged (no children added)")


def test_heading_node_content_unchanged():
    root = after_newline_split("# Title")
    heading_group = root.children[0]
    heading_node = heading_group.children[0]
    assert heading_node.type == "heading1", f"Got {heading_node.type!r}"
    assert heading_node.content == "Title", f"Got {heading_node.content!r}"
    assert len(heading_node.children) == 0
    print("  ✓  heading1 node content unchanged")


def test_single_paragraph_body_unchanged():
    root = after_newline_split("# H\n\nOne paragraph.")
    heading_group = root.children[0]
    body = heading_group.children[1]
    assert body.type == NodeType.TEXT, f"Body label: got {body.type!r}"
    assert body.content == "One paragraph.", f"Got {body.content!r}"
    assert len(body.children) == 0
    print("  ✓  single-line body TEXT node unchanged")


# ---------------------------------------------------------------------------
# Group F — heading integration (2 tests)
# ---------------------------------------------------------------------------


def test_heading_single_line_body_unchanged():
    root = after_newline_split("# H\n\nSingle line body.")
    heading_group = root.children[0]
    body = heading_group.children[1]
    assert body.type == NodeType.TEXT, f"Body label: got {body.type!r}"
    assert body.content == "Single line body.", f"Got {body.content!r}"
    assert len(body.children) == 0
    print("  ✓  heading single-line body → TEXT unchanged")


def test_heading_mixed_body_partial_split():
    root = after_newline_split("# H\n\nPara1.\n\nline1\nline2")
    heading_group = root.children[0]
    # Blank-split splices as [heading1, TEXT("Para1."), GROUP("line1\nline2")];
    # newline-split fills the GROUP with 2 TEXT children.
    assert len(heading_group.children) == 3, (
        f"Expected 3 children, got {len(heading_group.children)}"
    )
    assert_node(heading_group.children[0], "heading1", content="H", ctx="heading node")
    assert_node(
        heading_group.children[1], NodeType.TEXT, content="Para1.", ctx="Para1."
    )
    second = heading_group.children[2]
    assert second.type == NodeType.GROUP, f"Third child label: got {second.type!r}"
    assert len(second.children) == 2, (
        f"Third child should have 2 children, got {len(second.children)}"
    )
    assert_node(second.children[0], NodeType.TEXT, content="line1", ctx="line1")
    assert_node(second.children[1], NodeType.TEXT, content="line2", ctx="line2")
    print(
        "  ✓  heading body: [heading1, TEXT('Para1.'), GROUP[TEXT('line1'),TEXT('line2')]]"
    )


# ---------------------------------------------------------------------------
# Group G — recursion across nested headings (3 tests)
# ---------------------------------------------------------------------------


def test_heading_only_no_body_noop():
    root = after_newline_split("# H")
    heading_group = root.children[0]
    assert len(heading_group.children) == 1, (
        f"Expected 1 child (heading only), got {len(heading_group.children)}"
    )
    assert_node(heading_group.children[0], "heading1", content="H", ctx="heading node")
    print("  ✓  heading only (no body) → no-op")


def test_nested_only_h2_has_multiline():
    root = after_newline_split("# H1\n\nPlain.\n\n## H2\n\nline1\nline2")
    h1_group = root.children[0]
    # H1 body "Plain." is single-line: stays as TEXT at index 1; h2_group at index 2.
    assert_node(h1_group.children[0], "heading1", content="H1", ctx="H1 node")
    assert_node(h1_group.children[1], NodeType.TEXT, content="Plain.", ctx="H1 body")

    h2_group = h1_group.children[2]
    # H2 body splits and splices as siblings of heading2.
    assert len(h2_group.children) == 3, (
        f"Expected 3 H2 children, got {len(h2_group.children)}"
    )
    assert_node(h2_group.children[0], "heading2", content="H2", ctx="H2 node")
    assert_node(h2_group.children[1], NodeType.TEXT, content="line1", ctx="line1")
    assert_node(h2_group.children[2], NodeType.TEXT, content="line2", ctx="line2")
    print("  ✓  H1 body plain unchanged; H2 body → 2 TEXT siblings of heading2")


def test_both_headings_have_multiline_bodies():
    root = after_newline_split("# H1\n\nA1\nA2\n\n## H2\n\nB1\nB2")
    h1_group = root.children[0]
    # H1 body splices as siblings of heading1; h2_group shifts to index 3.
    assert len(h1_group.children) == 4, (
        f"Expected 4 H1 children, got {len(h1_group.children)}"
    )
    assert_node(h1_group.children[0], "heading1", content="H1", ctx="H1 node")
    assert_node(h1_group.children[1], NodeType.TEXT, content="A1", ctx="A1")
    assert_node(h1_group.children[2], NodeType.TEXT, content="A2", ctx="A2")

    h2_group = h1_group.children[3]
    assert len(h2_group.children) == 3, (
        f"Expected 3 H2 children, got {len(h2_group.children)}"
    )
    assert_node(h2_group.children[0], "heading2", content="H2", ctx="H2 node")
    assert_node(h2_group.children[1], NodeType.TEXT, content="B1", ctx="B1")
    assert_node(h2_group.children[2], NodeType.TEXT, content="B2", ctx="B2")
    print(
        "  ✓  H1 body → [TEXT('A1'),TEXT('A2')] siblings; H2 body → [TEXT('B1'),TEXT('B2')] siblings"
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS = [
    # Group A — _split_newlines isolation
    test_split_newlines_empty_string,
    test_split_newlines_single_line,
    test_split_newlines_whitespace_only_around_content,
    test_split_newlines_two_lines,
    test_split_newlines_three_lines,
    test_split_newlines_embedded_blank_filtered,
    # Group B — no-heading documents
    test_no_heading_single_line_unchanged,
    test_no_heading_two_lines_split,
    test_no_heading_three_lines_split,
    # Group C — GROUP nodes from blank-split get their content split
    test_group_from_blank_split_gets_children,
    test_heading_group_with_multiline_paragraph,
    # Group D — TEXT→GROUP relabeling
    test_heading_body_text_relabeled_group,
    test_heading_body_three_lines_relabeled_group,
    # Group E — no-op cases
    test_table_cells_unchanged,
    test_heading_node_content_unchanged,
    test_single_paragraph_body_unchanged,
    # Group F — heading integration
    test_heading_single_line_body_unchanged,
    test_heading_mixed_body_partial_split,
    # Group G — recursion across nested headings
    test_heading_only_no_body_noop,
    test_nested_only_h2_has_multiline,
    test_both_headings_have_multiline_bodies,
]

if __name__ == "__main__":
    print("Markdown Newline Split Tests")
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
