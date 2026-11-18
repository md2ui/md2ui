---
name: comparison
description: Two or three options measured on the same attributes, side by side; use when the user is weighing alternatives.
---
# Comparison

**Use for:** 2–3 options against the same 3–6 attributes. **Not for:** one item's attributes (`specs`). To let the user pick, follow it with `choices`.

```markdown
## Model A vs Model B

| Spec | Model A | Model B |
|---|---|---|
| Weight | 1.2 kg | 1.6 kg |
| Battery | 18 hours | 12 hours |
| Ports | 2 | 4 |
| Price | $1,199 | $999 |
| Best for | `Travel` | `Desk work` |

_Prices checked today; both ship in two days._
```

**Why each marker**
- A Markdown table puts attributes in rows and options in columns. The header row is styled apart from the body — `dashboards.md`.
- Give every header cell a label, the first column included.
- Chips in cells hold categorical verdicts, which are metadata — `text.md`.
- A `_…_` line under the table is the Muted footnote — `text.md`.
- At narrow widths the theme decides whether rows become cards. You write nothing extra.
