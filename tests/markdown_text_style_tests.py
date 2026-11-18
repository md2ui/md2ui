"""
Strikethrough (``~~``) marker-hygiene parity tests for MarkdownGrouper.

The helpers must treat ``~~`` as they treat ``**``/``*``, leaving no orphaned
or doubled strikethrough markers after a split:
  - ``_balance_markdown_markers``  (dangling / doubled ``~~``)
  - ``_extract_key_from_prefix``   (colon-only ``~~Strikethrough:~~``)
  - ``_split_kv_styled``           (``~~Key:~~ value`` key-value)
  - the boundary peel             (orphan ``~~`` discarded, each split keeps ``~~``)

Pure static-method / criteria=None checks so they are deterministic.
"""

from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.markdown_grouper import MarkdownGroupNode, MarkdownGrouper, NodeType
from md2ui.pipeline.grouper_inline_marks import _balance_markdown_markers
from md2ui.pipeline.grouper_value_splits import _split_kv_styled
from md2ui.pipeline.grouper_node_reads import _extract_key_from_prefix


def _leaves(node: MarkdownGroupNode) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if not node.children and node.content:
        out.append((node.type, node.content))
    for c in node.children:
        out.extend(_leaves(c))
    return out


def _processed(text: str) -> MarkdownGroupNode:
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    return g.ast


# --- _balance_markdown_markers -------------------------------------------


def test_balance_dangling_close_strike():
    # A trailing ``~~`` with no opener gets one prepended (not doubled).
    assert _balance_markdown_markers("€~~") == "~~€~~"


def test_balance_already_balanced_strike_unchanged():
    assert _balance_markdown_markers("~~€~~") == "~~€~~"


def test_balance_dangling_open_strike():
    assert _balance_markdown_markers("~~each") == "~~each~~"


# --- _extract_key_from_prefix --------------------------------------------


def test_extract_key_strike_colon_only():
    assert _extract_key_from_prefix("~~Strikethrough:~~") == "~~Strikethrough~~"


def test_extract_key_strike_colon_only_multiword():
    assert (
        _extract_key_from_prefix("~~Strikethrough more words:~~")
        == "~~Strikethrough more words~~"
    )


def test_extract_key_strike_no_colon_is_none():
    assert _extract_key_from_prefix("~~Strikethrough~~") is None


# --- _split_kv_styled -----------------------------------------------------


def test_kv_styled_strike_end_form():
    assert _split_kv_styled("~~KeyStrikethrough:~~ value", []) == [
        (NodeType.KEY, "~~KeyStrikethrough~~"),
        (NodeType.VALUE, "value"),
    ]


def test_kv_styled_strike_no_value_is_none():
    # No value after the colon → not a KV pair (colon-only handled elsewhere).
    assert _split_kv_styled("~~Strikethrough:~~", []) is None


def test_kv_styled_bold_still_works():
    assert _split_kv_styled("**KeyBold:** value", []) == [
        (NodeType.KEY, "**KeyBold**"),
        (NodeType.VALUE, "value"),
    ]


# --- a peel keeps ~~, no orphan/doubled -----------------------------------


def test_split_strike_interior_dp_keeps_markers():
    # `~~$3.59 each~~`: "each" is regular text, so the line is prose and stays
    # whole. The marker invariant — no orphaned pure-marker node, no doubled
    # `~~~~` — is asserted on the run spelling, where a cut happens.
    contents = [c for _, c in _leaves(_processed("~~$3.59 each~~"))]
    assert contents == ["~~$3.59 each~~"], contents
    run = [c for _, c in _leaves(_processed("~~$3.59~~ **$2.99**"))]
    assert all(set(c) - set("~") for c in run), run  # no node is only "~"
    assert not any("~~~~" in c for c in run), run
    print("  ✓  prose keeps its markers; a run cuts without orphaning one")


def test_split_strike_dp_in_middle_three_pieces():
    # `~~strike $5 here~~` is prose inside a strike wrap: the words around the
    # value are regular text, so the line is not cut (ADR-205) and the markers
    # stay exactly where the author put them.
    leaves = _leaves(_processed("~~strike $5 here~~"))
    contents = [c for _, c in leaves]
    assert contents == ["~~strike $5 here~~"], contents
    print("  ✓  a strike-wrapped sentence keeps its value and its markers")


def test_colon_only_strike_kept_whole():
    # No colon is stripped (ADR-205): the line draws as written.
    leaves = _leaves(_processed("~~Strikethrough:~~"))
    assert leaves == [(NodeType.TEXT, "~~Strikethrough:~~")], leaves


def test_kv_styled_strike_wrapping_emphasis():
    # `~~**Key:**~~ value` — the colon sits inside the inner emphasis, so
    # _KV_STRIKE_END_RE's `[^~:]+` key group cannot reach it. The wrapper is
    # peeled, the inner branches run, and both wrappers come back on the key.
    for wrap, marker in (("**", "**"), ("*", "*"), ("***", "***"), ("__", "__")):
        s = f"~~{wrap}Key:{marker}~~ value"
        assert _split_kv_styled(s) == [
            (NodeType.KEY, f"~~{wrap}Key{marker}~~"),
            (NodeType.VALUE, "value"),
        ], s
    print("  ✓  `~~**Key:**~~ value` keeps both wrappers, drops the colon")


def test_kv_styled_strike_wrapping_whole_pair():
    # Whole-line wrap: the value keeps the wrapper too, like the `**k: v**` form.
    assert _split_kv_styled("~~**Key: value**~~") == [
        (NodeType.KEY, "~~**Key**~~"),
        (NodeType.VALUE, "~~**value**~~"),
    ]
    print("  ✓  `~~**Key: value**~~` re-wraps both sides")


def test_kv_styled_nested_strike_respects_protected_colon():
    # The peel shifts positions, so the protected-range check must shift with
    # it — a colon inside an annotated datapoint still refuses to split.
    s = "~~**8:**~~ value"
    assert _split_kv_styled(s) is not None, "splits when free"
    colon = s.index(":")
    assert _split_kv_styled(s, [(colon - 1, colon + 2)]) is None
    # …and with leading whitespace, which shifts `offset` as well.
    s2 = "  " + s
    colon2 = s2.index(":")
    assert _split_kv_styled(s2, [(colon2 - 1, colon2 + 2)]) is None
    assert _split_kv_styled(s2, [(0, 2)]) is not None
    print("  ✓  the peel keeps protected colons protected")


TESTS = [
    test_balance_dangling_close_strike,
    test_balance_already_balanced_strike_unchanged,
    test_balance_dangling_open_strike,
    test_extract_key_strike_colon_only,
    test_extract_key_strike_colon_only_multiword,
    test_extract_key_strike_no_colon_is_none,
    test_kv_styled_strike_end_form,
    test_kv_styled_strike_no_value_is_none,
    test_kv_styled_bold_still_works,
    test_split_strike_interior_dp_keeps_markers,
    test_split_strike_dp_in_middle_three_pieces,
    test_colon_only_strike_kept_whole,
    test_kv_styled_strike_wrapping_emphasis,
    test_kv_styled_strike_wrapping_whole_pair,
    test_kv_styled_nested_strike_respects_protected_colon,
]


if __name__ == "__main__":
    print("Markdown Text-Style (strikethrough) Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓  {test.__name__}")
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
