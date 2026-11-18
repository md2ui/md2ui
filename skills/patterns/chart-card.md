---
name: chart-card
description: One measure over time or across items, under its title, with its total, its change, its period and the ranges to switch to; use for spending, traffic, usage or a price over time.
---
# Chart card

**Use for:** one measure the user follows. **Not for:** a few figures with no chart (`kpis`), or several items each with a small line (`ticker-rows`).

```markdown
## Steps

___61.4K___ - `▲ 9%`
_This week, against last week_

Steps: 8.2K (Mon) → 9.6K → 7.1K → 10.4K → 8.8K → 11.2K → 6.1K (Sun)

**[Week](agent:range?r=week)** ***[Month](agent:range?r=month)*** ***[Year](agent:range?r=year)***
```

**Why each marker**
- The figure leads: `___…___` is the Display tier, and its change is a chip after ` - ` — `text.md`. A rise or a fall takes the theme's token, `guide("theme")`.
- The muted line names the period the figure covers.
- `→` joins the points into a line, and a `(label)` names a point; across items, `- Key: value` rows draw a bar chart instead — `dashboards.md`.
- The ranges are a choice set inside the card: the one showing is the card's main action, the others quieter ones, in the theme's spellings.
