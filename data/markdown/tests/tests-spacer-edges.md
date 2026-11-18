<!--
A `+++` spacer at the EDGE of something that sits beside something else: a `:::` cell, a
piece of a same-line row, a card in a run. One case per section; render at 320, 480 and
700 with the wireframe on (W) to see the spacers.

Written 2026-09-29 for the owner to decide how an edge spacer should behave when the row
runs out of room (findings-fixes S1, phase 6). Measured that day:
- between two pieces of ONE line (sections D, E) the line wraps first and the spacer
  is dropped, as skills/structure.md says;
- at the start or end of a `:::` cell (A, B, G) the spacer is not counted in the cell's
  width, so the cell stays beside its neighbour and its text wraps instead;
- in a run of equal cards (I) some cards keep their spacer and others shrink it.
A `___` separates the cases so no two of them grid beside each other.
-->

# A. Leading spacer in a `:::` cell

___
Alpha beta gamma
:::
+++++ Delta epsilon zeta theta
___

***
___

# B. Trailing spacer in the first `:::` cell

___
Alpha beta gamma +++++
:::
Delta epsilon zeta theta
___

# Inline C

Alpha beta gamma - Delta epsilon zeta theta

___

# C. Control, the same row with no spacer

___
Alpha beta gamma
:::
Delta epsilon zeta theta
___

# Inline D + E

Alpha beta gamma +++++ Delta epsilon zeta theta

___

# D. Spacer between two pieces of one line

Alpha beta gamma +++++ Delta epsilon zeta theta

___

# E. Spacer after a `|` separator

Alpha beta gamma | +++++ Delta epsilon zeta theta

___

# F. Leading spacer in a prose `:::` cell

___
**Status**
:::
+++++ The order was picked up from the warehouse this morning and is on its way to you now, arriving before six.
___

***
___

# G. Leading spacer in a weighted `:::` row

___
Alpha beta gamma
:::1
+++++ Delta epsilon zeta theta
:::1
___

***
___

# H. A held paragraph beside a `:::0` label

___
**Status**
:::0
+++++ +++++ The order was picked up from the warehouse this morning and is on its way to you now. +++++ +++++
___

***
___

# I. A run of cards, each line opening with a spacer

## Shipping
+++++ Delta epsilon zeta theta

## Returns
+++++ Within thirty days of delivery

## Support
+++++ Chat with us any time
