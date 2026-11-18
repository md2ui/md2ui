<!--
Per-width `:::` dividers and the image `min_width` floor (2026-09-26).

  ::: 1 >     cuts in wide space only; in narrow space the two sides stack
  ::: 1 <     cuts in narrow space only
  ::: 1 1.5   weight 1 in narrow space, 1.5 in wide space

Narrow space is under 768px, measured on the width the ROW is given, not the page. The
snapshot renders at 767px, where every row here is in narrow space, and at 1280px, where
the full-width rows are in wide space and the rows inside the two grid cards are not.

Images are example.com placeholders, so only their boxes matter.
-->

# Row conditions

Each row below is cut from the next, so none of them takes its neighbour.

___

![Photo](https://example.com/image.jpg)
::: 1 >
**Wide only** — beside the picture at 1280px, under it at 767px.
:::2

___

![Photo](https://example.com/image.jpg)
::: 1 <
**Narrow only** — beside the picture at 767px, under it at 1280px.
:::2

___

![Photo](https://example.com/image.jpg)
::: 1 2
**Two weights** — the picture takes one share of two at 767px, two of three at 1280px.

___

![Icon](https://example.com/one.jpg?md2ui.max_width=48&md2ui.aspect_ratio=1:1)
::: 0 >
**Fit, wide only** — the icon shrinks to fit beside this text at 1280px.

___

**Condition alone**
::: >
Weight 1 and wide only — beside the label at 1280px, under it at 767px.

___

**A**
::: 1 >
**B** — stacks under A at 767px; beside it at 1280px.
:::2
**C** — beside the A and B cell at every width, which takes B's weight when they stack.

___

<!-- Mistyped: read as a bare `:::`, and `check` reports divider-fallback. -->
**Fallback**
::: 1 1.5 >
Beside the label at every width, with no weights.

___

<!-- Words after the colons keep the line as text: it draws, and nothing is cut. -->
::: note

***

# Image floors

A minimum width is a floor and a maximum width a ceiling on the picture's cell, and the ceiling wins.

___

![Photo](https://example.com/two.jpg?md2ui.min_width=320&md2ui.aspect_ratio=1:1)
::: 1
**Floor raised** — one share of six is under 320px, so the picture is raised to 320px and this text gives up the difference.
:::5

___

![Photo](https://example.com/two.jpg?md2ui.min_width=560&md2ui.aspect_ratio=16:10)
::: 1
**Floor too wide** — at 767px the picture and this text cannot both fit, so the row stacks instead of squeezing the picture.
:::1

___

![Photo](https://example.com/two.jpg?md2ui.min_width=120&md2ui.max_width=120&md2ui.aspect_ratio=1:1)
:::0
**Fixed size** — minimum equals maximum, so exactly 120px at every width.

___

![Photo](https://example.com/two.jpg?md2ui.min_width=400&md2ui.max_width=160&md2ui.aspect_ratio=1:1)
:::0
**The ceiling wins** — the minimum is above the maximum, so 160px.

***

# Rows inside grid cards

Two cards side by side — each row is offered about half the page, so it is in narrow space at both widths and stacks.

## Card one

![Photo](https://example.com/image.jpg)
::: 1 >
Under the picture at 1280px too.

## Card two

![Photo](https://example.com/image.jpg)
::: 1 >
Under the picture at 1280px too.

***

# In list items

- ![Icon](https://example.com/one.jpg?md2ui.max_width=40&md2ui.aspect_ratio=1:1)
  ::: 0 >
  **Beside the icon at 1280px only**

___

- ![Icon](https://example.com/one.jpg?md2ui.max_width=40&md2ui.aspect_ratio=1:1)
  ::: 0 <
  **Beside the icon at 767px only**
