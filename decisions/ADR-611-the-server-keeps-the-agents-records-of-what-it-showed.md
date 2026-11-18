# ADR-611: The server keeps the agent's records of what it showed, and edits them in place

**Status:** active
**Domain:** CLI tools / demo shell
**Read when:** you change `history`, `showing`, `patch`, what a heard click reports, the
`<!-- from: …; fresh: … -->` comment, or the `image-ratio` issue; you are about to add a separate
tool for inserting or deleting part of a page; or you are about to make an agent remember
something about its own pages.

## Decision

**The agent owns the state, and the frontend holds none (ADR-601). The server reports what it
already records about the pages the agent sent**, so the agent's context does not have to keep
that record by hand. The conversation's log holds every page's Markdown and when it was sent;
`wire_records`, `wire_sections` and `mcp_demo_records` expose it.

- **`history()` lists the pages this session sent**, newest first, one row per page however
  often it was re-sent. Any id a page had still names it. The log lives in memory: after a
  restart the list starts empty, an old id is gone and never reused, and `history()` says so.
- **Freshness is written by the agent, on the comment it already writes**:
  `<!-- from: git status; fresh: 5m -->` under a section's heading. `show` and `showing` of an
  earlier page report the sections past their limit. The server only reports: it never
  re-reads, fetches or refuses (ADR-608's line). A section with no `fresh:` is never reported.
- **A heard click names its section** and that section's age. The heading is the agent's own
  Markdown, so this adds no client string.
- **A section is addressed** by its `{#id}` or its heading's words.

**`patch` edits the server's copy and sends a replacement**, as `mark` does (ADR-601). It is one
verb with anchors:
- replace a section (`section=`);
- add whole sections after or before one (`after=`, `before=`), at the anchor's level;
- remove one (`section=` with empty `markdown`);
- replace exact text (`replace=[{old, new}, …]`), applied together or not at all, each `old`
  found once on the page and on one line, with no heading added or removed.

**Every edit is checked the same way: every word outside the edit comes out unchanged.** Every
refusal names the call to make instead. A page with no headings refuses `after` and `before`,
and says to `show` it. `patch` is not idempotent, and its annotation says so, so a host never
repeats it for the agent.

**A missing image ratio is one small fix, made before the user's next click.** The
`image-ratio` warning names the cheapest fix: a ratio on a run's first picture, which sets the
whole run (ADR-301). With `patch(replace=…)` that fix is one short call. It is a warning, and like
every other warning it stops `show` listening (ADR-602), so the agent fixes the page while it
still has the turn.

## Why

- **Records kept in the agent's context are lost.** Compaction and a server restart erase them,
  and agents re-ran commands and rebuilt whole pages only to decide whether something was
  stale.
- **Re-typing unchanged sections is how a figure, link or tick drifts.** Adding a section was the
  one common edit that forced a full re-send.
- **One verb, one new word.** An agent that knows `patch` learns `after`, and `before` for the
  top of the page; removing is "replace with nothing". The hint is effective in the tool's own
  description, far more than in its parameters or the notes.
- **`replace` reaches what `section` and `x` cannot**: a picture's URL, one word in a long
  section, a section whose heading has no words.
- **The safety check is the existing one.** No edit can change more than it names.

## Considered and rejected

- **Fragments** (`show(markdown, fragments=…)`, expanded by name later). They save tokens, never
  turns, and a server that wants them builds its own includes.
- **The window resolving "Back" by itself.** The frontend holds no state.
- **A replacement carrying extra sibling sections.** The agent would re-type the anchor section,
  the drift `patch` exists to prevent.
- **A `section="+name"` spelling.** It puts a verb into a name and still does not say where.
- **Separate `insert` / `remove` tools.** More tools to choose between for one operation.
- **A ratio inferred when a picture loads.** Ratios are authored, never resolved: the layout would
  jump on load, and `check` and the window would disagree.
- **`show` listening past the ratio warning**, so the user's clicks need not wait. Agents did not
  fix the ratio once they were not stopped: their next turn was the user's click, and they
  answered it. Stopping on the warning is what gets the fix made.
- **The ratio as a note instead of a warning.** A crop nobody chose is worth fixing; the warning
  keeps that weight without holding the user.
- **Fix handles on issues, invented section ids, page-level defaults.** Each is new vocabulary;
  the first picture already sets the run, and `replace` reaches any text.
