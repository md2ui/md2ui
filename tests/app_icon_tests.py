"""
Unit tests for ``md2ui.app_icon``, the window's icon.

What a window or the Dock shows needs a display; what can be checked headlessly
is the picture handed to them:

  * the icon is read from where the files md2ui runs with live
    (``session.resource_root``: the checkout, or ``md2ui/shipped/`` installed),
    and is the square 1024 px source;
  * GLFW is handed it at each of 16, 32, 48 and 256 px, as unpremultiplied RGBA
    rows, the shape ``glfw.set_window_icon`` reads;
  * the Dock gets it on macOS's grid: an 824 px body centred on a transparent
    1024 px canvas, so it stands as large as the icons beside it.

Run with: uv run python tests/app_icon_tests.py
"""

import skia

from md2ui import session
from md2ui.app_icon import DOCK_BODY, DOCK_CANVAS, ICON, SIZES, dock_image, icon_images


def test_the_icon_is_read_from_the_runtime_files():
    assert ICON == session.resource_root() / "assets" / "app" / "icon.png"
    image = skia.Image.MakeFromEncoded(skia.Data.MakeFromFileName(str(ICON)))
    assert image is not None, f"{ICON} does not decode"
    assert (image.width(), image.height()) == (1024, 1024)
    print("  ✓  the icon is the square source among the runtime files")


def test_glfw_gets_the_icon_at_each_size():
    images = icon_images()
    assert SIZES == (16, 32, 48, 256)
    assert [(w, h) for w, h, _ in images] == [(s, s) for s in SIZES]
    for size, _, pixels in images:
        assert pixels.shape == (size, size, 4) and pixels.dtype.name == "uint8"
        assert pixels[size // 2, size // 2, 3] == 255, "the centre is opaque"
    print("  ✓  GLFW gets the icon at 16, 32, 48 and 256 px, RGBA rows")


def test_the_dock_gets_it_with_macos_margin():
    pixels = dock_image().toarray(colorType=skia.kRGBA_8888_ColorType)
    assert pixels.shape == (DOCK_CANVAS, DOCK_CANVAS, 4)
    inset = (DOCK_CANVAS - DOCK_BODY) // 2
    margin = [
        pixels[: inset - 1],
        pixels[-inset + 1 :],
        pixels[:, : inset - 1],
        pixels[:, -inset + 1 :],
    ]
    assert all(band[..., 3].max() == 0 for band in margin), (
        "the margin is not transparent"
    )
    assert pixels[DOCK_CANVAS // 2, DOCK_CANVAS // 2, 3] == 255, "the body is drawn"
    rows = (pixels[..., 3] > 0).any(axis=1).nonzero()[0]
    assert rows.min() >= inset - 1 and rows.max() <= DOCK_CANVAS - inset, (
        rows.min(),
        rows.max(),
    )
    print(
        f"  ✓  the Dock gets an {DOCK_BODY} px body on a transparent {DOCK_CANVAS} px canvas"
    )


TESTS = [
    test_the_icon_is_read_from_the_runtime_files,
    test_glfw_gets_the_icon_at_each_size,
    test_the_dock_gets_it_with_macos_margin,
]

if __name__ == "__main__":
    print("App Icon Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
