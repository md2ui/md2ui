"""
The layout half of a ``:::`` column row: ratios, the zero floor, and the col
fallback.

The grouper hands the generator a ``column_row_group`` whose ``column_weights``
are what the author wrote (``tests/column_divider_tests.py`` covers that half).
This module covers what the layout stage does with it, which is three things:

* **the weights become the row's ratios** — and, unusually, they have to BIND.
  ``_layout_row`` ignores ``ratios`` entirely whenever the content fits: it
  collapses every cell to its natural width and packs by ``content_align``. So a
  column row also claims the width it is offered (``natural_width``) and takes
  the ratio path unconditionally, or an authored 1:2:1 would silently render as
  three shrink-wrapped cells packed left;

* **a weight of ``0`` is "no share of the SURPLUS", not "no width"** — the cell
  is reserved its own content width and the rest is split among the weighted
  cells. Three things break without that floor: ``_feasible_ratios``
  is all-or-nothing so one zero discards every authored weight; the ratio branch
  sets the width to 0; and ``draw_image_box`` divides by zero. The subtlety is
  that a zero cell must be MEASURED at an equal share — measured against its own
  zero share it reports zero, which is how a width-capped image gets sized
  against 0px and brings the crash back;

* **a row with no number is a line.** ``A ::: B ::: C`` with no weight written
  anywhere is not proportioned: its cells collapse to their content and flow
  like the pieces of ``A - B - C`` (``_flow_rows``). Only a row with a number
  takes the ratio path, and in it an unnumbered cell is an equal share;

* **nothing is forced, and nothing is all-or-nothing.** When the cells cannot
  clear their minimum widths, the ones that do not fit wrap onto the next line,
  as a piece of a `` - `` line does -- one wide cell does not stack the whole
  row. An author asking for a row is making a request the content may decline,
  one cell at a time.

Run with: uv run python tests/layout_column_row_tests.py
"""

from md2ui.pipeline.generator_column_cuts import row_groups, stack_category
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.layout_generator import LayoutGenerator, _row_weights
from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.markdown_grouper import ASTPatternAnalyzer, MarkdownGrouper
from md2ui.utils.font_loader import make_font


def layout(text: str, width: float = 1000.0, theme=None) -> LayoutNode:
    """The layout tree for *text* at *width*, grouper included."""
    g = MarkdownGrouper(text)
    g.to_ast()
    assert g.ast is not None
    ASTPatternAnalyzer(g.ast).fingerprints(include_unique=True)
    return LayoutGenerator().generate(g.ast, width, theme)


def layout_processed(text: str, width: float = 1000.0, theme=None) -> LayoutNode:
    """Like :func:`layout`, but through the WHOLE grouper.

    Needed for anything about the cell COUNT: the blank-line split runs in
    ``process()``, after the row was minted, and it is what can leave a row
    holding more cells than weights.
    """
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=None)
    assert g.ast is not None
    ASTPatternAnalyzer(g.ast).fingerprints(include_unique=True)
    return LayoutGenerator().generate(g.ast, width, theme)


def walk(node: LayoutNode):
    yield node
    for child in node.children:
        yield from walk(child)


def the_row(node: LayoutNode) -> LayoutNode:
    found = [n for n in walk(node) if getattr(n, "column_row", False)]
    assert len(found) == 1, f"expected one column row, got {len(found)}"
    return found[0]


def rows(node: LayoutNode) -> list[LayoutNode]:
    return [n for n in walk(node) if getattr(n, "column_row", False)]


def body(node: LayoutNode) -> LayoutNode:
    """The one real child under the ``layout`` root."""
    return node.children[0]


# ---------------------------------------------------------------------------
# 1 — the weights become the ratios
# ---------------------------------------------------------------------------


def test_a_row_is_built_with_the_authored_weights():
    row = the_row(layout("A\n:::2\nB\n"))
    assert row.type == "row"
    assert row.ratios == [2, 1.0], row.ratios
    assert len(row.children) == 2


def test_equal_weights_for_unnumbered_cells_beside_a_number():
    row = the_row(layout("A\n:::2\nB\n:::\nC\n"))
    assert row.ratios == [2, 1.0, 1.0]


def test_a_row_with_no_number_is_a_line():
    # Collapsed and flowed like `A - B - C`: a plain line row, not proportions,
    # and like that line it is not a row of blocks toward its neighbours.
    lay = layout("A\n:::\nB\n:::\nC\n")
    assert not rows(lay), "no number: nothing to proportion"
    row = body(lay)
    assert row.type == "row" and len(row.children) == 3, row
    assert row.line_split and not row.block_line


# A row fenced off from the paragraph above it, so the gap between the two is
# the row's own toward a neighbour. Leaf cells, then cells that are blocks.
_LEAF_ROW = "Intro words here\n\n___\nAlpha\n:::\nBravo\n___\n"
_BLOCK_ROW = (
    "Intro words here\n\n___\n- Alpha\n- Alpha two\n:::\n- Bravo\n- Bravo two\n___\n"
)


def _spaced(src: str):
    """(grouper row, its laid-out row, gap from the intro to it, theme) through
    the real pipeline with the fixture theme."""
    from pathlib import Path

    from md2ui import session

    theme = session.load_theme(Path("data/markdown/tests/THEME.md"))
    fonts = session.load_fonts(theme)
    ast = session.group_markdown(src, session.load_grouping_kit())
    assert ast is not None
    root, idx = session.prepare(ast, theme)
    scene = session.build_scene(LayoutGenerator(), root, idx, theme, fonts, 900)

    def grouped(n):
        yield n
        for c in n.children:
            yield from grouped(c)

    row = next(n for n in grouped(root) if n.column_row_group)
    laid = next(n for n in walk(scene.layout) if n.line_split and n.children)
    text = {
        b.content_id: (idx.get(b.content_id) or {}).get("content") for b in scene.boxes
    }
    intro = next(b for b in scene.boxes if text[b.content_id] == "Intro words here")
    first = next(b for b in scene.boxes if text[b.content_id] == "Alpha")
    return row, laid, first.y - (intro.y + intro.height), theme


def test_a_row_spaces_toward_its_neighbours_by_what_its_cells_hold():
    # As a line does: leaf cells take the line gap, cells that are all blocks
    # the group gap -- in the renderer (block_line) and in the generator's own
    # estimate of the same gap (_cell_gap), which must agree (ADR-400).
    from md2ui.pipeline.generator_units import _cell_gap, _group_spacing

    row, laid, gap, theme = _spaced(_LEAF_ROW)
    element = theme.elements.col_spacing or 0.0
    assert not laid.block_line
    assert gap == element, (gap, element)
    assert _cell_gap(row, theme, "col") == element
    assert _cell_gap(row, theme, "row") == theme.elements.row_spacing

    row, laid, gap, theme = _spaced(_BLOCK_ROW)
    group = _group_spacing(False, theme)
    assert group > element, "the fixture theme must tell the two gaps apart"
    assert laid.block_line
    assert gap >= group, (gap, group)
    assert _cell_gap(row, theme, "col") == group
    assert _cell_gap(row, theme, "row") == _group_spacing(True, theme)


def test_a_decimal_weight_reaches_the_ratios():
    assert the_row(layout("A\n:::0.5\nB\n")).ratios == [0.5, 1.0]


def test_the_row_is_flagged_so_the_renderer_can_tell():
    # `column_row` is what makes `natural_width` claim the offered width and
    # `_layout_row` take the ratio path. Without the flag the ratios are inert.
    row = the_row(layout("A\n:::2\nB\n"))
    assert row.column_row is True


def test_the_flag_is_not_serialized():
    # Runtime-only, like `grid` / `bento` / `spring`: the layout signature and
    # the eval must not move because a row was authored rather than decided.
    row = the_row(layout("A\n:::2\nB\n"))
    assert "column_row" not in row.to_dict()


# ---------------------------------------------------------------------------
# 2 — nothing is forced: the row declines when it cannot fit
# ---------------------------------------------------------------------------


def test_a_row_that_cannot_fit_wraps():
    # Each cell's `_min_width` plus the gaps against the width on offer, cell by
    # cell: a cell that does not fit starts the next line. At 40px no two fit, so
    # every cell is a line of its own.
    doc = "A\n:::1\nB\n:::1\nC\n"
    assert rows(layout(doc, width=1000.0)), "should be a row at 1000px"
    narrow = layout(doc, width=40.0)
    assert not rows(narrow), "no two cells fit at 40px"
    assert body(narrow).type == "col"
    assert len(body(narrow).children) == 3


def test_only_the_cell_that_does_not_fit_wraps():
    # The cells that fit stay a row and the rest start the next line: the
    # paragraph needs 320px
    # beside two 80px cells, which 400px cannot give.
    doc = "A\n:::1\nB\n:::1\n" + "word " * 40 + "\n"
    lay = body(layout(doc, width=400.0))
    assert lay.type == "col", lay.type
    first = lay.children[0]
    assert getattr(first, "column_row", False) and len(first.children) == 2, first


def test_the_col_fallback_keeps_every_cell():
    # Declining the arrangement must not lose content.
    narrow = body(layout("A\n:::\nB\n:::\nC\n", width=40.0))
    assert narrow.type == "col"
    assert len(narrow.children) == 3


def test_the_same_document_is_a_row_or_a_col_by_width_alone():
    doc = "A\n:::1\nB\n:::1\nC\n"
    flips = [bool(rows(layout(doc, width=w))) for w in (40.0, 1000.0)]
    assert flips == [False, True], flips


# ---------------------------------------------------------------------------
# 3 — the zero floor
# ---------------------------------------------------------------------------


def test_a_zero_weight_survives_into_the_ratios():
    # It must reach the renderer as a real 0 — that is the signal to reserve the
    # cell its content width rather than a share.
    assert the_row(layout("A\n:::0\nB\n")).ratios == [0, 1.0]


def test_a_zero_cell_is_still_given_width_by_the_generator():
    # `_column_row_widths` reserves a zero cell its own minimum first. A zero
    # here would mean the cell's subtree was decided against no width at all.
    gen = LayoutGenerator()
    g = MarkdownGrouper("Status\n:::0\nA much longer body of text here.\n")
    g.to_ast()
    assert g.ast is not None
    ASTPatternAnalyzer(g.ast).fingerprints(include_unique=True)
    gen.generate(g.ast, 900.0, None)
    node = next(n for n in _walk_md(g.ast) if n.column_row_group)
    weights = _row_weights(node, len(node.children))
    assert weights is not None
    widths = gen._column_row_widths(node.children, weights, 900.0, 0)
    assert widths[0] > 0.0, widths
    assert widths[1] > widths[0], widths


def test_a_zero_cell_leaves_the_rest_of_the_width_to_its_neighbours():
    gen = LayoutGenerator()
    g = MarkdownGrouper("Status\n:::0\nBody\n")
    g.to_ast()
    assert g.ast is not None
    ASTPatternAnalyzer(g.ast).fingerprints(include_unique=True)
    gen.generate(g.ast, 900.0, None)
    node = next(n for n in _walk_md(g.ast) if n.column_row_group)
    weights = _row_weights(node, len(node.children))
    assert weights is not None
    widths = gen._column_row_widths(node.children, weights, 900.0, 0)
    # The weighted cell takes everything the zero cell did not reserve.
    assert abs(sum(widths) - 900.0) < 1.0, widths


def _walk_md(node: MarkdownGroupNode):
    yield node
    for child in node.children:
        yield from _walk_md(child)


# ---------------------------------------------------------------------------
# 4 — an authored row outranks every decision source
# ---------------------------------------------------------------------------


def test_an_image_first_cell_is_not_turned_into_an_aside():
    # The aside gate fires on "a group carrying an image as its first or last
    # child". A `:::` row is exactly that shape, and it is the special case this
    # syntax replaces — so the row must be decided before the gate is reached.
    row = the_row(layout("![I](x.png)\n:::2\nA\nB\n"))
    assert row.type == "row"
    assert row.ratios == [2, 1.0]


def test_a_row_nested_in_a_card_is_still_a_row():
    for divider in (":::1", ":::"):
        lay = layout(f"## Card\nA\n{divider}\nB\n")
        row = next(n for n in walk(lay) if n.type == "row" and len(n.children) == 2)
        assert bool(getattr(row, "column_row", False)) == (divider == ":::1")


def test_the_weights_are_padded_never_dropped():
    """One weight per cell, always — short pads, long trims."""
    row = MarkdownGroupNode(type="group")
    row.column_row_group = True
    row.column_weights = (0, 2.0)
    assert _row_weights(row, 4) == [0, 2.0, 1.0, 1.0], "short: pad"
    assert _row_weights(row, 2) == [0, 2.0], "exact: unchanged"
    assert _row_weights(row, 1) == [0], "long: trim"

    unnumbered = MarkdownGroupNode(type="group")
    unnumbered.column_weights = (None, 2.0)
    assert _row_weights(unnumbered, 3) == [1.0, 2.0, 1.0], "unwritten: equal share"

    bare = MarkdownGroupNode(type="group")
    assert _row_weights(bare, 3) is None, "no number anywhere: not proportions"
    bare.column_weights = (None, None)
    assert _row_weights(bare, 3) is None


def test_a_blank_line_inside_a_side_adds_no_cell():
    """``build_column_rows`` runs before the blank-line split, so the middle side
    of this row is a single blob holding two blank-line separated groups. A row
    has one column per side: the blob keeps its side rather than being cut
    into extra cells, and every cell reaches the layout with a ratio.
    """
    md = (
        "## Cards\n\n⭐\n:::0\n**Fast delivery**\nIn under 30 minutes.\n\n"
        "⭐\n:::0\n**Free returns**\nWithin 30 days.\n"
    )
    row = the_row(layout_processed(md, 900.0))
    assert len(row.children) == 3, f"one cell per side: {len(row.children)} of 3"
    assert len(row.ratios) == len(row.children), (
        f"ratios={row.ratios} against {len(row.children)} cells"
    )
    last = [n for n in walk(row.children[-1]) if not n.children]
    assert len(last) == 2, f"a cell was dropped: {len(last)} leaves in the last"


def test_a_list_of_row_items_grids_like_any_group():
    # Each item's indented `:::` makes that item a row, and a run of same-shaped
    # rows grids whether or not each one carries a list marker. `___` between
    # the items is how an author keeps them stacked.
    lay = layout_processed("- A\n  :::0\n  **One**\n- B\n  :::0\n  **Two**\n")
    assert len(rows(lay)) == 2, [n.type for n in walk(lay)]
    assert any(getattr(n, "grid", False) for n in walk(lay))


# ---------------------------------------------------------------------------
# 5 — narrow and wide: the space the row is offered decides
# ---------------------------------------------------------------------------


def test_a_second_number_is_the_weight_in_wide_space():
    doc = "A\n::: 1 1.5\nB\n"
    assert the_row(layout(doc, width=600.0)).ratios == [1, 1.0]
    assert the_row(layout(doc, width=1000.0)).ratios == [1.5, 1.0]


def test_a_wide_only_cut_stacks_in_narrow_space():
    doc = "A\n::: 1 >\nB\n"
    assert rows(layout(doc, width=1000.0)), "a row in wide space"
    narrow = layout(doc, width=600.0)
    assert not rows(narrow), "no cut in narrow space"
    assert body(narrow).type == "col" and len(body(narrow).children) == 2


def test_a_narrow_only_cut_stacks_in_wide_space():
    doc = "A\n::: 1 <\nB\n"
    assert rows(layout(doc, width=600.0)), "a row in narrow space"
    assert not rows(layout(doc, width=1000.0)), "no cut in wide space"


def test_the_cells_either_side_of_an_idle_cut_stand_as_one():
    # Only the cut that does not apply goes: A and B stack as one cell, and the
    # row keeps its other cut. The merged cell takes the weight of the divider
    # that closes it (B's `:::2`).
    doc = "A\n::: 1 >\nB\n:::2\nC\n"
    row = the_row(layout(doc, width=600.0))
    assert len(row.children) == 2, row
    assert row.ratios == [2, 1.0], row.ratios
    stacked = row.children[0]
    assert stacked.type == "col" and len(stacked.children) == 2, stacked
    assert len(the_row(layout(doc, width=1000.0)).children) == 3


def test_the_natural_wrap_still_wins_in_wide_space():
    # A condition only turns a cut off; it never forces a row the cells cannot
    # fill — measured on the width the row is offered.
    doc = "A\n::: 1 1.5\nB\n:::1 >\nC\n"
    assert not rows(layout(doc, width=40.0))


def test_row_groups_reads_each_cut_at_one_width():
    row = MarkdownGroupNode(type=NodeType.GROUP)
    row.column_weights = (1, 2, None)
    row.column_weights_wide = (1.5, None, None)
    row.column_cuts = ("wide", None, None)
    assert row_groups(row, 3, 600.0) == ([[0, 1], [2]], [2, None])
    assert row_groups(row, 3, 1000.0) == ([[0], [1], [2]], [1.5, 2, None])


def test_a_stack_is_as_wide_as_its_widest_member():
    def leaf(kind, category=None):
        n = MarkdownGroupNode(type=kind)
        n.content_length_category = category
        return n

    assert (
        stack_category([leaf(NodeType.TEXT, "one_word"), leaf(NodeType.TEXT, "short")])
        == "short"
    )
    assert (
        stack_category([leaf(NodeType.IMAGE), leaf(NodeType.TEXT, "one_word")])
        == "very_short"
    )
    assert stack_category([leaf(NodeType.TEXT, None)]) is None


# ---------------------------------------------------------------------------
# 4 — a weighted row breaks its lines on what the cells hold
# ---------------------------------------------------------------------------
# The length-category minimums (80px for a word) are for repeated-card grids.
# A `:::` cell asks for its real content, and prose for at most its wrapping
# floor, so the weights only share out a line whose cells are already decided.
# These run through the real pipeline: without fonts both asks are the same
# category number and nothing here would be tested.

_KIT: list = []
_PHOTO = "https://example.com/photo.jpg"
_TABS = (
    "___\n"
    + "".join(
        f"🔷\n{name}\n:::1\n"
        for name in ("Ruby", "Python", "PHP", "Java", "Node.js", "Go", ".NET")
    )
    + "___\n"
)


def placed(text: str, width: float):
    """The scene for *text* at *width*, with the fixture theme and its fonts --
    the layout and the boxes the renderer places from it -- and the node index
    the boxes are read against."""
    from pathlib import Path

    from md2ui import session

    if not _KIT:
        theme = session.load_theme(Path("data/markdown/tests/THEME.md"))
        _KIT.extend([session.load_grouping_kit(), theme, session.load_fonts(theme)])
    kit, theme, fonts = _KIT
    grouped = session.group_markdown(text, kit)
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, width)
    return scene, index


def measured(text: str, width: float) -> LayoutNode:
    """The layout for *text* at *width*, with the fixture theme and its fonts."""
    return placed(text, width)[0].layout


def test_short_weighted_cells_fit_on_their_content():
    # Stripe A6: seven icon-over-label tabs that fit packed must fit weighted
    # too. This theme draws each icon as an 83px badge: the cells need about
    # 694px on their content, where an 80px word floor each asked about 892.
    found = rows(measured(_TABS, 720.0))
    assert len(found) == 1 and len(found[0].children) == 7, [
        len(r.children) for r in found
    ]
    print("  ✓  seven short weighted cells share one line at 720px")


def test_weighted_cells_that_do_not_fit_still_wrap():
    found = rows(measured(_TABS, 200.0))
    assert found and all(len(r.children) < 7 for r in found), [
        len(r.children) for r in found
    ]
    print("  ✓  weighted cells that do not fit still start the next line")


def test_prose_beside_a_picture_still_shares_the_line():
    # images.md's picture-beside-text: the copy is far wider than the row on
    # one line, and still sits beside the picture, wrapping inside its cell.
    doc = (
        f"![]({_PHOTO}?md2ui.min_width=200&md2ui.aspect_ratio=1:1)\n"
        "::: 1 >\n## Everything you crave, delivered.\n"
        "Our couriers bring the dishes you love from the restaurants around you,"
        " hot and on time, with live tracking from the kitchen to your door and"
        " no minimum order on most places.\n[Find restaurants](/x)\n:::2\n___\n"
    )
    row = the_row(measured(doc, 1280.0))
    assert len(row.children) == 2, len(row.children)
    print("  ✓  prose beside a picture still shares the line")


def test_an_image_floor_still_stacks_a_weighted_row():
    # images.md: below its min_width the picture cannot stay beside the text.
    # 480px of picture, the text's floor and the gap need about 598px.
    doc = (
        f"![Photo]({_PHOTO}?md2ui.min_width=480&md2ui.aspect_ratio=1:1)\n"
        "::: 1\nText beside a picture.\n:::5\n"
    )
    assert rows(measured(doc, 1024.0)), "the floor fits beside the text"
    assert not rows(measured(doc, 560.0)), "480px beside the text cannot fit"
    print("  ✓  an image floor still stacks a weighted row")


def test_a_wide_only_cut_still_stacks_when_measured():
    doc = "Alpha\n::: 1 >\nBeta\n"
    assert rows(measured(doc, 1000.0)), "a row in wide space"
    assert not rows(measured(doc, 600.0)), "no cut in narrow space"
    print("  ✓  `::: 1 >` still stacks in narrow space")


_PILLS = (
    "[`Docs`](/docs)\n:::1\n"
    "[`Presentation maker for distributed product teams`](/presentation-maker)"
    "\n:::{}\n[`Colour wheel`](/colours)\n:::{}\n"
)


def test_a_weighted_line_is_fitted_at_its_weights():
    # The three pills sum to about 600px, which fits 767; three EQUAL shares
    # of it do not hold the long one, which would draw over its neighbour.
    # Weighted to their content, the same cells keep one line.
    equal = [len(r.children) for r in rows(measured(_PILLS.format(1, 1), 767.0))]
    assert equal and max(equal) < 3, equal
    fitted = [len(r.children) for r in rows(measured(_PILLS.format(4, 2), 767.0))]
    assert fitted == [3], fitted
    print("  ✓  a weighted line keeps a cell only where its share holds it")


def test_a_rule_does_not_size_a_fit_cell():
    # A `---` fills whatever width its cell is given, so the rest of a `:::0`
    # cell sizes it. Measured as wide as the line, it took the whole row and
    # left the weighted picture 0 x 0.
    doc = (
        f"![A]({_PHOTO}?md2ui.max_width=104&md2ui.aspect_ratio=1:1)\n"
        ":::1\n**3591**\n_Reviews_\n---\n**4.82★**\n_Rating_\n:::0\n"
    )
    boxes = placed(doc, 800.0)[0].boxes
    picture = next(b for b in boxes if (b.render_properties or {}).get("max_width"))
    assert picture.width > 0 and picture.height > 0, picture
    widest = max(b.width for b in boxes)
    assert widest < 800.0 - 104.0, f"a cell still claims the line: {widest}"
    print("  ✓  a rule in a `:::0` cell leaves its neighbour the row")


def test_a_zero_sized_picture_draws_nothing():
    # One 0 x 0 picture used to divide by its zero scale and stop the render.
    import skia

    from md2ui.pipeline.layout_render import draw_image_box
    from md2ui.pipeline.layout_script_parser import LayoutBox

    src = skia.Surface(100, 50)
    surface = skia.Surface(40, 40)
    surface.getCanvas().clear(skia.ColorWHITE)
    draw_image_box(
        surface.getCanvas(),
        LayoutBox(x=10, y=10, width=0, height=0),
        "![](x.jpg)",
        make_font(skia.Typeface(""), 12),
        src.makeImageSnapshot(),
    )
    pixels = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    assert (pixels == 255).all(), "a zero-sized picture painted something"
    print("  ✓  a zero-sized picture draws nothing")


def test_a_picture_gives_way_before_a_button():
    # A button's label never wraps, so its box must hold its pill. The fit
    # test holds a `:::0` picture at its floor; the renderer kept it at its cap
    # and gave the weighted cell less than its button, whose pill then ran
    # under the next cell. Pictures flex first; the row wraps below their floor.
    from md2ui.pipeline.render_measure import _leaf_natural_width

    doc = (
        f"![A]({_PHOTO}?md2ui.max_width=180&md2ui.aspect_ratio=172:186)\n:::0\n"
        "___Good Morning, Mia!___\n_Let's enjoy some music today!_\n"
        "[▶️ Play Something](/play)\n:::1\n"
        f"![B]({_PHOTO}?md2ui.max_width=96&md2ui.aspect_ratio=96:144)\n:::0\n"
    )
    short = []
    for width in range(340, 640, 20):
        scene, index = placed(doc, float(width))
        for box in scene.boxes:
            nd = index.get(box.content_id)
            if nd and nd.get("type") == "link":
                pill = _leaf_natural_width(
                    nd, 1e6, _KIT[2], _KIT[1], box.render_properties
                )
                if pill > box.width + 0.5:
                    short.append((width, round(pill - box.width, 1)))
    assert not short, f"the button's box is short of its pill at {short}"
    print("  ✓  a `:::0` picture gives way before a button is squeezed")


def test_a_code_block_takes_no_room_from_a_picture():
    # A code block never wraps at words: a line wider than its box clips and
    # scrolls. It is not an element the give-way keeps whole, so a `:::0`
    # picture beside it keeps the width it has beside a short one (at 767 its
    # 60-character word took the picture from 384 to 269 px).
    def picture_width(code: str) -> float:
        doc = (
            f"![A]({_PHOTO}?md2ui.max_width=400&md2ui.aspect_ratio=4:3)\n:::0\n"
            f"```console\n$ {code}\n```\n:::1\n"
        )
        boxes = placed(doc, 767.0)[0].boxes
        return next(
            b.width for b in boxes if (b.render_properties or {}).get("max_width")
        )

    short, long = picture_width("ls"), picture_width("x" * 60)
    assert long == short, (short, long)
    print("  ✓  a code block takes no room from a picture beside it")


TESTS = [
    test_a_code_block_takes_no_room_from_a_picture,
    test_a_picture_gives_way_before_a_button,
    test_a_rule_does_not_size_a_fit_cell,
    test_a_zero_sized_picture_draws_nothing,
    test_a_weighted_line_is_fitted_at_its_weights,
    test_short_weighted_cells_fit_on_their_content,
    test_weighted_cells_that_do_not_fit_still_wrap,
    test_prose_beside_a_picture_still_shares_the_line,
    test_an_image_floor_still_stacks_a_weighted_row,
    test_a_wide_only_cut_still_stacks_when_measured,
    test_the_weights_are_padded_never_dropped,
    test_a_blank_line_inside_a_side_adds_no_cell,
    test_a_row_is_built_with_the_authored_weights,
    test_equal_weights_for_unnumbered_cells_beside_a_number,
    test_a_row_with_no_number_is_a_line,
    test_a_row_spaces_toward_its_neighbours_by_what_its_cells_hold,
    test_a_decimal_weight_reaches_the_ratios,
    test_the_row_is_flagged_so_the_renderer_can_tell,
    test_the_flag_is_not_serialized,
    test_a_row_that_cannot_fit_wraps,
    test_only_the_cell_that_does_not_fit_wraps,
    test_the_col_fallback_keeps_every_cell,
    test_the_same_document_is_a_row_or_a_col_by_width_alone,
    test_a_zero_weight_survives_into_the_ratios,
    test_a_zero_cell_is_still_given_width_by_the_generator,
    test_a_zero_cell_leaves_the_rest_of_the_width_to_its_neighbours,
    test_an_image_first_cell_is_not_turned_into_an_aside,
    test_a_row_nested_in_a_card_is_still_a_row,
    test_a_list_of_row_items_grids_like_any_group,
    test_a_second_number_is_the_weight_in_wide_space,
    test_a_wide_only_cut_stacks_in_narrow_space,
    test_a_narrow_only_cut_stacks_in_wide_space,
    test_the_cells_either_side_of_an_idle_cut_stand_as_one,
    test_the_natural_wrap_still_wins_in_wide_space,
    test_row_groups_reads_each_cut_at_one_width,
    test_a_stack_is_as_wide_as_its_widest_member,
]

if __name__ == "__main__":
    print("Layout Column Row Tests")
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
