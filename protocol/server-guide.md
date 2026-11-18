# Running md2ui in your own backend

For the developer whose backend runs the agent and whose app shows its replies. The reader is
the person building the server, not the LLM. Beside this:
- [`README.md`](README.md): the wire, if you use md2ui's WebSocket;
- [`backend.md`](backend.md): your send tool, your socket's security, includes and feeds.

Everything here is in the `md2ui` package (`uv add md2ui`, or `pip install --pre md2ui`).

## The shape

The agent writes Markdown, your backend sends it, and an md2ui view in your app renders it. A
tap on one of the agent's buttons comes back to the agent as a sentence.

| concern | md2ui provides |
|---|---|
| render the reply | md2ui-ts: `<md2ui-view>`, or the webview host for a native app |
| carry pages and taps | the wire (`README.md`, ADR-601), or nothing: your own API works |
| what the agent is told | `guide`, served for the project's theme (section 1) |
| a tap, as the agent's next input | `MessageLog.verify` → a sentence with the full action |
| a change without an agent turn | includes and handlers: `{{name args}}` drawn from your data, a click answered by changing it, `Show(page)`, `Conversation.changed` (ADR-612, ADR-614); else `mark`, `set_slider`, `patch` |
| the reply's mistakes, told to the agent | `reply_issues` (`backend.md`) |
| "the agent is working" | the wire's state frame (`s`) |

**You do not need the wire.** An HTTP API that returns the page, with the view in your client,
is a complete integration. The pieces below are plain Python and work with either.

## 0. A minimal backend

One conversation, served over the wire: send a page, listen, and act on what comes back.
`Served` runs the server on a background thread, so a synchronous program can drive it;
`served.call` runs a `Conversation` coroutine on the server's loop.

```python
from md2ui.wire import Prompt, Verified
from md2ui.wire_feeds import FeedEnded
from md2ui.wire_server import Conversation, Presence, Served

PAGE = """# Your order

- [ ] Add fries

[Checkout](agent:checkout?cart=42)
"""

conversation = Conversation()
served = Served(conversation, port=8765)  # loopback only; see backend.md for security
print("serving at", served.url, flush=True)

served.call(conversation.send(PAGE))
served.call(conversation.set_state("l"))  # listening: clients may now send input

try:
    while True:
        event = served.next_event(timeout=60)
        if event is None:  # nothing in 60 s
            continue
        if isinstance(event, Verified):
            served.call(conversation.set_state("w"))  # working: clients block input
            print("to the agent:", event.agent_text(), flush=True)
            if event.action.checked is not None:  # a task box: agree to it
                state = "checked" if event.action.checked else "unchecked"
                served.call(conversation.mark(event.message_id, event.ordinal, state))
            elif event.action.value is not None:  # a slider
                served.call(conversation.set_slider(
                    event.message_id, event.ordinal, event.action.value))
            # else: hand event.agent_text() to your agent, then send its reply
            served.call(conversation.set_state("l", answered={event.peer: [event.seq]}))
        elif isinstance(event, Prompt):
            print("the user wrote:", event.text, flush=True)
        elif isinstance(event, Presence):
            print("the window", event.kind, flush=True)  # "closed" or "reconnected"
        elif isinstance(event, FeedEnded):
            print(event.text, flush=True)
except KeyboardInterrupt:
    pass
finally:
    served.stop()
```

Run it, then connect md2ui's own window to it, `md2ui-app --connect ws://127.0.0.1:8765/ws`,
or any wire client. Ticking the box, pressing *Checkout* and disconnecting prints:

```
serving at ws://127.0.0.1:8765/ws
to the agent: User ticked "Add fries" (task 0) (message c1)
to the agent: User chose "Checkout": checkout {cart: 42} (message c2)
the window closed
```

The tick comes back as a replacement, `c2`, with the box ticked; `answered` tells the client
which of its clicks were answered, so it releases the button it held.

### The same, async, under your own server

When your backend already runs an event loop, serve `build_app` with uvicorn (or mount it in
your ASGI app) and read `conversation.events` directly. `routes` adds your own routes beside
`/ws`, here the theme folder, so the client can fetch `/theme/THEME.md` and its fonts:

```python
import asyncio
from pathlib import Path

import uvicorn
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from md2ui import session
from md2ui.wire import MAX_CLIENT_FRAME_BYTES, Prompt, Verified
from md2ui.wire_feeds import FeedEnded
from md2ui.wire_server import Conversation, Presence, build_app

THEME_DIR = Path("theme")  # THEME.md and the font files it names

PAGE = """# Your order

- [ ] Add fries

[Checkout](agent:checkout?cart=42)
"""


async def main() -> None:
    conversation = Conversation(session.load_grouping_kit())
    app = build_app(
        conversation,
        allowed_origins=["https://app.example"],  # the pages that may open /ws
        routes=[Mount("/theme", StaticFiles(directory=THEME_DIR))],  # GET /theme/THEME.md
    )
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8765,
        ws_max_size=MAX_CLIENT_FRAME_BYTES,  # refuse an oversize frame unread
        ws_per_message_deflate=False,  # no compression
        lifespan="off",
    )
    server = asyncio.create_task(uvicorn.Server(config).serve())

    await conversation.send(PAGE)
    await conversation.set_state("l")
    while not server.done():
        event = await conversation.events.get()
        if isinstance(event, Verified):
            await conversation.set_state("w")
            print("to the agent:", event.agent_text(), flush=True)
            if event.action.checked is not None:
                state = "checked" if event.action.checked else "unchecked"
                await conversation.mark(event.message_id, event.ordinal, state)
            await conversation.set_state("l", answered={event.peer: [event.seq]})
        elif isinstance(event, Prompt):
            print("the user wrote:", event.text, flush=True)
        elif isinstance(event, Presence):
            print("the window", event.kind, flush=True)
        elif isinstance(event, FeedEnded):
            print(event.text, flush=True)


asyncio.run(main())
```

A page whose Origin is not in `allowed_origins` is refused at the upgrade with a 403; a
native client, which sends no Origin, is let in. Authenticating the upgrade is yours:
`backend.md`, *Your security*.

### Without the wire: your own HTTP API

Keep a `MessageLog` per conversation, record every page you return, and verify every tap
against it. Your client reports a tap as the page's id and the target's ordinal `x`:

```python
from md2ui import wire_patch
from md2ui.wire import MessageLog, Verified

PAGE = """# Your order

- [ ] Add fries

[Checkout](agent:checkout?cart=42)

## Delivery

Arrives at 3:53 PM.
"""

log = MessageLog()                                # one per conversation
log.record("p1", PAGE, None)                      # every page you return, under its id

# POST /tap {"m": "p1", "x": 1, "q": 7}, from your client
result = log.verify({"t": "e", "m": "p1", "x": 1, "q": 7}, peer="session-abc")
if isinstance(result, Verified):
    print(result.agent_text())                    # hand this to the agent
else:
    print("refused:", result.code)                # Rejected: unknown page, stale, bad target

log.mark("p1", 0, "checked", "p2")                # tick the box: the page is now p2
page, edited, renewed = wire_patch.patch_page(    # replace one section, no agent turn
    log, "p2", "## Delivery\n\nArrives at 4:05 PM.\n", section="Delivery", x=None
)
log.record("p3", edited, page)                    # p3 carries on from p2
```

`log.markdown("p3")` is the page to return. A tap on `p1` is now refused as `stale`.

## The API, by when you call it

**Serving.** `build_app(conversation, allowed_origins=(), allow_loopback_origins=False,
bearer=None, max_events_per_second=20, routes=())` is the Starlette app: the wire at `/ws`,
feeds' posts at `/feed/{token}`, and your `routes`.

| parameter | does |
|---|---|
| `allowed_origins` | the browser pages, by Origin, that may open `/ws`; any other Origin is refused with a 403 |
| `allow_loopback_origins` | also let in pages served from `localhost`, `127.0.0.1` or `::1`; off by default |
| `bearer` | require `Authorization: Bearer <bearer>` on the upgrade, for a native client; a browser cannot send it |
| `max_events_per_second` | disconnect a client that sends more (close 1008) |
| `routes` | Starlette routes beside `/ws`, such as `Mount("/theme", StaticFiles(...))` |

`Served(conversation, host="127.0.0.1", port=0, **build_app_kwargs)` serves that app on a
background thread: `.url` is its `ws://…/ws` address (`port=0` takes a free one), `.call(coro)`
runs a conversation coroutine and returns its result, `.next_event(timeout)` returns one event
or `None`, `.next_events(timeout, limit)` everything waiting (clicks batched; a prompt always
alone), and `.stop()` shuts it down.

**The conversation.** `Conversation(kit=None, prefix="c", includes=None)` is one
conversation: what was sent, who is watching, and the queue of what came back. Pass
`session.load_grouping_kit()` to share one kit between conversations; `prefix` starts every
message id. Its methods are coroutines:

| call | when |
|---|---|
| `send(markdown, replaces=None)` | the agent replied: a new page, or with `replaces`, the page it edits in place; returns the message id |
| `stream(chunks)` | the same, sent as the agent writes it; its actions enable at the end |
| `set_state(state, note=None, answered=None, placeholder=None)` | the agent's state changed: `"l"` listening (with `placeholder`, the question it asked), `"w"` working (with `note`, its current step), `"i"` idle. `answered`, `{peer: [seq, …]}`, names the clicks the agent answered |
| `mark(message_id, x, state)` | tick, untick or disable target `x`: `"checked"`, `"unchecked"`, `"disabled"` |
| `set_slider(message_id, x, value)` | set a slider's value |
| `patch(message_id, markdown, section=None, x=None, side=None, replace=None)` | replace a section, a target or exact text, or add sections beside one |
| `changed(names)` | your data behind these includes changed: redraw them on the page shown |

Each of `mark`, `set_slider` and `patch` sends a replacement and returns its id. Beside them:
`conversation.events`, the queue of what came back; `conversation.log`, the `MessageLog` of
every page sent; `conversation.handlers`, the clicks your backend answers itself, and
`conversation.take_handled()`, the lines to tell the agent about them (`backend.md`);
`conversation.feeds.open(…)`, a feed (`backend.md`).

**What comes back.** `conversation.events` and `Served.next_event` yield one of four types:

| type | from | is | carries |
|---|---|---|---|
| `Verified` | `md2ui.wire` | a click, resolved against the server's copy of the page | `agent_text()`, the sentence for the agent; `action` (its `kind`, `action` slug, `params`, `label`, `checked`, `value`); `message_id`, `ordinal`, `peer`, `seq` |
| `Prompt` | `md2ui.wire` | what the user typed into the client's own field | `text`, verbatim: the user's words, never inside a sentence |
| `Presence` | `md2ui.wire_server` | the last client left, or one returned | `kind`: `"closed"` or `"reconnected"` |
| `FeedEnded` | `md2ui.wire_feeds` | a feed stopped | `text`, what to tell the agent; `reason`, `values` |

A refused event never reaches the queue: the client gets an `x` frame (`README.md`,
*Verification*).

## 1. What your agent is told

The agent needs md2ui's authoring notes and your project's meanings. md2ui serves both,
generated for your theme:

```python
from pathlib import Path

from md2ui.mcp_server import build_server

theme_path = Path("theme/THEME.md")              # your project's THEME.md, beside its MEANINGS.md
authoring = build_server(theme_path)
result = await authoring.call_tool("guide", {"topic": "readme"})
core = result.content[0].text
```

The core note comes back with your project's own sections already at its end:
- **the theme's own spellings** (`meanings.own_spellings`);
- **where each action and icon goes** (`placed_spellings`);
- **the placeholders it offers** (`placeholder_spellings`).

**Prefer giving the agent `guide` as a tool to inlining everything.** The notes point to sections
(`guide("theme")`, `guide("theme/<pattern>")`), and so does the advice your send tool returns
(`backend.md`).
- **With the tool,** those pointers work.
- **Inlined,** you need a shim ("there is no guide tool: read `## theme/<name>` below"), and
  the agent pays for every pattern on every turn.

Agents read the core note and little else (ADR-502). Anything that must change what they write
belongs in the core note or in advice, not behind a pointer.

Then add what only your app knows. Here is a template built from the demo's own instructions,
with the parts that belong only to the demo window left out:

> Every reply you write is shown to the user as an md2ui page: plain Markdown, which the app
> renders as UI on a screen about 375 points wide. A new reply replaces the page. Offer the next
> steps you can take with your tools as buttons, `[See movements](agent:transactions?category=dining)`.
> A tap comes back to you as a sentence: `User chose "See movements": transactions {category:
> dining}`. Act on it as the user's next message. Your send tool returns the page's authoring
> issues; when one applies, send the page again with it fixed. Call `guide` for a section of the
> notes when a question needs it.

**Leave out the demo's** `show`/`wait_for_event` listening, the window-against-chat rules,
"check md2ui", `screenshot` and `guide("opened")`. Your backend runs the loop, so your agent never
listens.

## 2. The theme, to the client

The client fetches `THEME.md` by URL and owns its fonts and assets. MEANINGS.md and your patterns
stay on the server: they are for the agent, not the renderer. Either:
- **serve it:** `GET /theme/THEME.md`, plus a static folder for its fonts and assets, as the
  async example in section 0 does with `routes`;
- **or bundle it in the app.**

The view measures text in a Worker that sees only the fonts it is given. So list every face
`THEME.md` names, and the icon font, and check that list whenever the theme's fonts change.
The fonts md2ui's own themes use are listed, with their source URLs and licences, in the
package's `assets/fonts.lock`.

## 3. Sending a reply, and telling the agent what went wrong

Send the reply, then return its authoring issues as the send tool's result. `backend.md` has the
ten lines. An agent that never hears the issues never learns that a picture run has no ratio,
or that a spelling isn't declared. Checking pages in your tests does not cover what the agent
writes live.

## 4. A tap comes back

The view reports a tap as its page's id and the target's ordinal (`x`, counted as `README.md`
*Targets* says), with the action's name. The link's query stays on the page. Keep your own copy
of every page you sent, and let md2ui resolve the tap against it:

```python
from md2ui.wire import MessageLog, Verified

log = MessageLog()                               # one per conversation
log.record(page_id, markdown, None)              # every page you send, under the id the view shows

result = log.verify({"t": "e", "m": page_id, "x": ordinal, "q": seq})
if isinstance(result, Verified):
    agent_input = result.agent_text()            # 'User chose "Remove": cart-remove {id: classic-smash} (message p1)'
    action = result.action                       # kind, action, params: the full link
else:
    ...                                          # Rejected: an unknown or replaced page, a stale ordinal
```

A `Conversation` does this for you: its `log` is this `MessageLog`, and what reaches
`conversation.events` is already verified.

`verify` takes the full action, its query included, from the server's own copy, never from
the client. A tap on a page you have since replaced is refused, never acted on.

The action is a request, not a permission. Decide whether it may proceed as you would for any
call to your API, then hand the sentence to the agent (`backend.md`).

## 5. Changing the page without a turn

A ➕, a ❤️, a "View cart" or an order moving on does not need the agent. Let the agent write
**includes**, lines the server draws from your data, and answer the clicks that only change
that data yourself (ADR-612). `backend.md` (*Includes and handlers*) has the rules and the code;
the shape, with `cart`, `cart_markdown` and `order_markdown` standing for your own data:

```python
from md2ui.includes import Includes
from md2ui.mcp_server import build_server
from md2ui.wire_includes import Show
from md2ui.wire_server import Conversation

includes = Includes()
includes.add("cart", "the cart, with its steppers", lambda args: cart_markdown())
includes.add("order", "one order's status", lambda args: order_markdown(args.words[0]),
             args="<order id>", failure="Order tracking is unavailable.")
conversation = Conversation(kit, includes=includes)
authoring = build_server(theme_path, reading=reading, includes=includes)  # guide("includes") lists them

def cart_add(params):                    # agent:cart-add?id=…
    cart.add(params["id"])
    return {"cart"}                      # the includes whose data changed
conversation.handlers["cart-add"] = cart_add
conversation.handlers["cart"] = lambda params: Show("{{cart}}")  # a tap that only picks a page
```

- **An include line**, `{{cart}}` or `{{order A17}}`, alone between blank lines at the page's top
  level, is replaced with what `expand` returns before the page is recorded, so the log, the
  ordinals and every client see the real page. One that cannot be drawn shows its `failure=` line,
  muted, or nothing.
- **A handled click** redraws the includes the handler names on the page shown and sends one
  replacement. **`Show(page)`**, a page of include lines, is sent as a new message instead
  (ADR-614). Either way the click never reaches `conversation.events`.
- **Data that changes with no click**: `await conversation.changed({"order"})` redraws those
  regions on the page shown (ADR-612).
- **The agent still knows**: `conversation.take_handled()` gives one line per handled click or
  redraw; hand them over with its next input.

For evals, a theme folder may hold static includes, `includes/<name>.md` beside its `THEME.md`;
`build_server` loads them when it is given no registry (`backend.md`).

The agent's words never change: only the include regions do, and its `patch` or `mark` of one is
refused. When the page has no include to redraw, edit your copy of the page and send the result
as a replacement. With a `Conversation`, call its `mark`, `set_slider` or `patch`, which also
send it. With a bare `MessageLog`:
- **`log.mark(page_id, x, "checked" | "unchecked" | "disabled", new_id)`:** a task box or a
  button, the way the agent would.
- **`log.set_slider(page_id, x, value, new_id)`:** a slider's value.
- **`wire_patch.patch_page(log, page_id, markdown, section, x)`:** a whole section
  (`section="Delivery", x=None`), one target (`section=None, x=3`), or exact text with
  `replace=[(old, new)]` (ADR-611). `x` has no default: pass `None` when you name a section.
  - **It returns** `(page, edited, renewed)`.
  - **Record the edited page:** `log.record(new_id, edited, page)`. `mark` and `set_slider` record
    theirs, and `log.markdown(new_id)` gives the page to send.

Each of these, like an include, works on the grouped page, not on spellings. A regex over
`__[➖](agent:cart-remove?id=X)__` breaks the day the theme's spellings change.

Tell the agent what you changed this way on its next turn, as `take_handled` does for includes.
Keep those notes per conversation.

## 6. "The agent is working"

Block the view's input while a turn runs. On the wire, the server's state frame does it for
every connected client (`README.md`, *Lifecycle* 5): `set_state("w")` when the agent starts,
`set_state("l")` when it listens again.

The state frame may also carry words for the client's chrome (ADR-613), never for the page:
- **`ph`, sent only with `l` (listening):** the question the agent is waiting on, which the client
  shows as its prompt field's placeholder: `set_state("l", placeholder=…)`.
- **`n`, sent only with `w` (working):** the agent's current step, a short label ("Edit app.py"),
  drawn under the working animation: `set_state("w", note=…)`, from whatever sees your agent's
  tools.

A state without one clears it. A client that ignores both shows its own lines.

## Checklist

- [ ] The agent gets the core note from `guide` for **your** theme, and has `guide` as a tool.
- [ ] Your prompt says what your app is: the screen, how taps come back, what it never asks the
      user to type.
- [ ] The client gets `THEME.md` and every font it names.
- [ ] Your send tool returns `reply_issues`.
- [ ] Taps are verified against your copy of the page (`MessageLog`), never parsed from the
      client's text.
- [ ] Data the agent would retype is an include, clicks that only change data have a handler,
      and edits without a turn go through includes, `mark` or `patch_page`, not regexes.
- [ ] State shared across requests (notes, carts) is per conversation.
- [ ] The WebSocket upgrade is authenticated by your backend, and `allowed_origins` names your
      pages (`backend.md`).
