"""
Unit tests for the ``:::`` COLUMN DIVIDER and the rows it mints.

Markdown gives the grouper three thematic-break spellings and this project gives
each one a job: ``---`` paints a rule, ``___`` cuts invisibly, ``***`` closes the
heading section holding it. ``:::`` is the fourth, and md2ui's own: it cuts like
``___`` and paints nothing, but the runs either side of it become CELLS OF ONE
ROW rather than a stack. It is the block-level twin of the same-line ` : ` column
split — one colon cuts a line into stacked columns, three cut a block into
side-by-side cells — and it carries an optional weight (``:::2``) that
proportions the cell ABOVE it.

Why ``:::`` and not ``:---``: every dash-bearing candidate is a legal GFM table
delimiter row and is already read as one (``table_align``). ``:::`` has no
CommonMark meaning at all, which is what made it free to take.

Two halves, and the tests follow that split:

* the TOKEN (``grouper_block_splits``) — what is a divider, and what weight does
  it carry. Being a member of ``_BREAK_TYPES`` is most of the feature: it buys
  heading-detection suppression on the line, a terminated glued run, a bounded
  heading peel, and the "never re-parse a break leaf" guards, none of which is
  new code. Those four inherited consequences are pinned here because they are
  inherited rather than written;
* the ROW (``grouper_column_rows``) — the cells, their weights, and the one rule
  that makes cells possible at all: a ``:::`` closes a heading section opened
  INSIDE the row, never the section containing it.

Like ``***``, no ``COLUMN_DIVIDER`` survives Phase 1 — ``build_column_rows``
consumes every one of them, so nothing downstream ever sees the type.

Most tests here use :func:`ast`, which stops after Phase 1. That is the right
scope for "was the row minted", and the wrong one for "does the row still exist
at the end": Phase 6's ``_collapse_groups`` lifts a sole-child row's cells into
the parent and must carry ``column_row_group`` and ``column_weights`` with them.
The tests that pin that use :func:`processed`, the whole pipeline.

Run with: uv run python tests/column_divider_tests.py
"""

from md2ui.pipeline.grouper_block_splits import (
    _break_node_type,
    _column_divider_weight,
    divider_fell_back,
)
from md2ui.pipeline.grouper_column_rows import build_column_rows
from md2ui.pipeline.markdown_grouper import (
    MarkdownGrouper,
    MarkdownGroupNode,
    NodeType,
)


def ast(text: str) -> MarkdownGroupNode:
    """The heading-level AST, without the rest of the pipeline."""
    g = MarkdownGrouper(text)
    g.to_ast()
    assert g.ast is not None
    return g.ast


def processed(text: str) -> MarkdownGroupNode:
    """The WHOLE pipeline, so Phase 6's collapse has run over the row."""
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=None)
    assert g.ast is not None
    return g.ast


def walk(node: MarkdownGroupNode):
    yield node
    for child in node.children:
        yield from walk(child)


def rows(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    return [n for n in walk(node) if n.column_row_group]


def the_row(node: MarkdownGroupNode) -> MarkdownGroupNode:
    found = rows(node)
    assert len(found) == 1, f"expected one row, got {len(found)}"
    return found[0]


def texts(node: MarkdownGroupNode) -> list[str]:
    """Every non-empty content string under *node*, in document order."""
    return [n.content for n in walk(node) if n.content]


def shape(node: MarkdownGroupNode) -> list:
    """``[(type, content)]`` for one node's children, for readable failures."""
    return [(c.type, c.content) for c in node.children]


# ---------------------------------------------------------------------------
# 1 — the spelling
# ---------------------------------------------------------------------------


def test_three_or_more_colons_is_a_divider():
    for line in (":::", "::::", ":::::"):
        assert _break_node_type(line) == NodeType.COLUMN_DIVIDER, line


def test_interior_spaces_are_allowed_like_a_dash_rule():
    # CommonMark treats `- - -` as `---`; the divider is spelled the same way,
    # so an author who spaces one out does not silently get a paragraph.
    assert _break_node_type(": : :") == NodeType.COLUMN_DIVIDER
    assert _break_node_type(":  :  :  :") == NodeType.COLUMN_DIVIDER


def test_indentation_does_not_disarm_a_divider():
    # Matches the other three: CommonMark treats up to three spaces as
    # insignificant, and four or more is a code block already consumed by
    # preprocess.
    assert _break_node_type("   :::") == NodeType.COLUMN_DIVIDER
    assert _break_node_type("\t:::") == NodeType.COLUMN_DIVIDER


def test_two_colons_is_not_a_divider():
    assert _break_node_type("::") is None
    assert _break_node_type(": :") is None


def test_a_divider_must_be_the_whole_line():
    for line in ("a:::", "::: b", ":::x", "see ::: here", "Key: value"):
        assert _break_node_type(line) is None, line


def test_the_four_spellings_do_four_different_things():
    assert _break_node_type("---") == NodeType.HORIZONTAL_RULE
    assert _break_node_type("___") == NodeType.CONTENT_BREAK
    assert _break_node_type("***") == NodeType.SECTION_STOP
    assert _break_node_type(":::") == NodeType.COLUMN_DIVIDER


def test_a_divider_behind_a_list_marker_is_a_list_item():
    # `- ---` collapses to a painted rule because CommonMark's "uniform run"
    # rule outranks a bullet. `- :::` is NOT a uniform run of the marker's own
    # character, so it stays what it looks like: an item holding some text.
    for line in ("- :::", "* :::", "1. :::"):
        assert _break_node_type(line) is None, line


# ---------------------------------------------------------------------------
# 2 — the weight, on the token
# ---------------------------------------------------------------------------


def test_a_bare_divider_carries_no_weight():
    assert _column_divider_weight(":::") is None
    assert _column_divider_weight(": : :") is None


def test_a_trailing_number_is_the_weight():
    assert _column_divider_weight(":::2") == 2
    assert _column_divider_weight(":::10") == 10
    assert _column_divider_weight("::: 3") == 3


def test_zero_is_a_real_weight():
    # `0` means "no share of the SURPLUS", not "no cell". The generator floors
    # a zero cell at its own minimum width, which is how an author writes a
    # shrink-to-fit cell beside a flexible one.
    assert _break_node_type(":::0") == NodeType.COLUMN_DIVIDER
    assert _column_divider_weight(":::0") == 0


def test_a_weight_may_be_a_decimal():
    # Ratios are floats the whole way down (``LayoutNode.ratios``), so a
    # fractional weight costs nothing and saves rescaling every other cell to
    # keep the numbers whole.
    assert _column_divider_weight(":::0.5") == 0.5
    assert _column_divider_weight(":::1.5") == 1.5
    assert _break_node_type(":::0.5") == NodeType.COLUMN_DIVIDER


def test_a_decimal_needs_a_leading_digit():
    # `0.5`, never `.5` — so the trailing token is always unmistakably a
    # number. `:::.5` is still plainly a divider, so it falls back to a bare one.
    for line in (":::.5", ":::1."):
        assert _break_node_type(line) == NodeType.COLUMN_DIVIDER, line
        assert _column_divider_weight(line) is None, line


def test_a_non_numeric_suffix_is_not_a_divider():
    for line in (":::x", ":::2px", ":::-2", ":::1,5"):
        assert _break_node_type(line) is None, line


# ---------------------------------------------------------------------------
# 3 — the row: cells and weights
# ---------------------------------------------------------------------------


def test_a_divider_makes_a_row_of_its_two_sides():
    root = ast("A\n:::\nB\n")
    row = the_row(root)
    assert [c.content for c in row.children] == ["A", "B"], shape(row)


def test_no_divider_node_survives():
    # Exactly like `***`: a Phase 1 instruction, consumed before the tree is
    # finished, so nothing downstream ever sees the type.
    root = ast("A\n:::2\nB\n:::\nC\n")
    assert [n for n in walk(root) if n.type == NodeType.COLUMN_DIVIDER] == []


def test_an_unnumbered_row_records_no_weight():
    # `None` is "no number written", which the generator reads as a row that
    # collapses and wraps like a ` - ` line -- not as three equal shares.
    root = ast("A\n:::\nB\n:::\nC\n")
    assert the_row(root).column_weights == (None, None, None)


def test_a_divider_weights_the_cell_ABOVE_it():
    root = ast("A\n:::2\nB\n")
    row = the_row(root)
    assert row.column_weights == (2, None), row.column_weights
    assert [c.content for c in row.children] == ["A", "B"]


def test_a_trailing_divider_weights_the_last_cell():
    # The last cell is the only one with no divider under it, which is why its
    # divider is optional and why writing one is how you weight it.
    root = ast("A\n:::1\nB\n:::2\n")
    row = the_row(root)
    assert row.column_weights == (1, 2)
    assert [c.content for c in row.children] == ["A", "B"]


def test_an_unweighted_cell_records_no_weight():
    # In a row with a number it is an equal share, 1 -- the generator's reading
    # (`_row_weights`); the grouper only records that none was written.
    root = ast("A\n:::3\nB\n")
    assert the_row(root).column_weights == (3, None)


def test_a_decimal_weight_reaches_the_row():
    root = ast("A\n:::0.5\nB\n")
    assert the_row(root).column_weights == (0.5, None)


def test_a_zero_weight_reaches_the_row():
    root = ast("A\n:::0\nB\n")
    assert the_row(root).column_weights == (0, None)


def test_a_cell_may_hold_several_blocks():
    # `:::` partitions the whole sibling run, as `---` and `___` do — so a cell
    # is everything between two cutters, blank lines included.
    root = ast("A\n:::\nB\n\nC\n")
    row = the_row(root)
    assert len(row.children) == 2, shape(row)
    assert texts(row.children[1]) == ["B\n\nC"]


def test_a_divider_that_partitions_nothing_mints_no_row():
    # A lone `:::` at the end of a section cut nothing apart. The divider still
    # disappears; the content is spliced straight back.
    root = ast("A\n:::\n")
    assert rows(root) == []
    assert [c.content for c in root.children] == ["A"]


def test_a_divider_with_no_content_at_all_leaves_nothing():
    root = ast(":::\n")
    assert rows(root) == []
    assert root.children == []


def test_the_pass_is_idempotent():
    # It consumes every divider, so a second run has nothing left to find. Worth
    # pinning because `to_ast` is called on card FRAGMENTS as well as the whole
    # document, and a fragment can be walked more than once.
    root = ast("A\n:::2\nB\n")
    before = root.to_dict()
    build_column_rows(root)
    assert root.to_dict() == before


def test_the_last_cell_without_a_divider_records_no_weight():
    # The last cell is the only one that can lack a divider, so this is what
    # "the trailing divider is optional" actually resolves to.
    root = ast("A\n:::\nB\n")
    assert the_row(root).column_weights[-1] is None


def test_the_row_survives_the_json_round_trip():
    # grouping-ast.json is the generator's input, so a flag that does not
    # round-trip is a flag the generator never sees.
    root = ast("A\n:::0.5\nB\n:::2\n")
    back = MarkdownGroupNode.from_dict(root.to_dict())
    row = the_row(back)
    assert row.column_weights == (0.5, 2)
    assert [c.content for c in row.children] == ["A", "B"]


# ---------------------------------------------------------------------------
# 4 — the row is a plain wrapper, not a card
# ---------------------------------------------------------------------------


def test_the_row_node_is_never_glued():
    # A `:::` is not a glue decision. Gluing the wrapper would paint a card
    # around the whole row that the author never wrote.
    root = ast("A\nB\n:::\nC\n")
    assert the_row(root).glued_content_group is False


def test_glue_never_spans_a_divider():
    # Cells have to be separate, so the glued-segment run ends at the cut —
    # which `hr_lines` already does for every break spelling.
    root = ast("A\nB\n:::\nC\nD\n")
    row = the_row(root)
    left, right = row.children
    ids = {n.glued_content_id for n in walk(left)} - {None}
    other = {n.glued_content_id for n in walk(right)} - {None}
    assert ids and other and not (ids & other), (ids, other)


def test_glue_inside_a_cell_is_untouched():
    # The divider neither creates nor destroys glue: two consecutive lines in a
    # cell are still one segment, exactly as they would be with no row at all.
    root = ast("A\n:::\nB\nC\n")
    right = the_row(root).children[1]
    assert right.glued_content_id is not None
    assert right.content == "B\nC"


def test_a_heading_travels_into_cell_one_with_its_body():
    # A heading and the body under it are one segment, and the whole segment is
    # cell 1. Holding the heading OUT would leave
    # `## Title / ::: / Text` with a single cell and so no row at all.
    root = ast("## Card\nIntro\nA\n:::\nB\n")
    row = the_row(root)
    first = row.children[0]
    assert first.children[0].type == "heading2", shape(first)
    assert texts(first) == ["Card", "Intro\nA"], texts(first)


# ---------------------------------------------------------------------------
# 5 — a `:::` closes a section opened INSIDE the row, never the one holding it
# ---------------------------------------------------------------------------


def test_a_heading_inside_the_row_does_not_swallow_the_next_cell():
    # Without this the `# Heading` in cell 2 owns the buttons, and they render
    # inside it rather than beside it — so there is no third cell at all.
    root = ast("![Image](x.png)\n:::\n# Heading\nText\n:::2\n[B1](/b) [B2](/b)\n")
    row = the_row(root)
    assert len(row.children) == 3, shape(row)
    assert row.children[0].content == "![Image](x.png)"
    # Cell 2 holds the heading LEAF and its body. The `heading_group` is the
    # section the row now lives inside, not the cell — the peel pulled the
    # image in, so the whole row sits under the section it belongs to.
    assert texts(row.children[1]) == ["Heading", "Text"]
    assert row.children[2].content == "[B1](/b) [B2](/b)"
    assert row.column_weights == (None, 2, None)


def test_an_empty_marker_is_not_a_cell():
    # `# ` / `## ` with nothing after it is a GROUPING DEVICE, not a heading —
    # `line_stacks` already says so. Its contentless leaf must stay a direct
    # child of the section; buried in a cell, an empty marker stops reading as
    # a section at all.
    root = ast("# \n⭐\n:::0\nBody\n")
    (section,) = root.children
    assert section.children[0].type == "heading1", shape(section)
    assert section.children[0].content in ("", None)
    assert section.children[1].column_row_group


def test_a_titled_heading_is_still_a_cell():
    # The other half: a TITLED heading is cell 1, or `## Title` + `:::` + body
    # has one cell and therefore no row.
    root = ast("## Title\n:::\nBody\n")
    row = the_row(root)
    assert row.children[0].type == "heading2"


def test_a_row_inside_a_card_does_not_escape_it():
    # The row belongs INSIDE the section — root holds no `:::`, so nothing is
    # lifted out. The section's own heading rides in cell 1.
    root = ast("## Card\nA\n:::\nB\n")
    (section,) = root.children
    assert section.heading_group and section.heading_level == 2
    row = the_row(root)
    assert texts(row.children[0]) == ["Card", "A"], shape(row)
    assert row.children[1].content == "B"


def test_the_heading_beside_its_text_is_the_two_cell_shape():
    # `## Title` + `:::` + body is exactly how an author writes "title on the
    # left, its text on the right" — the first case in
    # data/markdown/tests/tests-row-syntax.md.
    root = ast("## Heading 2 context\n:::\nText\n:::2\n")
    row = the_row(root)
    assert row.column_weights == (None, 2)
    assert row.children[0].type == "heading2"
    assert row.children[1].content == "Text"


def test_headed_columns_each_closed_by_a_divider_are_one_row():
    # The figma footer: every `:::1` is the last line of its own `######`
    # section, so the run's FIRST divider sits inside a section. It cuts
    # nothing there, so it closes the section as cell 1 of a row at the root —
    # an authored `:::` row is a row whatever its cells hold.
    root = ast("###### P\n[A](/a)\n[B](/b)\n:::1\n###### U\n[C](/c)\n:::1\n")
    row = the_row(root)
    assert len(row.children) == 2, shape(row)
    for cell, title in zip(row.children, ["P", "U"]):
        assert cell.heading_group and cell.heading_level == 6, shape(cell)
        assert cell.children[0].type == "heading6"
        assert cell.children[0].content == title
    assert row.column_weights == (1, 1)


def test_a_lone_section_closed_by_a_divider_is_still_no_row():
    # The same lift with nothing beside the section partitions nothing, and
    # the divider is dropped exactly as it was inside the section.
    root = ast("## Card\nA\n:::\n")
    assert rows(root) == []
    (section,) = root.children
    assert texts(section) == ["Card", "A"]


def test_a_row_inside_a_card_keeps_its_trailing_weight():
    # A section whose last divider is not its ONLY one holds a row of its own:
    # the trailing `:::2` weights that row's last cell and is not lifted.
    root = ast("## Card\nA\n:::\nB\n:::2\n## Next\nC\n")
    row = the_row(root)
    assert row.column_weights == (None, 2)
    assert texts(row.children[0]) == ["Card", "A"]
    assert root.children[-1].heading_group, shape(root)
    assert texts(root.children[-1]) == ["Next", "C"]


def test_a_row_nests_inside_a_cell():
    # A `:::` inside a section that is itself a cell builds its own row at its
    # own depth — the lift only reaches sections opened after a row is open.
    root = ast("Lead\n:::\n## Inner\nX\n___\nY\n")
    outer = rows(root)
    assert len(outer) == 1, [shape(r) for r in outer]


def test_text_above_the_first_headed_cell_is_its_own_cell():
    # The peel is transparent to `:::`, so `Links` and its `:::1` arrive inside
    # Plan's section. Plan is closed as a cell like Support, so what the peel
    # took is cell 1 — not a row inside Plan with Support dropped below it.
    root = ast("Links\n:::1\n### Plan\nTwo seats\n:::\n### Support\nEmail only\n:::\n")
    row = the_row(root)
    assert [texts(c) for c in row.children] == [
        ["Links"],
        ["Plan", "Two seats"],
        ["Support", "Email only"],
    ], [shape(c) for c in row.children]
    assert not row.children[0].heading_group
    for cell in row.children[1:]:
        assert cell.heading_group and cell.heading_level == 3, shape(cell)
        assert cell.children[0].type == "heading3"
    assert row.column_weights == (1, None, None)


def test_text_above_a_heading_met_inside_an_open_row_is_its_own_cell():
    # Once a row is open, the section is closed at its first divider; a divider
    # the peel put above the heading must not count as that first one. The text
    # is a cell and the section another.
    root = ast("Lead\n:::\n\nLinks\n:::\n### Plan\nTwo seats\n")
    row = the_row(root)
    assert [texts(c) for c in row.children] == [
        ["Lead"],
        ["Links"],
        ["Plan", "Two seats"],
    ], [shape(c) for c in row.children]
    assert row.children[2].heading_group, shape(row.children[2])


def test_a_lone_closed_section_does_not_wrap_the_text_above_it():
    # The same card with nothing after it parses the same way: its closing
    # `:::2` makes it a cell, so the text above it is cell 1 beside the card,
    # not inside it. Without the closing divider the row stays inside the
    # section (test_a_divider_is_transparent_to_the_heading_peel).
    root = ast("Links\n:::1\n### Plan\nTwo seats\n:::2\n")
    row = the_row(root)
    assert row in root.children, shape(root)
    assert [texts(c) for c in row.children] == [["Links"], ["Plan", "Two seats"]]
    assert row.children[1].heading_group, shape(row.children[1])
    assert row.column_weights == (1, 2)


# ---------------------------------------------------------------------------
# 6 — the cut, and what being a BREAK buys
# ---------------------------------------------------------------------------


def test_a_divider_suppresses_heading_detection_on_its_own_line():
    # `:::` reaches hr_lines before the heading scan, so it can never be read
    # as a heading or as heading text.
    root = ast(":::\n")
    assert [n.type for n in walk(root)] == ["root"]


def test_a_divider_is_transparent_to_the_heading_peel():
    # Unlike the other breaks, a `:::` does NOT bound the absorb. It says the
    # things either side of it are cells of one row, and cells must be
    # siblings — so an image above a divider above a heading travels into that
    # heading's group, and the row forms INSIDE the section rather than
    # stranding the image in the section before it.
    root = ast("![Logo](x.png)\n:::\n## Heading\nText\n")
    (section,) = root.children
    assert section.heading_group, shape(root)
    row = the_row(root)
    assert row in section.children or section.column_row_group
    assert row.children[0].content == "![Logo](x.png)"
    assert texts(row.children[1]) == ["Heading", "Text"]


def test_the_other_breaks_still_bound_the_peel():
    # Only `:::` is transparent. A `---` above a heading stops the absorb.
    root = ast("![Logo](x.png)\n---\n## Heading\nText\n")
    assert rows(root) == []
    assert root.children[0].content == "![Logo](x.png)"


def test_a_heading_still_absorbs_the_line_above_it_inside_a_cell():
    # Within a cell the absorb is unchanged, so a logo glued to its heading
    # stays one unit — it is the FIRST child of the cell, ahead of the heading.
    root = ast("A\n:::\n![Logo](x.png)\n# Heading\nText\n")
    cell = the_row(root).children[1]
    assert cell.children[0].content == "![Logo](x.png)", shape(cell)
    assert cell.children[1].type == "heading1"
    assert texts(cell) == ["![Logo](x.png)", "Heading", "Text"]


def test_a_divider_is_never_re_parsed_as_content():
    # _BREAK_TYPES membership is what stops the later splitters reading `:::`
    # as a key-value colon or a colon column. If one had, the literal text
    # would show up in the tree.
    root = ast("A\n:::\nB\n")
    assert ":::" not in "".join(texts(root))


def test_another_break_ends_the_row():
    # `___` / `***` / `;;;` bound a row as they bound any run of siblings, so a
    # cut written under the last cell closes the row instead of joining it.
    root = ast("A\n:::\nB\n___\nC\n")
    row = the_row(root)
    assert [c.content for c in row.children] == ["A", "B"], shape(row)
    tail = [c.type for c in root.children]
    assert NodeType.CONTENT_BREAK in tail, tail
    assert root.children[-1].content == "C"


def test_a_rule_does_not_end_the_row():
    # `---` paints and `___` cuts: a rule under a cell, even a block of its own,
    # is content of that cell, and the row runs on past it.
    root = ast("A\n:::\nB\n\n---\n\nC\n")
    row = the_row(root)
    assert len(row.children) == 2, shape(row)
    assert [c.type for c in row.children[1].children] == [
        NodeType.TEXT,
        NodeType.HORIZONTAL_RULE,
        NodeType.TEXT,
    ], shape(row.children[1])


def test_rules_alone_after_the_last_divider_are_no_cell():
    # The card closer `::: / --- / ___`: the rule paints under the row, as an
    # empty run after a trailing `:::` mints no cell.
    root = ast("A\n:::\nB\n:::\n\n---\n___\n")
    row = the_row(root)
    assert len(row.children) == 2, shape(row)
    after = root.children[root.children.index(row) + 1]
    assert after.type == NodeType.HORIZONTAL_RULE, shape(root)


def test_a_rule_divided_run_is_one_cell():
    # A `---` tight between two lines divides that block, so the whole run is
    # the cell — not its first line, with the rest stacked under the row.
    root = processed("## \nText\n:::\nKey: ... a\n---\nKey: ... b\n---\nKey: ... c\n")
    row = the_row(root)
    assert len(row.children) == 2, shape(row)
    cell = row.children[1]
    assert cell.glued_content_group, shape(cell)
    # Each `Key: ... v` line is a spring row: a group of two regions.
    assert [c.type for c in cell.children] == [
        NodeType.GROUP,
        NodeType.HORIZONTAL_RULE,
        NodeType.GROUP,
        NodeType.HORIZONTAL_RULE,
        NodeType.GROUP,
    ], shape(cell)


def test_a_blank_line_beside_a_divider_still_makes_the_row():
    root = ast("A\n:::\n\nB\n")
    assert [c.content for c in the_row(root).children] == ["A", "B"]


# ---------------------------------------------------------------------------
# 7 — it does not collide with the table delimiter row
# ---------------------------------------------------------------------------


def test_a_real_table_delimiter_row_is_not_a_divider():
    # This is the reason `:::` was chosen over `:---`: those spellings are
    # taken, and are already read for per-column alignment.
    for line in (":---", ":---:", "---:", "| :--- | ---: |"):
        assert _break_node_type(line) != NodeType.COLUMN_DIVIDER, line


def test_a_bare_divider_under_one_line_is_not_read_as_a_table():
    # A single-column GFM table needs no pipes, so `Name` over a delimiter row
    # IS a table. `:::` has no dashes, so the table pass cannot see it.
    root = ast("Name\n:::\nB\n")
    assert [c.content for c in the_row(root).children] == ["Name", "B"]


def test_a_table_beside_a_divider_still_groups_as_a_table():
    from md2ui.pipeline.grouper_split_criteria import SplitCriteria
    from md2ui.pipeline.data_point_detector import DataPointDetector

    criteria = SplitCriteria()
    g = MarkdownGrouper("| Name | Qty |\n| :--- | ---: |\n| Apples | 3 |\n")
    g.process(criteria, DataPointDetector())
    assert g.ast is not None
    kinds = {n.type for n in walk(g.ast)}
    assert NodeType.TABLE_HEADER in kinds, kinds
    assert NodeType.COLUMN_DIVIDER not in kinds, kinds


def test_a_row_survives_being_a_group_s_only_child():
    """A row that is the sole child of its section.

    ``AAA / ::: / ## H / body`` is one section holding one row, so the collapse
    merges the row into the section. The section becoming the row itself is
    fine; the cells being left stacked is not.
    """
    root = processed("AAA\n:::\n## H\nbody\n")
    row = the_row(root)
    assert row.heading_group, "the section and the row are one node here"
    assert texts(row.children[0]) == ["AAA"]
    assert texts(row.children[1]) == ["H", "body"]


def test_a_sole_child_row_keeps_its_weights():
    """The weights describe THESE cells, so a row that survives without them is
    a row whose ``:::0`` has quietly stopped meaning anything."""
    root = processed("![i](a.png)\n:::0\n## H\nbody\n")
    assert the_row(root).column_weights == (0, None)


def test_a_second_child_never_mattered():
    """Same document, plus a trailing ``---`` under the section.

    The extra child stops the collapse firing at all. Both spellings must give
    a row with the same cells; a ``---`` ends no row, so the rule is the last
    cell's last line.
    """
    one = the_row(processed("AAA\n:::\n## H\nbody\n"))
    two = the_row(processed("AAA\n:::\n## H\nbody\n\n---\n"))
    assert one.column_weights == two.column_weights
    *cells, last = [texts(c) for c in two.children]
    assert [texts(c) for c in one.children] == [*cells, last[:-1]]
    assert last[-1] == "---"


def test_an_earlier_row_does_not_change_a_later_section():
    """The lift must use the same scope ``_segments`` does.

    A ``:::`` row at one level must not make a heading section blocks later
    close at its divider. The card below must parse identically whether or not
    something earlier used a ``:::``.
    """
    card = "![img](x.png)\n:::\n## Heading 2 context\nText\n"
    # The last row is the card's; the "after a ::: row" case has an earlier one.
    alone = rows(processed(card))[-1]
    after_break = rows(processed("AAA\n\n___\n\n" + card))[-1]
    after_row = rows(processed("AAA\n:::\nBBB\n\n___\n\n" + card))[-1]
    for label, row in (("after a ___", after_break), ("after a ::: row", after_row)):
        assert row.heading_group and row.heading_level == 2, (
            f"{label}: the ROW must carry the section, got {shape(row)}"
        )
        assert [texts(c) for c in row.children] == [texts(c) for c in alone.children], (
            label
        )
    assert not any(c.heading_group for c in after_row.children), (
        "the section must not land on a cell — least of all the bare image leaf"
    )


# ---------------------------------------------------------------------------
# A `:::` indented under a list item divides that item, not the document
# ---------------------------------------------------------------------------

_ITEM_ROWS = "## Title\n- A\n  :::\n  B\n- C\n  :::\n  D\n"


def test_an_indented_divider_makes_a_row_inside_its_item():
    # Each item is its own row; neither the heading nor the next item is a cell.
    root = processed(_ITEM_ROWS)
    found = rows(root)
    assert len(found) == 2, [texts(r) for r in found]
    assert [texts(r) for r in found] == [["A", "B"], ["C", "D"]]
    assert all(r.type == NodeType.LIST_ITEM or r.column_row_group for r in found)
    assert "Title" not in [t for r in found for t in texts(r)]


def test_the_row_sits_inside_the_item():
    # The item holds the row, so its marker and its surface wrap every cell.
    root = processed("- ![i](a.png)\n  :::0\n  **Label**\n")
    item = next(n for n in walk(root) if n.type == NodeType.LIST_ITEM)
    assert rows(item), shape(item)
    assert texts(item) == ["![i](a.png)", "**Label**"], texts(item)
    assert the_row(item).column_weights == (0, None)


def test_a_top_level_divider_still_takes_the_heading():
    # Unindented, `:::` partitions the section as before: `## Title` + `:::`
    # + body is still "title beside its text".
    row = the_row(processed("## Title\nA\n:::\nB\n"))
    assert texts(row) == ["Title", "A", "B"], texts(row)


# ---------------------------------------------------------------------------
# 7 — narrow and wide: a second weight, or the space the cut applies in
# ---------------------------------------------------------------------------


def test_a_divider_may_say_where_it_cuts():
    # `<` cuts in narrow space only, `>` in wide space only; alone it is
    # weight 1 like a bare `:::`.
    for line in ("::: 1 <", "::: 1 >", "::: <", ":::>", "::: 0 >", ":::1<"):
        assert _break_node_type(line) == NodeType.COLUMN_DIVIDER, line


def test_a_second_number_is_the_wide_weight():
    for line in ("::: 1 1.5", "::: 0 1.5", ":::2 3"):
        assert _break_node_type(line) == NodeType.COLUMN_DIVIDER, line


def test_a_divider_that_contradicts_itself_is_a_bare_divider():
    # A pair AND a condition, two conditions, three numbers: plainly a divider
    # with its options mistyped, so it is read as a bare `:::` — and
    # `md2ui check` names it.
    for line in ("::: 1 1.5 >", "::: < >", "::: 1 2 3", "::: <1"):
        assert _break_node_type(line) == NodeType.COLUMN_DIVIDER, line
        assert divider_fell_back(line), line
    row = the_row(ast("A\n::: 1 1.5 >\nB\n"))
    assert row.column_weights == (None, None), row.column_weights
    assert row.column_weights_wide == () and row.column_cuts == ()


def test_a_valid_divider_did_not_fall_back():
    for line in (":::", "::: 1 <", "::: 1 1.5", ":::0"):
        assert not divider_fell_back(line), line


def test_words_after_a_divider_stay_text():
    # Pandoc's `::: note` container: reading it as a divider would turn the
    # note and what follows into cells nobody asked for.
    for line in ("::: note", "::: warning", "::: {.aside}"):
        assert _break_node_type(line) is None, line
        assert not divider_fell_back(line), line


def test_the_row_records_where_each_cut_applies():
    row = the_row(ast("A\n::: 1 <\nB\n::: >\nC\n"))
    assert row.column_cuts == ("narrow", "wide", None), row.column_cuts
    assert row.column_weights == (1, None, None)
    assert row.column_weights_wide == ()


def test_the_row_records_the_wide_weights():
    row = the_row(ast("A\n::: 1 1.5\nB\n:::\nC\n"))
    assert row.column_weights == (1, None, None)
    assert row.column_weights_wide == (1.5, None, None)
    assert row.column_cuts == ()


def test_a_row_spelled_the_old_way_serializes_as_before():
    # The new fields appear only when a divider wrote them.
    d = the_row(ast("A\n:::2\nB\n")).to_dict()
    assert "column_weights_wide" not in d and "column_cuts" not in d, d


def test_the_conditions_survive_the_json_round_trip():
    row = the_row(ast("A\n::: 1 1.5\nB\n::: <\nC\n"))
    back = MarkdownGroupNode.from_dict(row.to_dict())
    assert back.column_weights_wide == (1.5, None, None)
    assert back.column_cuts == (None, "narrow", None)


def test_a_sole_child_row_keeps_its_conditions():
    root = processed("![i](a.png)\n::: 0 >\n## H\nbody\n")
    assert the_row(root).column_cuts == ("wide", None)


def test_an_item_row_keeps_its_conditions():
    item = next(
        n
        for n in walk(processed("- A\n  ::: 1 <\n  B\n"))
        if n.type == NodeType.LIST_ITEM
    )
    assert the_row(item).column_cuts == ("narrow", None)


# ---------------------------------------------------------------------------
# 9 — `;;;` closes a row and leaves the run going
# ---------------------------------------------------------------------------


def test_three_semicolons_close_a_row():
    for line in (";;;", "; ; ;", "  ;;;;"):
        assert _break_node_type(line) == NodeType.ROW_CLOSER, line
    for line in (";;", "a;;;", ";;; b"):
        assert _break_node_type(line) is None, line


def test_a_closer_ends_the_row_and_leaves_nothing():
    root = ast("A\n:::\nB\n;;;\nC\n")
    assert [c.content for c in the_row(root).children] == ["A", "B"]
    assert root.children[-1].content == "C", shape(root)
    assert [n for n in walk(root) if n.type == NodeType.ROW_CLOSER] == []


def test_closed_rows_stay_adjacent_siblings():
    # The reason it exists: `___` leaves a break leaf between two rows, which
    # ends the run and so the grid. `;;;` leaves nothing between them.
    root = ast("A\n:::\nB\n;;;\nA\n:::\nB\n")
    assert [c.column_row_group for c in root.children] == [True, True], shape(root)


def test_a_content_break_still_ends_the_run():
    root = ast("A\n:::\nB\n___\nA\n:::\nB\n")
    assert NodeType.CONTENT_BREAK in [c.type for c in root.children], shape(root)


def test_repeated_closed_rows_share_a_kind():
    root = processed("A\n:::\nB\n;;;\nA\n:::\nB\n;;;\nA\n:::\nB\n")
    found = rows(root)
    assert len(found) == 3
    assert len({r.kind_hash for r in found}) == 1


def test_a_closer_outside_a_row_leaves_nothing():
    root = processed("A\n;;;\nB\n")
    assert [n for n in walk(root) if n.type == NodeType.ROW_CLOSER] == []
    assert ";;;" not in "".join(texts(root))


def test_a_closer_bounds_the_heading_peel():
    # It ends a row, so nothing above it belongs to what follows.
    root = ast("![Logo](x.png)\n;;;\n## Heading\nText\n")
    assert root.children[0].content == "![Logo](x.png)", shape(root)


# ---------------------------------------------------------------------------
# A row that flows is the line spelled across blocks
# ---------------------------------------------------------------------------

_SPELLINGS = "data/markdown/tests/test-separators-and-spacers.md"


def _grouped(text: str) -> MarkdownGroupNode:
    from md2ui import session

    root = session.group_markdown(text, session.load_grouping_kit())
    assert root is not None
    return root


def test_every_spelling_of_one_arrangement_is_one_kind():
    """Each `## Group` writes ONE arrangement with `+++`, ` | `, ` - `
    and `:::`; every spelling must come out the same kind of node."""
    from pathlib import Path

    root = _grouped(Path(_SPELLINGS).read_text())
    assert len(root.children) == 5, shape(root)
    for section in root.children:
        title, spellings = section.children[0].content, section.children[1:]
        assert any(s.column_row_group for s in spellings), title
        kinds = {s.kind_hash for s in spellings}
        assert len(kinds) == 1, (title, [s.kind_hash for s in spellings])


def test_a_flowing_rows_one_line_cells_are_its_pieces():
    """A one-line cell of an unweighted row is a `segment`, as the same text
    after a ` | ` is; a weighted row is proportions, not a line, and keeps its
    cells as they are."""
    flowing = the_row(_grouped("Alpha beta\n:::\nGamma delta\n"))
    assert [c.type for c in flowing.children] == [NodeType.SEGMENT] * 2
    piped = _grouped("Alpha beta | Gamma delta\n")
    line = next(n for n in walk(piped) if n.line_split_group)
    assert flowing.kind_hash == line.kind_hash
    weighted = the_row(_grouped("Alpha beta\n:::1\nGamma delta\n:::2\n"))
    assert [c.type for c in weighted.children] == [NodeType.TEXT] * 2


def test_a_cell_holding_a_split_line_stays_a_line():
    row = the_row(_grouped("Alpha | beta\n:::\nGamma delta\n"))
    assert row.children[0].line_split_group, shape(row)
    assert row.children[1].type == NodeType.SEGMENT


def test_blank_lines_inside_a_side_never_add_columns():
    """A row has one column per side of each `:::`, whatever the side holds:
    paragraphs a blank line apart stack inside their side, never beside it."""
    row = the_row(_grouped("A\n\n:::\n\nB\n\nC\n\nD\n"))
    assert len(row.children) == 2, shape(row)
    assert row.children[0].content == "A", shape(row)
    assert [c.content for c in row.children[1].children] == ["B", "C", "D"]


def test_blank_separated_groups_stay_in_the_first_side():
    """The same holds in the FIRST side, and for groups of lines: the byline
    beside the body, one column each, as the two weights say."""
    row = the_row(
        _grouped(
            "_Contributor_\n**Haqqi**\n\n_Reading time_\n2 minutes\n::: 1 >\n"
            "First paragraph.\n\nSecond paragraph.\n:::3\n"
        )
    )
    assert list(row.column_weights) == [1, 3], shape(row)
    assert len(row.children) == 2, shape(row)
    assert len(row.children[0].children) == 2, shape(row)
    assert len(row.children[1].children) == 2, shape(row)


TESTS = [
    test_an_indented_divider_makes_a_row_inside_its_item,
    test_the_row_sits_inside_the_item,
    test_a_top_level_divider_still_takes_the_heading,
    test_an_earlier_row_does_not_change_a_later_section,
    test_a_row_survives_being_a_group_s_only_child,
    test_a_sole_child_row_keeps_its_weights,
    test_a_second_child_never_mattered,
    test_three_or_more_colons_is_a_divider,
    test_interior_spaces_are_allowed_like_a_dash_rule,
    test_indentation_does_not_disarm_a_divider,
    test_two_colons_is_not_a_divider,
    test_a_divider_must_be_the_whole_line,
    test_the_four_spellings_do_four_different_things,
    test_a_divider_behind_a_list_marker_is_a_list_item,
    test_a_bare_divider_carries_no_weight,
    test_a_trailing_number_is_the_weight,
    test_zero_is_a_real_weight,
    test_a_weight_may_be_a_decimal,
    test_a_decimal_needs_a_leading_digit,
    test_a_non_numeric_suffix_is_not_a_divider,
    test_a_divider_may_say_where_it_cuts,
    test_a_second_number_is_the_wide_weight,
    test_a_divider_that_contradicts_itself_is_a_bare_divider,
    test_a_valid_divider_did_not_fall_back,
    test_words_after_a_divider_stay_text,
    test_the_row_records_where_each_cut_applies,
    test_the_row_records_the_wide_weights,
    test_a_row_spelled_the_old_way_serializes_as_before,
    test_the_conditions_survive_the_json_round_trip,
    test_a_sole_child_row_keeps_its_conditions,
    test_an_item_row_keeps_its_conditions,
    test_three_semicolons_close_a_row,
    test_a_closer_ends_the_row_and_leaves_nothing,
    test_closed_rows_stay_adjacent_siblings,
    test_a_content_break_still_ends_the_run,
    test_repeated_closed_rows_share_a_kind,
    test_a_closer_outside_a_row_leaves_nothing,
    test_a_closer_bounds_the_heading_peel,
    test_a_divider_makes_a_row_of_its_two_sides,
    test_no_divider_node_survives,
    test_an_unnumbered_row_records_no_weight,
    test_a_divider_weights_the_cell_ABOVE_it,
    test_a_trailing_divider_weights_the_last_cell,
    test_an_unweighted_cell_records_no_weight,
    test_a_decimal_weight_reaches_the_row,
    test_a_zero_weight_reaches_the_row,
    test_a_cell_may_hold_several_blocks,
    test_a_divider_that_partitions_nothing_mints_no_row,
    test_a_divider_with_no_content_at_all_leaves_nothing,
    test_the_pass_is_idempotent,
    test_the_last_cell_without_a_divider_records_no_weight,
    test_the_row_survives_the_json_round_trip,
    test_the_row_node_is_never_glued,
    test_glue_never_spans_a_divider,
    test_glue_inside_a_cell_is_untouched,
    test_a_heading_travels_into_cell_one_with_its_body,
    test_a_heading_inside_the_row_does_not_swallow_the_next_cell,
    test_an_empty_marker_is_not_a_cell,
    test_a_titled_heading_is_still_a_cell,
    test_a_row_inside_a_card_does_not_escape_it,
    test_the_heading_beside_its_text_is_the_two_cell_shape,
    test_headed_columns_each_closed_by_a_divider_are_one_row,
    test_a_lone_section_closed_by_a_divider_is_still_no_row,
    test_a_row_inside_a_card_keeps_its_trailing_weight,
    test_a_row_nests_inside_a_cell,
    test_text_above_the_first_headed_cell_is_its_own_cell,
    test_text_above_a_heading_met_inside_an_open_row_is_its_own_cell,
    test_a_lone_closed_section_does_not_wrap_the_text_above_it,
    test_a_divider_suppresses_heading_detection_on_its_own_line,
    test_a_divider_is_transparent_to_the_heading_peel,
    test_the_other_breaks_still_bound_the_peel,
    test_a_heading_still_absorbs_the_line_above_it_inside_a_cell,
    test_a_divider_is_never_re_parsed_as_content,
    test_another_break_ends_the_row,
    test_a_rule_does_not_end_the_row,
    test_a_rule_divided_run_is_one_cell,
    test_rules_alone_after_the_last_divider_are_no_cell,
    test_a_blank_line_beside_a_divider_still_makes_the_row,
    test_a_real_table_delimiter_row_is_not_a_divider,
    test_a_bare_divider_under_one_line_is_not_read_as_a_table,
    test_a_table_beside_a_divider_still_groups_as_a_table,
    test_every_spelling_of_one_arrangement_is_one_kind,
    test_a_flowing_rows_one_line_cells_are_its_pieces,
    test_a_cell_holding_a_split_line_stays_a_line,
    test_blank_lines_inside_a_side_never_add_columns,
    test_blank_separated_groups_stay_in_the_first_side,
]

if __name__ == "__main__":
    print("Column Divider Tests")
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
