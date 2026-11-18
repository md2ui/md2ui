---
name: md2ui-images
description: Images, icons, logos and image-background cards in md2ui — the ?md2ui. params that matter, why an icon renders half-size, and how to put text beside a picture.
---

# Images

Image behaviour is controlled by query parameters on the URL itself, because sizing one
photo is not a theme's decision:

```md
![alt](https://example.com/icon.svg?md2ui.max_width=56&md2ui.aspect_ratio=1:1)
```

Use `&` to join them. Your own query string is preserved untouched, and the params never
reach the network.

## An icon needs TWO params, not one

**A size plus a ratio draws an icon at the size you asked.** With no `aspect_ratio`, an
image gets a *photograph* box, chosen by the picture's own width — 3:2 until the picture is
768px wide, 16:9 from 768px, 2.35:1 from 1024px. A vector fits **inside** its box rather than
cropping, so a square icon in a 3:2 box fits to the box's *height* and draws at about two
thirds of the width you asked for:

```md
![](icon.svg?md2ui.max_width=56)                        → draws ~37px
![](icon.svg?md2ui.max_width=56&md2ui.aspect_ratio=1:1) → draws 56px
```

With `1:1`, an icon of any shape draws whole inside its 56×56 box, touching it on its
limiting axis.

**Always pair a size with `aspect_ratio` for icons and logos** — `max_width`, or `max_height` for
logos that line up by height (*A logo sized by its height*).

A ratio is any `W:H` — `7:1` for a wide wordmark as readily as `1:1`. Write the artwork's own
shape when you know it; `1:1` is the right default for an icon set.

## `fit`: usually leave it alone

`md2ui.fit=contain|cover` — `contain` fits the whole image in, `cover` fills and crops.

The defaults are already right: **vector → `contain`** (a drawing has meaningful bounds),
**raster → `cover`** (a photo is a texture). So you rarely set it.

The one case where it earns its place: **a logo saved as PNG/JPG**. It is raster, so it
defaults to `cover` and gets cropped. Say so explicitly:

```md
![](logo.png?md2ui.max_width=120&md2ui.aspect_ratio=1:1&md2ui.fit=contain)
```

## A ratio for each width

A picture always fills its width, at the ratio you wrote. A `3:4` photo filling a wide page
stands taller than the screen, because that is what `3:4` means there. To change the ratio as
the picture widens, list a ratio for each width it reaches:

```md
![Shirt](shirt.jpg?md2ui.aspect_ratio=3:4,1:1@600,16:9@960)
```

That is 3:4, then 1:1 once the picture is 600px wide, then 16:9 from 960px. The width is the
picture's own, never the window's: the same image stays 3:4 in a narrow cell of a wide page.
To keep a picture small instead, give it a `max_width`.

With no ratio, a picture uses `3:2,16:9@768,2.35:1@1024`. That ladder is only the default:
a ratio you write replaces all of it, so `4:3` alone stays 4:3 at every width, and a ladder you
write is the only one that applies.

A `_wide` twin (`?md2ui.aspect_ratio_wide=3:2`) applies where the space the picture is given
is 768px or wider.

## A logo sized by its height

Logos line up by height, whatever their shape. Give each one `max_height` and its own
`aspect_ratio`; its width is the height times that ratio:

```md
![Microblog](microblog.svg?md2ui.max_height=36&md2ui.aspect_ratio=1:1)
**Microblog**
Short posts

![Shelf for Developers](lockup.svg?md2ui.max_height=36&md2ui.aspect_ratio=7:1)
**Shelf for Developers**
Docs and tools
```

The two cards are one run: they share the height and each logo keeps its own ratio, so the
square draws 36×36 and the wordmark 252×36. Where the space is narrower, a logo shrinks
keeping its shape. On one line, pictures with `max_height` stand at one height the same way.

`max_height` sizes the picture by itself, so it takes exactly one ratio — no `,W:H@px` steps —
and never sits with `max_width` or `min_width` on the same picture (or the same `_wide` twin).
A picture that breaks either rule is drawn as if `max_height` were not there, and `check`
names it.

## Several images side by side

Write them on **one line** and they stay on one line, the same way a run of buttons does:

```md
![Logo one](one.svg?md2ui.max_width=96&md2ui.aspect_ratio=1:1) ![Logo two](two.svg?md2ui.max_width=96&md2ui.aspect_ratio=1:1) ![Logo three](three.svg?md2ui.max_width=96&md2ui.aspect_ratio=1:1)
```

Write them on **separate lines** and they stack. That is the whole control — the newline is
the instruction, and nothing needs annotating:

```md
![Logo one](one.svg?md2ui.max_width=96&md2ui.aspect_ratio=1:1)
![Logo two](two.svg?md2ui.max_width=96&md2ui.aspect_ratio=1:1)
```

The row shares the width between its pictures, so a `max_width` on each is what stops three
logos becoming three giant panels. A run too long for the width wraps onto a second row
rather than shrinking, so the same line reads as a strip on a wide screen and as two rows on
a narrow one. A separator between them (` - `, ` | `) is allowed and keeps the row; the theme draws
or hides it, exactly as it does between chips or buttons. By default a run of images sits
flush.

To line logos of different heights up on their middles rather than their tops, end the line
with `@ct` (`elements.md`). **Give each one a
`max_width` or `max_height` for that to do anything** — an uncapped picture takes the row's
height and so has no room to move within it.

**Logos of one height.** Give every logo the same `max_height` and its own shape:

```md
![Microblog](microblog.svg?md2ui.max_height=36&md2ui.aspect_ratio=1:1) ![Shelf for Developers](lockup.svg?md2ui.max_height=36&md2ui.aspect_ratio=7:1) @ct
```

A `...` spring works on a row of images like it does on a row of buttons — wrap the line
in one to centre the strip, or put a single spring in the middle to push the two halves
apart:

```md
... ![Logo one](one.svg?md2ui.max_width=96&md2ui.aspect_ratio=1:1) ![Logo two](two.svg?md2ui.max_width=96&md2ui.aspect_ratio=1:1) ...
```

**An image among words sits in the line with them.** A picture cannot be drawn at text
size, so it cuts the words around it into pieces, and the pieces sit side by side like any
other run — words, picture, words:

```md
Words before the picture ![Middle](one.jpg) and words after it.
```

Words too long for one row wrap piece by piece. To put a picture above or below text, give
it its own line.

For side-by-side **blocks** rather than one line — a picture beside a heading with its own
body and a button under it — use `:::`, and close the row with a `___` or it keeps taking
what follows as further cells (`structure.md`). One line is for one line.

## A mosaic of pictures

**Use one when you have several pictures of one subject** — a hotel, a place, a product from
several sides, an event. The mosaic is that subject's gallery: it opens its page, under the
title, with the best picture largest. Several items with one picture each are not a mosaic;
they are cards (question 5).

The gallery of a place or a stay — one large picture beside four, as a booking page opens. Give
every picture the same ratio and the two cells equal weight, and the large picture and the grid
of four come out the same height. `>` puts the large picture above the four on a phone:

```md
___
![Pool](pool.jpg?md2ui.aspect_ratio=4:3)
::: 1 >
![Room](room.jpg?md2ui.aspect_ratio=4:3) ![Bar](bar.jpg?md2ui.aspect_ratio=4:3)
![Terrace](terrace.jpg?md2ui.aspect_ratio=4:3) ![Lobby](lobby.jpg?md2ui.aspect_ratio=4:3)
:::1
___
```

With three pictures, put the two others stacked in the second cell the same way.

A looser gallery is lines of pictures, each line a band across the width. Vary how many
pictures each line holds, and the shorter bands of three set off the taller bands of one:

```md
![Tacos](tacos.jpg)
![Mole](mole.jpg) ![Lobby](lobby.jpg)
![Street](street.jpg) ![Guitar](guitar.jpg) ![Tee](tee.jpg)
![Pozole](pozole.jpg)
```

Lines stay a mosaic on a phone, scaled down. A line of three gets short there, so keep the
busiest pictures out of it.

## Text beside an image

Put the picture and the text in two cells of a `:::` row (`structure.md`). Picture first
puts it on the left, picture last on the right:

```md
![](photo.jpg?md2ui.min_width=200)
::: 1 >
## Everything you crave, delivered.
Some copy.
[Find restaurants](/x)
:::2
___
```

On a wide screen the picture takes a third and the text two thirds; in narrow space the
picture sits above the text (`::: 1 >`, see *narrow and wide* in `structure.md`).

**The picture's own limits clamp its cell.** The weight proposes a width; `max_width` is a
ceiling and `min_width` a floor, and the other cells take up the difference.

- `min_width` is what keeps a picture legible. Below its floor the picture cannot stay beside
  the text, so the row stacks instead of squeezing it.
- `min_width=N&max_width=N` is a picture of exactly N pixels at every width — pair it with
  `:::0` beside a flexible text cell.
- If `min_width` is larger than `max_width`, `max_width` wins.
- When the row stacks, the picture takes the width it is given, still capped by `max_width`.

**On a single line, the picture and what follows stay a row** without any of this:

```md
![Cover](cover.jpg?md2ui.max_width=56&md2ui.aspect_ratio=1:1) - __Ease into Sleep__ : _Meditation_ - [▶️](/play)
```

gives the picture, the stacked title/subtitle, and the play button on one row.

## Image-as-background cards

Put Markdown in the alt slot and the URL becomes the card's background:

```md
![
## Payday, a day early
Get paid one business day early.
](https://example.com/photo.jpg)
```

Two things that are not obvious:

- **The section that encloses a photo card styles it** — its radius, padding and scrim — so a
  photo card inside a `## ` card board looks like the board's other cards. The photograph you
  write wins over any fallback image the theme gives that section.
- **The card's height comes from its content**, so two lines of text behind a photo give a
  letterbox. Write `+++++` at the top of the alt slot to give the picture room above the
  words (the theme's `Spacer large` under `### Image Cards` sets how much):

  ```md
  ![
  +++++
  ## Payday, a day early
  Get paid one business day early.
  ](https://example.com/photo.jpg)
  ```

## A badge over the photo

For a photo card with a title, keep the heading first when that heading should
own the whole photo surface. A leading action followed by a heading can create
a different nesting structure. This is the title-first pattern:

```md
![
#### Sunset by the bay
... [🔖](agent:save?id=walk)

Leave the studio behind for an evening walk.
*`Close to home`*
*[Plan a walk](agent:plan?id=walk)*
](photo.jpg)
```

Here the heading owns the whole photo surface. Keep attribution and license
links outside the photo-card run when reusing photographs that require credit.

A link written as the **first child** of an image card's alt slot draws on top of the picture,
and composes with a spring to reach the far edge — which is the bookmark/favourite button that
sits in the corner of so many media cards:

```md
![

... [🔖](/save)

](photo.jpg)
```

## A picture card the user opens

Wrap the whole card, picture first, in `[ … ](url)`, and the card is the target: the picture,
the title and the chips open the item together. Cards of the same shape grid like any run.

```md
[
![Evening Tide](cover.jpg?md2ui.aspect_ratio=1:1)
### **Evening Tide**
_The Harbour Lights, Coastal Nights_
`Album` `Saved`
](agent:open-album?id=31)
```

With a button of its own instead, the card keeps the picture and the button is the only target
(the `listing` pattern).

## Placing one image against the card's alignment

`?md2ui.content_align=left|center|right` places a capped image inside its box, and it is
authored per node, so it **outranks the theme's alignment for the level** the way a `...` spring does for a
row. That is what lets one logo or card image sit centred on a board whose cards are otherwise
left-aligned:

```md
![Delta](logo.svg?md2ui.max_width=120&md2ui.aspect_ratio=3:2&md2ui.fit=contain&md2ui.content_align=center)
```

It only has an effect once the image is narrower than its box, which is why it pairs with
`max_width`.

## Choosing the picture's treatment

Seven choices, each settled by its own question. **Every answer comes from the context — what
the item is, and what it is to the answer — never from what the photo happens to show.** A band
photographed in a stairwell is still an artist, and a logo standing for an account is still
someone.

**These are references, not rules.** The tables and examples below are a starting point taken
from real designs. Compose from the data you are presenting and what the answer is for: extend a
shape, change it, or combine two when the content asks for it, and never drop a choice only
because no table lists it.

**1. What is the item → `aspect_ratio`.**

| The item is | `aspect_ratio` |
|---|---|
| someone — a person, an artist, a band, an account | `1:1` |
| an album, song, playlist or podcast | `1:1` |
| clothing, a movie poster, a book cover | `3:4` |
| a car, furniture, a place, a venue, a room | `4:3` |
| an event — shown by where it happens | `4:3` |
| a photograph that is itself the work | its own orientation, `3:4` or `4:3` |
| an illustration or artwork | the ratio nearest its own shape, with `fit=contain` |
| a map | `16:9`, wide enough to show the area |
| a screenshot of an app, a page or a screen | its own shape, with `fit=contain`: `9:19` for a phone screen, `16:10` for a window, when the data does not give it |
| anything else, or unsure — food, a gadget, a mixed product | `1:1` |

When your data gives the picture's width and height, as most image and music APIs do, write
them as its ratio: a 1200×800 photo is `3:2`. When nothing gives them — a picture found on a
web page — a photograph that is itself the work keeps its whole frame with `fit=contain` at
`4:3`, so a portrait is shown entire rather than cropped. A picture is no sharper than its
source, and md2ui sizes it by its params, never by the file it downloads: when the URL or the
data says it is small (a `/250px-` thumbnail), give it that `max_width` rather than letting it
fill the column. A repeated run of pictures with no ratio is named by `check`;
a lone picture may keep the default.

**Choose a picture by what its source says it shows** — its caption, its alt text, the words
beside it on the page, the title your data gives it — and caption it with those words. A file
name or a URL says where a picture is kept, not what is in it.

Square is the safe answer when unsure: it crops the least. **Then render and check the
subject.** A ratio crops a photo to fit, so if the item itself is cut off, use `1:1`:

```md
![Headphones](phones.png?md2ui.aspect_ratio=4:3)   → the headband is cut off
![Headphones](phones.png?md2ui.aspect_ratio=1:1)   → whole
```

**2. Is the item someone → `shape=circle`.** A person, an artist, a band or an account is a
circle. A product stays square.

**3. Is the item the subject → its size.**

- **The subject draws bigger**: a person's profile or account, the top albums or the main
  items of the answer. Someone or a cover takes `max_width=250`. A product or a place takes
  the full width. **In narrow space a big picture always has its text below it**, however many
  lines there are (in wide space, question 6 may put it beside),
  and **the text follows the picture**: centre the picture and the text is centred too; leave
  the picture at the left, or let it fill the width, and the text stays at the left. A profile
  card centres its picture; an artist, an album or a product leaves it at the left.
- **Secondary draws smaller**: the person who wrote a review, edited a file or sent a message
  is secondary to the review, the file or the message. Additional items (more podcasts) and
  people lists are secondary too. Use `max_width=56` for someone beside their text, and `80` for
  someone as a tile above their name, or for a cover or an item.
  A picture of **one part of the subject** is secondary too — the bedroom of a stay, a detail of
  a product. Give it a `max_width` of about a third of the page and its caption under it:

  ```md
  ![Bedroom](bedroom.jpg?md2ui.aspect_ratio=3:2&md2ui.max_width=360)
  **Bedroom**
  _1 queen bed_
  ```

**4. How many lines does a small picture carry → above or beside.**

| Lines of text | The picture sits |
|---|---|
| 1, in a tile of a strip or grid | above, with the line centred under it |
| 1, in a row of a vertical list | beside it |
| 2 to 4 or 5 | beside, centred against it |
| more | above |

This table is for small pictures only. A big one is above its text (question 3).

One line centred under a picture: `content_align=center` on the picture, and a `...` spring on
each side of the line (`structure.md`):

```md
![Ann](ann.jpg?md2ui.max_width=80&md2ui.aspect_ratio=1:1&md2ui.shape=circle&md2ui.content_align=center)
... Ann ...
```

Two or three short lines beside: write them as **one line**. ` : ` stacks the pieces beside the
picture, and `@ct` centres them against it (`elements.md`). Keep ` | ` and ` - ` out of
a piece, because they split it again; a comma or a dot keeps it whole:

```md
![Emily Johnson](emily.jpg?md2ui.max_width=56&md2ui.aspect_ratio=1:1&md2ui.shape=circle) - **Emily Johnson** : _CEO_ @ct
![Striped tee](tee.jpg?md2ui.max_width=80&md2ui.aspect_ratio=3:4) - **Striped Clash Tee** : _Size M, Qty 2_ : **$344.00** @ct
```

When the lines carry their own ` - ` or ` | ` runs, or a bar, keep
them as written in an indented `:::0` row, between a `...` above and below (`structure.md`):

```md
- ![Santorini](santorini.jpg?md2ui.max_width=160&md2ui.aspect_ratio=3:4)
  :::0
  ...
  **Santorini**
  _Greece • Aegean Sea_
  📅 13 days • 🧘 Relaxed & Slow
  Planned: 60%
  ...
```

A profile, centred: the same `content_align=center` and springs, line by line:

```md
![Alex Foster](alex.jpg?md2ui.max_width=250&md2ui.aspect_ratio=1:1&md2ui.shape=circle&md2ui.content_align=center)
... **Alex Foster** ...
... _CEO at Meta_ ...
```

An artist, at the left: nothing to add, since the left is where a picture and its text start:

```md
![Fuerza Regida](band.jpg?md2ui.max_width=250&md2ui.aspect_ratio=1:1&md2ui.shape=circle)
**Fuerza Regida**
_Artist_
```

**5. Is it repeated?** Write every item the same way and the run grids (`repetition.md`). Wide
rows centre up and down with `@ct`. Tall tiles, a picture above one line, centre left to right
as above:

```md
![Gladyce](gladyce.jpg?md2ui.max_width=80&md2ui.aspect_ratio=1:1&md2ui.shape=circle&md2ui.content_align=center)
... Gladyce ...

![Elbert](elbert.jpg?md2ui.max_width=80&md2ui.aspect_ratio=1:1&md2ui.shape=circle&md2ui.content_align=center)
... Elbert ...
```

**A card about an item with a picture leads with the picture.** Covers, products and places
start every card at the same height that way, however long the titles are; a title above the
picture pushes each one down by its own number of lines. Glue the picture to the line above
the card's heading — `![…](cover.jpg)` then `### Title` — or open the card with an untitled
`### ` and write the title in bold under the picture:

```md
### 
![Nostalgia Makes me Squeal](cover.jpg?md2ui.aspect_ratio=1:1)
**Nostalgia Makes me Squeal**
_By spazzros_
[Open](agent:open?id=1) *[Save](agent:save?id=1)*

### 
![90's & 00's bands](cover2.jpg?md2ui.aspect_ratio=1:1)
**90's & 00's bands**
_By jacksonbalchin_
[Open](agent:open?id=2) *[Save](agent:save?id=2)*
```

Give every member the same params (see below).

**6. In wide space, what kind of answer is it → in the column, beside, or a card.** From 768px
there is room beside a picture, but whether to use it depends on the answer, not the picture.

**An article** — prose in sections with long paragraphs: a review, a guide, travel writing, an
explanation. Every picture spans the column at a wide ratio, under its heading or between
paragraphs, never beside them. A credit goes under it, muted, with its colon escaped:

```md
### Design and displays

![The open phone held in one hand](phone.jpg?md2ui.aspect_ratio=4:3,16:9@768)
_Image credit: Future_

The phone features a 5.4-inch cover display and a 7.6-inch main screen.
```

Related reading is a list of headlines, each with a small square thumbnail at the edge:

```md
- Flip vs Fold — 7 ways the slab phone beats the foldable ... ![Two phones](two.jpg?md2ui.max_width=72&md2ui.aspect_ratio=1:1) @ct
```

**A composed page** — short copy in blocks: a landing page, a front page, a catalog.

| The picture is | In wide space |
|---|---|
| the hero, alone under the page's title | full width, at a wide ratio |
| an illustration of one block of copy | beside it, about 40% of the row |
| the lead item's picture | beside its text, about 60% of the row |
| one of several peer items | a card each, picture above (question 5) |

Up to four or five lines beside a picture are centred against it: a `...` line above and below
them. Copy first puts the picture on the right; picture first puts it on the left and gives it
the weight. Both stack in narrow space (*Text beside an image*):

```md
___
...
**Street food that defines a city**
Begin at any neighborhood taquería, where the pastor has been perfected since 1959.
...
::: 1.5 >
![Tacos al pastor](tacos.jpg?md2ui.aspect_ratio=4:3)
___
```

```md
___
![A plate at Pujol](plate.jpg?md2ui.aspect_ratio=4:3)
::: 1.5 >
...
**The tasting menu, reimagined**
Pujol reopens with a menu built around its mole madre.
...
___
```

Either order works for a hero: copy first puts the headline first on a phone, picture first puts
the picture first. Down a long page, alternate the sides. In either kind of answer, a small picture — an avatar, a
logo, a thumbnail — keeps its narrow-space treatment.

**7. How far may it widen → its ratio ladder.** A picture fills its width at the ratio written
(*A ratio for each width*), so a picture that spans wide space needs a ratio that stays sensible
there. Pick the ladder from what the item is:

| The item is | `aspect_ratio` |
|---|---|
| a place, a venue, a room, a car, furniture | `4:3,16:9@768` |
| food, a gadget, or unsure | `1:1,4:3@768` |
| someone, an album, a cover | `1:1`, with a `max_width` |
| clothing, a poster, a portrait | `3:4` — beside its text, or with a `max_width` |
| an event | as a place — `4:3,16:9@768` |
| a photograph that is itself the work | its own orientation, never widened — with a `max_width`; its shape unknown, `4:3` with `fit=contain` |
| an illustration or artwork | its own ratio with `fit=contain`, never cropped |
| the picture that leads a page or an article, alone under its title | `4:3,2:1@600` — wide once it has room |
| a map | `16:9,2.35:1@768` — the one picture besides the hero that may span a wide page |

**In wide space, a square or tall picture never spans the full width** — `1:1`, `3:4`, a
portrait photograph. Give it a `max_width`, or put it beside its text. In narrow space the full
width is fine.

The steps are the picture's own width, so they follow the placement: a picture beside its text
at 60% of a 1280px page is about 750px wide and keeps its first ratio, while the same picture
spanning the page reaches `16:9`. Always write one: with none, a photo widens to `2.35:1`, a banner. Then check the crop
(question 1); if the item is cut off at its widest ratio, drop that step.

## Params apply to a whole run

Repeated cards are polled together, so one annotated picture sets the whole run: write the
ratio on the first card and every card takes it. If several cards carry params, give them the
same values — different values are settled by majority vote, and `md2ui render` prints the conflict. Pictures sized
by `max_height` are the exception: the run shares the height and each keeps its own
`aspect_ratio` (*A logo sized by its height*). Pictures on one line are not a run, and each
keeps its own (*Several images side by side*).

## Quick reference

| Want | Write |
|---|---|
| an icon at a real size | `?md2ui.max_width=56&md2ui.aspect_ratio=1:1` |
| a raster logo, uncropped | `…&md2ui.fit=contain` |
| logos of different shapes at one height | `?md2ui.max_height=36&md2ui.aspect_ratio=<its own>` |
| picture beside text | picture, `:::`, text — the picture first puts it on the left |
| beside it in wide space only | `::: 1 >` |
| a picture never narrower than N | `?md2ui.min_width=N` |
| a circular avatar | `?md2ui.shape=circle` |
| an item with no picture of its own: a person with no photo, a company with no logo | a placeholder the theme offers, `![Sara Zane](?md2ui.placeholder=avatar:SZ&md2ui.shape=circle)`: `guide("theme")` lists them |
| an image centred inside a left-aligned card | `?md2ui.content_align=center` |
| different in wide space | any property + its `_wide` twin |
