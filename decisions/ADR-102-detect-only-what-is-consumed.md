# ADR-102: The pipeline detects only what something downstream consumes

**Status:** active
**Domain:** pipeline
**Read when:** you are adding or removing a `DataPointType`, or wondering why
`detect_all` and `detect_pipeline` both exist.

## Decision

`DataPointDetector` has two entry points and they are not interchangeable.

* **`detect_all`** — every registered type. The unscoped view, for scripts and
  the detector's own tests. **The pipeline does not call it.**
* **`detect_pipeline`** — only the types in `_PIPELINE_TYPES`
  (`detector_scope.py`). This is what every leaf of every document is scanned
  with.

A type earns its place in `_PIPELINE_TYPES` for exactly one of three reasons:

1. **Drawn** — a `## Drawing elements` family or a `## Charts` display consumes
   it, or `## Fixed colors` → `### Datapoints` pins a color by its type.
2. **Structural** — the grouper turns it into a node (EMOJI and LINK become
   `NodeType.EMOJI` / `NodeType.LINK` in the element peel).
3. **Guard** — it draws nothing, but overlap resolution keeps the LONGEST match,
   so removing it hands its span to a shorter drawing pattern. Each guard and what
   it prevents is listed beside `_GUARD_TYPES`.

## Reason

A type scanned on every leaf and read by nothing is cost with no output. The
wider scope served a consumer that no longer exists
([ADR-701](ADR-701-no-learned-layout.md)). So the scope follows the consumer:
each type present has a stated reason.

This is not primarily a performance decision; what it buys is a **stated scope**.

## Constraint created

- **Narrowing further is not free, and the corpus cannot prove that it is.** A
  type that changes nothing across the corpus can still mis-type as soon as such
  content appears. Absence from the corpus is not evidence of safety; re-run
  `scripts/audit_detector_scope.py` before removing one.
- **`## Fixed colors` → `### Datapoints` accepts any key string**, with no
  validation against the enum. Dropping a type silently disables a theme's pin on
  that name. Check that before removing one.
- A new display that needs a type outside the scope adds it to `_DRAWING_TYPES`.
  It does not reach for `detect_all`.
- `node.data_points` is also the sole source of the protected ranges — the no-cut
  zones for separator scans. A dropped type takes its protection with it; adding
  one back (as a guard) is a legitimate answer to a bad cut.

## Reconsider when

`detect_all` loses its last caller outside the tests; the two entry points can
then collapse into one.
