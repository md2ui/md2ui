# ADR-612: A backend expands includes, and answers clicks by changing data

**Status:** active (prototype)
**Domain:** CLI tools and shells
**Read when:** you register includes or click handlers on a `Conversation`, or tell it that an
include's data changed; change what `check`, `outline`, `layout`, `preview` or `show` read; or
are tempted to let a backend edit the agent's Markdown, or to give the agent a fragment tool.

How a backend registers them is `protocol/backend.md` (*Includes and handlers*). The code is
`includes.py` (the grammar, expansion, regions, the static folder) and `wire_includes.py`
(expanding on send, a handled click's redraw, a redraw on changed data).

## Decision

**An include is a line the server draws from the backend's data.** The agent writes
`{{cart}}` or `{{order BS-1042}}` on a line of its own; before the page is recorded, the
server replaces the line with the Markdown the backend's `expand(args)` returns. The log,
the ordinals, `showing`, `check` and the window all see the expanded page. The client is
unchanged: it is sent plain Markdown (ADR-601).

- **The spelling is a line**: exactly one `{{name args}}`, at the line's first column, with a
  blank line (or the document's edge) before and after, outside a code fence. A `{{…}}` inside
  text is never an include: inline braces are left to `variable-replacement`.
- **At the page's top level only.** A lone include line between list items or in a cell of a
  `:::` row is left as written, and `check` warns (`nested-include`): an include drawing a
  heading there would take the rest of the list, or the row's close, into its section.
- **The log keeps each include's region**, the lines it drew, with its line, so the source
  can be given back (`showing`'s `source`) and a region drawn again. A region is carried
  through the server's own edits (`mark`, a commit, a feed's tick, `patch`) by a line diff.
- **Every reader expands first**: the authoring server's `check`, `actions`, `outline`,
  `layout` and `preview`; the demo's `show` checks the page it sent. An include that cannot be
  drawn (an unknown name, args that do not read, an expander that raised) is an `error`
  (`unknown-include`), naming the include and the error's class. On a server with **no**
  includes nothing is expanded and a lone `{{name}}` is a `warning`: there it is more likely
  template syntax the agent is writing about than an include it was never offered.
- **A failure draws its backend's line or nothing, never braces.** An include that cannot be
  drawn, on send or on any redraw, draws as its region the failure line the backend registered
  for it (`failure=`, in its users' language) in the theme's muted tier; without one, an empty
  region. md2ui writes no words of its own on a page: it does not know the page's language. It
  stays the include's region, so the next redraw replaces it once the data recovers, and the
  region keeps why (`Region.failed`), so `check` and the digest still tell the agent. The
  error's text goes to stderr only.
- **What an include drew is the backend's.** An agent's `patch` or `mark` whose edit touches a
  region is refused, naming what to do instead: change the include line and re-send, or let the
  backend's data change. The next redraw would silently undo the edit, and applying it to the
  source has no source line to edit. An edit wholly outside keeps the regions; the server's own
  edits (a commit, a feed's tick) are not refused.
- **Going back draws the includes again**: `show(message_id=…)` re-sends the page's source, so
  each include is drawn from the data now, and its result names them (`redrawn`).
- **The agent learns them from the server**: `guide("includes")` lists each with its args and
  description, and `guide` names `includes` only on a server that has some.
- **For evals, includes can be static**: an `includes/` folder beside the theme, one Markdown
  file per name, whose body every call of that name expands to.

**A click handler changes data, never Markdown.** A backend registers handlers by `agent:`
slug: `fn(params) -> the names of the includes whose data changed`, or `None` for "not
mine". In `Conversation.receive`, after `verify` and the commit, a handled click redraws
those includes' regions on the page shown and sends **one** replacement (`r`), even when
nothing changed, so the same button can be pressed again. It is never queued for the agent.
In any state, the window is told the click is answered (`u`, to the connection that numbered
it): the agent was never handed it, so its listening cannot answer it.

**A backend whose data changes with no click says so** (`Conversation.changed(names)`), and
the server redraws those regions on the page shown by the same path, as one replacement. This is
the same redraw with another trigger: the same regions, ids and digest, and no new writer of the
Markdown.

- **Nothing to send, no frame.** When none of the names draws differently on the page shown,
  nothing is sent and no id is taken: unlike a handled click, no button needs releasing, and an
  identical replacement would clear the window's unanswered local state. No state frame
  follows.
- **Only the page shown**, including a page the backend showed (ADR-614). A page left is not
  redrawn; brought back, it draws its includes from the data then.
- **While a message streams, nothing is sent**: the stream is the page shown. The check is made
  where the frames are sent, under the send lock, so a stream or a page the agent sent
  meanwhile wins.
- **With a feed on the page**, the redraw and a tick take the log's lock in turn; the tick
  resolves the feed's page through the redraw and writes its values there. A fed slot inside a
  region is the backend's to redraw.

**The agent still knows.** Each handled click, and each redraw with no click, is one line of a
digest (`Conversation.take_handled`), handed over with the next thing the agent hears; the
demo's listens and tool results carry it as `handled`. A redraw's line names only the includes
that drew differently, and consecutive redraws are one line naming the last message. **Ids
survive**: the replacement is the server's, so `MessageLog.head` resolves the id the agent
carries through it, as through a feed's tick (ADR-608).

**A handler's failure goes to the agent.** A handler that raises leaves the click to the agent,
and the digest says the backend failed on that action, with the error's class and never its
text. The user sees no error: the agent, who now holds the click, answers it in words.

## Why

- **Correctness, not only tokens.** In a shop's conversation most replies are an include line,
  and every price, total and status on them comes from the shop's data. An include takes the
  agent out of the path of a figure; re-typing is how a figure drifts (ADR-611).
- **One writer of the Markdown stays one** (ADR-404). The agent's Markdown holds the include
  lines; what they draw is the backend's data. Every word outside a region is unchanged by
  construction, and an agent's later re-send carries include lines, not stale figures, so
  there is no lost update.
- **A click that only changes data should not cost a turn**, and a stepper the agent answers
  takes a turn per tap.
- **A page on screen must not go stale.** An order's status, or a button it no longer offers,
  changes while the user looks at it; the agent hears it because a button it might point the
  user at can be gone.
- **`check` must see the real page**, or an agent verifies placeholders, and the cheapest
  check (text-only) is the one every reply passes through.

## Considered and rejected

- **Handlers that patch any Markdown**, under ADR-611's edit check. A second writer of the
  agent's words; kept as a documented fallback, not built.
- **Fragments the agent declares** (ADR-611 rejected them): they save tokens, never turns.
  Includes are the backend's, with data the agent never sees.
- **Inline includes.** They would take `{{name}}` from `variable-replacement`, whose values
  the client fills.
- **Expanding a streamed message.** Whether a line is an include depends on what follows it (a
  `:::` later in the run makes it a cell), so the stream would have to hold text back, and a
  page streamed would differ from the same page sent whole.
- **md2ui's own words for a failed include.** It does not know the page's language; a backend
  that wants the user told registers its line.

## Constraint created

- **Only content inside an include can be answered by a handler.** A stepper the agent typed
  by hand still wakes the agent (or the agent `mark`s it). A handler may also answer with a
  new page of its includes, never an edit of the agent's page
  ([ADR-614](ADR-614-a-backend-may-answer-a-tap-with-a-page-of-its-includes.md)).
- **A streamed message is not expanded**: its chunks are sent as written, and `check` warns on
  an include line it holds (`streamed-include`: send the page whole).
- **A client accepts `u` on any state** (`protocol/README.md`, *Lifecycle*), since a handled
  click is answered whatever the agent is doing.

## Reconsider when

- `variable-replacement` is decided: its spelling must stay clear of a lone `{{…}}` line.
- A handler needs to answer *and* wake the agent ("out of stock" needs words).
- Redraws with no click arrive faster than a window should repaint: they are sent as they
  come, unpaced, unlike a feed's ticks.
