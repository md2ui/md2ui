"""Slider tokens that become explicit drawing-element leaves.

``[65%]`` is a plain slider and ``[[65%]](agent:set-volume)`` is a slider
carrying an action.  Recognition lives in the grouper so rendering and wire
target enumeration consume one semantic payload without re-parsing Markdown.
"""

import re
from typing import NamedTuple

from md2ui.pipeline.grouper_drawing_elements import (
    _LINE_HOLDERS,
    _become,
    muted_wrap,
)
from md2ui.pipeline.grouper_content_edits import edit_content, regex_edits
from md2ui.pipeline.grouper_ids import IdMint, _inherit_glue
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.render_text import LINK_DESTINATION


# Two spellings of the same control, and the difference is the DOMAIN. `[65%]` is
# a percentage, 0 through 100. `[3/10]` is the interactive twin of the ratio bar
# `68/100`, and its denominator authors the range -- so a quantity of ten is ten
# steps, and the domain travels in the document, where the server can see it.
_PERCENT = r"(?:100(?:\.0+)?|\d{1,2}(?:\.\d+)?)%"
_RATIO = r"\d{1,4}(?:\.\d+)?/\d{1,4}"
_VALUE = f"(?:{_PERCENT}|{_RATIO})"
_LINKED_SLIDER_RE = re.compile(rf"\[\[({_VALUE})]\]\(((?=[^)]){LINK_DESTINATION})\)")
_SLIDER_RE = re.compile(rf"\[({_VALUE})]")
_SKIP_LEAVES = frozenset(
    {NodeType.IMAGE, NodeType.LINK, NodeType.INLINE_CODE, NodeType.DRAWING_ELEMENT}
)
_ESCAPED_PREFIX = "\ue122"
_ESCAPED_PREFIX_RE = re.compile(_ESCAPED_PREFIX)


def protect_escaped_sliders(text: str) -> str:
    """Hide escaped slider openings while CommonMark escapes are resolved: every
    spelling, a percentage or a ratio, its closing bracket escaped or not."""
    return re.sub(rf"\\\[(?={_VALUE}\\?])", _ESCAPED_PREFIX, text)


def restore_escaped_sliders(node: MarkdownGroupNode) -> None:
    if node.content:
        edit_content(node, regex_edits(_ESCAPED_PREFIX_RE, "[", node.content))
    for child in node.children:
        restore_escaped_sliders(child)


def _code_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for i, char in enumerate(text):
        if char != "`" or (i > 0 and text[i - 1] == "\\"):
            continue
        if start is None:
            start = i
        else:
            ranges.append((start, i + 1))
            start = None
    return ranges


def _decimals(raw: str) -> int:
    """How precisely the AUTHOR wrote the value: ``65`` is whole percents, ``40.5``
    is tenths. A drag reports at that granularity, because a pointer position is
    not a decision — without this the agent is handed ``75.62937500000001`` and
    has to guess how much of it to believe."""
    _, _, fraction = raw.partition(".")
    return len(fraction)


class _Hit(NamedTuple):
    """One slider token, read: where it is, and the domain the author gave it."""

    start: int
    end: int
    value: float
    maximum: float
    unit: str
    decimals: int
    url: str | None


def _read(raw: str) -> tuple[float, float, str, int] | None:
    """``(value, maximum, unit, decimals)``, or None for a token that is not one.

    A ratio whose numerator exceeds its denominator is declined rather than
    clamped: the author wrote something that cannot mean a position on a track,
    so it stays text, exactly as ``[101%]`` already does.
    """
    if raw.endswith("%"):
        return float(raw[:-1]), 100.0, "%", _decimals(raw[:-1])
    top, _, bottom = raw.partition("/")
    maximum = float(bottom)
    if maximum <= 0 or float(top) > maximum:
        return None
    return float(top), maximum, "", _decimals(top)


def _hits(text: str) -> list[_Hit]:
    code = _code_ranges(text)
    linked = list(_LINKED_SLIDER_RE.finditer(text))
    hits: list[_Hit] = []

    def blocked(start: int, end: int) -> bool:
        return any(a < end and start < b for a, b in code) or (
            start > 0 and text[start - 1] in ("\\", "!")
        )

    for match in linked:
        read = _read(match.group(1))
        if read is not None and not blocked(match.start(), match.end()):
            hits.append(_Hit(match.start(), match.end(), *read, match.group(2)))
    linked_ranges = [(hit.start, hit.end) for hit in hits]
    for match in _SLIDER_RE.finditer(text):
        if any(a <= match.start() and match.end() <= b for a, b in linked_ranges):
            continue
        # ``[65%](url)`` remains an ordinary link. The explicitly nested form
        # is what opts a linked value into slider semantics.
        if match.end() < len(text) and text[match.end()] == "(":
            continue
        read = _read(match.group(1))
        if read is not None and not blocked(match.start(), match.end()):
            hits.append(_Hit(match.start(), match.end(), *read, None))
    return sorted(hits)


def _slider(hit: _Hit, muted: bool) -> MarkdownGroupNode:
    """A slider leaf; ``muted`` when it was written ``~~[65%]~~``, which disables it."""
    shown = f"{hit.value:g}%" if hit.unit else f"{hit.value:g}/{hit.maximum:g}"
    node = MarkdownGroupNode(type=NodeType.DRAWING_ELEMENT, content=f"[{shown}]")
    node.drawing_element = {
        "kind": "slider",
        "value": hit.value,
        "max": hit.maximum,
        "unit": hit.unit,
        "decimals": hit.decimals,
    }
    if muted:
        node.drawing_element["disabled"] = True
    node.link_url = hit.url
    return node


def _split_leaf(node: MarkdownGroupNode, ids: IdMint) -> bool:
    if node.type in _SKIP_LEAVES or node.children:
        return False
    hits = _hits(node.content)
    if not hits:
        return False
    children: list[MarkdownGroupNode] = []
    # A line holder's type names the holder, not the pieces of its text: a list
    # item stays the one item, and a one-line document's root the document.
    piece_type = NodeType.TEXT if node.type in _LINE_HOLDERS else node.type
    cursor = 0
    for hit in hits:
        start, end, muted = muted_wrap(node.content, hit.start, hit.end, cursor)
        if start > cursor:
            children.append(
                MarkdownGroupNode(type=piece_type, content=node.content[cursor:start])
            )
        children.append(_slider(hit, muted))
        cursor = end
    if cursor < len(node.content):
        children.append(
            MarkdownGroupNode(type=piece_type, content=node.content[cursor:])
        )
    if len(children) == 1 and node.type not in _LINE_HOLDERS:
        _become(node, children[0])
        return True
    _inherit_glue(node, children, ids)
    if node.type == NodeType.TEXT:
        node.type = NodeType.GROUP
    node.content = ""
    node.children = children
    node.data_points = []
    node.applicable = None
    return True


def split_sliders(root: MarkdownGroupNode, ids: IdMint) -> None:
    """Split every slider token; run after the line has been read (Phase 5.55)."""
    if not root.children:
        _split_leaf(root, ids)
    for child in list(root.children):
        split_sliders(child, ids)


def _runs(node: MarkdownGroupNode) -> list[str]:
    """The node's text, cut at every control inside it: a control's token is
    never words, and the words a control bounds are named apart from the rest."""
    if node.type == NodeType.DRAWING_ELEMENT:
        return ["", ""]
    if not node.children:
        return [node.content]
    runs = [""]
    for child in node.children:
        first, *rest = _runs(child)
        runs[-1] += " " + first
        runs.extend(rest)
    return runs


def _clean_label(text: str) -> str:
    """*text* as a label: one line, no colon after it, no ``~~`` wrapper around it."""
    label = " ".join(text.split()).rstrip(":").strip()
    if len(label) > 4 and label[:2] == label[-2:] == "~~":
        return label[2:-2].strip()
    return label


def _nearest(runs: list[str]) -> str:
    """The first run of words in *runs* that names anything."""
    return next((label for run in runs if (label := _clean_label(run))), "")


# A count is a ratio slider between a minus and a plus sign: ``Quantity: ➖ [2/9] ➕``.
# Only these two minus signs: an ASCII `` - `` before the figure is a dash, which
# divides the line before any slider is read.
_MINUS = ("\u2796", "\u2212")  # ➖ −
_PLUS = ("\u2795", "+")  # ➕ +


def _bare(text: str) -> str:
    return text.replace("\ufe0f", "").strip()


def _is_count(node: MarkdownGroupNode, i: int, payload: dict) -> bool:
    """A ratio slider whose neighbours on its line end and start with the signs."""
    children = node.children
    if payload.get("unit") or not 0 < i < len(children) - 1:
        return False
    before, after = children[i - 1], children[i + 1]
    return (
        not before.children
        and not after.children
        and _bare(before.content).endswith(_MINUS)
        and _bare(after.content).startswith(_PLUS)
    )


def _caption(holder: MarkdownGroupNode, parent: MarkdownGroupNode | None) -> str:
    """The words that name a count drawn alone in its *holder*: the key, the glued
    caption above it, the ``:`` caption after it or the cell before it -- a
    sibling of the holder that its line, card or table row keeps with it."""
    if parent is None:
        return ""
    at = next(k for k, child in enumerate(parent.children) if child is holder)
    kept = (
        parent.line_split_group
        or parent.glued_content_group
        or parent.type == NodeType.TABLE_ROW  # a row's first cell names it
    )
    for k, reverse in ((at - 1, True), (at + 1, False)):
        if 0 <= k < len(parent.children):
            sibling = parent.children[k]
            if kept or sibling.source_line_id == holder.source_line_id:
                runs = _runs(sibling)
                if label := _nearest(runs[::-1] if reverse else runs):
                    return label
    return ""


def stamp_sliders(root: MarkdownGroupNode) -> None:
    """Stamp slider ordinals and nearby server-owned labels on the final tree.

    A count (a ratio slider between ``➖`` and ``➕``) is stamped ``count`` and
    named by the words before its minus sign, else by its key or caption, never
    by the sign. Its two signs then become part of it: they are its buttons, so
    the words beside it lose them and one leaf is drawn whole, never wrapped
    between a sign and its digits."""
    count = 0
    counts: list[tuple[MarkdownGroupNode, MarkdownGroupNode]] = []

    def walk(node: MarkdownGroupNode, parent: MarkdownGroupNode | None) -> None:
        nonlocal count
        for i, child in enumerate(node.children):
            payload = child.drawing_element
            if payload is not None and payload.get("kind") == "slider":
                line = child.source_line_id
                same_context = node.line_split_group or node.glued_content_group
                # The words nearest the slider: a control between them and
                # the slider (a task's box) bounds them, as it does on a flat line.
                before = (
                    _nearest(_runs(node.children[i - 1])[::-1])
                    if i
                    and (same_context or node.children[i - 1].source_line_id == line)
                    else ""
                )
                after = (
                    _nearest(_runs(node.children[i + 1]))
                    if i + 1 < len(node.children)
                    and (same_context or node.children[i + 1].source_line_id == line)
                    else ""
                )
                if _is_count(node, i, payload):
                    payload["count"] = True
                    if _muted_signs(node.children[i - 1], node.children[i + 1]):
                        payload["disabled"] = True
                        before = _MUTED_MINUS.sub("", before)
                    before = _clean_label(_bare(before).rstrip("".join(_MINUS)))
                    after = ""
                    before = before or _caption(node, parent)
                    counts.append((node, child))
                payload["index"] = count
                payload["label"] = before or after or f"Slider {count + 1}"
                count += 1
            walk(child, node)

    walk(root, None)
    for node, child in counts:
        _take_signs(node, child)


_LEADING_PLUS = re.compile(r"^\s*[\u2795+]\ufe0f?")
_TRAILING_MINUS = re.compile(r"\s*[\u2796\u2212]\ufe0f?\s*$")
# A count muted whole, ``~~➖ [2/9] ➕~~``: its signs inside the tildes, which go
# with them, as ``➖ ~~[2/9]~~ ➕``'s go with the slider (``muted_wrap``).
_MUTED_PLUS = re.compile(r"^\s*[\u2795+]\ufe0f?~~")
_MUTED_MINUS = re.compile(r"\s*~~[\u2796\u2212]\ufe0f?\s*$")


def _muted_signs(before: MarkdownGroupNode, after: MarkdownGroupNode) -> bool:
    return bool(
        _MUTED_MINUS.search(before.content) and _MUTED_PLUS.match(after.content)
    )


def _take_signs(node: MarkdownGroupNode, count: MarkdownGroupNode) -> None:
    """Cut the count's signs from the words beside it, and drop a piece left empty."""
    at = node.children.index(count)
    before, after = node.children[at - 1], node.children[at + 1]
    muted = _muted_signs(before, after)
    minus, plus = (
        (_MUTED_MINUS, _MUTED_PLUS) if muted else (_TRAILING_MINUS, _LEADING_PLUS)
    )
    edit_content(before, regex_edits(minus, "", before.content))
    edit_content(after, regex_edits(plus, "", after.content))
    node.children = [
        c for c in node.children if c.children or c.content.strip() or c is count
    ]
