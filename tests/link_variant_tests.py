"""
Unit tests for the link button variants — one per markdown wrapping:

    [text](url)       Primary
    *[text](url)*     Secondary
    **[text](url)**   Tertiary
    ***[text](url)*** Quaternary
    _[text](url)_     Quinary      the small ladder, as chips have it
    __[text](url)__   Senary
    ___[text](url)___ Septenary

The wrapper is read by LENGTH — each extra marker is one more step down the
hierarchy — the same rule emoji badges and chips use. The tables live once, in
grouper_types._ELEMENT_VARIANT_BY_LEN and _CHIP_UNDERSCORE_VARIANT_BY_LEN.
    [`text`](url)     Text      the pure-text button. An emphasis
                                wrapper around it styles the LABEL instead of
                                picking a variant, since the backtick already
                                claimed one.

Classification happens once in markdown_grouper._classify_link_content; the
renderer only looks the variant up via LinksTheme.resolved.
Run with: uv run python tests/link_variant_tests.py
"""

import tempfile
from pathlib import Path

import sys

sys.path.insert(0, "tests")

import skia
from markdown_datapoint_split_tests import _processed

from md2ui.pipeline.markdown_grouper import MarkdownGroupNode, NodeType
from md2ui.pipeline.render_style import _disabled_link_style
from md2ui.pipeline.theme_model import muted_color
from md2ui.pipeline.grouper_types import _classify_link_content
from md2ui.pipeline.theme import LinkStyle, TextStyle, Theme, parse_theme
from md2ui.utils.font_loader import make_font

URL = "https://x.dev/a"


def test_each_wrapping_gets_its_own_variant():
    cases = [
        (f"[Regular]({URL})", "primary", "Regular"),
        (f"*[Italic]({URL})*", "secondary", "Italic"),
        (f"**[Bold]({URL})**", "tertiary", "Bold"),
        (f"***[Bold Italic]({URL})***", "quaternary", "Bold Italic"),
        (f"[`Code`]({URL})", "text", "Code"),
    ]
    for content, variant, label in cases:
        got = _classify_link_content(content)
        assert got == (variant, label, False, False, None), f"{content} → {got}"
    print("  ✓  the five wrappings classify to their own variants")


def test_backtick_label_wins_over_emphasis():
    # The label wrap is checked after the emphasis wrap and overrides it.
    variant, label, _, _, emphasis = _classify_link_content(f"***[`Code`]({URL})***")
    assert (variant, label, emphasis) == ("text", "Code", "bold_italic")
    print("  ✓  a backtick label stays Text and keeps the emphasis as a face")


def test_pure_emoji_keeps_its_variant():
    # No separate "emoji" style: is_emoji rides on top of the wrapping's variant.
    assert _classify_link_content(f"***[❤️]({URL})***") == (
        "quaternary",
        "❤️",
        True,
        False,
        None,
    )
    assert _classify_link_content(f"[`❤️`]({URL})") == ("text", "❤️", True, False, None)
    # Mixed content is not pure emoji.
    assert _classify_link_content(f"[`❤️ Save`]({URL})") == (
        "text",
        "❤️ Save",
        False,
        False,
        None,
    )
    print("  ✓  a pure-emoji label keeps its variant and sets is_emoji")


def test_resolved_merges_each_variant_onto_primary():
    t = Theme()
    t.links.quaternary = LinkStyle(corner_radius=3.0)
    t.links.text = LinkStyle(corner_radius=99.0)
    assert t.links.resolved("quaternary").corner_radius == 3.0
    assert t.links.resolved("text").corner_radius == 99.0
    # Unset fields still fall back to Primary's concrete values.
    assert t.links.resolved("quaternary").fill_color == t.links.primary.fill_color
    # Unknown names (and "inline", a text-run style) resolve to Primary.
    assert t.links.resolved("sextenary") is t.links.primary
    assert t.links.resolved("inline") is t.links.primary
    print("  ✓  quaternary merges onto Primary, text keeps its own; unknown → Primary")


def test_unthemed_buttons_are_grey_pills():
    # With the Links family unstyled a button reads as one, in the built-in
    # greys: Primary an ink pill, `*…*` an outlined one, `**…**` a light-grey
    # one; the other variants are Primary. A backtick Text link stays plain.
    from md2ui.pipeline.theme_model import GREY_INK, GREY_TRACK, GREY_WHITE

    t = Theme()
    primary = t.links.resolved("primary")
    assert primary.text_style is not None
    assert (primary.fill_color, primary.text_style.color) == (GREY_INK, GREY_WHITE)
    secondary = t.links.resolved("secondary")
    assert (secondary.fill_color, secondary.stroke_color) == (GREY_WHITE, GREY_INK)
    assert t.links.resolved("tertiary").fill_color == GREY_TRACK
    for variant in ("quaternary", "quinary", "senary", "septenary"):
        assert t.links.resolved(variant).fill_color == GREY_INK, variant
    text = t.links.resolved("text")
    assert skia.Color4f(text.fill_color).fA == 0.0
    assert (text.stroke_width or 0.0) == 0.0
    assert text.text_style is not None and text.text_style.color == t.text.color
    print("  ✓  with no theme buttons are grey pills; a Text link stays plain")


def test_declared_fill_still_wins():
    t = _theme_from(
        "## Links\n### Primary\nFill color: #8778F5\n### Secondary\nCorner radius: 2\n"
    )
    purple = skia.ColorSetARGB(255, 0x87, 0x78, 0xF5)
    assert t.links.resolved("primary").fill_color == purple
    # A variant that declares no fill still inherits Primary's.
    secondary = t.links.resolved("secondary")
    assert secondary.fill_color == purple and secondary.corner_radius == 2
    print("  ✓  a declared Fill color wins and still cascades to variants")


def test_quinary_is_a_button_not_the_text_link():
    # "quinary" is the small button, and "pill" names nothing, so it resolves to Primary like any unknown name.
    t = Theme()
    t.links.text = LinkStyle(corner_radius=99.0)
    for variant in ("quinary", "senary", "septenary"):
        assert t.links.resolved(variant).corner_radius != 99.0, variant
    assert t.links.resolved("pill") is t.links.primary
    print("  ✓  'quinary' is no longer the Text link; 'pill' names nothing")


def _theme_from(md: str) -> Theme:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "THEME.md"
        p.write_text(md)
        return parse_theme(p)


def test_theme_md_blocks_parse():
    t = _theme_from(
        "## Links\n"
        "### Quaternary\n"
        "Corner radius: 4\n"
        "Fill color: #112233\n"
        "### Quinary\n"
        "Corner radius: 20\n"
        "\n"
        "## Text Styles\n"
        "Links Quaternary\n"
        "- Font size: 15\n"
    )
    assert t.links.quaternary.corner_radius == 4
    assert t.links.quaternary.fill_color == skia.ColorSetARGB(255, 0x11, 0x22, 0x33)
    # "### Quinary" is the small button, not the Text link.
    assert t.links.quinary.corner_radius == 20
    assert t.links.text.corner_radius is None
    assert t.links.quaternary.text_style is not None
    assert t.links.quaternary.text_style.font_size == 15
    print("  ✓  '### Quaternary' / '### Quinary' / 'Links Quaternary' parse")


def test_small_ladder_blocks_and_text_styles_parse():
    t = _theme_from(
        "## Links\n"
        "### Quinary\nCorner radius: 5\n"
        "### Senary\nCorner radius: 6\n"
        "### Septenary\nCorner radius: 7\n"
        "\n## Text Styles\n"
        "Links Quinary\n- Font size: 11\n"
        "Links Senary\n- Font size: 12\n"
        "Links Septenary\n- Font size: 13\n"
    )
    for variant, n in (("quinary", 5), ("senary", 6), ("septenary", 7)):
        style = t.links.resolved(variant)
        assert style.corner_radius == n, variant
        assert style.text_style is not None
        assert style.text_style.font_size == n + 6, variant
    assert t.links.text.corner_radius is None and t.links.text.text_style is None
    print("  ✓  ### Quinary/Senary/Septenary and 'Links Quinary…' are the buttons")


def test_underscore_wrappers_are_the_small_ladder():
    # Buttons read `_` as their own family, as chips do: the small
    # main action, the small second one, the extra small one.
    for wrap, variant in (("_", "quinary"), ("__", "senary"), ("___", "septenary")):
        for label, is_emoji in (("Go", False), ("⭐", True)):
            got = _classify_link_content(f"{wrap}[{label}]({URL}){wrap}")
            assert got == (variant, label, is_emoji, False, None), (wrap, got)
    print("  ✓  _ / __ / ___ pick Quinary / Senary / Septenary")


def _link_variants(node: MarkdownGroupNode) -> list[tuple[str | None, str | None]]:
    """[(label, link_variant)] of every LINK leaf, as the AST records it."""
    d = node.to_dict()
    out: list[tuple[str | None, str | None]] = []

    def walk(n: dict) -> None:
        if n.get("type") == str(NodeType.LINK):
            out.append((n.get("link_label"), n.get("link_variant")))
        for c in n.get("children", []):
            walk(c)

    walk(d)
    return out


def test_grouper_records_the_small_ladder():
    for wrap, variant in (
        ("*", "secondary"),
        ("_", "quinary"),
        ("__", "senary"),
        ("___", "septenary"),
    ):
        for label in ("Go", "⭐"):
            src = f"{wrap}[{label}](/x){wrap}"
            assert _link_variants(_processed(src)) == [(label, variant)], src
    print("  ✓  the AST records _[x]_ / __[x]__ / ___[x]___ as the small ladder")


def test_emoji_badge_underscore_stays_a_synonym():
    # An emoji's sizes are the asterisk ladder: `_⭐_` is still Secondary.
    def variants(src: str) -> list[str | None]:
        out: list[str | None] = []

        def walk(n: MarkdownGroupNode) -> None:
            if n.type == NodeType.EMOJI:
                out.append(n.emoji_variant)
            for c in n.children:
                walk(c)

        walk(_processed(src))
        return out

    assert variants("_⭐_") == ["secondary"]
    assert variants("__⭐__") == ["tertiary"]
    print("  ✓  _⭐_ is still a Secondary badge")


def test_strike_marks_disabled_and_keeps_the_variant():
    # `~~` is a STATE riding on top of the variant, like is_emoji — not a
    # sixth variant, and never a strikethrough rule.
    cases = [
        (f"~~[x]({URL})~~", "primary"),
        (f"~~*[x]({URL})*~~", "secondary"),
        (f"~~**[x]({URL})**~~", "tertiary"),
        (f"~~***[x]({URL})***~~", "quaternary"),
        (f"~~_[x]({URL})_~~", "quinary"),
        (f"~~__[x]({URL})__~~", "senary"),
        (f"~~___[x]({URL})___~~", "septenary"),
        (f"~~[`x`]({URL})~~", "text"),
    ]
    for content, variant in cases:
        assert _classify_link_content(content)[:4] == (
            variant,
            "x",
            False,
            True,
        ), content
    # …and an unstruck link is never disabled.
    assert _classify_link_content(f"**[x]({URL})**")[3] is False
    print("  ✓  ~~ sets disabled and leaves the variant underneath intact")


def test_disabled_emoji_link_keeps_both_flags():
    assert _classify_link_content(f"~~***[❤️]({URL})***~~") == (
        "quaternary",
        "❤️",
        True,
        True,
        None,
    )
    print("  ✓  is_emoji and disabled ride together on one variant")


def test_disabled_colors_cascade_from_primary():
    t = _theme_from(
        "## Links\n"
        "### Primary\n"
        "Fill color: #8778F5\n"
        "Disabled fill color: #D9D7E4\n"
        "Disabled text color: #9A97AD\n"
        "### Secondary\n"
        "Disabled fill color: #112233\n"
    )
    grey = skia.ColorSetARGB(255, 0xD9, 0xD7, 0xE4)
    muted = skia.ColorSetARGB(255, 0x9A, 0x97, 0xAD)
    # Tertiary states nothing -> inherits both from Primary.
    tertiary = t.links.resolved("tertiary")
    assert tertiary.disabled_fill_color == grey
    assert tertiary.disabled_text_color == muted
    # Secondary overrides only the fill; the text color still cascades.
    secondary = t.links.resolved("secondary")
    assert secondary.disabled_fill_color == skia.ColorSetARGB(255, 0x11, 0x22, 0x33)
    assert secondary.disabled_text_color == muted
    print("  ✓  Disabled colors cascade from Primary, per-variant overrides win")


def test_unset_disabled_colors_take_the_default_mute():
    # A theme that configures no disabled colors still shows the state: the
    # link's own colors at MUTED_OPACITY (ADR-501).
    t = _theme_from("## Links\n### Primary\nFill color: #8778F5\n")
    style = t.links.resolved("primary")
    assert style.disabled_fill_color is None
    disabled = _disabled_link_style(style)
    assert disabled.fill_color == muted_color(style.fill_color, None, False)
    assert disabled.fill_color != style.fill_color
    assert disabled.stroke_color == muted_color(style.stroke_color, None, False)
    assert style.text_style is not None and disabled.text_style is not None
    want = muted_color(style.text_style.color, None, False)
    assert disabled.text_style.color == want
    print("  ✓  no disabled colors configured = the default mute")


def test_disabled_style_swaps_paint_but_not_geometry():
    t = _theme_from(
        "## Links\n### Primary\n"
        "Corner radius: 8\nPadding: 16\nFill color: #8778F5\n"
        "Disabled fill color: #D9D7E4\nDisabled text color: #9A97AD\n"
    )
    style = t.links.resolved("primary")
    disabled = _disabled_link_style(style)
    assert disabled.fill_color == skia.ColorSetARGB(255, 0xD9, 0xD7, 0xE4)
    assert disabled.text_style is not None
    assert disabled.text_style.color == skia.ColorSetARGB(255, 0x9A, 0x97, 0xAD)
    # Geometry is untouched, so a disabled button keeps its box and every
    # measurement path stays correct without knowing the state exists.
    assert disabled.corner_radius == style.corner_radius
    assert disabled.padding == style.padding
    assert disabled.emoji_shape == style.emoji_shape
    assert style.text_style is not None
    assert disabled.text_style.font_size == style.text_style.font_size
    print("  ✓  disabled swaps paint only — geometry and size are untouched")


def test_backtick_label_emphasis_mapping():
    # The wrapper the backtick label displaced is kept as a FACE, so a footer
    # gets plain/italic/bold/bold-italic pure-text links from plain markdown.
    for wrap, emphasis in (
        ("", None),
        ("*", "italic"),
        ("_", "italic"),
        ("**", "bold"),
        ("__", "bold"),
        ("***", "bold_italic"),
        ("___", "bold_italic"),
    ):
        content = f"{wrap}[`Code link`]({URL}){wrap}"
        variant, label, _, _, got = _classify_link_content(content)
        assert (variant, label) == ("text", "Code link"), content
        assert got == emphasis, f"{content} → {got}"
    print("  ✓  the displaced wrapper becomes italic / bold / bold-italic")


def test_emphasis_only_on_the_text_variant():
    # Everywhere else the wrapper already IS the variant, whose weight comes
    # from ## Text Styles — forcing a face there would override the theme.
    for content in (
        f"**[Bold]({URL})**",
        f"*[Italic]({URL})*",
        f"***[BI]({URL})***",
        f"[Plain]({URL})",
    ):
        assert _classify_link_content(content)[4] is None, content
    print("  ✓  only the Text variant carries an emphasis face")


# A Text link (`[`x`](/y)`) is its own construct, not a button variant: its shape
# and text style never fall back to Primary.
_PRIMARY_ONLY = (
    "## Links\n### Primary\nFill color: #111111\nCorner radius: 20\nPadding: 10\n"
    "Stroke width: 2\nStroke color: #222222\nDisabled fill color: #333333\n"
    "Outer shadow:\n- Offset y: 2\n- Color: #00000040\n- Radius: 6\n"
    "\n## Text Styles\nLinks\n- Font color: #FFFFFF\n- Font size: 21\n"
)


def test_text_link_without_blocks_is_plain_text():
    t = _theme_from(_PRIMARY_ONLY)
    primary, text = t.links.resolved("primary"), t.links.resolved("text")
    assert skia.Color4f(text.fill_color).fA == 0.0, "no fill"
    assert (text.stroke_width or 0.0) == 0.0 and not text.shadows, "no stroke/shadow"
    assert text.corner_radius != primary.corner_radius
    assert text.text_style is not None and text.text_style is not primary.text_style
    assert text.text_style == TextStyle(font_name=""), "the built-in default style"
    print("  ✓  a Text link with no Text blocks takes none of Primary's values")


def test_text_link_font_color_only_keeps_builtin_defaults():
    t = _theme_from(_PRIMARY_ONLY + "\nLinks Text\n- Font color: #FF0000\n")
    ts = t.links.resolved("text").text_style
    assert ts is not None
    assert ts.color == skia.ColorSetARGB(255, 0xFF, 0, 0)
    assert ts.font_size == TextStyle().font_size, "not Primary's 21"
    assert ts.font_name == "", "the body family, not Primary's"
    print("  ✓  'Links Text' with only a colour keeps the built-in size and face")


def test_button_variants_still_inherit_primary():
    t = _theme_from(_PRIMARY_ONLY + "\n## Links\n### Secondary\nCorner radius: 2\n")
    secondary = t.links.resolved("secondary")
    assert secondary.fill_color == skia.ColorSetARGB(255, 0x11, 0x11, 0x11)
    assert secondary.corner_radius == 2
    ts = secondary.text_style
    assert ts is not None and ts.font_size == 21, "Links text style inherited"
    print("  ✓  Secondary still inherits Primary's fill and text style")


def test_quinary_block_is_the_small_button():
    t = _theme_from(
        _PRIMARY_ONLY.replace(
            "## Text Styles", "### Quinary\nPadding: 4\n\n## Text Styles"
        )
    )
    small = t.links.resolved("quinary")
    assert small.padding is not None and small.padding.left == 4
    assert small.fill_color == skia.ColorSetRGB(0x11, 0x11, 0x11), "Primary's fill"
    text = t.links.resolved("text")
    assert text.padding is None or text.padding.left != 4, "Text untouched"
    print("  ✓  a '### Quinary' block lands on the small button, not the Text link")


def test_small_ladder_without_blocks_draws_as_primary():
    # A theme with no Quinary…Septenary blocks draws them exactly as Primary —
    # through the renderer's own lookup, disabled state included.
    from md2ui.pipeline.render_style import _resolve_link

    t = _theme_from(_PRIMARY_ONLY)
    _, _, _, primary = _resolve_link({"link_variant": "primary", "link_label": "x"}, t)
    for variant in ("quinary", "senary", "septenary"):
        for disabled in (False, True):
            nd = {"link_variant": variant, "link_label": "x", "link_disabled": disabled}
            _, _, _, style = _resolve_link(nd, t)
            base = _disabled_link_style(primary) if disabled else primary
            assert style == base, (variant, disabled)
    print("  ✓  Quinary/Senary/Septenary with no blocks draw as Primary, ~~ too")


def test_disabled_text_link_resolves_without_primary():
    from md2ui.pipeline.render_style import _resolve_link

    t = _theme_from(_PRIMARY_ONLY)
    nd = {"link_variant": "text", "link_label": "x", "link_disabled": True}
    _v, label, _e, style = _resolve_link(nd, t)
    assert label == "x"
    assert skia.Color4f(style.fill_color).fA == 0.0, "not Primary's disabled fill"
    assert (style.stroke_width or 0.0) == 0.0
    print("  ✓  a disabled Text link resolves without Primary's disabled paint")


def test_a_header_naming_no_button_style_targets_primary():
    # `resolved` and `__class__` are attributes of the links model but not
    # styles; like an unknown name (`foo`) they configure Primary, never crash.
    for sub in ("resolved", "__class__", "foo"):
        t = _theme_from(f"## Links\n### {sub}\nFill color: #008800\n")
        assert t.links.primary.fill_color == skia.ColorSetRGB(0, 0x88, 0), sub
    print("  ✓  a ### name that is no button style configures Primary")


def test_an_icon_button_is_as_tall_as_a_text_button():
    """An emoji-only label is a circle as tall as a text label of its variant:
    the glyph takes the vertical padding on every side, so wider left/right
    padding (24 here, against 16 top and bottom) never makes it bigger than the
    text buttons beside it."""
    from md2ui.pipeline.render_metrics import _link_pill_size
    from md2ui.pipeline.theme_model import LinkStyle, PaddingBox

    font = make_font(skia.Typeface.MakeDefault(), 16)
    style = LinkStyle(
        padding=PaddingBox(top=16, bottom=16, left=24, right=24),
        emoji_shape="circle",
    )
    _w, text_h = _link_pill_size([("Play", font)], style, font, 16, None, False)
    icon_w, icon_h = _link_pill_size([("▶", font)], style, font, 16, None, True)
    assert icon_w == icon_h, (icon_w, icon_h)
    assert icon_h == text_h, f"icon {icon_h} vs text {text_h}"
    print("  ✓  an icon button is as tall as a text button of its variant")


TESTS = [
    test_a_header_naming_no_button_style_targets_primary,
    test_text_link_without_blocks_is_plain_text,
    test_text_link_font_color_only_keeps_builtin_defaults,
    test_button_variants_still_inherit_primary,
    test_quinary_block_is_the_small_button,
    test_small_ladder_without_blocks_draws_as_primary,
    test_small_ladder_blocks_and_text_styles_parse,
    test_grouper_records_the_small_ladder,
    test_emoji_badge_underscore_stays_a_synonym,
    test_disabled_text_link_resolves_without_primary,
    test_each_wrapping_gets_its_own_variant,
    test_underscore_wrappers_are_the_small_ladder,
    test_strike_marks_disabled_and_keeps_the_variant,
    test_disabled_emoji_link_keeps_both_flags,
    test_disabled_colors_cascade_from_primary,
    test_unset_disabled_colors_take_the_default_mute,
    test_disabled_style_swaps_paint_but_not_geometry,
    test_backtick_label_wins_over_emphasis,
    test_pure_emoji_keeps_its_variant,
    test_an_icon_button_is_as_tall_as_a_text_button,
    test_resolved_merges_each_variant_onto_primary,
    test_unthemed_buttons_are_grey_pills,
    test_declared_fill_still_wins,
    test_quinary_is_a_button_not_the_text_link,
    test_theme_md_blocks_parse,
    test_backtick_label_emphasis_mapping,
    test_emphasis_only_on_the_text_variant,
]

if __name__ == "__main__":
    print("Link Variant Tests")
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
