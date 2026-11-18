---
name: gallery
description: Several pictures of one item, one leading over a strip of the others, with a way to see them all; use at the top of a product, a vehicle or an object's own page.
---
# Gallery

**Use for:** 3–8 pictures of one thing the user is deciding on, each a view or a detail of it. **Not for:** a place or a stay, which opens with a mosaic (`images/a-mosaic-of-pictures`); several items with a picture each (`listing`).

```markdown
# Ostra FR-4 Field Recorder

![Ostra FR-4, straight on](fr4-front.jpg?md2ui.aspect_ratio=4:3)

![Straight on](fr4-front.jpg?md2ui.max_width=80&md2ui.aspect_ratio=1:1) ![Top](fr4-top.jpg?md2ui.max_width=80&md2ui.aspect_ratio=1:1) ![Inputs](fr4-inputs.jpg?md2ui.max_width=80&md2ui.aspect_ratio=1:1) ![In the field](fr4-field.jpg?md2ui.max_width=80&md2ui.aspect_ratio=1:1)

[`Open all 9 shots`](agent:open-shots?item=fr4)
```

**Why each marker**
- The best picture leads on its own line, at the full width: the item is the subject — `images.md`.
- The others share one line, so they stay a strip and wrap where it runs out; each picture on a line keeps its own params — `images.md`.
- The lead's ratio comes from the item: an object `4:3` or `1:1`, clothing `3:4` — `images.md`.
- The pictures you did not include are a way in under the strip, in the theme's spelling for it — `elements.md`.
