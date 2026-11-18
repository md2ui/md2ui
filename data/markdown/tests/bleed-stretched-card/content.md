<!-- `Image bleed: yes` in a bento board, where a card is stretched to its band
     and keeps empty space below its last line. An image that ENDS its card's
     content runs down through that space to the card's edge, when it is full
     width or an aside. An image with a line below it, or pictures sharing a
     line, stop where they are (2026-10-23,
     data/markdown/tests-render/home-dashboards/whipsaw-phone-os). -->

## Two thumbnails

Two pictures share one line; only a full-width or aside image runs down a stretched card.

![One](https://example.com/one.jpg?md2ui.aspect_ratio=1:1) ![Two](https://example.com/two.jpg?md2ui.aspect_ratio=1:1)

## Long notes

A card of several paragraphs, so the board's cards differ in height.

Bento stretches each card to its band, whatever its own content needs.

A stretched card keeps its content at the top and leaves the rest empty.

An image that ends a card's content still reaches the card's bottom edge.

## Trailing photo

A photo after a line, the last thing in its card.

![Photo](https://example.com/one.jpg?md2ui.aspect_ratio=16:9)

## Aside photo

Beside a short column of text.
...
_A muted line_
::: 1
![Photo](https://example.com/two.jpg?md2ui.aspect_ratio=1:1)
:::1

## Captioned photo

![Photo](https://example.com/one.jpg?md2ui.aspect_ratio=16:9)

_A caption below stops the bottom bleed._
