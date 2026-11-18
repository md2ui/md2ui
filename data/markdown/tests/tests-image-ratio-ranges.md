<!--
Authored aspect-ratio ranges (render_metrics.ratio_ranges, owner decision 2026-10-04).

An image's ratio is authored, never inferred. `aspect_ratio=3:4` is 3:4 at every
width; `3:4,1:1@600,16:9@960` is 3:4, then 1:1 once the image is 600px wide, then
16:9 from 960px. There is no height limit: an image always fills its width, so
nothing leaves a gap beside it. With no ratio, the default is
`3:2,16:9@768,2.35:1@1024`.

The snapshot renders at 767px and 1280px, so each ranged image lands in a
different range at each width.
-->

# Ratios the author chose

<!-- The finding this was written for (findings/picture-weight-2-leaves-a-gap):
     a 4:3 photo in a `::: 2 >` cell. A height limit used to narrow it and leave
     a gap beside it; it now fills its cell at 4:3. -->
![Plate](https://upload.wikimedia.org/wikipedia/commons/e/e3/Che_ne_saj.jpg?md2ui.aspect_ratio=4:3)
::: 2 >
**The tasting menu, reimagined**
Begin at any neighborhood taquería, where the pastor has been perfected since 1959.

___

<!-- A tall photo that turns square, then wide, as it widens: 3:4 under 600px,
     1:1 at 767, 16:9 at 1280. -->
![Lake](https://upload.wikimedia.org/wikipedia/commons/e/e3/Che_ne_saj.jpg?md2ui.aspect_ratio=3:4,1:1@600,16:9@960)

___

<!-- The same ranges in a narrow cell of the row: the image's own width picks the
     ratio, so it stays 3:4 here on a wide page. -->
![Lake](https://upload.wikimedia.org/wikipedia/commons/e/e3/Che_ne_saj.jpg?md2ui.aspect_ratio=3:4,1:1@600,16:9@960)
:::1
**In a narrow cell** — the picture keeps its tall ratio.
:::2

___

<!-- No ratio written: the default — 3:2 at 767 (the image is under 768px wide)
     and 2.35:1 at 1280. -->
![Lake](https://upload.wikimedia.org/wikipedia/commons/e/e3/Che_ne_saj.jpg)
