"""
Unit tests for the agent's question in the prompt bar (ADR-613): ``show`` and
``mark`` take ``ask``, the server says it as the state frame's ``ph`` while the
agent listens, and the window shows it as its field's placeholder.

The window is not launched; a ``WireClient`` stands in for it, as in
``mcp_demo_tests``.

Pinned here:

  * ``ph`` is a well-formed state key up to 200 characters; a longer one, or one
    that is not text, is refused (the golden frames in ``protocol/examples``
    cover the schema side);
  * ``show(ask=…)`` puts the question on every ``l`` until the agent's next
    ``show`` or ``mark``; input arriving (``w``) drops it, a later listen says it
    again, and a ``show`` or ``mark`` without ``ask`` clears it;
  * the bar shows the question as its placeholder only while the agent listens:
    working, idle and before any state it keeps its own lines, and a draft the
    user typed covers it.

Run with: uv run python tests/prompt_ask_tests.py
"""

import asyncio
import contextlib
import io
import threading
import time
from pathlib import Path
from typing import Any

import skia

from server_policy import restores_server_policy

from md2ui import mcp_demo
from md2ui.app_prompt import PLACEHOLDERS, PromptBar
from md2ui.wire import FrameError, decode_server
from md2ui.wire_client import StateWords, WireClient

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "data/markdown/tests/tests-link-actions.md"
QUESTION = "Any note for the rider?"
mcp_demo.SHOW_WAIT_SECONDS = 0

_DEMO: Any = None


def _demo() -> Any:
    global _DEMO
    if _DEMO is None:
        _DEMO = mcp_demo.build_demo_server(None, launch_window=False)
    return _DEMO


def _call(name: str, arguments: dict) -> Any:
    server, _state = _demo()
    with contextlib.redirect_stdout(io.StringIO()):
        return asyncio.run(server.call_tool(name, arguments))


def _until(check, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.02)
    return False


def _listening(client: WireClient) -> threading.Thread:
    """A wait for the user, open on its own thread until something arrives."""
    waiting = threading.Thread(
        target=lambda: _call("wait_for_event", {"timeout_seconds": 10})
    )
    waiting.start()
    assert _until(lambda: client.state == "l"), client.state
    return waiting


def test_ph_is_a_state_key_of_at_most_200_characters():
    ok = decode_server('{"t":"s","s":"l","ph":"' + "x" * 200 + '"}')
    assert ok["ph"] == "x" * 200
    for bad in ('"' + "x" * 201 + '"', "7"):
        try:
            decode_server('{"t":"s","s":"l","ph":' + bad + "}")
        except FrameError:
            continue
        raise AssertionError(f"ph {bad[:12]}… was accepted")
    print("  ✓  ph: text up to 200 characters, refused otherwise")


def test_the_question_rides_every_listen_until_the_next_answer():
    _call("show", {"markdown": FIXTURE.read_text(), "ask": QUESTION})
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    was, mcp_demo.IDLE_AFTER_WORKING = mcp_demo.IDLE_AFTER_WORKING, 300.0
    try:
        client.start()
        client.wait_first(10)
        _call("wait_for_event", {"timeout_seconds": 1})  # the join's own news
        waiting = _listening(client)
        assert client.said == StateWords(None, QUESTION), client.said
        client.send_prompt("Leave it at the door")
        waiting.join(15)
        assert _until(lambda: client.state == "w"), client.state
        assert client.said.placeholder is None, "work drops the question"
        waiting = _listening(client)
        assert client.said.placeholder == QUESTION, "a later listen asks again"
        client.send_prompt("and ring twice")
        waiting.join(15)
        _call("show", {"markdown": FIXTURE.read_text()})  # answered, no new ask
        waiting = _listening(client)
        assert client.said.placeholder is None, "a show without ask clears it"
        client.send_prompt("thanks")
        waiting.join(15)
        mid = demo.served().conversation.latest
        _call("mark", {"message_id": mid, "x": 0, "state": "disabled", "ask": "Why?"})
        waiting = _listening(client)
        assert client.said.placeholder == "Why?", "mark asks as show does"
        client.send_prompt("because")
        waiting.join(15)
    finally:
        mcp_demo.IDLE_AFTER_WORKING = was
        client.close()
    print("  ✓  ask rides every l until the next show or mark; w drops it")


def test_the_bar_shows_the_question_only_while_listening():
    bar = PromptBar(skia.Typeface.MakeDefault())
    asked = StateWords(None, QUESTION)
    bar.sync("l", 1, said=asked)
    assert bar.placeholder == QUESTION, bar.placeholder
    for state in ("w", "i"):
        bar.sync(state, 2 if state == "w" else 3, said=asked)
        assert bar.placeholder == PLACEHOLDERS[state], (state, bar.placeholder)
    bar.sync("l", 4, said=StateWords())
    assert bar.placeholder == PLACEHOLDERS["l"], "a frame without ph clears it"
    bar.sync("l", 5, said=asked)
    bar.lock_for_reply()  # sent to a listening agent: blocked before `w` lands
    assert bar.placeholder == PLACEHOLDERS["w"], bar.placeholder

    def drawn(said: StateWords, draft: str = "") -> bytes:
        bar = PromptBar(skia.Typeface.MakeDefault())
        bar.sync("l", 1, said=said)
        bar.editor.insert(draft)
        surface = skia.Surface(480, 80)
        bar.draw(surface.getCanvas(), 480, 80)
        return bytes(surface.makeImageSnapshot().tobytes())

    assert drawn(asked) != drawn(StateWords()), "the question is drawn"
    assert drawn(asked, "Hi") == drawn(StateWords(), "Hi"), "a draft covers it"
    print("  ✓  the bar says the question while listening, its own lines otherwise")


# Each test starts or uses a server, which switches the fetch policy: put it back.
TESTS = [
    restores_server_policy(test)
    for test in (
        test_ph_is_a_state_key_of_at_most_200_characters,
        test_the_question_rides_every_listen_until_the_next_answer,
        test_the_bar_shows_the_question_only_while_listening,
    )
]

if __name__ == "__main__":
    try:
        for test in TESTS:
            test()
    finally:
        if _DEMO is not None:
            _DEMO[1].close()
    print(f"\n{len(TESTS)} prompt ask tests passed")
