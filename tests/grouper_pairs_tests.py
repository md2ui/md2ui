"""
A pair exists only while a display reads it (ADR-205, ``grouper_pairs``).

``Key: value`` is text, drawn as written: the grouper cuts the pair, and Phase
6.075 puts it back to its line when no display or control reads it. "Its line"
has one test, the escaped twin ``Key\\: value``, whose colon never pairs: the
two must make the same tree, wherever the line sits and however it is styled.
A pair a display reads is untouched, and ``check`` still sees a chart row that
did not draw as the pair it was (``check_charts.paired``).

Run with: uv run python tests/grouper_pairs_tests.py
"""

from md2ui import check_charts, session
from md2ui.pipeline.grouper_pairs import unpair_unread
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType

_KIT = session.load_grouping_kit()


def _group(text: str) -> MarkdownGroupNode:
    root = session.group_markdown(text + "\n", _KIT)
    assert root is not None, text
    return root


def _shape(node: MarkdownGroupNode) -> list:
    """Type, content (an escaped colon read as a colon), tier and children."""
    content = (node.content or "").replace("\\:", ":")
    return [
        str(node.type),
        content,
        node.text_style,
        [_shape(c) for c in node.children],
    ]


def _pairs(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    own = [node] if node.type == NodeType.KEY_VALUE else []
    return own + [p for c in node.children for p in _pairs(c)]


def test_a_line_no_display_reads_is_its_escaped_twin():
    for line in (
        "Day one: the old town",
        "**Day one:** the old town",
        "## Day one: the old town",
        "- Day one: the old town",
        "_Day one: the old town_",
        "Panelists:",
        "Cover:\n![x](https://example.com/one.jpg)",
        # A picture on the pair's own line is a picture, as in its twin.
        "Cover: ![x](https://example.com/one.jpg)",
        "**Cover:** ![Album](https://example.com/one.jpg)",
        "- **Cover:** ![Album](https://example.com/one.jpg)",
    ):
        twin = line.replace(":", "\\:", 1)
        assert _shape(_group(line)) == _shape(_group(twin)), line
        assert not _pairs(_group(line)), line
    print("  ✓  a line no display reads is the tree of its escaped twin")


def test_a_separator_outranks_the_colon():
    # The line divides where its author divided it, then each piece is text.
    for line in (
        "Status: open - Owner: Ana",
        "Price: $12 | Size: M",
        "v1.0: alpha | beta",
        "**Key:** v1 | v2 | v3",
        "K: 1,293 - `x` : vs last month",
    ):
        twin = line.replace(":", "\\:", 1)
        assert _shape(_group(line)) == _shape(_group(twin)), line
    print("  ✓  a separator divides first; each piece is its escaped twin")


def test_a_pair_a_display_reads_stays_a_pair():
    for line, display in (
        ("Progress: 60%", "kv_percent_bar"),
        ("Minutes: 7/8", "unit_ratio"),
        ("Price: $710 → $713 → $720", "line_chart"),
    ):
        (pair,) = _pairs(_group(line))
        assert pair.datapoint_display == display, (line, pair.datapoint_display)
    (slider,) = _pairs(_group("Volume: [[62%]]"))
    assert any(c.type == NodeType.DRAWING_ELEMENT for c in _walk(slider)), "slider"
    rows = "- Revenue: 40%\n- Costs: 25%\n- Profit: 35%"
    chart = next(n for n in _walk(_group(rows)) if n.chart_group)
    assert len(_pairs(chart)) == 3, "every chart row keeps its pair"
    print("  ✓  bars, rings, lines, sliders and chart rows keep their pairs")


def test_check_still_reads_a_row_a_chart_left_out():
    # The row with a word beside its value is text; the chart notes read it
    # as the pair it was, so they can name it and say why.
    ast = _group("- Revenue: 40%\n- Costs: 25% est\n- Profit: 35%")
    ((row, _),) = check_charts.rows_left_out(ast)
    assert "Costs" in row, row
    print("  ✓  check names the row a chart left out, from the pair it was")


def test_the_pass_leaves_a_finished_tree_as_it_is():
    # Every pair it could restore is already its line, and every pair a display
    # reads is left alone: running it again on a grouped tree changes nothing.
    doc = "Day one: old town\n\nProgress: 60%\n\n- Revenue: 40%\n- Costs: 25%\n- Profit: 35%"
    root = _group(doc)
    before = _shape(root)
    unpair_unread(root, _KIT[1])
    assert _shape(root) == before
    print("  ✓  the pass on a finished tree changes nothing")


def _walk(node: MarkdownGroupNode):
    yield node
    for c in node.children:
        yield from _walk(c)


TESTS = [
    test_a_line_no_display_reads_is_its_escaped_twin,
    test_a_separator_outranks_the_colon,
    test_a_pair_a_display_reads_stays_a_pair,
    test_check_still_reads_a_row_a_chart_left_out,
    test_the_pass_leaves_a_finished_tree_as_it_is,
]

if __name__ == "__main__":
    print("Grouper Pairs Tests")
    print("=" * 50)
    for test in TESTS:
        test()
    print("=" * 50)
    print(f"All {len(TESTS)} tests passed.")
