"""Code blocks survive grouping as opaque leaves and render from THEME.md.

Run with: uv run python tests/code_block_tests.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import skia

from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.grouper_code_blocks import extract_code_blocks
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_render import make_block_width_measurer
from md2ui.pipeline.markdown_grouper import MarkdownGrouper
from md2ui.pipeline.render_fills import _paint_layered_fill
from md2ui import session
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_code_blocks import (
    code_block_plan,
    copy_button_rect,
    copy_button_size,
    draw_code_block,
    highlighted_lines,
    lines_that_fit,
)
from md2ui.pipeline.theme import Theme, parse_theme
from md2ui.pipeline.theme_model import CodeBlockTheme


def _walk(node: MarkdownGroupNode):
    yield node
    for child in node.children:
        yield from _walk(child)


def _code_nodes(markdown: str) -> list[MarkdownGroupNode]:
    grouped = MarkdownGrouper(markdown).process()
    assert grouped.ast is not None
    return [node for node in _walk(grouped.ast) if node.type == NodeType.CODE_BLOCK]


def test_fenced_code_is_opaque_and_keeps_language():
    nodes = _code_nodes(
        "# Before\n\n```python\n# not a heading\nvalue = **literal**\n```\n\n# After"
    )
    assert len(nodes) == 1
    assert nodes[0].content == "# not a heading\nvalue = **literal**\n"
    assert nodes[0].code_language == "python"
    assert not nodes[0].children
    print("  ✓  a fenced block is one opaque leaf with its language")


def test_tilde_fence_and_class_info_string():
    nodes = _code_nodes("~~~{.typescript}\nconst answer = 42;\n~~~")
    assert len(nodes) == 1
    assert nodes[0].code_language == "typescript"
    print("  ✓  tilde fences and {.language} info strings are accepted")


def test_fenced_code_inside_list_item():
    grouped = MarkdownGrouper(
        "- ```md\n  <!-- Background image: hero.png -->\n  ```\n"
    ).process()
    assert grouped.ast is not None
    items = [node for node in _walk(grouped.ast) if node.type == NodeType.LIST_ITEM]
    assert len(items) == 1
    assert len(items[0].children) == 1
    code = items[0].children[0]
    assert code.type == NodeType.CODE_BLOCK
    assert code.code_language == "md"
    assert code.content == "<!-- Background image: hero.png -->\n"
    print("  ✓  a fenced block nested in a list remains nested code")


def test_indented_code_is_preserved():
    nodes = _code_nodes("Intro\n\n    total = 1\n    print(total)\n\nOutro")
    assert len(nodes) == 1
    assert nodes[0].content == "total = 1\nprint(total)\n"
    assert nodes[0].code_language is None
    print("  ✓  a genuine indented block becomes plain code")


def test_indentation_inside_html_comments_is_not_code():
    source = (
        "<!-- description\n\n     aligned continuation\n\n     still a comment -->\n"
    )
    protected, specs = extract_code_blocks(source)
    assert protected == source
    assert not specs
    nodes = _code_nodes(source)
    assert not nodes
    print("  ✓  indentation inside an HTML comment remains comment content")


def test_whitespace_only_line_is_not_code():
    assert not _code_nodes("Before\n\n     \nAfter\n")
    print("  ✓  whitespace-only indentation is not a code block")


def test_code_metadata_round_trips():
    node = _code_nodes('```json\n{"ok": true}\n```')[0]
    restored = MarkdownGroupNode.from_dict(node.to_dict())
    assert restored.type == NodeType.CODE_BLOCK
    assert restored.content == node.content
    assert restored.code_language == "json"
    print("  ✓  code language survives to_dict/from_dict")


def test_theme_parses_code_block_font_and_surface():
    source = """## Text Styles
Code Block
- Font Name: IBM Plex Mono
- Font size: 15
- Font color: #DDEEFF

## Code Blocks
Syntax style: monokai
Background color: #112233
Corner radius: 9
Padding top: 10
Padding right: 11
Padding bottom: 12
Padding left: 13
Line spacing: 5
"""
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "THEME.md"
        path.write_text(source)
        theme = parse_theme(path)
    block = theme.code_blocks
    assert block.text_style.font_name == "IBM Plex Mono"
    assert block.text_style.font_size == 15
    assert block.text_style.color == 0xFFDDEEFF
    assert block.syntax_style == "monokai"
    assert block.background_color == 0xFF112233
    assert block.corner_radius == 9
    assert (block.padding.top, block.padding.right) == (10, 11)
    assert (block.padding.bottom, block.padding.left) == (12, 13)
    assert block.line_spacing == 5
    print("  ✓  Code Block typography and ## Code Blocks paint parse independently")


def test_python_highlighting_has_multiple_colors():
    lines = highlighted_lines(
        "def greet(name):\n    return f'Hello {name}'",
        "python",
        "monokai",
        0xFFFFFFFF,
    )
    colors = {run.color for line in lines for run in line}
    assert len(lines) == 2
    assert len(colors) >= 3, colors
    plain = highlighted_lines("not syntax", "unknown-language", "monokai", 0xFFABCDEF)
    assert {run.color for line in plain for run in line} == {0xFFABCDEF}
    print("  ✓  known languages highlight; unknown languages stay plain")


def test_measurement_preserves_rows_and_padding():
    block = CodeBlockTheme()
    block.text_style.font_size = 14
    block.line_spacing = 6
    face = skia.Typeface.MakeFromName("Arial")
    assert face is not None
    plan = code_block_plan("short\nlonger line\n", "python", face, block)
    assert len(plan.lines) == 2
    assert plan.width > block.padding.x
    assert plan.height > block.padding.y
    assert plan.line_height > block.text_style.font_size
    print("  ✓  shared code plan measures multiline source and padding")


def test_theme_parses_min_width_and_fade():
    assert (CodeBlockTheme().min_width, CodeBlockTheme().fade) == (320.0, True)
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "THEME.md"
        path.write_text("## Code Blocks\nMin width: 240\nFade: no\n")
        block = parse_theme(path).code_blocks
    assert (block.min_width, block.fade) == (240.0, False)
    print("  ✓  Min width and Fade parse under ## Code Blocks")


def test_a_block_with_room_is_never_clipped():
    """The ``Min width`` cap is the PAGE floor only: arrangement still sees each
    block's whole width, so sections holding code do not grid into columns that
    would clip code the page has room to show whole."""
    doc = Path("data/markdown/tests/code-blocks.md").read_text()
    theme = session.load_theme(Path("data/markdown/tests/THEME.md"))
    fonts = session.load_fonts(theme)
    grouped = session.group_markdown(doc, session.load_grouping_kit())
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 1280.0)
    face = fonts.code_block or fonts.mono or fonts.typeface
    for box in scene.boxes:
        nd = index.get(box.content_id, {})
        if nd.get("type") == "code_block":
            plan = code_block_plan(
                nd["content"], nd.get("code_language"), face, theme.code_blocks
            )
            assert box.width >= plan.width - 0.5, (box.width, plan.width)
    print("  ✓  a code block the page has room for keeps its whole width")


def test_a_long_code_line_does_not_widen_the_page():
    doc = "Intro text.\n\n```\n" + "curl https://api.example.com " * 12 + "\n```\n"
    theme = session.load_theme(None)
    fonts = session.load_fonts(theme)
    grouped = session.group_markdown(doc, session.load_grouping_kit())
    assert grouped is not None
    root, _index = session.prepare(grouped, theme)
    width = session.effective_width(root, theme, fonts, 520.0)
    assert width <= 520.0, width
    print("  ✓  a long code line clips instead of widening the page")


def _right_edge_pixel(fade: bool) -> int:
    block = CodeBlockTheme(fade=fade)
    block.text_style.color = 0xFF000000
    block.background_color = 0xFFFFFFFF
    face = skia.Typeface.MakeDefault()
    surface = skia.Surface(300, 60)
    canvas = surface.getCanvas()
    canvas.clear(0xFFFFFFFF)
    box = LayoutBox(x=0.0, y=0.0, width=300.0, height=60.0)
    draw_code_block(
        canvas,
        box,
        "█" * 200,
        None,
        face,
        Theme(code_blocks=block),
        paint_fill=_paint_layered_fill,
    )
    plan = code_block_plan("█" * 200, None, face, block)
    y = int(plan.baseline - block.text_style.font_size / 2)
    return surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[
        y, 299
    ][0]


def test_a_clipped_line_fades_into_the_background():
    """With ``Fade`` the clipped edge is the block's background; without it the
    code runs to the edge."""
    assert _right_edge_pixel(fade=True) > 240
    assert _right_edge_pixel(fade=False) < 60
    print("  ✓  the clipped right edge fades into the background")


def test_theme_parses_max_lines():
    assert CodeBlockTheme().max_lines == 20
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "THEME.md"
        for val, want in (("8", 8), ("none", None)):
            path.write_text(f"## Code Blocks\nMax lines: {val}\n")
            assert parse_theme(path).code_blocks.max_lines == want, val
    print("  ✓  Max lines parses under ## Code Blocks, and none turns it off")


def test_an_unusable_max_lines_is_dropped():
    # `inf` and `1e999` are numbers no line count can be; like any bad value
    # they leave the default in place instead of failing the whole theme.
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "THEME.md"
        for val in ("inf", "1e999", "nan", "0", "seven"):
            path.write_text(f"## Code Blocks\nMax lines: {val}\n")
            assert parse_theme(path).code_blocks.max_lines == 20, val
    print("  ✓  an unusable Max lines value is dropped, never a crash")


def _source(n: int) -> str:
    return "\n".join(f"line_{i} = {i}" for i in range(n))


def test_a_block_is_capped_at_max_lines():
    """A block is at most ``Max lines`` tall, cut at a line boundary; the plan
    keeps the full height so the paint knows there is more."""
    block = CodeBlockTheme()
    face = skia.Typeface.MakeDefault()
    twenty = code_block_plan(_source(20), None, face, block)
    forty = code_block_plan(_source(40), None, face, block)
    ten = code_block_plan(_source(10), None, face, block)
    assert forty.height == twenty.height == twenty.full_height
    assert forty.full_height > forty.height
    assert ten.height == ten.full_height < twenty.height
    assert lines_that_fit(forty, forty.height, block) == 20
    assert lines_that_fit(forty, forty.height + forty.line_height, block) == 21
    assert lines_that_fit(ten, 10_000.0, block) == 10
    block.max_lines = None
    assert code_block_plan(_source(40), None, face, block).height == forty.full_height
    print("  ✓  a block is capped at Max lines, and none shows every line")


def _bottom_edge_pixel(fade: bool) -> int:
    block = CodeBlockTheme(fade=fade)
    block.text_style.color = 0xFF000000
    block.background_color = 0xFFFFFFFF
    face = skia.Typeface.MakeDefault()
    source = "\n".join("█" * 10 for _ in range(40))
    plan = code_block_plan(source, None, face, block)
    surface = skia.Surface(200, int(plan.height))
    canvas = surface.getCanvas()
    canvas.clear(0xFFFFFFFF)
    box = LayoutBox(x=0.0, y=0.0, width=200.0, height=plan.height)
    draw_code_block(
        canvas,
        box,
        source,
        None,
        face,
        Theme(code_blocks=block),
        paint_fill=_paint_layered_fill,
    )
    # Inside the last line shown, just above where its glyphs end.
    x = int(block.padding.left + 4)
    y = int(plan.height - block.padding.bottom) - 2
    return surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[
        y, x
    ][0]


def test_a_capped_block_fades_at_the_bottom():
    """The last visible lines of a capped block fade into its background."""
    assert _bottom_edge_pixel(fade=True) > 240
    assert _bottom_edge_pixel(fade=False) < 60
    print("  ✓  a capped block fades into the background at its bottom edge")


def _row_boxes(doc: str) -> tuple:
    theme = session.load_theme(Path("data/markdown/tests/THEME.md"))
    fonts = session.load_fonts(theme)
    grouped = session.group_markdown(doc, session.load_grouping_kit())
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 1100.0)
    code = [
        b
        for b in scene.boxes
        if index.get(b.content_id, {}).get("type") == "code_block"
    ]
    text = [
        b
        for b in scene.boxes
        if index.get(b.content_id, {}).get("type") not in ("code_block", None)
    ]
    assert len(code) == 1 and text, (code, text)
    return code[0], text, theme, fonts


def test_a_code_cell_fills_its_row():
    """Beside a taller cell a code block takes the row's height, so its surface
    lines up with its neighbour; beside a shorter one it keeps its own (capped)
    height and sets the row's."""
    prose = "A paragraph long enough to wrap onto several lines beside the code. " * 5
    # Weighted so the prose's drawn share still holds its wrapping floor, or
    # the line would not keep it beside the code (a cell wraps below it).
    short = f"```\nok = True\n```\n:::1\n{prose}\n:::2\n___\n"
    code, text, _t, _f = _row_boxes(short)
    bottom = max(b.y + b.height for b in text)
    assert abs((code.y + code.height) - bottom) < 1.0, (code, bottom)
    tall = f"```\n{_source(40)}\n```\n:::1\nA short neighbour.\n:::1\n___\n"
    code, text, theme, fonts = _row_boxes(tall)
    face = fonts.code_block or fonts.mono or fonts.typeface
    plan = code_block_plan(_source(40), None, face, theme.code_blocks)
    assert abs(code.height - plan.height) < 1.0, (code.height, plan.height)
    assert text[0].x >= code.x + code.width, (code, text[0])  # side by side
    print("  ✓  a code cell fills its row, and a tall one is capped at Max lines")


_BUTTON_THEME = """## Code Blocks
### Copy Button
Icon: ✂️
Icon size: 18
Fill color: #FF0000
Corner radius: 3
Padding: 5
"""


def test_theme_parses_the_copy_button():
    """``### Copy Button`` takes a button variant's keys plus ``Icon`` and
    ``Icon size``; ``Icon: none`` removes it."""
    default = CodeBlockTheme()
    assert (default.copy_icon, default.copy_icon_size) == ("📋", 14.0)
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "THEME.md"
        path.write_text(_BUTTON_THEME)
        block = parse_theme(path).code_blocks
        path.write_text("## Code Blocks\n### Copy Button\nIcon: none\n")
        hidden = parse_theme(path).code_blocks
    button = block.copy_button
    assert (block.copy_icon, block.copy_icon_size) == ("✂️", 18.0)
    assert button.fill_color == 0xFFFF0000 and button.corner_radius == 3
    assert button.padding is not None and button.padding.left == 5
    assert hidden.copy_icon is None
    print("  ✓  ### Copy Button parses its style, icon and size; none removes it")


def test_the_copy_button_heads_the_block():
    """The button sits in a header strip above the code, so it never covers a
    line; without it the block is exactly as tall as before."""
    face = skia.Typeface.MakeDefault()
    on = CodeBlockTheme()
    off = CodeBlockTheme(copy_icon=None)
    with_button = code_block_plan(_source(3), None, face, on)
    without = code_block_plan(_source(3), None, face, off)
    side = copy_button_size(on)
    assert with_button.header == side + on.line_spacing
    assert without.header == 0.0
    assert with_button.height == without.height + with_button.header
    assert with_button.baseline == without.baseline + with_button.header
    box = LayoutBox(x=10.0, y=20.0, width=300.0, height=with_button.height)
    x, y, w, h = copy_button_rect(box, on)
    assert (w, h) == (side, side)
    assert x + w == box.x + box.width - on.padding.right
    assert y == box.y + on.padding.top
    print("  ✓  the copy button sits in a header strip at the top right")


def test_the_copy_button_reports_a_copy_action():
    """A click on the button reports the block's whole source, at the rectangle
    the button is painted in (ADR-404)."""
    source = "curl https://api.example.com " * 12
    theme = session.load_theme(Path("data/markdown/tests/THEME.md"))
    fonts = session.load_fonts(theme)
    grouped = session.group_markdown(
        f"```\n{source}\n```\n", session.load_grouping_kit()
    )
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 520.0)
    box = next(
        b
        for b in scene.boxes
        if index.get(b.content_id, {}).get("type") == "code_block"
    )
    (region,) = [r for r in scene.regions if r.action.kind == "copy"]
    assert (region.x, region.y, region.width, region.height) == copy_button_rect(
        box, theme.code_blocks
    )
    assert region.action.text == source
    assert region.action.to_dict()["text"] == source
    print("  ✓  the copy button reports the block's source as a copy action")


def test_the_copy_button_is_painted_in_its_style():
    """The button's fill comes from ``### Copy Button``, painted where its
    region is."""
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "THEME.md"
        path.write_text(_BUTTON_THEME)
        block = parse_theme(path).code_blocks
    block.background_color = 0xFFFFFFFF
    face = skia.Typeface.MakeDefault()
    plan = code_block_plan("ok = True", None, face, block)
    surface = skia.Surface(300, int(plan.height) + 1)
    canvas = surface.getCanvas()
    canvas.clear(0xFFFFFFFF)
    box = LayoutBox(x=0.0, y=0.0, width=300.0, height=plan.height)
    draw_code_block(
        canvas,
        box,
        "ok = True",
        None,
        face,
        Theme(code_blocks=block),
        paint_fill=_paint_layered_fill,
    )
    x, y, _w, h = copy_button_rect(box, block)
    # Inside the button's padding, clear of the icon.
    r, g, b, _a = surface.makeImageSnapshot().toarray(
        colorType=skia.kRGBA_8888_ColorType
    )[int(y + h / 2), int(x + 2)]
    assert (r, g, b) == (255, 0, 0), (r, g, b)
    print("  ✓  the copy button is painted in its own style")


def test_a_clipped_block_is_scrollable():
    """The scene lists each block clipped at its right edge, with the box it is
    drawn in and the width of its content; a block that fits is not listed."""
    long = "curl https://api.example.com " * 12
    doc = f"```\n{long}\n```\n\nBetween.\n\n```\nok = True\n```\n"
    theme = session.load_theme(Path("data/markdown/tests/THEME.md"))
    fonts = session.load_fonts(theme)
    grouped = session.group_markdown(doc, session.load_grouping_kit())
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 520.0)
    (scroll,) = scene.scrollables
    box = next(
        b
        for b in scene.boxes
        if b.content_id and index[b.content_id].get("node_id") == scroll.node_id
    )
    assert (scroll.x, scroll.y, scroll.width, scroll.height) == (
        box.x,
        box.y,
        box.width,
        box.height,
    )
    face = fonts.code_block or fonts.mono or fonts.typeface
    plan = code_block_plan(long, None, face, theme.code_blocks)
    assert scroll.content_width == plan.width
    assert scroll.max_offset == plan.width - box.width > 0
    print("  ✓  a clipped block is listed as scrollable; one that fits is not")


def _texts(source: str, language: str | None) -> list[str]:
    rows = highlighted_lines(source, language, "default", 0xFF000000)
    return ["".join(run.text for run in row) for row in rows]


def test_a_session_lexer_keeps_the_last_line():
    """Shell-session lexers only emit a line once they see its newline; the
    last source line has none, and must still be drawn."""
    for language in ("console", "shell-session", "doscon", "ps1con", "tcshcon"):
        assert _texts("$ gem install rake", language) == ["$ gem install rake"]
        two = "$ gem install rake\nSuccessfully installed rake"
        assert _texts(two, language) == two.split("\n"), language
    print("  ✓  a shell-session block keeps its last line")


def test_authored_blank_lines_survive_highlighting():
    """Only the newline the lexer needs is added and taken back: a blank line
    the author wrote at either end stays a row."""
    assert _texts("\nx = 1\n\n", "python") == ["", "x = 1", ""]
    assert _texts("x = 1", "python") == ["x = 1"]
    print("  ✓  authored blank lines survive highlighting")


def test_a_token_the_style_does_not_list_takes_its_parent_colour():
    """YAML (and a few other lexers) emit token subtypes a style does not
    list; the colour comes from the nearest listed parent instead of raising."""
    rows = highlighted_lines("name: md2ui\nversion: 1", "yaml", "monokai", 0xFFFFFFFF)
    assert ["".join(r.text for r in row) for row in rows] == [
        "name: md2ui",
        "version: 1",
    ]
    for language in ("yaml", "prolog", "solidity"):
        highlighted_lines("a: 1\nb = 2", language, "default", 0xFF000000)
    print("  ✓  an unlisted token subtype takes its parent's colour")


_STACK_ASK = Path("data/markdown/tests/code-block-stack-ask")


def test_a_code_block_asks_stack_sections_for_its_drawn_width():
    """``Stack sections`` decides with the width a code block draws, not with its
    widest word in the body face: the block-width measurer answers the plan's
    width, so at 767 the ``Install`` band does not pack beside ``Notes``."""
    theme = session.load_theme(_STACK_ASK / "THEME.md")
    fonts = session.load_fonts(theme)
    grouped = session.group_markdown(
        (_STACK_ASK / "content.md").read_text(), session.load_grouping_kit()
    )
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 767.0)
    stack, code = [scene.layout], []
    while stack:
        n = stack.pop()
        stack.extend(n.children or [])
        if index.get(n.content_id or "", {}).get("type") == "code_block":
            code.append(n)
    assert len(code) == 1, code
    nd = index[code[0].content_id]
    face = fonts.code_block or fonts.mono or fonts.typeface
    plan = code_block_plan(
        nd["content"], nd.get("code_language"), face, theme.code_blocks
    )
    asked = make_block_width_measurer(index, fonts, theme)(code[0], 10000.0)
    assert abs(asked - plan.width) < 0.01, (asked, plan.width)
    box = next(b for b in scene.boxes if b.content_id == code[0].content_id)
    note = next(
        b
        for b in scene.boxes
        if "once per" in index.get(b.content_id, {}).get("content", "")
    )
    assert note.y >= box.y + box.height, (box, note)  # stacked, not side by side
    print("  ✓  a code block asks Stack sections for its drawn width")


TESTS = [
    test_fenced_code_is_opaque_and_keeps_language,
    test_tilde_fence_and_class_info_string,
    test_fenced_code_inside_list_item,
    test_indented_code_is_preserved,
    test_indentation_inside_html_comments_is_not_code,
    test_whitespace_only_line_is_not_code,
    test_code_metadata_round_trips,
    test_theme_parses_code_block_font_and_surface,
    test_python_highlighting_has_multiple_colors,
    test_measurement_preserves_rows_and_padding,
    test_theme_parses_min_width_and_fade,
    test_a_block_with_room_is_never_clipped,
    test_a_long_code_line_does_not_widen_the_page,
    test_a_clipped_line_fades_into_the_background,
    test_theme_parses_max_lines,
    test_an_unusable_max_lines_is_dropped,
    test_a_block_is_capped_at_max_lines,
    test_a_capped_block_fades_at_the_bottom,
    test_a_code_cell_fills_its_row,
    test_a_code_block_asks_stack_sections_for_its_drawn_width,
    test_theme_parses_the_copy_button,
    test_the_copy_button_heads_the_block,
    test_the_copy_button_reports_a_copy_action,
    test_the_copy_button_is_painted_in_its_style,
    test_a_clipped_block_is_scrollable,
    test_a_session_lexer_keeps_the_last_line,
    test_authored_blank_lines_survive_highlighting,
    test_a_token_the_style_does_not_list_takes_its_parent_colour,
]


if __name__ == "__main__":
    print("Code Block Tests")
    print("=" * 50)
    for test in TESTS:
        test()
    print("=" * 50)
    print(f"All {len(TESTS)} tests passed.")
