# ADR-401: The window replays a recorded document

**Status:** active
**Domain:** renderer
**Read when:** you are about to make a frame cheaper by skipping boxes, or you add a display
toggle, a cached image or anything else the document paint reads.

## Decision

The document layer — everything that scrolls with the content, painted by
`layout_render.draw_document` — is recorded once into a `skia.Picture` with an R-tree
(`render_picture.record_document`), and every frame replays it under the scroll translate and
the viewport clip (`draw_scene`). Viewport culling is that replay: the R-tree plays back only
the draws whose bounds meet the clip. The headless render records and replays the same way,
so there is one paint path.

The recording is reused while its key holds (`render_picture.DocumentPicture`).

## Reason

Repainting the whole document on every scroll tick made long documents slow to scroll; a
replay costs a fraction of a frame, and the recording is paid once per scene. The replay is
pixel-identical to direct drawing.

Skia bounds each recorded draw by the draw itself, blur mask filters included, so a shadow
cast into the viewport by an off-screen box is kept by construction
(`tests/render_picture_tests.py` pins that case).

## Alternatives rejected

- **A cull in Python:** an ink rect per box, grown by its shadows, and a band index to query.
  - Every drawer's ink extent would have to be derived a second time, beside the paint that
    produces it — shadow offset and radius, image bleed, gutter markers, chart overflow. That
    is the divergence ADR-400 exists to prevent.
  - Skipping a box would shift the section loop's positional colour counter, so table zebra
    rows would change colour with the scroll offset.
  - It would still repeat every visible box's styling on each frame.

## Constraint created

- **Anything `draw_document` reads must be part of the recording's key,** or a change to it
  will not reach the screen until something else re-records. A new display toggle goes in
  `render_picture.view_state`. A new asynchronously arriving resource needs a generation
  counter, as images have.
- **`draw_document` must not read the window:** its size, the scroll offset and the chrome
  all belong to `draw_scene`.
- **The pixel ratio is the one exception.** A photo is decoded at the size it lands on the
  device, so the pixel ratio is in `view_state`: a window moved to a screen of another ratio
  records again. Only the photo decode reads it; every position is still in layout pixels,
  scaled by `draw_scene`. A recording that changed a decode is recorded once more, so a
  one-shot render never draws a photo from a smaller decode stretched up.
- **The window does not wait for a decode.** Its decodes run in child processes
  (`src/md2ui/utils/photo_decoder.py` says why) and land like a fetch, bumping the image generation.
  Meanwhile it records what it holds: a smaller decode stretched up, or what the box showed
  while the photo was fetched. One-shot renders decode in process before they paint, so their
  output is the same.
- **A code block the user scrolls sideways is painted over the recording, never into it.**
  The recording holds every block at offset 0; each frame, `draw_scene`'s `overlay` hook
  repaints the scrolled blocks at their offsets (`render_scroll_overlay`). An offset is
  per-frame state and must never reach the recording's key, or scrolling a block would record
  the whole document again on every tick.

## Reconsider when

A document grows so large that recording it whole is noticeably slow on a width change. The
answer then is several recorded tiles, not a Python cull.
