"""Text style and metrics: how big a piece of text is, and what it looks like.

This is the module BOTH halves of the renderer depend on. Measurement asks it how
wide a word is; painting asks it which font and colour to use. Because they ask
the *same* function, they cannot disagree -- which is the whole point of ADR-400,
and why this module had to come out before measurement and painting could be
separated at all.

Owns:

  * **style resolution** -- a node plus a theme becomes a concrete font, size,
    weight and ink (`_effective_text_fonts`, `_kv_role_style`, `_heading_fonts`,
    `_resolve_link`, `_table_text_style`);
  * **metrics** -- the sizes that follow from that style (`_measure_word`,
    `_wrap_lines`, `_chip_metrics`, `_link_pill_size`, `_emoji_badge_size`).

Owns no drawing: nothing here takes a canvas, and nothing here may. A function
that needs a canvas belongs in the renderer; a size it needs belongs here.
"""

import dataclasses
import re
from pathlib import Path

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.render_colors import (
    _replace_color,
    _rotate_color,
    _rotation_slot,
)
from md2ui.pipeline.render_text import LINK_DESTINATION, LINK_LABEL
from md2ui.pipeline.render_text_scopes import (
    _kv_role_style as _kv_role_style,
    _has_local_font,
    _node_text_context,
    _own_face,
    _sizing_tier,
    _style_fonts,
    _text_style_scopes as _text_style_scopes,
    scoped_text_style,
)
from md2ui.pipeline.theme import (
    EmojiBadgeStyle,
    EmojiTextStyle,
    InlineCodeTheme,
    LinkStyle,
    TextStyle,
    Theme,
)
from md2ui.pipeline.theme_model import muted_color, muted_shadows
from md2ui.utils.font_loader import make_font, styled_font, varied_face, weight_from_str

# Air between a ring's inner edge and the text inside it.
_RING_TEXT_MARGIN = 4.0

# Absolute inline-code text size (px), from the effective inline-code text style
# (## Text Styles > Inline Code, or body font at 14 by default). Set right after
# each parse_theme so the layout-measurement pass and the draw pass (both routed
# through _span_font) stay consistent. _span_font is a pure helper without theme
# access, hence a global.
_INLINE_CODE_SIZE = 14.0
"""Inline-code font size, baked from the theme's BASE style once at load.

Module-level *mutable* state, so it has to be written through the setter below.
When this lived in ``layout_render`` the renderer set it with a bare ``global``;
after the split that statement would bind a NEW global in the RENDERER's
namespace and leave the readers here on the default -- silently, because a
rebind is not an error. The setter makes the cross-module write explicit and
impossible to get wrong.
"""


def set_inline_code_size(size: float) -> None:
    """Bake the inline-code size from the theme. Call on load and on reload."""
    global _INLINE_CODE_SIZE
    _INLINE_CODE_SIZE = size


HEADING_SIZES = {1: 28, 2: 22, 3: 18, 4: 15, 5: 13, 6: 12}
_LINK_RE = re.compile(rf"^\[({LINK_LABEL})\]\({LINK_DESTINATION}\)$", re.DOTALL)


def _parse_link_label(content: str) -> str:
    """Extract the display label from a markdown link ``[label](url)``.

    Fallback only: markdown_grouper.py classifies variant/label once at
    AST-build time (``link_variant``/``link_label`` on the node dict); this is
    a safety net for a ``grouping-ast.json`` that lacks them.
    """
    m = _LINK_RE.match(content.strip())
    return m.group(1) if m else content


def _code_size(theme: "Theme", variant: str | None) -> float:
    """Font size for a chip of *variant*.

    ``_INLINE_CODE_SIZE`` is a module global baked from the BASE style at
    startup, so it cannot express a per-variant size. A variant that states its
    own ``## Text Styles > Inline Code <Variant>`` size wins; everything else
    falls back to that global, keeping the un-themed path byte-identical.
    Measurement and drawing both resolve through here, so a bigger chip is also
    measured bigger and its pill never clips.
    """
    if variant:
        style = theme.inline_code.resolved(variant)
        if style.text_style is not None:
            return style.text_style.font_size
    return _INLINE_CODE_SIZE


def _disabled_link_style(style: "LinkStyle") -> "LinkStyle":
    """*style* with its disabled paint swapped in.

    Only paint changes — geometry, padding and emoji shape stay the variant's
    own, so a disabled button occupies exactly the same box and every
    measurement path stays correct without knowing about the state at all. An
    unset disabled color falls back to the ordinary one; a variant with none of
    them set takes the default mute (``muted_color``), so a Text button
    — which resolves onto bare defaults, not Primary's — is never drawn enabled.
    Its shadows fade as a muted chip's and badge's do, always, and so does its
    background image, where it is painted.
    """
    d_fill, d_text = style.disabled_fill_color, style.disabled_text_color
    stated = d_fill is not None or d_text is not None
    stated = stated or style.disabled_stroke_color is not None
    ts = style.text_style
    if ts is not None:
        ts = dataclasses.replace(ts, color=muted_color(ts.color, d_text, stated))
    return dataclasses.replace(
        style,
        fill_color=muted_color(style.fill_color, d_fill, stated),
        stroke_color=muted_color(
            style.stroke_color, style.disabled_stroke_color, stated
        ),
        text_style=ts,
        shadows=muted_shadows(style.shadows),
    )


def _resolve_link(nd: dict, theme: "Theme") -> tuple[str, str, bool, "LinkStyle"]:
    """O(1) lookup of a LINK node's (variant, label, is_emoji, style).

    variant/label/is_emoji were classified once in markdown_grouper.py at
    AST-build time; this just reads them back plus the fully concrete style
    for that variant, merged onto Primary (``theme.py``'s
    ``LinksTheme.resolved``). There is no separate "emoji" style — a pure-
    emoji label (``is_emoji``) forces this *same* variant's configured
    ``emoji_shape`` at render time instead of switching styles.

    The DISABLED state (``~~[x](/y)~~``) is folded into the returned style
    rather than returned alongside it: it only swaps colors, so every caller —
    the two measurers, the baseline pass, the drawer, the debug rect — gets it
    for free and none of them needs to know the state exists.

    COLOR ROTATION folds in the same way and for the same reason, just before
    the disabled swap so an explicitly disabled button still wins.
    """
    variant = nd.get("link_variant") or "primary"
    label = nd.get("link_label")
    if label is None:
        label = _parse_link_label(nd.get("content", ""))
    is_emoji = bool(nd.get("link_is_emoji", False))
    style = theme.links.resolved(variant)
    style = _rotated_link_style(style, nd, theme)
    if nd.get("link_disabled"):
        style = _disabled_link_style(style)
    return variant, label, is_emoji, style


def _rotated_link_style(style: "LinkStyle", nd: dict, theme: "Theme") -> "LinkStyle":
    """*style* with this link's slot picked out of its color lists.

    Only colors change, exactly like ``_disabled_link_style`` — the geometry,
    padding and emoji shape stay the variant's own, so every measurement path
    stays correct without knowing rotation exists. A no-op unless the theme
    listed two or more colors for a fill, stroke or label.
    """
    if not (
        style.fill_colors
        or style.stroke_colors
        or (style.text_style is not None and style.text_style.colors)
    ):
        return style
    idx, chain = _rotation_slot(nd, theme)
    ts = style.text_style
    if ts is not None and ts.colors:
        ts = dataclasses.replace(
            ts,
            color=_rotate_color(ts.colors, ts.color, idx, theme, "link", chain),
        )
    return dataclasses.replace(
        style,
        fill_color=_rotate_color(
            style.fill_colors, style.fill_color, idx, theme, "link", chain
        ),
        stroke_color=_rotate_color(
            style.stroke_colors, style.stroke_color, idx, theme, "link", chain
        ),
        text_style=ts,
    )


# Cache of per-context filled emoji typefaces loaded from theme font paths, so a
# ``### Text|Link|Inline`` ``Font:`` override is only decoded once, not per draw.
_EMOJI_TF_CACHE: dict[str, "skia.Typeface | None"] = {}


def _load_emoji_typeface(
    path: str | None, default: "skia.Typeface | None"
) -> "skia.Typeface | None":
    """Resolve an emoji ``Font:`` override path to a typeface (cached).

    Falls back to ``default`` (the theme's default emoji font) when the path is
    unset or fails to load."""
    if not path:
        return default
    if path not in _EMOJI_TF_CACHE:
        tf = None
        try:
            if Path(path).exists():
                tf = skia.Typeface.MakeFromFile(path)
        except Exception:
            tf = None
        _EMOJI_TF_CACHE[path] = tf
    return _EMOJI_TF_CACHE[path] or default


def _prose_emoji_paint(
    emoji_style: "EmojiTextStyle | None",
    styled: bool,
    fonts: "FontSet",
    bg_stack: tuple,
    theme: "Theme",
) -> tuple[skia.Typeface, int | None, dict[str, int] | None]:
    """The face, tint and pins for an UNSLICED emoji sitting inside a run of text
    — ``(font, color_or_None, fixed_or_None)``. ``None`` for the colour means
    "use the surrounding text's".

    ``Color`` under ``## Emoji styles > ### Text`` is the DEFAULT tint for such a
    glyph, **not an override**: in *styled* text — a ``## Text Styles`` tier, a
    table role, a heading, a K-V role, a ``## Fixed colors`` text pin — the glyph
    follows the text. Only plain body text keeps the tint.

    *styled* is said by whoever resolved the style (``_prose_text_is_styled``),
    never inferred from the ink: the default Lead shares body Text's colour, and
    reading "same colour as body" as "unstyled" left ``__"❤️" Lead__`` tinted
    while every other tier won.

    A per-glyph ``### Emoji`` pin is NOT replaced and is not subject to the
    cascade: it is an explicit statement about that glyph (❤️ red, 🔻 red), not a
    style inherited from its surroundings, so it outranks both.

    Here rather than in the painter because it decides an INK, which is this
    module's job.

    The face is the one *fonts* carries, never ``emoji_style``'s own: a `Font:`
    override reaches prose through ``_effective_text_fonts``, which measurement
    reads too, so the glyph paints in the face it was measured in (ADR-400).
    """
    if emoji_style is None:
        return fonts.emoji, None, None
    tint = (
        _replace_color(emoji_style.color, bg_stack, theme)
        if emoji_style.color is not None and not styled
        else None
    )
    return fonts.emoji, tint, emoji_style.fixed_colors


def _prose_text_is_styled(
    node_type: str,
    heading_ctx: int,
    table_role: str | None,
    text_style: str | None,
    weight: str | None,
    rp: dict | None,
    theme: Theme,
) -> bool:
    """Whether a style more specific than body Text set a prose leaf's colour —
    the *styled* ``_prose_emoji_paint`` asks about.

    Mirrors the order the prose drawer resolves its colour in: a heading, then a
    table role or else a tier or the key style, then the muted weight, a K-V
    role and a date-chip role. A ``## Fixed colors`` pin is the drawer's to add.
    A section-scoped ``Text`` is still body text.
    """
    if heading_ctx:
        return True
    if table_role:
        if _table_text_style(theme, table_role) is not None:
            return True
    elif text_style or node_type == "key":
        return True
    rp = rp or {}
    return bool(
        (weight == "less" and not text_style)
        or (rp.get("kv_role") and not text_style)
        or rp.get("date_role")
    )


def _span_font(fonts: "FontSet", size: float, bold: bool, italic: bool) -> skia.Font:
    """The font one styled span draws with.

    ``code`` marks a MARKER — an inline ``code`` span that stayed inside its text
    run — and deliberately changes nothing here: a marker keeps the surrounding
    text's face, size and bold/italic, and is distinguished only by its paint
    (``## Text Styles`` ``Marker …`` keys). ``mono_tf`` / ``_INLINE_CODE_SIZE``
    belong to the standalone ``inline_code`` element (``draw_code_box``) instead.
    """
    if italic:
        return styled_font(fonts.bold_italic if bold else fonts.italic, size, True)
    return make_font(fonts.bold if bold else fonts.typeface, size)


def _heading_level(label: str) -> int:
    """Extract heading level from a node label like 'heading3' → 3. Clamps to 1–6."""
    m = re.search(r"(\d+)$", label)
    return max(1, min(6, int(m.group(1)))) if m else 1


def _resolve_h_align(rp: dict | None, theme: Theme) -> str:
    """Resolve a leaf's horizontal alignment from its RENDER HINTS.

    ``text_align`` is the most specific; ``content_align`` (which may have been
    cascaded from an ancestor group/root) is next; the global
    ``theme.root.align`` is the fallback default ("left").

    Pass ``box.render_properties`` — never the grouping node. A grouping node
    carries neither key: the grouper writes the spring's alignment as
    ``authored_align`` and the generator mints ``content_align`` from it into
    ``render_properties``. Handing a node in therefore never *fails*, it just
    silently returns ``theme.root.align``, which is how ``... ☀️`` / ``... `x` ``
    / ``... [Buy](/b)`` stayed left while ``... 42`` went right.
    """
    rp = rp or {}
    return rp.get("text_align") or rp.get("content_align") or theme.root.align or "left"


def _weight_scale_and_color(
    theme: Theme,
    weight: str | None,
    base_color: int,
    text_style: str | None = None,
) -> tuple[float, int]:
    """Map a ``content_weight`` tier to a (size scale, color) pair.

    ``first``/``second`` only scale the size; ``less`` also swaps to the muted
    color. A missing/unknown weight is a no-op (1.0, base_color).

    An authored ``text_style`` tier suppresses it outright: ``content_weight`` is
    not the author's choice, and scaling an explicitly-sized ``___$12,480.55___`` by
    someone else's guess is never what the author asked for.
    """
    if text_style:
        return 1.0, base_color
    cw = theme.content_weight
    if weight == "first":
        return cw.first_scale, base_color
    if weight == "second":
        return cw.second_scale, base_color
    if weight == "less":
        return cw.less_scale, cw.less_color
    return 1.0, base_color


@dataclasses.dataclass
class FontSet:
    """Full typeface set shared by measuring and drawing text.

    Bundling these means the measurement code (``_leaf_height`` /
    ``_leaf_natural_width``) and the drawing code (``draw_styled_text_box``) wrap
    and size text with the *same* fonts, so a box never reserves less than what
    gets drawn into it. ``heading_typefaces`` maps a heading level to its
    ``(regular, italic, bold, bold_italic)`` typefaces, mirroring ``main()``'s
    resolution — the bold pair is what lets ``**x**`` inside a heading render in
    the heading's own family instead of the body bold face.
    """

    typeface: skia.Typeface
    bold: skia.Typeface
    italic: skia.Typeface
    bold_italic: skia.Typeface
    mono: skia.Typeface
    emoji: skia.Typeface | None = None
    heading_typefaces: dict[
        int, tuple[skia.Typeface, skia.Typeface, skia.Typeface, skia.Typeface]
    ] = dataclasses.field(default_factory=dict)
    # Dedicated fenced/indented block face. Kept separate from ``mono`` because
    # inline chips and block code have independent ## Text Styles roles.
    code_block: skia.Typeface | None = None
    # The faces an emoji in prose (`### Text`) and in a link label (`### Link`)
    # draw in, resolved once with the fonts so measurement and paint read the
    # same face (ADR-400). Without a `Font:` override, the default ``emoji``.
    text_emoji: skia.Typeface | None = None
    link_emoji: skia.Typeface | None = None
    # The emoji font each element's `Emoji weight` / `fill` / `grade` / `optical
    # size` set, keyed ``badge`` / ``link`` / ``chip`` (``render_text_scopes.
    # emoji_paths``). Read only through the methods below, which measurement and
    # paint both call (ADR-400).
    emoji_paths: dict[str, str] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        self.text_emoji = self.text_emoji or self.emoji
        self.link_emoji = self.link_emoji or self.emoji

    def varied_emoji(
        self,
        element: str,
        style: LinkStyle | InlineCodeTheme | EmojiBadgeStyle,
        face: skia.Typeface | None,
        size: float,
    ) -> skia.Typeface | None:
        """*face*, or the face of *element*'s emoji font that *style*'s emoji
        keys ask for, drawn at *size*."""
        path = self.emoji_paths.get(element)
        asked = (style.emoji_weight, *style.emoji_axes.at(size))
        if path is None or asked == (None, None, None, None):
            return face
        return varied_face(path, *asked) or face

    def emoji_badge(
        self, nd: dict, theme: Theme, ink: int | None = None
    ) -> tuple[EmojiBadgeStyle, skia.Typeface | None]:
        """An emoji badge's style (muted when *nd* is, *ink* its glyph's colour
        when the badge states none), and the face its glyph draws in."""
        style = theme.emojis.resolved(nd.get("emoji_variant"), nd, ink)
        return style, self.varied_emoji("badge", style, self.emoji, style.icon_size)

    def chip_emoji(self, variant: str | None, theme: Theme) -> skia.Typeface | None:
        """The face an emoji in a chip of *variant* draws in."""
        face = _load_emoji_typeface(theme.emojis.inline.font_path, self.emoji)
        style = theme.inline_code.resolved(variant)
        return self.varied_emoji("chip", style, face, _code_size(theme, variant))


# Table cell/key typefaces resolved once in main() from the ## Tables text
# styles (keys "header" | "cells" | "keys" → (regular, italic)); empty when the
# theme sets none. Module-level like _INLINE_CODE_SIZE so measurement and
# drawing share it without threading a parameter through every call site.
_TABLE_TYPEFACES: dict[str, tuple[skia.Typeface, skia.Typeface]] = {}


def _table_text_style(theme: Theme, role: str) -> "TextStyle | None":
    """THEME.md table text style for a cell role ("header" | "body") or "keys"."""
    tt = theme.tables
    if role == "header":
        return tt.header_text
    if role == "keys":
        return tt.keys_text
    return tt.cells_text


def _heading_fonts(level: int, fonts: FontSet, theme: Theme) -> tuple[FontSet, float]:
    """The (fonts, size) a heading level renders with.

    All four faces are swapped, not just regular+italic: ``**bold**`` inside a
    heading must come out in the heading's own family at heading weight (see
    ``main()``'s ``heading_typefaces``), otherwise a role inside a heading
    falls back to the body bold face."""
    ts = theme.headings.get(level)
    size = ts.font_size if ts else HEADING_SIZES[level]
    if fonts.heading_typefaces and level in fonts.heading_typefaces:
        h_tf, h_italic_tf, h_bold_tf, h_bold_italic_tf = fonts.heading_typefaces[level]
    else:
        h_weight = weight_from_str(ts.font_weight) if ts else 400
        h_tf = fonts.bold if h_weight >= 700 else fonts.typeface
        h_italic_tf = fonts.bold_italic if h_weight >= 700 else fonts.italic
        h_bold_tf = fonts.bold
        h_bold_italic_tf = fonts.bold_italic
    return dataclasses.replace(
        fonts,
        typeface=h_tf,
        italic=h_italic_tf,
        bold=h_bold_tf,
        bold_italic=h_bold_italic_tf,
    ), size


def _effective_text_fonts(
    node_type: str,
    atx_level: int,
    fonts: FontSet,
    theme: Theme,
    table_role: str | None = None,
    heading_ctx: int = 0,
    text_style: str | None = None,
    text_scopes: tuple[str, ...] = (),
    node: object | None = None,
) -> tuple[FontSet, float]:
    """Resolve a leaf's effective fonts + base size, mirroring ``draw_content_box``.

    Headings swap in their level-specific typefaces and the themed heading size;
    a table cell (``table_role``) swaps in its themed table text style; body text
    keeps the base fonts at ``theme.text.font_size``. The ``content_weight``
    scale is applied by the caller.

    ``text_style`` is an authored display tier (``muted``/``lead``/``display``),
    stamped by the grouper when a whole leaf was wrapped in underscores. It beats
    the K-V key branch — an explicit instruction outranks the key style — but loses to a heading, which is a heading first (mirroring how
    ``_apply_kv_role`` steps aside on a heading line).

    ``heading_ctx`` is the level of the heading LINE a piece was split out of
    (stamped by ``_walk``). It only replaces the plain-body fallback, so table
    cells, K-V keys and the caller's kv-role / date-chip / bar overrides keep
    winning exactly as they do outside a heading.
    """
    if node is not None:
        table_role, heading_ctx, text_style, text_scopes = _node_text_context(node)
    text_style = _sizing_tier(node_type, text_style)
    heading = atx_level or node_type.startswith("heading")
    if not heading and fonts.text_emoji is not fonts.emoji:
        # Everything but a heading is prose: its emoji draw in `### Text`'s face.
        fonts = dataclasses.replace(fonts, emoji=fonts.text_emoji)
    if table_role and not heading:
        ts = _table_text_style(theme, table_role)
        if ts is not None:
            key = "header" if table_role == "header" else "cells"
            pair = _TABLE_TYPEFACES.get(key)
            if pair is not None:
                t_tf, t_italic_tf = pair
            else:
                t_weight = weight_from_str(ts.font_weight)
                t_tf = fonts.bold if t_weight >= 700 else fonts.typeface
                t_italic_tf = fonts.bold_italic if t_weight >= 700 else fonts.italic
            return dataclasses.replace(
                fonts, typeface=t_tf, italic=t_italic_tf
            ), ts.font_size
    if heading:
        return _heading_fonts(atx_level or _heading_level(node_type), fonts, theme)
    # An authored tier (`_x_` / `__x__` / `___x___`).
    if text_style:
        ds = scoped_text_style(theme, text_style, text_scopes)
        body = scoped_text_style(theme, "text", text_scopes)
        if _has_local_font(theme, text_style, text_scopes) or _own_face(ds, body):
            return _style_fonts(ds, fonts), ds.font_size
        d_weight = weight_from_str(ds.font_weight)
        d_tf = fonts.bold if d_weight >= 700 else fonts.typeface
        d_italic_tf = fonts.bold_italic if d_weight >= 700 else fonts.italic
        return dataclasses.replace(
            fonts, typeface=d_tf, italic=d_italic_tf
        ), ds.font_size
    # A display pair's key takes the ``Key`` style (font/size), body text when
    # the theme sets none (see draw_content_box for the matching color).
    if node_type == "key":
        ks = scoped_text_style(theme, "key", text_scopes)
        if _has_local_font(theme, "key", text_scopes):
            return _style_fonts(ks, fonts), ks.font_size
        k_weight = weight_from_str(ks.font_weight)
        k_tf = fonts.bold if k_weight >= 700 else fonts.typeface
        k_italic_tf = fonts.bold_italic if k_weight >= 700 else fonts.italic
        return dataclasses.replace(
            fonts, typeface=k_tf, italic=k_italic_tf
        ), ks.font_size
    # A piece split off a heading line keeps that heading's text style.
    if heading_ctx:
        return _heading_fonts(heading_ctx, fonts, theme)
    body = scoped_text_style(theme, "text", text_scopes)
    if _has_local_font(theme, "text", text_scopes):
        return _style_fonts(body, fonts), body.font_size
    return fonts, body.font_size


_BOLD_WEIGHTS = frozenset(
    {"bold", "semibold", "extrabold", "black", "600", "700", "800", "900"}
)


def _marker_font(lm: dict, fonts: FontSet, theme: Theme) -> tuple[skia.Font, float]:
    """The font a *text* gutter marker (numbered ordinal / quote char) draws with.

    Shared by ``_leaf_height`` / ``_leaf_natural_width`` / ``_draw_list_marker``
    so the reserved cell is measured with the same face the drawer uses — the
    weight matters (bold "10" is ~4px wider than regular at 64px).
    """
    size = float(lm.get("font_size", theme.text.font_size))
    weight = str(lm.get("font_weight", "")).lower()
    tf = fonts.bold if weight in _BOLD_WEIGHTS else fonts.typeface
    return make_font(tf, size), size


def _effective_leaf_node(nd: dict | None, rp: dict | None) -> dict | None:
    """Apply baked or overridden text before any leaf measurement/drawing.

    With `### Dates → Enabled: no` the generator collapses the grouper's
    key/day pair back to one baked leaf carrying ``date_text``. It has no
    ``content_id``, so every path that resolves a leaf through ``node_index``
    would otherwise see no node: the text would size to nothing and be pushed
    around the row. Returning a plain text node lets it behave as the ordinary
    line it is.

    THE single normalization point for a leaf with no markdown node behind it.
    Each of the four leaf paths must go through it or they drift apart — which
    is exactly what happened: wired into the width and draw paths only, the
    height fell back to ``theme.text.font_size`` (one font size, not one LINE),
    so ``Aug 12`` drew into a box 6px too short and lost its descender, and the
    missing baseline dropped it off its row's line. ``_leaf_height``,
    ``_leaf_first_baseline`` and ``_leaf_natural_width`` all call it on entry;
    ``draw_content_box`` calls it on the node it is handed. Any new
    ``_leaf_*``-style helper must call it too.

    ``text_override`` keeps the real node's type and styling while replacing
    its visible content (used by unit-ratio bars that hide the denominator).
    This normalization must remain shared by every leaf path so measurement
    and drawing cannot disagree.
    """
    props = rp or {}
    override = props.get("text_override")
    if override is not None and nd is not None:
        return {**nd, "content": str(override)}
    text = props.get("date_text")
    if nd is None and text:
        return {
            "type": "text",
            "content": text,
            "text_style_chain": props.get("text_style_chain", []),
        }
    return nd


def _table_key_fonts(fonts: FontSet, theme: Theme) -> tuple[FontSet, float, int]:
    """Effective ``(fonts, size, color)`` for stacking-cards key labels."""
    ts = theme.tables.keys_text or theme.labels
    pair = _TABLE_TYPEFACES.get("keys")
    if pair is not None:
        k_tf, k_italic_tf = pair
    else:
        k_weight = weight_from_str(ts.font_weight)
        k_tf = fonts.bold if k_weight >= 700 else fonts.typeface
        k_italic_tf = fonts.bold_italic if k_weight >= 700 else fonts.italic
    return (
        dataclasses.replace(fonts, typeface=k_tf, italic=k_italic_tf),
        ts.font_size,
        ts.color,
    )


def _emoji_glyph_font(
    emoji_tf: "skia.Typeface | None",
    fallback_tf: "skia.Typeface",
    size: float,
) -> "skia.Font":
    """A Font at ``size`` using the emoji typeface, or ``fallback_tf`` if none."""
    return make_font(emoji_tf if emoji_tf is not None else fallback_tf, size)


def _ring_text_style(theme: Theme, role: str) -> TextStyle:
    """Effective text style for a ring role ("value" | "unit")."""
    rt = theme.datapoints.ring
    if role == "value":
        return rt.value_text or TextStyle(
            font_size=theme.text.font_size * 1.8,
            font_weight="bold",
            color=theme.text.color,
        )
    return rt.unit_text or theme.labels


def _apply_ring_role(
    rp: dict | None,
    eff_fonts: FontSet,
    size: float,
    color: int,
    theme: Theme,
    base_fonts: FontSet,
) -> tuple[FontSet, float, int]:
    """Swap in the ### Ring value/unit text style for a ring text leaf (mirrors
    ``_apply_date_role``). The value auto-fits to the ring's inner diameter in
    the draw path, so this returns the style's nominal size."""
    role = (rp or {}).get("ring_role")
    if not role:
        return eff_fonts, size, color
    ts = _ring_text_style(theme, role)
    if weight_from_str(ts.font_weight) >= 700:
        eff_fonts = dataclasses.replace(
            eff_fonts, typeface=base_fonts.bold, italic=base_fonts.bold_italic
        )
    return eff_fonts, ts.font_size, ts.color


def _date_chip_text_style(theme: Theme, role: str) -> TextStyle:
    """Effective text style for a date-chip role ("key" | "day")."""
    dc = theme.datapoints.date_chip
    if role == "key":
        return dc.key_text or theme.labels
    return dc.day_text or TextStyle(
        font_size=theme.text.font_size * 1.5,
        font_weight="bold",
        color=theme.text.color,
    )


def _apply_date_role(
    rp: dict | None,
    eff_fonts: FontSet,
    size: float,
    color: int,
    theme: Theme,
    base_fonts: FontSet,
) -> tuple[FontSet, float, int]:
    """Swap in the ### Date Key / ### Date Day text style for a chip leaf
    carrying a ``date_role``. No-op otherwise (mirrors ``_apply_kv_role``)."""
    role = (rp or {}).get("date_role")
    if not role:
        return eff_fonts, size, color
    ts = _date_chip_text_style(theme, role)
    if weight_from_str(ts.font_weight) >= 700:
        eff_fonts = dataclasses.replace(
            eff_fonts, typeface=base_fonts.bold, italic=base_fonts.bold_italic
        )
    return eff_fonts, ts.font_size, ts.color


def _date_role_content(rp: dict | None, content: str) -> str:
    """The key leaf renders uppercased (JUN / MON); the day leaf as-is."""
    if (rp or {}).get("date_role") == "key":
        return content.upper()
    return content


def _apply_kv_role(
    rp: dict | None,
    eff_fonts: FontSet,
    size: float,
    color: int,
    theme: Theme,
    base_fonts: FontSet,
    heading_ctx: int = 0,
    text_style: str | None = None,
    text_scopes: tuple[str, ...] = (),
    node: object | None = None,
) -> tuple[FontSet, float, int]:
    """Swap in the ``Key`` / ``Value`` text style when this box is one side of a
    key-value pair. No-op otherwise.

    The generator stamps ``kv_role`` only when the theme authored the block, so
    a theme that sets neither never reaches here and renders as it always did.

    On a heading line (``heading_ctx``) the heading's own style wins:
    `## Monthly Budget: $2,450` is a heading first — its value stays at the
    heading size, its key takes the ``Key`` style.

    An authored ``text_style`` tier also wins: it was already resolved by
    ``_effective_text_fonts``, and re-applying a role on top would size the leaf
    twice. An explicit instruction outranks the theme's uniform default."""
    if node is not None:
        _table_role, heading_ctx, text_style, text_scopes = _node_text_context(node)
    role = (rp or {}).get("kv_role")
    if not role or heading_ctx or _sizing_tier(role, text_style):
        return eff_fonts, size, color
    ts = _kv_role_style(theme, role, text_scopes)
    if _has_local_font(theme, role, text_scopes):
        # The family is the role's own; the emoji face stays the leaf's.
        eff_fonts = _style_fonts(
            ts, dataclasses.replace(base_fonts, emoji=eff_fonts.emoji)
        )
    elif weight_from_str(ts.font_weight) >= 700:
        eff_fonts = dataclasses.replace(
            eff_fonts, typeface=base_fonts.bold, italic=base_fonts.bold_italic
        )
    # A muted key (the one tier left standing here) keeps the ink it was handed.
    return eff_fonts, ts.font_size, color if text_style else ts.color
