"""scroll_state.py — 2-D scroll offset tracking and scrollbar overlay rendering."""

import skia  # type: ignore[import-untyped]

SCROLL_SPEED = 30.0  # pixels per scroll tick / arrow-key press

_SCROLLBAR_W = 8
_SCROLLBAR_COLOR = skia.ColorSetARGB(160, 80, 80, 80)
_SCROLLBAR_TRACK_COLOR = skia.ColorSetARGB(50, 150, 150, 150)
_BLOCK_THUMB_H = 4.0  # a block's own thumb: thinner than the page's


class ScrollState:
    """Tracks a 2-D scroll offset and renders overlay scrollbars."""

    def __init__(self) -> None:
        self.x = 0.0
        self.y = 0.0

    def reset(self) -> None:
        self.x = 0.0
        self.y = 0.0

    def pan(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def clamp(
        self,
        content_w: float,
        content_h: float,
        viewport_w: float,
        viewport_h: float,
    ) -> None:
        self.x = max(0.0, min(self.x, max(0.0, content_w - viewport_w)))
        self.y = max(0.0, min(self.y, max(0.0, content_h - viewport_h)))

    def draw_scrollbars(
        self,
        canvas: skia.Canvas,
        track_x: float,
        track_y: float,
        track_w: float,
        track_h: float,
        view_w: float,
        view_h: float,
        content_w: float,
        content_h: float,
    ) -> None:
        """Draw overlay scrollbars.

        The *track* rect (``track_*``) is where the bars are drawn — typically the
        full viewport/background — while ``view_w``/``view_h`` is the actual scroll
        viewport used for thumb size/position (these differ when the content area is
        inset from the background, e.g. by content padding). Reduces to the simple
        case when ``track_* == view_*``.
        """
        track_paint = skia.Paint(
            Color=_SCROLLBAR_TRACK_COLOR, Style=skia.Paint.kFill_Style, AntiAlias=True
        )
        thumb_paint = skia.Paint(
            Color=_SCROLLBAR_COLOR, Style=skia.Paint.kFill_Style, AntiAlias=True
        )

        if content_h > view_h:
            max_sy = content_h - view_h
            tx = track_x + track_w - _SCROLLBAR_W - 2
            canvas.drawRect(
                skia.Rect.MakeXYWH(tx, track_y, _SCROLLBAR_W, track_h), track_paint
            )
            thumb_h = max(20.0, track_h * view_h / content_h)
            thumb_y = track_y + (self.y / max_sy) * (track_h - thumb_h)
            canvas.drawRoundRect(
                skia.Rect.MakeXYWH(tx, thumb_y, _SCROLLBAR_W, thumb_h),
                4,
                4,
                thumb_paint,
            )

        if content_w > view_w:
            max_sx = content_w - view_w
            ty = track_y + track_h - _SCROLLBAR_W - 2
            canvas.drawRect(
                skia.Rect.MakeXYWH(track_x, ty, track_w, _SCROLLBAR_W), track_paint
            )
            thumb_w = max(20.0, track_w * view_w / content_w)
            thumb_x = track_x + (self.x / max_sx) * (track_w - thumb_w)
            canvas.drawRoundRect(
                skia.Rect.MakeXYWH(thumb_x, ty, thumb_w, _SCROLLBAR_W),
                4,
                4,
                thumb_paint,
            )


def split_scroll(
    xoffset: float, yoffset: float, shift: bool, to_block: bool
) -> tuple[float, float, float, float]:
    """One wheel or trackpad event as ``(block_dx, block_dy, page_dx, page_dy)``
    in px.

    An event drives ONE thing: the block its gesture started on, or the page
    (:class:`ScrollLatch` decides which). A block takes both axes and keeps what
    its own range allows, so the part it cannot use is dropped rather than
    passed to the page. Shift turns a vertical wheel horizontal only when the
    event carries no horizontal part: macOS already converts shift+wheel, and
    doing it twice would cancel it.
    """
    if shift and xoffset == 0.0:
        xoffset, yoffset = yoffset, 0.0
    dx, dy = -xoffset * SCROLL_SPEED, -yoffset * SCROLL_SPEED
    return (dx, dy, 0.0, 0.0) if to_block else (0.0, 0.0, dx, dy)


# A gap this long between two scroll events ends a gesture. GLFW reports no
# gesture phases, so a pause is the only boundary there is; a trackpad's momentum
# tail arrives as a steady stream and stays in the gesture that threw it.
LATCH_TIMEOUT = 0.3


class ScrollLatch:
    """Which target one scroll gesture drives: the one under the pointer when it
    starts, kept while its events keep coming. So a page scroll that passes over
    a code block keeps scrolling the page, and a block's never spills into it."""

    def __init__(self, timeout: float = LATCH_TIMEOUT) -> None:
        self.timeout = timeout
        self.target: str | None = None
        self._last = float("-inf")

    def target_for(self, under: str | None, now: float) -> str | None:
        """The target for an event at *now*: *under* (a block's id, or ``None``
        for the page) if it starts a gesture, else the gesture's own."""
        if now - self._last > self.timeout:
            self.target = under
        self._last = now
        return self.target


def draw_block_thumb(
    canvas: skia.Canvas,
    track_x: float,
    track_y: float,
    track_w: float,
    offset: float,
    view_w: float,
    content_w: float,
    vertical: bool = False,
) -> None:
    """A thin thumb for a block scrolled inside the page, in the page
    scrollbars' colour: where *view_w* of *content_w* sits at *offset*, along a
    track starting at ``(track_x, track_y)`` and running *track_w* across, or
    down when *vertical*."""
    if content_w <= view_w:
        return
    thumb_w = max(20.0, track_w * view_w / content_w)
    along = offset / (content_w - view_w) * (track_w - thumb_w)
    rect = (
        skia.Rect.MakeXYWH(track_x, track_y + along, _BLOCK_THUMB_H, thumb_w)
        if vertical
        else skia.Rect.MakeXYWH(track_x + along, track_y, thumb_w, _BLOCK_THUMB_H)
    )
    canvas.drawRoundRect(
        rect,
        _BLOCK_THUMB_H / 2,
        _BLOCK_THUMB_H / 2,
        skia.Paint(Color=_SCROLLBAR_COLOR, AntiAlias=True),
    )
