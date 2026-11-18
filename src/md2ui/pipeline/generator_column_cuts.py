"""Which cells of a ``:::`` row stand side by side at the width it is offered.

A divider may cut in narrow space only (``::: 1 <``), in wide space only
(``::: 1 >``), or write a second weight for wide space (``::: 1 1.5``). The grouper
records all three on the row (``column_cuts``, ``column_weights_wide``); this reads
them at one width. Where a cut does not apply, the cells either side of it stand
as ONE cell, stacked, and that cell takes the weight of the divider that closes it.

The row stays a request: the generator still wraps the cells that do not fit,
so the natural flow wins at every width.
"""

from __future__ import annotations

from md2ui.pipeline.generator_units import IMAGE_MIN_WIDTH, LEAF_WIDTH, _length_category
from md2ui.pipeline.grouper_annotate import stamp_group_kinds
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType

# The width from which a row is in WIDE space: the space the row is offered, not
# the page. The same 768 the default image box changes shape at.
WIDE_BREAKPOINT: float = 768.0


def row_groups(
    row: MarkdownGroupNode, count: int, width: float
) -> tuple[list[list[int]], list[float | None]]:
    """``(groups, written)`` for *row*'s *count* cells at *width*: the cell
    indices that stand together, in order, and the weight written for each
    group (``None``: no number), read as ``_row_weights`` reads a row's own.
    """
    wide = width >= WIDE_BREAKPOINT
    weights = list(row.column_weights or ())
    if wide and row.column_weights_wide:
        weights = [
            w if ww is None else ww for w, ww in zip(weights, row.column_weights_wide)
        ]
    weights += [None] * (count - len(weights))
    cuts = list(row.column_cuts or ()) + [None] * count
    here = "wide" if wide else "narrow"
    groups: list[list[int]] = [[]]
    written: list[float | None] = []
    for i in range(count):
        groups[-1].append(i)
        if i == count - 1 or cuts[i] in (None, here):
            written.append(weights[i])
            if i < count - 1:
                groups.append([])
    return groups, written


def group_gaps(row: MarkdownGroupNode, groups: list[list[int]]) -> list[str]:
    """The row's gaps (``separator_chars``) between *groups*: the gap after a
    group's last cell stays between that group and the next. A gap between
    two cells that stand as one falls where they stack, as a line's gap falls
    where it wraps."""
    chars = list(row.separator_chars or ())
    if not chars:
        return []
    return [chars[g[-1]] if g[-1] < len(chars) else "" for g in groups[:-1]]


def stack_category(members: list[MarkdownGroupNode]) -> str | None:
    """The length category of cells standing as one: the narrowest that is as
    wide as the widest of them, so the stack's minimum width is its widest
    member's. ``None`` (no bound) when a member has none either."""
    widest = 0.0
    for m in members:
        w = (
            IMAGE_MIN_WIDTH
            if m.type == NodeType.IMAGE
            else LEAF_WIDTH.get(_length_category(m) or "")
        )
        if w is None:
            return None
        widest = max(widest, w)
    return min(
        (c for c, w in LEAF_WIDTH.items() if w >= widest),
        key=LEAF_WIDTH.__getitem__,
        default=None,
    )


def stack_of(cells: list[MarkdownGroupNode], group: list[int]) -> MarkdownGroupNode:
    """A wrapper for the cells of *group*, standing as one cell: its minimum
    width is its widest member's, and its id cannot collide with a real node's."""
    stack = MarkdownGroupNode(type=NodeType.GROUP)
    stack.children = [cells[i] for i in group]
    stack.node_id = f"{stack.children[0].node_id}~"
    stack.content_length_category = stack_category(stack.children)
    stamp_group_kinds(stack)
    return stack
