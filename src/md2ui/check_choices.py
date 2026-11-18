"""What `check` says about choices and counts (ADR-405).

A choice option is an ``agent:`` button carrying ``md2ui.choice=<name>``; a count
is a ratio slider between ``➖`` and ``➕``. Both hold a value in the window until a
``md2ui.commit`` press carries it, so each spelling that would not hold one, or
would hold it where nothing shows it, is told:

* ``choice-not-agent`` (error): the hint on a plain link or an ``#anchor``, which
  hold nothing;
* ``choice-commits`` (error): an option that is also a commit press;
* ``choice-names`` (warning): two names in one run of buttons;
* ``choice-in-task`` (error): an option in a task row, whose box is the row's control;
* ``choice-chosen`` (warning / note): a group written with two main buttons, or
  with none (nothing chosen yet, which may be meant);
* ``choice-spelling`` (warning): an option written ``**…**`` or ``***…***``,
  stronger than ``*…*``, which a theme may paint as a main button, so that
  nothing chosen reads as all chosen;
* ``choice-not-button`` (warning): an option inside a sentence or after a key,
  which draws as a link and stays a turn;
* ``count-commits`` (error): a count linked to a commit press, ``[[2/9]](…)``;
* ``count-whole`` (error): a count written with a fraction; it steps by one.

Each issue is ``(level, code, message, x)``, ``x`` the target's ordinal.
"""

from __future__ import annotations

from collections.abc import Iterator

from md2ui.pipeline.render_actions import Target
from md2ui.pipeline.render_choices import CHOICE_HINT, choice_name

_HINT = f"md2ui.{CHOICE_HINT}="
_TASKS = ("task_open", "task_done")
# The two spellings an option takes: the chosen one unwrapped, the rest `*…*`.
_SPELLINGS = (None, "primary", "secondary")

Issue = tuple[str, str, str, int | None]


def _hinted(target: Target) -> str | None:
    """The choice name the destination asks for, option or not."""
    a = target.action
    if a is None:
        return None
    name = dict(a.hints).get(CHOICE_HINT)
    if name is None and _HINT in (a.href or ""):
        name = (a.href or "").split(_HINT, 1)[1].split("&", 1)[0]
    return name


def _walk(node: dict, in_task: bool, into: dict) -> None:
    """Note each node id with whether it sits in a task row, and its spelling."""
    in_task = in_task or node.get("type") in _TASKS
    into["task"][node.get("node_id", "")] = in_task
    into["variant"][node.get("node_id", "")] = node.get("link_variant")
    for child in node.get("children", []):
        _walk(child, in_task, into)


def problems(tree: dict, targets: list[Target]) -> Iterator[Issue]:
    """Every issue choices and counts raise in a grouped page."""
    seen: dict = {"task": {}, "variant": {}}
    _walk(tree, False, seen)
    yield from _runs(tree, targets)
    chosen: dict[str, list[int]] = {}
    strong: dict[str, list[tuple[int, str]]] = {}
    for x, target in enumerate(targets):
        a = target.action
        hinted = _hinted(target)
        if a is None:
            continue
        name = choice_name(a)
        if hinted is not None and a.kind != "agent":
            yield (
                "error",
                "choice-not-agent",
                (
                    f"Target {x}, `{a.label}`: `md2ui.choice` holds a choice on an "
                    "`agent:` button only; this link goes somewhere and holds nothing."
                ),
                x,
            )
        elif hinted is not None and name is None and a.value is None:
            yield (
                "warning",
                "choice-not-button",
                (
                    f"Target {x}, `{a.label}`, is inside a sentence or after a key, so it "
                    "draws as a link and is no option: each tap is a turn. Put the "
                    "options on a line of their own, with the label on a line above."
                ),
                x,
            )
        if name is not None:
            chosen.setdefault(name, [])
            if a.checked is False:
                chosen[name].append(x)
            if seen["variant"].get(target.key) not in _SPELLINGS:
                strong.setdefault(name, []).append((x, a.label))
            if a.commit:
                yield (
                    "error",
                    "choice-commits",
                    (
                        f"Target {x}, `{a.label}`, is an option and a commit press: a "
                        "tap on it would send the page. Put `md2ui.commit` on a button "
                        "of its own."
                    ),
                    x,
                )
            if seen["task"].get(target.key.split("#")[0]):
                yield (
                    "error",
                    "choice-in-task",
                    (
                        f"Target {x}, `{a.label}`, is an option inside a task row, whose "
                        "box is its control. Write the options on a line of their own."
                    ),
                    x,
                )
        if a.count and a.commit:
            yield (
                "error",
                "count-commits",
                (
                    f"Target {x}, `{a.label}`, is a count that commits itself: each step "
                    "would send the page. Write it bare, `➖ [2/9] ➕`, and commit it "
                    "with a button."
                ),
                x,
            )
        if a.count and a.value is not None and not float(a.value).is_integer():
            yield (
                "error",
                "count-whole",
                (
                    f"Target {x}, `{a.label}`, is a count written as {a.value:g}: a count "
                    "steps by one, so write a whole number."
                ),
                x,
            )
    for name, options in strong.items():
        xs = [x for x, _label in options]
        labels = ", ".join(
            f"`{label}`" for label in dict.fromkeys(o[1] for o in options)
        )
        yield (
            "warning",
            "choice-spelling",
            (
                f"The `{name}` choice writes {labels} (target"
                f"{'s' if len(xs) > 1 else ''} {', '.join(map(str, xs))}) in a "
                "stronger spelling than `*…*`, which the theme may draw as the main "
                "button, so the option looks chosen. Only the chosen option takes "
                "the main spelling, unwrapped; every other one the quieter `*…*`."
            ),
            xs[0],
        )
    for name, xs in chosen.items():
        if len(xs) > 1:
            yield (
                "warning",
                "choice-chosen",
                (
                    f"The `{name}` choice is written with {len(xs)} main buttons "
                    f"(targets {', '.join(map(str, xs))}): write the chosen option as "
                    "the main button and every other one `*…*`."
                ),
                xs[1],
            )
        elif not xs:
            yield (
                "note",
                "choice-chosen",
                (
                    f"No option of the `{name}` choice is written as the main button, so "
                    "none shows chosen. If one is the default, write it unwrapped."
                ),
                None,
            )


def _runs(tree: dict, targets: list[Target]) -> Iterator[Issue]:
    """A run of buttons whose options name two groups."""
    ordinal = {t.key: x for x, t in enumerate(targets)}
    names = {t.key: choice_name(t.action) for t in targets}
    stack = [tree]
    while stack:
        node = stack.pop()
        kids = node.get("children", [])
        stack.extend(kids)
        found = {names.get(k.get("node_id", "")) for k in kids} - {None}
        if len(found) > 1:
            first = ordinal.get(kids[0].get("node_id", ""))
            yield (
                "warning",
                "choice-names",
                (
                    f"One run of buttons names {len(found)} choices "
                    f"({', '.join(sorted(f'`{n}`' for n in found))}): a run is one "
                    "choice. Give every option in it the same name."
                ),
                first,
            )
