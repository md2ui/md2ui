"""
A backend redraws its includes on the page shown when its data changes, with no
click (ADR-612): ``Conversation.changed(names)``.

Pinned here:

  * a redraw sends ONE replacement (``r``) of the page shown, in which only the
    regions of the named includes changed: the agent's words and every other
    include are as they were; no state frame follows, as no click is answered;
  * no frame, no new id and no digest line when the page shown draws none of the
    names, draws them as before, has no includes, or a message is streaming;
  * a handled tap's replacement under a stream leaves the stream streaming: a
    window joining after it is sent the stream whole, its hash checks out;
  * the agent's id resolves through the redraw (``MessageLog.head``), so its
    ``mark`` lands on the redrawn page, and the region is carried through the mark;
  * the agent hears one digest line, ``the backend redrew {{cart}} (data changed;
    now message …)``; consecutive redraws are one line naming the last message,
    a handled click between them keeps its own line; an include that cannot be
    drawn draws its failure line and the line says so;
  * with a feed running on the page, a redraw and a tick both land: the tick
    writes its value on the redrawn page, and the feed runs on;
  * only the page shown is redrawn: after the agent sends another page, or the
    backend shows one of its includes (ADR-614), the page left is not.

Run with: uv run python tests/backend_redraw_tests.py
"""

import asyncio
import contextlib
import io
import json
from typing import Any

from websockets.sync.client import connect

from md2ui import session
from md2ui.includes import Includes
from md2ui.wire import md_hash
from md2ui.wire_feeds import Feeds
from md2ui.wire_server import Conversation, Served

_MODELS = None


def _kit():
    global _MODELS
    if _MODELS is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _MODELS = session.load_grouping_kit()
    return _MODELS


class Shop:
    """The burger shop's data: a cart and an order that moves on its own."""

    def __init__(self) -> None:
        self.count = 1
        self.stage = "Preparing"
        self.down = False

    def cart(self, _args: Any) -> str:
        return f"Cart: {self.count} items"

    def order(self, args: Any) -> str:
        if self.down:
            raise RuntimeError("the kitchen's database is down at db.internal")
        cancel = "\n\n[Cancel order](agent:cancel)" if self.stage == "Preparing" else ""
        return f"## Order {args.words[0]}\n\nStatus: `{self.stage}`{cancel}"


def _conversation(shop: Shop) -> Conversation:
    includes = Includes()
    includes.add("cart", "the cart badge", shop.cart)
    includes.add(
        "order", "one order", shop.order, "<order id>", failure="Tracking is down."
    )
    includes.add("menu", "the menu", lambda _a: "## Menu\n\n- Classic Smash")
    return Conversation(_kit(), includes=includes)


PAGE = (
    "# Thanks!\n\nYour order is in.\n\n{{cart}}\n\n{{order BS-1}}\n\n"
    "[Track](agent:track)\n"
)


def _send(conversation: Conversation, page: str = PAGE) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        return asyncio.run(conversation.send(page))


def test_a_redraw_sends_one_replacement_of_only_the_changed_regions():
    shop = Shop()
    served = Served(_conversation(shop))
    conversation = served.conversation
    try:
        mid = _send_served(served)
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 3)  # the page, its end, the state
            before = conversation.log.markdown(mid)
            shop.stage = "On the way"
            new = served.call(conversation.changed({"cart", "order"}))
            message, end = _frames(ws, 2)
            assert (message["r"], message["m"], end["t"]) == (mid, new, "z"), message
            after = message["md"]
            assert after == conversation.log.markdown(new), "sent is not recorded"
            expected = before.replace("Preparing", "On the way").replace(
                "\n\n[Cancel order](agent:cancel)", ""
            )
            assert after == expected, after
            try:
                extra = ws.recv(timeout=0.3)
            except TimeoutError:
                extra = None
            assert extra is None, f"a frame beyond the replacement: {extra}"
            assert conversation.state == "l"
            src = conversation.log.pages.includes.source(new, after)
            assert src == PAGE, src
    finally:
        served.stop()
    print("  ✓  a redraw: one r, only the changed regions, no state frame")


def _send_served(served: Served) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        mid = served.call(served.conversation.send(PAGE))
        served.call(served.conversation.set_state("l"))
    return mid


def _frames(ws, n: int) -> list[dict]:
    return [json.loads(ws.recv(timeout=5)) for _ in range(n)]


def test_no_frame_when_nothing_on_the_page_shown_changed():
    shop = Shop()
    conversation = _conversation(shop)
    mid = _send(conversation)

    async def run() -> list:
        return [
            await conversation.changed({"cart"}),  # the data did not move
            await conversation.changed({"menu"}),  # not on the page shown
            await conversation.changed(set()),
        ]

    assert asyncio.run(run()) == [None, None, None]
    plain = _send(conversation, "# Hello\n\nNo includes here.\n")
    shop.count = 2
    assert asyncio.run(conversation.changed({"cart"})) is None, "a page without it"
    assert conversation.latest == plain and conversation.log.head(mid) == mid
    assert conversation.take_handled() == [], "a line for nothing drawn"
    assert conversation.log.markdown(f"c{int(plain[1:]) + 1}") == "", "an id was used"
    print("  ✓  no frame, id or digest line when the page shown draws nothing new")


def test_a_redraw_while_a_message_streams_sends_nothing():
    shop = Shop()
    conversation = _conversation(shop)
    _send(conversation)
    seen: list = []

    async def run() -> str:
        async def chunks():
            yield "Thinking"
            shop.count = 5
            seen.append(await conversation.changed({"cart"}))
            yield " about it."

        return await conversation.stream(chunks())

    with contextlib.redirect_stdout(io.StringIO()):
        streamed = asyncio.run(run())
    assert seen == [None], seen
    assert conversation.latest == streamed and conversation.take_handled() == []
    print("  ✓  while a message streams, the stream is the page shown: no redraw")


def test_a_window_joining_after_a_handled_tap_mid_stream_gets_the_stream_whole():
    """A joins before the stream, C mid-stream before the tap, B after it: each
    assembles the streamed message whole, and its hash checks out."""
    shop = Shop()
    served = Served(_conversation(shop))
    conversation = served.conversation

    def track(_params: Any) -> set[str]:
        shop.count += 1
        return {"cart"}

    conversation.handlers["track"] = track
    windows: dict[str, Any] = {}
    got: dict[str, list[dict]] = {}
    stack = contextlib.ExitStack()

    def join(name: str) -> None:  # returns once the server has sent the join
        windows[name] = stack.enter_context(connect(served.url, compression=None))
        windows[name].send('{"t":"h","v":1}')
        got[name] = []
        while not got[name] or got[name][-1]["t"] != "s":
            got[name].append(json.loads(windows[name].recv(timeout=5)))

    try:
        page = _send_served(served)
        x = next(
            i
            for i, target in enumerate(conversation.log.targets(page))
            if target.action and target.action.action == "track"
        )
        join("A")

        async def chunks():
            yield "Thinking"
            await asyncio.to_thread(join, "C")
            tap = {"t": "e", "m": page, "x": x, "q": 1, "a": "track"}
            await conversation.receive(tap, "")
            await asyncio.to_thread(join, "B")
            yield " about"
            yield " it."

        with contextlib.redirect_stdout(io.StringIO()):
            streamed = served.call(conversation.stream(chunks()))
        assert conversation.take_handled(), "the tap was not handled"
        for name, ws in windows.items():
            while got[name][-1].get("m") != streamed or got[name][-1]["t"] != "z":
                got[name].append(json.loads(ws.recv(timeout=5)))
            ours = [f for f in got[name] if f.get("m") == streamed]
            assert ours[0]["t"] == "m", (name, "a tail with no m", ours)
            assembled = "".join(f["md"] for f in ours if f["t"] in ("m", "d"))
            assert assembled == "Thinking about it.", (name, assembled)
            assert md_hash(assembled) == ours[-1]["h"], (name, "hash mismatch")
    finally:
        stack.close()
        served.stop()
    print("  ✓  a window joining after a handled tap mid-stream gets the stream whole")


def test_the_agents_id_survives_a_redraw():
    shop = Shop()
    conversation = _conversation(shop)
    mid = _send(conversation)
    shop.count = 2
    new = asyncio.run(conversation.changed({"cart"}))
    assert new is not None and conversation.log.head(mid) == new
    with contextlib.redirect_stdout(io.StringIO()):
        marked = asyncio.run(conversation.mark(mid, 1, "disabled"))
    page = conversation.log.markdown(marked)
    assert "Cart: 2 items" in page and "~~[Track](agent:track)~~" in page, page
    shop.count = 3
    again = asyncio.run(conversation.changed({"cart"}))
    assert again is not None and "Cart: 3 items" in conversation.log.markdown(again)
    assert "~~[Track](agent:track)~~" in conversation.log.markdown(again)
    print("  ✓  the agent's id resolves through a redraw; its mark keeps the region")


def test_the_digest_says_what_the_backend_redrew():
    shop = Shop()
    conversation = _conversation(shop)
    mid = _send(conversation)
    shop.count = 2
    first = asyncio.run(conversation.changed({"cart", "order"}))
    assert conversation.take_handled() == [
        f"the backend redrew {{{{cart}}}} (data changed; now message {first})"
    ], "only the include that drew differently is named"
    shop.count, shop.stage = 3, "On the way"
    asyncio.run(conversation.changed({"cart"}))
    last = asyncio.run(conversation.changed({"order"}))
    (line,) = conversation.take_handled()
    assert line == (
        f"the backend redrew {{{{cart}}}}, {{{{order}}}} (data changed; now message "
        f"{last})"
    ), line
    # A handled click between two redraws keeps its own line, in order.
    conversation.handlers["track"] = lambda _p: {"cart"}
    shop.count = 4
    asyncio.run(conversation.changed({"cart"}))

    async def tap() -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            frame = {"t": "e", "m": conversation.latest, "x": 0, "q": 1}
            await conversation.receive(frame, "p")

    asyncio.run(tap())
    shop.down = True
    with contextlib.redirect_stderr(io.StringIO()) as said:
        failed = asyncio.run(conversation.changed({"order"}))
    lines = conversation.take_handled()
    assert len(lines) == 3, lines
    assert lines[0].startswith("the backend redrew {{cart}}"), lines
    assert "the backend answered it" in lines[1], lines
    assert lines[2] == (
        "the backend redrew {{order}} (data changed; `{{order BS-1}}` "
        f"(RuntimeError) could not be drawn; now message {failed})"
    ), lines[2]
    assert "db.internal" not in lines[2] and "db.internal" in said.getvalue()
    page = conversation.log.markdown(failed or "")
    assert "_Tracking is down._" in page and "Status:" not in page, page
    assert conversation.log.head(mid) == failed
    print("  ✓  one digest line per run of redraws, failures named by class")


def test_a_redraw_and_a_feed_tick_both_land():
    shop = Shop()
    conversation = _conversation(shop)
    conversation.feeds = Feeds(conversation, tick=(3600.0, 3600.0))
    page = "# Order\n\nCooking: 40%\n\n{{cart}}\n"

    async def run() -> tuple[str, str]:
        mid = await conversation.send(page)
        feed = await conversation.feeds.open(mid, None, None)
        status, _ = await conversation.feeds.post(feed.token, "Cooking: 60%")
        assert status == 200, status
        shop.count = 2
        redrawn = await conversation.changed({"cart"})
        assert redrawn is not None
        async with feed.lock:
            await conversation.feeds._tick(feed)
        ticked = conversation.latest or ""
        shop.count = 3
        again = await conversation.changed({"cart"})
        assert again is not None
        assert feed.ended is None, f"the feed ended: {feed.ended}"
        conversation.feeds.stop()
        return conversation.log.markdown(ticked), conversation.log.markdown(again)

    with contextlib.redirect_stdout(io.StringIO()):
        ticked, again = asyncio.run(run())
    assert "Cooking: 60%" in ticked and "Cart: 2 items" in ticked, ticked
    assert "Cooking: 60%" in again and "Cart: 3 items" in again, again
    assert conversation.events.qsize() == 0, "a redraw woke the agent"
    print("  ✓  a redraw and a feed's tick on one page: both land, the feed runs on")


def test_only_the_page_shown_is_redrawn():
    from md2ui.wire_includes import Show

    shop = Shop()
    conversation = _conversation(shop)
    mid = _send(conversation)
    other = _send(conversation, "# Menu\n\n{{menu}}\n\n[Order](agent:menu-order)\n")
    shop.count = 2
    assert asyncio.run(conversation.changed({"cart"})) is None
    assert conversation.log.head(mid) == mid, "the page left was redrawn"
    # A page the backend showed (ADR-614) is the page shown: it is redrawn.
    conversation.handlers["menu-order"] = lambda _p: Show("{{cart}}")

    async def tap() -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            await conversation.receive({"t": "e", "m": other, "x": 0, "q": 1}, "p")

    asyncio.run(tap())
    shown = conversation.latest
    assert shown != other and "Cart: 2 items" in conversation.log.markdown(shown or "")
    shop.count = 3
    new = asyncio.run(conversation.changed({"cart"}))
    assert new is not None and conversation.log.markdown(new) == "Cart: 3 items"
    assert conversation.log.head(other) == other
    print("  ✓  only the page shown is redrawn, a backend's page included")


TESTS = [
    test_a_redraw_sends_one_replacement_of_only_the_changed_regions,
    test_no_frame_when_nothing_on_the_page_shown_changed,
    test_a_redraw_while_a_message_streams_sends_nothing,
    test_a_window_joining_after_a_handled_tap_mid_stream_gets_the_stream_whole,
    test_the_agents_id_survives_a_redraw,
    test_the_digest_says_what_the_backend_redrew,
    test_a_redraw_and_a_feed_tick_both_land,
    test_only_the_page_shown_is_redrawn,
]


if __name__ == "__main__":
    for test in TESTS:
        test()
