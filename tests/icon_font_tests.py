"""The icon font draws every emoji as the Material icon its table names (`assets/icons/`).

`scripts/build_icon_font.py` turns `material-design-icons-md2ui.md` into
`material-design-icons-md2ui.ttf`. A theme that names that font as its emoji `Font:` gets
icons through md2ui's own emoji path, unchanged: `font_runs` / `glyph_runs` pick the face,
and an emoji run holding a sequence is shaped with HarfBuzz (ADR-402), which applies the
font's ligatures. These tests read the committed font through that path.

What they hold the font to: a listed emoji draws its icon and an unlisted one a square; a
skin tone, a flag, a keycap (with or without U+FE0F) and a ZWJ sequence each draw as one
icon; a pinned fill is its own glyph; and every emoji is as wide as md2ui's emoji box, so
swapping fonts moves no layout. A character that also appears inside a sequence draws
through its own glyph, a reference to the icon, so the ligatures can tell it apart; the
tests compare the icon drawn, not that reference. A `:mirrored` icon is drawn flipped
left to right in the same advance, as an outline the build generates: `◀️` is `▶️`
facing the other way.

Run with: uv run python scripts/run_tests.py
"""

import sys
from pathlib import Path

import skia  # type: ignore[import-untyped]
from fontTools.ttLib import TTFont

from md2ui.pipeline.render_glyph_faces import (
    font_runs,
    glyph_advance,
    glyph_runs,
    runs_advance,
)
from md2ui.pipeline.render_shaping import _shaped
from md2ui.pipeline.render_text import _split_emoji_runs
from md2ui.session import repo_root

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_icon_font as build  # noqa: E402
from md2ui.utils.font_loader import make_font

SIZE = 40
BOX = build.BOX_SIZE / build.BOX_UPEM * SIZE
_FONT = TTFont(build.OUT)
_ORDER = _FONT.getGlyphOrder()
_EMOJI = skia.Typeface.MakeFromFile(str(build.OUT))
_TEXT = skia.Typeface.MakeFromFile(
    str(repo_root() / "assets" / "fonts" / "GoogleSans-Regular.ttf")
)
_TABLE = build.read_table(build.TABLE)


def _icon(gid: int) -> str:
    """The icon glyph ``gid`` draws: itself, or the one its reference points at."""
    glyph = _FONT["glyf"][_ORDER[gid]]
    return glyph.components[0].glyphName if glyph.isComposite() else _ORDER[gid]


def _drawn(text: str) -> list[str]:
    """The icons ``text`` draws as in prose, run by run as md2ui measures and paints it."""
    icons = []
    for run, font, is_emoji in font_runs(text, make_font(_TEXT, SIZE), _EMOJI, SIZE):
        assert font.getTypeface().getFamilyName() == build.FAMILY, (text, run)
        shaped = _shaped(run, font.getTypeface()) if is_emoji else None
        glyphs = shaped if shaped is not None else font.textToGlyphs(run)
        icons += [_icon(gid) for gid in glyphs if font.getWidths([gid])[0]]
    return icons


def _drawn_alone(text: str) -> list[str]:
    """The icons ``text`` draws as on its own: an emoji badge, a peeled emoji."""
    icons = []
    for run, font in glyph_runs(text, _EMOJI, _TEXT, SIZE):
        assert font.getTypeface().getFamilyName() == build.FAMILY, (text, run)
        shaped = _shaped(run, font.getTypeface())
        glyphs = shaped if shaped is not None else font.textToGlyphs(run)
        icons += [_icon(gid) for gid in glyphs if font.getWidths([gid])[0]]
    return icons


def _listed(char: str) -> str:
    """The glyph the table names for ``char``: ``star``, or ``star.filled``."""
    icon = _TABLE[tuple(ord(c) for c in char)]
    return icon.replace(":", ".")


def test_a_listed_emoji_draws_its_icon():
    assert _drawn("⭐") == _drawn_alone("⭐") == [_listed("⭐")]
    print(
        f"  ✓  ⭐ draws {_listed('⭐')}, the icon its row names, in prose and on its own"
    )


def test_an_unlisted_emoji_draws_a_square():
    star = (ord("⭐"),)
    without_star = {
        seq: icon for seq, icon in _TABLE.items() if build.strip_vs16(seq) != star
    }
    singles, _ = build.plan(without_star, build.read_emoji_test(build.EMOJI_TEST))
    assert singles[star[0]] == build.SQUARE
    print("  ✓  an emoji the table does not list draws a square")


def test_a_skin_tone_draws_the_emoji_without_it():
    assert _drawn("👍🏽") == _drawn("👍") == [_listed("👍")]
    assert _drawn_alone("👍🏽") == [_listed("👍")]
    assert _drawn("🏽") == [build.SQUARE]
    print("  ✓  👍🏽 draws as 👍; a lone skin tone as a square")


def test_flags_draw_the_flag_icon():
    for flag in ("🇪🇸", "🇺🇸", "🇦"):
        assert _drawn(flag) == _drawn_alone(flag) == [build.FLAG], flag
    assert _drawn("🇪🇸🇺🇸") == [build.FLAG, build.FLAG]
    print("  ✓  🇪🇸 and 🇺🇸 each draw one flag, as does a lone regional indicator")


def test_a_keycap_draws_one_icon_with_or_without_vs16():
    assert _drawn("1️⃣") == _drawn("1⃣") == _drawn_alone("1️⃣") == [_listed("1️⃣")]
    print("  ✓  1️⃣ and the keycap without U+FE0F draw one icon")


def test_a_zwj_sequence_draws_its_icon():
    zwj = next(seq for seq in _TABLE if 0x200D in seq)
    text = "".join(map(chr, zwj))
    assert _drawn(text) == _drawn_alone(text) == [_listed(text)], text
    without = "".join(map(chr, build.strip_vs16(zwj)))
    assert _drawn(without) == [_listed(text)], without
    print(f"  ✓  {text} draws its icon, not its parts")


def test_a_pinned_fill_is_its_own_glyph():
    assert _drawn("★") == [_listed("★")]
    assert _drawn("☆") == [_listed("☆")]
    assert _drawn("★") != _drawn("☆")
    print("  ✓  ★ and ☆ draw different glyphs")


def test_a_mirrored_icon_is_the_icon_facing_the_other_way():
    # Material has no left-facing play_arrow: ◀️ is ▶️ flipped inside its own
    # advance, as an outline of its own, generated by the build, never a flip
    # asked of the renderer.
    mirror = _FONT["glyf"][_icon(_EMOJI.unicharToGlyph(ord("◀")))]
    assert not mirror.isComposite(), "a generated outline, not a flipped reference"
    font = make_font(_EMOJI, SIZE)
    play, reverse = (_EMOJI.unicharToGlyph(ord(c)) for c in "▶◀")
    advance = font.getWidths([play])[0]
    assert font.getWidths([reverse])[0] == advance
    flipped = font.getPath(play)
    flipped.transform(skia.Matrix.Scale(-1, 1).postTranslate(advance, 0))
    drawn = font.getPath(reverse)
    assert flipped.countPoints() == drawn.countPoints() > 0
    got, want = drawn.getBounds(), flipped.getBounds()
    for a, b in zip(
        (got.left(), got.top(), got.right(), got.bottom()),
        (want.left(), want.top(), want.right(), want.bottom()),
    ):
        assert abs(a - b) < 0.01, (got, want)
    print("  ✓  ◀️ draws ▶️ flipped, the same size and fill")


def test_every_emoji_is_as_wide_as_the_box():
    """Every fully-qualified emoji Unicode lists: on its own, and in prose when md2ui
    gives it to the emoji font (a few, 🃏 or ©️, it gives to the text font)."""
    font = make_font(_TEXT, SIZE)
    emoji = [
        "".join(map(chr, seq))
        for seq, status in build.read_emoji_test(build.EMOJI_TEST)
        if status == "fully-qualified"
    ]
    wrong = [
        text
        for text in emoji
        if abs(glyph_advance(text, _EMOJI, _TEXT, SIZE) - BOX) > 1e-3
        or (
            _split_emoji_runs(text) == [(text, True)]
            and abs(runs_advance(text, font, _EMOJI, SIZE) - BOX) > 1e-3
        )
    ]
    assert not wrong, wrong[:20]
    print(f"  ✓  every emoji is {BOX:.4g} px wide at {SIZE} px: md2ui's emoji box")


def test_every_listed_character_is_in_the_font():
    """The committed font was built from the committed table."""
    cmap = _FONT.getBestCmap() or {}
    stale = [seq for seq in _TABLE if build.strip_vs16(seq)[0] not in cmap]
    assert not stale, f"rebuild with scripts/build_icon_font.py: {stale[:10]}"
    print("  ✓  every character the table lists is in the font")


TESTS = [
    test_a_listed_emoji_draws_its_icon,
    test_an_unlisted_emoji_draws_a_square,
    test_a_skin_tone_draws_the_emoji_without_it,
    test_flags_draw_the_flag_icon,
    test_a_keycap_draws_one_icon_with_or_without_vs16,
    test_a_zwj_sequence_draws_its_icon,
    test_a_pinned_fill_is_its_own_glyph,
    test_a_mirrored_icon_is_the_icon_facing_the_other_way,
    test_every_emoji_is_as_wide_as_the_box,
    test_every_listed_character_is_in_the_font,
]
