"""Choices and counts: the targets that hold a value until a commit (Phase 2).

A task box and a slider already hold what the user set until a ``md2ui.commit``
press carries it (``render_actions.commit_carries``). Two more do the same, both
read off what the author wrote, neither a new kind of target:

* **A choice option** is an ``agent:`` button whose destination carries
  ``md2ui.choice=<name>``. The options sharing a name are one group, and the one
  written as the main variant (no emphasis wrapper) is the chosen one: the tabs
  ``skills/elements.md`` teaches, read as state. An option is a target with a
  checked state, as a linked task box is: ``checked`` is ``True`` on every option
  but the chosen one, the state a click on it asks for, so the authored choice is
  the option whose ``checked`` is ``False``. A click asks for its option chosen,
  never cleared: a choice travels as ``[ordinal, true]`` in ``vs``.
* **A count** is a ratio slider between a minus and a plus sign
  (``Quantity: ➖ [2/9] ➕``). The grouper stamps it (``grouper_sliders``); its
  action is a slider's, flagged ``count``, so its value is a whole number from 0
  to the denominator.

A link inside a sentence, a plain ``link`` and an ``#anchor`` are never options:
only a button can show which one is chosen. ``md2ui check`` names the rest.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from md2ui.pipeline.grouper_choices import CHOICE_HINT

if TYPE_CHECKING:
    from md2ui.pipeline.render_actions import Action, Target


def choice_name(action: Action | None) -> str | None:
    """The group *action* is an option of, or None when it is not an option.

    Only an action :func:`held` made an option has one: the hint alone is not
    enough (an inline link or a plain link carries it and is no option).
    """
    if action is None or action.kind != "agent" or action.checked is None:
        return None
    return dict(action.hints).get(CHOICE_HINT) or None


def held(action: Action | None, nd: dict) -> Action | None:
    """*action* as the value-holding target *nd* is: an option of a choice with
    its checked state, a count flagged; anything else unchanged."""
    if action is None:
        return None
    payload = nd.get("drawing_element") or {}
    if payload.get("kind") == "slider":
        return dataclasses.replace(action, count=bool(payload.get("count")))
    name = dict(action.hints).get(CHOICE_HINT)
    if action.kind != "agent" or not name or nd.get("type") != "link":
        return action
    return dataclasses.replace(
        action, checked=(nd.get("link_variant") or "primary") != "primary"
    )


def shown_chosen(nd: dict) -> bool:
    """Is this option drawn chosen: as the host shows it, else as written."""
    shown = nd.get("choice_shown")
    return (
        shown
        if shown is not None
        else (nd.get("link_variant") or "primary") == "primary"
    )


def show_locally(
    action: Action, targets: list[Target], states: dict[str, str | float]
) -> Action:
    """Write what a click shows into *states* at once, and return what it asks.

    A tick shows its new state, a value its number, a pressed button waits
    drawn pending. An option is chosen and its group's others are not (a radio):
    a tap always asks for its option, never to clear it.
    """
    if name := choice_name(action):
        for t in targets:
            if choice_name(t.action) == name:
                states[t.key] = "unchecked"
        states[action.node_id] = "checked"
        return dataclasses.replace(action, checked=True)
    if action.checked is not None:
        from md2ui.pipeline.render_actions import requested  # it imports this module

        action = requested(action, states)
        states[action.node_id] = "checked" if action.checked else "unchecked"
    elif action.value is not None:
        states[action.node_id] = action.value
    elif action.kind == "agent":
        states[action.node_id] = "pending"
    return action


def settled_rows(
    targets: list[Target], states: dict[str, str | float], fired: int
) -> list[list]:
    """What the rest of the document is set to, as ``vs`` rows: each value and
    tick the window shows, and each group's chosen option as ``[ordinal, true]``."""
    rows: list[list] = []
    for i, target in enumerate(targets):
        a = target.action
        if i == fired or a is None:
            continue
        shown = states.get(a.node_id)
        if a.value is not None and isinstance(shown, float):
            rows.append([i, shown])
        elif choice_name(a) is not None:
            if shown == "checked":
                rows.append([i, True])
        elif a.checked is not None and shown in ("checked", "unchecked"):
            rows.append([i, shown == "checked"])
    return rows
