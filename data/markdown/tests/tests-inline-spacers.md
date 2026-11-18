<!--
Every place a `+++` spacer can be written INSIDE a line (ADR-203), one case per section.

Spaced inside a line, `+++` / `++++` / `+++++` is horizontal space: small / medium / large,
by default 1x / 1.5x / 2x the group gap across (`Spacer <step> row` sets it in px). It is a
row separator whose gap is blank: `A +++ B` groups exactly as `A | B`, and the spacer is
spaced like a leaf, with the gap on each side of it. Render with D to see those gaps.

It only exists between side-by-side neighbours: where the line wraps it is dropped, a row
short of room shrinks it before its content, and consecutive spacers are one spacer of
their summed size.
-->

# The three steps

<!-- The same pair, a plain separator first for comparison. -->
Alpha | Bravo

Alpha +++ Bravo

Alpha ++++ Bravo

Alpha +++++ Bravo

# At a line's edges

<!-- At the start: an indent. At the end: space after the line's content. Neither is a
     cut, so each line groups exactly as it would without its spacer. -->
+++ Indented by a small step.

++++ Indented by a medium step.

Trailing space after this line. +++++

# Consecutive spacers

<!-- One spacer of their summed size: small + small, then small + medium. -->
Alpha +++ +++ Bravo

Alpha +++ ++++ Bravo

# Beside drawn separators

<!-- A gap keeps every separator it holds: the bar, then the space; space, bar, space. -->
Alpha | +++ Bravo

Alpha +++ | +++ Bravo

Alpha • Bravo +++ Charlie • Delta

# With a spring

<!-- A leading spacer after a spring is a minimum distance; a trailing one holds the
     pushed piece one step in from the edge. -->
Title ... +++ [Act](/act)

Title ... [Act](/act) +++

Title ... [Act](/act) +++++

# Elements

[One](/one) +++ [Two](/two) ++++ [Three](/three)

`chip` +++ `chip` +++++ `chip`

⭐ +++ Starred item

# Colon columns

<!-- ` : ` binds first: the spacer stands between two stacked columns. -->
94% : Accuracy +++++ 88% : Recall +++++ 71% : Coverage

# In a key-value value

**Delivery address:** 12 Main Street +++ Springfield +++ Illinois 62701

Status: ... Active +++ `since 2021`

# In a heading

## Weekly report +++ `draft`

Body under the heading.

# In list items

- First +++ item with a spacer
- Second ++++ item with a medium one
- Plain third item

1. One +++ `tag`
2. Two +++++ `tag`

# In a table cell

| Name | Note |
|---|---|
| Alpha +++ Bravo | plain |
| Charlie | Delta +++++ Echo |

# Where the line wraps

<!-- Narrow the window: no row starts or ends on a spacer, and the line's own edge
     spacers stay on its first and last rows. -->
`Alpha` +++ `Bravo` +++ `Charlie` +++ `Delta` +++ `Echo` +++ `Foxtrot` +++ `Golf` +++ `Hotel` +++ `India` +++ `Juliett` +++ `Kilo` +++ `Lima`

+++ `Alpha` `Bravo` `Charlie` `Delta` `Echo` `Foxtrot` `Golf` `Hotel` `India` `Juliett` `Kilo` `Lima` +++

# Short of room

<!-- Narrow the window until the chip barely fits: the spacer shrinks first, then leaves
     the row with its gap; the chip keeps its width. -->
+++++ `Identifier_Wide_Chip_Name_Longer_Still_Now_And_Longer_Again`

# Not spacers

<!-- Escaped, in inline code, unspaced, and the wrong count: all text. -->
\+++ is text.

Use `a +++ b` in code.

C+++ and D+++ are words.

Alpha ++ Bravo and Alpha ++++++ Bravo are text.
