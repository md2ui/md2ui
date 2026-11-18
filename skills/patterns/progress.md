---
name: progress
description: A job that is still running, how far it has got and what is left; use for an export, an upload, a sync or any task you started that takes time.
---
# Progress

**Use for:** one running job. **Not for:** a finished one (`result`), or several jobs with a status each (`status-list`).

```markdown
### "📦" Exporting 1,240 photos ... [`Cancel`](agent:cancel-export?id=7)

Exported: 68%

_843 of 1,240, about 3 minutes left_
```

**Why each marker**
- `"📦"` is the glyph alone, at the title's size, naming what is moving.
- ` ... ` puts the way out at the title's far edge: a minor action, because stopping is not what the user came for. Its spelling is the theme's, `guide("theme")`.
- `Exported: 68%` on its own line draws the bar — `dashboards.md`.
- The muted line says the counts and the time left in words.
