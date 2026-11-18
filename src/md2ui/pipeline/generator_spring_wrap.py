"""Where a spring line wraps, and how its pieces sit once it has.

A spring (`A ... B`) places each piece by where it was written: the first at the
left edge, the last at the right, any between them in the centre. That holds while
the line fits. When it wraps, two rules decide what the reader sees:

* **The end wraps first.** In `A ... B ... C`, C takes a line of its own and A and B
  keep the first; when A and B cannot share it either, every piece takes a line of
  its own, in the order written. A middle that is an icon between two values
  (`NBY ... ✈️ ... SPT`) so stays beside the value it leads from.
* **A wrapped right piece goes left.** A piece pushed right by its spring has
  nothing to push from once it is alone on its line, and right-aligned it reads as
  stranded; it starts where the text does. A centred piece stays centred.

Both follow the run's wrap pins (``generator_fit_votes.line_breaks``): the lines
of a run break in the same places, so its members wrap and realign alike.
"""

from __future__ import annotations

from md2ui.pipeline import generator_fit_votes
from md2ui.pipeline.grouper_types import MarkdownGroupNode
from md2ui.pipeline.layout_script_parser import LayoutNode


def _edges_and_middle(node: MarkdownGroupNode) -> bool:
    """Whether *node* is a spring line written `A ... B ... C`: a left piece, one
    or more centred ones, and a right piece."""
    aligns = [c.authored_align for c in node.children]
    return (
        node.align_group
        and len(aligns) >= 3
        and aligns[0] == "left"
        and aligns[-1] == "right"
        and all(a == "center" for a in aligns[1:-1])
    )


def rewrap(polls: list, node: MarkdownGroupNode, rows: list, lines: list, reflow):
    """*rows* and *lines* once *node*'s line has wrapped, as the rules above place
    them. *reflow(cells, breaks)* flows the line again from *cells* in that order,
    breaking before each piece in *breaks*. The line wraps where its run voted
    (``line_breaks``); whether the middle of `A ... B ... C` left the first line is
    one more vote, so a run's members take one line each together or not at all."""
    if _edges_and_middle(node) and len(lines) > 1:
        kids = node.children
        first = {id(p) for p in lines[0]}
        apart = any(id(m) not in first for m in kids[1:-1])
        breaks = {id(kids[-1])}
        if generator_fit_votes.vote(polls, node, apart):
            breaks |= {id(m) for m in kids[1:-1]}
        rows, lines = reflow(list(kids), frozenset(breaks))
    left_when_alone(rows, lines)
    return rows, lines


def left_when_alone(rows: list[LayoutNode], lines: list) -> None:
    """A right piece that wrapped onto a line of its own starts at the left."""
    for row, pieces in zip(rows[1:], lines[1:]):
        props = row.render_properties or {}
        if len(pieces) == 1 and props.get("content_align") == "right":
            row.render_properties = {**props, "content_align": "left"}
