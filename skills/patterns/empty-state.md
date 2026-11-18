---
name: empty-state
description: Nothing to show yet, what would fill it, and the one action that starts it; use when a list, a search or an upload area is empty.
---
# Empty state

**Use for:** a place that has no content yet, with one way to fill it. **Not for:** an error (say what failed), or a list that has content.

```markdown
#### 

+++++

... *🗂️* ...

... __No data sources uploaded__ ...

... Upload a file to start building your report ...

+++

... [⬆️ Upload](/upload) ...

+++++
```

**Why each marker**
- `#### ` with no title makes the card, and `+++++` gives it room above and below.
- ` ... ` at both ends centres each line.
- The icon is the one the empty state is about: the glyph of what is missing. Its spelling is the theme's, `guide("theme")`.
- `__…__` is the Lead title. The line under it says what fills the place, in a sentence.
- One main action, the one that fills the place. Leave it out when the user can do nothing.
