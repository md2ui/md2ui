"""
Strokes: where the line sits on an edge (``Stroke align``) and that it is the
front layer.

Skia centres a stroke on its path, which is ``center``, the default. ``outside`` grows the shape by half the width so the whole line lies
beyond the edge, ``inside`` shrinks it so the whole line lies within; a rounded
corner's radius moves with the edge. The key is read the same way on every
stroked surface: sections and cards, buttons, and chips.

A section's stroke is painted after all content, so a photo or a card reaching
the edge cannot cover its inner half.

Run with: uv run python tests/stroke_align_tests.py
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import skia

from md2ui.pipeline import layout_render as LR
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_backgrounds import SectionBox
from md2ui.pipeline.render_shadows import stroke_shape
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import PaddingBox, parse_theme


def _theme(text: str):
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(text)
        return parse_theme(path)


def _xywh(r) -> tuple[float, float, float, float]:
    return (r.x(), r.y(), r.width(), r.height())


RECT = skia.Rect.MakeXYWH(10, 10, 100, 50)


def test_center_is_the_shape_itself():
    shape, radius = stroke_shape(RECT, 12.0, 8.0, "center")
    assert _xywh(shape) == (10, 10, 100, 50) and radius == 12.0
    print("  ✓  center strokes along the edge, as before")


def test_outside_and_inside_move_the_edge_by_half_the_width():
    out, r_out = stroke_shape(RECT, 12.0, 8.0, "outside")
    inn, r_in = stroke_shape(RECT, 12.0, 8.0, "inside")
    assert _xywh(out) == (6, 6, 108, 58) and r_out == 16.0
    assert _xywh(inn) == (14, 14, 92, 42) and r_in == 8.0
    print("  ✓  outside grows the shape by w/2, inside shrinks it; radius follows")


def test_a_sharp_corner_stays_sharp_and_a_small_radius_floors_at_zero():
    assert stroke_shape(RECT, 0.0, 8.0, "outside")[1] == 0.0
    assert stroke_shape(RECT, 2.0, 8.0, "inside")[1] == 0.0
    print("  ✓  no radius is invented; none goes negative")


def test_every_stroked_surface_reads_the_key():
    t = _theme(
        "## Styling & Spacing\n### Heading 2\nStroke align: Inside\n\n"
        "## Links\nStroke align: outer\n### Secondary\nFill color: #FF0000\n"
        "### Tertiary\nStroke align: center\n\n"
        "## Inline Code\nStroke align: outside\n### Secondary\nFill color: #FF0000\n\n"
        "## Emoji styles\n### Primary\nStroke align: inside\n\n"
        "## Charts\nStroke align: outside\n"
    )
    assert t.sections[2].stroke_align == "inside"
    assert t.links.resolved("primary").stroke_align == "outside"
    assert t.links.resolved("secondary").stroke_align == "outside", "inherited"
    assert t.links.resolved("tertiary").stroke_align == "center"
    assert t.inline_code.resolved("secondary").stroke_align == "outside"
    assert t.emojis.primary.fill.stroke_align == "inside"
    assert t.charts.bar.stroke_align == "outside"
    assert _theme("## Links\nStroke align: sideways\n").links.primary.stroke_align == (
        "center"
    ), "an unknown value is ignored"
    print("  ✓  sections, buttons (with variants), chips, badges and charts parse it")


def test_a_section_stroke_is_painted_after_the_content():
    t = _theme(
        "## Styling & Spacing\n### Heading 2\nBackground color: #FFFFFF\n"
        "Stroke width: 8\nStroke color: #FF4A1C\n"
    )
    order: list[str] = []
    sbox = SectionBox(0, 0, 200, 100, 2, PaddingBox())
    face = skia.Typeface.MakeDefault()
    with (
        patch.object(LR, "draw_content_box", lambda *a, **k: order.append("content")),
        patch.object(LR, "draw_stroke", lambda *a, **k: order.append("stroke")),
    ):
        LR.draw_document(
            skia.Surface(200, 100).getCanvas(),
            [LayoutBox(0, 0, 200, 100)],
            [sbox],
            {},
            200.0,
            100.0,
            FontSet(face, face, face, face, face),
            MagicMock(),
            t,
        )
    assert order == ["content", "stroke"], order
    print("  ✓  the stroke is the front layer: content first, then the stroke")


TESTS = [
    test_center_is_the_shape_itself,
    test_outside_and_inside_move_the_edge_by_half_the_width,
    test_a_sharp_corner_stays_sharp_and_a_small_radius_floors_at_zero,
    test_every_stroked_surface_reads_the_key,
    test_a_section_stroke_is_painted_after_the_content,
]


if __name__ == "__main__":
    print("Stroke Align Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:
            failed += 1
            print(f"  ✗  {test.__name__}: {type(exc).__name__}: {exc}")
    print("=" * 50)
    if failed:
        raise SystemExit(f"{failed} test(s) FAILED")
    print(f"All {len(TESTS)} tests passed.")
