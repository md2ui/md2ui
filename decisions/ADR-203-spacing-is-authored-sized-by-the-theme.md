# ADR-203: Blank space is authored in the Markdown and sized by the theme

**Status:** active
**Domain:** markdown grouper
**Read when:** you want extra room somewhere a gap key cannot reach, or you are
about to add a theme key that reserves space on its own.

## Decision

1. **`+++` / `++++` / `+++++` is a spacer**: small / medium / large. Any other
   count of `+` is text, and `\+` declines it.
2. **A spacer is an empty leaf of fixed length along ONE axis**, sitting in the
   container it is written in, like any other piece:
   - alone on a line it is **vertical** — it pushes what follows down;
   - written inside a container — a card's body, a list item's lines — it
     stays in that container: after a section's body it is that section's;
   - spaced inside a line (` +++ `, or leading / trailing: `+++ B`, `B +++`)
     it is **horizontal** — it pushes what follows right.
3. **The Markdown names a step; the theme gives it px.** `Spacer small`,
   `Spacer medium`, `Spacer large`, with `row` / `col` overrides, resolved at
   the nearest surface that states it: `### Image Cards` for a spacer in a
   photo card, then the owning heading level, then `### Root`. Levels do not
   inherit from one another. When none states it, the step is a multiple of the
   group gap, never below a fixed floor, so a spacer never vanishes in a theme
   with no gaps.
4. **A spacer is spaced as a leaf.** The gap system treats it like any other
   element: the gap applies on each side of it, and the spacer adds its own size
   in between.
5. **A spacer is invisible to structure.** A document groups exactly as it
   would without its spacers — the same nodes, fingerprints, `kind_hash` and
   runs — plus SPACER leaves where they were written (`grouper_spacers`): the
   spacers go in after every grouping decision, so none can wrap, unglue or
   collapse anything. The fingerprint and the generator's passthrough silence
   them, as styling is silenced ([ADR-201](ADR-201-styling-is-not-structure.md)).
6. **A horizontal spacer exists only between side-by-side neighbours, and gives
   way first.** Where a flowed line wraps at it, it is dropped; it is never
   converted into vertical space. A row short of room shrinks its spacers before
   its content, so a spacer never widens the page's minimum or squeezes what it
   stands beside. Consecutive spacers are one spacer of their summed size. A
   spring can open room around a spacer, never take it away; ` : ` binds before
   it.
7. **An image card's own picture params size it.** An `aspect_ratio` on the
   card's URL gives the card a height at its width, capped by `max_height`;
   content that needs more room wins. The ratio never takes part in arranging:
   the columns are chosen from the card's content, and the ratio sizes the card in
   the column it was given. The spare height grows the card's first `+++++`, or,
   with none, goes above the content.

## Reason

Where space goes must not be a generator guess. A theme key that reserves space
on its own has to decide which node it belongs to, and gets that wrong for some
way of writing the same content, with no lever for the author. Writing the space
where it belongs removes the guess; naming a step rather than a pixel value keeps
sizes consistent across a document, keeps the wire free of theme values
([ADR-601](ADR-601-the-wire-carries-markdown-and-references.md)), and is a choice
an LLM author makes reliably.

Px on one axis, not a width-relative ratio: a spacer that cannot change with the
grid's column count is one an author can predict.

## Constraint created

- **No theme key reserves space on its own.** Room that is not a gap is written
  in the document as a spacer; a photo card's room is a `+++++` sized under
  `### Image Cards`. An image card's ratio (rule 7) is written on the card's own
  URL, so it is authored, not guessed.
- **Space between sections is written `***` then `+++`.** A spacer after a
  section's body belongs to that section by rule 2; `***` ends the section
  first, so the spacer sits between the runs, which then form two grids.
- **Open:** what a spacer between two cells of ONE grid means.
- **A document with spacers is grouped twice.** The cost falls only on
  documents that use them.

## Considered and deferred

- **A ratio spacer, `+W:H+`** — width-relative space on its own line, the shape
  of an image with no image. Deferred: a ratio grows with its container without
  bound (an image has `max_width`; a spacer would need its own cap), and it is
  only worth adding if px spacers turn out not to cover real cases.
