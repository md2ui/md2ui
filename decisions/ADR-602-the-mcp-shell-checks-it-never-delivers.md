# ADR-602: The MCP shells: authoring checks and never delivers; only a local demo delivers and holds the turn

**Status:** active (prototype)
**Domain:** CLI tools and shells
**Read when:** you add an MCP tool or resource; run md2ui inside a server; wonder why a
server-side preview shows placeholders; run md2ui as a live demo with an agent; or are tempted
to add a delivery tool to the authoring server.

## Decision

### The authoring server checks; it never delivers

**`mcp_server.py` is a shell over `session.py`, speaking MCP over stdio.** Every request runs
once and returns, like a CLI verb (ADR-600). It never watches a file, opens a window or loads
the app.

**It lets the agent check its own Markdown: issues, targets, structure, layout and a preview,
plus the authoring notes through `guide`.** Delivery is a backend's, over the wire (ADR-601).
Every output is sized for an agent's tokens.

**The cold start is the instructions and the tool descriptions**, because they are the only text
every client shows an agent. They say that writing for md2ui is writing the reply, and that
Markdown is harmless: nothing in it runs, and a click comes back as a sentence, never as a
command. md2ui names no connector and no backend tool; what the agent fills its channel with is
its own business.

**The notes are layered by cost**, since everything a tool returns stays in the agent's context:
- the core note is always read;
- section patterns are read one at a time;
- whole pages are read only when writing a whole page, from the corpus, never copied.

`guide` is a tool and not only a resource, because a client may leave resources for the user to
attach.

**A server fetches nothing by default** (`utils/fetch_policy.py`). `build_server` turns remote
fetching off for the process, and every fetch site obeys it: content images, theme
backgrounds, style images and theme fonts. Fonts come from files installed with the server. The
theme is the one the server was started with, never a path a model passes.

**A local install may fetch.** Started with `--fetch`, which packaging sets at launch and never
a tool argument, a server fetches as its window does. `preview` then waits for its pictures and
declares itself open-world. A hosted server never takes `--fetch`.

**stdout is the protocol.** Every tool call runs with stdout sent to stderr; one stray line from
the pipeline would corrupt the stream.

### The demo server delivers, locally

**`mcp_demo.py` is a second MCP server, for a live demo on one machine.** The agent answers in
md2ui Markdown, the answer appears in md2ui's window, and the user's clicks and prompts come back
to the agent. It is assembled from what exists and adds no wire rule of its own:
- the authoring tools (`build_server`);
- a conversation served on loopback over the reference binding (ADR-601);
- the window as that conversation's client, launched on the first `show` as a child process
  whose output goes to stderr.

Its own tools send a reply, listen, read back what was shown, edit it in place (`mark`,
`patch`, ADR-611), and feed values (ADR-608). Each result carries the authoring issues and its
own next step, so the agent needs no separate `check`.

**The window is a display for the same replies as the chat.** The agent chooses each reply's
form: a UI, a plain answer such as a plan, or both. Nothing has to be structured to be shown.

**The agent holds its turn.** An MCP server cannot start a turn, so the window is heard only
while a wait is open. The instructions state the loop once, as a table of what a listen can
return and what to do. The agent ends its turn only on `closed`, or when the user asks in the
chat.
- **Listening is part of the reply.** `show`, `mark` and `patch` listen after replying, under the
  common host cut on a tool call, and return what the user did. That also hands over whatever
  queued while nobody listened.
- **A page that is about to change is not listened to.** That is an answer with an issue the
  agent will fix because the page draws wrong. A note does not stop listening, and neither does
  a missing image ratio, whose page draws correctly on the default crop.
- **A short answer listens a short grace, extended while the user types**, up to a cap, so a
  reply being written is waited for and a field left open cannot hold a turn.
- **A wait cut by the host** is retried, never read as the window closing.
- **When the agent does stop**, the window tells the user to say "check md2ui" in the chat.

**Going back re-sends; it never rebuilds.** The server keeps every page of the session in
memory, and `show(message_id=…)` sends one again exactly.

**A static bar moves by its key.** `mark(message_id, key=…, value=…)` edits the server's own copy
of the Markdown, keeping the author's spelling, and sends an ordinary replacement.

## Why

- **The server knows the content and its layout shape; the client owns fonts, assets and
  images.** A server preview is optional, for when the agent thinks it necessary.
- **A fetch from a server is a security question, not a rendering one.** An image URL a model
  wrote would become a request from inside the server's network, or a local file read.
  Switching fetching off at the source is simpler and safer than filtering URLs.
- **A local plugin is different.** It runs on the user's machine, as the user, beside a window
  that already fetches every picture, and its agent can fetch any URL itself. Refusing protected
  nothing there, and cost the agent the one look that catches a wrong picture: a caption over a
  placeholder can read right while the real picture shows something else.
- **Keeping delivery out of the authoring server keeps it safe in any backend.** It has nothing
  to deliver, so it holds no conversation and opens no socket.
- **The demo is the whole product loop, runnable locally.** The agent writes, a frontend renders,
  the wire carries clicks back, and the agent decides state. Nothing is demo-only except its
  location: the frames, verification and sentence are a real backend's.
- **Agents stop listening unless listening is the reply.** Tool texts that tied the window to
  "structured" answers made agents end their turn after a plain one, and clicks then queued
  unheard. A rule in the descriptions alone was not enough.
- **Re-sending and editing in place beat regenerating.** Re-typing an unchanged page is how a
  figure, link or tick drifts, and it costs tokens and turns.

## Considered and rejected

- **Many whole examples served by default.** Each costs a lot of context for the rest of a
  conversation, gets copied rather than composed, and goes stale unless the snapshot corpus
  holds it.
- **Filtering URLs instead of turning fetching off.** More surface, same risk.
- **A short wait everywhere.** It costs a model step per timeout. The long default stays where
  hosts allow it, with a retry on a transport cut.

## Constraint created

- **A new fetch site asks `fetch_policy`**, or a server will fetch through it.
- **A tool is one-shot and quiet.** It runs through the shell's runner and returns something
  sized for an agent to read.
- **A delivery tool never lives in `mcp_server`.** A shell that delivers wraps `build_server`, as
  the demo does.
- **The demo is local only.** The socket binds loopback, and the window is a child process with
  a per-launch bearer secret. Serving others needs a real backend with authentication.
  The demo mints the secret, unless the process that starts it chose one in
  `MD2UI_WIRE_BEARER`: a launcher driving its own window (`--no-window`, the live eval harness)
  cannot learn a minted one. That launcher controls the server anyway, so the boundary is
  unchanged, and any other local process still gets a 403. The launcher makes a fresh random
  value per run, never one written in a config file; a value too short to trust
  (`LAUNCHER_BEARER_MIN`) is ignored and the demo mints its own.
- **A child process never inherits stdout.**
- **The pipeline never imports a shell.** Two import contracts in `pyproject.toml` say so: one
  for `app`, `main` and `session`, one for the MCP servers, the wire, `check` and the `app_*`
  modules.
- **A preview needing real images on a hosted server** gets an allow-list of hosts in
  `fetch_policy`, never fetching switched on:
  - hosts its operator names at launch, reached by name;
  - re-checked after every redirect;
  - never loopback, private or link-local addresses;
  - size and time caps, and no cache shared between users.

## Reconsider when

- **A host can deliver a server event to an idle agent.** The turn would then no longer need to
  be held.
- **A host caps a turn's length.** One long turn whose context keeps growing is the demo's cost.
