"""The text inside a ring: which lines, at what size, in what box.

A ring holds two baked leaves, its value over its unit label. The value scales
down to fit the clear inside on one line. The label wraps onto up to two lines that
each fit the circle's clear inside at that line's height, shrinks when two do not
fit but never below ``RING_UNIT_MIN_SCALE`` of its ``Ring Unit`` size, and ends
in an ellipsis when it still does not fit. Nothing is dropped silently, and
nothing runs over the stroke.

The leaf's measured box and its paint both read ``ring_text`` (ADR-400): the
label's lines are decided once, here, and the painter draws them as written.
"""

import dataclasses
from collections.abc import Callable

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.grouper_escapes import HARD_BREAK
from md2ui.pipeline.render_metrics import (
    LINE_SCALE,
    _outline_ink,
    _ring_fit_size,
    _ring_inner_diameter,
)
from md2ui.pipeline.render_style import FontSet, _apply_ring_role, _ring_text_style
from md2ui.pipeline.theme import Theme
from md2ui.utils.font_loader import make_font

# The label's lines, and the smallest share of its themed size it may shrink to.
RING_UNIT_MAX_LINES = 2
RING_UNIT_MIN_SCALE = 0.8
# How far each shrink trial steps down, in pixels.
_SHRINK_STEP = 0.25
_ELLIPSIS = "…"

# (text, face id, size, radius, value height, spacing) -> (face, lines, size).
# Keyed on the face's id and holding the face, so a freed id is never reused.
_PLAN_CACHE: dict[tuple, tuple] = {}
_PLAN_CACHE_MAX = 512


@dataclasses.dataclass(frozen=True)
class RingText:
    """One ring leaf as drawn: its fonts, its lines, and the box they claim."""

    fonts: FontSet
    lines: tuple[str, ...]
    size: float
    color: int
    width: float
    height: float

    @property
    def text(self) -> str:
        """The lines as one text whose breaks the wrap keeps at every width."""
        return HARD_BREAK.join(self.lines)


def ring_text(rp: dict, fonts: FontSet, theme: Theme) -> RingText:
    """The ring leaf whose render properties are *rp*, laid out to be drawn."""
    role = rp.get("ring_role")
    text = rp.get("ring_text", "")
    r_fonts, nominal, color = _apply_ring_role(
        rp, fonts, theme.text.font_size, theme.text.color, theme, fonts
    )
    face = r_fonts.typeface
    if role == "value":
        # The value's box keeps its themed line; its glyphs scale to fit.
        width = min(
            make_font(face, nominal).measureText(text), _ring_inner_diameter(theme)
        )
        size = _ring_fit_size(text, r_fonts, nominal, theme)
        return RingText(r_fonts, (text,), size, color, width, nominal * LINE_SCALE)
    lines, size = _unit_lines(text, face, nominal, theme)
    font = make_font(face, size)
    width = max(font.measureText(ln) for ln in lines)
    height = len(lines) * size * LINE_SCALE
    return RingText(r_fonts, lines, size, color, width, height)


def _unit_lines(
    text: str, face: skia.Typeface, nominal: float, theme: Theme
) -> tuple[tuple[str, ...], float]:
    """The label's lines and size, memoized: measure and paint both ask."""
    rt = theme.datapoints.ring
    radius = _ring_inner_diameter(theme) / 2.0
    value_h = _ring_text_style(theme, "value").font_size * LINE_SCALE
    key = (text, id(face), nominal, radius, value_h, rt.spacing)
    hit = _PLAN_CACHE.get(key)
    if hit is not None and hit[0] is face:
        return hit[1], hit[2]
    lines, size = _fit_unit(text.split(), face, nominal, radius, value_h, rt.spacing)
    if len(_PLAN_CACHE) >= _PLAN_CACHE_MAX:
        _PLAN_CACHE.clear()
    _PLAN_CACHE[key] = (face, lines, size)
    return lines, size


def _fit_unit(
    words: list[str],
    face: skia.Typeface,
    nominal: float,
    radius: float,
    value_h: float,
    spacing: float,
) -> tuple[tuple[str, ...], float]:
    """Wrap, then shrink to the floor, then ellipsize (module docstring)."""
    if not words:
        return ("",), nominal
    floor = nominal * RING_UNIT_MIN_SCALE
    size = nominal
    while True:
        for count in range(1, RING_UNIT_MAX_LINES + 1):
            fits = _clear_inside(count, make_font(face, size), radius, value_h, spacing)
            lines = _wrap(words, count, fits)
            if len(lines) == count and all(fits(ln, i) for i, ln in enumerate(lines)):
                return lines, size
        if size <= floor:
            break
        size = max(floor, size - _SHRINK_STEP)
    fits = _clear_inside(
        RING_UNIT_MAX_LINES, make_font(face, floor), radius, value_h, spacing
    )
    lines = _wrap(words, RING_UNIT_MAX_LINES, fits)
    return tuple(_ellipsize(ln, i, fits) for i, ln in enumerate(lines)), floor


def _clear_inside(
    count: int, font: skia.Font, radius: float, value_h: float, spacing: float
) -> Callable[[str, int], bool]:
    """Whether a text drawn as label line *i* of *count* stays inside the clear
    circle.

    The value and the label lines are centred in the circle together, and the
    painter puts a line's baseline one font size below its top and centres it
    on its advance, so each line's glyphs land at a known place. The test is
    their ink: its corner farthest from the centre must lie inside the circle,
    so the chord narrows for a line away from the centre, and a line's leading
    is free to run over the stroke where its glyphs do not. The ink is the
    outlines' (``_outline_ink``), so the same label fits the same way on every
    platform.
    """
    size = font.getSize()
    line_h = size * LINE_SCALE
    top = -(value_h + spacing + count * line_h) / 2.0 + value_h + spacing

    def fits(text: str, i: int) -> bool:
        advance, ink = _outline_ink(text, font)
        baseline = top + i * line_h + size
        dy = max(abs(baseline + ink.top()), abs(baseline + ink.bottom()))
        dx = max(advance / 2.0 - ink.left(), ink.right() - advance / 2.0)
        return dx * dx + dy * dy <= radius * radius

    return fits


def _wrap(
    words: list[str], count: int, fits: Callable[[str, int], bool]
) -> tuple[str, ...]:
    """*words* greedily onto at most *count* lines; the last takes the rest.

    A line always takes its first word, so a line may not fit: the caller
    decides whether that is a miss or an ellipsis.
    """
    lines: list[str] = []
    start = 0
    for i in range(count - 1):
        if start == len(words):
            break
        end = start + 1
        while end < len(words) and fits(" ".join(words[start : end + 1]), i):
            end += 1
        lines.append(" ".join(words[start:end]))
        start = end
    if start < len(words):
        lines.append(" ".join(words[start:]))
    return tuple(lines)


def _ellipsize(line: str, i: int, fits: Callable[[str, int], bool]) -> str:
    """*line* cut to end in an ellipsis that fits as line *i*, or unchanged if
    it already fits."""
    if fits(line, i):
        return line
    cut = line
    while cut and not fits(cut.rstrip() + _ELLIPSIS, i):
        cut = cut[:-1]
    return cut.rstrip() + _ELLIPSIS
