"""
Includes a backend expands, and clicks it answers by changing data (ADR-612,
proposed; option B of the agent-turns roadmap).

Pinned here:

  * an include is a line holding exactly one ``{{name args}}``, at its first
    column, with a blank line (or the document's edge) before and after, outside
    a code fence; ``{{…}}`` inside text is never one. Args read as the burger
    shop's: ``key=value``, ``key="quoted"``, bare words;
  * ``Conversation.send`` expands before recording, so the log, the ordinals and
    what a window is sent are the real page; the log keeps each include's region,
    so the page's source can be given back and a region drawn again;
  * a region survives the server's own edits (``mark``) and is found again;
  * a handled click (a handler by ``agent:`` slug) redraws its includes on the
    page shown in ONE replacement, is never queued for the agent, releases the
    button while listening, and is handed over as one line of ``take_handled``;
    the agent's id resolves through it, as through a feed's tick (ADR-608);
  * a handler that answers None leaves the click to the agent; one that raises
    does too, with a digest line naming the action and the error's class;
  * an agent's ``patch`` or ``mark`` touching an include's lines is refused,
    naming what to do instead; an edit outside keeps the region;
  * an include line between list items or in a ``:::`` row's cell is not
    expanded, and ``check`` warns; a streamed page's include line is warned
    about as streamed; an unknown include on a server with none is a warning;
  * a handled click is released (``u``) in any state, to its own connection;
  * ``show(message_id=…)`` draws the page's includes from the data now and
    says which (``redrawn``);
  * the authoring server expands before ``check`` and ``outline``, reports an
    include it does not have as an error, loads static includes from an
    ``includes/`` folder beside the theme, and names ``includes`` in ``guide``
    only when it has some;
  * the eval runner takes a suite by its path;
  * an include that cannot be drawn (no such name, args that do not read, an
    expander that raised), sent or redrawn, draws the failure line its backend
    registered, in the muted tier, or nothing. It stays the include's region,
    so a redraw recovers it, and ``check`` and the digest name it and the
    error's class, never its text (ADR-612).

Run with: uv run python tests/includes_tests.py
"""

import asyncio
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from websockets.sync.client import connect

from md2ui import mcp_server, session
from md2ui.pipeline.render_settings import VIEW
from md2ui.utils.fetch_policy import POLICY
from md2ui.wire import Verified
from md2ui.wire_server import Conversation, Served

ROOT = Path(__file__).resolve().parent.parent
TEST_THEME = ROOT / "data/markdown/tests/THEME.md"

_MODELS = None


def _kit():
    global _MODELS
    if _MODELS is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _MODELS = session.load_grouping_kit()
    return _MODELS


class Shop:
    """A backend's data: a cart, drawn by `{{cart}}`, changed by a handler."""

    def __init__(self) -> None:
        self.count = 1

    def cart(self, _args: Any) -> str:
        return (
            f"## Cart\n\nClassic Smash: {self.count}\n\n"
            "[➖](agent:cart-remove?id=smash) [➕](agent:cart-add?id=smash)"
        )

    def add(self, params: dict[str, str]) -> set[str]:
        assert params == {"id": "smash"}, params
        self.count += 1
        return {"cart"}


def _includes(shop: Shop):
    from md2ui.includes import Includes

    includes = Includes()
    includes.add("cart", "the cart page, with its steppers", shop.cart)
    includes.add(
        "order",
        "one order",
        lambda a: f"Order {a.words[0]}: {a.named.get('note', '')}",
        "<order id> note=…",
    )
    return includes


PAGE = "# Your order\n\nHere is your cart.\n\n{{cart}}\n\n[Checkout](agent:checkout)\n"


def test_only_a_lone_line_is_an_include():
    from md2ui.includes import expand, parse_args

    includes = _includes(Shop())
    page = (
        "Text with {{cart}} inside.\n\n"
        '{{order BS-1 note="two words"}}\n\n'
        "```\n\n{{cart}}\n\n```\n\n"
        "  {{cart}}\n\n"
        "{{cart}} {{order x}}\n\n"
        "{{cart}}\nglued to the next line\n"
    )
    out, regions = expand(page, includes)
    assert "Order BS-1: two words" in out, out
    assert [r.line for r in regions] == ['{{order BS-1 note="two words"}}'], regions
    for kept in ("Text with {{cart}} inside.", "```\n\n{{cart}}\n\n```", "  {{cart}}"):
        assert kept in out, kept
    assert "{{cart}} {{order x}}" in out and "{{cart}}\nglued" in out, out
    args = parse_args('a b, k=v t="x y"')
    assert args.words == ("a", "b") and dict(args.named) == {"k": "v", "t": "x y"}
    print("  ✓  only a lone {{name args}} line between blank lines is an include")


def test_send_expands_before_recording_and_keeps_the_source():
    shop = Shop()
    conversation = Conversation(_kit(), includes=_includes(shop))
    with contextlib.redirect_stdout(io.StringIO()):
        mid = asyncio.run(conversation.send(PAGE))
    log = conversation.log
    shown = log.markdown(mid)
    assert "Classic Smash: 1" in shown and "{{cart}}" not in shown, shown
    actions = [t.action.action for t in log.targets(mid) if t.action]
    assert actions == ["cart-remove", "cart-add", "checkout"], actions
    assert log.pages.includes.source(mid, shown) == PAGE, "the source is not kept"
    print("  ✓  send expands before the log records; the source is kept")


def _frames(ws, n: int) -> list[dict]:
    return [json.loads(ws.recv(timeout=5)) for _ in range(n)]


def test_a_handled_click_redraws_its_include_and_never_wakes_the_agent():
    shop = Shop()
    served = Served(Conversation(_kit(), includes=_includes(shop)))
    conversation = served.conversation
    conversation.handlers["cart-add"] = shop.add
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            mid = served.call(conversation.send(PAGE))
            served.call(conversation.set_state("l"))
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 3)  # the page, its end, the state
            ws.send(json.dumps({"t": "e", "m": mid, "x": 1, "q": 1, "a": "cart-add"}))
            message, end, state = _frames(ws, 3)
            assert message["r"] == mid and "Classic Smash: 2" in message["md"], message
            assert message["md"].replace("2", "1") == conversation.log.markdown(mid)
            assert (end["t"], state) == ("z", {"t": "s", "s": "l", "u": [1]}), state
            assert served.next_event(timeout=0.3) is None, "the agent was woken"
            (line,) = conversation.take_handled()
            assert line.startswith('User chose "➕": cart-add {id: smash}'), line
            assert "redrawing {{cart}}" in line, line
            assert conversation.take_handled() == [], "the digest is handed over once"
            # The agent's id still names its page: a mark on it lands on the redraw.
            with contextlib.redirect_stdout(io.StringIO()):
                new = served.call(conversation.mark(mid, 2, "disabled"))
            assert "~~[Checkout](agent:checkout)~~" in conversation.log.markdown(new)
            assert "Classic Smash: 2" in conversation.log.markdown(new)
            # The region was carried through the mark, so it is drawn again.
            ws.send(json.dumps({"t": "e", "m": new, "x": 1, "q": 2, "a": "cart-add"}))
            _frames(ws, 2)  # the mark's replacement
            message, _end, _state = _frames(ws, 3)
            assert "Classic Smash: 3" in message["md"], message["md"]
            assert "~~[Checkout](agent:checkout)~~" in message["md"], message["md"]
    finally:
        served.stop()
    print("  ✓  a handled click: one replacement, no wake, a digest line, ids kept")


def test_a_handler_that_declines_leaves_the_click_to_the_agent():
    shop = Shop()
    served = Served(Conversation(_kit(), includes=_includes(shop)))
    conversation = served.conversation
    conversation.handlers["cart-add"] = lambda _params: None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            mid = served.call(conversation.send(PAGE))
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 2)
            ws.send(json.dumps({"t": "e", "m": mid, "x": 1, "q": 1}))
            event = served.next_event()
            assert isinstance(event, Verified), event
            assert event.action.action == "cart-add", event
            assert conversation.take_handled() == []
    finally:
        served.stop()
    print("  ✓  a handler answering None: the agent hears the click")


def test_a_handler_that_raises_leaves_the_click_to_the_agent():
    from md2ui.wire_includes import answer

    shop = Shop()
    conversation = Conversation(_kit(), includes=_includes(shop))
    with contextlib.redirect_stdout(io.StringIO()):
        mid = asyncio.run(conversation.send(PAGE))
    log = conversation.log
    verified = log.verify({"t": "e", "m": mid, "x": 1, "q": 1})
    assert isinstance(verified, Verified), verified

    def broken(_params: dict[str, str]) -> set[str]:
        raise RuntimeError("the shop's database is down")

    with contextlib.redirect_stderr(io.StringIO()) as said:
        handled = answer(log, conversation.includes, broken, verified, mid, "c9")
    assert handled is not None and handled.frames == [], handled
    assert "database is down" in said.getvalue()  # the backend's log, not the agent's
    assert log.markdown("c9") == "", "a failed handler recorded a replacement"
    print("  ✓  a handler that raises: nothing is sent, the agent hears the click")


def _static_theme(folder: Path) -> Path:
    theme = folder / "THEME.md"
    theme.write_text(TEST_THEME.read_text(encoding="utf-8"), encoding="utf-8")
    (folder / "includes").mkdir()
    (folder / "includes" / "cart.md").write_text(
        "---\ndescription: the cart page\nargs: \n---\n## Cart\n\nClassic Smash: 4\n",
        encoding="utf-8",
    )
    return theme


def _text(result: Any) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


def test_the_authoring_server_checks_the_expanded_page():
    with tempfile.TemporaryDirectory() as folder:
        server = mcp_server.build_server(_static_theme(Path(folder)))
        with contextlib.redirect_stdout(io.StringIO()):

            def call(name: str, **arguments: Any) -> str:
                return _text(asyncio.run(server.call_tool(name, arguments)))

            page = "# Hi\n\n{{cart}}\n"
            assert "unknown-include" not in call("check", markdown=page)
            assert "Classic Smash" in call("outline", markdown=page)
            unknown = call("check", markdown="# Hi\n\n{{basket}}\n")
            assert "unknown-include" in unknown and '"error"' in unknown, unknown
            listed = call("guide", topic="includes")
            assert "- {{cart}}: the cart page" in listed, listed
            tools = {t.name: t for t in asyncio.run(server.list_tools())}
            assert "includes" in (tools["guide"].description or "")
    print("  ✓  check and outline see the expansion; an unknown include is an error")


def test_a_server_without_includes_says_so_and_does_not_name_them():
    server = mcp_server.build_server(None)
    with contextlib.redirect_stdout(io.StringIO()):
        result = asyncio.run(server.call_tool("guide", {"topic": "includes"}))
        tools = {t.name: t for t in asyncio.run(server.list_tools())}
        uris = {str(r.uri) for r in asyncio.run(server.list_resources())}
    assert (
        _text(result) == "This server has no includes: write every part of your answer."
    )
    assert "includes" not in (tools["guide"].description or "")
    assert "md2ui://skills/includes.md" not in uris, uris
    print("  ✓  no includes: guide says so in one line, and names none")


def test_the_demo_shows_the_expansion_and_hands_over_handled_clicks():
    from md2ui import mcp_demo

    with tempfile.TemporaryDirectory() as folder:
        server, demo = mcp_demo.build_demo_server(
            _static_theme(Path(folder)), launch_window=False
        )

        def call(name: str, **arguments: Any) -> dict:
            with contextlib.redirect_stdout(io.StringIO()):
                result: Any = asyncio.run(server.call_tool(name, arguments))
            return result.structured_content or json.loads(_text(result))

        try:
            page = "# Hi\n\n{{cart}}\n\n[Go](agent:go)\n"
            shown = call("show", markdown=page, wait_seconds=0)
            assert shown["issues"] == [], shown["issues"]
            read = call("showing")
            assert "Classic Smash: 4" in read["markdown"], read
            assert read["source"] == page, read
            unknown = call("show", markdown="# Hi\n\n{{basket}}\n", wait_seconds=0)
            codes = [i["code"] for i in unknown["issues"]]
            assert codes == ["unknown-include"], unknown["issues"]
            mid = call("show", markdown=page, wait_seconds=0)["message_id"]
            conversation = demo.started().conversation
            conversation.handlers["go"] = lambda _params: {"cart"}
            headers = {"Authorization": f"Bearer {demo.bearer}"}
            url = demo.started().url
            with connect(url, compression=None, additional_headers=headers) as ws:
                ws.send('{"t":"h","v":1}')
                ws.send(json.dumps({"t": "e", "m": mid, "x": 0, "q": 1}))
                heard = call("wait_for_event", timeout_seconds=1)
            assert heard["events"] == [], heard
            (line,) = heard["handled"]
            assert line.startswith('User chose "Go": go'), line
        finally:
            demo.close()
    print("  ✓  the demo checks the expanded page and hands over a handled click")


def test_the_eval_runner_takes_a_suite_by_its_path():
    spec = importlib.util.spec_from_file_location(
        "eval_run", ROOT / "scripts" / "eval_run.py"
    )
    assert spec is not None and spec.loader is not None
    eval_run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eval_run)
    with tempfile.TemporaryDirectory() as folder:
        suite = Path(folder) / "my-suite"
        suite.mkdir()
        (suite / "tasks.md").write_text("Intro.\n\n## one\n\nSay hi.\n")
        argv = ["eval_run.py", str(suite), "--model", "m", "--task", "nope"]
        out = io.StringIO()
        with contextlib.redirect_stdout(out), _argv(argv):
            code = eval_run.main()
        assert code == 2 and "the suite has one" in out.getvalue(), out.getvalue()
        theme = _static_theme(Path(folder))
        assert "Classic Smash: 4" in eval_run.expanded("{{cart}}\n", theme)
    print("  ✓  the eval runner reads a suite given as a path")


# The open questions of ADR-612, as it settles them.

ORDER_BODY = (
    "## Cart\n\nClassic Smash: 1\n\n- [ ] Extra cheese\n\n"
    "[➕](agent:cart-add?id=smash)\n\n## Totals\n\nPrep: 1/4\n\nTotal: $9.50"
)
ORDER_PAGE = "# Your order\n\n{{cart}}\n\n## Next\n\n- [ ] Napkins\n\n[Checkout](agent:checkout)\n"


def _order_conversation() -> tuple[Conversation, str]:
    from md2ui.includes import Includes

    includes = Includes()
    includes.add("cart", "the cart", lambda _args: ORDER_BODY)
    conversation = Conversation(_kit(), includes=includes)
    with contextlib.redirect_stdout(io.StringIO()):
        mid = asyncio.run(conversation.send(ORDER_PAGE))
    return conversation, mid


def test_an_agent_edit_touching_an_include_is_refused():
    from md2ui.wire_frames import FrameError

    conversation, mid = _order_conversation()
    log = conversation.log
    # x 0 is the cart's task box, x 1 its stepper: both drawn by {{cart}}.
    edits = {
        "patch section": conversation.patch(mid, "## Cart\n\nEmpty.", section="Cart"),
        "patch after": conversation.patch(mid, "## Tip\n\nTen.", "Cart", side="after"),
        "patch before": conversation.patch(
            mid, "## Tip\n\nTen.", "Totals", side="before"
        ),
        "patch x": conversation.patch(mid, "[❌](agent:cart-drop)", x=1),
        "patch replace": conversation.patch(
            mid, "", replace=[("Smash: 1", "Smash: 9")]
        ),
        "mark x": conversation.mark(mid, 0, "checked"),
        "mark key": conversation.set_bar(mid, "Prep", 3),
    }
    for verb, edit in edits.items():
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                asyncio.run(edit)
        except FrameError as exc:
            said = str(exc)
            assert "{{cart}}" in said and "re-send" in said, (verb, said)
            assert "data" in said, (verb, said)
        else:
            raise AssertionError(f"{verb} edited what {{{{cart}}}} drew")
    assert log.markdown(mid) and conversation.latest == mid, "a refused edit was sent"
    print("  ✓  an agent's patch or mark inside an include is refused, saying why")


def test_an_agent_edit_outside_an_include_keeps_it():
    conversation, mid = _order_conversation()
    log = conversation.log
    with contextlib.redirect_stdout(io.StringIO()):
        marked = asyncio.run(conversation.mark(mid, 2, "checked"))
        patched = asyncio.run(
            conversation.patch(marked, "## Next\n\n[Pay](agent:pay)", section="Next")
        )
        added = asyncio.run(
            conversation.patch(patched, "## Tip\n\nTen.", "Next", side="after")
        )
    for new in (marked, patched, added):
        source = log.pages.includes.source(new, log.markdown(new))
        assert source.count("{{cart}}") == 1 and "Smash" not in source, source
    assert "[Pay](agent:pay)" in log.markdown(added) and "## Tip" in log.markdown(added)
    print("  ✓  an edit wholly outside an include works and keeps its region")


def test_an_include_inside_a_list_or_a_row_is_not_expanded_and_warned():
    from md2ui.includes import expand, unexpanded

    includes = _includes(Shop())
    nested = {
        "between list items": "- Burger\n- Fries\n\n{{cart}}\n\n- Drink\n",
        "a middle cell": "___\n\nLeft\n\n:::\n\n{{cart}}\n\n:::\n\nRight\n\n___\n",
        "the last cell": "___\n\nLeft\n\n:::\n\n{{cart}}\n\n___\n\nAfter.\n",
        "a cell's section": "Left\n\n:::\n\n## Plan\n\n{{cart}}\n\n___\n\nAfter.\n",
        "an unbounded last cell": "# T\n\nLeft\n\n:::\n\nRight\n\n{{cart}}\n",
        "a section's first cell": "# T\n\n## B\n\n{{cart}}\n\n:::\n\nRight\n",
    }
    for where, page in nested.items():
        out, regions = expand(page, includes)
        assert out == page and regions == (), where
        (issue,) = unexpanded(page, includes)
        assert (issue["level"], issue["code"]) == ("warning", "nested-include"), issue
        assert "own block" in issue["message"], issue
    top = {
        "after a list": "- Burger\n- Fries\n\n{{cart}}\n\n## Next\n",
        "a later section": "## A\n\nLeft\n\n:::\n\nRight\n\n## B\n\n{{cart}}\n",
        "after a row": "___\n\nLeft\n\n:::\n\nRight\n\n___\n\n{{cart}}\n",
    }
    for where, page in top.items():
        out, regions = expand(page, includes)
        assert "Classic Smash: 1" in out and len(regions) == 1, where
    print("  ✓  an include in a list or a ::: row stays as written, and check warns")


def test_a_handler_that_raises_is_said_in_the_digest():
    shop = Shop()
    served = Served(Conversation(_kit(), includes=_includes(shop)))
    conversation = served.conversation

    def broken(_params: dict[str, str]) -> set[str]:
        raise RuntimeError("the shop's database is down at db.internal:5432")

    conversation.handlers["cart-add"] = broken
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            mid = served.call(conversation.send(PAGE))
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 2)
            with contextlib.redirect_stderr(io.StringIO()):
                ws.send(json.dumps({"t": "e", "m": mid, "x": 1, "q": 1}))
                event = served.next_event()
            assert isinstance(event, Verified), "the agent did not hear the click"
            (line,) = conversation.take_handled()
            assert "cart-add" in line and "RuntimeError" in line, line
            assert "failed" in line and "db.internal" not in line, line
    finally:
        served.stop()
    print("  ✓  a handler that raises: the agent hears the click and why it is theirs")


def test_a_handled_click_is_released_in_any_state():
    from md2ui.wire_frames import decode_server

    shop = Shop()
    served = Served(Conversation(_kit(), includes=_includes(shop)))
    conversation = served.conversation
    conversation.handlers["cart-add"] = shop.add
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            served.call(conversation.send(PAGE))
        for q, state in ((1, "w"), (2, "i")):
            served.call(conversation.set_state(state))
            with (
                connect(served.url, compression=None) as ws,
                connect(served.url, compression=None) as other,
            ):
                for each in (ws, other):
                    each.send('{"t":"h","v":1}')
                    _frames(each, 3)  # the page, its end, the state
                shown = conversation.latest
                ws.send(json.dumps({"t": "e", "m": shown, "x": 1, "q": q}))
                _message, _end, said = _frames(ws, 3)
                assert said == {"t": "s", "s": state, "u": [q]}, said
                assert decode_server(json.dumps(said)) == said
                _m, _e, told = _frames(other, 3)
                assert told == {"t": "s", "s": state}, told
    finally:
        served.stop()
    print("  ✓  a handled click is released (u) in w and i, to its own connection only")


def test_a_streamed_include_line_is_said_not_drawn():
    from md2ui.includes import unexpanded

    shop = Shop()
    conversation = Conversation(_kit(), includes=_includes(shop))
    with contextlib.redirect_stdout(io.StringIO()):
        mid = asyncio.run(conversation.stream(["# Hi\n\n", "{{cart}}\n"]))
    shown = conversation.log.markdown(mid)
    assert "{{cart}}" in shown, shown
    (issue,) = unexpanded(shown, conversation.includes)
    assert (issue["level"], issue["code"]) == ("warning", "streamed-include"), issue
    assert "stream" in issue["message"] and "whole" in issue["message"], issue
    print("  ✓  a streamed page's include line is warned about, as streamed")


def test_going_back_redraws_the_includes_and_says_so():
    from md2ui import mcp_demo

    with tempfile.TemporaryDirectory() as folder:
        server, demo = mcp_demo.build_demo_server(
            _static_theme(Path(folder)), launch_window=False
        )
        count = [1]
        demo.includes.add("count", "a count", lambda _args: f"Count: {count[0]}")

        def call(name: str, **arguments: Any) -> dict:
            with contextlib.redirect_stdout(io.StringIO()):
                result: Any = asyncio.run(server.call_tool(name, arguments))
            return result.structured_content or json.loads(_text(result))

        try:
            page = "# Hi\n\n{{count}}\n\n[Go](agent:go)\n"
            first = call("show", markdown=page, wait_seconds=0)
            call("show", markdown="# Elsewhere\n", wait_seconds=0)
            count[0] = 2
            back = call("show", message_id=first["message_id"], wait_seconds=0)
            assert back["redrawn"] == ["count"], back
            read = call("showing")
            assert "Count: 2" in read["markdown"], read
            assert read["source"] == page, read
            log = demo.started().conversation.log
            assert len(log.pages.includes.regions(read["message_id"])) == 1
            plain = call("show", markdown="# Plain\n", wait_seconds=0)
            again = call("show", message_id=plain["message_id"], wait_seconds=0)
            assert "redrawn" not in again, again
        finally:
            demo.close()
    print("  ✓  going back draws the page's includes from the data now, and says so")


def test_an_unknown_include_without_includes_is_a_warning():
    from md2ui.includes import Includes, unexpanded

    page = "# Templates\n\n{{name}}\n"
    for none in (None, Includes()):
        (issue,) = unexpanded(page, none)
        assert (issue["level"], issue["code"]) == ("warning", "unknown-include"), issue
    (issue,) = unexpanded(page, _includes(Shop()))
    assert issue["level"] == "error", issue
    server = mcp_server.build_server(None)
    with contextlib.redirect_stdout(io.StringIO()):
        said = _text(asyncio.run(server.call_tool("check", {"markdown": page})))
    assert "unknown-include" in said and '"error"' not in said, said
    print(
        "  ✓  an unknown include is a warning on a server with none, an error with some"
    )


@contextlib.contextmanager
def _app_policy():
    """build_server turns fetching off for the process; the modules run after
    this one draw as the app does (as mcp_server_tests restores it)."""
    try:
        yield
    finally:
        POLICY.remote, VIEW.placeholder_images = True, False


@contextlib.contextmanager
def _argv(argv: list[str]):
    saved, sys.argv = sys.argv, argv
    try:
        yield
    finally:
        sys.argv = saved


def _failing_includes(shop: Shop, down: list[bool], failure: str = ""):
    """`{{cart}}` drawn while the shop is up, with *failure* as its failure
    line; `{{menu}}`, which always fails, with its own; `{{order …}}` with none."""

    def cart(args: Any) -> str:
        if down[0]:
            raise RuntimeError("the shop's database is down at db.internal:5432")
        return shop.cart(args)

    def menu(_args: Any) -> str:
        raise KeyError("db.internal:5432")

    includes = _includes(shop)
    includes.add("cart", "the cart page", cart, failure=failure)
    includes.add("menu", "the menu", menu, failure="  La carte   est indisponible. ")
    return includes


def test_a_failed_include_is_sent_as_its_failure_line_or_nothing():
    from md2ui.advice import Reading, reply_issues
    from md2ui.includes import UNKNOWN

    page = (
        '# Hi\n\n{{menu}}\n\n{{basket}}\n\n{{order "unclosed}}\n\n'
        "[Checkout](agent:checkout)\n"
    )
    conversation = Conversation(_kit(), includes=_failing_includes(Shop(), [False]))
    with (
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        mid = asyncio.run(conversation.send(page))
    log = conversation.log
    shown = log.markdown(mid)
    assert "{{" not in shown, shown
    assert "\n_La carte est indisponible._\n" in shown, shown
    # The unknown name and the unread args registered no line: they draw none.
    assert shown == "# Hi\n\n_La carte est indisponible._\n\n\n\n" + (
        "[Checkout](agent:checkout)\n"
    ), shown
    regions = log.pages.includes.regions(mid)
    assert [r.failed for r in regions] == ["KeyError", UNKNOWN, "ValueError"], regions
    assert [r.end - r.start for r in regions] == [1, 0, 0], regions
    assert log.pages.includes.source(mid, shown) == page, "the source is not kept"
    issues = reply_issues(shown, None, None, Reading(), conversation.includes, regions)
    errors = [i for i in issues if i["code"] == "unknown-include"]
    assert [i["level"] for i in errors] == ["error"] * 3, errors
    assert "`{{menu}}`" in errors[0]["message"] and "KeyError" in errors[0]["message"]
    assert "`basket`" in errors[1]["message"], errors[1]
    assert not any("db.internal" in i["message"] for i in errors), errors
    print(
        "  ✓  a failed include is sent as its failure line or nothing; check names it"
    )


def test_a_failed_redraw_draws_its_failure_line_or_nothing_and_recovers():
    for failure, drawn_as in (
        ("Le panier n'a pas pu s'afficher.", "\n_Le panier n'a pas pu s'afficher._\n"),
        ("", "# Cart\n\n\n[Retry]"),  # an empty region
    ):
        _failed_redraw(failure, drawn_as)
    print("  ✓  a redraw that fails draws its failure line or nothing, then recovers")


def _failed_redraw(failure: str, drawn_as: str) -> None:
    shop, down = Shop(), [False]
    includes = _failing_includes(shop, down, failure)
    served = Served(Conversation(_kit(), includes=includes))
    conversation = served.conversation
    conversation.handlers["cart-add"] = shop.add
    page = "# Cart\n\n{{cart}}\n\n[Retry](agent:cart-add?id=smash)\n"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            mid = served.call(conversation.send(page))
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 2)  # the page, its end
            down[0] = True
            with contextlib.redirect_stderr(io.StringIO()):
                ws.send(json.dumps({"t": "e", "m": mid, "x": 1, "q": 1}))
                message, _end, _state = _frames(ws, 3)
            drawn = message["md"]
            assert "{{" not in drawn and "Smash" not in drawn, drawn
            assert drawn_as in drawn, drawn
            assert "[Retry](agent:cart-add?id=smash)" in drawn, drawn
            (region,) = conversation.log.pages.includes.regions(message["m"])
            assert region.failed == "RuntimeError", region
            (line,) = conversation.take_handled()
            assert "`{{cart}}` (RuntimeError) could not be drawn" in line, line
            assert "db.internal" not in line, line
            down[0] = False  # the data recovers: the region is still the include's
            ws.send(json.dumps({"t": "e", "m": message["m"], "x": 0, "q": 2}))
            message, _end, _state = _frames(ws, 3)
            assert "Classic Smash: 3" in message["md"], message["md"]
            assert "pas pu" not in message["md"], message["md"]
            (line,) = conversation.take_handled()
            assert "could not be drawn" not in line, line
    finally:
        served.stop()


def test_a_static_include_may_name_its_failure_line():
    from md2ui.includes import expand, static_includes

    with tempfile.TemporaryDirectory() as folder:
        theme = _static_theme(Path(folder))
        (Path(folder) / "includes" / "order.md").write_text(
            "---\ndescription: one order\nargs: <id>\nfailure: No order here.\n---\n"
            "Order: shipped\n",
            encoding="utf-8",
        )
        includes = static_includes(theme)
    with contextlib.redirect_stderr(io.StringIO()):
        out, (region,) = expand('# Hi\n\n{{order "BS-1}}\n', includes)
    assert out == "# Hi\n\n_No order here._\n", out
    assert region.failed == "ValueError", region
    print("  ✓  a static include may name its failure line in its frontmatter")


def _restoring(test):
    def run() -> None:
        with _app_policy():
            test()

    run.__name__ = test.__name__
    return run


TESTS = [
    test_only_a_lone_line_is_an_include,
    test_send_expands_before_recording_and_keeps_the_source,
    test_a_handled_click_redraws_its_include_and_never_wakes_the_agent,
    test_a_handler_that_declines_leaves_the_click_to_the_agent,
    test_a_handler_that_raises_leaves_the_click_to_the_agent,
    _restoring(test_the_authoring_server_checks_the_expanded_page),
    _restoring(test_a_server_without_includes_says_so_and_does_not_name_them),
    _restoring(test_the_demo_shows_the_expansion_and_hands_over_handled_clicks),
    test_the_eval_runner_takes_a_suite_by_its_path,
    test_an_agent_edit_touching_an_include_is_refused,
    test_an_agent_edit_outside_an_include_keeps_it,
    test_an_include_inside_a_list_or_a_row_is_not_expanded_and_warned,
    test_a_handler_that_raises_is_said_in_the_digest,
    test_a_handled_click_is_released_in_any_state,
    test_a_streamed_include_line_is_said_not_drawn,
    _restoring(test_going_back_redraws_the_includes_and_says_so),
    _restoring(test_an_unknown_include_without_includes_is_a_warning),
    test_a_failed_include_is_sent_as_its_failure_line_or_nothing,
    test_a_failed_redraw_draws_its_failure_line_or_nothing_and_recovers,
    test_a_static_include_may_name_its_failure_line,
]

if __name__ == "__main__":
    for test in TESTS:
        test()
