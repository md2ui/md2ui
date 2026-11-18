"""
Unit tests for the advice ``check``, ``preview`` and ``show`` add (advice.py).

Pinned here:

  * a badge beside a hero number points to the icon roles, and the glyph inside
    the number's tier does not; a badge beside a word is not a number;
  * two values joined in a line of their own by an arrow or a glyph point to
    the icon roles; the glyph standing between them, or a heading, does not;
  * one amount alone on a chip points to the section on what a chip is for; a
    change, a set of prices, a table's cell or a status does not;
  * two or more cards each holding a full-size action are given the theme's
    spellings for an action inside a card;
  * a run whose every card holds the same card action worded as the same way in
    (`Open …`, `View on …`), whatever its target, is given the theme's way-in
    spelling; an action the card is for, a way in already written as a text
    button, and a single card are not;
  * a theme's own spellings point to the theme only when the answer uses that
    element, and the base contract alone never does;
  * a section with a pattern's shape that lacks what the pattern adds points to
    the pattern, with what to add and the pattern's cost: a lone Display figure
    (`hero-figure`), two to four bare ones (`kpis`), a line no figure leads
    (`chart-card`), rows that each draw a line with no change (`ticker-rows`),
    named groups of picture cards whose titles stand above their pictures
    (`shelf`); the
    pattern's own example, and the near-miss shapes, do not;
  * a pattern is silenced by reading it, not by reading the patterns index;
  * advice is given once per section per session, never for a section or a
    note already read;
  * ``reply_issues``, what a reply's sender returns, is ``check``'s issues and
    then the advice;
  * through the server: ``guide`` records what it served, so ``check`` advises
    on what is unread and is quiet once it is read.

Run with: uv run python tests/advice_tests.py
"""

import asyncio
import contextlib
import io
from pathlib import Path
from typing import Any

from md2ui import mcp_server, meanings, session
from md2ui.advice import CHARTS, CHIPS, ICON_ROLES, THEME, Reading, reply_issues
from md2ui.advice_patterns import pattern_hints
from md2ui.check import check_grouped
from md2ui.meanings import SKILLS_PATTERNS
from server_policy import restores_server_policy

_KIT = None


def _tree(markdown: str) -> dict:
    global _KIT
    if _KIT is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _KIT = session.load_grouping_kit()
    ast = session.group_markdown(markdown, _KIT)
    assert ast is not None
    return ast.to_dict()


def _topics(markdown: str, contract=None, reading: Reading | None = None) -> list:
    advice = (reading or Reading()).advise(_tree(markdown), contract)
    return [a["read"] for a in advice]


def test_a_badge_beside_a_hero_number_points_to_the_icon_roles():
    assert _topics("## Now\n\n☀️\n\n___75°F___\n") == [ICON_ROLES]
    assert _topics("## Now\n\n☀️ - ___75°F___\n") == [ICON_ROLES]
    assert _topics("## Now\n\n___☀️ 75°F___\n") == []
    assert _topics("## Route\n\n✈️ - ___AUH___\n") == []
    print("  ✓  a badge beside a hero number advises; inside the tier, or a word, not")


def test_two_values_joined_in_text_point_to_the_icon_roles():
    joined = Reading().advise(_tree("## Flight\n\n**SFO** → **JFK**\n"), None)
    assert [a["read"] for a in joined] == [ICON_ROLES], joined
    assert "`__SFO__ ... → ... __JFK__`" in joined[0]["message"], joined
    assert _topics("## Flight\n\nLIS ✈️ AUH\n") == [ICON_ROLES]
    assert _topics("## Flight\n\n__SFO__ ... ✈️ ... __JFK__\n") == []
    assert _topics("## Flight\n\nSan Francisco SFO → New York JFK\n") == [ICON_ROLES]
    assert _topics("## Lisbon → Tokyo ... `12 Nov`\n\n_Etihad_\n") == []
    assert (
        _topics("## Note\n\nWe fly from Lisbon → then on to Tokyo next week.\n") == []
    )
    print(
        "  ✓  two values joined in text advise; a glyph standing between them does not"
    )


def test_a_lone_amount_on_a_chip_points_to_the_chips_section():
    # The shape of screenshots/IMG_4974.PNG and IMG_4975.PNG: one total per card.
    cards = (
        "## Lo que destaca\n\n### Apps de comida\n\n20 pedidos en Rappi\n\n"
        "`$6,955.70`\n\n### Renta\n\nEl 33% del mes\n\n`$14,000.00`\n"
    )
    advice = Reading().advise(_tree(cards), None)
    assert [a["read"] for a in advice] == [CHIPS], advice
    assert "`__$6,955.70__`" in advice[0]["message"], advice
    assert _topics("## Tacos\n\n**6 oct** ... `$634.24`\n") == [CHIPS]
    # A change, a set of prices, a table's cells, and a word are chips.
    assert _topics("## AAPL\n\n**$189.20** ... `▲ +2%`\n") == []
    assert _topics("## Tacos\n\n**6 oct** ... `-$634.24`\n") == []
    assert _topics("## Plans\n\n`$9` `$19` `$29`\n") == []
    assert _topics("## Plans\n\n| Plan | Price |\n|---|---|\n| Basic | `$5` |\n") == []
    assert _topics("## Order\n\n`Liquidado`\n") == []
    print("  ✓  a lone amount on a chip advises; a change, a set or a status does not")


def test_cards_with_full_size_actions_get_the_themes_card_spellings():
    base = meanings.parse(meanings.BASE.read_text())
    cards = "".join(
        f"## Candidate {n}\n_Designer_\n[Profile](agent:p?n={n}) *[Call](agent:c?n={n})*\n\n"
        for n in (1, 2)
    )
    advice = Reading().advise(_tree(cards), base)
    assert [a["read"] for a in advice] == [THEME], advice
    assert "`**[Label](/x)**` (the main action inside a card" in advice[0]["message"]
    sized = cards.replace("[Profile]", "**[Profile]").replace("n=1) *", "n=1)** *")
    sized = sized.replace("n=2) *", "n=2)** *").replace("*[Call]", "***[Call]")
    sized = sized.replace("c?n=1)*", "c?n=1)***").replace("c?n=2)*", "c?n=2)***")
    assert Reading().advise(_tree(sized), base) == [], sized
    assert Reading().advise(_tree(cards), None) == []
    print("  ✓  cards with full-size actions get the theme's card spellings")


def _cards(names: list[str], action) -> str:
    return "".join(f"## {name}\n_About {name}_\n{action(name)}\n\n" for name in names)


def test_a_way_in_on_every_card_gets_the_themes_way_in_spelling():
    """Agents write `**[Open …]**` on every card for a way in to the item; the
    contract spells a way in that repeats on every card as a text button."""
    base = meanings.parse(meanings.BASE.read_text())
    services = ["Copywriting", "Design", "Research", "Strategy"]
    opened = _cards(services, lambda n: f"**[Open {n}](agent:open?s={n.lower()})**")
    advice = Reading().advise(_tree(opened), base)
    assert [a["read"] for a in advice] == [THEME], advice
    message = advice[0]["message"]
    assert message.startswith("These 4 cards each hold `**[Open Copywriting]"), message
    assert 'every card is `` [`Label`](/x) ``: `guide("theme")`' in message

    hotels = ["Hotel Arts", "Casa Fuster", "Hotel Neri"]
    viewed = _cards(
        hotels, lambda n: f"**[View on Expedia](https://expedia.com/{n[-4:]})**"
    )
    assert _topics(viewed, base) == [THEME]

    reserve = _cards(hotels, lambda n: f"**[Reserve](agent:reserve?h={n[-4:]})**")
    add = _cards(["Mug", "Cap", "Tee"], lambda n: f"**[Add to cart](agent:add?p={n})**")
    text = _cards(services, lambda n: f"[`Open {n}`](agent:open?s={n.lower()})")
    single = _cards(services[:1], lambda n: f"**[Open {n}](agent:open?s=copy)**")
    for silent in (reserve, add, text, single):
        assert Reading().advise(_tree(silent), base) == [], silent
    assert Reading().advise(_tree(opened), None) == []
    print("  ✓  a way in on every card gets the theme's way-in spelling")


def test_a_themes_own_spellings_point_to_the_theme_when_used():
    base = meanings.parse(meanings.BASE.read_text())
    own = meanings.parse(
        "## Chips\n\n| Write | Means |\n|---|---|\n| `` **`Tag`** `` | good news |\n"
    )
    merged = meanings.merge(base, own)
    assert _topics("## Status\n\n`Open`\n", merged) == [THEME]
    assert (
        _topics("## Status\n\nAll fine today, nothing to report.\n\nSee you.\n", merged)
        == []
    )
    assert _topics("## Status\n\n`Open`\n", base) == []
    print("  ✓  a theme's own spellings advise when the answer uses that element")


def _example(pattern: str) -> str:
    """The Markdown example a pattern file shows."""
    text = (SKILLS_PATTERNS / f"{pattern}.md").read_text()
    return text.split("```markdown\n", 1)[1].split("\n```\n", 1)[0] + "\n"


def _pattern_advice(markdown: str, pattern: str, reading: Reading | None = None):
    """The advice that points to *pattern*, checked to fire alone and to end on
    the pattern's cost, the word count of its file."""
    advice = (reading or Reading()).advise(_tree(markdown), None)
    assert [a["read"] for a in advice] == [f"patterns/{pattern}"], advice
    words = len((SKILLS_PATTERNS / f"{pattern}.md").read_text().split())
    cost = f'`guide("patterns/{pattern}")`, ≈{words} words.'
    assert advice[0]["message"].endswith(cost), advice
    return advice[0]["message"]


def _silent(markdown: str, reading: Reading | None = None) -> bool:
    """No advice points to a pattern."""
    advice = (reading or Reading()).advise(_tree(markdown), None)
    return not [a for a in advice if a["read"].startswith("patterns/")]


def test_a_lone_figure_points_to_hero_figure():
    lone = "## Balance\n\n___$12,480.22___\n"
    message = _pattern_advice(lone, "hero-figure")
    assert message.startswith("`$12,480.22` leads its section on its own."), message
    assert _silent(lone, Reading(read={"patterns/hero-figure"}))
    # Labelled, with its change, a tile in a card, or not one figure.
    assert _silent(_example("hero-figure"))
    assert _silent("## Balance\n\n_Available_\n___$12,480.22___\n")
    assert _silent("## Balance\n\n___$12,480.22___ - `+2%`\n")
    assert _silent("## Today\n\n### UV index\n\n___12___\n")
    assert _silent("## Inbox\n\n___5 unread emails___\n")
    print("  ✓  a lone Display figure points to hero-figure; a labelled one does not")


def test_bare_figures_point_to_kpis():
    bare = "## This week\n\n___$48,200___\n\n___1,284___\n\n___$37.54___\n"
    message = _pattern_advice(bare, "kpis")
    assert message.startswith("These 3 figures, `$48,200` first,"), message
    assert _silent(bare, Reading(read={"patterns/kpis"}))
    assert _silent(_example("kpis"))
    print("  ✓  two to four bare figures point to kpis; labelled ones do not")


def test_a_line_with_no_figure_points_to_chart_card():
    line = "Spending ($): 120 → 140 → 90 → 160 → 130\n"
    message = _pattern_advice(f"## Spending\n\n{line}", "chart-card")
    assert message.startswith("The line `Spending ($)` has no figure"), message
    assert _silent(f"## Spending\n\n{line}", Reading(read={"patterns/chart-card"}))
    # A figure leads it, or leads the page elsewhere: the line is its history.
    assert _silent(_example("chart-card"))
    assert _silent(f"## Balance\n\n_Available_\n___$1,240___\n\n## History\n\n{line}")
    print("  ✓  a line no figure leads points to chart-card; one under a figure not")


def test_rows_that_draw_lines_with_no_change_point_to_ticker_rows():
    prices = (("AAPL", 180, 184, 189), ("MSFT", 420, 415, 412), ("NVDA", 110, 118, 121))
    rows = "## Watchlist\n\n" + "".join(
        f"- **{name}** ... Price ($): {a} → {b} → {c} ... ${c}.20\n"
        for name, a, b, c in prices
    )
    message = _pattern_advice(rows, "ticker-rows")
    assert message.startswith("These 3 rows each draw a line and no change."), message
    assert _silent(rows, Reading(read={"patterns/ticker-rows"}))
    # Each with its change, or a change and no line: rows of one value.
    assert _silent(_example("ticker-rows"))
    assert _silent(
        "## Watchlist\n\n- **AAPL** ... $189.20 ... `+1.2%`\n"
        "- **MSFT** ... $412.10 ... `-0.4%`\n- **NVDA** ... $121.40 ... `+3.1%`\n"
    )
    print("  ✓  rows each drawing a line with no change point to ticker-rows")


def _shelf(group: str, items: list[str], body: str = "_Mara Quinn_") -> str:
    cards = "".join(
        f"### {i}\n![{i}]({i.lower()}.jpg)\n{body}\n$18.99\n\n" for i in items
    )
    return f"## {group}\n\n{cards}"


def test_named_groups_of_picture_cards_point_to_shelf():
    shelves = _shelf("Fiction", ["Salt", "Tide"]) + _shelf("Audio", ["Glass", "Ferry"])
    message = _pattern_advice(shelves, "shelf")
    assert "Browse all" not in message, message
    assert "untitled `### `" in message, message
    assert _silent(shelves, Reading(read={"patterns/shelf"}))
    # One group, cards read rather than picked, or the pattern itself.
    assert _silent(_shelf("Fiction", ["Salt", "Tide"]))
    passage = (
        "A long paragraph about the place, its history and why it is worth a visit."
    )
    read = _shelf("Food", ["Tacos", "Elote"], passage)
    assert _silent(read + _shelf("Culture", ["Frida", "Lucha"], passage))
    assert _silent(_example("shelf"))
    print("  ✓  named groups of picture cards point to shelf; read cards do not")


def test_the_patterns_index_does_not_silence_a_pattern():
    lone = "## Balance\n\n___$12,480.22___\n"
    # The triggers know nothing of the session; ``Reading`` decides what is sent.
    assert [t for t, _ in pattern_hints(_tree(lone))] == ["patterns/hero-figure"]
    _pattern_advice(lone, "hero-figure", Reading(read={"patterns"}))
    reading = Reading()
    _pattern_advice(lone, "hero-figure", reading)
    assert _silent(lone, reading)
    print("  ✓  the patterns index does not silence a pattern; advice is given once")


def test_advice_is_given_once_and_never_for_what_was_read():
    hero = "## Now\n\n☀️\n\n___75°F___\n"
    reading = Reading()
    assert _topics(hero, reading=reading) == [ICON_ROLES]
    assert _topics(hero, reading=reading) == []
    assert _topics(hero, reading=Reading(read={"elements"})) == []
    assert _topics(hero, reading=Reading(read={ICON_ROLES})) == []
    own = meanings.parse(
        "## Chips\n\n| Write | Means |\n|---|---|\n| `` **`Tag`** `` | good |\n"
    )
    merged = meanings.merge(meanings.parse(meanings.BASE.read_text()), own)
    every = "## Now\n\n☀️\n\n___75°F___\n\n## Flight\n\nLIS ✈️ AUH\n\n`Open`\n"
    assert _topics(every, merged) == [ICON_ROLES, THEME]
    print("  ✓  advice once per section, never for a read note")


def test_reply_issues_are_the_checks_then_the_advice():
    markdown = "## Now\n\n☀️\n\n___75°F___\n\n[See pricing](#pricing)\n"
    _tree(markdown)  # loads the grouping kit
    assert _KIT is not None
    ast = session.group_markdown(markdown, _KIT)
    issues = reply_issues(markdown, ast, None, Reading())
    checks = check_grouped(markdown, ast, None)
    assert checks and issues[: len(checks)] == checks, issues
    assert [i["read"] for i in issues[len(checks) :]] == [ICON_ROLES], issues
    print("  ✓  a reply's issues are check's, then the session's advice")


def test_the_server_advises_on_what_guide_has_not_served():
    server = mcp_server.build_server(Path("data/markdown/tests/THEME.md"))

    def call(tool: str, args: dict) -> Any:
        with contextlib.redirect_stdout(io.StringIO()):
            result: Any = asyncio.run(server.call_tool(tool, args))
        return result.structured_content.get("result")

    hero = "## Now\n\n☀️\n\n___75°F___\n"
    first = [i for i in call("check", {"markdown": hero}) if i["code"] == "advice"]
    assert [i["read"] for i in first] == [ICON_ROLES], first

    server = mcp_server.build_server(Path("data/markdown/tests/THEME.md"))
    call("guide", {"topic": ICON_ROLES})
    after = [i for i in call("check", {"markdown": hero}) if i["code"] == "advice"]
    assert after == [], after
    print("  ✓  check advises on an unread section; guide's read silences it")


_WEEK = "| Day | High | Low |\n|---|---|---|\n| Mon | 24°C | 15°C |\n| Tue | 23°C | 14°C |\n| Wed | 21°C | 12°C |\n"


def test_a_tabulated_series_with_no_figure_points_to_the_chart_spellings():
    """A table column of three or more values in one unit, on a page that draws no
    figure, names the chart spellings and says the table can stay."""
    advice = Reading().advise(_tree(f"## Week\n\n{_WEEK}"), None)
    assert [a["read"] for a in advice] == [CHARTS], advice
    message = advice[0]["message"]
    assert message.startswith(
        "The `High`, `Low` columns hold 3 values each in `°C`, and the page draws "
        "no figure."
    ), message
    assert "`Name (°C):`" in message and "`A, B (°C):`" in message, message
    assert "The table can stay." in message, message
    # The unit in the header, the cells bare.
    header_unit = (
        "## Wind\n\n| Day | Wind (km/h) | Gusts (km/h) |\n|---|---|---|\n"
        "| Mon | 15 | 40 |\n| Tue | 22 | 67 |\n| Wed | 18 | 51 |\n"
    )
    advice = Reading().advise(_tree(header_unit), None)
    assert [a["read"] for a in advice] == [CHARTS], advice
    assert advice[0]["message"].startswith(
        "The `Wind`, `Gusts` columns hold 3 values each in `km/h`"
    ), advice[0]["message"]
    print("  ✓  a tabulated series on a page with no figure points to the charts")


def test_a_tabulated_series_beside_a_figure_or_without_a_series_is_silent():
    for markdown in (
        f"## Week\n\nHigh (°C): 24 → 23 → 21\n\n{_WEEK}",  # a line is a figure
        f"## Week\n\n- Mon: 40%\n- Tue: 60%\n- Wed: 50%\n\n{_WEEK}",  # bars too
        "## Wind\n\nWind (km/h): 15 → 22 → 18\n\n| Day | Wind (km/h) |\n|---|---|\n"
        "| Mon | 15 |\n| Tue | 22 |\n| Wed | 18 |\n",  # header unit, beside a line
        "## Week\n\n| Day | Value |\n|---|---|\n| Mon | 24°C |\n| Tue | $23 |\n| Wed | 21% |\n",
        "## Week\n\n| Day | High |\n|---|---|\n| Mon | 24°C |\n| Tue | 23°C |\n",
        "## Week\n\n| Day | Visitors |\n|---|---|\n| Mon | 240 |\n| Tue | 230 |\n| Wed | 210 |\n",
    ):
        assert CHARTS not in _topics(markdown), markdown
    print("  ✓  beside a figure, in mixed units, under three rows or unitless: silent")


TESTS = [
    restores_server_policy(test)
    for test in [
        test_a_tabulated_series_with_no_figure_points_to_the_chart_spellings,
        test_a_tabulated_series_beside_a_figure_or_without_a_series_is_silent,
        test_a_badge_beside_a_hero_number_points_to_the_icon_roles,
        test_two_values_joined_in_text_point_to_the_icon_roles,
        test_a_lone_amount_on_a_chip_points_to_the_chips_section,
        test_cards_with_full_size_actions_get_the_themes_card_spellings,
        test_a_way_in_on_every_card_gets_the_themes_way_in_spelling,
        test_a_themes_own_spellings_point_to_the_theme_when_used,
        test_a_lone_figure_points_to_hero_figure,
        test_bare_figures_point_to_kpis,
        test_a_line_with_no_figure_points_to_chart_card,
        test_rows_that_draw_lines_with_no_change_point_to_ticker_rows,
        test_named_groups_of_picture_cards_point_to_shelf,
        test_the_patterns_index_does_not_silence_a_pattern,
        test_advice_is_given_once_and_never_for_what_was_read,
        test_reply_issues_are_the_checks_then_the_advice,
        test_the_server_advises_on_what_guide_has_not_served,
    ]
]

if __name__ == "__main__":
    print("Advice Tests")
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
