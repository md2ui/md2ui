<!-- Emphasis INSIDE a link's brackets styles the label in its variant's own
     face: bold, italic or bold italic, markers never drawn (owner decision
     2026-10-06). Emphasis AROUND the link still picks the variant. -->

<!-- Bold: Primary's own family in its bold weight. -->
[**Bold label**](/bold)

<!-- Italic: `_x_` is italic in the link's face, size and colour — not the
     Muted tier, which this theme makes small and grey. -->
[_Italic label_](/italic)

<!-- Bold italic, both spellings. -->
[***Bold italic label***](/bold-italic)

[___Bold italic label___](/bold-italic-underscores)

<!-- Partial: only the span is bold, measured as painted. -->
[**Got a Tip?** The Times offers several ways to send information ›](/tips)

<!-- The outer `*` picks Secondary (IBM Plex Mono); the inner marker styles its
     label. The theme loads that family's Regular file only: the bold resolves
     to the nearest loaded weight, and the italic is a synthesised slant. -->
*[**Wrapped bold**](/secondary-bold)*

*[_Wrapped italic_](/secondary-italic)*

<!-- Disabled state over an emphasized label. -->
~~[**Disabled bold**](/disabled)~~

<!-- Text variant: the backticks make the label a code span, whose markers
     stay literal; the emphasis displaced around it still bolds it. -->
[`**Literal markers**`](/text-literal)

**[`Displaced bold`](/text-bold)**
