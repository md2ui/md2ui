# ADR-600: The CLI runs once and exits; the app owns every watcher

**Status:** active
**Domain:** CLI tools
**Read when:** you are adding a command, a flag or a watcher; changing how a shell hands the
grouper's tree to the layout; or wondering why `md2ui` and `md2ui-app` both exist.

## Decision

md2ui's shells share one pipeline sequence, and each shell serves one audience:

- **`md2ui`** (`main.py`) is for agents and scripts. Every verb takes the Markdown document
  itself, runs the pipeline once, reports what it wrote or found, and exits. There is no
  watcher, no stdin and no window. The verbs and exit codes are in `main.py`'s docstring.
- **`md2ui-app`** (`app.py`) is for people: the window, the key bindings and live reload. It is
  the **only** module that watches a file or loops on input.
- **`session.py`** is the pipeline from start to end: theme, typefaces, grouping, layout,
  placement and the headless paint. It is written once, and every shell calls it. That includes
  the MCP and wire servers (ADR-601, ADR-602): each request there runs once and returns, like a
  verb.

The import contracts in `pyproject.toml` hold the shape. The pipeline never imports a shell or
`session`, and `main` and `session` never import `app`.

**The grouper's tree reaches the layout in memory, through its dict form.**
`session.prepare` passes `to_dict()` to the layout's loaders. The tree never goes through a
file, and the live tree is never handed over.

## Why

- **The two audiences want opposite things.** A person wants a window that stays in step with
  the file. An agent wants a command that ends and says what it wrote: a command that waits
  hangs the agent that ran it. One program serving both served neither.
- **Taking the `.md` directly removes the intermediate file** and the "rebuild the AST first"
  step. Every run regroups, so a render can never show stale structure.
- **The dict, not the live tree.** The live tree and the tree rebuilt from its dict differ on
  almost every corpus document: some fields are not serialized and others change shape. Every
  reviewed render, snapshots included, was drawn from the rebuilt tree, so handing over the
  live one would move pixels nobody reviewed.

## Constraint created

- **A new command is a verb of `md2ui`, and it ends on its own.** Anything that waits belongs in
  the app or a server: a watcher, a prompt, a loop.
- **A pipeline step is added to `session.py` once, not to one shell.** A copy kept in one shell
  is how the window and a screenshot come to disagree.
- **The render snapshot drives `md2ui render` on the `.md`**, so it covers the CLI's whole path.
- **Handing over the live tree is a behaviour change, not a refactor.** The divergence must be
  resolved first, then reviewed with a render snapshot.

## Reconsider when

The dict form is made faithful to the live tree.
