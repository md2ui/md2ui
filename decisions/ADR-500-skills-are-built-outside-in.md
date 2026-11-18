# ADR-500: `skills/` is built from the outside in, and never trades content for looks

**Status:** active
**Domain:** skills
**Read when:** writing or changing anything in `skills/`, or before a change that decides what
a document *becomes*: a grouping rule, a layout decision, a theme key. Nothing in the code
states this intent, and several plausible "improvements" violate it.

## Decision

**`skills/` teaches an LLM to author Markdown that renders well, without letting it read this
codebase.** An author who has read the pipeline writes to the pipeline rather than to the
format, and the result stops generalising. Its content comes from LLMs' own attempts and the
problems they hit, validated by a human.

**A document's content is never reduced to improve its appearance.** The job is to format what
*can* be formatted without discarding anything. How much information appears is the author's
decision, not the renderer's and not the model's.

## Why

Nothing in the code expresses either rule, and each has an obvious-looking violation available
at all times: dropping a node that does not fit, collapsing a run to tidy a layout,
"simplifying" a response so a rule applies cleanly. A layout that improves by showing less
looks better in a screenshot and is worse at the job.

## How `skills/` speaks

- **A note informs; it never instructs.** Agents copy what they read as if it were mandatory.
  So a note says what a construct does and what that costs ("button text does not wrap, so a
  long label makes a wide card"), and the author decides from the content in front of it.
  Nothing is prohibited.
- **Alternatives side by side.** Where several spellings fit, the note shows them together and
  says what each gives. Patterns are references, not templates.
- **Written for cost.** The notes are read in full on every answer. So what changes most
  answers comes first, each fact lives in one place, and a note that is never reached does no
  work. An agent's account of what it missed is evidence about order and phrasing before it
  is a request for more text.
- **A production surface.** Measurements, provenance and the history of how a note was reached
  stay out of `skills/`: an agent reading the notes pays for every line.
- **What md2ui can do, never what it cannot.** A limit an agent reads becomes a reason not to
  try.
- **An edit to `skills/` is a product change**, made with the same care (ADR-502).

## Constraint created

- When a document cannot be laid out well, the answer is a better rule, a theme key, or
  guidance in `skills/`. It is never less content.
- A limitation an LLM reports is not automatically a defect. Some are correct behaviour that
  the author needed to be taught instead, and deciding which is a human call.

## Reconsider when

The outside-in method is a working assumption and can be revisited on evidence. The content
rule is not up for revision.
