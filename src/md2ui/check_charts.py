"""Authoring notes on charts that did not draw (ADR-602), for ``check``.

A chart is decided by the grouper from what each row holds, so a row that holds
a little more than a value leaves the chart without a word: the run it was part
of draws one row shorter, or not at all. The same goes for an arrow chain of
values that does not draw a line. These name the row and the reason, so the
author can decide whether it was meant. They are notes: a row of words beside
a chart may well be meant as text.

Grouping only, like the rest of ``check``. A shell module; the pipeline never
imports it.
"""

from __future__ import annotations

import copy
import re

from md2ui.pipeline.grouper_charts import (
    LINE_ASCII,
    LINE_PLAIN,
    LINE_TEXT,
    LINE_TICK,
    LINE_UNCHARTED,
    LINE_UNITS,
    LINES_COUNT,
    LINES_LABEL,
    ROW_PLAIN,
    ROW_TEXT,
    ROW_UNCHARTED,
    ROW_UNITS,
    _chart_row_info,
    _flag_charts,
    _header_unit,
    _line_runs,
    _series_header_names,
    _value_unit,
    chart_row_failure,
    line_chain_failure,
    line_run_failure,
    uncharted,
    unit_kind,
)
from md2ui.pipeline.grouper_display_vocab import _subtree_dps, _subtree_text
from md2ui.pipeline.value_format import MAX_UNIT, declared_unit, last_bracket
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType

# What a chart or line takes as written; every other unit is declared (ADR-204).
_DECLARE = (
    "write the numbers bare and declare the unit once above them, "
    "`Storage (GB):`, or in a line's key, `High (°C): 24 → 23 → 21`"
)
_CHART_UNITS = (
    "a chart value is a number, written alone or as `%`, a currency (`$220`, "
    f"`200 EUR`) or a magnitude (`5K`); for any other unit, {_DECLARE}"
)
_ROW_ADVICE = {
    ROW_UNCHARTED: f"its value is in no chart unit: {_CHART_UNITS}",
    ROW_TEXT: "a chart row is `- Key: value` with the value alone. Move the "
    "words into the key or out of the list",
    ROW_PLAIN: f"a plain number charts only under a declared unit: {_DECLARE}",
    ROW_UNITS: "its values are in more than one unit. Write them in one",
}
_LINE_ADVICE = {
    LINE_UNCHARTED: f"its values are in no chart unit: {_CHART_UNITS}",
    LINE_TICK: "a label in parentheses names its point -- words, a date or a time, "
    "`(Q1)`, `(6 PM)` -- not a second value. Move the value out of the label",
    LINE_ASCII: "a line is values joined by `→`. Write `→` instead of `->`",
    LINE_UNITS: "its values are in more than one unit. Write them in one",
    LINE_PLAIN: "plain numbers draw a line only when the key declares their unit, "
    "`Users (count): 900 → 1.2K → 5K`",
    LINE_TEXT: "a line is values joined by `→`, each with an optional `(label)`, "
    "and nothing else",
}
_LINE_UNCHARTED_IN_KEY = (
    "its values are in no chart unit: a line's values are numbers alone or `%`, a "
    "currency (`$220`) or a magnitude (`5K`); for any other unit, write the numbers "
    "bare and name the unit in the key, on the same line: "
)
_LINES_ADVICE = {
    LINES_COUNT: "lines share an axis only with the same number of points. Give "
    "every line a value at each position",
    LINES_LABEL: "two lines label one position differently. Label each position "
    "once, on any line",
}


def _shown(node: MarkdownGroupNode) -> str:
    """The ``Key: value`` pair in *node* as written, shortened to quote."""
    pair = node
    while pair.type != NodeType.KEY_VALUE and len(pair.children) == 1:
        pair = pair.children[0]
    parts = {c.type: _subtree_text(c) for c in pair.children}
    text = (
        f"{parts[NodeType.KEY]}: {parts[NodeType.VALUE]}"
        if NodeType.KEY in parts and NodeType.VALUE in parts
        else _subtree_text(node)
    ).replace("`", "")
    return text if len(text) <= 60 else text[:59] + "…"


_NUMBER = re.compile(r"[-+−]?\d[\d.,]*")


def _key_and_values(node: MarkdownGroupNode) -> tuple[str, str]:
    """The key and the values of the ``Key: value`` pair *node* holds, as
    written; ``("", "")`` when it holds none."""
    pair = node
    while pair.type != NodeType.KEY_VALUE and len(pair.children) == 1:
        pair = pair.children[0]
    parts = {c.type: _subtree_text(c) for c in pair.children}
    if pair.type != NodeType.KEY_VALUE or NodeType.KEY not in parts:
        return "", ""
    return parts[NodeType.KEY].strip(), parts.get(NodeType.VALUE, "")


def _first_points(text: str) -> str:
    """An arrow chain's first three points as written, then an ellipsis."""
    points = [p.strip() for p in text.split("→")]
    return " → ".join(points[:3]) + (" → …" if len(points) > 3 else "")


def _unit_in_key(key: str, chain: str) -> str:
    """The line rewritten with its unit in the key and its numbers bare, from
    what the author wrote: ``Temp: 20° → 19°`` becomes ``Temp (°): 20 → 19``."""
    first = chain.split("→")[0]
    number = _NUMBER.search(first)
    unit = re.sub(r"\(.*?\)", "", first[number.end() :]).strip() if number else ""
    bare = chain.replace(unit, "") if unit else chain
    return f"`{key} ({unit or 'unit'}): {_first_points(' '.join(bare.split()))}`"


def _is_value_chain(node: MarkdownGroupNode) -> bool:
    """Three or more values joined by ``→``: what a line is made of."""
    values = [
        d for d in _subtree_dps(node) if _value_unit(d) is not None or uncharted(d)
    ]
    return len(values) >= 3 and "→" in _subtree_text(node)


def _charts_beside(kids: list[MarkdownGroupNode], i: int) -> bool:
    """Whether the sibling before or after *kids[i]* is a chart or a row of one."""
    near = [kids[j] for j in (i - 1, i + 1) if 0 <= j < len(kids)]
    return any(n.chart_group or _chart_row_info(n) is not None for n in near)


def rows_left_out(ast: MarkdownGroupNode) -> list[tuple[str, str]]:
    """``(row, advice)`` for each bullet that holds a value but no chart row,
    beside a chart or a row of one."""
    ast = paired(ast)
    found: list[tuple[str, str]] = []

    def walk(node: MarkdownGroupNode) -> None:
        if node.chart_group or node.line_group:
            return  # its rows drew, read under the run's declared unit
        kids = node.children
        for i, kid in enumerate(kids):
            reason = chart_row_failure(kid)
            if reason is not None and _charts_beside(kids, i):
                found.append((_shown(kid), _ROW_ADVICE[reason]))
            walk(kid)

    walk(ast)
    return found


def runs_without_chart(ast: MarkdownGroupNode) -> list[tuple[str, str, str]]:
    """``(first row, last row, advice)`` of each run of three or more
    ``- Key: value`` rows that draws no chart: rows in different units, or
    rows whose values are in no chart unit."""
    ast = paired(ast)
    found: list[tuple[str, str, str]] = []

    def walk(node: MarkdownGroupNode) -> None:
        run: list[tuple[MarkdownGroupNode, str | None]] = []
        for kid in [*node.children, None]:
            info = _chart_row_info(kid) if kid is not None else None
            uncharted = kid is not None and chart_row_failure(kid) == ROW_UNCHARTED
            if kid is not None and (info is not None or uncharted):
                run.append((kid, info[3] if info is not None else None))
                continue
            units = {unit_kind(unit) for _, unit in run}
            # A run that mixes chart rows with others is named row by row
            # (``rows_left_out``); this one never had a chart to leave.
            if len(run) >= 3 and (
                units == {None} or (None not in units and len(units) > 1)
            ):
                advice = (
                    f"their values are in no chart unit: {_CHART_UNITS}"
                    if units == {None}
                    else "their values are in more than one unit. Write them in one"
                )
                found.append((_shown(run[0][0]), _shown(run[-1][0]), advice))
            run = []
        for kid in node.children:
            walk(kid)

    walk(ast)
    return found


def lines_left_text(ast: MarkdownGroupNode) -> list[tuple[str, str]]:
    """``(pair, advice)`` for each ``Key: a → b → c`` of three or more values
    that draws no line."""
    ast = paired(ast)
    found: list[tuple[str, str]] = []

    def walk(node: MarkdownGroupNode) -> None:
        if node.line_group:
            return  # its lines drew, read under the run's declared unit
        if node.type == NodeType.KEY_VALUE and node.datapoint_display != "line_chart":
            value = next((c for c in node.children if c.type == NodeType.VALUE), None)
            key = next((c for c in node.children if c.type == NodeType.KEY), None)
            declared = key is not None and declared_unit(_subtree_text(key)) is not None
            reason = line_chain_failure(value, declared) if value is not None else None
            if reason == LINE_UNCHARTED and key is not None and value is not None:
                # A line's unit goes in its key, on the same line; a unit
                # declared above serves only a run of rows.
                found.append(
                    (
                        _shown(node),
                        _LINE_UNCHARTED_IN_KEY
                        + _unit_in_key(_subtree_text(key), _subtree_text(value)),
                    )
                )
            elif reason is not None:
                found.append((_shown(node), _LINE_ADVICE[reason]))
        for kid in node.children:
            walk(kid)

    walk(ast)
    return found


def paired(ast: MarkdownGroupNode) -> MarkdownGroupNode:
    """A copy of *ast* in which each line that was a pair no display read is
    that pair again (ADR-205): the shape a chart is decided on, so these notes
    can name the row a chart left out and why."""
    view = copy.deepcopy(ast)

    def walk(node: MarkdownGroupNode) -> None:
        for kid in node.children:
            walk(kid)
        if node.unpaired is not None:
            node.content = ""
            node.children = [node.unpaired]

    walk(view)
    return view


def chains_without_key(ast: MarkdownGroupNode) -> list[tuple[str, str, str]]:
    """``(chain, why, fix)`` for each arrow chain of three or more values that
    draws no line for want of a key: a line is its key and its values on ONE
    line, so a chain under a label line, or alone, draws nothing, and the fix
    reuses the line written right above as the key. A chain whose key is there
    but whose values carry a unit a line does not take gets that unit moved
    into the key."""
    ast = paired(ast)
    found: list[tuple[str, str, str]] = []

    def walk(node: MarkdownGroupNode) -> None:
        kids = node.children
        for i, kid in enumerate(kids):
            if kid.type == NodeType.TEXT and _is_value_chain(kid):
                above = kids[i - 1] if i else None
                label = (
                    _subtree_text(above).rstrip().removesuffix(":").rstrip()
                    if above is not None
                    and above.type == NodeType.TEXT
                    and above.glued_content_id is not None
                    and above.glued_content_id == kid.glued_content_id
                    and not _is_value_chain(above)
                    else "Key"
                )
                key, values = _key_and_values(kid)
                if key and any(uncharted(d) for d in _subtree_dps(kid)):
                    # The key is there; the values carry a unit a line does not
                    # take, which is what keeps it from parsing as one.
                    why = "its values carry a unit a line does not take; name it in the key"
                    fix = _unit_in_key(key, values)
                else:
                    why = "a line is its key and its values on one line"
                    fix = f"`{label}: {_first_points(_subtree_text(kid))}`"
                found.append((_shown(kid), why, fix))
            walk(kid)

    walk(ast)
    return found


def lines_apart(ast: MarkdownGroupNode) -> list[tuple[str, str, str]]:
    """``(first, last, advice)`` for each run of ``- Key: a → b → c`` items in
    one unit that draws as separate lines rather than on one axis."""
    ast = paired(ast)
    found: list[tuple[str, str, str]] = []

    def walk(node: MarkdownGroupNode) -> None:
        if node.line_group:
            return
        for start, end, rows in _line_runs(node):
            reason = line_run_failure(rows)
            if reason is not None:
                kids = node.children
                found.append(
                    (_shown(kids[start]), _shown(kids[end - 1]), _LINES_ADVICE[reason])
                )
        for kid in node.children:
            walk(kid)

    walk(ast)
    return found


def _charts_with(header: MarkdownGroupNode, below: MarkdownGroupNode) -> bool:
    """Whether the list *below* would chart with *header* right above it: the
    two tried together, as the grouper would group them without the gap."""
    if below.chart_group or below.line_group or below.type != NodeType.GROUP:
        return False
    if not below.children or any(
        c.type not in (NodeType.LIST_ITEM, NodeType.ORDERED_ITEM)
        for c in below.children
    ):
        return False
    trial = MarkdownGroupNode(type=NodeType.GROUP)
    trial.children = copy.deepcopy([header, *below.children])
    _flag_charts(trial)
    return (
        trial.chart_group
        or trial.line_group
        or any(c.chart_group or c.line_group for c in trial.children)
    )


def headers_apart(ast: MarkdownGroupNode) -> list[str]:
    """Each ``(unit)`` or ``Name, Name:`` line that a blank line keeps from the
    list below it, where the two would chart together: the header declares only
    the rows right under it."""
    ast = paired(ast)
    found: list[str] = []

    def walk(node: MarkdownGroupNode) -> None:
        kids = node.children
        for kid, below in zip(kids, kids[1:]):
            header = kid.children[-1] if kid.children else kid
            declares = _header_unit(header) or _series_header_names(header)
            if declares and _charts_with(header, below):
                found.append(_subtree_text(header).rstrip(":"))
        for kid in kids:
            walk(kid)

    walk(ast)
    return found


def units_not_read(ast: MarkdownGroupNode) -> list[tuple[str, str]]:
    """``(unit, why)`` for each line ending in a ``(unit)`` that is read as no
    unit, over rows of plain numbers it was meant to declare: the rows then draw
    as text, with nothing to say why."""
    ast = paired(ast)
    found: list[tuple[str, str]] = []

    def walk(node: MarkdownGroupNode) -> None:
        kids = node.children
        for i, kid in enumerate(kids):
            if kid.children or kid.type not in (NodeType.TEXT, NodeType.SEGMENT):
                continue
            unit = last_bracket(_subtree_text(kid).rstrip(":"))
            plain = [
                k for k in kids[i + 1 : i + 3] if chart_row_failure(k) == ROW_PLAIN
            ]
            if unit and len(plain) == 2 and _header_unit(kid) is None:
                why = (
                    f"a unit is at most {MAX_UNIT} characters"
                    if len(unit) > MAX_UNIT
                    else "the line declaring it is at most six words"
                )
                found.append((unit, why))
        for kid in kids:
            walk(kid)

    walk(ast)
    return found
