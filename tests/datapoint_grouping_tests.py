"""
Unit tests for the datapoint display annotation passes in MarkdownGrouper
(Phase 6.06 _annotate_datapoint_displays / Phase 6.07 _flag_chart_groups).

Covers each display family (ratio_bar / unit_ratio / kv_percent_bar /
date_chip), the starred-ratio exclusions, single- and multi-series
chart_group flagging, chart-wins clearing, and the to_dict/from_dict
round-trip of the four fields.

Run with: uv run tests/datapoint_grouping_tests.py
"""

from md2ui.pipeline.grouper_display_vocab import _subtree_text
from md2ui.pipeline.data_point_detector import DataPointDetector, DataPointType
from md2ui.pipeline.markdown_grouper import (
    MarkdownGrouper,
    MarkdownGroupNode,
    NodeType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _processed(text: str) -> MarkdownGroupNode:
    detector = DataPointDetector()
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=detector)
    assert g.ast is not None
    return g.ast


def _displays(node: MarkdownGroupNode, name: str) -> list[MarkdownGroupNode]:
    """All nodes in the subtree flagged with datapoint_display == name."""
    out: list[MarkdownGroupNode] = []
    if node.datapoint_display == name:
        out.append(node)
    for c in node.children:
        out.extend(_displays(c, name))
    return out


def _all_displays(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    out: list[MarkdownGroupNode] = []
    if node.datapoint_display is not None:
        out.append(node)
    for c in node.children:
        out.extend(_all_displays(c))
    return out


def _charts(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    out: list[MarkdownGroupNode] = []
    if node.chart_group:
        out.append(node)
    for c in node.children:
        out.extend(_charts(c))
    return out


# ---------------------------------------------------------------------------
# Ratio bars
# ---------------------------------------------------------------------------


def test_bare_ratio_leaf():
    ast = _processed("4/8")
    bars = _displays(ast, "ratio_bar")
    assert len(bars) == 1, [n.content for n in _all_displays(ast)]
    p = bars[0].datapoint_payload
    assert p == {"value": 4.0, "max": 8.0, "text": "4/8"}, p


def test_annotate_only_ratio_still_draws_its_bar():
    # `4/8` is a TEXT leaf carrying the annotation, and `_try_leaf_display`
    # reads any leaf holding one slash-format ratio.
    ast = _processed("4/8")
    bars = _displays(ast, "ratio_bar")
    assert len(bars) == 1, [n.content for n in _all_displays(ast)]
    node = bars[0]
    assert node.type == NodeType.TEXT, node.type
    assert [dp["type"] for dp in node.data_points] == [DataPointType.RATIO], (
        node.data_points
    )
    assert node.datapoint_payload == {"value": 4.0, "max": 8.0, "text": "4/8"}
    print("  ✓  display: ratio_bar draws from an annotate-only ratio leaf")


def test_starred_ratio_excluded():
    # A star-glyph sibling marks the whole container as a rating — no bars.
    ast = _processed("**3.9**\n⭐⭐⭐⭐☆\n(1,084)")
    assert _all_displays(ast) == []


def test_score_with_stars_label_excluded():
    ast = _processed("4/5 stars")
    assert _displays(ast, "ratio_bar") == []
    assert _displays(ast, "unit_ratio") == []


def test_the_of_family_is_gone():
    """`205 MB of 270 MB` draws nothing, in any arrangement.

    A horizontal bar is spelled ONE way, the key-value percentage: "of" is a
    word, carrying no punctuation an author could escape to decline it. Its two
    numbers are still detected and read as ordinary values.
    """
    for src in ("205 MB of 270 MB", "8 of 10 tasks", "- 205 MB of 270 MB"):
        assert [n.datapoint_display for n in _all_displays(_processed(src))] == [], src
    print("  ✓  `A of B` draws nothing — the family is removed")


def test_unit_ratio_leaf_trailing_word():
    ast = _processed("25/100 progress")
    units = _displays(ast, "unit_ratio")
    assert len(units) == 1, [n.content for n in _all_displays(ast)]
    p = units[0].datapoint_payload
    assert p == {"value": 25.0, "max": 100.0, "unit": "progress"}, p


def test_unit_ratio_pair():
    ast = _processed("750/1800 Kcal")
    units = _displays(ast, "unit_ratio")
    assert len(units) == 1, [n.content for n in _all_displays(ast)]
    p = units[0].datapoint_payload
    assert p is not None
    assert p["value"] == 750.0 and p["max"] == 1800.0, p
    assert p["unit"].lower() == "kcal", p


def test_annotate_only_score_still_draws_its_unit_ratio():
    # SCORE does not split, so the fraction stays on its TEXT leaf with the
    # unit beside it — the only shape `unit_ratio` can read.
    ast = _processed("750/1800 Kcal")
    units = _displays(ast, "unit_ratio")
    assert len(units) == 1, [n.content for n in _all_displays(ast)]
    node = units[0]
    assert node.type == NodeType.TEXT, node.type
    assert [dp["type"] for dp in node.data_points] == [DataPointType.SCORE], (
        node.data_points
    )
    print("  ✓  display: unit_ratio draws from an annotate-only score leaf")


def test_unit_ratio_slash_quantity():
    ast = _processed("75/100g")
    units = _displays(ast, "unit_ratio")
    assert len(units) == 1, [n.content for n in _all_displays(ast)]
    p = units[0].datapoint_payload
    assert p is not None
    assert p["value"] == 75.0 and p["max"] == 100.0 and p["unit"] == "g", p


def test_a_sentence_that_mentions_a_quantity_fraction_stays_text():
    """A ring draws the fraction alone, so it must be the whole leaf, as the
    single-score fraction must: a sentence keeps its words, and the bare,
    wrapped or spaced fraction keeps its ring."""
    for line in (
        "I ate 75/100g of protein today and felt fine.",
        "Protein 75/100g",
        "Sugar 3 / 10 g left",
    ):
        ast = _processed(line)
        assert not _displays(ast, "unit_ratio"), (line, _all_displays(ast))
    for line in ("75/100g", "**75/100g**", "75 / 100 g"):
        assert len(_displays(_processed(line), "unit_ratio")) == 1, line
    print("  ✓  display: a sentence mentioning 75/100g stays text; the bare one rings")


def test_unit_ratio_from_kv():
    ast = _processed("Minutes: 7/8")
    units = _displays(ast, "unit_ratio")
    assert len(units) == 1, [n.content for n in _all_displays(ast)]
    node = units[0]
    assert node.type == NodeType.KEY_VALUE
    p = node.datapoint_payload
    assert p is not None
    assert p["value"] == 7.0 and p["max"] == 8.0, p
    assert p["unit"] == "Minutes" and p["from_kv"] is True, p
    # The KV display owns the subtree — no stray leaf flag inside.
    assert _all_displays(node) == [node]


# ---------------------------------------------------------------------------
# Key-value percentage bars
# ---------------------------------------------------------------------------


def test_kv_percent_bar():
    ast = _processed("GPT-5.5: 50%")
    bars = _displays(ast, "kv_percent_bar")
    assert len(bars) == 1, [n.content for n in _all_displays(ast)]
    p = bars[0].datapoint_payload
    assert p == {"percent": 50.0, "value_text": "50%"}, p


def test_kv_percent_bar_with_suffix_word():
    ast = _processed("Feedback Submission Progress: 60% Complete")
    bars = _displays(ast, "kv_percent_bar")
    assert len(bars) == 1, [n.content for n in _all_displays(ast)]
    p = bars[0].datapoint_payload
    assert p == {"percent": 60.0, "value_text": "60% Complete"}, p


def test_kv_multi_percent_not_flagged():
    # Two percentage values on one row belong to the multi-series chart
    # detection, never to a single kv bar.
    ast = _processed("May: 12.3%, 7%")
    assert _displays(ast, "kv_percent_bar") == []


# ---------------------------------------------------------------------------
# Date chips
# ---------------------------------------------------------------------------


def test_date_chip_weekday():
    ast = _processed("Mon-15")
    chips = _displays(ast, "date_chip")
    assert len(chips) == 1, [n.content for n in _all_displays(ast)]
    p = chips[0].datapoint_payload
    # ``text`` is the source line, kept so the layout generator can put the
    # chip back together as ordinary text when ### Dates → Enabled: no.
    assert p == {
        "key": "Mon",
        "day": 15,
        "subtype": "weekday_day",
        "text": "Mon-15",
    }, p


def test_date_chip_month_day():
    ast = _processed("Jun-15")
    chips = _displays(ast, "date_chip")
    assert len(chips) == 1, [n.content for n in _all_displays(ast)]
    p = chips[0].datapoint_payload
    assert p == {
        "key": "Jun",
        "day": 15,
        "subtype": "partial",
        "text": "Jun-15",
    }, p


def test_date_chip_negatives():
    # Full date (has a year), month-year (no day), misspelled weekday...
    for text in ("Jun-15, 2026", "June 2026", "Wen-14"):
        ast = _processed(text)
        assert _displays(ast, "date_chip") == [], text
    # ...and the two spellings that decline the chip on purpose. A SPACE is how
    # prose writes a date ("Delivered Jun 5"), so it stays a plain date; the
    # dash is the authored request, and a tight escape declines even that.
    for text in ("Jun 15", "Mon 15", "Jun\\-15", "Mon\\-15"):
        ast = _processed(text)
        assert _displays(ast, "date_chip") == [], text


def _types(node: MarkdownGroupNode, name: str) -> list[MarkdownGroupNode]:
    out = [node] if node.type == name else []
    for c in node.children:
        out.extend(_types(c, name))
    return out


def test_an_escape_in_a_link_label_keeps_the_link():
    # A tight or value escape declines the READING of its token. A link is an
    # element, not a reading: the escape in its label must not turn it into text.
    for text in (
        "[Tree\\-lined](agent:a)",
        "[Save 20\\%](agent:b)",
        "*[Plan 5\\-day](https://example.com)*",
    ):
        assert len(_types(_processed(text), "link")) == 1, text
    # A row of suggestions keeps all three when one label holds the escape...
    row = (
        "... [Plan a 5\\-day itinerary](agent:x) [Hotels](agent:y) [Back](agent:z) ..."
    )
    assert len(_types(_processed(row), "link")) == 3
    # ...and the label's words still decline their reading: no day chip.
    ast = _processed("[Mon\\-15](agent:m)")
    assert len(_types(ast, "link")) == 1
    assert _displays(ast, "date_chip") == []
    print("  ✓  an escape in a link's label keeps the link; its words still decline")


def test_date_chip_becomes_group():
    # The chip is wrapped into a group(text[key], text[day]) so the rule
    # layout can grid repeated chips (only group runs grid).
    ast = _processed("Mon-15")
    chip = _displays(ast, "date_chip")[0]
    assert chip.type == "group" and len(chip.children) == 2
    assert [c.type for c in chip.children] == ["text", "text"]
    assert [c.content for c in chip.children] == ["Mon", "15"]
    assert not chip.line_split_group  # gated, so it grids (not flows aside)


def test_date_chips_share_uniform_fingerprint():
    # A backticked date is inline_code as a leaf, but its chip is still
    # group(text,text) — so all chips (and only chips) share one fingerprint,
    # distinct from a plain-text header.
    from md2ui.pipeline.markdown_grouper import ASTPatternAnalyzer

    ast = _processed("**Header**\nJun-5\nJun-6\n`Jun-7`")
    ASTPatternAnalyzer(ast).fingerprints(include_unique=True)
    chips = _displays(ast, "date_chip")
    assert len(chips) == 3
    fps = {c.fingerprint_hash for c in chips}
    assert len(fps) == 1, "all chips share one fingerprint"
    header = next(c for n in [ast] for c in _all_nodes(n) if c.content == "**Header**")
    assert header.fingerprint_hash not in fps


def _all_nodes(n):
    yield n
    for c in n.children:
        yield from _all_nodes(c)


# ---------------------------------------------------------------------------
# Chart groups
# ---------------------------------------------------------------------------

_SINGLE_SERIES = """\
- Return on Equity: 14.2%
- Net Interest Margin: 3.8%
- Efficiency Ratio: 58.3%
"""

_MULTI_SERIES = """\
Key 1, Key 2:
- May: 12.3%, 7%
- Jun: 25.0%, 20%
- Jul: 19.5%, 15%
"""


def test_chart_single_series():
    ast = _processed(_SINGLE_SERIES)
    charts = _charts(ast)
    assert len(charts) == 1
    data = charts[0].chart_data
    assert data is not None
    assert data["series"] is None and data["unit"] == "%", data
    assert [r["label"] for r in data["rows"]] == [
        "Return on Equity",
        "Net Interest Margin",
        "Efficiency Ratio",
    ], data
    assert [r["values"] for r in data["rows"]] == [[14.2], [3.8], [58.3]]
    # Chart wins: the per-row kv_percent_bar flags are cleared inside.
    assert _all_displays(charts[0]) == []


def test_chart_needs_three_single_rows():
    ast = _processed("- A: 10%\n- B: 20%\n")
    assert _charts(ast) == []
    # The rows still get their individual kv bars.
    assert len(_displays(ast, "kv_percent_bar")) == 2


def test_chart_run_breaks_on_non_percent_row():
    ast = _processed(_SINGLE_SERIES + "- Assets: $89 billion\n")
    charts = _charts(ast)
    assert len(charts) == 1
    data = charts[0].chart_data
    assert data is not None and len(data["rows"]) == 3, data


def test_chart_multi_series():
    ast = _processed(_MULTI_SERIES)
    charts = _charts(ast)
    assert len(charts) == 1
    data = charts[0].chart_data
    assert data is not None
    assert data["series"] == ["Key 1", "Key 2"], data
    assert [r["label"] for r in data["rows"]] == ["May", "Jun", "Jul"]
    assert data["rows"][0]["values"] == [12.3, 7.0], data
    # The header text is absorbed into the chart container.
    header = [c for c in charts[0].children if "Key 1" in _subtree_text(c)]
    assert header, [c.content for c in charts[0].children]


def test_chart_multi_series_needs_matching_header():
    # Three names for two values per row → no chart.
    ast = _processed("Key 1, Key 2, Key 3:\n- May: 12.3%, 7%\n- Jun: 25.0%, 20%\n")
    assert _charts(ast) == []


def test_bare_kv_lines_stay_individual_bars():
    # Chart rows come only from bullet items; adjacent bare `Key: n%` lines
    # each keep their own kv bar.
    ast = _processed("GPT: 50%\nClaude: 35%\nGemini: 10%")
    assert _charts(ast) == []
    assert len(_displays(ast, "kv_percent_bar")) == 3


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


def test_round_trip_serialization():
    node = MarkdownGroupNode(content="", type=NodeType.GROUP)
    node.chart_group = True
    node.chart_data = {
        "series": ["A"],
        "unit": "%",
        "rows": [{"label": "May", "values": [1.0]}],
    }
    child = MarkdownGroupNode(content="4/8", type=NodeType.DATAPOINT)
    child.datapoint_display = "ratio_bar"
    child.datapoint_payload = {"value": 4.0, "max": 8.0, "text": "4/8"}
    node.children = [child]

    restored = MarkdownGroupNode.from_dict(node.to_dict())
    assert restored.chart_group is True
    assert restored.chart_data == node.chart_data
    assert restored.children[0].datapoint_display == "ratio_bar"
    assert restored.children[0].datapoint_payload == child.datapoint_payload


def test_round_trip_via_process():
    ast = _processed("Minutes: 7/8")
    restored = MarkdownGroupNode.from_dict(ast.to_dict())
    units = _displays(restored, "unit_ratio")
    assert len(units) == 1
    assert units[0].datapoint_payload == {
        "value": 7.0,
        "max": 8.0,
        "unit": "Minutes",
        "text": "7/8",
        "from_kv": True,
    }


# ---------------------------------------------------------------------------

TESTS = [
    test_an_escape_in_a_link_label_keeps_the_link,
    test_bare_ratio_leaf,
    test_annotate_only_ratio_still_draws_its_bar,
    test_starred_ratio_excluded,
    test_score_with_stars_label_excluded,
    test_the_of_family_is_gone,
    test_unit_ratio_leaf_trailing_word,
    test_unit_ratio_pair,
    test_annotate_only_score_still_draws_its_unit_ratio,
    test_unit_ratio_slash_quantity,
    test_a_sentence_that_mentions_a_quantity_fraction_stays_text,
    test_unit_ratio_from_kv,
    test_kv_percent_bar,
    test_kv_percent_bar_with_suffix_word,
    test_kv_multi_percent_not_flagged,
    test_date_chip_weekday,
    test_date_chip_month_day,
    test_date_chip_negatives,
    test_date_chip_becomes_group,
    test_date_chips_share_uniform_fingerprint,
    test_chart_single_series,
    test_chart_needs_three_single_rows,
    test_chart_run_breaks_on_non_percent_row,
    test_chart_multi_series,
    test_chart_multi_series_needs_matching_header,
    test_bare_kv_lines_stay_individual_bars,
    test_round_trip_serialization,
    test_round_trip_via_process,
]

if __name__ == "__main__":
    print("Datapoint Grouping Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓ {test.__name__}")
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} of {len(TESTS)} tests FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
