"""Turning a split result into children, and the housekeeping that follows.

A splitter returns a list of ``(label, text)`` pieces. Something then has to
make those pieces real: build the child nodes, hand each one the data points and
paren/quote ranges that fall inside it — with every offset rebased — give them
the parent's glue, and decide whether the parent becomes a container or is
relabelled in place. That is this module, and it is deliberately ONE place: the
five splitters that feed it would otherwise each re-derive the same arithmetic,
which is the divergence ADR-400 exists to prevent.

The two housekeeping helpers belong here for the same reason. ``_partition_data_points``
is the offset arithmetic itself; ``_flatten_empty_text`` clears the empty wrappers
a split leaves behind. Both are called from all over the grouper, but they exist
BECAUSE of splitting, and this is where their rules are written down.

Minting is explicit: anything that can earn a fresh glued-segment id takes an
:class:`~md2ui.pipeline.grouper_ids.IdMint` and is handed one by its caller. No
function here reaches for state of its own.
"""

from md2ui.pipeline.grouper_split_criteria import Criterion
from md2ui.pipeline.grouper_ids import IdMint, _inherit_glue
from md2ui.pipeline.grouper_inline_marks import _SPLIT_WRAP_CHARS, _detect_style_wrap
from md2ui.pipeline.grouper_node_reads import _classification_text
from md2ui.pipeline.grouper_ranges import _partition_ranges
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline import grouper_value_splits

# Every marker a split can have ADDED to a piece — what _partition_data_points
# strips back off when it has to relocate a child in its parent's raw content.
# Longest-first, because that loop breaks on its first hit.
_RECOVERY_MARKERS = ("***", "___", "~~", "**", "__", "*", "_", "`")

# Labels a node KEEPS when a split leaves exactly one piece, instead of being
# relabelled into that piece. Each of these is a container whose type IS its
# role: the bullet of a list item, the ordinal of a numbered one, a quote's bar,
# a table cell's column, a K-V value's half of the pair. Relabelling one deletes
# that role silently: `- X` would come out as a bare EMOJI with no list item
# around it, `1. X` would lose its number, and a lone-emoji table cell the cell
# its column is measured from.
#
# TEXT and SEGMENT are deliberately absent: they carry no role, and relabelling
# them in place is the whole point of the single-piece path -- a line that is
# nothing but a chip SHOULD become that chip rather than a wrapper around it.
#
# The document ROOT carries the largest role of the lot. Relabelled, a document
# that is nothing but one element would BECOME that element, a root childless
# and a leaf at once, which the generator reads as an empty document: a blank
# page, and for ``[Open](agent:x)`` the only action in it gone with the page.
_LABEL_IS_A_ROLE = (
    "root",
    NodeType.VALUE,
    NodeType.LIST_ITEM,
    NodeType.ORDERED_ITEM,
    NodeType.BLOCKQUOTE,
    NodeType.TABLE_CELL,
)


def _whole_annotate_only_piece(
    node: MarkdownGroupNode, data_points: list[dict]
) -> list[tuple[str, str]] | None:
    """Keep a role's one-child shape when a whole value is annotation-only.

    ``Key: $50/hour`` is ``VALUE(TEXT)``: collapsing the role into a contentful
    VALUE would change fingerprints, word-count clusters, and potentially
    layout. This is not a value split: it only preserves an authored role and
    its one child.

    An authored separator segment is the complementary case: ``Name |
    €180-200M`` ends in a TEXT leaf. Leaving an annotation-only RANGE as
    SEGMENT would change its hashes and make it join the adjacent segment's
    layout run, so one TEXT piece relabels that leaf in place.

    The exact whole-content guard is deliberate: it preserves only the
    single-child shape. A span that exactly fills a style wrapper's inner range
    is the same case: ``___256k___`` becomes content ``256k`` later, while its
    detector offsets remain relative to the wrapped source. Partial or multiple
    spans are not covered.
    """
    if node.type not in (*_LABEL_IS_A_ROLE, NodeType.SEGMENT) or not (
        _is_whole_annotate_only_value(node, data_points)
    ):
        return None
    return [(NodeType.TEXT, node.content)]


def _is_whole_annotate_only_value(
    node: MarkdownGroupNode, data_points: list[dict]
) -> bool:
    """Whether *node* is exactly one value this pass does not extract."""
    if node.children or len(data_points) != 1:
        return False
    point = data_points[0]
    if point["type"] in grouper_value_splits._BOUNDARY_DP_TYPES:
        return False
    exact_offsets = (point["start"], point["end"]) == (0, len(node.content))
    plain_whole = node.content == node.content.strip() and exact_offsets
    lead_offset = len(node.content) - len(node.content.lstrip())
    style_wrap = _detect_style_wrap(
        node.content, lead_offset, len(node.content.rstrip()), _SPLIT_WRAP_CHARS
    )
    wrapped_whole = (
        style_wrap is not None and (point["start"], point["end"]) == style_wrap[1:]
    )
    return plain_whole or wrapped_whole


def _flatten_empty_text(node: MarkdownGroupNode) -> None:
    """Unwrap text children that have no content (empty wrappers).

    Replaces each contentless text node with its own children, in place.

    Time: O(K), Space: O(K) (intermediate list).
    """
    new_children: list[MarkdownGroupNode] = []
    for c in node.children:
        if c.type == NodeType.TEXT and not c.content and c.children:
            new_children.extend(c.children)
        else:
            new_children.append(c)
    node.children = new_children


def _hand_data_points(
    node: MarkdownGroupNode, children: list[MarkdownGroupNode], pieces: list[str]
) -> None:
    """Give each of *children* the data points inside its piece of *node*'s
    content, and leave *node* none: it is about to become their empty
    container, and a data point it kept would index text it no longer has."""
    labelled = [(None, piece) for piece in pieces]
    shares = _partition_data_points(node.content, node.data_points, labelled)
    for child, share in zip(children, shares):
        child.data_points = share
    node.data_points = []


def _partition_data_points(
    parent_content: str,
    data_points: list[dict],
    result: list[tuple],
) -> list[list[dict]]:
    """Partition parent data_points into per-child lists with adjusted indices.

    Finds each child's text position in parent_content using a sequential
    scan (exploiting document order), then assigns each data point to the
    child whose range fully contains it, remapping start/end to child-local
    coordinates.  Data points that span a split boundary are silently
    dropped (compact patterns make this exceedingly rare in practice).

    Time:  O(C + R) where C = len(parent_content), R = len(data_points).
    Space: O(R).
    """
    if not data_points:
        return [[] for _ in result]

    # Locate each child's [start, end) range in the parent content along
    # with a leading_offset: when the leading-marker fallback succeeds, the
    # child's text has extra marker chars at the front that aren't in the
    # parent, so DP positions need shifting right by that many chars when
    # mapped into child-local coordinates.
    child_ranges: list[tuple[int, int, int] | None] = []
    search_from = 0
    for _label, text in result:
        if not text:
            child_ranges.append(None)
            continue
        leading_offset = 0
        idx = parent_content.find(text, search_from)
        if idx == -1:
            stripped = text.strip()
            idx = parent_content.find(stripped, search_from)
            length = len(stripped)
        else:
            length = len(text)
        if idx == -1:
            # Text may have had boundary markers added by _balance_markdown_markers
            # or wrap_marker; try stripping them to find the original span.
            # Longest-first, and the same tuple as _extract_key_from_prefix:
            # both the balancer and the wrap propagation can add ``~~`` and
            # the triples, so a list of only doubles/singles would fail to
            # relocate those children and silently drop their datapoints.
            core = text.strip()
            for _m in _RECOVERY_MARKERS:
                if core.endswith(_m):
                    candidate = core[: -len(_m)]
                    i2 = parent_content.find(candidate, search_from)
                    if i2 >= 0:
                        idx, length = i2, len(candidate)
                    break
            if idx == -1:
                for _m in _RECOVERY_MARKERS:
                    if core.startswith(_m):
                        candidate = core[len(_m) :]
                        i2 = parent_content.find(candidate, search_from)
                        if i2 >= 0:
                            idx, length = i2, len(candidate)
                            leading_offset = len(_m)
                        break
        if idx >= 0:
            child_ranges.append((idx, idx + length, leading_offset))
            # Advance past the matched span so a later child with identical
            # text (e.g. 4 identical links separated by " - ") finds its
            # own occurrence rather than re-matching the previous one.
            search_from = idx + length
        else:
            child_ranges.append(None)

    # Assign each data point to the first child that fully contains it.
    partitioned: list[list[dict]] = [[] for _ in result]
    for dp in data_points:
        dp_start, dp_end = dp["start"], dp["end"]
        for i, r in enumerate(child_ranges):
            if r is None:
                continue
            c_start, c_end, lead_off = r
            if dp_start >= c_start and dp_end <= c_end:
                adjusted = dict(dp)
                adjusted["start"] = dp_start - c_start + lead_off
                adjusted["end"] = dp_end - c_start + lead_off
                partitioned[i].append(adjusted)
                break

    return partitioned


def _apply_all_datapoints_to_node(
    node: "MarkdownGroupNode", criteria, ids: IdMint
) -> None:
    """Apply the unified data-point split to a single node without recursion.

    A value never divides a line (ADR-205); what remains is the relabel of a
    node that is exactly one whole value.  Skips nodes that are not eligible
    (image / link / emoji / datapoint labels, prose classification, or no
    qualifying data points), and refuses to CUT a line whose author escaped
    a separator.
    The split criteria are cached on the node when not already set.
    """
    if not node.content or node.type in (
        NodeType.IMAGE,
        NodeType.LINK,
        NodeType.EMOJI,
        NodeType.DATAPOINT,
    ):
        return

    if criteria is not None and node.applicable is None:
        node.applicable = criteria.applicable(
            _classification_text(node.content, node.data_points)
        )

    # Filter out data points that fall inside a paren/quote range so that
    # content inside () or "" is not split out as a separate node.
    # Invariant: `effective_dps` only gates the relabel decision. The full
    # `node.data_points` list is still used by _partition_data_points
    # below, so dps inside protected spans round-trip onto whichever leaf
    # ends up containing the protected substring — they are preserved for
    # post-processing, just not extracted as DATAPOINT nodes.
    node_pq = node.paren_quote_ranges
    if node_pq:
        effective_dps = [
            dp
            for dp in node.data_points
            if not any(ps <= dp["start"] and dp["end"] <= pe for ps, pe in node_pq)
        ]
    else:
        effective_dps = node.data_points

    # A value never divides a line (ADR-205). The one thing left here is the
    # relabel for a node that is exactly one whole value. A value outside
    # prose is structured, so the relabel follows the KEY_VALUE answer.
    if not _is_whole_annotate_only_value(node, effective_dps):
        return
    if node.applicable is not None and Criterion.KEY_VALUE not in node.applicable:
        return
    result = _whole_annotate_only_piece(node, effective_dps)
    if result is None:
        return
    _apply_split_result(node, result, node_pq, ids)


def _apply_split_result(
    node: "MarkdownGroupNode",
    result: list[tuple],
    node_pq: list[tuple[int, int]],
    ids: IdMint,
) -> None:
    """Replace ``node.content`` with the ``(label, text)`` split *result*,
    preserving the node's semantic label and re-homing its annotations.

    Shared by the gated structural datapoint split
    (:meth:`_apply_all_datapoints_to_node`) and the final ungated boundary
    peel (:meth:`_peel_boundary_dps_walk`). A single whole-content dp is
    relabeled in place, EXCEPT where the label is itself a role
    (``_LABEL_IS_A_ROLE`` -- those keep it and take the piece as a child);
    otherwise children are created with ``data_points`` and
    ``paren_quote_ranges`` partitioned onto them. Only ``TEXT`` is promoted
    to ``GROUP``; every other label (``VALUE``, ``SEGMENT``, ``LIST_ITEM``,
    …) is retained.

    Every piece stays a FLAT peer in authored order — a peeled LINK is a
    piece of its line like any other element, which is what
    :meth:`_derive_line_split_groups` documents. Chips, links and emojis share
    one element path, so a link is never hoisted into its own wrapper: that
    would reorder the line.
    """
    if len(result) == 1 and not node.children and node.type not in _LABEL_IS_A_ROLE:
        piece = result[0]
        pair = [(piece[0], piece[1])]
        # The piece's text can be SHORTER than the node's content — a chip
        # drops its backticks, an emoji its wrapper — so any dp / pq range
        # riding on this node has to be re-based onto the stripped text or
        # it indexes past the end of what the node now holds.
        same_text = piece[1] == node.content
        dps = (
            list(node.data_points)
            if same_text
            else _partition_data_points(node.content, node.data_points, pair)[0]
        )
        pqs = (
            list(node_pq)
            if same_text
            else _partition_ranges(node.content, node_pq, pair)[0]
        )
        node.type, node.content = piece[0], piece[1]
        node.data_points = dps
        node.paren_quote_ranges = pqs
        _stamp_element_piece(node, piece)
        return
    new_children = _build_split_children(node, result, node_pq, ids)
    node.data_points = []
    if node.type == NodeType.TEXT:
        node.type = NodeType.GROUP
    node.children = new_children + node.children
    node.content = ""
    node.applicable = None


def _stamp_element_piece(node: "MarkdownGroupNode", piece: tuple) -> None:
    """Give an emoji or chip *node* what its split *piece* carried past the peel:
    the variant its wrapper selected, then whether ``~~`` muted it.
    Both wrappers are gone from ``content`` by now, so this is their only record.
    """
    if node.type not in (NodeType.EMOJI, NodeType.INLINE_CODE):
        return
    variant = piece[2] if len(piece) > 2 else None
    if variant is not None and node.type == NodeType.EMOJI:
        node.emoji_variant = variant
    elif variant is not None:
        node.code_variant = variant
    node.element_muted = bool(piece[3]) if len(piece) > 3 else False


def _build_split_children(
    node: "MarkdownGroupNode",
    result: list[tuple],
    node_pq: list[tuple[int, int]],
    ids: IdMint,
) -> list["MarkdownGroupNode"]:
    """Build child nodes from a split *result*, partitioning the parent's
    ``data_points`` and ``paren_quote_ranges`` onto them.

    A piece is ``(label, text)`` or, from the element pass
    (:meth:`_split_elements`), ``(label, text, variant)`` — the emphasis
    wrapper is consumed off an emoji's / chip's content when it is peeled,
    so the variant it selected has to travel with the piece or it is lost.
    It lands on the field that kind's renderer reads.

    Shared by :meth:`_apply_split_result` (in-place promotion of *node* to a
    container) and the leaf flat-splice in :meth:`_peel_boundary_dps_walk`
    (pieces returned to the parent instead of nested). Does not mutate *node*.
    """
    pairs = [(piece[0], piece[1]) for piece in result]
    new_children = [MarkdownGroupNode(type=lbl, content=txt) for lbl, txt in pairs]
    for child, piece in zip(new_children, result):
        _stamp_element_piece(child, piece)
    _inherit_glue(node, new_children, ids)
    if node.data_points:
        partitioned = _partition_data_points(node.content, node.data_points, pairs)
        for child, dps in zip(new_children, partitioned):
            child.data_points = dps
    if node_pq:
        pq_parts = _partition_ranges(node.content, node_pq, pairs)
        for child, cpq in zip(new_children, pq_parts):
            child.paren_quote_ranges = cpq
    return new_children
