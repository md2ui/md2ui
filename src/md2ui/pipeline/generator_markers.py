"""Resolve background-level marker styles into renderer-ready properties.

Marker choice is a unit concern, but baking the chosen style also applies the
node's rotation slot. Keeping that one conversion here lets the layout generator
focus on arranging the resulting fixed marker cell.
"""

from md2ui.pipeline.theme import (
    BulletedListStyle,
    NumberedListStyle,
    QuoteStyle,
)
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.render_colors import _rotate_color, _synced_slot


def numbered_style(node: MarkdownGroupNode, theme) -> NumberedListStyle:
    """The owning background level's marker style for an ordinal."""
    style = (
        theme.sections.get(node.list_heading_level)
        if node.list_heading_level is not None
        else theme.numbered_lists
    )
    marker = style.marker if style is not None else None
    return marker if isinstance(marker, NumberedListStyle) else NumberedListStyle()


def bullet_style(node: MarkdownGroupNode, theme) -> BulletedListStyle | None:
    """The exact/fallback bullet marker for a list or task item."""
    if node.type == NodeType.LIST_ITEM:
        marker = theme.unordered_lists.marker
        return marker if isinstance(marker, BulletedListStyle) else None
    if node.type in (NodeType.TASK_OPEN, NodeType.TASK_DONE):
        marker = theme.task_lists.marker
        if not isinstance(marker, BulletedListStyle) or not marker.is_active():
            marker = theme.unordered_lists.marker
        return marker if isinstance(marker, BulletedListStyle) else None
    return None


def quote_style(theme) -> QuoteStyle | None:
    marker = theme.quotes.marker
    return marker if isinstance(marker, QuoteStyle) else None


def marker_style(node: MarkdownGroupNode, theme):
    """The marker owned by *node*'s structural/heading background level."""
    if node.type in (NodeType.LIST_ITEM, NodeType.TASK_OPEN, NodeType.TASK_DONE):
        return bullet_style(node, theme)
    if node.type == NodeType.ORDERED_ITEM:
        return numbered_style(node, theme)
    if node.type == NodeType.BLOCKQUOTE:
        return quote_style(theme)
    return None


def marker_gutter_x(node: MarkdownGroupNode, theme=None) -> float:
    """Horizontal width reserved by an active aside marker and its gap."""
    if theme is None:
        return 0.0
    marker = marker_style(node, theme)
    if marker is None or not marker.is_active() or not marker.aside:
        return 0.0
    if isinstance(marker, BulletedListStyle):
        return marker.size + marker.space
    if isinstance(marker, NumberedListStyle):
        return (
            marker.text_style.font_size + marker.space
            if marker.text_style is not None
            else 0.0
        )
    size = marker.bar_width if marker.is_bar() else marker.char_text_style.font_size
    return size + marker.space


def build_marker_props(node: MarkdownGroupNode, theme) -> dict | None:
    """Return the active marker style for *node* as plain render properties."""
    slot = _synced_slot(
        node.rotation_index, node.rotation_chain, node.rotation_path, theme
    )

    def marker_color(colors: list[int], fallback: int | None) -> int | None:
        return _rotate_color(
            colors, fallback, slot, theme, "background", node.rotation_chain
        )

    if node.type in (NodeType.LIST_ITEM, NodeType.TASK_OPEN, NodeType.TASK_DONE):
        marker = bullet_style(node, theme)
        if marker is None or not marker.is_active():
            return None
        return {
            "kind": "bullet",
            "shape": marker.shape,
            "size": marker.size,
            "color": marker_color(marker.colors, marker.color),
            "emoji": marker.emoji,
            "space": marker.space,
            "aside": marker.aside,
            "alignment": marker.alignment,
        }
    if node.type == NodeType.ORDERED_ITEM:
        marker = numbered_style(node, theme)
        if not marker.is_active():
            return None
        text_style = marker.text_style
        assert text_style is not None
        return {
            "kind": "number",
            "text": marker.number_format.format(n=node.list_ordinal or 1),
            "font_name": text_style.font_name,
            "font_size": text_style.font_size,
            "font_weight": text_style.font_weight,
            "color": marker_color(text_style.colors, text_style.color),
            "size": text_style.font_size,
            "space": marker.space,
            "aside": marker.aside,
            "alignment": marker.alignment,
        }
    if node.type == NodeType.BLOCKQUOTE:
        marker = quote_style(theme)
        if marker is None or not marker.is_active():
            return None
        if marker.is_bar():
            return {
                "kind": "quote",
                "mode": "bar",
                "bar_width": marker.bar_width,
                "bar_length": marker.bar_length,
                "color": marker_color(marker.bar_colors, marker.bar_color),
                "size": marker.bar_width,
                "space": marker.space,
                "aside": marker.aside,
                "alignment": marker.alignment,
            }
        text_style = marker.char_text_style
        return {
            "kind": "quote",
            "mode": "char",
            "text": marker.quote_char,
            "font_name": text_style.font_name,
            "font_size": text_style.font_size,
            "font_weight": text_style.font_weight,
            "color": marker_color(text_style.colors, text_style.color),
            "size": text_style.font_size,
            "space": marker.space,
            "aside": marker.aside,
            "alignment": marker.alignment,
        }
    return None
