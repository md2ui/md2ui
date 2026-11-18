"""The chart leaf: a run of ``Key: value`` rows in one unit drawn as bars.

Owns both halves of one picture — the geometry (``ChartPlan``: orientation,
scale, heights, where vertical bars go) and the painting that follows it. They
live together because a chart's measured box and its drawing must come from the
same plan (ADR-400): ``render_measure`` asks the plan for the leaf's height, and
``_draw_chart`` paints from the same plan at the same width.
"""

import dataclasses
import math
import re

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_colors import _replace_color
from md2ui.pipeline.render_fills import (
    _DEFAULT_BAR_FILL,
    _DEFAULT_BAR_TRACK,
    _paint_layered_fill,
    _replaced_gradient,
)
from md2ui.pipeline.render_metrics import LINE_SCALE
from md2ui.pipeline.render_placeholders import theme_picture
from md2ui.pipeline.render_shadows import draw_stroke
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import TextStyle, Theme
from md2ui.pipeline.theme_model import GREY_DARK, GREY_LIGHT, GREY_MID
from md2ui.pipeline.value_format import with_unit
from md2ui.utils.font_loader import make_font, weight_from_str


_CHART_ROW_GAP = 12.0  # vertical gap between horizontal chart rows
_CHART_VERTICAL_H = 140.0  # bar area height in vertical orientation
_CHART_COLUMN_W = 240.0  # min column width before stacking into columns
_CHART_MIN_SLOT = 44.0  # min per-bar slot width for vertical orientation
_CHART_SERIES_GAP = 2.0  # gap between one row's series bars, vertical orientation
_CHART_AXIS_GAP = 6.0  # between the widest tick label and the bars


@dataclasses.dataclass
class ChartPlan:
    """Resolved chart geometry decisions for one ``chart`` leaf at a width.

    Mirrors ``TablePlan``'s role: measurement (``_leaf_height``) and drawing
    (``_draw_chart``) share it so the reserved box always fits the drawing.
    """

    orientation: str  # "horizontal" | "vertical" | "columns"
    columns: int
    labels: list[str]
    values: list[list[float]]  # rows x series
    series: list[str] | None
    scale_max: float
    legend_h: float
    label_line_h: float
    row_h: float  # one horizontal row (label line + bars)
    height: float
    # Below zero only when a value is: the scale then spans the data, and the
    # bars diverge from a zero line inside it (``_chart_span``). Horizontal
    # rows that mix signs centre it.
    scale_min: float = 0.0
    # A vertical chart cut into ticks (``### Chart Grid``): the values its lines
    # and labels sit at, the gutter its labels take on the left, and the room
    # above the bars for the top label's upper half.
    ticks: list[float] = dataclasses.field(default_factory=list)
    axis_w: float = 0.0
    top_pad: float = 0.0
    # Each row's values as written, which its value label draws, and the
    # unit its author declared for bare values (``value_format``).
    texts: list[list[str]] = dataclasses.field(default_factory=list)
    display_unit: str | None = None


def _chart_span(plan: ChartPlan, v: float) -> tuple[float, float]:
    """Where a bar of value *v* runs along the value axis, as fractions of it:
    from zero to *v*, the lower end first. Every orientation places its bars
    with this, so a value lands at the same fraction whichever way it is drawn.
    """
    span = plan.scale_max - plan.scale_min
    zero = max(0.0, min(1.0, (0.0 - plan.scale_min) / span))
    end = max(0.0, min(1.0, (v - plan.scale_min) / span))
    return min(zero, end), max(zero, end)


def _chart_scale(
    values: list[list[float]], unit: str | None, percent_scale: str = "100"
) -> tuple[float, float]:
    """The ``(min, max)`` a chart's bars are measured against.

    Percent data scales against 100 so bars read as progress, unless the
    theme's ``Percent scale: peak`` asks for a comparison; every other unit
    scales against the data peak. A value below zero makes it change data
    instead: the scale is the data's own range, zero included.
    """
    flat = [v for row in values for v in row]
    peak = max(flat, default=0.0)
    least = min(flat, default=0.0)
    if least < 0.0:
        return least, max(peak, 0.0)
    progress = unit == "%" and percent_scale == "100" and peak <= 100.0
    return 0.0, (100.0 if progress else max(peak, 1.0))


def _chart_ticks(lo: float, hi: float, count: int) -> list[float]:
    """Round values from at or below *lo* to at or above *hi*, about *count*
    steps apart. Each is a multiple of the step, so zero is always one."""
    raw = (hi - lo) / max(1, count)
    mag = 10.0 ** math.floor(math.log10(raw))
    step = next(
        m * mag for m in (1.0, 2.0, 2.5, 5.0, 10.0) if m * mag >= raw * (1 - 1e-9)
    )
    first = math.floor(lo / step + 1e-9)
    last = math.ceil(hi / step - 1e-9)
    # `+ 0.0` turns a -0.0 into the 0 its label should print.
    return [round(i * step, 10) + 0.0 for i in range(first, last + 1)]


# A value's leading symbol, its figure with an optional magnitude letter, and
# whatever follows: `$`, `1.2`, `M`, `` / ``, `200`, ``, ` EUR`.
_WRITTEN_VALUE = re.compile(r"^(\D*?)[-−+]?\d[\d.,]*([KMB](?![A-Za-z]))?(.*)$")
_MAGNITUDES = ((1e9, "B"), (1e6, "M"), (1e3, "K"))


def _chart_tick(t: float, data: dict, theme: Theme) -> str:
    """A tick's label: in the values' own unit, or bare with the unit the
    author declared, as the theme's ``Value format`` places it."""
    label = _chart_tick_label(t, data.get("unit"), _chart_sample(data))
    return with_unit(label, data.get("display_unit"), theme.charts.value_format)


def _chart_tick_label(t: float, unit: str | None, sample: str = "") -> str:
    """A tick's label, in the unit the chart's values are written in: the
    symbol and unit word of *sample*, one of them as written (`40%`, `$200`,
    `200 EUR`, `5K`)."""
    m = _WRITTEN_VALUE.match(sample) if unit != "%" else None
    if m is None:
        return f"{t:g}{'%' if unit == '%' else ''}"
    prefix, magnitude, suffix = m.group(1).lstrip("-−+"), m.group(2), m.group(3)
    a = abs(t)
    figure = f"{a:.10g}"
    if magnitude or unit == "magnitude":
        size, letter = next(((s, k) for s, k in _MAGNITUDES if a >= s), (1.0, ""))
        figure = f"{a / size:.10g}{letter}"
    return ("-" if t < 0 else "") + prefix + figure + suffix


def _chart_sample(data: dict) -> str:
    """One of the chart's values as written, for its tick labels' unit."""
    rows = data.get("rows") or [{}]
    return next(iter(rows[0].get("texts") or []), "")


def _chart_axis(data: dict, fonts: FontSet, theme: Theme) -> tuple[list[float], float]:
    """A vertical chart's ticks and the gutter its tick labels take, by
    ``### Chart Grid``: no ticks when nothing is drawn at them, no gutter when
    their labels are off."""
    grid = theme.charts.grid
    if not grid.scaled:
        return [], 0.0
    values = [
        [float(v) for v in (r.get("values") or [0.0])] for r in data.get("rows") or []
    ]
    unit = data.get("unit")
    scale = _chart_scale(values, unit, theme.charts.percent_scale)
    ticks = _chart_ticks(*scale, grid.ticks)
    if not grid.axis_labels:
        return ticks, 0.0
    font = make_font(fonts.typeface, _chart_tick_style(theme).font_size)
    widest = max(font.measureText(_chart_tick(t, data, theme)) for t in ticks)
    return ticks, widest + _CHART_AXIS_GAP


def _chart_tick_style(theme: Theme) -> TextStyle:
    ct = theme.charts
    return ct.grid.text or ct.value_text or theme.labels


def _chart_vertical_min_width(data: dict, fonts: FontSet, theme: Theme) -> float | None:
    """The narrowest width at which a chart still draws VERTICAL bars.

    Below it the same data turns on its side — horizontal rows, or side-by-side
    columns of them — which is a different picture, not a narrower one. So it is
    a real minimum for anything sizing a block that holds a chart: a stacked
    section should wrap to the next row before its chart flips. The tick-label
    gutter, when there is one, is part of it.

    ``None`` when there is no flip to protect: four rows or fewer read best as
    horizontal bars and are drawn that way at every width.
    """
    rows = data.get("rows") or []
    n = len(rows)
    if n <= 4:
        return None
    label_ts = theme.charts.label_text or theme.labels
    label_font = make_font(fonts.typeface, label_ts.font_size)
    widest = max(
        (label_font.measureText(str(r.get("label", ""))) for r in rows), default=0.0
    )
    # Each row owns a slot: wide enough for its own label, and never under the
    # floor that keeps a bar readable.
    slots = n * max(_CHART_MIN_SLOT, widest + 8.0)
    axis_w = _chart_axis(data, fonts, theme)[1]
    ct = theme.charts
    if ct.bar_width != "fill":
        return slots + axis_w
    # Filled bars may not go under Bar thickness, so they need their groups
    # plus the Bar spacing between them.
    ns = max((len(r.get("values") or [0.0]) for r in rows), default=1)
    group = ns * ct.bar_thickness + (ns - 1) * _CHART_SERIES_GAP
    return max(slots, n * group + (n - 1) * ct.bar_spacing) + axis_w


def _chart_plan_for(
    data: dict, width: float, fonts: FontSet, theme: Theme
) -> ChartPlan:
    ct = theme.charts
    rows = data.get("rows") or []
    labels = [str(r.get("label", "")) for r in rows]
    values = [[float(v) for v in (r.get("values") or [0.0])] for r in rows]
    series = data.get("series")
    n = max(1, len(rows))
    ns = max((len(v) for v in values), default=1)
    scale_min, scale_max = _chart_scale(values, data.get("unit"), ct.percent_scale)

    label_ts = ct.label_text or theme.labels
    value_ts = ct.value_text or theme.labels
    label_line_h = max(label_ts.font_size, value_ts.font_size) * LINE_SCALE
    legend_h = label_line_h + 6.0 if series else 0.0
    chart_track_h = ct.bar_thickness + ct.track.padding.y
    bars_h = ns * chart_track_h + (ns - 1) * 2.0
    row_h = label_line_h + 4.0 + bars_h

    # Orientation: few rows read best as horizontal bars; many rows go
    # vertical when each label/bar gets enough width; otherwise the
    # horizontal rows stack into side-by-side columns. The width that buys
    # vertical is asked of ``_chart_vertical_min_width``, so whoever SIZES a
    # block holding a chart is working from the same number that decides what
    # the chart draws.
    vertical_min = _chart_vertical_min_width(data, fonts, theme)
    if vertical_min is None:
        orientation, columns = "horizontal", 1
    elif width >= vertical_min:
        orientation, columns = "vertical", 1
    else:
        columns = max(1, int(width // _CHART_COLUMN_W))
        orientation = "columns" if columns > 1 else "horizontal"

    ticks: list[float] = []
    axis_w = top_pad = 0.0
    if orientation == "vertical":
        ticks, axis_w = _chart_axis(data, fonts, theme)
        if ticks:
            # The scale reaches the round values its lines are drawn at.
            scale_min, scale_max = ticks[0], ticks[-1]
        if axis_w:
            top_pad = _chart_tick_style(theme).font_size / 2.0
        height = legend_h + top_pad + _CHART_VERTICAL_H + 4.0 + label_line_h
    else:
        if scale_min < 0.0 < scale_max:
            # Rows that mix gains and losses share one zero in the middle of
            # their tracks, so each side reads against the same reach.
            reach = max(-scale_min, scale_max)
            scale_min, scale_max = -reach, reach
        rows_per_col = -(-n // columns)  # ceil
        height = legend_h + rows_per_col * row_h + (rows_per_col - 1) * _CHART_ROW_GAP
    return ChartPlan(
        orientation=orientation,
        columns=columns,
        labels=labels,
        values=values,
        series=list(series) if series else None,
        scale_max=scale_max,
        scale_min=scale_min,
        ticks=ticks,
        axis_w=axis_w,
        top_pad=top_pad,
        texts=[[str(t) for t in r.get("texts") or []] for r in rows],
        display_unit=data.get("display_unit"),
        legend_h=legend_h,
        label_line_h=label_line_h,
        row_h=row_h,
        height=height,
    )


def _chart_vertical_bars(
    plan: ChartPlan, x: float, width: float, base_y: float, theme: Theme
) -> tuple[list[tuple[int, int, skia.Rect]], list[tuple[float, float]]]:
    """Where a vertical chart's bars go: ``(row, series, rect)`` for every bar,
    and each row's label span ``(left, width)`` to centre its label in.

    ``Bar width: fixed`` centres a group of ``Bar thickness`` bars in an equal
    slot per row, and a bar is never shorter than it is wide, so its rounded
    top stays whole. ``fill`` widens the groups to share the whole width with
    ``Bar spacing`` between them; ``Bar thickness`` is then the narrowest and
    the shortest a bar may be.
    """
    ct = theme.charts
    n = max(1, len(plan.labels))
    ns = max((len(v) for v in plan.values), default=1)
    gap = _CHART_SERIES_GAP
    least = ns * ct.bar_thickness + (ns - 1) * gap
    if ct.bar_width == "fill":
        group_w = max(least, (width - (n - 1) * ct.bar_spacing) / n)
        spans = [(x + i * (group_w + ct.bar_spacing), group_w) for i in range(n)]
        starts = [left for left, _ in spans]
    else:
        slot_w = width / n
        group_w = min(slot_w * 0.7, least)
        spans = [(x + i * slot_w, slot_w) for i in range(n)]
        starts = [left + (slot_w - group_w) / 2.0 for left, _ in spans]
    bar_w = max(3.0, (group_w - (ns - 1) * gap) / ns)
    floor_h = ct.bar_thickness if ct.bar_width == "fill" else bar_w
    zero_y = _chart_zero_y(plan, base_y)
    bars = []
    for i, row in enumerate(plan.values):
        for s, v in enumerate(row):
            lo, hi = _chart_span(plan, v)
            bh = max(floor_h, _CHART_VERTICAL_H * (hi - lo))
            if plan.scale_min < 0.0:
                # The floor may not push a bar out of the chart past its edge.
                room = (
                    base_y - zero_y
                    if v < 0.0
                    else zero_y - (base_y - _CHART_VERTICAL_H)
                )
                bh = min(bh, max(_CHART_VERTICAL_H * (hi - lo), room))
            top = zero_y if v < 0.0 else zero_y - bh
            rect = skia.Rect.MakeXYWH(starts[i] + s * (bar_w + gap), top, bar_w, bh)
            bars.append((i, s, rect))
    return bars, spans


def _chart_zero_y(plan: ChartPlan, base_y: float) -> float:
    """The y of zero in a vertical chart whose bar area ends at *base_y*: the
    bottom edge, unless the chart holds a value below zero."""
    return _chart_value_y(plan, base_y, 0.0)


def _chart_value_y(plan: ChartPlan, base_y: float, v: float) -> float:
    """The y a value sits at in a vertical chart whose bar area ends at *base_y*."""
    span = plan.scale_max - plan.scale_min
    return base_y - _CHART_VERTICAL_H * max(0.0, min(1.0, (v - plan.scale_min) / span))


# Fallback series colors cycled when THEME.md sets no ## Charts series list.
_DEFAULT_SERIES_COLORS = (
    _DEFAULT_BAR_FILL,
    GREY_MID,
    GREY_LIGHT,
    GREY_DARK,
)
_CHART_COL_GAP = 24.0  # gap between stacked columns


def _chart_series_color(
    theme: Theme,
    idx: int,
    bg_stack: "tuple[int | str, ...]" = (),
) -> int:
    ct = theme.charts
    if ct.series_colors:
        color = ct.series_colors[idx % len(ct.series_colors)]
    elif idx == 0 and ct.bar.bg_colors:
        color = ct.bar.bg_colors[0]
    else:
        color = _DEFAULT_SERIES_COLORS[idx % len(_DEFAULT_SERIES_COLORS)]
    return _replace_color(color, bg_stack, theme, "fill")


def _chart_bar_color(
    theme: Theme, idx: int, v: float, bg_stack: "tuple[int | str, ...]"
) -> int:
    """A bar's fill: ``Negative color`` below zero when the theme sets one,
    otherwise its series colour."""
    neg = theme.charts.negative_color
    if v < 0.0 and neg is not None:
        return _replace_color(neg, bg_stack, theme, "fill")
    return _chart_series_color(theme, idx, bg_stack)


def _chart_line(
    canvas: skia.Canvas,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    theme: Theme,
    bg_stack: "tuple[int | str, ...]",
    dashed: bool = False,
) -> None:
    """One of the chart's lines (zero, grid) in the ``### Chart Grid`` style;
    a grid line takes its ``Line dash``, the zero line never does."""
    grid = theme.charts.grid
    paint = skia.Paint(
        Color=_replace_color(grid.color, bg_stack, theme, "stroke"),
        Style=skia.Paint.kStroke_Style,
        StrokeWidth=grid.width,
        AntiAlias=True,
    )
    if dashed and grid.dash:
        # Skia takes on/off pairs; one length means equal dashes and gaps.
        dash = grid.dash * 2 if len(grid.dash) % 2 else grid.dash
        paint.setPathEffect(skia.DashPathEffect.Make(dash, 0.0))
    canvas.drawLine(x0, y0, x1, y1, paint)


def _draw_chart_grid(
    canvas: skia.Canvas,
    plan: ChartPlan,
    x: float,
    width: float,
    base_y: float,
    spans: list[tuple[float, float]],
    data: dict,
    fonts: FontSet,
    theme: Theme,
    bg_stack: "tuple[int | str, ...]",
) -> None:
    """A vertical chart's grid, behind its bars: a line at each tick, a line at
    each edge of each row's slot, and the tick labels in the gutter left of *x*."""
    grid = theme.charts.grid
    top = base_y - _CHART_VERTICAL_H
    if grid.horizontal:
        for t in plan.ticks:
            ty = _chart_value_y(plan, base_y, t)
            _chart_line(canvas, x, ty, x + width, ty, theme, bg_stack, dashed=True)
    if grid.vertical and spans:
        edges = [spans[0][0], spans[-1][0] + spans[-1][1]]
        edges[1:1] = [
            (spans[i - 1][0] + spans[i - 1][1] + spans[i][0]) / 2.0
            for i in range(1, len(spans))
        ]
        for ex in edges:
            _chart_line(canvas, ex, top, ex, base_y, theme, bg_stack, dashed=True)
    if plan.axis_w:
        ts = _chart_tick_style(theme)
        font = make_font(fonts.typeface, ts.font_size)
        metrics = font.getMetrics()
        paint = skia.Paint(
            Color=_replace_color(ts.color, bg_stack, theme), AntiAlias=True
        )
        for t in plan.ticks:
            label = _chart_tick(t, data, theme)
            ty = _chart_value_y(plan, base_y, t)
            canvas.drawString(
                label,
                x - _CHART_AXIS_GAP - font.measureText(label),
                ty - (metrics.fAscent + metrics.fDescent) / 2.0,
                font,
                paint,
            )


def _chart_bar_rect(
    canvas: skia.Canvas,
    rect: "skia.Rect",
    color: int,
    theme: Theme,
    radius: float,
    bg_stack: "tuple[int | str, ...]",
) -> None:
    ct = theme.charts
    _paint_layered_fill(
        canvas,
        rect,
        bg_color=color,
        image=theme_picture(ct.bar.bg_image),
        gradient=_replaced_gradient(ct.bar.gradient, bg_stack, theme),
        corner_radius=radius,
        shadows=ct.bar.shadows,
    )
    if ct.bar.stroke_width > 0 and ct.bar.stroke_color is not None:
        stroke_color = _replace_color(ct.bar.stroke_color, bg_stack, theme, "stroke")
        draw_stroke(
            canvas,
            rect,
            radius,
            skia.Paint(
                Color=stroke_color,
                Style=skia.Paint.kStroke_Style,
                StrokeWidth=ct.bar.stroke_width,
                AntiAlias=True,
            ),
            ct.bar.stroke_align,
        )


def _draw_chart_legend(
    canvas: skia.Canvas,
    x: float,
    y: float,
    plan: ChartPlan,
    fonts: FontSet,
    theme: Theme,
    bg_stack: "tuple[int | str, ...]",
) -> None:
    label_ts = theme.charts.label_text or theme.labels
    font = make_font(fonts.typeface, label_ts.font_size)
    ink = _replace_color(label_ts.color, bg_stack, theme)
    cx = x
    dot_r = label_ts.font_size * 0.32
    for i, name in enumerate(plan.series or []):
        cy = y + plan.label_line_h / 2.0
        canvas.drawCircle(
            cx + dot_r,
            cy,
            dot_r,
            skia.Paint(
                Color=_chart_series_color(theme, i, bg_stack),
                Style=skia.Paint.kFill_Style,
                AntiAlias=True,
            ),
        )
        tx = cx + dot_r * 2.0 + 5.0
        canvas.drawString(
            name,
            tx,
            y + label_ts.font_size,
            font,
            skia.Paint(Color=ink, AntiAlias=True),
        )
        if plan.display_unit and i == len(plan.series or []) - 1:
            # The unit the series header declared closes the legend.
            canvas.drawString(
                f"({plan.display_unit})",
                tx + font.measureText(name) + 14.0,
                y + label_ts.font_size,
                font,
                skia.Paint(Color=ink, AntiAlias=True),
            )
        cx = tx + font.measureText(name) + 14.0


def _draw_chart_rows(
    canvas: skia.Canvas,
    x: float,
    y: float,
    w: float,
    plan: ChartPlan,
    row_indices: range,
    fonts: FontSet,
    theme: Theme,
    bg_stack: "tuple[int | str, ...]",
) -> None:
    """Horizontal rows: label left / value right on one line, bar(s) below."""
    ct = theme.charts
    label_ts = ct.label_text or theme.labels
    value_ts = ct.value_text or theme.labels
    l_font = make_font(fonts.typeface, label_ts.font_size)
    v_tf = (
        fonts.bold if weight_from_str(value_ts.font_weight) >= 700 else fonts.typeface
    )
    v_font = make_font(v_tf, value_ts.font_size)
    label_ink = _replace_color(label_ts.color, bg_stack, theme)
    value_ink = _replace_color(value_ts.color, bg_stack, theme)
    track_color = ct.track.bg_colors[0] if ct.track.bg_colors else _DEFAULT_BAR_TRACK
    track_color = _replace_color(track_color, bg_stack, theme, "fill")
    bar_radius = ct.bar.corner_radius
    track_radius = ct.track.corner_radius
    pad = ct.track.padding
    track_h = ct.bar_thickness + pad.y
    ry = y
    for i in row_indices:
        canvas.drawString(
            plan.labels[i],
            x,
            ry + label_ts.font_size,
            l_font,
            skia.Paint(Color=label_ink, AntiAlias=True),
        )
        shown = plan.texts[i] if i < len(plan.texts) else []
        fmt = theme.charts.value_format
        vtext = ", ".join(with_unit(t, plan.display_unit, fmt) for t in shown)
        vtext = vtext or ", ".join(f"{v:g}%" for v in plan.values[i])
        vw = v_font.measureText(vtext)
        canvas.drawString(
            vtext,
            x + w - vw,
            ry + value_ts.font_size,
            v_font,
            skia.Paint(Color=value_ink, AntiAlias=True),
        )
        by = ry + plan.label_line_h + 4.0
        for s, v in enumerate(plan.values[i]):
            track = skia.Rect.MakeXYWH(x, by, w, track_h)
            if ct.track_enabled:
                _paint_layered_fill(
                    canvas,
                    track,
                    bg_color=track_color,
                    image=theme_picture(ct.track.bg_image),
                    gradient=_replaced_gradient(ct.track.gradient, bg_stack, theme),
                    corner_radius=track_radius,
                    shadows=ct.track.shadows,
                )
            if (
                ct.track_enabled
                and ct.track.stroke_width > 0
                and ct.track.stroke_color is not None
            ):
                draw_stroke(
                    canvas,
                    track,
                    track_radius,
                    skia.Paint(
                        Color=_replace_color(
                            ct.track.stroke_color, bg_stack, theme, "stroke"
                        ),
                        Style=skia.Paint.kStroke_Style,
                        StrokeWidth=ct.track.stroke_width,
                        AntiAlias=True,
                    ),
                    ct.track.stroke_align,
                )
            lo, hi = _chart_span(plan, v)
            inner = max(0.0, w - pad.x)
            left = x + pad.left
            if plan.scale_min < 0.0 < plan.scale_max:
                # Losses alone run from the track's right edge, which is zero.
                zero_x = left + inner * _chart_span(plan, 0.0)[0]
                _chart_line(canvas, zero_x, by, zero_x, by + track_h, theme, bg_stack)
            if hi > lo:
                length = min(max(ct.bar_thickness, inner * (hi - lo)), inner)
                # The floor grows a short bar away from zero, inside the track.
                if v < 0.0:
                    start = left + inner * hi - length
                    if start < left:
                        start = left
                else:
                    start = left + inner * lo
                    if start + length > left + inner:
                        start = left + inner - length
                fill = skia.Rect.MakeXYWH(
                    start,
                    by + pad.top,
                    length,
                    ct.bar_thickness,
                )
                _chart_bar_rect(
                    canvas,
                    fill,
                    _chart_bar_color(theme, s, v, bg_stack),
                    theme,
                    bar_radius,
                    bg_stack,
                )
            by += track_h + 2.0
        ry += plan.row_h + _CHART_ROW_GAP


def _draw_chart(
    canvas: skia.Canvas,
    box: LayoutBox,
    data: dict,
    fonts: FontSet,
    theme: Theme,
) -> None:
    """One chart leaf: horizontal rows, vertical bars, or stacked columns —
    decided by ``_chart_plan_for`` at this box's real width. ``mode: line``
    falls back to bars until a line mode exists."""
    plan = _chart_plan_for(data, box.width, fonts, theme)
    ct = theme.charts
    x, y = box.x, box.y
    if plan.legend_h > 0.0:
        _draw_chart_legend(canvas, x, y, plan, fonts, theme, box.bg_stack)
        y += plan.legend_h

    n = len(plan.labels)
    if plan.orientation == "vertical":
        label_ts = ct.label_text or theme.labels
        l_font = make_font(fonts.typeface, label_ts.font_size)
        base_y = y + plan.top_pad + _CHART_VERTICAL_H
        bx, bw = x + plan.axis_w, box.width - plan.axis_w
        bars, spans = _chart_vertical_bars(plan, bx, bw, base_y, theme)
        _draw_chart_grid(
            canvas,
            plan,
            bx,
            bw,
            base_y,
            spans,
            data,
            fonts,
            theme,
            box.bg_stack,
        )
        if plan.scale_min < 0.0:
            zero_y = _chart_zero_y(plan, base_y)
            _chart_line(canvas, bx, zero_y, bx + bw, zero_y, theme, box.bg_stack)
        for i, s, rect in bars:
            _chart_bar_rect(
                canvas,
                rect,
                _chart_bar_color(theme, s, plan.values[i][s], box.bg_stack),
                theme,
                ct.bar.corner_radius,
                box.bg_stack,
            )
        for label, (left, span_w) in zip(plan.labels, spans):
            lw = l_font.measureText(label)
            canvas.drawString(
                label,
                left + (span_w - lw) / 2.0,
                base_y + 4.0 + label_ts.font_size,
                l_font,
                skia.Paint(
                    Color=_replace_color(label_ts.color, box.bg_stack, theme),
                    AntiAlias=True,
                ),
            )
        return

    if plan.orientation == "columns":
        k = plan.columns
        col_w = (box.width - (k - 1) * _CHART_COL_GAP) / k
        rows_per_col = -(-n // k)
        for c in range(k):
            start = c * rows_per_col
            stop = min(n, start + rows_per_col)
            if start >= stop:
                break
            _draw_chart_rows(
                canvas,
                x + c * (col_w + _CHART_COL_GAP),
                y,
                col_w,
                plan,
                range(start, stop),
                fonts,
                theme,
                box.bg_stack,
            )
        return

    _draw_chart_rows(
        canvas,
        x,
        y,
        box.width,
        plan,
        range(n),
        fonts,
        theme,
        box.bg_stack,
    )
