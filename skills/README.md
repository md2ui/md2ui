---
name: md2ui-authoring
description: md2ui renders your Markdown reply as UI. How to write that reply so it renders well. Read this first.
---

# Writing Markdown for md2ui

md2ui takes an ordinary Markdown document and renders it as a UI. These notes are for the
LLM writing that Markdown.

## This is your reply

Writing for md2ui is writing your answer. There is no second artifact: the Markdown you would
send as a reply is what md2ui renders, and a client without md2ui shows the same text as
ordinary Markdown. Any answer can go through it, and its form is yours to choose: a UI, a plain
written answer such as a plan, or both in one document. An answer the user reads — an
explanation, an article, a guide — stays paragraphs, as long as it needs: md2ui draws it as a
reading page (`patterns/article`, `patterns/guide`). Structure goes where the content already
has it — items to compare, steps, figures — and never replaces the writing. Write it the way
you would anyway, with two differences. **Include the pictures.** A chat can only link to a
picture, and the window shows it: when your data comes with visuals — covers, photos, logos,
SVG icons, maps — include them by default, and when a tool you have can return an item's
picture, get it, even if that takes a second request. **Offer your next steps as buttons.**
In a chat the user acts by typing, while here they can click: offer the next steps you could
take with your own tools as buttons, `[Add to playlist](agent:add-to-playlist?id=7)`, and each click
comes back to you as a sentence. Everything on the page is real — what you read, or what the
conversation holds; the figures and names in these notes are illustrations, never content.
When the user asks for an example, a demo or a mockup, plausible sample data is what they asked
for: mark the page with a `` `Sample data` `` chip. Never use it to fill in for data you could
not get; say that instead.
And it is chosen: what a tool returns is material, not the answer. Show what answers the
question, and when nothing does, say so and offer the route that works.

**When you have includes, read `guide("includes")` before you write.** Your instructions or
the `guide` tool name them when this server has any: pages and figures it builds from live
data, each written as a line holding only `{{name args}}`. Use one for everything it covers,
instead of writing it yourself.

You control one thing: **structure** — what is grouped with what, what repeats, what goes
beside what. How it is painted is the user's `THEME.md`, set up once, outside your reply.
You are the composer, not the performer: the engine lays the piece out at every width the
user has, so a `:::` row, a spacer or a spring that exists only to make one width look like a
picture you have in mind is placement; write what the content is instead.

It is harmless by construction. Markdown is text: nothing in it runs, and a link or an action
does nothing until the user clicks it. A click comes back to you as a sentence built from your
own Markdown, never as a command.

## What changes most answers

Any raw answer is safe to send: ordinary Markdown renders as it is, with nothing to add or
remove. Only a few spellings divide a line, and everything that merely looks like them is
text — write it freely, and escape nothing else:

| divides its line | never divides |
|---|---|
| a spaced ` - ` or ` \| `, in a sentence too: write ` — ` there | a colon (`Day one: the old town`, `10:30`); `well-known`, `10–12`, an en dash ` – `, an em dash ` — `, a dot ` · ` ` • `; the same characters unspaced; ` / `, `;`, ` + `, commas, parentheses |

To keep one of them as text, `\-` `\|` hold it. A label over its value is two lines: `_Owner_` above `Alex`.

Names your tools return count too: a remaster, a file name or a product name often carries
its own ` - ` or ` | `. Escape it to show the name as its source spells it
(`The Chain \- 2004 Remaster`); a link's label is never divided, so a name that is a button's
label needs nothing.

The rest of this section is the few other things that change an ordinary
answer and do not show in the source; everything after it is something you look up when you
need it.

- **A `---` between cards joins the card above it,** so that card stops matching the others
  and the run no longer grids. `___` cuts between them instead ([`structure.md`](structure.md)).
- **A list's look is the theme's.** The same `- ` items draw as a card each, as rows in one
  card with a rule between them, or as plain rows, whichever this theme draws. A `---` between
  items adds a rule of its own beside the theme's, and a `___` cuts the list into separate
  lists ([`structure.md`](structure.md)).
- **The data decides the shape, and one thing leads.** The item a page or a card is about gets
  the largest treatment, one hero number or one big picture, and everything else less. When the user asks about one of several items (the step they are on, the one stock they named), that one leads: its detail in the heaviest text, the others kept and quieter (`_…_`). Items
  the user picks by their picture (products, stays, places, albums) are cards with a large
  picture; items the user reads down (songs, transactions, messages, reviews, days) are rows
  with a small one: `- ![Title](….jpg?md2ui.max_width=48&md2ui.aspect_ratio=1:1) - **Title** : _detail_ ... value`.
- **A body over ~100 words takes the full width,** and its section's cards stack
  ([`repetition.md`](repetition.md)).
- **A link's label stays on one line.** A long title written as a button makes its card as
  wide as the title, and the run takes fewer columns; the block inside
  `[ … ](agent:open?id=7)` wraps like text and makes the whole card the target
  ([`elements/a-links-label-stays-on-one-line`](elements.md#a-links-label-stays-on-one-line)).
- **Only `agent:` links come back to you.** An `https:` link opens for the user, and both draw
  the same ([`elements.md`](elements.md)).
- **A form is one turn**: its values wait for the one button marked `md2ui.commit=1`,
  `[Add to bag](agent:add?item=7&md2ui.commit=1)`. Its quantity is `Quantity: ➖ [2/9] ➕`,
  never ➖ ➕ buttons. Its options take `md2ui.choice=<name>`, their label on its own line
  above, and ` | ` between them keeps them one control:
  `[M](agent:pick?size=m&md2ui.choice=size) | *[L](agent:pick?size=l&md2ui.choice=size)*`.
  Tabs, toggles and actions stay plain buttons, with no `md2ui.choice` and no ` | `
  ([`elements/what-a-click-does`](elements.md#what-a-click-does)).
- **A section's shape is usually a pattern, and a page's is a page.** `guide("patterns")` lists
  them, one line each; read the one that fits before writing the section. When the answer is a
  whole page of one kind — money (an account, a card, a portfolio), markets (a watchlist, a
  ticker), a catalog to pick from, one product or place in detail, a help or API article, the
  weather, a dashboard —
  `guide("pages")` names a real page of that kind: see what it leads with before you write
  yours.
- **A look is cheap and a re-read is not.** `preview` renders a page or one section before
  anyone sees it: a section for about 100–300 tokens, a whole page for up to about 1,500. It
  renders without the window; whether its pictures load depends on where md2ui runs
  ([`verifying.md`](verifying.md)).
- **A page you sent earlier holds what your tools returned then.** Under each section a tool
  filled, say where it came from and how long that stays true:
  `<!-- from: calendar.list_events; fresh: 10m -->`. A comment draws nothing. To go back,
  check before you send: `showing(message_id=…)` names the sections past their `fresh:` as
  `stale`, without changing the window. Re-read only those and `patch` each one, which also
  brings the page back. With nothing stale, `show(message_id=…)` re-sends the page as it was.

## Opened with no request

When the user only opens md2ui — "open md2ui", "show me md2ui", nothing else — read
`guide("opened")` before you answer: it says what to show.

## What each element means

You already know these components from native UI. Each row is the Markdown that gives one,
and what it tells the user. The theme decides how every one of them looks; you decide what
it means.

| component | write | means, use for | not for |
|---|---|---|---|
| paragraph | sentences, a blank line between paragraphs | an explanation, an argument, a story, advice — anything read rather than scanned, as long as it needs | values the user compares across items |
| chip / tag / badge | `` `Shipped` `` | static metadata the user scans: a status, a category, an attribute (`` `2 Bed` `` `` `Vegan` ``). Its colour is the theme's | anything the user does; anything they read, such as a sentence, a source, an address or opening hours |
| button | `[Retry](agent:retry)` | what the user came to do here — one per place they decide; a run of offers (rooms, plans) carries one per card | an action every item repeats, which is a quieter button or an icon button |
| quieter button | by its place, below | an alternative to the main one, or an action the page is not for — Later, Details, Share | the one thing the page is for |
| text link | by its place, below | a minor action, a way in that repeats on every card, or a link to another place — Skip, Learn more, a footer | the action you want taken |
| emoji badge | `⭐ - Popular`, or `⭐` on its own line | an item's identity, drawn as a badge. Its wrapper is its size, and the size follows where it sits — `guide("theme")` lists which size goes where with this theme — and `~~⭐~~` is the same badge muted. An icon that belongs to a number goes inside its tier, `___🔋 82%___`; one between two values stands between them, `__Lisbon__ ... 🚆 ... __Porto__`; one that labels a word stays in its text, `🎧 Listeners: 4,210` — [`elements/what-the-icon-does-decides-how-you-write-it`](elements.md#what-the-icon-does-decides-how-you-write-it) | decoration on lines that read clearly without it |
| icon button | by its place, below: `[▶️](/x)` | an action a glyph already names — call, message, share, like, play, close — where the page is not about it; the item's own main action keeps its words — [`elements/words-an-icon-or-both`](elements.md#words-an-icon-or-both) | anything needing a word to be clear |
| choice set | `[Yes](agent:a) *[No](agent:b)*`; in a form, with `md2ui.choice`, above | a question the user answers by tapping; peers share one wrapper | links inside a sentence |
| tappable card | the block inside `[ … ](agent:open?id=7)`: two or more glued lines, such as a bold title over its caption (one line is a button) | one item the user opens or picks | a card with several actions |
| list row | `- 🎙️ - **Hard Fork** : _Today, 58 min_ ... _[▶️](agent:play?id=41)_`: a badge or picture, a title over its detail, a value or action at the edge; `1.` items when the order is a rank | one of many items the user scans down — a transaction, a track, a message, a setting | the same attributes compared across items, which is a table |
| task | `- [ ] Review the numbers` | something the user completes | a setting's state |
| toggle | `Notifications ... [x]` | a setting that is on or off | a task |
| slider, quantity | `Volume: [65%]`, `Quantity: ➖ [3/10] ➕` | a value the user drags — a percentage, or a count whose denominator is the range | static progress—use `Elapsed: 65%`; ➖ ➕ buttons, a turn per press |
| stat | `_Revenue_` on its own line, then `$129,201.40` under it — or on one line, `_Revenue_ : $129,201.40` | a measured value with its label above it; a run of them grids as tiles | a sentence, which keeps its colon as written: `Day one: the old town` |
| hero number | `___$12,480.55___` | the one number the section is about | several numbers |
| progress bar | `Elapsed: 45%` | progress toward a known whole | a lone number; a figure with no whole (a price, a count, a total), which stays a stat, never rescaled into a percentage to draw a bar |
| chart | three or more `- Key: value` list items in one unit (`40%`, `$220.06`, `5K`), each value alone; any other unit, a count included, as bare numbers right under `Storage (GB):`, no blank line between | one measure compared across items; signed values draw gains and losses from zero | two values; ports, years or versions |
| ring | `Disk: 61/128 GB` | a part of a whole that is not a percentage | a part over a whole with no key or unit, which draws a ratio bar |
| grouped chart | a `Revenue, Cost:` line naming the series, then right under it two or more `- Q1: $10K, $8K` items, one value per series, in one unit | several measures compared across the same items, with a legend | one measure — use a chart; measures in different units |
| line | `Price: $710 (Apr 13) → $713 → $777 (Now)` — three or more values in one unit joined by `→`; a `(label)` after a value names that point — words, a date, `(Q1)`, `(6 PM)`; a unit a line does not take goes in the key, its numbers bare: `High (°C): 24 → 23 → 21` | one value over time | items with no order; a before-and-after of two values; a sequence of states |
| several lines | a `- SPY: $710 → $756 → $767` item per line, each with the same number of points in one unit | a few things compared over the same steps, on one axis with a legend | one value over time — use a line |
| table | a Markdown table | the same attributes across items | one item |
| code block | a fenced or four-space-indented block | literal source, with an explicit fence language when syntax colour helps | a status or short label—use inline backticks |
| caption | `_Available balance_` | a quiet label over or under a value | a heading |
| image | `![Harbour Lights](https://…/cover.jpg)` | a picture the data came with — a cover, a photo, a logo, a map, raster or SVG. The user's window loads it, so when your data has one, show it. Its shapes are patterns: `people`, `picture-rows`, `listing`, `photo-card` (one featured item drawn over its own photo), `profile`, `split`, `article`, `guide` | a picture you would have to invent a URL for |
| card / section | `## Title` and its lines | one topic, or one item | a single line |

For a whole section of a reply (a status list, choices, an agenda, an inbox), its pattern is
a place to start: `guide("patterns")` lists them. A pattern is a reference, not a template —
your content decides the shape, so keep what fits it and drop what does not.

`guide("theme")` says what this theme's spellings mean — the size of an icon or an action by
where it sits (a headline, a card, a row), a second kind of tag — and lists the theme's own patterns, read as
`guide("theme/<name>")`. Write only the spellings it declares, and anything else bare.

## The one rule that explains most surprises

**Whitespace, separators and heading level are not decoration — they are the layout.** These
are the ones that draw something you did not expect, and none of them shows in the source:

- a blank line ends a block;
- no blank line glues consecutive lines into one element;
- a heading owns everything until the next heading of its level or above, and `***` alone on
  a line ends its section early, so what follows stands outside the card;
- a `:::` row reaches as far as its run: a `___` above and below it bounds it, and a blank
  line does not, so without the cuts the paragraphs above and below become cells of the row
  too;
- only repeated **groups** grid — single lines stay stacked, by design, and a one-line list
  item that a separator divides is a group;
- a spaced ` - ` ` | ` ` : ` divides its line, a sentence too. `\-` `\|` `\:`
  decline a division, a comma never makes one, and prose takes an em dash (` — `), which
  never divides;
- a value is **drawn** — a chip, a bar, a ring — when its line is nothing but elements and
  values; escaping its own punctuation (`45\%`, `\$412M`) keeps it text.

If two things look wrong together, they are almost always grouped wrong. Everything else in
these notes is something you go looking for.

## Read next

Each note answers one question; `guide` with its name reads it, and `guide("<note>/<section>")`
reads one section, named by its heading — the form `lookup` points with.

| File | When |
|---|---|
| [`lookup.md`](lookup.md) | you know the result you want and need the Markdown for it |
| [`structure.md`](structure.md) | sections, blank lines, how a heading swallows, `:::` rows, springs and separators |
| [`repetition.md`](repetition.md) | you want cards in a row / a grid |
| [`elements.md`](elements.md) | any button, CTA, chip or emoji badge — separation, quoting one back to text, variants, an icon inside a button |
| [`images.md`](images.md) | any image, icon, logo, or image-as-background card |
| [`text.md`](text.md) | emphasis, stats, labels over their values |
| [`colour.md`](colour.md) | which colour an element gets, and what you write to change it |
| [`code-blocks.md`](code-blocks.md) | fenced and indented source, and lexer names |
| [`dashboards.md`](dashboards.md) | cards, two-column rows, stats, bars, charts, the bento mosaic |
| [`verifying.md`](verifying.md) | `check`, `preview`, the render loop, and what the terminal tells you |
| [`patterns/`](patterns/) | one section of a reply — `guide("patterns")` lists them, one line each |
| [`opened.md`](opened.md) | the user only opened md2ui, with no request |
| [`pages.md`](pages.md) | you are writing a whole page and want to see sections composed into one |
