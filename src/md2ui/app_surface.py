"""The window's GL surface, kept the size of the framebuffer it draws into.

The Skia surface wraps the window's framebuffer at a fixed size in device pixels,
while each frame scales its drawing by the device pixel ratio read fresh. Moved to
a display of another scale, the window's framebuffer changes size; drawn through a
surface of the old size, the page comes out at double size.

GLFW reports that move as a framebuffer resize, a content-scale change or both, in
an order that is the platform's, so the frame does not trust either: before
drawing, it compares the surface with the framebuffer and rebuilds on a mismatch.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from typing import Protocol, TypeVar


class Sized(Protocol):
    def width(self) -> int: ...
    def height(self) -> int: ...


S = TypeVar("S", bound=Sized)


def fitted(surface: S, fb_w: int, fb_h: int, make: Callable[[int, int], S]) -> S:
    """*surface* while it is *fb_w* x *fb_h* device pixels, else one ``make`` builds
    at that size."""
    if (surface.width(), surface.height()) == (fb_w, fb_h):
        return surface
    return make(fb_w, fb_h)


def follow_backing() -> None:
    """On macOS, have the current GL context take its view's new size and backing
    scale. Cocoa asks for this when a view's drawable changes; GLFW makes the call
    when the window moves or resizes, and whether that always covers a change of
    display is not established, so a scale change makes it too."""
    if sys.platform != "darwin":
        return
    try:
        context = importlib.import_module("AppKit").NSOpenGLContext.currentContext()
    except ImportError:  # no PyObjC: GLFW's own updates are all there is
        return
    if context is not None:
        context.update()
