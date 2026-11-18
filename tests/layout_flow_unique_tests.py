"""
Unit tests for ``Stack sections``: UNIQUE sibling groups sit side by side instead of
each spanning the row.

Repeated siblings grid, because equal things deserve equal sizing. A one-off
group owes its neighbours nothing, so it asks for the width it needs and the
next one sits beside it — looser than a grid, and it WRAPS rather than squeezes
when the line runs out.

What a block ASKS for decides two things and only two: which row it lands on, and
its share of that row. The row itself always spans its line — the leftover is
shared out in proportion, so every block grows by the same factor and none is
ever drawn under the width it asked for.

The eligibility rule is group vs leaf, not section vs content: ``_is_group`` is
"content-less with children", so a heading's own title leaf, a horizontal rule
and a content break are excluded by the same one test that lets a `## ` band pack
beside another band. What is excluded beyond that is every child that already
owns an arrangement — a repeated member, an ``orphan_grid`` member, a table, an
authored `:::` or same-line row, and a list item.

**Unique means a different KIND.** The grouper buckets siblings of the same shape
whatever their size, so three text blocks of one, three and five lines are one
kind and grid; these fixtures give each block a different leaf TYPE, which is
what actually makes the kinds differ. ``_blocks`` asserts that, so a fixture can
never quietly test the gridding path instead.

Run with: uv run python tests/layout_flow_unique_tests.py
"""

from layout_bento_tests import _ast, _group, _leaf
from md2ui.pipeline.generator_units import _flow_pair_gap
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.markdown_grouper import NodeType
from md2ui.pipeline.theme import Theme

# One block per entry: the leaf TYPE that makes its kind distinct, and the width
# its measurer reports. A block is a single-leaf group, so the group is exactly
# as wide as its leaf.
BLOCKS = {
    "a": ("text", 100.0),
    "b": ("link", 200.0),
    "c": ("inline_code", 300.0),
    "d": ("emoji", 400.0),
    "wide": ("text", 900.0),
}


def _measure_line(node, _inherited=None):
    entry = BLOCKS.get(node.content)
    return entry[1] if entry else None


def _theme(pack: bool = True) -> Theme:
    t = Theme()
    t.root.pack_unique = pack
    return t


def _block(name: str, **flags):
    """One unique SECTION: a single leaf of the type that gives it its own kind,
    in a heading group.

    A heading group because only sections pack — a deeper element group is an
    arrangement its author already chose. Untitled, because a TITLED section at
    the document's top rank is a chapter and keeps the whole line; these are bare
    `## ` bands, which are what packing is for.
    """
    node_type, _width = BLOCKS[name]
    leaf = _leaf(name, "short")
    leaf["type"] = node_type
    flags.setdefault("heading_group", True)
    return _group(leaf, **flags)


def _blocks(*names: str):
    """A document of unique groups, checked to actually BE unique."""
    doc = _ast(_group(*[_block(n) for n in names]))
    assert not doc.repeated_children, (
        "fixture is not unique — these siblings would grid, not pack"
    )
    return doc


def _rows(doc, width: float, pack: bool = True):
    """``[[cell widths], ...]`` for the top-level children of a generated layout.

    A packed row reports its cells; anything still full-width reports as a row of
    one, so the shape reads the same either way.
    """
    layout = LayoutGenerator().generate(
        doc, width, _theme(pack), measure_line=_measure_line
    )
    top = layout.children[0] if layout.children else layout
    out = []
    for child in top.children:
        if child.type == "row" and not getattr(child, "grid", False):
            out.append([round(r, 1) for r in child.ratios])
        else:
            out.append([round(width)])
    return out


# The gap the renderer puts between two packed blocks, asked of the same function
# the flow asks — a row spans its line when its cells plus these add up to it.
_pair = _blocks("a", "b").children
_GAP = _flow_pair_gap(_pair[0], _pair[1], _theme(True))


def test_unique_groups_share_the_line_in_proportion():
    # 100 + 200 + 300 fits in 1000, so all three share one row — and the row
    # spans the line: what each asked for buys a SHARE of it, not a third of the
    # page apiece and not a 400px hole on the right.
    assert _rows(_blocks("a", "b", "c"), 1000.0) == [[164.0, 328.0, 492.0]]


def test_the_line_wraps_instead_of_squeezing():
    # a+b+c is 600 and fits 700; adding d would need 1000, so d WRAPS. The wrap
    # is decided on what the blocks ASKED for, never on what they are drawn at —
    # nothing is narrowed to make room for d.
    assert _rows(_blocks("a", "b", "c", "d"), 700.0) == [[114.0, 228.0, 342.0], [700]]


def test_narrowing_moves_an_item_down_rather_than_reflowing_the_rest():
    wide = _rows(_blocks("a", "b", "c"), 1000.0)
    narrow = _rows(_blocks("a", "b", "c"), 400.0)
    assert wide == [[164.0, 328.0, 492.0]]
    # At 400 only a+b fit, so c moves down. The two that stayed share a narrower
    # line and so are narrower, but they still divide it 1:2 — narrowing the page
    # changes which line a block is on, never its share of that line.
    assert narrow == [[130.7, 261.3], [400]], narrow
    kept, was = narrow[0][1] / narrow[0][0], wide[0][1] / wide[0][0]
    assert abs(kept - was) < 0.01, f"share changed: 1:{kept:.3f} was 1:{was:.3f}"


def test_the_tail_is_balanced_rather_than_left_alone():
    # Greedy first-fit would put a+b+c on one line and leave d by itself. Two and
    # two reads better, and the widths do not change -- only which row they sit on.
    assert _rows(_blocks("a", "b", "c", "d"), 1000.0) == [
        [330.7, 661.3],
        [425.1, 566.9],
    ]


def test_balancing_never_forces_a_row_that_does_not_fit():
    # At 700 the move would need 300 + 400 + a gap, so the tail stays as it is:
    # balance is a preference, never a reason to overflow.
    assert _rows(_blocks("a", "b", "c", "d"), 700.0) == [[114.0, 228.0, 342.0], [700]]


def test_a_two_then_one_tail_is_already_balanced():
    # One short of the row above is even enough -- the same floor the repeated
    # grids use, where a 2-column run ending in a single cell is allowed.
    assert _rows(_blocks("a", "b", "c"), 420.0) == [[137.3, 274.7], [420]]


def test_an_item_wider_than_the_line_takes_the_row():
    # A piece that cannot share the line renders full-width.
    assert _rows(_blocks("wide", "b"), 500.0) == [[500], [500]]


def test_pack_unique_no_restores_the_stack():
    assert _rows(_blocks("a", "b", "c"), 1000.0, pack=False) == [
        [1000],
        [1000],
        [1000],
    ]


def test_leaves_never_pack():
    # The case the group/leaf rule exists for: a heading's own title is a LEAF,
    # and must not sit beside the body it introduces.
    doc = _ast(_group(_leaf("a", "short"), _block("b"), _block("c")))
    assert _rows(doc, 1000.0)[0] == [1000], "the bare leaf keeps its own row"


def test_an_arrangement_that_owns_itself_stays_full_width():
    """Each of these already decides its own layout, so the flow leaves it alone
    — and being ineligible, it also breaks the run around it."""
    for flag in ("table_group", "column_split_group", "line_split_group"):
        doc = _ast(_group(_block("a"), _block("b", **{flag: True}), _block("c")))
        assert _rows(doc, 1000.0) == [[1000], [1000], [1000]], flag


def test_an_orphan_grid_member_is_left_to_its_grid():
    """``orphan_grid`` is a LIVE flag — the grouper sets it on the node and it is
    not serialized — so this asks the predicate rather than round-tripping a
    fixture dict that would silently drop it."""
    doc = _blocks("a", "b")
    gen = LayoutGenerator()
    gen._theme = _theme(True)
    first = doc.children[0]
    assert gen._packs_unique(first, set())
    first.orphan_grid = True
    assert not gen._packs_unique(first, set()), "an orphan is gridded, not packed"


def test_a_list_is_a_stack():
    """A list's items are a sequence, not a set of independent blocks. Asked of
    the predicate: same-typed list items bucket as ONE kind whatever their
    leaves, so a document of them exercises the gridding path, not this one."""
    doc = _blocks("a", "b")
    gen = LayoutGenerator()
    gen._theme = _theme(True)
    item = doc.children[0]
    assert gen._packs_unique(item, set())
    item.type = NodeType.LIST_ITEM
    assert not gen._packs_unique(item, set())


def test_a_repeated_member_is_gridded_not_packed():
    """The other half of the rule, at the predicate: a child the grouper bucketed
    as repeated belongs to its run."""
    doc = _blocks("a", "b")
    gen = LayoutGenerator()
    gen._theme = _theme(True)
    first = doc.children[0]
    assert gen._packs_unique(first, set())
    assert not gen._packs_unique(first, {id(first)})


def test_no_cell_is_drawn_under_the_width_it_asked_for():
    """The leftover is what is LEFT — ``available`` minus the minimums and the
    gaps between them.

    Sharing out the whole line instead pushes the row's cells past their line,
    and the renderer then normalises every one of them DOWN — including the cells
    already sitting at the width their content was proven at.
    """
    mins = [100.0, 200.0, 300.0]
    for width in (420.0, 700.0, 1000.0, 4000.0):
        drawn = [w for row in _rows(_blocks("a", "b", "c"), width) for w in row]
        for asked, got in zip(mins, drawn):
            assert got >= asked, f"{got} < {asked} asked, at {width}"


def test_a_row_spans_its_line_exactly():
    """Every block grows by the same factor, so the cells and the gaps between
    them add up to the line — no hole on the right, and no overflow to normalise
    away."""
    for width in (420.0, 700.0, 1000.0, 4000.0):
        for row in _rows(_blocks("a", "b", "c", "d"), width):
            if len(row) == 1:
                continue  # a block that could not share its line takes it whole
            spent = sum(row) + _GAP * (len(row) - 1)
            assert abs(spent - width) < 0.5, f"{spent} of {width}: {row}"


TESTS = [
    test_unique_groups_share_the_line_in_proportion,
    test_the_line_wraps_instead_of_squeezing,
    test_narrowing_moves_an_item_down_rather_than_reflowing_the_rest,
    test_no_cell_is_drawn_under_the_width_it_asked_for,
    test_a_row_spans_its_line_exactly,
    test_the_tail_is_balanced_rather_than_left_alone,
    test_balancing_never_forces_a_row_that_does_not_fit,
    test_a_two_then_one_tail_is_already_balanced,
    test_an_item_wider_than_the_line_takes_the_row,
    test_pack_unique_no_restores_the_stack,
    test_leaves_never_pack,
    test_an_arrangement_that_owns_itself_stays_full_width,
    test_an_orphan_grid_member_is_left_to_its_grid,
    test_a_list_is_a_stack,
    test_a_repeated_member_is_gridded_not_packed,
]


if __name__ == "__main__":
    print("Pack-Unique (flowing unique sibling groups) Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓  {test.__name__}")
        except Exception as exc:  # noqa: BLE001 — report and keep going
            failed += 1
            print(f"  ✗  {test.__name__}: {exc}")
    print("=" * 50)
    if failed:
        raise SystemExit(f"{failed} test(s) FAILED.")
    print(f"All {len(TESTS)} tests passed.")
