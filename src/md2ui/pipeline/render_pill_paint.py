"""A button pill's shape, painted once for every control drawn in its paint.

A button pill and a segmented run's surface (a run of buttons) are both drawn
in a button variant's paint, so they go through this one function (ADR-400,
one normalization point): its fill and stroke replaced against the
background stack they sit on and pinned by ``## Fixed colors`` as a pill's
are, its stroke drawn at the variant's ``Stroke align``, and the ink of what
it holds resolved on its own replaced fill. None of them computes a colour or
a stroke of its own. A count's round buttons are a slider's drawing elements,
painted by ``render_element_paint``, not here.
"""

from __future__ import annotations

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.render_backgrounds import _opaque_or_none, _push_bg
from md2ui.pipeline.render_colors import _pin_or_replace, painted_pins
from md2ui.pipeline.render_fills import _paint_layered_fill, _replaced_gradient
from md2ui.pipeline.render_placeholders import element_picture
from md2ui.pipeline.render_shadows import draw_stroke
from md2ui.pipeline.theme import BG_IMAGE, LinkStyle, TextStyle, Theme

Stack = tuple[int | str, ...]


def paint_pill(
    canvas: skia.Canvas,
    rect: skia.Rect,
    style: LinkStyle,
    pins: dict,
    stack: Stack,
    theme: Theme,
    *,
    disabled: bool = False,
    oval: bool = False,
    images: dict | None = None,
) -> tuple[int, Stack]:
    """Paint *style*'s fill, shadows and stroke in *rect* on *stack*, and return
    the ink of what it holds and the stack it sits on.

    *pins* are the ``fixed_*`` stamps of the node the pill draws
    (``stamp_fixed_colors``); a *disabled* pill takes none and fades its image.
    *oval* draws the shape as an oval (an emoji badge)."""
    # Resolved BEFORE anything is painted, because the fill is also what the
    # label will sit on: a pill the card flipped to white must hand white to its
    # own label, not the color it started with.
    fixed = {} if disabled else painted_pins(pins, style)
    fill = _pin_or_replace(
        style.fill_color or 0, fixed.get("fixed_fill"), stack, theme, "fill"
    )
    stroke = _pin_or_replace(
        style.stroke_color or 0, fixed.get("fixed_stroke"), stack, theme, "stroke"
    )
    radius = style.corner_radius if style.corner_radius is not None else 16.0
    _paint_layered_fill(
        canvas,
        rect,
        bg_color=_opaque_or_none(fill),
        image=element_picture(images, style.bg_image, disabled),
        gradient=_replaced_gradient(style.gradient, stack, theme),
        corner_radius=0.0 if oval else radius,
        shadows=style.shadows,
        oval=oval,
        direct_solid=True,
    )
    if (style.stroke_width or 0.0) > 0:
        paint = skia.Paint(
            Color=stroke,
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=style.stroke_width,
            AntiAlias=True,
        )
        draw_stroke(canvas, rect, radius, paint, style.stroke_align, oval=oval)
    # What the pill holds sits on its OWN fill -- the REPLACED one -- so that
    # fill leads the stack. A pill flipped to white therefore recolors its own
    # label from the `On background color: #FFFFFF` group, with no rule ever
    # having to mention buttons.
    held = _push_bg(stack, BG_IMAGE if style.bg_image else _opaque_or_none(fill))
    text = (style.text_style or TextStyle()).color
    return _pin_or_replace(text, fixed.get("fixed_text"), held, theme), held
