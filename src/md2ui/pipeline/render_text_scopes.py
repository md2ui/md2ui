"""Resolve styles declared at structural levels and their text typefaces.

The grouper supplies an outer-to-inner scope chain. This module overlays the
partial role patches from ``Theme`` and owns the custom-family cache shared by
measurement and drawing (ADR-400). It does not measure or paint.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.theme import (
    _CHIP_VARIANTS,
    TextStyle,
    Theme,
    tier_style,
)
from md2ui.pipeline.theme_model import LINK_BUTTON_VARIANTS, HorizontalRuleTheme
from md2ui.pipeline.render_glyph_faces import _has_glyph
from md2ui.pipeline.render_text import (
    OVERFLOW_MARKS,
    _split_emoji_runs,
    link_label_spans,
)
from md2ui.utils.font_loader import (
    load_custom_fonts,
    resolve_typeface,
    make_font,
    styled_font,
    weight_from_str,
)

if TYPE_CHECKING:
    from md2ui.pipeline.render_style import FontSet


_TEXT_TYPEFACES: dict[
    tuple[str, int],
    tuple[skia.Typeface, skia.Typeface, skia.Typeface, skia.Typeface],
] = {}


def load_theme_font_context(theme: Theme) -> tuple[dict, str, int]:
    """Load the base font context and prepare every local family/weight pair."""
    custom_fonts = load_custom_fonts(theme.font_paths)
    font_name = theme.text.font_name or "Arial"
    base_weight = weight_from_str(theme.text.font_weight)
    configure_text_typefaces(theme, custom_fonts, font_name, base_weight)
    configure_chip_typefaces(theme, custom_fonts)
    configure_link_typefaces(theme, custom_fonts)
    return custom_fonts, font_name, base_weight


def configure_text_typefaces(
    theme: Theme, custom_fonts: dict, base_font_name: str, base_weight: int
) -> None:
    """Resolve family/weight combinations reachable from local declarations."""
    names: set[str] = set()
    weights: set[int] = set()
    local_font_property = False
    for scope_patches in theme.text_style_overrides.values():
        for patch in scope_patches.values():
            if "font_name" in patch.declared:
                names.add(patch.style.font_name or base_font_name)
                local_font_property = True
            if "font_weight" in patch.declared:
                weights.add(weight_from_str(patch.style.font_weight))
                local_font_property = True

    _TEXT_TYPEFACES.clear()
    tiers = (theme.muted, theme.lead, theme.display)
    if not local_font_property and not any(
        _own_face(t, theme.text) for t in tiers if t is not None
    ):
        return
    names.add(base_font_name)
    weights.update({base_weight, 400, 700})
    for role_style in (
        theme.text,
        theme.muted,
        theme.lead,
        theme.display,
        theme.key_style,
        theme.value_style,
    ):
        if role_style is not None:
            names.add(role_style.font_name or base_font_name)
            weights.add(weight_from_str(role_style.font_weight))
    for name in names:
        for weight in weights:
            bold_weight = max(weight, 700)
            _TEXT_TYPEFACES[(name.casefold(), weight)] = (
                resolve_typeface(name, weight, False, custom_fonts),
                resolve_typeface(name, weight, True, custom_fonts),
                resolve_typeface(name, bold_weight, False, custom_fonts),
                resolve_typeface(name, bold_weight, True, custom_fonts),
            )


# A chip variant's face, keyed like ``_TEXT_TYPEFACES`` by (family, weight). Only
# pairs that differ from the base chip's are held; every other chip draws in
# ``FontSet.mono``, so a theme whose variants state no family or weight of their
# own draws every chip in the base chip's face.
_CHIP_TYPEFACES: dict[tuple[str, int], skia.Typeface] = {}


def _chip_face_key(ts: TextStyle, theme: Theme) -> tuple[str, int]:
    """The (family, weight) a chip text style resolves, as ``FontSet.mono`` is."""
    name = ts.font_name or theme.text.font_name or "Arial"
    weight = weight_from_str(ts.font_weight) or weight_from_str(theme.text.font_weight)
    return name.casefold(), weight


def configure_chip_typefaces(theme: Theme, custom_fonts: dict) -> None:
    """Resolve the face of every chip variant whose family or weight is its own."""
    _CHIP_TYPEFACES.clear()
    base = _chip_face_key(theme.inline_code.effective_text_style(theme.text), theme)
    for variant in _CHIP_VARIANTS:
        style = theme.inline_code.resolved(variant).effective_text_style(theme.text)
        key = _chip_face_key(style, theme)
        if key != base and key not in _CHIP_TYPEFACES:
            name = style.font_name or theme.text.font_name or "Arial"
            _CHIP_TYPEFACES[key] = resolve_typeface(name, key[1], False, custom_fonts)


def chip_face(theme: Theme, variant: str | None, mono: skia.Typeface) -> skia.Typeface:
    """The face a chip of *variant* draws its label in; *mono* is the base chip's.

    A variant's text style inherits the base ``Inline Code`` one and overrides
    what it states (theme.py), so a variant naming another family or weight
    resolves its own face here. Measurement and paint both come through this
    one lookup (ADR-400), by way of ``render_metrics._code_font``.
    """
    if not variant:
        return mono
    style = theme.inline_code.resolved(variant).effective_text_style(theme.text)
    return _CHIP_TYPEFACES.get(_chip_face_key(style, theme), mono)


# A link label's faces (regular, bold, italic, bold italic), keyed by the
# (family, weight) its variant's text style resolves. Only pairs that differ from
# the body's are held; every other label draws in the body's own faces.
_LINK_TYPEFACES: dict[
    tuple[str, int],
    tuple[skia.Typeface, skia.Typeface, skia.Typeface, skia.Typeface],
] = {}
_LINK_VARIANTS = ("primary", *LINK_BUTTON_VARIANTS, "text")


def _link_face_key(ts: TextStyle, theme: Theme) -> tuple[str, int]:
    """The (family, weight) a link text style resolves; unstated means the body's."""
    name = ts.font_name or theme.text.font_name or "Arial"
    return name.casefold(), weight_from_str(ts.font_weight or theme.text.font_weight)


def configure_link_typefaces(theme: Theme, custom_fonts: dict) -> None:
    """Resolve the faces of every link variant whose family or weight is its own."""
    _LINK_TYPEFACES.clear()
    base = _link_face_key(theme.text, theme)
    for variant in _LINK_VARIANTS:
        style = theme.links.resolved(variant).text_style
        if style is None:
            continue
        key = _link_face_key(style, theme)
        if key == base or key in _LINK_TYPEFACES:
            continue
        name = style.font_name or theme.text.font_name or "Arial"
        bold = max(key[1], 700)
        _LINK_TYPEFACES[key] = (
            resolve_typeface(name, key[1], False, custom_fonts),
            resolve_typeface(name, bold, False, custom_fonts),
            resolve_typeface(name, key[1], True, custom_fonts),
            resolve_typeface(name, bold, True, custom_fonts),
        )


def link_faces(
    theme: Theme, ts: TextStyle | None, fonts: FontSet
) -> tuple[skia.Typeface, skia.Typeface, skia.Typeface, skia.Typeface]:
    """(regular, bold, italic, bold italic) of the text style a link label uses.

    A label draws in its variant's ``## Text Styles`` block's family and weight;
    a block that names neither keeps the body's faces. Measurement, paint and
    the click target all come through this one lookup (ADR-400).
    """
    body = (fonts.typeface, fonts.bold, fonts.italic, fonts.bold_italic)
    if ts is None:
        return body
    return _LINK_TYPEFACES.get(_link_face_key(ts, theme), body)


# Where each emphasis sits in ``link_faces``: bold adds 1, italic adds 2.
_EMPHASIS_FACE = {None: 0, "bold": 1, "italic": 2, "bold_italic": 3}


def link_label_fonts(
    nd: dict, label: str, fonts: FontSet, theme: Theme, size: float
) -> tuple[skia.Font, list[tuple[str, skia.Font]], skia.Typeface | None]:
    """A button label's font, the ``(text, font)`` runs it is drawn in, and the
    face its emoji draw in.

    Every face is one of the link variant's own family (``link_faces``): the
    label's emphasis picks its bold or italic, never another style. The first
    font is the label's own face, whose metrics size the pill. ``link_emphasis``
    is the wrapper a backtick label displaced, and styles the whole label. The
    emoji face is ``### Link``'s set by the variant's ``Emoji …`` keys, and an
    ``Emoji gap`` is a run of its own (``_emoji_gap``).

    Measurement, drawing and the click target all come through here, so a bold
    run is measured as wide as it is painted (ADR-400).
    """
    variant = nd.get("link_variant") or "primary"
    style = theme.links.resolved(variant)
    faces = link_faces(theme, style.text_style, fonts)
    base = _EMPHASIS_FACE.get(nd.get("link_emphasis"), 0)
    font = styled_font(faces[base], size, base >= 2)
    runs = []
    for text, bold, italic in link_label_spans(label, variant):
        face = base | (1 if bold else 0) | (2 if italic else 0)
        runs.append(
            (text, font if face == base else styled_font(faces[face], size, face >= 2))
        )
    if style.emoji_gap is not None:
        runs = _emoji_gap(runs, style.emoji_gap, font)
    emoji_tf = fonts.varied_emoji("link", style, fonts.link_emoji, size)
    mark = label.strip()
    if mark in OVERFLOW_MARKS and emoji_tf and _has_glyph(emoji_tf, mark):
        # A "more" button draws its mark in the emoji face that has it, as an
        # icon; a face without it (the system emoji) leaves the text dots.
        runs = [(label, make_font(emoji_tf, size))]
    return font, runs, emoji_tf


def _emoji_ends(text: str) -> tuple[int, int, int, int] | None:
    """``(lead, start, end, trail)``: where the leading emoji end, the words
    start and end, and the trailing emoji start, as offsets into *text*.

    The emoji at either end may be several, apart or not. ``None`` when *text*
    has no emoji at either end, or no words beside them.
    """
    slots = _split_emoji_runs(text)
    offsets, at = [], 0
    for run, _ in slots:
        offsets.append(at)
        at += len(run)
    lead = 0
    for (run, is_emoji), off in zip(slots, offsets):
        if not (is_emoji or run.isspace()):
            break
        if is_emoji:
            lead = off + len(run)
    trail = len(text)
    for (run, is_emoji), off in zip(reversed(slots), reversed(offsets)):
        if not (is_emoji or run.isspace()):
            break
        if is_emoji:
            trail = off
    words = text[lead:trail]
    if not words.strip() or (lead == 0 and trail == len(text)):
        return None
    start = lead + len(words) - len(words.lstrip())
    return lead, start, trail - (len(words) - len(words.rstrip())), trail


def _emoji_gap(
    runs: list[tuple[str, skia.Font]], gap: float, font: skia.Font
) -> list[tuple[str, skia.Font]]:
    """*runs* with the spaces between a leading or trailing emoji and the words
    replaced by a gap *gap* pixels wide, typed or not.

    The gap is a run of its own: one space in *font* stretched to *gap*. It
    paints nothing, and every reader of the runs (both measurers, the painter,
    the click target) advances by it with no code of its own (ADR-400).
    """
    text = "".join(run for run, _ in runs)
    ends = _emoji_ends(text)
    space = font.measureText(" ")
    if ends is None or space <= 0:
        return runs
    lead, start, end, trail = ends
    spacer = [(" ", make_font(font.getTypeface(), font.getSize(), gap / space))]

    def cut(a: int, b: int) -> list[tuple[str, skia.Font]]:
        pieces, at = [], 0
        for run, run_font in runs:
            lo, hi = max(a, at), min(b, at + len(run))
            if lo < hi:
                pieces.append((run[lo - at : hi - at], run_font))
            at += len(run)
        return pieces

    return [
        *cut(0, lead),
        *(spacer if lead and gap > 0 else []),
        *cut(start, end),
        *(spacer if trail < len(text) and gap > 0 else []),
        *cut(trail, len(text)),
    ]


def emoji_paths(theme: Theme) -> dict[str, str]:
    """The font each element's emoji keys (``Emoji weight`` / ``fill`` /
    ``grade`` / ``optical size``) set, for ``FontSet.emoji_paths``.

    The element is ``badge`` (``## Emoji styles``), ``link`` (``## Links``) or
    ``chip`` (``## Inline Code``), and its font is the one that element's emoji
    already draw in: ``### Link`` / ``### Inline``'s ``Font``, else the ``##
    Emoji styles`` one. A theme naming no emoji font sets nothing.
    """
    base = theme.emojis.font_path

    def own(path: str | None) -> str | None:
        return path if path and Path(path).is_file() else base

    paths = {
        "badge": base,
        "link": own(theme.emojis.link.font_path),
        "chip": own(theme.emojis.inline.font_path),
    }
    return {element: path for element, path in paths.items() if path}


def _base_role_style(theme: Theme, role: str) -> TextStyle:
    """Global effective style behind one locally-overridable text role."""
    if role == "text":
        return theme.text
    if role in ("muted", "lead", "display"):
        return tier_style(role, theme)
    # `Key` / `Value` under ## Text Styles: the two sides of a display's pair
    # (ADR-205). A theme that sets neither draws both in ordinary body text.
    if role == "value":
        return theme.value_style if theme.value_style is not None else theme.text
    return theme.key_style if theme.key_style is not None else theme.text


def scoped_text_style(
    theme: Theme, role: str, scopes: tuple[str, ...] = ()
) -> TextStyle:
    """Resolve one role through its outer-to-inner styling-scope cascade."""
    style = _base_role_style(theme, role)
    for scope in scopes:
        patch = theme.text_style_overrides.get(scope, {}).get(role)
        if patch is not None:
            style = patch.apply(style)
    return style


def scoped_horizontal_rule_style(
    theme: Theme, scopes: tuple[str, ...] = ()
) -> HorizontalRuleTheme:
    """Resolve horizontal-rule paint through its outer-to-inner cascade."""
    style = theme.horizontal_rule
    for scope in scopes:
        patch = theme.horizontal_rule_overrides.get(scope)
        if patch is not None:
            style = patch.apply(style)
    return style


def _kv_role_style(
    theme: Theme, role: str, text_scopes: tuple[str, ...] = ()
) -> TextStyle:
    """Effective text style for the key or the value side of a K-V pair."""
    return scoped_text_style(theme, role, text_scopes)


def _text_style_scopes(node: object | None) -> tuple[str, ...]:
    """Read the grouper-authored scope chain from a node object or AST dict."""
    if node is None:
        return ()
    if isinstance(node, dict):
        return tuple(node.get("text_style_chain") or ())
    return tuple(getattr(node, "text_style_chain", ()) or ())


def _node_text_context(
    node: object,
) -> tuple[str | None, int, str | None, tuple[str, ...]]:
    """Return the four authored text selectors shared by measure and paint."""
    if isinstance(node, dict):
        return (
            node.get("table_role"),
            node.get("heading_ctx", 0),
            node.get("text_style"),
            _text_style_scopes(node),
        )
    return (
        getattr(node, "table_role", None),
        getattr(node, "heading_ctx", 0),
        getattr(node, "text_style", None),
        _text_style_scopes(node),
    )


def _sizing_tier(node_type: str | None, text_style: str | None) -> str | None:
    """The authored tier that picks a leaf's face and size.

    On a K-V key, Muted is a state, not a size: a muted key keeps the key's own
    style and changes only its ink, so a selected and an unselected card line up
    Every other tier, and Muted anywhere else, sizes as
    authored.
    """
    return None if node_type == "key" and text_style == "muted" else text_style


def _has_local_font(theme: Theme, role: str, scopes: tuple[str, ...]) -> bool:
    """Whether this cascade actually overrides family or weight."""
    return any(
        (patch := theme.text_style_overrides.get(scope, {}).get(role)) is not None
        and bool(patch.declared & {"font_name", "font_weight"})
        for scope in scopes
    )


def _own_face(ts: TextStyle, body: TextStyle) -> bool:
    """Whether a role style names a family of its own, or a weight between the
    body's regular and its bold: a face the body's two cannot draw."""
    weight = weight_from_str(ts.font_weight)
    family = (ts.font_name or "").casefold()
    return bool(family and family != (body.font_name or "").casefold()) or (
        weight < 700 and weight != weight_from_str(body.font_weight)
    )


def _style_fonts(ts: TextStyle, fonts: FontSet) -> FontSet:
    """Resolve a text style's family/weight for both measure and draw paths."""
    weight = weight_from_str(ts.font_weight)
    faces = _TEXT_TYPEFACES.get(((ts.font_name or "").casefold(), weight))
    if faces is not None:
        regular, italic, bold, bold_italic = faces
        return dataclasses.replace(
            fonts,
            typeface=regular,
            italic=italic,
            bold=bold,
            bold_italic=bold_italic,
        )
    return dataclasses.replace(
        fonts,
        typeface=fonts.bold if weight >= 700 else fonts.typeface,
        italic=fonts.bold_italic if weight >= 700 else fonts.italic,
    )
