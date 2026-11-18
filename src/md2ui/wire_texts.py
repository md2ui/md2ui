"""A feed's slots: the text its author marked for a feed to move (ADR-608).

A slot is authored, never detected, and the grouper annotates it (ADR-100): a
text ``[3:53 PM](feed:arrives)``, a chip `` [`Preparing`](feed:status) ``, or a
button's whole label, ``[Track · Preparing](agent:track?id=BS-1043&md2ui.feed=track)``.
The grouper draws each as its text and says where it landed
(``grouper_feed_slots``); this module writes a new value into one and checks it.

A post is data from the agent's own process, written into a page, so a value is
checked twice. First by cheap rules (:func:`check_text`): no character a reader
cannot see or that breaks a line, at most :data:`MAX_TEXT` characters and
``MAX_SLOT_WORDS`` words (a value, not prose), no word over :data:`MAX_WORD`. Then by its fingerprint (:func:`set_slot_markdown`):
the value goes in at the slot's own offsets, the page is regrouped, and the edit
is kept only when that slot alone changed -- every other node, run and target as
before, a label's button keeping its action, params and ordinal -- and it reads
back as posted, in one plain run: the author styles a slot, a post only supplies
words.
"""

from __future__ import annotations

import dataclasses
import unicodedata
from collections.abc import Mapping

from md2ui import session
from md2ui.pipeline.grouper_feed_slots import (
    MAX_SLOT_WORDS,
    FeedSlot,
    slot_words,
    feed_slots,
    slots_in_tree,
    with_value,
)
from md2ui.pipeline.render_actions import Target, action_targets
from md2ui.wire_bars import set_bar_markdown
from md2ui.wire_frames import FrameError

# Characters. A chosen figure, not a fit: on the test theme at 600 px a lone stat's
# display value takes a second line from about 31 characters, so 40 may wrap once,
# never three times.
MAX_TEXT = 40
# Characters in one unbroken word. On the test theme at width 600, a stat's
# display value `___word___` under a caption widens the page past its 680 px
# raster from 14 `W`, 15 `M`, 22 `8` and 25 `a`. The limit follows the lowercase
# threshold, not the worst-case glyph.
MAX_WORD = 24
# What a reader cannot see, or what breaks the line: controls, formats (bidi
# overrides, zero-width characters, soft hyphen), separators, private use, unassigned.
_UNSEEN = {"Cc": "a control", "Cf": "a format", "Zl": "a line break",
           "Zp": "a line break", "Co": "a private-use", "Cn": "an unassigned"}  # fmt: skip
_EMOJI = ("So", "Sk")  # a pictograph, or a skin tone
# Statistics the grouper derives from a node's text or its children's types: a
# longer value changes them all the way up, and they draw nothing of their own.
_DERIVED = frozenset(
    (
        "children",
        "fingerprint_hash",
        "avg_word_count",
        "text_length_category",
        "content_length_category",
        "child_types",
        "child_type_counts",
    )
)
# What a slot's own node may change: its text (a label's too), what the detector
# reads in it, the slot's offsets and, read again (a word is a segment in a colon
# column), its type.
_OWN = frozenset(("content", "link_label", "data_points", "type", "feed_slots"))
HOW = (
    "mark a value where it is drawn: [3:53 PM](feed:arrives), a chip "
    "[`Preparing`](feed:status), a button's label with ?md2ui.feed=track"
)

Path = tuple[int, ...]


def _pictograph(ch: str) -> bool:
    return bool(ch) and unicodedata.category(ch) in _EMOJI


def _joins(value: str, at: int) -> bool:
    """U+200D between two pictographs (the first may carry U+FE0F, a mark, not
    a format): the joiner of an emoji sequence, so a cook (👩 U+200D 🍳) passes, a lone one not."""
    before = value[at - 1] if at else ""
    after = value[at + 1] if at + 1 < len(value) else ""
    joined = _pictograph(before) or before == "\ufe0f"
    return value[at] == "\u200d" and joined and _pictograph(after)


def check_text(name: str, value: object) -> str:
    """*value* if it can be only text on the page, else refused (``bad_value``)
    saying what to fix, so the process can."""
    if not isinstance(value, str):
        raise FrameError("bad_value", f"{name!r}: {value!r} is not text")
    if not value or value != value.strip():
        raise FrameError("bad_value", f"{name!r}: post a non-empty, unpadded text")
    for at, ch in enumerate(value):
        kind = _UNSEEN.get(unicodedata.category(ch))
        if kind and not _joins(value, at):
            raise FrameError(
                "bad_value",
                f"{name!r}: {value[:80]!r} holds U+{ord(ch):04X}, {kind} "
                "character; post only what is drawn",
            )
    if len(value) > MAX_TEXT:
        raise FrameError("bad_value", f"{name!r}: over {MAX_TEXT} characters")
    if slot_words(value) > MAX_SLOT_WORDS:  # a slot is a value, not prose
        raise FrameError(
            "bad_value",
            f"{name!r}: {slot_words(value)} words; a slot holds a value of at most "
            f"{MAX_SLOT_WORDS} words, not a sentence",
        )
    if max(len(word) for word in value.split()) > MAX_WORD:
        raise FrameError(
            "bad_value", f"{name!r}: a word over {MAX_WORD} characters; add a space"
        )
    return value


def page_slots(markdown: str) -> dict[str, list[FeedSlot]]:
    """Every slot *markdown* marks, by name, in document order."""
    out: dict[str, list[FeedSlot]] = {}
    for slot in feed_slots(markdown):
        out.setdefault(slot.name, []).append(slot)
    return out


def find_slot(markdown: str, name: str) -> FeedSlot:
    """The one slot *markdown* marks as *name*, or a refusal (``bad_target``)
    listing those it marks and saying how to mark one."""
    found = page_slots(markdown)
    if len(found.get(name, ())) == 1:
        return found[name][0]
    why = "names more than one slot" if name in found else "names no slot"
    here = ", ".join(found) or "none"
    raise FrameError("bad_target", f"{name!r} {why}; slots here: {here}. To {HOW}")


def _frame(node: dict, skip: set[Path], path: Path = ()) -> tuple:
    """What *node* draws: each node's own fields, less what its text derives,
    and its children's frames. A slot's node, at a path in *skip*, may change
    its text and what is read in it; not how it draws."""
    mine = _DERIVED | (_OWN if path in skip else set())
    own = tuple(sorted((k, repr(v)) for k, v in node.items() if k not in mine))
    kids = node.get("children", [])
    return own, tuple(_frame(c, skip, (*path, i)) for i, c in enumerate(kids))


def _runs(node, path: Path = ()) -> list:
    """Which siblings grid together, and each orphan gridded with them: the run
    facts ``to_dict()`` leaves out (``scripts/grouper_snapshot.py``)."""
    out: list = [(path, "orphan")] if node.orphan_grid else []
    for run in (node.repeated_children or {}).values():
        if len(run) > 1:
            at = [i for i, c in enumerate(node.children) if any(c is m for m in run)]
            out.append((path, at))
    for i, child in enumerate(node.children):
        out += _runs(child, (*path, i))
    return out


def _paths(node: dict, path: Path = (), out: dict | None = None) -> dict[str, Path]:
    out = {} if out is None else out
    out[node.get("node_id", "")] = path
    for i, child in enumerate(node.get("children", [])):
        _paths(child, (*path, i), out)
    return out


def _targets(tree: dict, name: str) -> list:
    """Every target, the button whose label is slot *name* without its label:
    a post changes that and nothing else of it, its ordinal included."""

    def own(t: Target) -> tuple:
        a = t.action
        if a is not None and ("feed", name) in a.hints:
            a = dataclasses.replace(a, label="")
        return t.disabled, a

    return [own(t) for t in action_targets(tree)]


def _read(markdown: str, kit: session.GroupingKit, name: str) -> tuple:
    """What an edit of slot *name* must leave alone, where the slot landed in
    the tree, and the tree."""
    ast = session.group_shared(markdown, kit)
    tree = ast.to_dict() if ast is not None else {}
    paths = _paths(tree)
    at = [(paths.get(nid), a) for nid, a in slots_in_tree(tree) if a["name"] == name]
    frame = _frame(tree, {p for p, _a in at if p is not None})
    # The slot and its own siblings may form a run or not as its words change
    # (case 2c: `Soon` beside a caption is a run of two words, `3:53 PM` not):
    # that draws the same, every node's fields and targets being equal. Runs
    # anywhere else are compared.
    beside = {p[:-1] for p, _a in at if p}
    runs = [r for r in (_runs(ast) if ast is not None else []) if r[0] not in beside]
    return (frame, runs, _targets(tree, name)), at, tree


def _node(tree: dict, path: Path) -> dict:
    for i in path:
        tree = tree["children"][i]
    return tree


def set_slot_markdown(
    markdown: str, name: str, value: str, kit: session.GroupingKit
) -> str:
    """*markdown* with slot *name* reading *value*, and nothing else changed.

    Refused (``FrameError``): a value :func:`check_text` refuses, a name no slot
    or more than one is marked with, and an edit whose regrouping changes
    anything but that slot, or does not draw it as *value* in one plain run.
    """
    check_text(name, value)
    slot = find_slot(markdown, name)
    if slot.value == value:
        return markdown
    candidate = with_value(markdown, slot, value)
    before, at, _tree = _read(markdown, kit, name)
    after, at2, tree2 = _read(candidate, kit, name)
    if before != after or [p for p, _a in at] != [p for p, _a in at2]:
        raise FrameError(
            "bad_value",
            f"{name!r}: {value!r} would change the page beyond its slot; post a "
            "plain value of the kind the slot holds",
        )
    if any(a["styled"] for _p, a in at2):
        raise FrameError(
            "bad_value",
            f"{name!r}: {value!r} would be styled; post plain words, the page "
            "styles them",
        )
    drawn = [
        _node(tree2, p).get("content", "")[a["start"] : a["end"]]
        for p, a in at2
        if p is not None
    ]
    if drawn != [value] or find_slot(candidate, name).value != value:
        raise FrameError("bad_value", f"{name!r}: {value!r} would not read as posted")
    return candidate


def set_fed_markdown(
    markdown: str, values: Mapping[str, float | str], kit: session.GroupingKit
) -> str:
    """A feed's values written into *markdown*: a text into its slot, a figure
    into its bar (``wire_bars.set_bar_markdown``)."""
    for key, value in values.items():
        if isinstance(value, str):
            markdown = set_slot_markdown(markdown, key, value, kit)
        else:
            markdown = set_bar_markdown(markdown, key, value, kit)
    return markdown
