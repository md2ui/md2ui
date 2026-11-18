# ADR-302: Stack sections trust the content ask; they do not verify the arrangement

**Status:** active
**Domain:** layout generator
**Read when:** changing how `Stack sections` sizes a block (`_block_width` in
`layout_generator.py`), or tempted to add a verify-by-rebuild step back.

## Decision

A packing candidate's width is its **content ask**: the larger of the block measurer's
reading of its full-width build (the longest row of text boxes, gaps and paddings included)
and `_run_min_width` (its widest same-kind run on one line). That number is used as it is.
The block is **not** rebuilt at that width to check that its arrangement survives, and there
is no search for the narrowest width that keeps it.

## Reason

The check was the most expensive thing left in the generator: every block whose ask failed it
was rebuilt and then bisected, about a quarter of `generate()`. Without it, pages pack denser
and shorter, and no text overflows, because the ask already covers every text row. Compared
on rendered previews, the denser packing was preferred.

## Cost accepted

The ask is about text, and some arrangements floor themselves above their text: a grid sizes
a card by its length **category**. So a grid inside a packed band can use one column fewer
than it would across the whole line. A short packed card also stretches to its tallest
neighbour, leaving empty space at its foot. `THEME_GUIDE.md` and `skills/` describe the first
as behaviour.

## Alternatives rejected

- A pixel **tolerance** on the bisection: no gain once card heights were bucketed.
- A **direct threshold** from `_flow_rows`' own batch widths: rarely usable. Widths shrink by
  ratio through nested packing, not by an offset, so a flow's numbers do not predict where the
  whole block breaks.

## Reconsider when

A column dropped inside a packed band is reported as wrong. The first step back is partial:
re-check only **grid column counts**. Most blocks the old check caught failed on a flowed row
wrapping, not on a grid losing a column, and the wraps are where the denser packing comes
from.
