"""``Layout: Auto``: whether a document tiles (bento) or stacks, decided by its empty page.

The theme delegates the per-document choice to the engine. The wrong layout shows
as long blank spaces, so the engine lays the document out both ways and keeps
bento only when it leaves clearly less of the page empty (:data:`MARGIN`). It
tiles dashboards and summaries and stacks catalogs, detail pages and articles.

The choice belongs to a document and a WIDTH BAND, never to one width: it is made
the first time a window lays the document out in a band and kept for the document's
life, so a resize builds no trial layout. Narrow screens stack without measuring:
there bento almost never wins.

A band's first layout costs one extra build unless nothing can tile; a decided band
adds nothing but bento's own cost where it tiles.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from md2ui.pipeline.generator_column_cuts import WIDE_BREAKPOINT
from md2ui.pipeline.layout_render import make_line_width_measurer

if TYPE_CHECKING:
    from md2ui.pipeline.grouper_types import MarkdownGroupNode
    from md2ui.pipeline.layout_generator import LayoutGenerator
    from md2ui.pipeline.render_style import FontSet
    from md2ui.pipeline.theme import Theme

S = TypeVar("S")

MARGIN = 0.85
"""Bento wins when its empty area is at most this share of the stacked one."""

WIDE_FROM = 1280.0
"""Where the widest band starts: bento's advantage grows with width (3 wins at 390,
19 at 767, 43 at 1280), so a tablet-wide window decides apart from a desktop one."""

# [root, theme, fonts, {band: tiles}] for the document last laid out, by identity:
# a reload hands over new objects, so there is nothing to invalidate by hand.
_CHOICES: list = []


def band(width: float) -> int:
    """0 narrow (under ``WIDE_BREAKPOINT``), 1 up to :data:`WIDE_FROM`, 2 beyond."""
    return 0 if width < WIDE_BREAKPOINT else 1 if width < WIDE_FROM else 2


def empty_area(scene, root: MarkdownGroupNode, fonts: FontSet, theme: Theme) -> float:
    """The page area, in px², that neither text nor a picture covers.

    A text leaf covers its single-line width, capped at its box, times its height;
    a picture covers its whole box, at whatever size the layout gave it.
    """
    nodes = {node.node_id: node for node in _walk(root)}
    line_width = make_line_width_measurer(fonts, theme)
    ink = 0.0
    for box in scene.boxes:
        node = nodes.get(box.content_id)
        if node is None or box.width <= 0 or box.height <= 0:
            continue
        line = None if node.type == "image" else line_width(node)
        ink += (box.width if line is None else min(line, box.width)) * box.height
    return scene.width * scene.height - ink


def _walk(root: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    out, stack = [], [root]
    while stack:
        node = stack.pop()
        out.append(node)
        stack.extend(node.children)
    return out


def choose(
    gen: LayoutGenerator,
    root: MarkdownGroupNode,
    theme: Theme,
    fonts: FontSet,
    width: float,
    build: Callable[[], S],
) -> S:
    """The scene ``Layout: Auto`` shows at *width*, built by *build* under the
    generator's current choice. On a band's first layout it builds both and keeps
    the winner; after that, one build, as without Auto."""
    memo = _CHOICES
    if not memo or memo[0] is not root or memo[1] is not theme or memo[2] is not fonts:
        memo[:] = [root, theme, fonts, {0: False}]
    tiles: dict[int, bool] = memo[3]
    here = band(width)
    if here in tiles:
        gen.bento_auto = tiles[here]
        return build()
    gen.bento_auto = True
    tiled = build()
    if not gen._bento or not any(gen._bento_runs(n) for n in _walk(root)):
        # Nothing to tile: the bento layout IS the stacked one.
        tiles[here] = gen.bento_auto = False
        return tiled
    gen.bento_auto = False
    stacked = build()
    wins = empty_area(tiled, root, fonts, theme) <= MARGIN * empty_area(
        stacked, root, fonts, theme
    )
    tiles[here] = gen.bento_auto = wins
    return tiled if wins else stacked
