"""
Regression tests for DataPointDetector weekday + day-of-month detection
(e.g. "Mon 15", "Tuesday 3rd").

Run with: uv run python tests/data_point_detector_weekday_day_tests.py
"""

from md2ui.pipeline.data_point_detector import DataPointDetector, DataPointType


def _detect(text: str):
    return DataPointDetector().detect_all(text)


def _assert_single(
    text: str,
    dp_type: DataPointType,
    matched: str,
    start: int | None = None,
    end: int | None = None,
):
    results = _detect(text)
    assert len(results) == 1, (
        f"{text!r}: expected 1 match, got {len(results)}: "
        f"{[(r['type'].value, r['matched']) for r in results]}"
    )
    r = results[0]
    assert r["type"] == dp_type, (
        f"{text!r}: expected type {dp_type.value}, got {r['type'].value}"
    )
    assert r["matched"] == matched, (
        f"{text!r}: expected matched {matched!r}, got {r['matched']!r}"
    )
    if start is not None:
        assert r["start"] == start, (
            f"{text!r}: expected start {start}, got {r['start']}"
        )
    if end is not None:
        assert r["end"] == end, f"{text!r}: expected end {end}, got {r['end']}"
    return r


# ---------------------------------------------------------------------------
# Group A — Abbreviated weekday + bare day number
# ---------------------------------------------------------------------------


def test_short_weekday_day():
    r = _assert_single("Mon 15", DataPointType.DATE, "Mon 15", 0, 6)
    assert r["value"]["day_name"] == "Monday"
    assert r["value"]["day_index"] == 0
    assert r["value"]["day"] == 15
    assert r["value"]["subtype"] == "weekday_day"
    print("  ✓  short weekday+day: Mon 15 → DATE")


def test_short_weekday_day_tue():
    r = _assert_single("Tue 10", DataPointType.DATE, "Tue 10", 0, 6)
    assert r["value"]["day_name"] == "Tuesday"
    assert r["value"]["day"] == 10
    print("  ✓  short weekday+day: Tue 10 → DATE")


# ---------------------------------------------------------------------------
# Group B — Full weekday name + bare day number
# ---------------------------------------------------------------------------


def test_full_weekday_day():
    r = _assert_single("Monday 3", DataPointType.DATE, "Monday 3", 0, 8)
    assert r["value"]["day_name"] == "Monday"
    assert r["value"]["day_index"] == 0
    assert r["value"]["day"] == 3
    assert r["value"]["subtype"] == "weekday_day"
    print("  ✓  full weekday+day: Monday 3 → DATE")


# ---------------------------------------------------------------------------
# Group C — Ordinal suffix support
# ---------------------------------------------------------------------------


def test_short_weekday_day_ordinal():
    r = _assert_single("Fri 3rd", DataPointType.DATE, "Fri 3rd", 0, 7)
    assert r["value"]["day_name"] == "Friday"
    assert r["value"]["day"] == 3
    print("  ✓  ordinal suffix: Fri 3rd → DATE")


# ---------------------------------------------------------------------------
# Group D — Invalid day numbers rejected (combo doesn't match, falls back
# to bare weekday-only detection)
# ---------------------------------------------------------------------------


def _assert_no_weekday_day_combo(text: str, expected_weekday_matched: str):
    results = _detect(text)
    combos = [r for r in results if r["value"].get("subtype") == "weekday_day"]
    assert not combos, (
        f"{text!r}: expected no weekday_day combo match, got: "
        f"{[(r['type'].value, r['matched']) for r in combos]}"
    )
    weekday_matches = [r for r in results if r["value"].get("subtype") == "day_of_week"]
    assert len(weekday_matches) == 1, (
        f"{text!r}: expected exactly one bare weekday match, got: "
        f"{[(r['type'].value, r['matched']) for r in weekday_matches]}"
    )
    assert weekday_matches[0]["matched"] == expected_weekday_matched


def test_invalid_day_falls_back_to_bare_weekday():
    _assert_no_weekday_day_combo("Mon 45", "Mon")
    print("  ✓  invalid day: Mon 45 → only 'Mon' detected, not the combo")


def test_invalid_day_32_rejected():
    _assert_no_weekday_day_combo("Mon 32", "Mon")
    print("  ✓  invalid day: Mon 32 → only 'Mon' detected, not the combo")


def test_invalid_day_zero_rejected():
    _assert_no_weekday_day_combo("Tue 0", "Tue")
    print("  ✓  invalid day: Tue 0 → only 'Tue' detected, not the combo")


# ---------------------------------------------------------------------------
# Group E — Single combined match (no double-counting against bare weekday)
# ---------------------------------------------------------------------------


def test_full_weekday_day_single_match():
    results = _detect("Monday 15")
    assert len(results) == 1, (
        f"expected a single combined match, got: "
        f"{[(r['type'].value, r['matched']) for r in results]}"
    )
    assert results[0]["matched"] == "Monday 15"
    print("  ✓  Monday 15 → single combined match, not split")


TESTS = [
    # Group A
    test_short_weekday_day,
    test_short_weekday_day_tue,
    # Group B
    test_full_weekday_day,
    # Group C
    test_short_weekday_day_ordinal,
    # Group D
    test_invalid_day_falls_back_to_bare_weekday,
    test_invalid_day_32_rejected,
    test_invalid_day_zero_rejected,
    # Group E
    test_full_weekday_day_single_match,
]


if __name__ == "__main__":
    print("DataPointDetector — weekday + day-of-month detection tests")
    print("=" * 60)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 60)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
