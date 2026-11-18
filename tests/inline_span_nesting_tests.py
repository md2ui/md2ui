"""
Unit tests for NESTED inline spans: an emphasis inside a strikethrough (and
every other combination) must apply both styles instead of drawing the inner
markers literally. `parse_inline_spans` re-parses each captured span and merges
the outer style in, so `~~**bold**~~` is one bold+struck span.

Also covers the inline link spellings that ride on the same alternation:
  - `_`/`__`/`___` wrapped links match their asterisk twins
  - a struck link is a plain link span (its disabled styling is undecided)
  - a backtick label drops its backticks, keeping the wrapper's emphasis
  - a struck run draws ONE rule across its words, spaces included

And its cost: a line of `_` openers that never close is parsed in linear time, with
the same spans and link destinations as before.

Run with: uv run python tests/inline_span_nesting_tests.py
"""

import time

import skia
from md2ui.pipeline.render_measure import _explode_words, _line_width
from md2ui.pipeline.render_metrics import _measure_word
from md2ui.pipeline.render_style import FontSet, _effective_text_fonts
from md2ui.pipeline.layout_render import (
    _flag_runs,
    _FLAG_CODE,
    _FLAG_STRIKE,
    draw_styled_text_box,
)
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_text import inline_link_urls, parse_inline_spans
from md2ui.pipeline.theme import TextStyle, Theme
from md2ui.utils.font_loader import make_font

SIZE = 16.0

# Distinguishable faces so a test can tell WHICH one a span resolved to.
_REG = skia.Typeface.MakeFromName("Helvetica", skia.FontStyle.Normal())
_BOLD = skia.Typeface.MakeFromName("Helvetica", skia.FontStyle.Bold())
_ITAL = skia.Typeface.MakeFromName("Helvetica", skia.FontStyle.Italic())
_BI = skia.Typeface.MakeFromName("Helvetica", skia.FontStyle.BoldItalic())
_H_REG = skia.Typeface.MakeFromName("Courier", skia.FontStyle.Normal())
_H_BOLD = skia.Typeface.MakeFromName("Courier", skia.FontStyle.Bold())
_H_ITAL = skia.Typeface.MakeFromName("Courier", skia.FontStyle.Italic())
_H_BI = skia.Typeface.MakeFromName("Courier", skia.FontStyle.BoldItalic())


def _fonts() -> FontSet:
    return FontSet(_REG, _BOLD, _ITAL, _BI, None)


def _flags(text: str) -> list[tuple[str, str]]:
    """[(span_text, 'BICSL' subset)] — a compact, readable style signature."""
    return [
        (t, "".join(k for k, v in zip("BICSL", (b, i, c, s, ln)) if v) or "-")
        for t, b, i, c, s, ln in parse_inline_spans(text)
    ]


# ---------------------------------------------------------------------------
# Strike wrapping emphasis
# ---------------------------------------------------------------------------


def test_strike_wrapping_emphasis_asterisks():
    assert _flags("~~**bold text**~~") == [("bold text", "BS")]
    assert _flags("~~*italic text*~~") == [("italic text", "IS")]
    assert _flags("~~***bold italic text***~~") == [("bold italic text", "BIS")]
    print("  ✓  ~~**x**~~ / ~~*x*~~ / ~~***x***~~ apply both styles")


def test_strike_wrapping_emphasis_underscores():
    # `_` is a CommonMark synonym for `*`, so the underscore spellings must
    # behave identically.
    assert _flags("~~__bold text__~~") == [("bold text", "BS")]
    assert _flags("~~_italic text_~~") == [("italic text", "IS")]
    assert _flags("~~___bold italic text___~~") == [("bold italic text", "BIS")]
    print("  ✓  the underscore spellings behave identically")


def test_no_literal_markers_survive():
    for src in (
        "~~**b**~~",
        "~~*i*~~",
        "~~***bi***~~",
        "~~__b__~~",
        "~~_i_~~",
        "~~___bi___~~",
        "**~~b~~**",
        "~~`c`~~",
    ):
        drawn = "".join(t for t, *_ in parse_inline_spans(src))
        assert "*" not in drawn and "~" not in drawn and "`" not in drawn, (
            f"{src!r} still draws markers: {drawn!r}"
        )
    print("  ✓  no `*`, `~` or backtick reaches the drawn text")


# ---------------------------------------------------------------------------
# The other directions
# ---------------------------------------------------------------------------


def test_emphasis_wrapping_strike():
    assert _flags("**~~inverted~~**") == [("inverted", "BS")]
    assert _flags("*~~inverted~~*") == [("inverted", "IS")]
    assert _flags("***~~inverted~~***") == [("inverted", "BIS")]
    print("  ✓  emphasis on the outside works too")


def test_strike_wrapping_a_marker():
    assert _flags("~~`code`~~") == [("code", "CS")]
    print("  ✓  a `code` marker inside a strike keeps both flags")


def test_partially_styled_run():
    # Only part of the struck text is emphasized: three spans, all struck.
    assert _flags("~~**a** and *b*~~") == [
        ("a", "BS"),
        (" and ", "S"),
        ("b", "IS"),
    ]
    print("  ✓  a partially emphasized struck run splits into styled spans")


def test_nesting_inside_prose():
    assert _flags("a ~~**b**~~ c") == [("a ", "-"), ("b", "BS"), (" c", "-")]
    print("  ✓  nesting works mid-sentence")


# ---------------------------------------------------------------------------
# Boundaries the recursion must NOT cross
# ---------------------------------------------------------------------------


def test_unnested_styles_are_unchanged():
    # Single-level spans are untouched by the recursion.
    assert _flags("**b** *i* ~~s~~ `c`") == [
        ("b", "B"),
        (" ", "-"),
        ("i", "I"),
        (" ", "-"),
        ("s", "S"),
        (" ", "-"),
        ("c", "C"),
    ]
    assert _flags("plain text") == [("plain text", "-")]
    print("  ✓  un-nested spans parse exactly as before")


def test_top_level_links_are_unchanged():
    assert _flags("[a](/b)") == [("a", "L")]
    assert _flags("**[Bold link](/x)**") == [("Bold link", "BL")]
    assert _flags("*[i](/x)*") == [("i", "IL")]
    print("  ✓  top-level and wrapper-variant links are untouched")


def test_underscore_wrapped_links_match_their_asterisk_twins():
    # `_` is a CommonMark synonym for `*`, so the two spellings must produce
    # identical spans inline, just as they pick the same button variant.
    for u, a in (
        ("See _[this](/url)_ now.", "See *[this](/url)* now."),
        ("See __[this](/url)__ now.", "See **[this](/url)** now."),
        ("See ___[this](/url)___ now.", "See ***[this](/url)*** now."),
    ):
        assert _flags(u) == _flags(a), u
    assert _flags("See __[this](/url)__ now.") == [
        ("See ", "-"),
        ("this", "BL"),
        (" now.", "-"),
    ]
    print("  ✓  underscore-wrapped inline links match the asterisk spellings")


def test_disabled_link_inline_is_a_plain_link_span():
    # `~~` on a link is a STATE, not a text decoration. Inline, its disabled
    # styling is not decided yet, so all four spellings collapse to an ordinary
    # inline link: label only, no strike, no bold/italic.
    for src in (
        "See ~~[this](/url)~~ now.",
        "See ~~*[this](/url)*~~ now.",
        "See ~~**[this](/url)**~~ now.",
        "See ~~___[this](/url)___~~ now.",
    ):
        assert _flags(src) == [
            ("See ", "-"),
            ("this", "L"),
            (" now.", "-"),
        ], src
    print("  ✓  a struck inline link draws as a plain link span, never struck")


def test_recursion_terminates_on_degenerate_input():
    for src in ("~~~~", "****", "~~**~~", "___", "*", "~~*~~"):
        parse_inline_spans(src)  # must not hang or recurse away
    print("  ✓  degenerate marker runs terminate")


# ---------------------------------------------------------------------------
# Heading font
# ---------------------------------------------------------------------------


def _heading_fontset() -> FontSet:
    return FontSet(
        _REG,
        _BOLD,
        _ITAL,
        _BI,
        None,
        heading_typefaces={1: (_H_REG, _H_ITAL, _H_BOLD, _H_BI)},
    )


def test_nested_emphasis_in_a_heading_keeps_the_heading_family():
    # `# ~~**x**~~` must come out in the HEADING's bold face, not the body's.
    theme = Theme()
    theme.headings = {1: TextStyle(font_size=42.0)}
    eff, size = _effective_text_fonts("heading1", 0, _heading_fontset(), theme)
    assert size == 42.0
    assert eff.bold is _H_BOLD, "heading bold face must be swapped in"
    assert eff.bold_italic is _H_BI
    # …and the span that face gets applied to really is bold+struck.
    assert _flags("~~**bold heading**~~") == [("bold heading", "BS")]
    print("  ✓  nested emphasis in a heading uses the heading's own faces")


# ---------------------------------------------------------------------------
# Contiguous strike rule
# ---------------------------------------------------------------------------


def test_strike_run_spans_the_spaces_between_words():
    words = _explode_words("~~struck across words~~")
    assert len(words) == 3 and all(w[_FLAG_STRIKE] for w in words)
    runs = _flag_runs(words, _FLAG_STRIKE, 0.0, _fonts(), SIZE)
    assert len(runs) == 1, f"expected ONE rule, got {len(runs)}: {runs}"
    x0, x1, first = runs[0]
    assert first == 0 and x0 == 0.0
    # The run must reach the end of the last word — i.e. cover the spaces.
    assert abs(x1 - _line_width(words, _fonts(), SIZE)) < 0.5, (x1, runs)
    print("  ✓  a multi-word struck run draws one unbroken rule")


def test_separate_struck_runs_stay_separate():
    words = _explode_words("~~one~~ plain ~~two~~")
    runs = _flag_runs(words, _FLAG_STRIKE, 0.0, _fonts(), SIZE)
    assert len(runs) == 2, runs
    assert runs[0][1] < runs[1][0], "the runs must not touch"
    print("  ✓  strike runs separated by plain text stay separate")


def test_run_x_walk_matches_the_drawing_walk():
    # _flag_runs mirrors draw_styled_text_box's pen: same per-word advance and
    # one space between words. If they drift, rules land off the glyphs.
    words = _explode_words("~~a bb ccc~~")
    fonts = _fonts()
    x = 0.0
    for i, w in enumerate(words):
        if i > 0:
            x += make_font(fonts.typeface, SIZE).measureText(" ")
        x += _measure_word(w[0], w[1], w[2], fonts, SIZE)
    ((x0, x1, _),) = _flag_runs(words, _FLAG_STRIKE, 0.0, fonts, SIZE)
    assert x0 == 0.0 and abs(x1 - x) < 0.01, (x0, x1, x)
    print("  ✓  the run x-walk matches the drawing walk")


def test_adjacent_markers_paint_separately():
    # tests-inline.md: three markers with only a space between them. A run keyed
    # on the code FLAG alone merges all six words into one background — the
    # spaces between the markers get painted and they read as a single marker.
    words = _explode_words(
        "Lorem ipsum `dolor sit amet,` `consectetur adipiscing` `elit`. Aenean"
    )
    fonts = _fonts()
    runs = _flag_runs(words, _FLAG_CODE, 0.0, fonts, SIZE)
    assert len(runs) == 3, f"expected THREE backgrounds, got {len(runs)}: {runs}"
    # Each run starts on its own marker's first word, and none touch.
    assert [r[2] for r in runs] == [2, 5, 7], runs
    for a, b in zip(runs, runs[1:]):
        assert a[1] < b[0], f"backgrounds must not merge: {runs}"
    print("  ✓  three space-separated markers paint three backgrounds")


def test_multi_word_marker_stays_one_background():
    # The other half of the rule, and what the run logic exists for: a marker's
    # OWN spaces must stay covered.
    words = _explode_words("a `dolor sit amet,` b")
    runs = _flag_runs(words, _FLAG_CODE, 0.0, _fonts(), SIZE)
    assert len(runs) == 1, f"expected ONE background, got {len(runs)}: {runs}"
    print("  ✓  a multi-word marker still draws one unbroken background")


def test_adjacent_struck_runs_paint_separately():
    # Same defect on the strike rule: `~~one~~ ~~two~~` is two strikes, and the
    # space between them is not struck.
    words = _explode_words("~~one~~ ~~two~~")
    runs = _flag_runs(words, _FLAG_STRIKE, 0.0, _fonts(), SIZE)
    assert len(runs) == 2, f"expected TWO rules, got {len(runs)}: {runs}"
    assert runs[0][1] < runs[1][0], runs
    print("  ✓  two adjacent struck runs draw two rules, not one")


def test_nesting_inherits_the_region():
    # A nested span must NOT mint its own region: the emphasis inside a strike is
    # part of the same rule, so this stays one unbroken line.
    words = _explode_words("~~**a** and *b*~~")
    assert all(w[_FLAG_STRIKE] == words[0][_FLAG_STRIKE] for w in words), words
    runs = _flag_runs(words, _FLAG_STRIKE, 0.0, _fonts(), SIZE)
    assert len(runs) == 1, f"expected ONE rule, got {len(runs)}: {runs}"
    print("  ✓  emphasis nested in a strike stays one region")


def test_backtick_label_links_drop_their_backticks_inline():
    # The bare `[`x`](/y)` alternative already captures a clean label; the
    # emphasis-wrapped ones capture `.+?` between the brackets and must drop
    # the backticks too, or they draw literally (and underlined).
    assert _flags("See [`Code link`](/link) now.") == [
        ("See ", "-"),
        ("Code link", "L"),
        (" now.", "-"),
    ]
    for wrap, flags in (
        ("*", "IL"),
        ("**", "BL"),
        ("***", "BIL"),
        ("_", "IL"),
        ("__", "BL"),
        ("___", "BIL"),
    ):
        src = f"See {wrap}[`Code link`](/link){wrap} now."
        assert _flags(src) == [
            ("See ", "-"),
            ("Code link", flags),
            (" now.", "-"),
        ], src
    print("  ✓  a backtick label draws clean inline, keeping its emphasis")


def test_interior_code_in_a_label_is_untouched():
    # Only a WHOLE surrounding pair is the Text variant's marker.
    assert _flags("See [a `b` c](/x) now.") == [
        ("See ", "-"),
        ("a `b` c", "L"),
        (" now.", "-"),
    ]
    print("  ✓  an interior `code` inside a link label survives")


def test_the_drawer_paints_a_struck_run_without_unpacking_the_word():
    """The drawer reads a word by INDEX, so a new tuple field cannot break it.

    The tests above exercise ``_flag_runs`` and stop there; this one runs the
    CONSUMER, ``draw_styled_text_box``, where unpacking the word tuple by name
    would raise ValueError on every prose ``~~struck~~`` region.
    """
    words = _explode_words("Normal ~~two struck words~~ and `code` after")
    assert len(words[0]) > 6, "the word tuple is wider than the six flag fields"
    surface = skia.Surface(400, 120)
    box = LayoutBox(x=0.0, y=0.0, width=380.0, height=100.0)
    draw_styled_text_box(
        surface.getCanvas(),
        box,
        "Normal ~~two struck words~~ and `code` after",
        _fonts(),
        SIZE,
        0xFF000000,
        Theme(),
    )
    print("  ✓  the drawer paints a struck run by index, not by unpacking")


def test_a_line_of_unclosed_underscores_parses_in_linear_time():
    """Every `_` after a line's last closer opens nothing, and each used to be tried
    to the end of the line: 32 KB of `_a ` took about 1.7 s. The time limit leaves
    room for a loaded machine. The spans and links around them are unchanged."""
    flood = "_a " * 32_000
    started = time.perf_counter()
    spans = parse_inline_spans(flood)
    took = time.perf_counter() - started
    assert took < 1.0, f"{took:.1f} s for a 96 KB line"
    assert "".join(s[0] for s in spans) == flood
    assert parse_inline_spans("_it_ then _a _b") == [
        ("it", False, True, 0, 0, False),
        (" then _a _b", False, False, False, False, False),
    ]
    tail = "_a " * 20 + "see [x](/a_b) " + "_c " * 20
    assert inline_link_urls(tail) == ["/a_b"], inline_link_urls(tail)
    drawn = [s[0] for s in parse_inline_spans(tail)]
    assert drawn == ["_a " * 20 + "see ", "x", " " + "_c " * 20], drawn
    assert parse_inline_spans("__[a](/b)__x")[0][:3] == ("a", True, False)
    print(f"  ✓  a 96 KB line of unclosed `_` parses in {took:.2f} s, spans unchanged")


def test_a_link_inside_a_styled_phrase_is_its_inline_link():
    """Prose stays prose: a link inside a bold, italic or struck phrase draws as
    the same sentence's inline link would, with the phrase's style on top, and
    stays clickable. Links are numbered in reading order, inside phrases or not.
    A code span keeps link syntax literal."""
    for wrap, flag in (("**", 1), ("*", 2), ("__", 1), ("~~", 4)):
        spans = parse_inline_spans(f"{wrap}see [the docs](/d) for more{wrap}")
        assert [s[0] for s in spans] == ["see ", "the docs", " for more"], spans
        assert spans[1][5] == 1 and all(s[flag] for s in spans), (wrap, spans)
    line = "**a [one](/1) b** and [two](/2) and *c [three](/3)*"
    spans = parse_inline_spans(line)
    assert [(s[0], s[5]) for s in spans if s[5]] == [
        ("one", 1),
        ("two", 2),
        ("three", 3),
    ]
    assert inline_link_urls(line) == ["/1", "/2", "/3"], inline_link_urls(line)
    assert parse_inline_spans("**`[x](/y)`**")[0][:4] == ("[x](/y)", True, False, 1)
    print("  ✓  a link inside a styled phrase is its inline link, styled and numbered")


TESTS = [
    test_a_link_inside_a_styled_phrase_is_its_inline_link,
    test_a_line_of_unclosed_underscores_parses_in_linear_time,
    test_strike_wrapping_emphasis_asterisks,
    test_strike_wrapping_emphasis_underscores,
    test_no_literal_markers_survive,
    test_emphasis_wrapping_strike,
    test_strike_wrapping_a_marker,
    test_partially_styled_run,
    test_nesting_inside_prose,
    test_unnested_styles_are_unchanged,
    test_top_level_links_are_unchanged,
    test_underscore_wrapped_links_match_their_asterisk_twins,
    test_disabled_link_inline_is_a_plain_link_span,
    test_backtick_label_links_drop_their_backticks_inline,
    test_interior_code_in_a_label_is_untouched,
    test_recursion_terminates_on_degenerate_input,
    test_nested_emphasis_in_a_heading_keeps_the_heading_family,
    test_strike_run_spans_the_spaces_between_words,
    test_separate_struck_runs_stay_separate,
    test_run_x_walk_matches_the_drawing_walk,
    test_adjacent_markers_paint_separately,
    test_multi_word_marker_stays_one_background,
    test_adjacent_struck_runs_paint_separately,
    test_nesting_inherits_the_region,
    test_the_drawer_paints_a_struck_run_without_unpacking_the_word,
]

if __name__ == "__main__":
    print("Inline Span Nesting Tests")
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
