"""Spacing: how much air goes between two siblings, and why.

Owns the gap taxonomy. Every gap in a rendered document is one of three kinds,
and the widest applicable one wins:

  * **section** -- between two heading sections, resolved per level;
  * **group** -- between two grouped blocks inside a section;
  * **element** -- between two plain siblings.

``_sibling_gap`` is the single place that decision is made, for both axes, so a
column gap and a row gap can never disagree about what kind of boundary they are
looking at. The predicates here (`_is_group_node`, `_opens_section`,
`_is_key_block`, `_is_rule_leaf`, ...) exist to classify that boundary, and are
shared with the renderer, which asks the same questions while painting.

Owns no drawing and no measurement: given two nodes and a theme, it returns a
number.
"""

from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.grouper_types import ELEMENT_LEAF_TYPES
from md2ui.pipeline.render_list_surfaces import is_row
from md2ui.pipeline.render_backgrounds import (
    _card_style_for,
    _paints_fill,
    _structural_style_for,
)
from md2ui.pipeline.theme import Theme, resolve_section_style


def _resolve_section_spacing(
    owner_level: int,
    axis: str,
    theme: Theme,
    fixed_style_key: str | None = None,
) -> float:
    """Section gap owned by the nearest enclosing section ``owner_level`` (0=root).

    By axis ("row" | "col"): the owner's per-axis spacing. A level that declares
    one wins — including ``Spacing: 0``, which means "no gap". A level that
    declares none falls back to the **group** spacing (which itself chains to the
    element spacing, then 0), so an unstyled level picks up the document's group
    rhythm instead of collapsing to 0.

    The root (0) reads its value from ``## Root`` rather than from a heading
    level, but walks the SAME chain: one rule at every level, and one meaning for
    ``Spacing`` — *the gap between my own child sections*. So ``Root → Spacing``
    owns the gap between top-level bands, and ``Heading 1 → Spacing`` owns the
    rhythm inside each of them.
    """
    if owner_level == 0:
        v = theme.root.row_spacing if axis == "row" else theme.root.col_spacing
        return v if v is not None else _resolve_group_spacing(axis, theme)
    st = resolve_section_style(theme, owner_level, fixed_style_key)
    if st is not None:
        v = st.row_spacing if axis == "row" else st.col_spacing
        if v is not None:
            return v
    return _resolve_group_spacing(axis, theme)


def _resolve_element_spacing(axis: str, theme: Theme) -> float:
    """Element gap (inside an end-group) by axis, from the global element style."""
    v = theme.elements.row_spacing if axis == "row" else theme.elements.col_spacing
    return v if v is not None else 0.0


def _resolve_group_spacing(axis: str, theme: Theme) -> float:
    """Group gap by axis, from the global element style.

    Used for pairs involving a non-section group node (group↔leaf or group↔group).
    Falls back to the element (row/col) spacing when unset, so it's a no-op until a
    ``Group spacing`` value is given.
    """
    v = (
        theme.elements.group_row_spacing
        if axis == "row"
        else theme.elements.group_col_spacing
    )
    return v if v is not None else _resolve_element_spacing(axis, theme)


def _resolve_image_spacing(axis: str, theme: Theme) -> float:
    """Gap between two adjacent image leaves (image↔image), by axis.

    Defaults to 0 (images abut) when unset — a deliberate change from the element
    spacing images would otherwise fall through to.
    """
    v = (
        theme.elements.image_row_spacing
        if axis == "row"
        else theme.elements.image_col_spacing
    )
    return v if v is not None else 0.0


def _is_group_node(n: LayoutNode) -> bool:
    """A non-leaf container that is not a heading section (a plain row/col group)."""
    return n.type in ("row", "col") and n.section_level is None


def _is_task_control(n: LayoutNode, node_index: dict) -> bool:
    return (
        n.type == "-"
        and node_index.get(n.content_id, {}).get("type") == "drawing_element"
    )


def _is_pure_element_block(n: LayoutNode, node_index: dict) -> bool:
    """A plain group container whose entire leaf content is pills — links /
    inline_code (≥1 leaf).

    Such a block (a pill flow row, a col of flow rows, a grouper link group)
    reads as a run of buttons/chips, not a structural group — its neighbors
    space it with *element* spacing, matching how a lone pill leaf is spaced.
    """
    if not _is_group_node(n):
        return False
    found = False
    stack = list(n.children)
    while stack:
        x = stack.pop()
        if x.type == "-":
            if node_index.get(x.content_id, {}).get("type") not in ELEMENT_LEAF_TYPES:
                return False
            found = True
        else:
            stack.extend(x.children)
    return found


def _opens_section(n: LayoutNode) -> bool:
    """A section-owner group: a row/col that opens a heading section.

    Distinct from a heading *leaf*, which also carries a ``section_level`` (the text
    seed) but is not a section boundary — so keying on the group avoids treating
    ``image-leaf ↔ heading-leaf`` inside a glued card as a section change.
    """
    return n.type in ("row", "col") and n.section_level is not None


def _is_key_block(n: LayoutNode, node_index: dict) -> bool:
    """A KV *key* side: a ``key``-typed leaf, or a plain container whose
    entire leaf content is ``key``-typed (e.g. a key with a peeled emoji).

    A key's only sibling inside its key-value wrapper is its value, so
    key-adjacency safely marks the key↔value boundary — spaced with the
    element gap whatever shape the value takes.
    """
    if n.type == "-":
        return node_index.get(n.content_id, {}).get("type") == "key"
    if not _is_group_node(n):
        return False
    found = False
    stack = list(n.children)
    while stack:
        x = stack.pop()
        if x.type == "-":
            if node_index.get(x.content_id, {}).get("type") != "key":
                return False
            found = True
        else:
            stack.extend(x.children)
    return found


def _sibling_gap(
    prev_child: LayoutNode,
    child: LayoutNode,
    theme: Theme,
    axis: str,
    owner_level: int,
    node_index: dict,
    container: LayoutNode | None = None,
) -> tuple[float, bool]:
    """Gap between two adjacent siblings on ``axis`` ("row" | "col").

    ``container`` is the node these two are children of; its baked
    ``gap_in_line`` is what scopes the pure-pill exception below to one line
    block's own content. Omitting it (or passing an unbaked node) simply means
    that exception does not apply.

    Exactly one gap kind applies, in priority order (each replaces, not adds to, the
    others):

    1. section gap — a *section change* is detected by adjacency: at least one sibling
       is a section-owner group (``_opens_section``), or both carry a ``section_level``.
       Covers content↔section and section↔section boundaries (e.g. the content before
       the first heading, or a heading's body right before its first subsection). Uses
       the enclosing section's per-axis spacing (``owner_level``).
    2. group gap — at least one sibling is a non-section group node (group↔leaf or
       group↔group). Exceptions, all element gap: two siblings one flow batch
       emitted (a shared ``flow_run`` id — the rows a run wrapped onto stay one
       unit, cards excluded); and *inside one line block*
       (``container.gap_in_line`` — the container is a line block, or a card
       nested in one) a *pure pill block* (all leaf content is links /
       inline_code) next to a leaf or another pure-pill block. Outside those,
       two pill blocks are separate elements and keep the group gap. Likewise a KV *key*
       side (key leaf or all-key container) keeps the element gap to its
       value, whatever the value's shape; a drawn row SEPARATOR keeps the
       element gap on both sides, whatever it separates; and a ``line_split`` block (one
       source line's flowed pieces) element-spaces ANY adjacency, one-sided —
       unless it is also a glued card, which spaces like a card (glued wins), a
       heading's line (``heading_line``), or a line whose pieces are all BLOCKS
       (``block_line`` — colon columns, KV pairs, or a ``:::`` row of block
       cells), which is a group of groups toward its neighbors and keeps the
       group gap.
    3. both siblings are leaves:
       - image↔image → image spacing (replaces; default 0),
       - otherwise → element spacing.
    4. otherwise (section↔leaf, etc.) → element spacing.

    Returns ``(gap, is_section)``.
    """
    # A gutter marker's ``Space`` IS this gap — "the gap between the marker and
    # the content" (THEME.md). The marker cell is the bare
    # glyph/shape; the space between it and the content it labels is inserted
    # here, so the generator's aside split and the renderer agree on both.
    # A lone-``_`` CONTENT BREAK is structural, not visual: it cuts the run of
    # siblings but must not occupy space. So it contributes no gap of its own,
    # and the sibling AFTER it is spaced against the last real sibling BEFORE
    # it — the pair keeps exactly the one gap it would have had if the break
    # were never written. Without this the zero-height node takes a gap on each
    # side and the boundary is spaced twice.
    if _is_break_leaf(child, node_index):
        return 0.0, False
    if _is_break_leaf(prev_child, node_index):
        real = _prev_real_sibling(container, prev_child, node_index)
        if real is None:
            # The break opens the container (or the caller passed no container):
            # nothing before it to space against.
            return 0.0, False
        prev_child = real
    # The rows of one merged list card meet edge to edge: their padding is the
    # room between them, and the rule is drawn on the edge they share.
    if axis == "col" and is_row(prev_child) and is_row(child):
        return 0.0, False
    if axis == "row" and (
        _is_task_control(prev_child, node_index) or _is_task_control(child, node_index)
    ):
        return theme.datapoints.task_controls.space, False
    for n in (prev_child, child):
        if n.type == "-":
            lm = (n.render_properties or {}).get("list_marker")
            if lm is not None:
                return float(lm.get("space", 0.0)), False
    # The two leaves inside a date chip (key over day) use the chip's own
    # spacing (### Dates → Spacing, default 0), not the generic element gap.
    if (prev_child.render_properties or {}).get("date_role") and (
        child.render_properties or {}
    ).get("date_role"):
        return theme.datapoints.date_chip.spacing, False
    # The value/unit leaves inside a ring use the ring's own spacing.
    if (prev_child.render_properties or {}).get("ring_role") and (
        child.render_properties or {}
    ).get("ring_role"):
        return theme.datapoints.ring.spacing, False
    # Table gaps (## Tables): between two cells of one table row (row axis) the
    # table's row spacing; between two table rows (col axis) the table's col
    # spacing — forced to 0 in merged mode (one background behind the whole
    # table). Unset spacings fall back to the element gap.
    if (
        axis == "row"
        and getattr(prev_child, "in_table", None) is not None
        and getattr(child, "in_table", None) is not None
    ):
        v = theme.tables.table.row_spacing
        return (v if v is not None else _resolve_element_spacing(axis, theme)), False
    if (
        axis == "col"
        and getattr(prev_child, "table_row", None) is not None
        and getattr(child, "table_row", None) is not None
    ):
        if theme.tables.table.merge_rows:
            return 0.0, False
        v = theme.tables.table.col_spacing
        return (v if v is not None else _resolve_element_spacing(axis, theme)), False
    if (
        _opens_section(prev_child)
        or _opens_section(child)
        or (prev_child.section_level is not None and child.section_level is not None)
    ):
        # The ENCLOSING section owns the gap, at every level including the root:
        # top-level bands are spaced by ``Root → Spacing``, not by the heading
        # level they happen to enter. Root is tri-state, so an unset root falls
        # through to the group gap.
        #
        # The container names the style when it is a section itself; when it is a
        # transparent same-level wrapper it does not, so the fixed style key is
        # read off whichever sibling sits at the owner's level. A wrapper of
        # deeper sections (a grid row) names THEIR style, so the owner's is the
        # one it encloses: gridded children space like stacked ones.
        style_key = None
        if container is not None:
            style_key = container.section_style_key
            if container.section_level not in (None, owner_level):
                rp = container.render_properties or {}
                style_key = rp.get("enclosing_style", style_key)
        if style_key is None:
            style_key = next(
                (
                    n.section_style_key
                    for n in (prev_child, child)
                    if n.section_level == owner_level
                    and n.section_style_key is not None
                ),
                None,
            )
        return _resolve_section_spacing(owner_level, axis, theme, style_key), True
    # A rule is a DIVIDER: it takes the group gap whatever it separates, so it
    # never inherits the tight element gap from a leaf neighbour (and a rule
    # between a group and a leaf no longer takes one gap on each side). The
    # section branch above already returned, so section boundaries still win.
    if _is_rule_leaf(prev_child, node_index) or _is_rule_leaf(child, node_index):
        return _resolve_group_spacing(axis, theme), False
    # A separator separates whatever is on either side of it, so its own spacing
    # must not depend on what that is: one between two colon columns took the
    # group gap, and one between a column and a leaf took the group gap on ONE
    # side and the element gap on the other. It is not a group-triggering
    # neighbour — falling through lands on the leaf rules below, which give the
    # element gap.
    # Pictures beside pictures are one gallery, however they were written: a
    # line of them, a stack of lines, a `:::` row of picture cells. So two
    # adjacent picture-only siblings take the image gap whatever their shape,
    # and two mosaics on a page meet at the same gap their pictures do.
    if _is_pure_image_block(prev_child, node_index, theme) and _is_pure_image_block(
        child, node_index, theme
    ):
        return _resolve_image_spacing(axis, theme), False
    if not (_is_separator_cell(prev_child) or _is_separator_cell(child)) and (
        _is_group_node(prev_child) or _is_group_node(child)
    ):
        # Line-split blocks (one source line's pieces) element-space ANY
        # adjacency — one-sided: the line stays close to whatever precedes or
        # follows it, and to its own wrapped rows. Exception: a line block
        # that is ALSO a glued card spaces like every other card (glued wins);
        # its internal rows are not cards, so the in-card flow stays tight.
        def _line_side(n: LayoutNode) -> bool:
            # A heading's line flows internally but spaces as a heading toward
            # its neighbors, so `# 🔖 Emojis` keeps the same gap to the body as
            # a plain `# Emojis` (see LayoutNode.heading_line).
            # …and a line whose pieces are all BLOCKS (colon columns, KV pairs)
            # is a group of groups toward its neighbors, not a line of words, so
            # it falls through to the group gap below (see LayoutNode.block_line).
            return (
                getattr(n, "line_split", False)
                and not n.is_card
                and not getattr(n, "heading_line", False)
                and not getattr(n, "block_line", False)
            )

        if _line_side(prev_child) or _line_side(child):
            return _resolve_element_spacing(axis, theme), False
        # A KV key and its value stay element-spaced whatever the value's
        # shape (leaf values already are; group values would otherwise get
        # the group gap and detach from their key).
        if _is_key_block(prev_child, node_index) or _is_key_block(child, node_index):
            return _resolve_element_spacing(axis, theme), False
        # The rows ONE flowed run wrapped onto are still one unit, so they keep
        # the element gap between them. A pill run has no wrapper node (its rows
        # are spliced into the parent), so the relation travels on the siblings
        # as a shared ``flow_run`` id. Cards are excluded on both sides —
        # glued wins, like ``_line_side``.
        run_id = getattr(prev_child, "flow_run", 0)
        if (
            run_id
            and run_id == getattr(child, "flow_run", 0)
            and not prev_child.is_card
            and not child.is_card
        ):
            return _resolve_element_spacing(axis, theme), False

        # Pure-pill blocks (links / inline_code) are spaced like the pill leaves
        # they contain — but only INSIDE one line block (``gap_in_line``), which
        # is what the exception was for: a line's pills stay evenly spaced after
        # the flow wraps them onto more rows. Between separate elements (two pill
        # cards, a pill card and a heading) the group gap keeps them apart.
        def _pilly(n: LayoutNode) -> bool:
            return n.type == "-" or _is_pure_element_block(n, node_index)

        if (
            container is not None
            and getattr(container, "gap_in_line", False)
            and _pilly(prev_child)
            and _pilly(child)
        ):
            return _resolve_element_spacing(axis, theme), False
        return _resolve_group_spacing(axis, theme), False
    return _resolve_element_spacing(axis, theme), False


def _is_pure_image_block(n: LayoutNode, node_index: dict, theme: Theme) -> bool:
    """An image leaf, or a plain group container whose entire leaf content is
    images (≥1). A group that paints a surface of its own -- a card fill, a list
    or quote background -- is not: it is a group like any other, wherever it
    sits inside. A card that paints nothing draws as its pictures, so it counts.
    """
    if n.type == "-":
        return _is_image_leaf(n, node_index)
    if not _is_group_node(n):
        return False
    found = False
    stack = [n]
    while stack:
        x = stack.pop()
        if x.type == "-":
            if not _is_image_leaf(x, node_index):
                return False
            found = True
        elif _paints_surface(x, theme):
            return False
        else:
            stack.extend(x.children)
    return found


def _paints_surface(n: LayoutNode, theme: Theme) -> bool:
    """Whether *n* paints a card or a list/quote background of its own."""
    card = _card_style_for(n, theme)
    if card is not None and _paints_fill(card, n.card_bg_url):
        return True
    structural = _structural_style_for(n, theme)
    return structural is not None and _paints_fill(structural[1], None)


def _is_image_leaf(child: LayoutNode, node_index: dict) -> bool:
    """True when ``child`` is a leaf referencing an image content node."""
    return (
        child.type == "-"
        and node_index.get(child.content_id, {}).get("type") == "image"
    )


def _is_rule_leaf(child: LayoutNode, node_index: dict) -> bool:
    """True when ``child`` is a leaf referencing a painted ``___`` rule.

    Unlike the synthetic separator cell, a rule HAS a markdown node behind it, so
    this needs the ``node_index`` lookup — same shape as ``_is_image_leaf``.
    """
    return (
        child.type == "-"
        and node_index.get(child.content_id, {}).get("type") == "horizontal_rule"
    )


def _is_separator_cell(n: LayoutNode) -> bool:
    """True for a DRAWN row separator (## Separators): the ` - ` / ` • ` / ` | `
    cell the generator puts back between a line's pieces.

    No ``node_index`` lookup — the cell is synthetic, has no markdown node behind
    it, and carries its own render props, the same way a gutter marker does.
    """
    return (n.render_properties or {}).get("separator") is not None


def _is_break_leaf(child: LayoutNode, node_index: dict) -> bool:
    """True when ``child`` is a leaf referencing a lone-``_`` CONTENT BREAK.

    Not the painted ``horizontal_rule``: a visible rule wants breathing room on
    both sides, while the break is structural only and must cost nothing. Not
    a ``+++`` spacer either: it is spaced like any element, on each side
    (ADR-203).
    """
    return (
        child.type == "-"
        and node_index.get(child.content_id, {}).get("type") == "content_break"
    )


def _prev_real_sibling(
    container: LayoutNode | None, child: LayoutNode, node_index: dict
) -> LayoutNode | None:
    """The sibling before *child* that is not a content break, or ``None``.

    Walks back past a run of them, so consecutive ``_`` lines collapse to one
    boundary instead of re-introducing the doubled gap one break at a time.
    """
    if container is None:
        return None
    kids = container.children
    try:
        i = next(j for j, c in enumerate(kids) if c is child)
    except StopIteration:
        return None
    for j in range(i - 1, -1, -1):
        if not _is_break_leaf(kids[j], node_index):
            return kids[j]
    return None
