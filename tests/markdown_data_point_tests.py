"""
Unit tests for data_point propagation through KV splits in MarkdownGrouper.

Covers _separate_structured_content_walk: verifies that key/value child nodes
carry correctly-partitioned data_points after every KV-split path.

Run with: uv run markdown_data_point_tests.py
"""

from md2ui.pipeline.data_point_detector import (
    DataPointDetector,
    DataPointType,
)
from md2ui.pipeline.markdown_grouper import MarkdownGrouper, MarkdownGroupNode, NodeType
from md2ui.pipeline.grouper_split_apply import _partition_data_points

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_nodes(node: MarkdownGroupNode, label: str) -> list[MarkdownGroupNode]:
    """Return all nodes in subtree whose label == label."""
    results: list[MarkdownGroupNode] = []
    if node.type == label:
        results.append(node)
    for child in node.children:
        results.extend(_find_nodes(child, label))
    return results


def _leaf(node: MarkdownGroupNode, content: str) -> MarkdownGroupNode:
    """The leaf of *node*'s tree whose content is *content*."""
    if not node.children and node.content == content:
        return node
    for c in node.children:
        hit = _leaf_or_none(c, content)
        if hit is not None:
            return hit
    raise AssertionError(f"no leaf {content!r}")


def _leaf_or_none(node: MarkdownGroupNode, content: str) -> MarkdownGroupNode | None:
    try:
        return _leaf(node, content)
    except AssertionError:
        return None


def _processed(text: str) -> MarkdownGroupNode:
    detector = DataPointDetector()
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=detector)
    assert g.ast is not None
    return g.ast


# ---------------------------------------------------------------------------
# KV-first simple: value child gets partitioned data_points
# ---------------------------------------------------------------------------


def test_kv_simple_value_data_point():
    # "Price: $99.99" is one text as written (ADR-205), its CURRENCY data point
    # at the offset of the value in the line.
    leaf = _leaf(_processed("Price: $99.99"), "Price: $99.99")
    assert leaf.data_points, "the line must carry data_points"
    assert leaf.data_points[0]["type"] == DataPointType.CURRENCY
    assert leaf.data_points[0]["start"] == 7
    print("  ✓  kv simple: one text, CURRENCY at the value's offset")


# ---------------------------------------------------------------------------
# KV-first with val_seg_result: key child gets partitioned data_points
# ---------------------------------------------------------------------------


def test_kv_segmented_key_data_point():
    # "v1.0: alpha | beta" splits at the pipe only: the first piece holds the
    # VERSION data point at its start.
    leaf = _leaf(_processed("v1.0: alpha | beta"), "v1.0: alpha")
    assert leaf.data_points, "the piece must have data_points"
    assert leaf.data_points[0]["type"] == DataPointType.VERSION
    assert leaf.data_points[0]["start"] == 0
    print("  ✓  kv+segments: the piece carries VERSION at its start")


# ---------------------------------------------------------------------------
# Per-segment KV inside separator split: KV sub-children get data_points
# ---------------------------------------------------------------------------


def test_kv_after_sep_split_data_point():
    # "alpha | Cost: $20.00" → two pieces; the second is one text as written,
    # its CURRENCY data point at the value's offset in the piece.
    leaf = _leaf(_processed("alpha | Cost: $20.00"), "Cost: $20.00")
    assert leaf.data_points, "the piece must carry data_points"
    assert leaf.data_points[0]["type"] == DataPointType.CURRENCY
    assert leaf.data_points[0]["start"] == 6
    print("  ✓  sep-split: the piece carries CURRENCY at the value's offset")


# ---------------------------------------------------------------------------
# Plain KV with email value
# ---------------------------------------------------------------------------


def test_kv_email_value_data_point():
    # "Email: user@example.com" is one text as written, the address annotated
    # at its offset in the line.
    leaf = _leaf(_processed("Email: user@example.com"), "Email: user@example.com")
    assert leaf.data_points, "the line must carry data_points"
    assert leaf.data_points[0]["type"] == DataPointType.EMAIL
    assert leaf.data_points[0]["start"] == 7
    print("  ✓  kv email: one text, EMAIL at the address's offset")


# ---------------------------------------------------------------------------
# ISO date must not match inside hyphenated identifiers
# ---------------------------------------------------------------------------


def test_iso_date_not_matched_inside_hyphenated_identifier():
    # ORD-2026-02-04-78923 must pass through whole; the embedded date-shaped
    # digits must not be classified as DATE just because \b matches around `-`.
    detector = DataPointDetector()
    matches = detector.detect_all("ORD-2026-02-04-78923")
    assert not any(m["type"] == DataPointType.DATE for m in matches), (
        "ISO date must not be detected inside ORD-2026-02-04-78923"
    )
    print("  ✓  iso date not matched inside hyphenated identifier")


def test_iso_date_standalone_still_matched():
    detector = DataPointDetector()
    matches = detector.detect_all("2026-02-04")
    dates = [m for m in matches if m["type"] == DataPointType.DATE]
    assert len(dates) == 1 and dates[0]["matched"] == "2026-02-04"
    print("  ✓  iso date standalone still matched")


# ---------------------------------------------------------------------------
# `_partition_data_points` advances `search_from` past each match, so each
# identical sibling segment receives its own dp.
# ---------------------------------------------------------------------------


def test_partition_identical_sibling_segments():
    # Three identical "[L](u)" segments in parent content, each with its own
    # LINK dp. The partition must hand each child its own dp at child-local
    # coordinates (0..6 inside the 6-char segment).
    parent = "[L](u) - [L](u) - [L](u)"

    def _link_dp(start: int, end: int) -> dict:
        return {
            "type": DataPointType.LINK,
            "start": start,
            "end": end,
            "matched": parent[start:end],
            "value": {"text": "L", "url": "u", "matched": parent[start:end]},
        }

    dps = [_link_dp(0, 6), _link_dp(9, 15), _link_dp(18, 24)]
    result = [
        (NodeType.LINK, "[L](u)"),
        (NodeType.LINK, "[L](u)"),
        (NodeType.LINK, "[L](u)"),
    ]
    partitioned = _partition_data_points(parent, dps, result)
    assert len(partitioned) == 3, f"Expected 3 child lists, got {len(partitioned)}"
    for i, child_dps in enumerate(partitioned):
        assert len(child_dps) == 1, (
            f"Child #{i} should hold exactly 1 dp (partition-fix regression); "
            f"got {len(child_dps)}: {child_dps!r}"
        )
        # Remapped to child-local coordinates [0, 6].
        assert child_dps[0]["start"] == 0 and child_dps[0]["end"] == 6, (
            f"Child #{i} dp should be at local 0..6, got {child_dps[0]['start']}-{child_dps[0]['end']}"
        )
        assert child_dps[0]["type"] == DataPointType.LINK
    print("  ✓  partition fix: 3 identical sibling segments each receive one dp")


# ---------------------------------------------------------------------------
# Emoji persistence inside a LINK data point
#
# The detector's overlap rule (longest span wins) discards the nested EMOJI
# candidate inside a `[label](url)` span, so emoji info would otherwise be lost.
# `_parse_markdown_link` re-scans the label with EMOJI_CHAR_PATTERN and embeds
# the breakdown under the LINK value's `emojis` key — only when present.
# ---------------------------------------------------------------------------


def test_link_label_emoji_persisted_in_value():
    detector = DataPointDetector()
    matches = detector.detect_all("[🛒 Add](/add)")
    links = [m for m in matches if m["type"] == DataPointType.LINK]
    assert len(links) == 1, f"Expected exactly one LINK dp, got {matches!r}"
    value = links[0]["value"]
    assert value["emojis"] == [{"char": "🛒", "codepoint": "U+1F6D2"}], (
        f"LINK value should carry the label's emoji breakdown, got {value!r}"
    )
    print("  ✓  link label emoji persisted inside dp_link value")


def test_link_multi_emoji_run_flattened_per_char():
    # A maximal emoji run in the label is broken down one entry per character
    # (same shape a standalone dp_emoji produces), not one lumped entry.
    detector = DataPointDetector()
    matches = detector.detect_all("[🚀⭐ Go](/g)")
    (link,) = [m for m in matches if m["type"] == DataPointType.LINK]
    chars = [e["char"] for e in link["value"]["emojis"]]
    assert chars == ["🚀", "⭐"], f"Expected per-char breakdown, got {chars!r}"
    print("  ✓  multi-emoji run in link label flattened per character")


def test_link_without_emoji_has_no_emojis_key():
    # A plain link keeps its exact {text, url, matched} shape.
    detector = DataPointDetector()
    matches = detector.detect_all("[Plain](/x)")
    (link,) = [m for m in matches if m["type"] == DataPointType.LINK]
    assert "emojis" not in link["value"], (
        f"Plain link must not gain an 'emojis' key, got {link['value']!r}"
    )
    print("  ✓  link without emoji keeps its plain value shape")


def test_autolink_match_spans_its_brackets():
    # The bare-URL pattern excludes <>, so without the autolink pattern the URL
    # matches INSIDE the brackets and the splitter peels it out, leaving stray
    # '<' / '>' text siblings. The match must cover the whole autolink.
    detector = DataPointDetector()
    url = "https://www.markdownguide.org/basic-syntax/#html"
    (dp,) = [
        m for m in detector.detect_all(f"<{url}>") if m["type"] == DataPointType.URL
    ]
    assert dp["matched"] == f"<{url}>", dp["matched"]
    assert dp["value"]["url"] == url, dp["value"]
    assert dp["value"]["scheme"] == "https"
    # A bare URL is untouched.
    (plain,) = [m for m in detector.detect_all(url) if m["type"] == DataPointType.URL]
    assert plain["matched"] == url and plain["value"]["url"] == url
    print("  ✓  '<url>' detects as ONE url datapoint spanning its brackets")


def test_autolink_line_is_not_split():
    # End to end: the line stays a single node instead of '<' + url + '>'.
    grouper = MarkdownGrouper("<https://www.markdownguide.org/basic-syntax/#html>")
    grouper.process()
    ast = grouper.ast
    assert ast is not None
    contents = []

    def walk(n):
        if not n.children and n.content:
            contents.append(n.content)
        for c in n.children:
            walk(c)

    walk(ast)
    assert contents == ["<https://www.markdownguide.org/basic-syntax/#html>"], contents
    print("  ✓  a standalone autolink line stays ONE node (no '<' / '>' pieces)")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS = [
    test_autolink_match_spans_its_brackets,
    test_autolink_line_is_not_split,
    test_kv_simple_value_data_point,
    test_kv_segmented_key_data_point,
    test_kv_after_sep_split_data_point,
    test_kv_email_value_data_point,
    test_iso_date_not_matched_inside_hyphenated_identifier,
    test_iso_date_standalone_still_matched,
    test_partition_identical_sibling_segments,
    test_link_label_emoji_persisted_in_value,
    test_link_multi_emoji_run_flattened_per_char,
    test_link_without_emoji_has_no_emojis_key,
]

if __name__ == "__main__":
    print("Data-Point Propagation Tests")
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
