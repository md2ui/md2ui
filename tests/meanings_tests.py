"""
Unit tests for a theme's declared meanings and patterns (the variant contract).

Pinned here:

  * ``MEANINGS.md`` parses into its sections, and each spelling resolves to the
    variant the grouper stamps on the node it builds from that spelling, so the
    contract and the renderer cannot disagree;
  * a row's *Slot* cell parses into its keys, and a theme row replacing a base
    row with no slot of its own inherits none; the root contract fills every
    slot the code reads, from ``meanings.SLOTS`` only, and rewording a *Means*
    cell changes no row the placement table or the card advice picks;
  * *Slot* is never served: not by ``guide("theme")``, the core note, ``check``
    nor the advice;
  * a theme's file changes the base row by row: replace, add, remove with
    ``—``; a theme with no file uses the base, and no base means no contract;
  * ``guide("theme")`` serves the merged contract's meanings, the theme's own
    rows first and named first, with no size and no ``decoration`` pin, then
    the theme's patterns one line each; the core note ends with the theme's own
    spellings, then the rows whose slot says where an icon or an action sits
    (``meanings.PLACED_SLOTS``, in the contract's order), and is served as
    written when there are neither; ``guide("patterns")`` lists them
    under their own heading and ``guide("theme/<name>")`` reads one;
  * ``check`` warns on a spelling the contract does not declare, never on a
    declared or a bare one, and says nothing without a contract; a text
    button's wrapper (`` *[`x`](/y)* ``) is part of its spelling, as a button's
    is, though the backticks make it ``text`` whatever wraps it; a spelling a
    served pattern declares in its ``| Write | Means |`` table counts as
    declared, to ``check`` and to the lint's pattern check, and never enters
    the contract ``guide("theme")`` serves;
  * the theme is linted against its contract (``theme_lint``): two declared
    spellings that draw the same, a row's size the drawn sizes contradict, a pin
    no ``## Fixed colours`` row declares (a ``decoration`` row declares it), a
    colour or size in a meaning or a theme pattern's description, a slot outside
    ``meanings.SLOTS``, buttons with no ``card-main`` or ``row-main`` row; a
    pattern whose example fails
    ``check`` is not served, one that only warns is; a font family a block
    names that ``## Fonts`` never loads, once, with every block naming it and
    the face each falls back to (a code block to a monospaced one);
  * the lint never downloads: a server runs it before it answers its client,
    so a theme image by URL is drawn as one never fetched, fetching on or off.

Run with: uv run python tests/meanings_tests.py
"""

import asyncio
import contextlib
import io
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from md2ui import advice, mcp_server, meanings, pattern_respell, session, theme_lint
from md2ui.check import check_markdown
from md2ui.meanings import Selection
from md2ui.pipeline.render_settings import VIEW
from md2ui.utils.fetch_policy import POLICY
from md2ui.utils.font_loader import resolve_code_typeface, resolve_typeface

BASE = """# Meanings

- Write only the spellings listed here.

## Icons

| Write | Means |
|---|---|
| `⭐` | an icon |
| `*⭐*` | a large icon |
| `"⭐"` | the glyph alone |

## Chips

| Write | Means |
|---|---|
| `` `Tag` `` | a tag |
| `` _`Tag`_ `` | a small tag |

## Buttons

| Write | Means |
|---|---|
| `[Label](/x)` | the main action |
| `**[Label](/x)**` | the main action, medium |
| `` [`Label`](/x) `` | a text button |

## Icon buttons

| Write | Means |
|---|---|
| `***[❤️](/x)***` | an icon action, medium |

## Fixed colours

| Token | Means |
|---|---|
| `⬆` in a chip | a rise, good |
| `☀️` | decoration |
"""

THEME = """## Icons

| Write | Means |
|---|---|
| `*⭐*` | a hero icon |
| `**⭐**` | an overdue item |
| `"⭐"` | — |

## Fixed colours

| Token | Means |
|---|---|
| `⬆` in a chip | a rise, bad |
"""

PATTERN = """---
name: overdue-row
description: A row for a bill past its date.
---
# Overdue row
"""

_MODELS = None


def _kit():
    global _MODELS
    if _MODELS is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _MODELS = session.load_grouping_kit()
    return _MODELS


@contextlib.contextmanager
def _theme(
    base: str | None,
    own: str | None,
    patterns: dict[str, str],
    drawing: str = "# Theme\n",
    extends: bool = True,
):
    """A theme folder (THEME.md, its MEANINGS.md, patterns/) and a defaults file.

    The theme chooses the defaults (``Extends: defaults``, its own rows over
    them, or that line alone) unless *extends* is False: then *own* is its whole
    contract, and None means it has no file."""
    original = meanings.BASE
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        meanings.BASE = root / "base" / "MEANINGS.md"
        meanings.BASE.parent.mkdir()
        if base is not None:
            meanings.BASE.write_text(base)
        folder = root / "theme"
        (folder / "patterns").mkdir(parents=True)
        (folder / "THEME.md").write_text(drawing)
        if extends:
            (folder / "MEANINGS.md").write_text("Extends: defaults\n\n" + (own or ""))
        elif own is not None:
            (folder / "MEANINGS.md").write_text(own)
        for name, text in patterns.items():
            (folder / "patterns" / f"{name}.md").write_text(text)
        try:
            yield folder / "THEME.md"
        finally:
            meanings.BASE = original


def test_parse_resolves_spellings_as_the_grouper_does():
    contract = meanings.parse(BASE)
    headings = [s.heading for s in contract.sections]
    assert headings == ["Icons", "Chips", "Buttons", "Icon buttons", "Fixed colours"]
    selects = {r.write: r.selects for s in contract.sections for r in s.rows}
    assert selects == {
        "`⭐`": Selection("icon", "primary"),
        "`*⭐*`": Selection("icon", "secondary"),
        '`"⭐"`': Selection("icon", "quoted"),
        "`` `Tag` ``": Selection("chip", "primary"),
        "`` _`Tag`_ ``": Selection("chip", "quinary"),
        "`[Label](/x)`": Selection("button", "primary"),
        "`**[Label](/x)**`": Selection("button", "tertiary"),
        "`` [`Label`](/x) ``": Selection("button", "text"),
        "`***[❤️](/x)***`": Selection("icon button", "quaternary"),
        "`⬆` in a chip": None,
        "`☀️`": None,
    }, selects
    assert meanings.resolve("~~**[Go](/x)**~~") == Selection(
        "button", "tertiary", "muted"
    )
    assert meanings.resolve("~~`Tag`~~") == Selection("chip", "primary", "muted")
    assert meanings.resolve("plain words") is None

    # The same spellings, grouped: each node carries the variant resolved above.
    doc = "## A\n\n*⭐*\n\n**⭐**\n\n_`Tag`_\n\n***`Tag`***\n\n**[Go](/x)**\n\n*[▶️](/x)*\n"
    with contextlib.redirect_stdout(io.StringIO()):
        ast = session.group_markdown(doc, _kit())
    assert ast is not None
    found = []

    def walk(node: dict) -> None:
        spelled = meanings._node_spelling(node)
        if spelled is not None:
            found.append((spelled[0], meanings.resolve(spelled[1])))
        for child in node.get("children", []):
            walk(child)

    walk(ast.to_dict())
    assert len(found) == 6, found
    for grouped, parsed in found:
        assert grouped == parsed, (grouped, parsed)
    print("  ✓  MEANINGS.md parses; each spelling selects what the grouper builds")


def test_merge_replaces_adds_and_removes():
    merged = meanings.merge(meanings.parse(BASE), meanings.parse(THEME))
    icons = {r.write: r.means for r in merged.sections[0].rows}
    assert icons == {
        "`⭐`": "an icon",
        "`*⭐*`": "a hero icon",
        "`**⭐**`": "an overdue item",
    }, icons
    pins = [(r.write, r.means) for r in merged.sections[-1].rows]
    assert pins == [("`⬆` in a chip", "a rise, bad"), ("`☀️`", "decoration")], pins
    assert [s.heading for s in merged.sections][1:4] == [
        "Chips",
        "Buttons",
        "Icon buttons",
    ]

    with _theme(BASE, THEME, {}) as theme:
        assert (
            loaded := meanings.load_contract(theme)
        ) and loaded.text() == merged.text()
    with _theme(BASE, None, {}) as theme:
        assert (
            loaded := meanings.load_contract(theme)
        ) and loaded.text() == meanings.parse(BASE).text()
    with _theme(None, THEME, {}) as theme:
        assert meanings.load_contract(theme) is None
    print(
        "  ✓  a theme that extends the defaults replaces, adds and removes rows;"
        " the line alone, the defaults; no defaults, none"
    )


def test_a_theme_file_is_its_whole_contract_unless_it_extends():
    # A MEANINGS.md belongs to one project: another theme's agent is never
    # served the default theme's rows unless its owner chose them.
    with _theme(BASE, None, {}, extends=False) as theme:
        assert meanings.load_contract(theme) is None, "no file, no meanings"
    with _theme(BASE, THEME, {}, extends=False) as theme:
        loaded = meanings.load_contract(theme)
    assert loaded is not None
    rows = [r for s in loaded.sections for r in s.rows]
    assert {r.write for r in rows} == {"`*⭐*`", "`**⭐**`", "`⬆` in a chip"}, rows
    assert not any(r.own for r in rows), "nothing underneath, so nothing is extra"
    assert all(r.means != meanings.REMOVED for r in rows), "a `—` row removes nothing"
    root = meanings.load_contract(session.repo_root() / "THEME.md")
    defaults = meanings.parse(meanings.BASE.read_text())
    assert root is not None and root.text() == defaults.text()
    none = meanings.load_contract(None)
    assert none is not None and none.text() == defaults.text(), "no theme: the default"
    print(
        "  ✓  a theme's file alone is its contract; the root theme, and no theme,"
        " keep the defaults"
    )


def _guide(theme: Path, topic: str) -> str:
    server = mcp_server.build_server(theme)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            result: Any = asyncio.run(server.call_tool("guide", {"topic": topic}))
    finally:
        POLICY.remote = True
        VIEW.placeholder_images = False
    if result.structured_content is not None:
        return result.structured_content.get("result", "")
    return " ".join(getattr(c, "text", "") for c in result.content)


def test_a_themes_pattern_asked_under_patterns_is_served():
    # Agents ask for a theme's pattern where the shared ones are
    # (`patterns/order-status`). It is served when no shared pattern
    # has that name; a shared one by the same name wins.
    with _theme(BASE, THEME, {"overdue-row": PATTERN, "shelf": PATTERN}) as theme:
        asked = _guide(theme, "patterns/overdue-row")
        own = _guide(theme, "theme/overdue-row")
        shared = _guide(theme, "patterns/shelf")
    assert asked == own and PATTERN.strip() in asked, asked
    assert PATTERN.strip() not in shared, "the shared pattern wins"
    print("  ✓  a theme's pattern asked under patterns/ is served; a shared one wins")


def test_guide_serves_the_digest_and_the_themes_patterns():
    with _theme(BASE, THEME, {"overdue-row": PATTERN}) as theme:
        digest = _guide(theme, "theme")
        index = _guide(theme, "patterns")
        pattern = _guide(theme, "theme/overdue-row")
    assert digest.startswith(
        "# Meanings\n\n- Write only the spellings listed here.\n\n"
        "This theme declares 3 of its own, first in their sections: `*⭐*`, "
        "`**⭐**`, `⬆` in a chip.\n\n## Icons"
    ), digest
    assert (
        "## Icons\n\n| Write | Means |\n|---|---|\n| `*⭐*` | a hero icon |\n"
        "| `**⭐**` | an overdue item |\n| `⭐` | an icon |\n\n## Chips"
    ) in digest, digest
    assert '"⭐"' not in digest, digest
    assert "☀️" not in digest and "decoration" not in digest, digest
    assert digest.endswith(
        "## Patterns\n\nThis theme's shapes. Read one with guide('theme/<name>'):\n\n"
        "- overdue-row — A row for a bill past its date.\n"
    ), digest
    assert "This theme's patterns" in index, index
    assert index.endswith("- overdue-row: A row for a bill past its date."), index
    assert pattern == PATTERN
    print(
        "  ✓  guide('theme') is the merged contract and the patterns; theme/<name> reads one"
    )


def test_the_core_note_ends_with_the_themes_own_spellings():
    with _theme(BASE, THEME, {}) as theme:
        core = _guide(theme, "README.md")
    readme = (mcp_server.SKILLS / "README.md").read_text()
    assert core.startswith(readme), core[:80]
    assert core[len(readme) :] == (
        "\n\n## This theme's own spellings\n\nThis theme gives these a meaning of its "
        "own: write them where the meaning applies. What is unavailable, inactive "
        "or past is not one of these: it is the ordinary spelling muted, `~~…~~`. "
        '`guide("theme")` lists every spelling it declares.\n\n'
        "| Write | Means |\n|---|---|\n"
        "| `*⭐*` | a hero icon |\n| `**⭐**` | an overdue item |\n"
        "| `⬆` in a chip | a rise, bad |\n"
    ), core[len(readme) :]
    with _theme(BASE, None, {}) as theme:
        assert _guide(theme, "README.md") == readme
    print("  ✓  the core note ends with the theme's own spellings, and only then")


def test_the_core_note_lists_the_themes_own_patterns():
    """Agents rarely read guide('theme'), so the core note names each theme
    pattern."""
    with _theme(BASE, THEME, {"overdue-row": PATTERN}) as theme:
        core = _guide(theme, "README.md")
    with _theme(BASE, None, {"overdue-row": PATTERN}) as theme:
        only = _guide(theme, "README.md")
    listed = (
        "\n\n## This theme's own patterns\n\nShapes this theme's author made for "
        'its content. Before writing a section one fits, read it with `guide("theme/'
        '<name>")`; where it and a general pattern cover the same content, the '
        "theme's is the better reference.\n\n"
        "- `overdue-row`: A row for a bill past its date.\n"
    )
    readme = (mcp_server.SKILLS / "README.md").read_text()
    assert core.endswith("| `⬆` in a chip | a rise, bad |\n" + listed), core[-600:]
    assert only == readme + listed, only[len(readme) :]
    print("  ✓  the core note lists the theme's own patterns after its spellings")


PLACED_BASE = """# Meanings

## Icons

| Write | Means | Slot |
|---|---|---|
| `⭐` | an icon leading a row | icon-label |
| `*⭐*` | the icon an empty state is about | icon-subject |
| `***⭐***` | an icon inside a compact element | compact |
| `"⭐"` | the glyph inside a sentence | inline |

## Chips

| Write | Means |
|---|---|
| `` _`Tag`_ `` | a tag in a compact row |

## Buttons

| Write | Means | Size | Slot |
|---|---|---|---|
| `[Label](/x)` | the main action, at the foot of a section | | foot-main |
| `*[Label](/x)*` | a quieter action there | | foot-quieter |
| `_[Label](/x)_` | the main action at the edge of a row | small | row-main |
| `___[Label](/x)___` | an action inside a compact element | extra small | compact |

## Icon buttons

| Write | Means | Slot |
|---|---|---|
| `[▶️](/x)` | the main icon action | foot-main |
| `_[▶️](/x)_` | the main icon action at the edge of a row | row-main |
"""

PLACED_THEME = """## Buttons

| Write | Means | Slot |
|---|---|---|
| `_[Label](/x)_` | a save at the edge of a row | row-main |
"""


def test_the_core_note_ends_with_where_each_icon_or_action_sits():
    """Agents read the core note and rarely guide('theme'), where an icon's or an
    action's spelling by its place was declared: the core note carries the rows
    whose slot is one of ``PLACED_SLOTS``, with base rows only too, and never
    repeats a row of the theme's own table. A bare spelling's place is left to
    the table's lead, and a compact element's rows to guide('theme')."""
    with _theme(PLACED_BASE, None, {}) as theme:
        core = _guide(theme, "README.md")
    with _theme(PLACED_BASE, PLACED_THEME, {}) as theme:
        own = _guide(theme, "README.md")
    readme = (mcp_server.SKILLS / "README.md").read_text()
    head = (
        "\n\n## Where an icon or an action sits\n\nWith this theme, an icon's or "
        "an action's spelling follows where it sits: write the one for its place. "
        "A place no row names takes the bare spelling.\n\n"
        "| Write | Means |\n|---|---|\n"
        "| `*⭐*` | the icon an empty state is about |\n"
        "| `[Label](/x)` | the main action, at the foot of a section |\n"
        "| `*[Label](/x)*` | a quieter action there |\n"
    )
    tail = (
        "| `[▶️](/x)` | the main icon action |\n"
        "| `_[▶️](/x)_` | the main icon action at the edge of a row |\n"
    )
    assert core == readme + head + (
        "| `_[Label](/x)_` | the main action at the edge of a row |\n" + tail
    ), core[len(readme) :]
    assert own.endswith(
        "| `_[Label](/x)_` | a save at the edge of a row |\n" + head + tail
    ), own[len(readme) :]
    assert own.count("_[Label](/x)_") == 1, own[len(readme) :]
    print("  ✓  the core note ends with where each icon or action sits")


def test_slots_parse_and_a_theme_row_inherits_none():
    contract = meanings.parse(meanings.BASE.read_text())
    slots = {r.write: r.slots for s in contract.sections for r in s.rows}
    assert slots["`**[Label](/x)**`"] == ("card-main",), slots
    assert slots["`` [`Label`](/x) ``"] == ("card-way-in", "title-edge", "nav", "minor")
    assert slots["`` `Tag` ``"] == () and slots["`✓`"] == (), slots
    # Size and Slot are each read by their header, so either may be left out.
    sizes = {r.write: r.size for s in contract.sections for r in s.rows}
    assert sizes["`*⭐*`"] == "large" and sizes["`[Label](/x)`"] == "", sizes
    own = (
        "## Buttons\n\n| Write | Means |\n|---|---|\n| `**[Label](/x)**` | a booking |\n"
        "\n## Icons\n\n| Write | Means | Slot |\n|---|---|---|\n"
        "| `*⭐*` | a hero | icon-subject |\n"
    )
    merged = meanings.merge(contract, meanings.parse(own))
    rows = {r.write: r for s in merged.sections for r in s.rows}
    assert rows["`**[Label](/x)**`"].slots == (), rows["`**[Label](/x)**`"]
    hero = rows["`*⭐*`"]
    assert (hero.size, hero.slots) == ("", ("icon-subject",)), hero
    print("  ✓  a Slot cell parses into its keys; a theme row inherits none")


# The slots the code reads: the placement table's and the card advice's.
_READ_SLOTS = meanings.PLACED_SLOTS | advice._CARD_SLOTS | {advice._WAY_IN_SLOT}


def test_the_root_contract_fills_every_slot_the_code_reads():
    """A slot no row of the root contract names drops its place from the core
    note and the advice for every theme, with no other sign."""
    contract = meanings.parse(meanings.BASE.read_text())
    named = {slot for s in contract.sections for r in s.rows for slot in r.slots}
    assert _READ_SLOTS <= named, sorted(_READ_SLOTS - named)
    assert named <= set(meanings.SLOTS), sorted(named - set(meanings.SLOTS))
    print("  ✓  the root contract fills every slot the code reads, from SLOTS only")


def _reworded(text: str) -> str:
    """*text* with every element row's *Means* cell replaced by a number."""
    lines, heading, n = [], "", 0
    for line in text.splitlines():
        heading = line[3:].strip().lower() if line.startswith("## ") else heading
        cells = meanings._cells(line) if line.startswith("| `") else []
        if cells and heading in meanings.ELEMENT_SECTIONS:
            n += 1
            line = "| " + " | ".join([cells[0], f"meaning {n}", *cells[2:]]) + " |"
        lines.append(line)
    return "\n".join(lines) + "\n"


def test_rewording_a_meaning_changes_no_pick():
    """Rows are found by their slot, so rewording *Means* drops none."""
    text = meanings.BASE.read_text()
    reworded = _reworded(text)
    assert "inside a card" not in reworded and "way in" not in reworded

    names = ["Copywriting", "Design", "Research"]
    opened = "".join(
        f"## {n}\n_About {n}_\n**[Open {n}](agent:open?s={n})**\n\n" for n in names
    )
    with contextlib.redirect_stdout(io.StringIO()):
        ast = session.group_markdown(opened, _kit())
    assert ast is not None

    def picks(base: str) -> tuple[list[str], list[str], list[str]]:
        with _theme(base, None, {}) as theme:
            placed = meanings.placed_spellings(theme)
        table = [
            meanings._cells(line)[0]
            for line in placed.splitlines()
            if line.startswith("| `")
        ]
        contract = meanings.parse(base)
        card = advice._card_spellings(contract)
        tips = advice.Reading().advise(ast.to_dict(), contract)
        way_in = [t["message"].split("every card is ")[-1].split(":")[0] for t in tips]
        return table, [part.split(" (")[0] for part in card.split("), ")], way_in

    before, after = picks(text), picks(reworded)
    assert before == after, (before, after)
    assert len(before[0]) == 14, before
    assert before[1] == [
        "`**[Label](/x)**`",
        "`***[Label](/x)***`",
        "`**[💬](/x)**`",
        "`***[❤️](/x)***`",
    ], before
    assert before[2] == ["`` [`Label`](/x) ``"], before
    print("  ✓  rewording a meaning changes no row the code picks")


def test_slot_is_never_served():
    """*Slot* is the code's: no table the agent is served carries it."""
    own = (
        "## Buttons\n\n| Write | Means | Slot |\n|---|---|---|\n"
        "| `____[Label](/x)____` | a booking | card-main |\n"
    )
    cards = "".join(
        f"## Candidate {n}\n_Designer_\n[Profile](agent:p?n={n}) *[Call](agent:c?n={n})*\n\n"
        for n in (1, 2)
    )
    with _theme(meanings.BASE.read_text(), own, {}) as theme:
        contract = meanings.load_contract(theme)
        assert contract is not None
        with contextlib.redirect_stdout(io.StringIO()):
            issues = check_markdown(cards + "## B\n\n***`Tag`***\n", _kit(), contract)
            ast = session.group_markdown(cards, _kit())
        served = [_guide(theme, "theme"), _guide(theme, "README.md"), contract.text()]
    assert ast is not None
    tips = advice.Reading().advise(ast.to_dict(), contract)
    assert [t["read"] for t in tips] == [advice.THEME], tips
    assert any(i["code"] == "undeclared-spelling" for i in issues), issues
    served += [i["message"] for i in issues + tips]
    assert any("`____[Label](/x)____`" in text for text in served[:2]), served[1][-400:]
    for text in served:
        assert "Slot" not in text, text[-400:]
        for line in text.splitlines():
            cells = meanings._cells(line) if line.startswith("|") else []
            assert not set(cells) & set(meanings.SLOTS), line
            assert not any(slot in line for slot in _READ_SLOTS), line
    print("  ✓  Slot is in nothing served to agents")


def test_check_warns_on_an_undeclared_spelling():
    contract = meanings.parse(BASE)
    doc = "## A\n\n**⭐**\n\n*⭐*\n\n⭐\n\n**[Go](/x)**\n\n*[Go](/y)*\n\n`Tag`\n"
    with contextlib.redirect_stdout(io.StringIO()):
        warned = check_markdown(doc, _kit(), contract)
        silent = check_markdown(doc, _kit())
    messages = [i["message"] for i in warned if i["code"] == "undeclared-spelling"]
    assert messages == [
        "`**⭐**` is not declared by this theme; write `⭐`. Its icons are: `⭐`, "
        '`*⭐*`, `"⭐"`.',
        "`*[Go](/y)*` is not declared by this theme; write `[Go](/y)`. Its buttons "
        "are: `[Label](/x)`, `**[Label](/x)**`, `` [`Label`](/x) ``.",
    ], messages
    assert all(
        i["level"] == "warning" for i in warned if i["code"] == "undeclared-spelling"
    )
    assert not any(i["code"] == "undeclared-spelling" for i in silent), silent
    print("  ✓  check warns on an undeclared spelling only, and only with a contract")


TEXT_BUTTON_THEME = """## Buttons

| Write | Means |
|---|---|
| `` *[`Label`](/x)* `` | a way in, quieter |
"""


def _undeclared(doc: str, contract: meanings.Contract) -> list[str]:
    with contextlib.redirect_stdout(io.StringIO()):
        issues = check_markdown(doc, _kit(), contract)
    return [i["message"] for i in issues if i["code"] == "undeclared-spelling"]


def test_check_reads_a_text_buttons_wrapper_as_its_spelling():
    # The backtick label makes a link a text button whatever wraps it, so the
    # wrapper is kept as its face and checked as a button's wrapper is.
    assert meanings.resolve("*[`More`](/y)*") == Selection(
        "button", "text", None, "italic"
    )
    assert meanings.resolve("[`More`](/y)") == Selection("button", "text")
    root = meanings.load_contract(session.repo_root() / "THEME.md")
    assert root is not None
    clean = '## A\n\n[`More`](/y)\n\nRead the "[guide](/g)" first.\n'
    assert _undeclared(clean, root) == [], _undeclared(clean, root)
    wrapped = "## A\n\n*[`More`](/y)*\n\n**[`All`](/z)**\n"
    assert _undeclared(wrapped, root) == [
        "`` *[`More`](/y)* `` is not declared by this theme; write "
        "`` [`More`](/y) ``. Its text buttons are: `` [`Label`](/x) ``.",
        "`` **[`All`](/z)** `` is not declared by this theme; write "
        "`` [`All`](/z) ``. Its text buttons are: `` [`Label`](/x) ``.",
    ], _undeclared(wrapped, root)
    with _theme(meanings.BASE.read_text(), TEXT_BUTTON_THEME, {}) as theme:
        own = meanings.load_contract(theme)
    assert own is not None
    assert _undeclared(wrapped, own) == [
        "`` **[`All`](/z)** `` is not declared by this theme; write "
        "`` [`All`](/z) ``. Its text buttons are: `` [`Label`](/x) ``, "
        "`` *[`Label`](/x)* ``."
    ], _undeclared(wrapped, own)
    print("  ✓  a text button's wrapper is declared or warned like a button's")


LINT_BASE = """## Icons

| Write | Means | Size |
|---|---|---|
| `⭐` | an icon in a label | standard |
| `*⭐*` | the icon a headline is about | large |

## Buttons

| Write | Means | Size |
|---|---|---|
| `[Label](/x)` | the main action | |
| `_[Label](/x)_` | the main action at a row's edge | small |

## Fixed colours

| Token | Means |
|---|---|
| `☀️` | decoration |
| `❌` `🛑` | failure |
"""

LINT_THEME = """## Emoji styles
### Primary
Size: 28
Padding: 9
Background color: #D5FFCC

### Secondary
Size: 12
Padding: 2

## Links
Fill color: #25845B
Padding: 12

### Quinary
Padding: 4

## Fixed colors
### Emoji
- ☀ #D7A139
- 🛑 #FA3C4F
- 🚶 #9170D6
"""


def _lint(drawing: str, patterns: dict[str, str] | None = None) -> theme_lint.Lint:
    with _theme(LINT_BASE, None, patterns or {}, drawing) as theme:
        return theme_lint.lint(theme)


def test_lint_reports_two_spellings_that_draw_the_same():
    # No `### Quinary` under `## Links`: the small button inherits Primary.
    drawing = LINT_THEME.replace("### Quinary\nPadding: 4\n", "")
    same = [m for m in _lint(drawing).messages if "draw the same" in m]
    assert same == [
        "`_[Label](/x)_` and `[Label](/x)` draw the same with this theme: give "
        "`## Links → ### Quinary` its own look, or remove `_[Label](/x)_` from "
        "MEANINGS.md."
    ], same
    assert not [m for m in _lint(LINT_THEME).messages if "draw the same" in m]
    print("  ✓  two declared spellings that draw the same are reported")


def test_lint_reports_a_size_order_the_drawing_contradicts():
    taller = [m for m in _lint(LINT_THEME).messages if "draws taller" in m]
    assert len(taller) == 1, taller
    assert taller[0].startswith(
        "`⭐` is sized standard but draws taller than `*⭐*`, sized large"
    ), taller
    assert "make `## Emoji styles` smaller" in taller[0], taller
    drawing = LINT_THEME.replace("Size: 12\nPadding: 2", "Size: 48\nPadding: 14")
    assert not [m for m in _lint(drawing).messages if "draws taller" in m]
    print("  ✓  a row's size the drawn heights contradict is reported")


def test_lint_reports_a_pin_with_no_row():
    pins = [m for m in _lint(LINT_THEME).messages if " pin " in m]
    # ☀ is declared as ☀️ (decoration still declares it) and 🛑 shares a cell
    # with ❌: only 🚶 is undeclared.
    assert pins == [
        "The `🚶` pin under `## Fixed colors → ### Emoji` has no row under "
        "`## Fixed colours` in MEANINGS.md: add one saying what it means, or "
        "remove the pin."
    ], pins
    print("  ✓  a pin with no Fixed colours row is reported, with or without U+FE0F")


def test_lint_reports_a_slot_it_does_not_know_and_missing_button_slots():
    own = (
        "## Buttons\n\n| Write | Means | Slot |\n|---|---|---|\n"
        "| `_[Label](/x)_` | the main action at a row's edge | row-mian |\n"
    )
    with _theme(LINT_BASE, own, {}, LINT_THEME) as theme:
        messages = theme_lint.lint(theme).messages
    unknown = [m for m in messages if "names the slot" in m]
    known = ", ".join(f"`{slot}`" for slot in meanings.SLOTS)
    assert unknown == [
        "`_[Label](/x)_` under `## Buttons` names the slot `row-mian`, which md2ui "
        f"does not read: write one of {known}, or leave the cell empty."
    ], unknown
    missing = [m for m in messages if "has no row with the slot" in m]
    assert missing == [
        "`## Buttons` in MEANINGS.md has no row with the slot `card-main`, the main "
        "action inside a card: the core note never names its spelling. Add "
        "`card-main` to that row's *Slot* cell.",
        "`## Buttons` in MEANINGS.md has no row with the slot `row-main`, the main "
        "action at the edge of a row: the core note never names its spelling. Add "
        "`row-main` to that row's *Slot* cell.",
    ], missing
    with _theme(meanings.BASE.read_text(), None, {}, LINT_THEME) as theme:
        root = theme_lint.lint(theme).messages
    assert not [m for m in root if "slot" in m], root
    print("  ✓  a slot outside SLOTS, and buttons with no card-main or row-main")


BROKEN = """---
name: broken
description: An anchor to nowhere.
---
```markdown
## A

[Go](#nowhere)
```
"""

WARNS = """---
name: warns
description: An undeclared chip.
---
```markdown
## A

`26` ___`27`___
```
"""


def test_lint_reports_design_in_a_meaning_or_a_description():
    own = "## Icons\n\n| Write | Means |\n|---|---|\n| `**⭐**` | a small icon |\n"
    styled = "---\nname: hero\ndescription: A green card for the headline.\n---\n"
    with _theme(LINT_BASE, own, {"hero": styled}, LINT_THEME) as theme:
        design = [m for m in theme_lint.lint(theme).messages if "names `" in m]
    assert design == [
        "`**⭐**` under `## Icons` means `a small icon`, which names `small`: say "
        "what it is for and where it goes; a size belongs in the row's third "
        "column, and a colour in THEME.md.",
        "Pattern `hero`'s description names `green`: say what the pattern is for, "
        "in the domain's words; its look is the theme's.",
    ], design
    assert not [m for m in _lint(LINT_THEME).messages if "names `" in m]
    print("  ✓  a colour or a size in a meaning or a pattern's description is reported")


def test_a_pattern_that_fails_check_is_not_served():
    patterns = {"broken": BROKEN, "warns": WARNS}
    with _theme(LINT_BASE, None, patterns, LINT_THEME) as theme:
        result = theme_lint.lint(theme)
        index = _guide(theme, "patterns")
        digest = _guide(theme, "theme")
        served = theme_lint.served_patterns(theme)
    assert result.broken_patterns == {"broken"}, result
    assert any(m.startswith("Pattern `broken` is not served") for m in result.messages)
    assert any(m.startswith("Pattern `warns`: ") for m in result.messages), result
    assert list(served) == ["warns"], served
    assert "- warns:" in index and "broken" not in index, index
    assert "- warns —" in digest and "broken" not in digest, digest
    print("  ✓  a pattern whose example errs is not served; one that warns is")


DECLARES = """---
name: overdue-days
description: Days past their date.
---
```markdown
## A

`26` __`27`__
```

**What the days mean here.** Inside this shape, and only here:

| Write | Means |
|---|---|
| `` __`9`__ `` | a day past its date |
"""


def test_a_patterns_declared_spellings_are_declared():
    patterns = {"overdue-days": DECLARES, "warns": WARNS}
    answer = "## A\n\n`26` __`27`__\n\n`28` ___`29`___\n"
    with _theme(LINT_BASE, None, patterns, LINT_THEME) as theme:
        result = theme_lint.lint(theme)
        contract = theme_lint.answer_contract(theme)
        digest = _guide(theme, "theme")
    assert contract is not None
    assert not [m for m in result.messages if "`overdue-days`" in m], result
    assert any(m.startswith("Pattern `warns`: ") for m in result.messages), result
    with contextlib.redirect_stdout(io.StringIO()):
        issues = check_markdown(answer, _kit(), contract)
    messages = [i["message"] for i in issues if i["code"] == "undeclared-spelling"]
    # The pattern's spelling is declared; the one no pattern declares still warns,
    # and its message lists the contract's chips only (none here).
    assert messages == [
        "`` ___`29`___ `` is not declared by this theme; write `` `29` ``. "
        "Its chips are: none."
    ], messages
    assert "__`9`__" not in digest, digest
    print(
        "  ✓  a spelling a served pattern declares is declared; the contract is unchanged"
    )


FONTS = session.repo_root() / "assets" / "fonts"

FONT_THEME = f"""## Fonts
- {FONTS / "Inter_18pt-Regular.ttf"}

## Tables

### Header
- Font name: IBM Plex Mono

## Text Styles

<!-- Code Block
- Font Name: Fira Code -->

Text
- Font Name: inter 18PT

Code Block
- Font Name: IBM Plex Mono
"""


def _font_lint(drawing: str) -> tuple[str, ...]:
    """The lint of a theme with no contract: only what the drawing alone shows."""
    with _theme(None, None, {}, drawing) as theme:
        return theme_lint.lint(theme).messages


def test_lint_reports_a_family_the_fonts_never_load():
    with contextlib.redirect_stdout(io.StringIO()):
        fallback = resolve_typeface("IBM Plex Mono", 400, False, {}).getFamilyName()
        mono = resolve_code_typeface("IBM Plex Mono", 400, False, {}).getFamilyName()
    fonts = [m for m in _font_lint(FONT_THEME) if "## Fonts" in m]
    # A code block falls back to a monospaced face, the header to the platform's.
    assert fonts == [
        "`IBM Plex Mono` (Tables → Header, Text Styles → Code Block) is not loaded "
        f"by `## Fonts`: add its files, or that text renders in `{fallback}` "
        f"(code blocks in `{mono}`)."
    ], fonts
    only_code = FONT_THEME.replace("- Font name: IBM Plex Mono\n", "", 1)
    code = [m for m in _font_lint(only_code) if "## Fonts" in m]
    assert code == [
        "`IBM Plex Mono` (Text Styles → Code Block) is not loaded by `## Fonts`: "
        f"add its files, or that text renders in `{mono}`."
    ], code
    # Loaded under the family name the file declares, not its file name.
    plex = str(FONTS / "IBMPlexMono-Regular.ttf")
    loaded = FONT_THEME.replace("## Tables", f"- {plex}\n\n## Tables")
    assert not [m for m in _font_lint(loaded) if "## Fonts" in m]
    print("  ✓  a family no `## Fonts` file loads is reported once, with its blocks")


def test_lint_never_downloads_a_theme_image():
    # A background that never answers must not hold the demo server's start.
    from md2ui.pipeline import render_placeholders

    asked: list[str] = []
    drawing = LINT_THEME + (
        "\n## Styling & Spacing\n### Root\n"
        "Background image: http://10.255.255.1/never.jpg\n"
    )
    was, POLICY.remote = POLICY.remote, True
    try:
        with patch.object(render_placeholders, "fetch_remote", asked.append):
            _lint(drawing)
    finally:
        POLICY.remote = was
    assert asked == [], asked
    print("  ✓  the lint draws a theme image by URL as never fetched")


CARD_MAIN_AS_UNDERSCORE = """## Buttons

| Write | Means | Size | Slot |
|---|---|---|---|
| `__[Label](/x)__` | the action a card is for | medium | card-main |
"""


def test_a_shared_pattern_is_served_in_the_projects_spelling():
    # The shared patterns are written in the default theme's spellings: each
    # wrapped one is served as this project writes its slot.
    listing = mcp_server.PATTERNS / "listing.md"
    default = _guide(session.repo_root() / "THEME.md", "patterns/listing")
    assert default == listing.read_text(), "the default theme reads it as written"
    assert "**[Reserve](agent:reserve?room=standard)**" in default
    real = meanings.BASE.read_text()
    with _theme(real, CARD_MAIN_AS_UNDERSCORE, {}, extends=False) as theme:
        own = _guide(theme, "patterns/listing")
    assert "__[Reserve](agent:reserve?room=standard)__" in own, own
    assert "**[Reserve]" not in own
    with _theme(real, None, {}, extends=False) as theme:
        bare = _guide(theme, "patterns/listing")
    assert "\n[Reserve](agent:reserve?room=standard)\n" in bare, bare
    # Only the example moves: the prose around it is the pattern's own.
    assert bare.split("```")[0] == listing.read_text().split("```")[0]
    root = meanings.load_contract(session.repo_root() / "THEME.md")
    for pattern in sorted(mcp_server.PATTERNS.glob("*.md")):
        assert pattern_respell.respelled(pattern, root) == pattern.read_text(), pattern
    print("  ✓  a shared pattern's example is served in the project's spelling")


_PLACEHOLDERS = """# Meanings

## Placeholders

| Write | Means |
|---|---|
| `![Sara](?md2ui.placeholder=avatar:SZ)` | a person with no photo: their initials |
| `![Acme](?md2ui.placeholder=brand:A)` | a company with no logo: its initial |
"""


def test_placeholder_rows_end_the_core_note():
    """Agents see a placeholder only through its row, and rarely read
    guide("theme"): the rows are served in the core note itself. The lead puts
    fetching the item's own picture first: led by the placeholder, agents drew one
    for a company whose logo was a second request away."""
    with _theme(None, _PLACEHOLDERS, {}, extends=False) as theme:
        served = meanings.placeholder_spellings(theme)
    lead = "\n\n## An item with no picture\n\nAn item's picture comes from the tool"
    assert served.startswith(lead), served
    assert served.index("second request") < served.index("placeholder in its place")
    assert (
        "| `![Sara](?md2ui.placeholder=avatar:SZ)` | a person with no photo" in served
    )
    assert "| `![Acme](?md2ui.placeholder=brand:A)` |" in served
    without = _PLACEHOLDERS.replace("## Placeholders", "## Chips")
    with _theme(None, without, {}, extends=False) as theme:
        assert meanings.placeholder_spellings(theme) == "", "no rows, no section"
    with _theme(None, None, {}, extends=False) as theme:
        assert meanings.placeholder_spellings(theme) == "", "no MEANINGS.md"
    print("  ✓  placeholder rows end the core note; none, or no file, adds nothing")


TESTS = [
    test_placeholder_rows_end_the_core_note,
    test_parse_resolves_spellings_as_the_grouper_does,
    test_merge_replaces_adds_and_removes,
    test_a_theme_file_is_its_whole_contract_unless_it_extends,
    test_a_shared_pattern_is_served_in_the_projects_spelling,
    test_guide_serves_the_digest_and_the_themes_patterns,
    test_a_themes_pattern_asked_under_patterns_is_served,
    test_the_core_note_ends_with_the_themes_own_spellings,
    test_the_core_note_lists_the_themes_own_patterns,
    test_the_core_note_ends_with_where_each_icon_or_action_sits,
    test_slots_parse_and_a_theme_row_inherits_none,
    test_the_root_contract_fills_every_slot_the_code_reads,
    test_rewording_a_meaning_changes_no_pick,
    test_slot_is_never_served,
    test_check_warns_on_an_undeclared_spelling,
    test_check_reads_a_text_buttons_wrapper_as_its_spelling,
    test_lint_reports_two_spellings_that_draw_the_same,
    test_lint_reports_a_size_order_the_drawing_contradicts,
    test_lint_reports_a_pin_with_no_row,
    test_lint_reports_design_in_a_meaning_or_a_description,
    test_lint_reports_a_slot_it_does_not_know_and_missing_button_slots,
    test_a_pattern_that_fails_check_is_not_served,
    test_a_patterns_declared_spellings_are_declared,
    test_lint_reports_a_family_the_fonts_never_load,
    test_lint_never_downloads_a_theme_image,
]

if __name__ == "__main__":
    print("Meanings Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    raise SystemExit(1 if failed else 0)
