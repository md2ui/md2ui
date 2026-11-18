# ADR-301: New decision sources vote into the run poll; they never bypass it

**Status:** active
**Domain:** layout generator
**Read when:** adding a new source of layout or render decisions — a URL parameter, a theme
key, a fit rule — that applies to a node inside a repeated run.

## Decision

Every decision source **votes into** the run's poll; no source writes a per-node result that
skips it. Render hints are polled in `_unify_run` / `_unify_run_render` in
`layout_generator.py`; fit decisions (wraps, spacers) in `generator_fit_votes.py`.

Today's voters:

- **URL params** (`?md2ui.*`). Only annotated members vote, so annotating one card of a run
  styles every card; a conflict between annotated members resolves by majority, with a
  warning.
- **The theme's `Emoji aside`.** When the theme asks any member for an icon gutter, every
  member takes one.
- **The fit votes:**
  - *One wraps, all wrap.* A line, or a weighted `:::` row, that wraps before a piece makes
    every member's same line wrap there. Column counts never move.
  - *A run's spacers give way together.* The generator settles it per run and pins it on
    each row (`render_properties["spacers"]`); the renderer obeys the pin instead of deciding
    card by card.
  - *Sibling lines.* A run of same-kind lines stacked one per row opens a poll of its own
    that carries only the wrap vote. Lines made only of links, chips or emoji wrap as words do
    and cast nothing. A line inside a grid member votes in both its sibling-lines poll and the
    innermost grid poll, obeys the union of their pins, and casts a wrap pinned by one as its
    vote in the other, so a card's lines carry a wrap to its twins. Separate grid runs never
    outvote each other.

## Reason

Members of a repeated run must be laid out identically — that is what makes a run a run. The
poll is the single place that guarantees it. A source that writes directly to one node
produces a run whose members disagree, and the symptom is a visually broken grid far from the
code that caused it.

Priority between sources is a separate question, resolved *inside* the poll where it is
visible, rather than by who wrote last.

## Constraint created

A new source needs a vote with a stated precedence, not a write. A disagreement costs one
rebuild of its run per width; that is the accepted price of consistency.

## Reconsider when

A property is provably per-node and never shared across a run. Those exist, but the burden is
to show it, because most render properties turn out to be shared.
