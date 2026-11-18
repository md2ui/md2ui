"""Merged list surfaces: one card behind a whole list, a rule between its items.

A list surface (``### Unordered Lists``, ``### Task Lists``, ``### Numbered
Lists``) paints one background per item by default. ``Merge rows: yes`` on that
level asks for the other common shape -- the settings menu, the transaction
history -- where the items share ONE card and a divider runs between them. It is
the theme's look, never the author's: the Markdown is the same list either way.

The decision is baked onto the layout once per width, as ``bake_list_cards`` and
``bake_merged_row_cards`` are, so measuring and painting read the same layers
(ADR-400). A run of two or more items stacked in one column becomes:

- the **shell**, on the column: the level's paint with no padding of its own;
- a **row** per item: the level's padding and no paint, no gap between rows;
- a **divider** between two rows: the theme's horizontal rule, scoped to the
  list level (``#### Horizontal Rule`` under it; ``Stroke width: 0`` for none).

A run that grids is not merged: a grid of tiles is separate cards by nature.

A run made of a level's items alone, gridded or stacked, draws without the
element card the grouper's glue gives it unless the level says ``List card:
yes`` (``bake_list_run_cards``). The run keeps its arrangement; only the card
goes. A lead-in or a line glued to the list keeps the card: the run is not a
list alone.
"""

import dataclasses

from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.render_text_scopes import scoped_horizontal_rule_style
from md2ui.pipeline.theme import PaddingBox, SectionStyle, Theme

LIST_SURFACES = frozenset({"unordered_list", "task_list", "numbered_list"})

# The scopes a list kind's text and rule overrides are authored under; task
# items read the unordered level first, as their surface does.
_RULE_SCOPES = {
    "unordered_list": ("unordered_lists",),
    "task_list": ("unordered_lists", "task_lists"),
    "numbered_list": ("numbered_lists",),
}

_SHELL = "_shell"
_DIVIDER = "_divider"
ROW = "list_row"


def list_style(theme: Theme, kind: str) -> SectionStyle | None:
    """The style a list surface of *kind* paints with (task items fall back to
    the unordered level when ``### Task Lists`` paints nothing)."""
    if kind == "unordered_list":
        return theme.unordered_lists
    if kind == "task_list":
        if theme.task_lists.is_active():
            return theme.task_lists
        return theme.unordered_lists
    if kind == "numbered_list":
        return theme.numbered_lists
    return None


def _merges(theme: Theme, kind: str | None) -> bool:
    style = list_style(theme, kind) if kind in LIST_SURFACES else None
    return style is not None and style.is_active() and style.merge_rows


def bake_merged_lists(node: LayoutNode, theme: Theme) -> None:
    """Mark each stacked run of list items whose level merges its rows.

    Baked after ``bake_list_cards``, which has already taken the element cards
    out of every item: a merged row paints nothing, so those cards must stay
    gone, and the order keeps that pass unaware of this one. The run's own
    element card goes too, for the reason that pass gives: the shell IS the
    list's surface, and a card of the same extent would paint over it.
    """
    kinds = {c.background_kind for c in node.children}
    if node.type == "col" and len(node.children) >= 2 and len(kinds) == 1:
        kind = next(iter(kinds))
        if _merges(theme, kind):
            if node.card_kind is None:
                node.is_card = False
            node.render_properties = {
                **(node.render_properties or {}),
                "list_shell": kind,
            }
            for child in node.children:
                child.render_properties = {
                    **(child.render_properties or {}),
                    "list_row": kind,
                }
    for child in node.children:
        bake_merged_lists(child, theme)


def bake_list_run_cards(node: LayoutNode, theme: Theme) -> None:
    """Drop the element card around a run of list items alone, unless a level
    among them says ``List card: yes``. Baked with the other list
    decisions, before measuring, so measure and paint agree (ADR-400)."""
    kinds = _list_kinds(node)
    if node.is_card and node.card_kind is None and kinds:
        styles = [list_style(theme, k) for k in kinds]
        if not any(st is not None and st.list_card for st in styles):
            node.is_card = False
    for child in node.children:
        bake_list_run_cards(child, theme)


def _list_kinds(node: LayoutNode) -> set[str]:
    """The list kinds of the items *node* holds, through the rows and columns
    that arrange them; empty when anything else is among them."""
    kinds: set[str] = set()
    for child in node.children:
        if child.background_kind in LIST_SURFACES:
            kinds.add(child.background_kind)
        elif child.background_kind is None and child.children and not child.is_card:
            inner = _list_kinds(child)
            if not inner:
                return set()
            kinds |= inner
        else:
            return set()
    return kinds


def merged_layer(node: LayoutNode, theme: Theme) -> tuple[str, SectionStyle] | None:
    """The wrap layer a merged shell or row stands for, or None for any other
    node. The layer's style is what insets the content; what it paints is
    ``paint_style``'s, looked up from the kind."""
    props = node.render_properties or {}
    kind = props.get("list_shell")
    if kind is not None:
        style = list_style(theme, kind)
        assert style is not None
        return kind + _SHELL, dataclasses.replace(style, padding=PaddingBox())
    kind = props.get("list_row")
    if kind is not None:
        style = list_style(theme, kind)
        assert style is not None
        return ROW, SectionStyle(padding=style.padding)
    return None


def is_row(node: LayoutNode) -> bool:
    return (node.render_properties or {}).get("list_row") is not None


def paint_style(kind: str, theme: Theme) -> SectionStyle | None:
    """What a merged box paints, or None when *kind* is not one.

    The shell paints the level's first colour only: it is one box with no item
    behind it, so a cycle of colours has nothing to deal across (the rows it
    holds are its items). A divider paints the scoped rule as a thin fill.
    """
    if kind.endswith(_SHELL):
        style = list_style(theme, kind[: -len(_SHELL)])
        assert style is not None
        return dataclasses.replace(
            style, bg_colors=style.bg_colors[:1], padding=PaddingBox()
        )
    if kind.endswith(_DIVIDER):
        rule = scoped_horizontal_rule_style(theme, _RULE_SCOPES[kind[: -len(_DIVIDER)]])
        return SectionStyle(bg_colors=[rule.stroke_color])
    return None


def divider_rect(
    prev: LayoutNode, child: LayoutNode, x: float, y: float, width: float, theme: Theme
) -> tuple[float, float, float, float, str] | None:
    """The rule painted at *y*, the edge two merged rows share, as (x, y, w,
    h, kind): centred on that edge and inset by the rows' padding, so it lines
    up with their content. None between any other two siblings, or when the
    scoped rule has no width."""
    if not (is_row(prev) and is_row(child)):
        return None
    kind = (child.render_properties or {})["list_row"]
    rule = scoped_horizontal_rule_style(theme, _RULE_SCOPES[kind])
    if rule.stroke_width <= 0:
        return None
    style = list_style(theme, kind)
    assert style is not None
    pad = style.padding
    w = rule.stroke_width
    return x + pad.left, y - w / 2, width - pad.x, w, kind + _DIVIDER
