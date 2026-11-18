"""The window's capture channel: the agent asks for a screenshot, the window answers.

Pressing ``S`` saves a PNG for the USER (``app.save_screenshot``). This is the same
capture asked for from OUTSIDE, so an agent driving the wire can see what the user
is actually looking at — the scroll position, an optimistic tick, a slider left
mid-drag, the state light in the bar. A headless ``md2ui render`` reproduces none
of those: it renders the Markdown, not the window. Without this an agent can verify
that an event was *verified* and never that it was *drawn*.

Two modes, and the difference is the point:

* ``view`` — the window as it stands, chrome and scroll included: what the user sees;
* ``document`` — the whole layout, unscrolled and unframed, which is what ``S`` saves
  and what the render snapshot compares.

**No new wire frame.** A screenshot is a debug affordance of the local demo shell
(ADR-602), not part of the display protocol (ADR-601) — md2ui-ts must not have to
implement it to be a conforming client. So the two ends share a directory instead:
the server writes ``request.json``, the window writes the PNG beside it.

**The app owns the watcher** (ADR-600). The server only writes a file; the window
notices it on its next tick, at most 50 ms away, because the loop already wakes
that often. Both writes land through ``os.replace``, so neither end can read half a
file, and a failure is written as ``<out>.error`` rather than left to time out.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import skia

from md2ui.utils.png import encode_png

REQUEST_NAME = "request.json"
TAKEN_NAME = "request.taken.json"
MODES = ("view", "document")
DEFAULT_TIMEOUT = 15.0


class CaptureError(RuntimeError):
    """The window could not answer, or did not answer in time."""


@dataclass(frozen=True, slots=True)
class Request:
    """One capture the window has been asked for."""

    out: Path
    mode: str


def _replace(path: Path, data: bytes) -> None:
    """Write *data* to *path* so a reader sees all of it or none of it."""
    part = path.with_name(path.name + ".part")
    part.write_bytes(data)
    os.replace(part, path)


# --- the window's end ----------------------------------------------------------


class CaptureChannel:
    """Polled once per tick: a request, then the image that answers it."""

    def __init__(self, directory: Path) -> None:
        self.request_path = directory / REQUEST_NAME
        self._taken_path = directory / TAKEN_NAME

    def pending(self) -> Request | None:
        """The request written since the last poll, or None. A malformed one is
        reported and dropped: it is read once, so it cannot spin the loop.

        The window takes a request by moving it aside, so "new" never depends on
        a clock: Linux stamps mtimes once per kernel tick, and a request written
        in the same tick as the last one was missed. A request already waiting
        when the window opens is taken on the first poll.
        """
        try:
            os.replace(self.request_path, self._taken_path)
        except OSError:  # nothing asked, or the asker is mid-replace: next tick
            return None
        try:
            frame = json.loads(self._taken_path.read_text(encoding="utf-8"))
            out, mode = Path(frame["out"]), str(frame.get("mode", "view"))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"[capture] unreadable request: {exc}", file=sys.stderr)
            return None
        finally:
            self._taken_path.unlink(missing_ok=True)
        return Request(out, mode if mode in MODES else "view")

    def answer(self, request: Request, image: skia.Image | None) -> None:
        """Hand *image* back, or say why there is none."""
        data = _encode(image)
        if data is None:
            self.fail(request, "the window could not encode a capture that size")
            return
        _replace(request.out, data)
        print(f"[capture] {request.mode} -> {request.out}", file=sys.stderr)

    def fail(self, request: Request, reason: str) -> None:
        request.out.with_name(request.out.name + ".error").write_text(
            reason, encoding="utf-8"
        )


def _encode(image: skia.Image | None) -> bytes | None:
    """PNG bytes, as ``save_png`` writes them, without a path to write through."""
    return encode_png(image) if image is not None else None


def viewport_image(context, window, draw, scroll) -> skia.Image | None:
    """The window exactly as it stands: its size, its scroll, its chrome.

    Drawn into its own render target rather than read back from the on-screen
    surface, whose contents are undefined after a buffer swap. *draw* is the
    window's own ``_draw``, so this cannot drift from the frame the user sees.
    """
    import glfw  # only the window has one; the server end imports this module too

    win_w, win_h = glfw.get_window_size(window)
    fb_w = glfw.get_framebuffer_size(window)[0]
    dpr = fb_w / win_w if win_w > 0 else 1.0
    shot = skia.Surface.MakeRenderTarget(
        context,
        skia.Budgeted.kNo,
        skia.ImageInfo.MakeN32Premul(
            max(1, int(win_w * dpr)), max(1, int(win_h * dpr))
        ),
    )
    if shot is None:
        return None
    with shot as canvas:
        draw(canvas, win_w, win_h, scroll, dpr)
    shot.flushAndSubmit()
    return shot.makeImageSnapshot()


# --- the server's end ------------------------------------------------------------


def ask(directory: Path, out: Path, mode: str = "view") -> None:
    """Ask the window watching *directory* for a capture at *out*."""
    if mode not in MODES:
        raise CaptureError(f"mode is one of {', '.join(MODES)}, not {mode!r}")
    frame = json.dumps({"out": str(out.resolve()), "mode": mode}).encode()
    _replace(directory / REQUEST_NAME, frame)


def answer(out: Path, timeout: float = DEFAULT_TIMEOUT) -> bytes:
    """Block until the window answers, and return the PNG. Raises
    :class:`CaptureError` when it refuses, or when nothing arrives in time —
    which is what a closed window looks like from here."""
    error = out.with_name(out.name + ".error")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if out.exists():
            return out.read_bytes()
        if error.exists():
            raise CaptureError(error.read_text(encoding="utf-8").strip())
        time.sleep(0.02)
    raise CaptureError(
        f"the window did not answer within {timeout:g} s; it may be closed"
    )


def capture(directory: Path, out: Path, mode: str, timeout: float) -> bytes:
    """Ask, then wait: one capture, as PNG bytes."""
    for stale in (out, out.with_name(out.name + ".error")):
        stale.unlink(missing_ok=True)
    ask(directory, out, mode)
    return answer(out, timeout)


def shrink(data: bytes, width: int) -> bytes:
    """*data* scaled down to *width* pixels wide, when it is wider.

    An agent pays for a picture by its area, and at about 480 px the layout, the
    buttons and whether an image loaded are all still plain; only small text is
    lost. So a look is cheap by default, and a close read is asked for.
    """
    image = skia.Image.MakeFromEncoded(skia.Data.MakeWithCopy(data))
    if image is None or width <= 0 or image.width() <= width:
        return data
    height = max(1, round(image.height() * width / image.width()))
    sampling = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)
    return _encode(image.resize(width, height, sampling)) or data
