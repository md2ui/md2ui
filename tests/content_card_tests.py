"""
Unit tests for block-content links and images ("content cards").

A construct whose label holds block markdown can't be flattened onto one line
the way Tier 1 flattens inline ones — its body needs to be grouped as its own
little document. `preprocess` swaps it for a one-line sentinel and stashes the
body; Phase 2.13 (`_expand_cards_walk`) expands the sentinel into a subtree,
early enough that every later phase walks the body exactly once, like any
other content.

    ![ ## Title … ](hero.png)   ->  image_card(card_bg_url=hero.png){ … }
    [ ## Title … ](/x)          ->  group(link_url=/x){ … }

Run with: uv run python tests/content_card_tests.py
"""

from md2ui.pipeline.grouper_block_splits import (
    _BLOCKQUOTE_LINE_RE,
    _LIST_MARKER_RE,
    _break_node_type,
)
from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.markdown_grouper import (
    MarkdownGrouper,
    NodeType,
    _CARD_SENTINEL_RE,
)

HERO = "hero.png"


def _processed(text: str):
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    return g.ast


def _find(node, type_):
    out = []
    if node.type == type_:
        out.append(node)
    for child in node.children:
        out.extend(_find(child, type_))
    return out


def _flat(node):
    """(type, content) for every node in the subtree, pre-order."""
    out = [(node.type, node.content)]
    for child in node.children:
        out.extend(_flat(child))
    return out


# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------


def test_sentinel_is_inert_to_every_line_classifier():
    """It must not read as a heading, rule, list, quote or table row."""
    token = "⟦md2ui-card-0⟧"
    assert not MarkdownGrouper.HEADING_PATTERN.match(token)
    # Every thematic-break spelling at once: rule, content break, section stop.
    assert _break_node_type(token) is None
    assert not _LIST_MARKER_RE.match(token)
    assert not _BLOCKQUOTE_LINE_RE.match(token)
    assert "|" not in token and token.strip() == token
    print("  ✓  the sentinel is inert to every line classifier")


def test_sentinel_never_survives_processing():
    ast = _processed(f"![\n## Title\nbody\n]({HERO})")
    assert not any(_CARD_SENTINEL_RE.search(c) for _, c in _flat(ast) if c), _flat(ast)
    print("  ✓  no sentinel survives into the final AST")


def test_legacy_entry_points_plant_no_sentinels():
    """subgroup_by_* never reach Phase 2.13, so they must not plant either."""
    g = MarkdownGrouper(f"![\n## Title\nbody\n]({HERO})")
    g.to_ast()
    assert g._card_specs == {}, g._card_specs
    assert not any(_CARD_SENTINEL_RE.search(c) for _, c in _flat(g.ast) if c)
    print("  ✓  legacy entry points plant no sentinels")


# ---------------------------------------------------------------------------
# Image cards
# ---------------------------------------------------------------------------


def test_image_with_markdown_alt_becomes_a_card():
    ast = _processed(f"![\n## Payday, the Monzo way\nGet paid early.\n]({HERO})")
    (card,) = _find(ast, NodeType.IMAGE_CARD)
    assert card.card_bg_url == HERO
    assert card.content == "", "a card must never keep content of its own"
    kinds = [c.type for c in card.children]
    assert kinds == ["heading2", "text"], kinds
    print("  ✓  an image with a markdown alt becomes a card")


def test_plain_image_is_untouched():
    """Descriptive alt text is not markdown — this must stay a plain image."""
    for text in [
        '![A long descriptive alt, with commas and "quotes"](p.png)',
        "![alt](p.png)",
        "![](p.png)",
    ]:
        ast = _processed(text)
        assert not _find(ast, NodeType.IMAGE_CARD), text
        assert _find(ast, NodeType.IMAGE), text
    print("  ✓  a plain image keeps its existing behaviour")


def test_single_line_label_is_never_block():
    """`[>](/next)` is a chevron button, not a blockquote."""
    for text in ["[>](/next)", "[a | b](/x)", "[- x](/x)", "[# h](/x)"]:
        ast = _processed(text)
        assert not _find(ast, NodeType.IMAGE_CARD), text
        assert MarkdownGrouper._construct_is_inline_only(text[1 : text.index("]")])
    print("  ✓  a single-line label is never treated as block content")


# ---------------------------------------------------------------------------
# Link cards
# ---------------------------------------------------------------------------


def test_block_content_link_is_an_annotated_group():
    ast = _processed(f"[\n![]({HERO})\n### Portal\n](/detail)")
    groups = [n for n in _find(ast, NodeType.GROUP) if n.link_url]
    assert len(groups) == 1, _flat(ast)
    card = groups[0]
    assert card.link_url == "/detail"
    assert [c.type for c in card.children] == ["image", "heading3"]
    print("  ✓  a block-content link is a group carrying link_url")


def test_link_wrapping_one_image_collapses_to_a_clickable_image():
    """The wrapper is redundant; the annotation must follow the survivor."""
    ast = _processed("[![](i.svg)](/x)")
    (img,) = _find(ast, NodeType.IMAGE)
    assert img.link_url == "/x", img.link_url
    print("  ✓  a link wrapping one image collapses to a clickable image")


def test_link_url_round_trips():
    from md2ui.pipeline.markdown_grouper import MarkdownGroupNode

    ast = _processed(f"[\n![]({HERO})\n### Portal\n](/detail)")
    restored = MarkdownGroupNode.from_dict(ast.to_dict())
    urls = [n.link_url for n in _find(restored, NodeType.GROUP) if n.link_url]
    assert urls == ["/detail"], urls
    print("  ✓  link_url survives to_dict/from_dict")


def test_card_bg_url_round_trips():
    from md2ui.pipeline.markdown_grouper import MarkdownGroupNode

    ast = _processed(f"![\n## Title\nbody\n]({HERO})")
    restored = MarkdownGroupNode.from_dict(ast.to_dict())
    (card,) = _find(restored, NodeType.IMAGE_CARD)
    assert card.card_bg_url == HERO
    print("  ✓  card_bg_url survives to_dict/from_dict")


# ---------------------------------------------------------------------------
# Nesting rules
# ---------------------------------------------------------------------------


def test_a_plain_link_inside_a_link_card_stays_a_button():
    """It has no block content, so it cannot nest further — it draws as a
    button, and the enclosing card's link_url is the click target."""
    ast = _processed("[\n### Title\nSee - [Docs](/x)\n](/outer)")
    (link,) = _find(ast, NodeType.LINK)
    assert link.content == "[Docs](/x)", link.content
    (card,) = [n for n in _find(ast, NodeType.GROUP) if n.link_url]
    assert card.link_url == "/outer"
    print("  ✓  a plain link inside a link card stays a button")


def test_a_link_card_inside_a_link_card_is_still_discarded():
    """The prohibition applies to same-kind CARDS, which could nest further."""
    ast = _processed("[\n### Outer\n[\n### Inner\nbody line\n](/inner)\n](/outer)")
    urls = sorted(n.link_url for n in _find(ast, NodeType.GROUP) if n.link_url)
    assert urls == ["/outer"], urls
    print("  ✓  a link card inside a link card is still discarded")


def test_a_button_survives_through_an_image_card():
    """apparel-jacket: link card -> image card -> button.

    The heart is a plain link, so it draws even though a link card encloses it.
    """
    ast = _processed(f"[\n![[`❤️`](/like/125)]({HERO})\nDenim Jacket\n](/detail/282)")
    (link,) = _find(ast, NodeType.LINK)
    assert link.content == "[`❤️`](/like/125)", link.content
    assert _find(ast, NodeType.IMAGE_CARD), _flat(ast)
    print("  ✓  a button survives inside an image card inside a link card")


def test_links_inside_an_image_card_survive():
    """place/content.md: no link ancestor, so the buttons stay buttons."""
    ast = _processed(f"![\n[🔖](/save)\n## Loft\n[Book now](/book/78727)\n]({HERO})")
    urls = sorted(n.content for n in _find(ast, NodeType.LINK))
    assert urls == ["[Book now](/book/78727)", "[🔖](/save)"], urls
    print("  ✓  links inside an image card survive when no link encloses them")


def test_a_plain_image_inside_an_image_card_is_kept():
    """It cannot nest further, so it renders as ordinary content — and the
    card keeps its own background."""
    ast = _processed(f"![\n### T\n![inner](in.png)\nbody\n]({HERO})")
    (card,) = _find(ast, NodeType.IMAGE_CARD)
    (img,) = _find(card, NodeType.IMAGE)
    assert img.content == "![inner](in.png)", img.content
    assert card.card_bg_url == HERO, "the card keeps its own background"
    print("  ✓  a plain image inside an image card is kept as content")


def test_an_image_card_inside_an_image_card_is_dropped():
    """A same-kind CARD could nest further, so it is still prohibited."""
    ast = _processed(f"![\n### T\n![\n## Inner\nbody\n](in.png)\n]({HERO})")
    cards = _find(ast, NodeType.IMAGE_CARD)
    assert len(cards) == 1, [c.card_bg_url for c in cards]
    assert cards[0].card_bg_url == HERO
    print("  ✓  an image card inside an image card is still dropped")


def test_a_card_inside_a_list_item_parses_its_headings():
    """The body carries the item's continuation indent, which must be
    stripped or `## Title` never matches HEADING_PATTERN."""
    for indent in ("  ", "    "):
        md = (
            f"- ![\n\n{indent}[`❤️`](/like)\n\n{indent}## New York\n\n"
            f"{indent}Economy\n\n{indent}]({HERO})"
        )
        ast = _processed(md)
        heads = [t for t, _ in _flat(ast) if str(t).startswith("heading")]
        assert heads == ["heading2"], f"{indent!r}: {_flat(ast)}"
        raw = [c for t, c in _flat(ast) if c.startswith("##")]
        assert raw == [], f"{indent!r}: unparsed heading {raw}"
    print("  ✓  a card in a list item parses its body's headings")


# ---------------------------------------------------------------------------
# Structure survival
# ---------------------------------------------------------------------------


def test_single_child_card_survives_collapse():
    """_collapse_groups unwraps a one-child GROUP — a card must resist."""
    ast = _processed(f"![\n## Only a heading\n]({HERO})")
    (card,) = _find(ast, NodeType.IMAGE_CARD)
    assert card.card_bg_url == HERO
    assert len(card.children) == 1
    print("  ✓  a single-child card survives _collapse_groups")


def test_card_inside_a_list_item_keeps_the_marker():
    """The item absorbs the card (full overlap) but must keep the photo."""
    ast = _processed(f"- before\n- ![\n## Title\nbody\n]({HERO})\n- after")
    items = _find(ast, NodeType.LIST_ITEM)
    assert len(items) == 3, [i.content for i in items]
    carrying = [i for i in items if i.card_bg_url == HERO]
    assert len(carrying) == 1, [(i.content, i.card_bg_url) for i in items]
    print("  ✓  a card inside a list item keeps its marker and its photo")


def test_card_body_gets_list_structure():
    ast = _processed(f"![\n## Title\n- one\n- two\n]({HERO})")
    (card,) = _find(ast, NodeType.IMAGE_CARD)
    assert len(_find(card, NodeType.LIST_ITEM)) == 2, _flat(card)
    print("  ✓  a card body gets its own list structure")


def test_neighbours_are_undisturbed():
    """The card's heading body wins the background, so it is a heading group
    carrying the photo — but it is still exactly one node between the two."""
    ast = _processed(f"Before\n\n![\n## Title\nbody\n]({HERO})\n\nAfter")
    kinds = [c.type for c in ast.children]
    assert len(kinds) == 3 and kinds[0] == "text" and kinds[2] == "text", kinds
    middle = ast.children[1]
    assert middle.card_bg_url == HERO and middle.heading_group, middle.type
    print("  ✓  a card does not disturb its neighbours")


def test_a_card_costs_no_extra_detection():
    """The whole point of expanding at Phase 2.13.

    Detection dominates the grouper's cost, and Phases 3, 4+5 and 5.5 each call
    `detect_all` per node. A card body must therefore be
    spliced in as raw structure and ride those shared passes once — building it
    with a nested `process()` would run all three over it a second time. This
    pins that: wrapping content in a card must not add detector calls.
    """
    body = "## Loft - `$890`\nA cliffside loft.\n[Book now](/book/1)"

    class Counting(DataPointDetector):
        calls = 0

        def detect_all(self, text):
            Counting.calls += 1
            return super().detect_all(text)

    def run(md: str) -> int:
        Counting.calls = 0
        g = MarkdownGrouper(md)
        g.process(criteria=None, detector=Counting())
        return Counting.calls

    plain = run(body)
    carded = run(f"![\n{body}\n]({HERO})")
    assert carded == plain, (
        f"card body detected {carded - plain} extra times — "
        "someone reintroduced a nested process()"
    )
    print("  ✓  wrapping content in a card costs no extra detection")


# ---------------------------------------------------------------------------
# Group links: a label of glued lines
# ---------------------------------------------------------------------------

# data/markdown/tests-render/linked-file-cards: three file cards, title over caption.
GLUED_LABELS = (
    "[**Flights CDMX**\n_Edited Oct 4_](/a)\n\n"
    "[**Gastos 2026**\n_Edited Oct 1_](/b)\n\n"
    "[**Carta justificacion**\n_Edited Sep 22_](/c)"
)


def _shape(node):
    """What a card is, without the ids that count lines."""
    kids = tuple(_shape(c) for c in node.children)
    return (node.type, node.content, node.link_url, node.text_style, kids)


def test_glued_label_lines_make_a_group_link():
    """Each line an element styled as it would be outside a link, the whole
    card the link; same-shape cards share a fingerprint, so they grid."""
    ast = _processed(GLUED_LABELS)
    assert not _find(ast, NodeType.LINK), _flat(ast)
    cards = [n for n in _find(ast, NodeType.GROUP) if n.link_url]
    assert [c.link_url for c in cards] == ["/a", "/b", "/c"], _flat(ast)
    for card in cards:
        title, caption = card.children
        assert card.glued_content_group, card.node_id
        assert title.type == "text" and title.content.startswith("**"), title.content
        assert caption.text_style == "muted" and "_" not in caption.content
    assert len({c.fingerprint_hash for c in cards}) == 1
    print("  ✓  a label of glued lines is a group link")


def test_bracketed_glued_label_matches_the_inline_one():
    inline = _processed("[**Gastos 2026**\n_Edited Oct 1_](/b)")
    bracketed = _processed("[\n**Gastos 2026**\n_Edited Oct 1_\n](/b)")
    assert _shape(inline) == _shape(bracketed), (_flat(inline), _flat(bracketed))
    assert [n.link_url for n in _find(inline, NodeType.GROUP)] == ["/b"], _flat(inline)
    print("  ✓  the bracketed glued label is the same card as the inline one")


def test_a_label_without_glued_lines_stays_a_pill():
    """One line, however spelled, is a button; so is a link wrapped inside a
    sentence, and a multi-line image alt stays metadata."""
    for text in [
        "[**Gastos 2026** _Edited Oct 1_](/b)",
        "[\nPreview\n](/b)",
        "[\nPreview\n\nmore\n](/b)",
    ]:
        ast = _processed(text)
        assert [n.type for n in ast.children] == ["link"], (text, _flat(ast))
    ast = _processed("See the [long wrapped\nlabel](/b) mid-sentence.")
    assert not [n for n in _find(ast, NodeType.GROUP) if n.link_url], _flat(ast)
    ast = _processed("![two glued\nalt lines](p.png)")
    assert _find(ast, NodeType.IMAGE) and not _find(ast, NodeType.IMAGE_CARD)
    print("  ✓  a label without glued lines stays a pill")


def test_a_list_item_of_glued_label_lines_is_a_group_link():
    """The item keeps its marker and becomes the card, as a heading card in an
    item does; three of them share a fingerprint, so they grid as items do.
    A one-line link item stays a pill."""
    ast = _processed(
        "- [**Flights CDMX**\n  _Edited Oct 4_](/a)\n"
        "- [**Gastos 2026**\n  _Edited Oct 1_](/b)\n"
        "- [\n  **Carta**\n  _Edited Sep 22_\n  ](/c)\n"
        "- [One line](/d)"
    )
    items = _find(ast, NodeType.LIST_ITEM)
    assert [i.link_url for i in items] == ["/a", "/b", "/c", None], _flat(ast)
    for item in items[:3]:
        title, caption = item.children
        assert title.content.startswith("**") and caption.text_style == "muted"
    assert len({i.fingerprint_hash for i in items[:3]}) == 1
    assert [c.type for c in items[3].children] == ["link"], _flat(items[3])
    print("  ✓  a list item of glued label lines is a group link")


# ---------------------------------------------------------------------------
# Row links: a one-line label with a spring
# ---------------------------------------------------------------------------


def test_a_list_item_of_a_spring_label_is_a_row_link():
    """A one-line label holding a ` ... ` spring is a card of that line: its
    ` - ` divides, the spring pushes, and the item is the link (a settings row)."""
    ast = _processed(
        "- [👥 - Invite a friend ... **❯**](/invite)\n"
        "- [**Pro plan** : _Best for teams_ ... **❯**](/pro)"
    )
    items = _find(ast, NodeType.LIST_ITEM)
    assert [i.link_url for i in items] == ["/invite", "/pro"], _flat(ast)
    assert not _find(ast, NodeType.LINK), _flat(ast)

    def leaves(n):
        return [n] if not n.children else [x for c in n.children for x in leaves(c)]

    first = [(n.type, n.content) for n in leaves(items[0])]
    assert first == [("emoji", "👥"), ("segment", "Invite a friend"), ("emoji", "❯")], (
        first
    )
    print("  ✓  a list item of a spring label is a row link")


def test_a_spring_label_alone_on_its_line_is_a_row_link():
    ast = _processed("[📷 - Instagram ... **❯**](/ig)")
    assert [n.link_url for n in _find(ast, NodeType.GROUP) if n.link_url] == ["/ig"], (
        _flat(ast)
    )
    assert not _find(ast, NodeType.LINK), _flat(ast)
    print("  ✓  a spring label alone on its line is a row link")


def test_a_one_line_label_without_a_spring_stays_a_pill():
    """Names carry ` - ` (`Amazon - Echo Show 11`), a tight colon is text, an
    escaped mark is text, and a spring inside a sentence or beside another
    button is prose: every one stays a pill, as today."""
    for text in [
        "- [Amazon - Echo Show 11](/a)",
        "[Area: Westside ✕](/b)",
        "[🛒 6 \\| $800.72](/c)",
        "[mph : 100](/d)",
        "[Plan | Pro](/e)",
        "[a \\... b](/f)",
    ]:
        ast = _processed(text)
        assert _find(ast, NodeType.LINK), (text, _flat(ast))
        assert not [n for n in _find(ast, NodeType.GROUP) if n.link_url], (
            text,
            _flat(ast),
        )
    for text in ["Read [a ... b](/g) now.", "[Save](/s) [Share ... now](/h)"]:
        ast = _processed(text)
        assert not [n for n in _find(ast, NodeType.GROUP) if n.link_url], (
            text,
            _flat(ast),
        )
    print("  ✓  a one-line label without a spring stays a pill")


TESTS = [
    test_sentinel_is_inert_to_every_line_classifier,
    test_sentinel_never_survives_processing,
    test_legacy_entry_points_plant_no_sentinels,
    test_image_with_markdown_alt_becomes_a_card,
    test_plain_image_is_untouched,
    test_single_line_label_is_never_block,
    test_block_content_link_is_an_annotated_group,
    test_link_wrapping_one_image_collapses_to_a_clickable_image,
    test_link_url_round_trips,
    test_card_bg_url_round_trips,
    test_a_plain_link_inside_a_link_card_stays_a_button,
    test_a_link_card_inside_a_link_card_is_still_discarded,
    test_a_button_survives_through_an_image_card,
    test_links_inside_an_image_card_survive,
    test_a_plain_image_inside_an_image_card_is_kept,
    test_an_image_card_inside_an_image_card_is_dropped,
    test_a_card_inside_a_list_item_parses_its_headings,
    test_single_child_card_survives_collapse,
    test_card_inside_a_list_item_keeps_the_marker,
    test_card_body_gets_list_structure,
    test_neighbours_are_undisturbed,
    test_a_card_costs_no_extra_detection,
    test_glued_label_lines_make_a_group_link,
    test_bracketed_glued_label_matches_the_inline_one,
    test_a_label_without_glued_lines_stays_a_pill,
    test_a_list_item_of_glued_label_lines_is_a_group_link,
    test_a_list_item_of_a_spring_label_is_a_row_link,
    test_a_spring_label_alone_on_its_line_is_a_row_link,
    test_a_one_line_label_without_a_spring_stays_a_pill,
]

if __name__ == "__main__":
    print("Content Card Tests")
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
