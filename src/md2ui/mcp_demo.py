"""The demo shell: Claude talks to a user through an md2ui window (ADR-602).

Claude, in Claude Desktop or Claude Code, answers in md2ui Markdown; the answer
appears in md2ui's window; the user's clicks come back to Claude as sentences.
It is the whole product loop on one machine: the agent writes, a frontend
renders, the wire carries clicks back (ADR-601), and the agent decides state
(ADR-404).

Built from what exists: the authoring tools (``mcp_server``, ADR-602), a
conversation served over the reference WebSocket binding on localhost
(``wire_server``, ADR-601), and the app as its client, launched on the first
``show``. Three tools join the authoring six:

* ``show(markdown)`` — put a response in the window. Returns its id, what it
  offers the user, a digest of how it grouped, and its authoring issues, so no
  separate ``check`` is needed;
* ``wait_for_event()`` — block until the user clicks something that comes back to
  the agent, and return EVERYTHING waiting as the wire's sentences; or until the
  user types into the window's own field, and return that as their message
  (ADR-601), which never shares a call with clicks;
* ``mark(message_id, x, state)`` — tick, untick, disable, or set the VALUE of a
  target. The server edits its copy and the window updates in place; nothing is
  regenerated, so a long answer cannot drift under the user while one number in
  it changes;
* ``screenshot()`` — a PNG of the window itself (``app_capture``). The agent drives
  the wire blind otherwise: it can see that an event verified, never that it drew;
* ``showing()`` — what the window holds, as data: the live Markdown, its offers by
  ordinal, and what the user has asked for since. What a control HOLDS is this
  tool's question; how the page LOOKS is ``screenshot``'s, and only that one needs
  pixels;
* ``status()`` — the state the window was last told, and whether one is still
  connected. The wire's own answer, not a reading of this window's bar: the bar
  and the animation are the frontend's, and another frontend draws neither.

The window shows what the agent is doing, from the moments this shell already
sees (ADR-601): listening while ``wait_for_event`` is open; working from the input
it returns until the agent's next ``show``, ``mark`` or wait, and the window
blocks new input meanwhile; idle otherwise.

Those are the moments a tool call reveals, and a turn that answers a click and
ends reveals nothing — so ``working`` also ends on a deadline
(``IDLE_AFTER_WORKING``). Without one it never ends at all, and the window blocks
not just its prompt but every click in the document.

Local only, by construction: the socket listens on 127.0.0.1, and the window is a
child process of this server holding its secret, minted per run, or chosen by the
launcher in ``MD2UI_WIRE_BEARER`` (at least ``LAUNCHER_BEARER_MIN`` characters). A demo shell, not a deployment: a real backend
delivers through its own transport (ADR-601's binding, or its own).

Run it: ``md2ui-mcp-demo [--theme PATH] [--no-window] [--port N]``.
``--port`` puts the conversation at a known address, for a client of your own.
"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import contextlib
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from mcp.server.mcpserver import Context, Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from starlette.routing import BaseRoute

from md2ui import app_capture, mcp_demo_activity, session, theme_lint
from md2ui.advice import Reading, reply_issues
from md2ui.digest import digest, theme_at
from md2ui.includes import Includes, static_includes
from md2ui.mcp_demo_records import add_record_tools, freshness, went_back
from md2ui.mcp_demo_told import CLICK_NEXT, event_row, handled, narrate, prompt_row
from md2ui.mcp_server import ABOUT, FETCH_HELP, build_server
from md2ui.wire import (
    FORWARDED_KINDS,
    MARK_STATES,
    FrameError,
    Prompt,
    Verified,
)
from md2ui.wire_feeds import FeedEnded, snippets
from md2ui.wire_client import WIRE_BEARER
from md2ui.wire_server import Conversation, Presence, Served

# A wait must end as a TIMEOUT rather than as the host killing the call: Claude
# Code's MCP idle timeout aborts a wait at 1800 s with an error, so the agent loses
# the loop instead of being handed a clean "nobody clicked". A tool cannot know its
# host's limit, so the cap sits comfortably under the one host measured, and the
# default sits well under that again -- long enough that re-arming is rare, short
# enough to be portable. Progress is emitted while waiting so the call is not
# silent, which is what an idle timeout is counting.
MAX_WAIT_SECONDS = 1500
DEFAULT_WAIT_SECONDS = 900
PROGRESS_EVERY_SECONDS = 25.0
# A host may abandon a wait without telling this server (the Cowork device bridge
# cuts at 60 s), and the agent then opens another. The old one must not take the
# user's next click to a caller that is gone, so a wait is taken in short slices
# and gives way to a newer one between them.
SLICE_SECONDS = 1.0
# How long `show` and `mark` listen after they reply. Listening is part of the
# reply because an agent told to wait afterwards does not reliably do it; kept
# under the one host cut measured, 60 s, so a quiet user costs a timeout the
# agent can read rather than an error that hides the reply.
SHOW_WAIT_SECONDS = 45
# How long an answer to what the user just did listens when told 0: the user who
# acted is watching for the answer and may act on it at once.
GRACE_SECONDS = 15
# A grace waits for a user who is typing: a typed reply can outlast
# GRACE_SECONDS and would be heard only by a later wait. Typing is under way while
# the window's last `k` frame is younger than TYPING_PAUSE_SECONDS -- it sends
# one a second while keys are pressed -- so a grace ends at the later of its own
# GRACE_SECONDS and a pause that long after the last keystroke, and never after
# GRACE_MAX_SECONDS, so a field left typing in never holds a turn for good.
TYPING_PAUSE_SECONDS = 5.0
GRACE_MAX_SECONDS = 120

# How long `w` may stand before the shell stops claiming it. A turn that answers a
# click and ends makes no further call, and `w` is cleared only by one -- so
# without a deadline the window blocks EVERY click in the document, for good
# (app.py's handler returns while `bar.locked`, which is `state == "w"`). Blocking
# during `w` is the protocol's (protocol/README.md: "a client blocks new clicks and
# prompts"); only its duration is this shell's to bound. Nearly every agent answers
# input within 45 s; a slower one finds its clicks queued, not lost.
IDLE_AFTER_WORKING = 45.0
# The shortest secret a launcher may choose: `secrets.token_urlsafe(32)` mints 43.
LAUNCHER_BEARER_MIN = 32

# The loop, said once: what each thing a listen can return means, and what to do.
# The tool descriptions say only what each returns, and every result's `text`
# says what comes next -- except a transport error, which no result can carry,
# so `wait_for_event` keeps that one rule too.
DEMO_INSTRUCTIONS = ABOUT + (
    " This server is your channel to the user: `show` puts your reply in an md2ui "
    "window on their screen, and the window is a display for the same replies the "
    "chat would get. What form each reply takes is yours to decide: a UI, a plain "
    "written answer such as a plan, or both in one document; nothing needs to be "
    "structured to be shown. The window is heard only while a wait is open, and "
    "nothing can wake you once your turn ends, so `show` and `mark` listen after "
    "they reply and return what the user did as `heard`; `wait_for_event` only "
    "listens.\n\n"
    "| a listen returns | it means | do |\n"
    "|---|---|---|\n"
    "| a click | everything since you last listened: clicks queue while nothing "
    "listens, and none is lost while the server runs | act on all of it; your next "
    "`show` or `mark` listens again |\n"
    "| `prompt` | what the user typed into the window | answer it as their next "
    "message |\n"
    "| a timeout | nothing came | call `wait_for_event`, unless the user is in the "
    "chat |\n"
    "| a transport error | your host cut the wait, not the window | call "
    "`wait_for_event` with `timeout_seconds` 30 |\n"
    "| `closed` | the user closed the window | end the turn |\n\n"
    "End your turn only on `closed`, when the user says so in the chat, or when they "
    "are talking to you in the chat, not in the window they asked for: a wait "
    "holds your turn open there, so listen "
    "briefly (`show` with `wait_seconds` 120) and end it on the timeout. Their clicks "
    'queue, and the window tells them to say "check md2ui". When the '
    "user asks you in the chat to check md2ui, call `wait_for_event`: what they did "
    "there is waiting. In the chat, one line saying the answer is in the window is "
    "enough. Never ask the user to press a key: the window's keys are not the "
    "chat's, and to stop they say so in the chat or the window's prompt bar. "
    "When the user only asks to open, launch or show md2ui, read "
    '`guide("opened")`: never a tour of md2ui, never invented data. '
    "To tick, untick or disable something you showed, call `mark` instead of "
    "sending the answer again. `screenshot` shows you the window itself. `show` "
    "returns the answer's authoring issues and a `digest` of what it drew, one line "
    "per section: no issues does not mean it drew what you meant, so read the digest "
    "against it."
)

# What a timeout leaves to the agent: wait again, unless the turn should end.
WAIT_AGAIN = (
    "unless the user is done, or is talking to you in the chat, not in the window "
    "they asked for: then end your turn, "
    'and their clicks queue until they say "check md2ui".'
)

# Why a window's first page listened though told 0: the user who has a new window,
# launched or connected, is the one using it. Draft wording, awaiting its eval.
OPENED_LISTENS = "The window was just opened for the user, so this page listens."

# Why an answer to a click or a prompt listened though told 0.
# Draft wording, awaiting its eval.
GRACE_LISTENS = (
    "The user just acted, so this answer listens for {} s, longer while they type."
)


# The window is on this machine and the socket is loopback (ADR-602), so no tool
# reaches the outside world. `show` adds a message, it never removes one; `mark`
# edits a target and asking twice changes nothing more.
SHOWS = ToolAnnotations(destructive_hint=False, open_world_hint=False)
WAITS = ToolAnnotations(read_only_hint=True, open_world_hint=False)
MARKS = ToolAnnotations(
    destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
FEEDS = ToolAnnotations(destructive_hint=False, open_world_hint=False)


class _Demo:
    """The served conversation and its window, started on the first ``show``."""

    def __init__(
        self,
        theme_path: Path | None,
        launch_window: bool,
        working_animation: Path | None = None,
        port: int = 0,
    ) -> None:
        self.theme_path = theme_path
        self.port = port  # 0: any free one
        self.launch_window = launch_window
        self.working_animation = working_animation
        self._kit: session.GroupingKit | None = None
        # The secret only this run's window holds: any other local process that
        # finds the port is refused at the upgrade (ADR-601). Minted per run,
        # unless the launcher chose it (`launcher_bearer`).
        self.bearer = launcher_bearer() or secrets.token_urlsafe(32)
        self._served: Served | None = None
        self._window: subprocess.Popen | None = None
        # Where the window answers screenshot requests (app_capture). Made with
        # the conversation, so a capture cannot outlive the session that asked.
        self._captures: Path | None = None
        self._capture_count = 0
        self._idle: threading.Timer | None = None
        # Whether a wait is open. `i` means "nobody is listening", so it cannot
        # be asserted by a caller that does not know; it is derived from this.
        self._waiting = False
        # Which wait is the live one: a newer wait supersedes any still open.
        self._wait_gen = 0
        # When the agent last answered with `show`: a prompt typed before it was
        # typed at an older page, and must not read as a reply to the new one.
        self._replied_at = 0.0
        # The clicks a wait handed the agent: its next wait answers them (`u`).
        self._handed: list[Verified] = []
        # Whether the last wait handed the agent one click or a prompt: its next
        # answer listens briefly even when told 0, as no wait has since.
        self._acted = False
        self.includes = Includes()  # what `show` expands (ADR-612)
        # The question the agent's last `show` or `mark` asked the prompt bar to
        # show while it listens (ADR-613), and the lock that keeps a host's step
        # (`activity`) from landing between two states.
        self.ask: str | None = None
        self._saying = threading.RLock()
        self._advert: Path | None = None  # where the working line is posted

    def kit(self) -> session.GroupingKit:
        if self._kit is None:
            self._kit = session.load_grouping_kit()
        return self._kit

    def served(self) -> Served:
        if self._served is None:
            # Ids carry this run's own prefix: one the agent remembers from before
            # a restart is then unknown, never a different page that took its name.
            prefix = f"{secrets.token_hex(1)}-c"
            conversation = Conversation(self.kit(), prefix, self.includes)
            token = secrets.token_urlsafe(16)
            steps = mcp_demo_activity.route(token, self.activity)
            self._served = _serve(conversation, self.port, self.bearer, [steps])
            http = self._served.url.removesuffix("/ws").replace("ws:", "http:", 1)
            self._advert = mcp_demo_activity.advertise(f"{http}/activity/{token}")
            print(f"[demo] serving at {self._served.url}", file=sys.stderr, flush=True)
            self._captures = Path(tempfile.mkdtemp(prefix="md2ui-capture-"))
            atexit.register(self.close)
        return self._served

    def captures(self) -> Path:
        """The directory the window answers captures in; ``show`` made it."""
        if self._captures is None:
            raise ToolError("nothing is shown yet: call `show` first")
        return self._captures

    def next_capture(self) -> Path:
        self._capture_count += 1
        return self.captures() / f"shot-{self._capture_count}.png"

    def conversation(self) -> Conversation | None:
        """The conversation, once the first ``show`` has served it."""
        return self._served.conversation if self._served is not None else None

    def started(self) -> Served:
        if self._served is None:
            raise ToolError("nothing is shown yet: call `show` first")
        return self._served

    def say(
        self, state: str, answered: list[Verified] | None = None, note: str = ""
    ) -> None:
        """Tell the window what the agent is doing (ADR-601): ``l``, ``w``, ``i``;
        under ``l`` the question it asked (``ask``), under ``w`` its *note*.

        ``w`` is said with a deadline. Every other state is cleared by the agent's
        next call, but the turn that ends after answering a click makes no next
        call — so ``w`` alone needs one that does not depend on the agent speaking
        again. ``i`` stays honest when it fires: nobody is listening, and input
        waits until someone is.
        """
        if self._served is None:
            return
        with self._saying:
            self._cancel_idle()
            per_peer: dict[str, list[int]] = {}
            for click in answered or []:
                per_peer.setdefault(click.peer, []).append(click.seq)
            asked = self.ask if state == "l" else None
            told = self._served.conversation.set_state(
                state, note=note, answered=per_peer, placeholder=asked
            )
            self._served.call(told)
            if state == "w":
                timer = threading.Timer(
                    IDLE_AFTER_WORKING, lambda: self._idle_now(timer)
                )
                timer.daemon = True  # never hold the process open
                self._idle = timer
                timer.start()

    def activity(self, step: str) -> None:
        """A step the host saw the agent take (``mcp_demo_activity``): said as
        ``w``'s note, which also re-arms ``w``'s deadline, since the agent is
        plainly still working. Dropped in any other state: only work has a step."""
        with self._saying:
            if self._served is not None and self._served.conversation.state == "w":
                self.say("w", note=step)

    def settle(self) -> None:
        """Say what is true now, rather than assuming: listening while a wait is
        open, idle otherwise. Every caller that would assert ``i`` asks this."""
        self.say("l" if self._waiting else "i")

    def _idle_now(self, timer: threading.Timer) -> None:
        """The deadline passed with no further call: the turn ended. Unless a
        step re-armed it while this one waited for the lock."""
        with self._saying, contextlib.suppress(Exception):  # the server may stop
            if self._idle is timer:
                self.settle()

    def _cancel_idle(self) -> None:
        if self._idle is not None:
            self._idle.cancel()  # a no-op on one already running
            self._idle = None

    def open_window(self) -> bool:
        """Launch the app as this conversation's client, or again if it was closed;
        whether it launched one."""
        if not self.launch_window:
            return False
        if self._window is not None and self._window.poll() is None:
            return False
        args = [sys.executable, "-c", "from md2ui.app import main; main()"]
        args += ["--connect", self.served().url]
        if self.theme_path is not None:
            args += ["--theme", str(self.theme_path)]
        if self.working_animation is not None:
            args += ["--working-animation", str(self.working_animation)]
        args += ["--capture-requests", str(self.captures())]
        env = {**os.environ, WIRE_BEARER: self.bearer}
        # The window's prints must never reach this process's stdout: the protocol.
        self._window = subprocess.Popen(
            args, stdout=sys.stderr, stderr=sys.stderr, env=env
        )
        return True

    def close(self) -> None:
        self._cancel_idle()
        if self._advert is not None:
            self._advert.unlink(missing_ok=True)
        if self._window is not None and self._window.poll() is None:
            self._window.terminate()
        if self._served is not None:
            self._served.stop()
        if self._captures is not None:
            shutil.rmtree(self._captures, ignore_errors=True)


def launcher_bearer() -> str | None:
    """The secret the process that started this server chose for it, or None.

    A launcher that drives a window of its own (`--no-window`, as the live eval
    harness does) cannot learn a secret minted here, so it may choose one and put
    it in `MD2UI_WIRE_BEARER`, the variable the launched window inherits too. Only
    that launcher, which controls this server anyway, knows it. A value shorter
    than `LAUNCHER_BEARER_MIN` is ignored, never trusted: an empty variable, a
    typo or a placeholder must not weaken the door.
    """
    chosen = os.environ.get(WIRE_BEARER, "")
    return chosen if len(chosen) >= LAUNCHER_BEARER_MIN else None


def _serve(
    conversation: Conversation, port: int, bearer: str, routes: list[BaseRoute]
) -> Served:
    """Serve *conversation* on *port*, or say plainly that the port is taken.

    Something answering there already counts as taken, though the bind may still
    succeed: ``Served`` sets SO_REUSEADDR, which on macOS lets it bind beside a
    listener on 0.0.0.0, and a client asking for that port would reach either."""
    if port:
        with socket.socket() as probe:
            probe.settimeout(0.5)
            answered = probe.connect_ex(("127.0.0.1", port)) == 0
        if answered:
            raise ToolError(f"port {port} is taken: something already listens there")
    try:
        return Served(conversation, port=port, bearer=bearer, routes=routes)
    except OSError as exc:
        raise ToolError(f"port {port} is taken: {exc.strerror or exc}") from exc


def _log(message: str) -> None:
    """A line in the host's server log: stderr, never the protocol's stdout."""
    print(f"[wait] {message}", file=sys.stderr, flush=True)


def _since(started: float) -> str:
    return f"{time.monotonic() - started:.0f} s"


def _put_back(served: Served, done: asyncio.Future) -> None:
    """A cancelled wait's last slice may still take a batch: return it."""
    if not done.cancelled() and done.exception() is None:
        served.put_back(done.result())


def _offers(served: Served, message_id: str) -> list[dict]:
    """What a message offers that comes back to the agent, compactly."""
    out: list[dict] = []
    for x, target in enumerate(served.conversation.log.targets(message_id)):
        a = target.action
        if a is None or a.kind not in FORWARDED_KINDS:
            continue
        row: dict = {"x": x, "label": a.label}
        row |= {"action": a.action} if a.action else {"kind": a.kind}
        if a.value is not None:
            row["value"] = a.value
        out.append(row)
    return out


def _listens(issues: list[dict]) -> bool:
    """Whether ``show`` listens after replying: unless an issue is a defect the
    agent is about to fix. A ``note`` is advice and leaves the page as it is.
    An ``image-ratio`` warning stops listening as every warning does: agents fixed
    it before the user's click, and not after (ADR-611)."""
    return all(issue["level"] == "note" for issue in issues)


def _grace_end(conversation: Conversation, started: float, end: float) -> float:
    """When a grace that would end at *end* ends, given the user's typing."""
    typing_until = conversation.typed_at + TYPING_PAUSE_SECONDS
    return min(started + GRACE_MAX_SECONDS, max(end, typing_until))


async def _listen(
    demo: _Demo,
    ctx: Context,
    timeout_seconds: int,
    after_show: bool = False,
    grace: bool = False,
) -> dict:
    """One wait for the user, as ``wait_for_event``, ``show`` and ``mark`` share
    it, with the clicks a backend answered meanwhile (ADR-612), one line each."""
    heard = await _wait(demo, ctx, timeout_seconds, after_show, grace)
    return handled(demo.started().conversation) | heard  # read before what follows


async def _wait(
    demo: _Demo,
    ctx: Context,
    timeout_seconds: int,
    after_show: bool = False,
    grace: bool = False,
) -> dict:
    """One wait, as ``_listen``. A *grace* is extended while the user types
    (``_grace_end``)."""
    served = demo.started()
    timeout = float(min(MAX_WAIT_SECONDS, max(1, int(timeout_seconds))))
    demo._wait_gen += 1
    mine = demo._wait_gen
    demo._waiting = True
    # Listening again is the agent's answer to every click it was handed, so the
    # window may let those go -- not before: a batch answered by several `mark`s
    # with `wait_seconds` 0 listens only on the last.
    handed, demo._handed = demo._handed, []
    demo._acted = False
    await asyncio.to_thread(demo.say, "l", handed)
    # Progress is reported so the call is not silent: a host's idle timeout
    # counts silence, and one that fires kills the loop with an error instead
    # of a timeout the agent can act on.
    started = time.monotonic()
    deadline, reported = started + timeout, started
    batch: list = []
    try:
        while not batch:
            if demo._wait_gen != mine:
                _log(f"a {int(timeout)} s wait gave way after {_since(started)}")
                return {"text": "A newer wait took over.", "events": []}
            if grace:
                deadline = _grace_end(served.conversation, started, started + timeout)
            left = deadline - time.monotonic()
            if left <= 0:
                break
            job = asyncio.ensure_future(
                asyncio.to_thread(served.next_events, min(SLICE_SECONDS, left))
            )
            try:
                batch = await asyncio.shield(job)
            except asyncio.CancelledError:
                job.add_done_callback(lambda done: _put_back(served, done))
                _log(f"a {int(timeout)} s wait was cancelled after {_since(started)}")
                if demo._wait_gen == mine:  # nobody is listening any more
                    demo._waiting = False
                    demo.settle()
                raise
            if batch and demo._wait_gen != mine:
                served.put_back(batch)
                batch = []
            if after_show and [getattr(e, "kind", None) for e in batch] == [
                "reconnected"
            ]:
                batch = []  # the window `show` itself just opened is not news
            if not batch and time.monotonic() - reported >= PROGRESS_EVERY_SECONDS:
                reported = time.monotonic()
                with contextlib.suppress(Exception):  # progress is optional
                    await ctx.report_progress(
                        progress=time.monotonic() - started,
                        total=deadline - started,
                        message="waiting for the user",
                    )
    finally:
        if demo._wait_gen == mine:
            demo._waiting = False
    if not batch:
        await asyncio.to_thread(demo.settle)
        # The count as a field, not only a sentence: an agent acts on a fact
        # more reliably than on prose.
        served, live = demo._served, 0
        if served is not None and served.conversation.latest:
            live = len(_offers(served, served.conversation.latest))
        still = "1 offer is" if live == 1 else f"{live} offers are"
        return {
            "text": f"No click or message within {int(deadline - started)} s"
            + (f", and this page's {still} still live" if live else "")
            + ". Call `wait_for_event` again to keep listening"
            + (f" {WAIT_AGAIN}" if live else "."),
            "events": [],
            "live_offers": live,
        }
    if isinstance(batch[0], Presence):
        # NOT `w`: a window opening or closing is not input to work on, and
        # saying so would lock a window that just arrived on nothing.
        await asyncio.to_thread(demo.settle)
        gone = batch[0].kind == "closed"
        fed = batch[0].feeds
        stopped = f" Feed{'s' * (len(fed) > 1)} {', '.join(fed)} stopped with it."
        stopped = stopped if fed else ""
        return {
            "kind": batch[0].kind,
            "text": (
                "The user closed the md2ui window, and no click can arrive: stop "
                "waiting. Only you can reopen it, so say in the chat, in one line, "
                "that it is closed and that `show` will bring it back." + stopped
                if gone
                else "The md2ui window is back. It is already showing your last "
                "response; `showing` says what it holds. Wait again to hear it."
            ),
        }
    if isinstance(batch[0], FeedEnded):  # news, not input: the window stays open
        await asyncio.to_thread(demo.settle)
        return batch[0].heard()
    await asyncio.to_thread(demo.say, "w")
    # One event earns its answer a grace; a batch answered by several `mark`s
    # with `wait_seconds` 0 listens only on the last, so it never listens mid-batch.
    demo._acted = len(batch) == 1
    if isinstance(batch[0], Prompt):
        return prompt_row(batch[0], demo._replied_at)
    clicks = [e for e in batch if isinstance(e, Verified)]
    demo._handed += clicks
    log = served.conversation.log  # where each click came from, from its records
    rows = [event_row(e) | log.pages.clicked(e.message_id, e.ordinal) for e in clicks]
    told = narrate(clicks)
    told += ("\n" if len(clicks) > 1 else " ") + CLICK_NEXT
    result: dict = {"kind": "click", "text": told, "events": rows}
    if len(rows) == 1:
        # Nothing is hidden by lifting the one event, and every caller
        # written against the single-event shape keeps working.
        result |= {k: v for k, v in rows[0].items() if k != "text"}
    return result


async def _heard(
    demo: _Demo,
    ctx: Context,
    wait_seconds: int | None,
    after_show: bool = False,
    first: bool = False,
) -> dict:
    """``show``'s and ``mark``'s listening, as ``heard``. Told 0 it does not
    listen, and says so when the page it just sent offers something: those clicks
    reach the agent only while a wait is open. A page that offers nothing, a
    goodbye, is left quiet. Two pages listen even when told 0: a window's *first*
    page, even one offering nothing, since the user who has a new window is using
    it; and an answer to what the user just did, for a short grace."""
    seconds = SHOW_WAIT_SECONDS if wait_seconds is None else wait_seconds
    if seconds <= 0 and (first or demo._acted):
        seconds = SHOW_WAIT_SECONDS if first else GRACE_SECONDS
        why = OPENED_LISTENS if first else GRACE_LISTENS.format(seconds)
        heard = await _listen(demo, ctx, seconds, after_show, grace=not first)
        return {"heard": heard | {"text": f"{why} {heard['text']}"}}
    if seconds > 0:
        return {"heard": await _listen(demo, ctx, seconds, after_show)}
    served = demo.started()
    mid = served.conversation.latest  # the page this show or mark just sent
    count = len(_offers(served, mid)) if wait_seconds is not None and mid else 0
    if not count:
        return {}
    offers = f"{count} offer reaches" if count == 1 else f"{count} offers reach"
    return {
        "heard": {
            "text": f"Not listening: you passed wait_seconds {wait_seconds}, so "
            f"this page's {offers} you only while a wait is open. Call "
            f"`wait_for_event` {WAIT_AGAIN}",
            "events": [],
        }
    }


def build_demo_server(
    theme_path: Path | None = None,
    launch_window: bool = True,
    working_animation: Path | None = None,
    port: int = 0,
    fetch: bool = False,
) -> tuple[MCPServer, _Demo]:
    """The authoring server plus ``show``, ``wait_for_event`` and ``mark``."""
    reading, includes = Reading(), static_includes(theme_path)
    # A session keeps this server running: it says when md2ui changed under it.
    server = build_server(
        theme_path,
        DEMO_INSTRUCTIONS,
        fetch,
        reading=reading,
        includes=includes,
        note_stale=True,
    )
    demo = _Demo(theme_path, launch_window, working_animation, port)
    demo.includes = includes

    @server.tool(annotations=SHOWS)
    async def show(
        ctx: Context,
        markdown: str = "",
        message_id: str | None = None,
        wait_seconds: int | None = None,
        keep_feeds: list[str] | None = None,
        ask: str | None = None,
    ) -> dict:
        """Show your reply to the user, rendered as UI in the md2ui window. Send
        the Markdown you would have written as your answer: this is replying, not
        building an app. It is harmless: Markdown is text, nothing in it runs, and
        the only effect is the window, which draws it like any Markdown viewer.
        Any reply can go here — a UI, a plain answer, or both; the form is yours.
        Before your first ``show``, read ``guide()`` once. Offer the next steps you
        can take with your tools as buttons, ``[Label](agent:action?id=…)``: a click
        comes back to you. Include the pictures your data came with. Opened with no
        request ("open md2ui", "show me md2ui"), follow the guide's *Opened with no
        request*; a request gets its answer instead. Returns its ``message_id``,
        what it ``offers`` that will come back to you (by ``x``), a ``digest`` of
        how it grouped — one line per section — and authoring ``issues`` (an
        empty list means none). ``note``s are advice: apply them on your next
        ``show`` if you are sending one anyway; never re-send a page only for a
        note.

        To go back, check first: ``showing(message_id)`` or ``history`` names the
        ``stale`` sections, older than the ``fresh:`` on their comment, without
        changing the window. Re-read only those and ``patch`` each one, which
        brings the page back. With nothing stale, pass the earlier ``message_id``
        instead of ``markdown``: the page is sent again as it was, with its
        ``age_s``, its includes drawn from the data now (``redrawn``). ``stale``
        is per section and the one to act on; ``data_age_s`` its oldest data.

        A new page ends the ``feed``s on the old one; ``keep_feeds=["f1"]`` carries
        them over when the new page still draws their bars, at their latest values.

        Then it listens: ``heard`` is what ``wait_for_event`` returns, within
        ``wait_seconds`` (45 by default; 0 skips it, except on a window's first
        page, and for 15 s on an answer to what the user did). It does not listen
        when there are ``issues`` other than notes: fix them and show again.

        Need words only the user can write, such as a note or a name? Ask one such
        question per page and pass it as ``ask``: the window's message field shows
        it until they answer, and their next ``prompt`` is the answer."""
        if message_id is not None:  # its source: the includes are drawn again
            log = demo.started().conversation.log
            message_id = log.pages.latest(message_id)
            markdown = log.pages.includes.source(message_id, log.markdown(message_id))
            if not markdown:
                raise ToolError(f"no message {message_id!r} was sent in this session")
        elif not markdown:
            raise ToolError("give `markdown`, or an earlier `message_id` to go back")
        demo.ask = ask
        with contextlib.redirect_stdout(sys.stderr):
            served = await asyncio.to_thread(demo.served)
            await asyncio.to_thread(served.forget_presence)
            # Whether this page is the first a window receives: one connected that
            # was sent nothing yet, or (below) the one launched to show it.
            first = served.conversation.new_window
            try:  # the server refuses a frame too large to send, and sends nothing
                send = served.conversation.feeds.send(
                    markdown, keep_feeds or [], continues=message_id
                )
                mid = await asyncio.to_thread(served.call, send)
                log = served.conversation.log  # as carried, with what includes drew
                markdown, drawn = log.markdown(mid), log.pages.includes.regions(mid)
            except FrameError as exc:
                raise ToolError(str(exc)) from exc
            demo._replied_at = time.monotonic()
            first |= await asyncio.to_thread(demo.open_window)
            contract = theme_lint.answer_contract(demo.theme_path)
            ast = await asyncio.to_thread(session.group_shared, markdown, demo.kit())
            issues = await asyncio.to_thread(
                reply_issues, markdown, ast, contract, reading, demo.includes, drawn
            )
            await asyncio.to_thread(demo.settle)
        result = {"message_id": mid, "offers": _offers(served, mid)}
        result |= handled(served.conversation)  # what the backend did meanwhile
        if keep_feeds:
            result["feeds"] = served.conversation.feeds.listing()
        drawn_by = await asyncio.to_thread(theme_at, demo.theme_path)
        result |= {"digest": digest(ast, drawn_by), "issues": issues}
        result |= went_back(served.conversation.log, message_id, mid)
        if not _listens(issues):  # the answer is about to change: nothing to hear
            return result
        return result | await _heard(
            demo, ctx, wait_seconds, after_show=True, first=first
        )

    @server.tool(annotations=WAITS)
    async def wait_for_event(
        ctx: Context, timeout_seconds: int = DEFAULT_WAIT_SECONDS
    ) -> dict:
        """Wait for the user's next click that comes back to you (an agent action
        or a task box), or for what they type into the window's own field.

        It returns **everything waiting**, including what queued while nobody
        listened: ``text`` narrates it all, oldest first, and says what to do
        next; ``events`` carries each click's ``message_id`` and ``x`` (what
        ``mark`` takes) and, for an agent link, its ``action`` and ``params``.
        Typed words come back alone, as ``prompt``. ``closed`` means the window
        is gone and no click can arrive; ``reconnected`` means it is back; a
        timeout means nothing came, and its ``live_offers`` counts what the page
        still offers. ``showing`` answers what the user has
        touched without ending a wait.

        A transport error is your host cutting the wait (the Cowork device bridge
        at 60 s), not the window closing: wait again with ``timeout_seconds`` 30."""
        return await _listen(demo, ctx, timeout_seconds)

    @server.tool(annotations=WAITS)
    async def status() -> dict:
        """What the window is being told, and whether anyone is there to hear it.
        ``state`` is what you last told it: ``l`` listening, ``w`` working, ``i``
        nobody listening. ``watchers`` is how many windows are connected — ``0``
        means the user closed it, and a click can no longer arrive.
        ``message_id`` is the response they are looking at; ``url`` is where a
        window connects. This is the wire's own
        state, so it answers the same for any frontend; a screenshot answers only
        for this window, whose bar and animation are its own, not md2ui's."""
        served = demo.started()
        conversation = served.conversation
        return {
            "state": conversation.state,
            "watchers": conversation.watchers,
            "message_id": conversation.latest,
            "url": served.url,
        }

    @server.tool(annotations=WAITS)
    async def showing(message_id: str | None = None) -> dict:
        """What the window is showing right now, as data rather than pixels —
        or, given an earlier ``message_id``, what that page held, with its
        ``age_s``: the page to edit when going back to live data.

        Any id the page had names its latest version. Returns its ``message_id``,
        ``stale`` sections as ``show`` does, the ``markdown`` you sent, and its
        ``offers`` by ``x`` — each carrying ``requested`` when the user has asked
        for something you have not answered yet: a value they settled on, a box
        they ticked. Those are REQUESTS, not state: the document still says what
        it says until you change it.

        Use this, not ``screenshot``, to ask what a control HOLDS. A screenshot
        answers how the page LOOKS — layout, legibility, whether the answer fits —
        and cannot be read reliably for values. This answers what the page IS,
        exactly, and does not care what the theme draws. A page with includes
        also carries its ``source``, each include as its line: re-send that.

        It is also what a session that was NOT there should call first: a window
        outlives the chat that filled it (not this server, whose restart empties
        it), and this returns enough to act —
        re-send, ``mark`` by ordinal, or interpret the next click — without
        inventing a document you never wrote."""
        served = demo.started()
        conversation = served.conversation
        mid = message_id or conversation.latest
        mid = conversation.log.pages.latest(mid) if mid is not None else None
        if mid is None or not conversation.log.markdown(mid):
            raise ToolError(f"no message {mid!r} to read: call `show` first")
        asked = conversation.log.requested(mid)
        offers = [
            row | ({"requested": asked[row["x"]]} if row["x"] in asked else {})
            for row in _offers(served, mid)
        ]
        feeds = conversation.feeds.listing()  # said only while one runs
        markdown = conversation.log.markdown(mid)
        source = conversation.log.pages.includes.source(mid, markdown)
        return (
            {
                "message_id": mid,
                "markdown": markdown,
                "offers": offers,
                "age_s": conversation.log.pages.age(mid),
            }
            | freshness(conversation.log, mid)
            | ({"feeds": feeds} if feeds else {})
            | ({"source": source} if source != markdown else {})
        )

    @server.tool(annotations=WAITS)
    async def screenshot(
        mode: str = "view", width: int = 480, timeout_seconds: int = 15
    ) -> Image:
        """A PNG of the md2ui window as it is on screen right now. You cannot see
        the window, so use it to check what the user is actually looking at — a
        tick that did or did not appear, a slider left where they dragged it, how
        far down the page they are, whether the answer fits. ``document`` is the
        rendered answer, whole and unscrolled — the part every frontend shares.
        ``view`` is this window as they have it, so it also shows its scroll and
        its own bar, which are the window's, not md2ui's (ADR-601) — read
        ``status`` for the agent state rather than reading that bar. Either way
        this is the live window, not a re-render: ``preview`` renders Markdown,
        and cannot show what a click did.

        ``width`` is the picture's, not the window's: 480 (about 300 tokens) shows
        the layout, the buttons and whether pictures loaded; ask for more, or 0
        for full size, only to read small text. Pictures load after the page: one
        missing right after ``show`` may still be arriving, so look again before
        concluding. Unsure of one part before you send it? ``preview`` just that
        part."""
        demo.started()
        if not demo.launch_window:
            raise ToolError("no window: this server was started with --no-window")
        out = demo.next_capture()
        seconds = float(min(120, max(1, int(timeout_seconds))))
        try:
            data = await asyncio.to_thread(
                app_capture.capture, demo.captures(), out, mode, seconds
            )
        except app_capture.CaptureError as exc:
            raise ToolError(str(exc)) from exc
        data = await asyncio.to_thread(app_capture.shrink, data, int(width))
        return Image(data=data, format="png")

    @server.tool(annotations=MARKS)
    async def mark(
        ctx: Context,
        message_id: str,
        x: int | None = None,
        state: str | None = None,
        key: str | None = None,
        value: float | None = None,
        wait_seconds: int | None = None,
        ask: str | None = None,
    ) -> dict:
        """Change one target of a message you showed, without re-sending it.

        ``checked`` / ``unchecked`` / ``disabled`` for a task box or a button, or
        a **number** for a slider — ``"7"`` sets it to 7, inside the range its
        document authored. The window updates in place and the new
        ``message_id`` is returned. Then it listens, as ``show`` does: ``heard``
        is the user's next click or message, or a timeout.

        A static bar has no ``x``: name the key you wrote, ``key="Elapsed", value=60``.

        It costs the same turn a re-send would, and saves something else: you do
        not reproduce a document you already sent. For a long answer that is the
        real risk — a reworded line or a dropped chip is visible to the user as
        the page changing under them — and the server edits its own copy, so
        nothing can drift. ``ask`` is ``show``'s."""
        served = demo.started()
        with contextlib.redirect_stdout(sys.stderr):
            try:
                if (x is None) == (key is None):
                    raise ToolError("name a target by x, or a bar by key: one of them")
                if key is not None:
                    if value is None or state is not None:
                        raise ToolError('a bar takes a value: key="Elapsed", value=60')
                    change = served.conversation.set_bar(message_id, key, value)
                elif x is None or state is None or value is not None:
                    raise ToolError("x takes a state; value is for a bar named by key")
                elif state in MARK_STATES:
                    change = served.conversation.mark(message_id, x, state)
                else:
                    try:
                        value = float(state)
                    except ValueError:
                        raise ToolError(
                            f"state is a number or one of {', '.join(MARK_STATES)},"
                            f" not {state!r}"
                        ) from None
                    change = served.conversation.set_slider(message_id, x, value)
                new = await asyncio.to_thread(served.call, change)
            except FrameError as exc:
                raise ToolError(str(exc)) from exc
            demo.ask = ask
            await asyncio.to_thread(demo.settle)
        told = {"message_id": new} | handled(served.conversation)
        return told | await _heard(demo, ctx, wait_seconds)

    @server.tool(annotations=FEEDS)
    async def feed(
        message_id: str,
        keys: list[str] | None = None,
        slots: list[str] | None = None,
        values: dict[str, list[str]] | None = None,
        until: str | None = None,
    ) -> dict:
        """Let a process you run move values on a page you showed, costing you no
        turns. ``keys`` names bars (one bar needs none); ``slots`` names values you
        marked: ``[3:53 PM](feed:arrives)``, a chip `` [`Preparing`](feed:status) ``,
        a button label ``[Track · Preparing](agent:track?md2ui.feed=track)``. Declare
        a chip's values: ``values={"status": ["Preparing", "Sent"]}``.

        Returns a ``url``, a ``post`` command and a ``pipe`` forwarding ``name: value``
        lines (``Elapsed: 40%``, ``arrives: 3:58 PM``, or JSON) until the feed ends;
        text is plain words, at most 40 characters. Run it in the background, wait.

        It ends by itself, and ``wait_for_event`` returns ``feed_ended`` only when
        there is something to do: the bars are full (``until="silence"`` runs on;
        it is the default when a slot is fed), your process posted ``end``, went quiet
        or keeps posting what the feed cannot use. Another page ends it unless
        ``show`` keeps it; so does closing the window. ``mark`` keeps working."""
        served = demo.started()
        try:
            opened = served.conversation.feeds.open(
                message_id, keys, until, values, slots
            )
            made = await asyncio.to_thread(served.call, opened)
        except FrameError as exc:
            raise ToolError(str(exc)) from exc
        url = served.url.removesuffix("/ws").replace("ws://", "http://", 1)
        url += f"/feed/{made.token}"
        key = next(iter(made.values))
        return {"feed": made.id, "url": url, "keys": list(made.values)} | (
            snippets(url, f"{key}: {made.spelled(key)}")
        )

    add_record_tools(server, demo, _offers, _heard)
    return server, demo


def _terminated(demo: _Demo) -> None:
    """A host ends the session by closing stdin and, after a grace period, with
    SIGTERM. Python's default for SIGTERM skips atexit, and so ``_Demo.close``:
    the window would outlive its server. Nor can the handler raise SystemExit:
    the stdio reader's thread, blocked on stdin, then holds the process open for
    good. So it closes and leaves at once."""
    demo.close()
    os._exit(128 + signal.SIGTERM)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="md2ui-mcp-demo", description="An agent answers in an md2ui window"
    )
    parser.add_argument("--theme", help="the THEME.md the window and previews use")
    parser.add_argument("--fetch", action="store_true", help=FETCH_HELP)
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="do not launch the app (connect one yourself)",
    )
    parser.add_argument(
        "--working-animation",
        help="an animated WebP or GIF the window plays while the agent works",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="serve the conversation at ws://127.0.0.1:PORT/ws from launch "
        "(default: a free port, once the first answer is shown)",
    )
    args = parser.parse_args(argv)
    theme = Path(args.theme) if args.theme else session.default_theme_path()
    if theme is not None and not theme.is_file():
        parser.error(f"no such theme: {theme}")
    if not 0 <= args.port <= 65535:
        parser.error(f"no such port: {args.port}")
    animation = Path(args.working_animation) if args.working_animation else None
    server, demo = build_demo_server(
        theme,
        launch_window=not args.no_window,
        working_animation=animation,
        port=args.port,
        fetch=args.fetch,
    )
    theme_lint.log(theme)
    if args.port:
        # A port asked for is an address someone will connect to, so it is served
        # now: a client connects before the first answer, and a taken port stops
        # the launch here, in the host's log, rather than failing the first `show`.
        try:
            with contextlib.redirect_stdout(sys.stderr):
                demo.served()
        except ToolError as exc:
            parser.error(str(exc))
    signal.signal(signal.SIGTERM, lambda *_: _terminated(demo))
    server.run("stdio")


if __name__ == "__main__":
    main()
