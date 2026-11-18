"""The code blocks a host has scrolled, painted over the recorded document.

The document is recorded once per width with every block at offset 0 (ADR-401). A
block the user has scrolled, or is pointing at, is painted again each frame on top
of its recorded copy, at its own offset: its background is opaque, so the repaint
hides the copy underneath. It repaints inside the block's shape inset by a pixel,
so the recorded anti-aliased edge is never painted twice (which would darken it);
nothing that moves reaches that pixel — it is padding, or the right fade. A frame
with nothing scrolled or hovered is the recording alone, pixel for pixel.

The offsets are the host's (``Scene.scrollables`` says what may scroll, ADR-404);
nothing here decides them.
"""

from __future__ import annotations

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_code_blocks import Scrollable, draw_code_block
from md2ui.pipeline.render_fills import _paint_layered_fill
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import Theme
from md2ui.utils.scroll_state import draw_block_thumb

# Where a block's thumbs sit: this far in from its bottom edge, and its right.
_THUMB_INSET = 8.0


def clamp_offsets(
    offsets: dict[str, tuple[float, float]], scrollables: list[Scrollable]
) -> dict[str, tuple[float, float]]:
    """*offsets* (across, down) kept for the blocks that can still scroll, each
    within its new range: a rebuild at another width, or the agent re-sending the
    answer, keeps where the user had scrolled to while the block is still there."""
    ranges = {s.node_id: (s.max_offset, s.max_offset_y) for s in scrollables}
    return {
        node_id: (
            max(0.0, min(dx, ranges[node_id][0])),
            max(0.0, min(dy, ranges[node_id][1])),
        )
        for node_id, (dx, dy) in offsets.items()
        if node_id in ranges
    }


def scrolled_by(
    offsets: dict[str, tuple[float, float]],
    node_id: str,
    dx: float,
    dy: float,
    scrollables: list[Scrollable],
) -> dict[str, tuple[float, float]]:
    """*offsets* with block *node_id* moved by ``(dx, dy)``, within its range."""
    at_x, at_y = offsets.get(node_id, (0.0, 0.0))
    return clamp_offsets({**offsets, node_id: (at_x + dx, at_y + dy)}, scrollables)


def scrollable_at(
    scrollables: list[Scrollable], x: float, y: float
) -> Scrollable | None:
    """The scrollable block under content point ``(x, y)``, if any."""
    return next(
        (
            s
            for s in scrollables
            if s.x <= x < s.x + s.width and s.y <= y < s.y + s.height
        ),
        None,
    )


def _inner_shape(s: Scrollable, corner_radius: float) -> skia.RRect:
    """The block's rounded rectangle, one pixel in from its painted edge."""
    radius = max(0.0, min(corner_radius, s.width / 2.0, s.height / 2.0) - 1.0)
    rect = skia.Rect.MakeXYWH(s.x + 1.0, s.y + 1.0, s.width - 2.0, s.height - 2.0)
    return skia.RRect.MakeRectXY(rect, radius, radius)


def paint_scrolled(
    canvas: skia.Canvas,
    scrollables: list[Scrollable],
    offsets: dict[str, tuple[float, float]],
    hovered: str | None,
    node_index: dict,
    fonts: FontSet,
    theme: Theme,
    background_images: dict | None = None,
) -> None:
    """Each scrolled block at its offsets, and its thumbs on the scrolled or
    hovered one; in content coordinates, after the document's replay."""
    block = theme.code_blocks
    face = fonts.code_block or fonts.mono or fonts.typeface
    image = (background_images or {}).get(("element", block.copy_button.bg_image))
    for s in scrollables:
        offset, offset_y = offsets.get(s.node_id, (0.0, 0.0))
        scrolled = offset > 0.0 or offset_y > 0.0
        if not scrolled and s.node_id != hovered:
            continue
        nd = node_index.get(s.content_id)
        if nd is None:
            continue
        if scrolled:
            canvas.save()
            canvas.clipRRect(_inner_shape(s, block.corner_radius), True)
            draw_code_block(
                canvas,
                LayoutBox(
                    s.x, s.y, s.width, s.height, s.content_id, bg_stack=s.bg_stack
                ),
                nd.get("content", ""),
                nd.get("code_language"),
                face,
                theme,
                paint_fill=_paint_layered_fill,
                emoji_tf=fonts.emoji,
                button_image=image,
                offset=offset,
                offset_y=offset_y,
            )
            canvas.restore()
        draw_block_thumb(
            canvas,
            s.x + block.padding.left,
            s.y + s.height - _THUMB_INSET,
            s.width - block.padding.x,
            offset,
            s.width,
            s.content_width,
        )
        draw_block_thumb(
            canvas,
            s.x + s.width - _THUMB_INSET,
            s.y + block.padding.top,
            s.height - block.padding.y,
            offset_y,
            s.height,
            s.content_height,
            vertical=True,
        )
