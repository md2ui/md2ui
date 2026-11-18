"""Make the layout cells for ``+++`` spacers (ADR-203).

The grouper puts each spacer where it was written, silenced for matching; this
is where one gets its size — the theme's step at the surface that holds it —
and where a spacer that landed between the cells of a row moves into the cell
it belongs to.
"""

from collections.abc import Callable

from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.theme import Theme, resolve_section_style


# What a spacer measures when no surface states it (ADR-203): a multiple of
# the GROUP gap along its own direction. A spacer adds to the gap already there,
# so even the small one then reads as more than a group gap, in any theme, and
# every step keeps the theme's own proportions. Across a line the steps are
# closer together: a large jump in the middle of a line reads as a hole.
SPACER_MULTIPLES = {
    "col": {"small": 1.0, "medium": 2.0, "large": 4.0},
    "row": {"small": 1.0, "medium": 1.5, "large": 2.0},
}
# The least an unstated spacer measures: a theme whose gaps
# are 0 must not turn a written spacer into nothing, so a multiple of a small
# or empty gap is raised to these, the multiples of the default 8px gap. A
# wider gap still scales the spacer up.
SPACER_FLOORS = {
    "col": {"small": 8.0, "medium": 16.0, "large": 32.0},
    "row": {"small": 8.0, "medium": 12.0, "large": 16.0},
}
# The group gap when a theme gives no gap at all to take one from.
_FALLBACK_GAP = 8.0
# The spelling's length is its step: ``+++`` small … ``+++++`` large.
SPACER_STEPS = {3: "small", 4: "medium", 5: "large"}


def _group_gap(theme: Theme | None, axis: str, section) -> float:
    """The group gap along *axis* at this surface: the heading level's own, then
    ``### Elements``', then the element gap, then 8."""
    if theme is None:
        return _FALLBACK_GAP
    row = axis == "row"
    for st in (section, theme.elements):
        if st is None:
            continue
        gap = st.group_row_spacing if row else st.group_col_spacing
        if gap is not None:
            return gap
    element = theme.elements.row_spacing if row else theme.elements.col_spacing
    return element or _FALLBACK_GAP


def spacer_size(
    theme: Theme | None,
    step: str,
    axis: str,
    level: int,
    fixed_style_key: str | None = None,
    in_image_card: bool = False,
) -> float:
    """The px a spacer of *step* measures along *axis* (``row`` / ``col``).

    The nearest surface that states the step decides: the ``### Image Cards``
    block for a spacer inside a photo card, then the heading level that owns
    it, then ``### Root``. Levels do not inherit from one another, like every
    other per-level key. Within one surface ``Spacer <step> <axis>`` beats the
    plain ``Spacer <step>``. When none states it, a multiple of the group gap
    (``SPACER_MULTIPLES``), never less than its floor (``SPACER_FLOORS``).
    """
    surfaces = []
    sec = None
    if theme is not None:
        if in_image_card:
            surfaces.append(theme.image_cards)
        if level:
            sec = resolve_section_style(theme, level, fixed_style_key)
            if sec is not None:
                surfaces.append(sec)
        surfaces.append(theme.root)
    for st in surfaces:
        size = st.spacers.get(f"{step} {axis}", st.spacers.get(step))
        if size is not None:
            return size
    scaled = SPACER_MULTIPLES[axis][step] * _group_gap(theme, axis, sec)
    return max(scaled, SPACER_FLOORS[axis][step])


def spacer_cell(
    spelling: str, beside: MarkdownGroupNode | None = None, edge: bool = False
) -> MarkdownGroupNode:
    """The piece an inline spacer becomes in its line: a SPACER marked, like a
    drawn separator's cell, by ``separator_kind`` — which is also what tells it
    apart from a vertical spacer, and what keeps it out of the flow's gaps.

    It takes the spring alignment of the piece it belongs to (*beside*), so a
    `B +++` pushed right stays with B, one step in from the edge. An *edge*
    spacer is the line's own (`+++ B`): it stays where the line starts or ends,
    while one between pieces goes wherever the line wraps.
    """
    cell = MarkdownGroupNode(type=NodeType.SPACER, content=spelling)
    cell.separator_kind = "spacer"
    cell.spacer_binds = "edge" if edge else None
    if beside is not None:
        cell.authored_align = beside.authored_align
    return cell


def line_ask(
    cell: MarkdownGroupNode,
    min_of: Callable[[MarkdownGroupNode], float],
    size_of: Callable[[str], float],
) -> float:
    """The width *cell* asks for beside other cells on a line: its minimum, and
    for every line inside it that minimum with its spacers across at full size.

    A row wraps before its spacers give way: a cell whose padded line cannot
    fit beside its neighbours takes a line of its own, and only there, short of
    room, do its spacers shrink (ADR-203). The page minimum never counts them.
    """

    def across(n: MarkdownGroupNode) -> float:
        marks = [n.spacer_lead, n.spacer_trail]
        marks += [c.content for c in n.children if c.separator_kind == "spacer"]
        return sum(size_of(m) for m in marks if m)

    ask, stack = min_of(cell), [cell]
    while stack:
        n = stack.pop()
        if spaced := across(n):
            ask = max(ask, min_of(n) + spaced)
        stack.extend(c for c in n.children if c.type != NodeType.SPACER)
    return ask


def short_of_room(
    items: list[MarkdownGroupNode],
    width: float,
    ask_of: Callable[[MarkdownGroupNode], float],
    gap_of: Callable[[MarkdownGroupNode, MarkdownGroupNode], float],
    weights: list[float] | None = None,
) -> bool:
    """Whether a row of *items* holding spacers has no room for them at
    *width*: the renderer's give-way test (``render_measure._layout_row``),
    asked where a run can settle it for all its members. *ask_of* is what a
    piece needs beside a spacer; in a weighted row every weighted cell must
    keep that ask at its share."""
    gaps = sum(gap_of(a, b) for a, b in zip(items, items[1:]))
    asks = [ask_of(c) for c in items]
    if weights is None:
        return gaps + sum(asks) > width
    held = [a for a, w in zip(asks, weights) if not w]
    total = sum(weights) or 1.0
    share = max((a * total / w for a, w in zip(asks, weights) if w), default=0.0)
    return gaps + sum(held) + share > width


def trim_row_edges(batches: list[tuple[list, list]]) -> list[tuple[list, list]]:
    """The flowed rows of one line with the gaps they wrapped at taken out.

    A drawn separator or a spacer BETWEEN pieces exists only between
    neighbours: at the start or end of a wrapped row it is dropped, so no row
    ends on a dangling `|` or starts with blank space. A line's own edge spacer
    stays where it is — the first row keeps a leading indent. A row left with
    nothing but spacers is dropped: a spacer never takes a row of its own.
    """

    def gap(n) -> bool:
        return n.separator_kind is not None and n.spacer_binds != "edge"

    def blank(n) -> bool:
        return n.separator_kind == "spacer"

    out = []
    for batch, widths in batches:
        lo, hi = 0, len(batch)
        while lo < hi and gap(batch[lo]):
            lo += 1
        while hi > lo and gap(batch[hi - 1]):
            hi -= 1
        batch, widths = batch[lo:hi], widths[lo:hi]
        if batch and not all(blank(n) for n in batch):
            out.append((batch, widths))
    return out


def spacer_props(
    theme: Theme | None,
    spelling: str,
    axis: str,
    level: int,
    fixed_style_key: str | None,
    in_image_card: bool,
    binds: str | None = None,
) -> dict:
    """The ``spacer`` render property of one spacer leaf, its size resolved.

    *spelling* holds every mark the spacer was written as (`+++ ++++` for two
    consecutive ones): its size is the sum of their steps.
    """
    size = sum(
        spacer_size(
            theme,
            SPACER_STEPS.get(len(mark), "small"),
            axis,
            level,
            fixed_style_key,
            in_image_card,
        )
        for mark in spelling.split()
    )
    return {"axis": axis, "size": size, "binds": binds}


def fold_row_spacers(layout: LayoutNode) -> None:
    """Move every spacer that landed as a CELL of a row into its own cell.

    A spacer is vertical space inside a cell, never a column of its own: one
    written at the top of a `:::` cell reaches the row beside that cell,
    because a one-line cell has no container of its own to hold it. It goes
    into the cell it binds to (``binds``: the one before or after it), stacked
    with that cell's content.
    """
    for child in layout.children:
        fold_row_spacers(child)
    if layout.type != "row":
        return

    def is_spacer(n: LayoutNode) -> bool:
        # Vertical only: a horizontal spacer IS a cell of its row.
        sp = (n.render_properties or {}).get("spacer")
        return n.type == "-" and sp is not None and sp.get("axis") == "col"

    if not any(is_spacer(c) for c in layout.children):
        return
    # A row of spacers alone has no cell to fold them into: it stays as written.
    if all(is_spacer(c) for c in layout.children):
        return
    # A child without a ratio of its own takes the default share, never drops out.
    given = layout.ratios or []
    padded = [*given, *[1.0] * (len(layout.children) - len(given))]
    cells: list[LayoutNode] = []
    ratios: list[float] = []
    pending: list[LayoutNode] = []
    for child, ratio in zip(layout.children, padded):
        if is_spacer(child):
            binds = ((child.render_properties or {}).get("spacer") or {}).get("binds")
            if binds == "prev" and cells:
                cells[-1] = _stack(cells[-1], [], [child])
            else:
                pending.append(child)
            continue
        cells.append(_stack(child, pending, []) if pending else child)
        ratios.append(ratio)
        pending = []
    if pending:
        cells[-1] = _stack(cells[-1], [], pending)
    layout.children, layout.ratios = cells, ratios


def _stack(cell: LayoutNode, before: list, after: list) -> LayoutNode:
    """*cell* with *before* / *after* spacers stacked around its content."""
    if cell.type == "col":
        cell.children = [*before, *cell.children, *after]
        cell.ratios = [1.0] * len(cell.children)
        return cell
    kids = [*before, cell, *after]
    return LayoutNode(type="col", ratios=[1.0] * len(kids), children=kids)


def edge_spacers(
    node: MarkdownGroupNode,
    result: LayoutNode,
    make_leaf: Callable[[MarkdownGroupNode], LayoutNode],
    own_line: bool = False,
) -> LayoutNode:
    """*result* with the spacers written at its edges around it.

    Across: a flowed line puts them into its own row (``_with_separators``);
    any other node that carries one (a one-piece line, `+++ B`) is set in a
    row with them, space first or last. The row now positions the content, so
    an authored spring's alignment moves onto it — as the ring does
    (``_make_leaf``) for the same reason.

    *own_line*: *result* is the node's own line or row, which holds its edges
    across itself; what is left is the space written above and below it,
    stacked with it in a column — and the space of a cell beside it, which is
    not the line's.

    The space is inside whatever surface the node is: a card or a section
    moves onto the row, so its spacers sit between its edge and its content
    and the card keeps the width it would have without them. Space that was a
    cell beside the node (``spacer_beside``) stays outside the box the node
    paints for itself, as a cell beside it would.
    """
    if own_line:
        down = [
            make_leaf(MarkdownGroupNode(type=NodeType.SPACER, content=spelling))
            if spelling
            else None
            for spelling in (node.spacer_above, node.spacer_below)
        ]
        if down != [None, None]:
            kids = [n for n in (down[0], result, down[1]) if n is not None]
            col = LayoutNode("col", [1.0] * len(kids), kids)
            result = _hand_surface(result, col)
        if not node.spacer_beside:
            return result
    if not node.spacer_lead and not node.spacer_trail:
        return result
    lead = [make_leaf(spacer_cell(node.spacer_lead))] if node.spacer_lead else []
    trail = [make_leaf(spacer_cell(node.spacer_trail))] if node.spacer_trail else []
    kids = [*lead, result, *trail]
    row = LayoutNode(type="row", ratios=[1.0] * len(kids), children=kids)
    # A line with a cell beside it is spaced as the `:::` row of the two is: a line.
    row.line_split = own_line
    align = (result.render_properties or {}).get("content_align")
    if align is not None:
        row.render_properties = {"content_align": align}
    return _hand_surface(result, row, keep=_OWN_BOX if node.spacer_beside else ())


def holds(node: MarkdownGroupNode) -> bool:
    """Whether *node*'s spacers hold it, so it narrows to its own minimum
    before they give way: a block between two spacers, and one beside a spacer
    cell, which takes its room as the leaf cell it stands for would."""
    if not node.children:
        return False
    return node.spacer_beside or bool(node.spacer_lead and node.spacer_trail)


def _hand_surface(
    result: LayoutNode, holder: LayoutNode, keep: tuple[str, ...] = ()
) -> LayoutNode:
    """*holder*, now painting the surface *result* painted but *keep*."""
    for name in _SURFACE:
        if name not in keep:
            setattr(holder, name, getattr(result, name))
            setattr(result, name, LayoutNode.__dataclass_fields__[name].default)
    for name in _SURFACE_NAMES:  # what the content still reads its style by
        setattr(holder, name, getattr(result, name))
    return holder


# What paints a node's surface — moved onto the row that holds its spacers —
# and what names it, which its content keeps too.
_SURFACE = (
    "is_card",
    "card_kind",
    "background_kind",
    "section_level",
    "card_bg_url",
    "link_url",
    "link_node_id",
)
_SURFACE_NAMES = (
    "section_style_key",
    "heading_id",
    "rotation_index",
    "rotation_chain",
    "rotation_path",
)
# The box a node paints for itself rather than for the section it is: what
# space beside it stays outside of.
_OWN_BOX = ("background_kind",)


def ride_spacers(
    node: MarkdownGroupNode,
    only: MarkdownGroupNode,
    result: LayoutNode,
    make_leaf: Callable[[MarkdownGroupNode], LayoutNode],
) -> LayoutNode:
    """*result* for *only*, with the spacers written beside it in *node*.

    A spacer never keeps a group from passing through to its one child: they
    go at the start and end of the child's column, and a child laid out any
    other way is stacked with them in one.
    """
    at = node.children.index(only)
    before = [make_leaf(c) for c in node.children[:at]]
    after = [make_leaf(c) for c in node.children[at + 1 :]]
    if result.type != "col":
        kids = [*before, result, *after]
        return LayoutNode(type="col", ratios=[1.0] * len(kids), children=kids)
    result.children = [*before, *result.children, *after]
    result.ratios = [1.0] * len(result.children)
    return result
