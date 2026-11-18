# Empty table cells hold their column

An empty cell is not an absent cell: a row is laid out by cell order, so a dropped
one renumbers every column after it. These tables all have three columns in every
row, and the headers must stay over the values beneath them.

## Empty corner header

|  | A | B |
|---|---|---|
| Weight | 1 kg | 2 kg |

## Empty cell in a body row

| Spec | A | B |
|---|---|---|
| Weight |  | 2 kg |

## Alignment travels with the cell

|  | Left | Right |
|:---|:---|---:|
| Weight | 1 kg | 2 kg |

## Empty in the middle of a header, and a trailing empty

| Spec |  | B |
|---|---|---|
| Weight | 1 kg | 2 kg |
| Depth | 4 cm |  |
