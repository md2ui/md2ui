"""
Unit tests for MarkdownGrouper._subgroup_content_classified_multi and its splitters.
Run with: uv run markdown_classified_multi_tests.py
"""

from md2ui.pipeline.grouper_block_splits import (
    _split_all_lists,
    _split_blank_lines,
    _split_images,
    _split_newlines,
)
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


def after_classified_multi(text: str) -> MarkdownGroupNode:
    """Run Phase 1 + classified_multi (matches pipeline order)."""
    g = MarkdownGrouper(text)
    g.to_ast()
    assert g.ast is not None
    g._subgroup_content(g.ast, _split_blank_lines)
    g._subgroup_tables_walk(g.ast)
    g._subgroup_content(g.ast, _split_newlines)
    g._subgroup_content_classified_multi(
        g.ast,
        [_split_all_lists, _split_images],
    )
    return g.ast


# ---------------------------------------------------------------------------
# Group A — _split_all_lists isolation (5 tests)
# ---------------------------------------------------------------------------


def test_split_all_lists_plain_text():
    result = _split_all_lists("plain text")
    assert result is None, f"Expected None for plain text, got {result!r}"
    print("  ✓  _split_all_lists: plain text → None")


def test_split_all_lists_unordered():
    result = _split_all_lists("- a\n- b")
    assert result == [(NodeType.LIST_ITEM, "a"), (NodeType.LIST_ITEM, "b")], (
        f"Got {result!r}"
    )
    print("  ✓  _split_all_lists: '- a\\n- b' → [(LIST_ITEM,'a'),(LIST_ITEM,'b')]")


def test_split_all_lists_ordered():
    # An ordered item carries a THIRD element: the number the author wrote, kept
    # so it survives the "1. " marker being stripped off the text (the ordinal a
    # run draws seeds from it — see layout_marker_tests).
    result = _split_all_lists("1. first\n2. second")
    assert result == [
        (NodeType.ORDERED_ITEM, "first", 1),
        (NodeType.ORDERED_ITEM, "second", 2),
    ], f"Got {result!r}"
    print(
        "  ✓  _split_all_lists: '1. first\\n2. second' → [(ORDERED_ITEM,'first',1),(ORDERED_ITEM,'second',2)]"
    )


def test_split_all_lists_tasks():
    result = _split_all_lists("- [ ] open\n- [x] done")
    assert result == [(NodeType.TASK_OPEN, "open"), (NodeType.TASK_DONE, "done")], (
        f"Got {result!r}"
    )
    print("  ✓  _split_all_lists: task items → [(TASK_OPEN,'open'),(TASK_DONE,'done')]")


def test_split_all_lists_continuation():
    result = _split_all_lists("- item\ncontinuation")
    assert result is not None, "Expected result, got None"
    assert len(result) == 1, f"Expected 1 item, got {len(result)}"
    label, content = result[0]
    assert label == NodeType.LIST_ITEM, f"Expected LIST_ITEM, got {label!r}"
    assert "item" in content and "continuation" in content, (
        f"Expected continuation joined, got {content!r}"
    )
    print(f"  ✓  _split_all_lists: continuation joined → LIST_ITEM({content!r})")


# ---------------------------------------------------------------------------
# Group B — _split_images isolation (3 tests)
# ---------------------------------------------------------------------------


def test_split_images_plain_text():
    result = _split_images("plain text")
    assert result is None, f"Expected None for plain text, got {result!r}"
    print("  ✓  _split_images: plain text → None")


def test_split_images_single_image():
    result = _split_images("![alt](url.png)")
    assert result == [(NodeType.IMAGE, "![alt](url.png)")], f"Got {result!r}"
    print("  ✓  _split_images: '![alt](url.png)' → [(IMAGE,'![alt](url.png)')]")


def test_split_images_inline():
    result = _split_images("before ![alt](url.png) after")
    assert result is not None, "Expected result, got None"
    assert len(result) == 3, f"Expected 3 parts, got {len(result)}"
    assert result[0] == (NodeType.TEXT, "before"), f"Got {result[0]!r}"
    assert result[1] == (NodeType.IMAGE, "![alt](url.png)"), f"Got {result[1]!r}"
    assert result[2] == (NodeType.TEXT, "after"), f"Got {result[2]!r}"
    print("  ✓  _split_images: 'before ![alt](url.png) after' → [TEXT,IMAGE,TEXT]")


# ---------------------------------------------------------------------------
# Group D — list integration in pipeline (4 tests)
# ---------------------------------------------------------------------------


def test_pipeline_unordered_list():
    root = after_classified_multi("- a\n- b")
    # After newline-split, root has TEXT("- a") and TEXT("- b") children.
    # classified_multi absorbs each (single-result TEXT) → LIST_ITEM.
    assert len(root.children) == 2, f"Expected 2 children, got {len(root.children)}"
    assert_node(root.children[0], NodeType.LIST_ITEM, content="a", ctx="child0")
    assert_node(root.children[1], NodeType.LIST_ITEM, content="b", ctx="child1")
    print("  ✓  pipeline: '- a\\n- b' → root[LIST_ITEM('a'),LIST_ITEM('b')]")


def test_pipeline_ordered_list():
    root = after_classified_multi("1. x\n2. y")
    assert len(root.children) == 2, f"Expected 2 children, got {len(root.children)}"
    assert_node(root.children[0], NodeType.ORDERED_ITEM, content="x", ctx="child0")
    assert_node(root.children[1], NodeType.ORDERED_ITEM, content="y", ctx="child1")
    print("  ✓  pipeline: '1. x\\n2. y' → root[ORDERED_ITEM('x'),ORDERED_ITEM('y')]")


def test_pipeline_task_list():
    root = after_classified_multi("- [ ] open\n- [x] done")
    assert len(root.children) == 2, f"Expected 2 children, got {len(root.children)}"
    assert_node(root.children[0], NodeType.TASK_OPEN, content="open", ctx="child0")
    assert_node(root.children[1], NodeType.TASK_DONE, content="done", ctx="child1")
    print("  ✓  pipeline: task list → root[TASK_OPEN('open'),TASK_DONE('done')]")


def test_pipeline_list_in_heading_body():
    root = after_classified_multi("# H\n\n- a\n- b")
    heading_group = root.children[0]
    # Newline-split splices the two list lines as TEXT siblings of heading1;
    # each then gets absorbed into LIST_ITEM by _split_all_lists.
    assert len(heading_group.children) == 3, (
        f"Expected 3 children, got {len(heading_group.children)}"
    )
    assert_node(heading_group.children[0], "heading1", content="H", ctx="heading node")
    assert_node(
        heading_group.children[1], NodeType.LIST_ITEM, content="a", ctx="child0"
    )
    assert_node(
        heading_group.children[2], NodeType.LIST_ITEM, content="b", ctx="child1"
    )
    print(
        "  ✓  pipeline: '# H\\n\\n- a\\n- b' → [heading1, LIST_ITEM('a'), LIST_ITEM('b')]"
    )


# ---------------------------------------------------------------------------
# Group E — image integration in pipeline (2 tests)
# ---------------------------------------------------------------------------


def test_split_images_skips_a_code_span():
    # `` `![alt](url.png)` `` is a code span: the markup inside it is literal
    # text. Splitting it out would strand the backticks as their own leaves.
    assert _split_images("`![alt](url.png)`") is None
    assert _split_images("text `![a](x.png)` more") is None
    print("  ✓  _split_images: an image inside `code` is not an image")


def test_split_images_still_splits_beside_a_code_span():
    # Only the protected occurrence is skipped — a real image on the same line
    # still splits, and the code span rides along in the text part.
    result = _split_images("![a](x.png) and `![b](y.png)` here")
    assert result == [
        (NodeType.IMAGE, "![a](x.png)"),
        (NodeType.TEXT, "and `![b](y.png)` here"),
    ], f"Got {result!r}"
    print("  ✓  _split_images: a bare image beside a backticked one still splits")


def test_pipeline_single_image():
    root = after_classified_multi("![alt](url.png)")
    assert root.type == "root", f"Root label: got {root.type!r}"
    assert len(root.children) == 1, f"Expected 1 child, got {len(root.children)}"
    assert_node(
        root.children[0], NodeType.IMAGE, content="![alt](url.png)", ctx="image"
    )
    print("  ✓  pipeline: '![alt](url.png)' → root[IMAGE('![alt](url.png)')]")


def test_pipeline_inline_image():
    root = after_classified_multi("before ![alt](url.png) after")
    assert root.type == "root", f"Root label: got {root.type!r}"
    assert len(root.children) == 3, f"Expected 3 children, got {len(root.children)}"
    assert_node(root.children[0], NodeType.TEXT, content="before", ctx="before")
    assert_node(
        root.children[1], NodeType.IMAGE, content="![alt](url.png)", ctx="image"
    )
    assert_node(root.children[2], NodeType.TEXT, content="after", ctx="after")
    print("  ✓  pipeline: 'before ![alt](url.png) after' → root[TEXT,IMAGE,TEXT]")


def test_pipeline_code_span_image_survives_whole():
    # Through the real pipeline the line stays ONE leaf here, and the later
    # inline-code pass turns it into a chip / marker (see
    # markdown_datapoint_split_tests), never TEXT('`'), IMAGE, TEXT('`').
    root = after_classified_multi("`![alt](url.png)`")
    assert len(root.children) == 0, f"Expected no split, got {root.to_dict()}"
    assert root.content == "`![alt](url.png)`", f"Got {root.content!r}"

    inline = after_classified_multi("This line `![alt](url.png)` is prose.")
    assert len(inline.children) == 0, f"Expected no split, got {inline.to_dict()}"
    assert inline.content == "This line `![alt](url.png)` is prose."
    print("  ✓  pipeline: a backticked image keeps its line whole")


# ---------------------------------------------------------------------------
# Group F — link integration in pipeline
# ---------------------------------------------------------------------------
# Boundary-only LINK extraction happens in the boundary peel (ADR-200), not in `_subgroup_content_classified_multi`. Its tests live in
# `markdown_datapoint_split_tests.py` under "Group F — Boundary-LINK integration
# via process()", in the real pipeline order (annotate → split-criteria gate →
# separator → datapoint split).


# ---------------------------------------------------------------------------
# Group G — multi-splitter chaining (2 tests)
# ---------------------------------------------------------------------------


def test_pipeline_list_item_with_image():
    # After list-split absorbs TEXT → LIST_ITEM, image splitter splits it further.
    root = after_classified_multi("- ![icon](img.png) label\n- plain")
    assert len(root.children) == 2, f"Expected 2 children, got {len(root.children)}"

    first = root.children[0]
    assert first.type == NodeType.LIST_ITEM, f"First child label: got {first.type!r}"
    assert first.content == "", (
        f"First child content should be cleared, got {first.content!r}"
    )
    assert len(first.children) == 2, (
        f"First child should have 2 children, got {len(first.children)}"
    )
    assert_node(
        first.children[0], NodeType.IMAGE, content="![icon](img.png)", ctx="image"
    )
    assert_node(first.children[1], NodeType.TEXT, content="label", ctx="label")

    second = root.children[1]
    assert_node(second, NodeType.LIST_ITEM, content="plain", ctx="plain")
    print(
        "  ✓  pipeline: list item with image → LIST_ITEM[IMAGE('![icon](img.png)'),TEXT('label')] + LIST_ITEM('plain')"
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS = [
    # Group A — _split_all_lists isolation
    test_split_all_lists_plain_text,
    test_split_all_lists_unordered,
    test_split_all_lists_ordered,
    test_split_all_lists_tasks,
    test_split_all_lists_continuation,
    # Group B — _split_images isolation
    test_split_images_plain_text,
    test_split_images_single_image,
    test_split_images_inline,
    test_split_images_skips_a_code_span,
    test_split_images_still_splits_beside_a_code_span,
    # Group D — list integration in pipeline
    test_pipeline_unordered_list,
    test_pipeline_ordered_list,
    test_pipeline_task_list,
    test_pipeline_list_in_heading_body,
    # Group E — image integration in pipeline
    test_pipeline_single_image,
    test_pipeline_inline_image,
    test_pipeline_code_span_image_survives_whole,
    # Group G — multi-splitter chaining
    test_pipeline_list_item_with_image,
]

if __name__ == "__main__":
    print("Markdown Classified Multi Tests")
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
