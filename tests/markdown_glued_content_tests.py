"""
Unit tests for glued-content segmentation: MarkdownGrouper marks maximal runs
of consecutive non-blank source lines with the boolean property
`glued_content_group=True` on a (structural) group node; the run's direct
children each carry a shared `glued_content_id`.
Run with: uv run markdown_glued_content_tests.py
"""

from md2ui.pipeline.grouper_block_splits import _split_blank_lines, _split_newlines
from md2ui.pipeline.markdown_grouper import (
    MarkdownGrouper,
    MarkdownGroupNode,
    NodeType,
)
from md2ui.pipeline.grouper_glue import _collapse_groups, _wrap_glued_content

GROUP = NodeType.GROUP


def glued_ast(text: str):
    """Run the structural subset of the pipeline that produces glued groups
    (no detector needed for plain text + headings):
    to_ast → blank split → newline split → wrap → collapse."""
    g = MarkdownGrouper(text)
    g.to_ast()
    assert g.ast is not None
    g._subgroup_content(g.ast, _split_blank_lines, crosses_segments=True)
    g._subgroup_content(g.ast, _split_newlines, mints_segments=True)
    _wrap_glued_content(g.ast)
    _collapse_groups(g.ast)
    return g.ast


def _types(node):
    return [c.type for c in node.children]


def _glued_flags(node):
    return [c.glued_content_group for c in node.children]


def test_glued_paragraph():
    root = glued_ast("A text\nB text\n")
    seg = root.children[0]
    assert seg.type == GROUP and seg.glued_content_group, seg.type
    assert seg.glued_content_id is not None
    assert [c.content for c in seg.children] == ["A text", "B text"]
    print("  ✓  glued paragraph → single group(glued){A,B}")


def test_two_paragraphs_distinct_ids():
    root = glued_ast("A text\nB text\n\nC text\nD text\n")
    assert _glued_flags(root) == [True, True], _glued_flags(root)
    a, b = root.children
    assert a.glued_content_id != b.glued_content_id
    assert not any(c.glued_content_group for c in a.children)  # no nesting
    print("  ✓  two paragraphs → two glued groups, distinct ids, no nesting")


def test_lone_line_not_glued():
    root = glued_ast("Solo line\n\nGlued one\nGlued two\n")
    assert _types(root) == [NodeType.TEXT, GROUP], _types(root)
    assert _glued_flags(root) == [False, True], _glued_flags(root)
    print("  ✓  lone line stays a bare text; glued pair flagged")


def test_heading_spanning_segment():
    root = glued_ast("C text\n# Heading text\nD text\n")
    # Single-run section: redundant group collapses to the bare glued group.
    seg = root.children[0]
    assert seg.type == GROUP and seg.glued_content_group, seg.type
    assert [c.type for c in seg.children] == [
        NodeType.TEXT,
        "heading1",
        NodeType.TEXT,
    ]
    assert seg.children[1].content == "Heading text"
    print("  ✓  heading-spanning run is a glued group of text/heading/text")


def test_standalone_heading_not_glued():
    root = glued_ast("# Just a heading\n\nLone paragraph line\n")
    group = root.children[0]
    assert group.type == NodeType.GROUP and not group.glued_content_group
    # heading + blank-separated lone line: neither is glued
    assert not any(c.glued_content_group for c in group.children)
    print("  ✓  standalone heading + blank-separated line → no glued flag")


def test_heading_body_blank_split():
    # D is glued to the heading; E is a separate (blank-separated) segment.
    root = glued_ast("# Heading\nD line\n\nE line\n")
    group = root.children[0]
    # group children: group(glued){heading, D}, then bare text E
    assert group.children[0].glued_content_group
    seg_contents = [c.content for c in group.children[0].children]
    assert seg_contents == ["Heading", "D line"], seg_contents
    assert group.children[1].type == NodeType.TEXT
    assert group.children[1].content == "E line"
    print("  ✓  heading+glued body flagged; blank-separated tail stays out")


def test_canonical_tree():
    root = glued_ast(
        "Content not glued\n\n"
        "Content glued to next heading\n# heading\nContent glued to previous\n\n"
        "Loose line in section\n\n"
        "## Sub heading\n\nSub content\n"
    )
    assert _types(root) == [NodeType.TEXT, NodeType.GROUP], _types(root)
    h1 = root.children[1]
    # group(glued), loose text, h2 group
    assert [c.glued_content_group for c in h1.children] == [
        True,
        False,
        False,
    ], [c.glued_content_group for c in h1.children]
    glued = h1.children[0]
    assert [c.type for c in glued.children] == [
        NodeType.TEXT,
        "heading1",
        NodeType.TEXT,
    ]
    print("  ✓  canonical example produces the expected tree")


def test_serialization_bool_on_group_id_on_children():
    root = glued_ast("A text\nB text\n")
    d = root.to_dict()
    seg = d["children"][0]
    assert seg.get("glued_content_group") is True
    # the group node itself does NOT serialize an id
    assert "glued_content_id" not in seg
    # every direct child carries the shared id
    for child in seg["children"]:
        assert "glued_content_id" in child
    print("  ✓  glued_content_group on group; glued_content_id on each child")


def _leaf(text):
    return MarkdownGroupNode(type=NodeType.TEXT, content=text)


def _glued_group(gid, children):
    n = MarkdownGroupNode(type=NodeType.GROUP)
    n.glued_content_group = True
    n.glued_content_id = gid
    n.children = children
    return n


def test_collapse_glued_over_single_group():
    # group(glued) > group[text x3]  →  group(glued)[text x3]
    inner = MarkdownGroupNode(type=NodeType.GROUP)
    inner.children = [_leaf("A"), _leaf("B"), _leaf("C")]
    glued = _glued_group(7, [inner])
    root = MarkdownGroupNode(type="root")
    root.children = [glued]

    _collapse_groups(root)

    assert len(root.children) == 1
    merged = root.children[0]
    assert merged.glued_content_group, merged.type
    assert merged.glued_content_id == 7
    assert [c.type for c in merged.children] == [NodeType.TEXT] * 3
    print("  ✓  glued > group(single) → group(glued)[children], id kept")


def test_collapse_group_over_single_group():
    # group > group[text x2]  →  group[text x2]  (neither side glued)
    inner = MarkdownGroupNode(type=NodeType.GROUP)
    inner.children = [_leaf("A"), _leaf("B")]
    outer = MarkdownGroupNode(type=NodeType.GROUP)
    outer.children = [inner]
    root = MarkdownGroupNode(type="root")
    root.children = [outer]

    _collapse_groups(root)

    assert len(root.children) == 1
    merged = root.children[0]
    assert merged.type == NodeType.GROUP and not merged.glued_content_group
    assert [c.type for c in merged.children] == [NodeType.TEXT] * 2
    print("  ✓  group > group(single) → single group[children]")


def test_collapse_group_over_single_glued_keeps_glued():
    # group > group(glued)[text x2]  →  group(glued), id carried up
    inner = _glued_group(3, [_leaf("A"), _leaf("B")])
    outer = MarkdownGroupNode(type=NodeType.GROUP)
    outer.children = [inner]
    root = MarkdownGroupNode(type="root")
    root.children = [outer]

    _collapse_groups(root)

    merged = root.children[0]
    assert merged.glued_content_group, merged.type
    assert merged.glued_content_id == 3
    assert len(merged.children) == 2
    print("  ✓  group > glued(single) → group(glued), id carried up")


def test_collapse_absorbs_glued_into_parent():
    # list_item > group(glued)[image, text]  →  list_item(glued)[image, text]
    # The whole-item glued wrapper is absorbed onto the existing parent (no
    # redundant single-child wrapper) — the music-list-2 case.
    glued = _glued_group(
        5,
        [
            MarkdownGroupNode(type=NodeType.IMAGE, content="![x](u)"),
            _leaf("Name"),
        ],
    )
    item = MarkdownGroupNode(type=NodeType.LIST_ITEM)
    item.children = [glued]
    root = MarkdownGroupNode(type="root")
    root.children = [item]

    _collapse_groups(root)

    li = root.children[0]
    assert li.type == NodeType.LIST_ITEM, li.type
    assert li.glued_content_group, "flag should move onto the list_item"
    assert li.glued_content_id == 5
    assert [c.type for c in li.children] == [NodeType.IMAGE, NodeType.TEXT]
    # no nested glued group left inside
    assert not any(c.glued_content_group for c in li.children)
    print("  ✓  list_item > glued(single) → list_item(glued), wrapper absorbed")


def test_root_not_glued_absorbed():
    # root > group(glued)[items]  stays — root must never be flagged glued.
    glued = _glued_group(1, [_leaf("a"), _leaf("b")])
    root = MarkdownGroupNode(type="root")
    root.children = [glued]

    _collapse_groups(root)

    assert not root.glued_content_group
    assert len(root.children) == 1 and root.children[0].glued_content_group
    print("  ✓  root never absorbs a glued group (stays unflagged)")


# ---------------------------------------------------------------------------
# Lone-line splits mint their own glued segment
#
# A lone source line is not glued at the to_ast origin (id None), but when a
# split separates it into >= 2 pieces the pieces ARE closely related — the
# splitters mint a fresh segment id (see `_inherit_glue`) so the pieces end up
# in one `glued_content_group`. Glued content never nests: pieces of an
# already-glued line inherit the line's id instead of minting.
# ---------------------------------------------------------------------------


def _assert_no_nested_glued(node, in_glued=False):
    """A glued group must never contain another glued group."""
    if node.glued_content_group:
        assert not in_glued, f"nested glued group at {node.type}: {node.content!r}"
        in_glued = True
    for c in node.children:
        _assert_no_nested_glued(c, in_glued)


def _find_glued(node):
    out = []
    if node.glued_content_group:
        out.append(node)
    for c in node.children:
        out.extend(_find_glued(c))
    return out


def _walk_all(node):
    yield node
    for c in node.children:
        yield from _walk_all(c)


def test_lone_line_separator_split_not_glued():
    """A separator-split lone line is not glued content either.

    Its pieces flow as a homogeneous pill run — a generator path of its own,
    so the node carries no ``line_split_group`` flag — but it is still one
    source line, and one line has nothing to glue.
    """
    from markdown_datapoint_split_tests import _processed_with_criteria

    ast = _processed_with_criteria(
        "Intro paragraph line\n\n[A](u) | [B](u) | [C](u)\n\nOutro paragraph"
    )
    assert _find_glued(ast) == [], "a flowed line must not be glued"
    (run,) = [
        n for n in _walk_all(ast) if [c.type for c in n.children] == [NodeType.LINK] * 3
    ]
    assert run.source_line_id is not None, "the pieces share one source line"
    print("  ✓  lone line 'A | B | C' between paragraphs → not glued")


def test_lone_line_peel_not_glued():
    """A lone line flowed aside is a line split, not glued content.

    Glue means consecutive source lines stuck together; one line has none to
    glue, so it must not draw a card.
    """
    from markdown_datapoint_split_tests import _processed_with_criteria

    ast = _processed_with_criteria(
        "Intro paragraph line\n\nDenim Jacket - [buy](/x)\n\nOutro paragraph"
    )
    assert _find_glued(ast) == [], "a flowed line must not be glued"
    (line,) = [n for n in _walk_all(ast) if n.line_split_group and not n.heading_group]
    assert [c.type for c in line.children] == [
        NodeType.SEGMENT,
        NodeType.LINK,
    ], f"Got {[(c.type, c.content) for c in line.children]}"
    print("  ✓  lone line 'text [link]' peel → line split, not glued")


def test_lone_line_image_split_not_glued():
    from markdown_datapoint_split_tests import _processed_with_criteria

    ast = _processed_with_criteria(
        "Intro paragraph line\n\nbefore ![alt](u.png) after\n\nOutro paragraph"
    )
    assert _find_glued(ast) == [], "a flowed line must not be glued"
    (line,) = [n for n in _walk_all(ast) if n.line_split_group]
    types = [c.type for c in line.children]
    assert NodeType.IMAGE in types and NodeType.TEXT in types, f"Got {types}"
    print("  ✓  lone line 'text ![img] text' → line split, not glued")


def test_lone_kv_line_glued():
    from markdown_datapoint_split_tests import _processed_with_criteria

    # A display pair (a percentage bar): under ADR-205 a plain `Key: value`
    # line is one text, and a lone line of text has nothing to glue.
    ast = _processed_with_criteria(
        "Intro paragraph line\n\n**Progress:** 60%\n\nOutro paragraph"
    )
    glued = _find_glued(ast)
    assert len(glued) == 1, f"Expected 1 glued group, got {len(glued)}"
    kv = glued[0]
    assert kv.type == NodeType.KEY_VALUE, f"Got {kv.type!r}"
    types = [c.type for c in kv.children]
    assert NodeType.KEY in types and NodeType.VALUE in types, f"Got {types}"
    ids = {c.glued_content_id for c in kv.children}
    assert len(ids) == 1 and None not in ids, f"Got ids {ids}"
    _assert_no_nested_glued(ast)
    plain = _processed_with_criteria(
        "Intro paragraph line\n\n**Fabric:** organic cotton\n\nOutro paragraph"
    )
    assert _find_glued(plain) == [], "a lone line of text is not glued"
    print("  ✓  lone display pair → KEY_VALUE(glued), KEY/VALUE share id")


def test_lone_line_inline_code_peel_not_glued():
    from markdown_datapoint_split_tests import _processed_with_criteria

    # Separated, so the span peels — `` `code` explanation text `` with nothing
    # between them is prose adjacency and stays one leaf (marker), unpeeled.
    ast = _processed_with_criteria(
        "Intro paragraph line\n\n`code` - explanation text\n\nOutro paragraph"
    )
    assert _find_glued(ast) == [], "a flowed line must not be glued"
    (line,) = [n for n in _walk_all(ast) if n.line_split_group]
    assert [c.type for c in line.children] == [
        NodeType.INLINE_CODE,
        NodeType.SEGMENT,
    ], f"Got {[(c.type, c.content) for c in line.children]}"
    print("  ✓  lone line '`code` - text' peel → line split, not glued")


def test_glued_kv_dp_split_no_nested_glued():
    from markdown_datapoint_split_tests import _processed_with_criteria

    # The KV paths assign glue BEFORE the per-child datapoint splits; a bare
    # VALUE splitting on its inner datapoint must inherit the line's id, not
    # mint a nested segment — in glued context AND on a lone line.
    ast = _processed_with_criteria("Glued line one\n**Progress:** 60%\nGlued line two")
    glued = _find_glued(ast)
    assert len(glued) == 1, (
        f"Expected exactly 1 glued group, got "
        f"{[(g.type, [c.type for c in g.children]) for g in glued]}"
    )
    _assert_no_nested_glued(ast)
    print("  ✓  glued run with dp-splitting KV → exactly one glued group")


def test_split_heading_not_glued():
    from markdown_datapoint_split_tests import _processed_with_criteria

    # A standalone heading that peels its emoji keeps the pieces nested in the
    # heading container but must NOT become a glued card (heading exclusion).
    ast = _processed_with_criteria("# 🎯 Title\n\nbody text")
    glued = _find_glued(ast)
    assert not glued, (
        f"Expected no glued groups, got "
        f"{[(g.type, [c.type for c in g.children]) for g in glued]}"
    )
    print("  ✓  split standalone heading '# 🎯 Title' stays un-glued")


# ---------------------------------------------------------------------------
# Glue belongs to the stacked BLOCK, not to the line it sits on
# ---------------------------------------------------------------------------


def _glued(text: str) -> list[str]:
    """What each glued node IS, in document order.

    Reported as a role — "col" / "kv" / "block" — not a node type: a colon
    column is a GROUP when it is the whole line and a SEGMENT when it sits
    inside a flowed one, and that difference is not the contract.
    """
    import sys

    sys.path.insert(0, "tests")
    from markdown_datapoint_split_tests import _processed_with_criteria

    out: list[str] = []

    def walk(n):
        if n.glued_content_group:
            out.append(
                "kv"
                if n.type == NodeType.KEY_VALUE
                else "col"
                if n.column_split_group
                else "block"
            )
        for c in n.children:
            walk(c)

    walk(_processed_with_criteria(text))
    return out


def test_a_colon_column_on_a_flowed_line_is_the_card():
    """`A - B : C : D - E` flows as a row of three; the middle piece stacks,
    and the stack is the card. The line itself gets none."""
    assert _glued("A - B : C : D - E") == ["col"]


def test_a_plain_flowed_line_has_no_glue():
    assert _glued("A - B - C") == []


def test_a_colon_column_alone_on_its_line_is_still_the_card():
    assert _glued("A : B") == ["col"]


def test_a_key_value_pair_keeps_its_glue():
    """Without a spring a display pair stacks — value under key — so it is a
    card. A plain `K: v` is one text (ADR-205), and earns none."""
    assert _glued("CPU: 40%") == ["kv"]
    assert _glued("A - CPU: 40% - B") == ["kv"]
    assert _glued("K: v") == []
    assert _glued("A - K: v - B") == []


def test_a_spring_pair_is_a_row_and_never_a_card():
    """It is its own line, so it is the glue ROOT and already carries glue —
    this has to be cleared, not merely left unset."""
    assert _glued("K: ... v") == []


def test_glue_does_not_nest():
    """A colon column inside a multi-line card belongs to that card."""
    assert _glued("A : B\nsecond line") == ["block"]


def test_a_heading_that_is_a_colon_column_is_not_a_card():
    """`## 92 : days` parses as a heading2 that itself carries the column
    split; a card there would draw inside the heading line."""
    assert _glued("## 92 : days") == []


TESTS = [
    test_glued_paragraph,
    test_two_paragraphs_distinct_ids,
    test_lone_line_not_glued,
    test_heading_spanning_segment,
    test_standalone_heading_not_glued,
    test_heading_body_blank_split,
    test_canonical_tree,
    test_serialization_bool_on_group_id_on_children,
    test_collapse_glued_over_single_group,
    test_collapse_group_over_single_group,
    test_collapse_group_over_single_glued_keeps_glued,
    test_collapse_absorbs_glued_into_parent,
    test_root_not_glued_absorbed,
    test_lone_line_separator_split_not_glued,
    test_lone_line_peel_not_glued,
    test_lone_line_image_split_not_glued,
    test_lone_kv_line_glued,
    test_lone_line_inline_code_peel_not_glued,
    test_glued_kv_dp_split_no_nested_glued,
    test_split_heading_not_glued,
    test_a_colon_column_on_a_flowed_line_is_the_card,
    test_a_plain_flowed_line_has_no_glue,
    test_a_colon_column_alone_on_its_line_is_still_the_card,
    test_a_key_value_pair_keeps_its_glue,
    test_a_spring_pair_is_a_row_and_never_a_card,
    test_glue_does_not_nest,
    test_a_heading_that_is_a_colon_column_is_not_a_card,
]

if __name__ == "__main__":
    print("Markdown Glued-Content Tests")
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
