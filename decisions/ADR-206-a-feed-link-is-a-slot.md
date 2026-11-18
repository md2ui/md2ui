# ADR-206: A feed link is a slot, drawn as its words

**Status:** active (prototype)
**Domain:** markdown grouper
**Read when:** you change how `[text](feed:name)` or `md2ui.feed=name` is read, grouped, drawn,
counted as a target or checked; or you add another scheme that names a place a value fills
(`var:`). The code is `pipeline/grouper_feed_slots.py` and `check_feeds.py`; what a feed writes
into a slot is [ADR-608](ADR-608-a-feed-moves-a-bar-without-a-turn.md).

## Decision

**`[text](feed:name)` is a slot: an authored place a value fills, named by its author. It is
never a link and never a target.** Three spellings: a text slot `[3:53 PM](feed:arrives)`, a
chip slot `` [`Preparing`](feed:status) ``, and a button's label,
`[Track · Preparing](agent:track?id=BS-1043&md2ui.feed=track)`.

- **Respelled before grouping.** Each text and chip slot is written as its label before anything
  else reads the text, so it groups exactly as its plain twin and every tier around it holds
  (`___[x](feed:a)___` is a display value, a backticked label a chip). Style goes outside the
  brackets. A slot inside a code block or an HTML comment is not read.
- **Annotated where it landed (ADR-100).** After grouping, the leaf each slot landed in carries
  `feed_slots`: the slot's name, kind and the range of its words in the node's `content`. A slot
  that cannot be placed is left unannotated.
- **A fed button label** keeps its action, params and ordinal; `md2ui.feed` is split off like
  every `md2ui.*` param, so the agent never hears it.
- **A shell finds a slot by the same scan**: the exact span of its words in the Markdown, so a
  value is written into that span, never searched for.
- **`check` refuses every spelling that gives a feed no one plain place to write** (a bad or
  repeated name; an empty, nested, divided or undrawn slot; a label slot off an `agent:` button;
  a slot a bar draws, or one named as a bar's key), and warns on markup inside the brackets and
  on words that read as a sentence. `feed` refuses the same when it opens, so `check` says it
  before `show`. Each rule is one block in `check_feeds.problems`, so relaxing one is one edit.

## Reason

- **Structure is authored ([ADR-205](ADR-205-structure-is-authored-punctuation-is-text.md)), and the grouper
  annotates what it reads ([ADR-100](ADR-100-grouper-annotates.md)).** The author says which
  words a feed may write; nothing detects a "stat" or a "chip" to feed.
- **A slot is styling-neutral ([ADR-201](ADR-201-styling-is-not-structure.md)).** Kept as a
  link, a slot changes kind: it draws as a link or a button variant and becomes a target.
  Respelled, it is the text it would be without the link, in every tier
  (`data/markdown/tests/tests-feed-slots.md`).
- **Ordinals stay the page's actions (ADR-404, ADR-601).** A slot clicks nothing, so it must
  count nothing.
- **One shape across features.** A slot names a place, never a source. `variable-replacement`'s
  `[stand-in](var:name)` has the same shape; the scanner takes the scheme from one constant
  (`FEED_SCHEME`). `var:` is not built.

## Considered and rejected

- **Keep the link and teach each link site to treat `feed:` as text.** Many edits across the
  grouper and render files, and each site would still detect a slot its own way, so they could
  disagree.

## Constraint created

- **The respell is the first thing the grouper does to the text**, before comments and code
  are taken out; the annotation runs after the task controls and sliders are stamped. A client
  that groups Markdown does both, or its tree and its targets differ.
- **`feed_slots` is part of the AST contract** (`to_dict`/`from_dict`).
- **A slot's words are plain in the source.** A post replaces everything between the brackets,
  so any style must be outside them.

## Reconsider when

- `variable-replacement` is decided: its `var:` scan should share this one.
- An author needs a slot inside a link's label, or a picture's alt text.
