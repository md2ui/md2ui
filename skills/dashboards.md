---
name: md2ui-dashboards
description: Composing a dashboard-style answer in md2ui — the card recipe, the two-column row, stat lines, bars and charts, and what a mosaic will and will not do.
---

# Dashboards: composing cards, rows and figures

The most demanding thing an LLM answer gets rendered as. It is reachable, and it is mostly
four constructs used together.

## Start with a complete example

The [banking authoring example](banking-example.md) includes the complete Markdown. It
demonstrates account sections,
a gradient premium card, a transaction list with muted dates, and a separate summary
band. Read it before combining the individual recipes below into a whole page.

Its layout is part of the example: the account sections sit side by side at 1600 and stack
at 767; the summary is four columns at 1600 and two at 767. The recipe preserves content ownership and
styling as the available width changes. A row that fits the page
may wrap inside a narrower mosaic cell; check the composition at its actual width.

## The card recipe

One `##` section is one card. This shape works:

```md
## Total Spendings ... [`📋`](/copy) [`…`](/more)

Overview of your monthly expenses at a glance.

---

___$15,830.32___ - ⬆️ 5.9% - vs. Last week ... `This Week`

- Mon: 49%
- Tue: 78%
- Wed: 61%
```

Line by line, and each line is doing one job:

| line | construct | gives |
|---|---|---|
| `## Title ... [icons]` | a **spring** | title left, actions hard right |
| description | plain text | the caption under the title |
| `---` | the **drawn rule** | the hairline under the header |
| `___$x___ - ⬆️ 5.9% - … ... \`chip\`` | display tier + separators + spring | the big stat, its delta, and a period chip at the right edge |
| `- Key: value` run | a **chart** | bars, from three or more rows in one unit |

**For the rule under a header, use `---`.** `___` paints nothing — it is the run cut, the
thing that stops a band of same-shaped cards gridding ([`repetition.md`](repetition.md)). This
is the single easiest way to lose the rule under a card header, because `___` renders as a
divider in every other Markdown tool. Write both, `---` then `___`, when you want a rule you
can see that also separates.

## The two-column row

The row that makes a transaction list, a leaderboard, a line-item table. One line:

```md
- *🛍️* - **Streaming Subscription** : February 04, 9:17 PM ... `-$199.00` : Subscription
```

Three constructs composing, and the order they resolve in matters:

1. **`...` splits first** into a left region and a right region;
2. **` : ` binds tighter**, so each region stacks into two lines;
3. **`*🛍️* - `** is a separated emoji, so it draws as a badge rather than an inline glyph.

Result: badge, name over date, pushed apart, amount over category. That is the whole row.

**The emoji needs its separator.** `*🛍️* **Name**` with no ` - ` leaves the emoji as inline
text at body size. See [`elements.md`](elements.md) — separation is what makes an element.

## A row with a coloured gutter

An agenda, a timeline, a task list, a "what changed" list — anywhere a row wants a coloured
rule, a token or a tint. The Markdown is an ordinary quote or list. Whether a bar, a token or a
tint is drawn is the theme's; without it the rows render as a plain quote or a plain list.

**A rule per row — one blockquote per row:**

```md
> 4:00 PM - Finish packing

> 6:00 PM - Drop off keys

> 6:30 PM - Leave for airport
```

The blank lines are the whole construct: consecutive `>` lines are one quote and share one
bar down the side, while blank-separated ones get a bar each. Both shapes are useful — one bar
for "this block is quoted", a bar per row for a timeline. See
[`structure.md`](structure.md).

A ` - ` inside each row gives the "time, then title" pair.

**A token per row — an ordinary list:**

```md
- 4:00 PM ... Finish packing
- 6:00 PM ... Drop off keys
```

`1.` items are the same idea, with the ordinal as the token.

**A tinted row — an ordinary list:**

```md
- 9:00 AM ... Team Standup
- 10:00 AM ... 1:1 with Emily
- 12:30 PM ... Client Meeting
```

The ` ... ` keeps each item one row, time left and title right; a list item that ` - `
divides is a group, and a run of them grids as tiles ([`repetition.md`](repetition.md)).

A theme's tints are dealt per item and restart inside each section, so a second card tints the
same way with nothing added. Reach for these when a row wants a **fill** rather than a marker
beside it — an agenda, an alternating list, a status row.

An agenda usually wants a date above its rows, and that is a day chip: write `Mon-15`
(see *Stats, bars and charts*). Card, date header and rows are then a
handful of lines with nothing marked up.

Reach for these whenever a row should read as its own thing — it is the cheapest way
to make a list of rows look designed, and it needs nothing in the markdown but the `> ` or
the `- `. All three spellings side by side: `renders/gutter-rows-900.png`.

## Stats, bars and charts

- **A big number**: `___$847M___` — the Display tier. Wrapping the whole leaf is what
  picks the tier; a wrapper inside a sentence is just emphasis.
- **A stat with a delta**: separate the parts — `___$847M___ - ⬆️ 12% - vs. Q3 2023`.
- **A day tile**: `Mon-15` — or `Jun-15` — draws as a day chip, the weekday or month
  uppercased above the number. That is the whole calendar-widget header: one word of
  markdown, no emphasis wrappers.
  **The dash is the request.** `Mon 15` is how a sentence writes a date, so it stays text;
  the chip is spelled `Mon-15`, and `Mon\-15` declines even that.

### Which figure each spelling draws

**The spelling picks the figure, not the data.** The same numbers written two ways draw two
different figures, and the theme styles each figure separately. Every row below is shown
in `renders/chart-spellings-900.png`.

| you write | it draws | what makes it that figure |
|---|---|---|
| `Elapsed: 45%` | a **progress bar** under its key and value | a `Key: n%` line, the percentage alone (or with a word or two: `60% Complete`) |
| `Change: -1.55%` | the same bar, filling from the right | a signed percentage |
| `68/100` | a **ratio bar**, the number beside it | a part over a whole, alone on its line, no key |
| `Disk: 61/128 GB` · `Disk (GB): 61/128` · `Files: 3/10` | a **ring** filled to the share, the unit under the number — or the key, when the ratio has no unit | a part over a whole with a unit or a key |
| `- Mon: 40%` ×3 or more | a **bar chart**, one bar per item | list items in one unit, each value alone |
| `Storage (GB):` over `- Photos: 61` ×3 or more | a **bar chart** of bare numbers | the unit declared on the line directly above |
| `Revenue, Cost:` over `- Q1: $10K, $8K` ×2 or more | a **grouped bar chart**: one bar per series in every row, and a legend | a header naming as many series as each row has values |
| `SPY: $710 → $713 → $777` · `High (°C): 24 → 23 → 21` | a **line**, the key and last value above it | three or more values in one unit, joined by `→`; a bare number's unit declared in the key |
| `- SPY: $710 → $756 → $767` ×2 or more | **several lines on one axis**, under a legend of each name and its last value | list items, each a line, with the same number of points in one unit |

**A chart value is a number.** Bar charts and lines take the same values: a number written as
`40%`, as a currency (`$220.06`, `200 EUR`) or with a K/M/B (`5K`, `$274.5B`) stands alone.
**Every other value is a bare number with its unit declared once** — on the line above a bar
chart's rows, or in a line's key. That includes plain counts and every other unit: `61 GB`,
`12 kg` and `24°C` written in a row keep it out of the chart. Each value is drawn as you wrote
it, and signed values draw gains and losses from zero:

```md
Temperature (°C):
- Wed: 24
- Thu: 23
- Fri: 21
```

Orientation is the renderer's, not yours: four rows or fewer draw horizontal bars with the
label and value above each bar; five or more, given room, stand vertical with labels beneath.

**A grouped bar chart** compares several measures across the same items. The header line
names the series, comma-separated, and each row lists one value per series in that order:

```md
Revenue, Cost:
- Q1: $10K, $8K
- Q2: $12K, $9K
- Q3: $15K, $11K
```

The header becomes the legend. All values share one unit; for bare numbers, declare it in the
header: `High, Low (°C):`.

**A line** is one value over time. A `(label)` right after a value names that point —
words, a date, a time, a quarter or a year: `(May)`, `(Q1)`, `(FY2025)`, `(6 PM)`. A label
holds a name, not a second value: `$412M (49%)` keeps the line as text:

```md
SPY: $710.14 (Apr 13) → $713.94 → $720.65 → $737.62 (May) → $777.24 (Now)
High (°C): 24 (Wed) → 23 (Thu) → 21 (Fri)
```

The second declares its unit in the key, for bare numbers.

**Several lines on one axis** compare a few things over the same steps. Write each line as a
list item; the keys name the lines, and the legend shows each name with its last value:

```md
- SPY: $718.66 (Apr) → $756.48 (May) → $746.77 (Jun) → $767.87 (Oct)
- QQQ: $667.74 → $738.31 → $736.40 → $728.08
- DIA: $496.65 → $510.78 → $522.39 → $513.86
```

Every line has the same number of points, in one unit, and a label on any line names that
position for all of them. For bare numbers, declare the unit once above the list, as for a bar
chart: `Price (USD):`. The axis is shared, so the lines show which is higher as well as how
each moved.

### Near misses

Each of these is one character or one line away from a figure, and draws something else:

| written | draws | because |
|---|---|---|
| `Mon: 40%` on three lines, no `- ` | three separate progress bars | a chart is made of list items |
| two `- Key: n%` items | two progress bars | a single-series chart needs three rows |
| `- Port: 8080` ×3 | a plain list | a bare number charts only under a declared unit |
| `- Photos: 61 GB` ×3 | a plain list | `GB` is not written in a row; declare it: `Storage (GB):` above bare numbers |
| `Users: 900 → 1.2K → 5K` | text | a bare number in a line needs its unit in the key: `Users (count):` |
| `- Mon: 40% (holiday)` among chart rows | that row leaves the chart | a chart row is the value alone; move the words into the key |
| `- Q1: $10K, $8K` with no header line | a plain list | a grouped chart needs its series named above it |
| `Storage (GB):` or `Sales, Profit:`, a blank line, then the rows | a plain list | a header declares only the rows right under it; a blank line ends it |
| `Price: $10 → $12` | text | two values are a before-and-after, not a line |
| `Price: $10 -> $12 -> $14` | text | only `→` joins a line |
| `SPY: …` and `QQQ: …` on lines of their own, no `- ` | separate lines, each with its own axis | lines share an axis when they are list items |
| `- SPY:` 7 points, `- QQQ:` 6 points | separate lines | lines on one axis have the same number of points |
| `- SPY: … (Apr)` and `- QQQ: … (April)` at the same point | separate lines | two labels for one position; label it once, on any line |
| `3/10` and `Files: 3/10` | a ratio bar, then a ring | the key turns a ratio bar into a ring |

`md2ui check` names a row that left its chart, a `→` chain that drew no line, and a header a
blank line kept from its rows, with the reason.

**A value that draws when you wanted text is declined in the document**, one instance at a
time: do not separate the value, or escape its punctuation (see
[`structure.md`](structure.md)). Before declining, check the drawing is not the very thing you
were about to hand-build — `Mon-15` is a calendar header, not a mistake.

## A hero number and a stat footer, on the same card

An **authored** hero (`___53min___`) and a supporting pair (`_Duration_` over `08:21`) are
styled independently, which is what lets one card carry both. So write the two or three
numbers that should shout as `___x___`, and the supporting figures as plain values under
their muted labels.

## Value runs: choose their text role

A repeated list of pairs shares one treatment when each pair is written alike. Authored
tiers and the drawn families keep their own. See [`text.md`](text.md) for labels over their
values and the authored `Muted` / `Lead` / `Display` tiers.

Choose chips such as `` `47,000` `` and `` `+15%` `` for pill styling. Choose `___…___`
for an authored hero figure. Wrapping a backtick chip in emphasis selects a chip variant;
it does not select `Display`.

## The mosaic

When the theme turns on Bento, it tiles one heading level into a mosaic: the shallowest level
with three or more sections in a row. Each section stays whole, its heading full width above its
body. The arrangement is solved from what the cards contain, not authored, so if one comes back
wrong, change a card, not the layout.

Every card's minimum width (a wide table, a long unbreakable string, a wide image) constrains
the solve for all the others. The mosaic aims at about 260px per column, so a wider page buys
more columns, not wider cards, and nothing widens one cell: **the way to give a card room is
to write fewer cards.** The same document packs differently at each width.

- **Keep minimums small** unless the content needs the room: short lines, wrapped copy and
  chips leave the mosaic solvable.
- **Do not add width to get a layout.** It constrains the solve rather than steering it.
- **Write cards that read at any cell width.** Two identical cards can land at different
  widths, and a ` - `-separated stat row reflows into a stack in a narrow cell.
- **Check what needs room at the width it ships at.** A `:::` row of a picture beside text
  stacks in a narrow cell, and a `::: 1 >` divider treats that cell as narrow space; see
  [`structure.md`](structure.md).

## Checkboxes and switches

A task-list item is a drawn control. Nothing is placed and nothing is annotated:

```md
- [ ] Enable notifications
- [x] Sync over cellular
- [x]                        a bare control, no label
```

Whether they draw as checkboxes or switches is the theme's, for the whole document.

The linked spelling `[[x]](/disable)` keeps the URL as an annotation on the control instead
of turning it into a button. Exact `[ ]` / `[x]` / `[X]` tokens draw anywhere;
escaped tokens and code spans stay literal.

Where a control can sit, and how a spring places it
(`renders/task-control-spellings-900.png`):

| written | result |
|---|---|
| `- [x]` | **control**, alone in its row |
| `- WiFi [x]` | **control**, sitting left after its label |
| `[x]` on its own line | **control** |
| `... [x]` | **control**, pushed hard right by the spring |
| `WiFi ... [x]` | `WiFi` left, **control** right |
| `- ... [x]` | **control**, composed with the spring |

Use `Label ... [x]` for a settings row with the control at the far edge.

## Sliders

Use a bracketed percentage when the value is adjustable, rather than merely
reported:

```md
Volume: [65%]
Effects: [[35%]](agent:set-effects?channel=music)
```

The first is a plain slider. The linked spelling sends the same numeric value
with the server-owned `agent:` action and parameters. Keep the label before the
token so the event reads `User set "Volume" to …`. `[65%](/details)` remains an
ordinary percentage link; the extra bracket pair is intentional. Escape the
opening bracket (`\[65%]`) when the notation should remain literal.

This is distinct from `Elapsed: 65%`: the unbracketed percentage is a static
progress bar, while `[65%]` is draggable. A slider sends one event when the drag
ends, never a stream while it moves.

**For a count rather than a percentage, write the range.** `68/100` is a ratio
bar, so `[3/10]` is its draggable twin, and the denominator *is* the range:

```md
Quantity: [3/10]
Rating: [[4/5]](agent:rate)
```

The press comes back as `User set "Quantity" to 7` — no `%`, and never a value
outside 0 through 10, because the document is what says what the number means.
This is the spelling to reach for instead of `➖ 1 ➕` buttons: a stepper written
as two `agent:` links costs a turn per press, and this costs one when the user
has decided. Between ➖ and ➕, `Quantity: ➖ [2/9] ➕`, it steps by one, and a
press marked `md2ui.commit` carries it ([`elements.md`](elements.md)); write ➖
or −, since ` - ` is a separator.

**The value you write is also the precision you get back.** `[65%]` reports
whole percents and `[40.5%]` reports tenths, so write the number at the
granularity your answer actually depends on. `[3/10]` can only ever send one of
its ten steps.

## A token grid: calendars, heatmaps, seat maps

A grid of small coloured tokens is **a table whose every cell is a chip**. No drawn feature
is involved, and nothing is placed. This renders a month calendar:

```md
| Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `29` | `30` | `31` | `1` | `2` | `3` | `4` |
| `5` | `6` | `7` | `8` | `9` | `10` | `11` |
…
```

The delimiter row is where a column's alignment is set — `:---:` centers each
token under its weekday, `---:` right-aligns, `:---` left-aligns, and a plain
`---` leaves the column to whatever `Horizontal align` is in force. A token grid wants
`:---:`: the chips vary in width, and left-aligned they drift off the header.

The table gives the grid and the column alignment, the chips give the tokens, and the
header row gives the weekdays.

### Per-token state: use the chip variant, not a pin

**Author the per-token state in the cell, as a wrapper.** A theme can pin a colour to a
chip's *label*, but a label is global.

A pin sees a label, not a table, so on a page with two month grids "day 5 is active" colours
the 5 in both. A pin cannot express *this* five.

A wrapper is local to the cell that wrote it:

```md
| `19` | *`5`* | **`9`** | ***`12`*** |
```

| written | variant | state |
|---|---|---|
| `` `5` `` | Primary | default |
| `` *`5`* `` | Secondary | active |
| `` **`5`** `` | Tertiary | today |
| `` ***`5`*** `` | Quaternary | selected |
| `` _`5`_ `` / `` __`5`__ `` / `` ___`5`___ `` | Quinary / Senary / Septenary | three more |

The theme styles each variant once, so two grids keep their own states with nothing added.

**There are seven chip variants**: underscores are a second ladder, not a synonym of `*`. Spend
them on states that carry meaning — the neighbouring month's days, weekends, an event.

A label that means one thing across the whole document — a `Sold out` badge, a `⬇` trend
chip — is the one case a label pin suits.


## Before you decide something is out of scope

Ask **what plain Markdown composes into it**, not what draws it. The question sounds the
same and leads somewhere different: "what draws a calendar" has no answer, while "what
composes into a grid of coloured tokens" is a table whose cells are chips.

Each of these looks like a graphic and is plain Markdown:

| looked like a graphic | is actually |
|---|---|
| a month calendar | a table of `` `5` `` chips, state per cell |
| a toggle switch | `- [x]`, which the theme can draw as a switch |
| an agenda with a coloured bar down each row | a `> ` blockquote per row, which the theme can mark with a bar |
| a calendar header — weekday over the number | `Mon-15`, detected as a day chip |
| a row with its own tinted pill behind it | a `### ` section per row, which the theme can tint |

The tool has few primitives and they compose, so the reach is wider than any one of them
suggests. Before
concluding a result is not on offer, build it out of a table, a list, a chip run, a separator,
an emphasis wrapper and a gutter marker. Several constructs draw plainly until the user's
theme styles them — a gutter bar, a list marker, a switch — so a plain render does not mean
the construct is missing.

## Checklist

- [ ] one `##` per card, three or more of them if you want a mosaic
- [ ] `---` (not `___`) for the rule under each header
- [ ] `...` in the heading for title-left / actions-right
- [ ] every badge emoji separated with ` - `
- [ ] value runs uniform in kind, or chipped
- [ ] heroes authored as `___x___`, supporting figures under muted labels
- [ ] rows that want an accent written as `> ` per row or `- ` items
- [ ] a mosaic sized by card COUNT, not by asking for width
