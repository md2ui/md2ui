"""A message's sections as its author wrote them (ADR-611).

An agent names a section the way it wrote it: by its ``{#id}``, or, when it gave
none, by the heading's words. Under the heading it may say where the section came
from and how long that stays true, on one comment that draws nothing:

    ## 🧩 md2ui repo
    <!-- from: git status; fresh: 5m -->

This reads the Markdown the server sent, and no grouping: a section's name and
its comment are what the author typed, so they are found where the author typed
them. Headings are recognised exactly as the grouper recognises them
(``MarkdownGrouper.HEADING_PATTERN`` and ``HEADING_ID_PATTERN``), outside fences,
and a section's lines end where the grouper ends it. That extent is only where
``wire_patch`` looks: a patch is kept only when regrouping agrees.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from md2ui.pipeline.grouper_block_splits import _PARTITION_TYPES, _break_node_type
from md2ui.pipeline.grouper_types import NodeType
from md2ui.pipeline.markdown_grouper import MarkdownGrouper

_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL)
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
# A marked run is at most 256 characters: unbounded, every opener with no closer
# is scanned to the line's end, which is quadratic on a long line.
_MARKED = re.compile(r"(?<!\w)(\*{1,3}|_{1,3}|~~|`)(\S(?:.{0,254}?\S)?)\1(?!\w)")
_DURATION = re.compile(r"(\d+(?:\.\d+)?)\s*(s|m|h|d)", re.IGNORECASE)
_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


@dataclass(frozen=True, slots=True)
class Section:
    """One heading section: its name, its comment, and the lines it owns."""

    name: str  # what the agent addresses it by: its {#id}, else ``title``
    title: str  # the heading's words; "" for an id-only heading
    level: int
    line: int  # the heading's line, 0-based
    source: str | None  # the comment's ``from:``
    fresh: str | None  # the comment's ``fresh:``, as written
    start: int  # the section's first line: the heading, or a run glued above it
    end: int  # past its last line, as the grouper closes it
    closed: bool  # ended by its own ``***``, the line before ``end``

    @property
    def fresh_s(self) -> float | None:
        """The ``fresh:`` limit in seconds; None when absent or unreadable."""
        return _seconds(self.fresh) if self.fresh else None


def _words(text: str) -> str:
    """A heading as it reads: links by their labels, without their markers."""
    text = _MARKED.sub(r"\2", _LINK.sub(r"\1", text))
    return " ".join(text.split()).strip("*_~` ")


def _seconds(text: str) -> float | None:
    found = _DURATION.fullmatch(text.strip())
    if found is None:
        return None
    return float(found.group(1)) * _SECONDS[found.group(2).lower()]


def _notes(body: list[str]) -> tuple[str | None, str | None]:
    """The ``from:`` and ``fresh:`` of the first comment in *body* that has either."""
    for comment in _COMMENT.finditer("\n".join(body)):
        fields = {}
        for part in comment.group(1).split(";"):
            key, colon, value = part.partition(":")
            if colon:
                fields[key.strip().lower()] = value.strip()
        if "from" in fields or "fresh" in fields:
            return fields.get("from") or None, fields.get("fresh") or None
    return None, None


def _scan(lines: list[str]) -> tuple[list[tuple[int, int, str]], set[int]]:
    """``(line, level, text)`` for each heading outside a fence, and the lines
    outside a fence that are breaks of any kind (``grouper_block_splits``)."""
    headings: list[tuple[int, int, str]] = []
    breaks: set[int] = set()
    fence: str | None = None
    for i, line in enumerate(lines):
        opened = _FENCE.match(line)
        if fence is not None:
            if (
                opened
                and opened.group(1)[0] == fence[0]
                and len(opened.group(1)) >= len(fence)
            ):
                fence = None
            continue
        if opened:
            fence = opened.group(1)
            continue
        if _break_node_type(line) is not None:
            breaks.add(i)
            continue
        heading = MarkdownGrouper.HEADING_PATTERN.match(line)
        if heading:
            headings.append((i, len(heading.group(1)), line.lstrip("# ")))
    return headings, breaks


def _peel_start(lines: list[str], line: int, heading_lines: set[int]) -> int:
    """Where *line*'s heading section begins: a run glued above it is the
    heading's, unless it runs out of the previous heading (the grouper's peel)."""
    run, j = line, line - 1
    while j >= 0 and lines[j].strip() and j not in heading_lines:
        kind = _break_node_type(lines[j])
        if kind is not None and kind not in _PARTITION_TYPES:
            break
        run, j = j, j - 1
    return line if j >= 0 and j in heading_lines else run


def _end(
    lines: list[str],
    headings: list[tuple[int, int, str]],
    k: int,
    stops: set[int],
    starts: list[int],
) -> tuple[int, bool]:
    """Where heading *k*'s section ends: at the next heading of its level or
    above, less the run that heading peels, or past the ``***`` that closes it.
    A stop closes the innermost open section, as ``_apply_section_stops`` does."""
    line, level, _text = headings[k]
    open_levels = [level]
    later = {h[0]: (n, h[1]) for n, h in enumerate(headings) if h[0] > line}
    for j in range(line + 1, len(lines)):
        if j in later:
            n, deeper = later[j]
            if deeper <= level:
                return starts[n], False
            while open_levels[-1] >= deeper:
                open_levels.pop()
            open_levels.append(deeper)
        elif j in stops:
            open_levels.pop()
            if not open_levels:
                return j + 1, True
    return len(lines), False


def sections(markdown: str) -> list[Section]:
    """Every section of *markdown*, in the order written."""
    lines = markdown.split("\n")
    headings, breaks = _scan(lines)
    stops = {i for i in breaks if _break_node_type(lines[i]) == NodeType.SECTION_STOP}
    heading_lines = {h[0] for h in headings}
    starts = [_peel_start(lines, h[0], heading_lines) for h in headings]
    out: list[Section] = []
    for k, (line, level, text) in enumerate(headings):
        attr = MarkdownGrouper.HEADING_ID_PATTERN.search(text)
        heading_id = attr.group(1) if attr else None
        title = _words(text[: attr.start()] if attr else text)
        body_end = headings[k + 1][0] if k + 1 < len(headings) else len(lines)
        source, fresh = _notes(lines[line + 1 : body_end])
        end, closed = _end(lines, headings, k, stops, starts)
        name = heading_id or title
        out.append(
            Section(name, title, level, line, source, fresh, starts[k], end, closed)
        )
    return out


def heading_groups(tree: dict) -> list[dict]:
    """The grouped tree's heading sections, in document order: the k-th is the
    k-th of ``sections``, when the two counts agree."""
    found: list[dict] = []

    def walk(node: dict) -> None:
        if node.get("heading_group"):
            found.append(node)
        for child in node.get("children") or []:
            walk(child)

    walk(tree)
    return found


def target_sections(markdown: str, tree: dict, keys: list[str]) -> list[str | None]:
    """The name of the innermost section holding each target, by its ``key``
    (``render_actions.Target``); None outside every section, or for every target
    when the tree's sections are not the source's."""
    named = sections(markdown)
    groups = heading_groups(tree)
    if len(groups) != len(named):
        return [None] * len(keys)
    ids = [(g.get("node_id", ""), s.name) for g, s in zip(groups, named)]
    out: list[str | None] = []
    for key in keys:
        node = key.split("#")[0]
        holders = [n for i, n in ids if node == i or node.startswith(i + ".")]
        out.append(holders[-1] if holders else None)
    return out


def unread_limits(markdown: str) -> list[Section]:
    """The sections whose ``fresh:`` is no duration, so no clock can run out."""
    return [s for s in sections(markdown) if s.fresh and s.fresh_s is None]


def title(markdown: str) -> str:
    """What names a page: its first heading's words, else its first line's."""
    for section in sections(markdown):
        if section.title:
            return section.title
    for line in markdown.split("\n"):
        if _words(line):
            return _words(line)[:80]
    return ""
