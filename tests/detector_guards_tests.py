"""
Tests for the detector's pattern guards (``md2ui.pipeline.detector_guards``).

The detector skips a pattern when the text lacks a character every match of
that pattern must contain. That is only safe if the guard is a PROOF, so three
things are pinned here:

* each guard is read from the pattern's syntax tree the way the regex engine
  reads it -- an alternation needs only what every branch needs, an optional
  part needs nothing, a case-folded letter is never a guard;
* over every Markdown file of the snapshot corpus, every match of every
  registered pattern holds its guard's characters, and detection with the
  guards equals detection with every pattern run;
* a pattern whose tree cannot be read gets no guard and still runs, and a
  pattern registered after the first scan is not left out.

Byte-identity of the grouped corpus is the grouper snapshot's job.

Run with: uv run tests/detector_guards_tests.py
"""

import re
from pathlib import Path
from types import SimpleNamespace

from md2ui.pipeline import detector_guards
from md2ui.pipeline.data_point_detector import DataPointDetector, DataPointType
from md2ui.pipeline.detector_guards import PatternGuards, required

_ROOT = Path(__file__).resolve().parent.parent
_CORPUS = sorted(
    path
    for folder in ("tests", "tests-render")
    for path in (_ROOT / "data" / "markdown" / folder).rglob("*.md")
)


def _holds(match: str, need: frozenset[str]) -> bool:
    for c in need:
        if c == "DIGIT":
            if not re.search(r"\d", match):
                return False
        elif c not in match:
            return False
    return True


def test_guards_are_read_from_the_syntax_tree():
    assert required(re.compile(r"\$\d+(?:\.\d{2})?")) == {"$", "DIGIT"}
    # Each branch needs `%`; only one needs a digit.
    assert required(re.compile(r"(?:\d+%|about %)")) == {"%"}
    # An optional part, a lookahead and a negated class promise nothing.
    assert required(re.compile(r"a?(?=\d)[^x]")) == frozenset()
    # Under IGNORECASE a letter matches more than itself; `:` does not.
    assert required(re.compile(r"K:", re.IGNORECASE)) == {":"}
    assert required(re.compile(r"K:")) == {"K", ":"}


def test_every_match_over_the_corpus_holds_its_guard():
    assert _CORPUS, "the corpus moved; this test proves nothing without it"
    detector = DataPointDetector()
    guarded = 0
    for regex, _type, _parser in detector.patterns:
        need = required(regex)
        guarded += bool(need)
        for path in _CORPUS:
            text = path.read_text()
            for match in regex.finditer(text):
                assert _holds(match.group(), need), (regex.pattern, match.group())
    # Most patterns carry a guard, or the guards are not doing their job.
    assert guarded > len(detector.patterns) * 3 // 4, guarded


def test_detection_with_guards_equals_running_every_pattern():
    guarded = DataPointDetector()
    unguarded = DataPointDetector()
    original = detector_guards.required
    detector_guards.required = lambda regex: frozenset()
    try:
        lines = {line for path in _CORPUS for line in path.read_text().splitlines()}
        expected = {line: unguarded.detect_all(line) for line in lines}
    finally:
        detector_guards.required = original
    for line in lines:
        assert repr(guarded.detect_all(line)) == repr(expected[line]), line


def test_a_pattern_whose_tree_cannot_be_read_runs():
    dollars = re.compile(r"\$[0-9]+")
    assert required(dollars) == {"$", "DIGIT"}

    def unreadable(*args, **kwargs):
        raise RuntimeError("no tree")

    parser = detector_guards._P
    detector_guards._P = SimpleNamespace(parse=unreadable)
    try:
        assert required(dollars) == frozenset()
        guards = PatternGuards([(dollars, DataPointType.CURRENCY, str)])
    finally:
        detector_guards._P = parser
    assert len(guards.live("no digit, no dollar")) == 1


def test_a_text_without_a_digit_skips_the_digit_patterns():
    detector = DataPointDetector()
    guards = PatternGuards(detector._pipeline_patterns)
    assert len(guards.live("plain words only")) < len(detector._pipeline_patterns) / 2
    assert len(guards.live("$412M on 12/26/2025 at 45%")) > len(
        guards.live("plain words only")
    )


def test_a_pattern_registered_after_a_scan_runs():
    detector = DataPointDetector()
    detector.detect_all("zq-77")  # the first scan builds the guards
    detector.register(r"zq-\d+", DataPointType.IDENTIFIER, lambda m: {"value": m})
    assert any(dp["matched"] == "zq-77" for dp in detector.detect_all("zq-77"))


TESTS = [
    test_guards_are_read_from_the_syntax_tree,
    test_every_match_over_the_corpus_holds_its_guard,
    test_detection_with_guards_equals_running_every_pattern,
    test_a_pattern_whose_tree_cannot_be_read_runs,
    test_a_text_without_a_digit_skips_the_digit_patterns,
    test_a_pattern_registered_after_a_scan_runs,
]

if __name__ == "__main__":
    print("Detector Guards Tests")
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
