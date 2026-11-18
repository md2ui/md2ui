"""
Unit tests for a connected window whose server goes away.

The window stays open: the page is still worth reading. What changes is that
nothing more can reach the agent, and the window says so rather than looking
live.

Pinned here:

  * the app's wire client turns ``disconnected`` when its server stops cleanly
    and when it dies without a word (SIGKILL), wakes the window's loop, and
    re-sends nothing afterwards;
  * the prompt bar then says it in the field and in a notice above the bar, and
    a draft stays in the field: Enter or Send takes nothing from it.

Run with: uv run python tests/disconnected_window_tests.py
"""

import contextlib
import io
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import skia

from md2ui import session
from md2ui.app_chrome import ChromeStyle
from md2ui.app_prompt import DISCONNECTED_NOTICE, PLACEHOLDERS, PromptBar
from md2ui.wire_client import DISCONNECTED, WireClient
from md2ui.wire_server import Conversation, Served

PAGE = "# Ask\n\nReady?\n\n[Yes](agent:yes)\n"


def _connected(url: str) -> tuple[WireClient, list[int]]:
    """A started client that has the page, and the count of its wake-ups."""
    woken: list[int] = []
    client = WireClient(url, on_ready=lambda: woken.append(1))
    deadline = time.monotonic() + 15
    while True:  # a server in a subprocess may still be starting
        try:
            client.start()
            break
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)
    assert client.wait_first(10) is not None, "no page arrived"
    assert client.connected
    return client, woken


def _until_disconnected(client: WireClient) -> None:
    deadline = time.monotonic() + 5
    while client.connected and time.monotonic() < deadline:
        time.sleep(0.02)
    assert client.state == DISCONNECTED and not client.connected, client.state


def test_a_stopped_server_leaves_the_window_disconnected():
    with contextlib.redirect_stdout(io.StringIO()):
        served = Served(Conversation(session.load_grouping_kit()))
        served.call(served.conversation.send(PAGE))
    client, woken = _connected(served.url)
    seq, wakes = client.state_seq, len(woken)
    served.stop()
    _until_disconnected(client)
    assert client.state_seq > seq and len(woken) > wakes, "the loop was not woken"
    assert client.resend_stale("m", [], {}) == []
    print("  ✓  a server that stops leaves the window disconnected, and woken")


def test_a_killed_server_leaves_the_window_disconnected():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "page.md"
        page.write_text(PAGE)
        server = subprocess.Popen(
            [sys.executable, "-m", "md2ui.wire_server", str(page), "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            client, _woken = _connected(f"ws://127.0.0.1:{port}/ws")
            server.kill()  # SIGKILL on POSIX, TerminateProcess on Windows
            _until_disconnected(client)
        finally:
            server.kill()
            server.wait()
    print("  ✓  a server killed without a word leaves the window disconnected")


def test_the_bar_says_disconnected_and_keeps_the_draft():
    style = ChromeStyle()
    bar = PromptBar(skia.Typeface.MakeDefault(), style)
    assert bar.sync("l", 1)
    bar.editor.insert("one more thing")
    assert bar.sync(DISCONNECTED, 2)
    assert not bar.can_send and not bar.locked
    assert bar.submit() == "" and bar.editor.text == "one more thing"
    assert PLACEHOLDERS[DISCONNECTED].startswith("Disconnected")
    assert DISCONNECTED_NOTICE.startswith("Disconnected")
    w, h = 900, 300
    bitmap = skia.Bitmap()
    bitmap.allocPixels(skia.ImageInfo.MakeN32Premul(w, h))
    bitmap.eraseARGB(0, 0, 0, 0)
    bar.draw(skia.Canvas(bitmap), w, h)
    pill_y = int(h - style.bar_h - 8 - 16)  # inside the notice above the bar
    pill = bitmap.getColor(14, pill_y)
    assert abs((pill & 0xFFFFFF) - (style.notice_bg & 0xFFFFFF)) < 8, hex(pill)
    print("  ✓  the bar says it is disconnected, and a draft stays in the field")


TESTS = [
    test_a_stopped_server_leaves_the_window_disconnected,
    test_a_killed_server_leaves_the_window_disconnected,
    test_the_bar_says_disconnected_and_keeps_the_draft,
]

if __name__ == "__main__":
    print("Disconnected Window Tests")
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
