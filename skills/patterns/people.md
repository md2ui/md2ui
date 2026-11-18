---
name: people
description: A short list with a small picture per row, a name over a detail, and a value at the edge; use for payments, contacts, members, tracks or places.
---
# People

**Use for:** 2–6 items, one row each: who paid you, who is on a team, the tracks of an album, the stops of a trip.
**Not for:** one person's profile, where the picture is the subject and sits above the name (`images.md`).

```markdown
## Today

- ![Eva Novak](eva.jpg?md2ui.max_width=56&md2ui.aspect_ratio=1:1&md2ui.shape=circle) - **Eva Novak** : _Received_ ... +$5,710.20
- ![Northwind Exchange](exchange.png?md2ui.max_width=56&md2ui.aspect_ratio=1:1&md2ui.shape=circle) - **Northwind Exchange** : _Received_ ... +$714.00
- ![Marco Ruiz](marco.jpg?md2ui.max_width=56&md2ui.aspect_ratio=1:1&md2ui.shape=circle) - **Marco Ruiz** : _Sent_ ... −$120.00
```

**Why each marker**
- Each item is someone, so each picture is a `1:1` circle, including the account's logo; a track or a place keeps a square, without `shape=circle`. The picture labels the row, so it stays small at `56` — `images.md`.
- Every picture has the same params, because a run shares one decision — `images.md`.
- ` : ` stacks the name over the detail, and ` ... ` sends the value to the edge — `structure.md`.
- A `- ` item tints each row — `dashboards.md`.
- The ` ... ` keeps the run in one column, as spring lines do. Rows with no value at the edge would grid instead — `repetition.md`.
