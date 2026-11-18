"""Paint the theme's placeholder where an image has no picture (ADR-406).

An image that writes ``?md2ui.placeholder=<name>`` or ``<name>:<text>`` and has no
picture to show (its source left out, still loading, or failed) paints the theme's
placeholder of that name instead of the default ones: its fill, its image, and centred
over them the image's text (initials, one emoji) or else the placeholder's own icon.
An image that names none, or a name the theme does not declare, paints the theme's
default placeholder for its state (`#### Loading`, `Broken`, `Missing`) when there is one,
and md2ui's own otherwise. Either paints inside the clip the picture would have used,
so a circle, a rounded corner or a ratio shapes it exactly as it shapes a photo.

Only paint reads this; the box was laid out for the picture and does not move.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.render_colors import _rotate_color, _rotation_slot
from md2ui.pipeline.render_fills import draw_picture
from md2ui.pipeline.render_glyph_faces import glyph_advance
from md2ui.pipeline.render_placeholders import (
    NO_PICTURE,
    NO_PICTURE_COLOR,
    decode_theme_image,
    theme_picture,
)
from md2ui.pipeline.render_settings import VIEW
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.render_text_paint import draw_glyph_runs
from md2ui.pipeline.render_text_scopes import _base_role_style, _style_fonts
from md2ui.pipeline.theme_model import Theme
from md2ui.pipeline.theme_placeholders import ImagePlaceholder
from md2ui.utils.image_cache import Picture
from md2ui.utils.image_params import placeholder_ref
from md2ui.utils.font_loader import make_font

Painter = Callable[[skia.Canvas, skia.Rect], None]


def _state(img: "Picture | None") -> str | None:
    """Why *img* is not a picture (``loading``, ``broken``, ``missing``), or None
    when it is one."""
    if img is NO_PICTURE:
        return "missing"
    if img is not None and img is VIEW.placeholder_broken:
        return "broken"
    if img is not None and any(
        img is p for p in (VIEW.placeholder_raster, VIEW.placeholder_vector)
    ):
        return "loading"
    return None


# A placeholder's `Image:` decoded once per source, as theme background images are.
_decode = functools.cache(decode_theme_image)


def _typeface(name: str, theme: Theme, fonts: FontSet) -> tuple[skia.Typeface, int]:
    """The face and colour of the text style *name* (Text, Lead, Heading 2…)."""
    level = name.removeprefix("heading").strip()
    if level.isdigit() and int(level) in theme.headings:
        style = theme.headings[int(level)]
        faces = fonts.heading_typefaces.get(int(level))
        bold = (style.font_weight or "").lower() in ("bold", "700", "800", "900")
        face = (faces[2] if bold else faces[0]) if faces else fonts.typeface
        return face, style.color
    role = name if name in ("muted", "lead", "display", "key", "value") else "text"
    style = _base_role_style(theme, role)
    return _style_fonts(style, fonts).typeface, style.color


def _size(size: tuple[float, bool], side: float) -> float:
    value, share = size
    return side * value / 100.0 if share else value


def named_placeholder(
    img: "Picture | None", content: str, node: dict, theme: Theme, fonts: FontSet
) -> Painter | None:
    """The painter of the placeholder *content*'s image names, or of the theme's
    default for its state, when *img* is not a picture; else None."""
    state = _state(img)
    if state is None:
        return None
    ref = placeholder_ref(content)
    ph = theme.image_placeholders.get(ref[0]) if ref else None
    text = ref[1] if ref and ph is not None else ""
    if ph is None:
        ph = theme.image_placeholder_defaults.get(state)
    if ph is None and ref and ref[1] and not theme.image_placeholders:
        # The theme styles no placeholders at all: the written text (initials,
        # an emoji) still shows, in the built-in grey, rather than a bare
        # circle. A theme that declares placeholders keeps an undeclared name
        # quiet.
        ph, text = ImagePlaceholder(), ref[1]
    if ph is None:
        return None
    index, chain = _rotation_slot(node, theme)
    return lambda canvas, dst: _paint(canvas, dst, ph, text, index, chain, theme, fonts)


def _paint(
    canvas: skia.Canvas,
    dst: skia.Rect,
    ph: ImagePlaceholder,
    text: str,
    index: int,
    chain: tuple,
    theme: Theme,
    fonts: FontSet,
) -> None:
    fill = _rotate_color(
        ph.fill_colors, NO_PICTURE_COLOR, index, theme, "placeholder", chain
    )
    canvas.drawRect(dst, skia.Paint(Color=fill, AntiAlias=True))
    picture = theme_picture(ph.bg_image, _decode)
    if picture is not None and picture.width() > 0 and picture.height() > 0:
        _cover(canvas, picture, dst)
    glyphs = text or ph.icon
    if not glyphs:
        return
    face, style_color = _typeface(ph.text_style, theme, fonts)
    color = _rotate_color(
        ph.text_colors, style_color, index, theme, "placeholder", chain
    )
    side = min(dst.width(), dst.height())
    size = _size(ph.text_size if text else ph.icon_size, side)
    width = glyph_advance(glyphs, fonts.emoji, face, size)
    metrics = make_font(face, size).getMetrics()
    x = dst.left() + (dst.width() - width) / 2
    y = dst.top() + (dst.height() - (metrics.fDescent - metrics.fAscent)) / 2
    paint = skia.Paint(Color=color, AntiAlias=True)
    draw_glyph_runs(
        canvas, glyphs, x, y - metrics.fAscent, fonts.emoji, face, size, paint
    )


def _cover(canvas: skia.Canvas, picture: "skia.Image", dst: skia.Rect) -> None:
    """*picture* centred and cropped to fill *dst*, as theme background images are."""
    iw, ih = picture.width(), picture.height()
    scale = max(dst.width() / iw, dst.height() / ih)
    w, h = dst.width() / scale, dst.height() / scale
    draw_picture(
        canvas, picture, skia.Rect.MakeXYWH((iw - w) / 2, (ih - h) / 2, w, h), dst
    )
