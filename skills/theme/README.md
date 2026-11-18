# Theme material, parked

**Not a skill yet.** The theme side of `skills/` is written once the default `THEME.md` is
finished (owner decision, 2026-09-17), and a Claude Code skill will point at this folder when a
user asks for help with a `THEME.md`. `guide` does not serve this folder, so the LLM writing a
response never reads it.

Until then this file holds, **verbatim**, the theme material taken out of the response notes on
2026-09-17, each passage under the note it came from. It is source material, not a finished
note: passages overlap `THEME_GUIDE.md`, and some were written for the response writer's voice.
The deleted `skills/theme.md` is in git at `69e903af^`.

## From `skills/README.md`

**It displays a plain Markdown answer in a UI-like way.** The goal is a result that is
*good enough to drop into an existing design system* — not a replacement for one. The user
supplies a base `THEME.md` that carries their brand: their fonts, colors, radii, spacing.
Your job is to write Markdown whose **structure** the renderer can read, and — when asked —
to **extend** that theme with the few keys the content needs, in the user's own style.

So there are two things you can control, and only two:

| | how | governs |
|---|---|---|
| **Structure** | the Markdown you write | what is grouped with what, what repeats, what goes beside what |
| **Style** | `THEME.md` | how any of it is painted |

Almost every disappointing render is a *structure* problem being blamed on style. Get the
document shape right first.

---

| a toggle switch | `- [x]`, styled by `### Task controls` |
| an agenda with a coloured bar down each row | a `> ` blockquote per row, styled by `### Quotes` → `#### Marker` |
| a calendar header — weekday over the number | `Mon-15`, detected as a day chip |
| a row with its own tinted pill behind it | a `### ` section per row, tinted by a `Background color:` list |

---

| a mosaic | 3+ `##` sections and `Layout: Bento` on `### Root` | [`banking-example.md`](banking-example.md) | complete account overview: Markdown, theme, and two rendered widths |
| [`dashboards.md`](dashboards.md) |

---

| two words of a headline in the accent colour | `` # 4 ways `50,000+ teams` use Weave `` + `Marker text color` | [`text.md`](text.md) |

---

| a round icon button | `[▶️](/play)` + `Emoji shape: circle` | [`elements.md`](elements.md) |

---

| a coloured rule beside or above each row | a `> ` blockquote per row + `### Quotes` → `#### Marker` | [`dashboards.md`](dashboards.md) |
| a tinted / alternating row | a `### ` per row + a `Background color:` list on that level | [`dashboards.md`](dashboards.md) |
| a coloured token beside or above each list item | a `- ` list + `### Unordered Lists` → `#### Marker` | [`dashboards.md`](dashboards.md) |

---

 Override the level with `Heading level:` under `## Content arrangement` >
`### Bento` in the `THEME.md`.

---

## From `skills/elements.md`

**Declare `Links Text` under `## Text Styles` before you use it.** Every variant falls back to
Primary's values, font colour included — so a theme whose Primary is a black pill with a white
label renders its plain text links white on the page, invisible. It reads as the variant not
being applied.

---

A link whose label is **only** an emoji keeps its wrapper's variant but takes that variant's
`Emoji shape`, so with `Emoji shape: circle` it draws as a round badge rather than a rect
pill.

---

Two things come from the theme, and both are worth setting once:

- **the emoji font** — `## Emoji styles` → `Font:`, which is what gives you a consistent icon
  set across the whole document. Emoji and common Unicode symbol ranges use it in prose, mixed
  link labels, emoji-only buttons, and standalone badges alike;
- **the badge shape** — `Shape: circle | square`, declared per variant, so every Primary badge
  matches and a Secondary can differ.
- **the badge surface** — `Background color`, `Background image`, `Background gradient`,
  `Outer shadow`, `Inner shadow`, radius, padding, and stroke use the same layered background
  painter as buttons and standalone chips. The image is cover-fitted and clipped to `Shape`.

## Where an emoji's colour comes from

Separation decides whether you get a badge. **Context then decides which block styles it**, and
`## Emoji styles` has one per context. Measured 2026-09-03, one theme colouring each block
differently:

| written | drawn as | styled by | colour key |
|---|---|---|---|
| `⭐` alone, in a run, or separated (`Prose - ⭐`) | a **badge** | `### Primary` — wrapper picks `### Secondary` / `### Tertiary` / `### Quaternary` | **`Icon color`** |
| `⭐ Popular today` | an inline glyph at text size | `### Text` | `Color` |
| `[⭐](/x)` · `[⭐ Save](/x)` | inside the button | `### Link` | `Color` |
| `` `⭐` `` · `` *`⭐`* `` | inside the chip | `### Inline` | `Color` |

> **Correction, 2026-09-17** — two behaviours above have moved since that measurement. The
> passage is left as written because this file is a verbatim archive; `THEME_GUIDE.md` carries
> the current text.
>
> * **`### Text` has a second way in.** A quoted element — `"⭐"`, `"[Docs](/d)"`,
>   `` "`code`" `` — is the author declining the badge, button or chip, so it draws from the
>   in-text block at the surrounding size. The quotes are consumed.
> * **`Color` under `### Text` is a DEFAULT, not an override.** A glyph in styled text takes
>   that text's ink — a `## Text Styles` tier, a table role, a heading, a K-V role, a
>   `## Fixed colors` text pin — so `_Muted text with an emoji_` paints the glyph muted, even
>   when a tier's colour is the same as body text's. Plain body text, bold or italic included,
>   keeps the emoji tint. A per-glyph `### Emoji` pin outranks everything.

Three things worth holding onto:

- **The badge blocks take `Icon color`; the other three take `Color`.** Writing `Color:` under
  `### Primary` is silently nothing — the badge keeps its authored ink. The badge blocks are
  also the only ones with geometry (`Shape`, `Size`, `Padding`) and background layers, because
  only a badge has a surface of its own.
- **A chip's variant does not reach the emoji inside it.** `` `⭐` `` and `` *`⭐`* `` paint the
  *pill* from `## Inline Code` → `### Secondary`, but the glyph in both comes from
  `### Inline`. Same for a link: the button changes variant, the glyph does not.
- **`## Fixed colors` → `### Emoji` reaches all of them and outranks all of them** — including
  an emoji that opens a heading, which none of the four context blocks touched. So the pin is
  the lever for "this glyph is always this colour", and the four blocks are for "emoji in this
  role look like this".

With the pin plus `### Emoji background`, a badge becomes a brand-coloured disc — glyph and
disc pinned separately.

---

## From `skills/images.md`

A separator between them (` - `, ` | `) is allowed and keeps the row; it is drawn
or hidden by `## Separators`, exactly as it is between chips or buttons.

Space the row with `Image row spacing` under `### Elements`; `Image col spacing` is the
stacked case. Both default to 0, so a run of images sits flush by default.

---

Two things that are not obvious:

- **Style a photo card on whatever section encloses it.** `### Image Cards` answers only when
  none does — a card at the top level of the document. Put it inside a `## ` marker, as a card
  board does, and `### Heading 2` owns it: radius, padding, scrim and stroke all go there, and
  `### Image Cards` has no effect. Measured both ways, so check which shape you have before
  hunting for a key that is not being read. A top-level photo card in a theme with no
  `### Image Cards` falls back to `### Elements`: it draws its photo with that padding, and
  no radius, stroke or scrim.

  If that owning theme block also declares `Background image`, it is only a
  fallback for an image card: the photograph URL authored in the Markdown wins
  as soon as it loads. Both use centered cover cropping. Theme background
  images do not accept the Markdown image query parameters for `contain`,
  alignment, bleed, or corner radius; those parameters style image elements,
  while the owning theme block styles the card background.

  A matching heading ID fixed style (`{#name-1}` selected by `#### Name`) can be
  that owning block too. Its `Background image` behaves exactly like a heading
  level's image; the Markdown photograph still has the same precedence.

  That level is shared with the document's other cards, which is an advantage worth using. One
  `Stroke color: #FFFFFF` there frames every photo card the way a media card is usually drawn,
  and stays invisible on the pale cards beside them, because white on a white pane does not
  show — one declaration, both results.
- **Theme background images also paint element surfaces.** Put `Background image` inside a
  button variant under `## Links`, a chip variant under `## Inline Code`, or a badge variant
  under `## Emoji styles`. Each image is centered, cover-fitted, and clipped to that pill or
  badge shape; it sits above the solid color and below the gradient.
- **The card's height comes from its content**, so two lines of text behind a photo give a
  letterbox. A `+++++` spacer at the top of the card's alt text reserves room for the
  picture, and `Spacer large` under `### Image Cards` says how tall; without it a photo card
  is short.
- **A spacer the theme does not size scales with its level's group gap**, and never drops
  below 8/16/32 down (8/12/16 across). State `Spacer <step>` on a level, or under `### Root`,
  where a spacer must be an exact size.

---

Here Heading 4 supplies the photo card's radius, padding, and gradient. Filled
buttons and chips retain their own color contexts. Keep attribution and license
links outside the photo-card run when reusing photographs that require credit.

---

## From `skills/text.md`

Every `Key: value` pair uses **`Key` for its key and `Value` for its value** under
`## Text Styles`. These are independent of the three authored underscore tiers —
`Muted`, `Lead`, `Display` — so changing `Display` does not resize pairs, and changing
`Value` does not resize `___…___` text. State neither and a key keeps its automatic
`Text Overline` and a value stays ordinary body text.

A key on a heading line uses `Heading{N} Overline` instead, with the value at that
heading's size. Percentages and unit ratios can draw bars or rings; a link, a backtick
chip and an image keep their own styling wherever they sit. Nothing about what a value
says changes how its pair is styled.

---

| Intent | Markdown | Block under `## Text Styles` |
|---|---|---|
| Section title | `## Balance` | `Heading2` |
| Authored hero figure | `___$12,480___` | `Display` |
| Supporting lead | `__Ready for your next trip.__` | `Lead` |
| Caption | `_Available this month_` | `Muted` |
| Inferred stat | `Income: $4,250` | `Key` and `Value` |
| Ordinary text pair | `Owner: Alex` | `Text Overline` and body text |
| Status chip | `` `Draft` `` | `Inline Code` |

---

Set `Display` to the hero size and `Key` / `Value` to the supporting sizes in the
user's theme. Use underscore wrappers

---

The thing you reach for when a design sets two words of a title in the accent colour, and the
one people conclude is impossible. Emphasis is a weight, not a colour, and `## Color
Replacements` keys on a colour rather than on a span — but an inline `` `code` `` span that
**stays inside the text** is a *marker*, and a marker keeps its block's family, size and weight
and takes its own two colours:

```md
# 4 ways `50,000+ teams` use Weave to get more done each week.
```

```md
Heading1
- Marker text color: #E85D3C
- Marker background color: #00000000
```

Transparent background recolours the phrase; an opaque one highlights it. Set the pair per
block — a heading level that sets neither falls back to `Text`'s, and leaving them out
everywhere means markers just draw as ordinary text.

The span has to stay *inside* the line: give it the line to itself and it is a chip instead
(see below). Both keys take a bullet list and cycle, like every other colour key.

---

## From `skills/code-blocks.md`

## Extend the user's theme; do not replace it

Code-block typography is an independent `## Text Styles` role. Load the family under
`## Fonts` when it is a bundled font:

```md
## Fonts
- assets/fonts/IBMPlexMono-Regular.ttf

## Text Styles
Code Block
- Font Name: IBM Plex Mono
- Font size: 13
- Font weight: 400
- Font color: #24292F

## Code Blocks
Syntax style: sas
Background color: #F4FFF2
Corner radius: 12
Padding: 16
Line spacing: 4
```

`Syntax style` is a Pygments style name. Pygments supplies colours for tokens the style
defines. `Code Block` → `Font color` supplies every token for which that style defines no
colour—often ordinary names and text—and all text when the language is absent or unknown.
Choose it for contrast with `Background color`; a light fallback on a light surface remains
light even when the Pygments palette has dark keywords. md2ui deliberately uses the theme's
background rather than the Pygments style's background.

An unknown syntax style falls back to Pygments' `default`. The font family, size, weight,
surface colour, radius, padding, and line spacing still come from `THEME.md`.

---

Before sending, render one known-language block and one plain block. Check ordinary names as
well as colourful keywords: the ordinary names are what reveal a poor fallback colour.

---

## From `skills/dashboards.md`

An agenda, a timeline, a task list, a "what changed" list — anywhere a row wants a coloured
rule or token. A nested `#### Marker` on that row's own background level draws beside the row
by default or above it with `Aside: no`; leave the marker block out and nothing changes.

---

```md
## Background styles and Spacing
### Quotes
#### Marker
Bar width: 3
Bar length: 50
Bar color: #34C759
Space: 12
Aside: yes
Alignment: top
```

---

`Bar color` accepts one colour or a list. A list advances once per blockquote
and restarts in the next enclosing heading section; consecutive `>` lines are
one blockquote and therefore share one colour. `Space` is the gap to the content, and ` - ` with `Dash: hide` under
`## Separators` gives the "time, then title" pair inside each row.

With `Aside: no`, the same bar becomes a horizontal rule above the quote. `Bar width` remains
its thickness and `Bar length` (50px by default) sets its length. For an aside marker,
`Alignment: top | center | baseline | bottom` aligns against the whole row body; a full-height
quote bar is already stretched and therefore has no visible vertical alignment change.

---

```md
## Background styles and Spacing
### Unordered Lists
#### Marker
Shape: square        # circle | square
Size: 8
Color: #34C759
Space: 12
Aside: yes
Alignment: center
# Emoji: 🔹          # a glyph instead of a shape; Color tints the glyph
```

`### Numbered Lists` with its own `#### Marker` is the same idea for `1.` items, styling the ordinal as text
(`Number format`, `Font size`, `Font color`). `### Task Lists` can declare its own bullet marker;
otherwise it inherits the Unordered Lists marker. A drawn task control suppresses that extra
marker. All markers default to off, so a plain list keeps its plain bullet until you ask.

Numbered headings work the same way, but only from the exact `### Heading 1`–`### Heading 6`
background level that owns them. A `## 2. Plan` heading can therefore have a marker without
changing `### 2. Detail` or ordinary numbered-list rows.

Marker paint also passes through `## Color Replacements` on the marker's actual background.
Shapes and quote bars use `Fill color`; ordinals, quote characters and emoji markers use
`Text color`. This distinction lets one surface repair the contrast of either kind explicitly:

```md
## Color Replacements
On background color: #102A43
- Fill color: #34C759, Replacement: #B8F2D0
- Text color: #34C759, Replacement: #B8F2D0
```

**A tinted row — an ordinary list, painted by its level:**

---

```md
### Unordered Lists
Corner radius: 14
Padding: 12
Background color:
- #F2F2F7
- #FBE9E7
- #E8E9FB
```

`## Background styles and Spacing` has a paint level for each kind of row —
`### Unordered Lists`, `### Numbered Lists`, `### Task Lists` and `### Quotes` — and they take
the same keys as a heading level: background, gradient, stroke, radius, padding, shadows. The
markdown stays an ordinary list; nothing is annotated.

**The colour list is dealt per item, and restarts inside each section**, so three rows take
three tints and a second calendar card tints the same way with no extra key. That is the same
rotation the cards use, one level down.

**`### Task Lists` inherits the whole `### Unordered Lists` style until it declares its own.**
That is the sensible default and it is also the thing to check first: switching on list
backgrounds restyles every `- [ ]` in the document at the same time. If the checkboxes should
stay plain, say so on their own level rather than weakening the list you wanted:

```md
### Task Lists
Background color: #00000000
Corner radius: 0
Padding: 0
```

Reach for these when a row wants a **fill** rather than a marker beside it — an agenda, an
alternating list, a status row.

An agenda usually wants a date above its rows, and that is a day chip: write `Mon-15` and
`### Dates` draws it (see *Stats, bars and charts*).

---

- **A stat with a delta**: separate the parts — `___$847M___ - ⬆️ 12% - vs. Q3 2023`.
  Colour the arrows with `## Fixed colors` → `### Emoji` using the `datapoints` scope, so
  the arrow *and* the number beside it go green or red together.
- **A labelled bar per row**: a `Key: n%` run renders as `### Key Value Bars`.

---

- **A day tile**: `Mon-15` — or `Jun-15` — draws as a day chip, the weekday or month
  uppercased above the number, styled by `### Dates` / `### Date Key` / `### Date Day`. That
  is the whole calendar-widget header: one word of markdown, no emphasis wrappers, and
  `Background color: #00000000` on `### Dates` gives the same thing with no tile behind it.

---

**Render a datapoint family before you switch it off.** Each `### <Family>` block under
`## Datapoints` takes `Enabled: no`, and it is tempting to reach for that the moment a value
draws when you wanted text. Two reasons not to, in order: the per-instance opt-out is in the
*document* — do not separate the value, or escape the separator (see
[`structure.md`](structure.md)) — and the family may be drawing the very thing you were
about to hand-build. A board copied `### Dates` → `Enabled: no` out of another theme and then
built its two date headers out of `_MON_` + `___15___`; `Mon-15` was the same picture.
Inheriting a theme inherits its opt-outs, and those were decisions about a different
document.

Bar weight is **per family** and does not inherit. The bar families all live under
`## Datapoints` — `### Ratio Bars` and `### Key Value Bars` each take `Thickness` there, and
`## Charts` is its own top-level block taking `Bar thickness`; with `Bar width: fill` that is
the minimum, and vertical bars widen to share the chart, `Bar spacing` apart.
`Corner radius: 0` means **square**, like every other fill; half the thickness is the pill.

Usually you set them all to one value so the figures agree. But the same fact is a **lever**
when a document genuinely needs two bar weights: the family is chosen by how you *write* the
number, so a bare ratio and a K-V percentage draw from independent blocks.

```md
68/100            → ### Ratio Bars        (a fat lime charge bar)
Elapsed: 45%      → ### Key Value Bars    (a thin scrubber)
```

Writing the number differently is how a document gets a second bar weight.

`### Key Value Bars` also has independent `Show key: yes|no` and
`Show value: yes|no` controls. Both default to `yes`; set both to `no` when the
bar itself is the complete display, such as a media scrubber.

**A bar's colours follow the card it lands on.** Its fill and its track are background-aware,
like a ring's arc, so one declaration under `### Key Value Bars` / `### Key Value Bar Track`
plus a rule in `## Color Replacements` gives a figure that reads on a white card and a dark one
without per-card styling. Declare the colours for your commonest background and write one rule
for the exception.

---

An ordinary pair (`Duration: 08:21`) and an **authored** hero (`___53min___`) are styled
independently, which is what lets one card carry both:

| what | styled by |
|---|---|
| `Duration: 08:21` — every pair, uniformly | `## Text Styles` → `Key` and `Value` |
| `___53min___` — authored | `## Text Styles` → `Display` |
| `_Arrival in_` — authored caption | `Muted` |

So write the two or three numbers that should shout as `___x___`, leave the supporting
figures as ordinary `Key: value`, and size the two families apart in the theme. Measured on
a 16-card board: a 36px `Display` over a 12/17px `Key`/`Value` footer.

`Key` / `Value` reach every pair, so the choice is the theme's and it is the same one all the
way down. A theme that states neither leaves keys on `Text Overline` and values on `Text`.

---

`Layout: Bento` on `### Root` tiles one heading level into a Mondrian mosaic. It picks the
shallowest level with three or more sections in a row, or you name it under
`## Content arrangement` → `### Bento` → `Heading level: N`.

---

**And no theme key widens a cell — that follows from the solve.** A cell's width is an output
of the packing, so a key that asked for one would be another constraint on the puzzle rather
than a lever over it: it would remove arrangements from the search space, and what came back
would be the best of what was left, not what you asked for. This is the same reason a card's
own minimums cost you columns.

Measured on a 15-card board, all rendered at 1600px:

| tried | result |
|---|---|
| `Heading 2` → `Padding` 22 → 44 | usable width per card fell 265px → 221px — padding is taken *out* of the cell |
| `Root` → `Spacing` 20 → 56 | no change to cell width at all |
| `Max width` 1600 → 1400 → 1200 | cells did not widen; the packer re-solved and a *different* card ended up the narrow one |

Cell width falls out of the solve.

---

**Turning Bento off is not the escape hatch it sounds like.** Without it the same 15 sections
stack as full-width bands — each one does get the whole measure, and that is exactly the
problem: a card's image scales to the band, so the map that read at 265px becomes a
1560×750 hero, and the page went from 866px tall to 5519px. (Structurally identical siblings
still grid on their own — the two weather cards went 2-across with no Bento at all; see
[`repetition.md`](repetition.md).) Stacking is right for a document that reads top to bottom.
For a board of widgets, Bento is what makes the cards card-sized, and the way to give one card
room is to write fewer of them.

---

`## Datapoints` → `### Task controls` styles them (`## Drawing elements` is the same block
under another name), and `Type: checkbox | switch`
decides the shape for the whole document, so pick the one the answer's controls are. The
four state blocks (`### Checked outer` / `### Checked inner` / `### Unchecked outer` /
`### Unchecked inner`) take the ordinary background-card paint keys, which is how a switch
gets its brand-coloured track and white knob.

`Corner radius` on either outer state overrides the `### Task controls` radius
for that state. The inner shape keeps the same geometry rule: its radius is the
resolved outer radius minus `Padding`.

**A control is two nested shapes, and there is no tick glyph.** The outer is painted first and
the inner is drawn on top of it, inset by `Padding` — which is the switch's track and knob, and
is also what a checkbox is made of. So the inner decides what a checked box looks like:

```md
### Checked outer
Background color: #0A84FF
### Checked inner
Background color: #FFFFFF     → a blue ring with a white centre
### Checked inner
Background color: #00000000   → a solid blue box
```

If you were expecting a checkmark, that is the thing to know — pick the pair of colours that
reads as "on" rather than looking for a tick. Which layer carries the brand colour gives you
four looks from the same two keys:

| `### Checked outer` | `### Checked inner` | reads as |
|---|---|---|
| brand | white | a ring |
| brand | transparent | a solid tile |
| white + a brand `Stroke color` | brand | the inverted "selected" mark |
| transparent + a stroke | transparent | an empty outline (what an unchecked control usually wants) |

**`Padding` is the inset between the two shapes, so it is the lever that makes the mark read.**
With no tick glyph, it is doing the job the checkmark does elsewhere. Measured on a `Size: 22`
control: `Padding: 3` leaves a 3px rim and reads as a solid tile; `Padding: 6` leaves a clear
margin and reads as a square mark inside a box. Roughly 3–7 is the useful range at that size —
worth one render, because the two ends look like different controls.

Those four blocks are **background-aware**, so a control keeps its contrast wherever it lands:
a rule in `## Color Replacements` reaches each layer, and the outer layer becomes the
background the inner one resolves against — which is what keeps a white knob visible after its
track has been flipped for a dark card.

Rules are stagewise: if the card changes the outer track color, write the knob's rule under that
**resolved track color**, not under the card. A fully transparent control layer contributes no
context; the next visible surface behind it remains authoritative.

---

The theme's `## Drawing elements` → `### Sliders` selects `Style: thick|line`,
`Axis: horizontal|vertical`, length, thickness, radius and handle dimensions.
`### Slider Track`, `### Slider Bar`, and `### Slider Handle` take the shared
background paint keys. The Bar shares the Track's bounds and is clipped to its
rounded shape; sliders have no separate `Padding` or inset setting.

---

**Author the per-token state in the cell, as a wrapper.** It is tempting to pin it in the
theme with `## Fixed colors` → `### Badges` → `#### Exact`, but a pin keys on the chip's
*label*, which is global.

---

Style them under `## Inline Code` → `### Secondary` … `### Septenary`, with
fonts under `## Text Styles` → `Inline Code <Variant>`. Two grids then keep their own states
with no theme change at all. Each chip variant may use the full background stack—solid
`Fill color`/`Background color`, cover-fitted `Background image`, gradient, outer/inner
shadows, and stroke—without changing how the wrapper selects that state.

---

Pins are still right for a label that means one thing across the whole document: a
`Sold out` badge, a `⬇` trend chip.

### Three more things that cost a render each

- **A `Stroke color` paints nothing** unless `## Inline Code` itself carries a non-zero
  `Stroke width`. Set `Stroke width: 1` with a transparent `Stroke color` there, so only the
  variant that wants a ring shows one.
- **Column alignment is authored in the delimiter row**, not in the theme. A token grid wants
  `:---:` — the chips vary in width and drift off the header otherwise.
- **Set `Stacking cards: no`** on `### Table`, or a narrow cell flips the table into
  one card per row and the calendar becomes a list of seven-field records. The key also
  sets how narrow the PAGE may get: with `yes` it keeps shrinking until one card no longer
  fits, with `no` it stops at the grid's own width and scrolls sideways instead.

---

- [ ] one bar thickness across every family you use
- [ ] `Horizontal align` set on the level rather than restructuring the markdown

---

- [ ] bar and control colours checked on every card background they land on
- [ ] rows that want an accent written as `> ` per row or `- ` items, with a nested
      `#### Marker` on the matching background level
- [ ] a bento board sized by card COUNT, not by `Max width`

---

## From `skills/verifying.md`

so there is no intermediate file to keep in step: a document edit and a theme edit are both
just a re-run, a second or two. `THEME.md` is found beside the document; `--theme` picks another.

That is the most useful habit in this file: **iterate by re-rendering.** Colours, sizes, radii,
spacing, bar weights, alignment — each is one fast command, so try three versions rather than
reasoning about one.

The split mirrors the one in [`README.md`](README.md): *structure* is the document, *style* is
the theme. Knowing which one you are adjusting is most of the speed.

---

## Checking a documentation-only edit

When adding comments to a rendered sample, the intended result is unchanged output.
Preserve a before render, and after the edit render again with
the same theme, fonts, assets, width, and scale. Compare both a wide and narrow view:

```sh
shasum -a 256 before-1440.png after-1440.png
shasum -a 256 before-767.png after-767.png
```

Matching hashes prove those images are identical. If they differ, check whether
comment placement changed blank lines or interrupted consecutive content before
adjusting the theme. The [annotated Daylight template](Daylight-theme/content.md)
contains per-card exercise notes whose addition preserved both rendered images.

For an intentional visual edit, inspect the before/after images instead of
expecting matching hashes. Confirm the requested change and check surrounding cards.

---

## One rule per background, and a whole board is legible

`## Color Replacements` is the highest-leverage block in a theme, and the reason is how it is
scoped: it keys on the **nearest visible surface** — the pill, else the card, else an enclosing
section, else the page. Only that context's rules apply; a missing rule leaves the paint alone
rather than falling through to an outer surface.

One rule covers everything sitting directly on that colour: prose, headings, button labels,
chip fills, emoji tints, and the rules between blocks. A visible card fill establishes its own
context even when it declares no replacements; only a fully transparent fill exposes the layer
behind it.

Check nested paint one layer at a time. The parent surface selects a pill/component fill; after
that fill is replaced, its **resolved color** selects rules for the label or inner shape. If an
inner color looks wrong, add the rule to that resolved surface—not to the card farther out.
Never target `#00000000`: transparent cards, cells, pills and drawing layers are absent from the
context stack.

What it governs is the paint *on* a background — text, button and chip fills, strokes inside a
card, emoji tints, rules, and the card's own stroke. Card chrome resolves against the card's
image or solid fill before the enclosing surfaces. A card's own **fill** is what selects a rule,
so that fill stays the theme's job (see [`images.md`](images.md) for the white-stroke case).

It also means **each surface can answer for itself** — which is exactly what you want on a page
with its own background:

```md
### Root
Background image: gradient.jpg

## Color Replacements

On background color: image
- Replacement: #FFFFFF          # the photo cards

On background color: #FFFFFFAA  # the cards on the page background
- Replacement: #2B2B2F
```

The page-image rule reaches unfilled page content and photo cards. Glass cards are independent
because their fill establishes context; add a card-fill rule only for colors that should change
on that surface.

## Did that key do anything? Render it twice

The question you will ask most often about a theme is whether a declaration landed, and the
only reliable way to answer it is **two renders that differ in that one key**, compared:

```
uv run md2ui render content.md --theme THEME.md            --out with.png
uv run md2ui render content.md --theme THEME-without.md    --out without.png
shasum -a 256 with.png without.png
```

Identical hashes mean the key changed nothing. Different hashes mean it did, and the diff tells
you *where* — which matters, because many effects are confined to a few pixels you would not
think to look at. An inner shadow only touches the inside rim; a pin only touches one glyph; a
gutter marker only the left edge. Sampling one spot and finding it unchanged proves nothing
except that you sampled the wrong spot.

This is worth the extra render every time. Reading a single point cost three wrong "this key is
inert" conclusions in one session, each of which took longer to undo than the A/B would have
taken to run.

Every render regroups the document, so an A/B is seconds whether it varies the theme or the
Markdown.

## Before the first render: map content to its theme

Check only the constructs your document uses. Start with the user's existing theme;
add missing styling without replacing their fonts or palette.

| Authored construct | Check in `THEME.md` |
|---|---|
| A box around content | A heading level (`### Heading N`) or a named fixed style. `### Elements` only pads and spaces the cards inside it; it draws no fill, stroke, radius or shadow |
| `##` sections used as cards | `Heading 2` owns the surface; an ordinary card never paints, so nothing doubles it |
| Nested panel | Its heading level or named fixed style owns its surface; close the section with `***` if following content belongs outside it |
| Photo card | Identify the owning heading/card style before setting the scrim, radius and padding (the room for the photo is `Spacer large` under `### Image Cards`); keep photo-only gradients off shared plain-panel styles |
| Text on a photo | `On background color: image` provides readable text; a filled child button or chip uses its own surface context |
| Hero, lead and caption | `Display`, `Lead` and `Muted` style whole-leaf underscore wrappers |
| Inferred stat label and figure | Independent `Key` / `Value` blocks; `Text Overline` handles ordinary automatic keys |
| Button or chip variant | Both fill and text color are readable, including transparent variants |
| Task controls | Both checked and unchecked states appear in the document and have visible layers |
| Bars, rings or charts | Style the actual drawing family and its track; their typography is separate from authored text tiers |
| Icons and symbols | Verify coverage using the user's actual body and emoji fonts; a symbol that works in the example font is not guaranteed in a replacement |

For text-role examples, read [`text.md`](text.md).

---

- [ ] every glyph reads on the background it landed on

---

- [ ] **every state your theme styles has actually been drawn.** A state you did not write is a
      state you have not seen: a page of `- [ ]` items never renders `### Checked outer`, and a
      theme carried over from another document may be switching off a family you would have
      wanted (`### Dates`, `### Ratio Bars`). Write one of each — or read the blocks you inherited
      — before trusting a card that looks finished.

---

## From `skills/banking-example.md`

## THEME.md

```md
<!-- Worked banking example: three account sections and a separate summary band.
The summary uses ordinary repeated sections and responsive column counts. -->
## Fonts
- assets/fonts/Inter_18pt-Regular.ttf
- assets/fonts/Inter_18pt-SemiBold.ttf

## Background styles and Spacing
### Root
Background color: #F8F8FF
Padding: 24
Max width: 1600
### Elements
Padding: 0
Spacing: 12
### Heading 1
Padding: 0
Spacing: 24
### Heading 2
Padding: 24
Spacing: 18
Corner radius: 24
Background color: #FFFFFF
### Fixed styles
#### Premium
Padding: 24
Spacing: 18
Corner radius: 24
Background color: #8B5CF6
Background gradient:
- Type: Linear
- Colors:
  - #8B5CF6
  - #3B82F6
- Parameters:
  - Start: 0.0, 0.0
  - End: 1.0, 1.0

## Text Styles
Text
- Font Name: Inter 18pt
- Font size: 20
Heading1
- Font size: 28
Heading2
- Font size: 22
Muted
- Font size: 17
- Font color: #79798B
Display
- Font size: 36
Inline Code
- Font size: 20

## Inline Code
Fill color: #00000000
Padding: 0

## Fixed colors
### Badges
#### Exact
- +$8,450.00: Text color: #00A878, Fill color: #00000000
- -$2,340.50: Text color: #D85D10, Fill color: #00000000
- **** **** **** 9012: Text color: #FFFFFF, Fill color: #00000000

## Separators
Dash: hide

## Emoji styles
Font: assets/fonts/OpenMoji-black-glyf.ttf
### Secondary
Shape: square
Size: 26
Padding: 10
Icon color: #FFFFFF
Background color: #FF8427

## Color Replacements
On background color: #8B5CF6
- Replacement: #FFFFFF
```

The fixed Premium style declares its own complete card geometry. Its background-color replacement makes
text white. Exact-label chip pins supply the income/expense colors; `Fill color`
sets their chip fills to transparent. Adapt the exact-label pins to the amounts in
your answer.

---
