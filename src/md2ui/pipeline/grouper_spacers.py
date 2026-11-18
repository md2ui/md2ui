"""Put ``+++`` spacers into a tree that was grouped without them (ADR-203).

A spacer is blank space, so it must not change what the grouper builds: the
same nodes, fingerprints, kind_hash and runs as the document without it. That
is guaranteed by construction rather than by exempting spacers wherever a
grouping rule counts children. A document that holds spacers is grouped twice:

* without its spacer lines — that tree IS the answer, spacers aside;
* with them — only to learn, for each spacer, the leaf it follows (or, when it
  opens its container, the leaf it precedes).

Each spacer is then inserted into the first tree as a SPACER leaf, AFTER every
grouping decision was made, so it can create no wrapper and cut no glue; the
fingerprint silences it like the other elements it ignores. Leaves are matched
by position in document order, which the two groupings share because a spacer
line only ever sits BETWEEN lines. If they ever disagree, the spaced tree is
kept as it is, which is still a correct document with its spacers in place.

The one spacer both groupings keep is one that is ALL of a ``:::`` cell at an
edge of its row: that spacer is the row's structure, and the row build turns it
into space at the row's edge before any other decision reads the row.
"""

import re

from md2ui.pipeline.grouper_block_splits import SPACER_RE, _break_node_type
from md2ui.pipeline.grouper_content_edits import edit_content, regex_edits
from md2ui.pipeline.grouper_inline_marks import INLINE_SPACERS
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType

_FENCE_PREFIXES = ("```", "~~~")

# A spacer INSIDE a line: 3-5 `+` with whitespace or the line's edge on both
# sides. A backslash before it is an escape, so it never qualifies.
_INLINE_TOKEN_RE = re.compile(r"(?<![^ \t])\+{3,5}(?![^ \t])")
_BY_SPELLING = {spelling: ch for ch, spelling in INLINE_SPACERS.items()}
_EDGE = "".join(INLINE_SPACERS)
_MARK_RE = re.compile(f"[{_EDGE}]")


def mark_inline_spacers(text: str) -> str:
    """*text* with each spacer inside a line swapped for its one-character mark.

    A line that is nothing but a spacer is the vertical one and is left for the
    block split. Runs after code blocks are taken out, so code keeps its `+`.
    """
    if "+++" not in text:
        return text
    out = []
    for line in text.split("\n"):
        if "+++" in line and not SPACER_RE.match(line):
            line = _INLINE_TOKEN_RE.sub(lambda m: _BY_SPELLING[m.group(0)], line)
        out.append(line)
    return "\n".join(out)


def restore_inline_spacers(text: str) -> str:
    """*text* with any mark the separator scans did not consume spelled again —
    one inside inline code, say, is the author's `+++` and is drawn as such."""
    for ch, spelling in INLINE_SPACERS.items():
        text = text.replace(ch, spelling)
    return text


def restore_inline_spacer_text(root: MarkdownGroupNode) -> None:
    """Spell again every inline spacer mark left in *root*'s text, and hand
    each line-edge spacer to the node that became that line — for a cell of a
    row, that line is the row."""
    rows: list[MarkdownGroupNode] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.column_row_group:
            rows.append(node)
        # The edge was taken while a container still held the line's text (a
        # one-line document's root does); the line is now its only child.
        if (node.spacer_lead or node.spacer_trail) and len(node.children) == 1:
            carry_edge_spacers(node, node.children[0])
            node.spacer_lead = node.spacer_trail = None
            node.spacer_beside = False
        if any(ch in node.content for ch in INLINE_SPACERS):
            edit_content(node, regex_edits(_MARK_RE, INLINE_SPACERS, node.content))
        if node.link_label and any(ch in node.link_label for ch in INLINE_SPACERS):
            node.link_label = restore_inline_spacers(node.link_label)
        stack.extend(node.children)
    for row in rows:
        _lift_cell_edges(row)


def _lift_cell_edges(row: MarkdownGroupNode) -> None:
    """A spacer at the edge of a one-line cell is at an edge of the row's line:
    between two cells it is the gap, at the row's ends the row's own. A cell
    of blocks keeps its lines' spacers.

    A HELD cell keeps its spacers too: one with a spacer on BOTH edges
    (`+++ text +++`) is the author holding that text to a narrower column, so
    the spacers are the cell's own padding — they shrink together as the text
    wraps between them, rather than drop as gaps where the row wraps."""
    for i, cell in enumerate(row.children):
        if cell.children and not cell.line_split_group:
            continue
        if cell.spacer_lead and cell.spacer_trail:
            continue
        if cell.spacer_lead:
            _row_space(row, i, cell.spacer_lead)
        if cell.spacer_trail:
            _row_space(row, i + 1, cell.spacer_trail)
        cell.spacer_lead = cell.spacer_trail = None


def _row_space(row: MarkdownGroupNode, at: int, spelling: str) -> None:
    """Record *spelling* at cell boundary *at* of a row the way a line
    records it: a gap mark between two cells (``separator_chars``, one entry
    per gap), the row's own edge before the first or after the last."""
    if at == 0:
        row.spacer_lead = (
            f"{row.spacer_lead} {spelling}" if row.spacer_lead else spelling
        )
    elif at == len(row.children):
        row.spacer_trail = (
            f"{row.spacer_trail} {spelling}" if row.spacer_trail else spelling
        )
    else:
        if not row.separator_chars:
            row.separator_chars = [""] * (len(row.children) - 1)
        row.separator_chars[at - 1] += "".join(
            _BY_SPELLING[s] for s in spelling.split()
        )


def carry_edge_spacers(src: MarkdownGroupNode, dst: MarkdownGroupNode) -> None:
    """Give *dst* the space at *src*'s edges when a level dissolves and *dst*
    holds what *src* held: the space belongs to the content, not the level.
    Space that was a cell beside the content stays beside it."""
    dst.spacer_lead = dst.spacer_lead or src.spacer_lead
    dst.spacer_trail = dst.spacer_trail or src.spacer_trail
    dst.spacer_beside = dst.spacer_beside or src.spacer_beside


def take_edge_spacers(content: str) -> tuple[str | None, str | None, str]:
    """``(leading, trailing, rest)``: a spacer mark at either end of a line.

    A separator needs a piece on both sides; one at an edge has a piece on one,
    so it is not a cut but space before or after the line's content. It is
    recorded on the line (``spacer_lead`` / ``spacer_trail``), leaving the
    content exactly what it is without it. Consecutive spacers at one edge are
    one space, their spellings kept in order so their sizes add up — as
    consecutive spacer lines do.
    """
    s = content.strip()
    leads: list[str] = []
    trails: list[str] = []
    while len(s) > 1 and s[0] in _EDGE and s[1] in " \t":
        leads.append(INLINE_SPACERS[s[0]])
        s = s[1:].lstrip()
    while len(s) > 1 and s[-1] in _EDGE and s[-2] in " \t":
        trails.insert(0, INLINE_SPACERS[s[-1]])
        s = s[:-1].rstrip()
    lead = " ".join(leads) or None
    trail = " ".join(trails) or None
    return lead, trail, s if (lead or trail) else content


def strip_spacer_lines(text: str) -> str | None:
    """*text* without its spacer lines, or ``None`` when it has none to take.

    A spacer is a line the block split would read as one: up to three spaces
    of indent at the top level (four is a code block), any indent inside a
    list item, and never inside a fenced code block. A spacer that is the whole
    of a ``:::`` cell at a row's edge stays (``_cell_spacers``).
    """
    if "+++" not in text:
        return None  # nearly every document: one substring test, no line walk
    lines = text.split("\n")
    spacers: set[int] = set()
    top: set[int] = set()  # not inside a list item, whose `:::` is its own
    fence: str | None = None
    in_item = False
    for i, line in enumerate(lines):
        stripped = line.lstrip(" \t")
        indent = len(line) - len(stripped)
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith(_FENCE_PREFIXES):
            fence = stripped[:3]
            continue
        if stripped[:2] in ("- ", "* ", "+ ") or stripped[:1].isdigit():
            in_item = True
        elif stripped and indent == 0:
            in_item = False
        if SPACER_RE.match(line) and (indent <= 3 or in_item):
            spacers.add(i)
            if not in_item:
                top.add(i)
    # The neighbours are read as the grouping will see them: comments gone.
    shown = _COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    drop = spacers - (_cell_spacers(shown.split("\n"), spacers) & top)
    if not drop:
        return None
    return "\n".join(line for i, line in enumerate(lines) if i not in drop)


# What closes a `:::` cell on either side besides another divider.
_ROW_CUTS = (
    NodeType.COLUMN_DIVIDER,
    NodeType.HORIZONTAL_RULE,
    NodeType.CONTENT_BREAK,
    NodeType.SECTION_STOP,
    NodeType.ROW_CLOSER,
)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING_LINE_RE = re.compile(r"^#{1,6}(?:\s|$)")


def _cell_spacers(lines: list[str], spacers: set[int]) -> set[int]:
    """The spacer lines that are the whole of a ``:::`` cell at an EDGE of its
    row: nothing but spacer cells between it and where the row starts or ends.

    Taking one out would leave the row decided on an empty cell, and an empty
    cell at an edge changes what the row is — a section seems closed by its
    last ``:::``, a two-cell row has one. So it stays for the grouping to see,
    and the row build reads it as space at the row's edge
    (``grouper_column_rows.take_edge_spacer_cells``). One between two cells
    goes like any other: the empty cell it leaves cuts nothing, and the spaced
    grouping finds it a cell of its own (``stamp_spacers``).
    """

    def divider(line: str | None) -> bool:
        return line is not None and _break_node_type(line) == NodeType.COLUMN_DIVIDER

    def ends(line: str | None, step: int) -> bool:
        # Where a row stops: the document's edge, another break, or a heading
        # below (above, only an empty `## ` marker: a title is cell content).
        if line is None or _break_node_type(line) in _ROW_CUTS:
            return True
        return bool(_HEADING_LINE_RE.match(line)) and (
            step > 0 or not line.strip("# \t")
        )

    def near(i: int, step: int, over_dividers: bool) -> str | None:
        j = i + step
        while 0 <= j < len(lines) and (
            j in spacers
            or not lines[j].strip()
            or (over_dividers and divider(lines[j]))
        ):
            j += step
        return lines[j] if 0 <= j < len(lines) else None

    keep: set[int] = set()
    for i in spacers:
        sides = [(near(i, step, False), step) for step in (-1, 1)]
        if not any(divider(n) for n, _ in sides):
            continue
        if not all(divider(n) or ends(n, step) for n, step in sides):
            continue  # beside content in its cell
        if any(ends(near(i, step, True), step) for step in (-1, 1)):
            keep.add(i)
    return keep


def _leaves(root: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    """Every non-spacer leaf, in document order."""
    out: list[MarkdownGroupNode] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if not node.children:
            if node.type != NodeType.SPACER and node is not root:
                out.append(node)
            continue
        stack.extend(reversed(node.children))
    return out


def _ranges(root: MarkdownGroupNode) -> dict[int, tuple[int, int]]:
    """``id(node) -> (first, end)``: the leaves under each node, by index.

    Spacers hold no leaf, so a range means the same in both groupings.
    """
    out: dict[int, tuple[int, int]] = {}
    count = 0

    def walk(node: MarkdownGroupNode) -> None:
        nonlocal count
        start = count
        if not node.children:
            if node.type != NodeType.SPACER and node is not root:
                count += 1
        for child in node.children:
            walk(child)
        out[id(node)] = (start, count)

    walk(root)
    return out


def _spacers(
    spaced: MarkdownGroupNode,
) -> list[tuple[tuple[int, int], int, int, str, str, bool, bool]]:
    """``(container_range, depth, boundary, spelling, binds, is_cell, in_line)``
    for each spacer.

    The boundary is how many leaves come before the spacer: where it sits.
    ``depth`` tells apart containers that hold the same leaves — a card that is
    all of the document, and the document — by how many of its ancestors share
    its range. ``binds`` is "prev" when something precedes the spacer in its
    container, else "next". ``is_cell``: the spacer was a cell of a ``:::`` row
    of its own — written alone between two dividers, which no cell of the plain
    grouping can tell apart from space under the cell before it.
    ``in_line``: the spacer was written among the pieces of a line or a row,
    not beside one — in a card holding nothing but a row, the spaced grouping
    still keeps the card around the row, where the plain one merged the two.
    """
    ranges = _ranges(spaced)
    out: list[tuple[tuple[int, int], int, int, str, str, bool, bool]] = []

    def walk(node: MarkdownGroupNode, same: int) -> None:
        for i, child in enumerate(node.children):
            if child.type == NodeType.SPACER:
                before = any(c.type != NodeType.SPACER for c in node.children[:i])
                span, at = ranges[id(node)], ranges[id(child)][0]
                binds = "prev" if before else "next"
                row, line = node.column_row_group, node.line_split_group
                out.append((span, same, at, child.content, binds, row, row or line))
            elif child.children:
                walk(child, same + 1 if ranges[id(child)] == ranges[id(node)] else 0)

    walk(spaced, 0)
    return out


def _container(
    plain: MarkdownGroupNode, ranges: dict, span: tuple[int, int], depth: int
) -> MarkdownGroupNode:
    """The node of *plain* that holds *span*, the *depth*-th of those holding
    exactly it (the last, when there are fewer), else the deepest holding it."""
    first, end = span
    node, exact = plain, [plain] if ranges[id(plain)] == span else []
    while True:
        inner = next(
            (
                c
                for c in node.children
                if c.children and ranges[id(c)][0] <= first and end <= ranges[id(c)][1]
            ),
            None,
        )
        if inner is None:
            break
        node = inner
        if ranges[id(node)] == span:
            exact.append(node)
    return exact[min(depth, len(exact) - 1)] if exact else node


def _into_cell(
    row: MarkdownGroupNode, index: int, binds: str, ranges: dict
) -> tuple[MarkdownGroupNode, int]:
    """Where a spacer at child *index* of a ``:::`` row goes: into the cell it
    binds to — the end of the one before, or the start of the one after — as a
    leaf of that cell. A row holds cells, never a spacer: one standing between
    two cells would be a cell of its own, beside the others. A one-node cell is
    given a plain wrapper to hold it, as a multi-block cell already has one, so
    the row keeps its cell count and its weights."""
    prev = binds == "prev" and index > 0
    at = index - 1 if prev else min(index, len(row.children) - 1)
    cell = row.children[at]
    if not cell.children:
        wrapper = MarkdownGroupNode(type=NodeType.GROUP)
        wrapper.children = [cell]
        ranges[id(wrapper)] = ranges[id(cell)]
        row.children[at] = cell = wrapper
    return cell, len(cell.children) if prev else 0


def _row_edge(node: MarkdownGroupNode, ranges: dict, k: int, spelling: str) -> bool:
    """Record a spacer written beside a row, at boundary *k*, on *node* when
    *node* is that row merged with its card: a leaf above or below the row
    that the merged level has no place for. Whether it was recorded."""
    if not (node.line_split_group or node.column_row_group):
        return False
    first, end = ranges[id(node)]
    edge = "spacer_above" if k <= first else "spacer_below" if k >= end else None
    if edge is None:
        return False
    have = getattr(node, edge)
    setattr(node, edge, f"{have} {spelling}" if have else spelling)
    return True


def stamp_spacers(plain: MarkdownGroupNode, spaced: MarkdownGroupNode) -> bool:
    """Insert *spaced*'s spacers into *plain*, in the container each was written in.

    The container is the node of *plain* holding the same leaves as the
    spacer's container in *spaced*; the spacer goes at the child boundary where
    it sat, descending when that boundary falls inside a child. Returns
    ``False``, changing nothing, when the two trees' leaves do not line up.
    """
    # Content, not type: the same line can be a one-line item in one grouping
    # and the text inside that item in the other.
    if [n.content for n in _leaves(plain)] != [n.content for n in _leaves(spaced)]:
        return False
    # A spacer kept for the row build that did not become a cell is in both
    # trees: it goes back from the spaced one, like every other spacer.
    stack = [plain]
    while stack:
        node = stack.pop()
        node.children = [c for c in node.children if c.type != NodeType.SPACER]
        stack.extend(node.children)
    ranges = _ranges(plain)
    places: list[tuple[MarkdownGroupNode, int, str, str]] = []
    for span, depth, k, spelling, binds, is_cell, in_line in _spacers(spaced):
        if span[0] == span[1]:
            continue
        node = _container(plain, ranges, span, depth)
        if not in_line and _row_edge(node, ranges, k, spelling):
            continue
        while True:
            inside = next(
                (c for c in node.children if ranges[id(c)][0] < k < ranges[id(c)][1]),
                None,
            )
            if inside is None or not inside.children:
                break
            node = inside
        index = sum(1 for c in node.children if ranges[id(c)][1] <= k)
        # A spacer that was a cell of its own is space ACROSS its row, recorded
        # the way a line records it; anywhere else it stays a leaf.
        if node.column_row_group and is_cell:
            _row_space(node, index, spelling)
            continue
        if node.column_row_group:
            node, index = _into_cell(node, index, binds, ranges)
        places.append((node, index, spelling, binds))
    # Spacers that land in one place are ONE spacer, their marks in written
    # order: consecutive space adds up, and no gap opens between two blanks.
    merged: dict[tuple[int, int], list] = {}
    for node, index, spelling, binds in places:
        at = merged.setdefault((id(node), index), [node, index, [], binds])
        at[2].append(spelling)
    # Insert last-first per container, so each index still means what it did.
    for node, index, spellings, binds in sorted(
        merged.values(), key=lambda p: (id(p[0]), p[1]), reverse=True
    ):
        spacer = MarkdownGroupNode(type=NodeType.SPACER, content=" ".join(spellings))
        spacer.spacer_binds = binds
        node.children.insert(index, spacer)
    return True
