"""What `check` says about feed slots (``grouper_feed_slots``).

A slot is a place the author named for a feed to write words into: a text slot
``[3:53 PM](feed:arrives)``, a chip slot `` [`Preparing`](feed:status) ``, or the
label of an ``agent:`` button carrying ``md2ui.feed=<name>``. Each spelling that
would not give the feed one plain place to write is told:

* ``feed-name`` (error): a name that is not letters, digits, ``_`` and ``-``;
  the slot is still drawn as its words;
* ``feed-repeated`` (error): two slots with one name;
* ``feed-empty`` (error): a slot with no words, which draws nothing;
* ``feed-not-agent`` (error): ``md2ui.feed`` on a link that is not ``agent:``, or
  on a choice option;
* ``feed-nested`` (error): a slot written inside another link's label;
* ``feed-divided`` (error): a slot whose words hold a spaced divider, which cuts
  them in two;
* ``feed-unplaced`` (error): a slot whose words are drawn nowhere (a picture's
  alt text) or were cut;
* ``feed-styled`` (warning): markup inside a slot's brackets, which the first
  post replaces;
* ``feed-prose`` (warning): a slot whose words read as a sentence (more than
  ``MAX_SLOT_WORDS`` words, or sentence punctuation at the end): a slot is a value;
* ``feed-bar`` (error): a slot whose words draw a bar or a ratio, which a feed
  moves by its key, so the slot can never take a post (``feed`` refuses it too);
* ``feed-key`` (error): a slot named as a bar's key on the page, in any case,
  which ``feed`` refuses: a post's ``name: value`` would not say which it moves.

Each rule is one block below, so relaxing one is one edit. Each issue is
``(level, code, message, x)``; ``x`` is always None, as a slot is no target.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from md2ui.pipeline.grouper_feed_slots import (
    FEED_HINT,
    MAX_SLOT_WORDS,
    NAME_RE,
    FeedSlot,
    feed_slots,
    reads_like_prose,
    slots_in_tree,
    styled,
)
from md2ui.pipeline.render_choices import CHOICE_HINT
from md2ui.pipeline.render_text import LINK_DESTINATION
from md2ui.utils.image_params import destination_url, split_md2ui_params
from md2ui.wire_bars import bar_keys

Issue = tuple[str, str, str, int | None]

# A spaced mark that divides a line: the grouper's separators and its spring.
_DIVIDER_RE = re.compile(r" (?:\||-|:|\.\.\.|\+{3,5}) ")
_DESTINATION_RE = re.compile(rf"\]\(({LINK_DESTINATION})\)$")


def _spelled(slot: FeedSlot) -> str:
    return f"`{slot.value}`" if slot.value else f"`{slot.name}`"


def _not_agent(markdown: str, slot: FeedSlot) -> str | None:
    """Why a label slot's link cannot carry a fed label, or None."""
    m = _DESTINATION_RE.search(markdown[slice(*slot.construct)])
    url, hints = split_md2ui_params(destination_url(m.group(1) if m else ""))
    if url[:6].lower() != "agent:":
        return "only an `agent:` button's label can be fed"
    if CHOICE_HINT in hints:
        return "a choice option's label names the option, so it cannot be fed"
    return None


def problems(markdown: str, tree: dict) -> Iterator[Issue]:
    """Every issue the feed slots of a grouped page raise."""
    slots = feed_slots(markdown)
    if not slots:
        return
    placed = slots_in_tree(tree)
    names: dict[str, int] = {}
    for slot in slots:
        names[slot.name] = names.get(slot.name, 0) + 1
    for name, count in names.items():
        if count > 1:
            yield (
                "error",
                "feed-repeated",
                f"{count} slots are named `{name}`: a slot names one place. Give "
                "each its own name.",
                None,
            )
    for slot in slots:
        hint = f"md2ui.{FEED_HINT}" if slot.kind == "label" else "feed:"
        if not NAME_RE.fullmatch(slot.name):
            yield (
                "error",
                "feed-name",
                f"Slot {_spelled(slot)} is named `{slot.name}`: a {hint} name is "
                "letters, digits, `_` and `-` only.",
                None,
            )
        if not slot.value.strip():
            yield (
                "error",
                "feed-empty",
                f"Slot `{slot.name}` has no words, so it draws nothing until a "
                "post. Write the value it shows now inside the brackets.",
                None,
            )
            continue
        if slot.kind == "label" and (why := _not_agent(markdown, slot)):
            yield ("error", "feed-not-agent", f"`{slot.value}`: {why}.", None)
        if slot.nested:
            yield (
                "error",
                "feed-nested",
                f"Slot `{slot.name}` is written inside another link's label. To "
                "feed a button's label, write `md2ui.feed=<name>` in the button's "
                "destination instead.",
                None,
            )
        if _DIVIDER_RE.search(f" {slot.value} "):
            yield (
                "error",
                "feed-divided",
                f"Slot `{slot.name}`, {_spelled(slot)}, holds a spaced divider, "
                "which cuts its words in two. Write it without one.",
                None,
            )
        elif not slot.nested and not any(s["name"] == slot.name for _, s in placed):
            yield (
                "error",
                "feed-unplaced",
                f"Slot `{slot.name}`, {_spelled(slot)}, is not drawn as words a "
                "feed can write: a slot belongs in a line, a cell or a button's "
                "label, not in a picture's alt text.",
                None,
            )
        if "`" in slot.value if slot.kind == "chip" else styled(slot.value):
            yield (
                "warning",
                "feed-styled",
                f"Slot `{slot.name}`, {_spelled(slot)}, is styled inside its "
                "brackets, and the first post replaces that style with plain "
                "words. Style the slot outside its brackets, as in "
                "`**[words](feed:name)**`.",
                None,
            )
        if reads_like_prose(slot.value):
            yield (
                "warning",
                "feed-prose",
                f"Slot `{slot.name}`, {_spelled(slot)}, reads as a sentence (more "
                f"than {MAX_SLOT_WORDS} words, or a full stop): mark the value, not "
                "the sentence, as in `arriving around [7:58 PM](feed:arrives)`.",
                None,
            )
    words = {slot.name: slot.value for slot in slots}
    drawn = dict(barred(tree))
    for name, key in drawn.items():
        yield ("error", "feed-bar", unfed(name, words.get(name, ""), key), None)
    keys = {key.casefold(): key for key in bar_keys(tree)}
    for name in dict.fromkeys(slot.name for slot in slots):
        if name not in drawn and name.casefold() in keys:
            yield ("error", "feed-key", clashes(name, keys[name.casefold()]), None)


def unfed(name: str, words: str, key: str | None) -> str:
    """Why the slot *name* drawn by a bar takes no post, and what to write."""
    if key is None:
        return (
            f"Slot `{name}`, `{words}`, draws a bar or a ratio, which no slot can "
            "move. Write it without the slot."
        )
    return (
        f"Slot `{name}` draws the bar `{key}`, which a feed moves by its key, so "
        f"the slot can never take a post. Write the bar without the slot, "
        f'`{key}: {words}`, and feed it by its key: `keys=["{key}"]`.'
    )


def clashes(name: str, key: str) -> str:
    """Why the slot *name* may not share the bar *key*'s name, in any case."""
    return (
        f"Slot `{name}` is named as the bar `{key}`: a post's `{name}: value` "
        "would not say which it moves. Rename the slot."
    )


def barred(node: dict, key: str | None = None, under: bool = False) -> Iterator:
    """``(name, key)`` for each slot drawn by a datapoint display (a bar, a
    ratio), *key* being the pair's it is drawn in, or None."""
    if node["type"] == "key-value":
        key = next(
            (
                c["content"].strip("*_` ")
                for c in node["children"]
                if c["type"] == "key"
            ),
            key,
        )
    under = under or bool(node.get("datapoint_display"))
    if under:
        yield from ((slot["name"], key) for slot in node.get("feed_slots", ()))
    for child in node.get("children", ()):
        yield from barred(child, key, under)
