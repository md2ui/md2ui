"""photo_decoder.py — photos decoded in child processes, so the window never waits.

skia-python holds the GIL through a whole decode, and a progressive JPEG decodes
its entire file in one call however small the result (``startScanlineDecode``
does the work before the first scanline is out, so a decode cannot be cut into
short pieces either). A decode on a thread therefore freezes the window as
surely as one on the window's own thread. A child process has its own GIL. The window
only writes the encoded bytes to a pipe and reads the pixels back, and both wait
outside its GIL.

The children start with the first decode asked of them, so a shell that never
decodes in the background never starts one. A child exits when its stdin closes,
which is also what the operating system does to the pipe when the window dies
by any means, so no decoder outlives its window.
"""

import io
import os
import queue
import signal
import struct
import subprocess
import sys
import threading
from collections.abc import Callable
from typing import BinaryIO, cast

import skia  # type: ignore[import-untyped]

# A request: the level, the encoded length; then the encoded bytes.
_REQUEST = struct.Struct("<IQ")
# A reply: width and height (0 × 0 when the photo could not be decoded), colour
# type, alpha type; then the pixels, rows packed. The colour space is the one the
# photo's header declares, which the window already holds.
_REPLY = struct.Struct("<IIII")

# Seconds a child waits for another request before it ends.
_IDLE = 5.0

Deliver = Callable[[object, int, "skia.Image | None"], None]
"""Called with a request's key, its level and the decode (None when it failed)."""


def _read_into(stream: io.BufferedReader, buffer) -> bool:
    """Fill *buffer* from *stream*; False when the stream ended first."""
    view = memoryview(buffer).cast("B")
    got = 0
    while got < len(view):
        n = stream.readinto(view[got:])
        if not n:
            return False
        got += n
    return True


def serve() -> None:
    """A child's loop: decode each request and reply with its pixels, until
    stdin ends."""
    # The protocol owns stdout; anything printed goes to stderr instead.
    out = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    # Ctrl-C in the window's terminal is the window's to handle; the child
    # leaves when the window closes its pipe.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        _serve(open(0, "rb", closefd=False), out)
    except BrokenPipeError:
        pass  # the window left while a decode was under way


def _serve(stdin: io.BufferedReader, out: BinaryIO) -> None:
    """Answer the requests on *stdin* on *out*."""
    from md2ui.utils.image_cache import _decode_reduced

    header = bytearray(_REQUEST.size)
    while _read_into(stdin, header):
        level, length = _REQUEST.unpack(header)
        data = bytearray(length)
        if not _read_into(stdin, data):
            return
        image = _decode_reduced(bytes(data), level)
        if image is None:
            out.write(_REPLY.pack(0, 0, 0, 0))
        else:
            info = image.imageInfo()
            pixels = bytearray(info.computeMinByteSize())
            image.readPixels(info, pixels, info.minRowBytes())
            out.write(
                _REPLY.pack(
                    info.width(),
                    info.height(),
                    int(info.colorType()),
                    int(info.alphaType()),
                )
            )
            out.write(pixels)
        out.flush()


def _receive(
    stream: io.BufferedReader, space: "skia.ColorSpace | None"
) -> "tuple[bool, skia.Image | None]":
    """Read one reply: whether the stream still holds one, and its image.

    The pixels are read straight into a bitmap skia owns, and the image shares
    them: a buffer Python owns would be freed under an image that outlives it.
    """
    header = bytearray(_REPLY.size)
    if not _read_into(stream, header):
        return False, None
    width, height, color_type, alpha_type = _REPLY.unpack(header)
    if not width or not height:
        return True, None
    bitmap = skia.Bitmap()
    bitmap.allocPixels(
        skia.ImageInfo.Make(
            width, height, skia.ColorType(color_type), skia.AlphaType(alpha_type), space
        )
    )
    if not _read_into(stream, bitmap):
        return False, None
    bitmap.setImmutable()
    return True, skia.Image.MakeFromBitmap(bitmap)


class _Child:
    """One decoder process, and the thread that hands it one request at a time.

    The thread starts the process when a request comes, not the window's thread,
    and ends it once no request has come for ``_IDLE`` seconds: a decode leaves
    its working memory with the process, and an ended process gives it all back.
    """

    def __init__(self, jobs: "queue.Queue[tuple | None]", deliver: Deliver) -> None:
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()
        self._closed = False
        self._jobs = jobs
        self._deliver = deliver
        threading.Thread(target=self._run, daemon=True).start()

    def _start(self) -> "subprocess.Popen[bytes] | None":
        with self._lock:
            if self._process is None and not self._closed:
                self._process = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        "from md2ui.utils.photo_decoder import serve; serve()",
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                )
            return self._process

    def _run(self) -> None:
        while True:
            try:
                job = self._jobs.get(timeout=_IDLE)
            except queue.Empty:
                self._end()
                continue
            if job is None:
                return
            key, data, level, space = job
            process = self._start()
            image = None
            if process is not None:
                assert process.stdin is not None and process.stdout is not None
                try:
                    process.stdin.write(_REQUEST.pack(level, len(data)))
                    process.stdin.write(data)
                    process.stdin.flush()
                    # A pipe Popen opened for reading is a buffered reader.
                    stdout = cast(io.BufferedReader, process.stdout)
                    alive, image = _receive(stdout, space)
                except (OSError, ValueError):  # ValueError: closed meanwhile
                    alive = False
                if not alive:
                    # It died: this photo has failed; the next request starts
                    # another.
                    self._end()
            self._deliver(key, level, image)

    def _end(self, timeout: float = 1.0) -> None:
        """Close the process's stdin, which ends it; kill it if it lingers."""
        with self._lock:
            process, self._process = self._process, None
        if process is None:
            return
        assert process.stdin is not None
        try:
            process.stdin.close()
            process.wait(timeout)
        except OSError:
            pass
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def close(self) -> None:
        """End the process for good."""
        with self._lock:
            self._closed = True
        self._end()


class PhotoDecoder:
    """A small pool of decoder processes, started with the first request.

    :meth:`decode` returns at once; *deliver* is called later, from a pool
    thread, with the request's key, its level and the image.
    """

    def __init__(self, deliver: Deliver, processes: int = 2) -> None:
        self._deliver = deliver
        self._processes = processes
        self._jobs: "queue.Queue[tuple | None]" = queue.Queue()
        self._children: list[_Child] = []

    def decode(
        self, key: object, data: bytes, level: int, space: "skia.ColorSpace | None"
    ) -> None:
        """Queue *data*'s decode at *level*; *space* is its header's colour space."""
        if not self._children:
            self._children = [
                _Child(self._jobs, self._deliver) for _ in range(self._processes)
            ]
        self._jobs.put((key, data, level, space))

    def close(self) -> None:
        """End every child, waiting a moment for each before killing it."""
        for child in self._children:
            self._jobs.put(None)
            child.close()
        self._children = []
