"""
Unit and integration tests for paren/quote range protection in MarkdownGrouper.

All cases are drawn from data/markdown/tests/tests-separators.md.

Content inside balanced () or "..." is protected from:
  - separator splits  (_split_separators)
  - key-value splits  (_split_kv_styled / _plain_colon_kv)
  - data-point extraction  (_apply_all_datapoints_to_node)
  - the element peel    (_element_hits / _peel_elements)

Group H covers the half where a quote pair is also CONSUMED. A pair wrapping
exactly one bare element, at the boundary of its leaf, is the author declining
the element reading: "\U0001f4de" is a glyph in the surrounding text instead of a
badge, "[Docs](/d)" an inline span instead of a button, "`code`" a marker instead
of a chip. The quotes are stripped at Phase 6.17, so nothing extra is drawn, and
the style still comes from the context -- the */_ ladders keep their ordinary
meanings around the pair.

Two things a reader should not have to rediscover:
  - a quote pair around PROSE, and one mid-sentence, are the author's own
    punctuation and stay drawn;
  - a bare `code` span is its own backtick range in _bracket_quote_ranges, so a
    test written as "inside a protected range" rather than "wrapped by a quote
    pair" would suppress every chip in the document. test_bare_chip_still_a_chip
    is what catches that.

Run with: uv run tests/markdown_paren_quote_protection_tests.py
"""

import random

from md2ui.pipeline.grouper_ranges import _bracket_quote_ranges, _merge_pq
from md2ui.pipeline.grouper_content_edits import edit_content
from md2ui.pipeline.grouper_inline_marks import quoted_element_edits
from md2ui.pipeline.data_point_detector import DataPointDetector, DataPointType
from md2ui.pipeline.markdown_grouper import MarkdownGrouper, MarkdownGroupNode, NodeType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def strip_quoted_elements(content: str) -> str:
    """What Phase 6.17 leaves of *content* once a declined element's quotes go."""
    node = MarkdownGroupNode(content=content)
    edit_content(node, quoted_element_edits(content))
    return node.content


def _processed(text: str) -> MarkdownGroupNode:
    detector = DataPointDetector()
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=detector)
    assert g.ast is not None
    return g.ast


def _find_nodes(node: MarkdownGroupNode, label: str) -> list[MarkdownGroupNode]:
    results: list[MarkdownGroupNode] = []
    if node.type == label:
        results.append(node)
    for child in node.children:
        results.extend(_find_nodes(child, label))
    return results


def _leaf_texts(node: MarkdownGroupNode) -> list[str]:
    """Collect content of all leaf nodes in the subtree."""
    if not node.children:
        return [node.content] if node.content else []
    out: list[str] = []
    for child in node.children:
        out.extend(_leaf_texts(child))
    return out


def _all_contents(node: MarkdownGroupNode) -> set[str]:
    return {t for t in _leaf_texts(node) if t}


def _leaf_nodes(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    """Every childless node, whatever its type. A one-line document collapses to
    the ROOT, so a test that wants "the leaf" cannot ask for a TEXT node."""
    if not node.children:
        return [node]
    out: list[MarkdownGroupNode] = []
    for child in node.children:
        out.extend(_leaf_nodes(child))
    return out


def _segment_count(ast: MarkdownGroupNode) -> int:
    return len(_find_nodes(ast, NodeType.SEGMENT))


# ---------------------------------------------------------------------------
# Group A — _bracket_quote_ranges static method (unit tests)
# ---------------------------------------------------------------------------


def test_pq_ranges_empty():
    result = _bracket_quote_ranges("plain text", [])
    assert result == [], f"Expected no ranges for plain text, got {result!r}"
    print("  ✓  pq_ranges: plain text → []")


def test_pq_ranges_parens():
    result = _bracket_quote_ranges("(hello)", [])
    assert result == [(0, 7)], f"Expected [(0,7)], got {result!r}"
    print("  ✓  pq_ranges: '(hello)' → [(0, 7)]")


def test_pq_ranges_nested_parens():
    result = _bracket_quote_ranges("(a (b) c)", [])
    assert result == [(0, 9)], f"Expected outer span [(0,9)], got {result!r}"
    print("  ✓  pq_ranges: '(a (b) c)' → outer span [(0, 9)]")


def test_pq_ranges_quotes():
    result = _bracket_quote_ranges('"hello"', [])
    assert result == [(0, 7)], f"Expected [(0,7)], got {result!r}"
    print("  ✓  pq_ranges: '\"hello\"' → [(0, 7)]")


def test_pq_ranges_unbalanced_paren():
    result = _bracket_quote_ranges("(unclosed text", [])
    assert result == [], f"Expected [] for unbalanced paren, got {result!r}"
    print("  ✓  pq_ranges: '(unclosed text' → [] (no range for unbalanced paren)")


def test_pq_ranges_unmatched_quote():
    result = _bracket_quote_ranges('"unclosed', [])
    assert result == [], f"Expected [] for unmatched quote, got {result!r}"
    print("  ✓  pq_ranges: '\"unclosed' → [] (no range for unmatched quote)")


def test_pq_ranges_skips_dp_covered_delimiters():
    # If '(' is inside a dp range, it should be skipped.
    # Simulates a markdown link [text](url) where (url) is a dp range.
    dp_ranges = [(6, 14)]  # covers "(url)"
    result = _bracket_quote_ranges("link (url)", dp_ranges)
    assert result == [], f"Expected [] when paren is inside dp range, got {result!r}"
    print("  ✓  pq_ranges: paren inside dp range → skipped (no false range)")


def test_pq_ranges_multiple():
    result = _bracket_quote_ranges("(A) and (B)", [])
    assert result == [(0, 3), (8, 11)], f"Expected two spans, got {result!r}"
    print("  ✓  pq_ranges: '(A) and (B)' → [(0,3), (8,11)]")


def test_pq_ranges_backtick():
    content = "`**A bold code** - B code`"
    result = _bracket_quote_ranges(content, [])
    assert result == [(0, 26)], f"Expected [(0, 26)], got {result!r}"
    print("  ✓  pq_ranges: backtick span → [(0, 26)]")


def test_pq_ranges_single_quote():
    result = _bracket_quote_ranges("'hello - world'", [])
    assert result == [(0, 15)], f"Expected [(0, 15)], got {result!r}"
    print("  ✓  pq_ranges: single-quote span → [(0, 15)]")


def test_pq_ranges_apostrophe_not_protected():
    # Apostrophes inside words must NOT open a single-quote span
    result = _bracket_quote_ranges("don't - won't", [])
    assert result == [], f"Expected [] (apostrophes skipped), got {result!r}"
    print("  ✓  pq_ranges: apostrophes in contractions → [] (no false protection)")


def _reference_ranges(content, dp_protected):
    """The spans read one kind at a time, every character visited: the plain
    statement of the rule the grouper's one-pass version must equal."""
    free = [
        i for i in range(len(content)) if not any(s <= i < e for s, e in dp_protected)
    ]
    ranges = []
    depth = start = 0
    for i in free:
        if content[i] == "(":
            start = i if depth == 0 else start
            depth += 1
        elif content[i] == ")" and depth:
            depth -= 1
            if depth == 0:
                ranges.append((start, i + 1))
    for quote in ('"', "`", "'"):
        open_at = None
        for i in free:
            if content[i] != quote:
                continue
            if open_at is not None:
                ranges.append((open_at, i + 1))
                open_at = None
            elif quote != "'" or i == 0 or not content[i - 1].isalnum():
                open_at = i
    return sorted(ranges)


def test_pq_ranges_match_the_one_kind_at_a_time_reading():
    """Kinds interleave (`"a 'b" c'`), nest, sit inside data points and touch
    letters; 20k seeded random lines over the five characters must agree."""
    rnd = random.Random(20261024)
    cases = [("\"a 'b\" c' (`d)` e'", []), ("x'y 'z' (\"q\")", [(4, 7)])]
    for _ in range(20000):
        line = "".join(
            rnd.choice("ab1 ()\"`'\u00e9") for _ in range(rnd.randint(0, 24))
        )
        spans = []
        for _ in range(rnd.randint(0, 2) if line else 0):
            a = rnd.randrange(len(line))
            spans.append((a, min(len(line), a + rnd.randint(1, 5))))
        cases.append((line, spans))
    for line, spans in cases:
        assert _bracket_quote_ranges(line, spans) == _reference_ranges(line, spans), (
            line,
            spans,
        )


# ---------------------------------------------------------------------------
# Group B — _merge_pq static method (unit tests)
# ---------------------------------------------------------------------------


def test_merge_pq_empty():
    assert _merge_pq([]) == []
    print("  ✓  merge_pq: [] → []")


def test_merge_pq_no_overlap():
    result = _merge_pq([(0, 3), (5, 8)])
    assert result == [(0, 3), (5, 8)], f"Got {result!r}"
    print("  ✓  merge_pq: non-overlapping → unchanged")


def test_merge_pq_overlapping():
    result = _merge_pq([(0, 9), (1, 7)])
    assert result == [(0, 9)], f"Expected merged to [(0,9)], got {result!r}"
    print("  ✓  merge_pq: nested spans → merged to outer span")


# ---------------------------------------------------------------------------
# Group C — separator split protection (integration)
# ---------------------------------------------------------------------------


def test_quoted_comma_list_stays_whole():
    ast = _processed('"Mahmoud Ajjour, Aged Nine"')
    segs = _find_nodes(ast, NodeType.SEGMENT)
    assert not segs, [n.content for n in segs]
    print('  ✓  "Mahmoud Ajjour, Aged Nine" stays whole')


def test_paren_and_outer_commas_stay_whole():
    ast = _processed("Score (A, B), Other")
    segs = _find_nodes(ast, NodeType.SEGMENT)
    assert not segs, [n.content for n in segs]
    print("  ✓  'Score (A, B), Other' stays whole")


def test_paren_day_range_not_split():
    # (Mon-Fri) — hyphen inside parens must not trigger a separator split
    ast = _processed("(Mon-Fri)")
    segs = _find_nodes(ast, NodeType.SEGMENT)
    assert not segs, (
        f"Expected no SEGMENT nodes for '(Mon-Fri)', got {[n.content for n in segs]!r}"
    )
    print("  ✓  separator: '(Mon-Fri)' → not split (paren protects hyphen)")


def test_paren_emoji_content_not_split():
    # (↗️ +3 points) — emoji and number inside parens, must not be split or extracted
    ast = _processed("(↗️ +3 points)")
    segs = _find_nodes(ast, NodeType.SEGMENT)
    dps = _find_nodes(ast, NodeType.DATAPOINT)
    emojis = _find_nodes(ast, NodeType.EMOJI)
    assert not segs, f"Expected no SEGMENT nodes, got {[n.content for n in segs]!r}"
    assert not dps, (
        f"Expected no DATAPOINT nodes (protected by parens), got {[n.content for n in dps]!r}"
    )
    assert not emojis, (
        f"Expected no EMOJI nodes (protected by parens), got {[n.content for n in emojis]!r}"
    )
    print("  ✓  separator+dp: '(↗️ +3 points)' → no split, no dp/emoji extraction")


def test_no_paren_emoji_content_keeps_annotations_inline():
    # Without parens both values remain detectable, but CHANGE is annotation-only
    # and the adjacent emoji is consequently inline too: detection is not an
    # instruction to split an unseparated line.
    ast = _processed("↗️ +3 points")
    dps = _find_nodes(ast, NodeType.DATAPOINT)
    emojis = _find_nodes(ast, NodeType.EMOJI)
    assert not dps and not emojis
    carrier = next(n for n in _find_nodes(ast, NodeType.TEXT) if n.data_points)
    assert carrier.content == "↗️ +3 points"
    assert [point["type"] for point in carrier.data_points] == [
        DataPointType.EMOJI,
        DataPointType.CHANGE,
    ]
    print("  ✓  separator+dp: '↗️ +3 points' keeps both annotations inline")


# ---------------------------------------------------------------------------
# Group D — key-value split protection (integration)
#
# Under ADR-205 only a pair a display reads survives, so these use percentage
# bars (`Key: 40%`): a protected colon must not become one.
# ---------------------------------------------------------------------------


def test_quoted_kv_not_split():
    # "Progress: 60%" — colon inside quotes must not trigger KV split
    ast = _processed('"Progress: 60%"')
    kv_nodes = _find_nodes(ast, NodeType.KEY_VALUE)
    assert not kv_nodes, (
        f"Expected no KEY_VALUE nodes — colon inside quotes is protected, "
        f"got {[n.content for n in kv_nodes]!r}"
    )
    print('  ✓  kv: "Progress: 60%" → no KV split (quotes protect colon)')


def test_quoted_value_after_a_colon_not_split():
    # Key: "A, B, C" — the line is one text (ADR-205); commas stay punctuation.
    ast = _processed('Key: "A, B, C"')
    assert [(c.type, c.content) for c in ast.children] == [
        (NodeType.TEXT, 'Key: "A, B, C"')
    ], ast.to_dict()
    print('  ✓  Key: "A, B, C" → one text; commas stay punctuation')


def test_paren_kv_segments_inner_kv_not_split():
    # (A: 40%) | (B: 60%) — split at | is OK; inner colons are protected by parens
    ast = _processed("(A: 40%) | (B: 60%)")
    segs = _find_nodes(ast, NodeType.SEGMENT)
    kv_in_segs = _find_nodes(ast, NodeType.KEY_VALUE)
    assert len(segs) == 2, (
        f"Expected 2 SEGMENTs split at '|', got {len(segs)}: {[n.content for n in segs]!r}"
    )
    assert not kv_in_segs, (
        f"Expected no KV splits inside paren segments, got {[n.content for n in kv_in_segs]!r}"
    )
    print(
        "  ✓  kv: '(A: 40%) | (B: 60%)' → 2 segments; inner KV not split (parens protect)"
    )


# ---------------------------------------------------------------------------
# Group E — data-point extraction protection (integration)
# ---------------------------------------------------------------------------


def test_quoted_time_not_extracted():
    # "11 AM" — time data point inside quotes must not be extracted as DATAPOINT
    ast = _processed('"11 AM"')
    dps = _find_nodes(ast, NodeType.DATAPOINT)
    assert not dps, (
        f"Expected no DATAPOINT nodes — time inside quotes is protected, "
        f"got {[n.content for n in dps]!r}"
    )
    print('  ✓  dp: "11 AM" → time not extracted (quotes protect)')


def test_paren_size_not_split():
    # (9.5 in × 13 in) — × is not a current separator; data points inside parens
    # should also not be extracted, leaving the whole string intact.
    ast = _processed("(9.5 in × 13 in)")
    segs = _find_nodes(ast, NodeType.SEGMENT)
    dps = _find_nodes(ast, NodeType.DATAPOINT)
    assert not segs, (
        f"Expected no SEGMENTs for '(9.5 in × 13 in)', got {[n.content for n in segs]!r}"
    )
    assert not dps, (
        f"Expected no DATAPOINT nodes inside parens, got {[n.content for n in dps]!r}"
    )
    print(
        "  ✓  dp: '(9.5 in × 13 in)' → not split; inner data points protected by parens"
    )


# ---------------------------------------------------------------------------
# Group F — backtick and single-quote protection (integration)
# ---------------------------------------------------------------------------


def test_backtick_content_not_split():
    # `**A bold code** - B code` — hyphen inside backticks must not split
    ast = _processed("`**A bold code** - B code`")
    segs = _find_nodes(ast, NodeType.SEGMENT)
    assert not segs, (
        f"Expected no SEGMENT nodes — hyphen inside backticks is protected, "
        f"got {[n.content for n in segs]!r}"
    )
    print("  ✓  separator: `**A bold code** - B code` → not split (backtick protects)")


def test_single_quote_content_not_split():
    # '**A bold code** - B code' — hyphen inside single quotes must not split
    ast = _processed("'**A bold code** - B code'")
    segs = _find_nodes(ast, NodeType.SEGMENT)
    assert not segs, (
        f"Expected no SEGMENT nodes — hyphen inside single quotes is protected, "
        f"got {[n.content for n in segs]!r}"
    )
    print(
        "  ✓  separator: '**A bold code** - B code' → not split (single quote protects)"
    )


# ---------------------------------------------------------------------------
# Group F2 — protected dps remain annotated on the leaf for post-processing
# ---------------------------------------------------------------------------


def _all_dps(node: MarkdownGroupNode) -> list[dict]:
    """Flatten every node.data_points list in the subtree."""
    out: list[dict] = list(node.data_points)
    for child in node.children:
        out.extend(_all_dps(child))
    return out


def test_quoted_time_dp_preserved_on_leaf():
    # "11 AM" — no DATAPOINT node is extracted, but the TIME annotation
    # must survive on the leaf node that holds the quoted span so
    # post-processing still sees it.
    ast = _processed('"11 AM"')
    dps = _all_dps(ast)
    times = [dp for dp in dps if dp["type"] == DataPointType.TIME]
    assert times, f"Expected TIME dp annotated on a leaf, got {dps!r}"
    print('  ✓  dp annot: "11 AM" → TIME preserved on leaf data_points')


def test_paren_size_dps_preserved_on_leaf():
    # (9.5 in × 13 in) — sizes inside parens are not extracted as DATAPOINT
    # nodes, but the size annotations stay on the leaf.
    ast = _processed("(9.5 in × 13 in)")
    dps = _all_dps(ast)
    assert dps, "Expected size dps annotated on a leaf, got none"
    print("  ✓  dp annot: '(9.5 in × 13 in)' → size dps preserved on leaf data_points")


def test_inline_code_dp_preserved_on_inline_code_node():
    # `+$4,045.00` — whole content is one backtick span, the node gets
    # relabeled INLINE_CODE; the CHANGE dp must follow onto that node
    # with positions adjusted to the stripped (markerless) content.
    ast = _processed("`+$4,045.00`")
    ic_nodes = _find_nodes(ast, NodeType.INLINE_CODE)
    assert ic_nodes, "Expected an INLINE_CODE node"
    target = next((n for n in ic_nodes if n.content == "+$4,045.00"), None)
    assert target is not None, (
        f"Expected INLINE_CODE leaf with '+$4,045.00', got {[n.content for n in ic_nodes]!r}"
    )
    assert target.data_points, (
        f"Expected dp on INLINE_CODE leaf, got {target.data_points!r}"
    )
    dp = target.data_points[0]
    assert dp["start"] == 0 and dp["end"] == len("+$4,045.00"), (
        f"Expected dp positions to index into the stripped content, "
        f"got start={dp['start']} end={dp['end']}"
    )
    print(
        "  ✓  dp annot: `+$4,045.00` → CHANGE dp preserved on INLINE_CODE leaf with adjusted offsets"
    )


# ---------------------------------------------------------------------------
# Group H — a quoted element is DECLINED: the quotes are consumed (Phase 6.17)
# ---------------------------------------------------------------------------


def test_strip_unit_boundary_only():
    """The stripper itself: a boundary pair goes, a mid-sentence pair stays."""
    assert strip_quoted_elements('"📞"') == "📞"
    assert strip_quoted_elements('"📞" is our number') == "📞 is our number"
    assert strip_quoted_elements('call "📞"') == "call 📞"
    kept = 'Press "📞" to dial'
    assert strip_quoted_elements(kept) == kept, "mid-sentence pair must survive"
    print("  ✓  strip: boundary pair consumed, mid-sentence pair kept")


def test_strip_unit_needs_a_lone_element():
    """Only ONE bare element earns the reading; anything else keeps its quotes."""
    for kept in ('"This is prose"', '"📞 Call us"', '"Ready?" she asked'):
        assert strip_quoted_elements(kept) == kept, f"{kept!r} should be untouched"
    # A pair at the LEADING boundary of a prose line IS a decline, which is the
    # whole point of the boundary rule rather than a whole-leaf rule.
    assert strip_quoted_elements('"📞" is our number') == "📞 is our number"
    print("  ✓  strip: only a lone element is declined")


def test_strip_unit_boundary_skips_markers():
    """A wrapper that STARTS a line without spanning it still leaves the pair at
    the boundary, though _element_text_span reads whole-content wraps only:
    `**"X"** Call now` draws neither quote. Letters still block it."""
    assert strip_quoted_elements('**"📞"** Call now') == "**📞** Call now"
    assert strip_quoted_elements('_"📞"_ muted') == "_📞_ muted"
    kept = '**bold** "📞" more text'
    assert strip_quoted_elements(kept) == kept, "letters before the pair block it"
    print("  ✓  strip: markers are skipped at the boundary, letters are not")


def test_strip_unit_a_run_declines_every_member():
    """A RUN: each pair counts as skippable when its neighbour asks whether it is
    at a boundary. Testing the raw text would decline only the first (empty
    prefix) and the last (empty suffix), leaving the middle drawing its quotes."""
    run = '"\u2b50" "\u2764\ufe0f" "\U0001f4ac" "\u2709" "\U0001f4de"'
    assert (
        strip_quoted_elements(run) == "\u2b50 \u2764\ufe0f \U0001f4ac \u2709 \U0001f4de"
    )
    assert strip_quoted_elements('"`a`" "`b`" "`c`"') == "`a` `b` `c`"
    assert (
        strip_quoted_elements('"[A](/a)" "[B](/b)" "[C](/c)"')
        == "[A](/a) [B](/b) [C](/c)"
    )
    print("  \u2713  strip: every member of a run is declined, not just the ends")


def test_strip_unit_a_run_does_not_reach_into_prose():
    """The run rule must not turn the mid-sentence case into a boundary."""
    kept = 'Press "\U0001f4de" to dial'
    assert strip_quoted_elements(kept) == kept
    # only the trailing one is at a boundary here
    assert (
        strip_quoted_elements('Press "\U0001f4de" to dial "\u2b50"')
        == 'Press "\U0001f4de" to dial \u2b50'
    )
    print("  \u2713  strip: a run never makes prose a boundary")


def test_quoted_run_is_one_text_leaf():
    ast = _processed('"\u2b50" "\u2764\ufe0f" "\U0001f4ac"')
    assert not _find_nodes(ast, NodeType.EMOJI), "a quoted run must not peel"
    assert "\u2b50 \u2764\ufe0f \U0001f4ac" in _all_contents(ast), (
        f"got {_all_contents(ast)!r}"
    )
    print("  \u2713  a quoted emoji run stays one text leaf")


def test_quoted_chip_run_is_not_chips():
    """The chip half of the run rule: backtick spans are not data points, so only
    the quote filter can decline them, every one in the run."""
    ast = _processed('"`a`" "`b`" "`c`"')
    assert not _find_nodes(ast, NodeType.INLINE_CODE), "a quoted chip run must not peel"
    print("  \u2713  a quoted chip run stays markers")


def test_unquoted_run_still_peels():
    ast = _processed("\u2b50 \u2764\ufe0f \U0001f4ac")
    assert len(_find_nodes(ast, NodeType.EMOJI)) == 3, "an UNQUOTED run must still peel"
    print("  \u2713  an unquoted emoji run is still three badges")


def test_strip_unit_apostrophe_guard():
    """An opening ' attached to a letter is an apostrophe, never a wrapper."""
    for kept in ("Alice's 📞", "don't panic"):
        assert strip_quoted_elements(kept) == kept, f"{kept!r} should be untouched"
    assert strip_quoted_elements("'📞'") == "📞"
    print("  ✓  strip: apostrophe guard holds, a real ' pair still works")


def test_quoted_emoji_is_text_not_a_badge():
    ast = _processed('"📞"')
    assert not _find_nodes(ast, NodeType.EMOJI), "quoted emoji must not peel"
    assert "📞" in _all_contents(ast), f"glyph lost: {_all_contents(ast)!r}"
    assert not any('"' in c for c in _all_contents(ast)), "quotes must be consumed"
    print('  ✓  "📞" → a text leaf holding the glyph, no EMOJI node')


def test_single_quoted_emoji_is_text():
    ast = _processed("'📞'")
    assert not _find_nodes(ast, NodeType.EMOJI)
    assert "📞" in _all_contents(ast)
    print("  ✓  '📞' → a text leaf, single quotes work too")


def test_quoted_link_is_an_inline_span():
    ast = _processed('"[Docs](/d)"')
    assert not _find_nodes(ast, NodeType.LINK), "quoted link must not become a button"
    assert "[Docs](/d)" in _all_contents(ast), f"got {_all_contents(ast)!r}"
    print('  ✓  "[Docs](/d)" → link markup left inline, no LINK node')


def test_quoted_chip_is_a_marker():
    """A backtick span is matched by _element_hits directly and is never a data
    point, so the datapoint filter cannot stop its peel; the quote filter does."""
    ast = _processed('"`code`"')
    assert not _find_nodes(ast, NodeType.INLINE_CODE), "quoted chip must not peel"
    assert "`code`" in _all_contents(ast), f"got {_all_contents(ast)!r}"
    print('  ✓  "`code`" → an inline marker, no INLINE_CODE node')


def test_bare_chip_still_a_chip():
    """The trap: a bare `code` span is its own range in _bracket_quote_ranges,
    so a filter testing "inside a protected range" would suppress every chip."""
    ast = _processed("`code`")
    assert _find_nodes(ast, NodeType.INLINE_CODE), "an UNQUOTED chip must still peel"
    print("  ✓  `code` unquoted → still a chip")


def test_bare_emoji_still_a_badge():
    ast = _processed("📞")
    assert _find_nodes(ast, NodeType.EMOJI), "an UNQUOTED emoji must still peel"
    print("  ✓  📞 unquoted → still an EMOJI node")


def test_quoted_element_keeps_the_display_tier():
    """The underscore ladder still means what it means around the pair. Also the
    offset case node.paren_quote_ranges cannot serve: Phase 6.055 consumes three
    underscores before the peel runs, shifting every stored offset by three."""
    ast = _processed('# Heading\n\n___"📞"___')
    leaves = [n for n in _leaf_nodes(ast) if n.content]
    tiered = [n for n in leaves if n.text_style == "display"]
    assert tiered, (
        f"expected a display tier, got {[(n.content, n.text_style) for n in leaves]}"
    )
    assert tiered[0].content == "📞", f"got {tiered[0].content!r}"
    assert not _find_nodes(ast, NodeType.EMOJI)
    print('  ✓  ___"📞"___ → a Display-tier glyph, not a Quaternary badge')


def test_quoted_element_keeps_emphasis_markers():
    """An asterisk wrapper is not consumed here — it is a paint-time span."""
    ast = _processed('*"📞"*')
    assert "*📞*" in _all_contents(ast), f"got {_all_contents(ast)!r}"
    assert not _find_nodes(ast, NodeType.EMOJI)
    print('  ✓  *"📞"* → *📞*, italic at paint time')


def test_struck_quoted_link_reaches_its_quotes():
    """`~` joins the wrapper set only for this lookup, so the disabled spelling
    does not leave its quotes drawn. A struck INLINE link is already painted as
    an ordinary one — the disabled paint belongs to the button."""
    ast = _processed('~~"[Docs](/d)"~~')
    assert "~~[Docs](/d)~~" in _all_contents(ast), f"got {_all_contents(ast)!r}"
    print('  ✓  ~~"[Docs](/d)"~~ → quotes consumed under the strike wrapper')


def test_quoted_emoji_in_a_heading_takes_the_heading_font():
    ast = _processed('# "📞" Contact')
    headings = _find_nodes(ast, "heading1")
    assert headings, "heading must keep its type"
    assert headings[0].content == "📞 Contact", f"got {headings[0].content!r}"
    assert not _find_nodes(ast, NodeType.EMOJI)
    print('  ✓  # "📞" Contact → glyph inline in the heading, no EMOJI node')


def test_quoted_emoji_at_the_trailing_boundary():
    ast = _processed('Questions? "📞"')
    assert "Questions? 📞" in _all_contents(ast), f"got {_all_contents(ast)!r}"
    print('  ✓  Questions? "📞" → stripped at the trailing boundary')


def test_midsentence_quoted_emoji_keeps_its_quotes():
    """ADR-500: the document's content is never reduced to improve its look."""
    ast = _processed('Press "📞" to dial')
    assert 'Press "📞" to dial' in _all_contents(ast), f"got {_all_contents(ast)!r}"
    print('  ✓  Press "📞" to dial → the author\'s own quotes survive')


def test_quoted_prose_keeps_its_quotes():
    ast = _processed('"This is prose"')
    assert '"This is prose"' in _all_contents(ast), f"got {_all_contents(ast)!r}"
    print('  ✓  "This is prose" → untouched')


def test_a_declined_emoji_beside_a_badge():
    """The whole point of a per-instance spelling: the two looks mix on one line."""
    ast = _processed('⭐ - "📞"')
    emojis = _find_nodes(ast, NodeType.EMOJI)
    assert len(emojis) == 1, (
        f"expected exactly one badge, got {[n.content for n in emojis]}"
    )
    assert emojis[0].content == "⭐"
    assert "📞" in _all_contents(ast)
    print('  ✓  ⭐ - "📞" → one badge and one text glyph, same line')


# ---------------------------------------------------------------------------
# Group G — existing unprotected cases still work (regression)
# ---------------------------------------------------------------------------


def test_pipe_separated_still_splits():
    # one | two | three — should still produce 3 SEGMENT nodes
    ast = _processed("one | two | three")
    segs = _find_nodes(ast, NodeType.SEGMENT)
    assert len(segs) == 3, f"Expected 3 SEGMENTs, got {len(segs)}"
    print("  ✓  regression: 'one | two | three' → 3 SEGMENT nodes")


def test_bare_day_range_not_split():
    # Mon-Fri (no parens) — day range data point; hyphen rule requires spaces,
    # so Mon-Fri stays as-is regardless of protection.
    ast = _processed("Mon-Fri")
    segs = _find_nodes(ast, NodeType.SEGMENT)
    assert not segs, f"Expected no SEGMENT for 'Mon-Fri', got {len(segs)}"
    print("  ✓  regression: 'Mon-Fri' (no parens) → not split")


def test_kv_outside_quotes_splits():
    # **Progress:** 60% — a display's KV split must still work when not protected
    ast = _processed("**Progress:** 60%")
    kv_nodes = _find_nodes(ast, NodeType.KEY_VALUE)
    assert kv_nodes, "Expected KEY_VALUE node, got none"
    print("  ✓  regression: '**Progress:** 60%' → KV split still works")


def test_emoji_outside_parens_extracted():
    # ⭐ Popular — leading emoji should still be extracted
    ast = _processed("⭐ - Popular")
    emojis = _find_nodes(ast, NodeType.EMOJI)
    assert emojis, "Expected EMOJI node for '⭐', got none"
    print("  ✓  regression: '⭐ Popular' (no parens) → emoji extracted as expected")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS = [
    test_pq_ranges_empty,
    test_pq_ranges_parens,
    test_pq_ranges_nested_parens,
    test_pq_ranges_quotes,
    test_pq_ranges_unbalanced_paren,
    test_pq_ranges_unmatched_quote,
    test_pq_ranges_skips_dp_covered_delimiters,
    test_pq_ranges_multiple,
    test_pq_ranges_backtick,
    test_pq_ranges_single_quote,
    test_pq_ranges_apostrophe_not_protected,
    test_pq_ranges_match_the_one_kind_at_a_time_reading,
    test_merge_pq_empty,
    test_merge_pq_no_overlap,
    test_merge_pq_overlapping,
    test_quoted_comma_list_stays_whole,
    test_paren_and_outer_commas_stay_whole,
    test_paren_day_range_not_split,
    test_paren_emoji_content_not_split,
    test_no_paren_emoji_content_keeps_annotations_inline,
    test_quoted_kv_not_split,
    test_quoted_value_after_a_colon_not_split,
    test_paren_kv_segments_inner_kv_not_split,
    test_quoted_time_not_extracted,
    test_paren_size_not_split,
    test_backtick_content_not_split,
    test_single_quote_content_not_split,
    test_quoted_time_dp_preserved_on_leaf,
    test_paren_size_dps_preserved_on_leaf,
    test_inline_code_dp_preserved_on_inline_code_node,
    test_pipe_separated_still_splits,
    test_bare_day_range_not_split,
    test_kv_outside_quotes_splits,
    test_emoji_outside_parens_extracted,
    test_strip_unit_boundary_only,
    test_strip_unit_needs_a_lone_element,
    test_strip_unit_boundary_skips_markers,
    test_strip_unit_a_run_declines_every_member,
    test_strip_unit_a_run_does_not_reach_into_prose,
    test_quoted_run_is_one_text_leaf,
    test_quoted_chip_run_is_not_chips,
    test_unquoted_run_still_peels,
    test_strip_unit_apostrophe_guard,
    test_quoted_emoji_is_text_not_a_badge,
    test_single_quoted_emoji_is_text,
    test_quoted_link_is_an_inline_span,
    test_quoted_chip_is_a_marker,
    test_bare_chip_still_a_chip,
    test_bare_emoji_still_a_badge,
    test_quoted_element_keeps_the_display_tier,
    test_quoted_element_keeps_emphasis_markers,
    test_struck_quoted_link_reaches_its_quotes,
    test_quoted_emoji_in_a_heading_takes_the_heading_font,
    test_quoted_emoji_at_the_trailing_boundary,
    test_midsentence_quoted_emoji_keeps_its_quotes,
    test_quoted_prose_keeps_its_quotes,
    test_a_declined_emoji_beside_a_badge,
]

if __name__ == "__main__":
    print("Paren/Quote Protection Tests")
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
