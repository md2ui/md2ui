"""Which picture an image paints: its own, or the placeholder that says why not.

Two placeholders, one meaning each. The loading one says a picture has not
arrived yet; the broken one says it never will. Both assets share one pixel
size, so a failed picture draws in the loading one's crop.

An image with no source, ``![alt]()``, has no picture on purpose: it is neither
loading nor broken, so it paints neither placeholder, only a quiet box in the
picture background. Nothing is fetched for it.

A THEME.md background image that fails paints the broken placeholder in its
place: the declaration already chose the colours over it
(``On background color: image``), so leaving it out would leave that text on a
fill it was never coloured for. One a server never fetched has not failed, and
paints nothing.

A muted chip or badge (``~~…~~``) paints its theme background image faded to
``MUTED_OPACITY``: no ``Disabled …`` key names an image, so
the fade is its state whatever colours the theme states. The picture keeps its
pixels' size, so its cover-fit and clip do not change.

Only paint reads this. The grouper, the generator and the measurement never ask
whether a picture loaded, so a failed picture keeps its box and its run.
"""

from collections.abc import Callable
from pathlib import Path

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.render_backgrounds import element_background_sources
from md2ui.pipeline.render_settings import VIEW
from md2ui.pipeline.theme_model import MUTED_OPACITY, Theme
from md2ui.utils.fetch_policy import POLICY, fetch_remote
from md2ui.utils.image_cache import (
    ImageCache,
    Picture,
    cached_bytes,
    decode_image,
    shown,
)
from md2ui.utils.image_params import clean_image_url

NO_PICTURE_COLOR = skia.ColorSetRGB(0xD0, 0xD0, 0xD0)
"""The picture background: the field every placeholder asset is drawn on."""

# One pixel of it, handed to the picture drawer like any picture, so the box is
# clipped to its shape and corners exactly as a picture would be.
_pixel = skia.Surface(1, 1)
_pixel.getCanvas().clear(NO_PICTURE_COLOR)
NO_PICTURE = _pixel.makeImageSnapshot()
"""The quiet box. It always fills the box its ratio gives, whatever the fit:
a picture left out has nothing to fit."""


def image_picture(
    image_cache: ImageCache, url: str | None, is_vector: bool
) -> "Picture | None":
    """The picture a content image paints.

    The I key forces the loading placeholder whatever the cache holds, except
    on an image with no picture, which is never loading.
    """
    if not clean_image_url(url):
        return NO_PICTURE
    if VIEW.placeholder_images:
        return VIEW.placeholder_vector if is_vector else VIEW.placeholder_raster
    if image_cache.failed(url):
        return VIEW.placeholder_broken
    loading = VIEW.placeholder_vector if is_vector else VIEW.placeholder_raster
    real = image_cache.get(url)
    return shown(real, loading) if real is not None else loading


def card_photo(
    image_cache: ImageCache, url: str, fallback: "skia.Image | None"
) -> "Picture | None":
    """The picture a photo card paints as its background.

    Its own photo wins over any themed background image. While the fetch or the
    first decode is in flight the card falls back to the theme's, so it is never
    a hole and the window does not flash a placeholder for a photo that is
    merely late.
    """
    if image_cache.failed(url):
        return VIEW.placeholder_broken or fallback
    # A failed theme fallback is not this card's failure: it is still loading.
    loading = (
        VIEW.placeholder_raster if fallback is VIEW.placeholder_broken else fallback
    )
    real = image_cache.get(url)
    return shown(real, loading) if real is not None else loading


def decode_theme_image(source: str) -> "skia.Image | None":
    """Decode one theme background image from a local path or http(s) URL;
    ``None`` when it is missing, unreachable, undecodable, or never fetched."""
    try:
        if source.startswith(("http://", "https://")):
            # Kept like a document's pictures: one download, the same bytes after.
            data = cached_bytes(source, fetch_remote)  # None on a server
            return decode_image(data) if data is not None else None
        path = Path(source)
        if path.exists():
            return decode_image(path.read_bytes())
        print(f"[background] image not found: {path}")
    except Exception as exc:  # noqa: BLE001 - non-fatal, the placeholder stands in
        print(f"[background] failed to load {source}: {exc}")
    return None


def theme_picture(
    source: str | None,
    decode: Callable[[str], "skia.Image | None"] = decode_theme_image,
) -> "skia.Image | None":
    """The picture a declared THEME.md background image paints: its own, the
    broken placeholder once it failed, or nothing when there is none to paint.

    *decode* lets a caller cache the decode without caching the placeholder,
    which the shells load after import.
    """
    if not source:
        return None
    image = decode(source)
    if image is not None:
        return image
    if source.startswith(("http://", "https://")) and not POLICY.remote:
        return None  # never fetched, so never failed
    return VIEW.placeholder_broken


def element_pictures(theme: Theme) -> dict[object, "skia.Image"]:
    """The theme background image of every button, chip, emoji badge and copy
    button, decoded once per source and keyed ``("element", source)``, so
    variants that inherit or share one source share its picture."""
    images: dict[object, skia.Image] = {}
    for source in element_background_sources(theme):
        image = theme_picture(source)
        if image is not None:
            images[("element", source)] = image
    return images


def element_picture(
    images: dict | None, source: str | None, muted: bool
) -> "skia.Image | None":
    """The picture an element's theme background image paints: the decoded
    one, faded on a *muted* element. The fade is made once per source and kept
    in *images*, which lives exactly as long as the decoded theme does."""
    images = images if images is not None else {}
    image = images.get(("element", source))
    if image is None or not muted:
        return image
    faded = images.get(("element", source, "muted"))
    if faded is None:
        surface = skia.Surface(image.width(), image.height())
        surface.getCanvas().drawImage(
            image, 0, 0, skia.SamplingOptions(), skia.Paint(Alphaf=MUTED_OPACITY)
        )
        faded = images[("element", source, "muted")] = surface.makeImageSnapshot()
    return faded
