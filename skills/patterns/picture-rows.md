---
name: picture-rows
description: Items each with a picture and a few lines of text, side by side in a grid: the picture beside its text where a cell is wide enough, on top where not; use for sessions, episodes, dishes, trips or products.
---
# Picture rows

**Use for:** 2–6 items whose picture and text matter equally, each with two to four lines. As many items sit side by side as fit; longer text gives fewer, wider cells with the picture on top. **Not for:** one item per line with a small picture (`people`), or cards that always have the picture on top (`listing`).

```markdown
## Wind down
;;;
![Picturing Restful Sleep](sleep.jpg?md2ui.aspect_ratio=5:4)
:::1
**Picturing Restful Sleep**
🔉 Expert Guidance
`5 min`
:::2
;;;
![Breathing for Calm](calm.jpg)
:::1
**Breathing for Calm**
🔉 Guided
`10 min`
:::2
;;;
```

**Why each marker**
- `:::1` and `:::2` give the picture a third of the row and the text two thirds — `structure.md`.
- `;;;` closes each row and keeps the rows one run, so they grid: where a column is too narrow for the row, its picture moves on top. The first `;;;` keeps the heading out of the first row — `structure.md`, `repetition.md`.
- The picture's ratio comes from the item: a session or a dish `1:1` or `5:4`, clothing `3:4`, a place or a room `4:3` — `images.md`.
- The rows are one run, so the params go on the first picture only and every picture takes them — `images.md`. A row with no picture writes it empty, `![Name]()`: it draws a quiet box and keeps the run.
