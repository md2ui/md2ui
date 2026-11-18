# ADR-410: Matching pieces of the cards in a grid row share one height

**Status:** active
**Domain:** renderer
**Read when:** cards side by side have pieces that line up (or should and do not), a piece sits
higher in its slot than its own height explains, or you are looking at `render_slots`.

## Decision

In a grid row (cards of one run side by side), the piece at the same place in every card is
the same element, and it takes the tallest of their heights. The piece keeps the top of its
slot and the gap opens under it, so a subtitle, a picture, a text and a button line up with
their twins when one card's title wraps to two lines and the others' do not.

- **Per row, not per run.** Only the cards of one row share; a long title two rows up does not
  stretch every card of the run.
- **Matched by place.** Cards share only when each stacks the same number of pieces, of the
  same layout kinds in the same order. Cards that differ by a piece keep their own heights.
- **Not the last piece, not a picture.** The last piece has nothing below it to align; a piece
  that is or holds a picture keeps its own height, which is the picture's ratio: lifted, the
  photo would draw taller than authored.
- **Measured once, read twice.** `render_measure.natural_height` lifts a piece to its slot
  (`render_slots.lift`), so measuring and placing agree (ADR-400). The slots are per width
  (ADR-401): a row shares again whenever it is laid out, and a scene build clears them.

## Reason

Cards of a run are stretched to one height, but each stacked its pieces from the top, so the
slack collected under the shortest content and the twins drifted apart. A run reads as a run
when its repeated parts line up across a row.

The settling is a poll over a run's members, as ADR-301's are, but it lives in the renderer:
the generator's measurements are bucketed on purpose and cannot give exact heights. The cards
being one run's members is what makes a place in one card the same element as that place in
the next.

## Alternatives rejected

- **Sharing across the whole run.** Far more rows grow, by much more, for alignment the reader
  never compares: the row is the unit read across.

## Constraint created

- A piece's height inside a grid card is `max(own, slot)`, never less than its own.
- Code that measures a card in a grid row must go through `natural_height`, or it will see the
  piece's own height and disagree with placement.

## Reconsider when

- Cards of one run commonly differ by a piece (a badge on some cards only): pairing by place
  skips those rows today; matching by the grouper's piece identity would cover them.
- Nested pieces (a title over a caption inside one piece) should line up too: today only a
  card's top-level pieces share.
