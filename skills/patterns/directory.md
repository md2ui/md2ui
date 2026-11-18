---
name: directory
description: Columns of links under short titles, with a closing line of small print; use for a site map, a footer, or a long list of places to go.
---
# Directory

**Use for:** many destinations grouped by topic. **Not for:** actions you want taken (`choices`).

```markdown
###### Company
[`About us`](/about)
[`Careers`](/careers)
[`Blog`](/blog)

###### Help
[`Help center`](/help)
[`Contact`](/contact)
[`Status`](/status)

###### Legal
[`Terms`](/terms)
[`Privacy`](/privacy)
[`Cookies`](/cookies)
***

_© 2026 Example_ ... [`Privacy`](/privacy) [`Terms`](/terms)
```

**Why each marker**
- `######` titles each column, and one link per line stacks it; columns of one shape sit side by side — `repetition.md`.
- Every titled list is its own group, however a design you have in mind stacks several into one column; the engine finds the columns for each width.
- Each link goes to another place, in the theme's spelling for a list of links: `guide("theme")`.
- `***` closes the last column, so the closing line is not part of it — `structure.md`.
- The `...` spring sends the small print to one edge and the links to the other — `structure.md`.
- A long list with no titles is a `:::` row instead: one cell per column of links, a `:::1` after each, and a `___` above and below — `structure.md`.
