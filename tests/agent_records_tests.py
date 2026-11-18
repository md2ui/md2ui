"""
Unit tests for the server's records of the pages it sent: ``wire_sections`` and
``wire_records``.

Pinned here:

  * a section is named by its ``{#id}``, else by the heading's words, read as
    the grouper reads a heading and never inside a fence;
  * the comment under a heading gives its ``from:`` and its ``fresh:``, in any
    order, and a heading without one has neither;
  * a page is a message and everything that carried it on: any id it had names
    its latest message, and ``listing`` shows it once;
  * a section's time is inherited by whatever carries the page on, and only a
    renewal resets it, so re-sending a page never makes old data fresh;
  * ``stale`` names only sections past their own ``fresh:``;
  * ``MessageLog.record`` carries a page across a replacement and a re-send;
  * a heading of markers that never close is named in linear time;
  * a patch adds whole sections after or before a named one, past its ``***``,
    or removes one, and refuses with the call to make instead.

Run with: uv run python tests/agent_records_tests.py
"""

import time

from md2ui import session
from md2ui.mcp_demo_records import freshness
from md2ui.pipeline.grouper_feed_slots import feed_slots, with_value
from md2ui.wire import MessageLog
from md2ui.wire_frames import FrameError
from md2ui.wire_patch import (
    insert_section_markdown,
    patch_page,
    patch_section_markdown,
    patch_target_markdown,
    replace_text_markdown,
)
from md2ui.wire_records import Pages
from md2ui.wire_sections import sections, title

HOME = """# Home {#home}

## 🧩 md2ui repo
<!-- from: git status; fresh: 5m -->
3 files changed

## 📅 [Calendar](agent:open) **today**
<!-- fresh: 1h; from: calendar.list_events -->
Standup at 10

```md
## Not a heading
```

## {#tools-1}
Tiles that never change.
"""


BANDS = """![hero](https://example.com/a.png)
# Home {#home}

## Repo {#repo}
body
### Sub
sub body
***
still the repo's
***
lifted out of the repo

## Songs
[🤍](agent:like?id=3) Song A
[🤍](agent:like?id=4) Song B
"""

_KIT = None


def _kit():
    global _KIT
    if _KIT is None:
        _KIT = session.load_grouping_kit()
    return _KIT


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_sections_are_named_as_written():
    found = sections(HOME)
    assert [s.name for s in found] == [
        "home",
        "🧩 md2ui repo",
        "📅 Calendar today",
        "tools-1",
    ], found
    assert [s.title for s in found][-1] == "", found
    repo, calendar = found[1], found[2]
    assert (repo.source, repo.fresh_s) == ("git status", 300.0), repo
    assert (calendar.source, calendar.fresh_s) == ("calendar.list_events", 3600.0)
    assert found[0].source is None and found[3].fresh_s is None, found
    assert title(HOME) == "Home" and title("Just a line\n\nmore") == "Just a line"
    print("  ✓  a section is named by its {#id}, else its words; fences hide headings")


def test_a_page_keeps_its_ids_and_its_clocks():
    clock = _Clock()
    pages = Pages(clock)
    pages.sent("c1", HOME)
    clock.now += 400  # past the repo's 5 minutes, inside the calendar's hour
    assert pages.stale("c1") == ["🧩 md2ui repo"], pages.stale("c1")
    pages.sent("c2", "# Detail\n")
    pages.sent("c3", HOME, carries="c1")  # re-sent: the data is as old as it was
    assert pages.stale("c3") == ["🧩 md2ui repo"], pages.stale("c3")
    assert (pages.age("c3"), pages.data_age("c3")) == (0, 400), "the data is older"
    pages.sent("c4", HOME, carries="c3", renewed=["🧩 md2ui repo"])  # a patch
    assert pages.stale("c4") == [], pages.stale("c4")
    clock.now += 3300  # the calendar's hour passes; the repo is 55 minutes on
    assert pages.stale("c4") == ["🧩 md2ui repo", "📅 Calendar today"]
    for old in ("c1", "c3", "c4"):
        assert pages.latest(old) == "c4", old
    assert pages.latest("c2") == "c2" and pages.latest("nope") == "nope"
    rows = pages.listing()
    assert [r["message_id"] for r in rows] == ["c4", "c2"], rows
    assert rows[0]["title"] == "Home" and rows[0]["sources"] == {
        "🧩 md2ui repo": "git status",
        "📅 Calendar today": "calendar.list_events",
    }, rows[0]
    assert "stale" in rows[0] and "stale" not in rows[1] and "sources" not in rows[1]
    print("  ✓  any id names the latest page; a re-send keeps old data old")


def test_the_log_carries_a_page_across_a_replacement_and_a_resend():
    log = MessageLog(None)
    log.record("c1", "# Tasks\n\n- [ ] One\n")
    log.mark("c1", 0, "checked", "c2")
    log.record("c3", log.markdown("c2"), continues="c2")
    assert log.pages.latest("c1") == "c3", log.pages.latest("c1")
    assert [r["message_id"] for r in log.pages.listing()] == ["c3"]
    assert freshness(log, "c3") == {"data_age_s": 0}, "no fresh:, no stale"
    print("  ✓  a mark and a re-send carry one page on, listed once")


def test_a_section_ends_where_the_grouper_ends_it():
    """The lines a patch replaces are the lines the grouper puts in the section:
    a run glued above the heading is its, a `***` closes the innermost section,
    and the next heading of its level or above ends it."""
    lines = BANDS.split("\n")
    spans = {
        s.name: ("\n".join(lines[s.start : s.end]).strip(), s.closed)
        for s in sections(BANDS)
    }
    assert spans["home"][0].startswith("![hero]"), spans["home"]
    assert spans["Sub"] == ("### Sub\nsub body\n***", True), spans["Sub"]
    repo, closed = spans["repo"]
    assert closed and repo.endswith("still the repo's\n***"), repo
    assert spans["Songs"][0].endswith("Song B") and not spans["Songs"][1]
    print("  ✓  a section ends where the grouper ends it: peel, *** and level")


def test_a_patch_changes_one_section_and_nothing_else():
    kit = _kit()
    body, renewed = patch_section_markdown(BANDS, "repo", "new body", kit)
    assert "## Repo {#repo}\nnew body\n***\nlifted out" in body, body
    assert renewed == ["repo"], renewed
    card = "# Home\n\n## Repo\n### main\nold\n\n***\n\n## Also connected\ntiles\n"
    kept, _renewed = patch_section_markdown(card, "Repo", "new", kit)
    assert kept == card.replace("### main\nold", "new"), "the body's *** stays"
    closed, _renewed = patch_section_markdown(BANDS, "repo", "new body\n***", kit)
    assert closed == body, "a closer it writes itself takes the page's place"
    whole, renewed = patch_section_markdown(
        BANDS, "#repo", "## Repo {#repo}\nfresh\n### Sub\nnew sub", kit
    )
    assert "lifted out of the repo" in whole and renewed == ["repo", "Sub", "repo"]
    for name, replacement in (
        ("repo", "## Repo\nx\n## Two\ny"),  # a second section
        ("repo", "body\n***\n***"),  # one closer too many: Home closes too
        ("Songs", "# Top\nz"),  # a heading above its level
        ("missing", "x"),
    ):
        try:
            patch_section_markdown(BANDS, name, replacement, kit)
        except FrameError:
            continue
        raise AssertionError(f"{name!r} <- {replacement!r} must be refused")
    print("  ✓  a patch replaces one section, body or whole; more is refused")


def test_a_patch_changes_one_link_by_its_ordinal():
    kit = _kit()
    liked = patch_target_markdown(BANDS, 1, "[❤️](agent:unlike?id=4)", kit)
    assert "[🤍](agent:like?id=3) Song A" in liked, liked
    assert "[❤️](agent:unlike?id=4) Song B" in liked, liked
    for x, replacement in (
        (1, "liked"),
        (1, "[a](agent:a)\n[b](agent:b)"),
        (9, "[a](/a)"),
    ):
        try:
            patch_target_markdown(BANDS, x, replacement, kit)
        except FrameError:
            continue
        raise AssertionError(f"{x} <- {replacement!r} must be refused")
    print("  ✓  a patch replaces one link by x, and it must stay one target")


def test_each_target_knows_its_section():
    kit = _kit()
    log = MessageLog(kit)
    log.record("c1", BANDS)
    assert log.pages.clicked("c1", 0)["section"] == "Songs", log.pages.clicked("c1", 0)
    nested = "# Home\n[Top](agent:top)\n\n## Card {#card}\n[In](agent:in)\n"
    log.record("c2", nested)
    assert [log.pages.clicked("c2", x).get("section") for x in (0, 1)] == [
        "Home",
        "card",
    ]
    clock = _Clock()
    log.pages = Pages(clock)
    log.record("c4", nested)
    clock.now += 30
    renewed = log.markdown("c4").replace("[In]", "[Out]")
    log.record("c5", renewed, continues="c4", renewed=["card"])  # as a patch does
    clicked = log.pages.clicked("c5", 1)
    assert (clicked["section_age_s"], clicked["data_age_s"]) == (0, 30), clicked
    assert log.pages.clicked("c5", 0)["section_age_s"] == 30, "Home's data is older"
    log.record("c3", "[Alone](agent:alone)\n\nNo heading here.\n")
    assert "section" not in log.pages.clicked("c3", 0), "outside every section"
    print("  ✓  each target knows the innermost section it sits in, by its name")


SHIP = "# Ship\n\n## Build\nmake\n\n## Tests\nmake check\n\n## Deploy\npush it\n"


def test_a_patch_adds_sections_after_or_before_one():
    kit = _kit()
    end, renewed = insert_section_markdown(
        SHIP, "Deploy", "after", "## Monitoring {#monitoring}\ndashboards", kit
    )
    assert end == SHIP + "\n## Monitoring {#monitoring}\ndashboards\n", end
    assert renewed == ["monitoring"], renewed
    top, renewed = insert_section_markdown(SHIP, "Build", "before", "## Sum\nok", kit)
    assert top == SHIP.replace("## Build", "## Sum\nok\n\n## Build"), top
    assert renewed == ["Sum"], renewed
    two, renewed = insert_section_markdown(
        SHIP, "Tests", "after", "## A\na\n\n## B\nb\n### B1\nb1", kit
    )
    assert "make check\n\n## A\na\n\n## B\nb\n### B1\nb1\n\n## Deploy" in two
    assert renewed == ["A", "B", "B1"], renewed
    closed, renewed = insert_section_markdown(BANDS, "repo", "after", "## N\nn", kit)
    assert "still the repo's\n***\n\n## N\nn\n***\n\nlifted out" in closed, closed
    assert renewed == ["N"], "closed as the repo is, so Home keeps its words"
    print("  ✓  a patch adds whole sections after or before one, past its ***")


def test_an_addition_is_refused_with_the_call_to_make():
    kit = _kit()
    for page, anchor, block, says in (
        (SHIP, "Deploy", "just text", "start the block with a level-2 heading"),
        (SHIP, "Deploy", "### Deeper\nd", "patch(section='Deploy'"),
        (SHIP, "Deploy", "## A\na\n# Higher\nh", "a level-1 heading"),
        (BANDS, "Songs", "## Again {#repo}\nr", "patch(section='repo'"),
        (SHIP, "Nope", "## A\na", "sections: 'Ship', 'Build'"),
        ("No heading here.\n", "x", "## A\na", "`show`"),
        (SHIP, "Deploy", "", 'markdown=""'),
    ):
        try:
            insert_section_markdown(page, anchor, "after", block, kit)
        except FrameError as exc:
            assert says in str(exc), (block, str(exc))
            continue
        raise AssertionError(f"{anchor!r} <- {block!r} must be refused")
    print("  ✓  an addition that is not whole sections is refused, saying what to do")


def test_an_empty_patch_removes_the_section():
    kit = _kit()
    gone, renewed = patch_section_markdown(SHIP, "Tests", "", kit)
    assert gone == "# Ship\n\n## Build\nmake\n\n## Deploy\npush it\n", gone
    assert renewed == [], renewed
    last, _renewed = patch_section_markdown(SHIP, "Deploy", "", kit)
    assert last == "# Ship\n\n## Build\nmake\n\n## Tests\nmake check\n", last
    closed, _renewed = patch_section_markdown(BANDS, "repo", "", kit)
    assert "# Home {#home}\n\nlifted out of the repo\n\n## Songs" in closed, closed
    try:
        patch_section_markdown("# Only\nx\n", "Only", "", kit)
    except FrameError as exc:
        assert "empty" in str(exc), str(exc)
    else:
        raise AssertionError("removing the whole page must be refused")
    print("  ✓  an empty patch removes a section, its heading and its closer")


def test_offers_after_an_added_section_renumber():
    log = MessageLog(_kit())
    log.record("c1", BANDS)
    before = [t.action.action for t in log.targets("c1") if t.action]
    mid, edited, renewed = patch_page(
        log, "c1", "## New {#new}\n[Go](agent:go)", "repo", None, "before"
    )
    log.record("c2", edited, mid, continues=mid, renewed=renewed)
    after = [t.action.action for t in log.targets("c2") if t.action]
    assert after == ["go", *before], (before, after)
    assert log.pages.clicked("c2", 0)["section"] == "new", log.pages.clicked("c2", 0)
    print("  ✓  the offers after an added section move up by its own")


_COVERS = "## Your mixes\n\n" + "\n\n".join(
    f"### \n![Mix {i}](https://i.scdn.co/image/ab{i}.jpg)\n**Mix {i}**\n_Playlist_"
    for i in range(4)
)


def _refused(edits: list[tuple[str, str]]) -> str:
    try:
        replace_text_markdown(_COVERS, edits, _kit())
    except FrameError as exc:
        return str(exc)
    raise AssertionError(f"{edits} was not refused")


def test_replace_edits_exact_text_where_a_section_cannot_be_named():
    """The Spotify page: eight cards under empty `### ` headings, so no `section` or
    `x` reaches a cover. One exact-text replace adds the run's ratio to the first
    picture; nothing else changes (ADR-611)."""
    old, new = "ab0.jpg)", "ab0.jpg?md2ui.aspect_ratio=1:1)"
    edited, renewed = replace_text_markdown(_COVERS, [(old, new)], _kit())
    assert edited == _COVERS.replace(old, new)
    assert len(renewed) == 1, renewed  # the first card's clock restarts
    both, renewed = replace_text_markdown(
        _COVERS, [("ab0.jpg)", "a.jpg)"), ("**Mix 3**", "**Deep Focus**")], _kit()
    )
    assert "a.jpg)" in both and "**Deep Focus**" in both and len(renewed) == 2
    log = MessageLog(_kit())
    log.record("c1", _COVERS)
    mid, page, _ = patch_page(log, "c1", "", None, None, replace=[(old, new)])
    assert (mid, page) == ("c1", _COVERS.replace(old, new)), "through the server's copy"
    print("  ✓  replace edits exact text, several at once, where no section is named")


def test_replace_refuses_what_it_cannot_place_safely():
    assert "is not on the page" in _refused([("ab9.jpg", "x")])
    assert "4 times" in _refused([("_Playlist_", "_Mix_")])
    assert "one line" in _refused([("**Mix 1**", "**Mix 1**\n\n## More")])
    assert "overlap" in _refused([("ab1.jpg", "x"), ("1.jpg)", "y")])
    assert "heading" in _refused([("**Mix 2**", "## Mix 2")])
    # All or none: one bad edit refuses the good one with it.
    assert "is not on the page" in _refused([("ab0.jpg)", "a.jpg)"), ("nope", "x")])
    print(
        "  ✓  replace refuses a missing, repeated, multi-line, overlapping or heading edit"
    )


def test_a_replace_quoting_a_fed_slot_names_the_slot():
    """t3b: after a feed, the page holds the fed value, so a
    replace quoting the value the agent wrote is not on it. The refusal names the
    slot and quotes it as the page holds it."""
    authored = "# Board\n\n_last update [16:48:00 UTC](feed:updated)_\n"
    (slot,) = feed_slots(authored)
    fed = with_value(authored, slot, "16:29:42 UTC")
    try:
        replace_text_markdown(fed, [("[16:48:00 UTC](feed:updated)", "x")], _kit())
    except FrameError as exc:
        why = str(exc)
    else:
        raise AssertionError("a stale slot quote was not refused")
    assert why.startswith("bad_target") and "slot 'updated'" in why, why
    assert "[16:29:42 UTC](feed:updated)" in why, why
    print("  ✓  a replace quoting a fed slot's old value names the slot")


def test_a_heading_of_unclosed_markers_reads_in_linear_time():
    """A page's heading is read for its name on every send: one long line of
    markers that never close must not stall the conversation's lock. Marked
    runs are bounded, so it reads at once; ordinary markers still drop from the
    name. The time limit leaves room for a loaded machine."""
    flood = "*a _b " * 8000
    started = time.perf_counter()
    named = [s.name for s in sections(f"# {flood}\n\nBody\n")] + [title(flood)]
    took = time.perf_counter() - started
    assert took < 5.0, f"{took:.1f} s for a 48 KB heading"
    assert named[0].startswith("a _b"), named[0][:20]
    assert title("# **Bold** and _it_ and `code`\n") == "Bold and it and code"
    print(f"  ✓  a 48 KB heading of unclosed markers reads in {took:.2f} s")


TESTS = [
    test_replace_edits_exact_text_where_a_section_cannot_be_named,
    test_replace_refuses_what_it_cannot_place_safely,
    test_a_replace_quoting_a_fed_slot_names_the_slot,
    test_sections_are_named_as_written,
    test_a_page_keeps_its_ids_and_its_clocks,
    test_the_log_carries_a_page_across_a_replacement_and_a_resend,
    test_a_section_ends_where_the_grouper_ends_it,
    test_a_patch_changes_one_section_and_nothing_else,
    test_a_patch_changes_one_link_by_its_ordinal,
    test_each_target_knows_its_section,
    test_a_patch_adds_sections_after_or_before_one,
    test_an_addition_is_refused_with_the_call_to_make,
    test_an_empty_patch_removes_the_section,
    test_offers_after_an_added_section_renumber,
    test_a_heading_of_unclosed_markers_reads_in_linear_time,
]

if __name__ == "__main__":
    print("Agent Records Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
