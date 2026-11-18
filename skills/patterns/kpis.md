---
name: kpis
description: A row of headline numbers, each with its label and change; use when the answer leads with a few figures.
---
# KPIs

**Use for:** 2–4 figures the user should see first. **Not for:** many figures (a table) or a product's attributes (`specs`).

```markdown
## This week

___$48,200___
_Revenue_ - `+12%`

___1,284___
_Orders_ - `+4%`

___$37.54___
_Average order_ - `-2%`
```

**Why each marker**
- `___…___` wraps the whole line, which selects the Display tier: the number — `text.md`.
- `_…_` is the Muted caption naming the figure — `text.md`.
- ` - ` separates the change from the label, and backticks make it a chip — `elements.md`.
- Each KPI is two glued lines, with a blank line between KPIs. That repeated shape grids, and three makes a clean row — `repetition.md`.
- Leave colour to the theme. The sign already carries the direction.
