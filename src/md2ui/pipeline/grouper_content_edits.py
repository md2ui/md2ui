"""Editing a node's ``content`` after its data points were recorded.

A data point names a span of its node's ``content``: ``start`` / ``end``, and
``matched``, the text of that span (``_detect_through_markers`` sets it to the
REAL span, markers included). Several passes rewrite ``content`` after detection
— the tier wrapper comes off (6.055), the late escapes and the quotes of a
declined element are consumed (6.17), placeholder characters are spelled again.
Assigning the new string directly leaves the data points describing the old
one, so a reader that slices ``content`` by them gets the wrong characters.

So there is ONE way to rewrite content a data point may index: describe the
rewrite as edits and hand them to :func:`edit_content`. A split, which hands
pieces of a node to new children, is the other case and keeps its own home
(``grouper_split_apply._partition_data_points``); :func:`keep_content` is that
same locate-the-piece rule for a node that keeps ONE piece of itself.

Pure arithmetic on ``content`` and ``data_points``: it imports nothing from the
pipeline, so every pass can call it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from md2ui.pipeline.grouper_types import MarkdownGroupNode

# ``(start, end, text)``: replace ``content[start:end]`` with ``text``.
Edit = tuple[int, int, str]


def _moved(pos: int, edits: list[Edit], is_end: bool) -> int:
    """Where offset *pos* of the old content lands in the edited content.

    An offset inside a replaced span lands on that span's replacement: at its
    start for a data point's start, at its end for a data point's end, so a
    range that overlaps an edit keeps whatever of it survives.
    """
    shift = 0
    for start, end, text in edits:
        if pos <= start:
            break
        if pos >= end:
            shift += len(text) - (end - start)
            continue
        return start + shift + (len(text) if is_end else 0)
    return pos + shift


def edit_content(node: MarkdownGroupNode, edits: Iterable[Edit]) -> None:
    """Apply *edits* to ``node.content`` and keep its data points true.

    Edits are non-overlapping spans of the CURRENT content, in any order. Every
    data point is re-based onto the new content and its ``matched`` re-read
    from it; one whose whole span was removed names nothing and is dropped.
    """
    ordered = sorted(edits)
    if not ordered:
        return
    old = node.content
    pieces: list[str] = []
    prev = 0
    for start, end, text in ordered:
        pieces += [old[prev:start], text]
        prev = end
    pieces.append(old[prev:])
    new = "".join(pieces)
    node.content = new
    if not node.data_points:
        return
    kept = []
    for dp in node.data_points:
        start = _moved(dp["start"], ordered, is_end=False)
        end = _moved(dp["end"], ordered, is_end=True)
        if start < end:
            # A copy: a split may have handed the same dict to another node.
            kept.append({**dp, "start": start, "end": end, "matched": new[start:end]})
    node.data_points = kept


def keep_content(node: MarkdownGroupNode, piece: str) -> None:
    """Narrow ``node.content`` to *piece*, a substring of it — a wrapper or
    the whitespace around it coming off.

    The piece is located the way ``_partition_data_points`` locates a split
    child: its first occurrence.
    """
    at = node.content.find(piece)
    if at < 0:
        raise ValueError(f"{piece!r} is not part of {node.content!r}")
    edit_content(node, [(0, at, ""), (at + len(piece), len(node.content), "")])


def regex_edits(
    pattern: re.Pattern[str], repl: str | Mapping[str, str], text: str
) -> list[Edit]:
    """The edits ``pattern.sub`` would make, one per match: *repl* is a
    template, or a table from each matched text to its replacement."""
    return [
        (m.start(), m.end(), m.expand(repl) if isinstance(repl, str) else repl[m[0]])
        for m in pattern.finditer(text)
    ]
