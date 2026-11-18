"""
Unit tests for the reference WebSocket binding (ADR-601): the server a backend
runs, and the client the app runs, over a real socket on localhost.

Pinned here:

  * a client says hello and is sent the latest message; a click is verified and
    queued for the agent, and a forged one is answered with its error code;
  * the security defaults: hello first, a browser Origin the host did not name
    refused at the handshake (localhost too), a ``bearer`` server refusing an
    upgrade without its secret, an oversize frame closing the socket, a flood disconnected;
  * ``q`` counts per connection, so two clients' first events both count;
  * ``mark`` sends the replacement to every client, and the old message is stale;
  * a streamed message reaches the app's ``WireClient`` whole, hash checked, and
    the app's click reaches the agent by ordinal;
  * every message opens with ``m``, an empty stream too, and one too large for a
    frame is refused to its caller before a client is sent it;
  * the agent's state goes to a joiner and to every client on change, and a
    prompt reaches the agent as the user's words, within its own size cap
    (ADR-601);
  * a replacement keeps the window's clicks on targets it left as they were --
    none, when its Markdown is unchanged, the agent's "no change" -- and
    a click the replacement overtook (refused ``stale``) goes again, once, to the
    same target of the message now shown (ADR-601).

Run with: uv run python tests/wire_server_tests.py
"""

import asyncio
import contextlib
import io
import json
import threading
import time
from pathlib import Path
from typing import Any, cast

from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.sync.client import connect

from md2ui import session
from md2ui.pipeline.render_actions import action_targets
from md2ui.wire import FrameError, MessageLog, Prompt, Verified
from md2ui.wire_client import (
    WireClient,
    carried_states,
    ordinal_of,
    released,
    still_shown,
)
from md2ui.wire_server import Conversation, Served

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "data/markdown/tests/tests-link-actions.md"
ASK = "# Ask\n\nWant the report?\n\n[Yes](agent:generate-report?format=pdf) *[No](agent:cancel)*\n"

_MODELS = None


def _kit():
    global _MODELS
    if _MODELS is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _MODELS = session.load_grouping_kit()
    return _MODELS


def _served(markdown: str | None = ASK, **app) -> tuple[Served, str | None]:
    served = Served(Conversation(_kit()), **app)
    mid = None
    if markdown is not None:
        with contextlib.redirect_stdout(io.StringIO()):
            mid = served.call(served.conversation.send(markdown))
    return served, mid


def _frames(ws, n: int) -> list[dict]:
    return [json.loads(ws.recv(timeout=5)) for _ in range(n)]


def test_hello_then_the_latest_message_then_verified_events():
    served, mid = _served()
    try:
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            message, end = _frames(ws, 2)
            assert (message["t"], message["m"], end["t"]) == ("m", mid, "z"), message
            ws.send(
                json.dumps({"t": "e", "m": mid, "x": 0, "q": 1, "a": "generate-report"})
            )
            event = served.next_event()
            assert isinstance(event, Verified), "the click never reached the agent"
            assert event.agent_text() == (
                f'User chose "Yes": generate-report {{format: pdf}} (message {mid})'
            ), event.agent_text()
            ws.send(json.dumps({"t": "e", "m": mid, "x": 1, "q": 2, "a": "delete-all"}))
            (error,) = _frames(ws, 1)
            assert error == {"t": "x", "code": "slug_mismatch", "m": mid, "q": 2}, error
    finally:
        served.stop()
    print("  ✓  hello → latest message; a click is verified; a forged one refused")


def test_the_first_frame_must_be_hello():
    served, mid = _served()
    try:
        with connect(served.url, compression=None) as ws:
            ws.send(json.dumps({"t": "e", "m": mid, "x": 0, "q": 1}))
            (error,) = _frames(ws, 1)
            assert error["code"] == "bad_frame", error
            try:
                ws.recv(timeout=5)
            except ConnectionClosed as exc:
                assert exc.rcvd is not None and exc.rcvd.code == 1008, exc
            else:
                raise AssertionError("the socket stayed open")
    finally:
        served.stop()
    print("  ✓  an event before hello is refused and the socket closed")


def _refused(url: str, **kw) -> bool:
    """Whether the handshake to *url* is refused with a 403."""
    try:
        with connect(url, compression=None, **kw):
            pass
    except InvalidStatus as exc:
        assert exc.response.status_code == 403, exc.response.status_code
        return True
    return False


def test_only_named_origins_are_let_in_at_the_handshake():
    loopback_page = "http://localhost:3000"
    served, _mid = _served()
    try:
        assert _refused(served.url, origin="https://evil.example")
        assert _refused(served.url, origin=loopback_page), "a localhost page got in"
        assert not _refused(served.url), "a native client (no Origin) was refused"
    finally:
        served.stop()
    named, _mid = _served(allowed_origins=[loopback_page])
    try:
        with connect(named.url, origin=loopback_page, compression=None) as ws:  # type: ignore[arg-type]
            ws.send('{"t":"h","v":1}')
            assert _frames(ws, 2)[0]["t"] == "m"
    finally:
        named.stop()
    print("  ✓  a browser origin gets in only when named, localhost too; native passes")


def test_a_bearer_server_refuses_an_upgrade_without_it():
    served, mid = _served(bearer="s3cret")
    try:
        assert _refused(served.url), "no Authorization was let in"
        assert _refused(served.url, additional_headers={"Authorization": "Bearer nope"})
        client = WireClient(served.url, bearer="s3cret")
        client.start()
        first = client.wait_first()
        assert first is not None and first.message_id == mid, first
        client.close()
    finally:
        served.stop()
    print(
        "  ✓  a bearer server: 403 without the secret, the app client gets in with it"
    )


def test_oversize_frames_and_floods_close_the_socket():
    served, mid = _served()
    try:
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 2)
            ws.send("x" * 9000)
            try:
                ws.recv(timeout=5)
            except ConnectionClosed as exc:
                assert exc.rcvd is not None and exc.rcvd.code == 1009, exc
            else:
                raise AssertionError("an oversize frame was read")
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 2)
            try:
                for q in range(1, 60):
                    ws.send(json.dumps({"t": "e", "m": mid, "x": 99, "q": q}))
                while True:
                    ws.recv(timeout=5)
            except ConnectionClosed as exc:
                assert exc.rcvd is not None and exc.rcvd.code == 1008, exc
    finally:
        served.stop()
    print("  ✓  an oversize frame closes with 1009; a flood with 1008")


def test_a_refused_event_unblocks_its_sender():
    """A client blocks itself on send (ADR-601) because the server's `w` follows.
    A REFUSED event reaches no agent, so no `w` follows and nothing releases it —
    leaving the window stuck in working until the idle deadline. The server
    re-states the state it is already in, to that socket alone: it unblocks the
    sender, and says nothing a client could answer, so no retry loop is possible.
    """
    served, mid = _served(FIXTURE.read_text())
    try:
        served.call(served.conversation.set_state("l"))
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 2)  # the message and its end
            assert json.loads(ws.recv(timeout=5))["t"] == "s", "the joiner's state"
            ws.send(json.dumps({"t": "e", "m": mid, "x": 14, "q": 1, "c": True}))
            assert served.next_event() is not None, "the first is accepted"
            # The same `q` again: refused as a duplicate, which is never answered.
            ws.send(json.dumps({"t": "e", "m": mid, "x": 14, "q": 1, "c": True}))
            answer = json.loads(ws.recv(timeout=5))
            assert answer == {"t": "s", "s": "l"}, answer
    finally:
        served.stop()
    print("  ✓  a refused event is answered with the state, so the sender unblocks")


def test_an_oversized_commit_press_unblocks_its_sender():
    """A commit press may carry 32 settled values (`vs`), and 32 do not always fit
    the 512-byte event cap: with a long slug the frame is refused `too_large`
    before it is read, so its `m` and `q` are unknown. It is refused like any
    event that reaches no agent, and so released the same way: the state again,
    to that socket alone."""
    slug = "a" * 128
    boxes = "".join(f"- [ ] item {n}\n" for n in range(32))
    served, mid = _served(f"# Form\n\n{boxes}\n[Done](agent:{slug}?md2ui.commit=1)\n")
    try:
        served.call(served.conversation.set_state("l"))
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 2)  # the message and its end
            assert json.loads(ws.recv(timeout=5))["t"] == "s", "the joiner's state"
            press = {"t": "e", "m": mid, "x": 32, "q": 1, "a": slug}
            press["vs"] = [[n, False] for n in range(32)]
            assert len(json.dumps(press, separators=(",", ":"))) > 512
            ws.send(json.dumps(press, separators=(",", ":")))
            refusal, answer = _frames(ws, 2)
            assert refusal == {"t": "x", "code": "too_large"}, refusal
            assert answer == {"t": "s", "s": "l"}, answer
            handed = served.next_events(timeout=0.5)
            assert not any(isinstance(e, Verified) for e in handed), handed
    finally:
        served.stop()
    print("  ✓  an oversized commit press is refused, then answered with the state")


FORM = (
    "# Smash\n\nQuantity: [1/9]\n\nSpice: [2/5]\n\n"
    "[Single](agent:size?n=1&md2ui.choice=size) | [Double](agent:size?n=2&md2ui.choice=size)\n\n"
    "[Add to cart](agent:add?id=smash&md2ui.commit=1)\n\n[Ask](agent:ask)\n"
)


def _pressed(ws, served: Served, frame: dict) -> tuple[list[dict], list]:
    """Send *frame*; what this client was answered, and what the agent was handed."""
    ws.send(json.dumps(frame))
    answered = []
    while not answered or answered[-1]["t"] != "s":
        try:
            answered.append(json.loads(ws.recv(timeout=0.5)))
        except TimeoutError:
            break
    return answered, served.next_events(timeout=0.5)


def test_a_refused_commit_press_leaves_no_trace():
    """A refused event is not in the log (protocol/README.md), so it spends
    nothing: a commit press refused for one of its `vs` values neither fires
    its button -- the user's corrected press reaches the agent instead of
    being dropped as a duplicate -- nor reports the values it carried. A press
    that did fire is still fired once."""
    served, mid = _served(FORM)
    assert mid is not None
    press = {"t": "e", "m": mid, "x": 4, "a": "add"}
    try:
        served.call(served.conversation.set_state("l"))
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 3)  # the message, its end, the joiner's state
            answered, handed = _pressed(
                ws, served, press | {"q": 1, "vs": [[0, 4], [1, 99]]}
            )
            assert answered == [
                {"t": "x", "code": "bad_value", "m": mid, "q": 1},
                {"t": "s", "s": "l"},
            ], answered
            assert handed == [], handed
            assert served.conversation.log.requested(mid) == {}, (
                "a refused value reported"
            )
            # Valid, and at what the page says, so the press writes no new page
            # and the button can be pressed again on the same message.
            answered, handed = _pressed(ws, served, press | {"q": 2, "vs": [[0, 1]]})
            assert [type(e) for e in handed] == [Verified], (answered, handed)
            answered, handed = _pressed(ws, served, press | {"q": 3, "vs": [[0, 1]]})
            assert (answered, handed) == ([{"t": "s", "s": "l"}], []), (
                "fired twice",
                answered,
                handed,
            )
    finally:
        served.stop()
    print(
        "  ✓  a commit press refused for its vs spends nothing; a fired one stays fired"
    )


def test_a_refusal_checked_before_the_press_still_spends_nothing():
    """The refusals read before a press is recorded keep the button usable, as
    they always did: stale, bad_target, slug_mismatch, and bad_value on `v` or
    on `c` (a choice option cleared) -- the option can then still be chosen."""
    served, old = _served(FORM)
    assert old is not None
    try:
        served.call(served.conversation.set_state("l"))
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 3)
            with contextlib.redirect_stdout(io.StringIO()):
                mid = served.call(served.conversation.mark(old, 5, "disabled"))
            _frames(ws, 2)  # the replacement and its end
            press = {"t": "e", "m": mid, "x": 4, "a": "add"}
            for q, (code, frame) in enumerate(
                (
                    ("stale", press | {"m": old}),
                    ("bad_target", press | {"x": 99}),
                    ("slug_mismatch", press | {"a": "nope"}),
                    ("bad_value", press | {"v": 3}),
                    ("bad_target", press | {"c": True}),
                    (
                        "bad_value",
                        {"t": "e", "m": mid, "x": 2, "a": "size", "c": False},
                    ),
                ),
                start=1,
            ):
                answered, handed = _pressed(ws, served, frame | {"q": q})
                assert answered[0]["code"] == code and handed == [], (
                    code,
                    answered,
                    handed,
                )
            option = {"t": "e", "m": mid, "x": 2, "q": 8, "a": "size", "c": True}
            got = _pressed(ws, served, option)
            assert got == ([{"t": "s", "s": "l"}], []), got
            answered, handed = _pressed(ws, served, press | {"q": 9, "vs": [[0, 4]]})
            assert [type(e) for e in handed] == [Verified], (answered, handed)
    finally:
        served.stop()
    print(
        "  ✓  stale, bad_target, slug_mismatch, bad_value on v/c leave the press usable"
    )


def test_seq_counts_per_connection():
    """`q` is per connection, so every client's first event counts.

    Looped, because a reused peer key collides only sometimes: keyed on `id(ws)`,
    a discarded socket's address can be reused, and the next client's `q=1` would
    be dropped as an unanswered duplicate. Target 14 is a task box: repeatable, so the fire-once guard
    on bare `agent:` buttons cannot be mistaken for this.
    """
    served, mid = _served(FIXTURE.read_text())
    try:
        for round_ in range(12):
            with connect(served.url, compression=None) as ws:
                ws.send('{"t":"h","v":1}')
                _frames(ws, 2)
                ws.send(json.dumps({"t": "e", "m": mid, "x": 14, "q": 1}))
                assert served.next_event() is not None, f"connection {round_}"
        # And two different bare buttons, each firing once on its own connection.
        for x in (0, 1):
            with connect(served.url, compression=None) as ws:
                ws.send('{"t":"h","v":1}')
                _frames(ws, 2)
                ws.send(json.dumps({"t": "e", "m": mid, "x": x, "q": 1}))
                assert served.next_event() is not None, f"client {x}'s first event"
    finally:
        served.stop()
    print("  ✓  every connection's q=1 counts; a peer key is minted, not an address")


def test_mark_replaces_the_message_for_every_client():
    served, mid = _served(FIXTURE.read_text())
    assert mid is not None
    try:
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            _frames(ws, 2)
            with contextlib.redirect_stdout(io.StringIO()):
                new = served.call(served.conversation.mark(mid, 14, "checked"))
            message, end = _frames(ws, 2)
            assert (message["m"], message["r"], end["m"]) == (new, mid, new), message
            assert "- [x] Review the numbers" in message["md"]
            ws.send(json.dumps({"t": "e", "m": mid, "x": 0, "q": 1}))
            assert _frames(ws, 1)[0]["code"] == "stale"
    finally:
        served.stop()
    print("  ✓  mark: every client gets the replacement; the old message is stale")


def test_the_app_client_streams_in_and_clicks_out():
    served, _mid = _served(None)
    client = WireClient(served.url)
    try:
        client.start()
        chunks = [
            "# Ask\n\nWant the ",
            "report?\n\n[Yes](agent:generate-report?format=pdf)",
            " *[No](agent:cancel)*\n",
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            mid = served.call(served.conversation.stream(chunks))
        deadline = time.monotonic() + 5
        got = []
        while not got and time.monotonic() < deadline:
            got = client.poll()
            time.sleep(0.02)
        assert len(got) == 1 and got[0].markdown == "".join(chunks), got
        with contextlib.redirect_stdout(io.StringIO()):
            ast = session.group_markdown(got[0].markdown, _kit())
        assert ast is not None
        targets = action_targets(ast.to_dict())
        no = next(
            t for t in targets if t.action is not None and t.action.action == "cancel"
        )
        x = ordinal_of(targets, no.key)
        assert x == 1, x
        client.send_event(got[0].message_id, x, action="cancel")
        event = served.next_event()
        assert isinstance(event, Verified) and event.action.action == "cancel", event
        assert got[0].message_id == mid
    finally:
        client.close()
        served.stop()
    print("  ✓  the app's client: a streamed message whole, a click out by ordinal")


def test_a_client_joining_mid_stream_gets_the_whole_message():
    """A client whose hello lands while a message streams still gets it whole:
    the join replays the frames already sent, so the joiner never gets only the
    tail, whose hash would fail."""
    served, _mid = _served(None)
    gate = threading.Event()
    chunks = [
        "# Ask\n\nWant the ",
        "report?\n\n[Yes](agent:generate-report?format=pdf)",
        " *[No](agent:cancel)*\n",
    ]

    async def tokens():
        yield chunks[0]
        while not gate.is_set():
            await asyncio.sleep(0.01)
        for chunk in chunks[1:]:
            yield chunk

    done: list[str] = []
    streamer = threading.Thread(
        target=lambda: done.append(served.call(served.conversation.stream(tokens())))
    )
    client = WireClient(served.url)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            streamer.start()
            time.sleep(0.2)  # the first chunk is out; the stream waits on the gate
            client.start()
            deadline = time.monotonic() + 5
            while served.conversation.watchers < 1 and time.monotonic() < deadline:
                time.sleep(0.01)
            gate.set()
            streamer.join(timeout=30)
        got: list = []
        deadline = time.monotonic() + 5
        while not got and time.monotonic() < deadline:
            got = client.poll()
            time.sleep(0.02)
        assert len(got) == 1 and got[0].markdown == "".join(chunks), got
        assert done == [got[0].message_id], (done, got)
    finally:
        client.close()
        served.stop()
    print("  ✓  a client joining mid-stream gets the whole message, hash intact")


def test_the_state_reaches_every_client_and_a_prompt_the_agent():
    served, mid = _served()
    try:
        served.call(served.conversation.set_state("l"))
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            frames = _frames(ws, 3)
            assert frames[2] == {"t": "s", "s": "l"}, frames
            served.call(served.conversation.set_state("l"))  # a repeat sends nothing
            served.call(served.conversation.set_state("w"))
            assert _frames(ws, 1)[0] == {"t": "s", "s": "w"}
            ws.send(json.dumps({"t": "p", "q": 1, "tx": "  Move it to Friday "}))
            got = served.next_event()
            assert isinstance(got, Prompt) and got.text == "Move it to Friday", got
            ws.send(json.dumps({"t": "e", "m": mid, "x": 0, "q": 2, "a": "x" * 600}))
            refused, state = _frames(ws, 2)  # refused unread, then released
            assert (refused["code"], state) == ("too_large", {"t": "s", "s": "w"})
            ws.send(json.dumps({"t": "p", "q": 3, "tx": "x" * 5000}))
            assert _frames(ws, 1)[0]["code"] == "too_large"
    finally:
        served.stop()
    print("  ✓  state: sent on join, then on change; a prompt reaches the agent")


def test_the_app_client_hears_the_state_and_sends_prompts():
    served, _mid = _served()
    client = WireClient(served.url)
    try:
        client.start()
        assert client.wait_first() is not None
        served.call(served.conversation.set_state("i"))
        deadline = time.monotonic() + 5
        while client.state != "i" and time.monotonic() < deadline:
            time.sleep(0.02)
        assert client.state == "i", client.state
        client.send_prompt("What changed?")
        got = served.next_event()
        assert isinstance(got, Prompt) and got.text == "What changed?", got
        for bad in ("   ", "é" * 3000):
            try:
                client.send_prompt(bad)
            except FrameError:
                continue
            raise AssertionError(f"sent {bad[:10]!r}")
    finally:
        client.close()
        served.stop()
    print("  ✓  the app's client: the state lands; a prompt goes out; bad ones don't")


class _Socket:
    """A watcher that keeps what it is sent, for tests that need no real socket."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))


def _watched(run) -> tuple[_Socket, _Socket]:
    """Run *run* against a conversation with one watcher, then join a late one."""
    conversation = Conversation(_kit())
    live, late = _Socket(), _Socket()

    async def main() -> None:
        await conversation.join(cast(Any, live))
        with contextlib.redirect_stdout(io.StringIO()):
            await run(conversation)
        await conversation.join(cast(Any, late))

    asyncio.run(main())
    return live, late


def test_listening_answers_each_connection_its_own_clicks():
    """`u` names the `q`s a connection numbered, so each is sent its own, a
    joiner none; any state may carry them, for a backend's handled click (ADR-612)."""
    conversation = Conversation(_kit())
    one, two, late = _Socket(), _Socket(), _Socket()

    async def main() -> None:
        await conversation.join(cast(Any, one), "p1")
        await conversation.join(cast(Any, two), "p2")
        await conversation.set_state("w")
        await conversation.set_state("l", answered={"p1": [3, 4]})
        await conversation.set_state("l", answered={"p2": [3]})  # no change, yet sent
        # A click a backend answered is released in any state (ADR-612).
        await conversation.set_state("i", answered={"p1": [5]})
        await conversation.join(cast(Any, late), "p3")

    asyncio.run(main())
    assert one.sent[-3:] == [
        {"t": "s", "s": "l", "u": [3, 4]},
        {"t": "s", "s": "l"},
        {"t": "s", "s": "i", "u": [5]},
    ]
    assert two.sent[-3:] == [
        {"t": "s", "s": "l"},
        {"t": "s", "s": "l", "u": [3]},
        {"t": "s", "s": "i"},
    ]
    assert late.sent == [{"t": "s", "s": "i"}], late.sent
    print("  ✓  listening answers each connection its own clicks; a joiner none")


def test_an_over_cap_message_is_refused_before_it_is_sent():
    """The caller gets ``too_large``; no client is sent a frame it would refuse.
    A stream is refused at the chunk that would take the whole message over the
    cap, since a late joiner is sent the whole message as one frame."""
    quotes = '"' * 200_000  # 200 KB of Markdown, 400 KB once escaped

    async def run(conversation: Conversation) -> None:
        for attempt in (
            conversation.send(quotes),
            conversation.stream(["# Head\n", quotes]),
        ):
            try:
                await attempt
            except FrameError as exc:
                assert exc.code == "too_large", exc.code
            else:
                raise AssertionError("an over-cap message was sent")
        await conversation.send("plain")

    live, late = _watched(run)
    assert [f["t"] for f in live.sent] == ["m", "m", "z"], live.sent
    assert live.sent[0]["md"] == "# Head\n" and live.sent[1]["md"] == "plain"
    assert late.sent == live.sent[1:], late.sent
    print("  ✓  an over-cap message is refused with too_large before it is sent")


def test_an_empty_stream_opens_with_a_message_frame():
    """Every message starts with ``m``: a stream of no chunks is an empty ``m``
    then ``z``, as a whole empty message is, so live and late clients agree."""

    async def run(conversation: Conversation) -> None:
        await conversation.stream([])

    live, late = _watched(run)
    assert [f["t"] for f in live.sent] == ["m", "z"], live.sent
    assert live.sent[0]["md"] == "", live.sent
    assert late.sent == live.sent, (live.sent, late.sent)
    print("  ✓  an empty stream sends m then z, to live and late clients alike")


TASKS = "- [ ] A\n- [ ] B\n- [ ] C\n\n[Go](agent:go) [50%]\n"


def test_a_replacement_keeps_the_clicks_it_left_unanswered():
    """The user ticks B after the
    agent drained its events and before its `mark` of A lands. The replacement
    still reads `- [ ] B`, so redrawing it bare would untick B under the user.
    Every local kind stands while its target is untouched -- a tick, a dragged
    slider, a pressed button -- and gives way where the agent changed it."""
    log = MessageLog(_kit())
    with contextlib.redirect_stdout(io.StringIO()):
        log.record("c1", TASKS)
        log.mark("c1", 0, "checked", "c2")
        log.mark("c2", 3, "disabled", "c3")
        log.record("d1", "- [ ] A\n- [ ] B\n", replaces="c3")
    c1, c2, c3 = log.targets("c1"), log.targets("c2"), log.targets("c3")
    assert [t.key for t in c1] == [t.key for t in c2] == [t.key for t in c3]
    md = log.markdown
    a, b, go, slider = (c1[i].key for i in (0, 1, 3, 4))
    states = {a: "checked", b: "checked", go: "pending", slider: 70.0}
    kept = carried_states(c1, c2, states, md("c1"), md("c2"))
    assert kept == {b: "checked", go: "pending", slider: 70.0}, kept
    assert carried_states(c2, c3, kept, md("c2"), md("c3")) == {
        b: "checked",
        slider: 70.0,
    }
    d1 = log.targets("d1")
    assert carried_states(c3, d1, kept, md("c3"), md("d1")) == {}, "a different page"
    print("  ✓  a replacement keeps the clicks it left unanswered, and only those")


def test_an_answered_click_releases_only_its_held_button():
    """An answered `q` lets its button go; a tick, a value and a button nobody
    answered stay as the user left them."""
    log = MessageLog(_kit())
    with contextlib.redirect_stdout(io.StringIO()):
        log.record("c1", TASKS + "\n[Stop](agent:stop)\n")
    targets = log.targets("c1")
    a, go, slider, stop = (targets[i].key for i in (0, 3, 4, 5))
    states = {a: "checked", go: "pending", slider: 70.0, stop: "pending"}
    kept = released(targets, states, [0, 3, 4, 99])
    assert kept == {a: "checked", slider: 70.0, stop: "pending"}, kept
    print("  ✓  an answered click releases its held button, and nothing else")


def test_a_replacement_that_changes_nothing_clears_every_state():
    """The agent declining the user's tick marks the box to the state it already
    has: the replacement's Markdown is the replaced one's, and that "no change"
    is the answer, so every local state goes -- ticks, values and presses alike.
    A stale refusal held for it then finds nothing shown
    and is not re-sent."""
    log = MessageLog(_kit())
    with contextlib.redirect_stdout(io.StringIO()):
        log.record("c1", TASKS)
        log.mark("c1", 1, "unchecked", "c2")
    assert log.markdown("c2") == log.markdown("c1")
    c1, c2 = log.targets("c1"), log.targets("c2")
    b, go, slider = (c1[i].key for i in (1, 3, 4))
    states = {b: "checked", go: "pending", slider: 70.0}
    kept = carried_states(c1, c2, states, log.markdown("c1"), log.markdown("c2"))
    assert kept == {}, kept
    tick = {"t": "e", "m": "c1", "x": 1, "q": 1, "c": True}
    assert not still_shown(tick, c2, kept), "a declined tick is not re-sent"
    print("  ✓  a replacement that changes nothing clears every local state")


def test_a_refused_click_is_re_sent_only_while_shown():
    log = MessageLog(_kit())
    with contextlib.redirect_stdout(io.StringIO()):
        log.record("c1", TASKS)
    targets = log.targets("c1")
    c, slider, go = targets[2].key, targets[4].key, targets[3].key
    tick = {"t": "e", "m": "c0", "x": 2, "q": 1, "c": True}
    assert still_shown(tick, targets, {c: "checked"})
    assert not still_shown(tick, targets, {c: "unchecked"}), "the user undid it"
    assert not still_shown(tick, targets, {}), "the replacement answered it"
    drag = {"t": "e", "m": "c0", "x": 4, "q": 2, "v": 70.0}
    assert still_shown(drag, targets, {slider: 70.0})
    back = {**drag, "v": 50.0}
    assert not still_shown(back, targets, {slider: 50.0}), "the authored value"
    press = {"t": "e", "m": "c0", "x": 3, "q": 3, "a": "go"}
    assert still_shown(press, targets, {go: "pending"})
    assert not still_shown({**tick, "x": 9}, targets, {c: "checked"})
    print("  ✓  a refused click goes again only while the window still shows it")


def _until(read, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        got = read()
        if got:
            return got
        time.sleep(0.02)
    return read()


def test_a_click_the_replacement_overtook_is_sent_again_once():
    """The user ticks C on c1 after the server recorded c2 and before the
    window received it. The server refuses it `stale`, and the window re-sends it to c2's same target
    once c2 is on screen -- the refusal may arrive first -- and a re-send that
    is itself overtaken is let go, so nothing loops."""
    served, c1 = _served(TASKS)
    assert c1 is not None
    client = WireClient(served.url)
    try:
        served.call(served.conversation.set_state("l"))
        client.start()
        assert _until(client.poll)[0].message_id == c1
        with contextlib.redirect_stdout(io.StringIO()):
            c2 = served.call(served.conversation.mark(c1, 0, "checked"))
        seen = client.state_seq
        with contextlib.redirect_stderr(io.StringIO()):
            client.send_event(c1, 2, checked=True)
            # The server answers a refusal with its state: the refusal is in.
            assert _until(lambda: client.state_seq > seen)
        old = served.conversation.log.targets(c1)
        new = served.conversation.log.targets(c2)
        states = carried_states(
            old,
            new,
            {old[2].key: "checked"},
            served.conversation.log.markdown(c1),
            served.conversation.log.markdown(c2),
        )
        assert client.resend_stale(c1, old, states) == [], "c2 is not shown yet"
        assert [m.message_id for m in _until(client.poll)] == [c2]
        again = client.resend_stale(c2, new, states)
        assert [(f["m"], f["x"], f["c"]) for f in again] == [(c2, 2, True)], again
        event = served.next_event()
        assert isinstance(event, Verified), event
        assert (event.message_id, event.ordinal, event.action.checked) == (c2, 2, True)
        assert client.resend_stale(c2, new, states) == [], "sent once"
        # A re-send overtaken in turn is let go: c3 lands before the click on c2
        # arrives, and c4 before its re-send to c3 does.
        with contextlib.redirect_stdout(io.StringIO()):
            c3 = served.call(served.conversation.mark(c2, 1, "checked"))
        untick = {new[2].key: "unchecked"}
        with contextlib.redirect_stderr(io.StringIO()):
            seen = client.state_seq
            client.send_event(c2, 2, checked=False)
            assert _until(lambda: client.state_seq > seen)
            with contextlib.redirect_stdout(io.StringIO()):
                c4 = served.call(served.conversation.mark(c3, 0, "unchecked"))
            seen = client.state_seq
            assert len(client.resend_stale(c3, new, untick)) == 1
            assert _until(lambda: client.state_seq > seen)
        assert client.resend_stale(c4, new, untick) == [], "never a second time"
        assert served.next_event(timeout=0.5) is None
    finally:
        client.close()
        served.stop()
    print("  ✓  a click the replacement overtook goes again, once, to the same target")


TESTS = [
    test_listening_answers_each_connection_its_own_clicks,
    test_an_answered_click_releases_only_its_held_button,
    test_the_state_reaches_every_client_and_a_prompt_the_agent,
    test_the_app_client_hears_the_state_and_sends_prompts,
    test_a_client_joining_mid_stream_gets_the_whole_message,
    test_hello_then_the_latest_message_then_verified_events,
    test_the_first_frame_must_be_hello,
    test_only_named_origins_are_let_in_at_the_handshake,
    test_a_bearer_server_refuses_an_upgrade_without_it,
    test_oversize_frames_and_floods_close_the_socket,
    test_a_refused_event_unblocks_its_sender,
    test_an_oversized_commit_press_unblocks_its_sender,
    test_a_refused_commit_press_leaves_no_trace,
    test_a_refusal_checked_before_the_press_still_spends_nothing,
    test_seq_counts_per_connection,
    test_mark_replaces_the_message_for_every_client,
    test_the_app_client_streams_in_and_clicks_out,
    test_an_over_cap_message_is_refused_before_it_is_sent,
    test_an_empty_stream_opens_with_a_message_frame,
    test_a_replacement_keeps_the_clicks_it_left_unanswered,
    test_a_replacement_that_changes_nothing_clears_every_state,
    test_a_refused_click_is_re_sent_only_while_shown,
    test_a_click_the_replacement_overtook_is_sent_again_once,
]

if __name__ == "__main__":
    print("Wire Server Tests")
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
