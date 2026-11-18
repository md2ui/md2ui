"""Emoji and symbol glyphs consistently route to the configured emoji font.

Prose, mixed link labels and standalone emoji all share ``_split_emoji_runs``.
These probes cover Unicode planes the body font may or may not contain, so
rendering never depends on it.

A character the run's face lacks then falls back, per run, to a face that has
it -- the body face for a symbol the emoji face lacks, else a system face in the
same weight -- through ``render_glyph_faces.font_runs``, which measurement and
painting both read. Covered text keeps its exact runs and fonts.

A glyph drawn on its own -- an emoji badge, a peeled emoji, a code block's
lines -- takes the same fallback through ``glyph_runs`` / ``glyph_advance``.
"""

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.render_glyph_faces import font_runs
from md2ui.pipeline.render_code_blocks import code_block_plan
from md2ui.pipeline.render_metrics import _emoji_badge_size, _measure_word
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.render_text import _split_emoji_runs
from md2ui.pipeline.render_text_paint import _draw_text_with_emoji
from md2ui.pipeline.theme_model import CodeBlockTheme, EmojiBadgeStyle
from md2ui.session import repo_root
from md2ui.utils.font_loader import make_font

_FONTS = repo_root() / "assets" / "fonts"


SYMBOLS = "↗▶⭐🔖"


def test_symbol_planes_are_all_emoji_runs():
    assert _split_emoji_runs(SYMBOLS) == [(SYMBOLS, True)]
    print("  ✓  arrows, shapes, stars and pictographs all route to the emoji font")


def test_symbols_split_from_surrounding_prose_or_link_text():
    assert _split_emoji_runs(f"Open {SYMBOLS} now") == [
        ("Open ", False),
        (SYMBOLS, True),
        (" now", False),
    ]
    print("  ✓  emoji-font runs split consistently inside mixed text labels")


def _fonts() -> FontSet:
    regular = skia.Typeface.MakeFromFile(str(_FONTS / "Inter_18pt-Regular.ttf"))
    bold = skia.Typeface.MakeFromFile(str(_FONTS / "Inter_18pt-Bold.ttf"))
    emoji = skia.Typeface.MakeFromFile(str(_FONTS / "OpenMoji-black-glyf.ttf"))
    return FontSet(regular, bold, regular, bold, regular, emoji)


def _all_drawn(text: str, fonts: FontSet, font: "skia.Font") -> bool:
    return all(
        f.getTypeface().unicharToGlyph(ord(ch)) != 0
        for run, f, _ in font_runs(text, font, fonts.emoji, 16)
        for ch in run
    )


def test_covered_text_keeps_its_runs_and_fonts():
    fonts = _fonts()
    font = make_font(fonts.typeface, 16)
    for text in ("Plain words", "Math ∑ ≈ ∞", "Open ↔★ now"):
        runs = font_runs(text, font, fonts.emoji, 16)
        assert [(r, e) for r, _, e in runs] == _split_emoji_runs(text), text
        for _, f, is_emoji in runs:
            assert f.getTypeface() is (fonts.emoji if is_emoji else fonts.typeface)
        assert all(f is font for _, f, e in runs if not e), text
    print("  ✓  text the theme faces cover keeps the runs and fonts it had")


def test_missing_glyphs_fall_back_to_a_face_that_has_them():
    fonts = _fonts()
    font = make_font(fonts.typeface, 16)
    for text in ("Quarter ⏷", "CJK 漢字", "Arrow ▾ and ▼", "a → b ✓"):
        assert _all_drawn(text, fonts, font), text
    # ▼ and → are emoji-slot symbols OpenMoji lacks; the body face has them.
    runs = font_runs("a → b", font, fonts.emoji, 16)
    assert [f.getTypeface() for r, f, _ in runs if r == "→"] == [fonts.typeface]
    assert [e for r, _, e in runs if r == "→"] == [True], "keeps the emoji paint"
    print("  ✓  ⏷, ▾, ▼, → and CJK draw in a face that has the glyph")


def test_fallback_keeps_the_weight():
    fonts = _fonts()
    bold = make_font(fonts.bold, 16)
    face = font_runs("太字", bold, fonts.emoji, 16)[0][1].getTypeface()
    assert face.unicharToGlyph(ord("太")) != 0
    assert face.fontStyle().weight() >= 600
    print("  ✓  bold CJK falls back to a bold system face")


def test_fallback_glyphs_measure_as_wide_as_they_draw():
    fonts = _fonts()
    word = "収益⏷▾"
    measured = _measure_word(word, False, False, fonts, 16)
    surface = skia.Surface(200, 40)
    drawn = _draw_text_with_emoji(
        surface.getCanvas(),
        word,
        0,
        20,
        make_font(fonts.typeface, 16),
        fonts.emoji,
        16,
        skia.Paint(),
    )
    assert measured == drawn, (measured, drawn)
    assert measured > 0
    print("  ✓  a fallback word measures exactly as wide as it paints (ADR-400)")


def test_lone_badge_glyph_measures_in_a_face_that_has_it():
    fonts = _fonts()
    style = EmojiBadgeStyle(icon_size=20.0)
    pad = style.fill.padding.x
    # → is missing from OpenMoji: the badge sizes to the body face's arrow.
    width, _ = _emoji_badge_size("→", style, fonts.emoji, fonts.typeface)
    assert width == make_font(fonts.typeface, 20.0).measureText("→") + pad, width
    # ⭐ is OpenMoji's own: measured in it.
    width, _ = _emoji_badge_size("⭐", style, fonts.emoji, fonts.typeface)
    assert width == make_font(fonts.emoji, 20.0).measureText("⭐") + pad, width
    print("  ✓  a lone badge glyph the emoji face lacks sizes in the body face")


def test_lone_glyph_paints_as_wide_as_it_measures():
    from md2ui.pipeline.render_glyph_faces import glyph_advance, glyph_runs
    from md2ui.pipeline.render_text_paint import draw_glyph_runs

    fonts = _fonts()
    for text in ("→", "⭐", "✓漢", "⏷"):
        runs = glyph_runs(text, fonts.emoji, fonts.typeface, 20.0)
        assert all(
            f.getTypeface().unicharToGlyph(ord(ch)) != 0 for r, f in runs for ch in r
        ), text
        surface = skia.Surface(200, 60)
        drawn = draw_glyph_runs(
            surface.getCanvas(),
            text,
            0,
            40,
            fonts.emoji,
            fonts.typeface,
            20.0,
            skia.Paint(),
        )
        assert drawn == glyph_advance(text, fonts.emoji, fonts.typeface, 20.0), text
    print("  ✓  a lone glyph draws from a face that has it, as wide as measured")


def test_code_block_measures_fallback_glyphs_as_drawn():
    mono = skia.Typeface.MakeFromFile(str(_FONTS / "IBMPlexMono-Regular.ttf"))
    theme = CodeBlockTheme(copy_icon=None)
    ascii_plan = code_block_plan("ab", None, mono, theme)
    cjk_plan = code_block_plan("漢字", None, mono, theme)
    # Two CJK glyphs from a system face are wider than two mono cells; drawn
    # as the mono face's missing-glyph boxes they would be exactly two cells.
    assert cjk_plan.width > ascii_plan.width, (cjk_plan.width, ascii_plan.width)
    # Text the mono face covers keeps its mono width.
    mono_w = make_font(mono, theme.text_style.font_size).measureText("a → ✓")
    plan = code_block_plan("a → ✓", None, mono, theme)
    assert plan.width == mono_w + theme.padding.x, plan.width
    print("  ✓  a code block measures fallback CJK as wide as it draws")


def test_a_selector_the_face_would_box_is_not_measured_or_drawn():
    """Noto Emoji resolves ``❤`` + U+FE0F as one sequence and leaves the
    selector's slot as glyph 0, the missing-glyph box, which would draw ``❤️``
    wider than ``❤``. OpenMoji maps the selector to its own empty glyph, so its
    runs keep the selector."""
    from md2ui.pipeline.render_glyph_faces import glyph_advance, runs_advance

    fonts = _fonts()
    noto = skia.Typeface.MakeFromFile(str(_FONTS / "NotoEmoji-Medium.ttf"))
    font = make_font(fonts.typeface, 16)
    for bare in ("❤", "☀", "▶", "🗂"):
        sel = bare + "\ufe0f"
        assert runs_advance(sel, font, noto, 16) == runs_advance(
            bare, font, noto, 16
        ), sel
        assert glyph_advance(sel, noto, fonts.typeface, 40) == glyph_advance(
            bare, noto, fonts.typeface, 40
        ), sel
    assert [r for r, _, _ in font_runs("Sunny ☀\ufe0f", font, fonts.emoji, 16)] == [
        "Sunny ",
        "☀\ufe0f",
    ], "OpenMoji keeps its runs"
    print(
        "  ✓  a selector Noto Emoji would draw as a box is neither measured nor drawn"
    )


# A joined emoji, a flag, a skin tone and a keycap: each one glyph in the font,
# through its ligature table only.
SEQUENCES = (
    "\U0001f468\u200d\U0001f4bb",
    "\U0001f1fa\U0001f1f8",
    "\U0001f44d\U0001f3fd",
    "1\ufe0f\u20e3",
)


def _emoji_faces() -> list["skia.Typeface"]:
    return [
        skia.Typeface.MakeFromFile(str(_FONTS / "OpenMoji-black-glyf.ttf")),
        skia.Typeface.MakeFromFile(str(_FONTS / "NotoEmoji-Medium.ttf")),
    ]


def test_an_emoji_sequence_measures_as_one_glyph():
    """Mapped character by character, 👨‍💻 would draw as a man and a laptop,
    🇺🇸 as the letters U and S. Shaped, each is one emoji wide, as a
    badge and in prose, in both emoji fonts."""
    from md2ui.pipeline.render_glyph_faces import glyph_advance, runs_advance

    body = _fonts().typeface
    font = make_font(body, 16)
    one = "\U0001f468"
    for face in _emoji_faces():
        name = face.getFamilyName()
        for seq in SEQUENCES:
            assert glyph_advance(seq, face, body, 40) == glyph_advance(
                one, face, body, 40
            ), (name, seq)
            assert runs_advance(f"a {seq} b", font, face, 16) == runs_advance(
                f"a {one} b", font, face, 16
            ), (name, seq)
    print("  ✓  👨‍💻, 🇺🇸, 👍🏽 and 1️⃣ each measure one glyph wide in both fonts")


def test_a_shaped_sequence_paints_as_wide_as_it_measures():
    """The shaped glyph is the one painted, at the width measured, and a pin
    keyed on the whole sequence colours it (ADR-400)."""
    from md2ui.pipeline.render_glyph_faces import glyph_advance
    from md2ui.pipeline.render_text_paint import draw_glyph_runs

    body = _fonts().typeface
    font = make_font(body, 16)
    for face in _emoji_faces():
        for seq in SEQUENCES:
            word = f"x{seq}"
            fonts = FontSet(body, body, body, body, body, face)
            measured = _measure_word(word, False, False, fonts, 16)
            surface = skia.Surface(120, 40)
            drawn = _draw_text_with_emoji(
                surface.getCanvas(),
                word,
                0,
                30,
                font,
                face,
                16,
                skia.Paint(),
                fixed_colors={seq: 0xFFFF0000},
            )
            assert measured == drawn, (seq, measured, drawn)
            # Red, whichever order the platform keeps its channels in.
            px = (
                surface.makeImageSnapshot()
                .toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3]
                .astype(int)
            )
            assert ((px.max(axis=-1) > 200) & (px[..., 1] < 60)).any(), seq
            surface = skia.Surface(120, 60)
            drawn = draw_glyph_runs(
                surface.getCanvas(), seq, 0, 40, face, body, 40, skia.Paint()
            )
            assert drawn == glyph_advance(seq, face, body, 40), seq
    print("  ✓  a shaped sequence paints as wide as it measures, and takes its pin")


def test_runs_without_a_sequence_are_not_shaped():
    """Plain text, and an emoji run holding no sequence, measure exactly as
    skia measures their characters: shaping changes nothing else."""
    from md2ui.pipeline.render_glyph_faces import font_runs, runs_advance
    from md2ui.pipeline.render_shaping import run_advance

    body = _fonts().typeface
    font = make_font(body, 16)
    for face in _emoji_faces():
        for text in ("café naïve", "Math ∑ ≈ ∞", "Ship 🚀⭐ it", "Hot ❤\ufe0f"):
            expected = sum(
                f.measureText(r) for r, f, _ in font_runs(text, font, face, 16)
            )
            assert runs_advance(text, font, face, 16) == expected, text
        # A run from the text slot is never shaped, even holding a sequence.
        emoji = make_font(face, 16)
        for seq in SEQUENCES:
            assert run_advance(seq, emoji, False) == emoji.measureText(seq), seq
    print("  ✓  runs without an emoji sequence measure as their characters")


TESTS = [
    test_an_emoji_sequence_measures_as_one_glyph,
    test_a_shaped_sequence_paints_as_wide_as_it_measures,
    test_runs_without_a_sequence_are_not_shaped,
    test_a_selector_the_face_would_box_is_not_measured_or_drawn,
    test_lone_badge_glyph_measures_in_a_face_that_has_it,
    test_lone_glyph_paints_as_wide_as_it_measures,
    test_code_block_measures_fallback_glyphs_as_drawn,
    test_covered_text_keeps_its_runs_and_fonts,
    test_missing_glyphs_fall_back_to_a_face_that_has_them,
    test_fallback_keeps_the_weight,
    test_fallback_glyphs_measure_as_wide_as_they_draw,
    test_symbol_planes_are_all_emoji_runs,
    test_symbols_split_from_surrounding_prose_or_link_text,
]
