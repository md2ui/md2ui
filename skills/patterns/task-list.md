---
name: task-list
description: A checklist the user ticks off and sends back with one button; use for to-dos, preparation lists and settings to confirm.
---
# Task list

**Use for:** things the user does and marks done. **Not for:** states only you change (`status-list`), or an ordered procedure (`steps`).

```markdown
## Before the move

- [x] Book the moving van
- [ ] Forward mail to the new address
- [ ] Cancel the gym membership
- [ ] Pack the kitchen
- [ ] Transfer the utilities

[Save](agent:save?md2ui.commit=1)
```

**Why each marker**
- `- [ ]` and `- [x]` draw controls. The theme draws them as checkboxes or switches — `dashboards.md`.
- `?md2ui.commit=1` sends the list at once: ticks wait on the page, and the press reports what changed — `elements.md`.
- A press changes nothing for good: to keep the ticks, use `mark`, or re-send the list with `[x]` — `elements.md`.
- Write one short task per item. The label is what comes back to you.
