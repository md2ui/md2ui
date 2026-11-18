# ADR-701: md2ui has no learned layout

**Status:** active
**Domain:** layout model
**Read when:** you are tempted to add a trained model, a training corpus or a gold-replay hook to
the pipeline, or to make the generator guess an arrangement the author did not write.

## Decision

The pipeline has **no learned parts**. The grouper's split criteria and the data point detector
are rules. The layout generator is rules, plus what the author writes (`:::` rows, `...`
springs, `+++` spacers, image URL params) and what the theme asks for.

An experimental per-group layout model, a topic labeler, their training data and the hooks that
served them were removed. So was the image aside only they could reach: an image goes beside
text through a `:::` row the author writes. The per-node render-hint vocabulary stayed, as
`pipeline/render_hints.py`, because image URL params use it.

## Why

The model never shipped: it was opt-in, no snapshot reached it, and nothing in a real run used
it. Its scaffolding still cost dependencies, tests and generator branches. Its intended next
shape, Markdown generation over a raw LLM response rather than layout prediction, would not have
reused that code.

## Constraint created

A layout choice the author did not write is not inferred. It is authored syntax, a theme key,
or the rules' feasibility. A new learned component needs its own decision record.

## Reconsider when

A learned component is proposed again.
