---
name: buy-box
description: The options of one item, its price, its quantity and the button that buys it; use for a product's size, colour or plan before it goes in the basket.
---
# Buy box

**Use for:** one item's choices and the purchase, under its title or beside its gallery (`gallery`). **Not for:** several items to pick between (`listing`), or answers that each need a line (`choices`).

```markdown
## Ridgeline Espresso Blend

`Medium roast` - `⭐ 4.7`
___$16.00___ - ~~$19.00~~

_Pack size_
[250 g](agent:pick?size=250g&md2ui.choice=size) | *[500 g](agent:pick?size=500g&md2ui.choice=size)* | *[1 kg](agent:pick?size=1kg&md2ui.choice=size)*

_Grind_
*[Whole bean](agent:pick?grind=whole&md2ui.choice=grind)* [Espresso](agent:pick?grind=espresso&md2ui.choice=grind) *[Filter](agent:pick?grind=filter&md2ui.choice=grind)*

How many: ➖ [2/9] ➕

+++

[Put in basket](agent:add-to-basket?item=ridgeline&md2ui.commit=1) *[Order now](agent:order-now?item=ridgeline&md2ui.commit=1)*
```

**Why each marker**
- The price is the hero number, the old one struck beside it; tags lead as chips — `text.md`.
- Each option is a caption over its answers, the chosen one the main action and the rest quieter; `md2ui.choice` holds a tap in the window, and ` | ` keeps them one control — `elements.md`.
- The quantity is a count between ➖ and ➕, held in the window too — `dashboards.md`.
- Both purchase buttons carry `md2ui.commit`: one press reports the size, grind and count. Putting it in the basket is the main action, ordering at once the quieter one beside it.
