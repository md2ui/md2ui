# ADR-400: Measurement and painting share one normalization point

**Status:** active
**Domain:** renderer
**Read when:** text or a pill is clipped, a box is the wrong size, or you are
about to compute a width, a padding or a font size in the drawing path.

## Decision

Any quantity used by both measurement and painting is computed in **one**
function, and both paths call it. When a discrepancy appears, the fix is to
collapse the two computations into a single normalization point — never to add a
compensating adjustment on the drawing side.

## Reason

This is the repository's most persistent defect family. Measurement decides a
box's size; painting decides what goes in it. When each computes the same
quantity independently they agree on the common case and diverge on the edges —
emoji runs, inline code, wrapped pills, marker gutters — and the symptom is
always clipping, never an exception. Because the paths are far apart in the file,
the divergence is invisible in review.

A compensating fudge on one side hides the symptom for one input shape and
guarantees a new one later.

## Constraint created

The renderer is split along the measurement / painting seam, with an import
contract between them, so this is mechanically enforced rather than remembered —
[ADR-000](ADR-000-architecture-and-structure.md).

## Reconsider when

Never, as stated. A specific quantity may legitimately differ between the two
paths — but then it is two different quantities and deserves two names.
