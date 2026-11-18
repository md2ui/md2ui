# findings/ — how a finding is fixed

A finding is an LLM's report, unverified until it is re-checked against the code. What a
finding folder holds, its header, its probes and the two types (**code**, **skills**) are in
`AGENTS.md` (§ *`findings/` — reports awaiting review*). This file is the procedure for
working one off: re-check, decide with the owner, fix, prove, close. It was learned over the
findings-fix batches of 2026-09-28 to 2026-11-03.

A **skills** finding (what agents read) is reviewed by the owner apart; a fix to text agents
read is measured with an eval before and after (`evals/README.md`).

## 1. Re-check before anything

Name the commit you measure on (`git log -1`): the owner and other sessions commit while you
work.

- **Read the header.** *Type: code* names a cause; *Type: skills* names none, so find it.
- **Already fixed?** Check first. A plan row can be stale and a feature already built
  (`git log -S '<symbol>'` finds when). Delete a finding only after the code or the probe shows
  the fix.
- **Re-run the cause.** Grep the cited lines (numbers drift; find the function), re-run the
  probe (`uv run md2ui render <content.md> --theme <THEME.md> --width N --out <png>`), or
  reproduce in a small script in the scratchpad, never in the repository. For "these should
  differ", compare hashes: `shasum -a 256 a.png b.png`.
- **Check your own measurement.** Before trusting "0 differences" or "0 documents", make sure
  the measure can see anything at all: a blank raster matches every other blank raster, and a
  shell that does not word-split a variable passes one wrong argument. Look at the image.
- **A claim that does not reproduce is corrected in the report at once**, with the numbers,
  never left for a later phase.

## 2. Show it, measure it, then ask

- **Show visible claims**: render before/after, crop to the rows that differ (skia/numpy),
  look at them yourself, and send them to the owner. Every point is validated with evidence
  re-run that day: a probe, hashes, quoted output. Never a claim carried over from a report.
- **Measure the reach before asking** about a fix that would move pixels or change what agents
  read: how many documents use the construct (`data/markdown/**`, the real LLM responses in
  `data/markdown/claude|gemini|gpt`, `skills/`, the agents' answers in `eval-runs/`), and what
  they draw now. Separate a construct's real uses from look-alikes (`© 2026` is text, `©️` is
  the emoji). The owner decides on numbers.
- **Measure through the real pipeline**: `session.load_grouping_kit()` and
  `session.group_markdown`, not a bare `MarkdownGrouper.process()`, which shatters prose the
  real run keeps whole.
- **Classify**: a real bug; real but latent (no corpus document reaches it: the fix is a unit
  test, the snapshots stay silent); not a bug (intended: say why, so it is not filed again);
  needs a decision (a semantic choice); the owner's (a feature, docs, parked).
- **Ask.** Explain the mechanism plainly, with the code lines, then give the options with a
  recommended one and what each would change. The owner decides one finding at a time, or all
  open decisions in one question. The owner's verdict often reframes the finding.
- **Sketch before building a visual change**: patch it in memory on one sample (monkeypatch in
  a scratchpad script) and show the before/after. An approved plan is not approval of the look.
  Test the obvious fix that way too: on 2026-11-03 the suggested `Orphan row` fix broke the
  workaround a corpus theme relied on, which only the sketch showed.

## 3. Fix

- **Where the code goes** is `AGENTS.md`'s table. Big files (`markdown_grouper.py`,
  `layout_render.py`, `render_measure.py`, `layout_generator.py`) must not grow without the
  owner; net-zero is fine. A file that grows past its budget for a second concept is split (a
  new module, as `pattern_respell.py` was), otherwise its budget is raised with a dated reason.
- **Tests fail before and pass after.** Prove the fail-before by running the test against the
  old code (the old file written in place, or the function recompiled in memory), not by
  reasoning.
- **A regression sample** in `data/markdown/tests/` for every fixed finding that no corpus
  document covers: the smallest document that shows it, with a header comment saying what it
  expects. A sample covers a case when it moved in this fix's snapshot for the same mechanism;
  never add a second one for a covered case. Check that the sample really shows the bug before
  the fix (one did not, until its cards were `####` sections).
- **A fix that inverts what a covering sample expects** updates that sample's comment in the
  same change.
- **Never edit**: the root `THEME.md` (unless the owner asks for that edit, and then only it),
  the corpora's existing documents, `skills/` (the skills session's), or a finding's claims
  you have not re-measured.

## 4. Prove it: the snapshots

The rules are `AGENTS.md` § *Before finishing*: the grouper snapshot for anything the grouper
does, the render snapshot for anything drawn, both for a performance change. What the batches
added:

- **Run them from the working tree.** A fresh worktree changes renders (the font assets are
  partly tracked).
- **Take the before side by copying files aside**, never with `git stash`. In a bash script:
  copy your changed files to the scratchpad, write `git show HEAD:<path>` over each, run the
  two befores, restore, `cmp` that the restore is exact, then run the after. Use bash arrays
  (`FILES=(…)`, `"${FILES[@]}"`); zsh does not split `$F`, and a failed `stash push` followed by
  `stash pop` once applied an old stash of the owner's.
- **Never edit `src/` while a render snapshot runs**: each render is a subprocess that imports
  what is on disk at that moment.
- **Two befores, then one after.** The befores must match each other (determinism); then
  explain every file the after changes. A changed PNG is cropped and looked at, against the
  prediction made before the run.
- **Chain**: the after of one fix is the before of the next, but only if nothing moved
  between them: `git diff <after-commit> HEAD -- src data/markdown THEME.md`. Another session
  may edit the corpus between your runs (a folder appearing or disappearing, a file changed):
  check the files' mtimes before calling a difference yours, and re-render the documents in
  question on one read with the old and the new code.
- **A flaky render** (a document that differs between two runs of the same code) is a finding
  of its own, not a change. Before filing it, render that page alone many times, some at once as
  the snapshot does (`xargs -P`) and some one by one, and count its hashes; file it with that
  count and the differing pixels' region, and name a cause only once a trace shows one. A flip
  seen once and never again is closed as not reproducible, with its hashes and the count, so a
  recurrence is filed with a trace.
- **Separate tree changes from flag changes** in an AST diff, and run changes from both (the
  grouper snapshot writes `<doc>.runs.json` beside each AST).
- The snapshot scripts take the output folder as their first argument and have no `--help`:
  `--help` becomes a folder in the repository. Always pass a scratchpad path.
- A change only the window shows (a cursor, a grace, a display move) needs the owner's live
  test; say so and record the result.

## 5. Close

- `git rm` the fixed finding's folder (a generated `grouping-ast.json` is ignored and may be
  left behind: remove the folder). When only part is fixed, remove the closed claims and keep
  what is open, with the date of the re-check.
- **Record it** where the plan keeps its record, with the numbers: what changed, what moved in
  the snapshots, and the test. An intended limit is recorded so
  it is not filed again (an ADR or the plan), never in `skills/` or `THEME_GUIDE.md`, which
  describe what md2ui does, not its defects.
- **Run `make check`** and report its result as it is; a budget it flags is a decision, not a
  formality.
- **Commit only when the owner asks**, and only your paths unless told to commit everything.
  Another session's commit may carry your staged deletions; check `git log` before saying a
  file is uncommitted.

## Several fixes at once

For a batch run in parallel: triage every finding first and ask all the questions; take a base
commit; give each fix its own worktree and agent (branch `fix/<name>` at the base, every missing
`assets/fonts/*` file linked one by one, then `uv sync`), with files grouped so no two agents
edit one function; agents never commit, stash or reset, re-check the cause first and stop on an
undecided semantic or a big-file growth. The orchestrator re-runs the gate and the snapshots on
each branch, merges them in an integration worktree (a `budgets.txt` conflict keeps both dated
reasons and the merged file's real count), checks that combined = base + each branch's own
changes, then fast-forwards `main`. Remove the agents' worktrees before running `make check` on
`main`: inside the checkout they stall pyright.
