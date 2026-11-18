"""Background resolution: which surface a box sits on, and how the layers stack.

Owns the **background stack** -- for any box, the list of surfaces behind it,
innermost first: its own card fill, then the section it is in, then the sections
above that, then the page. ``_emit_wrap_boxes`` builds it while wrapping a node,
and ``_bg_selector`` names the colour each layer contributes.

That stack is what makes ``## Color Replacements`` work: a rule is keyed on the
colour *and* the surface behind it, so the renderer must know what is underneath
before it can decide what to paint. Colour resolution itself lives in
``render_colors``; this module only decides what the layers ARE.

Owns no painting. ``_paint_style_for`` picks a *style*, not pixels -- the actual
fills (``_paint_layered_fill``, ``_paint_section_background``) stay in the
renderer, because they need a canvas.
"""

import dataclasses

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.render_colors import _replace_color, _rotate_color, _synced_slot
from md2ui.pipeline.render_list_surfaces import ROW, merged_layer, paint_style
from md2ui.pipeline.render_style import _RING_TEXT_MARGIN
from md2ui.pipeline.theme import (
    _CHIP_VARIANTS,
    BG_IMAGE,
    PaddingBox,
    SectionStyle,
    Theme,
    resolve_section_style,
)
from md2ui.pipeline.theme_model import LINK_BUTTON_VARIANTS
from md2ui.utils.image_params import clean_image_url


def element_background_sources(theme: Theme) -> set[str]:
    """Unique image sources used by button, chip, emoji-badge and copy-button
    styles."""
    button_styles = (
        theme.links.resolved(name)
        for name in ("primary", *LINK_BUTTON_VARIANTS, "text")
    )
    chip_styles = (theme.inline_code.resolved(name) for name in (None, *_CHIP_VARIANTS))
    badge_styles = (
        theme.emojis.resolved(name)
        for name in (None, "secondary", "tertiary", "quaternary")
    )
    sources = {style.bg_image for style in (*button_styles, *chip_styles)}
    sources.update(style.fill.bg_image for style in badge_styles)
    sources.add(theme.code_blocks.copy_button.bg_image)
    return {source for source in sources if source}


def _row_backgrounds_match(child: LayoutNode, level: int) -> bool:
    """True when every same-level section in this row paints the same
    background, so one merged rect can stand in for all of them.

    ``merge_rows`` predates image cards, when a section's background came
    entirely from its theme level and same-level siblings were therefore
    identical by construction. A section can now carry its own photo, and
    merging a row of image cards would throw every card's image away in favour
    of one shared background.

    Comparing ``card_bg_url`` alone is enough: every other background property
    (colors, gradient, stroke) comes from the level's style, which is the same
    for all sections at that level. The photo is the only per-node datum.

    Compared on the CLEAN url: two cards showing one photo with different
    ``?md2ui.*`` annotations are still the same background, and must not be
    kept apart by an annotation the fetcher strips anyway.
    """
    style_keys = {
        c.section_style_key for c in child.children if c.section_level == level
    }
    return len(style_keys) <= 1 and (
        len(
            {
                clean_image_url(c.card_bg_url)
                for c in child.children
                if c.section_level == level
            }
        )
        <= 1
    )


@dataclasses.dataclass
class SectionBox:
    """A heading-section background box, in content coordinate space.

    ``x/y/width/height`` is the *outer* (background) rect; the section's content
    is inset by ``padding`` on all sides. ``level`` selects the themed paint.
    """

    x: float
    y: float
    width: float
    height: float
    level: int
    padding: "PaddingBox"
    kind: str = (
        "section"  # "section" | "card" | "root" (root: debug overlay only)
        # | "table" | "table_header" | "table_row" (## Tables styles)
    )
    # Rounded-rect clip applied while painting this box, as
    # (x, y, w, h, radius): row fills inside a merged table shell clip to the
    # shell so they don't overpaint its rounded corners. None = no clip.
    clip: tuple[float, float, float, float, float] | None = None
    # For a ``kind == "ring"`` box: the arc's ``{"value", "max"}`` so the paint
    # loop can draw the value arc (a per-ring datum the themed style can't
    # carry). None on every other box.
    ring: dict | None = None
    # For a ``kind == "image_card"`` box: the background photo's URL — the same
    # per-box datum problem as ``ring``, since the themed style is shared by
    # every card while this image belongs to one. Painted between the style's
    # fill and its gradient by ``_paint_layered_fill``.
    bg_image_url: str | None = None
    # This box's slot in its color cycle, from the markdown node via
    # ``LayoutNode.rotation_index`` — the section's / card's ordinal among its
    # same-channel siblings inside the enclosing section. None when no markdown
    # node backs the box (table rows, the root), in which case the paint loop
    # falls back to its positional counter and behaves exactly as before.
    rotation_index: int | None = None
    # The heading levels enclosing this box, outermost first, for resolving
    # ``Rotate <kind> colors`` gates — the SectionBox twin of a node's
    # ``heading_chain``. A section's OWN level is not in its chain: a level
    # gates what sits inside it, not itself.
    rotation_chain: tuple[int | str, ...] = ()
    # The slot each of those ancestors took, for ``Rotate colors: sync``.
    rotation_path: tuple[int, ...] = ()
    # Backgrounds behind this box, innermost first. Graphic painters (rings)
    # use this to resolve ## Color Replacements against their actual card /
    # section / page rather than painting their configured colors verbatim.
    bg_stack: tuple[int | str, ...] = ()
    fixed_style_key: str | None = None


def _card_style_for(child: LayoutNode, theme: Theme) -> SectionStyle | None:
    """Global element (card) style for ``child`` if it should be wrapped.

    A glued-content card is wrapped iff ``theme.elements`` insets it. It never
    paints: ``### Elements`` keeps only layout keys, and a box comes from a
    heading style.
    """
    if not child.is_card:
        return None
    # A date chip wraps with its OWN themed style (### Dates) regardless of the
    # generic element card gating.
    if getattr(child, "card_kind", None) == "date_chip":
        return theme.datapoints.date_chip.chip
    # A circular bar: the "card" is the ring; its padding insets the centered
    # value/unit text within the ring stroke. Always active (ring always drawn).
    if getattr(child, "card_kind", None) == "ring":
        return _ring_card_style(theme)
    # An image card carries its own background photo, so it is drawn even where
    # an element card insets nothing — the image IS the card. It gets its own
    # ### Image Cards block when the theme declares one, so a photo card can
    # carry a radius, padding or overlay; without one it paints only its photo.
    if getattr(child, "card_kind", None) == "image_card":
        return theme.image_cards if theme.image_cards.is_active() else theme.elements
    if getattr(child, "table", False) and theme.tables.is_active():
        # The themed table shell/row backgrounds replace the generic element
        # card; without a ## Tables block, tables keep the generic card wrap.
        return None
    return theme.elements if theme.elements.is_active() else None


def _structural_style_for(
    child: LayoutNode, theme: Theme
) -> tuple[str, SectionStyle] | None:
    """The dedicated list/quote surface carried by *child*, when configured."""
    merged = merged_layer(child, theme)
    if merged is not None:
        return merged
    kind = child.background_kind
    style = {
        "unordered_list": theme.unordered_lists,
        "task_list": theme.task_lists,
        "numbered_list": theme.numbered_lists,
        "quote": theme.quotes,
    }.get(kind or "")
    if kind == "task_list" and style is not None and not style.is_active():
        style = theme.unordered_lists
    return (
        (kind, style)
        if kind is not None and style is not None and style.is_active()
        else None
    )


_LIST_SURFACES = frozenset({"unordered_list", "task_list", "numbered_list"})


def bake_list_cards(node: LayoutNode, theme: Theme, in_list: bool = False) -> None:
    """Stop element cards painting inside a list item's own surface.

    A list item's lines are consecutive, so the grouper glues them and the
    generator makes the glued run a card -- which then paints its element
    background inside the item's list background, the two competing for the
    same content. The glue stays (the generator arranges by it); only the card
    goes, as ``bake_merged_row_cards`` stops repeated cards. Image cards, date
    chips and rings keep theirs: that background IS the element.

    Baked before ``natural_height`` / ``place_boxes`` so measure and paint read
    the same ``is_card`` (ADR-400). Only under a surface that actually paints:
    with no list background there is nothing for a card to compete with.
    """
    surface = _structural_style_for(node, theme)
    inside = in_list or (
        surface is not None
        and surface[0] in _LIST_SURFACES
        and _paints_fill(surface[1], None)
    )
    # `inside`, not `in_list`: a glued run that collapsed onto the item makes
    # the item itself the card, painting both layers on the one box.
    if inside and node.is_card and node.card_kind is None:
        node.is_card = False
    for child in node.children:
        bake_list_cards(child, theme, inside)


def _paints_fill(st: SectionStyle, bg_image_url: str | None) -> bool:
    """True when *st* actually covers its rect with something visible.

    ``SectionStyle.is_active()`` also counts padding, so a level configured with
    insets but no paint reads as active while drawing nothing. Background
    precedence has to know the difference: only a style that really covers the
    area may suppress the card layer beneath it.
    """
    return bool(
        st.bg_colors
        or st.bg_image
        or st.gradient
        or (st.stroke_width > 0.0 and st.stroke_color is not None)
        or bg_image_url
    )


def _wrap_layers(
    child: LayoutNode, theme: Theme, in_levels: frozenset[int]
) -> list[tuple[str, int, SectionStyle]]:
    """Background+padding wrap layers for ``child``, outer→inner.

    The heading **section** layer (per-level style) then the **card** (element)
    layer (global style). Each is ``(kind, level, style)``; both are composable.
    """
    layers: list[tuple[str, int, SectionStyle]] = []
    lvl, st = _section_style_for(child, theme, in_levels)
    if st is not None and lvl is not None:
        layers.append(("section", lvl, st))
    structural = _structural_style_for(child, theme)
    if structural is not None:
        kind, st = structural
        layers.append((kind, 0, st))
    card = _card_style_for(child, theme)
    if card is not None:
        ck = getattr(child, "card_kind", None)
        kind = ck if ck in ("date_chip", "ring", "image_card") else "card"
        # Background precedence — heading > image card > glued. One node can
        # hold several of these roles at once (a heading section that is also a
        # glued card, or a heading that absorbed an image card), and painting
        # them all stacks rects of the same extent differing only by padding.
        # The card layer is dropped only when the section actually *covers* the
        # area, though: a level whose style is "active" through padding alone
        # paints nothing, and suppressing the card there would leave the node
        # with no background at all. Chips and rings are not backgrounds in
        # this sense — they are the element itself — so they always compose.
        covered = (
            bool(layers)
            and layers[0][0] == "section"
            and kind in ("card", "image_card")
            and _paints_fill(layers[0][2], getattr(child, "card_bg_url", None))
        )
        if not covered:
            layers.append((kind, 0, card))
    return layers


# Margin between the ring stroke and the text region inside it.


def _ring_card_style(theme: Theme) -> SectionStyle:
    """The ring card's inset style: symmetric padding that keeps the centered
    value/unit text clear of the ring stroke."""
    pad = theme.datapoints.ring.thickness + _RING_TEXT_MARGIN
    return SectionStyle(padding=PaddingBox(top=pad, left=pad, right=pad, bottom=pad))


def _layers_pad(layers: list[tuple[str, int, SectionStyle]]) -> "PaddingBox":
    """Total TLRB padding of a layer stack (summed)."""
    box = PaddingBox()
    for _kind, _lvl, st in layers:
        box.top += st.padding.top
        box.left += st.padding.left
        box.right += st.padding.right
        box.bottom += st.padding.bottom
    return box


def _layers_section_level(
    layers: list[tuple[str, int, SectionStyle]],
) -> int | None:
    """The heading-section level among the layers (None if card-only)."""
    for kind, lvl, _st in layers:
        if kind == "section":
            return lvl
    return None


def _paint_style_for(
    kind: str,
    level: int,
    theme: "Theme",
    fixed_style_key: str | None = None,
) -> "tuple[SectionStyle | None, int | str]":
    """The style (and themed-image key) a SectionBox of this kind paints with.

    Shared by the paint loop and by ``_bg_selector`` so the color a leaf believes
    is behind it is resolved from the very same style that put it there.
    """
    if kind == ROW:
        return None, 0
    merged = paint_style(kind, theme)
    if merged is not None:
        # A shell paints from its list level's image slot; a rule has none.
        base = kind.removesuffix("_shell")
        return merged, (_paint_style_for(base, level, theme)[1] if base != kind else 0)
    if kind == "image_card":
        if theme.image_cards.is_active():
            return theme.image_cards, -5
        return theme.elements, -1
    if kind == "card":
        # Read for its image keys only: ``### Elements`` paints nothing, so no
        # image is ever stored under -1.
        return theme.elements, -1
    if kind == "unordered_list":
        return theme.unordered_lists, -6
    if kind == "task_list":
        style = (
            theme.task_lists if theme.task_lists.is_active() else theme.unordered_lists
        )
        return style, -9 if style is theme.task_lists else -6
    if kind == "numbered_list":
        return theme.numbered_lists, -7
    if kind == "quote":
        return theme.quotes, -8
    if kind == "date_chip":
        return theme.datapoints.date_chip.chip, 0
    if kind == "table_header":
        return theme.tables.header, -2
    if kind == "table_row":
        return theme.tables.cells, -3
    if kind == "table":
        return theme.tables.table, -4
    if fixed_style_key and fixed_style_key in theme.fixed_sections:
        own = theme.fixed_sections[fixed_style_key]
        st = theme.fixed_section_levels.get((fixed_style_key, level), own)
        # A `Mode: override` style that states no image paints its level's.
        return (
            st,
            f"fixed:{fixed_style_key}" if own.bg_image or not st.bg_image else level,
        )
    return theme.sections.get(level), level


def _bg_selector(
    kind: str,
    level: int,
    bg_image_url: str | None,
    rotation_index: int | None,
    rotation_chain: tuple[int | str, ...],
    theme: "Theme",
    rotation_path: tuple[int, ...] = (),
    fixed_style_key: str | None = None,
) -> "int | str | None":
    """What one wrap layer counts as, for the content it wraps.

    Returns ``BG_IMAGE`` for a photo-backed layer, the concrete ARGB the layer
    paints (rotation resolved exactly as the paint loop resolves it), or None
    when the layer covers nothing a rule could key on — padding only, or a bare
    gradient, which has no single color to name.
    """
    st, _img = _paint_style_for(kind, level, theme, fixed_style_key)
    if st is None:
        return None
    if bg_image_url or st.bg_image:
        return _photo(fixed_style_key)
    if not st.bg_colors:
        return None
    if kind == "date_chip":
        # The dedicated chip painter currently uses its first authored color;
        # mirror that exact paint rather than applying section/card rotation.
        return _opaque_or_none(st.bg_colors[0])
    if rotation_index is None:
        # No markdown node behind the box (a table row): the paint loop picks
        # by a positional counter this side cannot see, so name the base color.
        return _opaque_or_none(st.bg_colors[0])
    return _opaque_or_none(
        _rotate_color(
            st.bg_colors,
            None,
            _synced_slot(rotation_index, rotation_chain, rotation_path, theme),
            theme,
            "card" if kind in ("card", "image_card") else "background",
            rotation_chain
            + (
                (f"fixed:{fixed_style_key}|{level}",)
                if fixed_style_key
                else ((level,) if level else ())
            ),
        )
    )


def _photo(fixed_style_key: str | None) -> str:
    """A photo surface, named by the fixed style that paints it when one does,
    so ``On background color: image <style>`` can tell one photo from another."""
    return f"{BG_IMAGE}:{fixed_style_key}" if fixed_style_key else BG_IMAGE


def _own_surface(sbox: "SectionBox", style: "SectionStyle", fill: int | None):
    """What a wrap box's own paint counts as, for the stroke drawn on it."""
    if sbox.bg_image_url or style.bg_image:
        return _photo(sbox.fixed_style_key)
    return _opaque_or_none(fill)


def _push_bg(
    stack: "tuple[int | str, ...]", selector: "int | str | None"
) -> "tuple[int | str, ...]":
    """Push a genuinely visible selector; absent/transparent means unchanged."""
    if selector is None or (isinstance(selector, int) and selector >> 24 == 0):
        return stack
    return (selector,) + stack


def _opaque_or_none(color: "int | None") -> "int | None":
    """*color* if it actually covers anything, else None.

    A fully transparent fill — Primary's default, and the Text button variant's
    whole point — is not a background, so it must not shadow whatever it sits on.
    """
    if color is None or skia.Color4f(color).fA <= 0:
        return None
    return color


def _root_bg_stack(theme: "Theme") -> "tuple[int | str, ...]":
    """The page itself, as the outermost entry every box inherits."""
    if theme.root.bg_image:
        return (BG_IMAGE,)
    if theme.root.box:
        return (theme.root.box_fill_color,)
    return (theme.root.bg_color,)


def _emit_wrap_boxes(
    section_boxes: list | None,
    x: float,
    y: float,
    width: float,
    total_h: float,
    layers: list[tuple[str, int, SectionStyle]],
    ring: dict | None = None,
    bg_image_url: str | None = None,
    rotation_index: int | None = None,
    rotation_chain: tuple[int | str, ...] = (),
    rotation_path: tuple[int, ...] = (),
    theme: "Theme | None" = None,
    bg_stack: "tuple[int | str, ...]" = (),
    fixed_style_key: str | None = None,
) -> "tuple[float, float, float, tuple[int | str, ...]]":
    """Emit one SectionBox per layer (outer→inner), each inset by the previous
    layer's TLRB padding. Returns the innermost content origin/width plus the
    background stack the wrapped content sits on,
    ``(inner_x, inner_y, inner_w, bg_stack)``. ``ring`` (the wrapped node's arc
    datum) rides its ``kind == "ring"`` box so the paint loop can draw the value
    arc; ``bg_image_url`` rides its ``kind == "image_card"`` box the same way.

    Resolving the stack here is what keeps it honest: this is the one place that
    knows a node's whole layer list, and each entry is named by the very style
    the paint loop will use (``_paint_style_for``), so the two cannot drift."""
    bx, by, rw, rh = x, y, width, total_h
    for i, (kind, level, st) in enumerate(layers):
        enclosing_bg_stack = bg_stack
        if theme is not None:
            selector = _bg_selector(
                kind,
                level,
                bg_image_url if i == 0 else None,
                rotation_index,
                rotation_chain,
                theme,
                rotation_path,
                fixed_style_key,
            )
            if isinstance(selector, int):
                # Its own fill is replaced first, as the paint loop replaces it.
                selector = _replace_color(selector, bg_stack, theme, "fill")
            bg_stack = _push_bg(
                bg_stack,
                selector,
            )
        if section_boxes is not None:
            section_boxes.append(
                SectionBox(
                    bx,
                    by,
                    rw,
                    rh,
                    level,
                    st.padding,
                    kind,
                    ring=ring if kind == "ring" else None,
                    # The photo rides the OUTERMOST layer — the one covering
                    # the node's full extent. Which role that is depends on the
                    # precedence in _wrap_layers: a heading that absorbed a
                    # card paints it as a section, a bare card as itself.
                    bg_image_url=bg_image_url if i == 0 else None,
                    # Every layer of one node shares that node's slot: a
                    # heading that also owns a card paints both from it.
                    rotation_index=rotation_index,
                    rotation_chain=rotation_chain,
                    rotation_path=rotation_path,
                    bg_stack=enclosing_bg_stack,
                    fixed_style_key=fixed_style_key,
                )
            )
        bx += st.padding.left
        by += st.padding.top
        rw -= st.padding.x
        rh -= st.padding.y
    return bx, by, rw, bg_stack


def _section_style_for(
    child: LayoutNode, theme: Theme, in_levels: frozenset[int]
) -> tuple[int | None, SectionStyle | None]:
    """Active section style for ``child`` if it opens a new heading section.

    Returns ``(level, style)`` when ``child.section_level`` is a level with an
    active theme style that no ancestor has already opened; otherwise
    ``(None, None)``. Detection is done by the parent branch — ``col``, ``row``,
    and ``layout`` (the document body, which IS a section when the whole document
    is one heading section).

    A node with 2+ direct children at its own level is a *container* of same-level
    sections: by default it is transparent (each child is wrapped on its own); a
    ``row`` container is wrapped as one merged section only when that level sets
    ``merge_rows`` (col containers, incl. the root, are always transparent).
    """
    level = child.section_level
    if level is None or level in in_levels:
        return None, None
    style = resolve_section_style(theme, level, child.section_style_key)
    if style is None or not style.is_active():
        return None, None
    same_level = sum(1 for c in child.children if c.section_level == level)
    if same_level >= 2:
        if (
            child.type == "row"
            and style.merge_rows
            and _row_backgrounds_match(child, level)
        ):
            return level, style
        return None, None
    return level, style
