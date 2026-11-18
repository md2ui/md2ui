"""
A long-running md2ui server says when the md2ui code it loaded has changed.

A Claude Code session keeps the plugin's MCP server it started with: after md2ui
changes, that server still serves its old tools, and nothing would say so. The
server records the newest of md2ui's own source files when it starts; once one is
newer, every dict a tool returns carries ``stale_server`` and every string ends
with the same line, so the agent and the owner both see it. Before that, nothing
changes.

Run with: uv run python tests/stale_code_tests.py
"""

import asyncio
import inspect
import os
import tempfile
import time
from pathlib import Path

from md2ui.stale_code import StaleCode, noting


def _tree() -> Path:
    root = Path(tempfile.mkdtemp())
    (root / "a.py").write_text("x = 1\n")
    return root


def _touch_later(path: Path) -> None:
    later = time.time() + 60
    os.utime(path, (later, later))


def test_nothing_is_said_until_the_code_changes():
    root = _tree()
    stale = StaleCode(root, every=0.0)
    assert stale.note() is None
    _touch_later(root / "a.py")
    note = stale.note()
    assert note is not None and "/mcp" in note, note
    print("  ✓  the note appears once md2ui's source is newer than the server")


def test_every_dict_and_string_a_tool_returns_carries_it():
    root = _tree()
    stale = StaleCode(root, every=0.0)
    registered: dict = {}

    def tool(**_kw):
        def register(fn):
            registered[fn.__name__] = fn
            return fn

        return register

    note_tool = noting(tool, stale)

    @note_tool(annotations=None)
    async def answers(text: str, n: int = 1) -> dict:
        """An answer."""
        return {"text": text}

    @note_tool()
    def says(word: str) -> str:
        return word

    assert inspect.signature(registered["answers"]) == inspect.signature(answers)
    assert registered["answers"].__doc__ == "An answer."
    assert asyncio.run(registered["answers"]("hi")) == {"text": "hi"}, "fresh"
    _touch_later(root / "a.py")
    out = asyncio.run(registered["answers"]("hi"))
    assert out["text"] == "hi" and "/mcp" in out["stale_server"], out
    said = asyncio.run(registered["says"]("hi"))
    assert said.startswith("hi\n\n") and said.endswith(stale.note() or ""), said
    print("  ✓  a stale server's dicts carry stale_server and its strings end with it")


def test_the_demo_server_notes_it():
    from md2ui import mcp_server
    from md2ui.pipeline.render_settings import VIEW
    from md2ui.utils.fetch_policy import POLICY

    # build_server sets the process's fetch policy; the tests after this share it.
    was = POLICY.remote, VIEW.placeholder_images
    try:
        plain = mcp_server.build_server()
        noted = mcp_server.build_server(note_stale=True)
    finally:
        POLICY.remote, VIEW.placeholder_images = was
    assert getattr(plain.tool, "stale_code", None) is None
    assert isinstance(getattr(noted.tool, "stale_code", None), StaleCode)
    print("  ✓  build_server notes stale code only when asked (the demo plugin)")


TESTS = [
    test_nothing_is_said_until_the_code_changes,
    test_every_dict_and_string_a_tool_returns_carries_it,
    test_the_demo_server_notes_it,
]

if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"All {len(TESTS)} tests passed.")
