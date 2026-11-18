<!--
Every place a `+++` spacer can be written (ADR-203), one case per section.

`+++` / `++++` / `+++++` = Spacer small / medium / large (8 / 16 / 32 px unless the theme
says otherwise). A spacer is blank space: it adds its own length and never changes what
matches, so a card holding one still grids with its twins. Render with D to see the gaps
around it: the pair either side keeps the gap it had.

This theme still has `Image card photo band`, so the photo cards below show the band AND
the spacer until the band is removed.
-->

# Cards

<!-- A spacer at the end of a card's body stays in that card: B is taller, and all four
     cards still form ONE grid. -->
## Alpha
Body.

## Bravo
Body.

+++++

## Charlie
Body.

## Delta
Body.

___

<!-- The same four, with the space BETWEEN them: `***` ends Bravo's section, so the
     spacer sits between two runs, which form two grids. -->
## Alpha
Body.

## Bravo
Body.

***
+++++

## Charlie
Body.

## Delta
Body.

# Inside one card

<!-- Start, middle and end of one card, and the three steps. -->
## Steps
+++
Small space above this line.
++++
Medium space above this line.
+++++
Large space above this line, and a small one below it.
+++

# Groups

<!-- A glued block keeps its glue across the spacer: it is still ONE card. -->
**Glued card**
First line of the card.
+++
Second line, one small step further down.

**Glued card**
First line of the card.
Second line, with no spacer — the same card shape as the one above.

# Image cards

<!-- At the start: the space is photo above the words. Both spellings of the card get it. -->
![
+++++
## Tight card
Body over the photo.
[Act now](/act)
](https://images.unsplash.com/photo-1551650975-87deedd944c3?q=80&w=1200)

![
+++++

## Loose card

Body over the photo.

[Act now](/act)

](https://images.unsplash.com/photo-1551650975-87deedd944c3?q=80&w=1200)

<!-- At the end: photo below the words. -->
![
## Words on top
Body over the photo.
+++++
](https://images.unsplash.com/photo-1551650975-87deedd944c3?q=80&w=1200)

# Lists

<!-- Indented under an item: space inside that item, the list stays one list. -->
- First item
  +++++
  its second line
- Second item

<!-- Between single-line items: space between them, still one list. -->
1. One
2. Two
+++++
3. Three
4. Four

# Rows and columns

<!-- In a `:::` cell: vertical space inside that cell only. A row is opened and
     closed with `___`, or the heading above joins its first cell. -->
___
Left cell
:::
+++++
Right cell, pushed down
:::
Third cell
___

<!-- With the vertical spring: the spacer stays fixed, the spring takes the rest. -->
Top
+++
Under the top
...
Bottom

<!-- Between two colon-column lines: space between the lines, the columns intact. -->
94% : Accuracy
+++++
88% : Recall

# Mixed

- 👤 Customers: ___1,293___ - `⬇ +36.8%` : _vs last month_

# Not spacers

<!-- Escaped, in code, and the wrong count: all text. -->
\+++

```
+++
```

++ and ++++++ are text.
