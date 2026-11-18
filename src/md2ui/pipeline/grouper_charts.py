"""Charts: which values a chart or a line takes, and which runs of rows draw as
one.

A chart value is a number; `%`, a currency and a magnitude stand alone, every
other unit is declared (ADR-204). ``_parse_line`` reads a ``Key: a → b → c``
chain and ``_parse_chart_row`` a ``- Key: value`` row; each failure has a reason
``check`` can name (``line_chain_failure``, ``chart_row_failure``,
``line_run_failure``). ``_flag_charts`` decides across a group: a run of rows
is a bar chart (``chart_group``), a run of chains is several lines on one axis
(``line_group``). It paints nothing and chooses no colours.
"""

from md2ui.pipeline.grouper_display_vocab import (
    _bare_content,
    _clear_datapoint_displays,
    _dp_kind,
    _dp_scalar,
    _subtree_dps,
    _subtree_text,
)
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.value_format import declared_unit, without_unit


# An arrow chain of values (`$710.14 → $713.94 → $720.65`) is a value over time.
_LINE_ARROW = "→"
_LINE_MIN_POINTS = 3
# Why an arrow chain of values stayed text (``line_chain_failure``).
LINE_SHORT = "fewer than three values"
LINE_TICK = "a number in a label"
LINE_UNITS = "mixed units"
LINE_TEXT = "text that is not a value"
LINE_ASCII = "values joined by `->`"
_ASCII_ARROW = "->"
LINE_UNCHARTED = "a value in no chart unit"
LINE_PLAIN = "a plain number with no declared unit"
# Numbers that draw their own display, or name a place rather than measure.
_NOT_MEASURES = frozenset({"score", "ratio", "ranking", "ordinal", "date", "time"})


def _value_unit(dp: dict) -> str | None:
    """The unit a datapoint's value is written in, which a chart's values must
    share: a currency, `%`, a magnitude (`5K`), or ``""`` for a plain number.
    ``None`` when it is no value a chart can draw -- every other unit, `61 GB`
    and `12 kg` included, is written bare and declared once (ADR-204)."""
    kind = _dp_kind(dp)
    v = dp.get("value")
    if kind == "currency" and isinstance(v, dict):
        return f"currency {v.get('currency')}"
    if kind == "percentage":
        return "%"
    if kind == "quantity" and isinstance(v, dict):
        if v.get("unit"):
            return None
        return "magnitude" if v.get("magnitude") else ""
    if kind == "number":
        return ""
    if kind == "change" and isinstance(v, dict):
        # `+5.26%`, `+$2.30`, `+12`: the same units, written with their sign.
        unit = {"percentage": "%", "bare": ""}.get(str(v.get("type")))
        if v.get("type") == "currency":
            unit = f"currency {v.get('currency')}"
        return unit
    return None


def unit_kind(unit: str | None) -> str | None:
    """*unit* as a chart compares it: a magnitude is a number, so `900` and
    `1.2K` are one kind."""
    return "" if unit == "magnitude" else unit


def _run_unit(units: list[str]) -> str:
    """The unit of values of one kind: ``"magnitude"`` only when every one is,
    ``""`` when plain numbers are among them."""
    if set(units) == {"magnitude"}:
        return "magnitude"
    return "" if "" in units else units[0]


def _signed_scalar(dp: dict) -> float | None:
    """The datapoint's value with its sign: a change carries its sign as a
    direction, every other value in its number."""
    x = _dp_scalar(dp)
    v = dp.get("value")
    if x is not None and isinstance(v, dict) and v.get("direction") == "decrease":
        return -abs(x)
    return x


def _is_marked(dp: dict) -> bool:
    """Whether *dp* is a value with a mark -- `%`, a currency, a magnitude, a
    sign or a unit -- rather than a bare number or a name (a date, a time)."""
    return bool(_value_unit(dp)) or _dp_kind(dp) == "change" or uncharted(dp)


def uncharted(dp: dict) -> bool:
    """Whether *dp* is a measured number written in a unit no chart takes
    (`24°`, `120 bpm` as a rate): the chart units are a closed list
    (``_value_unit``), so such a value stays text and ``check`` says why."""
    return (
        _value_unit(dp) is None
        and _dp_kind(dp) not in _NOT_MEASURES
        and _dp_scalar(dp) is not None
    )


def _parse_line(value: "MarkdownGroupNode", declared: bool = False) -> list[dict] | str:
    """The points of a value written as ``a → b → c``, or why it is not one.

    Every piece of the text must be accounted for: values joined by ``→``,
    each optionally followed by a ``(tick)`` of words or a date, and nothing
    else. A tick names its point -- `(May)`, `(Q1)`, `(FY2020)`, `(6 PM)`,
    `(2025)` -- so one holding a second value (`$412M (49%)`, `(1.2K)`,
    `(+5)`) keeps the text, as do an ellipsis, a word chain, a second unit or
    fewer than three values. A
    plain number and a magnitude (`900`, `1.2K`) are one kind, and a chain
    holding a plain number draws only when its key *declared* the unit, as a
    bar chart's run does (ADR-204)."""
    if value.children:
        return LINE_TEXT
    text = value.content
    dps = sorted(value.data_points, key=lambda d: d.get("start", 0))
    starts = {d.get("start"): d for d in dps}
    points: list[dict] = []
    units: set[str] = set()
    plain = False
    pos, n = 0, len(text)

    def skip_space(p: int) -> int:
        while p < n and text[p].isspace():
            p += 1
        return p

    while True:
        pos = skip_space(pos)
        dp = starts.get(pos)
        unit = _value_unit(dp) if dp is not None else None
        scalar = _signed_scalar(dp) if dp is not None else None
        if dp is not None and uncharted(dp):
            return LINE_UNCHARTED
        if dp is None or unit is None or scalar is None:
            return LINE_TEXT
        plain = plain or unit == ""
        units.add(unit_kind(unit) or "")
        point: dict = {"value": scalar, "text": dp["matched"].strip(), "tick": None}
        pos = skip_space(dp["end"])
        if pos < n and text[pos] == "(":
            close = text.find(")", pos)
            if close < 0:
                return LINE_TEXT
            tick = text[pos + 1 : close].strip()
            if not tick or "(" in tick:
                return LINE_TEXT
            if any(pos < d.get("start", 0) < close and _is_marked(d) for d in dps):
                return LINE_TICK
            point["tick"] = tick
            pos = skip_space(close + 1)
        points.append(point)
        if pos >= n:
            break
        arrow = starts.get(pos)
        if arrow is None or arrow["matched"].strip() != _LINE_ARROW:
            return LINE_TEXT
        pos = arrow["end"]
    if len(points) < _LINE_MIN_POINTS:
        return LINE_SHORT
    if len(units) != 1:
        return LINE_UNITS
    if plain and not declared:
        return LINE_PLAIN
    return points


def _holds_code(node: "MarkdownGroupNode") -> bool:
    return node.type == NodeType.INLINE_CODE or any(
        _holds_code(c) for c in node.children
    )


def line_chain_failure(
    value: "MarkdownGroupNode", declared: bool = False
) -> str | None:
    """Why *value*, an arrow chain of three or more values, draws no line;
    ``None`` when it draws one or is no such chain (`a → b → c` of words, or
    a before-and-after of two values, is text by design). *declared*: the
    pair's key declares a unit."""
    values = [
        d for d in _subtree_dps(value) if _value_unit(d) is not None or uncharted(d)
    ]
    text = _subtree_text(value)
    if len(values) < _LINE_MIN_POINTS:
        return None
    if _LINE_ARROW not in text:
        # `->` is no arrow: one spelling draws a line.
        joins = text.count(_ASCII_ARROW)
        fits = joins >= _LINE_MIN_POINTS - 1 and not _holds_code(value)
        return LINE_ASCII if fits else None
    parsed = _parse_line(value, declared)
    return None if isinstance(parsed, list) or parsed == LINE_SHORT else parsed


# Why a `- Key: value` bullet is no chart row (``chart_row_failure``).
ROW_TEXT = "text beside its value"
ROW_PLAIN = "a plain number"
ROW_UNITS = "mixed units"
ROW_UNCHARTED = "a value in no chart unit"


def _parse_chart_row(
    node: "MarkdownGroupNode", declared: bool = False
) -> tuple[str, list[float], list[str], str] | str | None:
    """``(label, values, texts as written, unit)`` when *node* is a bullet item
    wrapping exactly one ``Key: value(s)`` pair whose values a chart can draw;
    a reason when it is such a pair and they cannot be; None when it is no
    such pair. Chart rows come only from bullet lists --
    bare adjacent key-value lines stay individual kv_percent_bar rows.

    The value must be its values alone, comma-separated, in one kind: `%`, a
    currency (`$220.06`, `200 EUR`), or numbers with or without a magnitude
    (`5K`). A word beside it would be dropped by the chart, and a plain number
    is where ports, years and versions live, so neither draws -- unless the
    run *declared* its unit above it (``Temperature (°C):``), which makes its
    bare numbers a chart. Any other unit (`61 GB`) is written bare and
    declared the same way (ADR-204)."""
    if node.type not in (NodeType.LIST_ITEM, NodeType.ORDERED_ITEM):
        return None
    content_kids = [c for c in node.children if _subtree_text(c)]
    if len(content_kids) != 1 or content_kids[0].type != NodeType.KEY_VALUE:
        return None
    kv = content_kids[0]
    key = next((c for c in kv.children if c.type == NodeType.KEY), None)
    value = next((c for c in kv.children if c.type == NodeType.VALUE), None)
    if key is None or value is None:
        return None
    dps = [d for d in _subtree_dps(value) if _value_unit(d) is not None or uncharted(d)]
    if not dps:
        return None
    rest = _bare_content(_subtree_text(value))
    for d in dps:
        rest = rest.replace(d["matched"].strip(), "", 1)
    if rest.replace(",", "").strip("*_` "):
        return ROW_TEXT
    if any(uncharted(d) for d in dps):
        return ROW_UNCHARTED
    written = [_value_unit(d) or "" for d in dps]
    if len({unit_kind(u) for u in written}) != 1:
        return ROW_UNITS
    unit = _run_unit(written)
    if not unit and not declared:
        return ROW_PLAIN
    values: list[float] = []
    for d in dps:
        x = _signed_scalar(d)
        if x is None:
            return ROW_TEXT
        values.append(x)
    texts = [d["matched"].strip() for d in dps]
    return _subtree_text(key), values, texts, unit


def _chart_row_info(
    node: "MarkdownGroupNode", declared: bool = False
) -> tuple[str, list[float], list[str], str] | None:
    row = _parse_chart_row(node, declared)
    return row if isinstance(row, tuple) else None


def chart_row_failure(node: "MarkdownGroupNode") -> str | None:
    """Why the bullet *node*, a ``Key: value`` pair holding a value, is no
    chart row; None when it is one, or is no such pair."""
    row = _parse_chart_row(node)
    return row if isinstance(row, str) else None


def _series_header_names(node: "MarkdownGroupNode") -> list[str] | None:
    """Series names from a `Key 1, Key 2:` header text sibling."""
    if node.children or node.type not in (NodeType.TEXT, NodeType.SEGMENT):
        return None
    text = without_unit(_bare_content(node.content).rstrip(":"))
    if "," not in text:
        return None
    names = [p.strip() for p in text.split(",")]
    if any(not n for n in names):
        return None
    return names


def _header_unit(node: "MarkdownGroupNode") -> str | None:
    """The unit a short text line declares for the run below it, as in
    `Temperature (°C):` or `High, Low (°C):`; None for anything else."""
    if node.children or node.type not in (NodeType.TEXT, NodeType.SEGMENT):
        return None
    text = _bare_content(node.content).rstrip(":")
    return declared_unit(text) if len(text.split()) <= 6 else None


def _flag_chart_groups(node: "MarkdownGroupNode", in_table: bool = False) -> None:
    """Post-order: mark chart containers with ``chart_group``.

    A chart is a contiguous run of bullet items whose sole content is a
    Key: value pair in one shared unit (``_parse_chart_row``) — >=3
    single-value rows, or >=2 multi-value rows
    (each with the SAME value count N>=2) immediately preceded by a
    `Name, Name:` header of N comma-separated series names (the header is
    absorbed into the wrapper). Mirrors _flag_table_groups: the run is
    flagged in place when it is all of a node's children, else wrapped in
    a new flagged ``group`` (safe pre-node_id). Chart wins over the
    per-row kv_percent_bar flags stamped in Phase 6.06 — they are cleared
    inside the wrapper.

    Time: O(K + D), Space: O(K) worst case (rebuilt child lists).
    """
    in_table = in_table or node.table_group
    for child in node.children:
        _flag_chart_groups(child, in_table)
    if in_table or node.chart_group or not node.children:
        return

    # A short line ending in `(unit)` right above a run declares the unit its
    # bare numbers are in, which is what lets them chart.
    units = [_header_unit(c) for c in node.children]
    infos = []
    declaring: str | None = None
    for k, c in enumerate(node.children):
        declaring = units[k - 1] if k and units[k - 1] else declaring
        info = _chart_row_info(c, declared=declaring is not None)
        if info is None:
            declaring = None
        infos.append(info)
    if not any(info is not None for info in infos):
        return

    # (wrap_start, end, series names | None, first row index)
    runs: list[tuple[int, int, list[str] | None, int]] = []
    i, n = 0, len(node.children)
    while i < n:
        info = infos[i]
        if info is None:
            i += 1
            continue
        width, kind = len(info[1]), unit_kind(info[3])
        j = i + 1
        while (
            j < n
            and infos[j] is not None
            and len(infos[j][1]) == width  # type: ignore[index]
            and unit_kind(infos[j][3]) == kind  # type: ignore[index]
        ):
            j += 1
        if width == 1:
            if j - i >= 3:
                runs.append((i, j, None, i))
        elif j - i >= 2 and i > 0:
            names = _series_header_names(node.children[i - 1])
            if names is not None and len(names) == width:
                runs.append((i - 1, j, names, i))
        i = j
    if not runs:
        return

    def chart_data(series: list[str] | None, first: int, end: int) -> dict:
        shown = units[first - 1] if first else None
        chart = plain_chart(series, first, end)
        if not chart["unit"] and shown:
            return {**chart, "display_unit": shown}
        return chart

    def plain_chart(series: list[str] | None, first: int, end: int) -> dict:
        return {
            "series": series,
            "unit": _run_unit([infos[k][3] for k in range(first, end)]),  # type: ignore[index]
            "rows": [
                {
                    "label": infos[k][0],  # type: ignore[index]
                    "values": infos[k][1],  # type: ignore[index]
                    "texts": infos[k][2],  # type: ignore[index]
                }
                for k in range(first, end)
            ],
        }

    first_run = runs[0]
    if len(runs) == 1 and (first_run[0], first_run[1]) == (0, n) and not node.content:
        _clear_datapoint_displays(node)
        node.chart_group = True
        node.chart_data = chart_data(first_run[2], first_run[3], n)
        return

    new_children: list[MarkdownGroupNode] = []
    pos = 0
    for start, end, series, first in runs:
        new_children.extend(node.children[pos:start])
        wrapper = MarkdownGroupNode(type=NodeType.GROUP)
        wrapper.chart_group = True
        wrapper.chart_data = chart_data(series, first, end)
        wrapper.children = node.children[start:end]
        # Keep the wrapper a well-behaved direct child of a glued group.
        wrapper.glued_content_id = wrapper.children[0].glued_content_id
        for c in wrapper.children:
            _clear_datapoint_displays(c)
        new_children.append(wrapper)
        pos = end
    new_children.extend(node.children[pos:])
    node.children = new_children


# Why a run of line items, each drawing, stays separate lines (``check`` says).
LINES_COUNT = "a different number of points"
LINES_LABEL = "two labels at one position"

_LineRow = tuple[str, list[dict], str, str | None]


def _line_row(node: "MarkdownGroupNode", declaring: str | None) -> _LineRow | None:
    """``(series name, points, unit kind, declared unit)`` when *node* is a
    bullet item whose sole content is a ``Key: a → b → c`` pair that draws as
    a line -- its unit declared in its key or, for the run, on the line above
    (*declaring*)."""
    if node.type not in (NodeType.LIST_ITEM, NodeType.ORDERED_ITEM):
        return None
    content_kids = [c for c in node.children if _subtree_text(c)]
    if len(content_kids) != 1 or content_kids[0].type != NodeType.KEY_VALUE:
        return None
    kv = content_kids[0]
    key = next((c for c in kv.children if c.type == NodeType.KEY), None)
    value = next((c for c in kv.children if c.type == NodeType.VALUE), None)
    if key is None or value is None:
        return None
    name = _subtree_text(key)
    own = declared_unit(name) or declaring
    points = _parse_line(value, declared=own is not None)
    if not isinstance(points, list):
        return None
    dps = [d for d in _subtree_dps(value) if _value_unit(d) is not None]
    return without_unit(name), points, unit_kind(_value_unit(dps[0])) or "", own


def _merged_labels(series: list[list[dict]]) -> list[str | None] | None:
    """One label per position, from whichever series wrote it; None when two
    series label one position differently."""
    labels: list[str | None] = []
    for i in range(len(series[0])):
        written = {p[i]["tick"] for p in series if p[i]["tick"]}
        if len(written) > 1:
            return None
        labels.append(written.pop() if written else None)
    return labels


def _line_runs(node: "MarkdownGroupNode") -> list[tuple[int, int, list[_LineRow]]]:
    """Each run of two or more consecutive line items of *node* in one unit,
    as its first child, the child after its last, and its rows. A short line
    ending in ``(unit)`` right above a run declares the unit of its bare
    numbers, carried down the run as a bar chart's is (ADR-204)."""
    kids = node.children
    units = [_header_unit(c) for c in kids]
    rows: list[_LineRow | None] = []
    declaring: str | None = None
    for k, c in enumerate(kids):
        declaring = units[k - 1] if k and units[k - 1] else declaring
        rows.append(_line_row(c, declaring))
        if rows[-1] is None:
            declaring = None
    runs: list[tuple[int, int, list[_LineRow]]] = []
    i = 0
    while i < len(kids):
        row = rows[i]
        if row is None:
            i += 1
            continue
        run = [row]
        while i + len(run) < len(kids):
            other = rows[i + len(run)]
            if other is None or other[2:] != row[2:]:
                break
            run.append(other)
        if len(run) >= 2:
            runs.append((i, i + len(run), run))
        i += len(run)
    return runs


def line_run_failure(rows: list[_LineRow]) -> str | None:
    """Why a run of line items in one unit draws as separate lines, or None
    when it draws on one axis."""
    if len({len(r[1]) for r in rows}) > 1:
        return LINES_COUNT
    if _merged_labels([r[1] for r in rows]) is None:
        return LINES_LABEL
    return None


def _flag_charts(ast: "MarkdownGroupNode") -> None:
    """Bar charts first, then several lines on one axis over what is left."""
    _flag_chart_groups(ast)
    _flag_line_groups(ast)


def _flag_line_groups(node: "MarkdownGroupNode") -> None:
    """Post-order: mark several lines on one axis with ``line_group``.

    A run of line items in one unit (``_line_runs``) is one chart when every
    line has the same number of points and no two label one position
    differently (``line_run_failure``); else it stays separate lines, all of
    them, so the author is told rather than shown part of it. The keys name
    the series. Mirrors _flag_chart_groups: flagged in place when the run is
    all of the node's children, else wrapped in a new group; the rows' own
    line flags clear."""
    for child in node.children:
        _flag_line_groups(child)
    if node.chart_group or node.line_group or node.table_group or not node.children:
        return
    kids, n = node.children, len(node.children)
    flagged: list[tuple[int, int, dict]] = [
        (
            start,
            end,
            {
                "series": [{"name": r[0], "points": r[1]} for r in rows],
                "labels": _merged_labels([r[1] for r in rows]),
                "display_unit": rows[0][3],
            },
        )
        for start, end, rows in _line_runs(node)
        if line_run_failure(rows) is None
    ]
    if not flagged:
        return
    if len(flagged) == 1 and flagged[0][:2] == (0, n) and not node.content:
        _clear_datapoint_displays(node)
        node.line_group, node.line_data = True, flagged[0][2]
        return
    new_children: list[MarkdownGroupNode] = []
    pos = 0
    for start, end, data in flagged:
        new_children.extend(kids[pos:start])
        wrapper = MarkdownGroupNode(type=NodeType.GROUP)
        wrapper.line_group, wrapper.line_data = True, data
        wrapper.children = kids[start:end]
        wrapper.glued_content_id = wrapper.children[0].glued_content_id
        for c in wrapper.children:
            _clear_datapoint_displays(c)
        new_children.append(wrapper)
        pos = end
    new_children.extend(kids[pos:])
    node.children = new_children
