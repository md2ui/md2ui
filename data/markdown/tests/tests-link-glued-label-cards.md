<!-- A link whose label is two or more GLUED lines is a group link: each line
     an element, styled as it would be outside a link (`**…**` bold, `_…_`
     the Muted tier), the glued block a card on the element background, and
     the whole card the link. Owner decision 2026-10-06; see
     data/markdown/tests-render/linked-file-cards. -->

## Glued labels

<!-- Inline-wrapped: the label runs over a soft line break. A card of two
     elements, not a pill with `**` and `_` printed. -->
[**Flights CDMX ⇄ Huatulco**
_Edited Oct 4_](/files/flights)

<!-- Bracketed: `[` and `](url)` on their own lines around the glued block.
     The same card as the inline spelling; the three cards share a shape and
     grid in a row. -->
[
**Gastos 2026**
_Edited Oct 1_
](/files/gastos)

[
**Carta**
_Edited Sep 22_
](/files/carta)

## Glued labels in a list

<!-- A list item whose whole content is such a link: the item keeps its
     marker and is the card, inline-wrapped or bracketed. A one-line link
     item stays a pill. -->
- [**Flights CDMX ⇄ Huatulco**
  _Edited Oct 4_](/files/flights)
- [
  **Gastos 2026**
  _Edited Oct 1_
  ](/files/gastos)
- [Open Drive](/drive)

## Still pills

<!-- A one-line label stays a pill, however it is spelled. -->
[Open Drive](/drive)

[
Preview
](/preview)

<!-- Lines separated by a blank line are not glued: still one pill. -->
[
Shared with me

Recent
](/shared)

<!-- A link wrapped inside a sentence is prose, not a card: still a pill
     inside the paragraph. -->
See the [recent files
list](/recent) before the meeting.
