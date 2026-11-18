"""The state edits the agent decides and the server applies to its own copy.

Each is found, not computed: a candidate token of the Markdown is tried, the result
regrouped, and the first that changes exactly the target asked for is kept, so no
second copy of the grouper's rules lives here. A tick or a disable
(:func:`mark_markdown`), a slider's or a count's value
(:func:`set_slider_markdown`), and a choice (:func:`choose_markdown`). ``wire.MessageLog`` applies them for the agent
and for a commit press; ``wire_bars`` and ``wire_patch`` find their edits the same
way. Split from ``wire.py``, which re-exports the public ones.
"""

from __future__ import annotations

import math
import re

from md2ui import session
from md2ui.pipeline.render_actions import Action, Target, action_targets
from md2ui.pipeline.render_choices import choice_name
from md2ui.pipeline.render_text import LINK_DESTINATION
from md2ui.wire_frames import FrameError


def _in_domain(action: Action, value: float) -> bool:
    """Is *value* inside the range the DOCUMENT gave this target? A count's
    range holds whole numbers only."""
    ceiling = action.value_max if action.value_max is not None else 100.0
    whole = not action.count or float(value).is_integer()
    return 0.0 <= value <= ceiling and whole


MARK_STATES = ("checked", "unchecked", "disabled")
_CONTROL_TOKEN = re.compile(r"\[[ xX]\]")
_SLIDER_TOKEN = re.compile(
    r"\[(?:(?:100(?:\.0+)?|\d{1,2}(?:\.\d+)?)%|\d{1,4}(?:\.\d+)?/\d{1,4})]"
)
# A slider, plain or linked (``[[65%]](agent:…)``): the token ``~~`` disables.
_SLIDER_SPELLING = re.compile(
    rf"\[{_SLIDER_TOKEN.pattern}\]\({LINK_DESTINATION}\)|{_SLIDER_TOKEN.pattern}"
)
# A one-line link, with an emphasis wrapper if it has one (the wrapper is its
# variant, and a disabled button keeps it: `~~*[No](agent:cancel)*~~`). Its
# destination is the grouper's, so the token ends where the link does.
_LINK_TOKEN = re.compile(
    rf"(?<![!~*_])(?:\*{{1,3}}|_{{1,3}})?\[[^\]\n]+\]\({LINK_DESTINATION}\)"
    r"(?:\*{1,3}|_{1,3})?"
)


def _targets(markdown: str, kit: session.GroupingKit) -> list[Target]:
    ast = session.group_shared(markdown, kit)
    return action_targets(ast.to_dict()) if ast is not None else []


def _signature(target: Target) -> tuple | None:
    a = target.action
    if a is None:
        return None
    return (
        a.kind,
        a.action,
        a.href,
        a.params,
        a.checked,
        a.value,
        a.index,
        a.commit,
        a.value_max,
        a.value_unit,
    )


def _only_changed(
    before: list[Target], after: list[Target], x: int, state: str
) -> bool:
    """True when *after* is *before* with target *x*, and nothing else, in *state*."""
    if len(before) != len(after):
        return False
    for i, (b, a) in enumerate(zip(before, after)):
        if i != x and _signature(b) != _signature(a):
            return False
    moved = after[x].action
    if state == "disabled":
        return moved is None
    # A task box's action asks for the OPPOSITE of what the document shows.
    return moved is not None and moved.checked == (state != "checked")


def mark_markdown(markdown: str, x: int, state: str, kit: session.GroupingKit) -> str:
    """*markdown* with target *x* ticked, unticked or disabled, and nothing else.

    The edit is found, not computed. Each candidate token is tried in source order,
    the result regrouped, and the first that changes exactly target *x* is kept. A
    candidate in a code span, an escaped ``\\[ ]`` or the wrong link fails that
    check, so no second copy of the grouper's rules is needed here. A state the
    target already has returns *markdown* unchanged. Raises ``FrameError`` with
    ``bad_target`` for a target that cannot take the state (a link card cannot be
    disabled this way; only a task box ticks). A slider or a count is disabled
    as a link is, its token wrapped in ``~~``. A choice option is ``checked`` by
    choosing it (:func:`choose_markdown`), never ``unchecked``: a group's choice
    changes by choosing another.
    """
    if state not in MARK_STATES:
        raise FrameError("bad_frame", f"state {state!r}")
    before = _targets(markdown, kit)
    if not 0 <= x < len(before):
        raise FrameError("bad_target", f"no target {x}")
    action = before[x].action
    if choice_name(action) is not None and state != "disabled":
        if state == "unchecked":
            raise FrameError("bad_target", "a choice changes by choosing another")
        return choose_markdown(markdown, x, kit)
    if state == "disabled":
        if action is None:
            return markdown
        if action.checked is not None and choice_name(action) is None:
            raise FrameError("bad_target", "a task box is ticked, not disabled")
        spelling = _LINK_TOKEN if action.value is None else _SLIDER_SPELLING
        tokens = list(spelling.finditer(markdown))
        replace = [f"~~{m.group(0)}~~" for m in tokens]
    else:
        if action is None or action.checked is None:
            raise FrameError("bad_target", "only a task box is ticked")
        if action.checked != (state == "checked"):
            return markdown
        tokens = list(_CONTROL_TOKEN.finditer(markdown))
        replace = ["[x]" if state == "checked" else "[ ]"] * len(tokens)
        # The box's own ordinal is the likeliest token: try it first.
        if action.index is not None and action.index < len(tokens):
            first = action.index
            tokens.insert(0, tokens.pop(first))
            replace.insert(0, replace.pop(first))
    for m, new in zip(tokens, replace):
        candidate = markdown[: m.start()] + new + markdown[m.end() :]
        if _only_changed(before, _targets(candidate, kit), x, state):
            return candidate
    raise FrameError("bad_target", f"no source edit changes only target {x}")


def set_slider_markdown(
    markdown: str, x: int, value: float, kit: session.GroupingKit
) -> str:
    """*markdown* with slider target *x* set, inside the domain it was authored in.

    The range is the target's, not the protocol's, so it cannot be checked until
    the target is known — and the replacement keeps the spelling the author used:
    a percentage stays a percentage, and a ratio keeps its denominator.
    """
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise FrameError("bad_value", str(value))
    before = _targets(markdown, kit)
    if not 0 <= x < len(before):
        raise FrameError("bad_target", f"no target {x}")
    action = before[x].action
    if action is None or action.value is None:
        raise FrameError("bad_target", "only a slider takes a value")
    if not _in_domain(action, value):
        raise FrameError("bad_value", str(value))
    if action.value == float(value):
        return markdown
    replacement = (
        f"[{float(value):g}{action.value_unit}]"
        if action.value_unit
        else f"[{float(value):g}/{action.value_max or 100:g}]"
    )
    for match in _SLIDER_TOKEN.finditer(markdown):
        candidate = markdown[: match.start()] + replacement + markdown[match.end() :]
        after = _targets(candidate, kit)
        if len(before) != len(after):
            continue
        if any(
            _signature(old) != _signature(new)
            for i, (old, new) in enumerate(zip(before, after))
            if i != x
        ):
            continue
        moved = after[x].action
        if moved is not None and moved.value == float(value):
            return candidate
    raise FrameError("bad_target", f"no source edit changes only target {x}")


# An emphasis wrapper around a whole link token: the button's variant.
_WRAPPED = re.compile(r"^(\*{1,3}|_{1,3})(.*)\1$", re.DOTALL)


def _respelled(token: str, chosen: bool) -> str | None:
    """*token* as the main variant (*chosen*) or the quieter ``*…*`` one, or None
    when it is spelled so already."""
    wrapped = _WRAPPED.match(token)
    if chosen:
        return wrapped.group(2) if wrapped else None
    return None if wrapped else f"*{token}*"


def _set_option(
    markdown: str, before: list[Target], i: int, chosen: bool, kit
) -> tuple[str, list[Target]]:
    """*markdown* with option *i* alone respelled chosen or not, and its targets."""
    for m in _LINK_TOKEN.finditer(markdown):
        new = _respelled(m.group(0), chosen)
        if new is None or "md2ui.choice" not in new:
            continue
        candidate = markdown[: m.start()] + new + markdown[m.end() :]
        after = _targets(candidate, kit)
        if _only_changed(before, after, i, "checked" if chosen else "unchecked"):
            return candidate, after
    raise FrameError("bad_target", f"no source edit changes only target {i}")


def choose_markdown(markdown: str, x: int, kit: session.GroupingKit) -> str:
    """*markdown* with choice option *x* chosen in its group, and nothing else.

    The chosen option is the one written as the main variant (``render_choices``):
    *x*'s button loses its emphasis wrapper and the option chosen before it gains
    ``*…*``, each edit found the way :func:`mark_markdown` finds one. An option
    already chosen returns *markdown* unchanged.
    """
    before = _targets(markdown, kit)
    if not 0 <= x < len(before):
        raise FrameError("bad_target", f"no target {x}")
    name = choice_name(before[x].action)
    if name is None:
        raise FrameError("bad_target", "only a choice option is chosen")
    if not _option_checked(before[x]):
        return markdown
    markdown, before = _set_option(markdown, before, x, True, kit)
    for i, target in enumerate(before):
        if (
            i != x
            and choice_name(target.action) == name
            and not _option_checked(target)
        ):
            markdown, before = _set_option(markdown, before, i, False, kit)
    return markdown


def _option_checked(target: Target) -> bool:
    """An option's ``checked``: True unless it is the chosen one."""
    return target.action is not None and bool(target.action.checked)
