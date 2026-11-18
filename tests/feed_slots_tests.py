"""
Unit tests for feed slots (Phase 2.5 of the agent-turns roadmap): the places on a
page an author names for a feed to write words into.

Pinned here:

  * a text slot ``[3:53 PM](feed:arrives)`` and a chip slot
    `` [`Preparing`](feed:status) `` group exactly as their words written without
    the link, so every tier the author put around one holds: a key line's value,
    a stat's value (stacked and in a colon column), bold, caption, struck, hero,
    a sentence's words, and a chip alone, in a colon column and across a spring;
  * a slot is never a link and never a target, so the targets after it keep the
    ordinals they have without it; a label slot (``md2ui.feed`` on an ``agent:``
    button) stays the button it is;
  * the grouper annotates the node that draws each slot with the range of its
    words in ``content`` (ADR-100), and ``slots_in_tree`` says whether those words
    are styled;
  * ``feed_slots`` finds every slot outside code and comments with the exact span
    of its words, and ``with_value`` writes a value there: the substituted page
    groups as its plain twin does, tier and all;
  * a slot is a value, not prose: ``reads_like_prose`` is
    True past ``MAX_SLOT_WORDS`` words or at sentence punctuation, and ``check``
    warns of a slot that reads so;
  * ``check`` reads ``md2ui.feed`` on an ``agent:`` link, and refuses a repeated,
    empty, misnamed, divided, nested or unplaced slot and a fed label on any other
    link or a choice option; it warns of markup inside a slot's brackets and notes
    a slot that draws a bar.

Run with: uv run python tests/feed_slots_tests.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from grouper_snapshot import _runs  # noqa: E402

from md2ui import check_feeds, session  # noqa: E402
from md2ui.check import check_markdown  # noqa: E402
from md2ui.pipeline.render_actions import action_targets  # noqa: E402

_KIT = None

# Each spelling with a slot, and the same line with only its words.
TIERS = {
    "key line": ("Arrives: [3:53 PM](feed:arrives)", "Arrives: 3:53 PM"),
    "stat": (
        "_Arrives_\n___[3:53 PM](feed:arrives)___",
        "_Arrives_\n___3:53 PM___",
    ),
    "colon stat": (
        "_Arrives_ : ___[3:53 PM](feed:arrives)___",
        "_Arrives_ : ___3:53 PM___",
    ),
    "bold": ("**[Ready soon](feed:a)**", "**Ready soon**"),
    "caption": ("_[Ready soon](feed:a)_", "_Ready soon_"),
    "struck": ("~~[Ready soon](feed:a)~~", "~~Ready soon~~"),
    "hero": ("___[3:53 PM](feed:a)___", "___3:53 PM___"),
    "sentence": (
        "Your order arrives at **[3:53 PM](feed:arrives)** today.",
        "Your order arrives at **3:53 PM** today.",
    ),
    "chip": ("[`Preparing`](feed:status)", "`Preparing`"),
    "chip key": ("Status: [`Preparing`](feed:status)", "Status: `Preparing`"),
    "chip colon": (
        "[`Preparing`](feed:status) : _Status_",
        "`Preparing` : _Status_",
    ),
    "chip spring": (
        "Order BS-1043 ... [`Preparing`](feed:status)",
        "Order BS-1043 ... `Preparing`",
    ),
}

ORDER = (
    "## Order BS-1043\n\n"
    "Status: [`Preparing`](feed:status)\n\n"
    "_Arrives_\n___[3:53 PM](feed:arrives)___\n\n"
    "Your courier is **[Sam](feed:courier)** today.\n\n"
    "[Track · Preparing](agent:track?id=BS-1043&md2ui.feed=track) | "
    "[Cancel](agent:cancel?id=BS-1043)\n"
)


def _kit():
    global _KIT
    if _KIT is None:
        _KIT = session.load_grouping_kit()
    return _KIT


def _tree(markdown: str) -> dict:
    ast = session.group_markdown(markdown, _kit())
    assert ast is not None
    return ast.to_dict()


def _bare(node: dict) -> dict:
    """*node* without its slot annotations: what the plain twin groups to."""
    node.pop("feed_slots", None)
    for child in node.get("children", []):
        _bare(child)
    return node


def _same_as_plain(slotted: str, plain: str) -> bool:
    a = session.group_markdown(slotted, _kit())
    b = session.group_markdown(plain, _kit())
    assert a is not None and b is not None
    same_tree = json.dumps(_bare(a.to_dict()), sort_keys=True) == json.dumps(
        b.to_dict(), sort_keys=True
    )
    return same_tree and _runs(a) == _runs(b)


def _codes(markdown: str) -> list[str]:
    return [issue["code"] for issue in check_markdown(markdown, _kit())]


def test_a_slot_groups_as_its_words():
    for name, (slotted, plain) in TIERS.items():
        doc = "## Order\n\n{}\n"
        assert _same_as_plain(doc.format(slotted), doc.format(plain)), name


def test_a_slot_is_no_target():
    targets = action_targets(_tree(ORDER))
    assert [t.action and t.action.label for t in targets] == [
        "Track · Preparing",
        "Cancel",
    ], targets
    assert all((t.action.href or "")[:5] != "feed:" for t in targets if t.action)


def test_the_node_drawing_a_slot_carries_its_words():
    from md2ui.pipeline.grouper_feed_slots import feed_slots, slots_in_tree

    tree = _tree(ORDER)
    nodes: dict[str, dict] = {}

    def index(nd: dict) -> None:
        nodes[nd["node_id"]] = nd
        for child in nd.get("children", []):
            index(child)

    index(tree)
    placed = slots_in_tree(tree)
    assert [(s["name"], s["kind"]) for _, s in placed] == [
        ("status", "chip"),
        ("arrives", "text"),
        ("courier", "text"),
        ("track", "label"),
    ], placed
    words = [nodes[nid]["content"][s["start"] : s["end"]] for nid, s in placed]
    assert words == [s.value for s in feed_slots(ORDER)], words
    assert words == ["Preparing", "3:53 PM", "Sam", "Track · Preparing"], words
    assert not any(s["styled"] for _, s in placed)


def test_feed_slots_names_the_span_of_each_slots_words():
    from md2ui.pipeline.grouper_feed_slots import feed_slots, with_value

    slots = feed_slots(ORDER)
    assert [(s.name, s.kind, s.value) for s in slots] == [
        ("status", "chip", "Preparing"),
        ("arrives", "text", "3:53 PM"),
        ("courier", "text", "Sam"),
        ("track", "label", "Track · Preparing"),
    ], slots
    assert all(ORDER[s.start : s.end] == s.value for s in slots)
    chip = with_value(ORDER, slots[0], "On the way")
    assert "Status: [`On the way`](feed:status)" in chip
    label = with_value(ORDER, slots[3], "Track · On the way")
    assert "[Track · On the way](agent:track?id=BS-1043&md2ui.feed=track)" in label
    # Code, comments and escapes hold no slot; the scheme is case-insensitive.
    quiet = (
        "`[a](feed:a)` \\[b](feed:b) <!-- [c](feed:c) -->\n\n"
        "```\n[d](feed:d)\n```\n\n[E](FEED:e)\n"
    )
    assert [s.name for s in feed_slots(quiet)] == ["e"], feed_slots(quiet)
    nested = feed_slots("[Track · [Preparing](feed:s)](agent:t)")
    assert [(s.name, s.nested) for s in nested] == [("s", True)], nested


def test_a_substituted_value_keeps_its_tier():
    from md2ui.pipeline.grouper_feed_slots import feed_slots, with_value

    doc = "## Order\n\n{}\n"
    for name, (slotted, plain) in TIERS.items():
        page = doc.format(slotted)
        (slot,) = feed_slots(page)
        value = "On the way" if slot.kind == "chip" else "3:58 PM"
        posted = with_value(page, slot, value)
        twin = doc.format(plain.replace(slot.value, value))
        assert _same_as_plain(posted, twin), name


def test_a_styled_post_is_seen_in_the_tree():
    from md2ui.pipeline.grouper_feed_slots import feed_slots, slots_in_tree, with_value

    for page in (
        "## A\n\nArrives: [3:53 PM](feed:a)\n",
        "## A\n\n___[3:53 PM](feed:a)___\n",
        "## A\n\nStatus: [`Preparing`](feed:a)\n",
    ):
        (slot,) = feed_slots(page)
        [(_, plain)] = slots_in_tree(_tree(page))
        assert not plain["styled"], page
        for value in ("**soon**", "_soon_", "~~soon~~", "`so`on`", "[s](/x)"):
            placed = slots_in_tree(_tree(with_value(page, slot, value)))
            assert all(s["styled"] for _, s in placed), (page, value, placed)
    # A whole code span posted into a text slot is a chip slot's spelling: the
    # kind it is read back as tells it apart.
    page = "## A\n\nArrives: [3:53 PM](feed:a)\n"
    (slot,) = feed_slots(page)
    [(_, posted)] = slots_in_tree(_tree(with_value(page, slot, "`soon`")))
    assert posted["kind"] == "chip" != slot.kind, posted
    # A chip's words are its code span's inside: a backtick there is styled.
    page = "## A\n\n[`Preparing`](feed:a)\n"
    (slot,) = feed_slots(page)
    placed = slots_in_tree(_tree(with_value(page, slot, "a`b")))
    assert all(s["styled"] for _, s in placed), placed


def test_check_reads_and_refuses_slots():
    assert _codes(ORDER) == [], check_markdown(ORDER, _kit())
    assert list(check_feeds.problems(ORDER, _tree(ORDER))) == []
    cases = {
        "## A\n\nArrives: [3:53 PM](feed:a)\n\nAt [3:53 PM](feed:a) today.\n": (
            "feed-repeated"
        ),
        "## A\n\nArrives: [](feed:a)\n": "feed-empty",
        "## A\n\nArrives: [3:53 PM](feed:a?x=1)\n": "feed-name",
        "## A\n\n[Open · x](https://e.com?md2ui.feed=o)\n": "feed-not-agent",
        "## A\n\n[S](agent:size?md2ui.choice=size&md2ui.feed=s) | "
        "*[L](agent:size?md2ui.choice=size)*\n": "feed-not-agent",
        "## A\n\n[Track · [Preparing](feed:s)](agent:t)\n": "feed-nested",
        "## A\n\nArrives: [soon | late](feed:a)\n": "feed-divided",
        "## A\n\n![a [x](feed:b)](https://e.com/i.png)\n\nText.\n": "feed-unplaced",
        "## A\n\nArrives: [**3:53 PM**](feed:a)\n": "feed-styled",
        "## A\n\nElapsed: [45%](feed:e)\n": "feed-bar",
        "## A\n\nStep: [3/10](feed:step)\n": "feed-bar",
        "## A\n\nProgress: 40%\n\nStatus: [Preparing](feed:progress)\n": "feed-key",
        "## A\n\nProgress: 40%\n\n[Track · x](agent:t?md2ui.feed=Progress)\n": (
            "feed-key"
        ),
        "## A\n\n[Your order is arriving around 7:58 PM](feed:a)\n": "feed-prose",
        "## A\n\nStatus: [Arriving soon.](feed:a)\n": "feed-prose",
    }
    for page, code in cases.items():
        assert code in _codes(page), (page, check_markdown(page, _kit()))
    # A fed label on an `agent:` button, alone or inside a sentence, is read.
    for page in (
        "## A\n\n[Track · x](agent:track?md2ui.feed=t)\n",
        "## A\n\nTap [Track · x](agent:track?md2ui.feed=t) to follow.\n",
    ):
        codes = _codes(page)
        assert "link-param" not in codes and not any(
            c.startswith("feed-") for c in codes
        ), (page, codes)


def test_a_slot_a_bar_draws_is_an_error_naming_the_fix():
    """A bar is fed by its key, so a slot it draws can never take a post: an
    error that says to write the bar unmarked and feed it by its key."""
    page = "## A\n\nElapsed: [45%](feed:elapsed)\n"
    issue = next(i for i in check_markdown(page, _kit()) if i["code"] == "feed-bar")
    assert issue["level"] == "error", issue
    assert "`Elapsed: 45%`" in issue["message"], issue
    assert 'keys=["Elapsed"]' in issue["message"], issue
    assert "feed-key" not in _codes(page), "one verdict per slot"
    print("  ✓  a slot a bar draws is an error that names the key to feed")


def test_a_slot_is_a_value_not_prose():
    from md2ui.pipeline.grouper_feed_slots import MAX_SLOT_WORDS, reads_like_prose

    assert MAX_SLOT_WORDS == 4
    from md2ui.pipeline.grouper_feed_slots import slot_words

    assert slot_words("Track · On the way") == 4
    assert slot_words("a - b — c | d") == 4
    for value in (
        "3:53 PM",
        "On the way",
        "Track · Preparing",
        "Track · On the way",
        "one two three four",
    ):
        assert not reads_like_prose(value), value
    for value in (
        "one two three four five",
        "Track · on the way now",
        "Done.",
        "Wait!",
        "Ready?",
        "Soon…",
    ):
        assert reads_like_prose(value), value
    sentence = "## A\n\n[Your order is arriving around 7:58 PM](feed:a)\n"
    assert "feed-prose" in _codes(sentence), check_markdown(sentence, _kit())
    marked = "## A\n\nYour order is arriving around [7:58 PM](feed:a)\n"
    assert "feed-prose" not in _codes(marked), check_markdown(marked, _kit())


def test_a_page_without_slots_is_left_as_written():
    from md2ui.pipeline.grouper_feed_slots import respell

    text = "## A\n\n[Go](/g) and `[x](feed:a)`\n"
    assert respell(text)[0] is text
    assert respell("## A\n\nplain\n")[0] == "## A\n\nplain\n"


TESTS = [
    test_a_slot_groups_as_its_words,
    test_a_slot_is_no_target,
    test_the_node_drawing_a_slot_carries_its_words,
    test_feed_slots_names_the_span_of_each_slots_words,
    test_a_substituted_value_keeps_its_tier,
    test_a_styled_post_is_seen_in_the_tree,
    test_check_reads_and_refuses_slots,
    test_a_slot_a_bar_draws_is_an_error_naming_the_fix,
    test_a_slot_is_a_value_not_prose,
    test_a_page_without_slots_is_left_as_written,
]


if __name__ == "__main__":
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ok    {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL  {test.__name__}: {type(exc).__name__}: {exc}"[:600])
    sys.exit(1 if failed else 0)
