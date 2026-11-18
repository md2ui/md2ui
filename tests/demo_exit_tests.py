"""
Unit tests for how the demo shell (ADR-602) ends with its session.

A host ends an MCP session by closing the server's stdin and, after a grace
period, with SIGTERM. The demo server owns a child process, the window, and it
must not outlive the server either way.

Pinned here:

  * on SIGTERM the server closes what it opened — the window first — and exits,
    rather than hanging on the stdio reader's thread or leaving the window open.

Not pinned, because a server cannot act on it: a SIGKILL of the server itself
leaves its window running.

Run with: uv run python tests/demo_exit_tests.py
"""

import os
import subprocess
import sys
import time
import unittest

# A demo whose window is a sleeper, ended as SIGTERM ends it; prints the window's
# pid first, so the test can look for it afterwards.
_TERMINATED = """
import subprocess, sys
from md2ui import mcp_demo
demo = mcp_demo._Demo(None, launch_window=True)
demo._window = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
print(demo._window.pid, flush=True)
mcp_demo._terminated(demo)
"""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_sigterm_closes_the_window_and_exits():
    """The handler the demo installs for SIGTERM ends the window and the process."""
    if sys.platform == "win32":
        # A Windows host ends a process with TerminateProcess, which runs no
        # handler, and os.kill(pid, 0) there terminates rather than asks.
        raise unittest.SkipTest("no SIGTERM is delivered here; `kill -0` is POSIX")
    run = subprocess.run(
        [sys.executable, "-c", _TERMINATED], capture_output=True, text=True, timeout=60
    )
    assert run.returncode == 128 + 15, run.stderr
    window = int(run.stdout.split()[0])
    deadline = time.monotonic() + 5
    while _alive(window) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(window), "the window outlived its server"
    print("  ✓  SIGTERM closes the window and exits")


TESTS = [
    test_sigterm_closes_the_window_and_exits,
]

if __name__ == "__main__":
    print("Demo Exit Tests")
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
