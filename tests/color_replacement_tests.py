"""
Unit tests for COLOR REPLACEMENTS — swapping a painted color when the thing
behind it would make it illegible.

Three components plus a channel, as authored in ``## Color Replacements``:

    On background color: #101010
    - Text color:   #0A0A0A,   Replacement: #FFFFFF
    - Fill color:   #101010,   Replacement: #FFFFFF
    - Stroke color: #00000022, Replacement: #FFFFFF33

The background is not something a style can know: with color rotation a `### `
card takes whichever fill its slot deals it, so the same heading style lands on
a light card and a black one. The renderer therefore carries a BACKGROUND STACK
down the placement walk (`LayoutBox.bg_stack`, innermost first) and every swap
is resolved against that at paint time.

Run with: uv run python tests/color_replacement_tests.py
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import skia

sys.path.insert(0, "tests")

from md2ui import session
from md2ui.pipeline import layout_render as LR
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.render_backgrounds import (
    SectionBox,
    _opaque_or_none,
    _push_bg,
    _root_bg_stack,
)
from md2ui.pipeline.render_colors import _replace_color
from md2ui.pipeline import render_chart
from md2ui.pipeline.render_chart import ChartPlan, _chart_bar_rect, _chart_series_color
from md2ui.pipeline.layout_render import (
    _date_chip_text_bg_stack,
    _paint_date_chip_background,
    _replaced_gradient,
)
from md2ui.pipeline.render_bars import _draw_datapoint_bar, _draw_ring_arc, _paint_bar
from md2ui.pipeline.render_text_paint import _draw_text_with_emoji
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_backgrounds import _bg_selector
from md2ui.pipeline.theme import (
    BG_IMAGE,
    BarTheme,
    GradientTheme,
    SectionStyle,
    Theme,
    parse_theme,
)
from md2ui.utils.font_loader import make_font

W = 0xFFFFFFFF
BLACK = 0xFF101010
INK = 0xFF0A0A0A
BODY = 0xFF3F3F46
HAIR = 0x22000000
PURPLE = 0xFF5B4FC4
TRACK = 0xFFE9E7F2
ORANGE = 0xFFFF4A1C
DARK_TRACK = 0xFF3A3A3C


def _theme(text: str) -> Theme:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
        fh.write(text)
        path = Path(fh.name)
    try:
        return parse_theme(path)
    finally:
        path.unlink()


_DARK = """# t
## Color Replacements
On background color: #101010
- Text color: #0A0A0A, Replacement: #FFFFFF
- Text color: #3F3F46, Replacement: #D4D4D8
"""

# A full card: text, the button pill, the divider — and the
# pill's own new color as a background in its own right.
_CARD = """# t
## Color Replacements
On background color: #101010
- Text color:   #0A0A0A,   Replacement: #FFFFFF
- Fill color:   #101010,   Replacement: #FFFFFF
- Stroke color: #00000022, Replacement: #FFFFFF33

On background color: #FFFFFF
- Text color:   #FFFFFF,   Replacement: #101010
"""


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------


def test_a_group_parses_into_background_role_and_pairs():
    t = _theme(_DARK)
    assert list(t.color_replacements) == [BLACK]
    assert t.color_replacements[BLACK] == {"text": {INK: W, BODY: 0xFFD4D4D8}}


def test_the_three_roles_land_in_their_own_channels():
    t = _theme(_CARD)
    assert t.color_replacements[BLACK] == {
        "text": {INK: W},
        "fill": {BLACK: W},
        "stroke": {HAIR: 0x33FFFFFF},
    }


def test_a_bullet_without_a_channel_is_the_text_default():
    """`- Replacement: X` alone is TEXT's default for that background.

    Never fill's or stroke's: recoloring every pill on a background is not
    something anyone means by a bare default.
    """
    t = _theme(
        "# t\n## Color Replacements\n"
        "On background color: #101010\n"
        "- Replacement: #FFFFFF\n"
        "- Text color: #3F3F46, Replacement: #D4D4D8\n"
    )
    assert t.color_replacements[BLACK] == {"text": {None: W, BODY: 0xFFD4D4D8}}


def test_background_color_is_the_fill_channel():
    """`Background color:` names the fill channel, like `Fill color:`.

    It is how every other block in THEME.md spells this, so authors write it
    here too; an unmatched key would silently become that background's TEXT
    default.
    """

    def parsed(bullet: str) -> dict:
        return _theme(
            "# t\n## Color Replacements\nOn background color: #101010\n" + bullet + "\n"
        ).color_replacements[BLACK]

    group = parsed("- Background color: #101010, Replacement: #00FF00")
    assert group == {"fill": {BLACK: 0xFF00FF00}}, (
        f"must be a fill rule, not a text default: {group}"
    )
    # the three accepted spellings agree
    assert parsed("- Fill color: #101010, Replacement: #00FF00") == group
    assert parsed("- Background: #101010, Replacement: #00FF00") == group
    print("  ✓  `Background color:` is the fill channel, not a text default")


def test_the_old_section_name_still_parses():
    """Themes written before fills and strokes joined must not break."""
    t = _theme(
        "# t\n## Text Color Replacements\n"
        "On background color: #101010\n"
        "- Text color: #0A0A0A, Replacement: #FFFFFF\n"
    )
    assert t.color_replacements[BLACK] == {"text": {INK: W}}


def test_image_is_a_background_like_any_other():
    """A photo has no hex, so it gets the one reserved selector name."""
    t = _theme(
        "# t\n## Color Replacements\n"
        "On background color: image\n- Replacement: #FFFFFF\n"
    )
    assert t.color_replacements == {BG_IMAGE: {"text": {None: W}}}


def test_field_order_inside_a_bullet_does_not_matter():
    t = _theme(
        "# t\n## Color Replacements\n"
        "On background color: #101010\n"
        "- Replacement: #FFFFFF, Fill color: #101010\n"
    )
    assert t.color_replacements[BLACK] == {"fill": {BLACK: W}}


def test_groups_are_independent():
    t = _theme(
        "# t\n## Color Replacements\n"
        "On background color: #101010\n- Text color: #0A0A0A, Replacement: #FFFFFF\n"
        "\nOn background color: #EDEF6B\n- Text color: #FFFFFF, Replacement: #0A0A0A\n"
    )
    assert t.color_replacements[BLACK] == {"text": {INK: W}}
    assert t.color_replacements[0xFFEDEF6B] == {"text": {W: INK}}


# ---------------------------------------------------------------------------
# The lookup
# ---------------------------------------------------------------------------


def test_an_empty_table_is_a_no_op():
    """No rules, no behavior change, no cost."""
    t = Theme()
    assert _replace_color(INK, (BLACK, W), t) == INK
    assert _replace_color(BLACK, (BLACK,), t, "fill") == BLACK


def test_each_role_reads_its_own_channel():
    t = _theme(_CARD)
    assert _replace_color(INK, (BLACK,), t, "text") == W
    assert _replace_color(BLACK, (BLACK,), t, "fill") == W
    assert _replace_color(HAIR, (BLACK,), t, "stroke") == 0x33FFFFFF
    # The same hex under a different channel is not the same rule: #101010 is
    # a fill rule here, so asking for it as TEXT must leave it alone.
    assert _replace_color(BLACK, (BLACK,), t, "text") == BLACK


def test_nearest_surface_owns_every_channel():
    """A visible card is the context even when it has no rule for one role."""
    t = _theme(
        "# t\n## Color Replacements\n"
        "On background color: #2E3439\n- Text color: #0A0A0A, Replacement: #FFFFFF\n"
        "\nOn background color: #101010\n- Stroke color: #00000022, Replacement: #FFFFFF33\n"
    )
    stack = (0xFF2E3439, BLACK)
    assert _replace_color(INK, stack, t, "text") == W
    assert _replace_color(HAIR, stack, t, "stroke") == HAIR


def test_an_exact_entry_beats_the_role_default():
    t = _theme(
        "# t\n## Color Replacements\n"
        "On background color: #101010\n"
        "- Replacement: #FFFFFF\n"
        "- Text color: #3F3F46, Replacement: #D4D4D8\n"
    )
    assert _replace_color(BODY, (BLACK,), t) == 0xFFD4D4D8
    assert _replace_color(INK, (BLACK,), t) == W


def test_a_color_with_no_rule_and_no_default_is_untouched():
    t = _theme(_DARK)
    assert _replace_color(0xFF123456, (BLACK,), t) == 0xFF123456


def test_a_visible_translucent_fill_blocks_an_outer_rule():
    """Any nonzero-alpha fill establishes the context, not only opaque fills."""
    t = _theme(_DARK)
    faint_card = 0x208778F5
    assert _replace_color(INK, (faint_card, BLACK), t) == INK


def test_an_unmatched_color_stays_unchanged_in_its_context():
    """An outer rule cannot answer for the nearest visible surface."""
    t = _theme(
        "# t\n## Color Replacements\n"
        "On background color: #EDEF6B\n- Text color: #FFFFFF, Replacement: #0A0A0A\n"
        "\nOn background color: #101010\n- Text color: #0A0A0A, Replacement: #FFFFFF\n"
    )
    # Yellow has text rules but says nothing about INK, so INK keeps its color —
    # the black background further out must NOT get a say.
    assert _replace_color(INK, (0xFFEDEF6B, BLACK), t) == INK


def test_a_flipped_pill_becomes_its_own_labels_background():
    """The cascade, asserted directly rather than only by eye.

    The pill's fill is replaced FIRST, and the replaced color is what gets
    pushed for the label — so a black-on-black button that the card flips to
    white re-colors its own arrow from the `#FFFFFF` group, with no rule
    mentioning buttons at all.
    """
    t = _theme(_CARD)
    card = (BLACK,)
    pill = _replace_color(BLACK, card, t, "fill")
    assert pill == W, "the pill flips"
    label_bg = _push_bg(card, _opaque_or_none(pill))
    assert _replace_color(W, label_bg, t, "text") == BLACK, "and its label flips back"
    # Without the cascade the label would resolve against the CARD, where white
    # has no text rule, and stay invisible.
    assert _replace_color(W, card, t, "text") == W


def test_an_empty_stack_changes_nothing():
    assert _replace_color(INK, (), _theme(_DARK)) == INK


def test_a_pinned_emoji_color_outranks_every_background_rule():
    """`Fixed colors` wins: a pin is semantics, not an inherited style color.

    An emoji TINT is a style color and is replaced like text — but ❤️ red and
    🔻 red mean something, so a contrast rule must not turn them into whatever
    reads best on the card. The pin is passed to the drawer untouched; only the
    fallback tint behind it goes through `_replace_color`.
    """
    import inspect

    from md2ui.pipeline import layout_render as LR

    for fn in (
        LR.draw_link_box,
        LR.draw_code_box,
        LR.draw_styled_text_box,
        LR.draw_emoji_box,
    ):
        src = inspect.getsource(fn)
        for line in src.splitlines():
            if "fixed_colors" in line and "_replace_color" in line:
                raise AssertionError(
                    f"{fn.__name__} replaces a pinned emoji color: {line.strip()}"
                )


def test_an_inline_emoji_pin_equal_to_its_background_is_dropped():
    """Inline prose has no emoji node, but it gets the same pin veto."""
    theme = Theme()
    white = 0xFFFFFFFF
    ink = 0xFF1C1C1E
    theme.color_replacements = {white: {"text": {None: ink}}}
    surface = skia.Surface(48, 48)
    canvas = surface.getCanvas()
    canvas.clear(white)
    face = skia.Typeface.MakeDefault()
    font = make_font(face, 24)
    paint = skia.Paint(Color=ink, AntiAlias=True)

    # The helper returns the advance; the assertion that matters is that the
    # shared resolver receives the inline pin's real background context.
    advance = _draw_text_with_emoji(
        canvas,
        "✅",
        4,
        30,
        font,
        face,
        24,
        paint,
        fixed_colors={"✅": white},
        bg_stack=(white,),
        theme=theme,
    )
    assert advance > 0
    pixels = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    assert (pixels[:, :, :3] != 255).any(), "the white pin vanished on white"


# ---------------------------------------------------------------------------
# Building the stack
# ---------------------------------------------------------------------------


def test_push_skips_a_layer_that_names_nothing():
    assert _push_bg((W,), None) == (W,)
    assert _push_bg((W,), 0x00FFFFFF) == (W,)
    assert _push_bg((W,), BLACK) == (BLACK, W)


def test_a_transparent_fill_is_not_a_background():
    """Primary's default fill and the Text variant are fully transparent."""
    assert _opaque_or_none(0x00FFFFFF) is None
    assert _opaque_or_none(None) is None
    assert _opaque_or_none(BLACK) == BLACK


def test_the_page_itself_is_the_outermost_entry():
    t = Theme()
    t.root.bg_color = BLACK
    assert _root_bg_stack(t) == (BLACK,)
    t.root.box = True
    t.root.box_fill_color = W
    assert _root_bg_stack(t) == (W,)
    t.root.bg_image = "hero.png"
    assert _root_bg_stack(t) == (BG_IMAGE,)


def test_a_section_reports_the_color_its_slot_deals_it():
    """The stack must name what the paint loop actually paints, rotation and all."""
    t = Theme()
    t.sections[3] = SectionStyle(bg_colors=[0xFF6FDCA6, BLACK, 0xFFC9A7F5])
    assert _bg_selector("section", 3, None, 0, (2,), t) == 0xFF6FDCA6
    assert _bg_selector("section", 3, None, 1, (2,), t) == BLACK
    # Wraps, like every other consumer of a color list.
    assert _bg_selector("section", 3, None, 3, (2,), t) == 0xFF6FDCA6


def test_a_layer_that_paints_nothing_names_nothing():
    """Padding-only levels wrap and inset but cover nothing keyable."""
    t = Theme()
    t.sections[2] = SectionStyle()
    assert _bg_selector("section", 2, None, 0, (), t) is None
    assert _bg_selector("section", 5, None, 0, (), t) is None  # no such level


def test_a_fully_transparent_color_names_no_context():
    """A zero-alpha fill lets the nearest genuinely visible surface answer."""
    t = Theme()
    t.sections[3] = SectionStyle(bg_colors=[0x00FFFFFF])
    assert _bg_selector("section", 3, None, 0, (), t) is None


def test_a_glass_card_shields_text_from_a_root_image_rule():
    """Dashboard regression: the pane, not the root photograph, is the context."""
    t = Theme()
    t.root.bg_image = "photo.jpg"
    pane = 0xAAFFFFFF
    t.color_replacements = {BG_IMAGE: {"text": {None: W}}}
    stack = _push_bg(_root_bg_stack(t), pane)
    assert stack == (pane, BG_IMAGE)
    assert _replace_color(INK, stack, t) == INK


def test_a_photo_layer_reports_image():
    t = Theme()
    t.elements = SectionStyle(bg_colors=[W])
    assert _bg_selector("image_card", 0, "hero.png", 0, (), t) == BG_IMAGE
    # …and without a photo it is an ordinary colored card again.
    assert _bg_selector("card", 0, None, 0, (), t) == W


def test_a_fixed_style_names_its_own_photo():
    """`image <style>` keys one fixed style's photo; the rest keep `image`."""
    t = _theme(
        "# t\n## Color Replacements\n"
        "On background color: image\n- Replacement: #FFFFFF\n"
        "On background color: image Music player\n- Replacement: #101010\n"
    )
    assert t.color_replacements == {
        BG_IMAGE: {"text": {None: W}},
        f"{BG_IMAGE}:music-player": {"text": {None: BLACK}},
    }
    t.fixed_sections["music-player"] = SectionStyle(bg_image="p.png")
    t.fixed_sections["podcast"] = SectionStyle(bg_image="q.png")
    own = _bg_selector("section", 4, None, 0, (), t, fixed_style_key="music-player")
    assert own == f"{BG_IMAGE}:music-player"
    assert _replace_color(INK, _push_bg((), own), t) == BLACK
    # A styled photo with no rules of its own falls back to the theme's.
    other = _bg_selector("section", 4, None, 0, (), t, fixed_style_key="podcast")
    assert _replace_color(INK, _push_bg((), other), t) == W
    assert _replace_color(INK, (BG_IMAGE,), t) == W


# ---------------------------------------------------------------------------
# Graphic painters
# ---------------------------------------------------------------------------

_GRAPHICS = """# t
## Color Replacements
On background color: #101010
- Fill color: #5B4FC4, Replacement: #FF4A1C
- Fill color: #E9E7F2, Replacement: #3A3A3C
- Fill color: #FFFFFF, Replacement: #2C2C2E
- Stroke color: #E5E5E5, Replacement: #5A5A5E
"""


def _pixel(surface: skia.Surface, x: int, y: int) -> tuple[int, int, int, int]:
    rgba = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    red, green, blue, alpha = (int(v) for v in rgba[y, x])
    return red, green, blue, alpha


def _fonts() -> FontSet:
    face = skia.Typeface.MakeDefault()
    return FontSet(face, face, face, face, face)


def test_graphic_gradient_stops_use_fill_replacements_without_mutation():
    t = _theme(_GRAPHICS)
    original = GradientTheme(colors=[PURPLE, TRACK])
    replaced = _replaced_gradient(original, (BLACK,), t)
    assert replaced is not original
    assert replaced is not None
    assert replaced.colors == [ORANGE, DARK_TRACK]
    assert original.colors == [PURPLE, TRACK], "theme gradient was mutated"


def test_ratio_bar_fill_and_track_are_replaced_at_paint_time():
    t = _theme(_GRAPHICS)
    bt = BarTheme(thickness=10.0)
    bt.bar.bg_colors = [PURPLE]
    bt.track.bg_colors = [TRACK]
    surface = skia.Surface(100, 10)
    _paint_bar(surface.getCanvas(), 0, 0, 100, bt, 0.5, (BLACK,), t)
    assert _pixel(surface, 25, 5) == (255, 74, 28, 255)
    assert _pixel(surface, 75, 5) == (58, 58, 60, 255)


def test_marker_shapes_and_bars_use_fill_replacements_at_paint_time():
    """Marker geometry resolves after rotation, against its real box surface."""
    t = _theme(_GRAPHICS)
    box = LayoutBox(x=0, y=0, width=30, height=30, bg_stack=(BLACK,))
    for marker, pixel in (
        (
            {
                "kind": "bullet",
                "shape": "square",
                "size": 10.0,
                "color": PURPLE,
            },
            (5, 9),
        ),
        (
            {
                "kind": "quote",
                "mode": "bar",
                "bar_width": 10.0,
                "color": PURPLE,
                "aside": True,
            },
            (5, 15),
        ),
    ):
        surface = skia.Surface(30, 30)
        LR._draw_list_marker(surface.getCanvas(), box, marker, _fonts(), t)
        assert _pixel(surface, *pixel) == (255, 74, 28, 255)


def test_each_marker_kind_uses_its_declared_replacement_role():
    """Shape/bar are fill; number/quote-char/emoji are text."""
    cases = (
        ({"kind": "bullet", "shape": "square", "size": 8.0}, "fill"),
        ({"kind": "bullet", "emoji": "x", "size": 16.0}, "text"),
        (
            {
                "kind": "quote",
                "mode": "bar",
                "bar_width": 4.0,
                "aside": True,
            },
            "fill",
        ),
        ({"kind": "number", "text": "1", "font_size": 16.0}, "text"),
        (
            {
                "kind": "quote",
                "mode": "char",
                "text": "“",
                "font_size": 16.0,
            },
            "text",
        ),
    )
    box = LayoutBox(x=0, y=0, width=30, height=30, bg_stack=(BLACK,))
    for marker, expected_role in cases:
        marker["color"] = PURPLE
        surface = skia.Surface(30, 30)
        with patch.object(LR, "_replace_color", return_value=W) as replace:
            LR._draw_list_marker(surface.getCanvas(), box, marker, _fonts(), Theme())
        assert replace.call_count == 1
        color, stack, _theme_arg, role = replace.call_args.args
        assert (color, stack, role) == (PURPLE, (BLACK,), expected_role)


def test_zero_radius_makes_progress_and_chart_bars_square():
    theme = Theme()
    bar = BarTheme(thickness=10.0)
    bar.bar.bg_colors = [PURPLE]
    bar.track.bg_colors = [TRACK]
    surface = skia.Surface(100, 10)
    _paint_bar(surface.getCanvas(), 0, 0, 100, bar, 0.5)
    assert _pixel(surface, 0, 0) == (91, 79, 196, 255)

    surface = skia.Surface(50, 10)
    _chart_bar_rect(
        surface.getCanvas(),
        skia.Rect.MakeWH(50, 10),
        PURPLE,
        theme,
        0,
        (),
    )
    assert _pixel(surface, 0, 0) == (91, 79, 196, 255)


def test_progress_bar_track_can_hide_without_losing_inner_padding():
    bar = BarTheme(thickness=10.0, track_enabled=False)
    bar.track.padding.top = bar.track.padding.bottom = 3.0
    bar.track.padding.left = bar.track.padding.right = 4.0
    bar.bar.bg_colors = [PURPLE]
    surface = skia.Surface(100, 16)
    _paint_bar(surface.getCanvas(), 0, 0, 100, bar, 0.5)
    assert _pixel(surface, 1, 8) == (0, 0, 0, 0)
    assert _pixel(surface, 5, 4) == (91, 79, 196, 255)


def test_a_bar_fill_never_passes_its_track():
    """The thickness floor keeps a tiny value visible, but never past the track.

    A stub as wide as the bar is thick leaves the track when the track's inner
    width is narrower than that, so the floor is capped at the inner width —
    for a progress bar and for a horizontal chart row alike.
    """
    bar = BarTheme(thickness=30.0, track_enabled=False)
    bar.track.padding.left = bar.track.padding.right = 4.0
    bar.bar.bg_colors = [PURPLE]
    surface = skia.Surface(60, 40)
    _paint_bar(surface.getCanvas(), 0, 0, 20, bar, 0.01)
    assert _pixel(surface, 10, 5) == (91, 79, 196, 255)
    assert _pixel(surface, 17, 5) == (0, 0, 0, 0), "fill left its 12px track"

    theme = Theme()
    theme.charts.bar_thickness = 30.0
    theme.charts.track.padding.left = theme.charts.track.padding.right = 4.0
    plan = ChartPlan(
        "horizontal", 1, ["a"], [[1.0]], None, 100.0, 0.0, 10.0, 50.0, 50.0
    )
    with patch.object(render_chart, "_chart_bar_rect") as drawn:
        render_chart._draw_chart_rows(
            skia.Surface(60, 60).getCanvas(),
            0,
            0,
            20,
            plan,
            range(1),
            _fonts(),
            theme,
            (),
        )
    fill = drawn.call_args.args[1]
    assert (fill.left(), fill.right()) == (4.0, 16.0)


def test_every_datapoint_bar_family_opts_into_replacement():
    """Every bar kind is background-aware, not just the ratio family: a
    literal declared colour would leave a bar invisible on a dark card.
    """
    t = _theme(_GRAPHICS)
    for bt in (t.datapoints.ratio_bar, t.datapoints.kv_bar):
        bt.thickness = 10.0
        bt.bar.bg_colors = [PURPLE]
        bt.track.bg_colors = [TRACK]
    box = LayoutBox(x=0, y=0, width=100, height=10, bg_stack=(BLACK,))
    for kind in ("ratio", "unit", "percent", "kv_unit"):
        surface = skia.Surface(100, 10)
        _draw_datapoint_bar(
            surface.getCanvas(),
            box,
            {"kind": kind, "value": 50, "max": 100},
            _fonts(),
            t,
        )
        assert _pixel(surface, 25, 5) == (255, 74, 28, 255), (
            f"{kind} bar fill was not replaced on a {BLACK:#010x} background"
        )
    print("  ✓  every datapoint bar family follows ## Color Replacements")


def test_ring_value_and_track_arcs_use_fill_replacements():
    t = _theme(_GRAPHICS)
    t.datapoints.ring.thickness = 10.0
    t.datapoints.ring.ring.bg_colors = [PURPLE]
    t.datapoints.ring.track.bg_colors = [TRACK]
    surface = skia.Surface(100, 100)
    sbox = SectionBox(
        0,
        0,
        100,
        100,
        0,
        SectionStyle().padding,
        "ring",
        ring={"value": 25.0, "max": 100.0},
        bg_stack=(BLACK,),
    )
    _draw_ring_arc(surface.getCanvas(), sbox, t)
    assert _pixel(surface, 95, 50) == (255, 74, 28, 255)
    assert _pixel(surface, 50, 95) == (58, 58, 60, 255)


def test_date_chip_nested_regions_become_the_text_context():
    t = _theme(_GRAPHICS)
    dc = t.datapoints.date_chip
    dc.chip.bg_colors = [W]
    dc.chip.stroke_width = 2.0
    dc.chip.stroke_color = 0xFFE5E5E5
    sbox = SectionBox(
        0,
        0,
        100,
        100,
        0,
        dc.chip.padding,
        "date_chip",
        bg_stack=(BLACK,),
    )
    surface = skia.Surface(100, 100)
    _paint_date_chip_background(surface.getCanvas(), sbox, t)
    assert _pixel(surface, 50, 50) == (44, 44, 46, 255)
    assert _pixel(surface, 0, 50)[:3] == (90, 90, 94)

    dc.fill = "split"
    dc.key_bg.bg_colors = [TRACK]
    dc.day_bg.bg_colors = [PURPLE]
    surface = skia.Surface(100, 100)
    _paint_date_chip_background(surface.getCanvas(), sbox, t)
    # The base is first resolved against the enclosing black surface. Once
    # painted, that base becomes the context for the nested split regions, so
    # rules belonging to the outer black surface do not leak through it.
    assert _pixel(surface, 50, 25) == (233, 231, 242, 255)
    assert _pixel(surface, 50, 75) == (91, 79, 196, 255)
    base_stack = (0xFF2C2C2E, BLACK)
    assert _date_chip_text_bg_stack({"date_role": "key"}, base_stack, t) == (
        TRACK,
        *base_stack,
    )


def test_chart_authored_and_fallback_series_colors_are_replaced():
    t = _theme(_GRAPHICS)
    t.charts.series_colors = [PURPLE]
    assert _chart_series_color(t, 0, (BLACK,)) == ORANGE
    t.charts.series_colors = []
    t.charts.bar.bg_colors = [PURPLE]
    assert _chart_series_color(t, 0, (BLACK,)) == ORANGE


_DARK_TABLE = """# t
## Styling & Spacing
### Fixed styles
#### Dark
Background color: #101010

## Tables
### Header
Background color: #00E70019
### Cells
Background colors:
- #FDFDFD

## Color Replacements
On background color: #101010
- Fill color: #FDFDFD, Replacement: #FFFFFF14
- Fill color: #00E70019, Replacement: #00E70033
"""


def test_table_fills_are_replaced_against_the_card_they_sit_on():
    """A table's header and cell fills are replaced against the card behind
    them, and the replaced fill is what the cell text reads."""
    t = _theme(_DARK_TABLE)
    ast = session.group_markdown(
        "## Dark {#dark-1}\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",
        session.load_grouping_kit(),
    )
    assert ast is not None
    root, index = session.prepare(ast, t)
    scene = session.build_scene(
        LayoutGenerator(), root, index, t, session.load_fonts(t), 600
    )
    rows = [sb for sb in scene.sections if sb.kind in ("table_header", "table_row")]
    assert rows and all(sb.bg_stack[:1] == (BLACK,) for sb in rows)
    cell_contexts = {
        b.bg_stack[0]
        for b in scene.boxes
        if (index.get(b.content_id) or {}).get("table_role")
    }
    assert cell_contexts == {0x14FFFFFF, 0x3300E700}, cell_contexts


def test_a_stacked_tables_keys_read_the_replaced_fill():
    """A table stacked into cards puts each key on the cell fill its values sit
    on, so the key reads the replaced fill too, and a rule on it reaches both."""
    t = _theme(
        _DARK_TABLE.replace(
            "## Tables\n", "## Tables\n### Table\nStacking cards: yes\n"
        )
    )
    words = (
        "Supercalifragilistic",
        "Antidisestablishment",
        "Floccinaucinihilipil",
        "Pneumonoultramicrosc",
    )
    table = "| A | B | C | D |\n|---|---|---|---|\n| " + " | ".join(words) + " |\n"
    ast = session.group_markdown(
        "## Dark {#dark-1}\n\n" + table, session.load_grouping_kit()
    )
    assert ast is not None
    root, index = session.prepare(ast, t)
    scene = session.build_scene(
        LayoutGenerator(), root, index, t, session.load_fonts(t), 360
    )
    keys = [b for b in scene.boxes if "table_key" in (b.render_properties or {})]
    assert keys, "fixture must stack"
    assert {b.bg_stack[0] for b in keys} == {0x14FFFFFF}, [b.bg_stack for b in keys]


TESTS = [
    test_a_fixed_style_names_its_own_photo,
    test_a_group_parses_into_background_role_and_pairs,
    test_the_three_roles_land_in_their_own_channels,
    test_a_bullet_without_a_channel_is_the_text_default,
    test_background_color_is_the_fill_channel,
    test_the_old_section_name_still_parses,
    test_image_is_a_background_like_any_other,
    test_field_order_inside_a_bullet_does_not_matter,
    test_groups_are_independent,
    test_an_empty_table_is_a_no_op,
    test_each_role_reads_its_own_channel,
    test_nearest_surface_owns_every_channel,
    test_an_exact_entry_beats_the_role_default,
    test_a_color_with_no_rule_and_no_default_is_untouched,
    test_a_visible_translucent_fill_blocks_an_outer_rule,
    test_an_unmatched_color_stays_unchanged_in_its_context,
    test_a_flipped_pill_becomes_its_own_labels_background,
    test_an_empty_stack_changes_nothing,
    test_a_pinned_emoji_color_outranks_every_background_rule,
    test_an_inline_emoji_pin_equal_to_its_background_is_dropped,
    test_push_skips_a_layer_that_names_nothing,
    test_a_transparent_fill_is_not_a_background,
    test_the_page_itself_is_the_outermost_entry,
    test_a_section_reports_the_color_its_slot_deals_it,
    test_a_layer_that_paints_nothing_names_nothing,
    test_a_fully_transparent_color_names_no_context,
    test_a_glass_card_shields_text_from_a_root_image_rule,
    test_a_photo_layer_reports_image,
    test_graphic_gradient_stops_use_fill_replacements_without_mutation,
    test_ratio_bar_fill_and_track_are_replaced_at_paint_time,
    test_marker_shapes_and_bars_use_fill_replacements_at_paint_time,
    test_each_marker_kind_uses_its_declared_replacement_role,
    test_zero_radius_makes_progress_and_chart_bars_square,
    test_progress_bar_track_can_hide_without_losing_inner_padding,
    test_a_bar_fill_never_passes_its_track,
    test_every_datapoint_bar_family_opts_into_replacement,
    test_ring_value_and_track_arcs_use_fill_replacements,
    test_date_chip_nested_regions_become_the_text_context,
    test_chart_authored_and_fallback_series_colors_are_replaced,
    test_table_fills_are_replaced_against_the_card_they_sit_on,
    test_a_stacked_tables_keys_read_the_replaced_fill,
]

if __name__ == "__main__":
    print("Color Replacement Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            doc = test.__doc__.splitlines()[0] if test.__doc__ else test.__name__
            print(f"  ✓  {doc}")
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
