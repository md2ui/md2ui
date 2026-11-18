---
name: shortcuts
description: The places or kinds of task the user can go to next, each a glyph over its word; use for a menu of bills, services or categories.
---
# Shortcuts

**Use for:** four to eight places to go, each named in one or two words. **Not for:** actions on one item (`quick-actions`), or items with details (`feed`).

```markdown
## Pay a bill

[
📱
Mobile
](agent:pay-bill?kind=mobile)

[
💡
Power
](agent:pay-bill?kind=power)

[
💧
Water
](agent:pay-bill?kind=water)

[
📺
TV
](agent:pay-bill?kind=tv)
```

**Why each marker**
- Each tile is a block inside `[ … ](agent:…)`, so the whole tile is the target — `elements.md`.
- The glyph names the place; every tile has one, and no two share it.
- The tiles repeat the same shape, so they grid — `repetition.md`.
