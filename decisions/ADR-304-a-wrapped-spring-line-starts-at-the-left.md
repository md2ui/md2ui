# ADR-304: A wrapped spring line starts at the left, and its end wraps first

**Status:** active
**Domain:** layout generator
**Read when:** a `...` line wraps and a piece lands somewhere you did not expect, or you are
looking at `generator_spring_wrap` or the spring branch of `LayoutGenerator._flow_line_group`.

## Decision

While a spring line fits, every piece sits where it was written: the first at the left edge,
the last at the right, any between them centred. When the line wraps (decided by the flow and
the run's wrap vote, ADR-301), `generator_spring_wrap.rewrap` settles the pieces:

- **A right piece alone on a later line starts at the left.** `A ... B` that wraps puts B
  under A, left-aligned. A right piece that still shares its line keeps its spring.
- **A centred piece stays centred,** alone or not (`A ... B ...`, and A in `... A ... B`).
- **In `A ... B ... C` the end wraps first.** C takes a line of its own, at the left, and A
  and B keep the first line. When A and B cannot share it either, every piece takes a line of
  its own in the order written: A, then B centred, then C at the left.
- **A run decides together.** Whether the middle left the first line is one more fit vote, so
  the members of a run take one piece per line together or not at all.

## Reason

A piece pushed right by its spring has nothing to push from once it is alone on its line;
right-aligned under a left-aligned title it reads as stranded (a price at the right edge under
its dish name). Starting at the left, it reads as the next line of the same item.

## Alternatives rejected

- **Break the middle first in `A ... B ... C`,** so A and C keep one line. In agent answers
  the middle is most often a lone icon, the "from → to" connector the skills teach
  (`__Lisbon__ ... 🚆 ... __Porto__`); moving it below its two values broke that reading, and
  could change a card's height enough for the bento solve to repack the page. Wrapping the end
  first keeps the connector beside the value it leads from.

## Constraint created

- The rule lives where the wrap is decided, in the generator, and writes the piece's
  `content_align`; the renderer only obeys it. Nothing re-decides alignment per frame or in
  the renderer.
- A line that fits is never reflowed: the run's shared spring columns pair regions by
  position, and reordering a fitting line would hand one region another's column.

## Reconsider when

- A theme needs a wrapped right piece to stay right; that would be a theme key, not a change
  to the default.
- Agents start writing three-region lines whose middle should lead on narrow screens.
