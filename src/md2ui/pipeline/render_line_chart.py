"""The line chart leaf: ``Key: a → b → c`` drawn as one line over its points,
or a run of such items drawn as several lines on one axis, under a legend.

The points are spread evenly along the width, in the order written, and the
axis fits the data's range: a line does not start at zero, so prices that move
within a few percent still show their shape. A point written with ``(words)``
after it is labelled with them under the line and gets a dot, as the last point
does (only the last, under the theme's `Points: last`); where labels crowd, some are left out (``_shown_ticks``). A group's
legend wraps between entries. The area under each line takes the section
background keys, painted as every surface is (``_draw_areas``). The measured height and the painting both come
from ``line_chart_height``'s numbers, so the box and the drawing agree (ADR-400).
"""

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_chart import _chart_series_color
from md2ui.pipeline.render_colors import _replace_color
from md2ui.pipeline.render_fills import _paint_layered_fill, _replaced_gradient
from md2ui.pipeline.render_metrics import LINE_SCALE
from md2ui.pipeline.render_placeholders import theme_picture
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import TextStyle, Theme
from md2ui.pipeline.value_format import with_unit
from md2ui.utils.font_loader import make_font

_TICK_GAP = 4.0  # between the line's area and its tick labels
_LEGEND_GAP = 6.0  # between a group's legend and its lines
_LEGEND_SPACING = 14.0  # between one series' legend entry and the next


def _tick_style(theme: Theme) -> TextStyle:
    return theme.charts.label_text or theme.labels


def _series(data: dict) -> list[list[dict]]:
    """The points of every line *data* draws: one, or each series of a group."""
    if data.get("series"):
        return [list(s.get("points") or []) for s in data["series"]]
    return [list(data.get("points") or [])]


def _labels(data: dict) -> list[str | None]:
    """One label per position: a group's merged labels, a line's own ticks."""
    if data.get("series"):
        return list(data.get("labels") or [])
    return [p.get("tick") for p in data.get("points") or []]


def _legend_rows(
    data: dict, width: float, fonts: FontSet, theme: Theme
) -> list[list[tuple[int, str, float]]]:
    """A group's legend, as rows of ``(series, label, left x)``: each series'
    dot, name and last value as written (with its declared unit, as the
    theme's ``Value format`` shows it), wrapped to *width* between entries,
    never inside one. A single line has none (its key and last value are a row
    the generator built)."""
    ts = _tick_style(theme)
    font = make_font(fonts.typeface, ts.font_size)
    dot = ts.font_size * 0.64 + 5.0  # the dot and its gap to the name
    rows: list[list[tuple[int, str, float]]] = []
    x = width  # forces the first entry onto a new row
    for i, s in enumerate(data.get("series") or []):
        points = s.get("points") or [{}]
        last = with_unit(
            str(points[-1].get("text", "")),
            data.get("display_unit"),
            theme.charts.value_format,
        )
        label = f"{s.get('name', '')}  {last}"
        entry = dot + font.measureText(label)
        if x > 0 and x + entry > width:
            rows.append([])
            x = 0.0
        rows[-1].append((i, label, x))
        x += entry + _LEGEND_SPACING
    return rows


def _legend_h(rows: list, theme: Theme) -> float:
    if not rows:
        return 0.0
    return len(rows) * _tick_style(theme).font_size * LINE_SCALE + _LEGEND_GAP


def _area_h(data: dict, theme: Theme) -> float:
    """The lines' area: ``Group height`` for several lines, else ``Height``."""
    lt = theme.charts.line
    if data.get("series") and lt.group_height is not None:
        return lt.group_height
    return lt.height


def line_chart_height(data: dict, width: float, fonts: FontSet, theme: Theme) -> float:
    """The legend of a group, the lines' area, and a line of tick labels when
    any position has one."""
    rows = _legend_rows(data, width, fonts, theme)
    h = _legend_h(rows, theme) + _area_h(data, theme)
    if any(_labels(data)):
        h += _TICK_GAP + _tick_style(theme).font_size * LINE_SCALE
    return h


def _line_points(
    data: dict,
    x: float,
    y: float,
    width: float,
    theme: Theme,
    span: tuple[float, float] | None = None,
    height: float | None = None,
) -> list[tuple[float, float]]:
    """Where each point sits: evenly along *width*, lowest value at the bottom
    of the area and highest at its top -- of *span* when lines share an axis,
    else of the line's own values. The area is *height* tall, ``Height`` when
    None. Inset by half a dot, so neither the first
    point's dot nor the highest one is cut at the box's edge."""
    lt = theme.charts.line
    values = [float(p["value"]) for p in data.get("points") or []]
    if len(values) < 2:
        return []
    lo, hi = span or (min(values), max(values))
    inset = max(lt.point_size, lt.width) / 2.0
    left, right = x + inset, x + width - inset
    top, bottom = y + inset, y + (height or lt.height) - inset
    step = (right - left) / (len(values) - 1)

    def value_y(v: float) -> float:
        if hi == lo:
            return (top + bottom) / 2.0  # a flat line sits mid-area
        return bottom - (v - lo) / (hi - lo) * (bottom - top)

    return [(left + i * step, value_y(v)) for i, v in enumerate(values)]


def _draw_legend(
    canvas: skia.Canvas,
    box: LayoutBox,
    rows: list[list[tuple[int, str, float]]],
    colors: list[int],
    fonts: FontSet,
    theme: Theme,
) -> None:
    """Each entry where ``_legend_rows`` placed it, its dot in its line's colour."""
    ts = _tick_style(theme)
    font = make_font(fonts.typeface, ts.font_size)
    text = skia.Paint(
        Color=_replace_color(ts.color, box.bg_stack, theme), AntiAlias=True
    )
    radius = ts.font_size * 0.32
    line_h = ts.font_size * LINE_SCALE
    for r, row in enumerate(rows):
        top = box.y + r * line_h
        for i, label, lx in row:
            x = box.x + lx
            dot = skia.Paint(Color=colors[i], AntiAlias=True)
            canvas.drawCircle(x + radius, top + line_h / 2.0, radius, dot)
            canvas.drawString(
                label, x + radius * 2.0 + 5.0, top + ts.font_size, font, text
            )


def draw_line_chart(
    canvas: skia.Canvas,
    box: LayoutBox,
    data: dict,
    fonts: FontSet,
    theme: Theme,
) -> None:
    lt = theme.charts.line
    series = _series(data)
    values = [float(p["value"]) for points in series for p in points]
    if not values:
        return
    span = (min(values), max(values))
    rows = _legend_rows(data, box.width, fonts, theme)
    if data.get("series"):
        colors = [
            _chart_series_color(theme, i, box.bg_stack) for i in range(len(series))
        ]
        _draw_legend(canvas, box, rows, colors, fonts, theme)
    elif lt.color is not None:
        colors = [_replace_color(lt.color, box.bg_stack, theme, "fill")]
    else:
        colors = [_chart_series_color(theme, 0, box.bg_stack)]
    top = box.y + _legend_h(rows, theme)
    area = _area_h(data, theme)
    lines = [
        _line_points({"points": points}, box.x, top, box.width, theme, span, area)
        for points in series
    ]
    if not all(lines):
        return
    _draw_areas(canvas, box, lines, top, area, theme)
    stroke = dict(
        Style=skia.Paint.kStroke_Style,
        StrokeWidth=lt.width,
        StrokeJoin=skia.Paint.kRound_Join,
        StrokeCap=skia.Paint.kRound_Cap,
        AntiAlias=True,
    )
    for pts, color in zip(lines, colors):
        path = skia.Path()
        path.moveTo(*pts[0])
        for px, py in pts[1:]:
            path.lineTo(px, py)
        canvas.drawPath(path, skia.Paint(Color=color, **stroke))
    labels = _labels(data)
    ts = _tick_style(theme)
    font = make_font(fonts.typeface, ts.font_size)
    placed: list[tuple[int, str, float]] = []  # (position, label, left x)
    for i, label in enumerate(labels):
        if label:
            lw = font.measureText(label)
            lx = min(max(lines[0][i][0] - lw / 2.0, box.x), box.x + box.width - lw)
            placed.append((i, label, lx))
    spans = [(lx, lx + font.measureText(label)) for _, label, lx in placed]
    shown = [placed[k] for k in _shown_ticks(spans)]
    if lt.point_size > 0:
        # A dot marks each line's latest value and, unless the theme keeps
        # dots to the last point (`Points: last`), each label that is drawn.
        labelled = [i for i, _, _ in shown] if lt.points == "labelled" else []
        for pts, color in zip(lines, colors):
            dot = skia.Paint(Color=color, AntiAlias=True)
            for i in sorted({*labelled, len(pts) - 1}):
                canvas.drawCircle(*pts[i], lt.point_size / 2.0, dot)
    paint = skia.Paint(
        Color=_replace_color(ts.color, box.bg_stack, theme), AntiAlias=True
    )
    baseline = top + area + _TICK_GAP + ts.font_size
    for _, label, lx in shown:
        canvas.drawString(label, lx, baseline, font, paint)


def _draw_areas(
    canvas: skia.Canvas,
    box: LayoutBox,
    lines: list[list[tuple[float, float]]],
    top: float,
    area: float,
    theme: Theme,
) -> None:
    """The shape under each line, down to the bottom of the area, filled by the
    layered fill a card uses. A group's lines take the colours in turn, and the
    gradient and image span the whole area, so every line's shape shows the same
    part of them at the same height."""
    fill = theme.charts.line.fill
    if not (fill.bg_colors or fill.gradient or fill.bg_image or fill.shadows):
        return
    rect = skia.Rect.MakeXYWH(box.x, top, box.width, area)
    gradient = _replaced_gradient(fill.gradient, box.bg_stack, theme)
    for i, pts in enumerate(lines):
        path = skia.Path()
        path.moveTo(pts[0][0], top + area)
        for px, py in pts:
            path.lineTo(px, py)
        path.lineTo(pts[-1][0], top + area)
        path.close()
        color = fill.bg_colors[i % len(fill.bg_colors)] if fill.bg_colors else None
        _paint_layered_fill(
            canvas,
            rect,
            bg_color=(
                _replace_color(color, box.bg_stack, theme, "fill")
                if color is not None
                else None
            ),
            image=theme_picture(fill.bg_image),
            gradient=gradient,
            shadows=fill.shadows,
            outline=path,
        )


def _shown_ticks(spans: list[tuple[float, float]]) -> list[int]:
    """Which tick labels draw, as indexes into *spans* (each label's left and
    right x, in point order), so that none runs into another.

    The ends come first: the last label says where the line is now and the
    first where it starts, so when two cannot both fit only the last stays.
    The middle ones then fill in by halving the run between labels already
    placed, so labels left out are spread along the line rather than piled at
    one end. A label is left out, never shortened or turned."""
    n = len(spans)
    order: list[int] = []
    if n:
        order = [n - 1, 0]
        ranges = [(0, n - 1)]
        while ranges:
            lo, hi = ranges.pop(0)
            if hi - lo < 2:
                continue
            mid = (lo + hi) // 2
            order.append(mid)
            ranges += [(lo, mid), (mid, hi)]
    placed: list[int] = []
    for k in dict.fromkeys(order):
        left, right = spans[k]
        if all(
            right + _TICK_GAP <= spans[j][0] or spans[j][1] + _TICK_GAP <= left
            for j in placed
        ):
            placed.append(k)
    return sorted(placed)
