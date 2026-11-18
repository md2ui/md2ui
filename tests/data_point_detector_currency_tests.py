"""
Regression tests for DataPointDetector around currency / number with commas.

Prices like ``$19,357.5`` parse as CURRENCY (not NUMBER ``19,357.5`` without
the ``$``), and ``$19,357.500`` / ``$19,357.123`` keep every decimal.

Run with: uv run python tests/data_point_detector_currency_tests.py
"""

from md2ui.pipeline.data_point_detector import DataPointDetector, DataPointType
from md2ui.pipeline.markdown_grouper import MarkdownGrouper, NodeType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _find_nodes(node, label):
    out = []
    if node.type == label:
        out.append(node)
    for c in node.children:
        out.extend(_find_nodes(c, label))
    return out


def _processed(text: str):
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    return g.ast


# ---------------------------------------------------------------------------
# Group A — Baseline
# ---------------------------------------------------------------------------


def test_baseline_dollar_thousands():
    _assert_single("$19,357", DataPointType.CURRENCY, "$19,357", 0, 7)
    print("  ✓  baseline: $19,357 → CURRENCY $19,357")


def test_baseline_dollar_small_thousands():
    _assert_single("$1,234", DataPointType.CURRENCY, "$1,234", 0, 6)
    print("  ✓  baseline: $1,234 → CURRENCY $1,234")


def test_baseline_dollar_two_decimals():
    _assert_single("$1,234.56", DataPointType.CURRENCY, "$1,234.56", 0, 9)
    print("  ✓  baseline: $1,234.56 → CURRENCY $1,234.56")


def test_baseline_dollar_million_two_decimals():
    _assert_single("$1,234,567.89", DataPointType.CURRENCY, "$1,234,567.89", 0, 13)
    print("  ✓  baseline: $1,234,567.89 → CURRENCY $1,234,567.89")


# ---------------------------------------------------------------------------
# Group B — Decimals
# ---------------------------------------------------------------------------


def test_dollar_one_decimal_keeps_dollar_sign():
    # Full CURRENCY, not NUMBER "19,357.5" without the $.
    _assert_single("$19,357.5", DataPointType.CURRENCY, "$19,357.5", 0, 9)
    print("  ✓  fix: $19,357.5 → CURRENCY $19,357.5 (was NUMBER)")


def test_dollar_three_decimals_no_truncation():
    # Full string, not truncated to "$19,357.50".
    _assert_single("$19,357.500", DataPointType.CURRENCY, "$19,357.500", 0, 11)
    print("  ✓  fix: $19,357.500 → CURRENCY $19,357.500 (was $19,357.50)")


def test_dollar_three_decimals_distinct():
    # Full string, not truncated to "$19,357.12".
    _assert_single("$19,357.123", DataPointType.CURRENCY, "$19,357.123", 0, 11)
    print("  ✓  fix: $19,357.123 → CURRENCY $19,357.123 (was $19,357.12)")


def test_dollar_long_multi_grouping_with_long_decimals():
    _assert_single(
        "$1,234,567,890.12345", DataPointType.CURRENCY, "$1,234,567,890.12345", 0, 20
    )
    print("  ✓  fix: $1,234,567,890.12345 → full CURRENCY")


# ---------------------------------------------------------------------------
# Group C — Other currency symbols same shape
# ---------------------------------------------------------------------------


def test_pound_one_decimal():
    _assert_single("£19,357.5", DataPointType.CURRENCY, "£19,357.5", 0, 9)
    print("  ✓  fix: £19,357.5 → CURRENCY £19,357.5")


def test_pound_two_decimals_million():
    _assert_single("£1,234,567.89", DataPointType.CURRENCY, "£1,234,567.89", 0, 13)
    print("  ✓  baseline: £1,234,567.89 → CURRENCY £1,234,567.89")


# ---------------------------------------------------------------------------
# Group D — ISO codes (suffix and prefix)
# ---------------------------------------------------------------------------


def test_iso_suffix_three_decimals():
    _assert_single("1,234.567 MXN", DataPointType.CURRENCY, "1,234.567 MXN", 0, 13)
    print("  ✓  fix: 1,234.567 MXN → CURRENCY 1,234.567 MXN")


def test_iso_prefix_one_decimal():
    _assert_single("MXN 1,234.5", DataPointType.CURRENCY, "MXN 1,234.5", 0, 11)
    print("  ✓  fix: MXN 1,234.5 → CURRENCY MXN 1,234.5 (was 'MXN 1,234' + NUMBER 5)")


def test_iso_prefix_two_decimals():
    _assert_single("USD 19,357.99", DataPointType.CURRENCY, "USD 19,357.99", 0, 13)
    print("  ✓  baseline: USD 19,357.99 → CURRENCY USD 19,357.99")


# ---------------------------------------------------------------------------
# Group E — NUMBER vs CURRENCY overlap (negative lookbehind)
# ---------------------------------------------------------------------------


def test_dollar_no_number_overlap_integer():
    # Only CURRENCY — NUMBER must not also match the digits inside.
    results = _detect("$19,357")
    types = [r["type"] for r in results]
    assert DataPointType.NUMBER not in types, (
        f"NUMBER must not match inside $19,357, got {[(r['type'].value, r['matched']) for r in results]}"
    )
    assert DataPointType.CURRENCY in types
    print("  ✓  overlap: $19,357 yields no spurious NUMBER")


def test_dollar_no_number_overlap_with_decimals():
    results = _detect("$1,234,567.89")
    types = [r["type"] for r in results]
    assert DataPointType.NUMBER not in types, (
        f"NUMBER must not match inside $1,234,567.89, got {[(r['type'].value, r['matched']) for r in results]}"
    )
    print("  ✓  overlap: $1,234,567.89 yields no spurious NUMBER")


def test_pound_no_number_overlap():
    results = _detect("£1,234,567.89")
    types = [r["type"] for r in results]
    assert DataPointType.NUMBER not in types, (
        f"NUMBER must not match inside £1,234,567.89, got {[(r['type'].value, r['matched']) for r in results]}"
    )
    print("  ✓  overlap: £1,234,567.89 yields no spurious NUMBER")


def test_bare_number_still_detected_integer():
    _assert_single("19,357", DataPointType.NUMBER, "19,357", 0, 6)
    print("  ✓  non-regression: bare 19,357 still NUMBER")


def test_bare_number_still_detected_decimal():
    _assert_single("19,357.5", DataPointType.NUMBER, "19,357.5", 0, 8)
    print("  ✓  non-regression: bare 19,357.5 still NUMBER (decimal)")


# ---------------------------------------------------------------------------
# Group F — Mixed sentence: detector must recover both types
# ---------------------------------------------------------------------------


def test_mixed_number_and_currency_in_sentence():
    text = "Buy 5,000 widgets for $19,357.99"
    results = _detect(text)
    # Expect exactly one NUMBER and one CURRENCY, in order.
    pairs = [(r["type"], r["matched"]) for r in results]
    assert (DataPointType.NUMBER, "5,000") in pairs, pairs
    assert (DataPointType.CURRENCY, "$19,357.99") in pairs, pairs
    assert len(results) == 2, pairs
    print("  ✓  mixed: NUMBER 5,000 + CURRENCY $19,357.99")


def test_mixed_one_decimal_currency_in_sentence():
    text = "Buy 5,000 widgets for $19,357.5"
    results = _detect(text)
    pairs = [(r["type"], r["matched"]) for r in results]
    assert (DataPointType.NUMBER, "5,000") in pairs, pairs
    assert (DataPointType.CURRENCY, "$19,357.5") in pairs, pairs
    print("  ✓  mixed: NUMBER 5,000 + CURRENCY $19,357.5 (1 decimal)")


# ---------------------------------------------------------------------------
# Group G — Comma-list of prices (integration via MarkdownGrouper)
# ---------------------------------------------------------------------------


def test_comma_list_of_prices_keeps_each_intact():
    text = "Sales: $1,234, $5,678, $9,000"
    results = _detect(text)
    matched = [(r["type"], r["matched"]) for r in results]
    assert (DataPointType.CURRENCY, "$1,234") in matched, matched
    assert (DataPointType.CURRENCY, "$5,678") in matched, matched
    assert (DataPointType.CURRENCY, "$9,000") in matched, matched
    print("  ✓  comma-list: 3 CURRENCY data_points, no $ orphaning")


def _price_line(line: str, price: str) -> None:
    """*line* stays one text (ADR-205) whose one data point is *price*, whole,
    at the offset it was written."""
    (leaf,) = [
        n for n in _find_nodes(_processed(line), NodeType.TEXT) if not n.children
    ]
    assert leaf.content == line, leaf.content
    (dp,) = leaf.data_points
    assert dp["type"] == DataPointType.CURRENCY, dp
    assert dp["matched"] == price, f"{dp['matched']!r} != {price!r}"
    assert line[dp["start"] : dp["end"]] == price, (dp["start"], dp["end"])


def test_kv_currency_round_trip_through_grouper():
    # Top-level integration: the reported symptom shape ("Price: $19,357").
    _price_line("Price: $19,357", "$19,357")
    print("  ✓  integration: Price: $19,357 → one TEXT, the currency intact")


def test_kv_currency_one_decimal_round_trip():
    # The $ must not be split off, and the decimal must be preserved.
    _price_line("Price: $19,357.5", "$19,357.5")
    print("  ✓  integration: Price: $19,357.5 → annotated TEXT intact")


def test_grouper_keeps_each_currency_value_intact():
    for text in ("$19,357", "$19,357.5", "$19,357.50", "$19,357.123", "$1,234,567.89"):
        ast = _processed(text)
        leaves = [n for n in _find_nodes(ast, NodeType.TEXT) if not n.children]
        assert [leaf.content for leaf in leaves] == [text], (
            text,
            [leaf.content for leaf in leaves],
        )
        assert leaves[0].data_points[0]["type"] == DataPointType.CURRENCY
    print("  ✓  integration: currency values keep every thousands comma")


# ---------------------------------------------------------------------------
# Group H — Long / multi-grouping currencies
# ---------------------------------------------------------------------------


def test_million_round():
    _assert_single("$1,000,000", DataPointType.CURRENCY, "$1,000,000", 0, 10)
    print("  ✓  baseline: $1,000,000 → CURRENCY $1,000,000")


def test_billion_no_decimals():
    _assert_single("$1,234,567,890", DataPointType.CURRENCY, "$1,234,567,890", 0, 14)
    print("  ✓  baseline: $1,234,567,890 → CURRENCY $1,234,567,890")


# ---------------------------------------------------------------------------
# Group I — Approximate / sign prefixes (must still hand off correctly)
# ---------------------------------------------------------------------------


def test_negative_currency_change_still_detected():
    # `-$19,357` is read as CHANGE — the comma inside the number must be
    # inside the matched span.
    results = _detect("-$19,357")
    assert results, "expected at least one match"
    # Whatever type it is, the matched span must cover the comma.
    spans = [(r["start"], r["end"], r["matched"]) for r in results]
    covers_comma = any(s <= 4 < e for s, e, _ in spans)
    assert covers_comma, f"-$19,357: no match covers the comma at index 4, got {spans}"
    print("  ✓  -$19,357: comma in number is inside a protected match")


# ---------------------------------------------------------------------------
# Group J — QUANTITY / overlap with currency
# ---------------------------------------------------------------------------


def test_isolated_one_input_two_currencies():
    # Mirrors data/markdown/tests/test-isolated-1.md verbatim.
    text = "~~$22,540~~ $19,357 month"
    results = _detect(text)
    pairs = [(r["type"], r["matched"]) for r in results]
    assert (DataPointType.CURRENCY, "$22,540") in pairs, pairs
    assert (DataPointType.CURRENCY, "$19,357") in pairs, pairs
    # No QUANTITY anywhere — the digits in $19,357 must not be sniped.
    assert not any(t == DataPointType.QUANTITY for t, _ in pairs), pairs
    print("  ✓  isolated-1: 2× CURRENCY, no spurious QUANTITY")


def test_trailing_symbol_dual_dollar_euro():
    # "$2.36 €": dual symbol; trailing € decides currency → EUR 2.36.
    _assert_single("$2.36 €", DataPointType.CURRENCY, "$2.36 €", 0, 7)
    r = _detect("$2.36 €")[0]
    assert r["value"]["currency"] == "EUR", r["value"]
    assert str(r["value"]["amount"]) == "2.36", r["value"]
    print("  ✓  trailing symbol: '$2.36 €' → CURRENCY EUR 2.36")


def test_trailing_symbol_european_decimal():
    # "2,36 €": European comma-decimal, trailing symbol → EUR 2.36 (whole span).
    _assert_single("2,36 €", DataPointType.CURRENCY, "2,36 €", 0, 6)
    r = _detect("2,36 €")[0]
    assert r["value"]["currency"] == "EUR", r["value"]
    assert str(r["value"]["amount"]) == "2.36", r["value"]
    print("  ✓  trailing symbol: '2,36 €' → CURRENCY EUR 2.36")


def test_trailing_symbol_dotted_date_is_not_an_amount():
    # "25.12.2021 €": three dot groups cannot be an amount, so the trailing
    # symbol claims nothing; the date reads as itself and the € stays text.
    _assert_single("25.12.2021 €", DataPointType.DATE, "25.12.2021", 0, 10)
    print("  ✓  trailing symbol: '25.12.2021 €' → DATE only, € stays text")


def test_trailing_symbol_dotted_version_is_not_an_amount():
    _assert_single("1.2.3 €", DataPointType.VERSION, "1.2.3", 0, 5)
    print("  ✓  trailing symbol: '1.2.3 €' → VERSION only, € stays text")


def test_trailing_symbol_dot_thousands():
    # Repeated dots that each group three digits are European thousands.
    _assert_single("1.234.567 €", DataPointType.CURRENCY, "1.234.567 €", 0, 11)
    r = _detect("1.234.567 €")[0]
    assert str(r["value"]["amount"]) == "1234567", r["value"]
    print("  ✓  trailing symbol: '1.234.567 €' → CURRENCY EUR 1234567")


def test_trailing_symbol_dotted_non_amount_groups():
    # The grouper reaches the detector on every leaf: such a line must group.
    for text in ("Price: 25.12.2021 €", "Build 1.2.3 €"):
        _processed(text)
    print("  ✓  integration: dotted non-amounts before € group without error")


def test_line20_grouper_styled_currency_round_trip():
    # The test-isolated-1.md / tests-text-styles.md line 20:
    # the unseparated run stays one text leaf; both exact spans remain annotated.
    g = _processed("**$2.36 €** ~~$3.59 €~~")
    leaves = []

    def _walk(n):
        if not n.children and n.content:
            leaves.append(n.content)
        for ch in n.children:
            _walk(ch)

    _walk(g)
    assert leaves == ["**$2.36 €** ~~$3.59 €~~"], leaves
    leaf = next(n for n in _find_nodes(g, NodeType.TEXT) if not n.children)
    assert [dp["matched"] for dp in leaf.data_points] == ["$2.36 €", "$3.59 €"]
    assert [(dp["start"], dp["end"]) for dp in leaf.data_points] == [(2, 9), (14, 21)]
    print("  ✓  line 20: both styled currencies stay annotated in one intact leaf")


def test_quantity_with_thousands_units():
    # QUANTITY '5,000 units' with value=5000, not '000 units'.
    results = _detect("5,000 units sold")
    qs = [r for r in results if r["type"] == DataPointType.QUANTITY]
    assert qs, (
        f"expected a QUANTITY match, got {[(r['type'].value, r['matched']) for r in results]}"
    )
    assert qs[0]["matched"] == "5,000 units", qs[0]["matched"]
    val = qs[0]["value"]
    # _parse_quantity returns {"value": Decimal, "unit": str}
    assert val["unit"] == "units", val
    assert int(val["value"]) == 5000, val
    print("  ✓  quantity: '5,000 units sold' → QUANTITY '5,000 units' value=5000")


def test_quantity_with_thousands_kg():
    results = _detect("1,000 kg of stuff")
    qs = [r for r in results if r["type"] == DataPointType.QUANTITY]
    assert qs, (
        f"expected QUANTITY, got {[(r['type'].value, r['matched']) for r in results]}"
    )
    assert qs[0]["matched"] == "1,000 kg", qs[0]["matched"]
    val = qs[0]["value"]
    assert val["unit"] == "kg", val
    assert int(val["value"]) == 1000, val
    print("  ✓  quantity: '1,000 kg of stuff' → QUANTITY '1,000 kg' value=1000")


def test_quantity_inside_currency_not_matched():
    # $19,357 month yields ONE match (CURRENCY)
    # — the trailing "month" must not pull '357' into a QUANTITY.
    results = _detect("$19,357 month")
    pairs = [(r["type"], r["matched"]) for r in results]
    assert (DataPointType.CURRENCY, "$19,357") in pairs, pairs
    assert not any(t == DataPointType.QUANTITY for t, _ in pairs), pairs
    print("  ✓  overlap: '$19,357 month' → CURRENCY only, no QUANTITY '357 month'")


def test_quantity_inside_currency_with_decimal_not_matched():
    # Decimal-tail variant: '$19,357.5 month' — the '5' must not start a
    # QUANTITY just because '5 month' looks like one.
    results = _detect("$19,357.5 month")
    pairs = [(r["type"], r["matched"]) for r in results]
    assert (DataPointType.CURRENCY, "$19,357.5") in pairs, pairs
    assert not any(t == DataPointType.QUANTITY for t, _ in pairs), pairs
    print(
        "  ✓  overlap: '$19,357.5 month' → CURRENCY only, no QUANTITY at decimal tail"
    )


def test_magnitude_thousands_grouping():
    # '5,000 million users' — magnitude word should match the whole '5,000 million'.
    results = _detect("5,000 million users")
    qs = [r for r in results if r["type"] == DataPointType.QUANTITY]
    assert qs, (
        f"expected QUANTITY/MAGNITUDE, got {[(r['type'].value, r['matched']) for r in results]}"
    )
    matches = [q["matched"] for q in qs]
    assert "5,000 million" in matches, matches
    print("  ✓  magnitude: '5,000 million users' → QUANTITY '5,000 million'")


def test_quantity_simple_units_unchanged():
    # The lookbehind must not over-block legitimate simple cases.
    cases = [
        ("5 days", "5 days", "days", 5),
        ("100 kg", "100 kg", "kg", 100),
        ("2 hours", "2 hours", "hours", 2),
    ]
    for text, expected_match, expected_unit, expected_value in cases:
        results = _detect(text)
        qs = [r for r in results if r["type"] == DataPointType.QUANTITY]
        assert qs, f"{text!r}: expected QUANTITY"
        assert qs[0]["matched"] == expected_match, (text, qs[0]["matched"])
        val = qs[0]["value"]
        assert val["unit"] == expected_unit, (text, val)
        assert int(val["value"]) == expected_value, (text, val)
    print("  ✓  quantity: simple cases ('5 days', '100 kg', '2 hours') still work")


def test_explicit_rate_still_works():
    # The slash and 'per' rate forms must not regress.
    for text, expected in (
        ("$50/hour", "$50/hour"),
        ("50 per hour", "50 per hour"),
    ):
        results = _detect(text)
        rates = [r for r in results if r["type"] == DataPointType.RATE]
        assert rates, (
            f"{text!r}: expected RATE, got {[(r['type'].value, r['matched']) for r in results]}"
        )
        assert any(r["matched"] == expected for r in rates), (text, rates)
    print("  ✓  rate: '$50/hour' and '50 per hour' still RATE")


def test_price_per_person_is_rate():
    # '$659/person' must be a single price-per-person RATE (not a bare $659
    # CURRENCY with a loose '/person'). Mirrors the '$X/oz' commodity handling.
    for text in ("$659/person", "from $659/person"):
        results = _detect(text)
        rates = [r for r in results if r["type"] == DataPointType.RATE]
        assert rates, (
            f"{text!r}: expected RATE, got "
            f"{[(r['type'].value, r['matched']) for r in results]}"
        )
        r = rates[0]
        assert r["matched"] == "$659/person", (text, r["matched"])
        assert r["value"]["per"] == "person", (text, r["value"])
        assert r["value"]["rate_type"] == "price", (text, r["value"])
        # the bare $659 CURRENCY must not survive alongside the RATE
        assert not any(x["type"] == DataPointType.CURRENCY for x in results), (
            text,
            [(x["type"].value, x["matched"]) for x in results],
        )
    print("  ✓  rate: '$659/person' → price-per-person RATE (per='person')")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


TESTS = [
    # Group A — baseline
    test_baseline_dollar_thousands,
    test_baseline_dollar_small_thousands,
    test_baseline_dollar_two_decimals,
    test_baseline_dollar_million_two_decimals,
    # Group B — decimals
    test_dollar_one_decimal_keeps_dollar_sign,
    test_dollar_three_decimals_no_truncation,
    test_dollar_three_decimals_distinct,
    test_dollar_long_multi_grouping_with_long_decimals,
    # Group C — other symbols
    test_pound_one_decimal,
    test_pound_two_decimals_million,
    # Group D — ISO codes
    test_iso_suffix_three_decimals,
    test_iso_prefix_one_decimal,
    test_iso_prefix_two_decimals,
    # Group E — NUMBER vs CURRENCY overlap
    test_dollar_no_number_overlap_integer,
    test_dollar_no_number_overlap_with_decimals,
    test_pound_no_number_overlap,
    test_bare_number_still_detected_integer,
    test_bare_number_still_detected_decimal,
    # Group F — mixed sentences
    test_mixed_number_and_currency_in_sentence,
    test_mixed_one_decimal_currency_in_sentence,
    # Group G — comma-list integration
    test_comma_list_of_prices_keeps_each_intact,
    test_kv_currency_round_trip_through_grouper,
    test_kv_currency_one_decimal_round_trip,
    test_grouper_keeps_each_currency_value_intact,
    # Group H — multi-grouping
    test_million_round,
    test_billion_no_decimals,
    # Group I — sign prefixes
    test_negative_currency_change_still_detected,
    # Group J — QUANTITY / overlap with currency
    test_isolated_one_input_two_currencies,
    test_trailing_symbol_dual_dollar_euro,
    test_trailing_symbol_european_decimal,
    test_trailing_symbol_dotted_date_is_not_an_amount,
    test_trailing_symbol_dotted_version_is_not_an_amount,
    test_trailing_symbol_dot_thousands,
    test_trailing_symbol_dotted_non_amount_groups,
    test_line20_grouper_styled_currency_round_trip,
    test_quantity_with_thousands_units,
    test_quantity_with_thousands_kg,
    test_quantity_inside_currency_not_matched,
    test_quantity_inside_currency_with_decimal_not_matched,
    test_magnitude_thousands_grouping,
    test_quantity_simple_units_unchanged,
    test_explicit_rate_still_works,
    test_price_per_person_is_rate,
]


if __name__ == "__main__":
    print("DataPointDetector — currency / comma regression tests")
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
