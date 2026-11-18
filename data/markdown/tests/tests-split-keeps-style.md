<!-- Styling survives a split: each piece keeps the style its text had in
     the unsplit line. A span with text outside it (the `!`) is inline
     emphasis, so BOTH halves stay inline; neither becomes a text tier. -->

<!-- Muted-shaped span, cut by a row separator. Both halves italic, not grey. -->
_Alpha | Beta_!

<!-- Lead-shaped span. Both halves bold, neither at the Lead size. -->
__Alpha | Beta__!

<!-- The same cut made by a spring. -->
_Alpha ... Beta_!

<!-- A key/value inside one span: the key is not Muted while the value is italic. -->
_Key: value here_!

<!-- The whole line IS the wrap: both halves take the Muted tier. -->
_Alpha | Beta_

<!-- A piece wrapped on its own in the source keeps its own tier. -->
_A_ | B
