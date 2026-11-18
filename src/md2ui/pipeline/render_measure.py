"""Intrinsic sizing: how big a node wants to be, before anything is placed.

This is the half of the renderer that painting must agree with. `natural_width`
and `natural_height` answer "how much room does this node need?"; `first_baseline`
and the extent helpers answer "where does its text sit?". Placement consumes
these answers; painting consumes the same ones, which is the invariant ADR-400
exists to protect.

Nothing here takes a canvas, and nothing here reads the renderer's mutable
display state (`render_settings.VIEW`).

Placement (`place_boxes`, `_layout_row`, the table and bento row builders) stays
in the renderer for now and depends on this module, never the reverse.
"""

import contextlib
import dataclasses
import functools
import math
from collections.abc import Callable, Iterator

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.grouper_escapes import HARD_BREAK
from md2ui.pipeline.generator_units import IMAGE_MIN_WIDTH, LEAF_WIDTH
from md2ui.pipeline.layout_script_parser import (
    LayoutBox,
    LayoutNode,
)
from md2ui.pipeline.render_backgrounds import (
    _layers_pad,
    _layers_section_level,
    _row_backgrounds_match,
    _wrap_layers,
)
from md2ui.pipeline.render_chart import _chart_plan_for
from md2ui.pipeline.render_line_chart import line_chart_height
from md2ui.pipeline import render_slots
from md2ui.pipeline.render_code_blocks import code_block_plan, is_code_block_leaf
from md2ui.pipeline.render_drawing_elements import drawing_element_baseline
from md2ui.pipeline.render_drawing_elements import leaf_slider_size, task_control_size
from md2ui.pipeline.render_glyph_faces import glyph_advance
from md2ui.pipeline.render_metrics import (
    image_card_height,
    _text_ink,
    LINE_SCALE,
    _chip_metrics,
    _code_font,
    _emoji_badge_size,
    _image_aspect_ratio,
    _image_content_width,
    _label_runs_width,
    _link_label_width,
    image_floor,
    image_width_cap,
    _link_pill_size,
    _measure_word,
    _text_emoji_px,
    _widest_unit,
    _wrap_lines,
)
from md2ui.pipeline.render_ring_text import ring_text
from md2ui.pipeline.render_spacing import (
    _is_image_leaf,
    _is_pure_image_block,
    _resolve_element_spacing,
    _sibling_gap,
)
from md2ui.pipeline.render_style import (
    FontSet,
    _apply_date_role,
    _apply_kv_role,
    _date_role_content,
    _effective_leaf_node,
    _effective_text_fonts,
    _emoji_glyph_font,
    _load_emoji_typeface,
    _marker_font,
    _resolve_h_align,
    _resolve_link,
    _span_font,
    _table_key_fonts,
    _weight_scale_and_color,
)
from md2ui.pipeline.render_text_scopes import link_label_fonts
from md2ui.pipeline.render_text import (
    parse_inline_spans,
)
from md2ui.pipeline.theme import (
    BarTheme,
    LINE_ALIGN_DEFAULT,
    PaddingBox,
    TABLE_KEY_COL_MAX_SHARE,
    TextStyle,
    Theme,
    resolve_section_style,
)

# Leaf types that never inherit their heading line's text style: links and
# separated inline-code leaves render as their own pills (their styles come from
# ## Links / ## Inline Code), and images/rules have no text at all.
# A break leaf has no text, so no heading style applies to it — the invisible
# `_` break behaves as the painted rule does everywhere except the draw.
# A ``+++`` spacer is one too: blank space, sized from its render properties.
_BREAK_LEAVES = ("horizontal_rule", "content_break", "spacer")


def _padded_children(node: LayoutNode) -> list:
    """Return children list padded with implicit '-' leaves to match ratios."""
    children = list(node.children)
    if node.ratios:
        while len(children) < len(node.ratios):
            children.append(LayoutNode(type="-", ratios=[], children=[]))
    return children


def _is_transparent_container(child: LayoutNode, theme: Theme) -> bool:
    """True when ``child`` merely groups 2+ same-level sibling sections (so its
    children are the sections). A ``merge_rows`` row is NOT transparent — it is a
    single merged section. Mirrors the wrapping decision in ``_section_style_for``.
    """
    level = child.section_level
    if level is None:
        return False
    if sum(1 for c in child.children if c.section_level == level) < 2:
        return False
    st = resolve_section_style(theme, level, child.section_style_key)
    if (
        child.type == "row"
        and st is not None
        and st.merge_rows
        and _row_backgrounds_match(child, level)
    ):
        return False
    return True


def _child_owner_level(child: LayoutNode, theme: Theme, owner_level: int) -> int:
    """Owner level for ``child``'s descendant section gaps.

    A *structural section* (has a section_level and is not a transparent
    same-level container) owns its descendants' spacing at its own level;
    otherwise the enclosing ``owner_level`` flows through.
    """
    if child.section_level is None or _is_transparent_container(child, theme):
        return owner_level
    return child.section_level


def _spacer_height(spacer: dict) -> float:
    """Height of a ``+++`` spacer leaf (ADR-203): its px along a column, and
    nothing for a row spacer, which is horizontal space."""
    if spacer.get("axis") == "row":
        return 0.0
    return max(0.0, float(spacer.get("size") or 0.0))


def _explode_words(content: str) -> list:
    """Split styled content into per-word tuples
    ``(word, bold, italic, code, strike, link, space_before)``.

    A whitespace-only span between two markers (```a` `b```) splits into nothing
    and disappears here, which is why ``code``/``strike`` carry a region id: it
    is the only thing left telling ``_flag_runs`` where one marker ends and the
    next begins.

    Memoised by content: a leaf is measured at every width a trial layout tries,
    and its words never change. A fresh list per call, so no caller can edit the
    shared copy."""
    return list(_exploded(content))


@functools.lru_cache(maxsize=16_384)
def _exploded(content: str) -> tuple:
    """``(word, bold, italic, code, strike, link, space_before)`` per word.

    ``space_before`` is the 7th field because the first six are read by INDEX
    downstream (``_FLAG_CODE`` / ``_FLAG_STRIKE`` / ``_FLAG_LINK`` are 3/4/5), so
    it can only be appended.

    It exists because splitting each span on ``" "`` throws away the one thing
    that says whether a word was attached to the one before it. Both consumers
    then assumed a space always stood between two words, and drew
    ``Open **Settings**.`` as ``Open Settings .`` -- the punctuation is its own
    span, with no space in front of it. The correct case worked by accident of
    the same rule: ``Open **Settings** now.`` has its trailing span BEGIN with a
    space, so the split yields ``['', 'now.']``, the empty part is dropped, and
    the inter-word space put back is exactly the one the author wrote. The two
    cases produced the same word list and differed only in what was discarded.

    A space is recorded from two places, which is why the empty parts matter:
    between two parts of one span (the split consumed it), and from an empty
    part at a span's edge (the span began or ended with one).

    The field says what stands before the word: nothing, a space, or an
    author's hard break (``HARD_BREAK``, see grouper_escapes). Not an 8th field:
    the paint path appends its colour spans there (``project_paint_spans``).
    """
    words: list = []
    space_before: bool | str = False
    for span_text, bold, italic, code, strike, link in parse_inline_spans(content):
        for j, chunk in enumerate(span_text.split(HARD_BREAK)):
            if j:
                space_before = HARD_BREAK
            for i, part in enumerate(chunk.split(" ")):
                if i and space_before != HARD_BREAK:
                    space_before = True
                if part:
                    words.append((part, bold, italic, code, strike, link, space_before))
                    space_before = False
    return tuple(words)


def _line_width(line: list, fonts: FontSet, size: float) -> float:
    """Width of one line: the words, plus a space only where one was WRITTEN
    (matches the drawer).

    ``i > 0`` alone would put a space in front of punctuation that followed a
    span with nothing between them — see :func:`_exploded`. The index test stays
    as well, because a word that begins a line never takes a leading space even
    when one preceded it in the source.
    """
    if any(w[6] == HARD_BREAK for w in line[1:]):
        # A text with forced breaks is as wide as its widest segment.
        segments: list = [[]]
        for w in line:
            if w[6] == HARD_BREAK and segments[-1]:
                segments.append([])
            segments[-1].append(w)
        return max(_line_width(seg, fonts, size) for seg in segments)
    total = 0.0
    for i, w in enumerate(line):
        word, bold, italic = w[0], w[1], w[2]
        if i > 0 and w[6]:
            total += _span_font(fonts, size, bold, italic).measureText(" ")
        total += _measure_word(word, bold, italic, fonts, size)
    return total


def _is_text_marker(lm: dict) -> bool:
    """True for gutter markers drawn as text (a numbered ordinal or a quote
    char) — as opposed to a bullet shape/emoji or a blockquote bar."""
    return lm.get("kind") == "number" or lm.get("mode") == "char"


def _leaf_height(
    nd: dict | None,
    width: float,
    fonts: FontSet,
    theme: Theme | None = None,
    render_properties: dict | None = None,
) -> float:
    """Natural height of a leaf node given its content and available width.

    Boxes hug their content — no per-leaf padding.
    """
    _t = theme or Theme()
    nd = _effective_leaf_node(nd, render_properties)
    sp = (render_properties or {}).get("spacer")
    if sp is not None:
        return _spacer_height(sp)
    lm = (render_properties or {}).get("list_marker")
    if lm is not None:
        # Marker leaf (no markdown node): an aside marker stays near the first
        # content line, while a marker above the content hugs its own ink/shape.
        # A horizontal quote bar's height is its thickness; its configured
        # length is handled by _leaf_natural_width.
        if not lm.get("aside", True):
            if lm.get("kind") == "quote" and lm.get("mode") == "bar":
                return float(lm.get("bar_width", 0.0))
            if _is_text_marker(lm):
                font, _size = _marker_font(lm, fonts, _t)
                return _text_ink(lm.get("text") or "", font)[1]
            return float(lm.get("size", 0.0))
        # An aside glyph/shape is kept to ~the first content line so the row
        # height is driven by the content.
        # A text marker hugs its ink (a 64px ordinal draws ~46px tall), so a
        # short item's row isn't padded out by the font's ascent/descent gaps.
        if _is_text_marker(lm):
            font, _size = _marker_font(lm, fonts, _t)
            return _text_ink(lm.get("text") or "", font)[1]
        return max(float(lm.get("size", 0.0)), _t.text.font_size)
    sep = (render_properties or {}).get("separator")
    if sep is not None:
        # A drawn row separator (## Separators). A rule stretches to the row —
        # _is_separator_rule puts it on the same fill path as a blockquote bar —
        # so it claims no height of its own; a glyph is one line of text.
        # A rule stretches to the row (see _is_bar_marker), so it claims no
        # height; a glyph is one text line, measured the way a text box is so
        # the baselines line up.
        return 0.0 if sep.get("kind") == "rule" else _t.text.font_size * LINE_SCALE
    _rp = render_properties or {}
    dpb = _rp.get("datapoint_bar")
    if dpb is not None:
        return _datapoint_bar_height(dpb, _t)
    if _rp.get("ring_role") is not None:
        return ring_text(_rp, fonts, _t).height
    chart = _rp.get("chart")
    if chart is not None:
        return _chart_plan_for(chart, width, fonts, _t).height
    line = _rp.get("line_chart")
    if line is not None:
        return line_chart_height(line, width, fonts, _t)
    if nd is None:
        return _t.text.font_size

    if nd.get("type") == "drawing_element":
        kind = (nd.get("drawing_element") or {}).get("kind")
        if kind == "slider" and _t.datapoints.sliders.enabled:
            return leaf_slider_size(nd, _t)[1]
        if _t.datapoints.task_controls.enabled:
            return task_control_size(_t)[1]

    if nd.get("type") == "link":
        _variant, label, is_emoji, style = _resolve_link(nd, _t)
        size = (style.text_style or TextStyle()).font_size
        font, runs, e_tf = link_label_fonts(nd, label, fonts, _t, size)
        _pill_w, pill_h = _link_pill_size(runs, style, font, size, e_tf, is_emoji)
        return pill_h

    if nd.get("type") == "emoji":
        return _emoji_leaf_size(nd, fonts, _t)[1]

    if nd.get("type") == "inline_code":
        # Whole-leaf inline code renders as a padded rounded box (like a link), so
        # reserve the code background's vertical padding.
        metrics = _code_font(_t, nd.get("code_variant"), fonts.mono)[0].getMetrics()
        text_h = metrics.fDescent - metrics.fAscent
        return text_h + _t.inline_code.resolved(nd.get("code_variant")).padding.y

    if nd.get("type") == "code_block":
        code_face = fonts.code_block or fonts.mono or fonts.typeface
        return code_block_plan(
            nd.get("content", ""),
            nd.get("code_language"),
            code_face,
            _t.code_blocks,
        ).height

    if nd.get("type") == "image":
        # Height collapses to the image's content: capped width / aspect ratio.
        content_w = _image_content_width(render_properties, width)
        return content_w / _image_aspect_ratio(render_properties, content_w)

    if nd.get("type") in _BREAK_LEAVES:
        return 0.0  # by design: render_spacing gives a break the gap on both sides; the rule strokes at mid-y

    raw_content = nd.get("content", "")
    node_type = nd.get("type", "")

    atx_level, atx_text = nd.get("atx_level", 0), raw_content

    # content_weight scales the font size, so reserve the matching height.
    weight = (render_properties or {}).get("content_weight")
    w_scale, _ = _weight_scale_and_color(_t, weight, 0, nd.get("text_style"))
    eff_fonts, base_size = _effective_text_fonts(
        node_type,
        atx_level,
        fonts,
        _t,
        node=nd,
    )
    size = base_size * w_scale
    eff_fonts, size, _ = _apply_kv_role(
        render_properties,
        eff_fonts,
        size,
        0,
        _t,
        fonts,
        node=nd,
    )
    eff_fonts, size, _ = _apply_date_role(
        render_properties, eff_fonts, size, 0, _t, fonts
    )

    n_lines = max(len(_wrap_lines(_explode_words(atx_text), width, eff_fonts, size)), 1)
    return n_lines * size * LINE_SCALE


def _leaf_first_baseline(
    nd: dict | None,
    fonts: FontSet,
    theme: Theme | None = None,
    render_properties: dict | None = None,
) -> float | None:
    """Distance from a leaf's box top down to its FIRST text baseline.

    Mirrors what each drawer actually does — ``draw_styled_text_box`` puts the
    baseline at ``box.y + size`` (not at the ascent), ``draw_code_box`` and
    ``draw_link_box`` hang theirs off a self-centered pill, ``draw_emoji_box``
    off a centered glyph — so it MUST be kept in sync with them, like
    ``_text_extent_rect``. Returns ``None`` for a leaf with no text baseline (an
    image, a rule, a bar, a chart): those have nothing to align to.

    Used to baseline-align the cells of a same-line row: three different height
    conventions meet there (``size * LINE_SCALE`` for text, ``ascent + descent +
    padding`` for pills, bare metrics for emoji), so neither box top nor box
    bottom puts the glyphs on one line.
    """
    _t = theme or Theme()
    _rp = render_properties or {}
    nd = _effective_leaf_node(nd, _rp)
    lm = _rp.get("list_marker")
    if lm is not None:
        # A vertical quote bar is stretched rather than aligned. Text markers
        # expose the actual baseline used by the drawer; emoji bullets draw at
        # y + size; shape bullets use their bottom edge as the visual baseline.
        if not lm:
            return None
        if lm.get("kind") == "quote" and lm.get("mode") == "bar":
            return None
        if _is_text_marker(lm):
            font, _size = _marker_font(lm, fonts, _t)
            return _text_ink(lm.get("text") or "", font)[0]
        size = float(lm.get("size", 0.0))
        if lm.get("emoji"):
            return size
        line_h = min(max(size, _t.text.font_size), _t.text.font_size * LINE_SCALE)
        return size + max(0.0, (line_h - size) / 2.0)
    _sep = _rp.get("separator")
    if _sep is not None:
        # A separator GLYPH is one line of text and must sit on the same
        # baseline as the pieces it divides; a rule is a line, nothing to align.
        return None if _sep.get("kind") == "rule" else _t.text.font_size
    if any(_rp.get(k) is not None for k in ("datapoint_bar", "chart", "line_chart")):
        return None
    if _rp.get("ring_role") is not None:
        return ring_text(_rp, fonts, _t).size
    if nd is None:
        return None

    node_type = nd.get("type", "")
    if node_type == "drawing_element":
        base = drawing_element_baseline(nd.get("drawing_element"), fonts, _t)
        if base is not None:
            return base
    if node_type == "link":
        _variant, label, is_emoji, style = _resolve_link(nd, _t)
        size = (style.text_style or TextStyle()).font_size
        font, runs, e_tf = link_label_fonts(nd, label, fonts, _t, size)
        metrics = font.getMetrics()
        _pill_w, pill_h = _link_pill_size(runs, style, font, size, e_tf, is_emoji)
        # draw_link_box: pill self-centers in the cell, text centers in the pill.
        text_h = metrics.fDescent - metrics.fAscent
        return (pill_h - text_h) / 2.0 - metrics.fAscent

    if node_type == "emoji":
        return _emoji_first_baseline(nd, fonts, _t)

    if node_type == "inline_code":
        metrics = _code_font(_t, nd.get("code_variant"), fonts.mono)[0].getMetrics()
        # draw_code_box: bg self-centers, text sits at pad.top below its top.
        return (
            _t.inline_code.resolved(nd.get("code_variant")).padding.top
            - metrics.fAscent
        )

    if node_type == "code_block":
        code_face = fonts.code_block or fonts.mono or fonts.typeface
        return code_block_plan(
            nd.get("content", ""),
            nd.get("code_language"),
            code_face,
            _t.code_blocks,
        ).baseline

    if node_type in ("image", *_BREAK_LEAVES):
        return None

    atx_level = nd.get("atx_level", 0)
    weight = _rp.get("content_weight")
    w_scale, _ = _weight_scale_and_color(_t, weight, 0, nd.get("text_style"))
    eff_fonts, base_size = _effective_text_fonts(
        node_type,
        atx_level,
        fonts,
        _t,
        node=nd,
    )
    size = base_size * w_scale
    eff_fonts, size, _ = _apply_kv_role(
        _rp,
        eff_fonts,
        size,
        0,
        _t,
        fonts,
        node=nd,
    )
    eff_fonts, size, _ = _apply_date_role(_rp, eff_fonts, size, 0, _t, fonts)
    return size


def _emoji_first_baseline(nd: dict, fonts: FontSet, theme: Theme) -> float | None:
    """First baseline of an emoji leaf, mirroring ``draw_emoji_box``: a peeled
    glyph sits on the text line, a badge glyph centers inside its fill box."""
    content = nd.get("content", "")
    if not content:
        return None
    if nd.get("emoji_kind") == "text":
        e_tf = _load_emoji_typeface(theme.emojis.text.font_path, fonts.emoji)
        font = _emoji_glyph_font(e_tf, fonts.typeface, _text_emoji_px(nd, theme))
        return -font.getMetrics().fAscent
    style, b_tf = fonts.emoji_badge(nd, theme)
    font = _emoji_glyph_font(b_tf, fonts.typeface, style.icon_size)
    m = font.getMetrics()
    glyph_h = m.fDescent - m.fAscent
    _box_w, box_h = _emoji_badge_size(content, style, b_tf, fonts.typeface)
    return (box_h - glyph_h) / 2.0 - m.fAscent


def first_baseline(
    node: LayoutNode,
    width: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme | None = None,
) -> float | None:
    """First text baseline of a laid-out cell, measured from its box top.

    A leaf answers for itself; a container answers with its first child's
    baseline, offset by the wrap padding that child sits inside (the same
    ``_wrap_layers`` inset ``place_boxes`` applies). ``None`` when nothing in
    the subtree has a baseline to align to.
    """
    _t = theme or Theme()
    if node.type == "-":
        nd = node_index.get(node.content_id) if node.content_id else None
        return _leaf_first_baseline(nd, fonts, _t, node.render_properties)
    pad_top = _layers_pad(_wrap_layers(node, _t, frozenset())).top
    for child in _padded_children(node):
        base = first_baseline(child, width, node_index, fonts, _t)
        if base is not None:
            return base + pad_top
    return None


# One rebuild's heights, live only inside ``height_memo()``. ``place_boxes`` asks
# ``natural_height`` for each child on its way down, and each ask re-walks that
# child's subtree several times per rebuild.
# The key leaves out ``node_index``, ``fonts`` and ``theme``, which one scope never
# changes, and the value holds the node so its id cannot be reused. ``None`` outside
# a scope, so ``generate``'s measurers, whose nodes the bakes edit later, never hit it.
_HEIGHT_MEMO: dict[tuple, tuple[LayoutNode, float]] | None = None


@contextlib.contextmanager
def height_memo() -> Iterator[None]:
    """Memoise ``natural_height`` for one placement of a finished, baked layout."""
    global _HEIGHT_MEMO
    _HEIGHT_MEMO = {}
    try:
        yield
    finally:
        _HEIGHT_MEMO = None


def natural_height(
    node: LayoutNode,
    width: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme | None = None,
    in_section_levels: frozenset[int] = frozenset(),
    owner_level: int = 0,
) -> float:
    """``_natural_height_uncached``, memoised inside ``height_memo()``."""
    memo = _HEIGHT_MEMO
    key = (id(node), width, in_section_levels, owner_level)
    hit = memo.get(key) if memo is not None else None
    if hit is None:
        hit = (
            node,
            _card_sized(
                node, width, node_index, fonts, theme, in_section_levels, owner_level
            ),
        )
        if memo is not None:
            memo[key] = hit
    # A piece of a card in a grid row takes the slot its twins share (render_slots).
    return render_slots.lift(node, width, hit[1])


def _card_sized(
    node: LayoutNode,
    width: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme | None,
    in_section_levels: frozenset[int],
    owner_level: int,
) -> float:
    """The content's height, or a baked image card's own when its picture asks
    for more (``image_card_height``, read at the card's outer width)."""
    h = _natural_height_uncached(
        node, width, node_index, fonts, theme, in_section_levels, owner_level
    )
    if not (node.render_properties or {}).get("photo_sized"):
        return h
    pad = _layers_pad(_wrap_layers(node, theme or Theme(), frozenset()))
    return max(h, image_card_height(node.card_bg_url, width + pad.x) - pad.y)


def _natural_height_uncached(
    node: LayoutNode,
    width: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme | None = None,
    in_section_levels: frozenset[int] = frozenset(),
    owner_level: int = 0,
) -> float:
    """Recursively compute the content-fitted height of a layout subtree.

    ``in_section_levels`` carries the heading levels whose section background an
    ancestor has already opened, so a section is wrapped (padded) only at its
    outermost occurrence — must mirror ``place_boxes`` exactly.
    """
    if node.type == "layout":
        if not node.children:
            return 0.0
        # The document body is a single child, and it IS a section whenever the
        # grouper flagged it as one (a doc whose whole body is one heading).
        # Reserve its wrap padding exactly like the col branch below.
        _t = theme or Theme()
        child = node.children[0]
        child_owner = _child_owner_level(child, _t, owner_level)
        layers = _wrap_layers(child, _t, in_section_levels)
        if layers:
            tpad = _layers_pad(layers)
            slvl = _layers_section_level(layers)
            child_levels = in_section_levels | ({slvl} if slvl else frozenset())
            return (
                natural_height(
                    child,
                    max(0.0, width - tpad.x),
                    node_index,
                    fonts,
                    theme,
                    child_levels,
                    child_owner,
                )
                + tpad.y
            )
        return natural_height(
            child,
            width,
            node_index,
            fonts,
            theme,
            in_section_levels,
            child_owner,
        )

    if node.type == "-":
        nd = node_index.get(node.content_id) if node.content_id else None
        return _leaf_height(
            nd,
            width,
            fonts,
            theme,
            node.render_properties,
        )

    if node.type == "row":
        _placements, row_h, _gaps = _layout_row(
            node,
            width,
            node_index,
            fonts,
            theme,
            None,
            in_section_levels,
            owner_level,
        )
        return row_h

    if node.type == "col":
        _t = theme or Theme()
        if getattr(node, "card_kind", None) == "ring":
            # A ring reserves its fixed theme diameter (square).
            return _t.datapoints.ring.diameter
        if getattr(node, "table", False):
            # Table subtree: the TablePlan owns the full geometry.
            return _table_plan(node, width, node_index, fonts, _t).height
        children = _padded_children(node)
        heights = []
        for c in children:
            child_owner = _child_owner_level(c, _t, owner_level)
            layers = _wrap_layers(c, _t, in_section_levels)
            if layers:
                # Section/card wrap layers: content at the reduced inner width,
                # extended by the summed TLRB paddings (applied by the parent).
                tpad = _layers_pad(layers)
                slvl = _layers_section_level(layers)
                child_levels = in_section_levels | ({slvl} if slvl else frozenset())
                heights.append(
                    natural_height(
                        c,
                        width - tpad.x,
                        node_index,
                        fonts,
                        theme,
                        child_levels,
                        child_owner,
                    )
                    + tpad.y
                )
            else:
                heights.append(
                    natural_height(
                        c,
                        width,
                        node_index,
                        fonts,
                        theme,
                        in_section_levels,
                        child_owner,
                    )
                )
        # Per-boundary col gaps owned by the enclosing section (owner_level) —
        # must mirror place_boxes exactly.
        gaps = sum(
            _sibling_gap(
                children[i - 1], children[i], _t, "col", owner_level, node_index, node
            )[0]
            for i in range(1, len(children))
        )
        return sum(heights) + gaps

    return 0.0


def _leaf_natural_width(
    nd: dict | None,
    available: float,
    fonts: FontSet,
    theme: Theme | None = None,
    render_properties: dict | None = None,
) -> float:
    """Width a leaf wants to occupy, capped at ``available`` (box hugs content).

    Mirrors ``_leaf_height``: images keep their allocated width (never
    collapsed), links size to their pill, rules span the full width, and text is
    measured on a single line with the *same* fonts, sizes, and word-by-word
    metrics the drawer uses — so a collapsed box never clips its content.
    """
    _t = theme or Theme()
    nd = _effective_leaf_node(nd, render_properties)
    sp = (render_properties or {}).get("spacer")
    if sp is not None:
        # A spacer across a line is exactly its size; one down a column is
        # height only, so it asks for no width: a cell or card holding it still
        # fits its content (``:::0``, a packed row), and a column stretches it.
        if sp.get("axis") == "row":
            return min(max(0.0, float(sp.get("size") or 0.0)), available)
        return 0.0
    lm = (render_properties or {}).get("list_marker")
    if lm is not None:
        # Marker leaf: the bare glyph/shape. ``Space`` is NOT part of the cell —
        # _sibling_gap inserts it between marker and content in either axis.
        if (
            not lm.get("aside", True)
            and lm.get("kind") == "quote"
            and lm.get("mode") == "bar"
        ):
            return min(float(lm.get("bar_length", 50.0)), available)
        if _is_text_marker(lm):
            # Measured with the marker's own (possibly bold) face — the same
            # font _draw_list_marker draws with, so a wide ordinal like "10"
            # never under-reserves the gutter and overlaps the content.
            font, _size = _marker_font(lm, fonts, _t)
            return min(_text_ink(lm.get("text") or "", font)[2], available)
        return min(float(lm.get("size", 0.0)), available)
    sep = (render_properties or {}).get("separator")
    if sep is not None:
        if sep.get("kind") == "rule":
            return min(_t.vertical_rule.stroke_width, available)
        font = _span_font(fonts, _t.text.font_size, False, False)
        return min(font.measureText(sep.get("char") or ""), available)
    _rp = render_properties or {}
    if _rp.get("datapoint_bar") is not None:
        # The bar is the stretch member: claiming the full width forces its
        # row into the ratio branch, where the generator's [text_w, remainder]
        # ratios apply; as a col child it simply spans the column.
        return available
    if _rp.get("ring_role") is not None:
        # A ring text leaf (baked value/unit), as wide as render_ring_text laid
        # it out inside the ring.
        return min(ring_text(_rp, fonts, _t).width, available)
    if _rp.get("chart") is not None or _rp.get("line_chart") is not None:
        return available  # charts span their column
    if nd is None:
        return available

    node_type = nd.get("type", "")

    if node_type == "drawing_element":
        kind = (nd.get("drawing_element") or {}).get("kind")
        if kind == "slider" and _t.datapoints.sliders.enabled:
            return min(leaf_slider_size(nd, _t)[0], available)
        if _t.datapoints.task_controls.enabled:
            return min(task_control_size(_t)[0], available)

    if node_type == "image":
        # Images are never collapsed — keep their allocated width.
        return _image_content_width(render_properties, available)

    if node_type == "link":
        _variant, label, is_emoji, style = _resolve_link(nd, _t)
        size = (style.text_style or TextStyle()).font_size
        font, runs, e_tf = link_label_fonts(nd, label, fonts, _t, size)
        pill_w, _pill_h = _link_pill_size(runs, style, font, size, e_tf, is_emoji)
        return min(pill_w, available)

    if node_type == "emoji":
        return min(_emoji_leaf_size(nd, fonts, _t)[0], available)

    if node_type == "inline_code":
        # Padded rounded box (like a link): text + L/R padding + the two corner insets.
        label = nd.get("content", "").strip().strip("`")
        font, ic_size = _code_font(_t, nd.get("code_variant"), fonts.mono)
        inline_tf = fonts.chip_emoji(nd.get("code_variant"), _t)
        _code = _t.inline_code.resolved(nd.get("code_variant"))
        metrics = font.getMetrics()
        code_w, _h, _r, _l, _rp = _chip_metrics(
            _code,
            _link_label_width(label, font, ic_size, inline_tf),
            metrics.fDescent - metrics.fAscent,
        )
        return min(code_w, available)

    if node_type == "code_block":
        # A block surface spans its column; its unbreakable source-line width
        # is supplied separately to the generator's minimum-width measurer.
        return available

    if node_type in _BREAK_LEAVES:
        return available

    raw_content = nd.get("content", "")
    atx_level, atx_text = nd.get("atx_level", 0), raw_content
    weight = (render_properties or {}).get("content_weight")
    w_scale, _ = _weight_scale_and_color(_t, weight, 0, nd.get("text_style"))
    eff_fonts, base_size = _effective_text_fonts(
        node_type,
        atx_level,
        fonts,
        _t,
        node=nd,
    )
    size = base_size * w_scale
    eff_fonts, size, _ = _apply_kv_role(
        render_properties,
        eff_fonts,
        size,
        0,
        _t,
        fonts,
        node=nd,
    )
    eff_fonts, size, _ = _apply_date_role(
        render_properties, eff_fonts, size, 0, _t, fonts
    )
    atx_text = _date_role_content(render_properties, atx_text)

    # Unwrapped single-line width, measured exactly as the drawer renders it.
    measured = _line_width(_explode_words(atx_text), eff_fonts, size)
    return min(measured, available)


def natural_width(
    node: LayoutNode,
    available: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme | None = None,
    in_section_levels: frozenset[int] = frozenset(),
    owner_level: int = 0,
) -> float:
    """Content-fitted width of a layout subtree, capped at ``available``.

    Leaves collapse to their content (except images, which keep their allocated
    width); a ``col`` is as wide as its widest child; a ``row`` is the gap-aware
    sum of its children's collapsed widths.

    ``in_section_levels`` carries the heading levels whose section wrap an ancestor
    already opened, so a wrapped child reserves its section/card padding only at its
    outermost occurrence — must mirror ``natural_height`` / ``place_boxes`` exactly.
    """
    if node.type == "layout":
        if not node.children:
            return 0.0
        # Mirrors natural_height / place_boxes: the body child reserves its own
        # section/card wrap padding when it opens one.
        _t0 = theme or Theme()
        body = node.children[0]
        body_owner = _child_owner_level(body, _t0, owner_level)
        layers = _wrap_layers(body, _t0, in_section_levels)
        if layers:
            tpad = _layers_pad(layers)
            slvl = _layers_section_level(layers)
            body_levels = in_section_levels | ({slvl} if slvl else frozenset())
            return (
                natural_width(
                    body,
                    max(0.0, available - tpad.x),
                    node_index,
                    fonts,
                    theme,
                    body_levels,
                    body_owner,
                )
                + tpad.x
            )
        return natural_width(
            body,
            available,
            node_index,
            fonts,
            theme,
            in_section_levels,
            body_owner,
        )

    if node.type == "-":
        nd = node_index.get(node.content_id) if node.content_id else None
        return _leaf_natural_width(
            nd,
            available,
            fonts,
            theme,
            node.render_properties,
        )

    if node.type == "row":
        _t = theme or Theme()
        if getattr(node, "grid", False) or getattr(node, "bento", False):
            # Grid and bento rows stretch to fill their available width.
            return available
        if getattr(node, "spring", False):
            # A row holding a markdown ``...`` spring is an authored request to
            # push its cells to opposite edges, so it stretches for the same
            # reason a grid does: collapsed to its content width there would be
            # no slack left for the spring to open, and the regions would sit
            # flush against each other wherever this row is nested.
            return available
        if getattr(node, "column_row", False):
            # An authored ``:::`` row, and the same reason again: its cells are
            # proportioned by weights the author wrote, and there is nothing to
            # proportion once the row has collapsed to exactly what its content
            # fills.
            return available
        children, _ratio_widths, desired = _row_desired_widths(
            node,
            available,
            node_index,
            fonts,
            _t,
            in_section_levels,
            owner_level,
        )
        # Per-pair row gaps owned by the enclosing section — matches _layout_row.
        gaps = sum(
            _sibling_gap(
                children[i - 1], children[i], _t, "row", owner_level, node_index, node
            )[0]
            for i in range(1, len(children))
        )
        content_width = sum(desired) + gaps
        return min(content_width, available)

    if node.type == "col":
        _t = theme or Theme()
        if getattr(node, "card_kind", None) == "ring":
            return min(_t.datapoints.ring.diameter, available)
        if getattr(node, "table", False):
            return min(
                _table_plan(node, available, node_index, fonts, _t).width,
                available,
            )
        children = _padded_children(node)
        widths: list[float] = []
        for c in children:
            child_owner = _child_owner_level(c, _t, owner_level)
            layers = _wrap_layers(c, _t, in_section_levels)
            if layers:
                # Reserve content + wrap padding so a wrapped child's cell is as wide
                # as its content once place_boxes carves the padding back out. Mirrors
                # natural_height's col branch (which adds tpad.y).
                tpad = _layers_pad(layers)
                slvl = _layers_section_level(layers)
                child_levels = in_section_levels | ({slvl} if slvl else frozenset())
                widths.append(
                    natural_width(
                        c,
                        max(0.0, available - tpad.x),
                        node_index,
                        fonts,
                        _t,
                        child_levels,
                        child_owner,
                    )
                    + tpad.x
                )
            else:
                widths.append(
                    natural_width(
                        c,
                        available,
                        node_index,
                        fonts,
                        _t,
                        in_section_levels,
                        child_owner,
                    )
                )
        return min(max(widths, default=0.0), available)

    return 0.0


def _is_bar_marker(child: LayoutNode) -> bool:
    """True when ``child`` is a blockquote *bar* gutter marker leaf.

    Bar markers stretch to the full row height (like images), so the rule spans
    the whole quote; shape/number/char markers keep their own first-line height.
    """
    if child.type != "-" or not child.render_properties:
        return False
    lm = child.render_properties.get("list_marker")
    if bool(lm) and lm.get("mode") == "bar" and lm.get("aside", True):
        return True
    # A ` | ` painted as a vertical rule (## Vertical Rule) has the same need:
    # it is a line down the row, so it must span the row's height, not the
    # first line's. Same shape, same path.
    sep = child.render_properties.get("separator")
    return bool(sep) and sep.get("kind") == "rule"


def _is_row_spacer(child: LayoutNode) -> bool:
    """True when ``child`` is a spacer across a line (ADR-203)."""
    sp = (child.render_properties or {}).get("spacer")
    return child.type == "-" and sp is not None and sp.get("axis") == "row"


def _row_desired_widths(
    node: LayoutNode,
    available: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme | None = None,
    in_section_levels: frozenset[int] = frozenset(),
    owner_level: int = 0,
) -> tuple[list, list, list]:
    """Per-child desired widths for a row.

    Returns ``(children, ratio_widths, desired)``. Uncapped images keep their
    ratio-allocated share; a ``max_width`` image collapses to that cap like its
    painted content. Every other child collapses to its
    ``natural_width``, plus its section/card wrap padding so the reserved cell is
    as wide as its content once ``place_boxes`` carves that padding back out.
    ``ratio_widths`` is the layout-generator approximation, used as the image
    reserve and the overflow fallback.
    """
    _t = theme or Theme()
    children = _padded_children(node)
    ratios = node.ratios if node.ratios else [1.0] * len(children)
    zero_cells = (
        [i for i, r in enumerate(ratios) if not r]
        if getattr(node, "column_row", False)
        else []
    )
    # A rule fills whatever width its cell is given, so it never sizes a ``:::0``
    # cell: the rest of the cell does. The cell still draws it.
    sized = [
        _without_rules(c, node_index) if i in zero_cells else c
        for i, c in enumerate(children)
    ]
    if zero_cells:
        # A ``:::0`` cell takes no share of the SURPLUS, which is not the same as
        # taking no width. Measure every cell at an EQUAL share first — a zero
        # cell measured against its own zero share reports zero, which is how a
        # width-capped image ends up sized against 0px and divides by zero in
        # ``draw_image_box`` — then reserve the zero cells that honest width and
        # split what is left among the weighted ones.
        _, _, honest = _row_desired_widths(
            dataclasses.replace(
                node, children=sized, ratios=[1.0] * len(children), column_row=False
            ),
            available,
            node_index,
            fonts,
            theme,
            in_section_levels,
            owner_level,
        )
        reserved = sum(honest[i] for i in zero_cells)
        share = max(0.0, available - reserved)
        weighted = sum(ratios) or 1.0
        ratio_widths = [
            honest[i] if not r else (share * r) / weighted for i, r in enumerate(ratios)
        ]
    else:
        total = sum(ratios) or 1.0
        ratio_widths = [(available * r) / total for r in ratios]
    desired: list = []
    for child, rw in zip(sized, ratio_widths):
        if _is_image_leaf(child, node_index):
            desired.append(_image_content_width(child.render_properties, rw))
            continue
        if (child.render_properties or {}).get("fill_row"):
            # A cell of a packed row the generator sized to fill its line.
            # Collapsing it back to its content would put the hole straight back,
            # so it keeps the share it was given, the way an uncapped image does.
            desired.append(rw)
            continue
        child_owner = _child_owner_level(child, _t, owner_level)
        layers = _wrap_layers(child, _t, in_section_levels)
        if layers:
            # Reserve content + wrap padding, so place_boxes' _emit_wrap_boxes can
            # carve the padding back out and leave exactly the measured content width.
            tpad = _layers_pad(layers)
            slvl = _layers_section_level(layers)
            child_levels = in_section_levels | ({slvl} if slvl else frozenset())
            nw = (
                natural_width(
                    child,
                    max(0.0, available - tpad.x),
                    node_index,
                    fonts,
                    _t,
                    child_levels,
                    child_owner,
                )
                + tpad.x
            )
        else:
            nw = natural_width(
                child,
                available,
                node_index,
                fonts,
                _t,
                in_section_levels,
                child_owner,
            )
        desired.append(min(nw, available))
    return children, ratio_widths, desired


def _without_rules(node: LayoutNode, node_index: dict) -> LayoutNode:
    """*node* with its ``---`` rules left out, to measure what else it holds."""
    if not node.children:
        return node
    keep = [
        i
        for i, c in enumerate(node.children)
        if (node_index.get(c.content_id) or {}).get("type") != "horizontal_rule"
    ]
    ratios = node.ratios
    if ratios and len(ratios) == len(node.children):
        ratios = [ratios[i] for i in keep]  # or the gap is padded back as a leaf
    children = [_without_rules(node.children[i], node_index) for i in keep]
    return dataclasses.replace(node, children=children, ratios=ratios)


def _cell_floor(
    node: LayoutNode,
    node_index: dict,
    theme: Theme,
    in_section_levels: frozenset[int],
    owner_level: int,
    leaf: Callable[[LayoutNode], float] | None = None,
) -> float:
    """The least width a row may give *node* so that every leaf in it keeps its
    own floor -- *leaf*'s answer, by default an image's ``min_width`` -- plus each
    wrap's padding on the way down, reserved the way ``natural_width`` reserves
    it. A lower bound where leaves sit side by side inside the cell."""
    layers = _wrap_layers(node, theme, in_section_levels)
    pad, levels = 0.0, in_section_levels
    if layers:
        pad = _layers_pad(layers).x
        slvl = _layers_section_level(layers)
        levels = in_section_levels | ({slvl} if slvl else frozenset())
    if leaf is not None and not node.children:
        inner = leaf(node)
    elif _is_image_leaf(node, node_index):
        inner = image_floor(node.render_properties) or 0.0
    else:
        owner = _child_owner_level(node, theme, owner_level)
        inner = max(
            (
                _cell_floor(c, node_index, theme, levels, owner, leaf)
                for c in node.children
            ),
            default=0.0,
        )
    return inner + pad if inner else 0.0


def _give_elements_room(
    widths: list,
    children: list,
    ratios: list,
    node_index: dict,
    fonts: FontSet,
    theme: Theme,
    in_section_levels: frozenset[int],
    owner_level: int,
) -> None:
    """Give each weighted cell of a `:::` row at least its widest pill or word,
    in place. A button's label never wraps, so the room comes out of the
    ``:::0`` cells that hold only pictures: a picture flexes down to the floor
    the generator's fit test held it at, and the row wraps only below that."""

    def floor(cell: LayoutNode, leaf: Callable[[LayoutNode], float]) -> float:
        return _cell_floor(
            cell, node_index, theme, in_section_levels, owner_level, leaf
        )

    def element(n: LayoutNode) -> float:
        nd = node_index.get(n.content_id) if n.content_id else None
        # A code block is a surface, not an element: a line wider than its box
        # clips and scrolls, so nothing in it is kept whole here.
        if not nd or nd.get("type") in ("image", "code_block", *_BREAK_LEAVES):
            return 0.0
        return _table_cell_min_width(n, node_index, fonts, theme, math.inf)

    def picture(n: LayoutNode) -> float:
        if not _is_image_leaf(n, node_index):
            return math.inf  # anything else in the cell keeps it whole
        rp = n.render_properties
        own = image_floor(rp) or IMAGE_MIN_WIDTH
        cap = image_width_cap(rp)
        return min(own, float(cap)) if cap else own

    give = {j: floor(c, picture) for j, c in enumerate(children) if not ratios[j]}
    for i, cell in enumerate(children):
        short = floor(cell, element) - widths[i] if ratios[i] else 0.0
        for j, least in give.items():
            room = min(short, widths[j] - least)
            if room > 0:
                widths[j] -= room
                widths[i] += room
                short -= room


def _is_width_capped(node: LayoutNode) -> bool:
    """Whether an image leaf asks its layout box not to stretch."""
    return image_width_cap(node.render_properties) is not None


def _stretch_bento_placements(placements: list, height: float) -> list:
    """Stretch a bento band except for explicitly capped image allocations."""
    return [
        (child, x, width, natural_h if _is_width_capped(child) else height, dy)
        for child, x, width, natural_h, dy in placements
    ]


def _cell_heights(
    children: list,
    widths: list,
    node_index: dict,
    fonts: FontSet,
    theme: Theme,
    in_section_levels: frozenset[int],
    owner_level: int,
) -> tuple[list, list]:
    """Wrap-layer-aware natural heights for row/col cells at the given widths.

    Returns ``(heights, is_section_cell)``: a wrapped (section/card) cell is
    measured at the padding-reduced inner width and extended by the summed TLRB
    paddings; ``is_section_cell`` flags wrapped cells (they fill their row).
    Shared by ``_layout_row`` / ``_layout_grid_row`` / ``_layout_bento_row``.
    """
    heights: list = []
    is_section_cell: list = []
    for child, w in zip(children, widths):
        child_owner = _child_owner_level(child, theme, owner_level)
        layers = _wrap_layers(child, theme, in_section_levels)
        if layers:
            tpad = _layers_pad(layers)
            slvl = _layers_section_level(layers)
            child_levels = in_section_levels | ({slvl} if slvl else frozenset())
            heights.append(
                natural_height(
                    child,
                    w - tpad.x,
                    node_index,
                    fonts,
                    theme,
                    child_levels,
                    child_owner,
                )
                + tpad.y
            )
            is_section_cell.append(True)
        else:
            heights.append(
                natural_height(
                    child,
                    w,
                    node_index,
                    fonts,
                    theme,
                    in_section_levels,
                    child_owner,
                )
            )
            is_section_cell.append(False)
    return heights, is_section_cell


# How far a table's horizontal chrome (per-cell label padding.x + column
# gaps) may compress before the plan gives up on fitting the grid inside its
# container (stacking-cards, else overflow). 0.5 = chrome shrinks to half;
# glyph/pill widths never shrink, at this floor or past it.
TABLE_SQUEEZE_FLOOR = 0.5


@dataclasses.dataclass
class TablePlan:
    """Full geometry of one table subtree, in table-local coordinates.

    The single source of truth shared by ``natural_height``, ``natural_width``
    and ``_place_table_boxes`` so measurement and paint always agree.

    ``mode`` is "grid" (column-aligned rows) or "cards" (stacking-cards
    fallback). ``row_boxes`` are the header/body row (or card) background
    rects as ``(kind, x, y, w, h)``; ``cells`` are the content placements as
    ``(cell_node, x, y, w, h, rp_extra)`` (rects already inset by the cell
    padding); ``keys`` are stacking-mode key labels as
    ``(text, x, y, w, h, row_index)``.
    ``shell`` is the merged-mode whole-table rect or None.
    """

    mode: str
    width: float
    height: float
    shell: tuple[float, float, float, float] | None
    row_boxes: list
    cells: list
    keys: list


def _table_cell_pad(theme: Theme, role: str) -> "PaddingBox":
    """Per-cell label padding for a table cell role."""
    return (theme.tables.header if role == "header" else theme.tables.cells).padding


def _beside_spacer_floor(
    cell: LayoutNode,
    desired: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme,
    available: float,
) -> float:
    """How narrow *cell* may go before the row spacers beside it give way
    (ADR-203): its widest word, and for prose its length category's floor — the
    width that text needs to read. A long paragraph has no floor short of its
    whole line: it goes full width, so its spacers always give way. A block
    held between two spacers floors at the minimum the generator found for it."""
    held = (cell.render_properties or {}).get("held_floor")
    if held is not None:
        return min(desired, held)
    word = _table_cell_min_width(cell, node_index, fonts, theme, available)
    nd = node_index.get(cell.content_id) if cell.content_id else None
    category = (nd or {}).get("content_length_category") or ""
    floor = desired if category == "long_paragraph" else LEAF_WIDTH.get(category, 0.0)
    return min(desired, max(word, floor))


def _weighted_need(ratios: list, asks: list, spacers: list) -> float:
    """The width a weighted row needs for every weighted cell to get its ask
    at its share, the spacers and ``:::0`` cells held at theirs."""
    weighted = [i for i, r in enumerate(ratios) if r and i not in spacers]
    total = sum(ratios[i] for i in weighted) or 1.0
    held = sum(a for i, a in enumerate(asks) if i not in weighted)
    return held + max((asks[i] * total / ratios[i] for i in weighted), default=0.0)


def _table_cell_min_width(
    cell: LayoutNode,
    node_index: dict,
    fonts: FontSet,
    theme: Theme,
    available: float,
) -> float:
    """Minimum unbreakable width of one table cell (widest wrap unit / whole pill)."""
    if cell.type != "-":
        return natural_width(cell, available, node_index, fonts, theme)
    nd = node_index.get(cell.content_id) if cell.content_id else None
    if nd is None:
        return 0.0
    node_type = nd.get("type", "")
    if node_type in ("link", "inline_code", "emoji", "image"):
        return _leaf_natural_width(nd, available, fonts, theme, cell.render_properties)
    content = nd.get("content", "")
    if not content:
        return 0.0
    atx_level, atx_text = nd.get("atx_level", 0), content
    eff_fonts, size = _effective_text_fonts(
        node_type,
        atx_level,
        fonts,
        theme,
        node=nd,
    )
    return _widest_unit(_explode_words(atx_text), eff_fonts, size)


def _table_cell_height(
    cell: LayoutNode,
    width: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme,
    rp_extra: dict | None = None,
) -> float:
    """Natural height of one table cell at ``width``, honoring an extra
    render-property overlay (the stacking-cards title weight) on leaves."""
    if cell.type == "-":
        nd = node_index.get(cell.content_id) if cell.content_id else None
        rp = cell.render_properties
        if rp_extra:
            rp = {**(rp or {}), **rp_extra}
        return _leaf_height(nd, width, fonts, theme, rp)
    return natural_height(cell, width, node_index, fonts, theme)


def _table_plan(
    node: LayoutNode,
    available: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme | None = None,
) -> TablePlan:
    """Measure a ``table`` col into a :class:`TablePlan`.

    Grid mode: per-column widths are the max Skia-measured natural (and
    minimum-unbreakable) cell widths across ALL rows, so columns align; the
    surplus of ``available`` is distributed proportionally (the table fills
    its width). When even the minimum widths don't fit: stacking-cards mode
    if the theme enables it, else the grid keeps every column at its
    minimum-unbreakable width and overflows ``available`` — a pill and a word
    are both indivisible, so a narrower cell would only be drawn over.
    """
    _t = theme or Theme()
    tt = _t.tables
    rows = [c for c in node.children if getattr(c, "table_row", None) is not None]
    n_cols = max((len(r.children) for r in rows), default=0)
    if n_cols == 0:
        return TablePlan("grid", 0.0, 0.0, None, [], [], [])

    # Gaps through the single-source _sibling_gap (table rule → element
    # fallback): cells on the row axis, rows on the col axis.
    col_gap = 0.0
    for r in rows:
        if len(r.children) >= 2:
            col_gap = _sibling_gap(
                r.children[0], r.children[1], _t, "row", 0, node_index, r
            )[0]
            break
    row_gap = (
        _sibling_gap(rows[0], rows[1], _t, "col", 0, node_index, node)[0]
        if len(rows) >= 2
        else 0.0
    )
    merged = tt.table.merge_rows and tt.table.is_active()
    shell_pad = tt.table.padding if merged else PaddingBox()
    inner_w = max(1.0, available - shell_pad.x)

    nat = [0.0] * n_cols
    mins = [0.0] * n_cols
    # Split of each column's min into glyph content vs squeezable chrome
    # (per-cell padding.x), tracked as independent per-column maxima so the
    # squeeze total stays LINEAR in the squeeze factor.
    content_min = [0.0] * n_cols
    pad_col = [0.0] * n_cols
    for r in rows:
        role = r.table_row or "body"
        pad = _table_cell_pad(_t, role)
        for j, cell in enumerate(r.children):
            nat[j] = max(
                nat[j],
                natural_width(cell, inner_w, node_index, fonts, _t) + pad.x,
            )
            c_min = _table_cell_min_width(cell, node_index, fonts, _t, inner_w)
            mins[j] = max(mins[j], c_min + pad.x)
            content_min[j] = max(content_min[j], c_min)
            pad_col[j] = max(pad_col[j], pad.x)
    gaps_w = (n_cols - 1) * col_gap
    budget = max(1.0, inner_w - gaps_w)
    sum_nat, sum_min = sum(nat), sum(mins)

    mode = "grid"
    fx = 1.0  # horizontal chrome squeeze factor (cell padding.x + col gaps)
    if sum_nat <= budget:
        extra = budget - sum_nat
        widths = [
            n + (extra * n / sum_nat if sum_nat > 0 else extra / n_cols) for n in nat
        ]
    elif sum_min <= budget:
        denom = sum(n - m for n, m in zip(nat, mins))
        extra = budget - sum_min
        widths = [
            m + (extra * (n - m) / denom if denom > 0 else extra / n_cols)
            for n, m in zip(nat, mins)
        ]
    else:
        # Squeeze stage: before giving up on the grid, compress the
        # horizontal chrome — per-cell padding.x and column gaps — down to
        # TABLE_SQUEEZE_FLOOR. Glyph/pill widths and vertical padding never
        # shrink. total(f) = Σcontent + f·(Σpad + gaps) is linear in f.
        chrome = sum(pad_col) + gaps_w
        content = sum(content_min)
        f = (inner_w - content) / chrome if chrome > 0 else 0.0
        if f >= TABLE_SQUEEZE_FLOOR:
            fx = min(1.0, f)
            widths = [c + fx * p for c, p in zip(content_min, pad_col)]
        elif tt.stacking:
            mode = "cards"
            widths = []
        else:
            # Overflow without stacking: squeeze the chrome to its floor and
            # then STOP. A column is never narrower than its widest
            # unbreakable unit — a whole pill, a whole word — because neither
            # shrinks at draw time, so a cell scaled past that floor is drawn
            # over by its own content (this is what made calendar chips
            # overlap). The table overflows its container instead, the way a
            # too-long word does.
            fx = TABLE_SQUEEZE_FLOOR
            widths = [c + fx * p for c, p in zip(content_min, pad_col)]

    if mode == "grid":
        gap_eff = col_gap * fx
        gaps_w_eff = (n_cols - 1) * gap_eff
        row_boxes: list = []
        cells: list = []
        row_w = sum(widths) + gaps_w_eff
        y = shell_pad.top
        x0 = shell_pad.left
        body_index = 0
        for i, r in enumerate(rows):
            if i > 0:
                y += row_gap
            role = r.table_row or "body"
            pad = _table_cell_pad(_t, role)
            pad_fx = fx  # squeezed horizontal padding factor
            content_h = 0.0
            placements = []
            cx = x0
            for j, cell in enumerate(r.children):
                w_in = max(1.0, widths[j] - pad_fx * pad.x)
                ch = _table_cell_height(cell, w_in, node_index, fonts, _t)
                content_h = max(content_h, ch)
                placements.append((cell, cx + pad_fx * pad.left, w_in))
                cx += widths[j] + gap_eff
            kind = "table_header" if role == "header" else "table_row"
            bg_index = 0 if role == "header" else body_index
            row_boxes.append((kind, x0, y, row_w, content_h + pad.y))
            for cell, cell_x, w_in in placements:
                cells.append(
                    (
                        cell,
                        cell_x,
                        y + pad.top,
                        w_in,
                        content_h,
                        {"table_bg_index": bg_index},
                    )
                )
            if role != "header":
                body_index += 1
            y += content_h + pad.y
        total_h = y + shell_pad.bottom
        shell = (0.0, 0.0, row_w + shell_pad.x, total_h) if merged else None
        return TablePlan(
            "grid", row_w + shell_pad.x, total_h, shell, row_boxes, cells, []
        )

    # ---- stacking-cards mode -------------------------------------------
    header = next((r for r in rows if r.table_row == "header"), None)
    key_texts: list[str] = []
    if header is not None:
        for cell in header.children:
            nd = node_index.get(cell.content_id) if cell.content_id else None
            key_texts.append((nd or {}).get("content", ""))
    body_rows = [r for r in rows if r.table_row != "header"]
    card_pad = tt.cells.padding
    inner_cw = max(1.0, available - card_pad.x)
    key_fonts, key_size, _key_color = _table_key_fonts(fonts, _t)
    key_h = key_size * LINE_SCALE
    key_w = min(
        max(
            (
                _line_width(_explode_words(t), key_fonts, key_size)
                for t in key_texts
                if t
            ),
            default=0.0,
        ),
        TABLE_KEY_COL_MAX_SHARE * inner_cw,
    )
    v = tt.table.col_spacing
    card_gap = v if v is not None else _resolve_element_spacing("col", _t)
    pair_gap = _resolve_element_spacing("col", _t)
    title_mode = tt.card_layout == "title"

    row_boxes = []
    cells = []
    keys: list = []
    y = 0.0
    for bi, r in enumerate(body_rows):
        if bi > 0:
            y += card_gap
        card_y = y
        cy = card_y + card_pad.top
        cell_list = list(r.children)
        start = 0
        if title_mode and cell_list:
            title_rp = {"content_weight": "first", "table_bg_index": bi}
            th = _table_cell_height(
                cell_list[0], inner_cw, node_index, fonts, _t, title_rp
            )
            cells.append((cell_list[0], card_pad.left, cy, inner_cw, th, title_rp))
            cy += th
            start = 1
        val_x = card_pad.left + key_w + tt.key_spacing
        val_w = max(1.0, inner_cw - key_w - tt.key_spacing)
        for j in range(start, len(cell_list)):
            if j > start or start == 1:
                cy += pair_gap
            vh = _table_cell_height(cell_list[j], val_w, node_index, fonts, _t)
            pair_h = max(key_h, vh)
            key_text = key_texts[j] if j < len(key_texts) else ""
            if key_text:
                keys.append((key_text, card_pad.left, cy, key_w, key_h, bi))
            cells.append(
                (
                    cell_list[j],
                    val_x,
                    cy,
                    val_w,
                    vh,
                    {"table_bg_index": bi},
                )
            )
            cy += pair_h
        card_h = (cy - card_y) + card_pad.bottom
        row_boxes.append(("table_row", 0.0, card_y, available, card_h))
        y = card_y + card_h
    return TablePlan("cards", available, y, None, row_boxes, cells, keys)


def _layout_grid_row(
    node: LayoutNode,
    available: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme | None = None,
    in_section_levels: frozenset[int] = frozenset(),
    owner_level: int = 0,
) -> tuple[list, float, list]:
    """Place a repeated-unit grid row: ``K`` equal columns stretched to fill
    ``available``.

    Every cell gets ``col_w = (available - (K-1)*gap) / K`` and is placed
    left-to-right, so the row fills the width. Only the *real* children are placed
    (``node.grid_cols`` = K may exceed ``len(children)`` for the ragged last row),
    which stays grid-aligned left with no empty placeholder cells. Height logic
    mirrors ``_layout_row``'s tail (wrap-layer aware).
    """
    _t = theme or Theme()
    children = node.children
    K = node.grid_cols or len(children)
    # Uniform per-unit gap (same for full and ragged rows). Passing the cell twice
    # resolves its own kind (section vs group) without needing a real neighbour.
    gap = _sibling_gap(
        children[0], children[0], _t, "row", owner_level, node_index, node
    )[0]
    # A picture cell asked about itself answers with the image gap, which only
    # the pictures-only grid has earned: beside any other cell the real
    # neighbours decide, so one picture cannot pull a mixed grid flush.
    if _is_pure_image_block(children[0], node_index, _t) and not all(
        _is_pure_image_block(c, node_index, _t) for c in children
    ):
        gap = max(
            _sibling_gap(a, b, _t, "row", owner_level, node_index, node)[0]
            for a, b in zip(children, children[1:])
        )
    col_w = max(0.0, (available - (K - 1) * gap) / K)
    widths = [col_w] * len(children)
    offsets = [i * (col_w + gap) for i in range(len(children))]
    # THEME ``Orphan row: Center`` on a RAGGED row (fewer cells than columns):
    # the cells keep a column's width and the space the missing ones would have
    # filled is split either side. Stamped by the generator, which resolves the
    # mode once — ``stretch`` never reaches here because it was settled at build
    # time (a cell is arranged at the width it is given), and ``left`` stamps
    # nothing, so the default costs neither a lookup nor a shift.
    if (node.render_properties or {}).get("orphan_row") == "center" and children:
        used = len(children) * col_w + (len(children) - 1) * gap
        shift = max(0.0, (available - used) / 2.0)
        offsets = [o + shift for o in offsets]

    gap_spans: list = []
    for i in range(1, len(children)):
        start = offsets[i - 1] + widths[i - 1]
        is_sec = _sibling_gap(
            children[i - 1], children[i], _t, "row", owner_level, node_index, node
        )[1]
        gap_spans.append((start, offsets[i] - start, is_sec, owner_level))

    measure = lambda: _cell_heights(  # noqa: E731
        children, widths, node_index, fonts, _t, in_section_levels, owner_level
    )
    is_picture = lambda c: _is_image_leaf(c, node_index)  # noqa: E731
    render_slots.share(children, measure, is_picture, _HEIGHT_MEMO)
    heights, is_section_cell = measure()
    row_h = max(heights) if heights else 0.0
    # A grid row is cards side by side, never one source line: cells stay top
    # aligned, so no baseline shift (the 5th placement element).
    placements = [
        (
            child,
            offset,
            w,
            row_h
            if (
                (_is_image_leaf(child, node_index) and not _is_width_capped(child))
                or sec
                or _is_bar_marker(child)
            )
            else h,
            0.0,
        )
        for child, offset, w, h, sec in zip(
            children, offsets, widths, heights, is_section_cell
        )
    ]
    return placements, row_h, gap_spans


def _layout_bento_row(
    node: LayoutNode,
    available: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme | None = None,
    in_section_levels: frozenset[int] = frozenset(),
    owner_level: int = 0,
) -> tuple[list, float, list]:
    """Place a bento (mosaic) row: ratios are integer grid-span weights honored
    exactly — no content collapse — and EVERY cell stretches to the row height,
    so the Mondrian edges align (surplus reads as bottom padding inside each
    cell's wrap box). Gap and height logic mirror ``_layout_grid_row``.

    Widths use the generator's *grid model* — ``w(t) = t·u + (t−1)·g`` with
    ``u = (available − (Σt−1)·g) / Σt`` and one uniform gap ``g`` — NOT plain
    ratio shares of the remaining width. A span-``t`` band keeps its ``t−1``
    interior gap widths, so the band is exactly as wide as the generator
    promised when it batched the cell's content (ratio shares come out
    ``g·(t·(k−1)−(Σt−t))/Σt`` narrower for multi-span bands and clip
    tight-fitted content by a few px).
    """
    _t = theme or Theme()
    children = node.children
    ratios = node.ratios if node.ratios else [1.0] * len(children)
    total = sum(ratios) or 1.0
    pair_gaps = [
        _sibling_gap(
            children[i - 1], children[i], _t, "row", owner_level, node_index, node
        )[0]
        for i in range(1, len(children))
    ]
    # One uniform gap for the whole row (the generator's span math assumes it);
    # max over the actual pair gaps keeps same-kind rows exact and mixed rows
    # conservative.
    gap = max(pair_gaps, default=0.0)
    unit = max(0.0, (available - (total - 1) * gap) / total)
    widths = [r * unit + (r - 1) * gap for r in ratios]
    # A max-width image is an icon-sized cell, not an empty grid span with a
    # small painting floating inside it. Give the released span to the other
    # cells so the following content starts immediately after the normal gap.
    capped = [
        i
        for i, child in enumerate(children)
        if _is_image_leaf(child, node_index) and _is_width_capped(child)
    ]
    loose = [i for i in range(len(children)) if i not in capped]
    for i in capped:
        capped_w = _image_content_width(children[i].render_properties, widths[i])
        slack = widths[i] - capped_w
        widths[i] = capped_w
        if slack > 0 and loose:
            share = sum(widths[j] for j in loose)
            for j in loose:
                widths[j] += (
                    slack * widths[j] / share if share > 0 else slack / len(loose)
                )
    pair_gaps = [0.0] + [gap] * (len(children) - 1)
    offsets, cx = [], 0.0
    for i, w in enumerate(widths):
        cx += pair_gaps[i]
        offsets.append(cx)
        cx += w

    gap_spans: list = []
    for i in range(1, len(children)):
        if pair_gaps[i] > 0:
            start = offsets[i - 1] + widths[i - 1]
            is_sec = _sibling_gap(
                children[i - 1], children[i], _t, "row", owner_level, node_index, node
            )[1]
            gap_spans.append((start, offsets[i] - start, is_sec, owner_level))

    heights, _sec = _cell_heights(
        children, widths, node_index, fonts, _t, in_section_levels, owner_level
    )
    row_h = max(heights) if heights else 0.0
    # Capped images hug their measured height and remain top-aligned. Other
    # bento cells stretch to the band height so the mosaic edges still align.
    placements = [
        (
            child,
            offset,
            w,
            h
            if _is_image_leaf(child, node_index) and _is_width_capped(child)
            else row_h,
            0.0,
        )
        for child, offset, w, h in zip(children, offsets, widths, heights)
    ]
    return placements, row_h, gap_spans


def _layout_row(
    node: LayoutNode,
    available: float,
    node_index: dict,
    fonts: FontSet,
    theme: Theme | None = None,
    inherited: dict | None = None,
    in_section_levels: frozenset[int] = frozenset(),
    owner_level: int = 0,
) -> tuple[list, float, list]:
    """Compute compacted child placements for a ``row``.

    Returns ``(placements, row_height, gap_spans)`` where each placement is
    ``(child_node, x_offset, width, effective_height)`` and ``gap_spans`` is a
    list of ``(x_offset, width, is_section, owner_level)`` gaps inserted between
    adjacent same-alignment-bucket siblings (empty in the overflow branch);
    ``is_section`` flags the larger between-section gaps and ``owner_level`` is
    the incoming section's heading level, so the debug overlay can color them.
    Non-image children collapse to their content width and pack with a per-pair
    gap — ``section_spacing`` between same-level heading siblings, else
    ``element_spacing``; the freed slack is sent to the edge each child's
    ``content_align`` selects (left packs left, right packs right, center groups
    in the middle). When the collapsed content can't fit (e.g. paragraphs that
    must wrap), it falls back to the layout-generator's ratio distribution —
    preserving the previous behavior.
    """
    _t = theme or Theme()
    if getattr(node, "grid", False) and node.children:
        # Repeated-unit grid: stretch K equal columns to fill `available`
        # (ragged last row grid-aligned left, no empty cells).
        return _layout_grid_row(
            node,
            available,
            node_index,
            fonts,
            _t,
            in_section_levels,
            owner_level,
        )
    if getattr(node, "bento", False) and node.children:
        # Bento mosaic row: exact span-ratio widths, all cells stretch to row_h.
        return _layout_bento_row(
            node,
            available,
            node_index,
            fonts,
            _t,
            in_section_levels,
            owner_level,
        )
    children, ratio_widths, desired = _row_desired_widths(
        node, available, node_index, fonts, _t, in_section_levels, owner_level
    )
    if not children:
        return [], 0.0, []

    gap_spans: list = []

    # Per-pair gaps in document order (section spacing between same-level heading
    # siblings, else element spacing); the fit estimate must account for them so
    # packed items never overflow ``available``.
    gaps_total = sum(
        _sibling_gap(
            children[i - 1], children[i], _t, "row", owner_level, node_index, node
        )[0]
        for i in range(1, len(children))
    )
    content_width = sum(desired) + gaps_total

    # A row that does not fit gives up its spacers first (ADR-203): they
    # shrink together, down to nothing, before any content is narrowed. So a
    # spacer never widens what a row needs, and never squeezes what it holds.
    # "Does not fit" counts a text at its length category's floor, not its
    # one-line width: prose wraps, so a spacer beside a paragraph keeps its
    # space while the paragraph still has the room its length needs to read,
    # and makes way before it is squeezed below that.
    # In a weighted row a cell is narrowed as soon as its share is under its
    # line, even when the row's content would fit, so there the spacers give
    # way before any share is. A run's rows follow the pin their run settled
    # (``spacers``), not their own room.
    spacers = [i for i, c in enumerate(children) if _is_row_spacer(c)]
    row_ratios = list(node.ratios) if node.ratios else [1.0] * len(children)
    pin = (node.render_properties or {}).get("spacers")
    weighted = getattr(node, "column_row", False)
    if spacers and pin != "keep" and (pin or weighted or content_width > available):
        floors = [
            desired[i]
            if i in spacers or weighted
            else _beside_spacer_floor(
                children[i], desired[i], node_index, fonts, _t, available
            )
            for i in range(len(children))
        ]
        need = gaps_total + (
            _weighted_need(row_ratios, floors, spacers) if weighted else sum(floors)
        )
        need = math.inf if pin == "give_way" else need
        desired = list(desired)
        room = sum(desired[i] for i in spacers)
        cut = min(max(0.0, need - available), room)
        for i in spacers:
            desired[i] -= desired[i] * cut / room if room > 0 else 0.0
        content_width -= cut
        if need - cut > available:
            # Given way entirely and still too wide: the spacers leave the row,
            # and the gaps they stood between with them.
            keep = [i for i in range(len(children)) if i not in spacers]
            children = [children[i] for i in keep]
            desired = [desired[i] for i in keep]
            ratio_widths = [ratio_widths[i] for i in keep]
            row_ratios = [row_ratios[i] for i in keep]
            gaps_total = sum(
                _sibling_gap(
                    children[i - 1],
                    children[i],
                    _t,
                    "row",
                    owner_level,
                    node_index,
                    node,
                )[0]
                for i in range(1, len(children))
            )
            content_width = sum(desired) + gaps_total

    # An authored ``:::`` row always distributes by ratio. The packed branch
    # below ignores ``ratios`` outright — it collapses every cell to its content
    # and packs by ``content_align`` — so a row whose content happens to fit
    # would silently throw the author's weights away. Everything else packs
    # when it fits and proportions when it does not.
    if content_width <= available and not getattr(node, "column_row", False):
        widths = desired
        # Bucket children by effective horizontal alignment, preserving order.
        buckets: dict[str, list[int]] = {"left": [], "center": [], "right": []}
        for idx, child in enumerate(children):
            rp = child.render_properties or {}
            align = (
                rp.get("content_align")
                or (inherited or {}).get("content_align")
                or _t.root.align
                or "left"
            )
            buckets.get(align, buckets["left"]).append(idx)

        def _bucket_gap(prev_idx: int, idx: int) -> float:
            return _sibling_gap(
                children[prev_idx],
                children[idx],
                _t,
                "row",
                owner_level,
                node_index,
                node,
            )[0]

        offsets = [0.0] * len(children)
        cx = 0.0
        prev: int | None = None
        for idx in buckets["left"]:
            if prev is not None:
                cx += _bucket_gap(prev, idx)
            offsets[idx] = cx
            cx += widths[idx]
            prev = idx
        rx = available
        prev = None
        for idx in reversed(buckets["right"]):
            if prev is not None:
                rx -= _bucket_gap(idx, prev)
            rx -= widths[idx]
            offsets[idx] = rx
            prev = idx
        if buckets["center"]:
            center = buckets["center"]
            center_gaps = sum(
                _bucket_gap(center[k - 1], center[k]) for k in range(1, len(center))
            )
            block = sum(widths[i] for i in center) + center_gaps
            cx = (available - block) / 2
            # Centred, but never over its neighbours: the block keeps a gap
            # clear of the left bucket's end and of the right bucket's start.
            # Everything fits here, gaps included, so both bounds hold at once.
            if buckets["right"]:
                first_right = buckets["right"][0]
                hi = offsets[first_right] - _bucket_gap(center[-1], first_right)
                cx = min(cx, hi - block)
            if buckets["left"]:
                last_left = buckets["left"][-1]
                lo = offsets[last_left] + widths[last_left]
                cx = max(cx, lo + _bucket_gap(last_left, center[0]))
            prev = None
            for idx in center:
                if prev is not None:
                    cx += _bucket_gap(prev, idx)
                offsets[idx] = cx
                cx += widths[idx]
                prev = idx
        # Gaps: the space between consecutive same-bucket items, tagged by kind
        # and (for section gaps) the owner = incoming child's section level.
        for bucket in buckets.values():
            ordered = sorted(bucket, key=lambda i: offsets[i])
            for a, b in zip(ordered, ordered[1:]):
                start = offsets[a] + widths[a]
                is_section = _sibling_gap(
                    children[a], children[b], _t, "row", owner_level, node_index, node
                )[1]
                gap_spans.append((start, offsets[b] - start, is_section, owner_level))
    else:
        # Overflow: distribute by ratio, but still inset per-pair gaps so
        # same-level sections (and elements) stay separated instead of abutting.
        # The ratio widths (which fill ``available``) are scaled down to leave
        # room for the gaps, then placed sequentially with them.
        pair_gaps = [0.0] + [
            _sibling_gap(
                children[i - 1], children[i], _t, "row", owner_level, node_index, node
            )[0]
            for i in range(1, len(children))
        ]
        total_gaps = sum(pair_gaps)
        scale = max(0.0, available - total_gaps) / available if available > 0 else 0.0
        widths = [w * scale for w in ratio_widths]
        if getattr(node, "column_row", False):
            # Authored weights, resolved against the width left after the gaps
            # rather than scaled down from a full-width share. A cell weighted
            # ``0`` is pinned to what its content measured and takes no part in
            # the split — scaling it, as the line above does, would shave it
            # below its own content for the sake of the gaps.
            ratios = row_ratios
            room = max(0.0, available - total_gaps)
            zero = [i for i, r in enumerate(ratios) if not r]
            share = max(0.0, room - sum(desired[i] for i in zero))
            weighted = sum(r for r in ratios if r) or 1.0
            widths = [
                desired[i] if not r else (share * r) / weighted
                for i, r in enumerate(ratios)
            ]
        # A fixed aside cell — a gutter marker, an icon placed aside, or an
        # explicitly width-capped image — is a
        # column, not a share: scaling its ratio would grow it with the row (a
        # 60px ordinal claiming 96px at one width and more at the next),
        # squeezing the content beside it. Pin it to its measured width and
        # hand the slack to the siblings.
        fixed = [
            i
            for i, c in enumerate(children)
            if (c.render_properties or {}).get("list_marker")
            or (c.render_properties or {}).get("aside_fixed")
            # …and a spacer, already shrunk to nothing above: a ratio share
            # would grow it with the row while the content beside it squeezes.
            or _is_row_spacer(c)
            or (
                _is_image_leaf(c, node_index)
                and image_width_cap(c.render_properties) is not None
            )
        ]
        loose = [i for i in range(len(children)) if i not in fixed]
        for i in fixed:
            slack = widths[i] - desired[i]
            if slack <= 0 or not loose:
                continue
            widths[i] = desired[i]
            share = sum(widths[j] for j in loose)
            for j in loose:
                widths[j] += (
                    slack * widths[j] / share if share > 0 else slack / len(loose)
                )
        # An image's ``min_width`` is a floor: a share below it is raised, and
        # the difference comes out of the cells that are not pinned. Only an
        # authored ``:::`` row splits by weight, so only it can undercut one.
        floored = children if getattr(node, "column_row", False) else []
        for i, c in enumerate(floored):
            floor = _cell_floor(c, node_index, _t, in_section_levels, owner_level)
            rest = [j for j in loose if j != i]
            short = floor - widths[i]
            if not floor or short <= 0 or not rest:
                continue
            widths[i] = floor
            share = sum(widths[j] for j in rest)
            for j in rest:
                widths[j] -= (
                    short * widths[j] / share if share > 0 else short / len(rest)
                )
        if floored:
            _give_elements_room(
                widths,
                children,
                row_ratios,
                node_index,
                fonts,
                _t,
                in_section_levels,
                owner_level,
            )
        offsets, cx = [], 0.0
        for i, w in enumerate(widths):
            cx += pair_gaps[i]
            offsets.append(cx)
            cx += w
        for i in range(1, len(children)):
            if pair_gaps[i] > 0:
                start = offsets[i - 1] + widths[i - 1]
                is_section = _sibling_gap(
                    children[i - 1],
                    children[i],
                    _t,
                    "row",
                    owner_level,
                    node_index,
                    node,
                )[1]
                gap_spans.append((start, offsets[i] - start, is_section, owner_level))

    # A row cell that is its own heading section reserves its content height plus
    # 2*padding (content laid at the reduced inner width), mirroring the col
    # branch; such cells fill the row height (like images) so the bg spans them.
    heights, is_section_cell = _cell_heights(
        children, widths, node_index, fonts, _t, in_section_levels, owner_level
    )
    y_offsets = _row_valign_offsets(
        node, children, widths, heights, is_section_cell, node_index, fonts, _t
    )
    # A cell pushed down onto the row's baseline needs room for the shift, so the
    # row is the tallest (offset + height), not simply the tallest height.
    row_h = max((o + h for o, h in zip(y_offsets, heights)), default=0.0)
    placements = [
        (
            child,
            offset,
            w,
            row_h
            if (
                (_is_image_leaf(child, node_index) and not _is_width_capped(child))
                or sec
                or _is_bar_marker(child)
                # A code block is a surface: beside a taller cell it shows more of
                # its lines, and its background lines up with its neighbour's.
                or is_code_block_leaf(child, node_index)
                # A cell an author partitioned with `...` asked for the row's
                # full height: that is the surplus its spring opens. Without
                # this it gets its own content height, there is no slack, and
                # the spring is silently inert in the one place it is useful.
                or getattr(child, "col_spring", False)
            )
            else h,
            dy,
        )
        for child, offset, w, h, sec, dy in zip(
            children, offsets, widths, heights, is_section_cell, y_offsets
        )
    ]
    return placements, row_h, gap_spans


def _row_valign_offsets(
    node: LayoutNode,
    children: list,
    widths: list,
    heights: list,
    is_section_cell: list,
    node_index: dict,
    fonts: FontSet,
    theme: Theme,
) -> list:
    """Per-cell downward shift that vertically aligns a same-line row's cells.

    Applies to a row the grouper marked as one source line (``line_split``), an
    authored column row, or a marker-aside row carrying ``marker_align``. Other
    rows — card grids and image asides — keep top alignment, so neither themed
    alignment surface can restack a card grid.

    The mode is the level's ``Line align`` (seeded onto the row by
    ``bake_render_cascade``, root's value as the floor):

    - ``baseline`` (the default): a LEAF or a ``row`` cell puts its first text
      baseline on the row's shared baseline, so a 26px number and the 16px text
      beside it sit on one line. A ``col`` cell STACKS, so it has no single line
      to offer — snapping its top line to the baseline leaves the rest of the
      block hanging below and makes a row of such pairs zig-zag. It centers its
      box on the row's text band instead (the union of the baseline-aligned
      cells' line boxes), which is the ``align-items: center`` reading: the
      baseline lands a little below that center because text sits above it.
    - ``top``: every cell hangs from the row's top edge.
    - ``center`` / ``bottom``: every cell distributes its slack in the row.

    A cell with no text baseline (a bar, an image) falls back to a body line box
    (``h / LINE_SCALE``), which is exactly where a ratio bar's own line-box
    height puts it, so it keeps sitting on its neighbour's line. Stretched cells
    (images, section cells, bar markers) fill the row and never shift, in any
    mode.
    """
    n = len(children)
    column_row = getattr(node, "column_row", False)
    marker_mode = (node.render_properties or {}).get("marker_align")
    marker_row = marker_mode is not None
    if n < 2 or not (getattr(node, "line_split", False) or column_row or marker_row):
        return [0.0] * n
    mode = (
        marker_mode
        or (node.render_properties or {}).get("line_align")
        or (theme.root.line_align or LINE_ALIGN_DEFAULT)
    )
    if column_row and mode == "baseline":
        # An authored `:::` row's cells are BLOCKS, not the words of one line:
        # they come from different source lines and most of them stack. There is
        # no shared line for a baseline to be shared along, so the default reads
        # as `top` here — the same answer the branch below gives a row of cells
        # that all stack. `top`/`center`/`bottom` still mean what they say.
        return [0.0] * n
    if mode == "top":
        return [0.0] * n
    stretched = [
        bool(sec)
        or _is_image_leaf(child, node_index)
        or _is_bar_marker(child)
        # A `...` cell is given the row's full height and places its own
        # content inside it; shifting it as well would place that content twice.
        or getattr(child, "col_spring", False)
        for child, sec in zip(children, is_section_cell)
    ]
    if mode in ("center", "bottom"):
        # A cell can only be aligned if it has slack, and a ``max_width`` image
        # has some: its height is the cap over its aspect, intrinsic, not the
        # row's. An UNCAPPED one takes the width the row gives it and its height
        # follows, so that one really does fill the row and stays pinned.
        #
        # Counting every image as stretched is what made `Vertical align`
        # silently inert on a row of logos: top, center and bottom rendered
        # byte-identically because every cell was pinned. The capped/uncapped
        # split is the one `_layout_grid_row` and `_layout_bento_row` already
        # make, through this same `_is_width_capped`.
        #
        # Deliberately NOT applied to the baseline branch below. There
        # ``stretched`` means "has no baseline to hang off", which is true of
        # every image however it is sized — a picture has no text baseline, and
        # letting a capped one take the ``h / LINE_SCALE`` fallback would invent
        # one from its height.
        boxed = [
            fixed
            and not (_is_image_leaf(child, node_index) and _is_width_capped(child))
            for child, fixed in zip(children, stretched)
        ]
        return _box_valign_offsets(mode, heights, boxed)

    # --- baseline -------------------------------------------------------
    # A col cell in a source-line row stacks: it does not vote on the axis and
    # is centered on the band the others define. A marker row is different: its
    # content col represents one item body, whose first baseline is the intended
    # baseline target even when the body continues for several lines.
    bases: list = []
    for child, w, h, fixed in zip(children, widths, heights, stretched):
        if fixed or (child.type == "col" and not marker_row):
            bases.append(None)
            continue
        base = first_baseline(child, w, node_index, fonts, theme)
        bases.append(h / LINE_SCALE if base is None else base)
    # A cell with no base and not stretched is exactly a col cell.
    has_stacked = any(b is None and not fixed for b, fixed in zip(bases, stretched))
    real = [b for b in bases if b is not None]
    if not real:
        # Nothing single-line to hang a band off: a row of stacked cells
        # centers on itself, anything else is left alone.
        return (
            _box_valign_offsets("center", heights, stretched)
            if has_stacked
            else [0.0] * n
        )
    if len(real) < 2 and not has_stacked:
        # A lone baseline has nothing to align to.
        return [0.0] * n
    top = max(real)
    # The text band: the union of the baseline-aligned cells' boxes once they
    # are on the shared baseline. ``lo`` is 0 by construction (the cell holding
    # the deepest baseline does not move) — spelled out so the band reads as a
    # span rather than a height.
    lo = min(top - b for b in bases if b is not None)
    hi = max(top - b + h for b, h in zip(bases, heights) if b is not None)
    band_center = (lo + hi) / 2.0
    raw = [
        None if fixed else (band_center - h / 2.0 if b is None else top - b)
        for b, h, fixed in zip(bases, heights, stretched)
    ]
    # A tall col can want to start ABOVE the row's top edge; shift the whole
    # row down rather than clipping it (stretched cells stay pinned to the top,
    # which is where they are drawn from).
    shift = -min([r for r in raw if r is not None] + [0.0])
    return [0.0 if r is None else r + shift for r in raw]


def _box_valign_offsets(mode: str, heights: list, stretched: list) -> list:
    """Uniform box alignment of a row's cells: ``center`` or ``bottom``.

    Shares ``_valign_offset``'s arithmetic so the themed row mode and the
    per-cell ``content_valign`` hint can never disagree. Stretched cells fill
    the row, so they have no slack and stay at 0 by construction.
    """
    row_h = max(heights, default=0.0)
    return [
        0.0 if fixed else _valign_offset({"content_valign": mode}, h, row_h)
        for h, fixed in zip(heights, stretched)
    ]


def _valign_offset(rp: dict | None, cell_h: float, row_h: float) -> float:
    """Vertical offset of a row cell per its ``content_valign`` hint.

    ``center``/``bottom`` distribute the cell's slack (``row_h - cell_h``);
    the default (``top`` / no hint) keeps top alignment. Cells
    stretched to the full row height have no slack, so the hint is a no-op
    there by construction. Cell-local — deliberately NOT part of the
    content_weight/content_align cascade.
    """
    v = (rp or {}).get("content_valign")
    if v == "center":
        return max(0.0, (row_h - cell_h) / 2.0)
    if v == "bottom":
        return max(0.0, row_h - cell_h)
    return 0.0


def _emoji_leaf_size(nd: dict, fonts: "FontSet", theme: "Theme") -> tuple[float, float]:
    """(w, h) reserved for an EMOJI leaf, matching what ``draw_emoji_box`` draws.

    ``peeled`` emojis size to a plain glyph at the surrounding text size (Text
    block; table cells use their themed size); ``heading``/``alone`` use the
    Primary badge size."""
    content = nd.get("content", "")
    if nd.get("emoji_kind") == "text":
        e_tf = _load_emoji_typeface(theme.emojis.text.font_path, fonts.emoji)
        size = _text_emoji_px(nd, theme)
        font = _emoji_glyph_font(e_tf, fonts.typeface, size)
        glyph_w = glyph_advance(content, e_tf, fonts.typeface, size)
        m = font.getMetrics()
        return glyph_w, m.fDescent - m.fAscent
    return _emoji_badge_size(content, *fonts.emoji_badge(nd, theme), fonts.typeface)


def _dp_bar_theme(theme: Theme, kind: str) -> "BarTheme":
    """The BarTheme for a datapoint_bar kind (unit bars reuse Ratio Bars;
    Key: value bars — percent or ratio — use Key Value Bars)."""
    dp = theme.datapoints
    if kind in ("percent", "kv_unit"):
        return dp.kv_bar
    return dp.ratio_bar


def _bar_track_height(bt: "BarTheme") -> float:
    return bt.thickness + bt.track.padding.y


def _datapoint_bar_height(props: dict, theme: Theme) -> float:
    """Bar leaves are bar-only (their text renders as sibling leaves). The
    ratio/unit bars sit in a same-line row beside a text leaf, so their box
    matches the text line height and the draw centers the bar in it."""
    bt = _dp_bar_theme(theme, props.get("kind", ""))
    bar_h = _bar_track_height(bt)
    if props.get("kind") in ("ratio", "unit"):
        return max(theme.text.font_size * LINE_SCALE, bar_h)
    return bar_h


# Non-text content types that don't get a real-text box.
_DEBUG_NO_PADDING = {"image", *_BREAK_LEAVES}


def _text_extent_rect(
    box: LayoutBox,
    nd: dict | None,
    fonts: FontSet,
    theme: Theme,
) -> skia.Rect | None:
    """Tight bounds of a leaf's real rendered text.

    Laid out exactly like ``draw_styled_text_box`` (same fonts/size/wrap/align,
    box hugs content) but **not clamped** to the box, so overflow — lines the box
    clips — extends the rect past the layout box. Returns ``None`` for non-text
    leaves.
    """
    # Gutter marker leaf: synthetic box (no markdown node). Only the text
    # markers (ordinal / quote char) have a text extent — and it IS the drawn
    # ink, since _draw_list_marker anchors them ink-top flush with box.y.
    lm = (box.render_properties or {}).get("list_marker")
    if lm is not None:
        text = lm.get("text") or ""
        if not _is_text_marker(lm) or not text:
            return None
        font, _size = _marker_font(lm, fonts, theme)
        _top, ink_h, advance = _text_ink(text, font)
        return skia.Rect.MakeXYWH(box.x, box.y, advance, ink_h)
    # Stacking-cards key label: synthetic box (no markdown node) drawn in the
    # Card Keys style — measure it with the same fonts the drawer uses.
    tk = (box.render_properties or {}).get("table_key")
    if tk is not None:
        key_fonts, key_size, _kc = _table_key_fonts(fonts, theme)
        words = _explode_words(tk.get("text", ""))
        if not words:
            return None
        lines = _wrap_lines(words, box.width, key_fonts, key_size)
        widest = max(
            (_line_width(ln, key_fonts, key_size) for ln in lines),
            default=0.0,
        )
        return skia.Rect.MakeXYWH(
            box.x, box.y, widest, len(lines) * key_size * LINE_SCALE
        )
    # Ring value/unit: synthetic box (no markdown node) drawn centered inside
    # the circular bar from its baked ``ring_text``. Measure it with the same
    # lines, fonts and size the drawer uses (render_ring_text), centered —
    # mirroring draw_content_box's ring_role branch.
    if (box.render_properties or {}).get("ring_role") is not None:
        rt = ring_text(box.render_properties or {}, fonts, theme)
        r_fonts, r_size = rt.fonts, rt.size
        words = _explode_words(rt.text)
        if not words:
            return None
        lines = _wrap_lines(words, box.width, r_fonts, r_size)
        if not lines:
            return None
        line_h = r_size * LINE_SCALE
        spans = [
            (
                box.x + (box.width - _line_width(ln, r_fonts, r_size)) / 2,
                _line_width(ln, r_fonts, r_size),
            )
            for ln in lines
        ]
        left = min(s for s, _ in spans)
        right = max(s + w for s, w in spans)
        return skia.Rect.MakeXYWH(
            left, box.y, max(0.0, right - left), len(lines) * line_h
        )
    if nd is None or nd.get("type") in _DEBUG_NO_PADDING:
        return None
    node_type = nd.get("type", "")
    raw_content = nd.get("content", "")

    if node_type == "emoji":
        content = raw_content
        if not content:
            return None
        if nd.get("emoji_kind") == "text":
            e_tf = _load_emoji_typeface(theme.emojis.text.font_path, fonts.emoji)
            size = _text_emoji_px(nd, theme)
            font = _emoji_glyph_font(e_tf, fonts.typeface, size)
            gw = glyph_advance(content, e_tf, fonts.typeface, size)
            m = font.getMetrics()
            gh = m.fDescent - m.fAscent
            _align = _resolve_h_align(box.render_properties, theme)
            if _align == "center":
                gx = box.x + (box.width - gw) / 2
            elif _align == "right":
                gx = box.x + (box.width - gw)
            else:
                gx = box.x
            return skia.Rect.MakeXYWH(gx, box.y + (box.height - gh) / 2, gw, gh)
        # heading / alone → badge glyph, centered in the (shaped) box
        style, b_tf = fonts.emoji_badge(nd, theme)
        font = _emoji_glyph_font(b_tf, fonts.typeface, style.icon_size)
        gw = glyph_advance(content, b_tf, fonts.typeface, style.icon_size)
        m = font.getMetrics()
        gh = m.fDescent - m.fAscent
        box_w, box_h = _emoji_badge_size(content, style, b_tf, fonts.typeface)
        _align = _resolve_h_align(box.render_properties, theme)
        if _align == "center":
            bx = box.x + (box.width - box_w) / 2
        elif _align == "right":
            bx = box.x + (box.width - box_w)
        else:
            bx = box.x
        by = box.y + (box.height - box_h) / 2
        return skia.Rect.MakeXYWH(bx + (box_w - gw) / 2, by + (box_h - gh) / 2, gw, gh)

    if node_type == "inline_code":
        label = raw_content.strip().strip("`")
        if not label:
            return None
        font, ic_size = _code_font(theme, nd.get("code_variant"), fonts.mono)
        inline_tf = fonts.chip_emoji(nd.get("code_variant"), theme)
        text_w = _link_label_width(label, font, ic_size, inline_tf)
        metrics = font.getMetrics()
        text_h = metrics.fDescent - metrics.fAscent
        code = theme.inline_code.resolved(nd.get("code_variant"))
        pad = code.padding
        bg_w, bg_h, _radius, l_pad, _r_pad = _chip_metrics(code, text_w, text_h)
        _align = _resolve_h_align(box.render_properties, theme)
        if _align == "center":
            bg_x = box.x + (box.width - bg_w) / 2
        elif _align == "right":
            bg_x = box.x + (box.width - bg_w)
        else:
            bg_x = box.x
        bg_y = box.y + (box.height - bg_h) / 2
        return skia.Rect.MakeXYWH(bg_x + l_pad, bg_y + pad.top, text_w, text_h)

    if node_type == "link":
        _variant, label, is_emoji, style = _resolve_link(nd, theme)
        if not label:
            return None
        size = (style.text_style or TextStyle()).font_size
        font, runs, e_tf = link_label_fonts(nd, label, fonts, theme, size)
        text_w = _label_runs_width(runs, size, e_tf)
        metrics = font.getMetrics()
        text_h = metrics.fDescent - metrics.fAscent
        pad = style.padding or PaddingBox()
        pill_w, pill_h = _link_pill_size(runs, style, font, size, e_tf, is_emoji)
        _align = _resolve_h_align(box.render_properties, theme)
        if _align == "center":
            pill_x = box.x + (box.width - pill_w) / 2
        elif _align == "right":
            pill_x = box.x + (box.width - pill_w)
        else:
            pill_x = box.x
        pill_y = box.y + (box.height - pill_h) / 2
        text_off_x = pill_x + (pill_w - text_w) / 2 if is_emoji else pill_x + pad.left
        text_off_y = pill_y + (pill_h - text_h) / 2
        return skia.Rect.MakeXYWH(text_off_x, text_off_y, text_w, text_h)

    if node_type == "bullet_point":
        raw_content = "•"
    laid = _text_leaf_lines(box, nd, raw_content, fonts, theme)
    if laid is None:
        return None
    _text, lines, starts, eff_fonts, size = laid
    ends = [s + _line_width(ln, eff_fonts, size) for s, ln in zip(starts, lines)]
    left = min(starts)
    return skia.Rect.MakeXYWH(
        left, box.y, max(0.0, max(ends) - left), len(lines) * size * LINE_SCALE
    )


def _text_leaf_lines(
    box, nd: dict, raw_content: str, fonts: FontSet, theme: Theme
) -> tuple[str, list, list[float], FontSet, float] | None:
    """A text leaf as ``draw_content_box`` lays it out: ``(text, lines, starts,
    fonts, size)`` — the drawn text, its wrapped lines, the x each line starts
    at, and the fonts and size they are drawn with.

    The text branch's style chain, mirrored so the two cannot disagree
    (ADR-400). The text-box overlay and the click regions of the links inside
    a sentence (render_actions) both read this one answer.
    """
    node_type = nd.get("type", "")
    atx_level, atx_text = nd.get("atx_level", 0), raw_content

    rp = box.render_properties or {}
    weight = rp.get("content_weight")
    w_scale, _ = _weight_scale_and_color(theme, weight, 0, nd.get("text_style"))
    eff_fonts, base_size = _effective_text_fonts(
        node_type,
        atx_level,
        fonts,
        theme,
        node=nd,
    )
    # Mirror draw_content_box's leaf styling so the box matches the drawn glyphs:
    # emphasis, then date-chip key/day (day = larger/bold, key = labels style +
    # upper-cased content), which also forces center alignment.
    eff_fonts, size, _c = _apply_kv_role(
        rp,
        eff_fonts,
        base_size * w_scale,
        0,
        theme,
        fonts,
        node=nd,
    )
    eff_fonts, size, _c = _apply_date_role(rp, eff_fonts, size, 0, theme, fonts)
    content = _date_role_content(rp, atx_text)
    words = _explode_words(content)
    if not words:
        return None

    inner_w = box.width
    inner_x = box.x
    lines = _wrap_lines(words, inner_w, eff_fonts, size)
    if not lines:
        return None
    align = "center" if rp.get("date_role") else _resolve_h_align(rp, theme)

    starts: list[float] = []
    for ln in lines:
        lw = _line_width(ln, eff_fonts, size)
        if align == "center":
            starts.append(inner_x + (inner_w - lw) / 2)
        elif align == "right":
            starts.append(inner_x + (inner_w - lw))
        else:
            starts.append(inner_x)
    return content, lines, starts, eff_fonts, size
