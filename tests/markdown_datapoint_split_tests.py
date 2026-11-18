"""
Unit tests for the unified data-point splitting in MarkdownGrouper.

Covers:
  - _apply_all_datapoints_to_node (via integration through process())

Run with: uv run markdown_datapoint_split_tests.py
"""

from md2ui.pipeline.data_point_detector import DataPointDetector, DataPointType
from md2ui.pipeline.markdown_grouper import MarkdownGrouper, MarkdownGroupNode, NodeType
from md2ui.pipeline.grouper_element_splits import _split_elements
from md2ui.pipeline.grouper_inline_marks import _detect_style_wrap
from md2ui.pipeline.grouper_annotate import _detect_through_markers

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


def _processed(text: str) -> MarkdownGroupNode:
    detector = DataPointDetector()
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=detector)
    assert g.ast is not None
    return g.ast


_criteria_singleton = None


def _processed_with_criteria(text: str) -> MarkdownGroupNode:
    """Run the grouper with the real SplitCriteria loaded.

    `_separate_structured_content_walk` skips its criteria gate when given
    None, which would mask gate-ordering bugs.
    """
    global _criteria_singleton
    if _criteria_singleton is None:
        from md2ui.pipeline.grouper_split_criteria import SplitCriteria

        criteria = SplitCriteria()
        _criteria_singleton = criteria
    detector = DataPointDetector()
    g = MarkdownGrouper(text)
    g.process(_criteria_singleton, detector)
    assert g.ast is not None
    return g.ast


def _as_written_shape(node: MarkdownGroupNode):
    """(type, content, text_style, children) with escaped colons read as colons."""
    content = (node.content or "").replace("\\:", ":")
    kids = [_as_written_shape(c) for c in node.children]
    return (node.type, content, node.text_style, kids)


def assert_reads_as_escaped_twin(line: str) -> None:
    """ADR-205: a `Key: value` line no display reads is the line as written —
    the same tree as its twin with the colon escaped, which never pairs."""
    twin = line.replace(":", "\\:", 1)
    got = _as_written_shape(_processed_with_criteria(line))
    want = _as_written_shape(_processed_with_criteria(twin))
    assert got == want, (line, got, want)


def _split_pairs(result):
    """(label, text) for each split piece — drops the variant column.

    `_split_elements` returns (label, text, variant): a peeled emoji or chip
    has its emphasis wrapper consumed, so the variant it selected travels with
    the piece. These tests are about WHAT splits, not how it is styled.
    """
    return None if result is None else [(p[0], p[1]) for p in result]


def _walk_nodes(node: MarkdownGroupNode):
    """Every node in the subtree, root first."""
    yield node
    for child in node.children:
        yield from _walk_nodes(child)


def _only_leaf(ast: MarkdownGroupNode) -> MarkdownGroupNode:
    """The single leaf of a one-leaf document.

    The ROOT is a container and never a leaf: a childless root's content is
    handed to a child, and ``_LABEL_IS_A_ROLE`` keeps the root from being
    relabelled into the element a one-element document holds (the generator
    reads a childless root as an empty document).
    """
    assert len(ast.children) == 1, f"not a one-leaf document: {ast.to_dict()}"
    return ast.children[0]


def _root_pieces(ast: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    """Pieces split out of a single-line document.

    A lone source line that gets separated holds its pieces in exactly one
    GROUP under the root. It is deliberately NOT ``glued_content_group``:
    glue means consecutive source lines stuck together, and one line has none
    to glue. (Whether it also carries ``line_split_group`` depends on how the
    generator will flow it — a homogeneous pill run takes its own path and
    carries neither flag.) Asserts that shape and returns the members.
    """
    assert len(ast.children) == 1, (
        f"Expected one wrapper under root, got "
        f"{[(c.type, c.content) for c in ast.children]}"
    )
    wrapper = ast.children[0]
    assert wrapper.type == NodeType.GROUP, (
        f"Root child should be a GROUP, got {wrapper.type!r}"
    )
    assert not wrapper.glued_content_group, (
        "a single split line must not be glued content"
    )
    return wrapper.children


def _make_dp(dp_type, start: int, end: int, matched: str) -> dict:
    """Build a minimal data-point dict for use in static-method tests."""
    return {
        "type": dp_type,
        "matched": matched,
        "value": matched,
        "start": start,
        "end": end,
    }


# ---------------------------------------------------------------------------
# Group A — annotate-only values: non-emoji cases
# ---------------------------------------------------------------------------


def test_annotate_only_ratio_group_keeps_the_unsplit_fingerprint():
    # `0:18 ... -2:24` (tests-render/home-dashboards/bento-cards) annotates the
    # ratio and leaves [TEXT, TEXT]. `_is_datapoint_split_group` must collapse
    # that to the fingerprint an unsplit value line carries, or the line stops
    # matching its siblings and grids differently.
    group = _processed_with_criteria("0:18 ... -2:24").children[0]
    leaf = _processed_with_criteria("0:18").children[0]
    assert group.type == NodeType.GROUP and group.line_split_group, group.type
    assert group.fingerprint_hash == leaf.fingerprint_hash, (
        f"{group.fingerprint_hash} != {leaf.fingerprint_hash}"
    )
    print("  ✓  split: an annotate-only ratio group keeps the unsplit fingerprint")


def test_a_spring_cut_value_line_fingerprints_the_same_after_serialization():
    # The layout generator reads the tree rebuilt from `to_dict()`, not the live
    # one. A line that springs cut into whole values must collapse to `text()`
    # on that tree too, or split and unsplit stat values stop sharing a hash
    # exactly where it decides runs and grids.
    from md2ui.pipeline.layout_render import load_grouping_ast_node

    live = _processed_with_criteria(
        "_Accuracy_: ... ___94%___ ... _Customers_: ... ___1,293___"
    )
    rebuilt = load_grouping_ast_node(live.to_dict())

    def hashes(node: MarkdownGroupNode) -> list[tuple]:
        out = [(node.type, node.kind_hash, node.fingerprint_hash)]
        for child in node.children:
            out.extend(hashes(child))
        return out

    assert hashes(rebuilt) == hashes(live), f"{hashes(rebuilt)} != {hashes(live)}"
    print(
        "  ✓  split: a spring-cut value line fingerprints the same after serialization"
    )


def test_an_annotated_value_grids_with_every_other_annotated_value():
    """Whichever type a value carries, the line comes out the SAME SHAPE, so a
    list of stats grids as one run instead of by data-point type.

    Under ADR-205 a `Key: value` line no display reads is one text, so the
    point is annotated on that text, at the value's offset in the line, and a
    line with no data point at all is the same shape too. A ratio (`4/8`) is
    left out: it draws as a ring, which is a display, not a text.
    """
    cases = [
        ("Rate: $50/hour", "$50/hour", DataPointType.RATE),
        ("Check-in: 3 PM", "3 PM", DataPointType.TIME),
        ("Cap: €180-200M", "€180-200M", DataPointType.RANGE),
        ("Pack: 2 items", "2 items", DataPointType.QUANTITY),
        ("Score: 4.8/5", "4.8/5", DataPointType.SCORE),
        ("Rate: abcdefgh", None, None),
    ]
    shapes, kinds = set(), set()
    for content, value, dp_type in cases:
        (node,) = _processed(content).children
        assert (node.type, node.content, node.children) == (
            NodeType.TEXT,
            content,
            [],
        ), (content, node.to_dict())
        if value is None:
            assert not node.data_points, (content, node.data_points)
        else:
            point = node.data_points[0]
            assert point["type"] == dp_type, (content, point["type"])
            start = content.index(value)
            assert (point["matched"], point["start"], point["end"]) == (
                value,
                start,
                start + len(value),
            ), (content, point)
        shapes.add(node.fingerprint_hash)
        kinds.add(node.kind_hash)
    assert len(shapes) == 1, f"value lines must share one fingerprint: {shapes}"
    assert len(kinds) == 1, f"value lines must share one kind_hash: {kinds}"
    print("  ✓  integration: every value line is one shape")


def test_an_emoji_sequence_peels_as_one_badge():
    # A joined emoji (👨‍💻), a flag, a skin tone and a keycap are each ONE
    # emoji: alone on a line, or before a label, each peels as one EMOJI node
    # holding the whole sequence, not as a node per codepoint.
    for seq in (
        "\U0001f468\u200d\U0001f4bb",
        "\U0001f1fa\U0001f1f8",
        "\U0001f44d\U0001f3fd",
        "1\ufe0f\u20e3",
    ):
        for text in (seq, f"{seq} - Label"):
            root = _processed_with_criteria(text)
            emojis = [n.content for n in _walk_nodes(root) if n.type == NodeType.EMOJI]
            assert emojis == [seq], (text, root.to_dict())
    print("  ✓  a ZWJ sequence, flag, skin tone or keycap peels as one emoji")


# ---------------------------------------------------------------------------
# Group B2 — _split_elements: the ONE element pass (emoji, links and chips),
# the function the final ungated walk uses. Pieces are (label, text, variant);
# these tests compare the (label, text) prefix via _split_pairs().
# ---------------------------------------------------------------------------


def test_boundary_dps_leading_emoji():
    # A run the prose runs into is a TEXT-EMOJI and is left in place; only an
    # explicit separator earns the peel. Same rule the chip pass applies to a
    # backtick span.
    emoji_dp = _make_dp(DataPointType.EMOJI, 0, 1, "😊")
    assert _split_elements("😊 hello", NodeType.TEXT, [emoji_dp]) is None, (
        "adjacent prose must not peel"
    )
    result = _split_elements("😊 - hello", NodeType.TEXT, [emoji_dp])
    assert _split_pairs(result) == [
        (NodeType.EMOJI, "😊"),
        (NodeType.TEXT, "- hello"),
    ], result
    print("  ✓  boundary: '😊 hello' stays inline; '😊 - hello' → EMOJI / TEXT")


def test_boundary_dps_single_trailing_emoji():
    # Regression: a lone trailing emoji must peel (the 'Received ↙️' bug).
    emoji_dp = _make_dp(DataPointType.EMOJI, 6, 7, "😊")
    assert _split_elements("hello 😊", NodeType.SEGMENT, [emoji_dp]) is None, (
        "adjacent prose must not peel"
    )
    sep_dp = _make_dp(DataPointType.EMOJI, 8, 9, "😊")
    result = _split_elements("hello - 😊", NodeType.SEGMENT, [sep_dp])
    assert _split_pairs(result) == [
        (NodeType.SEGMENT, "hello -"),
        (NodeType.EMOJI, "😊"),
    ], result
    print("  ✓  boundary: trailing emoji peels only when separated")


def test_boundary_dps_mid_text_emoji_not_peeled():
    emoji_dp = _make_dp(DataPointType.EMOJI, 6, 7, "😊")
    result = _split_elements("a b c 😊 d", NodeType.TEXT, [emoji_dp])
    # emoji is interior (text after it) → no boundary peel.
    assert result is None, result
    print("  ✓  boundary: mid-text emoji → None")


# ---------------------------------------------------------------------------
# Group C — Integration through process()
# ---------------------------------------------------------------------------


def test_integration_dp_in_middle():
    # Through the real pipeline: the sentence keeps its value (ADR-205).
    ast = _processed("Entry fee $20 total")
    assert not _find_nodes(ast, NodeType.DATAPOINT), (
        "a value inside a sentence must not become its own node"
    )
    print("  ✓  integration: a value inside a sentence stays in the sentence")


def test_integration_datapoint_annotations_preserved():
    # No node is cut out, but the ANNOTATION still rides on the leaf that holds
    # the value — which is what the displays and ## Fixed colors read.
    ast = _processed("Fee $99.99")
    assert not _find_nodes(ast, NodeType.DATAPOINT)
    carrier = next((n for n in _walk_nodes(ast) if n.data_points), None)
    assert carrier is not None, f"no leaf carries data_points: {ast.to_dict()}"
    assert carrier.data_points[0]["type"] == DataPointType.CURRENCY
    matched = carrier.data_points[0]["matched"]
    assert matched == "$99.99", f"expected the currency span, got {matched!r}"
    print("  ✓  integration: an uncut leaf still carries its datapoint annotation")


def test_integration_dimension_annotation_is_preserved():
    ast = _processed("1920 x 1080")
    assert not _find_nodes(ast, NodeType.DATAPOINT)
    carrier = next((n for n in _walk_nodes(ast) if n.data_points), None)
    assert carrier is not None, f"no leaf carries data_points: {ast.to_dict()}"
    assert carrier.type == NodeType.TEXT
    assert carrier.content == "1920 x 1080"
    assert len(carrier.data_points) == 1
    dp = carrier.data_points[0]
    assert dp["type"] == DataPointType.DIMENSION
    assert (dp["matched"], dp["start"], dp["end"]) == ("1920 x 1080", 0, 11)
    print("  ✓  integration: an uncut dimension keeps its exact annotation")


def test_integration_duration_annotation_is_preserved():
    content = "4 hours 35 minutes"
    ast = _processed(content)
    assert not _find_nodes(ast, NodeType.DATAPOINT)
    carrier = next((n for n in _walk_nodes(ast) if n.data_points), None)
    assert carrier is not None, f"no leaf carries data_points: {ast.to_dict()}"
    assert carrier.type == NodeType.TEXT
    assert carrier.content == content
    assert len(carrier.data_points) == 1
    dp = carrier.data_points[0]
    assert dp["type"] == DataPointType.DURATION
    assert (dp["matched"], dp["start"], dp["end"]) == (content, 0, len(content))
    print("  ✓  integration: an uncut duration keeps its exact annotation")


def test_integration_version_annotation_is_preserved():
    content = "v1.2.3"
    ast = _processed(content)
    assert not _find_nodes(ast, NodeType.DATAPOINT)
    carrier = next((n for n in _walk_nodes(ast) if n.data_points), None)
    assert carrier is not None, f"no leaf carries data_points: {ast.to_dict()}"
    assert carrier.type == NodeType.TEXT
    assert carrier.content == content
    assert len(carrier.data_points) == 1
    dp = carrier.data_points[0]
    assert dp["type"] == DataPointType.VERSION
    assert (dp["matched"], dp["start"], dp["end"]) == (content, 0, len(content))
    print("  ✓  integration: an uncut version keeps its exact annotation")


def test_integration_date_range_annotation_is_preserved():
    content = "Jan 12-28, 2026"
    ast = _processed(content)
    assert not _find_nodes(ast, NodeType.DATAPOINT)
    carrier = next((n for n in _walk_nodes(ast) if n.data_points), None)
    assert carrier is not None, f"no leaf carries data_points: {ast.to_dict()}"
    assert carrier.type == NodeType.TEXT
    assert carrier.content == content
    assert len(carrier.data_points) == 1
    dp = carrier.data_points[0]
    assert dp["type"] == DataPointType.DATE_RANGE
    assert (dp["matched"], dp["start"], dp["end"]) == (content, 0, len(content))
    print("  ✓  integration: an uncut date range keeps its exact annotation")


def _assert_integration_annotation_is_preserved(content: str, kind: DataPointType):
    ast = _processed(content)
    assert not _find_nodes(ast, NodeType.DATAPOINT)
    carrier = next((n for n in _walk_nodes(ast) if n.data_points), None)
    assert carrier is not None, f"no leaf carries data_points: {ast.to_dict()}"
    assert carrier.type == NodeType.TEXT
    assert carrier.content == content
    assert len(carrier.data_points) == 1
    dp = carrier.data_points[0]
    assert dp["type"] == kind
    assert (dp["matched"], dp["start"], dp["end"]) == (content, 0, len(content))


def test_integration_file_size_annotation_is_preserved():
    _assert_integration_annotation_is_preserved("500 MB", DataPointType.FILE_SIZE)
    print("  ✓  integration: an uncut file size keeps its exact annotation")


def test_integration_phone_annotation_is_preserved():
    _assert_integration_annotation_is_preserved("(555) 123-4567", DataPointType.PHONE)
    print("  ✓  integration: an uncut phone keeps its exact annotation")


def test_integration_url_annotation_is_preserved():
    _assert_integration_annotation_is_preserved(
        "https://example.com", DataPointType.URL
    )
    print("  ✓  integration: an uncut URL keeps its exact annotation")


def test_integration_date_annotation_is_preserved():
    _assert_integration_annotation_is_preserved("May 2017", DataPointType.DATE)
    print("  ✓  integration: an uncut date keeps its exact annotation")


def test_integration_emoji_and_dp_coexist():
    # The ELEMENT peel is untouched by ADR-205: the author separated the emoji
    # with ` - `, so it still peels. The value rides on the text beside it.
    ast = _processed("😊 - costs $5")
    assert _find_nodes(ast, NodeType.EMOJI), "Expected EMOJI node"
    assert not _find_nodes(ast, NodeType.DATAPOINT), (
        "`costs $5` is prose — the value must not be cut out of it"
    )
    print("  ✓  integration: the emoji still peels; the value stays inline")


def test_emoji_before_a_colon_line():
    # The separated emoji peels; the rest is the text as written, colon kept
    # (ADR-205), with no emoji left in it.
    ast = _processed("⚽ - FIFA World Cup 2026: Tournament Overview")
    emoji_nodes = _find_nodes(ast, NodeType.EMOJI)
    assert [n.content for n in emoji_nodes] == ["⚽"], emoji_nodes
    segs = [n.content for n in _find_nodes(ast, NodeType.SEGMENT)]
    assert segs == ["FIFA World Cup 2026: Tournament Overview"], segs
    print("  ✓  emoji + colon line: emoji peeled, the text keeps its colon")


def test_emoji_before_separator_and_colon_line():
    # Emoji must be extracted BEFORE the separator split, and the remainder must
    # then be split by '-' into segments; the colon stays in its segment.
    ast = _processed("✅ - **Personal Record** - Fastest 5K: 23:45")
    emoji_nodes = _find_nodes(ast, NodeType.EMOJI)
    assert [n.content for n in emoji_nodes] == ["✅"], emoji_nodes
    segs = _find_nodes(ast, NodeType.SEGMENT)
    assert [n.content for n in segs] == [
        "**Personal Record**",
        "Fastest 5K: 23:45",
    ], [n.content for n in segs]
    for seg in segs:
        assert not _find_nodes(seg, NodeType.EMOJI), seg.to_dict()
    print("  ✓  emoji-first: '✅ - Record - Key: val' → emoji / segment / segment")


def test_integration_plain_prose_not_split():
    ast = _processed("The quick brown fox jumps over the lazy dog")
    dps = _find_nodes(ast, NodeType.DATAPOINT)
    assert not dps, (
        f"Expected no DATAPOINT nodes in prose, got {[n.content for n in dps]}"
    )
    print("  ✓  integration: prose without data points → no DATAPOINT nodes")


def test_score_decimal_denominator():
    # '4.8/5.0' must be a single SCORE, with no '.0' left for NUMBER. SCORE is
    # annotation-only, so the match is read off the leaf it annotates.
    ast = _processed("4.8/5.0 ⭐")
    found = [dp for n in _walk_nodes(ast) for dp in n.data_points]
    scores = [d for d in found if d["type"] == DataPointType.SCORE]
    assert len(scores) == 1, (
        f"Expected one SCORE annotation, got {[(d['type'].value, d['matched']) for d in found]!r}"
    )
    assert scores[0]["matched"] == "4.8/5.0", (
        f"SCORE matched should be '4.8/5.0', got {scores[0]['matched']!r}"
    )
    # No NUMBER should leak through for the orphaned '.0'.
    nums = [d for d in found if d["type"] == DataPointType.NUMBER]
    assert not nums, f"No NUMBER expected, got {[d['matched'] for d in nums]}"
    print("  ✓  score: '4.8/5.0' detected as single SCORE (decimal denominator)")


def test_bold_colon_line_currency_with_space():
    # The bold marker must not shift the offset: the line is one text
    # (ADR-205) and the point names exactly its span.
    ast = _processed_with_criteria("- **Total: $85.00 MXN**")
    (item,) = ast.children
    assert (item.type, item.content, item.children) == (
        NodeType.LIST_ITEM,
        "**Total: $85.00 MXN**",
        [],
    ), item.to_dict()
    (point,) = item.data_points
    assert point["type"] == DataPointType.CURRENCY
    assert point["matched"] == "$85.00 MXN"
    assert item.content[point["start"] : point["end"]] == "$85.00 MXN", point
    print("  ✓  bold colon line + CURRENCY: the point names its span in the text")


def test_prose_adjacent_leading_emoji_is_a_text_emoji():
    # With nothing separating it, 🔑 belongs to the sentence and stays in it as
    # a text-emoji, drawn at the surrounding text size. "🔑 - Add …" earns the
    # peel.
    text = (
        "🔑 Add a passkey to log in instantly using your fingerprint, "
        "face, or screen lock."
    )
    ast = _processed_with_criteria(text)
    emoji_nodes = _find_nodes(ast, NodeType.EMOJI)
    assert not emoji_nodes, "a prose-adjacent 🔑 is a TEXT-EMOJI, not a peel"
    leaves: list = []

    def collect(n):
        if not n.children and n.content:
            leaves.append(n.content)
        for c in n.children:
            collect(c)

    collect(ast)
    assert len(leaves) == 1, leaves
    assert leaves[0].startswith("🔑 Add a passkey"), (
        f"the emoji stays with its prose, got {leaves[0]!r}"
    )
    print("  ✓  a prose-adjacent leading 🔑 stays a text-emoji, not a peel")


# ---------------------------------------------------------------------------
# Group D — values in styled and plain text, through process()
# ---------------------------------------------------------------------------


def test_integration_time_hours_detected():
    ast = _processed("3 PM")
    assert not _find_nodes(ast, NodeType.DATAPOINT)
    carrier = next(n for n in _walk_nodes(ast) if n.data_points)
    assert carrier.type == NodeType.TEXT
    assert carrier.content == "3 PM"
    point = carrier.data_points[0]
    assert point["type"] == DataPointType.TIME
    assert point["value"]["period"] == "PM"
    assert point["value"]["hour"] == 15
    assert (point["matched"], point["start"], point["end"]) == ("3 PM", 0, 4)
    print("  ✓  integration: '3 PM' stays inline with TIME annotation, hour=15")


# ---------------------------------------------------------------------------
# Group G — Bare signed number change detection
# ---------------------------------------------------------------------------


def test_change_bare_positive_integer():
    dps = DataPointDetector().detect_all("+3")
    assert len(dps) == 1 and dps[0]["type"] == DataPointType.CHANGE, (
        f"Expected 1 CHANGE, got {dps!r}"
    )
    assert dps[0]["value"]["direction"] == "increase"
    assert dps[0]["value"]["type"] == "bare"
    print("  ✓  change: '+3' → CHANGE bare increase")


def test_change_bare_negative_integer():
    dps = DataPointDetector().detect_all("-5")
    assert len(dps) == 1 and dps[0]["type"] == DataPointType.CHANGE, (
        f"Expected 1 CHANGE, got {dps!r}"
    )
    assert dps[0]["value"]["direction"] == "decrease"
    assert dps[0]["value"]["type"] == "bare"
    print("  ✓  change: '-5' → CHANGE bare decrease")


def test_change_bare_decimal():
    dps = DataPointDetector().detect_all("+2.5")
    assert len(dps) == 1 and dps[0]["type"] == DataPointType.CHANGE, (
        f"Expected 1 CHANGE, got {dps!r}"
    )
    assert dps[0]["value"]["type"] == "bare"
    print("  ✓  change: '+2.5' → CHANGE bare decimal")


def test_change_bare_does_not_override_quantity():
    # +3 points must still be detected as quantity (longer match wins)
    dps = DataPointDetector().detect_all("+3 points")
    assert len(dps) == 1 and dps[0]["type"] == DataPointType.CHANGE, (
        f"Expected 1 CHANGE, got {dps!r}"
    )
    assert dps[0]["value"]["type"] == "quantity", (
        f"Expected quantity, got {dps[0]['value']['type']!r}"
    )
    print("  ✓  change: '+3 points' → CHANGE quantity (not bare)")


def test_change_bare_does_not_override_percentage():
    # +3% must still be detected as percentage (longer match wins)
    dps = DataPointDetector().detect_all("+3%")
    assert len(dps) == 1 and dps[0]["type"] == DataPointType.CHANGE, (
        f"Expected 1 CHANGE, got {dps!r}"
    )
    assert dps[0]["value"]["type"] == "percentage", (
        f"Expected percentage, got {dps[0]['value']['type']!r}"
    )
    print("  ✓  change: '+3%' → CHANGE percentage (not bare)")


def test_annotate_only_change_and_emoji_stay_one_leaf():
    ast = _processed("+11.18% 📈")
    leaves = [n for n in _walk_nodes(ast) if not n.children and n.content]
    assert [(n.type, n.content) for n in leaves] == [(NodeType.TEXT, "+11.18% 📈")]
    change, emoji = leaves[0].data_points
    assert change["type"] == DataPointType.CHANGE
    assert (change["matched"], change["start"], change["end"]) == (
        "+11.18%",
        0,
        7,
    )
    assert emoji["type"] == DataPointType.EMOJI
    assert (emoji["matched"], emoji["start"], emoji["end"]) == ("📈", 8, 9)
    print("  ✓  integration: '+11.18% 📈' stays one annotated text leaf")


def test_number_not_detected_in_suffix_identifier():
    # X-2026 — number after word-char+hyphen must not be detected.
    dps = DataPointDetector().detect_all("X-2026")
    assert not dps, f"Expected no detections for 'X-2026', got {dps!r}"
    print("  ✓  number: 'X-2026' → no detections")


def test_number_not_detected_in_prefix_identifier():
    # 2024-X — number before hyphen+word-char must not be detected.
    dps = DataPointDetector().detect_all("2024-X")
    assert not dps, f"Expected no detections for '2024-X', got {dps!r}"
    print("  ✓  number: '2024-X' → no detections")


def test_number_not_detected_in_sandwiched_identifier():
    # X-2024-Y — number sandwiched between word chars via hyphens.
    dps = DataPointDetector().detect_all("X-2024-Y")
    assert not dps, f"Expected no detections for 'X-2024-Y', got {dps!r}"
    print("  ✓  number: 'X-2024-Y' → no detections")


def test_standalone_number_still_detected():
    # A bare number with no surrounding word-char+hyphen context must detect.
    dps = DataPointDetector().detect_all("2026")
    assert len(dps) == 1 and dps[0]["type"] == DataPointType.NUMBER, (
        f"Expected 1 NUMBER for '2026', got {dps!r}"
    )
    print("  ✓  number: '2026' standalone → NUMBER")


def test_change_not_detected_inside_identifier():
    # Hyphens inside alphanumeric codes must not produce CHANGE detections.
    dps = DataPointDetector().detect_all("OAX-2024-789456")
    change_dps = [d for d in dps if d["type"] == DataPointType.CHANGE]
    assert not change_dps, f"Expected no CHANGE inside identifier, got {change_dps!r}"
    print("  ✓  change: 'OAX-2024-789456' → no CHANGE detections")


def test_change_bare_still_detected_standalone():
    # A bare -2024 (not attached to a preceding word char) must still detect.
    dps = DataPointDetector().detect_all("-2024")
    assert len(dps) == 1 and dps[0]["type"] == DataPointType.CHANGE, (
        f"Expected 1 CHANGE for '-2024', got {dps!r}"
    )
    assert dps[0]["value"]["direction"] == "decrease"
    print("  ✓  change: '-2024' standalone → CHANGE bare decrease")


def test_date_hyphenated_dmy():
    # 10-10-2026 must be detected as a DATE, not as CHANGE fragments.
    dps = DataPointDetector().detect_all("10-10-2026")
    assert len(dps) == 1 and dps[0]["type"] == DataPointType.DATE, (
        f"Expected 1 DATE for '10-10-2026', got {dps!r}"
    )
    print("  ✓  date: '10-10-2026' → DATE (not CHANGE)")


# ---------------------------------------------------------------------------
# Group G — Emoji inside style markers (bold / italic / bold-italic)
# ---------------------------------------------------------------------------


def test_detect_style_wrap_bold_italic():
    result = _detect_style_wrap("***⭐ Popular***", 0, 15)
    assert result == (3, 3, 12), f"Expected (3, 3, 12), got {result!r}"
    print("  ✓  detect_style_wrap: '***⭐ Popular***' → (3, 3, 12)")


def test_detect_style_wrap_bold():
    result = _detect_style_wrap("**⭐ Popular**", 0, 13)
    assert result == (2, 2, 11), f"Expected (2, 2, 11), got {result!r}"
    print("  ✓  detect_style_wrap: '**⭐ Popular**' → (2, 2, 11)")


def test_detect_style_wrap_italic():
    result = _detect_style_wrap("*⭐ Popular*", 0, 11)
    assert result == (1, 1, 10), f"Expected (1, 1, 10), got {result!r}"
    print("  ✓  detect_style_wrap: '*⭐ Popular*' → (1, 1, 10)")


def test_detect_style_wrap_no_markers():
    result = _detect_style_wrap("⭐ Popular", 0, 10)
    assert result is None, f"Expected None, got {result!r}"
    print("  ✓  detect_style_wrap: no markers → None")


def test_detect_style_wrap_mismatched():
    # Mismatched marker counts (3 leading, 2 trailing) should return None
    s = "***⭐ Popular**"
    result = _detect_style_wrap(s, 0, len(s))
    assert result is None, f"Expected None for mismatched markers, got {result!r}"
    print("  ✓  detect_style_wrap: mismatched markers → None")


def test_split_boundary_emoji_bold_italic():
    # '***⭐ Popular***' — emoji at inner boundary of bold-italic markers
    # ⭐ is at position 3 (after '***'), len('***⭐ Popular***') == 15
    emoji_dp = _make_dp(DataPointType.EMOJI, 3, 4, "⭐")
    result = _split_elements("***⭐ - Popular***", NodeType.TEXT, [emoji_dp])
    assert _split_pairs(result) == [
        (NodeType.EMOJI, "⭐"),
        (NodeType.TEXT, "***- Popular***"),
    ], f"Expected EMOJI + styled TEXT, got {result!r}"
    print("  ✓  split_boundary_emojis: '***⭐ Popular***' → EMOJI + '***Popular***'")


def test_split_boundary_emoji_bold():
    # '**⭐ Popular**' — emoji at inner boundary of bold markers
    emoji_dp = _make_dp(DataPointType.EMOJI, 2, 3, "⭐")
    result = _split_elements("**⭐ - Popular**", NodeType.TEXT, [emoji_dp])
    assert _split_pairs(result) == [
        (NodeType.EMOJI, "⭐"),
        (NodeType.TEXT, "**- Popular**"),
    ], f"Expected EMOJI + styled TEXT, got {result!r}"
    print("  ✓  split_boundary_emojis: '**⭐ Popular**' → EMOJI + '**Popular**'")


def test_split_boundary_emoji_italic():
    # '*⭐ Popular*' — emoji at inner boundary of italic markers
    emoji_dp = _make_dp(DataPointType.EMOJI, 1, 2, "⭐")
    result = _split_elements("*⭐ - Popular*", NodeType.TEXT, [emoji_dp])
    assert _split_pairs(result) == [
        (NodeType.EMOJI, "⭐"),
        (NodeType.TEXT, "*- Popular*"),
    ], f"Expected EMOJI + styled TEXT, got {result!r}"
    print("  ✓  split_boundary_emojis: '*⭐ Popular*' → EMOJI + '*Popular*'")


def test_integration_emoji_bold_italic_heading():
    ast = _processed("# ***⭐ - Popular***")
    emojis = _find_nodes(ast, NodeType.EMOJI)
    assert len(emojis) == 1, (
        f"Expected 1 EMOJI node, got {[n.content for n in emojis]!r}"
    )
    assert emojis[0].content == "⭐", f"Unexpected emoji content: {emojis[0].content!r}"
    print("  ✓  integration: '# ***⭐ Popular***' → 1 EMOJI node with '⭐'")


def test_integration_emoji_bold_heading():
    ast = _processed("# **⭐ - Popular**")
    emojis = _find_nodes(ast, NodeType.EMOJI)
    assert len(emojis) == 1, (
        f"Expected 1 EMOJI node, got {[n.content for n in emojis]!r}"
    )
    assert emojis[0].content == "⭐", f"Unexpected emoji content: {emojis[0].content!r}"
    print("  ✓  integration: '# **⭐ Popular**' → 1 EMOJI node with '⭐'")


def test_integration_emoji_italic_heading():
    ast = _processed("# *⭐ - Popular*")
    emojis = _find_nodes(ast, NodeType.EMOJI)
    assert len(emojis) == 1, (
        f"Expected 1 EMOJI node, got {[n.content for n in emojis]!r}"
    )
    assert emojis[0].content == "⭐", f"Unexpected emoji content: {emojis[0].content!r}"
    print("  ✓  integration: '# *⭐ Popular*' → 1 EMOJI node with '⭐'")


# ---------------------------------------------------------------------------
# Group: SCORE single-star + decimal pattern
# ---------------------------------------------------------------------------


def test_score_single_star_detected_forward():
    detector = DataPointDetector()
    dps = detector.detect_all("⭐ 4.9")
    assert len(dps) == 1, f"Expected 1 dp, got {dps!r}"
    assert dps[0]["type"] == DataPointType.SCORE
    assert dps[0]["start"] == 0 and dps[0]["end"] == 5
    print("  ✓  score: '⭐ 4.9' → single SCORE dp")


def test_score_single_star_detected_no_space():
    detector = DataPointDetector()
    dps = detector.detect_all("⭐4.9")
    assert len(dps) == 1 and dps[0]["type"] == DataPointType.SCORE
    print("  ✓  score: '⭐4.9' → single SCORE dp")


def test_score_single_star_detected_reverse():
    detector = DataPointDetector()
    dps = detector.detect_all("4.9 ⭐")
    assert len(dps) == 1 and dps[0]["type"] == DataPointType.SCORE
    print("  ✓  score: '4.9 ⭐' → single SCORE dp")


def test_score_single_star_glyph_variants():
    detector = DataPointDetector()
    for s in ("★ 4.5", "☆4.0", "4.5★"):
        dps = detector.detect_all(s)
        assert len(dps) == 1 and dps[0]["type"] == DataPointType.SCORE, (
            f"Expected SCORE for {s!r}, got {dps!r}"
        )
    print("  ✓  score: ★/☆ glyph variants → SCORE dp")


def test_integration_score_keeps_star_with_number():
    # `**Sundown café** ⭐ 4.9` is prose (the name is regular text), so the SCORE
    # is not cut out; it is an annotation on the line.
    ast = _processed("**Sundown café** ⭐ 4.9")
    assert not _find_nodes(ast, NodeType.DATAPOINT)
    kinds = {p["type"] for n in _walk_nodes(ast) for p in n.data_points}
    assert DataPointType.SCORE in kinds, f"SCORE annotation lost, got {kinds!r}"
    print("  ✓  integration: a star score stays inline but keeps its annotation")


def test_link_whole_content():
    # Single link covering the whole content → a LINK leaf under the root, not
    # a relabelled ROOT: the generator reads a childless root as empty.
    ast = _processed_with_criteria("[click](url)")
    leaf = _only_leaf(ast)
    assert ast.type == "root", f"the root must stay a root, got {ast.type!r}"
    assert leaf.type == NodeType.LINK, f"Expected LINK, got {leaf.type!r}"
    assert leaf.content == "[click](url)", f"Got {leaf.content!r}"
    assert not leaf.children
    assert leaf.data_points and leaf.data_points[0]["type"] == DataPointType.LINK
    print("  ✓  link whole content: '[click](url)' → a LINK leaf under the root")


def test_link_leading_extracted():
    # Boundary rule: leading link peels; trailing text becomes a sibling.
    # The lone line's pieces live inside one glued group under root.
    ast = _processed_with_criteria("[click](url) - then more.")
    pieces = _root_pieces(ast)
    assert len(pieces) == 2, f"Expected 2 children, got {len(pieces)}"
    assert pieces[0].type == NodeType.LINK
    assert pieces[0].content == "[click](url)"
    assert pieces[1].content == "then more."
    print(
        "  ✓  link leading: '[click](url) then more.' → glued[LINK, TEXT('then more.')]"
    )


def test_link_mid_text_inline():
    # Boundary rule: a link in the middle stays inline as raw markdown with
    # only a `dp_link` annotation on the node. The user's reference case.
    ast = _processed_with_criteria("See [this](url) now.")
    leaf = _only_leaf(ast)
    assert not leaf.children, f"Expected no children, got {len(leaf.children)}"
    assert leaf.content == "See [this](url) now.", f"Got {leaf.content!r}"
    assert any(dp["type"] == DataPointType.LINK for dp in leaf.data_points), (
        "Expected a LINK datapoint annotation on the node"
    )
    print("  ✓  link mid-text: 'See [this](url) now.' stays inline w/ dp_link")


def test_link_both_ends():
    # Both boundary links peel; middle link stays embedded in the middle text.
    ast = _processed_with_criteria("[a](u) - middle [c](u) end - [b](u)")
    pieces = _root_pieces(ast)
    assert len(pieces) == 3, f"Expected 3 children, got {len(pieces)}"
    assert pieces[0].type == NodeType.LINK and pieces[0].content == "[a](u)"
    middle = pieces[1]
    assert middle.content == "middle [c](u) end", f"middle: got {middle.content!r}"
    assert any(dp["type"] == DataPointType.LINK for dp in middle.data_points), (
        "Middle node should retain the mid-link as a dp_link annotation"
    )
    assert pieces[2].type == NodeType.LINK and pieces[2].content == "[b](u)"
    print("  ✓  link both ends: middle link kept inline as markdown")


def test_link_italic_wrap():
    # *[link](url)* → LINK with the surrounding `*` markers preserved on content.
    ast = _processed_with_criteria("*[Italic link](url)*")
    leaf = _only_leaf(ast)
    assert leaf.type == NodeType.LINK, f"Expected LINK root, got {ast.type!r}"
    assert leaf.content == "*[Italic link](url)*", f"Got {leaf.content!r}"
    print("  ✓  link italic wrap: '*[Italic link](url)*' → LINK keeps '*' wrappers")


def test_link_bold_wrap():
    ast = _processed_with_criteria("**[Bold link](url)**")
    leaf = _only_leaf(ast)
    assert leaf.type == NodeType.LINK
    assert leaf.content == "**[Bold link](url)**", f"Got {leaf.content!r}"
    print("  ✓  link bold wrap: '**[Bold link](url)**' → LINK keeps '**' wrappers")


def test_link_bold_italic_wrap():
    # `***` must not be matched as `**`; the marker length comes from
    # `_detect_style_wrap`.
    ast = _processed_with_criteria("***[BoldItalic link](url)***")
    leaf = _only_leaf(ast)
    assert leaf.type == NodeType.LINK
    assert leaf.content == "***[BoldItalic link](url)***", f"Got {leaf.content!r}"
    print("  ✓  link bold-italic wrap: '***...***' keeps all three '*'")


def test_link_after_a_bold_label():
    # '- **Listen:** [Spotify](url)' is one text (ADR-205): the bold label and
    # its colon as written, the link inline and annotated at its offset. The
    # boundary peel must not cut the link out of the line.
    ast = _processed_with_criteria("- **Listen:** [Spotify](url)")
    (item,) = ast.children
    assert (item.type, item.content, item.children) == (
        NodeType.LIST_ITEM,
        "**Listen:** [Spotify](url)",
        [],
    ), item.to_dict()
    links = [p for p in item.data_points if p["type"] == DataPointType.LINK]
    assert len(links) == 1, item.data_points
    assert item.content[links[0]["start"] : links[0]["end"]] == "[Spotify](url)"
    print("  ✓  link after a bold label: one text, the link inline")


def test_links_pipe_separated_flat():
    ast = _processed_with_criteria("[A](u) | [B](u) | [C](u)")
    pieces = _root_pieces(ast)
    assert len(pieces) == 3, f"Expected 3 LINK siblings, got {len(pieces)}"
    for child, expected in zip(pieces, ["[A](u)", "[B](u)", "[C](u)"]):
        assert child.type == NodeType.LINK and child.content == expected, (
            f"Got {child.type!r}: {child.content!r}"
        )
        assert child.data_points and child.data_points[0]["type"] == DataPointType.LINK
    print("  ✓  links pipe-sep: '[A]|[B]|[C]' → 3 LINK siblings in one glued group")


def test_links_dash_separated_flat():
    ast = _processed_with_criteria("[A](u) - [B](u) - [C](u)")
    pieces = _root_pieces(ast)
    assert len(pieces) == 3
    for child in pieces:
        assert child.type == NodeType.LINK
    print("  ✓  links dash-sep: '[A] - [B] - [C]' → 3 LINK siblings in one glued group")


def test_links_between_dots_stay_one_text():
    # A dot divides nothing (ADR-205): the line is one text, links inline.
    ast = _processed_with_criteria("[A](u) • [B](u) • [C](u)")
    assert [c.type for c in ast.children] == [NodeType.TEXT], ast.children
    print("  ✓  '[A] • [B] • [C]' stays one text; a dot is not a separator")


def test_links_identical_partition():
    # Regression for `_partition_data_points` `search_from = idx + length`:
    # three identical sibling LINK segments must each receive their own dp.
    ast = _processed_with_criteria("[Link](/u) - [Link](/u) - [Link](/u)")
    pieces = _root_pieces(ast)
    links = [c for c in pieces if c.type == NodeType.LINK]
    assert len(links) == 3, f"Expected 3 LINK siblings, got {len(pieces)} children"
    for i, link in enumerate(links):
        assert link.data_points, f"LINK #{i} missing its dp (partition bug)"
        assert link.data_points[0]["type"] == DataPointType.LINK
    print("  ✓  partition fix: 3 identical sibling LINKs each carry their dp")


# ---------------------------------------------------------------------------
# Group G — Flat EMOJI when content is `EMOJI <sep> EMOJI`
#
# The `_is_pure_emoji_separator_content` gate: when the whole
# content is emojis separated by spaced Pass-2 separators, Step 1.5 is skipped
# and `_split_separators` produces a flat sibling list (matching how links
# already resolve via `tests-links.md`'s last samples).
# ---------------------------------------------------------------------------


def test_emojis_dash_separated_flat():
    ast = _processed_with_criteria("⭐ - 🚀 - ⚛️ - 🍎 - 🪴")
    pieces = _root_pieces(ast)
    assert len(pieces) == 5, f"Expected 5 EMOJI siblings, got {len(pieces)}"
    for child in pieces:
        assert child.type == NodeType.EMOJI, f"Got {child.type!r}: {child.content!r}"
    contents = [c.content for c in pieces]
    assert contents == ["⭐", "🚀", "⚛️", "🍎", "🪴"], f"Got {contents}"
    print(
        "  ✓  emojis dash-sep: '⭐ - 🚀 - ⚛️ - 🍎 - 🪴' → 5 EMOJI siblings in one glued group"
    )


def test_emojis_between_dots_stay_one_text():
    ast = _processed_with_criteria("⭐ • 🚀 • ⚛️ • 🍎 • 🪴")
    assert [c.type for c in ast.children] == [NodeType.TEXT], ast.children
    print("  ✓  '⭐ • 🚀 • …' stays one text; a dot is not a separator")


def test_emojis_pipe_separated_flat():
    ast = _processed_with_criteria("⭐ | 🚀 | ⚛️")
    pieces = _root_pieces(ast)
    assert len(pieces) == 3
    for child in pieces:
        assert child.type == NodeType.EMOJI
    print("  ✓  emojis pipe-sep: '⭐ | 🚀 | ⚛️' → 3 EMOJI siblings in one glued group")


def test_emojis_em_dash_separated_flat():
    # An em dash is not a separator: it cannot be escaped, so an author
    # could not decline it (grouper_inline_marks._LINE_SEPARATORS). The
    # ASCII `-` is the spelling that separates an emoji run.
    pieces = _root_pieces(_processed_with_criteria("⭐ - 🚀 - ⚛️"))
    assert len(pieces) == 3
    for child in pieces:
        assert child.type == NodeType.EMOJI
    em = _processed_with_criteria("⭐ — 🚀 — ⚛️")
    # Not separated means ONE leaf, which under the root is one child — not zero.
    em_leaf = _only_leaf(em)
    assert not em_leaf.children and em_leaf.type != NodeType.EMOJI, (
        f"an em dash must not separate, got {em_leaf.to_dict()!r}"
    )
    print("  ✓  emoji run: ` - ` separates, ` — ` does not")


def test_mixed_emoji_text_does_not_flatten():
    # 'word' between the emojis prevents the pure-emoji-separator gate from
    # firing → existing Step 1.5 boundary peel runs. We just assert the
    # boundary emojis are still peeled (not flat, but at least extracted).
    ast = _processed_with_criteria("⭐ - word - 🚀")
    emojis = _find_nodes(ast, NodeType.EMOJI)
    contents = {e.content for e in emojis}
    assert contents == {"⭐", "🚀"}, f"Expected both boundary emojis, got {contents}"
    # And the helper did NOT fire — so the middle text node still exists.
    non_emoji = [c for c in ast.children if c.type != NodeType.EMOJI]
    assert non_emoji, "Mixed content should still produce a non-EMOJI middle child"
    print("  ✓  mixed emoji+text: '⭐ word - 🚀' falls back to legacy boundary peel")


def test_single_emoji_prose_not_flat():
    # The emoji peel before the split criteria still fires for prose content with a leading
    # emoji. Helper returns False (only one emoji), so behavior is unchanged.
    ast = _processed_with_criteria("🔑 - Add a passkey today")
    pieces = _root_pieces(ast)
    emojis = _find_nodes(ast, NodeType.EMOJI)
    assert len(emojis) == 1 and emojis[0].content == "🔑"
    # The text node should still carry the rest of the prose.
    other = [c for c in pieces if c.type != NodeType.EMOJI]
    assert any("Add a passkey" in c.content for c in other), (
        f"Expected prose remainder, got {[(c.type, c.content) for c in pieces]}"
    )
    print("  ✓  single emoji prose: '🔑 Add a passkey today' → glued[EMOJI, TEXT(...)]")


# ---------------------------------------------------------------------------
# Group H — same-line content stays grouped when the leaf is a child
#
# The boundary peel no longer flat-splices a TEXT/heading leaf into its parent;
# it nests the whole peeled run + remainder in one container so same-line
# content stays grouped. (A single-line document keeps content on the root and
# its split pieces mint their own glued group — see `_root_pieces` in Group F;
# the cases here use a multi-line/glued context to put the peeled leaf under a
# parent.)
# ---------------------------------------------------------------------------


def _has_group_with_child_types(node: MarkdownGroupNode, types: list[str]) -> bool:
    for g in _find_nodes(node, NodeType.GROUP):
        if [c.type for c in g.children] == types:
            return True
    return False


def test_same_line_emojis_text_grouped_in_glued():
    # Three glued lines; the middle line's leading emoji run + remainder must
    # become ONE group[emoji, emoji, text], not flat siblings of the others.
    ast = _processed_with_criteria(
        "Glued text 1\n❤️ ❤️ - Text and multiple emojis prefix\nGlued text 2"
    )
    assert _has_group_with_child_types(ast, [NodeType.SEGMENT, NodeType.SEGMENT]), (
        f"Expected group[segment,segment]; tree={ast.to_dict()}"
    )
    print("  ✓  same line: glued '❤️ ❤️ text' → group[emoji,emoji,text]")


def test_same_line_text_link_grouped_in_glued():
    # text + trailing link on one line, inside a glued segment, stays grouped.
    ast = _processed_with_criteria("Intro line\nDenim Jacket - [buy](/x)\nOutro line")
    assert _has_group_with_child_types(ast, [NodeType.SEGMENT, NodeType.LINK]), (
        f"Expected group[segment,link]; tree={ast.to_dict()}"
    )
    print("  ✓  same line: glued 'text [link]' → group[text,link]")


def test_leading_emoji_nests_inside_heading():
    # A heading with a leading emoji keeps its heading label as the container
    # and holds the emoji + heading text inside it (not as a flat sibling).
    ast = _processed_with_criteria("# 🔎 - Heading\n\nbody text")
    containers = [h for h in _find_nodes(ast, "heading1") if h.children]
    assert containers, f"Expected a heading1 container; tree={ast.to_dict()}"
    child_types = [c.type for c in containers[0].children]
    assert child_types == [NodeType.EMOJI, NodeType.SEGMENT], (
        f"Expected [emoji, segment]; got {child_types}"
    )
    print("  ✓  same line: '# 🔎 Heading' → heading1[emoji, heading1]")


# ---------------------------------------------------------------------------
# Group I — chip vs marker: a boundary `code` span earns a CHIP only when it
# owns the line, the line is one sequenced run, or it is EXPLICITLY separated.
# A span the prose runs straight into stays inline as a MARKER, wherever on the
# line it sits — being first or last is not on its own a reason to become a pill.
# ---------------------------------------------------------------------------


def _chips(node: MarkdownGroupNode) -> list[str]:
    """Every INLINE_CODE leaf's content, in document order."""
    return [c.content for c in _find_nodes(node, NodeType.INLINE_CODE)]


def _is_marker_line(node: MarkdownGroupNode) -> bool:
    """True when the whole line survived as ONE leaf that still holds its
    backticks — i.e. nothing was peeled and the renderer will paint markers.

    The leaf is the root's single child, not the root: the root is a container
    and never a leaf (see :func:`_only_leaf`)."""
    if len(node.children) != 1:
        return False
    leaf = node.children[0]
    return not leaf.children and "`" in leaf.content


def test_chip_vs_marker_table():
    cases = [
        # (source, wanted chips, wanted marker-only line)
        ("`This is a text sample`", ["This is a text sample"], False),
        ("This is a `text` sample", [], True),
        ("`This` is a text sample", [], True),
        ("This is a text `sample`", [], True),
        (
            "`This` `is` `a` `text` `sample`",
            ["This", "is", "a", "text", "sample"],
            False,
        ),
        ("This is a text - `sample`", ["sample"], False),
        ("This is - `a` `text` `sample`", ["a", "text", "sample"], False),
    ]
    for src, want_chips, want_marker in cases:
        ast = _processed_with_criteria(src)
        assert _chips(ast) == want_chips, f"{src!r}: chips={_chips(ast)}"
        if want_marker:
            assert _is_marker_line(ast), (
                f"{src!r}: expected one marker leaf; {ast.to_dict()}"
            )
    print("  ✓  chip only when whole-line / sequenced / separated; else marker")


def test_prose_adjacent_run_is_markers_not_chips():
    # Prose adjacency beats a run: no separator, so all four stay inline.
    ast = _processed_with_criteria("This is a text `followed` `by` `multiple` `labels`")
    assert _chips(ast) == [], ast.to_dict()
    assert _is_marker_line(ast), ast.to_dict()
    print("  ✓  a run butting straight against prose is markers, not chips")


def test_separator_left_in_the_middle_text_still_earns_chips():
    # A separator the Phase-2 split leaves in place reaches _split_elements as
    # the head of the middle text, and it counts. Spelled with the ASCII `-`:
    # the em dash is not a separator, because it cannot be escaped and so could
    # not be declined (ADR-205).
    ast = _processed_with_criteria("`Draft` - needs review")
    assert _chips(ast) == ["Draft"], ast.to_dict()
    assert _chips(_processed_with_criteria("`Draft` — needs review")) == [], (
        "an em dash must not separate a chip out of prose"
    )
    print("  ✓  a separator the split left in place still earns a chip")


def test_an_escaped_separator_keeps_its_element_inline():
    """``\\-`` / ``\\|`` before a trailing element, or after a leading one,
    declines the division the plain separator would make: the element stays an
    inline marker in its sentence (skills/structure.md, *Escape a separator to
    keep the line whole*). The plain spelling still peels it.
    """
    for line in (
        r"Draft words here \- `Label`",
        r"`Label` \- draft words here",
        r"Read more \| [docs](/d)",
    ):
        typed = _typed_pieces(line)
        assert len(typed) == 1 and typed[0][0] == NodeType.TEXT, (line, typed)
        assert "\\" not in typed[0][1], (line, typed)
    assert _chips(_processed_with_criteria("Draft words here - `Label`")) == ["Label"]
    print("  ✓  an escaped separator keeps its element inline")


def test_comma_is_not_a_separator():
    ast = _processed_with_criteria("This is a text, `sample`")
    assert _chips(ast) == [], ast.to_dict()
    seq = _processed_with_criteria("`Label A`, `Label B`, `Label C`")
    assert _chips(seq) == [], seq.to_dict()
    print("  ✓  commas never separate chips from their line")


def test_a_span_after_a_colon_stays_in_its_line():
    # ADR-205: a colon makes no pair, so the span is not a whole value that
    # peels; it stays inline in the text, as its escaped twin's does.
    for line in ("Status: `Active`", "Tags: `a` `b` `c`"):
        ast = _processed_with_criteria(line)
        assert _chips(ast) == [], ast.to_dict()
        assert [(c.type, c.content) for c in ast.children] == [(NodeType.TEXT, line)]
        assert_reads_as_escaped_twin(line)
    print("  ✓  a span after a colon stays inline in its line")


def test_peeled_emoji_leaves_a_whole_line_chip():
    # Peeling the emoji turns the leaf INTO a whole-line span, which
    # is a chip — the earlier peel could only see a span adjacent to the emoji.
    ast = _processed_with_criteria("⭐ `Popular` | 🚀 `Growth`")
    assert _chips(ast) == ["Popular", "Growth"], ast.to_dict()
    print("  ✓  a span left alone by the emoji/link peel becomes a chip")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Detection must see through an author's tier wrapper
# ---------------------------------------------------------------------------


def _detected(text: str):
    return [
        (d["start"], d["end"], d["matched"])
        for d in _detect_through_markers(text, DataPointDetector())
    ]


def _pieces(text: str) -> list[str]:
    out: list[str] = []

    def walk(n):
        if not n.children and n.content:
            out.append(n.content)
        for c in n.children:
            walk(c)

    walk(_processed_with_criteria(text))
    return out


def test_a_tier_wrapper_does_not_hide_a_datapoint():
    """`_` is a regex WORD character, so a \\b-anchored pattern cannot match at
    `__8`. Bold never had the problem because `*` is not one."""
    for wrap in ("_", "__", "___"):
        got = _detected(f"{wrap}8:00 AM - 9:00 AM{wrap}")
        assert len(got) == 1 and got[0][2] == "8:00 AM - 9:00 AM", (wrap, got)
    assert _detected("**8:00 AM - 9:00 AM**")[0][2] == "8:00 AM - 9:00 AM"


def test_the_mapped_offsets_slice_the_real_span():
    """The range is reported against the ORIGINAL text, wrapper included, so
    everything downstream that slices content gets the right characters."""
    src = "__8:00 AM - 9:00 AM__"
    start, end, matched = _detected(src)[0]
    assert src[start:end] == matched == "8:00 AM - 9:00 AM"


def test_an_identifier_underscore_is_not_a_wrapper():
    """Only a run with whitespace (or the edge) on its outer side is a wrap;
    eating interior ones would rewrite real content such as URLs."""
    url = "https://x.org/Van_Gogh_-_Starry_Night.jpg"
    got = _detected(url)
    assert got and got[0][2] == url, got
    assert _detected("message_schemas") == []
    assert _detected("snake_case 8:00 AM - 9:00 AM")[0][2] == "8:00 AM - 9:00 AM"


def test_a_wrapped_value_survives_every_split():
    """Every separator reads the same protected ranges, so all must hold."""
    for line in (
        "_Key_ : __8:00 AM - 9:00 AM__",
        "Key : __8:00 AM - 9:00 AM__",
        "Key - __8:00 AM - 9:00 AM__",
        "Key | __8:00 AM - 9:00 AM__",
    ):
        assert _pieces(line) == ["Key", "8:00 AM - 9:00 AM"], (line, _pieces(line))
    # A tight colon divides nothing (ADR-205); the wrapped range's dash still
    # must not cut the line.
    line = "Key: __8:00 AM - 9:00 AM__"
    assert _pieces(line) == [line], _pieces(line)


# ---------------------------------------------------------------------------
# An escaped separator stops this split too
#
# `_make_is_safe` is where every separator SCAN reads the escape, but this split
# reaches no scan at all — it cuts at DATAPOINT boundaries. So it needs its own
# gate, or the escape is stranded as a leaf between the pieces it was meant to
# hold together.
# ---------------------------------------------------------------------------


def test_an_escaped_separator_keeps_its_line_whole():
    """Legacy comma escapes remain accepted and resolve harmlessly."""
    assert _pieces(r"February 04\, 9:17 PM") == ["February 04, 9:17 PM"]
    assert _pieces(r"Check-in\: 3 PM \| Check-out\: 11 AM") == [
        "Check-in: 3 PM | Check-out: 11 AM"
    ]


def test_the_escaped_line_reads_like_the_plain_one():
    """The backslashes are resolved before anything draws, so the two spellings must be indistinguishable in the output."""
    assert _pieces(r"February 04\, 9:17 PM") == _pieces("February 04, 9:17 PM")


def test_an_unescaped_line_still_splits():
    """The gate must fire on the ESCAPE, not on the datapoints beside it."""
    assert _pieces("8:00 AM - 9:00 AM") == ["8:00 AM - 9:00 AM"]
    assert _pieces("Total: $128.00 - Paid") == ["Total: $128.00", "Paid"]


def _typed_pieces(text: str) -> list[tuple[str, str]]:
    """``(type, content)`` per leaf — the escape tests need the TYPE too.

    ``_pieces`` compares content only, and both spellings hold the same text.
    """
    out: list[tuple[str, str]] = []

    def walk(n):
        if not n.children and n.content:
            out.append((n.type, n.content))
        for c in n.children:
            walk(c)

    walk(_processed_with_criteria(text))
    return out


def test_an_escape_refuses_the_cut_but_not_the_relabel():
    """The escape refuses the separator cut, not TIME detection.

    TIME is annotation-only, so the escape-free line remains TEXT while
    carrying the same whole-value evidence.
    """
    assert _typed_pieces(r"8:00 AM \- 9:00 AM") == [
        (NodeType.TEXT, "8:00 AM - 9:00 AM")
    ]


def test_an_escape_does_not_change_how_a_line_is_styled():
    """A backslash stops a split; it must not decide the node's TYPE.

    Every stage reads through it: the detector strips it before matching,
    `_make_is_safe` honours it in each separator scan, and the comma-signal rules
    must not let a trailing "\\" break their month+day tell.
    """
    assert _typed_pieces(r"February 04\, 9:17 PM") == _typed_pieces(
        "February 04, 9:17 PM"
    )
    # ...and the same inside a line that does split, where the timestamp is one
    # piece among several.
    assert _typed_pieces(r"Netflix : February 04\, 9:17 PM") == _typed_pieces(
        "Netflix : February 04, 9:17 PM"
    )


def test_a_weekdays_comma_stays_with_its_date():
    assert _pieces(r"_Dates_ : Fri, Aug 14 \- Sun, Aug 16") == [
        "Dates",
        "Fri, Aug 14 - Sun, Aug 16",
    ]
    # ...while the range's own ` - ` still separates when it is not escaped.
    assert _pieces("Fri, Aug 14 - Sun, Aug 16") == ["Fri, Aug 14", "Sun, Aug 16"]


def test_the_escape_still_stops_a_dash_and_is_harmless_on_a_comma():
    assert _pieces(r"Fri, Aug 14 \- Sun, Aug 16") == ["Fri, Aug 14 - Sun, Aug 16"]
    assert _pieces(r"One\, Two\, Three\, Four\, Five") == [
        "One, Two, Three, Four, Five"
    ]
    # The dash still separates; the unescaped comma spelling is identical.
    assert _pieces("Fri, Aug 14 - Sun, Aug 16") == ["Fri, Aug 14", "Sun, Aug 16"]
    assert _pieces("One, Two, Three, Four, Five") == ["One, Two, Three, Four, Five"]


def test_a_timestamps_comma_stays_with_its_timestamp():
    for line in (
        "Netflix : February 04, 9:17 PM",
        "Netflix | February 04, 9:17 PM",
        "Netflix - February 04, 9:17 PM",
    ):
        assert _pieces(line) == ["Netflix", "February 04, 9:17 PM"], (
            line,
            _pieces(line),
        )
    assert _pieces("February 04, 9:17 PM") == ["February 04, 9:17 PM"]


def test_an_ordinary_comma_list_stays_whole():
    assert _pieces("One, Two, Three, Four, Five") == ["One, Two, Three, Four, Five"]
    assert _pieces("Alpha : Beta, Gamma") == ["Alpha", "Beta, Gamma"]


def test_a_date_beside_a_count_is_not_a_timestamp():
    """The bare-hour branch needs AM/PM, or `March 5, 10` would read as a time.

    Asserted on the detector, where the rule actually lives; the grouper keeps
    commas intact regardless, so a tree-shape proxy cannot distinguish the two
    detector outcomes.
    """
    det = DataPointDetector()
    spanning = [
        dp for dp in det.detect_all("March 5, 10 people") if "," in dp["matched"]
    ]
    assert not spanning, f"'March 5, 10' must not match as one timestamp: {spanning}"
    # ...and with a real meridiem it IS one, matched across the comma.
    assert [
        dp["matched"] for dp in det.detect_all("March 5, 3 PM") if "," in dp["matched"]
    ] == ["March 5, 3 PM"], det.detect_all("March 5, 3 PM")
    # End to end: the colon takes the line, so the value is one whole piece.
    assert _pieces("Order : March 5, 3 PM") == ["Order", "March 5, 3 PM"]


def test_the_escaped_lines_already_whole_are_untouched():
    """Lines already kept whole must stay unchanged by the gate."""
    for line, want in (
        (r"8:00 AM \- 9:00 AM", ["8:00 AM - 9:00 AM"]),
        (r"Fri, Aug 14 \- Sun, Aug 16", ["Fri, Aug 14 - Sun, Aug 16"]),
        (r"One\, Two\, Three\, Four\, Five", ["One, Two, Three, Four, Five"]),
        (r"\- This is not a list", ["- This is not a list"]),
    ):
        assert _pieces(line) == want, (line, _pieces(line))


def test_the_peel_never_eats_its_container_s_label():
    """A container whose content peels to ONE element keeps its own label.

    `_apply_split_result` relabels a node in place when the split leaves a
    single piece — right for a TEXT leaf (a line that is nothing but a chip
    should BE that chip) and wrong for a node whose type is its role: a list
    item, quote or table cell must survive around its lone element.
    """
    for md, wrapper in (
        ("- ⭐", NodeType.LIST_ITEM),
        ("- [Link](/x)", NodeType.LIST_ITEM),
        ("- `Draft`", NodeType.LIST_ITEM),
        ("1. ⭐", NodeType.ORDERED_ITEM),
        ("> [Link](/x)", NodeType.BLOCKQUOTE),
    ):
        ast = _processed(md + "\n")
        kept = [n for n in _walk_nodes(ast) if n.type == wrapper]
        assert kept, (
            f"{md!r}: {wrapper} was eaten -> {[n.type for n in _walk_nodes(ast)]}"
        )
        assert kept[0].children, f"{md!r}: the piece must be its CHILD"
    print("  ✓  a one-piece peel never eats its container's label")


def test_a_plain_text_leaf_is_still_relabelled_in_place():
    """The other half: TEXT carries no role, so it still becomes the element."""
    for md, kind in (("⭐", NodeType.EMOJI), ("[Link](/x)", NodeType.LINK)):
        ast = _processed(md + "\n")
        types = [n.type for n in _walk_nodes(ast)]
        assert kind in types, f"{md!r}: {types}"
        assert NodeType.LIST_ITEM not in types
    print("  ✓  a bare element line is still relabelled in place")


TESTS = [
    test_an_emoji_sequence_peels_as_one_badge,
    test_the_peel_never_eats_its_container_s_label,
    test_a_plain_text_leaf_is_still_relabelled_in_place,
    test_an_escaped_separator_keeps_its_line_whole,
    test_the_escaped_line_reads_like_the_plain_one,
    test_an_unescaped_line_still_splits,
    test_an_escape_refuses_the_cut_but_not_the_relabel,
    test_an_escape_does_not_change_how_a_line_is_styled,
    test_a_weekdays_comma_stays_with_its_date,
    test_the_escape_still_stops_a_dash_and_is_harmless_on_a_comma,
    test_the_escaped_lines_already_whole_are_untouched,
    test_a_timestamps_comma_stays_with_its_timestamp,
    test_an_ordinary_comma_list_stays_whole,
    test_a_date_beside_a_count_is_not_a_timestamp,
    test_chip_vs_marker_table,
    test_prose_adjacent_run_is_markers_not_chips,
    test_separator_left_in_the_middle_text_still_earns_chips,
    test_an_escaped_separator_keeps_its_element_inline,
    test_comma_is_not_a_separator,
    test_a_span_after_a_colon_stays_in_its_line,
    test_peeled_emoji_leaves_a_whole_line_chip,
    test_an_annotated_value_grids_with_every_other_annotated_value,
    test_annotate_only_ratio_group_keeps_the_unsplit_fingerprint,
    test_a_spring_cut_value_line_fingerprints_the_same_after_serialization,
    test_boundary_dps_leading_emoji,
    test_boundary_dps_single_trailing_emoji,
    test_boundary_dps_mid_text_emoji_not_peeled,
    test_integration_dp_in_middle,
    test_integration_datapoint_annotations_preserved,
    test_integration_dimension_annotation_is_preserved,
    test_integration_duration_annotation_is_preserved,
    test_integration_version_annotation_is_preserved,
    test_integration_date_range_annotation_is_preserved,
    test_integration_file_size_annotation_is_preserved,
    test_integration_phone_annotation_is_preserved,
    test_integration_url_annotation_is_preserved,
    test_integration_date_annotation_is_preserved,
    test_integration_emoji_and_dp_coexist,
    test_emoji_before_a_colon_line,
    test_emoji_before_separator_and_colon_line,
    test_integration_plain_prose_not_split,
    test_score_decimal_denominator,
    test_bold_colon_line_currency_with_space,
    test_prose_adjacent_leading_emoji_is_a_text_emoji,
    test_integration_time_hours_detected,
    test_change_bare_positive_integer,
    test_change_bare_negative_integer,
    test_change_bare_decimal,
    test_change_bare_does_not_override_quantity,
    test_change_bare_does_not_override_percentage,
    test_annotate_only_change_and_emoji_stay_one_leaf,
    test_number_not_detected_in_suffix_identifier,
    test_number_not_detected_in_prefix_identifier,
    test_number_not_detected_in_sandwiched_identifier,
    test_standalone_number_still_detected,
    test_change_not_detected_inside_identifier,
    test_change_bare_still_detected_standalone,
    test_date_hyphenated_dmy,
    test_detect_style_wrap_bold_italic,
    test_detect_style_wrap_bold,
    test_detect_style_wrap_italic,
    test_detect_style_wrap_no_markers,
    test_detect_style_wrap_mismatched,
    test_split_boundary_emoji_bold_italic,
    test_split_boundary_emoji_bold,
    test_split_boundary_emoji_italic,
    test_integration_emoji_bold_italic_heading,
    test_integration_emoji_bold_heading,
    test_integration_emoji_italic_heading,
    test_score_single_star_detected_forward,
    test_score_single_star_detected_no_space,
    test_score_single_star_detected_reverse,
    test_score_single_star_glyph_variants,
    test_integration_score_keeps_star_with_number,
    # Group F — Boundary-LINK integration via process()
    test_link_whole_content,
    test_link_leading_extracted,
    test_link_mid_text_inline,
    test_link_both_ends,
    test_link_italic_wrap,
    test_link_bold_wrap,
    test_link_bold_italic_wrap,
    test_link_after_a_bold_label,
    test_links_pipe_separated_flat,
    test_links_dash_separated_flat,
    test_links_between_dots_stay_one_text,
    test_links_identical_partition,
    # Group G — Flat EMOJI when content is `EMOJI <sep> EMOJI`
    test_emojis_dash_separated_flat,
    test_emojis_between_dots_stay_one_text,
    test_emojis_pipe_separated_flat,
    test_emojis_em_dash_separated_flat,
    test_mixed_emoji_text_does_not_flatten,
    test_single_emoji_prose_not_flat,
    # Group H — same-line content stays grouped under a child leaf
    test_same_line_emojis_text_grouped_in_glued,
    test_same_line_text_link_grouped_in_glued,
    test_leading_emoji_nests_inside_heading,
    test_a_tier_wrapper_does_not_hide_a_datapoint,
    test_the_mapped_offsets_slice_the_real_span,
    test_an_identifier_underscore_is_not_a_wrapper,
    test_a_wrapped_value_survives_every_split,
]

if __name__ == "__main__":
    print("Unified Data-Point Split Tests")
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
