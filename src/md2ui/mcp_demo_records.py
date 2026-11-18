"""The demo's tools over the server's records of what it sent
(ADR-611).

The agent owns every page and the window holds none (ADR-404). These tools hand
back what the server already recorded of the agent's own pages, so the agent does
not keep that record in its context, where compaction and a restart erase it.
They decide nothing.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from md2ui.mcp_demo_told import handled
from md2ui.wire_frames import FrameError

if TYPE_CHECKING:
    from md2ui.mcp_demo import _Demo
    from md2ui.wire import MessageLog
    from md2ui.wire_server import Served

READS = ToolAnnotations(read_only_hint=True, open_world_hint=False)
# A patch replaces a part the agent names, and patching it again with the same
# words changes nothing more, as `mark` does.
# Not idempotent: `after=` sends its sections again on a retry, so a host must
# not repeat the call for us.
PATCHES = ToolAnnotations(
    destructive_hint=False, idempotent_hint=False, open_world_hint=False
)


def freshness(log: MessageLog, message_id: str) -> dict:
    """How old *message_id*'s data is, and its sections past their ``fresh:``,
    said only when there are any."""
    names = log.pages.stale(message_id)
    return {"data_age_s": log.pages.data_age(message_id)} | (
        {"stale": names} if names else {}
    )


def went_back(log: MessageLog, message_id: str | None, new_id: str) -> dict:
    """What ``show`` adds when it sent the earlier *message_id* again as *new_id*:
    its age and freshness, and ``redrawn``, the includes drawn again from the
    backend's data now, so the agent knows those figures may have moved."""
    if message_id is None:
        return {}
    redrawn = sorted({r.name for r in log.pages.includes.regions(new_id)})
    return (
        {"sent_again": message_id, "age_s": log.pages.age(message_id)}
        | freshness(log, message_id)
        | ({"redrawn": redrawn} if redrawn else {})
    )


def add_record_tools(
    server: MCPServer,
    demo: _Demo,
    offers: Callable[[Served, str], list[dict]],
    heard: Callable[[_Demo, Context, int | None], Awaitable[dict]],
) -> None:
    """Register ``history`` and ``patch`` on *server*, over *demo*'s conversation;
    *offers* and *heard* are the shell's own, so ``patch`` answers as ``mark``."""

    @server.tool(annotations=PATCHES)
    async def patch(
        ctx: Context,
        message_id: str,
        markdown: str = "",
        section: str | None = None,
        x: int | None = None,
        after: str | None = None,
        before: str | None = None,
        replace: list[dict[str, str]] | None = None,
        wait_seconds: int | None = None,
    ) -> dict:
        """Replace one part of a page you showed, without re-sending the rest:
        a ``section`` by its ``{#id}`` or its heading's words, or one link or
        button by its ``x``. ``markdown`` is the section with its heading, or
        only its body, which keeps the heading; for ``x``, the one new link,
        ``[❤️](agent:unlike?id=3)``. The server edits its own copy, so nothing
        else on the page can drift, and refuses a patch that would change more.
        To add sections, name the one they go ``after`` or ``before`` and send
        only the new sections, headings at its level; ``markdown=""`` removes
        the ``section``. For a small fix anywhere, ``replace`` swaps exact text,
        each ``old`` found once on one line: ``replace=[{"old": "a.jpg)",
        "new": "a.jpg?md2ui.aspect_ratio=1:1)"}]``.

        The page in the window updates in place. Any other page is shown, as
        ``show(message_id=…)`` does: re-read a ``stale`` section, then patch it,
        and going back costs one call. A patched section's data is new, so its
        ``fresh:`` clock starts again. Returns the new ``message_id`` and its
        ``offers``; then it listens, as ``mark`` does."""
        served = demo.started()
        named = [p for p in (section, x, after, before, replace) if p is not None]
        if len(named) != 1:
            raise ToolError(
                "name a section, a link by x, the section to add after or "
                "before, or the text to replace: one of them"
            )
        edits = None
        if replace is not None:
            if not all(
                isinstance(e, dict) and {"old", "new"} <= e.keys() for e in replace
            ):
                raise ToolError('each replace edit is {"old": …, "new": …}')
            edits = [(str(e["old"]), str(e["new"])) for e in replace]
        side = (
            "after" if after is not None else "before" if before is not None else None
        )
        conversation = served.conversation
        with contextlib.redirect_stdout(sys.stderr):
            try:
                change = conversation.patch(
                    message_id, markdown, section or after or before, x, side, edits
                )
                new = await asyncio.to_thread(served.call, change)
            except FrameError as exc:
                raise ToolError(str(exc)) from exc
            await asyncio.to_thread(demo.settle)
        result = {"message_id": new, "offers": offers(served, new)}
        result |= freshness(conversation.log, new) | handled(conversation)
        return result | await heard(demo, ctx, wait_seconds)

    @server.tool(annotations=READS)
    async def history() -> dict:
        """The pages you showed in this session, newest first: one row per page,
        however often you re-sent, marked or fed it. Each row has the page's
        ``message_id``, its ``title`` (first heading), ``age_s`` since it was last
        sent, ``data_age_s`` since its oldest data was given, the ``sources``
        your ``<!-- from: … -->`` comments name, by section, and ``stale``: the
        sections older than the ``fresh:`` you wrote on that comment. Any id a page
        had still names it, so ``show(message_id=…)`` and ``showing`` take the old
        one too. ``showing`` is the page in the window now. Ids end with the
        server: after a restart this list starts empty, and an id from before is
        gone, not reused."""
        conversation = demo.conversation()
        if conversation is None:
            return {
                "pages": [],
                "text": "Nothing shown since this server started: an id you "
                "remember from before is gone. `show` starts again.",
            }
        pages = conversation.log.pages
        return {
            "pages": pages.listing(),
            "showing": conversation.latest,
            "since_s": round(time.monotonic() - pages.started),
        }
