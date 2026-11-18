"""Whether the md2ui code a running server loaded has changed on disk since.

A Claude Code session keeps the MCP server it started: after md2ui changes,
that server still serves the tools it loaded, and nothing says so. A server
built with ``note_stale`` records the newest of md2ui's own source files when it
starts; once one is newer, what its tools return says so, in one line, where
the agent and the owner both read it.
"""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from pathlib import Path

import md2ui


def _newest(root: Path) -> float:
    return max((p.stat().st_mtime for p in root.rglob("*.py")), default=0.0)


class StaleCode:
    """The newest source time at start, and whether the tree has passed it.
    Checked at most every *every* seconds: one walk of md2ui's files per check."""

    def __init__(self, root: Path | None = None, every: float = 5.0) -> None:
        self._root = root if root is not None else Path(md2ui.__file__).parent
        self._loaded = _newest(self._root)
        self._started = time.localtime()
        self._every = every
        self._checked = float("-inf")
        self._stale = False

    def note(self) -> str | None:
        """The line to show once md2ui has changed, else None."""
        now = time.monotonic()
        if not self._stale and now - self._checked >= self._every:
            self._checked = now
            self._stale = _newest(self._root) > self._loaded
        if not self._stale:
            return None
        return (
            f"md2ui changed since this server started "
            f"({time.strftime('%H:%M', self._started)}); restart it with /mcp "
            "for the current tools."
        )


def noting(tool: Callable, stale: StaleCode) -> Callable:
    """*tool* (an ``MCPServer.tool``) whose tools add *stale*'s note: a dict gains
    ``stale_server``, a string ends with the line. Lists and images are left as
    they are. Each wrapper keeps its tool's signature, which the schema reads."""

    def registering(*args, **kwargs):
        register = tool(*args, **kwargs)

        def decorate(fn):
            @functools.wraps(fn)
            async def wrapped(*a, **k):
                out = fn(*a, **k)
                if inspect.isawaitable(out):
                    out = await out
                note = stale.note()
                if note is None:
                    return out
                if isinstance(out, dict):
                    return {**out, "stale_server": note}
                if isinstance(out, str):
                    return f"{out}\n\n{note}"
                return out

            return register(wrapped)

        return decorate

    registering.stale_code = stale  # type: ignore[attr-defined]
    return registering
