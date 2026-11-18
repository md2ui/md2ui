"""
Unit tests for heading isolation around content cards.

The grouper nests content by heading level. A card body is its own document:
its headings must not participate in the outer hierarchy in either direction.
Without this, `### Title` inside a link opens a real section that swallows
every following block.

    # Level1
      ## Level2          <- outer section, unaffected
      ![ # Inner1 … ]()  <- card: own root, its # does not close # Level1
      ## Level2
    # Level1             <- still opens a second top-level section

Isolation outward comes from the sentinel (the document-level pass sees one
opaque line); isolation inward comes from `_build_block_ast` being run on the
body alone.

Run with: uv run python tests/content_card_hierarchy_tests.py
"""

from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.markdown_grouper import MarkdownGrouper, NodeType

HERO = "hero.png"

CARD = f"![\n# Inner1\n## Inner2\ninner body\n]({HERO})"

WITHOUT = """# Level1

## Level2 A

## Level2 B

### Level3

# Level1 Two

## Level2 C
"""

WITH = f"""# Level1

## Level2 A

{CARD}

## Level2 B

### Level3

# Level1 Two

## Level2 C
"""


def _processed(text: str):
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    return g.ast


def _find(node, type_):
    out = [node] if node.type == type_ else []
    for child in node.children:
        out.extend(_find(child, type_))
    return out


def _headings(node, inside_card=False):
    """(level, text, inside_card) for every heading leaf in the subtree."""
    out = []
    inside = inside_card or node.type == NodeType.IMAGE_CARD
    if node.type.startswith("heading") and node.content:
        out.append((int(node.type[-1]), node.content, inside))
    for child in node.children:
        out.extend(_headings(child, inside))
    return out


def _outer_sections(ast):
    """Top-level heading-1 sections of the document."""
    return [c for c in ast.children if c.heading_group and c.heading_level == 1]


def test_card_headings_do_not_close_outer_sections():
    """The card's `# Inner1` must not end the enclosing `# Level1`."""
    ast = _processed(WITH)
    sections = _outer_sections(ast)
    assert len(sections) == 2, [c.type for c in ast.children]
    print("  ✓  card headings do not close an outer section")


def test_outer_hierarchy_matches_the_card_free_document():
    """Same outer shape with and without the card present."""
    outer_with = [
        (lvl, txt) for lvl, txt, in_card in _headings(_processed(WITH)) if not in_card
    ]
    outer_without = [(lvl, txt) for lvl, txt, _ in _headings(_processed(WITHOUT))]
    assert outer_with == outer_without, (outer_with, outer_without)
    print("  ✓  the outer heading hierarchy is identical either way")


def test_card_headings_live_only_inside_the_card():
    ast = _processed(WITH)
    inner = [(lvl, txt) for lvl, txt, in_card in _headings(ast) if in_card]
    assert inner == [(1, "Inner1"), (2, "Inner2")], inner
    outer_texts = [txt for _, txt, in_card in _headings(ast) if not in_card]
    assert "Inner1" not in outer_texts and "Inner2" not in outer_texts
    print("  ✓  card headings appear nowhere in the outer tree")


def test_card_body_nests_by_its_own_levels():
    """Inside the card, `## Inner2` nests under `# Inner1` as its own document."""
    (card,) = _find(_processed(WITH), NodeType.IMAGE_CARD)
    levels = [lvl for lvl, _, _ in _headings(card)]
    assert levels == [1, 2], levels
    sections = _find(card, NodeType.GROUP)
    assert any(s.heading_group for s in sections), "body should form a section"
    print("  ✓  a card body nests by its own heading levels")


def test_heading_levels_stay_literal():
    """Levels are what the author wrote — only nesting is scoped."""
    (card,) = _find(_processed(WITH), NodeType.IMAGE_CARD)
    assert _headings(card)[0][0] == 1, "a card's `#` stays heading1 for styling"
    print("  ✓  heading levels inside a card stay literal")


def test_content_after_a_card_is_not_swallowed():
    """Nothing after the card ends up inside it."""
    ast = _processed(
        f"[\n![]({HERO})\n### Portal\n](/a)\n\n[\n![]({HERO})\nMasaya\n](/b)"
    )
    urls = sorted(n.link_url for n in ast.children if n.link_url)
    assert urls == ["/a", "/b"], [(c.type, c.link_url) for c in ast.children]
    print("  ✓  content after a card is not swallowed by it")


TESTS = [
    test_card_headings_do_not_close_outer_sections,
    test_outer_hierarchy_matches_the_card_free_document,
    test_card_headings_live_only_inside_the_card,
    test_card_body_nests_by_its_own_levels,
    test_heading_levels_stay_literal,
    test_content_after_a_card_is_not_swallowed,
]

if __name__ == "__main__":
    print("Content Card Hierarchy Tests")
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
