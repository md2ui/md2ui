"""What a theme tells the agent writing for it.

A theme draws; ``THEME.md`` is the frontend's input and says nothing about
purpose. What each element spelling *means* is declared beside it, in
``MEANINGS.md``, and the shapes a theme wants used are its ``patterns/*.md``.
This module reads both for the MCP shells: ``guide("theme")`` serves the merged
contract, ``guide("patterns")`` lists the theme's patterns, and ``check`` warns
when an answer writes a spelling the contract does not declare.

A pattern may give an unlisted spelling a meaning inside its own shape
(ADR-501), and says so in the contract's own ``| Write | Means |`` table, outside
its example. ``check`` counts those spellings as declared; the contract, and the
digest that serves it, never grow by them.

A ``MEANINGS.md`` belongs to one project, as its ``THEME.md`` does. The
repository's own (the defaults) is the default theme's, and another project uses
it only when its owner chooses to. So a theme's file is its whole contract,
unless its first line is ``Extends: defaults``: then it changes the defaults row
by row. A row with the same
spelling under the same heading replaces the default row, a new one is added,
and one whose meaning is ``—`` removes it. A theme with no file declares no
meanings, and its agent writes bare spellings, which every theme draws; with no
theme at all the defaults are served, md2ui's default theme being the root
``THEME.md``. Every path here is the theme's, so a backend outside this
repository serves its own project's meanings from its own theme folder.

What the agent is served is meaning and shape, never design: a row's optional
*Size* column is the theme lint's, and a fixed colour whose meaning is
``decoration`` is the theme's alone. Its optional *Slot* column is the code's:
where a spelling goes, as keys from ``SLOTS``, so what reads the contract keys on
the slot and *Means* stays prose for the agent (ADR-501). It is never served.
The theme's own rows come first, so what this theme changes is read before what
every theme shares.

A spelling is read with the grouper's own marker vocabulary, never a copy of
it, so the contract and the renderer cannot disagree about which variant a
spelling selects: a row resolves to the same ``(element, variant, state)`` the
grouper stamps on the node it would build.

A shell module beside ``check`` and ``session``; the pipeline never imports it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import NamedTuple

from md2ui import session
from md2ui.pipeline.grouper_block_splits import INLINE_CODE_RE
from md2ui.pipeline.grouper_inline_marks import (
    _element_text_span,
    _is_lone_emoji,
    _quoted_element_spans,
    _wrapped_element_variant,
)
from md2ui.pipeline.grouper_types import (
    _CHIP_UNDERSCORE_VARIANT_BY_LEN,
    _ELEMENT_VARIANT_BY_LEN,
    _LINK_CONTENT_RE,
    _classify_link_content,
    _strip_wrap,
    link_destination,
)

# The default theme's contract, which a theme extends only when its own file says
# so. Module-level so a test can point it at a fixture.
BASE = session.resource_root() / "MEANINGS.md"
# A theme file's first line when the theme keeps the defaults underneath its rows.
EXTENDS = re.compile(r"\A\s*Extends:[ \t]*defaults[ \t]*(?:\n|\Z)", re.IGNORECASE)
# The patterns every theme serves, beside its own.
SKILLS_PATTERNS = session.resource_root() / "skills" / "patterns"
FILE_NAME = "MEANINGS.md"
REMOVED = "—"
# A fixed colour the agent cannot act on: declared, so the lint knows the pin is
# meant, and never served.
DECORATION = "decoration"
# The sections whose rows are spellings of one element. ``## Fixed colours``
# keys a token, not a spelling, so its rows are kept as written.
ELEMENT_SECTIONS = ("icons", "chips", "buttons", "icon buttons")
# Where a spelling goes: the closed list a row's *Slot* cell names keys from
# (ADR-501). Icon buttons take the same slots as buttons.
SLOTS = (
    "foot-main",  # the foot of a flow, a section or a dialog
    "foot-quieter",
    "card-main",  # inside a card: the action the card is for
    "card-quieter",
    "card-way-in",  # a way in that repeats on every card
    "row-main",  # the edge of a row in a list
    "row-quieter",
    "title-edge",  # the edge of a section's title
    "nav",  # a link to another place: a site map, a footer, a list of links
    "minor",  # a minor action
    "compact",  # inside a compact element
    "inline",  # inside a sentence, as text
    "icon-label",  # an icon in a label or leading a row
    "icon-subject",  # the icon a feature, an empty state or a headline is about
    "icon-dense",  # an icon in a dense row
)
# The slots the core note's placement table lists. The bare spellings' places
# are left to the table's lead, and a compact element's rows to guide("theme").
PLACED_SLOTS = frozenset(
    {
        "icon-subject",
        "icon-dense",
        "foot-main",
        "foot-quieter",
        "card-main",
        "card-quieter",
        "row-main",
        "row-quieter",
        "card-way-in",
    }
)


class Selection(NamedTuple):
    """What a spelling selects: ``element`` is ``icon`` / ``chip`` / ``button`` /
    ``icon button``; ``variant`` is the grouper's name for it (``primary``,
    ``secondary``…, ``text``) or ``quoted`` for an element the author declined;
    ``state`` is ``muted`` for ``~~…~~``, else None. ``face`` is a text
    button's wrapper: the backtick label makes it ``text`` whatever wraps it, so
    the wrapper is kept as the face it draws (``italic``, ``bold``…) and is part
    of what a row declares, as a wrapper is for every other element."""

    element: str
    variant: str
    state: str | None = None
    face: str | None = None

    @property
    def key(self) -> tuple[str, str, str | None]:
        """What a row declares: the spelling but its state."""
        return self.element, self.variant, self.face


@dataclass
class Row:
    write: str  # the first cell as written, code span and all
    means: str
    selects: Selection | None  # None: not an element spelling (a pin, a phrase)
    size: str = ""  # how the theme should draw it: the lint's, never served
    slots: tuple[str, ...] = ()  # where it goes, keys from SLOTS: never served
    own: bool = False  # declared by the theme, not the base


@dataclass
class Section:
    heading: str
    header: str  # the table's header and rule lines, as written
    rows: list[Row] = field(default_factory=list)


@dataclass
class Contract:
    preamble: str
    sections: list[Section]
    # The ``Selection.key`` a served pattern gives a meaning in its own shape:
    # declared to ``check``, never part of the contract's text.
    in_patterns: frozenset[tuple[str, str, str | None]] = frozenset()

    def declared(self, element: str) -> list[Row]:
        return [
            row
            for section in self.sections
            for row in section.rows
            if row.selects is not None and row.selects.element == element
        ]

    def text(self) -> str:
        """The contract as the agent reads it: what each spelling means, the
        theme's own rows first in each section, with no size, no comment for the
        theme's author and no decoration."""
        preamble = _COMMENT.sub("", self.preamble).strip()
        parts = [preamble] if preamble else []
        own = [row.write for s in self.sections for row in s.rows if row.own]
        if own:
            parts.append(
                f"This theme declares {len(own)} of its own, first in their "
                f"sections: {', '.join(own)}."
            )
        for section in self.sections:
            served = [row for row in section.rows if row.means != DECORATION]
            if not served:
                continue
            ordered = sorted(served, key=lambda row: not row.own)
            write, means = _cells(section.header.split("\n")[0])[:2]
            rows = [f"| {row.write} | {row.means} |" for row in ordered]
            head = [f"## {section.heading}", "", f"| {write} | {means} |", "|---|---|"]
            parts.append("\n".join([*head, *rows]))
        return "\n\n".join(parts) + "\n"


_COMMENT = re.compile(r"\s*<!--.*?-->", re.DOTALL)


def _cells(line: str) -> list[str]:
    """A table row's cells. A ``|`` inside a code span or escaped stays text."""
    cells, cell, fence, i = [], "", 0, 0
    body = line.strip().removeprefix("|").removesuffix("|")
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            cell += body[i : i + 2]
            i += 2
            continue
        if ch == "`":
            run = len(body[i:]) - len(body[i:].lstrip("`"))
            fence = run if fence == 0 else (0 if run == fence else fence)
            cell += body[i : i + run]
            i += run
            continue
        if ch == "|" and fence == 0:
            cells.append(cell.strip())
            cell = ""
        else:
            cell += ch
        i += 1
    return [*cells, cell.strip()]


_CODE_SPAN = re.compile(r"^(`+)(.+?)\1$", re.DOTALL)


def _code_span(cell: str) -> str | None:
    """The text of a cell that is one code span, by CommonMark's rule (a space
    on both sides is padding), else None."""
    m = _CODE_SPAN.match(cell.strip())
    if m is None:
        return None
    text = m.group(2)
    if len(text) > 2 and text[0] == " " and text[-1] == " " and text.strip():
        text = text[1:-1]
    return text


def _element(core: str) -> str | None:
    if _LINK_CONTENT_RE.match(core):
        return "icon button" if _classify_link_content(core)[2] else "button"
    if INLINE_CODE_RE.fullmatch(core):
        return "chip"
    if _is_lone_emoji(core):
        return "icon"
    return None


def resolve(spelling: str) -> Selection | None:
    """What *spelling* selects, read the way the grouper reads it; None for
    anything that is not one element."""
    s = spelling.strip()
    lo, hi = _element_text_span(s)
    core = s[lo:hi]
    element = _element(core)
    if element is None:
        if (lo, hi) in _quoted_element_spans(s) and _element(core[1:-1]):
            muted = _strip_wrap(s, "~~") is not None
            return Selection(_element(core[1:-1]) or "", "quoted", _state(muted))
        return None
    if element in ("button", "icon button"):
        variant, _label, _emoji, disabled, face = _classify_link_content(s)
        face = face if element == "button" else None
        return Selection(element, variant, _state(disabled), face)
    unstruck = _strip_wrap(s, "~~")
    wrapped = unstruck if unstruck is not None else s
    if wrapped == core:
        return Selection(element, "primary", _state(unstruck is not None))
    variant = _wrapped_element_variant(wrapped, core, chip=element == "chip")
    return (
        Selection(element, variant, _state(unstruck is not None)) if variant else None
    )


def _state(muted: bool) -> str | None:
    return "muted" if muted else None


def parse(text: str) -> Contract:
    """A ``MEANINGS.md``: the prose before the first ``##``, then one table per
    section. A row whose first cell is a code span is a spelling and resolved;
    every other row (a fixed colour's token) is kept as written."""
    preamble: list[str] = []
    sections: list[Section] = []
    for line in text.splitlines():
        if line.startswith("## "):
            sections.append(Section(line[3:].strip(), ""))
        elif not sections:
            preamble.append(line)
        elif line.lstrip().startswith("|"):
            section = sections[-1]
            cells = _cells(line)
            if not section.header:
                section.header = line.strip()
            elif section.header.count("\n") == 0:
                section.header += "\n" + line.strip()
            elif len(cells) >= 2:
                spelling = _code_span(cells[0])
                spells = section.heading.lower() in ELEMENT_SECTIONS
                selects = resolve(spelling) if spells and spelling else None
                size = _column(section, cells, "size")
                slots = _column(section, cells, "slot").split(",")
                keys = tuple(key.strip() for key in slots if key.strip())
                section.rows.append(Row(cells[0], cells[1], selects, size, keys))
    return Contract("\n".join(preamble), sections)


def _column(section: Section, cells: list[str], name: str) -> str:
    """A row's cell under the header *name*, so *Size* and *Slot* are each
    optional; empty when the table has no such column."""
    header = [cell.lower() for cell in _cells(section.header.split("\n")[0])]
    at = header.index(name) if name in header else len(cells)
    return cells[at] if at < len(cells) else ""


def merge(base: Contract, theme: Contract) -> Contract:
    """*base* changed by *theme* row by row: a row matches the base
    row written the same under the same heading, and replaces it whole, its
    slots too: a theme row with no slot inherits none."""
    sections = [Section(s.heading, s.header, list(s.rows)) for s in base.sections]
    by_heading = {s.heading.lower(): s for s in sections}
    for theirs in theme.sections:
        ours = by_heading.get(theirs.heading.lower())
        if ours is None:
            ours = Section(theirs.heading, theirs.header)
            sections.append(ours)
            by_heading[ours.heading.lower()] = ours
        for row in (replace(r, own=True) for r in theirs.rows):
            same = [i for i, r in enumerate(ours.rows) if r.write == row.write]
            if row.means.strip() == REMOVED:
                ours.rows = [r for r in ours.rows if r.write != row.write]
            elif same:
                ours.rows[same[0]] = row
            else:
                ours.rows.append(row)
    return Contract(base.preamble, sections)


_FENCED = re.compile(r"^```.*?^```[ \t]*$", re.DOTALL | re.MULTILINE)


def pattern_spellings(path: Path) -> frozenset[tuple[str, str, str | None]]:
    """The ``Selection.key`` of each spelling the pattern at *path* declares:
    the rows of a ``| Write | Means |`` table outside its example."""
    found: set[tuple[str, str, str | None]] = set()
    in_table = False
    for line in _FENCED.sub("", path.read_text(encoding="utf-8")).splitlines():
        cells = _cells(line) if line.lstrip().startswith("|") else []
        in_table = bool(cells) and (in_table or cells[:2] == ["Write", "Means"])
        spelling = _code_span(cells[0]) if in_table else None
        selects = resolve(spelling) if spelling else None
        if selects is not None:
            found.add(selects.key)
    return frozenset(found)


def with_patterns(contract: Contract, patterns: list[Path]) -> Contract:
    """*contract*, with the spellings the *patterns* declare counted as declared."""
    spelled = contract.in_patterns.union(*(pattern_spellings(p) for p in patterns))
    return replace(contract, in_patterns=spelled)


def theme_dir(theme_path: Path | None) -> Path | None:
    return theme_path.resolve().parent if theme_path is not None else None


def load_contract(theme_path: Path | None) -> Contract | None:
    """The contract for the theme at *theme_path*: its own file alone, or the
    defaults changed by it when it starts ``Extends: defaults``. The defaults
    as they are with no theme (md2ui's default theme is the root ``THEME.md``)
    and for that theme; None for a theme with no file, and for one that extends
    defaults there are none of."""
    folder = theme_dir(theme_path)
    own = folder / FILE_NAME if folder is not None else None
    if own is None or (BASE.is_file() and own.resolve() == BASE.resolve()):
        return parse(BASE.read_text(encoding="utf-8")) if BASE.is_file() else None
    if not own.is_file():
        return None
    text = own.read_text(encoding="utf-8")
    extends = EXTENDS.match(text)
    if extends is None:  # the whole contract: a `—` row has nothing to remove
        contract = parse(text)
        for section in contract.sections:
            section.rows = [r for r in section.rows if r.means.strip() != REMOVED]
        return contract
    if not BASE.is_file():
        return None
    return merge(parse(BASE.read_text(encoding="utf-8")), parse(text[extends.end() :]))


def own_spellings(
    theme_path: Path | None, patterns: dict[str, Path] | None = None
) -> str:
    """What this theme declares beyond the base, as the section ``guide`` ends the
    core note with: its own spellings, then its *patterns*, one line each. Most
    agents read the core note and nothing else, and never open
    ``guide("theme")``, so a theme's own vocabulary must be where they read.
    Empty when the theme declares nothing of its own: on such a theme the core
    note is served as written."""
    contract = load_contract(theme_path)
    rows = [
        row
        for section in (contract.sections if contract else [])
        for row in section.rows
        if row.own and row.means != DECORATION
    ]
    text = ""
    if rows:
        table = "\n".join(f"| {row.write} | {row.means} |" for row in rows)
        text += (
            "\n\n## This theme's own spellings\n\nThis theme gives these a meaning of "
            "its own: write them where the meaning applies. What is unavailable, "
            "inactive or past is not one of these: it is the ordinary spelling muted, "
            '`~~…~~`. `guide("theme")` lists every spelling it declares.\n\n'
            "| Write | Means |\n|---|---|\n" + table + "\n"
        )
    if patterns:
        lines = "\n".join(
            f"- `{name}`: {pattern_description(path)}"
            for name, path in patterns.items()
        )
        text += (
            "\n\n## This theme's own patterns\n\nShapes this theme's author made for "
            'its content. Before writing a section one fits, read it with `guide("theme/'
            '<name>")`; where it and a general pattern cover the same content, the '
            "theme's is the better reference.\n\n" + lines + "\n"
        )
    return text


def placeholder_spellings(theme_path: Path | None) -> str:
    """The contract's ``## Placeholders`` rows, as the section ``guide`` ends the
    core note with after the placement table: a placeholder is chosen when the
    answer is written, so it has to be in front of the agent. Empty when the
    theme offers none."""
    contract = load_contract(theme_path)
    rows = [
        row
        for section in (contract.sections if contract else [])
        if section.heading.lower() == "placeholders"
        for row in section.rows
    ]
    if not rows:
        return ""
    table = "\n".join(f"| {row.write} | {row.means} |" for row in rows)
    return (
        "\n\n## An item with no picture\n\nAn item's picture comes from the tool that "
        "returns it, even when that takes a second request: a company's logo, a "
        "person's photo, an album's cover. With this theme, an item that has no "
        "picture of its own, such as a person with no photo, shows a placeholder in "
        "its place: write the one for what it is, with its text.\n\n"
        "| Write | Means |\n|---|---|\n" + table + "\n"
    )


def placed_spellings(theme_path: Path | None) -> str:
    """The rows whose slot is one of *PLACED_SLOTS*, in the contract's order, as
    the section ``guide`` ends the core note with. Which spelling an icon or an
    action takes follows its place (the foot of a section, a card, a row's edge,
    an empty state), and agents that read only the core note wrote the wrong one
    for its place.

    Every agent pays for this table on every answer, so it carries only the slots
    the core note cannot do without: a bare spelling's place is left to the
    table's lead, and a compact element's rows to ``guide("theme")``. Never a
    theme's own row, already in its own table, nor decoration.

    Empty when no row is left."""
    contract = load_contract(theme_path)
    rows = [
        row
        for section in (contract.sections if contract else [])
        for row in section.rows
        if not row.own
        and row.means != DECORATION
        and PLACED_SLOTS.intersection(row.slots)
    ]
    if not rows:
        return ""
    table = "\n".join(f"| {row.write} | {row.means} |" for row in rows)
    return (
        "\n\n## Where an icon or an action sits\n\nWith this theme, an icon's or "
        "an action's spelling follows where it sits: write the one for its place. "
        "A place no row names takes the bare spelling.\n\n"
        "| Write | Means |\n|---|---|\n" + table + "\n"
    )


def skills_patterns() -> list[Path]:
    """md2ui's own patterns, which ``guide`` serves with every theme."""
    return sorted(SKILLS_PATTERNS.glob("*.md"))


def theme_patterns(theme_path: Path | None) -> dict[str, Path]:
    """The theme's patterns by lower-cased name: ``<theme dir>/patterns/*.md``."""
    folder = theme_dir(theme_path)
    if folder is None:
        return {}
    return {p.stem.lower(): p for p in sorted((folder / "patterns").glob("*.md"))}


def pattern_description(path: Path) -> str:
    found = re.search(
        r"^description:\s*(.+)$", path.read_text(encoding="utf-8"), re.MULTILINE
    )
    return found.group(1).strip() if found else ""


def digest(theme_path: Path | None, patterns: dict[str, Path]) -> str:
    """``guide("theme")``: the merged contract, then the theme's *patterns*
    (the ones served: a pattern whose example fails ``check`` is not)."""
    contract = load_contract(theme_path)
    text = contract.text() if contract else "This theme declares no meanings.\n"
    if patterns:
        rows = [f"- {n} — {pattern_description(p)}" for n, p in patterns.items()]
        head = (
            "## Patterns\n\nThis theme's shapes. Read one with guide('theme/<name>'):"
        )
        text += "\n" + "\n".join([head, "", *rows]) + "\n"
    return text


# The wrapper each variant is written with, derived from the grouper's tables.
_WRAPPER = {v: "*" * n for n, v in _ELEMENT_VARIANT_BY_LEN.items()}
_CHIP_WRAPPER = _WRAPPER | {
    v: "_" * n for n, v in _CHIP_UNDERSCORE_VARIANT_BY_LEN.items()
}


def _node_spelling(node: dict) -> tuple[Selection, str, str] | None:
    """``(selection, as written, bare)`` for an element node of a grouped tree."""
    kind, content = node.get("type"), str(node.get("content", ""))
    if kind == "emoji":
        variant = node.get("emoji_variant") or "primary"
        wrap = _WRAPPER.get(variant, "")
        return Selection("icon", variant), f"{wrap}{content}{wrap}", content
    if kind == "inline_code":
        variant = node.get("code_variant") or "primary"
        wrap, chip = _CHIP_WRAPPER.get(variant, ""), f"`{content}`"
        return Selection("chip", variant), f"{wrap}{chip}{wrap}", chip
    if kind == "link" and node.get("link_variant"):
        element = "icon button" if node.get("link_is_emoji") else "button"
        variant, label = node["link_variant"], node.get("link_label", "")
        text = element == "button" and variant == "text"
        face = node.get("link_emphasis") if text else None
        label = f"`{label}`" if text else label
        bare = f"[{label}]({link_destination(content) or ''})"
        return Selection(element, variant, None, face), content.strip(), bare
    return None


def _kind(selects: Selection) -> str:
    """What the message calls *selects*'s element: a text button is its own."""
    text = selects.element == "button" and selects.variant == "text"
    return "text button" if text else selects.element


def _code(text: str) -> str:
    return f"`` {text} ``" if "`" in text else f"`{text}`"


def undeclared(tree: dict, contract: Contract) -> list[str]:
    """One message per element spelling in *tree* that neither *contract* nor
    one of its patterns declares, in document order. A bare element never is:
    it is always correct, and a bare text button is checked as the other text
    buttons are, since its backticks are what make it one."""
    found: dict[Selection, str] = {}

    def walk(node: dict) -> None:
        spelled = _node_spelling(node)
        if spelled is not None:
            selects, written, bare = spelled
            declared = contract.declared(selects.element)
            ok = {r.selects.key for r in declared if r.selects} | contract.in_patterns
            if selects.variant != "primary" and selects.key not in ok:
                kind = _kind(selects)
                listed = declared
                if kind != selects.element:
                    listed = [
                        r for r in declared if r.selects and _kind(r.selects) == kind
                    ]
                names = ", ".join(r.write for r in listed) or "none"
                found.setdefault(
                    selects,
                    f"{_code(written)} is not declared by this theme; write "
                    f"{_code(bare)}. "
                    f"Its {kind}s are: {names}.",
                )
        for child in node.get("children", []):
            walk(child)

    walk(tree)
    return list(found.values())
