"""image_cache.py — Markdown image URL parsing, fetching, and GPU upload.

A photograph is decoded at the size it is drawn, not at the size it was sent:
full-size camera photos shown as thumbnails would hold far more memory than
their drawn size needs. See :class:`Photo`.

The window decodes them in child processes (:mod:`photo_decoder`) and draws
what it holds meanwhile; a one-shot render decodes them before it paints.
"""

import hashlib
import importlib.metadata
import math
import queue
import re
import time
from urllib.parse import urlsplit

from md2ui.utils.fetch_policy import POLICY
from md2ui.utils.image_params import clean_image_url, image_url
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from pathlib import Path

import diskcache  # type: ignore[import-untyped]
import numpy as np
import skia  # type: ignore[import-untyped]

_CACHE_DIR = Path.home() / ".cache" / "md2ui" / "images"
_CACHE_SIZE_LIMIT = 500 * 1024 * 1024  # 500 MB

# Where a host that wants to reach whoever runs md2ui should look. pyproject.toml
# names no project URL yet; this placeholder (a reserved, unroutable domain, so
# it points at no one else's project) stands in until it does.
_PROJECT_URL = "https://md2ui.invalid"


def _version() -> str:
    try:
        return importlib.metadata.version("md2ui")
    except importlib.metadata.PackageNotFoundError:
        return "0"


# Image hosts ask clients to name themselves (Wikimedia's policy does): a burst
# from an anonymous browser-like agent is answered 429, the same burst from a
# client that says what it is gets its pictures.
_USER_AGENT = f"md2ui/{_version()} (+{_PROJECT_URL}; image preview)"

# A 429 is retried once, after the host's Retry-After, but never waits longer
# than the cap: a picture is not worth holding a first open for. A missing or
# unreadable Retry-After (an HTTP-date included) waits the short default.
_RETRY_AFTER_CAP = 5.0
_RETRY_AFTER_DEFAULT = 1.0

# Target max dimension when rasterizing a vector (SVG) image. Upscaling a vector
# is lossless, so render large enough to stay crisp through draw_image_box's
# cover-fit downscale, but capped to keep the raster surface modest.
_SVG_RENDER_MAX = 512

_VIEWBOX_RE = re.compile(
    rb'viewBox\s*=\s*["\']\s*[\d.eE+-]+\s+[\d.eE+-]+\s+([\d.eE+-]+)\s+([\d.eE+-]+)'
)


def _trim_to_ink(img: skia.Image) -> skia.Image:
    """Crop *img* to its non-transparent bounding box — the vector's own bounds.

    An SVG's declared canvas is usually bigger than the mark drawn in it
    (``play-console.svg`` paints inside ~35% of its 108×108 box), so without this
    the artwork arrives as a small island in a sea of transparent padding and
    every downstream fit — cover, contain, ``max_width`` — measures the padding
    instead of the art. Trimming moves the vector to the origin so its box is the
    thing that gets sized.

    A fully transparent image has no bounding box; it is returned untouched.
    """
    alpha = img.toarray(colorType=skia.kRGBA_8888_ColorType)[:, :, 3]
    rows = np.flatnonzero(alpha.any(axis=1))
    cols = np.flatnonzero(alpha.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        return img
    subset = img.makeSubset(
        skia.IRect.MakeLTRB(
            int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1
        )
    )
    return subset if subset is not None else img


def _rasterize_svg(data: bytes) -> skia.Image | None:
    """Rasterize SVG bytes to a CPU skia.Image, or None if not a valid SVG.

    Renders at up to ``_SVG_RENDER_MAX`` on the longest side, preserving the
    SVG's aspect ratio (from its width/height, else its ``viewBox``, else
    square), then trims the transparent padding. Safe to call off the GL thread —
    it uses a CPU raster surface.
    """
    dom = skia.SVGDOM.MakeFromStream(skia.MemoryStream(data))
    if dom is None:
        return None

    size = dom.containerSize()
    w, h = size.width(), size.height()
    if w <= 0 or h <= 0:
        # viewBox-only SVG: recover aspect from the viewBox, else default square.
        m = _VIEWBOX_RE.search(data)
        if m:
            try:
                w, h = float(m.group(1)), float(m.group(2))
            except ValueError:
                w = h = 0.0
        if w <= 0 or h <= 0:
            w = h = float(_SVG_RENDER_MAX)

    # Render at _SVG_RENDER_MAX on the longest side (vector scaling is lossless),
    # preserving aspect — upscales small icons and caps large art.
    scale = _SVG_RENDER_MAX / max(w, h)
    render_w = max(1, round(w * scale))
    render_h = max(1, round(h * scale))

    surface = skia.Surface(int(render_w), int(render_h))
    canvas = surface.getCanvas()
    canvas.clear(skia.Color4f(0, 0, 0, 0))
    # Enlarging the CONTAINER does not enlarge the drawing: an SVG with intrinsic
    # width/height keeps its own user-space coordinates, so a bigger container
    # just adds empty space and the art stays at 1:1 in the top-left corner
    # (measured: 0.4–3.8% ink coverage on real icons). Scale the CANVAS instead
    # and leave the container at the intrinsic size, which is what actually
    # magnifies the vector.
    dom.setContainerSize(skia.Size(float(w), float(h)))
    canvas.scale(scale, scale)
    dom.render(canvas)
    return _trim_to_ink(surface.makeImageSnapshot())


def _retry_delay(retry_after: str | None) -> float:
    """Seconds to wait before retrying a 429 whose ``Retry-After`` is *retry_after*."""
    try:
        seconds = float(retry_after) if retry_after is not None else math.nan
    except ValueError:
        seconds = math.nan
    if not math.isfinite(seconds) or seconds < 0:
        return _RETRY_AFTER_DEFAULT
    return min(seconds, _RETRY_AFTER_CAP)


def _http_only(url: str) -> None:
    """Raise unless *url* is http(s). A picture's URL is the page's words, and
    ``file://`` would read the user's disk into a preview the agent sees."""
    if urlsplit(url).scheme.lower() not in ("http", "https"):
        raise ValueError(f"not an http(s) picture: {url}")


def _download(url: str) -> bytes:
    """GET *url* as md2ui, retrying a 429 once; any other failure raises.
    Only http(s), and only redirects that stay there: urllib alone follows one
    to ``ftp://``."""
    # Imported here: urllib.request and the HTTP client under it slow every
    # shell's start, and a document without remote pictures never needs them.
    import urllib.error
    import urllib.request

    class _StaysHttp(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            _http_only(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    _http_only(url)
    open_url = urllib.request.build_opener(_StaysHttp).open
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with open_url(req, timeout=10) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code != 429:
            raise
        time.sleep(_retry_delay(exc.headers.get("Retry-After")))
    with open_url(req, timeout=10) as resp:
        return resp.read()


def cached_bytes(url: str, fetch: Callable[[str], bytes | None]) -> bytes | None:
    """*url*'s bytes from the disk cache document pictures are kept in, fetched
    with *fetch* only the first time: the same picture on every run, as a CDN
    may serve one photo in more than one encoding. A server reads neither the
    network nor the cache (ADR-602)."""
    if not POLICY.remote:
        return None
    key = hashlib.md5((clean_image_url(url) or url).encode()).hexdigest()
    with diskcache.Cache(_CACHE_DIR, size_limit=_CACHE_SIZE_LIMIT) as disk:
        data = disk.get(key)
        if data is None:
            data = fetch(url)
            if data is not None:
                disk.set(key, data)
    return data  # type: ignore[return-value]  # diskcache returns Unknown


def decode_image(data: bytes) -> skia.Image | None:
    """Decode image bytes to a skia.Image, supporting raster formats and SVG.

    Raster (PNG/JPG/WebP/…) is the fast path; SVG is rasterized only when raster
    decoding fails, so a real raster image is never mis-parsed as SVG.

    ``MakeFromEncoded`` returns a *lazy* image that decodes on first draw; that
    lazy decode is unreliable when first drawn as a sub-rect on a CPU raster
    surface (it can silently render blank). Force an eager raster image so draws
    are deterministic — and so the decode happens here on the worker thread,
    not lazily on the GL thread.
    """
    img = skia.Image.MakeFromEncoded(data)
    if img is not None:
        raster = img.makeRasterImage()
        return raster if raster is not None else img
    return _rasterize_svg(data)


# A reduction is a resize by mipmaps where the codec cannot make it itself.
_REDUCE = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)


def _decode_reduced(data: bytes, level: int) -> skia.Image | None:
    """*data* decoded at ``1 / 2**level`` of its size (rounded up), or None.

    Level 0 is :func:`decode_image`, so a picture drawn at its full size is the
    same pixels it always was. Below that, a JPEG reduces inside its own decoder,
    which is closest to averaging every source pixel (closer than a mipmap or
    bilinear resize) and never holds the full-size pixels.
    Whatever the codec cannot reduce — a PNG, a JPEG stored rotated — is decoded
    whole and resized by mipmaps.
    """
    if level == 0:
        return decode_image(data)
    oriented = skia.Image.MakeFromEncoded(data)
    if oriented is None:
        return None
    width = -(-oriented.width() // 2**level)
    height = -(-oriented.height() // 2**level)
    codec = skia.Codec.MakeFromData(data)
    image = None
    if codec is not None and codec.getOrigin() == skia.kTopLeft_EncodedOrigin:
        size = codec.getScaledDimensions(1 / 2**level)
        if size.width() >= width and size.height() >= height:
            info = codec.getInfo().makeWH(size.width(), size.height())
            bitmap = skia.Bitmap()
            bitmap.allocPixels(info.makeColorType(skia.kN32_ColorType))
            pixels = skia.Pixmap()
            bitmap.peekPixels(pixels)
            if codec.getPixels(pixels) == skia.Codec.Result.kSuccess:
                bitmap.setImmutable()
                image = skia.Image.MakeFromBitmap(bitmap)
    if image is None:
        image = decode_image(data)
        if image is None:
            return None
    if (image.width(), image.height()) == (width, height):
        return image
    return image.resize(width, height, _REDUCE)


# A photo is held at least twice the size it is drawn, and drawn down through
# mipmaps (``render_fills.draw_picture``): held at 1x, a small picture such as an
# avatar reads soft. Holding more than 2x gains nothing visible for many more
# pixels.
_SLACK = 2.0


def _level(scale: float) -> int:
    """The coarsest halving of a picture that still holds *scale* of its pixels."""
    return 0 if scale >= 1.0 else math.floor(-math.log2(scale))


class Photo:
    """A raster picture, held as its encoded bytes and decoded at the size it is drawn.

    ``width()`` and ``height()`` are the source's, so every fit, crop and ratio is
    measured on the picture as it was sent (ADR-400): how much of it is held
    decides which pixels are drawn, never where. A draw asks for the scale it is
    drawn at (:meth:`image_for`); :meth:`ImageCache.fit_decodes` then decodes the
    photo at the largest scale any draw asked for, never beyond its source. A draw
    that needs more than is held is drawn from what is held, stretched, until the
    larger decode lands; a one-shot render waits for it, so it never shows. The
    held size steps by halvings, so a window resized by a few pixels keeps what
    it has.
    """

    def __init__(
        self, data: bytes, width: int, height: int, space: skia.ColorSpace | None
    ) -> None:
        self.data = data
        self._size = (width, height)
        # The colour space the header declares, which every decode of it has.
        self.space = space
        self.image: skia.Image | None = None
        self.level: int | None = None
        # The finest level asked for by the draws since the last fit.
        self.wanted: int | None = None
        # The level being decoded in the background, if one is.
        self.decoding: int | None = None

    def width(self) -> int:
        return self._size[0]

    def height(self) -> int:
        return self._size[1]

    def level_to_decode(self) -> int | None:
        """The level the draws since the last fit need decoded, or None when
        what is held serves them: at least as large as the largest draw, and no
        more than one halving larger. A photo held one halving larger is kept,
        so a window dragged narrower and back decodes nothing; following every
        halving both ways would stall the window's recordings on a drag."""
        wanted = self.wanted
        if wanted is None:
            return None
        if self.level is not None and wanted - 1 <= self.level <= wanted:
            return None
        return wanted

    def image_for(self, scale: float) -> skia.Image | None:
        """The held decode, if any, noting that a draw wants *scale* of the
        source's pixels."""
        # A box of no size still wants a pixel, not an endless halving.
        level = _level(max(_SLACK * scale, 1 / max(self._size)))
        self.wanted = level if self.wanted is None else min(self.wanted, level)
        return self.image


class Loading:
    """A photo with no decode yet, and the picture drawn in its place until it
    has one: what the box showed before the photo arrived. It measures as the
    photo, so the draw asks the photo's size of it."""

    def __init__(self, photo: Photo, standin: skia.Image | None) -> None:
        self.photo = photo
        self.standin = standin

    def width(self) -> int:
        return self.photo.width()

    def height(self) -> int:
        return self.photo.height()


Picture = skia.Image | Photo | Loading
"""What a picture's URL holds once it has landed: a photo, or an SVG's raster."""


def shown(picture: Picture, standin: skia.Image | None) -> Picture:
    """*picture*, or while it is a photo with no decode, *standin* in its place."""
    if isinstance(picture, Photo) and picture.image is None:
        return Loading(picture, standin)
    return picture


def load_picture(data: bytes) -> Picture | None:
    """A raster as a :class:`Photo`, read no further than its size; an SVG
    rasterized now; None when *data* is neither."""
    # Header-only: MakeFromEncoded decodes no pixel until one is drawn.
    raster = skia.Image.MakeFromEncoded(data)
    if raster is not None:
        # refColorSpace, not colorSpace: a borrowed sRGB singleton makes pybind refuse it
        # later wherever a shared one is asked for (the window's surface on resize).
        return Photo(data, raster.width(), raster.height(), raster.refColorSpace())
    return _rasterize_svg(data)


class ImageCache:
    """Fetches, decodes, and caches images referenced in a markdown node index.

    With *background* (the window), photos are decoded in child processes and
    land like a fetch, through :meth:`drain_pending`; without it (a one-shot
    render), :meth:`fit_decodes` decodes them before it returns.
    """

    def __init__(self, background: bool = False) -> None:
        self._disk: diskcache.Cache = diskcache.Cache(
            _CACHE_DIR, size_limit=_CACHE_SIZE_LIMIT
        )
        self._cache: dict[str, Picture | None] = {}
        # Per-url content kind ("svg" | "raster"), known after decode — used to
        # pick a kind-matched placeholder.
        self._kind: dict[str, str | None] = {}
        self._pending: queue.Queue[
            tuple[str, skia.Image | Photo | None, str | None]
        ] = queue.Queue()
        self._futures: list[Future[None]] = []
        self._decoder = None
        if background:
            # Imported here: the decoder's subprocess machinery slows every
            # shell's start, and only the window decodes in the background.
            from md2ui.utils.photo_decoder import PhotoDecoder

            self._decoder = PhotoDecoder(self._decoded)
        self._landed: queue.Queue[tuple[str, Photo, int, skia.Image | None]] = (
            queue.Queue()
        )
        self._wake: Callable[[], None] | None = None

    def fetch(
        self,
        node_index: dict,
        on_image_ready: Callable[[], None] | None = None,
    ) -> None:
        """Start background downloads for all images in node_index.

        Returns immediately. Each completed download is placed in the pending
        queue and ``on_image_ready`` is called (from the worker thread) so the
        caller can wake its event loop (e.g. ``glfw.post_empty_event``).
        Call ``drain_pending`` on the main / GL thread to upload results to GPU.
        """
        self._cache.clear()
        self._kind.clear()
        self._wake = on_image_ready
        # Drain any leftover pending results from a previous fetch.
        while not self._pending.empty():
            try:
                self._pending.get_nowait()
            except queue.Empty:
                break

        # Image leaves carry their URL inside the markdown content; an image
        # card carries its background URL as an attribute (it is a container,
        # so it has no content of its own). Both are normalised through
        # ``clean_image_url``, so ``md2ui.*`` annotations never reach the
        # network and two differently-annotated references to one photo share a
        # single download, decode and cache entry.
        urls: set[str] = {
            url
            for node in node_index.values()
            for url in [
                clean_image_url(
                    image_url(node.get("content", ""))
                    if node.get("type") == "image"
                    else node.get("card_bg_url")
                )
            ]
            if url
        }

        disk = self._disk
        pending = self._pending

        def _load(url: str) -> None:
            try:
                _fetch_one(url)
            finally:
                # diskcache opens a connection per thread and keeps it until the
                # thread ends: close this one now, as Windows cannot remove a
                # cache whose file is still open.
                disk.close()

        def _fetch_one(url: str) -> None:
            if not POLICY.remote:
                # A server fetches nothing, not even from the disk cache an app
                # filled. A fetch never made has not failed: the URL gets no
                # entry, so the image draws as one still loading.
                return
            key = hashlib.md5(url.encode()).hexdigest()
            cached = disk.get(key)
            if cached is None:
                print(f"[image] fetch  {url}")
                try:
                    data: bytes = _download(url)
                    disk.set(key, data)
                except Exception as exc:
                    print(f"[image] fetch failed  {exc}")
                    pending.put((url, None, None))
                    if on_image_ready:
                        on_image_ready()
                    return
            else:
                print(f"[image] disk cache hit  {url}")
                data = cached  # type: ignore[assignment]  # diskcache returns Unknown
            kind = "svg" if b"<svg" in data[:1024] else "raster"
            picture = load_picture(data)
            if picture is not None:
                print(
                    f"[image] read ok ({kind})  {len(data)} bytes"
                    f"  →  {picture.width()}×{picture.height()}"
                )
            else:
                print(f"[image] decode failed  ({len(data)} bytes received)")
            pending.put((url, picture, kind))
            if on_image_ready:
                on_image_ready()

        executor = ThreadPoolExecutor(max_workers=8)
        self._futures = [executor.submit(_load, url) for url in urls]
        executor.shutdown(wait=False)

    def drain_pending(self, context: skia.GrDirectContext) -> bool:
        """Take the pictures that landed, uploading each SVG raster to the GPU.
        Call from the GL thread. A photo is decoded when it is first drawn.

        Returns True if at least one image was newly added to the cache
        (i.e. a re-render is needed).
        """
        changed = self._take_decodes()
        while True:
            try:
                url, cpu_img, kind = self._pending.get_nowait()
            except queue.Empty:
                break
            self._kind[url] = kind
            if cpu_img is None or isinstance(cpu_img, Photo):
                self._cache[url] = cpu_img
                changed = True
                continue
            gpu_img = cpu_img.makeTextureImage(context)
            if gpu_img is not None:
                self._cache[url] = gpu_img
                print(
                    f"[image] gpu upload ok  {gpu_img.width()}×{gpu_img.height()}  {url}"
                )
            else:
                self._cache[url] = cpu_img
                print(f"[image] gpu upload failed, keeping CPU image  {url}")
            changed = True
        return changed

    def drain_pending_cpu(self) -> bool:
        """Move any decoded CPU images into the cache without a GL context.

        Headless counterpart of ``drain_pending`` — stores the CPU ``skia.Image``
        directly (no ``makeTextureImage``), so ``get`` returns images that draw on
        a CPU raster surface. Returns True if anything was added.
        """
        changed = False
        while True:
            try:
                url, cpu_img, kind = self._pending.get_nowait()
            except queue.Empty:
                break
            self._kind[url] = kind
            self._cache[url] = cpu_img
            changed = True
        return changed

    def _decoded(self, key: object, level: int, image: skia.Image | None) -> None:
        """A background decode landed (called from the decoder's thread)."""
        url, photo = key  # type: ignore[misc]  # the key fit_decodes gave
        self._landed.put((url, photo, level, image))
        if self._wake:
            self._wake()

    def _take_decodes(self) -> bool:
        """Hold the background decodes that landed; True if one did."""
        changed = False
        while True:
            try:
                url, photo, level, image = self._landed.get_nowait()
            except queue.Empty:
                return changed
            photo.decoding = None
            if self._cache.get(url) is not photo:
                continue  # a photo of a document since replaced
            changed = True
            if image is None:
                print(f"[image] decode failed  {url}")
                self._cache[url] = None
            else:
                photo.image, photo.level = image, level

    def close(self) -> None:
        """End the background decoders, if any started, and let go of the disk
        cache this thread opened."""
        if self._decoder is not None:
            self._decoder.close()
        self._disk.close()

    def wait(self, timeout: float) -> None:
        """Block until every fetch has landed, or *timeout* seconds have passed."""
        wait(self._futures, timeout=timeout)

    def fit_decodes(self) -> bool:
        """Decode each photo drawn since the last fit at the largest scale its
        draws asked for. True when a decode changed, so what was drawn with the
        old one must be drawn again; a photo that cannot be decoded has failed.

        One at a time: decoding on threads is no faster, and each decode in
        flight holds a progressive JPEG's whole-image working memory.

        In the background, a decode is queued instead and this returns False: it
        lands through :meth:`drain_pending`, whose True has the window draw again,
        and that draw asks again. One decode per photo is in flight at a time,
        two photos at once (``PhotoDecoder``): each in its own process, so two
        run in parallel where two threads could not, and their working memory
        goes with the processes once they idle.
        """
        changed = False
        for url, picture in list(self._cache.items()):
            if not isinstance(picture, Photo):
                continue
            level, picture.wanted = picture.level_to_decode(), None
            if level is None:
                continue
            if self._decoder is not None:
                if picture.decoding is None:
                    picture.decoding = level
                    self._decoder.decode(
                        (url, picture), picture.data, level, picture.space
                    )
                continue
            changed = True
            image = _decode_reduced(picture.data, level)
            if image is None:
                print(f"[image] decode failed  {url}")
                self._cache[url] = None
            else:
                picture.image, picture.level = image, level
        return changed

    def has_pending(self) -> bool:
        """Return True if fetched pictures or decodes are waiting to be taken."""
        return not (self._pending.empty() and self._landed.empty())

    def get(self, url: str | None) -> Picture | None:
        # Normalised so callers can pass the raw markdown URL, annotations and
        # all, and still hit the entry ``fetch`` stored under the clean URL.
        url = clean_image_url(url)
        if url is None:
            return None
        return self._cache.get(url)

    def failed(self, url: str | None) -> bool:
        """True once *url*'s fetch or decode has failed: an answer, not a wait.

        A URL still in flight, or one the fetch policy skipped, has no entry at
        all, so it has not failed.
        """
        url = clean_image_url(url)
        return url is not None and url in self._cache and self._cache[url] is None

    def get_kind(self, url: str | None) -> str | None:
        """Decoded content kind for *url* ("svg" | "raster"), or None if unknown."""
        url = clean_image_url(url)
        if url is None:
            return None
        return self._kind.get(url)
