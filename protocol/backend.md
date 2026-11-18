# A backend's send tool: return the issues to the agent

For the developer running md2ui server-side. [`README.md`](README.md) is the wire between the
server and its frontends; this note is the other side, between the server and the agent that
writes the Markdown. The whole integration, step by step, is [`server-guide.md`](server-guide.md).

Your agent's reply reaches the user through your own tool: the agent calls it, and your
backend sends the Markdown with `Conversation.send` (ADR-601). That tool's result is the one
thing every agent reads after every reply, so return the reply's authoring issues there, as
the demo's `show` does (ADR-602):

```python
from pathlib import Path

from md2ui import session, theme_lint
from md2ui.advice import Reading, reply_issues
from md2ui.mcp_server import build_server
from md2ui.wire_server import Conversation

theme_path = Path("theme/THEME.md")             # your project's THEME.md, beside its MEANINGS.md
kit = session.load_grouping_kit()
contract = theme_lint.answer_contract(theme_path)
reading = Reading()                             # one per agent session
authoring = build_server(theme_path, reading=reading)  # its `guide` records what is read
conversation = Conversation(kit)                # served with Served or build_app (server-guide.md)


async def send(markdown: str) -> dict:          # your agent's tool
    message_id = await conversation.send(markdown)
    ast = session.group_markdown(markdown, kit)
    return {"message_id": message_id, "issues": reply_issues(markdown, ast, contract, reading)}
```

**What the agent gets:**
- the authoring issues `check` finds, each a `level`, `code` and `message`;
- advice: a `note` with `code: advice`. It names the section of the notes that teaches
  something the reply used, under `read`, with what to write. It is given once per section,
  and never for one the agent has read.

The page is already in front of the user, so an agent that acts on an issue sends the
corrected page, and the user sees it refresh.

**Keep `reading` per agent session.** It is what keeps advice to sections the agent has not
read, so it is shared with that session's `guide` (pass it to `build_server`) and starts
empty for a new one.

Sending first and advising after keeps the first paint fast. A backend that would rather gate
a reply can call `reply_issues` before `send` and give the agent one revision. That holds
the page back by a turn.

## Your security: authenticate the upgrade

**What the reference binding checks.** `wire_server.build_app()` authenticates in two ways
only, both at the WebSocket upgrade:
- **`allowed_origins`**, an allow-list of the browser pages, by Origin, that may open `/ws`.
  Any other page is refused, a `localhost` one included, unless you pass
  `allow_loopback_origins=True`. A native client sends no Origin and is let in.
- **`bearer`**, a fixed secret: the upgrade must carry `Authorization: Bearer <bearer>`. A
  browser's `WebSocket` cannot set headers, so a browser page cannot present it; it suits a
  native client, as the MCP demo uses it for its own window.

**A backend that serves browsers authenticates the upgrade itself**, with what it already
uses. `build_app()` is a plain ASGI app, so the backend's own security applies to it unchanged:

- **At the door, the WebSocket upgrade.** This is the standard place (RFC 6455 §10.5): the
  upgrade is an HTTP request, carrying the backend's cookie, `Authorization` header or a
  one-time ticket in the URL. Put `/ws` behind the proxy that already checks them, or mount
  it inside the backend's app, under the middleware that already guards its other routes.
  A refusal before the socket is accepted reaches the client as a 403:

  ```python
  class RequireSession:                      # any ASGI middleware does the same
      def __init__(self, app):
          self.app = app

      async def __call__(self, scope, receive, send):
          if scope["type"] == "websocket" and not await my_session_is_valid(scope):
              await send({"type": "websocket.close", "code": 1008})  # -> HTTP 403
              return
          await self.app(scope, receive, send)

  app = RequireSession(build_app(conversation, allowed_origins=["https://shop.example"]))
  ```

  `my_session_is_valid` is your own check: of the session cookie in `scope["headers"]`, or of
  a ticket in `scope["query_string"]`. A browser client sends its cookies with the upgrade on
  its own; md2ui-ts takes the `WebSocket` the host opened, so the URL and its ticket are the
  host's choice too.
- **At the queue, before the agent hears anything.** Every click and prompt waits on the
  conversation's queue until the backend takes it (`Served.next_event`, or
  `conversation.events`), already verified against the page the server sent. The backend
  decides there whether the action may proceed, as it would for any request to its API, and
  only then hands it to the agent. The `agent:` slug is a request, never a permission.

A server reachable by other local processes needs the door above even with no browser
client, since a native client sends no Origin.

**The reference binding's other defaults** (`wire_server`), which a binding you write keeps
too, or documents why one does not apply:

- it listens on loopback only;
- the first frame must be `hello`;
- the socket refuses a client frame over 8 KB before any JSON is parsed (close 1009), and the
  codec holds every client frame but a prompt to 512 bytes;
- a client that sends more than 20 events a second is disconnected (close 1008);
- permessage-deflate is off;
- `q` counts per connection, so one client's retries cannot shadow another's clicks.

Served under your own uvicorn, keep the frame cap and compression off yourself:
`uvicorn.Config(app, ws_max_size=MAX_CLIENT_FRAME_BYTES, ws_per_message_deflate=False)`, with
`MAX_CLIENT_FRAME_BYTES` from `md2ui.wire` (`server-guide.md`, section 0).

## Includes and handlers: data the backend draws, clicks it answers

([ADR-612](../decisions/ADR-612-a-backend-expands-includes-and-answers-clicks-by-changing-data.md).)
Your agent can write a line the server draws from your data, and a click that only
changes data can be answered without waking the agent.

**An include** is a line holding exactly one `{{name args}}`, at its first column, with a
blank line before and after, at the page's top level: one between list items or in a cell of
a `:::` row is not drawn, and `check` warns (what it draws would take the rest of the list or
the row's bound into its section). `Conversation.send` replaces it with what your
`expand(args)` returns before the page is recorded, so the log, the ordinals and every window
see the real page. Args are `key=value`, `key="two words"` and bare words (`args.named`,
`args.words`). `Conversation.stream` sends its chunks as written and expands nothing: stream
a page with no include lines, or `check` warns (`streamed-include`).

**An include that cannot be drawn** (an `expand` that raises, args that do not read, a name
you did not register) never shows its braces: its region is the `failure=` line you
registered for it (in your users' language), drawn in the theme's muted tier, or, without
one, empty: md2ui writes no words of its own on your page. It is still the include's
region, so your next redraw of it draws it again once your data recovers. The exception's text goes to stderr only.

```python
from md2ui.includes import Includes
from md2ui.wire_server import Conversation

includes = Includes()
includes.add("cart", "the cart page, with its steppers", lambda args: cart_markdown())
includes.add("order", "one order's status", lambda args: order_markdown(args.words[0]),
             args="<order id>", failure="Le suivi de commande est indisponible.")
conversation = Conversation(kit, includes=includes)


def cart_add(params: dict[str, str]) -> set[str] | None:  # a handler, by agent: slug
    cart.add(params["id"])
    return {"cart"}                 # the includes whose data changed; None: not mine

conversation.handlers["cart-add"] = cart_add
```

- **Tell the agent which includes exist**: build the authoring server with the same
  registry, `build_server(theme_path, reading=reading, includes=includes)`. Its
  `guide("includes")` lists them, one line each, and its `check`, `outline`, `layout` and
  `preview` read the page expanded. Pass `includes` and the page's regions
  (`conversation.log.pages.includes.regions(mid)`) to `reply_issues` too: an include that
  could not be drawn (an unknown name, args that do not read, an `expand` that raised) is
  an `error` (`unknown-include`) naming it and the error's class, since the user sees its
  failure line, or nothing, instead. On a server with no includes nothing is expanded, and a lone
  `{{name}}` is a `warning`: it may be template syntax the agent is writing about.
  Pass `handled=conversation.handlers` as well: a `➖ n ➕` stepper whose `agent:` slugs
  your handlers answer costs no turn, so the agent is not advised to write it as a count.
- **Check the page you sent**, as the demo's `show` does: `conversation.log.markdown(mid)` is
  the expanded page.
- **A handled click** redraws the named includes on the page shown and sends one replacement
  (`r`), then releases the button (`u`) whatever the state: the agent never had the click.
  It never reaches `conversation.events`. A handler only ever receives a verified click's
  params, so an `agent:` slug stays a request: decide there whether it may proceed. A
  handler that raises leaves the click to the agent, with a digest line naming the action
  and the error's class (its text goes to stderr only). An include the redraw cannot draw
  shows its failure line or nothing, and the digest line says so: `` `{{cart}}`
  (RuntimeError) could not be drawn ``.
- **A tap that only chooses a page** ("🍟 Sides", "View cart") is answered with a page of
  your includes ([ADR-614](../decisions/ADR-614-a-backend-may-answer-a-tap-with-a-page-of-its-includes.md)):
  the handler returns `Show(page)`, every non-blank line of `page` an include line.

  ```python
  from md2ui.wire_includes import Show

  def catalog(params: dict[str, str]) -> Show:     # agent:catalog?category=sides
      category = params.get("category")
      return Show(f"{{{{menu category={category}}}}}" if category else "{{menu}}")

  conversation.handlers["catalog"] = catalog
  conversation.handlers["cart"] = lambda params: Show("{{cart}}")
  ```

  The server draws it before anything is sent and sends it as a **new message** (no `r`),
  then releases the button (`u`) in any state; it never reaches `conversation.events`. The
  agent's page is not edited: it keeps its id and its row in `history` (marked
  `shown_by: backend` for yours), and `show(message_id=…)` brings it back. The feeds on the
  page left end with it. A line that is not an include, an unknown name, args that do not
  read or an `expand` that raises sends nothing: the click goes to the agent, with a digest
  line naming `PageNotDrawn`. While your page is shown, the agent's `mark` or `patch` of
  another page is refused (`bad_target`), naming the page shown, so it cannot pull the user
  back; once the agent shows a page of its own, it edits as before. Words of the agent's
  belong on its pages: a title above your include is drawn by the include.
- **The agent still knows**: `conversation.take_handled()` returns one line per handled
  click since the last call (`… the backend showed {{menu category=sides}} (now message
  c7)` for a page, naming any feed it ended); hand them over with the agent's next input.
  The demo hands them over with every listen and with the results of `show`, `mark` and
  `patch`.
- **Data that changes with no click** (an order moving on, a cart filled elsewhere): call
  `await conversation.changed({"order"})` with the names of the includes whose data changed,
  as a handler returns them (ADR-612). The server draws those
  regions again on the page shown, from your data now, and sends one replacement (`r`), the
  same a handled click sends; it returns the new id, or `None` and sends nothing when the
  page shown draws none of them differently (an identical replacement would clear the
  window's unanswered local state), or while a message is streaming (the stream is the page
  shown). Only the page shown is redrawn: a page the user left draws from your data when the
  agent brings it back. From another thread, `served.call(conversation.changed({"order"}))`.
  The agent hears it in the same digest, one line until it next hears anything: `the backend
  redrew {{order}} (data changed; now message c9)`, naming an include drawn as its failure
  line as a handled click's line does. A feed on the page runs on: its next tick writes its
  values on the redrawn page.
- **The agent's page stays its own, and the includes yours**: only include regions change,
  the id it carries resolves through the replacement, and `showing`'s `source` (in the demo)
  gives the page back with its include lines, so a re-send never retypes a figure. An
  agent's `patch` or `mark` that touches an include's lines is refused (`bad_target`),
  naming what to do instead; an edit outside them keeps them. The demo's
  `show(message_id=…)` draws the page's includes from your data now and names them
  (`redrawn`).

For evals, a theme folder may hold `includes/<name>.md`: frontmatter `description:`,
`args:` and an optional `failure:` line, then the body every call of that name expands to. `md2ui-mcp --theme DIR/THEME.md` and
the demo load them.

## Feeds: values a process moves without a turn

([ADR-608](../decisions/ADR-608-a-feed-moves-a-bar-without-a-turn.md).) A backend opens a feed
on the page shown, and any process it trusts then posts values to it; each post becomes a
replacement, with no turn of the agent's:

```python
mid = await conversation.send("# Build\n\nElapsed: 10%\n")
feed = await conversation.feeds.open(mid, keys=None, until=None)  # the page's one bar
url = f"http://127.0.0.1:{port}/feed/{feed.token}"                # build_app serves it
```

- **`open(message_id, keys, until, values=None, slots=None)`**: `keys` names the bars to move
  (none for a page with one bar), `slots` the values the author marked
  (`[3:53 PM](feed:arrives)`), and `values` each chip slot's allowed values. `until` is
  `"full"` (end when every bar is full, the default when only bars are fed) or `"silence"`.
  It refuses a page that is not the one shown.
- **A post** is `POST /feed/{token}` with `name: value` lines in the page's own spelling
  (`Elapsed: 60%`), or a JSON object; `end` ends the feed. The answers, limits and pacing
  are in `README.md`, *Feeds*. A post that carries an `Origin` is refused: a browser may not
  post.
- **When it ends** by itself (its bars full, `end` posted, silence, unusable posts, its
  lifetime), `conversation.events` yields a `FeedEnded` whose `text` says why and what to tell
  the agent. It also ends, with no `FeedEnded`, when another page is shown, and when the last
  client leaves: the `Presence("closed")` names the feeds it stopped (`feeds`). To show a new
  page and keep a feed moving on it, send it with
  `await conversation.feeds.send(markdown, keep=[feed.id])` instead of `conversation.send`.
