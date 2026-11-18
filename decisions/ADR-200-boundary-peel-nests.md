# ADR-200: The boundary peel nests in place; it does not flat-splice

**Status:** active
**Domain:** markdown grouper
**Read when:** working on the element walk (`_peel_boundary_dps_walk` /
`_peel_elements` in `markdown_grouper.py`), or on how a leading/trailing run of
elements — emoji, links, chips — separates from the text around it.

## Decision

When a leading or trailing run of elements is peeled off a leaf, the result is
**nested in place**: the leaf becomes a container holding the peeled run and the
remainder (TEXT is promoted to GROUP; a heading keeps its label). It is not
spliced flat into the parent's child list.

## Rejected alternative

Flat-splicing — lifting the peeled run into the parent. It destroys the fact
that the peeled content and the text it came from were on the *same line*.
Downstream, same-line content must lay out together, and after a splice nothing
says it belongs together: the run and its text become unrelated siblings among
the parent's other children.

## Reason

Nesting keeps the relationship in the tree, where the generator can still see it.

## Constraint created

The peel changes tree *depth*. Anything walking the tree by fixed depth, or
comparing node counts between parent and child, must tolerate this.

## Reconsider when

Same-line grouping stops being carried by tree structure and is carried entirely
by `source_line_id` / `line_split_group` instead. Then the shape would no longer
be load-bearing.
