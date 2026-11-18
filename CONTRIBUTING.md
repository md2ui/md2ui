# Contributing

md2ui is experimental: anything may change between 0.x releases.

## Set up

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync        # create .venv and install md2ui with its dev tools
make assets    # fetch the fonts the themes name: none is in the repository
make check     # the gate: run it before you open a pull request
```

In a checkout, run the README's commands through `uv run` (`uv run md2ui render doc.md`,
`uv run md2ui-app doc.md`, `uv run md2ui-wire doc.md`). md2ui then reads
`skills/`, `THEME.md` and `assets/` from the checkout itself instead of the package's
`md2ui/shipped/`. Add a dependency with `uv add <pkg>`; never edit `pyproject.toml` by hand.

`AGENTS.md` is the map of the code and its rules, for people and agents alike. A pull request
merges when `make check` passes and the change is explained.

## Develop

```sh
make check       # THE GATE: tests vs tests/BASELINE.txt, import contracts,
                 # per-file budgets, ratcheted lint and type counts
make check-fast  # same minus type checking: inner loop only, not the gate
make fix         # auto-fixable lint only
```

Every other target is in the `Makefile`, each with a comment.

| Path | What it is |
| --- | --- |
| `AGENTS.md` | How to work in this repo: read it first if you are making changes |
| `decisions/` | ADRs: decisions that could have gone the other way, grouped by domain |
| `THEME_GUIDE.md` | Every `THEME.md` key |
| `src/md2ui/` | The pipeline (grouper, detector, generator, renderer) and the shells: the CLI, the app, the MCP servers, the wire |
| `skills/` | How to author Markdown for md2ui, written for the LLM that writes it and served by the MCP `guide` tool |
| `protocol/` | The wire protocol: spec, JSON Schemas, golden frames, the gRPC `.proto`, and the backend guides |
| `tests/` · `scripts/` | One `<feature>_tests.py` per feature; one-purpose CLIs, each described by its module docstring |
| `data/` | The corpora: real LLM responses, regression documents, samples |

The TypeScript client library is a separate repository,
[md2ui/md2ui-ts](https://github.com/md2ui/md2ui-ts); this project is its reference
implementation. The host plugins are in [md2ui/plugins](https://github.com/md2ui/plugins).

## Fonts in a checkout

No font lives in the repository. `make assets` downloads each one from its source into
`assets/fonts/`, checked against the SHA-256 in `assets/fonts.lock`; `make check` and the
render snapshot refuse to run until every locked font is there, byte for byte.

**Adding a font.** When the root `THEME.md`, or a theme under `data/markdown/tests` or
`data/markdown/tests-render`, names a font file the lock lacks, `make check` reports it
`missing`. Lock it:

1. Find the file. For a Google Fonts family, open
   `https://fonts.google.com/download/list?family=<Family>` (JSON after a first line of
   `)]}'`); in `manifest.fileRefs`, the entry whose `filename` ends in the file's name has
   its `url`, on `fonts.gstatic.com/s/<family>/vNN/`. Otherwise use the project's release
   zip, and the file's path inside it.
2. Add an entry to `assets/fonts.lock`, with the SHA-256 of the file you downloaded
   (`shasum -a 256 <file>`):

   ```toml
   [[font]]
   file = "Inter_18pt-Regular.ttf"
   sha256 = "<64 hex digits>"
   url = "https://fonts.gstatic.com/s/inter/v20/<...>.ttf"
   member = "<path inside the zip>"   # only when url is a zip
   licence = "OFL-1.1"
   ```
3. Run `make assets`, then `make check`.

Lock the bytes the snapshots should use: a newer version of the same font is a different
file, and it moves pixels.

A theme of your own that names a font the lock does not hold needs the file at the path the
theme names; a relative path is read beside the `THEME.md` first, then from the working
directory. Find it as in step 1, keep the family's licence beside it (`OFL.txt` for Google
Fonts), and check with `uv run md2ui render`, which then logs no `[fonts] not found`.

## A change that moves pixels or structure

`AGENTS.md`, *Before finishing*, says which snapshot a change needs: the grouper snapshot for
structure, the render snapshot for anything drawn. Run it before and after, and explain every
difference in the pull request. A layout change also needs a look: say which sample you
rendered.

## A change to `skills/`

`skills/` is what agents read to author for md2ui, and one line can change what they write.
The owner measures each change to it with the eval suites before merging (`evals/README.md`;
`evals/example/` shows a suite's shape). The suites themselves are private, and a run costs API
calls, so say in the pull request what the change is meant to do, and expect that measurement
to come before the merge.

## Reporting what you found, proposing what you want

The owner works with two kinds of record, kept privately. Their procedures are public, and a
GitHub issue is the way in from outside:

| You have | Open an issue with | How the owner works it |
|---|---|---|
| Something md2ui does that looks wrong | the **Finding** template | `findings/README.md` |
| A feature or a design change you would like | the **Proposal** template | `proposals/README.md` |

A finding states its type (*skills*: what an author gets from the notes alone; *code*: what the
implementation does), the files it was measured on, the smallest document that shows it, and
the date. A finding that cannot be re-run is an opinion.

## License

By contributing you agree that your contribution is licensed under the MIT License (`LICENSE`).
