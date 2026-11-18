"""Includes: lines a backend expands from its own data (ADR-612, proposed).

An agent writes ``{{cart}}`` or ``{{order BS-1042}}`` on a line of its own; the
server replaces the line with the Markdown the backend draws for it, before the
page is recorded, so the log, the ordinals, ``check`` and the window all see the
real page. The agent never types a figure an include draws.

**A failure draws no braces** (ADR-612): an include that
cannot be drawn (no such name on a server that has includes, args that do not
read, an expander that raised) draws the failure line its backend registered,
in the theme's muted tier, or nothing: md2ui writes no words of its own on the
page. It is still the include's region, so a later redraw replaces it, and the
region says why (``Region.failed``), so ``check`` and the handled-click digest
tell the agent.

**What is an include.** A line holding exactly one ``{{name args}}``, starting at
its first column, with a blank line (or the document's edge) before and after it,
outside a fenced code block, at the page's top level: one between list items or
in a cell of a ``:::`` row is left as written, and ``unexpanded`` warns, since the
Markdown it draws (a heading, say) would take the rest of the list or the row's
bound into its own section. A ``{{…}}`` inside text is never one: inline braces
are left to another proposal (variable-replacement). Args are read as the burger
shop's ``pages.py`` reads them: ``key=value``, ``key="two words"`` and bare words.

**Regions.** Each expanded include is a run of lines in the page, kept with the
include line it came from, so a backend's handler can redraw it when its data
changes (``wire_includes``) and the source can be given back. When the server
edits a page (``mark``, a feed's tick, a commit, a ``patch``), each region is
carried to the new page through a line diff. An agent's edit that touches a
region is refused (``Expansions.refuse``): what an include draws is the backend's.

A static set of includes, for evals, is a folder of ``<name>.md`` files beside a
theme (``static_includes``): ANY call of a known name expands to the file's body.

A shell module beside ``check``; the pipeline never imports it.
"""

from __future__ import annotations

import difflib
import re
import shlex
import sys
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

from md2ui.pipeline.grouper_block_splits import _break_node_type
from md2ui.pipeline.grouper_types import NodeType
from md2ui.wire_frames import FrameError

# One `{{name args}}` alone on its line. The args hold no `{{` or `}}`, so a line
# with two includes on it is neither.
INCLUDE_LINE = re.compile(
    r"^\{\{\s*(?P<name>[A-Za-z][\w-]*)(?P<args>(?:(?!\{\{|\}\}).)*?)\s*\}\}[ \t]*$"
)
NAME = re.compile(r"^[A-Za-z][\w-]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_LIST_ITEM = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])(?:[ \t]|$)")
_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]|$)")
# The lines that end a `:::` row's run of siblings (grouper_column_rows).
_ROW_BOUNDS = (NodeType.CONTENT_BREAK, NodeType.SECTION_STOP, NodeType.ROW_CLOSER)
_FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)
UNKNOWN = "unknown"  # a region's ``failed`` when no include has its name


@dataclass(frozen=True, slots=True)
class Args:
    """An include line's args: bare ``words`` in order, and ``named`` ones."""

    words: tuple[str, ...] = ()
    named: Mapping[str, str] = field(default_factory=dict)


def parse_args(text: str) -> Args:
    """*text* as ``key=value``, ``key="quoted"`` and bare words (the shop's
    ``pages._args``). An unclosed quote raises ValueError."""
    words: list[str] = []
    named: dict[str, str] = {}
    for token in shlex.split(text.strip()):
        if "=" in token:
            key, value = token.split("=", 1)
            named[key.strip()] = value.strip()
        elif token.strip(","):
            words.append(token.strip(","))
    return Args(tuple(words), named)


@dataclass(frozen=True, slots=True)
class Include:
    """One include a backend offers: ``expand(args)`` returns its Markdown."""

    name: str
    description: str
    expand: Callable[[Args], str]
    args: str = ""  # how the args are written, for the agent: `<order id>`
    failure: str = ""  # the line shown, muted, when it cannot be drawn; else none

    def row(self) -> str:
        """The include's line in ``guide("includes")``."""
        call = f"{self.name} {self.args}".strip()
        return f"- {{{{{call}}}}}: {self.description}"


class Includes:
    """The includes a backend registered, by name."""

    def __init__(self) -> None:
        self._by_name: dict[str, Include] = {}

    def add(
        self,
        name: str,
        description: str,
        expand: Callable[[Args], str],
        args: str = "",
        failure: str = "",
    ) -> None:
        """Register *name*. *failure* is the line the user sees, muted, when it
        cannot be drawn, in your users' language; without one, nothing is."""
        if not NAME.match(name):
            raise ValueError(f"an include's name is a word: {name!r}")
        words = " ".join(description.split())
        self._by_name[name] = Include(
            name, words, expand, args, " ".join(failure.split())
        )

    def get(self, name: str) -> Include | None:
        return self._by_name.get(name)

    def __len__(self) -> int:
        return len(self._by_name)

    def rows(self) -> list[str]:
        return [self._by_name[n].row() for n in sorted(self._by_name)]


@dataclass(frozen=True, slots=True)
class Region:
    """Lines ``start`` to ``end`` (exclusive) of a page, drawn by ``line``.
    ``failed`` is why they are its failure line (or none): the error's class,
    or :data:`UNKNOWN`; empty when the include drew."""

    line: str
    start: int
    end: int
    failed: str = ""

    @property
    def name(self) -> str:
        found = INCLUDE_LINE.match(self.line)
        return found.group("name") if found else ""


def _unfenced(lines: list[str]) -> list[bool]:
    """Whether each of *lines* is outside a fenced code block (and no fence)."""
    out, fence = [], ""
    for line in lines:
        opened = _FENCE.match(line)
        if fence:
            if (
                opened
                and opened.group(1)[0] == fence[0]
                and len(opened.group(1)) >= len(fence)
            ):
                fence = ""
            out.append(False)
        elif opened:
            fence = opened.group(1)
            out.append(False)
        else:
            out.append(True)
    return out


def _in_rows(lines: list[str], text: list[bool]) -> list[bool]:
    """Whether each line is in a cell of a ``:::`` row: the run around a divider,
    from its section's heading (or the last ``___``, ``***``, ``;;;``) to the next
    bound, or the next heading that closes its section. A heading in that run
    opens a section inside a cell, as ``grouper_column_rows`` builds it."""
    kinds = [_break_node_type(line) if ok else None for line, ok in zip(lines, text)]
    levels = [
        len(found.group(1)) if ok and (found := _HEADING.match(line)) else 0
        for line, ok in zip(lines, text)
    ]
    inside = [False] * len(lines)
    for d, kind in enumerate(kinds):
        if kind != NodeType.COLUMN_DIVIDER:
            continue
        start = d
        while start > 0 and kinds[start - 1] not in _ROW_BOUNDS and not levels[start]:
            start -= 1
        above = d  # the section the row forms in: its heading's level; 0, the top
        while above > 0 and not levels[above] and kinds[above] != NodeType.SECTION_STOP:
            above -= 1
        level = levels[above]
        end = d + 1
        while end < len(lines) and kinds[end] not in _ROW_BOUNDS:
            if levels[end] and level and levels[end] <= level:
                break
            end += 1
        inside[start:end] = [True] * (end - start)
    return inside


def _between_items(lines: list[str], i: int) -> bool:
    """Whether line *i* sits between two items of a list."""
    above = next((x for x in reversed(lines[:i]) if x.strip()), "")
    below = next((x for x in lines[i + 1 :] if x.strip()), "")
    listed = bool(_LIST_ITEM.match(above)) or above[:1] in (" ", "\t")
    return listed and bool(_LIST_ITEM.match(below))


def _lone_lines(lines: list[str]) -> Iterator[tuple[int, re.Match[str], bool]]:
    """Each lone ``{{…}}`` line of *lines* outside code fences, by index, and
    whether it is nested: between list items, or in a ``:::`` row's cell."""
    text = _unfenced(lines)
    rows: list[bool] | None = None
    for i, line in enumerate(lines):
        found = INCLUDE_LINE.match(line) if text[i] else None
        if not found:
            continue
        before = i == 0 or not lines[i - 1].strip()
        after = i == len(lines) - 1 or not lines[i + 1].strip()
        if before and after:
            rows = rows if rows is not None else _in_rows(lines, text)
            yield i, found, rows[i] or _between_items(lines, i)


def include_lines(lines: list[str]) -> Iterator[tuple[int, re.Match[str]]]:
    """Each line of *lines* that is an include, by index: lone, outside code
    fences, at the top level."""
    for i, found, nested in _lone_lines(lines):
        if not nested:
            yield i, found


def _draw(include: Include | None, args: str) -> tuple[list[str], str]:
    """The lines *include* draws for *args*, and ``""``; or, when there is no
    such include, its args do not read or its backend failed, the failure line
    it registered, in the muted tier (else no line), and why
    (``Region.failed``). The error's text goes to stderr only: it is the
    backend's."""
    if include is None:
        return [], UNKNOWN
    try:
        text = include.expand(parse_args(args))
    except Exception as exc:  # noqa: BLE001 -- a failure draws no braces
        print(f"[includes] {{{{{include.name}}}}} failed: {exc!r}", file=sys.stderr)
        failure = [f"_{include.failure}_"] if include.failure else []
        return failure, type(exc).__name__
    text = text.strip("\n")
    return (text.split("\n") if text.strip() else []), ""


def expand(markdown: str, includes: Includes) -> tuple[str, tuple[Region, ...]]:
    """*markdown* with every include line it holds replaced by its Markdown, and
    the region each one drew. One that cannot be drawn draws its failure line
    or nothing (``failed``). With no includes at all, nothing is one: a lone
    ``{{name}}`` there is text about a template, and ``unexpanded`` warns."""
    if not includes:
        return markdown, ()
    lines = markdown.split("\n")
    regions: list[Region] = []
    for i, found in reversed(list(include_lines(lines))):
        include = includes.get(found.group("name"))
        body, failed = _draw(include, found.group("args"))
        lines[i : i + 1] = body
        shift = len(body) - 1
        regions = [
            replace(r, start=r.start + shift, end=r.end + shift) for r in regions
        ]
        regions.insert(0, Region(found.group(0).strip(), i, i + len(body), failed))
    return "\n".join(lines), tuple(regions)


def redraw(
    markdown: str, regions: tuple[Region, ...], includes: Includes, names: set[str]
) -> tuple[str, tuple[Region, ...]]:
    """*markdown* with the regions of the includes *names* drawn again from the
    backend's data now. One that cannot be drawn now draws its failure line or
    nothing, and one that failed before draws again once it can."""
    lines = markdown.split("\n")
    out = list(regions)
    for k in reversed(range(len(out))):
        region = out[k]
        found = INCLUDE_LINE.match(region.line)
        if found is None or region.name not in names:
            continue
        body, failed = _draw(includes.get(region.name), found.group("args"))
        lines[region.start : region.end] = body
        shift = len(body) - (region.end - region.start)
        out[k] = replace(region, end=region.start + len(body), failed=failed)
        out[k + 1 :] = [
            replace(r, start=r.start + shift, end=r.end + shift) for r in out[k + 1 :]
        ]
    return "\n".join(lines), tuple(out)


def source(markdown: str, regions: tuple[Region, ...]) -> str:
    """The page as the agent would write it: each region its include line."""
    lines = markdown.split("\n")
    for region in reversed(regions):
        lines[region.start : region.end] = [region.line]
    return "\n".join(lines)


def _moved(p: int, ops: list, start: bool) -> int | None:
    """Where line boundary *p* of the old page is in the new one; None when an
    edit spans it. A start keeps what was added before it outside, an end what
    was added after it."""
    for tag, i1, i2, j1, j2 in ops:
        if tag != "equal" and (i2 == p if start else i1 == p):
            return j2 if start else j1
    for tag, i1, i2, j1, _j2 in ops:
        if tag == "equal" and i1 <= p <= i2:
            return j1 + p - i1
    return None


def carry(old: str, new: str, regions: tuple[Region, ...]) -> tuple[Region, ...]:
    """*regions* of the page *old*, found again in its edit *new*."""
    ops = difflib.SequenceMatcher(
        None, old.split("\n"), new.split("\n"), autojunk=False
    ).get_opcodes()
    out: list[Region] = []
    for region in regions:
        start = _moved(region.start, ops, True)
        end = start if region.start == region.end else _moved(region.end, ops, False)
        if start is not None and end is not None and start <= end:
            out.append(replace(region, start=start, end=end))
    return tuple(out)


def touched(old: str, new: str, regions: tuple[Region, ...]) -> list[Region]:
    """The *regions* of the page *old* whose lines its edit *new* changes, or
    adds a line inside."""
    ops = difflib.SequenceMatcher(
        None, old.split("\n"), new.split("\n"), autojunk=False
    ).get_opcodes()
    return [
        r
        for r in regions
        if any(
            tag != "equal"
            and (r.start < i1 < r.end if i1 == i2 else i1 < r.end and r.start < i2)
            for tag, i1, i2, _j1, _j2 in ops
        )
    ]


class Expansions:
    """The regions of each recorded message that has any, by message id: what
    the log keeps beside its Markdown so an include can be drawn again."""

    def __init__(self) -> None:
        self._pages: dict[str, tuple[str, tuple[Region, ...]]] = {}

    def regions(self, message_id: str) -> tuple[Region, ...]:
        return self._pages.get(message_id, ("", ()))[1]

    def sent(self, message_id: str, markdown: str, carries: str | None) -> None:
        """A message was recorded: carry the regions of the one it carries on."""
        if carries in self._pages:
            old, regions = self._pages[carries]
            self.put(message_id, markdown, carry(old, markdown, regions))

    def put(self, message_id: str, markdown: str, regions: tuple[Region, ...]) -> None:
        if regions:
            self._pages[message_id] = (markdown, regions)
        else:
            self._pages.pop(message_id, None)

    def add(self, message_id: str, markdown: str, fresh: tuple[Region, ...]) -> None:
        """Regions drawn as *message_id* was recorded, beside those it carried. A
        carried one where a fresh one was drawn is that include, drawn again (a
        page re-sent from its source)."""
        kept = tuple(
            r
            for r in self.regions(message_id)
            if not any(r.start <= f.end and f.start <= r.end for f in fresh)
        )
        both = sorted(kept + fresh, key=lambda r: r.start)
        self.put(message_id, markdown, tuple(both))

    def refuse(self, message_id: str, old: str, new: str) -> None:
        """Raise when an agent's edit of *message_id*, its page *old* made *new*,
        touches what an include drew: that is the backend's data, and its next
        redraw would undo the edit."""
        hit = touched(old, new, self.regions(message_id))
        if hit:
            lines = ", ".join(f"`{r.line}`" for r in hit)
            raise FrameError(
                "bad_target",
                f"that edit touches what {lines} drew from the backend's data, "
                "which only the backend changes. Change the include line and re-send "
                "the page (`showing` gives its `source`), or let the backend's data "
                "change.",
            )

    def source(self, message_id: str, markdown: str) -> str:
        """*message_id*'s page with each region its include line again."""
        return source(markdown, self.regions(message_id))


def unexpanded(markdown: str, includes: Includes | None = None) -> list[dict]:
    """An issue for each lone ``{{…}}`` line left in *markdown*: the user would
    see its braces. An error, but a warning where the line may be meant: on a
    server with no includes (template syntax written about), inside a list or a
    row (not drawn there: move it), or one *includes* draws now (it was streamed)."""
    issues = []
    for _i, found, nested in _lone_lines(markdown.split("\n")):
        name, line = found.group("name"), found.group(0).strip()
        include = includes.get(name) if includes else None
        level, code = "warning", "unknown-include"
        if not includes:
            why = (
                f"This server has no includes, so `{line}` is shown as written: "
                "fine as text about a template, but nothing here draws it."
            )
        elif nested:
            code = "nested-include"
            why = (
                f"`{line}` is inside a list or a `:::` row, where an include is not "
                "drawn, so the user would see it as written. Move it to its own "
                "block: between blank lines, outside the list or the row."
            )
        elif include is not None and not _draw(include, found.group("args"))[1]:
            code = "streamed-include"
            why = (
                f"`{line}` was not drawn: a streamed message is not expanded "
                "(ADR-612), so the user sees it as written. Send a page with "
                "includes whole."
            )
        elif include is not None:
            level = "error"
            why = (
                f"`{{{{{name} …}}}}` could not be drawn from these args: check them "
                'against `guide("includes")` (an unclosed quote?).'
            )
        else:
            level = "error"
            why = (
                f"No include named `{name}` here, so the user would see "
                f'`{line}` as written. `guide("includes")` '
                "lists this server's includes; write the content otherwise."
            )
        issues.append({"level": level, "code": code, "message": why})
    return issues


def failures(regions: tuple[Region, ...]) -> list[dict]:
    """An error for each of *regions* that could not be drawn: the user sees its
    failure line, or nothing, where the agent meant content. Named by the
    include and the error's class, never its text (the backend's)."""
    issues = []
    for region in regions:
        if region.failed == UNKNOWN:
            why = (
                f"No include named `{region.name}` here, so the user sees nothing "
                f'where `{region.line}` is. `guide("includes")` lists this '
                "server's includes; write the content otherwise."
            )
        elif region.failed:
            why = (
                f"`{region.line}` could not be drawn ({region.failed}), so the user "
                "sees its failure line, or nothing, in its place. Check its args "
                'against `guide("includes")` (an unclosed quote?); if they are '
                "right, the backend failed, and its next redraw draws it again."
            )
        else:
            continue
        issues.append({"level": "error", "code": "unknown-include", "message": why})
    return issues


GUIDE_HEADING = "## This server's includes"
NO_INCLUDES = "This server has no includes: write every part of your answer."
GUIDE_HINT = (
    ' This server has includes: lines it draws from its own data. `guide("includes")` '
    "lists them."
)


def guide_text(includes: Includes, note: Path) -> str:
    """``guide("includes")``: the note on writing includes, then this server's,
    one line each. With none registered, one line says so."""
    if not includes:
        return NO_INCLUDES
    text = note.read_text(encoding="utf-8").rstrip() if note.is_file() else ""
    if GUIDE_HEADING not in text:
        text = f"{text}\n\n{GUIDE_HEADING}".strip()
    return f"{text}\n\n" + "\n".join(includes.rows()) + "\n"


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    found = _FRONTMATTER.match(text)
    if not found:
        return {}, text
    keys = {}
    for line in found.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            keys[key.strip()] = value.strip().strip('"')
    return keys, text[found.end() :]


def static_includes(theme_path: Path | None) -> Includes:
    """The includes in an ``includes/`` folder beside *theme_path*: each
    ``<name>.md`` is frontmatter (``description:``, ``args:``, where ``none`` means
    it takes none, and an optional ``failure:`` line), then the body every call
    of that name expands to, whatever its args (evals)."""
    includes = Includes()
    folder = theme_path.parent / "includes" if theme_path is not None else None
    if folder is None or not folder.is_dir():
        return includes
    for path in sorted(folder.glob("*.md")):
        keys, body = _frontmatter(path.read_text(encoding="utf-8"))
        if NAME.match(path.stem):
            includes.add(
                path.stem,
                keys.get("description", ""),
                lambda _args, body=body: body,
                "" if keys.get("args", "").lower() == "none" else keys.get("args", ""),
                keys.get("failure", ""),
            )
    return includes
