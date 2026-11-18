"""Card and section chrome uses background-aware stroke replacements."""

import sys

import skia

sys.path.insert(0, "tests")

from color_replacement_tests import _pixel

from md2ui.pipeline.layout_render import _paint_section_background
from md2ui.pipeline.render_backgrounds import SectionBox, _emit_wrap_boxes
from md2ui.pipeline.theme import BG_IMAGE, PaddingBox, SectionStyle, Theme

RED = 0xFFFF0000
GREEN = 0xFF00FF00
BLACK = 0xFF000000
WHITE = 0xFFFFFFFF


def _paint(style: SectionStyle, theme: Theme, *, image_card: bool = False):
    surface = skia.Surface(20, 20)
    box = SectionBox(
        2,
        2,
        16,
        16,
        0,
        PaddingBox(),
        "image_card" if image_card else "card",
        bg_image_url="photo.jpg" if image_card else None,
        bg_stack=(BLACK,),
    )
    _paint_section_background(
        surface.getCanvas(),
        box,
        style,
        bg_color=style.bg_colors[0] if style.bg_colors else None,
        theme=theme,
    )
    return _pixel(surface, 2, 10)


def test_card_stroke_resolves_against_its_own_fill():
    theme = Theme()
    theme.color_replacements = {WHITE: {"stroke": {RED: GREEN}}}
    style = SectionStyle(bg_colors=[WHITE], stroke_width=4.0, stroke_color=RED)
    assert _paint(style, theme) == (0, 255, 0, 255)
    print("  ✓  a card stroke resolves against the card's own fill")


def test_image_card_stroke_resolves_against_image():
    theme = Theme()
    theme.color_replacements = {BG_IMAGE: {"stroke": {RED: GREEN}}}
    style = SectionStyle(stroke_width=4.0, stroke_color=RED)
    assert _paint(style, theme, image_card=True) == (0, 255, 0, 255)
    print("  ✓  an image-card stroke resolves against its own photograph")


def test_section_fill_is_replaced_against_what_it_sits_on():
    theme = Theme()
    theme.color_replacements = {BLACK: {"fill": {RED: GREEN}}}
    assert _paint(SectionStyle(bg_colors=[RED]), theme) == (0, 255, 0, 255)
    print("  ✓  a section fill is replaced against the surface it sits on")


def test_replaced_list_fill_is_its_contents_context():
    theme = Theme()
    theme.unordered_lists.bg_colors = [RED]
    theme.color_replacements = {BLACK: {"fill": {RED: GREEN}}}
    layers = [("unordered_list", 0, theme.unordered_lists)]
    *_, stack = _emit_wrap_boxes(
        [], 0, 0, 10, 10, layers, theme=theme, bg_stack=(BLACK,)
    )
    assert stack == (GREEN, BLACK)
    print("  ✓  a list item's text sits on its replaced fill, not the authored one")


TESTS = [
    test_section_fill_is_replaced_against_what_it_sits_on,
    test_replaced_list_fill_is_its_contents_context,
    test_card_stroke_resolves_against_its_own_fill,
    test_image_card_stroke_resolves_against_image,
]
