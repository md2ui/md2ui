---
name: listing
description: Rooms, stays, products or plans to choose from, each a card with its photo first, a rating, a few features and the price at the edge; use for hotel rooms, shopping results or offers.
---
# Listing

**Use for:** 2–6 options the user picks one of, each with a photo and a price. **Not for:** one item's own page (open it with a gallery, `images.md`).

```markdown
## Choose your room

### 
![Standard room](room.jpg?md2ui.aspect_ratio=16:9)
**Standard Room, 2 Double Beds**
`8.0` - Very good
⛰️ Mountain view
🛏️ 2 Double Beds
Per night ... $159
Total ... ~~$859~~ $567
**[Reserve](agent:reserve?room=standard)**

### 
![Sea view room](sea.jpg?md2ui.aspect_ratio=16:9)
**Standard Room, Sea View**
`9.0` - Wonderful
🌊 Sea view
🛏️ 2 Double Beds
Per night ... $202
Total ... ~~$1,092~~ $721
**[Reserve](agent:reserve?room=sea-view)**
```

**Why each marker**
- An untitled `### ` opens each card, so the photo leads and every photo starts at the same height — `images.md`.
- The rating is a chip, its word beside it with ` - ` — `elements.md`.
- One feature per line, its emoji first: the lines stack as a list — `elements.md`.
- ` ... ` sends each price to the edge; `~~…~~` strikes the old one — `structure.md`, `text.md`.
- Every card holds the same lines, so the run grids — `repetition.md`.
- Reserve is the action each card is for, one per card; its spelling is the theme's, `guide("theme")`.
