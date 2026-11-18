"""
The VALUE escape: ``\\/`` ``\\%`` ``\\$`` mean "this token is text".

Markdown carries two escapes with two different meanings, told apart by
which character is escaped:

    \\-  \\|  \\:  \\,  \\.     do not SPLIT here   — detection still sees through
    \\/  \\%  \\$            this token is TEXT   — detection stops

The second set is what lets an author keep a value where the drawn families
would otherwise claim it: a bar, a ring, a chart point or a stat tile is
declined per instance, without turning the family off for the whole document
in THEME.md. Without it the only opt-out is "do not separate the value", which
costs the arrangement the author wanted.

The escaped character stays a plain character in the output — the backslash is
markup and never reaches the tree — so each test compares an escaped line
against the unescaped twin that must still draw.

Run with: uv run python tests/value_escape_tests.py
"""

from markdown_datapoint_split_tests import _processed_with_criteria

from md2ui.pipeline.grouper_escapes import _declines_the_reading, _value_escape_spans
from md2ui.pipeline.grouper_types import MarkdownGroupNode


def _nodes(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    out = [node]
    for c in node.children:
        out.extend(_nodes(c))
    return out


def _displays(node: MarkdownGroupNode) -> list[str]:
    return [n.datapoint_display for n in _nodes(node) if n.datapoint_display]


def _texts(node: MarkdownGroupNode) -> list[str]:
    return [n.content for n in _nodes(node) if n.content and not n.children]


def _dps(node: MarkdownGroupNode) -> list[str]:
    return [dp["matched"] for n in _nodes(node) for dp in n.data_points]


def _doc(line: str) -> MarkdownGroupNode:
    return _processed_with_criteria(f"## S\n\n{line}\n")


def test_an_escaped_value_draws_nothing_and_its_twin_does():
    drawn = _doc("4/8")
    assert _displays(drawn) == ["ratio_bar"], _displays(drawn)
    plain = _doc("4\\/8")
    assert _displays(plain) == [], _displays(plain)
    assert _dps(plain) == [], "an escaped token yields no data point"
    assert "4/8" in _texts(plain), _texts(plain)
    print("  ✓  4/8 draws a bar; 4\\/8 is the same characters as text")


def test_the_escape_covers_every_punctuation_family():
    """One rule, four families: the slash ratios, the percentage bar and the
    currency stat tile all read punctuation this set can carry."""
    for line in ("750\\/1800 Kcal", "Elapsed: 45\\%", "\\$412M", "Minutes: 7\\/8"):
        ast = _doc(line)
        assert _displays(ast) == [], f"{line}: {_displays(ast)}"
        assert _dps(ast) == [], f"{line}: {_dps(ast)}"
    # ...and their unescaped twins are exactly what still draws.
    assert _displays(_doc("750/1800 Kcal")) == ["unit_ratio"]
    assert _displays(_doc("Elapsed: 45%")) == ["kv_percent_bar"]
    print("  ✓  ratio / unit ratio / percentage / currency all decline")


def test_an_escaped_value_leaves_its_line_as_written():
    """The escape declines the DRAWING: with no display left to read the pair,
    the line is the one text its author wrote, markers and colon kept."""
    drawn = _doc("_Expires:_ 12/26")
    assert [n for n in _nodes(drawn) if n.type == "key-value"], "the twin draws a pair"
    ast = _doc("_Expires:_ 12\\/26")
    assert not [n for n in _nodes(ast) if n.type == "key-value"]
    assert _texts(ast) == ["S", "_Expires:_ 12/26"], _texts(ast)
    assert _displays(ast) == []
    print("  ✓  an escaped value leaves its line one text, as written")


def test_no_backslash_reaches_the_tree():
    for line in ("4\\/8", "Elapsed: 45\\%", "\\$412M", "_Expires:_ 12\\/26"):
        assert not any("\\" in t for t in _texts(_doc(line))), line
    print("  ✓  the backslash is markup and is never drawn")


def test_an_escaped_row_leaves_the_chart_without_falling_back_to_a_bar():
    """A chart is a contiguous run of Key: percentage rows. An escaped row is
    not one, so it breaks the run exactly as any other non-percentage row
    does — and it draws no bar of its own either."""
    rows = "- Jan: 75\\%\n- Feb: 50\\%\n- Mar: 100\\%\n"
    ast = _processed_with_criteria(f"## Spending\n\n{rows}")
    assert not any(n.chart_group for n in _nodes(ast)), "no chart from escaped rows"
    assert _displays(ast) == [], _displays(ast)

    survivors = "- Jan: 75\\%\n- Feb: 50%\n- Mar: 100%\n- Apr: 20%\n"
    ast = _processed_with_criteria(f"## Spending\n\n{survivors}")
    charts = [n for n in _nodes(ast) if n.chart_group]
    assert len(charts) == 1, "the remaining run of three still charts"
    data = charts[0].chart_data
    assert data is not None
    assert [r["label"] for r in data["rows"]] == ["Feb", "Mar", "Apr"]
    print("  ✓  an escaped row drops out; a surviving run of 3 still charts")


def test_a_legacy_comma_escape_still_keeps_its_datapoint():
    """``\\,`` remains accepted and does not cancel datapoint detection."""
    ast = _doc("February 04\\, 9:17 PM")
    assert _dps(ast), "the escaped comma must not cancel detection"
    assert not any("\\" in t for t in _texts(ast))
    print("  ✓  \\, still keeps its datapoint whole")


def test_a_tight_separator_escape_declines_the_reading_too():
    """The rule read positionally, which is what spells the day chip's opt-out.

    A separator only separates with a space around it. An escape with none is
    not declining a split, so the only thing left for it to decline is the
    token's reading — and that is how ``Mon\\-15`` says "text", while every
    documented separator escape, each sitting against a space, is untouched.
    """
    assert _declines_the_reading("Mon\\-15", 3)  # tight: n before, 1 after
    assert not _declines_the_reading("Aug 14 \\- Sun", 7)  # spaced both sides
    assert not _declines_the_reading("Cat\\, Dog", 3)  # space after
    assert not _declines_the_reading("\\- not a list", 0)  # line start
    assert _declines_the_reading("4\\/8", 1)  # a value escape, always
    # The span is the whole whitespace-delimited token, so nothing smaller
    # inside it can be read instead.
    assert _value_escape_spans("left 12\\/26 right") == [(5, 11)]

    ast = _doc("Mon\\-15")
    assert _displays(ast) == [], "an escaped day chip must not draw"
    assert _texts(ast)[-1] == "Mon-15", _texts(ast)
    assert _displays(_doc("Mon-15")) == ["date_chip"], "the twin still draws"
    print("  ✓  a TIGHT separator escape declines the token (Mon\\-15)")


TESTS = [
    test_an_escaped_value_draws_nothing_and_its_twin_does,
    test_the_escape_covers_every_punctuation_family,
    test_an_escaped_value_leaves_its_line_as_written,
    test_no_backslash_reaches_the_tree,
    test_an_escaped_row_leaves_the_chart_without_falling_back_to_a_bar,
    test_a_legacy_comma_escape_still_keeps_its_datapoint,
    test_a_tight_separator_escape_declines_the_reading_too,
]


if __name__ == "__main__":
    print("Value Escape Tests")
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
