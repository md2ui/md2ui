"""The working line: what the agent is doing while the window shows it working.

The demo shell sees only its own tools, so while the agent works between them
(reading files, running commands) the window could say nothing but "working". A
host that sees every tool call can say more: Claude Code runs a ``PreToolUse``
hook before each one, and this module is both ends of that channel (ADR-613):

* **the hook**, ``md2ui-demo-activity [true|false]``, reads the call
  Claude Code hands it on stdin, makes a short label of it, and posts the label
  to this conversation's server. It never blocks the call it reports: whatever
  goes wrong, it says nothing and exits 0;
* **the server's side**: :func:`advertise` writes where to post, and
  :func:`route` takes the post and hands the label to the shell, which says it
  as the state frame's note ``n`` under ``w`` and ignores it otherwise.

**What a label may say.** The window can be on a shared screen, so a label is
never a command, a path or content: a Bash call's own ``description`` (the line
the model wrote for the user, the one Claude Code shows), else the tool's name
and a file's basename, else the tool's name. A label, not narration: one line,
at most ``MAX_LABEL`` characters.

**How the hook finds the server.** Both are children of one Claude Code session,
and the ids agree: Claude Code gives its MCP servers ``CLAUDE_CODE_SESSION_ID`` in
their environment, and every hook the same id as ``session_id`` on stdin. So the
server writes ``<session>.json`` (the url to post to, which carries a secret) in
a directory only this user may read, and the hook reads the one named for its
session. A server outside Claude Code has no session id and advertises nothing.

The hook runs before every tool call, so this module imports only the standard
library at load time; the route's web framework is imported where it is built.
"""

from __future__ import annotations

import hmac
import json
import os
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.routing import Route

# Where a server says where to post, by Claude Code session.
ADVERTS = Path(tempfile.gettempdir()) / "md2ui-demo-activity"
SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
# A label is a short line under the working animation, not a sentence.
MAX_LABEL = 60
MAX_BODY_BYTES = 512
# A hook delays the call it reports: a server that does not answer at once is
# not worth waiting for.
POST_TIMEOUT_S = 0.5
# Keys a tool's input names one file by.
_FILE_KEYS = ("file_path", "notebook_path", "path")


def label(tool_name: str, tool_input: object) -> str | None:
    """What the window may say about one tool call, or None to say nothing.

    The demo's own tools are left out: the shell already sees those."""
    if tool_name.startswith("mcp__") and "md2ui" in tool_name:
        return None
    given = tool_input if isinstance(tool_input, dict) else {}
    name = tool_name.rsplit("__", 1)[-1] if tool_name.startswith("mcp__") else tool_name
    said = given.get("description") if tool_name == "Bash" else None
    if not isinstance(said, str) or not said.strip():
        file = next((given[k] for k in _FILE_KEYS if isinstance(given.get(k), str)), "")
        said = f"{name} {Path(file).name}" if Path(file).name else name
    said = " ".join(said.split())
    return said if len(said) <= MAX_LABEL else said[: MAX_LABEL - 1] + "…"


def advert_path(session: str) -> Path | None:
    """Where the server of *session* says where to post; None for an id that
    could name a path elsewhere."""
    if not session or not all(c.isalnum() or c in "-_" for c in session):
        return None
    return ADVERTS / f"{session}.json"


def advertise(url: str) -> Path | None:
    """Say, for this process's Claude Code session, that labels go to *url*:
    the file written, or None outside Claude Code."""
    path = advert_path(os.environ.get(SESSION_ENV, ""))
    if path is None:
        return None
    path.parent.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump({"url": url}, out)
    return path


def route(token: str, said: Callable[[str], None]) -> Route:
    """``POST /activity/{token}``: one label from the hook, handed to *said* off
    the event loop. A browser's request (one with an ``Origin``) is refused."""
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.routing import Route

    async def endpoint(request: Request) -> Response:
        if "origin" in request.headers:
            return Response(status_code=403)
        if not hmac.compare_digest(request.path_params["token"], token):
            return Response(status_code=404)
        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            return Response(status_code=413)
        text = " ".join(body.decode("utf-8", "replace").split())[:MAX_LABEL]
        if text:
            await asyncio.to_thread(said, text)
        return Response(status_code=204)

    return Route("/activity/{token}", endpoint, methods=["POST"])


def post(call: dict) -> bool:
    """Post the label for one hook *call* to its session's server; whether one
    went. Every failure is quiet: the call it reports must go ahead."""
    try:
        tool = call.get("tool_name")
        path = advert_path(str(call.get("session_id", "")))
        said = label(tool, call.get("tool_input")) if isinstance(tool, str) else None
        if path is None or said is None:
            return False
        url = json.loads(path.read_text(encoding="utf-8"))["url"]
        if not isinstance(url, str) or not url.startswith("http://127.0.0.1:"):
            return False
        request = urllib.request.Request(url, data=said.encode(), method="POST")
        with urllib.request.urlopen(request, timeout=POST_TIMEOUT_S):
            return True
    except Exception:  # the hook must never stop the call it reports
        return False


def main(argv: list[str] | None = None) -> None:
    """The hook: ``false``, the plugin's switch turned off, posts nothing."""
    args = sys.argv[1:] if argv is None else argv
    if args[:1] != ["false"]:
        try:
            call = json.load(sys.stdin)
        except ValueError:
            return
        if isinstance(call, dict):
            post(call)


if __name__ == "__main__":
    main()
