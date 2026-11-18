"""The two authored partitions of a box: ``:::`` across, ``...`` down.

Both are whole-line tokens that cut a run of siblings and say how the pieces
share the space, which is why they live together: ``:::`` divides the width into
CELLS with weights, ``...`` divides the height into REGIONS pushed to the top
and bottom. The horizontal spring (`` ... `` inside one line) is the same idea a
level down, and ``grouper_separate._promote_align_regions`` is the pass this one
mirrors.

The second Phase 1 instruction, and the sibling of ``_apply_section_stops``.
That pass consumes every ``***``; this one consumes every ``:::``, and neither
type survives into the finished tree.

A ``:::`` cuts like ``___`` — it ends a glued run, bounds the heading peel, and
suppresses heading detection on its own line, all of which it gets from being in
``_BREAK_TYPES``. What it adds is the reason it exists: **the runs either side of
it are CELLS OF ONE ROW** rather than a stack, proportioned by the weight each
divider carries (``:::2``).

Two rules do all the work, and both are forced by the shape authors write:

* **A ``:::`` closes a heading section opened INSIDE the row, never the section
  containing it.** For the cells to be a row they have to be siblings, and a
  ``#`` heading in cell 2 would otherwise swallow cell 3. So the row forms at
  the depth of the run's FIRST divider, and later dividers are lifted to it —
  taking their tail with them, exactly as ``***`` re-parents a tail. A node with
  no divider of its own lifts nothing, which is what keeps ``## Card / A / ::: /
  B`` a row *inside* the card rather than one that escapes it. A section
  whose only ``:::`` is its last line is the exception: that divider cuts
  nothing inside it, so it closes the section as a cell of the row outside.

* **The divider partitions the whole sibling run**, as ``___`` already
  does — cell 1 is everything from the start of the run to the first
  ``:::``, not just the block immediately above it. A cell may hold several
  blocks. The one exception is a section's own heading node: it stays the title
  above the row, because a row that swallowed its card's title would reorder the
  document.

The wrapper this mints is deliberately plain — not glued, not a card. A ``:::``
is not a glue decision: glue never spans a cut (the segment scan already ends
there), is untouched inside a cell, and the row node itself carries none.
"""

from collections.abc import Callable

from md2ui.pipeline.grouper_types import (
    _HEADING_TYPE_RE,
    ITEM_DIVIDER,
    MarkdownGroupNode,
    NodeType,
)

# A cell whose divider carries no number -- `:::` rather than `:::2` -- or that
# has no divider at all (only the LAST cell can, which is why the trailing
# divider is optional) records ``None``: NO weight was written. The generator
# reads a row of ``None`` as a run that collapses and wraps like a ` - ` line,
# and a row with any number as proportions, where ``None`` is an equal share.

# The break spellings that BOUND a row. A `:::` divides one; these end it,
# exactly as they end any other run of siblings -- so a `___` written under the
# last cell closes the row instead of joining it. A `;;;` bounds it too, and is
# then dropped: the row ends and the run does not, so rows that repeat stay
# adjacent siblings and grid. Not `---`: it paints a line and cuts nothing, so
# a rule inside a row is content of the cell it is written in.
_OTHER_BREAKS = (
    NodeType.CONTENT_BREAK,
    NodeType.SECTION_STOP,
    NodeType.ROW_CLOSER,
)


def _is_divider(node: MarkdownGroupNode) -> bool:
    return node.type == NodeType.COLUMN_DIVIDER


def _is_rule(node: MarkdownGroupNode) -> bool:
    return node.type == NodeType.HORIZONTAL_RULE


def _holds_divider(node: MarkdownGroupNode) -> int | None:
    """Index of the first ``:::`` among *node*'s own children, or ``None``.

    Direct children only: a divider deeper down belongs to a row that will form
    at *its* depth, not this one.
    """
    for i, child in enumerate(node.children):
        if _is_divider(child):
            return i
    return None


def _leading_cells(
    section: MarkdownGroupNode, row_open: bool
) -> list[MarkdownGroupNode]:
    """Detach and return the cells the peel absorbed ABOVE *section*'s heading.

    The peel is transparent to ``:::``, so ``Links / ::: / ### Plan`` arrives
    with ``Links`` and its divider inside Plan's section. That is right while
    the row lives inside the section (``![Logo] / ::: / ## Heading / Text``).
    It is wrong once the section is itself a cell of a row outside it — closed
    by a ``:::`` that is its last line and its only one under the heading, or
    met while a row is already open here: then cell 1 is everything from the
    start of the run to the first ``:::``, and the section is the heading and
    its body. Returns ``[]`` and leaves the section alone otherwise.
    """
    kids = section.children
    heading = next(
        (i for i, c in enumerate(kids) if _HEADING_TYPE_RE.match(c.type or "")), None
    )
    if heading is None:
        return []
    above = [i for i in range(heading) if _is_divider(kids[i])]
    if not above:
        return []
    below = [i for i in range(heading, len(kids)) if _is_divider(kids[i])]
    closed_as_cell = below == [len(kids) - 1]
    if not (row_open or closed_as_cell):
        return []
    lead = kids[: above[-1] + 1]
    del kids[: above[-1] + 1]
    return lead


def _lift_dividers(node: MarkdownGroupNode) -> None:
    """Raise every ``:::`` in this node's run up to the run's own depth.

    Walks the children left to right. Until a divider is seen among them the
    node has no row open, so a heading section holding one keeps it — that is
    the row belonging *inside* the section — unless that divider is the
    section's only one and its last line: then the section is the row's first
    cell, as in four ``######`` columns each closed by ``:::``. Once a row IS
    open here, a heading section holding a divider is closed at it: the section
    keeps what came before, and the divider plus its tail are re-queued as
    siblings, so a second divider inside that tail lifts on the same pass.

    Mirrors ``_apply_section_stops``' re-parenting, with one difference — that
    pass DROPS the ``***`` it consumes, while the divider must survive the lift
    or the row loses the cut it names.

    Time: O(nodes at this level), Space: O(width).
    """
    pending = list(node.children)
    out: list[MarkdownGroupNode] = []
    row_open = False
    while pending:
        child = pending.pop(0)
        if _is_divider(child):
            row_open = True
            out.append(child)
            continue
        if child.type in _OTHER_BREAKS:
            # A row's scope ENDS at the other breaks, where ``_segments`` cuts
            # the run. The lift runs first, so it must close the row here too:
            # otherwise a heading section after a ``___`` is still closed at its
            # divider, and a card parses differently depending on whether ANY
            # earlier block in the document used a ``:::``.
            row_open = False
            out.append(child)
            continue
        if child.heading_group:
            lead = _leading_cells(child, row_open)
            if lead:
                # The cells written above the heading go back ahead of it, so
                # their divider opens the row and the section is seen again
                # holding only its heading and body.
                pending[:0] = [*lead, child]
                continue
            at = _holds_divider(child)
            # A section whose ONE divider is its last line is a cell that `:::`
            # closes: inside the section it would cut nothing apart, so it
            # opens the row here even when it is the run's first divider.
            closes_section = at is not None and at == len(child.children) - 1
            if at is not None and (row_open or closes_section):
                tail = child.children[at:]
                del child.children[at:]
                out.append(child)
                # The divider leads the tail, so the next loop sees it first
                # and keeps row_open true for whatever follows.
                pending[:0] = tail
                continue
        out.append(child)
    node.children = out


def _partition(
    children: list[MarkdownGroupNode],
) -> tuple[list[list[MarkdownGroupNode]], list[MarkdownGroupNode | None]]:
    """Split a sibling run at its dividers into ``(cells, closers)``.

    Each divider CLOSES the cell above it and hands over what it says about that
    cell; a run that ends without one records ``None`` (nothing written). An
    empty run — a leading divider, two in a row, or a trailing one — mints no
    cell, so a trailing ``:::2`` weights the last real cell instead of adding a
    blank column.
    """
    cells: list[list[MarkdownGroupNode]] = []
    closers: list[MarkdownGroupNode | None] = []
    cur: list[MarkdownGroupNode] = []
    for child in children:
        if not _is_divider(child):
            cur.append(child)
            continue
        if cur:
            cells.append(cur)
            closers.append(child)
            cur = []
        # An empty run has no cell for this divider's weight to land on, so the
        # weight is simply dropped -- the cut still happened.
    if cur:
        cells.append(cur)
        closers.append(None)
    return cells, closers


def _describe_row(row: MarkdownGroupNode, closers: list) -> None:
    """Stamp the row with what each cell's closing divider wrote, aligned with
    the cells: its weight, its weight in wide space, and the space the cut
    after it applies in. The last two stay empty unless some divider wrote
    them.
    """
    row.column_weights = tuple(None if d is None else d.column_weight for d in closers)
    wide = tuple(None if d is None else d.column_weight_wide for d in closers)
    cuts = tuple(None if d is None else d.column_when for d in closers)
    row.column_weights_wide = wide if any(w is not None for w in wide) else ()
    row.column_cuts = cuts if any(cuts) else ()


def _marker_prefix(children: list[MarkdownGroupNode]) -> int:
    """How many leading children are EMPTY heading markers, not content.

    A titled heading is cell 1 — ``## Title`` + ``:::`` + body is exactly how an
    author writes "title on the left, its text on the right", and holding it out
    leaves that row with one cell and so no row at all.

    An empty ``# `` / ``## `` marker is the opposite case and the project already
    says so (``line_stacks``): it is a GROUPING DEVICE, not a heading. Its title
    leaf carries no content, gets pruned, and the section collapses onto what it
    wrapped — which must then render exactly as it would anywhere else. Making it
    a cell buries that leaf inside the row and the section stops looking like one.
    """
    n = 0
    for child in children:
        if (
            not _HEADING_TYPE_RE.match(child.type or "")
            or (child.content or "").strip()
        ):
            break
        n += 1
    return n


def _segments(
    children: list[MarkdownGroupNode],
) -> list[tuple[bool, list[MarkdownGroupNode]]]:
    """Cut a sibling run at every break that bounds a row (``_OTHER_BREAKS``).

    ``___`` / ``***`` / ``;;;`` bound a row the same way they bound anything
    else, so a cut written after the last cell closes the row instead of being
    swallowed into it. Returns ``(is_row_candidate, nodes)`` in document order;
    the bounding break comes back as a segment of its own so it keeps its place.
    """
    out: list[tuple[bool, list[MarkdownGroupNode]]] = []
    cur: list[MarkdownGroupNode] = []
    for child in children:
        if child.type in _OTHER_BREAKS:
            if cur:
                out.append((True, cur))
                cur = []
            out.append((False, [child]))
            continue
        cur.append(child)
    if cur:
        out.append((True, cur))
    return out


def _is_spring(node: MarkdownGroupNode) -> bool:
    return node.type == NodeType.VERTICAL_SPRING


def _region_valigns(n: int) -> list[str]:
    """Alignment per region, by POSITION — the vertical twin of the ``...`` rule.

    First to the top, last to the bottom, anything between centred. One spring
    therefore reads "top | bottom" and two read "top | center | bottom", which
    is the ceiling: a third separates the middle without placing it, exactly as
    on the horizontal axis.
    """
    if n == 1:
        return ["top"]
    return ["top"] + ["center"] * (n - 2) + ["bottom"]


def build_vertical_springs(node: MarkdownGroupNode) -> None:
    """Consume every ``...`` line under *node*, stamping the regions it places.

    A spring cuts its siblings into REGIONS and the region's position is its
    alignment. An empty region — a leading or trailing spring — keeps its slot
    without minting a node, so ``...`` before the only block pushes it to the
    bottom and after it pushes it to the top, the way an edge spring works on a
    line.

    Runs after the rows are built, so a spring inside a ``:::`` cell partitions
    that cell rather than the row: the cell is the box with height to give away.

    Time: O(nodes), Space: O(width).
    """
    for child in node.children:
        build_vertical_springs(child)
    if not any(_is_spring(c) for c in node.children):
        return
    regions: list[list[MarkdownGroupNode]] = [[]]
    for child in node.children:
        if _is_spring(child):
            regions.append([])
            continue
        regions[-1].append(child)
    valigns = _region_valigns(len(regions))
    out: list[MarkdownGroupNode] = []
    for nodes, valign in zip(regions, valigns):
        if not nodes:
            continue  # an empty region keeps its slot, not a child
        for n in nodes:
            if n.authored_valign is None:
                n.authored_valign = valign
        out.extend(nodes)
    if out:
        node.valign_group = True
    node.children = out


def hand_down_valign(region: MarkdownGroupNode, pieces: list) -> None:
    """Keep a region's placement on the pieces that replace it.

    A ``...`` region is placed as ONE block in the box the springs divide. When
    a later phase splits it into its lines, or dissolves its level, the pieces
    stand in that box directly, so each takes the region's alignment unless it
    has its own: still one contiguous block, in the same place.
    """
    if region.authored_valign is None:
        return
    for piece in pieces:
        if piece.authored_valign is None:
            piece.authored_valign = region.authored_valign


def take_edge_spacer_cells(cells: list[list], closers: list) -> list[str | None]:
    """Take the cells at either end of a row's partition that hold only
    ``+++`` spacers, and return ``[lead, trail]``: the space they were.

    Space at a row's edge is the row's own, as `+++ A | B` puts it on its
    line, never a column — and a row of one cell is that cell with the space
    beside it. Consecutive ones are one space, their marks in written order.
    """
    lead: list[str] = []
    while cells and all(n.type == NodeType.SPACER for n in cells[0]):
        lead += [n.content for n in cells.pop(0)]
        closers.pop(0)
    trail: list[str] = []
    while cells and all(n.type == NodeType.SPACER for n in cells[-1]):
        trail[:0] = [n.content for n in cells.pop()]
        closers.pop()
    return [" ".join(lead) or None, " ".join(trail) or None]


def _as_cell(nodes: list[MarkdownGroupNode]) -> MarkdownGroupNode:
    """One cell: the node itself when it is alone, else a plain wrapper.

    A single-node cell is spliced in as-is so the row does not add a level the
    document did not ask for -- ``_collapse_groups`` would only unwrap it again.
    The exception is a lone run of text that the blank-line split will still
    divide: it is several blocks of ONE side, and without its wrapper they would
    land in the row as columns of their own.
    """
    if len(nodes) == 1 and not _holds_blocks(nodes[0]):
        return nodes[0]
    cell = MarkdownGroupNode(type=NodeType.GROUP)
    cell.children = nodes
    return cell


def _holds_blocks(node: MarkdownGroupNode) -> bool:
    """Whether *node* is a leaf text that a blank line still divides."""
    return (
        node.type == NodeType.TEXT
        and not node.children
        and "\n\n" in node.content.strip()
    )


def build_column_rows(node: MarkdownGroupNode) -> None:
    """Consume every ``:::`` under *node*, minting the rows they describe.

    Top-down, unlike ``_apply_section_stops``: the lift has to run at this level
    BEFORE the children are visited, or a nested pass would have already wrapped
    the divider that needs raising and hidden it from view.

    The run is cut first at the OTHER break spellings, so a ``___`` under the
    last cell ends the row rather than joining it, and each bounded segment is
    partitioned on its own. A segment that yields fewer than two cells is not a
    row -- a lone ``:::`` at the end of a section cut nothing apart -- so its
    nodes are spliced straight back and only the dividers disappear.

    A section's own heading is IN the row, as cell 1 along with anything
    absorbed above it. ``## Title`` + ``:::`` + body is the shape an author
    writes for "title beside its text", and holding the heading out would leave
    that row with one cell and silently no row at all.

    Time: O(nodes), Space: O(depth + width).
    """
    _lift_dividers(node)

    if any(_is_divider(c) for c in node.children):
        # An empty marker stays ahead of the row rather than becoming a cell.
        keep = _marker_prefix(node.children)
        out: list[MarkdownGroupNode] = list(node.children[:keep])
        for is_candidate, nodes in _segments(node.children[keep:]):
            if not is_candidate or not any(_is_divider(n) for n in nodes):
                out.extend(n for n in nodes if not _is_divider(n))
                continue
            cells, closers = _partition(nodes)
            # Rules alone after the last divider are no cell, as an empty run is
            # none: they paint under the row rather than becoming a column.
            under = []
            if cells and closers[-1] is None and all(map(_is_rule, cells[-1])):
                under = cells.pop()
                closers.pop()
            space = take_edge_spacer_cells(cells, closers)
            if len(cells) == 1 and any(space):
                # One cell between spacer cells is that cell with space beside
                # it, outside any box it paints. Its own level holds the space
                # while later phases split what is inside it.
                only = MarkdownGroupNode(type=NodeType.GROUP)
                only.children = cells[0]
                only.spacer_lead, only.spacer_trail, only.spacer_beside = *space, True
                out.append(only)
                out.extend(under)
                continue
            if len(cells) < 2:
                # Dividers that partitioned nothing: drop them, keep the content
                # (the rules under it included, where they were written).
                out.extend(n for n in nodes if not _is_divider(n))
                continue
            row = MarkdownGroupNode(type=NodeType.GROUP)
            row.column_row_group = True
            _describe_row(row, closers)
            row.children = [_as_cell(c) for c in cells]
            row.spacer_lead, row.spacer_trail = space
            out.append(row)
            out.extend(under)
        node.children = out
    # Every `;;;` has bounded its row by now; one outside any row cut nothing.
    node.children = [c for c in node.children if c.type != NodeType.ROW_CLOSER]

    for child in node.children:
        build_column_rows(child)


def row_flows(row: MarkdownGroupNode) -> bool:
    """Whether *row* is a LINE spelled across blocks: no weight and no cut
    written, so its cells flow and wrap like the pieces of a `` - `` line.
    A row with a number is proportions instead, and one with a `<` / `>`
    regroups its cells by width."""
    return not (
        any(w is not None for w in row.column_weights)
        or row.column_weights_wide
        or row.column_cuts
    )


def mark_row_pieces(row: MarkdownGroupNode) -> None:
    """Name a flowing row's one-line text cells as the pieces of its line —
    the segments a `` | `` would have cut — so the row is the same kind of
    node as the line it spells. A cell holding a split line stays that line."""
    for cell in row.children:
        if not cell.children and cell.type == NodeType.TEXT:
            cell.type = NodeType.SEGMENT


# ---------------------------------------------------------------------------
# A `:::` indented under a list item divides THAT ITEM, not the document.
# ---------------------------------------------------------------------------


def build_item_rows(
    item: MarkdownGroupNode, stamp: Callable[[MarkdownGroupNode, str], None]
) -> None:
    """Turn a list item's scoped ``:::`` and ``...`` back into breaks, and build
    the row and the regions they describe.

    ``grouper_block_splits.scope_item_dividers`` wrote them as ``ITEM_DIVIDER``
    lines; *stamp* reads the ``:::N`` spelling back onto the node, handed in by the
    grouper so this module keeps to the node model.

    Runs on one item once Phase 2.1 has made its body its own children, so the
    row is made of the item's lines and nothing else: the heading and the next
    item are out of reach. The row then sits INSIDE the item, which is what
    keeps the item's marker and its surface around every cell.
    """

    def is_scoped(node: MarkdownGroupNode) -> bool:
        return not node.children and node.content.startswith(ITEM_DIVIDER)

    # A blank line in the item makes paragraph groups, and a divider can land
    # inside one. It is a cut all the same, so that paragraph opens into the
    # item's run and the divider partitions the item, not the paragraph.
    opened: list[MarkdownGroupNode] = []
    for child in item.children:
        if child.children and any(is_scoped(c) for c in child.children):
            opened.extend(child.children)
        else:
            opened.append(child)
    item.children = opened
    found = False
    for child in item.children:
        if is_scoped(child):
            spelling = child.content[len(ITEM_DIVIDER) :]
            child.content = spelling
            child.type = (
                NodeType.VERTICAL_SPRING
                if spelling == "..."
                else NodeType.COLUMN_DIVIDER
            )
            if _is_divider(child):
                stamp(child, spelling)
            found = True
    if not found:
        return
    # The item's lines were one glued run while the breaks were text. A `:::`
    # or `...` is a cut and glue never spans one, so a piece of one line is no
    # longer glued to anything; a piece of several keeps the run, and stays one
    # block.
    pieces: list[list[MarkdownGroupNode]] = [[]]
    for child in item.children:
        if _is_divider(child) or _is_spring(child):
            pieces.append([])
        else:
            pieces[-1].append(child)
    for piece in pieces:
        if len(piece) == 1:
            piece[0].glued_content_id = None
    build_column_rows(item)
    # The row IS the item, as a ` - ` line is: `- A - B` makes the item itself
    # the line group, so this does too. Left as the item's one child group it
    # would read as a card inside the item.
    if len(item.children) == 1 and item.children[0].column_row_group:
        row = item.children[0]
        item.children = row.children
        item.take_column_row(row)
    # After the row, as at the top level: a spring inside a cell partitions
    # that cell, and one in an item with no row partitions the item.
    build_vertical_springs(item)
