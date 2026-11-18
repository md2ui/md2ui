"""Advice that points to a pattern: a section with its shape, lacking what it adds.

Agents rarely open the patterns in ``skills/patterns/``, and three tries at
routing them there by text did not reach them: a grouped index, a routing line
in the core note, a page-recipe table (ADR-502, *Eleven new
patterns*). Advice tied to the answer did. So a section whose shape a pattern
teaches, and which lacks what that pattern adds, gets one line naming what to
add and the pattern to read; a section that has it gets nothing, since a hint
is worth its re-send only where the read would change the answer.

Each trigger reads the grouped tree only. ``advice`` owns when a line is sent:
once per pattern per session, never for a pattern the session has read.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator

from md2ui.meanings import SKILLS_PATTERNS

# The values a Display-tier figure is: an amount, a count, a reading. A date or a
# clock time in the Display tier is not a figure with a change.
_FIGURES = frozenset(
    f"dp_{kind}"
    for kind in "currency percentage number quantity measurement rate score ratio "
    "duration".split()
)
# What a section shows: anything beside a lone figure means it is not alone.
_LEAVES = frozenset(
    "text segment inline_code link image key value list_item table_cell code_block "
    "emoji".split()
)
# The most words a line of a picked item's card holds: a name, a byline, a price.
_SHORT_LINE = 12


def pattern_hints(tree: dict) -> Iterator[tuple[str, str]]:
    """``(topic, message)`` for each section whose shape a pattern teaches and
    which lacks what the pattern adds, in document order."""
    figure = any(n.get("text_style") == "display" for n in _walk(tree))
    yield from _section_hints(tree, False, figure)
    for node in _walk(tree):
        kids = node.get("children", [])
        shapes = Counter(
            k.get("fingerprint_hash") for k in kids if k.get("heading_group")
        )
        for kid in kids:
            if kid.get("heading_group"):
                in_run = shapes[kid.get("fingerprint_hash")] > 1
                yield from _section_hints(kid, in_run, figure)
        yield from _rows_without_change(kids)
        yield from _shelves(kids)


def _section_hints(
    section: dict, in_run: bool, page_has_figure: bool
) -> Iterator[tuple[str, str]]:
    """A section's own figures and line. A card, `###` or below, or one of a run
    of its kind, is a tile, not the figure a page leads with."""
    if not in_run and section.get("heading_level", 0) <= 2:
        yield from _lead_figures(section)
    yield from _chart_without_figure(section, page_has_figure)


def _pattern(name: str) -> str | None:
    """``patterns/<name>`` while ``skills/patterns`` holds it: a renamed or removed
    pattern silences its trigger rather than point to nothing."""
    return f"patterns/{name}" if (SKILLS_PATTERNS / f"{name}.md").is_file() else None


def _own(section: dict) -> list[dict]:
    """What a section holds under its title, at any depth: a card inside it, a
    ``heading_group``, is a section of its own."""
    out: list[dict] = []
    for kid in section.get("children", []):
        heading = str(kid.get("type")).startswith("heading")
        if not kid.get("heading_group") and not heading:
            out += [kid, *_own(kid)]
    return out


def _title(section: dict) -> str:
    """A section's heading text, without what stands at its edge; nothing for an
    untitled one."""
    for kid in section.get("children", []):
        if str(kid.get("type")).startswith("heading"):
            texts = [c for c in kid.get("children", []) if c.get("type") == "text"]
            return " ".join(str(p["content"]) for p in [kid, *texts] if p["content"])
    return ""


def _is_figure(node: dict) -> bool:
    """A Display-tier text that is one amount, count or reading and nothing else:
    `48,210`, not `5 unread emails`."""
    points = node.get("data_points", [])
    return (
        node.get("text_style") == "display"
        and len(points) == 1
        and points[0]["label"] in _FIGURES
        and points[0]["matched"] == str(node.get("content", "")).strip()
    )


def _is_change(node: dict) -> bool:
    """A chip that is a change: `+12%`, `▲ 6%`, `-63`."""
    return node.get("type") == "inline_code" and any(
        dp["label"] in ("dp_change", "dp_percentage")
        for dp in node.get("data_points", [])
    )


def _draws_line(node: dict) -> bool:
    return node.get("datapoint_display") == "line_chart"


def _lead_figures(section: dict) -> Iterator[tuple[str, str]]:
    """One to four Display-tier figures that are all a section holds besides its
    title: no label, no context line, no change, nothing else. One is a hero
    figure, two to four a row of KPIs."""
    own = _own(section)
    figures = [str(n["content"]) for n in own if _is_figure(n)]
    if not 1 <= len(figures) <= 4:
        return
    if any(n.get("type") in _LEAVES and not _is_figure(n) for n in own):
        return
    if len(figures) == 1 and (topic := _pattern("hero-figure")):
        yield (
            topic,
            f"`{figures[0]}` leads its section on its own. Glue a muted label above "
            f"it, its change as a chip after ` - ` where it has one, and a muted line "
            f"on what it rests on, a period or a range. {_cost(topic)}",
        )
    elif len(figures) > 1 and (topic := _pattern("kpis")):
        yield (
            topic,
            f"These {len(figures)} figures, `{figures[0]}` first, stand without "
            f"labels. Glue a muted label under each, with its change as a chip after "
            f"` - ` where it has one: `` _Orders_ - `+4%` ``. {_cost(topic)}",
        )


def _chart_without_figure(
    section: dict, page_has_figure: bool
) -> Iterator[tuple[str, str]]:
    """A section that draws one line, on a line of its own, on a page with no
    figure to lead it: the chart card's total, change and period. Where the page
    leads with a figure elsewhere, the line is that figure's history."""
    if page_has_figure:
        return
    own = _own(section)
    rows = [n for n in own if n.get("line_split_group") or n.get("type") == "list_item"]
    in_rows = {id(kid) for row in rows for kid in row.get("children", [])}
    lines = [n for n in own if _draws_line(n) and id(n) not in in_rows]
    if len(lines) != 1:
        return
    if topic := _pattern("chart-card"):
        key = next(
            (str(k["content"]) for k in lines[0]["children"] if k.get("type") == "key"),
            "",
        )
        yield (
            topic,
            f"The line `{key}` has no figure to lead it. Put its total or latest "
            f"value above it in the Display tier, its change as a chip after ` - `, "
            f"and a muted line naming the period; the pattern adds the ranges to "
            f"switch to. {_cost(topic)}",
        )


def _rows_without_change(kids: list[dict]) -> Iterator[tuple[str, str]]:
    """Three or more rows of one shape, each drawing a line, none with its change:
    the ticker row's chip at the edge."""
    runs: dict[object, list[dict]] = {}
    for kid in kids:
        if kid.get("line_split_group") and any(
            _draws_line(c) for c in kid.get("children", [])
        ):
            runs.setdefault(kid.get("fingerprint_hash"), []).append(kid)
    rows = max(runs.values(), key=len, default=[])
    if len(rows) < 3 or any(_is_change(n) for row in rows for n in _walk(row)):
        return
    if topic := _pattern("ticker-rows"):
        stacked = all(
            any(c.get("column_split_group") for c in row["children"]) for row in rows
        )
        stack = "" if stacked else " and stack its name over a muted detail with ` : `"
        yield (
            topic,
            f"These {len(rows)} rows each draw a line and no change. Put each item's "
            f"change at the row's edge as a chip after ` ... `{stack}. {_cost(topic)}",
        )


def _shelves(kids: list[dict]) -> Iterator[tuple[str, str]]:
    """Two or more sibling groups, each named and holding a run of picture cards,
    where a card's title stands above its picture. A way to see all is not
    advised: it is real only when the data holds more than the page shows."""
    shelves = [
        kid
        for kid in kids
        if kid.get("heading_group") and _title(kid) and _picture_run(kid)
    ]
    if len(shelves) < 2 or not (topic := _pattern("shelf")):
        return
    if any(_titled(card) for shelf in shelves for card in _picture_run(shelf)):
        yield (
            topic,
            f"These {len(shelves)} groups each hold a run of picture cards. Open each "
            f"card with an untitled `### ` so its picture leads. {_cost(topic)}",
        )


def _picture_run(section: dict) -> list[dict]:
    """The longest run of two or more same-shape cards in *section* that each
    hold a picture of their own and only short lines: an item picked by its
    picture, not a feature or a passage read beside one."""
    runs: dict[object, list[dict]] = {}
    for card in section.get("children", []):
        if (
            card.get("heading_group")
            and any(c.get("type") == "image" for c in card.get("children", []))
            and all(
                len(str(n.get("content", "")).split()) <= _SHORT_LINE
                for n in _own(card)
            )
        ):
            runs.setdefault(card.get("fingerprint_hash"), []).append(card)
    run = max(runs.values(), key=len, default=[])
    return run if len(run) >= 2 else []


def _titled(card: dict) -> bool:
    """A card whose heading has a title, which stands above its picture."""
    return bool(_title(card))


def _walk(node: dict) -> Iterator[dict]:
    yield node
    for kid in node.get("children", []):
        yield from _walk(kid)


def _cost(topic: str) -> str:
    """The read a pattern hint ends on: the pattern's topic and its length."""
    text = (SKILLS_PATTERNS / f"{topic.removeprefix('patterns/')}.md").read_text(
        encoding="utf-8"
    )
    return f'`guide("{topic}")`, ≈{len(text.split())} words.'
