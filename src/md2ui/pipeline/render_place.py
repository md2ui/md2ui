"""Placement: turning sized nodes into positioned boxes.

Sizing (``render_measure``) answers how big a node wants to be; this module
decides where each box actually goes -- ``place_boxes`` walks the layout tree and
emits a ``LayoutBox`` per node, and the ``bake_*`` passes fold in the decisions
that can only be made once positions are known (image bleed, merged row cards,
the render cascade).

Depends on sizing and never the reverse. That order is not a preference: placement
calls the measurers, so extracting it before sizing would have made this module
import the renderer back and cycle.

Nothing here takes a canvas, and nothing here reads the renderer's mutable display
globals -- both verified before the split.
"""

from md2ui.pipeline.layout_script_parser import (
    LayoutBox,
    LayoutNode,
)
from md2ui.pipeline.render_backgrounds import (
    SectionBox,
    _emit_wrap_boxes,
    _layers_pad,
    _layers_section_level,
    _paint_style_for,
    _push_bg,
    _root_bg_stack,
    _row_backgrounds_match,
    _wrap_layers,
)
from md2ui.pipeline.render_list_surfaces import divider_rect
from md2ui.pipeline.render_measure import (
    _cell_heights,
    _child_owner_level,
    _is_transparent_container,
    _layout_row,
    _padded_children,
    _stretch_bento_placements,
    _table_plan,
    _valign_offset,
    natural_height,
)
from md2ui.pipeline.render_colors import _replace_color, _table_background_color
from md2ui.pipeline.render_metrics import (
    _image_content_width,
)
from md2ui.pipeline.render_spacing import (
    _sibling_gap,
)
from md2ui.pipeline.render_style import (
    FontSet,
)
from md2ui.pipeline.theme import (
    PaddingBox,
    Theme,
    resolve_section_style,
)


def _place_table_boxes(
    node: LayoutNode,
    x: float,
    y: float,
    width: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme | None,
    inherited: dict | None,
    debug_gaps: list | None,
    debug_section_gaps: list | None,
    in_section_levels: frozenset[int],
    section_boxes: list | None,
    owner_level: int,
    bg_stack: "tuple[int | str, ...]" = (),
    action_marks: list | None = None,
) -> list:
    """Emit a table's SectionBoxes + content LayoutBoxes from its TablePlan.

    A cell is placed like any other node, so a link card inside one is noted in
    ``action_marks`` and clicks where it is drawn.
    """
    _t = theme or Theme()
    tt = _t.tables

    # Header and body cells sit on their own themed fill, so table text resolves
    # its color against that rather than against whatever encloses the table.
    # The fill is a paint first, replaced against what the table sits on, as a
    # card's is (the row boxes below carry the same stack to paint it); a
    # stacked card's keys sit on the cell fill too, so they read it the same way.
    def _fill_bg(style, index: int):
        color = _table_background_color(style, index, _t)
        if color is not None:
            color = _replace_color(color, bg_stack, _t, "fill")
        return _push_bg(bg_stack, color)

    def _cell_bg_for(content_id: str | None, rp: dict | None = None):
        role = (node_index.get(content_id) or {}).get("table_role")
        style = tt.header if role == "header" else tt.cells
        return _fill_bg(style, int((rp or {}).get("table_bg_index", 0)))

    plan = _table_plan(node, width, node_index, fonts, _t)

    shell_clip = None
    if section_boxes is not None and tt.is_active():
        if plan.shell is not None:
            sx, sy, sw, sh = plan.shell
            section_boxes.append(
                SectionBox(x + sx, y + sy, sw, sh, 0, tt.table.padding, "table")
            )
            if tt.table.corner_radius > 0:
                shell_clip = (
                    x + sx,
                    y + sy,
                    sw,
                    sh,
                    tt.table.corner_radius,
                )
        for kind, bx, by, bw, bh in plan.row_boxes:
            st = tt.header if kind == "table_header" else tt.cells
            if st.is_active():
                section_boxes.append(
                    SectionBox(
                        x + bx,
                        y + by,
                        bw,
                        bh,
                        0,
                        st.padding,
                        kind,
                        clip=shell_clip,
                        bg_stack=bg_stack,
                    )
                )

    child_inherited = _cascade_render(node, inherited)
    results: list = []
    for cell, cx, cy, cw, ch, rp_extra in plan.cells:
        if cell.type == "-":
            if action_marks is not None:
                _note_actions(action_marks, cell, x + cx, y + cy, cw, ch)
            eff = dict(cell.render_properties or {})
            if rp_extra:
                eff.update(rp_extra)
            inh = child_inherited or {}
            for key in ("content_weight", "content_align"):
                if not eff.get(key) and inh.get(key):
                    eff[key] = inh[key]
            results.append(
                LayoutBox(
                    x=x + cx,
                    y=y + cy,
                    width=cw,
                    height=ch,
                    content_id=cell.content_id,
                    render_properties=eff or None,
                    bg_stack=_cell_bg_for(cell.content_id, rp_extra),
                )
            )
        else:
            results.extend(
                place_boxes(
                    cell,
                    x + cx,
                    y + cy,
                    cw,
                    ch,
                    node_index,
                    fonts,
                    theme,
                    child_inherited,
                    debug_gaps,
                    debug_section_gaps,
                    in_section_levels,
                    section_boxes,
                    owner_level,
                    _cell_bg_for(cell.content_id, rp_extra),
                    action_marks=action_marks,
                )
            )
    for text, kx, ky, kw, kh, bg_index in plan.keys:
        results.append(
            LayoutBox(
                x=x + kx,
                y=y + ky,
                width=kw,
                height=kh,
                render_properties={"table_key": {"text": text}},
                bg_stack=_fill_bg(tt.cells, bg_index),
            )
        )
    return results


def _cascade_render(node: LayoutNode, inherited: dict | None) -> dict:
    """Resolve the render hints a node passes down to its descendants.

    ``content_weight``, ``content_align`` and ``line_align`` cascade: a node's
    own value (the nearest ancestor) overrides a farther ancestor's; otherwise
    the inherited value flows through. Other (image-only) hints never cascade.
    """
    own = node.render_properties or {}
    inh = inherited or {}
    return {
        "content_weight": own.get("content_weight") or inh.get("content_weight"),
        "content_align": own.get("content_align") or inh.get("content_align"),
        "line_align": own.get("line_align") or inh.get("line_align"),
    }


_BLEED_EPS = 0.5  # px slack when testing whether a box touches an inner edge


def bake_image_bleed(
    boxes: list,
    section_boxes: list,
    node_index: dict,
    theme: Theme,
) -> None:
    """Let image leaves reach their enclosing level's edge, and round them.

    Runs after placement, over the boxes and the ``SectionBox`` list that
    ``place_boxes`` already produces. Nothing here re-measures: a ``SectionBox``
    records its layer's OUTER rect plus the ``padding`` that inset the content,
    which is exactly the space an image would bleed into, so this is paint-only
    and cannot move the layout.

    Two independent per-level opt-ins, both off by default:

    * ``image_corner_radius`` rounds an image leaf inside that level;
    * ``image_bleed`` expands the image over the level's own padding on every
      inner edge it ALREADY TOUCHES — a leading image touches top/left/right and
      so bleeds TLR, an aside touches top/left/bottom (TLB, or TRB on the right),
      a trailing image LRB. Touching is the whole rule, and it is self-policing:
      a sibling on some side is precisely what stops the image touching that
      edge, so an image can never bleed over its neighbours. Each edge moves out
      by ITS OWN padding, into space the level had already reserved and left
      empty, which is why growing the box cannot overlap anything. A level
      stretched past its content (a bento band) leaves empty space below its
      last line too, so an image that ends the content reaches down through it.

    While bleeding, the level's own ``corner_radius`` clips the image on just the
    corners the two rects now share, and ``image_corner_radius`` is dropped — the
    parent's shape wins, so a top image sits flush inside a rounded card instead
    of showing its own rounded bottom corners mid-card.
    """
    if not section_boxes:
        return
    images = [
        b
        for b in boxes
        if b.content_id and node_index.get(b.content_id, {}).get("type") == "image"
    ]
    if not images:
        return
    # Where everything sat before any image bled, so one image's bleed never
    # decides whether the next one ends its card's content.
    placed = [(b, b.x, b.y, b.width, b.height) for b in boxes]

    for box in images:
        rp = box.render_properties or {}
        # The image outranks its level, both ways: ``bleed: no`` excuses one
        # image from a level that bleeds, and ``bleed: yes`` works in a level
        # that never mentioned images. ``None`` means "not stated" — only then
        # does the level decide.
        own_bleed = rp.get("bleed")
        own_radius = rp.get("corner_radius")

        found = _bleed_layer_for(box, section_boxes, theme, own_bleed)
        layer, style = found if found is not None else (None, None)
        bleed_on = (
            own_bleed if own_bleed is not None else bool(style and style.image_bleed)
        )

        radii = None
        if bleed_on and layer is not None and style is not None:
            radii = _apply_bleed(box, layer, style, placed)
        if radii is None:
            # Not bleeding: the image's own radius, else the level's. A per-image
            # radius needs no layer at all — it neither eats padding nor changes
            # geometry — so it works where the theme says nothing about images.
            r = (
                own_radius
                if own_radius is not None
                else (style.image_corner_radius if style else 0.0)
            )
            if r and r > 0:
                radii = (r, r, r, r)
        if radii and any(radii):
            box.render_properties = {
                **(box.render_properties or {}),
                "corner_radii": radii,
            }


def _bleed_layer_for(box, section_boxes, theme, own_bleed=None):
    """The innermost ENCLOSING layer this image acts on, with its style.

    Candidates are always layers that *contain* the box, scanned innermost
    first, so a bleed can only ever eat the padding of a box the image is
    actually sitting in — never a sibling's, and never a level the image is not
    inside.

    Which enclosing layer qualifies depends on who asked:

    * the level asked (``image_bleed`` / ``image_corner_radius``) — that level,
      innermost first. Innermost-that-opted-in rather than plain innermost,
      because the tightest layer around an image is often a glued card with no
      padding at all, and letting it shadow the padded section that actually
      asked would silently do nothing;
    * the IMAGE asked (``?md2ui.bleed=yes``) — the innermost enclosing layer with
      any padding, so a one-off image can bleed its card with the theme silent.
    """
    candidates = []
    for s in section_boxes:
        if (
            s.x - _BLEED_EPS <= box.x
            and s.y - _BLEED_EPS <= box.y
            and box.x + box.width <= s.x + s.width + _BLEED_EPS
            and box.y + box.height <= s.y + s.height + _BLEED_EPS
        ):
            candidates.append(s)
    candidates.sort(key=lambda s: s.width * s.height)  # innermost first
    for s in candidates:
        style, _ = _paint_style_for(s.kind, s.level, theme, s.fixed_style_key)
        if style is None:
            continue
        if style.image_bleed or style.image_corner_radius > 0:
            return s, style
        if own_bleed and (style.padding.x or style.padding.y):
            return s, style
    return None


def _apply_bleed(
    box, layer, style, placed
) -> "tuple[float, float, float, float] | None":
    """Expand *box* over *layer*'s padding on every inner edge it touches.

    The bottom edge counts as touched also when a full-width or aside image
    ends the layer's content: a card stretched to its band (bento) leaves empty
    space below its last line, and no sibling stands in it, so the image runs
    down through it. *placed* is every box's rect before any image bled.

    Returns the per-corner radii (TL, TR, BR, BL) the expanded box should clip
    to — the layer's own ``corner_radius`` on corners the two rects now share,
    0 elsewhere — or None when the image touched nothing and did not move.
    """
    # An image that does not FILL its box cannot meaningfully bleed: a
    # ``max_width`` cap (an icon) paints a small rect inside a big box, so
    # expanding the box would only shove the icon into the card's corner,
    # outside the rounded edge, rather than making anything reach the edge.
    # Bleeding is for images meant to fill, so let the cap opt itself out.
    rp = box.render_properties or {}
    if _image_content_width(rp, box.width) < box.width - _BLEED_EPS:
        return None

    pad = layer.padding
    inner_l = layer.x + pad.left
    inner_t = layer.y + pad.top
    inner_r = layer.x + layer.width - pad.right
    inner_b = layer.y + layer.height - pad.bottom

    left = abs(box.x - inner_l) <= _BLEED_EPS
    top = abs(box.y - inner_t) <= _BLEED_EPS
    right = abs((box.x + box.width) - inner_r) <= _BLEED_EPS
    box_b = box.y + box.height
    bottom = abs(box_b - inner_b) <= _BLEED_EPS
    reach = pad.bottom
    edge_image = (left and right) or (top and (left or right))
    if (
        not bottom
        and edge_image
        and box_b < inner_b
        and _ends_layer_content(box, layer, placed)
    ):
        bottom, reach = True, inner_b - box_b + pad.bottom
    if not (left or top or right or bottom):
        return None

    if left:
        box.x -= pad.left
        box.width += pad.left
    if right:
        box.width += pad.right
    if top:
        box.y -= pad.top
        box.height += pad.top
    if bottom:
        box.height += reach

    r = style.corner_radius
    if r <= 0:
        return None
    # A corner is shared only when the image reaches BOTH of its edges.
    return (
        r if (top and left) else 0.0,
        r if (top and right) else 0.0,
        r if (bottom and right) else 0.0,
        r if (bottom and left) else 0.0,
    )


def _ends_layer_content(box, layer, placed) -> bool:
    """Whether no other box inside *layer* reached lower than *box*."""
    box_b = box.y + box.height
    for other, x, y, w, h in placed:
        if other is box:
            continue
        if (
            layer.x - _BLEED_EPS <= x
            and x + w <= layer.x + layer.width + _BLEED_EPS
            and layer.y - _BLEED_EPS <= y
            and y + h <= layer.y + layer.height + _BLEED_EPS
            and y + h > box_b + _BLEED_EPS
        ):
            return False
    return True


def bake_merged_row_cards(node: LayoutNode, theme: Theme) -> None:
    """Hand a merging row its children's shared photo, and stop them repeating it.

    A merged row already suppresses each child's *section* wrap — once the level
    is in ``in_levels`` its children get ``(None, None)`` from
    ``_section_style_for``. Nothing does the same for the **card** wrap, so a row
    of identical image cards painted the merged background *and* three full-extent
    photos on top of it. Nor did the shared photo ever reach the row, which drew
    only its theme colours.

    Moving the photo up and clearing the children resolves both, and resolving it
    here — the same reasoning ``bake_render_cascade`` documents — keeps
    ``place_boxes``/``natural_height`` from having to thread "an ancestor already
    painted my card" through every recursion.

    Only a shared *photo* triggers this. A merged row of non-photo cards is left
    alone: that shape renders correctly and there is no case asking to
    change it.

    Time: O(K), Space: O(depth).
    """
    level = node.section_level
    if node.type == "row" and level is not None:
        style = resolve_section_style(theme, level, node.section_style_key)
        same = [c for c in node.children if c.section_level == level]
        if (
            len(same) >= 2
            and style is not None
            and style.is_active()
            and style.merge_rows
            and _row_backgrounds_match(node, level)
            and same[0].card_bg_url
        ):
            node.card_bg_url = same[0].card_bg_url
            for child in same:
                child.card_bg_url = None
                child.is_card = False
                child.card_kind = None
    for child in node.children:
        bake_merged_row_cards(child, theme)


def _level_align(
    node: LayoutNode, theme: "Theme | None", owner_level: int
) -> str | None:
    """The THEME's ``Align`` for the level or card *node* opens, if any.

    A node may open a structural section and also be a glued card. Its explicit
    section alignment owns that content, matching the section background; card
    style is the fallback when the section leaves ``Align`` unset.
    """
    if theme is None:
        return None
    if node.section_level is not None and not _is_transparent_container(node, theme):
        st = resolve_section_style(theme, node.section_level, node.section_style_key)
        if st is not None and st.align is not None:
            return st.align
    if getattr(node, "is_card", False):
        kind = getattr(node, "card_kind", None)
        if kind == "image_card":
            st = theme.image_cards if theme.image_cards.is_active() else theme.elements
        elif kind in ("date_chip", "ring"):
            return None  # drawn chips, not a themed content level
        else:
            st = theme.elements
        return getattr(st, "align", None)
    return None


def _level_line_align(
    node: LayoutNode, theme: "Theme | None", owner_level: int
) -> str | None:
    """The THEME's ``Line align`` for the level or card *node* opens, if any.

    The vertical twin of ``_level_align`` — same section-before-card ownership
    and same "opens nothing = inherit" contract — so one document can never
    resolve its two alignment axes against different levels.
    """
    if theme is None:
        return None
    if node.section_level is not None and not _is_transparent_container(node, theme):
        st = resolve_section_style(theme, node.section_level, node.section_style_key)
        if st is not None and st.line_align is not None:
            return st.line_align
    if getattr(node, "is_card", False):
        kind = getattr(node, "card_kind", None)
        if kind == "image_card":
            st = theme.image_cards if theme.image_cards.is_active() else theme.elements
        elif kind in ("date_chip", "ring"):
            return None  # drawn chips, not a themed content level
        else:
            st = theme.elements
        return getattr(st, "line_align", None)
    return None


def bake_render_cascade(
    node: LayoutNode,
    inherited: dict | None = None,
    in_line: bool = False,
    theme: "Theme | None" = None,
    owner_level: int = 0,
) -> None:
    """Push cascading hints (content_weight/content_align) down onto leaves, and
    mark which containers hold one line block's content.

    A group/root acts as alignment/weight context for its descendants: each
    leaf inherits the nearest ancestor's value unless it sets its own. Baking
    this onto leaf ``render_properties`` once (right after layout generation)
    means both height measurement (``_leaf_height``) and drawing see a leaf's
    *effective* hints, so enlarged/shrunk text reserves the right box height.

    The same walk seeds a LEVEL's themed ``Align`` (``theme.sections[n].align``,
    ``theme.elements``/``image_cards`` for a card) onto the node that opens it —
    but only into an EMPTY slot, so anything authored on that node wins. Seeding
    the existing channel rather than resolving per-level at each draw site is
    what makes one key reach rows, glyphs, images, pills and chips alike, and it
    is why a deeper level overrides a shallower one for free: ``_cascade_render``
    is "own or inherited", so the nearest value wins. A markdown ``...`` spring
    keeps its regions' alignment for the same reason — its region carries its own
    ``content_align`` (written last by ``_attach_render``), which this never
    overwrites and which beats any ancestor's.

    ``Line align`` — the VERTICAL twin, read by ``_row_valign_offsets`` — rides
    the same channel, except that its consumer is a same-line ROW rather than a
    leaf, so the effective value is stamped onto every node on the way down
    instead of only onto leaves.

    The same walk sets ``gap_in_line`` on every container: True when the node is
    a line block, or a card nested inside one. ``_sibling_gap`` reads it to keep
    the pure-pill element gap *inside* one line's content, so two pill blocks
    that are separate elements stay a group gap apart. Resolving it here means
    the gap rule never has to thread an ancestor chain through the layout,
    measurement and placement recursions.
    """
    lvl_align = _level_align(node, theme, owner_level)
    if lvl_align and not (node.render_properties or {}).get("content_align"):
        node.render_properties = {
            **(node.render_properties or {}),
            "content_align": lvl_align,
        }
    lvl_valign = _level_line_align(node, theme, owner_level)
    if lvl_valign and not (node.render_properties or {}).get("line_align"):
        node.render_properties = {
            **(node.render_properties or {}),
            "line_align": lvl_valign,
        }
    cascade = _cascade_render(node, inherited)
    # ``line_align`` is read off the ROW itself, which normally sits several
    # levels below the node that opens the section, so — unlike the two leaf
    # hints — stamp the EFFECTIVE value onto every node as we descend. Own
    # still beats inherited: the slot is only filled when it is empty.
    if cascade.get("line_align") and not (node.render_properties or {}).get(
        "line_align"
    ):
        node.render_properties = {
            **(node.render_properties or {}),
            "line_align": cascade["line_align"],
        }
    node.gap_in_line = bool(getattr(node, "line_split", False)) or (
        bool(getattr(node, "is_card", False)) and in_line
    )
    if node.type == "-":
        rp = dict(node.render_properties) if node.render_properties else {}
        for key in ("content_weight", "content_align"):
            if cascade.get(key) and not rp.get(key):
                rp[key] = cascade[key]
        node.render_properties = rp or None
        return
    child_level = (
        _child_owner_level(node, theme, owner_level)
        if theme is not None
        else owner_level
    )
    for child in node.children:
        bake_render_cascade(child, cascade, node.gap_in_line, theme, child_level)


def _col_spring_gaps(
    node,
    children: list,
    width: float,
    height: float,
    node_index: dict,
    fonts,
    theme,
    in_section_levels: frozenset,
    owner_level: int,
) -> list:
    """Extra space to inject BEFORE each child of a ``...`` column.

    LayoutScript splits a ``col`` by ratio on the vertical axis; that half of
    the grammar was never ported, so a col stacks its children at their natural
    heights and ``ratios`` on it are inert. This is the authored slice of it: a
    ``...`` line marks a region boundary, and the surplus height the column was
    given is handed to those boundaries.

    Regions are contiguous and ordered top -> center -> bottom, so the answer is
    a gap before the first child of the centre region and before the first of
    the bottom region. The centre block is placed on the box's midline rather
    than given half the slack each side, matching how ``_layout_row`` places its
    centre bucket — with two blocks of different heights those are not the same
    thing, and the midline is what "centred" means.

    All zeros when the column has no spring, or no surplus to give away — a
    free-standing column's height is its content, so a spring there is inert by
    construction and says so quietly.

    An image card that its picture's ratio made taller than its content puts
    the surplus where its author put room, growing its first ``+++++``; with
    none, above the content, so the words sit at the bottom of the photo and a
    one-line row written first (a chip, a button) stays on top.
    """
    n = len(children)
    card = bool((node.render_properties or {}).get("photo_sized"))
    if not (getattr(node, "col_spring", False) and n >= 2) and not (card and n):
        return [0.0] * n
    # Wrap-aware, as the placement loop reserves them: a region that is a card
    # of its own is as tall as its content plus its padding, and that padding
    # is not surplus to hand to a spring.
    heights, _sec = _cell_heights(
        children,
        [width] * n,
        node_index,
        fonts,
        theme,
        in_section_levels,
        owner_level,
    )
    gaps = [0.0] + [
        _sibling_gap(
            children[i - 1], children[i], theme, "col", owner_level, node_index, node
        )[0]
        for i in range(1, n)
    ]
    surplus = height - (sum(heights) + sum(gaps))
    if surplus <= 0:
        return [0.0] * n
    if not getattr(node, "col_spring", False):
        out = [0.0] * n
        spacers = [i for i, c in enumerate(children) if _is_col_spacer(c)]
        if spacers:
            if spacers[0] + 1 < n:  # a last spacer already has the room below
                out[spacers[0] + 1] = surplus
        else:
            out[1 if n > 1 and children[0].type == "row" else 0] = surplus
        return out
    valigns = [
        (c.render_properties or {}).get("content_valign") or "top" for c in children
    ]

    # Block extents, in document order.
    def _block(name: str) -> tuple[int, float]:
        idx = [i for i, v in enumerate(valigns) if v == name]
        if not idx:
            return -1, 0.0
        span = sum(heights[i] for i in idx) + sum(gaps[i] for i in idx[1:])
        return idx[0], span

    top_i, top_h = _block("top")
    mid_i, mid_h = _block("center")
    bot_i, bot_h = _block("bottom")
    out = [0.0] * n
    # Where each block starts, measured from the top of the box.
    consumed = top_h + (gaps[mid_i] if mid_i > 0 else 0.0)
    if mid_i >= 0:
        want = max(0.0, (height - mid_h) / 2.0)
        out[mid_i] = max(0.0, want - consumed)
        consumed = want + mid_h
    if bot_i >= 0:
        want = height - bot_h
        before = consumed + (gaps[bot_i] if bot_i > 0 else 0.0)
        out[bot_i] = max(0.0, want - before)
    return out


def _is_col_spacer(node) -> bool:
    spacer = (node.render_properties or {}).get("spacer")
    return isinstance(spacer, dict) and spacer.get("axis") == "col"


def _note_actions(
    marks: list, node: LayoutNode, x: float, y: float, w: float, h: float
) -> None:
    """Note where a link card or a heading anchor lands, for ``render_actions``.

    Called with the slot a node is placed in, and again with the outer box a
    wrapped node's background fills; ``render_actions`` merges the two by node
    id, so a card is clickable across its padding too. Plain tuples, so
    placement stays free of the action contract it feeds.
    """
    if node.link_url is not None and node.link_node_id:
        marks.append(("card", node.link_node_id, node.link_url, x, y, w, h))
    if node.heading_id:
        marks.append(("anchor", node.heading_id, None, x, y, w, h))


def place_boxes(
    node: LayoutNode,
    x: float,
    y: float,
    width: float,
    height: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme | None = None,
    inherited: dict | None = None,
    debug_gaps: list | None = None,
    debug_section_gaps: list | None = None,
    in_section_levels: frozenset[int] = frozenset(),
    section_boxes: list | None = None,
    owner_level: int = 0,
    bg_stack: "tuple[int | str, ...] | None" = None,
    action_marks: list | None = None,
) -> list:
    """
    Place LayoutBoxes with content-fitted heights.

    height is the available height from the parent (used by images to fill
    their row slot); text boxes ignore it and use their measured height.

    ``inherited`` carries the cascaded content_weight/content_align hints from
    ancestor group/root nodes, applied to leaf boxes that don't set their own.

    ``debug_gaps`` is an optional accumulator: when provided, each row's
    element-spacing gaps (and plain col gaps) are appended as ``LayoutBox`` rects
    (absolute coords) for the debug overlay. ``debug_section_gaps`` is the same,
    but for the larger between-section gaps (same-level heading siblings), so the
    overlay can color them distinctly. ``None`` (the default) is a zero-cost no-op.

    ``in_section_levels`` tracks heading levels whose section background an
    ancestor already opened (so a section is wrapped only at its outermost
    occurrence); ``section_boxes``, when provided, collects one ``SectionBox`` per
    heading section for the background paint pass.

    ``bg_stack`` is what is painted behind this subtree, innermost first (see
    ``LayoutBox.bg_stack``). ``None`` means "start from the page", so every
    caller — including the tests and the debug overlay — gets it right without
    knowing it exists. Paint-only: it is deliberately absent from every
    measurement mirror (``natural_height`` / ``natural_width`` / ``_layout_row``)
    because it can never change a size.

    ``action_marks``, when provided, collects where each link card and heading
    anchor lands (``_note_actions``). Like ``section_boxes`` it only observes;
    ``None`` is a zero-cost no-op.
    """
    if bg_stack is None:
        bg_stack = _root_bg_stack(theme or Theme())
    if action_marks is not None:
        _note_actions(action_marks, node, x, y, width, height)
    if node.type == "layout":
        results = []
        _t = theme or Theme()
        child_inherited = _cascade_render(node, inherited)
        for child in node.children:
            child_owner = _child_owner_level(child, _t, owner_level)
            # The document body opens a section whenever the grouper flagged it
            # as a heading group (a doc whose whole body is one section) — wrap
            # it here exactly like the col branch, or its background never paints.
            layers = _wrap_layers(child, _t, in_section_levels)
            if layers:
                tpad = _layers_pad(layers)
                slvl = _layers_section_level(layers)
                child_levels = in_section_levels | ({slvl} if slvl else frozenset())
                inner_w = width - tpad.x
                inner_h = natural_height(
                    child,
                    inner_w,
                    node_index,
                    fonts,
                    theme,
                    child_levels,
                    child_owner,
                )
                if action_marks is not None:
                    _note_actions(action_marks, child, x, y, width, inner_h + tpad.y)
                cx2, cy2, cw2, child_bg = _emit_wrap_boxes(
                    section_boxes,
                    x,
                    y,
                    width,
                    inner_h + tpad.y,
                    layers,
                    ring=(child.render_properties or {}).get("ring"),
                    bg_image_url=child.card_bg_url,
                    rotation_index=child.rotation_index,
                    rotation_chain=child.rotation_chain,
                    rotation_path=child.rotation_path,
                    theme=_t,
                    bg_stack=bg_stack,
                    fixed_style_key=child.section_style_key,
                )
                results.extend(
                    place_boxes(
                        child,
                        cx2,
                        cy2,
                        cw2,
                        inner_h,
                        node_index,
                        fonts,
                        theme,
                        child_inherited,
                        debug_gaps,
                        debug_section_gaps,
                        child_levels,
                        section_boxes,
                        child_owner,
                        child_bg,
                        action_marks=action_marks,
                    )
                )
                continue
            child_h = natural_height(
                child,
                width,
                node_index,
                fonts,
                theme,
                in_section_levels,
                child_owner,
            )
            results.extend(
                place_boxes(
                    child,
                    x,
                    y,
                    width,
                    child_h,
                    node_index,
                    fonts,
                    theme,
                    child_inherited,
                    debug_gaps,
                    debug_section_gaps,
                    in_section_levels,
                    section_boxes,
                    child_owner,
                    bg_stack,
                    action_marks=action_marks,
                )
            )
        return results

    if node.type == "-":
        eff = dict(node.render_properties) if node.render_properties else {}
        inh = inherited or {}
        for key in ("content_weight", "content_align"):
            if not eff.get(key) and inh.get(key):
                eff[key] = inh[key]
        return [
            LayoutBox(
                x=x,
                y=y,
                width=width,
                height=height,
                content_id=node.content_id,
                render_properties=eff or None,
                bg_stack=bg_stack,
            )
        ]

    if node.type == "row":
        child_inherited = _cascade_render(node, inherited)
        placements, row_h, gap_spans = _layout_row(
            node,
            width,
            node_index,
            fonts,
            theme,
            child_inherited,
            in_section_levels,
            owner_level,
        )
        if getattr(node, "bento", False) and height > row_h:
            # A nested bento row inside a stretched column band: the parent
            # allotted more height than the row's natural row_h — stretch every
            # cell to it so the mosaic edges stay aligned.
            placements = _stretch_bento_placements(placements, height)
            row_h = height
        for gx, gw, is_sec, owner in gap_spans:
            box = LayoutBox(x=x + gx, y=y, width=gw, height=row_h)
            if is_sec:
                if debug_section_gaps is not None:
                    debug_section_gaps.append((box, owner))
            elif debug_gaps is not None:
                debug_gaps.append(box)
        _t = theme or Theme()
        results = []
        for child, x_offset, cw, effective_h, dy in placements:
            child_owner = _child_owner_level(child, _t, owner_level)
            # Two vertical channels, and the ROW's answer wins where both speak.
            #
            # `dy` is the row-level alignment `_row_valign_offsets` computed for
            # a same-line row or an authored `:::` row, from the level's
            # `Line align`. `content_valign` is a per-CELL hint. A `:::` row can
            # carry both: the level says `Line align`, and one cell may still
            # hold its own hint.
            #
            # `or` resolves that the right way round, since a cell the row placed
            # has a non-zero `dy` only when the row had something to say.
            cy = y + (dy or _valign_offset(child.render_properties, effective_h, row_h))
            layers = _wrap_layers(child, _t, in_section_levels)
            if layers:
                # Per-cell section/card wrap: emit one box per layer (outer→inner)
                # filling the cell, inset content by the summed TLRB paddings.
                slvl = _layers_section_level(layers)
                child_levels = in_section_levels | ({slvl} if slvl else frozenset())
                if action_marks is not None:
                    _note_actions(
                        action_marks, child, x + x_offset, cy, cw, effective_h
                    )
                cx2, cy2, cw2, child_bg = _emit_wrap_boxes(
                    section_boxes,
                    x + x_offset,
                    cy,
                    cw,
                    effective_h,
                    layers,
                    ring=(child.render_properties or {}).get("ring"),
                    bg_image_url=child.card_bg_url,
                    rotation_index=child.rotation_index,
                    rotation_chain=child.rotation_chain,
                    rotation_path=child.rotation_path,
                    theme=_t,
                    bg_stack=bg_stack,
                    fixed_style_key=child.section_style_key,
                )
                inner_h = effective_h - _layers_pad(layers).y
                results.extend(
                    place_boxes(
                        child,
                        cx2,
                        cy2,
                        cw2,
                        inner_h,
                        node_index,
                        fonts,
                        theme,
                        child_inherited,
                        debug_gaps,
                        debug_section_gaps,
                        child_levels,
                        section_boxes,
                        child_owner,
                        child_bg,
                        action_marks=action_marks,
                    )
                )
                continue
            results.extend(
                place_boxes(
                    child,
                    x + x_offset,
                    cy,
                    cw,
                    effective_h,
                    node_index,
                    fonts,
                    theme,
                    child_inherited,
                    debug_gaps,
                    debug_section_gaps,
                    in_section_levels,
                    section_boxes,
                    child_owner,
                    bg_stack,
                    action_marks=action_marks,
                )
            )
        return results

    if node.type == "col":
        _t = theme or Theme()
        if getattr(node, "table", False):
            # Table subtree: geometry comes from the TablePlan (grid or
            # stacking-cards), not the generic col stacking.
            return _place_table_boxes(
                node,
                x,
                y,
                width,
                node_index,
                fonts,
                theme,
                inherited,
                debug_gaps,
                debug_section_gaps,
                in_section_levels,
                section_boxes,
                owner_level,
                bg_stack,
                action_marks=action_marks,
            )
        children = _padded_children(node)
        child_inherited = _cascade_render(node, inherited)
        # Bento column band: when the enclosing bento row allotted more height
        # than the stacked content needs, distribute the surplus across the
        # children proportional to their natural totals (all-zero → last child),
        # so interior horizontal edges spread naturally and the band bottom
        # reaches the row bottom. All-zero extras ⇒ identical to the default.
        extras = [0.0] * len(children)
        if getattr(node, "bento", False) and children:
            totals, _sec = _cell_heights(
                children,
                [width] * len(children),
                node_index,
                fonts,
                _t,
                in_section_levels,
                owner_level,
            )
            gaps_total = sum(
                _sibling_gap(
                    children[i - 1],
                    children[i],
                    _t,
                    "col",
                    owner_level,
                    node_index,
                    node,
                )[0]
                for i in range(1, len(children))
            )
            surplus = max(0.0, height - (sum(totals) + gaps_total))
            if surplus > 0:
                denom = sum(totals)
                if denom > 0:
                    extras = [surplus * t / denom for t in totals]
                else:
                    extras[-1] = surplus
        results, cur_y = [], y
        # An authored `...` column: the surplus height becomes the springs.
        # Regions are contiguous and ordered top -> center -> bottom, so the
        # slack is injected as extra space at the two region BOUNDARIES — a
        # spring IS an expanding gap, which is exactly what this is. The middle
        # block centres on the box rather than splitting the slack evenly,
        # matching how `_layout_row` places a centre bucket on the other axis.
        spring_gap = _col_spring_gaps(
            node,
            children,
            width,
            height,
            node_index,
            fonts,
            _t,
            in_section_levels,
            owner_level,
        )
        # A ring reserves the full diameter but its value/unit content is
        # smaller — center the col vertically within the inner (padded) box.
        if getattr(node, "card_kind", None) == "ring" and children:
            content_h = sum(
                natural_height(
                    c,
                    width,
                    node_index,
                    fonts,
                    theme,
                    in_section_levels,
                    _child_owner_level(c, _t, owner_level),
                )
                for c in children
            ) + sum(
                _sibling_gap(
                    children[i - 1],
                    children[i],
                    _t,
                    "col",
                    owner_level,
                    node_index,
                    node,
                )[0]
                for i in range(1, len(children))
            )
            cur_y = y + max(0.0, (height - content_h) / 2.0)
        # The space a spring opens above the FIRST child: a column that starts
        # with `...` has no top region, so its first block is the one placed.
        if spring_gap:
            cur_y += spring_gap[0]
        for i, child in enumerate(children):
            if i > 0:
                # Col gap owned by the enclosing section (owner_level); section
                # spacing between sections, else element spacing. Mirrors
                # natural_height exactly.
                gap, is_section = _sibling_gap(
                    children[i - 1], child, _t, "col", owner_level, node_index, node
                )
                if gap > 0:
                    box = LayoutBox(x=x, y=cur_y, width=width, height=gap)
                    if is_section:
                        if debug_section_gaps is not None:
                            debug_section_gaps.append((box, owner_level))
                    elif debug_gaps is not None:
                        debug_gaps.append(box)
                cur_y += gap + spring_gap[i]
                rule = divider_rect(children[i - 1], child, x, cur_y, width, _t)
                if rule is not None and section_boxes is not None:
                    rx, ry, rw, rh, kind = rule
                    section_boxes.append(
                        SectionBox(rx, ry, rw, rh, 0, PaddingBox(), kind)
                    )
            child_owner = _child_owner_level(child, _t, owner_level)
            layers = _wrap_layers(child, _t, in_section_levels)
            if layers:
                # Section/card wrap: emit one box per layer (outer→inner), inset
                # content by the summed TLRB paddings, reserve inner_h + Σpad.y.
                tpad = _layers_pad(layers)
                slvl = _layers_section_level(layers)
                child_levels = in_section_levels | ({slvl} if slvl else frozenset())
                inner_w = width - tpad.x
                inner_h = (
                    natural_height(
                        child,
                        inner_w,
                        node_index,
                        fonts,
                        theme,
                        child_levels,
                        child_owner,
                    )
                    + extras[i]
                )
                total_h = inner_h + tpad.y
                if action_marks is not None:
                    _note_actions(action_marks, child, x, cur_y, width, total_h)
                cx2, cy2, cw2, child_bg = _emit_wrap_boxes(
                    section_boxes,
                    x,
                    cur_y,
                    width,
                    total_h,
                    layers,
                    ring=(child.render_properties or {}).get("ring"),
                    bg_image_url=child.card_bg_url,
                    rotation_index=child.rotation_index,
                    rotation_chain=child.rotation_chain,
                    rotation_path=child.rotation_path,
                    theme=_t,
                    bg_stack=bg_stack,
                    fixed_style_key=child.section_style_key,
                )
                results.extend(
                    place_boxes(
                        child,
                        cx2,
                        cy2,
                        cw2,
                        inner_h,
                        node_index,
                        fonts,
                        theme,
                        child_inherited,
                        debug_gaps,
                        debug_section_gaps,
                        child_levels,
                        section_boxes,
                        child_owner,
                        child_bg,
                        action_marks=action_marks,
                    )
                )
                cur_y += total_h
                continue
            child_h = (
                natural_height(
                    child,
                    width,
                    node_index,
                    fonts,
                    theme,
                    in_section_levels,
                    child_owner,
                )
                + extras[i]
            )
            results.extend(
                place_boxes(
                    child,
                    x,
                    cur_y,
                    width,
                    child_h,
                    node_index,
                    fonts,
                    theme,
                    child_inherited,
                    debug_gaps,
                    debug_section_gaps,
                    in_section_levels,
                    section_boxes,
                    child_owner,
                    bg_stack,
                    action_marks=action_marks,
                )
            )
            cur_y += child_h
        return results

    return []
