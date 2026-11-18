"""Stamps the grouper puts on a finished node.

The last phases ``process`` runs. By this point the tree's SHAPE is settled;
what is left is to record, on the nodes themselves, the things a later stage
would otherwise have to re-infer from the text: that a value should be drawn as
a bar or a ring, that an emoji is a badge rather than a glyph in a sentence,
which colour slot a section takes, that a run of ⭐ is a rating.

That is ADR-100 in its most literal form — the generator and the renderer
CONSUME these flags and never re-derive them. Each function here takes a
finished node and returns nothing; it writes flags, and it does not restructure.

The one exception earns its place: ``_detect_through_markers`` runs the data
point detector on a line with the author's markers and escapes taken out of the
way, because a ``\\b``-anchored pattern cannot see past an underscore. It is
here because the data-point annotation phase is its main caller.
"""

import re

from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.data_point_types import DataPointType
from md2ui.pipeline.grouper_escapes import (
    ESCAPABLE_SEPARATORS,
    _value_escape_spans,
)
from md2ui.pipeline.grouper_display_vocab import _bare_content, _dp_kind
from md2ui.pipeline.grouper_displays import (
    _STAR_SCORE_LABELS,
    _try_container_display,
    _try_leaf_display,
)
from md2ui.pipeline.grouper_glue import _glue_stacked_block
from md2ui.pipeline.grouper_choices import is_segmented_run
from md2ui.pipeline.grouper_content_edits import edit_content
from md2ui.pipeline.grouper_inline_marks import quoted_element_edits
from md2ui.pipeline.grouper_node_reads import late_escape_edits
from md2ui.pipeline.grouper_ranges import _bracket_quote_ranges, _merge_pq
from md2ui.utils.image_params import placeholder_ref
from md2ui.pipeline.grouper_types import (
    ELEMENT_LEAF_TYPES,
    MarkdownGroupNode,
    NodeType,
    STRUCTURAL_BACKGROUND_KINDS,
    _classify_link_content,
)


# A leaf that is nothing but star-rating glyphs — its ratio/score siblings are
# a star rating, not a progress ratio, so the drawn-bar families skip them.
_STAR_RUN_RE = re.compile(r"^[⭐★☆]+$")

# An ATX heading marker still on a leaf's text: a heading written inside another
# block (`- # Title`, `> # Title`), which the block parse keeps as the block's text.
_ATX_PREFIX_RE = re.compile(r"^(#{1,6}) (?=.)")


def _wrap_date_chip_groups(node: "MarkdownGroupNode") -> None:
    """Replace each ``datapoint_display == "date_chip"`` LEAF with a
    GROUP holding two TEXT children (key = weekday/month, day = number).

    The chip must be a group, not a leaf: the rule layout grids repeated
    GROUP runs but stacks leaf runs. Building plain-text children gives a
    uniform ``group(text,text)`` fingerprint — distinct from a bare-text
    header and identical across chips whatever the source token type
    (a backticked date is inline_code as a leaf, but its chip is still
    ``group(text,text)``) — so ``repeated_children`` buckets only the
    chips and ``_build_grouped`` grids them. The display flag + payload
    move onto the group; the children are pure presentation (no
    data_points). Runs before fingerprints/node_ids, so inserting nodes
    is safe.
    """
    for child in node.children:
        _wrap_date_chip_groups(child)
    # Convert the node itself in place when it is a date-chip leaf (covers
    # a single-line document that collapses to a lone leaf root, too).
    if node.datapoint_display == "date_chip" and not node.children:
        payload = node.datapoint_payload or {}
        # Keep the source text. A chip is presentation and `### Dates →
        # Enabled: no` switches it off, but this split has already happened
        # by then — the grouper has no theme to gate it on. It must travel
        # in the PAYLOAD, not on the node: `_is_group` in the layout
        # generator defines a container as contentless, so leaving the text
        # on `node.content` would stop the chip being recognised as a group
        # at all. The `ratio_bar` payload carries a "text" key too.
        payload = {**payload, "text": node.content}
        node.datapoint_payload = payload
        key = MarkdownGroupNode(content=str(payload.get("key", "")), type=NodeType.TEXT)
        day = MarkdownGroupNode(content=str(payload.get("day", "")), type=NodeType.TEXT)
        key.source_line_id = node.source_line_id
        day.source_line_id = node.source_line_id
        node.type = NodeType.GROUP
        node.content = ""
        node.data_points = []
        node.children = [key, day]


def _is_star_leaf(node: "MarkdownGroupNode") -> bool:
    """A star-glyph run leaf, or a leaf holding a star-rating SCORE."""
    if _STAR_RUN_RE.fullmatch(_bare_content(node.content)):
        return True
    for dp in node.data_points:
        if _dp_kind(dp) != "score":
            continue
        v = dp.get("value")
        if isinstance(v, dict) and (
            str(v.get("label") or "").lower() in _STAR_SCORE_LABELS
            or v.get("subtype") == "single_star"
        ):
            return True
    return False


def _annotate_datapoint_displays(
    node: "MarkdownGroupNode",
    in_table: bool = False,
    _root: bool = True,
) -> None:
    """Post-order: stamp ``datapoint_display`` + ``datapoint_payload``.

    Runs UNCONDITIONALLY (like table_group): THEME.md toggles gate the
    *consumption* downstream, never the grouping AST, so grouping
    snapshots stay theme-independent. Table subtrees are skipped — the
    table cell rendering owns their datapoints. Starred ratios (a SCORE
    labelled stars/rating, or a star-glyph sibling) are left as text.

    Leaf families are decided from the parent (so sibling star context is
    visible); container families from the node itself. First match wins.

    Time: O(K + D) where D = total datapoints, Space: O(depth).
    """
    in_table = in_table or node.table_group
    for c in node.children:
        _annotate_datapoint_displays(c, in_table, _root=False)
    if in_table:
        return
    if not node.children:
        # A single-line document collapses to a lone leaf root — there is
        # no parent loop to decide its leaf family (and no siblings, so no
        # star context either).
        if _root and node.datapoint_display is None and node.text_style is None:
            _try_leaf_display(node, False)
        return
    star_context = any(_is_star_leaf(c) for c in node.children)
    for c in node.children:
        if not c.children and c.datapoint_display is None and c.text_style is None:
            _try_leaf_display(c, star_context)
    # An authored tier anywhere in the pair takes the whole container out of
    # the running: the author has stated this line's typography, and a
    # half-authored / half-drawn pair (an explicit key beside a drawn value)
    # is never what they asked for.
    if node.datapoint_display is None and not any(c.text_style for c in node.children):
        _try_container_display(node, star_context)


def _stamp_emoji_children(node: "MarkdownGroupNode", in_heading: bool) -> bool:
    """Tag *node*'s EMOJI children with their render role and sibling ordinal,
    and return the heading context those children hand down — Phase 6.2, one
    step of :func:`_stamp_finished_tree`.

    ``emoji_kind`` (precedence heading > text > alone):
      * ``heading`` — an EMOJI under a ``heading{n}``-typed node: the
        heading's *text* element (or the subtree the element pass splits it
        into, which keeps the ``heading{n}`` label). NOT merely inside a
        heading *section* (``heading_group`` container) — that section owns
        all the body content under the heading, which are ordinary emojis.
      * ``text``    — an EMOJI whose CONTAINER styles it as text: a KEY, or
        a table cell. It draws at the surrounding text size from
        ``## Emoji styles > ### Text``, like the key or cell it belongs to.
      * ``alone``   — anything else: an ELEMENT, drawn as the
        ``### Primary`` badge with its wrapper's variant.

    **An EMOJI leaf exists only because the element pass peeled it, and it
    peels only when the author made it an element** — it owns the line, it
    is one of a sequenced run, or it is explicitly separated. So the node's
    mere existence is the decision, exactly as for a chip and a button: the same ``⭐`` that becomes a badge in ``⭐ - Popular`` stays
    an inline glyph in ``⭐ Popular``, where it is never a node at all and
    the text painter draws it from the same ``### Text`` block.

    ``emoji_index`` is the emoji's position among its EMOJI siblings, so the
    renderer can cycle a per-source Icon color array across sibling emojis.
    Computed once here from the final tree; persisted via to_dict.
    Time: O(K), Space: O(depth).
    """
    # Context the CHILDREN inherit. Heading context is the heading *text*
    # node (type ``heading{n}``), NOT the heading_group *section* container
    # (which owns unrelated body content).
    child_in_heading = in_heading or node.type.startswith("heading")
    # Containers that style their content as text rather than letting it be
    # an element: a K-V key (## Text Styles > Keys) and a table cell.
    text_context = node.type == NodeType.KEY or node.table_role is not None
    emoji_ordinal = 0
    for child in node.children:
        if child.type == NodeType.EMOJI:
            child.emoji_index = emoji_ordinal
            emoji_ordinal += 1
            if child_in_heading:
                child.emoji_kind = "heading"
            elif text_context:
                child.emoji_kind = "text"
            else:
                child.emoji_kind = "alone"
            # An emoji whose direct parent is a KEY is part of that key —
            # the renderer styles it with the Keys text style.
            if node.type == NodeType.KEY:
                child.in_key = True
    return child_in_heading


def _rotation_channel(node: "MarkdownGroupNode") -> str | None:
    """The color-rotation cycle *node* takes part in, or None.

    A channel is one THEME.md color list: a heading level's section fill, a
    card fill, an emoji/link/chip variant's fill, or a named image placeholder's. Every node belongs to at
    most one, which is why a single ``rotation_index`` per node is enough.
    A heading section wins over the card flag — a node can be both.
    """
    if node.heading_group:
        return f"section:{node.heading_level}"
    if kind := STRUCTURAL_BACKGROUND_KINDS.get(node.type):
        return f"structural:{kind}"
    if node.type == NodeType.EMOJI:
        return f"emoji:{node.emoji_variant or 'primary'}"
    if node.type == NodeType.LINK:
        return f"link:{_classify_link_content(node.content)[0] or 'primary'}"
    if node.type == NodeType.INLINE_CODE:
        return f"chip:{node.code_variant or 'primary'}"
    if node.type == NodeType.IMAGE and (ref := placeholder_ref(node.content or "")):
        return f"placeholder:{ref[0]}"  # each placeholder its own cycle (ADR-406)
    if node.glued_content_group:
        return "card"
    return None


_TEXT_STYLE_SURFACES = {
    NodeType.IMAGE_CARD.value: ("image_cards",),
    NodeType.LIST_ITEM.value: ("unordered_lists",),
    NodeType.TASK_OPEN.value: ("unordered_lists", "task_lists"),
    NodeType.TASK_DONE.value: ("unordered_lists", "task_lists"),
    NodeType.ORDERED_ITEM.value: ("numbered_lists",),
    NodeType.BLOCKQUOTE.value: ("quotes",),
}


def _text_style_chain(
    node: "MarkdownGroupNode", chain: tuple[str, ...]
) -> tuple[str, ...]:
    """Stamp the authored styling scopes that enclose *node*, and return them
    for its children — Phase 6.245, one step of :func:`_stamp_finished_tree`.

    The ordering is the cascade: Root, heading levels (and an optional fixed
    style), then structural surfaces such as image cards, lists and quotes.
    Task items intentionally receive Unordered Lists before Task Lists, making
    the latter the more specific per-property override.
    """
    current = chain
    if node.heading_group and node.heading_level:
        current += (f"heading:{node.heading_level}",)
        if node.fixed_style_key:
            current += (f"fixed:{node.fixed_style_key}",)
    for scope in _TEXT_STYLE_SURFACES.get(node.type, ()):
        if scope not in current:
            current += (scope,)
    node.text_style_chain = current
    return current


def _stamp_finished_tree(
    node: "MarkdownGroupNode",
    in_glued: bool = False,
    in_heading: bool = False,
    emoji_in_heading: bool = False,
    section_key: str | None = None,
    chain: tuple[str, ...] = ("root",),
) -> None:
    """Phases 6.15–6.245: the stamps on the finished tree, in ONE pre-order walk.

    None reads what another writes — 6.15 writes ``glued_content_group``, 6.17
    ``content``, 6.2 fields on the node's EMOJI children, 6.24
    ``section_style_key``, 6.245 ``text_style_chain`` — and each reads only its
    own node plus the context its ancestors hand down. So doing all five at
    every node leaves exactly the tree five separate walks would.

    Rotation (6.25) cannot join: it stamps a CHILD's slot from that child's
    glue flag before the child is visited, so it needs 6.15 finished first.

    "Inside a heading" is carried twice on purpose: glue tests ``heading{N}``
    with a regex, emoji kinds with a prefix. They agree on every type the
    grouper mints (``heading1``–``heading6``); carrying both keeps the fusion
    exact by construction rather than by that argument.
    """
    # 6.15 — one glue per STACKED block.
    child_glued, child_in_heading = _glue_stacked_block(node, in_glued, in_heading)
    # 6.18 — a heading written inside another block keeps its level, not its marker,
    # so no later stage parses it. Code is literal; ``\# x`` (6.17 not yet run) is text.
    if (
        node.content
        and not node.children
        and node.type not in (NodeType.CODE_BLOCK, NodeType.INLINE_CODE)
        and (m := _ATX_PREFIX_RE.match(node.content))
    ):
        node.atx_level = len(m.group(1))
        edit_content(node, [(0, m.end(), "")])
    # 6.17 — drop the separator backslashes. They were kept through the
    # splitting phases so every scan could see them (_make_is_safe); nothing
    # can split any more, so from here they are debris that would be drawn,
    # and no later pass can reintroduce a split at a character an author
    # protected. Fingerprints (6.5) read the resolved text. The tiers and
    # displays (6.055 / 6.06) run before this, harmlessly.
    # The quotes of a declined element ride along on the same rule: a quote pair
    # around a bare element is what kept it from being peeled, so consuming it
    # any earlier would hand the element straight back to the peel.
    if node.content:
        edit_content(node, late_escape_edits(node))
        edit_content(node, quoted_element_edits(node.content))
    # 6.2 — each EMOJI child's render role and sibling ordinal.
    child_emoji_in_heading = _stamp_emoji_children(node, emoji_in_heading)
    # 6.24 — carry a fixed heading style through exactly the section it owns.
    # Every heading boundary resets the context; an ordinary nested heading
    # must not accidentally keep its parent's standalone fixed style.
    if node.heading_group:
        section_key = node.fixed_style_key
    node.section_style_key = section_key
    # 6.245 — the styling scopes enclosing this node.
    chain = _text_style_chain(node, chain)
    # 6.246 — a ` | ` run of one choice's options, drawn as one control (ADR-405).
    node.segmented_run = is_segmented_run(node)
    for child in node.children:
        _stamp_finished_tree(
            child,
            child_glued,
            child_in_heading,
            child_emoji_in_heading,
            section_key,
            chain,
        )


def _stamp_leaf_kinds(root: "MarkdownGroupNode | None") -> None:
    """Stamp ``pure_element`` / ``key_side`` on every group and
    ``top_heading_level`` on *root*, in one post-order walk.

    The generator asks these of a node many times per layout, and a layout is
    rebuilt on every resize; the answer depends only on the finished tree.
    """
    if root is not None:
        root.top_heading_level = stamp_group_kinds(root)[3]


def stamp_group_kinds(
    node: "MarkdownGroupNode",
) -> tuple[bool, bool, bool, int | None]:
    """Stamp *node* and the groups under it; return (has a leaf, every leaf a
    pill, every leaf a key, shallowest section level below it). Also how the
    generator stamps the one group it builds itself, a ``:::`` column stack."""
    found, element, key, top = False, True, True, None
    for child in node.children:
        c_top = None
        if child.children:
            c_found, c_element, c_key, c_top = stamp_group_kinds(child)
            found, element, key = found or c_found, element and c_element, key and c_key
        elif child.content:
            found = True
            element = element and child.type in ELEMENT_LEAF_TYPES
            key = key and child.type == NodeType.KEY
        if child.heading_group and child.heading_level is not None:
            c_top = (
                child.heading_level
                if c_top is None
                else min(c_top, child.heading_level)
            )
        if c_top is not None:
            top = c_top if top is None else min(top, c_top)
    node.pure_element = found and element
    node.key_side = found and key
    return found, element, key, top


def _lend_slot_to_title(node: "MarkdownGroupNode", level: int, slot: int) -> None:
    """Give a heading section's own title text the section's rotation slot.

    Without this the title would be alone in its section's scope and always
    land on color 0, so ``Background color:`` on ``### Heading 3`` and ``Font
    color:`` on ``Heading3`` could never pick the same hue. A split heading
    line leaves several ``heading{N}`` pieces (each with a source_line_id) —
    they all belong to the one title, so they all take the slot. The walk
    stops at a nested section, whose title owns a slot of its own.
    """
    if node.type == f"heading{level}":
        node.rotation_index = slot
    for child in node.children:
        if child.heading_group:
            continue
        _lend_slot_to_title(child, level, slot)


def _annotate_rotation_indices(
    node: "MarkdownGroupNode",
    scope: dict[str, int] | None = None,
    chain: tuple[int | str, ...] = (),
    path: tuple[int, ...] = (),
) -> None:
    """Stamp every node with its slot in its section's color cycle.

    One counter per (channel, enclosing section). A heading section takes its
    own slot from the ENCLOSING scope, then opens a fresh one for its
    children — that is the reset the references need: sample-4's three
    ``### `` cards cycle 0,1,2 under "Upcoming meetups" and the emoji badges
    under the next ``## `` restart at 0 instead of continuing at 3.

    Everything else (list items, glued groups, line splits) is transparent:
    it passes the scope straight through, so six emojis in six sibling list
    items share one cycle rather than each being alone at index 0.

    Time: O(K). Space: O(depth * channels).
    """
    if scope is None:
        scope = {}
    for child in node.children:
        # A node's chain is its ANCESTOR sections — its own level is not in
        # it, because a level's gate governs what sits inside that level.
        child.rotation_chain = chain
        child.rotation_path = path
        channel = _rotation_channel(child)
        if channel is not None:
            child.rotation_index = scope.get(channel, 0)
            scope[channel] = child.rotation_index + 1
        if child.heading_group and child.fixed_style_key:
            fixed_channel = f"fixed:{child.fixed_style_key}"
            child.fixed_rotation_index = scope.get(fixed_channel, 0)
            scope[fixed_channel] = child.fixed_rotation_index + 1
        if child.heading_group:
            _lend_slot_to_title(child, child.heading_level or 0, child.rotation_index)
            if child.fixed_style_key:
                _lend_fixed_slot_to_title(child, child.fixed_rotation_index)
            # The section joins its children's ancestry: its level goes on
            # the chain, the slot it just drew goes on the path, so anything
            # inside can borrow that slot by naming this level.
            _annotate_rotation_indices(
                child,
                {},
                chain
                + (
                    (
                        f"fixed:{child.fixed_style_key}|"
                        f"{child.heading_level or 0}|{child.fixed_rotation_index}"
                    )
                    if child.fixed_style_key
                    else child.heading_level or 0,
                ),
                path + (child.rotation_index,),
            )
        else:
            _annotate_rotation_indices(child, scope, chain, path)


def _lend_fixed_slot_to_title(node: "MarkdownGroupNode", slot: int) -> None:
    """Parallel to _lend_slot_to_title for a matched fixed-style family."""
    if node.type.startswith("heading"):
        node.fixed_rotation_index = slot
    for child in node.children:
        if child.heading_group:
            continue
        _lend_fixed_slot_to_title(child, slot)


def _annotate_data_points_walk(
    node: "MarkdownGroupNode",
    detector: DataPointDetector,
) -> None:
    """Phase 3: detect data points on every node that has content,
    regardless of label.  This gives the kv walk and the later phases access to
    protected ranges so data-point regions (times, prices, URLs …) are
    never incorrectly split at a colon or separator.

    Unlike Phase 4+5 annotation (which filters by label to avoid wasting
    work on structural nodes), Phase 3 must cover all labels because
    headings, bold spans, etc. may still hold unsplit content at this point.

    Time: O(K + N), Space: O(R) where R = total data points found.
    """
    for child in node.children:
        _annotate_data_points_walk(child, detector)
    if node.content:
        node.data_points = _detect_through_markers(node.content, detector)
        dp_ranges = [(dp["start"], dp["end"]) for dp in node.data_points]
        node.paren_quote_ranges = _merge_pq(
            _bracket_quote_ranges(node.content, dp_ranges)
        )


def _detect_through_markers(content: str, detector) -> list[dict]:
    """Data points of *content*, detected as if the author's markers and
    escapes were not in the way.

    Two things sit between the characters a pattern needs to see:

    * a backslash — ``8:00 AM \\- 9:00 AM`` would stop being a time range
      purely because the author asked its dash not to split;
    * a marker UNDERSCORE — and this one is not merely a missed detection.
      ``_`` is a regex WORD character, so a ``\\b``-anchored pattern cannot
      match at ``__8``: ``__8:00 AM - 9:00 AM__`` comes back as ``00`` and
      ``9:00 `` instead of the range. Those bogus ranges then leave the
      ``8:`` colon unprotected, ``_plain_colon_kv`` reads it as a key-value
      colon, and the time is cut in half. ``*`` and ``~`` are not word
      characters, which is why bold never had this problem.

    Detection therefore runs on the stripped text and every offset is mapped
    back — the ranges stay valid against the real content, which is what
    :meth:`_protected_ranges` hands the scans.

    An INTRAWORD underscore is not a marker and stays: ``snake_case`` and
    ``message_schemas`` are identifiers, exactly the rule
    :meth:`_marker_runs` already applies.
    """
    if "\\" not in content and "_" not in content:
        return detector.detect_pipeline(content)
    clean_chars: list[str] = []
    back: list[int] = []  # clean index -> index in *content*
    i = 0
    n = len(content)
    while i < n:
        if content[i] == "\\" and i + 1 < n and content[i + 1] in ESCAPABLE_SEPARATORS:
            i += 1  # drop the backslash, keep what it protects
            continue
        if content[i] == "_":
            j = i
            while j < n and content[j] == "_":
                j += 1
            # ONLY a run that OPENS or CLOSES a wrap — whitespace (or the
            # string edge) on its outer side. That is what a tier wrapper
            # looks like, at the start of the piece or in the middle of a
            # line, and it is what an identifier never looks like: the
            # underscores in ``snake_case`` and in a URL's ``_-_`` have
            # non-space on both sides, and eating those would rewrite real
            # content (``Van_Gogh_-_Starry_Night``).
            opens = i == 0 or content[i - 1].isspace()
            closes = j == n or content[j].isspace()
            if opens or closes:
                i = j
                continue
        clean_chars.append(content[i])
        back.append(i)
        i += 1
    dps = detector.detect_pipeline("".join(clean_chars))
    for dp in dps:
        # The END is exclusive, so it maps through the LAST character the
        # match covers, not through the next one — otherwise a range that
        # ends where a marker run begins would swallow that run
        # (``__8:00 AM - 9:00 AM__`` covering its own trailing ``__``).
        start, end = dp["start"], dp["end"]
        dp["start"] = back[start] if start < len(back) else n
        dp["end"] = back[end - 1] + 1 if end > start else dp["start"]
        # ...and the matched text is the REAL span, never the stripped one.
        dp["matched"] = content[dp["start"] : dp["end"]]
    escaped = _value_escape_spans(content)
    if escaped:
        # A link is an element, not a reading: an escape in its label declines
        # what the label's words would read as, never the link, whose label is
        # never divided (``[Plan a 5\-day itinerary](…)`` stays a button).
        dps = [
            dp
            for dp in dps
            if dp["type"] == DataPointType.LINK
            or not any(dp["start"] < e and s < dp["end"] for s, e in escaped)
        ]
    return dps
