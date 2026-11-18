# ADR-614: A backend may answer a tap with a page of its includes

**Status:** active (prototype)
**Domain:** CLI tools and shells
**Read when:** you write a handler that should show another page, or change how a handled
click is recorded or told to the agent.

Narrows [ADR-612](ADR-612-a-backend-expands-includes-and-answers-clicks-by-changing-data.md)'s
first constraint. How a backend registers one is `protocol/backend.md` (*Includes and
handlers*); the code is `wire_includes.py` (`Show`, `refuse_left`), `Conversation.receive`
and the demo's `handled` (`mcp_demo_told.py`).

## Decision

**A handler may answer a tap with a new page made only of include lines.** It returns
`Show(page)`; every non-blank line of `page` is an include line (ADR-612's spelling) naming a
registered include. The server expands it before anything is sent and records it as a new
message and a new page (no `r`), the page shown from then on; it releases the button (`u`) in
any state, and never queues the click for the agent.

- **One writer per page.** The agent's pages are never edited by it. A page the backend
  shows is made of the backend's includes and nothing else, so its source is a page the agent
  could have sent itself, and `showing` gives it back as include lines. Only the backend's
  handler writes one: the agent registers no routes.
- **The agent still knows.** One digest line, `… the backend showed {{menu category=sides}}
  (now message c7)`, naming any feed the page left ended with. Listens carry the digest, and so
  do the results of `show`, `mark` and `patch`.
- **Ids and Back.** The old page keeps its id and its row in `history`, where the backend's
  page is marked `shown_by: backend`; `MessageLog.head` does not resolve the old id to the
  new page; `show(message_id=…)` brings it back. There is no Back without a turn.
- **The page left cannot pull the user back.** While the page shown is one the backend showed,
  the agent's `mark` or `patch` of another page is refused (`bad_target`), naming the page
  shown and how to bring the old one back on purpose. Once the agent shows a page of its own,
  it edits as before.
- **Failure goes to the agent**, as ADR-612's: a line that is not an include, an unknown name,
  unreadable args or an expander that raises sends nothing (a backend's page is never drawn
  with a failure line); the click is the agent's, and the digest names the action and
  `PageNotDrawn`. Data the handler changed first stays changed.
- **No wire change.** The page is an ordinary message; its `u` names a button no longer shown.

## Why

Many taps in a shop are answered by one include line chosen by the tap alone, a mapping the
shop's prompt otherwise teaches its agent in prose. A deterministic answer should not cost a
turn, and a route the backend knows should not be retyped by the agent.

## Considered and rejected

- Replacing the page shown (`r`): a restructuring is a new message (protocol), and the
  agent's id would resolve to a page it never wrote.
- Rewriting the include's args on the page shown: a second writer of the agent's words.
- Any Markdown from a handler: a second author nobody checks.
- Routes the agent registers: state outside the Markdown, a new tool and grammar, and the
  first tap still costs a turn.
- Links that name their own page (`md2ui.show=`): not now.
- Marking an offer whose slug has a handler: no agent decision depends on it; a tap the backend
  answers reaches the agent as a `handled` line.

## Constraint created

- A backend's page has no words of the agent's. A title or a sentence above an include is
  drawn by the include, or the tap goes to the agent.
- The demo has static includes and no handlers, so navigation without a turn is exercised only
  by a backend that registers one.
- The note results carry with handled taps (`HANDLED_NOTE`) is teaching kept on evals
  (ADR-502): a change to it is measured again.

## Reconsider when

- Back taps measurably cost turns (re-sending the agent's own page by id).
- A server without handlers (the demo, evals) needs navigation without a turn.
