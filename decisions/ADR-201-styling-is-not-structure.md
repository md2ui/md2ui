# ADR-201: Styling is not structure

**Status:** active
**Domain:** markdown grouper
**Read when:** changing how the grouper decides two lines are "the same kind",
or adding handling for a new inline marker.

## Decision

Inline **styling** never changes grouping. Bold, italic, inline code and emoji
must not stop two otherwise-alike lines from grouping together. Links and images
**do** change kind, because they change what the element *is* — except that one
link with only decoration beside it is still that link's kind.

## Reason

Grouping asks "are these the same kind of thing?". A word being bold does not
change what the line is; it changes how it is painted. When styling leaks into
the kind test, a list where one item happens to contain `**bold**` silently stops
being a repeated run, loses its grid, and lays out differently from its
neighbours — for a reason no reader would ever guess.

A link or an image is a different element with different behaviour, so it is
legitimately a different kind.

## Constraint created

The fingerprint / kind test normalizes styling away. Markers must still be
**preserved on the node content** — normalization is for comparison only, and
the text keeps its `**` so it can be painted.

## Reconsider when

A styling marker starts carrying real semantics. The underscore text tiers
(`_x_`, `__x__`, `___x___`) are the existing exception: the wrapper is consumed
and *becomes* a property of the leaf, so it is no longer decoration by the time
grouping sees it.
