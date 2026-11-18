"""
Unit tests for the PNG writer (``utils/png``) every md2ui PNG goes through.

It stands in for Skia's encoder, for speed, so it must write what Skia writes:

  * the file decodes, with Skia and with a decoder written here from the PNG
    specification, to exactly the pixels Skia's own file decodes to;
  * a translucent, antialiased edge stores the same unpremultiplied colour
    Skia's encoder stores, not a rounding of it;
  * a page tall enough to be compressed in several bands is still one valid
    stream;
  * the same pixels always give the same bytes, so a byte comparison of two
    renders (scripts/render_snapshot.py) still means something.

Run with: uv run python tests/png_encode_tests.py
"""

import struct
import zlib

import numpy as np
import skia

from md2ui.utils import png


def _circles(width: int, height: int, background: int) -> skia.Image:
    """Antialiased circles of every alpha, some overlapping, on *background*."""
    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    canvas.clear(background)
    paint = skia.Paint(AntiAlias=True)
    for i in range(256):
        paint.setColor(
            skia.Color4f(
                (i * 37 % 256) / 255,
                (i * 91 % 256) / 255,
                (i * 13 % 256) / 255,
                i / 255,
            )
        )
        canvas.drawCircle(i * 7 % width, i * 11 % height, 9.5, paint)
    return surface.makeImageSnapshot()


def _encoded(image: skia.Image) -> bytes:
    data = png.encode_png(image)
    assert data is not None
    return data


def _stored(data: bytes) -> np.ndarray:
    """The pixels a PNG stores, read from the specification rather than by a
    library: the IDAT chunks inflated and each row's "up" filter undone. The
    writer filters every row "up", which this also checks."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    at, idat, header = 8, b"", None
    while at < len(data):
        (length,) = struct.unpack(">I", data[at : at + 4])
        kind, body = data[at + 4 : at + 8], data[at + 8 : at + 8 + length]
        (crc,) = struct.unpack(">I", data[at + 8 + length : at + 12 + length])
        assert crc == zlib.crc32(kind + body), kind
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        at += 12 + length
    assert header is not None
    width, height, depth, color, *_ = header
    assert depth == 8 and color in (2, 6)
    channels = 3 if color == 2 else 4
    rows = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(height, -1)
    assert (rows[:, 0] == 2).all()
    pixels = np.cumsum(rows[:, 1:], axis=0, dtype=np.uint8)  # undo "up", mod 256
    return pixels.reshape(height, width, channels)


def _decoded(data: bytes) -> np.ndarray:
    image = skia.Image.MakeFromEncoded(skia.Data.MakeWithCopy(data))
    assert image is not None
    return image.toarray(colorType=skia.kRGBA_8888_ColorType)


def test_a_translucent_edge_stores_what_skia_stored():
    """Unpremultiplied exactly as Skia's encoder does, on every alpha."""
    image = _circles(300, 200, skia.ColorTRANSPARENT)
    ours, skias = _encoded(image), bytes(image.encodeToData())
    stored = _stored(ours)
    assert stored.shape[2] == 4, "a translucent page keeps its alpha"
    expected = image.toarray(
        colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType
    )
    edge = (expected[..., 3] > 0) & (expected[..., 3] < 255)
    assert edge.sum() > 10_000, "the sample has antialiased edges to compare"
    assert (stored == expected).all()
    assert (_decoded(ours) == _decoded(skias)).all()
    print("  ✓  a translucent edge stores what Skia's encoder stored")


def test_an_opaque_page_in_several_bands_decodes_to_skias_pixels():
    """Taller than one band, so the stream is joined from several pieces."""
    image = _circles(640, 8000, skia.ColorWHITE)
    assert 640 * 3 * 8000 > png._BAND_BYTES * 2
    ours = _encoded(image)
    stored = _stored(ours)
    assert stored.shape[2] == 3, "an opaque page is written without alpha"
    expected = image.toarray(colorType=skia.kRGBA_8888_ColorType)
    assert (stored == expected[..., :3]).all()
    assert (_decoded(ours) == _decoded(bytes(image.encodeToData()))).all()
    print("  ✓  an opaque page in several bands decodes to Skia's pixels")


def test_the_same_pixels_give_the_same_bytes():
    """Bands finish in any order on the threads; the file does not change."""
    image = _circles(640, 8000, skia.ColorWHITE)
    first = _encoded(image)
    assert all(_encoded(image) == first for _ in range(5))
    copy = skia.Image.MakeFromEncoded(skia.Data.MakeWithCopy(first))
    assert _encoded(copy.makeRasterImage()) == first
    print("  ✓  the same pixels give the same bytes")


def test_a_one_pixel_page_is_a_png():
    surface = skia.Surface(1, 1)
    surface.getCanvas().clear(0x80FF0000)
    image = surface.makeImageSnapshot()
    assert (_decoded(_encoded(image)) == _decoded(bytes(image.encodeToData()))).all()
    print("  ✓  a one-pixel page is a PNG")


TESTS = [
    test_a_translucent_edge_stores_what_skia_stored,
    test_an_opaque_page_in_several_bands_decodes_to_skias_pixels,
    test_the_same_pixels_give_the_same_bytes,
    test_a_one_pixel_page_is_a_png,
]


if __name__ == "__main__":
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ✗  {test.__name__}: {exc!r}")
    if failed:
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
