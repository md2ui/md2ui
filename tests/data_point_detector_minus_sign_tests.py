"""A minus is a minus however it is written.

LLMs write the typographic minus U+2212 (``−1.55%``, ``−$120.00``) in finance and
statistics answers. Every signed pattern in the detector accepts it beside the ASCII
hyphen, and reads it as negative: otherwise the pattern matches from the digit and
the value silently turns positive.

A sign written right before an amount, a count or a temperature belongs to it
too: ``-€200`` is a change of -200 EUR as
``-$200`` is of -200 USD, ``-$5K`` keeps its thousands, and ``-5°C`` is a
temperature of -5. A hyphen after a word or digit is not a sign (``10-20``).

Run with: uv run python tests/data_point_detector_minus_sign_tests.py
"""

from decimal import Decimal

from md2ui.pipeline.data_point_detector import DataPointDetector, DataPointType
from md2ui.pipeline.detector_signs import take_sign


def _only(text: str):
    results = DataPointDetector().detect_all(text)
    assert len(results) == 1, (
        f"{text!r}: expected 1 match, got "
        f"{[(r['type'].value, r['matched']) for r in results]}"
    )
    return results[0]


def _assert_negative(text: str, dp_type: DataPointType, amount: str):
    r = _only(text)
    assert r["type"] == dp_type, f"{text!r}: got {r['type'].value}"
    assert r["matched"].startswith("−"), f"{text!r}: sign left out of {r['matched']!r}"
    value = r["value"]["value"] if isinstance(r["value"], dict) else r["value"]
    assert Decimal(str(value)) == Decimal(amount), f"{text!r}: value {value!r}"


def test_a_percentage_keeps_its_typographic_minus():
    _assert_negative("−1.55%", DataPointType.PERCENTAGE, "-1.55")
    _assert_negative("−12%", DataPointType.PERCENTAGE, "-12")


def test_signed_changes_keep_their_typographic_minus():
    _assert_negative("−5% decrease", DataPointType.CHANGE, "-5")
    _assert_negative("−$120.00", DataPointType.CHANGE, "-120.00")
    _assert_negative("−3 points", DataPointType.CHANGE, "-3")
    _assert_negative("−2.5", DataPointType.CHANGE, "-2.5")


def test_both_minuses_read_the_same():
    for ascii_text in ("-1.55%", "-$120.00", "-3 points", "-2.5"):
        a = _only(ascii_text)
        b = _only(ascii_text.replace("-", "−"))
        assert (a["type"], a["value"]) == (b["type"], b["value"]), ascii_text


def _assert_signed(text, dp_type, amount, **fields):
    r = _only(text)
    assert r["type"] == dp_type, f"{text!r}: got {r['type'].value} {r['matched']!r}"
    assert r["matched"] == text.split(": ")[-1], f"{text!r}: matched {r['matched']!r}"
    assert r["value"]["value"] == Decimal(amount), f"{text!r}: value {r['value']!r}"
    for key, want in fields.items():
        assert r["value"][key] == want, f"{text!r}: {key} {r['value'][key]!r}"


def test_a_signed_amount_is_a_change_in_its_own_currency():
    _assert_signed("Refund: -\u20ac200", DataPointType.CHANGE, "-200", currency="EUR")
    _assert_signed(
        "Refund: \u2212\u00a350", DataPointType.CHANGE, "-50", currency="GBP"
    )
    _assert_signed("Refund: -200 EUR", DataPointType.CHANGE, "-200", currency="EUR")
    _assert_signed("Refund: -200\u20ac", DataPointType.CHANGE, "-200", currency="EUR")
    _assert_signed(
        "Gain: +\u20ac200", DataPointType.CHANGE, "200", direction="increase"
    )


def test_a_signed_magnitude_keeps_its_magnitude():
    _assert_signed("Loss: -$5K", DataPointType.CHANGE, "-5000", currency="USD")
    _assert_signed("Loss: -$1.2M", DataPointType.CHANGE, "-1200000")


def test_a_signed_grouped_number_is_a_change():
    _assert_signed("Net: -1,234", DataPointType.CHANGE, "-1234", type="bare")
    _assert_signed("Net: -4,783.45", DataPointType.CHANGE, "-4783.45", type="bare")


def test_a_signed_temperature_stays_a_temperature():
    _assert_signed("Low: -5\u00b0C", DataPointType.MEASUREMENT, "-5", unit="C")
    _assert_signed("Low: \u22125 \u00b0C", DataPointType.MEASUREMENT, "-5", unit="C")


def test_a_hyphen_after_a_word_or_digit_is_not_a_sign():
    assert _only("A-\u20ac5")["matched"] == "\u20ac5"
    assert _only("$10-$20")["type"] == DataPointType.RANGE


def test_take_sign_declines_what_a_sign_does_not_change():
    # A height is not signed, and a sign after a letter is a hyphen.
    height = {
        "type": DataPointType.MEASUREMENT,
        "matched": "6 ft",
        "value": {"value": Decimal(6), "measurement_type": "height"},
        "start": 1,
        "end": 5,
    }
    assert take_sign(height, "-6 ft") is None
    euro = {
        "type": DataPointType.CURRENCY,
        "matched": "\u20ac5",
        "value": {"amount": Decimal(5), "currency": "EUR"},
        "start": 2,
        "end": 4,
    }
    assert take_sign(euro, "A-\u20ac5") is None
    signed = take_sign({**euro, "start": 1, "end": 3}, "-\u20ac5")
    assert signed is not None
    assert signed["start"] == 0 and signed["matched"] == "-\u20ac5", signed


TESTS = [
    test_a_percentage_keeps_its_typographic_minus,
    test_signed_changes_keep_their_typographic_minus,
    test_both_minuses_read_the_same,
    test_a_signed_amount_is_a_change_in_its_own_currency,
    test_a_signed_magnitude_keeps_its_magnitude,
    test_a_signed_grouped_number_is_a_change,
    test_a_signed_temperature_stays_a_temperature,
    test_a_hyphen_after_a_word_or_digit_is_not_a_sign,
    test_take_sign_declines_what_a_sign_does_not_change,
]


if __name__ == "__main__":
    for t in TESTS:
        t()
        print(f"  ✓  {t.__name__}")
    print(f"All {len(TESTS)} tests passed.")
