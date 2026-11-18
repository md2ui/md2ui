---
name: md2ui-colour
description: Which colour an element gets — a theme's cycle by position, a glyph that names the item, a pin on a token, a named style.
---

# What you decide about colour

Every colour is the theme's. But four things in your Markdown decide *which* colour an
element gets, and three of them are easy to disturb without noticing.

**Position, when the theme deals a cycle.** A theme can give a style a list of colours
instead of one, and then siblings take them in turn, in document order. A cycle **restarts
inside every heading section**, so two boards of cards each begin at the first colour with
nothing asked for — and inserting, removing or reordering a section recolours everything
after it. A section lends its slot to its own title, so a card's heading follows its card.

**The glyph names the item; the theme colours it.** Where a run of items each carry a badge,
give each the glyph that means it: the cycle colours the run by position whatever the glyphs
are, so a different glyph never costs the run its colours. Varying the glyph does not choose a
colour, so never pick one for its colour, and never repeat one placeholder glyph to get a
uniform look.

**A pin keys on a token you wrote.** For a colour that carries meaning — up and down, done
and failed — a theme pins it to the thing that means it: a glyph, the sign of a delta, or a
glyph inside a chip. **`guide("theme")` lists the tokens this theme pins and what each
means: write those.** A pin can never key on the number, which changes every render. So write
the direction as one of those tokens rather than as a word,
put the glyph inside the chip when the chip is what should colour, and keep the glyph on the
line it should reach — a pin can be scoped to the glyph alone, to the value beside it, or to
the whole run it sits in. A pin reaches **every** place its token appears, so it carries what
the token always means, never one item's state: the state of one item is its wrapper.

**`{#name-1}` asks for one specific style.** A heading id in lowercase kebab-case ending in a
number selects a named style the theme defines — `## Premium {#premium-1}`, as in
[`banking-example.md`](banking-example.md). It is how you say "this card, not the one the
cycle would have dealt it" — and more than colour: a named style is a whole card look, so it is
also how two kinds of card share one heading level. Reuse the name with a new number for each
card of that kind (`{#feature-1}`, `{#feature-2}`). Leave the number off an id that is only a scroll target
([`elements.md`](elements.md)).
A named style changes the look only. Two boards of the same card shape still share one column
count; to grid them separately, put one at another heading level ([`repetition.md`](repetition.md)).
