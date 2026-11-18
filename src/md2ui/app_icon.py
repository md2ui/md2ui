"""The window's icon: md2ui's own, not the Python interpreter's.

`assets/app/icon.png` (1024 x 1024, shipped inside the package) is the one
picture. Where it goes depends on the platform:

* Windows and X11 take it per window, through GLFW, at a few sizes so the
  system picks a sharp one for the title bar, the taskbar and the switcher;
* macOS ignores a window icon: the Dock shows the application's, which a
  Python process only has once it is set through AppKit. A macOS icon leaves
  a transparent margin around its body (Apple's grid: an 824 px body on a
  1024 px canvas), so the picture is drawn at that size; full bleed, it would
  stand larger than every icon beside it in the Dock and the switcher.

The Dock still NAMES the process "Python": that comes from the interpreter's
bundle, not from anything a running process can set.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import glfw
import numpy as np
import skia

from md2ui import session

ICON = session.resource_root() / "assets" / "app" / "icon.png"
SIZES = (16, 32, 48, 256)
DOCK_CANVAS, DOCK_BODY = 1024, 824


def icon_images(path: Path = ICON) -> list[tuple[int, int, np.ndarray]]:
    """The icon at each of :data:`SIZES`, as GLFW takes it: ``(width, height,
    pixels)`` with the pixels unpremultiplied RGBA, one row per index."""
    image = skia.Image.MakeFromEncoded(skia.Data.MakeFromFileName(str(path)))
    sampling = skia.SamplingOptions(skia.CubicResampler.Mitchell())
    return [
        (
            size,
            size,
            image.resize(size, size, sampling).toarray(
                colorType=skia.kRGBA_8888_ColorType,
                alphaType=skia.kUnpremul_AlphaType,
            ),
        )
        for size in SIZES
    ]


def dock_image(path: Path = ICON) -> skia.Image:
    """The icon on macOS's grid: the picture at :data:`DOCK_BODY`, centred on a
    transparent :data:`DOCK_CANVAS` square."""
    image = skia.Image.MakeFromEncoded(skia.Data.MakeFromFileName(str(path)))
    surface = skia.Surface(DOCK_CANVAS, DOCK_CANVAS)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    inset = (DOCK_CANVAS - DOCK_BODY) / 2
    canvas.drawImageRect(
        image,
        skia.Rect.MakeXYWH(inset, inset, DOCK_BODY, DOCK_BODY),
        skia.SamplingOptions(skia.CubicResampler.Mitchell()),
    )
    return surface.makeImageSnapshot()


def set_icon(window: object) -> None:
    """Show md2ui's icon for *window*: the Dock's on macOS, the window's elsewhere.

    Call it after ``glfw.init()``, which creates the application the Dock shows.
    A missing icon file leaves the platform's default, as before.
    """
    if not ICON.is_file():
        print(f"[icon] not found: {ICON}")
        return
    if sys.platform == "darwin":
        # PyObjC's classes are made at run time, so no checker sees them; it is
        # a darwin-only dependency, imported only here.
        appkit = importlib.import_module("AppKit")
        png = bytes(dock_image().encodeToData())
        data = appkit.NSData.dataWithBytes_length_(png, len(png))
        image = appkit.NSImage.alloc().initWithData_(data)
        appkit.NSApplication.sharedApplication().setApplicationIconImage_(image)
    else:
        images = icon_images()
        glfw.set_window_icon(window, len(images), images)
