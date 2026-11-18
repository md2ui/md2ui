"""A count's geometry and paint: its digits between two round buttons.

A count is a ratio slider the grouper stamped ``count`` (``Quantity: ➖ [2/9] ➕``,
``grouper_sliders``). It is drawn as two round buttons, ➖ and ➕, with the value's
digits between them, never as a track. A count is a slider, so each button is a
drawing element painted as a slider's handle is (``render_element_paint``), in
its own ``### Count Button`` paint or, unset, the quieter button's. One
target with two regions: :func:`count_rects` is where the paint puts each button
and where a click lands (ADR-400, ADR-404), and both read :func:`count_size`, the
box the measurers give the leaf.

The size is the theme's alone, so a value the user steps to never moves a box:
the digits' slot is as wide as the authored maximum written out.

A count written ``~~`` is disabled, as a slider or a task box is: each control's
drawer is wrapped in :func:`muted_paint`, which fades the whole control.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_backgrounds import _opaque_or_none, _push_bg
from md2ui.pipeline.render_colors import _replace_color
from md2ui.pipeline.render_element_paint import _paint_style
from md2ui.pipeline.render_fills import _paint_layered_fill
from md2ui.pipeline.render_placeholders import element_picture
from md2ui.pipeline.render_style import (
    FontSet,
    _disabled_link_style,
    _resolve_h_align,
    _resolve_link,
)
from md2ui.pipeline.theme import BG_IMAGE, LinkStyle, SectionStyle, TextStyle, Theme
from md2ui.pipeline.theme_model import MUTED_OPACITY
from md2ui.utils.font_loader import make_font

# A button's diameter and the digits' size, as multiples of the body text size.
_BUTTON = 1.875
_DIGITS = 1.2
# One digit's slot at the digits' size, and the room either side of them.
_DIGIT_WIDTH = 0.62
_SIDE = 0.75


def muted_paint(draw: Callable[..., None]) -> Callable[..., None]:
    """*draw*, a control's drawer, painting a control written ``~~`` (its payload
    ``disabled``) whole at the default mute, one layer in its own box: no
    ``Disabled …`` key names a slider's, a count's or a box's colours."""

    @functools.wraps(draw)
    def drawn(canvas: skia.Canvas, box: LayoutBox, node: dict, *rest) -> None:
        if not (node.get("drawing_element") or {}).get("disabled"):
            return draw(canvas, box, node, *rest)
        canvas.saveLayer(None, skia.Paint(Alphaf=MUTED_OPACITY))
        draw(canvas, box, node, *rest)
        canvas.restore()

    return drawn


def is_count(payload: dict | None) -> bool:
    payload = payload or {}
    return payload.get("kind") == "slider" and bool(payload.get("count"))


def count_size(payload: dict, theme: Theme) -> tuple[float, float]:
    """The box a count is drawn in: two buttons and the slot of its widest value."""
    size = theme.text.font_size
    button = round(size * _BUTTON)
    digits = len(f"{float(payload.get('max') or 0):g}")
    slot = digits * size * _DIGITS * _DIGIT_WIDTH + 2 * size * _SIDE
    return 2 * button + slot, float(button)


def count_rects(
    box: LayoutBox, payload: dict, theme: Theme
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """The ➖ and ➕ buttons' rectangles in *box*, as the paint draws them."""
    width, button = count_size(payload, theme)
    align = _resolve_h_align(box.render_properties, theme)
    slack = max(0.0, box.width - width)
    x = box.x + (slack if align == "right" else slack / 2.0 if align == "center" else 0)
    y = box.y + max(0.0, (box.height - button) / 2.0)
    return (x, y, button, button), (x + width - button, y, button, button)


def _as_layer(style: LinkStyle) -> SectionStyle:
    """A button's paint as one drawing-element layer: the fill, image, gradient,
    shadows and stroke its pill would paint (``render_pill_paint``)."""
    return SectionStyle(
        bg_colors=[] if style.fill_color is None else [style.fill_color],
        bg_image=style.bg_image,
        gradient=style.gradient,
        shadows=list(style.shadows),
        stroke_width=style.stroke_width or 0.0,
        stroke_color=style.stroke_color,
        stroke_align=style.stroke_align or "center",
    )


def _count_button(
    node: dict, theme: Theme, live: bool, images: dict | None
) -> tuple[SectionStyle, int, skia.Image | None, bool]:
    """One button's layer, its sign's colour, the picture it inherits, and
    whether it is muted whole.

    With no ``### Count Button`` key the button is the quieter button's paint
    and, when it cannot step, that button's disabled paint, as its pill would
    be. A theme that keys the count paints its own layer (or the inherited one,
    for ``Symbol color`` alone), and a button that cannot step is that layer at
    the default mute, as a ``~~`` slider is."""
    counts = theme.datapoints.counts
    quiet = _resolve_link({**node, "type": "link", "link_variant": "secondary"}, theme)
    keyed = counts.button.is_active() or counts.symbol_color is not None
    link = quiet[3] if live or keyed else _disabled_link_style(quiet[3])
    ink = counts.symbol_color
    if ink is None:
        ink = (link.text_style or TextStyle()).color
    if counts.button.is_active():
        return counts.button, ink, None, not live
    picture = element_picture(images, link.bg_image, not (live or keyed))
    return _as_layer(link), ink, picture, not live and keyed


@muted_paint
def draw_count(
    canvas: skia.Canvas,
    box: LayoutBox,
    node: dict,
    fonts: FontSet,
    theme: Theme,
    images: dict | None = None,
) -> None:
    """Paint the two buttons and the digits; a button that cannot step is muted
    (``_count_button``). Each button is one drawing-element layer, a circle
    painted by ``_paint_style`` against the stack the count sits on, its solid
    fill drawn whole as a pill's is. No label names a sign, so no pin colours
    it."""
    payload = node.get("drawing_element") or {}
    value = float(payload.get("value", 0.0))
    maximum = float(payload.get("max") or 0.0)
    minus, plus = count_rects(box, payload, theme)
    solid = functools.partial(_paint_layered_fill, direct_solid=True)
    for rect, live, sign in ((minus, value > 0, "-"), (plus, value < maximum, "+")):
        style, color, picture, muted = _count_button(node, theme, live, images)
        oval = skia.Rect.MakeXYWH(*rect)
        if muted:
            canvas.saveLayer(None, skia.Paint(Alphaf=MUTED_OPACITY))
        fill = _paint_style(
            canvas,
            oval,
            0.0,
            style,
            node,
            box.bg_stack,
            theme,
            solid,
            oval=True,
            picture=picture,
        )
        held = _push_bg(
            box.bg_stack, BG_IMAGE if style.bg_image else _opaque_or_none(fill)
        )
        ink = skia.Paint(
            Color=_replace_color(color, held, theme),
            StrokeWidth=max(1.5, rect[2] / 15.0),
            StrokeCap=skia.Paint.kRound_Cap,
            AntiAlias=True,
        )
        cx, cy, arm = oval.centerX(), oval.centerY(), rect[2] * 0.22
        canvas.drawLine(cx - arm, cy, cx + arm, cy, ink)
        if sign == "+":
            canvas.drawLine(cx, cy - arm, cx, cy + arm, ink)
        if muted:
            canvas.restore()
    font = make_font(fonts.bold, theme.text.font_size * _DIGITS)
    text = f"{value:g}"
    metrics = font.getMetrics()
    left, right = minus[0] + minus[2], plus[0]
    x = left + (right - left - font.measureText(text)) / 2.0
    y = minus[1] + (minus[3] - (metrics.fDescent - metrics.fAscent)) / 2.0
    canvas.drawString(
        text,
        x,
        y - metrics.fAscent,
        font,
        skia.Paint(
            Color=_replace_color(theme.text.color, box.bg_stack, theme), AntiAlias=True
        ),
    )
