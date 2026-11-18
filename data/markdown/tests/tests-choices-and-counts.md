<!-- Choices and counts (ADR-405). Size is a ` | ` run whose options share one
     `md2ui.choice` name: one segmented control, S chosen (the main button). Milk is
     space-divided: separate pills, Oat chosen. Cabin's run is too long for its column
     and falls back to separate pills. Each count is its digits between two round
     buttons on one line — on a key line, in a `:::` row and in a table cell; Children
     at 0 shows its ➖ muted. Before ADR-405 every count drew as a slider between the
     signs, wrapping ➕ and stacking in the table. -->

# Your order

_Size_
[S](agent:size?v=s&md2ui.choice=size) | *[M](agent:size?v=m&md2ui.choice=size)* | *[L](agent:size?v=l&md2ui.choice=size)*

_Milk_
*[Whole](agent:milk?m=whole&md2ui.choice=milk)* [Oat](agent:milk?m=oat&md2ui.choice=milk) *[Soy](agent:milk?m=soy&md2ui.choice=milk)*

_Cabin_
[Economy](agent:cabin?c=y&md2ui.choice=cabin) | *[Premium economy](agent:cabin?c=w&md2ui.choice=cabin)* | *[Business](agent:cabin?c=j&md2ui.choice=cabin)* | *[First](agent:cabin?c=f&md2ui.choice=cabin)*

Quantity: ➖ [2/9] ➕

___
_Adults_
➖ [2/9] ➕
:::
_Children_
➖ [0/6] ➕
___

| Item | Qty |
|---|---|
| Socks | ➖ [2/9] ➕ |
| Hat | ➖ [1/3] ➕ |

[Add to cart](agent:add?id=7&md2ui.commit=1) *[Cancel](agent:cancel)*
