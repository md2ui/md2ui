<!-- A `:::` cell whose only content is a `+++` spacer is a SPACER CELL of its
     row: space across the row, never an empty cell the row is decided without
     (findings/spacer-cells-in-rows, 2026-10-07). -->

<!-- A spacer cell after the last cell: space after Text, inside this
     section. The section is NOT closed by its `:::` as a cell of an outer
     row, so the next section stays a section of its own. -->
## 

Text

:::

++++

<!-- A spacer cell before the only cell: space before Text, as `++++ Text`. -->
## 

++++

:::

Text

<!-- A spacer cell between two cells: the gap between them, as `Text ++++ Text`. -->
## 

Text

:::

++++

:::

Text

<!-- Spacer cells on both sides of one cell hold it between them, as
     `++++ text ++++` holds a paragraph: space across, never down. -->
## 

++++

:::

Key: ... value
Key: ... value
Key: ... value
Key: ... value

:::

++++
