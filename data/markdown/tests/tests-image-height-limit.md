<!--
The image height limit (render_image_limits, 2026-09-26).

In a space 768px or wider — the space the image is given, never the window — an image
with an authored `aspect_ratio` is never drawn taller than a 16:9 image filling that
space (HEIGHT_LIMIT = 9/16 of its width). Its width is capped and its ratio kept. The
author wins wherever they said something about size — a `max_width`, a circle, a
`min_width` above the limit — and an image with no ratio keeps the default ratios. In
a narrow space nothing is limited.

The snapshot renders at 767px (every space here is narrow, so nothing is limited)
and at 1280px (the tall and square ones are held to the limit of their space). Images are example.com
placeholders, so only their boxes matter.
-->

# Limited in a wide space

**Tall 3 by 4** — narrower at 1280px, full width at 767px.

![Map](https://example.com/map.jpg?md2ui.aspect_ratio=3:4)

___

**Portrait 9 by 16** — narrower still at 1280px.

![Phone](https://example.com/phone.jpg?md2ui.aspect_ratio=9:16)

___

**Square** — held to the height of a full-width 16 by 9 at 1280px.

![Square](https://example.com/square.jpg?md2ui.aspect_ratio=1:1)

___

**Inside a card** — the limit is the card's space, a little narrower than the page.

## Card

![Map](https://example.com/map.jpg?md2ui.aspect_ratio=3:4)

***

# Never limited

**Wide 16 by 9** — exactly at the limit, full width at both widths.

![Banner](https://example.com/banner.jpg?md2ui.aspect_ratio=16:9)

___

**Wider 2.35 by 1** — under the limit.

![Panorama](https://example.com/pano.jpg?md2ui.aspect_ratio=2.35:1)

___

**No ratio written** — the default ratio for its width.

![Photo](https://example.com/photo.jpg)

___

**The author's maximum** — 900px wide at 1280px, taller than the limit.

![Map](https://example.com/map.jpg?md2ui.aspect_ratio=3:4&md2ui.max_width=900)

___

**The author's minimum** — at least 800px wide at 1280px, above the limit.

![Square](https://example.com/square.jpg?md2ui.aspect_ratio=1:1&md2ui.min_width=800)

___

**A circle** — its shape is the author's, so it is left alone.

![Avatar](https://example.com/avatar.jpg?md2ui.shape=circle&md2ui.max_width=160)

___

![Square](https://example.com/square.jpg?md2ui.aspect_ratio=1:1)
:::1
**In a row cell** — the square takes one share of two, a narrow space, so it is not limited.
:::1
