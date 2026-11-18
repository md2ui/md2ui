# ADR-300: A fixed width constrains the bento packer; it never steers it

**Status:** active
**Domain:** layout generator
**Read when:** a bento (mosaic) layout packs into a shape you did not want and
you are considering a width hint, a minimum width, or a column count to push it.

## Decision

Width inputs to the packer are **constraints**, not preferences. Do not add width
hints to steer a result. Keep declared minimums as small as the content truly
needs.

## Reason

The packer searches for an arrangement that satisfies its constraints. A width
added to *express a preference* removes candidate arrangements from that search,
so the packer does not do what the hint asked — it does the best it can with
fewer options, which is usually worse and always harder to predict. Large
minimums are the same mistake in a quieter form: they eliminate the compact
arrangements the packer needs to fit anything else.

Bento is a solve. Steering it is fighting it.

## Constraint created

If a bento result is wrong, the diagnosis is the *content* (structure, grouping,
minimums), not a missing hint.

## Consequence accepted

A solve re-solves on any measured change. One label a few characters longer can move a
whole page into a different arrangement, with every section still given the room it needs
(a longer account name in one row of `skills/pages/wallet-overview.md` can turn a narrow tile
beside a wide card into two even columns). That is the packer
working, not a defect: the arrangement follows the content and is not stable under small
edits to it.

## Reconsider when

A genuine hard minimum exists — an image that is illegible below a real pixel
size, for instance. That is a constraint, and stating it is correct.
