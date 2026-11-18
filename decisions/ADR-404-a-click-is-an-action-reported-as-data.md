# ADR-404: A click is an action reported as data

**Status:** active
**Domain:** renderer
**Read when:** you make something clickable, add an event kind, or are about to have md2ui (or
its host) act on a click by changing the document.

## Decision

**md2ui never acts on a click. It reports what was clicked, as data, and the host decides.**
What it reports depends only on what the author wrote:

| kind | written as | reports | who acts |
|---|---|---|---|
| `link` | `https://…`, `mailto:…`, `/route` | `href`, `label`, `node_id` | the host: a browser, a web view, its own router |
| `anchor` | `#id`, the heading written `## Title {#id}` | `href` | md2ui scrolls to the heading itself; never forwarded |
| `agent` | `agent:<slug>?<args>` | `action`, `params`, `label`, `node_id`; the host adds `message_id` | the host forwards it; the agent's **next Markdown response** decides what is shown |
| `checkbox` | `- [ ]`, `[ ]` | `checked` (the state asked for), `index`, `label`, `node_id` | forwarded to the agent, like `agent` |
| `agent` + `checked` | `[[ ]](agent:…)` | as `agent`, plus `checked`, `index`, `label` | the same |
| `copy` | nothing: every code block's copy button (`### Copy Button`) | `text` (the block's source), `label`, `node_id` | the host puts `text` on the clipboard; never forwarded, like `anchor` |

- **The innermost target wins** (`hit_test`): a button or link inside a link card takes its
  own clicks, and the card takes the rest of its area. A pending card still swallows every
  click inside it.
- **An `agent:` link never navigates,** so a host that does not know md2ui ignores it safely.
- **A `~~disabled~~` link, an empty destination and a bare `agent:` report nothing.**
- **There is no `prompt:` scheme.** Free-form prompts use the host's own input.
- **A link inside a sentence** reports one event per link, however many lines it wraps onto.
  Its `node_id` is the text's id plus `#<k>`, the link's ordinal in the text.

**The LLM owns state.** A click never edits the Markdown. The answer, a tick, or a choice shown
as taken (`~~[No](agent:cancel)~~`) arrives as the agent re-sending the same response with the
marks changed. What the host shows in the meantime is **transient** host state (`pending`,
`disabled`, or an optimistic `checked`/`unchecked`), keyed by node id in `VIEW.node_states`. It
paints **colours only**, never a box; the next response replaces it, and that reload keeps the
scroll.

**The regions come from where the ink is decided.** Each clickable region is computed by the
same function its drawer paints with (ADR-400), never re-derived beside it. The rules live in
`render_actions.py`; regions are built once per width, beside the scene, and the window maps a
click back through the inverse of `draw_scene`'s transform (ADR-401's lifetimes).

**What can scroll is reported the same way.** The scene lists each code block clipped at its
right edge, with its box and content width. The pipeline says what can scroll; the host
decides how, and holds the offset. A host that cannot scroll ignores the list: the block stays
clipped, faded and copyable.

## Reason

- **The host knows what a click should do; md2ui does not.** The same answer renders in a
  desktop window, a web view and a chat client, and each routes a url differently. Reporting
  data keeps md2ui one pipeline for all of them.
- **An agent-driven UI needs the LLM to hold the state.** If the host edited the Markdown on a
  tick, there would be two writers of one document, and the agent's next response would
  silently undo the host's edit, or restate it. With one writer, a re-send is the whole
  protocol.
- **A region beside the paint drifts.** Every click area computed separately from its drawer
  would be a second geometry to keep in step: the clipping family ADR-400 closed. Sharing the
  drawer's own function makes a region wrong only when the paint is.

## Alternatives rejected

- **Recording regions while painting** (a collector threaded through `draw_document`). It
  couples the paint to events, and regions would then live as long as the recording, which is
  re-recorded for toggles, images and host state, instead of as long as the scene.
- **The host edits the Markdown on a checkbox tap.** The LLM owns state.
- **Host state that moves geometry.** A pending button that shrank would invalidate the
  regions built for the width, and every frame would need a re-layout.

## Constraint created

- A new clickable thing gets its region from the function its drawer paints with. If no such
  function exists, extract one; do not compute the rectangle a second time.
- Host state may change colours only, and it must reach the recording's key
  (`render_picture.view_state`), or the window keeps replaying the old picture.
- Node ids are positions in the tree today, so host state keyed by id survives a re-send only
  while the structure does. A tick keeps every id (`tests/link_actions_tests.py` pins it); an
  inserted section does not.

## Reconsider when

- **Node ids become content-derived.** Host state and events should then key on those ids.
- **A pending or disabled inline-link style is settled.** Today a pending link inside a
  sentence ignores clicks but looks unchanged.
