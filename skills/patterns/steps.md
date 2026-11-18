---
name: steps
description: An ordered procedure the user follows, with an offer to help; use for how-to answers.
---
# Steps

**Use for:** 3–6 actions done in order. **Not for:** items to tick off (`task-list`) or events at times (`agenda`).

```markdown
## Share the project folder

1. Open **Settings** and choose **Sharing**
2. Add each teammate's email address
3. Set their access to **Can edit**
4. Send the invite and check it arrived

[Walk me through it](agent:guide-sharing) *[I'm done](agent:sharing-done)*
```

**Why each marker**
- `1.` items keep the order, and the ordinals are styled as tokens — `dashboards.md`.
- `**…**` marks the on-screen label the user looks for. Emphasis is styling, never structure — `text.md`.
- Keep each step to one short line. Long steps belong in prose above the list.
- Offers go on `agent:` buttons after the list, never on words in a step — `elements.md`.
