# ADR-000: Architecture and structure

**Status:** active
**Domain:** whole project
**Read when:** you are deciding where new code goes, wondering why `make check`
exists, about to add to one of the large files, or about to propose a different
shape for the repository.

This file records **why the repository is shaped this way**. It holds no line
counts, file sizes or module counts: `budgets.txt`, `ratchets.txt` and `git log`
hold those, and they are checked.

---

## The architecture: a compiler, in layers

md2ui is a compiler. One shared data model is threaded through ordered stages,
each annotating it and handing it on:

```
app · main · session   the shells: window + live reload, the one-shot CLI, the run they share
  ↓
render               measurement + painting          ─┐
generator            layout decisions                 │  MarkdownGroupNode
grouper              AST construction + annotation    │  → LayoutNode
detector             data point detection            ─┘  → LayoutBox
  ↓
primitives · utils   theme, the layout parser, inline text; leaf helpers
```

**Dependencies point one way and nothing imports upward.** The direction is not a
convention: it is declared as import contracts in `pyproject.toml` and a violation
fails `make check`.

### Layers, not vertical slices

Features here cut across stages by design — colour rotation is decided in the
grouper, configured in the theme, and applied in the renderer. Organised as
vertical feature slices, those slices would import each other on day one. So the
repository is organised by **stage**, and a feature is a thread running through
several of them.

## Structure: where code goes

`AGENTS.md` is the routing table and carries the current answer per case. The
principles behind it:

- **A module has an admission rule statable in one sentence.** If an agent adding
  something new cannot tell whether it belongs there without reading the file,
  the module has no boundary, and it grows without limit.
- **The earliest stage that can see a fact owns it.** Later stages read what was
  stamped; they never re-derive it — [ADR-100](ADR-100-grouper-annotates.md).
- **A quantity two stages both need gets its own module below both.** A shared
  middle is a module, not a duplication — [ADR-400](ADR-400-one-normalization-point.md).
- **Big files are a prompt, not a verdict.** A file that is genuinely one concept
  is allowed to be long; splitting a coherent file to satisfy a number erodes the
  code to protect the metric. Each ceiling in `budgets.txt` carries its reason.
  Three questions decide it, beyond the admission rule above: does the file grow
  in proportion to something external and bounded — one field per THEME.md key —
  or because it is where an agent already was? Is it read by lookup, or must it
  be read whole? Does it mix kinds — the seam that matters is schema-versus-logic,
  since splitting by domain breaks the admission rule by construction. A schema
  or a table answers all three and is accepted long; a file that grew by
  accretion answers none.

## Design principles

**Functional core, imperative shell.** A stage is a function of its input; the
shell — CLI, window, live reload — is the only place that touches the outside.
Where a stage reads state threaded through an instance, that is a known cost
rather than a style preference: such a stage cannot be split, tested in pieces,
or reasoned about locally.

**State that two modules share is one object, passed as an argument.** Not a
module-level global: when a global's writer and its readers end up in different
modules, the write binds a *new* global in the writer's module and the readers
keep the stale default — no error, and nothing static sees it. This is why
display settings and id counters are each a single object threaded through.

**Documentation lives at the smallest scope that can hold it.** A field comment
beats a module docstring beats `AGENTS.md` beats an ADR. Every prose surface must
be either derivable from the code — then delete it, the reader can run the command
— or mechanically checked. Prose that is neither goes stale without anyone
noticing.

## Verification: output snapshots, not the test suite

**A change that is supposed to preserve behaviour is verified by a byte-identical
output snapshot.** The test suite is not sufficient: it can stay green over a real
regression in what is drawn. The snapshot scripts and when to run each are in
`AGENTS.md`, under *Before finishing*.

This is why the snapshots must stay deterministic and why their variants matter:
a corpus rendered entirely at default settings cannot detect a broken non-default
flag, so a variant that does not differ from the plain render of the same sample
proves nothing.

### What the checks do NOT cover

Stated precisely, because a green gate means less than it appears:

- **The interactive window's loop.** `scripts/viewport_snapshot.py` covers what
  the window *draws* — the replayed document, the chrome, scroll offsets — but
  the GLFW loop, key bindings and live reload are exercised by no check. If you
  touch the shell, run it.
- **Anything derived from `__file__`.** A module-relative path breaks when the
  file moves, and no test, contract or linter sees it. Anchor on a marker (walk up
  to `pyproject.toml`), never on a depth.

## The feedback loops

Every mechanism pairs a direction signal with a mechanical check, so an agent can
do the obvious thing and have the repo confirm or correct it:

- the test baseline makes "I broke it" distinguishable from "it was already broken";
- `AGENTS.md` routes an agent instead of leaving it to infer;
- the import contracts make a layering mistake fail rather than be remembered;
- `budgets.txt` makes code concentrating in one file for no reason visible;
- `decisions/` records once a choice that could have gone the other way.

## Deliberately not adopted

Recorded so they are not re-proposed.

- **Vertical slices**, with an independence contract — see *Layers, not vertical
  slices* above.
- **"Duplicate rather than share"** — inverted here. Duplication *is* the
  measure/draw divergence bug family; one normalization point is the fix.
- **mypy strict / ruff `ANN`** — pyright standard, deliberately. Strict produces
  volume, not signal, on this codebase.
- **CODEOWNERS, `.github/`, PR templates** — near-zero value at this size.
- **Explicit state machines** — nothing here is one. The grouper's phases are a
  fixed sequence, which is a pipeline; naming it a state machine adds vocabulary,
  not signal.
- **A property-based testing campaign** — the oracle here is real documents
  rendering byte-identically, and generated inputs exercise cases nobody has. Two
  or three stated invariants fit; a framework does not.
- **`__all__` and public-API ceremony** — the import contracts already restrict
  interaction paths, and they do it *across* modules, which `__all__` cannot.
- **Assertions as scattered validation** — an invariant belongs at a stage
  boundary, where violating it violates [ADR-100](ADR-100-grouper-annotates.md).
  Elsewhere the snapshot is the stronger contract and the assert is noise.
- **Migrating the test runner to pytest** — the `TESTS` lists plus
  `tests/BASELINE.txt` are what make "already broken" distinguishable from
  "I broke it"; the migration risks the gate to gain familiarity.
- **A ceiling on the largest single function**, beside `budgets.txt`. File size
  answers "is code piling up here for no reason", which is the failure the budget
  exists for. A unit ceiling would enrol deliberately-whole procedures — the
  window's loop, the grouper's separation walk — and forbid growth nobody was
  attempting. The three questions above separate healthy long files from
  accreted ones; no number does.
