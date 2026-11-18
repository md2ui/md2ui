---
name: result
description: What happened after the user acted, with the next step; use to answer a click that paid, sent, saved or failed.
---
# Result

**Use for:** the answer to one action the user just took. **Not for:** a job still running (`progress`).

```markdown
#### 

... ✅ ...

... __Payment sent__ ...

... €240.00 to Lisbon Lofts, reference 4471 ...

... [View receipt](agent:open-receipt?id=4471) *[Done](agent:done)* ...
```

**Why each marker**
- `✅` alone on its line is the verdict, coloured by the theme. When it failed, `❌`, the line says what to change, and the retry is the main action.
- `#### ` with no title makes the card; ` ... ` at both ends centres each line.
- `__…__` names what happened; the line under it is the detail the user may need later.
- The next step is the main action, and the way to finish a quieter one, in the theme's spellings: `guide("theme")`.
