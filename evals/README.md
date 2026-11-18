# Evals

Requests and the data behind them, used to measure how agents author against `skills/`. Each
suite is a folder holding a `tasks.md`: what a user asked, plus what the agent's tools
returned. An agent answers each task as the md2ui document it would show, with the notes
(`guide`) as its only source.

**Never copy a task or an answer into `skills/`.** An example taken from the eval teaches the
eval's answer and stops it measuring anything.

## What goes where

| part | where |
|---|---|
| the tasks | `evals/<suite>/tasks.md` — the data in a task is real: what a tool returned, or transcribed from a published design and said so at the top of the suite's `tasks.md` (owner, 2026-10-12); never invented |
| a condition: the theme an agent is served | a folder in the suite holding its `THEME.md` (and `MEANINGS.md`, `patterns/`), passed as `--theme` |
| the runner and scorer | `scripts/eval_run.py`, `scripts/eval_score.py` |
| a run's answers, transcripts, renders and manifest | `eval-runs/<suite>/<date>/<model>[-<condition>]/` — gitignored, like `screenshots/` |
| a run's scores | `evals/<suite>/scores.md`, one dated row per model and condition — tracked, so the trend outlives the finding |
| renders and sheets | made during the run, beside the answers, so a quick look costs nothing; disposable, since an answer and its commit rebuild them |
| an answer a finding quotes | copied into that finding's folder; the rest stay in `eval-runs/` |
| an answer that shows a real md2ui limit | promoted to `data/markdown/tests-render/` |

Keep what a rerun cannot reproduce: an agent's answer and transcript are never the same twice,
so they are kept; a render is the same every time from the same answer and commit, so it is
made once, for looking at, and never tracked.

## Running a suite

```sh
uv run python scripts/eval_run.py <suite> --model haiku --n 1 --task <id>   # try one first
uv run python scripts/eval_run.py <suite> --model sonnet [--theme evals/<suite>/<condition>]
uv run python scripts/eval_score.py eval-runs/<suite>/<date> --sheet --ledger evals/<suite>/scores.md
```

Each answer starts its own md2ui server. Measured 2026-11-01 on an idle machine: 24 sessions at
once connect in at most 8 s, so the runner's `MCP_TIMEOUT=60000` has room. Answers lost to a
connect timeout came from heavy load or an API outage, and the runner marks them; run one suite at
a time when the machine is busy.

A run is one suite × condition × model, each task answered **N times (3 by default)** by a
fresh agent. The runner isolates each agent by construction: a temp directory outside the repo,
no built-in tools, no settings, memory or installed skills, and only the md2ui authoring server
serving this checkout's `skills/` and the condition's theme. Nothing depends on the agent
choosing not to read `src/`.

Each run directory holds a `manifest.json`: suite, condition, model, date, N, the commit, whether
`skills/` was dirty, and a hash of the prompts. Two runs compare only when their manifests differ
in the one thing being measured.

Run each suite before and after the change it measures, on each model you care about (Opus,
Sonnet and Haiku at least): what trips a large model trips a small one harder. Capture both
sides back to back, and name the commit the `before` side ran on.

## Scoring

Score each answer on what is mechanical first, then by eye:

- `check`'s errors, warnings and notes;
- `show`'s digest: a section drawn as something the author did not mean (key–value cards for
  sentences);
- the data's pictures: present, or left out;
- fidelity: the data's values kept, nothing invented;
- for a writing request, the writing kept: words and paragraphs of 25 words or more, against the
  answer it was taken from in `data/markdown/claude`, `gemini` or `gpt` — an answer cut to
  cards loses what the user asked for (ADR-500), however good the cards look;
- the section's pattern (`guide("patterns")`): used where one fits;
- effort: tool calls, `guide` topics read, tokens.

A suite whose README states what counts as right for each task (as `emoji-roles` does) is
scored against it; otherwise the counts describe the answers but do not judge them.

**Report rates with their N**, never a single answer: "2/3" from one run each is one agent
changing its mind. A difference inside the spread between repeats of the same run is no change.

Beside the rate, report whether **every** trial of a task was right (clean^k in the scorer's
table). A user sees one reply, not the best of three: at 75% per trial, only 42% of tasks pass
all three.

**Read the transcripts of the failures** before believing a score. A failure should be fair: an
agent's mistake, not an ambiguous task or a scorer that rejects a valid answer. When every trial
of a task fails, suspect the task first. Grade what the agent produced, not the path it took —
effort is reported, never scored.

## Two kinds of suite, and a held-out set

**Mix writing requests with catalogs.** md2ui is for any answer, articles and explanations
included. A suite of lists, prices and recommendations only measures catalogs, and teaches
the notes to turn every answer into one. Balance each suite the other way too: tasks where a
display (a chart, chips, an icon) should appear, and tasks where it should not.

- A **regression** suite holds tasks agents already get right; it should stay near 100%, and runs
  on any change to `skills/`.
- A **capability** suite holds tasks agents still get wrong; it is what a change tries to raise.

Each suite's README says which it is. A task moves from capability to regression once it passes
on every model.

Keep some tasks **held out**: not read while editing `skills/`, run only to confirm a change.
Whoever edits the notes has read the other tasks and their answers, and teaches towards them
without copying anything. When a held-out task has been read, it is no longer held out; add a
fresh one from real tool output.
