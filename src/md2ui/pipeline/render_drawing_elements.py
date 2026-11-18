"""Shared geometry and painting for non-text ``drawing_element`` leaves."""

import dataclasses
from typing import Callable

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_backgrounds import _opaque_or_none, _push_bg
from md2ui.pipeline.render_colors import _replace_color
from md2ui.pipeline.render_counts import count_size, is_count, muted_paint
from md2ui.pipeline.render_element_paint import _paint_style, _stroke_paint
from md2ui.pipeline.render_glyph_faces import glyph_advance
from md2ui.pipeline.render_shadows import draw_stroke, paint_shadows, shape_path
from md2ui.pipeline.render_style import FontSet, _emoji_glyph_font, _resolve_h_align
from md2ui.pipeline.render_text_paint import draw_glyph_runs
from md2ui.pipeline.theme import SectionStyle, Theme
from md2ui.pipeline.theme_model import (
    GREY_INK,
    GREY_LIGHT,
    GREY_MID,
    GREY_TRACK,
    GREY_WHITE,
)
from md2ui.utils.font_loader import make_font


@dataclasses.dataclass(frozen=True)
class TaskControlGeometry:
    width: float
    height: float
    padding: float
    outer_radius: float
    inner_radius: float


@dataclasses.dataclass(frozen=True)
class SliderGeometry:
    width: float
    height: float
    length: float
    thickness: float
    handle_size: float


def slider_geometry(theme: Theme) -> SliderGeometry:
    sliders = theme.datapoints.sliders
    thickness = sliders.thickness
    if thickness is None:
        thickness = 85.0 if sliders.style == "thick" else 10.0
    thickness = max(1.0, thickness)
    length = max(thickness, sliders.length)
    handle_size = (
        sliders.drag_bar_length if sliders.style == "thick" else sliders.circle_diameter
    )
    cross = max(thickness, handle_size)
    if sliders.axis == "vertical":
        return SliderGeometry(cross, length, length, thickness, handle_size)
    return SliderGeometry(length, cross, length, thickness, handle_size)


def slider_size(theme: Theme) -> tuple[float, float]:
    geometry = slider_geometry(theme)
    return geometry.width, geometry.height


def leaf_slider_size(nd: dict, theme: Theme) -> tuple[float, float]:
    """The box a slider leaf is measured at: a count's (``render_counts``), else
    the theme's slider."""
    payload = nd.get("drawing_element") or {}
    return count_size(payload, theme) if is_count(payload) else slider_size(theme)


# The shortest a horizontal slider is squeezed to before its row has to wrap
# instead. The same floor an image gets (generator_units.IMAGE_MIN_WIDTH).
_SLIDER_MIN_LENGTH = 96.0


def drawing_element_min_width(payload: dict | None, theme: Theme) -> float:
    """The narrowest box a drawing element still paints whole in.

    A task control and a vertical slider are fixed across; a horizontal slider
    keeps its theme ``length`` as its natural width but may shrink to a floor
    (``slider_rect`` caps it at its box), so a lone slider on a narrow line
    shrinks rather than overflowing.
    """
    if (payload or {}).get("kind") != "slider":
        return task_control_size(theme)[0]
    if is_count(payload):
        return count_size(payload or {}, theme)[0]
    geometry = slider_geometry(theme)
    if theme.datapoints.sliders.axis == "vertical":
        return geometry.width
    cross = max(geometry.thickness, geometry.handle_size)
    return min(geometry.width, max(cross, _SLIDER_MIN_LENGTH))


def drawing_element_baseline(
    payload: dict | None, fonts: FontSet, theme: Theme
) -> float | None:
    """The baseline a control offers the text row it sits in.

    A control has no text, but it sits in a line of it: its baseline is the one
    a line of body text would have centred in its box, as a link pill's is.
    Without one the row invented ``h / LINE_SCALE`` and hung the words beside a
    slider low, off its middle. The box height follows ``natural_height``.
    """
    if (payload or {}).get("kind") == "slider" and theme.datapoints.sliders.enabled:
        height = leaf_slider_size({"drawing_element": payload}, theme)[1]
    elif theme.datapoints.task_controls.enabled:
        height = task_control_size(theme)[1]
    else:
        return None
    metrics = make_font(fonts.typeface, theme.text.font_size).getMetrics()
    text_h = metrics.fDescent - metrics.fAscent
    return (height - text_h) / 2.0 - metrics.fAscent


def task_control_geometry(theme: Theme) -> TaskControlGeometry:
    controls = theme.datapoints.task_controls
    is_switch = controls.type == "switch"
    minimum = 40.0 if is_switch else 32.0
    size = max(minimum, controls.size if controls.size is not None else minimum)
    padding = max(0.0, min(controls.padding, size / 2.0))
    default_radius = size / 2.0 if is_switch else 6.0
    radius = (
        controls.corner_radius if controls.corner_radius is not None else default_radius
    )
    outer_radius = max(0.0, min(radius, size / 2.0))
    return TaskControlGeometry(
        width=size * 2.0 if is_switch else size,
        height=size,
        padding=padding,
        outer_radius=outer_radius,
        inner_radius=max(0.0, outer_radius - padding),
    )


def task_control_size(theme: Theme) -> tuple[float, float]:
    geometry = task_control_geometry(theme)
    return geometry.width, geometry.height


def task_control_radii(
    geometry: TaskControlGeometry, outer_style: SectionStyle
) -> tuple[float, float]:
    """Resolve one state's outer radius and its padding-derived inner radius."""
    outer = geometry.outer_radius
    if outer_style.corner_radius_authored:
        outer = max(0.0, min(outer_style.corner_radius, geometry.height / 2.0))
    return outer, max(0.0, outer - geometry.padding)


def task_control_rect(
    box: LayoutBox, theme: Theme
) -> tuple[float, float, float, float]:
    """The control's outer rectangle in *box*, as ``(x, y, width, height)``.

    Where ``draw_task_control`` paints it and where a click on it lands — one
    computation for both (ADR-400), as ``_link_pill_rect`` is for a button.
    """
    geometry = task_control_geometry(theme)
    align = _resolve_h_align(box.render_properties, theme)
    slack = max(0.0, box.width - geometry.width)
    x = box.x + (slack if align == "right" else slack / 2.0 if align == "center" else 0)
    y = box.y + max(0.0, (box.height - geometry.height) / 2.0)
    return x, y, geometry.width, geometry.height


def slider_rect(box: LayoutBox, theme: Theme) -> tuple[float, float, float, float]:
    """The slider's stable outer rectangle, shared by paint and hit testing.

    Its length along the axis is the theme ``length`` capped at the box, so a
    slider in a box narrower than its length shrinks inside it rather than
    painting past its edge. The track and the click-to-value map both read this
    rectangle, so they shrink with it.
    """
    geometry = slider_geometry(theme)
    width, height = geometry.width, geometry.height
    if theme.datapoints.sliders.axis == "vertical":
        height = max(geometry.thickness, min(height, box.height))
    else:
        width = max(geometry.thickness, min(width, box.width))
    align = _resolve_h_align(box.render_properties, theme)
    x_slack = max(0.0, box.width - width)
    y_slack = max(0.0, box.height - height)
    x = box.x + (
        x_slack if align == "right" else x_slack / 2.0 if align == "center" else 0
    )
    return x, box.y + y_slack / 2.0, width, height


def _slider_track_rect(box: LayoutBox, theme: Theme) -> skia.Rect:
    geometry = slider_geometry(theme)
    x, y, width, height = slider_rect(box, theme)
    if theme.datapoints.sliders.axis == "vertical":
        return skia.Rect.MakeXYWH(
            x + (width - geometry.thickness) / 2.0,
            y,
            geometry.thickness,
            height,
        )
    return skia.Rect.MakeXYWH(
        x,
        y + (height - geometry.thickness) / 2.0,
        width,
        geometry.thickness,
    )


def slider_value_at(
    box: LayoutBox,
    theme: Theme,
    x: float,
    y: float,
    decimals: int | None = None,
    maximum: float = 100.0,
) -> float:
    """Map a content point to a clamped slider value in its own domain."""
    return slider_value_in_rect(slider_rect(box, theme), theme, x, y, decimals, maximum)


def slider_value_in_rect(
    rect: tuple[float, float, float, float],
    theme: Theme,
    x: float,
    y: float,
    decimals: int | None = None,
    maximum: float = 100.0,
) -> float:
    """Map a point through the slider's full track range.

    *decimals* is the granularity the AUTHOR wrote (``[65%]`` is whole percents),
    and rounding here rather than at either caller is what keeps the value the
    window previews and the value the agent is told the same number (ADR-400: one
    normalization point). Without it a pointer position travels verbatim, float
    noise and all.
    """
    left, top, width, height = rect
    if theme.datapoints.sliders.axis == "vertical":
        ratio = (top + height - y) / max(1.0, height)
    else:
        ratio = (x - left) / max(1.0, width)
    value = min(maximum, max(0.0, ratio * maximum))
    return value if decimals is None else round(value, decimals)


def _drag_bar_rect(inner: skia.Rect, boundary: float, theme: Theme) -> skia.Rect:
    """The thick style's drag bar: inside the fill, ``drag_bar_gap`` short of
    the value edge, and never past the track's start when the fill is too short
    to hold the gap and the bar."""
    sliders = theme.datapoints.sliders
    near = sliders.drag_bar_gap + sliders.drag_bar_thickness
    if sliders.axis == "vertical":
        top = min(inner.bottom(), boundary + near) - sliders.drag_bar_thickness
        return skia.Rect.MakeXYWH(
            inner.centerX() - sliders.drag_bar_length / 2.0,
            top,
            sliders.drag_bar_length,
            sliders.drag_bar_thickness,
        )
    return skia.Rect.MakeXYWH(
        max(inner.left(), boundary - near),
        inner.centerY() - sliders.drag_bar_length / 2.0,
        sliders.drag_bar_thickness,
        sliders.drag_bar_length,
    )


def _slider_radius(theme: Theme, style: SectionStyle, thickness: float) -> float:
    if style.corner_radius_authored:
        return max(0.0, min(style.corner_radius, thickness / 2.0))
    radius = theme.datapoints.sliders.corner_radius
    if radius is None:
        radius = thickness / 2.0
    return max(0.0, min(radius, thickness / 2.0))


def _paint_slider_bar(
    canvas: skia.Canvas,
    inner: skia.Rect,
    fill: skia.Rect,
    radius: float,
    style: SectionStyle,
    node: dict,
    stack: tuple[int | str, ...],
    theme: Theme,
    layered_fill: Callable[..., None],
) -> None:
    """Paint the bar as one shape: the rounded inner track cut at the value.

    The fixed end keeps the track's rounded cap and the moving edge is square,
    including while the value is narrower than the corner radius. Everything
    the bar draws belongs to that shape: its color, image and gradient fill it,
    and its shadows and stroke trace it, so the outline closes at the value
    edge rather than running on under the empty track.
    """
    if fill.width() <= 0 or fill.height() <= 0:
        return
    # A full bar is the whole track, painted as the track's own shape.
    within = None if fill.contains(inner) else fill

    paint_shadows(canvas, inner, radius, style.shadows, inner=False, within=within)

    # Every content layer uses the zero-radius progress rectangle. The outer
    # clip, not a second rounded bar, supplies the track's fixed-end cap.
    content_style = dataclasses.replace(style, shadows=(), stroke_width=0.0)
    canvas.save()
    canvas.clipPath(shape_path(inner, radius), skia.ClipOp.kIntersect, True)
    _paint_style(
        canvas,
        fill,
        0.0,
        content_style,
        node,
        stack,
        theme,
        layered_fill,
    )
    canvas.restore()

    paint_shadows(canvas, inner, radius, style.shadows, inner=True, within=within)
    paint = _stroke_paint(style, stack, theme)
    if paint is not None:
        draw_stroke(canvas, inner, radius, paint, style.stroke_align, within=within)


@muted_paint
def draw_slider(
    canvas: skia.Canvas,
    box: LayoutBox,
    node: dict,
    theme: Theme,
    layered_fill: Callable[..., None],
) -> None:
    """Paint a themed slider from its grouper-owned numeric payload."""
    sliders = theme.datapoints.sliders
    geometry = slider_geometry(theme)
    payload = node.get("drawing_element") or {}
    # The domain is the document's: `[65%]` fills to 100, `[3/10]` to 10.
    maximum = float(payload.get("max") or 100.0)
    value = min(maximum, max(0.0, float(payload.get("value", 0.0))))

    if sliders.style == "thick":
        default_track = SectionStyle(bg_colors=[GREY_INK])
        default_bar = SectionStyle(bg_colors=[GREY_WHITE])
        default_handle = SectionStyle(bg_colors=[GREY_MID])
    else:
        default_track = SectionStyle(bg_colors=[GREY_TRACK])
        default_bar = SectionStyle(bg_colors=[GREY_INK])
        default_handle = SectionStyle(bg_colors=[GREY_INK])

    def resolved(style: SectionStyle, fallback: SectionStyle) -> SectionStyle:
        if style.bg_colors or style.bg_image is not None or style.gradient is not None:
            return style
        return dataclasses.replace(style, bg_colors=list(fallback.bg_colors))

    track_style = resolved(sliders.track, default_track)
    bar_style = resolved(sliders.bar, default_bar)
    handle_style = resolved(sliders.handle, default_handle)

    track = _slider_track_rect(box, theme)
    track_fill = _paint_style(
        canvas,
        track,
        _slider_radius(theme, track_style, geometry.thickness),
        track_style,
        node,
        box.bg_stack,
        theme,
        layered_fill,
    )
    inner = track
    inner_stack = _push_bg(box.bg_stack, _opaque_or_none(track_fill))
    ratio = value / maximum
    if sliders.axis == "vertical":
        boundary = inner.bottom() - inner.height() * ratio
        fill = skia.Rect.MakeLTRB(inner.left(), boundary, inner.right(), inner.bottom())
    else:
        boundary = inner.left() + inner.width() * ratio
        fill = skia.Rect.MakeLTRB(inner.left(), inner.top(), boundary, inner.bottom())
    _paint_slider_bar(
        canvas,
        inner,
        fill,
        _slider_radius(theme, bar_style, min(inner.width(), inner.height())),
        bar_style,
        node,
        inner_stack,
        theme,
        layered_fill,
    )

    if sliders.style == "line":
        diameter = sliders.circle_diameter
        handle = skia.Rect.MakeXYWH(
            boundary - diameter / 2.0,
            inner.centerY() - diameter / 2.0,
            diameter,
            diameter,
        )
        if sliders.axis == "vertical":
            handle = skia.Rect.MakeXYWH(
                inner.centerX() - diameter / 2.0,
                boundary - diameter / 2.0,
                diameter,
                diameter,
            )
        radius = diameter / 2.0
    else:
        handle = _drag_bar_rect(inner, boundary, theme)
        radius = min(handle.width(), handle.height()) / 2.0
    _paint_style(
        canvas,
        handle,
        radius,
        handle_style,
        node,
        inner_stack,
        theme,
        layered_fill,
    )


@muted_paint
def draw_task_control(
    canvas: skia.Canvas,
    box: LayoutBox,
    node: dict,
    fonts: FontSet,
    theme: Theme,
    layered_fill: Callable[..., None],
) -> None:
    geometry = task_control_geometry(theme)
    checked = bool((node.get("drawing_element") or {}).get("checked"))
    controls = theme.datapoints.task_controls
    outer_style = controls.checked_outer if checked else controls.unchecked_outer
    inner_style = controls.checked_inner if checked else controls.unchecked_inner
    # A box the theme does not style draws in the built-in greys, and a ticked
    # one shows its tick: a ring alone tells ticked from open by colour only.
    unstyled = not outer_style.is_active()
    if unstyled:
        outer_style = SectionStyle(bg_colors=[GREY_INK if checked else GREY_LIGHT])
    if not inner_style.is_active():
        inner_style = SectionStyle(bg_colors=[GREY_WHITE])
    outer_radius, inner_radius = task_control_radii(geometry, outer_style)
    x, y, _w, _h = task_control_rect(box, theme)
    outer = skia.Rect.MakeXYWH(x, y, geometry.width, geometry.height)
    fill = _paint_style(
        canvas,
        outer,
        outer_radius,
        outer_style,
        node,
        box.bg_stack,
        theme,
        layered_fill,
    )
    inner_size = max(0.0, geometry.height - 2.0 * geometry.padding)
    if inner_size <= 0:
        return
    inner_x = x + geometry.padding
    if controls.type == "switch" and checked:
        inner_x = x + geometry.width - geometry.padding - inner_size
    inner = skia.Rect.MakeXYWH(
        inner_x,
        y + geometry.padding,
        inner_size
        if controls.type == "switch"
        else geometry.width - 2.0 * geometry.padding,
        inner_size,
    )
    inner_stack = _push_bg(box.bg_stack, _opaque_or_none(fill))
    inner_fill = _paint_style(
        canvas,
        inner,
        inner_radius,
        inner_style,
        node,
        inner_stack,
        theme,
        layered_fill,
    )
    symbol, color = (
        (controls.checked_symbol, controls.checked_symbol_color)
        if checked
        else (controls.unchecked_symbol, controls.unchecked_symbol_color)
    )
    if unstyled and checked and not symbol:
        symbol, color = "✓", GREY_INK
    if symbol:
        if color is None:
            color = fill if fill is not None else theme.text.color
        stack = _push_bg(inner_stack, _opaque_or_none(inner_fill))
        _draw_symbol(canvas, inner, symbol, _replace_color(color, stack, theme), fonts)


# The symbol's size as a share of the inner shape's height: room around a glyph
# whose line box (ascent to descent) is taller than its size.
_SYMBOL_SHARE = 0.7


def _draw_symbol(
    canvas: skia.Canvas, inner: skia.Rect, symbol: str, color: int, fonts: FontSet
) -> None:
    """*symbol* centred in *inner*, in the emoji face a badge glyph draws in."""
    size = inner.height() * _SYMBOL_SHARE
    width = glyph_advance(symbol, fonts.emoji, fonts.typeface, size)
    if width > inner.width():
        size *= inner.width() / width
        width = glyph_advance(symbol, fonts.emoji, fonts.typeface, size)
    metrics = _emoji_glyph_font(fonts.emoji, fonts.typeface, size).getMetrics()
    x = inner.centerX() - width / 2.0
    y = inner.centerY() - (metrics.fAscent + metrics.fDescent) / 2.0
    paint = skia.Paint(Color=color, AntiAlias=True)
    draw_glyph_runs(canvas, symbol, x, y, fonts.emoji, fonts.typeface, size, paint)
