"""What a layout unit is, how big it is, and what goes between two of them.

The vocabulary every arrangement decision is written in: the gap between two
cells, the padding inside one, a unit's minimum width, an estimate of its height,
and the small tests that say what kind of unit it is at all — leaf or group, key
or value, a pure run of elements, which heading level a node sits at.

None of it decides an arrangement. `LayoutGenerator` does that, and calls in here
for the numbers and the predicates it reasons with. These are pure functions of a
node: no theme, no measurers, no oracles, no caches — which is exactly why they
could leave the class while the rest of it could not.

**Deliberately untouched by the authored hints.** Nothing here reads the URL
params or the theme's asides.
"""

import math

from md2ui.pipeline import generator_markers
from md2ui.pipeline.grouper_types import (
    MarkdownGroupNode,
    NodeType,
    STRUCTURAL_BACKGROUND_KINDS,
    _HEADING_TYPE_RE,
)
from md2ui.pipeline.grouper_column_rows import row_flows
from md2ui.pipeline.layout_script_parser import LayoutNode

# An image's estimated height uses the renderer's default ratio, not a copy of it.
from md2ui.pipeline.render_metrics import default_image_ratio

# The generator decides gaps the renderer will later draw, so it asks the
# renderer's own resolver rather than keeping a second copy of the rule.
from md2ui.pipeline.render_spacing import _resolve_section_spacing
from md2ui.pipeline.theme import TABLE_KEY_COL_MAX_SHARE, resolve_section_style

LEAF_WIDTH: dict[str, float] = {
    "one_word": 80.0,
    "very_short": 100.0,
    "short": 200.0,
    "medium": 320.0,
    "paragraph": 580.0,
}


# Minimum width an image cell needs before it is worth placing beside content.
IMAGE_MIN_WIDTH: float = 96.0


BENTO_MIN_CELLS: int = 3  # containers with fewer cells keep the default layout


# Crude single-line text width (px) per content-length category, for the
# measurer-less cell-height estimate (unit tests / script callers without fonts).
_BENTO_EST_LINE_PX: dict[str, float] = {
    "one_word": 70.0,
    "very_short": 120.0,
    "short": 260.0,
    "medium": 480.0,
    "paragraph": 900.0,
    "long_paragraph": 1800.0,
}


_BENTO_EST_LINE_H: float = 22.0  # nominal wrapped line height (px)


_BENTO_EST_GAP: float = 8.0  # nominal gap between leaves (px)


def _bento_est_image_ratio(width: float) -> float:
    """Estimated image W/H ratio for the bento height estimate: an image with no
    authored ratio at *width* — the renderer's own default, so the two agree."""
    return default_image_ratio(width)


def _unit_padding_x(node: MarkdownGroupNode, theme=None) -> float:
    """Horizontal wrap padding a *unit* gets from its own outermost wrap(s).

    A glued-content group is wrapped as a card (elements padding), a photo card
    as an image card (its own ``### Image Cards`` padding, which the overlay sits
    inside); a heading-section group adds that level's section padding. A node can
    be both (independent flags), so the two are summed. Nested/inner wraps are out
    of scope. 0 without a theme.
    """
    if theme is None:
        return 0.0
    pad = 0.0
    if node.card_bg_url is not None:
        cards = theme.image_cards if theme.image_cards.is_active() else theme.elements
        pad += cards.padding.x
    elif node.glued_content_group:
        pad += theme.elements.padding.x
    if node.heading_group and node.heading_level is not None:
        st = resolve_section_style(theme, node.heading_level, node.fixed_style_key)
        if st is not None:
            pad += st.padding.x
    if kind := STRUCTURAL_BACKGROUND_KINDS.get(node.type):
        style = getattr(theme, f"{kind}s")
        if kind == "task_list" and not style.is_active():
            style = theme.unordered_lists
        pad += style.padding.x
    return pad


def _is_pure_element_group(node: MarkdownGroupNode) -> bool:
    """A group whose entire leaf content is ELEMENT leaves — chips, links or
    emojis, in any mix (≥1): the grouper's ``pure_element`` stamp.

    Mirrors the renderer's ``_is_pure_element_block``: such units space with
    *element* gaps (like the elements they contain), not group gaps.
    """
    return node.pure_element


def _is_key_unit(node: MarkdownGroupNode) -> bool:
    """A KV *key* side: a ``key``-typed leaf, or a group whose entire leaf
    content is ``key``-typed (the grouper's ``key_side`` stamp). Mirrors the
    renderer's ``_is_key_block``."""
    if not node.children:
        return bool(node.content) and node.type == "key"
    return node.key_side


def _group_spacing(row: bool, theme) -> float:
    """Group gap on the given axis: the theme's group spacing, falling back to
    the element spacing, then 0.

    Mirrors the renderer's ``_resolve_group_spacing``. Used both for plain group
    units and as the fallback for a heading level that declares no spacing.
    """
    grp = theme.elements.group_row_spacing if row else theme.elements.group_col_spacing
    if grp is not None:
        return grp
    return (theme.elements.row_spacing if row else theme.elements.col_spacing) or 0.0


def _flows_as_line(unit: MarkdownGroupNode) -> bool:
    """Whether an authored ``:::`` row is a line toward its neighbours: it flows,
    and not every cell is a block (the renderer's ``block_line``)."""
    return bool(
        getattr(unit, "column_row_group", False)
        and row_flows(unit)
        and not all(c.children for c in unit.children)
    )


def _cell_gap(
    unit: MarkdownGroupNode,
    theme=None,
    axis: str = "row",
    owner_level: int = 0,
    owner_key: str | None = None,
) -> float:
    """Gap the renderer inserts between adjacent siblings of this unit kind on
    *axis* ("row" | "col").

    Mirrors ``_sibling_gap``'s resolution for the relevant cases: sibling
    *sections* call the renderer's own ``_resolve_section_spacing(owner_level)``
    — the **enclosing** level's spacing, falling back to the group spacing when
    that level declares none, and NOT the unit's own level. At ``owner_level``
    0 that is ``Root → Spacing``. Calling the renderer's one resolver, rather
    than repeating its lookup, keeps the batch and the drawing from drifting
    apart (ADR-400).
    ``line_split_group`` units and the flowing ``:::`` rows that space like
    them (``_flows_as_line``), KV
    *key* units and *pure pill* group units (links / inline_code) use the
    element spacing (one line's pieces, keys next to their values, and pill
    groups all space like leaves);
    other glued/plain group units use the group spacing (fallback element
    spacing). 0 without a theme.

    Not an exact mirror for the *pure pill* case: the renderer additionally
    requires the adjacency to sit inside one line block
    (``_sibling_gap``'s ``gap_in_line``), so two pill CARDS stay a group gap
    apart. Every call here asks about gaps *within* a run/grid (``_col_gap`` in
    ``_flow_rows`` / ``_build_grouped`` / the aside splits), which is exactly
    the case that keeps the element gap on both sides.
    """
    if theme is None:
        return 0.0
    row = axis == "row"
    if unit.heading_group and unit.heading_level is not None:
        # The owner's fixed style, not the unit's own (see _fill_container_levels).
        return _resolve_section_spacing(owner_level, axis, theme, owner_key)
    if (
        (
            (getattr(unit, "line_split_group", False) or _flows_as_line(unit))
            and not unit.glued_content_group  # glued wins: cards space as cards
            # A heading's line spaces as a heading toward its neighbors, even
            # though its own pieces flow (mirrors _sibling_gap's _line_side).
            and not _HEADING_TYPE_RE.match(unit.type)
        )
        or _is_key_unit(unit)
        or _is_pure_element_group(unit)
    ):
        return (
            theme.elements.row_spacing if row else theme.elements.col_spacing
        ) or 0.0
    return _group_spacing(row, theme)


def _col_gap(
    unit: MarkdownGroupNode,
    theme=None,
    owner_level: int = 0,
    owner_key: str | None = None,
) -> float:
    """Row-axis gap the renderer inserts between adjacent columns of this unit kind."""
    return _cell_gap(unit, theme, "row", owner_level, owner_key)


def _batch_width(items: list, widths: list[float], theme) -> float:
    """What one flow batch occupies: its pieces plus the gaps between them.

    The width a batch is ADMITTED at (``_balance_batches``) and the width it is
    flushed at (``_flow_rows``) are the same question, and were once two
    expressions -- one of which read a running total ``close()`` had already
    reset, so every packed row believed its whole width was leftover and shared
    it out. One function, so the two cannot drift apart again.
    """
    return sum(widths) + sum(
        _flow_pair_gap(items[i - 1], items[i], theme) for i in range(1, len(items))
    )


def _flow_pair_gap(prev: MarkdownGroupNode, cur: MarkdownGroupNode, theme) -> float:
    """Gap the renderer will put between two adjacent pieces of ONE flowed line.

    ``_cell_gap`` answers for a unit KIND within a run or grid, where every unit
    is group-ish; a flowed line mixes leaves, blocks, pills and drawn separators,
    so the choice has to be made per PAIR the way ``_sibling_gap`` makes it:

    - a drawn row separator keeps the element gap on both sides, whatever it
      separates;
    - two element-ish pieces (leaves, pure-pill blocks, a KV key side) take the
      element gap — ``_sibling_gap`` rule 3 plus its ``gap_in_line`` exception,
      which always applies here because a flowed line IS a line block;
    - otherwise at least one side is a block, and rule 2 gives the GROUP gap.

    A flat element gap here would measure a line of colon columns narrower than
    it draws: the batch would "fit", the renderer would disagree, and the
    overflow branch would scale the cells down until an unbreakable word clipped.
    """
    if theme is None:
        return 0.0
    element = theme.elements.row_spacing or 0.0
    # A drawn separator; not an inline spacer, which is spaced like the leaf
    # it is — element beside a leaf, group beside a block — on each side
    # (ADR-203), exactly as the renderer's _sibling_gap spaces it.
    if any(n.separator_kind not in (None, "spacer") for n in (prev, cur)):
        return element

    def _elementish(n: MarkdownGroupNode) -> bool:
        return not n.children or _is_pure_element_group(n) or _is_key_unit(n)

    if _elementish(prev) and _elementish(cur):
        return element
    return _group_spacing(True, theme)


def _row_pair_gap(
    prev: MarkdownGroupNode,
    cur: MarkdownGroupNode,
    theme=None,
    owner_level: int = 0,
    owner_key: str | None = None,
) -> float:
    """Gap between two items of a weighted `:::` row: one beside a gap cell (a
    spacer, a drawn separator) is spaced as in a line, two cells as columns."""
    if prev.separator_kind is not None or cur.separator_kind is not None:
        return _flow_pair_gap(prev, cur, theme)
    return _col_gap(cur, theme, owner_level, owner_key)


def _table_cell_padding_x(cell: MarkdownGroupNode, theme=None) -> float:
    """Horizontal per-cell label padding from the THEME.md table style."""
    if theme is None:
        return 0.0
    st = theme.tables.header if cell.table_role == "header" else theme.tables.cells
    return st.padding.x


def _table_col_gap(theme=None) -> float:
    """Gap between table columns: the table's row spacing, falling back to
    the element row spacing (mirrors the renderer's _sibling_gap table rule)."""
    if theme is None:
        return 0.0
    v = theme.tables.table.row_spacing
    if v is not None:
        return v
    return theme.elements.row_spacing or 0.0


def _length_category(node: MarkdownGroupNode) -> str | None:
    """Per-node content length used for layout min-width.

    Prefers the grouper's per-node ``content_length_category`` (each element's own
    word count, so a one-word box is ``one_word`` even when its fingerprint cluster
    averages longer); falls back to the cluster-average ``text_length_category``
    when unset (e.g. older serialized ASTs).
    """
    return node.content_length_category or node.text_length_category


# A K-V role never reaches a leaf that draws as something other than text: an
# element owns its own styling (a link its variant, a chip its pill, an image
# itself), and a drawn datapoint owns its bar, ring or chip.
_KV_ROLE_ELEMENTS = frozenset(
    {
        NodeType.LINK,
        NodeType.IMAGE,
        NodeType.EMOJI,
        NodeType.INLINE_CODE,
        NodeType.CODE_BLOCK,
        NodeType.DRAWING_ELEMENT,
    }
)


def kv_role_map(root: MarkdownGroupNode, theme) -> dict[str, str]:
    """``{node_id: "key" | "value"}`` — every node the theme's ``Key`` /
    ``Value`` text style covers.

    The ONE place the rule lives, read by measurement (``_measured_min_width``,
    ``_line_item_width``) and by paint (``_make_leaf``) alike, so the two cannot
    drift (ADR-400). The role is the node's nearest ``KEY`` / ``VALUE``
    ancestor — or the node itself — because a ``VALUE`` may wrap its text one or
    two levels down (`$412M (49% of total)`), and a nested pair inside a value
    re-decides for its own subtree.

    Empty unless the theme authored the block, so a theme with no ``Key`` /
    ``Value`` measures and paints exactly as it did before. A heading line is
    NOT excluded here — the key of `## Total: $9` is still a key; the heading
    wins later, at ``_apply_kv_role``, where every other authored selector is
    already weighed.
    """
    want_key = getattr(theme, "key_style", None) is not None
    want_value = getattr(theme, "value_style", None) is not None
    out: dict[str, str] = {}
    if not (want_key or want_value):
        return out

    def walk(node: MarkdownGroupNode, role: str | None) -> None:
        if node.type is NodeType.KEY:
            role = "key" if want_key else None
        elif node.type is NodeType.VALUE:
            role = "value" if want_value else None
        if role is not None and node.type not in _KV_ROLE_ELEMENTS:
            if node.datapoint_display is None and node.node_id:
                out[node.node_id] = role
        for child in node.children:
            walk(child, role)

    walk(root, None)
    return out


def _stacked_table_min(
    node: MarkdownGroupNode,
    measure_width,
    theme,
    cache: dict | None,
    kv_roles: dict[str, str] | None,
) -> float | None:
    """How narrow a table may go once ``Stacking cards`` takes the grid over.

    The grid minimum is a SUM across columns; a stacked card is a single column
    of key/value pairs, so its minimum is the widest single VALUE plus the key
    column beside it — a different and far smaller number. Mirrors the cards
    branch of ``render_measure._table_plan``:

    * the header row supplies the key LABELS, not values, so it is not measured;
    * ``Card layout: title`` lifts each row's first cell out of the pairs and
      hands it the whole card width, so it is floored on its own;
    * a value shares the card with the key column, which the renderer caps at
      ``TABLE_KEY_COL_MAX_SHARE`` of the card's inner width. At the minimum that
      cap is always what binds, so ``inner - share*inner - key_spacing >= value``
      is solved directly instead of measuring label text — `measure_width`
      answers for pill-type leaves only, and the solved bound agrees with the
      renderer exactly where it matters;
    * a card pays ``tables.cells.padding`` ONCE, around the whole card. There is
      no per-cell label padding in this mode, unlike the grid.

    Returns ``None`` when the table has no body rows to stack, so the caller
    keeps the grid minimum rather than inventing a floor from nothing.
    """
    tt = getattr(theme, "tables", None)
    if tt is None:
        return None
    rows = [c for c in node.children if c.type == NodeType.TABLE_ROW]
    if not rows:
        return None
    title = tt.card_layout == "title"
    value_min = 0.0
    first_min = 0.0
    for r in rows:
        for j, cell in enumerate(r.children):
            m = _measured_min_width(cell, measure_width, theme, cache, kv_roles, True)
            if title and j == 0:
                first_min = max(first_min, m)
            else:
                value_min = max(value_min, m)
    # Guarded so a future share of 1.0 could never divide by zero.
    denom = max(0.1, 1.0 - TABLE_KEY_COL_MAX_SHARE)
    inner = (tt.key_spacing + value_min) / denom if value_min > 0 else 0.0
    return max(inner, first_min) + tt.cells.padding.x


def _measured_min_width(
    node: MarkdownGroupNode,
    measure_width=None,
    theme=None,
    cache: dict | None = None,
    kv_roles: dict[str, str] | None = None,
    stacked_tables: bool = False,
) -> float:
    """Widest *unbreakable* unit in *node*'s subtree — a whole pill (link /
    inline_code never wrap) or a single word of text — measured INSIDE
    *node*'s own wrap: each descendant's own wrap padding along the path is
    added, since nested section/card insets really consume that width before
    the leaf renders. The caller adds *node*'s own padding, mirroring
    ``_min_width`` / ``_cols_for_unit``.

    *measure_width* is the renderer-supplied
    ``Callable[[node, emphasis], float | None]`` (None where there is no text
    constraint, e.g. images); returns 0.0 without a measurer, so callers can fold
    it in with ``max(...)`` at no effect. *kv_roles* is ``kv_role_map``'s table,
    so a leaf the theme's ``Key`` / ``Value`` style covers is measured at that
    style's font rather than the body's.
    *cache* (keyed by ``(id(node), stacked_tables)``) memoizes subtree
    results across the many fit checks of one ``generate()`` pass.

    *stacked_tables* asks for the floor a table has once ``Stacking cards``
    takes over — the widest single cell, not the summed columns. Only
    ``document_min_width`` sets it: the page may shrink until the cards
    themselves stop fitting, while a table sitting in a GRID cell still reserves
    its full grid width, so the packer can never hand a cell less than the
    renderer's stacking threshold.
    """
    if measure_width is None:
        return 0.0
    role = kv_roles.get(node.node_id) if kv_roles and node.node_id else None
    key = (id(node), stacked_tables)
    if cache is not None and key in cache:
        return cache[key]
    table_types = (NodeType.TABLE_HEADER, NodeType.TABLE_ROW)
    if node.table_group and any(c.type in table_types for c in node.children):
        # Table container: columns align ACROSS rows, so the min is the sum
        # of per-COLUMN maxima (cell min + per-cell label padding) + gaps —
        # NOT the widest row's own sum (wide cells in different rows would
        # under-count and the grid packer would grant cells less than the
        # renderer's stacking threshold). Mirrors _table_plan's mins.
        stacked = (
            _stacked_table_min(node, measure_width, theme, cache, kv_roles)
            if stacked_tables
            and getattr(getattr(theme, "tables", None), "stacking", False)
            else None
        )
        if stacked is not None:
            # The theme stacks, and the caller is measuring how narrow the PAGE
            # may get: this table will be cards there, not a grid, so its grid
            # width is not a constraint on anything.
            result = stacked
        else:
            gap = _table_col_gap(theme)
            rows = [c for c in node.children if c.type in table_types]
            n_cols = max(len(r.children) for r in rows)
            col_mins = [0.0] * n_cols
            for r in rows:
                for j, cell in enumerate(r.children):
                    col_mins[j] = max(
                        col_mins[j],
                        _measured_min_width(
                            cell, measure_width, theme, cache, kv_roles, stacked_tables
                        )
                        + _table_cell_padding_x(cell, theme),
                    )
            result = sum(col_mins) + max(0, n_cols - 1) * gap
        # Stray non-table children (defensive) still floor the width.
        for c in node.children:
            if c.type not in table_types:
                result = max(
                    result,
                    _measured_min_width(
                        c, measure_width, theme, cache, kv_roles, stacked_tables
                    )
                    + _unit_padding_x(c, theme),
                )
    elif node.type in table_types:
        # A standalone table row: SUM of its cells + gaps (fallback when a
        # row is measured outside its container).
        gap = _table_col_gap(theme)
        result = (
            sum(
                _measured_min_width(
                    c, measure_width, theme, cache, kv_roles, stacked_tables
                )
                + _table_cell_padding_x(c, theme)
                for c in node.children
            )
            + max(0, len(node.children) - 1) * gap
        )
    elif node.children:
        result = max(
            (
                _measured_min_width(
                    c, measure_width, theme, cache, kv_roles, stacked_tables
                )
                + _unit_padding_x(c, theme)
                for c in node.children
            ),
            default=0.0,
        )
    else:
        # Pass the K-V role only when there is one, so single-argument
        # measurers (older callers / test doubles) keep working and a document
        # the theme does not style this way measures byte-for-byte as before.
        result = (
            measure_width(node, role) if role is not None else measure_width(node)
        ) or 0.0
        if stacked_tables and node.type == NodeType.CODE_BLOCK and theme is not None:
            # Code does not wrap, so the PAGE floor stops at ``Min width`` and a
            # longer line clips there; an arrangement still sees the whole line.
            result = min(result, theme.code_blocks.min_width)
    # A unit ratio drawn as a circular ring can never be narrower than the
    # ring itself (the text minimum above would let a grid cell squeeze it).
    dpth = getattr(theme, "datapoints", None)
    if (
        dpth is not None
        and node.datapoint_display == "unit_ratio"
        and dpth.unit_ratio_enabled
        and dpth.unit_ratio_style == "ring"
    ):
        result = max(result, dpth.ring.diameter)
    if cache is not None:
        cache[key] = result
    return result


def document_min_width(
    root: MarkdownGroupNode, theme=None, measure_width=None
) -> float:
    """The narrowest width *root* can be laid out at without clipping.

    The subtree's widest unbreakable unit — a whole pill, a single word at its
    effective font, a table's summed per-column minima. In CONTENT space: the
    root's own ``theme.root.padding`` sits outside the generated layout and so
    is not included. Returns 0.0 without a *measure_width*, so a measurer-less
    caller simply gets no floor.

    A table is the exception, and it is why this asks for ``stacked_tables``:
    under ``Stacking cards: yes`` the page is allowed to keep shrinking past the
    grid's own width, because down there the table is no longer a grid — each
    row becomes a card. Its floor is what a CARD needs. Without the key, or with
    ``Stacking cards: no``, the summed columns stand and the window scrolls.

    Deliberately not ``_min_width``: that one also floors at the ``LEAF_WIDTH``
    category guesses and returns ``inf`` for a ``long_paragraph``, neither of
    which is a real rendering constraint. This is the floor the app shell hands
    ``_content_width`` so the layout stops shrinking at what its content needs
    and the window scrolls horizontally instead.
    """
    return _measured_min_width(
        root, measure_width, theme, {}, kv_role_map(root, theme), True
    )


def _min_width(
    node: MarkdownGroupNode, theme=None, measure_width=None, cache=None, kv_roles=None
) -> float:
    """Minimum width *node* needs to render without compression.

    Reuses ``LEAF_WIDTH`` (keyed by the per-node ``content_length_category``).
    Images get their authored ``min_width``, which the measurer reports
    (``with_image_floors``), else ``IMAGE_MIN_WIDTH``; ``long_paragraph`` /
    unknown categories return ``inf`` so wide text can never be squeezed into a
    shared row. When a ``theme`` is given, the unit's own wrap padding is added so
    the fit checks match what the renderer can actually deliver. When
    *measure_width* is given, the width also floors at the subtree's widest
    unbreakable unit — a whole pill (links/inline_code never wrap) or a single
    word of text.
    """
    if node.type == "image":
        base = 0.0
    elif node.type == NodeType.CODE_BLOCK:
        # Code is not prose: its word count says nothing about the width it
        # reads at. Its floor is its own measured width, below.
        base = 0.0
    else:
        w = LEAF_WIDTH.get(_length_category(node) or "")
        if w is None:
            return float("inf")
        base = w
    base = max(base, _measured_min_width(node, measure_width, theme, cache, kv_roles))
    if node.type == "image" and not base:
        # No authored floor was measured: the default stands. An authored one
        # replaces it, lower or higher.
        base = IMAGE_MIN_WIDTH
    return (
        base
        + _unit_padding_x(node, theme)
        + generator_markers.marker_gutter_x(node, theme)
    )


def _section_level(node: MarkdownGroupNode) -> int | None:
    """*node*'s heading level when it is a heading SECTION, else ``None``.

    A section that holds only its title collapses onto its ``heading{N}`` leaf,
    which then carries ``heading_group`` itself (see the grouper's
    ``_derive_line_split_groups``), so this catches both the section container
    and the collapsed shape without a type test.
    """
    if node.heading_group and node.heading_level is not None:
        return node.heading_level
    return None


def _level_runs(node: MarkdownGroupNode, best: dict[int, int]) -> None:
    """Record, per heading level, the longest CONTIGUOUS run of sections at that
    level sharing one parent, over the whole subtree."""
    run_level: int | None = None
    run_len = 0
    for child in node.children:
        lvl = _section_level(child)
        if lvl is not None and lvl == run_level:
            run_len += 1
        else:
            run_level, run_len = lvl, 1 if lvl is not None else 0
        if run_level is not None:
            best[run_level] = max(best.get(run_level, 0), run_len)
        _level_runs(child, best)


def _auto_bento_level(root: MarkdownGroupNode) -> int | None:
    """The bento target level when the theme names none.

    The SHALLOWEST heading level that has a contiguous run of at least
    ``BENTO_MIN_CELLS`` sections under one parent — root included, since the
    container is simply whoever holds the run. A document of ``##`` sections
    with ``###`` inside targets 2 (the ``###`` runs are deeper), and one ``#``
    over three ``##`` targets 2 as well (level 1 has a run of one).
    """
    best: dict[int, int] = {}
    _level_runs(root, best)
    return next((lvl for lvl in sorted(best) if best[lvl] >= BENTO_MIN_CELLS), None)


def _estimate_cell_height(node: MarkdownGroupNode, width: float) -> float:
    """Crude height-for-width estimate of a cell, without fonts.

    Fallback used by the bento search when no ``measure`` callback was passed to
    ``generate()`` (unit tests, script callers). Per text leaf: wrapped lines from
    a category → single-line-px table at a nominal line height; images contribute
    ``width / _bento_est_image_ratio(width)`` (the renderer's width-conditioned
    default). Crude by design — the renderer owns the
    real geometry and the bento flags keep edges aligned regardless.
    """
    width = max(width, 1.0)
    total = 0.0
    count = 0

    def walk(n: MarkdownGroupNode) -> None:
        nonlocal total, count
        if n.children:
            for c in n.children:
                walk(c)
            return
        if not n.content:
            return
        if n.type == "image":
            h = width / _bento_est_image_ratio(width)
        else:
            px = _BENTO_EST_LINE_PX.get(_length_category(n) or "", 300.0)
            h = max(1.0, math.ceil(px / width)) * _BENTO_EST_LINE_H
        total += h
        count += 1

    walk(node)
    return total + max(0, count - 1) * _BENTO_EST_GAP


def _bento_col(parts: list[LayoutNode]) -> LayoutNode:
    """A vertical band of mosaic parts; ``bento`` marks it for height stretch."""
    col = LayoutNode(type="col", ratios=[1.0] * len(parts), children=list(parts))
    col.bento = True
    return col


def _fill_container_levels(node: LayoutNode, enclosing: str | None = None) -> None:
    """Give generator-made *transparent containers* a ``section_level``, bottom-up.

    Heading sections already carry their level directly, from the grouper's
    ``heading_group``/``heading_level`` flag (set on the LayoutNode in ``_decide_group``
    for groups, and ``_make_leaf`` for a bare-heading leaf). This pass only fills a
    group that does NOT already have a level and that holds **2+ children at the same
    level** — i.e. a grid row/col of same-level sibling sections the generator built.
    Such a container needs the level so the renderer's ``_section_style_for`` treats it
    as transparent, ``merge_rows`` works, and section-spacing adjacency sees it as a
    section block. A wrapper around a single section stays ``None`` (transparent).

    A wrapper filled here names its children's style, but the gaps between them
    belong to the section enclosing it (THEME_GUIDE §3, gridded or stacked), so
    when the two differ that one's fixed style rides along as a render hint.
    """
    inner = node.section_style_key if node.section_level is not None else enclosing
    for child in node.children:
        _fill_container_levels(child, inner)
    if node.type == "-" or node.section_level is not None:
        return
    level_counts: dict[int, int] = {}
    for c in node.children:
        if c.section_level is not None:
            level_counts[c.section_level] = level_counts.get(c.section_level, 0) + 1
    container_levels = [lvl for lvl, n in level_counts.items() if n >= 2]
    if container_levels:
        node.section_level = min(container_levels)
        keys = {
            c.section_style_key
            for c in node.children
            if c.section_level == node.section_level
        }
        if len(keys) == 1:
            node.section_style_key = next(iter(keys))
        if node.section_style_key != enclosing:
            rp = node.render_properties or {}
            node.render_properties = {**rp, "enclosing_style": enclosing}


def _is_group(node: MarkdownGroupNode) -> bool:
    return not node.content and bool(node.children)


def _is_marked_line(node: MarkdownGroupNode) -> bool:
    """A task item of one piece: its box is its marker, as a bullet is, so it is
    the one-piece item ``- text`` and stacks as that one does."""
    pieces = [c for c in node.children if not (c.drawing_element or {}).get("marker")]
    return len(pieces) == 1 and not pieces[0].children


# The list item kinds, whose runs of one-line items grid like any other group.
_LIST_ITEM_TYPES = (
    NodeType.LIST_ITEM,
    NodeType.ORDERED_ITEM,
    NodeType.TASK_OPEN,
    NodeType.TASK_DONE,
)


def _line_run(run: list[MarkdownGroupNode]) -> str | None:
    """How a repeated run of line groups is laid out: ``"flow"`` beside each
    other on one line, ``"stack"`` one line under another, or ``None`` for a run
    that is not lines and grids like any other group."""
    # Runs of line-split sub-groups. These only flow aside when the run
    # members are the pieces of ONE physical source line (e.g. emoji-
    # peeled pipe segments ⭐+Popular | 🚀+... — all share a
    # source_line_id). A run whose members are on DIFFERENT lines (a
    # list/section of same-shaped items, e.g. one amenity per line) must
    # STACK — each member renders full-width and still flows its own
    # emoji+text aside internally. Same-line check: all members share
    # one non-None source_line_id. LIST ITEMS on different lines are the
    # exception: an item of two or more leaves is a group like any other,
    # so the run falls through and grids.
    #
    # A real grouper line_split_group always carries a non-None
    # source_line_id, so members on one line share a single value and
    # members on different lines differ. (Hand-built fixtures that leave
    # it None collapse to {None} → treated as one line, preserving the
    # pre-source_line_id flow behavior.)
    # A run of spring list items (``- A ... B``, ``align_group``) stacks:
    # a spring asks for the full width. Mixed runs poll, tie → first.
    same_line = len({m.source_line_id for m in run}) == 1
    vote = 2 * sum(m.align_group for m in run) - len(run)
    springs = vote > 0 or (vote == 0 and run[0].align_group)
    line = springs or _is_marked_line(run[0])
    if (
        _is_group(run[0])
        and run[0].line_split_group
        and (same_line or line or run[0].type not in _LIST_ITEM_TYPES)
    ):
        return "flow" if same_line else "stack"
    return None


def shares_params(run: list[MarkdownGroupNode]) -> bool:
    """Whether a repeated run polls its pictures' params into one set, so one
    annotated member draws them all: the renderer's run poll, and what ``check``
    counts. Every run of groups does, list rows stacked as lines included; other
    lines and the pieces of one line keep their own."""
    kind = _line_run(run)
    if kind is None:
        return _is_group(run[0])
    return kind == "stack" and run[0].type in _LIST_ITEM_TYPES


def _is_leaf(node: MarkdownGroupNode) -> bool:
    return not node.children and bool(node.content)
