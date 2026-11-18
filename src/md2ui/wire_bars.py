"""A static bar, addressed by the key its author wrote.

A bar (``Elapsed: 45%``, ``Files: 3/10``, a ``- CPU: 40%`` or ``- Q1: $1,200``
chart row) is not an actionable target, so it has no ordinal for an event or a
``mark`` to name. The agent names the KEY instead, and the server moves the bar
in its own copy of the Markdown, the way ``wire.set_slider_markdown`` moves a
slider: the spelling is kept and the domain is the bar's own. The result goes
out as an ordinary replacement message (ADR-601), so the wire needs nothing new.

What a bar is comes from the grouper's annotations (ADR-100), never from the
Markdown: the patterns here only locate candidate figures, and an edit is
kept only when regrouping shows it moved exactly that bar.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from md2ui import session
from md2ui.pipeline.render_actions import action_targets
from md2ui.wire_frames import FrameError

# A percentage's figure, and a ratio's numerator with its denominator kept.
_PERCENT_FIGURE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?%")
_RATIO_FIGURE = re.compile(r"(?<![\w./])(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)")
_RATIOS = ("unit_ratio", "ratio_bar")
# A chart row's figure as written: what precedes it (`$`), its digits with any
# thousands commas and decimals, a magnitude letter, and what follows (` EUR`).
_WRITTEN = re.compile(r"^(\D*?)(\d[\d,]*)(?:\.(\d+))?([KMB]?)(.*)$")
_MAGNITUDE = {"": 1.0, "K": 1e3, "M": 1e6, "B": 1e9}


@dataclass(frozen=True, slots=True)
class Figure:
    """A chart row's figure as its author wrote it (``$1,200``, ``1.2K``,
    ``40%``), and the unit its chart declared above the rows (``ms``), if any:
    how a new value is spelled on the page, and how a post may spell one."""

    written: str
    declared: str | None = None

    def spellings(self, value: float) -> list[str]:
        """*value* in this spelling: its symbols, its magnitude letter and at
        least its decimals. Thousands commas follow the figure when it is long
        enough to show them, else the value, then the other choice is offered:
        `$980` grows into `$1,500`, since `$1500` reads as no currency a chart
        takes."""
        m = _WRITTEN.match(self.written)
        if m is None:
            return []
        head, digits, decimals, magnitude, tail = m.groups()
        x = value / _MAGNITUDE[magnitude]
        places = max(len(decimals or ""), len(f"{x:.6f}".rstrip("0").split(".")[1]))
        known = len(digits.replace(",", "")) > 3
        commas = "," in digits if known else x >= 1000
        figures = dict.fromkeys(
            f"{x:,.{places}f}" if c else f"{x:.{places}f}" for c in (commas, not commas)
        )
        return [head + figure + magnitude + tail for figure in figures]

    def spell(self, value: float) -> str:
        return next(iter(self.spellings(value)), f"{value:g}")

    def read(self, text: str) -> float | None:
        """The value *text* writes in this spelling, its declared unit after it,
        or bare; None when it is written in another unit."""
        own, got = _WRITTEN.match(self.written), _WRITTEN.match(text.strip())
        if own is None or got is None:
            return None
        sign, head = _signed(got[1])
        _, digits, decimals, magnitude, tail = got.groups()
        marks = (head, tail.strip())
        if marks not in (
            (_signed(own[1])[1], own[5].strip()),
            ("", ""),
            ("", self.declared or ""),
        ):
            return None
        number = digits.replace(",", "") + (f".{decimals}" if decimals else "")
        return sign * float(number) * _MAGNITUDE[magnitude]


def _signed(head: str) -> tuple[float, str]:
    """A minus sign before a figure (`-5`, `-$5`, `$-5`) is the value's, not its
    spelling's, so a negative post reaches the domain check instead of reading
    as another unit."""
    if head.startswith("-"):
        return -1.0, head[1:]
    return (-1.0, head[:-1]) if head.endswith("-") else (1.0, head)


def _bare(text: str) -> str:
    return text.strip().strip("*_`").strip()


def _read(markdown: str, kit: session.GroupingKit) -> tuple[list, list, list]:
    """The document's drawn values in order, the keyed bars among them, and its
    targets' actions -- everything an edit must leave alone, from one grouping."""
    ast = session.group_shared(markdown, kit)
    if ast is None:
        return [], [], []
    tree = ast.to_dict()
    shown, bars = _drawn(tree)
    return shown, bars, [t.action for t in action_targets(tree)]


def bar_keys(tree: dict) -> list[str]:
    """The key of each bar a grouped page (``to_dict``) draws: the names a feed
    moves a bar by, which no slot may also take (``check_feeds``)."""
    return [bar[0] for bar in _drawn(tree)[1]]


def _drawn(tree: dict) -> tuple[list, list]:
    """A grouped page's drawn values in order, and the keyed bars among them.

    A bar is ``(key, index, values, ceiling, figure, unit)``: *index* is its
    place among the drawn values, *ceiling* is None for a percentage and infinite
    for a chart row in any other unit, *figure* is a chart row's :class:`Figure`
    (None off a chart), and *unit* is what a ratio writes after it (``GB``, else
    empty). It is what the grouper drew under a
    key: a key-value percent bar, a key-value ratio (stamped on the pair, or on
    its value when the value carries a unit), or a chart row.
    """
    shown: list = []
    bars: list = []

    def walk(d: dict, key: str | None) -> None:
        if d.get("chart_group"):
            # A percentage chart scales against 100; any other unit against
            # its data, which a value below zero turns into change data.
            percent = d["chart_data"].get("unit") == "%"
            ceiling = None if percent else math.inf
            declared = d["chart_data"].get("display_unit")
            for row in d["chart_data"]["rows"]:
                label, values = _bare(row["label"]), row["values"]
                figure = Figure(row["texts"][0], declared)
                bars.append((label, len(shown), values, ceiling, figure, ""))
                shown.append(("chart", row["label"], values))
            return
        if d.get("line_group"):
            shown.append(("lines", d["line_data"]))
            return
        pair = d["type"] == "key-value"
        if pair:
            key = next(
                (_bare(c["content"]) for c in d["children"] if c["type"] == "key"), None
            )
        kind = d.get("datapoint_display")
        if kind is not None:
            p = d["datapoint_payload"]
            if key is not None and kind == "kv_percent_bar":
                bars.append((key, len(shown), [p["percent"]], None, None, ""))
            elif key is not None and kind in _RATIOS:
                # A pair's own key stands in as the unit of a bare `Files: 3/10`.
                unit = "" if p.get("from_kv") else p.get("unit", "")
                bars.append((key, len(shown), [p["value"]], p["max"], None, unit))
            shown.append((kind, sorted(p.items())))
        for c in d["children"]:
            # A pair's key reaches its own display and its value's, no deeper.
            walk(c, key if pair and kind is None and c["type"] == "value" else None)

    walk(tree, None)
    return shown, bars


def bars(
    markdown: str, kit: session.GroupingKit
) -> list[tuple[str, list[float], float | None, Figure | None, str]]:
    """Each bar the document draws under a key, as ``(key, values, ceiling,
    figure, unit)``: what a feed may be given to move (ADR-608)."""
    return [
        (key, values, ceiling, figure, unit)
        for key, _, values, ceiling, figure, unit in _read(markdown, kit)[1]
    ]


def check_domain(key: str, value: float, ceiling: float | None) -> None:
    """Refuse *value* outside the domain of the bar under *key* (``bad_value``)."""
    top = 100.0 if ceiling is None else ceiling
    if not 0.0 <= value <= top:
        domain = "0 or more" if math.isinf(top) else f"0 to {top:g}"
        raise FrameError(
            "bad_value", f"{value:g} is outside the domain of `{key}`, {domain}"
        )


def _lines_naming(markdown: str, key: str) -> str:
    at = [
        str(n)
        for n, line in enumerate(markdown.split("\n"), 1)
        if key in line and any(ch.isdigit() for ch in line)
    ]
    return ", ".join(at[:-1]) + " and " + at[-1] if len(at) > 1 else "".join(at)


def set_bar_markdown(
    markdown: str, key: str, value: float, kit: session.GroupingKit
) -> str:
    """*markdown* with the bar written under *key* at *value*, and nothing else.

    Refused (``FrameError``): a value outside the bar's domain (0-100, 0 to its
    denominator, or 0 or more for a chart row in a unit other than `%`), a key no
    bar is written under, and a key written under more than one -- with their
    lines, so the agent can re-send instead. The edit is found, not computed:
    each figure equal to the bar's value is tried, those on a line naming the
    key first, and the first whose regrouping moves only this bar, with every
    other drawn value and every target unchanged, is kept.
    """
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise FrameError("bad_value", str(value))
    name = _bare(key)
    shown, bars, targets = _read(markdown, kit)
    found = [b for b in bars if b[0] == name]
    if not found:
        keys = ", ".join(dict.fromkeys(b[0] for b in bars)) or "none"
        raise FrameError("bad_target", f"no bar keyed {key!r}; bars here: {keys}")
    if len(found) > 1:
        lines = _lines_naming(markdown, name)
        raise FrameError(
            "bad_target",
            f"{key!r} keys {len(found)} bars (lines {lines}); re-send the answer",
        )
    _name, index, values, ceiling, figure, _unit = found[0]
    if len(values) != 1:
        raise FrameError(
            "bad_target", f"{key!r} is a chart row of {len(values)} values"
        )
    check_domain(key, value, ceiling)
    if values[0] == float(value):
        return markdown
    # Each edit is (start, end, replacement): a chart row's figure is found as
    # written and respelled, any other bar's number is rewritten in place.
    edits: list[tuple[int, int, str]] = []
    if figure is not None:
        found_at = re.compile(rf"(?<![\w.,]){re.escape(figure.written)}(?![\w.]|,\d)")
        edits = [
            (m.start(), m.end(), spelled)
            for m in found_at.finditer(markdown)
            for spelled in figure.spellings(float(value))
        ]
    else:
        number = _PERCENT_FIGURE if ceiling is None else _RATIO_FIGURE
        edits = [
            (m.start(1), m.end(1), f"{float(value):g}")
            for m in number.finditer(markdown)
            if float(m.group(1)) == values[0]
            and (ceiling is None or float(m.group(2)) == ceiling)
        ]
    lines = markdown.split("\n")
    named = {n for n, line in enumerate(lines) if name in line}
    edits.sort(key=lambda e: markdown.count("\n", 0, e[0]) not in named)
    for start, end, text in edits:
        candidate = markdown[:start] + text + markdown[end:]
        after, moved, now = _read(candidate, kit)
        if (
            now == targets
            and len(after) == len(shown)
            and all(a == b for i, (a, b) in enumerate(zip(after, shown)) if i != index)
            and (name, index, [float(value)], ceiling) in [b[:4] for b in moved]
        ):
            return candidate
    raise FrameError("bad_target", f"no source edit changes only the bar {key!r}")
