"""
Unit tests for in-text markers: a `code` span the grouper never split out stays
inside its text run and is painted from the surrounding ## Text Styles block
(Marker text color / Marker background color) while keeping that block's font
and size. A STANDALONE `code` element is untouched — it stays an ## Inline Code
pill. Not to be confused with layout_marker_tests.py (gutter markers).
Run with: uv run python tests/layout_inline_marker_tests.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "tests")

import skia
from markdown_datapoint_split_tests import _processed_with_criteria

from md2ui.pipeline.render_measure import _explode_words, _line_width
from md2ui.pipeline.render_style import FontSet, _span_font
from md2ui.pipeline.layout_render import (
    _marker_style,
)
from md2ui.pipeline.render_text import parse_inline_spans
from md2ui.pipeline.theme import TextStyle, Theme, parse_theme

SIZE = 16.0


def _fonts() -> FontSet:
    tf = skia.Typeface.MakeDefault()
    mono = skia.Typeface.MakeFromName("Courier", skia.FontStyle.Normal())
    return FontSet(tf, tf, tf, tf, mono)


def _width(text: str, size: float = SIZE) -> float:
    return _line_width(_explode_words(text), _fonts(), size)


def test_marker_stays_inline_in_the_ast():
    # The premise: prose keeps its code span inline (marker), while a span the
    # grouper split onto its own leaf is a pill. Both shapes must keep working.
    # Sitting at the END of a line is NOT a split — only a whole line, a
    # sequenced line or an explicitly separated span earns the leaf.
    for src in (
        "This is a `label`  inside of a text.",
        "This is the `Label`",
        "`Label` at the start of a text.",
    ):
        inline = _processed_with_criteria(src)
        # One leaf, and under the root that is one CHILD — the root is a
        # container and never a leaf (Phase 6.04).
        assert len(inline.children) == 1, f"expected one leaf: {src}"
        leaf = inline.children[0]
        assert not leaf.children, f"prose keeps its code span inline: {src}"
        assert "`" in leaf.content, src
    split = _processed_with_criteria("This is the - `Label`")
    types = [c.type for c in split.children[0].children]
    assert "inline_code" in types, f"expected a split-out leaf, got {types}"
    print("  ✓  in-text `code` stays inline; a separated `code` is its own leaf")


def test_marker_keeps_the_surrounding_font():
    # No mono face, no fixed 14px: a marker is the surrounding run's font.
    fonts = _fonts()
    plain = _span_font(fonts, SIZE, False, False)
    assert plain.getTypeface() is fonts.typeface
    assert plain.getSize() == SIZE
    # ...and at a heading size it grows with the heading.
    assert _span_font(fonts, 32.0, False, False).getSize() == 32.0
    print("  ✓  a marker span uses the surrounding face and size")


def test_marker_measures_like_plain_text():
    assert _width("a `label` b") == _width("a label b")
    assert _width("a `label` b", 32.0) == _width("a label b", 32.0)
    print("  ✓  a marker measures exactly like the same text unmarked")


def test_span_is_flagged_as_code():
    spans = parse_inline_spans("This is a `label` inside")
    code = [s[0] for s in spans if s[3]]
    assert code == ["label"], spans
    print("  ✓  the span parser still flags the marker run")


def test_no_theme_keys_means_no_paint():
    t = Theme()
    ms = _marker_style(t, "text", 0)
    assert ms.marker_text_color is None and ms.marker_bg_color is None
    print("  ✓  with no Marker keys in THEME.md a marker paints nothing")


def test_heading_falls_back_to_text():
    t = Theme()
    t.text = TextStyle(marker_text_color=1, marker_bg_color=2)
    t.headings = {2: TextStyle(), 3: TextStyle(marker_bg_color=7)}
    # H2 sets no marker of its own -> Text's.
    assert _marker_style(t, "segment", 2).marker_bg_color == 2
    # H3 sets one -> its own wins whole.
    assert _marker_style(t, "segment", 3).marker_bg_color == 7
    # Plain text -> Text's.
    assert _marker_style(t, "text", 0).marker_bg_color == 2
    print("  ✓  a heading level with no Marker keys falls back to Text's")


def test_theme_md_marker_bullets():
    md = (
        "## Text Styles\n"
        "Text\n"
        "- Font size: 16\n"
        "- Marker text color: #6B4E00\n"
        "- Marker background color: #FFF3CD\n"
        "\n"
        "Heading4\n"
        "- Font size: 22\n"
        "- Marker background color: #FFE8A3\n"
    )
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "THEME.md"
        p.write_text(md)
        t = parse_theme(p)
    assert t.text.marker_text_color == skia.ColorSetARGB(255, 0x6B, 0x4E, 0x00)
    assert t.text.marker_bg_color == skia.ColorSetARGB(255, 0xFF, 0xF3, 0xCD)
    assert t.headings[4].marker_bg_color == skia.ColorSetARGB(255, 0xFF, 0xE8, 0xA3)
    assert t.headings[4].marker_text_color is None
    assert t.headings[4].font_size == 22
    print("  ✓  Marker bullets parse per ## Text Styles block")


TESTS = [
    test_marker_stays_inline_in_the_ast,
    test_marker_keeps_the_surrounding_font,
    test_marker_measures_like_plain_text,
    test_span_is_flagged_as_code,
    test_no_theme_keys_means_no_paint,
    test_heading_falls_back_to_text,
    test_theme_md_marker_bullets,
]

if __name__ == "__main__":
    print("Layout Inline-Marker Tests")
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
