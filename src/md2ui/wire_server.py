"""The reference WebSocket binding of the wire (ADR-601): one conversation, served.

What a backend does with md2ui's protocol, in the smallest form that is still
real: a Starlette app with one WebSocket endpoint, speaking ``protocol/README.md``.
The backend holds the :class:`Conversation`: it sends Markdown (whole or
streamed), marks state when the agent decides to, and takes verified events off a
queue. Every client frame goes through ``wire.decode_client`` and
``MessageLog.verify``: the rules are the wire's; this module only carries them.

Security, by default:

* it listens on localhost only;
* a WebSocket opened by a browser must come from an Origin the host allowed by
  name, which stops any other page -- a localhost one included -- from driving
  the conversation (cross-site WebSocket hijacking). A native client sends no
  Origin;
* the first frame must be ``hello``;
* the socket refuses a frame over 8 KB before any JSON is parsed, and the codec
  holds every frame but a prompt to 512 bytes;
* a client that sends events faster than the cap is disconnected;
* compression is off: no secret shares a deflate context with attacker text.

TLS and authentication belong to the host: put this behind the proxy that already
terminates them, or wrap the app in the host's own ASGI middleware, which sees
the upgrade request before ``/ws`` does (``protocol/backend.md``). A host with
no sessions of its own, such as the MCP demo and its window, passes ``bearer``:
the upgrade must then carry ``Authorization: Bearer <bearer>``. The demo mints it
per run, or takes the one its launcher chose (``mcp_demo.launcher_bearer``).

Run the demo: ``md2ui-wire DOC.md [--port 8765]``. It
serves the document, prints what each click would tell the agent, and ticks task
boxes itself, so the state round trip can be seen from ``md2ui-app --connect``.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import contextlib
import hmac
import itertools
import socket
import sys
import threading
import time
from collections.abc import (
    AsyncIterable,
    AsyncIterator,
    Callable,
    Collection,
    Iterable,
    Mapping,
    Sequence,
)
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import uvicorn
from starlette.applications import Starlette
from starlette.routing import BaseRoute, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from md2ui import session
from md2ui.includes import Includes
from md2ui.wire import (
    MAX_CLIENT_FRAME_BYTES,
    MAX_NOTE,
    MAX_SERVER_FRAME_BYTES,
    STATES,
    FrameError,
    MessageLog,
    Prompt,
    Recorded,
    Rejected,
    Verified,
    check_server_size,
    decode_client,
    encode,
    escaped_bytes,
    md_hash,
)
from md2ui.wire_feeds import FeedEnded, Feeds, route
from md2ui.wire_frames import MAX_ANSWERED, MAX_PLACEHOLDER
from md2ui.wire_includes import Handler, Redrawn, answer, changed, record, refuse_left
from md2ui.wire_patch import patch_page


@dataclass(frozen=True, slots=True)
class Presence:
    """The watchers changed: ``"closed"`` when the last one left, ``"reconnected"``
    when one returned after that.

    Not a wire frame — the protocol carries what the agent SAYS, and this is the
    binding telling its own caller something the wire cannot. It matters because
    a wait is long: an agent is told to open one for up to 25 minutes and
    re-arm, so a window closed inside one leaves the loop dead for that long.
    `status()` answers the same question, but only if the agent thinks to ask,
    and an agent blocked in a wait is not asking anything.
    """

    kind: str
    feeds: tuple[str, ...] = ()  # the feeds a closing window stopped (ADR-608)


# What a wait can be handed: a click, a prompt, the window, or a feed ending.
Event = Verified | Prompt | Presence | FeedEnded

LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
MAX_EVENTS_PER_SECOND = 20


class Conversation:
    """One conversation: the server's copy of what it sent, and who is watching.

    Every message goes to every connected client. A client that connects late is
    sent the latest complete message and, if one is being streamed, its frames so
    far — so joining mid-stream yields the whole message, never a tail whose hash
    fails. Joins and broadcasts share one send lock, so they never interleave.

    The log is not thread-safe, so all of it runs under its own lock; grouping
    runs off the event loop.
    """

    def __init__(
        self,
        kit: session.GroupingKit | None = None,
        prefix: str = "c",
        includes: Includes | None = None,
    ) -> None:
        self.log = MessageLog(kit)
        # What a backend draws from its data, and the clicks it answers by
        # changing that data (ADR-612): by `agent:` slug, and the digest of the
        # clicks they answered, for the agent's next input.
        self.includes = includes if includes is not None else Includes()
        self.handlers: dict[str, Handler] = {}
        self.handled: list[str | Redrawn] = []
        self.events: asyncio.Queue[Event] = asyncio.Queue()
        self.feeds = Feeds(self)  # bars moved by a process, not a turn (ADR-608)
        self._was_watched = False  # so the FIRST join is not a reconnection
        # When a window last said its user was typing (a `k` frame), on the
        # monotonic clock; 0.0 before any. Kept, never queued: typing is not input.
        self.typed_at = 0.0
        self._state: dict | None = None  # the last state frame, for joiners
        self.prefix = prefix
        self._count = 0
        self._sockets: set[WebSocket] = set()
        self._peers: dict[WebSocket, str] = {}  # whose `q` numbering each one is
        self._unpaged: set[WebSocket] = set()  # joined before any page was sent
        self._latest: list[dict] = []  # the last complete message's frames
        self._streaming: list[dict] = []  # the frames sent so far of one in flight
        self._lock = asyncio.Lock()  # the log
        self._send_lock = asyncio.Lock()  # who is watching, and what they were sent

    @property
    def watchers(self) -> int:
        return len(self._sockets)

    @property
    def new_window(self) -> bool:
        """Whether a window is connected that no page has reached yet: the next
        message is the first it receives."""
        return bool(self._unpaged)

    @property
    def watched_once(self) -> bool:
        return self._was_watched

    def _next_id(self) -> str:
        self._count += 1
        return f"{self.prefix}{self._count}"

    async def _broadcast(self, frames: list[dict]) -> None:
        """Send *frames* to every watcher; the caller holds the send lock."""
        for ws in list(self._sockets):
            for frame in frames:
                with contextlib.suppress(Exception):  # a closing socket
                    await ws.send_text(encode(frame).decode())

    async def join(self, ws: WebSocket, peer: str = "") -> None:
        """Start sending to *ws*, beginning with what it missed; *peer* names the
        connection, as its events are verified under."""
        async with self._send_lock:
            if self._was_watched and not self._sockets:
                self.events.put_nowait(Presence("reconnected"))
            self._was_watched = True
            self._sockets.add(ws)
            self._peers[ws] = peer
            if not self._latest:
                self._unpaged.add(ws)
            state = [self._state] if self._state is not None else []
            for frame in self._latest + self._streaming + state:
                await ws.send_text(encode(frame).decode())

    def leave(self, ws: WebSocket) -> None:
        self._sockets.discard(ws)
        self._peers.pop(ws, None)
        self._unpaged.discard(ws)
        if not self._sockets:
            stopped = self.feeds.end_all("closed")
            self.events.put_nowait(Presence("closed", stopped))

    @property
    def state(self) -> str | None:
        return self._state["s"] if self._state is not None else None

    @property
    def latest(self) -> str | None:
        """The id of the last complete message — what a watcher is showing."""
        return self._latest[0].get("m") if self._latest else None

    async def set_state(
        self,
        state: str,
        note: str | None = None,
        answered: Mapping[str, list[int]] | None = None,
        placeholder: str | None = None,
    ) -> None:
        """Tell every watcher what the agent is doing (ADR-601): ``l`` listening,
        ``w`` working on the last input, ``i`` idle. A late joiner is sent the
        latest; repeating the current state sends nothing. *note* is the step
        the agent is on, *placeholder* the question its field should show
        (ADR-613); a frame without one clears it.

        *answered* is, per connection, the ``q`` of each click answered: by the
        agent, handed it before it listened again, or by a backend's handler, in
        any state. The window may let them go (``u``). Each connection is told
        its own, and a joiner none, since a ``q`` means something only on the
        connection that numbered it."""
        if state not in STATES:
            raise FrameError("bad_frame", f"state {state!r}")
        frame: dict = {"t": "s", "s": state}
        if note:
            frame["n"] = note[:MAX_NOTE]
        if placeholder:
            frame["ph"] = placeholder[:MAX_PLACEHOLDER]
        answered = {p: qs for p, qs in (answered or {}).items() if qs}
        async with self._send_lock:
            if frame == self._state and not answered:
                return
            self._state = frame
            for ws in list(self._sockets):
                own = answered.get(self._peers.get(ws, ""), [])[-MAX_ANSWERED:]
                sent = frame | {"u": own} if own else frame
                with contextlib.suppress(Exception):  # a closing socket
                    await ws.send_text(encode(sent).decode())

    async def tell(self, ws: WebSocket) -> None:
        """Re-send the current state frame to one watcher, if there is one."""
        async with self._send_lock:
            if self._state is None or ws not in self._sockets:
                return
            with contextlib.suppress(Exception):  # a closing socket
                await ws.send_text(encode(self._state).decode())

    async def _complete(
        self, frames: list[dict], send: list[dict], over: str | None = None
    ) -> bool:
        """Show *frames*; with *over*, only while it is the page shown and no
        message is streaming: the stream is the page shown then. Only its own
        end ends it: a page replaced under it leaves a joiner the stream's start."""
        async with self._send_lock:
            if over is not None and (self.latest != over or self._streaming):
                return False
            if self._streaming and self._streaming[0]["m"] == frames[0]["m"]:
                self._streaming = []
            self._latest = frames
            self._unpaged.clear()
            await self._broadcast(send)
            return True

    async def send(
        self, markdown: str, replaces: str | None = None, continues: str | None = None
    ) -> str:
        """Send a whole message; returns its id. *continues* names the page it
        re-sends (``MessageLog.record``)."""
        mid = self._next_id()
        async with self._lock:
            frames = await asyncio.to_thread(
                record,
                self.log,
                self.includes,
                mid,
                markdown,
                replaces=replaces,
                continues=continues,
            )
        await self._complete(frames, frames)
        return mid

    def take_handled(self) -> list[str]:
        """The clicks handlers answered since the last call, one line each, and
        the backend's redraws of the page shown with no click (``changed``)."""
        taken, self.handled = self.handled, []
        return [str(line) for line in taken]

    async def changed(self, names: Collection[str]) -> str | None:
        """The backend's data behind the includes *names* changed with no click:
        draw them again on the page shown and send one replacement, as a handled
        click does (``wire_includes.changed``); returns its id, or None when the
        page shown draws none of them differently, or a message is streaming."""
        async with self._lock:
            shown = self.latest
            if shown is None or self._streaming:
                return None
            done = await asyncio.to_thread(
                changed, self.log, self.includes, names, shown, self._next_id
            )
            if done is None or not await self._complete(done[0], done[0], shown):
                return None
        done[1].tell(self.handled)
        return done[1].message_id

    async def stream(self, chunks: Iterable[str] | AsyncIterable[str]) -> str:
        """Send a message as it is written — an LLM's tokens, say: a message frame
        with the first chunk, deltas for the rest, then its end. Its actions exist
        only from the end. No chunks at all is an empty message, sent as one.

        The whole message must fit one frame, since a late joiner is sent it
        whole; the chunk that would take it over is refused, unsent."""
        mid = self._next_id()
        parts: list[str] = []
        size = len(encode({"t": "m", "m": mid, "md": ""}))

        async def each() -> AsyncIterator[str]:
            if isinstance(chunks, AsyncIterable):
                async for chunk in chunks:
                    yield chunk
            else:
                for chunk in chunks:
                    yield chunk

        async for chunk in each():
            seq = len(parts)
            frame = (
                {"t": "m", "m": mid, "md": chunk}
                if seq == 0
                else {"t": "d", "m": mid, "s": seq - 1, "md": chunk}
            )
            size += escaped_bytes(chunk)
            if size > MAX_SERVER_FRAME_BYTES:
                await self._abandon()
                raise FrameError("too_large", f"message {mid} over {size} bytes")
            check_server_size(frame)
            parts.append(chunk)
            async with self._send_lock:
                self._streaming.append(frame)
                await self._broadcast([frame])
        async with self._lock:
            frames = await asyncio.to_thread(self.log.record, mid, "".join(parts))
        await self._complete(frames, frames if not parts else [frames[1]])
        return mid

    async def patch(
        self,
        message_id: str,
        markdown: str,
        section: str | None = None,
        x: int | None = None,
        side: Literal["after", "before"] | None = None,
        replace: list[tuple[str, str]] | None = None,
    ) -> str:
        """Replace one section, target *x*, or exact text, of the page *message_id* names, or
        add sections *side* one, in the server's own copy (``wire_patch``);
        returns the new message's id. The page shown is replaced in place;
        another is sent as the page, as a re-send is. A section's clocks
        restart; *x*, an ordinal, must name the page's latest message, as
        ``mark``'s does."""
        async with self._lock:
            refuse_left(self.log, message_id, self.latest)  # ADR-614
            mid, edited, renewed = await asyncio.to_thread(
                patch_page, self.log, message_id, markdown, section, x, side, replace
            )
            new_id = self._next_id()  # a refused patch changes nothing, ids included
            replaces = mid if mid == self.latest else None
            frames = await asyncio.to_thread(
                record,
                self.log,
                self.includes,
                new_id,
                edited,
                replaces=replaces,
                continues=mid,
                renewed=renewed,
            )
        await self._complete(frames, frames)
        return new_id

    async def _abandon(self) -> None:
        """Forget a stream that will not end, so no joiner is sent its start."""
        async with self._send_lock:
            self._streaming = []

    async def _agents(self, message_id: str, edit: Callable[[str], list[dict]]) -> str:
        """The agent's *edit* of *message_id* into a new id, broadcast in place;
        refused on a page a backend navigated away from (ADR-614)."""
        async with self._lock:
            refuse_left(self.log, message_id, self.latest)
            new_id = self._next_id()
            frames = await asyncio.to_thread(edit, new_id)
        await self._complete(frames, frames)
        return new_id

    async def mark(self, message_id: str, x: int, state: str) -> str:
        """Tick, untick or disable target *x* the way the agent decided; the
        replacement goes out with ``r``. Returns the new message's id."""
        return await self._agents(
            message_id, lambda new_id: self.log.mark(message_id, x, state, new_id)
        )

    async def set_slider(self, message_id: str, x: int, value: float) -> str:
        """Set slider target *x* and broadcast the replacement in place."""
        return await self._agents(
            message_id,
            lambda new_id: self.log.set_slider(message_id, x, value, new_id),
        )

    async def set_bar(self, message_id: str, key: str, value: float) -> str:
        """Move the static bar under *key* and broadcast the replacement in place."""
        return await self._agents(
            message_id, lambda new_id: self.log.set_bar(message_id, key, value, new_id)
        )

    async def apply_feed(self, message_id: str, edit: Callable[..., str]) -> str:
        """A feed's tick: *edit* writes its bars and slots, one replacement (ADR-608)."""
        new_id = self._next_id()
        async with self._lock:
            frames = await asyncio.to_thread(
                self.log.set_bars, message_id, edit, new_id
            )
        await self._complete(frames, frames)
        return new_id

    async def receive(
        self, frame: dict, peer: str
    ) -> Verified | Prompt | Recorded | Rejected:
        """Verify, and queue only what the agent should be woken for.

        A :class:`Recorded` event is accepted and in the log; it is simply not
        delivered, because a committing press will report it (``wire.Recorded``).

        A press that commits values is written into the server's copy first
        (``MessageLog.commit``) and handed over naming the replacement, so the
        page the agent's next ``patch`` or ``mark`` edits is the one the user
        committed. The replacement goes to the window only while it shows that
        page: an answer that overtook the press stays on screen.

        A click whose slug has a handler goes to it first (``wire_includes``):
        answered, by a redraw or a new page, it is a line of ``handled``, not
        an event.
        """
        frames: list[dict] = []
        handled = None
        async with self._lock:
            if frame["t"] == "p":
                result = self.log.verify_prompt(frame, peer)
                if isinstance(result, Prompt):
                    result = replace(result, on=self.latest, at=time.monotonic())
            else:
                result = self.log.verify(frame, peer)
                if isinstance(result, Verified) and result.settled:
                    new_id, shown = self._next_id(), result.message_id == self.latest
                    try:
                        written = await asyncio.to_thread(
                            self.log.commit, result, new_id
                        )
                    except FrameError as exc:  # delivered as before, unwritten
                        print(f"[wire] commit not written: {exc}", file=sys.stderr)
                    else:
                        frames = written if shown else []
                        result = replace(result, message_id=new_id)
                if isinstance(result, Verified) and (
                    handler := self.handlers.get(result.action.action or "")
                ):
                    handled = await asyncio.to_thread(
                        answer,
                        self.log,
                        self.includes,
                        handler,
                        result,
                        self.latest or result.message_id,
                        self._next_id(),
                    )
        if frames:
            await self._complete(frames, frames)
        if handled is not None and handled.left is not None:  # a new page (ADR-614)
            handled = handled.ending(self.feeds.end_all("replaced", handled.left))
        if handled is not None:  # a line of the digest: answered, or failed
            self.handled.append(handled.line)
        if handled is not None and handled.frames and isinstance(result, Verified):
            # Answered by the backend: one replacement, never queued; the window
            # lets the button go in any state, as the agent never had the click.
            await self._complete(handled.frames, handled.frames)
            await self.set_state(self.state or "i", answered={peer: [result.seq]})
            return result
        if isinstance(result, (Verified, Prompt)):
            await self.events.put(result)
        return result


def _origin_ok(origin: str | None, allowed: Collection[str], loopback: bool) -> bool:
    if origin is None:
        return True  # not a browser: a native client or a script
    if origin in allowed:
        return True
    return loopback and (urlsplit(origin).hostname or "") in LOOPBACK


def build_app(
    conversation: Conversation,
    allowed_origins: Collection[str] = (),
    allow_loopback_origins: bool = False,
    bearer: str | None = None,
    max_events_per_second: int = MAX_EVENTS_PER_SECOND,
    routes: Sequence[BaseRoute] = (),
) -> Starlette:
    """The ASGI app: ``/ws``, speaking the wire to *conversation*, the feeds'
    posts, and the host's own *routes*."""

    peer_ids = itertools.count(1)

    async def endpoint(ws: WebSocket) -> None:
        origin = ws.headers.get("origin")
        sent = ws.headers.get("authorization", "")
        if not _origin_ok(origin, allowed_origins, allow_loopback_origins) or (
            bearer is not None
            and not hmac.compare_digest(sent.encode(), f"Bearer {bearer}".encode())
        ):
            await ws.close(code=1008)  # before accept: the handshake gets a 403
            return
        await ws.accept()
        # Minted, never derived from the socket: nothing holds the socket once
        # `leave` discards it, so CPython may reuse `id(ws)` for the next client,
        # whose `q=1` would collide with the last one's and be dropped as a
        # duplicate without an error frame. The rule is in AGENTS.md: key on
        # identity only for objects you hold a reference to.
        peers = next(peer_ids)
        peer = f"p{peers}"
        try:
            hello = decode_client(await ws.receive_text())
            if hello["t"] != "h":
                raise FrameError("bad_frame", "the first frame must be hello")
        except FrameError as exc:
            await ws.send_text(encode({"t": "x", "code": exc.code}).decode())
            await ws.close(code=1008)
            return
        except (WebSocketDisconnect, KeyError):
            return
        await conversation.join(ws, peer)
        recent: collections.deque[float] = collections.deque()
        try:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                now = time.monotonic()
                recent.append(now)
                while recent and now - recent[0] > 1.0:
                    recent.popleft()
                if len(recent) > max_events_per_second:
                    await ws.close(code=1008)
                    break
                try:
                    frame = decode_client(message.get("text") or b"\x00")
                except FrameError as exc:  # unread, so its `q` is unknown
                    await ws.send_text(encode({"t": "x", "code": exc.code}).decode())
                    await conversation.tell(ws)  # refused: released as below
                    continue
                if frame["t"] == "k":
                    conversation.typed_at = time.monotonic()
                    continue
                if frame["t"] not in ("e", "p"):
                    continue  # a second hello changes nothing
                result = await conversation.receive(frame, peer)
                if isinstance(result, (Rejected, Recorded)):
                    if isinstance(result, Rejected) and result.code != "duplicate":
                        await ws.send_text(encode(result.frame()).decode())
                    # An event that reaches no agent -- refused (here, or unread
                    # above), or recorded and deliberately not delivered -- is
                    # followed by no state frame, and a client that blocked itself
                    # on send (ADR-601 allows it, "since the server's `w` follows")
                    # then waits for something that is never coming. Re-send the
                    # state it is already in, to that socket alone: it unblocks the
                    # sender without inventing a frame, and says nothing a client
                    # could answer, so no retry loop is possible. That last part is
                    # why a duplicate goes unanswered; being stuck is a different
                    # situation from being ignored, and only this one needs a word.
                    await conversation.tell(ws)
        except WebSocketDisconnect:
            pass
        finally:
            conversation.leave(ws)

    feeds = route(lambda: conversation.feeds)
    return Starlette(routes=[WebSocketRoute("/ws", endpoint), feeds, *routes])


def _config(app: Starlette, host: str, port: int) -> uvicorn.Config:
    return uvicorn.Config(
        app,
        host=host,
        port=port,
        ws="websockets-sansio",
        ws_max_size=MAX_CLIENT_FRAME_BYTES,
        ws_per_message_deflate=False,
        lifespan="off",
        log_level="warning",
    )


class Served:
    """The server on a background thread, for a synchronous caller: a test, or
    the MCP demo bridge. ``call`` runs a conversation coroutine on its loop."""

    def __init__(
        self,
        conversation: Conversation,
        host: str = "127.0.0.1",
        port: int = 0,
        **app: Any,
    ) -> None:
        self.conversation = conversation
        # A prompt taken off the queue behind clicks, kept for the next call so
        # batching it is refused without losing it or reordering it.
        self._held: Event | None = None
        # Batches taken by a wait nobody was left to answer, served first, whole
        # but for a presence that is no longer true.
        self._returned: list[list[Event]] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, port))
        self.port = self._sock.getsockname()[1]
        self.url = f"ws://{host}:{self.port}/ws"
        self._server = uvicorn.Server(
            _config(build_app(conversation, **app), host, port)
        )
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        deadline = time.monotonic() + 10
        while not self._server.started and time.monotonic() < deadline:
            time.sleep(0.02)

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._server.serve(sockets=[self._sock]))

    def call(self, coro: Any, timeout: float = 30.0) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def _current(self, presence: Presence) -> bool:
        """Is this presence still true? ``closed`` only while nobody watches."""
        watching = self.conversation.watchers > 0
        return watching if presence.kind == "reconnected" else not watching

    def next_event(self, timeout: float = 5.0) -> Event | None:
        """The next event alone, or None on *timeout*."""
        batch = self.next_events(timeout, limit=1)
        return batch[0] if batch else None

    def forget_presence(self) -> None:
        """Drop every presence not yet read, keeping the rest in order.

        Called as a new answer is sent: a window that closed or came back before
        it says nothing about the window that will show it, and a ``closed`` read
        while a launched window is still starting would stop an agent waiting on
        a live one. What the user did is never dropped.
        """

        def kept(batch: list) -> list:
            return [e for e in batch if not isinstance(e, Presence)]

        async def forget() -> None:
            events = self.conversation.events
            queued = []
            while not events.empty():
                queued.append(events.get_nowait())
            for event in kept(queued):
                events.put_nowait(event)
            if isinstance(self._held, Presence):
                self._held = None
            self._returned = [b for b in map(kept, self._returned) if b]

        self.call(forget())

    def put_back(self, batch: list[Event]) -> None:
        """Return a batch no caller received, to be the next one served."""
        if batch:
            self._returned.append(batch)

    def next_events(self, timeout: float = 5.0, limit: int = 32) -> list[Event]:
        """Everything already waiting, oldest first: block for the first, then
        take what queued behind it.

        A click the agent was not listening for waits in the queue, so N clicks
        cost N waits — and a wait is a model turn. Draining makes them one.

        **A prompt is never batched.** It is the user's own words (ADR-601), the
        one client string that reaches the agent, and joining it to sentences
        built from the agent's own Markdown would blur the provenance boundary
        the protocol keeps. So a leading prompt comes back alone, and a prompt
        behind clicks is held for the next call rather than dropped or reordered.
        """
        # A put-back batch waited for a caller, and a presence in it may have
        # stopped being true meanwhile: it is checked now, as a queue read is.
        while self._returned:
            with contextlib.suppress(IndexError):  # another wait may take it first
                batch = [
                    e
                    for e in self._returned.pop(0)
                    if not isinstance(e, Presence) or self._current(e)
                ]
                if batch:
                    return batch
        held, self._held = self._held, None

        async def gather() -> list[Event]:
            batch: list[Event] = []
            if held is not None:
                batch.append(held)
            else:
                try:
                    first = self.conversation.events.get()
                    batch.append(await asyncio.wait_for(first, timeout))
                except TimeoutError:
                    return []
            # A presence taken off the queue may already be stale: a window that
            # closed and came back before anyone read it is not gone, and saying
            # so would stop an agent waiting on a live window. Checked against
            # who is watching NOW, which is the only thing that is true.
            while (
                batch and isinstance(batch[0], Presence) and not self._current(batch[0])
            ):
                batch.pop()
                try:
                    batch.append(self.conversation.events.get_nowait())
                except asyncio.QueueEmpty:
                    return []
            while len(batch) < limit and batch and isinstance(batch[0], Verified):
                try:
                    nxt = self.conversation.events.get_nowait()
                except asyncio.QueueEmpty:
                    break
                # Only clicks batch. A prompt is the user's own words and a
                # presence change is about the connection: each is a call of its
                # own, and holding it keeps the order the user made it in.
                if not isinstance(nxt, Verified):
                    self._held = nxt
                    break
                batch.append(nxt)
            return batch

        return self.call(gather(), timeout + 1)

    def stop(self) -> None:
        self._loop.call_soon_threadsafe(self.conversation.feeds.stop)
        self._server.should_exit = True
        self._thread.join(timeout=10)


async def _demo(document: Path, host: str, port: int) -> None:
    """Serve *document*; print each click's agent sentence; tick boxes on click."""
    conversation = Conversation()
    await conversation.send(document.read_text(encoding="utf-8"))
    await conversation.set_state("l")  # the loop below takes every event
    server = uvicorn.Server(_config(build_app(conversation), host, port))
    serving = asyncio.create_task(server.serve())
    print(f"[wire] serving {document} at ws://{host}:{port}/ws", file=sys.stderr)
    while not serving.done():
        event = await conversation.events.get()
        if isinstance(event, Presence):
            print(f"[agent] the window {event.kind}", file=sys.stderr)
            continue
        if isinstance(event, Prompt):
            print(f"[agent] the user wrote: {event.text}", file=sys.stderr)
            continue
        if isinstance(event, FeedEnded):  # this demo opens none
            continue
        print(f"[agent] {event.agent_text()}", file=sys.stderr)
        if event.action.checked is not None:  # the demo "agent" agrees to every tick
            state = "checked" if event.action.checked else "unchecked"
            await conversation.mark(event.message_id, event.ordinal, state)
        elif event.action.value is not None:
            await conversation.set_slider(
                event.message_id, event.ordinal, event.action.value
            )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="md2ui-wire", description="Serve one Markdown document over the md2ui wire"
    )
    parser.add_argument("markdown", help="the document to serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    document = Path(args.markdown)
    if not document.is_file():
        parser.error(f"no such file: {document}")
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_demo(document, args.host, args.port))


# md_hash is part of what a client of this binding needs; re-exported for it.
__all__ = ["Conversation", "Presence", "Served", "build_app", "main", "md_hash"]

if __name__ == "__main__":
    main()
