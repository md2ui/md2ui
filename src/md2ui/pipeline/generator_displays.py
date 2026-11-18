"""Build the layout nodes that draw datapoint displays.

This is the generator-side counterpart to ``grouper_displays``: the grouper
identifies display-shaped data, while this module applies the theme and builds
the synthetic bars, rings and charts the renderer paints.
"""

import copy
from collections.abc import Callable
from dataclasses import dataclass

from md2ui.pipeline.generator_units import LEAF_WIDTH, _length_category, _unit_padding_x
from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.markdown_grouper import MarkdownGroupNode
from md2ui.pipeline.theme import Theme


@dataclass(frozen=True)
class GeneratorContext:
    theme: Theme | None
    measure_line: Callable[..., float | None] | None
    measure_width: Callable[[MarkdownGroupNode], float | None] | None


def _dp_theme(ctx: GeneratorContext):
    return getattr(ctx.theme, "datapoints", None)


def _charts_enabled(ctx: GeneratorContext) -> bool:
    ct = getattr(ctx.theme, "charts", None)
    return ct is not None and ct.enabled


def _dp_display_enabled(ctx: GeneratorContext, node: MarkdownGroupNode) -> bool:
    """Whether *node*'s datapoint_display family is enabled by the theme.

    Without a theme every family is off — the flags stay inert and the
    node renders exactly as before (the grouper annotates unconditionally;
    the theme gates consumption)."""
    dp = _dp_theme(ctx)
    if dp is None or node.datapoint_display is None:
        return False
    d = node.datapoint_display
    if d == "ratio_bar":
        return dp.ratio_bar.enabled
    if d == "kv_percent_bar":
        return dp.kv_bar.enabled
    if d == "unit_ratio":
        return dp.unit_ratio_enabled
    if d == "date_chip":
        return dp.date_chip.enabled
    if d == "line_chart":
        ct = getattr(ctx.theme, "charts", None)
        return ct is not None and ct.line.enabled
    return False


def _is_drawn_date_chip(ctx: GeneratorContext, node: MarkdownGroupNode) -> bool:
    return node.datapoint_display == "date_chip" and _dp_display_enabled(ctx, node)


def _is_drawn_ring(ctx: GeneratorContext, node: MarkdownGroupNode) -> bool:
    return (
        node.datapoint_display == "unit_ratio"
        and _dp_display_enabled(ctx, node)
        and _unit_ratio_is_ring(ctx)
    )


def column_floor(ctx: GeneratorContext, unit: MarkdownGroupNode) -> float | None:
    """The per-column minimum a grid of *unit* starts from, before measurement.

    ``LEAF_WIDTH`` by the unit's text-length category — a prose heuristic for
    text that wraps. A drawn display that is the whole unit (through any
    single-child wrap, such as a list item) is as wide as it draws, which the
    measurement already floors, so it gets no word-count floor:

    - a date chip is its widest line plus its card padding
      (``column_padding_x``): flooring `Jun 5` at a one-word 80px left 8 chips
      gridding 4+4 at widths that fit all 8 in a row;
    - a ring is its diameter, its words drawn inside it: flooring a ring by its
      key's word count made a run of rings grid by its FIRST member's label.

    Bars keep the floor (they write their words as a line beside a bar that
    stretches), and so does a chart (the generator measures no chart size)."""
    node = unit
    while True:
        if _is_drawn_date_chip(ctx, node) or _is_drawn_ring(ctx, node):
            return 0.0
        if len(node.children) != 1:
            break
        node = node.children[0]
    return LEAF_WIDTH.get(_length_category(unit) or "")


def column_padding_x(ctx: GeneratorContext, unit: MarkdownGroupNode) -> float:
    """``_unit_padding_x`` plus the ``### Dates`` card padding of a drawn chip.

    The chip card is the chip unit's own outermost wrap, painted with the
    ``### Dates`` style (``render_backgrounds._paint_style_for``), so a column
    that holds one needs that padding on top of the chip's measured text."""
    pad = _unit_padding_x(unit, ctx.theme)
    dp = _dp_theme(ctx)
    if dp is not None and _is_drawn_date_chip(ctx, unit):
        pad += dp.date_chip.chip.padding.x
    return pad


def _build_ring(ctx: GeneratorContext, node: MarkdownGroupNode) -> LayoutNode:
    """A circular bar (`unit_ratio` with Style: ring) as a card whose
    background paint is the arc (not a fill), wrapping two centered
    synthetic text leaves — mirrors the date chip's card-wrap.

    The value/unit are baked from the payload (uniform across all ring
    sources); the col carries the arc fraction for the renderer's paint."""
    p = dict(node.datapoint_payload or {})
    value = float(p.get("value", 0.0))
    mx = float(p.get("max", 0.0))
    dpth = _dp_theme(ctx)
    show_total = dpth.unit_ratio_show_total if dpth is not None else True
    show_key = dpth.unit_ratio_show_key if dpth is not None else True
    value_leaf = LayoutNode(
        type="-",
        ratios=[],
        children=[],
        content_id=None,
        render_properties={
            "ring_role": "value",
            "ring_text": (f"{value:g}/{mx:g}" if show_total else f"{value:g}"),
        },
    )
    unit_leaf = LayoutNode(
        type="-",
        ratios=[],
        children=[],
        content_id=None,
        render_properties={
            "ring_role": "unit",
            "ring_text": str(p.get("unit", "") or ""),
        },
    )
    leaves = [value_leaf, unit_leaf] if show_key else [value_leaf]
    col = LayoutNode(
        type="col",
        ratios=[1.0] * len(leaves),
        children=leaves,
        content_id=node.node_id or None,
        render_properties={"ring": {"value": value, "max": mx}},
    )
    col.is_card = True
    col.card_kind = "ring"
    return LayoutNode(type="row", ratios=[1.0], children=[col])


def _unit_ratio_is_ring(ctx: GeneratorContext) -> bool:
    dp = _dp_theme(ctx)
    return dp is not None and dp.unit_ratio_style == "ring"


def _bar_leaf(ctx: GeneratorContext, payload: dict | None, kind: str) -> LayoutNode:
    """Synthetic stretch-bar leaf (no content_id, like a gutter marker)."""
    return LayoutNode(
        type="-",
        ratios=[],
        children=[],
        content_id=None,
        render_properties={"datapoint_bar": {**dict(payload or {}), "kind": kind}},
    )


def _with_text_override(
    ctx: GeneratorContext, leaf: LayoutNode, text: str
) -> LayoutNode:
    """Keep a real leaf's type/style but replace only its visible text."""
    target = leaf
    while len(target.children) == 1:
        target = target.children[0]
    target.render_properties = {
        **(target.render_properties or {}),
        "text_override": text,
    }
    return leaf


def _text_override_w(
    ctx: GeneratorContext, node: MarkdownGroupNode, replacement: str
) -> float:
    """Measure replacement text with the original leaf's type/style."""
    measured_node = copy.copy(node)
    measured_node.content = replacement
    return _text_leaf_w(ctx, measured_node)


def _text_leaf_w(ctx: GeneratorContext, node: MarkdownGroupNode) -> float:
    """Measured single-line width of a text piece (for bar-row ratios).

    Ratios only matter in the renderer's overflow fallback — which the
    stretch bar leaf deliberately forces — so this mirrors
    ``_line_item_width``'s measure-else-category resolution."""
    if ctx.measure_line is not None:
        w = ctx.measure_line(node)
        if w is not None:
            return w
    if ctx.measure_width is not None:
        w = ctx.measure_width(node)
        if w is not None:
            return w
    return LEAF_WIDTH.get(_length_category(node) or "", 100.0)


def _bar_text_row(
    ctx: GeneratorContext,
    payload: dict | None,
    kind: str,
    text_leaves: list[LayoutNode],
    text_widths: list[float],
    available_width: float,
) -> LayoutNode:
    """Same-line row of the text leaves beside a stretch bar leaf.

    The bar's natural width is ``available`` (it is the flex member), which
    forces the renderer's ratio branch — so the ratios here ARE the layout:
    each text piece gets its measured width, the bar takes the remainder.
    Side per ``Ratio Bars → Text side`` ("right" = text right of the bar).
    """
    dpth = _dp_theme(ctx)
    text_side = dpth.ratio_bar.text_side if dpth is not None else "right"
    # The renderer's ratio branch insets one element gap per adjacency and
    # scales all ratios down accordingly — budget the real theme gap here
    # so a text ratio lands at its measured width, plus a small guard so
    # float rounding never wraps a trailing word.
    gap = (ctx.theme.elements.row_spacing or 0.0) if ctx.theme is not None else 8.0
    text_widths = [w + 3.0 for w in text_widths]
    remainder = max(
        available_width - sum(text_widths) - gap * len(text_widths),
        60.0,
    )
    bar = _bar_leaf(ctx, payload, kind)
    if text_side == "left":
        children = [*text_leaves, bar]
        ratios = [*text_widths, remainder]
    else:
        children = [bar, *text_leaves]
        ratios = [remainder, *text_widths]
    row = LayoutNode(type="row", ratios=ratios, children=children)
    row.line_split = True
    return row


def _bar_stack_col(
    ctx: GeneratorContext,
    text_part: LayoutNode,
    payload: dict | None,
    kind: str,
    position: str,
) -> LayoutNode:
    """col of [text part, full-width bar leaf], bar above or below."""
    bar = _bar_leaf(ctx, payload, kind)
    children = [bar, text_part] if position == "above" else [text_part, bar]
    return LayoutNode(type="col", ratios=[1.0, 1.0], children=children)


def _leaf_bar_display(
    ctx: GeneratorContext,
    node: MarkdownGroupNode,
    leaf: LayoutNode,
    available_width: float,
) -> LayoutNode | None:
    """Bar layout around a bar-family LEAF (bare ``4/8``,
    ``25/100 progress``, a single-leaf ``A of B``), keeping *leaf* — the
    untouched text leaf with its content_id — as the text member. None
    when the node is no bar-family leaf (or disabled / ring style)."""
    if not _dp_display_enabled(ctx, node):
        return None
    d = node.datapoint_display
    if d == "ratio_bar" or (d == "unit_ratio" and not _unit_ratio_is_ring(ctx)):
        kind = "ratio" if d == "ratio_bar" else "unit"
        text_width = _text_leaf_w(ctx, node)
        dpth = _dp_theme(ctx)
        if d == "ratio_bar":
            if dpth is not None and not dpth.unit_ratio_show_total:
                p = dict(node.datapoint_payload or {})
                text = f"{float(p.get('value', 0.0)):g}"
                _with_text_override(ctx, leaf, text)
                text_width = _text_override_w(ctx, node, text)
        else:
            if dpth is not None and (
                not dpth.unit_ratio_show_total or not dpth.unit_ratio_show_key
            ):
                p = dict(node.datapoint_payload or {})
                value = float(p.get("value", 0.0))
                mx = float(p.get("max", 0.0))
                text = f"{value:g}"
                if dpth.unit_ratio_show_total:
                    text += f"/{mx:g}"
                unit = str(p.get("unit", "") or "")
                if dpth.unit_ratio_show_key and unit:
                    text += f" {unit}"
                _with_text_override(ctx, leaf, text)
                text_width = _text_override_w(ctx, node, text)
        return _bar_text_row(
            ctx,
            node.datapoint_payload,
            kind,
            [leaf],
            [text_width],
            available_width,
        )
    return None


def _line_leaf(node: MarkdownGroupNode) -> LayoutNode:
    """Synthetic line-chart leaf carrying its points; the renderer draws it."""
    return LayoutNode(
        type="-",
        ratios=[],
        children=[],
        content_id=None,
        render_properties={"line_chart": dict(node.datapoint_payload or {})},
    )


def _lines_enabled(ctx: GeneratorContext) -> bool:
    ct = getattr(ctx.theme, "charts", None)
    return ct is not None and ct.line.enabled


def _drawn_chart(ctx: GeneratorContext, node: MarkdownGroupNode) -> bool:
    """Whether *node* is a chart container the theme draws: bars or lines."""
    if node.line_group:
        return _lines_enabled(ctx)
    return node.chart_group and _charts_enabled(ctx)


def _build_line_group(node: MarkdownGroupNode) -> LayoutNode:
    """Several lines on one axis → one drawn leaf carrying every series; the
    renderer draws the legend, the lines and the shared labels."""
    return LayoutNode(
        type="-",
        ratios=[],
        children=[],
        content_id=node.node_id or None,
        render_properties={"line_chart": dict(node.line_data or {})},
    )


def _build_chart(ctx: GeneratorContext, node: MarkdownGroupNode) -> LayoutNode:
    """Chart container → one synthetic leaf carrying the chart data.

    The renderer computes the whole geometry (orientation, bars, labels)
    from ``chart_data`` at the real width — nothing to lay out here.
    """
    if node.line_group:
        return _build_line_group(node)
    return LayoutNode(
        type="-",
        ratios=[],
        children=[],
        content_id=node.node_id or None,
        render_properties={"chart": node.chart_data},
    )
