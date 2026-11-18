<!-- TEXT AND A `:::` ABOVE THE FIRST HEADED CELL. The heading peel is
     transparent to `:::`, so the text above the first heading arrives inside
     that heading's section. When the section is itself a cell of a row outside
     it, the text is cell 1 and the section holds only its heading and body.
     Once broken: `Links` and `Plan` squeezed into one card, `Support` dropped
     below it at full width. Each case ends with `***`, which closes the
     heading section holding it (a `___` alone would not, and the next case
     would land in the section's body), then `___`, which ends the row. -->

<!-- Three cells: Links | Plan | Support. -->
___
Links
:::1
### Plan
Two seats
:::
### Support
Email only
:::
***
___

<!-- The same card with nothing after it: its closing `:::2` makes it a cell,
     so Links sits beside the card rather than inside it. -->
Links
:::1
### Plan
Two seats
:::2
***
___

<!-- A row already open when the heading arrives: Lead | Links | Plan. Once
     broken: the section kept only Links, and the Plan heading landed bare in
     the next cell. -->
Lead
:::

Links
:::
### Plan
Two seats
***
___

<!-- No closing `:::`: the row stays inside the section, unchanged. -->
Links
:::
### Plan
Two seats
