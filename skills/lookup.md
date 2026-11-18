---
name: md2ui-lookup
description: A table from what you want to the Markdown that gives it — find the row, write the construct.
---

# Start from what you want

The fastest route in. Find the row, write the construct, and only if it surprises you read
the one section it names: `guide("elements/icon-buttons")` reads that section, not the note.

| I want | Write | More |
|---|---|---|
| a row / grid of cards | repeated **groups** of the same shape — a heading with its lines, or 2+ glued lines | [`repetition/only-repeated-groups-grid-and-that-is-the-control`](repetition.md#only-repeated-groups-grid-and-that-is-the-control) |
| a row of short items | put them on **one line**, separated | [`repetition/choose-the-arrangement-by-the-spelling`](repetition.md#choose-the-arrangement-by-the-spelling) |
| one-line items as a column, or as a grid | `A - B` lines stack; the same as list items `- A - B` grid | [`repetition/choose-the-arrangement-by-the-spelling`](repetition.md#choose-the-arrangement-by-the-spelling) |
| a mosaic | 3+ `##` sections, in a theme that turns on Bento | [`dashboards/the-mosaic`](dashboards.md#the-mosaic) |
| a complete account overview to start from | the worked example | [`banking-example.md`](banking-example.md) |
| a card with a title in a size no heading offers | untitled `## ` marker + `__Title__` | [`structure/an-empty-heading-marker-opens-a-section-with-no-title`](structure.md#an-empty-heading-marker-opens-a-section-with-no-title) |
| cards at one level that need different looks — white widgets beside lime features | a named style per kind: `## {#feature-1}`, `## {#feature-2}` | [`colour.md`](colour.md) |
| one loud title among small ones at the same level | the small ones stay headings; the loud one is `___…___` in a `## ` marker | [`text/choose-the-text-role-before-its-size`](text.md#choose-the-text-role-before-its-size) |
| a headline that breaks where you say | a `___…___` paragraph with `\` at the end of the line to break | [`text/choose-the-text-role-before-its-size`](text.md#choose-the-text-role-before-its-size) |
| a tall card with its content at the top, middle and bottom | `+++++` then `...` between the blocks | [`structure/on-its-own-line-pushes-blocks-apart`](structure.md#on-its-own-line-pushes-blocks-apart) |
| blank space between two blocks | `+++`, `++++` or `+++++` on its own line — small to large | [`structure/adds-space`](structure.md#adds-space) |
| a paragraph held narrower than the page | `+++++ +++++` on both sides of it, on its line | [`structure/adds-space`](structure.md#adds-space) |
| the big number | `___$12,480.55___` | [`text/three-tiers-you-can-pick-directly`](text.md#three-tiers-you-can-pick-directly) |
| two words of a headline in the accent colour | `` # 4 ways `50,000+ teams` use Weave `` | [`text/one-phrase-of-a-headline-in-the-brand-colour`](text.md#one-phrase-of-a-headline-in-the-brand-colour) |
| a stat with a label | `_Revenue_` above `$129,201.40`, or `_Revenue_ : $129,201.40` | [`text/a-label-and-its-value-write-the-label-above-it`](text.md#a-label-and-its-value-write-the-label-above-it) |
| a caption | `_Available balance_` | [`text/three-tiers-you-can-pick-directly`](text.md#three-tiers-you-can-pick-directly) |
| a value pushed to the right edge | `Subtotal ... $42.50` | [`structure/pushes-content-apart`](structure.md#pushes-content-apart) |
| one card centred while its siblings are not | `... x ...` on each of its lines | [`structure/pushes-content-apart`](structure.md#pushes-content-apart) |
| a title left, actions right | `## Title ... [`📋`](/copy)` | [`dashboards/the-card-recipe`](dashboards.md#the-card-recipe) |
| the main action, a quieter one, a minor one — by where it sits | the spelling `guide("theme")` gives its place; bare `[Go](/x)` where it names none | [`elements/an-actions-weight-and-place`](elements.md#an-actions-weight-and-place) |
| an icon **inside** a button | `[🔖 Saved](/saved)` | [`elements/an-icon-inside-a-button`](elements.md#an-icon-inside-a-button) |
| an icon **beside** a block | `⭐ - Popular` — ` - ` divides; use ` — ` in prose | [`elements/separate-it-or-it-stays-inline-text`](elements.md#separate-it-or-it-stays-inline-text) |
| an icon, link or chip to read as **plain text** | `"⭐"` — quote it to decline the badge/button/chip | [`elements/quote-an-element-to-keep-it-text`](elements.md#quote-an-element-to-keep-it-text) |
| an icon **with its number**, at the number's size | `___🔋 82%___` | [`elements/what-the-icon-does-decides-how-you-write-it`](elements.md#what-the-icon-does-decides-how-you-write-it) |
| an icon **between** two values, from one to the other | `__Lisbon__ ... 🚆 ... __Porto__` | [`elements/what-the-icon-does-decides-how-you-write-it`](elements.md#what-the-icon-does-decides-how-you-write-it) |
| the **current** or the **off** badge in a run | `🌙` ordinary · `~~🏖️~~` off · the current one bare, its emphasis in the text beside it, unless `guide("theme")` declares a spelling | [`elements/a-badges-state-is-the-same-spelling-or-muted`](elements.md#a-badges-state-is-the-same-spelling-or-muted) |
| an icon button | `[▶️](/play)`, in the spelling for its place | [`elements/icon-buttons`](elements.md#icon-buttons) |
| the user to answer you | one button per answer: `[Yes](agent:generate-report) *[No](agent:cancel)*` | [`elements/what-a-click-does`](elements.md#what-a-click-does) |
| a whole card the user taps | the block wrapped in `[ … ](agent:choose-plan?plan=team)`, two or more glued lines; one line is a button | [`elements/what-a-click-does`](elements.md#what-a-click-does) |
| a link that scrolls to a section | `[Pricing](#pricing)` + `## Pricing {#pricing}` | [`elements/what-a-click-does`](elements.md#what-a-click-does) |
| tasks the user ticks and you hear about | `- [ ] Review the numbers`, or `- [[ ]](agent:toggle-task?id=3) Send it` for your own action | [`elements/what-a-click-does`](elements.md#what-a-click-does) |
| to go back to an earlier page | note each section's source and how long it stays true under its heading, `<!-- from: calendar.list_events; fresh: 10m -->`; going back, `showing(message_id=…)` names the `stale` sections without changing the window: re-read those and `patch` each, or `show(message_id=…)` when none is stale | — |
| an answered choice, a ticked task | `mark` if your backend offers it; else re-send the response with the others `~~…~~` and `[x]` | [`elements/what-a-click-does`](elements.md#what-a-click-does) |
| to know your answer is sound before you send it | the `check` tool, or a render | [`verifying.md`](verifying.md) |
| a chip / tag row | `` `Draft` `In review` `Shipped` `` | [`text/inline-code-has-two-forms`](text.md#inline-code-has-two-forms) |
| syntax-highlighted source code | a fenced block such as ```` ```python ```` | [`code-blocks/fence-it-and-name-the-language`](code-blocks.md#fence-it-and-name-the-language) |
| a code block with a title | a `###` heading glued above the fence | [`code-blocks/fence-it-and-name-the-language`](code-blocks.md#fence-it-and-name-the-language) |
| a table with a title | a `###` heading glued above the table | — |
| tabs, a selector, "show more" | `agent:` buttons; you re-send the page in the new state | [`elements/tabs-a-selector-show-more`](elements.md#tabs-a-selector-show-more) |
| the figure the user is not looking at, beside the one they are | its key muted, its value kept: `_🛌 Sleep_: ___7h 10m___` beside `👟 Steps: ___8,204___` | [`elements/tabs-a-selector-show-more`](elements.md#tabs-a-selector-show-more) |
| a day tile — weekday over the number | `Mon-15` — detected, not marked up | [`dashboards/a-token-grid-calendars-heatmaps-seat-maps`](dashboards.md#a-token-grid-calendars-heatmaps-seat-maps) |
| **blocks side by side** | a `:::` between them, and a `___` above and below | [`structure/puts-blocks-side-by-side`](structure.md#puts-blocks-side-by-side) |
| one cell wider than another | `:::2` — the number sizes the cell above it; close the row with `___` | [`structure/puts-blocks-side-by-side`](structure.md#puts-blocks-side-by-side) |
| a label that just fits, beside a body | `:::0` — no share, shrink to content; close the row with `___` | [`structure/puts-blocks-side-by-side`](structure.md#puts-blocks-side-by-side) |
| text beside a picture | the picture, a `:::`, then the text, then a `___` to close the row | [`structure/puts-blocks-side-by-side`](structure.md#puts-blocks-side-by-side) |
| a long answer in sections that each look different | one untitled `# {#name-1}` band per section, each closed with `***` | [`structure/a-page-of-sections-that-each-look-different`](structure.md#a-page-of-sections-that-each-look-different) |
| columns of links — a site map, a footer | `###### Title` + one link per line, per column | `patterns/directory` |
| an icon beside a label, **inside a list item** | indent the `:::0` to the item's column — the item ends the row | [`structure/a-acts-on-the-level-it-is-written-at`](structure.md#a-acts-on-the-level-it-is-written-at) |
| a row that stops swallowing what follows | a `___` after it — a row ends at a cut, never at a blank line | [`structure/cuts-a-run-only-paints-one`](structure.md#cuts-a-run-only-paints-one) |
| the same row repeated, as a grid | close each row with `;;;`, not `___` — `___` stops the grid | [`structure/puts-blocks-side-by-side`](structure.md#puts-blocks-side-by-side) |
| blocks at the **top and bottom** of a cell | a `...` line between them | [`structure/on-its-own-line-pushes-blocks-apart`](structure.md#on-its-own-line-pushes-blocks-apart) |
| a photo card with a title on it | markdown in the alt slot, styled on the **heading level** | [`images/image-as-background-cards`](images.md#image-as-background-cards) |
| a bookmark in a photo's corner | a link as the alt slot's **first child**, on a `...` spring | [`images/a-badge-over-the-photo`](images.md#a-badge-over-the-photo) |
| an icon at its real size | `?md2ui.max_width=56&md2ui.aspect_ratio=1:1` | [`images/an-icon-needs-two-params-not-one`](images.md#an-icon-needs-two-params-not-one) |
| an album, playlist or podcast cover | `?md2ui.aspect_ratio=1:1`, the cover first in its card | [`images/a-picture-card-the-user-opens`](images.md#a-picture-card-the-user-opens) |
| cards that each have a picture | an untitled `### `, the picture, then the title in `**bold**` — every picture starts at the same height | [`images/choosing-the-pictures-treatment`](images.md#choosing-the-pictures-treatment) |
| a gallery: several pictures of one subject | one large beside four, `::: 1 >`, every picture `4:3`; or lines of one, two, three pictures | [`images/a-mosaic-of-pictures`](images.md#a-mosaic-of-pictures) |
| a photo's ratio, circle, size and place | seven questions on the context: what the item is, is it someone, is it the subject, how many lines, repeated, what kind of answer it is, how far it may widen | [`images/choosing-the-pictures-treatment`](images.md#choosing-the-pictures-treatment) |
| a progress bar | `Elapsed: 45%` | [`dashboards/which-figure-each-spelling-draws`](dashboards.md#which-figure-each-spelling-draws) |
| a form's quantity and options, sent by its one `md2ui.commit=1` press | `Quantity: ➖ [2/9] ➕`, never ➖ ➕ buttons; each option with `md2ui.choice=size`, ` \| ` between them; tabs, toggles and actions stay plain buttons | [`elements/what-a-click-does`](elements.md#what-a-click-does) |
| a bar that moves while the page stays | `mark(message_id, key="Elapsed", value=60)` | [`elements/what-a-click-does`](elements.md#what-a-click-does) |
| a value a process you run changes while the page is shown: a stage, an arrival time | `[3:53 PM](feed:arrives)`, `` [`Preparing`](feed:status) ``, then `feed` | [`elements/a-value-a-process-changes-while-the-page-is-shown`](elements.md#a-value-a-process-changes-while-the-page-is-shown) |
| which figure a number draws | the spelling picks it: *Which figure each spelling draws* | [`dashboards/which-figure-each-spelling-draws`](dashboards.md#which-figure-each-spelling-draws) |
| a bar chart | three or more `- Key: value` list items in one unit (`40%`, `$220.06`, `5K`); any other unit, a count included: bare numbers under `Storage (GB):` | [`dashboards/stats-bars-and-charts`](dashboards.md#stats-bars-and-charts) |
| several measures per item, as a grouped bar chart | a `Revenue, Cost:` line, then two or more `- Q1: $10K, $8K` items, one value per series | [`dashboards/stats-bars-and-charts`](dashboards.md#stats-bars-and-charts) |
| a share of a whole, as a ring | `Disk: 61/128 GB` — a part over a whole with a unit or key; `68/100` alone is a ratio bar | [`dashboards/which-figure-each-spelling-draws`](dashboards.md#which-figure-each-spelling-draws) |
| a value over time, as a line | `Price: $710 (Apr 13) → $713 → $777 (Now)` | [`dashboards/which-figure-each-spelling-draws`](dashboards.md#which-figure-each-spelling-draws) |
| several values over time, on one axis | a `- Key: a → b → c` item per line, each with the same number of points | [`dashboards/which-figure-each-spelling-draws`](dashboards.md#which-figure-each-spelling-draws) |
| a settings toggle at the far edge | `Label ... [x]` | [`dashboards/checkboxes-and-switches`](dashboards.md#checkboxes-and-switches) |
| an interactive 0–100 value | `Label: [65%]`; linked: `[[65%]](agent:set-value)` | [`dashboards/sliders`](dashboards.md#sliders) |
| a calendar / heatmap | a table whose every cell is a chip | [`dashboards/a-token-grid-calendars-heatmaps-seat-maps`](dashboards.md#a-token-grid-calendars-heatmaps-seat-maps) |
| a coloured rule beside or above each row | a `> ` blockquote per row, blank lines between | [`dashboards/a-row-with-a-coloured-gutter`](dashboards.md#a-row-with-a-coloured-gutter) |
| a tinted / alternating row | a `- ` item per row | [`dashboards/a-row-with-a-coloured-gutter`](dashboards.md#a-row-with-a-coloured-gutter) |
| a coloured token beside or above each list item | a `- ` list | [`dashboards/a-row-with-a-coloured-gutter`](dashboards.md#a-row-with-a-coloured-gutter) |
| a divider | `---` — `___` paints nothing, it is the run cut | [`structure/cuts-a-run-only-paints-one`](structure.md#cuts-a-run-only-paints-one) |
| these cards NOT to grid / to break 5 into 2+3 | a `___` between them | [`repetition/is-the-off-switch-and-the-way-to-shape-a-run`](repetition.md#is-the-off-switch-and-the-way-to-shape-a-run) |
| cards that refuse to grid | check every item is a group — a long body takes the full width by design | [`repetition/the-orphan-rule-4-items-often-become-2-2`](repetition.md#the-orphan-rule-4-items-often-become-2-2) |
| this band to end here | `***` | [`structure/ends-a-section`](structure.md#ends-a-section) |
