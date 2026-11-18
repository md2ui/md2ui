---
name: ticker-rows
description: Items the user watches, each a row with its name over a detail, its recent line and its change as a chip at the edge; use for prices, fares, rates or any value that moves.
---
# Ticker rows

**Use for:** 3–8 watched items, one row each. **Not for:** one item's history (`chart-card`), or rows with one value and no line (`people`).

```markdown
## Fares you watch

- **Lisbon to New York** : _Nonstop, May 12_ ... Fare (EUR): 612 → 598 → 640 → 575 → 549 ... `-63`
- **Lisbon to Tokyo** : _One stop, June 3_ ... Fare (EUR): 980 → 1010 → 995 → 1040 → 1062 ... `+82`
- **Porto to Paris** : _Nonstop, April 28_ ... Fare (EUR): 88 → 92 → 79 → 84 → 81 ... `-7`
- **Porto to Berlin** : _Nonstop, May 2_ ... Fare (EUR): 120 → 118 → 131 → 127 → 129 ... `+9`
```

**Why each marker**
- ` : ` stacks the name over its detail; ` ... ` springs the line to the middle and the chip to the edge — `structure.md`.
- `→` joins each item's values into a line; bare numbers declare their unit in the key — `dashboards.md`.
- The change is a chip with its sign. The theme's rise and fall tokens mean good and bad news, `guide("theme")`; a fare that rises is bad news, so here the sign alone carries it — `text.md`.
- Every row has the same points, so the lines read alike down the list.
