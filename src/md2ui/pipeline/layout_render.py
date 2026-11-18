"""
md_layout_render.py

Renders basic-grouping-ast.json into each breakpoint layout, drawing content
inside each box according to its hint type (heading, text, image).
Box heights are content-fitted: text boxes are only as tall as their text;
images in col stacks use a proportional placeholder height; images in row
splits expand to fill their tallest sibling.

Navigate breakpoints with ← → arrow keys.  ESC to quit.
"""

import colorsys
import dataclasses
import json
import math
import re
from collections.abc import Callable

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.layout_script_parser import LayoutBox, LayoutNode
from md2ui.pipeline.render_colors import (
    _pin_or_replace,
    _replace_color,
    _rotate_color,
    _rotation_slot,
    _synced_slot,
    _table_background_color,
    painted_pins,
    stamp_fixed_colors,
)
from md2ui.pipeline.render_bars import _draw_datapoint_bar, _draw_ring_arc
from md2ui.pipeline.render_backgrounds import (
    SectionBox,
    _layers_pad,
    _layers_section_level,
    _opaque_or_none,
    _own_surface,
    _paint_style_for,
    _push_bg,
    _wrap_layers,
)
from md2ui.pipeline.render_chart import _chart_vertical_min_width, _draw_chart
from md2ui.pipeline.render_line_chart import draw_line_chart
from md2ui.pipeline.render_code_blocks import code_block_plan, draw_code_block
from md2ui.pipeline.render_counts import draw_count, is_count
from md2ui.pipeline.render_pill_paint import paint_pill
from md2ui.pipeline.render_segmented import choice_style, paint_segmented
from md2ui.pipeline.render_fills import (
    _paint_layered_fill,
    _replaced_gradient,
    draw_picture,
    replaced_surface,
)
from md2ui.pipeline.render_image_placeholder import Painter, named_placeholder
from md2ui.pipeline.render_placeholders import (
    NO_PICTURE,
    card_photo,
    element_picture,
    element_pictures,
    image_picture,
    theme_picture,
)
from md2ui.pipeline.render_ring_text import ring_text
from md2ui.pipeline.render_settings import VIEW
from md2ui.pipeline.render_shadows import draw_stroke
from md2ui.pipeline.render_drawing_elements import (
    draw_slider,
    draw_task_control,
    drawing_element_min_width,
)
from md2ui.pipeline.render_metrics import (
    _chip_metrics,
    _text_ink,
    _code_font,
    _emoji_badge_size,
    _image_content_width,
    _label_runs_width,
    _link_label_width,
    _link_pill_size,
    _measure_word,
    _text_emoji_px,
    _widest_unit,
    _wrap_lines,
)
from md2ui.pipeline.render_measure import (
    LINE_SCALE,
    _BREAK_LEAVES,
    _child_owner_level,
    _explode_words,
    _is_text_marker,
    _leaf_natural_width,
    _padded_children,
    _line_width,
    _sibling_gap,
    _table_cell_min_width,
    _text_extent_rect,
    natural_height,
)

# The one thing the width walk needs from the generator's vocabulary: how narrow
# a text of N words may be squeezed before it is allowed to collapse inside.
from md2ui.pipeline.generator_units import LEAF_WIDTH
from md2ui.pipeline.render_place import (
    place_boxes,
)
from md2ui.pipeline.render_style import (
    FontSet,
    _apply_date_role,
    _apply_kv_role,
    _date_chip_text_style,
    _date_role_content,
    _effective_leaf_node,
    _effective_text_fonts,
    _emoji_glyph_font,
    _heading_level,
    _load_emoji_typeface,
    _marker_font,
    _prose_emoji_paint,
    _prose_text_is_styled,
    _resolve_h_align,
    _resolve_link,
    _span_font,
    _table_key_fonts,
    _table_text_style,
    _text_style_scopes,
    _weight_scale_and_color,
    scoped_text_style,
)
from md2ui.pipeline.render_text import _emoji_clusters, emoji_pin, project_paint_spans
from md2ui.pipeline.render_text_scopes import (
    link_label_fonts,
    scoped_horizontal_rule_style,
)
from md2ui.pipeline.render_glyph_faces import glyph_advance
from md2ui.pipeline.render_text_paint import _draw_text_with_emoji, draw_glyph_runs
from md2ui.pipeline.grouper_types import normalize_emoji_kind
from md2ui.pipeline.markdown_grouper import (
    ASTPatternAnalyzer,
    MarkdownGroupNode,
)
from md2ui.pipeline.theme import (
    BG_IMAGE,
    CONTENT_WIDTH_MAX,
    CONTENT_WIDTH_MIN,
    EmojiTextStyle,
    InlineCodeTheme,
    PaddingBox,
    SectionStyle,
    TextStyle,
    Theme,
)
from md2ui.utils.image_cache import ImageCache, Picture
from md2ui.utils.image_params import image_alt, image_url
from md2ui.utils.scroll_state import ScrollState
from md2ui.utils.font_loader import make_font

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

PADDING = 30  # window chrome padding
RESIZE_DEBOUNCE = 0.15  # seconds after last resize event before regenerating layout
RESIZE_REGEN_THROTTLE = 0.05  # min seconds between live regenerations during drag
TITLE_H = 26  # top title bar height
HINT_H = 22  # bottom hint bar height


# Heading colors (per level h1–h6), the fallback when the theme sets none
HEADING_COLORS = {
    1: skia.ColorSetARGB(255, 10, 10, 10),
    2: skia.ColorSetARGB(255, 25, 25, 25),
    3: skia.ColorSetARGB(255, 40, 40, 40),
    4: skia.ColorSetARGB(255, 55, 55, 55),
    5: skia.ColorSetARGB(255, 70, 70, 70),
    6: skia.ColorSetARGB(255, 85, 85, 85),
}

# Chrome typography
CHROME_SIZE = 12
HINT_SIZE = 11

# Colors
BG_COLOR = skia.ColorSetARGB(255, 245, 245, 245)
# Chrome/frame background (behind title, path, hint bar) — distinct from the layout
# render area, which keeps the theme's content background.
FRAME_BG_COLOR = skia.ColorSetARGB(255, 26, 27, 32)
# Wireframe per-box color palette — (fill, stroke) pairs, generated from HSV color wheel


def _hsv_wireframe_pair(hue: float) -> tuple[int, int]:
    r, g, b = (round(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.75, 0.90))
    rs, gs, bs = (round(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.90, 0.70))
    return skia.ColorSetARGB(70, r, g, b), skia.ColorSetARGB(220, rs, gs, bs)


_PALETTE_SIZE = 12
WIREFRAME_PALETTE: list[tuple[int, int]] = [
    _hsv_wireframe_pair(i / _PALETTE_SIZE) for i in range(_PALETTE_SIZE)
]
TEXT_COLOR = skia.ColorSetARGB(255, 60, 60, 60)
# Debug overlay colors (spacing gaps toggled with D, padding rings with P).
#
# Padding and spacing are each drawn as an 8-tier hue ramp so the nesting depth
# reads off the color. Tiers: 0=root, 1..6=heading levels, 7=element/card.
#   - Paddings ramp green -> blue -> purple (root green, element purple)
#   - Spacings ramp yellow -> orange -> red (root yellow, element red)
_DEBUG_TIERS = 8


def _debug_ramp(h0: float, h1: float, alpha: int) -> list[int]:
    """8 ARGB fill colors interpolating hue h0->h1 (HSV), one per debug tier."""
    out: list[int] = []
    for i in range(_DEBUG_TIERS):
        h = h0 + (h1 - h0) * (i / (_DEBUG_TIERS - 1))
        r, g, b = (round(c * 255) for c in colorsys.hsv_to_rgb(h, 0.75, 0.88))
        out.append(skia.ColorSetARGB(alpha, r, g, b))
    return out


PADDING_DEBUG_RAMP = _debug_ramp(0.33, 0.78, 115)  # green -> blue -> purple
SPACING_DEBUG_RAMP = _debug_ramp(0.14, 0.0, 115)  # yellow -> orange -> red
DEBUG_TEXTBOX_COLOR = skia.ColorSetARGB(255, 230, 20, 120)  # real text box (magenta)
# Link / inline-code padding rings in the P overlay — a distinct orange, separate from
# the green->blue->purple section/card/root padding ramp.
LINKCODE_PAD_DEBUG_COLOR = skia.ColorSetARGB(150, 255, 145, 0)
# Per-frame accumulator of (outer, inner) rects for link + inline-code padding, filled
# during the draw pass (when VIEW.debug_padding) and painted in the P overlay.
_DEBUG_PAD_RINGS: "list[tuple[skia.Rect, skia.Rect]]" = []


def _padding_tier(sb: "SectionBox") -> int:
    """Padding-ramp tier for a section box: root=0, heading=level(1-6), card=7."""
    if sb.kind in ("card", "image_card", "quote") or sb.kind.endswith("_list"):
        return _DEBUG_TIERS - 1
    if sb.kind == "root":
        return 0
    return sb.level  # 1..6


def _spacing_debug_color(level: int | None) -> int:
    """Spacing-ramp color for a gap owned by *level* (0=root..6); None -> root."""
    return SPACING_DEBUG_RAMP[level if level is not None else 0]


IMAGE_DECO_COLOR = skia.ColorSetARGB(255, 150, 150, 150)
CHROME_COLOR = skia.ColorSetARGB(255, 100, 100, 100)
LINK_RADIUS = 16.0  # rounded-rect corner radius


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


_HEADING_TYPE_RE = re.compile(r"^heading([1-6])$")

_NO_HEADING_STYLE = frozenset({"link", "inline_code", "image", *_BREAK_LEAVES})


def load_node_index(source: "str | dict", theme: "Theme | None" = None) -> dict:
    """Flatten the AST into {node_id: node_dict} for O(1) lookup.

    *source* is a ``grouping-ast.json`` path, or the grouper's ``to_dict()``
    already in memory — which is how the app and the CLI hand it over. A dict
    is indexed in place, and mutated.

    *theme* is optional and used only to resolve ``## Fixed colors`` onto the
    tree while it is still a tree — a pin can reach a leaf's siblings, which a
    drawer holding one box could never do.
    """
    if isinstance(source, dict):
        root = source
    else:
        with open(source, encoding="utf-8") as f:
            root = json.load(f)
    index: dict = {}
    _walk(root, index)
    if theme is not None:
        stamp_fixed_colors(root, theme)
    return index


def _walk(node: dict, index: dict, h_level: int = 0, h_line: int | None = None) -> None:
    """Index every node by id and stamp each one's heading context.

    A heading LINE that the grouper split keeps its ``heading{N}`` type only on
    the line's container (and sometimes on one piece); the other pieces come out
    as ``segment``/``key``/``value``/``datapoint`` and would otherwise render as
    body text. ``heading_ctx`` carries the level down to them so every path that
    resolves fonts (``_effective_text_fonts``) styles the whole line alike.

    The anchor is deliberately the heading *line* — a ``heading{N}``-typed node
    that has a ``source_line_id`` — never the heading *content group*
    (``heading_group``), which spans the section's body lines too. Inheritance
    therefore follows the line id, not child position, so the heading's text
    element may sit at any depth inside the line.

    Note the *structural* ancestry a color-rotation gate needs is a different
    thing and is not computed here: ``rotation_chain`` comes straight off the
    grouper's annotation, so leaves and container boxes read one source.
    """
    nid = node.get("node_id", "")
    if nid:
        index[nid] = node
    # A persisted AST may carry a legacy spelling; migrate it here, on the very
    # dicts the drawers read, so the node_index and MarkdownGroupNode.from_dict
    # cannot disagree about one node (see normalize_emoji_kind).
    if node.get("emoji_kind") is not None:
        node["emoji_kind"] = normalize_emoji_kind(node["emoji_kind"])
    node_type = node.get("type", "") or ""
    line = node.get("source_line_id")
    level = _node_heading_level(node_type, node.get("atx_level", 0))
    if level and line is not None:
        h_level, h_line = level, line
    if h_level and line == h_line and node_type not in _NO_HEADING_STYLE:
        node["heading_ctx"] = h_level
    for child in node.get("children", []):
        _walk(child, index, h_level, h_line)


def _node_heading_level(node_type: str, atx_level: int) -> int:
    """The heading level a node itself declares: its ``heading{N}`` type, or the
    grouper's ``atx_level`` for a heading written inside another block. 0 when
    it is not a heading."""
    m = _HEADING_TYPE_RE.match(node_type or "")
    if m:
        return int(m.group(1))
    return atx_level


def _stamp_heading_ctx(
    node: MarkdownGroupNode, h_level: int = 0, h_line: int | None = None
) -> None:
    """``_walk``'s heading stamping for the MarkdownGroupNode tree.

    The generator measures min widths straight off these nodes
    (``make_width_measurer``), so they must resolve the same heading style the
    renderer draws with — otherwise a split heading line would be provisioned at
    body width and packed too tightly."""
    level = _node_heading_level(node.type, node.atx_level)
    if level and node.source_line_id is not None:
        h_level, h_line = level, node.source_line_id
    if h_level and node.source_line_id == h_line and node.type not in _NO_HEADING_STYLE:
        node.heading_ctx = h_level
    for child in node.children:
        _stamp_heading_ctx(child, h_level, h_line)


def _attach_data_points(node: MarkdownGroupNode, d: dict) -> None:
    """Re-attach data_points dropped by from_dict."""
    node.data_points = d.get("data_points", [])
    for child, cd in zip(node.children, d.get("children", [])):
        _attach_data_points(child, cd)


def load_grouping_ast_node(source: "str | dict") -> MarkdownGroupNode:
    """Reconstruct a MarkdownGroupNode tree from a grouping AST path or dict."""
    if isinstance(source, dict):
        d = source
    else:
        with open(source, encoding="utf-8") as f:
            d = json.load(f)
    node = MarkdownGroupNode.from_dict(d)
    _attach_data_points(node, d)
    _stamp_heading_ctx(node)
    ASTPatternAnalyzer(node).fingerprints(include_unique=True)
    return node


def _content_width(
    avail_w: float, theme: "Theme | None" = None, *, min_width: float = 0.0
) -> float:
    """Clamp an available viewport width to the layout's content-width range.

    The caller passes the viewport width from ``_viewport_metrics`` (already inset
    by the chrome when the frame is shown), so the layout fills the window width
    when the frame is hidden.

    The upper bound is the THEME's root ``Max width`` (default
    ``CONTENT_WIDTH_MAX``); ``theme=None`` keeps that default, which is why the
    parameter is optional — hand-built callers and tests pass a bare width.

    ``min_width`` is what the DOCUMENT's own content needs — the app shell
    measures it with ``generator_units.document_min_width`` and hands it in as a
    plain float (the renderer imports nothing from the generator). It outranks
    both ``CONTENT_WIDTH_MIN`` and the cap, because content is incompressible: a
    pill, a word and a table column do not shrink at draw time, so a width under
    this one is a width the layout cannot render in, whatever asked for it.
    ``Max width`` is a limit on GROWTH. Past this floor
    the layout stops shrinking and the window scrolls horizontally instead.
    Defaults to 0.0, so a caller with no measurer simply gets no floor.
    """
    cap = (
        getattr((theme or Theme()).root, "max_width", CONTENT_WIDTH_MAX)
        or CONTENT_WIDTH_MAX
    )
    return float(max(CONTENT_WIDTH_MIN, min_width, min(cap, avail_w)))


def _content_origin_x(
    vp_x: float, la_w: float, layout_w: float, pad_left: float, centered: bool
) -> float:
    """X of the layout's content origin inside the viewport.

    The layout stops growing at ``Max width``, so in a wider window there is
    slack. ``Centered`` (the default) splits it either side; otherwise the
    layout stays hard left, which is what md2ui did before the key existed.

    Only ever non-zero when ``layout_w < la_w`` — exactly the regime where the
    content already fits, so ``ScrollState.clamp`` pins ``scroll.x`` at 0 and no
    horizontal scrollbar is drawn. That is why centring needs no change to the
    scroll math.
    """
    slack = max(0.0, la_w - layout_w)
    return vp_x + pad_left + (slack / 2.0 if centered else 0.0)


def _viewport_metrics(win_w: int, win_h: int) -> tuple[float, float, float, float]:
    """Layout viewport rect ``(x, y, w, h)`` in window space.

    With the chrome frame shown it's inset by the padding/title/hint chrome; with
    ``VIEW.show_frame`` off the viewport fills the whole window so the layout drawing
    area expands edge-to-edge. Single source of truth shared by ``draw_scene`` and
    the scroll math so both agree in either mode. A connected window's prompt bar
    (``VIEW.prompt_bar_h``, ADR-601) takes the bottom edge in both.
    """
    bar = VIEW.prompt_bar_h
    if VIEW.show_frame:
        return (
            float(PADDING),
            float(PADDING + TITLE_H),
            float(win_w - PADDING * 2),
            float(win_h - PADDING * 2 - TITLE_H - HINT_H - bar),
        )
    return 0.0, 0.0, float(win_w), float(win_h - bar)


def _layout_width(win_w: int, win_h: int, theme: Theme | None = None) -> float:
    """Width handed to the layout generator: the viewport width minus
    ``content.padding`` on both sides. Reducing it makes the layout collapse
    responsively (rows→cols) to fit the narrower area (X padding = reduce space).
    """
    vp_w = _viewport_metrics(win_w, win_h)[2]
    pad = (theme or Theme()).root.padding
    return max(0.0, vp_w - pad.x)


# ---------------------------------------------------------------------------
# Content-fitted height measurement
# ---------------------------------------------------------------------------


def load_background_images(theme: Theme) -> dict[object, "skia.Image"]:
    """Decode every themed background image once (local path or URL).

    Returns ``{level: skia.Image}`` keyed by heading level, with **key 0 = root**
    (``theme.root.bg_image``). Levels with no image, or one a server never
    fetched, are absent; a failed one holds the broken placeholder
    (``render_placeholders.theme_picture``). Element images are keyed by
    ``("element", source)`` so variants that inherit or share one source also
    share its decoded image.
    Mirrors ``_load_placeholders``.
    """
    images: dict[object, skia.Image] = {}
    root_img = theme_picture(theme.root.bg_image)
    if root_img is not None:
        images[0] = root_img
    for key, style in (
        (-5, theme.image_cards),
        (-6, theme.unordered_lists),
        (-9, theme.task_lists),
        (-7, theme.numbered_lists),
        (-8, theme.quotes),
        (-2, theme.tables.header),
        (-3, theme.tables.cells),
        (-4, theme.tables.table),
    ):
        image = theme_picture(style.bg_image)
        if image is not None:
            images[key] = image
    for level, st in theme.sections.items():
        img = theme_picture(st.bg_image)
        if img is not None:
            images[level] = img
    for key, st in theme.fixed_sections.items():
        img = theme_picture(st.bg_image)
        if img is not None:
            images[f"fixed:{key}"] = img
    images.update(element_pictures(theme))
    return images


def _paint_section_background(
    canvas: skia.Canvas,
    sbox: SectionBox,
    style: SectionStyle,
    image: "Picture | None" = None,
    bg_color: int | None = None,
    theme: "Theme | None" = None,
    strokes: list | None = None,
) -> None:
    """Paint one section's background: layered fill (color → image → gradient)
    then the stroke on top. Any unset (None/zero) parameter paints nothing.

    ``bg_color`` is the rotated solid fill; given ``theme``, it and the gradient
    are replaced against what the box sits on, as a pill's are. Given
    ``strokes``, the stroke is queued there instead, for ``draw_document`` to
    paint after the content: a photo or card reaching the edge must not cover it.
    """
    rect = skia.Rect.MakeXYWH(sbox.x, sbox.y, sbox.width, sbox.height)
    r = style.corner_radius
    fill, gradient = replaced_surface(bg_color, style.gradient, sbox.bg_stack, theme)
    _paint_layered_fill(
        canvas,
        rect,
        bg_color=fill,
        image=image,
        gradient=gradient,
        corner_radius=r,
        shadows=style.shadows,
    )
    if style.stroke_width > 0 and style.stroke_color is not None:
        stroke_color = style.stroke_color
        if theme is not None:
            stroke_color = _replace_color(
                stroke_color,
                _push_bg(sbox.bg_stack, _own_surface(sbox, style, fill)),
                theme,
                "stroke",
            )
        stroke_paint = skia.Paint(
            Color=stroke_color,
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=style.stroke_width,
            AntiAlias=True,
        )
        if strokes is not None:
            strokes.append((rect, r, stroke_paint, style.stroke_align, sbox.clip))
        else:
            draw_stroke(canvas, rect, r, stroke_paint, style.stroke_align)


def _clip_to_shell(canvas: skia.Canvas, clip: tuple) -> None:
    """Clip to a merged table shell's rounded rect, so a row inside it does not
    overpaint the shell's corners. The caller restores."""
    clx, cly, clw, clh, clr = clip
    canvas.save()
    clip_path = skia.Path()
    clip_path.addRoundRect(skia.Rect.MakeXYWH(clx, cly, clw, clh), clr, clr)
    canvas.clipPath(clip_path, skia.ClipOp.kIntersect, True)


def _draw_section_padding_overlay(canvas: skia.Canvas, section_boxes: list) -> None:
    """Fill each section's padding ring (between the outer box and inset content).

    Each ring is colored by its padding tier (root/heading level/element) along
    the green->blue->purple ramp.
    """
    for sb in section_boxes:
        p = sb.padding
        if not p.any():
            continue
        paint = skia.Paint(
            Color=PADDING_DEBUG_RAMP[_padding_tier(sb)],
            Style=skia.Paint.kFill_Style,
            AntiAlias=True,
        )
        x, y, w, h = sb.x, sb.y, sb.width, sb.height
        mid_h = h - p.top - p.bottom  # left/right band height (between T/B bands)
        canvas.drawRect(skia.Rect.MakeXYWH(x, y, w, p.top), paint)  # top
        canvas.drawRect(
            skia.Rect.MakeXYWH(x, y + h - p.bottom, w, p.bottom), paint
        )  # bottom
        canvas.drawRect(skia.Rect.MakeXYWH(x, y + p.top, p.left, mid_h), paint)  # left
        canvas.drawRect(
            skia.Rect.MakeXYWH(x + w - p.right, y + p.top, p.right, mid_h),
            paint,
        )  # right


def _draw_pad_ring(
    canvas: skia.Canvas, outer: "skia.Rect", inner: "skia.Rect", color: int
) -> None:
    """Fill the 4 padding bands between an ``outer`` box and its ``inner`` content."""
    paint = skia.Paint(Color=color, Style=skia.Paint.kFill_Style, AntiAlias=True)
    canvas.drawRect(
        skia.Rect.MakeLTRB(outer.left(), outer.top(), outer.right(), inner.top()),
        paint,
    )  # top
    canvas.drawRect(
        skia.Rect.MakeLTRB(outer.left(), inner.bottom(), outer.right(), outer.bottom()),
        paint,
    )  # bottom
    canvas.drawRect(
        skia.Rect.MakeLTRB(outer.left(), inner.top(), inner.left(), inner.bottom()),
        paint,
    )  # left
    canvas.drawRect(
        skia.Rect.MakeLTRB(inner.right(), inner.top(), outer.right(), inner.bottom()),
        paint,
    )  # right


# ---------------------------------------------------------------------------
# Render-property helpers (hints attached to LayoutNode/LayoutBox)
# ---------------------------------------------------------------------------


# Positions of the region ids inside a word tuple
# ``(text, bold, italic, code, strike, link)``. Both are 0 when unflagged and
# otherwise identify WHICH region the word belongs to (see parse_inline_spans).
_FLAG_CODE, _FLAG_STRIKE, _FLAG_LINK = 3, 4, 5


def _flag_runs(
    line: list, flag_i: int, start_x: float, fonts: FontSet, size: float
) -> list[tuple[float, float, int]]:
    """``[(x0, x1, first_word_index)]`` per flagged REGION on this line.

    The x-walk mirrors ``draw_styled_text_box``'s drawing loop exactly — one
    space advance between words — so a run spans the spaces *inside* one region.
    That is the whole point: a span style that paints a region (a marker
    background, a strikethrough rule) has to cover ``two words`` as one region
    rather than leaving a gap at every space.

    It stops at the region's edge, though. Two adjacent regions (```a` `b```,
    ``~~a~~ ~~b~~``) have nothing but a space between them, so a run keyed on the
    flag alone would swallow that space and paint them as one — which is why the
    break is on the region id changing, not on the flag going off.
    """
    runs: list[tuple[float, float, int]] = []
    x = start_x
    run_start: float | None = None
    run_end = 0.0
    first_i = 0
    run_id = 0
    for word_i, w in enumerate(line):
        word, bold, italic = w[0], w[1], w[2]
        # Same space rule as the painter and the measurer; a run's x would drift
        # from the glyphs it underlines otherwise (ADR-400).
        if word_i > 0 and w[6]:
            x += _span_font(fonts, size, bold, italic).measureText(" ")
        word_w = _measure_word(word, bold, italic, fonts, size)
        rid = w[flag_i]
        if rid:
            if run_start is not None and rid != run_id:
                runs.append((run_start, run_end, first_i))
                run_start = None
            if run_start is None:
                run_start, first_i, run_id = x, word_i, rid
            run_end = x + word_w
        elif run_start is not None:
            runs.append((run_start, run_end, first_i))
            run_start = None
        x += word_w
    if run_start is not None:
        runs.append((run_start, run_end, first_i))
    return runs


def _marker_style(
    theme: Theme,
    node_type: str,
    level: int,
    table_role: str | None = None,
    text_style: str | None = None,
    node: dict | None = None,
) -> "TextStyle":
    """The style whose ``Marker …`` keys paint inline ``code`` spans in a leaf.

    Mirrors ``_effective_text_fonts``'s branch order so a marker is painted by
    the same ``## Text Styles`` block that sizes the text it sits in. A block
    that sets neither marker key falls back to ``Text``'s, so a theme can style
    every marker once and still override a heading level."""
    text_scopes = _text_style_scopes(node)
    if table_role and not level:
        ts = _table_text_style(theme, table_role)
    elif level:
        ts = theme.headings.get(level)
    elif text_style:
        ts = scoped_text_style(theme, text_style, text_scopes)
    elif node_type == "key":
        ts = scoped_text_style(theme, "key", text_scopes)
    else:
        ts = scoped_text_style(theme, "text", text_scopes)
    if ts is None or (ts.marker_text_color is None and ts.marker_bg_color is None):
        ts = scoped_text_style(theme, "text", text_scopes)
    return _rotated_marker(ts, node, theme)


def _rotated_marker(ts: "TextStyle", node: dict | None, theme: Theme) -> "TextStyle":
    """*ts* with this leaf's slot picked out of its marker color lists.

    A marker is the in-text form of a chip, so it cycles on the ``chip``
    channel — one gate covers both, and a theme never learns a seventh channel
    name. Colors only: a marker keeps its block's font, size and weight, so no
    measurement can change. Returns *ts* untouched unless a list holds two or
    more colors.
    """
    if node is None or not (ts.marker_text_colors or ts.marker_bg_colors):
        return ts
    idx, chain = _rotation_slot(node, theme)
    return dataclasses.replace(
        ts,
        marker_text_color=_rotate_color(
            ts.marker_text_colors, ts.marker_text_color, idx, theme, "chip", chain
        ),
        marker_bg_color=_rotate_color(
            ts.marker_bg_colors, ts.marker_bg_color, idx, theme, "chip", chain
        ),
    )


def _toggle_state(on: bool) -> str:
    """Label for an interactive layout toggle (title bar / key print). Two states,
    never a third "follow the theme": a toggle is seeded from the theme already."""
    return "on" if on else "off"


def make_layout_measurer(node_index: dict, fonts: FontSet, theme: Theme | None):
    """Height-for-width closure for ``LayoutGenerator.generate(measure=...)``.

    The generator's bento mode calls it to score candidate cells: given a built
    layout subtree and its *outer* cell width, it returns the rendered height.
    Wrap-layer aware: a section/card cell is measured at the padding-reduced
    inner width and extended by the summed TLRB paddings, mirroring the col
    branch of ``natural_height`` / ``place_boxes``.
    """
    _t = theme or Theme()

    def measure(cell: LayoutNode, width: float) -> float:
        layers = _wrap_layers(cell, _t, frozenset())
        if layers:
            tpad = _layers_pad(layers)
            slvl = _layers_section_level(layers)
            levels = frozenset({slvl}) if slvl is not None else frozenset()
            owner = _child_owner_level(cell, _t, 0)
            return (
                natural_height(
                    cell,
                    max(0.0, width - tpad.x),
                    node_index,
                    fonts,
                    _t,
                    levels,
                    owner,
                )
                + tpad.y
            )
        return natural_height(cell, width, node_index, fonts, _t)

    return measure


def _code_block_width(
    content: str, language: str | None, fonts: FontSet, theme: Theme
) -> float:
    """A code block's whole width, the one its paint draws (ADR-400): it scrolls
    once placed, but that is what it asks a layout for."""
    face = fonts.code_block or fonts.mono or fonts.typeface
    return code_block_plan(content, language, face, theme.code_blocks).width


def _stacked_text_width(
    nd: dict | None, fonts: FontSet, theme: Theme, rp: dict | None
) -> float | None:
    """A text leaf's width on ONE line, or None when the leaf is not text.

    A stacked section wraps to the next row before the text inside it wraps
    (see ``make_block_width_measurer``), so a text cell is worth the line it
    would draw rather than its longest unbreakable word. A code block's line is
    its widest source line in the code face.

    ``None`` means "not my question", and there are two ways to be:

    * the leaf is not text -- a pill, a chip, an emoji or an image. Those are
      already measured whole by the caller, and an image's allocation was never
      a claim about text;
    * the leaf is a FILLER -- a rule, a chart, a bar. Those return the width
      they were offered, which is infinite here. An answer that is just the
      question back is not an opinion about content.
    """
    if nd is None:
        return None
    if nd.get("type") == "code_block":
        return _code_block_width(nd["content"], nd.get("code_language"), fonts, theme)
    if nd.get("type", "") in ("link", "inline_code", "emoji", "image"):
        return None
    if not nd.get("content"):
        return None
    w = _leaf_natural_width(nd, float("inf"), fonts, theme, rp)
    return w if math.isfinite(w) else None


def make_block_width_measurer(node_index: dict, fonts: FontSet, theme: Theme | None):
    """The width below which a built block starts to COLLAPSE.

    ``Stack sections`` needs a block's own width requirement, and neither existing
    measurer is one: ``natural_width`` of a section returns whatever it is given
    (a band with a background fills its slot, so it reports 6000 of 6000), and
    the markdown-side minimum reports the widest unbreakable WORD, which is far
    under what the block's arrangement needs.

    The honest question is asked of the BUILT tree, where the rows are real:

      * a **row** costs the sum of its cells plus the gaps and paddings the
        renderer will really put between and around them — springs off, packed
        left, which is the arrangement's own width;
      * a **column** costs the widest of its children, since they stack;
      * a **leaf** costs the width it would draw at: a whole pill, and for text
        the whole LINE — a stacked section is meant to wrap to the next row
        before the text inside it wraps, so a card is never squeezed until its
        own title breaks in two. A section holding a paragraph therefore asks
        for more than the line and keeps the line, which is what a card gets
        anyway unless it grids or stacks.

    So the answer is the longest ROW in the block, measured through the same
    ``_sibling_gap`` and wrap-padding the paint uses. Below it some row has to
    give up a cell; at or above it the block keeps the shape it was built with.
    Width-independent by construction, which is why the caller memoises it.
    """
    _t = theme or Theme()

    def width(
        cell: LayoutNode,
        avail: float,
        levels: frozenset = frozenset(),
        owner: int = 0,
    ) -> float:
        layers = _wrap_layers(cell, _t, levels)
        pad = _layers_pad(layers) if layers else PaddingBox()
        slvl = _layers_section_level(layers) if layers else None
        inner_levels = frozenset({slvl}) if slvl is not None else levels
        inner_owner = _child_owner_level(cell, _t, owner)
        kids = _padded_children(cell)
        if not kids:
            rp = cell.render_properties or {}
            # A gutter marker and a drawn separator are SYNTHETIC leaves: no
            # markdown node behind them, so the cell minimum below reads them as
            # 0 and the gutter vanishes from the sum. They are drawn from their
            # baked props, and that is where their width is — a marked item is
            # built as ``row[marker | content]``, so counting the marker cell is
            # what reserves the gutter rather than letting the content have it.
            if rp.get("list_marker") is not None or rp.get("separator") is not None:
                return (
                    _leaf_natural_width(
                        node_index.get(cell.content_id), avail, fonts, _t, rp
                    )
                    + pad.x
                )
            nd = node_index.get(cell.content_id) if cell.content_id else None
            chart = rp.get("chart")
            if chart is not None:
                # A chart is a filler by WIDTH — it spans whatever column it is
                # handed — but not by shape. A multi-row chart draws vertical
                # bars only while every row has a slot of its own, and turns on
                # its side below that. A stacked section should wrap to the next
                # row before its chart turns, so the flip point is its ask. A
                # chart that is horizontal at every width has nothing to protect
                # and falls through to the floor below.
                flip = _chart_vertical_min_width(chart, fonts, _t)
                if flip is not None:
                    return flip + pad.x
            # The length CATEGORY is the floor: it is how narrow an element may
            # be compressed before it is allowed to collapse internally. The
            # longest text box is the honest ask, the category is the boundary,
            # and a cell is worth the larger of the two -- which is also what the
            # arrangements themselves size by, so a grid measured this way does
            # not shed a column at the width this reports.
            floor = LEAF_WIDTH.get((nd or {}).get("content_length_category") or "", 0.0)
            one_line = _stacked_text_width(nd, fonts, _t, rp)
            if one_line is not None:
                return max(one_line, floor) + pad.x
            return (
                max(_table_cell_min_width(cell, node_index, fonts, _t, avail), floor)
                + pad.x
            )
        inner = max(0.0, avail - pad.x)
        if cell.type == "row":
            total = sum(width(c, inner, inner_levels, inner_owner) for c in kids)
            total += sum(
                _sibling_gap(
                    kids[i - 1], kids[i], _t, "row", inner_owner, node_index, cell
                )[0]
                for i in range(1, len(kids))
            )
        else:
            total = max(
                (width(c, inner, inner_levels, inner_owner) for c in kids),
                default=0.0,
            )
        return total + pad.x

    return width


def make_width_measurer(fonts: FontSet, theme: Theme | None):
    """Minimum-unbreakable-width closure for
    ``LayoutGenerator.generate(measure_width=...)``.

    Returns the narrowest width an AST leaf can render at without clipping:
    pills (link / inline_code) never wrap, so it is their *uncapped*
    single-line width (same measurement as ``_leaf_natural_width`` /
    ``draw_link_box``); text-ish leaves wrap by unit, so it is the widest
    unit the wrap keeps whole (a word with its attached punctuation), at the
    leaf's effective font (same resolution the wrap/draw path uses); images / rules return ``None`` (no text constraint). The
    generator floors its min-width fit decisions at the subtree max of this,
    so a row/grid cell is never narrower than its longest button or word.
    """
    _t = theme or Theme()

    def measure_width(node, kv_role: str | None = None) -> float | None:
        if node.type in ("image", *_BREAK_LEAVES):
            return None
        if node.type == "code_block":
            return _code_block_width(node.content, node.code_language, fonts, _t)
        # The generator owns the K-V role (`kv_role_map`), so a leaf is measured
        # at the same `Key` / `Value` font the renderer will draw it in.
        rp = {"kv_role": kv_role} if kv_role else None
        if node.type == "drawing_element":
            return drawing_element_min_width(node.drawing_element, _t)
        if node.type in ("link", "inline_code", "emoji"):
            nd = {
                "type": node.type,
                "content": node.content,
                "link_variant": node.link_variant,
                "link_label": node.link_label,
                "link_is_emoji": node.link_is_emoji,
                "link_disabled": node.link_disabled,
                "emoji_kind": getattr(node, "emoji_kind", None),
                "emoji_index": getattr(node, "emoji_index", 0),
                # These four are read by the DRAW path and were missing here, so
                # the generator sized a leaf one way and the renderer drew it
                # another: code_variant picks the chip's size/padding
                # (_leaf_natural_width), emoji_variant the badge's icon_size
                # (_emoji_leaf_size), and in_key / table_role the peeled glyph's
                # font size (_text_emoji_px).
                "code_variant": getattr(node, "code_variant", None),
                "emoji_variant": getattr(node, "emoji_variant", None),
                "in_key": getattr(node, "in_key", False),
                "table_role": getattr(node, "table_role", None),
                "text_style_chain": list(getattr(node, "text_style_chain", ()) or ()),
            }
            return _leaf_natural_width(nd, float("inf"), fonts, _t, rp)
        content = node.content or ""
        if not content:
            return None
        atx_level, atx_text = getattr(node, "atx_level", 0), content
        eff_fonts, size = _effective_text_fonts(
            node.type,
            atx_level,
            fonts,
            _t,
            node=node,
        )
        # A `Key` / `Value` leaf draws at that block's font, so its
        # unbreakable (widest-word) minimum must be measured there too — else the
        # generator provisions it at the base width and the box clips.
        eff_fonts, size, _ = _apply_kv_role(
            rp,
            eff_fonts,
            size,
            0,
            _t,
            fonts,
            node=node,
        )
        return _widest_unit(_explode_words(atx_text), eff_fonts, size) or None

    return measure_width


def make_line_width_measurer(fonts: FontSet, theme: Theme | None):
    """Full-single-line-width closure for
    ``LayoutGenerator.generate(measure_line=...)``.

    Returns the *uncapped* width a leaf occupies rendered on one line — the
    same measurement ``_leaf_natural_width`` collapses to (pills at pill
    width; text/segment/emoji/bullet_point/datapoint via the text path with
    emoji-aware word advances) — and ``None`` for images/rules. The
    generator's line-split flow uses it to batch one source line's pieces
    back into rows as if they were never split.

    Measured at the leaf's *effective* font, heading lines AND authored tiers
    included: a piece split off a heading keeps that heading's size
    (``heading_ctx``), and a ``_x_`` / ``__x__`` / ``___x___`` piece keeps its
    tier's size (``text_style``), so the flow batches each against what it
    really draws. Measuring it as body text packs a row that cannot fit, and the
    row then falls back to ratio widths in ``_layout_row``, and the text clips
    mid-word.
    """
    _t = theme or Theme()
    # A generate asks about the same leaves again at every trial build that flows
    # them. Keyed on every field the answer is measured from, so a leaf edited between
    # two asks is measured afresh; the fonts and the theme are this closure's own.
    memo: dict[tuple, float | None] = {}

    def measure_line(node, kv_role: str | None = None) -> float | None:
        if node.type in ("image", *_BREAK_LEAVES):
            return None
        if node.type == "code_block":
            return _code_block_width(node.content, node.code_language, fonts, _t)
        # The generator owns the K-V role (`kv_role_map`), so a leaf is measured
        # at the same `Key` / `Value` font the renderer will draw it in.
        rp = {"kv_role": kv_role} if kv_role else None
        nd = {
            "type": node.type,
            "content": node.content,
            "link_variant": node.link_variant,
            "link_label": node.link_label,
            "link_is_emoji": node.link_is_emoji,
            "link_disabled": node.link_disabled,
            "emoji_kind": getattr(node, "emoji_kind", None),
            "emoji_index": getattr(node, "emoji_index", 0),
            "heading_ctx": getattr(node, "heading_ctx", 0),
            # The authored tier and the section's text style, like heading_ctx
            # above: _leaf_natural_width resolves both, so leaving either out
            # measured a Display/Lead/Muted piece, or one in a section, at body size.
            "text_style": getattr(node, "text_style", None),
            "text_style_chain": tuple(getattr(node, "text_style_chain", ()) or ()),
            # See make_width_measurer: all four are read by the draw path.
            "code_variant": getattr(node, "code_variant", None),
            "emoji_variant": getattr(node, "emoji_variant", None),
            "in_key": getattr(node, "in_key", False),
            "table_role": getattr(node, "table_role", None),
            # The kind (slider or task control) picks the drawn size; without
            # it a slider was measured as a checkbox and overflowed its row.
            "drawing_element": node.drawing_element,
        }
        if node.drawing_element is not None:  # a dict, so no key; and rare
            return _leaf_natural_width(nd, float("inf"), fonts, _t, rp)
        key = (*nd.values(), kv_role)
        if key not in memo:
            memo[key] = _leaf_natural_width(nd, float("inf"), fonts, _t, rp)
        return memo[key]

    return measure_line


def make_marker_measurer(fonts: FontSet, theme: Theme | None):
    """Gutter-marker glyph-width closure for
    ``LayoutGenerator.generate(measure_marker=...)``.

    Takes the marker props the generator just baked and returns the width its
    glyphs actually occupy — the *same* measurement ``_draw_list_marker`` draws
    with. Without it the generator has to stand in the marker's em size for a
    numbered ordinal (64px for a "1" that draws 27.6px wide, but only 96px for
    a "10" that draws 100.8px), and its gutter budget disagrees with what the
    renderer reserves. Shapes and the quote bar carry their true width in
    ``size`` already.
    """
    _t = theme or Theme()

    def measure_marker(props: dict) -> float:
        if not _is_text_marker(props):
            return float(props.get("size", 0.0))
        font, _size = _marker_font(props, fonts, _t)
        return _text_ink(props.get("text") or "", font)[2]

    return measure_marker


# ---------------------------------------------------------------------------
# Content-fitted width measurement (horizontal collapse)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Content-fitted box placement
# ---------------------------------------------------------------------------


def _rrect(rect: "skia.Rect", radii) -> "skia.RRect":
    """A rounded rect with per-corner radii ``(TL, TR, BR, BL)``.

    ``RRect.MakeRectRadii`` does not exist in this binding, so build it with
    ``setRectRadii``; skia clamps radii that would exceed the rect itself.
    """
    tl, tr, br, bl = radii
    rr = skia.RRect()
    rr.setRectRadii(
        rect,
        [
            skia.Point(tl, tl),
            skia.Point(tr, tr),
            skia.Point(br, br),
            skia.Point(bl, bl),
        ],
    )
    return rr


# ---------------------------------------------------------------------------
# Box drawing
# ---------------------------------------------------------------------------


def draw_image_box(
    canvas: skia.Canvas,
    box: LayoutBox,
    content: str,
    font: skia.Font,
    img: Picture | None = None,
    render_properties: dict | None = None,
    theme: Theme | None = None,
    contain: bool = False,
    stand_in: Painter | None = None,
) -> None:
    """Draw a fetched image with cover-fit clipping, or a placeholder.

    Honors the render hints: ``max_width`` caps the drawn width (the
    leftover is positioned by ``content_align``, default left), and
    ``shape: circle`` draws a 1:1 square region clipped to a circle.

    ``contain`` fits the WHOLE image inside the box instead of cover-cropping it,
    and is the caller's kind-based DEFAULT: it is passed for SVGs. A photograph is
    a texture — cropping it to fill the frame is the intent — but a vector is a
    drawing with meaningful bounds, and a square icon in the width-conditioned
    default box (3:2 below 768px) loses a third of its height to a crop that has
    no business being there.

    An explicit ``fit`` render hint (``contain`` / ``cover``, authored as
    ``?md2ui.fit=``) overrides that default either way — a
    logo photograph that must not be cropped, or a vector texture meant to bleed.
    """
    rp = render_properties or {}
    _theme = theme or Theme()
    is_circle = rp.get("shape") == "circle"
    fit = rp.get("fit")
    if fit in ("contain", "cover") or img is NO_PICTURE:
        contain = fit == "contain" and img is not NO_PICTURE

    # Content rect: image fills the box width unless capped by max_width.
    content_w = _image_content_width(rp, box.width)
    if is_circle:
        # Force a square so the circle is never an oval.
        side = min(content_w, box.height)
        cw = ch = side
    else:
        cw = content_w
        ch = box.height
    if cw <= 0 or ch <= 0:
        return  # nothing to show, and the cover scale below would be 0

    # Horizontal alignment of the (capped) image within the box; default left.
    align = rp.get("content_align") or _theme.root.align or "left"
    slack = max(0.0, box.width - cw)
    if align == "center":
        ox = slack / 2
    elif align == "right":
        ox = slack
    else:
        ox = 0.0
    cx = box.x + ox
    cy = box.y + max(0.0, (box.height - ch) / 2)
    dst = skia.Rect.MakeXYWH(cx, cy, cw, ch)

    if img is not None:
        iw, ih = img.width(), img.height()
        if iw > 0 and ih > 0:
            if contain:
                # Whole image, letterboxed: the source is never sub-rected, so
                # nothing is ever cropped. Only the DRAWN rect shrinks to fit;
                # ``dst`` stays the region the layout reserved, so the clip (and
                # a circle's oval) keeps the box's shape rather than collapsing
                # onto the image's own bounds.
                fit = min(cw / iw, ch / ih)
                dw, dh = iw * fit, ih * fit
                src = skia.Rect.MakeWH(iw, ih)
                draw_dst = skia.Rect.MakeXYWH(
                    cx + (cw - dw) / 2, cy + (ch - dh) / 2, dw, dh
                )
            else:
                scale = max(cw / iw, ch / ih)
                src_w = cw / scale
                src_h = ch / scale
                src = skia.Rect.MakeXYWH(
                    (iw - src_w) / 2, (ih - src_h) / 2, src_w, src_h
                )
                draw_dst = dst
            canvas.save()
            radii = rp.get("corner_radii")
            if is_circle:
                path = skia.Path()
                path.addOval(dst)
                canvas.clipPath(path, skia.ClipOp.kIntersect, True)
            elif radii and any(radii):
                # Per-corner, because a bleeding image shares only SOME corners
                # with its card: a top image rounds its top pair to the card's
                # radius and keeps the bottom pair square, where content
                # continues below.
                canvas.clipRRect(_rrect(dst, radii), doAntiAlias=True)
            else:
                canvas.clipRect(dst)
            if stand_in is not None:  # a named placeholder, in the picture's clip
                stand_in(canvas, dst)
            else:
                draw_picture(canvas, img, src, draw_dst)
            canvas.restore()
            return

    # Placeholder: circle outline (circular images) or diagonal cross + alt label
    deco = skia.Paint(
        Color=IMAGE_DECO_COLOR,
        Style=skia.Paint.kStroke_Style,
        StrokeWidth=1.0,
        AntiAlias=True,
    )
    if is_circle:
        canvas.drawOval(dst, deco)
    else:
        canvas.drawLine(dst.left(), dst.top(), dst.right(), dst.bottom(), deco)
        canvas.drawLine(dst.right(), dst.top(), dst.left(), dst.bottom(), deco)

    label = image_alt(content)
    if label and dst.width() > 40 and dst.height() > 20:
        text_w = font.measureText(label)
        canvas.drawString(
            label,
            dst.left() + (dst.width() - text_w) / 2,
            dst.top() + dst.height() / 2 + font.getSize() / 2,
            font,
            skia.Paint(Color=IMAGE_DECO_COLOR, AntiAlias=True),
        )


def draw_horizontal_rule(
    canvas: skia.Canvas,
    box: LayoutBox,
    theme: Theme | None = None,
    node: dict | None = None,
) -> None:
    _theme = theme or Theme()
    hr = scoped_horizontal_rule_style(_theme, _text_style_scopes(node))
    y = box.y + box.height / 2
    canvas.drawLine(
        box.x,
        y,
        box.x + box.width,
        y,
        skia.Paint(
            Color=_replace_color(hr.stroke_color, box.bg_stack, _theme, "stroke"),
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=hr.stroke_width,
            AntiAlias=True,
        ),
    )


def _draw_row_separator(
    canvas: skia.Canvas,
    box: LayoutBox,
    sep: dict,
    fonts: FontSet,
    theme: "Theme",
) -> None:
    """Draw a row separator cell: the character, or a vertical rule.

    ``rule`` is the vertical twin of :func:`draw_horizontal_rule` — same stroke
    keys, turned 90°, spanning the cell's full height (the cell was stretched to
    the row by ``_is_bar_marker``). ``glyph`` draws the separator character in
    the body text style — and since it IS the body color, it takes the body color's
    replacement too, or a bullet would stay the sheet's color on a card that
    recolored the words
    either side of it.
    """
    if sep.get("kind") == "rule":
        vr = theme.vertical_rule
        x = box.x + box.width / 2
        canvas.drawLine(
            x,
            box.y,
            x,
            box.y + box.height,
            skia.Paint(
                Color=_replace_color(vr.stroke_color, box.bg_stack, theme, "stroke"),
                Style=skia.Paint.kStroke_Style,
                StrokeWidth=vr.stroke_width,
                AntiAlias=True,
            ),
        )
        return
    ch = sep.get("char") or ""
    if not ch:
        return
    size = theme.text.font_size
    canvas.drawString(
        ch,
        box.x,
        box.y + size,
        _span_font(fonts, size, False, False),
        skia.Paint(
            Color=_replace_color(theme.text.color, box.bg_stack, theme),
            AntiAlias=True,
        ),
    )


def _link_pill_rect(
    box: LayoutBox,
    nd: dict,
    fonts: FontSet,
    theme: Theme,
) -> tuple[float, float, float, float]:
    """Where a button's pill is painted: ``(x, y, width, height)``, content space.

    One function, called by ``draw_link_box`` to paint the pill and by
    ``render_actions`` to make it clickable, so a click lands exactly on the ink
    (ADR-400). Plain floats, not a ``skia.Rect``: the drawer places the label
    from these, and a Rect would round them to float32 first.
    """
    _variant, label, is_emoji, style = _resolve_link(nd, theme)
    size = (style.text_style or TextStyle()).font_size
    font, runs, emoji_tf = link_label_fonts(nd, label, fonts, theme, size)
    pill_w, pill_h = _link_pill_size(runs, style, font, size, emoji_tf, is_emoji)
    # Three-way, and resolved through _resolve_h_align so a CASCADED
    # content_align reaches it: a centered section must draw its buttons
    # centered too, not flush left off the ROOT's align.
    _align = _resolve_h_align(box.render_properties, theme)
    if _align == "center":
        pill_x = box.x + (box.width - pill_w) / 2
    elif _align == "right":
        pill_x = box.x + (box.width - pill_w)
    else:
        pill_x = box.x
    return pill_x, box.y + (box.height - pill_h) / 2, pill_w, pill_h


def draw_link_box(
    canvas: skia.Canvas,
    box: LayoutBox,
    nd: dict,
    fonts: FontSet,
    theme: Theme | None = None,
    background_images: dict | None = None,
) -> None:
    """Draw a link as its label text inside a shape-aware pill/badge.

    Every variant (primary, secondary…septenary, text — one per
    markdown wrapping) normally draws as a rounded rect at its configured
    ``corner_radius``; a stadium look just comes from a larger radius, not a
    different shape. Shape is only
    forced when the label is pure emoji: then the box is squared into that
    same variant's ``emoji_shape`` ("circle" draws an oval; "square" forces
    a 1:1 aspect box but keeps drawing a rounded rect at ``corner_radius``,
    per the theme, so it reads as a rounded square rather than a sharp one).
    """
    _theme = theme or Theme()
    _variant, label, is_emoji, style = _resolve_link(nd, _theme)
    style = choice_style(nd, style, _theme)  # a choice option's colours only
    text_style = style.text_style or TextStyle()
    size = text_style.font_size
    font, runs, emoji_tf = link_label_fonts(nd, label, fonts, _theme, size)
    text_w = _label_runs_width(runs, size, emoji_tf)
    metrics = font.getMetrics()
    text_h = metrics.fDescent - metrics.fAscent

    pad = style.padding or PaddingBox()
    pill_x, pill_y, pill_w, pill_h = _link_pill_rect(box, nd, fonts, _theme)
    force_circle = is_emoji and style.emoji_shape == "circle"
    pill_rect = skia.Rect.MakeXYWH(pill_x, pill_y, pill_w, pill_h)
    # Center the (possibly narrower, for a forced-square/circle emoji badge)
    # text box inside the pill rect.
    text_off_x = pill_x + (pill_w - text_w) / 2 if is_emoji else pill_x + pad.left
    text_off_y = pill_y + (pill_h - text_h) / 2
    if VIEW.debug_padding:
        _DEBUG_PAD_RINGS.append(
            (
                pill_rect,
                skia.Rect.MakeXYWH(text_off_x, text_off_y, text_w, text_h),
            )
        )

    disabled = bool(nd.get("link_disabled"))
    ink, label_bg = paint_pill(
        canvas,
        pill_rect,
        style,
        nd,
        nd.get("segment_stack") or box.bg_stack,  # a segment sits on its run
        _theme,
        disabled=disabled,
        oval=force_circle,
        images=background_images,
    )
    text_x = text_off_x
    text_y = text_off_y - metrics.fAscent
    text_paint = skia.Paint(Color=ink, AntiAlias=True)
    # The label's emoji take its ink, so they follow the variant (and the
    # disabled state); only a `## Fixed colors` pin on the glyph outranks it.
    pins = {} if disabled else _theme.emojis.link.fixed_colors
    for run, run_font in runs:
        text_x += _draw_text_with_emoji(
            canvas,
            run,
            text_x,
            text_y,
            run_font,
            emoji_tf,
            size,
            text_paint,
            fixed_colors=pins,
            bg_stack=label_bg,
            theme=_theme,
        )


def _rotated_code_style(
    code: "InlineCodeTheme", nd: dict | None, theme: "Theme"
) -> "InlineCodeTheme":
    """*code* with this chip's slot picked out of its color lists.

    The chip twin of ``_rotated_link_style``: colors only, so the pill's size and
    padding are identical whether or not the theme rotates. Returns *code*
    untouched when nothing was listed more than once.
    """
    if nd is None:
        return code
    ts = code.text_style
    if not (code.fill_colors or code.stroke_colors or (ts is not None and ts.colors)):
        return code
    idx, chain = _rotation_slot(nd, theme)
    if ts is not None and ts.colors:
        ts = dataclasses.replace(
            ts,
            color=_rotate_color(ts.colors, ts.color, idx, theme, "chip", chain),
        )
    return dataclasses.replace(
        code,
        fill_color=_rotate_color(
            code.fill_colors, code.fill_color, idx, theme, "chip", chain
        ),
        stroke_color=_rotate_color(
            code.stroke_colors, code.stroke_color, idx, theme, "chip", chain
        ),
        text_style=ts,
    )


def draw_code_box(
    canvas: skia.Canvas,
    box: LayoutBox,
    content: str,
    mono_typeface: skia.Typeface,
    theme: Theme | None = None,
    emoji_tf: skia.Typeface | None = None,
    variant: str | None = None,
    node: dict | None = None,
    background_images: dict | None = None,
) -> None:
    """Draw a whole-leaf ``inline_code`` node as a padded rounded background, like a
    link pill — aligned to ``box.x`` with the text inset, and NOT clipped, so the
    background's per-side padding is never cut off.

    Only used for ``type == "inline_code"`` leaves. Inline code *spans* inside paragraph
    text keep the ``_draw_code_run`` path (clipped to the text box) unchanged.

    *node* is needed only for color rotation (this chip's slot in its section's
    cycle); the geometry never depends on it.
    """
    _theme = theme or Theme()
    code = _rotated_code_style(_theme.inline_code.resolved(variant, node), node, _theme)
    label = content.strip().strip("`")
    # Inline code renders in its own text style (body font at a fixed 14 by default).
    _ic = code.effective_text_style(_theme.text)
    font, ic_size = _code_font(_theme, variant, mono_typeface)
    # Resolved before painting, for the same reason a button's is: the chip's
    # own fill — the REPLACED one — leads the stack for its own label.
    _pins = painted_pins(node or {}, code)
    chip_fill = _pin_or_replace(
        code.fill_color, _pins.get("fixed_fill"), box.bg_stack, _theme, "fill"
    )
    chip_stroke = _pin_or_replace(
        code.stroke_color,
        _pins.get("fixed_stroke"),
        box.bg_stack,
        _theme,
        "stroke",
    )
    chip_bg = _push_bg(
        box.bg_stack,
        BG_IMAGE if code.bg_image else _opaque_or_none(chip_fill),
    )
    ic_color = _pin_or_replace(_ic.color, _pins.get("fixed_text"), chip_bg, _theme)
    inline_es = _theme.emojis.inline
    # Emoji-aware width: emojis draw with the (wider) emoji font, so the pill
    # background must reserve that advance, not mono's, or the text overflows.
    text_w = _link_label_width(label, font, ic_size, emoji_tf)
    metrics = font.getMetrics()
    text_h = metrics.fDescent - metrics.fAscent

    pad = code.padding
    bg_w, bg_h, corner_radius, l_pad, r_pad = _chip_metrics(code, text_w, text_h)

    # Three-way, and resolved through _resolve_h_align so a CASCADED
    # content_align reaches it: a centered section must draw its chips
    # centered too, not flush left off the ROOT's align.
    _align = _resolve_h_align(box.render_properties, _theme)
    if _align == "center":
        bg_x = box.x + (box.width - bg_w) / 2
    elif _align == "right":
        bg_x = box.x + (box.width - bg_w)
    else:
        bg_x = box.x
    bg_y = box.y + (box.height - bg_h) / 2

    bg_rect = skia.Rect.MakeXYWH(bg_x, bg_y, bg_w, bg_h)
    if VIEW.debug_padding:
        _DEBUG_PAD_RINGS.append(
            (
                bg_rect,
                skia.Rect.MakeXYWH(bg_x + l_pad, bg_y + pad.top, text_w, text_h),
            )
        )
    _paint_layered_fill(
        canvas,
        bg_rect,
        bg_color=_opaque_or_none(chip_fill),
        image=element_picture(background_images, code.bg_image, code.muted),
        gradient=_replaced_gradient(code.gradient, box.bg_stack, _theme),
        corner_radius=corner_radius,
        shadows=code.shadows,
        direct_solid=True,
    )
    if code.stroke_width > 0:
        draw_stroke(
            canvas,
            bg_rect,
            corner_radius,
            skia.Paint(
                Color=chip_stroke,
                Style=skia.Paint.kStroke_Style,
                StrokeWidth=code.stroke_width,
                AntiAlias=True,
            ),
            code.stroke_align,
        )

    _draw_text_with_emoji(
        canvas,
        label,
        bg_x + l_pad,
        bg_y + pad.top - metrics.fAscent,
        font,
        emoji_tf,
        ic_size,
        skia.Paint(Color=ic_color, AntiAlias=True),
        emoji_color=(
            _replace_color(inline_es.color, chip_bg, _theme)
            if inline_es.color is not None
            else None
        ),
        fixed_colors=inline_es.fixed_colors,
        bg_stack=chip_bg,
        theme=_theme,
    )


def _pin_only_emoji_style(theme: "Theme") -> "EmojiTextStyle | None":
    """The `## Fixed colors` emoji pins, carried WITHOUT any styling.

    Headings and bullets deliberately keep the default emoji font and the
    surrounding text colour (see ``draw_styled_text_box``), and that stays true
    — a pin is not styling. It is an explicit per-glyph statement of meaning
    (❤️ red, ☀️ amber), which is why ``stamp_fixed_colors`` lets it outrank both
    rotation and replacement; a glyph that reads as itself in a paragraph must
    read as itself in the heading above it too.

    An ``EmojiTextStyle`` with only ``fixed_colors`` set expresses exactly that:
    ``font_path=None`` falls back to the default emoji font and ``color=None``
    keeps the text colour, so nothing but the pinned glyphs changes. Returns
    ``None`` when the theme pins nothing, so the caller keeps its plain path.
    """
    pins = theme.emojis.text.fixed_colors
    return EmojiTextStyle(fixed_colors=pins) if pins else None


def draw_styled_text_box(
    canvas: skia.Canvas,
    box: LayoutBox,
    content: str,
    fonts: FontSet,
    size: float,
    color: int,
    theme: Theme | None = None,
    text_align: str | None = None,
    emoji_style: "EmojiTextStyle | None" = None,
    marker: "TextStyle | None" = None,
    fixed: "int | None" = None,
    fixed_spans: "list[dict] | None" = None,
    styled: bool = False,
) -> None:
    """Draw word-wrapped styled text inside a box, clipped to its bounds.

    ``fixed`` is a ``## Fixed colors`` pin for this leaf (``node["fixed_text"]``,
    resolved once by ``stamp_fixed_colors``). It outranks replacement, so the
    caller passes it rather than pre-applying it — the precedence lives in
    ``_pin_or_replace``, in one place.

    The box hugs its content (no inner padding). ``text_align`` (Skia SkTextAlign
    — left/center/right) overrides the global ``theme.root.align`` for this box
    when provided. Wrapping and measurement go through the shared
    ``_wrap_lines``/``_line_width`` helpers, so the box reserved by
    ``_leaf_height``/``_leaf_natural_width`` exactly fits what is drawn here.

    ``emoji_style`` (the Text block) restyles unsliced emojis inside this text —
    a filled font, a color override and per-glyph Fixed colors. Passed only for
    plain prose; headings/bullets keep the default emoji font + text color.
    ``styled`` says a style beyond body Text set ``color``: the glyph follows it.

    ``marker`` is the TextStyle whose ``Marker …`` keys paint inline ``code``
    spans in this box (``_marker_style``); ``None`` — or a style that sets
    neither key — leaves those spans looking like the text around them.
    """
    _theme = theme or Theme()
    words = _explode_words(content)
    if not words:
        return
    if fixed_spans:
        words = project_paint_spans(content, words, fixed_spans)

    inner_w = box.width
    inner_x = box.x
    baseline_y = box.y + size
    line_h = size * LINE_SCALE

    def _span_f(bold: bool, italic: bool) -> skia.Font:
        return _span_font(fonts, size, bold, italic)

    lines = _wrap_lines(words, inner_w, fonts, size)

    align = text_align or _theme.root.align or "left"
    line_starts: list[float] = []
    for ln in lines:
        if align == "center":
            line_starts.append(inner_x + (inner_w - _line_width(ln, fonts, size)) / 2)
        elif align == "right":
            line_starts.append(inner_x + (inner_w - _line_width(ln, fonts, size)))
        else:
            line_starts.append(inner_x)

    # ## Text Color Replacements: every color this box paints is swapped against
    # what is actually behind the box, so a rotated card that landed on a dark
    # fill gets legible text without the style knowing which card it is on.
    # Applied to the resolved colors, so it is the last word.
    _bg = box.bg_stack
    color = _pin_or_replace(color, fixed, _bg, _theme)
    text_paint = skia.Paint(Color=color, AntiAlias=True)

    # The face, tint and pins for an emoji sitting in this text. ``### Text``'s
    # ``Color`` is a default the surrounding style outranks — _prose_emoji_paint.
    _e_font, _e_color, _e_fixed = _prose_emoji_paint(
        emoji_style, styled or fixed is not None, fonts, _bg, _theme
    )
    # Inline links (### Inline under ## Links) are a paint-only span style: same
    # font and size as this box's text, only recolored — an unset Text color
    # keeps the surrounding color — and optionally underlined.
    inline_link = _theme.links.inline
    link_color = (
        _replace_color(inline_link.text_color, _bg, _theme)
        if inline_link.text_color is not None
        else color
    )
    link_paint = (
        text_paint
        if link_color == color
        else skia.Paint(Color=link_color, AntiAlias=True)
    )

    # Markers: an inline `code` span that stayed inside this text. It keeps this
    # box's font and size (see _span_font) — only these two paints differ, and
    # both unset means the span draws as ordinary text.
    marker_bg = marker.marker_bg_color if marker is not None else None
    marker_color = marker.marker_text_color if marker is not None else None
    if marker_bg is not None:
        # The marker's flat background is a fill like any pill's, and is
        # replaced before it becomes the background its own text sits on.
        marker_bg = _replace_color(marker_bg, _bg, _theme, "fill")
    if marker_color is not None:
        # A marker paints its own flat background, so its text sits on that
        # when there is one and on the box's background when there is not.
        marker_color = _replace_color(
            marker_color, _push_bg(_bg, _opaque_or_none(marker_bg)), _theme
        )
    marker_paint = (
        skia.Paint(Color=marker_color, AntiAlias=True)
        if marker_color is not None
        else text_paint
    )
    span_metrics = make_font(fonts.typeface, size).getMetrics()
    marker_top = span_metrics.fAscent
    marker_height = span_metrics.fDescent - span_metrics.fAscent

    def _draw_marker_run(rs: float, re: float, y: float) -> None:
        """Flat background behind one contiguous marker run — no corner radius,
        no padding: the run's advance by the line's ascent→descent."""
        canvas.drawRect(
            skia.Rect.MakeXYWH(rs, y + marker_top, re - rs, marker_height),
            skia.Paint(Color=marker_bg, Style=skia.Paint.kFill_Style, AntiAlias=True),
        )

    # A line ending in a synthesised slant leans past its advance: the clip makes
    # room for that ink (font_loader.styled_font); the box is never widened.
    slant = [-_span_f(ln[-1][1], ln[-1][2]).getSkewX() for ln in lines if ln]
    room = size * max(slant, default=0.0)
    canvas.save()
    canvas.clipRect(skia.Rect.MakeXYWH(box.x, box.y, box.width + room, box.height))
    for line_i, line in enumerate(lines):
        y = baseline_y + line_i * line_h

        # Pass 1 — one background per marker on this line: the spaces inside a
        # multi-word marker are covered, the space BETWEEN two markers is not.
        if marker_bg is not None:
            for run_x0, run_x1, _ in _flag_runs(
                line, _FLAG_CODE, line_starts[line_i], fonts, size
            ):
                _draw_marker_run(run_x0, run_x1, y)

        # Pass 2 — draw the text words on top of the marker backgrounds
        x = line_starts[line_i]
        for word_i, w in enumerate(line):
            word, bold, italic, code, strike, link = w[:6]
            font = _span_f(bold, italic)
            # Only where a space was WRITTEN: punctuation after a span has none,
            # and adding one here drew `Open **Settings**.` as `Open Settings .`
            # (_exploded). Must stay in step with _line_width and _flag_runs —
            # measurement and painting share one normalization point (ADR-400).
            if word_i > 0 and w[6]:
                x += font.measureText(" ")
            word_w = _measure_word(word, bold, italic, fonts, size)
            if link:
                word_paint = link_paint
            elif code:
                word_paint = marker_paint
            else:
                word_paint = text_paint
            _draw_text_with_emoji(
                canvas,
                word,
                x,
                y,
                font,
                _e_font,
                size,
                word_paint,
                emoji_color=_e_color,
                fixed_colors=_e_fixed,
                fixed_spans=w[7] if len(w) > 7 else (),
                bg_stack=_bg,
                theme=_theme,
            )
            x += word_w

        # Pass 3 — one underline per inline link on this line (### Inline), so
        # `[two words](/x)` reads as one link: it breaks only where another link
        # starts (the link slot is a region id) and at the line's end.
        if inline_link.underline:
            under_y = y + size * 0.12
            for run_x0, run_x1, _ in _flag_runs(
                line, _FLAG_LINK, line_starts[line_i], fonts, size
            ):
                canvas.drawLine(
                    run_x0,
                    under_y,
                    run_x1,
                    under_y,
                    skia.Paint(Color=link_color, StrokeWidth=1.0, AntiAlias=True),
                )

        # Pass 4 — one rule per contiguous struck run, drawn over the text so
        # `~~two words~~` reads as a single strikethrough rather than one
        # segment per word with a gap at every space. The run takes its first
        # word's color, so a struck marker or link keeps its own paint.
        for run_x0, run_x1, first_i in _flag_runs(
            line, _FLAG_STRIKE, line_starts[line_i], fonts, size
        ):
            # By INDEX, not by unpacking: `_exploded` appended a 7th field
            # (`space_before`) and says so — "the first six are read by INDEX
            # downstream, so it can only be appended". This was the one site
            # still unpacking, and a 7-tuple into six names raised ValueError
            # for every document holding a `~~struck~~` region.
            first_word = line[first_i]
            r_code = first_word[_FLAG_CODE]
            r_link = first_word[_FLAG_LINK]
            if r_link:
                run_color = link_color
            elif r_code and marker_color is not None:
                run_color = marker_color
            else:
                run_color = color
            mid_y = y - size * 0.35
            canvas.drawLine(
                run_x0,
                mid_y,
                run_x1,
                mid_y,
                skia.Paint(Color=run_color, StrokeWidth=1.0, AntiAlias=True),
            )
    canvas.restore()


def draw_emoji_box(
    canvas: skia.Canvas,
    box: LayoutBox,
    node: dict,
    fonts: "FontSet",
    theme: "Theme",
    background_images: dict | None = None,
) -> None:
    """Draw an EMOJI leaf by its ``emoji_kind`` (set once by the grouper).

    ``heading``/``alone`` → the Primary badge (icon size, per-sibling-cycled
    icon color, padding, background fill, forced circle/square). ``alone`` is
    any emoji the element pass peeled — the author separated it, so it is an
    element, the same way a separated backtick span is a chip. ``text`` → the
    Text block: a bare glyph at the surrounding text size, for an emoji whose
    CONTAINER styles it as text (a K-V key, a table cell), tinted by the Text
    color / Fixed-colors override."""
    content = node.get("content", "")
    kind = node.get("emoji_kind")
    emoji_tf = fonts.emoji

    if kind == "text":
        style = theme.emojis.text
        e_tf = _load_emoji_typeface(style.font_path, emoji_tf)
        size = _text_emoji_px(node, theme)
        font = _emoji_glyph_font(e_tf, fonts.typeface, size)
        glyph_w = glyph_advance(content, e_tf, fonts.typeface, size)
        m = font.getMetrics()
        glyph_h = m.fDescent - m.fAscent
        _align = _resolve_h_align(box.render_properties, theme)
        if _align == "center":
            gx = box.x + (box.width - glyph_w) / 2
        elif _align == "right":
            gx = box.x + (box.width - glyph_w)
        else:
            gx = box.x
        gy = box.y + (box.height - glyph_h) / 2 - m.fAscent
        # A key-peeled emoji takes its key's color; a
        # per-glyph Fixed color still wins below.
        if node.get("in_key"):
            color = scoped_text_style(theme, "key", _text_style_scopes(node)).color
        else:
            color = (
                style.color
                if style.color is not None
                else scoped_text_style(theme, "text", _text_style_scopes(node)).color
            )
        # A peeled glyph reads as inline text, so it takes the same treatment
        # the text around it would — but a `## Fixed colors` pin outranks it.
        color = _pin_or_replace(color, node.get("fixed_text"), box.bg_stack, theme)
        if style.fixed_colors:
            rx = gx
            for cl in _emoji_clusters(content):
                col = emoji_pin(style.fixed_colors, cl, color)
                paint = skia.Paint(Color=col, AntiAlias=True)
                rx += draw_glyph_runs(
                    canvas, cl, rx, gy, e_tf, fonts.typeface, size, paint
                )
        else:
            paint = skia.Paint(Color=color, AntiAlias=True)
            draw_glyph_runs(canvas, content, gx, gy, e_tf, fonts.typeface, size, paint)
        return

    # heading / alone → the badge, in whatever variant its wrapper picked
    style, emoji_tf = fonts.emoji_badge(node, theme, theme.text.color)
    fill = style.fill
    size = style.icon_size
    font = _emoji_glyph_font(emoji_tf, fonts.typeface, size)
    glyph_w = glyph_advance(content, emoji_tf, fonts.typeface, size)
    m = font.getMetrics()
    glyph_h = m.fDescent - m.fAscent
    box_w, box_h = _emoji_badge_size(content, style, emoji_tf, fonts.typeface)

    # Resolved, not root-only: a badge inside a centered section centers too.
    _align = _resolve_h_align(box.render_properties, theme)
    if _align == "center":
        bx = box.x + (box.width - box_w) / 2
    elif _align == "right":
        bx = box.x + (box.width - box_w)
    else:
        bx = box.x
    by = box.y + (box.height - box_h) / 2
    rect = skia.Rect.MakeXYWH(bx, by, box_w, box_h)

    # Badge fill, border and glyph all read the SAME slot, so a theme that lists
    # a tinted background and a matching saturated icon color gets the two in
    # lockstep with no second mechanism.
    _rot_i, _rot_chain = _rotation_slot(node, theme)
    bg_color = None
    if fill.is_active():
        bg_color = _pin_or_replace(
            _rotate_color(fill.bg_colors, None, _rot_i, theme, "emoji", _rot_chain)
            or 0,
            node.get("fixed_fill"),
            box.bg_stack,
            theme,
            "fill",
        )
        is_circle = style.shape == "circle"
        # The oval clip moved INTO the shared fill: an outer shadow paints
        # beyond the badge, so a clip wrapped around the call would erase it.
        _paint_layered_fill(
            canvas,
            rect,
            bg_color=bg_color,
            image=element_picture(background_images, fill.bg_image, style.is_muted),
            gradient=_replaced_gradient(fill.gradient, box.bg_stack, theme),
            corner_radius=0.0 if is_circle else fill.corner_radius,
            shadows=fill.shadows,
            oval=is_circle,
        )
        stroke_color = _rotate_color(
            fill.stroke_colors, fill.stroke_color, _rot_i, theme, "emoji", _rot_chain
        )
        if stroke_color is not None:
            stroke_color = _replace_color(stroke_color, box.bg_stack, theme, "stroke")
        if fill.stroke_width > 0 and stroke_color is not None:
            stroke_paint = skia.Paint(
                Color=stroke_color,
                Style=skia.Paint.kStroke_Style,
                StrokeWidth=fill.stroke_width,
                AntiAlias=True,
            )
            draw_stroke(
                canvas,
                rect,
                fill.corner_radius,
                stroke_paint,
                fill.stroke_align,
                oval=is_circle,
            )

    color = _rotate_color(
        style.icon_colors, theme.text.color, _rot_i, theme, "emoji", _rot_chain
    )
    if color is None:
        color = theme.text.color
    # The glyph sits on the badge's own fill when there is one — replacement
    # runs after rotation, so it is the last word on a rotated badge too.
    color = _pin_or_replace(
        color,
        node.get("fixed_text"),
        _push_bg(
            box.bg_stack,
            BG_IMAGE if fill.bg_image else _opaque_or_none(bg_color),
        ),
        theme,
    )
    gx = bx + (box_w - glyph_w) / 2
    gy = by + (box_h - glyph_h) / 2 - m.fAscent
    paint = skia.Paint(Color=color, AntiAlias=True)
    draw_glyph_runs(canvas, content, gx, gy, emoji_tf, fonts.typeface, size, paint)


def _draw_list_marker(
    canvas: skia.Canvas,
    box: LayoutBox,
    lm: dict,
    fonts: FontSet,
    theme: Theme,
) -> None:
    """Draw a list/blockquote marker from its baked ``list_marker`` props.

    ``lm`` carries pre-resolved values (incl. skia int colors) — a bullet shape
    (circle/square), a bullet emoji glyph, a numbered ordinal, or a blockquote
    marker (a bar or quote char). Aside shapes center on the first content line,
    number/char glyphs sit ink-top flush with the box top, and an aside quote bar
    spans the full item height. With ``Aside: no`` the marker is above its item;
    a quote bar is horizontal and uses ``Bar length``. ``Space`` is inserted by
    layout between this box and the content.
    """
    kind = lm.get("kind")
    line_h = min(box.height, theme.text.font_size * LINE_SCALE)

    def marker_color(role: str) -> int:
        """Resolve the rotated marker paint against its actual surface."""
        configured = lm.get("color")
        base = theme.text.color if configured is None else configured
        return _replace_color(base, box.bg_stack, theme, role)

    if kind == "bullet" and not lm.get("emoji"):
        size = float(lm.get("size", 0.0))
        top = box.y + max(0.0, (line_h - size) / 2.0)
        rect = skia.Rect.MakeXYWH(box.x, top, size, size)
        color = marker_color("fill")
        paint = skia.Paint(Color=color, Style=skia.Paint.kFill_Style, AntiAlias=True)
        if lm.get("shape") == "square":
            canvas.drawRoundRect(rect, 2.0, 2.0, paint)
        else:
            canvas.drawOval(rect, paint)
        return

    if kind == "bullet" and lm.get("emoji"):
        size = float(lm.get("size", theme.text.font_size))
        paint = skia.Paint(Color=marker_color("text"), AntiAlias=True)
        _draw_text_with_emoji(
            canvas,
            lm["emoji"],
            box.x,
            box.y + size,
            make_font(fonts.typeface, size),
            fonts.emoji,
            size,
            paint,
        )
        return

    if kind == "quote" and lm.get("mode") == "bar":
        if lm.get("aside", True):
            rect = skia.Rect.MakeXYWH(
                box.x, box.y, float(lm.get("bar_width", 0.0)), box.height
            )
        else:
            rect = skia.Rect.MakeXYWH(
                box.x,
                box.y,
                min(float(lm.get("bar_length", 50.0)), box.width),
                float(lm.get("bar_width", 0.0)),
            )
        canvas.drawRect(
            rect,
            skia.Paint(
                Color=marker_color("fill"),
                Style=skia.Paint.kFill_Style,
                AntiAlias=True,
            ),
        )
        return

    # Numbered ordinal, or a quote char — drawn ink-top flush with the box top.
    # The baseline is placed at the glyphs' own top (not box.y + size), so the
    # font's ascent gap doesn't show up as whitespace above the number.
    text = lm.get("text") or ""
    font, size = _marker_font(lm, fonts, theme)
    ink_top, _ink_h, _adv = _text_ink(text, font)
    paint = skia.Paint(Color=marker_color("text"), AntiAlias=True)
    _draw_text_with_emoji(
        canvas, text, box.x, box.y + ink_top, font, fonts.emoji, size, paint
    )


# ---------------------------------------------------------------------------
# Drawn datapoint displays (bars / rings / date chips)
# ---------------------------------------------------------------------------


def _date_chip_text_bg_stack(
    rp: dict | None,
    stack: "tuple[int | str, ...]",
    theme: Theme,
) -> "tuple[int | str, ...]":
    """Background stack for key/day text inside a split date chip.

    The outer chip's replaced fill is already in ``stack``. A split-region
    fill is resolved against it, then becomes the innermost background for the
    existing global text-color cascade, just like a replaced button fill.
    """
    role = (rp or {}).get("date_role")
    dc = theme.datapoints.date_chip
    if not role or dc.fill != "split":
        return stack
    style = dc.key_bg if role == "key" else dc.day_bg
    if not style.bg_colors:
        return stack
    color = _replace_color(style.bg_colors[0], stack, theme, "fill")
    return _push_bg(stack, _opaque_or_none(color))


def _paint_date_chip_background(
    canvas: skia.Canvas, sbox: SectionBox, theme: Theme, strokes: list | None = None
) -> None:
    """Paint a date chip's card background from ``### Dates → chip``: the base
    fill/gradient/stroke, then (when ``Fill: split``) two region fills clipped
    to the chip's rounded rect — key (top corners rounded) over day (bottom
    corners rounded), sharing the outer corners. The split lands at the key/day
    text proportion, the same metrics the col uses to size its two cells."""
    dc = theme.datapoints.date_chip
    base_color = dc.chip.bg_colors[0] if dc.chip.bg_colors else None
    if base_color is not None:
        base_color = _replace_color(base_color, sbox.bg_stack, theme, "fill")
    base_stroke = dc.chip.stroke_color
    if base_stroke is not None:
        base_stroke = _replace_color(base_stroke, sbox.bg_stack, theme, "stroke")
    resolved_chip = dataclasses.replace(
        dc.chip,
        gradient=_replaced_gradient(dc.chip.gradient, sbox.bg_stack, theme),
        stroke_color=base_stroke,
    )
    _paint_section_background(
        canvas, sbox, resolved_chip, None, base_color, strokes=strokes
    )
    if dc.fill != "split" or not (dc.key_bg.bg_colors or dc.day_bg.bg_colors):
        return
    key_ts = _date_chip_text_style(theme, "key")
    day_ts = _date_chip_text_style(theme, "day")
    key_h = key_ts.font_size + dc.key_bg.padding.y
    day_h = day_ts.font_size + dc.day_bg.padding.y
    total = key_h + day_h
    if total <= 0:
        return
    split = sbox.y + sbox.height * (key_h / total)
    r = dc.chip.corner_radius
    left, right = sbox.x, sbox.x + sbox.width
    top, bot = sbox.y, sbox.y + sbox.height
    region_stack = _push_bg(sbox.bg_stack, _opaque_or_none(base_color))
    if dc.key_bg.bg_colors:
        path = skia.Path()
        path.addRoundRect(
            skia.Rect.MakeLTRB(left, top, right, split),
            [r, r, r, r, 0, 0, 0, 0],  # TL, TR rounded; BR, BL square
        )
        canvas.drawPath(
            path,
            skia.Paint(
                Color=_replace_color(
                    dc.key_bg.bg_colors[0], region_stack, theme, "fill"
                ),
                Style=skia.Paint.kFill_Style,
                AntiAlias=True,
            ),
        )
    if dc.day_bg.bg_colors:
        path = skia.Path()
        path.addRoundRect(
            skia.Rect.MakeLTRB(left, split, right, bot),
            [0, 0, 0, 0, r, r, r, r],  # TL, TR square; BR, BL rounded
        )
        canvas.drawPath(
            path,
            skia.Paint(
                Color=_replace_color(
                    dc.day_bg.bg_colors[0], region_stack, theme, "fill"
                ),
                Style=skia.Paint.kFill_Style,
                AntiAlias=True,
            ),
        )


def draw_content_box(
    canvas: skia.Canvas,
    box: LayoutBox,
    node: dict | None,
    fonts: FontSet,
    image_cache: ImageCache,
    theme: Theme | None = None,
    background_images: dict | None = None,
) -> None:
    _theme = theme or Theme()
    rect = skia.Rect.MakeXYWH(box.x, box.y, box.width, box.height)
    if VIEW.wireframe:
        _nid = node.get("node_id", "") if node is not None else ""
        _level = _nid.count(".") + 1 if _nid else 0
        fill_color, stroke_color = WIREFRAME_PALETTE[_level % len(WIREFRAME_PALETTE)]
        canvas.drawRect(
            rect,
            skia.Paint(Color=fill_color, Style=skia.Paint.kFill_Style, AntiAlias=True),
        )
        canvas.drawRect(
            rect,
            skia.Paint(
                Color=stroke_color,
                Style=skia.Paint.kStroke_Style,
                StrokeWidth=1.0,
                AntiAlias=True,
            ),
        )
        if box.content_id:
            wf_size = 9.0
            wf_font = make_font(fonts.typeface, wf_size)
            wf_metrics = wf_font.getMetrics()
            canvas.drawString(
                box.content_id,
                box.x + 3,
                box.y + 3 - wf_metrics.fAscent,
                wf_font,
                skia.Paint(Color=stroke_color, AntiAlias=True),
            )

    # Gutter marker leaf: a synthetic box with no markdown node, drawn from its
    # baked ``list_marker`` render props. Must run before the ``node is None``
    # bail below (a marker box has no node).
    lm = (box.render_properties or {}).get("list_marker")
    if lm is not None:
        _draw_list_marker(canvas, box, lm, fonts, _theme)
        return

    # Drawn row separator: another synthetic box with no markdown node — the
    # ` - ` / ` • ` / ` | ` the split ate, put back by the generator when
    # ## Separators asks for it.
    sep = (box.render_properties or {}).get("separator")
    if sep is not None:
        _draw_row_separator(canvas, box, sep, fonts, _theme)
        return

    # Stacking-cards key label: a synthetic box with no markdown node, drawn
    # from the header cell text baked into its render props (## Tables →
    # ### Card Keys style). Must also run before the ``node is None`` bail.
    tk = (box.render_properties or {}).get("table_key")
    if tk is not None:
        key_fonts, key_size, key_color = _table_key_fonts(fonts, _theme)
        draw_styled_text_box(
            canvas,
            box,
            tk.get("text", ""),
            key_fonts,
            key_size,
            key_color,
            _theme,
            "left",
        )
        return

    # Drawn datapoint displays: the box replaces its node's text rendering
    # entirely (bar/ring boxes may or may not carry a markdown node, so these
    # run before the ``node is None`` bail too).
    _rp0 = box.render_properties or {}
    if _rp0.get("date_role") is not None:
        box = dataclasses.replace(
            box,
            bg_stack=_date_chip_text_bg_stack(_rp0, box.bg_stack, _theme),
        )
    dpb = _rp0.get("datapoint_bar")
    if dpb is not None:
        _draw_datapoint_bar(canvas, box, dpb, fonts, _theme)
        return
    # Ring value/unit: a baked-text leaf (no markdown node) centered inside the
    # ring, drawn with the ### Ring value/unit style, as render_ring_text laid it
    # out: the value scaled to fit, the label wrapped to the clear inside.
    if _rp0.get("ring_role") is not None:
        rt = ring_text(_rp0, fonts, _theme)
        draw_styled_text_box(
            canvas, box, rt.text, rt.fonts, rt.size, rt.color, _theme, "center"
        )
        return
    chart = _rp0.get("chart")
    if chart is not None:
        _draw_chart(canvas, box, chart, fonts, _theme)
        return
    line = _rp0.get("line_chart")
    if line is not None:
        draw_line_chart(canvas, box, line, fonts, _theme)
        return
    # A date whose chip the theme switched off: baked text with no markdown node
    # behind it (the grouper had already split the leaf into key + day). Give it
    # a node so it renders as the ordinary line the author wrote, rather than as
    # the two stacked halves of a chip that is not being drawn.
    node = _effective_leaf_node(node, _rp0)

    if node is None:
        return

    raw_content = node.get("content", "")
    node_type = node.get("type", "")
    # The grouper strips backticks when relabeling a leaf as INLINE_CODE
    # (the wrapping is encoded by the type, not the content). Re-wrap here so
    # parse_inline_spans treats the content as a code span and the renderer
    # applies the inline-code background and monospace font.
    if (
        node_type == "inline_code"
        and raw_content
        and not (raw_content.startswith("`") and raw_content.endswith("`"))
    ):
        raw_content = f"`{raw_content}`"
    atx_level, atx_text = node.get("atx_level", 0), raw_content

    # Per-node render hints (own + cascaded from ancestor groups/root).
    rp = box.render_properties or {}
    weight = rp.get("content_weight")
    text_align = _resolve_h_align(rp, _theme)

    if node_type == "link":
        draw_link_box(
            canvas,
            box,
            node,
            fonts,
            _theme,
            background_images,
        )
    elif node_type == "drawing_element" and is_count(node.get("drawing_element")):
        if _theme.datapoints.sliders.enabled:  # a count is a slider, drawn as digits
            draw_count(canvas, box, node, fonts, _theme, background_images)
    elif (
        node_type == "drawing_element"
        and (node.get("drawing_element") or {}).get("kind") == "slider"
        and _theme.datapoints.sliders.enabled
    ):
        draw_slider(canvas, box, node, _theme, _paint_layered_fill)
    elif node_type == "drawing_element" and _theme.datapoints.task_controls.enabled:
        draw_task_control(canvas, box, node, fonts, _theme, _paint_layered_fill)
    elif node_type == "emoji":
        # Standalone/peeled/heading emoji leaf → styled badge or inline glyph,
        # routed by the grouper's persisted emoji_kind (no re-classification).
        draw_emoji_box(canvas, box, node, fonts, _theme, background_images)
    elif node_type == "inline_code":
        # Whole-leaf inline code → padded rounded box (like a link), never clipped.
        # Code spans inside paragraph text keep the _draw_code_run path in
        # draw_styled_text_box unchanged.
        draw_code_box(
            canvas,
            box,
            raw_content,
            fonts.mono,
            _theme,
            fonts.chip_emoji(node.get("code_variant"), _theme),
            node.get("code_variant"),
            node,
            background_images,
        )
    elif node_type == "code_block":
        draw_code_block(
            canvas,
            box,
            raw_content,
            node.get("code_language"),
            fonts.code_block or fonts.mono or fonts.typeface,
            _theme,
            paint_fill=_paint_layered_fill,
            emoji_tf=fonts.emoji,
            button_image=(background_images or {}).get(
                ("element", _theme.code_blocks.copy_button.bg_image)
            ),
        )
    elif node_type == "horizontal_rule":
        draw_horizontal_rule(canvas, box, _theme, node)
    elif node_type in ("content_break", "spacer"):
        # A lone `_`: the invisible break. A `+++` spacer is blank by definition. It occupies the rule's zero-height
        # box — so it still cuts the run and still takes the sibling gap — and
        # paints nothing at all. Explicit rather than a fallthrough, so the
        # underscore can never reach the text drawer.
        pass
    elif node_type == "image":
        url = image_url(raw_content)
        is_vector = image_cache.get_kind(url) == "svg"
        picture = image_picture(image_cache, url, is_vector)
        draw_image_box(
            canvas,
            box,
            raw_content,
            make_font(fonts.typeface, _theme.labels.font_size),
            picture,
            rp,
            _theme,
            # A vector is fitted whole; a photograph still cover-crops to fill.
            # The same flag picks the placeholder, so a loading SVG and the
            # real thing land identically.
            contain=is_vector,
            stand_in=named_placeholder(picture, raw_content, node, _theme, fonts),
        )
    elif node_type == "bullet_point":
        draw_styled_text_box(
            canvas,
            box,
            "•",
            fonts,
            _theme.text.font_size,
            _theme.text.color,
            _theme,
            text_align,
            # Pins only — a bullet keeps its own emoji font and text colour.
            emoji_style=_pin_only_emoji_style(_theme),
        )
    elif atx_level or node_type.startswith("heading"):
        level = atx_level or _heading_level(node_type)
        ts = _theme.headings.get(level)
        h_base_color = ts.color if ts else HEADING_COLORS[level]
        if ts is not None and ts.colors:
            # The title took its section's slot in the grouper, so a rotated
            # `### Heading 3` background and a rotated Heading3 font color land
            # on the same entry of their respective lists.
            _hi, _hchain = _rotation_slot(node, _theme)
            h_base_color = (
                _rotate_color(ts.colors, ts.color, _hi, _theme, "heading", _hchain)
                or h_base_color
            )
        eff_fonts, base_size = _effective_text_fonts(
            node_type, atx_level, fonts, _theme
        )
        h_scale, h_color = _weight_scale_and_color(_theme, weight, h_base_color)
        draw_styled_text_box(
            canvas,
            box,
            atx_text,
            eff_fonts,
            base_size * h_scale,
            h_color,
            _theme,
            text_align,
            fixed=(node or {}).get("fixed_text"),
            fixed_spans=(node or {}).get("fixed_text_spans"),
            marker=_marker_style(_theme, node_type, level, node=node),
            # Pins only — a heading keeps its own emoji font and text colour.
            emoji_style=_pin_only_emoji_style(_theme),
        )
    else:
        # Table cells swap in their themed table text style (font/size/color);
        # a piece split off a heading line (heading_ctx) keeps that heading's
        # style; for every other leaf _effective_text_fonts returns the base
        # fonts at theme.text.font_size, so this is the same path as before.
        table_role = node.get("table_role")
        heading_ctx = node.get("heading_ctx", 0)
        text_style = node.get("text_style")
        text_scopes = _text_style_scopes(node)
        eff_fonts, base_size = _effective_text_fonts(
            node_type,
            atx_level,
            fonts,
            _theme,
            table_role=table_role,
            heading_ctx=heading_ctx,
            text_style=text_style,
            text_scopes=text_scopes,
        )
        base_color = scoped_text_style(_theme, "text", text_scopes).color
        if heading_ctx:
            h_ts = _theme.headings.get(heading_ctx)
            base_color = h_ts.color if h_ts else HEADING_COLORS[heading_ctx]
            if h_ts is not None and h_ts.colors:
                # Pieces split off a heading line keep the heading's color, so
                # they must keep its rotated color too.
                _hi, _hchain = _rotation_slot(node, _theme)
                base_color = (
                    _rotate_color(
                        h_ts.colors, h_ts.color, _hi, _theme, "heading", _hchain
                    )
                    or base_color
                )
        if table_role:
            tts = _table_text_style(_theme, table_role)
            if tts is not None:
                base_color = tts.color
        # Mirrors _effective_text_fonts's branch order: an authored tier beats
        # the key color, a heading beats both.
        elif text_style:
            base_color = scoped_text_style(_theme, text_style, text_scopes).color
        elif node_type == "key":
            base_color = scoped_text_style(_theme, "key", text_scopes).color
        t_scale, t_color = _weight_scale_and_color(
            _theme, weight, base_color, text_style
        )
        eff_fonts, eff_size, t_color = _apply_kv_role(
            rp,
            eff_fonts,
            base_size * t_scale,
            t_color,
            _theme,
            fonts,
            heading_ctx,
            text_style,
            text_scopes,
        )
        # Date-chip key/day leaves swap in their ### Date Key/Day style, render
        # the key uppercased, and center within the chip cell.
        eff_fonts, eff_size, t_color = _apply_date_role(
            rp, eff_fonts, eff_size, t_color, _theme, fonts
        )
        content = _date_role_content(rp, raw_content)
        if (rp or {}).get("date_role"):
            text_align = "center"
        draw_styled_text_box(
            canvas,
            box,
            content,
            eff_fonts,
            eff_size,
            t_color,
            _theme,
            text_align,
            emoji_style=_theme.emojis.text,
            styled=_prose_text_is_styled(
                node_type, heading_ctx, table_role, text_style, weight, rp, _theme
            ),
            fixed=(node or {}).get("fixed_text"),
            fixed_spans=(node or {}).get("fixed_text_spans"),
            marker=_marker_style(
                _theme, node_type, heading_ctx, table_role, text_style, node
            ),
        )


# ---------------------------------------------------------------------------
# Debug spacing overlay
# ---------------------------------------------------------------------------


def _draw_spacing_overlay(
    canvas: skia.Canvas,
    gap_rects: list,
    color: int = SPACING_DEBUG_RAMP[-1],
) -> None:
    """Overlay spacing gaps as filled rects in ``color``.

    Used for the element-spacing gaps, which default to the element tier (red end
    of the spacing ramp); section gaps are handled by
    ``_draw_section_spacing_overlay`` per owner level.
    """
    gap_paint = skia.Paint(Color=color, Style=skia.Paint.kFill_Style, AntiAlias=True)
    for g in gap_rects:
        if g.width > 0 and g.height > 0:
            canvas.drawRect(skia.Rect.MakeXYWH(g.x, g.y, g.width, g.height), gap_paint)


def _draw_section_spacing_overlay(canvas: skia.Canvas, entries: list) -> None:
    """Overlay section-spacing gaps, each colored by its owner heading level.

    ``entries`` is a list of ``(LayoutBox, level)`` so the same level's gaps share
    a color and level transitions are visible.
    """
    for g, level in entries:
        if g.width > 0 and g.height > 0:
            canvas.drawRect(
                skia.Rect.MakeXYWH(g.x, g.y, g.width, g.height),
                skia.Paint(
                    Color=_spacing_debug_color(level),
                    Style=skia.Paint.kFill_Style,
                    AntiAlias=True,
                ),
            )


def _draw_text_boxes(
    canvas: skia.Canvas,
    boxes: list,
    node_index: dict,
    fonts: FontSet,
    theme: Theme,
) -> None:
    """Stroke each text leaf's real text box (tight glyph extent, unclamped)."""
    paint = skia.Paint(
        Color=DEBUG_TEXTBOX_COLOR,
        Style=skia.Paint.kStroke_Style,
        StrokeWidth=1.5,
        AntiAlias=True,
    )
    for box in boxes:
        nd = node_index.get(box.content_id) if box.content_id else None
        # _text_extent_rect takes no render_properties, so the baked-date leaf
        # has to be resolved here (see _effective_leaf_node) or the overlay draws
        # nothing for it.
        nd = _effective_leaf_node(nd, box.render_properties)
        rect = _text_extent_rect(box, nd, fonts, theme)
        if rect is not None and rect.width() > 0 and rect.height() > 0:
            canvas.drawRect(rect, paint)


# ---------------------------------------------------------------------------
# Full scene
# ---------------------------------------------------------------------------


def draw_document(
    canvas: skia.Canvas,
    boxes: list,
    section_boxes: list | None,
    node_index: dict,
    layout_w: float,
    layout_h: float,
    fonts: FontSet,
    image_cache: ImageCache,
    theme: Theme | None = None,
    ast_layout: LayoutNode | None = None,
    background_images: dict | None = None,
) -> None:
    """Paint the document itself, in content coordinates: the root content box,
    every section background, every content box, and the D/P/B debug overlays.

    Everything here scrolls with the content and nothing here depends on the
    window — not its size, the scroll offset, the chrome or the pixel ratio.
    That is what lets ``render_picture`` record it once per scene and replay it
    every frame; ``draw_scene`` owns what the window adds around it.
    """
    _theme = theme or Theme()
    strokes: list = []

    # Content box — solid fill behind cards, filling the layout area.
    if _theme.root.box:
        inset = 0.0
        _bw = layout_w - inset * 2
        _bh = layout_h - inset * 2
        if _bw > 0 and _bh > 0:
            box_rect = skia.Rect.MakeXYWH(inset, inset, _bw, _bh)
            box_paint = skia.Paint(
                Color=_theme.root.box_fill_color,
                Style=skia.Paint.kFill_Style,
                AntiAlias=True,
            )
            r = _theme.root.box_radius
            if r > 0:
                canvas.drawRoundRect(box_rect, r, r, box_paint)
            else:
                canvas.drawRect(box_rect, box_paint)

    if section_boxes:
        # Color cycling counter per (kind, level): sections cycle per level, cards
        # cycle across all cards in document order.
        _color_idx: dict[tuple[str, int], int] = {}
        for sbox in section_boxes:
            if sbox.kind == "date_chip":
                # A date chip's own themed background (### Dates → chip). The
                # base fill/gradient/stroke; optional two-region split painted
                # on top, clipped to the chip's rounded rect.
                _paint_date_chip_background(canvas, sbox, _theme, strokes)
                continue
            if sbox.kind == "ring":
                # A circular bar: the "background" is the arc itself (track +
                # value arc), not a rect fill. Value/unit text draw on top.
                _draw_ring_arc(canvas, sbox, _theme)
                continue
            st, img_key = _paint_style_for(
                sbox.kind, sbox.level, _theme, sbox.fixed_style_key
            )
            if st is None or (sbox.kind.startswith("table") and not st.is_active()):
                continue
            # A box's own level is part of its gate chain here — "## Heading 2 /
            # Rotate background colors: no" reads as "heading-2 backgrounds
            # don't cycle", which is its own level, unlike the content gates.
            rot_chain = sbox.rotation_chain + (
                (f"fixed:{sbox.fixed_style_key}|{sbox.level}",)
                if sbox.fixed_style_key
                else ((sbox.level,) if sbox.level else ())
            )
            bg_color = None
            if st.bg_colors:
                if sbox.rotation_index is not None:
                    # Through `Rotate colors: sync`, exactly as _bg_selector
                    # resolves it — a section whose own cycle has only itself
                    # in it (one `### ` card inside each `## ` wrapper) still
                    # paints the colour of the card it is in.
                    i = _synced_slot(
                        sbox.rotation_index,
                        sbox.rotation_chain,
                        sbox.rotation_path,
                        _theme,
                    )
                else:
                    # No markdown node behind this box (table rows, the root):
                    # keep the positional counter, so table zebra striping and
                    # every pre-rotation theme paint exactly as before.
                    key = (sbox.kind, sbox.level)
                    i = _color_idx.get(key, 0)
                    _color_idx[key] = i + 1
                if sbox.kind in ("table_header", "table_row"):
                    bg_color = _table_background_color(st, i, _theme)
                else:
                    bg_color = _rotate_color(
                        st.bg_colors,
                        None,
                        i,
                        _theme,
                        "card" if sbox.kind in ("card", "image_card") else "background",
                        rot_chain,
                    )
            if st.stroke_colors:
                st = dataclasses.replace(
                    st,
                    stroke_color=_rotate_color(
                        st.stroke_colors,
                        st.stroke_color,
                        _synced_slot(
                            sbox.rotation_index or 0,
                            sbox.rotation_chain,
                            sbox.rotation_path,
                            _theme,
                        ),
                        _theme,
                        "card" if sbox.kind in ("card", "image_card") else "background",
                        rot_chain,
                    ),
                )
            if sbox.clip is not None:
                _clip_to_shell(canvas, sbox.clip)
            bg_img = (background_images or {}).get(img_key)
            if sbox.bg_image_url:
                # A photo card: its photo, the theme's, or the placeholder.
                bg_img = card_photo(image_cache, sbox.bg_image_url, bg_img)
            _paint_section_background(
                canvas, sbox, st, bg_img, bg_color, _theme, strokes
            )
            if sbox.clip is not None:
                canvas.restore()

    # Link / inline-code padding rings are collected during the content draw below
    # (when VIEW.debug_padding) and painted in the P overlay afterwards.
    if VIEW.debug_padding:
        _DEBUG_PAD_RINGS.clear()
    pill = lambda b, nd: _link_pill_rect(b, nd, fonts, _theme)  # noqa: E731
    node_index = paint_segmented(
        canvas, boxes, node_index, pill, _theme, background_images
    )
    for box in boxes:
        node = node_index.get(box.content_id) if box.content_id else None
        draw_content_box(
            canvas, box, node, fonts, image_cache, _theme, background_images
        )
    # Every section's stroke is the front layer, above whatever reached its edge.
    for rect, r, paint, align, clip in strokes:
        if clip is not None:
            _clip_to_shell(canvas, clip)
        draw_stroke(canvas, rect, r, paint, align)
        if clip is not None:
            canvas.restore()

    if VIEW.debug_spacing or VIEW.debug_padding or VIEW.text_boxes:
        if (VIEW.debug_spacing or VIEW.debug_padding) and ast_layout is not None:
            gap_rects: list = []
            section_rects: list = []
            pad_section_boxes: list = []
            place_boxes(
                ast_layout,
                0,
                0,
                layout_w,
                layout_h,
                node_index,
                fonts,
                _theme,
                debug_gaps=gap_rects,
                debug_section_gaps=section_rects,
                section_boxes=pad_section_boxes,
            )
            if VIEW.debug_spacing:
                _draw_spacing_overlay(canvas, gap_rects, SPACING_DEBUG_RAMP[-1])
                _draw_section_spacing_overlay(canvas, section_rects)
            if VIEW.debug_padding:
                # Root/content padding is applied as a canvas translate rather than a
                # drawn box, so add a root SectionBox (tier 0, green) around the whole
                # layout so its padding band is visible in the overlay.
                root_pad = _theme.root.padding
                if root_pad.any():
                    pad_section_boxes.insert(
                        0,
                        SectionBox(
                            -root_pad.left,
                            -root_pad.top,
                            layout_w + root_pad.x,
                            layout_h + root_pad.y,
                            0,
                            root_pad,
                            "root",
                        ),
                    )
                _draw_section_padding_overlay(canvas, pad_section_boxes)
                # Link + inline-code padding rings collected during the content pass.
                for outer, inner in _DEBUG_PAD_RINGS:
                    _draw_pad_ring(canvas, outer, inner, LINKCODE_PAD_DEBUG_COLOR)
        if VIEW.text_boxes:
            _draw_text_boxes(
                canvas,
                boxes,
                node_index,
                fonts,
                _theme,
            )


def _document_origin(
    win_w: int, win_h: int, layout_w: float, theme: Theme
) -> tuple[float, float, float, float, float, float]:
    """``(vp_x, vp_y, vp_w, vp_h, origin_x, la_w)`` for one window size.

    The viewport, the x where the document's content origin sits in it (left
    pad, plus half the slack when centered), and the layout's view width. One
    function for ``draw_scene``, which paints through it, and
    ``window_to_content``, which inverts it, so a click can never disagree with
    what was painted where it landed.
    """
    vp_x, vp_y, vp_w, vp_h = _viewport_metrics(win_w, win_h)
    pad = theme.root.padding
    la_w = max(0.0, vp_w - pad.x)  # layout width (L+R reduces) / scrollbar X view
    origin_x = _content_origin_x(vp_x, la_w, layout_w, pad.left, theme.root.centered)
    return vp_x, vp_y, vp_w, vp_h, origin_x, la_w


def window_to_content(
    mx: float,
    my: float,
    win_w: int,
    win_h: int,
    layout_w: float,
    theme: Theme | None,
    scroll: ScrollState,
) -> tuple[float, float] | None:
    """The content point under window point ``(mx, my)``, or None outside the
    viewport — the inverse of ``draw_scene``'s origin, scroll and top-pad
    translates."""
    _theme = theme or Theme()
    vp_x, vp_y, vp_w, vp_h, origin_x, _la_w = _document_origin(
        win_w, win_h, layout_w, _theme
    )
    if not (vp_x <= mx < vp_x + vp_w and vp_y <= my < vp_y + vp_h):
        return None
    return mx - origin_x + scroll.x, my - vp_y + scroll.y - _theme.root.padding.top


def draw_scene(
    canvas: skia.Canvas,
    document: "skia.Picture",
    layout_w: float,
    layout_h: float,
    title: str,
    chrome_typeface: skia.Typeface,
    win_w: int,
    win_h: int,
    scroll: ScrollState,
    theme: Theme | None = None,
    dpr: float = 1.0,
    background_images: dict | None = None,
    overlay: Callable[[skia.Canvas], None] | None = None,
) -> None:
    """Paint one window frame around the recorded *document*.

    The chrome, the viewport-fixed root background and the scrollbars are drawn
    here, every frame; the document (``draw_document``, recorded once by
    ``render_picture.record_document``) is replayed under the scroll translate
    and the viewport clip. Replaying through that clip is the viewport culling:
    the picture's R-tree plays back only the draws whose bounds meet it.
    """
    _theme = theme or Theme()

    # Frame/chrome fills the canvas; the layout render area is painted over it.
    canvas.clear(FRAME_BG_COLOR)
    # Reset any accumulated transform then set the logical→physical scale for retina support
    canvas.resetMatrix()
    canvas.scale(dpr, dpr)

    vp_x, vp_y, vp_w, vp_h, origin_x, la_w = _document_origin(
        win_w, win_h, layout_w, _theme
    )
    vp_rect = skia.Rect.MakeXYWH(vp_x, vp_y, vp_w, vp_h)

    # Layout render-area background: fill color → image → gradient, confined to
    # the viewport so the frame color shows around it. Painted in viewport space
    # (before the scroll translate) so it stays fixed.
    _paint_layered_fill(
        canvas,
        vp_rect,
        bg_color=_theme.root.bg_color,
        image=(background_images or {}).get(0),
        gradient=_theme.root.gradient,
        corner_radius=0.0,
        shadows=_theme.root.shadows,
    )

    if VIEW.show_frame:
        chrome_font = make_font(chrome_typeface, CHROME_SIZE)
        chrome_paint = skia.Paint(Color=CHROME_COLOR, AntiAlias=True)
        _title_line_h = CHROME_SIZE + 3
        for _i, _title_line in enumerate(title.split("\n")):
            canvas.drawString(
                _title_line,
                PADDING,
                TITLE_H - 4 + _i * _title_line_h,
                chrome_font,
                chrome_paint,
            )

    # Content padding (TLRB): X reduces the layout width (la_w); Y adds top+bottom
    # margin to the scrollable document. Background already fills the full viewport.
    pad = _theme.root.padding
    canvas.save()
    # Clip to the full background area, not the inset layout frame, so overflow
    # content bleeds into the padding instead of being clipped at the layout edge.
    canvas.clipRect(skia.Rect.MakeXYWH(vp_x, vp_y, vp_w, vp_h))
    # Content origin: left pad, plus half the slack if centered. Three separate
    # translates, as always: window_to_content inverts them.
    canvas.translate(origin_x, vp_y)
    canvas.translate(-scroll.x, -scroll.y)  # scroll the document
    canvas.translate(0.0, pad.top)  # y: top pad (scrolls with content)
    canvas.drawPicture(document)
    if overlay is not None:  # per frame, in content space (render_scroll_overlay)
        overlay(canvas)
    canvas.restore()

    scroll.draw_scrollbars(
        canvas,
        vp_x,
        vp_y,
        vp_w,
        vp_h,  # track: full viewport (background edges)
        la_w,
        vp_h,  # view: X = la_w (clip width), Y = vp_h
        layout_w,
        layout_h + pad.y,  # content (matches clamp_scroll)
    )

    if VIEW.show_frame:
        hint_font = make_font(chrome_typeface, HINT_SIZE)
        hint_text = f"↑↓←→ pan  |  R reload  |  W wireframe  |  D gaps  |  P pad  |  B boxes  |  I imgs  |  F frame  |  S shot  |  C copy  |  G bento{VIEW.stack_key_hint}  |  E export{VIEW.quit_key_hint}"
        hint_w = hint_font.measureText(hint_text)
        canvas.drawString(
            hint_text,
            (win_w - hint_w) / 2,
            win_h - HINT_H + 12 - VIEW.prompt_bar_h,
            hint_font,
            skia.Paint(Color=CHROME_COLOR, AntiAlias=True),
        )


# ---------------------------------------------------------------------------
# GL surface helper
# ---------------------------------------------------------------------------


def make_surface(context: skia.GrDirectContext, fb_w: int, fb_h: int) -> skia.Surface:
    target = skia.GrBackendRenderTarget(
        fb_w, fb_h, 0, 0, skia.GrGLFramebufferInfo(0, 0x8058)
    )
    surface = skia.Surface.MakeFromBackendRenderTarget(
        context,
        target,
        skia.kBottomLeft_GrSurfaceOrigin,
        skia.kRGBA_8888_ColorType,
        skia.ColorSpace.MakeSRGB(),
    )
    assert surface is not None, "Failed to create skia GL surface"
    return surface
