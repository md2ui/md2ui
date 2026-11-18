---
name: choices
description: A set of answers for the user to pick one from, each a tappable card; use when you need a decision before you continue.
---
# Choices

**Use for:** 2–4 options that each need a line of explanation. **Not for:** a plain yes/no, which is one line of buttons: `[Yes](agent:x) *[No](agent:cancel)*`.

```markdown
## Pick a delivery option

[
### Standard
In 3 to 5 days
`Free`
](agent:choose-delivery?option=standard)

[
### Express
Next business day
`$12`
](agent:choose-delivery?option=express)

[
### Pickup
_No store near this address_
~~`Free`~~
](agent:choose-delivery?option=pickup)
```

**Why each marker**
- Wrapping a block in `[ … ](agent:…)` makes the whole card the answer. The click comes back as `choose-delivery` with `option=` — `elements.md`.
- Every option has the same shape, `###` title plus line plus chip, so the options repeat and grid — `repetition.md`.
- The price is a chip, which is metadata. The action belongs to the card.
- An option the user cannot take keeps its place and shape, muted from inside: a `_…_` line saying why and the chip `~~…~~`. The brackets style nothing — `elements.md`.
- Keep bodies short, because text length sets how many columns fit — `repetition.md`.
- Once the user has picked, `mark` disables the others; or send the page again with the choice made — `elements.md`.
