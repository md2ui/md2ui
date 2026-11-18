# md2ui

__Markdown in, a rendered UI out.__

An LLM already answers in Markdown. md2ui lays that answer out as an interface — cards, rows, stats, charts, buttons — and styles it with a `THEME.md` that belongs to your app, not to the model. Clicks come back to the agent as sentences built from its own Markdown.

+++

`Python` `TypeScript` `Wire protocol`

+++

[Edit this page](agent:edit-source)

+++

## What you are looking at

This page is md2ui-ts running in your browser. The bar above picks a document, the theme it is drawn with, and the theme's layout. Pick another document and its own theme comes with it; pick another theme to restyle that document only.

+++

Nothing on this page is a screenshot. Resize the window and the layout is solved again for the new width.

+++

The __Edit this page__ button above is an `agent:` link. In an app its click would go back to the agent as a sentence; here the page catches it and opens this document's source beside the view. Type in it and the view lays out your text as you go.

## How it works

A pipeline, and each stage annotates one shared tree and hands it on.

1. __Group__ — blank lines, headings and separators decide what belongs together
2. __Detect__ — dates, figures, ratios, tasks and actions become typed values
3. __Lay out__ — runs grid, sections stack or tile into a mosaic, at the width you have
4. __Paint__ — every colour, radius, font and shadow comes from `THEME.md`

The model controls one thing — structure. The theme owns the look.

## Python — the reference implementation

The renderer, an interactive window, a CLI for agents and an MCP server. Requires Python 3.13+ and uv.

```
uv sync

# Render a document to a PNG
uv run md2ui render path/to/content.md --width 1280 --out out.png

# Open it in a window that re-renders on save
uv run md2ui-app path/to/content.md --theme path/to/THEME.md

# Check what an agent wrote before it is delivered
uv run md2ui check path/to/content.md
```

## TypeScript — md2ui-ts in the browser

One custom element runs the whole pipeline client-side. React and Vue components wrap it, and it works with no framework at all.

```
import { defineMd2uiView } from "@md2ui/dom";

defineMd2uiView();

const view = document.querySelector("md2ui-view");
view.themeSrc = "/theme/THEME.md";
view.fonts = [{ family: "Inter", url: "/fonts/Inter-Regular.ttf" }];
view.messageId = "m1";
view.markdown = "# Your order\n\nShip it?\n\n[Yes](agent:ship) [No](agent:cancel)";

view.addEventListener("md2ui-action", (event) => {
  console.log(event.detail); // { kind: "agent", slug: "ship", ordinal: 0, ... }
});
```

## The wire — a server and its frontends

A backend sends plain Markdown, whole or streamed. A frontend reports a click by naming the target's ordinal, never restating it, so a client cannot ask for an action the message did not offer.

__Serve a document__ with the reference WebSocket server

```
uv run python -m md2ui.wire_server path/to/content.md --port 8765
uv run md2ui-app --connect ws://127.0.0.1:8765/ws
```

__Verify events__ in your own backend

```
from md2ui.wire import MessageLog, Verified

log = MessageLog()

# Record what you send; send each frame to the client as JSON
for frame in log.record("m1", markdown):
    await socket.send_json(frame)

# Resolve each event against your own copy of the message
result = log.verify(await socket.receive_json())
if isinstance(result, Verified):
    agent.tell(result.agent_text())
```

__Connect a view__ with `@md2ui/wire`

```
import { connectWebSocket } from "@md2ui/wire";

const client = connectWebSocket(new WebSocket("wss://agent.example/md2ui"), (event) => {
  if (event.type === "message") {
    view.streaming = !event.complete;
    view.markdown = event.markdown;
    view.messageId = event.id;
  }
});

view.addEventListener("md2ui-action", ({ detail }) => {
  if (detail.kind === "link" || detail.messageId === null) return;
  client.sendEvent({ message: detail.messageId, target: detail.ordinal, kind: detail.kind });
});
```

## Writing for it

Ordinary Markdown renders as it is. A few spellings divide a line, and they are the layout:

- `---` draws a rule; `___` cuts a run of cards
- `Key: value` is a stat; `___$12,480___` is the hero number
- `[Label](agent:do-it)` is a button whose click comes back to the agent
- `- [ ] Task` is a checkbox; `Volume: [65%]` is a slider
- one `##` per card, and three or more of them can tile into a mosaic
