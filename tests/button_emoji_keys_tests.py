"""
An emoji in a button, a badge or a chip follows its element's variant.

* A button's emoji takes its variant's LABEL ink, so it reads on a dark fill and
  on an outline alike; ``## Emoji styles > ### Link > Color`` does not reach
  buttons, and a ``## Fixed colors`` pin on the glyph still wins.
* ``Emoji gap`` under ``## Links`` (base and per variant) is the space between a
  leading or trailing emoji and the label's words. It replaces whatever spaces
  were typed there, none included; unset, the typed space stays.
* ``Emoji weight`` under ``## Emoji styles`` (badges), ``## Links`` (buttons) and
  ``## Inline Code`` (chips), base and per variant, draws that element's emoji in
  the weight of the emoji font's family nearest it: a variable font's ``wght``
  axis, else a sibling file (``NotoEmoji-Bold.ttf`` beside
  ``NotoEmoji-Regular.ttf``). The face is read through ``FontSet``, so
  measurement and paint take the same face (ADR-400).
* A button whose whole label is ``…``, ``⋯`` or ``⋮`` is an icon button (a "more"
  button): its mark draws in the emoji face when that face has it, as md2ui's
  icon font does (``more_horiz``, ``more_vert``), and stays text dots in one
  that does not; the same character beside words, or in prose, stays text.

Run with: uv run python tests/button_emoji_keys_tests.py
"""

import tempfile
from pathlib import Path

import skia

from md2ui import session
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.render_measure import _leaf_natural_width
from md2ui.pipeline.render_text_scopes import link_label_fonts
from md2ui.pipeline.theme import Theme, parse_theme
from md2ui.utils.font_loader import varied_face
from md2ui.utils.image_cache import ImageCache

_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_EMOJI = _FONTS / "NotoEmoji-Regular.ttf"
_KIT: list = []


def _theme(body: str) -> Theme:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(f"## Emoji styles\nFont: {_EMOJI}\n\n{body}")
        return parse_theme(path)


def _link(theme: Theme, markdown: str) -> tuple[dict, dict]:
    """(the button node, the node index) of the one button *markdown* holds."""
    if not _KIT:
        _KIT.append(session.load_grouping_kit())
    root = session.group_markdown(markdown + "\n", _KIT[0])
    assert root is not None
    root, index = session.prepare(root, theme)
    return next(n for n in index.values() if n.get("type") == "link"), index


def _width(theme: Theme, markdown: str) -> float:
    node, _ = _link(theme, markdown)
    return _leaf_natural_width(node, 600.0, session.load_fonts(theme), theme)


def test_the_keys_parse():
    t = _theme(
        "### Primary\nEmoji weight: 300\n\n### Secondary\nEmoji weight: 700\n\n"
        "## Links\nEmoji gap: 8\nEmoji weight: 600\n\n"
        "### Secondary\nEmoji gap: 2\n\n### Tertiary\nEmoji weight: bold\n\n"
        "## Inline Code\nEmoji weight: 500\n\n### Secondary\nEmoji weight: 950\n"
        "\n### Tertiary\nEmoji weight: 200\n"
    )
    assert t.emojis.resolved(None).emoji_weight == 300
    assert t.emojis.resolved("secondary").emoji_weight == 700
    assert t.emojis.resolved("tertiary").emoji_weight == 300, "inherits Primary"
    assert (t.links.primary.emoji_gap, t.links.primary.emoji_weight) == (8.0, 600)
    secondary = t.links.resolved("secondary")
    assert (secondary.emoji_gap, secondary.emoji_weight) == (2.0, 600)
    assert t.links.resolved("tertiary").emoji_weight == 600, "a bad weight is no key"
    assert t.inline_code.resolved(None).emoji_weight == 500
    assert t.inline_code.resolved("secondary").emoji_weight == 500, "out of range"
    assert t.inline_code.resolved("tertiary").emoji_weight == 200
    assert Theme().links.primary.emoji_gap is None
    print("  ✓  Emoji gap / Emoji weight parse per variant, inheriting the base")


_LABEL_INK = (0x11, 0x44, 0xAA)
_LINK_TINT = (0x25, 0x84, 0x5B)


def test_outline_button_emoji_takes_the_label_ink():
    theme = _theme(
        "### Link\nColor: #25845B\n\n"
        "## Links\n### Primary\nStroke width: 2\nStroke color: #000000\n\n"
        "## Text Styles\n\nLinks\n- Font size: 32\n- Font color: #1144AA\n"
    )
    _link(theme, "[😀 Label](/x)")  # loads the grouping kit
    fonts = session.load_fonts(theme)
    root = session.group_markdown("[😀 Label](/x)\n", _KIT[0])
    assert root is not None
    root, index = session.prepare(root, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 400.0)
    image = session.render_image(scene, index, theme, fonts, ImageCache(), {}, 1.0)
    arr = image.toarray(colorType=skia.kRGBA_8888_ColorType)
    near = {_LABEL_INK: 0, _LINK_TINT: 0}
    for row in arr:
        for px in row:
            rgb = tuple(int(v) for v in px[:3])
            for ink in near:
                if sum(abs(a - b) for a, b in zip(rgb, ink)) < 24:
                    near[ink] += 1
    assert near[_LINK_TINT] == 0, f"the emoji kept `### Link` Color: {near}"
    assert near[_LABEL_INK] > 0, near
    print("  ✓  an outline button's emoji draws in its label's ink")


def test_gap_replaces_the_typed_space():
    # The same link family on both sides, so only the gap differs: a bare
    # `## Links` takes it over without setting anything.
    plain = _theme("## Links\n")
    gapped = _theme("## Links\nEmoji gap: 20\n")
    bare = _width(plain, "[😀Label](/x)")
    assert _width(plain, "[😀 Label](/x)") > bare, "unset: the typed space stays"
    for md in ("[😀Label](/x)", "[😀 Label](/x)", "[😀   Label](/x)"):
        assert abs(_width(gapped, md) - (bare + 20)) < 0.01, md
    trailing = _width(plain, "[Label😀](/x)")
    assert abs(_width(gapped, "[Label  😀](/x)") - (trailing + 20)) < 0.01
    both = _width(plain, "[😀Label😀](/x)")
    assert abs(_width(gapped, "[😀 Label 😀](/x)") - (both + 40)) < 0.01
    assert _width(gapped, "[😀](/x)") == _width(plain, "[😀](/x)"), "no words"
    print("  ✓  Emoji gap replaces the typed space, measured where it is painted")


def test_gap_is_a_run_the_painter_advances_by():
    theme = _theme("## Links\nEmoji gap: 12\n")
    fonts = session.load_fonts(theme)
    node, _ = _link(theme, "[😀 Label](/x)")
    _font, runs, _tf = link_label_fonts(node, "😀 Label", fonts, theme, 16.0)
    assert [run for run, _ in runs] == ["😀", " ", "Label"], runs
    assert abs(runs[1][1].measureText(" ") - 12) < 0.01
    print("  ✓  the gap travels with the label's runs, one space stretched to it")


def test_weight_selects_another_face():
    theme = _theme(
        "### Secondary\nEmoji weight: 300\n\n"
        "## Links\n### Secondary\nEmoji weight: 700\n\n"
        "## Inline Code\n### Secondary\nEmoji weight: 600\n"
    )
    fonts = session.load_fonts(theme)
    base = fonts.emoji
    node, _ = _link(theme, "*[😀 Label](/x)*")
    _f, _r, link_tf = link_label_fonts(node, "😀 Label", fonts, theme, 16.0)
    assert link_tf is not None and link_tf is not fonts.link_emoji
    assert link_tf.fontStyle().weight() == 700
    plain, _ = _link(theme, "[😀 Label](/x)")
    assert link_label_fonts(plain, "😀 Label", fonts, theme, 16.0)[2] is base
    _style, badge_tf = fonts.emoji_badge({"emoji_variant": "secondary"}, theme)
    assert badge_tf is not None and badge_tf.fontStyle().weight() == 300
    assert fonts.emoji_badge({}, theme)[1] is base, "Primary keeps the base face"
    chip_tf = fonts.chip_emoji("secondary", theme)
    assert chip_tf is not None and chip_tf.fontStyle().weight() == 600
    assert fonts.chip_emoji(None, theme) is base
    print("  ✓  Emoji weight picks the family's face per element variant")


def test_weight_on_a_variable_font_sets_its_axis():
    face = varied_face(str(_FONTS / "NotoEmoji-VariableFont_wght.ttf"), 650)
    assert face is not None
    assert [c.value for c in face.getVariationDesignPosition()] == [650.0]
    assert varied_face(str(_EMOJI), 420) is None, "nearest is the font itself"
    print("  ✓  a variable emoji font is set on its weight axis")


_ICONS = Path(__file__).resolve().parent.parent / "assets" / "icons"


def test_a_more_button_draws_its_icon():
    # Authors write the overflow button as dots, which no emoji range holds.
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(
            f"## Emoji styles\nFont: {_ICONS / 'material-design-icons-md2ui.ttf'}\n"
        )
        theme: Theme = parse_theme(path)
    fonts = session.load_fonts(theme)
    for mark in ("…", "⋯", "⋮"):
        node, _ = _link(theme, f"[{mark}](/more)")
        assert node.get("link_is_emoji"), mark
        _font, runs, tf = link_label_fonts(node, mark, fonts, theme, 16.0)
        assert tf is not None and tf.unicharToGlyph(ord(mark))
        assert runs[0][1].getTypeface() is tf, f"{mark} draws in the icon face"
    words, _ = _link(theme, "[More …](/more)")
    assert not words.get("link_is_emoji")
    _font, runs, tf = link_label_fonts(words, "More …", fonts, theme, 16.0)
    assert all(run_font.getTypeface() is not tf for _, run_font in runs)
    noto = _theme("")  # Noto Emoji has no dots: the label keeps its text face
    node, _ = _link(noto, "[…](/more)")
    font, runs, _tf = link_label_fonts(node, "…", session.load_fonts(noto), noto, 16.0)
    assert runs[0][1].getTypeface() is font.getTypeface()
    print("  ✓  a button labelled only by dots draws the emoji face's more icon")


TESTS = [
    test_the_keys_parse,
    test_outline_button_emoji_takes_the_label_ink,
    test_gap_replaces_the_typed_space,
    test_gap_is_a_run_the_painter_advances_by,
    test_weight_selects_another_face,
    test_weight_on_a_variable_font_sets_its_axis,
    test_a_more_button_draws_its_icon,
]


if __name__ == "__main__":
    for t in TESTS:
        t()
