"""Which buttons are a choice's options, and which runs of them are segmented.

An ``agent:`` button whose destination carries ``md2ui.choice=<name>`` is an
option of the choice of that name (ADR-405). A run of options the author divided
with `` | `` (``separator_chars``) and gave one name is one control, drawn
segmented when the theme asks: the grouper stamps ``segmented_run`` on that
run's group once, on the finished tree, whatever the theme, and the renderer
reads the flag (ADR-100) rather than re-reading the run's pieces.
"""

from __future__ import annotations

from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType, link_destination
from md2ui.utils.image_params import destination_url, split_md2ui_params

# The `md2ui.` param that makes an `agent:` button an option of a named group.
CHOICE_HINT = "choice"


def choice_of(content: str) -> str | None:
    """The choice a button's raw ``[label](agent:…)`` content is an option of."""
    url = link_destination(content) or ""
    u, hints = split_md2ui_params(destination_url(url))
    return (hints.get(CHOICE_HINT) or None) if u[:6].lower() == "agent:" else None


def is_segmented_run(node: MarkdownGroupNode) -> bool:
    """A group of two or more buttons, divided only by `` | ``, all options of one
    choice."""
    kids = node.children
    if len(kids) < 2 or not node.separator_chars or set(node.separator_chars) != {"|"}:
        return False
    if any(k.type != NodeType.LINK for k in kids):
        return False
    names = {choice_of(k.content) for k in kids}
    return len(names) == 1 and None not in names
