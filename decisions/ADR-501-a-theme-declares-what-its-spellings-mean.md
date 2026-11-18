# ADR-501: A theme declares what its spellings mean, and agents learn it only through `guide`

**Status:** active
**Domain:** skills
**Read when:** you teach, draw or serve an element variant (`*⭐*`, `` ***`x`*** ``,
`~~[x](/y)~~`); write a theme's `MEANINGS.md` or patterns; change what `guide` serves; or
wonder why an agent writes only bare elements for some theme.

## Decision

### A variant means what is declared

**The agent shapes Markdown; it never designs.** Choosing a variant by how it looks is design,
so the agent chooses by **meaning**, from a declared list.

- **Every variant's meaning is declared in `MEANINGS.md`, beside `THEME.md`.** A `MEANINGS.md`
  belongs to one theme, as its `THEME.md` does. The root `MEANINGS.md` is the default theme's
  (the **defaults**).
- **A theme uses the defaults only by choice.** Its file then starts `Extends: defaults` and
  changes them row by row: the same spelling replaces a row, a new row adds one, and a meaning
  of `—` removes one. A theme with no file declares no meanings.
- **Undeclared means unused.** An agent writes only declared spellings, and writes everything
  else bare. Bare is always correct: every element has a Primary, every theme draws it, and it
  is the ordinary case, never a degraded one.
- **`~~…~~` is the one muted state** for every element and variant: inactive, unavailable,
  past. It is never declared per variant.
- **A pattern may declare the spellings its own shape needs** in a `| Write | Means |` table,
  and `check` accepts them in any answer. A spelling meant to hold across answers belongs in
  `MEANINGS.md`. `check` cannot reliably tell which pattern a section follows, so the scope is
  not enforced per shape.
- **The format is a table per element, spelling first.** The exact text the agent will write
  sits first in each row. The headings and columns are `MEANINGS.md`'s own author comment and
  `meanings.py`'s.
- **Agents are served meaning and place, never design.**
  - *Means* says what a spelling is for and where it goes. It never gives a colour, a size or a
    measurement: size words led agents to the wrong size.
  - *Size* is optional and only for the theme lint, which compares it with what `THEME.md`
    draws.
  - *Slot* is optional and only for code. It is a key from a closed list (`meanings.SLOTS`)
    saying where a spelling goes, so code that reads the contract keys on the slot, never on
    the words of *Means*. Matching phrases in *Means* broke silently whenever a row was
    reworded.
  - A pin the agent cannot act on is declared `decoration`, so the lint knows it is meant, and
    it is never served.

### The theme's vocabulary reaches agents through `guide`, and nowhere else

- **Three layers, each complementing the one before:**
  1. `skills/`, the general layer, for any theme;
  2. theme patterns, the theme author's purpose and shape: `<theme dir>/patterns/*.md`,
     in the format of `skills/patterns/`;
  3. the digest: the theme's declared meanings.
- **Patterns and meanings sit beside `THEME.md`, never inside it.** `THEME.md` is the
  frontend's drawing input. Guidance for agents never enters that payload.
- **Both MCP shells serve them through `guide`, with no extra tool.**
  - `guide("patterns")` lists the theme's patterns after md2ui's.
  - `guide("theme/<name>")` reads one. The prefix is reserved, so a theme pattern never
    shadows one of md2ui's.
  - `guide("theme")` returns the digest.
  - The whole `THEME.md` stays a resource, and `guide` never points at it.
- **A theme pattern is a reference, not a template.** It guides an agent whose data has that
  shape, and never makes it trim or invent content (ADR-500).
- **Every served example is a real document.** A theme pattern whose example fails `check`
  against its theme is left out and logged (`theme_lint.served_patterns`).
- **Pins are global by token, never one item's state.** The digest says so.

## Why

- **Meanings an agent cannot see do not work.** Taught variants as looks, each theme author gave
  the same wrappers their own meanings, invisible to agents. Agents then either ignored
  variants or used all of them.
- **A closed, declared list removes the design decision from the agent.** The question is
  never "which looks right" but "which of these few meanings is this", and the answer is a
  table lookup.
- **Spelling-first tables are the cheapest form for a model to apply.** One fact per row,
  nothing to interpret, and an absent row is an explicit "no".
- **One muted spelling across all elements** is one fact instead of five.
- **Patterns are the form agents already read well**: short, indexed, loaded one at a time,
  showing a shape. Serving the theme's through the same `guide` keeps one way to learn. The
  raw `THEME.md` was reachable but not findable, long, and silent about purpose.

## Constraint created

- `skills/` teaches roles and the base contract. It never teaches a variant as a look, and
  never a meaning the contract does not declare.
- **A declared row must draw distinctly with its theme.** The theme lint (`theme_lint.py`)
  reports, when the theme loads:
  - two declared spellings that draw the same;
  - a size order that contradicts a meaning;
  - a pin with no `## Fixed colours` row;
  - a slot outside the list, or buttons with no main card or row slot.
- **The default `MEANINGS.md` and the default `THEME.md` move together.**
- **Emoji `_` stays a synonym of `*`.**
- **`guide` is the only door.** Guidance that is neither a pattern nor in the digest does not
  reach agents; a comment in `THEME.md` does not.
- When a theme lacks something, the agent still writes the meaning: the answer is correct and
  only looks the same.

## Considered and rejected

- **Deriving meanings from the theme's styles** (bigger means emphasis, red means danger). That
  is the design judgement this decision removes, and it guesses the author's intent.
- **Every variant usable by default.** Agents put chips everywhere, and nobody had declared what
  the variants mean.
- **Per-variant muted spellings.** Rejected for consistency.
- **Meanings or a `Use:` key inside `THEME.md`.** `THEME.md` is the frontend's drawing input,
  and a key pointing into md2ui's pattern list cannot say what a style is for in the theme's
  domain. Do not re-propose it.
- **Prose rules instead of tables.** A model reads "use the large icon for features" as a style
  hint; a table row reads as a definition.
- **A dedicated `theme` tool.** A second way to learn beside `guide`, for what `guide` already
  shapes.
- **Agents supplementing a theme per answer.** It would make an answer more than Markdown, need
  every client to support it, and hide the gap from the theme author.

## Reconsider when

- Agents write undeclared spellings anyway, ignore declared ones, or do not use theme patterns
  they were offered.
- A host lets the agent see the rendered result and correct itself. A visual choice may then be
  safe to hand back.
- A host can show agents a theme's own documentation natively, without `guide`.
