# ADR-405: A choice and a count hold a value until a commit

**Status:** active (prototype)
**Domain:** renderer
**Read when:** you change how an option or a count is written, drawn, clicked, sent on the
wire or written back; or you add another target that holds a value until a
`md2ui.commit` press.

## Decision

**Two more targets hold what the user sets until a commit press carries it, as a task box
and a slider already do. Neither is a new kind of target.**

- **A choice option** is an `agent:` button with `md2ui.choice=<name>`:
  `[M](agent:size?v=m&md2ui.choice=size)`. It is the button it was, with a checked state; a
  commit sends `[ordinal, true]` in `vs` for each group's chosen option, and the written-back
  Markdown moves the main-button spelling to it (`wire_edits.choose_markdown`).
- **A count** is a ratio slider between a minus and a plus sign, `Quantity: ➖ [2/9] ➕`,
  flagged `count`: whole numbers from 0 to the denominator, written back as a slider is.
- **A choice group is named, not inferred.** The options sharing a `md2ui.choice` name, in
  the whole document, are one group; the chosen one is the option written as the main button.
  Only an `agent:` button is an option: a link, an `#anchor` or a link inside a sentence is not.
- **A choice is chosen, never cleared:** `false` for an option, or two options of one group in
  one `vs`, is refused `bad_value`. The agent hears `…, with size: "L"`; on a page without a
  commit press a tap is narrated as an ordinary tap.
- **A count is a slider between its signs.** The grouper stamps it, names it by the words
  before the minus sign (else its key or caption), and takes the two signs out of the words
  beside it. Only `➖`/`−` before and `➕`/`+` after make one; ASCII ` - ` is a dash separator.
  Its minimum is 0.
- **The look is the theme's.** A ` | ` run whose options share one name is stamped
  `segmented_run` by the grouper whatever the theme; a theme with `## Links` → `Segmented: yes`
  draws it as one segmented control (`render_segmented`). A theme that says nothing draws it as
  separate pills, the chosen one the main variant, as tabs are. The behaviour is the same either
  way. A run its row cannot hold on one line stays separate pills, as does a space-divided run.
  A count is its digits between two round buttons (`render_counts`), a sign muted at its bound.
- **The window.** A tap chooses its option and unchooses the group's others at once (a radio),
  colours only; a count's two signs are two regions of its one target, each a step of one.
- **`check`** (`check_choices.py`) refuses the spellings that cannot hold a value (the hint off
  an `agent:` button, an option or a count that commits, an option in a task row, a fractional
  count) and warns on the ones that read ambiguously (two names in one run, two main buttons in
  one group, an option in a sentence, an option spelled stronger than `*…*`, which a theme may
  paint as the main button so that none chosen reads as all chosen).

## Reason

- **The meaning is authored, not inferred.** Most pages with a commit press also have a
  same-slug run of action buttons that must stay turns; a name says which runs are choices.
- **Ordinals agree with a client that knows neither.** Each option is the button it was and a
  count is the slider it was, so a client without this counts the same targets and degrades
  to a tap per option and a drag per count.
- **No new value type.** `[o, true]` is a bool `vs` already takes; a string id would be the
  one entry that could overflow the frame's size cap, and a client-sent string.
- **Colours only (ADR-404).** A tap paints the other variant's colours in the option's own
  box; the segmented surface is paint under the pills, never a box, so the regions built per
  width stay true and no layout changes.

## Alternatives rejected

- `@choice` after the run (drawn as text, breaks the run), radio items `- (x) S` (targets an
  older client does not count), a pipe alone meaning "local" (tabs are pipe runs that must
  change the page).
- A count as `[➖] [2/1..9] [➕]` or `[➖ 2/9 ➕]` (text to older clients: targets they do not
  count); ➖ and ➕ as targets of their own.
- Segmented always, whatever the theme: a look is the theme's decision, so code does not impose
  one.

## Constraint created

- A segmented run is a grouper flag (ADR-100), `segmented_run`, stamped once on the run's group
  (`grouper_choices.is_segmented_run`). The renderer reads the flag and the host's tap and never
  re-reads a destination or a neighbour; it decides only whether the theme asks for the control
  and the run fits one row, a fact of the width.
- A count's size is the theme's (`count_size`), never the value's, so a step moves no box.
- md2ui-ts implements the same targets, the same `vs` rule and the same paint.

## Reconsider when

- A choice must be cleared, or a count needs a minimum other than 0 (a written minimum).
- An option inside a sentence should hold a choice (it would need a chosen paint for links in
  prose).
