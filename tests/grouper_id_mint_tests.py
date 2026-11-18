"""
Unit tests for the document id counters (``grouper_ids.IdMint``) and the
inheritance rule that spends them (``_inherit_glue``).

This is the grouper's only genuinely mutable state. It is an explicit object,
not attributes on ``MarkdownGrouper``, so the phases that mint ids can be
ordinary functions in their own modules.

These tests pin BEHAVIOUR, not the shape of the code: WHEN a fresh segment id is
minted, and when one must not be, is the part a refactor can silently change.
The grouper snapshot catches a change to the ids a real document produces; these
say why.

Run with: uv run tests/grouper_id_mint_tests.py
"""

from md2ui.pipeline.grouper_ids import IdMint, _inherit_glue
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType


def _leaf(content="x", **kw):
    """A TEXT leaf. ``MarkdownGroupNode`` takes only content and type, so the
    ids are set after construction."""
    node = MarkdownGroupNode(type=NodeType.TEXT, content=content)
    for k, v in kw.items():
        setattr(node, k, v)
    return node


def test_ids_start_at_zero_and_are_consecutive():
    """The first id of a document is 0 and each mint is the next integer."""
    ids = IdMint()
    assert [ids.next_glued() for _ in range(3)] == [0, 1, 2]


def test_the_two_counters_are_independent():
    """Glued-segment ids and source-line ids mean different things, so they
    are numbered separately — a document's third line is line id 2 however
    many glued segments it happens to contain."""
    ids = IdMint()
    ids.next_glued()
    ids.next_glued()
    assert ids.next_source_line() == 0
    assert ids.next_glued() == 2


def test_two_documents_never_share_a_counter():
    """Ids are document-unique, not process-unique. Two mints are two
    documents; a module-level counter would make them one."""
    a, b = IdMint(), IdMint()
    a.next_glued()
    a.next_glued()
    assert b.next_glued() == 0


def test_a_parents_id_is_copied_to_id_less_children():
    """A split stays inside its parent's segment, so its pieces belong to it
    and nothing is minted."""
    ids = IdMint()
    parent = _leaf(glued_content_id=7)
    kids = [_leaf("a"), _leaf("b")]
    _inherit_glue(parent, kids, ids)
    assert [c.glued_content_id for c in kids] == [7, 7]
    assert ids.next_glued() == 0, "inheriting must not spend an id"


def test_a_child_that_already_has_an_id_keeps_it():
    """Non-overwrite: an id set at an earlier origin outranks the parent's."""
    ids = IdMint()
    parent = _leaf(glued_content_id=7)
    keeps, takes = _leaf("a", glued_content_id=3), _leaf("b")
    _inherit_glue(parent, [keeps, takes], ids)
    assert (keeps.glued_content_id, takes.glued_content_id) == (3, 7)


def test_an_id_less_parent_mints_one_segment_for_its_pieces():
    """Content separated out of a lone source line is one glued segment of its
    own — ONE id, shared, and it goes on the children only. The parent stays
    id-less: _wrap_glued_content places the group flag from the children."""
    ids = IdMint()
    parent = _leaf()
    kids = [_leaf("a"), _leaf("b"), _leaf("c")]
    _inherit_glue(parent, kids, ids)
    assert [c.glued_content_id for c in kids] == [0, 0, 0]
    assert parent.glued_content_id is None
    assert ids.next_glued() == 1, "exactly one id was spent"


def test_a_single_piece_is_not_a_segment():
    """A "split" that produced one piece separated nothing, so there is no
    segment and no id is spent."""
    ids = IdMint()
    parent = _leaf()
    only = _leaf("a")
    _inherit_glue(parent, [only], ids)
    assert only.glued_content_id is None
    assert ids.next_glued() == 0


def test_a_split_heading_does_not_become_a_glued_card():
    """Heading containers are excluded on purpose: a standalone heading that
    splits inline must not earn a card."""
    ids = IdMint()
    parent = MarkdownGroupNode(type="heading1", content="T")
    kids = [_leaf("a"), _leaf("b")]
    _inherit_glue(parent, kids, ids)
    assert [c.glued_content_id for c in kids] == [None, None]
    assert ids.next_glued() == 0


def test_the_source_line_id_rides_along_and_never_mints():
    """An intra-line split never crosses a line, so its pieces inherit the
    parent's line id — pure inheritance, no mint, on every path including the
    one that DOES mint a glued id."""
    ids = IdMint()
    parent = _leaf(source_line_id=4)
    kids = [_leaf("a"), _leaf("b")]
    _inherit_glue(parent, kids, ids)
    assert [c.source_line_id for c in kids] == [4, 4]
    assert ids.next_source_line() == 0


def test_an_unstamped_parent_leaves_the_line_id_alone():
    """Splits that run before Phase 2.3 stamps see a parent with no line id;
    those leaves are stamped directly later, so this must be a no-op rather
    than a mint."""
    ids = IdMint()
    parent = _leaf()
    kids = [_leaf("a"), _leaf("b")]
    _inherit_glue(parent, kids, ids)
    assert [c.source_line_id for c in kids] == [None, None]


TESTS = [
    test_ids_start_at_zero_and_are_consecutive,
    test_the_two_counters_are_independent,
    test_two_documents_never_share_a_counter,
    test_a_parents_id_is_copied_to_id_less_children,
    test_a_child_that_already_has_an_id_keeps_it,
    test_an_id_less_parent_mints_one_segment_for_its_pieces,
    test_a_single_piece_is_not_a_segment,
    test_a_split_heading_does_not_become_a_glued_card,
    test_the_source_line_id_rides_along_and_never_mints,
    test_an_unstamped_parent_leaves_the_line_id_alone,
]

if __name__ == "__main__":
    print("Grouper Id Mint Tests")
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
