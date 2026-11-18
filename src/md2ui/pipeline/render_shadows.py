"""The shadow drawing layer: what falls inside and outside a painted box.

A shadow is not a property of any one element. Every box in the document is
painted by the same layered fill in ``layout_render``, so a shadow declared on a
background reaches all of them from one place: the root, every heading section,
cards and image cards, lists, task lists, quotes, tables and their header and
cells, buttons, inline-code chips, date chips, emoji badges, the four
task-control state layers, progress bars and their tracks, and chart bars and
their tracks.

The two kinds are geometrically different, not mirror images, and the difference
is entirely in the CLIP:

* an **inner** shadow is clipped to the shape. What is blurred is the region
  *outside* the shape after it has been moved by the offset, so a positive
  offset darkens the top-left inside edge and a zero offset rings all four;
* an **outer** shadow is clipped to the shape's bounds grown by ``radius``
  (``radius / 2`` per side) and moved by the offset, with the shape itself cut
  out. Cutting the shape out is what keeps a shadow from showing through a
  translucent fill; the grown box is where the blur has already reached zero,
  so it crops nothing visible.

**Two ways to draw the same blur.** A rect or rounded rect goes through Skia's
rounded-rect blur (``clipRRect`` / ``drawRRect``): it renders one small blurred
corner tile and stretches it, so a layer costs about the same on a badge and on a
page-sized panel (0.2 ms against 30 ms for a path blur there). Its falloff
differs from the path blur's by a few /255 on the rim. An oval, a box cut by
*within*, an *outline*, and a plain rect's inner shadow (a path Skia already
draws fast) are blurred as paths.

``radius`` is authored as the distance the shadow reaches past the edge, which
is why it becomes a Gaussian sigma of ``radius / 4`` rather than the CSS
``radius / 2``: see ``SHADOW_SIGMA_RATIO``, measured against the reference
renders in ``data/markdown/tests-render/theme-tests/shadows/``.
"""

from __future__ import annotations

from collections.abc import Sequence

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.theme_model import SHADOW_SIGMA_RATIO, ShadowSpec

__all__ = ["draw_stroke", "paint_shadows", "shape_path", "stroke_shape"]

# Slack added to the rect an inner shadow subtracts its shape from, so the blur
# of THAT rect's own outer edge cannot reach back into the clipped region. The
# blur reaches ~3 sigma = 0.75 * radius, which the radius term alone covers.
_INNER_MARGIN = 8.0


def shape_path(
    rect: "skia.Rect",
    corner_radius: float,
    *,
    oval: bool = False,
    dx: float = 0.0,
    dy: float = 0.0,
    within: "skia.Rect | None" = None,
    outline: "skia.Path | None" = None,
) -> "skia.Path":
    """The outline a background paints, optionally moved by ``(dx, dy)``.

    One helper so a box's fill clip and the shadows it casts are the same shape
    — a rounded rect, a plain rect, or the oval an emoji badge uses. *within*
    cuts that shape to a rectangle, for a box that is only partly filled — a
    slider bar is its rounded track up to the value, square at the value edge.
    *outline* is a shape no rectangle describes, such as the area under a line
    chart; *rect* is then only its bounds.
    """
    r = skia.Rect.MakeXYWH(
        rect.left() + dx, rect.top() + dy, rect.width(), rect.height()
    )
    path = skia.Path()
    if outline is not None:
        path = skia.Path(outline)
        path.offset(dx, dy)
    elif oval:
        path.addOval(r)
    elif corner_radius > 0:
        path.addRoundRect(r, corner_radius, corner_radius)
    else:
        path.addRect(r)
    if within is None:
        return path
    cut = skia.Path()
    cut.addRect(within.makeOffset(dx, dy))
    return skia.Op(path, cut, skia.PathOp.kIntersect_PathOp) or skia.Path()


def stroke_shape(
    rect: "skia.Rect", radius: float, width: float, align: str | None
) -> tuple["skia.Rect", float]:
    """The shape a stroke of *width* is drawn along, for ``Stroke align``.

    Skia centres a stroke on its path, so ``center`` is the shape itself;
    ``outside`` grows it by half the width so the whole line lies outside, and
    ``inside`` shrinks it so the whole line lies within. A rounded corner's
    radius moves with the edge (floored at 0); a sharp corner stays sharp.
    """
    d = {"inside": -width / 2.0, "outside": width / 2.0}.get(align or "", 0.0)
    if d == 0.0:
        return rect, radius
    return rect.makeOutset(d, d), max(0.0, radius + d) if radius > 0 else 0.0


def draw_stroke(
    canvas: "skia.Canvas",
    rect: "skia.Rect",
    radius: float,
    paint: "skia.Paint",
    align: str | None = None,
    *,
    oval: bool = False,
    within: "skia.Rect | None" = None,
) -> None:
    """Stroke a background's outline — rounded rect, rect or oval — at *align*.

    With *within* the outline is that of the shape cut to the rectangle (see
    ``shape_path``), so it closes along the cut; both are moved by the same
    ``Stroke align`` rule.
    """
    shape, r = stroke_shape(rect, radius, paint.getStrokeWidth(), align)
    if within is not None:
        cut, _ = stroke_shape(within, 0.0, paint.getStrokeWidth(), align)
        canvas.drawPath(shape_path(shape, r, oval=oval, within=cut), paint)
    elif oval:
        canvas.drawOval(shape, paint)
    elif r > 0:
        canvas.drawRoundRect(shape, r, r, paint)
    else:
        canvas.drawRect(shape, paint)


def _blur_paint(color: int, radius: float) -> "skia.Paint":
    """A fill paint for the shadow's silhouette, blurred by ``radius``."""
    paint = skia.Paint(Color=color, AntiAlias=True)
    if radius > 0:
        paint.setMaskFilter(
            skia.MaskFilter.MakeBlur(
                skia.kNormal_BlurStyle, radius * SHADOW_SIGMA_RATIO
            )
        )
    return paint


def _rrect(
    rect: "skia.Rect",
    corner_radius: float,
    oval: bool,
    dx: float = 0.0,
    dy: float = 0.0,
) -> "skia.RRect":
    """``shape_path``'s silhouette as an ``RRect``, for Skia's rounded-rect blur.

    Only for a shape no ``within`` cut and no ``outline`` changes: a rect, a
    rounded rect or an oval, moved by ``(dx, dy)``.
    """
    r = rect.makeOffset(dx, dy)
    if oval:
        return skia.RRect.MakeOval(r)
    if corner_radius > 0:
        return skia.RRect.MakeRectXY(r, corner_radius, corner_radius)
    return skia.RRect.MakeRect(r)


def _paint_outer(
    canvas: "skia.Canvas",
    rect: "skia.Rect",
    corner_radius: float,
    oval: bool,
    sh: ShadowSpec,
    within: "skia.Rect | None",
    outline: "skia.Path | None",
) -> None:
    """Blur the shape moved by the offset, clipped to the grown box minus it.

    A rect or rounded rect is clipped with ``clipRect`` / ``clipRRect`` and drawn
    with ``drawRRect``: Skia blurs that as a small nine-patch stretched to size,
    where a path is blurred over its whole area (30 ms for one small-radius layer
    on a page-sized panel, against 0.2 ms). An oval, a cut or an outline keeps the
    path: the raster backend has no fast blur for them.
    """
    reach = sh.radius / 2.0
    grown = skia.Rect.MakeXYWH(
        rect.left() - reach + sh.offset_x,
        rect.top() - reach + sh.offset_y,
        rect.width() + sh.radius,
        rect.height() + sh.radius,
    )
    if within is None and outline is None and not oval:
        canvas.save()
        canvas.clipRect(grown, skia.ClipOp.kIntersect, True)
        canvas.clipRRect(
            _rrect(rect, corner_radius, False), skia.ClipOp.kDifference, True
        )
        canvas.drawRRect(
            _rrect(rect, corner_radius, False, sh.offset_x, sh.offset_y),
            _blur_paint(sh.color, sh.radius),
        )
        canvas.restore()
        return
    box = skia.Path()
    box.addRect(grown)
    clip = skia.Op(
        box,
        shape_path(rect, corner_radius, oval=oval, within=within, outline=outline),
        skia.PathOp.kDifference_PathOp,
    )
    if clip is None or clip.isEmpty():
        return
    canvas.save()
    canvas.clipPath(clip, skia.ClipOp.kIntersect, True)
    canvas.drawPath(
        shape_path(
            rect,
            corner_radius,
            oval=oval,
            dx=sh.offset_x,
            dy=sh.offset_y,
            within=within,
            outline=outline,
        ),
        _blur_paint(sh.color, sh.radius),
    )
    canvas.restore()


def _paint_inner(
    canvas: "skia.Canvas",
    rect: "skia.Rect",
    corner_radius: float,
    oval: bool,
    sh: ShadowSpec,
    within: "skia.Rect | None",
    outline: "skia.Path | None",
) -> None:
    """Blur everything OUTSIDE the moved shape, clipped to the shape itself.

    For a rounded rect that is drawn as its equivalent: blur is linear and the
    field reaches past the blur, so inside the shape "blur(field - moved shape)"
    is "colour - blur(moved shape)". Inside a layer clipped to the shape, fill
    the shadow colour and erase it with the blurred moved rounded rect
    (``kDstOut``): no path boolean, and the blur is Skia's rounded-rect one.
    A plain rect keeps the path, which Skia already special-cases; an oval, a cut
    or an outline keeps it too.
    """
    if within is None and outline is None and not oval and corner_radius > 0:
        canvas.save()
        canvas.clipRRect(
            _rrect(rect, corner_radius, False), skia.ClipOp.kIntersect, True
        )
        canvas.saveLayer(rect.makeOutset(1, 1), None)
        canvas.drawColor(sh.color, skia.BlendMode.kSrc)
        erase = _blur_paint(0xFF000000, sh.radius)
        erase.setBlendMode(skia.BlendMode.kDstOut)
        canvas.drawRRect(
            _rrect(rect, corner_radius, False, sh.offset_x, sh.offset_y), erase
        )
        canvas.restore()
        canvas.restore()
        return
    margin = sh.radius + abs(sh.offset_x) + abs(sh.offset_y) + _INNER_MARGIN
    field = skia.Path()
    field.addRect(
        skia.Rect.MakeXYWH(
            rect.left() - margin,
            rect.top() - margin,
            rect.width() + 2 * margin,
            rect.height() + 2 * margin,
        )
    )
    outside = skia.Op(
        field,
        shape_path(
            rect,
            corner_radius,
            oval=oval,
            dx=sh.offset_x,
            dy=sh.offset_y,
            within=within,
            outline=outline,
        ),
        skia.PathOp.kDifference_PathOp,
    )
    if outside is None or outside.isEmpty():
        return
    canvas.save()
    canvas.clipPath(
        shape_path(rect, corner_radius, oval=oval, within=within, outline=outline),
        skia.ClipOp.kIntersect,
        True,
    )
    canvas.drawPath(outside, _blur_paint(sh.color, sh.radius))
    canvas.restore()


def paint_shadows(
    canvas: "skia.Canvas",
    rect: "skia.Rect",
    corner_radius: float,
    shadows: "Sequence[ShadowSpec]",
    *,
    inner: bool,
    oval: bool = False,
    within: "skia.Rect | None" = None,
    outline: "skia.Path | None" = None,
) -> None:
    """Paint the ``inner`` (or outer) half of ``shadows`` around ``rect``.

    *within* casts them from the shape cut to that rectangle, *outline* from
    that path (``shape_path``).

    Called twice by the layered fill — once for the outer layers, under the
    fill, and once for the inner ones, over it. Within each half the layers
    paint in the order they were declared, so a later one sits on top.
    """
    if not shadows or rect.width() <= 0 or rect.height() <= 0:
        return
    for sh in shadows:
        if sh.inner != inner or not sh.paints():
            continue
        if inner:
            _paint_inner(canvas, rect, corner_radius, oval, sh, within, outline)
        else:
            _paint_outer(canvas, rect, corner_radius, oval, sh, within, outline)
