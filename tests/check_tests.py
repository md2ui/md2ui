"""
Unit tests for what ``check`` adds to an issue beyond its message, and for the
effect warnings it reads off the grouping.

Pinned here:

  * an issue with a mechanical fix carries ``line`` (1-based, in the document as
    sent), ``text`` (that line as written) and ``replacements`` (the line
    rewritten, one per meaning) — two for a dash that split a heading, one for an
    escape that draws its backslash. Nothing is applied: the author chooses;
  * an issue with no mechanical fix carries its message alone;
  * a picture that a pictureless `;;;` row cut off from its run's ratio is named,
    and the same picture with its own params, cards and lone pictures are not;
  * a run broken by one card with a different number of buttons is named, and
    the same cards with one button each are not;
  * a ``note`` is advice from a fact of the tree: one ``agent:`` offer (action and
    params, whatever the label) shown twice, a run of cards where some are
    tappable and some are not, and a styled name a spaced dash cut in two (not a link, not an emoji badge), each
    with the escape and the em dash that keep it whole — each silent on its near
    miss;
  * a main button whose label is long enough to fill a phone card is a note; the
    same words as a text link, or a short main button, are not;
  * plain task boxes no ``?md2ui.commit=1`` button commits are a note; with one,
    or linked to their own action, they are not;
  * a link's ``md2ui.*`` param that nothing reads is a warning: any one on a
    non-``agent:`` link, anything but ``commit`` on an ``agent:`` one.

The other codes are pinned in ``mcp_server_tests.py``.

Run with: uv run python tests/check_tests.py
"""

import contextlib
import io
import sys

from md2ui import session
from md2ui.check import check_markdown

_MODELS = None


def _check(markdown: str) -> list[dict]:
    global _MODELS
    with contextlib.redirect_stdout(io.StringIO()):
        if _MODELS is None:
            _MODELS = session.load_grouping_kit()
        return check_markdown(markdown, _MODELS)


def _coded(issues: list[dict], code: str) -> list[dict]:
    return [issue for issue in issues if issue["code"] == code]


def test_a_split_heading_carries_both_replacements():
    doc = "Intro.\n\n## Deploying - a guide\n\nText.\n"
    [issue] = _coded(_check(doc), "split-heading")
    assert issue["line"] == 3, issue
    assert issue["text"] == "## Deploying - a guide", issue
    assert issue["replacements"] == [
        "## Deploying \\- a guide",
        "## Deploying — a guide",
    ], issue
    # A numbered heading records its split one level down; it is found all the same.
    [numbered] = _coded(_check("## 1. **Strobe** - Deadmau5\n"), "split-heading")
    assert numbered["line"] == 1, numbered
    assert numbered["replacements"][0] == "## 1. **Strobe** \\- Deadmau5", numbered
    print("  ✓  check: a split heading names its line and both spellings")


def test_a_drawn_backslash_carries_its_replacement():
    doc = "## A\n\n```\ncode \\— kept\n```\n\nShip it \\— now, `a \\— b`.\n"
    [issue] = _coded(_check(doc), "drawn-backslash")
    assert issue["line"] == 7, issue
    assert issue["text"] == "Ship it \\— now, `a \\— b`.", issue
    # The code span is the author's text, drawn as written: left alone.
    assert issue["replacements"] == ["Ship it — now, `a \\— b`."], issue
    print("  ✓  check: a drawn backslash names its line and the bare spelling")


def test_an_escaped_dot_is_a_drawn_backslash():
    # A dot divides nothing (ADR-205) and Markdown escapes ASCII punctuation
    # only, so a backslash before a dot is drawn, as before a long dash, and
    # check names each one with the bare spelling.
    doc = "## A\n\n**Concha y Toro \\· Vino**\n\n750 ml \\• 13% ABV\n\nNow \\— later.\n"
    issues = _coded(_check(doc), "drawn-backslash")
    assert [i["text"] for i in issues] == [
        "**Concha y Toro \\· Vino**",
        "750 ml \\• 13% ABV",
        "Now \\— later.",
    ], issues
    print("  ✓  check: a backslash before a dot is drawn, and named")


def test_an_issue_without_a_mechanical_fix_keeps_its_message_alone():
    doc = "# Page\n\nIntro.\n\n[Go]() [Away](#nowhere)\n"
    issues = _check(doc)
    assert {i["code"] for i in issues} >= {"reports-nothing", "anchor-missing"}, issues
    for issue in issues:
        assert not {"line", "text", "replacements"} & issue.keys(), issue
    print("  ✓  check: an issue with no mechanical fix carries no replacement")


def _rows(ratios: dict[str, str]) -> str:
    """Two `##` sections of `;;;` picture rows, each picture with its ratio
    from *ratios*."""

    def row(name: str) -> str:
        params = f"?md2ui.aspect_ratio={ratios[name]}" if name in ratios else ""
        return f";;;\n![{name}](https://example.com/{name}.jpg{params})\n" + (
            f":::1\n**{name}**\n_Line_\n:::2\n"
        )

    return "\n".join(
        f"## {t}\n{row(a)}{row(b)};;;\n"
        for t, a, b in (("One", "A", "B"), ("Two", "C", "D"))
    )


def test_the_ratio_warning_counts_runs_as_the_render_polls_them():
    """`check` follows the render: a picture is named only when it falls back to
    the default crop, so a ratio on the first row of each section is enough, a
    list row shares the first row's, and pictures on one line each keep their own."""
    first_of_each = _check(_rows({"A": "4:3", "C": "4:3"}))
    assert not _coded(first_of_each, "image-ratio"), first_of_each
    [bare] = _coded(_check(_rows({})), "image-ratio")
    assert bare["message"].startswith("4 pictures"), bare
    # The cheapest fix, named: one ratio on the first picture sets the run.
    assert "on the first picture" in bare["message"], bare
    assert bare["message"].endswith("; the run takes it."), bare
    [half] = _coded(_check(_rows({"A": "4:3"})), "image-ratio")
    assert half["message"].startswith("1 of the 4 pictures"), half
    circle = "?md2ui.max_width=56&md2ui.aspect_ratio=1:1&md2ui.shape=circle"
    rows = "".join(
        f"- ![{t}](https://example.com/{t}.jpg{circle if t == 'Eva' else ''}) - "
        f"**{t}** : _Received_ ... +$5\n"
        for t in ("Eva", "Ben", "Mo")
    )
    assert not _coded(_check(rows), "image-ratio")
    assert _coded(_check(rows.replace(circle, "")), "image-ratio")
    line = " ".join(
        f"![{t}](https://example.com/{t}.png{'?md2ui.aspect_ratio=1:1' if t == 'A' else ''})"
        for t in "ABC"
    )
    [one_line] = _coded(_check(f"## Logos\n\n{line}\n"), "image-ratio")
    assert one_line["message"].startswith("2 of the 3 pictures"), one_line
    print("  ✓  check: the ratio warning counts each run as the render polls it")


def test_one_offer_shown_twice_is_a_note():
    doc = (
        "## Commits\n\nText.\n\n[Run make check](agent:make-check)\n\n"
        "## Work\n\nMore.\n\n*[Check again](agent:make-check)*\n"
    )
    [issue] = _coded(_check(doc), "repeated-offer")
    assert issue["level"] == "note" and issue["x"] == 1, issue
    assert "`agent:make-check`" in issue["message"], issue
    # The same action with other params is another offer: three Saves, three uris.
    near = "## Files\n\n[Save](agent:save?uri=a) [Save](agent:save?uri=b)\n"
    assert not _coded(_check(near), "repeated-offer")
    # A button inside a link card clicks through to the card: one offer.
    card = "## Plans\n\n[\n### Team\nFor ten.\n\n[Choose](agent:pick)\n](agent:pick)\n"
    assert not _coded(_check(card), "repeated-offer")
    print("  ✓  check: one agent offer shown twice is a note; other params are not")


def test_a_long_main_button_is_a_note():
    # Whole payees written as main buttons.
    payees = (
        "## Transferir\n\n"
        "[Aleja : Alejandra Ramírez López · BBVA México](agent:pay?to=1)\n\n"
        "[Sofi : Sofía Navarro Peña · STP •••• 6863](agent:pay?to=2)\n"
    )
    found = _coded(_check(payees), "long-main-button")
    assert [i["x"] for i in found] == [0, 1], found
    assert all(i["level"] == "note" for i in found), found
    assert "of 45 characters" in found[0]["message"], found
    # A text link draws the same words quietly; a short main button fits.
    text_link = "## Pay\n\n[`Alejandra Ramírez López · BBVA México`](agent:pay?to=1)\n"
    assert not _coded(_check(text_link), "long-main-button")
    short = (
        "## Pay\n\nAlejandra Ramírez López · BBVA México\n\n[Pagar](agent:pay?to=1)\n"
    )
    assert not _coded(_check(short), "long-main-button")
    print("  ✓  check: a long main button is a note; a text link or short one is not")


_CHOICE = "{open}\n### {name}\n{line}\n`{price}`\n{close}\n\n"


def _choices(tappable: tuple[bool, ...]) -> str:
    doc = "## Pick a delivery option\n\n"
    rows = [("Standard", "In 3 to 5 days", "Free"), ("Express", "Next day", "$12")]
    rows.append(("Pickup", "At the store", "Free"))
    for (name, line, price), tap in zip(rows, tappable, strict=True):
        close = f"](agent:choose?option={name.lower()})" if tap else ""
        doc += _CHOICE.format(
            open="[" if tap else "", name=name, line=line, price=price, close=close
        )
    return doc


def test_a_run_of_cards_only_partly_tappable_is_a_note():
    [issue] = _coded(_check(_choices((True, True, False))), "mixed-tappable-run")
    assert issue["level"] == "note", issue
    assert "`Pickup`" in issue["message"] and "`Standard`" in issue["message"], issue
    for same in ((True, True, True), (False, False, False)):
        assert not _coded(_check(_choices(same)), "mixed-tappable-run"), same
    print("  ✓  check: a run whose cards are only partly tappable is a note")


def test_a_styled_name_cut_at_its_dash_is_a_note():
    """Names copied from data, as Spotify and a file list return them, and the
    bold spans that must stay silent."""
    doc = (
        "## Picks\n\n**The Chain - 2004 Remaster**\nFleetwood Mac\n\n"
        '**"Heroes" - 2017 Remaster**\nDavid Bowie\n\n'
        "- **Under Pressure - Remastered 2011** - Queen\n\n"
        "3. ***Meeting Notes - February 2026.pdf*** - February 4, 2026\n"
    )
    issues = _coded(_check(doc), "dash-in-styled-name")
    assert [i["line"] for i in issues] == [3, 6, 9, 11], issues
    first = issues[0]
    assert (
        first["level"] == "note" and "`The Chain - 2004 Remaster`" in (first["message"])
    ), first
    assert first["replacements"] == [
        "**The Chain \\- 2004 Remaster**",
        "**The Chain — 2004 Remaster**",
        "**The Chain** - **2004 Remaster**",
    ], first
    # Only the name's own dash: the one dividing the row stays.
    assert issues[2]["replacements"][0] == (
        "- **Under Pressure \\- Remastered 2011** - Queen"
    ), issues[2]
    # The escape keeps the name whole, and a piece styled on its own divides
    # on purpose: either way, nothing left to note.
    for choice in (0, 2):
        fixed = doc
        for issue in issues:
            fixed = fixed.replace(issue["text"], issue["replacements"][choice])
        assert not _coded(_check(fixed), "dash-in-styled-name"), fixed
    for style in ("*", "_", "__", "___", "~~"):
        styled = f"## T\n\n{style}The Chain - 2004 Remaster{style}\nFleetwood Mac\n"
        assert _coded(_check(styled), "dash-in-styled-name"), style
    for silent in (
        "## Nav\n\n**[Back](/prev)** - **[Next](/next)**\n",
        "## Agenda\n\n### **8:00 AM - 9:00 AM**\n\nRegistration.\n",
        "## Badges\n\n**⭐ - Popular**\n\n***☀️ - 75°***\n",
        "## Code\n\n**`a - b`**\n",
        '## Quoted\n\n*"The Chain - 2004 Remaster"*\nFleetwood Mac\n',
        "## Parens\n\n_(Live - 1980)_\nFleetwood Mac\n",
    ):
        assert not _coded(_check(silent), "dash-in-styled-name"), silent
    print(
        "  ✓  check: a styled name cut at its dash is a note; links and badges are not"
    )


def test_a_picture_after_a_pictureless_row_is_named():
    """An item without a picture ends the `;;;` run, so a later picture loses
    the first one's ratio."""

    def row(name: str, params: str = "", picture: bool = True) -> str:
        image = (
            f"![{name}](https://example.com/{name}.jpg{params})\n" if picture else ""
        )
        return f";;;\n{image}:::1\n**{name}**\n_Line_\n:::2\n"

    ratio = "?md2ui.aspect_ratio=4:3"
    doc = "## Bays\n" + row("A", ratio) + row("B", picture=False) + row("C") + ";;;\n"
    [issue] = _coded(_check(doc), "image-ratio-after-break")
    assert issue["level"] == "warning", issue
    assert "`C`" in issue["message"] and "`A`" in issue["message"], issue
    # Two breaks: each picture past a break is named, not just the first.
    twice = doc.removesuffix(";;;\n") + row("D", picture=False) + row("E") + ";;;\n"
    named = _coded(_check(twice), "image-ratio-after-break")
    assert ["`C`" in i["message"] for i in named] == [True, False], named
    assert "`E`" in named[1]["message"], named
    # A run after the break is left to `image-ratio`: one report, one fix.
    two = doc.removesuffix(";;;\n") + row("D") + ";;;\n"
    issues = _check(two)
    assert not _coded(issues, "image-ratio-after-break"), issues
    assert _coded(issues, "image-ratio"), issues
    # A circle is lost the same way, and the message names params, not a ratio.
    circle = doc.replace(ratio, "?md2ui.shape=circle")
    [lost] = _coded(_check(circle), "image-ratio-after-break")
    assert "params `A` set" in lost["message"], lost
    repeated = doc.replace("C.jpg)", f"C.jpg{ratio})")
    assert not _coded(_check(repeated), "image-ratio-after-break"), repeated
    # Cards keep their run across a card without a picture; lone pictures
    # between cuts are no run at all.
    cards = (
        f"## Places\n\n### A\n![A](https://example.com/a.jpg{ratio})\nText.\n\n"
        "### B\nText.\n\n### C\n![C](https://example.com/c.jpg)\nText.\n"
    )
    lone = (
        f"## Photos\n\n![A](https://example.com/a.jpg{ratio})\n\n___\n\n"
        "**Text**\n\n___\n\n![C](https://example.com/c.jpg)\n"
    )
    for silent in (cards, lone):
        assert not _coded(_check(silent), "image-ratio-after-break"), silent
    print(
        "  ✓  check: a picture after a pictureless row is named; cards and lone pictures are not"
    )


def test_an_empty_picture_keeps_its_run():
    """`![Name]()` is a picture with no
    picture, valid, and a member of its run. The after-break warning offers it as
    a fix; a run holding one is one run, to both run warnings."""

    def row(name: str, picture: str) -> str:
        return f";;;\n{picture}\n:::1\n**{name}**\n_Line_\n:::2\n"

    ratio = "?md2ui.aspect_ratio=4:3"
    broken = (
        "## Bays\n"
        + row("A", f"![A](https://example.com/A.jpg{ratio})")
        + ";;;\n:::1\n**B**\n_Line_\n:::2\n"
        + row("C", "![C](https://example.com/C.jpg)")
        + ";;;\n"
    )
    [issue] = _coded(_check(broken), "image-ratio-after-break")
    assert (
        "give the pictureless item an empty picture, `![Name]()`" in issue["message"]
    ), issue
    kept = broken.replace(";;;\n:::1\n**B**", ";;;\n![B]()\n:::1\n**B**")
    issues = _check(kept)
    assert not _coded(issues, "image-ratio-after-break"), issues
    assert not _coded(issues, "image-ratio"), issues
    assert not [i for i in issues if "![B]()" in i["message"]], issues
    # With no ratio at all, the three are one run, named once.
    plain = kept.replace(ratio, "")
    [run] = _coded(_check(plain), "image-ratio")
    assert run["message"].startswith("3 pictures in the repeated run"), run
    print("  ✓  check: `![Name]()` is offered as a fix and keeps its run")


def test_task_boxes_no_button_commits_are_a_note():
    """Plain boxes with no commit button: every tick reaches the agent alone and
    the window waits on each answer. A commit button, or boxes linked to their own
    action, are the author's choice and pass in silence."""
    boxes = "## Packing\n\n- [ ] Passport\n- [x] Charger\n- [ ] Tickets\n"
    [issue] = _coded(_check(boxes), "boxes-without-commit")
    assert issue["level"] == "note" and issue["x"] == 0, issue
    assert "The 3 task boxes from target 0" in issue["message"], issue
    assert "`[Save](agent:save?md2ui.commit=1)`" in issue["message"], issue
    committed = boxes + "\n[Save](agent:save?md2ui.commit=1)\n"
    assert not _coded(_check(committed), "boxes-without-commit")
    linked = "## Packing\n\n- [[ ]](agent:pack?item=1) Passport\n"
    assert not _coded(_check(linked), "boxes-without-commit")
    # A box beside its label is a toggle: a tick there is an action.
    toggles = "## Settings\n\nWi-Fi ... [x]\n\nNotifications ... [ ]\n"
    assert not _coded(_check(toggles), "boxes-without-commit")
    print("  ✓  check: task boxes no button commits are a note; toggles are not")


def test_a_link_param_nothing_reads_is_named():
    """A link's ``md2ui.*`` params are split off every destination, so one that
    nothing reads is lost without a trace: named, as an image's are. ``commit``
    on an ``agent:`` link is read, and silent."""
    https = _coded(
        _check("[Docs](https://example.com/d?md2ui.commit=1&q=a)\n"), "link-param"
    )
    assert len(https) == 1 and "'md2ui.commit'" in https[0]["message"], https
    agent = _coded(_check("[Newest](agent:sort?md2ui.menu=1)\n"), "link-param")
    assert len(agent) == 1 and "'md2ui.menu'" in agent[0]["message"], agent
    assert not _coded(_check("[Keep](agent:keep?md2ui.commit=1)\n"), "link-param")
    print("  ✓  check: a link param nothing reads is named; agent: commit is not")


TESTS = [
    test_a_link_param_nothing_reads_is_named,
    test_task_boxes_no_button_commits_are_a_note,
    test_an_empty_picture_keeps_its_run,
    test_a_picture_after_a_pictureless_row_is_named,
    test_a_styled_name_cut_at_its_dash_is_a_note,
    test_one_offer_shown_twice_is_a_note,
    test_a_long_main_button_is_a_note,
    test_a_run_of_cards_only_partly_tappable_is_a_note,
    test_a_split_heading_carries_both_replacements,
    test_a_drawn_backslash_carries_its_replacement,
    test_an_escaped_dot_is_a_drawn_backslash,
    test_an_issue_without_a_mechanical_fix_keeps_its_message_alone,
    test_the_ratio_warning_counts_runs_as_the_render_polls_them,
]

if __name__ == "__main__":
    print("Check Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    sys.exit(1 if failed else 0)
