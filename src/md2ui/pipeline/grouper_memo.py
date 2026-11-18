"""The memo for what the grouper asks: the split criteria and the detector.

``process`` asks both the same question many times: Phase 3 detects every
node, Phase 4+5 and the 5.5 peel then re-detect the same leaves, and the split
paths re-ask the criteria of the same content. Both answers are pure functions
of the text, so the memo has nothing to invalidate.

The memo also lives ACROSS calls (ADR-103): the grouping kit that
``session.load_grouping_kit`` builds is memoized, so a document re-sent or
patched by an agent, or saved again in the window, is answered from the memo
for every line that did not change. The cap bounds the memory. A caller that
hands ``process`` bare objects still gets a memo for that one call.

Each wrapper is a SUBCLASS of what it wraps, so every ``detector:
DataPointDetector`` annotation downstream still holds without a cast. Neither
calls ``super().__init__`` -- that would recompile the detector's patterns.
Anything not overridden reaches the wrapped object through ``__getattr__``.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any

from md2ui.pipeline.grouper_split_criteria import Criterion, SplitCriteria
from md2ui.pipeline.data_point_detector import DataPointDetector

# Distinct texts each memo keeps; the least recently asked goes first. Sized to
# keep a long agent session's documents and their revisions answered.
MEMO_CAP = 20_000


class _Lru:
    """A capped text -> answer map, safe to share between grouping threads
    (the server groups off its event loop)."""

    def __init__(self, cap: int) -> None:
        self._cap = cap
        self._answers: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, text: str) -> Any:
        with self._lock:
            hit = self._answers.get(text)
            if hit is not None:
                self._answers.move_to_end(text)
            return hit

    def put(self, text: str, answer: Any) -> None:
        with self._lock:
            self._answers[text] = answer
            if len(self._answers) > self._cap:
                self._answers.popitem(last=False)

    def __contains__(self, text: str) -> bool:
        return text in self._answers

    def __len__(self) -> int:
        return len(self._answers)


class MemoSplitCriteria(SplitCriteria):
    """Each criteria question answered once per distinct text."""

    def __init__(self, inner: SplitCriteria, cap: int = MEMO_CAP) -> None:
        self._inner = inner
        self._applicable_memo = _Lru(cap)

    def __getattr__(self, name: str) -> Any:
        # Only reached for attributes this wrapper does not have itself. The
        # guard stops a half-built wrapper (copy / pickle) recursing forever.
        if name in ("_inner", "_applicable_memo"):
            raise AttributeError(name)
        return getattr(self._inner, name)

    def applicable(self, text: str) -> frozenset[Criterion]:
        hit = self._applicable_memo.get(text)
        if hit is None:
            hit = self._inner.applicable(text)
            self._applicable_memo.put(text, hit)
        return hit


class MemoDetector(DataPointDetector):
    """``detect_pipeline`` answered once per distinct text, as a fresh copy."""

    def __init__(self, inner: DataPointDetector, cap: int = MEMO_CAP) -> None:
        self._inner = inner
        self._memo = _Lru(cap)

    def __getattr__(self, name: str) -> Any:
        if name in ("_inner", "_memo"):
            raise AttributeError(name)
        return getattr(self._inner, name)

    def detect_pipeline(self, text: str) -> list[dict]:
        hit = self._memo.get(text)
        if hit is None:
            hit = self._inner.detect_pipeline(text)
            self._memo.put(text, hit)
        # A fresh list of fresh dicts every time, the first answer included.
        # Callers rewrite the TOP-LEVEL keys of the dicts they get back —
        # ``_detect_through_markers`` re-bases ``start`` / ``end`` /
        # ``matched`` onto the unstripped text — so a shared dict would hand
        # the next caller offsets that belong to someone else's content. The
        # nested ``value`` is shared, exactly as ``_partition_data_points``
        # already shares it between split pieces: nothing writes into a
        # ``value`` after detection, and ``to_dict`` serializes it into new
        # objects, so a deepcopy would protect nothing more.
        return [dict(dp) for dp in hit]


def memoized(
    criteria: SplitCriteria | None, detector: DataPointDetector | None
) -> tuple[SplitCriteria | None, MemoDetector]:
    """The criteria and detector ``process`` asks: the caller's own memo when it brings one
    (the kit's, shared across calls), otherwise a memo for this call alone.
    The caller's objects are never changed."""
    if not isinstance(detector, MemoDetector):
        detector = MemoDetector(detector or DataPointDetector())
    if criteria is not None and not isinstance(criteria, MemoSplitCriteria):
        criteria = MemoSplitCriteria(criteria)
    return criteria, detector
