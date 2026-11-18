"""A score fraction reads both of its numbers whole: ``0.8/1.5 TB`` is 0.8 of 1.5.

The skills teach ``Key: a/b unit`` for a share of a total that is not a percentage,
and a total is often a decimal (disk sizes, budgets). Both the ring's share and the
maximum ``mark key=`` checks an update against come from the parsed numbers.

Run with: uv run python tests/data_point_detector_score_fraction_tests.py
"""

from decimal import Decimal

from md2ui.pipeline.data_point_detector import DataPointDetector, DataPointType


def _score(text: str):
    results = [
        r
        for r in DataPointDetector().detect_all(text)
        if r["type"] == DataPointType.SCORE
    ]
    assert len(results) == 1, f"{text!r}: expected one SCORE, got {results}"
    return results[0]


def test_a_decimal_maximum_is_read_whole():
    r = _score("Backup: 0.8/1.5 TB")
    assert r["matched"] == "0.8/1.5", r["matched"]
    assert r["value"]["score"] == Decimal("0.8"), r["value"]
    assert r["value"]["max"] == Decimal("1.5"), r["value"]


def test_a_maximum_below_one_is_not_zero():
    assert _score("Load: 0.3/0.5")["value"]["max"] == Decimal("0.5")


def test_whole_maximums_are_unchanged():
    assert _score("Disk: 61/128 GB")["value"]["max"] == Decimal("128")
    assert _score("4.8/5.0 stars")["value"]["max"] == Decimal("5")


TESTS = [
    test_a_decimal_maximum_is_read_whole,
    test_a_maximum_below_one_is_not_zero,
    test_whole_maximums_are_unchanged,
]


if __name__ == "__main__":
    for t in TESTS:
        t()
        print(f"  ✓  {t.__name__}")
    print(f"All {len(TESTS)} tests passed.")
