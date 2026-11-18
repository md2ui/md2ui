"""Feed slots: the places on a page a feed writes words into, named by the author.

A slot is authored, never detected: ``[3:53 PM](feed:arrives)`` is a
text slot named ``arrives``; `` [`Preparing`](feed:status) `` a chip slot; and an
``agent:`` button whose destination carries ``md2ui.feed=<name>`` is a label slot,
``[Track · Preparing](agent:track?id=BS-1043&md2ui.feed=track)``. A slot names a
place, never a source (ADR-206; the feed that writes it, ADR-608).

**A text or chip slot is drawn exactly as its label would be without the link.**
The grouper writes each one as its label before anything else reads the text
(:func:`respell`), so every tier the author put around it holds as it would for
plain words: ``___[x](feed:a)___`` is a display value, ``_[x](feed:a)_`` a caption,
``**…**`` bold, ``~~…~~`` struck, and a backticked label a chip the theme pins by
its word. It is never a link and never a target. A label slot stays the button it
is: only its words are the feed's.

After grouping, :func:`stamp` annotates the leaf each slot landed in (ADR-100):
``feed_slots``, one ``{"name", "kind", "start", "end"}`` per slot, the range of
the slot's words in that node's ``content``. Words are placed by document order,
which grouping keeps, as whole words, after as many drawn copies as the Markdown
holds between the slot before and this one. A slot that cannot be placed (its
words were cut by a divider, rewritten, or are drawn nowhere) is left
unannotated, and ``check`` says so.

The same scan answers a shell (:func:`feed_slots`): every slot of a page with the
exact span of its words in the Markdown, so a value is written into that span
(:func:`with_value`) rather than searched for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from md2ui.pipeline.grouper_code_blocks import (
    _FENCE_OPEN_RE,
    extract_code_blocks,
)
from md2ui.pipeline.grouper_inline_marks import _marker_runs
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.render_text import LINK_DESTINATION, LINK_LABEL, _LINK_LABEL
from md2ui.utils.image_params import destination_url, split_md2ui_params

# The scheme of a text or chip slot, and the `md2ui.` param of a label slot.
FEED_SCHEME = "feed:"
FEED_HINT = "feed"
# What a slot may be called. A destination naming anything else is still drawn as
# its words (it is a slot), and `check` refuses the name.
NAME_RE = re.compile(r"[A-Za-z0-9_-]+")
# A slot is a value, not prose: a few words, no sentence.
MAX_SLOT_WORDS = 4


def slot_words(text: str) -> int:
    """How many words *text* holds: whitespace tokens with a letter or a digit, so
    a lone ``·``, ``-``, ``—`` or ``|`` is no word."""
    return sum(1 for token in text.split() if any(c.isalnum() for c in token))


def reads_like_prose(text: str) -> bool:
    """True when *text* reads as a sentence rather than a value: more than
    ``MAX_SLOT_WORDS`` words (:func:`slot_words`), or it ends in sentence
    punctuation."""
    return slot_words(text) > MAX_SLOT_WORDS or text.rstrip().endswith(
        (".", "!", "?", "…")
    )


# One pass, left to right: an escape, a code span or a link, whichever starts
# first. A label holds no link of its own (render_text's `_LINK_LABEL`), so in a
# link written inside another's label the inner one is the link, as in CommonMark.
# A code span stays on its line, as the grouper reads one: a stray backtick never
# pairs with one lines below and hides the slots between.
_SCAN_RE = re.compile(
    r"(?P<esc>\\.)"
    r"|(?P<code>`+)(?P<code_body>[^\n]*?[^`\n])(?P=code)(?!`)"
    rf"|(?<!!)\[(?P<label>(?:{_LINK_LABEL})?)\]\((?P<dest>{LINK_DESTINATION})\)"
)
# A link whose label may hold another link: what an inner slot is nested in.
# A picture's alt text is not a label; a slot there is drawn nowhere.
_OUTER_LINK_RE = re.compile(rf"(?<!!)\[(?:{LINK_LABEL})\]\((?:{LINK_DESTINATION})\)")
_CHIP_RE = re.compile(r"`([^`]+)`")
# Text a search for a slot's words must not find: where a link points, a
# picture, a code block's stand-in. They are not drawn as words.
_UNDRAWN_RE = re.compile(
    rf"!\[(?:{LINK_LABEL})?\]\((?:{LINK_DESTINATION})\)"
    rf"|(?<=\])\((?:{LINK_DESTINATION})\)"
    r"|⟦md2ui-code-\d+⟧"
)


@dataclass(frozen=True, slots=True)
class FeedSlot:
    """One slot, where the scanned Markdown spells it."""

    name: str  # as written; NAME_RE says whether it is a name at all
    kind: str  # "text" | "chip" | "label"
    value: str  # the words: a chip's without its backticks, a label's whole
    start: int  # markdown[start:end] == value
    end: int
    construct: tuple[int, int]  # the whole [label](destination)
    nested: bool = False  # written inside another link's label


@dataclass(slots=True)
class Respelled:
    """What :func:`respell` hands the grouper to :func:`stamp` the finished tree."""

    slots: list[FeedSlot]
    # Per text or chip slot, in order: how many times its words appear drawn
    # between the slot before it and itself, in the respelled text.
    skips: list[int]


def _masked(text: str) -> list[tuple[int, int]]:
    """The spans of *text* grouping takes out before any slot is read: HTML
    comments and code blocks, found by the grouper's own extraction."""
    spans = [m.span() for m in re.finditer(r"<!--.*?-->", text, re.DOTALL)]
    _, specs = extract_code_blocks(text)
    cursor = {True: 0, False: 0}
    for spec in specs.values():
        fenced = bool(_FENCE_OPEN_RE.match(spec.raw.splitlines()[0]))
        at = text.find(spec.raw, cursor[fenced])
        if at >= 0:
            spans.append((at, at + len(spec.raw)))
            cursor[fenced] = at + len(spec.raw)
    return spans


def _slot(m: re.Match[str], outer: list[tuple[int, int]]) -> FeedSlot | None:
    """The slot a link match is, or None for any other link."""
    url, hints = split_md2ui_params(destination_url(m.group("dest")))
    if url[: len(FEED_SCHEME)].lower() == FEED_SCHEME:
        kind, name = "text", url[len(FEED_SCHEME) :]
    elif FEED_HINT in hints:
        kind, name = "label", hints[FEED_HINT]
    else:
        return None
    start, end = m.span("label")
    chip = _CHIP_RE.fullmatch(m.group("label"))
    if chip is not None:
        kind = "chip" if kind == "text" else kind
        start, end = start + 1, end - 1
    a, b = m.span()
    nested = any(x <= a and b <= y and (x, y) != (a, b) for x, y in outer)
    return FeedSlot(name, kind, m.string[start:end], start, end, (a, b), nested)


def _scan(text: str, masked: list[tuple[int, int]]) -> list[FeedSlot]:
    """Every slot in *text* outside the *masked* spans, in document order."""
    outer = [m.span() for m in _OUTER_LINK_RE.finditer(text)]
    out = []
    for m in _SCAN_RE.finditer(text):
        if m.group("label") is None or any(a <= m.start() < b for a, b in masked):
            continue
        slot = _slot(m, outer)
        if slot is not None:
            out.append(slot)
    return out


def feed_slots(markdown: str) -> list[FeedSlot]:
    """Every slot of a page, in document order, with the span of its words in
    *markdown*, the exact string the page is grouped from."""
    return _scan(markdown, _masked(markdown)) if "](" in markdown else []


def with_value(markdown: str, slot: FeedSlot, value: str) -> str:
    """*markdown* with *value* written in place of *slot*'s words."""
    return markdown[: slot.start] + value + markdown[slot.end :]


def respell(text: str) -> tuple[str, Respelled]:
    """*text* with each text and chip slot written as its label (a chip keeps its
    backticks), and what :func:`stamp` needs to find them in the tree."""
    if "](" not in text:
        return text, Respelled([], [])
    masked = _masked(text)
    slots = _scan(text, masked)
    # What a count of drawn words must not see: code and comments, blanked.
    seen = list(text)
    for a, b in masked:
        seen[a:b] = " " * (b - a)
    blank = "".join(seen)
    pieces: list[str] = []
    skips: list[int] = []
    last = 0
    for slot in slots:
        if slot.kind == "label":
            continue
        a, b = slot.construct
        # Only slots are respelled, so what lies between two is as written.
        seen_words = _words(slot.value).findall(_UNDRAWN_RE.sub(" ", blank[last:a]))
        skips.append(len(seen_words))
        chip = slot.kind == "chip"
        pieces += [text[last:a], text[slot.start - chip : slot.end + chip]]
        last = b
    if not pieces:
        return text, Respelled(slots, skips)
    return "".join(pieces) + text[last:], Respelled(slots, skips)


def _leaves(node: MarkdownGroupNode, out: list[MarkdownGroupNode]) -> list:
    """Every node with drawn words, in document order."""
    if node.content and node.type != NodeType.CODE_BLOCK:
        out.append(node)
    for child in node.children:
        _leaves(child, out)
    return out


def _drawn(content: str) -> str:
    """*content* with what is not drawn as words blanked, offsets kept."""
    return _UNDRAWN_RE.sub(lambda m: "\0" * len(m.group()), content)


def _unescaped(value: str) -> str:
    return re.sub(r"\\(.)", r"\1", value)


def stamp(root: MarkdownGroupNode | None, respelled: Respelled | None) -> None:
    """Annotate the leaf each slot landed in with ``feed_slots``."""
    if root is None or respelled is None or not respelled.slots:
        return
    leaves = _leaves(root, [])
    drawn = [_drawn(leaf.content) for leaf in leaves]
    at, offset = 0, 0
    words = [s for s in respelled.slots if s.kind != "label"]
    for slot, skip in zip(words, respelled.skips, strict=True):
        found = _find(drawn, at, offset, slot.value, skip)
        if found is None and "\\" in slot.value:
            found = _find(drawn, at, offset, _unescaped(slot.value), skip)
        if found is None:
            continue
        at, start, offset = found
        _annotate(leaves[at], slot, start, offset)
    labels = [s for s in respelled.slots if s.kind == "label"]
    for leaf in leaves if labels else ():
        for slot in _scan(leaf.content, []):
            if slot.kind == "label" and labels and labels[0].name == slot.name:
                labels.pop(0)
                _annotate(leaf, slot, slot.start, slot.end)


def _words(value: str) -> re.Pattern[str]:
    """*value* as whole words: never the inside of a longer word, so the slot
    ``x`` is not found in ``Text``. A letter or digit may not touch either end."""
    return re.compile(rf"(?<![^\W_]){re.escape(value)}(?![^\W_])")


def _find(
    drawn: list[str], at: int, offset: int, value: str, skip: int
) -> tuple[int, int, int] | None:
    """``(leaf, start, end)`` of *value*'s next drawn occurrence from the cursor,
    after *skip* others."""
    if not value:
        return None
    words = _words(value)
    for i in range(at, len(drawn)):
        for m in words.finditer(drawn[i], offset if i == at else 0):
            if not skip:
                return i, m.start(), m.end()
            skip -= 1
    return None


def _annotate(node: MarkdownGroupNode, slot: FeedSlot, start: int, end: int) -> None:
    entry = {"name": slot.name, "kind": slot.kind, "start": start, "end": end}
    node.feed_slots = (*node.feed_slots, entry)


def styled(text: str) -> bool:
    """True when *text* is not one plain run: it holds an inline mark the grouper
    reads (an emphasis, strike or code run, a link or an autolink)."""
    return (
        "`" in text
        or bool(_marker_runs(text))
        or "](" in text
        or bool(re.search(r"<[A-Za-z][A-Za-z0-9+.-]*:", text))
    )


def slots_in_tree(tree: dict) -> list[tuple[str, dict]]:
    """``(node_id, slot)`` for every placed slot of a grouped page (``to_dict``),
    in document order. Each slot is ``{"name", "kind", "start", "end"}`` (its words
    are ``content[start:end]``) and ``styled``: those words are not one plain
    run."""
    out: list[tuple[str, dict]] = []

    def walk(nd: dict) -> None:
        for slot in nd.get("feed_slots", ()):
            words = nd.get("content", "")[slot["start"] : slot["end"]]
            out.append((nd.get("node_id", ""), {**slot, "styled": styled(words)}))
        for child in nd.get("children", ()):
            walk(child)

    walk(tree)
    return out
