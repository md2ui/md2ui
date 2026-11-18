"""Metrics: how big a thing is, once its style is known.

The second half of the shared middle. ``render_style`` answers *what font and
size*; this module answers *how many pixels* -- word widths, wrapped line counts,
chip and pill boxes, badge and ring sizes.

Both halves of the renderer call these, and that is the point: a box measured
here and painted there cannot disagree, because there is only one arithmetic
(ADR-400). Nothing here takes a canvas.

Depends on ``render_style`` and never the other way round.
"""

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.grouper_escapes import HARD_BREAK
from md2ui.pipeline.render_style import (
    _RING_TEXT_MARGIN,
    FontSet,
    _code_size,
    _emoji_glyph_font,
    _span_font,
    _table_text_style,
    _text_style_scopes,
    scoped_text_style,
)
from md2ui.pipeline.render_glyph_faces import glyph_advance, runs_advance
from md2ui.pipeline.render_text_scopes import chip_face
from md2ui.pipeline.theme import (
    EmojiBadgeStyle,
    InlineCodeTheme,
    LinkStyle,
    PaddingBox,
    Theme,
)
from md2ui.utils.image_params import split_md2ui_params
from md2ui.utils.font_loader import make_font


LINE_SCALE = 1.4  # line-height multiplier


def _code_font(
    theme: Theme, variant: str | None, mono: skia.Typeface
) -> tuple[skia.Font, float]:
    """The font a chip of *variant* measures and draws its label with, and its size.

    Every place that sizes or paints a chip label comes through here, so a
    variant stating ``Font weight: 700`` is measured as wide as it is drawn.
    """
    size = _code_size(theme, variant)
    return make_font(chip_face(theme, variant, mono), size), size


def _link_label_width(
    label: str, font: skia.Font, size: float, emoji_tf: skia.Typeface | None
) -> float:
    """Emoji-aware label width — the runs and fonts the label is drawn with."""
    return runs_advance(label, font, emoji_tf, size)


def _label_runs_width(
    runs: list[tuple[str, skia.Font]], size: float, emoji_tf: skia.Typeface | None
) -> float:
    """Width of a button label drawn run by run, each in its own face."""
    return sum(_link_label_width(text, font, size, emoji_tf) for text, font in runs)


def _chip_metrics(
    code: "InlineCodeTheme", text_w: float, text_h: float
) -> tuple[float, float, float, float, float]:
    """``(bg_w, bg_h, radius, l_pad, r_pad)`` for an inline-code pill.

    The rounded corners inset the glyphs by half the radius on each side so they
    do not touch the curve — but that inset is CLAMPED to the chip's own height,
    for the same reason a stadium never needs more than one end-cap of room. Ask
    for a huge radius (the CSS "fully rounded" idiom) and you get a stadium, not
    a pill a thousand pixels wide that can never share a row with its siblings.
    A radius that already fits inside the height is untouched.

    One function because three places size a chip — the width measurer, the
    drawer and the text-extent path — and a clamp applied to only some of them
    would be a silent mis-measure.
    """
    bg_h = text_h + code.padding.y
    inset = min(code.corner_radius, bg_h)
    l_pad = code.padding.left + inset / 2
    r_pad = code.padding.right + inset / 2
    radius = min(code.corner_radius, bg_h / 2.0)
    return text_w + l_pad + r_pad, bg_h, radius, l_pad, r_pad


def _link_pill_size(
    runs: list[tuple[str, skia.Font]],
    style: "LinkStyle",
    font: skia.Font,
    size: float,
    emoji_tf: skia.Typeface | None,
    is_emoji: bool,
) -> tuple[float, float]:
    """(pill_w, pill_h) for a link's box, shape-aware.

    Shape is only forced when ``is_emoji`` — a pure-emoji label is squared
    into ``style.emoji_shape`` ("circle"/"square" force a 1:1 aspect) as tall
    as a text label of its variant, padded by its vertical padding on every
    side. Any other link (including Pill) always sizes to
    content + configured padding — a stadium look comes purely from a larger
    ``corner_radius``, not a different sizing rule.
    """
    metrics = font.getMetrics()
    text_h = metrics.fDescent - metrics.fAscent
    text_w = _label_runs_width(runs, size, emoji_tf)
    pad = style.padding or PaddingBox()
    pill_w = text_w + pad.x
    pill_h = text_h + pad.y
    if is_emoji and style.emoji_shape in ("circle", "square"):
        side = max(text_w, text_h) + pad.y
        return side, side
    return pill_w, pill_h


def image_floor(rp: dict | None) -> float | None:
    """The width an image may not be given less of: its ``min_width``, capped
    by its ``max_width`` — the ceiling wins, so ``min == max`` is a fixed size."""
    rp = rp or {}
    floor = rp.get("min_width")
    if not floor:
        return None
    cap = rp.get("max_width")
    return float(min(floor, cap)) if cap else float(floor)


def with_image_floors(measure, floors: dict[str, float]):
    """*measure*, but reporting each floored image's floor — so every fit test
    that measures a subtree counts it — where it otherwise reports no width."""

    def measured(node, *role):
        floor = floors.get(node.node_id) if node.type == "image" else None
        return floor if floor is not None else measure(node, *role)

    return measured


def image_width_cap(rp: dict | None) -> float | None:
    """The widest the author lets an image draw (``max_width``); ``None`` when it
    stretches to its space."""
    return (rp or {}).get("max_width")


def height_sized(rp: dict, own_ratio: str | None = None) -> dict:
    """*rp* with a ``max_height`` turned into the width cap it means: that
    height times the picture's own ratio, so the box shrinks keeping its shape
    where the space is narrower. A run shares one height while each picture
    keeps *own_ratio*, its own ``aspect_ratio``, when it wrote one."""
    height = rp.get("max_height")
    ratio = own_ratio or rp.get("aspect_ratio")
    parsed = _parse_ratio(str(ratio)) if ratio else None
    if not height or parsed is None:
        return rp
    out = {k: v for k, v in rp.items() if k != "max_height"}
    return {**out, "aspect_ratio": ratio, "max_width": round(height * parsed)}


def _parse_ratio(spec: str) -> float | None:
    """Parse a ``"W:H"`` aspect-ratio string into a W/H float, or None."""
    try:
        w, h = spec.split(":")
        wf, hf = float(w), float(h)
        return wf / hf if hf > 0 else None
    except ValueError:
        return None


def ratio_ranges(spec) -> list[tuple[float, float]] | None:
    """An authored ``aspect_ratio`` as ``(from_width, ratio)`` pairs, narrowest
    first, or None when it does not parse.

    ``3:4,1:1@600,16:9@960`` is 3:4, then 1:1 once the image is 600px wide, then
    16:9 from 960px: the author decides what a picture becomes as it widens
    (neither a height limit nor an automatic step)."""
    first, *rest = str(spec).split(",")
    base = _parse_ratio(first)
    if base is None:
        return None
    ranges = [(0.0, base)]
    for entry in rest:
        ratio, at, width = entry.partition("@")
        parsed = _parse_ratio(ratio)
        if parsed is None or not at:
            return None
        try:
            ranges.append((float(width), parsed))
        except ValueError:
            return None
    return sorted(ranges)


# The ratio of an image with none authored, written the way an author writes one:
# a photograph box that widens with the image.
DEFAULT_IMAGE_RATIOS = "3:2,16:9@768,2.35:1@1024"


def ratio_at(spec, width: float) -> float | None:
    """The ratio *spec* (``ratio_ranges``) gives an image *width* wide."""
    ranges = ratio_ranges(spec)
    if ranges is None:
        return None
    return [ratio for start, ratio in ranges if start <= width][-1]


def default_image_ratio(width: float) -> float:
    """The ratio an image with no authored ratio draws at, *width* wide."""
    ratio = ratio_at(DEFAULT_IMAGE_RATIOS, width)
    assert ratio is not None
    return ratio


def _image_aspect_ratio(rp: dict | None, width: float) -> float:
    """The W/H ratio an image draws at, *width* wide: 1:1 for a circle, else the
    author's ratio for that width, else the default's."""
    rp = rp or {}
    if rp.get("shape") == "circle":
        return 1.0
    spec = rp.get("aspect_ratio")
    authored = ratio_at(spec, width) if spec else None
    return authored if authored is not None else default_image_ratio(width)


def image_card_height(url: str | None, width: float) -> float:
    """The height an image card's own picture asks for, *width* wide: that
    width over the ``aspect_ratio`` its URL writes (the ladder read at that
    width), capped by its ``max_height``. 0 when it writes no ratio, so a card
    without one is as tall as its content, as before. Content that needs more
    room than this always gets it (``natural_height``)."""
    params = split_md2ui_params(url or "")[1]
    ratio = (
        ratio_at(params["aspect_ratio"], width) if "aspect_ratio" in params else None
    )
    if not ratio:
        return 0.0
    height = width / ratio
    try:
        return min(height, float(params.get("max_height", height)))
    except ValueError:
        return height


def bake_card_ratios(node) -> None:
    """Let each image card whose URL writes an ``aspect_ratio`` take its
    picture's own size (``image_card_height``), once the generator has chosen
    the arrangement from the content: baked after ``generate``, so the ratio
    sizes a card in the columns it was given and never changes how many there
    are."""
    url = getattr(node, "card_bg_url", None)
    if getattr(node, "card_kind", None) == "image_card" and url:
        if "aspect_ratio" in split_md2ui_params(url)[1]:
            rp = node.render_properties or {}
            node.render_properties = {**rp, "photo_sized": True}
    for child in node.children:
        bake_card_ratios(child)


def _image_content_width(rp: dict | None, available: float) -> float:
    """Image content width: fills ``available`` unless the author caps it
    (``max_width``)."""
    mw = image_width_cap(rp)
    if mw:
        try:
            return min(available, float(mw))
        except (TypeError, ValueError):
            return available
    return available


# Word advances, keyed by ``(typeface id, emoji typeface id, size, word)``. A leaf
# is measured at every width a trial layout tries (the generator's _block_width
# and _cell_height), and a word's advance never depends on that width, so each is
# measured once. ``skia.Typeface`` is unhashable, hence the ids — and
# ``_WORD_FACES`` keeps every keyed face alive, so no other face can reuse its id.
# Emptied when full, which bounds a long app session's theme reloads.
_WORD_WIDTHS: dict[tuple, float] = {}
_WORD_FACES: dict[int, object] = {}
_WORD_CACHE_MAX = 200_000


def _measure_word(
    word: str, bold: bool, italic: bool, fonts: FontSet, size: float
) -> float:
    """Advance width of one word, emoji-aware (matches the drawer). Memoised;
    see ``_WORD_WIDTHS``."""
    # The face _span_font picks for this bold/italic pair.
    if bold:
        face = fonts.bold_italic if italic else fonts.bold
    else:
        face = fonts.italic if italic else fonts.typeface
    key = (id(face), id(fonts.emoji), size, word)
    width = _WORD_WIDTHS.get(key)
    if width is None:
        if len(_WORD_WIDTHS) >= _WORD_CACHE_MAX:
            _WORD_WIDTHS.clear()
            _WORD_FACES.clear()
        width = _WORD_WIDTHS[key] = _measure_word_uncached(
            word, bold, italic, fonts, size
        )
        _WORD_FACES[id(face)] = face
        _WORD_FACES[id(fonts.emoji)] = fonts.emoji
    return width


def _measure_word_uncached(
    word: str, bold: bool, italic: bool, fonts: FontSet, size: float
) -> float:
    return runs_advance(word, _span_font(fonts, size, bold, italic), fonts.emoji, size)


# Wrapped lines, keyed by ``(the five face ids, size, words as a tuple)``; the value is a
# short list of ``(lo, hi, lines)`` entries, one per distinct breaking of that
# text. The greedy wrap below gives the same lines for EVERY width in
# ``[lo, hi)`` (see ``_wrap_lines_uncached``), so a leaf wrapped once need not be
# wrapped again until the width crosses one of its breaks -- measure, place and
# paint each wrap the same leaf, and a window drag moves the width a few pixels
# at a time, so nearly every re-wrap lands inside an interval already computed.
#
# The key is the FIVE FACES the wrap reads -- ``typeface``, ``bold``, ``italic``
# and ``bold_italic`` through ``_span_font``, ``emoji`` through ``_measure_word``
# -- not the FontSet that carries them. ``render_style`` builds a fresh FontSet on
# nearly every call with ``dataclasses.replace`` (``_heading_fonts``,
# ``_table_key_fonts``, ``_apply_ring_role``, ``_apply_date_role``,
# ``_apply_kv_role``), so a FontSet id would be a new key on nearly every call and
# the cache would rarely hit. A face never changes once loaded; a theme reload makes
# new ones.
#
# ``_WRAP_FACES`` keeps every keyed face alive, so no other face can reuse its id
# -- the rule ``_WORD_FACES`` follows, in a dict of its own because
# ``_WORD_FACES`` is emptied with ``_WORD_WIDTHS``, on a schedule this cache does
# not share: a face released there while its id is still a key here would be
# unsound. ``tuple(words)`` because ``_explode_words`` hands every caller a fresh
# list and ``project_paint_spans`` can rewrite it. Emptied when full, like
# ``_WORD_WIDTHS``.
_WRAP_CACHE: dict[tuple, list] = {}
_WRAP_FACES: dict[int, object] = {}
_WRAP_CACHE_MAX = 50_000


def _wrap_lines(words: list, inner_w: float, fonts: FontSet, size: float) -> list:
    """Word-wrap styled ``words`` into lines that fit ``inner_w`` (matches the drawer).

    Wraps by UNIT, not by word. A unit is a run of words with no space written
    between them — ``Settings`` and the ``.`` after it, which are two words only
    because a span boundary fell between them. Breaking there would put the full
    stop alone on the next line.

    Each word tuple is passed through WHOLE rather than rebuilt, so the
    ``space_before`` flag reaches the drawer; rebuilding it from named fields
    would silently drop it.

    Memoised by width INTERVAL; see ``_WRAP_CACHE``. The returned list and its
    lines are the cached objects themselves, shared with every later caller that
    wraps the same words: callers must not mutate them. Copy before editing.
    """
    faces = (
        fonts.typeface,
        fonts.bold,
        fonts.italic,
        fonts.bold_italic,
        fonts.emoji,
    )
    try:
        key = (*map(id, faces), size, tuple(words))
        entries = _WRAP_CACHE.get(key)
    except TypeError:  # an unhashable field in a word: wrap without the memo
        return _wrap_lines_uncached(words, inner_w, fonts, size)[0]
    if entries is not None:
        for lo, hi, lines in entries:
            if lo <= inner_w < hi:
                return lines
    else:
        if len(_WRAP_CACHE) >= _WRAP_CACHE_MAX:
            _WRAP_CACHE.clear()
            _WRAP_FACES.clear()
        entries = _WRAP_CACHE[key] = []
        for face in faces:
            _WRAP_FACES[id(face)] = face
    lines, lo, hi = _wrap_lines_uncached(words, inner_w, fonts, size)
    entries.append((lo, hi, lines))
    return lines


def _wrap_lines_uncached(
    words: list, inner_w: float, fonts: FontSet, size: float
) -> tuple[list, float, float]:
    """``(lines, lo, hi)``: the greedy unit wrap, and the width interval
    ``[lo, hi)`` over which it gives exactly these lines.

    Every decision the loop takes is one comparison of a running total against
    ``inner_w``: a unit joins the line while ``total <= inner_w`` and breaks to a
    new one while ``total > inner_w`` (the first unit of a line takes no
    decision -- it is placed whatever its width). So ``lo`` is the largest total
    any line ACCEPTED and ``hi`` the smallest total any break REJECTED; for every
    width in between each comparison comes out the same, and so do the lines.
    ``lo`` is ``-inf`` when no line took a second unit, ``hi`` is ``inf`` when
    nothing broke. ``lo`` is NOT the widest finished line: a line whose one unit
    is wider than ``inner_w`` took no comparison, and counting it would put
    ``lo`` above the very width that produced these lines.

    Both bounds are the very sums the comparison reads, in the same order --
    not ``_line_width``, which counts spaces differently (only where one was
    written) and would drift from the wrap in the last bit.
    """
    lines: list = []
    current_line: list = []
    current_w = 0.0
    lo = float("-inf")
    hi = float("inf")
    for unit in _wrap_units(words):
        head = unit[0]
        font = _span_font(fonts, size, head[1], head[2])
        space_w = font.measureText(" ") if current_line else 0.0
        unit_w = _unit_width(unit, fonts, size)
        if current_line and head[6:7] == (HARD_BREAK,):
            # An author's hard break: a new line at every width.
            lines.append(current_line)
            current_line = list(unit)
            current_w = unit_w
            continue
        if current_line:
            total = current_w + space_w + unit_w
            if total > inner_w:
                # A break: it holds for every width below this total.
                hi = min(hi, total)
                lines.append(current_line)
                current_line = list(unit)
                current_w = unit_w
                continue
            # A join: it holds for every width at or above this total.
            lo = max(lo, total)
        current_line.extend(unit)
        current_w += space_w + unit_w
    if current_line:
        lines.append(current_line)
    return lines, lo, hi


def _wrap_units(words: list) -> list:
    """``words`` grouped into the runs that must not be split across lines.

    A new unit starts at every word a space was written in front of; a word with
    none is glued to the one before it, because there is no break between them to
    take. The first word always starts a unit.
    """
    units: list = []
    for w in words:
        if units and len(w) > 6 and not w[6]:
            units[-1].append(w)
        else:
            units.append([w])
    return units


def _unit_width(unit: list, fonts: FontSet, size: float) -> float:
    """Width of one wrap unit: its words side by side, with no space between
    them, since a unit holds none by construction."""
    return sum(_measure_word(w[0], w[1], w[2], fonts, size) for w in unit)


def _widest_unit(words: list, fonts: FontSet, size: float) -> float:
    """The narrowest width ``words`` wrap into without clipping: the widest run
    ``_wrap_lines`` will not break, measured as the wrap measures it. A word's
    attached punctuation (``Settings.`` across a span boundary) counts with it."""
    return max((_unit_width(u, fonts, size) for u in _wrap_units(words)), default=0.0)


def _emoji_badge_size(
    content: str,
    style: "EmojiBadgeStyle",
    emoji_tf: "skia.Typeface | None",
    fallback_tf: "skia.Typeface",
) -> tuple[float, float]:
    """(w, h) for a Primary emoji badge: glyph at ``icon_size`` + fill padding.

    When a background fill is active and ``shape`` is circle/square the box is
    squared to a 1:1 ``side = max(w, h)`` — mirroring ``_link_pill_size`` and the
    image circle-crop. A bare glyph (no active fill) is never squared."""
    size = style.icon_size
    font = _emoji_glyph_font(emoji_tf, fallback_tf, size)
    glyph_w = glyph_advance(content, emoji_tf, fallback_tf, size)
    m = font.getMetrics()
    glyph_h = m.fDescent - m.fAscent
    pad = style.fill.padding
    box_w = glyph_w + pad.x
    box_h = glyph_h + pad.y
    if style.fill.is_active() and style.shape in ("circle", "square"):
        side = max(box_w, box_h)
        return side, side
    return box_w, box_h


def _text_emoji_px(nd: dict, theme: "Theme") -> float:
    """Glyph size for a peeled emoji: the surrounding text size — the themed
    table cell size when the emoji sits inside a table cell (``table_role``),
    else ``theme.text.font_size``. Single source for measurement, drawing,
    and the text-box overlay."""
    role = nd.get("table_role")
    if role:
        ts = _table_text_style(theme, role)
        if ts is not None:
            return ts.font_size
    # A key-peeled emoji sizes to its key's style.
    if nd.get("in_key"):
        return scoped_text_style(theme, "key", _text_style_scopes(nd)).font_size
    return scoped_text_style(theme, "text", _text_style_scopes(nd)).font_size


def _ring_inner_diameter(theme: Theme) -> float:
    """The clear region inside the ring stroke (value auto-fit ceiling)."""
    rt = theme.datapoints.ring
    return max(1.0, rt.diameter - 2.0 * rt.thickness - 2.0 * _RING_TEXT_MARGIN)


def _ring_fit_size(text: str, fonts: FontSet, size: float, theme: Theme) -> float:
    """Scale *size* down so *text* fits the ring's inner diameter (no wrap)."""
    inner = _ring_inner_diameter(theme)
    w = make_font(fonts.typeface, size).measureText(text)
    if w > inner:
        return max(8.0, size * inner / w)
    return size


def _outline_ink(text: str, font: skia.Font) -> tuple[float, skia.Rect]:
    """``(advance, ink)`` of *text* from the glyph outlines: exact, unrounded,
    the same on every rasterizer. ``measureText``'s ink is the rasterized
    glyphs' bounds rounded out to whole pixels, which CoreText and FreeType
    round differently, so a label near the edge fitted on one and not the other.
    """
    glyphs = font.textToGlyphs(text)
    ink = skia.Rect.MakeEmpty()
    x = 0.0
    for glyph, width in zip(glyphs, font.getWidths(glyphs)):
        path = font.getPath(glyph)
        if path is not None and not path.isEmpty():
            bounds = path.computeTightBounds()
            bounds.offset(x, 0.0)
            ink.join(bounds)
        x += width
    return x, ink


def _text_ink(text: str, font: skia.Font) -> tuple[float, float, float]:
    """``(ink_top, ink_height, advance)`` for *text*, relative to the baseline.

    ``ink_top`` is the distance from the baseline *up* to the top of the drawn
    glyphs, so ``baseline = top + ink_top`` puts the ink flush with ``top`` —
    unlike ``top + size``, which leaves the font's ascent gap (~20px for a 64px
    digit) as visible whitespace above the glyphs. Real bounds, not
    ``fCapHeight``, so a format like ``(1)`` — whose parens rise above the
    digits — sits flush too. The outlines' bounds, so a marker is the same
    size and sits at the same place on every platform. Falls back to cap height
    for inkless text.
    """
    advance, ink = _outline_ink(text, font)
    if ink.isEmpty():
        m = font.getMetrics()
        top = m.fCapHeight or -m.fAscent
        return top, top, advance
    return -ink.top(), ink.height(), advance
