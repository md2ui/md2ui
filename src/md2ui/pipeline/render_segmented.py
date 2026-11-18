"""A choice run drawn as one segmented control, and a choice option's paint.

A run of buttons the author divided with `` | `` whose options all share one
``md2ui.choice`` name, which the grouper stamps ``segmented_run`` (ADR-100,
``grouper_choices``), is drawn as one control when the theme asks for it
(``## Links`` → ``Segmented: yes``; ADR-405): a surface in the quieter button's paint behind the run, the
chosen option's own main-variant pill on it, the others their labels only, and
a thin divider between two unchosen neighbours. The surface is painted as a
button pill is (``render_pill_paint``): replaced against what it sits on, at
the variant's ``Stroke align``. Each segment stays its own
button, at the pill it is measured and clicked at (ADR-404, ADR-400): the
surface is paint, never a box, so no layout changes. A run its row cannot hold
on one line (its pills wrapped) stays separate pills, as does every run under
a theme that does not ask: the look is the theme's, the behaviour the same.

The chosen option is the one shown chosen: the host's tap (``choice_shown``,
``render_actions.with_node_states``) or else the main variant as written. A tap
swaps colours only, never the variant's padding or weight, so no box moves.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_choices import shown_chosen
from md2ui.pipeline.render_pill_paint import paint_pill
from md2ui.pipeline.render_style import _resolve_link
from md2ui.pipeline.theme import Theme

# How far the surface reaches past the run's pills, on every side.
_INSET = 3.0

Rect = tuple[float, float, float, float]


def _runs(node_index: dict) -> list[list[str]]:
    """Each run the grouper stamped ``segmented_run``, as its buttons' node ids."""
    return [
        [k.get("node_id", "") for k in nd.get("children") or []]
        for nd in node_index.values()
        if nd.get("segmented_run")
    ]


def paint_segmented(
    canvas: skia.Canvas,
    boxes: list,
    node_index: dict,
    pill_rect: Callable[[LayoutBox, dict], Rect],
    theme: Theme,
    images: dict | None = None,
) -> dict:
    """Under a theme that asks for the control (``links.segmented``), paint
    every segmented run's surface and dividers under its buttons, and
    return *node_index* with those buttons marked ``segment`` (dicts swapped,
    never edited), for :func:`choice_style` to draw them as segments. The
    surface is a pill of the quieter button (``paint_pill``): replaced against
    the stack the run sits on, at its ``Stroke align``; each segment is marked
    with the stack the surface makes (``segment_stack``), which its own paint
    is replaced against, as a pill on a card is against the card."""
    if not theme.links.segmented:
        return node_index
    placed = {b.content_id: b for b in boxes if b.content_id}
    marked = node_index
    for ids in _runs(node_index):
        if any(i not in placed for i in ids):
            continue
        rects = [pill_rect(placed[i], node_index[i]) for i in ids]
        top, bottom = rects[0][1], rects[0][1] + rects[0][3]
        if any(r[1] >= bottom or r[1] + r[3] <= top for r in rects):
            continue  # wrapped: separate pills
        # The surface is the control's, not its first option's: that option's
        # disabled or pending state (both stamped ``link_disabled``) stays its own.
        first = {**node_index[ids[0]], "link_variant": "secondary"}
        quiet = _resolve_link({**first, "link_disabled": False}, theme)[3]
        ink, stack = _surface(
            canvas, rects, quiet, placed[ids[0]].bg_stack, theme, images
        )
        chosen = [shown_chosen(node_index[i]) for i in ids]
        line = skia.Paint(
            Color=(ink & 0xFFFFFF) | 0x55000000, StrokeWidth=1.0, AntiAlias=True
        )
        for k in range(len(ids) - 1):
            if not (chosen[k] or chosen[k + 1]):
                a, b = rects[k], rects[k + 1]
                x, cy, h = (a[0] + a[2] + b[0]) / 2.0, a[1] + a[3] / 2.0, a[3] / 4.0
                canvas.drawLine(x, cy - h, x, cy + h, line)
        if marked is node_index:
            marked = dict(node_index)
        for i in ids:
            marked[i] = {**node_index[i], "segment": True, "segment_stack": stack}
    return marked


def _surface(
    canvas: skia.Canvas,
    rects: list[Rect],
    quiet,
    stack: tuple,
    theme: Theme,
    images: dict | None,
) -> tuple[int, tuple]:
    """The run's surface, *_INSET* past its pills: the quieter button's pill,
    its corners grown with it. No label names it, so no pin colours it."""
    left, top = rects[0][0] - _INSET, min(r[1] for r in rects) - _INSET
    right = rects[-1][0] + rects[-1][2] + _INSET
    bottom = max(r[1] + r[3] for r in rects) + _INSET
    radius = (quiet.corner_radius if quiet.corner_radius is not None else 16.0) + _INSET
    shape = skia.Rect.MakeLTRB(left, top, right, bottom)
    grown = dataclasses.replace(quiet, corner_radius=radius)
    return paint_pill(canvas, shape, grown, {}, stack, theme, images=images)


def choice_style(nd: dict, style, theme: Theme):
    """*style* as a choice option is shown: an unchosen segment its label only,
    in the quieter ink; an option the host's tap moved takes the other
    variant's colours in its own box. Anything else unchanged. An option is
    known by what was stamped on it -- the grouper's run (``segment``) or the
    host's tap (``choice_shown``) -- never by reading its destination here.
    A disabled or pending segment is drawn the same, in its disabled colours,
    inside its segment; a disabled option outside a run keeps its own pill."""
    if not (nd.get("segment") or "choice_shown" in nd):
        return style
    if nd.get("link_disabled") and not nd.get("segment"):
        return style  # a separate pill, disabled whole
    chosen = shown_chosen(nd)
    authored = (nd.get("link_variant") or "primary") == "primary"
    if not nd.get("segment") and chosen == authored:
        return style
    other = _resolve_link(
        {**nd, "link_variant": "primary" if chosen else "secondary"}, theme
    )[3]
    ts = style.text_style
    if ts is not None and other.text_style is not None:
        ts = dataclasses.replace(ts, color=other.text_style.color)
    if nd.get("segment") and not chosen:
        return dataclasses.replace(
            style,
            fill_color=0,
            stroke_width=0.0,
            shadows=[],
            gradient=None,
            bg_image=None,
            text_style=ts,
        )
    return dataclasses.replace(
        style,
        fill_color=other.fill_color,
        stroke_color=other.stroke_color,
        stroke_width=other.stroke_width,
        shadows=other.shadows,
        gradient=other.gradient,
        bg_image=other.bg_image,
        text_style=ts,
    )
