"""
Unit tests for multi-line link / image constructs.

Some markdown generators emit a link with its label on its own lines::

    [
    Preview
    ](/team-hub)

The grouper splits on blank lines and then on newlines before anything looks
for links, so such a construct would reach the detector as three unrelated
leaves ("[", "Preview", "](/team-hub)"). MarkdownGrouper's preprocess
flattens the inline-only ones onto a single line, which hands
the rest of the pipeline a shape it already handles.

The contract these tests pin down: a flattened construct is *byte-identical*
to the hand-written single-line form, so every downstream behaviour (variant,
emoji badge, pill sizing) follows for free.

Run with: uv run python tests/multiline_link_tests.py
"""

from md2ui.pipeline.markdown_grouper import (
    MarkdownGrouper,
    _scan_bracket_constructs,
)
from md2ui.pipeline.grouper_types import _classify_link_content

URL = "/@codatemplates/team-hub-quick-start"


def _flatten(text: str) -> str:
    """The flatten-only half of _rewrite_constructs.

    A grouper that has not been through `process()` leaves `_extract_cards`
    off, so block-content constructs are left alone instead of becoming card
    sentinels — the behaviour these tests pin down.
    """
    return MarkdownGrouper(text)._rewrite_constructs(text)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


def test_scanner_counts_nested_brackets():
    """The label may hold a whole image; [^\\]]* cannot count that."""
    (c,) = _scan_bracket_constructs("[![alt](i.svg)](/x)")
    assert not c.is_image, "outer construct is a link"
    assert c.inner == "![alt](i.svg)", c.inner
    assert c.url == "/x", c.url
    print("  ✓  scanner counts nested brackets")


def test_scanner_returns_top_level_only():
    """A nested construct belongs to its parent's label, not the top level."""
    found = _scan_bracket_constructs("a [![](i.svg)](/x) b ![](j.png) c")
    assert len(found) == 2, [f.inner for f in found]
    assert found[0].url == "/x" and found[1].url == "j.png"
    print("  ✓  scanner returns top-level constructs only")


def test_scanner_skips_escapes_and_bare_brackets():
    assert _scan_bracket_constructs(r"\[not a link\](x)") == []
    assert _scan_bracket_constructs("[unsupported element (code block)]") == []
    assert _scan_bracket_constructs("[label] (spaced)") == []
    print("  ✓  scanner skips escapes and bare brackets")


def test_scanner_balances_parens_in_url():
    (c,) = _scan_bracket_constructs("[a](/b(c)d)")
    assert c.url == "/b(c)d", c.url
    print("  ✓  scanner balances parens inside the URL")


def test_scanner_reads_a_links_destination():
    """A card's destination follows the link grammar: a bare space ends it, so
    a spaced one is no card and its brackets stay text, not a card to ``/my``.
    Angle brackets carry the space, and a title may follow."""
    card = "[![](a.png) Caption\non two lines]"
    found = _scan_bracket_constructs(card + "(/my file)")
    assert [c.url for c in found] == ["a.png"], [c.url for c in found]
    for dest in ("</my file>", '/x "A title"'):
        (c,) = _scan_bracket_constructs(f"{card}({dest})")
        assert c.url == dest and not c.is_image, c.url
    tree = str(_processed(card + "(/my file)").to_dict())
    assert "link_url" not in tree, "a spaced destination makes no card"
    print("  ✓  scanner reads a card's destination as a link's")


def test_scanner_abandons_runaway_candidate():
    """A stray "[" must not scan to end-of-document (O(N^2) guard)."""
    assert _scan_bracket_constructs("[" + "x\n" * 200 + "](/y)") == []
    print("  ✓  scanner abandons a runaway candidate")


# ---------------------------------------------------------------------------
# Flattening
# ---------------------------------------------------------------------------


def test_flatten_matches_single_line_form():
    """Every wrapper x label combination flattens to the written-out form."""
    labels = ["Preview", "❤️", "❤️ Preview", "`Preview`", "`❤️`"]
    wraps = ["", "*", "**", "***"]
    for label in labels:
        for w in wraps:
            multi = f"{w}[\n\n{label}\n\n]({URL}){w}"
            expected = f"{w}[{label}]({URL}){w}"
            assert _flatten(multi) == expected, (multi, _flatten(multi))
    print(f"  ✓  {len(labels) * len(wraps)} wrapper/label combinations flatten")


def test_flatten_preserves_variant_and_emoji():
    """The flattened form classifies exactly like the single-line one."""
    for label, wrap in [
        ("Preview", ""),
        ("Preview", "*"),
        ("Preview", "**"),
        ("Preview", "***"),
        ("`Preview`", "***"),
        ("❤️", ""),
        ("❤️", "***"),
        ("`❤️`", "***"),
        ("❤️ Preview", "**"),
    ]:
        multi = f"{wrap}[\n{label} \n]({URL}){wrap}"
        assert _classify_link_content(_flatten(multi)) == _classify_link_content(
            f"{wrap}[{label}]({URL}){wrap}"
        ), multi
    print("  ✓  flattened links classify like single-line links")


def test_trailing_space_still_reads_as_pure_emoji():
    """ "[\\n❤️ \\n](/x)" must reach the emoji-badge path, not mixed content."""
    variant, label, is_emoji, _, _ = _classify_link_content(
        _flatten(f"[\n❤️ \n]({URL})")
    )
    assert (variant, label, is_emoji) == ("primary", "❤️", True)
    print("  ✓  a trailing space still reads as a pure-emoji label")


def test_multiline_image_alt_flattens():
    assert _flatten("![\nplain alt text\n](u.png)") == "![plain alt text](u.png)"
    print("  ✓  a multi-line image alt flattens")


def test_single_line_content_is_untouched():
    """Only constructs that actually span lines may be rewritten."""
    for text in [
        "See [this](/url) now.",
        "a  b [x](/y)  c",
        "![alt  text](u.png)",
        "[![](i.svg)](/x)",
    ]:
        assert _flatten(text) == text, text
    print("  ✓  single-line content is untouched byte for byte")


def test_block_content_is_left_alone():
    """Block labels need a sub-document, not a flatten — leave them intact."""
    for text in [
        "![\n## Payday\ntext\n](u.png)",  # heading
        "[\n![](i.svg)\n](/x)",  # nested image
        "[\n- one\n- two\n](/x)",  # list
        "[\n> quoted\n](/x)",  # blockquote
        "[\n| a | b |\n](/x)",  # table
        "[\n---\n](/x)",  # rule
    ]:
        assert _flatten(text) == text, text
    print("  ✓  block-content labels are left alone")


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------


def _processed(text: str):
    from md2ui.pipeline.data_point_detector import DataPointDetector

    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    return g.ast


def test_multiline_link_becomes_one_link_node():
    """A lone link becomes one LINK leaf under the root — same as the
    single-line form does.

    Absorbed into the root itself, it would leave the document childless and
    non-empty: the shape the generator reads as an empty document.
    """
    ast = _processed(f"[\n\nPreview\n\n]({URL})")
    assert ast.type == "root" and len(ast.children) == 1, (ast.type, ast.children)
    leaf = ast.children[0]
    assert leaf.type == "link" and not leaf.children, (leaf.type, leaf.children)
    d = leaf.to_dict()
    assert d["link_variant"] == "primary" and d["link_label"] == "Preview"
    print("  ✓  a multi-line link becomes exactly one link node")


def test_multiline_matches_single_line_end_to_end():
    """The whole AST is identical to the hand-written single-line document."""
    for wrap in ["", "*", "**", "***"]:
        for label in ["Preview", "❤️", "`❤️ Preview`"]:
            multi = f"Before\n\n{wrap}[\n{label}\n]({URL}){wrap}\n\nAfter"
            single = f"Before\n\n{wrap}[{label}]({URL}){wrap}\n\nAfter"
            assert _processed(multi).to_dict() == _processed(single).to_dict(), multi
    print("  ✓  multi-line and single-line produce identical ASTs")


def test_multiline_link_does_not_disturb_neighbours():
    ast = _processed(f"Before\n\n[\nPreview\n]({URL})\n\nAfter")
    kinds = [c.type for c in ast.children]
    assert kinds == ["text", "link", "text"], kinds
    print("  ✓  a multi-line link does not disturb its neighbours")


TESTS = [
    test_scanner_counts_nested_brackets,
    test_scanner_returns_top_level_only,
    test_scanner_skips_escapes_and_bare_brackets,
    test_scanner_balances_parens_in_url,
    test_scanner_reads_a_links_destination,
    test_scanner_abandons_runaway_candidate,
    test_flatten_matches_single_line_form,
    test_flatten_preserves_variant_and_emoji,
    test_trailing_space_still_reads_as_pure_emoji,
    test_multiline_image_alt_flattens,
    test_single_line_content_is_untouched,
    test_block_content_is_left_alone,
    test_multiline_link_becomes_one_link_node,
    test_multiline_matches_single_line_end_to_end,
    test_multiline_link_does_not_disturb_neighbours,
]

if __name__ == "__main__":
    print("Multiline Link Tests")
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
