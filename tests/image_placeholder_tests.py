"""
Unit tests for named image placeholders (ADR-406).

An image that writes ``?md2ui.placeholder=<name>`` or ``<name>:<text>`` and has no
picture (its source left out, loading or failed) paints the theme's placeholder of
that name, declared under ``## Images`` → ``### Placeholders`` → ``#### Avatar``: a
fill, and centred in it the image's text or the placeholder's icon, inside the clip the
picture would use. Pinned here:

  * the theme parse: colours (one, or a rotating bullet list), text style, sizes, icon;
  * the URL: ``name`` or ``name:text``, named as headings are; never a layout param;
  * rotation: each placeholder name counts its own cycle per section, as chips do;
  * the paint: the declared fill inside the picture's own clip (a circle stays one), and
    an undeclared name leaves the default quiet box;
  * the defaults: ``#### Loading``, ``Broken`` or ``Missing`` under ``### Placeholders``,
    in any order, restyle md2ui's own for every image that names none, and a named placeholder outranks it; an ``Image:`` is
    drawn over the fill;
  * ``check``: an undeclared name is a warning, text past three characters a note;
  * the lint: a placeholder with no MEANINGS.md row, and a row with no placeholder.

Run with: uv run python tests/image_placeholder_tests.py
"""

import contextlib
import io
import tempfile
from pathlib import Path

import numpy as np
import skia

from md2ui import check_placeholders, session
from md2ui.meanings import Contract, Row, Section
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.render_image_placeholder import named_placeholder
from md2ui.pipeline.theme import parse_theme
from md2ui.pipeline.theme_placeholders import placeholder_name
from md2ui.utils.image_cache import ImageCache
from md2ui.utils.image_params import image_params, placeholder_ref

THEME = Path("data/markdown/tests/THEME.md")
_KIT = None


def _theme_from(text: str):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(text)
    try:
        return parse_theme(Path(f.name))
    finally:
        Path(f.name).unlink()


def _tree(markdown: str) -> dict:
    global _KIT
    with contextlib.redirect_stdout(io.StringIO()):
        if _KIT is None:
            _KIT = session.load_grouping_kit()
        ast = session.group_markdown(markdown, _KIT)
    assert ast is not None
    return ast.to_dict()


def _pixels(
    markdown: str, width: float = 600.0, theme_path: Path = THEME
) -> tuple[np.ndarray, list, dict]:
    """The page painted, its boxes, and its nodes."""
    with contextlib.redirect_stdout(io.StringIO()):
        theme = session.load_theme(theme_path)
        fonts = session.load_fonts(theme)
        session.load_placeholders()
        ast = session.group_markdown(markdown, _KIT or session.load_grouping_kit())
        assert ast is not None
        root, index = session.prepare(ast, theme)
        scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, width)
        image = session.render_image(scene, index, theme, fonts, ImageCache(), {}, 1)
    pad = theme.root.padding
    boxes = [(b, pad.left, pad.top) for b in scene.boxes]
    return image.toarray(colorType=skia.kRGBA_8888_ColorType), boxes, index


def _image_box(boxes: list, index: dict):
    hits = [
        (b, dx, dy)
        for b, dx, dy in boxes
        if b.content_id and index.get(b.content_id, {}).get("type") == "image"
    ]
    assert len(hits) == 1, hits
    return hits[0]


def _rgb(pixels: np.ndarray, x: float, y: float) -> tuple[int, int, int]:
    """The colour at (x, y); the painted array is RGBA."""
    r, g, b, _a = pixels[int(y), int(x)]
    return int(r), int(g), int(b)


def test_the_theme_declares_placeholders_by_name():
    theme = _theme_from(
        "## Images\n\n### Placeholders\n\n#### Avatar Style\nFill color:\n- #E8F0FE\n"
        "- #FDE7E9\nText color: #1A56DB\nText style: Lead\nText size: 40%\n\n"
        "#### Media\nFill color: #F2F2F2\nIcon: 🖼️\nIcon size: 28\n"
    )
    avatar = theme.image_placeholders["avatar-style"]
    assert avatar.fill_colors == [0xFFE8F0FE, 0xFFFDE7E9]
    assert avatar.text_colors == [0xFF1A56DB]
    assert (avatar.text_style, avatar.text_size) == ("lead", (40.0, True))
    media = theme.image_placeholders["media"]
    assert (media.icon, media.icon_size, media.fill_colors) == (
        "🖼️",
        (28.0, False),
        [0xFFF2F2F2],
    )
    assert not _theme_from(
        "## Images\n\n#### Avatar\nFill color: #000000\n"
    ).image_placeholders
    print("  ✓  ## Images → ### Placeholders declares each placeholder by its heading")


def test_an_image_names_a_placeholder_and_maybe_its_text():
    assert placeholder_ref("![S](?md2ui.placeholder=avatar:SZ)") == ("avatar", "SZ")
    assert placeholder_ref("![S](x.jpg?md2ui.placeholder=Media)") == ("media", "")
    assert placeholder_ref("![S](?md2ui.placeholder=Avatar_Style:👤)") == (
        "avatar-style",
        "👤",
    )
    assert placeholder_ref("![S](x.jpg?md2ui.shape=circle)") is None
    params = image_params("![S](?md2ui.placeholder=avatar:SZ&md2ui.shape=circle)")
    assert params == {"shape": "circle"}, "a placeholder is never a layout param"
    print("  ✓  ?md2ui.placeholder= names a placeholder, and text after a colon")


_AVATAR = "## Team\n\n![Sara Zane](?md2ui.placeholder={}:SZ&md2ui.shape=circle&md2ui.max_width=120)\n"


def test_a_named_placeholder_fills_the_pictures_own_clip():
    pixels, boxes, index = _pixels(_AVATAR.format("avatar"))
    box, dx, dy = _image_box(boxes, index)
    side = min(box.width, box.height, 120)
    cx, cy = dx + box.x + side / 2, dy + box.y + box.height / 2
    # Left of the initials, inside the circle: the avatar's first fill.
    assert _rgb(pixels, cx - side * 0.38, cy) == (0xE8, 0xF0, 0xFE)
    # The circle's corner: outside the clip, never the fill.
    assert _rgb(pixels, dx + box.x + 2, cy - side / 2 + 2) != (0xE8, 0xF0, 0xFE)
    # Ink in the middle: the initials, in the avatar's text colour family.
    middle = pixels[int(cy) - 8 : int(cy) + 8, int(cx) - 20 : int(cx) + 20]
    assert (middle[..., :3] != np.array([0xE8, 0xF0, 0xFE])).any()
    print("  ✓  the placeholder paints its fill and text inside the picture's circle")


def test_an_undeclared_name_keeps_the_quiet_box():
    pixels, boxes, index = _pixels(_AVATAR.format("nobody"))
    box, dx, dy = _image_box(boxes, index)
    side = min(box.width, box.height, 120)
    cx, cy = dx + box.x + side / 2, dy + box.y + box.height / 2
    assert _rgb(pixels, cx, cy) == (0xD0, 0xD0, 0xD0), "the quiet box, as before"
    print("  ✓  a name the theme does not declare draws today's quiet box")


def _contract(*spellings: str) -> Contract:
    rows = [
        Row(write=f"`{s}`", means="a person with no photo", selects=None)
        for s in spellings
    ]
    return Contract(preamble="", sections=[Section("Placeholders", "", rows)])


def test_check_warns_on_an_undeclared_name_and_notes_long_text():
    contract = _contract("![Name](?md2ui.placeholder=avatar:SZ)")
    tree = _tree(
        "## Team\n\n![A](?md2ui.placeholder=avatar:SZ)\n\n![B](?md2ui.placeholder=brand:AC)\n\n"
        "![C](?md2ui.placeholder=avatar:Sara)\n\n![D](?md2ui.placeholder=avatar:👩‍💻)\n"
    )
    codes = [
        (code, msg.split("`")[1])
        for _lvl, code, msg in check_placeholders.problems(tree, contract)
    ]
    assert codes == [("undeclared-placeholder", "B"), ("placeholder-text", "C")], codes
    assert check_placeholders.problems(tree, None) == [
        p for p in check_placeholders.problems(tree, None) if p[1] == "placeholder-text"
    ], "with no contract, names are not judged"
    print("  ✓  check warns on an undeclared name and notes text past three characters")


def test_the_lint_pairs_placeholders_with_meanings_rows():
    theme = _theme_from(
        "## Images\n\n### Placeholders\n\n#### Avatar\nFill color: #000000\n\n#### Media\nFill color: #111111\n"
    )
    messages = check_placeholders.lint(
        theme, _contract("?md2ui.placeholder=avatar:SZ", "?md2ui.placeholder=brand:AC")
    )
    assert any("`media` is drawn but no MEANINGS.md row" in m for m in messages), (
        messages
    )
    assert any("offers placeholder `brand`" in m for m in messages), messages
    assert len(messages) == 2, messages
    alone = check_placeholders.lint(theme, None)
    assert alone and "no MEANINGS.md" in alone[0], alone
    assert check_placeholders.lint(_theme_from("## Images\n"), None) == []
    print("  ✓  the lint reports a placeholder without a row, and a row without one")


DEFAULTS = Path("data/markdown/tests/image-placeholder-defaults/THEME.md")


def test_defaults_and_images_are_declared_too():
    theme = _theme_from(
        # The defaults first, a named one after: a defaults block written above
        # the named ones must not swallow them.
        "## Images\n\n### Placeholders\n\n#### Missing\nFill color: #FFF4E5\n\n"
        "#### Brand\nImage: assets/brand.png\n"
    )
    assert theme.image_placeholders["brand"].bg_image == "assets/brand.png"
    assert list(theme.image_placeholders) == ["brand"], (
        "a reserved name is no named one"
    )
    assert list(theme.image_placeholder_defaults) == ["missing"]
    assert theme.image_placeholder_defaults["missing"].fill_colors == [0xFFFFF4E5]
    print("  ✓  `Image:`, and Loading / Broken / Missing as defaults, in any order")


def test_a_default_restyles_an_image_that_names_none():
    pixels, boxes, index = _pixels(
        "## Shop\n\n![Product photo]()\n", theme_path=DEFAULTS
    )
    box, dx, dy = _image_box(boxes, index)
    assert _rgb(pixels, dx + box.x + 4, dy + box.y + 4) == (0xFF, 0xF4, 0xE5)
    named, boxes, index = _pixels(_AVATAR.format("avatar"), theme_path=DEFAULTS)
    box, dx, dy = _image_box(boxes, index)
    side = min(box.width, box.height, 120)
    cx, cy = dx + box.x + side / 2, dy + box.y + box.height / 2
    assert _rgb(named, cx - side * 0.38, cy) == (0xE8, 0xF0, 0xFE), "the name wins"
    print("  ✓  a default restyles an image that names none; a name outranks it")


def test_a_real_picture_never_takes_a_placeholder():
    """A loaded picture wins: only a stand-in (left out, loading, broken) is replaced."""
    assert placeholder_name("  Avatar Style! ") == "avatar-style"
    with contextlib.redirect_stdout(io.StringIO()):
        theme = session.load_theme(DEFAULTS)
        fonts = session.load_fonts(theme)
    surface = skia.Surface(4, 4)
    photo = surface.makeImageSnapshot()
    content = "![Sara](x.jpg?md2ui.placeholder=avatar:SZ)"
    assert named_placeholder(photo, content, {}, theme, fonts) is None
    print("  ✓  a loaded picture is drawn, never its placeholder")


def test_placeholders_in_list_rows_rotate_their_own_cycle():
    """Each placeholder name counts its own colour cycle per section, as chips do,
    so four avatars in four list rows take four colours."""
    rows = "".join(
        f"- ![{n}](?md2ui.placeholder=avatar:{n[0]}&md2ui.shape=circle) - **{n}**\n"
        for n in ("Ana", "Ben", "Cy")
    )
    tree = _tree(f"## Contacts\n\n{rows}\n![Acme](?md2ui.placeholder=brand:AC)\n")
    slots = [
        n.get("rotation_index") or 0  # to_dict leaves a zero out
        for n in _walk(tree)
        if n.get("type") == "image" and "avatar" in str(n.get("content"))
    ]
    assert slots == [0, 1, 2], slots
    brand = [n for n in _walk(tree) if "brand" in str(n.get("content", ""))]
    assert brand and brand[0].get("rotation_index", 0) == 0, "brand counts apart"
    print("  ✓  a placeholder name counts its own colour cycle, as chips do")


def _walk(node: dict):
    yield node
    for child in node.get("children", []):
        yield from _walk(child)


def test_the_lint_reports_a_block_the_parser_ignores():
    """Anything under ## Images but outside ### Placeholders is dropped without a word,
    so the lint names the block; a commented one is not read, and is not reported."""
    images = "## Images\n\n### Placeholders\n\n#### Avatar\nFill color: #000000\n"
    assert check_placeholders.unknown_blocks(images) == []
    stray = images + "\n### Defaults\n\n#### Broken\nFill color: #F2F2F2\n"
    found = check_placeholders.unknown_blocks(stray)
    assert len(found) == 1 and "`### Defaults`" in found[0], found
    commented = images + "\n<!--### Defaults\n#### Broken-->\n"
    assert check_placeholders.unknown_blocks(commented) == []
    elsewhere = "## Text Styles\n\n### Defaults\n\n" + images
    assert check_placeholders.unknown_blocks(elsewhere) == [], "only under ## Images"
    print("  ✓  the lint names a ### block under ## Images that the parser ignores")


def test_rotate_placeholder_colors_turns_the_cycle_off():
    """`Rotate placeholder colors: no` pins fill and text to their first colours; the
    section-fill and text switches do not reach a placeholder."""
    rows = "".join(
        f"- ![{n}](?md2ui.placeholder=avatar:{n[0]}&md2ui.shape=circle&md2ui.max_width=48)"
        f" - **{n}**\n"
        for n in ("Ana", "Ben")
    )
    page = f"## Contacts\n\n{rows}"

    def fills(gate: str) -> list[tuple[int, int, int]]:
        text = THEME.read_text().replace("### Heading 2\n", f"### Heading 2\n{gate}", 1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "THEME.md"
            path.write_text(text)
            pixels, boxes, index = _pixels(page, theme_path=path)
        avatars = sorted(
            (
                b
                for b, _dx, _dy in boxes
                if index.get(b.content_id or "", {}).get("type") == "image"
            ),
            key=lambda b: b.y,
        )
        dx, dy = boxes[0][1], boxes[0][2]
        return [_rgb(pixels, dx + b.x + 4, dy + b.y + b.height / 2) for b in avatars]

    assert fills("") == [(0xE8, 0xF0, 0xFE), (0xFD, 0xE7, 0xE9)], "rotates by default"
    pinned = [(0xE8, 0xF0, 0xFE)] * 2
    assert fills("Rotate placeholder colors: no\n") == pinned
    assert fills("Rotate colors: no\n") == pinned, "the blanket form covers it"
    assert fills("Rotate background colors: no\n") != pinned, (
        "the section switch does not"
    )
    print(
        "  ✓  Rotate placeholder colors: no pins a placeholder; section switches do not"
    )


TESTS = [
    test_rotate_placeholder_colors_turns_the_cycle_off,
    test_placeholders_in_list_rows_rotate_their_own_cycle,
    test_the_lint_reports_a_block_the_parser_ignores,
    test_the_theme_declares_placeholders_by_name,
    test_a_real_picture_never_takes_a_placeholder,
    test_defaults_and_images_are_declared_too,
    test_a_default_restyles_an_image_that_names_none,
    test_an_image_names_a_placeholder_and_maybe_its_text,
    test_a_named_placeholder_fills_the_pictures_own_clip,
    test_an_undeclared_name_keeps_the_quiet_box,
    test_check_warns_on_an_undeclared_name_and_notes_long_text,
    test_the_lint_pairs_placeholders_with_meanings_rows,
]


if __name__ == "__main__":
    print("Image Placeholder Tests")
    print("=" * 50)
    for t in TESTS:
        t()
    print("=" * 50)
    print(f"All {len(TESTS)} tests passed.")
