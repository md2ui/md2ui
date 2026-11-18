---
name: photo-card
description: One item drawn over its own photo, its name, a line, tags and the action on the picture; use for a featured stay, trip, event or place.
---
# Photo card

**Use for:** the one item the section features, when its photo is the reason to look.
**Not for:** a run of items to compare, which are cards with the photo above the text (`listing`); a photo the user needs to see whole, since text covers part of it.

```markdown
## Featured stay

![
+++++
## Cliffside cabin in Big Sur
A timber cabin above the ocean, with a wood stove and a deck facing west.
`⭐ 4.8` - `2 nights`
[Reserve](agent:reserve?stay=big-sur-cabin)
](https://images.example.com/stays/big-sur-cabin.jpg)
```

**Why each marker**
- The block inside `![ … ](url)` is the card's content and the URL its background — `images.md`, *Image-as-background cards*.
- `+++++` at the top gives the photo room above the words; without it, two lines make a letterbox — `images.md`.
- One main action, on the card itself: it is the item the section is about.
