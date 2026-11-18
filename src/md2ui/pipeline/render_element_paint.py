"""The drawing-element painter: one ``SectionStyle`` layer of a non-text leaf.

A slider's track, bar and handle, a task control's outer and inner shapes and a
count's round buttons are each one layer painted here (ADR-400, one
normalization point): its fill rotated and replaced against the background
stack it sits on, its image and gradient, its shadows, and its stroke at its
``Stroke align``. No colour pin applies: a pin names a label, and none of these
layers is one. It lives apart from the geometry (``render_drawing_elements``,
``render_counts``) so both can paint through it.
"""

import dataclasses
import functools
from typing import Callable

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.render_colors import _replace_color, _rotate_color, _rotation_slot
from md2ui.pipeline.render_placeholders import decode_theme_image, theme_picture
from md2ui.pipeline.render_shadows import draw_stroke
from md2ui.pipeline.theme import GradientTheme, SectionStyle, Theme

_cached_decode = functools.lru_cache(maxsize=32)(decode_theme_image)


def _style_image(source: str | None) -> skia.Image | None:
    return theme_picture(source, _cached_decode)


def _gradient_for(
    gradient: GradientTheme | None, stack: tuple[int | str, ...], theme: Theme
) -> GradientTheme | None:
    if gradient is None:
        return None
    colors = [_replace_color(color, stack, theme, "fill") for color in gradient.colors]
    return (
        gradient
        if colors == gradient.colors
        else dataclasses.replace(gradient, colors=colors)
    )


def _resolved_fill(
    style: SectionStyle, node: dict, stack: tuple[int | str, ...], theme: Theme
) -> int | None:
    if not style.bg_colors:
        return None
    slot, chain = _rotation_slot(node, theme)
    color = _rotate_color(
        style.bg_colors, style.bg_colors[0], slot, theme, "card", chain
    )
    assert color is not None
    return _replace_color(color, stack, theme, "fill")


def _paint_style(
    canvas: skia.Canvas,
    rect: skia.Rect,
    radius: float,
    style: SectionStyle,
    node: dict,
    stack: tuple[int | str, ...],
    theme: Theme,
    layered_fill: Callable[..., None],
    *,
    oval: bool = False,
    picture: skia.Image | None = None,
) -> int | None:
    """Paint *style* in *rect* on *stack* and return its resolved fill.

    *oval* draws the shape as a circle (a count's button). *picture*, when
    given, is painted in place of the style's own decoded image: a button's
    paint a count inherits brings its picture, faded when the button cannot
    step."""
    fill = _resolved_fill(style, node, stack, theme)
    layered_fill(
        canvas,
        rect,
        bg_color=fill,
        image=picture if picture is not None else _style_image(style.bg_image),
        gradient=_gradient_for(style.gradient, stack, theme),
        corner_radius=radius,
        shadows=style.shadows,
        oval=oval,
    )
    paint = _stroke_paint(style, stack, theme)
    if paint is not None:
        draw_stroke(canvas, rect, radius, paint, style.stroke_align, oval=oval)
    return fill


def _stroke_paint(
    style: SectionStyle, stack: tuple[int | str, ...], theme: Theme
) -> skia.Paint | None:
    """The paint *style*'s stroke is drawn with, or None when it has none."""
    if style.stroke_width <= 0 or style.stroke_color is None:
        return None
    return skia.Paint(
        Color=_replace_color(style.stroke_color, stack, theme, "stroke"),
        Style=skia.Paint.kStroke_Style,
        StrokeWidth=style.stroke_width,
        AntiAlias=True,
    )
