---
name: md2ui-opened
description: What to show when the user only opens md2ui, with no request — what is new for them, never a tour.
---

# Opened with no request

When the user only opens md2ui — "open md2ui", "show me md2ui", nothing else — there is no
question yet, so answer this one: *what is new for them?* Read the sources that answer it
best — the ones this conversation or the user's recent activity points to, such as a task
your memory or the session says is still pending, and two or three of the connected tools that
hold what is new today, such as the calendar, the mail that just came in, the weather where
they are or what they last played — and give every source you read a card of
its own, however many came back, led by what matters most in it, as the tiles of a dashboard
are (`pages/widget-board`). Leading is size, not
selection: every figure a source returned stays on its card, smaller lines under the lead (a
delivery's three stops under its arrival time, a meeting's room and dial-in under its hour).
Each takes the shape of
what came back, usually a pattern: `empty-state` for a source with nothing in it, `agenda` for
events, `inbox` for messages, `status-list` for items that each stand somewhere, `kpis` for a
few figures, `now-playing` for a track. Give each the buttons for what it can do. A source you
could not read keeps its section and says why, with the way to connect it (`connect-account`).

Every other tool connected is named after them, by its own name, read only when the user picks
it, so the user sees everything they have connected: each with one thing it can do, as an
action, and the way to connect one that needs a sign-in. Two tools that do the same thing are
each named and each keep their action, and none
is left out: not one that needs a sign-in, not one unrelated to what you found, and not one
whose own rules say to read it only when asked. Their shape follows what you have for them, as
any section's does: a few actions can stand in a row, tools that each need a word on what they
do are a list or tiles (`shortcuts`). Close with a centred row of suggestions drawn from what
you found, after `***`, which ends the section above it (the row would otherwise join it); it
closes one heading level, so after `###` cards inside a `##` write it twice:

```md
***

... [Plan my week](agent:suggest?q=week) [Reply to Ana](agent:suggest?q=reply-ana) ...
```

Show only what you read. A count is one you counted in what came back, and a status one the
source states: a commit message or a title is not a status. What no source said stays out, and
so does a tour of md2ui. When the user asks for something, answer that instead.
