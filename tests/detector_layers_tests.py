"""
Unit tests for the two layers under ``data_point_detector.py``:
``detector_parsers`` (match → value) and ``detector_vocabulary`` (the tables
both the patterns and the parsers are written in).

The other detector suites all go through ``detect_all``, which is the right
level for "does this document find its dates" but hides two things:

**The parser protocol.** Every parser is a module function that takes the
matched text and nothing else — asserted directly here,
because a signature change would otherwise only surface as a wrong value deep in
a document.

**The vocabulary's one job is agreement.** A month name appears in the regex that
FINDS a date and again in the parser that reads it. The tables are one place so
those cannot drift; these assert the pairs that must correspond.

Run with: uv run python scripts/run_tests.py
"""

from decimal import Decimal

from md2ui.pipeline import detector_vocabulary as V
from md2ui.pipeline.detector_parsers import (
    _parse_blood_type,
    _parse_emoji,
    _parse_ordinal,
    _parse_ratio_colon,
    _parse_score_fraction,
    _parse_shorthand_magnitude,
    _parse_time_12h,
    emoji_to_text,
)


# --- the parser protocol ----------------------------------------------------


def test_a_parser_takes_only_the_matched_text():
    """One positional argument, no self. The pattern table stores the function
    and calls it with the match; nothing else is available to it."""
    assert _parse_time_12h("3:45 PM") == {
        "hour": 15,
        "minute": 45,
        "subtype": "time_12h",
        "period": "PM",
    }


def test_twelve_hour_time_converts_to_twenty_four():
    """PM adds 12 — the conversion, not just the split."""
    assert _parse_time_12h("3:45 PM")["hour"] == 15
    assert _parse_time_12h("3:45 AM")["hour"] == 3


def test_a_fraction_score_keeps_decimal_precision():
    """Decimal, not float: a score is compared and rendered, and 0.1+0.2 is the
    reason this pipeline uses Decimal for every numeric value."""
    got = _parse_score_fraction("7/10")
    assert got["score"] == Decimal("7") and got["max"] == Decimal("10")
    assert isinstance(got["score"], Decimal)


def test_a_shorthand_magnitude_multiplies_out():
    got = _parse_shorthand_magnitude("2.5k")
    assert got["value"] == Decimal("2500.0")
    assert got["base_value"] == Decimal("2.5")


def test_blood_type_splits_group_from_rhesus():
    assert _parse_blood_type("B+") == {"abo": "B", "rh": "positive", "full": "B+"}


def test_an_ordinal_keeps_its_suffix():
    assert _parse_ordinal("3rd") == {"value": 3, "suffix": "rd"}


def test_a_ratio_records_its_written_format():
    """16:9 and 16/9 are the same ratio written two ways, and the renderer
    shows it back the way the author typed it."""
    assert _parse_ratio_colon("16:9") == {"left": 16, "right": 9, "format": "colon"}


def test_an_emoji_parses_to_its_character_and_codepoint():
    """No name: only the Phase 7 labeller reads one, and it derives it (ADR-102)."""
    got = _parse_emoji("🎉")
    assert got["count"] == 1
    assert got["emojis"] == [{"char": "🎉", "codepoint": "U+1F389"}]
    assert emoji_to_text("🎉") == "party popper"


# --- the vocabulary must agree with itself ----------------------------------


def test_the_currency_symbol_table_and_class_agree():
    """``_CURRENCY_SYMBOLS`` is the character class the regex uses;
    ``_SYMBOL_CURRENCY`` maps each symbol to its ISO code. A symbol in one and
    not the other is a currency that is found but not named, or named but never
    found."""
    in_class = {c for c in V._CURRENCY_SYMBOLS if c not in "[]"}
    assert in_class == set(V._SYMBOL_CURRENCY), in_class ^ set(V._SYMBOL_CURRENCY)


def test_every_magnitude_word_has_a_multiplier():
    """``_MAGNITUDE_WORDS`` is the regex alternation; ``_MAGNITUDE_MULTIPLIERS``
    is what the parser looks the match up in. A word in the pattern with no
    multiplier raises at parse time on a real document."""
    words = set(V._MAGNITUDE_WORDS.split("|"))
    assert words == set(V._MAGNITUDE_MULTIPLIERS), words ^ set(V._MAGNITUDE_MULTIPLIERS)


def test_the_long_month_names_are_all_twelve_and_ordered():
    months = V._MONTH_NAMES_LONG.split("|")
    assert len(months) == 12
    assert months[0] == "January" and months[-1] == "December"


def test_the_month_pattern_contains_the_month_names():
    """``_MONTH_NAMES`` is the compiled alternation the date regexes embed; it
    must be built from the same list the parser indexes into."""
    for name in V._MONTH_NAMES_LONG.split("|"):
        assert name in V._MONTH_NAMES, name


TESTS = [
    test_a_parser_takes_only_the_matched_text,
    test_twelve_hour_time_converts_to_twenty_four,
    test_a_fraction_score_keeps_decimal_precision,
    test_a_shorthand_magnitude_multiplies_out,
    test_blood_type_splits_group_from_rhesus,
    test_an_ordinal_keeps_its_suffix,
    test_a_ratio_records_its_written_format,
    test_an_emoji_parses_to_its_character_and_codepoint,
    test_the_currency_symbol_table_and_class_agree,
    test_every_magnitude_word_has_a_multiplier,
    test_the_long_month_names_are_all_twelve_and_ordered,
    test_the_month_pattern_contains_the_month_names,
]

if __name__ == "__main__":
    print("Detector Layers Tests")
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
