"""
Unit tests for inline links: a [label](url) the grouper never peeled into its
own LINK button stays inside its text run and renders as a span style, exactly
like bold/italic/strike — same font, same size, only the label drawn (never the
URL), recolored and optionally underlined from ## Links > ### Inline.
Run with: uv run python tests/layout_inline_link_tests.py
"""

import skia
from md2ui.pipeline.layout_render import _FLAG_LINK, _flag_runs
from md2ui.pipeline.render_measure import _explode_words, _line_width
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.render_text import (
    LINK_DESTINATION,
    inline_link_urls,
    parse_inline_spans,
)
from md2ui.pipeline.theme import InlineLinkStyle, Theme, parse_theme

SIZE = 16.0


def _fonts() -> FontSet:
    tf = skia.Typeface.MakeDefault()
    return FontSet(tf, tf, tf, tf, tf)


def _links(spans: list) -> list:
    """[(text, bold, italic)] for the link spans only."""
    return [(s[0], s[1], s[2]) for s in spans if s[5]]


def _width(text: str) -> float:
    return _line_width(_explode_words(text), _fonts(), SIZE)


def test_plain_link_span():
    spans = parse_inline_spans("See the [docs](https://x.dev/a) now")
    assert _links(spans) == [("docs", False, False)], spans
    # The URL never reaches a span, and the prose around it survives intact.
    assert [s[0] for s in spans] == ["See the ", "docs", " now"], spans
    print("  ✓  '[docs](url)' → one link span, URL dropped, prose intact")


def test_wrapped_variants_keep_their_style():
    bold = parse_inline_spans("**[Secondary](/link)**")
    italic = parse_inline_spans("*[Tertiary](/link)*")
    pill = parse_inline_spans("[`Pill`](/link)")
    assert _links(bold) == [("Secondary", True, False)], bold
    assert _links(italic) == [("Tertiary", False, True)], italic
    assert _links(pill) == [("Pill", False, False)], pill
    # No stray wrapper markers left behind as plain spans.
    for spans in (bold, italic, pill):
        assert len(spans) == 1, spans
    print("  ✓  **[a]()** / *[a]()* / [`a`]() → link + bold / italic / plain")


def test_images_are_not_links():
    spans = parse_inline_spans("An ![alt](pic.png) image")
    assert _links(spans) == [], spans
    print("  ✓  '![alt](url)' produces no link span")


def test_empty_url_link():
    # The detector's LINK pattern needs a non-empty URL, so these never peel, and
    # their raw markup must not leak onto the canvas.
    spans = parse_inline_spans("Make my website [↗️]()")
    assert _links(spans) == [("↗️", False, False)], spans
    print("  ✓  empty-URL '[↗️]()' still parses as a link")


def test_styles_still_parse():
    spans = parse_inline_spans("**b** *i* ~~s~~ `c`")
    flags = [(s[0], s[1], s[2], s[3], s[4]) for s in spans if s[0].strip()]
    assert flags == [
        ("b", True, False, False, False),
        ("i", False, True, False, False),
        ("s", False, False, False, True),
        ("c", False, False, True, False),
    ], spans
    assert not any(s[5] for s in spans), "no link flags in plain styled text"
    print("  ✓  bold/italic/strike/code spans unchanged by the link pass")


def test_url_excluded_from_width():
    # Same font, same size ⇒ an inline link measures exactly like its label.
    assert _width("See the [docs](/a/very/long/url/that/is/huge) now") == _width(
        "See the docs now"
    )
    print("  ✓  measured width equals the label-only text (URL not measured)")


def test_words_carry_the_flag():
    words = _explode_words("Read [the full guide](/g) today")
    flagged = [w[0] for w in words if w[5]]
    assert flagged == ["the", "full", "guide"], words
    assert [w[0] for w in words if not w[5]] == ["Read", "today"], words
    print("  ✓  every word of a multi-word label carries the link flag")


def test_theme_defaults_and_parsing():
    t = Theme()
    assert isinstance(t.links.inline, InlineLinkStyle)
    assert t.links.inline.text_color is None, "unset ⇒ inherit surrounding color"
    assert t.links.inline.underline is True
    # ### Inline must not be treated as a button variant.
    assert t.links.resolved("inline") is t.links.primary
    print("  ✓  InlineLinkStyle defaults; 'inline' never resolves as a button")


def test_theme_md_block_parses():
    import tempfile
    from pathlib import Path

    md = (
        "## Links\n"
        "### Primary\n"
        "Corner radius: 8\n"
        "Fill color: #112233\n"
        "### Inline\n"
        "Text color: #4C6EF5\n"
        "Underline: no\n"
    )
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "THEME.md"
        p.write_text(md)
        t = parse_theme(p)
    assert t.links.inline.text_color == skia.ColorSetARGB(255, 0x4C, 0x6E, 0xF5)
    assert t.links.inline.underline is False
    # The Inline block must not have leaked into Primary's button style.
    assert t.links.primary.fill_color == skia.ColorSetARGB(255, 0x11, 0x22, 0x33)
    assert t.links.primary.corner_radius == 8
    print("  ✓  '### Inline' parses Text color / Underline, leaves Primary alone")


def test_autolink_spans():
    # <https://…> is a link too: drawn as its URI, brackets dropped.
    spans = parse_inline_spans("See <https://a.dev/x?y=1#z> now")
    assert _links(spans) == [("https://a.dev/x?y=1#z", False, False)], spans
    assert [s[0] for s in spans] == ["See ", "https://a.dev/x?y=1#z", " now"]
    # Wrapped variants carry their emphasis, with no stray markers left over.
    for src, bold, italic in (
        ("*<https://a.dev>*", False, True),
        ("**<https://a.dev>**", True, False),
        ("***<https://a.dev>***", True, True),
    ):
        got = parse_inline_spans(src)
        assert got == [("https://a.dev", bold, italic, False, False, True)], got
    # An email autolink counts as well.
    assert _links(parse_inline_spans("mail <me@x.com> now")) == [
        ("me@x.com", False, False)
    ]
    print("  ✓  '<uri>' → link span with the URI, brackets dropped")


def test_angle_brackets_without_a_scheme_are_not_links():
    # The scheme's colon is the whole test — HTML-ish text must stay literal.
    for src in ("<not-a-link>", "<br>", '<div class="x">', "a < b and c > d"):
        assert _links(parse_inline_spans(src)) == [], src
    print("  ✓  '<not-a-link>' / '<br>' / '<div …>' are never links")


def test_bold_italic_wrapped_link():
    # ***[x](/y)*** is a link span carrying both emphases, not raw ***…*** markup.
    got = parse_inline_spans("***[Bold Italic link](/y)***")
    assert got == [("Bold Italic link", True, True, False, False, True)], got
    print("  ✓  '***[label](url)***' is a bold+italic link, not raw markup")


def test_autolink_width_excludes_brackets():
    assert _width("go <https://a.dev/x> now") == _width("go https://a.dev/x now")
    print("  ✓  an autolink measures as its bare URI")


def test_one_underline_run_per_link():
    """A link is one underline over all its words, the spaces inside it
    included. It breaks only where a different link starts — the link slot is a
    region id, like code and strike — and at a line break, where runs restart."""
    words = _explode_words("see [two words](/x) [b](/y) end")
    runs = _flag_runs(words, _FLAG_LINK, 0.0, _fonts(), SIZE)
    assert len(runs) == 2, runs
    (x0, x1, first), (y0, _y1, second) = runs
    assert [w[0] for w in words[first : first + 2]] == ["two", "words"], words
    assert words[second][0] == "b", words
    assert x1 - x0 == _width("two words"), "one run, spanning the inner space"
    assert x1 < y0, "the space between two links is not underlined"
    print("  ✓  one underline run per link; separate links stay separate")


# A destination may hold one level of balanced parentheses (CommonMark), so a
# Wikipedia URL keeps its tail; `render_text.LINK_DESTINATION` is the one pattern.
_WIKI = "https://en.wikipedia.org/wiki/POST_(HTTP)#Use_for_submitting_web_forms"


def test_parentheses_in_a_destination():
    for src, label in (
        (f"Accepts [form-encoded]({_WIKI}) request bodies.", "form-encoded"),
        (f"Accepts **[form-encoded]({_WIKI})** request bodies.", "form-encoded"),
        (f"Accepts [`form-encoded`]({_WIKI}) request bodies.", "form-encoded"),
    ):
        spans = parse_inline_spans(src)
        assert [s[0] for s in spans if s[5]] == [label], spans
        assert [s[0] for s in spans][-1] == " request bodies.", spans
        assert inline_link_urls(src) == [_WIKI], inline_link_urls(src)
    print("  ✓  plain, bold and code-label links keep a URL with (…) whole")


def test_two_links_one_with_parentheses():
    src = "[a](https://x.org/a_(b)) and [b](/plain)"
    assert [s[0] for s in parse_inline_spans(src) if s[5]] == ["a", "b"]
    assert inline_link_urls(src) == ["https://x.org/a_(b)", "/plain"]
    print("  ✓  two links on one line end where each one's own URL ends")


def test_empty_and_spaced_destinations():
    assert inline_link_urls("Go [↗️]() now ~~[x]()~~") == ["", None]
    # CommonMark: a bare space ends the destination, so only a title may follow
    # it; a destination that needs a space is written in angle brackets.
    src = '[go](<agent:say?text=hello world>) and [t](/x "title")'
    assert [s[0] for s in parse_inline_spans(src) if s[5]] == ["go", "t"]
    assert inline_link_urls(src) == ["<agent:say?text=hello world>", '/x "title"']
    assert inline_link_urls("[go](agent:say?text=hello world)") == []
    print("  ✓  an empty destination, <…> and a title are links; a bare space is not")


def test_image_with_parentheses_is_not_a_link():
    from md2ui.utils.image_params import image_url

    src = "![i](https://x.org/a_(b).png) [l](m)"
    assert [s[0] for s in parse_inline_spans(src) if s[5]] == ["l"]
    assert image_url("![i](https://x.org/a_(b).png)") == "https://x.org/a_(b).png"
    # An empty source is an image with no picture.
    assert image_url("![i]()") == "", "an empty source is an image"
    print("  ✓  an image keeps its (…) URL and is never an inline link")


def test_image_params_copies_the_destination_pattern():
    # utils may not import the pipeline, so image_params holds a copy.
    from md2ui.utils import image_params

    assert image_params._LINK_DESTINATION == LINK_DESTINATION
    print("  ✓  image_params's destination pattern is render_text's")


TESTS = [
    test_parentheses_in_a_destination,
    test_two_links_one_with_parentheses,
    test_empty_and_spaced_destinations,
    test_image_with_parentheses_is_not_a_link,
    test_image_params_copies_the_destination_pattern,
    test_plain_link_span,
    test_autolink_spans,
    test_angle_brackets_without_a_scheme_are_not_links,
    test_bold_italic_wrapped_link,
    test_autolink_width_excludes_brackets,
    test_wrapped_variants_keep_their_style,
    test_images_are_not_links,
    test_empty_url_link,
    test_styles_still_parse,
    test_url_excluded_from_width,
    test_words_carry_the_flag,
    test_theme_defaults_and_parsing,
    test_theme_md_block_parses,
    test_one_underline_run_per_link,
]

if __name__ == "__main__":
    print("Layout Inline-Link Tests")
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
