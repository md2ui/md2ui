---
name: md2ui-repetition
description: How to get cards into a row or grid in md2ui — what makes siblings repeat, why a run refuses to grid, and how many columns you actually get.
---

# Repetition: getting a row of cards

You never ask for a grid. You write repeated siblings of the same shape, and the renderer
grids them. So "make these three side by side" is really "make these three look identical
to each other, and put them somewhere that can grid".

## What counts as a run

Think in two steps: **consecutive lines form one group; repeated similar groups
form a run that can grid.** A blank line separates groups; their matching internal
structure makes them candidates for the same row:

```md
**Design critique**
Bring one screen and one open question.

**Peer practice**
Work through a small challenge together.

**Tool exchange**
Share one shortcut that saves you time.
```

Each pair is one group, and the three groups repeat. Removing the blank lines
makes one larger group; inserting a blank line inside every pair leaves isolated
lines. Available width determines how many columns fit.

A run is **contiguous siblings with the same shape**. Same child types, same order, similar
size. Three cards each `image + heading + paragraph + link` are a run. A card may carry one
line more or less than its siblings, any number of chips or buttons, or no picture where they
have one, and still run with them. To keep a missing picture's place, write it empty, `![Name]()`: it
draws a quiet box the size of its siblings' pictures, so every line below it lines up.

Practical consequence: **keep repeated items structurally identical.** If one card needs a
footnote, either give every card one or put it outside the run. Members of a run also share
their arrangement: if one tile has to stack its key over its value, every tile in the run does,
and if one `:::` row wraps its cells, every row puts one cell per line. Repeated lines do the same:
when one line of a run has to break its pieces onto a second row, every line of the run breaks at
the same piece, lines inside one card included. A line of only links or chips wraps like words.

The shape includes what an item draws: a picture's size (`md2ui.max_width`, `min_width`,
`aspect_ratio`, `shape`) and whether a link is a button or a text button. Two boards whose
pictures are sized differently are two shapes, so each finds its own column count. A checked
and an unchecked task are the same shape, so a checklist runs as one list. A block of exactly two
lines is a shape of its own: it runs with other two-line blocks, never beside a block of three.

## Only repeated GROUPS grid — and that is the control

A leaf is one line; a group is a heading with its lines, or two or more lines glued together.
**Leaves stay vertical, and only repeated groups start a grid.** Four identical items:

| item | result |
|---|---|
| `Alpha` (one line) | **stacks** |
| `- Alpha` (plain list item) | **stacks** |
| `- ![](a.png) - **Alpha**` (list item of two pieces) | grids |
| `[Alpha](/a)` alone on its line | **stacks** |
| `![](a.png)` alone on its line | **stacks** |
| `Alpha` + a second line | grids |
| `### Alpha` + a line | grids |

**A list item is a leaf or a group by what it holds**, so items of two or more pieces — split
from one line, or an indented `:::` row — grid like any other group. To keep such a list in
one column, put a `___` between the items.

That distinction is the whole of your control over the page. If leaves gridded too, every line
in the document would start arranging itself and there would be no way to say "these belong
side by side, those do not".

**When each card has a picture, the picture leads.** Open the card with an untitled `### ` and
put the title in bold under the picture, so every picture starts at the same height
([`images.md`](images.md), question 5).

**A group does not have to be glued.** A heading owns the lines under it, so this is three
groups of the same shape, and it grids three across with blank lines throughout:

```md
## Heading

leaf 1

leaf 2

## Heading

leaf 1

leaf 2

## Heading

leaf 1

leaf 2
```

**Want short things in a row? Put them on one line.** A same-line run stays a row and flows
into fewer columns as the space narrows — that is the leaf-level answer, and it needs no
grouping at all:

```md
Alpha | Beta | Gamma | Delta     one row that reflows

Alpha

Beta                             three leaves, stacked
```

**Never split a paragraph just to make a group.** Cutting prose in two to earn a grid makes
related sentences read as unrelated blocks, and it is the one thing here that damages the
answer rather than its layout. A paragraph finds its own fit — leave it on one line.

## Choose the arrangement by the spelling

The same items can stack or grid; how you write them decides which, on purpose. Four
items at 1024px:

| you want | write | the run |
|---|---|---|
| a column of one-line items | lines `**Wi-Fi** - Free in every room`, spring lines `Check-in ... 3 PM`, or spring list items `- Check-in ... 3 PM` | stacks |
| a grid of one-line items | the same as list items, `- **Wi-Fi** - Free in every room`, or `:::` rows closed with `;;;` | grids |
| stat tiles | a label over its value, `_Revenue_` above `$129,201.40`, a blank line between tiles | grids |
| a grid of rich items | glued blocks (a title line + a body line), or `:::` rows closed with `;;;` | grids |
| a column of blocks that would grid | a `___` between them | stacks |

Pick the row for the arrangement; never reshape the content to get it.

## A run at the TOP LEVEL grids like any other

Repeated sections grid wherever they sit, the document's top level included: three
top-level `##` sections go 3-across, and a longer run tiles under `Layout: Bento`.

**A run grids without a wrapper.** An empty `## ` wrapper adds nothing to the grid and
shifts every background-rotation slot after it ([`colour.md`](colour.md)). Wrap only when
you want the band painted as its own section.

`***` moves what follows to the top level, which is fine.

## `___` is the off switch — and the way to shape a run

Gridding is automatic, and it groups **contiguous** siblings of the same shape. So the way to
stop it, or to decide where it breaks, is to make two of them non-contiguous: a `___` between
them cuts the run, paints nothing and costs no space.

That is one control doing two jobs:

```md
## Card one       ┐
…                 │  these two grid as a pair
## Card two       ┘
…
___
## Card three     ┐
…                 │
## Card four      │  and these three as a trio
…                 │
## Card five      ┘
```

Five same-shaped cards, one `___`, and you get 2 + 3 instead of one run the packer arranges
its own way.

**It works at every level, page bands included.** A page written as a run of `# ` bands with
one paragraph each is a run like any other, so it grids into columns — which is almost never
what a page wants. A `___` between the bands stacks them:

```md
# Band one
A paragraph.

___

# Band two
A paragraph.
```

Use `---` when you also want the divider drawn; write both (`---` then `___`) for a rule you
can see that separates too. Only `___` is lifted out of the section above, which is what lets
it land *between* two sections — see [`structure.md`](structure.md).

## One long paragraph stacks the whole section

The one full-width trap no wrapper saves you from. A block
over ~100 words forces its container full-width, and the length travels upward — so one
long paragraph buried inside one card stacks every card in that section.

Four short cards go 4-across at 1280px; make one card's body 110 words and all
four stack.

**That is the layout following the content, and it is correct.** A paragraph that long needs
the measure to read, so the section gives it the whole width. Write the body the answer needs.
**Never cut content to win a grid** — shortening a paragraph so cards line up makes related
material read as unrelated fragments, and it trades the answer for its arrangement.

## How many columns you get

You do not choose. The count comes from arithmetic:

```
columns ≈ (available_width + gap) / (column_min_width + padding + gap)
```

and `column_min_width` is floored by the **length category of the text inside**, not by
anything about the card. The values that matter:

| words in the item | minimum column width |
|---|---|
| ≤ 1 | 80px |
| 2–4 | 100px |
| 5–9 | 200px |
| 10–40 | **320px** |
| 41–100 | 580px |
| over 100 | never grids (see above) |

So a card holding one 10–40 word paragraph costs ~320px + its padding per column, whatever
else is in it. Two consequences:

- **Longer text takes more width, by design.** Each category gets the space that kind of text
  needs to read, so the column count is an *outcome* of what you wrote — not a target to write
  toward.
- **The default theme caps the page at 1440px** (its `Max width`). Four columns of 10–40
  word text need more than that, so a run of that shape lands at three columns there.

Most runs therefore land at 2 or 3 columns, and 4-across happens when the items are short
labels. Read those numbers as what to expect, not as something to aim at.

## The orphan rule: 4 items often become 2+2

The renderer refuses to leave a nearly-empty last row. With a 3-column fit and 4 items,
3+1 is rejected and it steps down to **2+2**.

So for a 4-item run the outcomes are 4-across or 2×2 — normally not 3+1. If 4-across is out of
reach (see above), you get 2×2. **If you want a single row, use 2 or 3 items, or accept
2×2.** A 3-item run at a 3-column fit renders as one clean row, which is why three is the
safest number for a feature row.

The step down is decided once for a **shape**, not once per run. If a document repeats the
same card in several places they share one column count, and it drops only when a third or
more of those runs would end on an under-half row — so a single 3+1 among clean runs of the
same card can survive. Write each run at a length that divides rather than relying on the
rule to rescue it. What stays ragged is then the theme's `Orphan row` (left, center or
stretch), written on the level that contains the grid.

**Give each board its own heading level to size it on its own.** Cards at `###` and cards at
`####` are two shapes, so each board finds its own column count: a feature row of three stays
three across on the same page as a grid of four. A named style (`{#feature-1}`) changes the
look only: the boards still share one column count.

## Tall cards get fewer, wider columns — when that makes them shorter

If the columns that fit leave the cards much taller than they are wide, the run drops a
column, and keeps dropping while that makes its tallest card shorter. Text that wraps gets
shorter in a wider column, so a run of paragraph cards steps down to two or three across. A
run whose cards do not wrap — lists of short lines or links, a number with a ring, a key over
its value — keeps its columns: a wider column would only add empty space beside each item.

So you do not shorten text to keep columns, and a footer of four link lists stays four
across wherever four fit. To place items side by side whatever their height, write them as a `:::` row.

## What happens to blocks that are NOT repeated

They pack. A one-off `## ` band asks for the width its content needs — text included, which
is why a band wraps to the next line before its own text does — and sits beside the next
band rather than spanning the page. A grid inside a packed band can use one column fewer
than it would across the whole line. A line always fills its width: the
leftover is shared in proportion, so bands on a line grow together and none is drawn under
what it asked for. That is the theme's `Stack sections` (on by default); nothing in the
Markdown asks for it.

The practical consequence for authoring: **you do not have to make blocks identical just to
get them onto one line.** Make them identical when you want them SIZED alike — that is the
grid above. Leave them different when they are different; they will still share the line.

## Same-kind runs share one decision

Repeated items are polled and get **one** decision for the whole run — one column count, and
one set of image properties. This is deliberate: it is what keeps six cards looking like six
cards instead of six different cards.

It means a per-item override is not really per-item. If you annotate one image in a run, it
applies to all of them; if you annotate several differently, a majority vote picks one and
the conflict is reported. **Annotate every member identically**, or none.

## Checklist

- [ ] each item is a BLOCK (2+ lines, or a list item of 2+ pieces), not a bare line, one-piece list item or lone link
- [ ] repeated items are structurally identical
- [ ] they are contiguous (nothing interleaved)
- [ ] the copy is what the answer needs — not trimmed to make a row fit
- [ ] the count is 2 or 3 if you need a single clean row
- [ ] a `___` sits anywhere the run should stop or break
