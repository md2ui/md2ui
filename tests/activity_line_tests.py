"""
Unit tests for the working line (ADR-613): a Claude Code hook posts what the
agent is doing, the demo shell says it as the state frame's note ``n`` while the
agent works, and the window draws it under the working animation.

The window is not launched; a ``WireClient`` stands in for it, as in
``mcp_demo_tests``. The hook runs in-process, on the dict Claude Code would hand
it on stdin.

Pinned here:

  * a label never shows a command, a path or content: a Bash call's own
    ``description``, else the tool and a file's basename, else the tool; one
    line, at most ``MAX_LABEL`` characters; the demo's own tools say nothing;
  * the server advertises where to post only inside a Claude Code session, in a
    file only this user can read, named for the session; an id that could name
    another path is refused, and closing the shell removes the file;
  * the route refuses a browser and a wrong secret;
  * a step lands as ``n`` under ``w`` and re-arms ``w``'s deadline; under ``l``
    it is dropped; ``l`` or ``i`` drops the note; the hook's ``false`` switch
    posts nothing;
  * the bar draws the step only while the agent works.

Run with: uv run python tests/activity_line_tests.py
"""

import asyncio
import contextlib
import io
import json
import os
import secrets
import stat
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import skia

from server_policy import restores_server_policy

from md2ui import mcp_demo, mcp_demo_activity
from md2ui.app_prompt import PromptBar
from md2ui.mcp_demo_activity import MAX_LABEL, advert_path, label, post
from md2ui.wire_client import StateWords, WireClient

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "data/markdown/tests/tests-link-actions.md"
mcp_demo.SHOW_WAIT_SECONDS = 0
mcp_demo_activity.ADVERTS = Path(tempfile.mkdtemp(prefix="md2ui-activity-")) / "a"
SESSION = f"test-{secrets.token_hex(4)}"

_DEMO: Any = None


def _demo() -> Any:
    global _DEMO
    if _DEMO is None:
        os.environ[mcp_demo_activity.SESSION_ENV] = SESSION
        try:
            _DEMO = mcp_demo.build_demo_server(None, launch_window=False)
            _call("show", {"markdown": FIXTURE.read_text()})  # serves, advertises
        finally:
            del os.environ[mcp_demo_activity.SESSION_ENV]
    return _DEMO


def _call(name: str, arguments: dict) -> Any:
    server, _state = _DEMO
    with contextlib.redirect_stdout(io.StringIO()):
        return asyncio.run(server.call_tool(name, arguments))


def _until(check, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.02)
    return False


def _hook(tool: str, given: dict, session: str = SESSION) -> bool:
    return post({"session_id": session, "tool_name": tool, "tool_input": given})


def test_a_label_never_shows_a_command_a_path_or_content():
    command = {"command": "rm -rf /Users/me/secret", "description": "Clean the build"}
    assert label("Bash", command) == "Clean the build"
    assert label("Bash", {"command": "cat ~/.ssh/id_rsa"}) == "Bash"
    assert label("Edit", {"file_path": "/Users/me/x/app.py", "new_string": "k"}) == (
        "Edit app.py"
    )
    assert label("NotebookEdit", {"notebook_path": "/a/b/n.ipynb"}) == (
        "NotebookEdit n.ipynb"
    )
    assert label("Grep", {"pattern": "password=", "path": "/srv/"}) == "Grep srv"
    assert label("WebFetch", {"url": "https://x.test/?token=1"}) == "WebFetch"
    assert label("mcp__gmail__search_threads", {"query": "bank"}) == "search_threads"
    assert label("mcp__plugin_md2ui-demo_md2ui-demo__show", {}) is None
    assert label("mcp__md2ui-demo__mark", {}) is None
    long = label("Bash", {"description": "Run\nthe   " + "very " * 40 + "long"})
    assert long is not None and "\n" not in long and len(long) == MAX_LABEL, long
    print("  ✓  labels: a Bash description, else tool and basename; never a command")


def test_the_server_advertises_only_inside_a_session():
    _server, demo = _demo()
    advert = advert_path(SESSION)
    assert advert is not None and advert.is_file(), advert
    assert stat.S_IMODE(advert.stat().st_mode) == 0o600, oct(advert.stat().st_mode)
    assert stat.S_IMODE(advert.parent.stat().st_mode) == 0o700
    url = json.loads(advert.read_text())["url"]
    assert url.startswith(f"http://127.0.0.1:{demo.served().port}/activity/"), url
    for bad in ("", "../x", "a/b", "a.json"):
        assert advert_path(bad) is None, bad
    saved = os.environ.pop(mcp_demo_activity.SESSION_ENV, None)
    try:
        assert mcp_demo_activity.advertise("http://127.0.0.1:1/x") is None
    finally:
        if saved is not None:
            os.environ[mcp_demo_activity.SESSION_ENV] = saved
    print("  ✓  advertised per session, 0600 in a 0700 folder; nothing outside one")


def test_the_route_refuses_a_browser_and_a_wrong_secret():
    _demo()
    advert = advert_path(SESSION)
    assert advert is not None
    url = json.loads(advert.read_text())["url"]
    for target, headers, code in (
        (url, {"Origin": "http://evil.test"}, 403),
        (url[:-3] + "xyz", {}, 404),
    ):
        request = urllib.request.Request(target, b"Edit a.py", headers, method="POST")
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            assert exc.code == code, (target, exc.code)
            continue
        raise AssertionError(f"{headers or 'a wrong secret'} was let in")
    print("  ✓  the route refuses a browser's post and a wrong secret")


def test_a_step_shows_while_working_and_rearms_the_deadline():
    _server, demo = _demo()
    client = WireClient(demo.served().url, bearer=demo.bearer)
    was, mcp_demo.IDLE_AFTER_WORKING = mcp_demo.IDLE_AFTER_WORKING, 0.6
    try:
        client.start()
        client.wait_first(10)
        _call("wait_for_event", {"timeout_seconds": 1})  # the join's own news
        heard: dict = {}
        waiting = threading.Thread(
            target=lambda: heard.update(
                {"r": _call("wait_for_event", {"timeout_seconds": 10})}
            )
        )
        waiting.start()
        assert _until(lambda: client.state == "l"), client.state
        assert _hook("Read", {"file_path": "/x/notes.md"})  # posted, and dropped
        time.sleep(0.2)
        assert client.state == "l" and client.said.note is None, client.said
        client.send_prompt("Fix the bar")
        waiting.join(15)
        assert _until(lambda: client.state == "w"), client.state
        assert _hook("Edit", {"file_path": "/Users/me/src/app_prompt.py"})
        assert _until(lambda: client.said.note == "Edit app_prompt.py"), client.said
        # Steps keep coming for twice the deadline: `w` stands throughout.
        end = time.monotonic() + 1.2
        while time.monotonic() < end:
            assert client.state == "w", "a step re-arms the deadline"
            _hook("Bash", {"command": "make check", "description": "Run the gate"})
            time.sleep(0.2)
        assert client.said.note == "Run the gate", client.said
        assert _until(lambda: client.state == "i", 3.0), "the deadline still ends w"
        assert client.said.note is None, "i drops the step"
    finally:
        mcp_demo.IDLE_AFTER_WORKING = was
        client.close()
    print("  ✓  a step is w's note and re-arms its deadline; l ignores it, i drops it")


def test_the_switch_turns_the_hook_off():
    _server, demo = _demo()
    advert = advert_path(SESSION)
    assert advert is not None
    call = {"session_id": SESSION, "tool_name": "Edit", "tool_input": {}}
    sent: list[bool] = []
    real = mcp_demo_activity.post
    mcp_demo_activity.post = lambda c: sent.append(True) or True
    stdin = sys.stdin
    try:
        for switch, expected in ((["false"], []), (["true"], [True]), ([], [True])):
            sent.clear()
            sys.stdin = io.StringIO(json.dumps(call))
            mcp_demo_activity.main(switch)
            assert sent == expected, (switch, sent)
    finally:
        mcp_demo_activity.post, sys.stdin = real, stdin
    assert not _hook("Edit", {}, session="nobody"), "no advert, nothing posted"
    demo.close()
    assert not advert.exists(), "closing the shell removes its advert"
    print(
        "  ✓  `false` posts nothing; an unknown session posts nothing; close cleans up"
    )


def test_the_bar_draws_the_step_only_while_working():
    def drawn(state: str, note: str | None) -> bytes:
        bar = PromptBar(skia.Typeface.MakeDefault())
        bar.sync(state, 1, said=StateWords(note, None))
        surface = skia.Surface(480, 120)
        bar.draw_step(surface.getCanvas(), 240, 40, 480)
        return bytes(surface.makeImageSnapshot().tobytes())

    blank = drawn("w", None)
    assert drawn("w", "Edit app.py") != blank, "the step is drawn while working"
    for state in ("l", "i"):
        assert drawn(state, "Edit app.py") == blank, f"no step under {state}"
    print("  ✓  the step is drawn under w and nowhere else")


# Each test starts or uses a server, which switches the fetch policy: put it back.
TESTS = [
    restores_server_policy(test)
    for test in (
        test_a_label_never_shows_a_command_a_path_or_content,
        test_the_server_advertises_only_inside_a_session,
        test_the_route_refuses_a_browser_and_a_wrong_secret,
        test_a_step_shows_while_working_and_rearms_the_deadline,
        test_the_switch_turns_the_hook_off,
        test_the_bar_draws_the_step_only_while_working,
    )
]

if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"\n{len(TESTS)} activity line tests passed")
