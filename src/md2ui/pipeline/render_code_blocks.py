"""Shared syntax highlighting, measurement and painting for code blocks."""

from __future__ import annotations

import dataclasses
import functools
from collections.abc import Callable
from typing import Any

import skia  # type: ignore[import-untyped]
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.token import Token
from pygments.util import ClassNotFound

from md2ui.pipeline.layout_script_parser import LayoutBox, LayoutNode
from md2ui.pipeline.render_backgrounds import _push_bg
from md2ui.pipeline.render_colors import _replace_color
from md2ui.pipeline.render_fills import _replaced_gradient
from md2ui.pipeline.render_glyph_faces import glyph_advance, glyph_runs
from md2ui.pipeline.theme_model import CodeBlockTheme, Theme
from md2ui.utils.font_loader import make_font


@dataclasses.dataclass(frozen=True)
class CodeRun:
    text: str
    color: int


@dataclasses.dataclass(frozen=True)
class CodeBlockPlan:
    lines: tuple[tuple[CodeRun, ...], ...]
    width: float
    # What the block measures: at most ``Max lines`` of it. ``full_height`` is
    # every line, so the paint can tell a block that has more below its cut.
    height: float
    line_height: float
    baseline: float
    full_height: float
    # The strip above the code that holds the copy button; 0 without one.
    header: float = 0.0


def _argb(hex_color: str | None, fallback: int) -> int:
    if not hex_color:
        return fallback
    value = hex_color.lstrip("#")
    if len(value) != 6:
        return fallback
    try:
        rgb = int(value, 16)
    except ValueError:
        return fallback
    return skia.ColorSetARGB(255, (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255)


def _normalized_source(content: str) -> str:
    source = content.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4)
    # The line ending immediately before a closing fence terminates the last
    # source line; it is not an additional empty display row. A second newline
    # remains and therefore still represents an authored blank line.
    return source[:-1] if source.endswith("\n") else source


@functools.lru_cache(maxsize=512)
def highlighted_lines(
    content: str,
    language: str | None,
    style_name: str,
    fallback_color: int,
) -> tuple[tuple[CodeRun, ...], ...]:
    """Return exact source rows split into adjacent same-color runs."""
    source = _normalized_source(content)
    try:
        style = get_style_by_name(style_name or "bw")
    except ClassNotFound:
        style = get_style_by_name("bw")

    tokens: list[tuple[Any, str]]
    syntax = False
    if language:
        try:
            lexer = get_lexer_by_name(language)
            # With the newline that ends the last line: line-based lexers (the
            # shell sessions) emit a line only once they see it, and would drop
            # the last one. The rows it adds are cut back below.
            tokens = [
                (token, value)
                for _, token, value in lexer.get_tokens_unprocessed(source + "\n")
            ]
            syntax = True
        except ClassNotFound:
            tokens = [(Token.Text, source)]
    else:
        tokens = [(Token.Text, source)]

    lines: list[list[CodeRun]] = [[]]
    for token, value in tokens:
        color = _token_color(style, token, fallback_color) if syntax else fallback_color
        parts = value.split("\n")
        for index, part in enumerate(parts):
            if part:
                current = lines[-1]
                if current and current[-1].color == color:
                    current[-1] = CodeRun(current[-1].text + part, color)
                else:
                    current.append(CodeRun(part, color))
            if index < len(parts) - 1:
                lines.append([])
    rows = source.count("\n") + 1  # every source line, and only those
    return tuple(tuple(line) for line in lines[:rows])


def _token_color(style: Any, token: Any, fallback: int) -> int:
    """*token*'s colour in *style*, from its nearest type the style lists: some
    lexers emit subtypes no style names (YAML's ``Literal.Scalar.Plain``)."""
    while not style.styles_token(token) and token.parent is not None:
        token = token.parent
    return _argb(style.style_for_token(token)["color"], fallback)


def code_block_plan(
    content: str,
    language: str | None,
    typeface: skia.Typeface,
    theme: CodeBlockTheme,
) -> CodeBlockPlan:
    """Build the geometry used unchanged by both measurement and painting."""
    style = theme.text_style
    font = make_font(typeface, style.font_size)
    metrics = font.getMetrics()
    glyph_height = metrics.fDescent - metrics.fAscent
    line_height = glyph_height + theme.line_spacing
    lines = highlighted_lines(content, language, theme.syntax_style, style.color)
    # Measured in the faces the paint draws each run in: a character the mono
    # face lacks draws (wider) from a system face, never as a box.
    text_width = max(
        (
            sum(
                glyph_advance(run.text, None, typeface, style.font_size) for run in line
            )
            for line in lines
        ),
        default=0.0,
    )
    shown = len(lines) if theme.max_lines is None else min(len(lines), theme.max_lines)
    text_height = glyph_height + max(0, len(lines) - 1) * line_height
    # The button, and one line's spacing below it before the code starts.
    header = copy_button_size(theme) + theme.line_spacing if theme.copy_icon else 0.0
    return CodeBlockPlan(
        lines=lines,
        width=text_width + theme.padding.x,
        height=header
        + glyph_height
        + max(0, shown - 1) * line_height
        + theme.padding.y,
        line_height=line_height,
        baseline=header + theme.padding.top - metrics.fAscent,
        full_height=header + text_height + theme.padding.y,
        header=header,
    )


def copied_text(content: str) -> str:
    """What the copy button puts on the clipboard: the source as written, less
    the line ending that closes it before the fence (it is not a shown row)."""
    return content[:-1] if content.endswith("\n") else content


def copy_button_size(theme: CodeBlockTheme) -> float:
    """The copy button's side: its icon plus the larger of its paddings. Square,
    so the block can be measured without the emoji font."""
    pad = theme.copy_button.padding
    return theme.copy_icon_size + (max(pad.x, pad.y) if pad else 0.0)


def copy_button_rect(
    box: LayoutBox, theme: CodeBlockTheme
) -> tuple[float, float, float, float]:
    """Where the copy button is painted, ``(x, y, width, height)``: the block's
    top-right corner, inside its padding. The drawer and the click region both
    read it (ADR-404)."""
    side = copy_button_size(theme)
    x = box.x + box.width - theme.padding.right - side
    return x, box.y + theme.padding.top, side, side


@dataclasses.dataclass(frozen=True)
class Scrollable:
    """A code block whose lines run past its right edge, or past its last shown
    line (``Max lines``): the box it is drawn in, and how wide and tall its
    content really is. The pipeline says WHAT can scroll; the host decides how,
    and keeps the offsets (0 … ``max_offset`` across, 0 … ``max_offset_y`` down)."""

    node_id: str
    content_id: str
    x: float
    y: float
    width: float
    height: float
    content_width: float
    content_height: float = 0.0
    bg_stack: tuple = ()  # what the block sits on, for its colour replacements

    @property
    def max_offset(self) -> float:
        return max(0.0, self.content_width - self.width)

    @property
    def max_offset_y(self) -> float:
        return max(0.0, self.content_height - self.height)


def code_block_scrollables(
    boxes: list, node_index: dict, typeface: skia.Typeface, theme: CodeBlockTheme
) -> list[Scrollable]:
    """One :class:`Scrollable` per code block clipped at its right edge or below
    its last shown line, from the same :func:`code_block_plan` its paint uses.
    Built once per width, like the click regions."""
    found: list[Scrollable] = []
    for box in boxes:
        nd = node_index.get(box.content_id) if box.content_id else None
        if nd is None or nd.get("type") != "code_block":
            continue
        plan = code_block_plan(nd["content"], nd.get("code_language"), typeface, theme)
        if plan.width > box.width + 0.5 or plan.full_height > box.height + 0.5:
            found.append(
                Scrollable(
                    node_id=nd.get("node_id", ""),
                    content_id=box.content_id,
                    x=box.x,
                    y=box.y,
                    width=box.width,
                    height=box.height,
                    content_width=plan.width,
                    content_height=plan.full_height,
                    bg_stack=box.bg_stack,
                )
            )
    return found


def is_code_block_leaf(node: LayoutNode, node_index: dict) -> bool:
    """True when *node* is a code block leaf."""
    nd = node_index.get(node.content_id) if node.content_id else None
    return node.type == "-" and (nd or {}).get("type") == "code_block"


# How far a clipped line's fade reaches in from the block's right edge.
FADE_WIDTH = 32.0


def lines_that_fit(plan: CodeBlockPlan, height: float, theme: CodeBlockTheme) -> int:
    """How many whole lines a block *height* tall shows above its bottom padding
    — at least one — so a cut always falls between two lines."""
    glyph = plan.line_height - theme.line_spacing
    room = height - plan.header - theme.padding.y - glyph + 0.5
    return max(1, min(len(plan.lines), int(room // plan.line_height) + 1))


def _paint_fade(canvas: skia.Canvas, rect: skia.Rect, color: int, edge: str) -> None:
    """The block's background, transparent to opaque across its *edge*
    (``right``, ``left``, ``bottom`` or ``top``)."""
    if edge == "bottom":
        top = max(rect.top(), rect.bottom() - FADE_WIDTH)
        band = skia.Rect.MakeLTRB(rect.left(), top, rect.right(), rect.bottom())
        ends = [skia.Point(rect.left(), top), skia.Point(rect.left(), rect.bottom())]
    elif edge == "top":
        bottom = min(rect.bottom(), rect.top() + FADE_WIDTH)
        band = skia.Rect.MakeLTRB(rect.left(), rect.top(), rect.right(), bottom)
        ends = [skia.Point(rect.left(), bottom), skia.Point(rect.left(), rect.top())]
    elif edge == "left":
        right = rect.left() + min(FADE_WIDTH, rect.width())
        band = skia.Rect.MakeLTRB(rect.left(), rect.top(), right, rect.bottom())
        ends = [skia.Point(right, rect.top()), skia.Point(rect.left(), rect.top())]
    else:
        left = rect.right() - min(FADE_WIDTH, rect.width())
        band = skia.Rect.MakeLTRB(left, rect.top(), rect.right(), rect.bottom())
        ends = [skia.Point(left, rect.top()), skia.Point(rect.right(), rect.top())]
    shader = skia.GradientShader.MakeLinear(ends, [skia.ColorSetA(color, 0), color])
    canvas.drawRect(band, skia.Paint(Shader=shader))


def draw_code_block(
    canvas: skia.Canvas,
    box: LayoutBox,
    content: str,
    language: str | None,
    typeface: skia.Typeface,
    page: Theme,
    *,
    paint_fill: Callable[..., None],
    emoji_tf: skia.Typeface | None = None,
    button_image: skia.Image | None = None,
    offset: float = 0.0,
    offset_y: float = 0.0,
) -> None:
    """Paint one block using :func:`code_block_plan` geometry.

    *paint_fill* is the renderer's layered background painter, so the copy
    button takes every background key a button does without this module
    reaching back into the renderer. *offset* and *offset_y* are how far a host
    has scrolled the lines left and up (:class:`Scrollable`); the button stays
    where it is, and lines scrolled up pass under the space above the code. *page*'s
    colour replacements apply as to a pill: the fill against what the block sits
    on, then the runs and the copy button against that replaced fill.
    """
    theme = page.code_blocks
    fill = _replace_color(theme.background_color, box.bg_stack, page, "fill")
    inner = _push_bg(box.bg_stack, fill)
    plan = code_block_plan(content, language, typeface, theme)
    rect = skia.Rect.MakeXYWH(box.x, box.y, box.width, box.height)
    radius = min(theme.corner_radius, box.width / 2.0, box.height / 2.0)
    canvas.drawRoundRect(
        rect,
        radius,
        radius,
        skia.Paint(Color=fill, Style=skia.Paint.kFill_Style),
    )
    size = theme.text_style.font_size
    canvas.save()
    canvas.clipRRect(skia.RRect.MakeRectXY(rect, radius, radius), True)
    y = box.y + plan.baseline
    shown = lines_that_fit(plan, box.height, theme)
    first = 0
    more_below = shown < len(plan.lines)
    if offset_y > 0.0:
        # The lines move up inside the code's own window, between the space
        # above the code and the bottom padding; a line cut by an edge is drawn.
        window = skia.Rect.MakeLTRB(
            rect.left(),
            box.y + plan.header + theme.padding.top,
            rect.right(),
            rect.bottom() - theme.padding.bottom,
        )
        canvas.clipRect(window, True)
        first = int(offset_y // plan.line_height)
        y += first * plan.line_height - offset_y
        shown = min(len(plan.lines), first + shown + 1)
        more_below = offset_y < plan.full_height - box.height - 0.5
    for line in plan.lines[first:shown]:
        x = box.x + theme.padding.left - offset
        for run in line:
            paint = skia.Paint(
                Color=_replace_color(run.color, inner, page), AntiAlias=True
            )
            for piece, font in glyph_runs(run.text, None, typeface, size):
                canvas.drawString(piece, x, y, font, paint)
                x += font.measureText(piece)
        y += plan.line_height
    if theme.fade and plan.width - offset > box.width:
        _paint_fade(canvas, rect, fill, "right")
    if theme.fade and offset > 0.0:
        _paint_fade(canvas, rect, fill, "left")
    if theme.fade and more_below:
        # Across the last lines, ending where the text does: the bottom padding
        # below them is background already.
        text = skia.Rect.MakeLTRB(
            rect.left(), rect.top(), rect.right(), rect.bottom() - theme.padding.bottom
        )
        _paint_fade(canvas, text, fill, "bottom")
    if theme.fade and offset_y > 0.0:
        top = box.y + plan.header + theme.padding.top
        above = skia.Rect.MakeLTRB(rect.left(), top, rect.right(), rect.bottom())
        _paint_fade(canvas, above, fill, "top")
    canvas.restore()
    if theme.copy_icon:
        _paint_copy_button(
            canvas, box, page, inner, paint_fill, emoji_tf or typeface, button_image
        )


def _paint_copy_button(
    canvas: skia.Canvas,
    box: LayoutBox,
    page: Theme,
    stack: tuple,
    paint_fill: Callable[..., None],
    icon_tf: skia.Typeface,
    image: skia.Image | None,
) -> None:
    """The button in its ``### Copy Button`` style, its icon centred on it,
    replaced as a link button is against the block's fill (*stack*)."""
    theme = page.code_blocks
    style = theme.copy_button
    fill = style.fill_color
    if fill is not None:
        fill = _replace_color(fill, stack, page, "fill")
    x, y, w, h = copy_button_rect(box, theme)
    rect = skia.Rect.MakeXYWH(x, y, w, h)
    radius = style.corner_radius or 0.0
    paint_fill(
        canvas,
        rect,
        bg_color=fill,
        image=image,
        gradient=_replaced_gradient(style.gradient, stack, page),
        corner_radius=radius,
        shadows=style.shadows,
        direct_solid=True,
    )
    if style.stroke_width and style.stroke_color is not None:
        stroke = skia.Paint(
            Color=_replace_color(style.stroke_color, stack, page, "stroke"),
            Style=skia.Paint.kStroke_Style,
            StrokeWidth=style.stroke_width,
            AntiAlias=True,
        )
        canvas.drawRoundRect(rect, radius, radius, stroke)
    font = make_font(icon_tf, theme.copy_icon_size)
    metrics = font.getMetrics()
    icon = theme.copy_icon or ""
    ink = (style.text_style or theme.text_style).color
    ink = _replace_color(ink, _push_bg(stack, fill), page)
    canvas.drawString(
        icon,
        x + (w - font.measureText(icon)) / 2,
        y + (h - (metrics.fDescent - metrics.fAscent)) / 2 - metrics.fAscent,
        font,
        skia.Paint(Color=ink, AntiAlias=True),
    )
