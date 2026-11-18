<!-- `---` paints a line; `___` is the cut. A `---` written tight between two
     lines divides that block: the run stays ONE block, so it is one `:::`
     cell, with a rule under each line but the last. -->
## 

Text

:::

Key: ... value
---
Key: ... value
---
Key: ... value

<!-- The same run with no `:::`: one card, divided by its rules. -->
## 

Lorem ipsum dolor sit amet, consectetur adipiscing elit.
---
Short text

<!-- A `---` with a blank line on a side is a block of its own, and it no
     longer ends a `:::` row: the rule and the line after it stay in cell 2. -->
## 

A

:::

B

---

C

<!-- `___` still ends the row: C stacks below it. -->
## 

A

:::

B
___
C
