"""
Unit tests for the theme SCHEMA (``md2ui.pipeline.theme_model``).

The dataclasses a parsed THEME.md becomes, apart from ``theme.py`` so that what
a theme IS sits apart from how one is read.

Two things are worth pinning here and are pinned nowhere else:

**The defaults are the design.** A document with no THEME.md renders through
these values, so a changed default silently restyles every unthemed render —
and the render snapshot only covers the seven samples that HAVE themes.

**The merge rule is per-field for links and whole-object for text**, which is
not a detail: a variant's ``### `` block in THEME.md materialises a TextStyle
only when one of its bullets is parsed, so ``None`` means "never mentioned" and
Primary applies as-is. A LinkStyle, by contrast, is merged field by field, so a
variant that sets only a corner radius keeps Primary's padding and colours.
Collapsing those two into one rule is an easy and invisible mistake.

Run with: uv run python scripts/run_tests.py
"""

from md2ui.pipeline.theme_model import (
    GREY_INK,
    GREY_TRACK,
    GREY_WHITE,
    LinkStyle,
    PaddingBox,
    TextStyle,
    Theme,
    _default_primary_link_style,
    _resolve_link_style,
    _resolve_text_style,
)


def test_an_unthemed_document_has_a_complete_theme():
    """Theme() must be usable with no THEME.md at all — every block present."""
    t = Theme()
    for block in ("text", "root", "links", "emojis", "inline_code", "tables"):
        assert getattr(t, block) is not None, block


def test_the_default_body_text_is_concrete():
    """Not None: the renderer asks for these on every leaf of every document."""
    t = Theme()
    assert t.text.font_size == 13.0
    assert t.text.font_name == "Arial"


def test_the_default_content_width_cap_is_1280():
    """The cap every ordinary render uses."""
    assert Theme().root.max_width == 1280.0


def test_unthemed_buttons_are_grey_pills():
    """With the Links family unstyled a button still reads as one, in the
    built-in greys; a backtick Text link stays plain text."""
    links = Theme().links
    assert links.primary.fill_color == GREY_INK
    assert links.resolved("secondary").stroke_color == GREY_INK
    assert links.resolved("secondary").fill_color == GREY_WHITE
    assert links.resolved("tertiary").fill_color == GREY_TRACK
    assert links.resolved("text").fill_color == 0, "transparent"
    assert _default_primary_link_style().corner_radius == 999.0


def test_a_theme_that_styles_links_starts_unpainted():
    """A theme that touches links takes them over: Primary starts unpainted and
    a variant it leaves unset is Primary, exactly as before the grey defaults."""
    import tempfile
    from pathlib import Path

    from md2ui.pipeline.theme import parse_theme

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text("## Links\n### Primary\nCorner radius: 8\n", encoding="utf-8")
        links = parse_theme(path).links
    assert links.primary.fill_color == 0, "transparent"
    assert links.primary.padding == PaddingBox(
        top=10.0, left=10.0, right=10.0, bottom=10.0
    )
    assert links.resolved("secondary").fill_color == links.primary.fill_color


def test_a_text_style_merges_whole_object():
    """None means the variant's subsection was never seen, so Primary applies
    as-is — NOT field-by-field."""
    base = TextStyle(font_size=9.0)
    assert _resolve_text_style(None, base) is base
    override = TextStyle(font_size=1.0)
    assert _resolve_text_style(override, base) is override


def test_a_link_style_merges_field_by_field():
    """The opposite rule: a variant that sets only one field keeps Primary's
    values for every other one."""
    base = LinkStyle(
        corner_radius=7.0, padding=PaddingBox(top=1, left=2, right=3, bottom=4)
    )
    merged = _resolve_link_style(LinkStyle(corner_radius=3.0), base)
    assert merged.corner_radius == 3.0, "the override wins where it is set"
    assert merged.padding == base.padding, "and Primary fills the rest"


def test_merging_an_empty_override_yields_the_base_values():
    base = LinkStyle(corner_radius=7.0)
    assert _resolve_link_style(LinkStyle(), base).corner_radius == 7.0


TESTS = [
    test_an_unthemed_document_has_a_complete_theme,
    test_the_default_body_text_is_concrete,
    test_the_default_content_width_cap_is_1280,
    test_unthemed_buttons_are_grey_pills,
    test_a_theme_that_styles_links_starts_unpainted,
    test_a_text_style_merges_whole_object,
    test_a_link_style_merges_field_by_field,
    test_merging_an_empty_override_yields_the_base_values,
]

if __name__ == "__main__":
    print("Theme Model Tests")
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
