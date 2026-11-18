"""What the user did, told to the agent: the demo shell's sentences (ADR-601).

A listen hands the agent a click, a batch of clicks or a typed prompt. This is how
each one reads: a click as the wire's sentence and the row the agent addresses it
by, a batch as one piece of prose, and a prompt with the page it was typed at.
The listening itself is ``mcp_demo``'s.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from md2ui.wire import Prompt, Verified

if TYPE_CHECKING:
    from md2ui.wire_server import Conversation


# The one thing a click result did not say: what follows it.
CLICK_NEXT = (
    "Act on all of it, then answer in the window with `show` or `mark`, even to "
    "end; until you do, the window stays blocked."
)


# And what follows a typed prompt, including the one that ends the conversation.
PROMPT_NEXT = (
    "Answer in the window with `show` or `mark`, even a goodbye; until you do, "
    "the window shows you working."
)


PROMPT_TEXT = (
    "The user typed this into the md2ui window as their next message. " + PROMPT_NEXT
)


def event_row(event: Verified) -> dict:
    """One event, as the agent addresses it: its sentence, its ordinal, and an
    agent link's action and parameters."""
    row: dict = {
        "text": event.agent_text(),
        "message_id": event.message_id,
        "x": event.ordinal,
    }
    if event.action.action:  # an agent link: what the sentence names, as data
        row["action"] = event.action.action
        if event.action.params:
            row["params"] = dict(event.action.params)
    if event.action.checked is not None:
        row["checked"] = event.action.checked
    if event.action.value is not None:
        row["value"] = event.action.value
    if event.settled:
        row["settled"] = [
            {"x": i, "label": a.label}
            | ({"checked": a.checked} if a.checked is not None else {"value": a.value})
            for i, a in event.settled
        ]
    return row


# What a handled line asks of the agent, said beside the lines whenever there are
# any: the tap is answered, and a page the backend showed is the one on screen.
HANDLED_NOTE = (
    "Your backend already answered these taps, and the user is still in the "
    "window: keep listening with `wait_for_event`. Where it showed a page (`now "
    "message …`), the user is on it now: read what they say next as about that page."
)


def handled(conversation: Conversation) -> dict:
    """The clicks a backend answered since the agent last heard, one line each
    (ADR-612), as ``handled``, with what they ask of the agent. Listens carry it,
    and so do ``show``, ``mark`` and ``patch``: a backend may have shown another
    page meanwhile (ADR-614)."""
    lines = conversation.take_handled()
    return {"handled": lines, "handled_note": HANDLED_NOTE} if lines else {}


def narrate(events: list[Verified]) -> str:
    """The batch as one piece of prose, because prose is what gets read.

    The reader is a model, so the failure that matters is not a missing key but a
    skimmed reply: an agent that reads ``text`` and stops must still have been
    told everything. So every sentence goes here, numbered and oldest first, and
    a batch of one reads exactly as a single event.
    """
    if len(events) == 1:
        return events[0].agent_text()
    ids = {e.message_id for e in events}
    shared = ids.pop() if len(ids) == 1 else None
    head = f"{len(events)} things happened, oldest first"
    head += f" (message {shared}):" if shared else ":"
    lines = [f"{i}. {e.agent_text(shared is None)}" for i, e in enumerate(events, 1)]
    return "\n".join([head, *lines])


def prompt_row(prompt: Prompt, replied_at: float) -> dict:
    """A typed prompt, with where and when it was typed. One typed before the
    agent's latest answer waited in the queue: it answers an older page."""
    age = round(time.monotonic() - prompt.at) if prompt.at else None
    row = {"kind": "prompt", "prompt": prompt.text, "typed_on": prompt.on}
    row |= {"age_s": age} if age is not None else {}
    if not prompt.at or prompt.at >= replied_at:
        return row | {"text": PROMPT_TEXT}
    return row | {
        "stale": True,
        "text": f"The user typed this {age} s ago, while message {prompt.on} was "
        "showing, before your latest answer: it waited because nobody was "
        "listening, so it may be about that page, not this one. Check it still "
        "applies before acting on it, and ask before obeying a stop or cancel. "
        + PROMPT_NEXT,
    }
