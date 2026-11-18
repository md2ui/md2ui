# ADR-100: The grouper annotates; the generator never infers structure

**Status:** active
**Domain:** pipeline
**Read when:** the layout generator needs to know something about the document
that it cannot see in the layout tree — "is this a heading section?", "were these
on the same source line?", "is this a table?".

## Decision

Structural facts are computed **once, in the grouper stage**, and recorded as a
flag on the node (most are stamped in `grouper_annotate.py`). The layout
generator reads flags; it never re-derives structure by inspecting content, node
types, or ordering.

New flags mirror the existing shape: `glued_content_group`, `line_split_group`,
`heading_group` / `heading_level`, `table_group`, `column_split_group`.

## Reason

The grouper has the source text, the line numbers and the parse. The generator
has neither, so anything it "infers" is a second, weaker implementation of a
decision already made upstream — and the two drift. An inference ends up
replaced by a flag anyway; adding the flag first is cheaper than adding it after
a bug.

## Constraint created

A generator change that needs new structural knowledge is really a **grouper
change plus a generator change**. If flagging is impossible, that is a signal
the grouping is wrong, not that the generator should guess.

## Reconsider when

A fact is genuinely about *layout* rather than *document structure* — available
width, measured size, breakpoint. Those are the generator's own business and no
flag should carry them.
