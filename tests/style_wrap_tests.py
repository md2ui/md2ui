"""
Unit tests for emphasis-wrap detection and emphasis-wrapped links.

`_detect_style_wrap` decides whether a leaf's content is wrapped in `*`, `**`
or `***`. Matching runs at both ends are not sufficient — the two runs must be
the SAME span. A line that is a *sequence* of emphasis spans (`*A* *B*`) also
starts and ends with a marker, and treating it as one wrap would make callers
strip a wrapper that was never there and re-wrap the leftover, doubling the
markers.

Run with: uv run python tests/style_wrap_tests.py
"""

from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.markdown_grouper import MarkdownGrouper
from md2ui.pipeline.grouper_inline_marks import (
    _SPLIT_WRAP_CHARS,
    _balance_markdown_markers,
    _detect_style_wrap,
    _drop_orphan_marker,
)

_wrap = _detect_style_wrap
_orphan = _drop_orphan_marker


def _leaves(text: str) -> list[tuple[str, str, str | None]]:
    """(type, content, link_variant) for every leaf of a processed document."""
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    out: list[tuple[str, str, str | None]] = []

    def walk(node):
        if not node.children:
            out.append((node.type, node.content, node.to_dict().get("link_variant")))
        for child in node.children:
            walk(child)

    walk(g.ast)
    return out


# ---------------------------------------------------------------------------
# _detect_style_wrap
# ---------------------------------------------------------------------------


def test_whole_content_wraps_are_detected():
    for text, marker_len in [
        ("*a*", 1),
        ("**a b**", 2),
        ("***x***", 3),
        ("***⭐ Popular***", 3),
        ("*[A](/l)*", 1),
        ("**[A](/l)**", 2),
        ("***[A](/l)***", 3),
    ]:
        got = _wrap(text, 0, len(text))
        assert got is not None and got[0] == marker_len, (text, got)
    print("  ✓  whole-content wraps are detected")


def test_sequences_of_spans_are_not_a_wrap():
    """Two matching runs are not automatically one span."""
    for text in [
        "*A* *B*",
        "**Bold** and **more**",
        "*[A](/l)* *[B](/l)*",
        "**[A](/l)** **[B](/l)**",
        "**a**b**c**",
    ]:
        assert _wrap(text, 0, len(text)) is None, (text, _wrap(text, 0, len(text)))
    print("  ✓  a sequence of emphasis spans is not a whole-content wrap")


def test_nested_shorter_emphasis_still_wraps():
    """`**a *b* c**` is genuinely bold-wrapped — interior runs are shorter."""
    got = _wrap("**a *b* c**", 0, 11)
    assert got is not None and got[0] == 2, got
    print("  ✓  a shorter nested emphasis does not break the wrap")


def test_non_wraps_stay_none():
    for text in ["**a** b", "****x****", "*", "**", "***", "_a_ _b_", "plain"]:
        assert _wrap(text, 0, len(text)) is None, text
    print("  ✓  non-wraps stay None")


def test_documented_conservative_limitation():
    """`*a *b* c*` IS one wrap under CommonMark; we deliberately reject it.

    Pinned so the trade-off is a decision, not an accident. Failing benignly
    (content left unwrapped) beats unwrapping something that isn't wrapped.
    """
    assert _wrap("*a *b* c*", 0, 9) is None
    print("  ✓  the documented CommonMark limitation is pinned")


# ---------------------------------------------------------------------------
# Emphasis-wrapped links
# ---------------------------------------------------------------------------


def test_row_of_styled_links_keeps_every_variant():
    """tests-links.md:79-87 — each row is three links of one variant."""
    for wrap, variant in [
        ("", "primary"),
        ("*", "secondary"),
        ("**", "tertiary"),
        ("***", "quaternary"),
    ]:
        text = " ".join(f"{wrap}[{label}](/link){wrap}" for label in ("A", "❤️ B", "❤️"))
        leaves = _leaves(text)
        assert len(leaves) == 3, (text, leaves)
        assert all(t == "link" for t, _, _ in leaves), (text, leaves)
        assert all(v == variant for _, _, v in leaves), (text, leaves)
    print("  ✓  a row of styled links keeps every variant")


def test_no_doubled_marker_artifact():
    """The middle link must not become a text node of doubled markers."""
    for wrap in ("*", "**", "***"):
        text = f"{wrap}[A](/l){wrap} {wrap}[B](/l){wrap} {wrap}[C](/l){wrap}"
        kinds = [t for t, _, _ in _leaves(text)]
        assert kinds == ["link", "link", "link"], (text, _leaves(text))
    print("  ✓  no doubled-marker text node survives")


def test_styling_does_not_decide_recognition():
    """A styled boundary link peels exactly like an unwrapped one."""
    for wrap, variant in [("", "primary"), ("*", "secondary"), ("**", "tertiary")]:
        # The separator is what earns the peel; the wrapper only picks the
        # variant. Without it the link stays a TEXT-LINK inside the prose.
        lead = _leaves(f"{wrap}[A](/l){wrap} - text here")
        assert lead[0][0] == "link" and lead[0][2] == variant, lead
        assert lead[1][0] == "segment", lead
        trail = _leaves(f"text here - {wrap}[A](/l){wrap}")
        assert trail[-1][0] == "link" and trail[-1][2] == variant, trail
    print("  ✓  styling picks the variant, never recognition")


def test_mixed_emoji_and_styled_link_run():
    leaves = _leaves("🙂 *[A](/l)*")
    assert [t for t, _, _ in leaves] == ["emoji", "link"], leaves
    assert leaves[1][2] == "secondary", leaves
    print("  ✓  an emoji + styled-link run peels together")


def test_emoji_still_drops_its_markers():
    """Regression guard: EMOJI must keep dropping the wrap, unlike LINK."""
    # Separated so there IS an emoji element to check (adjacency keeps the
    # whole line as one leaf). The emoji still drops the wrap from its CONTENT —
    # unlike a LINK, which keeps it — and only reads it as a variant.
    leaves = _leaves("***⭐ - Popular***")
    assert leaves == [
        ("emoji", "⭐", None),
        ("segment", "***Popular***", None),
    ], leaves
    print("  ✓  a wrapped emoji still drops its markers")


def test_lone_styled_link_unchanged():
    leaves = _leaves("*[A](/l)*")
    assert leaves == [("link", "*[A](/l)*", "secondary")], leaves
    print("  ✓  a lone styled link is unchanged")


# ---------------------------------------------------------------------------
# _drop_orphan_marker
# ---------------------------------------------------------------------------


def test_stray_opener_is_dropped():
    """A marker left open by a datapoint cut is removed."""
    assert _orphan("**Key** **") == "**Key**"
    assert _orphan("*x* *") == "*x*"
    print("  ✓  a stray opener is dropped")


def test_orphan_closer_is_kept_for_balancing():
    """The mirror case: `ppm (2024)**` closes a span whose opener was cut.

    Stripping it here would lose the bold; _balance_markdown_markers must be
    left to restore the opener instead.
    """
    assert _orphan("ppm (2024)**") == "ppm (2024)**"
    assert _balance_markdown_markers("ppm (2024)**") == ("**ppm (2024)**")
    print("  ✓  an orphan closer is kept so balancing can restore it")


def test_balanced_text_is_untouched():
    for text in ["**a**", "**~420 ppm (2024)**", "`code`", "plain text", "~~x~~"]:
        assert _orphan(text) == text, text
    print("  ✓  balanced text is untouched")


def test_a_marker_unpaired_in_its_line_stays_text():
    """A cut never changes what a piece says: an ``_`` with no partner in the
    whole line is text in the piece, while a pair the cut split is repaired."""
    line = "Mail - nora.vasquez_@example.com"
    piece = "nora.vasquez_@example.com"
    assert _balance_markdown_markers(piece, line, 6) == piece
    assert _balance_markdown_markers("value**", "**Key - value**", 8) == "**value**"
    print("  ✓  a marker unpaired in its line stays text")


def test_datapoint_cut_leaves_no_stray_marker():
    """End to end: data/markdown/claude/customer-reviews.md:297."""
    leaves = _leaves("**Would customers recommend this product?** **94% say YES**")
    assert leaves[0][1] == "**Would customers recommend this product?**", leaves
    assert not any("****" in c for _, c, _ in leaves), leaves
    print("  ✓  a datapoint cut leaves no stray marker")


# ---------------------------------------------------------------------------
# _detect_style_wrap — the wider marker set the structural splitters use
# ---------------------------------------------------------------------------

_SPLIT_CHARS = _SPLIT_WRAP_CHARS


def test_run_lengths_are_per_marker_character():
    """A wrap opens only on run lengths that marker actually has.

    Widening *chars* without this reads `~420 - ~600` as a strike wrap and
    splits the interior of a ``code span``.
    """
    assert _wrap("~~A | B~~", 0, 9, _SPLIT_CHARS) == (2, 2, 7)
    assert _wrap("~A | B~", 0, 7, _SPLIT_CHARS) is None
    assert _wrap("~~~a~~~", 0, 7, _SPLIT_CHARS) is None
    assert _wrap("`a b`", 0, 5, _SPLIT_CHARS) == (1, 1, 4)
    assert _wrap("``a | b``", 0, 9, _SPLIT_CHARS) is None
    assert _wrap("___x___", 0, 7, _SPLIT_CHARS) == (3, 3, 4)
    print("  ✓  run lengths are per marker character")


def test_default_chars_still_mean_asterisks_only():
    """Existing callers pass no *chars*; widening must not reach them."""
    assert _wrap("__a__", 0, 5) is None
    assert _wrap("~~a~~", 0, 5) is None
    assert _wrap("**a**", 0, 5) == (2, 2, 3)
    print("  ✓  the default chars set is unchanged")


def test_a_tier_followed_by_spans_is_not_a_wrap():
    """This line begins and ends with `_` but is not wrapped.

    Reading it as one italic wrap would re-wrap every segment that lacked a
    leading `_`, turning `` `x` : _vs last month_ `` into
    `` _`x` : _vs last month__ ``.
    """
    line = "___1,293___ - `x` : _vs last month_"
    assert _wrap(line, 0, len(line), _SPLIT_CHARS) is None
    assert _wrap("_A_ - _B_", 0, 9, _SPLIT_CHARS) is None
    print("  ✓  a tier followed by spans is not a whole-line wrap")


# ---------------------------------------------------------------------------
# _balance_markdown_markers
# ---------------------------------------------------------------------------

_balance = _balance_markdown_markers


def test_balance_is_run_aware():
    """`***` and `___` are one run, never `**` plus a stray `*`."""
    assert _balance("***A") == "***A***"
    assert _balance("C***") == "***C***"
    assert _balance("___x") == "___x___"
    assert _balance("~~a") == "~~a~~"
    print("  ✓  balancing closes with the run it opened")


def test_balance_normalises_the_closer_to_the_opener():
    """The opener is authoritative, so a tier is never invented upward.

    `__x_` must not come out `__x___` — a Display tier built out of a Lead one.
    """
    assert _balance("__vs last month_") == "__vs last month__"
    assert _balance("**vs last month*") == "**vs last month**"
    assert _balance("___vs last month_") == "___vs last month___"
    assert _balance("_vs last month__") == "_vs last month_"
    print("  ✓  a mismatched closer is normalised to its opener")


def test_balance_closes_a_marker_anywhere_in_the_piece():
    """Not just the first run at each end — any unpaired opener is closed."""
    assert _balance("`x` : _vs last") == "`x` : _vs last_"
    print("  ✓  an unpaired opener is closed wherever it sits")


def test_balance_reopens_a_closer_stranded_before_punctuation():
    """A cut that leaves a span's closer before punctuation repairs it as a
    closer: ``**`` after a letter and before ``.`` can only close, so its
    opener is prepended — it is not a new span to be closed after the dot."""
    for cut, repaired in (
        ("Beta**.", "**Beta**."),
        ("Beta*.", "*Beta*."),
        ("Beta_!", "_Beta_!"),
        ("Beta_.", "_Beta_."),
    ):
        assert _balance(cut) == repaired, cut
    # A run that could open or close (``*`` between letters) stays an opener.
    assert _balance("a*b") == "a*b*"
    print("  ✓  a closer stranded before punctuation is re-opened")


def test_a_cut_span_keeps_its_closer_before_punctuation():
    """End to end: the separator and the spring both hand their piece over."""
    for line, piece in (
        ("_Alpha | Beta_!", "_Beta_!"),
        ("*Alpha | Beta*.", "*Beta*."),
        ("**Alpha | Beta**.", "**Beta**."),
        ("_Alpha ... Beta_.", "_Beta_."),
    ):
        contents = [c for _, c, _ in _leaves(line)]
        assert contents[-1] == piece, (line, contents)
    print("  ✓  a cut span keeps its closer before punctuation")


def test_balance_leaves_a_pure_marker_run_alone():
    """`___` is a horizontal rule, not three unmatched markers.

    _split_colon_columns relies on this, or `___` would come back as `_____`.
    """
    for s in ("___", "***", "**", "`", "~~"):
        assert _balance(s) == s, s
    print("  ✓  a pure marker run is not a span to close")


def test_balance_drops_a_stranded_run_at_either_edge():
    """A run with whitespace on both sides can flank in neither direction, so
    CommonMark can never pair it — the renderer would draw it literally.

    Cutting `**$100 Milestone:** Crossed on…` at the colon strands the key's
    closer at the head of the value.
    """
    assert _balance("** Crossed on August 5, 2025") == "Crossed on August 5, 2025"
    assert _balance("**Key** **") == "**Key**"
    print("  ✓  a stranded run at an edge is dropped")


def test_balance_keeps_a_rule_between_stacked_columns():
    """...but only at the EDGES. `A | B : ___ : C | D` draws that `___`."""
    assert _balance("B : ___ : C") == "B : ___ : C"
    print("  ✓  a mid-piece rule survives balancing")


def test_balance_ignores_intraword_underscores():
    """`message_schemas` is an identifier, not emphasis — CommonMark exempts
    an underscore run that is alphanumeric on both sides. `*` has no such
    exemption, so the rule is deliberately asymmetric.
    """
    assert _balance("`message_schemas` is **append-only**") == (
        "`message_schemas` is **append-only**"
    )
    assert _balance("snake_case_name") == "snake_case_name"
    print("  ✓  intraword underscores are not markers")


def test_balance_ignores_a_lone_tilde():
    """`~420 ppm` — a single `~` is "approximately", never strikethrough."""
    assert _balance("CO₂ levels increased from **~") == (
        "CO₂ levels increased from **~**"
    )
    print("  ✓  a lone tilde is not a marker")


TESTS = [
    test_whole_content_wraps_are_detected,
    test_sequences_of_spans_are_not_a_wrap,
    test_nested_shorter_emphasis_still_wraps,
    test_non_wraps_stay_none,
    test_documented_conservative_limitation,
    test_row_of_styled_links_keeps_every_variant,
    test_no_doubled_marker_artifact,
    test_styling_does_not_decide_recognition,
    test_mixed_emoji_and_styled_link_run,
    test_emoji_still_drops_its_markers,
    test_lone_styled_link_unchanged,
    test_stray_opener_is_dropped,
    test_orphan_closer_is_kept_for_balancing,
    test_balanced_text_is_untouched,
    test_a_marker_unpaired_in_its_line_stays_text,
    test_datapoint_cut_leaves_no_stray_marker,
    test_run_lengths_are_per_marker_character,
    test_default_chars_still_mean_asterisks_only,
    test_a_tier_followed_by_spans_is_not_a_wrap,
    test_balance_is_run_aware,
    test_balance_normalises_the_closer_to_the_opener,
    test_balance_closes_a_marker_anywhere_in_the_piece,
    test_balance_reopens_a_closer_stranded_before_punctuation,
    test_a_cut_span_keeps_its_closer_before_punctuation,
    test_balance_leaves_a_pure_marker_run_alone,
    test_balance_drops_a_stranded_run_at_either_edge,
    test_balance_keeps_a_rule_between_stacked_columns,
    test_balance_ignores_intraword_underscores,
    test_balance_ignores_a_lone_tilde,
]

if __name__ == "__main__":
    print("Style Wrap Tests")
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
