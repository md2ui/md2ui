---
name: md2ui-text
description: Emphasis tiers, labelled values, stats and inline code in md2ui — the three underscore wrappers, and why emphasis must never be used for structure.
---

# Text, emphasis and stats

## Three tiers you can pick directly

Wrapping a **whole leaf** — a full line, or a full segment — in underscores selects a
display tier:

| Markdown | Tier | Use for |
|---|---|---|
| `_Available balance_` | Muted | captions, footnotes, secondary labels |
| `__From $145 per night__` | Lead | a standfirst, a lead-in line |
| `___$12,480.55___` | Display | the big number |

They are exact CommonMark synonyms for asterisks, so the same file still reads correctly
anywhere else — italic → bold → bold-italic, in the same order of weight.

**Scope is the whole leaf.** A wrapper inside a sentence is just emphasis:

```md
___$12,480.55___              → Display tier
Text with a __bold__ word     → an ordinary bold span, NOT a tier
```

An icon beside a big value is the same rule. Wrap the whole line and the icon grows with the
value; divide the line and the value is a segment of its own, beside the icon as a badge:

```md
___🔋 82%___                  → the icon and the value, both Display
🔋 - ___82%___                → an icon badge beside a Display value
```

## A label and its value: write the label above it

A colon is text: `Revenue: $129,201.40` draws as written, on one line, and so does a
sentence that holds one. To show a label and its value as a pair, write the label on its
own line, muted, and the value under it:

```md
_Revenue_
$129,201.40

_Wealth Management_
__$412M__
```

The value takes whatever weight you give it — plain, `__Lead__` or `___Display___` — and a
blank line between pairs makes each one a group, so a run of them repeats as a set
([`repetition.md`](repetition.md)). On one line, a spaced colon stacks the same pair:
`_Revenue_ : $129,201.40`, and ` - ` puts several side by side,
`_Duration_ : 11:05 - _Calories_ : 182 kcal`. A chip goes on the value's line the same way:
`_Status_` over `` `Active` ``.

A value that draws reads its label from the colon on its line: `Progress: 60%` is a bar,
`Disk: 61/128 GB` a ring, `Price: $710 → $713 → $720` a line, and three or more
`- Key: value` rows in one unit a chart ([`dashboards.md`](dashboards.md)). Keep that colon
tight to the label; a spaced ` : ` stacks two pieces into columns instead.

## Choose the text role before its size

| Intent | Markdown |
|---|---|
| Section title | `## Balance` |
| Authored hero figure | `___$12,480___` |
| Hero figure with its icon | `___🔋 82%___` — the glyph grows with the number; `🔋 - ___82%___` puts a badge beside it |
| Supporting lead | `__Ready for your next trip.__` |
| Caption | `_Available this month_` |
| A label and its value | `_Owner_` over `Alex` |
| Status chip | `` `Draft` `` |

For a large balance with smaller supporting stats, write:

```md
___$12,480___
_Available this month_

_Income_
$4,250

_Expenses_
$1,180
```

Use underscore wrappers for these authored tiers; asterisk emphasis
is ordinary emphasis, and a wrapped backtick chip selects a chip variant rather than
`Display`. Heading levels express section ownership, so do not change a heading's
level merely to obtain a different font size.

When one title must be louder than its peers at the same level — a band headline among small
card titles — keep the small ones as headings and write the loud one as a tier inside an
untitled marker:

```md
## 
___From budgeting to fraud detection___
```

A tier is also how a headline breaks where you say: a `\` at the end of a line breaks inside a
paragraph, and the wrapper spans the break:

```md
# 
___Everything needed for\
financial security in one app___
```

That is one text, two lines, at the tier's own line spacing.

## A repeated list of pairs is uniform when written alike

Write every pair the same way — the same tier on each label, the same on each value — and a
repeated list of them reads as one set.

Use chips — `` `47,000` ``, `` `+15%` `` — when you want pill styling. Choose an authored
tier when a figure must shout; repetition alone does not make a number a hero.

## Emphasis is styling, never structure

Do not use `**bold**` or `*italic*` to signal "these belong together" or "this is a new
section". Grouping comes from blank lines and headings only
(see [`structure.md`](structure.md)). Emphasis inside a line never changes how the line is
grouped — but wrapping a *whole* line changes its style tier, which may not be what you
meant.

## One phrase of a headline in the brand colour

The thing you reach for when a design sets two words of a title in the accent colour. Emphasis is a weight, not a colour — but an inline
`` `code` `` span that **stays inside the text** is a *marker*: it keeps its line's family, size
and weight, and the theme gives markers their own colours:

```md
# 4 ways `50,000+ teams` use Weave to get more done each week.
```

Where the theme gives markers no colours, the span draws as ordinary text. The span has to stay
*inside* the line: give it the line to itself and it is a chip instead (see below).

## Inline code has two forms

- **In a sentence** — `` the `active.json` file `` — stays inline and is painted as a
  marker.
- **On its own, or clearly separated** — `` `Draft` `Review` `Shipped` `` — becomes a chip
  (a small pill).
- **On its own but quoted** — `` "`code`" `` — is a marker again. Quoting an element
  declines the pill, so a span that has to own its line can still read as text; the quotes
  are not drawn. See *Quote an element to keep it text* in
  [`elements.md`](elements.md).

A chip run is a good way to render tags or statuses. Separate its members explicitly:
`` `Draft` - `Review` `` is a run of two.

**A chip is for a word the reader scans for** — a status, a category, a tag, where an item comes
from: `` `Free cancellation` ``, `` `Made for you` ``, `` `You follow` ``. Chips share one look, so the
fewer there are, the more each one says:

- **A count, a year, a duration or a size is a detail, written muted:** `_1,002 reviews_`,
  `_2004_`, `_3:57_`.
- **A rating is one chip with its word beside it,** and its count muted after:

  ```md
  `9.0` - Wonderful - _1,002 reviews_
  ```

- **A status belongs at the edge of its title:** `` **Home in Raito** ... `★ New` ``.
- **An item's own categories are one run under its name:**
  `` `Indie rock` `Post-punk revival` `Dance-punk` ``.
- **A chip repeats its heading when every item carries it.** Under `## Artists`, an
  `` `Artist` `` chip on each card says what the heading already said; in a list that mixes
  kinds, the same chip is what tells them apart.
- **Two kinds of chip on one card look alike unless one takes a variant.** Wrap one kind in
  `*…*`, and the theme draws it with another look: `` `Pool` - `Wi-Fi` - *`Free cancellation`* `` keeps the amenities and
  the policy apart (`guide("theme")` lists the variants).
- **When a chip's colour should mean something,** put the glyph inside it, `` `✓ Shipped` ``, so a
  theme pin can colour it ([`colour.md`](colour.md)).

Triple-backtick or tilde fences are a separate block element, not a third inline form. They
preserve source whitespace and can use Pygments syntax highlighting; see
[`code-blocks.md`](code-blocks.md).

## Headings win

Precedence is **heading > tier > automatic key styling**. `# ___x___` is a heading first —
it keeps the heading's family and size and just paints bold-italic.

## Practical defaults

- one `#` per band, `##` for the blocks inside it, `###` for cards in a run;
- write the body the answer needs — text length sets the width that kind of text gets, so the
  column count follows the copy rather than the other way round ([`repetition.md`](repetition.md));
- write a figure under its muted label (`_Revenue_` over `$129,201.40`);
- use `_…_` for the caption under a stat, not a smaller heading level.
