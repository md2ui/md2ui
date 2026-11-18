---
name: md2ui-structure
description: How document shape becomes layout in md2ui — blank lines, heading sections, section stops, and empty heading markers. The highest-leverage file.
---

# Structure: how the document shape becomes the layout

## Blank lines decide what belongs to what

Consecutive lines with **no blank line between them** are glued into one element (a
"card"). A blank line ends it.

This is the single most common authoring bug, and it is silent:

```md
![Beauty](beauty.jpg)
## Beauty essentials
Get all your beauty needs delivered.
[Shop beauty](/beauty)
![Flowers](flowers.jpg)      ← NO blank line above: glues to the BEAUTY card
                              
## Flowers for any occasion
```

Every card ends up carrying the *next* card's image, and the first carries none. Rendered,
it looks like the images are randomly offset by one. Put a blank line before each block
that starts something new:

```md
![Beauty](beauty.jpg)
## Beauty essentials
Get all your beauty needs delivered.
[Shop beauty](/beauty)

![Flowers](flowers.jpg)
## Flowers for any occasion
```

The image and the heading stay glued (no blank line between them), which is what makes the
icon part of the card.

**That is how anything joins the section below it.** A block glued to a heading — no blank
line between them, and a blank line above the block — opens that heading's section and draws
above its title: a picture, an eyebrow line, a badge. It is the only way to put something
above a section's title:

```md
## Alpha
Read the full report.

New this week                ← blank line above, glued to the heading: opens Beta's card
## Beta
Ships on Friday.
```

Leave out the blank line above `New this week` and it stays in Alpha's card, under
`Read the full report.`

**Blockquotes glue the same way, and it decides how many gutter markers you get.** Consecutive
`>` lines are *one* blockquote, so a gutter bar, where the theme draws one, spans all of them
as a single rule. A blank line between them makes each row its own quote with its own bar — which
is the agenda / timeline row (see [`dashboards.md`](dashboards.md)):

```md
> 4:00 PM - Finish packing        ┐
> 6:00 PM - Drop off keys         │ one quote, ONE bar down the side
> 6:30 PM - Leave for airport     ┘

> 4:00 PM - Finish packing        ┐
                                  │
> 6:00 PM - Drop off keys         │ three quotes, a bar EACH
                                  │
> 6:30 PM - Leave for airport     ┘
```

Both shapes, and the list-token version, are in `renders/gutter-rows-900.png`.

## A leaf is not a group — and several features need a group

Grouping happens before repetition: first form a meaningful group from consecutive
lines, then repeat that shape as siblings. [Repetition](repetition.md#what-counts-as-a-run)
shows a minimal example of the two steps.

### Comments must preserve the grouping whitespace

HTML comments are hidden, but whitespace outside them still counts. When annotating
a card, preserve the blank lines that join or separate its content. For example,
this comment leaves the title and description consecutive after removal:

```md
### Design critique<!-- Exercises: heading and body glued into one card.
Tip: keep the next line adjacent to the heading. -->
Bring one screen and one open question.
```

Putting a comment on a new line between those two lines can leave a blank line
when it is removed. For documentation-only edits, compare the comment-stripped
Markdown, including whitespace, and the rendered output; see [verifying](verifying.md).

### What needs a group

One line is a **leaf**. Two or more consecutive lines glue into a **group**. That distinction is
the requirement behind three features; a leaf gets the ordinary behaviour:

| feature | needs |
|---|---|
| a run that **grids** into columns | every item a group — a bare line, one-piece list item or lone link stacks, by design ([`repetition.md`](repetition.md)) |
| `Emoji aside` | a group of more than one source line ([`elements.md`](elements.md)) |
| `Layout: Bento` | three or more sections at one level ([`dashboards.md`](dashboards.md)) |

Two pieces on **one** line never count: a line has no consecutive lines to glue, so
`___A___ - ___B___` is one leaf split into segments, and a segment is not a sibling.

The **styling** does survive the split, so do not restructure to protect it. Each segment keeps
whatever tier wrapped it, and so does a segment that had a badge peeled off the front:

```md
___Lisbon___ - 🚆 - ___Porto___  both cities still Display, badge between them
🔋 - ___82%___                  badge, then the charge still Display
_Full in 40 min - 12 W_         both pieces still Muted
```

So when a feature you asked for quietly did not happen, count the lines first — but count them
because of grouping, not because of type size.

## A heading swallows everything below it

A heading owns every following block until the next heading **of its own level or above**.
That is normal Markdown semantics, but here it decides what gets a background, a padding
and a corner radius — so it is visible.

The failure mode: you write a page with one `# Title` at the top and everything else under
it, and the whole document becomes a single section. If your theme paints `Heading 1`, the
entire page takes that paint.

## `***` ends a section

`***` alone on a line closes the section holding it. Everything after is lifted out as that
section's **sibling**.

A heading of the same level or above already closes everything before it, so `***` right before
one changes nothing. It earns its place **inside** a section, where what follows it would
otherwise stay in: here it lifts the footer line out of the card's tinted panel.

```md
### Web Design
Crafts engaging, user-friendly websites.
`Landing Page` - `One Page` - `Website`
***
__Explore__ - [➡️](/web-design)
```

**It climbs exactly one level, so write one per heading you are inside.**

**A heading written inside a `:::` row counts as one more heading you are inside.** A band
holding `___` + `## Title` + `:::` + picture + `___` closes with `***` twice: the first closes
the title's section, the second the band.

Symptom of getting this wrong: content that should start a new band stays inside the
previous one and inherits its background.

## An empty heading marker opens a section with no title

`# ` or `## ` — **with a trailing space** — opens that level's section and paints no title.

```md
## 

![icon.svg](icon.svg)
### Feature one
…
```

Its use: **giving a footer, a band or a card its own painted container** without inventing
a visible heading. That is also how a card gets a title in a size no heading level offers —
open an untitled section and write the title as a display tier (`__Daily Writing__`).

A run does not need a wrapper to grid — a top-level run grids on its own
(see [`repetition.md`](repetition.md)), and an extra wrapper shifts every background
rotation slot after it ([`colour.md`](colour.md)).

**The trailing space is required.** `#` alone on a line is literal text and renders as a
stray `#` character. This is easy to get wrong and gives no warning.

## `___` cuts a run; `---` only paints one

`___` alone on a line is a content break: it splits a run of siblings and paints nothing.
`---` paints a visible rule, with or without a blank line above it: straight under a line it
is still a rule, never a heading for that line.

**Written tight between two lines, `---` divides one block.** With no blank line on either side,
the lines and their rules stay one block — one card, one `:::` cell — with each rule drawn under
the line above it, the way `- ---` divides list items:

```md
Subtotal ... $42.50
---
Tax ... $3.40
---
Total ... $45.90
```

With a blank line on either side, a `---` is a block of its own.

The two marks look interchangeable and are not, because a heading owns everything down to the
next heading:

| written between two `##` sections | what happens |
|---|---|
| `___` | **lifted out of the section above**, so it lands between them and cuts |
| `---` | **swallowed by the section above** as its last child — it paints, and cuts nothing |

Only `___` is lifted, and deliberately: `---` is the spelling every generator emits for a
divider, so lifting those would break up card boards nobody asked to break up. The rare
spelling is the one allowed to restructure.

**Cutting nothing is not the same as changing nothing.** The section that swallowed a `---`
now carries a child the next section does not, so a run of same-shaped cards stops matching
and stops gridding. Give every card in the run its own `---`, or cut with `___`.

So **`___` is the cut** — for breaking a band of same-shaped sections so they stop
gridding, and for ending a `:::` row. Reach for `---` when you want the line drawn, and
write both when you want a divider you can see *and* that separates:

```md
---
___
```

## The whole-line tools

A line holding nothing but one of these is structure, not text.

| Spelling | Does |
|---|---|
| `---` | draws a rule |
| `___` | cuts a run, paints nothing, costs no space |
| `***` | closes the heading section holding it |
| `:::` | puts what is above and below it **side by side** |
| `;;;` | ends a `:::` row; the run goes on |
| `...` | pushes what is above and below it to the **top and bottom** |
| `+++` | adds **blank space** between what is above and below it |

The first three END a run — except that a `---` never ends a `:::` row: inside one it is part of
its cell. `;;;` ends one `:::` row and nothing more. The next two PARTITION one box — they say the pieces
either side share a space, and divide it across or down. `+++` does neither: it is space
inside the run, and a card holding one still matches its twins.

**A spaced separator divides its line.** ` - ` ` | ` ` : ` need a space on each
side, and there they divide whatever is around them — a sentence as readily as a run. How
the line reads is not the test; what you typed is. Unspaced is not a separator at all, which
is why `well-known`, `2026-09-18` and `a|b|c` are left alone.

In prose, write an em dash (` — `): ` - ` divides a line wherever it is.

**Escape a separator to keep the line whole.** `\-` `\|` `\:` `\.` stop that
character splitting the line — `Fri, Aug 14 \- Sun, Aug 16` stays one piece. A dot (` · ` ` • `)
never divides, so `Concha y Toro · Vino tinto` is one piece as written. The backslash is not drawn. The long dashes `—` `–` never divide, so write ` — ` for a dash inside a sentence and `\-`
when you need the ASCII one to stay put.

**End a line with `\` to break it without starting a new text.** Every line is its own
text; a trailing backslash joins the next line onto it, drawn on a new line of the same
text — an address in one value, a caption on two lines:

```md
**Address:** 12 Main Street\
Springfield, IL 62701
```

The next line must follow directly and not start a block (a list item, heading, quote or
table row); otherwise the backslash is drawn. Two trailing spaces do nothing.

Dividing a line is not the same as drawing its pieces. A sentence cut at a dash gives two
sentences; each piece is then read on its own, and a piece that reads as prose keeps its
values inline exactly as it would have on a line of its own.

**Escape a value's own punctuation to keep it text.** `\/` `\%` `\$` say "this token is
text", so the value is not read as data and draws nothing — no bar, ring, chip or chart
point — while the line keeps the structure you wrote:

```md
Elapsed: 45%           a percentage bar
Elapsed: 45\%          one line, the value drawn as text
4\/8                   plain "4/8", no ratio bar
_Expires_ 12\/26       a muted word beside a plain "12/26"
\$412M                 plain text, read as no value at all
```

A quick choice table:

| Desired result | Write | Visible treatment |
|---|---|---|
| Expiry label above plain value | `_Expires:_ 12\/26` | Muted Expires above plain 12/26 |
| Labelled percentage as text | `Elapsed: 45\%` | Key/value text |
| Currency as ordinary text | `Revenue: \$412M` | Ordinary key/value text |
| Weekday/day tile | `Mon-15` | MON above 15 |
| Date written as prose | `Mon 15` | Plain Mon 15 |
| Literal hyphenated date | `Mon\-15` | Plain Mon-15 |

For the expiry spelling, place one colon **inside** the muted wrapper.
Backticks select chips; value escapes select ordinary text.
For a chart list, escape every row's unit (`\%`, `\$`) when
you want every row as text; escaping just one row leaves eligible unescaped runs
available for charting.

**The long dashes are NOT separators.** ` — ` and ` – ` are punctuation, not structure: write
`Let's start simple — I'll guide you.` and it stays one sentence. That is deliberate — they are
not on the escape list above, so if they split you would have had no way to say "not here".
Only the ASCII ` - ` composes a row.

Two questions, two escapes — *did the line split* (a separator, declined with `\-`) and *was
the value drawn* (a run of nothing but elements and values, declined by escaping the value's own
punctuation):

```md
Jul-5 - Dec-5                    two day chips — a run of values, so they draw
Open the panel - Jul-5 is here   two pieces, and Jul-5 stays text — the line is prose
Delivered Jul-5.                 one piece — no separator, so nothing splits
GMT +9 \- Aug-12                 one piece — the separator is escaped
```

**A comma never divides a line.** It is punctuation, whether it appears in prose or in a list:

```md
Draft, In review, Shipped                              one line
We tested the app, it crashed twice, so we rolled back one line
Draft - In review - Shipped                            three pieces
```

Write ` - ` or ` | ` when list items must become separate pieces.

An escape declines whatever *rides* on the split, too: a peeled-off piece can be detected as a
date, a currency or a percentage, so `GMT +9 \- Aug-12` keeps the line whole and leaves `Aug-12`
as text, while the unescaped form splits and draws a day chip.

**An underscore inside a word needs no escape.** CommonMark does not read `_` between two
alphanumerics as emphasis, so `user_id`, `max_width` and `snake_case_name` are literal text
wherever they appear — in prose, and inside a `_…_` muted line: `_kawsar's_wifi_` is one muted
run with the identifier intact. Writing it as a chip `` `user_id` `` is still fine, but it is
now a styling choice rather than a workaround.

**`\_` is still not one of the five**, and it only matters for an underscore that is NOT inside
a word — one next to a space or another underscore, as in `_leading \_underscore_`. There the
underscore is kept as text and the line draws in italic rather than muted; a literal
underscore inside a word or in a chip keeps the line muted.

**Inside a list all three are just a rule.** `- ---`, `* ___`, `1. ***` each paint a
divider with no bullet beside it — the three tools are a top-level distinction. Careful:
`* ***` is four matching stars, so it is one thematic break and still closes the section.

Between list items, `- ---` is a row divider: a rule under one item, and every item keeps its
marker — the divided rows of a settings or reference list.

## `...` pushes content apart

` ... ` is a **spring**: an expanding gap. Everything before it goes to one edge,
everything after it to the other — the only way to place a piece against the opposite
edge from the level's `Horizontal align`.

```md
Subtotal ... $42.50                 → Subtotal left, $42.50 right
... Read more                       → the whole line right
Terms - Privacy ...                 → the whole line left
Home ... About ... Contact          → left, centre, right
... Centred ...                     → centred
450 : Done ... 35 : Users           → two stacked columns, pushed apart
Key: ... Value                      → Key: left, Value right
```

The rule is positional: the first region goes left, the last right, anything between
them centres. A spring against an edge leaves an empty region on that side, which is how
"push everything the other way" is written.

**Two springs is the ceiling** — that reaches all three placements. A third and beyond
still *separate* the middle into cells but cannot *place* them: every middle region lands
in the one centre bucket and packs there as a block. So `A ... B ... C ... D` is left /
B and C centred together / right — **not** four evenly spaced items. A spring sends the
slack to an edge; it never distributes it. There is no space-between. For evenly spaced
items, write a repeated run and let it grid.

Spacing is the same as for ` - ` and ` | ` — a space on both sides — except that the
start and end of the line also count, so `... A` and `A ...` are springs. Exactly three
dots: `....` and `wait...what` are literal text, and so is `\...` — write `Loading...` or
`Loading \...` to end a line on dots rather than push it left.

`...` splits **before** every other separator, so `A ... B - C` is `A` on the left and
`B - C` together on the right, with the dash between B and C drawn or hidden as the theme
says. Nothing is ever drawn in the spring's own gap.

**It works on a heading line too**, which is how a card header gets its title on the left
and its action icons hard right:

```md
## Transaction History ... [`📋`](/copy) [`…`](/more)
```

Two things to know:

- **A spring places a row.** It is at its best on a line with structure in it —
  `Subtotal ... $42.50`, `## Title ... [icons]`, `Label ... [x]`, `🙂 - __You__ ...` — where it
  reaches both edges of the card no matter how wide the layout made it. **It works on every
  line, prose included**: `He paused ... unsure what to say next.` is two pieces pushed to
  the two edges, not a sentence. For an ellipsis inside a sentence, write the single character
  `…` or escape the dots: `He paused … unsure` and `He paused \... unsure` both stay the
  sentence you wrote.

  To place a whole block, give it its own section; the theme's `Horizontal align` on that
  level places it.

  **When every card is at the same level, the spring is what makes one of them differ.** On a
  board of `## ` cards, the theme's alignment reaches all of them at once, so a card that should be centred
  gets a spring on each of its lines:

  ```md
  ... ___$28.75___ ...
  ... _Add money_ ...
  ```

  It costs one line's worth of typing per line, and the tier, the muted style and any badge on
  the line all survive it.
- **Escape a dot to keep the dots literal**, like any separator: `Total \... $128` stays one
  text reading "Total ... $128". Backticks and quotes work too:
  `` `Total ... $128` `` and `"Total ... $128"` are both left alone.

  Quotes protect more than dots. A quote pair also declines a separator, and around a bare
  emoji, link or code span it declines the whole element — `"📞"` is a glyph in the text
  rather than a badge, and there the quotes are consumed rather than drawn. See *Quote an
  element to keep it text* in [`elements.md`](elements.md).

## `:::` puts blocks side by side

A line of three colons divides a run of blocks into **cells of one row**. It is the
block-level twin of ` : `, which stacks the pieces of a single line into columns.

**A row is a run, so you open it and you close it.** `:::` divides a run; it does not begin or
end one. A row ends at `___`, at `;;;` (which ends the row and keeps the run going), at a
heading of its level or above, or at the end of the document. `***` ends it by closing the section
the row is in. A `---` does not end a row: it belongs to the cell it is written in, and `---` lines
alone after the last `:::` draw under the row. That explains every surprise in this section, so
the shape to write is:

```md
___          the cut above: the row starts here, and takes nothing before it
A
:::
B
___          the cut below: the row ends here, and takes nothing after it
```

Leave the cuts out and the row reaches as far as the run does: a heading above it becomes cell 1
(with the first block), and the paragraphs below it join the last cell. Neither is announced,
and a blank line does not help — only a cut does.

**`;;;` closes a row and keeps the run going.** `___` ends the run, so rows cut apart with it
never grid. Close each row with `;;;` instead and the rows stay one run: rows of the same
shape grid like any other repeated block.

```md
## Artists
;;;
![](a.jpg)
:::
**Artist A**
;;;
![](b.jpg)
:::
**Artist B**
;;;
```

The first `;;;` keeps the heading out of the first row. Use `___` where you want the
repetition to stop.

```md
![](photo.jpg)
:::
## Everything you crave
Delivered in minutes.
:::
[Find restaurants](/x)
___
```

That is one row of three cells: the picture, the heading with its line under it, and the
button. Everything between two dividers is one cell, so a cell can hold as many blocks as
you like — a heading, its body, a button, paragraphs with blank lines between them — and it
stays one column. Only a `:::` adds a column; to start a new row, close the one before with
`;;;`.

`:::` is for cells that hold **blocks**. If each cell is one thing — a strip of logos, a
picture beside a button — write them on **one line** instead and they stay on it; see
`elements.md` and `images.md`. Reach for `:::` when a cell needs more than a line.

**With no number, each cell is as wide as its content**, like the pieces of a ` - ` line:
`A` `:::` `B` `:::` `C` sits the three side by side, packed, not stretched across the row.

**A number sizes the cell ABOVE the divider**, and turns the row into proportions that
fill it. Every cell but the last already has a divider under it, so the weight always has
somewhere to go; the last cell's divider is optional, and in a row with a number an
unweighted cell is `1`.

```md
![](photo.jpg)
:::1
## Everything you crave
Delivered in minutes.
:::2
```

The picture takes a third, the text two thirds. Weights are ordinary numbers, so `:::0.5`
is half of what its neighbour gets and you never have to rescale the others to keep them
whole.

**`:::0` means "no share — just fit".** The cell shrinks to exactly what its content needs
and the others flex around it. That is the shape for a label beside a body, or an icon
beside a block:

```md
**Status**
:::0
The order was picked up and is on its way to you now.
```

**A divider can say what it does in narrow and in wide space.** Narrow is under 768px,
wide is 768px and up, measured on the space the ROW is given, not the window: a row inside
a card in a two-column grid is in narrow space even on a wide screen.

| Write | Narrow | Wide |
|---|---|---|
| `::: 1` | side by side, weight 1 | side by side, weight 1 |
| `::: 1 >` | stacked | side by side, weight 1 |
| `::: 1 <` | side by side, weight 1 | stacked |
| `::: 1 1.5` | side by side, weight 1 | side by side, weight 1.5 |

`::: >` and `::: <` alone carry no number, like a bare `:::`, and `::: 0 >` is "just fit, wide only". The most
common use is a picture beside its text on a wide screen and above it on a narrow one:

```md
![](photo.jpg)
::: 1 >
## Everything you crave, delivered.
Some copy.
[Find restaurants](/x)
:::2
___
```

- Where a divider does not cut, the cells either side of it stack as one cell; the row's
  other dividers keep their own rule.
- It only turns a cut off. A row that does not fit still wraps, in wide space too.
- Written with the same characters but in any other shape — `::: 1 1.5 >`, `::: < >`,
  `::: 1 2 3` — the line is read as a bare `:::`, and `check` names it. Words after the
  colons (`::: note`) keep the line as text.

Three things worth knowing:

- **A row is a request, not a command.** A cell that does not fit beside the others at the
  width they are given moves to the next line, as a piece of a ` - ` line does; at a narrow
  width every cell can end up on its own line. It is why a row inside a narrow card
  behaves — you do not have to plan for it.
- **A `:::` closes a heading opened inside the row**, so `## Title` in cell 2 does not
  swallow cell 3. A section's own heading rides in cell 1, which is how
  `## Title` + `:::` + body reads as "title on the left, its text on the right".
- **A row runs from one cut to the next — so close it, or it keeps eating.** A blank line
  does not end a row; only the marks listed at the top of this section do. A row with no
  cut after it goes on taking whatever follows as extra cells: the next paragraph, and then
  the next section, silently. `___` is the cut to reach for, since it works everywhere.

  ```md
  Left
  :::
  Right

  A following paragraph.        ← becomes a THIRD CELL, not a paragraph
  ```

  ```md
  Left
  :::
  Right

  ___

  A following paragraph.        ← its own block, as written
  ```

  A trailing `:::` does not close anything either — it only weights the last cell. If
  there is content after it, that content becomes another cell.

  The same rule is what gives each repeated shape its own row:

  ```md
  ___
  ⭐
  :::0
  **Fast delivery**
  In under 30 minutes.

  ___
  ⭐
  :::0
  **Free returns**
  Within 30 days.
  ```

  Two rows, each an icon shrink-to-fit beside its text. Note what `___` costs: it cuts the
  run, so these stack rather than sitting side by side — that is the same `___` that breaks
  up a repeated-element grid, doing the one job it has. Leave the cuts out when you want
  the cards to grid, and keep each card to a single group.

### A `:::` acts on the level it is written at

The divider splits the **siblings around it**, wherever those are — it is not a top-level
tool. Three places that matters.

**Inside a heading section.** The section keeps its own background and padding, and the row
sits inside it. A section's own heading rides in cell 1, so this is the two-cell shape:

```md
## Everything you crave
Delivered in minutes.
:::
![](photo.jpg)
```

**Inside a list item, by indenting the divider** to the item's continuation column. That is
how an icon sits beside its label while the item stays an item: the row is the ITEM's, so it
ends where the item ends, and neither the next item nor the heading above joins it:

```md
- ![](icon.svg)
  :::0
  **Product team hub**
- ![](icon.svg)
  :::0
  **Decision doc**
```

Items like these are groups, so a run of them grids; a `___` between them
keeps them in one column.

**One level out, by closing the section first.** A `***` ends the heading section holding
it, so a `:::` written after it divides the OUTER section's children instead of the inner
one's. Without the `***` below, the divider would land inside the `###` and the button
would sit beside the screenshot; with it, the button sits beside the whole card:

```md
## Writeups
Weave reads like a document.

### {#screenshot}
![](screenshot.png)

***
:::
[Explore](/x)
```

## `...` on its own line pushes blocks apart

The same spring, on the other axis. Written alone on a line it divides a column into
regions and sends them to the top and bottom of the space they were given:

```md
![](photo.jpg?md2ui.aspect_ratio=3:4)
:::
## Everything you crave
...
Delivered in minutes.
```

The heading sits at the top of the picture's height and the line drops to the bottom.
Positional, exactly like the inline spring: first region top, last bottom, anything between
centred, and a spring at either end pushes the one block the other way.

It needs a space to open into, so it does something only where a column was given a height
— a `:::` cell beside something taller, a card in a grid. In a plain column the height is
the content, so there is no slack and the spring is quietly inert.

**Indented under a list item, it belongs to that item**, as an indented `:::` does — this
centres the name beside the picture in every item:

```md
- ![](photo.jpg)
  :::
  ...
  **The Weeknd**
  ...
```

## `+++` adds space

Three to five `+` are blank space — `+++` small, `++++` medium, `+++++` large; the theme
says how large. Alone on a line the space runs **down**; spaced inside a line it runs
**across**:

```md
Title
+++++
Body pushed a large step down.

Price +++ `€12` ++++ [Buy](/buy)
+++ Indented line.
```

- It stays in the container you wrote it in: at the end of a card's body it is space inside
  that card, indented under a list item it is space inside that item, in a `:::` cell it is
  space in that cell. Alone between two `:::` it is space between the two cells, across the
  row. Above and below a card's only line or `:::` row, it is space above and below that row,
  inside the card.
- To put space **between** two sections rather than inside the first, close it first:
  `***` then `+++`.
- Inside a line it divides the line like ` | ` does and draws blank space in the gap. When the
  window narrows, the line wraps first: a piece that does not fit moves to the next line,
  spacers at full size. Only then do spacers shrink, and only enough for the text beside them
  to keep its minimum width — the same floors that size a grid column
  ([`repetition.md`](repetition.md)). So padded prose wraps more on a narrow screen, down to
  that width, and no further.
- A `:::` row is one line in the same way, with or without numbers, so a spacer at the
  edge of a one-line cell is space beside the cell — `Alpha +++` `:::` `Bravo` is the gap
  of `Alpha +++ Bravo` — and when the row wraps it drops the same way. A spacer written as a
  whole cell at the row's start or end is that edge space, inside the card; beside a list
item it sits outside the item's box, while `- +++ Item` puts the space inside the item's own
line, in its box. A cell with spacers
  on **both** edges is held instead, like the paragraph below: they stay its own, and a block
  is held the same way, down to its own minimum width:

  ```md
  ++++
  :::
  Subtotal ... $42.50
  Tax ... $3.40
  Total ... $45.90
  :::
  ++++
  ```
- Spacers written together add up: `+++ +++` is two small steps.
- Spacer lines stacked one under another add up too, and the blank lines between them add
  nothing. Several spacers alone on one line are the same thing: `+++++ +++++` with nothing
  beside it is one spacer down the page, two large steps tall. Beside content they run across
  the line instead.
- Other counts of `+` are text, and so is `\+++`.

**Spacers on both sides hold a paragraph to a narrower column:**

```md
+++++ +++++ Our security features watch every transaction as it happens, flag what looks unusual and hold it for review, so your money stays where you put it. +++++ +++++
```

On a wide screen the paragraph wraps in the column between the spacers, held off both edges; on
a phone the spacers give way until it has its minimum width. A line too short to wrap only gets
the left indent — it never reaches the spacers on the right. To choose where a headline breaks,
end its line with `\` instead ([`text.md`](text.md)).

**A spacer gives a `...` spring room to move.** On its own a spacer is the same size in every
card, so twins with captions of different lengths end at different heights. Write the spacer
then the spring, and each card keeps the room *and* sends its last block to the floor:

```md
## 
🎯
+++++
__Authorized transactions promptly__
+++++
...
_Contributing to a well-managed financial system_
```

Icon at the top, title in the middle, caption on the floor, and the captions of a row of
these line up.

## A page of sections that each look different

When an answer is long — an overview, a guide, a report, a page — give each part its own
**band**: an untitled `# ` section carrying a named style. The theme paints each named style
once, so a band keeps its look wherever it sits, and bands can be added, removed or reordered
freely:

```md
# {#hero-1}

___Everything you crave\
delivered to your door___
[Find restaurants](/restaurants) *[Learn more](/about)*
***
___

# {#features-1}

![](a.svg?md2ui.max_width=56&md2ui.aspect_ratio=1:1)
#### Feature one
Copy.

![](b.svg?md2ui.max_width=56&md2ui.aspect_ratio=1:1)
#### Feature two
Copy.
***
___

# {#split-1}

___
## Everything you crave
Delivered in minutes.
[Find restaurants](/restaurants)
::: 1 >
![](photo.jpg?md2ui.min_width=320)
:::1.6
___
***
***
```

- **One name per look.** `{#split-1}`, `{#split-2}` and `{#split-3}` all take `#### Split`; the
  number only keeps each id unique ([`colour.md`](colour.md)).
- **Close every band with `***`**, one for each heading you are inside — counting a heading
  written inside a `:::` row, which is why the last band closes twice — **and cut with `___`**
  so each band takes the full width rather than sharing a line with the next
  ([`repetition.md`](repetition.md)).
- **Leave a blank line under the band's `# ` line**, so its first block belongs to what
  follows rather than to the band itself.
- **Fill each band with the construct its content asks for:** a row of cards
  ([`repetition.md`](repetition.md)), text beside a picture (`patterns/split`), columns of links
  (`patterns/directory`), a photo with words on it (an image card between two bands, with
  `+++++` in its alt slot — [`images.md`](images.md)).
- **Several boards of cards on one page** each take their own heading level, so each finds its
  own column count ([`repetition.md`](repetition.md)).
