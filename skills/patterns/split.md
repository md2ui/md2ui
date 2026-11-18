---
name: split
description: Text beside a picture — side by side on a wide screen, stacked on a narrow one; use to present one idea with its image.
---
# Split

**Use for:** one idea with its picture — a product, a place, a step with its screenshot. **Not for:** several items that each have a picture (a row of cards).

```markdown
___
## Everything you crave, delivered.
Get a slice of pizza or the whole pie, from the spots you have been meaning to try.
[Find restaurants](agent:find-restaurants)
::: 1 >
![A picnic of takeout](https://example.com/picnic.jpg?md2ui.min_width=320&md2ui.aspect_ratio=4:3)
:::1.6
___
***
```

**Why each marker**
- `___` above and below opens and closes the row — `structure.md`.
- `::: 1 >` sets the text beside the picture in wide space and above it in narrow — `structure.md`.
- The picture written last sits on the right; write it first to put it on the left.
- `:::1.6` gives the picture the larger share of the row.
- `min_width` keeps the picture legible, `aspect_ratio` its shape — `images.md`.
- `***` closes the `##` written inside the row, so what follows is not part of it — `structure.md`.
