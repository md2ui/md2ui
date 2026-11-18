"""The app's side of the wire (ADR-601): a WebSocket client on a background thread.

The window's loop owns every watcher (ADR-600), so this thread only talks. It
receives frames, assembles each message — deltas appended in order, the end's
hash checked — and hands complete ones to the loop through a queue the loop polls
once per tick. A message is handed over only at its end, because that is when its
actions exist (protocol/README.md).

Events go out from the loop's thread; the connection's ``send`` is safe to call
there while this thread receives. So do prompts, what the user typed into the
window's own field; and the server's state frame, what the agent is doing, lands
in :attr:`WireClient.state` (ADR-601). When the connection drops, the state
becomes :data:`DISCONNECTED`, and nothing more is sent: the window stays open and
says so.

A replacement is the agent answering, not a new page: the window keeps what the
user did that the agent has not yet answered, and re-sends a click the server
refused only because the agent replaced its message meanwhile (ADR-601).
"""

from __future__ import annotations

import contextlib
import dataclasses
import queue
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

from md2ui.pipeline.render_actions import Target
from md2ui.wire import (
    VERSION,
    FrameError,
    decode_client,
    decode_server,
    encode,
    md_hash,
)


@dataclass(frozen=True, slots=True)
class Incoming:
    """A complete message: what the window shows next."""

    message_id: str
    markdown: str
    replaces: str | None


@dataclass(frozen=True, slots=True)
class StateWords:
    """What a state frame says beside its letter (ADR-613), each until the next
    frame: the step the agent is on while it works (``n``), and the question it
    asked the prompt bar to show while it listens (``ph``)."""

    note: str | None = None
    placeholder: str | None = None


def ordinal_of(targets: list[Target], key: str) -> int | None:
    """The wire ordinal of the target a click region reports under *key*."""
    for x, target in enumerate(targets):
        if target.key == key:
            return x
    return None


def carried_states(
    old: list[Target],
    new: list[Target],
    states: Mapping[str, str | float],
    old_markdown: str,
    new_markdown: str,
) -> dict[str, str | float]:
    """The window's *states* that a replacement of *old* by *new* leaves standing.

    None, when the replacement's Markdown is the replaced one's: that is the agent
    answering "no change" -- declining a tick by marking the box to the state it
    already has -- so the page shows what it says.

    A state stands where the replacement left its target exactly as it was: the
    agent has not answered it yet, and showing the old Markdown would undo the
    user's click. Where the agent changed the target -- ticked it, moved it,
    disabled it -- its Markdown is the answer. Targets are matched by ordinal, the
    wire's own identity, and only when the replacement offers the same number of
    them, as every ``mark`` does.
    """
    if old_markdown == new_markdown or len(old) != len(new):
        return {}
    kept: dict[str, str | float] = {}
    for before, after in zip(old, new):
        if before.key not in states or before.action is None or after.action is None:
            continue
        # A label is read from the target's neighbours, so disabling the link
        # beside a slider rewords the slider without changing it.
        same = dataclasses.replace(
            after.action, node_id=before.action.node_id, label=before.action.label
        )
        if same == before.action:
            kept[after.key] = states[before.key]
    return kept


def released(
    targets: list[Target], states: Mapping[str, str | float], answered: list[int]
) -> dict[str, str | float]:
    """*states* without the waiting buttons the agent answered: ``answered`` are
    ordinals on the page on screen, which ``carried_states`` keeps ordinals of.
    Only a button waits; a tick or a value the user set stays as they set it."""
    done = {
        targets[x].key
        for x in answered
        if x < len(targets) and states.get(targets[x].key) == "pending"
    }
    return {key: state for key, state in states.items() if key not in done}


def still_shown(
    event: dict, targets: list[Target], states: Mapping[str, str | float]
) -> bool:
    """Whether the window still shows, on the message now on screen, what the
    refused *event* asked for -- and so whether re-sending it says anything."""
    x = event["x"]
    if x >= len(targets) or targets[x].action is None:
        return False
    shown = states.get(targets[x].key)
    if "c" in event:
        return shown == ("checked" if event["c"] else "unchecked")
    if "v" in event:
        # The authored value is the server's baseline: sent, it would be dropped
        # as a repeat, unanswered.
        return shown == event["v"] and event["v"] != targets[x].action.value
    return shown == "pending"


# The window's own state once its server is gone: never a frame, so never one of
# the wire's STATES. A dropped connection is not retried; the agent's next answer
# comes in a new window, from the server that replaced this one.
DISCONNECTED = "disconnected"

# Where a launching backend puts its server's secret for the window: the
# environment, which only the launched process inherits.
WIRE_BEARER = "MD2UI_WIRE_BEARER"

# How often a window may say its user is typing (the `k` frame, ADR-601): enough
# for a server to tell typing under way from typing stopped, not a frame a key.
TYPING_EVERY_SECONDS = 1.0


class Throttle:
    """Lets the first call through, then none until *every* seconds have passed."""

    def __init__(self, every: float) -> None:
        self.every = every
        self._last: float | None = None

    def due(self, now: float) -> bool:
        if self._last is not None and now - self._last < self.every:
            return False
        self._last = now
        return True


class WireClient:
    """One connection to a wire server; ``poll`` from the window's loop."""

    def __init__(
        self,
        url: str,
        origin: str | None = None,
        on_ready: Callable[[], None] | None = None,
        bearer: str | None = None,
    ) -> None:
        self.url = url
        self._origin = origin
        # The server's secret, when it asks for one (wire_server ``bearer``).
        self._headers = {"Authorization": f"Bearer {bearer}"} if bearer else None
        # Called from the receiving thread when a message completes: the window
        # passes glfw.post_empty_event so its loop wakes to poll.
        self.on_ready = on_ready
        self._ready: queue.Queue[Incoming] = queue.Queue()
        self._parts: dict[str, list[str]] = {}
        self._replaces: dict[str, str | None] = {}
        self._seq = 0
        # What the agent is doing, from the server's last state frame: "l", "w",
        # "i", or None before the first; DISCONNECTED once the connection drops.
        # Written by the receiving thread.
        self.state: str | None = None
        # The words the last state frame carried beside its letter (ADR-613).
        self.said = StateWords()
        # Counts state FRAMES, not changes. The server re-states the current
        # state to a client whose event it refused, and that repeat is the whole
        # signal: a window that blocked itself on send has nothing else to
        # release it, so "the same value again" must still register.
        self.state_seq = 0
        # The events sent, by ``q``, so a refusal can be matched to its click;
        # the ``q``s that were already re-sends, which are never re-sent again;
        # and the stale refusals waiting for the replacement that made them stale.
        self._sent: dict[int, dict] = {}
        self._resent: set[int] = set()
        self._stale: queue.Queue[dict] = queue.Queue()
        self._held: list[dict] = []
        # The `q`s a listening state said the agent answered, and the messages
        # the page on screen has been since it was last a new page: an answered
        # click still belongs to it only while its message is one of them.
        self._answered: queue.Queue[list[int]] = queue.Queue()
        self._chain: set[str] = set()
        self._typing = Throttle(TYPING_EVERY_SECONDS)
        self._conn: ClientConnection | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        """Connect and say hello, in the caller's thread so a refusal surfaces
        there; then receive on the background thread."""
        conn = connect(
            self.url,
            origin=self._origin,  # type: ignore[arg-type]
            additional_headers=self._headers,
            compression=None,
            open_timeout=5,
        )
        assert isinstance(conn, ClientConnection)
        self._conn = conn
        conn.send(encode({"t": "h", "v": VERSION}).decode())
        self._thread.start()

    def wait_first(self, timeout: float = 15.0) -> Incoming | None:
        """Block until the first complete message arrives, or *timeout* passes."""
        try:
            return self._taken(self._ready.get(timeout=timeout))
        except queue.Empty:
            return None

    def _taken(self, incoming: Incoming) -> Incoming:
        """*incoming*, now the page on screen: a new page starts a new chain."""
        if incoming.replaces is None:
            self._chain = set()
        self._chain.add(incoming.message_id)
        return incoming

    def _run(self) -> None:
        assert self._conn is not None
        try:
            for text in self._conn:
                try:
                    self._handle(decode_server(text))
                except FrameError as exc:
                    print(f"[wire] refused a server frame: {exc}", file=sys.stderr)
        except ConnectionClosed:
            print("[wire] the server closed the connection", file=sys.stderr)
        finally:
            self.state = DISCONNECTED
            self.state_seq += 1
            if self.on_ready is not None:
                self.on_ready()

    @property
    def connected(self) -> bool:
        return self.state != DISCONNECTED

    def _handle(self, frame: dict) -> None:
        kind, mid = frame["t"], frame.get("m", "")
        if kind == "m":
            self._parts[mid] = [frame["md"]]
            self._replaces[mid] = frame.get("r")
        elif kind == "d":
            self._parts.setdefault(mid, []).append(frame["md"])
        elif kind == "z":
            markdown = "".join(self._parts.pop(mid, []))
            replaces = self._replaces.pop(mid, None)
            if md_hash(markdown) != frame["h"]:
                print(f"[wire] {mid}: hash mismatch, message dropped", file=sys.stderr)
                return
            self._ready.put(Incoming(mid, markdown, replaces))
            if self.on_ready is not None:
                self.on_ready()
        elif kind == "s":
            if "u" in frame:  # queued before the state, so a poll never misses it
                self._answered.put(frame["u"])
            self.said = StateWords(frame.get("n"), frame.get("ph"))
            self.state = frame["s"]
            self.state_seq += 1
            if self.on_ready is not None:
                self.on_ready()
        elif kind == "x":
            print(f"[wire] the server refused an event: {frame}", file=sys.stderr)
            if frame["code"] == "stale" and "q" in frame:
                self._stale.put(frame)

    def poll(self) -> list[Incoming]:
        """Every message completed since the last poll, oldest first."""
        out: list[Incoming] = []
        while True:
            try:
                out.append(self._taken(self._ready.get_nowait()))
            except queue.Empty:
                return out

    def answered(self) -> list[int]:
        """The ordinals of this window's clicks the agent has answered by
        listening again, on the page now on screen. Call it after ``poll``."""
        out: list[int] = []
        while True:
            try:
                for q in self._answered.get_nowait():
                    sent = self._sent.get(q)
                    if sent is not None and sent["m"] in self._chain:
                        out.append(sent["x"])
            except queue.Empty:
                return out

    def send_event(
        self,
        message_id: str,
        ordinal: int,
        action: str | None = None,
        checked: bool | None = None,
        value: float | None = None,
        settled: list | None = None,
    ) -> dict:
        """Report a click on target *ordinal*; returns the frame sent.

        *settled* commits the document's other live values with it — each
        ``[ordinal, number | bool]`` — so a button that means "done" carries what
        the user adjusted rather than costing a turn per control.
        """
        self._seq += 1
        frame: dict = {"t": "e", "m": message_id, "x": ordinal, "q": self._seq}
        if action is not None:
            frame["a"] = action
        if checked is not None:
            frame["c"] = checked
        if value is not None:
            frame["v"] = value
        if settled:
            frame["vs"] = settled
        assert self._conn is not None, "start() first"
        self._conn.send(encode(frame).decode())
        self._sent[self._seq] = frame
        return frame

    def resend_stale(
        self,
        message_id: str,
        targets: list[Target],
        states: Mapping[str, str | float],
    ) -> list[dict]:
        """Re-send, against *message_id* -- its *targets*, the window's *states*
        -- each click refused as ``stale`` that the window still shows; returns
        the frames sent.

        A stale refusal means the agent replaced the message between the click
        and its arrival, so the click reached nobody. It waits here until the
        replacement is on screen -- the refusal can arrive before it -- and is
        then sent once, to the same target. A re-send refused in turn is let go:
        each try is bounded by the agent's own messages, never by a retry loop.
        """
        if not self.connected:
            return []
        while True:
            try:
                refusal = self._stale.get_nowait()
            except queue.Empty:
                break
            q = refusal["q"]
            if q in self._sent and q not in self._resent:
                self._held.append(self._sent[q])
        out: list[dict] = []
        waiting: list[dict] = []
        for event in self._held:
            if event["m"] == message_id:
                waiting.append(event)
            elif still_shown(event, targets, states):
                self._seq += 1
                again = {**event, "m": message_id, "q": self._seq}
                assert self._conn is not None, "start() first"
                self._conn.send(encode(again).decode())
                self._sent[self._seq] = again
                self._resent.add(self._seq)
                out.append(again)
        self._held = waiting
        return out

    def send_prompt(self, text: str) -> dict:
        """Send what the user typed (ADR-601); returns the frame sent. A blank or
        oversize text raises :class:`FrameError` before anything is sent."""
        frame: dict = {"t": "p", "q": self._seq + 1, "tx": text}
        decode_client(encode(frame))
        self._seq += 1
        assert self._conn is not None, "start() first"
        self._conn.send(encode(frame).decode())
        return frame

    def typing(self) -> None:
        """The user pressed a key in the window's field: say so, throttled."""
        if self._conn is not None and self.connected:
            if self._typing.due(time.monotonic()):
                with contextlib.suppress(ConnectionClosed):  # the drop is _run's
                    self._conn.send(encode({"t": "k"}).decode())

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
