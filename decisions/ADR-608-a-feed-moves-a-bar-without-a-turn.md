# ADR-608: A feed moves a bar without a turn; md2ui runs and fetches nothing for it

**Status:** active (prototype: bars, chart rows and authored slots)
**Domain:** CLI tools and shells
**Read when:** you want a shown value to change without the agent spending a turn on it, or are
tempted to have md2ui fetch, poll or run something to get live data. The endpoint, its limits
and its answers are `protocol/README.md` (*Feeds*); timings are `wire_feeds.py`'s, what a post
may say is `wire_feed_posts.py`'s, how a value is written into a slot and checked is
`wire_texts.py`'s, and what a slot is, [ADR-206](ADR-206-a-feed-link-is-a-slot.md).

## Decision

**The agent opens a feed once; a process it already runs posts the values; the server moves the
page.** `mark(message_id, key, value)` (ADR-602) moves a bar, but each move is a turn. That is the
right price when the value falls out of the agent's own work, and the wrong one for a value that
changes on its own: a build, a download, an eval run, a service's metric, an order's status.

- **Push only.** The process posts `name: value` lines, in the page's own spelling, to a local
  URL on the conversation's server. md2ui never fetches a URL or runs a command for a feed.
  Bridging a service is the agent's own one-liner with `curl`.
- **What is fed:** what `mark` moves by its key (a key-value bar, a chart row, in its own unit
  and spelling), and the words of a slot its author marked (ADR-206): text, a chip, or a
  button's label. Text is fed only through a slot, a key line's value too
  (`Placed: [3:41 PM](feed:placed)`); nothing is detected as a stat or a chip to feed.
  Checkboxes and sliders are not fed.
- **The agent tunes nothing it cannot see.** It names what moves (`keys`, `slots`), declares
  each chip slot's values, and may say when the feed is finished (`until`). Left out, `until`
  follows what is fed: `full` for bars alone, `silence` whenever a slot is fed, since a slot is
  never full and a feed that ended with its bars would strand its slots. The tick rate, the
  silence that ends a feed and the lifetime are the server's, derived from what a tick costs and
  how the process posts.
- **The agent is told only what it would act on**, each with the next step: the feed is done,
  silent, posting unusable values, or past its lifetime; its values can no longer be set; the
  window closed. A tick, a single refused post or a page the agent replaced itself is never
  reported.
- **The wire is unchanged.** A tick is an ordinary replacement message (ADR-601), built from the
  server's own copy exactly as `mark` builds one. Posts coalesce: the latest value per key goes
  out once per tick.
- **Text in a post is data.** Its producer is the agent's own process, as trusted as the agent's
  own tool output; ADR-601's "no client string reaches the agent" is about the window and its
  user. What the agent hears quotes a text value.
- **A value is checked by cheap rules, then by its fingerprint.** The rules: a short value of a
  few words, not prose, and no character a reader cannot see. The fingerprint: the value is
  written at the slot's exact offsets, the page regrouped, and the edit kept only when every
  other node, run and target is unchanged, the slot lands where it did, reads back as posted
  and is not styled (read with the grouper's own marker reader, not a character list). A run
  among the slot's own siblings is not compared: a value that only joins or splits such a run
  draws the same. A chip slot takes only its declared values.
- **The post-time verdict is the tick-time verdict.** A post is checked by writing it, with the
  values still pending, into the server's copy as the tick will, and the tick writes that very
  draft; a value the tick would refuse is refused to the process. One race remains: when the
  server's copy changes between a post and its tick (an agent's `mark`, another feed's tick),
  the tick writes the pending values again on the new copy, and if that refuses them the feed
  ends `lost`.
- **A post is refused whole**, and a feed ends itself; afterwards every post is answered 410, so
  the process stops too.
- **A slot is never a bar, and never shares a bar's key.** A slot a bar or a ratio draws, or one
  named as a bar's key on the page in any case, is refused when the feed opens: a bar is fed by
  its key, and a post's `name: value` must say which one it moves.
- **A new page ends the old page's feeds** unless `show(keep_feeds=…)` keeps them. The server
  writes a kept feed's latest values into the new page, so the agent's stale figure never steps
  a bar back.
- **The agent's id survives the ticks.** `MessageLog.head` resolves an id through replacements a
  feed made, so a `mark` on the id the agent carries still lands. It does not resolve through a
  replacement the agent made: that id is stale, as before.
- **The endpoint is loopback only and refuses browsers.** A feed trusts its token, never its
  source, and the process runs under the host's permissions, so the host's own prompts still
  guard it.

## Why

- **Structure stays authored.** Reading a stat or a chip from the grouper's annotations needed a
  character denylist and still let a value change what the page drew; an authored slot says
  exactly which words a feed may write.
- **A slot holds a value, not prose.** The word and character caps keep a post from wrapping or
  widening the page in a common theme; the regroup catches what the caps cannot see (`3/10`
  posted into a chip draws a ratio bar).
- **A value refused late is a feed lost.** Checking at post time against the draft the tick will
  write answers the process that can fix it.

## Considered and rejected

- **md2ui polling a URL, following a file, or running a command.** It would put fetching and
  execution into the server, past the host's permission prompts. Allow-listed URLs were declined
  too: push covers every source a process can reach.
- **The window subscribing to a source.** The frontend fetches nothing.
- **Detected stats and chips** as feed targets, with a character denylist: see *Why*.
- **A value-only frame.** No patch frame until a measurement shows re-sends matter (ADR-601). A
  tick is at most a few re-sends a second.
- **A built-in line pipe (`… | md2ui feed URL`).** It would be a long-running CLI, against
  ADR-600, and `curl` already does the job.

## Constraint created

- **The value checks are the server's.** A text never reaches the page unchecked (the rules,
  then the fingerprint), and a chip never takes a value its feed did not declare.
- **A post is refused when it arrives or not at all**, but for the one race above.
- **A post costs one regroup of the page per value it changes**, off the event loop, one post of
  a feed at a time.
- **Nothing in the Markdown names a source.** A slot names a place; the agent declares a feed
  through the tool.
- **The feed logic lives in `wire_feeds.py`.** The binding only holds it (`Conversation.feeds`)
  and serves its route.

## Reconsider when

- A tick's regroup on the server or reload in the window is felt at the paced rate. A value-only
  frame is then worth its protocol change.
- Bars should glide between ticks. That is the window easing a bar over about the gap between
  updates: a renderer change (ADR-401), invisible to the agent.
- Another component should be fed. It becomes a slot spelling (ADR-206), never a detected
  reading.
- A cap is wrong in use: the character cap wraps a lone value, `MAX_WORD` (chosen for lowercase,
  not the widest glyph) lets a code in capitals or digits widen a page, or the word cap refuses
  a value an author needs.
- A value the sibling-run exception accepts draws differently after all. The fingerprint then
  compares those runs again.
- The race above shows in use: a feed ending `lost` after an agent's `mark`.
- A post's regroup is felt on long pages at the post rate cap.
- A host can deliver a server event to an idle agent. A feed's end could then wake it.
