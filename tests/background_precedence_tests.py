"""
Unit tests for background-role precedence when wrappers fully overlap.

Four node kinds paint a background: root, heading groups, glued content groups
and image cards. When one is the sole contentless child of another they cover
the same rect, differing only by padding. The order is

    heading  >  image card  >  glued  >  plain

applied by *role*, not by nesting direction — the inner wins in
``image card ⊃ heading``, the outer wins in ``heading ⊃ image card``. When an
image card loses, its photo transfers to the winner, which paints it with its
own corner radius and padding so a collapsed heading matches its siblings.

**The one full overlap that is NOT redundant is two heading sections at
different levels.** Each takes its fill, padding and scrim from its own level in
THEME.md, and an empty ``# `` marker is written precisely to open one around
another, so dissolving either deletes styling the author asked for. Sections
that share a level are still one container written twice and still collapse.
See ``_same_section_kind`` in ``grouper_glue``.

Fixture: data/markdown/tests/test-background-collapsing.md
Run with: uv run python tests/background_precedence_tests.py
"""

from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.markdown_grouper import MarkdownGrouper, NodeType

HERO = "hero.png"


def _processed(text: str):
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    return g.ast


def _roles(n) -> str:
    """The background roles a node holds, as a stable label."""
    out = []
    if n.type == "root":
        out.append("ROOT")
    if n.type == NodeType.IMAGE_CARD:
        out.append("IMGCARD")
    if n.heading_group:
        out.append(f"H{n.heading_level}")
    if n.glued_content_group:
        out.append("GLUED")
    return "+".join(out)


def _painters(node) -> list:
    """Every node in the subtree that would paint a background."""
    out = [node] if _roles(node) and node.type != "root" else []
    for child in node.children:
        out.extend(_painters(child))
    return out


# ---------------------------------------------------------------------------
# Precedence
# ---------------------------------------------------------------------------


def test_heading_beats_image_card_and_takes_the_photo():
    """image card ⊃ heading — the inner heading wins."""
    (node,) = _painters(_processed(f"![\n## Title\nbody line\n]({HERO})"))
    assert node.heading_group and node.heading_level == 2, _roles(node)
    assert node.card_bg_url == HERO, node.card_bg_url
    print("  ✓  a heading beats an image card and takes the photo")


def test_heading_wrapper_beats_image_card_and_takes_the_photo():
    """heading ⊃ image card — the outer heading wins. Same rule, other way."""
    (node,) = _painters(_processed(f"## \n![\n[a](/x)\nbody line\n]({HERO})"))
    assert node.heading_group, _roles(node)
    assert node.card_bg_url == HERO, node.card_bg_url
    print("  ✓  a heading wrapper beats an image card and takes the photo")


def test_image_card_beats_glued():
    """No heading in the body, so the card keeps the background."""
    (node,) = _painters(_processed(f"![\n[a](/x)\nbody line\n]({HERO})"))
    assert node.type == NodeType.IMAGE_CARD, _roles(node)
    assert node.card_bg_url == HERO
    print("  ✓  an image card beats glued content")


def test_heading_and_glued_collapse_to_one_node():
    (node,) = _painters(_processed("## Title\nbody line\nmore body"))
    assert node.heading_group and node.heading_level == 2, _roles(node)
    print("  ✓  a heading and its glued body are one node")


def test_an_empty_wrapper_keeps_its_own_level():
    """An empty ``## `` opens a section at its OWN level, so wrapping a ``### ``
    section leaves two. The inner still carries the title; what it does not do
    is inherit the wrapper's rect."""
    outer, inner = _painters(_processed("## \n### Real Title\nbody line\nmore body"))
    assert (outer.heading_level, inner.heading_level) == (2, 3), (
        f"got H{outer.heading_level} / H{inner.heading_level}"
    )
    assert inner in outer.children, "the H3 must sit INSIDE the H2, not beside it"
    print("  ✓  an empty wrapper keeps its own level around the inner section")


def test_a_same_level_wrapper_still_collapses():
    """The other half of the rule: two sections at the SAME level are one
    container written twice, so one of them is genuinely redundant."""
    (node,) = _painters(_processed(f"## \n![\n[a](/x)\n## Title\nbody line\n]({HERO})"))
    assert node.heading_group and node.heading_level == 2, _roles(node)
    print("  ✓  a same-level wrapper is still redundant and still collapses")


def test_an_empty_wrapper_survives_a_glued_body():
    """The inner section is glued content, which reaches a different branch of
    the collapse (the absorb); the wrapper survives there too."""
    outer, inner = _painters(_processed("# \n\n## \nContent\n"))
    assert (outer.heading_level, inner.heading_level) == (1, 2), (
        f"got H{outer.heading_level} / H{inner.heading_level}"
    )
    print("  ✓  an empty wrapper survives a glued inner section")


def test_a_chain_of_empty_markers_keeps_every_level():
    """Six markers, six containers. Each merge is judged against the level the
    survivor has just taken, so the chain stops at every boundary instead of
    flattening to the innermost."""
    md = "\n".join(f"{'#' * n} " for n in range(1, 7)) + "\nA"
    levels = [p.heading_level for p in _painters(_processed(md))]
    assert levels == [1, 2, 3, 4, 5, 6], levels
    print("  ✓  a chain of empty markers keeps every level")


def test_nested_headings_with_content_do_not_collapse():
    painters = _painters(_processed("## Outer\n### Inner\nbody line\nmore body"))
    levels = sorted(p.heading_level for p in painters if p.heading_group)
    assert levels == [2, 3], levels
    print("  ✓  nested headings with content keep both sections")


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


def test_empty_heading_dividers_survive():
    """A bare ``# `` divides content with no title — a documented usage."""
    ast = _processed("# Heading 1\n## Two A\n## Two B\nprose\n# \n## Two C\n## Two D")
    tops = [c for c in ast.children if c.heading_group]
    assert len(tops) == 2, [(_roles(c)) for c in ast.children]
    assert all(c.heading_level == 1 for c in tops), [c.heading_level for c in tops]
    print("  ✓  empty-heading dividers still divide")


def test_root_never_takes_a_photo():
    """Root paints in viewport space; a card's photo must never reach it."""
    ast = _processed(f"![\n[a](/x)\nbody line\n]({HERO})")
    assert ast.type == "root"
    assert ast.card_bg_url is None, ast.card_bg_url
    print("  ✓  root never receives a transferred photo")


def test_photo_does_not_climb_past_siblings():
    """A card with siblings is not a full overlap, so nothing absorbs it."""
    ast = _processed(
        f"# Doc\n\nintro line\n\n![\n[a](/x)\ncard text\n]({HERO})\n\noutro"
    )
    holders = [n for n in _painters(ast) if n.card_bg_url]
    assert len(holders) == 1, [(_roles(h), h.card_bg_url) for h in holders]
    top = ast.children[0]
    assert top.card_bg_url is None, "the photo escaped to the h1 section"
    print("  ✓  a photo never climbs past siblings")


def test_every_full_overlap_paints_once():
    """The fixture, end to end: no case may stack two REDUNDANT painters.

    A painter may nest when it covers a *part* of the parent (the parent has
    more than one child) — or when the whole stack is heading sections at
    distinct levels, the one full overlap that is not redundant. Any other
    full-extent pair means a background is being painted twice for nothing.
    """
    with open("data/markdown/tests/test-background-collapsing.md") as fh:
        ast = _processed(fh.read())
    for i, block in enumerate(ast.children, 1):
        nested = [p for p in _painters(block) if p is not block]
        if not nested or len(block.children) > 1:
            continue
        stack = [block, *nested]
        levels = [p.heading_level for p in stack]
        assert all(p.heading_group for p in stack) and len(set(levels)) == len(
            levels
        ), (
            f"block {i}: {_roles(block)} fully overlapped by "
            f"{[_roles(n) for n in nested]}"
        )
    print("  ✓  no fixture case stacks two redundant full-extent backgrounds")


# ---------------------------------------------------------------------------
# What counts as glued content
# ---------------------------------------------------------------------------


def test_a_flowed_single_line_is_not_glued():
    """Glue means consecutive lines; one line flowed aside has none to glue."""
    for md in [
        "🎉 Great news for everyone [more](/x)",
        "Denim Jacket [buy](/x)",
        "before ![alt](u.png) after",
        "`code` explanation text",
    ]:
        painters = _painters(_processed(md))
        assert not any(p.glued_content_group for p in painters), (
            f"{md!r}: {[_roles(p) for p in painters]}"
        )
    print("  ✓  a flowed single line is not glued content")


def test_a_pill_run_is_not_glued_either():
    """It flows via the generator's own pill path, so it carries no flag —
    but it is still one source line."""
    painters = _painters(_processed("[A](u) | [B](u) | [C](u)"))
    assert not any(p.glued_content_group for p in painters), [
        _roles(p) for p in painters
    ]
    print("  ✓  a homogeneous pill run is not glued content")


def test_every_key_value_pair_gets_its_own_glue():
    """Glue is minted per source LINE, but several pairs on one line must not
    share one wrapper, which is cleared as a flowed line. Each pair is its own
    unit and carries its own glue. The
    pairs are percentage bars, which keep their pair (ADR-205)."""
    for md in [
        "CPU: 40% - RAM: 60% - Disk: 80%",
        "`inline text` - CPU: 40% - RAM: 60% - Disk: 80%",
    ]:
        ast = _processed(md)
        pairs = [n for n in _painters(ast) if n.type == NodeType.KEY_VALUE]
        assert len(pairs) == 3, f"{md!r}: {[_roles(p) for p in pairs]}"
        assert all(p.glued_content_group for p in pairs), md
    print("  ✓  every K-V pair on a line gets its own glue")


def test_key_value_inside_a_paragraph_stays_unglued():
    """The paragraph is the card; nesting glue is forbidden."""
    (node,) = _painters(_processed("line one\nCPU: 40%\nline three"))
    assert node.glued_content_group and node.type != NodeType.KEY_VALUE
    kv = [n for n in _painters(node) if n.type == NodeType.KEY_VALUE and n is not node]
    assert kv == [], "a K-V inside a glued paragraph must not nest glue"
    print("  ✓  a K-V inside a glued paragraph stays unglued")


def test_key_value_on_a_heading_line_is_untouched():
    """Headings are out of scope — a heading's K-V must not become a card."""
    for md in ["## 💲 Monthly Budget: **$2,450**", "# Key: Value heading"]:
        ast = _processed(md)
        glued = [p for p in _painters(ast) if p.glued_content_group]
        assert glued == [], f"{md!r}: {[_roles(g) for g in glued]}"
    print("  ✓  a K-V on a heading line is untouched")


def test_a_key_value_line_stays_glued():
    """The bar takes its own line, so the pair really is two lines in a col."""
    (kv,) = _painters(_processed("CPU: 40%"))
    assert kv.type == NodeType.KEY_VALUE, kv.type
    assert kv.glued_content_group, "a K-V split stacks, so it IS glued"
    print("  ✓  a Key: value line stays glued")


def test_multiline_prose_stays_glued():
    (node,) = _painters(_processed("line one\nline two\nline three"))
    assert node.glued_content_group, _roles(node)
    print("  ✓  genuinely consecutive lines stay glued")


def test_a_group_holding_a_heading_is_not_glued():
    """A heading section is not a card, and neither is a bare heading wrapper."""
    (node,) = _painters(_processed("## Title\nbody line\nmore body"))
    assert node.heading_group and not node.glued_content_group, _roles(node)
    wrappers = _painters(_processed("# One\n## Two A\nbody line"))
    assert not any(
        w.glued_content_group and any(c.type.startswith("heading") for c in w.children)
        for w in wrappers
    ), [_roles(w) for w in wrappers]
    print("  ✓  a group holding a heading leaf is not glued")


TESTS = [
    test_a_flowed_single_line_is_not_glued,
    test_a_pill_run_is_not_glued_either,
    test_a_key_value_line_stays_glued,
    test_every_key_value_pair_gets_its_own_glue,
    test_key_value_inside_a_paragraph_stays_unglued,
    test_key_value_on_a_heading_line_is_untouched,
    test_multiline_prose_stays_glued,
    test_a_group_holding_a_heading_is_not_glued,
    test_heading_beats_image_card_and_takes_the_photo,
    test_heading_wrapper_beats_image_card_and_takes_the_photo,
    test_image_card_beats_glued,
    test_heading_and_glued_collapse_to_one_node,
    test_an_empty_wrapper_keeps_its_own_level,
    test_a_same_level_wrapper_still_collapses,
    test_an_empty_wrapper_survives_a_glued_body,
    test_a_chain_of_empty_markers_keeps_every_level,
    test_nested_headings_with_content_do_not_collapse,
    test_empty_heading_dividers_survive,
    test_root_never_takes_a_photo,
    test_photo_does_not_climb_past_siblings,
    test_every_full_overlap_paints_once,
]

if __name__ == "__main__":
    print("Background Precedence Tests")
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
