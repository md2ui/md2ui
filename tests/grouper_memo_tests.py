"""
Tests for the grouper's memo (``md2ui.pipeline.grouper_memo``).

``process`` wraps its split criteria and detector so that a text asked about
twice is answered once: for one call when it is handed bare objects, and across
calls when it is handed the grouping kit, whose objects come memoized (ADR-103).
Within a document most questions are repeats. These properties make that safe,
and each is pinned here:

* an answer from the memo equals the wrapped object's own answer;
* a detector answer is a fresh list of fresh dicts every time. Callers rewrite
  the dicts' top-level keys (``_detect_through_markers`` re-bases their
  offsets), so a shared dict would hand the next caller offsets that belong to
  other content. The nested ``value`` is shared on purpose — the split paths
  already share it, and nothing writes into it;
* bare objects get a memo for one ``process`` call only, and the caller's
  objects are never touched;
* the kit's memo is shared by every call, so it must not change any output:
  documents grouped one after another with one kit -- in any order, from
  several threads -- come out as they do with a fresh kit each, and nothing a
  grouping does writes into an answer the memo keeps for the next one;
* the memo is capped, dropping the least recently asked text first.

Byte-identity over the whole corpus is the grouper snapshot's job, not this
module's.

Run with: uv run tests/grouper_memo_tests.py
"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from md2ui import session
from md2ui.pipeline.grouper_split_criteria import Criterion, SplitCriteria
from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.grouper_memo import MemoSplitCriteria, MemoDetector
from md2ui.pipeline.markdown_grouper import MarkdownGrouper

_RENDER = Path(__file__).resolve().parent.parent / "data" / "markdown" / "tests-render"
# Real pages: each repeats lines within itself, and the catalogs share some.
_DOCS = (
    sorted(_RENDER.glob("catalogs/*/content.md"))[:5]
    + sorted(_RENDER.glob("details-pages/*/content.md"))[:4]
)

_TEXT = "Revenue: $412M (49%) on 12/26/2025"


class _CountingDetector(DataPointDetector):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def detect_pipeline(self, text: str) -> list[dict]:
        self.calls.append(text)
        return super().detect_pipeline(text)


class _CountingCriteria(SplitCriteria):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def applicable(self, text: str) -> frozenset[Criterion]:
        self.calls.append(text)
        if len(text) % 2:
            return frozenset({Criterion.KEY_VALUE, Criterion.ELEMENT})
        return frozenset({Criterion.ELEMENT})


def test_a_detector_answer_matches_and_each_text_is_detected_once():
    inner = _CountingDetector()
    memo = MemoDetector(inner)
    first = memo.detect_pipeline(_TEXT)
    second = memo.detect_pipeline(_TEXT)
    assert first, "the sample must detect something, or this proves nothing"
    assert first == second == DataPointDetector().detect_pipeline(_TEXT)
    assert inner.calls == [_TEXT]


def test_every_detector_answer_is_a_fresh_copy():
    memo = MemoDetector(DataPointDetector())
    first = memo.detect_pipeline(_TEXT)
    first[0]["start"] = -1
    first[0]["matched"] = "corrupted"
    first.append({"type": "junk"})
    assert memo.detect_pipeline(_TEXT) == DataPointDetector().detect_pipeline(_TEXT)


def test_applicable_is_memoized_once_per_distinct_text():
    inner = _CountingCriteria()
    memo = MemoSplitCriteria(inner)
    answers = [memo.applicable(t) for t in ("a", "bb", "a", "bb", "a")]
    assert answers == [
        frozenset({Criterion.KEY_VALUE, Criterion.ELEMENT}),
        frozenset({Criterion.ELEMENT}),
        frozenset({Criterion.KEY_VALUE, Criterion.ELEMENT}),
        frozenset({Criterion.ELEMENT}),
        frozenset({Criterion.KEY_VALUE, Criterion.ELEMENT}),
    ]
    assert inner.calls == ["a", "bb"]


def test_other_attributes_reach_the_wrapped_object():
    inner = DataPointDetector()
    memo = MemoDetector(inner)
    assert memo.patterns is inner.patterns


def test_process_memoizes_per_call_and_leaves_the_callers_detector_alone():
    """A document that repeats a line, grouped twice with the same detector."""
    doc = "# Stats\n\n- Revenue: $412M\n- Revenue: $412M\n\nRevenue: $412M\n"
    criteria = SplitCriteria()
    det = _CountingDetector()
    MarkdownGrouper(doc).process(criteria, det)
    first = list(det.calls)
    assert first and len(first) == len(set(first)), "a text reached the criteria twice"
    det.calls.clear()
    MarkdownGrouper(doc).process(criteria, det)
    assert det.calls == first, "the second call must start cold"
    assert type(det) is _CountingDetector


def test_the_memo_drops_the_least_recently_asked_text():
    inner = _CountingCriteria()
    memo = MemoSplitCriteria(inner, cap=2)
    for text in ("a", "bb", "a", "ccc", "a", "bb"):
        memo.applicable(text)
    # "bb" was the least recently asked when "ccc" arrived, so it was dropped.
    assert inner.calls == ["a", "bb", "ccc", "bb"]
    assert len(memo._applicable_memo) == 2


def test_the_kit_answers_a_resent_document_from_its_memo():
    doc = "# Stats\n\n- Revenue: $412M\n- Margin: 49%\n"
    counting = _CountingDetector()
    kit = (MemoSplitCriteria(SplitCriteria()), MemoDetector(counting))
    session.group_markdown(doc, kit)
    assert counting.calls, "the first grouping must reach the detector"
    counting.calls.clear()
    session.group_markdown(doc, kit)
    assert counting.calls == [], "a re-sent document must be answered from the memo"
    criteria, det = session.load_grouping_kit()
    assert isinstance(criteria, MemoSplitCriteria) and isinstance(det, MemoDetector)


def _dump(text: str, kit: session.GroupingKit) -> str:
    ast = session.group_markdown(text, kit)
    assert ast is not None
    return json.dumps(ast.to_dict(), sort_keys=True)


def test_a_shared_kit_changes_no_output():
    """Corpus A, then B, then A again with one kit, against a fresh kit each."""
    assert len(_DOCS) >= 8, "the sample pages moved; this test proves nothing"
    texts = [path.read_text() for path in _DOCS]
    edited = [text.replace("\n\n", "\n\nAn added line, 42%.\n\n", 1) for text in texts]
    fresh = [_dump(t, session.load_grouping_kit()) for t in texts + edited]
    kit = session.load_grouping_kit()
    shared = [_dump(t, kit) for t in texts + edited + texts]
    assert shared == fresh + fresh[: len(texts)]
    with ThreadPoolExecutor(4) as pool:
        threaded = list(pool.map(lambda t: _dump(t, kit), edited + texts))
    assert threaded == fresh[len(texts) :] + fresh[: len(texts)]
    # Nothing written into an answer the memo keeps: each still equals what
    # the detector says about its text today.
    memo = kit[1]
    assert isinstance(memo, MemoDetector)
    kept = memo._memo._answers
    detector = DataPointDetector()
    assert kept
    for text, answer in kept.items():
        assert repr(answer) == repr(detector.detect_pipeline(text)), text


TESTS = [
    test_a_detector_answer_matches_and_each_text_is_detected_once,
    test_every_detector_answer_is_a_fresh_copy,
    test_applicable_is_memoized_once_per_distinct_text,
    test_other_attributes_reach_the_wrapped_object,
    test_process_memoizes_per_call_and_leaves_the_callers_detector_alone,
    test_the_memo_drops_the_least_recently_asked_text,
    test_the_kit_answers_a_resent_document_from_its_memo,
    test_a_shared_kit_changes_no_output,
]

if __name__ == "__main__":
    print("Grouper Memo Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
