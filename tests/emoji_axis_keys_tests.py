"""
``Emoji fill``, ``Emoji grade`` and ``Emoji optical size`` set an icon font's
FILL, GRAD and opsz axes, where and as ``Emoji weight`` sets its wght.

* They are read under ``## Emoji styles`` (badges), ``## Links`` (buttons) and
  ``## Inline Code`` (chips), base and per variant, and a variant that states
  none inherits its base's, exactly as ``Emoji weight`` does.
* ``Emoji fill`` takes 0–1, ``Emoji grade`` any number, ``Emoji optical size`` a
  size above 0 or ``auto``: the size the glyph is drawn at. Each is clamped to
  the font's range on its axis; a value outside the key's range is no key.
* One face carries every axis asked (``font_loader.varied_face``), read through
  ``FontSet.varied_emoji`` so measurement and paint take the same face
  (ADR-400). A key the font has no axis for changes nothing, so a static font,
  or a theme stating none of the keys, keeps the face it had.

The face-level checks run on the tracked ``GoogleSans`` variable font, whose
axes are wght, GRAD and opsz (17–18); it has no FILL axis, which is what the
"a missing axis is ignored" check needs.

Run with: uv run python tests/emoji_axis_keys_tests.py
"""

import tempfile
from pathlib import Path

import skia  # type: ignore[import-untyped]

from md2ui import session
from md2ui.pipeline.render_text_scopes import link_label_fonts
from md2ui.pipeline.theme import Theme, parse_theme
from md2ui.pipeline.theme_model import EmojiAxes

_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_VARIABLE = _FONTS / "GoogleSans-VariableFont_GRAD,opsz,wght.ttf"
_STATIC = _FONTS / "GoogleSans-Regular.ttf"
_TAG = {b"wght": "wght", b"GRAD": "GRAD", b"opsz": "opsz", b"FILL": "FILL"}


def _theme(body: str, font: Path = _VARIABLE) -> Theme:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(f"## Emoji styles\nFont: {font}\n\n{body}")
        return parse_theme(path)


def _position(face: skia.Typeface | None) -> dict[str, float]:
    """*face*'s variation position, by axis name."""
    assert face is not None
    return {
        _TAG[c.axis.to_bytes(4, "big")]: c.value
        for c in face.getVariationDesignPosition()
    }


def test_the_keys_parse_and_inherit():
    t = _theme(
        "### Primary\nEmoji fill: 1\nEmoji grade: -25\nEmoji optical size: auto\n\n"
        "### Secondary\nEmoji fill: 0.5\n\n"
        "### Tertiary\nEmoji fill: 2\nEmoji optical size: 0\n\n"
        "## Links\nEmoji grade: 100\nEmoji optical size: 24\n\n"
        "### Secondary\nEmoji fill: 0\n\n"
        "## Inline Code\nEmoji optical size: auto\n\n"
        "### Secondary\nEmoji grade: 50\n"
    )
    assert t.emojis.resolved(None).emoji_axes == EmojiAxes(1.0, -25.0, "auto")
    assert t.emojis.resolved("secondary").emoji_axes == EmojiAxes(0.5, -25.0, "auto")
    assert t.emojis.resolved("tertiary").emoji_axes == EmojiAxes(1.0, -25.0, "auto"), (
        "an out-of-range value is no key"
    )
    assert t.links.resolved("primary").emoji_axes == EmojiAxes(None, 100.0, 24.0)
    assert t.links.resolved("secondary").emoji_axes == EmojiAxes(0.0, 100.0, 24.0)
    assert t.inline_code.resolved(None).emoji_axes == EmojiAxes(None, None, "auto")
    assert t.inline_code.resolved("secondary").emoji_axes == EmojiAxes(
        None, 50.0, "auto"
    )
    print(
        "  ✓  Emoji fill / grade / optical size parse per variant, inheriting the base"
    )


def test_each_key_reaches_the_face():
    theme = _theme(
        "### Primary\nEmoji grade: 150\nEmoji optical size: 17.5\n\n"
        "## Links\n### Secondary\nEmoji grade: -50\nEmoji weight: 600\n\n"
        "## Inline Code\n### Secondary\nEmoji optical size: 18\n"
    )
    fonts = session.load_fonts(theme)
    badge = _position(fonts.emoji_badge({}, theme)[1])
    assert (badge["GRAD"], badge["opsz"], badge["wght"]) == (150.0, 17.5, 400.0)
    link = link_label_fonts({"link_variant": "secondary"}, "😀 x", fonts, theme, 16.0)
    assert (_position(link[2])["GRAD"], _position(link[2])["wght"]) == (-50.0, 600.0)
    assert _position(fonts.chip_emoji("secondary", theme))["opsz"] == 18.0
    print(
        "  ✓  each key sets its axis on the element's face; one face carries them all"
    )


def test_auto_optical_size_follows_the_drawn_size_and_clamps():
    theme = _theme(
        "### Primary\nIcon size: 17.5\nEmoji optical size: auto\n\n"
        "### Secondary\nIcon size: 12\n\n### Tertiary\nIcon size: 40\n\n"
        "### Quaternary\nIcon size: 64\n"
    )
    fonts = session.load_fonts(theme)

    def face(variant):
        return fonts.emoji_badge({"emoji_variant": variant}, theme)[1]

    assert _position(face(None))["opsz"] == 17.5, "the drawn size"
    assert _position(face("secondary"))["opsz"] == 17.0, "clamped to the axis minimum"
    assert _position(face("tertiary"))["opsz"] == 18.0, "clamped to the axis maximum"
    assert face("tertiary") is face("quaternary"), "one face per axis position"
    print("  ✓  auto optical size is the drawn size, clamped to the font's axis")


def test_absent_or_missing_axes_keep_the_face():
    fonts = session.load_fonts(plain := _theme(""))
    assert fonts.emoji_badge({}, plain)[1] is fonts.emoji, "no key, no new face"
    assert fonts.chip_emoji(None, plain) is fonts.emoji
    no_fill = _theme("### Primary\nEmoji fill: 1\n")
    fonts = session.load_fonts(no_fill)
    assert fonts.emoji_badge({}, no_fill)[1] is fonts.emoji, "the font has no FILL"
    static = _theme(
        "### Primary\nEmoji fill: 1\nEmoji grade: 100\nEmoji optical size: auto\n",
        _STATIC,
    )
    fonts = session.load_fonts(static)
    assert fonts.emoji_badge({}, static)[1] is fonts.emoji, "a static font"
    print("  ✓  an absent key, or an axis the font lacks, keeps the face as loaded")


TESTS = [
    test_the_keys_parse_and_inherit,
    test_each_key_reaches_the_face,
    test_auto_optical_size_follows_the_drawn_size_and_clamps,
    test_absent_or_missing_axes_keep_the_face,
]


if __name__ == "__main__":
    for t in TESTS:
        t()
