"""
theme.py

Dataclasses and THEME.md parser for layout_render.py draw parameters.
All dataclass defaults mirror the existing module-level constants in layout_render.py.
"""

from __future__ import annotations

import copy
import dataclasses
import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import skia  # type: ignore[import-untyped]

# The theme MODEL lives in theme_model.py; this module is the parser that
# builds it. Re-exported here because `md2ui.pipeline.theme` is what the rest
# of the codebase means by "the theme" -- `Theme` alone is imported from it in
# 32 files -- and moving 16 names would be churn with no reader benefit.
from md2ui.pipeline.theme_placeholders import PlaceholderParser
from md2ui.pipeline.theme_model import (
    VALUE_FORMATS,
    _MUTED_TEXT_COLOR,
    _TEXT_COLOR,
    CONTENT_WIDTH_MAX,
    LINE_ALIGN_DEFAULT,
    LINK_BUTTON_VARIANTS,
    ORPHAN_ROW_DEFAULT,
    SHADOW_MAX_PER_KIND,
    SHADOW_RADIUS_MAX,
    STROKE_ALIGNS,
    BarTheme,
    BulletedListStyle,
    EmojiBadgeStyle,
    EmojiTextStyle,
    GradientTheme,
    HorizontalRulePatch,
    InlineCodeTheme,
    InlineLinkStyle,
    LinkStyle,
    NumberedListStyle,
    PaddingBox,
    QuoteStyle,
    RootTheme,
    SectionStyle,
    ShadowSpec,
    SliderTheme,
    TextStyle,
    TextStylePatch,
    Theme,
)

__all__ = [
    "BarTheme",
    "BulletedListStyle",
    "CONTENT_WIDTH_MAX",
    "EmojiBadgeStyle",
    "EmojiTextStyle",
    "GradientTheme",
    "InlineCodeTheme",
    "InlineLinkStyle",
    "LINE_ALIGN_DEFAULT",
    "LinkStyle",
    "NumberedListStyle",
    "ORPHAN_ROW_DEFAULT",
    "PaddingBox",
    "RootTheme",
    "QuoteStyle",
    "SHADOW_MAX_PER_KIND",
    "SHADOW_RADIUS_MAX",
    "SectionStyle",
    "ShadowSpec",
    "SliderTheme",
    "TABLE_KEY_COL_MAX_SHARE",
    "TextStyle",
    "TextStylePatch",
    "Theme",
    "parse_theme",
    "resolve_section_style",
]

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

_GROUP_FILL = skia.ColorSetARGB(255, 252, 252, 252)

# ``Line align`` vocabulary: the VERTICAL alignment of the pieces of one
# source line. "baseline" is the default.
LINE_ALIGN_VALUES = ("top", "baseline", "center", "bottom")
MARKER_ALIGN_VALUES = frozenset(LINE_ALIGN_VALUES)


def resolve_section_style(
    theme: Theme, level: int, fixed_style_key: str | None = None
) -> SectionStyle | None:
    """The complete style selected by a heading section.

    A matching fixed style replaces ``Heading N`` whole, or with ``Mode:
    override`` wins only the keys it states; unmatched ids and ordinary
    headings keep the level style.
    """
    if fixed_style_key:
        merged = theme.fixed_section_levels.get((fixed_style_key, level))
        if merged is not None:
            return merged
        fixed = theme.fixed_sections.get(fixed_style_key)
        if fixed is not None:
            return fixed
    return theme.sections.get(level)


# ``Orphan row`` vocabulary: what a repeated-item grid's RAGGED final row does
# with the width its missing cells would have used. "left" is the default —
# cells at one column's width packed from the left edge.
ORPHAN_ROW_VALUES = ("left", "center", "stretch")

# The layout content-width range. ``CONTENT_WIDTH_MAX`` is only the DEFAULT of
# the root's ``Max width``; ``CONTENT_WIDTH_MIN`` is a sanity floor, not a
# policy, so a typo can never collapse a layout to nothing. They live here
# rather than in layout_render because the theme parser has to clamp against
# them and layout_render already imports this module.
CONTENT_WIDTH_MIN = 320.0

# Most of a stacking-cards table's width a key label may take before it is
# capped and the label wraps instead. Lives here for the same reason as the
# widths above: the RENDERER lays the key column out with it (`_table_plan`)
# and the GENERATOR solves for it when it works out how narrow a stacked table
# can go (`generator_units._stacked_table_min`), so the two must read one
# number rather than keep a copy each.
TABLE_KEY_COL_MAX_SHARE = 0.4


# Wrapper variants an EMOJI or CHIP can take, by wrapper length:
#   *x* Secondary | **x** Tertiary | ***x*** Quaternary
# (Primary is the unwrapped base and needs no slot.)
_ELEMENT_VARIANTS = ("secondary", "tertiary", "quaternary")
# A chip also reads underscores as their own family: _x_ Quinary | __x__ Senary
# | ___x___ Septenary (see grouper_types._CHIP_UNDERSCORE_VARIANT_BY_LEN).
_CHIP_VARIANTS = (*_ELEMENT_VARIANTS, "quinary", "senary", "septenary")


# ---------------------------------------------------------------------------
# Color / numeric helpers
# ---------------------------------------------------------------------------

# Regex to detect valid hex strings like #RRGGBB or #RRGGBBAA
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
# Regex to identify a text-styles sub-section header: bare word(s) (optional
# colon). Spaces are allowed (e.g. "Links Secondary") — the subsection key
# is space-stripped after matching, so "Links Secondary" -> "linkssecondary".
_SUBSECTION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 ]*:?\s*$")


def _hex_to_skia(h: str) -> int:
    """Convert #RRGGBB or #RRGGBBAA to a skia ARGB integer."""
    h = h.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return skia.ColorSetARGB(255, r, g, b)
    if len(h) == 8:
        r, g, b, a = (
            int(h[0:2], 16),
            int(h[2:4], 16),
            int(h[4:6], 16),
            int(h[6:8], 16),
        )
        return skia.ColorSetARGB(a, r, g, b)
    raise ValueError(f"Bad hex color: #{h}")


def _try_hex(val: str, default: int) -> int:
    val = val.strip()
    if not _HEX_RE.match(val):
        return default
    try:
        return _hex_to_skia(val)
    except Exception:
        return default


def _try_float(val: str, default: float) -> float:
    try:
        return float(val.strip())
    except Exception:
        return default


_EMOJI_KEYS = ("emoji weight", "emoji fill", "emoji grade", "emoji optical size")


def _set_emoji_key(
    style: LinkStyle | InlineCodeTheme | EmojiBadgeStyle, key: str, val: str
) -> None:
    """One of ``_EMOJI_KEYS`` on a button, chip or badge style: a weight from 100
    to 900, a fill from 0 to 1, any grade, an optical size above 0 or ``auto``.
    A value outside its key's range is no key."""
    n, auto = _try_float(val, math.nan), val.strip().lower() == "auto"
    if key == "emoji weight" and 100 <= n <= 900:
        style.emoji_weight = int(n)
    elif key == "emoji fill" and 0 <= n <= 1:
        style.emoji_axes = dataclasses.replace(style.emoji_axes, fill=n)
    elif key == "emoji grade" and math.isfinite(n):
        style.emoji_axes = dataclasses.replace(style.emoji_axes, grade=n)
    elif key == "emoji optical size" and (auto or n > 0):
        opsz = "auto" if auto else n
        style.emoji_axes = dataclasses.replace(style.emoji_axes, optical_size=opsz)


# The two axis keys, each with the spelling it was FIRST shipped under.
#
# `Align` and `Line align` came from a time when a same-line row was the only
# row an author could make, so "line" described the
# only thing the key could reach. `:::` rows ended that, and the name stopped
# being true — a key named for a limitation outlives the limitation. The
# spellings below say which axis they move, which is what they always meant.
#
# The originals keep parsing, and silently: there is no warning channel for a
# THEME.md key today, so dropping them would take a theme's alignment away with
# nothing said. Two names, one field.
HORIZONTAL_ALIGN_KEYS = ("horizontal align", "align")
VERTICAL_ALIGN_KEYS = ("vertical align", "line align")


def _try_align(val: str) -> str | None:
    """``Align:`` for Root and for a level — ``left`` / ``center`` / ``right``.

    Returns None for ``Default`` and for anything unrecognised, which a LEVEL
    reads as "unset, inherit" and Root resolves to its own default of ``left``.
    One helper for both so they cannot disagree on the vocabulary: Right is
    advertised by THEME.md, accepted by ``md2ui.content_align`` and drawn by
    every renderer site, so neither parser may drop it.
    """
    v = val.strip().lower()
    return v if v in ("left", "center", "right") else None


def _try_line_align(val: str) -> str | None:
    """``Line align:`` for Root and for a level — the VERTICAL counterpart of
    ``Align``: how the cells of a row sit against each other.

    It governs the two rows an AUTHOR writes: the pieces of one source line
    (``Subtotal - 92 : days``) and the cells of a ``:::`` column row. It still
    does not reach a card grid, a gutter-marker row or an image aside — those
    are arrangements the document did not ask for by name, and a theme value
    that restacked them would be a surprise.

    ``baseline`` is the default and means "share a text baseline", so on a
    ``:::`` row — whose cells come from different source lines and mostly stack
    — it reads as ``top``.

    ``top`` / ``baseline`` / ``center`` / ``bottom``. Returns None for
    ``Default`` and for anything unrecognised, which a LEVEL reads as "unset,
    inherit" and Root resolves to its own default of ``baseline``. One helper for
    both so the vocabulary cannot diverge, exactly like ``_try_align``.
    """
    v = val.strip().lower()
    return v if v in LINE_ALIGN_VALUES else None


def _try_bool(val: str, default: bool) -> bool:
    """A boolean key that may default either way.

    The house idiom ``val.lower() in ("yes", "true", "1")`` is only safe for a
    key whose default is False: for a yes-default key any typo silently turns it
    OFF. This reads an explicit no as False, an explicit yes as True, and leaves
    anything else on the default.
    """
    v = val.strip().lower()
    if v in ("no", "false", "0"):
        return False
    if v in ("yes", "true", "1"):
        return True
    return default


def _try_orphan_row(val: str) -> str | None:
    """``Orphan row:`` for Root and for a level — what a grid's ragged final row
    does with the space its missing cells would have filled.

    ``left`` (the default) keeps every cell at one column's width, packed from
    the left; ``center`` keeps that width and centers the cells in the row;
    ``stretch`` shares the whole row between the cells that are actually there.
    Returns None for ``Default`` and for anything unrecognised, which a LEVEL
    reads as "unset, inherit" and Root resolves to its own default of ``left``.
    """
    v = val.strip().lower()
    return v if v in ORPHAN_ROW_VALUES else None


def _try_point(val: str, default: tuple[float, float]) -> tuple[float, float]:
    """Parse 'x, y' into a float tuple."""
    try:
        parts = val.split(",")
        return float(parts[0].strip()), float(parts[1].strip())
    except Exception:
        return default


def _apply_padding(box: "PaddingBox", key: str, val: str) -> bool:
    """Apply a padding key to a PaddingBox in place. Returns True if it matched.

    ``padding`` sets all four sides; ``padding top|left|right|bottom`` sets one.
    """
    if key == "padding":
        v = _try_float(val, 0.0)
        box.top = box.left = box.right = box.bottom = v
        return True
    if key in (
        "padding top",
        "padding left",
        "padding right",
        "padding bottom",
    ):
        side = key.split()[1]
        setattr(box, side, _try_float(val, getattr(box, side)))
        return True
    return False


def _append_color_bullet(raw: str, state: dict, targets: dict[str, list[int]]) -> bool:
    """Consume a bare ``- #RRGGBB`` bullet into the list ``state['sl']`` names.

    The multi-color form of every color key: the key line opens a list, the
    bullets under it fill it. Returns True when *raw* was a bullet (whether or
    not it landed anywhere), so callers stop treating it as a key line.
    """
    if not raw.startswith("- "):
        return False
    cval = raw[2:].strip()
    if not cval.startswith("#"):
        return False
    lst = targets.get(state.get("sl", ""))
    c = _try_hex(cval, -1)
    if lst is not None and c != -1:
        lst.append(c)
    return True


def _parse_link_style_line(
    ls: "LinkStyle", key: str, val: str, state: dict | None = None
) -> None:
    """Apply one ``## Links`` key:val line to a LinkStyle in place.

    Unset (``None``) fields are lazily materialized here so a variant block
    that only sets e.g. ``Fill color`` doesn't force the others away from
    their Primary fallback (see ``_resolve_link_style``).

    ``state["sl"]`` is the active bullet list, so ``Fill color:`` / ``Stroke
    color:`` can each be written as one inline color or as a list of them; the
    scalar field mirrors the list's first entry either way.
    """
    st = state if state is not None else {}
    if key == "corner radius":
        ls.corner_radius = _try_float(val, ls.corner_radius or 0.0)
    elif key.startswith("padding"):
        if ls.padding is None:
            ls.padding = PaddingBox()
        _apply_padding(ls.padding, key, val)
    elif key in (
        "fill color",
        "fill colors",
        "background color",
        "background colors",
    ):
        st["sl"] = "fill"
        if val.startswith("#") and (c := _try_hex(val, -1)) != -1:
            ls.fill_colors.append(c)
            ls.fill_color = ls.fill_colors[0]
    elif key == "stroke width":
        ls.stroke_width = _try_float(val, ls.stroke_width or 0.0)
    elif key in ("stroke color", "stroke colors"):
        st["sl"] = "stroke"
        if val.startswith("#") and (c := _try_hex(val, -1)) != -1:
            ls.stroke_colors.append(c)
            ls.stroke_color = ls.stroke_colors[0]
    elif key == "stroke align" and val.lower() in STROKE_ALIGNS:
        ls.stroke_align = STROKE_ALIGNS[val.lower()]
    elif key == "emoji shape":
        v = val.strip().lower()
        if v in ("circle", "square"):
            ls.emoji_shape = v
    elif key == "disabled fill color":
        ls.disabled_fill_color = _try_hex(val, ls.disabled_fill_color or 0)
    elif key == "disabled text color":
        ls.disabled_text_color = _try_hex(val, ls.disabled_text_color or 0)
    elif key == "disabled stroke color":
        ls.disabled_stroke_color = _try_hex(val, ls.disabled_stroke_color or 0)
    elif key == "emoji gap":
        ls.emoji_gap = max(0.0, _try_float(val, ls.emoji_gap or 0.0))
    elif key in _EMOJI_KEYS:
        _set_emoji_key(ls, key, val)
    else:
        st["sl"] = ""  # an unrecognised key ends the active bullet list


def _parse_inline_link_line(ils: "InlineLinkStyle", key: str, val: str) -> None:
    """Apply one ``## Links`` ``### Inline`` key:val line in place.

    Only two keys — the font and size of an inline link always come from the
    text or heading around it, never from here (see ``InlineLinkStyle``).
    """
    if key == "text color":
        ils.text_color = _try_hex(val, ils.text_color or 0)
    elif key == "underline":
        ils.underline = _parse_bool(val)


def _parse_layered_background_line(
    target: Any, line: str, raw: str, state: dict
) -> bool:
    """Parse one image/gradient/shadow layer shared by background painters.

    ``target`` is any theme record exposing ``bg_image``, ``gradient`` and
    ``shadows``. Returns whether the line belonged to those layers, leaving
    solid color, stroke, radius and padding to the owning style parser.
    """
    if state.get("sh") is not None and raw.startswith("- "):
        _shadow_bullet(state["sh"], raw[2:].strip())
        return True
    gradient = target.gradient
    if raw.startswith("  - ") and gradient is not None:
        value = raw[4:].strip()
        if state.get("gl") == "ratios":
            ratio = _try_float(value, -1.0)
            if ratio >= 0.0:
                gradient.ratios.append(ratio)
        elif state.get("gl") == "colors":
            color = _try_hex(value, -1)
            if color != -1:
                gradient.colors.append(color)
        elif state.get("gl") == "parameters" and ":" in value:
            key, _, val = value.partition(":")
            if key.strip().lower() == "start":
                gradient.start = _try_point(val.strip(), gradient.start)
            elif key.strip().lower() == "end":
                gradient.end = _try_point(val.strip(), gradient.end)
        return True
    if raw.startswith("- ") and gradient is not None:
        value = raw[2:].strip().rstrip(":")
        key = value.partition(":")[0].strip().lower()
        if key in ("ratios", "colors", "parameters"):
            state["gl"] = key
            return True
        if key == "type":
            if ":" in value:
                gradient.type = value.partition(":")[2].strip().lower()
            return True
    if ":" not in line or raw.startswith("- "):
        return False
    key, _, val = line.partition(":")
    key = key.strip().lower()
    val = val.strip()
    state["sh"] = None
    if (inner := _shadow_key(key)) is not None:
        state["sh"] = _open_shadow(target.shadows, inner)
        state["gl"] = ""
        state["sl"] = ""
        return True
    if key == "background image":
        if val and not val.startswith("("):
            target.bg_image = val
        return True
    if key == "background gradient":
        target.gradient = GradientTheme()
        state["gl"] = ""
        return True
    return False


def _parse_inline_code_line(
    ic: "InlineCodeTheme",
    line: str,
    state: dict | None = None,
    raw: str | None = None,
) -> None:
    """Apply one ``## Inline Code`` line in place.

    ``Fill color:`` and ``Stroke color:`` each take one inline color or a list
    of ``- #RRGGBB`` bullets; ``state["sl"]`` tracks which list is open and the
    scalar field mirrors its first entry.

    Shared by the base block and by each ``### <Variant>`` block, which is
    replayed onto a copy of the base after the file is read.
    """
    st = state if state is not None else {}
    if _parse_layered_background_line(ic, line, raw if raw is not None else line, st):
        return
    if line.startswith("- "):
        _append_color_bullet(
            line, st, {"fill": ic.fill_colors, "stroke": ic.stroke_colors}
        )
        if ic.fill_colors:
            ic.fill_color = ic.fill_colors[0]
        if ic.stroke_colors:
            ic.stroke_color = ic.stroke_colors[0]
        return
    if ":" not in line:
        return
    key, _, val = line.partition(":")
    key = key.strip().lower()
    val = val.strip()
    if key == "corner radius":
        ic.corner_radius = _try_float(val, ic.corner_radius)
    elif _apply_padding(ic.padding, key, val):
        pass
    elif key in (
        "fill color",
        "fill colors",
        "background color",
        "background colors",
    ):
        st["sl"] = "fill"
        if val.startswith("#") and (c := _try_hex(val, -1)) != -1:
            ic.fill_colors.append(c)
            ic.fill_color = ic.fill_colors[0]
    elif key in ("stroke color", "stroke colors"):
        st["sl"] = "stroke"
        if val.startswith("#") and (c := _try_hex(val, -1)) != -1:
            ic.stroke_colors.append(c)
            ic.stroke_color = ic.stroke_colors[0]
    elif key == "stroke width":
        ic.stroke_width = _try_float(val, ic.stroke_width)
    elif key == "stroke align" and val.lower() in STROKE_ALIGNS:
        ic.stroke_align = STROKE_ALIGNS[val.lower()]
    elif key in _DISABLED_CHIP_KEYS:
        # The muted chip (`` ~~`x`~~ ``), keyed exactly as ``## Links`` keys it.
        if (c := _try_hex(val, -1)) != -1:
            setattr(ic, _DISABLED_CHIP_KEYS[key], c)
    elif key in _EMOJI_KEYS:
        _set_emoji_key(ic, key, val)
    else:
        st["sl"] = ""  # an unrecognised key ends the active bullet list


_DISABLED_CHIP_KEYS = {
    "disabled fill color": "disabled_fill_color",
    "disabled text color": "disabled_text_color",
    "disabled stroke color": "disabled_stroke_color",
}

# The muted badge (``~~⭐~~``), named after the badge's own keys.
_DISABLED_BADGE_KEYS = {
    "disabled background color": "disabled_bg_color",
    "disabled icon color": "disabled_icon_color",
    "disabled stroke color": "disabled_stroke_color",
}


def _parse_code_block_line(theme: Theme, line: str) -> None:
    """Apply one scalar ``## Code Blocks`` declaration."""
    if ":" not in line or line.startswith("- "):
        return
    key, _, val = line.partition(":")
    key = key.strip().lower()
    val = val.strip()
    block = theme.code_blocks
    if key == "syntax style" and val:
        block.syntax_style = val
    elif key in ("background color", "fill color"):
        block.background_color = _try_hex(val, block.background_color)
    elif key == "corner radius":
        block.corner_radius = max(0.0, _try_float(val, block.corner_radius))
    elif key == "line spacing":
        block.line_spacing = max(0.0, _try_float(val, block.line_spacing))
    elif key == "min width":
        block.min_width = max(0.0, _try_float(val, block.min_width))
    elif key == "max lines":
        if val.lower() == "none":
            block.max_lines = None
        elif 1 <= _try_float(val, 0.0) < float("inf"):
            block.max_lines = int(_try_float(val, 0.0))
    elif key == "fade":
        block.fade = _try_bool(val, block.fade)
    else:
        _apply_padding(block.padding, key, val)


def _parse_copy_button_line(block, line: str, raw: str, state: dict) -> None:
    """Apply one ``### Copy Button`` line: its ``Icon`` and ``Icon size``, else
    the keys a button variant takes, painted by the same layers."""
    if _parse_layered_background_line(block.copy_button, line, raw, state):
        return
    if ":" not in line or line.startswith("- "):
        return
    key, _, val = line.partition(":")
    key, val = key.strip().lower(), val.strip()
    if key == "icon":
        block.copy_icon = None if val.lower() in ("", "none") else val
    elif key == "icon size":
        block.copy_icon_size = max(1.0, _try_float(val, block.copy_icon_size))
    else:
        _parse_link_style_line(block.copy_button, key, val, state)


def _parse_emoji_badge_line(
    style: "EmojiBadgeStyle", line: str, raw: str, state: dict
) -> None:
    """Apply one ``### Primary`` emoji line to an EmojiBadgeStyle in place.

    Handles the badge-only keys (``Icon size``/``Icon color[s]``/``Shape``/
    ``_EMOJI_KEYS``) and
    the ``Icon color`` bullet list locally, and delegates every fill/padding/
    gradient/stroke line to the shared ``_parse_section_style_line`` on
    ``style.fill`` — so Background colors / Corner radius / Stroke / Gradient /
    Padding all behave exactly as they do for section backgrounds. ``state["sl"]``
    is the shared active-bullet-list selector ("icon" | "bg" | "stroke").
    """
    # Top-level "- #RRGGBB" bullet under an active "Icon color" list.
    if raw.startswith("- ") and state.get("sl") == "icon":
        cval = raw[2:].strip()
        if cval.startswith("#"):
            c = _try_hex(cval, -1)
            if c != -1:
                style.icon_colors.append(c)
        return
    if ":" in line and not raw.startswith("- "):
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key in ("icon size", "size"):
            style.icon_size = _try_float(val, style.icon_size)
            return
        if key in ("icon color", "icon colors"):
            state["sl"] = "icon"
            if val.startswith("#"):
                c = _try_hex(val, -1)
                if c != -1:
                    style.icon_colors.append(c)
            return
        if key == "shape":
            v = val.lower()
            if v in ("circle", "square"):
                style.shape = v
            return
        if key in _DISABLED_BADGE_KEYS:
            if (c := _try_hex(val, -1)) != -1:
                setattr(style, _DISABLED_BADGE_KEYS[key], c)
        if key in _EMOJI_KEYS:
            _set_emoji_key(style, key, val)
            return
    # Everything else (fill/padding/gradient/stroke) → shared section parser.
    _parse_section_style_line(style.fill, line, raw, state)


def _parse_emoji_text_line(
    style: "EmojiTextStyle", line: str, raw: str, state: dict
) -> None:
    """Apply one ``### Text|Link|Inline`` emoji line to an EmojiTextStyle.

    Keys: ``Color:`` (single glyph color override), ``Font:`` (filled emoji
    font path), and a ``Fixed colors:`` bullet list of ``- <emoji> #RRGGBB``
    per-glyph overrides. ``state["sl"] == "fixed"`` marks the active list.
    """
    if raw.startswith("- ") and state.get("sl") == "fixed":
        item = raw[2:].strip()
        parts = item.rsplit(None, 1)  # rightmost token is the hex value
        if len(parts) == 2 and parts[0].strip():
            c = _try_hex(parts[1].strip(), -1)
            if c != -1:
                style.fixed_colors[parts[0].strip()] = c
        return
    if ":" in line and not raw.startswith("- "):
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key == "color":
            c = _try_hex(val, -1)
            if c != -1:
                style.color = c
            return
        if key == "font":
            if val and not val.startswith("("):
                style.font_path = val
            return
        if key == "fixed colors":
            state["sl"] = "fixed"
            return


# The channels a heading level can gate with ``Rotate <kind> colors: yes|no``,
# mapped from the word the author writes to the channel the renderer resolves.
# ``background`` covers this level's own section fill/stroke.
_ROTATE_CHANNELS = {
    "background": "background",
    "backgrounds": "background",
    "section": "background",
    "card": "card",
    "cards": "card",
    "element": "card",
    "elements": "card",
    "emoji": "emoji",
    "emojis": "emoji",
    "icon": "emoji",
    "icons": "emoji",
    "link": "link",
    "links": "link",
    "button": "link",
    "buttons": "link",
    "chip": "chip",
    "chips": "chip",
    "placeholder": "placeholder",  # a placeholder's fill and text (ADR-406)
    "placeholders": "placeholder",
    "code": "chip",
    "inline code": "chip",
    "heading": "heading",
    "headings": "heading",
    "text": "heading",
}


def _rotate_channel_key(key: str) -> str | None:
    """The channel a ``Rotate <kind> colors`` key gates, or None.

    ``Rotate link colors`` / ``Rotate links color`` / ``Rotate buttons colors``
    all reach the same switch — the key is prose, so it is read leniently rather
    than being one exact spelling.
    """
    if not key.startswith("rotate "):
        return None
    mid = key[len("rotate ") :].strip()
    for suffix in (" colors", " color"):
        if mid.endswith(suffix):
            mid = mid[: -len(suffix)].strip()
            break
    return _ROTATE_CHANNELS.get(mid)


def _shadow_key(key: str) -> "bool | None":
    """``Inner shadow`` / ``Outer shadow`` -> the layer's ``inner`` flag.

    A bare ``Shadow`` is the outer one, which is what an author who writes only
    one means. None for anything else, so the caller keeps looking.
    """
    k = key.replace(" ", "")
    if k in ("innershadow", "innershadows"):
        return True
    if k in ("outershadow", "outershadows", "shadow", "shadows"):
        return False
    return None


def _open_shadow(shadows: list[ShadowSpec], inner: bool) -> ShadowSpec:
    """Begin a shadow layer of one kind and return it for its bullets.

    Past ``SHADOW_MAX_PER_KIND`` of that kind the layer is still returned but
    never appended: its bullets are absorbed and the whole block is discarded,
    which is quieter than letting them fall through onto the colour lists.
    """
    sh = ShadowSpec(inner=inner)
    if sum(1 for s in shadows if s.inner == inner) < SHADOW_MAX_PER_KIND:
        shadows.append(sh)
    return sh


def _shadow_bullet(sh: ShadowSpec, bullet: str) -> None:
    """Apply one ``- Key: value`` line inside an open shadow block."""
    if ":" not in bullet:
        return
    key, _, val = bullet.partition(":")
    key = key.strip().lower().replace(" ", "")
    val = val.strip()
    if key in ("offsetx", "xoffset", "x"):
        sh.offset_x = _try_float(val, sh.offset_x)
    elif key in ("offsety", "yoffset", "y"):
        sh.offset_y = _try_float(val, sh.offset_y)
    elif key == "color":
        sh.color = _try_hex(val, sh.color)
    elif key.startswith("radius") or key.startswith("blur"):
        # ``Radius (blur)`` is the spelling in the notes, so match on the stem
        # rather than the whole key. Clamped, never rejected.
        sh.radius = max(0.0, min(SHADOW_RADIUS_MAX, _try_float(val, sh.radius)))


_SPACER_KEY_RE = re.compile(r"spacer (small|medium|large)(?: (row|col))?")


def _apply_spacer(spacers: dict, key: str, val: str) -> bool:
    """Read a ``Spacer <step> [row|col]: <px>`` line into a level's steps.

    True when *key* is a spacer key, whether or not its value was usable: an
    unusable value is dropped so the level states nothing, rather than a
    typo reserving an arbitrary space.
    """
    m = _SPACER_KEY_RE.fullmatch(key)
    if m is None:
        return key.startswith("spacer ")
    px = _try_float(val, -1.0)
    if px >= 0.0:
        step, axis = m.group(1), m.group(2)
        spacers[step if axis is None else f"{step} {axis}"] = px
    return True


# What ``### Elements`` would paint. A card is laid out, never drawn: a box comes
# from a heading style, so the block keeps its spacing,
# padding and the other layout keys and reads nothing that fills or outlines.
_CARD_PAINT_KEYS = frozenset(
    {
        "background color",
        "background colors",
        "background image",
        "background gradient",
        "stroke width",
        "stroke align",
        "stroke color",
        "stroke colors",
        "corner radius",
    }
)


def _is_card_paint_line(line: str, raw: str) -> bool:
    """True for a ``### Elements`` line that only paint keys read: a paint key,
    a shadow, a colour rotation, or a bullet of one of their lists."""
    if raw.lstrip().startswith("- "):
        return True
    key = line.partition(":")[0].strip().lower()
    return (
        key in _CARD_PAINT_KEYS
        or _shadow_key(key) is not None
        or key.startswith("rotate ")
    )


def _parse_section_style_line(
    st: "SectionStyle", line: str, raw: str, state: dict
) -> None:
    """Apply one THEME.md line to a SectionStyle (used for headings + elements).

    ``state`` carries mutable parse state: ``gl`` (active gradient list) and
    ``sl`` (active bullet list: "bg" | "stroke").
    """
    if _parse_layered_background_line(st, line, raw, state):
        return
    # Bare "- #RRGGBB" bullet: append to the active list (bg colors or stroke).
    # Both keys take one value or a list, so this is how the multi-color form of
    # each is written; the scalar mirror stays the first entry.
    elif raw.startswith("- "):
        cval = raw[2:].strip()
        if cval.startswith("#"):
            c = _try_hex(cval, -1)
            if c != -1:
                if state["sl"] == "bg":
                    st.bg_colors.append(c)
                elif state["sl"] == "stroke":
                    st.stroke_colors.append(c)
                    st.stroke_color = st.stroke_colors[0]
    elif ":" in line:
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key == "corner radius":
            st.corner_radius = _try_float(val, st.corner_radius)
            st.corner_radius_authored = True
        elif key == "image corner radius":
            st.image_corner_radius = _try_float(val, st.image_corner_radius)
        elif key == "image bleed":
            st.image_bleed = val.lower() in ("yes", "true", "1")
        elif key == "emoji aside":
            # Tri-state: an explicit "no" is not the same as unset, so that a
            # level can turn the gutter OFF without the key reading as absent.
            st.emoji_aside = val.lower() in ("yes", "true", "1")
        elif key in HORIZONTAL_ALIGN_KEYS:
            # Exact match, and ahead of the _apply_* predicate helpers below,
            # which match by pattern. None (Default/unknown) = inherit.
            st.align = _try_align(val)
        elif key in VERTICAL_ALIGN_KEYS:
            # The vertical twin; same exact-match placement, same
            # None = inherit convention.
            st.line_align = _try_line_align(val)
        elif key == "orphan row":
            # Same exact-match placement and None = inherit convention.
            st.orphan_row = _try_orphan_row(val)
        elif _apply_spacer(st.spacers, key, val):
            pass
        elif _apply_padding(st.padding, key, val):
            pass
        elif (gspc := _apply_group_spacing(key, val)) is not None:
            axis, v = gspc
            if axis in ("both", "row"):
                st.group_row_spacing = v
            if axis in ("both", "col"):
                st.group_col_spacing = v
        elif (ispc := _apply_image_spacing(key, val)) is not None:
            axis, v = ispc
            if axis in ("both", "row"):
                st.image_row_spacing = v
            if axis in ("both", "col"):
                st.image_col_spacing = v
        elif (spc := _apply_spacing(key, val)) is not None:
            axis, v = spc
            if axis in ("both", "row"):
                st.row_spacing = v
            if axis in ("both", "col"):
                st.col_spacing = v
        elif key == "merge rows":
            st.merge_rows = val.lower() in ("yes", "true", "1")
        elif key == "list card":
            st.list_card = _parse_bool(val)
        elif key == "adjacent section spacing":
            pass  # removed concept — ignored for back-compat
        elif key == "stroke width":
            st.stroke_width = _try_float(val, st.stroke_width)
        elif key == "stroke align" and val.lower() in STROKE_ALIGNS:
            st.stroke_align = STROKE_ALIGNS[val.lower()]
        elif key in ("stroke color", "stroke colors"):
            state["sl"] = "stroke"
            if val.startswith("#"):
                c = _try_hex(val, -1)
                if c != -1:
                    st.stroke_colors.append(c)
                    st.stroke_color = st.stroke_colors[0]
        elif key in ("background color", "background colors"):
            state["sl"] = "bg"
            if val.startswith("#"):
                c = _try_hex(val, -1)
                if c != -1:
                    st.bg_colors.append(c)
        elif key in ("rotate colors", "rotate color"):
            # The blanket form: `sync` shares this level's slot downward, while
            # yes/no gate every channel at once.
            if val.strip().lower() == "sync":
                st.sync_slot = True
            else:
                on = val.lower() in ("yes", "true", "1")
                for chan in set(_ROTATE_CHANNELS.values()):
                    st.rotate[chan] = on
        elif (chan := _rotate_channel_key(key)) is not None:
            st.rotate[chan] = val.lower() in ("yes", "true", "1")
        else:
            # An unrecognised key ENDS the active bullet list. Without this a
            # stray key between a list key and its bullets silently swallows
            # them into the previous list (a `Font colors:` line under an emoji
            # badge would append its color to that badge's bg_colors).
            state["sl"] = ""


def _new_marker_style(kind: str):
    """Create the marker style valid for one background-style level."""
    if kind == "bullet":
        return BulletedListStyle()
    if kind == "number":
        return NumberedListStyle()
    if kind == "quote":
        return QuoteStyle()
    return None


def _parse_marker_style_line(marker, line: str, state: dict, theme: Theme) -> None:
    """Apply one line inside a background level's ``#### Marker`` block."""
    if line.startswith("- "):
        value = line[2:].strip()
        if isinstance(marker, BulletedListStyle):
            if state.get("sl") == "color" and value.startswith("#"):
                c = _try_hex(value, -1)
                if c != -1:
                    marker.colors.append(c)
                    marker.color = marker.colors[0]
        elif isinstance(marker, QuoteStyle) and state.get("sl") == "bar":
            if value.startswith("#") and (c := _try_hex(value, -1)) != -1:
                marker.bar_colors.append(c)
                marker.bar_color = marker.bar_colors[0]
        else:
            _apply_text_style_bullet(value, "", theme, state=state)
        return
    if ":" not in line:
        return

    key, _, val = line.partition(":")
    key = key.strip().lower()
    val = val.strip()
    if key == "aside":
        marker.aside = val.lower() in ("yes", "true", "1")
        return
    if key in ("alignment", "align"):
        mode = val.lower()
        if mode in MARKER_ALIGN_VALUES:
            marker.alignment = mode
        return
    if key == "space":
        marker.space = _try_float(val, marker.space)
        return

    if isinstance(marker, BulletedListStyle):
        if key == "shape":
            marker.shape = val.lower() or None
        elif key == "size":
            marker.size = _try_float(val, marker.size)
        elif key == "color":
            state["sl"] = "color"
            if val.startswith("#") and (c := _try_hex(val, -1)) != -1:
                marker.colors.append(c)
                marker.color = marker.colors[0]
        elif key == "emoji":
            marker.emoji = val or None
        return

    if isinstance(marker, NumberedListStyle):
        if key == "number format":
            marker.number_format = _parse_number_format(val)
        else:
            if marker.text_style is None:
                marker.text_style = TextStyle()
            state["colors_ts"] = None
            _set_text_style_field(marker.text_style, key, val, state=state)
        return

    if isinstance(marker, QuoteStyle):
        if key == "bar width":
            marker.bar_width = _try_float(val, marker.bar_width)
        elif key == "bar length":
            marker.bar_length = _try_float(val, marker.bar_length)
        elif key == "bar color":
            state["sl"] = "bar"
            if val.startswith("#") and (c := _try_hex(val, -1)) != -1:
                marker.bar_colors.append(c)
                marker.bar_color = marker.bar_colors[0]
        elif key == "quote char":
            marker.quote_char = val or None
        else:
            state["sl"] = ""
            state["colors_ts"] = None
            _set_text_style_field(marker.char_text_style, key, val, state=state)


def _parse_root_line(theme: "Theme", line: str, raw: str, state: dict) -> None:
    """Apply one THEME.md line to the RootTheme. ``state['gl']`` = gradient list,
    ``state['sh']`` = the open shadow layer."""
    c = theme.root
    if state.get("sh") is not None and raw.startswith("- "):
        _shadow_bullet(state["sh"], raw[2:].strip())
    elif raw.startswith("  - ") and c.gradient is not None:
        sub = raw[4:].strip()
        g = c.gradient
        if state["gl"] == "ratios":
            v = _try_float(sub, -1.0)
            if v >= 0.0:
                g.ratios.append(v)
        elif state["gl"] == "colors":
            cc = _try_hex(sub, -1)
            if cc != -1:
                g.colors.append(cc)
        elif state["gl"] == "parameters":
            if ":" in sub:
                pk, _, pv = sub.partition(":")
                pk = pk.strip().lower()
                pv = pv.strip()
                if pk == "start":
                    g.start = _try_point(pv, g.start)
                elif pk == "end":
                    g.end = _try_point(pv, g.end)
    elif raw.startswith("- ") and c.gradient is not None:
        sub = raw[2:].strip().rstrip(":")
        key_lower = sub.lower()
        if key_lower == "ratios":
            state["gl"] = "ratios"
        elif key_lower == "colors":
            state["gl"] = "colors"
        elif key_lower == "parameters":
            state["gl"] = "parameters"
        elif key_lower.startswith("type"):
            if ":" in sub:
                _, _, tv = sub.partition(":")
                c.gradient.type = tv.strip().lower()
    elif ":" in line and not line.startswith("- "):
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip()
        state["sh"] = None
        if (inner := _shadow_key(key)) is not None:
            state["sh"] = _open_shadow(c.shadows, inner)
            state["gl"] = ""
        elif key == "background color":
            c.bg_color = _try_hex(val, c.bg_color)
        elif key == "background image":
            if val and not val.startswith("("):
                c.bg_image = val
        elif key == "background gradient":
            c.gradient = GradientTheme()
            state["gl"] = ""
        elif key == "box":
            c.box = val.lower() in ("true", "yes", "1")
        elif key == "box fill color":
            c.box_fill_color = _try_hex(val, c.box_fill_color)
        elif key == "box radius":
            c.box_radius = _try_float(val, c.box_radius)
        elif key in HORIZONTAL_ALIGN_KEYS:
            # Root is the base of the cascade, so an unset/Default value is its
            # own default rather than "inherit" — there is nothing above it.
            c.align = _try_align(val) or "left"
        elif key in VERTICAL_ALIGN_KEYS:
            c.line_align = _try_line_align(val) or LINE_ALIGN_DEFAULT
        elif key == "orphan row":
            c.orphan_row = _try_orphan_row(val) or ORPHAN_ROW_DEFAULT
        elif key == "max width":
            c.max_width = max(CONTENT_WIDTH_MIN, _try_float(val, c.max_width))
        elif key == "centered":
            c.centered = _try_bool(val, c.centered)
        elif key == "stack sections":
            c.pack_unique = _try_bool(val, c.pack_unique)
        elif key == "layout":
            c.layout = val.lower() if val.lower() in ("bento", "auto") else "default"
        elif _apply_spacer(c.spacers, key, val):
            pass
        elif key in ("element space", "element spacing"):
            sp = _try_float(val, theme.elements.row_spacing or 0.0)
            theme.elements.row_spacing = sp
            theme.elements.col_spacing = sp
        elif key == "element row space":
            theme.elements.row_spacing = _try_float(
                val, theme.elements.row_spacing or 0.0
            )
        elif key == "element col space":
            theme.elements.col_spacing = _try_float(
                val, theme.elements.col_spacing or 0.0
            )
        elif _apply_padding(c.padding, key, val):
            pass
        elif (sp2 := _apply_spacing(key, val)) is not None:
            axis, v = sp2
            if axis in ("both", "row"):
                c.row_spacing = v
            if axis in ("both", "col"):
                c.col_spacing = v


def _apply_spacing(key: str, val: str) -> tuple[str, float] | None:
    """Parse a spacing key into ``(axis, value)`` where axis is "row"|"col"|"both".

    ``spacing`` (or ``section spacing`` alias) → both; ``row spacing``/``col spacing``
    → one axis. Returns None if the key is not a spacing key.
    """
    if key in ("spacing", "section spacing"):
        return "both", _try_float(val, 0.0)
    if key == "row spacing":
        return "row", _try_float(val, 0.0)
    if key == "col spacing":
        return "col", _try_float(val, 0.0)
    return None


def _apply_group_spacing(key: str, val: str) -> tuple[str, float] | None:
    """Parse a group-spacing key into ``(axis, value)`` (axis "row"|"col"|"both").

    ``group spacing`` → both; ``group row spacing``/``group col spacing`` → one axis.
    Returns None if the key is not a group-spacing key.
    """
    if key == "group spacing":
        return "both", _try_float(val, 0.0)
    if key == "group row spacing":
        return "row", _try_float(val, 0.0)
    if key == "group col spacing":
        return "col", _try_float(val, 0.0)
    return None


def _apply_image_spacing(key: str, val: str) -> tuple[str, float] | None:
    """Parse an image-spacing key into ``(axis, value)`` (axis "row"|"col"|"both").

    ``image spacing`` → both; ``image row spacing``/``image col spacing`` → one axis.
    Returns None if the key is not an image-spacing key.
    """
    if key == "image spacing":
        return "both", _try_float(val, 0.0)
    if key == "image row spacing":
        return "row", _try_float(val, 0.0)
    if key == "image col spacing":
        return "col", _try_float(val, 0.0)
    return None


# ---------------------------------------------------------------------------
# Default heading styles (mirrors HEADING_SIZES / HEADING_COLORS constants)
# ---------------------------------------------------------------------------

_DEFAULT_HEADING_SIZES = {1: 28.0, 2: 22.0, 3: 18.0, 4: 15.0, 5: 13.0, 6: 12.0}
_DEFAULT_HEADING_COLORS = {
    1: skia.ColorSetARGB(255, 10, 10, 10),
    2: skia.ColorSetARGB(255, 25, 25, 25),
    3: skia.ColorSetARGB(255, 40, 40, 40),
    4: skia.ColorSetARGB(255, 55, 55, 55),
    5: skia.ColorSetARGB(255, 70, 70, 70),
    6: skia.ColorSetARGB(255, 85, 85, 85),
}


def _default_heading_style(level: int) -> TextStyle:
    return TextStyle(
        font_name="",  # "" = the body family
        font_size=_DEFAULT_HEADING_SIZES.get(level, 13.0),
        color=_DEFAULT_HEADING_COLORS.get(level, _TEXT_COLOR),
    )


# Size multipliers (and, for muted, a colour) applied to the BODY style when a
# tier block is absent from THEME.md.
_TIER_DEFAULTS: dict[str, tuple[float, str, int | None]] = {
    "muted": (0.85, "", _MUTED_TEXT_COLOR),
    "lead": (1.25, "", None),
    "display": (2.0, "bold", None),
}


def tier_style(name: str, theme: "Theme") -> TextStyle:
    """The effective ``muted``/``lead``/``display`` style for *theme*.

    An unset tier is derived from the body style rather than carrying a fixed
    default, so a theme that only restyles ``Text`` keeps its tiers in
    proportion. Single source of truth — the parser materialises a block
    through here, and the renderer resolves an unset one through here too.
    """
    ts = getattr(theme, name, None)
    if ts is not None:
        return ts
    return _default_tier_style(name, theme)


def _default_tier_style(name: str, theme: "Theme") -> TextStyle:
    scale, weight, color = _TIER_DEFAULTS[name]
    return TextStyle(
        font_name=theme.text.font_name,
        font_size=theme.text.font_size * scale,
        font_weight=weight,
        color=color if color is not None else theme.text.color,
    )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _parse_number_format(val: str) -> str:
    """Turn a ``Number format`` example (e.g. ``1.``, ``1)``, ``(1)``) into a
    ``str.format`` template with an ``{n}`` placeholder.

    The first run of digits in the example marks where the ordinal goes; the
    surrounding characters are kept verbatim. ``"1"`` ⇒ ``"{n}"`` (bare number).
    An example with no digits falls back to a bare number.
    """
    m = re.search(r"\d+", val)
    if not m:
        return "{n}"
    return val[: m.start()] + "{n}" + val[m.end() :]


def _set_text_style_field(
    ts: TextStyle, key: str, val: str, state: dict | None = None
) -> None:
    """Apply a 'Font X: value' / 'Marker X: value' bullet entry in place.

    A valueless ``Font color:`` opens the list form: *state* records this style
    so the nested ``  - #RRGGBB`` bullets that follow append to its ``colors``.
    """
    # A valueless color key opens its list; the state remembers which of the
    # three a following `  - #RRGGBB` bullet belongs to.
    if state is not None and not val:
        which = {
            "font color": "colors",
            "font colors": "colors",
            "marker text color": "marker_text_colors",
            "marker background color": "marker_bg_colors",
        }.get(key)
        if which:
            state["colors_ts"] = ts
            state["colors_attr"] = which
    if key == "font name":
        if val:
            ts.font_name = val
    elif key == "font size":
        ts.font_size = _try_float(val, ts.font_size)
    elif key == "font weight":
        if val:
            ts.font_weight = val
    elif key == "font color":
        if val.startswith("#") and (c := _try_hex(val, -1)) != -1:
            ts.colors.append(c)
            ts.color = ts.colors[0]
        else:
            ts.color = _try_hex(val, ts.color)
    elif key == "font colors":
        # The list form of `Font color`, written as nested `  - #RRGGBB`
        # bullets under a bare key (see _apply_text_style_bullet).
        pass
    elif key == "marker text color":
        if val.startswith("#") and (c := _try_hex(val, -1)) != -1:
            ts.marker_text_colors.append(c)
            ts.marker_text_color = ts.marker_text_colors[0]
    elif key == "marker background color":
        if val.startswith("#") and (c := _try_hex(val, -1)) != -1:
            ts.marker_bg_colors.append(c)
            ts.marker_bg_color = ts.marker_bg_colors[0]


_LOCAL_TEXT_ROLES = frozenset({"text", "muted", "lead", "display", "key", "value"})
_TEXT_PATCH_PROPERTIES = {
    "font name": "font_name",
    "font size": "font_size",
    "font weight": "font_weight",
    "font color": "color",
    "font colors": "color",
    "marker text color": "marker_text_color",
    "marker background color": "marker_bg_color",
}


def _apply_text_style_patch_bullet(
    line: str, patch: TextStylePatch, state: dict
) -> None:
    """Apply one bullet to a level-local role and remember it was authored."""
    if line.startswith("#"):
        ts_open = state.get("colors_ts")
        if ts_open is not None and (color := _try_hex(line.strip(), -1)) != -1:
            attr = state.get("colors_attr") or "colors"
            values = getattr(ts_open, attr)
            values.append(color)
            scalar = {
                "colors": "color",
                "marker_text_colors": "marker_text_color",
                "marker_bg_colors": "marker_bg_color",
            }[attr]
            setattr(ts_open, scalar, values[0])
        return
    if ":" not in line:
        return
    key, _, val = line.partition(":")
    key = key.strip().lower()
    declared = _TEXT_PATCH_PROPERTIES.get(key)
    if declared is None:
        state["colors_ts"] = None
        state["colors_attr"] = None
        return
    patch.declared.add(declared)
    _set_text_style_field(patch.style, key, val.strip(), state=state)


def _parse_horizontal_rule_line(target: Any, line: str) -> None:
    """Apply one global or level-local horizontal-rule paint property."""
    if ":" not in line or line.startswith("- "):
        return
    key, _, val = line.partition(":")
    key = key.strip().lower()
    val = val.strip()
    if key == "stroke color":
        color = _try_hex(val, -1)
        if color != -1:
            target.stroke_color = color
    elif key == "stroke width":
        try:
            target.stroke_width = float(val)
        except ValueError:
            pass


# Section-style list keys a ``Mode: override`` block replaces rather than extends.
_OVERRIDE_LISTS = {
    "background color": "bg_colors",
    "background colors": "bg_colors",
    "stroke color": "stroke_colors",
    "stroke colors": "stroke_colors",
}


@dataclasses.dataclass
class _StylingScopeParser:
    """State machine for the nested ``## Styling & Spacing`` grammar."""

    theme: Theme
    mode: str = ""
    scope: str = ""
    section_target: SectionStyle | None = None
    marker_kind: str = ""
    marker_target: Any = None
    text_patch_target: TextStylePatch | None = None
    horizontal_rule_target: HorizontalRulePatch | None = None
    root_state: dict = dataclasses.field(default_factory=lambda: {"gl": ""})
    section_state: dict = dataclasses.field(
        default_factory=lambda: {"gl": "", "sl": "stroke"}
    )
    marker_state: dict = dataclasses.field(
        default_factory=lambda: {"sl": "", "colors_ts": None}
    )
    text_state: dict = dataclasses.field(default_factory=lambda: {"colors_ts": None})
    # Each fixed style's own section lines, for replay onto a heading level
    # when it says ``Mode: override`` (see ``resolve_fixed_overrides``).
    fixed_lines: dict[str, list[tuple[str, str]]] = dataclasses.field(
        default_factory=dict
    )
    fixed_override: set[str] = dataclasses.field(default_factory=set)

    def reset(self) -> None:
        self.mode = ""
        self.scope = ""
        self.section_target = None
        self.marker_kind = ""
        self.marker_target = None
        self.text_patch_target = None
        self.horizontal_rule_target = None
        self.root_state = {"gl": ""}
        self.section_state = {"gl": "", "sl": "stroke"}
        self.marker_state = {"sl": "", "colors_ts": None}
        self.text_state = {"colors_ts": None}

    def _open_role(self, role: str) -> None:
        self.text_patch_target = None
        self.horizontal_rule_target = None
        self.text_state = {"colors_ts": None}
        if not self.scope:
            return
        self.marker_target = None
        if role == "horizontal rule":
            self.horizontal_rule_target = (
                self.theme.horizontal_rule_overrides.setdefault(
                    self.scope, HorizontalRulePatch()
                )
            )
        elif role in _LOCAL_TEXT_ROLES:
            self.text_patch_target = self.theme.text_style_overrides.setdefault(
                self.scope, {}
            ).setdefault(role, TextStylePatch())

    def parse(
        self,
        line: str,
        raw: str,
        parse_root: Callable[..., None],
        parse_section: Callable[..., None],
        parse_marker: Callable[..., None],
        new_marker: Callable[[str], Any],
    ) -> None:
        if line.startswith("##### ") and self.mode == "fixed" and self.scope:
            self._open_role(line[6:].strip().lower())
            return
        if line.startswith("#### ") and self.mode != "fixed":
            role = line[5:].strip().lower()
            if role in _LOCAL_TEXT_ROLES or role == "horizontal rule":
                self._open_role(role)
                return
        if (
            line.startswith("#### ")
            and line[5:].strip().lower() == "marker"
            and self.section_target is not None
            and self.marker_kind
        ):
            if self.section_target.marker is None:
                self.section_target.marker = new_marker(self.marker_kind)
            self.marker_target = self.section_target.marker
            self.text_patch_target = None
            self.horizontal_rule_target = None
            self.marker_state = {"sl": "", "colors_ts": None}
            return
        if line.startswith("#### ") and self.mode == "fixed":
            title = line[5:].strip()
            key = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            self.section_state = {"gl": "", "sl": "stroke"}
            self.section_target = SectionStyle()
            self.marker_kind = ""
            self.marker_target = None
            self.text_patch_target = None
            self.horizontal_rule_target = None
            self.text_state = {"colors_ts": None}
            self.scope = f"fixed:{key}" if key else ""
            if key:
                self.theme.fixed_sections[key] = self.section_target
                self.fixed_lines[key] = []
            return
        if line.startswith("### "):
            self._open_surface(line[4:].strip().lower())
            return
        if self.horizontal_rule_target is not None:
            _parse_horizontal_rule_line(self.horizontal_rule_target, line)
        elif self.text_patch_target is not None and line.startswith("- "):
            _apply_text_style_patch_bullet(
                line[2:].strip(), self.text_patch_target, self.text_state
            )
        elif self.mode == "root":
            parse_root(self.theme, line, raw, self.root_state)
        elif self.marker_target is not None:
            parse_marker(self.marker_target, line, self.marker_state, self.theme)
        elif self.mode == "elements":
            if not _is_card_paint_line(line, raw):
                parse_section(self.theme.elements, line, raw, self.section_state)
        elif self.mode in ("section", "fixed") and self.section_target is not None:
            key = self.scope.removeprefix("fixed:")
            if self.mode == "fixed" and key in self.fixed_lines:
                if line.lower().startswith("mode:"):
                    if line.partition(":")[2].strip().lower() == "override":
                        self.fixed_override.add(key)
                    return
                self.fixed_lines[key].append((line, raw))
            parse_section(self.section_target, line, raw, self.section_state)

    def resolve_fixed_overrides(self, parse_section: Callable[..., None]) -> None:
        """Build each ``Mode: override`` fixed style once per heading level.

        The block's own lines are replayed onto a copy of ``### Heading N``,
        so a key it states wins and every other key keeps the level's value.
        A list it states (colors, shadows) replaces the level's list whole.
        A level with no style of its own uses the standalone fixed style.
        """
        for key in self.fixed_override:
            for level, base in self.theme.sections.items():
                st = copy.deepcopy(base)
                state: dict = {"gl": "", "sl": "stroke", "sh": None}
                cleared: set[str] = set()
                for line, raw in self.fixed_lines[key]:
                    name = line.partition(":")[0].strip().lower()
                    field = _OVERRIDE_LISTS.get(name) or (
                        "shadows" if _shadow_key(name) is not None else None
                    )
                    if field and field not in cleared:
                        cleared.add(field)
                        setattr(st, field, [])
                    parse_section(st, line, raw, state)
                self.theme.fixed_section_levels[(key, level)] = st

    def _open_surface(self, sub: str) -> None:
        self.root_state = {"gl": ""}
        self.section_state = {"gl": "", "sl": "stroke"}
        self.marker_kind = ""
        self.marker_target = None
        self.text_patch_target = None
        self.horizontal_rule_target = None
        self.text_state = {"colors_ts": None}
        self.scope = ""
        if sub == "fixed styles":
            self.mode = "fixed"
            self.section_target = None
        elif sub.startswith("root"):
            self.mode, self.scope, self.section_target = "root", "root", None
        elif sub.startswith("element"):
            self.mode, self.section_target = "elements", self.theme.elements
        elif sub.startswith("image card"):
            self.mode, self.scope = "section", "image_cards"
            self.section_target = self.theme.image_cards
        elif sub.startswith(("unordered list", "bulleted list")):
            self.mode, self.scope = "section", "unordered_lists"
            self.section_target, self.marker_kind = (
                self.theme.unordered_lists,
                "bullet",
            )
        elif sub.startswith("task list"):
            self.mode, self.scope = "section", "task_lists"
            self.section_target, self.marker_kind = (
                self.theme.task_lists,
                "bullet",
            )
        elif sub.startswith(("numbered list", "ordered list")):
            self.mode, self.scope = "section", "numbered_lists"
            self.section_target, self.marker_kind = (
                self.theme.numbered_lists,
                "number",
            )
        elif sub.startswith(("quote", "blockquote")):
            self.mode, self.scope = "section", "quotes"
            self.section_target, self.marker_kind = self.theme.quotes, "quote"
        elif "heading" in sub and (match := re.search(r"(\d+)", sub)):
            level = max(1, min(6, int(match.group(1))))
            self.mode, self.scope = "section", f"heading:{level}"
            self.section_target = self.theme.sections.setdefault(level, SectionStyle())
            self.marker_kind = "number"
        else:
            self.mode, self.section_target = "", None


def _parse_bool(val: str) -> bool:
    return val.lower() in ("yes", "true", "1")


# The one non-color background selector: a card whose fill is a photo. Spelled
# in THEME.md exactly like a hex would be — `On background color: image`.
BG_IMAGE = "image"


def _bg_selector_key(val: str) -> "int | str | None":
    """The lookup key for a background: its ARGB, or ``image``, or None.

    One place decides what a background is *called*, so the parser and the
    renderer cannot disagree about which string means the photo case.
    """
    v, _, style = val.strip().lower().partition(" ")  # `image Music player`
    if v in (BG_IMAGE, "photo"):  # that fixed style's photo alone, by its slug
        return f"{BG_IMAGE}:{re.sub(r'[^a-z0-9]+', '-', style).strip('-')}".rstrip(":")
    c = _try_hex(val.strip(), -1)
    return None if c == -1 else c


# The three channels a replacement can target, by the key that names it. These
# are the same key names ## Links / ## Inline Code / ## Horizontal Rule already
# use, so a rule reads like the property it overrides.
_REPLACEMENT_ROLES = {
    "text color": "text",
    "text": "text",
    "color": "text",
    "from": "text",
    "fill color": "fill",
    "fill": "fill",
    "background": "fill",
    # `background color` is how every OTHER block in THEME.md spells this, so an
    # author writes it here too. Without this alias the key matched nothing, so
    # `role` stayed at its "text" default and `src` stayed None — the rule
    # silently became that background's TEXT default instead of doing nothing,
    # which is the worse failure of the two.
    "background color": "fill",
    "stroke color": "stroke",
    "stroke": "stroke",
    "border color": "stroke",
    "border": "stroke",
}
_REPLACEMENT_TO = ("replacement", "replace with", "to", "replacement color")


_FIXED_ROLE_KEYS = {
    "text color": "text",
    "text": "text",
    "color": "text",
    "fill color": "fill",
    "fill": "fill",
    "background color": "fill",
    "stroke color": "stroke",
    "stroke": "stroke",
    "border color": "stroke",
}
_FIXED_SCOPES = ("datapoints", "datapoint", "line", "glyph")
# Or the pieces of a run, named by kind.
_FIXED_KINDS = ("text", "emojis", "buttons", "chips")


def _parse_fixed_emoji(bullet: str) -> "tuple[str, int, str] | None":
    """``- 📈 #22C55E datapoints`` -> ``("📈", argb, "datapoints")``.

    The scope words are optional and default to the glyph alone. Several words add
    up, sorted and space-joined.
    """
    parts = bullet.split()
    if len(parts) < 2:
        return None
    words: set[str] = set()
    while len(parts) >= 3 and parts[-1].lower() in _FIXED_SCOPES + _FIXED_KINDS:
        word = parts.pop().lower()
        words.add({"datapoint": "datapoints", "glyph": ""}.get(word, word))
    color = _try_hex(parts[-1], -1)
    key = " ".join(parts[:-1]).strip()
    if color == -1 or not key:
        return None
    return key, color, " ".join(sorted(words - {""}))


def _parse_fixed_element(bullet: str) -> "tuple[str, dict[str, int]] | None":
    """``- Sold out: Text color: #A, Fill color: #B`` -> ``(key, {role: color})``.

    The key is everything before the FIRST colon that is followed by a role —
    so a label may itself contain a colon.
    """
    roles: dict[str, int] = {}
    head, _, rest = bullet.partition(":")
    key = head.strip()
    if not key or not rest.strip():
        return None
    for part in rest.split(","):
        rk, _, rv = part.partition(":")
        role = _FIXED_ROLE_KEYS.get(rk.strip().lower())
        c = _try_hex(rv.strip(), -1)
        if role is not None and c != -1:
            roles[role] = c
    return (key, roles) if roles else None


def _parse_color_replacement(group: dict, bullet: str) -> None:
    """Apply one ``<Role> color: X, Replacement: Y`` bullet to a background group.

    The left key picks the channel — ``Text color`` / ``Fill color`` /
    ``Stroke color`` — and is optional: a bullet that only states
    ``Replacement`` is that background's TEXT default, stored under the ``None``
    key and used for any text color the group does not name. (There is no
    blanket fill or stroke default: recoloring every pill on a background is
    never what someone means.) Field order does not matter.
    """
    role = "text"
    src: int | None = None
    dst: int | None = None
    for part in bullet.split(","):
        key, _, val = part.partition(":")
        key = key.strip().lower()
        c = _try_hex(val.strip(), -1)
        if c == -1:
            continue
        if key in _REPLACEMENT_ROLES:
            role = _REPLACEMENT_ROLES[key]
            src = c
        elif key in _REPLACEMENT_TO:
            dst = c
    if dst is not None:
        group.setdefault(role, {})[src] = dst


def _font_bullet(line: str) -> tuple[str, str] | None:
    """('font size', '12') from a `- Font size: 12` bullet, else None."""
    if not line.startswith("- "):
        return None
    bullet = line[2:].strip()
    if bullet.lower().startswith(("font", "marker")) and ":" in bullet:
        fkey, _, fval = bullet.partition(":")
        return fkey.strip().lower(), fval.strip()
    return None


def _apply_text_style_bullet(
    line: str,
    subsection: str,
    theme: Theme,
    tier_bullets: dict[str, dict[str, str]] | None = None,
    state: dict | None = None,
) -> None:
    """Parse 'Font X: value' and apply to the correct TextStyle slot.

    ``tier_bullets`` collects the raw ``Muted``/``Lead``/``Display`` bullets, for
    ``parse_theme`` to merge once the whole file (notably ``Text``) is parsed.

    ``state`` remembers which TextStyle a valueless ``- Font color:`` opened, so
    the nested ``  - #RRGGBB`` bullets under it land in that style's ``colors``
    list. One key, one value or many — the same shape every other color key has.
    """
    st = state if state is not None else {}
    if line.startswith("#"):
        ts_open = st.get("colors_ts")
        if ts_open is not None and (c := _try_hex(line.strip(), -1)) != -1:
            attr = st.get("colors_attr") or "colors"
            getattr(ts_open, attr).append(c)
            scalar = {
                "colors": "color",
                "marker_text_colors": "marker_text_color",
                "marker_bg_colors": "marker_bg_color",
            }[attr]
            setattr(ts_open, scalar, getattr(ts_open, attr)[0])
        return
    if ":" not in line:
        return
    raw_key, _, raw_val = line.partition(":")
    key = raw_key.strip().lower()
    val = raw_val.strip()
    # A `Font color:` with no value opens the list form; anything else closes it.
    st["colors_ts"] = None
    st["colors_attr"] = None

    if subsection.startswith("heading") and subsection[7:].isdigit():
        level = int(subsection[7:])
        if 1 <= level <= 6:
            ts = theme.headings.setdefault(level, _default_heading_style(level))
            _set_text_style_field(ts, key, val, state=st)
    elif subsection == "text":
        _set_text_style_field(theme.text, key, val, state=st)
    elif subsection == "labels":
        _set_text_style_field(theme.labels, key, val, state=st)
    elif subsection in ("key", "value"):
        attr = f"{subsection}_style"
        if getattr(theme, attr) is None:
            setattr(theme, attr, TextStyle())
        _set_text_style_field(getattr(theme, attr), key, val, state=st)
    # Authored display tiers. Collected raw and merged at the end of parse_theme
    # because their defaults derive from ``Text`` —
    # building them here would bake in whatever body size had been parsed so far,
    # making the result depend on block order.
    elif subsection in ("muted", "lead", "display"):
        if tier_bullets is not None:
            tier_bullets.setdefault(subsection, {})[key] = val
    elif subsection.startswith("inlinecode"):
        # "Inline Code" -> the base; "Inline Code Secondary" -> that variant.
        # The variant object itself is built after the file, so its text style
        # is stashed as a patch of what it stated and applied onto the base there.
        _v = subsection[len("inlinecode") :]
        if _v in _CHIP_VARIANTS:
            if not isinstance(getattr(theme.inline_code, _v, None), TextStylePatch):
                setattr(theme.inline_code, _v, TextStylePatch())
            _apply_text_style_patch_bullet(line, getattr(theme.inline_code, _v), st)
            return
        if theme.inline_code.text_style is None:
            theme.inline_code.text_style = TextStyle()
        _set_text_style_field(theme.inline_code.text_style, key, val, state=st)
    elif subsection == "codeblock":
        _set_text_style_field(theme.code_blocks.text_style, key, val, state=st)
    elif subsection == "links":
        theme.links.take_over()
        # Primary's text_style is always concrete (_unpainted_link_style).
        assert theme.links.primary.text_style is not None
        _set_text_style_field(theme.links.primary.text_style, key, val, state=st)
    elif subsection.startswith("links") and (
        subsection[5:] in LINK_BUTTON_VARIANTS or subsection[5:] == "text"
    ):
        theme.links.take_over()
        ls = getattr(theme.links, subsection[5:])
        if ls.text_style is None:
            ls.text_style = TextStyle(font_name="")  # "" = the body family
        _set_text_style_field(ls.text_style, key, val, state=st)


def parse_theme(path: Path) -> Theme:
    """
    Parse a THEME.md file into a Theme dataclass.
    Missing or invalid values retain their dataclass defaults.
    Returns a default Theme if the file cannot be read.
    """
    theme = Theme()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return theme
    # Strip complete HTML comments first so multi-line ``<!-- … -->`` blocks are
    # fully removed (the body of a multi-line comment must not parse as keys).
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    lines = text.splitlines()

    section: str = ""
    subsection: str = ""

    # Per-block parse state (gradient list + bullet list); reset on headers.
    _rstate = {"gl": ""}  # root gradient list
    _sstate = {"gl": "", "sl": "stroke"}  # active section-style block state
    # Target SectionStyle for the current ## Sections / ## Background block.
    _section_target: "SectionStyle | None" = None
    _styling_parser = _StylingScopeParser(theme)
    _placeholders = PlaceholderParser(
        theme.image_placeholders, theme.image_placeholder_defaults
    )
    # Target LinkStyle for the current ## Links block; defaults to Primary so
    # a flat ## Links block (no ### subheaders) keeps configuring Primary,
    # exactly like before variants existed.
    _link_target: "LinkStyle" = theme.links.primary
    # True while the ### Inline block of ## Links is active — its keys land on
    # theme.links.inline (a text-run style) instead of on a button variant.
    _link_inline: bool = False
    # Raw Muted/Lead/Display bullets, merged after the whole file (see below).
    _tier_bullets: dict[str, dict[str, str]] = {}
    # Raw lines of each emoji-badge / chip VARIANT block, replayed onto a
    # copy of the base after the whole file (see the merge at the end).
    _emoji_variant: str | None = None
    _emoji_variant_lines: dict[str, list[tuple[str, str]]] = {}
    _code_variant: str | None = None
    _code_variant_lines: dict[str, list[tuple[str, str]]] = {}
    # Active color bullet list inside ## Links / ## Inline Code ("fill" |
    # "stroke" | ""), the twin of _sstate["sl"] for section styles.
    _link_state: dict = {"gl": "", "sl": "", "sh": None}
    _code_state: dict = {"gl": "", "sl": "", "sh": None}
    # Inside ## Code Blocks: whether the lines belong to ### Copy Button.
    _copy_button = False
    # Within ## Text Styles: the TextStyle whose `Font color:` opened a list.
    _ts_state: dict = {"colors_ts": None}
    # Within ## Text Color Replacements: the background group being filled.
    _tcr_bg: "int | str | None" = None
    # Within ## Fixed colors: the active ### block and #### sub-block.
    _fx_block: str = ""
    _fx_sub: str = ""
    # Within ## Emoji styles: the active ### block target (Primary badge vs a
    # Text/Link/Inline text style) and which kind it is.
    _emoji_target: "EmojiBadgeStyle | EmojiTextStyle | None" = None
    # Within ## Tables: the active ### block ("table" | "header" | "cells" | "keys").
    _table_mode: str = ""
    # Within ## Drawing elements (legacy: Datapoints) / ## Charts: the active
    # ### block, lowercased with
    # spaces stripped ("ratiobars", "ringtrack", "chartseriescolors", ...).
    _dp_mode: str = ""
    _chart_mode: str = ""
    _arr_mode: str = ""

    for raw in lines:
        line = raw.strip()

        # Skip blanks and HTML comments
        if not line or line.startswith("<!--") or line.startswith("<!---"):
            continue

        # Level-2 section header
        if line.startswith("## "):
            section = line[3:].strip().lower()
            subsection = ""
            _rstate = {"gl": ""}
            _sstate = {"gl": "", "sl": "stroke"}
            _section_target = None
            _styling_parser.reset()
            if section == "links":
                theme.links.take_over()  # before its target: Primary is replaced
            _link_target = theme.links.primary
            _link_inline = False
            _link_state = {"gl": "", "sl": "", "sh": None}
            _code_state = {"gl": "", "sl": "", "sh": None}
            _copy_button = False
            _ts_state = {"colors_ts": None}
            _tcr_bg = None
            _fx_block = ""
            _fx_sub = ""
            _emoji_target = None
            _table_mode = ""
            _dp_mode = ""
            _chart_mode = ""
            _arr_mode = ""
            continue

        # Level-1 title — capture as theme name
        if line.startswith("# "):
            theme.name = line[2:].strip()
            continue

        # ---- Root ----------------------------------------------------------
        if section == "root":
            _parse_root_line(theme, line, raw, _rstate)

        # ---- Sections (per-heading-level backgrounds) ----------------------
        elif section == "sections":
            if line.startswith("### "):
                sub = line[4:].strip().lower()
                m = re.search(r"(\d+)", sub)
                if "heading" in sub and m:
                    lvl = max(1, min(6, int(m.group(1))))
                    _section_target = theme.sections.setdefault(lvl, SectionStyle())
                    _sstate = {"gl": "", "sl": "stroke"}
                continue
            if _section_target is not None:
                _parse_section_style_line(_section_target, line, raw, _sstate)

        # ---- Styling & Spacing (Root + surfaces + local text roles) ----------
        elif section in (
            "styling & spacing",
            "styling and spacing",
            "background styles and spacing",
        ):
            _styling_parser.parse(
                line,
                raw,
                _parse_root_line,
                _parse_section_style_line,
                _parse_marker_style_line,
                _new_marker_style,
            )

        # ---- Content arrangement (Bento targeting) --------------------------
        elif section == "content arrangement":
            if line.startswith("### "):
                _arr_mode = line[4:].strip().lower()
                continue
            if _arr_mode == "bento":
                key, _, val = line.partition(":")
                if key.strip().lower() in ("heading level", "level"):
                    m = re.search(r"(\d+)", val)
                    if m:
                        theme.bento.heading_level = max(1, min(6, int(m.group(1))))

        # ---- Tables ----------------------------------------------------------
        elif section == "tables":
            if line.startswith("### "):
                sub = line[4:].strip().lower()
                _sstate = {"gl": "", "sl": "stroke"}
                if sub.startswith("table"):
                    _table_mode = "table"
                elif sub.startswith("header"):
                    _table_mode = "header"
                elif sub.startswith("cell"):
                    _table_mode = "cells"
                elif "key" in sub:
                    _table_mode = "keys"
                else:
                    _table_mode = ""
                continue
            tt = theme.tables
            if _table_mode == "table":
                key, _, val = line.partition(":")
                key = key.strip().lower()
                val = val.strip()
                if key == "stacking cards":
                    tt.stacking = val.lower() in ("yes", "true", "1")
                elif key == "card layout":
                    if val.lower() in ("title", "keys"):
                        tt.card_layout = val.lower()
                else:
                    _parse_section_style_line(tt.table, line, raw, _sstate)
            elif _table_mode in ("header", "cells"):
                bullet = line[2:].strip() if line.startswith("- ") else ""
                if bullet.lower().startswith("font") and ":" in bullet:
                    fkey, _, fval = bullet.partition(":")
                    if _table_mode == "header":
                        if tt.header_text is None:
                            tt.header_text = TextStyle()
                        ts = tt.header_text
                    else:
                        if tt.cells_text is None:
                            tt.cells_text = TextStyle()
                        ts = tt.cells_text
                    _set_text_style_field(ts, fkey.strip().lower(), fval.strip())
                else:
                    st = tt.header if _table_mode == "header" else tt.cells
                    _parse_section_style_line(st, line, raw, _sstate)
            elif _table_mode == "keys":
                bullet = line[2:].strip() if line.startswith("- ") else ""
                if bullet.lower().startswith("font") and ":" in bullet:
                    fkey, _, fval = bullet.partition(":")
                    if tt.keys_text is None:
                        tt.keys_text = TextStyle()
                    _set_text_style_field(
                        tt.keys_text, fkey.strip().lower(), fval.strip()
                    )
                elif ":" in line:
                    key, _, val = line.partition(":")
                    if key.strip().lower() == "key spacing":
                        tt.key_spacing = _try_float(val.strip(), tt.key_spacing)

        # ---- Drawing elements (legacy header: Datapoints) ------------------
        elif section in ("drawing elements", "datapoints"):
            if line.startswith("### "):
                _dp_mode = line[4:].strip().lower().replace(" ", "")
                _sstate = {"gl": "", "sl": "stroke"}
                continue
            dp = theme.datapoints
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()
            bars = {
                "ratiobars": dp.ratio_bar,
                "keyvaluebars": dp.kv_bar,
            }
            tracks = {
                "ratiobartrack": dp.ratio_bar.track,
                "keyvaluebartrack": dp.kv_bar.track,
                "ringtrack": dp.ring.track,
            }
            control_styles = {
                "checkedouter": dp.task_controls.checked_outer,
                "checkedinner": dp.task_controls.checked_inner,
                "uncheckedouter": dp.task_controls.unchecked_outer,
                "uncheckedinner": dp.task_controls.unchecked_inner,
            }
            slider_styles = {
                "sliderbar": dp.sliders.bar,
                "slidertrack": dp.sliders.track,
                "sliderhandle": dp.sliders.handle,
                "countbutton": dp.counts.button,
            }
            if _dp_mode == "taskcontrols":
                controls = dp.task_controls
                if key == "enabled":
                    controls.enabled = _parse_bool(val)
                elif key == "type" and val.lower() in ("checkbox", "switch"):
                    controls.type = val.lower()
                elif key == "size":
                    controls.size = _try_float(val, controls.size or 0.0)
                elif key == "padding":
                    controls.padding = max(0.0, _try_float(val, controls.padding))
                elif key == "corner radius":
                    controls.corner_radius = max(0.0, _try_float(val, 0.0))
                elif key == "space":
                    controls.space = max(0.0, _try_float(val, controls.space))
            elif _dp_mode in ("checkedinner", "uncheckedinner") and key in (
                "symbol",
                "symbol color",
            ):
                field = f"{_dp_mode.removesuffix('inner')}_{key.replace(' ', '_')}"
                if key == "symbol":
                    setattr(dp.task_controls, field, val or None)
                elif (color := _try_hex(val, -1)) != -1:
                    setattr(dp.task_controls, field, color)
            elif _dp_mode in control_styles:
                _parse_section_style_line(control_styles[_dp_mode], line, raw, _sstate)
            elif _dp_mode == "sliders":
                sliders = dp.sliders
                if key == "enabled":
                    sliders.enabled = _parse_bool(val)
                elif key == "style" and val.lower() in ("thick", "line"):
                    sliders.style = val.lower()
                elif key == "axis" and val.lower() in (
                    "horizontal",
                    "vertical",
                ):
                    sliders.axis = val.lower()
                elif key == "length":
                    sliders.length = max(1.0, _try_float(val, sliders.length))
                elif key == "thickness":
                    sliders.thickness = max(1.0, _try_float(val, 1.0))
                elif key == "corner radius":
                    sliders.corner_radius = max(0.0, _try_float(val, 0.0))
                elif key == "circle diameter":
                    sliders.circle_diameter = max(
                        1.0, _try_float(val, sliders.circle_diameter)
                    )
                elif key == "drag bar length":
                    sliders.drag_bar_length = max(
                        1.0, _try_float(val, sliders.drag_bar_length)
                    )
                elif key in ("bar thickness", "drag bar thickness"):
                    sliders.drag_bar_thickness = max(
                        1.0, _try_float(val, sliders.drag_bar_thickness)
                    )
                elif key == "drag bar gap":
                    sliders.drag_bar_gap = max(
                        0.0, _try_float(val, sliders.drag_bar_gap)
                    )
            elif _dp_mode == "countbutton" and key == "symbol color":
                if (color := _try_hex(val, -1)) != -1:
                    dp.counts.symbol_color = color
            elif _dp_mode in slider_styles and key != "padding":
                _parse_section_style_line(slider_styles[_dp_mode], line, raw, _sstate)
            elif _dp_mode in bars:
                bar = bars[_dp_mode]
                if key == "enabled":
                    bar.enabled = _parse_bool(val)
                elif key == "thickness":
                    bar.thickness = _try_float(val, bar.thickness)
                elif key == "position" and val.lower() in ("above", "below"):
                    bar.position = val.lower()
                elif key == "text side" and val.lower() in ("left", "right"):
                    bar.text_side = val.lower()
                elif key == "show key" and _dp_mode == "keyvaluebars":
                    bar.show_key = _parse_bool(val)
                elif key == "show value" and _dp_mode == "keyvaluebars":
                    bar.show_value = _parse_bool(val)
                elif key == "negative color":
                    c = _try_hex(val, -1)
                    if c != -1:
                        bar.negative_color = c
                else:
                    _parse_section_style_line(bar.bar, line, raw, _sstate)
            elif _dp_mode in tracks:
                owner = {
                    "ratiobartrack": dp.ratio_bar,
                    "keyvaluebartrack": dp.kv_bar,
                }.get(_dp_mode)
                if key == "enabled" and owner is not None:
                    owner.track_enabled = _parse_bool(val)
                else:
                    _parse_section_style_line(tracks[_dp_mode], line, raw, _sstate)
            elif _dp_mode == "unitratios":
                if key == "enabled":
                    dp.unit_ratio_enabled = _parse_bool(val)
                elif key == "style" and val.lower() in ("bar", "ring"):
                    dp.unit_ratio_style = val.lower()
                elif key == "show total":
                    dp.unit_ratio_show_total = _parse_bool(val)
                elif key == "show key":
                    dp.unit_ratio_show_key = _parse_bool(val)
            elif _dp_mode == "ring":
                fb = _font_bullet(line)
                if fb is not None:
                    if dp.ring.value_text is None:
                        dp.ring.value_text = TextStyle()
                    _set_text_style_field(dp.ring.value_text, *fb)
                elif key == "thickness":
                    dp.ring.thickness = _try_float(val, dp.ring.thickness)
                elif key == "diameter":
                    dp.ring.diameter = _try_float(val, dp.ring.diameter)
                elif key == "spacing":
                    dp.ring.spacing = _try_float(val, dp.ring.spacing)
                else:
                    _parse_section_style_line(dp.ring.ring, line, raw, _sstate)
            elif _dp_mode == "ringunit":
                fb = _font_bullet(line)
                if fb is not None:
                    if dp.ring.unit_text is None:
                        dp.ring.unit_text = TextStyle()
                    _set_text_style_field(dp.ring.unit_text, *fb)
            elif _dp_mode == "dates":
                if key == "enabled":
                    dp.date_chip.enabled = _parse_bool(val)
                elif key == "fill" and val.lower() in ("single", "split"):
                    dp.date_chip.fill = val.lower()
                elif key == "spacing":
                    dp.date_chip.spacing = _try_float(val, dp.date_chip.spacing)
                else:
                    _parse_section_style_line(dp.date_chip.chip, line, raw, _sstate)
            elif _dp_mode in ("datekey", "dateday"):
                is_key = _dp_mode == "datekey"
                fb = _font_bullet(line)
                if fb is not None:
                    if is_key:
                        if dp.date_chip.key_text is None:
                            dp.date_chip.key_text = TextStyle()
                        _set_text_style_field(dp.date_chip.key_text, *fb)
                    else:
                        if dp.date_chip.day_text is None:
                            dp.date_chip.day_text = TextStyle()
                        _set_text_style_field(dp.date_chip.day_text, *fb)
                else:
                    st = dp.date_chip.key_bg if is_key else dp.date_chip.day_bg
                    _parse_section_style_line(st, line, raw, _sstate)

        # ---- Charts ----------------------------------------------------------
        elif section == "charts":
            if line.startswith("### "):
                _chart_mode = line[4:].strip().lower().replace(" ", "")
                _sstate = {"gl": "", "sl": "stroke"}
                continue
            ct = theme.charts
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()
            if _chart_mode == "":
                if key == "enabled":
                    ct.enabled = _parse_bool(val)
                elif key == "mode" and val.lower() in ("bar", "line"):
                    ct.mode = val.lower()
                elif key == "bar thickness":
                    ct.bar_thickness = _try_float(val, ct.bar_thickness)
                elif key == "bar spacing":
                    ct.bar_spacing = _try_float(val, ct.bar_spacing)
                elif key == "bar width" and val.lower() in ("fixed", "fill"):
                    ct.bar_width = val.lower()
                elif key == "negative color":
                    c = _try_hex(val, -1)
                    if c != -1:
                        ct.negative_color = c
                elif key == "percent scale" and val.lower() in ("100", "peak"):
                    ct.percent_scale = val.lower()
                elif key == "value format" and " ".join(val.split()) in VALUE_FORMATS:
                    ct.value_format = " ".join(val.split())
                else:
                    _parse_section_style_line(ct.bar, line, raw, _sstate)
            elif _chart_mode == "charttrack":
                if key == "enabled":
                    ct.track_enabled = _parse_bool(val)
                else:
                    _parse_section_style_line(ct.track, line, raw, _sstate)
            elif _chart_mode == "chartgrid":
                grid = ct.grid
                fb = _font_bullet(line)
                if fb is not None:
                    if grid.text is None:
                        grid.text = TextStyle()
                    _set_text_style_field(grid.text, *fb)
                elif key == "axis labels":
                    grid.axis_labels = _parse_bool(val)
                elif key == "ticks":
                    grid.ticks = max(1, min(20, int(_try_float(val, grid.ticks))))
                elif key == "horizontal lines":
                    grid.horizontal = _parse_bool(val)
                elif key == "vertical lines":
                    grid.vertical = _parse_bool(val)
                elif key == "line color":
                    grid.color = _try_hex(val, grid.color)
                elif key == "line width":
                    grid.width = max(0.0, _try_float(val, grid.width))
                elif key == "line dash":
                    dash = [_try_float(d, 0.0) for d in val.split()]
                    grid.dash = dash if dash and all(d > 0 for d in dash) else []
            elif _chart_mode == "linechart":
                lt = ct.line
                if key == "enabled":
                    lt.enabled = _parse_bool(val)
                elif key == "height":
                    lt.height = max(8.0, _try_float(val, lt.height))
                elif key == "group height":
                    lt.group_height = max(8.0, _try_float(val, lt.height))
                elif key == "line width":
                    lt.width = max(0.5, _try_float(val, lt.width))
                elif key == "line color":
                    c = _try_hex(val, -1)
                    if c != -1:
                        lt.color = c
                elif key == "point size":
                    lt.point_size = max(0.0, _try_float(val, lt.point_size))
                elif key == "points" and val.lower() in ("labelled", "last"):
                    lt.points = val.lower()
                else:
                    _parse_section_style_line(lt.fill, line, raw, _sstate)
            elif _chart_mode == "chartseriescolors":
                if raw.strip().startswith("- "):
                    c = _try_hex(raw.strip()[2:].strip(), -1)
                    if c != -1:
                        ct.series_colors.append(c)
            elif _chart_mode in ("chartlabels", "chartvalues"):
                fb = _font_bullet(line)
                if fb is not None:
                    if _chart_mode == "chartlabels":
                        if ct.label_text is None:
                            ct.label_text = TextStyle()
                        _set_text_style_field(ct.label_text, *fb)
                    else:
                        if ct.value_text is None:
                            ct.value_text = TextStyle()
                        _set_text_style_field(ct.value_text, *fb)

        # ---- Text Styles ---------------------------------------------------
        elif section == "text styles":
            if line.startswith("- "):
                _apply_text_style_bullet(
                    line[2:],
                    subsection,
                    theme,
                    _tier_bullets,
                    _ts_state,
                )
            elif _SUBSECTION_RE.match(line):
                subsection = line.rstrip(":").strip().lower().replace(" ", "")
                _ts_state = {"colors_ts": None}

        # ---- Links -----------------------------------------------------------
        # ### Primary|Secondary|…|Septenary|Text subheaders switch the active
        # target; a flat block with no subheader (back-compat) configures Primary.
        # ### Inline is NOT a button variant — it styles links drawn inside a
        # text run, so it parses its own two keys on theme.links.inline.
        elif section == "links":
            if line.startswith("### "):
                sub = line[4:].strip().lower()
                _link_inline = sub == "inline"
                _link_target = theme.links.primary
                if isinstance(_style := getattr(theme.links, sub, None), LinkStyle):
                    _link_target = _style
                _link_state = {"gl": "", "sl": "", "sh": None}
                continue
            if not _link_inline and _parse_layered_background_line(
                _link_target, line, raw, _link_state
            ):
                continue
            if line.startswith("- "):
                # The list form of Fill/Stroke color. Text style still lives in
                # ## Text Styles — these bullets are colors, never font keys.
                if not _link_inline:
                    _append_color_bullet(
                        line,
                        _link_state,
                        {
                            "fill": _link_target.fill_colors,
                            "stroke": _link_target.stroke_colors,
                        },
                    )
                    if _link_target.fill_colors:
                        _link_target.fill_color = _link_target.fill_colors[0]
                    if _link_target.stroke_colors:
                        _link_target.stroke_color = _link_target.stroke_colors[0]
            elif ":" in line:
                key, _, val = line.partition(":")
                key = key.strip().lower()
                val = val.strip()
                if key == "segmented":  # the section's, from any of its blocks
                    theme.links.segmented = _parse_bool(val)
                elif _link_inline:
                    _parse_inline_link_line(theme.links.inline, key, val)
                else:
                    _parse_link_style_line(_link_target, key, val, _link_state)

        # ---- Inline Code ---------------------------------------------------
        elif section == "inline code":
            if line.startswith("### "):
                sub = line[4:].strip().lower().split()[0]
                # ### Primary configures the base (identical to the flat,
                # subsection-less block THEME.md used before variants existed).
                _code_variant = sub if sub in _CHIP_VARIANTS else None
                if _code_variant:
                    _code_variant_lines.setdefault(_code_variant, [])
                _code_state = {"gl": "", "sl": "", "sh": None}
                continue
            if _code_variant is not None:
                _code_variant_lines[_code_variant].append((line, raw))
            else:
                _parse_inline_code_line(theme.inline_code, line, _code_state, raw)

        # ---- Code Blocks --------------------------------------------------
        elif section == "code blocks":
            if line.startswith("### "):
                _copy_button = line[4:].strip().lower() == "copy button"
                continue
            if _copy_button:
                _parse_copy_button_line(theme.code_blocks, line, raw, _code_state)
            else:
                _parse_code_block_line(theme, line)

        # ---- Content Weight ------------------------------------------------
        elif section == "content weight":
            if ":" in line and not line.startswith("- "):
                key, _, val = line.partition(":")
                key = key.strip().lower()
                val = val.strip()
                if key == "first scale":
                    theme.content_weight.first_scale = _try_float(
                        val, theme.content_weight.first_scale
                    )
                elif key == "second scale":
                    theme.content_weight.second_scale = _try_float(
                        val, theme.content_weight.second_scale
                    )
                elif key == "less scale":
                    theme.content_weight.less_scale = _try_float(
                        val, theme.content_weight.less_scale
                    )
                elif key == "less color":
                    theme.content_weight.less_color = _try_hex(
                        val, theme.content_weight.less_color
                    )

        # ---- Color Replacements --------------------------------------------
        # `On background color: <#hex|image>` opens a group; each bullet under
        # it is one swap, named by the channel it targets (Text / Fill / Stroke
        # color). A bullet with no channel key is that background's TEXT
        # default, used for any text color the group does not name explicitly.
        # The old `## Text Color Replacements` spelling still parses.
        # ---- Fixed colors --------------------------------------------------
        # Meaning-bearing pins: Emoji / Emoji background / Pills / Buttons /
        # Datapoints. Pills and Buttons take #### Exact and #### Contains.
        elif section == "images":  # ### Placeholders (ADR-406)
            _placeholders.line(line)
        elif section == "fixed colors":
            if line.startswith("#### "):
                _fx_sub = line[5:].strip().lower()
                continue
            if line.startswith("### "):
                _fx_block = line[4:].strip().lower()
                _fx_sub = ""
                continue
            if not line.startswith("- "):
                continue
            bullet = line[2:].strip()
            if _fx_block in ("emoji", "emojis"):
                got = _parse_fixed_emoji(bullet)
                if got:
                    theme.fixed.emoji[got[0]] = (got[1], got[2])
            elif _fx_block in ("emoji background", "emoji backgrounds"):
                got = _parse_fixed_emoji(bullet)
                if got:
                    theme.fixed.emoji_bg[got[0]] = got[1]
            elif _fx_block in ("badges", "badge", "buttons", "button"):
                got2 = _parse_fixed_element(bullet)
                if got2:
                    kind = "button" if _fx_block.startswith("button") else "pill"
                    match = "contains" if _fx_sub.startswith("contain") else "exact"
                    target = getattr(theme.fixed, f"{kind}_{match}")
                    target[got2[0]] = got2[1]
            elif _fx_block in ("datapoints", "datapoint"):
                key, _, val = bullet.partition(":")
                c = _try_hex(val.strip(), -1)
                if c != -1 and key.strip():
                    theme.fixed.datapoints[" ".join(key.split()).lower()] = c

        elif section in ("color replacements", "text color replacements"):
            if line.startswith("- "):
                if _tcr_bg is not None:
                    _parse_color_replacement(
                        theme.color_replacements[_tcr_bg], line[2:]
                    )
            elif ":" in line:
                key, _, val = line.partition(":")
                if key.strip().lower() in (
                    "on background color",
                    "on background",
                    "background color",
                ):
                    _tcr_bg = _bg_selector_key(val.strip())
                    if _tcr_bg is not None:
                        theme.color_replacements.setdefault(_tcr_bg, {})

        # ---- Horizontal Rule -----------------------------------------------
        elif section == "horizontal rule":
            _parse_horizontal_rule_line(theme.horizontal_rule, line)

        # ---- Separators ----------------------------------------------------
        elif section == "separators":
            if ":" in line and not line.startswith("- "):
                key, _, val = line.partition(":")
                key = key.strip().lower()
                # "show"/"hide" reads better than yes/no for a glyph, but
                # _parse_bool's spellings keep working.
                shown = val.strip().lower() == "show" or _parse_bool(val.strip())
                if key == "dash":
                    theme.separators.dash = shown
                elif key == "bar":
                    theme.separators.bar = shown

        # ---- Vertical Rule -------------------------------------------------
        elif section == "vertical rule":
            if ":" in line and not line.startswith("- "):
                key, _, val = line.partition(":")
                key = key.strip().lower()
                val = val.strip()
                if key == "draw":
                    theme.vertical_rule.draw = _parse_bool(val)
                elif key == "stroke color":
                    theme.vertical_rule.stroke_color = _try_hex(
                        val, theme.vertical_rule.stroke_color
                    )
                elif key == "stroke width":
                    theme.vertical_rule.stroke_width = _try_float(
                        val, theme.vertical_rule.stroke_width
                    )

        # ---- Emoji styles --------------------------------------------------
        elif section == "emoji styles":
            if line.startswith("### "):
                sub = line[4:].strip().lower()
                _sstate = {"gl": "", "sl": ""}
                if sub.startswith("primary"):
                    _emoji_target = theme.emojis.primary
                elif sub.startswith("text"):
                    _emoji_target = theme.emojis.text
                elif sub.startswith("link"):
                    _emoji_target = theme.emojis.link
                elif sub.startswith("inline"):
                    _emoji_target = theme.emojis.inline
                elif sub.split()[0] in _ELEMENT_VARIANTS:
                    # A badge VARIANT. Buffered raw and replayed onto a copy of
                    # Primary after the whole file, so it inherits every key it
                    # does not state regardless of block order.
                    _emoji_variant = sub.split()[0]
                    _emoji_variant_lines.setdefault(_emoji_variant, [])
                    _emoji_target = None
                    continue
                else:
                    _emoji_target = None
                _emoji_variant = None
                continue
            # A variant block buffers every line verbatim — checked FIRST,
            # because its keys (``Background colors:``) would otherwise be
            # swallowed by the top-level ``Font:`` branch below, which only
            # fires when there is no active ### target.
            if _emoji_variant is not None:
                _emoji_variant_lines[_emoji_variant].append((line, raw))
            # Top-level ``Font:`` (before/outside any ### block) = default font.
            elif _emoji_target is None and ":" in line and not line.startswith("- "):
                key, _, val = line.partition(":")
                if (
                    key.strip().lower() == "font"
                    and val.strip()
                    and not val.strip().startswith("(")
                ):
                    theme.emojis.font_path = val.strip()
            elif isinstance(_emoji_target, EmojiBadgeStyle):
                _parse_emoji_badge_line(_emoji_target, line, raw, _sstate)
            elif isinstance(_emoji_target, EmojiTextStyle):
                _parse_emoji_text_line(_emoji_target, line, raw, _sstate)

        # ---- Fonts ---------------------------------------------------------
        elif section == "fonts":
            if line.startswith("- "):
                val = line[2:].strip()
                if val and not val.lower().startswith("url or path"):
                    theme.font_paths.append(val)

    # Authored display tiers: start from the body-derived default (``Text`` is
    # final by now) and apply only what the block stated, so a block that sets
    # just a colour still gets the tier's proportional size.
    for _t_name, _t_fields in _tier_bullets.items():
        _t_style = _default_tier_style(_t_name, theme)
        for _t_key, _t_val in _t_fields.items():
            _set_text_style_field(_t_style, _t_key, _t_val)
        setattr(theme, _t_name, _t_style)

    # Emoji-badge and chip variants: start from a deep copy of the base and
    # replay only what the block stated, so an unstated key inherits and block
    # order never matters — the same shape as the tiers.
    for _ev_name, _ev_lines in _emoji_variant_lines.items():
        _ev_style = copy.deepcopy(theme.emojis.primary)
        _ev_state = {"gl": "", "sl": ""}
        _ev_own: set[bool] = set()  # the kinds of shadow this variant declares
        for _ev_line, _ev_raw in _ev_lines:
            # A list-valued key REPLACES what it inherited rather than
            # extending it — a variant that states its own palette means that
            # palette, not Primary's plus its own. Shadows too, kind by kind
            # (``inherit_shadows``): the variant's first layer of a kind drops
            # Primary's of that kind, before the cap counts them.
            _ev_key = _ev_line.partition(":")[0].strip().lower()
            _ev_kind = None if _ev_raw.startswith("- ") else _shadow_key(_ev_key)
            if _ev_kind is not None and _ev_kind not in _ev_own:
                _ev_own.add(_ev_kind)
                _ev_style.fill.shadows = [
                    s for s in _ev_style.fill.shadows if s.inner != _ev_kind
                ]
            if _ev_key in ("background color", "background colors"):
                _ev_style.fill.bg_colors = []
            elif _ev_key in ("icon color", "icon colors"):
                _ev_style.icon_colors = []
            elif _ev_key in ("stroke color", "stroke colors"):
                _ev_style.fill.stroke_colors = []
            _parse_emoji_badge_line(_ev_style, _ev_line, _ev_raw, _ev_state)
        setattr(theme.emojis, _ev_name, _ev_style)

    _styling_parser.resolve_fixed_overrides(_parse_section_style_line)

    for _cv_name in _CHIP_VARIANTS:
        _cv_lines = _code_variant_lines.get(_cv_name)
        _cv_prior = getattr(theme.inline_code, _cv_name, None)
        if _cv_lines is None and _cv_prior is None:
            continue  # neither a ## Inline Code block nor a text style
        _cv_style = copy.deepcopy(theme.inline_code)
        for _cv_other in _CHIP_VARIANTS:
            setattr(_cv_style, _cv_other, None)
        # An "Inline Code <Variant>" text style was parsed as a patch of what it
        # stated; it overrides a copy of the base's, so an unstated key inherits.
        if isinstance(_cv_prior, TextStylePatch):
            _cv_base = theme.inline_code.effective_text_style(theme.text)
            _cv_style.text_style = _cv_prior.apply(_cv_base)
        _cv_state: dict = {"gl": "", "sl": "", "sh": None}
        _cv_own: set[bool] = set()  # the kinds of shadow this variant declares
        for _cv_line, _cv_raw in _cv_lines or ():
            # A variant that opens a color list REPLACES the inherited one
            # rather than appending to it, mirroring the emoji badge replay
            # above — otherwise ### Secondary would extend Primary's cycle.
            # Shadows likewise, kind by kind.
            _cv_key = _cv_line.partition(":")[0].strip().lower()
            _cv_kind = (
                None if (_cv_raw or _cv_line).startswith("- ") else _shadow_key(_cv_key)
            )
            if _cv_kind is not None and _cv_kind not in _cv_own:
                _cv_own.add(_cv_kind)
                _cv_style.shadows = [
                    s for s in _cv_style.shadows if s.inner != _cv_kind
                ]
            if _cv_key in (
                "fill color",
                "fill colors",
                "background color",
                "background colors",
            ):
                _cv_style.fill_colors = []
            elif _cv_key in ("stroke color", "stroke colors"):
                _cv_style.stroke_colors = []
            _parse_inline_code_line(_cv_style, _cv_line, _cv_state, _cv_raw)
        setattr(theme.inline_code, _cv_name, _cv_style)

    # A `## Fixed colors > ### Emoji` pin is a statement about the GLYPH, not
    # about the node that happens to hold it: ☀️ is amber wherever it appears.
    # It reaches emoji that are their own node through `stamp_fixed_colors`,
    # but an emoji inside a prose line or a heading is drawn as an inline glyph
    # run, which reads its colours from the text-context styles instead. Seed
    # those from the pin table so ONE declaration covers both, and so the same
    # glyph cannot come out amber in one line and grey in the next.
    #
    # `setdefault`, so an explicit `### Text|Link|Inline > Fixed colors` entry
    # still wins — the same "inherit unless stated" shape as the variant blocks
    # above. The pin's SCOPE is dropped on purpose: it governs how far a pin
    # spreads to sibling NODES, which has no meaning for one glyph inside a run.
    for _tc_style in (
        theme.emojis.text,
        theme.emojis.link,
        theme.emojis.inline,
    ):
        for _pin_glyph, (_pin_color, _pin_scope) in theme.fixed.emoji.items():
            _tc_style.fixed_colors.setdefault(_pin_glyph, _pin_color)

    # Button-variant fields (secondary…septenary, text) stay as raw
    # THEME.md overrides here — call theme.links.resolved(variant) to get
    # the fully concrete, Primary-merged LinkStyle for rendering (resolved
    # lazily so it can't go stale if Primary itself was edited later in the
    # file than a variant's block).
    return theme
