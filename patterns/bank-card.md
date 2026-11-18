---
name: bank-card
description: One card the user holds, as this theme's object card with its balance, holder and number; use when the answer is about one bank card, pass or membership.
---
# Bank card

**Use for:** one card the user holds and the answer is about: a bank card, a gift card, a membership or a pass. **Not for:** a list of accounts or cards (rows), or a balance with no card behind it (`kpis`).

```markdown
## {#card-1}
__$1,720.01__ ... "🛜"

+++++

_Holder name_
4756 •••• •••• 9018 ... _12/26_
```

**Why each marker**
- `{#card-1}` asks this theme for its object card, with no title drawn: the card is the object itself — `MEANINGS.md`.
- The balance leads in the Lead tier; `"🛜"` is the contactless glyph alone, at text size; ` ... ` pushes it to the right edge — `text.md`, `structure.md`.
- `+++++` opens the room a real card has between its balance and its details — `structure.md`.
- The holder is a caption over the number; the expiry sits right, after ` ... `. Write the number masked, as the card shows it.
