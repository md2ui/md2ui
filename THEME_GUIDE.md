# THEME.md Guide

How to write a `THEME.md` to style the md2ui renderer.

`THEME.md` is a plain Markdown file that configures every visual aspect of the layout:
backgrounds, padding, spacing, typography, links, and more. It is parsed by
`src/md2ui/pipeline/theme.py` (`parse_theme`). This guide documents every section and
key the parser understands, their value formats, and their defaults.

---

## 0. Orientation — which block do I need?

This file documents every key. Most tasks need one block, so start here rather than reading
through.

| I want to change | Section |
|---|---|
| the page: background, outer padding, width, stack vs mosaic | §3 `### Root` |
| a card's fill, radius, padding, stroke | §3 `### Heading N` — see *who paints what* below |
| depth: a drop shadow, a glow, a pressed-in edge | §3 *Shadows* — on any block that paints a background |
| the gaps between things | §3 *Spacing* — `Row spacing` is horizontal, `Col spacing` vertical |
| where content sits in a level | §3 `Horizontal align`, `Vertical align` |
| fonts, sizes, colors per role | §3 local role blocks; §4 global/base `## Text Styles` |
| button and chip pills | §5 `## Links`, `## Inline Code` — the variant comes from the markdown wrapper |
| code-block font, syntax palette, surface, and spacing | §5 `## Code Blocks`; typography is `Code Block` under `## Text Styles` |
| making text legible on a dark card or a photo | §5 `## Color Replacements` |
| a color that carries meaning | §5 `## Fixed colors` |
| dealing different colors to sibling cards | §6 *Color rotation* |
| bars, rings, date chips, task controls | §5 `## Drawing elements` |
| tables and token grids | §5 `## Tables` |
| one image's size, shape, crop or placement | §7 `?md2ui.*` — an image's own URL, not a theme key |
| what a picture that is not there shows: initials, an icon, an image, a fill | §7 *Named placeholders* — `## Images` → `### Placeholders` |
| what each spelling means for agents, and which one a place takes | §10 your project's `MEANINGS.md` — read by agents, not drawn |

### Who paints what

Styling nests outer-to-inner. Heading and list/quote surfaces may compose around the
same content; `Image Cards` specializes a photo-backed card. A plain card (`### Elements`)
is padding and gaps only: **a box comes from a heading style**, never from a card. Three
ownership rules decide which block answers. Most keys that appear to do nothing are written on the wrong level, and
an unknown or inapplicable key is ignored in silence:

1. **A card is owned by the nearest heading section enclosing it**, or by `Root` when none does.
2. **When your sections *are* your cards**, style the heading level: that is the box. The
   glued group inside it paints nothing of its own.
3. **A photo card's picture is its background**, and `### Image Cards` styles that card layer —
   but rule 1 still decides who owns it. `### Image Cards` answers when no heading section
   encloses the card; inside a `## ` marker or any heading section, that level owns it, and a
   heading inside the alt slot collapses onto the card the same way. For example, at root,
   `### Image Cards` → `Corner radius` shapes the card; inside a `## ` marker, only the heading
   level's radius takes effect.

`## Color Replacements` asks the same question from the other side — it searches the layers
*behind* a paint, innermost first (§5).

### Things that fail quietly

There are no errors, so these are worth checking before concluding a feature is missing:

| symptom | usual cause |
|---|---|
| a key does nothing | a misspelling, or the wrong level — unknown keys are ignored silently |
| a whole block does nothing | another level owns that element (above) |
| a gradient vanished | a quoted hex — `THEME.md` is not YAML; write `- #00000000` |
| a pinned stroke paints nothing | the element's own block has `Stroke width: 0` |
| an emoji section is ignored | it is `## Emoji styles`; `## Emojis` parses as nothing |
| an image annotation was skipped | read the terminal — a dropped param is named with the reason (§7) |
| a feature needing a *group* did nothing | it was given one line; two or more consecutive lines make a group |

---

## 1. Basics

- **Where it lives / discovery.** The renderer looks for `THEME.md` next to the
  Markdown document, then in the current working directory, and uses the first one it
  finds. You can point at a specific file with `--theme PATH`. If none is found (or a
  value is missing/invalid), built-in defaults are used.
- **Title.** The first `# Heading` line is taken as the theme *name* (informational).
- **Comments.** Anything inside `<!-- … -->` is ignored — including multi-line blocks.
  Use them to document your theme or to **disable a line** without deleting it:
  ```md
  <!--Background image: hero.png-->   ← ignored
  ```
- **Structure.** Configuration is grouped under `##` sections; some sections have `###`
  subsections. Keys are written `Key: value` (case-insensitive). Unknown keys are
  ignored, so a value simply has no effect if misspelled.

### Value formats

| Type | Format | Example |
|------|--------|---------|
| Color | `#RRGGBB` or `#RRGGBBAA` (alpha) — **or a bullet list**, which cycles (§6) | `#808080`, `#00000000` (transparent) |
| Number | integer or float | `16`, `1.5` |
| Boolean | `yes` / `true` / `1` (anything else = false) | `Merge rows: yes` |
| Point | `x, y` normalized 0–1 (gradients) | `Start: 0.5, 0.5` |

---

## 2. Layout levels

Styling is applied at three nested levels (outer → inner):

```
Root                     the whole content area (page background + outer padding)
└─ Heading 1 … 6         heading "sections" (a heading + its content), per level
   Fixed styles          named styles selected by heading ID (replace or override)
   └─ Elements           "cards": glued-content groups — padding and gaps, never painted
      Image Cards        a card whose background is a photo
      Unordered Lists    each `- ` / `* ` / `+ ` item
      Task Lists         each `- [ ]` / `- [x]` item; fallback: Unordered Lists
      Numbered Lists     each `1. ` / `1) ` item
      Quotes             each `>` blockquote
```

They all live under the **`## Styling & Spacing`** section, as `### Root`,
`### Heading 1`…`### Heading 6`, `### Elements`, `### Image Cards`,
`### Unordered Lists`, `### Task Lists`, `### Numbered Lists`, and `### Quotes` subsections. They
share most keys (background, padding, spacing). `### Fixed styles` contains named `####` blocks.

**What counts as a card** (an "Elements" block) is worth being precise about, since it
decides where card padding applies:

- a run of **consecutive source lines** — a paragraph;
- **one per display pair** — a `Key: value` that draws as a bar, a ring or a line —
  even when several share a line;
- **not** a same-line split that flows: `🎉 Great news [more](/x)` is a single line broken into pieces, and a single line has no consecutive lines to glue;
- **not** a heading section — a heading is a section, not a card.

### Repeated runs and grids

A grid is never requested — it is inferred. Two or more **contiguous siblings of the same
shape**, each of them a container (a card, a heading section — not a bare line), are laid
out as columns in place.

The column count is arithmetic, not a setting:

```
cols = floor( (available + gap) / (min_width + padding + gap) )
```

- `min_width` is the largest of: the item's text-length floor (`≤1 word` 80px,
  `2-4` 100, `5-9` 200, `10-40` 320, `41-100` 580), the widest unbreakable thing measured
  inside it (a pill, a long word), and any fixed aside cell;
- `available` is already inset by the container's own padding;
- content width is clamped to the root's **`Max width`** (**1280px** by default), which
  caps how many columns are reachable at all;
- a ragged last row must be at least half full, else the count steps down (4 items at a
  3-column fit render 2+2, not 3+1). That step is decided once per repeated **shape**,
  not per run: where a document repeats the same card in several places they share one
  column count, and it drops only when a third or more of those runs would end on an
  under-half row — so they keep one card width rather than each solving its own last row.

Columns are equal. The floor is one unbreakable piece, not a whole line, so a card whose
line of buttons is wider than its column wraps that line inside its cell; the grid
neither widens that one column nor ends the run for it.

**The theme keys that move it:**

| key | effect on a grid |
|---|---|
| `Group row spacing` on `### Elements` | the gap **between columns**. Plain `Row spacing` is only its fallback |
| `Padding` on any level | subtracted **twice** — once from the container's width, once per column — so raising card padding costs columns |

(`Row spacing` is horizontal and `Col spacing` vertical throughout — see §3.)

**It will not grid** when any child runs over ~100 words, which forces its container
full-width; when the run members are bare lines rather than containers; inside tables,
charts and drawn datapoints; or when the siblings are pieces of one source line, which
flow along the line instead.

A run at the document's **top level** grids like any other — no wrapper needed. (This
changed: the root used to be forced full-width, and the workaround was to wrap everything
in an empty `## `. That wrapper is now a no-op, not a requirement.) One consequence worth
knowing: two same-shaped top-level sections separated by an authored `---` currently grid
side by side, and the rule ends up inside the left column rather than dividing them.

### Bento — a Mondrian mosaic instead of a stack

`Layout: Bento` on `### Root` (§3) replaces the default stacking with a mosaic: cells of
varying width and height packed into a grid, edges aligned, in document order.

Bento tiles **one heading level**. The sections at that level are the cells; whoever holds
them — a heading section, or the document root — is the container. Everything *else* in
that container stays full width: its own heading, a lead-in paragraph. Only a run of 3 or
more sections tiles.

```
# Report                    ← the container's own heading: full width
Quarterly figures.          ← lead-in prose: full width
## Revenue      ┐
## Costs        │ ← the target level (2): these three are the cells
## Headcount    ┘
```

By default the level is picked automatically: the **shallowest level with 3 or more
sections in a row under one parent**. In the example above level 1 has a run of one, so
the target is 2. Name it explicitly with `Heading level` under `## Content arrangement`
(§5) when the automatic pick is not what you want.

Unlike a grid, bento is a *request* — it is off unless the theme asks for it. It falls
back to plain stacking when no level has a long enough run, and when the width is too
narrow to divide at all — the mosaic aims at ~260px per column, so below about 390px of
available width there is only one column and it stacks instead.

---

## 3. `## Styling & Spacing`

The main customization section. Contains `### Root`, `### Elements`, `### Image Cards`,
`### Unordered Lists`, `### Task Lists`, `### Numbered Lists`, `### Quotes`,
`### Heading 1`–`### Heading 6`, and `### Fixed styles`. The former heading
`## Background styles and Spacing` and the word form `## Styling and Spacing`
remain parser aliases; new themes should use `## Styling & Spacing`.

### Local styles at a level

Every level except `### Elements` may contain `#### Text`, `#### Muted`,
`#### Lead`, `#### Display`, `#### Key`, and `#### Value`.
These are partial overrides: a role changes only when its block is present, and
only the listed properties change. Supported bullets are `Font name`, `Font size`,
`Font weight`, `Font color`, `Marker text color`, and `Marker background color`.

```md
## Styling & Spacing

### Root
#### Text
- Font name: Inter
- Font size: 14

### Heading 2
#### Text
- Font size: 17
#### Display
- Font color: #8844CC

### Unordered Lists
#### Text
- Font weight: bold
```

Inheritance follows the actual content ancestry, one property at a time:
`Root` → enclosing heading levels → a matching fixed style → image/list/quote
surface. The nearest declaration of a property wins. Task items apply
`Unordered Lists` first and `Task Lists` second, so Task Lists can override one
property and inherit the rest. Nested headings retain their outer heading
declarations until a closer level overrides them.

`### Fixed styles` already uses `#### Name` for each named style, so its role
blocks use one deeper heading:

```md
### Fixed styles
#### Featured
Background color: #101010
##### Text
- Font color: #FFFFFF
```

`### Elements` is deliberately excluded: it is generic card layout, not a stable
content ancestry. Put typography on Root, a heading/fixed level, Image Cards,
or the list/quote surface that owns the content. A local `Font name` is used by
both measurement and drawing. Local text colors pass through `## Color
Replacements` against the visible background exactly like global text colors.

The global `## Text Styles` section remains available for base typography and
specialized roles such as headings, labels, links, inline code, and code blocks. A local role
block above overlays that role's global/default style; it does not mutate it.

Each eligible level may also contain `#### Horizontal Rule`, using the same
bare `Stroke color` and `Stroke width` keys as the global `## Horizontal Rule`
block. It is partial and follows the same cascade: for example, Heading 2 can
change only thickness while a nested Quote changes only color. Fixed styles use
`##### Horizontal Rule`. `### Elements` is excluded here too.

```md
### Heading 2
#### Horizontal Rule
Stroke width: 2

### Quotes
#### Horizontal Rule
Stroke color: #8844CC
```

The resolved local stroke color still passes through `## Color Replacements`
for the rule's visible background.

### Padding

Insets a level's content (Root outer margin, or a section/card's inner padding).

```md
Padding: 16                 all four sides
Padding top: 32             one side (top | left | right | bottom)
Padding bottom: 8
```
Default: `0` on every level. (Links and inline code also take per-side `Padding` — see
§5.)

> **Tip:** to visualize padding, render with `--debug-padding` (or press **P** in the
> interactive viewer). Section/card/root padding rings are green→blue→purple; link and
> inline-code padding rings are shown in a distinct orange.

### Spacing (gaps between adjacent items)

Every gap between two adjacent items is exactly **one kind**, chosen by priority
(highest first). A pair uses one kind; kinds do not stack.

| Priority | Kind | When | Key (lives on) | Default |
|---|---|---|---|---|
| 1 | **Section** | a section-change boundary — at least one side opens a heading section | `Spacing` on the **enclosing** level — `Heading N`, or `Root` for the top-level ones | unset on every level; falls back to group spacing |
| 2 | **Group** | a pair involving a non-section group (group↔leaf / group↔group) | `Group spacing` on `Elements` | falls back to element spacing |
| 3 | **Image** | picture ↔ picture — an image, or a group holding only images (a line of them, a `:::` row of picture cells) that paints no background of its own | `Image spacing` on `Elements` | `0` (images abut) |
| 4 | **Element** | leaf ↔ leaf (the base gap) | `Row spacing` / `Col spacing` on `Elements` | `8` row / `8` col |

Plus:

- **Which axis an image gap uses.** `Image row spacing` is the gap inside a strip — images
  the author wrote **on one source line**, which lay out as a row. `Image col spacing` is the
  gap between images on separate lines, which stack. Both default to `0`, so a strip sits
  flush and reads as one band unless you open it up. Groups of pictures meet at the same
  gaps — line to line, a mosaic to the `:::` row after it, one picture cell to the next —
  so consecutive mosaics read as one gallery. A group that paints a background of its own
  (a card fill, a list or quote background) is a group like any other and keeps the group
  gap. An image beside anything that is not an image takes the element gap; author more
  room with a spacer (`+++`).
- **Setting element gaps from `Root`.** The base gap can also be written on `### Root`
  instead of `### Elements`: `Element space: N` sets both axes at once, and
  `Element row space` / `Element col space` set one. (`Element spacing` is accepted as
  a synonym of `Element space`.) These write the same values as `Row spacing` /
  `Col spacing` on `Elements`, so use one place or the other, not both.

#### Items that override the table

A few items describe *themselves* rather than their neighbours, so they pick their own
gap regardless of what sits beside them. None of them is configurable — they exist so
the same construct always looks the same:

| Item | Gap it takes | Why |
|---|---|---|
| A **line block** (one source line's flowed pieces) | element, one-sided | a line reads as one element toward its neighbours. Exceptions: a glued card spaces as a card, a heading's line as a heading, and a line whose pieces are **all blocks** (colon columns, KV pairs) as a *group* — it is a group of groups, not a line of words |
| A **row separator** (` - ` ` \| `, see `## Separators`) | element, both sides | a separator divides whatever is beside it; its spacing must not change with what that happens to be |
| A **horizontal rule** (`---`) | **group**, both sides | a rule is a divider between blocks. A section boundary still wins — it describes the neighbour, not the rule |
| A **content break** (`___`) | **none** — it is transparent | it cuts a run without occupying space; the pair either side keeps the single gap it would have had |
| A **KV key** and its value | element | the value never detaches from its key, whatever shape it is |
| The rows one flowed run **wrapped** onto | element | they are still one unit |

Two of those are authored in the markdown, not in the theme:

- a **colon column** — ` : ` with a space each side stacks the pieces either side of
  it (`94% : Accuracy`). It binds tighter than ` | ` / ` - `, so `92 : days - ⬇` is
  two columns, the first of which stacks. `Key: value` (colon tight to the key) is
  text, drawn as written, unless a display reads it (ADR-205);
- a **content break** — `___` on its own line. It splits a group in two and
  paints nothing, which is what breaks a repeated-element grid into separate bands.
  An empty `# ` / `## ` heading does the same *and* opens that level's section;
- a **section stop** — `***` on its own line. It tells the heading section
  holding it to stop swallowing: everything after it is lifted out and becomes
  the section's next *sibling*, so a footer row sits beside the section's
  painted box instead of inside it. See *Section stops* below.

#### Per-axis

`Spacing: N` sets both axes; `Row spacing` / `Col spacing` override one. This applies to every spacing key:

```md
Spacing: 16                 both axes
Row spacing: 16             horizontal gap
Col spacing: 8              vertical gap

Group spacing: 16           Group row spacing / Group col spacing
Image spacing: 24           Image row spacing / Image col spacing
```

#### How section spacing is sized

A level's `Spacing` means one thing at every level: **the gap between its own child
sections.** A section gap is therefore owned by the **enclosing** level.

| The gap between… | is owned by |
|---|---|
| two `Heading 2` sections inside a `Heading 1` | `Heading 1 → Spacing` |
| two `Heading 3` sections inside a `Heading 2` | `Heading 2 → Spacing` |
| two top-level `# ` bands, or the content before the first heading and that heading | **`Root → Spacing`** |

So the vertical rhythm *between* your top-level bands and the rhythm *inside* each one
are two different keys, and setting one does not move the other.

A level that states no `Spacing` falls back to `Group spacing`, which itself falls back
to the element spacing — so an unstyled level picks up the document's group rhythm
rather than collapsing. A stated `0` is not "unstated": it means **no gap**, which is
how two same-coloured full-bleed bands are made flush.

```md
### Root
Spacing: 0          # the bands butt together into one continuous field

### Heading 1
Spacing: 32         # …while the sections inside each band keep their rhythm
```

### Backgrounds

`Background image` is part of the shared painted-background vocabulary, but not
every block that stores a `SectionStyle` paints every field. The table below is
the authoritative support list.

| THEME.md location | Image painted? | What receives it |
|---|---:|---|
| `### Root` | yes | the document background |
| `### Image Cards` | yes | top-level image-card fallback; the Markdown photo wins once loaded |
| `### Heading 1`–`6` | yes | that heading level's section/card background |
| `### Fixed styles` → `#### Name` | yes | instances of that named heading style |
| `### Unordered Lists`, `### Task Lists`, `### Numbered Lists`, `### Quotes` | yes | the structural list/quote row background; a nested `#### Marker` styles its marker |
| `## Tables` → `### Table` | yes | the whole-table shell when `Merge rows: yes` |
| `## Tables` → `### Header`, `### Cells` | yes | header and body-row backgrounds |
| `## Links` → button variants | yes | the button pill |
| `## Inline Code` → chip variants | yes | the standalone chip pill; in-sentence code markers are unchanged |
| `## Emoji styles` → badge variants | yes | the standalone or heading badge, clipped to its `Shape` |
| task-control state layers | yes | checked/unchecked outer and inner shapes |
| ratio/of/key-value bars and their tracks | yes | each filled bar or track |
| chart bars and `### Chart Track` | yes | each chart bar or horizontal track |
| `### Ring`, `### Ring Track` | **no** | rings are solid-color stroked arcs, not filled background shapes |
| `### Dates`, `### Date Key`, `### Date Day` | **no** | date chips currently paint outer color/gradient and split-region colors only |

`### Elements` is not in the table: a card paints nothing, and its block reads only padding
and spacing (with the alignment and image keys). Paint keys written there are ignored.

The supported layers paint in a fixed order: **outer shadows → fill color →
image → gradient → inner shadows → stroke**.
An opaque gradient covers the image; use transparent gradient stops for a
scrim. The fill, image, and gradient are clipped to the background's rectangle,
corner radius, or control shape. Outer shadows may extend beyond that clip;
strokes paint on its edge.

```md
Background color: #FFFFFF            single solid fill
Background image: assets/hero.png    local path or http(s) URL
Background gradient:                 see below
```

An image value is one local filesystem path or one `http://` / `https://` URL.
A relative path resolves beside the THEME.md first (see `## Fonts`).
It is not a rotating list. A missing, unreachable, or undecodable image paints
the broken placeholder in its place, cover-fitted and clipped like the image,
and every color rule stays as declared, so text over it keeps the
`On background color: image` color it was given. An image that was never
fetched, because the renderer fetches nothing (an MCP server without
`--fetch`), has not failed and paints nothing. The color, gradient, stroke, and
shadow layers paint either way.

Theme background images always use centered **cover** fitting: they fill the
entire painted rectangle and crop equal amounts from opposite sides as needed.
There are currently no theme keys for `contain`, focal position, repetition,
image opacity, tint, or blend mode. Image URL parameters documented under
`## Images` style Markdown image elements; they do not change theme background
images.

For a Markdown image card, the URL in the Markdown is the primary photograph.
The applicable theme background image is visible only as its fallback while
that photograph is unavailable or loading. If that fallback image itself failed,
the card shows the loading placeholder while its photograph loads, and the
broken placeholder only once its photograph fails too. Which theme block applies still
follows normal ownership: an enclosing heading level wins; `### Image Cards`
answers only when no heading section owns the card.

For color replacement, declaring a background image establishes the special
context `On background color: image` (as does a Markdown image-card photo).
That context is selected from the declaration even if loading later fails.
Rules recolor text, fills, strokes, and other paint placed over it; they never
alter the image pixels. A visible solid child surface establishes its own
nearer context and shields its contents from the image rule.

Give **multiple** fill colors as a bullet list and they cycle — one per
same-level sibling section, restarting inside each enclosing section. Two colors
alternate like zebra stripes; four give four cards four hues. See §6.

```md
Background color:
- #808080
- #ADADAD
```

(`Background colors:` — plural — is the same key and still parses.)

#### Gradient syntax

```md
Background gradient:
- Type: Linear                 Linear | Radial
- Ratios:
  - 0.0
  - 0.55
- Colors:
  - #F7D3CF
  - #FBF8F7
- Parameters:
  - Start: 0.5, 0.5            normalized 0–1
  - End: 1.0, 1.0
```
Default gradient (if you only write `Background gradient:`):
linear, `Start 0,0` → `End 0,1`.

For a **linear** gradient, `Start` and `End` are normalized coordinates in the
painted rectangle: `(0,0)` is top-left and `(1,1)` is bottom-right. The first color
starts at `Start`; the last color is reached at `End` (subject to explicit `Ratios`).

| Direction | Start | End |
|---|---|---|
| Left to right | `0.0, 0.5` | `1.0, 0.5` |
| Top to bottom | `0.5, 0.0` | `0.5, 1.0` |
| Top-left to bottom-right | `0.0, 0.0` | `1.0, 1.0` |
| Reverse that diagonal | `1.0, 1.0` | `0.0, 0.0` |

These directions describe linear interpolation. Copy the complete gradient block,
including distinct `Colors` and the `Parameters` that position their transition. The
[banking example](skills/banking-example.md) includes a complete diagonal card theme.

### Borders & shape

```md
Corner radius: 16
Stroke width: 2
Stroke color: #000000
Stroke align: center            center | inside | outside
```
Defaults: corner radius `0`, stroke width `0`, no stroke color, `Stroke align:
center`. `Stroke color` also takes a bullet list, so a rotated card can carry a
rotated border (§6).

`Stroke align` says where the line sits on the edge:

```
          outside │ inside        (│ = the box's edge)
center        ━━━━┿━━━━           half beyond, half within
inside            │━━━━━━━━       all within the box
outside   ━━━━━━━━│               all beyond the box
```

`inside` keeps the whole line within the box, drawn over the fill's edge;
`outside` draws it entirely beyond the box, into the space around it — the box
keeps its size and position either way, so a thick outside stroke can reach a
neighbour. A rounded corner's radius moves with the line; a square corner stays
square. The same key works on every stroked surface: every `###` level here,
tables, button pills (`## Links`), chips (`## Inline Code`), emojis, task
controls, sliders, and the bars and tracks of `## Datapoints` and `## Charts`.

**A stroke is the front layer.** It is painted after everything inside the box,
so a photo, an image card or a nested card that reaches the edge sits *under*
the border, never over half of it.

### Shadows

A shadow is a layer on the background, not a property of one element, so the
same three keys work on **every box that paints a background**: `### Root`, each
`### Heading N` and `### Image Cards`, the list and quote levels,
`## Sections`, tables (`### Table` / `### Header` / `### Cells`), button pills,
inline-code chips, date chips, emojis, task controls (each of the four
checkbox/switch state layers), progress bars and their tracks, and chart bars
and their tracks.

```md
Outer shadow:
- Offset x: 0
- Offset y: 12
- Color: #0F172A29        RGBA — the alpha is how strong the shadow is
- Radius: 40              the blur; how far it reaches past the edge
```

`Inner shadow:` takes the same four bullets, and a bare `Shadow:` means the
outer one. Offsets may be negative. Every bullet is optional: a shadow with no
`Color` has no alpha and paints nothing, and `Radius: 0` is a hard-edged copy.
`Radius` is capped at **250** — a larger value is clamped, not rejected.

**The two are not mirror images**, which is why both exist:

| | falls | clipped to | a positive offset |
|---|---|---|---|
| **Outer** | outside the shape | the shape's bounds grown by `Radius`, moved by the offset, with the shape cut out | casts down-right, away from the box |
| **Inner** | inside the shape | the shape itself | darkens the **top-left** inside edge, as if the box were pressed in |

Cutting the shape out of an outer shadow's clip is what lets a translucent card
sit on one: the shadow is never painted under the fill it belongs to.

#### Several at once

Repeat the key. Up to **four of each kind** per background, painted in the
order written — outer layers under the fill, inner layers over it. One shadow
rarely reads as depth; a tight, dark one over a wide, soft one does:

```md
Outer shadow:
- Offset y: 2
- Color: #0F172A14
- Radius: 6

Outer shadow:
- Offset y: 16
- Color: #0F172A29
- Radius: 48
```

A fifth shadow of the same kind is dropped, and `md2ui check --theme THEME.md`
names the block it was dropped from.

**Variants replace, kind by kind.** A button, chip or badge variant
(`### Secondary` and the rest) inherits Primary's shadows until it declares one of
its own: then its outer shadows replace Primary's outer ones, or its inner
shadows Primary's inner ones, and the other kind is still inherited. The same rule
as a variant's colour lists. A variant that should cast no shadow of a kind
declares one with a transparent `Color`.

> On `### Root` an inner shadow reads as a vignette around the whole render
> area. An outer one has nothing outside the viewport to fall on.

### Images inside a level

Two keys, both **off by default**, on any level (`### Elements`, `### Heading N`,
`## Sections`). They style the images *inside* the level — `Corner radius` above
rounds the level's own background, not its images.

```md
### Heading 3
Background color: #F0F0F2
Corner radius: 24
Padding: 20
Image corner radius: 8    # round image leaves in this level
Image bleed: yes          # let them reach the level's edge
```

`Image bleed` lets an image run over the level's own `Padding`, for the
edge-to-edge look. **It bleeds every inner edge the image already touches**, so
you never declare directions:

| where the image sits | edges it touches | bleeds |
|---|---|---|
| first child, full width | top, left, right | T L R |
| aside on the left | top, left, bottom | T L B |
| aside on the right | top, right, bottom | T R B |
| last child, full width | left, right, bottom | L R B |
| between two siblings | left, right | L R |

The rule polices itself: a sibling on some side is exactly what stops the image
touching that edge, so an image can never bleed over its neighbours. Each edge
moves out by that edge's padding — space the level had already reserved and left
empty — so nothing reflows.

A card can be taller than its content: under `Layout: Bento` a card is stretched
to its band, and the extra space stays empty below the last line. A full-width or
aside image that ends the card's content runs down through that space to the
card's edge, as it would if the card fitted it. Nothing reflows here either: only
the image grows, into space no sibling stands in.

While bleeding, the **level's** `Corner radius` clips the image, on just the
corners the two now share: a top image rounds its top pair and keeps its bottom
pair square where content continues below. `Image corner radius` is ignored
while bleeding — the parent's shape wins.

Two images opt themselves out: one carrying `?md2ui.max_width=` (it paints a
small rect inside a big box, so bleeding would only push it into the corner) and
one with `?md2ui.shape=circle` (it clips to an oval and ignores any radius).

### Horizontal align: where a level's content sits

`Horizontal align` puts a level's content `left`, `center` or `right`. Formerly
`Align`, and that spelling still works. `### Root` has always
had it; every level takes it now — `### Heading 1`…`### Heading 6`,
`### Elements` and `### Image Cards`.

```md
### Heading 2
Horizontal align: Center
```

It **inherits**: a level's value reaches everything below it, *including a nested
section*, until a deeper level states its own.

```
┌ H2  Align: Center      centred
│ ┌ card                 centred   (inherits)
│ ┌ H3  (no Align)       centred   (inherits)
│ │ └ ...unless that H3 says Align: Left
└
```

On `### Elements` / `### Image Cards` it aligns the content **inside** the card;
the card keeps the width the layout gave it. That is the same thing `### Root`'s
Align means — content alignment, not block placement.

It moves everything the level owns: text, rows, images, and also buttons, chips
and emojis (those used to read the Root value directly and stayed flush
left inside a centred section).

Two things still outrank it, both per-node and both authored: a `...` **spring**,
which is why `Subtotal ... $42.50` keeps reaching both edges inside a centred
section, and a `?md2ui.content_align` on an image. See §7's precedence ladder.

Unset means "inherit", so a theme that says nothing is unchanged. `Default` on a
level reads as unset; on `### Root` it means Root's own default, `left`.

`### Root` is the broadest place to declare it and reaches everything below, so
work inward from there: state a level's own value only where that level should
differ from the page. Remember that a `...` spring and an image's
`?md2ui.content_align` outrank `Horizontal align` by design (§7), so a line carrying a
spring is never evidence about what the level is doing.

### Vertical align: the vertical axis of a row

Formerly `Line align`, and that spelling still works — it was named for a time
when the pieces of one source line were the only row an author could make, and
`:::` rows ended that.

`Vertical align` is `Horizontal align`'s twin on the other axis. It takes `top`, `baseline` (the
default), `center` or `bottom`, and lives on the same blocks — `### Root`,
`### Heading 1`…`### Heading 6`, `### Elements`, `### Image Cards` — inheriting
the same way.

```md
### Heading 2
Vertical align: Center
```

It governs the two rows an **author writes**: the pieces of a single source line
(`Subtotal - 92 : days - 41%`), and the cells of a `:::` column row.

**A single line can overrule it.** Ending a source line with `@tp`, `@ct`, `@bs` or `@bm`
sets that row's alignment to top / center / baseline / bottom, whatever the level says —
the same way a `...` spring outranks `Horizontal align` in §7. Set the level for the
document's rhythm and use a token where one row differs; `\@ct` declines it and draws the
characters. It reaches only the same-line row, so a `:::` row still takes the level (or a
vertical `...` spring inside a cell).

**What can be moved.** `center` and `bottom` distribute a cell's slack, so a cell with none
does not move: an **uncapped** image takes whatever width the row gives it and its height
follows, filling the row. Give a picture `?md2ui.max_width=` and it has an intrinsic height,
so a row of logos aligns like any other row. Under `baseline` an image never moves whatever
its width, because a picture has no text baseline to sit on. A grid of
cards, a gutter-marker row and an image aside are neither, and no value here
touches them — they keep their top alignment and their own per-cell
`Content valign`. That line matters: those are arrangements the document did not
ask for by name, and a theme value that restacked them would be a surprise.

On a `:::` row, `baseline` reads as `top`. A same-line row's pieces are the words
of one line and share a text baseline; a column row's cells come from different
source lines and mostly stack, so there is no shared line to hang them from.

- `baseline` — a piece that is one line puts its text baseline on the row's
  shared baseline, so a 26px number and the 13px word beside it sit on one line.
  A piece that **stacks** (a colon column like `92 : days`) has no single line to
  offer, so it centres on the row's text band instead. Snapping its top line to
  the baseline is what used to leave the rest of the block dangling and make a
  row of such pairs zig-zag.
- `top` — every piece hangs from the row's top edge.
- `center` / `bottom` — every piece distributes its slack in the row.

```
Baseline (default)            Top                    Bottom

           ┌ 92                 ┌ 92         Discount ┌ 92
Discount   └ days      Discount └ days                └ days
```

Unset means "inherit"; `Default` on a level reads as unset, and on `### Root` it
means Root's own default, `baseline` — so a theme that says nothing renders
exactly as before.

### Orphan row: the last row of a grid

When a run of repeated items grids into N columns and the count does not divide
evenly, the final row is *ragged* — it holds fewer cells than there are columns.
`Orphan row` decides what it does with the width the missing cells would have
used. It takes `left` (the default), `center` or `stretch`, on the same blocks as
`Horizontal align` — `### Root`, `### Heading 1`…`### Heading 6`, `### Elements`,
`### Image Cards` — inheriting the same way.

**Write it on the level that CONTAINS the grid, not the level of the cards.** A run
of `### ` sections sitting inside a `## ` section is that `## ` section's grid, so
the key belongs on `### Heading 2`; put it on `### Heading 3` and it does nothing to
that run, because `Heading 3` owns no grid there. A run with no heading above it is
the root's.

```md
## Products        <- the grid belongs to this section...
### Item 1         <- ...so this is not the level to write it on
```

```md
### Heading 2
Orphan row: Stretch
```

```
3 columns, 5 items:

left (default)        center                stretch
┌──┐┌──┐┌──┐          ┌──┐┌──┐┌──┐          ┌──┐┌──┐┌──┐
└──┘└──┘└──┘          └──┘└──┘└──┘          └──┘└──┘└──┘
┌──┐┌──┐                ┌──┐┌──┐            ┌─────┐┌─────┐
└──┘└──┘                └──┘└──┘            └─────┘└─────┘
```

It governs **any** ragged row, not only a lone cell: a 3-of-4 row reads the same
way and moves the same way.

The column count has already done what it can before this key is consulted: a last
row under half full makes the count step down instead (§2, *Repeated runs and
grids*). So `Orphan row` acts on the rows that are left genuinely ragged — a 2-of-3,
a 3-of-4, or the single cell a 2-column grid is allowed to end on.

`stretch` does more than resize the box. A cell is *built* at the width it is
given — its card, its wrapping and any grid inside it are already arranged by the
time it is drawn — so a stretched cell is rebuilt at the full row width and its
contents re-flow into it. That is usually what you want, and it is why the key
cannot simply be a drawing option.

`left` is the default because it is what md2ui has always done, and because a
lone card held at its siblings' width is deliberate: `Orphan row` makes that
choice explicit rather than changing it. A theme that says nothing renders
exactly as before.

### Stack sections: one-off bands share a line

```md
### Root
Stack sections: yes
```

Repeated siblings **grid** — equal things deserve equal sizing, one column count for the
whole run. A **unique** band owes its neighbours nothing, so instead of spanning the page
with little in it, it sits beside the next one:

```
[    ][       ][   ]
[         ][       ]
```

Looser than a grid, and the two halves of it answer different questions.

**What a band asks for decides which line it lands on.** The ask is the width at which
nothing inside has to give way: the longest ROW inside the band, gaps and padding included;
the widest same-kind run it holds, kept on one line; every line of text at its full
unwrapped width; and a multi-row chart at the width its bars stay vertical rather than
turning on their side. The ask is measured from that content, not re-checked: a grid inside
a packed band can use one column fewer than it would across the whole line, because its
cards are floored by their length category rather than by their text. Text never overflows.
**A section wraps to the next line before the text inside it wraps**
— so a band holding a paragraph asks for more than the line and simply keeps the line,
which is what any block gets when it does not grid or stack. Bands are taken in document
order, as many per line as fit, and the last two lines are evened out rather than left with
a lone block on the end.

**What it asks for also buys its share of the line it landed on.** A line always spans the
full width: the leftover is shared out in proportion, so every band on a line grows by the
same factor and none is ever drawn under the width it asked for. Narrowing the page
therefore moves a band down to the next line rather than squeezing the ones that stay.

What packs is a unique **`## ` band** — a heading section, titled or a bare `## ` marker.
A deeper group does not: the pieces of a card and the cells of a `:::` row are an
arrangement their author already chose, and putting two of those side by side would
second-guess it. Nor does a **leaf**, which is what keeps a section's own title above the
body it introduces rather than beside it, and a `---` or a content break on its own line.

Five more things keep their own row, each because it already decides its own arrangement or
its own separation:

- a **repeated member** (it grids) and a lone member of a kind its siblings grid (it is
  gridded at their card width);
- a **table**, an authored **`:::` row**, a **same-line row**, and a **list item** — a list
  is a sequence, not a set of independent blocks;
- a section **ending in a `---`**: a block that closes with a divider is announcing a
  separation from what follows;
- a **titled section at the document's top heading rank** — a `# ` chapter keeps the whole
  line, and the packing happens inside it. A page of bare `## ` markers is what this is
  for; a page of chapters is not.

`Stack sections: no` restores the one-block-per-row stack md2ui had before the key.

### Max width and Centered: the draw area

Two `### Root`-only keys that shape the drawing area rather than its contents.

```md
### Root
Max width: 1280
Centered: yes
```

`Max width` caps the layout's content width. The window may be wider; the layout stops
growing there. Default **1280**, floored at 320 so a typo cannot collapse a page. One
thing to know before lowering it: the layout's wide breakpoint is **768**, so a cap
below that does not merely narrow the page — it flips the whole document to its narrow
variant.

Under `Layout: Bento` the key means something different in practice from what it means in a
stacked layout. The mosaic aims at ~260px per column, so a larger cap is spent on **more
columns** rather than on wider cells: a 15-card board at 1280 packs four cells of ~300px and
the same board at 1600 packs five of ~265px — every card narrower than before. Card width in a
mosaic follows from the number of cards, not from this key, and content that needs room (an
image aside, a wide table) is likelier to fit at the smaller cap. See §2's *Bento*.

`Centered` decides where the layout sits once the window is wider than `Max width`:
`yes` (the default) splits the leftover space either side, `no` keeps it hard left, which
is what md2ui did before the key existed.

Neither key changes an `md2ui render`'s placement: that path sizes its surface to the
layout, so there is no slack to centre in. `Max width` does change a render's *width*,
since it is what the requested `--width` is clamped to.

### Box: a filled panel behind the content

`Box: yes` draws one solid rounded rectangle over the whole layout area, behind
every card, inset inside `Root`'s own padding. It is the page's content panel:
when it is on, it — not `Background color` — is what every box inherits as its
backdrop.

```md
### Root
Box: yes
Box fill color: #FFFFFF     (default: the standard background colour)
Box radius: 24              (default 0 — square corners)
```

Off by default. With `Box: no` the other two keys are parsed and ignored.

### Layout: stacked, bento or auto

`### Root` only. Switches the whole document between the default vertical stack and
the Mondrian mosaic described in §2, or lets each document choose.

```md
### Root
Layout: Auto                Default (stacked) | Bento | Auto
```

`Auto` lays the document out both ways and tiles it only when the mosaic leaves
clearly less of the page empty (at most 85% of the stacked page's empty area), so
dashboards and summaries tile while catalogs, detail pages and articles stack. The
choice is made once per document for each width band — under 768px, 768–1279px,
1280px and wider — the first time the window reaches that band, and kept while the
document is open; under 768px the page always stacks. The window's `G` key still
switches to the other layout on purpose.

This is the layout switch; *which* heading level the mosaic tiles is set separately,
under `## Content arrangement` (§5), and picked automatically when unset. Any other
value reads as `Default`.

### Emoji aside: an icon in the gutter

`Emoji aside` puts a lone emoji into a **gutter beside the whole group** rather
than leaving it on the group's first line. Off by default, declared per level on
the same blocks as `Image bleed`.

```md
### Heading 2
Emoji aside: yes
```

```
without                      with
⭐ Section title             ┌───┐ Section title
body line one                │ ⭐ │ body line one
body line two                └───┘ body line two
```

It applies to every group **that level owns**, and stops at the next heading
boundary — a nested `### Heading 3` section answers to its own key, not to the
H2 that contains it, while glued groups inside the level do follow it:

```
┌ H2 section          ✅ (Emoji aside: yes on ### Heading 2)
│ ┌ glued group       ✅  inherits the level
│ └
│ ┌ H3 section        ❌  answers to ### Heading 3
│ └
└
```

Content outside any heading section follows `### Elements`.

**Position picks the side.** The emoji has to be the group's first or last
child — first takes the left gutter, last the right one, exactly like an image
aside. A middle emoji is never eligible. The emoji also has to be one the
document made an ELEMENT (separated, so it draws as a `### Primary` badge); an
emoji that a heading, a key or a table cell styles as text stays where it is.

A group that is **one source line** is never turned into an aside. A line keeps
flowing — `⭐ - text - 🚀` stays a row — because an aside stacks whatever sits
beside the icon, which would be the opposite of the line you wrote.

The icon cell is **fixed**, not proportional: it takes the width its own badge
renders at and the content column takes the rest, so it never grows with the row.
If the gutter plus the narrowest content will not fit the available width, the
group simply stacks instead — it is never clipped.

A picture goes beside text through a `:::` row in the document
([`skills/structure.md`](skills/structure.md)); an icon aside is a theme key
because it states one rule for a whole level.

### Spacers: how much room `+++` makes

A document writes blank space as a spacer line — `+++`, `++++`, `+++++` for small,
medium and large — and the theme says how many pixels each one is. Unset, a spacer
scales with the group gap of the level that holds it — down 1×, 2× and 4× the gap,
across 1×, 1.5× and 2× — and never measures less than 8, 16 and 32 down, 8, 12 and 16
across. So with the default 8px gap they are 8, 16 and 32, and a theme whose gaps are
0 still draws every spacer it does not size.

```md
### Root
Spacer small: 8
Spacer medium: 16
Spacer large: 32

### Image Cards
Spacer large: 240        # the room above a photo card's words
```

`Spacer <step> row` / `Spacer <step> col` size one direction only (row = across,
col = down), beating the plain key on that direction.

The **nearest surface that states the step** decides: `### Image Cards` for a
spacer inside a photo card, then a fixed style (`#### Tall` for `{#tall-1}`) on the
section that holds it, then the `### Heading N` whose section holds it, then
`### Root`. Heading levels do not inherit from each other, like every other
per-level key.

A spacer is **added** to the spacing around it: the two things either side keep
the gap they would have had, and the spacer adds its own size. It never changes
how a card matches its neighbours, so a card holding one still grids with its
twins.

The size is **pixels, not a proportion of the card**. A photo card's room is
therefore the same height at every column count; write a different step, or a
different size per level, where cards of one width need more.

### Section behavior flags

```md
Merge rows: yes             draw ONE shared background behind same-level cards grid'd in a row (default no)
```

#### `### Image Cards`

Styles a card whose background is a photo — written in markdown by putting content in
an image's alt slot:

```md
![
## Santorini Sunset Loft
Cliffside views over the caldera.
[Book now](/book)
](https://example.com/hero.jpg)
```

The alt-slot markdown becomes the card's content and the URL becomes its background.
It takes the paint keys a heading level takes (padding, corner radius, background colors,
gradient, stroke, shadows). When it declares nothing it falls back to `### Elements`, which
paints nothing, so the card draws its photo alone with the card padding.

```md
### Image Cards
Corner radius: 16
Padding: 16
```

Paint order inside the card is **background color → photo → gradient**, so a
`Background gradient` here lands *on top of* the photo — that is how you get a scrim
to keep text legible over a busy image.

A plain `![alt text](photo.jpg)` is unaffected: it stays an ordinary image. Only an
alt slot containing real markdown (a heading, a list, a link, a nested image) makes a
card. When a card's content has its own heading, the heading wins the background and
paints the photo with the heading level's own radius and padding, so it matches its
sibling sections.

#### `### Unordered Lists`, `### Task Lists`, `### Numbered Lists`, and `### Quotes`

These are structural surfaces using the same fill stack and geometry as cards:
background color or image, gradient, stroke, corner radius, and per-edge padding. They also
participate in `## Color Replacements` through their actual painted background.

Each list **item** gets its own surface. `### Unordered Lists` covers `- `, `* ` and `+ ` items;
`### Task Lists` covers `- [ ]` / `- [x]` and falls back to the complete Unordered Lists style
when its own block is inactive. `### Numbered Lists` covers `1. ` and `1) ` items.
`### Quotes` covers one blockquote, with consecutive `>` lines remaining one surface.
Like heading-level backgrounds, a `Background colors:` list cycles across matching items and
restarts inside each heading section. Each structural type has its own cycle. Root retains its
document-wide extent behavior.

```md
### Unordered Lists
Background colors:
- #FFFFFF18
- #FFFFFF24
Corner radius: 12
Padding: 12

### Numbered Lists
Background color: #FFFFFF24

### Task Lists
Background colors:
- #DFF7E8
- #C8EED8

### Quotes
Background color: #FFFFFF18
Stroke width: 1
Stroke color: #FFFFFF40
Padding left: 16
```

These blocks paint the container. Put a `#### Marker` last inside the same block when it also
needs a bullet, ordinal, quote character, or quote bar. Marker-only declarations do not make
an otherwise transparent container start painting.

**One card for the whole list.** `Merge rows: yes` on `### Unordered Lists`, `### Task Lists` or
`### Numbered Lists` paints the level's surface ONCE behind each list whose items stack (a
settings menu, a transaction history) instead of once per item. Each item keeps the level's
`Padding`, rows meet with no gap, and the theme's horizontal rule runs between them, inset by
that padding. Style the rule for the list with a `#### Horizontal Rule` inside the same block;
`Stroke width: 0` there leaves the rows undivided. The shell paints the first of
`Background colors:` (one card has nothing to cycle across), and a run of items that grids
into tiles keeps a card each. The Markdown is the same list either way: whether its rows are
separate cards or one card is this key's, never the author's.

```md
### Unordered Lists
Merge rows: yes
Background color: #FFFFFF
Corner radius: 24
Padding: 16
#### Horizontal Rule
Stroke color: #16162414
Stroke width: 1
```

**No card around the list.** Lines written with no blank line between them are one card
(`### Elements`), but a run that holds a list's items and nothing else draws without it: the
items keep their arrangement, stacked or gridded, and their own surfaces. `List card: yes` on
`### Unordered Lists`, `### Task Lists` or `### Numbered Lists` puts the card back around that
level's lists. A line glued to the list, such as a lead-in above it, always keeps the card,
since the run is then more than a list. Default `no`.

```md
### Unordered Lists
List card: yes
```

#### `### Fixed styles` — one named section style

Use a standard trailing heading ID when one section needs a stable, named style rather than
its `### Heading N` style:

```md
### Fixed styles

#### This is another fixed style
Background colors:
- #FFFFFF
- #F4F4F4
Corner radius: 24
Padding: 24

## Heading text {#this-is-another-fixed-style-1}

## {#this-is-another-fixed-style-2}
```

The `####` title is converted in full to lowercase kebab-case, so the declaration above is
keyed as `this-is-another-fixed-style`. An eligible heading ID is lowercase kebab-case ending
in a positive numeric suffix; removing that final suffix selects the key. The complete ID stays
attached to the section for future navigation, while the `{#…}` attribute is not drawn. An
ID-only heading opens a section without drawing an empty title.

By default a matching fixed style is a **standalone replacement** for the complete
`### Heading N` SectionStyle: omitted properties use their normal defaults and do not inherit
from that heading level. `Mode: override` in the `####` block makes it a layer instead — the
keys it states win, and every key it omits keeps the value of the heading level the ID sits on:

```md
### Heading 2
Background color: #FFFFFF
Padding: 30
Outer shadow:
- Offset y: 4
- Color: #00000033

### Fixed styles
#### Featured
Mode: override
Background color: #101010
Corner radius: 28
```

`## Launch {#featured-1}` keeps Heading 2's padding and shadow and paints the dark fill with the
larger radius. A list the block states — `Background colors`, `Stroke colors`, shadows —
replaces the level's list whole rather than extending it. The same `#### Featured` on a
`### ` heading layers over `### Heading 3` instead; on a level with no style of its own there
is nothing to keep, so it paints as the standalone style. `Mode: replace` states the default.
Role typography (`##### Text` and the rest) already cascades per property in both modes.

Either way it accepts the same paint, padding, spacing, sizing, alignment, image, and arrangement
keys. Its color lists rotate among instances of that fixed style independently of ordinary
heading sections and other fixed styles. An unmatched or non-numbered ID is retained but has no
styling effect. Keep complete IDs unique; duplicate-ID navigation is intentionally not enforced
until navigation itself is implemented.

That includes `Background image`: a matching `{#name-N}` section paints the
single local or HTTP(S) image declared by its `#### Name` block — or, under
`Mode: override` with no image of its own, the heading level's — using the same
centered-cover clipping and color → image → gradient order described under
*Backgrounds*. The heading ID only selects the named style; no image path or
paint property is read from the ID itself. If the section owns a Markdown image
card, that card's authored photograph still wins over the fixed style's image,
which remains its loading fallback (the loading placeholder, if the fixed
style's image failed). Content directly on the fixed-style image
uses `On background color: image`; a visible child fill establishes a nearer
replacement context.

---

## 4. `## Text Styles`

Base typography per role. The seven body roles can be overridden at structural
levels under `## Styling & Spacing` (§3); this section supplies their global
defaults and owns specialized typography. Subsections: `Heading1`…`Heading6`, `Text`,
`Muted`, `Lead`, `Display`, `Key`, `Value`, `Labels`, `Links`. Each takes a bullet list.
(`Text Overline` and `Heading{N} Overline` are not keys (ADR-205); a theme
that still has them loads, and they style nothing.)

`Font color` can also take a **nested** list, which cycles (§6) — write the key
bare and indent the colors two spaces under it:

```md
Heading2
- Font size: 32
- Font color:
  - #0A0A0A
  - #FFFFFF
```

This works for the heading, `Text`, `Links <Variant>` and `Inline Code <Variant>`
blocks, and for `Marker text color` / `Marker background color` — so an in-text
`` `code` `` span can follow the card it sits on. Markers cycle on the `chip`
channel, a marker being the in-text form of a chip. The display tiers (`Muted` / `Lead` / `Display`) do
**not** take it: their bullets are collected and merged after the whole file is
read, which leaves no room for a list. They do not need one — a tier that must
change color per card gets it from `## Color Replacements`, which is keyed on the
color itself, so one rule per card background recolors every `Display` value
sitting on it.

A `Key: value` line is **text**, drawn as written, colon included: its words take
whatever the author wrapped them in (`**Key:** value` draws a bold key). Only a
display reads such a line as a pair — a bar, a ring, a line, a chart row — and
labels it in the `Key` style below (ADR-205).

### Display tiers — `Muted`, `Lead`, `Display`

The only three styles an *author* picks directly, by wrapping a **whole leaf** in
underscores:

| Markdown | Style | How a plain editor renders it |
|---|---|---|
| `_Available balance_` | `Muted` | *italic* |
| `__From $145 per night__` | `Lead` | **bold** |
| `___$12,480.55___` | `Display` | ***bold italic*** |

Underscores are exact CommonMark synonyms for asterisks, so the same file still
reads correctly anywhere else — italic → bold → bold-italic, in the same order of
weight as muted → lead → display. That is the whole point of the choice: no
invented characters, nothing that degrades into visible punctuation. The asterisk
family is untouched, so `*x*` is still plain italic.

Three rules that are easy to get wrong:

- **Scope is the whole leaf** — a full line, or a full `|`/`-` separated segment.
  A wrapper inside a sentence is just emphasis:
  ```md
  ___$12,480.55___                  → Display tier
  Text with a __bold__ word         → a plain bold span, NOT a tier
  __Total__ | __$412M__ | __+12%__  → three separate Lead segments
  _A_ _B_                           → two italic spans, not one wrap
  ```
- **Precedence is heading > tier.** `# ___x___` is a heading first — it keeps its
  markers and paints bold-italic in the heading's own family, exactly like
  `# ***x***`.
- **A tier suppresses `## Content Weight`** — see below.

**`Key` and `Value` style the two sides of a display's pair** (the label and
value of a bar, a ring or a line), one decision for the whole document. State
neither and both are body text.

Three things outrank them, in this order: a **table cell**, a **heading line**
(a heading first), and an **authored underscore tier**, because an explicit
instruction outranks the theme's default. They also
never reach a leaf that draws as something else — a link keeps its variant, a
backtick chip its pill, an image itself, and a bar, ring or day chip its own
drawing.

```md
## Text Styles

Heading1:
- Font Name: work sans
- Font size: 42
- Font weight: 900
- Font color: #000000

Text
- Font Name: work sans
- Font size: 16
- Font weight: 400
- Font color: #000000

Muted
- Font size: 13
- Font color: #8A87A0

Lead
- Font size: 20
- Font weight: 500

Display
- Font size: 32
- Font weight: bold
- Font color: #1A1A22

Key
- Font size: 12
- Font color: #8A87A0

Value
- Font size: 32
- Font weight: bold
- Font color: #1A1A22
```

Defaults: font `Arial`, body size `13`, labels size `11`, color `#3C3C3C`; heading sizes
`28 / 22 / 18 / 15 / 13 / 12` for H1–H6 with progressively lighter colors. `Font weight`
is a numeric-ish weight string (e.g. `400`, `700`, `900`).

An omitted tier block is derived from `Text` rather than carrying a fixed size, so
a theme that only restyles the body keeps its tiers in proportion: `Muted` = 0.85×
body (in the muted grey `#9A9A9A`), `Lead` = 1.25× body, `Display` = 2.0× body and
bold. A block that states only *some* bullets still gets the derived value for the
rest, whatever order the blocks appear in.

---

## 5. Other sections

### `## Links`
Pill style for link buttons, one `###` block per variant.

With no `## Links` block and no `Links …` text style, buttons draw in md2ui's built-in
greys: Primary an ink pill with a white label, `*…*` white with an ink outline, `**…**` a
light-grey pill, the other variants as Primary; a backtick Text link stays plain text. A
theme that styles links in either place takes them over and starts from no fill, no
stroke and the body text colour, so its links draw exactly as it writes them.
```md
Corner radius: 16               (default 16)
Fill color: #000000             (default: none, once the theme styles links)
Padding: 10                     all sides (default 10)
Padding left: 16                or per-side: top | left | right | bottom
Stroke width: 0
Stroke color: #000000           Fill/Stroke color also take a bullet list (§6)
Stroke align: center            center | inside | outside (§3 Borders & shape)
Background image: texture.png
Background gradient:            same syntax as section gradients (§3)
Outer shadow:                    same four bullets as section shadows (§3)
Inner shadow:
Emoji shape: circle             circle | square — an emoji-only label, see below
Emoji gap: 8                    px between a label's leading/trailing emoji and its words
Emoji weight: 300               100–900: the weight of this button's emoji (see below)
Emoji fill: 1                   0–1: an icon font's fill axis for this button's emoji (below)
Emoji grade: -25                its grade axis
Emoji optical size: auto        px, or `auto`: its optical size axis
Disabled fill color: #D9D7E4    used when the link is ~~struck~~
Disabled text color: #9A97AD
Disabled stroke color: #00000000
Segmented: yes                  a choice run as one control (default no), see below
```
`Padding` is per-side (like Root/Sections): `Padding: N` sets all sides, and
`Padding top/left/right/bottom: N` override one — so you can give a link wide horizontal
and tight vertical padding. (Link *text* color/size is set under `## Text Styles` →
`Links`.)

Button backgrounds use the same clipped layer order as sections and cards:
outer shadows → solid color → cover-fitted image → gradient → inner shadows,
with the existing stroke painted last. `Background color(s)` is accepted as an
alias for `Fill color(s)`. These properties participate in each button variant's
normal Primary fallback. A variant that declares shadows of a kind replaces
Primary's of that kind (§3 *Several at once*).

**Which variant a link gets** comes from how the markdown wraps it:

| Markdown | Variant | Markdown | Variant |
|---|---|---|---|
| `[text](url)` | Primary | | |
| `*[text](url)*` | Secondary | `_[text](url)_` | Quinary |
| `**[text](url)**` | Tertiary | `__[text](url)__` | Senary |
| `***[text](url)***` | Quaternary | `___[text](url)___` | Septenary |
| `` [`text`](url) `` | Text (checked last — a backtick label wins) | | |

The same holds for an emoji-only label (`_[⭐](/x)_` is the Quinary icon button).
Quinary, Senary and Septenary inherit from Primary like the other button
variants, so a theme without those blocks draws them as Primary; their text
styles are `Links Quinary` … `Links Septenary` under `## Text Styles`. The
default theme uses them as the small ladder `MEANINGS.md` declares: `_` the main
action small, `__` a second action small, `___` an extra-small action.

**One rule for every element.** Links, emojis and chips all read the
wrapper by **length** — each extra marker is one more step down the hierarchy.
The table lives once, in `grouper_types._ELEMENT_VARIANT_BY_LEN`. Buttons and
chips add an underscore ladder of their own; for emojis `_` is a synonym
of `*`.

**`Text` is a plain text link, not a button variant.** It has its own shape
(`### Text`) and its own text style (`## Text Styles` → `Links Text`), and it never
falls back to `### Primary`, `Links` or any other variant: a key its blocks do not
state takes the built-in default. So a theme with no Text blocks draws it as bare
plain text: no fill, no stroke, the default text style. Under `## Links`,
`### Quinary` is the small button above, not the Text link.

Because the backtick label already claimed that variant, an emphasis wrapper
around it styles the **label** instead of picking a different variant:

| Markdown | Renders as |
|---|---|
| `` [`text`](url) `` | pure text, regular |
| `` *[`text`](url)* `` | pure text, *italic* |
| `` **[`text`](url)** `` | pure text, **bold** |
| `` ***[`text`](url)*** `` | pure text, ***bold italic*** |

Only the face changes — no fill, same padding, same size. This is the one place
an emphasis wrapper *around* a link becomes a face: everywhere else the wrapper *is*
the variant, whose weight comes from its `## Text Styles` block.

**Emphasis *inside* the brackets styles the label** of any variant, in that variant's
own family, size and colour: `[**Book**](url)` is bold, `[_Book_](url)` italic,
`[***Book***](url)` bold italic, and the markers are never drawn. `_x_` there is
italic, not the Muted tier. A family loaded without an italic file draws italic as a
slanted upright face, as a browser does, so the label is never left upright.

**`~~` is a *state*, not a variant** — and never a strikethrough rule.
`~~*[text](url)*~~` is a Secondary button drawn in Secondary's `Disabled …`
colors; it rides on top of whichever variant the wrapping picked, exactly like a
pure-emoji label does. Only paint changes: corner radius, padding and
emoji shape stay the variant's own, so a disabled button keeps its size and its
place in the layout. A set `Disabled …` key replaces its colour; one left out
keeps the variant's ordinary colour. A variant that sets none of the three is
drawn in its ordinary colours at 40% opacity, so the state is never invisible.
Its shadows and its background image are always drawn at 40% opacity, whatever
`Disabled …` keys are set, as a muted chip's and badge's are. For a button variant, unset keys also cascade from `### Primary`, like every
other field; a Text link's come from its own `### Text` block only. An emoji in
a disabled button takes the disabled label colour, and its `## Fixed colors` pin
does not apply.

A struck link left *inside* a line of text is drawn as an ordinary inline link
(`### Inline` below) — no disabled paint, no strike. What an inline disabled link
should look like is not decided yet.

**`Segmented` is a key of the whole `## Links` section**, written before any `###` block
(written inside one, it still applies to the section). It decides how a **choice run** is drawn: buttons divided by ` | ` that
are all options of one `md2ui.choice` name (`skills/elements.md`). With `Segmented: yes` the
run is one segmented control: a surface in the Secondary button's paint, the chosen option's
own Primary pill on it, the others their labels only, a thin divider between two unchosen
neighbours. Unset (the default), the run is separate pills, the chosen one Primary and the
rest Secondary. Only the paint differs: each option keeps its box, its click and its
behaviour, and a run that does not fit one line is separate pills either way. Buttons
divided by ` | ` without a shared `md2ui.choice` (plain tabs) are separate pills whatever
this key says.

#### `### Inline` — links inside a line of text

A link left inside a sentence, and an `<autolink>`, are painted as a **span of
text**, not a pill: no fill, no padding, no corner radius. Its own block, with
two keys:

```md
### Inline
Text color: #4682D2
Underline: yes            (default no)
```

A link the author **quoted** is painted from this block too. `"[Docs](/d)"` is how a
link that owns its line declines the pill and reads as prose; the quotes are consumed.

### `## Inline Code`
Chips: the pill for a **standalone** `` `code` `` element. (A `code` span left
inside a sentence is a *marker* instead — see `Marker text color` /
`Marker background color` under `## Text Styles`. So is one the author **quoted**:
`` "`code`" `` declines the chip on a line the span owns.)
```md
Corner radius: 16               (default 4)
Padding: 2                      all sides (default 2); or Padding top/left/right/bottom
Fill color: #E6E6E6             Fill/Stroke color also take a bullet list (§6)
Background image: texture.png
Background gradient:            same syntax as section gradients (§3)
Outer shadow:                    same four bullets as section shadows (§3)
Inner shadow:
Stroke color: #00000000
Stroke width: 0
Stroke align: center            center | inside | outside (§3 Borders & shape)
Emoji weight: 300               100–900: the weight of an emoji inside this chip
Emoji fill: 1                   0–1: an icon font's fill axis for an emoji in this chip
Emoji grade: -25                its grade axis
Emoji optical size: auto        px, or `auto`: its optical size axis (`## Emoji styles`)
Disabled fill color: #EEEEF0    the muted chip, `` ~~`x`~~ ``
Disabled text color: #96969D
Disabled stroke color: #00000000
```
`Padding` is per-side, same as Links.

**`` ~~`x`~~ `` is the muted chip** — a state, as on buttons: the chip keeps its
variant, size and place, and is drawn in its `Disabled …` colours, with no strike.
The `~~` may sit outside or inside the variant's wrapper (`` ~~*`x`*~~ ``,
`` *~~`x`~~* ``). A set key replaces its colour and one left out keeps the ordinary
one; a variant that sets none of the three is drawn at 40% opacity. Its shadows
and its background image are always drawn at 40% opacity, whatever `Disabled …`
keys are set. A muted chip takes no `## Fixed colors` pin.

Chip backgrounds use the same clipped layer order as button and section
backgrounds. `Background color(s)` is an alias for `Fill color(s)`; images,
gradients, and shadows may be declared on Primary or any wrapper variant and
inherit through that variant system; a variant's shadows of a kind replace
Primary's of that kind (§3 *Several at once*).

**A stroke pinned in `## Fixed colors` still needs a width here.** A
`### Badges` → `#### Exact` entry naming a `Stroke color` paints nothing while
this block says `Stroke width: 0` — a pin supplies the color, never the
geometry. To outline only the pinned chips, set `Stroke width: 1` with
`Stroke color: #00000000` so every unpinned chip draws an invisible one.

**`Corner radius` never widens the chip.** The glyphs are inset by half the
radius so they never touch the curve, and that inset is clamped to the chip's own
height — so an oversized value (the CSS "fully rounded" idiom) gives you a
stadium rather than a pill hundreds of pixels wide that can never share a row
with its siblings. That is the same thing a large radius already means on a link
button, which never sizes from its radius at all. A radius that fits inside the
height behaves exactly as it always did.

**Seven wrapper variants**, chosen by the wrapper's character and **length**:

| Markdown | Variant | Markdown | Variant |
|---|---|---|---|
| `` `code` `` | Primary | | |
| `` *`code`* `` | Secondary | `` _`code`_ `` | Quinary |
| `` **`code`** `` | Tertiary | `` __`code`__ `` | Senary |
| `` ***`code`*** `` | Quaternary | `` ___`code`___ `` | Septenary |

The keys above — with no `###` subsection — configure Primary, exactly as they
did before variants existed. Add `### Secondary` … `### Septenary` blocks to
override; each inherits every key it does not state, in any block order, and an
undeclared variant draws as Primary. Per-variant fonts come from `## Text Styles`
→ `Inline Code <Variant>` and `Code Block`.

The asterisk column is the same length-ordered scheme `## Links` and
`## Emoji styles` use. Buttons share the underscore column; for emojis `_`
stays a synonym of `*`.

### `## Code Blocks`

Fenced and indented Markdown code blocks are full-width, whitespace-preserving
surfaces. A fenced block's first info-string word selects its Pygments lexer;
both ordinary and class-style info strings are accepted:

````md
```python
def greet(name):
    return f"Hello {name}"
```

~~~{.typescript}
const ready: boolean = true;
~~~
````

A fence can also be the direct content of a list item (````- ```md```` with its body and
closing fence indented to the item's column). Source that looks like Markdown or an HTML
comment remains literal inside every supported code block.

An absent or unknown language is rendered as plain code; md2ui never guesses a
language from the source. Markdown markers inside the block remain literal.
Configure its font independently under `## Text Styles`:

```md
Code Block
- Font Name: IBM Plex Mono
- Font size: 13
- Font weight: 400
- Font color: #E6EDF3
```

The named family must be available to Skia or loaded under `## Fonts`, like any
other custom font; one that is neither draws in the system's monospaced face
(Courier on macOS), so the code keeps its columns, and `md2ui check` names it.
The block surface and syntax palette are separate:

```md
## Code Blocks
Syntax style: monokai
Background color: #161B22
Corner radius: 12
Padding: 16
Line spacing: 4
Min width: 320
Max lines: 20
Fade: yes
```

`Syntax style` is a Pygments style name. A token colour supplied by that style wins; when
the style leaves a token uncoloured—ordinary names and text commonly are—the renderer uses
`Code Block` → `Font color`. That fallback also paints every token when the language is absent
or unknown, so choose it for contrast with `Background color`. An unknown syntax style falls
back to Pygments' `bw`, as an unset one does (grayscale); `Background color` always comes from THEME.md rather than from
the Pygments style.

Code does not wrap. A block fills the width it is given, and asks the page for no more than
`Min width` (default 320) however long its lines are, so one long line never widens the
page. A block whose code is narrower asks only for its own width. A line longer than the
block is clipped at its right edge.

A block is at most `Max lines` tall (default 20), cut between two lines, so one long listing
never covers the page; `Max lines: none` shows every line. In the window, a cut block scrolls:
a scroll that starts over it moves its lines, down past the cut and across past the right
edge, and a thin bar on each side shows where you are. In a row, a code block takes the
row's height: beside a taller neighbour it shows more of its lines, up to all of them, and
the rest of the surface is its background; beside a shorter one its own height sets the
row's.

With `Fade: yes` (the default) a clipped edge — the right one, the bottom one or both —
fades into the block's background so the cut reads as "there is more". `Fade: no` clips
hard.

Every block carries a copy button at its top right, in a strip above the code, so it never
covers a line. A click copies the block's whole source, including anything clipped. It has
its own style under `### Copy Button`, with the keys a `## Links` variant takes — `Fill
color`, `Corner radius`, `Padding`, `Stroke`, `Gradient`, `Background image`, `Shadow` —
plus its icon and the icon's size:

```md
## Code Blocks
### Copy Button
Icon: 📋
Icon size: 14
Fill color: #FFFFFF22
Corner radius: 6
Padding: 4
```

The button is square: the icon size plus its padding. `Icon: none` removes the button and
its strip. The icon draws in `Code Block` → `Font color`.

### `## Content Weight`
Emphasis tiers the model assigns per node (`first`/`second` scale the font size up;
`less` scales down and recolors).
```md
First scale: 1.30
Second scale: 1.15
Less scale: 0.85
Less color: #9A9A9A
```
These are *predicted*, not authored. A leaf carrying a display tier
(`_x_` / `__x__` / `___x___`, §4) suppresses them outright — an explicitly sized
line is never rescaled by a guess.

### `## Content arrangement`

Targeting for the bento mosaic (§2). Inert unless `Layout: Bento` is set on
`### Root` (§3) — this section chooses *what* tiles, not *whether* it tiles.

```md
## Content arrangement

### Bento
Heading level: 2            which level's sections become the cells
```

| | |
|---|---|
| unset | **auto** — the shallowest heading level with 3 or more sections in a row under one parent |
| `Heading level: N` | tile level `N` (clamped 1–6) |

The named level is **absolute**. If no parent holds a run of 3+ sections at that
level, the document simply stacks — it does not quietly fall back to the automatic
pick, because a silent retarget is harder to debug than no mosaic at all.

Raising the level tiles deeper and smaller. On a document of `##` sections that each
contain `###` subsections, auto picks 2 and the `##` sections tile as whole cells;
`Heading level: 3` instead stacks the `##` sections full width and tiles the `###`s
inside each one.

Note the level names the **cells**, not the container. There is no key for the
container: it is always whoever holds the run, root included.

### `## Fixed colors`

Colors that carry **meaning**, and so outrank both rotation and replacement. A
❤️ is red because red is what it *means*; a 📉 is amber because the number fell.
Rotation deals colors out (§6) and replacement fixes the ones that land badly —
a pin is neither.

```md
## Fixed colors

### Emoji
- ☀️ #F0A93B                 glyph only
- 📈 #22C55E datapoints      + the value beside it
- ↗️ #10B981 line            + the whole run
- 🔥 #E5484D text chips      + the words and chips of the run

### Emoji background
- 📈 #E9F9EF

### Badges
#### Exact
- Sold out: Text color: #991B1B, Fill color: #FEE2E2
#### Contains
- ⬇: Text color: #E5484D, Fill color: #FDEDEC, Stroke color: #F7C8C5

### Buttons
#### Exact
- Cancel: Text color: #26262B, Fill color: #E5E7EB
#### Contains
- Delete: Text color: #FFFFFF, Fill color: #DC2626, Stroke color: #991B1B

### Datapoints
- change up: #16A34A
- change down: #E5484D
```

**Scope is the whole emoji design.** The optional word after the color says how
far it reaches — nothing (the glyph alone, which is what Fixed colors always
did), `datapoints` (also the datapoints beside it: values, links and other
emojis), or `line` (the whole run, words included). So `☀️ 75°` keeps a black
temperature beside an amber sun, while `📈 5.1% from last month` greens the
percentage and leaves the words grey.

**Or name the kinds it paints.** `text`, `emojis`, `buttons` (text links
included) and `chips` color those pieces of the run and leave the rest as they
are; a datapoint counts as the kind that holds it, so a number in the words is
`text`. Words add up: `- 📈 #22C55E chips datapoints` colors the chips and every
datapoint. A kind colors the text only, never a chip's or button's fill or
outline — those are `### Badges` / `### Buttons` and `## Color Replacements`.

A pin reaches past its glyph only when the glyph is a piece of its own: a run cut
into pieces (`🔥 - Hot deal - \`Sale\``) or a line of elements (`🔥 \`Sale\` \`New\``).
In a sentence (`🔥 Hot deal today`) the glyph and its words are one piece: `line`
and the kinds color the glyph alone there, and `datapoints` the glyph and the
datapoints of that sentence.

**A pin matches the glyph with or without its variation selector.** `- ☀️ #F0A93B`
reaches `☀` too, and the reverse, as `### Badges` keys always did, so a pin does not
depend on which spelling an author's keyboard emitted.

For a ready-to-copy transparent chip and exact amount-color example, see
[skills/theme/README.md](skills/theme/README.md#from-skillsbanking-examplemd).
Use `Fill color` under `## Inline Code`, and put exact-label rules under
`## Fixed colors` → `### Badges` → `#### Exact`. These keys style the chip surface and label.

**Pills.** `Exact` matches a chip's whole label. `Contains` matches any chip
holding the key, which is the only way to color one whose text changes every
render — a single `⬇` row colors every falling metric, border included.

**Buttons.** `Exact` and `Contains` use the same matching rules for a standalone
link button's visible label. They are independent from `Badges`: a `Delete` rule
under `Buttons` cannot recolor a chip, and the same rule under `Badges` cannot
recolor a button. Exact matches win over contains matches. Matching is
case-sensitive. A disabled button keeps its `Disabled … color` state instead of
its label pin.

**A pin paints only what the variant paints.** One entry serves every variant
of the label, and each surface lands only where that variant already draws it:
a `Fill color` pin skips a variant whose fill is transparent, and a `Stroke
color` pin skips one with no `Stroke width` (a width with no color is a stroke
the pin colors). Every variant paints its label, so `Text color` always applies.
Pills follow the same rule, so a pin cannot give a surface to a chip whose
variant has none — give that `## Inline Code` variant a fill.

One entry can give a red label to an outline and a white one to a filled
button. Pin the label the same color as the fill: on the filled variant it
equals the surface behind it, so the pin is dropped (see *The one exception*
below) and `## Color Replacements` answers for that surface. It replaces the
variant's own label color, not the dropped pin, so write the rule as that
surface's text default rather than keyed on `#FA3C4F`:

```md
## Fixed colors
### Buttons
#### Exact
- Cancel: Text color: #FA3C4F, Fill color: #FA3C4F, Stroke color: #FA3C4F

## Color Replacements
On background color: #FA3C4F
- Replacement: #FFFFFF
```

`[Cancel](/x)` is a red pill with a white label; `*[Cancel](/x)*`, an outlined
variant, keeps its clear fill and draws a red outline around a red label.

**Datapoints** key on the detected type plus `up`/`down` for a signed value,
because the direction is what the color means. A sign detached from its number
still counts, and is painted with it — otherwise `+2,588` renders a grey plus
beside a green figure.

**The one exception.** A pin that, painted over what shows behind it, leaves
exactly that color is dropped, and ordinary replacement runs instead, so a red 🔻
on the red card a rotation just dealt does not vanish. What shows behind is every
layer composited: a 10% green fill over a green section is green, so a label
pinned green on it is dropped too. A fully clear pin (`#00000000`) is an authored
"no fill" and always kept. Exact match only — no threshold to tune.

Leave the section out and nothing is pinned.

### `## Color Replacements`

Swaps a painted color when what is **behind** it would make it illegible. Each
rule names a background, a channel, the color to replace, and its replacement:

```md
## Color Replacements

On background color: #101010
- Text color:   #0A0A0A,   Replacement: #FFFFFF
- Fill color:   #101010,   Replacement: #FFFFFF     # the button pill flips
- Stroke color: #00000022, Replacement: #FFFFFF33   # the ___ divider
- Replacement:  #FFFFFF                             # text's default here

On background color: image
- Replacement: #FFFFFF
```

`On background color:` takes a hex, or the word `image` for a card whose
background is a photo. `image` followed by a fixed style's name
(`On background color: image Music player`) covers only the photo that style
paints, so a pale photo and a dark one can take different ink; a fixed style
with no group of its own uses the `image` one. The channel keys are the same ones you already write in
`## Links`, `## Inline Code` and `## Horizontal Rule`. A bullet naming no
channel is that background's **text** default.

**Three channels, and the spellings each accepts.** A key outside this list is
not a channel, and the bullet falls back to being that background's text
default — so a typo changes your text colour rather than doing nothing.

| channel | write any of |
|---|---|
| text | `Text color`, `Text`, `Color`, `From` |
| fill | `Fill color`, `Fill`, `Background color`, `Background` |
| stroke | `Stroke color`, `Stroke`, `Border color`, `Border` |

**Fill is what a drawn graphic uses.** A bar's fill and track, a ring's arc and
track, and a chart's bars all resolve through the `fill` channel, even though
they are *declared* with `Background color:` under their own `###` block. So one
`Fill color` rule per background is what makes a figure legible on a white card
and a dark one without per-card styling. Every bar family, `### Key Value Bars`
and the K-V unit ratio included, follows these rules.

> **`image` also names a page background.** The nearest visible surface owns
> the context: an unfilled element on that page uses the image rule, while a
> card with its own visible fill uses only that fill's rules. Photo cards still
> use `image` because the photograph is their nearest surface:
>
> ```md
> On background color: image
> - Replacement: #FFFFFF          # the photo cards
>
> On background color: #FFFFFFAA  # optional rules for the glass cards
> - Text color: #FFFFFF, Replacement: #2B2B2F
> ```
>
> A card-fill rule is needed only for colors that should actually change on
> that card; the fill itself already prevents the root image rule leaking in.

**The cascade.** An element that paints a fill hands that fill to its own label,
and the fill is replaced *first*. So a black pill on a black card, flipped white
by the `Fill color` rule above, then reads its label from the white group:

```md
On background color: #FFFFFF
- Text color: #FFFFFF, Replacement: #101010
```

No rule ever mentions buttons, and the swap stays scoped to that button instead
of recoloring every white glyph on the card.

The same rule applies at every nested layer. If a card rule changes a component
base from `#121212` to `#2C2C2E`, then `#2C2C2E`—not the card—is the context for
that component's inner fills. Put their mappings under the resolved surface:

```md
On background color: #101010
- Fill color: #121212, Replacement: #2C2C2E

On background color: #2C2C2E
- Fill color: #131313, Replacement: #A99FFF
- Fill color: #141414, Replacement: #FFFFFF

On background color: #FFFFFF
- Text color: #FFFFFF, Replacement: #101010
```

Read this from the outside in: each paint resolves against the visible surface
immediately behind it, then becomes the context for what it contains. Do not
repeat the inner mappings on the outer card; outer rules never skip across a
visible component surface.

**Why it is keyed on the color, not on an element.** With color rotation a
`### ` card takes whichever fill its slot deals it — mint, black, lavender,
yellow — so no style can know in advance it will land on the dark one. One rule
fixes every use of that color, and nothing in `## Text Styles`, `## Links` or
`## Inline Code` changes.

**Which background counts.** The nearest visible surface is the context — the
pill it sits on, else the card, else the nearest painted section, else the page.
Only that surface's rules are consulted. A nonzero-alpha translucent fill (say
`#8778f520`) is visible and therefore establishes context; a fully transparent
fill does not. Within the context, channels are independent and an exact entry
beats that channel's default. A missing channel or unmatched color leaves the
paint unchanged rather than consulting an outer surface.

Fully transparent means alpha `00`, for example `#00000000`. It is absent from
the context hierarchy everywhere—including transparent cards, table cells,
buttons, chips and drawing-element layers—so never write an `On background
color: #00000000` group. Write the rule for the nearest surface that is actually
painted behind it.

Reaches every glyph (prose, headings, button labels, chip text, emoji tints,
gutter markers, table cells, a chart's labels, values, legend and tick labels)
and every pill or line: button and chip fills and strokes, the in-text
`` `code` `` marker background, emojis, and both the horizontal and
vertical rules. A code block is a pill too: its `Background color` resolves
through `fill` against what it sits on, and its highlighted text, its edge fade
and its `### Copy Button` (fill, stroke, icon) then resolve against that
replaced fill. Shadow colours are not covered: a shadow is a translucent
darkening of whatever is behind it, never the ink a rule exists to rescue. A section, card, list item or quote is covered
the way a pill is: its fill and gradient resolve through the `fill` channel of
the surface it sits on, and the replaced fill is then the context for its
contents and its own stroke. So one tint (`### Unordered Lists` at
`#47474714`) can read differently on each panel it lands on:

```md
On background color: #18181B
- Fill color: #47474714, Replacement: #FFFFFF14

On background color: #FFFFFF14
- Replacement: #FFFFFF
```

**One exception:** `Fixed colors` under `## Emoji styles` is never replaced. An
emoji *tint* is a style color and swaps like text, but a pinned ❤️ or 🔻 is a
meaning rather than a look, so the pin outranks every background rule. Only colors change — never a size, never a
position — and it runs *after* color rotation, so it is the last word on a
rotated element too.

Rotation still chooses which fill a section or card is dealt; replacement runs
after it, as everywhere. A table's zebra stripe is replaced when it is painted,
but a row's contents key on the table's first stripe color, since the stripe
index is picked during painting.

The **drawn figures** are covered. A ring's arc, a progress bar's fill and its
track, and the four `### Task controls` state layers all resolve their paint
through this section, so one declaration plus one rule per exceptional background
gives a figure that reads on a white card and a dark one alike. For a task
control the outer layer becomes the background stack its inner layer resolves
against, which is what keeps a white knob visible once its track has been
flipped.

A **section or card's own stroke** is covered too: the lookup starts at the
card's own photograph (`On background color: image`) or its resolved solid fill
and stays in that context. That is how one
`Stroke color` on a heading level draws a solid rim on the photo cards and a
transparent one on the pale cards beside them.

Leave the section out entirely and everything keeps the color its style gives
it. `## Text Color Replacements` is the old name and still parses.

### `## Horizontal Rule`

Supplies the global fallback paint for **`---`**, three dashes or more. Override
`Stroke color` and/or `Stroke width` at a structural level with nested
`Horizontal Rule` blocks under `## Styling & Spacing` (§3).

Markdown has three thematic-break spellings and each one has its own job here.
All three are whole-line, content-free, three characters or more, interior
spaces allowed (`- - -`), and all three cut a run of siblings identically. They
differ only in what they leave behind:

| Spelling | Meaning |
|---|---|
| `---` | the painted rule this block styles |
| `___` | a **content break** — cuts, paints nothing, costs no space |
| `***` | a **section stop** — closes the heading section holding it |

```md
Stroke color: #C0C0C0
Stroke width: 1
```

Two behaviours are built in and take no keys:

- **It always takes the group gap**, above and below, so it never inherits the
  tight element gap from a leaf neighbour (see *Items that override the table*).
- **A rule stays where it is written.** Written between two sections, a `---`
  belongs to the section above as its last child and paints inside that card. To
  divide the two sections instead, close the first one with `***` before the
  rule: the `---` is then a sibling between them, with the gap on both sides.

### Section stops (`***`)

Authored in the markdown, not in the theme — there is nothing to style, because
a stop paints nothing.

A heading owns everything up to the next heading, so a footer row written under
a section is *inside* that section's box and takes its background, padding and
radius. `***` says where the section ends. Everything after it is re-parented as
the section's next sibling, in source order:

```md
##                        <- empty marker: the card (## Heading 2 style)

### Web Design            <- the tinted block (## Heading 3 style)
Crafts engaging, user-friendly websites.
`Landing Page` - `One Page` - `Website`
***                       <- the tint stops here
Explore - [➡️](/web-design)   <- beside the block, still inside the card
```

The rules, all of which fall out of "a stop closes the section holding it":

- **It composes.** A stop that ends up first in a lifted tail becomes the
  parent's stop and closes that level too, exactly as if it had been written
  there. Two stops in a row therefore climb two levels.
- **A stopped section cannot be re-entered.** A deeper heading written after the
  stop is lifted out with the rest of the tail, as a sibling.
- **With no section to close it only cuts.** At the top of a document, or in a
  fragment with no headings, `***` behaves like `___`.
- **Spacing is not special.** The lifted content is an ordinary sibling and takes
  whatever gap the table above gives it.

Note the interaction with `Rotate colors: sync`: once the tinted section is the
only one inside its wrapper, its own cycle deals it slot 0 every time. Put
`sync` on the level that **lends** the slot (the wrapper), never on the one
borrowing it.

### `## Separators`

Row separators (` - `, ` | `) are **consumed** by the split — the line becomes its
pieces and the character is gone. These flags say whether it is drawn back into the
gap between those pieces. Purely display: the grouper only records *which*
character split the line, so the same markdown renders either way. A dot (` • `
` · `) divides nothing: it is text, drawn where it is written.

```md
Dash: hide          # ` - `
Bar: hide           # ` | `
```

`show` / `hide` (`yes` / `no` / `true` / `1` also work); both are hidden by default.
A drawn separator takes the **element** gap on both sides whatever it separates.

### `## Vertical Rule`

The vertical twin of `## Horizontal Rule`: paints ` | ` as a drawn line spanning
the row instead of a pipe character.

```md
Draw: no
Stroke color: #C0C0C0
Stroke width: 1
```

`Draw` **wins over `Bar`** above, so it is not gated on the glyph flag — every
pairing is defined:

| `Bar` | `Draw` | Result |
|---|---|---|
| `hide` | `no` | nothing |
| `show` | `no` | the `\|` character |
| any | `yes` | the line |

`Bar: hide` + `Draw: yes` is the useful combination: no pipe, just the line.

### `## Emoji styles`

The section name is `## Emoji styles`. `## Emojis` is not an alias — like any
unrecognised heading it is ignored, so a block written under it has no effect.

```md
Font: assets/fonts/NotoColorEmoji.ttf   (path to an emoji font; default none)
```

The configured emoji font is used consistently for emoji and common Unicode
symbol ranges wherever they occur: prose, mixed link labels, emoji-only links,
inline elements, and standalone badges. Body-font coverage does not decide
whether glyphs such as `↗`, `▶`, `⭐`, or `🔖` render.


Emojis are styled on **two independent axes**:

1. **Context** — which block applies, from the role the grouper tagged:
   `### Primary` (heading + standalone badges — the only one with the full badge
   treatment), `### Text` (peeled, in-prose, and **quoted**), `### Link`,
   `### Inline`.
2. **Wrapper variant** — only for the badge, chosen by wrapper **length**
   (underscores are synonyms):

| Markdown | Variant |
|---|---|
| `🔎` | Primary |
| `*🔎*` | Secondary |
| `**🔎**` | Tertiary |
| `***🔎***` | Quaternary |

**A quoted emoji has no variant** — `"🔎"` is the author declining the badge, so it
is drawn from `### Text` at the surrounding size, and the wrapper around the quotes
styles it as ordinary text would be styled (`_"🔎"_` Muted, `___"🔎"___` Display).
The quotes are consumed, not drawn.

**`Color` under `### Text` is the DEFAULT tint for a glyph sitting in text, not an
override.** Whatever set this text's colour more specifically wins — a `## Text
Styles` tier, a table role, a heading, an emphasis, a `## Fixed colors` pin — so
`_Muted text with an emoji_` paints the glyph in the muted colour, not the emoji
tint. `Color` applies where nothing more specific did, which for most documents is
ordinary body text. A per-glyph `## Fixed colors > ### Emoji` pin still outranks
everything: it is a statement about that glyph (❤️ is red), not a style inherited
from its surroundings. This is the per-instance counterpart to
`Emoji aside`: both change what a lone emoji becomes, one from the document and
one from the theme.

`### Secondary` / `### Tertiary` / `### Quaternary` sit beside `### Primary` and
inherit every key they do not state, in any block order. A list-valued key
(`Background colors`, `Icon color`) **replaces** the inherited list rather than
extending it. The same length-ordered scheme as `## Links` and `## Inline Code`.

`Icon size: N` sets the glyph size inside the badge (`Size` is accepted as a
synonym), and `Icon color` / `Icon colors` tint it.

The badge background accepts the complete shared paint vocabulary:
`Background color(s)`, `Background image`, `Background gradient`, outer/inner
shadows, corner radius, padding, and stroke. Layers are clipped to `Shape` and
paint in the same order as section, button, and chip backgrounds. These layers
also inherit from Primary into the wrapper variants; a variant's shadows of a
kind replace Primary's of that kind (§3 *Several at once*).

`Shape: circle|square` squares the badge into a 1:1 box: `circle` draws it
round, `square` keeps its `Corner radius`. It is honoured only when the badge
paints a background — a bare glyph is never shaped.

**`~~⭐~~` is the muted badge** — the same state as on chips and buttons: the
badge keeps its variant, size, shape and place and is drawn in muted colours, with
no strike. Its keys are named after the badge's own:

```md
Disabled background color: #EEEEF0
Disabled icon color: #96969D
Disabled stroke color: #00000000
```

A set key replaces its colour and one left out keeps the ordinary one; a variant
that sets none of the three is drawn at 40% opacity. Its shadows and its
background image are always drawn at 40% opacity, whatever `Disabled …` keys are
set. A muted badge takes no `## Fixed colors` pin.

**`Emoji weight: 100–900`** on `### Primary` … `### Quaternary` draws that
badge's glyph in another weight of the emoji font's family: a variable font is set
on its weight axis, a static one takes the nearest sibling file beside it
(`NotoEmoji-Light.ttf`, `NotoEmoji-Bold.ttf` …). Use it to even out stroke
thickness across badge sizes. Buttons and chips take the same key in `## Links`
and `## Inline Code`; an emoji in prose keeps the `Font` as loaded.

**`Emoji fill`, `Emoji grade` and `Emoji optical size`** set the other axes of a
variable icon font named as the emoji `Font:` (Material Symbols has all of them),
in the same blocks as `Emoji weight` and inherited between variants the same way:

```md
Emoji fill: 1                   0–1: the outline (0) or the filled icon (1)
Emoji grade: -25                the stroke's grade, thinner below 0, heavier above
Emoji optical size: auto        a size in px, or `auto`: the size the glyph is drawn at
```

Each value is clamped to the font's range on its axis, and a key whose axis the
font does not have changes nothing, so on a static font these keys do nothing.
Left out, an axis stays at the font's default. `auto` draws a small badge or a
chip's emoji with the font's small-size design and a large badge with its
large-size one.

#### Emoji as icons: `material-design-icons-md2ui.ttf`

`assets/icons/material-design-icons-md2ui.ttf` is an emoji font in which every emoji, and
every symbol md2ui draws from the emoji font, draws as a Material Symbols Outlined icon.
The document keeps its emoji; only the drawing changes:

```md
## Emoji styles
Font: assets/icons/material-design-icons-md2ui.ttf
```

- **The closest similar icon.** `⭐` → star, `📞` → call, `👉` → an arrow pointing right. Many
  emoji share an icon, and an emoji with no close icon takes a broader one (`🦒` → pets).
  `square` is the last resort.
- **One colour.** An icon takes the tint of where it is drawn, as any single-colour emoji font
  does. Emoji whose meaning is their colour (`🟢 🔴`, the coloured squares and hearts) draw alike
  unless the theme pins them under `## Fixed colors > ### Emoji`.
- **Solid against hollow is kept** where that is the meaning: `★ ☆`, `● ○`, `■ □`, white and
  black chess pieces. Those icons ignore `Emoji fill`; every other icon follows it.
- **Bars stay bars.** `▓` and `█` draw as a filled square and `░` and `▒` as an outlined one, so
  `▓▓▓░░` reads as a bar.
- **Every flag draws as one flag icon**, and an emoji with a skin tone draws as the same emoji
  without one.
- **The icons fill md2ui's emoji box,** so swapping this font in for an emoji font moves no
  layout. All four axes are variable, so `Emoji weight`, `Emoji fill`, `Emoji grade` and
  `Emoji optical size` apply.

The table `assets/icons/material-design-icons-md2ui.md` lists which icon each character
draws, and its header gives the rules. To change a row, edit the table and run
`uv run python scripts/build_icon_font.py` (ADR-407).

**`Shape` reaches badges, never buttons.** An emoji written as a link label —
`[➕](/add)` — is a **button**, not a badge: the link owns its label, so none of
this section's badge keys apply to it. Its shape is the `Emoji shape` key of its
`## Links` variant (`circle` by default, or `square`); see *An emoji inside a
button* below. The glyph inside it is drawn in `### Link`'s `Font`, and in the
button label's colour (below).

#### An emoji inside a button

Separation puts an emoji *beside* a pill. Writing it into the link's own label
puts it **inside** one, which is what a nav row, a menu item or an icon CTA
wants:

```md
⭐ - [Saved](/saved)          a badge, then a separate pill
[🔖 Saved](/saved)           one pill with the icon inside it
```

The label keeps the variant its wrapper picked, so a run of these on consecutive
lines is a menu whose active row is a bare `[…]` and whose others are `**[…]**`.
An emoji-only label (`[▶️](/play)`) additionally takes the variant's
`Emoji shape` from `## Links` — `circle` (the default) or `square`, a 1:1 box at
the variant's `Corner radius` — which is how the circular icon button is written.
It is as tall as a text label of the same variant: the glyph takes the variant's
top and bottom padding on every side, so an icon button stands level with the
text buttons beside it whatever the left and right padding.
`## Emoji styles` → `Shape` does not apply to it: that key shapes badges only.

**The emoji takes the label's colour.** An emoji inside a button is drawn in its
variant's label colour — white on a dark fill, dark on an outline — after the same
colour replacements as the label, and disabled when the button is. A
`## Fixed colors` pin on the glyph still wins on an enabled button.

**`Emoji gap`** under `## Links` (or a variant block) sets the space between a
leading or trailing emoji and the label's words. It replaces whatever spaces the
author typed there, so `[🔖Saved]` and `[🔖 Saved]` draw alike. Without it, the
typed space is the gap.
### `#### Marker` — list and quote markers (opt-in)

Marker appearance lives with the background level it labels. Put `#### Marker`
last inside `### Unordered Lists`, `### Task Lists`, `### Numbered Lists`,
`### Quotes`, or an exact `### Heading 1`–`### Heading 6` level. Leaving the
nested block out keeps that level's marker inactive.

```md
## Styling & Spacing

### Unordered Lists
#### Marker
Shape: circle        # circle | square — a Size×Size filled glyph tinted by Color
Size: 8
Color: #4B3F91
Space: 10            # gap between the marker and the content
# Emoji: 🔹          # draw this glyph instead of Shape; Color tints the glyph
Aside: yes            # yes = left gutter; no = marker above the body
Alignment: top        # top | center | baseline | bottom; aside markers only

### Numbered Lists
#### Marker
Number format: 1     # 1 (bare, default) | 1. | 1) | (1)
Font name: work sans
Font size: 16
Font weight: bold
Font color: #4B3F91
Space: 10
```

`Aside: yes` is the default and lays out `row[marker | content]`. `Aside: no`
lays out `col[marker, content]`, left-aligns the marker, and uses `Space` as the
vertical gap. The boolean spellings `true` and `false` are equivalent to `yes`
and `no`. `Alignment` defaults to `top`; `center` and `bottom` align against the
whole item body, while `baseline` aligns text/emoji baselines to the body's first
baseline and places a shape's bottom edge on that baseline. Alignment only
changes aside placement; a marker above the body is always left-aligned.

The number is the item's running 1-based ordinal.
`Color` and the numbered marker's `Font color` accept either one color or a
list of `- #RRGGBB` entries. A list advances once per list row and restarts in
the next enclosing heading section.

Marker colors participate in `## Color Replacements` at paint time against the
marker's actual background. A bullet `Shape` and a quote `Bar color` use the
**fill** channel. A numbered marker's `Font color`, a quote character's `Font
color`, and an emoji marker's `Color` use the **text** channel. Replacement runs
after the marker's color list has selected its rotation slot.

```md
## Color Replacements
On background color: #102A43
- Fill color: #4B3F91, Replacement: #B8F2D0
- Text color: #4B3F91, Replacement: #B8F2D0
```

`### Task Lists` accepts the same bullet-marker keys. Its active marker wins;
otherwise task rows fall back to the `### Unordered Lists` marker. A drawn task
control still suppresses an extra gutter marker.

```md
### Task Lists
#### Marker
Emoji: ✓
Color: #4B3F91
Space: 10
Aside: yes
Alignment: center
```

Numbered headings take a numbered marker only from their exact Heading N
background block; heading levels do not fall back to one another.

```md
### Heading 2
#### Marker
Number format: (1)
Font size: 18
Font color: #4B3F91
Space: 8
Aside: no
```

For single-level blockquotes (`>` lines), two mutually-exclusive modes are available —
**bar** (a thick full-height vertical rule) or **char** (a quote glyph styled
like a numbered marker); bar wins if both are set. Unset ⇒ no marker.

```md
## Styling & Spacing
### Quotes
#### Marker
Bar width: 4
Bar length: 50
Bar color: #C0C0C0
Space: 12
Aside: yes
Alignment: top
# Quote char: "      # instead of a bar; the Font * keys below style it, any left out use the default text style
# Font name: work sans
# Font size: 28
# Font color: #C0C0C0
```

An aside bar is vertical and spans the quote's full height, so its `Alignment`
has no visible effect. With `Aside: no`,
it becomes a horizontal rule above the body: `Bar width` remains its thickness,
and `Bar length` is its fixed length (50px by default, capped by available width).

**How many bars you get is a document question, not a theme one.** The bar spans
one blockquote, and CommonMark makes consecutive `>` lines a single blockquote —
so three glued rows share one rule down the side, while three blank-line-separated
rows are three quotes and take a rule each. The second shape is the agenda /
timeline row:

```md
> 4:00 PM - Finish packing        one quote, ONE bar
> 6:00 PM - Drop off keys

> 4:00 PM - Finish packing        two quotes, a bar EACH

> 6:00 PM - Drop off keys
```

`Bar color` and the character marker's `Font color` accept either one color or
a list of `- #RRGGBB` entries. A list advances once per blockquote and restarts
in the next enclosing heading section. Consecutive `>` lines are one
blockquote, so they consume one color together; blank-separated blockquotes
each consume the next color.

### `## Tables`
Table drawing styles. Without this block, tables render as a plain
column-aligned grid with no background of its own (a heading section around
it may paint one); any active key here gives the table its own backgrounds.

> **A table is also how you draw a token grid.** A calendar, a heatmap or a seat
> map is a table whose every cell is an inline-code chip, with the per-token
> state pinned by label under `## Fixed colors` → `### Badges` → `#### Exact`.
> Set `Stacking cards: no` or a narrow column flips the grid into one card per
> row. See `skills/dashboards.md` and
> `skills/renders/calendar-card-detail.png`.
>
> Note the cost in a bento mosaic: a wide table carries a large minimum width,
> and bento is a packing solve. Every hard minimum removes arrangements from the
> search space, so the card holding the table takes the widest cell because the
> packer had no alternative — and the rest of the board is arranged around that
> constraint. Keep minimum widths small unless the content truly needs the room;
> width is a constraint on the puzzle, never a way to steer it.

> **Column alignment is authored in the markdown, not here.** The delimiter row
> carries it per column — `:---` left, `:---:` center, `---:` right — and a
> colon-less `---` column states nothing, so it falls through to the `Horizontal align`
> in force (this level's, the root's). There is no table alignment key.

Four `###` blocks:

- **`### Table`** — the table as a whole.
  - `Merge rows: yes|no` — `yes` draws ONE rounded background behind the whole
    table with zero gaps between rows (header/row fills clip to its rounded
    corners); `no` (default) draws each row separately, spaced apart.
  - `Corner radius` / `Background color` / `Background image|gradient` /
    `Stroke width|color` / `Padding` — the merged-mode shell's paint and inner
    padding (painted only when `Merge rows: yes`).
  - `Row spacing: N` — horizontal gap between **columns**; `Col spacing: N` —
    vertical gap between **rows** (separated mode). Unset = element spacing.
  - `Stacking cards: yes|no` — when `yes` and the table's minimum width does
    not fit the available width, each body row renders as a vertical card:
    the header labels become small keys next to each value. When `no` (or the
    table fits), an overflowing table keeps every column at its
    minimum-unbreakable width and overflows: a pill and a word are indivisible,
    so a narrower column would only be drawn over.
    It also decides **how narrow the page itself may get**. The layout stops
    shrinking at what its content needs (§3, *Max width and Centered*); with
    `yes` a table's share of that floor is what one CARD needs — its widest
    single cell plus the key column — so the window keeps narrowing and the
    tables flip as it goes. With `no` the floor is the whole grid's width, and
    a window under it scrolls horizontally instead.
  - `Card layout: title|keys` — stacking-cards shape: `title` renders the
    row's FIRST cell as the card title (no key label, drawn emphasized) and
    the rest as key/value pairs; `keys` gives every cell a key label.
- **`### Header`** — the header row: `Background color(s)` / `Corner radius` /
  `Stroke` / `Background image|gradient` like any section style; `Padding` is
  the per-label padding inside each header cell; `- Font name/size/weight/color`
  bullets style the header text.
- **`### Cells`** — the body rows, same keys as Header. Two or more
  `Background colors` cycle across rows = zebra striping. In stacking-cards
  mode this style paints each row card (its `Padding` = the card padding).
- **`### Card Keys`** — the stacking-mode key labels, styled separately from
  the header: `- Font name/size/weight/color` bullets, and `Key spacing: N`
  (gap between a key and its value).

```md
## Tables

### Table
Merge rows: no
Row spacing: 12
Col spacing: 6
Stacking cards: yes
Card layout: title

### Header
Background color: #5B4FC4
Corner radius: 12
Padding: 10
- Font size: 12
- Font weight: semibold
- Font color: #FFFFFF

### Cells
Background colors:
- #FFFFFF
- #F1F0FA
Corner radius: 12
Padding: 10
- Font size: 12
- Font color: #2A2A33

### Card Keys
Key spacing: 8
- Font size: 10
- Font weight: semibold
- Font color: #8A87A0
```

### `## Drawing elements`
Drawn replacements for semantic Markdown elements. `## Datapoints` is accepted
as a legacy alias so existing themes continue to parse. Every family is **enabled by
default** with built-in styling; `Enabled: no` opts a family out (its content
falls back to plain text rendering). The grouper always annotates the AST —
these toggles gate only the drawing.

**Task controls.** Exact `[ ]`, `[x]`, and `[X]` tokens become drawings anywhere.
Standard task-list markers (`- [ ] item`), standalone controls, and controls
mixed with adjacent content use the same component. They compose with an
authored spring (`WiFi ... [x]`) so the control can align at the opposite edge.
The linked spelling is
`[[ ]](/enable)` / `[[X]](/disable)`: the URL is retained as an annotation on
the drawing and the control does not become a link button. Escaped tokens and
tokens in code spans stay literal.

```md
## Drawing elements

### Task controls
Enabled: yes
Type: checkbox              # checkbox | switch
Size: 32                    # checkbox minimum/default 32
Padding: 4                  # outer-to-inner inset
Corner radius: 6            # inner radius is this value minus Padding
Space: 10                   # gap to adjacent list content

### Checked outer
Background color: #5B4FC4
### Checked inner
Background color: #FFFFFF
### Unchecked outer
Background color: #E9E7F2
### Unchecked inner
Background color: #FFFFFF
```

For `Type: switch`, `Size` is the height (minimum/default 40) and width is
twice that value. Its inner shape moves left when unchecked and right when
checked. Checkbox width and height both equal `Size`. An omitted corner radius
defaults to 6 for a checkbox and half the height for a switch; explicit `0`
means square. Each state/layer block accepts the background-card paint keys:
background color(s), image or gradient, stroke color(s)/width, `Outer shadow` /
`Inner shadow` (*Shadows*, §3), rotation, and background-aware color
replacement. The four layers take them independently, so a lifted knob over a
pressed-in track is two declarations; the outer layer is the background the
inner one resolves against. `Corner radius` on `### Checked outer` or
`### Unchecked outer` overrides the family radius for that state; its inner
radius remains the resolved outer radius minus `Padding`. `Enabled: no` draws the original bracket
token as text. Parenthesized radio controls and click handling are not included.

`### Checked inner` and `### Unchecked inner` also take `Symbol:`, an emoji or
symbol character drawn centred in that state's inner shape (on a switch, the
knob), and an optional `Symbol color:`. Without `Symbol` nothing is drawn. The
glyph is 70% of the inner shape's height (smaller if that is too wide), in the
`## Emoji styles` `Font:` when the theme names one (an icon font draws its
icon). With no `Symbol color` it
takes the same state's outer fill, so a white box on a purple control gets a
purple mark; either colour then goes through *Color Replacements* against the
inner background, like text. A colour emoji keeps its own colours.

```md
### Checked inner
Background color: #FFFFFF
Symbol: ✓
### Unchecked inner
Symbol: ✕
Symbol color: #B3261E
```

**Sliders.** Exact `[0%]` through `[100%]` tokens are interactive sliders. Put a
label before the token (`Volume: [65%]`) so events carry a useful server-owned
name. A linked slider uses `[[65%]](agent:set-volume?channel=music)`; the nested
brackets deliberately distinguish it from the ordinary Markdown link
`[65%](/details)`. Escaped tokens, code spans, ordinary percentage links and
out-of-range values stay literal. A drag paints optimistically and sends one
wire event on release.

```md
## Drawing elements

### Sliders
Enabled: yes
Style: thick               # thick | line
Axis: horizontal           # horizontal | vertical
Length: 240
Thickness: 85              # omitted: thick 85, line 10
Corner radius: 42.5        # omitted: half the resolved thickness
Circle diameter: 28        # line-style handle
Drag bar length: 22        # thick-style handle
Bar thickness: 3           # thick-style handle's short dimension
Drag bar gap: 5            # thick-style handle sits this far inside the fill

### Slider Track
Background color: #F8C91C

### Slider Bar
Background color: #FFFFFF

### Slider Handle
Background color: #D8D8D8
```

`Style: thick` draws a short perpendicular drag bar inside the broad track;
`Style: line` draws the configured circle over a thin track. `Axis` and `Style`
apply to all sliders in the document. Vertical values grow bottom-to-top.
`Length`, `Thickness`, `Corner radius`, `Circle diameter`, `Drag bar length`,
`Bar thickness` and `Drag bar gap` are pixels. `Bar thickness` is also accepted
as the explicit alias `Drag bar thickness`. `Drag bar gap` (default 5) is how far
inside the filled bar the drag bar sits from the value edge — below it on a
vertical slider, left of it on a horizontal one; a fill too short for the gap
and the bar keeps the bar at the track's start. The `line` circle stays centred
on the value edge.

The Track, Bar (filled portion), and Handle blocks independently accept the
shared background-card paint keys: color(s), image, gradient, stroke, shadows,
corner radius, rotation and background-aware color replacement. Track
and Bar share the same bounds; the Bar is clipped to the Track's rounded shape.
Sliders have no separate `Padding` or inset setting.
`Enabled: no` leaves the authored bracket token as text.

**Counts.** A ratio slider written between ➖ and ➕ (`Quantity: ➖ [2/9] ➕`) is a
count: the value's digits between two round buttons that step it by one. It is a
slider, so `### Sliders` → `Enabled` gates it too; its size follows the body text
size, never the slider's `Length` or `Thickness`.

```md
## Drawing elements

### Count Button
Background color: #FDE68A
Stroke width: 3
Stroke color: #B45309
Stroke align: inside
Outer shadow:
- Offset y: 3
- Color: #92400E
Symbol color: #78350F       # the ➖ and ➕ drawn on the button
```

`### Count Button` paints both round buttons and takes the same paint keys as
`### Slider Handle`: color(s), image, gradient, stroke, shadows, rotation and
background-aware color replacement (a corner radius does not apply to a circle).
`Symbol color` is the ink of the ➖ and ➕, resolved through *Color Replacements*
against the button's own fill, as a checkbox's `Symbol color` is.

With no `### Count Button` key, the buttons take the quieter button's paint
(`### Secondary` under `## Links`, as its pill has it), the signs its label
colour, and a button that cannot step (➖ at 0, ➕ at the maximum) that button's
disabled paint. Once the block paints anything, its paint replaces the inherited
one whole; `Symbol color` alone keeps the inherited paint and recolors the signs.
With either key, a button that cannot step is the same button at the default
mute, as a `~~` slider is. The digits are the body text in bold, 1.2 times its
size.

**What that costs, for a family that splits its leaf.** The split has already
happened by the time the toggle is read, so the pieces stay separate leaves.
`### Dates` → `Enabled: no` on a line the author separated leaves the pieces
separate — `Enabled: no` means "do not draw it", not "treat it as text".

**A drawing is earned by separating the value.** This is the per-instance lever,
and it lives in the document rather than the theme. A value is only cut out of its line
when the line is a **run** — nothing but elements and values. Any ordinary word
beside it makes the line prose, and prose keeps its values inline and undrawn:

```md
GMT +9 - Aug-12        a day chip — separated, and joined by the chip's dash
GMT +9 - Aug 12        plain text — a spaced date is how prose writes one
GMT +9 - Aug\-12       plain text — the chip's dash is escaped
This is Aug-12 here.   plain text — the sentence around it is prose
```

So a caption is declined by *not* separating it, or by escaping the separator
(`\-` `\|` `\:` `\,` `\.`: every character that divides a line can be escaped). Switching the family off is still
available, and is still document-wide; it is no longer the only answer.

`###` blocks (bar families share the same keys):

- **`### Ratio Bars`** — a bare `4/8` ratio renders as a progress bar with the
  ratio text beside it.
  - `Enabled: yes|no`, `Thickness: N`.
  - `Text side: left|right` — which side of the bar the ratio text sits on.
  - `Corner radius: N` — `0` (default) is square, consistently with every
    background fill. Use half the bar thickness for a full pill.
  - `Background color(s)` / `Background image` / `Background gradient` /
    `Stroke width|color` / `Outer shadow` / `Inner shadow` (§3) — the filled
    portion's paint.
- **`### Ratio Bar Track`** — the empty background behind the bar: the same
  background image, color, gradient, corner-radius, stroke and shadow properties;
  `Enabled: no` hides that background without hiding the filled bar.
  `Padding: N` is the inner gap between track and fill and remains effective
  when the track paint is hidden.
- **`### Key Value Bars`** / **`### Key Value Bar Track`** — a `Key: 50%` pair
  renders its key/value line plus a full-width progress bar. Same keys as Ratio Bars, plus
  `Position: above|below` — the bar relative to the key/value text — and two
  independent visibility controls:
  - `Show key: yes|no` — whether the `Key` label is drawn (default `yes`).
  - `Show value: yes|no` — whether the percentage is drawn (default `yes`).
  Set both to `no` for a bare media-scrubber style bar. These options affect
  only Key Value Bars; Unit Ratios keep their own controls below.
- **`Negative color: #hex`** (Ratio Bars, Key Value Bars) — the fill of a value
  below zero. Such a bar reads its track from the right edge and fills right to
  left, so `-40%` fills the right 40% and `-100%` the whole track. Unset, the
  fill keeps the bar's own colour. Values at or above zero draw from the left as
  before. A ring has no side to go below zero on and stays empty.
- **`### Unit Ratios`** — ratio-plus-unit datapoints (`750/1800 Kcal`,
  `75/100g`, `25/100 progress`, `Minutes: 7/8` where the key is the unit,
  `Disk (GB): 61/128` where the key declares it):
  - `Enabled: yes|no`.
  - `Style: bar|ring` — `bar` reuses the Ratio Bars styling; `ring` draws the
    circular progress ring below.
  - `Show total: yes|no` — whether the denominator is drawn. With `no`, only the
    value is shown.
  - `Show key: yes|no` — whether the key is drawn, for the `Minutes: 7/8` form
    where the key is the unit.
- **`### Ring`** — the circular ring (a fixed-diameter card whose background
  paint is the arc, wrapping the centered value/unit text leaves):
  `Thickness`, `Diameter`, `Spacing` (gap between the value and unit,
  default 0), `Background color` (the value arc), and
  `- Font name/size/weight/color` bullets for the value text (which scales
  down to fit the ring). Background image/gradient/stroke/shadow fields are
  parsed through the shared style but are not painted on this stroked arc.
- **`### Ring Unit`** — font bullets for the unit text under the value.
- **`### Ring Track`** — the full-circle background arc; currently only its
  `Background color` is painted.
- **`### Dates`** — `Mon-15` / `Jun-15` render as a day chip: a card
  background wrapping two stacked text leaves (weekday/month over the day
  number). `Enabled`; `Fill: single|split` (`single` = one chip fill;
  `split` = the chip is divided into two regions filled by the Date Key /
  Date Day backgrounds, sharing the outer rounded corners); `Spacing: N` =
  the gap between the weekday/month leaf and the day-number leaf (default 0);
  plus `Background color`, `Background gradient`, corner radius, stroke,
  shadows, and `Padding` for the outer chip card. `Background image` parses but
  is not painted.
- **`### Date Key`** — the weekday/month name (uppercased): font bullets. Its
  `Background color` is the TOP region fill when `Fill: split`; other parsed
  background paint fields are not painted on the split region.
- **`### Date Day`** — the day-of-month number: font bullets. Its
  `Background color` is the BOTTOM region fill when `Fill: split`; other parsed
  background paint fields are not painted on the split region.
```md
## Drawing elements

### Ratio Bars
Enabled: yes
Thickness: 10
Text side: right
Background color: #5B4FC4

### Ratio Bar Track
Background color: #E9E7F2
Padding: 0

### Unit Ratios
Enabled: yes
Style: ring

### Ring
Thickness: 12
Diameter: 110
Background color: #5B4FC4
- Font size: 24
- Font weight: bold
```

### `## Charts`
Bar charts drawn in place of bullet runs of `Key: value` rows in one unit
(three or more single-value rows, or two or more multi-value rows under a
`Name, Name:` header — the header names the series). A value is a number: a
percentage, a currency (`$220.06`, `200 EUR`) or a magnitude (`5K`) as written,
or a bare number whose unit is declared on the line above (`Storage (GB):`);
any other unit written in a row keeps it out of the chart (ADR-204). Each value is drawn as written. The renderer picks the orientation
from row count and available width: few rows → horizontal bars; many rows
with room → vertical bars with labels beneath; narrow → the horizontal rows
stack into columns.

Choose the data representation before styling the chart:

| Input or requirement | Authoring contract |
|---|---|
| Single series | Three or more `- Key: value` rows in one unit |
| Multiple series | A `Name, Name:` header and two or more multi-value rows |
| A row with words beside its value | Stays a list item, out of the chart: a row is the value alone |
| Literal value row | Escape the unit, for example `- Jan: 75\%` or `- Jan: \$75`; it renders as a labelled text value |
| Orientation | Selected from row count and available width |
| Label/value typography | `### Chart Labels` and `### Chart Values` |

A percentage chart reads as progress against 100%; any other unit is compared
against its largest row. `Charts` → `Enabled: no` renders percentage rows as
individual bars and other rows as key–value items; value escapes render them as
text. `md2ui check` notes a row left out of the chart beside it and a run whose
units differ.

Top-level keys (no `###` needed):

- `Enabled: yes|no` — chart drawing on/off (rows fall back to their
  individual Key Value Bars when off).
- `Mode: bar|line` — parsed, with no effect: a line is written as an arrow
  chain (see *Line charts* below).
- `Percent scale: 100|peak` — `100` (default): a percentage chart reads as
  progress against 100%. `peak`: it compares its rows against the largest, so
  `1.2%`, `2.4%`, `3.1%` fill the chart instead of drawing as slivers.
- `Value format: 1|1 unit|1unit|unit 1` — where a **declared** unit shows. A
  value in no chart unit is written bare and its unit declared once by the data:
  a short line ending in `(unit)` right above the run (`Temperature (°C):`, or
  `High, Low (°C):` for two series), or a line's key (`High (°C): 24 → 23 → 21`).
  `1` (default) leaves values bare, the unit shown only where it was written;
  `1unit` draws `24°C`, `1 unit` draws `24 °C`, `unit 1` draws `$ 24` — on row
  values, tick labels and a line's last value. A series legend ends with the
  unit. Values written in their own unit (`$220.06`) are drawn as written.
- `Bar thickness: N`, `Bar width: fixed|fill`, `Bar spacing: N` — bar size and
  spacing; see *Bar size and spacing* below.
- `Corner radius` / `Background color` / `Background image` /
  `Background gradient` / `Stroke width|color` / `Outer shadow` /
  `Inner shadow` (§3) — each bar's paint (single-series / first series).
  `Corner radius: 0` is square.
- `Negative color: #hex` — the fill of a bar below zero. Unset, it keeps its
  series colour.

**Values below zero.** A chart whose rows are all zero or above scales against
100% (or its peak above that), so a bar reads as progress. One value below zero
makes it change data, and every bar runs from zero — up or right for a gain,
down or left for a loss:

- **Vertical bars** scale from the lowest value to the highest, zero always
  included, so zero sits where the data puts it.
- **Horizontal rows** (and their side-by-side columns): when every value is
  below zero, zero is the track's right edge and the bars run right to left.
  When gains and losses mix, zero is the middle of the track and the scale
  reaches the largest value either way.

A zero line is drawn wherever zero falls inside the bars, in the `### Chart
Grid` line style.

**Line charts.** A `Key: value` whose whole value is three or more values
joined by `→` (`Price: $710.14 → $713.94 → $777.24`) draws as a line once the
theme declares the block below. The values take what a bar chart's do, in one
unit (`$`, `%`, `5K`), or are bare numbers whose unit the key declares
(`Users (count): 900 → 1.2K → 5K`). The key and the last
value as written share a row above the line, at every width. The line's axis
fits the data's range rather than starting at zero. A `(label)` right after a
value — words, a date, a time, `(Q1)`, `(FY2025)` — labels that point under the
line and gives it a dot, as the last point always has. A parenthesis holding a
second value (`(49%)`, `(1.2K)`), mixed units, an ellipsis, a chain of words or
`->` in place of `→` keeps the text as written.

```md
### Line Chart
Height: 56          # the line's area; tick labels go below it
Line width: 2
Line color: #00CC58 # unset: the first series colour
Point size: 6       # dot diameter; 0 draws none
Points: labelled    # dots on labelled points and the last; `last`: the last only
Group height: 112   # several lines on one axis; unset: Height
```

A line draws with no `### Line Chart` block at all, as every display does, in md2ui's
own defaults: height 48, line width 2, the first series colour, 6 px points on the
labelled points. The block restyles it; `Enabled: no` turns it off. Tick labels use
`### Chart Labels`.

**The area under a line** takes the section background keys inside
`### Line Chart`: `Background color` (one colour, or a bullet list whose colours
the lines of a group take in turn), `Background gradient`, `Background image`,
`Outer shadow` and `Inner shadow`. They paint the shape between the line and the
bottom of its area, as they paint a card, and follow `## Color Replacements` on
the `fill` channel. The gradient and image span the whole area, so a vertical
gradient fades every line's shape toward the axis alike. Without them, no area
is drawn.

```md
### Line Chart
Background color: #00A84A33
Background gradient:
- Colors:
  - #FFFFFF00
  - #FFFFFFCC
```

**Several lines on one axis.** Two or more `- Key: a → b → c` list items with
the same number of points, in one unit, draw as one chart: the lines share the
axis, in an area `Group height` tall (`Height` when unset), so lines at
different levels can keep their own movement visible. A `(unit)` line right
above the list declares the unit of bare numbers, as for a bar chart, or each
key declares its own. Each line takes the next chart series colour (`Line
color` colours a single line only), and a legend above the lines shows each line's dot, name and last
value as written — with the declared unit as `Value format` places it — in the
`### Chart Labels` style, wrapping between entries when they do not fit the
width. A label written on any line names that position for all of them. A run
with a line of a different length, or two labels for one position, stays
separate lines, and `check` notes why.

**Bar size and spacing.** What the three keys mean depends on the orientation
the renderer picked. Vertical bars need **five or more rows** and room for them;
four rows or fewer are horizontal at every width, so `Bar width` changes nothing
there.

| key | horizontal rows | vertical, `Bar width: fixed` (default) | vertical, `Bar width: fill` |
|---|---|---|---|
| `Bar thickness` | the bar's height, and the shortest a bar gets | the bar's width, and the shortest a bar gets (its top stays round) | the **minimum** width and the minimum height |
| `Bar spacing` | not used | not used | the gap between one row's bars and the next |

```
Bar width: fixed                         Bar width: fill
┌─────────────────────────────┐          ┌─────────────────────────────┐
│               ┌┐            │          │           ┌───────┐         │
│     ┌┐        ││            │          │ ┌───────┐ │       │         │
│     ││        ││       ┌┐   │          │ │       │ │       │ ┌─────┐ │
│     ││        ││       ││   │          │ │       │ │       │ │     │ │
└─────────────────────────────┘          └─────────────────────────────┘
  thin bars, centred in each slot           bars share the width,
                                            `Bar spacing` apart
```

A `fixed` bar is drawn at `Bar thickness` unless its slot is too small, when it
narrows (a row's bars take at most 70% of the slot, never under 3 px). A `fill`
bar never goes under `Bar thickness`: a chart too narrow for every bar at that
width plus the spacing turns on its side instead of squeezing them. The same
floor keeps a low value a low bar rather than a square as tall as it is wide.

In a multi-series chart the bars of one row sit 2 px apart and share that row's
width, and `Bar spacing` separates the rows.

`###` blocks:

- **`### Chart Track`** — the track behind each **horizontal** bar (vertical
  bars have none, in either `Bar width` mode); it accepts the
  same background image, color, gradient, corner-radius, stroke and shadow
  properties.
  `Enabled: no` hides the track, while `Padding: N` controls the inner gap
  between its bounds and the bar. Padding participates in chart measurement.
- **`### Chart Series Colors`** — bullet list of colors cycled across series
  in multi-series charts.
- **`### Chart Labels`** — font bullets for row labels and the series legend.
- **`### Chart Values`** — font bullets for value annotations on bars.
- **`### Chart Grid`** — a **vertical** chart's scale and lines, all off by
  default (horizontal rows already print each value, and draw none of it):
  - `Axis labels: yes` — tick labels (`0%`, `25%` …) in a gutter left of the
    bars; the gutter counts toward the width a chart needs to stay vertical.
  - `Ticks: N` (default 4) — about how many steps the scale is cut into. Ticks
    land on round values (1, 2, 2.5 or 5 × 10ⁿ apart), so the scale may reach
    past the data to the next one, and 0 is always a tick.
  - `Horizontal lines: yes` — a line at each tick. `Vertical lines: yes` — a
    line at each edge of every row's slot.
  - `Line color: #hex` (default `#D0D0D0`), `Line width: N` (default 1),
    `Line dash: on off` (e.g. `4 3`; solid when unset).
  - Font bullets style the tick labels (falling back to `### Chart Values`).

  The zero line of a chart holding a negative is drawn in the same colour and
  width whether the grid is on or not, and is never dashed.

```md
### Chart Grid
Axis labels: yes
Horizontal lines: yes
Line color: #E4E4E8
Line dash: 4 3
- Font size: 11
```

```md
## Charts
Enabled: yes
Bar thickness: 14
Corner radius: 7
Background color: #5B4FC4

### Chart Track
Background color: #F1F0FA

### Chart Series Colors
- #5B4FC4
- #E8B93E
```

Vertical bars that fill their card, as in `data/markdown/tests-render/home-dashboards/bento-cards`
(five rows, `Mon: 90%` … `Fri: 10%`):

```md
## Charts
Bar width: fill
Bar thickness: 22
Bar spacing: 10
Corner radius: 8
Background color: #FF4A1C
```

### `## Fonts`
Bullet list of font files to load (so custom `Font Name`s resolve):
```md
## Fonts
- assets/fonts/WorkSans-Regular.ttf
- assets/fonts/WorkSans-Bold.ttf
```

**Where a relative path points.** Every file a theme names — these entries, an emoji
`Font:`, and any `Background image:` — resolves **beside the THEME.md first**. So a theme
can live in its own folder with its assets:

```
my-theme/
  THEME.md            ## Fonts → - fonts/WorkSans-Regular.ttf
  fonts/WorkSans-Regular.ttf
```

When no such file is beside the THEME.md, the path resolves against the working directory
instead. A font that md2ui's lock (`assets/fonts.lock`) names is also found by its file name:
an installed md2ui fetches it into its per-user cache on first use (README, *Files md2ui reads
at run time*), and in a checkout `make assets` fetches every locked font (CONTRIBUTING.md,
*Adding a font*, says how to lock a new one).
Absolute paths and `http(s)` URLs are used as written.

---

## 6. Color rotation

Most designs keep one consistent color per kind of element. Some deal a
different one to each — four service cards in four hues, six feature icons in
six. Rotation is how a theme says the second thing.

### Listing more than one color IS the switch

Every color key takes either one inline value or a bullet list. There is no
separate key and nothing to enable:

```md
Fill color: #8778f5          one consistent color — the traditional look

Fill color:                  a CYCLE
- #6FDCA6
- #101010
- #C9A7F5
```

A one-entry list is not a cycle, so **every theme written before rotation
existed renders identically**. That is the whole compatibility story.

### Which color an element gets

Elements take the next color in document order, and **a cycle restarts inside
every heading section**. Three `### ` cards under one `## ` cycle 0,1,2, and the
emojis under the *next* `## ` start again at 0 rather than continuing at 3
— which is what lets two unrelated runs in one document each begin at their first
color.

Kinds count separately — cards, buttons, chips, emojis and heading text
each run their own cycle — with one deliberate exception: **a heading section
lends its slot to its own title**, so a rotated `### Heading 3` background and a
rotated `Heading3` font color land on the same hue without being linked.

An emoji's fill and its `Icon color` read the *same* slot, so a tinted
background stays paired with its matching saturated glyph.

### What a cycle cannot express, and where to go instead

A cycle deals colors by **position**; a pin under `## Fixed colors` matches by **label**; a
replacement matches by **color**. None of the three can name a particular node, and that is
deliberate — a theme describes kinds, not instances, which is what lets one theme serve a
document it has never seen.

The consequence is worth stating plainly, because it is reached from several directions:

| you want | a theme can | so author it in the markdown |
|---|---|---|
| this token a different color from an identical one elsewhere | no — a pin on `5` hits every `5` in the document | a chip variant: `` `5` `` / `` *`5`* `` / `` **`5`** `` / `` ***`5`*** `` |
| this line bigger than its neighbours | no — `Text` is per role | a display tier: `_x_` / `__x__` / `___x___` |
| this row's value against the right edge | no — `Horizontal align` is per level | a spring: `Subtotal ... $42.50` |
| this line not to split | no — separators are global | an escape: `Shibuya\, Tokyo` |

A page with two month calendars is the case that makes it concrete: pinning "day 5 is
active" colors the 5 in **both** grids, because the pin sees a label and not a table. Moving
the state into the cell as a wrapper fixes it and needs no theme change at all.

So when a theme rule keeps reaching further than intended, the question is not which key is
missing — it is whether the distinction belongs in the document instead.

### Turning a cycle off — `Rotate <kind> colors`

Written on a heading level, under `## Styling & Spacing`:

```md
### Heading 2
Rotate link colors: no
Rotate chip colors: yes
```

Kinds: `background` (that level's own section fill/stroke), `card`, `emoji`,
`link`, `chip`, `heading`, `placeholder` (a named image placeholder's fill and text). The key is read leniently — `Rotate links color` and
`Rotate buttons colors` reach the same switch. Unstated means on, and the
innermost level that states one wins, so a `no` high up is overridden by a `yes`
further in. Turning a kind off pins it to the first color of its list.
`Rotate colors: yes|no` is the blanket form.

### Sharing a card's color — `Rotate colors: sync`

A cycle is scoped to its section, so an element inside a card counts among its
own siblings. The chips of one card are "the first chip, the second chip" — none
of them can say **"the third card"**, so no list can give each card its own chip
color. `sync` hands a level's slot down to everything inside it:

```md
### Heading 2
Background color:
- #DCEBFA
- #E5DCFA
- #FBDCC4
- #C8EEDC
Rotate colors: sync          <- everything inside takes THIS section's slot

## Inline Code
Fill color:                  <- one entry per CARD, not per chip
- #B9DDF5
- #D2C4F5
- #F8CBA6
- #A8E3C6
```

Every chip in the third card now paints the third fill. Two things make the
blanket key safe rather than blunt:

- **A one-color list ignores the slot**, so sharing it with single-color buttons,
  emoji or heading text changes nothing — there is nothing to opt out of.
- **A section never syncs to itself.** The cards keep the slots their own cycle
  dealt them; only their contents borrow.

Write it on the level whose slot is being shared — the level is named by where
you put it.

### What outranks a cycle

A `## Fixed colors` pin wins over the slot a cycle would deal — see §5. Rotation
chooses; a pin means.

### What does not rotate

The display tiers (`Muted` / `Lead` / `Display`) take a single
color. They do not need a cycle: `## Color Replacements` is keyed on the color
itself, so one rule per card background recolors every `Display` value sitting on
that background. Rotation deals colors out; replacement fixes the ones that land
badly — and between them the tiers are covered.

---

## 7. Image annotations — `?md2ui.*`

Everything above is a theme: it styles a whole document. Some image decisions
are not a theme's to make and not a model's to guess — this photo must not be
crop to 16:9, this avatar is a circle, this cover goes beside its text rather
than above it. Those are properties of the *image*, so they are written on the
image, as ordinary URL query parameters:

```md
![Alex Foster](https://images.example.com/portrait.jpg?q=80&md2ui.shape=circle&md2ui.max_width=250)
```

Parsed by `split_md2ui_params` in `src/md2ui/utils/image_params.py`.

### Properties

| Property | Values | Effect |
|----------|--------|--------|
| `md2ui.aspect_ratio` | `W:H` (e.g. `4:3`, `2.35:1`), optionally followed by `,W:H@px` ranges (`3:4,1:1@600,16:9@960`) | The box the image is cover-cropped into. Each range applies from that image width up. |
| `md2ui.max_width` | integer px | Caps the image leaf's box and drawn width; adjacent content uses the released space. |
| `md2ui.min_width` | integer px | A floor: in a `:::` row the image's cell is never given less, and a row that cannot give it stacks. `max_width` wins when it is smaller. |
| `md2ui.shape` | `circle` | Forces a 1:1 box clipped to a circle. **Outranks `aspect_ratio`.** |
| `md2ui.fit` | `contain` \| `cover` | How the image scales into its box — see below. |
| `md2ui.corner_radius` | integer px | Rounds this image. `0` is an explicit square. |
| `md2ui.bleed` | `yes` \| `no` | Whether this image runs over its level's padding. |
| `md2ui.content_align` | `left` \| `center` \| `right` | Horizontal placement of a capped image in its box. Also settable from the markdown itself — see below. |

The params say how an image is drawn, never where it goes: a picture beside text
is a `:::` row. The aside params (`arrangement`, `aside_ratio`, `content_valign`)
are not params and are reported as unknown names.

In a space 768px or wider, an image with an `aspect_ratio` is never drawn taller
than a 16:9 image filling that space: its width is capped and its ratio kept. A
`max_width` replaces that limit, and a `min_width` above it is kept.

**Every property also takes a `_wide` twin**, which replaces the base value where
the **space the image is laid out in** is **768px or wider** (`WIDE_BREAKPOINT`) —
the space, never the window: on a large screen an image in a small card keeps its
base value, the same rule the `:::` divider conditions follow. There are no
window breakpoints. `_wide=default` reverts to no opinion instead of overriding.
(A picture beside text only in wide space is a `::: 1 >` divider, not a twin.)

```md
![Cover](cover.jpg?md2ui.aspect_ratio=4:3&md2ui.aspect_ratio_wide=3:4)
```

### Precedence

```
markdown `...` spring  >  URL param  >  THEME.md level Align
                       >  Root Align  >  left
```

`Horizontal align` on a level (see §3) sits below everything authored per node and above the
Root default, so a centred section still lets a `...` spring push its own line to
the edges.

The ` ... ` **spring** in the markdown source is the only channel above the URL
params, and it sets exactly one field: `content_align`, whose whole vocabulary is
`left` / `center` / `right`. It is the document stating where a piece of one line
goes — `Subtotal ... $42.50` puts the subtotal left and the price right — so it
wins over anything inferred. See
[`skills/structure.md`](skills/structure.md) for the syntax.

Three values is also the ceiling: two springs reach all of them, and further
springs separate the middle without placing it (`A ... B ... C ... D` is left /
B and C centred together / right, not four evenly spaced items). A spring sends
the slack to an edge; there is no space-between.

Unlike every other channel it is **per node, never polled across a run** (see
below). The kind-hash tolerance already lets one member of a repeated run carry
a piece its siblings do not — a button, a chip label — and that piece is exactly
the one an author wants placed differently, so a spring on one row aligns that
row and leaves its siblings alone.

Per **field**: `?md2ui.shape=circle` alone still lets the model predict
`max_width`. A capped image's layout box hugs that width and its aspect-ratio
height, so a taller row keeps it at the top instead of vertically centering it
inside an empty allocation. `content_align` positions that compact box when its
parent still owns horizontal slack. A param is real input, not a hint.

**Repeated runs stay uniform.** Six identical cards are one run, and a run gets
one decision so the design stays consistent. Params do not break that: they vote
at the top of the run's poll, so **annotating one card annotates the whole
run**. If members
of one run carry conflicting params the majority wins for all of them, and the
conflict is reported.

### Scaling: `contain` vs `cover`

`cover` fills the box and crops whatever overflows. `contain` fits the whole
image inside the box, letterboxing the leftover. Same meanings as CSS
`object-fit`.

**The default depends on the kind of image**, which is usually what you want:

| | default | why |
|---|---|---|
| photograph (PNG/JPG/WebP) | `cover` | a photo is a texture — filling the frame is the intent |
| vector (SVG) | `contain` | a drawing has meaningful bounds; cropping a logo mangles it |

Set `md2ui.fit` only to override that — a photograph that must not be cropped,
or a vector meant to bleed to the edges:

```md
![Team photo](team.jpg?md2ui.fit=contain)
![Background texture](pattern.svg?md2ui.fit=cover)
```

It takes a `_wide` twin like every other property, so an image can crop on
narrow and show whole on wide: `?md2ui.fit=cover&md2ui.fit_wide=contain`.

### `corner_radius` and `bleed` — the per-image twins of two theme keys

`Image corner radius` and `Image bleed` are declared **per level** in
`THEME.md` (§3). These two params say the same things about **one image**, and
the image wins either way:

```md
![hero](hero.jpg?md2ui.bleed=yes)          fills its card, theme untouched
![avatar](me.jpg?md2ui.corner_radius=0)    stays square in a rounded level
![logo](logo.svg?md2ui.bleed=no)           excused from a level that bleeds
```

* **Unset** falls back to the level. Only a stated value overrides it, so
  `bleed=no` genuinely escapes a level that said `Image bleed: yes`.
* **`bleed` works on its own** — no THEME.md change needed. It uses the
  innermost *enclosing* layer that has padding, so a bleed only ever eats the
  padding of a box the image is sitting in; it can never reach a sibling card or
  a level the image is not inside.
* **`corner_radius` also works on its own**, since it eats no padding and moves
  nothing.
* While bleeding, the **level's** `Corner radius` clips the image on the corners
  the two now share, and `md2ui.corner_radius` is ignored — the parent's shape
  wins, exactly as with the level key.
* A `max_width`-capped image never bleeds, even with `bleed=yes`: it paints a
  small rect inside a big box, so bleeding would only push it into the corner.

Each takes the usual `_wide` twin.

### Defaults when nothing is set

With no annotation, an image fills its column at a
width-conditioned ratio: **3:2** below 768px, **16:9** from 768px, **2.35:1**
from 1024px — `3:2,16:9@768,2.35:1@1024` in the range syntax. Those are photo defaults, so a square SVG icon gets a 3:2 box and is
letterboxed inside it — `md2ui.aspect_ratio=1:1` fixes that per image.
`## Images` in `THEME.md` holds only placeholders (below), so there is no
theme-level image default to sit between these and a URL param yet.

### Named placeholders — `md2ui.placeholder`

An image with no picture to show (its source left out, `![Sara Zane](?md2ui.placeholder=avatar:SZ)`,
still loading, or failed) can paint a placeholder the theme declares by name instead of the
default ones. It is opt-in per image: an image that names none, or names one the theme does
not declare, paints exactly as before (the loading, broken or quiet box). Once a URL's picture
loads, the picture wins.

```md
![Sara Zane](?md2ui.placeholder=avatar:SZ&md2ui.shape=circle)        initials
![Guest](?md2ui.placeholder=avatar:👤&md2ui.shape=circle)            one emoji
![Product photo](?md2ui.placeholder=media)                           the placeholder's own look
![Sara Zane](https://cdn.example.com/u/42.jpg?md2ui.placeholder=avatar:SZ)
```

The value is `<name>` or `<name>:<text>`: the name picks the placeholder, the text (initials,
up to three characters, or one emoji) is what this image shows in it. No spaces. The
placeholder paints in the picture's own box and clip, so `shape`, `corner_radius`, the ratio
and bleed shape it as they shape a photo, and the layout never moves.

The theme declares each placeholder under `## Images` → `### Placeholders`, one `#### Name`
block each; the image writes the name lower-cased, spaces and punctuation as `-`
(`#### Avatar Style` → `avatar-style`):

```md
## Images

### Placeholders

#### Avatar
Fill color:
- #E8F0FE
- #FDE7E9
Text color:
- #1A56DB
- #C81E1E
Text style: Lead
Text size: 40%

#### Media
Fill color: #F2F2F2
Text color: #8A8A8A
Icon: 🖼️
Icon size: 30%
```

| Key | Value | Default |
|---|---|---|
| `Fill color` | one colour, or a list of `- #hex` bullets | the quiet box's grey |
| `Text color` | one colour, or a list | the text style's colour |
| `Text style` | a text style this theme declares: `Text`, `Muted`, `Lead`, `Display`, `Key`, `Value`, `Heading 1`…`Heading 6` | `Text` |
| `Text size` | a share of the box's shorter side (`40%`) or px (`28`) | `40%` |
| `Icon` | one emoji, drawn when the image gives no text | none: the fill alone |
| `Icon size` | as `Text size` | `50%` |
| `Image` | a local path (beside the THEME.md first, as `Background image`) or an http(s) URL, cover-fitted over the fill and under the text or icon | none |

**Three names restyle md2ui's own placeholders:** `#### Loading`, `#### Broken` and
`#### Missing` (the source left out, `![alt]()`), anywhere among the others under
`### Placeholders`, take the same keys and are drawn for every image in that state that names
no placeholder (or one the theme does not declare). An image cannot name them. A state with
no block keeps md2ui's own look; a named placeholder always outranks a default. Defaults need
no MEANINGS.md row: agents never write them. Placeholders, named or default, stand in for a
Markdown image only: a failed theme `Background image` and an image card's photo keep md2ui's
own placeholders (§3 *Backgrounds*).

```md
### Placeholders

#### Missing
Fill color: #FFF4E5
Icon: 🖼️

#### Broken
Image: assets/broken.svg
```

A colour list rotates as every colour list does (§6 *Color rotation*): each placeholder
name counts its own cycle per section, as chips do, so four avatars in four list rows take
four colours, and a new heading section starts again unless its level says
`Rotate colors: sync`. `Rotate placeholder colors: no` (or the blanket `Rotate colors: no`)
on an enclosing level pins its fill and text to their first colours.

**Agents see a placeholder only through `MEANINGS.md`.** Give each one a row whose spelling
names it, saying what it is for (`` `?md2ui.placeholder=avatar:SZ` `` — a person or account
with no photo: their initials). The theme lint reports a placeholder with no row, a row with
no placeholder, placeholders in a theme with no `MEANINGS.md`, and any `###` block under
`## Images` other than `### Placeholders` (the parser reads nothing in it); `check` warns when an
image names a placeholder no row declares, and notes text longer than three characters.
The rows reach agents in the core note itself, as a closing section *An item with no picture*
after the table of spellings by place (§10): a placeholder is chosen while the answer is
written, and rows behind `guide("theme")` are not read.

### Safety and syntax rules

- **Params never reach the network.** They are stripped before the image is
  fetched, and the disk-cache key is the clean URL — so annotating an
  already-cached photo is a cache hit, not a re-download, and two differently
  annotated references to one photo share a single download and decode.
- **Your own query is untouched.** Removal is textual, not a re-encode, so a
  signed CDN URL (`X-Amz-Signature=…`) survives byte-for-byte.
- **Use `&` when the URL already has a query** — most CDN URLs do. A second `?`
  is accepted too, so a pasted `?md2ui.shape=circle` still works.
- **No spaces in a value.** A space changes the leaf's word count and can shift
  its length category; whitespace-bearing values are dropped.
- `data:` URIs and `#fragments` are never parsed, so an inline SVG payload and
  an SVG sprite id (`icons.svg#star`) are both safe.
- A misspelled name or an out-of-range value is **dropped and reported**, never
  guessed — `md2ui.shappe=circle` warns rather than silently doing nothing.

### When a param does not apply

A misspelled or retired name and an out-of-range value are dropped and
reported, never guessed. Params are echoed on load (`[url] N md2ui param
entries`) and their diagnostics appear in the terminal. Conflicting params
inside one repeated run resolve by majority, applied to every member, with a
warning.

---

## 8. Reserved / not yet implemented

`## Images` is parsed for `### Placeholders` only (§7, *Named placeholders*); any other
block under it is ignored.

Not yet supported as image annotations either (§7): `md2ui.border_radius`, and
percentage values such as `max_width=50%`.

---

## 9. Minimal example

```md
# My Theme

## Styling & Spacing

### Root
Background color: #FFFFFF
Padding: 32
Spacing: 0

### Elements
Row Spacing: 8
Col Spacing: 4
Group spacing: 16
Padding: 0

### Heading 1
Padding: 0
Spacing: 32

### Heading 2
Background colors:
- #808080
Corner radius: 16
Padding: 16
Spacing: 16

## Text Styles
Text
- Font Name: Arial
- Font size: 16
- Font color: #000000

## Fonts
- assets/fonts/WorkSans-Regular.ttf
```

---

For a complete, live reference, see the repo's `THEME.md`.

## 10. Your project's meanings — `MEANINGS.md`

`THEME.md` says how things look; `MEANINGS.md`, beside it, says what each spelling is **for**, so
an agent writing for your project knows which one to use. Agents read it through
`guide("theme")` and the core note; nothing in it is drawn. Like `THEME.md`, it belongs to one
project: a banking app and a shopping app each write their own (ADR-501).

### Which meanings a project gets

| your theme folder has | your agents are served |
|---|---|
| a `MEANINGS.md` | that file alone: it is your whole contract |
| a `MEANINGS.md` whose first line is `Extends: defaults` | md2ui's default meanings, changed by your rows: the same spelling replaces a default row, a new one adds a meaning, and a meaning of `—` removes one |
| no `MEANINGS.md` | no meanings: agents write bare spellings, which every theme draws |

The root `MEANINGS.md` is the default theme's own. A project uses it only by choosing
`Extends: defaults`.

### The format

One table per element, the spelling first, under the fixed headings `## Icons`, `## Chips`,
`## Buttons`, `## Icon buttons`, `## Fixed colours` and `## Placeholders` (the named image
placeholders, §7; served at the end of the core note). For example:

```md
## Buttons

| Write | Means | Size | Slot |
|---|---|---|---|
| `[Label](/x)` | the main action, at the foot of a flow, a section or a dialog | | foot-main |
| `**[Label](/x)**` | the main action inside a card: the one the card is for | medium | card-main |
| `_[Label](/x)_` | the main action at the edge of a row in a list | small | row-main |
| `` [`Label`](/x) `` | a way in that repeats on every card; a link to another place | | card-way-in, nav |
```

- **Write** is the exact spelling. A row's spelling is what agents may write; anything you do not
  list, they write bare.
- **Means** is what it is for and where it goes, in words an agent acts on. Never a colour, a size
  or a measurement: the theme draws those.
- **Size** (optional) is for the lint, which compares it with what your theme draws. Agents never
  see it.
- **Slot** (optional) names the place a row serves, from a closed list. Agents never see it. md2ui
  reads it, never the words of *Means*, so you can word *Means* freely.

### Give your button and icon rows slots

Four things md2ui serves read the slots: the table of spellings by place at the end of the core
note, the advice `show` and `check` give about card actions and ways in, the check of
undeclared text buttons, and the shared patterns' examples, which `guide("patterns/<name>")`
serves in your spelling for each place (bare where you declare none). A row with no slot is
still served to agents; these simply cannot use it.

| slot | the place |
|---|---|
| `foot-main`, `foot-quieter` | the foot of a flow, a section or a dialog |
| `card-main`, `card-quieter` | inside a card: the action the card is for, and a quieter one |
| `card-way-in` | a way in that repeats on every card |
| `row-main`, `row-quieter` | the edge of a row in a list |
| `title-edge` | the edge of a section's title |
| `nav` | a link to another place: a site map, a footer, a list of links |
| `minor` | a minor action |
| `compact` | inside a compact element |
| `inline` | inside a sentence, as text |
| `icon-label`, `icon-subject`, `icon-dense` | an icon in a label or leading a row; the one a feature, an empty state or a headline is about; one in a dense row |

A row may name several slots, comma-separated. Icon buttons take the same slots as buttons.

### What the theme lint tells you

`md2ui check --theme <THEME.md>`, and the server's log at start, report:
- a slot that is not in the list above;
- `## Buttons` rows with no `card-main` or no `row-main`, the two places the core note and the
  advice need;
- a colour, a size word or a measurement in a *Means* cell;
- a *Size* that your theme does not draw that way.

### Your own patterns

Patterns in your theme folder's `patterns/` are served beside md2ui's shared ones, which stay
available to every project. A pattern may give a spelling a meaning inside its own shape with a
small `| Write | Means |` table of its own; that spelling is declared for its example, not added
to your contract.

