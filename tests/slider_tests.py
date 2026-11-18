"""Slider syntax, theme geometry, rendering and transient-state tests.

Run with: uv run python tests/slider_tests.py
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import skia

from md2ui import session
from md2ui.pipeline import grouper_sliders
from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.render_fills import _paint_layered_fill
from md2ui.pipeline.layout_render import draw_content_box
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.markdown_grouper import MarkdownGrouper
from md2ui.pipeline.render_actions import action_targets, with_node_states
from md2ui.pipeline import render_drawing_elements as drawing_elements
from md2ui.pipeline.render_drawing_elements import (
    draw_slider,
    slider_geometry,
    slider_value_in_rect,
)
from md2ui.pipeline.theme import Theme, parse_theme
from md2ui.utils.image_cache import ImageCache


def _ast(markdown: str):
    grouper = MarkdownGrouper(markdown).process(None, DataPointDetector())
    assert grouper.ast is not None
    return grouper.ast


def _drawing_nodes(node: dict) -> list[dict]:
    out = [node] if node.get("type") == "drawing_element" else []
    for child in node.get("children", []):
        out.extend(_drawing_nodes(child))
    return out


def _theme(text: str) -> Theme:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as file:
        file.write(text)
        path = Path(file.name)
    try:
        return parse_theme(path)
    finally:
        path.unlink()


def test_slider_syntax_is_grouped_once():
    assert grouper_sliders._hits("[65%]") == [(0, 5, 65.0, 100.0, "%", 0, None)]
    assert grouper_sliders._hits("[3/10]") == [(0, 6, 3.0, 10.0, "", 0, None)]
    tree = _ast("Volume: [65%]\n\n[[25.5%]](agent:set-volume?channel=music)").to_dict()
    nodes = _drawing_nodes(tree)
    assert [node["drawing_element"]["value"] for node in nodes] == [65.0, 25.5]
    assert [node["drawing_element"]["label"] for node in nodes] == [
        "Volume",
        "Slider 2",
    ]
    targets = [target.action for target in action_targets(tree)]
    assert targets[0] is not None and targets[0].kind == "slider"
    assert targets[0].value == 65.0 and targets[0].index == 0
    assert targets[1] is not None and targets[1].kind == "agent"
    assert targets[1].action == "set-volume" and targets[1].value == 25.5
    assert dict(targets[1].params) == {"channel": "music"}
    print("  ✓  plain and linked [n%] sliders become server-visible targets")


def test_slider_declines_lookalikes():
    tree = _ast(r"\[65%] `[25%]` [50%](/ordinary) [101%] [15/10] [3/0]").to_dict()
    assert not _drawing_nodes(tree), tree
    print("  ✓  escaped, code, ordinary-link and out-of-range lookalikes stay text")


def test_slider_is_read_with_its_line():
    # Cut after the springs, `... [65%] ...` is a centred region like any
    # other token: no literal `...` is left, and the PERCENTAGE inside the
    # brackets never reaches the value split.
    tree = _ast("... [65%] ...\n\nA - [65%] - B").to_dict()
    nodes = _drawing_nodes(tree)
    assert [n["drawing_element"]["value"] for n in nodes] == [65.0, 65.0]

    def texts(node: dict) -> list[str]:
        own = [node["content"]] if node.get("content") else []
        return own + [t for c in node.get("children", []) for t in texts(c)]

    assert not any("..." in t or t.strip() == "-" for t in texts(tree)), texts(tree)
    assert nodes[0].get("authored_align") == "center", nodes[0]
    print("  ✓  a slider is one token of its line: springs and separators hold")


def test_a_linked_slider_is_read_with_its_line_too():
    # `[[65%]](url)` is a slider carrying an action, not a link card around a
    # `[65%]` label: carded, it would be cut before the springs saw its line.
    tree = _ast("... [[35%]](agent:x) ...\n\nA - [[35%]](agent:x) - B").to_dict()
    nodes = _drawing_nodes(tree)
    assert [n.get("link_url") for n in nodes] == ["agent:x", "agent:x"], nodes
    assert nodes[0].get("authored_align") == "center", nodes[0]

    def texts(node: dict) -> list[str]:
        own = [node["content"]] if node.get("content") else []
        return own + [t for c in node.get("children", []) for t in texts(c)]

    assert not any("..." in t or t.strip() == "-" for t in texts(tree)), texts(tree)
    print("  ✓  a linked slider holds its springs and separators too")


def test_a_slider_in_a_task_item_is_named_by_its_words():
    # The words the slider sits by name it, as `- Volume [65%] loud` does; a
    # task box's token is never part of them, and a second box bounds them.
    markdown = (
        "- Volume [65%] loud\n- [ ] Mute [20%] now\n- [ ] Buy [x] Bass [3/10] low"
    )
    nodes = _drawing_nodes(_ast(markdown).to_dict())
    labels = {
        n["content"]: n["drawing_element"]["label"]
        for n in nodes
        if n["drawing_element"]["kind"] == "slider"
    }
    assert labels == {"[65%]": "Volume", "[20%]": "Mute", "[3/10]": "Bass"}, labels
    print("  ✓  a slider in a task item is named by its words, not the box's token")


def test_slider_fits_its_box_and_centres_its_row():
    theme = Theme()
    box = LayoutBox(x=0, y=0, width=150, height=85)
    assert drawing_elements.slider_rect(box, theme)[2] == 150.0
    wide = LayoutBox(x=0, y=0, width=400, height=85)
    assert drawing_elements.slider_rect(wide, theme)[:3] == (0, 0.0, 240.0)
    assert drawing_elements.drawing_element_min_width({"kind": "slider"}, theme) < 240
    fonts = session.load_fonts(theme)
    base = drawing_elements.drawing_element_baseline({"kind": "slider"}, fonts, theme)
    assert base is not None and 0 < base < 85, base
    print("  ✓  slider paint caps at its box, left by default, text-centred baseline")


def test_slider_theme_defaults_and_layers():
    defaults = Theme().datapoints.sliders
    assert defaults.style == "thick" and defaults.axis == "horizontal"
    assert defaults.thickness is None
    assert defaults.circle_diameter == 28 and defaults.drag_bar_length == 22
    theme = _theme(
        """## Drawing elements
### Sliders
Style: line
Axis: vertical
Length: 320
Thickness: 12
Corner radius: 4
Circle diameter: 30
Drag bar length: 24
Bar thickness: 5
### Slider Track
Padding: 3
Background color: #E8E4FF
### Slider Bar
Background color: #7657F6
### Slider Handle
Outer shadow:
- Offset Y: 2
- Color: #44000000
- Radius: 8
"""
    )
    sliders = theme.datapoints.sliders
    assert (sliders.style, sliders.axis, sliders.length, sliders.thickness) == (
        "line",
        "vertical",
        320.0,
        12.0,
    )
    assert sliders.corner_radius == 4.0
    assert (sliders.circle_diameter, sliders.drag_bar_length) == (30.0, 24.0)
    assert sliders.drag_bar_thickness == 5.0
    assert not sliders.track.padding.any(), "slider track padding is unsupported"
    assert sliders.track.bg_colors == [0xFFE8E4FF]
    assert sliders.bar.bg_colors == [0xFF7657F6]
    assert len(sliders.handle.shadows) == 1
    print("  ✓  slider geometry and all three background layers parse")


def test_slider_geometry_and_pointer_mapping():
    thick = Theme()
    assert slider_geometry(thick).height == 85.0
    assert slider_value_in_rect((0, 0, 240, 85), thick, 120, 42) == 50.0
    assert slider_value_in_rect((0, 0, 240, 85), thick, 0, 42) == 0.0
    assert slider_value_in_rect((0, 0, 240, 85), thick, 240, 42) == 100.0

    line = Theme()
    line.datapoints.sliders.style = "line"
    line.datapoints.sliders.axis = "vertical"
    geometry = slider_geometry(line)
    assert (geometry.width, geometry.height, geometry.thickness) == (28.0, 240.0, 10.0)
    assert slider_value_in_rect((0, 0, 28, 240), line, 14, 240) == 0.0
    assert slider_value_in_rect((0, 0, 28, 240), line, 14, 0) == 100.0
    print("  ✓  thick/line geometry and horizontal/vertical values share one map")


def test_a_drag_reports_at_the_authored_granularity():
    """A pointer position is not a decision. `[65%]` names whole percents, so a
    drag reports whole percents, so no agent has to decide how much of a raw
    track position to believe."""
    thick = Theme()
    rect = (0.0, 0.0, 200.0, 20.0)
    raw = slider_value_in_rect(rect, thick, 151.2587, 10.0)
    assert raw == 75.62935, raw  # unrounded: the track position, noise and all
    assert slider_value_in_rect(rect, thick, 151.2587, 10.0, 0) == 76.0
    assert slider_value_in_rect(rect, thick, 151.2587, 10.0, 1) == 75.6

    # The precision comes from the document, and reaches the click as data.
    tree = _ast("Volume: [65%]\n\nFine: [40.5%]").to_dict()
    actions = [t.action for t in action_targets(tree) if t.action is not None]
    got = [(a.label, a.value_decimals) for a in actions]
    assert got == [("Volume", 0), ("Fine", 1)], got
    print("  ✓  a drag reports at the precision the author wrote, not the pixel's")


def _paint_test_slider(theme: Theme, *, value: float = 10.0):
    surface = skia.Surface(140, 80)
    surface.getCanvas().clear(0xFFFFFFFF)
    box = LayoutBox(20, 20, 100, 40, bg_stack=(0xFFFFFFFF,))
    node = {"id": "slider", "drawing_element": {"kind": "slider", "value": value}}
    draw_slider(surface.getCanvas(), box, node, theme, _paint_layered_fill)
    return surface


def test_narrow_bar_is_clipped_to_the_inner_track_shape():
    theme = _theme(
        """## Drawing elements
### Sliders
Style: thick
Axis: horizontal
Length: 100
Thickness: 40
Corner radius: 20
Drag bar length: 2
Bar thickness: 2
### Slider Track
Background color: #FFAAFF
### Slider Bar
Background color: #0000FF
### Slider Handle
Background color: #00FF00
"""
    )
    pixels = (
        _paint_test_slider(theme)
        .makeImageSnapshot()
        .toarray(colorType=skia.kRGBA_8888_ColorType)
    )
    assert tuple(pixels[30, 21]) == (255, 255, 255, 255)
    assert tuple(pixels[40, 25]) == (0, 0, 255, 255)
    assert tuple(pixels[40, 40]) == (255, 170, 255, 255)
    print("  ✓  a bar narrower than its radius cannot escape the rounded track")


def test_bar_layers_use_square_fill_and_cast_shadows_from_it():
    theme = _theme(
        """## Drawing elements
### Sliders
Style: thick
Axis: horizontal
Length: 100
Thickness: 40
Corner radius: 20
Drag bar length: 2
Bar thickness: 2
### Slider Track
Background color: #FFAAFF
### Slider Bar
Background color: #0000FF
Outer shadow:
- Color: #44000000
- Radius: 6
Inner shadow:
- Color: #44000000
- Radius: 4
### Slider Handle
Background color: #00FF00
"""
    )
    layers: list[tuple[float, float, tuple]] = []

    def record_layers(canvas, rect, **kwargs):
        layers.append((rect.width(), kwargs["corner_radius"], kwargs["shadows"]))
        _paint_layered_fill(canvas, rect, **kwargs)

    surface = skia.Surface(140, 80)
    box = LayoutBox(20, 20, 100, 40, bg_stack=(0xFFFFFFFF,))
    node = {"id": "slider", "drawing_element": {"kind": "slider", "value": 10}}
    with patch.object(
        drawing_elements,
        "paint_shadows",
        wraps=drawing_elements.paint_shadows,
    ) as shadows:
        draw_slider(surface.getCanvas(), box, node, theme, record_layers)

    bar_layer = next(layer for layer in layers if layer[0] == 10.0)
    assert bar_layer[1:] == (0.0, ())
    assert [
        (
            call.args[1].width(),
            call.args[2],
            call.kwargs["inner"],
            call.kwargs["within"].width(),
        )
        for call in shadows.call_args_list
    ] == [
        (100.0, 20.0, False, 10.0),
        (100.0, 20.0, True, 10.0),
    ]
    print("  ✓  bar content is square; both shadows trace the track cut at the value")


_BAR_THEME = """## Drawing elements
### Sliders
Style: thick
Axis: {axis}
Length: 100
Thickness: 40
Corner radius: 20
Drag bar length: 2
Bar thickness: 2
### Slider Track
Background color: #FFFFFF
### Slider Bar
Background color: #0000FF
{bar}
### Slider Handle
Background color: #00000000
"""


def _bar_pixels(bar: str, value: float, axis: str = "horizontal"):
    """The slider painted in a 140x140 surface; horizontal track is 20..120 x 20..60."""
    theme = _theme(_BAR_THEME.format(axis=axis, bar=bar))
    surface = skia.Surface(140, 140)
    surface.getCanvas().clear(0xFFFFFFFF)
    box = (
        LayoutBox(20, 20, 40, 100, bg_stack=(0xFFFFFFFF,))
        if axis == "vertical"
        else LayoutBox(20, 20, 100, 40, bg_stack=(0xFFFFFFFF,))
    )
    node = {"id": "slider", "drawing_element": {"kind": "slider", "value": value}}
    draw_slider(surface.getCanvas(), box, node, theme, _paint_layered_fill)
    return surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)


def _is_red(pixel) -> bool:
    r, g, b, _ = (int(c) for c in pixel)
    return r > 200 and g < 80 and b < 80


def test_bar_stroke_closes_at_the_value_edge():
    # At 50% the moving edge is x = 70; the outline must cross it at mid-height
    # for every Stroke align, and must not run on under the empty track.
    for align in ("inside", "center", "outside"):
        bar = f"Stroke width: 4\nStroke color: #FF0000\nStroke align: {align}"
        pixels = _bar_pixels(bar, 50)
        edge = [pixels[40, x] for x in range(64, 76)]
        assert any(_is_red(p) for p in edge), f"{align}: no stroke at the value edge"
        assert not any(_is_red(pixels[y, 100]) for y in range(14, 66)), align
    # Vertical: a 50% bar fills 70..120, its moving edge is y = 70.
    bar = "Stroke width: 4\nStroke color: #FF0000\nStroke align: center"
    pixels = _bar_pixels(bar, 50, axis="vertical")
    assert any(_is_red(pixels[y, 40]) for y in range(64, 76))
    print("  ✓  the bar's outline closes at the value edge, for every align")


def test_a_full_bar_strokes_and_shadows_the_whole_track_shape():
    bar = (
        "Stroke width: 4\nStroke color: #FF0000\nStroke align: outside\n"
        "Outer shadow:\n- Color: #88000000\n- Radius: 6\n- Offset x: 2\n- Offset y: 2\n"
        "Inner shadow:\n- Color: #88000000\n- Radius: 4"
    )
    theme = _theme(_BAR_THEME.format(axis="horizontal", bar=bar))
    style = theme.datapoints.sliders.bar
    inner = skia.Rect.MakeXYWH(20, 20, 100, 40)
    expected = skia.Surface(140, 140)
    canvas = expected.getCanvas()
    canvas.clear(0xFFFFFFFF)
    canvas.drawRoundRect(inner, 20, 20, skia.Paint(Color=0xFFFFFFFF, AntiAlias=True))
    drawing_elements.paint_shadows(canvas, inner, 20.0, style.shadows, inner=False)
    canvas.save()
    canvas.clipPath(
        drawing_elements.shape_path(inner, 20.0), skia.ClipOp.kIntersect, True
    )
    canvas.drawRect(inner, skia.Paint(Color=0xFF0000FF, AntiAlias=True))
    canvas.restore()
    drawing_elements.paint_shadows(canvas, inner, 20.0, style.shadows, inner=True)
    stroke = skia.Paint(
        Color=0xFFFF0000, Style=skia.Paint.kStroke_Style, StrokeWidth=4, AntiAlias=True
    )
    drawing_elements.draw_stroke(canvas, inner, 20.0, stroke, "outside")
    want = expected.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    assert (_bar_pixels(bar, 100) == want).all()
    print("  ✓  at 100% the bar's stroke and shadows are the full track shape's")


def test_bar_shadows_reach_the_value_edge():
    # An outer shadow moved right shows past the moving edge (x = 70) ...
    outer = _bar_pixels("Outer shadow:\n- Color: #000000\n- Offset x: 4", 50)
    assert tuple(outer[40, 72]) == (0, 0, 0, 255), tuple(outer[40, 72])
    # ... and an inner shadow moved left darkens the inside of that edge.
    inner = _bar_pixels("Inner shadow:\n- Color: #000000\n- Offset x: -4", 50)
    assert tuple(inner[40, 68]) == (0, 0, 0, 255), tuple(inner[40, 68])
    print("  ✓  the bar's shadows are cast from the filled shape, value edge included")


def test_slider_region_and_transient_value_match_target():
    ast = _ast("# Audio\n\nVolume: [65%]")
    theme = Theme()
    fonts = session.load_fonts(theme)
    root, node_index = session.prepare(ast, theme)
    expected = action_targets(ast.to_dict())[0].action
    assert expected is not None
    for width in (767.0, 1280.0):
        scene = session.build_scene(
            LayoutGenerator(), root, node_index, theme, fonts, width
        )
        assert len(scene.regions) == 1
        action = scene.regions[0].action
        assert (action.kind, action.node_id, action.value) == (
            expected.kind,
            expected.node_id,
            expected.value,
        )
    shown = with_node_states(node_index, {expected.node_id: 72.5})
    assert shown[expected.node_id]["drawing_element"]["value"] == 72.5
    assert node_index[expected.node_id]["drawing_element"]["value"] == 65.0
    print("  ✓  paint/hit geometry shares the target; drag state swaps no source node")


_HANDLE_THEME = """## Drawing elements
### Sliders
Style: thick
Axis: {axis}
Length: 100
Thickness: 40
Drag bar length: 20
Bar thickness: 4
{gap}
### Slider Track
Background color: #FFFFFF
### Slider Bar
Background color: #0000FF
### Slider Handle
Background color: #00FF00
"""


def _handle_span(value: float, axis: str, gap: str = "") -> tuple[int, int]:
    """The drag bar's painted extent along the axis, in the 140x140 surface
    whose track is 20..120 on that axis."""
    theme = _theme(_HANDLE_THEME.format(axis=axis, gap=gap))
    surface = skia.Surface(140, 140)
    surface.getCanvas().clear(0xFFFFFFFF)
    box = (
        LayoutBox(20, 20, 40, 100, bg_stack=(0xFFFFFFFF,))
        if axis == "vertical"
        else LayoutBox(20, 20, 100, 40, bg_stack=(0xFFFFFFFF,))
    )
    node = {"id": "slider", "drawing_element": {"kind": "slider", "value": value}}
    draw_slider(surface.getCanvas(), box, node, theme, _paint_layered_fill)
    pixels = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    line = pixels[:, 40] if axis == "vertical" else pixels[40, :]
    green = [i for i, (r, g, b, _) in enumerate(line) if g > 200 and r < 60 and b < 60]
    assert green, f"no drag bar painted ({axis}, {value})"
    return green[0], green[-1]


def test_the_drag_bar_sits_inside_the_fill_at_its_gap():
    assert Theme().datapoints.sliders.drag_bar_gap == 5.0
    gap = _theme(_HANDLE_THEME.format(axis="horizontal", gap="Drag bar gap: 8"))
    assert gap.datapoints.sliders.drag_bar_gap == 8.0
    # At 50% the value edge is 70 on both axes. Horizontal: the bar ends
    # `gap` short of it, on the fill's side; vertical: it starts `gap` below it.
    assert _handle_span(50, "horizontal") == (61, 64)
    assert _handle_span(50, "horizontal", "Drag bar gap: 8") == (58, 61)
    assert _handle_span(50, "vertical") == (75, 78)
    # A fill too short for gap + bar keeps the bar at the track's start.
    assert _handle_span(1, "horizontal") == (20, 23)
    assert _handle_span(1, "vertical") == (116, 119)
    print("  ✓  the drag bar sits inside the fill, its gap short of the value edge")


def _typed_root_below(node: dict) -> list[dict]:
    out: list[dict] = []
    for child in node.get("children", []):
        if child.get("type") == "root":
            out.append(child)
        out.extend(_typed_root_below(child))
    return out


def test_a_one_line_document_keeps_its_root_a_root():
    # A one-line document keeps its line on the root; the slider cut from it is
    # the root's child and the text beside it is text, not a second root.
    for markdown in ["Volume [65%] loud", "[[3/10]](agent:x) b", "[65%]"]:
        tree = _ast(markdown).to_dict()
        assert tree["type"] == "root", (markdown, tree["type"])
        assert not _typed_root_below(tree), (markdown, _typed_root_below(tree))
        assert len(_drawing_nodes(tree)) == 1, markdown
    print("  ✓  a one-line document's slider and text are children of its root")


def _leaves(node: dict) -> list[dict]:
    children = node.get("children", [])
    return (
        [leaf for child in children for leaf in _leaves(child)] if children else [node]
    )


def test_a_list_item_keeps_its_slider_line_one_item():
    # The text cut from beside a slider in a list item is text inside that one
    # item, the way the task-box splitter cuts it, not further items of the
    # list, and a task item keeps exactly one box of its own.
    cases = {
        "- Volume [65%] loud": "list_item",
        "1. Treble [[3/10]](agent:x) high": "ordered_item",
        "- [ ] Mute [40%] now": "task_open",
    }
    for markdown, holder in cases.items():
        tree = _ast(markdown).to_dict()
        items = [tree] if tree["type"] == holder else []
        stack = list(tree.get("children", []))
        while stack:
            node = stack.pop()
            if node["type"] == holder:
                items.append(node)
            stack.extend(node.get("children", []))
        assert len(items) == 1, (markdown, [n["type"] for n in items])
        leaves = _leaves(items[0])
        kinds = [(leaf.get("drawing_element") or {}).get("kind") for leaf in leaves]
        texts = [leaf["type"] for leaf in leaves if leaf["type"] != "drawing_element"]
        assert texts and set(texts) == {"text"}, (markdown, texts)
        assert kinds.count("slider") == 1, (markdown, kinds)
        boxes = 1 if holder == "task_open" else 0
        assert kinds.count("task_control") == boxes, (markdown, kinds)
    print("  ✓  text beside a slider in a list item is text inside that one item")


_KIT = None


def _grouped(markdown: str) -> dict:
    """*markdown* through the real pipeline (``session.group_markdown``)."""
    global _KIT
    if _KIT is None:
        _KIT = session.load_grouping_kit()
    ast = session.group_markdown(markdown + "\n", _KIT)
    assert ast is not None, markdown
    return ast.to_dict()


def test_every_escaped_slider_spelling_is_text_drawn_as_written():
    """Escaping a slider's bracket declines it whatever its spelling: a
    percentage or a ratio, its closing bracket escaped or not. On a ``Label:``
    line the line is put back as written, with ``[`` and never the placeholder
    the escape hid it behind."""
    for markdown, drawn in (
        (r"Volume: \[65%]", "Volume: [65%]"),
        (r"Volume: \[65%\]", "Volume: [65%]"),
        (r"Quantity: \[2/9]", "Quantity: [2/9]"),
        (r"Quantity: \[2/9\]", "Quantity: [2/9]"),
        (r"Set it \[65%\] now.", "Set it [65%] now."),
    ):
        tree = _grouped(markdown)
        assert not _drawing_nodes(tree) and not action_targets(tree), markdown
        texts = [leaf.get("content") for leaf in _leaves(tree)]
        assert texts == [drawn], (markdown, texts)
    print("  ✓  every escaped slider spelling is text, its bracket drawn as written")


def test_a_muted_slider_is_disabled_and_keeps_its_ordinal():
    """``~~[65%]~~`` is a slider's muted state, as ``~~[Go](agent:go)~~`` is a
    link's: it reports nothing, keeps its ordinal (ADR-601), and its tildes are
    neither drawn nor its label."""
    tree = _grouped(
        "Volume: ~~[65%]~~\n\nEffects: ~~[[35%]](agent:set-effects)~~\n\n"
        "Bass: [30%]\n\n~~Treble: [40%]~~"
    )
    payloads = [node["drawing_element"] for node in _drawing_nodes(tree)]
    assert [p.get("disabled", False) for p in payloads] == [True, True, False, True]
    assert [p["label"] for p in payloads] == ["Volume", "Effects", "Bass", "Treble"]
    assert [p["index"] for p in payloads] == [0, 1, 2, 3]
    assert "~~" not in [leaf.get("content") for leaf in _leaves(tree)]
    targets = action_targets(tree)
    assert [(t.action is None, t.disabled) for t in targets] == [
        (True, True),
        (True, True),
        (False, False),
        (True, True),
    ], targets
    assert targets[2].action is not None and targets[2].action.index == 2
    print("  ✓  a muted slider reports nothing, keeps its ordinal, takes no tildes")


def _painted(payload: dict) -> skia.Image:
    surface = skia.Surface(140, 80)
    surface.getCanvas().clear(0xFFFFFFFF)
    box = LayoutBox(20, 20, 100, 40, bg_stack=(0xFFFFFFFF,))
    node = {"type": "drawing_element", "node_id": "n", "drawing_element": payload}
    draw_content_box(surface.getCanvas(), box, node, _FONTS, ImageCache(), Theme())
    return surface.makeImageSnapshot()


_FONTS = session.load_fonts(Theme())


def test_a_muted_control_is_painted_faded_in_its_box():
    """A muted slider, count or task box is drawn whole at the muted opacity:
    the same shapes in the same place, every painted pixel nearer the
    background than the live control's, and nothing painted the live one
    leaves blank."""
    for payload in (
        {"kind": "slider", "value": 40.0, "max": 100.0, "unit": "%"},
        {"kind": "slider", "value": 2.0, "max": 9.0, "unit": "", "count": True},
        {"kind": "task_control", "checked": True},
    ):
        live = _painted(payload).toarray(colorType=skia.kRGBA_8888_ColorType)
        muted = _painted({**payload, "disabled": True}).toarray(
            colorType=skia.kRGBA_8888_ColorType
        )
        ink_live = (255 - live[..., :3].astype(int)).sum(axis=2)
        ink_muted = (255 - muted[..., :3].astype(int)).sum(axis=2)
        assert ink_live.sum() > 0, payload
        assert ((ink_muted > 0) <= (ink_live > 0)).all(), payload
        assert ink_muted.sum() < 0.6 * ink_live.sum(), payload
    print("  ✓  a muted slider, count or task box is painted faded, in its own box")


TESTS = [
    test_slider_syntax_is_grouped_once,
    test_slider_declines_lookalikes,
    test_slider_is_read_with_its_line,
    test_a_linked_slider_is_read_with_its_line_too,
    test_a_one_line_document_keeps_its_root_a_root,
    test_a_list_item_keeps_its_slider_line_one_item,
    test_every_escaped_slider_spelling_is_text_drawn_as_written,
    test_a_muted_slider_is_disabled_and_keeps_its_ordinal,
    test_a_muted_control_is_painted_faded_in_its_box,
    test_a_slider_in_a_task_item_is_named_by_its_words,
    test_slider_fits_its_box_and_centres_its_row,
    test_slider_theme_defaults_and_layers,
    test_slider_geometry_and_pointer_mapping,
    test_a_drag_reports_at_the_authored_granularity,
    test_narrow_bar_is_clipped_to_the_inner_track_shape,
    test_bar_layers_use_square_fill_and_cast_shadows_from_it,
    test_bar_stroke_closes_at_the_value_edge,
    test_a_full_bar_strokes_and_shadows_the_whole_track_shape,
    test_bar_shadows_reach_the_value_edge,
    test_slider_region_and_transient_value_match_target,
    test_the_drag_bar_sits_inside_the_fill_at_its_gap,
]


if __name__ == "__main__":
    print("Slider Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:
            print(f"  ✗  {test.__name__}: {exc!r}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
