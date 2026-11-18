"""List-scoped task-control grouping, theme parsing, and shared geometry."""

import tempfile
from pathlib import Path

import skia  # type: ignore[import-untyped]

from md2ui import session
from md2ui.pipeline import render_drawing_elements as RDE
from md2ui.pipeline.grouper_drawing_elements import protect_escaped_task_controls
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.markdown_grouper import MarkdownGrouper
from md2ui.pipeline.render_actions import action_targets
from md2ui.pipeline.render_glyph_faces import glyph_advance
from md2ui.pipeline.render_drawing_elements import (
    draw_task_control,
    task_control_geometry,
    task_control_radii,
)
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import Theme, parse_theme
from md2ui.pipeline.theme_model import TaskControlsTheme
from md2ui.utils.font_loader import make_font


def _group(markdown: str) -> MarkdownGroupNode:
    grouper = MarkdownGrouper(markdown)
    grouper.process()
    assert grouper.ast is not None
    return grouper.ast


def _controls(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    out = [node] if node.type == NodeType.DRAWING_ELEMENT else []
    for child in node.children:
        out.extend(_controls(child))
    return out


def _theme(markdown: str) -> Theme:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
        handle.write(markdown)
        path = Path(handle.name)
    try:
        return parse_theme(path)
    finally:
        path.unlink()


def test_standard_and_empty_tasks_become_controls():
    root = _group("- [x] done\n- [ ] open\n- [X]")
    controls = _controls(root)
    assert all(c.drawing_element is not None for c in controls)
    assert [c.drawing_element["checked"] for c in controls if c.drawing_element] == [
        True,
        False,
        True,
    ]
    assert [c.content for c in controls] == ["[X]", "[ ]", "[X]"]


def test_controls_split_inside_or_outside_lists():
    root = _group("outside [X]\n[ ]\n- before [ ] middle [X] after")
    controls = _controls(root)
    assert [c.drawing_element["checked"] for c in controls if c.drawing_element] == [
        True,
        False,
        False,
        True,
    ]


def test_controls_compose_with_springs():
    root = _group("... [x]\nWiFi ... [x]\n- ... [x]")
    assert len(_controls(root)) == 3
    aligned = [
        n for n in _walk(root) if n.authored_align in ("left", "center", "right")
    ]
    assert any(n.authored_align == "right" and _controls(n) for n in aligned)


def _walk(node: MarkdownGroupNode):
    yield node
    for child in node.children:
        yield from _walk(child)


def test_link_annotation_does_not_make_a_link_node():
    root = _group("- [[X]](/disable) linked")
    controls = _controls(root)
    assert len(controls) == 1 and controls[0].link_url == "/disable"
    assert not any(n.type == NodeType.LINK for n in _walk(root))
    line_ids = {n.source_line_id for n in _walk(root) if n.content}
    assert line_ids == {0}, line_ids


def test_code_escape_image_and_ordinary_link_are_not_controls():
    assert protect_escaped_task_controls(r"\[X]") != "[X]"
    root = _group(
        "- `[X]` literal\n- \\[X] escaped\n- ![X](a.png) image\n- [X](/go) link"
    )
    assert not _controls(root)


def test_an_escaped_box_draws_as_written():
    """An escape keeps the token's spelling: ``\\[x]`` is ``[x]``, never ``[X]``."""
    root = _group("plain \\[x] one\n\nplain \\[X] two\n\nplain \\[ ] three\n")
    assert not _controls(root)
    texts = _leaf_texts(root)
    assert texts == ["plain [x] one", "plain [X] two", "plain [ ] three"], texts


def test_drawing_payload_round_trips():
    control = _controls(_group("- [[ ]](/enable)"))[0]
    restored = MarkdownGroupNode.from_dict(control.to_dict())
    assert restored.type == NodeType.DRAWING_ELEMENT
    # index / label: the ordinal and item text a click reports (Phase 6.246).
    assert restored.drawing_element == {
        "kind": "task_control",
        "checked": False,
        "index": 0,
        "label": "",
    }
    assert restored.link_url == "/enable"


def test_theme_canonical_header_and_legacy_alias():
    canonical = _theme(
        """## Drawing elements
### Task controls
Type: switch
Size: 52
Padding: 6
Corner radius: 18
Space: 9
### Checked outer
Background color: #123456
Stroke width: 2
"""
    ).datapoints.task_controls
    assert (canonical.type, canonical.size, canonical.padding) == ("switch", 52, 6)
    assert (canonical.corner_radius, canonical.space) == (18, 9)
    assert canonical.checked_outer.bg_colors == [0xFF123456]
    assert canonical.checked_outer.stroke_width == 2
    legacy = _theme("## Datapoints\n### Task controls\nType: switch\n")
    assert legacy.datapoints.task_controls.type == "switch"


def test_geometry_defaults_minimums_and_inner_radius():
    checkbox = task_control_geometry(Theme())
    assert (checkbox.width, checkbox.height, checkbox.outer_radius) == (32, 32, 6)
    assert checkbox.inner_radius == 2
    theme = Theme()
    assert isinstance(theme.datapoints.task_controls, TaskControlsTheme)
    controls = theme.datapoints.task_controls
    controls.type, controls.size, controls.padding = "switch", 12, 4
    switch = task_control_geometry(theme)
    assert (switch.width, switch.height) == (80, 40)
    assert switch.outer_radius == 20 and switch.inner_radius == 16
    controls.corner_radius = 0
    square = task_control_geometry(theme)
    assert square.outer_radius == 0 and square.inner_radius == 0


def test_outer_state_corner_radius_is_authored():
    theme = _theme(
        """## Drawing elements
### Task controls
Corner radius: 6
### Checked outer
Background color: #123456
Corner radius: 16
### Unchecked outer
Background color: #123456
Corner radius: 0
"""
    )
    controls = theme.datapoints.task_controls
    assert controls.checked_outer.corner_radius == 16
    assert controls.checked_outer.corner_radius_authored
    assert controls.unchecked_outer.corner_radius == 0
    assert controls.unchecked_outer.corner_radius_authored
    geometry = task_control_geometry(theme)
    assert task_control_radii(geometry, controls.checked_outer) == (16, 12)
    assert task_control_radii(geometry, controls.unchecked_outer) == (0, 0)


def _leaf_texts(node: MarkdownGroupNode) -> list[str]:
    return [n.content for n in _walk(node) if not n.children and n.content]


def test_controls_join_a_separated_run():
    # Cut after the separators have read the line, a control is one more piece
    # of the run -- no ` - ` stranded in a text leaf, no nested sub-run.
    root = _group("A - [ ] - B")
    run = next(n for n in _walk(root) if n.separator_chars)
    assert run.separator_chars == ["-", "-"], run.separator_chars
    assert [c.type for c in run.children] == [
        NodeType.SEGMENT,
        NodeType.DRAWING_ELEMENT,
        NodeType.SEGMENT,
    ], [c.type for c in run.children]
    assert not any("-" in text for text in _leaf_texts(root)), _leaf_texts(root)


def test_task_marker_is_the_left_region_of_a_spring_item():
    # `- [ ] ... Word` lines up with `- ✅ ... Word`: the box is the left
    # region, not folded into the right-aligned text.
    root = _group("- [ ] ... Word")
    item = next(n for n in _walk(root) if n.type == NodeType.TASK_OPEN)
    assert item.align_group
    first, second = item.children
    assert first.type == NodeType.DRAWING_ELEMENT and first.authored_align == "left"
    assert second.content == "Word" and second.authored_align == "right"


def test_a_task_marker_ending_its_line_takes_the_label_under_it():
    # `- [ ]` then an indented line is a task item, with or without a space
    # after the box -- the indented line is its label, as for any item.
    for spelling in ("- [ ]\n  Task item", "- [ ] \n  Task item"):
        root = _group(spelling)
        item = next(n for n in _walk(root) if n.type in (NodeType.TASK_OPEN,))
        assert _controls(item) and "Task item" in [n.content for n in _walk(item)]


_LINKED = (
    "- [ ] Pack the kitchen\n- [[{box}]](agent:toggle-task?id=1) Transfer the utilities"
)


def test_a_linked_box_is_the_same_task_item():
    # `- [[ ]](url) label` is `- [ ] label` whose box clicks through to url:
    # the same task item, styled from task_lists, with ONE control.
    for box, kind in ((" ", NodeType.TASK_OPEN), ("x", NodeType.TASK_DONE)):
        root = _group(_LINKED.format(box=box))
        items = [n for n in _walk(root) if n.type in (kind, NodeType.TASK_OPEN)]
        linked = items[-1]
        assert linked.type == kind, (box, linked.type)
        assert linked.text_style_chain[-1] == "task_lists", linked.text_style_chain
        (control,) = _controls(linked)
        payload = control.drawing_element
        assert control.link_url == "agent:toggle-task?id=1" and payload is not None
        assert payload["checked"] is (box == "x")
        texts = [n.content for n in _walk(linked) if n.type == NodeType.TEXT]
        assert texts == ["Transfer the utilities"], texts
        assert payload["label"] == "Transfer the utilities"


def test_a_bare_linked_box_stays_a_bullet_holding_it():
    # With no label, the linked box is what the plain bare box is: a bullet
    # holding one control, which keeps its URL.
    for bare, url in (("- [ ]", None), ("- [[ ]](/enable)", "/enable")):
        root = _group(bare)
        item = next(n for n in _walk(root) if n.type == NodeType.LIST_ITEM)
        (control,) = _controls(item)
        assert control.link_url == url, (bare, control.link_url)


def test_a_linked_box_after_the_marker_is_a_second_control():
    # `- [ ] [[x]](/u) b` is a task whose own box is the marker's, holding a
    # linked box and the label: two controls, each with its own state, and the
    # marker's box takes nothing from the linked one. A spring before the box
    # leaves it a control too.
    for markdown, kind in (
        ("- [ ] [[x]](/u) b", NodeType.TASK_OPEN),
        ("- [x] [[ ]](/u) b", NodeType.TASK_DONE),
        ("- [ ] ... [[x]](/u) b", NodeType.TASK_OPEN),
    ):
        root = _group(markdown)
        (item,) = [n for n in _walk(root) if n.type == kind]
        marker, linked = _controls(item)
        assert marker.drawing_element is not None, markdown
        assert linked.drawing_element is not None, markdown
        assert marker.drawing_element["checked"] is (kind == NodeType.TASK_DONE)
        assert linked.drawing_element["checked"] is (kind == NodeType.TASK_OPEN)
        assert (marker.link_url, linked.link_url) == (None, "/u"), markdown
        texts = [n.content.strip() for n in _walk(item) if n.type == NodeType.TEXT]
        assert texts == ["b"], (markdown, texts)


def test_only_a_task_items_own_box_is_its_marker():
    # A task item's box marks it as a bullet does, so the layout counts the
    # item's pieces without it; a box inside the text, a
    # linked one after the marker, or one in a bare bullet is a piece.
    for markdown, flags in (
        ("- [ ] Buy milk", [True]),
        ("- [x] Pay rent - $1,200", [True]),
        ("- [[ ]](/a) Buy milk", [True]),
        ("- [ ] [[x]](/u) b", [True, False]),
        ("- [ ] ... Word", [True]),
        ("- before [ ] after", [False]),
        ("- [ ]", [False]),
        ("[x] b", [False]),
    ):
        controls = _controls(_group(markdown))
        got = [bool((c.drawing_element or {}).get("marker")) for c in controls]
        assert got == flags, (markdown, got)


def test_a_task_box_reports_the_item_text():
    # A task item's own box reports the item's text even when another box
    # comes first in it; a box inside the item reports the text it starts.
    for markdown, labels in (
        ("- [ ] b", ["b"]),
        ("- [ ] [[x]](/u) b", ["b", "b"]),
        ("- [ ] [x] b", ["b", "b"]),
        ("- [ ] a [x] b", ["a b", "b"]),
        ("- [ ] ... [x] b", ["b", "b"]),
        ("- [ ] Mute [20%] now", ["Mute"]),
        ("- [ ] a\n  b", ["a"]),
        ("- [ ] [x] b\n  - [ ] c", ["b", "b", "c"]),
    ):
        got = [
            c.drawing_element["label"]
            for c in _controls(_group(markdown))
            if c.drawing_element is not None
            and c.drawing_element["kind"] == "task_control"
        ]
        assert got == labels, (markdown, got)


def test_a_spring_task_box_reports_the_whole_item_text():
    # A spring divides the item's line into regions, which wraps the box in a
    # region of its own; the box still names the item, by all of its words, as
    # the same line without the spring would.
    for markdown, labels in (
        ("- [ ] a ... Word", ["a Word"]),
        ("- [ ] a Word", ["a Word"]),
        ("- [ ] a ... [x] b", ["a b", "b"]),
        ("- [ ] Mute [20%] ... now", ["Mute"]),
        ("- [ ] a ... b\n  - [ ] c", ["a b", "c"]),
    ):
        got = [
            c.drawing_element["label"]
            for c in _controls(_group(markdown))
            if c.drawing_element is not None
            and c.drawing_element["kind"] == "task_control"
        ]
        assert got == labels, (markdown, got)


def _regions(node: MarkdownGroupNode) -> tuple:
    return (
        node.type,
        node.authored_align,
        node.content,
        tuple(_regions(c) for c in node.children),
    )


def test_a_linked_box_is_the_left_region_of_a_spring_item():
    # `- [[ ]](/a) Pay ... [x]` lays out as `- [ ] Pay ... [x]`: the box is a
    # left region of its own, and only its destination differs.
    plain = _group("- [ ] Pay ... [x]")
    linked = _group("- [[ ]](/a) Pay ... [x]")
    assert _regions(linked) == _regions(plain), (_regions(linked), _regions(plain))
    assert [c.link_url for c in _controls(linked)] == ["/a", None]


def _typed_root_below(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    out: list[MarkdownGroupNode] = []
    for child in node.children:
        if child.type == "root":
            out.append(child)
        out.extend(_typed_root_below(child))
    return out


def test_a_one_line_document_keeps_its_root_a_root():
    # A one-line document keeps its line on the root. The control cut from it
    # is the root's child and the text beside it is text: neither the pieces
    # nor the root take each other's type.
    for markdown in ["[x] b", "[[x]](/u) b", "b [x]", "[ ] a and [x] c", "[x]"]:
        root = _group(markdown)
        assert root.type == "root", (markdown, root.type)
        assert not _typed_root_below(root), (markdown, _typed_root_below(root))
        assert _controls(root), markdown
        assert root.drawing_element is None, markdown


def test_inner_symbol_keys_parse():
    controls = _theme(
        """## Drawing elements
### Checked inner
Background color: #FFFFFF
Symbol: ✓
Symbol color: #5B4FC4
### Unchecked inner
Symbol: ✕
"""
    ).datapoints.task_controls
    assert (controls.checked_symbol, controls.checked_symbol_color) == (
        "✓",
        0xFF5B4FC4,
    )
    assert (controls.unchecked_symbol, controls.unchecked_symbol_color) == ("✕", None)
    assert controls.checked_inner.bg_colors == [0xFFFFFFFF]
    plain = Theme().datapoints.task_controls
    assert plain.checked_symbol is None and plain.unchecked_symbol is None


_SYMBOL_THEME = """## Drawing elements
### Task controls
Type: {kind}
### Checked outer
Background color: #5B4FC4
### Checked inner
Background color: #FFFFFF
{symbol}
"""


def _drawn_symbols(theme: Theme, checked: bool = True) -> tuple[list, skia.Rect]:
    """The glyph draws ``draw_task_control`` makes, and its inner shape."""
    face = skia.Typeface.MakeDefault()
    fonts = FontSet(face, face, face, face, face, face, {})
    fills: list[skia.Rect] = []
    calls: list[tuple] = []

    def fill(_canvas, rect, **_kwargs):
        fills.append(rect)

    def glyphs(_canvas, text, x, y, emoji_tf, fallback_tf, size, paint):
        calls.append((text, x, y, emoji_tf, fallback_tf, size, paint.getColor()))
        return 0.0

    node = {"drawing_element": {"kind": "task", "checked": checked}}
    canvas = skia.Surface(200, 100).getCanvas()
    original = RDE.draw_glyph_runs
    RDE.draw_glyph_runs = glyphs
    try:
        draw_task_control(canvas, LayoutBox(0, 0, 200, 100), node, fonts, theme, fill)
    finally:
        RDE.draw_glyph_runs = original
    return calls, fills[-1]


def test_no_symbol_key_draws_no_glyph():
    calls, _inner = _drawn_symbols(
        _theme(_SYMBOL_THEME.format(kind="checkbox", symbol=""))
    )
    assert calls == []


def _assert_centred(call: tuple, inner: skia.Rect) -> None:
    text, x, y, emoji_tf, fallback_tf, size, _color = call
    width = glyph_advance(text, emoji_tf, fallback_tf, size)
    metrics = make_font(emoji_tf or fallback_tf, size).getMetrics()
    assert abs(x + width / 2 - inner.centerX()) < 0.01
    middle = y + (metrics.fAscent + metrics.fDescent) / 2
    assert abs(middle - inner.centerY()) < 0.01
    assert size <= inner.height()


def test_symbol_is_centred_in_the_outer_fill_color():
    for kind in ("checkbox", "switch"):
        theme = _theme(_SYMBOL_THEME.format(kind=kind, symbol="Symbol: ✓"))
        calls, inner = _drawn_symbols(theme)
        assert [c[0] for c in calls] == ["✓"]
        assert calls[0][6] == 0xFF5B4FC4
        _assert_centred(calls[0], inner)


def test_an_explicit_symbol_color_wins():
    theme = _theme(
        _SYMBOL_THEME.format(kind="checkbox", symbol="Symbol: ✓\nSymbol color: #D03030")
    )
    calls, _inner = _drawn_symbols(theme)
    assert calls[0][6] == 0xFFD03030
    unchecked, _inner = _drawn_symbols(theme, checked=False)
    assert unchecked == []


def test_symbol_color_is_replaced_on_the_inner_background():
    theme = _theme(
        _SYMBOL_THEME.format(kind="checkbox", symbol="Symbol: ✓")
        + """
## Color Replacements
On background color: #FFFFFF
- Text color: #5B4FC4, Replacement: #101010
"""
    )
    calls, _inner = _drawn_symbols(theme)
    assert calls[0][6] == 0xFF101010


def _grouped(markdown: str) -> dict:
    """*markdown* through the real pipeline (``session.group_markdown``)."""
    ast = session.group_markdown(markdown + "\n", session.load_grouping_kit())
    assert ast is not None, markdown
    return ast.to_dict()


def _dict_leaves(node: dict) -> list[dict]:
    kids = node.get("children", [])
    return [leaf for kid in kids for leaf in _dict_leaves(kid)] if kids else [node]


def test_an_escaped_box_is_text_whatever_its_spelling():
    """``\\[x\\]`` declines a box as ``\\[x]`` does, and a ``Label:`` line
    gives the box's spelling back when its pair is undone, never the
    placeholder the escape hid it behind."""
    for markdown, drawn in (
        (r"WiFi: \[x]", "WiFi: [x]"),
        (r"WiFi: \[x\]", "WiFi: [x]"),
        (r"- \[x\] Escaped box", "[x] Escaped box"),
    ):
        tree = _grouped(markdown)
        assert not action_targets(tree), markdown
        texts = [leaf.get("content") for leaf in _dict_leaves(tree)]
        assert texts == [drawn], (markdown, texts)
    print("  ✓  an escaped box is text in every spelling, drawn as written")


def test_a_muted_task_box_is_disabled_and_keeps_its_ordinal():
    """``~~[ ]~~`` is a box's muted state: it reports nothing, keeps its
    ordinal (ADR-601), and its tildes are neither drawn nor its label."""
    tree = _grouped("- ~~[ ]~~ Send the report\n- [ ] Call Ana\n\nWiFi ... ~~[x]~~")
    boxes = [
        leaf["drawing_element"]
        for leaf in _dict_leaves(tree)
        if leaf.get("drawing_element")
    ]
    assert [b.get("disabled", False) for b in boxes] == [True, False, True], boxes
    assert [b["label"] for b in boxes] == ["Send the report", "Call Ana", ""], boxes
    assert not [
        leaf for leaf in _dict_leaves(tree) if "~~" in (leaf.get("content") or "")
    ]
    targets = action_targets(tree)
    assert [(t.action is None, t.disabled) for t in targets] == [
        (True, True),
        (False, False),
        (True, True),
    ], targets
    assert targets[1].action is not None and targets[1].action.index == 1
    print("  ✓  a muted task box reports nothing, keeps its ordinal, takes no tildes")


TESTS = [
    test_standard_and_empty_tasks_become_controls,
    test_an_escaped_box_is_text_whatever_its_spelling,
    test_a_muted_task_box_is_disabled_and_keeps_its_ordinal,
    test_a_task_marker_ending_its_line_takes_the_label_under_it,
    test_controls_split_inside_or_outside_lists,
    test_controls_compose_with_springs,
    test_controls_join_a_separated_run,
    test_task_marker_is_the_left_region_of_a_spring_item,
    test_link_annotation_does_not_make_a_link_node,
    test_a_linked_box_is_the_same_task_item,
    test_a_bare_linked_box_stays_a_bullet_holding_it,
    test_a_linked_box_after_the_marker_is_a_second_control,
    test_only_a_task_items_own_box_is_its_marker,
    test_a_linked_box_is_the_left_region_of_a_spring_item,
    test_a_task_box_reports_the_item_text,
    test_a_spring_task_box_reports_the_whole_item_text,
    test_a_one_line_document_keeps_its_root_a_root,
    test_code_escape_image_and_ordinary_link_are_not_controls,
    test_an_escaped_box_draws_as_written,
    test_drawing_payload_round_trips,
    test_theme_canonical_header_and_legacy_alias,
    test_geometry_defaults_minimums_and_inner_radius,
    test_outer_state_corner_radius_is_authored,
    test_inner_symbol_keys_parse,
    test_no_symbol_key_draws_no_glyph,
    test_symbol_is_centred_in_the_outer_fill_color,
    test_an_explicit_symbol_color_wins,
    test_symbol_color_is_replaced_on_the_inner_background,
]


if __name__ == "__main__":
    for test in TESTS:
        test()
        print(f"  ✓ {test.__name__}")
