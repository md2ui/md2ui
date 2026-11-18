"""The wire: frames between an md2ui server and its frontends (ADR-601).

The spec is ``protocol/README.md``; this module is the prototype's codec and
verifier, and ``protocol/examples/`` is the conformance set it is tested against.

A server sends plain Markdown — a message, or deltas then an end — and receives
events that NAME a target of a message it sent, ``(m, x)``, never restate it. The
server resolves the target against its own copy (:class:`MessageLog`), so an event
cannot ask for an action the message did not offer; and the agent is handed a
sentence built from its own Markdown (:meth:`Verified.agent_text`), never a string
from the client. The one exception is a :class:`Prompt`: what the user typed into
the frontend's own field, handed over as the user's words (ADR-601). The server
also tells its frontends what the agent is doing, with a state frame.

It needs grouping only: no theme, fonts, layout or width, so a server that knows
the content and not the look can verify. A shell module, beside ``session``: the
pipeline never imports it.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Callable, Collection
from dataclasses import dataclass

from md2ui import session
from md2ui.pipeline.render_actions import (
    Action,
    Target,
    action_targets,
    commit_carries,
)
from md2ui.pipeline.render_choices import choice_name
from md2ui.wire_bars import set_bar_markdown
from md2ui.wire_edits import (
    MARK_STATES,
    _in_domain,
    choose_markdown,
    mark_markdown,
    set_slider_markdown,
)
from md2ui.wire_records import Pages
from md2ui.wire_frames import (
    FORWARDED_KINDS,
    MAX_CLIENT_FRAME_BYTES,
    MAX_EVENT_BYTES,
    MAX_NOTE,
    MAX_PROMPT_BYTES,
    MAX_SERVER_FRAME_BYTES,
    MAX_SETTLED,
    MAX_SLUG,
    STATES,
    VERSION,
    FrameError,
    _check_message,
    check_server_size,
    decode_client,
    decode_server,
    encode,
    escaped_bytes,
    md_hash,
)

# Re-exported: this module is the wire's public face, and every caller imports
# the codec through it (protocol/README.md is the contract, not the file split).
__all__ = [
    "FORWARDED_KINDS",
    "MAX_CLIENT_FRAME_BYTES",
    "MAX_EVENT_BYTES",
    "MAX_NOTE",
    "MAX_PROMPT_BYTES",
    "MAX_SERVER_FRAME_BYTES",
    "MAX_SETTLED",
    "MAX_SLUG",
    "MARK_STATES",
    "STATES",
    "VERSION",
    "FrameError",
    "MessageLog",
    "Prompt",
    "Recorded",
    "Rejected",
    "Verified",
    "check_server_size",
    "decode_client",
    "decode_server",
    "encode",
    "escaped_bytes",
    "mark_markdown",
    "md_hash",
    "set_bar_markdown",
    "set_slider_markdown",
]


# --- verification: the server's own copy decides --------------------------------
def _as_authored(action: Action, value: float | bool) -> bool:
    """Does *value* say what the document already says for this target?

    A task box's ``checked`` is the state a click ASKS FOR, the opposite of the
    box as written, so a box is as authored when *value* is not that.
    """
    if isinstance(value, bool):
        return action.checked is not None and value != action.checked
    return action.value is not None and float(value) == action.value


# What may break a sentence the agent reads: a line break or other control
# character, a quote, or what delimits the parameters.
_UNSAFE = re.compile(r'[\x00-\x1f\x7f\u2028\u2029"\\{},]')


def _quoted(text: str) -> str:
    """*text* in quotes, escaped: a label is the page's words, and may say
    anything, but it can never close its quotes or start a line of its own."""
    quoted = json.dumps(text, ensure_ascii=False)  # leaves U+2028/9 raw
    return quoted.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _word(text: str) -> str:
    """*text* as it stands when it cannot break the sentence, else quoted."""
    return _quoted(text) if not text or _UNSAFE.search(text) else text


def _params(a: Action) -> str:
    return " {" + ", ".join(f"{_word(k)}: {_word(v)}" for k, v in a.params) + "}"


def _settled_phrase(a: Action) -> str:
    """One committed target, in the server's own words."""
    if name := choice_name(a):
        return f"{_word(name)}: {_quoted(a.label)}"
    if a.checked is not None:
        return f"{_quoted(a.label)} {'ticked' if a.checked else 'unticked'}"
    return f"{_quoted(a.label)} at {a.value:g}{a.value_unit}"


@dataclass(frozen=True, slots=True)
class Verified:
    """An event resolved against the message it names: the action is the server's."""

    message_id: str
    ordinal: int
    action: Action
    seq: int
    # The other targets this event commits (``vs``), each as its ordinal and the
    # server's own action with the client's number or boolean put in.
    settled: tuple[tuple[int, Action], ...] = ()
    peer: str = ""  # the connection it came on, whose numbering ``seq`` is

    def agent_text(self, with_message: bool = True) -> str:
        """The sentence the agent is handed. Every word but ``checked`` comes from
        the server's copy of its own Markdown; nothing the client sent is quoted.
        That Markdown may carry untrusted words, so a label is always escaped in
        its quotes and a slug or parameter is quoted when it could break the line.

        ``with_message`` False drops the trailing message id, for a caller that
        reports several events at once and says it once for the batch.
        """
        a = self.action
        if a.kind == "checkbox":
            state = "ticked" if a.checked else "unticked"
            text = f"User {state} {_quoted(a.label)} (task {a.index})"
        elif a.value is not None:
            text = f"User set {_quoted(a.label)} to {a.value:g}{a.value_unit}"
            if a.action:
                text += f": {_word(a.action)}"
                if a.params:
                    text += _params(a)
        else:
            text = f"User chose {_quoted(a.label)}: {_word(a.action or '')}"
            if a.params:
                text += _params(a)
            if a.checked is not None and choice_name(a) is None:
                text += " (ticked)" if a.checked else " (unticked)"
        if self.settled:
            text += ", with " + ", ".join(_settled_phrase(s) for _x, s in self.settled)
        elif a.commit:
            text += ", with no change"
        return f"{text} (message {self.message_id})" if with_message else text


@dataclass(frozen=True, slots=True)
class Recorded:
    """Accepted and remembered, deliberately not delivered.

    The third outcome, and neither of the other two: the event was verified
    against the server's copy exactly as a :class:`Verified` one is, and its value
    is in the log — but a ``?md2ui.commit=1`` press in the same message will
    report this target, so waking the agent for it would cost a turn the press
    already pays for.

    **The client reports; the server decides what to deliver.** A frontend cannot
    tell which of its events the agent needs, any more than it can tell a press
    that means *keep this* from one that means *discard it* — so it sends
    everything and this decides. That also keeps :meth:`MessageLog.requested`
    honest: the server knows what the user has done to a commit form, so a read of
    it is not blind in the one case an agent would ask about.
    """

    message_id: str
    ordinal: int


@dataclass(frozen=True, slots=True)
class Rejected:
    """An event refused; :meth:`frame` is the ``x`` frame to answer with."""

    code: str
    message_id: str | None = None
    seq: int | None = None

    def frame(self) -> dict:
        out: dict = {"t": "x", "code": self.code}
        if self.message_id is not None:
            out["m"] = self.message_id
        if self.seq is not None:
            out["q"] = self.seq
        return out


@dataclass(frozen=True, slots=True)
class Prompt:
    """What the user typed into the frontend's own field (ADR-601). Unlike a
    click, it is the user's own words: it reaches the agent verbatim, labelled as
    theirs, and never inside a sentence built from the agent's Markdown."""

    text: str
    seq: int
    # Stamped by the server on receipt, since a prompt that waited in a queue is
    # otherwise indistinguishable from one typed a moment ago: the message the
    # window showed, and when (monotonic seconds).
    on: str | None = None
    at: float = 0.0


@dataclass
class _Record:
    markdown: str
    digest: str
    targets: list[Target]
    superseded: bool = False
    # What replaced it, and whether the server made this record unasked -- a feed's
    # tick (ADR-608) or a commit press written in: an id the agent carries
    # resolves through edits it did not make.
    replaced_by: str | None = None
    by_server: bool = False


class MessageLog:
    """The server's copy of what it sent on one connection, and the verifier.

    ``record`` groups a message once — its targets are the index every event is
    checked against in O(1) — so the pipeline never runs per event.
    """

    def __init__(self, kit: session.GroupingKit | None = None) -> None:
        self._kit = kit
        self._messages: dict[str, _Record] = {}
        self.pages = Pages()  # what the agent would otherwise remember of them
        self._seen: set[tuple[str, int]] = set()
        self._fired: set[tuple[str, int]] = set()
        # The value each target last REPORTED, keyed like `_fired`. A settle equal
        # to it is not a decision -- picking a control up and putting it down
        # where it already was fires a full event, and a batch can carry the
        # same number three times. The document's own value is the
        # wrong baseline after the first change, so what is tracked is what was
        # last said, seeded from the authored value when nothing has been.
        # `mark` and `set_slider` mint a NEW message id, so a value the agent
        # sets arrives as a fresh target whose authored value is the new seed.
        # Booleans are recorded here too, and NEVER consulted for dedupe. Not to
        # avoid a collision -- each event writes this, so tick/untick/re-tick is
        # three changes -- but because a checkbox has no no-op to suppress: a
        # slider release can repeat meaninglessly, while every tick is a
        # deliberate request for a state. Dedupe buys nothing there and can only
        # cost, and `mark` is where it would: writing a mark's state here would
        # swallow a user who then asks for it themselves, while not writing it
        # would report state the agent has already overwritten. Recording without
        # suppressing means the question never needs an answer. For NUMBERS the
        # answer is the opposite, so the rule divides on the same line as the
        # noise: written by everything, consulted only for values.
        self._last: dict[tuple[str, int], float | bool] = {}

    def record(
        self,
        message_id: str,
        markdown: str,
        replaces: str | None = None,
        by_server: bool = False,
        continues: str | None = None,
        renewed: Collection[str] = (),
    ) -> list[dict]:
        """Store a complete message and return the frames that send it whole:
        the message, then its end. A replaced message is stale from now on; one
        whose frame a client would refuse is refused here, before anything.
        *continues* is a message this one re-sends: the same page, sent again;
        *renewed* names the sections whose data it gives anew (``wire_patch``)."""
        frame: dict = {"t": "m", "m": message_id, "md": markdown}
        if replaces is not None:
            frame["r"] = replaces
        _check_message(frame)
        check_server_size(frame)
        ast = session.group_shared(markdown, self.kit())
        tree = ast.to_dict() if ast is not None else {}
        targets = action_targets(tree) if tree else []
        digest = md_hash(markdown)
        self._messages[message_id] = _Record(
            markdown, digest, targets, by_server=by_server
        )
        carries = replaces or continues
        self.pages.sent(
            message_id, markdown, carries, renewed, (tree, targets), by_server
        )
        if replaces is not None and replaces in self._messages:
            self._messages[replaces].superseded = True
            self._messages[replaces].replaced_by = message_id
        return [frame, {"t": "z", "m": message_id, "h": digest}]

    def kit(self) -> session.GroupingKit:
        if self._kit is None:
            self._kit = session.load_grouping_kit()
        return self._kit

    def markdown(self, message_id: str) -> str:
        """The server's own copy of what it sent, so a reader need not invent it."""
        record = self._messages.get(message_id)
        return record.markdown if record is not None else ""

    def head(self, message_id: str, through_server_only: bool = False) -> str:
        """The message that replaced *message_id* last: through every replacement,
        or only through those the server made unasked (a feed's tick, ADR-608)."""
        record = self._messages.get(message_id)
        while record is not None and record.replaced_by is not None:
            nxt = self._messages[record.replaced_by]
            if through_server_only and not nxt.by_server:
                break
            message_id, record = record.replaced_by, nxt
        return message_id

    def targets(self, message_id: str) -> list[Target]:
        record = self._messages.get(message_id)
        return list(record.targets) if record is not None else []

    def _edit(
        self,
        message_id: str,
        new_id: str,
        edit: Callable[[str, session.GroupingKit], str],
        by_server: bool = False,
    ) -> list[dict]:
        """Apply *edit* to the server's copy of *message_id* and return the frames
        of the replacement (ADR-601). The agent regenerates nothing, and an id it
        carries still names its page after the server edited it unasked (ADR-608)."""
        message_id = self.head(message_id, through_server_only=True)
        record = self._messages.get(message_id)
        if record is None:
            raise FrameError("unknown_message", message_id)
        if record.superseded:
            raise FrameError("stale", message_id)
        edited = edit(record.markdown, self.kit())
        if not by_server:  # the agent's: never inside an include (ADR-612)
            self.pages.includes.refuse(message_id, record.markdown, edited)
        return self.record(new_id, edited, replaces=message_id, by_server=by_server)

    def mark(self, message_id: str, x: int, state: str, new_id: str) -> list[dict]:
        """Tick, untick or disable target *x* as the agent decided."""
        return self._edit(
            message_id, new_id, lambda md, kit: mark_markdown(md, x, state, kit)
        )

    def set_slider(
        self, message_id: str, x: int, value: float, new_id: str
    ) -> list[dict]:
        """Apply one slider value and return its replacement message frames."""
        return self._edit(
            message_id, new_id, lambda md, kit: set_slider_markdown(md, x, value, kit)
        )

    def set_bar(
        self, message_id: str, key: str, value: float, new_id: str
    ) -> list[dict]:
        """Move the static bar written under *key* (:func:`set_bar_markdown`)."""
        return self._edit(
            message_id, new_id, lambda md, kit: set_bar_markdown(md, key, value, kit)
        )

    def set_bars(
        self,
        message_id: str,
        edit: Callable[[str, session.GroupingKit], str],
        new_id: str,
    ) -> list[dict]:
        """A feed's tick: *edit* writes its bars and slots, one replacement."""
        return self._edit(message_id, new_id, edit, by_server=True)

    def commit(self, press: Verified, new_id: str) -> list[dict]:
        """What *press* committed, written into the server's copy of its page as
        ``mark`` and ``set_slider`` would write it.

        The window already shows these values, and once the press is answered it
        shows what the page's Markdown says, so a copy still holding the values
        as sent would undo the user's commit at the agent's next ``patch``. The
        agent did not ask for this edit, so an id it carries resolves through it,
        as through a feed's tick; it may still change any of them afterwards.
        """

        def edit(md: str, kit: session.GroupingKit) -> str:
            for x, a in press.settled:
                if choice_name(a):
                    md = choose_markdown(md, x, kit)
                elif a.checked is not None:
                    md = mark_markdown(
                        md, x, "checked" if a.checked else "unchecked", kit
                    )
                elif a.value is not None:
                    md = set_slider_markdown(md, x, a.value, kit)
            return md

        return self._edit(press.message_id, new_id, edit, by_server=True)

    def _settle(self, message_id: str, record: _Record, rows: list) -> tuple | str:
        """The targets an event commits alongside the one it fired.

        Resolved by exactly the rules ``v`` and ``c`` already use, against the
        server's own copy: a string back is the refusal code. The client
        contributes only the number or the boolean — every label, slug and param
        still comes from the Markdown the server sent, so committing many targets
        gives the client no more say than committing one.

        The press reports the NET change: a target the client sends at what the
        document authored is left out, so a box ticked and unticked again is not
        reported as a decision. The client sends what each touched control shows;
        which of those differ from the page as sent is the server's to say.
        """
        out: list[tuple[int, Action]] = []
        chosen: set[str] = set()  # the groups a choice was sent for
        for index, value in rows:
            if index >= len(record.targets):
                return "bad_target"
            action = record.targets[index].action
            if action is None or action.kind not in FORWARDED_KINDS:
                return "bad_target"
            if isinstance(value, bool):
                name = choice_name(action)
                # A choice travels as its chosen option, one per group.
                if action.checked is None or name in chosen or (name and not value):
                    return "bad_value"
                if name:
                    chosen.add(name)
                changed = dataclasses.replace(action, checked=value)
            else:
                if action.value is None or not _in_domain(action, value):
                    return "bad_value"
                changed = dataclasses.replace(action, value=float(value))
            if not _as_authored(action, value):
                out.append((index, changed))
        return tuple(out)

    def _forget_others(self, message_id: str, record: _Record, x: int) -> None:
        """A choice is one of its group: choosing *x* drops what was asked of the
        other options, so :meth:`requested` names the group's choice once."""
        name = choice_name(record.targets[x].action)
        for i, target in enumerate(record.targets):
            if name and i != x and choice_name(target.action) == name:
                self._last.pop((message_id, i), None)

    def requested(self, message_id: str) -> dict[int, float | bool]:
        """What the user has ASKED FOR since *message_id* was sent, by ordinal.

        Requests, not accepted state: the agent decides (ADR-404), and until it
        answers, the document still says what it said. It is populated by
        :meth:`verify` itself, so it reports what the server verified rather than
        a parallel record — it cannot disagree with what the agent was told, which
        is the reason to keep one structure rather than two. A request for what the
        document already says is none, as a commit press reports it (:meth:`_settle`).
        """
        record = self._messages.get(message_id)
        out: dict[int, float | bool] = {}
        for (mid, x), value in self._last.items():
            if mid != message_id or record is None:
                continue
            action = record.targets[x].action
            if action is not None and not _as_authored(action, value):
                out[x] = value
        return out

    def verify(self, event: dict, peer: str = "") -> Verified | Recorded | Rejected:
        """Resolve a decoded event frame against the message it names.

        *peer* names the connection the event came on: ``q`` counts per
        connection (protocol/README.md), so a repeat is a repeat only there.
        """
        mid, x, q = event["m"], event["x"], event["q"]
        if (peer, q) in self._seen:
            return Rejected("duplicate", mid, q)
        self._seen.add((peer, q))
        record = self._messages.get(mid)
        if record is None:
            return Rejected("unknown_message", mid, q)
        if record.superseded:
            return Rejected("stale", mid, q)
        if x >= len(record.targets) or record.targets[x].action is None:
            return Rejected("bad_target", mid, q)
        action = record.targets[x].action
        assert action is not None
        if action.kind not in FORWARDED_KINDS:
            return Rejected("not_forwarded", mid, q)
        if "a" in event and event["a"] != action.action:
            return Rejected("slug_mismatch", mid, q)
        if "c" in event and action.checked is None:
            return Rejected("bad_target", mid, q)
        if choice_name(action) and not event.get("c", True):
            return Rejected("bad_value", mid, q)  # an option is chosen, never cleared
        carries_value = action.value is not None
        if carries_value != ("v" in event):
            return Rejected("bad_value", mid, q)
        if "v" in event:
            if not _in_domain(action, event["v"]):
                return Rejected("bad_value", mid, q)
            value = float(event["v"])
            if self._last.get((mid, x), action.value) == value:
                return Rejected("duplicate", mid, q)
            action = dataclasses.replace(action, value=value)
        fires = (
            action.kind == "agent" and action.checked is None and action.value is None
        )
        if fires and (mid, x) in self._fired:
            return Rejected("duplicate", mid, q)
        settled: tuple = ()
        if "vs" in event:
            resolved = self._settle(mid, record, event["vs"])
            if isinstance(resolved, str):
                return Rejected(resolved, mid, q)
            settled = resolved
        # Every check has passed. Only now is anything recorded: a refused event
        # is not in the log (protocol/README.md), so it must not spend its button.
        if "v" in event:
            self._last[(mid, x)] = float(event["v"])
        if fires:
            self._fired.add((mid, x))
        if action.checked is not None and "c" in event:
            action = dataclasses.replace(action, checked=event["c"])
            self._last[(mid, x)] = event["c"]
            self._forget_others(mid, record, x)
        for index, row_value in event.get("vs", ()):
            if not isinstance(row_value, bool):
                self._last[(mid, index)] = float(row_value)
        if commit_carries(action, record.targets):
            return Recorded(mid, x)
        return Verified(mid, x, action, q, settled, peer)

    def verify_prompt(self, frame: dict, peer: str = "") -> Prompt | Rejected:
        """Accept a decoded prompt frame once per ``q`` on its connection. There
        is nothing to resolve against a message: the text is the user's."""
        q = frame["q"]
        if (peer, q) in self._seen:
            return Rejected("duplicate", None, q)
        self._seen.add((peer, q))
        return Prompt(frame["tx"].strip(), q)
