---
name: article
description: A piece of writing read top to bottom (an explanation, an article, a story, an answer in paragraphs), with a wide lead picture; use whenever the answer is read, not scanned.
---
# Article

**Use for:** an answer the user reads: paragraphs, a lead, a quote. **Not for:** items to compare or pick (`listing`, `feed`).

```markdown
# The city that gave its streets back to walkers
`Urban design` `Walking`

![A car-free street](street.jpg?md2ui.aspect_ratio=4:3,2:1@600)

![Ana Ruiz](ana.jpg?md2ui.max_width=40&md2ui.aspect_ratio=1:1&md2ui.shape=circle) - **Ana Ruiz** : _2 hours ago_ ... 🕑 _6 min read_

__In 1999 Alder Falls closed its centre to cars. Nobody wants them back.__

The plan was simple and unpopular. Through traffic would go around the old town, vans could come in for an hour each morning, and the rest belonged to people on foot.

## What changed

The centre gained twelve thousand residents while the region shrank.

> We did not ban cars. We gave the space back to the people already there.
```

**Why each marker**
- Paragraphs stay whole, as long as the answer needs: md2ui draws them as a reading page.
- The picture that leads a page is wide, `2:1` once it has room — `images.md`.
- The chips carry the topics. The author is a row: a small circle, ` : ` stacks the name over the date, ` ... ` sends the reading time to the edge — `people`, `structure.md`.
- `__…__` is the lead, `>` a quote, `##` a part of the piece — `text.md`, `structure.md`.
