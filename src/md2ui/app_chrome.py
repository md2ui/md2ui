"""The demo window's own chrome: how its prompt bar and its working animation look.

md2ui draws the ANSWER. How a frontend draws its own controls is the frontend's
business: THEME.md is the user's design system for the answer, read by every
frontend alike, so nothing here belongs in it (ADR-601).
A web or native frontend builds its own field and its own indicator from the
wire's state frame; this module is only what the demo window uses.

Two things, both replaceable without touching the pipeline:

* :class:`ChromeStyle` — the bar's colours and sizes, in one object;
* :class:`WorkingAnimation` — the loop drawn at the centre of the document while
  the agent works, decoded from a FILE: ``assets/demo/working.webp`` by default,
  ``md2ui-app --working-animation PATH`` to swap it. Any animated WebP or GIF
  that Skia decodes will do; a still image is shown still.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import skia

from md2ui import session

DEFAULT_ANIMATION = session.resource_root() / "assets" / "demo" / "working.webp"
_FALLBACK_FRAME_SECONDS = 0.1


@dataclass(frozen=True)
class ChromeStyle:
    """The demo window's chrome in one place: ARGB colours, logical pixels."""

    bar_h: float = 60.0
    bar_bg: int = 0xFFF1F1F3
    field_bg: int = 0xFFFFFFFF
    field_stroke: int = 0xFFD4D4DA
    focus_stroke: int = 0xFF6B6BD6
    ink: int = 0xFF202025
    muted: int = 0xFF8A8A93
    button_bg: int = 0xFF202025
    button_off: int = 0xFFC9C9CF
    button_ink: int = 0xFFFFFFFF
    notice_bg: int = 0xEE202025
    notice_ink: int = 0xFFFFFFFF
    radius: float = 10.0
    text_size: float = 15.0
    working_size: float = 48.0


class WorkingAnimation:
    """An animation file's frames, decoded once, and the frame for a moment."""

    def __init__(self, frames: list[skia.Image], durations: list[float]) -> None:
        self.frames = frames
        self.durations = durations  # seconds, one per frame
        self.period = sum(durations)

    @classmethod
    def load(cls, path: Path) -> WorkingAnimation | None:
        """Decode every frame of *path*. None, with a message on stderr, when the
        file is missing or is not an image Skia decodes: the window then shows
        the state in its bar alone."""
        try:
            data = path.read_bytes()
        except OSError as exc:
            print(f"[working] cannot read {path}: {exc}", file=sys.stderr)
            return None
        # Held for as long as the codec decodes: skia-python does not keep it
        # alive, and a temporary is freed while frames are still read from it.
        blob = skia.Data.MakeWithCopy(data)
        try:  # skia-python raises, rather than returning None, for data it cannot read
            codec = skia.Codec.MakeFromData(blob)
        except RuntimeError:
            codec = None
        if codec is None:
            print(f"[working] not an image Skia decodes: {path}", file=sys.stderr)
            return None
        info = (
            codec.getInfo()
            .makeColorType(skia.kN32_ColorType)
            .makeAlphaType(skia.kPremul_AlphaType)
        )
        count = max(1, codec.getFrameCount())
        infos = codec.getFrameInfo() if count > 1 else []
        bitmap = skia.Bitmap()
        bitmap.allocPixels(info)
        frames: list[skia.Image] = []
        durations: list[float] = []
        for i in range(count):
            options = skia.Codec.Options()
            options.fFrameIndex = i
            # Frames are decoded in order into one bitmap, so it always holds the
            # frame before: a frame that builds on an earlier one names it as the
            # prior frame, and one that starts afresh starts from a clear canvas.
            if infos and infos[i].fRequiredFrame != -1:
                options.fPriorFrame = i - 1
            else:
                bitmap.eraseARGB(0, 0, 0, 0)
                options.fPriorFrame = -1
            result = codec.getPixels(
                info, bitmap.getPixels(), info.minRowBytes(), options
            )
            if result != skia.Codec.Result.kSuccess:
                print(f"[working] frame {i} of {path}: {result}", file=sys.stderr)
                break
            # A copy: the next frame is decoded into the same bitmap.
            frames.append(skia.Image.MakeRasterCopy(bitmap.pixmap()))
            ms = infos[i].fDuration if infos else 0
            durations.append(ms / 1000 if ms > 0 else _FALLBACK_FRAME_SECONDS)
        if not frames:
            return None
        return cls(frames, durations)

    def frame_at(self, seconds: float) -> skia.Image:
        """The frame showing *seconds* into the loop."""
        position = seconds % self.period if self.period > 0 else 0.0
        for frame, duration in zip(self.frames, self.durations):
            if position < duration:
                return frame
            position -= duration
        return self.frames[-1]

    def draw(
        self, canvas: skia.Canvas, cx: float, cy: float, size: float, seconds: float
    ) -> None:
        """Draw the frame for *seconds*, *size* logical pixels square, centred."""
        canvas.drawImageRect(
            self.frame_at(seconds),
            skia.Rect.MakeXYWH(cx - size / 2, cy - size / 2, size, size),
            skia.SamplingOptions(skia.FilterMode.kLinear),
        )
