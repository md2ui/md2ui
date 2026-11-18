"""
Unit tests for heading-line style inheritance: when the grouper splits a heading
LINE, every text piece of that line keeps the heading's font, size and color —
links and standalone `code` elements opt out, and the section's BODY lines are
never touched. Also covers the heading-family bold face, the `Key` style of a
display's pair on a heading line, and the measurers that have
to agree with all of it or the layout clips what it draws.
Run with: uv run python tests/layout_heading_style_tests.py
"""

import sys

sys.path.insert(0, "tests")

import skia
from markdown_datapoint_split_tests import _processed_with_criteria

from md2ui.pipeline.render_style import FontSet, _effective_text_fonts
from md2ui.pipeline import render_measure as RMS
from md2ui.pipeline import render_place as RPL
from md2ui.pipeline.layout_render import (
    _stamp_heading_ctx,
    _walk,
    make_line_width_measurer,
    make_width_measurer,
)
from md2ui.pipeline.theme import TextStyle, Theme

H2, H3, BODY = 32.0, 24.0, 16.0


def _theme() -> Theme:
    t = Theme()
    t.text = TextStyle(font_size=BODY)
    t.headings = {2: TextStyle(font_size=H2), 3: TextStyle(font_size=H3)}
    return t


def _fonts() -> FontSet:
    tf = skia.Typeface.MakeDefault()
    bold = skia.Typeface.MakeFromName("Helvetica", skia.FontStyle.Bold())
    return FontSet(tf, bold, tf, bold, tf)


def _stamped(md: str):
    """Grouping tree run through the renderer's heading-context pass."""
    ast = _processed_with_criteria(md)
    _stamp_heading_ctx(ast)
    return ast


def _leaves(node, out=None):
    out = [] if out is None else out
    if not node.children:
        out.append(node)
    for c in node.children:
        _leaves(c, out)
    return out


def _by_content(node, needle):
    for leaf in _leaves(node):
        if needle in (leaf.content or ""):
            return leaf
    raise AssertionError(f"no leaf containing {needle!r}")


def _size(node, theme=None) -> float:
    _f, size = _effective_text_fonts(
        node.type,
        0,
        _fonts(),
        theme or _theme(),
        heading_ctx=getattr(node, "heading_ctx", 0),
    )
    return size


def test_split_heading_pieces_inherit():
    ast = _stamped("### My schedule [<](/prev) **Today** [>](/next)")
    assert _by_content(ast, "My schedule").heading_ctx == 3
    assert _by_content(ast, "Today").heading_ctx == 3
    assert _size(_by_content(ast, "My schedule")) == H3
    assert _size(_by_content(ast, "Today")) == H3
    print("  ✓  every text piece of a split heading line inherits its level")


def test_links_and_code_leaves_opt_out():
    ast = _stamped("### 🗓 - Datapoint tests `code` - [link](/link)")
    link = _by_content(ast, "[link]")
    assert link.heading_ctx == 0, "a link renders as its own button"
    for leaf in _leaves(ast):
        if leaf.type == "inline_code":
            assert leaf.heading_ctx == 0, "a standalone `code` stays a pill"
    print("  ✓  links and standalone `code` leaves never inherit")


def test_section_body_untouched():
    # The heading CONTENT GROUP spans the body lines too — inheritance must
    # follow the heading LINE only, or the whole section would go heading-sized.
    ast = _stamped("## Overview\n\nBody text under the heading.\n")
    body = _by_content(ast, "Body text")
    assert body.heading_ctx == 0, "section body is not part of the heading line"
    assert _size(body) == BODY
    print("  ✓  a section's body lines keep body text style")


def test_nested_heading_text_element():
    # The heading's text element can sit at any depth (here under a glued
    # emoji+text segment), so inheritance keys off the line, not child position.
    ast = _stamped("#### 🗓 Datapoint tests - `code` [link](/link)")
    piece = _by_content(ast, "Datapoint tests")
    assert piece.heading_ctx == 4, "nested heading text still inherits"
    print("  ✓  a heading text element nested in a glued group still inherits")


def test_kv_on_a_heading_line():
    # A colon alone makes no pair (ADR-205): the line is the heading as written.
    line = _by_content(_stamped("## Monthly Budget: **$2,450**"), "Monthly Budget")
    assert line.content == "Monthly Budget: **$2,450**" and _size(line) == H2
    # A display's pair on a heading line: its key takes `Key`, else body Text.
    ast = _stamped("## Progress: 60%")
    key = _by_content(ast, "Progress")
    value = _by_content(ast, "60%")
    assert key.type == "key" and key.heading_ctx == 2
    theme = _theme()
    theme.key_style = TextStyle(font_size=14.0)
    assert _size(key, theme) == 14.0, "key takes the Key size"
    assert _size(value, theme) == H2, "value keeps the heading's style"
    assert _size(key) == BODY
    print("  ✓  heading K-V: key = Key style, value = heading style")


def test_heading_bold_face():
    # The bold pair of a level's heading_typefaces is what **x** inside that
    # heading resolves to — not the body bold face.
    fonts = _fonts()
    h_reg = skia.Typeface.MakeFromName("Times", skia.FontStyle.Normal())
    h_bold = skia.Typeface.MakeFromName("Times", skia.FontStyle.Bold())
    fonts = FontSet(
        fonts.typeface,
        fonts.bold,
        fonts.italic,
        fonts.bold_italic,
        fonts.mono,
        heading_typefaces={2: (h_reg, h_reg, h_bold, h_bold)},
    )
    eff, size = _effective_text_fonts("heading2", 0, fonts, _theme())
    assert size == H2
    assert eff.bold is h_bold and eff.bold_italic is h_bold
    assert eff.typeface is h_reg
    # A piece split off that line resolves the same faces.
    eff2, size2 = _effective_text_fonts("segment", 0, fonts, _theme(), heading_ctx=2)
    assert (eff2.typeface, eff2.bold, size2) == (h_reg, h_bold, H2)
    print("  ✓  bold inside a heading uses the heading family's bold face")


def test_measure_line_uses_the_heading_font():
    # The generator batches a line's pieces at these widths (_flow_rows). Measured
    # as body text, it would pack a row that cannot fit and _layout_row's ratio
    # fallback would clip the heading mid-word.
    # A piece that LOST the heading type in the split (type "segment"): the one
    # whose font can only be resolved through heading_ctx.
    ast = _stamped("### My schedule - [<](/prev) **Today** [>](/next)")
    piece = _by_content(ast, "My schedule")
    assert piece.type == "segment" and piece.heading_ctx == 3, piece.type
    theme, fonts = _theme(), _fonts()
    measure_line = make_line_width_measurer(fonts, theme)
    heading_w = measure_line(piece)
    # Same node, same theme, only the heading context removed — so this isolates
    # the context, not a font-size difference between two themes.
    piece.heading_ctx = 0
    body_w = measure_line(piece)
    piece.heading_ctx = 3
    assert heading_w is not None and body_w is not None
    # H3 is 24 against a 16px body, so the widths must scale with it.
    assert heading_w / body_w > 1.4, (heading_w, body_w)
    # ...and it agrees with the same leaf's minimum-width measurer, which
    # resolves the heading font.
    min_w = make_width_measurer(fonts, theme)(piece)
    assert min_w is not None and heading_w >= min_w
    print("  ✓  measure_line measures a heading piece at the heading font")


def test_measure_line_uses_the_section_text_style():
    # A theme can size the body of a section differently from the root, and the
    # renderer draws a piece there at the section's size (``text_style_chain``).
    # Without the chain, measure_line would measure a line in such a section at
    # the root's body size: the generator would think a row fitted, and the
    # renderer would wrap the text inside it.
    from pathlib import Path

    from md2ui import session

    theme = session.load_theme(Path("data/markdown/tests/THEME.md"))
    fonts = session.load_fonts(theme)
    ast = session.group_markdown(
        "## Artists\n\nAlpha - Bunny\n", session.load_grouping_kit()
    )
    assert ast is not None
    piece = _by_content(ast, "Bunny")
    assert tuple(piece.text_style_chain) == ("root", "heading:2"), (
        piece.text_style_chain
    )
    line_w = make_line_width_measurer(fonts, theme)(piece)
    # One word, so its widest word IS its line: the two measurers must agree.
    assert line_w == make_width_measurer(fonts, theme)(piece), line_w
    # ...and the fixture theme really does size that section apart from the root,
    # or this test would pass with the chain ignored.
    chain, piece.text_style_chain = piece.text_style_chain, ["root"]
    root_w = make_line_width_measurer(fonts, theme)(piece)
    piece.text_style_chain = chain
    assert root_w is not None and line_w is not None and line_w > root_w, (
        line_w,
        root_w,
    )
    print("  ✓  measure_line measures a section's piece at the section's size")


def test_no_leaf_overflows_its_box():
    """End-to-end: no leaf's real text extent may stick out of the box the layout
    gave it, at any width — that overflow IS clipping."""
    from md2ui.pipeline import layout_render as LR
    from md2ui.pipeline.layout_generator import LayoutGenerator

    from layout_line_split_tests import _themed_fonts

    theme, fonts = _themed_fonts()
    # The md, not grouping-ast.json: that file is regenerated from whichever
    # corpus is being worked on, while this one is the same-line/heading corpus.
    src = open("data/markdown/tests/tests-same-line-split.md").read()
    for width in (480.0, 600.0, 768.0, 1280.0):
        ast = _processed_with_criteria(src)
        LR._stamp_heading_ctx(ast)
        node_index: dict = {}
        LR._walk(ast.to_dict(), node_index)
        w = LR._content_width(width)
        layout = LayoutGenerator().generate(
            ast,
            w,
            theme,
            measure=LR.make_layout_measurer(node_index, fonts, theme),
            measure_width=LR.make_width_measurer(fonts, theme),
            measure_line=LR.make_line_width_measurer(fonts, theme),
            measure_marker=LR.make_marker_measurer(fonts, theme),
        )
        RPL.bake_render_cascade(layout)
        height = RMS.natural_height(layout, w, node_index, fonts, theme)
        clipped = []
        for b in RPL.place_boxes(
            layout, 0, 0, w, height, node_index, fonts, theme, section_boxes=[]
        ):
            nd = node_index.get(b.content_id) if b.content_id else None
            if nd is None:
                continue
            rect = RMS._text_extent_rect(b, nd, fonts, theme)
            if rect is None:
                continue
            over = rect.right() - (b.x + b.width)
            if over > 1.0:
                clipped.append(
                    f"+{over:.0f}px {(nd.get('content') or '')[:28]!r} "
                    f"(box {b.width:.0f}, text {rect.width():.0f})"
                )
        assert not clipped, f"at {width:.0f}px:\n   " + "\n   ".join(clipped)
    print("  ✓  no leaf's text overflows its box at 480/600/768/1280")


def test_index_walk_stamps_dicts():
    # The dict path (grouping-ast.json -> node index) stamps the same way.
    root = {
        "node_id": "0",
        "type": "heading2",
        "content": "",
        "source_line_id": 4,
        "children": [
            {
                "node_id": "0.0",
                "type": "segment",
                "content": "Title",
                "source_line_id": 4,
                "children": [],
            },
            {
                "node_id": "0.1",
                "type": "link",
                "content": "[a](/b)",
                "source_line_id": 4,
                "children": [],
            },
            {
                "node_id": "0.2",
                "type": "text",
                "content": "body",
                "source_line_id": 5,
                "children": [],
            },
        ],
    }
    index: dict = {}
    _walk(root, index)
    assert index["0.0"].get("heading_ctx") == 2
    assert index["0.1"].get("heading_ctx", 0) == 0, "link opts out"
    assert index["0.2"].get("heading_ctx", 0) == 0, "other line untouched"
    print("  ✓  load_node_index's walk stamps the same context on dict nodes")


def test_heading_honours_its_own_font_name():
    # A heading block's `Font Name` picks its family, as a ## Tables text style's
    # does; a block that names none keeps the body's (``Text``) family.
    import tempfile
    from pathlib import Path

    from md2ui import session

    fonts_dir = Path("assets/fonts").resolve()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(
            "## Fonts\n"
            f"- {fonts_dir / 'IBMPlexMono-Regular.ttf'}\n"
            f"- {fonts_dir / 'Inter_18pt-Regular.ttf'}\n\n"
            "## Text Styles\n\n"
            "Text\n- Font Name: Inter 18pt\n\n"
            "Heading1\n- Font Name: IBM Plex Mono\n- Font size: 30\n\n"
            "Heading2\n- Font size: 24\n"
        )
        theme = session.load_theme(path)
    fonts = session.load_fonts(theme)
    family = {
        level: faces[0].getFamilyName()
        for level, faces in fonts.heading_typefaces.items()
    }
    assert family[1] == "IBM Plex Mono", family
    assert family[2] == fonts.typeface.getFamilyName() == "Inter 18pt", family
    print("  ✓  a heading draws in its own Font Name; unnamed, in the body's")


TESTS = [
    test_split_heading_pieces_inherit,
    test_links_and_code_leaves_opt_out,
    test_section_body_untouched,
    test_nested_heading_text_element,
    test_kv_on_a_heading_line,
    test_heading_bold_face,
    test_measure_line_uses_the_heading_font,
    test_measure_line_uses_the_section_text_style,
    test_no_leaf_overflows_its_box,
    test_index_walk_stamps_dicts,
    test_heading_honours_its_own_font_name,
]

if __name__ == "__main__":
    print("Layout Heading-Style Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
