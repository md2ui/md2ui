---
name: shelf
description: A group heading with a way to see all, over a run of the same card, one shelf per group; use for recommendations, new arrivals, a catalog's sections or an artist's releases.
---
# Shelf

**Use for:** items in named groups, each group a few cards the user picks by their picture. **Not for:** one set of options to choose between, with the action on every card (`listing`).

```markdown
## New in fiction ... [`Browse all`](agent:browse?shelf=fiction)

### 
![The Salt Road](salt-road.jpg?md2ui.aspect_ratio=2:3)
**The Salt Road** ... ***[❤️](agent:save?book=salt-road)***
_Mara Quinn, 4.4 ⭐_
$18.99

### 
![Low Tide](low-tide.jpg)
**Low Tide** ... ***[❤️](agent:save?book=low-tide)***
_Theo Brandt, 4.1 ⭐_
$14.50

### 
![Glasshouse](glasshouse.jpg)
**Glasshouse** ... ***[❤️](agent:save?book=glasshouse)***
_Ines Varga, 4.9 ⭐_
$21.00

***

## Read by the author ... [`Browse all`](agent:browse?shelf=audio)
```

**Why each marker**
- The shelf's title leads; ` ... ` puts its way in at the title's edge, in the theme's spelling for it — `structure.md`, `elements.md`.
- An untitled `### ` opens each card, so the picture leads; the ratio on the first picture sets the run — `images.md`.
- The name leads the card, the save is a quieter icon action at its edge, the detail is a caption under it.
- Every card holds the same lines, so the shelf grids — `repetition.md`.
- `***` ends a shelf; the next one repeats the same shape.
