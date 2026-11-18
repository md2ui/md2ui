"""A feed's slots: text its author marked, moved by name (ADR-608).

A feed moves short text as well as figures, through ``wire_texts``:

  * a slot is authored, never detected (``grouper_feed_slots`` finds it): ``[3:53 PM](feed:arrives)``, a chip
    `` [`Preparing`](feed:status) ``, a button's label with ``md2ui.feed=track``;
    a name no slot carries, or more than one, is refused naming the page's slots
    and how to mark one;
  * a value is refused before anything is regrouped by cheap rules: a character
    of category Cc, Cf, Zl, Zp, Co or Cn (U+200D only inside an emoji
    sequence; U+FE0F is a mark, not a format), over 40 characters, over
    ``MAX_SLOT_WORDS`` words (a value, not prose), a word over ``MAX_WORD``;
  * then by its fingerprint: written at the slot's own offsets, the page is
    regrouped, and the edit is kept only when that slot alone changed (every other
    node, run and target, a label's action, params and ordinal) and it reads back
    as posted in one plain run: a styled value is refused from the grouper's
    annotation, a value that divides, links or draws a bar by the regroup;
  * a feed's values go in as one edit, a figure into its bar and a text into
    its slot.

Run with: uv run python tests/wire_texts_tests.py
"""

import contextlib
import io

from md2ui import session
from md2ui.pipeline.grouper_feed_slots import MAX_SLOT_WORDS
from md2ui.pipeline.render_actions import action_targets
from md2ui.wire import FrameError
from md2ui.wire_texts import (
    MAX_WORD,
    check_text,
    page_slots,
    set_fed_markdown,
    set_slot_markdown,
)

LABEL = "[Track · Received](agent:track?id=BS-1043&md2ui.feed=track)"
PAGE = (
    "# Order BS-1043\n\n"
    "_Arrives_\n___[3:53 PM](feed:arrives)___\n\n"
    "[`Received`](feed:status) : _Status_\n\n"
    "Due: [3:53 PM](feed:due)\n\n"
    f"[Help](agent:help) {LABEL}\n\n"
    "Elapsed: 0%\n"
)

_MODELS = None


def _kit():
    global _MODELS
    if _MODELS is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _MODELS = session.load_grouping_kit()
    return _MODELS


def _refused(edit, code: str = "bad_value") -> str:
    try:
        edit()
    except FrameError as exc:
        assert exc.code == code, exc
        return str(exc)
    raise AssertionError("not refused")


def test_a_slot_is_authored_and_named():
    found = {n: [(s.kind, s.value) for s in v] for n, v in page_slots(PAGE).items()}
    assert found == {
        "arrives": [("text", "3:53 PM")],
        "status": [("chip", "Received")],
        "due": [("text", "3:53 PM")],
        "track": [("label", "Track · Received")],
    }, found
    for name in ("Arrives", "Elapsed", "nope"):
        why = _refused(
            lambda n=name: set_slot_markdown(PAGE, n, "x", _kit()), "bad_target"
        )
        assert "names no slot; slots here: arrives, status, due, track" in why, why
        assert "[3:53 PM](feed:arrives)" in why, "the refusal says how to mark one"
    twice = PAGE + "\n[1](feed:due)\n"
    why = _refused(lambda: set_slot_markdown(twice, "due", "x", _kit()), "bad_target")
    assert "names more than one slot" in why, why
    print("  ✓  a slot is the author's, by name; an unknown name says how to mark one")


def test_a_slot_edit_moves_only_its_value():
    kit = _kit()
    for name, value, line in (
        ("arrives", "3:58 PM", "___[3:58 PM](feed:arrives)___"),
        ("arrives", "Soon", "___[Soon](feed:arrives)___"),
        ("status", "On the way", "[`On the way`](feed:status) : _Status_"),
        ("due", "Soon", "Due: [Soon](feed:due)"),
        ("track", "Track · On the way", f"[Help](agent:help) {LABEL}".replace(
            "Received", "On the way")),
    ):  # fmt: skip
        edited = set_slot_markdown(PAGE, name, value, kit)
        changed = set(edited.split("\n")) - set(PAGE.split("\n"))
        assert changed == {line}, (name, value, changed)
        assert page_slots(edited)[name][0].value == value
    assert set_slot_markdown(PAGE, "arrives", "3:53 PM", kit) == PAGE
    print("  ✓  a slot edit changes its own value and nothing else")


def test_a_label_keeps_its_buttons_action_params_and_ordinal():
    kit = _kit()

    def buttons(md: str) -> list:
        ast = session.group_shared(md, kit)
        assert ast is not None
        acts = [t.action for t in action_targets(ast.to_dict())]
        return [(a.label, a.action, a.params, a.hints) for a in acts if a is not None]

    before = buttons(PAGE)
    after = buttons(set_slot_markdown(PAGE, "track", "Track · Sent", kit))
    assert len(after) == len(before) == 2, after
    assert after[0] == before[0], "the other button is untouched"
    assert after[1] == ("Track · Sent", *before[1][1:]), (before, after)
    assert after[1][2] == (("id", "BS-1043"),), "md2ui.feed is never a param"
    print("  ✓  a label slot changes the button's words; action, params, ordinal stay")


def test_cheap_rules_refuse_what_a_reader_cannot_see():
    for value, why in (
        ("x\ny", "U+000A, a control"),
        ("x\x1by", "U+001B, a control"),
        ("x\u2028y", "U+2028, a line break"),
        ("x\u2029y", "U+2029, a line break"),
        ("Late \u202eMP 85:3", "U+202E, a format"),  # case 3a: a bidi override
        ("a\u2066b", "U+2066, a format"),
        ("a\u200bb", "U+200B, a format"),  # zero-width space
        ("a\u00adb", "U+00AD, a format"),  # soft hyphen
        ("a\ue000b", "U+E000, a private-use"),
        ("a\u0378b", "U+0378, an unassigned"),
        ("a\u200db", "U+200D"),  # a joiner outside an emoji sequence
        ("\u200d🍳", "U+200D"),
        ("a" * 41, "over 40"),
        ("Out for delivery right now", "5 words; a slot holds a value"),
        ("x" * (MAX_WORD + 1), f"a word over {MAX_WORD}"),
        ("Order " + "W" * (MAX_WORD + 1), "add a space"),
        (" padded", "unpadded"),
        ("", "non-empty"),
        (4, "is not text"),
    ):
        said = _refused(lambda v=value: check_text("arrives", v))
        assert "'arrives'" in said and why in said, (value, said)
    for value in (
        "3:58 PM",
        "late, 4:10",
        "a | b",  # no character list: the regroup judges structure
        "😀 Ready",
        "👩\u200d🍳 cooking",  # case 3b: a ZWJ sequence
        "👨\u200d👩\u200d👧 Family",
        "🏳\ufe0f\u200d🌈 Pride",
        "❤\ufe0f",
        "1\ufe0f\u20e3 first",
        "x" * MAX_WORD,
        " ".join(["w"] * MAX_SLOT_WORDS),
        "On the way now",  # four words
    ):
        assert check_text("arrives", value) == value
    print("  ✓  invisible, line-breaking, long or unbroken values refused; emoji pass")


def test_a_styled_value_is_refused_from_the_annotation():
    kit = _kit()
    for name, value in (
        ("arrives", "**bold**"),
        ("due", "_x_"),
        ("due", "~~x~~"),
        ("due", "a `b` c"),
        ("track", "**Go**"),
        ("status", "a`b"),  # a backtick in a chip
    ):
        said = _refused(lambda n=name, v=value: set_slot_markdown(PAGE, n, v, kit))
        assert "would be styled; post plain words" in said, (name, value, said)
    print("  ✓  a posted style is refused: the author styles, the feed supplies words")


def test_the_regroup_refuses_what_changes_more_than_the_slot():
    kit = _kit()
    for name, value in (
        ("status", "3/10"),  # a ratio in a chip draws a bar
        ("due", "45%"),  # on a key line too
        ("arrives", "a | b"),  # divides a stat
        ("arrives", "# Big"),
        ("arrives", "x\\"),
        ("due", "[Go](#top)"),  # a target
    ):
        said = _refused(lambda n=name, v=value: set_slot_markdown(PAGE, n, v, kit))
        assert "would change the page beyond its slot" in said, (name, value, said)
    colon = "# Order\n\n_Arrives_ : ___[3:53 PM](feed:arrives)___\n"  # case 2c
    for value in ("Soon", "4:10 PM"):  # a word splits the column's run, not its look
        edited = set_slot_markdown(colon, "arrives", value, kit)
        assert f"___[{value}](feed:arrives)___" in edited, edited
    said = _refused(lambda: set_slot_markdown(colon, "arrives", "a | b", kit))
    assert "beyond its slot" in said, said
    assert "a | b" in set_slot_markdown(PAGE, "status", "a | b", kit), "literal in code"
    print("  ✓  a value that would draw as something else is refused on regrouping")


def test_a_feeds_values_go_in_as_one_edit():
    edited = set_fed_markdown(PAGE, {"Elapsed": 40.0, "arrives": "4:02 PM"}, _kit())
    assert edited == PAGE.replace("0%", "40%").replace(
        "[3:53 PM](feed:a", "[4:02 PM](feed:a"
    )
    print("  ✓  a figure goes into its bar and a text into its slot, in one edit")


TESTS = [
    test_a_slot_is_authored_and_named,
    test_a_slot_edit_moves_only_its_value,
    test_a_label_keeps_its_buttons_action_params_and_ordinal,
    test_cheap_rules_refuse_what_a_reader_cannot_see,
    test_a_styled_value_is_refused_from_the_annotation,
    test_the_regroup_refuses_what_changes_more_than_the_slot,
    test_a_feeds_values_go_in_as_one_edit,
]

if __name__ == "__main__":
    print("Wire Texts Tests")
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
