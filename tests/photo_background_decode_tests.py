"""
Tests for photos decoded off the window's thread.

skia-python holds the GIL through a decode, so a decode on a thread would freeze
the window too. The window's photos are decoded in child processes
(``photo_decoder``) and land like a fetch. Pinned here:

  * a background decode is the same pixels, colour type, alpha and colour space
    as the one-shot render's own decode;
  * in the background, ``fit_decodes`` queues and returns at once; the decode
    lands through ``drain_pending``, one per photo in flight;
  * until a photo's first decode lands, the box shows what it showed while the
    photo was fetched: the loading placeholder, or a card's theme picture;
  * a one-shot render starts no decoder process;
  * a child ends when its pipe closes, and with its window however that ends.

Run with: uv run python tests/photo_background_decode_tests.py
"""

import subprocess
import sys
import textwrap
import time
import unittest

import numpy as np
import skia  # type: ignore[import-untyped]

from md2ui.pipeline.render_fills import draw_picture
from md2ui.pipeline.render_placeholders import card_photo
from md2ui.pipeline.render_settings import VIEW
from md2ui.utils.image_cache import (
    ImageCache,
    Loading,
    Photo,
    _decode_reduced,
    load_picture,
)

_URL = "https://example.invalid/coat.jpg"


def _jpeg(width: int, height: int) -> bytes:
    """A photo with detail in it: a gradient under a noise."""
    rng = np.random.default_rng(7)
    pixels = rng.integers(0, 255, (height, width, 4), dtype=np.uint8)
    pixels[:, :, 0] = np.linspace(0, 255, width, dtype=np.uint8)
    pixels[:, :, 3] = 255
    image = skia.Image.fromarray(pixels, colorType=skia.kRGBA_8888_ColorType)
    return bytes(image.encodeToData(skia.EncodedImageFormat.kJPEG, 90))


def _cache_with_photo(background: bool) -> tuple[ImageCache, Photo]:
    cache = ImageCache(background=background)
    photo = load_picture(_jpeg(640, 480))
    assert isinstance(photo, Photo)
    cache._cache[_URL], cache._kind[_URL] = photo, "raster"
    return cache, photo


def _landed(cache: ImageCache, timeout: float = 30.0) -> bool:
    """Drain until a decode lands; True when one did."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cache.drain_pending(None):
            return True
        time.sleep(0.01)
    return False


def test_a_background_decode_is_the_same_picture():
    cache, photo = _cache_with_photo(background=True)
    try:
        photo.image_for(0.15)
        assert not cache.fit_decodes(), "the background answers later, not now"
        assert photo.decoding == 1 and photo.image is None
        photo.image_for(0.15)
        cache.fit_decodes()  # in flight already: not asked twice
        assert _landed(cache), "the decode never landed"
        assert photo.decoding is None and photo.level == 1
        own = _decode_reduced(photo.data, 1)
        assert own is not None and photo.image is not None
        assert photo.image.imageInfo() == own.imageInfo()
        assert bytes(photo.image.tobytes()) == bytes(own.tobytes())
        assert not cache.has_pending()
    finally:
        cache.close()
    print("  ✓  a background decode is the one-shot render's picture, byte for byte")


def test_a_photo_not_yet_decoded_shows_what_its_box_showed():
    VIEW.placeholder_raster = skia.Image.fromarray(
        np.full((10, 10, 4), (0, 200, 0, 255), dtype=np.uint8),
        colorType=skia.kRGBA_8888_ColorType,
    )
    cache, photo = _cache_with_photo(background=True)
    try:
        theme_picture = skia.Image.fromarray(
            np.full((4, 4, 4), (0, 0, 200, 255), dtype=np.uint8),
            colorType=skia.kRGBA_8888_ColorType,
        )
        shown = card_photo(cache, _URL, theme_picture)
        assert isinstance(shown, Loading) and shown.standin is theme_picture
        surface = skia.Surface(64, 48)
        src = skia.Rect.MakeWH(photo.width(), photo.height())
        draw_picture(surface.getCanvas(), shown, src, skia.Rect.MakeWH(64, 48))
        pixel = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
        assert tuple(pixel[24, 32][:3]) == (0, 0, 200), pixel[24, 32]
        assert photo.wanted is not None, "the draw still asked for its size"
        assert not isinstance(card_photo(cache, _URL, None), Photo)
    finally:
        VIEW.placeholder_raster = None
        cache.close()
    print("  ✓  until its first decode lands, a photo's box shows its stand-in")


def test_a_one_shot_render_starts_no_decoder():
    cache, photo = _cache_with_photo(background=False)
    photo.image_for(0.3)
    assert cache.fit_decodes() and photo.image is not None
    assert cache._decoder is None
    print("  ✓  a one-shot render decodes in process and starts no decoder")


_PARENT = textwrap.dedent(
    """
    import os, signal, sys, time
    import skia, numpy as np
    from md2ui.utils.photo_decoder import PhotoDecoder
    pixels = np.random.default_rng(1).integers(0, 255, (3000, 3000, 4), dtype=np.uint8)
    data = bytes(skia.Image.fromarray(pixels).encodeToData(skia.EncodedImageFormat.kJPEG, 95))
    decoder = PhotoDecoder(lambda *a: None)
    for i in range(6):
        decoder.decode(i, data, 0, None)
    while not all(c._process for c in decoder._children):
        time.sleep(0.01)
    print(" ".join(str(c._process.pid) for c in decoder._children), flush=True)
    how = sys.argv[1]
    if how == "close":
        decoder.close()
    elif how == "sigterm":
        os.kill(os.getpid(), signal.SIGTERM)
    elif how == "sigkill":
        os.kill(os.getpid(), signal.SIGKILL)
    """
)


def _alive(pid: int) -> bool:
    # The parent has gone, so a child that ended is reaped by init.
    return subprocess.run(["kill", "-0", str(pid)], capture_output=True).returncode == 0


def test_decoders_end_with_their_window():
    if sys.platform == "win32":
        raise unittest.SkipTest("kills its parent with POSIX signals; asks `kill -0`")
    for how in ("close", "exit", "sigterm", "sigkill"):
        run = subprocess.run(
            [sys.executable, "-c", _PARENT, how], capture_output=True, text=True
        )
        pids = [int(p) for p in run.stdout.split()]
        assert len(pids) == 2, (how, run.stdout, run.stderr[-500:])
        end = time.monotonic() + 15
        while any(_alive(p) for p in pids) and time.monotonic() < end:
            time.sleep(0.1)
        assert not any(_alive(p) for p in pids), f"a decoder outlived {how}"
    print("  ✓  decoders end when the window closes, exits, or is killed")


TESTS = [
    test_a_background_decode_is_the_same_picture,
    test_a_photo_not_yet_decoded_shows_what_its_box_showed,
    test_a_one_shot_render_starts_no_decoder,
    test_decoders_end_with_their_window,
]

if __name__ == "__main__":
    print("Photo Background Decode Tests")
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
