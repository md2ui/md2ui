"""PNG bytes for a rendered page, written fast enough to serve.

Skia's own encoder dominates a warm server render and skia-python passes no
compression level through to it. This one filters every row "up", deflates fast, and
compresses bands of rows on threads (zlib releases
the GIL). The bands are cut by the page's size alone, never by
the machine or by which thread finishes first, so the same pixels always give
the same bytes and a byte comparison of two renders still means something.

The pixels are those Skia's encoder stored: unpremultiplied RGBA, or RGB when
every pixel is opaque. The files are a few percent larger.
"""

from __future__ import annotations

import os
import struct
import zlib
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import skia

# zlib level 1 over 2 and 3: higher levels shrink files only slightly and take
# markedly longer. The bytes only go to a local file or a local pipe, so the
# time is what counts.
_LEVEL = 1
# Rows per compressed band: about 1 MiB of filtered rows, so an ordinary page is
# a few bands and gains from the threads too, and a huge page is held as its pixels
# plus the bands in flight. Cutting finer costs nothing measurable in size.
_BAND_BYTES = 1 << 20
_POOL = ThreadPoolExecutor(min(8, os.cpu_count() or 1), thread_name_prefix="png")


def encode_png(image: skia.Image) -> bytes | None:
    """*image* as PNG bytes; None when Skia cannot read its pixels."""
    if image.isTextureBacked():
        image = image.makeRasterImage()
        if image is None:
            return None
    try:
        pixels = image.toarray(
            colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType
        )
    except (RuntimeError, ValueError):
        return None
    height, width, _ = pixels.shape
    opaque = int(pixels[:, :, 3].min()) == 255
    channels = 3 if opaque else 4
    rows = max(1, _BAND_BYTES // (width * channels + 1))
    bands = [(top, min(height, top + rows)) for top in range(0, height, rows)]
    last = len(bands) - 1
    parts = _POOL.map(
        lambda i: _band(pixels, channels, bands[i][0], bands[i][1], i == last),
        range(len(bands)),
    )
    stream = [b"\x78\x01"]  # a zlib header: deflate, 32 KiB window
    checksum = 1
    for deflated, adler, length in parts:
        stream.append(deflated)
        checksum = _adler32_combine(checksum, adler, length)
    stream.append(struct.pack(">I", checksum))
    header = struct.pack(">IIBBBBB", width, height, 8, 2 if opaque else 6, 0, 0, 0)
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            *_chunk(b"IHDR", [header]),
            *_chunk(b"IDAT", stream),
            *_chunk(b"IEND", []),
        )
    )


def _band(
    pixels: np.ndarray, channels: int, top: int, bottom: int, last: bool
) -> tuple[bytes, int, int]:
    """Rows ``top:bottom`` filtered "up" and deflated as one piece of the
    stream, with the Adler-32 and length of what was deflated."""
    width = pixels.shape[1]
    raw = np.empty((bottom - top, width * channels + 1), np.uint8)
    raw[:, 0] = 2  # filter type "up": each byte minus the one above it
    out = raw[:, 1:].reshape(bottom - top, width, channels)
    here = pixels[top:bottom, :, :channels]
    if top == 0:
        out[0] = here[0]  # the first row has nothing above it
        np.subtract(here[1:], pixels[: bottom - 1, :, :channels], out=out[1:])
    else:
        np.subtract(here, pixels[top - 1 : bottom - 1, :, :channels], out=out)
    deflate = zlib.compressobj(_LEVEL, zlib.DEFLATED, -15)
    data = raw.data
    # A sync flush ends a band on a byte boundary, so the next band's raw
    # deflate continues the one stream.
    deflated = deflate.compress(data)
    deflated += deflate.flush(zlib.Z_FINISH if last else zlib.Z_SYNC_FLUSH)
    return deflated, zlib.adler32(data), raw.nbytes


def _adler32_combine(first: int, second: int, second_length: int) -> int:
    """The Adler-32 of two byte strings joined, from the checksum of each
    (zlib's ``adler32_combine``, which Python does not expose)."""
    base = 65521
    remainder = second_length % base
    low = (first & 0xFFFF) + (second & 0xFFFF) + base - 1
    high = (remainder * (first & 0xFFFF)) % base
    high += (first >> 16) + (second >> 16) + base - remainder
    return (low % base) | ((high % base) << 16)


def _chunk(kind: bytes, data: list[bytes]) -> list[bytes]:
    """One chunk as its pieces, so a large IDAT is joined only once."""
    crc = zlib.crc32(kind)
    for piece in data:
        crc = zlib.crc32(piece, crc)
    length = sum(len(piece) for piece in data)
    return [struct.pack(">I", length), kind, *data, struct.pack(">I", crc)]
