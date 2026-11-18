"""
Unit tests for the ``***`` SECTION STOP — the marker that tells a heading group
where to stop swallowing.

A heading otherwise owns everything up to the next heading, so a footer row can
only ever sit *inside* that section's painted box. ``***`` closes the section
where it is written; whatever follows is re-parented as the section's next
sibling, keeping source order. Paired with an empty ``## `` marker as the
wrapper, that is how a card gets a tinted upper block and a plain footer.

The stop leaves nothing behind: ``MarkdownGrouper._apply_section_stops``
consumes every ``section_stop`` node in Phase 1, so no later phase and nothing
in the renderer ever sees the type.

Run with: uv run python tests/section_stop_tests.py
"""

from pathlib import Path

from md2ui.pipeline.markdown_grouper import (
    MarkdownGrouper,
    MarkdownGroupNode,
    NodeType,
)
from md2ui.pipeline.grouper_block_splits import _break_node_type

SAMPLE_7 = Path("data/markdown/tests/tests-card-section-stop.md")


def ast(text: str) -> MarkdownGroupNode:
    """The heading-level AST, without the rest of the pipeline."""
    g = MarkdownGrouper(text)
    g.to_ast()
    assert g.ast is not None
    return g.ast


def walk(node: MarkdownGroupNode):
    yield node
    for child in node.children:
        yield from walk(child)


def shape(node: MarkdownGroupNode) -> list:
    """``[(type, content)]`` for one node's children, for readable failures."""
    return [(c.type, c.content) for c in node.children]


# ---------------------------------------------------------------------------
# 1 — the lift
# ---------------------------------------------------------------------------


def test_a_stop_lifts_the_tail_out_to_the_parent():
    root = ast("# Doc\n## Section\nbody\n***\nfooter\n")
    (doc,) = root.children
    assert doc.heading_level == 1
    section, footer = doc.children[1], doc.children[2]
    assert section.heading_group and section.heading_level == 2, shape(doc)
    # The section kept its heading and its body, and nothing else.
    assert shape(section) == [("heading2", "Section"), (NodeType.TEXT, "body")]
    # The footer is a SIBLING of the section, under the same parent, after it.
    assert (footer.type, footer.content) == (NodeType.TEXT, "footer"), shape(doc)
    print("  ✓  a '***' lifts the rest of the section out to its parent")


def test_the_stop_itself_leaves_no_node():
    root = ast("## Section\nbody\n***\nfooter\n")
    stops = [n for n in walk(root) if n.type == NodeType.SECTION_STOP]
    assert not stops, [(n.type, n.content) for n in walk(root)]
    print("  ✓  no section_stop node survives to_ast")


def test_a_stop_right_after_the_heading_empties_the_section():
    root = ast("## Section\n***\nall out\n")
    section, tail = root.children
    assert shape(section) == [("heading2", "Section")]
    assert (tail.type, tail.content) == (NodeType.TEXT, "all out")
    print("  ✓  a stop on the first body line leaves the heading alone")


def test_source_order_is_preserved_across_the_lift():
    # The tail slots in between the section it left and whatever came next.
    root = ast("## S\na\n***\nb\n\n## T\nc\n")
    s, tail, t = root.children
    assert shape(s) == [("heading2", "S"), (NodeType.TEXT, "a")]
    assert (tail.type, tail.content) == (NodeType.TEXT, "b")
    assert shape(t) == [("heading2", "T"), (NodeType.TEXT, "c")], shape(root)
    print("  ✓  the lifted tail keeps its source order after the section")


# ---------------------------------------------------------------------------
# 2 — what a stop does NOT do
# ---------------------------------------------------------------------------


def test_a_stop_with_no_section_only_cuts():
    # Nothing to close, so it is dropped — but it still ends the glued run,
    # which is what keeps the two paragraphs from becoming one TEXT node.
    root = ast("alpha\n***\nbeta\n")
    assert [(c.type, c.content) for c in root.children] == [
        (NodeType.TEXT, "alpha"),
        (NodeType.TEXT, "beta"),
    ], shape(root)
    print("  ✓  a stop with no enclosing section is an invisible cut only")


def test_a_stopped_section_cannot_be_re_entered():
    # `### Deeper` nests into `## Sec` while the tree is built, but it lands
    # after the stop, so it rides out with the rest of the tail.
    root = ast("## Sec\nbody\n***\n\n### Deeper\nmore\n")
    sec, deeper = root.children
    assert sec.heading_level == 2 and shape(sec) == [
        ("heading2", "Sec"),
        (NodeType.TEXT, "body"),
    ]
    assert deeper.heading_group and deeper.heading_level == 3, shape(root)
    assert shape(deeper) == [("heading3", "Deeper"), (NodeType.TEXT, "more")]
    print("  ✓  a heading after the stop is a sibling, not a re-entry")


def test_stops_compose_up_the_levels():
    # A stop that ends up first in a lifted tail becomes the PARENT's stop, so
    # `footer` climbs one level further than `mid` does.
    root = ast("# Doc\n## Card\n### T\nbody\n***\nmid\n***\nfooter\n")
    (doc,) = root.children
    card = doc.children[1]
    assert card.heading_level == 2
    assert [c.content for c in card.children if c.type == NodeType.TEXT] == ["mid"]
    assert [c.content for c in doc.children if c.type == NodeType.TEXT] == ["footer"], (
        shape(doc)
    )
    print("  ✓  a second '***' closes the level the first one lifted into")


# ---------------------------------------------------------------------------
# 3 — the shape sample-7 needs
# ---------------------------------------------------------------------------


def test_sample_7_is_a_card_wrapping_a_tinted_section_and_a_footer():
    """The reference: an empty `## ` white card holding a tinted `### ` block
    that stops before the Explore row, four times over."""
    root = ast(SAMPLE_7.read_text())
    (doc,) = root.children
    cards = [c for c in doc.children if c.heading_group]
    assert len(cards) == 4, shape(doc)
    for card in cards:
        assert card.heading_level == 2, shape(doc)
        # heading2 leaf is empty (pruned later); then the section, then Explore.
        section = next(c for c in card.children if c.heading_group)
        assert section.heading_level == 3, shape(card)
        assert section.children[0].type == "heading3"
        after = card.children[card.children.index(section) + 1 :]
        assert [c.type for c in after] == [NodeType.TEXT], shape(card)
        # Text-style markers are the sample's business, not the stop's.
        assert "Explore" in after[0].content, shape(card)
        # …and the Explore row is NOT inside the tinted section.
        assert not any("Explore" in (c.content or "") for c in walk(section)), shape(
            section
        )
    print("  ✓  sample-7: 4 cards, each a tinted section + a footer beside it")


# ---------------------------------------------------------------------------
# 4 — the three spellings stay apart
# ---------------------------------------------------------------------------


def test_the_three_spellings_do_three_different_things():
    # The `---` stands alone: tight between two lines it would divide one block.
    root = ast("## S\na\n\n---\n\nb\n___\nc\n***\nd\n")
    section = root.children[0]
    assert [c.type for c in section.children] == [
        "heading2",
        NodeType.TEXT,
        NodeType.HORIZONTAL_RULE,
        NodeType.TEXT,
        NodeType.CONTENT_BREAK,
        NodeType.TEXT,
    ], shape(section)
    assert [(c.type, c.content) for c in root.children[1:]] == [(NodeType.TEXT, "d")], (
        shape(root)
    )
    print("  ✓  --- paints, ___ cuts, *** closes — all in one section")


def test_a_stop_is_not_bold_italic():
    # `***` is only a stop when it is the whole line. Emphasis is untouched.
    root = ast("## S\n***emphasised***\nbody\n")
    section = root.children[0]
    assert [c.type for c in section.children] == ["heading2", NodeType.TEXT]
    assert "***emphasised***" in section.children[1].content
    print("  ✓  '***text***' is emphasis, not a stop")


def test_a_stop_behind_a_list_marker_is_a_rule_not_a_stop():
    """Inside a list every break spelling is just a divider, so `- ***` paints a
    rule and leaves the section open. `* ***` is NOT this case — four matching
    stars are one thematic break, so it stays a stop."""
    from md2ui.pipeline.grouper_types import NodeType

    for line in ("- ***", "+ ***", "1. ***"):
        assert _break_node_type(line) == NodeType.HORIZONTAL_RULE, line
    for line in ("***", "* ***", "* * *", "* **"):
        assert _break_node_type(line) == NodeType.SECTION_STOP, line


def test_indentation_does_not_disarm_a_stop():
    """CommonMark treats up to three spaces as insignificant, so a lone `***`
    closes its section at any indent. Four or more is a code block, consumed
    upstream by INDENTED_CODE_RE."""
    from md2ui.pipeline.grouper_types import NodeType

    for line in ("***", " ***", "  ***", "   ***", "\t***"):
        assert _break_node_type(line) == NodeType.SECTION_STOP, repr(line)


TESTS = [
    test_a_stop_lifts_the_tail_out_to_the_parent,
    test_the_stop_itself_leaves_no_node,
    test_a_stop_right_after_the_heading_empties_the_section,
    test_source_order_is_preserved_across_the_lift,
    test_a_stop_with_no_section_only_cuts,
    test_a_stopped_section_cannot_be_re_entered,
    test_stops_compose_up_the_levels,
    test_sample_7_is_a_card_wrapping_a_tinted_section_and_a_footer,
    test_the_three_spellings_do_three_different_things,
    test_a_stop_is_not_bold_italic,
    test_a_stop_behind_a_list_marker_is_a_rule_not_a_stop,
    test_indentation_does_not_disarm_a_stop,
]

if __name__ == "__main__":
    print("Section Stop Tests")
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
