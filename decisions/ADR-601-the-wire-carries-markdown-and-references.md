# ADR-601: The wire carries Markdown and references; the server says what the agent is doing

**Status:** active (prototype; the spec is `protocol/`)
**Domain:** CLI tools and shells
**Read when:** you connect md2ui to a backend or a frontend; add a frame, an event field or a
binding; make something newly clickable; change the server's socket defaults; or wonder why a
prompt is the one client string that reaches the agent.

The frames, keys, limits and lifecycle are `protocol/README.md`. A backend's side, including the
reference binding's security defaults, is `protocol/backend.md`. This record keeps why.

## Decision

**A server sends a frontend plain Markdown and nothing else.** No font, asset, image, AST or
layout travels. The client runs the pipeline and gets its fonts and assets its own way. The
server knows only the content and the layout shape.

**THEME.md lives on the server.** There is one file, so a server `preview` draws with exactly
the theme the user sees. How a client receives it is the client's way, never a wire frame.

**An event names a target by ordinal, and the server re-derives the rest.** `x` is the target's
position among the message's actionable targets in document order
(`render_actions.action_targets`). The server resolves `(m, x)` against its own copy of what it
sent. The kind, action, params and label come from there. The client adds only the value it
asks for: a checkbox's state, or a slider's value inside its authored range. A `link` or an
`anchor` is the client's business and never travels (ADR-404).

**The agent receives a sentence built from its own Markdown**, never a client string. The one
exception is a **prompt**: what the user typed into the frontend's own field, handed over
verbatim and labelled as the user's words, never inside a built sentence.

**The server says what the agent is doing**: listening, working on the last input, or idle.
The backend derives the state from moments it already sees, and the agent never writes it. (Words for the client's chrome may ride the state frame:
[ADR-613](ADR-613-the-state-frame-carries-words-for-the-chrome.md).)
The window blocks input only while the agent works. **Listening again releases the buttons the
agent was handed**, by their event `q`s, sent to the connection that numbered them.

**A replacement (`r`) is the agent answering on the same page.** It keeps the scroll, and a
client keeps its unanswered local state wherever the replacement left the target unchanged.

**Transport is a binding, not part of the contract.** The reference binding is one WebSocket
endpoint (`wire_server`), secure by default. gRPC is a mirror: `protocol/md2ui.proto` fixes the
field numbers, with no server. SSE plus POST stays in the spec, unbuilt.

**The agent's effort stays on reasoning.** It writes only the Markdown answer. The backend does
the framing, ids, hashes, verification, state and, through a tool, state edits.

**The server fetches nothing, and the window is a client like any other.** A URL a model writes
must never become a request from inside the server's network (`utils/fetch_policy.py`;
ADR-602 for the local exception). What the window loads is decided by the system it runs on:
md2ui keeps no origin list, and a blocked picture draws its placeholder without stalling the
page. Resolving media is the service's option, offered in its own tools; `skills/` describes
md2ui, not services.

## Why

- **Every frame fits in about one packet**, so the cost is round trips. Hence one persistent
  bidirectional connection, streamed deltas, and O(1) verification from an index built once per
  message, instead of regrouping per event.
- **A reference is the security boundary.** An event that restated its action and params could
  be forged. One that names only a target the server offered cannot ask for anything the server
  did not put on the page.
- **An ordinal, not a node id.** The Python prototype's ids are tree positions, and md2ui-ts
  derives ids from content. A node id cannot be agreed across the two; an ordinal can, wherever
  their structure agrees.
- **The prompt breaks "no client string reaches the agent" on purpose, and only there.** It is
  exactly as trusted as the same words typed into the agent's own chat.
- **The state costs the agent nothing**, because the backend knows every transition. Without
  it nobody could see whether anyone was listening, and clicks queued silently. Blocking input
  while the agent works removes the race where the agent's replacement erased clicks it had not
  handled yet.
- **Released at the listen, by `q`.** An agent answering several clicks listens only after the
  last answer, so buttons come back when the batch is answered. Replacements can renumber
  ordinals between a click and its release; a `q` stays exact.
- **Keeping local state across a replacement.** Without it, a replacement reverted ticks or
  dropped clicks that crossed it in flight.
- **One WebSocket is the fastest honest binding**: one connection, both directions, streaming.
  Security defaults belong in the reference, because whoever copies it copies its defaults.
- **JSON first; gRPC as `.proto` only.** Protobuf would save a few bytes per event. A gRPC
  server now would be a second implementation to keep secure, for no client that needs it,
  while the fixed field numbers keep adding one later cheap.
- **An image URL can carry data out** when a prompt-injected agent writes one. The system's
  network rules limit that, not md2ui; it is not an md2ui defect.

## Considered and rejected

- **Fonts, assets or the theme in a frame.** The wire stays Markdown. A server that fetched
  assets would also widen the attack surface to local files and the internal network.
- **Node ids as event keys**, for the reason above.
- **A patch frame for re-sends.** A full re-send is small; add one only if a measurement says it
  matters.
- **The agent writing its own state.** It would cost a step per transition for something the
  backend already knows. The reserved note `n` is where the agent's own words would go; ADR-613
  has since filled it with the agent's current step.
- **Ending "working" from the host** (a plugin `Stop` hook, Claude Code channels). Each only
  shortens a wait in the demo. A server-side integration knows when its turn ends and sets the
  state itself.

## Constraint created

- **A newly clickable thing joins `action_targets`** in document order, or its events are refused
  as out of range. `tests/wire_tests.py` checks every click region against its ordinal.
- **The index needs grouping only**: no fonts, no theme, no layout, no width. A server that knows
  only content can verify.
- **Every client frame goes through `wire.decode_client` and `MessageLog.verify`.** A binding
  carries the rules; it never re-implements them.
- **A new binding keeps every reference default** listed in `protocol/backend.md`, or says in
  its own record why one does not apply.
- **A frame field goes into the schema, the `.proto` and the codec together.** The wire tests
  fail otherwise.
- **New frames and keys are additive** (`protocol/README.md`, *Versioning*). `tp` and `vars` are
  reserved and not designed.
- **A backend that uses the wire sets the state itself** (`Conversation.set_state`).
- **Prompt text is untrusted** and never mixed into a server-built sentence.
- **The prompt bar is the window's chrome, not the theme's.** THEME.md styles the answer for
  every frontend; a frontend's own controls are its own (`app_chrome.ChromeStyle`). The bar is
  never recorded into the document (ADR-401), and the pipeline never imports it.
- **TLS and authentication are the host's**, at the WebSocket upgrade. md2ui authenticates no
  one, except with the bearer secret a host with no sessions passes.

## Reconsider when

- **The two implementations' structure diverges for a document.** Ordinals then disagree, and
  events must carry more than `x`.
- **Both implementations share one id scheme.** An event may then name the node directly.
- **A measurement shows full re-sends matter.** Add the patch frame.
- **A native client needs gRPC.** Build the server behind an optional extra, from the `.proto`.
- **A deployment's proxy blocks WebSockets.** Build SSE plus POST, with the same rules.
- **More than one conversation per server is needed.** A `Conversation` per session id, bound to
  the host's authentication.
- **The agent should say what it is doing.** Fill `n` and show it in the bar. Taken up by
  ADR-613.
