---
name: status-list
description: Items that each carry a current status (orders, tickets, jobs); use when every row is a thing plus where it stands.
---
# Status list

**Use for:** several items, each with one current state and a short detail. **Not for:** one item's history (`steps`), or states the user changes (`task-list`).

```markdown
## Your orders

- **Desk lamp** : Order 4821 ... `Shipped` : Arrives Thursday
- **Wool throw** : Order 4817 ... `Delivered` : Left at the door
- **Ceramic mugs** : Order 4809 ... `Processing` : Ships in 2 days
- **Floor rug** : Order 4795 ... `Returned` : Refund issued

[Track an order](agent:track-order) *[Start a return](agent:start-return)*
```

**Why each marker**
- ` ... ` is a spring: the item goes left and its status right — `structure.md`.
- ` : ` stacks each side, name over id and status over detail — the two-column row in `dashboards.md`.
- The status is the primary field: each row is read for where it stands.
- `` `Shipped` `` is a chip. A status is metadata, never a button — `text.md`, `elements.md`.
- What the user can do goes on `agent:` buttons below the list: the main action, then a quieter one, in the theme's spellings — `guide("theme")`.
