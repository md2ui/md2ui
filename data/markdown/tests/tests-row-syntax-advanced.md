<!--
  THE WHOLE-LINE MARKERS THIS DOCUMENT USES.
  A line holding nothing but one of these is structure, not text.

  ---  PAINTS, does not divide.
       A visible rule, and nothing else structural. A heading section swallows
       everything down to the next heading, so a `---` written under a
       section's last line belongs to THAT section as its last child and never
       becomes a sibling BETWEEN two sections. On its own it cannot separate
       them: four identical neighbouring cards still grid side by side.

  ___  DIVIDES, does not paint.
       Cuts the run it sits in and SURVIVES as a real sibling that draws
       nothing. That is what breaks up a repeated-element grid, because
       gridding only groups CONTIGUOUS siblings of the same shape. Unlike
       `---`, a section-trailing `___` is LIFTED OUT of the section as its
       next sibling, so it can separate two sections. Only `___` is lifted:
       `---` is the spelling every markdown generator emits for a divider, so
       lifting those would break up card boards nobody asked to break up. The
       rare, deliberate spelling is the one allowed to restructure.

       So `---` then `___` = a divider you can SEE and that also SEPARATES.
       That is the pair written between the four cards below.

  ***  CLOSES the heading section holding it.
       Everything after it is re-parented as that section's next SIBLING,
       keeping source order; the marker itself is consumed and never reaches
       the finished tree. Use it to put content BESIDE a heading's box instead
       of inside it - which is how the screenshots below escape their `###`.

  :::  makes the runs either side of it CELLS OF ONE ROW instead of a stack.
       `:::N` weights the cell ABOVE it; `:::0` means "take no share of the
       spare width, just fit the content". Consumed like `***`.

  EDITING NOTE: these HTML comments are stripped before parsing, but each one
  still leaves an EMPTY LINE behind - and a blank line is a block split. A
  comment added inside a glued run therefore BREAKS that glue. Only put one
  where a blank line already sits, and keep it to a single line anywhere else.
-->
# 4 ways `50,000+ teams` use Coda to supercharge their work days.
<!-- `___` DIVIDES: it cuts this run so the `#` title is not part of the run below and cannot be arranged beside it. `---` here would be swallowed by the `#` section instead of cutting it. -->
___
<!-- This image is attached to `## Writeups` by GLUE (consecutive non-blank lines are one segment). `:::` neither makes nor breaks glue - it only says the runs either side of it share a row. -->
![](https://sanity-images.imgix.net/production/3802869a8c1696c09986c721490f8ded81c26aea-52x52.svg?w=250&auto=format%2Ccompress&md2ui.max_width=60)
:::0
## Writeups

Coda is familiar like a doc and engaging like an app, so your team can jump in quickly, collaborate effectively, and make decisions that stick.

[Explore Zoom's decision doc](https://coda.io/@ross/root-cause-reasoning)

<!-- Blank line above = a new glued segment, and that is what gives group spacing. -->
_Replaces_
![What Writeups replaces](https://sanity-images.imgix.net/production/dc6ecafdbf551e8b69d9ff2c721a5642b271fd08-360x96.png?auto=format%2Ccompress&md2ui.max_width=210&md2ui.aspect_ratio=16:5&md2ui.fit=contain)

:::

### {#screenshot-2}
![A Coda writeups doc](https://sanity-images.imgix.net/production/e1f7d03809351daa1e198e05b4faf8afeaeaf60d-1096x720.png?auto=format%2Ccompress&md2ui.min_width=559&md2ui.max_width=560&md2ui.aspect_ratio=16:10)

<!-- `***` CLOSES the `###` section: the screenshot above is lifted OUT of it and becomes a sibling at `##` level, which is what lets the `:::` below close a row spanning the whole card. The marker itself is consumed and never reaches the tree. -->
***
:::

<!-- `---` PAINTS the divider and nothing else. It does NOT separate the cards: a heading swallows to the next heading, so this lands INSIDE the card above as its last child. -->
---
<!-- `___` is what actually stops the gridding: a section-trailing `___` is LIFTED OUT as a real sibling, so it sits BETWEEN two cards of identical shape and they are never contiguous. Gridding needs contiguous same-shape siblings - delete this and the four cards pack into a 2x2. -->
___

![](https://sanity-images.imgix.net/production/afc046fbcc9383ee58037d183acbba39a7db1590-52x52.svg?w=250&auto=format%2Ccompress&md2ui.max_width=60)
:::0
## Hubs

Teams move quicker together. So give them a place to get on the same page while centralizing everything from strategy to schedules.

[Explore Coda's team hub](https://coda.io/@codatemplates/engineering-team-hub)

_Replaces_
![What Hubs replaces](https://sanity-images.imgix.net/production/8de1d8cc679b2103c09a3ddc78558a0f1d22f9b6-246x96.png?auto=format%2Ccompress&md2ui.max_width=210&md2ui.aspect_ratio=16:5&md2ui.fit=contain)

:::

### {#screenshot-3}
![A Coda hubs doc](https://sanity-images.imgix.net/production/6b841f6760d03a82de7ebd9d1868050fe8996c87-1096x720.png?auto=format%2Ccompress&md2ui.max_width=560&md2ui.aspect_ratio=16:10)

<!-- `***` CLOSES the `###` section: the screenshot above is lifted OUT of it and becomes a sibling at `##` level, which is what lets the `:::` below close a row spanning the whole card. The marker itself is consumed and never reaches the tree. -->
***
:::

<!-- `---` PAINTS the divider and nothing else. It does NOT separate the cards: a heading swallows to the next heading, so this lands INSIDE the card above as its last child. -->
---
<!-- `___` is what actually stops the gridding: a section-trailing `___` is LIFTED OUT as a real sibling, so it sits BETWEEN two cards of identical shape and they are never contiguous. Gridding needs contiguous same-shape siblings - delete this and the four cards pack into a 2x2. -->
___

![](https://sanity-images.imgix.net/production/21def69429625ab15c36e596d21865359fa876ab-52x52.svg?w=250&auto=format%2Ccompress&md2ui.max_width=60)
:::0
## Trackers

Tables talk to each other, edits sync everywhere, views are personalized, and you can ditch the hacky spreadsheets.

[Explore Figma's product roadmap](https://coda.io/@yuhki/figma-product-roadmap)

_Replaces_
![What Trackers replaces](https://sanity-images.imgix.net/production/1edc9caac27582d93440c85423c3aae5d5c502b8-702x98.png?auto=format%2Ccompress&md2ui.max_width=210&md2ui.aspect_ratio=16:5&md2ui.fit=contain)

:::

### {#screenshot-4}
![A Coda trackers doc](https://sanity-images.imgix.net/production/3a73d607bcca00c98633b128ec3730725579ba94-1096x720.png?auto=format%2Ccompress&md2ui.max_width=560&md2ui.aspect_ratio=16:10)

<!-- `***` CLOSES the `###` section: the screenshot above is lifted OUT of it and becomes a sibling at `##` level, which is what lets the `:::` below close a row spanning the whole card. The marker itself is consumed and never reaches the tree. -->
***
:::

<!-- `---` PAINTS the divider and nothing else. It does NOT separate the cards: a heading swallows to the next heading, so this lands INSIDE the card above as its last child. -->
---
<!-- `___` is what actually stops the gridding: a section-trailing `___` is LIFTED OUT as a real sibling, so it sits BETWEEN two cards of identical shape and they are never contiguous. Gridding needs contiguous same-shape siblings - delete this and the four cards pack into a 2x2. -->
___

![](https://sanity-images.imgix.net/production/2a8e46b1bd02b102d2d8a08c8d551446fe410c80-52x52.svg?w=250&auto=format%2Ccompress&md2ui.max_width=60)
:::0
## Applications

With Coda, anyone can design a time-saving solution with a formula, button, or automation. And replace niche apps in your tool stack.

[Explore Google's LaunchCal](https://coda.io/@shivar/rethinking-googles-famous-launchcal)

_Replaces_
![What Applications replaces](https://sanity-images.imgix.net/production/4e5ccd63d1c9fca2af7ae56bb4fe06e086591f77-468x98.png?auto=format%2Ccompress&md2ui.max_width=210&md2ui.aspect_ratio=16:5&md2ui.fit=contain)

:::

### {#screenshot-5}
![A Coda applications doc](https://sanity-images.imgix.net/production/20b61c57b5c0b43da81274dfce9f927f55c20a0e-1096x720.png?auto=format%2Ccompress&md2ui.max_width=560&md2ui.aspect_ratio=16:10)

<!-- `***` CLOSES the `###` section: the screenshot above is lifted OUT of it and becomes a sibling at `##` level, which is what lets the `:::` below close a row spanning the whole card. The marker itself is consumed and never reaches the tree. -->
***
:::

<!-- `---` PAINTS the divider and nothing else. It does NOT separate the cards: a heading swallows to the next heading, so this lands INSIDE the card above as its last child. -->
---
<!-- `___` is what actually stops the gridding: a section-trailing `___` is LIFTED OUT as a real sibling, so it sits BETWEEN two cards of identical shape and they are never contiguous. Gridding needs contiguous same-shape siblings - delete this and the four cards pack into a 2x2. -->
___


## For product teams

<!-- Same `___` cut as at the top: keeps the heading out of the run below so it is not arranged with it. -->
___

#### 

- ![Product team hub](https://sanity-images.imgix.net/production/28ef7164271ac6b83023f3a604e17f39968ff527-160x160.png?auto=format%2Ccompress&md2ui.max_width=36&md2ui.aspect_ratio=1:1)
  <!-- The indentation puts `:::0` at the LIST GROUP level, so the icon sits beside its label. The `___` under each item is what BOUNDS that row to one item: remove them and the four items become ONE run, the `:::0` markers stop pairing icon with label, and the items grid instead. -->
  :::0
  **Product team hub**
___

- ![Decision doc](https://sanity-images.imgix.net/production/94b940aa7e28314ab9f8a0eb2b3387ff275ac06b-160x160.png?auto=format%2Ccompress&md2ui.max_width=36&md2ui.aspect_ratio=1:1)
  <!-- The indentation puts `:::0` at the LIST GROUP level, so the icon sits beside its label. The `___` under each item is what BOUNDS that row to one item: remove them and the four items become ONE run, the `:::0` markers stop pairing icon with label, and the items grid instead. -->
  :::0
  **Decision doc**
___

- ![$100 voting exercise](https://sanity-images.imgix.net/production/9809fea622ebe88c3d400d958c8d39cd35897fc8-480x480.png?auto=format%2Ccompress&md2ui.max_width=36&md2ui.aspect_ratio=1:1)
  <!-- The indentation puts `:::0` at the LIST GROUP level, so the icon sits beside its label. The `___` under each item is what BOUNDS that row to one item: remove them and the four items become ONE run, the `:::0` markers stop pairing icon with label, and the items grid instead. -->
  :::0
  **$100 voting exercise**
___

- ![Meeting forum](https://sanity-images.imgix.net/production/9089cf6533f1a9e52319d25d8d0a603c4aaafaac-480x480.png?auto=format%2Ccompress&md2ui.max_width=36&md2ui.aspect_ratio=1:1)
  :::0
  **Meeting forum**

<!-- `***` closes the `####` section so the row mark below lands outside it. -->
***
<!-- With the section closed, this `:::` closes a 2-column row: the list of items on the left, the screenshot below on the right. -->
:::

![](https://sanity-images.imgix.net/production/790addddeddb4b254864c57b547c780765f28232-1096x720.png?w=1500&auto=format%2Ccompress)
<!-- `:::3` weights THIS cell: the image takes 3 shares of the spare width (`:::0` = take no share, just fit the content). -->
:::3
