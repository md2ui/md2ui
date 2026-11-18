"""
Unit tests for _split_blank_lines and _subgroup_content.
Run with: uv run markdown_blank_split_tests.py
"""

from md2ui.pipeline.grouper_block_splits import _split_blank_lines
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


def after_blank_split(text: str) -> MarkdownGroupNode:
    """Build heading AST then apply only the blank-line split pass."""
    g = MarkdownGrouper(text)
    g.to_ast()
    assert g.ast is not None
    g._subgroup_content(g.ast, _split_blank_lines)
    return g.ast


# ---------------------------------------------------------------------------
# Group A — _split_blank_lines in isolation
# ---------------------------------------------------------------------------


def test_split_empty():
    result = _split_blank_lines("")
    assert result is None, f"Expected None, got {result!r}"
    print("  ✓  _split_blank_lines: empty string → None")


def test_split_single_paragraph():
    result = _split_blank_lines("Single paragraph")
    assert result is None, f"Expected None, got {result!r}"
    print("  ✓  _split_blank_lines: single paragraph → None")


def test_split_single_newline_not_blank():
    result = _split_blank_lines("Line one\nLine two")
    assert result is None, f"Expected None for single newline, got {result!r}"
    print("  ✓  _split_blank_lines: single \\n → None (not a blank line)")


def test_split_two_paragraphs():
    result = _split_blank_lines("Para 1\n\nPara 2")
    assert result == [(NodeType.TEXT, "Para 1"), (NodeType.TEXT, "Para 2")], (
        f"Got {result!r}"
    )
    print("  ✓  _split_blank_lines: two paragraphs → 2 TEXT parts")


def test_split_three_paragraphs():
    result = _split_blank_lines("P1\n\nP2\n\nP3")
    assert result is not None and len(result) == 3, f"Expected 3 parts, got {result!r}"
    assert all(label == NodeType.TEXT for label, _ in result), (
        f"All should be TEXT: {result!r}"
    )
    print("  ✓  _split_blank_lines: three paragraphs → 3-element list")


def test_split_multiple_blank_lines():
    result = _split_blank_lines("P1\n\n\n\nP2")
    assert result == [(NodeType.TEXT, "P1"), (NodeType.TEXT, "P2")], f"Got {result!r}"
    print("  ✓  _split_blank_lines: 3+ newlines treated same as double")


def test_split_multiline_first_part():
    result = _split_blank_lines("Multi\nline\n\nPara 2")
    assert result == [(NodeType.GROUP, "Multi\nline"), (NodeType.TEXT, "Para 2")], (
        f"Got {result!r}"
    )
    print("  ✓  _split_blank_lines: first part has \\n → GROUP label")


def test_split_leading_trailing_blanks():
    result = _split_blank_lines("\n\nPara\n\n")
    assert result is None, f"Expected None (only 1 non-empty part), got {result!r}"
    print("  ✓  _split_blank_lines: leading/trailing blanks, 1 part → None")


def test_split_whitespace_stripped():
    result = _split_blank_lines("  Para 1  \n\n  Para 2  ")
    assert result == [(NodeType.TEXT, "Para 1"), (NodeType.TEXT, "Para 2")], (
        f"Got {result!r}"
    )
    print("  ✓  _split_blank_lines: surrounding whitespace stripped")


# ---------------------------------------------------------------------------
# Group B — no-heading documents (root carries content)
# ---------------------------------------------------------------------------


def test_no_heading_single_para_unchanged():
    root = after_blank_split("Single paragraph.")
    assert_node(
        root,
        "root",
        content="Single paragraph.",
        n_children=0,
        ctx="no-heading single para",
    )
    print("  ✓  subgroup: no-heading, single para → root unchanged")


def test_no_heading_two_paras():
    root = after_blank_split("Para 1\n\nPara 2")
    assert root.content == "", f"Expected empty content, got {root.content!r}"
    assert len(root.children) == 2, f"Expected 2 children, got {len(root.children)}"
    assert_node(root.children[0], NodeType.TEXT, content="Para 1", ctx="child 0")
    assert_node(root.children[1], NodeType.TEXT, content="Para 2", ctx="child 1")
    print("  ✓  subgroup: no-heading, two paras → 2 TEXT children")


def test_no_heading_three_paras():
    root = after_blank_split("P1\n\nP2\n\nP3")
    assert root.content == ""
    assert len(root.children) == 3, f"Expected 3 children, got {len(root.children)}"
    print("  ✓  subgroup: no-heading, three paras → 3 TEXT children")


def test_no_heading_multiline_first():
    root = after_blank_split("Multi\nline\n\nPara 2")
    assert root.content == ""
    assert len(root.children) == 2
    assert_node(
        root.children[0], NodeType.GROUP, content="Multi\nline", ctx="first child"
    )
    assert_node(root.children[1], NodeType.TEXT, content="Para 2", ctx="second child")
    print("  ✓  subgroup: no-heading, multiline+para → GROUP + TEXT children")


# ---------------------------------------------------------------------------
# Group C — heading section body
# ---------------------------------------------------------------------------


def test_heading_single_para_body_unchanged():
    root = after_blank_split("# H\n\nOne paragraph.")
    group = root.children[0]
    body = group.children[1]
    assert_node(
        body,
        NodeType.TEXT,
        content="One paragraph.",
        n_children=0,
        ctx="heading single para body",
    )
    print("  ✓  subgroup: heading + single para body → body unchanged")


def test_heading_body_two_paras():
    root = after_blank_split("# H\n\nPara 1\n\nPara 2")
    group = root.children[0]
    # Split TEXT pieces splice into the heading group (no extra GROUP wrapper)
    assert len(group.children) == 3, f"Expected 3 children, got {len(group.children)}"
    assert_node(group.children[0], "heading1", content="H", ctx="heading node")
    assert_node(group.children[1], NodeType.TEXT, content="Para 1", ctx="body child 0")
    assert_node(group.children[2], NodeType.TEXT, content="Para 2", ctx="body child 1")
    print("  ✓  subgroup: heading + 2-para body → 2 TEXT siblings of heading1")


def test_heading_body_three_paras():
    root = after_blank_split("# H\n\nP1\n\nP2\n\nP3")
    group = root.children[0]
    assert len(group.children) == 4, f"Expected 4 children, got {len(group.children)}"
    assert_node(group.children[0], "heading1", content="H", ctx="heading node")
    for i, txt in enumerate(("P1", "P2", "P3"), start=1):
        assert_node(
            group.children[i], NodeType.TEXT, content=txt, ctx=f"body child {i - 1}"
        )
    print("  ✓  subgroup: heading + 3-para body → 3 TEXT siblings of heading1")


def test_heading_body_multiline_para():
    root = after_blank_split("# H\n\nMulti\nline\n\nSingle")
    group = root.children[0]
    # Multi-line part stays as GROUP (still unsplit at this phase);
    # single-line part is TEXT. Both splice as siblings of heading1.
    assert len(group.children) == 3, f"Expected 3 children, got {len(group.children)}"
    assert_node(group.children[0], "heading1", content="H", ctx="heading node")
    assert_node(
        group.children[1], NodeType.GROUP, content="Multi\nline", ctx="body child 0"
    )
    assert_node(group.children[2], NodeType.TEXT, content="Single", ctx="body child 1")
    print("  ✓  subgroup: heading + multiline\\n\\nsingle → [heading, GROUP, TEXT]")


def test_heading_only_no_body():
    root = after_blank_split("# H")
    group = root.children[0]
    assert len(group.children) == 1, (
        f"Expected 1 child (heading only), got {len(group.children)}"
    )
    assert_node(group.children[0], "heading1", content="H", ctx="heading node")
    print("  ✓  subgroup: heading only (no body) → no-op")


# ---------------------------------------------------------------------------
# Group D — heading node itself is not split
# ---------------------------------------------------------------------------


def test_heading_content_not_split():
    root = after_blank_split("# Title Text")
    heading = root.children[0].children[0]
    assert_node(
        heading, "heading1", content="Title Text", n_children=0, ctx="heading node"
    )
    print("  ✓  subgroup: heading content unchanged, label stays heading1")


def test_nested_headings_not_split():
    root = after_blank_split("## A\n\n### B")
    h2_group = root.children[0]
    h2_node = h2_group.children[0]
    assert_node(h2_node, "heading2", content="A", n_children=0, ctx="H2 node")
    h3_group = h2_group.children[1]
    h3_node = h3_group.children[0]
    assert_node(h3_node, "heading3", content="B", n_children=0, ctx="H3 node")
    print("  ✓  subgroup: heading nodes untouched in nested structure")


# ---------------------------------------------------------------------------
# Group E — recursion across nested headings
# ---------------------------------------------------------------------------


def test_nested_h2_body_split():
    root = after_blank_split("# H1\n\n## H2\n\nBody A\n\nBody B")
    h1_group = root.children[0]
    h2_group = h1_group.children[1]
    # Split TEXT pieces splice as siblings of heading2 (no extra GROUP wrapper)
    assert len(h2_group.children) == 3, (
        f"Expected 3 H2 children, got {len(h2_group.children)}"
    )
    assert_node(h2_group.children[0], "heading2", content="H2", ctx="H2 node")
    assert_node(
        h2_group.children[1], NodeType.TEXT, content="Body A", ctx="H2 body child 0"
    )
    assert_node(
        h2_group.children[2], NodeType.TEXT, content="Body B", ctx="H2 body child 1"
    )
    print("  ✓  subgroup: nested H2 body → 2 TEXT siblings of heading2; H1 unaffected")


def test_both_heading_bodies_split_independently():
    root = after_blank_split("# H1\n\nA1\n\nA2\n\n## H2\n\nB1\n\nB2")
    h1_group = root.children[0]
    # H1 body TEXT splice: heading1, A1, A2, then nested h2_group
    assert len(h1_group.children) == 4, (
        f"Expected 4 H1 children, got {len(h1_group.children)}"
    )
    assert_node(h1_group.children[0], "heading1", content="H1", ctx="H1 node")
    assert_node(
        h1_group.children[1], NodeType.TEXT, content="A1", ctx="H1 body child 0"
    )
    assert_node(
        h1_group.children[2], NodeType.TEXT, content="A2", ctx="H1 body child 1"
    )
    h2_group = h1_group.children[3]
    # H2 body TEXT splice: heading2, B1, B2
    assert len(h2_group.children) == 3, (
        f"Expected 3 H2 children, got {len(h2_group.children)}"
    )
    assert_node(h2_group.children[0], "heading2", content="H2", ctx="H2 node")
    assert_node(
        h2_group.children[1], NodeType.TEXT, content="B1", ctx="H2 body child 0"
    )
    assert_node(
        h2_group.children[2], NodeType.TEXT, content="B2", ctx="H2 body child 1"
    )
    print("  ✓  subgroup: H1 and H2 bodies splice independently as heading siblings")


# ---------------------------------------------------------------------------
# Group F — preamble (text before first heading)
# ---------------------------------------------------------------------------


def test_preamble_single_para_unchanged():
    root = after_blank_split("Intro.\n\n# H")
    preamble = root.children[0]
    assert_node(preamble, NodeType.TEXT, content="Intro.", n_children=0, ctx="preamble")
    print("  ✓  subgroup: single-para preamble → unchanged")


def test_preamble_two_paras_split():
    root = after_blank_split("P1\n\nP2\n\n# H")
    # Preamble TEXT splice into root: [TEXT("P1"), TEXT("P2"), heading_group]
    assert len(root.children) == 3, (
        f"Expected 3 root children, got {len(root.children)}"
    )
    assert_node(root.children[0], NodeType.TEXT, content="P1", ctx="preamble child 0")
    assert_node(root.children[1], NodeType.TEXT, content="P2", ctx="preamble child 1")
    assert root.children[2].type == NodeType.GROUP, (
        f"Third child should be heading group, got {root.children[2].type!r}"
    )
    print("  ✓  subgroup: two-para preamble → 2 TEXT siblings at root")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS = [
    # Group A — _split_blank_lines in isolation
    test_split_empty,
    test_split_single_paragraph,
    test_split_single_newline_not_blank,
    test_split_two_paragraphs,
    test_split_three_paragraphs,
    test_split_multiple_blank_lines,
    test_split_multiline_first_part,
    test_split_leading_trailing_blanks,
    test_split_whitespace_stripped,
    # Group B — no-heading documents
    test_no_heading_single_para_unchanged,
    test_no_heading_two_paras,
    test_no_heading_three_paras,
    test_no_heading_multiline_first,
    # Group C — heading section body
    test_heading_single_para_body_unchanged,
    test_heading_body_two_paras,
    test_heading_body_three_paras,
    test_heading_body_multiline_para,
    test_heading_only_no_body,
    # Group D — heading node itself is not split
    test_heading_content_not_split,
    test_nested_headings_not_split,
    # Group E — recursion across nested headings
    test_nested_h2_body_split,
    test_both_heading_bodies_split_independently,
    # Group F — preamble
    test_preamble_single_para_unchanged,
    test_preamble_two_paras_split,
]

if __name__ == "__main__":
    print("Markdown Blank-Line Split Tests")
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
