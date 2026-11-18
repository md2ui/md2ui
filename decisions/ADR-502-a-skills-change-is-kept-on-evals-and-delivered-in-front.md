# ADR-502: A skills change is kept on evals, and reaches agents only in front of them

**Status:** active
**Domain:** skills
**Read when:** you change any text an agent reads (`skills/`, a pattern, `MEANINGS.md`, the core
note's generated sections, `check` and `show` messages, tool descriptions), or you are deciding
how a fact should reach agents.

## Decision

**A change to what agents read is kept only when an eval shows it helps.** Text that looks right
is not evidence: one sentence can flip behaviour, in either direction.
- **Measure:** before and after, on the same commit base, on small, mid and large models,
  several runs each. A sketch on the few tasks that show the case comes first; the full suites
  run only when the sketch moves.
- **Keep:** the change helps on most models and regresses on none, and time and input tokens on
  the answers it does not help stay roughly flat.
- **Grade blind.** The grader gets shuffled answers and the rubric, never the condition, and
  every miss quotes the line that shows it.
- **Count the miss before building a fix.** Several ideas had no miss to fix once counted in
  existing answers, and were dropped without a sketch.
- **Outcome over reading.** How much an agent reads is not the goal. What it writes is.

**A fact reaches agents in front of them, or through the answer they wrote. A pointer does not
deliver.** Agents read the core note and stop. What reaches them:
- **the core note's generated sections**, built from the theme's contract (`meanings`: the
  placement table, the theme's own spellings, the placeholder rows);
- **advice computed from the grouped answer**, returned by `check` and `show` (`advice`,
  `advice_patterns`). It fires only where the answer has the case, and costs nothing elsewhere.

## Why

- **Behind a pointer, a fact is not read.** The same rows that agents ignored behind a `guide`
  topic or a pattern index were applied almost every time once they sat in the core note, and a
  new pattern listed only in the index was never opened.
- **Advice triggered by the answer moves behaviour where it fires**, at no cost to answers
  without the case.
- **Plausible additions regress.** A routing bullet, a page-recipe table, a regrouped patterns
  index and a merged buttons table were each measured and reverted: some did nothing, and one
  lowered fit while doubling a model's tokens.
- **Wording decides where a rule fires.** A lead that keyed on "a picture your tools did not
  return" put placeholders on items whose pictures exist, and fewer real pictures were fetched.

## Constraint created

- Every edit to text agents read names its eval, before and after, in its commit or its suite's
  scores.
- A fact that must change what agents write goes in the core note, generated from the contract
  where it is per theme, or into advice triggered by the answer. Behind a pointer, it is
  reference only.
- Every line in the core note costs every answer, so it is kept only on a measured gain.

## Reconsider when

A host loads a skill's sections on demand by itself, so that what sits behind a pointer is read
as the core note is.
