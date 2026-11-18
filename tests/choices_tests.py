"""
Unit tests for choices and counts (Phase 2 of the agent-turns roadmap): two
targets that hold a value in the window until a ``md2ui.commit`` press, read off
plain Markdown and committed by the mechanism task boxes and sliders already use.

Pinned here:

  * a choice option is an ``agent:`` button carrying ``md2ui.choice=<name>``; it
    is a target with a checked state, the chosen one written as the main variant
    and the rest ``*…*``, and it keeps the ordinal it has without the hint;
  * the hint makes no option of a plain link, an ``#anchor`` or a link inside a
    sentence: only a button shows which option is chosen;
  * a count is a ratio slider between ``➖`` (or ``−``) and ``➕`` (or ``+``), named
    by its key or caption rather than by the sign; an ASCII `` - `` before the
    figure is a dash, and a percent slider is no count;
  * on the wire a choice travels as ``[ordinal, true]``: one per group, never
    ``false``; the agent hears "…with size: "L"", and the commit writes the
    choice back by moving the main variant to the chosen option;
  * a count takes whole numbers only, in ``v`` and in ``vs``; a plain slider
    still takes a fraction;
  * on a page without a commit press, a tap on an option is delivered as a tap
    on that button is today.

Run with: uv run python tests/choices_tests.py
"""

import contextlib
import dataclasses
import io
import tempfile
from pathlib import Path

from md2ui import check_choices, session
from md2ui.check import check_markdown
from md2ui.pipeline.grouper_choices import choice_of
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.render_actions import Action, action_targets, stepped
from md2ui.pipeline.render_choices import settled_rows, show_locally
from md2ui.pipeline.render_counts import count_rects, count_size
from md2ui.pipeline.render_segmented import choice_style, paint_segmented
from md2ui.wire import MessageLog, Recorded, Rejected, Verified
from md2ui.wire_edits import choose_markdown, mark_markdown
from md2ui.wire_frames import FrameError, decode_client, encode

_KIT = None

SIZES = (
    "_Size_\n"
    "[S](agent:size?v=s&md2ui.choice=size) | "
    "*[M](agent:size?v=m&md2ui.choice=size)* | "
    "*[L](agent:size?v=l&md2ui.choice=size)*"
)
CART = (
    SIZES + "\n\nQuantity: ➖ [2/9] ➕\n\n[Add to cart](agent:add?id=7&md2ui.commit=1)"
)


def _kit():
    global _KIT
    if _KIT is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _KIT = session.load_grouping_kit()
    return _KIT


def _targets(markdown: str):
    ast = session.group_markdown(markdown, _kit())
    assert ast is not None
    return action_targets(ast.to_dict())


def _actions(markdown: str) -> list[Action]:
    actions = [t.action for t in _targets(markdown)]
    assert all(a is not None for a in actions), actions
    return [a for a in actions if a is not None]


def _log(mid: str, markdown: str) -> MessageLog:
    log = MessageLog(_kit())
    with contextlib.redirect_stdout(io.StringIO()):
        log.record(mid, markdown)
    return log


def _event(log: MessageLog, **frame):
    return log.verify(decode_client(encode({"t": "e", **frame})))


def test_an_option_is_a_target_with_a_checked_state():
    targets = _targets(SIZES)
    plain = _targets(SIZES.replace("&md2ui.choice=size", ""))
    assert [t.key for t in targets] == [t.key for t in plain], "same ordinals"
    assert [a.checked for a in _actions(SIZES)] == [False, True, True], targets
    assert [a.checked for a in _actions(SIZES.replace("&md2ui.choice=size", ""))] == [
        None,
        None,
        None,
    ]
    assert all(a.kind == "agent" for a in _actions(SIZES))
    print("  ✓  an option is a target with a checked state, at its old ordinal")


def test_the_hint_makes_no_option_of_a_link_an_anchor_or_prose():
    for markdown in (
        "[S](/s?md2ui.choice=size) | *[M](/m?md2ui.choice=size)*",
        "[S](#s?md2ui.choice=size) | *[M](#m?md2ui.choice=size)*",
        "Pick a size: [S](agent:size?v=s&md2ui.choice=size) or "
        "[M](agent:size?v=m&md2ui.choice=size).",
    ):
        for target in _targets(markdown):
            assert target.action is not None and target.action.checked is None, (
                markdown,
                target,
            )
    print("  ✓  a link, an anchor or a link in a sentence is no option")


def test_a_count_is_named_by_its_key_not_its_sign():
    cases = {
        "Quantity: ➖ [2/9] ➕": "Quantity",
        "Quantity: − [2/9] +": "Quantity",
        "_Adults_\n➖ [2/9] ➕": "Adults",
        "➖ [2/9] ➕ : _Quantity_": "Quantity",
        "| Item | Qty |\n|---|---|\n| Socks | ➖ [2/9] ➕ |": "Socks",
        "- Quantity: ➖ [2/9] ➕": "Quantity",
    }
    for markdown, label in cases.items():
        (target,) = _targets(markdown)
        action = target.action
        assert action is not None and action.kind == "slider", markdown
        assert action.count and action.label == label, (markdown, action)
    for markdown in ("Quantity: - [2/9] +", "Quantity: ➖ [65%] ➕", "Apples: [3/10]"):
        (target,) = _targets(markdown)
        assert target.action is not None and not target.action.count, markdown
    print("  ✓  a count is named by its key, not its sign; a dash or a % is none")


def test_a_choice_travels_as_its_chosen_option():
    log = _log("c1", CART)
    press = _event(log, m="c1", x=4, q=1, a="add", vs=[[2, True], [3, 5]])
    assert isinstance(press, Verified), press
    assert press.agent_text() == (
        'User chose "Add to cart": add {id: 7}, with size: "L", "Quantity" at 5 '
        "(message c1)"
    ), press.agent_text()
    with contextlib.redirect_stdout(io.StringIO()):
        frames = log.commit(press, "c2")
    assert frames[0]["md"] == CART.replace(
        "[S](agent:size?v=s&md2ui.choice=size)",
        "*[S](agent:size?v=s&md2ui.choice=size)*",
    ).replace(
        "*[L](agent:size?v=l&md2ui.choice=size)*",
        "[L](agent:size?v=l&md2ui.choice=size)",
    ).replace("[2/9]", "[5/9]"), frames[0]["md"]
    print("  ✓  a choice travels as its chosen option and is written back")


def test_the_chosen_option_as_written_is_no_change():
    log = _log("c1", CART)
    press = _event(log, m="c1", x=4, q=1, a="add", vs=[[0, True]])
    assert isinstance(press, Verified), press
    assert press.settled == (), press.settled
    assert press.agent_text().endswith("with no change (message c1)")
    print("  ✓  the option chosen as written is no change")


def test_a_choice_is_one_option_and_never_cleared():
    for q, rows in enumerate(([[1, True], [2, True]], [[1, False]], [[0, False]])):
        got = _event(_log("c1", CART), m="c1", x=4, q=q, a="add", vs=rows)
        assert isinstance(got, Rejected) and got.code == "bad_value", (rows, got)
    got = _event(_log("c1", SIZES), m="c1", x=1, q=1, a="size", c=False)
    assert isinstance(got, Rejected) and got.code == "bad_value", got
    print("  ✓  a group sends one option, and an option is never cleared")


def test_a_count_takes_whole_numbers_only():
    log = _log("c1", CART)
    for q, frame in enumerate(({"x": 3, "v": 2.5}, {"x": 4, "vs": [[3, 4.5]]})):
        got = _event(log, m="c1", q=q, **frame)
        assert isinstance(got, Rejected) and got.code == "bad_value", (frame, got)
    got = _event(log, m="c1", x=3, q=9, v=4)
    assert isinstance(got, Recorded), got  # the press carries it
    plain = _log("p1", "Apples: [3/10]")
    assert isinstance(_event(plain, m="p1", x=0, q=1, v=2.5), Verified)
    print("  ✓  a count takes whole numbers only; a plain slider a fraction")


def test_a_tap_without_a_commit_press_is_todays_tap():
    log = _log("c1", SIZES)
    got = _event(log, m="c1", x=1, q=1, a="size", c=True)
    assert isinstance(got, Verified), got
    assert got.agent_text() == 'User chose "M": size {v: m} (message c1)', (
        got.agent_text()
    )
    print("  ✓  without a commit press a tap is delivered as today's tap")


def test_a_recorded_choice_is_asked_for_once_per_group():
    log = _log("c1", CART)
    for q, x in enumerate((1, 2)):
        got = _event(log, m="c1", x=x, q=q, a="size", c=True)
        assert isinstance(got, Recorded), got
    assert log.requested("c1") == {2: True}, log.requested("c1")
    print("  ✓  what the user asked of a group is its last choice")


def test_the_agent_chooses_and_disables_an_option():
    chosen = choose_markdown(SIZES, 1, _kit())
    assert [a.checked for a in _actions(chosen)] == [True, False, True]
    assert mark_markdown(SIZES, 2, "checked", _kit()) == choose_markdown(
        SIZES, 2, _kit()
    )
    assert choose_markdown(SIZES, 0, _kit()) == SIZES
    disabled = mark_markdown(SIZES, 1, "disabled", _kit())
    assert "~~*[M](agent:size?v=m&md2ui.choice=size)*~~" in disabled, disabled
    try:
        mark_markdown(SIZES, 0, "unchecked", _kit())
    except FrameError as e:
        assert e.code == "bad_target"
    else:
        raise AssertionError("a choice is never unchecked")
    print("  ✓  the agent chooses or disables an option, never unchecks one")


THEME = Path(__file__).resolve().parent.parent / "data/markdown/tests/THEME.md"


def _scene(markdown: str, width: float = 600.0):
    with contextlib.redirect_stdout(io.StringIO()):
        theme = session.load_theme(THEME)
        fonts = session.load_fonts(theme)
        ast = session.group_markdown(markdown, _kit())
        assert ast is not None
        root, node_index = session.prepare(ast, theme)
        scene = session.build_scene(
            LayoutGenerator(), root, node_index, theme, fonts, width
        )
    return scene, node_index, theme, fonts


def test_a_count_takes_its_signs_as_buttons():
    """The signs leave the words beside the count: one leaf, never wrapped."""
    ast = session.group_markdown("Take ➖ [2/9] ➕ of them.", _kit())
    assert ast is not None

    def leaves(nd: dict) -> list[str]:
        kids = nd.get("children", [])
        if not kids:
            return [] if nd.get("drawing_element") else [nd.get("content", "")]
        return [text for kid in kids for text in leaves(kid)]

    texts = leaves(ast.to_dict())
    assert texts == ["Take", " of them."], texts
    (target,) = _targets("Quantity: ➖ [2/9] ➕")
    assert target.action is not None and target.action.count
    print("  ✓  a count takes its signs as its buttons, out of the words")


def test_a_count_has_two_regions_that_step_inside_its_range():
    scene, _index, _theme, _fonts = _scene("Quantity: ➖ [0/2] ➕")
    minus, plus = [r for r in scene.regions if r.action.kind == "slider"]
    assert (minus.step, plus.step) == (-1, 1) and minus.x < plus.x
    assert minus.action == plus.action, "one target"
    assert stepped(minus, {}) is None, "0 is the floor"
    up = stepped(plus, {})
    assert up is not None and up.value == 1.0
    assert stepped(plus, {plus.action.node_id: 2.0}) is None, "2 is the ceiling"
    print("  ✓  a count's ➖ and ➕ step one target inside 0..max")


def test_a_tap_chooses_one_option_and_the_press_carries_it():
    targets = _targets(CART)
    actions = _actions(CART)
    states: dict = {}
    asked = show_locally(actions[2], targets, states)
    assert asked.checked is True
    keys = [t.key for t in targets[:3]]
    assert [states[k] for k in keys] == ["unchecked", "unchecked", "checked"]
    asked = show_locally(actions[1], targets, states)
    assert [states[k] for k in keys] == ["unchecked", "checked", "unchecked"]
    states[targets[3].key] = 5.0
    assert settled_rows(targets, states, 4) == [[1, True], [3, 5.0]]
    print("  ✓  a tap chooses one option locally; the press carries [o, true]")


def _marked(markdown: str, width: float, segmented: bool | None = None) -> list[bool]:
    """Which of *markdown*'s buttons ``paint_segmented`` draws as segments, under
    the fixture theme, its ``Segmented`` key replaced when *segmented* is given."""
    import skia

    from md2ui.pipeline.layout_render import _link_pill_rect

    scene, index, theme, fonts = _scene(markdown, width)
    if segmented is not None:
        theme = dataclasses.replace(
            theme, links=dataclasses.replace(theme.links, segmented=segmented)
        )
    canvas = skia.Surface(10, 10).getCanvas()
    out = paint_segmented(
        canvas,
        scene.boxes,
        index,
        lambda b, nd: _link_pill_rect(b, nd, fonts, theme),
        theme,
    )
    return [bool(nd.get("segment")) for nd in out.values() if nd["type"] == "link"]


def test_a_shared_run_draws_segmented_and_a_wrapped_one_does_not():
    assert _marked(SIZES, 600) == [True, True, True]
    assert _marked(SIZES.replace(" | ", " "), 600) == [False] * 3, "pills"
    long = (
        "[Economy](agent:c?c=y&md2ui.choice=c) | "
        "*[Premium economy plus](agent:c?c=w&md2ui.choice=c)* | "
        "*[Business class](agent:c?c=j&md2ui.choice=c)* | "
        "*[First class suite](agent:c?c=f&md2ui.choice=c)*"
    )
    assert _marked(long, 360) == [False] * 4, "wrapped: pills"
    print("  ✓  a shared ` | ` run draws segmented; spaced or wrapped, pills")


def test_a_choice_run_is_segmented_only_when_the_theme_says_so():
    """The look is the theme's (ADR-405): `## Links` →
    `Segmented: yes` draws the run as one control; a theme that says nothing
    draws it as pills. The grouper's stamp is the same either way."""
    assert session.load_theme(THEME).links.segmented, "the fixture theme asks for it"
    with tempfile.TemporaryDirectory() as tmp:
        bare = Path(tmp) / "THEME.md"
        bare.write_text("## Links\n### Primary\nCorner radius: 8\n")
        with contextlib.redirect_stdout(io.StringIO()):
            assert not session.load_theme(bare).links.segmented, "unset: no"
        keyed = Path(tmp) / "keyed" / "THEME.md"
        keyed.parent.mkdir()
        keyed.write_text("## Links\n### Secondary\nSegmented: yes\n")
        with contextlib.redirect_stdout(io.StringIO()):
            assert session.load_theme(keyed).links.segmented, "any block of the section"
    assert _marked(SIZES, 600, segmented=False) == [False] * 3, "pills"
    assert _marked(SIZES, 600, segmented=True) == [True] * 3
    print("  ✓  a choice run is segmented only when the theme says so")


def test_a_tap_swaps_an_options_colours_only():
    theme = session.load_theme(THEME)
    (node,) = [nd for nd in _scene(SIZES)[1].values() if nd.get("link_label") == "L"]
    from md2ui.pipeline.render_style import _resolve_link

    style = _resolve_link(node, theme)[3]
    shown = choice_style({**node, "choice_shown": True}, style, theme)
    main = _resolve_link({**node, "link_variant": "primary"}, theme)[3]
    assert shown.fill_color == main.fill_color != style.fill_color
    assert shown.padding == style.padding, "the box is the authored variant's"
    assert choice_style(node, style, theme) is style
    print("  ✓  a tap swaps an option's colours, never its box")


def test_check_names_what_would_not_hold_a_choice():
    def codes(markdown: str) -> list[str]:
        return [
            i["code"]
            for i in check_markdown(markdown, _kit())
            if i["code"].startswith(("choice", "count", "link-param"))
        ]

    assert codes(CART) == [], codes(CART)
    assert codes("[S](/s?md2ui.choice=size) | *[M](/m?md2ui.choice=size)*") == [
        "choice-not-agent",
        "choice-not-agent",
    ]
    commits = SIZES.replace("v=s&md2ui.choice", "v=s&md2ui.commit=1&md2ui.choice")
    assert "choice-commits" in codes(commits)
    two = SIZES.replace("v=l&md2ui.choice=size", "v=l&md2ui.choice=cabin")
    assert "choice-names" in codes(two)
    assert "choice-in-task" in codes("- [ ] " + SIZES.splitlines()[1])
    assert "choice-chosen" in codes(
        SIZES.replace("*[M]", "[M]").replace(")* |", ") |", 1)
    )
    bold = "**[L](agent:size?v=l&md2ui.choice=size)**"
    strong = check_markdown(SIZES.replace(SIZES.rsplit(" | ", 1)[1], bold), _kit())
    (spelled,) = [i for i in strong if i["code"] == "choice-spelling"]
    assert spelled["level"] == "warning" and "`L`" in spelled["message"], spelled
    assert "`M`" not in spelled["message"] and spelled["x"] == 2, spelled
    assert "choice-not-button" in codes(
        "Pick [S](agent:size?v=s&md2ui.choice=size) or "
        "[M](agent:size?v=m&md2ui.choice=size)."
    )
    assert codes("Quantity: ➖ [[2/9]](agent:qty?md2ui.commit=1) ➕") == [
        "count-commits"
    ]
    assert codes("Quantity: ➖ [2.5/9] ➕") == ["count-whole"]
    print("  ✓  check names what would not hold a choice or a count")


def test_a_count_box_is_the_same_at_every_value():
    """The digits' slot is the authored maximum's, so a step moves no box."""
    theme = session.load_theme(THEME)
    sizes = {count_size({"value": v, "max": 12.0}, theme) for v in (0.0, 5.0, 12.0)}
    assert len(sizes) == 1, sizes
    scene, index, theme, _fonts = _scene("Quantity: ➖ [2/9] ➕")
    (box,) = [
        b for b in scene.boxes if (index.get(b.content_id) or {}).get("drawing_element")
    ]
    payload = index[box.content_id]["drawing_element"]
    minus, plus = count_rects(box, payload, theme)
    assert (box.width, box.height) >= (count_size(payload, theme)), box
    assert minus[2] == plus[2] == count_size(payload, theme)[1]
    print("  ✓  a count's box is the theme's, the same at every value")


def test_check_choices_reports_each_issue_with_its_target():
    ast = session.group_markdown("- [ ] " + SIZES.splitlines()[1], _kit())
    assert ast is not None
    tree = ast.to_dict()
    found = list(check_choices.problems(tree, action_targets(tree)))
    assert {(code, x) for _level, code, _m, x in found} >= {
        ("choice-in-task", 0),
        ("choice-in-task", 1),
    }, found
    print("  ✓  check_choices names each issue's target")


def test_the_grouper_stamps_a_shared_pipe_run_segmented():
    """ADR-100: the run is a flag the grouper stamps once; paint only reads it."""

    def flagged(markdown: str) -> list[list[str]]:
        ast = session.group_markdown(markdown, _kit())
        assert ast is not None
        stack, runs = [ast.to_dict()], []
        while stack:
            nd = stack.pop()
            if nd.get("segmented_run"):
                runs.append([k.get("link_label") for k in nd["children"]])
            stack.extend(nd.get("children", []))
        return runs

    assert flagged(SIZES) == [["S", "M", "L"]], flagged(SIZES)
    assert choice_of("*[M](agent:size?v=m&md2ui.choice=size)*") == "size"
    assert choice_of("[M](/m?md2ui.choice=size)") is None, "only an agent: button"
    assert flagged(SIZES.replace(" | ", " ")) == [], "space-divided: pills"
    assert flagged(SIZES.replace(" | ", " - ")) == [], "dash-divided: pills"
    two = SIZES.replace("v=l&md2ui.choice=size", "v=l&md2ui.choice=cabin")
    assert flagged(two) == [], "two names"
    tabs = SIZES.replace("&md2ui.choice=size", "")
    assert flagged(tabs) == [], "plain tabs stay the theme key's"
    print("  ✓  the grouper stamps a ` | ` run of one choice segmented, once")


def test_a_muted_count_is_disabled_and_keeps_its_ordinal():
    """A count takes a slider's muted state, around its figure or around the
    whole control: ``➖ ~~[2/9]~~ ➕`` and ``~~➖ [2/9] ➕~~`` are a count drawn
    disabled that reports nothing, at its ordinal, named by its key, with no
    tildes left beside it."""
    for markdown in (
        "Quantity: ➖ ~~[2/9]~~ ➕\n\nSize: ➖ [3/9] ➕",
        "Quantity: ~~➖ [2/9] ➕~~\n\nSize: ➖ [3/9] ➕",
        "~~Quantity: ➖ [2/9] ➕~~\n\nSize: ➖ [3/9] ➕",
    ):
        ast = session.group_markdown(markdown, _kit())
        assert ast is not None
        tree = ast.to_dict()
        payloads, texts = [], []

        def walk(nd: dict) -> None:
            if nd.get("drawing_element"):
                payloads.append(nd["drawing_element"])
            elif not nd.get("children"):
                texts.append(nd.get("content", ""))
            for kid in nd.get("children", []):
                walk(kid)

        walk(tree)
        assert [(p.get("count"), p.get("disabled", False)) for p in payloads] == [
            (True, True),
            (True, False),
        ], (markdown, payloads)
        assert [p["label"] for p in payloads] == ["Quantity", "Size"], markdown
        assert not [t for t in texts if "~~" in t.replace("~~Quantity~~", "")], texts
        targets = action_targets(tree)
        assert targets[0].action is None and targets[0].disabled, markdown
        live = targets[1].action
        assert live is not None and live.count and live.index == 1, markdown
    print("  ✓  a muted count is disabled, at its ordinal, its tildes taken with it")


TESTS = [
    test_an_option_is_a_target_with_a_checked_state,
    test_the_hint_makes_no_option_of_a_link_an_anchor_or_prose,
    test_a_count_is_named_by_its_key_not_its_sign,
    test_a_choice_travels_as_its_chosen_option,
    test_the_chosen_option_as_written_is_no_change,
    test_a_choice_is_one_option_and_never_cleared,
    test_a_count_takes_whole_numbers_only,
    test_a_tap_without_a_commit_press_is_todays_tap,
    test_a_recorded_choice_is_asked_for_once_per_group,
    test_the_agent_chooses_and_disables_an_option,
    test_a_count_takes_its_signs_as_buttons,
    test_a_muted_count_is_disabled_and_keeps_its_ordinal,
    test_a_count_has_two_regions_that_step_inside_its_range,
    test_a_tap_chooses_one_option_and_the_press_carries_it,
    test_a_shared_run_draws_segmented_and_a_wrapped_one_does_not,
    test_a_choice_run_is_segmented_only_when_the_theme_says_so,
    test_a_tap_swaps_an_options_colours_only,
    test_check_names_what_would_not_hold_a_choice,
    test_a_count_box_is_the_same_at_every_value,
    test_check_choices_reports_each_issue_with_its_target,
    test_the_grouper_stamps_a_shared_pipe_run_segmented,
]

if __name__ == "__main__":
    print("Choices and counts")
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
