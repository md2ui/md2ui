"""Layered fills: how a box's background layers are painted onto a canvas.

``render_backgrounds`` decides what the layers ARE; this module paints them, in
the fixed order every surface shares — outer shadows, fill colour, image,
gradient, inner shadows. Any painter of a filled shape uses it, so a card, a
bar and a chart bar cannot drift apart.
"""

import dataclasses
import math
from collections.abc import Sequence

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.render_colors import _replace_color
from md2ui.pipeline.render_settings import VIEW
from md2ui.pipeline.render_shadows import paint_shadows, shape_path
from md2ui.pipeline.theme import GradientTheme, ShadowSpec, Theme
from md2ui.pipeline.theme_model import GREY_INK, GREY_TRACK
from md2ui.utils.image_cache import Loading, Photo, Picture

# Built-in paints used when THEME.md leaves a family unstyled (grayscale).
_DEFAULT_BAR_FILL = GREY_INK
_DEFAULT_BAR_TRACK = GREY_TRACK


_PHOTO_SAMPLING = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)


def draw_picture(
    canvas: skia.Canvas, picture: Picture, src: skia.Rect, dst: skia.Rect
) -> None:
    """Draw the *src* rect of *picture*, in the source's own pixels, into *dst*.

    A photo asks for its decode at the size *dst* lands at on the device: the
    canvas's scale times the pixel ratio the recording is shown at
    (``ImageCache.fit_decodes``). It is drawn from what is held meanwhile; with
    nothing held yet, its stand-in fills *dst* in its place.
    """
    image = picture
    if isinstance(picture, Photo | Loading):
        if src.isEmpty():
            return
        photo = picture.photo if isinstance(picture, Loading) else picture
        m = canvas.getTotalMatrix()
        device = math.hypot(m.getScaleX(), m.getSkewY()) * VIEW.pixel_ratio
        scale = max(dst.width() / src.width(), dst.height() / src.height())
        image = photo.image_for(scale * device)
        if image is None:
            if isinstance(picture, Loading) and picture.standin is not None:
                _draw_cover(canvas, picture.standin, dst)
            return
        sx = image.width() / photo.width()
        sy = image.height() / photo.height()
        src = skia.Rect.MakeLTRB(
            src.left() * sx, src.top() * sy, src.right() * sx, src.bottom() * sy
        )
        # Held at least twice its drawn size (``image_cache._SLACK``), a photo is
        # drawn down through mipmaps, which a strict source rect turns off; the
        # pixels just outside a crop are the photo's own.
        canvas.drawImageRect(
            image, src, dst, _PHOTO_SAMPLING, None, skia.Canvas.kFast_SrcRectConstraint
        )
        return
    canvas.drawImageRect(image, src, dst, skia.SamplingOptions(skia.FilterMode.kLinear))


def _cover_src(width: float, height: float, dst: skia.Rect) -> skia.Rect:
    """The centred part of a *width* × *height* picture that covers *dst*."""
    scale = max(dst.width() / width, dst.height() / height)
    src_w, src_h = dst.width() / scale, dst.height() / scale
    return skia.Rect.MakeXYWH((width - src_w) / 2, (height - src_h) / 2, src_w, src_h)


def _draw_cover(canvas: skia.Canvas, image: skia.Image, dst: skia.Rect) -> None:
    """*image* cover-fitted into *dst*, as a picture of its own size is."""
    if image.width() > 0 and image.height() > 0:
        draw_picture(canvas, image, _cover_src(image.width(), image.height(), dst), dst)


def _paint_layered_fill(
    canvas: skia.Canvas,
    rect: "skia.Rect",
    *,
    bg_color: int | None,
    image: "Picture | None",
    gradient: "GradientTheme | None",
    corner_radius: float = 0.0,
    shadows: "Sequence[ShadowSpec]" = (),
    oval: bool = False,
    direct_solid: bool = False,
    outline: "skia.Path | None" = None,
) -> None:
    """Paint a layered background into ``rect``: outer shadows, then fill color,
    image and gradient, then inner shadows — the fixed order shared by the root
    and every section level.

    Layers are clipped to the (optionally rounded, optionally oval) rect; any
    unset (None) layer is skipped. Because the gradient is drawn last, an opaque
    gradient covers the image. Mirrors the root/section paint so both stay
    identical. The shadows bracket the fill rather than sitting inside its clip:
    an outer one paints beyond the rect, so it cannot be drawn under it. A box
    with shadows and no fill still casts them — the silhouette is the shape, not
    the ink in it (see render_shadows). An *outline* replaces the rect's shape,
    for an area no rectangle describes; *rect* still places the image and the
    gradient.
    """
    has_gradient = gradient is not None and len(gradient.colors) >= 2
    paint_shadows(
        canvas, rect, corner_radius, shadows, inner=False, oval=oval, outline=outline
    )
    if direct_solid and bg_color is not None and image is None and not has_gradient:
        paint = skia.Paint(Color=bg_color, Style=skia.Paint.kFill_Style, AntiAlias=True)
        if oval:
            canvas.drawOval(rect, paint)
        else:
            canvas.drawRoundRect(rect, corner_radius, corner_radius, paint)
        bg_color = None
    if bg_color is None and image is None and not has_gradient:
        paint_shadows(
            canvas, rect, corner_radius, shadows, inner=True, oval=oval, outline=outline
        )
        return
    canvas.save()
    if oval or corner_radius > 0 or outline is not None:
        canvas.clipPath(
            shape_path(rect, corner_radius, oval=oval, outline=outline),
            skia.ClipOp.kIntersect,
            True,
        )
    else:
        canvas.clipRect(rect)
    # 1. Fill color
    if bg_color is not None:
        canvas.drawRect(
            rect,
            skia.Paint(Color=bg_color, Style=skia.Paint.kFill_Style, AntiAlias=True),
        )
    # 2. Image (cover-fit, centered)
    if image is not None:
        iw, ih = image.width(), image.height()
        if iw > 0 and ih > 0:
            draw_picture(canvas, image, _cover_src(iw, ih, rect), rect)
    # 3. Gradient
    if has_gradient:
        assert gradient is not None
        g = gradient
        shader = skia.GradientShader.MakeLinear(
            [
                (
                    rect.left() + g.start[0] * rect.width(),
                    rect.top() + g.start[1] * rect.height(),
                ),
                (
                    rect.left() + g.end[0] * rect.width(),
                    rect.top() + g.end[1] * rect.height(),
                ),
            ],
            g.colors,
            g.ratios if len(g.ratios) == len(g.colors) else None,
        )
        grad_paint = skia.Paint(AntiAlias=True)
        grad_paint.setShader(shader)
        canvas.drawRect(rect, grad_paint)
    canvas.restore()
    paint_shadows(
        canvas, rect, corner_radius, shadows, inner=True, oval=oval, outline=outline
    )


def _replaced_gradient(
    gradient: "GradientTheme | None",
    stack: "tuple[int | str, ...]",
    theme: "Theme",
) -> "GradientTheme | None":
    """A gradient whose painted stops use the existing ``fill`` channel.

    Theme objects are shared across every component, so return a copy only
    when a stop changes; never mutate the authored gradient in place.
    """
    if gradient is None or not gradient.colors:
        return gradient
    colors = [_replace_color(c, stack, theme, "fill") for c in gradient.colors]
    if colors == gradient.colors:
        return gradient
    return dataclasses.replace(gradient, colors=colors)


def replaced_surface(
    bg_color: int | None,
    gradient: "GradientTheme | None",
    stack: "tuple[int | str, ...]",
    theme: "Theme | None",
) -> "tuple[int | None, GradientTheme | None]":
    """A section, card or list item's fill, replaced as a pill's fill is.

    The fill is a paint first, resolved against the surface it sits on, and
    only then the context for what it holds. Without a theme it is as given.
    """
    if theme is None:
        return bg_color, gradient
    if bg_color is not None:
        bg_color = _replace_color(bg_color, stack, theme, "fill")
    return bg_color, _replaced_gradient(gradient, stack, theme)
