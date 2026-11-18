# ADR-103: The grouper's answers are memoized, so they must stay pure

**Status:** active
**Domain:** pipeline
**Read when:** you are touching `grouper_memo.py`, any code that reads or edits a
data point dict, or the split criteria or the detector.

## Decision

The split criteria and the detector are memoized by text (`grouper_memo.py`), for
as long as the grouping kit `session.load_grouping_kit` builds is alive, capped
by `MEMO_CAP` with the least recently asked dropped first. A caller that hands
`MarkdownGrouper.process` bare objects gets a memo for that one call.

## Reason

The grouper's cost is how often content reaches the criteria and the detector,
not how many walks it makes: the same text is asked about repeatedly within a
document, and again whenever a document is re-sent, patched or re-saved.

## Constraint created

- **Nothing may write into `dp["value"]` after detection, anywhere.** The nested
  `value` is shared with the cached answer. A write corrupts every other node
  answered from the same text — in this document and in every later one grouped
  with the same kit. Code that needs a different `value` copies it first.
  `grouper_memo_tests` checks kept answers against fresh detection.
- **A memoized answer is a pure function of the text.** Criteria or a detector
  that grow per-document state (a context window, a running count) invalidate the
  memo.
- **Each answer is a fresh dict; it is not deep-copied.** Callers rewrite the
  top-level keys (`_detect_through_markers` re-bases `start`, `end`, `matched`),
  so every answer is a new list of new dicts; the `value` inside stays shared,
  per the first rule.

## Reconsider when

- The memo's footprint matters more than regroup speed: lower `MEMO_CAP`, or hand
  `process` bare objects for a per-call memo.
- The criteria or the detector change shape.
