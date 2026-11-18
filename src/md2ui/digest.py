"""How a page grouped, in a few lines: the digest ``show`` returns.

An agent that only sends a page never sees how it grouped, and a line written as
a sentence that grouped as a key and a value is invisible until someone looks.
The whole tree is ``outline``'s, for debugging the grouping, and costs as much as a
preview; this names each section by its heading and says what it holds in the
grouper's terms — a caption, a run counted by its shape with its first member
quoted, a table's size, a count of buttons — in about a hundred tokens.

Grouping only: no columns or widths, which are the layout's to answer
(``preview``, ``screenshot``), and no labels of buttons, which ``offers`` lists.
What a value draws as — a bar, a ring, a chart — is named, because an agent
cannot tell a drawn value from text by its spelling, and guessing makes it escape
values defensively. The grouper flags a display and the theme decides whether it
draws, so the digest asks the generator's own gate rather than a copy of it.
A shell module beside ``check``; the pipeline never imports it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from md2ui.check import button_count
from md2ui.pipeline.generator_displays import (
    GeneratorContext,
    _charts_enabled,
    _dp_display_enabled,
    _lines_enabled,
    _unit_ratio_is_ring,
)
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.theme import Theme, parse_theme

# A long page keeps its first sections; the rest are counted.
MAX_LINES = 12

# What a quote keeps of a value or a line: enough to recognise it.
QUOTE_WORDS = 4

# How many of several lines are named; the count says the rest.
LINE_NAMES = 4

# Arrangement marks: they place what is around them and hold nothing.
_ARRANGEMENT = {
    NodeType.SPACER,
    NodeType.CONTENT_BREAK,
    NodeType.SECTION_STOP,
    NodeType.COLUMN_DIVIDER,
    NodeType.VERTICAL_SPRING,
    NodeType.ROW_CLOSER,
    NodeType.HORIZONTAL_RULE,
}


# What a pair's value is made of: words, a value and its unit, or a chip.
_VALUE_PIECES = {
    NodeType.TEXT,
    NodeType.SEGMENT,
    NodeType.DATAPOINT,
    NodeType.INLINE_CODE,
}

_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")

# A run of markers wrapping a whole text, as `**Total**` or `` `Passed` `` does.
_WRAP_RE = re.compile(r"([*_~`]+)(.*)\1")

# What each drawn display is called; a unit ratio is a bar unless the theme rings it.
_DISPLAY_NOUNS = {
    "kv_percent_bar": "bar",
    "ratio_bar": "bar",
    "unit_ratio": "bar",
    "date_chip": "day chip",
    "line_chart": "line chart",
}

# The theme the digest judges drawing by; None draws nothing, so every value is text.
_drawing: GeneratorContext = GeneratorContext(None, None, None)


@dataclass
class _Part:
    """One thing a section holds: *count* of *noun*, the first one *quote*d."""

    noun: str
    count: int = 1
    quote: str = ""

    def words(self) -> str:
        text = self.noun if self.count == 1 else f"{self.count} {self.noun}s"
        return f"{text} ({self.quote})" if self.quote else text


def _text(node: MarkdownGroupNode) -> str:
    """The words a node shows: a link by its label, a marker wrapping it all
    trimmed, arrangement marks left out."""
    if node.type in _ARRANGEMENT:
        return ""
    if node.content:
        text = _LINK_RE.sub(r"\1", node.content)
    else:
        text = " ".join(_text(child) for child in node.children)
    text = " ".join(text.split())
    # Only a wrap comes off: a marker that closes a chip or an emphasis inside
    # the text is half of a pair, so a heading ending in a chip keeps both.
    while (m := _WRAP_RE.fullmatch(text)) and m[1] not in m[2]:
        text = m[2].strip()
    return text


def _clip(text: str) -> str:
    words = text.split()
    clipped = " ".join(words[:QUOTE_WORDS])
    return clipped + "…" if len(words) > QUOTE_WORDS else clipped


def _is_heading(node: MarkdownGroupNode) -> bool:
    return str(node.type).startswith("heading")


def _heading(section: MarkdownGroupNode) -> MarkdownGroupNode | None:
    """The heading that names *section*: the first one in it, nearest first,
    that no section nested in it owns."""
    queue = list(section.children)
    while queue:
        node = queue.pop(0)
        if _is_heading(node):
            return node
        if not node.heading_group:
            queue += node.children
    return None


def _title(node: MarkdownGroupNode) -> str:
    """What names *node*: its heading, else its first words."""
    heading = _heading(node)
    return _text(heading) if heading is not None else _clip(_text(node))


def _drawn(node: MarkdownGroupNode) -> str | None:
    """What *node* draws as, by its own display flag or its value's, when the
    theme draws that display; None for text."""
    for flagged in (node, *node.children):
        if flagged.datapoint_display and _dp_display_enabled(_drawing, flagged):
            if flagged.datapoint_display == "unit_ratio" and _unit_ratio_is_ring(
                _drawing
            ):
                return "ring"
            return _DISPLAY_NOUNS.get(flagged.datapoint_display)
    return None


def _pair(node: MarkdownGroupNode) -> tuple[str, str] | None:
    """A label and its value, when *node* is a glued block of just those two that
    draws as one unit: a `label : value` column, or a muted `_label_` line over
    its value. The label is authored, never guessed: two lines of prose are not a
    pair, nor is a line over a muted one, which is as often a title over its
    subtitle. A value may be a chip, but not a link, which may draw as a
    button; a pair that is a link is a tappable card. None otherwise."""
    tappable = node.link_url is not None
    if node.type != NodeType.GROUP or not node.glued_content_group or tappable:
        return None
    lines = [c for c in node.children if c.type != NodeType.SPACER]
    if len(lines) != 2:
        return None
    if node.column_split_group:
        return _text(lines[0]), _text(lines[1])
    return _label_over_value(lines)


def _label_over_value(lines: list[MarkdownGroupNode]) -> tuple[str, str] | None:
    """A muted `_label_` line over its value, as a label and a value."""
    if len(lines) != 2:
        return None
    label, value = lines
    muted = [c.type == NodeType.TEXT and c.text_style == "muted" for c in lines]
    if muted != [True, False]:
        return None
    pieces = value.children or [value]
    if any(c.children or c.type not in _VALUE_PIECES for c in pieces):
        return None
    return _text(label), _text(value)


def _pair_under(
    node: MarkdownGroupNode, heading: MarkdownGroupNode | None
) -> tuple[str, str] | None:
    """A label and its value written on the lines right under *heading*: the
    grouper keeps them in the heading's section, unglued, as it keeps any lines
    tight to a heading, but they are the same pair a blank line would glue."""
    if heading is None or heading not in node.children:
        return None
    lines = [
        c for c in node.children if c is not heading and c.type not in _ARRANGEMENT
    ]
    block = heading.glued_content_id
    if block is None or any(c.glued_content_id != block for c in lines):
        return None  # lines a blank line parts, which the section collapsed in
    return _label_over_value(lines)


def _end(point: dict) -> str:
    """A line's first or last point: its value as written, and its label."""
    label = f" ({point['tick']})" if point.get("tick") else ""
    return f"{point.get('text', '')}{label}"


def _line_quote(name: str, points: list[dict]) -> str:
    """A line by its name, its point count and its two ends, so a point the
    author meant to draw and did not is visible."""
    if not points:
        return f'"{name}"'
    return f'"{name}", {len(points)} points, {_end(points[0])} → {_end(points[-1])}'


def _lines_quote(data: dict) -> str:
    """Several lines by their names, their point count, and the labels at the
    two ends when written."""
    series = data.get("series") or []
    names = ", ".join(f'"{s["name"]}"' for s in series[:LINE_NAMES])
    names += ", …" if len(series) > LINE_NAMES else ""
    points = len(series[0]["points"]) if series else 0
    labels = data.get("labels") or []
    ends = (
        f", {labels[0]} → {labels[-1]}" if labels and labels[0] and labels[-1] else ""
    )
    return f"{names}; {points} points{ends}"


def _member(node: MarkdownGroupNode) -> _Part:
    """One node as a part: what it is, and the words that identify it."""
    if node.type in (NodeType.LIST_ITEM, NodeType.ORDERED_ITEM) and node.children:
        inner = [c for c in node.children if c.type != NodeType.BULLET_POINT]
        if len(inner) == 1 and inner[0].type == NodeType.KEY_VALUE:
            return _member(inner[0])
        noun = "list item" if node.type == NodeType.LIST_ITEM else "numbered item"
        return _Part(noun, quote=f'"{_clip(_text(node))}"')
    drawn = _drawn(node)
    if node.type == NodeType.KEY_VALUE and len(node.children) == 2:
        key, value = (_text(c) for c in node.children)
        if drawn == "line chart" and node.datapoint_display == "line_chart":
            points = (node.datapoint_payload or {}).get("points") or []
            return _Part(drawn, quote=_line_quote(key, points))
        noun = drawn or "key–value item"
        return _Part(noun, quote=f'"{key}" → "{_clip(value)}"')
    if drawn is not None:
        return _Part(drawn, quote=f'"{_clip(_text(node))}"')
    pair = _pair(node)
    if pair is not None:
        return _Part("pair", quote=f'"{_clip(pair[0])}" → "{_clip(pair[1])}"')
    if node.type == NodeType.IMAGE:
        return _Part("picture")
    if node.type == NodeType.INLINE_CODE:
        return _Part("chip")
    if node.type == NodeType.TEXT:
        return _Part("text", quote=f'"{_clip(_text(node))}"')
    if node.children:
        noun = "tappable card" if node.link_url is not None else "card"
        return _Part(noun, quote=f'"{_title(node)}"')
    if _is_heading(node):
        return _Part("heading", quote=f'"{_text(node)}"')
    return _Part(str(node.type).replace("_", " "))


def _parts(node: MarkdownGroupNode, heading: MarkdownGroupNode | None) -> list[_Part]:
    """What *node* holds, in order, inside the section *heading* names."""
    if node is heading or node.type in _ARRANGEMENT:
        return []
    buttons = button_count(node)
    if buttons is not None:
        return [_Part("button", buttons)]
    if node.chart_group and _charts_enabled(_drawing):
        rows = [c for c in node.children if c.type != NodeType.TEXT]
        first = _member(rows[0]) if rows else _Part("")
        return [_Part(f"chart of {len(rows)} rows", quote=first.quote)]
    if node.line_group and _lines_enabled(_drawing):
        data = node.line_data or {}
        count = len(data.get("series") or [])
        return [_Part(f"chart of {count} lines", quote=_lines_quote(data))]
    if node.datapoint_display and _drawn(node) is not None:
        return [_member(node)]
    if node.table_group:
        rows = [c for c in node.children if c.type == NodeType.TABLE_ROW]
        cols = max((len(c.children) for c in node.children), default=0)
        return [_Part(f"table {len(rows)}×{cols}")]
    if _pair(node) is not None:  # one unit, though its two lines may be a run
        return [_member(node)]
    holds_heading = heading is not None and _holds(node, heading)
    # A chart is named for what it draws, also beside the `(unit)` line above it.
    holds_chart = any(c.chart_group or c.line_group for c in node.children)
    if not holds_heading and not _runs(node) and not node.line_split_group:
        if not holds_chart and (node.type != NodeType.GROUP or len(node.children) != 1):
            return [_member(node)]  # a leaf, or a card: its contents are its own
    parts = [
        item if isinstance(item, _Part) else _member(item)
        for item in _contents(node, heading)
    ]
    if holds_heading:  # a text beside the heading, in its group, captions it
        parts = [_Part("caption") if p.noun == "text" else p for p in parts]
    return parts


def _runs(node: MarkdownGroupNode) -> list[list[MarkdownGroupNode]]:
    return [run for run in (node.repeated_children or {}).values() if len(run) > 1]


def _is_card(node: MarkdownGroupNode) -> bool:
    """A heading over leaves: a card that happens to have a title, not a section."""
    return all(not c.children or _is_heading(c) for c in node.children)


def _contents(
    node: MarkdownGroupNode, heading: MarkdownGroupNode | None
) -> list[_Part | MarkdownGroupNode]:
    """*node*'s children in order, as parts, with each repeated run counted
    once, and each subsection left as its node for a line of its own. A run of
    titled cards is a run, not as many sections."""
    pair = _pair_under(node, heading)
    if pair is not None:
        return [_Part("pair", quote=f'"{_clip(pair[0])}" → "{_clip(pair[1])}"')]
    runs = _runs(node)
    run_of = {id(m): i for i, run in enumerate(runs) for m in run}
    out: list[_Part | MarkdownGroupNode] = []
    seen: set[int] = set()
    for child in node.children:
        if child.type in _ARRANGEMENT:
            continue
        at = run_of.get(id(child))
        if at is not None and child.heading_group and not all(map(_is_card, runs[at])):
            at = None
        if at is None:
            out += [child] if child.heading_group else _parts(child, heading)
        elif at not in seen:
            seen.add(at)
            first = _member(child)
            noun = "button" if button_count(child) == 1 else first.noun
            if noun == "tappable card" and any(m.link_url is None for m in runs[at]):
                noun = "card"  # `check` notes the mix
            quote = "" if noun in ("button", "picture") else first.quote
            out.append(_Part(noun, len(runs[at]), quote))
    return out


def _holds(node: MarkdownGroupNode, target: MarkdownGroupNode) -> bool:
    return node is target or any(_holds(c, target) for c in node.children)


def _merged(parts: list[_Part]) -> list[_Part]:
    """Neighbouring parts of one unquoted noun, counted together."""
    out: list[_Part] = []
    for part in parts:
        if out and not part.quote and not out[-1].quote and out[-1].noun == part.noun:
            out[-1] = _Part(part.noun, out[-1].count + part.count)
        else:
            out.append(part)
    return out


def _line(label: str, parts: list[_Part]) -> str:
    return f"{label}: " + " · ".join(p.words() for p in _merged(parts))


def _section(node: MarkdownGroupNode, label: str, lines: list[str]) -> None:
    """*node*'s own parts on one line under *label*, then each subsection's; a
    part after a subsection is no longer this heading's, so it takes a line of
    its own."""
    heading = _heading(node) if node.heading_group else None
    parts: list[_Part] = []
    after_subsection = False
    for item in _contents(node, heading):
        if isinstance(item, _Part) and not after_subsection:
            parts.append(item)
        elif isinstance(item, _Part):
            lines.append(_line("row" if item.noun == "button" else "then", [item]))
        else:
            if parts:
                lines.append(_line(label, parts))
                parts = []
            _section(item, _title(item), lines)
            after_subsection = True
    if parts:
        lines.append(_line(label, parts))


def theme_at(path: Path | None) -> Theme:
    """The theme the window draws with: the file, else md2ui's built-in defaults."""
    return parse_theme(path) if path is not None else Theme()


def digest(ast: MarkdownGroupNode | None, theme: Theme | None = None) -> str:
    """How *ast* grouped, one line per section, named by its heading; with
    *theme*, each value it draws is named by what it draws as."""
    global _drawing
    _drawing = GeneratorContext(theme, None, None)
    lines: list[str] = []
    if ast is not None:
        _section(ast, "page", lines)
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES] + [f"… {len(lines) - MAX_LINES} more lines"]
    return "\n".join(lines)
