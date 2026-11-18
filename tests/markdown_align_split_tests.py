"""
Unit tests for the markdown ``...`` SPRING — the authored expanding gap.

A spring pushes what sits on either side of it toward opposite edges. It cuts a
line into REGIONS whose position is their alignment (first left, last right,
anything between centred), and it is split off BEFORE every other separator, so
each region reaches the separator / key-value / colon-column chain as an
ordinary line. A spring after a colon is no exception (ADR-205): `Key: ... Value`
is two regions, and the colon stays in the left one.

Run with: uv run tests/markdown_align_split_tests.py
"""

import sys

sys.path.insert(0, "tests")

from markdown_datapoint_split_tests import (
    _processed_with_criteria,
    assert_reads_as_escaped_twin,
)

from md2ui.pipeline.grouper_split_criteria import SENTENCE_BOUNDARY_RE
from md2ui.pipeline.markdown_grouper import NodeType
from md2ui.pipeline.grouper_separator_splits import _split_align_regions


def _regions(content: str, protected=None):
    return _split_align_regions(content, protected or [])


def _aligned_leaves(text: str) -> list[tuple[str, str | None]]:
    """``(content, effective align)`` per leaf of a processed line.

    The alignment is read through ancestors because it CASCADES: a region
    carries one value and every leaf under it inherits it.
    """
    out: list[tuple[str, str | None]] = []

    def walk(n, align):
        align = n.authored_align or align
        if not n.children:
            out.append((n.content, align))
        for c in n.children:
            walk(c, align)

    walk(_processed_with_criteria(text), None)
    return out


def _find(node, pred):
    if pred(node):
        return node
    for c in node.children:
        found = _find(c, pred)
        if found is not None:
            return found
    return None


# --- the split itself -------------------------------------------------------


def test_one_spring_splits_left_and_right():
    assert _regions("A ... B") == [("A", "left"), ("B", "right")]


def test_two_springs_give_left_center_right():
    assert _regions("A ... B ... C") == [
        ("A", "left"),
        ("B", "center"),
        ("C", "right"),
    ]


def test_springs_on_both_ends_centre_the_middle():
    """The empty regions are dropped but still take their slot."""
    assert _regions("... A ...") == [("A", "center")]


def test_leading_spring_pushes_everything_right():
    assert _regions("... A - B - C") == [("A - B - C", "right")]


def test_trailing_spring_pushes_everything_left():
    assert _regions("A - B ...") == [("A - B", "left")]


def test_four_regions_centre_every_middle():
    assert _regions("A ... B ... C ... D") == [
        ("A", "left"),
        ("B", "center"),
        ("C", "center"),
        ("D", "right"),
    ]


def test_a_line_of_only_springs_is_not_a_split():
    assert _regions("...") is None
    assert _regions("... ...") is None


def test_no_spring_is_no_split():
    assert _regions("A - B") is None


# --- what is NOT a spring ---------------------------------------------------


def test_four_dots_are_not_a_spring():
    assert _regions("A .... B") is None


def test_tight_dots_are_not_a_spring():
    assert _regions("wait...what") is None
    assert _regions("A ...B") is None
    assert _regions("A... B") is None


def test_a_protected_span_hides_its_spring():
    """The same guard that keeps ``-`` literal inside a datapoint or a quote."""
    content = 'say "A ... B" now'
    assert _regions(content, [(4, 12)]) is None


def test_a_spring_on_prose_is_a_spring():
    """A spaced ``...`` springs on any line, prose or not: a spring is authored,
    so a comma or a sentence never decides whether it aligns. An ellipsis is
    written escaped or unspaced.
    """
    assert _aligned_leaves("He paused ... unsure what to say next.") == [
        ("He paused", "left"),
        ("unsure what to say next.", "right"),
    ]
    assert _aligned_leaves(r"He paused \... unsure what to say next.") == [
        ("He paused ... unsure what to say next.", None)
    ]
    assert _aligned_leaves("He paused... unsure what to say next.") == [
        ("He paused... unsure what to say next.", None)
    ]


def test_a_comma_does_not_stop_a_spring():
    """The comma that makes a line read as prose leaves its spring alone."""
    assert _aligned_leaves("**Choco croissant, 110g** ... `460 kcal`") == [
        ("**Choco croissant, 110g**", "left"),
        ("460 kcal", "right"),
    ]
    assert _aligned_leaves("Total, incl. tax ... $42.50") == [
        ("Total, incl. tax", "left"),
        ("$42.50", "right"),
    ]
    assert _aligned_leaves("Fruit, apples ... pears, plums ... figs, dates") == [
        ("Fruit, apples", "left"),
        ("pears, plums", "center"),
        ("figs, dates", "right"),
    ]


def test_a_protected_spring_on_prose_stays_text():
    """Springing on prose keeps the protected-range guard: dots inside a quote
    or a code span are content."""
    for src in (
        'She said "wait ... no" and left, slowly.',
        "Use `a ... b`, then go.",
    ):
        assert _aligned_leaves(src) == [(src, None)], src


def test_a_trailing_spring_on_prose_is_a_spring():
    """A spaced trailing ``...`` is a spring on any line; an author who means
    dots escapes them or drops the space."""
    assert _aligned_leaves("Loading your dashboard ...") == [
        ("Loading your dashboard", "left")
    ]
    assert _aligned_leaves(r"Loading your dashboard \...") == [
        ("Loading your dashboard ...", None)
    ]
    assert _aligned_leaves("Loading your dashboard...") == [
        ("Loading your dashboard...", None)
    ]


# --- through the whole grouper ----------------------------------------------


def test_spring_binds_looser_than_the_dash():
    """``A ... B - C``: A left, and B and C both right behind the one dash."""
    assert _aligned_leaves("A ... B - C") == [
        ("A", "left"),
        ("B", "right"),
        ("C", "right"),
    ]


def test_the_dash_still_separates_inside_a_region():
    """The spring gap draws nothing; the region's own separator survives."""
    root = _processed_with_criteria("A ... B - C")
    region = _find(root, lambda n: n.authored_align == "right")
    assert region is not None
    assert region.separator_chars == ["-"]
    holder = _find(root, lambda n: n.align_group)
    assert holder is not None
    assert holder.separator_chars == []


def test_the_spring_line_still_flows_as_a_row():
    """Regions are containers, so without the exception they would grid."""
    root = _processed_with_criteria("450 : Projects ... 35 : Users")
    holder = _find(root, lambda n: n.align_group)
    assert holder is not None
    assert holder.line_split_group


def test_colon_columns_align_as_units():
    """A spring aligns the stacked columns, and cascades onto their leaves."""
    assert _aligned_leaves("450 : Projects ... 35 : Users") == [
        ("450", "left"),
        ("Projects", "left"),
        ("35", "right"),
        ("Users", "right"),
    ]


def test_whole_line_wrap_reaches_every_region():
    assert _aligned_leaves("**A ... B - C**") == [
        ("**A**", "left"),
        ("**B**", "right"),
        ("**C**", "right"),
    ]


def test_a_tier_survives_the_split():
    """``___x___`` is consumed into a text_style, exactly as the dash does it."""
    root = _processed_with_criteria("___A___ ... B")
    display = _find(root, lambda n: n.content == "A")
    assert display is not None and display.text_style == "display"


# --- inside a heading line --------------------------------------------------
#
# The heading TEXT node is not the heading GROUP: the group is a whole section
# (the heading plus every body line under it), while the text node is one source
# line that may itself become a container. The spring splits the text node, which
# keeps its ``heading{N}`` label and holds the regions — that label is the anchor
# ``layout_render._stamp_heading_ctx`` reads, so every region keeps the heading's
# typography.


def test_a_spring_splits_a_heading_line():
    root = _processed_with_criteria("## A ... B - C")
    holder = _find(root, lambda n: n.align_group)
    assert holder is not None
    assert holder.type == "heading2", holder.type
    assert _aligned_leaves("## A ... B - C") == [
        ("A", "left"),
        ("B", "right"),
        ("C", "right"),
    ]


def test_a_trailing_spring_on_a_heading_pushes_the_title_left():
    assert _aligned_leaves("## Title ...") == [("Title", "left")]


def test_a_spring_line_reads_as_the_unsprung_line():
    """Springs only align: the region says what the line said without them."""
    assert _aligned_leaves("... nora.vasquez_@example.com ...") == [
        ("nora.vasquez_@example.com", "center")
    ]


def test_a_heading_button_goes_right():
    """The shape this was written for: a title left, an action button right.

    Trimming the trailing boundary LINK run must not turn the mid-line spring
    into a line-final one ("Transaction History ..."), read as prose truncation.
    """
    for level in range(1, 7):
        src = f"{'#' * level} Transaction History ... [`…`](/more)"
        assert _aligned_leaves(src) == [
            ("Transaction History", "left"),
            ("[`…`](/more)", "right"),
        ], src


def test_a_trailing_link_does_not_hide_a_spring():
    """…and the same line outside a heading."""
    assert _aligned_leaves("Recent orders ... [View all](/orders)") == [
        ("Recent orders", "left"),
        ("[View all](/orders)", "right"),
    ]


def test_a_spring_before_a_link_on_prose_still_springs():
    """A link authored BEHIND a spring on a prose line is pushed away like any
    other region; the escaped twin keeps its dots."""
    assert _aligned_leaves(r"Loading your dashboard \... [cancel](/x)") == [
        ("Loading your dashboard ... [cancel](/x)", None)
    ]
    assert _aligned_leaves("Loading your dashboard ... [cancel](/x)") == [
        ("Loading your dashboard", "left"),
        ("[cancel](/x)", "right"),
    ]


# --- Key: ... Value ---------------------------------------------------------


def test_a_kv_spring_is_two_regions_and_keeps_its_colon():
    """The spring sets the row as on any line; the colon is the left text's,
    styled key or not, exactly as when it is escaped (ADR-205)."""
    for line, leaves in (
        ("Key: ... Value", [("Key:", "left"), ("Value", "right")]),
        ("**Total:** ... $128.00", [("**Total:**", "left"), ("$128.00", "right")]),
    ):
        root = _processed_with_criteria(line)
        assert _find(root, lambda n: n.align_group) is not None, line
        assert _find(root, lambda n: n.type == NodeType.KEY_VALUE) is None, line
        assert _aligned_leaves(line) == leaves, (line, _aligned_leaves(line))
        assert_reads_as_escaped_twin(line)


# --- serialization ----------------------------------------------------------


def test_the_flags_round_trip_through_the_ast_json():
    from md2ui.pipeline.markdown_grouper import MarkdownGroupNode

    root = _processed_with_criteria("A ... B - C")
    back = MarkdownGroupNode.from_dict(root.to_dict())
    assert _find(back, lambda n: n.align_group) is not None
    assert sorted(
        n.authored_align for n in (back, *_all(back)) if n.authored_align
    ) == ["left", "right"]


def _all(node):
    for c in node.children:
        yield c
        yield from _all(c)


# ---------------------------------------------------------------------------
# A spring is not a full stop
# ---------------------------------------------------------------------------


def test_a_spring_is_not_a_sentence_boundary():
    """The dot-run must not read as ". Capital".

    In "Alpha ... Beta" the LAST dot of the spring plus " B" would match
    `SENTENCE_BOUNDARY_RE` without its lookbehind, judging an aligned line two
    sentences, one of `has_prose_signal`'s unambiguous prose tells.
    """
    assert not SENTENCE_BOUNDARY_RE.search("Alpha ... Beta")
    assert not SENTENCE_BOUNDARY_RE.search("Alpha .. Beta")
    # ...and every genuine boundary still reads as one.
    for prose in ("He paused. Then left.", "Total: 5. Done Now", "See fig. Two"):
        assert SENTENCE_BOUNDARY_RE.search(prose), prose
    print("  ✓  a run of dots is an ellipsis, not a sentence boundary")


def test_a_spring_region_keeps_its_commas():
    assert _aligned_leaves("Alpha ... Beta, Gamma") == [
        ("Alpha", "left"),
        ("Beta, Gamma", "right"),
    ]
    assert _aligned_leaves("Alpha ... Beta, Gamma ... Delta") == [
        ("Alpha", "left"),
        ("Beta, Gamma", "center"),
        ("Delta", "right"),
    ]
    print("  ✓  a spring region keeps its commas and its alignment")


def test_an_escaped_comma_is_harmless_in_a_spring_region():
    """`\\,` remains accepted and resolves to an ordinary comma."""
    assert _aligned_leaves(r"Alpha ... Beta\, Gamma") == [
        ("Alpha", "left"),
        ("Beta, Gamma", "right"),
    ]
    assert _aligned_leaves(r"Alpha ... Beta\, Gamma ... Delta") == [
        ("Alpha", "left"),
        ("Beta, Gamma", "center"),
        ("Delta", "right"),
    ]
    print("  ✓  an escaped comma resolves harmlessly in a spring region")


# --- one region only aligns its line -----------------------------------------
# A spring that leaves ONE region is arrangement, not a second piece: the item
# is its unsprung self plus the alignment, as the bare line already is.


def _item(text: str):
    item = _find(_processed_with_criteria(text), lambda n: n.type == "list_item")
    assert item is not None
    return item


def test_a_centred_item_is_a_leaf_like_the_bare_line():
    item = _item("- ... Word ...")
    assert (item.content, item.children, item.authored_align) == ("Word", [], "center")
    assert not item.align_group
    assert _aligned_leaves("- ... Word ...") == _aligned_leaves("... Word ...")


def test_a_pushed_item_folds_too():
    assert _item("- ... Word").authored_align == "right"
    assert _item("- ... Word").content == "Word"


def test_a_task_keeps_its_checkbox_left_of_a_folded_spring():
    assert _aligned_leaves("- [ ] ... Word") == [("[ ]", "left"), ("Word", "right")]
    assert _aligned_leaves("- [ ] ... **A** - B") == [
        ("[ ]", "left"),
        ("**A**", "right"),
        ("B", "right"),
    ]


def test_a_spring_line_alone_in_an_image_card_stays_a_row():
    """``![`` / ``A ... B`` / ``+++++`` / ``](url)``: the spring line is the card's
    only content, so the collapse dissolves the line's own group into the card.
    The card must still hold the pieces as one line, or the chip and the button
    stack (tests/tests-spring-row-syntax.md)."""
    for spacer in ("+++++\n", ""):
        text = f"![\n`Chip` ... [Save](agent:save)\n{spacer}](?w=800)\n**Bold**\n"
        holder = _find(
            _processed_with_criteria(text),
            lambda n: any(c.type == NodeType.INLINE_CODE for c in n.children),
        )
        assert holder is not None
        assert holder.line_split_group and holder.align_group, (
            spacer,
            [c.type for c in holder.children],
        )


TESTS = [
    test_a_spring_is_not_a_sentence_boundary,
    test_a_spring_region_keeps_its_commas,
    test_an_escaped_comma_is_harmless_in_a_spring_region,
    test_one_spring_splits_left_and_right,
    test_two_springs_give_left_center_right,
    test_springs_on_both_ends_centre_the_middle,
    test_leading_spring_pushes_everything_right,
    test_trailing_spring_pushes_everything_left,
    test_four_regions_centre_every_middle,
    test_a_line_of_only_springs_is_not_a_split,
    test_no_spring_is_no_split,
    test_four_dots_are_not_a_spring,
    test_tight_dots_are_not_a_spring,
    test_a_protected_span_hides_its_spring,
    test_a_spring_on_prose_is_a_spring,
    test_a_comma_does_not_stop_a_spring,
    test_a_protected_spring_on_prose_stays_text,
    test_a_trailing_spring_on_prose_is_a_spring,
    test_spring_binds_looser_than_the_dash,
    test_the_dash_still_separates_inside_a_region,
    test_the_spring_line_still_flows_as_a_row,
    test_colon_columns_align_as_units,
    test_whole_line_wrap_reaches_every_region,
    test_a_tier_survives_the_split,
    test_a_spring_splits_a_heading_line,
    test_a_trailing_spring_on_a_heading_pushes_the_title_left,
    test_a_spring_line_reads_as_the_unsprung_line,
    test_a_heading_button_goes_right,
    test_a_trailing_link_does_not_hide_a_spring,
    test_a_spring_before_a_link_on_prose_still_springs,
    test_a_kv_spring_is_two_regions_and_keeps_its_colon,
    test_the_flags_round_trip_through_the_ast_json,
    test_a_centred_item_is_a_leaf_like_the_bare_line,
    test_a_pushed_item_folds_too,
    test_a_task_keeps_its_checkbox_left_of_a_folded_spring,
    test_a_spring_line_alone_in_an_image_card_stays_a_row,
]


if __name__ == "__main__":
    print("Align Split (spring) Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓  {test.__name__}")
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
