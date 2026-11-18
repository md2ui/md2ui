# ADR-605: Every package points at an md2ui checkout; none holds md2ui code

**Status:** active (prototype), until md2ui is installable from PyPI
**Domain:** CLI tools and shells
**Read when:** you build or change a host package (the Claude Desktop extension, the Claude Code
plugins, the local OpenAI plugin for ChatGPT Desktop and Codex), package md2ui for another host,
or wonder why a fresh install previews in the wrong fonts. The packages, their launcher and their
tests live in their own repository, md2ui-plugins; setup steps are in its README.

## Decision

**Each host package runs md2ui from the user's checkout, after `uv sync`.** A package
holds host metadata, thin skills that point at `guide`, and at most a launcher. It never holds a
copy of md2ui's code or notes. The checkout and the theme are the package's settings, wherever
the host supports settings.

**The Claude Desktop extension has a launcher; the others do not.**
- **Desktop** starts an extension with its own `python3`, and a GUI app does not inherit the
  shell's `PATH`. So the extension's launcher checks the checkout, finds `uv`, warns about theme
  fonts missing on disk, and then replaces itself with the same command a person would run.
- **Hosts started from a shell** (Claude Code, Codex, ChatGPT Desktop's local plugin) run
  `md2ui.mcp_demo` over stdio directly. An installed plugin cannot reach outside its own folder,
  so a launcher would have to be copied into each.

**A font comes only from the lock, and only with a person's consent or `--fetch`.** A checkout's
setup (`make assets`, or a package's user-invoked setup skill) fetches the files the theme names;
a server started with `--fetch` fetches a locked font it lacks on first use, verified against
`assets/fonts.lock`, into the per-user cache. A launcher only warns. A package may ship setup as
a user-invoked skill, never one the model invokes by itself.

**Packages are built and installed locally, and published nowhere.** A built bundle (`.mcpb`) is
a build output and is never committed.

## Why

- **One copy of the code: the one the developer is already running.** Until md2ui is
  published, a checkout is the only md2ui a package can name; a bundle with its own copy would
  drift from it.
- **A launcher is the only way to fail clearly where the host gives no shell.** Run directly, a
  missing `uv`, a wrong directory or absent theme fonts show up as a server that never starts,
  or a window in the wrong fonts. The launcher says which, on stderr, where the host logs it.
- **A font fetch stays visible and bounded.** Fonts are not committed; only a locked file, from
  its pinned source and with its checksum, is ever fetched, and only where fetching is on.
- **The skills stay thin** so the notes exist once, in `skills/`, served by `guide`.

## Constraint created

- **The launcher stays standard-library-only and Python-3.9-safe**, and never writes to stdout
  outside `--dry-run`.
- **A package's tool list is its server's.** md2ui-plugins' packaging tests compare them, so a
  tool added to a server here is listed in its packages too.
- **A package passes `--fetch` only for a local install** (ADR-602). A hosted server never
  does.

## Reconsider when

- **md2ui is distributed beyond its developers.** The pipeline's data already ships in the wheel
  (`session.resource_root`), so packages can run a published md2ui instead of a checkout, and
  launchers give way.
- **A package runs on Windows or Linux.** The Desktop extension declares `darwin` only, because
  the window has only been run there.
