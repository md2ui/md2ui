"""The hooks `export_ts_fixtures.py` records the grouper through.

Everything here WRAPS md2ui from outside: nothing under ``src/`` knows it is being
watched. Each hook names the md2ui object it wraps, and a hook whose target has
moved or been renamed raises instead of recording nothing, because a silent hook
would export fixtures that look complete and are not.

* :func:`plain` / :func:`dump_json` -- the one JSON form every fixture is written
  in: dataclasses by field, enums by value, floats repr-exact, and the three
  non-finite floats as strings, since JSON has no spelling for them.
* :class:`PhaseRecorder` -- the tree after every phase of
  ``MarkdownGrouper._process_once``. The phases are read from that method's own
  ``# Phase N — …`` comments, so a phase is named exactly as md2ui names it.
* :class:`CallRecorder` -- every question the grouper asks the split criteria and
  the data-point detector, with its answer, in the order asked.
"""

from __future__ import annotations

import abc
import contextlib
import copy
import dataclasses
import enum
import importlib
import inspect
import json
import math
import re
import sys
from collections.abc import Callable, Iterator
from typing import Any

# --- one JSON form ------------------------------------------------------------

NON_FINITE = {math.inf: "Infinity", -math.inf: "-Infinity"}


def plain(obj: Any, rel_root: str | None = None) -> Any:
    """*obj* as JSON-safe data, losing nothing a fixture compares.

    A value of a type this does not know raises: a fixture that silently wrote
    ``repr()`` of an object would compare equal to nothing, or to everything.
    *rel_root*, when given, turns an absolute path under it into a path relative
    to it, so a fixture does not depend on where the checkout lives.
    """
    if obj is None or isinstance(obj, (bool, int, str)):
        if rel_root and isinstance(obj, str) and obj.startswith(rel_root):
            return obj[len(rel_root) :].lstrip("/")
        return obj
    if isinstance(obj, float):
        if math.isnan(obj):
            return "NaN"
        return NON_FINITE.get(obj, obj)
    if isinstance(obj, enum.Enum):
        return plain(obj.value, rel_root)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: plain(getattr(obj, f.name), rel_root)
            for f in dataclasses.fields(obj)
        }
    if isinstance(obj, dict):
        return {_key(k): plain(v, rel_root) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [plain(v, rel_root) for v in obj]
    if isinstance(obj, (set, frozenset)):
        # A text style override's `declared` field names: written sorted.
        return sorted((plain(v, rel_root) for v in obj), key=repr)
    raise TypeError(f"no fixture form for {type(obj).__module__}.{type(obj).__name__}")


def _key(k: Any) -> str:
    if isinstance(k, str):
        return k
    if isinstance(k, enum.Enum):
        return str(k.value)
    if isinstance(k, (int, float, bool)) or k is None:
        return json.dumps(k)
    if isinstance(k, tuple):
        # `Theme.fixed_section_levels` is keyed by (style name, level).
        return json.dumps([plain(v) for v in k])
    raise TypeError(f"no fixture form for a {type(k).__name__} dict key")


def dump_json(obj: Any) -> str:
    """The text every ``.json`` fixture is written as (the grouper snapshot's form)."""
    return json.dumps(obj, indent=2, sort_keys=True, allow_nan=False)


def dump_line(obj: Any) -> str:
    """One ``.jsonl`` record. ASCII, so no character inside a string (U+2028, the
    hard break) can be read as a line end by a reader that splits lines."""
    return json.dumps(obj, sort_keys=True, allow_nan=False)


# --- installing hooks ---------------------------------------------------------


class Hooks(abc.ABC):
    """Patches md2ui attributes from outside and puts every one back.

    A patch whose target is not where it should be raises: md2ui moved or renamed
    it, and a hook that silently patched nothing would record nothing.
    """

    def __init__(self) -> None:
        self._undo: list[tuple[Any, str, Any]] = []

    def patch(self, owner: Any, name: str, new: Any) -> Any:
        """Replace ``owner.name`` with *new*; returns what was there."""
        if name not in vars(owner):
            raise RuntimeError(f"hook target {owner.__name__}.{name} is gone")
        orig = vars(owner)[name]
        self._undo.append((owner, name, orig))
        setattr(owner, name, new)
        return orig

    @abc.abstractmethod
    def install(self) -> None:
        """Apply every patch; each subclass says which."""

    def restore(self) -> None:
        for owner, name, orig in reversed(self._undo):
            setattr(owner, name, orig)
        self._undo.clear()


@contextlib.contextmanager
def installed(*hooks: Hooks) -> Iterator[None]:
    """*hooks* installed for the duration of the block, in order."""
    done: list[Hooks] = []
    try:
        for h in hooks:
            h.install()
            done.append(h)
        yield
    finally:
        for h in reversed(done):
            h.restore()


# --- the tree after every phase -----------------------------------------------

# `# Phase 2.1b — …`, `# Phases 6.15–6.245 — …`. The em dash is what separates a
# phase header from a comment that merely mentions a phase.
_PHASE_HEADER = re.compile(r"^\s*# Phases? ([0-9][0-9a-z.+–]*) — ")
# The one step the method comments without a phase number.
_UNNUMBERED = {"# Safety net:": "safety-net"}

# The phases as md2ui names them on the commit the fixtures were made from. A
# change to this list is a change to what the port must reproduce, so it is
# asserted rather than discovered: a renamed, added or removed phase fails.
EXPECTED_PHASES = (
    "1",
    "2",
    "2.1",
    "2.1b",
    "2.13",
    "2.15",
    "2.16",
    "2.165",
    "safety-net",
    "3",
    "4+5",
    "5.5",
    "5.55",
    "5.6",
    "6",
    "6.04",
    "6.05",
    "6.055",
    "6.06",
    "6.065",
    "6.07",
    "6.075",
    "6.08",
    "6.1",
    "6.15–6.245",
    "6.246",
    "6.25",
    "6.26",
    "6.5",
)


def phase_dir(index: int, phase: str) -> str:
    """The directory a phase's trees are written to: ordered, filesystem-safe."""
    return f"{index:02d}-phase-{phase.replace('–', '-')}"


def read_phases(method: Callable) -> tuple[list[str], dict[int, int]]:
    """``(phase names, line -> phase index)`` from *method*'s phase comments.

    A line belongs to the last phase header above it; lines above the first
    header (the docstring, the memo set-up) belong to none.
    """
    lines, first = inspect.getsourcelines(method)
    names: list[str] = []
    owner: dict[int, int] = {}
    for offset, text in enumerate(lines):
        m = _PHASE_HEADER.match(text)
        label = m.group(1) if m else None
        for marker, name in _UNNUMBERED.items():
            if text.strip().startswith(marker):
                label = name
        if label is not None:
            names.append(label)
        if names:
            owner[first + offset] = len(names) - 1
    if tuple(names) != EXPECTED_PHASES:
        raise RuntimeError(
            "MarkdownGrouper._process_once's phases changed: "
            f"expected {EXPECTED_PHASES}, found {tuple(names)}. "
            "Update EXPECTED_PHASES and say so in the fixture report."
        )
    return names, owner


class PhaseRecorder(Hooks):
    """Records the grouper's tree each time ``_process_once`` leaves a phase.

    ``passes`` holds one list per ``_process_once`` call, each a list of
    ``to_dict()`` trees, one per phase in :data:`EXPECTED_PHASES`. A document
    with ``+++`` spacers is grouped twice by ``process`` (with the spacers, then
    without), so it has two passes; every other document has one.

    A phase ends when the first line of a LATER phase runs (line events are
    switched on for that one code object only). A phase whose body is skipped
    (``if self._card_specs:``) still runs its ``if`` line, so every phase is
    recorded for every document, unchanged where it did nothing. The last phase
    ends when the method returns. The tree is deep-copied before ``to_dict``,
    which assigns a link's variant fields as it serializes.
    """

    TOOL = sys.monitoring.PROFILER_ID

    def __init__(self) -> None:
        super().__init__()
        from md2ui.pipeline.markdown_grouper import MarkdownGrouper

        self._cls = MarkdownGrouper
        self._code = MarkdownGrouper._process_once.__code__
        self.names, self._owner = read_phases(MarkdownGrouper._process_once)
        self.passes: list[list[dict]] = []
        self._stack: list[Any] = []
        self._current = -1

    def _snapshot_through(self, index: int) -> None:
        grouper = self._stack[-1]
        trees = self.passes[-1]
        while self._current < index:
            if self._current >= 0:
                trees.append(copy.deepcopy(grouper.ast).to_dict())
            self._current += 1

    def _on_line(self, code: Any, line: int) -> None:
        if code is not self._code:
            raise RuntimeError("a line event from code that was not instrumented")
        index = self._owner.get(line, -1)
        if index > self._current and self._stack:
            self._snapshot_through(index)

    def install(self) -> None:
        recorder = self
        orig: Callable = vars(self._cls)["_process_once"]

        def _process_once(
            grouper: Any,
            criteria: Any = None,
            detector: Any = None,
        ) -> Any:
            recorder._stack.append(grouper)
            recorder.passes.append([])
            recorder._current = -1
            try:
                result = orig(grouper, criteria, detector)
                recorder._snapshot_through(len(recorder.names))
            finally:
                recorder._stack.pop()
            if len(recorder.passes[-1]) != len(recorder.names):
                raise RuntimeError("a phase of _process_once was never recorded")
            return result

        mon = sys.monitoring
        mon.use_tool_id(self.TOOL, "md2ui-ts-fixtures")
        mon.register_callback(self.TOOL, mon.events.LINE, self._on_line)
        mon.set_local_events(self.TOOL, self._code, mon.events.LINE)
        self.patch(self._cls, "_process_once", _process_once)

    def restore(self) -> None:
        super().restore()
        mon = sys.monitoring
        mon.set_local_events(self.TOOL, self._code, 0)
        mon.register_callback(self.TOOL, mon.events.LINE, None)
        mon.free_tool_id(self.TOOL)


# --- every question the grouper asks ------------------------------------------


def _criteria(answer: frozenset) -> list[str]:
    return sorted(c.name for c in answer)


def detector_answer(points: list[dict]) -> list[dict]:
    """A detector answer in the grouper's own serialized form, plus the two keys
    ``to_dict`` drops (``type`` as the enum value, ``is_approximate``)."""
    from md2ui.pipeline.grouper_types import MarkdownGroupNode

    return [
        {
            "type": dp["type"].value,
            "label": f"dp_{dp['type'].value}",
            "matched": dp["matched"],
            "value": plain(MarkdownGroupNode._serialize_dp_value(dp["value"])),
            "start": dp["start"],
            "end": dp["end"],
            "is_approximate": dp.get("is_approximate", False),
        }
        for dp in points
    ]


class CallRecorder(Hooks):
    """Every split-criteria and detector question asked while grouping.

    Recorded where the PHASES ask it, above the per-call memo, so repeats are
    kept (``memo_hit`` says which were answered from the memo). Three entry
    points carry every question at this commit:

    * ``MemoSplitCriteria.applicable(text)`` -- the criteria object;
    * ``_rule_applicable(text, element_has_regular_text=…)``, which the element
      splitter imports and asks directly, bypassing the object;
    * ``MemoDetector.detect_pipeline(text)`` -- the detector.
    """

    RULE_MODULES = ("md2ui.pipeline.grouper_element_splits",)

    def __init__(self) -> None:
        super().__init__()
        self.criteria: list[dict] = []
        self.detector: list[dict] = []

    def install(self) -> None:
        from md2ui.pipeline.grouper_memo import MemoDetector, MemoSplitCriteria

        criteria, detector = self.criteria, self.detector
        orig_applicable = vars(MemoSplitCriteria)["applicable"]
        orig_detect = vars(MemoDetector)["detect_pipeline"]

        def applicable(memo: Any, text: str) -> frozenset:
            hit = text in memo._applicable_memo
            answer = orig_applicable(memo, text)
            criteria.append(
                {
                    "q": "applicable",
                    "text": text,
                    "answer": _criteria(answer),
                    "memo_hit": hit,
                }
            )
            return answer

        def detect_pipeline(memo: Any, text: str) -> list[dict]:
            hit = text in memo._memo
            answer = orig_detect(memo, text)
            detector.append(
                {
                    "q": "detect_pipeline",
                    "text": text,
                    "answer": detector_answer(answer),
                    "memo_hit": hit,
                }
            )
            return answer

        self.patch(MemoSplitCriteria, "applicable", applicable)
        self.patch(MemoDetector, "detect_pipeline", detect_pipeline)
        for name in self.RULE_MODULES:
            module = importlib.import_module(name)
            self.patch(module, "_rule_applicable", self._rule_hook(module))

    def _rule_hook(self, module: Any) -> Callable:
        criteria = self.criteria
        orig = vars(module)["_rule_applicable"]
        asked_by = module.__name__.rsplit(".", 1)[1]

        def _rule_applicable(
            text: str, *, element_has_regular_text: bool | None = None
        ) -> frozenset:
            answer = orig(text, element_has_regular_text=element_has_regular_text)
            criteria.append(
                {
                    "q": "rule_applicable",
                    "asked_by": asked_by,
                    "text": text,
                    "element_has_regular_text": element_has_regular_text,
                    "answer": _criteria(answer),
                }
            )
            return answer

        return _rule_applicable
