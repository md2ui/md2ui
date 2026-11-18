# ADR-303: The aspect cap widens a grid only when that makes it shorter

**Status:** active
**Domain:** layout generator
**Read when:** a run of cards lands at fewer columns than fit across, or keeps more columns
than you expected, and you are looking at `LayoutGenerator._aspect_cap`.

## Decision

After a repeated run's column count is fitted, the aspect cap may lower it so that tall, thin
cards get wider columns. It does so **only when a lower count makes the run's tallest member
shorter** than at the fitted count (by more than `ASPECT_CAP_SHORTER_BY`). If no lower count
is shorter, the count stands. The rest of the cap (when it looks, how far it walks, how much
growth it tolerates) is stated with its constants in `layout_generator.py`.

## Reason

The cap exists for cards of **wrapping** text: four columns of a short paragraph break every
heading word by word, and two wider columns read properly and are shorter.

Content that does not wrap gains nothing from a wider column. Without the condition, the cap
also fired on it: a footer's four link lists dropped to 2 × 2 with every list exactly as
tall, doubling the page; ring cards and a theme's key lists lost columns at the same height.
The condition keeps exactly the reductions that shorten the tallest member.

The cap measures the result it is for — a shorter, more readable card — instead of the shape
(an aspect ratio) that usually predicts it.

## Alternatives rejected

- **Exempting columns made only of links.** Fixes the footer but not ring cards or key lists;
  a special case.
- **Leaving the cap as it was.** An author could force four across with a `:::` row, but the
  default would still double pages for nothing.

## Constraint created

Lowering a column count must buy height. Do not add another reason for the cap to widen a
grid without measuring that the tallest member gets shorter, and do not use it to steer a
look (ADR-300: width constrains, it does not steer).

## Reconsider when

A card's height stops being what `_cell_height` measures — for example a card whose height is
fixed by a picture's aspect ratio, where a wider column makes it taller, not shorter — or an
author-facing reason appears to prefer fewer columns of the same height.
