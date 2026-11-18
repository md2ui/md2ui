<!--
Every IMAGE ADJACENCY, one case per section, for previewing the two image keys:

  Elements -> Image spacing   image leaf <-> image leaf      REPLACES the element gap, default 0
  Elements -> Image distance  image leaf <-> non-image leaf  ADDED to the element gap, default 8

Both live in the leaf<->leaf branch of _sibling_gap, which is the LAST branch. Section A is
where they apply; section B is where a container neighbour short-circuits to the group or
section gap first and both keys silently stop existing.

The "-> " note on each case is the gap that was MEASURED for it, not the one intended.

To read the gaps, render with the debug overlay (D = spacing, P = padding) and separate the
four values under ### Elements, e.g.
    Row spacing: 6 / Col spacing: 6 / Group spacing: 18 / Image spacing: 44 / Image distance: 30
Keep them realistic: absurd values (thousands) change the ARRANGEMENT, not just the gaps,
and the document stops testing what it says.

All URLs are unresolvable on purpose: they draw the placeholder, so the document renders the
same everywhere with no network. Most images carry max_width purely so the page stays
scannable -- render_spacing.py never reads _is_width_capped, so capping changes the SIZE
and not one gap. C1 is left uncapped on purpose, as the full-bleed contrast to C2 and C3.
-->

# A. Where the image keys apply (both sides are leaves)

<!-- A1 -> IMAGE SPACING. The base case: two bare images, col axis. -->
## A1 image to image stacked

![First](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)
![Second](https://example.com/two.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

<!-- A2 -> IMAGE SPACING on the ROW axis. Two images on ONE source line ARE a row: the
     grouper flags the line line_split_group and the generator flows it, exactly as it
     flows a same-line run of buttons. This is the reachable case for Image ROW spacing. -->
## A2 image to image on one source line

![Left](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2) ![Right](https://example.com/two.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

<!-- A2b -> IMAGE SPACING, row axis, with a drawn separator between the two images. The
     image split runs after the separator split, so the gap is recorded as separator_chars
     like any other line's and ## Separators decides whether the dash is drawn at all. -->
## A2b image to image separated on one source line

![Left](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2) - ![Right](https://example.com/two.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

<!-- A2c -> element + IMAGE DISTANCE on the ROW axis, without an aside. An image beside a
     link is a run of elements like any other, so the two flow together. -->
## A2c image beside a button

![Logo](https://example.com/one.jpg?md2ui.max_width=96&md2ui.aspect_ratio=1:1) [Buy now](/buy)

<!-- A2d -> the ONE line that does not flow, and the one place an image is not a link. A
     link sits inside its sentence and is never peeled out of prose; an image cannot be
     drawn as text, so it DIVIDES the sentence -- and the halves either side are prose,
     which stacks. Col axis, so the image DISTANCE keys apply on both boundaries. -->
## A2d image among words

Words before the picture ![Middle](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2) and words after it.

<!-- A3 -> element + IMAGE DISTANCE on both boundaries. -->
## A3 image to text

Text above the image.
![Middle](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)
Text below the image.

<!-- A4 -> element + IMAGE DISTANCE. A link is a pill, but still a leaf. -->
## A4 image to link

![Above the button](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)
[Get started](https://example.com/start)

<!-- A5 -> element + IMAGE DISTANCE on both sides. A rule normally forces the GROUP gap
     whatever it separates; an image neighbour is deliberately excluded from that clause,
     so the distance wins here. -->
## A5 image to horizontal rule

![Before the rule](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

---

![After the rule](https://example.com/two.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

<!-- A6 -> the break itself takes NO gap, and the pair either side keeps the single
     IMAGE SPACING it would have had. -->
## A6 image to content break

![Before the break](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

___

![After the break](https://example.com/two.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

<!-- A7 -> element + IMAGE DISTANCE between the heading LEAF and the image below it, but
     the boundary to the NEXT section is the SECTION gap: the section branch returns before
     the leaf branch is reached, so image distance never applies across a heading.
     This is the "In headings - separated by image distance" item in technical-debt.md. -->
## A7 image to heading

![Last thing in this section](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

## A7b the next section

First thing in the next section.

# B. Where the image keys are never reached (one side is a container)

<!-- B1 -> GROUP. ` : ` stacks its pieces into a group, so the image sees a container. -->
## B1 image to colon column

![Above a column](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)
94% : Accuracy

<!-- B2 -> GROUP. The same two pictures as A1, one level of nesting apart. A group holding
     only pictures would take the image gap, but this list paints its own background, and a
     group with a background spaces like any other group. Under a theme whose lists paint
     nothing, the pair spaces like A1. -->
## B2 image to a wrapped image

![Loose image](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

- ![Wrapped in a list item](https://example.com/two.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

<!-- B3 -> GROUP. Glued content is a card, and a card is a group. -->
## B3 image to glued card

![Above the card](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

**Card title**
A line of card body copy.
A second line, so the block glues.

<!-- B4 -> SECTION, not group: putting a heading in the alt slot is what makes the URL a
     card background, and that heading also makes the card a SECTION OWNER. So a picture
     beside a picture-backed card takes the enclosing section's gap. -->
## B4 image to photo card

![Plain image](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

![
### Photo card
Markdown in the alt slot makes the URL the card background.
](https://example.com/photo.jpg)

<!-- B5 -> SECTION, and the two cards GRID side by side. Note what they are made of: a
     photo card holds NO image leaf at all -- the picture is a background, so _is_image_leaf
     is false for both sides and Image spacing could never have applied. -->
## B5 photo card to photo card

![
### First photo card
Body copy.
](https://example.com/photo.jpg)

![
### Second photo card
Body copy.
](https://example.com/photo.jpg)

<!-- B6 -> element + IMAGE DISTANCE. The control for B4: with NO heading in the alt slot
     the construct is not a photo card at all, just an ordinary image leaf with a long alt
     text. Same two lines of Markdown, completely different gap. -->
## B6 alt slot without a heading

![Plain image](https://example.com/one.jpg?md2ui.max_width=140&md2ui.aspect_ratio=3:2)

![
Body copy only, no heading, so this stays an image leaf.
](https://example.com/photo.jpg)

<!-- B7 -> the TABLE gap. Every table cell wraps its image in a group, and the table branch
     answers before either image clause. -->
## B7 images in a table

| ![A](https://example.com/1.jpg?md2ui.max_width=64&md2ui.aspect_ratio=1:1) | ![B](https://example.com/2.jpg?md2ui.max_width=64&md2ui.aspect_ratio=1:1) |
| --- | --- |
| one | two |

# C. Size and role, which the gap rule cannot see

<!-- C1-C3 -> the identical element + IMAGE DISTANCE. One number for a full-bleed hero, a
     24px icon and a circular avatar. _is_width_capped tells them apart for SIZING; nothing
     in render_spacing.py ever looks at it. -->
## C1 hero to text

![Hero](https://example.com/hero.jpg)
Body copy under a full-width photograph.

## C2 icon to text

![Icon](https://example.com/icon.svg?md2ui.max_width=24&md2ui.aspect_ratio=1:1)
Body copy under a 24px icon.

## C3 circle avatar to text

![Avatar](https://example.com/avatar.jpg?md2ui.max_width=64&md2ui.aspect_ratio=1:1&md2ui.shape=circle)
Body copy under a circular avatar.

# D. Which axis each key can actually be reached on

<!-- D1 -> IMAGE SPACING on the COL axis. Four capped logos on four LINES glue into one
     card and STACK; a strip is written on one line (A2), not on four. Kept as the col-axis
     twin of A2: the same four images, the only difference being where the newlines are. -->
## D1 logo strip written down the page

![Logo one](https://example.com/logo1.svg?md2ui.max_width=96&md2ui.aspect_ratio=1:1)
![Logo two](https://example.com/logo2.svg?md2ui.max_width=96&md2ui.aspect_ratio=1:1)
![Logo three](https://example.com/logo3.svg?md2ui.max_width=96&md2ui.aspect_ratio=1:1)
![Logo four](https://example.com/logo4.svg?md2ui.max_width=96&md2ui.aspect_ratio=1:1)

<!-- D2 -> IMAGE SPACING, col axis again. Blank lines between bare images leave them as
     plain stacked children of the section, not a grid. -->
## D2 bare images separated by blank lines

![A](https://example.com/1.jpg?md2ui.max_width=96&md2ui.aspect_ratio=1:1)

![B](https://example.com/2.jpg?md2ui.max_width=96&md2ui.aspect_ratio=1:1)

![C](https://example.com/3.jpg?md2ui.max_width=96&md2ui.aspect_ratio=1:1)

<!-- D3 -> the gap between a picture and the text beside it on the ROW axis, without them
     on one source line (A2c is the same-line route). A `:::` row since 2026-09-26, when the
     URL aside (`md2ui.arrangement=aside`) was retired; the `___` keeps the title out of
     cell 1. -->
## D3 aside picture left

___
![Side](https://example.com/one.jpg?md2ui.max_width=200&md2ui.aspect_ratio=3:2)
:::0
Copy that sits beside the picture rather than under it, long enough to hold the column open.

<!-- D4 -> the mirror of D3, picture last. -->
## D4 aside picture right

___
Copy that sits beside the picture rather than under it, long enough to hold the column open.
:::
![Side](https://example.com/one.jpg?md2ui.max_width=200&md2ui.aspect_ratio=3:2)
:::0
