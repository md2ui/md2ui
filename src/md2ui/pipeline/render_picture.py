"""The recorded document: painted once per scene, replayed every frame.

Repainting the whole document on every scroll tick would redo work that has
not changed. The document layer (``layout_render.draw_document``) is in
content coordinates and depends on nothing about the window, so it is recorded
once into a ``skia.Picture`` and ``draw_scene`` replays it under the scroll
translate and the viewport clip. The headless render goes through the same
recording, so the render snapshot exercises the path the window shows.

**Viewport culling is Skia's R-tree, not per-box bounds.** The picture is
recorded with an R-tree bounding-box hierarchy, so a replay through the viewport
clip plays back only the draws whose bounds meet it. Skia computes those bounds
from each draw itself — blur mask filters included, clamped by the clip each
draw paints through — so a shadow's offset and radius are accounted for by
construction. A cull in Python would have to re-derive every drawer's ink
extent (shadows, image bleed, gutter markers, chart overflow): a second geometry
computation beside the paint, which is the divergence ADR-400 exists to prevent.
Skipping boxes would also shift ``draw_document``'s positional colour counter.

Replay is pixel-identical to direct drawing at dpr 1 and 2, and a frame costs
far less than the one-time recording.
"""

from __future__ import annotations

from collections.abc import Callable

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.layout_render import draw_document
from md2ui.pipeline.render_actions import with_node_states
from md2ui.pipeline.render_settings import VIEW
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import Theme
from md2ui.utils.image_cache import ImageCache

# How far past the layout the recording's cull rect reaches. Content may bleed
# into the root padding and the centring slack, and the viewport clip — not the
# recording — is what decides what is visible, so the recording must clamp
# nothing a window could show.
_CULL_MARGIN = 100_000.0


def record(
    draw: Callable[[skia.Canvas], None], width: float, height: float
) -> skia.Picture:
    """Record *draw* into a picture with an R-tree, covering the ``width`` ×
    ``height`` content rect and ``_CULL_MARGIN`` around it."""
    recorder = skia.PictureRecorder()
    canvas = recorder.beginRecording(
        skia.Rect.MakeLTRB(
            -_CULL_MARGIN, -_CULL_MARGIN, width + _CULL_MARGIN, height + _CULL_MARGIN
        ),
        skia.RTreeFactory()(),
    )
    draw(canvas)
    return recorder.finishRecordingAsPicture()


def record_document(
    boxes: list,
    section_boxes: list | None,
    node_index: dict,
    layout_w: float,
    layout_h: float,
    fonts: FontSet,
    image_cache: ImageCache,
    theme: Theme | None,
    ast_layout=None,
    background_images: dict | None = None,
) -> skia.Picture:
    """``draw_document``, recorded, with the host's node states shown.

    A photo draws from its decode at the size this recording asked of it, so the
    document is recorded again whenever that changed a decode — the first
    recording after a photo landed, or after a width or pixel ratio that holds
    it at another size. The second asks the same sizes, so it is the last. In
    the window the decode lands later instead (``ImageCache(background=True)``),
    and its landing records again.
    """
    shown = with_node_states(node_index, VIEW.node_states)

    def draw(canvas: skia.Canvas) -> None:
        draw_document(
            canvas,
            boxes,
            section_boxes,
            shown,
            layout_w,
            layout_h,
            fonts,
            image_cache,
            theme,
            ast_layout,
            background_images,
        )

    picture = record(draw, layout_w, layout_h)
    while image_cache.fit_decodes():
        picture = record(draw, layout_w, layout_h)
    return picture


def view_state() -> tuple:
    """The display toggles ``draw_document`` reads. Flipping any of them makes a
    different document, so they belong in the recording's key. ``show_frame`` is
    deliberately absent: the chrome is drawn by ``draw_scene``, outside it. So
    is the host's per-node state (a pending button, an optimistic tick)."""
    return (
        VIEW.wireframe,
        VIEW.debug_spacing,
        VIEW.debug_padding,
        VIEW.text_boxes,
        VIEW.placeholder_images,
        VIEW.pixel_ratio,
        tuple(sorted(VIEW.node_states.items())),
    )


class DocumentPicture:
    """One recorded document and the key it was recorded under.

    The key has two halves. ``objects`` — the boxes, the theme, the fonts, the
    image cache — are compared by IDENTITY: they are replaced, never edited, when
    they change, and holding them here keeps each alive, so a new object can
    never reuse a cached one's id. ``values`` — the layout size, the image
    generation and :func:`view_state` — are compared by equality.
    """

    def __init__(self) -> None:
        self._objects: tuple = ()
        self._values: tuple | None = None
        self._picture: skia.Picture | None = None
        self.recordings = 0

    def get(
        self,
        objects: tuple,
        values: tuple,
        record_fn: Callable[[], skia.Picture],
    ) -> skia.Picture:
        """The cached picture, re-recorded with *record_fn* only when the key moved."""
        if (
            self._picture is None
            or values != self._values
            or len(objects) != len(self._objects)
            or any(a is not b for a, b in zip(objects, self._objects))
        ):
            self._picture = record_fn()
            self._objects, self._values = objects, values
            self.recordings += 1
        return self._picture

    def document(
        self,
        boxes: list,
        section_boxes: list | None,
        node_index: dict,
        layout_w: float,
        layout_h: float,
        fonts: FontSet,
        image_cache: ImageCache,
        theme: Theme | None,
        ast_layout=None,
        background_images: dict | None = None,
        image_generation: int = 0,
    ) -> skia.Picture:
        """``draw_document`` for these arguments, recorded only when the key moved.

        The key is built HERE, from exactly the arguments the document is painted
        from, plus the toggles it reads (:func:`view_state`) and
        *image_generation* — which the caller bumps when an image fetched in the
        background lands in *image_cache*. One list, so a new input to the paint
        cannot be left out of the key (ADR-401).
        """
        return self.get(
            (boxes, section_boxes, node_index, fonts, image_cache, theme)
            + (ast_layout, background_images),
            (layout_w, layout_h, image_generation, view_state()),
            lambda: record_document(
                boxes,
                section_boxes,
                node_index,
                layout_w,
                layout_h,
                fonts,
                image_cache,
                theme,
                ast_layout,
                background_images,
            ),
        )
