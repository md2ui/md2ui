# ADR-409: A card is never painted; a box comes from a heading style

**Status:** active
**Domain:** renderer
**Read when:** you are about to give `### Elements` a fill, stroke, radius or shadow again, or
add a per-level switch for card drawing.

## Decision

A glued-content card (the `### Elements` block) is laid out and never painted. The block keeps
its padding, spacing and other layout keys; the parser ignores every paint key there
(background colour, image and gradient, stroke, corner radius, shadows, colour rotation). A box
around content comes from a heading style: `### Heading N` or a fixed style. Card padding
applies wherever a card is wrapped.

Lists, quotes, Image Cards, tables, chips, buttons and badges paint as usual. A photo card with
no `### Image Cards` block falls back to `### Elements`, so it draws its photo with the card
padding and nothing else.

## Reason

- **Two ways to make a box were confusing.** A card painted where its section did not, and a
  per-level switch existed only to stop a card painting a second box inside a section that
  already painted one; the default theme turned it off everywhere.
- **The switch also hid padding, and the generator did not know it.** The generator's unit
  padding (`generator_units._unit_padding_x`) added the Elements padding regardless, while the
  renderer left it out wherever the switch was off. With no switch, the two agree (ADR-400).

## Alternatives rejected

- **Keep the switch as a padding switch.** It would keep every render unchanged, but a switch
  named for drawing would gate nothing that draws.
