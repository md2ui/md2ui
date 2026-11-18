"""Advice for a form: the values a page holds, and the one press that carries them.

A click on an ``agent:`` button costs a turn, so a form is one turn: its values
wait in the window and one press marked ``md2ui.commit=1`` carries them
(``skills/README.md``, *A form is one turn*; ADR-405). Agents write the form a
click at a time unless something tells them as they write it. Two shapes, read
from the grouped tree and the targets it offers (``render_actions.action_targets``),
never from the source text:

* **a stepper of buttons**, ``[➖](agent:…) 2 [➕](agent:…)``: a turn per tap, where
  a count, ``Quantity: ➖ [2/9] ➕``, holds the number until the press;
* **values and no commit press**: a count or a choice (and the sliders and task
  boxes beside it) with an ``agent:`` button on the page. A checklist's boxes or a
  dashboard's slider alone are not a form: each reports as its own action, so
  they are never advised by themselves (measured on past answers: shopping lists,
  a walk's stops, a storm's preparations).

Both point to one section, and ``advice`` sends a section once per session, so a
page gets one line: each fix that applies, in this order.

A third shape, options written without ``md2ui.choice`` beside a commit press, is
not advised (ADR-502): it never fired in the evals, so its help was never measured.

What an include drew is the backend's (ADR-612): a click there is answered by a
handler with no turn, and the agent cannot edit it. A shape whose targets all sit
in the lines an include drew (*drawn*) is skipped; one the agent typed is not.
So is a stepper whose ``agent:`` slugs a registered handler answers (*handled*,
the server's ``Conversation.handlers``): its taps change the backend's data with
no turn, so a count would only slow them. A server with no handlers, and
``check``, pass none, and nothing changes.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator
from dataclasses import dataclass
from typing import TypeGuard

from md2ui.pipeline.render_actions import Action, Target, action_targets
from md2ui.pipeline.render_choices import choice_name

_MINUS = frozenset("➖ − - –".split())
_PLUS = frozenset("➕ +".split())
# The most a written count can reach, in the hint's example.
_MOST = 9


@dataclass(frozen=True)
class _Stepper:
    """A minus and a plus button around a number: what was written, the number
    shown, and the two targets' keys."""

    written: str
    now: int
    keys: tuple[str, str]


def form_hints(
    tree: dict, drawn: Collection[str] = (), handled: Collection[str] = ()
) -> Iterator[str]:
    """One message when the page writes a form a turn at a time, with each fix
    that applies; nothing otherwise."""
    targets = action_targets(tree)
    nodes = _nodes(tree)
    mine = [
        t
        for t in targets
        if t.action is not None
        and not _drawn(
            str(nodes.get(t.key.split("#")[0], {}).get("content", "")), drawn
        )
    ]
    commits = [t for t in targets if _agent(t.action) and t.action.commit]
    steppers = [s for s in _steppers(tree, targets) if _owned(s.keys, mine)]
    stepped = {k for s in steppers for k in s.keys}
    steppers = [s for s in steppers if not _answered(s.keys, targets, handled)]
    parts: list[str] = []
    if steppers:
        first = steppers[0]
        lead = (
            f"These {len(steppers)} steppers, `{first.written}` first, are buttons"
            if len(steppers) > 1
            else f"`{first.written}` is a stepper of buttons"
        )
        parts.append(
            f"{lead}: each tap is a turn. Write the number as a count, "
            f"`Quantity: ➖ [{first.now}/{_MOST}] ➕` ({first.now} now, {_MOST} the "
            f"most), which the press marked `md2ui.commit=1` carries."
        )
    if not commits:
        held = _held(mine)
        press = _press(tree, mine, stepped)
        if (held or steppers) and any(_agent(t.action) for t in mine):
            what = f"{held} and the count" if held and steppers else held or "The count"
            parts.append(
                f"{what} would wait for a press, and no button carries "
                f"{'it' if what == 'The count' else 'them'}. A form is one turn: mark "
                f"the button that means keep, {_keep(press)}; a discard stays unmarked."
            )
    if parts:
        yield " ".join(parts)


def _agent(action: Action | None) -> TypeGuard[Action]:
    return action is not None and action.kind == "agent"


def _nodes(tree: dict) -> dict[str, dict]:
    found: dict[str, dict] = {}
    stack = [tree]
    while stack:
        node = stack.pop()
        found[str(node.get("node_id", ""))] = node
        stack.extend(node.get("children", []))
    return found


def _drawn(content: str, drawn: Collection[str]) -> bool:
    """Whether *content* sits in a line an include drew."""
    content = content.strip()
    return bool(content) and any(content in line for line in drawn)


def _owned(keys: tuple[str, ...], mine: list[Target]) -> bool:
    """Whether any of *keys* is a target the agent wrote: a disabled half of a
    stepper reports nothing, so one live half is enough."""
    return any(t.key in keys for t in mine)


def _answered(
    keys: tuple[str, ...], targets: list[Target], handled: Collection[str]
) -> bool:
    """Whether a handler answers every ``agent:`` half of a stepper: a half it
    does not answer is still a turn per tap."""
    slugs = [t.action.action for t in targets if t.key in keys and _agent(t.action)]
    return bool(slugs) and all(slug in handled for slug in slugs)


def _label(node: dict) -> str:
    return str(node.get("link_label") or "").replace("️", "").strip()


def _steppers(tree: dict, targets: list[Target]) -> Iterator[_Stepper]:
    """Each minus button followed by a plus button, at most one thing between:
    a row's buttons around a number or a slider, or two links in one text."""
    actions = {t.key: t.action for t in targets}
    for node in _nodes_in_order(tree):
        kids = node.get("children", [])
        for i, minus in enumerate(kids):
            if minus.get("type") != "link" or _label(minus) not in _MINUS:
                continue
            for j in (i + 1, i + 2):
                plus = kids[j] if j < len(kids) else {}
                if plus.get("type") == "link" and _label(plus) in _PLUS:
                    pair = (str(minus.get("node_id")), str(plus.get("node_id")))
                    if any(_agent(actions.get(k)) for k in pair):
                        between = kids[i + 1] if j == i + 2 else {}
                        yield _Stepper(
                            _written(actions, pair, _now(between)), _now(between), pair
                        )
                    break
                if plus.get("type") == "link":
                    break
    inline = [t for t in targets if "#" in t.key]
    for a, b in zip(inline, inline[1:]):
        same = a.key.split("#")[0] == b.key.split("#")[0]
        if (
            same
            and _agent(a.action)
            and _agent(b.action)
            and a.action.label.replace("️", "").strip() in _MINUS
            and b.action.label.replace("️", "").strip() in _PLUS
        ):
            yield _Stepper(_written(actions, (a.key, b.key), 1), 1, (a.key, b.key))


def _now(between: dict) -> int:
    """The number a stepper shows: its middle text's digits, or a slider's value."""
    payload = between.get("drawing_element") or {}
    if payload.get("kind") == "slider":
        return int(payload.get("value") or 0)
    digits = "".join(c for c in str(between.get("content", "")) if c.isdigit())
    return int(digits) if digits and len(digits) <= 3 else 1


def _written(actions: dict, pair: tuple[str, str], now: int) -> str:
    """A stepper as it reads: its signs and their actions, the number between."""
    signs = []
    for key, sign in zip(pair, "➖➕"):
        a = actions.get(key)
        signs.append(f"[{sign}](agent:{a.action})" if _agent(a) else sign)
    return f"{signs[0]} {now} {signs[1]}"


def _sections(tree: dict) -> dict[str, tuple[str, ...]]:
    """Each node's sections, outermost first: the ``heading_group``s it is in."""
    out: dict[str, tuple[str, ...]] = {}

    def walk(node: dict, chain: tuple[str, ...]) -> None:
        if node.get("heading_group"):
            chain = (*chain, str(node.get("node_id")))
        out[str(node.get("node_id", ""))] = chain
        for kid in node.get("children", []):
            walk(kid, chain)

    walk(tree, ("",))
    return out


def _nodes_in_order(node: dict) -> Iterator[dict]:
    yield node
    for kid in node.get("children", []):
        yield from _nodes_in_order(kid)


def _held(mine: list[Target]) -> str:
    """The values a page holds, named: its counts and choices, then the number
    of sliders and task boxes beside them; nothing without a count or choice."""
    counts = [f"`{t.action.label}`" for t in mine if t.action and t.action.count]
    choices = sorted(
        {f"the `{n}` choice" for t in mine if (n := choice_name(t.action)) is not None}
    )
    sliders = [t for t in mine if t.action and t.action.kind == "slider"]
    boxes = [t for t in mine if t.action and t.action.kind == "checkbox"]
    others = len(sliders) - len(counts) + len(boxes)
    if not counts and not choices:
        return ""
    named = counts + choices
    if others:
        other = "other " if named else ""
        named.append(f"{others} {other}value{'s' if others > 1 else ''}")
    text = ", ".join(named[:-1]) + (" and " if len(named) > 1 else "") + named[-1]
    return text[0].upper() + text[1:] if text.startswith("the") else text


def _press(tree: dict, mine: list[Target], stepped: set[str]) -> Action | None:
    """The ``agent:`` button that could carry the page's values: the first after
    the last value, neither an option nor a stepper's sign, in that value's
    section or one around it (a row's own link to its item comes before). None when there is none: a tab elsewhere on the
    page is no press."""
    values = [
        i
        for i, t in enumerate(mine)
        if t.key in stepped
        or choice_name(t.action) is not None
        or (t.action and t.action.kind in ("slider", "checkbox"))
    ]
    if not values:
        return None
    sections = _sections(tree)
    around = sections.get(mine[values[-1]].key.split("#")[0], ("",))
    for t in mine[values[-1] + 1 :]:
        if (
            _agent(t.action)
            and choice_name(t.action) is None
            and t.key not in stepped
            and sections.get(t.key.split("#")[0], ("",))[-1] in around
        ):
            return t.action
    return None


def _keep(press: Action | None) -> str:
    """The keep press as it should be written: the page's own, or an example."""
    if press is None:
        return "`[Add to bag](agent:add?item=7&md2ui.commit=1)`"
    return f"`[{press.label}]({_spelled(press, 'md2ui.commit=1')})`"


def _spelled(action: Action, hint: str) -> str:
    """*action*'s destination with *hint* added: ``agent:add?id=7&md2ui.commit=1``."""
    query = "&".join(f"{k}={v}" for k, v in action.params)
    return f"agent:{action.action}?" + "&".join(q for q in (query, hint) if q)
