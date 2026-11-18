"""
Unit tests for "one stacks, all stack" (generator_fit_votes, ADR-301): inside a
repeated grid run, a member whose key and value cannot share a row makes every
member stack its key over its value (a pair is a display's since ADR-205: these
are percentage bars); the votes never move the run's column count; a `:::` row
that wraps its cells stacks every row of its run; one wraps, all wrap: a line, or a weighted row, that wraps before a piece
makes every member's same line wrap there, between sibling lines
that stack too, a line inside a grid card voting in both
runs, while a line of links casts nothing; and a run's spacers give way
together, through a pin the renderer obeys; and a stacked run of spring rows
of the same regions shares its column edges.

Run with: uv run tests/layout_fit_votes_tests.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import skia

from md2ui.pipeline import generator_fit_votes
from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.grouper_types import NodeType
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.render_measure import _layout_row
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.markdown_grouper import MarkdownGrouper, MarkdownGroupNode
from md2ui.pipeline.theme import Theme

# Four percentage bars: three whose key shares a row with its bar in a quarter
# of 800px, one whose key is too long to.
_ONE_TOO_LONG = """\
CPU: 40%

Memory: 60%

Disk: 80%

The network interface throughput of the primary cluster gateway: 20%
"""

_ALL_FIT = """\
CPU: 40%

Memory: 60%

Disk: 80%

Network: 20%
"""


def _ast(text: str) -> MarkdownGroupNode:
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    return g.ast


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def _generate(text: str, theme=None, width: float = 800.0):
    ast = _ast(text)
    return ast, LayoutGenerator().generate(ast, width, theme=theme)


def _without_votes(fn):
    """Run *fn* with every fit answered by its own member alone."""
    names = ("vote", "row_stacks", "line_breaks", "spacer_row")
    saved = [getattr(generator_fit_votes, n) for n in names]
    generator_fit_votes.vote = lambda _polls, _node, stacked: stacked
    generator_fit_votes.row_stacks = lambda _polls, _node, _rows: False
    generator_fit_votes.line_breaks = lambda *_: set()
    generator_fit_votes.spacer_row = lambda *_: None
    try:
        return fn()
    finally:
        for n, f in zip(names, saved):
            setattr(generator_fit_votes, n, f)


def _pair_shapes(ast, layout) -> list[str]:
    """For every key/value pair, in order: the type of the smallest layout node
    holding both its key and its value — ``row`` side by side, ``col`` stacked."""
    parent = {}
    for n in _walk(layout):
        for c in n.children:
            parent[id(c)] = n
    leaves = {n.content_id: n for n in _walk(layout) if n.content_id}
    shapes = []
    for pair in _walk(ast):
        if pair.type != NodeType.KEY_VALUE:
            continue
        sides = [c for c in pair.children if c.type in (NodeType.KEY, NodeType.VALUE)]
        ids = [{x.node_id for x in _walk(s)} for s in sides]
        firsts = [next(leaves[i] for i in s if i in leaves) for s in ids]
        up = firsts[0]
        while not all(any(x.content_id in s for x in _walk(up)) for s in ids):
            up = parent[id(up)]
        shapes.append(up.type)
    return shapes


def _grid_cols(layout) -> list[int]:
    return [n.grid_cols for n in _walk(layout) if getattr(n, "grid", False)]


def test_one_member_that_cannot_fit_stacks_every_member():
    ast, layout = _generate(_ONE_TOO_LONG, Theme())
    assert _grid_cols(layout), "the four pairs grid"
    _, alone = _without_votes(lambda: _generate(_ONE_TOO_LONG, Theme()))
    assert _pair_shapes(_ast(_ONE_TOO_LONG), alone) == ["row", "row", "row", "col"]
    assert _pair_shapes(ast, layout) == ["col"] * 4


def test_members_that_all_fit_keep_their_rows():
    ast, layout = _generate(_ALL_FIT, Theme())
    assert _grid_cols(layout), "the four pairs grid"
    assert _pair_shapes(ast, layout) == ["row"] * 4


def test_the_votes_never_move_the_column_count():
    for text in (_ONE_TOO_LONG, _ALL_FIT):
        for width in (500.0, 800.0, 1200.0):
            _, voted = _generate(text, Theme(), width)
            _, alone = _without_votes(lambda: _generate(text, Theme(), width))
            assert _grid_cols(voted) == _grid_cols(alone), (text, width)


# The Artists shape (tests/tests-image-issues.md): two `:::` rows, a picture
# beside a name, one name much longer than the other.
_ARTISTS = (
    ";;;\nAlpha\n:::\n**Bad Bunny**\n\n"
    ";;;\nAlpha\n:::\n**This Is Taylor Swift on tour**\n;;;\n"
)


def _measure_line(node, _role=None) -> float:
    """8px a character: enough to give the two names different asks."""
    return 8.0 * sum(len(x.content or "") for x in _walk(node) if not x.children)


def _row_shapes(width: float) -> tuple[list[str], list[str]]:
    """Each `:::` row's shape — ``row`` beside, ``col`` stacked — with the run's
    votes and without them."""

    def shapes():
        ast = _ast(_ARTISTS)
        layout = LayoutGenerator().generate(ast, width, measure_line=_measure_line)
        assert _grid_cols(layout) == [2], "the two rows are one gridded run"
        parent = {id(c): n for n in _walk(layout) for c in n.children}
        out = []
        for row in (n for n in _walk(ast) if n.column_row_group):
            first, *_, last = [x.node_id for x in _walk(row) if not x.children]
            up = next(n for n in _walk(layout) if n.content_id == first)
            while not any(x.content_id == last for x in _walk(up)):
                up = parent[id(up)]
            out.append(up.type)
        return out

    return shapes(), _without_votes(shapes)


def test_a_row_that_wraps_its_cells_stacks_every_row_of_its_run():
    voted, alone = _row_shapes(500.0)
    assert alone == ["row", "col"], "only the long name wraps on its own"
    assert voted == ["col", "col"]


def test_rows_that_all_fit_stay_beside():
    assert _row_shapes(700.0) == (["row", "row"], ["row", "row"])


def _grid_cells(layout) -> list:
    return [c for n in _walk(layout) if getattr(n, "grid", False) for c in n.children]


def test_one_line_that_wraps_its_pieces_wraps_every_line_of_its_run():
    # List items grid; alone, only the last line wraps its pieces.
    text = "- Alpha - Beta\n- Alpha - Beta\n- Alpha - " + " ".join(["Beta"] * 12)
    _, layout = _generate(text, width=600.0)
    _, alone = _without_votes(lambda: _generate(text, width=600.0))
    assert [c.type for c in _grid_cells(alone)] == ["row", "row", "col"]
    assert [c.type for c in _grid_cells(layout)] == ["col"] * 3
    assert [len(c.children) for c in _grid_cells(layout)] == [2] * 3
    assert _grid_cols(layout) == _grid_cols(alone)


def test_lines_that_all_fit_stay_rows():
    text = "- Alpha - Beta\n- Alpha - Beta\n- Alpha - Beta gamma\n"
    _, layout = _generate(text, width=600.0)
    assert [c.type for c in _grid_cells(layout)] == ["row"] * 3


def test_a_card_whose_line_wraps_wraps_the_others():
    # Three cards, each a title over one line of pieces; only the last line is
    # long enough to wrap on its own, and the others' lines follow it.
    text = "\n\n".join(
        f"**Card {i}**\nAlpha - {tail}"
        for i, tail in enumerate(
            ("Beta", "Beta", "Beta gamma delta epsilon zeta eta theta iota kappa")
        )
    )
    _, layout = _generate(text, width=600.0)
    _, alone = _without_votes(lambda: _generate(text, width=600.0))
    last = lambda lay: [c.children[-1].type for c in _grid_cells(lay)]  # noqa: E731
    assert last(alone) == ["row", "row", "col"], "alone only the long line wraps"
    assert last(layout) == ["col"] * 3


def _line_shapes(text: str, width: float) -> tuple[list[str], list[str]]:
    """Each source line's shape -- ``row`` on one line, ``col`` wrapped -- with
    the runs' votes and without them; 8px a character."""

    def shapes():
        ast = _ast(text)
        layout = LayoutGenerator().generate(ast, width, measure_line=_measure_line)
        out = []
        for n in _walk(layout):
            ids = [c.content_id or "" for c in n.children]
            if len(ids) == 2 and ids[0].endswith(".0") and ids[1].endswith(".1"):
                out.append(n.type)
        return out

    return shapes(), _without_votes(shapes)


def test_sibling_lines_wrap_together():
    # Three stacked lines of one kind; alone, only the long third one wraps.
    text = "Alpha - Beta\nAlpha - Beta\nAlpha - Beta gamma delta epsilon\n"
    voted, alone = _line_shapes(text, 200.0)
    assert alone == ["row", "row", "col"], "alone only the long line wraps"
    assert voted == ["col"] * 3


def test_link_lines_wrap_alone():
    # A line of links is a cloud: it wraps as words do, and casts nothing.
    text = "[Alpha](/a) [Beta](/b)\n[Alpha](/a) [Beta](/b)\n"
    text += "[Alpha](/a) [Beta gamma delta epsilon](/b)\n"
    assert _line_shapes(text, 200.0) == (["row", "row", "col"],) * 2


def test_a_line_in_a_grid_card_votes_in_both_runs():
    # Two cards of two lines; alone, only the second card's last line wraps.
    # Its card's other line follows it, and so do the twin card's lines.
    text = "\n\n".join(
        f"**Card {i}**\nAlpha - Beta\nAlpha - {tail}"
        for i, tail in enumerate(("Beta", "Beta gamma delta epsilon"))
    )
    voted, alone = _line_shapes(text, 450.0)
    assert alone == ["row", "row", "row", "col"], "alone only one line wraps"
    assert voted == ["col"] * 4


def test_a_weighted_row_that_wraps_wraps_every_row_of_its_run():
    text = _ARTISTS.replace(":::\n", ":::0\n")

    def shapes(width):
        ast = _ast(text)
        layout = LayoutGenerator().generate(ast, width, measure_line=_measure_line)
        assert _grid_cols(layout) == [2], "the two rows are one gridded run"
        return [c.type for c in _grid_cells(layout)]

    assert _without_votes(lambda: shapes(400.0)) == ["row", "col"]
    assert shapes(400.0) == ["col", "col"]
    assert shapes(600.0) == ["row", "row"]


# Case I of tests-spacer-edges.md: three cards, each line opening with a spacer.
_SPACED_CARDS = (
    "## Shipping\n+++++ Delta epsilon zeta theta\n\n"
    "## Returns\n+++++ Within thirty days of delivery\n\n"
    "## Support\n+++++ Chat with us any time\n"
)


def _spacer_pins(width: float) -> list:
    ast = _ast(_SPACED_CARDS)
    layout = LayoutGenerator().generate(ast, width, theme=Theme())
    rows = [
        n
        for n in _walk(layout)
        if n.type == "row"
        and any((c.render_properties or {}).get("spacer") for c in n.children)
    ]
    return [(r.render_properties or {}).get("spacers") for r in rows]


def test_a_runs_spacers_give_way_together():
    # At 480 the cards are short of room for their spacers: all give way. Wide,
    # none is, and every card keeps them. Alone, nothing is pinned.
    assert _spacer_pins(480.0) == ["give_way"] * 3
    assert _spacer_pins(1400.0) == ["keep"] * 3
    assert _without_votes(lambda: _spacer_pins(480.0)) == [None] * 3


def _spacers_drawn(pin: str | None, width: float) -> list[float]:
    """The spacer widths the renderer lays out in a row *width* wide, pinned
    *pin* by its run."""
    face = skia.Typeface.MakeDefault()
    spacer = {"spacer": {"axis": "row", "size": 40.0, "binds": None}}
    row = LayoutNode(
        type="row",
        ratios=[1.0, 1.0],
        children=[
            LayoutNode(type="-", ratios=[], children=[], render_properties=spacer),
            LayoutNode(type="-", ratios=[], children=[], content_id="t"),
        ],
        render_properties={"spacers": pin} if pin else None,
    )
    index = {"t": {"type": "text", "content": "Alpha"}}
    placed, _, _ = _layout_row(row, width, index, FontSet(*[face] * 5), Theme())
    return [w for c, _, w, *_ in placed if (c.render_properties or {}).get("spacer")]


def test_the_renderer_obeys_the_runs_spacer_pin():
    # With room to spare a row keeps its spacer unless its run gave way; short
    # of room its spacer leaves the row unless its run kept them.
    assert _spacers_drawn(None, 600.0) == [40.0]
    assert _spacers_drawn("give_way", 600.0) == []
    assert _spacers_drawn(None, 30.0) == []
    assert len(_spacers_drawn("keep", 30.0)) == 1


# Two list rows of one spring shape whose
# names and chips differ in length, so each row's own asks differ.
_FARE = "**{}** : _Nonstop_ ... Fare (EUR): {} ... `{}`"
_FARES = [
    _FARE.format("Lisbon to New York", "612 → 598 → 640 → 575 → 549", "-63"),
    _FARE.format("Porto to Paris", "88 → 92 → 79 → 84 → 81", "-7"),
]


def _spring_asks(lines: list[str]) -> list[list[float]]:
    text = "".join(f"- {line}\n" for line in lines)
    layout = LayoutGenerator().generate(_ast(text), 767.0, measure_line=_measure_line)
    return [n.ratios for n in _walk(layout) if n.spring]


def test_a_stacked_run_of_spring_rows_shares_its_column_edges():
    # Each region takes the run's widest ask, so the chart sits at one x.
    asks = _spring_asks(_FARES)
    assert len(asks) == 2 and len(asks[0]) == 3, asks
    assert asks[0] == asks[1], asks


def test_spring_rows_of_other_regions_keep_their_own_asks():
    # A row without the chip is not the same row: nothing is shared.
    asks = _spring_asks([_FARES[0], _FARES[1].rsplit(" ... ", 1)[0]])
    assert [len(a) for a in asks] == [3, 2], asks
    assert asks[0][:2] != asks[1], asks


TESTS = [
    test_one_member_that_cannot_fit_stacks_every_member,
    test_members_that_all_fit_keep_their_rows,
    test_the_votes_never_move_the_column_count,
    test_a_row_that_wraps_its_cells_stacks_every_row_of_its_run,
    test_rows_that_all_fit_stay_beside,
    test_one_line_that_wraps_its_pieces_wraps_every_line_of_its_run,
    test_lines_that_all_fit_stay_rows,
    test_a_card_whose_line_wraps_wraps_the_others,
    test_a_weighted_row_that_wraps_wraps_every_row_of_its_run,
    test_sibling_lines_wrap_together,
    test_link_lines_wrap_alone,
    test_a_line_in_a_grid_card_votes_in_both_runs,
    test_a_runs_spacers_give_way_together,
    test_the_renderer_obeys_the_runs_spacer_pin,
    test_a_stacked_run_of_spring_rows_shares_its_column_edges,
    test_spring_rows_of_other_regions_keep_their_own_asks,
]


if __name__ == "__main__":
    failed = 0
    for t in TESTS:
        try:
            t()
            print(f"  ok    {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  FAIL  {t.__name__}: {e!r}")
    sys.exit(1 if failed else 0)
