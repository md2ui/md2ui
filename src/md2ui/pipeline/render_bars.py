"""The drawn datapoint bars: a value's linear bar and its circular ring.

A bar paints a track across its box and a fill for the value; a ring paints the
same two as a circle, behind its card's text. Both read the value's share from
``_bar_ratio`` so the two families agree on what a value fills.
"""

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_backgrounds import SectionBox
from md2ui.pipeline.render_colors import _replace_color
from md2ui.pipeline.render_fills import (
    _DEFAULT_BAR_FILL,
    _DEFAULT_BAR_TRACK,
    _paint_layered_fill,
    _replaced_gradient,
)
from md2ui.pipeline.render_measure import _bar_track_height, _dp_bar_theme
from md2ui.pipeline.render_placeholders import theme_picture
from md2ui.pipeline.render_shadows import draw_stroke
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import BarTheme, Theme


def _bar_ratio(props: dict) -> float:
    """The value as a share of its whole, signed: -1 to 1."""
    if "percent" in props:
        v, mx = float(props["percent"]), 100.0
    else:
        v = float(props.get("value", 0.0))
        mx = float(props.get("max", 0.0)) or 1.0
    return max(-1.0, min(1.0, v / mx))


def _bar_fraction(props: dict) -> float:
    """How much of a ring a value fills; a ring has no side to go below zero on."""
    return max(0.0, _bar_ratio(props))


def _paint_bar(
    canvas: skia.Canvas,
    x: float,
    y: float,
    w: float,
    bt: "BarTheme",
    frac: float,
    bg_stack: "tuple[int | str, ...]" = (),
    theme: "Theme | None" = None,
) -> None:
    """Track (full width) + fill (frac of the padded inner width) at (x, y).

    A negative *frac* is a value below zero: the track is read from its right
    edge, which is zero, and the fill runs left from it, as a chart of losses
    only does."""
    pad = bt.track.padding
    track_h = _bar_track_height(bt)
    track_r = bt.track.corner_radius
    track_color = bt.track.bg_colors[0] if bt.track.bg_colors else _DEFAULT_BAR_TRACK
    if theme is not None:
        track_color = _replace_color(track_color, bg_stack, theme, "fill")
    if bt.track_enabled:
        _paint_layered_fill(
            canvas,
            skia.Rect.MakeXYWH(x, y, w, track_h),
            bg_color=track_color,
            image=theme_picture(bt.track.bg_image),
            gradient=(
                _replaced_gradient(bt.track.gradient, bg_stack, theme)
                if theme is not None
                else bt.track.gradient
            ),
            corner_radius=track_r,
            shadows=bt.track.shadows,
        )
    if (
        bt.track_enabled
        and bt.track.stroke_width > 0
        and bt.track.stroke_color is not None
    ):
        track_stroke = bt.track.stroke_color
        if theme is not None:
            track_stroke = _replace_color(track_stroke, bg_stack, theme, "stroke")
        draw_stroke(
            canvas,
            skia.Rect.MakeXYWH(x, y, w, track_h),
            track_r,
            skia.Paint(
                Color=track_stroke,
                Style=skia.Paint.kStroke_Style,
                StrokeWidth=bt.track.stroke_width,
                AntiAlias=True,
            ),
            bt.track.stroke_align,
        )
    inner_w = max(0.0, w - pad.x)
    if frac == 0.0 or inner_w <= 0.0:
        return
    fill_w = min(max(bt.thickness, inner_w * abs(frac)), inner_w)
    left = x + pad.left
    if frac < 0.0:
        left += inner_w - fill_w
    fill_r = bt.bar.corner_radius
    fill_rect = skia.Rect.MakeXYWH(left, y + pad.top, fill_w, bt.thickness)
    fill_color = bt.bar.bg_colors[0] if bt.bar.bg_colors else _DEFAULT_BAR_FILL
    if frac < 0.0 and bt.negative_color is not None:
        fill_color = bt.negative_color
    if theme is not None:
        fill_color = _replace_color(fill_color, bg_stack, theme, "fill")
    _paint_layered_fill(
        canvas,
        fill_rect,
        bg_color=fill_color,
        image=theme_picture(bt.bar.bg_image),
        gradient=(
            _replaced_gradient(bt.bar.gradient, bg_stack, theme)
            if theme is not None
            else bt.bar.gradient
        ),
        corner_radius=fill_r,
        shadows=bt.bar.shadows,
    )
    if bt.bar.stroke_width > 0 and bt.bar.stroke_color is not None:
        stroke_color = bt.bar.stroke_color
        if theme is not None:
            stroke_color = _replace_color(stroke_color, bg_stack, theme, "stroke")
        draw_stroke(
            canvas,
            fill_rect,
            fill_r,
            skia.Paint(
                Color=stroke_color,
                Style=skia.Paint.kStroke_Style,
                StrokeWidth=bt.bar.stroke_width,
                AntiAlias=True,
            ),
            bt.bar.stroke_align,
        )


def _draw_datapoint_bar(
    canvas: skia.Canvas,
    box: LayoutBox,
    props: dict,
    _fonts: FontSet,
    theme: Theme,
) -> None:
    """One bar-only leaf: track + fill spanning the box width, vertically
    centered. The companion text renders as its own sibling leaves (the
    original markdown nodes), so the layout can arrange them —
    ``kind`` only selects which BarTheme styles the paint."""
    bt = _dp_bar_theme(theme, props.get("kind", ""))
    frac = _bar_ratio(props)
    bar_h = _bar_track_height(bt)
    bar_y = box.y + max(0.0, (box.height - bar_h) / 2.0)
    # Background-aware for EVERY bar family: a bar painting its literal declared
    # colours on whatever card it lands on can vanish (a #101010 fill on a
    # #202020 track is invisible on a dark card). A bar is a bar, and the ring's
    # arc beside it is replaced the same way (see _draw_ring_arc).
    _paint_bar(canvas, box.x, bar_y, box.width, bt, frac, box.bg_stack, theme)


def _draw_ring_arc(canvas: skia.Canvas, sbox: SectionBox, theme: Theme) -> None:
    """The circular bar itself, painted as the ring card's "background": a
    full-circle track plus a round-capped value arc from 12 o'clock, inscribed
    in the SectionBox. The value/unit text render as separate leaves on top."""
    rt = theme.datapoints.ring
    d = min(sbox.width, sbox.height)
    cx = sbox.x + sbox.width / 2.0
    cy = sbox.y + sbox.height / 2.0
    r = max(1.0, (d - rt.thickness) / 2.0)
    oval = skia.Rect.MakeLTRB(cx - r, cy - r, cx + r, cy + r)

    track_color = rt.track.bg_colors[0] if rt.track.bg_colors else _DEFAULT_BAR_TRACK
    track_color = _replace_color(track_color, sbox.bg_stack, theme, "fill")
    canvas.drawOval(
        oval,
        skia.Paint(
            Color=track_color,
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=rt.thickness,
            AntiAlias=True,
        ),
    )
    frac = _bar_fraction(sbox.ring or {})
    if frac > 0.0:
        ring_color = rt.ring.bg_colors[0] if rt.ring.bg_colors else _DEFAULT_BAR_FILL
        ring_color = _replace_color(ring_color, sbox.bg_stack, theme, "fill")
        canvas.drawArc(
            oval,
            -90.0,
            frac * 360.0,
            False,
            skia.Paint(
                Color=ring_color,
                Style=skia.Paint.kStroke_Style,
                StrokeWidth=rt.thickness,
                StrokeCap=skia.Paint.kRound_Cap,
                AntiAlias=True,
            ),
        )
