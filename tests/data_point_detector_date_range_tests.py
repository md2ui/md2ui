"""
Regression tests for DataPointDetector DATE_RANGE detection.

Covers the single-month-with-year shape and the two-endpoint shape
(cross-month, with/without year, ASCII or Unicode dash separators).

Run with: uv run python tests/data_point_detector_date_range_tests.py
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


# ---------------------------------------------------------------------------
# Group A — Single-month-with-year ranges
# ---------------------------------------------------------------------------


def test_baseline_long_month_with_year():
    _assert_single(
        "January 12-28, 2026", DataPointType.DATE_RANGE, "January 12-28, 2026", 0, 19
    )
    print("  ✓  baseline: January 12-28, 2026 → DATE_RANGE")


def test_baseline_short_month_with_year():
    _assert_single(
        "Jan 12-28, 2026", DataPointType.DATE_RANGE, "Jan 12-28, 2026", 0, 15
    )
    print("  ✓  baseline: Jan 12-28, 2026 → DATE_RANGE")


# ---------------------------------------------------------------------------
# Group B — Short month, no year
# ---------------------------------------------------------------------------


def test_short_month_no_year_cross_month():
    _assert_single("Jul 5 - Dec 5", DataPointType.DATE_RANGE, "Jul 5 - Dec 5", 0, 13)
    print("  ✓  new: Jul 5 - Dec 5 → DATE_RANGE")


def test_short_month_no_year_same_month():
    _assert_single("Jul 5 - Jul 28", DataPointType.DATE_RANGE, "Jul 5 - Jul 28", 0, 14)
    print("  ✓  new: Jul 5 - Jul 28 → DATE_RANGE")


# ---------------------------------------------------------------------------
# Group C — Long month, no year
# ---------------------------------------------------------------------------


def test_long_month_no_year_cross_month():
    _assert_single(
        "July 5 - December 5", DataPointType.DATE_RANGE, "July 5 - December 5", 0, 19
    )
    print("  ✓  new: July 5 - December 5 → DATE_RANGE")


# ---------------------------------------------------------------------------
# Group D — With per-side year
# ---------------------------------------------------------------------------


def test_short_month_with_year_both_sides():
    _assert_single(
        "Jul 5, 2025 - Dec 5, 2025",
        DataPointType.DATE_RANGE,
        "Jul 5, 2025 - Dec 5, 2025",
        0,
        25,
    )
    print("  ✓  new: Jul 5, 2025 - Dec 5, 2025 → DATE_RANGE")


def test_long_month_with_year_both_sides():
    _assert_single(
        "July 5, 2025 - December 5, 2025",
        DataPointType.DATE_RANGE,
        "July 5, 2025 - December 5, 2025",
        0,
        31,
    )
    print("  ✓  new: July 5, 2025 - December 5, 2025 → DATE_RANGE")


# ---------------------------------------------------------------------------
# Group E — Unicode dash variants
# ---------------------------------------------------------------------------


def test_en_dash_separator():
    _assert_single("Jul 5 – Dec 5", DataPointType.DATE_RANGE, "Jul 5 – Dec 5", 0, 13)
    print("  ✓  new: en-dash → DATE_RANGE")


def test_em_dash_separator():
    _assert_single("Jul 5 — Dec 5", DataPointType.DATE_RANGE, "Jul 5 — Dec 5", 0, 13)
    print("  ✓  new: em-dash → DATE_RANGE")


# ---------------------------------------------------------------------------
# Group F — Overlap guard: range must beat two stray partial DATEs
# ---------------------------------------------------------------------------


def test_range_wins_over_partial_dates():
    results = _detect("Jul 5 - Dec 5")
    types = [r["type"] for r in results]
    assert DataPointType.DATE not in types, (
        f"expected no stray DATE, got "
        f"{[(r['type'].value, r['matched']) for r in results]}"
    )
    assert len(results) == 1
    assert results[0]["type"] == DataPointType.DATE_RANGE
    print("  ✓  overlap: Jul 5 - Dec 5 collapses to one DATE_RANGE")


# ---------------------------------------------------------------------------
# Group G — Sentence integration
# ---------------------------------------------------------------------------


def test_range_in_sentence():
    text = "Festival runs Jul 5 - Dec 5 each year."
    _assert_single(text, DataPointType.DATE_RANGE, "Jul 5 - Dec 5", 14, 27)
    print("  ✓  sentence: embedded Jul 5 - Dec 5 → DATE_RANGE")


def test_range_value_shape_no_year():
    results = _detect("Jul 5 - Dec 5")
    assert len(results) == 1
    v = results[0]["value"]
    assert v["has_year"] is False
    assert v["start"] == {"month": 7, "day": 5, "has_year": False}
    assert v["end"] == {"month": 12, "day": 5, "has_year": False}
    print("  ✓  value: no-year range yields month/day endpoints")


def test_range_value_shape_with_year():
    results = _detect("Jul 5, 2025 - Dec 5, 2025")
    assert len(results) == 1
    v = results[0]["value"]
    assert v["has_year"] is True
    assert v["start"]["datetime"].year == 2025
    assert v["start"]["datetime"].month == 7
    assert v["start"]["datetime"].day == 5
    assert v["end"]["datetime"].year == 2025
    assert v["end"]["datetime"].month == 12
    assert v["end"]["datetime"].day == 5
    print("  ✓  value: with-year range yields datetime endpoints")


# ---------------------------------------------------------------------------
# Group H — Day-first full dates: 20 May 2017, 20th May 2017, 5 Jan 2024
# ---------------------------------------------------------------------------


def test_day_first_long_month():
    _assert_single("20 May 2017", DataPointType.DATE, "20 May 2017", 0, 11)
    print("  ✓  day-first: 20 May 2017 → DATE")


def test_day_first_ordinal():
    _assert_single("20th May 2017", DataPointType.DATE, "20th May 2017", 0, 13)
    print("  ✓  day-first: 20th May 2017 → DATE")


def test_day_first_short_month():
    _assert_single("5 Jan 2024", DataPointType.DATE, "5 Jan 2024", 0, 10)
    print("  ✓  day-first: 5 Jan 2024 → DATE")


def test_day_first_in_sentence():
    text = "Released 20 May 2017 worldwide"
    _assert_single(text, DataPointType.DATE, "20 May 2017", 9, 20)
    print("  ✓  day-first: embedded 20 May 2017 → DATE")


def test_day_first_value_shape():
    results = _detect("20 May 2017")
    assert len(results) == 1
    v = results[0]["value"]
    assert v["has_year"] is True
    assert v["subtype"] == "full"
    assert v["datetime"].year == 2017
    assert v["datetime"].month == 5
    assert v["datetime"].day == 20
    print("  ✓  day-first: value yields datetime(2017, 5, 20)")


# ---------------------------------------------------------------------------
# Group I — Month+year (no day): May 2017, 2017-05, 05/2017
# ---------------------------------------------------------------------------


def test_month_year_name():
    _assert_single("May 2017", DataPointType.DATE, "May 2017", 0, 8)
    print("  ✓  month-year: May 2017 → DATE")


def test_month_year_name_comma():
    _assert_single("May, 2017", DataPointType.DATE, "May, 2017", 0, 9)
    print("  ✓  month-year: May, 2017 → DATE")


def test_month_year_iso():
    _assert_single("2017-05", DataPointType.DATE, "2017-05", 0, 7)
    print("  ✓  month-year: 2017-05 → DATE")


def test_month_year_numeric():
    _assert_single("05/2017", DataPointType.DATE, "05/2017", 0, 7)
    print("  ✓  month-year: 05/2017 → DATE (beats RATIO)")


def test_month_year_value_shape():
    results = _detect("May 2017")
    assert len(results) == 1
    v = results[0]["value"]
    assert v == {"month": 5, "year": 2017, "subtype": "month_year", "has_year": True}, v
    print("  ✓  month-year: value shape {month,year,has_year}")


# ---------------------------------------------------------------------------
# Group J — Full dates, extra month-name orderings
# ---------------------------------------------------------------------------


def test_month_first_ordinal_comma():
    _assert_single("May 20th, 2017", DataPointType.DATE, "May 20th, 2017", 0, 14)
    print("  ✓  full: May 20th, 2017 → DATE")


def test_day_first_comma():
    _assert_single("20 May, 2017", DataPointType.DATE, "20 May, 2017", 0, 12)
    print("  ✓  full: 20 May, 2017 → DATE")


def test_month_first_no_comma():
    _assert_single("May 20 2017", DataPointType.DATE, "May 20 2017", 0, 11)
    print("  ✓  full: May 20 2017 → DATE")


def test_day_of_month_year():
    _assert_single("20th of May 2017", DataPointType.DATE, "20th of May 2017", 0, 16)
    print("  ✓  full: 20th of May 2017 → DATE")


def test_dotted_short_year():
    _assert_single("20.05.17", DataPointType.DATE, "20.05.17", 0, 8)
    print("  ✓  full: 20.05.17 → DATE (beats VERSION)")


def test_full_date_value_shape():
    results = _detect("May 20th, 2017")
    assert len(results) == 1
    v = results[0]["value"]
    assert v["has_year"] is True and v["subtype"] == "full"
    assert v["datetime"].year == 2017
    assert v["datetime"].month == 5
    assert v["datetime"].day == 20
    print("  ✓  full: value yields datetime(2017, 5, 20)")


# ---------------------------------------------------------------------------
# Group K — Regression & fall-through guards
# ---------------------------------------------------------------------------


def test_day_first_still_single():
    # month-year (May 2017) overlaps the inner span but the longer day-first
    # span must still collapse to one DATE.
    results = _detect("20 May 2017")
    assert len(results) == 1
    assert results[0]["type"] == DataPointType.DATE
    assert results[0]["matched"] == "20 May 2017"
    print("  ✓  regression: 20 May 2017 stays one DATE")


def test_invalid_month_year_not_date():
    # Invalid month → not a date; falls through to RATIO.
    types = {r["type"] for r in _detect("13/2017")}
    assert DataPointType.DATE not in types, types
    print("  ✓  guard: 13/2017 is not a DATE")


def test_invalid_dotted_not_date():
    # Invalid day/month → not a date; falls through to VERSION.
    types = {r["type"] for r in _detect("20.99.17")}
    assert DataPointType.DATE not in types, types
    print("  ✓  guard: 20.99.17 is not a DATE")


def test_full_numeric_dates_unaffected():
    _assert_single("05/20/2017", DataPointType.DATE, "05/20/2017", 0, 10)
    _assert_single("20.05.2017", DataPointType.DATE, "20.05.2017", 0, 10)
    print("  ✓  guard: MM/DD/YYYY and DD.MM.YYYY unaffected")


TESTS = [
    # Group A
    test_baseline_long_month_with_year,
    test_baseline_short_month_with_year,
    # Group B
    test_short_month_no_year_cross_month,
    test_short_month_no_year_same_month,
    # Group C
    test_long_month_no_year_cross_month,
    # Group D
    test_short_month_with_year_both_sides,
    test_long_month_with_year_both_sides,
    # Group E
    test_en_dash_separator,
    test_em_dash_separator,
    # Group F
    test_range_wins_over_partial_dates,
    # Group G
    test_range_in_sentence,
    test_range_value_shape_no_year,
    test_range_value_shape_with_year,
    # Group H
    test_day_first_long_month,
    test_day_first_ordinal,
    test_day_first_short_month,
    test_day_first_in_sentence,
    test_day_first_value_shape,
    # Group I
    test_month_year_name,
    test_month_year_name_comma,
    test_month_year_iso,
    test_month_year_numeric,
    test_month_year_value_shape,
    # Group J
    test_month_first_ordinal_comma,
    test_day_first_comma,
    test_month_first_no_comma,
    test_day_of_month_year,
    test_dotted_short_year,
    test_full_date_value_shape,
    # Group K
    test_day_first_still_single,
    test_invalid_month_year_not_date,
    test_invalid_dotted_not_date,
    test_full_numeric_dates_unaffected,
]


if __name__ == "__main__":
    print("DataPointDetector — DATE_RANGE detection tests")
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
