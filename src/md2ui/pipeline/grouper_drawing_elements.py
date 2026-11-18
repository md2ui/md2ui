"""Markdown task-control tokens that become explicit drawing-element leaves.

The grouper owns recognition: later stages consume the serialized semantic
payload and never inspect bracket text. Standard task markers stripped by the
block splitter and literal ``[ ]``/``[X]`` tokens share one representation.
"""

import re

from md2ui.pipeline.grouper_content_edits import edit_content, regex_edits
from md2ui.pipeline.grouper_ids import IdMint, _inherit_glue
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.render_text import LINK_DESTINATION


_LIST_TYPES = frozenset(
    {NodeType.LIST_ITEM, NodeType.ORDERED_ITEM, NodeType.TASK_OPEN, NodeType.TASK_DONE}
)
# Nodes that hold a line without being it: a list item, and the root of a
# one-line document, whose type names the document. A control cut from their
# text is their child, never a relabel of the holder.
_LINE_HOLDERS = _LIST_TYPES | {"root"}
_LINKED_CONTROL_RE = re.compile(rf"\[\[([ xX])\]\]\(((?=[^)]){LINK_DESTINATION})\)")
_CONTROL_RE = re.compile(r"\[([ xX])\]")
_SKIP_LEAVES = frozenset(
    {NodeType.IMAGE, NodeType.LINK, NodeType.INLINE_CODE, NodeType.DRAWING_ELEMENT}
)
# One placeholder per spelling, so an escaped token draws exactly as written:
# ``\[x]`` stays ``[x]`` and ``\[X]`` stays ``[X]``.
_ESCAPED_SPELLING = {"\ue120": "[ ]", "\ue121": "[X]", "\ue123": "[x]"}
_ESCAPED_PLACEHOLDER = {spelling: mark for mark, spelling in _ESCAPED_SPELLING.items()}
_ESCAPED_RE = re.compile(f"[{''.join(_ESCAPED_SPELLING)}]")


def protect_escaped_task_controls(text: str) -> str:
    """Hide escaped control tokens while CommonMark escapes are resolved, its
    closing bracket escaped or not."""
    return re.sub(
        r"\\(\[[ xX])\\?\]",
        lambda match: _ESCAPED_PLACEHOLDER[match.group(1) + "]"],
        text,
    )


def restore_escaped_task_controls(node: MarkdownGroupNode) -> None:
    if node.content:
        edit_content(node, regex_edits(_ESCAPED_RE, _ESCAPED_SPELLING, node.content))
    for child in node.children:
        restore_escaped_task_controls(child)


def _code_ranges(text: str) -> list[tuple[int, int]]:
    """Ranges covered by simple backtick code spans in one physical line."""
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


def _hits(text: str) -> list[tuple[int, int, bool, str | None]]:
    """Return non-overlapping ``(start, end, checked, url)`` control hits."""
    code = _code_ranges(text)
    linked = list(_LINKED_CONTROL_RE.finditer(text))
    hits: list[tuple[int, int, bool, str | None]] = []

    def blocked(start: int, end: int) -> bool:
        return any(a < end and start < b for a, b in code) or (
            start > 0 and text[start - 1] in ("\\", "!")
        )

    for match in linked:
        if not blocked(match.start(), match.end()):
            hits.append(
                (
                    match.start(),
                    match.end(),
                    match.group(1).lower() == "x",
                    match.group(2),
                )
            )
    linked_ranges = [(h[0], h[1]) for h in hits]
    for match in _CONTROL_RE.finditer(text):
        if any(a <= match.start() and match.end() <= b for a, b in linked_ranges):
            continue
        # ``[X](/url)`` is an ordinary Markdown link. Only the explicitly
        # nested ``[[X]](/url)`` spelling annotates a drawn control.
        if match.end() < len(text) and text[match.end()] == "(":
            continue
        if not blocked(match.start(), match.end()):
            hits.append(
                (match.start(), match.end(), match.group(1).lower() == "x", None)
            )
    return sorted(hits)


def muted_wrap(text: str, start: int, end: int, floor: int) -> tuple[int, int, bool]:
    """The token at *start*:*end* of *text* with its ``~~`` wrapper, when it has
    one after *floor*: ``~~[ ]~~`` is a muted control as ``~~[Cancel](agent:c)~~``
    is a disabled link, drawn disabled and reporting nothing, its tildes no text."""
    if start - 2 >= floor and text[start - 2 : start] == text[end : end + 2] == "~~":
        return start - 2, end + 2, True
    return start, end, False


def _control(
    checked: bool, url: str | None = None, marker: bool = False, muted: bool = False
) -> MarkdownGroupNode:
    """A task control; ``marker`` when it is a task item's own box, which marks
    the item as a bullet does rather than counting as one of its pieces, and
    ``muted`` when it was written ``~~[ ]~~``, which disables it."""
    node = MarkdownGroupNode(
        type=NodeType.DRAWING_ELEMENT,
        content="[X]" if checked else "[ ]",
    )
    node.drawing_element = {"kind": "task_control", "checked": checked}
    if marker:
        node.drawing_element["marker"] = True
    if muted:
        node.drawing_element["disabled"] = True
    node.link_url = url
    return node


def _become(node: MarkdownGroupNode, element: MarkdownGroupNode) -> None:
    """Relabel a leaf that IS one token in place, keeping its line and glue.

    A separator run's ``- [ ] -`` piece is a SEGMENT holding only the token;
    wrapping it would leave a one-child segment where an emoji or chip is a
    direct child of the run, so it becomes the element as the peel does.
    """
    node.type = element.type
    node.content = element.content
    node.drawing_element = element.drawing_element
    node.link_url = element.link_url
    node.data_points = []
    node.applicable = None


def _split_leaf(
    node: MarkdownGroupNode,
    ids: IdMint,
    leading: bool | None = None,
    leading_url: str | None = None,
) -> bool:
    if node.type in _SKIP_LEAVES or node.children:
        return False
    hits = _hits(node.content)
    if leading is None and not hits:
        return False
    children: list[MarkdownGroupNode] = []
    piece_type = NodeType.TEXT if node.type in _LINE_HOLDERS else node.type
    if leading is not None:
        children.append(_control(leading, leading_url, marker=True))
    cursor = 0
    for start, end, checked, url in hits:
        start, end, muted = muted_wrap(node.content, start, end, cursor)
        if start > cursor:
            children.append(
                MarkdownGroupNode(type=piece_type, content=node.content[cursor:start])
            )
        children.append(_control(checked, url, muted=muted))
        cursor = end
    if cursor < len(node.content):
        children.append(
            MarkdownGroupNode(type=piece_type, content=node.content[cursor:])
        )
    if not children:
        return False
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


def _first_content_leaf(node: MarkdownGroupNode) -> MarkdownGroupNode | None:
    if not node.children:
        return node if node.type not in _SKIP_LEAVES else None
    for child in node.children:
        if child.type in _LIST_TYPES:
            continue
        found = _first_content_leaf(child)
        if found is not None:
            return found
    return None


def _take_marker(node: MarkdownGroupNode) -> tuple[bool, str | None]:
    """Whether this task item's text opens with its own marker box, taken off
    the text, and the URL of that box when it is linked.

    `- [[ ]](url) Send it` is the task `- [ ] Send it` whose box clicks through
    to *url*: the box is the item's marker, not a second control. The block
    splitter keeps the marker in the text when it is linked, or when the label
    opens with a box of its own, as in `- [ ] [[x]](url) Send it`; a box after
    the marker is then a control inside the item. A spring before the text
    (`- [ ] ... [x] Send it`) means the marker was not kept: the box the text
    opens with stands after the spring, so it is a control.
    """
    region = node.children[0] if node.align_group and node.children else node
    if region.authored_align not in (None, "left"):
        return False, None
    first = _first_content_leaf(node)
    if first is None:
        return False, None
    linked = _LINKED_CONTROL_RE.match(first.content)
    plain = _CONTROL_RE.match(first.content)
    if linked is not None:
        first.content = first.content[linked.end() :].lstrip()
        return True, linked.group(2)
    if plain is not None and first.content[plain.end() : plain.end() + 1] != "(":
        first.content = first.content[plain.end() :].lstrip()
        return True, None
    return False, None


# What a walked line holds, moved onto the region a task marker sits beside.
_REGION_FIELDS = ("children", "data_points", "paren_quote_ranges", "applicable")
_REGION_FIELDS += ("separator_chars", "column_split_group", "authored_align")


def _split_list_contents(node: MarkdownGroupNode, ids: IdMint) -> None:
    """Split controls in this list item, leaving nested items to their own walk."""

    # A task box already cut means the marker was taken; a slider beside the
    # text is content, and the item still owns its box.
    def has_control(part: MarkdownGroupNode) -> bool:
        payload = part.drawing_element
        return (payload is not None and payload.get("kind") == "task_control") or any(
            has_control(child) for child in part.children
        )

    marker = (
        node.type == NodeType.TASK_DONE
        if node.type in (NodeType.TASK_OPEN, NodeType.TASK_DONE)
        else None
    )
    if marker is not None and has_control(node):
        marker = None
    marker_url = _take_marker(node)[1] if marker is not None else None
    if marker is not None and node.authored_align and not node.align_group:
        # `- [ ] ... Word` with its one region folded into the item: the marker
        # is a second piece, so the content is an aligned region again.
        kind = NodeType.GROUP if node.children else NodeType.TEXT
        region = MarkdownGroupNode(type=kind, content=node.content)
        for field in _REGION_FIELDS:
            setattr(region, field, getattr(node, field))
        node.content, node.data_points, node.children = "", [], [region]
        node.separator_chars, node.column_split_group = [], False
        node.authored_align, node.align_group = None, True
    if marker is not None and node.align_group:
        # `- [ ] ... Word`: the item's springs have made its content aligned
        # regions, and the first of them may be the RIGHT one. The marker
        # starts the line, so it is a left region of its own, as the emoji is
        # in `- ✅ ... Word`.
        control = _control(marker, marker_url, marker=True)
        control.authored_align = "left"
        node.children.insert(0, control)
        _inherit_glue(node, node.children, ids)
        marker = None
    first = _first_content_leaf(node) if marker is not None else None

    def walk(part: MarkdownGroupNode) -> None:
        if part is not node and part.type in _LIST_TYPES:
            return
        if not part.children:
            _split_leaf(
                part,
                ids,
                marker if part is first else None,
                marker_url if part is first else None,
            )
            return
        for child in list(part.children):
            walk(child)

    walk(node)


def _is_control(node: MarkdownGroupNode) -> bool:
    payload = node.drawing_element
    return payload is not None and payload.get("kind") == "task_control"


def _text_of(node: MarkdownGroupNode) -> str:
    if not node.children:
        return node.content
    return " ".join(_text_of(child) for child in node.children)


def _label_after(siblings: list[MarkdownGroupNode]) -> str:
    """The text a control starts: its following siblings, up to the next control
    or a nested list item (which is an item of its own)."""
    parts: list[str] = []
    for sibling in siblings:
        if sibling.type == NodeType.DRAWING_ELEMENT or sibling.type in _LIST_TYPES:
            break
        parts.append(_text_of(sibling))
    return " ".join(" ".join(parts).split())


def _item_box(item: MarkdownGroupNode) -> MarkdownGroupNode | None:
    """A task item's own box: the first control it holds, nested items aside."""
    for child in item.children:
        if child.type in _LIST_TYPES:
            continue
        if _is_control(child):
            return child
        found = _item_box(child)
        if found is not None:
            return found
    return None


def _item_label(item: MarkdownGroupNode, box: MarkdownGroupNode) -> str:
    """The item's words after its own box on its line, other task boxes left
    out, up to a slider or a nested item. Read across the whole item, not the box's siblings:
    a spring divides one item's line into regions, it does not end its name."""
    words: list[str] = []
    seen = False
    line = box.source_line_id

    def _next_line(node: MarkdownGroupNode) -> bool:
        return None not in (line, node.source_line_id) and node.source_line_id != line

    def walk(node: MarkdownGroupNode) -> bool:
        nonlocal seen
        for child in node.children:
            if child is box:
                seen = True
            elif child.type in _LIST_TYPES or (seen and _next_line(child)):
                return False
            elif _is_control(child):
                continue
            elif child.type == NodeType.DRAWING_ELEMENT:
                if seen:
                    return False
            elif child.children:
                if not walk(child):
                    return False
            elif seen:
                words.append(child.content)
        return True

    walk(item)
    return " ".join(" ".join(words).split())


def stamp_task_controls(root: MarkdownGroupNode) -> None:
    """Stamp each task control's ``index`` and ``label`` into its payload.

    ``index`` counts controls in document order from 0; ``label`` is the text of
    the item the control starts. A task item's own box names the item even when
    another box comes first in its text, and across the regions a spring divides
    its line into: ticking it is never a tick with no name. They are what a
    click on it reports (render_actions), and a re-send that only ticks a box leaves both unchanged, so a host can key on
    them. Runs on the finished tree, after the late escapes are dropped, so a
    label holds the text as drawn.
    """
    count = 0
    item_labels: dict[int, str] = {}

    def walk(node: MarkdownGroupNode) -> None:
        nonlocal count
        if node.type in (NodeType.TASK_OPEN, NodeType.TASK_DONE):
            box = _item_box(node)
            if box is not None:
                item_labels[id(box)] = _item_label(node, box)
        for i, child in enumerate(node.children):
            payload = child.drawing_element
            if payload is not None and payload.get("kind") == "task_control":
                payload["index"] = count
                own = item_labels.get(id(child))
                if own is None:
                    own = _label_after(node.children[i + 1 :])
                payload["label"] = own
                count += 1
            walk(child)

    walk(root)


def split_task_controls(root: MarkdownGroupNode, ids: IdMint) -> None:
    """Annotate exact task controls anywhere, after the line has been read."""
    if root.type in _LIST_TYPES:
        _split_list_contents(root, ids)
    elif not root.children:
        _split_leaf(root, ids)
    for child in list(root.children):
        split_task_controls(child, ids)
