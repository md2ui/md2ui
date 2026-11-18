"""Matching pieces of the cards in one grid row share the tallest one's height.

Cards of one run sit side by side in a grid row and are stretched to one height,
but each stacks its pieces from the top: a title that wraps to two lines in one
card pushes its subtitle, picture, text and button below their twins in the
next card, and the row stops reading as a run. So in a grid row, the piece at
the same place in every card is the same element (the cards share a
fingerprint), and it gets the tallest of their heights; the piece keeps the top
of that slot and the gap opens under it.

Only a row's own cards share, never a whole run: a long title two rows up does
not make every card taller, which sharing across a whole run would do by far
more. The last
piece shares nothing, having nothing below it to align, and neither does a
piece that is or holds a picture, whose height is its own ratio.

Measuring and placing both read heights through ``render_measure.natural_height``,
which lifts a piece to its slot here, so the two agree (ADR-400). The slots are
per width (ADR-401): each grid row shares again whenever it is laid out, and a
scene build starts from none.
"""

from __future__ import annotations

from collections.abc import Callable

from md2ui.pipeline.layout_script_parser import LayoutNode

# id(piece) -> (piece, width, slot height). The piece is held so its id cannot be
# reused while the entry lives.
_SLOTS: dict[int, tuple[LayoutNode, float, float]] = {}
# While a row measures its cards: id(node) -> (width, height) of every node asked.
_SEEN: dict[int, tuple[float, float]] | None = None


def clear() -> None:
    """Forget every slot: a new scene shares again from nothing."""
    _SLOTS.clear()


def lift(node: LayoutNode, width: float, height: float) -> float:
    """*height*, or the slot *node* shares in its grid row at *width* if taller."""
    if _SEEN is not None:
        _SEEN[id(node)] = (width, height)
    slot = _SLOTS.get(id(node))
    if slot is None or slot[0] is not node or abs(slot[1] - width) > 0.5:
        return height
    return max(height, slot[2])


def _pieces(card: LayoutNode) -> tuple[list[LayoutNode], list[LayoutNode]]:
    """The pieces *card* stacks, and the wrappers down to them."""
    chain = [card]
    while len(card.children) == 1 and card.type in ("col", "row", "layout"):
        card = card.children[0]
        chain.append(card)
    return (list(card.children) if card.type == "col" else []), chain


def _holds_picture(node: LayoutNode, is_picture: Callable[[LayoutNode], bool]) -> bool:
    """Whether *node* is a picture or holds one: an image card, a photo beside its
    caption. A taller slot would draw the picture taller than its ratio."""
    return (
        is_picture(node)
        or node.card_bg_url is not None  # a photo the card's own background draws
        or any(_holds_picture(c, is_picture) for c in node.children)
    )


def _forget(memo: dict | None, ids: set[int]) -> None:
    """Drop the memoised heights of *ids*, which a share has just changed."""
    if memo:
        for key in [k for k in memo if k[0] in ids]:
            del memo[key]


def share(
    cards: list[LayoutNode],
    measure: Callable[[], object],
    is_picture: Callable[[LayoutNode], bool],
    memo: dict | None,
) -> None:
    """Give the matching pieces of *cards*, one grid row, one height.

    Cards share only when each stacks the same number of pieces, of the same
    kinds in the same order. *measure* measures the row's cards as the row does."""
    global _SEEN
    stacks = [_pieces(c) for c in cards]
    pieces = [p for p, _ in stacks]
    if len(cards) < 2 or len({len(p) for p in pieces}) != 1 or len(pieces[0]) < 2:
        return
    if any(len({p[i].type for p in pieces}) != 1 for i in range(len(pieces[0]))):
        return
    for p in pieces:
        for piece in p:
            _SLOTS.pop(id(piece), None)
    chains = {id(n) for _, chain in stacks for n in chain}
    _forget(memo, chains)
    # A card can hold a grid row of its own, which shares while this row measures:
    # each row records into its own table and hands the outer one back after.
    outer, seen = _SEEN, {}
    _SEEN = seen
    try:
        measure()
    finally:
        _SEEN = outer
    for i in range(len(pieces[0]) - 1):
        column = [p[i] for p in pieces]
        asked = [seen[id(c)] for c in column if id(c) in seen]
        if len(asked) < len(column) or any(
            _holds_picture(c, is_picture) for c in column
        ):
            continue
        top = max(h for _, h in asked)
        for piece, (w, h) in zip(column, asked):
            if top - h > 0.5:
                _SLOTS[id(piece)] = (piece, w, top)
    _forget(memo, chains)
