"""
Unit tests for the separation walk (``grouper_separate``), called directly
rather than through ``MarkdownGrouper.process``.

The walk is exercised by most of the grouping suite already, but always end to
end, where a change in the ORDER it applies its cuts shows up as a different
tree without saying which rule moved. These call it on one node at a time and
assert the precedence itself, because that order is the part a refactor can
reorder silently:

    springs  >  colon columns  >  bullets and rules

The walk is also the grouper module that most invites a decomposition (see
decisions/ADR-000-architecture-and-structure.md); these are the assertions such
a rewrite has to keep true.

Run with: uv run tests/grouper_separation_walk_tests.py
"""

from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.grouper_ids import IdMint
from md2ui.pipeline.grouper_separate import _separate_structured_content_walk
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.markdown_grouper import MarkdownGrouper


def _walk(text: str, ids: IdMint | None = None) -> MarkdownGroupNode:
    """Run the walk on ONE text leaf written as a single source line."""
    node = MarkdownGroupNode(type=NodeType.TEXT, content=text)
    node.source_line_id = 1
    _separate_structured_content_walk(
        node,
        DataPointDetector(),
        None,
        MarkdownGrouper._ANNOTATE_DEFAULT_LABELS,
        ids or IdMint(),
    )
    return node


def _shape(node: MarkdownGroupNode):
    """``(type, content, [children])`` one level deep — enough to see the cut."""
    return [
        (c.type, c.content, [(g.type, g.content) for g in c.children])
        for c in node.children
    ]


def test_a_bullet_line_becomes_flat_segments():
    assert _shape(_walk("A | B")) == [
        (NodeType.SEGMENT, "A", []),
        (NodeType.SEGMENT, "B", []),
    ]


def test_a_colon_line_stacks_its_pieces():
    """A spaced colon is a COLUMN split — same segment pieces as a bullet
    line, and it is the flag on the parent that makes them stack."""
    assert _shape(_walk("A : B")) == [
        (NodeType.SEGMENT, "A", []),
        (NodeType.SEGMENT, "B", []),
    ]


def test_a_comma_stays_in_a_finished_piece():
    assert _shape(_walk("A | B, C")) == [
        (NodeType.SEGMENT, "A", []),
        (NodeType.SEGMENT, "B, C", []),
    ]


def test_a_key_value_keeps_the_comma_in_its_value():
    shape = _shape(_walk("Key: A, B"))
    assert [(t, c) for t, c, _ in shape] == [(NodeType.KEY_VALUE, "")]
    assert shape[0][2] == [(NodeType.KEY, "Key"), (NodeType.VALUE, "A, B")]


def test_prose_is_left_whole():
    """Nothing in a sentence is a separator, so the walk must not touch it."""
    node = _walk("plain sentence here")
    assert node.children == []
    assert node.content == "plain sentence here"


def test_the_pieces_of_one_line_share_one_fresh_glued_id():
    """Content separated out of a lone source line is ONE glued segment, so the
    walk spends exactly one id and puts it on every piece. This is the thread
    that runs from IdMint through _inherit_glue into the walk."""
    ids = IdMint()
    node = _walk("A | B", ids)
    assert [c.glued_content_id for c in node.children] == [0, 0]
    assert ids.next_glued() == 1, "exactly one id was spent"


def test_two_walks_do_not_share_a_counter():
    """The mint is passed in, not reached for, so two documents start at 0."""
    a, b = IdMint(), IdMint()
    _walk("A | B", a)
    node = _walk("A | B", b)
    assert [c.glued_content_id for c in node.children] == [0, 0]


def test_a_stranded_column_colon_is_dropped_not_drawn():
    """A colon with a space on each side is the COLUMN separator. When
    whatever cut first consumed the text on its left, the colon is left
    leading a finished piece, where no scan can reach it — the column split
    needs a space on the LEFT and a piece starts at index 0. An empty column
    cell is nothing, so the separator that named it goes too, on every route
    that can strand one."""
    assert _shape(_walk("Status - : Active")) == [
        (NodeType.SEGMENT, "Status", []),
        (NodeType.SEGMENT, "Active", []),
    ]
    assert _shape(_walk("A : : B")) == [
        (NodeType.SEGMENT, "A", []),
        (NodeType.SEGMENT, "B", []),
    ]
    assert _shape(_walk("Key: : v")) == [
        (NodeType.SEGMENT, "Key:", []),
        (NodeType.SEGMENT, "v", []),
    ]


def test_the_column_colon_outranks_a_key_value_colon():
    """A separator outranks a tight colon (ADR-205): ``K: A : B`` folds into
    columns around the spaced colon, the tight one kept in its piece, exactly
    as its escaped twin ``K\\: A : B`` does."""
    node = _walk("Key: A : B")
    assert node.column_split_group
    assert _shape(node) == [
        (NodeType.SEGMENT, "Key: A", []),
        (NodeType.SEGMENT, "B", []),
    ]


TESTS = [
    test_a_bullet_line_becomes_flat_segments,
    test_a_colon_line_stacks_its_pieces,
    test_a_stranded_column_colon_is_dropped_not_drawn,
    test_the_column_colon_outranks_a_key_value_colon,
    test_a_comma_stays_in_a_finished_piece,
    test_a_key_value_keeps_the_comma_in_its_value,
    test_prose_is_left_whole,
    test_the_pieces_of_one_line_share_one_fresh_glued_id,
    test_two_walks_do_not_share_a_counter,
]

if __name__ == "__main__":
    print("Grouper Separation Walk Tests")
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
