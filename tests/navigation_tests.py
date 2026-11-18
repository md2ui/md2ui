"""
A backend answers a tap with a page of its includes (ADR-614, proposed).

Pinned here:

  * a handler returning ``Show(page)``, every non-blank line an include line, is
    answered with a NEW message and a new page (an ``m`` with no ``r``), then the
    button's release (``u``); the click is never queued for the agent, and one
    digest line says what the backend showed and the new id;
  * the page left keeps its id (``MessageLog.head`` does not resolve it to the
    backend's page) and its row in ``history``; the backend's page is marked
    ``shown_by: backend`` there, and its ``source`` is its include lines;
  * the burger shop's four navigation taps (Sides, Shakes, View cart, Keep
    shopping) are answered with no agent turn;
  * a line that is not an include, an unknown name, args that do not read or an
    expander that raises sends nothing: the click is the agent's, as a handler
    that raises is (ADR-612), with a digest line naming the error's class;
  * the feeds of the page left end with it, and the digest line names them;
  * while the backend's page is shown, the agent's ``mark``, ``set_slider``,
    ``set_bar`` and ``patch`` of the page left are refused, naming the page shown;
    once the agent shows a page of its own, edits go as before;
  * the demo hands the digest over on ``show``, ``mark`` and ``patch`` results.

Run with: uv run python tests/navigation_tests.py
"""

import asyncio
import contextlib
import io
import json
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from websockets.sync.client import connect

from md2ui import session
from md2ui.includes import Includes
from md2ui.pipeline.render_settings import VIEW
from md2ui.utils.fetch_policy import POLICY
from md2ui.wire import FrameError, Verified
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


def _shop_includes() -> Includes:
    """The shop's pages: a menu by category, with its tabs, and the cart."""
    tabs = (
        "[🍟 Sides](agent:catalog?category=sides) "
        "[🥤 Shakes](agent:catalog?category=shakes) [View cart](agent:cart)"
    )

    def menu(args: Any) -> str:
        category = args.named.get("category", "all")
        if category == "fish":
            raise LookupError("no such category in db.internal")
        return (
            f"## Menu: {category}\n\n{tabs}\n\n- Fries [Add](agent:cart-add?id=fries)"
        )

    includes = Includes()
    includes.add("menu", "the menu, by category", menu, "category=…")
    includes.add(
        "cart",
        "the cart",
        lambda _args: "## Cart\n\nFries: 1\n\n[Checkout](agent:checkout) "
        "[Keep shopping](agent:catalog)",
    )
    return includes


def _shop_handlers(conversation: Conversation) -> None:
    from md2ui.wire_includes import Show

    def catalog(params: dict[str, str]) -> Any:
        category = params.get("category")
        return Show(f"{{{{menu category={category}}}}}" if category else "{{menu}}")

    conversation.handlers["catalog"] = catalog
    conversation.handlers["cart"] = lambda _params: Show("{{cart}}")


AGENT_PAGE = (
    "# Burger Shop\n\nWhat are you craving?\n\n"
    "[🍟 Sides](agent:catalog?category=sides) [Ask me](agent:ask)\n\n"
    "- [ ] Extra napkins\n"
)


def _tap(conversation: Conversation, label: str, q: int) -> Any:
    """The user taps the target labelled *label* on the page shown."""
    shown = conversation.latest
    assert shown is not None
    labels = [t.action and t.action.label for t in conversation.log.targets(shown)]
    frame = {"t": "e", "m": shown, "x": labels.index(label), "q": q}
    return asyncio.run(conversation.receive(frame, "p"))


def _frames(ws, n: int) -> list[dict]:
    return [json.loads(ws.recv(timeout=5)) for _ in range(n)]


def test_a_handler_shows_a_new_page_and_releases_the_button():
    served = Served(Conversation(_kit(), includes=_shop_includes()))
    conversation = served.conversation
    _shop_handlers(conversation)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            mid = served.call(conversation.send(AGENT_PAGE))
            served.call(conversation.set_state("l"))
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 3)  # the page, its end, the state
            ws.send(json.dumps({"t": "e", "m": mid, "x": 0, "q": 1}))
            message, end, state = _frames(ws, 3)
            assert "r" not in message, "the backend's page replaced the agent's"
            assert message["md"].startswith("## Menu: sides"), message["md"]
            assert (end["t"], state) == ("z", {"t": "s", "s": "l", "u": [1]}), state
            assert served.next_event(timeout=0.3) is None, "the agent was woken"
        new = conversation.latest
        assert new is not None and new != mid
        (line,) = conversation.take_handled()
        assert line == (
            'User chose "🍟 Sides": catalog {category: sides} (message '
            f"{mid}): the backend showed {{{{menu category=sides}}}} (now message "
            f"{new})"
        ), line
        log = conversation.log
        assert log.head(mid) == mid and log.pages.latest(mid) == mid, "id moved"
        assert log.markdown(mid).startswith("# Burger Shop"), "the agent's page changed"
        assert log.pages.includes.source(new, log.markdown(new)) == (
            "{{menu category=sides}}"
        )
        rows = {r["message_id"]: r for r in log.pages.listing()}
        assert rows[new]["shown_by"] == "backend" and "shown_by" not in rows[mid], rows
    finally:
        served.stop()
    print("  ✓  Show: a new page (no r), released, never queued, one digest line")


def test_the_shops_four_navigation_taps_cost_no_turn():
    conversation = Conversation(_kit(), includes=_shop_includes())
    _shop_handlers(conversation)
    with contextlib.redirect_stdout(io.StringIO()):
        asyncio.run(conversation.send(AGENT_PAGE))
    sources = []
    for q, label in enumerate(("🍟 Sides", "🥤 Shakes", "View cart", "Keep shopping")):
        result = _tap(conversation, label, q + 1)
        assert isinstance(result, Verified), (label, result)
        shown = conversation.latest
        assert shown is not None
        log = conversation.log
        sources.append(log.pages.includes.source(shown, log.markdown(shown)))
    assert conversation.events.qsize() == 0, "a navigation tap woke the agent"
    assert sources == [
        "{{menu category=sides}}",
        "{{menu category=shakes}}",
        "{{cart}}",
        "{{menu}}",
    ], sources
    assert len(conversation.take_handled()) == 4
    print("  ✓  Sides, Shakes, View cart, Keep shopping: answered, no agent turn")


def test_a_page_the_server_cannot_draw_is_the_agents_click():
    from md2ui.wire_includes import Show

    pages = {
        "a line that is not an include": "## Sides\n\n{{menu category=sides}}",
        "an unknown name": "{{basket}}",
        "args that do not read": '{{menu category="sides}}',
        "an expander that raises": "{{menu category=fish}}",
        "nothing": "\n\n",
    }
    for why, page in pages.items():
        conversation = Conversation(_kit(), includes=_shop_includes())
        conversation.handlers["catalog"] = lambda _params, page=page: Show(page)
        with contextlib.redirect_stdout(io.StringIO()):
            mid = asyncio.run(conversation.send(AGENT_PAGE))
        with contextlib.redirect_stderr(io.StringIO()):
            _tap(conversation, "🍟 Sides", 1)
        assert conversation.latest == mid, f"{why}: something was sent"
        assert conversation.log.markdown("c2") == "", f"{why}: a page was recorded"
        event = conversation.events.get_nowait()
        assert isinstance(event, Verified), why
        (line,) = conversation.take_handled()
        assert "failed on catalog (PageNotDrawn); the click is yours" in line, line
        assert "db.internal" not in line, line
    print("  ✓  a Show the server cannot draw sends nothing: the click is the agent's")


def test_the_page_left_ends_its_feeds_and_the_digest_names_them():
    conversation = Conversation(_kit(), includes=_shop_includes())
    _shop_handlers(conversation)
    page = "# Order\n\nCooking: 40%\n\n[🍟 Sides](agent:catalog?category=sides)\n"

    async def run() -> tuple[Any, list[str]]:
        mid = await conversation.send(page)
        feed = await conversation.feeds.open(mid, None, None)
        frame = {"t": "e", "m": mid, "x": 0, "q": 1}
        await conversation.receive(frame, "p")
        conversation.feeds.stop()
        return feed, conversation.take_handled()

    with contextlib.redirect_stdout(io.StringIO()):
        feed, (line,) = asyncio.run(run())
    assert feed.ended == "replaced", feed.ended
    assert line.endswith(f", ending feed {feed.id}"), line
    assert conversation.events.qsize() == 0, "an untold end was queued"
    print("  ✓  the page left ends its feeds, named in the digest line")


def test_an_edit_of_the_page_left_is_refused_while_the_backend_page_shows():
    conversation = Conversation(_kit(), includes=_shop_includes())
    _shop_handlers(conversation)
    with contextlib.redirect_stdout(io.StringIO()):
        mid = asyncio.run(conversation.send(AGENT_PAGE))
    _tap(conversation, "🍟 Sides", 1)
    shown = conversation.latest
    assert shown is not None
    edits = {
        "mark": conversation.mark(mid, 2, "checked"),
        "set_slider": conversation.set_slider(mid, 2, 1.0),
        "set_bar": conversation.set_bar(mid, "Cooking", 1.0),
        "patch": conversation.patch(mid, "Hungry?", section="Burger Shop"),
    }
    for name, edit in edits.items():
        try:
            asyncio.run(edit)
        except FrameError as exc:
            assert exc.code == "bad_target", (name, exc.code)
            assert f"the user is on {shown}" in str(exc), str(exc)
            assert f"show(message_id='{mid}')" in str(exc), str(exc)
        else:
            raise AssertionError(f"{name} of the page left was not refused")
        assert conversation.latest == shown, f"{name} pulled the user back"
    # The agent's own page puts the rule away: an edit elsewhere goes as before.
    with contextlib.redirect_stdout(io.StringIO()):
        asyncio.run(conversation.send("# Elsewhere\n"))
        new = asyncio.run(conversation.mark(mid, 2, "checked"))
    assert "- [x] Extra napkins" in conversation.log.markdown(new)
    print("  ✓  mark/patch of the page left are refused while the backend's shows")


def test_the_demo_hands_the_digest_to_show_mark_and_patch():
    from md2ui import mcp_demo
    from md2ui.wire_includes import Show

    with tempfile.TemporaryDirectory() as folder:
        theme = Path(folder) / "THEME.md"
        theme.write_text(TEST_THEME.read_text(encoding="utf-8"), encoding="utf-8")
        server, demo = mcp_demo.build_demo_server(theme, launch_window=False)
        demo.includes.add("menu", "the menu", lambda _a: "## Menu\n\n- Fries")

        def call(name: str, **arguments: Any) -> dict:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    result: Any = asyncio.run(server.call_tool(name, arguments))
            except ToolError as exc:
                return {"error": str(exc)}
            return result.structured_content or json.loads(result.content[0].text)

        try:
            page = "# Hi\n\n[Menu](agent:catalog) [Ask](agent:ask)\n\n- [ ] Napkins\n"
            call("show", markdown=page, wait_seconds=0)
            served = demo.started()
            conversation = served.conversation
            conversation.handlers["catalog"] = lambda _params: Show("{{menu}}")
            conversation.handlers["ask"] = lambda _params: set()  # answered, as is
            for q, (tool, arguments) in enumerate(
                (
                    ("show", {"markdown": page}),
                    ("mark", {"x": 2, "state": "checked"}),
                    ("patch", {"section": "Hi", "markdown": "Hello"}),
                )
            ):
                shown = conversation.latest
                frame = {"t": "e", "m": shown, "x": 1, "q": q + 1}
                served.call(conversation.receive(frame, ""))
                if tool != "show":
                    arguments |= {"message_id": conversation.latest}
                result = call(tool, wait_seconds=0, **arguments)
                (line,) = result["handled"]
                assert line.startswith('User chose "Ask"'), (tool, line)
            left = call("show", markdown=page, wait_seconds=0)["message_id"]
            frame = {"t": "e", "m": left, "x": 0, "q": 9}
            served.call(conversation.receive(frame, ""))
            refused = call(
                "mark", message_id=left, x=2, state="checked", wait_seconds=0
            )
            assert "a page the backend showed" in refused["error"], refused
        finally:
            demo.close()
    print("  ✓  show, mark and patch hand over the digest")


@contextlib.contextmanager
def _app_policy():
    """build_demo_server turns fetching off for the process; restore it."""
    try:
        yield
    finally:
        POLICY.remote, VIEW.placeholder_images = True, False


def _restoring(test):
    def run() -> None:
        with _app_policy():
            test()

    run.__name__ = test.__name__
    return run


TESTS = [
    test_a_handler_shows_a_new_page_and_releases_the_button,
    test_the_shops_four_navigation_taps_cost_no_turn,
    test_a_page_the_server_cannot_draw_is_the_agents_click,
    test_the_page_left_ends_its_feeds_and_the_digest_names_them,
    test_an_edit_of_the_page_left_is_refused_while_the_backend_page_shows,
    _restoring(test_the_demo_hands_the_digest_to_show_mark_and_patch),
]

if __name__ == "__main__":
    for test in TESTS:
        test()
