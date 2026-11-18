"""
`~~…~~` is the one muted state of every element (ADR-501):

    ~~⭐~~  ~~*⭐*~~  *~~⭐~~*        a muted badge, in that variant
    ~~`Tag`~~  ~~**`Tag`**~~         a muted chip
    ~~[`Go`](/x)~~                   a muted Text button
    ~~struck prose~~                 still struck text: the state is for elements

The grouper peels the `~~` beside the variant's wrapper and records it as
`element_muted`, the badge's and chip's `link_disabled`. The renderer paints
the element's `Disabled …` colours (`## Inline Code`, `## Emoji styles`, and
`## Links → ### Text`), or, where the theme states none, its own colours at
`MUTED_OPACITY`. A chip's, badge's or button's shadows and background image are
faded to `MUTED_OPACITY` always, as no `Disabled …` key names them. Only paint changes: a
muted element keeps its size and place.

Run with: uv run python tests/muted_element_tests.py
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "tests")

import skia
from markdown_datapoint_split_tests import _processed

from md2ui.pipeline import layout_render as LR
from md2ui.pipeline import render_pill_paint as PP
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.markdown_grouper import MarkdownGroupNode, NodeType
from md2ui.pipeline.render_colors import stamp_fixed_colors
from md2ui.pipeline.render_style import FontSet, _disabled_link_style
from md2ui.pipeline.theme import Theme, parse_theme
from md2ui.pipeline.theme_model import MUTED_OPACITY

MUTED = {"element_muted": True}


def _leaves(node: MarkdownGroupNode) -> list[tuple[str, str, str | None, bool]]:
    """[(type, content, variant, muted)] for every leaf, in document order."""
    out: list[tuple[str, str, str | None, bool]] = []
    if not node.children:
        variant = node.emoji_variant or node.code_variant
        out.append((str(node.type), node.content, variant, node.element_muted))
    for c in node.children:
        out.extend(_leaves(c))
    return out


def _theme_from(md: str) -> Theme:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "THEME.md"
        p.write_text(md)
        return parse_theme(p)


def _hex(h: str) -> int:
    h = h.lstrip("#")
    a = int(h[6:8], 16) if len(h) == 8 else 255
    return skia.ColorSetARGB(a, int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _faded(color: int) -> int:
    """*color* at the default mute's opacity."""
    alpha = round(((color >> 24) & 0xFF) * MUTED_OPACITY)
    return (alpha << 24) | (color & 0xFFFFFF)


# ---------------------------------------------------------------------------
# Grouper: `~~` is a state on the element, not a strike around it
# ---------------------------------------------------------------------------


def test_struck_badge_is_a_muted_badge():
    for src, variant in (
        ("~~⭐~~", None),
        ("~~*⭐*~~", "secondary"),
        ("*~~⭐~~*", "secondary"),
        ("~~***⭐***~~", "quaternary"),
    ):
        got = _leaves(_processed(src))
        assert got == [(NodeType.EMOJI, "⭐", variant, True)], (src, got)
    print("  ✓  ~~⭐~~ (wrapper inside or out) is the badge, muted")


def test_struck_chip_is_a_muted_chip():
    for src, variant in (
        ("~~`Tag`~~", None),
        ("~~**`Tag`**~~", "tertiary"),
        ("**~~`Tag`~~**", "tertiary"),
        ("~~_`Tag`_~~", "quinary"),
        ("~~`~/path`~~", None),
    ):
        text = src.split("`")[1]
        got = _leaves(_processed(src))
        assert got == [(NodeType.INLINE_CODE, text, variant, True)], (src, got)
    print("  ✓  ~~`Tag`~~ is the chip, muted, in its variant")


def test_an_enabled_element_is_not_muted():
    for src in ("⭐", "*⭐*", "`Tag`", "**`Tag`**"):
        assert all(not muted for *_, muted in _leaves(_processed(src))), src
    print("  ✓  no ~~, no muted state")


def test_prose_strike_stays_struck_text():
    for src in ("~~struck prose~~", "~~⭐ old item~~", "~⭐~"):
        got = _leaves(_processed(src))
        assert got == [(NodeType.TEXT, src, None, False)], (src, got)
    print("  ✓  a strike around prose, or a lone ~, keeps drawing as text")


def test_muted_element_in_a_run():
    got = _leaves(_processed("⭐ ~~`Sold out`~~ 🚀"))
    assert got == [
        (NodeType.EMOJI, "⭐", None, False),
        (NodeType.INLINE_CODE, "Sold out", None, True),
        (NodeType.EMOJI, "🚀", None, False),
    ], got
    print("  ✓  only the struck element of a run is muted")


def test_muted_survives_the_round_trip():
    for src in ("~~**⭐**~~", "~~*`Tag`*~~"):
        ast = _processed(src)
        d = ast.to_dict()
        assert d["children"][0].get("element_muted") is True, d
        assert _leaves(MarkdownGroupNode.from_dict(d)) == _leaves(ast), src
    print("  ✓  element_muted is on the AST and survives to_dict/from_dict")


# ---------------------------------------------------------------------------
# Theme: the Disabled keys, named after each section's own keys
# ---------------------------------------------------------------------------


_KEYED = """\
## Inline Code
Fill color: #5EE117
Disabled fill color: #EEEEF0
Disabled text color: #96969D
Disabled stroke color: #E2E2E7

### Secondary
Fill color: #E7F4EB

## Emoji styles
### Primary
Icon color: #00CF33
Background color: #D5FFCC
Disabled background color: #EEEEF0
Disabled icon color: #96969D
Disabled stroke color: #E2E2E7

### Secondary
Disabled icon color: #112233
"""


def test_disabled_keys_parse_and_cascade():
    t = _theme_from(_KEYED)
    code, chip2 = t.inline_code, t.inline_code.resolved("secondary")
    for style in (code, chip2):
        assert style.disabled_fill_color == _hex("#EEEEF0")
        assert style.disabled_text_color == _hex("#96969D")
        assert style.disabled_stroke_color == _hex("#E2E2E7")
    badge, badge2 = t.emojis.primary, t.emojis.resolved("secondary")
    assert badge.disabled_bg_color == _hex("#EEEEF0")
    assert badge.disabled_icon_color == _hex("#96969D")
    assert badge.disabled_stroke_color == _hex("#E2E2E7")
    assert badge2.disabled_bg_color == _hex("#EEEEF0")
    assert badge2.disabled_icon_color == _hex("#112233")
    print("  ✓  Disabled keys parse on chips and badges, variants inherit")


# ---------------------------------------------------------------------------
# Paint: the keys when stated, the default mute when not; geometry untouched
# ---------------------------------------------------------------------------


def test_muted_chip_paints_the_keys():
    t = _theme_from(_KEYED)
    code = t.inline_code.resolved("secondary", MUTED)
    assert code.fill_color == _hex("#EEEEF0")
    assert code.stroke_color == _hex("#E2E2E7")
    assert code.effective_text_style(t.text).color == _hex("#96969D")
    enabled = t.inline_code.resolved("secondary")
    assert enabled.fill_color == _hex("#E7F4EB")
    assert (code.padding, code.corner_radius) == (
        enabled.padding,
        enabled.corner_radius,
    )
    print("  ✓  a muted chip paints its Disabled keys, at the enabled geometry")


def test_muted_chip_default_mute():
    t = _theme_from(
        "## Inline Code\nFill color: #5EE117\nBackground gradient:\n"
        "- Colors:\n  - #F2EEF9\n  - #DDD4F1\n"
    )
    code = t.inline_code.resolved(None, MUTED)
    assert code.fill_color == _faded(_hex("#5EE117"))
    body = t.inline_code.effective_text_style(t.text).color
    assert code.effective_text_style(t.text).color == _faded(body)
    assert code.gradient is not None
    assert code.gradient.colors == [_faded(_hex("#F2EEF9")), _faded(_hex("#DDD4F1"))]
    print("  ✓  no Disabled keys: the chip's own colours at MUTED_OPACITY")


def test_muted_badge_paints_the_keys():
    t = _theme_from(_KEYED)
    badge = t.emojis.resolved(None, MUTED, t.text.color)
    assert badge.fill.bg_colors == [_hex("#EEEEF0")]
    assert badge.icon_colors == [_hex("#96969D")]
    enabled = t.emojis.resolved(None)
    assert badge.icon_size == enabled.icon_size
    assert badge.fill.padding == enabled.fill.padding
    assert badge.shape == enabled.shape
    print("  ✓  a muted badge paints its Disabled keys, at the enabled size")


def test_muted_badge_default_mute():
    t = _theme_from(
        "## Emoji styles\n### Primary\nIcon color: #00CF33\n"
        "Background color: #D5FFCC\nPadding: 9\n"
    )
    badge = t.emojis.resolved(None, MUTED, t.text.color)
    assert badge.fill.bg_colors == [_faded(_hex("#D5FFCC"))]
    assert badge.icon_colors == [_faded(_hex("#00CF33"))]
    # No icon colour of its own: the glyph's ink is the one faded.
    bare = _theme_from("## Emoji styles\n### Primary\nPadding: 9\n")
    glyph = bare.emojis.resolved(None, MUTED, bare.text.color)
    assert glyph.icon_colors == [_faded(bare.text.color)]
    # A badge with no background never gains one: muting adds no layer.
    assert glyph.fill.bg_colors == []
    print("  ✓  no Disabled keys: the badge's own colours at MUTED_OPACITY")


def test_muted_text_button():
    t = _theme_from(
        "## Links\nFill color: #26262B\nDisabled fill color: #EEEEF0\n"
        "### Text\nFill color: #00000000\n"
    )
    # Text resolves onto bare defaults, not Primary, so Primary's keys never
    # reach it: with none of its own it takes the default mute.
    text = t.links.resolved("text")
    muted = _disabled_link_style(text)
    assert text.text_style is not None and muted.text_style is not None
    assert muted.text_style.color == _faded(text.text_style.color)
    keyed = _theme_from("## Links\n### Text\nDisabled text color: #96969D\n")
    muted = _disabled_link_style(keyed.links.resolved("text"))
    assert muted.text_style is not None
    assert muted.text_style.color == _hex("#96969D")
    print("  ✓  ~~[`Go`](/x)~~ mutes: ### Text's Disabled keys, else the default")


def test_muted_elements_take_no_pin():
    t = _theme_from(
        "## Fixed colors\n### Emoji\n- ⭐ #D7A139\n"
        "### Badges\n#### Contains\n- ⬆: Text color: #00CF33\n"
    )
    for src in ("~~⭐~~", "~~`⬆ 4%`~~"):
        d = _processed(src).to_dict()
        stamp_fixed_colors(d, t)
        leaf = d["children"][0]
        assert leaf.get("element_muted") and "fixed_text" not in leaf, (src, leaf)
    for src in ("⭐", "`⬆ 4%`"):
        d = _processed(src).to_dict()
        stamp_fixed_colors(d, t)
        assert "fixed_text" in d["children"][0], src
    print("  ✓  a muted element paints its state, not its pin (as a disabled link)")


_LAYERED = """\
## Inline Code
Fill color: #5EE117
Background image: shared.png
Outer shadow:
- Offset y: 6
- Radius: 12
- Color: #1A1A40AA
Inner shadow:
- Radius: 4
- Color: #000000AA

## Emoji styles
### Primary
Background color: #D5FFCC
Background image: shared.png
Outer shadow:
- Offset y: 6
- Radius: 12
- Color: #1A1A40AA
Inner shadow:
- Radius: 4
- Color: #000000AA
"""


def _painted(theme: Theme, muted: bool) -> list[tuple[skia.Rect, dict]]:
    """What a chip, then a badge, hand the layered painter: (rect, layers)."""
    photo = skia.Surface(4, 4)
    photo.getCanvas().clear(skia.ColorSetARGB(255, 200, 40, 90))
    images = {("element", "shared.png"): photo.makeImageSnapshot()}
    calls: list[tuple[skia.Rect, dict]] = []
    state = MUTED if muted else {}
    face = skia.Typeface.MakeDefault()
    canvas = skia.Surface(400, 100).getCanvas()
    with patch.object(
        LR, "_paint_layered_fill", side_effect=lambda _c, r, **kw: calls.append((r, kw))
    ):
        LR.draw_code_box(
            canvas,
            LayoutBox(0, 0, 180, 60),
            "`Tag`",
            face,
            theme,
            face,
            None,
            dict(state),
            images,
        )
        fonts = FontSet(face, face, face, face, face, face, {})
        badge = {"type": "emoji", "content": "★", "emoji_kind": "alone", **state}
        LR.draw_emoji_box(
            canvas, LayoutBox(200, 0, 180, 60), badge, fonts, theme, images
        )
    assert len(calls) == 2, calls
    return calls


def _alpha(image: skia.Image) -> int:
    pixels = image.toarray(colorType=skia.kRGBA_8888_ColorType)
    return int(pixels[..., 3].max())


def test_muted_chip_and_badge_fade_shadows_and_image():
    # The fade is the state whatever Disabled colours the theme states.
    stated = _LAYERED.replace(
        "Fill color: #5EE117\n", "Fill color: #5EE117\nDisabled fill color: #EEEEF0\n"
    ).replace(
        "Background color: #D5FFCC\n",
        "Background color: #D5FFCC\nDisabled background color: #EEEEF0\n",
    )
    for source in (_LAYERED, stated):
        t = _theme_from(source)
        enabled, muted = _painted(t, False), _painted(t, True)
        for (on_rect, on), (off_rect, off) in zip(enabled, muted, strict=True):
            assert (on_rect.width(), on_rect.height()) == (
                off_rect.width(),
                off_rect.height(),
            )
            assert [s.color for s in on["shadows"]] == [
                _hex("#1A1A40AA"),
                _hex("#000000AA"),
            ]
            assert [s.color for s in off["shadows"]] == [
                _faded(s.color) for s in on["shadows"]
            ]
            assert [(s.inner, s.offset_y, s.radius) for s in off["shadows"]] == [
                (s.inner, s.offset_y, s.radius) for s in on["shadows"]
            ]
            assert _alpha(on["image"]) == 255
            assert _alpha(off["image"]) == round(255 * MUTED_OPACITY)
            assert off["image"].dimensions() == on["image"].dimensions()
    print("  ✓  a muted chip and badge fade their shadows and photo, same size")


def _painted_button(theme: Theme, muted: bool) -> dict:
    """What a button hands the layered painter."""
    photo = skia.Surface(4, 4)
    photo.getCanvas().clear(skia.ColorSetARGB(255, 200, 40, 90))
    images = {("element", "shared.png"): photo.makeImageSnapshot()}
    calls: list[dict] = []
    face = skia.Typeface.MakeDefault()
    fonts = FontSet(face, face, face, face, face, face, {})
    button = {
        "type": "link",
        "content": "[Book](agent:book)",
        "link_label": "Book",
        "link_variant": "primary",
        "link_disabled": muted,
    }
    with patch.object(
        PP, "_paint_layered_fill", side_effect=lambda _c, _r, **kw: calls.append(kw)
    ):
        LR.draw_link_box(
            skia.Surface(200, 100).getCanvas(),
            LayoutBox(0, 0, 180, 60),
            button,
            fonts,
            theme,
            images,
        )
    assert len(calls) == 1, calls
    return calls[0]


def test_muted_button_fades_shadows_and_image():
    # As a chip and a badge: the fade is the state whatever the theme states.
    plain = "## Links\nFill color: #3B5BDB\nBackground image: shared.png\n"
    plain += "Outer shadow:\n- Offset y: 6\n- Radius: 12\n- Color: #1A1A40AA\n"
    stated = plain + "Disabled fill color: #EEEEF0\n"
    for source in (plain, stated):
        t = _theme_from(source)
        on, off = _painted_button(t, False), _painted_button(t, True)
        assert [s.color for s in on["shadows"]] == [_hex("#1A1A40AA")]
        assert [s.color for s in off["shadows"]] == [_faded(_hex("#1A1A40AA"))]
        assert [(s.offset_y, s.radius) for s in off["shadows"]] == [(6, 12)]
        assert _alpha(on["image"]) == 255
        assert _alpha(off["image"]) == round(255 * MUTED_OPACITY)
    print("  ✓  a muted button fades its shadows and photo, as a chip and badge do")


TESTS = [
    test_struck_badge_is_a_muted_badge,
    test_struck_chip_is_a_muted_chip,
    test_an_enabled_element_is_not_muted,
    test_prose_strike_stays_struck_text,
    test_muted_element_in_a_run,
    test_muted_survives_the_round_trip,
    test_disabled_keys_parse_and_cascade,
    test_muted_chip_paints_the_keys,
    test_muted_chip_default_mute,
    test_muted_badge_paints_the_keys,
    test_muted_badge_default_mute,
    test_muted_text_button,
    test_muted_elements_take_no_pin,
    test_muted_chip_and_badge_fade_shadows_and_image,
    test_muted_button_fades_shadows_and_image,
]

if __name__ == "__main__":
    print("Muted Element Tests")
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
