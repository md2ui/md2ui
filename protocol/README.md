# The md2ui wire protocol, v1

How an md2ui server and its frontends talk. The decision and its reasons are
[ADR-601](../decisions/ADR-601-the-wire-carries-markdown-and-references.md); this is the spec.
It is language-neutral: md2ui-ts and native clients implement it from this folder, and
`examples/` is the conformance set every implementation must accept (and `examples/invalid/`
reject). The Python reference implementation is `md2ui.wire` (codec, verifier) and
`md2ui.wire_server` (WebSocket binding), in the `md2ui` package. What a backend returns to the
agent that wrote the Markdown is [`backend.md`](backend.md). How to run md2ui in your own
backend, with or without this wire, is [`server-guide.md`](server-guide.md).

## What travels

**Plain Markdown, and references to it.** No theme, fonts, assets, images, AST or layout —
each client owns those and runs the pipeline itself. The server knows the content and its
layout shape, nothing else.

Two small additions: the server says what the agent is doing, and a client may send what the user typed into
its own native field.

## Frames

One JSON object per frame, UTF-8, compact. `t` is the frame type. Keys are short on purpose;
the table gives each its readable name. **Unknown keys are ignored** (forward compatibility);
known keys are strictly typed.

### Server → client

| `t` | frame | keys |
|---|---|---|
| `m` | message | `m` message id · `md` the Markdown · `r` *(optional)* the id of the message this one **replaces** |
| `d` | delta | `m` message id · `s` sequence (0, 1, 2…) · `md` text to **append** |
| `z` | end | `m` message id · `h` the first 16 hex digits of the SHA-256 of the complete Markdown |
| `x` | error | `code` (below) · `m` *(optional)* message id · `q` *(optional)* the event's sequence |
| `s` | state | `s` what the agent is doing: `l` listening · `w` working · `i` idle · `n` *(optional)* the step the agent is on, with `w`, at most 200 characters · `ph` *(optional)* the question the agent asked its prompt to show, with `l`, at most 200 characters · `u` *(optional)* the `q`s of **this client's** events that were answered, at most 64: by the agent, with `l`; by the backend, with any state |

### Client → server

| `t` | frame | keys |
|---|---|---|
| `h` | hello | `v` protocol version — `1` |
| `e` | event | `m` message id · `x` target ordinal · `q` the client's sequence number · `a` *(optional)* the target's action slug, a drift check · `c` *(optional)* the state a checkbox asks for · `v` *(optional)* the value a slider asks for, inside the domain its document authored · `vs` *(optional)* other targets this event **commits**, each `[ordinal, value]` |
| `p` | prompt | `q` the client's sequence number · `tx` what the user typed, not blank |
| `k` | typing | nothing: the user is typing in the client's own field, sent at most once a second while keys are pressed |

**Ids** match `^[A-Za-z0-9._:-]{1,64}$`. The server mints them; they are opaque to the client.
**Integers** are non-negative. **Limits** count the UTF-8 bytes of the encoded frame, as
it travels: a hello, event or typing frame is at most 512 bytes; a prompt frame at most 8 KB, and
its text at most 4 KB; a server frame at most 256 KB (a server may configure it lower).
A binding may refuse an oversize client frame before parsing it, at the larger 8 KB cap
(the reference WebSocket binding closes with 1009); the 512-byte cap on every client frame
but a prompt is then checked when the frame is decoded.

A message is bounded by its frame, not by its Markdown's own length: JSON escaping counts
(a quote or a newline costs two bytes, a control character six), so how much Markdown fits
depends on what it holds. A whole message must fit one `m` frame — a client that joins late
is sent it whole — and a streamed message is held to the same bound. A server never sends
a frame over its cap: it refuses a whole message that does not fit before sending any of it,
and a stream at the chunk that would take it over; that stream is never ended, so like any
stream cut short its actions never enable.

## Lifecycle

1. The client connects and sends `hello`. A server that does not speak `v` answers
   `x` / `bad_version`.
2. **Every message starts with `m`.** A response arrives either whole (`m`, then `z`) or
   streamed (`m` with the first chunk, `d` frames for the rest, then `z`); a message with
   no Markdown — a stream of no chunks too — is an `m` with empty `md`, then `z`. The client
   may render while it streams; **it enables the message's actions only after `z`**, and
   checks `h` against what it assembled.
3. A message with `r` replaces the named one **in place, keeping the scroll**. This is how
   the agent changes state (a tick, a disabled choice): the replaced message is from then on
   stale, and its events are rejected.

   **A replacement keeps the client's unanswered local state.** A message with `r` is the
   agent answering on the same page, so a client keeps each local state (an optimistic tick,
   a dragged slider value, a pressed agent target drawn pending) whose target the replacement
   left exactly as it was. It matches targets by ordinal, and only when both messages offer
   the same number of targets. A target the replacement changed takes the new Markdown. A
   replacement whose Markdown is identical to the one it replaces is the agent answering "no
   change", and clears every local state, as does a message without `r`. So a server sends
   a replacement that restructures a page without `r`.

   An event refused `stale` is re-sent once, with a new `q`, to the same ordinal of the newest
   message, once that message is on screen and only while the client still shows what the
   event asked for. No frame changes: the `x` frame's `m` and `q` identify the event.
4. A click or completed drag sends `e`. A client MAY attach `vs`, the settled values of
   the message's **other** targets, so one press commits what the user adjusted instead of
   costing an event each: a bool is that target's `c`, a number its `v`, at most 32 entries,
   never naming the fired `x` and never an ordinal twice. A choice travels as its chosen
   option, `[ordinal, true]`: one entry per group, never `false`. The frame's 512-byte cap still
   applies. A server writes what a verified `vs` changed into its own copy and, while
   the client still shows that message, sends it as a replacement (`r`): the client
   already shows those values, and the page it next replaces must keep them. A `vs`
   that changes nothing is not written. Only **`agent`** targets (`agent:` links,
   cards, linked task boxes and linked sliders), **`checkbox`** targets (plain task
   boxes), and **`slider`** targets (`[65%]`) are sent; a `link` and an `#anchor`
   are handled on the client and never sent. A slider sends one event on release,
   not a stream during pointer movement.
5. The server says what the agent is doing with `s`:
   - `l`: it is listening for input;
   - `w`: it is working on the last input, and a client blocks new clicks and prompts;
   - `i`: nobody is listening, so input waits until someone is.

   A joining client is sent the current state after the latest message. Until the first
   `s` arrives a client sends no `e` and no `p`: nothing yet says the server can take
   input, and what it sent could be lost. A `k` may go once `hello` has. A client that
   sends input while the state is `l` may block itself at once, since the server's `w`
   follows.

   **Listening again answers the events the agent was handed.** An `l` may carry `u`, the
   `q`s of events this client sent that reached the agent before it listened again: the
   agent answered them, whether or not its replacement changed their targets. A client
   releases a button it was holding for one, while the message it was sent on is still the
   one shown or was replaced into it; a tick or a value the user set stays as set. `u` is
   sent to the connection that numbered those `q`s and to no other, and never to a joiner.
   A client that ignores it keeps holding the button until a replacement changes it or a
   new message arrives.

   **A click the backend answers is released in any state.** A server whose backend
   answers a click itself (a handler that changes data and redraws the page, ADR-612, or
   that shows a new page of its includes, ADR-614) sends its replacement or its new
   message, then the current state again with `u` naming that click, under
   `w` or `i` as under `l`: the agent was never handed it, so its listening cannot answer
   it. The same rule holds: only the connection that numbered the `q` is told. A client
   accepts `u` on any state. After a new message, its `u` names a button on a page no
   longer shown, and changes nothing.

   **A state may carry words for the client's chrome** (ADR-613), never for the document:
   `n`, the step the agent is on while it works (a short label such as "Edit app.py", from
   a host that sees the agent's tools), and `ph`, the question the agent asked while it
   listens ("Any note for the rider?"), which a client may show as its field's placeholder.
   Each holds until the next `s`: a state without it clears it, and a server sends `n` only
   with `w` and `ph` only with `l`. A client that ignores both shows its own lines.
6. A prompt `p` carries what the user typed into the client's own native field. It is the
   one client string that reaches the agent: verbatim, labelled as the user's words, never
   inside a sentence built from the agent's Markdown.
7. A typing frame `k` says the user is typing a prompt. It carries no text and gets no
   reply; a server MAY ignore it. A client sends one on the first key pressed in its
   field and then at most one a second while keys are pressed, so a server can tell
   typing that is under way (a frame in the last few seconds) from typing that stopped.
   An unsent draft in the field counts as typing: while one is there, the client keeps
   sending `k` at that rate. Enter and Esc are not typing. A server never queues a `k` and
   never hands it to the agent; it may use the time of the last one, for instance to keep
   a short listen open while a reply is being written.

## Targets: what `x` counts

The actionable targets of a message, **in document order**, numbered from 0:

- a **link card** (a block wrapped in `[ … ](url)`), counted before what it contains;
- a **button** (a link on its own);
- a **task box** (`- [ ]`, `[ ]`, `[[ ]](agent:…)`);
- a **slider** (`[65%]` or `[3/10]`, bare or as `[[65%]](agent:…)`);
- a **count** (`Quantity: ➖ [2/9] ➕`): one slider target, whatever its two buttons;
- each **link inside a sentence**, in the order it appears in its text.

A **choice option** (an `agent:` button with `md2ui.choice=<name>`) is a button with a
checked state, counted where the button is: the options sharing a name are one group, and
the one written as the main button (no `*…*`) is the chosen one. Its `c` is `true`: a tap
chooses it, never clears it.

Disabled links (`~~[x](url)~~`) keep their place and report nothing, so ordinals do not shift
between a message and its re-send. Both ends derive the list from the same grouped document,
so it needs no ids to agree — only the structure (the reference implementation is the oracle for it).

## Three outcomes, not two

An event is **verified**, **recorded**, or **refused**. The middle one is easy to miss and a
frontend author should not have to infer it from behaviour:

| outcome | in the log | the agent is told | when |
|---|---|---|---|
| verified | yes | yes | the ordinary case |
| **recorded** | **yes** | **no** | the target is one a `md2ui.commit` press in the same message will report |
| refused | no | no | it failed a check below |

**A client sends every event and the server decides which to deliver.** A frontend cannot tell
which of its events the agent needs, so it does not try: it reports what the user did, and the
server withholds what a coming press already carries. The consequence worth stating is that a
recorded event is *not* lost — the server knows the value, so a backend can answer "what is
this form set to" for a form whose agent has not been woken once.

A recorded event produces no `x` frame, and like a refusal it is followed by the current `s`
frame to that client alone, so a frontend that blocked itself on send is released. That holds
for a frame refused before it is read, too (`too_large`, `bad_frame`): its `x` carries no `m`
or `q`, since none was read, and the `s` still follows. A commit press can meet this: 32 `vs`
entries do not always fit the 512-byte cap.

## Verification (the server)

The server resolves `(m, x)` against **its own copy** of the message it sent, and takes the
kind, action, params, label, index and authored slider value from there. From the
client it takes only `c`, or a slider's finite `v`. **A slider's range is authored, not
protocol:** `[65%]` runs 0–100 and `[3/10]` runs 0–10, so the server checks `v` against the
target's own domain rather than a fixed bound; a count's domain holds whole numbers only. Every entry of `vs` is
resolved the same way against the same copy, so committing many targets gives the client no
more say than committing one. It answers with an `x` frame, or silence for a duplicate:

| code | when |
|---|---|
| `bad_frame` | not a frame of this spec: wrong type, missing or mistyped key |
| `too_large` | over the size limit |
| `bad_version` | `hello` with a version the server does not speak |
| `unknown_message` | `m` was never sent on this connection |
| `stale` | `m` has been replaced |
| `bad_target` | `x` — or an ordinal in `vs` — is out of range, or that target reports nothing (disabled, empty) |
| `not_forwarded` | the target is a `link` or an `anchor` |
| `slug_mismatch` | `a` was sent and is not the target's action |
| `bad_value` | slider `v` is missing for a slider or present for another target; `v` is outside the target's authored domain (a count's is whole numbers); a `vs` entry gives a number to a target with no value, or a bool to one with no checked state; or a choice option is sent `false` (in `c` or `vs`), or two options of one group in one `vs` (a `v` that is not a finite number at all is a malformed `bad_frame`) |
| `duplicate` | `q` was already seen, or an `agent` target already fired for this message — dropped, not answered |

A prompt has no target to resolve: it is checked for size and blankness, and for a repeated
`q`.

A server SHOULD stamp each prompt on receipt with the message the client was showing (the
latest the server sent) and the time. A prompt typed while nobody listened waits in the
queue, and is otherwise indistinguishable from one typed a moment ago. When the agent has
sent a new message since, hand the prompt over as typed at the older one, with its age, so
an old "stop" is not taken as the reply to the new page. The stamp is the server's: no
frame carries it, and a client sends nothing new.

The agent is handed a sentence **composed from its own Markdown**, e.g.
`User chose "Yes": generate-report {format: pdf} (message c7.12)`. A committed choice reads
as its group's name and the option's label: `…, with size: "L", "Quantity" at 3`. No client string reaches
the agent.

## Security

- Every event is untrusted input; the verification above is mandatory.
- A prompt is untrusted text the user wrote. The agent treats it as the user's next message,
  exactly as if it had been typed into the agent's own chat. Everything else the agent is
  handed is built from its own Markdown.
- The agent still authorises an action against the actions it offers — the slug is a request.
- A client opens only allow-listed link schemes: `https:`, `mailto:` and its own routes;
  never `javascript:`, `data:` or `file:`.
- TLS always. Frames carry no credentials: authentication and sessions belong to the host,
  which checks them when the connection opens. What the reference WebSocket binding checks,
  and how a backend that serves browsers authenticates the upgrade, is in
  [`backend.md`](backend.md), *Your security*.
- Do not compress, in one shared context, frames that mix secrets with attacker-controlled
  text (the CRIME/BREACH class); disable context takeover where that applies.

## Transports

The frames are the contract; the carrier is a binding.

- **WebSocket**, JSON text frames — the default: one connection, both directions, streaming.
- **SSE + POST** — server frames as SSE `data:` lines, events as POSTed frames, where
  WebSockets are blocked.
- **gRPC** *(optional)* — the same frames as protobuf messages with fixed field numbers, one
  bidirectional stream. For browsers, the Connect protocol.

## Feeds: values from a process, not a turn

A backend may let a process the agent runs move values on a shown message
([ADR-608](../decisions/ADR-608-a-feed-moves-a-bar-without-a-turn.md)). This is not a wire
frame, and a client needs nothing for it: each change arrives as an ordinary replacement
(`r`).

- **Endpoint:** `POST /feed/{token}`, plain text, at most 4 KB, from the backend's own machine.
  The agent is handed the URL when it opens the feed.
- **What moves:** a bar or a chart row, named by its key, and a **slot**: a value the
  message's author marked for a feed and named. A text slot `[3:53 PM](feed:arrives)` and a
  chip slot `` [`Preparing`](feed:status) `` are drawn as their text, never as a link; a
  button's label is a slot through a link param,
  `[Track · Preparing](agent:track?id=BS-1043&md2ui.feed=track)`, and only its words change:
  its action, params and ordinal stay, and a press is narrated from the backend's current
  copy. Emphasis around a slot is the author's and holds across posts. A chip slot takes only
  the values declared when the feed was opened. A slot is never named as a bar's key, in
  any case, and never drawn by a bar or a ratio: a bar is fed by its key, so the feed refuses
  such a slot when it opens.
- **Body:** `name: value` lines in the message's own spelling (`40`, `40%`, `4/10`,
  `3:58 PM`), one or more, or a JSON object of strings and numbers (`{"Elapsed": 40}`). The
  line `end` ends the feed after the values beside it. A slot's value is a value, not prose:
  at most 4 words and 40 characters, no word longer than 24, and no character of Unicode
  category Cc, Cf, Zl, Zp, Co or Cn (U+200D only inside an emoji sequence). It is written at
  the slot's place and kept only when the message then draws nothing else differently and
  draws it as posted, in one plain run. A post is checked when it arrives, exactly as its
  tick will write it, so a refused value is refused to the process, never later.
- **Answers:**

  | code | means |
  |---|---|
  | 200 | the values were accepted |
  | 400 | the post was refused whole, with the reason; five in a row end the feed |
  | 403 | the request carried `Origin`: a browser may not post |
  | 404 | there is no such feed |
  | 410 | the feed ended: stop posting |
  | 413 | the body was over 4 KB |
  | 429 | over 50 posts a second |

- **Pacing:** the latest value per key is applied once per tick, every key in one replacement.
  The backend paces ticks by what one costs.
- **Ending:** a feed ends itself in any of these cases:
  - its bars are complete (a slot is never complete), when it was opened to end so: the
    default when it moves bars and no slot;
  - it falls silent;
  - it keeps posting unusable values;
  - another message is shown without keeping it;
  - the last client leaves;
  - it reaches its lifetime.

## Reserved (not in v1)

- `t: "tp"` — a THEME.md patch from the agent, filling gaps in the user's theme.
- `vars` in `hello` — the variables the client can substitute (`{{name}}`), names and
  descriptions only. **Values never leave the client.**

## Versioning

`v` is the major version. Adding an optional key or a frame type is not a breaking change;
changing a key's meaning or type is, and bumps `v`.
