"""The prompt bar: a connected window's own text field and Send button (ADR-601).

For the Claude Desktop and Claude Code demos the window hosts a native field, so
the user can prompt the agent from md2ui itself. In md2ui-ts the host frontend
builds its own field; this one exists only when the window is a wire client
(``md2ui-app --connect``).

It is chrome, not document: drawn every frame over the window's bottom edge,
outside the recorded picture (ADR-401), with the viewport ending above it
(``VIEW.prompt_bar_h``). It also shows what the agent is doing, from the
server's state frame: listening, working (input is blocked), or idle. While idle
it counts what the window sent and, if nobody has listened for a moment, says it
is queued (:class:`QueuedNotice`). Once the server is gone it says so, and that
nothing more is sent: a draft stays in the field, and a click changes nothing.

Two halves, so the logic is testable without a window: :class:`PromptText` is
the single-line editor, and :class:`PromptBar` draws it and takes the window's
keys, characters and clicks. On macOS a native control edits the text instead
(:mod:`md2ui.app_native_field`), and the bar draws everything but the text. How it looks is the window's own
(``app_chrome.ChromeStyle``), never THEME.md's: the theme styles the answer, and
a frontend styles its own controls.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import glfw
import skia

from md2ui.app_chrome import ChromeStyle
from md2ui.wire import MAX_PROMPT_BYTES
from md2ui.wire_client import DISCONNECTED, StateWords
from md2ui.utils.font_loader import make_font

_PAD = 12.0
_GAP = 8.0
_BUTTON_W = 84.0
_INSET = 14.0

# What the empty field says, by the server's state (None: none received yet).
PLACEHOLDERS: dict[str | None, str] = {
    "l": "Message the agent…",
    "w": "The agent is working — or waiting for your approval in the chat.",
    "i": "The agent isn't listening. Type, then say “check md2ui” in the chat.",
    None: "Waiting for the agent…",
    DISCONNECTED: "Disconnected from the agent: nothing typed here is sent.",
}
# Said above the bar for as long as the window is disconnected.
DISCONNECTED_NOTICE = (
    "Disconnected: the agent's session ended, so clicks and messages here are not sent"
)
_SHORTCUT = glfw.MOD_SUPER | glfw.MOD_CONTROL
# How long `i` must last after the first queued input before the notice shows:
# between one wait and the next the agent is `i` for a moment, and that gap
# should never flash it.
NOTICE_DELAY_S = 2.0
_NOTICE_H = 32.0


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


@dataclass
class QueuedNotice:
    """What the window sent while nobody listened, said once it has waited.

    In ``i`` a click or a typed prompt waits in the server's queue until the user
    asks for it in the chat (ADR-601), and nothing on screen says so: the button
    stays pending, and a sent prompt has already left the field. Counts start at
    entering ``i`` and end on leaving it, which is the delivery the user then sees.
    Only what waits for an agent is counted: a click the backend answers leaves
    the count when the server releases it (``u``), as its button does.
    """

    clicks: list[int] = field(default_factory=list)  # each queued click's ordinal
    messages: int = 0
    first: float | None = None

    def click(self, x: int, now: float) -> None:
        """A click on target ordinal *x* sent."""
        self.clicks.append(x)
        self._started(now)

    def message(self, now: float) -> None:
        """A typed prompt sent."""
        self.messages += 1
        self._started(now)

    def _started(self, now: float) -> None:
        if self.first is None:
            self.first = now

    def release(self, answered: list[int]) -> None:
        """The clicks on these ordinals were answered without an agent."""
        for x in answered:
            if x in self.clicks:
                self.clicks.remove(x)
        if not self.clicks and not self.messages:
            self.first = None

    def clear(self) -> None:
        self.clicks, self.messages, self.first = [], 0, None

    def text(self, now: float) -> str | None:
        """The notice to show at *now*, or None while there is none yet."""
        if self.first is None or now - self.first < NOTICE_DELAY_S:
            return None
        parts = [
            _count(n, noun)
            for n, noun in ((len(self.clicks), "click"), (self.messages, "message"))
            if n
        ]
        them = "it" if len(self.clicks) + self.messages == 1 else "them"
        return (
            f"{' and '.join(parts)} queued — the agent will see {them} when you say "
            "“check md2ui” in the chat"
        )


@dataclass
class PromptText:
    """A single-line editor: the text and the caret, nothing drawn."""

    text: str = ""
    caret: int = 0

    def insert(self, piece: str) -> None:
        """Type or paste *piece* at the caret. A pasted line break becomes a
        space, and the text stops at the wire's prompt size."""
        piece = " ".join(piece.splitlines())
        room = MAX_PROMPT_BYTES - len(self.text.encode())
        while piece and len(piece.encode()) > room:
            piece = piece[:-1]
        self.text = self.text[: self.caret] + piece + self.text[self.caret :]
        self.caret += len(piece)

    def backspace(self) -> None:
        if self.caret > 0:
            self.text = self.text[: self.caret - 1] + self.text[self.caret :]
            self.caret -= 1

    def delete(self) -> None:
        self.text = self.text[: self.caret] + self.text[self.caret + 1 :]

    def move(self, to: int) -> None:
        self.caret = max(0, min(len(self.text), to))

    def take(self) -> str:
        """The text to send, stripped, and the field emptied; '' when blank."""
        out = self.text.strip()
        if out:
            self.text, self.caret = "", 0
        return out


@dataclass(frozen=True)
class _Box:
    x: float
    y: float
    w: float
    h: float

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h

    def rect(self) -> skia.Rect:
        return skia.Rect.MakeXYWH(self.x, self.y, self.w, self.h)


class PromptBar:
    """The bar at the window's bottom edge: the field, the Send button, and the
    agent's state. Coordinates are the window's logical pixels."""

    def __init__(
        self,
        typeface: skia.Typeface,
        style: ChromeStyle | None = None,
        paste: Callable[[], str | bytes | None] | None = None,
        typed: Callable[[], None] | None = None,
    ) -> None:
        self.style = style or ChromeStyle()
        self.editor = PromptText()
        self.focused = False
        self.state: str | None = None
        self.said = StateWords()  # the agent's words beside the state (ADR-613)
        self.paste = paste
        # Called on each key the field takes: the wire's typing frame (ADR-601).
        self.typed = typed
        self._seen: str | None = None
        self._seen_seq = 0
        self.notice = QueuedNotice()
        self._notice_up = False
        self._font = make_font(typeface, self.style.text_size)
        self._scroll = 0.0
        # A native control edits the text instead (app_native_field, macOS).
        self.native = False

    @property
    def locked(self) -> bool:
        """Input is blocked while the agent works on the last input."""
        return self.state == "w"

    @property
    def placeholder(self) -> str:
        """What the empty field says: the question the agent asked while it
        listens for the answer (ADR-613), else the line for its state."""
        if self.state == "l" and self.said.placeholder:
            return self.said.placeholder
        return PLACEHOLDERS.get(self.state, PLACEHOLDERS[None])

    @property
    def can_send(self) -> bool:
        """Only once the server has said what the agent is doing, and not while
        it works. Before any state arrives nothing says the server can take a
        prompt at all: an older one refuses it, and the text would be lost."""
        return self.state not in (None, DISCONNECTED) and not self.locked

    def sync(
        self,
        server_state: str | None,
        seq: int = 0,
        now: float | None = None,
        said: StateWords | None = None,
    ) -> bool:
        """Take the server's state when a frame ARRIVES; True when the bar must be
        redrawn: the state changed, or the queued notice came or went at *now*.

        *seq* counts frames rather than changes, because a repeat carries meaning:
        the server re-states the current state to a client whose event it refused,
        and a window that blocked itself on send (:meth:`lock_for_reply`) has
        nothing else to release it. Comparing values alone discarded exactly that
        frame and left the page locked until the agent's idle deadline.
        *said* is what that frame said beside its letter.
        """
        self.said = said or self.said
        changed = (server_state, seq) != (self._seen, self._seen_seq)
        if changed:
            self._seen, self._seen_seq = server_state, seq
            self.state = server_state
            if server_state != "i":
                self.notice.clear()
        up = self.notice.text(time.monotonic() if now is None else now) is not None
        flipped, self._notice_up = up != self._notice_up, up
        return changed or flipped

    def sent(self, kind: str, now: float | None = None, x: int | None = None) -> None:
        """Input went to the server: a ``"click"`` on ordinal *x* or a
        ``"message"``. Counted while nobody listens; else the window blocks until
        the agent replies. A click with no *x* is one a commit press will report:
        the server records it for that press, so no agent waits on it."""
        if self.state == "i":
            at = time.monotonic() if now is None else now
            if kind == "message":
                self.notice.message(at)
            elif x is not None:
                self.notice.click(x, at)
        self.lock_for_reply()

    def lock_for_reply(self) -> None:
        """Input just went to a listening agent: block at once, before the
        server's ``w`` arrives. Not when nobody listens, or nothing would unlock."""
        if self.state == "l":
            self.state = "w"

    def _boxes(self, win_w: float, win_h: float) -> tuple[_Box, _Box, _Box]:
        bar_h = self.style.bar_h
        top = win_h - bar_h
        bar = _Box(0.0, top, win_w, bar_h)
        inner_h = bar_h - 2 * _PAD
        button = _Box(win_w - _PAD - _BUTTON_W, top + _PAD, _BUTTON_W, inner_h)
        field_w = max(0.0, button.x - _GAP - _PAD)
        return bar, _Box(_PAD, top + _PAD, field_w, inner_h), button

    def hit(self, x: float, y: float, win_w: float, win_h: float) -> str | None:
        """``"send"``, ``"field"``, ``"bar"``, or None when (x, y) is above it."""
        bar, field, button = self._boxes(win_w, win_h)
        if button.contains(x, y):
            return "send"
        if field.contains(x, y):
            return "field"
        return "bar" if bar.contains(x, y) else None

    def on_char(self, codepoint: int) -> bool:
        """A typed character; True when the field took it."""
        if not self.focused or self.locked:
            return False
        self.editor.insert(chr(codepoint))
        self.took_key()
        return True

    def took_key(self) -> None:
        """The field took a key: the user is typing."""
        if self.typed is not None:
            self.typed()

    def composing(self) -> None:
        """Called each tick: an unsent draft keeps the user typing through a
        pause, so a grace waits for a reply still being written. The wire's
        throttle keeps it to one frame a second."""
        if self.editor.text.strip() and not self.locked:
            self.took_key()

    def on_key(self, key: int, mods: int) -> str:
        """A key while the field has focus: ``"send"`` for Enter, ``"blur"`` for
        Esc, else ``"edit"``. Every key is the field's while it has focus, so the
        window's one-letter shortcuts never fire mid-sentence."""
        if key in (glfw.KEY_ENTER, glfw.KEY_KP_ENTER):
            return "send"
        if key == glfw.KEY_ESCAPE:
            self.focused = False
            return "blur"
        if self.locked:
            return "edit"
        e = self.editor
        if key == glfw.KEY_BACKSPACE:
            e.backspace()
        elif key == glfw.KEY_DELETE:
            e.delete()
        elif key == glfw.KEY_LEFT:
            e.move(e.caret - 1)
        elif key == glfw.KEY_RIGHT:
            e.move(e.caret + 1)
        elif key in (glfw.KEY_HOME, glfw.KEY_UP):
            e.move(0)
        elif key in (glfw.KEY_END, glfw.KEY_DOWN):
            e.move(len(e.text))
        elif key == glfw.KEY_V and mods & _SHORTCUT and self.paste is not None:
            pasted = self.paste()
            if isinstance(pasted, bytes):
                pasted = pasted.decode("utf-8", "replace")
            if pasted:
                e.insert(pasted)
        self.took_key()
        return "edit"

    def submit(self) -> str:
        """The text to send, or '' when there is none or it cannot go yet; then
        the text stays in the field."""
        return self.editor.take() if self.can_send else ""

    def draw(self, canvas: skia.Canvas, win_w: float, win_h: float) -> None:
        st = self.style
        bar, field, button = self._boxes(win_w, win_h)
        canvas.drawRect(bar.rect(), skia.Paint(Color=st.bar_bg))
        shape = skia.RRect.MakeRectXY(field.rect(), st.radius, st.radius)
        canvas.drawRRect(shape, skia.Paint(AntiAlias=True, Color=st.field_bg))
        focused = self.focused and not self.locked
        canvas.drawRRect(
            shape,
            skia.Paint(
                AntiAlias=True,
                Style=skia.Paint.kStroke_Style,
                StrokeWidth=1.5 if focused else 1.0,
                Color=st.focus_stroke if focused else st.field_stroke,
            ),
        )
        if not self.native:
            self._draw_text(canvas, field)
        self._draw_button(canvas, button)
        notice = self.notice.text(time.monotonic())
        if self.state == DISCONNECTED:
            notice = DISCONNECTED_NOTICE
        if notice is not None:
            self._draw_notice(canvas, notice, bar, win_w)

    def _draw_notice(
        self, canvas: skia.Canvas, text: str, bar: _Box, win_w: float
    ) -> None:
        """The queued notice, a pill just above the bar, clipped to the window."""
        st = self.style
        w = min(self._font.measureText(text) + 2 * _INSET, win_w - 2 * _PAD)
        pill = _Box(_PAD, bar.y - _GAP - _NOTICE_H, max(0.0, w), _NOTICE_H)
        canvas.drawRRect(
            skia.RRect.MakeRectXY(pill.rect(), st.radius, st.radius),
            skia.Paint(AntiAlias=True, Color=st.notice_bg),
        )
        canvas.save()
        canvas.clipRect(pill.rect())
        canvas.drawString(
            text,
            pill.x + _INSET,
            self._baseline(pill),
            self._font,
            skia.Paint(AntiAlias=True, Color=st.notice_ink),
        )
        canvas.restore()

    def draw_step(
        self, canvas: skia.Canvas, cx: float, top: float, max_w: float
    ) -> None:
        """The step the agent is on, a pill centred under the working animation
        at *top*, while it works and the server said one (ADR-613)."""
        step = self.said.note if self.locked else None
        if not step:
            return
        st = self.style
        w = min(self._font.measureText(step) + 2 * _INSET, max_w - 2 * _PAD)
        pill = _Box(cx - w / 2, top, max(0.0, w), _NOTICE_H)
        canvas.drawRRect(
            skia.RRect.MakeRectXY(pill.rect(), st.radius, st.radius),
            skia.Paint(AntiAlias=True, Color=st.notice_bg),
        )
        canvas.save()
        canvas.clipRect(pill.rect())
        canvas.drawString(
            step,
            pill.x + _INSET,
            self._baseline(pill),
            self._font,
            skia.Paint(AntiAlias=True, Color=st.notice_ink),
        )
        canvas.restore()

    def _baseline(self, box: _Box) -> float:
        return box.y + box.h / 2 + self.style.text_size * 0.35

    def _draw_text(self, canvas: skia.Canvas, field: _Box) -> None:
        st = self.style
        inner_x, inner_w = field.x + _INSET, max(0.0, field.w - 2 * _INSET)
        text, caret = self.editor.text, self.editor.caret
        caret_x = self._font.measureText(text[:caret]) if text else 0.0
        # Keep the caret in view: the text slides left once it outgrows the field.
        if caret_x - self._scroll > inner_w - 2:
            self._scroll = caret_x - inner_w + 2
        elif caret_x < self._scroll or not text:
            self._scroll = caret_x
        canvas.save()
        canvas.clipRect(skia.Rect.MakeXYWH(inner_x, field.y, inner_w, field.h))
        ink = st.muted if self.locked or not text else st.ink
        shown = text or self.placeholder
        canvas.drawString(
            shown,
            inner_x - (self._scroll if text else 0.0),
            self._baseline(field),
            self._font,
            skia.Paint(AntiAlias=True, Color=ink),
        )
        if self.focused and not self.locked:
            x = inner_x + caret_x - self._scroll
            canvas.drawLine(
                x,
                field.y + 11,
                x,
                field.y + field.h - 11,
                skia.Paint(AntiAlias=True, Color=st.ink, StrokeWidth=1.5),
            )
        canvas.restore()

    def _draw_button(self, canvas: skia.Canvas, button: _Box) -> None:
        st = self.style
        ready = bool(self.editor.text.strip()) and self.can_send
        canvas.drawRRect(
            skia.RRect.MakeRectXY(button.rect(), st.radius, st.radius),
            skia.Paint(AntiAlias=True, Color=st.button_bg if ready else st.button_off),
        )
        label = "Working…" if self.locked else "Send"
        width = self._font.measureText(label)
        canvas.drawString(
            label,
            button.x + (button.w - width) / 2,
            self._baseline(button),
            self._font,
            skia.Paint(AntiAlias=True, Color=st.button_ink),
        )
