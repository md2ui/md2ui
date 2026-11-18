"""A pair exists only while a display reads it (ADR-205).

The separation walk still cuts `Key: value` into a ``KEY_VALUE`` pair, because
the displays read their label and value from one: a percentage bar, a ratio
ring, a line, a chart row, a slider. Once the displays and the charts are
decided (Phases 6.06–6.07), a pair that holds none goes back to the line its
author wrote, colon and markers kept, as one text — the same node the line is
when its colon is escaped and never pairs. A pair that holds one is untouched,
so every display draws as it did.
"""

from md2ui.pipeline.grouper_annotate import _detect_through_markers
from md2ui.pipeline.grouper_block_splits import _split_images
from md2ui.pipeline.grouper_drawing_elements import restore_escaped_task_controls
from md2ui.pipeline.grouper_ranges import _bracket_quote_ranges, _merge_pq
from md2ui.pipeline.grouper_sliders import restore_escaped_sliders
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType

# Containers that hold their line as their own content when it is not split.
_HOLDS_ITS_LINE = (NodeType.GROUP, "root")


def unpair_unread(node: MarkdownGroupNode, detector, in_chart: bool = False) -> None:
    """Every pair under *node* that no display claimed, back to its line."""
    in_chart = in_chart or node.chart_group or node.line_group
    restored: list[MarkdownGroupNode] = []
    for i, child in enumerate(node.children):
        if (
            child.type == NodeType.KEY_VALUE
            and child.pair_source
            and not in_chart
            and not _draws(child)
        ):
            node.children[i] = _as_written(child, detector)
            restored.append(node.children[i])
        else:
            unpair_unread(child, detector, in_chart)
    if len(node.children) == 1 and restored:
        _whole_line_again(node)


def _draws(node: MarkdownGroupNode) -> bool:
    """Whether *node* or anything in it is drawn as a display or a control."""
    return (
        bool(node.datapoint_display)
        or node.type == NodeType.DRAWING_ELEMENT
        or any(_draws(c) for c in node.children)
    )


def _as_written(pair: MarkdownGroupNode, detector) -> MarkdownGroupNode:
    """The line *pair* was cut from, as one node in its place. A picture
    written on it is a picture, so the line comes back as its escaped twin
    does: its text and its pictures, side by side on one line. The source was
    taken before Phase 5.55 put an escaped control's bracket back, so it is put
    back here too: ``Volume: \\[65%]`` is drawn ``Volume: [65%]``."""
    assert pair.pair_source is not None
    kind, content = pair.pair_source
    pieces = _split_images(content)
    if pieces is None:
        line = _piece(kind, content, pair, detector)
    else:
        line = _piece(NodeType.GROUP, "", pair, detector)
        line.children = [
            _piece(kind if t == NodeType.TEXT else t, part.strip(), pair, detector)
            for t, part in pieces
            if part.strip()
        ]
    restore_escaped_task_controls(line)
    restore_escaped_sliders(line)
    return line


def _piece(kind, content: str, pair: MarkdownGroupNode, detector):
    """One node of *pair*'s line, on that line."""
    node = MarkdownGroupNode(type=kind, content=content)
    node.node_id = pair.node_id
    node.glued_content_id = pair.glued_content_id
    node.source_line_id = pair.source_line_id or _first_line_id(pair)
    node.unpaired = pair
    if content and kind != NodeType.IMAGE:
        node.text_style = _shared_style(pair)
        node.data_points = _detect_through_markers(content, detector)
        spans = [(dp["start"], dp["end"]) for dp in node.data_points]
        node.paren_quote_ranges = _merge_pq(_bracket_quote_ranges(content, spans))
    return node


def _whole_line_again(node: MarkdownGroupNode) -> None:
    """*node*'s one line is whole again, so it holds it as it does a line that
    never split: a heading or an item takes the text back as its own content,
    and a tier the split had stranded on the container returns to the text."""
    (only,) = node.children
    if only.children and node.type not in _HOLDS_ITS_LINE:
        node.children = only.children  # an item holds its line's pieces itself
        return
    if node.type in _HOLDS_ITS_LINE:
        if node.text_style == only.text_style:
            node.text_style = None
        return
    if node.content:
        return
    node.content = only.content
    node.data_points = only.data_points
    node.paren_quote_ranges = only.paren_quote_ranges
    node.unpaired = only.unpaired
    node.children = []
    if only.text_style is not None:
        node.text_style = only.text_style


def _leaves(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    if not node.children:
        return [node]
    return [leaf for c in node.children for leaf in _leaves(c)]


def _first_line_id(node: MarkdownGroupNode) -> int | None:
    return next(
        (
            leaf.source_line_id
            for leaf in _leaves(node)
            if leaf.source_line_id is not None
        ),
        None,
    )


def _shared_style(pair: MarkdownGroupNode) -> str | None:
    """The text tier every leaf of *pair* carries: a tier written around the
    whole line was handed down to its pieces, and comes back with the line."""
    styles = {leaf.text_style for leaf in _leaves(pair) if leaf.content}
    return styles.pop() if len(styles) == 1 else None
