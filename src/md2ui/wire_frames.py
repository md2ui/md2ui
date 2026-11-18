"""The wire's frames: what one looks like, and whether a given one is well formed.

Kept apart from ``wire.py`` (ADR-601). The line runs between **the shape of a
frame** and **what a server does with it**: this module says a frame is well
formed, and ``wire.py`` says whether the thing it names exists and what it means.

So nothing here knows about targets, messages or Markdown — it imports nothing
from md2ui at all. That is the point rather than a coincidence: a validator that
could reach a target would be tempted to check one, and the range of a slider's
value is exactly the check that belongs on the other side of this line
(``wire._in_domain``), because the domain is authored per target.

The spec is ``protocol/README.md`` and ``protocol/examples/`` is the conformance
set. ``wire`` re-exports everything public here, so a caller imports either.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable

VERSION = 1
MAX_EVENT_BYTES = 512
# A server frame as a client receives it: UTF-8 bytes of the encoded JSON, so a
# message's Markdown is bounded by what it costs once escaped (a quote or newline
# two bytes, a control character six), not by its own length.
MAX_SERVER_FRAME_BYTES = 256 * 1024
MAX_SLUG = 128
# A prompt the user types into the frontend's own field (ADR-601): its text, and
# the frame that carries it. Every other client frame keeps the event cap.
MAX_PROMPT_BYTES = 4096
MAX_CLIENT_FRAME_BYTES = 8192
# A state frame's words beside its letter (ADR-613): the step the agent is on (`n`)
# and the question it asked the prompt bar to show (`ph`).
MAX_NOTE = MAX_PLACEHOLDER = 200
# How many other targets one event may commit (``vs``). A cart, not a document:
# the frame still has to fit MAX_EVENT_BYTES, which is the real limit.
MAX_SETTLED = 32
# How many answered clicks one `l` may release (``u``): those one wait handed over.
MAX_ANSWERED = 64

# What the agent is doing, as the server tells its frontends (ADR-601): listening
# for input, working on the last input, or idle, with nobody listening.
STATES = frozenset({"l", "w", "i"})

# Only these kinds travel: a `link` and an `#anchor` are the client's business.
FORWARDED_KINDS = frozenset({"agent", "checkbox", "slider"})

_ID = re.compile(r"[A-Za-z0-9._:-]{1,64}\Z")
_HASH = re.compile(r"[0-9a-f]{16}\Z")


class FrameError(ValueError):
    """A frame this protocol refuses; ``code`` is its ``x``-frame error code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def md_hash(markdown: str) -> str:
    """The ``h`` of an end frame: the first 16 hex digits of the SHA-256."""
    return hashlib.sha256(markdown.encode()).hexdigest()[:16]


def encode(frame: dict) -> bytes:
    """One frame as compact UTF-8 JSON."""
    return json.dumps(frame, separators=(",", ":"), ensure_ascii=False).encode()


def escaped_bytes(text: str) -> int:
    """What *text* costs inside an encoded frame: its UTF-8 bytes once escaped."""
    return len(json.dumps(text, ensure_ascii=False).encode()) - 2


def check_server_size(frame: dict) -> None:
    """Refuse a server frame a client would refuse, before it is sent."""
    size = len(encode(frame))
    if size > MAX_SERVER_FRAME_BYTES:
        raise FrameError("too_large", f"{size} bytes")


# --- decoding: strict on known keys, silent on unknown ones --------------------


def _is_nat(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _need(frame: dict, key: str, ok: bool) -> None:
    if not ok:
        raise FrameError("bad_frame", f"{frame.get('t')!r}: bad or missing {key!r}")


def _id(frame: dict, key: str, optional: bool = False) -> None:
    if optional and key not in frame:
        return
    value = frame.get(key)
    _need(frame, key, isinstance(value, str) and bool(_ID.match(value)))


def _markdown(frame: dict) -> None:
    # No size of its own: the frame cap bounds it, and is the stricter of the two.
    _need(frame, "md", isinstance(frame.get("md"), str))


def _check_message(f: dict) -> None:
    _id(f, "m")
    _id(f, "r", optional=True)
    _markdown(f)


def _check_delta(f: dict) -> None:
    _id(f, "m")
    _need(f, "s", _is_nat(f.get("s")))
    _markdown(f)


def _check_end(f: dict) -> None:
    _id(f, "m")
    _need(f, "h", isinstance(f.get("h"), str) and bool(_HASH.match(f["h"])))


def _check_error(f: dict) -> None:
    _need(f, "code", isinstance(f.get("code"), str))
    _id(f, "m", optional=True)
    _need(f, "q", "q" not in f or _is_nat(f.get("q")))


def _check_hello(f: dict) -> None:
    _need(f, "v", _is_nat(f.get("v")) and f["v"] >= 1)
    if f["v"] != VERSION:
        raise FrameError("bad_version", str(f["v"]))


def _is_value(value: object) -> bool:
    """A number a client may send as a target's value: finite, numeric, not a bool.

    **The RANGE is deliberately not checked here.** A frame-shape validator does
    not know which target the number is for, and a slider's domain is authored —
    ``[65%]`` runs to 100, ``[3/10]`` to 10. So the bound lives in
    :meth:`MessageLog.verify`, which holds the target, and this layer only says
    the value is a number at all.
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _check_settled(f: dict) -> None:
    """``vs``: the other targets this event commits, as ``[ordinal, value]``.

    Shape only — whether a target exists and carries what is claimed is the
    server's, in :meth:`MessageLog.verify`. A bool is that target's ``c`` and a
    number its ``v``; the fired ``x`` may not name itself, and no ordinal twice.
    """
    rows = f.get("vs")
    if rows is None:
        return
    _need(f, "vs", isinstance(rows, list) and len(rows) <= MAX_SETTLED)
    seen = {f["x"]}
    for row in rows:
        ok = isinstance(row, list) and len(row) == 2 and _is_nat(row[0])
        _need(f, "vs", ok and (isinstance(row[1], bool) or _is_value(row[1])))
        _need(f, "vs", row[0] not in seen)
        seen.add(row[0])


def _check_event(f: dict) -> None:
    _id(f, "m")
    _need(f, "x", _is_nat(f.get("x")))
    _need(f, "q", _is_nat(f.get("q")))
    slug = f.get("a")
    _need(f, "a", "a" not in f or (isinstance(slug, str) and 0 < len(slug) <= MAX_SLUG))
    _need(f, "c", "c" not in f or isinstance(f.get("c"), bool))
    _need(f, "v", "v" not in f or _is_value(f.get("v")))
    _check_settled(f)


def _check_state(f: dict) -> None:
    _need(f, "s", f.get("s") in STATES)
    for key, cap in (("n", MAX_NOTE), ("ph", MAX_PLACEHOLDER)):
        words = f.get(key)
        _need(f, key, key not in f or (isinstance(words, str) and len(words) <= cap))
    answered = f.get("u")
    _need(
        f,
        "u",
        "u" not in f
        or (
            isinstance(answered, list)
            and 0 < len(answered) <= MAX_ANSWERED
            and all(_is_nat(q) for q in answered)
        ),
    )


def _check_prompt(f: dict) -> None:
    _need(f, "q", _is_nat(f.get("q")))
    text = f.get("tx")
    _need(f, "tx", isinstance(text, str) and bool(text.strip()))
    assert isinstance(text, str)
    if len(text.encode()) > MAX_PROMPT_BYTES:
        raise FrameError("too_large", "tx")


_SERVER_FRAMES = {
    "m": _check_message,
    "d": _check_delta,
    "z": _check_end,
    "x": _check_error,
    "s": _check_state,
}


def _check_typing(_f: dict) -> None:
    """``k``: the user is typing in the frontend's field. It carries nothing,
    not even the text: what is typed reaches the server only when it is sent."""


_CLIENT_FRAMES = {
    "h": _check_hello,
    "e": _check_event,
    "p": _check_prompt,
    "k": _check_typing,
}


def _decode(
    data: bytes | str,
    checks: dict,
    max_bytes: int,
    cap: Callable[[dict], int] | None = None,
) -> dict:
    raw = data.encode() if isinstance(data, str) else data
    if len(raw) > max_bytes:
        raise FrameError("too_large", f"{len(raw)} bytes")
    try:
        frame = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FrameError("bad_frame", "not JSON") from exc
    if not isinstance(frame, dict) or frame.get("t") not in checks:
        raise FrameError("bad_frame", "unknown frame type")
    if cap is not None and len(raw) > cap(frame):
        raise FrameError("too_large", f"{len(raw)} bytes")
    checks[frame["t"]](frame)
    return frame


def _client_cap(frame: dict) -> int:
    return MAX_CLIENT_FRAME_BYTES if frame["t"] == "p" else MAX_EVENT_BYTES


def decode_client(data: bytes | str) -> dict:
    """A frame from a frontend, checked; raises :class:`FrameError`. A prompt
    frame may be up to ``MAX_CLIENT_FRAME_BYTES``; every other client frame keeps
    the event cap, ``MAX_EVENT_BYTES``, checked before its keys are."""
    return _decode(data, _CLIENT_FRAMES, MAX_CLIENT_FRAME_BYTES, _client_cap)


def decode_server(data: bytes | str) -> dict:
    """A frame from a server, checked; raises :class:`FrameError`."""
    return _decode(data, _SERVER_FRAMES, MAX_SERVER_FRAME_BYTES)
