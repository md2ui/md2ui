---
name: hero
description: A page's headline, the line under it and its lead action; use at the top of a landing page, a product or a plan the answer introduces.
---
# Hero

**Use for:** the one headline a page opens with, its tagline and the action it leads to.
**Not for:** a headline beside its picture (`split`); a figure the page is about (`kpis`); a closing invitation (`call-to-action`).

```markdown
# 
*🌱*
___Grow food on a city balcony___
__A planting plan for your light, your space and the season you start in.__
[Plan my balcony](agent:plan-balcony) *[See a sample plan](agent:open?plan=sample)*
```

**Why each marker**
- `# ` with a trailing space opens the page's top section without a title, so the headline takes the Display tier instead — `text.md`, *Choose the text role before its size*.
- The icon is the one the headline is about, above it, in the theme's spelling: `guide("theme")`.
- `__…__` is the Lead tier: the tagline, one line on what the user gets — `text.md`.
- The lead action is the main button, and one alternative beside it is quieter; the spellings are the theme's.
- No blank lines: icon, headline, tagline and actions are one group.
- A step that needs the user's details, such as an email for updates, is an action too: an `agent:` action you handle with your own tools, or a `mailto:` or `https:` link to the platform's own form.
