---
name: feed
description: A few recommended items as matching cards, each with topic chips and a way in; use for suggested reads, videos or places.
---
# Feed

**Use for:** 2–3 recommendations, each with a title, one line and a way in. **Not for:** long results. A body over ~100 words stops the grid. For the `feed` tool, a value a process changes while the page is shown, read [`elements/a-value-a-process-changes-while-the-page-is-shown`](../elements.md#a-value-a-process-changes-while-the-page-is-shown).

```markdown
## Recommended reads

### How cities keep cool
The science of shade
`Urban design` `6 min`
[`Read`](agent:open-article?id=cool-cities)

### The case for slow travel
Fewer stops, longer stays
`Travel` `8 min`
[`Read`](agent:open-article?id=slow-travel)

### Sleep, explained simply
A decade of research
`Health` `5 min`
[`Read`](agent:open-article?id=sleep)
```

**Why each marker**
- Each `###` card has the same four lines, so the cards repeat and grid — `repetition.md`.
- Blank lines between cards, none inside one — `structure.md`.
- The chip run holds topic and length, which are metadata — `text.md`.
- One `agent:` link per card, with the item's id in the args: a way in that repeats on every card, so it reads quiet. Its spelling is the theme's, `guide("theme")`.
- Short body lines buy columns — `repetition.md`.
