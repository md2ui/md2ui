"""
Regression tests for DataPointDetector combined DATE+TIME ("datetime") detection.

A timestamp is ONE datapoint, not a date beside a time. Matching it whole keeps
its type, value and display treatment together; the comma is punctuation and
does not divide the line.

Covers both spellings — the ``at`` form and the comma form — plus the
near-misses that must stay two things.

Run with: uv run python tests/data_point_detector_datetime_tests.py
"""

from md2ui.pipeline.data_point_detector import DataPointDetector, DataPointType
from md2ui.pipeline.markdown_grouper import MarkdownGrouper


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
# Group A — the comma spelling, no year
# ---------------------------------------------------------------------------


def test_comma_long_month_no_year():
    _assert_single(
        "February 04, 9:17 PM", DataPointType.DATE, "February 04, 9:17 PM", 0, 20
    )
    print("  ✓  February 04, 9:17 PM → one DATE")


def test_comma_short_month_no_year():
    _assert_single("Feb 4, 9:17 PM", DataPointType.DATE, "Feb 4, 9:17 PM")
    print("  ✓  Feb 4, 9:17 PM → one DATE")


def test_comma_without_a_space():
    """The tight punctuation spelling resolves to the same timestamp."""
    _assert_single("February 04,9:17 PM", DataPointType.DATE, "February 04,9:17 PM")
    print("  ✓  February 04,9:17 PM (no space) → one DATE")


def test_comma_bare_hour_with_meridiem():
    _assert_single("March 5, 3 PM", DataPointType.DATE, "March 5, 3 PM")
    print("  ✓  March 5, 3 PM → one DATE")


# ---------------------------------------------------------------------------
# Group B — the comma spelling, with a year
# ---------------------------------------------------------------------------


def test_comma_with_year():
    _assert_single("Feb 28, 2020, 7:00 pm", DataPointType.DATE, "Feb 28, 2020, 7:00 pm")
    print("  ✓  Feb 28, 2020, 7:00 pm → one DATE")


def test_a_trailing_timezone_stays_outside():
    """The span ends at the time; `EST` is not part of the datetime pattern."""
    r = _detect("February 4, 2026, 4:00 PM EST")
    assert len(r) == 1, r
    assert r[0]["matched"] == "February 4, 2026, 4:00 PM", r[0]["matched"]
    print("  ✓  a trailing timezone is left outside the span")


# ---------------------------------------------------------------------------
# Group C — value shapes
# ---------------------------------------------------------------------------


def test_value_shape_no_year():
    """Degrades to month/day the way _parse_date_range_endpoint does, because
    _combine_date_time needs a real date and hardcodes has_year."""
    v = _assert_single(
        "February 04, 9:17 PM", DataPointType.DATE, "February 04, 9:17 PM"
    )["value"]
    assert v["subtype"] == "datetime", v
    assert v["has_year"] is False, v
    assert (v["month"], v["day"]) == (2, 4), v
    assert (v["hour"], v["minute"]) == (21, 17), v  # PM → 24h
    print("  ✓  no-year value: month/day + 24h hour/minute")


def test_value_shape_with_year():
    v = _assert_single(
        "Feb 28, 2020, 7:00 pm", DataPointType.DATE, "Feb 28, 2020, 7:00 pm"
    )["value"]
    assert v["subtype"] == "datetime", v
    assert v["has_year"] is True, v
    assert v["datetime"].year == 2020 and v["datetime"].hour == 19, v
    print("  ✓  with-year value: a real datetime")


def test_a_bare_hour_gets_minute_zero():
    v = _assert_single("March 5, 3 PM", DataPointType.DATE, "March 5, 3 PM")["value"]
    assert (v["hour"], v["minute"]) == (15, 0), v
    print("  ✓  a bare hour gets minute 0")


def test_a_bare_hour_with_a_year_gets_minute_zero():
    """With a year the comma spelling builds a real datetime; a bare hour must
    read as minute 0 there too, not stop the document from grouping."""
    v = _assert_single(
        "February 4, 2026, 3 PM", DataPointType.DATE, "February 4, 2026, 3 PM"
    )["value"]
    assert (v["hour"], v["minute"], v["has_year"]) == (15, 0, True), v
    print("  ✓  a bare hour with a year gets minute 0")


def test_a_bare_hour_with_a_year_groups():
    """The same line through the grouper, the way a document reaches it."""
    g = MarkdownGrouper("Meeting: February 4, 2026, 3 PM")
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    print("  ✓  'Meeting: February 4, 2026, 3 PM' groups")


def test_the_subtype_keeps_it_off_the_date_chip():
    """The chip gate wants subtype partial/weekday_day. A chip reading
    "FEBRUARY / 04" while the time renders elsewhere is the split this pattern
    exists to prevent, so the subtype must not be 'partial'."""
    v = _assert_single(
        "February 04, 9:17 PM", DataPointType.DATE, "February 04, 9:17 PM"
    )["value"]
    assert v["subtype"] not in ("partial", "weekday_day"), v
    print("  ✓  subtype 'datetime' keeps it off the date-chip path")


# ---------------------------------------------------------------------------
# Group D — the `at` spelling
# ---------------------------------------------------------------------------


def test_at_spelling_long_month():
    _assert_single(
        "February 3, 2026 at 4:45 PM", DataPointType.DATE, "February 3, 2026 at 4:45 PM"
    )
    print("  ✓  February 3, 2026 at 4:45 PM → one DATE")


def test_at_spelling_short_month():
    _assert_single(
        "Feb 3, 2026 at 4:45 PM", DataPointType.DATE, "Feb 3, 2026 at 4:45 PM"
    )
    print("  ✓  Feb 3, 2026 at 4:45 PM → one DATE")


def test_at_spelling_iso():
    _assert_single("2024-01-15 at 14:30", DataPointType.DATE, "2024-01-15 at 14:30")
    print("  ✓  2024-01-15 at 14:30 → one DATE")


# ---------------------------------------------------------------------------
# Group E — what must stay TWO things (or none)
# ---------------------------------------------------------------------------


def test_a_date_alone_is_unchanged():
    _assert_single("February 04, 2026", DataPointType.DATE, "February 04, 2026")
    _assert_single("Jun 15", DataPointType.DATE, "Jun 15")
    _assert_single("9:17 PM", DataPointType.TIME, "9:17 PM")
    print("  ✓  a bare date / bare time is untouched")


def test_a_quantity_after_a_date_is_not_a_time():
    """The bare-hour branch requires AM/PM, or `March 5, 10 people` would read
    as a timestamp instead of a date beside a count."""
    for text in ("March 5, 10 people", "Aug 14, 2 items"):
        kinds = [r["type"] for r in _detect(text)]
        assert DataPointType.QUANTITY in kinds, (text, kinds)
        assert len(_detect(text)) == 2, (text, _detect(text))
    print("  ✓  a quantity after a date stays a separate datapoint")


def test_a_date_range_keeps_its_two_endpoints_apart():
    """The range's ` - ` is a real separator and must stay one: the weekday
    pattern joins each endpoint, it does not swallow the range."""
    got = [r["matched"] for r in _detect("Fri, Aug 14 - Sun, Aug 16")]
    assert got == ["Fri, Aug 14", "Sun, Aug 16"], got
    print("  ✓  a weekday/date range keeps its two endpoints apart")


def test_a_comma_list_is_still_a_comma_list():
    assert _detect("One, Two, Three") == []
    print("  ✓  a plain comma list detects nothing")


# ---------------------------------------------------------------------------
# Group F — a weekday introducing a date is one unit too
#
# The split criteria also carry this span (_NON_LIST_COMMA_SPAN in
# pipeline/grouper_split_criteria.py); the detector must agree so the weekday and date share
# one typed value.
# ---------------------------------------------------------------------------


def test_a_weekday_joins_its_date():
    _assert_single("Fri, Aug 14", DataPointType.DATE, "Fri, Aug 14", 0, 11)
    _assert_single("Wednesday, February 5", DataPointType.DATE, "Wednesday, February 5")
    _assert_single("Mon, Jan 5, 2026", DataPointType.DATE, "Mon, Jan 5, 2026")
    print("  ✓  Fri, Aug 14 → one DATE")


def test_a_weekday_does_not_join_another_weekday():
    """`Tuesday, Wednesday` is a list of two days. Requiring a MONTH date on the
    right keeps it from merging into a single bogus date."""
    got = [r["matched"] for r in _detect("Tuesday, Wednesday")]
    assert got == ["Tuesday", "Wednesday"], got
    print("  ✓  Tuesday, Wednesday stays two days")


def test_a_weekday_does_not_join_a_quantity():
    kinds = [r["type"] for r in _detect("Mon, 5 items")]
    assert DataPointType.QUANTITY in kinds, kinds
    assert len(kinds) == 2, kinds
    print("  ✓  Mon, 5 items is a day beside a count")


def test_the_weekday_subtype_keeps_it_off_the_date_chip():
    """A chip built from this span would take `matched.split()[0]` as its key and
    render "FRI," — comma and all — over a day whose month it dropped."""
    v = _assert_single("Fri, Aug 14", DataPointType.DATE, "Fri, Aug 14")["value"]
    assert v["subtype"] == "weekday_date", v
    assert v["subtype"] not in ("partial", "weekday_day"), v
    assert (v["day_name"], v["month"], v["day"]) == ("Fri", 8, 14), v
    assert v["has_year"] is False, v
    print("  ✓  subtype 'weekday_date' keeps it off the date-chip path")


def test_the_bare_weekday_day_chip_is_untouched():
    """`Mon 15` (no comma) is the shape the date chip exists for."""
    v = _assert_single("Mon 15", DataPointType.DATE, "Mon 15")["value"]
    assert v["subtype"] == "weekday_day", v
    print("  ✓  Mon 15 keeps its weekday_day chip")


TESTS = [
    test_comma_long_month_no_year,
    test_comma_short_month_no_year,
    test_comma_without_a_space,
    test_comma_bare_hour_with_meridiem,
    test_comma_with_year,
    test_a_trailing_timezone_stays_outside,
    test_value_shape_no_year,
    test_value_shape_with_year,
    test_a_bare_hour_gets_minute_zero,
    test_a_bare_hour_with_a_year_gets_minute_zero,
    test_a_bare_hour_with_a_year_groups,
    test_the_subtype_keeps_it_off_the_date_chip,
    test_at_spelling_long_month,
    test_at_spelling_short_month,
    test_at_spelling_iso,
    test_a_date_alone_is_unchanged,
    test_a_quantity_after_a_date_is_not_a_time,
    test_a_date_range_keeps_its_two_endpoints_apart,
    test_a_comma_list_is_still_a_comma_list,
    test_a_weekday_joins_its_date,
    test_a_weekday_does_not_join_another_weekday,
    test_a_weekday_does_not_join_a_quantity,
    test_the_weekday_subtype_keeps_it_off_the_date_chip,
    test_the_bare_weekday_day_chip_is_untouched,
]


if __name__ == "__main__":
    print("DataPointDetector — datetime (DATE+TIME) detection tests")
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
