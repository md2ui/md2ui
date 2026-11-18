"""A theme's font files resolve to the face each emphasis draws in.

``resolve_typeface`` answers a (family, weight, italic) request from the files
the theme loaded: the exact file, else the nearest weight in the same style.
A family loaded without its italic files still keeps the weight asked for --
bold italic takes the Bold file, italic the Regular one -- and ``styled_font``
slants that upright face, as a browser synthesises an oblique. A family that
has its italic files draws them unslanted.

A slanted word leans past its advance, so a text box ending in one widens its
clip -- never its measured width -- to keep that ink; any other box clips at
its edge exactly.

A system family no theme loaded answers a weight it lacks as CSS font matching
does, among the weights the family has: 500 takes 400 before 700, 600 takes
700. The rule is checked on explicit weight sets, so it holds on any host; the
Arial checks run only where the host's Arial is the Regular + Bold family they
were measured on (macOS), and say so where it is not.
"""

import struct
import unittest

import numpy as np
import skia  # type: ignore[import-untyped]

from md2ui.pipeline.layout_render import draw_styled_text_box
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_metrics import _measure_word
from md2ui.pipeline.render_style import FontSet, _span_font
from md2ui.pipeline.theme import Theme
from md2ui.utils.font_loader import (
    _FONT_MGR,
    MONOSPACE_FAMILIES,
    _declared_family,
    family_name,
    make_font,
    SYNTHETIC_OBLIQUE_SKEW,
    css_matched_weight,
    load_custom_fonts,
    resolve_code_typeface,
    resolve_typeface,
    styled_font,
)
from md2ui.session import repo_root

_FONTS = repo_root() / "assets" / "fonts"
_FAMILY = "inter 18pt"


def _load(*names: str):
    return load_custom_fonts([str(_FONTS / f"Inter_18pt-{n}.ttf") for n in names])


def _style(tf: skia.Typeface) -> tuple[int, bool]:
    fs = tf.fontStyle()
    return fs.weight(), fs.slant() != skia.FontStyle.kUpright_Slant


def test_no_italic_file_keeps_the_weight():
    custom = _load("Regular", "Bold")
    assert _style(resolve_typeface(_FAMILY, 700, True, custom)) == (700, False)
    assert _style(resolve_typeface(_FAMILY, 400, True, custom)) == (400, False)
    print("  ✓  with no italic file, bold italic takes Bold and italic takes Regular")


def test_italic_files_are_still_chosen():
    custom = _load("Regular", "Bold", "Italic", "BoldItalic")
    assert _style(resolve_typeface(_FAMILY, 700, True, custom)) == (700, True)
    assert _style(resolve_typeface(_FAMILY, 400, True, custom)) == (400, True)
    print("  ✓  a family with italic files resolves italic requests to them")


def test_only_an_upright_face_is_slanted():
    custom = _load("Regular", "Italic")
    upright = resolve_typeface(_FAMILY, 400, False, custom)
    italic = resolve_typeface(_FAMILY, 400, True, custom)
    assert styled_font(upright, 16, True).getSkewX() == SYNTHETIC_OBLIQUE_SKEW
    assert styled_font(upright, 16, False).getSkewX() == 0
    assert styled_font(italic, 16, True).getSkewX() == 0
    print("  ✓  the synthetic slant applies only where no italic face exists")


def test_bold_italic_span_draws_bold_and_slanted():
    custom = _load("Regular", "Bold")
    faces = [
        resolve_typeface(_FAMILY, w, i, custom)
        for w, i in ((400, False), (700, False), (400, True), (700, True))
    ]
    fonts = FontSet(faces[0], faces[1], faces[2], faces[3], faces[0])
    font = _span_font(fonts, 16, bold=True, italic=True)
    assert _style(font.getTypeface())[0] == 700
    assert font.getSkewX() == SYNTHETIC_OBLIQUE_SKEW
    # The slant moves no advance, so measuring without it still agrees.
    plain = make_font(font.getTypeface(), 16)
    assert font.measureText("bold italic") == plain.measureText("bold italic")
    print("  ✓  ***bold italic*** draws in Bold, slanted, at Bold's advance")


def _no_italic_fonts() -> FontSet:
    custom = _load("Regular", "Bold")
    faces = [
        resolve_typeface(_FAMILY, w, i, custom)
        for w, i in ((400, False), (700, False), (400, True), (700, True))
    ]
    return FontSet(faces[0], faces[1], faces[2], faces[3], faces[0])


def _ink_right_of(content: str, box_w: float, size: float = 32) -> tuple[int, int]:
    """(inked pixels right of the box edge as drawn, and as drawn unclipped)."""
    fonts = _no_italic_fonts()
    drawn = skia.Surface(400, 80)
    drawn.getCanvas().clear(skia.ColorWHITE)
    box = LayoutBox(x=0.0, y=0.0, width=box_w, height=60.0)
    draw_styled_text_box(
        drawn.getCanvas(), box, content, fonts, size, 0xFF000000, Theme()
    )
    italic = content.startswith("*")
    font = _span_font(fonts, size, False, italic)
    free = skia.Surface(400, 80)
    free.getCanvas().clear(skia.ColorWHITE)
    free.getCanvas().drawString(
        content.strip("*"), 0, size, font, skia.Paint(Color=0xFF000000, AntiAlias=True)
    )
    edge = int(np.ceil(box_w))
    ink = [
        int(
            np.count_nonzero(
                s.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[
                    :, edge:, :3
                ]
                < 250
            )
        )
        for s in (drawn, free)
    ]
    return ink[0], ink[1]


def test_a_slanted_last_word_keeps_its_ink():
    fonts = _no_italic_fonts()
    advance = _measure_word("bold", False, True, fonts, 32)
    drawn, free = _ink_right_of("*bold*", advance)
    assert free > 0, "the slanted d leans past its advance"
    assert drawn == free, (drawn, free)
    print("  ✓  a box ending in a synthesised slant does not cut that slant off")


def test_an_upright_last_word_clips_at_the_edge():
    fonts = _no_italic_fonts()
    advance = _measure_word("bold", False, False, fonts, 32)
    drawn, free = _ink_right_of("bold", advance - 8)
    assert free > 0 and drawn == 0, (drawn, free)
    print("  ✓  any other box still clips at its own edge")


def test_css_weight_matching_rule():
    regular_bold = [400, 700]
    assert css_matched_weight(500, regular_bold) == 400
    assert css_matched_weight(600, regular_bold) == 700
    assert css_matched_weight(300, regular_bold) == 400
    assert css_matched_weight(900, regular_bold) == 700
    # 400-500: up to 500 first, then lighter, then heavier.
    assert css_matched_weight(400, [300, 500, 600]) == 500
    assert css_matched_weight(450, [300, 600]) == 300
    # Lighter than 400 looks lighter first; heavier than 500 looks heavier first.
    assert css_matched_weight(300, [200, 400]) == 200
    assert css_matched_weight(600, [500, 800]) == 800
    assert css_matched_weight(700, [100, 400, 700]) == 700
    print("  ✓  a missing weight resolves by the CSS font-matching order")


def _require_host_arial_regular_bold() -> None:
    styles = skia.FontMgr.RefDefault().matchFamily("Arial")
    weights = {styles.getStyle(i)[0].weight() for i in range(styles.count())}
    if weights != {400, 700}:
        raise unittest.SkipTest(f"host Arial has weights {sorted(weights)}")


def test_system_arial_500_draws_regular():
    _require_host_arial_regular_bold()
    face = resolve_typeface("Arial", 500, False, {})
    assert _style(face) == (400, False), _style(face)
    assert _style(resolve_typeface("Arial", 500, True, {})) == (400, True)
    print("  ✓  system Arial at 500 draws Regular, as a browser does")


def test_system_arial_keeps_its_bold_and_exact_weights():
    _require_host_arial_regular_bold()
    assert _style(resolve_typeface("Arial", 600, False, {}))[0] == 700
    assert _style(resolve_typeface("Arial", 700, False, {}))[0] == 700
    assert _style(resolve_typeface("Arial", 400, False, {}))[0] == 400
    print("  ✓  system Arial at 600 stays Bold; weights it has resolve exactly")


def test_an_unloaded_code_font_falls_back_to_monospace():
    # A code block whose family is neither loaded nor installed keeps its columns.
    def fixed_pitch(face: skia.Typeface) -> bool:
        font = make_font(face, 20)
        return font.measureText("iiii") == font.measureText("MMMM")

    missing = "Not An Installed Mono"
    assert not fixed_pitch(resolve_typeface(missing, 400, False, {})), "fixture"
    assert fixed_pitch(resolve_code_typeface(missing, 400, False, {}))
    plex = load_custom_fonts(
        [str(repo_root() / "assets/fonts/IBMPlexMono-Regular.ttf")]
    )
    loaded = resolve_code_typeface("IBM Plex Mono", 400, False, plex)
    assert family_name(loaded) == "IBM Plex Mono", "a loaded family is kept"
    print("  ✓  an unloaded code font falls back to a monospaced face")


def test_a_theme_names_a_font_by_its_file_whatever_the_platform_calls_it():
    # DirectWrite (Windows) calls Inter_18pt-*.ttf 'Inter 18pt 18pt'; the file's
    # own name table, and CoreText and FreeType, call it 'Inter 18pt'.
    platform_name = skia.Typeface.getFamilyName
    skia.Typeface.getFamilyName = lambda tf: platform_name(tf) + " 18pt"
    try:
        custom = _load("Regular", "Bold")
        assert {k[0] for k in custom} == {_FAMILY}, sorted(custom)
        face = resolve_typeface("Inter 18pt", 700, False, custom)
    finally:
        skia.Typeface.getFamilyName = platform_name
    assert face is custom[(_FAMILY, 700, False)], face.getFamilyName()
    print("  ✓  a theme's family resolves to its file, whatever the platform calls it")


def test_a_name_table_family_prefers_the_typographic_english_record():
    def record(platform: int, encoding: int, language: int, name_id: int, text: bytes):
        return (platform, encoding, language, name_id, text)

    records = [
        record(1, 0, 0, 16, "Caf\u00e9 Mac".encode("mac_roman")),
        record(3, 1, 0x40C, 16, "Famille".encode("utf-16-be")),
        record(3, 1, 0x409, 1, "Cafe Legacy".encode("utf-16-be")),
        record(3, 1, 0x409, 16, "Caf\u00e9".encode("utf-16-be")),
    ]
    header = 6 + 12 * len(records)
    table, strings = struct.pack(">HHH", 0, len(records), header), b""
    for platform, encoding, language, name_id, text in records:
        table += struct.pack(
            ">6H", platform, encoding, language, name_id, len(text), len(strings)
        )
        strings += text
    assert _declared_family(table + strings) == "Caf\u00e9"
    cut = table + strings[: -len(records[-1][-1])]
    assert _declared_family(cut) == "Famille", "a record past the table is skipped"
    assert _declared_family(b"") is None
    print("  ✓  the name table's US-English typographic family wins, decoded")


def test_the_generic_monospace_is_monospaced_where_the_platform_lacks_it():
    # DirectWrite (Windows) knows no generic families: it answers 'monospace'
    # with its proportional default face, as this stand-in does.
    make_from_name = skia.Typeface.MakeFromName
    default = make_from_name("Helvetica", skia.FontStyle.Normal())

    def no_generics(name, style):
        return default if name == "monospace" else make_from_name(name, style)

    skia.Typeface.MakeFromName = staticmethod(no_generics)
    try:
        face = resolve_typeface("monospace", 400, False, {})
        code = resolve_code_typeface("Not An Installed Mono", 400, False, {})
    finally:
        skia.Typeface.MakeFromName = make_from_name
    if not any(_FONT_MGR.matchFamily(f).count() for f in MONOSPACE_FAMILIES):
        raise unittest.SkipTest(f"none of {MONOSPACE_FAMILIES} is installed here")
    assert face.isFixedPitch() and code.isFixedPitch(), face.getFamilyName()
    print("  ✓  'monospace' draws a monospaced face where the platform has no generic")


TESTS = [
    test_a_theme_names_a_font_by_its_file_whatever_the_platform_calls_it,
    test_a_name_table_family_prefers_the_typographic_english_record,
    test_the_generic_monospace_is_monospaced_where_the_platform_lacks_it,
    test_no_italic_file_keeps_the_weight,
    test_italic_files_are_still_chosen,
    test_only_an_upright_face_is_slanted,
    test_bold_italic_span_draws_bold_and_slanted,
    test_a_slanted_last_word_keeps_its_ink,
    test_an_upright_last_word_clips_at_the_edge,
    test_css_weight_matching_rule,
    test_system_arial_500_draws_regular,
    test_system_arial_keeps_its_bold_and_exact_weights,
    test_an_unloaded_code_font_falls_back_to_monospace,
]
