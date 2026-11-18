"""
The hard line break: a trailing backslash wraps a text without splitting it.

md2ui makes every source line its own text, so the author's one way to break a
line INSIDE a text is CommonMark's explicit hard break, a backslash at the end of
the line:

* whatever the line is, a paragraph, a ``Key: value`` line, a list item or a
  heading, the two lines stay one text;
* it draws on a new line there at every width, and is as wide as its widest
  segment.

Two trailing spaces, CommonMark's other spelling, stay ignored: LLMs put them on
hundreds of stacked ``Key: value`` rows, which must stay separate lines.

Run with: uv run python tests/hard_break_tests.py
"""

import skia  # type: ignore[import-untyped]

from md2ui import session
from md2ui.pipeline.grouper_block_splits import flat_label
from md2ui.pipeline.grouper_escapes import HARD_BREAK
from md2ui.pipeline.grouper_types import MarkdownGroupNode
from md2ui.pipeline.markdown_grouper import MarkdownGrouper
from md2ui.pipeline.render_measure import _explode_words, _line_width
from md2ui.pipeline.render_metrics import _wrap_lines_uncached
from md2ui.pipeline.render_text import plain_link_label
from md2ui.pipeline.render_style import FontSet

_KIT = None


def _leaves(markdown: str) -> list[tuple[str, str]]:
    global _KIT
    if _KIT is None:
        _KIT = session.load_grouping_kit()
    grouper = MarkdownGrouper(markdown)
    grouper.process(*_KIT)
    out: list[tuple[str, str]] = []

    def walk(node: MarkdownGroupNode) -> None:
        if node.content and not node.children:
            out.append((str(node.type), node.content))
        for child in node.children:
            walk(child)

    assert grouper.ast is not None
    walk(grouper.ast)
    return out


def _fonts() -> FontSet:
    tf = skia.Typeface.MakeDefault()
    return FontSet(tf, tf, tf, tf, tf)


# ---------------------------------------------------------------------------
# Grouper: where the break joins, and where the backslash is drawn as written
# ---------------------------------------------------------------------------


def test_a_trailing_backslash_joins_two_lines_into_one_text():
    assert _leaves("Line one\\\nLine two") == [
        ("text", f"Line one{HARD_BREAK}Line two")
    ]
    print("  ✓  two lines, one text, the break inside it")


def test_a_key_value_line_keeps_its_break():
    leaves = _leaves("**Address:** 12 Main St\\\nSpringfield")
    assert leaves == [
        ("text", f"**Address:** 12 Main St{HARD_BREAK}Springfield"),
    ], leaves
    print("  ✓  a Key: value line wraps where the author broke it")


def test_a_list_item_continues_on_its_indented_line():
    leaves = _leaves("- Item one\\\n  continues\n- Item two")
    assert leaves == [
        ("list_item", f"Item one{HARD_BREAK}continues"),
        ("list_item", "Item two"),
    ], leaves
    print("  ✓  a list item keeps its broken line")


def test_breaks_chain():
    assert _leaves("A\\\nB\\\nC") == [("text", f"A{HARD_BREAK}B{HARD_BREAK}C")]
    print("  ✓  consecutive breaks chain into one text")


def test_the_backslash_is_drawn_where_nothing_can_join():
    """As in CommonMark: no line to join, or a line that starts its own block."""
    cases = {
        "Last line\\": [("text", "Last line\\")],
        "Before blank\\\n\nAfter": [("text", "Before blank\\"), ("text", "After")],
        "Before list\\\n- item": [("text", "Before list\\"), ("list_item", "item")],
        "# Heading\\\n\nbody": [("heading1", "Heading\\"), ("text", "body")],
        "# Heading\\\n- item": [("heading1", "Heading\\"), ("list_item", "item")],
        "Text\\\n---": [("text", "Text\\"), ("horizontal_rule", "---")],
    }
    for markdown, expected in cases.items():
        assert _leaves(markdown) == expected, (markdown, _leaves(markdown))
    print("  ✓  the backslash is kept where no join is possible")


def test_a_heading_continues_onto_its_next_lines():
    """A heading breaks as a text does: the lines are one
    heading of its level, and the last one, with nothing to join, keeps its
    backslash."""
    leaves = _leaves("# Heading line 1\\\nheading line 2\\\nheading line 3\\\n")
    assert leaves == [
        (
            "heading1",
            f"Heading line 1{HARD_BREAK}heading line 2{HARD_BREAK}heading line 3\\",
        ),
    ], leaves
    print("  ✓  a heading's broken lines are one heading")


def test_a_blank_line_ends_a_continued_heading():
    leaves = _leaves("# Heading line 1\\\nheading line 2\\\n\nheading line 3\\\n")
    assert leaves == [
        ("heading1", f"Heading line 1{HARD_BREAK}heading line 2\\"),
        ("text", "heading line 3\\"),
    ], leaves
    print("  ✓  before a blank line the heading's backslash is drawn")


def test_a_continued_heading_keeps_its_level():
    leaves = _leaves("## Second\\\nline 2\n\nBody")
    assert leaves == [
        ("heading2", f"Second{HARD_BREAK}line 2"),
        ("text", "Body"),
    ], leaves
    print("  ✓  a continued `##` is one level-2 heading")


def test_a_continued_heading_takes_its_id_from_the_last_line():
    """``{#id}`` closes a heading, so on a continued one it ends the last line."""
    grouper = MarkdownGrouper("# Title\\\nsecond line {#hero-1}\n\nBody")
    grouper.process(*session.load_grouping_kit())
    assert grouper.ast is not None
    section = grouper.ast.children[0]
    assert section.heading_id == "hero-1", section.heading_id
    assert section.fixed_style_key == "hero", section.fixed_style_key
    assert section.children[0].content == f"Title{HARD_BREAK}second line"
    print("  ✓  a continued heading's id resolves from its last line")


def test_an_escaped_backslash_is_not_a_break():
    assert _leaves("Ends in a backslash \\\\\nnext") == [
        ("text", "Ends in a backslash \\"),
        ("text", "next"),
    ]
    print("  ✓  `\\\\` at a line end draws one backslash and breaks nothing")


def test_a_break_and_an_escape_work_inside_an_image_card():
    """A card body is its own little document, stashed before the document's
    breaks are joined and its escapes resolved — so it gets both passes too."""
    texts = [
        c
        for _t, c in _leaves(
            "![\n# T\nOne\\\ntwo \\_star\\_\n](https://example.com/p.jpg)\n"
        )
    ]
    assert f"One{HARD_BREAK}two _star_" in texts, texts
    print("  ✓  inside an image card a break joins and an escape resolves")


def test_a_break_holds_inside_a_link_label_in_a_sentence():
    """Link text is inline content, so a hard break holds inside a label that a
    sentence carries, as CommonMark reads it; the label's lines without one still
    join with a space."""
    leaves = _leaves("Pick the [monthly plan\\\nat $9](agent:choose) today.")
    want = f"Pick the [monthly plan{HARD_BREAK}at $9](agent:choose) today."
    assert leaves == [("text", want)], leaves
    assert _leaves("x [a\nb](/x) y") == [("text", "x [a b](/x) y")]
    print("  ✓  a break holds inside a link label in a sentence; a soft one is a space")


def test_a_button_label_keeps_its_break_and_reads_as_words():
    """A button's label keeps the break the author wrote, never a drawn
    backslash, and the agent reads its words with a space."""
    leaves = _leaves("[Monthly\\\nplan](agent:a) [Yearly](agent:b)")
    assert ("link", f"[Monthly{HARD_BREAK}plan](agent:a)") in leaves, leaves
    label = plain_link_label({"link_label": f"Monthly{HARD_BREAK}plan"})
    assert label == "Monthly plan", repr(label)
    print("  ✓  a button label keeps its break and reads as words")


def test_a_label_breaks_only_where_a_text_would():
    """The same rule as a text's: an escaped backslash is no break, and neither is
    a backslash before a blank line, which is drawn."""
    assert flat_label("a\\\\\nb") == "a\\\\ b"
    assert flat_label("a\\\n\nb") == "a\\ b"
    assert flat_label("a\\\nb") == f"a{HARD_BREAK}b"
    print("  ✓  a label breaks only where a text would")


def test_two_trailing_spaces_still_join_nothing():
    assert _leaves("**Key:** one  \n**Key:** two  ") == [
        ("text", "**Key:** one"),
        ("text", "**Key:** two"),
    ]
    print("  ✓  two trailing spaces leave stacked rows separate")


def test_a_code_block_keeps_its_backslash():
    leaves = _leaves("```\ncode\\\nmore\n```")
    assert leaves == [("code_block", "code\\\nmore\n")], leaves
    print("  ✓  code is verbatim")


# ---------------------------------------------------------------------------
# Renderer: the forced line, the wrap interval, the natural width
# ---------------------------------------------------------------------------


def test_the_word_after_a_break_carries_it():
    words = _explode_words(f"12 Main St{HARD_BREAK}Springfield")
    assert [(w[0], w[6]) for w in words] == [
        ("12", False),
        ("Main", True),
        ("St", True),
        ("Springfield", HARD_BREAK),
    ]
    print("  ✓  the break rides on the next word's space_before field")


def test_the_wrap_breaks_there_at_every_width():
    fonts = _fonts()
    words = _explode_words(f"one two{HARD_BREAK}three")
    for width in (1.0, 60.0, 500.0, 10_000.0):
        lines, _, _ = _wrap_lines_uncached(words, width, fonts, 16.0)
        texts = [[w[0] for w in line] for line in lines]
        assert texts[-1][0] == "three", (width, texts)
        assert all("three" not in t[1:] for t in texts), (width, texts)
    print("  ✓  the break starts a new line at every width")


def test_a_break_moves_neither_bound_of_the_wrap_interval():
    """The resize cache replays a wrap across [lo, hi): a
    forced break holds at every width, so the bounds are those of the two
    segments wrapped alone."""
    fonts = _fonts()
    first = _explode_words("alpha beta gamma delta")
    second = _explode_words("epsilon zeta eta")
    joined = _explode_words(f"alpha beta gamma delta{HARD_BREAK}epsilon zeta eta")
    for width in (40.0, 120.0, 400.0):
        _, lo_a, hi_a = _wrap_lines_uncached(first, width, fonts, 16.0)
        _, lo_b, hi_b = _wrap_lines_uncached(second, width, fonts, 16.0)
        _, lo, hi = _wrap_lines_uncached(joined, width, fonts, 16.0)
        assert (lo, hi) == (max(lo_a, lo_b), min(hi_a, hi_b)), width
    print("  ✓  the wrap interval is the segments' own")


def test_the_natural_width_is_the_widest_segment():
    fonts = _fonts()
    wide = _explode_words("a much wider first segment")
    narrow = _explode_words("tiny")
    joined = _explode_words(f"a much wider first segment{HARD_BREAK}tiny")
    assert _line_width(joined, fonts, 16.0) == max(
        _line_width(wide, fonts, 16.0), _line_width(narrow, fonts, 16.0)
    )
    print("  ✓  a broken text is as wide as its widest segment")


TESTS = [
    test_a_break_and_an_escape_work_inside_an_image_card,
    test_a_trailing_backslash_joins_two_lines_into_one_text,
    test_a_key_value_line_keeps_its_break,
    test_a_list_item_continues_on_its_indented_line,
    test_breaks_chain,
    test_the_backslash_is_drawn_where_nothing_can_join,
    test_a_heading_continues_onto_its_next_lines,
    test_a_blank_line_ends_a_continued_heading,
    test_a_continued_heading_keeps_its_level,
    test_a_continued_heading_takes_its_id_from_the_last_line,
    test_an_escaped_backslash_is_not_a_break,
    test_a_break_holds_inside_a_link_label_in_a_sentence,
    test_a_button_label_keeps_its_break_and_reads_as_words,
    test_a_label_breaks_only_where_a_text_would,
    test_two_trailing_spaces_still_join_nothing,
    test_a_code_block_keeps_its_backslash,
    test_the_word_after_a_break_carries_it,
    test_the_wrap_breaks_there_at_every_width,
    test_a_break_moves_neither_bound_of_the_wrap_interval,
    test_the_natural_width_is_the_widest_segment,
]


if __name__ == "__main__":
    print("Hard Break Tests")
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
