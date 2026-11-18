"""Advice from what an answer used: the section that teaches it, while unread.

Agents read the core note and stop (ADR-502).
Directed, they find the right note and use it; unprompted, nothing tells them
their answer needs one. The one surface every agent reads at the moment it
decides is a tool's result, and it is the only one that knows what the agent
wrote. So ``check``, ``preview`` and the demo's ``show`` add a line naming the
section that teaches a construct the answer used, when this session has not
read that section (ADR-502).

Each trigger reads the grouped tree, never the source text, and is kept only
while an eval shows it helps: an answer it fires on is better after the re-send
than before. A line says what to write first, so a small fix needs no read, and
then the section, with its cost, for the cases the hint does not cover.

Once per section per session, and nothing when nothing fires, so an answer that
needs no advice pays nothing. A hint that only points is not enough for card
actions, so the card hint names the theme's own card spellings.

A pattern in ``skills/patterns/`` is advised the same way, from the shape of a
section (``advice_patterns``). Reading the patterns index is not reading a
pattern, so only ``patterns/<name>`` silences one.

A form written a turn at a time (a stepper of buttons, options without a name,
values no press carries) is advised from ``advice_forms``, skipping what an
include drew and the steppers a registered handler answers (ADR-612): a
backend's handler answers those with no turn.

A shell module beside ``check`` and ``digest``; the pipeline never imports it.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterator
from dataclasses import dataclass, field

from md2ui import session, wire_sections
from md2ui.advice_forms import form_hints
from md2ui.advice_patterns import pattern_hints
from md2ui.check import check_grouped
from md2ui.includes import Includes, Region, failures, unexpanded
from md2ui.meanings import Contract, Row, _node_spelling
from md2ui.pipeline.grouper_types import MarkdownGroupNode
from md2ui.notes import sections

SKILLS = session.resource_root() / "skills"

ICON_ROLES = "elements/what-the-icon-does-decides-how-you-write-it"
THEME = "theme"
CHIPS = "text/inline-code-has-two-forms"
CHARTS = "dashboards/which-figure-each-spelling-draws"
FORMS = "elements/what-a-click-does"

# Two values and what joins them, written as a line of its own: `SFO → JFK`,
# `San Francisco SFO → New York JFK`. Up to three words a side, so a sentence
# never matches.
_SIDE = r"(\S+(?:\s\S+){0,2})"
_JOINED = re.compile(rf"^\s*{_SIDE}\s+(\S{{1,3}})\s+{_SIDE}\s*$")
_ARROWS = frozenset("→ ⟶ ➔ ➜ ⇒ ->".split())
_DIGIT = re.compile(r"\d")
# A label that names a way in to the item rather than what the card is for:
# `Open Copywriting`, `View on Expedia`, `Read more`.
_WAY_IN = re.compile(r"^(?:open|view|see|details|read|visit|go to)\b", re.IGNORECASE)
# A note whose bare name serves an index of its parts, not the parts themselves.
_INDEXES = frozenset({"patterns"})
# The contract's slots for an action inside a card, and for a way in that repeats
# on every card (``meanings.SLOTS``).
_CARD_SLOTS = frozenset({"card-main", "card-quieter"})
_WAY_IN_SLOT = "card-way-in"


@dataclass
class Reading:
    """What one session has read through ``guide``, and what it was advised to
    read: advice is never repeated, whether or not it was followed."""

    read: set[str] = field(default_factory=set)
    advised: set[str] = field(default_factory=set)

    def covers(self, topic: str) -> bool:
        """Read or advised already: the topic itself, or the whole note it is a
        section of. ``patterns`` is the index, so a pattern counts only when it
        was read by its own name."""
        seen = self.read | self.advised
        note = topic.split("/")[0]
        return topic in seen or (note in seen and note not in _INDEXES)

    def advise(
        self,
        tree: dict | None,
        contract: Contract | None,
        drawn: Collection[str] = (),
        handled: Collection[str] = (),
    ) -> list[dict]:
        """Advice for the grouped *tree*, as ``check`` notes, each with the topic
        it points to under ``read``. *drawn* is the lines includes drew, and
        *handled* the ``agent:`` slugs the server's handlers answer."""
        out: list[dict] = []
        for topic, message in _found(tree, contract, drawn, handled) if tree else ():
            if self.covers(topic) or any(o["read"] == topic for o in out):
                continue
            out.append(
                {"level": "note", "code": "advice", "message": message, "read": topic}
            )
        self.advised |= {o["read"] for o in out}
        return out


def reply_issues(
    markdown: str,
    ast: MarkdownGroupNode | None,
    contract: Contract | None,
    reading: Reading,
    includes: Includes | None = None,
    regions: tuple[Region, ...] = (),
    handled: Collection[str] = (),
) -> list[dict]:
    """What a reply's sender returns to its agent: the authoring issues, then the
    advice for this session. The demo's ``show`` and the ``check`` tool return it,
    and so does a backend's own send tool after ``Conversation.send``
    (protocol/backend.md): advice helps only on the path every reply takes.
    *markdown* is the page with its includes expanded; an include line left in it
    is an issue, said for *includes* (``includes.unexpanded``, ADR-612), and
    *regions* are the lines they drew, which no advice is about; one that drew
    its failure line is an issue too (``includes.failures``). *handled* is
    the ``agent:`` slugs the server's handlers answer (``Conversation.handlers``):
    a stepper they answer costs no turn and is not advised a count."""
    tree = ast.to_dict() if ast is not None else None
    issues = unexpanded(markdown, includes) + failures(regions)
    issues += check_grouped(markdown, ast, contract)
    issues += _unread_limits(markdown)
    lines = markdown.split("\n")
    drawn = [line for r in regions for line in lines[r.start : r.end]]
    return issues + reading.advise(tree, contract, drawn, handled)


def _unread_limits(markdown: str) -> list[dict]:
    """A note for each ``fresh:`` that names no duration: without one, the section
    is never reported stale, and nothing else would say so."""
    return [
        {
            "level": "note",
            "code": "fresh-unread",
            "message": f"`fresh: {s.fresh}` under `{s.name}` is not a duration, so "
            "the section is never reported stale. Write a number and a unit: "
            "`30s`, `5m`, `2h`, `1d`.",
        }
        for s in wire_sections.unread_limits(markdown)
    ]


def _found(
    tree: dict,
    contract: Contract | None,
    drawn: Collection[str] = (),
    handled: Collection[str] = (),
) -> Iterator[tuple[str, str]]:
    """``(topic, message)`` for each trigger the tree sets off, in document order."""
    for node in _walk(tree):
        kids = node.get("children", [])
        for glyph, number in zip(kids, kids[1:]):
            if (
                glyph.get("type") == "emoji"
                and number.get("text_style") == "display"
                and _DIGIT.search(str(number.get("content", "")))
            ):
                yield (
                    ICON_ROLES,
                    (
                        f"`{glyph['content']}` stands as a badge beside the number "
                        f"`{number['content']}`. An icon that belongs to the number is "
                        f"written inside its tier, `___{glyph['content']} "
                        f"{number['content']}___`, and grows with it. {_read(ICON_ROLES)}"
                    ),
                )
        for amount in _lone_amounts(node):
            yield (
                CHIPS,
                (
                    f"`{amount}` is one amount on a chip, and a chip is for a word the "
                    f"reader scans for: a status, a tag. Write the amount without the "
                    f"backticks, {amount}, or `__{amount}__` when it leads its card; a set of "
                    f"prices, or a change such as `▲ +2%`, stays chips. {_read(CHIPS)}"
                ),
            )
        lines = [] if str(node.get("type")).startswith("heading") else kids
        for line in lines:
            if line.get("type") != "text" or not (joined := _joined(line)):
                continue
            yield (
                ICON_ROLES,
                (
                    f"`{line['content']}` writes how two values relate as one line of "
                    f"text. An icon between two values stands between them, "
                    f"`__{_bare(joined[0])}__ ... {joined[1]} ... "
                    f"__{_bare(joined[2])}__`. "
                    f"{_read(ICON_ROLES)}"
                ),
            )
        runs: dict[object, list[str]] = {}
        for card in kids:
            if card.get("heading_group") and not _asks(card):
                if action := _full_size_action(card):
                    runs.setdefault(card.get("fingerprint_hash"), []).append(action)
        actions = max(runs.values(), key=len, default=[])
        if len(actions) >= 2 and contract and (spelled := _card_spellings(contract)):
            yield (
                THEME,
                f"These {len(actions)} cards each hold a full-size action, "
                f"`{actions[0]}`. With this theme an action inside a card is "
                f'{spelled}: `guide("theme")` lists which size goes where.',
            )
        if contract and (way_in := _repeated_way_in(kids, contract)):
            count, written, spelled = way_in
            yield (
                THEME,
                f"These {count} cards each hold `{written}`, a way in to the item. "
                f"With this theme a way in that repeats on every card is {spelled}: "
                f'`guide("theme")` lists which spelling goes where.',
            )
    yield from _tabulated_series(tree)
    for message in form_hints(tree, drawn, handled):
        yield FORMS, f"{message} {_read(FORMS)}"
    yield from pattern_hints(tree)
    if contract is not None and (own := _declared_and_used(tree, contract)):
        yield (
            THEME,
            (
                f"This theme declares spellings of its own for {own}: "
                f'`guide("theme")` lists them and what each means.'
            ),
        )


def _walk(node: dict) -> Iterator[dict]:
    yield node
    for kid in node.get("children", []):
        yield from _walk(kid)


def _joined(node: dict) -> tuple[str, str, str] | None:
    """``(from, glyph, to)`` when a text line is two short values joined by an
    arrow or a lone glyph."""
    found = _JOINED.match(str(node.get("content", "")))
    if found is None:
        return None
    glyphs = {
        dp["matched"] for dp in node.get("data_points", []) if dp["label"] == "dp_emoji"
    }
    if found.group(2) not in _ARROWS and found.group(2) not in glyphs:
        return None
    return found.group(1), found.group(2), found.group(3)


def _lone_amounts(node: dict) -> list[str]:
    """The chips among *node*'s children that are one amount and nothing else,
    each the only amount chip on its line. A line of several prices is a set,
    and a table cell is a cell of one; a signed or arrowed change is detected as
    a change, not an amount, so it never counts."""
    amounts = [
        str(kid["content"])
        for kid in node.get("children", [])
        if kid.get("type") == "inline_code"
        and not kid.get("table_role")
        and [dp["matched"] for dp in kid.get("data_points", [])]
        == [str(kid["content"]).strip()]
        and kid["data_points"][0]["label"] == "dp_currency"
    ]
    # Children of a line group share one line; any other node's chips each
    # stand on a line of their own.
    return amounts if len(amounts) == 1 or not node.get("line_split_group") else []


def _bare(value: str) -> str:
    """A value without the emphasis it was written with, to rewrap in a hint."""
    return value.strip("*_")


def _asks(card: dict) -> bool:
    """A card that asks the user something: its buttons are the answers, a choice
    set, which takes the full size (``skills/README.md``, *choice set*)."""
    return any(
        str(kid.get("content", "")).rstrip().endswith("?")
        for kid in card.get("children", [])
        if kid.get("type") == "text"
    )


def _full_size_action(card: dict) -> str | None:
    """The first button a card holds at the standard size: the bare main action
    or the quieter one, worded or an icon."""
    link = _card_link(card, ("primary", "secondary"))
    return str(link["content"]).strip() if link else None


def _card_link(card: dict, variants: tuple[str, ...]) -> dict | None:
    """The first link of one of *variants* a card holds, as its own child or in a
    row of its own (never in a card nested inside it)."""
    for kid in card.get("children", []):
        row = [] if kid.get("heading_group") else kid.get("children", [])
        for node in [kid, *row]:
            if node.get("type") == "link" and node.get("link_variant") in variants:
                return node
    return None


def _repeated_way_in(
    kids: list[dict], contract: Contract
) -> tuple[int, str, str] | None:
    """``(cards, as written, the way-in spelling)`` when every card of a run holds
    the same kind of card action worded as the same way in to the item (`Open`,
    `View`, `Read more`): a link that repeats on every card, which the theme
    spells apart from the action the card is for.

    A way in is told by its label, not its target: `Open Copywriting` as an
    ``agent:`` action and `View on Expedia` as an ``https:`` link are both one.
    The spellings are the contract's rows chosen by their slot, as
    ``_card_spellings`` chooses them: the card actions are the rows with a
    ``_CARD_SLOTS`` slot, and the way in is the row with ``_WAY_IN_SLOT``. A
    way in already written in that spelling is not a card action, so it never
    fires."""
    rows = _button_rows(contract)
    way_in = [row.write for row in rows if _WAY_IN_SLOT in row.slots]
    in_card = tuple(
        row.selects.variant
        for row in rows
        if row.selects is not None and _CARD_SLOTS.intersection(row.slots)
    )
    if not way_in or not in_card:
        return None
    runs: dict[object, list[dict | None]] = {}
    for card in kids:
        if card.get("heading_group"):
            link = _card_link(card, in_card)
            runs.setdefault(card.get("fingerprint_hash"), []).append(link)
    for links in runs.values():
        found = [link for link in links if link is not None]
        if len(links) < 2 or len(found) < len(links):
            continue
        verbs = {_way_in_verb(str(link.get("link_label", ""))) for link in found}
        kinds = {link.get("link_variant") for link in found}
        if len(kinds) == 1 and len(verbs) == 1 and None not in verbs:
            return len(found), str(found[0]["content"]).strip(), way_in[0]
    return None


def _way_in_verb(label: str) -> str | None:
    """The word a label opens with when it names a way in to the item."""
    found = _WAY_IN.match(label)
    return found[0].lower() if found else None


def _card_spellings(contract: Contract) -> str:
    """The theme's spellings for an action inside a card, from the rows whose
    slot places them there, each with its meaning: ``**[Label](/x)**`` (the main
    action inside a card), ``***[Label](/x)***`` (a quieter action inside a card)."""
    rows = [
        row for row in _button_rows(contract) if _CARD_SLOTS.intersection(row.slots)
    ]
    return ", ".join(f"{row.write} ({row.means})" for row in rows)


def _button_rows(contract: Contract) -> list[Row]:
    """The contract's rows for a worded or an icon button."""
    return [
        row
        for section in contract.sections
        if section.heading.lower() in ("buttons", "icon buttons")
        for row in section.rows
    ]


def _declared_and_used(tree: dict, contract: Contract) -> str:
    """The elements the answer uses that the theme gives spellings of its own,
    named as ``MEANINGS.md``'s sections are: ``icons and chips``."""
    own = {
        row.selects.element
        for section in contract.sections
        for row in section.rows
        if row.own and row.selects is not None
    }
    used = {
        spelled[0].element
        for node in _walk(tree)
        if (spelled := _node_spelling(node)) is not None
    }
    names = sorted(f"{element}s" for element in own & used)
    return " and ".join(names)


def _read(topic: str) -> str:
    note, _, name = topic.partition("/")
    path = SKILLS / f"{note}.md"
    text = (
        sections(path.read_text(encoding="utf-8")).get(name, "")
        if path.is_file()
        else ""
    )
    return f'`guide("{topic}")`, ≈{len(text.split())} words.'


# The grouper's datapoint displays that draw a figure: bars, rings, ratio bars and a
# line (a date chip is a chip).
_FIGURES = frozenset({"kv_percent_bar", "unit_ratio", "ratio_bar", "line_chart"})

# One number in a cell, with what it is measured in: a currency before it, or a
# unit after it.
_CELL_VALUE = re.compile(
    r"^\D*?([$€£¥]?)\s*[-−+]?\d[\d.,]*\s*(%|°[CF]?|[A-Za-z/]+)?\s*$"
)


def _text(node: dict) -> str:
    return " ".join(
        [str(node.get("content") or "")] + [_text(k) for k in node.get("children", [])]
    ).strip()


def _tabulated_series(tree: dict) -> Iterator[tuple[str, str]]:
    """A table column of three or more numbers in one unit, on a page that draws
    no figure: the series is there, only written as cells."""
    if any(
        n.get("chart_group")
        or n.get("line_group")
        or n.get("datapoint_display") in _FIGURES
        for n in _walk(tree)
    ):
        return
    for node in _walk(tree):
        kids = node.get("children", [])
        header = next((k for k in kids if k.get("type") == "table_header"), None)
        rows = [k for k in kids if k.get("type") == "table_row"]
        if not header or len(rows) < 3:
            continue
        heads = [_text(c) for c in header.get("children", [])]
        names = [re.sub(r"\s*\(.*?\)", "", h) for h in heads]
        series: dict[str, list[str]] = {}
        for col, name in enumerate(names):
            # Bare numbers take the unit their header declares in parentheses,
            # `Wind (km/h)`; with none declared they are not a series in one unit.
            declared = re.search(r"\(([^()]+)\)", heads[col])
            units = set()
            for row in rows:
                cells = row.get("children", [])
                text = _text(cells[col]) if col < len(cells) else ""
                found = _CELL_VALUE.match(text)
                if not found or len(re.findall(r"\d+(?:[.,]\d+)*", text)) != 1:
                    break
                unit = found.group(1) + (found.group(2) or "")
                units.add(unit or (declared.group(1).strip() if declared else ""))
            else:
                if len(units) == 1 and (unit := units.pop()):
                    series.setdefault(unit, []).append(name)
        if not series:
            continue
        unit, named = max(series.items(), key=lambda s: len(s[1]))
        cols = ", ".join(f"`{n}`" for n in named)
        yield (
            CHARTS,
            f"{'The ' + cols + ' columns hold' if len(named) > 1 else 'The ' + cols + ' column holds'} "
            f"{len(rows)} values each in `{unit}`, and the page draws no figure. A "
            f"series the reader follows draws as a chart: rows under a "
            f"`Name ({unit}):` line, each value alone, or two series compared under "
            f"`A, B ({unit}):`, one value per series. The table can stay. "
            f"{_read(CHARTS)}",
        )
        return
