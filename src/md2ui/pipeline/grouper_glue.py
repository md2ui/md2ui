"""Glued content: which siblings become one card, and which wrappers go away.

A *glued content segment* is a run of sibling nodes the author wrote as one
unbroken stretch of source — no blank line between them. The grouper stamps a
``glued_content_id`` on those siblings while it builds the tree; this module is
the phase that reads those ids back and turns them into structure: a wrapper
group flagged ``glued_content_group``, and the card that flag earns.

Collapse belongs here for the same reason: a group that survives with one child
or none is an artifact of the wrapping, and unwrapping it is the other half of
the same decision. ``_keep_card_role`` is the correction that pairs with it —
a collapse can hand a photo to a wrapper that has no role to paint it with.

Every function here runs post-order over a FINISHED tree and is called only by
``process``. Nothing here splits text or mints an id.
"""

from md2ui.pipeline.data_point_types import DataPointType
from md2ui.pipeline.grouper_column_rows import hand_down_valign
from md2ui.pipeline.grouper_spacers import carry_edge_spacers
from md2ui.pipeline.grouper_types import (
    MarkdownGroupNode,
    NodeType,
    _HEADING_TYPE_RE,
    same_section_kind,
)


# Types whose value, annotated on a whole TEXT leaf, can sit beside TEXT
# siblings in a same-line value group that must keep the collapsed fingerprint
# of the unsplit line. Add a type only with a document that needs it.
_ANNOTATE_ONLY_SPLIT_GROUP_TYPES = frozenset(
    {
        DataPointType.QUANTITY,
        DataPointType.TIME,
        DataPointType.CHANGE,
        DataPointType.CURRENCY,
        DataPointType.RANKING,
        # `0:18 ... -2:24` (tests-render/home-dashboards/bento-cards) is a same-line
        # [DATAPOINT, TEXT] group; annotating the ratio leaves [TEXT, TEXT],
        # which stops collapsing to the unsplit line's fingerprint without this.
        DataPointType.RATIO,
        DataPointType.PERCENTAGE,
    }
)
# The same types as a serialized data point names them: the layout generator
# fingerprints the tree rebuilt from ``to_dict()``, whose data points carry a
# ``dp_<type>`` label instead of the enum, and must reach the same decision.
_ANNOTATE_ONLY_SPLIT_GROUP_LABELS = frozenset(
    f"dp_{t.value}" for t in _ANNOTATE_ONLY_SPLIT_GROUP_TYPES
)


def _wrap_glued_content(node: "MarkdownGroupNode") -> None:
    """Wrap each source-glued content segment in a ``group`` flagged
    ``glued_content_group=True``.

    Post-order. For each parent, its children carry the ``glued_content_id``
    of the segment they belong to (set at the to_ast / blank-split origins
    and inherited through splits). Two shapes are handled:

    - A blank-split paragraph segment is already its own wrapper group
      (flagged ``_glue_root``); it is flagged ``glued_content_group`` in
      place.
    - A heading-spanning (or otherwise flat) segment is a maximal run of
      consecutive siblings sharing one id; the run is moved into a new
      ``group`` node flagged ``glued_content_group``.

    The id stays on the members (children). A redundant single-child
    wrapper left around a glued group is absorbed into its parent later by
    ``_collapse_groups`` (which moves the flag onto the parent).

    Time: O(K), Space: O(K).
    """
    for child in node.children:
        _wrap_glued_content(child)

    new_children: list[MarkdownGroupNode] = []
    children = node.children
    n = len(children)
    i = 0
    while i < n:
        child = children[i]
        gid = child.glued_content_id
        if gid is None or gid == node.glued_content_id:
            # Not part of a segment, or a member of the parent's own segment
            # (the parent is already the wrapper) — leave in place.
            new_children.append(child)
            i += 1
        elif child._glue_root:
            # Paragraph segment that is already its own wrapper group.
            child.glued_content_group = True
            child._glue_root = False
            new_children.append(child)
            i += 1
        else:
            # Flat run of consecutive members sharing this segment id.
            j = i
            while (
                j < n
                and children[j].glued_content_id == gid
                and not children[j]._glue_root
            ):
                j += 1
            wrapper = MarkdownGroupNode(type=NodeType.GROUP)
            wrapper.glued_content_group = True
            wrapper.glued_content_id = gid
            wrapper.children = children[i:j]
            # ``column_split_group`` names the node that DIRECTLY holds the
            # colon pieces, so it has to follow them into the wrapper — on a
            # lone-line document the pieces sit on the root and this wrapper
            # is what ends up holding them. Only when the run is all of them:
            # a partial run means the parent still holds pieces of its own.
            if node.column_split_group and j - i == n:
                wrapper.column_split_group = True
                node.column_split_group = False
            # ``align_group`` names the node that DIRECTLY holds the spring
            # regions, for the same reason and under the same all-of-them
            # condition.
            if node.align_group and j - i == n:
                wrapper.align_group = True
                node.align_group = False
            if node.separator_chars and j - i == n:
                wrapper.separator_chars = node.separator_chars
                node.separator_chars = []
            new_children.append(wrapper)
            i = j
    node.children = new_children


def _keep_card_role(node: "MarkdownGroupNode") -> None:
    """Make sure a node that ended up holding a photo still paints one.

    When a collapse hands ``card_bg_url`` to a plain wrapper, that wrapper
    has the image but no background role, so nothing would draw it. A
    heading wrapper is left alone on purpose: its section role outranks the
    card, and it paints the photo with its own radius and padding, so the
    collapsed heading matches its untouched siblings.
    """
    if node.card_bg_url is None or node.heading_group:
        return
    if node.type == NodeType.GROUP:
        node.type = NodeType.IMAGE_CARD
    elif node.type != NodeType.IMAGE_CARD and not node.glued_content_group:
        # A semantic wrapper (list item, table cell, …) keeps its own type,
        # so mark it glued instead — the same thing the collapse already
        # does for a list item whose only content is one glued segment.
        # Without a role of some kind the photo would simply never paint.
        node.glued_content_group = True


def _wrap_lone_root_content(root: "MarkdownGroupNode") -> None:
    """Give a childless ROOT's content a child to live on — Phase 6.04.

    The document root is the one node where content means nothing to anybody:
    the generator's empty-document guard tests ``children`` alone, so a root
    holding text and no children draws nothing at all. Everywhere else in the
    tree content means a leaf to draw, which is why ``- One line.`` renders and
    ``One line.`` would not — the list marker gives the text a child to sit on.

    A no-op for an empty document, which is childless because it really is
    empty, and that is the case the guard exists for.

    Time: O(1), Space: O(1).
    """
    if root.children or not root.content:
        return
    child = MarkdownGroupNode(type=NodeType.TEXT, content=root.content)
    # Pure inheritance, no mint: this module mints nothing (see the header), and
    # there is nothing to mint for anyway — glue groups two or more pieces, and
    # a document that is one leaf has one.
    child.glued_content_id = root.glued_content_id
    child.source_line_id = root.source_line_id
    # Everything that describes the LEAF travels with it. A tier is the one that
    # bites: Phase 2.16 stamps a whole-line tier on the node holding the line, so
    # leaving it on the root would count `_Muted text_` twice — once on the
    # container and once on the leaf 6.055 pushes it down to.
    child.text_style = root.text_style
    child.data_points = root.data_points
    child.paren_quote_ranges = root.paren_quote_ranges
    root.content = ""
    root.text_style = None
    root.data_points = []
    root.paren_quote_ranges = []
    root.children = [child]


def _collapse_groups(node: "MarkdownGroupNode") -> None:
    """Collapse redundant group nodes (post-order).

    - An organizational ``group`` wrapper whose only child is another such
      ``group`` is merged: the grandchildren are lifted into the surviving
      node, the ``glued_content_group`` flag is OR-ed in, and the
      ``glued_content_id`` is inherited. Chains collapse. Only plain
      ``group``-typed nodes are merged, so semantic group nodes
      (``key-value``, ``list_item``, …) keep their level.
    - A plain ``group`` with 0 children  → dropped.
    - A plain ``group`` with 1 child     → replaced by that child, EXCEPT a
      glued group, which is preserved (the flag must survive).

    **A level survives when it is a heading section of a different level from
    its sole child** — see ``_same_section_kind``. Two nested sections are two
    painted containers, and every branch below would keep only one of them.
    All three branches are guarded, because all three could dissolve the outer.

    Then, the glued-redundancy absorb: a non-root group node (no content)
    whose sole child is a glued ``group`` absorbs it — the grandchildren are
    lifted and the flag moves onto this node (e.g. a ``list_item`` whose only
    content is one glued segment becomes the glued group itself, dropping the
    wrapper). The ``root`` guard keeps the document root from being flagged.

    Only targets nodes with no content, since content means the pipeline
    has not yet split them.

    Time: O(K), Space: O(1) (in-place).
    """
    for child in list(node.children):
        _collapse_groups(child)
    new_children: list[MarkdownGroupNode] = []
    for child in node.children:
        # Merge a plain group wrapper that holds a single plain group child,
        # OR-ing the glued flag and inheriting the id.
        while (
            child.type == NodeType.GROUP
            and not child.content
            and len(child.children) == 1
            and child.children[0].type == NodeType.GROUP
            and not child.children[0].content
            # Re-tested every iteration on purpose: once ``child`` adopts an
            # inner section's level below, the next lap compares against the
            # level it just took, so a ``# `` > ``## `` > ``### T`` chain stops
            # at each real boundary instead of flattening to the innermost.
            and same_section_kind(child, child.children[0])
        ):
            inner = child.children[0]
            if inner.glued_content_group:
                child.glued_content_group = True
            # The colon-column flag names whoever DIRECTLY holds the pieces,
            # so it follows them up every time a level is dissolved. The
            # separator chars are the same kind of fact — they describe the
            # gaps between THESE children.
            if inner.column_split_group:
                child.column_split_group = True
            # Its BLOCK-level twin: without it, a `:::` row that is a group's
            # sole child (`AAA / ::: / ## H / body`) is lifted as cells that
            # silently stack. The weights travel with the flag — they describe
            # THESE cells.
            if inner.column_row_group:
                child.take_column_row(inner)
            if inner.align_group:
                child.align_group = True
            # So does the flag a `...` line leaves on whoever holds its regions:
            # without it a link card's springs, lifted into its section, have
            # no height to divide.
            if inner.valign_group:
                child.valign_group = True
            # An authored alignment describes the CONTENT that is moving up,
            # not the level being dissolved, so it rides along with it —
            # otherwise a single-region spring line ("... A - B - C", whose
            # one region collapses straight away) would lose the very
            # alignment it was written to express.
            if inner.authored_align and not child.authored_align:
                child.authored_align = inner.authored_align
            carry_edge_spacers(inner, child)
            if inner.separator_chars and not child.separator_chars:
                child.separator_chars = inner.separator_chars
            if inner.heading_group:
                child.heading_group = True
                # Reached only when the two sections share a level (the guard
                # above stops every other pair), so "which level wins"
                # decides nothing — both spellings name the same
                # container. The assignment stays because ``child`` may not be
                # a section at all: a plain wrapper takes the flag and the
                # level from the section it absorbs.
                if inner.heading_level is not None:
                    child.heading_level = inner.heading_level
                child.heading_id = inner.heading_id
                child.fixed_style_key = inner.fixed_style_key
            if child.glued_content_id is None:
                child.glued_content_id = inner.glued_content_id
            if child.link_url is None:
                child.link_url = inner.link_url
            if child.card_bg_url is None:
                child.card_bg_url = inner.card_bg_url
            child.children = inner.children
            _keep_card_role(child)

        if child.type == NodeType.GROUP and not child.content:
            if len(child.children) == 0:
                pass  # drop
            elif (
                len(child.children) == 1
                and not child.glued_content_group
                # Promoting the child would drop the wrapper's own level, and
                # the transfer below declines to overwrite a child that is
                # already a section — so without this the outer simply vanishes.
                and same_section_kind(child, child.children[0])
            ):
                # Unwrap: move a heading-section flag onto the promoted child so
                # the section marking survives without keeping the wrapper level.
                promoted = child.children[0]
                if child.heading_group and not promoted.heading_group:
                    promoted.heading_group = True
                    promoted.heading_level = child.heading_level
                    promoted.heading_id = child.heading_id
                    promoted.fixed_style_key = child.fixed_style_key
                # Same reason as the merge branch: the alignment belongs to
                # the content, so it survives the wrapper being unwrapped.
                if child.authored_align and not promoted.authored_align:
                    promoted.authored_align = child.authored_align
                carry_edge_spacers(child, promoted)
                # The clickable annotation follows whatever survives, so a
                # link wrapping one image collapses to a clickable image.
                if child.link_url is not None and promoted.link_url is None:
                    promoted.link_url = child.link_url
                if child.card_bg_url is not None and promoted.card_bg_url is None:
                    promoted.card_bg_url = child.card_bg_url
                    _keep_card_role(promoted)
                new_children.append(promoted)
            else:
                new_children.append(child)
        else:
            new_children.append(child)
    node.children = new_children

    # Glued-redundancy absorb: an existing (non-root) group node whose sole
    # child is a glued group becomes that glued group itself — no wrapper.
    if node.type != "root" and not node.content and len(node.children) == 1:
        only = node.children[0]
        if (
            not only.content
            and (
                (only.type == NodeType.GROUP and only.glued_content_group)
                or only.type == NodeType.IMAGE_CARD
            )
            # A glued section absorbed into a section of another level would
            # take the inner level with it, same loss as the two branches above.
            and same_section_kind(node, only)
            # A card never flows as a line (grouper_line_flow), so a one-line
            # row absorbed into it would stack its pieces.
            and not (node.type == NodeType.IMAGE_CARD and _one_line(only))
        ):
            # A `...` region's placement belongs to its content, like the flags.
            hand_down_valign(only, only.children)
            node.children = only.children
            if only.glued_content_group:
                node.glued_content_group = True
            # Same reason as the merge branch above: these name whoever
            # directly holds the pieces, so they follow them here too.
            if only.column_split_group:
                node.column_split_group = True
            # Same pair as the merge branch, for the same reason.
            if only.column_row_group:
                node.take_column_row(only)
            if only.align_group:
                node.align_group = True
            if only.valign_group:
                node.valign_group = True
            if only.authored_align and not node.authored_align:
                node.authored_align = only.authored_align
            carry_edge_spacers(only, node)
            if only.separator_chars and not node.separator_chars:
                node.separator_chars = only.separator_chars
            # A heading role has to survive the absorb: it outranks the
            # wrapper's card role when the paint layer is chosen, and
            # dropping it deletes the section styling outright.
            if only.heading_group:
                node.heading_group = True
                # Same rule as the merge branch: the guard above leaves only
                # pairs that share a level, or in which ``node`` is not a
                # section and inherits one.
                if only.heading_level is not None:
                    node.heading_level = only.heading_level
                node.heading_id = only.heading_id
                node.fixed_style_key = only.fixed_style_key
            if node.glued_content_id is None:
                node.glued_content_id = only.glued_content_id
            if node.link_url is None:
                node.link_url = only.link_url
            # The photo follows whatever survives. Safe at any depth
            # because every collapse here is a *full overlap* — the node
            # has exactly one contentless child — so the survivor covers
            # precisely the same rect the card did. It is the merge/unwrap
            # of nodes with *siblings* that could widen the extent, and
            # those never reach this branch.
            if node.card_bg_url is None:
                node.card_bg_url = only.card_bg_url
            _keep_card_role(node)


def _one_line(node: "MarkdownGroupNode") -> bool:
    """Whether *node* holds two or more pieces written on one source line."""
    lines = {c.source_line_id for c in node.children}
    return len(node.children) > 1 and len(lines) == 1 and None not in lines


def _glue_stacked_block(
    node: "MarkdownGroupNode", in_glued: bool, in_heading: bool
) -> tuple[bool, bool]:
    """Give a STACKED block its own glue — one card per block.

    Glue means a card, and the thing that earns one is a block that stacks
    its pieces. Two shapes qualify, and the reason is the same for both:

    * a ``Key: value`` pair — the value takes its own line under the key;
    * a colon COLUMN (``A : B``, ``column_split_group``) with 2+ children —
      ` : ` is the authored way to stack peer pieces into one block.

    Glue is minted per source-line *segment*, so a line holding several of
    these produces one wrapper for the whole line, not one per block. That
    wrapper is then cleared by :meth:`_clear_false_glue` (the line flows),
    leaving ``Key: value - Key: value`` with no glue on the LINE — and this
    pass then puts it back where it belongs, on each block. A block is its
    own unit, so it carries its own glue wherever it sits: the middle of
    ``A - B : C : D - E`` is a card, exactly as a lone ``B : C : D`` is.

    Three exclusions:

    * **Inside a glued group** — a block sitting in a multi-line paragraph
      is part of that card, and nesting glue is forbidden.
    * **Inside a heading TEXT node** — ``## 💲 Budget: **$2,450**`` parses
      as ``heading2 > key-value``; gluing that would draw a card inside the
      heading line. Note this tests the heading text node, not
      ``heading_group``: a heading *section's body* still glues its blocks.

    One step (Phase 6.15) of the top-down stamp walk,
    ``grouper_annotate._stamp_finished_tree``: it stamps *node* and returns the
    ``(in_glued, in_heading)`` its children inherit. It cannot join Phase 6.1 —
    that one is post-order (it needs children's line ids before it can clear a
    parent's glue), while this needs ancestor state that is only final
    afterwards.

    Time: O(K), Space: O(depth).
    """
    is_heading = bool(_HEADING_TYPE_RE.match(node.type))
    if not in_glued and not in_heading and not is_heading:
        # ``not is_heading`` covers the node ITSELF being a heading: a colon
        # column can BE the heading node (``## 92 : days`` is a heading2
        # carrying column_split_group), where ``in_heading`` — which only
        # describes ancestors — has not been set yet.
        if node.type == NodeType.KEY_VALUE or (
            node.column_split_group and len(node.children) >= 2
        ):
            node.glued_content_group = True
    return in_glued or node.glued_content_group, in_heading or is_heading


def _clear_false_glue(node: "MarkdownGroupNode", flows_one_line: bool) -> None:
    """Drop ``glued_content_group`` where it does not mean glued content.

    Glue means *consecutive source lines stuck together*, and it is what
    makes the renderer draw an element card. Two shapes acquire the label
    without meaning it:

    * **A same-line split that flows.** One physical line broken into
      pieces has no consecutive lines to glue. ``flows_one_line`` says so
      directly rather than reading ``line_split_group``, because some
      same-line runs flow through their own generator path (a homogeneous
      pill run, a repeated group run) and carry no flag at all. A
      same-line split that *stacks* still counts as glue — that is the
      ``Key: value`` case, where the value takes its own line.
    * **A group holding a heading leaf.** The heading section and the
      heading text node are different things, and a section carrying a
      heading is not a card. Testing direct children covers both the
      section (``group[heading2, text…]``) and a bare wrapper around just
      the heading text.

    Runs from :meth:`_derive_line_split_groups` because that pass is
    already a full-tree walk at the only correct point: after
    ``_collapse_groups`` (which ORs glue onto merged nodes) and after
    ``line_split_group`` exists. Folding it in costs no extra traversal.
    """
    if not node.glued_content_group:
        return
    if flows_one_line or any(_HEADING_TYPE_RE.match(c.type) for c in node.children):
        node.glued_content_group = False


def _is_datapoint_split_group(node: "MarkdownGroupNode") -> bool:
    """True for a same-line group produced by the DATAPOINT split — one
    value line shattered into DATAPOINT/TEXT pieces (e.g. ``750/1800 Kcal``
    → ``[datapoint, text]``, ``75/100g`` → ``[datapoint, text, datapoint]``).

    Used by ``_build_fingerprint`` to collapse such a group to a single
    TEXT-leaf fingerprint so it matches the unsplit value line. Scoped to
    datapoint splits only: the group must be a same-line ``line_split_group``
    whose children are ALL leaves of type DATAPOINT/TEXT with at least one
    DATAPOINT or its proven annotate-only equivalent: a TEXT leaf carrying
    exactly one allowlisted datapoint that matches its whole content. It excludes
    emoji/link peels (EMOJI/LINK children), segment splits (SEGMENT/GROUP
    children), partial inline spans and KV pairs (KEY/VALUE, not line-split).
    """
    if not node.line_split_group or node.type != NodeType.GROUP or not node.children:
        return False
    saw_datapoint = False
    for c in node.children:
        if c.children or c.type not in (NodeType.DATAPOINT, NodeType.TEXT):
            return False
        if c.type == NodeType.DATAPOINT or _is_whole_annotate_only_leaf(c):
            saw_datapoint = True
    return saw_datapoint


def _is_whole_annotate_only_leaf(leaf: "MarkdownGroupNode") -> bool:
    """A TEXT leaf that is exactly one value of a former split type.

    Read only from fields ``to_dict()`` keeps, so the live tree and the tree
    rebuilt from it fingerprint a spring-cut stat line the same way.
    """
    if leaf.type != NodeType.TEXT or len(leaf.data_points) != 1:
        return False
    point = leaf.data_points[0]
    return point.get("matched") == leaf.content and (
        point.get("type") in _ANNOTATE_ONLY_SPLIT_GROUP_TYPES
        or point.get("label") in _ANNOTATE_ONLY_SPLIT_GROUP_LABELS
    )
