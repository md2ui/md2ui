"""The separation walk: one depth-first pass that cuts a line into structure.

This is the phase everything else in the grouper was built for. It visits each
node once and decides, in a fixed order of precedence, how that line divides:
colon columns before bullets and rules, with springs before either. Each
decision then calls the module that owns it — the splitters for the
cut, ``grouper_split_apply`` for turning the pieces into children,
``grouper_node_reads`` for the questions it asks along the way.

**It is one unit.** ``_promote_align_regions`` calls the walk back, so the
recursion is genuinely mutual, and the walk itself is one long function whose
branches share local state throughout. It is over the default size budget on
purpose, with that reasoning recorded in ``budgets.txt``.

Minting is explicit: every function here takes an
:class:`~md2ui.pipeline.grouper_ids.IdMint` and passes it down. Nothing reaches
for state of its own.
"""

from md2ui.pipeline.grouper_spacers import take_edge_spacers
from md2ui.pipeline.grouper_split_criteria import Criterion
from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.grouper_annotate import _detect_through_markers
from md2ui.pipeline.grouper_content_edits import keep_content
from md2ui.pipeline.grouper_block_splits import (
    _BREAK_TYPES,
    _KEEP_WHEN_EMPTY,
)
from md2ui.pipeline.grouper_ids import IdMint, _inherit_glue
from md2ui.pipeline.grouper_node_reads import (
    _classification_text,
    _extract_key_from_prefix,
    _plain_colon_kv,
    _protected_ranges,
    _row_separator_chars,
)
from md2ui.pipeline.grouper_ranges import (
    _bracket_quote_ranges,
    _merge_pq,
    _partition_ranges,
)
from md2ui.pipeline.grouper_separator_splits import (
    _split_align_regions,
    _split_colon_columns,
    _split_separators,
)
from md2ui.pipeline.grouper_split_apply import (
    _apply_all_datapoints_to_node,
    _flatten_empty_text,
    _partition_data_points,
)
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.grouper_value_splits import _split_kv_styled


def _separate_structured_content_walk(
    node: "MarkdownGroupNode",
    detector: DataPointDetector,
    criteria,
    annotate_labels: set[str],
    ids: IdMint,
) -> None:
    """Single depth-first walk that combines:

    1. Data-point annotation (leaf nodes in *annotate_labels*)
    2. Structural splits     (spring, separator, colon column, key-value)
    3. Datapoint split       (on the line or on each piece it split into)

    Children created by a separator split get their key-value and datapoint
    passes immediately, so no second walk is needed.

    Time: O(K + N·log R), Space: O(N).
    """
    for child in list(node.children):
        _separate_structured_content_walk(
            child, detector, criteria, annotate_labels, ids
        )

    # Inline _prune_empty: drop children with no content and no children.
    # Horizontal rules are kept unconditionally (preserved for the renderer).
    node.children = [
        c
        for c in node.children
        if c.content or c.children or c.type in _KEEP_WHEN_EMPTY
    ]

    _flatten_empty_text(node)

    if not node.content:
        return

    # Step 1 — annotate
    if node.type in annotate_labels:
        node.data_points = _detect_through_markers(node.content, detector)

    # Steps 2-3 — separator then emoji (both skip image / link nodes, and
    # BREAK leaves for the same reason: their content is the author's
    # SPELLING, not content. ``- - -`` is a rule whose own characters read
    # as a separator split, so without this it comes back as two ``-``
    # segments and the rule is never painted.)
    if node.type in (NodeType.IMAGE, NodeType.LINK) or (node.type in _BREAK_TYPES):
        return

    # A spacer at either end of the line is space around it, not a cut: take
    # it off and record it, before anything reads the line (ADR-203).
    lead, trail, rest = take_edge_spacers(node.content)
    if lead or trail:
        keep_content(node, rest)
        node.spacer_lead = lead or node.spacer_lead
        node.spacer_trail = trail or node.spacer_trail

    # A line ending in a colon (`Panelists:`, `**Bold:**`) is drawn as written:
    # no colon is stripped (ADR-205), and with nothing after it there is no
    # value to pair, so it is an ordinary line.
    stripped = node.content.rstrip()
    if stripped.endswith(":") or _extract_key_from_prefix(stripped) is not None:
        return

    pq = node.paren_quote_ranges

    # Boundary emoji/link peeling is not done here — it runs in the final
    # ungated pass (_peel_boundary_dps_walk) after all structural separation.
    # This walk does structural splits only: separators use their rule-only
    # criterion; KV and inner datapoints use their split-criteria gates.

    # True when key-value criteria decline this line. Separators have their own
    # rule-only criterion inside the scanner and are not gated by it.
    prose = False
    key_value_applicable = True

    # Cache criteria for this node's de-boundary'd classification text; every
    # node-local consumer asks that same text. The VALUE re-check below asks a
    # different substring directly, so it deliberately bypasses this cache.
    if criteria is not None:
        applicable = (
            node.applicable
            if node.applicable is not None
            else criteria.applicable(
                _classification_text(node.content, node.data_points)
            )
        )
        node.applicable = applicable
        key_value_applicable = Criterion.KEY_VALUE in applicable
        if not key_value_applicable:
            prose = True
            # KEY_VALUE keeps its own gates below. The ELEMENT pass
            # (_peel_boundary_dps_walk → _split_elements) runs
            # unconditionally afterwards and is what decides whether this
            # node's emoji / links / backtick spans peel — its own gate,
            # not the split criteria.
            #
            # ONE exception: a SPRING. A spring is authored, not inferred, so
            # it springs on any line, prose or not: a comma or a sentence must
            # not decide whether `A ... B` aligns, and gating it would leave
            # the literal `... ` in the rendered text. An
            # author who means an ellipsis writes `\...` or drops the space
            # ("He paused... unsure"). Each region is then walked as its own
            # line, so the prose reading still applies inside a region.
            if _promote_align_regions(
                node,
                sorted(_protected_ranges(node)),
                detector,
                criteria,
                annotate_labels,
                ids,
            ):
                return

    # Build protected ranges: dp ranges outside pq + pq ranges (non-overlapping).
    # dp ranges that fall entirely inside a pq range are omitted — they are
    # already covered by the pq range, and including them would create overlaps
    # that break the binary-search in is_safe().
    if node.data_points or pq:
        dp_ranges = [(dp["start"], dp["end"]) for dp in node.data_points]
        if pq:
            protected = [
                r
                for r in dp_ranges
                if not any(ps <= r[0] and r[1] <= pe for ps, pe in pq)
            ] + pq
        else:
            protected = dp_ranges
    else:
        protected = []

    # Sort the protected ranges once and share them across every separator
    # scan below (split + tie-break), instead of re-sorting per helper.
    sorted_protected = sorted(protected)

    # Step 1.9 — a spring splits the line into aligned REGIONS, ahead of the
    # whole separator / key-value / colon-column chain. Each region is then
    # walked as an ordinary line, so that chain needs no knowledge of springs
    # and its precedence rules are untouched. `Key: ... Value` is a spring like
    # any other: two regions, the colon kept in the first (ADR-205).
    if not prose and _promote_align_regions(
        node, sorted_protected, detector, criteria, annotate_labels, ids
    ):
        return

    # Step 2 — separator split. A separator always outranks a key-value colon
    # (ADR-205): `Key: A | B` divides at its pipe as `Key\: A | B` does, and
    # each piece may then pair, so a pair that goes back to its line is the
    # piece it was cut from.
    sep_result = _split_separators(node.content, sorted_protected)
    if sep_result is not None:
        # Record the character the split ate, so ## Separators can have it
        # drawn back between the pieces. Display-only — nothing structural
        # reads it, and it is set before the children so a later collapse
        # carries it with them.
        node.separator_chars = _row_separator_chars(node.content, sorted_protected)
        new_children = [
            MarkdownGroupNode(type=lbl, content=txt) for lbl, txt in sep_result
        ]
        _inherit_glue(node, new_children, ids)
        if node.data_points:
            partitioned = _partition_data_points(
                node.content, node.data_points, sep_result
            )
            for child, dps in zip(new_children, partitioned):
                child.data_points = dps
            node.data_points = []
        if pq:
            pq_sep = _partition_ranges(node.content, pq, sep_result)
            for child, cpq in zip(new_children, pq_sep):
                child.paren_quote_ranges = cpq
        if node.type == NodeType.TEXT:
            node.type = NodeType.GROUP
        node.children = new_children + node.children
        node.content = ""
        node.applicable = None
        # Step 2.5 — per-segment KV promotion (before emoji)
        for child in new_children:
            child_protected = _protected_ranges(child)
            # A spaced colon inside a segment is a COLUMN split: it binds
            # tighter than the separator that produced this segment, so
            # "92 : days - ⬇" is two columns and the first one stacks.
            if _promote_colon_columns(child, child_protected, criteria, ids):
                continue
            kv = _split_kv_styled(child.content, child_protected)
            if kv is None:
                kv = _plain_colon_kv(child.content, child_protected)
            if kv is not None:
                child.pair_source = (child.type, child.content)
                child.type = NodeType.KEY_VALUE
                child.children = [
                    MarkdownGroupNode(type=lbl, content=txt) for lbl, txt in kv
                ]
                if child.data_points:
                    kv_partitioned = _partition_data_points(
                        child.content, child.data_points, kv
                    )
                    for sub, dps in zip(child.children, kv_partitioned):
                        sub.data_points = dps
                    child.data_points = []
                if child.paren_quote_ranges:
                    pq_kv = _partition_ranges(
                        child.content, child.paren_quote_ranges, kv
                    )
                    for sub, spq in zip(child.children, pq_kv):
                        sub.paren_quote_ranges = spq
                    child.paren_quote_ranges = []
                # Glue before the VALUE datapoint split (copy-only: the
                # segment already carries an id) so the inner split
                # inherits instead of minting a nested segment.
                _inherit_glue(child, child.children, ids)
                for sub in child.children:
                    if sub.type == NodeType.VALUE:
                        _apply_all_datapoints_to_node(sub, criteria, ids)
                child.content = ""
        # Step 3 — unified datapoint split (emoji at boundary, all others anywhere)
        for child in new_children:
            _apply_all_datapoints_to_node(child, criteria, ids)
            # Step 4 — boundary inline-code peel on the segment subtree.
            # Runs after the datapoint pass so any DP-extracted children
            # (TEXT remainders) also get a chance to be peeled.
    else:
        # Step 2.4 — spaced-colon COLUMN split. Reached only when neither a
        # separator nor a KV colon claimed the line, which IS the precedence
        # rule: "|" / "-" split into columns first, a colon stacks within
        # one. ("A : B" arrives here directly — it has no separator, and a
        # spaced colon is not a KV colon.)
        columns = _promote_colon_columns(node, protected, criteria, ids)
        # Step 2.5 — KV detection before datapoint split
        kv = (
            None
            if columns or not key_value_applicable
            else (
                _split_kv_styled(node.content, protected)
                or _plain_colon_kv(node.content, protected)
            )
        )
        if kv is not None:
            kv_node = MarkdownGroupNode(type=NodeType.KEY_VALUE, content="")
            kv_node.glued_content_id = node.glued_content_id
            kv_node.pair_source = (NodeType.TEXT, node.content)
            kv_node.children = [
                MarkdownGroupNode(type=lbl, content=txt) for lbl, txt in kv
            ]
            if node.data_points:
                kv_partitioned = _partition_data_points(
                    node.content, node.data_points, kv
                )
                for child, dps in zip(kv_node.children, kv_partitioned):
                    child.data_points = dps
                node.data_points = []
            if pq:
                pq_kv = _partition_ranges(node.content, pq, kv)
                for child, cpq in zip(kv_node.children, pq_kv):
                    child.paren_quote_ranges = cpq
            # Glue before the VALUE datapoint split: a lone line mints one
            # shared id for KEY+VALUE so the inner split inherits instead
            # of minting a nested segment.
            _inherit_glue(node, kv_node.children, ids)
            for child in kv_node.children:
                if child.type == NodeType.VALUE:
                    _apply_all_datapoints_to_node(child, criteria, ids)
            if node.type == NodeType.TEXT:
                node.type = NodeType.GROUP
            node.children = [kv_node] + node.children
            node.content = ""
            node.applicable = None
        # Step 3 — unified datapoint split (KV-promoted nodes have no content → no-op)
        _apply_all_datapoints_to_node(node, criteria, ids)


def _promote_colon_columns(
    node: "MarkdownGroupNode",
    protected: list[tuple[int, int]],
    criteria,
    ids: IdMint,
) -> bool:
    """Split *node*'s content at spaced colons into stacked children.

    Mirrors the KV promotion beside it — same dp / paren-quote partitioning,
    same glue inheritance, same TEXT→GROUP retype — and additionally marks
    the container ``column_split_group`` so the layout stacks the pieces
    instead of flowing them along their shared source line.

    Returns True when it fired, in which case the caller must not also try
    the KV split: the colon it would have used is this one.
    """
    cols = _split_colon_columns(node.content, sorted(protected))
    if cols is None:
        return False

    kids = [MarkdownGroupNode(type=lbl, content=txt) for lbl, txt in cols]
    if node.data_points:
        for kid, dps in zip(
            kids,
            _partition_data_points(node.content, node.data_points, cols),
        ):
            kid.data_points = dps
        node.data_points = []
    if node.paren_quote_ranges:
        for kid, cpq in zip(
            kids,
            _partition_ranges(node.content, node.paren_quote_ranges, cols),
        ):
            kid.paren_quote_ranges = cpq
        node.paren_quote_ranges = []
    _inherit_glue(node, kids, ids)
    if node.type == NodeType.TEXT:
        node.type = NodeType.GROUP
    node.children = kids + node.children
    node.content = ""
    node.applicable = None
    node.column_split_group = True
    # The pieces are ordinary content, so give each the datapoint pass the
    # caller would have given the unsplit line. The inline-code peel is left
    # to the caller's Step 4 walk, which recurses through here.
    for kid in kids:
        _apply_all_datapoints_to_node(kid, criteria, ids)
    return True


def _promote_align_regions(
    node: "MarkdownGroupNode",
    protected: list[tuple[int, int]],
    detector: DataPointDetector,
    criteria,
    annotate_labels: set[str],
    ids: IdMint,
) -> bool:
    """Split *node*'s content at its springs into aligned region children.

    Mirrors :meth:`_promote_colon_columns` beside it — same dp / paren-quote
    partitioning, same glue inheritance, same TEXT→GROUP retype — but marks
    the container ``align_group`` and stamps each region's ``authored_align``.

    It runs BEFORE every other split, which is the whole design: with the
    regions carved out first, each one is an ordinary line as far as the
    separator / key-value / colon-column chain is concerned, so that chain
    needs no knowledge of springs at all and its precedence rules are
    untouched. It also means the parent's ``separator_chars`` is naturally
    empty across a spring gap — a spring is an absence of separator, and
    ## Separators can never draw a glyph into the gap the author opened.

    Returns True when it fired, in which case the caller must stop: the
    regions have already been walked and hold whatever structure they have.
    """
    regions = _split_align_regions(node.content, sorted(protected))
    if regions is None:
        return False
    # One region only ALIGNS its line. A bare line's lone region collapses back
    # into a leaf (grouper_glue); any other node (``- ... X ...``) becomes its
    # unsprung self plus the alignment, and is walked as that.
    if len(regions) == 1 and node.type != NodeType.TEXT:
        node.content, node.authored_align = regions[0]
        node.data_points = _detect_through_markers(node.content, detector)
        dp_ranges = [(dp["start"], dp["end"]) for dp in node.data_points]
        node.paren_quote_ranges = _merge_pq(
            _bracket_quote_ranges(node.content, dp_ranges)
        )
        node.applicable = None
        _separate_structured_content_walk(
            node, detector, criteria, annotate_labels, ids
        )
        return True

    # The partition helpers speak the ``(label, text)`` shape every other
    # splitter returns; a region carries an alignment where a label would
    # be, so hand them the pieces in that shape explicitly.
    pieces = [(NodeType.TEXT, txt) for txt, _ in regions]
    kids = [MarkdownGroupNode(type=NodeType.TEXT, content=txt) for txt, _ in regions]
    for kid, (_, align) in zip(kids, regions):
        kid.authored_align = align
    if node.data_points:
        for kid, dps in zip(
            kids,
            _partition_data_points(node.content, node.data_points, pieces),
        ):
            kid.data_points = dps
        node.data_points = []
    if node.paren_quote_ranges:
        for kid, cpq in zip(
            kids,
            _partition_ranges(node.content, node.paren_quote_ranges, pieces),
        ):
            kid.paren_quote_ranges = cpq
        node.paren_quote_ranges = []
    _inherit_glue(node, kids, ids)
    if node.type == NodeType.TEXT:
        node.type = NodeType.GROUP
    node.children = kids + node.children
    node.content = ""
    node.applicable = None
    node.align_group = True
    # Each region is now an ordinary line: hand it the same full walk the
    # unsplit line would have had, so separators, key-values, colon columns
    # and datapoints all resolve inside it under their usual precedence.
    for kid in kids:
        _separate_structured_content_walk(kid, detector, criteria, annotate_labels, ids)
    return True
