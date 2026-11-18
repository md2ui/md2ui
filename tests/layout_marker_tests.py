"""
Unit tests for list/quote markers: background-level style selection, placement,
alignment, sizing, color rotation, and which ordinal is drawn (it comes from the
document — a run starts at the number the author wrote and counts up).
Run with: uv run python tests/layout_marker_tests.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import skia

from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.grouper_block_splits import _split_all_lists, _split_blockquote
from md2ui.pipeline.generator_markers import (
    build_marker_props,
    marker_gutter_x,
    marker_style,
    numbered_style,
)
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_render import _draw_list_marker
from md2ui.pipeline.layout_script_parser import LayoutBox, LayoutNode
from md2ui.pipeline.markdown_grouper import (
    MarkdownGroupNode,
    MarkdownGrouper,
    NodeType,
)
from md2ui.pipeline.render_measure import (
    _leaf_height,
    _leaf_natural_width,
    _row_valign_offsets,
    first_baseline,
)
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import (
    BulletedListStyle,
    NumberedListStyle,
    QuoteStyle,
    SectionStyle,
    TextStyle,
    Theme,
    parse_theme,
)


def _grouped(md: str) -> MarkdownGrouper:
    """Group *md* far enough to mint list items and stamp their ordinals."""
    g = MarkdownGrouper(md)
    g.to_ast()
    g.subgroup_by_blank_lines()
    assert g.ast is not None
    g._subgroup_content_classified_multi(g.ast, [_split_all_lists, _split_blockquote])
    g._stamp_list_ordinals(g.ast)
    return g


def _items(g: MarkdownGrouper) -> list:
    out: list = []

    def walk(n):
        if n.type == NodeType.ORDERED_ITEM:
            out.append(n)
        for c in n.children:
            walk(c)

    walk(g.ast)
    return out


def _ordinals(md: str) -> list[int]:
    return [n.list_ordinal for n in _items(_grouped(md))]


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _layout(markdown: str, theme: Theme) -> LayoutNode:
    grouper = MarkdownGrouper(markdown)
    grouper.process(criteria=None, detector=DataPointDetector())
    assert grouper.ast is not None
    return LayoutGenerator().generate(grouper.ast, 800.0, theme)


def _marker_parent(layout: LayoutNode) -> LayoutNode:
    return next(
        node
        for node in _walk(layout)
        if any(
            (child.render_properties or {}).get("list_marker")
            for child in node.children
        )
    )


def _fonts() -> FontSet:
    face = skia.Typeface.MakeDefault()
    return FontSet(face, face, face, face, face)


# ---------------------------------------------------------------------------
# Ordinals
# ---------------------------------------------------------------------------


def test_heading_items_keep_their_own_number():
    """Each `## N. …` heading splits into a lone ordered item under its own
    heading node — a run of one — so it must keep the author's number instead of
    every heading in the document rendering "1"."""
    md = (
        "# Top\n\n## 1. **Alpha**\n\nbody a\n\n## 2. **Beta**\n\nbody b\n\n"
        "## 10. **Kappa**\n\nbody k\n"
    )
    assert _ordinals(md) == [1, 2, 10], _ordinals(md)
    print("  ✓  heading ordinals: 1, 2, 10 (not 1, 1, 1)")


def test_run_seeds_from_the_first_number():
    """CommonMark: only the first number of a list counts, the rest is a running
    counter — so a list written 1./1./1. still renders 1,2,3."""
    assert _ordinals("# L\n\n1. Alpha\n1. Beta\n1. Gamma\n") == [1, 2, 3]
    assert _ordinals("# L\n\n3. Third\n4. Fourth\n") == [3, 4]
    assert _ordinals("# L\n\n5. Five\n9. Nine\n") == [5, 6]
    print("  ✓  a run seeds at its first number, then counts up")


def test_non_ordered_sibling_resets_the_run():
    md = "# L\n\n1. One\n2. Two\n\nsome prose\n\n7. Seven\n8. Eight\n"
    assert _ordinals(md) == [1, 2, 7, 8], _ordinals(md)
    print("  ✓  a non-ordered sibling ends the run (next run re-seeds)")


def test_source_number_is_kept_on_the_node():
    """The `1. ` marker is stripped from the text, so the number has to survive
    as its own field or it is gone for good."""
    items = _items(_grouped("# L\n\n4. Fourth\n5. Fifth\n"))
    assert [n.list_number for n in items] == [4, 5]
    assert all("4." not in (n.content or "") for n in items)
    print("  ✓  the author's number survives on list_number")


# ---------------------------------------------------------------------------
# Heading annotation + style selection
# ---------------------------------------------------------------------------


def test_heading_level_annotation():
    heading = _items(_grouped("# Top\n\n## 3. **Gamma**\n\nbody\n"))
    plain = _items(_grouped("# L\n\n1. Alpha\n2. Beta\n"))
    assert [n.list_heading_level for n in heading] == [2], heading[0].list_heading_level
    assert [n.list_heading_level for n in plain] == [None, None]
    print("  ✓  list_heading_level: 2 for a heading ordinal, None for a list one")


def _theme(*, plain: bool, headings: bool) -> Theme:
    t = Theme()
    if plain:
        t.numbered_lists.marker = NumberedListStyle(
            text_style=TextStyle(font_size=28.0), space=16.0
        )
    if headings:
        t.sections[2] = SectionStyle(
            marker=NumberedListStyle(text_style=TextStyle(font_size=64.0), space=32.0)
        )
    return t


def _node(heading_level):
    n = MarkdownGroupNode(type=NodeType.ORDERED_ITEM, content="Alpha")
    n.list_heading_level = heading_level
    return n


def test_style_selection():
    both = _theme(plain=True, headings=True)
    heading_style = numbered_style(_node(2), both).text_style
    assert heading_style is not None
    assert heading_style.font_size == 64.0
    plain_style = numbered_style(_node(None), both).text_style
    assert plain_style is not None
    assert plain_style.font_size == 28.0
    print("  ✓  heading ordinal → 64, plain ordinal → 28")


def test_numbered_marker_styles_do_not_cross_background_levels():
    """Plain lists and each heading level own their marker independently."""
    only_plain = _theme(plain=True, headings=False)
    assert not numbered_style(_node(2), only_plain).is_active()
    only_headings = _theme(plain=False, headings=True)
    assert not numbered_style(_node(None), only_headings).is_active()
    neither = _theme(plain=False, headings=False)
    assert not numbered_style(_node(2), neither).is_active()
    print("  ✓  numbered marker styles stay on their exact background level")


def test_task_marker_falls_back_to_unordered_marker():
    theme = Theme()
    inherited = BulletedListStyle(shape="circle")
    theme.unordered_lists.marker = inherited
    task = MarkdownGroupNode(type=NodeType.TASK_OPEN, content="open")
    assert marker_style(task, theme) is inherited

    own = BulletedListStyle(shape="square")
    theme.task_lists.marker = own
    assert marker_style(task, theme) is own
    print("  ✓  task markers override, then fall back to Unordered Lists")


def test_old_top_level_marker_sections_are_not_parsed():
    with TemporaryDirectory() as td:
        path = Path(td) / "THEME.md"
        path.write_text(
            """## Emoji lists
### Bulleted lists
Shape: square
### Numbered lists
Font size: 20
## Quotes
### Blockquotes
Bar width: 4
Bar color: #112233
""",
            encoding="utf-8",
        )
        theme = parse_theme(path)
    assert theme.unordered_lists.marker is None
    assert theme.numbered_lists.marker is None
    assert theme.quotes.marker is None
    print("  ✓  removed top-level marker sections have no effect")


def test_gutter_color_lists_parse_and_rotate_per_marker():
    """All painted gutter kinds use their item's structural rotation slot."""
    with TemporaryDirectory() as td:
        path = Path(td) / "THEME.md"
        path.write_text(
            """## Background styles and Spacing
### Unordered Lists
#### Marker
Shape: square
Color:
- #11AA22
- #3344CC
### Numbered lists
#### Marker
Font color:
- #11AA22
- #3344CC
### Quotes
#### Marker
Bar width: 4
Bar color:
- #11AA22
- #3344CC
""",
            encoding="utf-8",
        )
        theme = parse_theme(path)

    bullet = theme.unordered_lists.marker
    quote = theme.quotes.marker
    numbered = theme.numbered_lists.marker
    assert isinstance(bullet, BulletedListStyle)
    assert isinstance(quote, QuoteStyle)
    assert isinstance(numbered, NumberedListStyle)
    assert bullet.color == bullet.colors[0]
    assert quote.bar_color == quote.bar_colors[0]
    assert numbered.text_style is not None
    assert numbered.text_style.color == numbered.text_style.colors[0]

    expected = [bullet.colors[i] for i in (0, 1, 0)]
    for kind in (NodeType.LIST_ITEM, NodeType.ORDERED_ITEM, NodeType.BLOCKQUOTE):
        actual = []
        for index in (0, 1, 2):
            node = MarkdownGroupNode(type=kind, content="row")
            node.rotation_index = index
            node.list_ordinal = index + 1
            props = build_marker_props(node, theme)
            assert props is not None
            actual.append(props["color"])
        assert actual == expected
    print("  ✓  bullet, ordinal, and quote-bar colors rotate per gutter marker")


# ---------------------------------------------------------------------------
# Placement, alignment, and quote-bar geometry
# ---------------------------------------------------------------------------


def test_marker_position_fields_parse_and_default():
    with TemporaryDirectory() as td:
        path = Path(td) / "THEME.md"
        path.write_text(
            """## Background styles and Spacing
### Unordered Lists
#### Marker
Shape: circle
Aside: no
Alignment: bottom
### Numbered Lists
#### Marker
Font size: 28
### Quotes
#### Marker
Bar width: 4
Bar length: 88
Bar color: #112233
Aside: false
Alignment: center
""",
            encoding="utf-8",
        )
        theme = parse_theme(path)

    bullet = theme.unordered_lists.marker
    number = theme.numbered_lists.marker
    quote = theme.quotes.marker
    assert isinstance(bullet, BulletedListStyle)
    assert isinstance(number, NumberedListStyle)
    assert isinstance(quote, QuoteStyle)
    assert (bullet.aside, bullet.alignment) == (False, "bottom")
    assert (number.aside, number.alignment) == (True, "top")
    assert (quote.aside, quote.alignment, quote.bar_length) == (False, "center", 88)
    defaults = (BulletedListStyle(), NumberedListStyle(), QuoteStyle())
    assert all((style.aside, style.alignment) == (True, "top") for style in defaults)
    assert QuoteStyle().bar_length == 50.0
    print("  ✓  Aside/Alignment/Bar length parse; defaults remain aside + top + 50")


def test_aside_switches_between_row_and_above_column():
    theme = Theme()
    theme.unordered_lists.marker = BulletedListStyle(shape="circle")
    aside = _marker_parent(_layout("- bullet", theme))
    assert aside.type == "row"
    assert aside.render_properties == {"marker_align": "top"}

    theme.unordered_lists.marker.aside = False
    above = _marker_parent(_layout("- bullet", theme))
    assert above.type == "col"
    assert (above.children[0].render_properties or {})["list_marker"]["aside"] is False
    print("  ✓  Aside yes → marker row; Aside no → left-origin marker above content")


def test_above_marker_does_not_reserve_a_horizontal_gutter():
    theme = Theme()
    theme.unordered_lists.marker = BulletedListStyle(
        shape="square", size=9.0, space=13.0, aside=False
    )
    node = MarkdownGroupNode(type=NodeType.LIST_ITEM, content="body")
    assert marker_gutter_x(node, theme) == 0.0
    theme.unordered_lists.marker.aside = True
    assert marker_gutter_x(node, theme) == 22.0
    print("  ✓  only an aside marker contributes to horizontal minimum width")


def _marker_offsets(mode: str, marker: dict, heights=(16.0, 60.0)) -> tuple:
    marker_leaf = LayoutNode(
        type="-",
        ratios=[],
        children=[],
        render_properties={"list_marker": marker},
    )
    body_leaf = LayoutNode(type="-", ratios=[], children=[], content_id="body")
    body = LayoutNode(type="col", ratios=[1.0], children=[body_leaf])
    row = LayoutNode(
        type="row",
        ratios=[1.0, 1.0],
        children=[marker_leaf, body],
        render_properties={"marker_align": mode},
    )
    offsets = _row_valign_offsets(
        row,
        row.children,
        [20.0, 200.0],
        list(heights),
        [False, False],
        {"body": {"type": "text", "content": "body"}},
        _fonts(),
        Theme(),
    )
    return offsets, marker_leaf, body


def test_marker_alignment_uses_the_whole_item_body():
    marker = {
        "kind": "bullet",
        "shape": "circle",
        "size": 8.0,
        "aside": True,
    }
    assert _marker_offsets("top", marker)[0] == [0.0, 0.0]
    assert _marker_offsets("center", marker)[0] == [22.0, 0.0]
    assert _marker_offsets("bottom", marker)[0] == [44.0, 0.0]
    print("  ✓  top/center/bottom align against the full item-body height")


def test_marker_baseline_uses_the_item_bodys_first_line():
    marker = {
        "kind": "bullet",
        "shape": "circle",
        "size": 8.0,
        "aside": True,
    }
    offsets, marker_leaf, body = _marker_offsets("baseline", marker)
    marker_base = first_baseline(marker_leaf, 20.0, {}, _fonts(), Theme())
    body_base = first_baseline(
        body,
        200.0,
        {"body": {"type": "text", "content": "body"}},
        _fonts(),
        Theme(),
    )
    assert marker_base is not None and body_base is not None
    assert abs(offsets[0] + marker_base - (offsets[1] + body_base)) < 1e-6
    assert offsets[0] > 0.0
    print("  ✓  baseline aligns the marker with a multi-line body's first line")


class _RectCanvas:
    def __init__(self):
        self.rect = None

    def drawRect(self, rect, _paint):
        self.rect = rect


def test_quote_bar_turns_horizontal_above_the_body():
    props = {
        "kind": "quote",
        "mode": "bar",
        "bar_width": 4.0,
        "bar_length": 50.0,
        "color": 0xFF112233,
        "size": 4.0,
        "aside": False,
    }
    assert _leaf_height(None, 200.0, _fonts(), Theme(), {"list_marker": props}) == 4.0
    assert (
        _leaf_natural_width(None, 200.0, _fonts(), Theme(), {"list_marker": props})
        == 50.0
    )
    canvas = _RectCanvas()
    _draw_list_marker(
        canvas,
        LayoutBox(10.0, 20.0, 200.0, 80.0),
        props,
        _fonts(),
        Theme(),
    )
    assert canvas.rect is not None
    assert (canvas.rect.left(), canvas.rect.top()) == (10.0, 20.0)
    assert (canvas.rect.width(), canvas.rect.height()) == (50.0, 4.0)
    print("  ✓  an above quote bar is horizontal, 50px long, and thickness-high")


def test_vertical_quote_bar_stretches_and_ignores_alignment():
    marker = {
        "kind": "quote",
        "mode": "bar",
        "bar_width": 4.0,
        "size": 4.0,
        "aside": True,
    }
    offsets, _marker, _body = _marker_offsets("bottom", marker, (4.0, 60.0))
    assert offsets == [0.0, 0.0]
    canvas = _RectCanvas()
    _draw_list_marker(
        canvas,
        LayoutBox(10.0, 20.0, 4.0, 80.0),
        {**marker, "color": 0xFF112233},
        _fonts(),
        Theme(),
    )
    assert canvas.rect is not None
    assert (canvas.rect.width(), canvas.rect.height()) == (4.0, 80.0)
    print("  ✓  an aside quote bar stays vertical/full-height in every alignment")


def test_quote_char_without_font_keys_draws_in_the_default_style():
    """A quote char is an active marker on its own: with no font key under the
    marker it takes the default text style rather than needing one."""
    with TemporaryDirectory() as td:
        path = Path(td) / "THEME.md"
        path.write_text(
            """## Background styles and Spacing
### Quotes
#### Marker
Quote char: \"
""",
            encoding="utf-8",
        )
        theme = parse_theme(path)

    quote = theme.quotes.marker
    assert isinstance(quote, QuoteStyle) and quote.is_active()
    assert quote.char_text_style == TextStyle()
    node = MarkdownGroupNode(type=NodeType.BLOCKQUOTE, content="row")
    props = build_marker_props(node, theme)
    assert props is not None
    assert (props["mode"], props["text"]) == ("char", '"')
    assert props["font_size"] == TextStyle().font_size
    assert marker_gutter_x(node, theme) == TextStyle().font_size + quote.space
    layout = _layout("> A quoted line.", theme)
    marker = (_marker_parent(layout).children[0].render_properties or {})["list_marker"]
    assert marker["text"] == '"'

    surface = skia.Surface(40, 40)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorWHITE)
    _draw_list_marker(canvas, LayoutBox(4.0, 4.0, 30.0, 30.0), props, _fonts(), theme)
    pixels = surface.makeImageSnapshot().tobytes()
    assert any(b != 0xFF for b in pixels), "the quote char painted nothing"
    print(
        "  ✓  a quote char with no font keys generates and draws in the default style"
    )


TESTS = [
    test_heading_items_keep_their_own_number,
    test_run_seeds_from_the_first_number,
    test_non_ordered_sibling_resets_the_run,
    test_source_number_is_kept_on_the_node,
    test_heading_level_annotation,
    test_style_selection,
    test_numbered_marker_styles_do_not_cross_background_levels,
    test_task_marker_falls_back_to_unordered_marker,
    test_old_top_level_marker_sections_are_not_parsed,
    test_gutter_color_lists_parse_and_rotate_per_marker,
    test_marker_position_fields_parse_and_default,
    test_aside_switches_between_row_and_above_column,
    test_above_marker_does_not_reserve_a_horizontal_gutter,
    test_marker_alignment_uses_the_whole_item_body,
    test_marker_baseline_uses_the_item_bodys_first_line,
    test_quote_bar_turns_horizontal_above_the_body,
    test_vertical_quote_bar_stretches_and_ignores_alignment,
    test_quote_char_without_font_keys_draws_in_the_default_style,
]

if __name__ == "__main__":
    print("Layout Marker Tests")
    print("=" * 50)
    for test in TESTS:
        test()
    print("=" * 50)
    print(f"All {len(TESTS)} tests passed.")
