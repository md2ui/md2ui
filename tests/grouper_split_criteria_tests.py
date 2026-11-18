"""
Unit tests for grouper_split_criteria: the structural criteria and their rules.

Every answer here is a rule's. The ``test_predict_*`` tests exercise the
comma-signal path: when text has 2+ comma segments (after stripping numeric
commas) SplitCriteria delegates to CommaSignalRules,
which applies ordered prose-detection rules before falling back to cap uniformity.

Run with: uv run python tests/grouper_split_criteria_tests.py
"""

import re

from md2ui.pipeline.grouper_split_criteria import (
    Criterion,
    SplitCriteria,
    _key_value_rule,
    _rule_applicable,
)

# ---------------------------------------------------------------------------
# The comma-signal path, read through the KEY_VALUE answer: 1 when applicable()
# includes it (structured), 0 when a rule calls the line prose. For texts with
# 2+ list segments the rules use comma_cap_uniform directly.
# ---------------------------------------------------------------------------


def _structured(text: str) -> int:
    return int(Criterion.KEY_VALUE in SplitCriteria().applicable(text))


def test_verdict_prose_mixed_cap():
    assert _structured("Welcome coffee, networking, badge pickup") == 0
    print("  ✓  verdict: prose — mixed cap (ai-summit-schedule.md)")


def test_verdict_prose_buffet():
    assert _structured("Buffet lunch, roundtable discussions") == 0
    print("  ✓  verdict: prose — mixed cap")


def test_verdict_prose_connector_and():
    # "and Beyond" starts lowercase — breaks cap uniformity
    assert _structured("ChatGPT, GPT-5, and Beyond") == 0
    print("  ✓  verdict: prose — connector 'and' breaks cap uniformity")


def test_verdict_prose_sentence_with_connector():
    # "reliable" and "and easy to use" are lowercase — mixed
    assert _structured("The app is fast, reliable, and easy to use") == 0
    print("  ✓  verdict: prose — sentence with connector")


def test_verdict_prose_bags_goodbye():
    # "said goodbye" and "and left" both start lowercase
    assert _structured("He packed his bags, said goodbye, and left") == 0
    print("  ✓  verdict: prose — narrative sentence")


def test_verdict_structured_all_cap():
    assert _structured("View pin, Reveal code") == 1
    print("  ✓  verdict: structured — all-cap segments")


def test_verdict_structured_all_lower():
    assert _structured("apples, peas, carrots") == 1
    print("  ✓  verdict: structured — all-lower segments")


def test_verdict_structured_days():
    assert _structured("Monday, Tuesday, Wednesday") == 1
    print("  ✓  verdict: structured — days of week")


def test_verdict_structured_sizes():
    assert _structured("Small, Medium, Large") == 1
    print("  ✓  verdict: structured — sizes")


def test_verdict_structured_colors():
    assert _structured("Red, Green, Blue") == 1
    print("  ✓  verdict: structured — colors")


def test_verdict_prose_date_comma():
    # A date comma is not evidence that the surrounding text is structured.
    # Rule 4 (date fragment in segment) fires before the cap-uniformity fallback.
    assert _structured("February 1, 2026") == 0
    assert _structured("February 4, 2026 at 6:00 PM") == 0
    print("  ✓  verdict: prose — date comma not treated as list separator")


def test_verdict_prose_cancellation_date():
    # A date comma inside a prose sentence
    assert (
        _structured(
            "Free cancellation until March 8, 2024. Cancellations after this date are subject to one night's charge."
        )
        == 0
    )
    print("  ✓  verdict: prose — date comma + internal sentence boundary")


def test_verdict_prose_etc_ending():
    # Rule 2: "etc." ending marks prose, not a list
    assert _structured("Netflix, Disney+, Prime Video, Hulu, etc.") == 0
    print("  ✓  verdict: prose — trailing 'etc.'")


def test_verdict_prose_preposition_intro():
    # Rule 7: first segment is an intro phrase containing a preposition
    assert (
        _structured("Major events in Australia, California, Canada, Mediterranean") == 0
    )
    print("  ✓  verdict: prose — preposition intro phrase in first segment")


def test_verdict_prose_contraction():
    # Rule 5: apostrophe contraction
    assert _structured("Hurry Up, We're Dreaming") == 0
    print("  ✓  verdict: prose — apostrophe contraction")


def test_verdict_italic_kv_basic():
    assert _structured("*KeyItalic:* value") == 1
    print("  ✓  verdict: structured — italic key-value *Key:* value")


def test_verdict_italic_kv_multiword():
    assert _structured("*Multi Word Key:* some value here") == 1
    print("  ✓  verdict: structured — italic key-value multi-word key")


def test_verdict_italic_kv_bullet_not_triggered():
    # "* bullet item" is a markdown bullet (space after *), not italic key-value.
    # Verify the (?!\s) guard prevents the italic immediate rule from firing.
    assert re.match(r"^\*(?!\s)[^*:]+:\*\s+\S", "* bullet item") is None
    print(
        "  ✓  verdict: (?!\\s) guard — markdown bullet not confused with italic key-value"
    )


def test_verdict_structured_no_rules_fire():
    # Verify that legitimate lists still classify as structured
    assert _structured("Netflix, Disney+, Prime Video, Hulu") == 1
    assert _structured("Replace, Order new card") == 1
    assert _structured("Organic Whole Milk, Free Range Eggs, Greek Yogurt Plain") == 1
    print("  ✓  verdict: structured — lists with no prose signals")


def test_verdict_kv_candidate_overrides_period_rule():
    # 'Ingredients: Chicken eggs, ..., vanillin.' has 11 comma segments,
    # uniform-lowercase value, but a trailing period. CommaSignalRules's
    # period rule (Rule 6) would return 0; the Key: prefix override flips it
    # to 1 so the structural KV split runs. The value is reclassified on its
    # own at the next gate (it stays as a single VALUE node — see grouper).
    assert (
        _structured(
            "Ingredients: Chicken eggs, flour, milk 3.2%, butter, water, "
            "dark chocolate 54-55%, melange, white sugar, cocoa powder, salt, vanillin."
        )
        == 1
    )
    assert _structured("Key with comma list: Value A, Value B, Value C") == 1
    print("  ✓  verdict: 'Key:' prefix overrides comma-signal prose verdict")


def test_verdict_no_kv_candidate_still_prose():
    # Without a Key: prefix, the comma-signal rules still apply unchanged. The
    # value-after-peeling shape — which is what the grouper sees at the
    # second gate — must still classify as prose for these.
    assert (
        _structured(
            "Chicken eggs, flour, milk 3.2%, butter, water, "
            "dark chocolate 54-55%, melange, white sugar, cocoa powder, salt, vanillin."
        )
        == 0
    )
    assert _structured("apples, oranges, bananas.") == 0
    print("  ✓  verdict: no Key: prefix → period rule still fires")


def test_verdict_kv_candidate_requires_letter_before_colon():
    # '8:00 AM, Workshop, ...' has a colon but no letter before it — must
    # not be treated as a Key: candidate (otherwise time patterns would be
    # mis-split as KV).
    assert _structured("8:00 AM, Workshop, Networking, Lunch") in (0, 1)
    # The exact verdict depends on other rules; the important thing is the
    # KV-candidate override does NOT fire on this input.
    from md2ui.pipeline.grouper_split_criteria import _KV_PREFIX_CANDIDATE

    assert _KV_PREFIX_CANDIDATE.match("8:00 AM, Workshop, Networking, Lunch") is None
    print("  ✓  verdict: '8:00 AM, ...' — no letter before colon → no KV override")


def _assert_pred(text: str, expected: int, label: str):
    got = _structured(text)
    assert got == expected, f"{text!r}: expected {expected}, got {got}"
    print(f"  ✓  {label}")


# ---------------------------------------------------------------------------
# Incidental commas do not make a line structured
#
# The comma-signal path can claim any text with 2+ comma segments, so a line
# whose only comma belongs to a date would otherwise be judged by rules outside
# their remit. Authored separators are character-driven; these assertions pin
# the remaining key-value/datapoint classification signal.
# ---------------------------------------------------------------------------


def test_date_comma_with_separator_is_structured():
    for sep in ("-", "|", ":"):
        _assert_pred(
            f"**User Research on Web** {sep} Feb 28, 2020.7:00 pm",
            1,
            f"verdict: date comma + ' {sep} ' separator → structured",
        )


def test_date_range_with_dash_is_structured():
    _assert_pred(
        "Fri, Aug 14 - Sun, Aug 16", 1, "verdict: weekday-comma date range → structured"
    )


def test_paren_comma_with_separator_is_structured():
    _assert_pred(
        "iPhone 15 Pro (San Francisco, CA) - 2 hours ago",
        1,
        "verdict: comma inside parens + separator → structured",
    )


def test_comma_prose_signal_still_wins_over_a_separator():
    """The connector rule's prose verdict holds beside a separator."""
    _assert_pred(
        "**Labrador Retriever** - Friendly, outgoing, and active companion",
        0,
        "verdict: connector list + dash → still prose",
    )


def test_sentence_with_a_date_and_a_period_stays_prose():
    _assert_pred(
        "Free cancellation until March 8, 2024. Cancellations after this "
        "date are subject to a charge.",
        0,
        "verdict: trailing period + sentence boundary → still prose",
    )


# ---------------------------------------------------------------------------
# A labelled paragraph is not a row of key-values
#
# A first `Top left:` must not let the KV escape hatch overturn a prose verdict,
# or the grouper cuts a photo credit into leaves with sentence fragments as KEYs.
# ---------------------------------------------------------------------------


def test_labelled_paragraph_is_prose():
    _assert_pred(
        "Top left: a photo by someone, here cropped, is public domain. "
        "Bottom left: another photo, also cropped, is public domain.",
        0,
        "verdict: sentences opening with labels → prose, not key-values",
    )


def test_one_label_with_a_prose_value_still_pairs():
    """BOTH signals are required. A single key whose value runs to several
    sentences is an ordinary key-value and must keep pairing."""
    _assert_pred(
        "**Note**: These are simulated statistics for demonstration purposes "
        "only. For actual trading decisions, consult real-time sources.",
        1,
        "verdict: one label + a multi-sentence value → still key-value",
    )
    _assert_pred(
        "**Altitude**: At 7,350 feet (2,240 meters), Mexico City sits high. "
        "Take it easy your first day.",
        1,
        "verdict: bold key + prose value → still key-value",
    )


def test_single_sentence_multi_label_still_pairs():
    """The other half: several labels on ONE sentence is a genuine KV row."""
    _assert_pred(
        "Key segment 1: value 1 - Key segment 2: value 2",
        1,
        "verdict: two labels, one sentence → still key-values",
    )


def test_labelled_paragraph_helper_needs_both_signals():
    from md2ui.pipeline.grouper_split_criteria import _is_labelled_paragraph as f

    assert f("Top left: a. Bottom left: b.")
    assert not f("Note: one sentence only, no break.")
    assert not f("Key 1: a - Key 2: b")
    print("  ✓  _is_labelled_paragraph requires a break AND >=2 labels")


def test_tight_kv_colon_is_not_a_structural_separator():
    """`Key: value` has no spaced colon, so the separator escape must not fire
    on it — the KV path owns that shape."""
    from md2ui.pipeline.grouper_split_criteria import _STRUCTURAL_SEPARATOR

    assert not _STRUCTURAL_SEPARATOR.search("Key: value")
    assert _STRUCTURAL_SEPARATOR.search("Key : value")
    print("  ✓  a tight Key: colon is not a structural separator")


def test_applicable_answers_key_value_by_its_rules():
    criteria = SplitCriteria()
    assert criteria.applicable("**Key:** value") == frozenset({Criterion.KEY_VALUE})
    assert Criterion.KEY_VALUE in criteria.applicable("Note: it crashed - really.")


def test_element_criterion_reads_regular_text_evidence():
    assert Criterion.ELEMENT not in _rule_applicable("⭐ 🚀")
    criteria = SplitCriteria()
    assert Criterion.ELEMENT not in criteria.applicable("⭐ 🚀")
    assert Criterion.ELEMENT not in criteria.applicable(
        "Text with a ⭐ inside a sentence."
    )
    assert Criterion.ELEMENT in _rule_applicable(
        "⭐ `Sale`", element_has_regular_text=False
    )
    assert Criterion.ELEMENT not in _rule_applicable(
        "⭐ Popular", element_has_regular_text=True
    )


def test_the_prose_shapes_answer_first():
    """Three prose shapes the key-value rule itself must call prose."""
    for prose in (
        "He paused ... unsure what to say next.",
        "Loading your dashboard ...",
        "Apple HomePod delivers sound. :contentReference[oaicite:8]{index=8}",
    ):
        assert _key_value_rule(prose) == 0, prose
    # The keeps: a row with a spring, a spring beside a separator, a piped
    # line, a colon inside a link target, a time.
    for other in (
        "Subtotal ... $42.50",
        "**Jonas Whitfield** ... Product Designer",
        "A - B ...",
        "key:value 1 | key:value 2",
        "Distribution ... *[+](agent:add-metric)*",
        "3:00 AM",
    ):
        assert _key_value_rule(other) != 0, other


def test_a_struck_key_is_a_key_value():
    assert _key_value_rule("~~KeyStrikethrough:~~ value") == 1


def test_key_value_rules_answer_first():
    criteria = SplitCriteria()
    assert Criterion.KEY_VALUE in criteria.applicable("Small, Medium, Large")
    assert Criterion.KEY_VALUE not in criteria.applicable(
        "The app is fast, reliable, and easy to use"
    )


def test_an_unanswered_key_value_is_structured():
    criteria = SplitCriteria()
    assert _key_value_rule("plain words") is None, "the rules must abstain here"
    answer = criteria.applicable("plain words")
    assert Criterion.KEY_VALUE in answer
    assert Criterion.ELEMENT not in answer


TESTS = [
    test_an_unanswered_key_value_is_structured,
    test_key_value_rules_answer_first,
    test_the_prose_shapes_answer_first,
    test_a_struck_key_is_a_key_value,
    test_element_criterion_reads_regular_text_evidence,
    test_applicable_answers_key_value_by_its_rules,
    test_labelled_paragraph_is_prose,
    test_one_label_with_a_prose_value_still_pairs,
    test_single_sentence_multi_label_still_pairs,
    test_labelled_paragraph_helper_needs_both_signals,
    test_date_comma_with_separator_is_structured,
    test_date_range_with_dash_is_structured,
    test_paren_comma_with_separator_is_structured,
    test_comma_prose_signal_still_wins_over_a_separator,
    test_sentence_with_a_date_and_a_period_stays_prose,
    test_tight_kv_colon_is_not_a_structural_separator,
    # verdict (comma-signal path)
    test_verdict_prose_mixed_cap,
    test_verdict_prose_buffet,
    test_verdict_prose_connector_and,
    test_verdict_prose_sentence_with_connector,
    test_verdict_prose_bags_goodbye,
    test_verdict_structured_all_cap,
    test_verdict_structured_all_lower,
    test_verdict_structured_days,
    test_verdict_structured_sizes,
    test_verdict_structured_colors,
    test_verdict_prose_date_comma,
    test_verdict_prose_cancellation_date,
    test_verdict_prose_etc_ending,
    test_verdict_prose_preposition_intro,
    test_verdict_prose_contraction,
    test_verdict_structured_no_rules_fire,
    test_verdict_kv_candidate_overrides_period_rule,
    test_verdict_no_kv_candidate_still_prose,
    test_verdict_kv_candidate_requires_letter_before_colon,
    # italic key-value immediate rule
    test_verdict_italic_kv_basic,
    test_verdict_italic_kv_multiword,
    test_verdict_italic_kv_bullet_not_triggered,
]


if __name__ == "__main__":
    print("Text Classifier Tests")
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
