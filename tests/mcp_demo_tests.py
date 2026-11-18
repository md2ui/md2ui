"""
Unit tests for the demo shell (ADR-602): Claude shows a response, the user
clicks, Claude hears it, and marks state — over the real localhost binding.

The window is not launched (``launch_window=False``); a ``WireClient`` — the very
client the app runs — stands in for it.

Pinned here:

  * the demo offers the authoring six plus ``show``, ``wait_for_event``, ``mark``,
    and a client may read ``show`` and ``mark`` as non-destructive and local;
  * ``show`` returns the message id, what comes back to the agent by ``x``, a
    digest of how the page grouped, and the authoring issues;
  * a click in the client reaches ``wait_for_event`` as the wire's sentence;
  * ``mark`` updates the client in place (``r``), and a bad state is a tool error;
  * ``wait_for_event`` returns on its timeout rather than hanging, and tells
    the agent to wait again: a session holds the turn;
  * ``show`` and ``mark`` listen after replying, and a ``show`` hands over what
    queued while nobody listened; an answer with issues is not listened to,
    unless every one is a ``note``;
  * told ``wait_seconds`` 0, they say they are not listening when the page offers
    something, and stay quiet on a page that offers nothing -- except a window's
    first page, launched or connected, which listens and says why, and an answer
    to a click or a prompt, which listens a short grace; a grace waits while
    the window says the user is typing, until a pause or its maximum;
  * a prompt says which page it was typed at, and one typed before the agent's
    latest answer is flagged ``stale``;
  * going back re-sends an earlier page exactly, with its age, and ``showing``
    reads an earlier page back;
  * a wait its host abandoned never takes the next click: a newer wait
    supersedes it, and a cancelled one puts back what it took;
  * the window hears the agent's state, idle after ``show``, listening in a
    wait, working once input arrives, and what the user types reaches the agent
    as ``prompt`` (ADR-601);
  * ``status`` reports that state, and the watcher leaving, from the wire rather
    than from this window's own bar;
  * ``working`` ends on its own deadline, because the agent's turn can end without
    another call and the window blocks every click while it stands;
  * one wait returns every queued click, narrated oldest first and saying the
    message once — but never a prompt, which waits for a call of its own;
  * a press COMMITS the document's other values with it, and the agent is handed
    them under the server's own labels; the server writes them into its copy of
    the page, so a later ``patch`` keeps them, and one that nets to nothing writes
    nothing;
  * ``--port`` serves the conversation at that port from launch, for a client of
    the operator's own; 0 keeps a free one; a taken port stops the launch, saying
    so, whether its listener holds 127.0.0.1 or every address.

Run with: uv run python tests/mcp_demo_tests.py
"""

import asyncio
import contextlib
import io
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from websockets.exceptions import InvalidStatus

from md2ui import mcp_demo, mcp_demo_told, wire_client
from md2ui.utils.fetch_policy import POLICY
from md2ui.pipeline.render_settings import VIEW
from md2ui.wire_client import WireClient
from md2ui.wire_server import Presence
from server_policy import restores_server_policy

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "data/markdown/tests/tests-link-actions.md"

_DEMO = None
# `show` and `mark` listen after replying; the tests here that are not about that
# listening turn it off, and the ones that are pass `wait_seconds` themselves.
mcp_demo.SHOW_WAIT_SECONDS = 0


def _demo():
    global _DEMO
    if _DEMO is None:
        _DEMO = mcp_demo.build_demo_server(None, launch_window=False)
    return _DEMO


def _call(name: str, arguments: dict) -> Any:
    server, _demo_state = _demo()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            result: Any = asyncio.run(server.call_tool(name, arguments))
    finally:
        POLICY.remote, VIEW.placeholder_images = True, False  # as an app left it
    # A tool returning a plain dict comes back as JSON text, not structured content.
    if result.structured_content is not None:
        content = result.structured_content
        return content.get("result", content), result
    texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
    return (json.loads(texts[0]) if texts and not result.is_error else {}), result


def _drain() -> None:
    """Empty the queue, so a test asserts on its own events and no others.

    These tests share one conversation, so anything an earlier test left — a
    presence from a window it opened or closed, a click it did not read — is
    still queued.
    """
    for _ in range(12):
        heard, _raw = _call("wait_for_event", {"timeout_seconds": 1})
        if heard.get("events") == [] and "No click" in heard.get("text", ""):
            return
    raise AssertionError("the queue would not drain")


def _mine(message_id: str) -> dict:
    """The next click that belongs to *message_id*, stepping past any other.

    One conversation is shared by every test here, so a click left by another is
    a real event on the same queue. A test should assert on its own.
    """
    for _ in range(12):
        heard, _raw = _call("wait_for_event", {"timeout_seconds": 10})
        if heard.get("message_id") == message_id:
            return heard
    raise AssertionError(f"no event for {message_id}")


def _connected(client: WireClient) -> None:
    """Connect, and take the reconnection this join announces.

    These tests share one conversation, so a client opened here after an earlier
    test closed one IS a reconnection — the same event a second window produces in
    production. Draining it once, here, keeps it out of the waits each test makes
    its own assertions on.
    """
    client.start()
    client.wait_first(10)
    _drain()


def _closed(client: WireClient) -> None:
    """Close, and take the `closed` this leaves behind — symmetric with
    `_connected`. Whoever shuts a window consumes the event it produces, so it
    does not surface in the next test's wait."""
    client.close()
    _drain()


def _poll(client: WireClient, timeout: float = 5.0) -> list:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        got = client.poll()
        if got:
            return got
        time.sleep(0.02)
    return []


def test_the_demo_offers_fifteen_tools():
    server, _demo_state = _demo()
    try:
        tools = {t.name: t for t in asyncio.run(server.list_tools())}
    finally:
        POLICY.remote, VIEW.placeholder_images = True, False
    assert set(tools) == {
        "check",
        "actions",
        "outline",
        "layout",
        "preview",
        "guide",
        "show",
        "wait_for_event",
        "mark",
        "screenshot",
        "status",
        "showing",
        "feed",
        "history",
        "patch",
    }, set(tools)
    for name in ("show", "mark", "feed"):
        hints = tools[name].annotations
        assert hints is not None and not hints.read_only_hint, name
        assert hints.destructive_hint is False and hints.open_world_hint is False
    print(
        "  ✓  the authoring six, plus show, wait, mark, feed, screenshot, status,"
        " showing, history, patch"
    )


def test_show_click_hear_mark():
    shown, _raw = _call("show", {"markdown": FIXTURE.read_text()})
    mid = shown["message_id"]
    offers = {row["x"]: row for row in shown["offers"]}
    assert offers[0] == {"x": 0, "label": "Yes", "action": "generate-report"}, offers
    assert offers[14] == {"x": 14, "label": "Review the numbers", "kind": "checkbox"}
    assert 8 not in offers, "a web link does not come back to the agent"
    # Advice turns on what this session has read (advice.py), so it is not this test's.
    codes = [i["code"] for i in shown["issues"] if i["code"] != "advice"]
    assert codes == ["action-in-sentence", "boxes-without-commit"], shown
    assert shown["digest"] and isinstance(shown["digest"], str), shown

    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    try:
        client.start()
        first = client.wait_first(10)
        assert first is not None and first.message_id == mid, first
        client.send_event(mid, 14, checked=True)
        heard = _mine(mid)
        assert heard["text"] == (
            f'User ticked "Review the numbers" (task 1) (message {mid}) '
            + mcp_demo_told.CLICK_NEXT
        ), heard
        assert (heard["x"], heard["checked"]) == (14, True), heard

        marked, _raw = _call("mark", {"message_id": mid, "x": 14, "state": "checked"})
        (update,) = _poll(client)
        assert update.replaces == mid and update.message_id == marked["message_id"]
        assert "- [x] Review the numbers" in update.markdown
    finally:
        _closed(client)
    print("  ✓  show → the window gets it → a click is heard → mark updates in place")


def test_bad_marks_and_quiet_waits():
    shown, _raw = _call("show", {"markdown": FIXTURE.read_text()})
    try:
        _call("mark", {"message_id": shown["message_id"], "x": 14, "state": "maybe"})
    except ToolError as exc:
        # `mark` also takes a number, so an unusable state says what it takes
        # rather than reporting the wire's frame code.
        assert "checked, unchecked, disabled" in str(exc), str(exc)
    else:
        _payload, raw = _call(
            "mark", {"message_id": shown["message_id"], "x": 14, "state": "maybe"}
        )
        assert raw.is_error, raw
    started = time.monotonic()
    heard, _raw = _call("wait_for_event", {"timeout_seconds": 1})
    assert heard["events"] == [] and "No click" in heard["text"], heard
    assert time.monotonic() - started < 5
    print("  ✓  a bad state is a tool error; a wait with no click times out")


def _until(check, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.02)
    return False


def test_the_window_hears_the_state_and_its_prompts_reach_the_agent():
    _call("show", {"markdown": FIXTURE.read_text()})
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    heard: dict = {}
    # Pinned long: this test asserts that `w` is REACHED, and the idle watchdog
    # would end it. Other tests shorten the deadline to assert the opposite.
    was, mcp_demo.IDLE_AFTER_WORKING = mcp_demo.IDLE_AFTER_WORKING, 300.0
    try:
        _connected(client)
        assert _until(lambda: client.state == "i"), client.state
        waiting = threading.Thread(
            target=lambda: heard.update(
                _call("wait_for_event", {"timeout_seconds": 10})[0]
            )
        )
        waiting.start()
        assert _until(lambda: client.state == "l"), client.state
        client.send_prompt("Move the call to Friday")
        waiting.join(15)
        assert heard.get("kind") == "prompt", heard
        assert heard["prompt"] == "Move the call to Friday", heard
        assert heard["text"].endswith(mcp_demo_told.PROMPT_NEXT), heard
        assert _until(lambda: client.state == "w"), client.state
        # The same answer, without reading a pixel: the bar and the animation are
        # this window's own (ADR-601), so `status` is what another frontend gets.
        reported, _raw = _call("status", {})
        assert reported["state"] == client.state, (reported, client.state)
        assert reported["watchers"] == 1, reported
        assert reported["message_id"] == demo.served().conversation.latest, reported
    finally:
        mcp_demo.IDLE_AFTER_WORKING = was
        _closed(client)
    assert _until(lambda: _call("status", {})[0]["watchers"] == 0), "the window left"
    print("  ✓  idle after show, listening in a wait, working once a prompt arrives")
    print("  ✓  status reports that state, and the watcher leaving, without pixels")


def test_one_wait_drains_the_queue_but_never_batches_a_prompt():
    """N clicks cost N waits, and a wait is a model turn — so a wait takes
    everything waiting. A prompt is the exception: it is the user's own words
    (ADR-601), so it is left for a call of its own rather than joined to
    sentences built from the agent's Markdown."""
    shown, _raw = _call("show", {"markdown": FIXTURE.read_text()})
    mid = shown["message_id"]
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    try:
        _connected(client)
        # Nobody is listening: these queue.
        client.send_event(mid, 14, checked=True)
        client.send_event(mid, 0, "generate-report")
        client.send_prompt("and that is all of it")
        client.send_event(mid, 15, checked=True)

        heard, _raw = _call("wait_for_event", {"timeout_seconds": 10})
        assert heard["kind"] == "click", heard
        assert [e["x"] for e in heard["events"]] == [14, 0], heard
        assert "2 things happened, oldest first" in heard["text"], heard["text"]
        assert f"(message {mid})" in heard["text"], heard["text"]
        # Said once for the batch, not once per line.
        assert heard["text"].count(f"(message {mid})") == 1, heard["text"]
        assert "Review the numbers" in heard["text"], heard["text"]
        assert "generate-report" in heard["text"], heard["text"]
        assert "x" not in heard, "a batch must not privilege one event"

        # The prompt was held, not dropped, and comes back on its own.
        spoken, _raw = _call("wait_for_event", {"timeout_seconds": 10})
        assert spoken["kind"] == "prompt", spoken
        assert spoken["prompt"] == "and that is all of it", spoken

        # And what queued behind it is still there, reading as a single event.
        last, _raw = _call("wait_for_event", {"timeout_seconds": 10})
        assert last["kind"] == "click" and last["x"] == 15, last
        assert last["text"].startswith(last["events"][0]["text"]), last
        assert "things happened" not in last["text"], last["text"]
    finally:
        _closed(client)
    print("  ✓  one wait drains the clicks; a prompt waits for a call of its own")


def test_a_press_commits_the_values_the_user_adjusted():
    """The cart: adjust three things, press one button, cost one turn. The agent
    hears the decision and the values together, all named by the server."""
    markdown = (
        "# Order\n\nApples: [30%]\n\nPears: [10%]\n\n"
        "- [ ] Gift wrap it\n\n[Proceed](agent:proceed)"
    )
    shown, _raw = _call("show", {"markdown": markdown})
    mid = shown["message_id"]
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    try:
        _connected(client)
        client.send_event(mid, 3, "proceed", settled=[[0, 60.0], [1, 25.5], [2, True]])
        heard, _raw = _call("wait_for_event", {"timeout_seconds": 10})
        assert heard["x"] == 3, heard
        assert '"Apples" at 60%' in heard["text"], heard["text"]
        assert '"Gift wrap it" ticked' in heard["text"], heard["text"]
        settled = heard["events"][0]["settled"]
        assert [s["x"] for s in settled] == [0, 1, 2], settled
        assert settled[1] == {"x": 1, "label": "Pears", "value": 25.5}, settled
        assert settled[2] == {"x": 2, "label": "Gift wrap it", "checked": True}
    finally:
        _closed(client)
    print("  ✓  one press carries the values the user adjusted, named by the server")


def test_a_commit_carried_settle_never_reaches_the_agent():
    """The server withholds what a committing press will report, so the agent is
    woken once. It is RECORDED, not lost — `showing` can still answer what the
    form holds, which is the case a client-side hold left blind."""
    markdown = "# Order\n\nA: [30%]\n\nB: [10%]\n\n[Go](agent:go?md2ui.commit=1)"
    shown, _raw = _call("show", {"markdown": markdown})
    mid = shown["message_id"]
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    try:
        _connected(client)
        client.send_event(mid, 0, value=60.0)
        client.send_event(mid, 1, value=25.0)

        # Sent, and the server knows them — without waking the agent.
        assert _until(
            lambda: _call("showing", {})[0]["offers"][0].get("requested") == 60.0
        ), _call("showing", {})[0]["offers"]

        client.send_event(mid, 2, "go", settled=[[0, 60.0], [1, 25.0]])
        heard, _raw = _call("wait_for_event", {"timeout_seconds": 10})
        assert [e["x"] for e in heard["events"]] == [2], heard["events"]
        assert heard["text"].startswith('User chose "Go": go, with'), heard["text"]
    finally:
        _closed(client)
    print("  ✓  a settle a press will carry is recorded, and only the press wakes")


def test_a_commit_press_writes_its_values_into_the_servers_page():
    """Once a press is answered the window shows what the page's Markdown says,
    so the press is written into the server's copy, and the event names the copy
    that holds it: a patch to another section then keeps the pressed values."""
    page = (
        "# Display\n\nBrightness: [62%]\n\n"
        "# Checklist\n\n- [ ] Back up the files\n- [ ] Update the drivers\n\n"
        "[Save](agent:save-checklist?md2ui.commit=1)\n\n"
        "# Status\n\nNot saved yet.\n"
    )
    shown, _raw = _call("show", {"markdown": page})
    mid = shown["message_id"]
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    grace, mcp_demo.GRACE_SECONDS = mcp_demo.GRACE_SECONDS, 1
    try:
        _connected(client)
        client.send_event(mid, 0, value=83.0)
        client.send_event(mid, 1, checked=True)
        client.send_event(
            mid, 3, "save-checklist", settled=[[0, 83.0], [1, True], [2, False]]
        )
        heard, _raw = _call("wait_for_event", {"timeout_seconds": 10})
        assert heard["x"] == 3, heard
        assert '"Brightness" at 83%' in heard["text"], heard["text"]
        assert heard["message_id"] != mid, "the event names the page holding it"

        # The window is sent the copy it already shows, replacing the one it had.
        (written,) = _poll(client)
        assert (written.replaces, written.message_id) == (mid, heard["message_id"])
        assert "Brightness: [83%]" in written.markdown, written.markdown
        assert "- [x] Back up the files" in written.markdown, written.markdown
        assert "- [ ] Update the drivers" in written.markdown, written.markdown

        patched, _raw = _call(
            "patch",
            {
                "message_id": heard["message_id"],
                "section": "Status",
                "markdown": "Saved.",
                "wait_seconds": 0,
            },
        )
        (update,) = _poll(client)
        for kept in ("Brightness: [83%]", "- [x] Back up the files", "Saved."):
            assert kept in update.markdown, (kept, update.markdown)
        seen, _raw = _call("showing", {})
        assert seen["message_id"] == patched["message_id"], seen
        assert seen["markdown"] == update.markdown, seen["markdown"]
        assert not any("requested" in row for row in seen["offers"]), seen["offers"]

        # A press that nets to nothing writes nothing: no replacement, same id.
        again, _raw = _call("show", {"markdown": page, "wait_seconds": 0})
        _poll(client)
        client.send_event(
            again["message_id"],
            3,
            "save-checklist",
            settled=[[0, 62.0], [1, False], [2, False]],
        )
        quiet = _mine(again["message_id"])
        assert quiet["text"].startswith(
            'User chose "Save": save-checklist, with no change'
        )
        assert _poll(client, timeout=1.0) == [], "nothing was written"
        assert _call("showing", {})[0]["markdown"] == page
    finally:
        mcp_demo.GRACE_SECONDS = grace
        _closed(client)
    print("  ✓  a commit press is written into the server's page, and a patch keeps it")


def test_mark_sets_a_value_without_resending_the_document():
    """A number can only change by re-sending the whole answer otherwise, and for
    a long one that is reproducing prose from memory on every press. The server
    edits its own copy, so only the named token moves."""
    markdown = "# Order\n\nApples: [3/10]\n\nVolume: [65%]\n\n- [ ] Wrap it"
    shown, _raw = _call("show", {"markdown": markdown})
    mid = shown["message_id"]
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    try:
        _connected(client)
        marked, _raw = _call("mark", {"message_id": mid, "x": 0, "state": "7"})
        (update,) = _poll(client)
        assert update.replaces == mid, update
        assert update.message_id == marked["message_id"]
        # The authored spelling survives, and nothing else in the document moved.
        assert "Apples: [7/10]" in update.markdown, update.markdown
        assert "Volume: [65%]" in update.markdown, update.markdown
        assert "- [ ] Wrap it" in update.markdown, update.markdown

        # Outside the target's authored domain, and not a number at all.
        for bad in ("50", "soon"):
            try:
                _payload, raw = _call(
                    "mark", {"message_id": marked["message_id"], "x": 0, "state": bad}
                )
                assert raw.is_error, bad
            except ToolError:
                pass
    finally:
        _closed(client)
    print("  ✓  mark sets a value in place, inside the range its document authored")


def test_mark_moves_a_bar_by_its_key():
    """A static bar has no ordinal, so `mark` names it by the key the agent wrote;
    the update is an ordinary replacement, and a slider is still named by `x`."""
    markdown = "# Upload\n\nElapsed: 45%\n\n- CPU: 40%\n- RAM: 70%\n- Disk: 20%\n\nVolume: [65%]"
    shown, _raw = _call("show", {"markdown": markdown})
    mid = shown["message_id"]
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    try:
        _connected(client)
        marked, _raw = _call("mark", {"message_id": mid, "key": "Elapsed", "value": 60})
        (update,) = _poll(client)
        assert update.replaces == mid and update.message_id == marked["message_id"]
        assert update.markdown == markdown.replace("45%", "60%"), update.markdown
        marked, _raw = _call(
            "mark", {"message_id": update.message_id, "key": "RAM", "value": 90}
        )
        (row,) = _poll(client)
        assert "- RAM: 90%" in row.markdown and "Elapsed: 60%" in row.markdown
        marked, _raw = _call(
            "mark", {"message_id": row.message_id, "x": 0, "state": "30"}
        )
        (slid,) = _poll(client)
        assert "Volume: [30%]" in slid.markdown and "Elapsed: 60%" in slid.markdown
        latest = slid.message_id
        for bad in (
            {"x": 0, "state": "30", "key": "Elapsed", "value": 10},
            {},
            {"key": "Elapsed"},
            {"key": "Elapsed", "value": 101},
            {"key": "Uptime", "value": 10},
        ):
            try:
                _payload, raw = _call("mark", {"message_id": latest} | bad)
                assert raw.is_error, bad
            except ToolError:
                pass
    finally:
        _closed(client)
    print("  ✓  mark moves a bar by its key in place; a slider is still named by x")


def test_a_feed_moves_a_bar_without_a_turn():
    """`feed` hands back a URL; a post to it moves the bar in place, and the wait
    hears the feed end: one call to open it, one wait, no turn per value."""
    markdown = "# Build\n\nCompiled: 0%\n"
    shown, _raw = _call("show", {"markdown": markdown})
    mid = shown["message_id"]
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    try:
        _connected(client)
        opened, _raw = _call("feed", {"message_id": mid})  # its one bar
        assert opened["keys"] == ["Compiled"] and opened["url"] in opened["pipe"]
        assert opened["post"] == f"curl -s --data-binary 'Compiled: 0%' {opened['url']}"
        posted = urllib.request.Request(opened["url"], b"Compiled: 100%", method="POST")
        with urllib.request.urlopen(posted, timeout=5) as response:
            assert response.status == 200
        (update,) = _poll(client)
        assert update.replaces == mid and update.markdown == markdown.replace(
            "0%", "100%"
        )
        heard, _raw = _call("wait_for_event", {"timeout_seconds": 10})
        assert (heard["kind"], heard["reason"]) == ("feed_ended", "full"), heard
        for bad in ({"keys": ["Uptime"]}, {"keys": ["Compiled"], "until": "never"}):
            try:
                _payload, raw = _call("feed", {"message_id": mid} | bad)
                assert raw.is_error, bad
            except ToolError:
                pass
    finally:
        _closed(client)
    print("  ✓  feed moves a bar from a post, and the wait hears it end")


def test_idle_is_derived_not_asserted():
    """`i` means nobody is listening, so a caller that does not know whether a
    wait is open cannot say it: neither `show` nor the watchdog sends it while a
    wait is pending."""
    _call("show", {"markdown": FIXTURE.read_text()})
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    was, mcp_demo.IDLE_AFTER_WORKING = mcp_demo.IDLE_AFTER_WORKING, 0.3
    try:
        _connected(client)
        assert _until(lambda: client.state == "i"), "no wait open: idle"

        waiting = threading.Thread(
            target=lambda: _call("wait_for_event", {"timeout_seconds": 8})
        )
        waiting.start()
        assert _until(lambda: client.state == "l"), client.state

        # A `show` while that wait is pending must not claim nobody is listening.
        _call("show", {"markdown": "# Still here\n\n[Go](agent:go)"})
        assert _until(lambda: _call("status", {})[0]["state"] == "l"), "show said i"
        assert client.state == "l", client.state
        waiting.join(20)
    finally:
        mcp_demo.IDLE_AFTER_WORKING = was
        _closed(client)
    print("  ✓  idle is derived from whether a wait is open, never asserted")


def test_a_wait_ends_as_a_timeout_not_as_the_host_killing_it():
    """A host that kills a long wait with an error loses the agent the loop, so
    the cap sits under the host's limit, and the wait is taken in slices so the
    call reports progress: silence is what an idle timeout counts."""
    assert mcp_demo.MAX_WAIT_SECONDS < 1800, "the measured host abort"
    assert mcp_demo.DEFAULT_WAIT_SECONDS < mcp_demo.MAX_WAIT_SECONDS
    assert mcp_demo.PROGRESS_EVERY_SECONDS < 120, "the host backgrounds at 120 s"

    _call("show", {"markdown": FIXTURE.read_text()})
    started = time.monotonic()
    # Shorter than one slice: the loop must still end on the caller's timeout.
    heard, _raw = _call("wait_for_event", {"timeout_seconds": 1})
    assert heard["events"] == [] and "No click" in heard["text"], heard
    assert time.monotonic() - started < 10, "the slices must not extend the wait"
    print("  ✓  a wait is capped under the host's limit and reports progress")


def test_a_session_holds_the_turn():
    """Nothing can wake an agent whose turn has ended, so the window is heard only
    while a wait is open. The shell tells the agent to
    re-arm after every return, and never ties showing to structure or listening to
    choices: the form of a reply is the agent's."""
    _call("show", {"markdown": FIXTURE.read_text()})
    heard, _raw = _call("wait_for_event", {"timeout_seconds": 1})
    assert "`wait_for_event` again" in heard["text"], heard
    said = mcp_demo.DEMO_INSTRUCTIONS
    assert "`show` and `mark` listen" in said and "has structure" not in said, said
    print("  ✓  a session re-arms its wait and shows any reply")


def test_an_abandoned_wait_never_takes_the_next_click():
    """A host may abandon a wait and the agent open another. Two waits then
    share one queue, and the old
    one must not carry the user's click to a caller that is gone: it gives way to
    the newer wait, and one it was cancelled out of is put back."""
    shown, _raw = _call("show", {"markdown": FIXTURE.read_text()})
    mid = shown["message_id"]
    server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    _connected(client)
    # Each `_call` redirects stdout, and two overlapping in threads can restore
    # them out of order, leaving the rest of the run printing into a buffer.
    stdout = sys.stdout
    try:
        old: dict = {}
        first = threading.Thread(
            target=lambda: old.update(
                _call("wait_for_event", {"timeout_seconds": 30})[0]
            )
        )
        first.start()
        assert _until(lambda: demo._waiting)
        new: dict = {}
        second = threading.Thread(
            target=lambda: new.update(
                _call("wait_for_event", {"timeout_seconds": 10})[0]
            )
        )
        second.start()
        first.join(5)
        assert old.get("text") == "A newer wait took over.", old
        assert _call("status", {})[0]["state"] == "l", "the newer wait still listens"
        client.send_event(mid, 14, checked=True)
        second.join(12)
        assert (new.get("message_id"), new.get("x")) == (mid, 14), new

        async def cancelled() -> None:
            task = asyncio.ensure_future(
                server.call_tool("wait_for_event", {"timeout_seconds": 30})
            )
            await asyncio.sleep(0.3)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            # Clicked while the cancelled wait's last slice still listens, and
            # the loop kept alive past it, as the real server's always is.
            client.send_event(mid, 14, checked=False)
            await asyncio.sleep(mcp_demo.SLICE_SECONDS + 0.5)

        with contextlib.redirect_stdout(io.StringIO()):
            asyncio.run(cancelled())
        assert _call("status", {})[0]["state"] == "i", (
            "a cancelled wait listens no more"
        )
        heard = _mine(mid)
        assert (heard["x"], heard["checked"]) == (14, False), heard
    finally:
        sys.stdout = stdout
        _closed(client)
    print("  ✓  an abandoned wait gives way, and a cancelled one returns its click")


def test_show_and_mark_listen_after_replying():
    """An agent told to wait after `show` does not reliably do it, so listening
    is part of the reply: `show` and `mark` return what
    the user did next as `heard`, and a `show` hands over everything that queued
    while nobody listened. An answer with issues is about to change, so it is not
    listened to."""
    plain = "# Listening\n\n- [ ] One\n"
    first, _raw = _call("show", {"markdown": plain})
    assert "heard" not in first, "the default is off in these tests"
    server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    _connected(client)
    stdout = sys.stdout
    try:
        started = time.monotonic()
        quiet, _raw = _call("show", {"markdown": plain, "wait_seconds": 1})
        assert quiet["heard"]["events"] == [], quiet
        assert "`wait_for_event` again" in quiet["heard"]["text"], quiet
        assert time.monotonic() - started < 10

        mid = quiet["message_id"]
        client.send_event(mid, 0, checked=True)  # made while nobody listened
        time.sleep(0.5)  # let it queue
        again, _raw = _call("show", {"markdown": plain, "wait_seconds": 5})
        assert (again["heard"]["message_id"], again["heard"]["x"]) == (mid, 0), again

        # An error stops the listen (a note would not: see _listens).
        flawed, _raw = _call(
            "show", {"markdown": "[Skip ahead](#nowhere)", "wait_seconds": 5}
        )
        assert flawed["issues"] and "heard" not in flawed, flawed

        shown, _raw = _call("show", {"markdown": plain})
        marked, _raw = _call(
            "mark",
            {
                "message_id": shown["message_id"],
                "x": 0,
                "state": "checked",
                "wait_seconds": 1,
            },
        )
        assert marked["heard"]["events"] == [], marked
    finally:
        sys.stdout = stdout
        _closed(client)
    print("  ✓  show and mark listen after replying, and a show drains the queue")


def test_a_prompt_typed_at_an_older_page_says_so():
    """A prompt typed while nobody listened waits in the queue, and `show` hands
    the queue over, so an old "you can stop" could read as the reply to a new
    page. Each prompt is stamped on receipt with the page
    it was typed at, and one typed before the agent's latest answer says so."""
    plain = "# Stale\n\nA page.\n"
    first, _raw = _call("show", {"markdown": plain})
    server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    _connected(client)
    stdout = sys.stdout
    try:
        client.send_prompt("you can stop listening")
        time.sleep(0.5)  # queued while nobody listens
        later, _raw = _call("show", {"markdown": plain, "wait_seconds": 5})
        old = later["heard"]
        assert old["kind"] == "prompt" and old["stale"] is True, old
        assert old["typed_on"] == first["message_id"], old
        assert "before your latest answer" in old["text"], old
        assert old["text"].endswith(mcp_demo_told.PROMPT_NEXT), old

        fresh: dict = {}
        waiting = threading.Thread(
            target=lambda: fresh.update(
                _call("wait_for_event", {"timeout_seconds": 10})[0]
            )
        )
        waiting.start()
        assert _until(lambda: demo._waiting)
        client.send_prompt("and this one is new")
        waiting.join(12)
        assert fresh.get("kind") == "prompt" and "stale" not in fresh, fresh
        assert fresh["typed_on"] == later["message_id"], fresh
    finally:
        sys.stdout = stdout
        _closed(client)
    print("  ✓  a prompt typed at an older page says so; a new one does not")


def test_going_back_resends_an_earlier_page_as_it_was():
    """A page rebuilt from memory is reworded and its data stale. The server
    keeps every page it sent, so `show`
    re-sends one by id, exactly, and says its age; `showing` reads one back for
    an agent that would rather refresh its live parts first."""
    overview = "# Overview\n\n- [ ] One\n"
    detail = "# Detail\n\nA second page.\n"
    first, _raw = _call("show", {"markdown": overview})
    _call("show", {"markdown": detail})
    back, _raw = _call("show", {"message_id": first["message_id"]})
    assert back["sent_again"] == first["message_id"], back
    assert isinstance(back["age_s"], int), back
    live, _raw = _call("showing", {})
    assert live["message_id"] == back["message_id"] and live["markdown"] == overview
    old, _raw = _call("showing", {"message_id": first["message_id"]})
    assert old["markdown"] == overview and isinstance(old["age_s"], int), old
    for arguments in ({"message_id": "nope"}, {}):
        try:
            _call("show", arguments)
        except ToolError:
            continue
        raise AssertionError(f"{arguments} must be an error, not an empty page")
    print("  ✓  going back re-sends an earlier page as it was, with its age")


def test_any_id_a_page_had_goes_back_to_its_latest_version():
    """A Back link the agent wrote names the page as it was when the link was
    written; a `mark` since gave the page a new id. Every id the page had names
    its latest version, and `history` lists the page once, under that id, so the
    agent need not keep a map of ids in its context. Ids carry the run's prefix,
    so one from before a restart cannot name a page of this run."""
    home = (
        "# Home {#home}\n\n## Repo\n<!-- from: git status; fresh: 5m -->\n\n- [ ] One\n"
    )
    first, _raw = _call(
        "show", {"markdown": home + "\n## Later\n<!-- fresh: soon -->\n"}
    )
    notes = [i["code"] for i in first["issues"] if i["level"] == "note"]
    assert "fresh-unread" in notes, first["issues"]
    first, _raw = _call("show", {"markdown": home})
    old = first["message_id"]
    assert re.fullmatch(r"[0-9a-f]{2}-c\d+", old), old
    marked, _raw = _call("mark", {"message_id": old, "x": 0, "state": "checked"})
    _call("show", {"markdown": "# Detail\n\nA second page.\n"})
    back, _raw = _call("show", {"message_id": old})
    assert back["sent_again"] == marked["message_id"], (back, marked)
    assert "[x] One" in _call("showing", {"message_id": old})[0]["markdown"]
    listed, _raw = _call("history", {})
    rows = [r for r in listed["pages"] if r["title"] in ("Home", "Detail")]
    assert [r["title"] for r in rows][:2] == ["Home", "Detail"], listed
    assert rows[0]["message_id"] == back["message_id"], listed
    assert rows[0]["sources"] == {"Repo": "git status"}, rows[0]
    assert rows[0]["data_age_s"] >= rows[0]["age_s"], rows[0]
    assert listed["showing"] == back["message_id"], listed
    print(
        "  ✓  any id a page had goes back to its latest version; history lists it once"
    )


def test_patch_changes_one_part_and_going_back_is_one_call():
    """`patch` replaces one stale card in the server's copy, so the agent need
    not rebuild the page: in place on the page shown, and as
    the page itself when going back to one that is not, so re-read + patch is
    the whole of going back. A link is patched by its `x`."""
    home = (
        "# Home {#home}\n\n## Repo {#repo}\n<!-- from: git status; fresh: 5m -->\n"
        "85 minutes ago\n\n## Songs\n[🤍](agent:like?id=3) Song A\n"
    )
    shown, _raw = _call("show", {"markdown": home})
    page = shown["message_id"]
    liked, _raw = _call(
        "patch", {"message_id": page, "x": 0, "markdown": "[❤️](agent:unlike?id=3)"}
    )
    assert liked["offers"][0]["action"] == "unlike", liked
    _call("show", {"markdown": "# Detail\n\nA second page.\n"})
    back, _raw = _call(
        "patch", {"message_id": page, "section": "repo", "markdown": "88 minutes ago"}
    )
    now, _raw = _call("showing", {})
    assert now["message_id"] == back["message_id"], (now, back)
    assert "88 minutes ago" in now["markdown"] and "❤️" in now["markdown"], now
    assert "85 minutes" not in now["markdown"] and "stale" not in back, back
    try:
        _call(
            "patch", {"message_id": page, "x": 0, "markdown": "[🤍](agent:like?id=3)"}
        )
        raise AssertionError("x on a page since patched must be refused")
    except ToolError as exc:
        said = str(exc)
    assert now["message_id"] in said and said.count("stale") == 1, said
    for bad in (
        {"message_id": page, "section": "nope", "markdown": "x"},
        {"message_id": page, "section": "repo", "markdown": "# Big\n\nz"},
        {"message_id": page, "markdown": "x"},
    ):
        try:
            _call("patch", bad)
        except ToolError:
            continue
        raise AssertionError(f"{bad} must be refused")
    after, _raw = _call("showing", {})
    assert after["message_id"] == now["message_id"], "a refusal takes no id"
    print("  ✓  patch changes one section or link; going back is one call")


def test_a_closed_window_interrupts_a_waiting_agent():
    """`status()` answers "quiet or gone" by poll, but an agent blocked in a wait
    is not asking, and a wait lasts up to 25 minutes, so a window closed inside
    one would leave the loop dead for that long."""
    _call("show", {"markdown": FIXTURE.read_text()})
    _server, demo = _demo()
    heard: dict = {}
    client = WireClient(demo.served().url, bearer=demo.bearer)
    _connected(client)
    waiting = threading.Thread(
        target=lambda: heard.update(_call("wait_for_event", {"timeout_seconds": 20})[0])
    )
    waiting.start()
    assert _until(lambda: _call("status", {})[0]["state"] == "l")
    client.close()  # the user closes the window; the wait below IS the assertion
    waiting.join(25)
    assert heard.get("kind") == "closed", heard
    assert "no click can arrive" in heard["text"], heard
    assert "in the chat" in heard["text"], "only the agent can reopen it"

    # And coming back is its own event, not silence.
    back = WireClient(demo.served().url, bearer=demo.bearer)
    try:
        back.start()
        back.wait_first(10)
        again, _raw = _call("wait_for_event", {"timeout_seconds": 10})
        assert again["kind"] == "reconnected", again
    finally:
        _closed(back)
    print("  ✓  a closed window interrupts the wait; coming back is its own event")


def test_show_drops_a_presence_queued_before_it():
    """A presence queued before `show` sends describes a window before this
    answer, so `show` drops it rather than read a stale `closed` as news about the
    window it just launched; a click queued with it is kept, and a close after
    `show` still arrives.

    No window is launched here, so `open_window` stands for one that has not
    joined yet."""
    plain = "# Presence\n\n- [ ] One\n"
    _call("show", {"markdown": plain})
    _server, demo = _demo()
    old = WireClient(demo.served().url, bearer=demo.bearer)
    _connected(old)
    old.close()  # the earlier window goes; its `closed` stays queued
    assert _until(lambda: demo.served().conversation.events.qsize() > 0)
    shown, _raw = _call("show", {"markdown": plain, "wait_seconds": 1})
    assert shown["heard"].get("events") == [], shown["heard"]
    _drain()

    # A click made before the window went is the user's, and is kept.
    client = WireClient(demo.served().url, bearer=demo.bearer)
    _connected(client)
    client.send_event(shown["message_id"], 0, checked=True)
    assert _until(lambda: demo.served().conversation.events.qsize() > 0)
    client.close()
    assert _until(lambda: demo.served().conversation.events.qsize() > 1)
    again, _raw = _call("show", {"markdown": plain, "wait_seconds": 5})
    assert (again["heard"]["message_id"], again["heard"]["x"]) == (
        shown["message_id"],
        0,
    ), again["heard"]
    quiet, _raw = _call("wait_for_event", {"timeout_seconds": 1})
    assert quiet.get("events") == [], quiet

    # A close after `show` is about the window showing this answer: it arrives.
    late = WireClient(demo.served().url, bearer=demo.bearer)
    _connected(late)
    _call("show", {"markdown": plain})
    late.close()
    gone, _raw = _call("wait_for_event", {"timeout_seconds": 10})
    assert gone.get("kind") == "closed", gone
    print("  ✓  show drops a presence queued before it; clicks and later closes stay")


def test_a_put_back_presence_is_served_only_while_true():
    """A cancelled wait's last slice can take a `closed` that `show` cannot see,
    and put it back after the next window joined. A put-back presence is checked
    against who is watching when it is served, as one read off the queue is.

    The slice holds its batch for half a second: with natural timing the put-back
    lands before `show` clears it."""
    plain = "# Presence\n\n- [ ] One\n"
    _call("show", {"markdown": plain})
    server, demo = _demo()
    served = demo.served()
    old = WireClient(served.url, bearer=demo.bearer)
    _connected(old)
    take = served.next_events

    def held(*args: Any, **kwargs: Any) -> list:
        batch = take(*args, **kwargs)
        if batch:
            time.sleep(0.5)
        return batch

    new = WireClient(served.url, bearer=demo.bearer)

    async def race() -> None:
        task = asyncio.ensure_future(
            server.call_tool("wait_for_event", {"timeout_seconds": 30})
        )
        await asyncio.sleep(0.3)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        old.close()  # the orphaned slice takes this `closed`
        await asyncio.sleep(0.1)
        await server.call_tool("show", {"markdown": plain})
        new.start()
        await asyncio.to_thread(new.wait_first, 10)
        await asyncio.sleep(mcp_demo.SLICE_SECONDS + 0.5)

    stdout = sys.stdout
    served.next_events = held  # type: ignore[method-assign]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            asyncio.run(race())
        assert served._returned, "the slice did not put its `closed` back"
        heard, _raw = _call("wait_for_event", {"timeout_seconds": 2})
        assert heard.get("kind") != "closed", heard
    finally:
        del served.next_events
        sys.stdout = stdout
        _closed(new)

    # With nobody watching, a put-back `closed` is still true and still served;
    # a put-back `reconnected` is not, and is dropped.
    assert _until(lambda: served.conversation.watchers == 0)
    served.put_back([Presence("reconnected")])
    served.put_back([Presence("closed")])
    gone, _raw = _call("wait_for_event", {"timeout_seconds": 2})
    assert gone.get("kind") == "closed", gone
    quiet, _raw = _call("wait_for_event", {"timeout_seconds": 1})
    assert quiet.get("events") == [], quiet
    print("  ✓  a put-back presence is served only while it is still true")


def test_showing_reports_what_the_user_asked_for():
    """What a control HOLDS is a data question: a render is expensive to read,
    and unreadable when a theme draws a slider as a block."""
    markdown = "# Order\n\nA: [3/10]\n\n- [ ] Wrap it\n\n[Go](agent:go)"
    shown, _raw = _call("show", {"markdown": markdown})
    mid = shown["message_id"]
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    try:
        _connected(client)
        before, _raw = _call("showing", {})
        assert before["message_id"] == mid, before
        assert "A: [3/10]" in before["markdown"], before["markdown"]
        assert all("requested" not in row for row in before["offers"]), before

        client.send_event(mid, 0, value=8.0)
        client.send_event(mid, 1, checked=True)
        _call("wait_for_event", {"timeout_seconds": 10})

        after, _raw = _call("showing", {})
        rows = {row["x"]: row for row in after["offers"]}
        assert rows[0]["requested"] == 8.0, rows[0]
        assert rows[1]["requested"] is True, rows[1]
        assert "go" not in str(rows[2].get("requested", "")), rows[2]
        # Requests, not state: the document still says what it said (ADR-404).
        assert "A: [3/10]" in after["markdown"], after["markdown"]
    finally:
        _closed(client)
    print("  ✓  showing reports the live document and what the user asked for")


def test_working_ends_without_the_agent_saying_so():
    """`w` is the one state the agent cannot be relied on to clear: a turn that
    answers a click and ends makes no further call. While it stands the window
    blocks every click in the document, not just its own prompt bar, so it ends
    on a deadline instead."""
    _call("show", {"markdown": FIXTURE.read_text()})
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    was, mcp_demo.IDLE_AFTER_WORKING = mcp_demo.IDLE_AFTER_WORKING, 0.3
    try:
        _connected(client)
        heard: dict = {}
        waiting = threading.Thread(
            target=lambda: heard.update(
                _call("wait_for_event", {"timeout_seconds": 10})[0]
            )
        )
        waiting.start()
        assert _until(lambda: client.state == "l"), client.state
        client.send_prompt("Book it")
        waiting.join(15)
        assert _until(lambda: client.state == "w"), client.state
        # Nothing else is called: this is the agent's turn simply ending.
        assert _until(lambda: client.state == "i", 5.0), client.state
        assert _call("status", {})[0]["state"] == "i"
    finally:
        mcp_demo.IDLE_AFTER_WORKING = was
        _closed(client)
    print("  ✓  working ends on its own, so a finished turn cannot freeze the page")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_a_port_asked_for_is_served():
    port = _free_port()
    _server, demo = mcp_demo.build_demo_server(None, launch_window=False, port=port)
    try:
        assert demo.served().url == f"ws://127.0.0.1:{port}/ws", demo.served().url
        client = WireClient(demo.served().url, bearer=demo.bearer)
        client.start()
        assert _until(lambda: demo.served().conversation.watchers == 1), "no join"
        client.close()
    finally:
        demo.close()
    _server, demo = mcp_demo.build_demo_server(None, launch_window=False)
    try:
        assert demo.served().port not in (0, port), demo.served().port
    finally:
        demo.close()
    print("  ✓  --port serves at that port; 0 keeps a free one")


def test_only_the_launched_window_holds_the_servers_secret():
    _server, demo = mcp_demo.build_demo_server(None, launch_window=True)
    launched: dict = {}

    class _Window:
        def __init__(self, args, **kw):
            launched.update(args=args, env=kw.get("env") or {})

        def poll(self):
            return None

        def terminate(self):
            pass

    real = mcp_demo.subprocess.Popen
    mcp_demo.subprocess.Popen = _Window  # type: ignore[misc]
    try:
        assert demo.open_window()
        assert launched["env"].get(wire_client.WIRE_BEARER) == demo.bearer, launched
        assert demo.bearer not in " ".join(launched["args"]), "the secret is in argv"
        stranger = WireClient(demo.served().url)
        try:
            stranger.start()
            raise AssertionError("a client without the secret got in")
        except InvalidStatus as exc:
            assert exc.response.status_code == 403, exc.response.status_code
    finally:
        mcp_demo.subprocess.Popen = real  # type: ignore[misc]
        demo.close()
    print("  ✓  the window gets the secret in its environment; a stranger gets a 403")


def _demo_with_launcher_secret(value: str | None):
    """A demo built with *value* in `MD2UI_WIRE_BEARER` (None: unset), and what its
    window was launched with. The variable is restored afterwards."""
    saved = os.environ.pop(wire_client.WIRE_BEARER, None)
    if value is not None:
        os.environ[wire_client.WIRE_BEARER] = value
    launched: dict = {}

    class _Window:
        def __init__(self, args, **kw):
            launched.update(env=kw.get("env") or {})

        def poll(self):
            return None

        def terminate(self):
            pass

    real = mcp_demo.subprocess.Popen
    mcp_demo.subprocess.Popen = _Window  # type: ignore[misc]
    try:
        _server, demo = mcp_demo.build_demo_server(None, launch_window=True)
        assert demo.open_window()
    finally:
        mcp_demo.subprocess.Popen = real  # type: ignore[misc]
        os.environ.pop(wire_client.WIRE_BEARER, None)
        if saved is not None:
            os.environ[wire_client.WIRE_BEARER] = saved
    return demo, launched["env"].get(wire_client.WIRE_BEARER)


def test_a_launcher_may_choose_the_secret_and_nobody_else_gets_in():
    """A launcher that drives its own window chooses the secret in the variable the
    window inherits: the server then requires exactly that value, the window it
    launches holds the same one, and any other client still gets a 403."""
    chosen = "l" * mcp_demo.LAUNCHER_BEARER_MIN
    demo, window_secret = _demo_with_launcher_secret(chosen)
    try:
        assert demo.bearer == chosen and window_secret == chosen, (
            demo.bearer,
            window_secret,
        )
        holder = WireClient(demo.served().url, bearer=chosen)
        holder.start()
        holder.close()
        for wrong in (None, chosen[:-1] + "x"):
            stranger = WireClient(demo.served().url, bearer=wrong)
            try:
                stranger.start()
                raise AssertionError(f"a client with {wrong!r} got in")
            except InvalidStatus as exc:
                assert exc.response.status_code == 403, exc.response.status_code
    finally:
        demo.close()
    print("  ✓  a launcher's secret is the one required; any other client gets a 403")


def test_an_unset_or_short_launcher_secret_is_minted_instead():
    """No variable, or a value under the minimum, and the demo mints its own per run:
    a typo or a placeholder never becomes the door."""
    short = "s" * (mcp_demo.LAUNCHER_BEARER_MIN - 1)
    for value in (None, "", short):
        demo, window_secret = _demo_with_launcher_secret(value)
        try:
            assert demo.bearer != value and len(demo.bearer) >= 43, demo.bearer
            assert window_secret == demo.bearer, (window_secret, demo.bearer)
        finally:
            demo.close()
    print("  ✓  an unset or short launcher secret is ignored; the demo mints its own")


def test_a_taken_port_stops_the_launch():
    for host in ("127.0.0.1", "0.0.0.0"):
        with socket.socket() as holder:
            holder.bind((host, 0))
            holder.listen()
            port = holder.getsockname()[1]
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                try:
                    mcp_demo.main(["--no-window", "--port", str(port)])
                    raise AssertionError(f"{host}: the launch went ahead")
                except SystemExit as exc:
                    assert exc.code == 2, exc.code
            assert f"port {port} is taken" in err.getvalue(), err.getvalue()
    print("  ✓  a taken port stops the launch and says so")


def test_a_click_says_what_comes_next_and_carries_its_action():
    """A click result says what follows, as every result does, and an agent
    link's action and parameters come as fields, not only inside the sentence."""
    shown, _raw = _call("show", {"markdown": FIXTURE.read_text()})
    mid = shown["message_id"]
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    try:
        _connected(client)
        client.send_event(mid, 0)
        chose = _mine(mid)
        assert chose["text"].endswith(mcp_demo_told.CLICK_NEXT), chose
        assert chose["action"] == "generate-report", chose
        assert chose["params"] == {"format": "pdf", "year": "2026"}, chose
        assert chose["events"][0]["action"] == "generate-report", chose

        client.send_event(mid, 14, checked=True)
        ticked = _mine(mid)
        assert "action" not in ticked and "params" not in ticked, ticked
    finally:
        _closed(client)
    print("  ✓  a click says what comes next, and carries its action as fields")


def test_a_click_says_which_section_it_came_from():
    """A heard event says the section, by the name `patch` takes, so the agent
    need not map an ordinal back to a page it remembers; also how old the page's
    data is, and whether that section is past its `fresh:`."""
    page = (
        "# Home\n\n## 🌤️ Weather {#weather}\n<!-- from: accuweather; fresh: 1s -->\n"
        "Sunny\n\n[Hourly](agent:hourly)\n\n## Also connected\n[Spotify](agent:spotify)\n"
    )
    shown, _raw = _call("show", {"markdown": page})
    mid = shown["message_id"]
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    try:
        _connected(client)
        time.sleep(1.2)  # past the weather's 1 s
        client.send_event(mid, 0)
        weather = _mine(mid)
        assert weather["section"] == "weather" and weather["stale"] is True, weather
        assert weather["data_age_s"] >= 1 and weather["section_age_s"] >= 1, weather
        client.send_event(mid, 1)
        other = _mine(mid)
        assert other["section"] == "Also connected" and "stale" not in other, other
    finally:
        _closed(client)
    print("  ✓  a click says its section, the page's data age, and a stale section")


def test_listening_again_answers_the_clicks_it_was_handed():
    """A click answered by changing something else would leave its button held,
    since the replacement leaves the button as it is. Listening again is the answer:
    the window is told to let go of what the agent was handed, when its next
    wait opens, so a batch answered with `wait_seconds` 0 stays held until the
    last, and a click it has not been handed yet stays held (ADR-601)."""
    page = (
        "# Ask\n\n## Repo {#repo}\nold\n\n"
        "## Choose\n[A](agent:a) [B](agent:b) [C](agent:c)\n"
    )
    shown, _raw = _call("show", {"markdown": page})
    mid = shown["message_id"]
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)

    def released() -> list[int]:
        client.poll()  # the window takes its messages before what they answer
        return client.answered()

    try:
        _connected(client)
        client.send_event(mid, 0)
        client.send_event(mid, 1)
        heard, _raw = _call("wait_for_event", {"timeout_seconds": 10})
        assert [(e["message_id"], e["x"]) for e in heard["events"]] == [
            (mid, 0),
            (mid, 1),
        ], heard
        patched, _raw = _call(
            "patch",
            {
                "message_id": mid,
                "section": "repo",
                "markdown": "new",
                "wait_seconds": 0,
            },
        )
        _poll(client)
        assert released() == [], "not listening yet: both stay held"
        client.send_event(patched["message_id"], 2)  # not handed to the agent yet
        again = _mine(patched["message_id"])
        assert again["x"] == 2, again
        assert _until(lambda: released() == [0, 1]), "the listen answered A and B"
        assert released() == [], "C stays held until the next listen"
    finally:
        _closed(client)
    print("  ✓  listening again answers the clicks it was handed, and only those")


def test_a_note_leaves_show_listening():
    note = {"level": "note", "code": "repeated-offer", "message": "m"}
    warning = {"level": "warning", "code": "image-param", "message": "m"}
    assert mcp_demo._listens([]) and mcp_demo._listens([note, note])
    assert not mcp_demo._listens([note, warning])
    assert not mcp_demo._listens([{**warning, "level": "error"}])
    print("  ✓  show listens through notes; an error or a warning stops it")


def test_a_timeout_counts_the_live_offers():
    """A timeout on a page with live offers must not read like one on a page with
    none, so it says how many offers are live, as a field too."""
    shown, _raw = _call(
        "show", {"markdown": "# Next\n\n- [ ] One\n- [ ] Two\n", "wait_seconds": 0}
    )
    heard, _raw = _call("wait_for_event", {"timeout_seconds": 1})
    assert heard["live_offers"] == 2 and heard["events"] == [], heard
    assert "this page's 2 offers are still live" in heard["text"], heard
    assert heard["text"].endswith("again to keep listening " + mcp_demo.WAIT_AGAIN), (
        heard
    )

    _call("show", {"markdown": "# Goodbye\n\nThanks.\n", "wait_seconds": 0})
    quiet, _raw = _call("wait_for_event", {"timeout_seconds": 1})
    assert quiet["live_offers"] == 0, quiet
    assert (
        quiet["text"]
        == "No click or message within 1 s. Call `wait_for_event` again to keep listening."
    ), quiet
    print("  ✓  a timeout counts the page's live offers, in its text and as a field")


def test_wait_seconds_zero_says_the_offers_go_unheard():
    """Passing 0 on a page with buttons leaves every button dead once the turn
    ends, so the result says so. Passing 0 on a page with no offers, a goodbye,
    is fine."""
    offering = "# Next\n\n- [ ] One\n- [ ] Two\n"
    shown, _raw = _call("show", {"markdown": offering, "wait_seconds": 0})
    issues = [i["code"] for i in shown["issues"]]
    assert issues == ["boxes-without-commit"] and len(shown["offers"]) == 2, shown
    assert shown["heard"] == {
        "text": "Not listening: you passed wait_seconds 0, so this page's 2 offers"
        " reach you only while a wait is open. Call `wait_for_event` "
        + mcp_demo.WAIT_AGAIN,
        "events": [],
    }, shown
    marked, _raw = _call(
        "mark",
        {
            "message_id": shown["message_id"],
            "x": 0,
            "state": "checked",
            "wait_seconds": 0,
        },
    )
    assert marked["heard"]["events"] == [], marked
    assert "this page's 2 offers reach you" in marked["heard"]["text"], marked

    one, _raw = _call("show", {"markdown": "# Next\n\n- [ ] One\n", "wait_seconds": 0})
    assert "this page's 1 offer reaches you" in one["heard"]["text"], one

    goodbye, _raw = _call(
        "show", {"markdown": "# Goodbye\n\nThanks.\n", "wait_seconds": 0}
    )
    assert not goodbye["issues"] and "heard" not in goodbye, goodbye
    defaulted, _raw = _call("show", {"markdown": offering})
    assert "heard" not in defaulted, "only these tests turn the default off"

    _drain()
    listened, _raw = _call("show", {"markdown": offering, "wait_seconds": 1})
    assert "Not listening" not in listened["heard"]["text"], listened
    assert "`wait_for_event` again" in listened["heard"]["text"], listened
    print("  ✓  wait_seconds 0 says a page's offers go unheard; a goodbye stays quiet")


def test_the_page_a_window_opens_for_listens():
    """The user who has a new window is using it, so a window's first page
    listens even when told 0, and even when it offers nothing: whoever opened the
    window, this server or a client that connected. A later page told 0 does not.
    A stand-in process is
    launched, as the window would be; a `WireClient` connects as any other."""

    class _Window:
        def poll(self):
            return None  # still open

        def terminate(self):
            pass

    offering = "# Next\n\n- [ ] One\n- [ ] Two\n"

    def show(server, markdown: str = offering) -> dict:
        args = {"markdown": markdown, "wait_seconds": 0}
        with contextlib.redirect_stdout(io.StringIO()):
            result: Any = asyncio.run(server.call_tool("show", args))
        return json.loads(result.content[0].text)

    def connected(launch_window: bool = False):
        server, demo = mcp_demo.build_demo_server(None, launch_window=launch_window)
        if launch_window:
            return server, demo, None
        with contextlib.redirect_stdout(io.StringIO()):
            client = WireClient(demo.served().url, bearer=demo.bearer)
        client.start()
        assert _until(lambda: demo.served().conversation.watchers == 1)
        return server, demo, client

    popen, default = mcp_demo.subprocess.Popen, mcp_demo.SHOW_WAIT_SECONDS
    mcp_demo.subprocess.Popen = lambda *a, **k: _Window()  # type: ignore[assignment]
    mcp_demo.SHOW_WAIT_SECONDS = 1
    opened: list = []
    try:
        for launch_window in (True, False):
            server, demo, client = connected(launch_window)
            opened.append((demo, client))
            first = show(server)
            assert first["heard"]["text"].startswith(mcp_demo.OPENED_LISTENS), first
            assert "No click or message within 1 s" in first["heard"]["text"], first
            second = show(server)
            assert second["heard"]["text"].startswith("Not listening"), second

        server, demo, client = connected()
        opened.append((demo, client))
        goodbye = show(server, "# Goodbye\n\nThanks.\n")
        assert not goodbye["offers"], goodbye
        assert goodbye["heard"]["text"].startswith(mcp_demo.OPENED_LISTENS), goodbye
        assert "heard" not in show(server, "# Goodbye\n\nThanks.\n")
    finally:
        mcp_demo.subprocess.Popen, mcp_demo.SHOW_WAIT_SECONDS = popen, default
        for demo, client in opened:
            if client is not None:
                client.close()
            demo.close()
    print("  ✓  a window's first page listens though told 0, launched or connected")


def test_an_answer_to_the_user_listens_for_a_grace():
    """Told 0, an answer to a click or a prompt still listens a short grace and
    says so: the user who just acted watches for the answer.
    One told 0 with nothing to answer does not, nor does one answering a batch of
    several, so a batch never listens mid-way. The grace is shortened here."""
    page = "# Pick\n\n[A](agent:a) [B](agent:b)\n"
    shown, _raw = _call("show", {"markdown": page})
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    grace, mcp_demo.GRACE_SECONDS = mcp_demo.GRACE_SECONDS, 1
    try:
        _connected(client)
        quiet, _raw = _call("show", {"markdown": page, "wait_seconds": 0})
        assert quiet["heard"]["text"].startswith("Not listening"), quiet
        client.send_event(quiet["message_id"], 0)
        assert _mine(quiet["message_id"])["x"] == 0
        answer, _raw = _call("show", {"markdown": page, "wait_seconds": 0})
        said = mcp_demo.GRACE_LISTENS.format(1) + " No click or message within 1 s"
        assert answer["heard"]["text"].startswith(said), answer
        after, _raw = _call("show", {"markdown": page, "wait_seconds": 0})
        assert after["heard"]["text"].startswith("Not listening"), after

        client.send_prompt("and C?")
        typed, _raw = _call("wait_for_event", {"timeout_seconds": 10})
        assert typed["kind"] == "prompt", typed
        marked, _raw = _call(
            "mark",
            {
                "message_id": after["message_id"],
                "x": 0,
                "state": "disabled",
                "wait_seconds": 0,
            },
        )
        assert marked["heard"]["text"].startswith(said), marked

        fresh, _raw = _call("show", {"markdown": page, "wait_seconds": 0})
        client.send_event(fresh["message_id"], 0)
        client.send_event(fresh["message_id"], 1)
        assert _until(lambda: demo.served().conversation.events.qsize() > 1)
        batch, _raw = _call("wait_for_event", {"timeout_seconds": 10})
        assert len(batch["events"]) == 2, batch
        first, _raw = _call(
            "mark",
            {
                "message_id": fresh["message_id"],
                "x": 0,
                "state": "disabled",
                "wait_seconds": 0,
            },
        )
        assert first["heard"]["text"].startswith("Not listening"), first
    finally:
        mcp_demo.GRACE_SECONDS = grace
        _closed(client)
    print("  ✓  an answer to a click or a prompt listens a grace though told 0")


def test_a_grace_waits_while_the_user_types():
    """A grace listens past its own length while the window says the user is
    typing (`k` frames): it returns the prompt they send, ends
    a pause after typing stops, and never outlasts its maximum. Every length is
    shortened here: a 1 s grace, a 1 s pause, a 3 s maximum, a frame each 0.2 s."""
    page = "# Pick\n\n[A](agent:a) [B](agent:b)\n"
    _server, demo = _demo()
    saved = (
        mcp_demo.GRACE_SECONDS,
        mcp_demo.TYPING_PAUSE_SECONDS,
        mcp_demo.GRACE_MAX_SECONDS,
        wire_client.TYPING_EVERY_SECONDS,
    )
    mcp_demo.GRACE_SECONDS, mcp_demo.TYPING_PAUSE_SECONDS = 1, 1.0
    mcp_demo.GRACE_MAX_SECONDS, wire_client.TYPING_EVERY_SECONDS = 3, 0.2
    client = WireClient(demo.served().url, bearer=demo.bearer)

    def typing(seconds: float, then: str | None = None) -> threading.Thread:
        def run() -> None:
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                client.typing()
                time.sleep(0.05)
            if then is not None:
                client.send_prompt(then)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def answered(*typed) -> tuple[dict, float]:
        clicked, _raw = _call("show", {"markdown": page, "wait_seconds": 0})
        client.send_event(clicked["message_id"], 0)
        _mine(clicked["message_id"])  # the one click a grace answers
        thread = typing(*typed)
        started = time.monotonic()
        answer, _raw = _call("show", {"markdown": page, "wait_seconds": 0})
        elapsed = time.monotonic() - started
        thread.join()
        return answer["heard"], elapsed

    try:
        _connected(client)
        heard, elapsed = answered(2.0, "and C, slowly typed?")
        assert heard.get("kind") == "prompt", heard
        assert heard["prompt"] == "and C, slowly typed?" and elapsed > 1.5, elapsed
        assert heard["text"].startswith(mcp_demo.GRACE_LISTENS.format(1)), heard

        heard, elapsed = answered(0.5)  # typing stops: a pause later, it ends
        assert heard["events"] == [] and "No click" in heard["text"], heard
        assert 1.2 < elapsed < 2.5, elapsed

        heard, elapsed = answered(4.0)  # typing goes on: the maximum holds
        assert heard["events"] == [] and "within 3 s" in heard["text"], heard
        assert 2.8 < elapsed < 3.8, elapsed
    finally:
        (
            mcp_demo.GRACE_SECONDS,
            mcp_demo.TYPING_PAUSE_SECONDS,
            mcp_demo.GRACE_MAX_SECONDS,
            wire_client.TYPING_EVERY_SECONDS,
        ) = saved
        _closed(client)
    print("  ✓  a grace waits while the user types, until a pause or its maximum")


def test_an_image_ratio_warning_stops_show_listening():
    """Every warning holds the window until the page is fixed, `image-ratio`
    included: listening past it, agents left the ratio unset (ADR-611). Only notes
    let `show` listen."""
    ratio = {"level": "warning", "code": "image-ratio", "message": "…"}
    other = {"level": "warning", "code": "image-param", "message": "…"}
    note = {"level": "note", "code": "repeated-offer", "message": "…"}
    assert mcp_demo._listens([]) and mcp_demo._listens([note])
    assert not mcp_demo._listens([ratio]) and not mcp_demo._listens([ratio, note])
    assert not mcp_demo._listens([other])
    print("  ✓  an image-ratio warning stops show listening, as every warning does")


TESTS = [
    restores_server_policy(test)
    for test in [
        test_an_image_ratio_warning_stops_show_listening,
        test_a_note_leaves_show_listening,
        test_the_demo_offers_fifteen_tools,
        test_show_click_hear_mark,
        test_a_click_says_what_comes_next_and_carries_its_action,
        test_a_click_says_which_section_it_came_from,
        test_listening_again_answers_the_clicks_it_was_handed,
        test_bad_marks_and_quiet_waits,
        test_the_window_hears_the_state_and_its_prompts_reach_the_agent,
        test_one_wait_drains_the_queue_but_never_batches_a_prompt,
        test_a_press_commits_the_values_the_user_adjusted,
        test_a_commit_carried_settle_never_reaches_the_agent,
        test_a_commit_press_writes_its_values_into_the_servers_page,
        test_mark_sets_a_value_without_resending_the_document,
        test_mark_moves_a_bar_by_its_key,
        test_a_feed_moves_a_bar_without_a_turn,
        test_idle_is_derived_not_asserted,
        test_a_wait_ends_as_a_timeout_not_as_the_host_killing_it,
        test_a_session_holds_the_turn,
        test_an_abandoned_wait_never_takes_the_next_click,
        test_show_and_mark_listen_after_replying,
        test_a_timeout_counts_the_live_offers,
        test_wait_seconds_zero_says_the_offers_go_unheard,
        test_the_page_a_window_opens_for_listens,
        test_an_answer_to_the_user_listens_for_a_grace,
        test_a_grace_waits_while_the_user_types,
        test_a_prompt_typed_at_an_older_page_says_so,
        test_going_back_resends_an_earlier_page_as_it_was,
        test_any_id_a_page_had_goes_back_to_its_latest_version,
        test_patch_changes_one_part_and_going_back_is_one_call,
        test_a_closed_window_interrupts_a_waiting_agent,
        test_show_drops_a_presence_queued_before_it,
        test_a_put_back_presence_is_served_only_while_true,
        test_showing_reports_what_the_user_asked_for,
        test_working_ends_without_the_agent_saying_so,
        test_a_port_asked_for_is_served,
        test_only_the_launched_window_holds_the_servers_secret,
        test_a_launcher_may_choose_the_secret_and_nobody_else_gets_in,
        test_an_unset_or_short_launcher_secret_is_minted_instead,
        test_a_taken_port_stops_the_launch,
    ]
]

if __name__ == "__main__":
    print("MCP Demo Tests")
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
