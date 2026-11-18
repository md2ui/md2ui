"""Shared layered backgrounds for buttons, chips, and emoji badges.

These element families keep their solid fill, radius, padding, stroke,
variant, rotation, and replacement rules. Their backgrounds also use
the section/card layer order: outer shadows, solid color, image, gradient, then
inner shadows. Background images are decoded once per source for a scene.

Run with: uv run python tests/element_background_paint_tests.py
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import skia  # type: ignore[import-untyped]

from md2ui.pipeline import layout_render as LR
from md2ui.pipeline import render_pill_paint as PP
from md2ui.pipeline import render_placeholders as RP
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import GradientTheme, ShadowSpec, Theme, parse_theme


def _theme(markdown: str) -> Theme:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "THEME.md"
        path.write_text(markdown)
        return parse_theme(path)


def _fonts() -> FontSet:
    face = skia.Typeface.MakeDefault()
    return FontSet(face, face, face, face, face, face, {})


def test_layered_background_keys_parse_and_variants_inherit():
    theme = _theme(
        """## Links
### Primary
Background color: #112233
Background image: shared.png
Background gradient:
- Colors:
  - #223344
  - #445566
Outer shadow:
- Color: #00000080
- Radius: 8
### Secondary
Corner radius: 9
Inner shadow:
- Color: #FFFFFF40
- Radius: 2

## Inline Code
Background color: #334455
Background image: shared.png
Background gradient:
- Colors:
  - #556677
  - #778899
Inner shadow:
- Color: #00000060
- Radius: 4
### Secondary
Stroke width: 2

## Emoji styles
### Primary
Background image: shared.png
Background gradient:
- Colors:
  - #667788
  - #8899AA
Outer shadow:
- Color: #00000040
- Radius: 6
### Secondary
Icon size: 24
"""
    )

    button = theme.links.resolved("secondary")
    assert button.fill_color == 0xFF112233
    assert button.bg_image == "shared.png"
    assert button.gradient is not None
    assert button.gradient.colors == [0xFF223344, 0xFF445566]
    assert len(button.shadows) == 2
    assert not button.shadows[0].inner and button.shadows[1].inner

    chip = theme.inline_code.resolved("secondary")
    assert chip.fill_color == 0xFF334455
    assert chip.bg_image == "shared.png"
    assert chip.gradient is not None
    assert chip.gradient.colors == [0xFF556677, 0xFF778899]
    assert len(chip.shadows) == 1 and chip.shadows[0].inner

    badge = theme.emojis.resolved("secondary")
    assert badge.fill.bg_image == "shared.png"
    assert badge.fill.gradient is not None
    assert badge.fill.gradient.colors == [0xFF667788, 0xFF8899AA]
    assert len(badge.fill.shadows) == 1
    print("  ✓  layered element backgrounds parse and inherit through variants")


def test_element_background_images_load_once_per_source():
    theme = Theme()
    theme.links.primary.bg_image = "shared.png"
    theme.inline_code.bg_image = "shared.png"
    theme.emojis.primary.fill.bg_image = "shared.png"
    calls: list[str | None] = []
    decoded = object()

    def fake_decode(source):
        calls.append(source)
        return decoded if source else None

    with patch.object(RP, "theme_picture", side_effect=fake_decode):
        images = LR.load_background_images(theme)

    assert images[("element", "shared.png")] is decoded
    assert calls.count("shared.png") == 1
    print("  ✓  one decoded image is shared by button, chip, and badge backgrounds")


def test_all_three_elements_use_the_shared_layered_painter():
    theme = Theme()
    gradient = GradientTheme(colors=[0xFF112233, 0xFF445566])
    shadow = ShadowSpec(color=0x66000000, radius=4)
    theme.links.primary.fill_color = 0xFF223344
    theme.links.primary.bg_image = "shared.png"
    theme.links.primary.gradient = gradient
    theme.links.primary.shadows = [shadow]
    theme.inline_code.fill_color = 0xFF334455
    theme.inline_code.bg_image = "shared.png"
    theme.inline_code.gradient = gradient
    theme.inline_code.shadows = [shadow]
    theme.emojis.primary.fill.bg_image = "shared.png"
    theme.emojis.primary.fill.bg_colors = [0xFF223344]
    theme.emojis.primary.fill.gradient = gradient
    theme.emojis.primary.fill.shadows = [shadow]
    surface_color = 0xFF010203
    theme.color_replacements = {
        surface_color: {
            "fill": {
                0xFF112233: 0xFFAABBCC,
                0xFF445566: 0xFFDDEEFF,
                0xFF223344: 0xFFA1B2C3,
                0xFF334455: 0xFFB2C3D4,
            }
        }
    }

    decoded = object()
    images = {("element", "shared.png"): decoded}
    calls: list[dict] = []

    def record(_canvas, _rect, **kwargs):
        calls.append(kwargs)

    surface = skia.Surface(600, 120)
    canvas = surface.getCanvas()
    face = skia.Typeface.MakeDefault()
    boxes = [LayoutBox(i * 200, 0, 180, 60) for i in range(3)]
    for box in boxes:
        box.bg_stack = (surface_color,)
    with (
        patch.object(LR, "_paint_layered_fill", side_effect=record),
        patch.object(PP, "_paint_layered_fill", side_effect=record),  # a button's
    ):
        LR.draw_link_box(
            canvas,
            boxes[0],
            {
                "type": "link",
                "content": "[Open](#open)",
                "link_label": "Open",
                "link_variant": "primary",
            },
            _fonts(),
            theme,
            images,
        )
        LR.draw_code_box(
            canvas,
            boxes[1],
            "`Ready`",
            face,
            theme,
            face,
            None,
            {},
            images,
        )
        LR.draw_emoji_box(
            canvas,
            boxes[2],
            {"type": "emoji", "content": "★", "emoji_kind": "alone"},
            _fonts(),
            theme,
            images,
        )

    assert len(calls) == 3
    assert all(call["image"] is decoded for call in calls)
    assert all(call["gradient"].colors == [0xFFAABBCC, 0xFFDDEEFF] for call in calls)
    assert [call["bg_color"] for call in calls] == [
        0xFFA1B2C3,
        0xFFB2C3D4,
        0xFFA1B2C3,
    ]
    assert all(call["shadows"] == [shadow] for call in calls)
    print("  ✓  all three use the layered painter and fill-color replacements")


TESTS = [
    test_layered_background_keys_parse_and_variants_inherit,
    test_element_background_images_load_once_per_source,
    test_all_three_elements_use_the_shared_layered_painter,
]


if __name__ == "__main__":
    print("Element Background Paint Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:
            failed += 1
            print(f"  ✗  {test.__name__}: {exc}")
    print("=" * 50)
    raise SystemExit(1 if failed else 0)
