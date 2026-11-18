"""
Tests for photos decoded at the size they are drawn.

A photo is held at the size it lands on the device, in halvings of its source,
not at its full size. Pinned here:

  * a photo is held at least twice as large as it is drawn, at the render's
    pixel ratio, and less than four times that — never beyond its source;
  * a draw that needs more than is held is drawn from what is held until the
    next decode, which a one-shot render waits for; a draw that needs less lets
    the next decode shrink it;
  * drawn at its full size, a photo is the same pixels as before;
  * fine detail drawn small averages to its tone rather than aliasing;
  * the crop is measured on the source, so a reduced decode cuts the picture
    where the full one does;
  * a one-shot render returns as soon as the fetches land, and waits no longer
    than its timeout;
  * importing the session loads no HTTP client: a document with no remote
    picture never pays for it.

Run with: uv run python tests/photo_decode_tests.py
"""

import contextlib
import io
import subprocess
import sys
import threading
import time
import unittest
from concurrent.futures import Future
from pathlib import Path

import numpy as np
import skia  # type: ignore[import-untyped]

from md2ui import session
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.render_fills import draw_picture
from md2ui.utils.image_cache import (
    ImageCache,
    Photo,
    _decode_reduced,
    decode_image,
    load_picture,
)

_THEME = Path("data/markdown/tests/THEME.md")
_KIT: list = []
_URL = "https://example.invalid/coat.jpg"
_RED, _BLUE = (220, 30, 30), (30, 30, 220)


def _kit():
    if not _KIT:
        with contextlib.redirect_stdout(io.StringIO()):
            theme = session.load_theme(_THEME)
            _KIT.extend([session.load_grouping_kit(), theme, session.load_fonts(theme)])
    return _KIT


def _jpeg(width: int, height: int) -> bytes:
    """A photo whose left half is red and right half blue."""
    pixels = np.zeros((height, width, 4), dtype=np.uint8)
    pixels[:, : width // 2] = (*_RED, 255)
    pixels[:, width // 2 :] = (*_BLUE, 255)
    image = skia.Image.fromarray(pixels, colorType=skia.kRGBA_8888_ColorType)
    return bytes(image.encodeToData(skia.EncodedImageFormat.kJPEG, 95))


def _render(markdown: str, data: bytes, scale: float):
    """Render *markdown* with *data* landed as ``_URL``; the image, its box and
    the photo as the cache holds it after the paint."""
    kit, theme, fonts = _kit()
    grouped = session.group_markdown(markdown, kit)
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 600.0)
    [box] = [b for b in scene.boxes if index[b.content_id].get("type") == "image"]
    cache = ImageCache()
    photo = load_picture(data)
    assert isinstance(photo, Photo), photo
    cache._cache[_URL], cache._kind[_URL] = photo, "raster"
    image = session.render_image(scene, index, theme, fonts, cache, {}, scale)
    return image, box, photo


def test_a_photo_is_held_at_the_size_it_is_drawn():
    markdown = (
        f"## Coat\n\n![Coat]({_URL}?md2ui.max_width=120&md2ui.aspect_ratio=1:1)\n"
    )
    for scale in (1.0, 2.0):
        _, box, photo = _render(markdown, _jpeg(1600, 800), scale)
        assert photo.image is not None, "the photo was never decoded"
        # A 2:1 photo cover-cropped into a square: its height is what is drawn.
        drawn = 120 * scale
        held = photo.image.height()
        assert 2 * drawn <= held < 4 * drawn, (scale, drawn, held)
        assert photo.image.width() == 2 * held, "the source's ratio is kept"
    print("  ✓  a photo is held at twice its drawn size × the pixel ratio, in halvings")


def _held(photo: Photo) -> int:
    """The width *photo* is held at."""
    assert photo.image is not None, "nothing is held"
    return photo.image.width()


def test_a_held_photo_serves_until_the_next_decode():
    photo = load_picture(_jpeg(1600, 1200))
    assert isinstance(photo, Photo)
    cache = ImageCache()
    cache._cache[_URL] = photo
    assert photo.image_for(0.05) is None, "nothing is held before the first decode"
    assert cache.fit_decodes() and _held(photo) == 200, _held(photo)
    assert photo.image_for(0.05) is photo.image, "a held decode that suffices draws"
    held = photo.image
    assert photo.image_for(0.15) is held, "a smaller decode stands in until the next"
    assert cache.fit_decodes() and _held(photo) == 800, _held(photo)
    assert photo.image_for(1.0) is not None and cache.fit_decodes()
    assert _held(photo) == 1600, "never decoded beyond the source"
    assert photo.image_for(0.025) is photo.image
    assert cache.fit_decodes() and _held(photo) == 100, "a smaller draw shrinks"
    assert not cache.fit_decodes(), "nothing drawn since, nothing to decode"
    assert photo.image_for(0.05) is not None and cache.fit_decodes()
    held = photo.image
    assert photo.image_for(0.025) is held and not cache.fit_decodes(), (
        "a photo held one halving larger than it is drawn is kept"
    )
    assert photo.image_for(0.01) is held and cache.fit_decodes()
    assert _held(photo) == 50, "two halvings larger is shrunk"
    print(
        "  ✓  a held photo serves until the next decode, and shrinks when drawn smaller"
    )


def test_full_size_is_the_source_decode():
    data = _jpeg(320, 200)
    full, same = _decode_reduced(data, 0), decode_image(data)
    assert full is not None and same is not None
    assert full.tobytes() == same.tobytes(), "a full-size draw must not move a pixel"
    print("  ✓  drawn at its full size, a photo is the same pixels as before")


def test_fine_detail_averages_rather_than_aliases():
    """One-pixel stripes drawn at a tenth of their size are their average grey:
    the photo is held larger than it is drawn and drawn down through mipmaps,
    so no stripe survives as a stray line."""
    pixels = np.zeros((640, 640, 4), dtype=np.uint8)
    pixels[:, ::2] = (255, 255, 255, 255)
    pixels[:, 1::2] = (0, 0, 0, 255)
    data = bytes(
        skia.Image.fromarray(pixels, colorType=skia.kRGBA_8888_ColorType).encodeToData(
            skia.EncodedImageFormat.kPNG, 100
        )
    )
    photo = load_picture(data)
    assert isinstance(photo, Photo)
    cache = ImageCache()
    cache._cache[_URL] = photo
    surface = skia.Surface(64, 64)
    src, dst = skia.Rect.MakeWH(640, 640), skia.Rect.MakeWH(64, 64)
    draw_picture(surface.getCanvas(), photo, src, dst)
    assert cache.fit_decodes() and _held(photo) >= 128, "held at least twice drawn"
    draw_picture(surface.getCanvas(), photo, src, dst)
    grey = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    grey = grey[2:-2, 2:-2, 0].astype(int)  # away from the edges
    assert abs(grey.mean() - 128) < 12 and grey.std() < 6, (grey.mean(), grey.std())
    print("  ✓  fine detail drawn small averages to its grey instead of aliasing")


def test_a_reduced_decode_cuts_where_the_full_one_does():
    """Cover-cropped into a square, a 2:1 red|blue photo shows its middle half,
    so the colours meet at the drawn square's centre, whatever size it is held
    at."""
    markdown = (
        f"## Coat\n\n![Coat]({_URL}?md2ui.max_width=120&md2ui.aspect_ratio=1:1)\n"
    )
    image, box, photo = _render(markdown, _jpeg(3200, 1600), 1.0)
    assert photo.level is not None and photo.level >= 2, photo.level
    row = image.toarray(colorType=skia.kRGBA_8888_ColorType)[
        round(box.y + box.height / 2)
    ][:, :3].astype(int)
    red = [x for x in range(len(row)) if abs(row[x] - _RED).sum() < 40]
    blue = [x for x in range(len(row)) if abs(row[x] - _BLUE).sum() < 40]
    assert red and blue, (red, blue)
    left, right = min(red), max(blue) + 1
    assert abs((right - left) - 120) <= 2, (left, right)
    seam = (max(red) + 1 + min(blue)) / 2
    assert abs(seam - (left + right) / 2) <= 1.5, (seam, left, right)
    print("  ✓  a reduced decode cuts the picture where the full one does")


def test_waiting_for_pictures_ends_when_they_land():
    cache = ImageCache()
    landed: Future[None] = Future()
    cache._futures = [landed]

    def land() -> None:
        time.sleep(0.2)
        landed.set_result(None)

    threading.Thread(target=land, daemon=True).start()
    start = time.perf_counter()
    cache.wait(10.0)
    assert landed.done(), "it returned before the picture landed"
    assert time.perf_counter() - start < 5.0, "it waited past the landing"
    cache._futures = [Future()]
    start = time.perf_counter()
    cache.wait(0.1)
    assert time.perf_counter() - start < 5.0, "it ignored its timeout"
    print("  ✓  a one-shot render waits until the pictures land, within its timeout")


def test_importing_the_session_loads_no_http_client():
    loaded = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, md2ui.session; print('urllib.request' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert loaded == "False", loaded
    print("  ✓  importing the session loads no HTTP client")


_GL_SURFACE_AFTER_A_PHOTO = """
import glfw, skia
from md2ui.pipeline.layout_render import make_surface
from md2ui.utils.image_cache import load_picture
if not glfw.init():
    raise SystemExit("SKIP")
glfw.window_hint(glfw.VISIBLE, False)
glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 2)
glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)
glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
window = glfw.create_window(64, 64, "t", None, None)
if not window:  # a failed create is a NULL pointer, never None
    raise SystemExit("SKIP")
glfw.make_context_current(window)
context = skia.GrDirectContext.MakeGL()
if context is None:
    raise SystemExit("SKIP")
srgb = skia.ImageInfo.MakeN32Premul(16, 16, skia.ColorSpace.MakeSRGB())
jpeg = bytes(skia.Surface.MakeRaster(srgb).makeImageSnapshot().encodeToData(skia.kJPEG, 90))
del srgb  # no shared sRGB held anywhere, as in the window when a photo lands
held = load_picture(jpeg)
assert held is not None and held.space is not None
make_surface(context, 64, 64)
print("OK")
"""


def test_a_held_photo_leaves_the_window_able_to_resize():
    """A photo that kept the sRGB colour space borrowed (``colorSpace()``) makes
    pybind refuse the shared one ``make_surface`` asks for, crashing a resize.
    Needs a GL context, so it runs in a child."""
    run = _run_gl_probe("")
    if _skipped(run):
        raise unittest.SkipTest(
            "no GL context here; the resize surface was not checked"
        )
    assert run.stdout.strip() == "OK", run.stderr[-400:]
    print("  ✓  a held photo leaves the window able to make its surface on resize")


def _run_gl_probe(prelude: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", prelude + _GL_SURFACE_AFTER_A_PHOTO],
        capture_output=True,
        text=True,
    )


def _skipped(run: subprocess.CompletedProcess[str]) -> bool:
    """The child says SKIP as its last word: GLFW's own warnings come before it."""
    lines = run.stderr.strip().splitlines()
    return run.returncode != 0 and bool(lines) and lines[-1] == "SKIP"


def test_a_host_that_cannot_make_the_window_skips_the_probe():
    """A runner with no usable pixel format gets a NULL window, not None: the
    probe must say SKIP instead of going on to a surface it cannot make."""
    null_window = (
        "import ctypes, glfw\n"
        "glfw.create_window = lambda *a: ctypes.POINTER(glfw._GLFWwindow)()\n"
    )
    run = _run_gl_probe(null_window)
    assert _skipped(run), run.stderr[-400:]
    print("  ✓  a host that cannot make the probe's window skips it")


TESTS = [
    test_a_held_photo_leaves_the_window_able_to_resize,
    test_a_host_that_cannot_make_the_window_skips_the_probe,
    test_a_photo_is_held_at_the_size_it_is_drawn,
    test_a_held_photo_serves_until_the_next_decode,
    test_full_size_is_the_source_decode,
    test_fine_detail_averages_rather_than_aliases,
    test_a_reduced_decode_cuts_where_the_full_one_does,
    test_waiting_for_pictures_ends_when_they_land,
    test_importing_the_session_loads_no_http_client,
]

if __name__ == "__main__":
    print("Photo Decode Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
