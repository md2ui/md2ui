# AGENTS.md

md2ui is a **pipeline**, not a set of features: each stage annotates one shared
tree and hands it on. What it is for is in `README.md`.

## The gate

```
make check       # the gate; each step is a Makefile target with its comment
uv add <pkg>     # add a dependency; never edit pyproject.toml by hand
```

Run `make check` before claiming a change works. It is the only gate.
Setting up a checkout and the other `make` targets are in `CONTRIBUTING.md`; using md2ui is in `README.md`.

The root `THEME.md` and `style-template.md` are owner-authored default
artifacts. **Agents do not edit them.** Tests that need a complete theme use
`data/markdown/tests/THEME.md`; the root default is not a test fixture.

## Layout

```
src/md2ui/pipeline/    the stages, in order:
                         markdown_grouper.py    Markdown -> MarkdownGroupNode tree; drives the phases below
                         grouper_types.py       MarkdownGroupNode / NodeType — the shared model
                         grouper_block_splits.py      where the document divides into blocks
                         grouper_inline_marks.py      the markdown-marker vocabulary
                         grouper_separator_splits.py  cuts at a typed separator
                         grouper_element_splits.py    cuts around an element
                         grouper_value_splits.py      cuts around a value
                         grouper_glue.py        which siblings become one card; group collapse
                         grouper_annotate.py    flags stamped on a finished node
                         grouper_split_criteria.py    the rules that decide which kind of cut a line takes
                         data_point_detector.py the value types the pipeline consumes (ADR-102)
                         layout_generator.py    tree -> LayoutNode, arrangement decisions
                         layout_render.py       measure + paint (Skia/GLFW), THEME.md consumption
                         render_picture.py      the recorded document the window replays; viewport culling (ADR-401)
                         theme.py               THEME.md parser and style dataclasses
src/md2ui/app.py       the user's window: GLFW, key bindings, live reload — the only watcher
src/md2ui/main.py      the CLI for agents and scripts: each command runs once and exits
src/md2ui/session.py   the pipeline start to end, shared by both shells — they call the pipeline, never the reverse
src/md2ui/utils/       leaf helpers: fonts, image cache, scroll state
tests/                 one <feature>_tests.py per feature, each exposing a TESTS list
evals/                 agent-authoring suites: requests + real data, scored against skills/; runs go to eval-runs/ (gitignored)
scripts/               one-purpose CLIs; the module docstring is the description
decisions/             ADR-nnn records, numbered by domain; read when pointed at one
findings/              LLM reports awaiting human review — one folder each, unverified, see below
proposals/             features and design changes awaiting the owner's decision — see its README.md
```

`findings/`, `proposals/` and `evals/`, and a plans folder beside them, are working folders
whose contents are private: the owner keeps them in a separate repository, md2ui-private,
mounted at these same paths (its own notes say how). In a public checkout each of the three
holds only its procedure `README.md`, plus the example suite `evals/example/`, and git ignores
whatever else is written there. A contributor without that repository files a finding or a proposal as a GitHub issue
instead: `CONTRIBUTING.md`.

The TypeScript client library, md2ui-ts, is a separate git repository, kept beside this
one in a local checkout (its repository is github.com/md2ui/md2ui-ts).

This is a curated map of the stages, not an inventory: the pipeline holds more
modules than are listed. Each module's own docstring says what it owns.

Dependencies point one way: `pipeline` -> `utils`. Nothing imports upward.

## Where a new X goes

| New… | Goes in | And also |
| --- | --- | --- |
| structural annotation (a flag on nodes) | `grouper_annotate.py` | the generator *consumes* flags, it never re-infers structure — ADR-100 |
| a cut inside a line | `grouper_separator_splits.py` / `grouper_element_splits.py` / `grouper_value_splits.py` — the one that names the cut | `grouper_inline_marks.py` owns the marker vocabulary all three share |
| arrangement / sizing decision | `layout_generator.py` | an arrangement the author did not write is never guessed — ADR-701 |
| drawing or measurement | `layout_render.py` | measurement and painting must share one normalization point — ADR-400 |
| THEME.md key | `theme.py` parser + dataclass default, then consume it in `layout_render.py` | document it in `THEME_GUIDE.md` |
| a display toggle, or anything else the document paint reads | `render_settings.VIEW`, read in `draw_document` | add it to `render_picture.view_state`, or the window keeps replaying the old recording — ADR-401 |
| test | `tests/<feature>_tests.py` with a module-level `TESTS` list | a module with no `TESTS` list never runs |
| a move of existing code out of a big file | nowhere new — use `scripts/extract_module.py` | read its docstring first, and run its `check_arity` after any signature change |
| a one-off script that builds or transforms a sample | nowhere in the repo — a temp dir outside it | commit the artifact, not the generator. If it will be run again it belongs in `scripts/`, and putting it there is a commitment to keep it working |

## Finding things

Search before browsing. The large files are large; grep the nouns of your task rather
than reading them end to end. A feature's **test module docstring** is usually the
cheapest accurate description of how that feature works.

| Question | Read |
| --- | --- |
| What does this THEME.md key mean? | `THEME_GUIDE.md` |
| What is in flight or known broken? | `findings/` and `proposals/` (private, see above), and the GitHub issues |
| Why is it built this way? | `decisions/` — the domain index is at the end of this file |
| An LLM's report on something it investigated | `findings/` — **unverified, see below** |
| How a finding is re-checked, fixed, proved and closed | `findings/README.md` |
| A proposed feature or design change, not yet decided | `proposals/` — its `README.md` says how one is filed and closed |
| Verifying a change did not alter output | *Before finishing*, below — the snapshots |
| How Markdown should be authored *for* md2ui | `skills/` — ships to end users, not repo guidance |
| What this project is for, and how to run it | `README.md` |

## The corpora, and what each one is for

Five directories of Markdown that look alike and are not. Using the wrong one
proves the wrong thing.

| Directory | What it is |
| --- | --- |
| `data/markdown/claude`, `gemini`, `gpt` | Real LLM responses. The **origin** of the problem the project exists to solve, not fixtures |
| `data/markdown/tests` | Documents that once broke or regressed. A snapshot corpus; things are added here *after* they go wrong |
| `data/markdown/tests-render` | Documents written by LLMs to find md2ui's real limits, **without those LLMs reading the pipeline**. Deliberately adversarial |
| `data/markdown/tests-render/<kind>/` (`catalogs`, `landing-pages`, `documentation-pages`…) | Real websites imported as Markdown, to test how faithfully the UI can be reproduced; filed by kind, beside the adversarial documents |
| `evals` | Requests and the data behind them, to measure how agents author against `skills/`. Not under `data/`: it is a test suite for the authoring surface, as `tests/` is for `src/`. **Never copied into `skills/`** — see its `README.md` |

`data/` holds corpora only — Markdown, references, ASTs, renders. **No code.** A
transform that builds a sample is either durable, in which case it belongs in
`scripts/` where it is linted, type-checked and budgeted, or it is one-off, in
which case it belongs outside the repo entirely. Nothing under `data/` is checked
by anything, so a script left there stops working without telling anyone.

## `findings/` — reports awaiting review, not facts

**Everything in `findings/` was written by an LLM and has not been verified.**
Some is outdated, some was wrong when written, and a reported "limitation" is
sometimes correct behaviour the document's author needed to be taught instead
([ADR-500](decisions/ADR-500-skills-are-built-outside-in.md)).

So: **never cite a finding as established fact, and never act on one without
re-checking it against the code.** If you find one that is wrong, correcting it
is welcome — say what you measured.

Write your own findings there, including limitations you could not resolve.
A human reads `findings/`, promotes what is real to a fix or a proposal, and
discards the rest.

**`findings/` holds two things and nothing else: the reports, and the evidence for them**
(besides its `README.md`, the procedure for fixing one).

| in | out |
|---|---|
| the report (`README.md`) | the exercise a report was measured on — that is a fixture, see below |
| probes: the small documents, theme variants and renders that show one claim | anything another part of the repo will still want once the finding closes |
| hash comparisons, terminal output, measurements | code, scripts, tests |

Everything in it is disposable on the day its finding closes. If something in a finding's
folder would be a loss to delete, it is in the wrong place — move it to the corpus, to
`skills/`, or to a proposal, and cite it from the report by path.

### One finding, one folder

A finding is a **directory** under `findings/`, named for the thing it is about, holding a
`README.md` and — where the finding can be shown — the documents that show it:

```
findings/<finding-name>/
  README.md                     the report — see the header rule below
  <id>-<what-it-shows>/         one isolated probe per claim
    content.md                  the smallest document that shows it
    THEME.md                    the theme that isolates it
    THEME-<variant>.md          only when the claim needs two renders compared
    grouping-ast.json           generated; rebuild rather than trust it
    render.png                  the evidence
```

**The `README.md` opens with a header, before any prose**, so a reader knows in two lines
what the report is about and where to look:

```md
# <title>

**Type:** skills | code
**Source:** the path(s) this is about — the document and theme it was measured on for a
skills finding, the module(s) it concerns for a code one.
```

Keep `Source` to the paths a reader would open first; the full list belongs in the
**Sources** table below it.

Rules that make the structure worth having:

- **One reproduction per claim, not one sheet for all of them.** A combined sheet shares a
  theme, so its cards share a background rotation and a card can silently land on the wrong
  colour and quietly stop testing what it claims. Isolation also removes "which of these six
  things caused it" from every render.
- **Each reproduction is the smallest document that still shows the finding.** If it needs a
  paragraph of scaffolding, the finding is not yet understood.
- **Where a claim is "these two renders should differ", say so with hashes**, not two
  screenshots that look alike: `shasum -a 256 render.png render-variant.png`.
- **Delete a reproduction when its finding closes.** The folder holds what is open; git holds
  what was.

### Where the exercise lives, and where the probes live

The corpora are fixtures; a finding's scaffolding is not. The line runs between the
**exercise** and the **probes**:

| document | goes | because |
|---|---|---|
| the exercise — a reproduction of a real design, with its `content.md`, `THEME.md`, reference image and renders | `data/markdown/tests-render/` | it outlives the finding: anyone can re-render it later against a new build |
| a probe — a few lines that exist only to show one claim, with the theme variant that isolates it | the finding's folder | it means nothing once the claim closes, and it deletes with it |

So a finding's folder holds its `README.md` and its probes, and points at the exercise by
path. Do not copy the exercise in — one location, cited.

If a probe turns out to be worth keeping after its finding closes, promote it deliberately:
`data/markdown/tests` is where documents go after they have gone wrong at least once.

### Two types, declared at the top

Every finding's `README.md` opens with `**Type: skills.**` or `**Type: code.**` — they are
read differently, and a reader who cannot tell which one they hold will act on it wrongly.

| Type | Asks | Written by |
| --- | --- | --- |
| **skills** | *Can an author get this result from the notes alone?* Authoring is done against `skills/` and `THEME_GUIDE.md` with `src/` unread, so the report describes what someone following the documentation actually gets | whoever is validating the authoring surface |
| **code** | *Does the implementation do what it says?* Free to read `src/`, cite modules and line numbers, and name a cause | whoever is investigating the pipeline |

The distinction is about the *evidence*, not the fix. A skills finding often resolves as a
code change and a code finding often resolves as a doc change; what differs is that a skills
report may not name a cause, because its author never looked. Do not read "the notes are
wrong" into a skills finding, or "the code is wrong" out of one.

### Every finding names its sources

A finding that cannot be re-run is an opinion. Open with a **Sources** table listing the
repo-relative path of every file the result was measured on, plus the command that rebuilds
them. `content.md` and `THEME.md` are the sources; the AST and the renders are generated
from them and are disposable.

State the date on every measured claim. Behaviour moves; an undated number cannot be told
apart from a stale one.

### Keep the report to what is open

Closed findings are **deleted, not struck through** — the report is a worklist, not a
changelog, and git holds the history. Two things are worth keeping when a finding closes:
a construct the exercise validated (that belongs in `skills/`), and a limit that turned out
to be intended (say so, so it is not re-filed).

**`skills/` and `THEME_GUIDE.md` describe what the tool is meant to do and what it
deliberately does not.** Never document a defect there, open or fixed — that is what
`findings/` is for, and a fixed bug left in the notes reads as a live limit forever.

## Enforced by `make check`

- Every test in every `tests/*_tests.py` `TESTS` list runs. Failures must match
  `tests/BASELINE.txt` exactly — a new failure fails the gate, and so does a
  baselined test that starts passing (delete its line; that is how a fix is recorded).
- The counts in `ratchets.txt` may not grow. Beating one means lowering it in the
  same change, so a ceiling only ever travels downward.
- The per-file line ceilings in `budgets.txt` follow a **different** rule. A budget
  is a PROMPT, not a verdict: if a file holds more than one concept, split it and
  lower the number; if it holds one coherent concept, **raise the number and record
  the reason**. If the file is already thousands of lines long, stop and obtain
  owner approval before adding code or raising its ceiling. This review requirement
  does not imply that the file must be split. Never pay for a needed line by deleting
  a comment — documentation is the cheapest thing to cut and the most expensive to
  lose.

Those three files, the `Makefile`, `scripts/`, and this file record what the project
guarantees. An agent may change anything the checks verify; changing the checks
themselves is the owner's call.

## Before finishing

Keep the change small and in one stage of the pipeline. Say what remains uncertain:
a green `make check` does not prove the behaviour is what was asked for. Layout
changes need a look, not just a pass — render one named sample before and after.

Write no dead code: no unused import, local, parameter, function, file or dependency, and
nothing written "for later" — code exists once something calls it. ruff catches unused
imports and locals; read the diff for the rest. Comments and docstrings are not dead code.

| Change affects | Required validation |
| --- | --- |
| Grouper structure, node types, annotations, splitting, glue, or detection | AST/grouper snapshot |
| Layout, measurement, drawing, fonts, colors, themes, or rendered samples | Render snapshot |
| Performance: a cache, a memo, fewer walks or builds | Both snapshots silent, plus timings — see *Measuring performance* |

Both snapshot oracles use the same derived scope: **every Markdown file under
`data/markdown/tests` and `data/markdown/tests-render`**. The grouper snapshot groups each one;
the render snapshot regenerates each one and renders it at both widths. Nothing renders from a
saved grouper AST — a render from one proves nothing about the grouper — and a file
outside those two fixture directories is intentionally outside the snapshot scope.

Use the applicable command—or both when both rows apply:

```sh
uv run python scripts/grouper_snapshot.py <dir>
uv run python scripts/render_snapshot.py <dir>
diff -rq <before> <after>
```

1. From the working tree and committed pre-change source, generate two independent
   `before` directories. Their `diff -rq` must be silent; this proves the snapshot
   is deterministic.
2. Restore or apply the change and generate the matching `after` directory.
3. Compare `before` and `after` with `diff -rq`. Inspect every reported AST or PNG
   difference and explain why it is intended; an unexplained difference means
   validation has not passed.

Capture both sides back to back so corpus edits are not mistaken for implementation
changes, and name the commit the `before` side is taken from: `HEAD` moves when the
owner commits mid-session, and "before my change" silently becomes "the last commit".
Run `make assets` in any fresh checkout or worktree before a snapshot: no font is
tracked, and the render snapshot refuses to start until every font in
`assets/fonts.lock` is present byte for byte. For AST comparisons,
inspect node-tree changes separately from annotation-flag changes, and both from
run changes: the runs file the grouper snapshot writes beside each AST records which
siblings grid together, which `to_dict()` leaves out. A single named
render is useful additional evidence, never a substitute for the snapshot corpus.

The render snapshot paints each page whole, unscrolled and without the window chrome.
A change to what the window draws per frame (the replay, the chrome, scrolling) also
needs window-sized frames compared at several scroll offsets and both pixel ratios.

Unchanged pixels mean the corpus is unaffected, not that nothing broke: a feature the
corpus does not contain fails silently in both snapshots.

**Stop and ask** if a test contradicts the implementation, if the change needs a new
public surface, or if the large-file review above applies.

## Measuring performance

Every performance pass so far has taught the same lessons:

- **Profile before choosing a fix, then count calls.** The cost was never where it
  looked like it was:
  - in the grouper, the same question answered again, not walks (now memoized, ADR-103);
  - in the generator, the NUMBER of trial builds;
  - in the renderer, repainting the whole document every frame (ADR-401).
- **Measure through the real pipeline.** `MarkdownGrouper.process()` with no
  arguments runs without the split criteria and detector the real run passes, so it
  groups differently and skews every delta. Go through `session.load_grouping_kit()`
  and `session.group_markdown`.
- **cProfile overstates call-heavy code.** Confirm a win in wall-clock time.
- **Noise within one session is a few percent.** Confirm a small win with repeated,
  interleaved runs (A, B, A, B), and report best-of-N. A win inside the noise is not
  a win.
- **A/B on one frozen read of the corpus.** The owner edits the corpus while you
  work. Load each document once, and run both variants in one process — the old code
  loaded with `git show` and swapped in — rather than two snapshots taken minutes
  apart.
- **Check a memo's hit rate before adding it.** Two were rejected on measurement:
  - a `_decide_group` memo, because nearly every key was distinct;
  - `id()` memos of functions that are cheaper than a dict lookup, which came out
    slower.
- **Key a cache on identity only for objects that are replaced, never edited, and
  hold a strong reference to them**, so a freed object's id cannot be reused.
  Examples: `render_metrics._WORD_FACES`, `render_picture.DocumentPicture` and
  `session.effective_width`.
- **Give work its lifetime.** In the window, everything is done once per one of three
  things:
  - the **document**: grouping, `document_min_width`;
  - the **width**: layout, placement, the recording;
  - the **frame**: the replay, the chrome, the scrollbars.

  Per-width work must never run per frame, and per-document work must never run per
  width.

## Decisions already made

`decisions/` holds one record per decision that could have gone the other way.
They are numbered by domain, and re-litigating one needs a reason.

| Number | Domain |
| --- | --- |
| 000 | whole project: architecture, structure, what the checks cover |
| 1xx | pipeline: grouper and detector contracts |
| 2xx | Markdown grouper: what the author's text means |
| 3xx | layout generator |
| 4xx | renderer and window |
| 5xx | `skills/` and theme meanings |
| 6xx | shells: CLI, wire, MCP servers, packaging |
| 7xx | what md2ui deliberately does not learn |

`head -n1 decisions/*.md` lists every title. Start at [ADR-000](decisions/ADR-000-architecture-and-structure.md) if you are
deciding where new code goes or about to propose a different shape.
