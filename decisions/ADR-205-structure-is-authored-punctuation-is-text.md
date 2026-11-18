# ADR-205: Structure is authored; punctuation is text

**Status:** active
**Domain:** markdown grouper
**Read when:** a value, an emoji or a chip is not becoming its own node; a `Key: value` line or
a ` • ` line is not drawing as you expect; or you are about to widen what counts as a separator
or infer a pair or a run from punctuation.

## Decision

A line divides only where its **author** divided it, and md2ui never infers a pattern from
punctuation written for other reasons.

1. **The separators are ASCII ` - ` and ` | `**, spaced. Nothing else divides a line. The long
   dashes `—` `–` and the dots `•` `·` `∙` `‧` are text and draw as written: `8 days • from $659`
   is one text. An escape before them is not Markdown, so `\•` draws its backslash, as any
   renderer draws it, and `check` names it.
2. **A separator is declinable.** `\-` and `\|` keep a line whole and draw the character
   (`ESCAPABLE_SEPARATORS` in `grouper_escapes.py`). A separator always outranks a key-value
   colon: `Key: A | B` divides at its pipe, and each piece may then pair.
3. **A value never divides a line.** It stays in the leaf it was written in, carried as a
   `data_points` annotation, and never makes a line read as a RUN: `⭐ Q1 2026` is one leaf,
   `⭐ - Q1 2026` is a badge and a value. A value becomes a `DATAPOINT` node only when it is the
   whole of a piece the author already separated, or the whole line.
4. **Elements separate under the element rule.** A line peels its emoji, links and backtick
   spans into nodes only when it is a run of nothing but elements; any ordinary word beside them
   makes it prose, which keeps them inline (`_has_regular_text`). The peel's shape is
   [ADR-200](ADR-200-boundary-peel-nests.md).
5. **A colon does not make a pair.** `Key: value` is one text, drawn as written, colon kept, in
   the body style unless the author styles it (`**Key:** value` is bold where written). The
   grouper still cuts `Key: value` into a `KEY_VALUE` pair, because displays read a label and a
   value from one — a percentage bar, a ratio ring, a chart row, a line, a slider. **A pair
   survives only while a display reads it** (`grouper_pairs`): once displays are decided, a pair
   holding none becomes the line it was cut from, the same tree as its escaped twin
   `Key\: value`.
6. **A pair is composed:** the author stacks a styled label over its value — `_Key_` over
   `Value`, or `_Key_` over `__Value__`. These are the existing text tiers; nothing new is parsed.
7. **No colon is stripped.** A trailing colon is drawn (`## Ingredients:`), and so is the colon
   of a line declaring a chart's unit (`Temperature (°C):`). `Key: ... Value` keeps its colon:
   the spring sets the row and the colon is part of the left text.
8. **The spaced ` : ` stays.** A colon with a space on each side (colon columns) is a different,
   authored spelling that agents rarely write by accident.
9. **Charts read their own spelling.** `- Key: value` rows, `Key: a → b → c` lines and the
   percentage bar are display syntax, read by the display parsers
   ([ADR-204](ADR-204-a-chart-value-is-a-number.md)), not a split.
10. **A display that is switched off draws its plain text.** Every display a theme turns off
    (charts, bars, rings, chips) leaves the text the author wrote, never a substitute display.
11. **A drawing that needs sub-structure builds it in the layout generator**, from the
    display's payload — not by asking the grouper to cut prose again.

## Reason

Every inference here was a decision the author could not decline. A rule asking "is this value
flanked by whitespace?" is true inside prose all the time, and shredded sentences into pieces
and drew day chips nobody wrote. A long dash split prose sentences at every spaced dash and
could not be escaped — CommonMark escapes ASCII punctuation only. A dot split names taken from
a page (`Concha y Toro · Vino tinto`). The key-value split restyled, re-arranged and stripped
the colon of every `Label: text` sentence an agent wrote, and the authoring notes spent effort
teaching agents to dodge it.

The author already has the vocabulary: `skills/` teaches explicit separators and composed
pairs, and LLMs writing for md2ui use them. So the author composes the pattern; md2ui reads it.

## Rejected alternatives

- **md2ui's own escape for non-ASCII separators** (`\·`). It keeps a separator declinable, but
  another Markdown renderer draws the backslash, and the dot was rarely wanted as a separator at
  all. Making the dots text removed the need.
- **Inferring a pair from a colon, or a value split from whitespace.** See *Reason*.

## Constraint created

- **A new structure may not be inferred from punctuation.** It is spelled by the author, or by a
  display's own syntax that `check` can name.
- **A new separator must be CommonMark-escapable ASCII punctuation.** Adding one to
  `_LINE_SEPARATORS` without that property re-creates the problem.
- **A drawing family may not reach back into the grouper for a cut.** A family that depends on
  the grouper cutting prose stops being drawn when the cut goes, and its spelling cannot be
  declined.
- **A value type is split into its own node only if a display reads the split node.** None does,
  so no value divides a line; a value is annotated on the leaf it was written in.

## Reconsider when

An authored construct genuinely needs a cut the author cannot express. The answer is then a new
**spelling** they can write and escape, not a rule that infers one.
