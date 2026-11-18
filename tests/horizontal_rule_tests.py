"""
Unit tests for the painted ``---`` horizontal rule.

Four behaviours, all consumed by layout_render:
  1. a rule is a DIVIDER — it takes the group gap whatever it separates, so it
     never inherits the tight element gap from a leaf neighbour;
  2. a rule stays where it was written: one that ends a heading group is that
     group's last child and paints INSIDE its background box, and a rule meant
     to lie between two groups is written after a ``***`` that closes the first;
  3. a rule is drawn WHERE IT WAS PLACED — never widened, moved or suppressed to
     line up with a sibling cell's;
  4. rule paint can be partially overridden at each authored Styling & Spacing
     level, then its resolved stroke color follows the normal replacement path.

Plus the ``___`` invisible break, whose whole job is the one thing ``---`` must
NOT do: a ``___`` that ends a heading section is lifted out as that section's
next SIBLING, so it can cut a run of repeated sections apart. A break trapped
inside one group cannot separate that group from the next.

``---`` deliberately stays put. It is the spelling every markdown generator
reaches for when it wants a visible divider, so documents written by authors who
never heard of this project are full of them. Lifting those would
break up card boards nobody asked to break up. The rare, deliberate spelling is
the one allowed to restructure.

Run with: uv run python tests/horizontal_rule_tests.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "tests")

from markdown_datapoint_split_tests import _processed_with_criteria

from md2ui.pipeline.grouper_types import NodeType
from md2ui.pipeline.markdown_grouper import MarkdownGrouper
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.render_text_scopes import scoped_horizontal_rule_style
from md2ui.pipeline import render_backgrounds as RBG
from md2ui.pipeline import render_measure as RMS
from md2ui.pipeline import render_place as RPL
from md2ui.pipeline import render_spacing as RSP
from md2ui.pipeline import layout_render as LR
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.theme import parse_theme
from md2ui.utils.font_loader import (
    load_custom_fonts,
    resolve_typeface,
    weight_from_str,
)

LEAF = "Plain sentence here."
GROUP = "key:a | key:b"


def _themed(theme=None):
    """The shipped THEME.md and its fonts, or *theme* and its fonts when given."""
    theme = (
        theme
        if theme is not None
        else parse_theme(Path("data/markdown/tests/THEME.md"))
    )
    custom = load_custom_fonts(theme.font_paths)
    name = theme.text.font_name or "Arial"
    bw = weight_from_str(theme.text.font_weight)

    def tf(w, i):
        return resolve_typeface(name, w, i, custom)

    return theme, FontSet(
        tf(bw, False),
        tf(700, False),
        tf(bw, True),
        tf(700, True),
        tf(bw, False),
        None,
        {},
    )


def _theme_from(markdown: str):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "THEME.md"
        path.write_text(markdown)
        return parse_theme(path)


def test_level_rule_styles_parse_and_cascade_partially():
    theme = _theme_from(
        """## Horizontal Rule
Stroke color: #111111
Stroke width: 1

## Styling & Spacing
### Root
#### Horizontal Rule
Stroke color: #223344

### Heading 2
#### Horizontal Rule
Stroke width: 3

### Heading 4
#### Horizontal Rule
Stroke width: not-a-number

### Quotes
#### Horizontal Rule
Stroke color: #556677

### Elements
#### Horizontal Rule
Stroke width: 99

### Fixed styles
#### Featured
##### Horizontal Rule
Stroke width: 5
"""
    )
    heading = scoped_horizontal_rule_style(theme, ("root", "heading:2"))
    assert heading.stroke_color == 0xFF223344
    assert heading.stroke_width == 3
    invalid = scoped_horizontal_rule_style(theme, ("root", "heading:4"))
    assert invalid.stroke_color == 0xFF223344
    assert invalid.stroke_width == 1
    nested = scoped_horizontal_rule_style(
        theme, ("root", "heading:2", "fixed:featured", "quotes")
    )
    assert nested.stroke_color == 0xFF556677
    assert nested.stroke_width == 5
    assert "" not in theme.horizontal_rule_overrides
    print("  ✓  local rule paint cascades property-by-property; Elements is excluded")


def test_rule_node_keeps_its_authored_style_scope():
    ast = _processed_with_criteria("## Section\n\nbody\n\n---\n")

    def rules(node):
        if node.type == "horizontal_rule":
            yield node
        for child in node.children:
            yield from rules(child)

    rule = next(rules(ast))
    assert rule.text_style_chain == ("root", "heading:2")
    print("  ✓  a rule keeps its authored heading scope after grouping")


def test_rule_paint_uses_local_style_and_color_replacement():
    theme = _theme_from(
        """## Styling & Spacing
### Root
#### Horizontal Rule
Stroke color: #223344
### Heading 2
#### Horizontal Rule
Stroke width: 4
"""
    )
    theme.color_replacements = {0xFF101010: {"stroke": {0xFF223344: 0xFFFFFFFF}}}
    box = LayoutBox(
        x=2.0,
        y=3.0,
        width=20.0,
        height=0.0,
        bg_stack=(0xFF101010,),
    )

    class Canvas:
        call = None

        def drawLine(self, *args):
            self.call = args

    canvas = Canvas()
    LR.draw_horizontal_rule(
        canvas,
        box,
        theme,
        {"text_style_chain": ["root", "heading:2"]},
    )
    assert canvas.call is not None
    paint = canvas.call[-1]
    assert paint.getColor() == 0xFFFFFFFF
    assert paint.getStrokeWidth() == 4
    print("  ✓  painting uses the local rule style and existing stroke replacements")


def _laid_out(src: str, width: float = 900.0, theme=None):
    """(theme, node_index, layout, boxes, section_boxes) for *src*."""
    theme, fonts = _themed(theme)
    ast = _processed_with_criteria(src)
    node_index: dict = {}
    LR._walk(ast.to_dict(), node_index)
    w = LR._content_width(width)
    layout = LayoutGenerator().generate(
        ast,
        w,
        theme,
        measure=LR.make_layout_measurer(node_index, fonts, theme),
        measure_width=LR.make_width_measurer(fonts, theme),
        measure_line=LR.make_line_width_measurer(fonts, theme),
        measure_marker=LR.make_marker_measurer(fonts, theme),
    )
    RPL.bake_render_cascade(layout)
    h = RMS.natural_height(layout, w, node_index, fonts, theme)
    section_boxes: list = []
    boxes = RPL.place_boxes(
        layout,
        0,
        0,
        w,
        h,
        node_index,
        fonts,
        theme,
        section_boxes=section_boxes,
    )
    return theme, node_index, layout, boxes, section_boxes


def _is_rule(content_id, node_index) -> bool:
    return node_index.get(content_id or "", {}).get("type") == "horizontal_rule"


def _deep_trailing_rule(node, node_index):
    """The rule a subtree ENDS with, following the last child down, or None.

    A rule written between two sections attaches to the preceding one, so it
    lands as that section's last element — possibly several levels down, since a
    heading section's last child is often the last SUB-section.
    """
    n = node
    while n.children:
        n = n.children[-1]
    return n if n.type == "-" and _is_rule(n.content_id, node_index) else None


def _rule_boxes(boxes, node_index):
    return [b for b in boxes if b.content_id and _is_rule(b.content_id, node_index)]


# ---------------------------------------------------------------------------
# 1 — the rule takes the group gap whatever it separates
# ---------------------------------------------------------------------------


def _top_gaps(src: str):
    theme, node_index, layout, _boxes, _sb = _laid_out(src, 700.0)
    col = layout.children[0]
    return theme, [
        RSP._sibling_gap(
            col.children[i - 1],
            col.children[i],
            theme,
            "col",
            0,
            node_index,
            col,
        )[0]
        for i in range(1, len(col.children))
    ]


def test_rule_takes_the_group_gap_whatever_it_separates():
    for label, src in (
        ("leaf/leaf", f"{LEAF}\n\n---\n\n{LEAF}"),
        ("group/group", f"{GROUP}\n\n---\n\n{GROUP}"),
        ("group/leaf", f"{GROUP}\n\n---\n\n{LEAF}"),
        ("leaf/group", f"{LEAF}\n\n---\n\n{GROUP}"),
    ):
        theme, gaps = _top_gaps(src)
        want = theme.elements.group_col_spacing
        assert gaps == [want, want], f"{label}: {gaps}"
    print("  ✓  a rule takes the group gap on both sides, whatever it separates")


def test_a_section_boundary_still_outranks_the_rule():
    # The section branch returns before the rule clause: a heading's own spacing
    # describes the heading, not the rule beside it.
    theme, node_index, layout, _b, _s = _laid_out(
        f"{LEAF}\n\n---\n\n## Heading\n\nbody text\n", 700.0
    )
    col = layout.children[0]
    seen = [
        RSP._sibling_gap(
            col.children[i - 1],
            col.children[i],
            theme,
            "col",
            0,
            node_index,
            col,
        )[1]
        for i in range(1, len(col.children))
    ]
    assert any(seen), "the section boundary must still report a section gap"
    print("  ✓  a section boundary still outranks the rule")


# ---------------------------------------------------------------------------
# 2 — a rule stays in the section it was written in
# ---------------------------------------------------------------------------


def _trailing_rules_inside(src: str, theme=None) -> int:
    """Sections that END with a rule, counted when that rule paints inside a box."""
    theme, node_index, layout, boxes, section_boxes = _laid_out(src, theme=theme)
    by_id: dict = {}
    for b in boxes:
        if b.content_id:
            by_id.setdefault(b.content_id, b)
    bad = 0

    def walk(n, levels=frozenset(), owner=0):
        nonlocal bad
        for c in n.children:
            if RBG._wrap_layers(c, theme, levels):
                rule = _deep_trailing_rule(c, node_index)
                if rule is not None and rule.content_id in by_id:
                    rb = by_id[rule.content_id]
                    if any(
                        sb.x <= rb.x < sb.x + sb.width
                        and sb.y <= rb.y < sb.y + sb.height - 0.01
                        for sb in section_boxes
                    ):
                        bad += 1
            walk(c, levels, owner)

    walk(layout)
    return bad


def _cell_rule_ids(node, in_grid: bool = False) -> set:
    """Rules that live INSIDE a grid cell, which never divide two sections.

    A rule between two sections is a real SIBLING of the two section wrappers.
    A rule inside a gridded cell is the opposite case — it is drawn where it was
    placed, in its own cell
    (``test_a_gridded_rows_rules_stay_in_their_own_cells``). The two are told
    apart by the tree, not by ``y``: when the last cell of a grid ends a
    section, its trailing rule sits at exactly the section box's bottom edge,
    and a purely geometric reading counts it as dividing that section from the
    next one. It divides two cells.
    """
    out = set()
    for c in node.children:
        here = in_grid or bool(getattr(node, "grid", False))
        if here and c.type == "-" and c.content_id:
            out.add(c.content_id)
        out |= _cell_rule_ids(c, here)
    return out


def _dividing_rule_gaps(src: str, theme=None):
    """[(gap above, gap below)] for each rule that divides two section boxes."""
    _t, node_index, _lay, boxes, section_boxes = _laid_out(src, theme=theme)
    secs = sorted(
        (sb for sb in section_boxes if sb.kind == "section"), key=lambda s: s.y
    )
    in_cell = _cell_rule_ids(_lay)
    out = []
    for r in _rule_boxes(boxes, node_index):
        if r.width <= 0 or r.content_id in in_cell:
            continue
        above = max(
            (s.y + s.height for s in secs if s.y + s.height <= r.y + 0.01),
            default=None,
        )
        below = min((s.y for s in secs if s.y >= r.y - 0.01), default=None)
        if above is not None and below is not None:
            out.append((round(r.y - above, 1), round(below - r.y, 1)))
    return out


# A background on `##` sections gives them boxes, which is what these tests need
# to tell "inside" from "between"; padding keeps a rule that ends a section off
# its box's edge. Inline, so a change to the shipped THEME.md cannot move it.
_BOXED_SECTIONS = """## Styling & Spacing
### Heading 2
Background colors:
- #FFFFFF40
Padding: 16
"""


# Two sections of different shapes, so they stack rather than grid side by side:
# the question is where the rule lies between two full-width boxes.
_FIRST = "## Section\n\nbody text here\n\n"
_NEXT = "## Next\n\nmore body\n\n- a list item\n- another item\n"


def test_a_trailing_rule_paints_inside_its_section():
    # `---` stays where it is written: at the end of a section it is that
    # section's last child and paints inside its box, dividing nothing.
    theme = _theme_from(_BOXED_SECTIONS)
    src = _FIRST + "---\n\n" + _NEXT
    assert _trailing_rules_inside(src, theme) == 1
    assert _dividing_rule_gaps(src, theme) == []
    print("  ✓  a rule ending a section paints inside that section's box")


def test_a_rule_after_a_section_stop_lies_between_the_boxes():
    # To divide two sections, close the first with `***` and write the rule
    # after it: the rule is then a sibling of the two boxes, between them.
    theme = _theme_from(_BOXED_SECTIONS)
    src = _FIRST + "***\n\n---\n\n" + _NEXT
    assert _trailing_rules_inside(src, theme) == 0
    gaps = _dividing_rule_gaps(src, theme)
    assert len(gaps) == 1, gaps
    above, below = gaps[0]
    assert above == below and above > 0, gaps
    print("  ✓  `***` then `---` puts the rule between the two boxes")


# ---------------------------------------------------------------------------
# 3 — a rule is drawn where it was placed
# ---------------------------------------------------------------------------


def _rule_row_cells(node, node_index, cells: int = 1):
    """``{rule content_id: cells in its nearest enclosing row}``."""
    out: dict = {}
    for c in node.children:
        n = len(node.children) if node.type == "row" else cells
        if c.type == "-" and _is_rule(c.content_id, node_index):
            out[c.content_id] = n
        out.update(_rule_row_cells(c, node_index, n))
    return out


def test_a_gridded_rows_rules_stay_in_their_own_cells():
    # A row's per-cell rules are never collapsed into ONE full-width line at
    # the bottom of the TALLEST cell: a rule is drawn where it is.
    src = Path("data/markdown/claude/ai-summit-schedule.md").read_text()
    for width in (990.0, 1280.0):
        _t, node_index, layout, boxes, _sb = _laid_out(src, width)
        rules = _rule_boxes(boxes, node_index)
        assert rules, width
        assert all(b.width > 0 for b in rules), (
            width,
            [(b.x, b.width) for b in rules if b.width <= 0],
        )
        cells = _rule_row_cells(layout, node_index)
        content = LR._content_width(width)
        for b in rules:
            n = cells.get(b.content_id, 1)
            # One of n cells, plus slack for the column gaps it does not span.
            assert b.width * n <= content + 40, (width, n, b.x, b.width)
    print("  ✓  every rule is drawn at its own cell, none suppressed")


# ---------------------------------------------------------------------------
# 4 — a break leaf's content is a SPELLING, and no pass may re-read it
# ---------------------------------------------------------------------------


def _leaves(src: str, width: float = 800.0):
    """``(node type, content)`` per placed leaf, in document order."""
    _t, node_index, _lay, boxes, _sb = _laid_out(src, width)
    out = []
    for b in boxes:
        n = node_index.get(b.content_id or "", {})
        if n:
            out.append((str(n.get("type", "")), str(n.get("content", ""))))
    return out


def _rules(src: str, width: float = 800.0):
    return [c for t, c in _leaves(src, width) if t == "horizontal_rule"]


def test_a_spaced_dash_rule_is_still_a_rule():
    """``- - -`` is a thematic break, but its own characters read as a list
    item to the list splitter and as a separator split to ` - `. Either one re-reading
    it costs the paint: a horizontal_rule draws only as a LEAF, so a rule that
    picked up a child renders that child's literal text instead."""
    for spelling in ("---", "----", "- - -", "-  -  -"):
        src = f"x\n\n{spelling}\n\ny\n"
        assert _rules(src) == [spelling], (
            f"{spelling!r} did not survive as one rule leaf: {_leaves(src)}"
        )


def test_a_rule_written_as_a_list_item_is_still_a_rule():
    leaves = _leaves("- x\n- ---\n- y\n")
    assert [t for t, _ in leaves] == [
        "list_item",
        "horizontal_rule",
        "list_item",
    ], leaves


def test_the_invisible_break_spellings_are_untouched():
    """``_ _ _`` works because no splitter matches underscores; the type skip
    must not disturb it."""
    for spelling in ("___", "_ _ _"):
        leaves = _leaves(f"x\n\n{spelling}\n\ny\n")
        assert [t for t, _ in leaves] == [
            "text",
            "content_break",
            "text",
        ], leaves


def test_a_real_list_is_still_a_list():
    """The skip is keyed on the node TYPE, so ordinary content is unaffected —
    including a list and a line the separator split owns."""
    assert [t for t, _ in _leaves("- a\n- b\n- c\n")] == ["list_item"] * 3
    assert [t for t, _ in _leaves("A - B\n")] == ["segment", "segment"]


def test_a_break_behind_a_list_marker_is_a_rule():
    """All three spellings collapse to a painted rule inside a list, and the
    marker is not drawn — the leaf is the rule itself, not a list item."""
    for marker in ("-", "*", "+", "1."):
        for spelling in ("---", "___", "***"):
            if marker == spelling[0]:
                # Same character throughout, so CommonMark reads the whole line
                # as one thematic break rather than a marked one — covered by
                # test_a_uniform_run_keeps_its_own_spelling instead.
                continue
            src = f"{marker} a\n{marker} {spelling}\n{marker} b\n"
            types = [t for t, _ in _leaves(src)]
            assert types == [
                "list_item" if marker != "1." else "ordered_item",
                "horizontal_rule",
                "list_item" if marker != "1." else "ordered_item",
            ], f"{marker} {spelling}: {_leaves(src)}"


def test_a_uniform_run_keeps_its_own_spelling():
    """CommonMark's rule is three or more MATCHING characters, and it outranks a
    list item — so these are breaks in their own right, not marked ones, and
    each keeps the meaning its spelling carries."""
    for line, kind in (
        ("- - -", "horizontal_rule"),
        ("- --", "horizontal_rule"),
        ("- ---", "horizontal_rule"),
        ("_ _ _", "content_break"),
        ("___", "content_break"),
    ):
        leaves = _leaves(f"x\n\n{line}\n\ny\n")
        assert [t for t, _ in leaves] == ["text", kind, "text"], (line, leaves)
    # ...and the star spellings stay SECTION STOPS, which are consumed whole —
    # `* ***` is four matching stars, not a bullet carrying `***`.
    for line in ("* * *", "* **", "* ***", "***"):
        leaves = _leaves(f"x\n\n{line}\n\ny\n")
        assert [t for t, _ in leaves] == ["text", "text"], (line, leaves)


def test_a_marker_before_ordinary_text_is_still_a_list():
    """The marked form needs 3+ break characters and nothing else, so a list
    item that merely starts with dashes is untouched."""
    assert [t for t, _ in _leaves("- --option\n- b\n")] == [
        "list_item",
        "list_item",
    ]


def _sections_grid(doc: str) -> bool:
    """True when two same-shaped `## ` sections in *doc* end up side by side."""
    from md2ui.pipeline.layout_generator import LayoutGenerator
    from md2ui.pipeline.markdown_grouper import ASTPatternAnalyzer, MarkdownGrouper

    g = MarkdownGrouper(doc)
    g.to_ast()
    assert g.ast is not None
    ASTPatternAnalyzer(g.ast).fingerprints(include_unique=True)
    lay = LayoutGenerator().generate(g.ast, 1000.0, None)

    def walk(n):
        yield n
        for c in n.children:
            yield from walk(c)

    return any(getattr(n, "grid", False) for n in walk(lay))


def test_a_trailing_content_break_is_lifted_out_of_its_section():
    from md2ui.pipeline.grouper_types import NodeType
    from md2ui.pipeline.markdown_grouper import MarkdownGrouper

    g = MarkdownGrouper("## A\nx\n___\n## B\ny\n")
    g.to_ast()
    assert g.ast is not None
    kinds = [c.type for c in g.ast.children]
    assert kinds.count(NodeType.CONTENT_BREAK) == 1, kinds
    # ...and it is BETWEEN the two sections, not inside the first.
    assert kinds.index(NodeType.CONTENT_BREAK) == 1, kinds
    first = g.ast.children[0]
    assert all(c.type != NodeType.CONTENT_BREAK for c in first.children)


def test_a_content_break_stops_two_sections_gridding():
    # The one job `___` exists for: it only cuts, which is what breaking up a
    # repeated-element grid needs.
    assert _sections_grid("## A\nx\n## B\ny\n"), "no break: should grid"
    assert not _sections_grid("## A\nx\n___\n## B\ny\n"), "`___` should cut"


def test_a_trailing_rule_is_left_where_it_was():
    # `---` is the common spelling and must not restructure a document written
    # by someone who does not know this syntax.
    assert _sections_grid("## A\nx\n---\n## B\ny\n"), "`---` must not cut"


def _top(src: str) -> list:
    """The root's children after the whole pipeline: ``(type, glued, kids)``."""
    g = MarkdownGrouper(src)
    g.process(criteria=None, detector=None)
    assert g.ast is not None
    return [
        (c.type, c.glued_content_group, [k.type for k in c.children])
        for c in g.ast.children
    ]


def test_a_tight_rule_divides_one_glued_block():
    # `---` paints and `___` cuts: written tight between two lines, a rule is a
    # divider under the line above, and the run it divides stays one block.
    assert _top("Alpha one\n---\nBeta two\n---\nGamma three\n") == [
        (
            NodeType.GROUP,
            True,
            [NodeType.TEXT, NodeType.HORIZONTAL_RULE] * 2 + [NodeType.TEXT],
        )
    ]


def test_a_spaced_rule_is_still_a_block_of_its_own():
    # A blank line on either side keeps the rule a sibling.
    for src in ("Alpha one\nBeta\n\n---\nGamma\nDelta\n", "Alpha\n---\n\nBeta\n"):
        types = [t for t, _, _ in _top(src)]
        assert NodeType.HORIZONTAL_RULE in types, (src, types)


def test_a_rule_beside_a_heading_still_cuts():
    # A rule tight under a heading, or tight above the next one, divides no
    # block: the section above still swallows it as its last child.
    for src in ("## A\n---\nText\n", "## A\nText\n---\n## B\nMore\n"):
        kids = _top(src)[0][2]
        assert NodeType.HORIZONTAL_RULE in kids, (src, kids)


TESTS = [
    test_level_rule_styles_parse_and_cascade_partially,
    test_rule_node_keeps_its_authored_style_scope,
    test_rule_paint_uses_local_style_and_color_replacement,
    test_a_trailing_content_break_is_lifted_out_of_its_section,
    test_a_content_break_stops_two_sections_gridding,
    test_a_trailing_rule_is_left_where_it_was,
    test_rule_takes_the_group_gap_whatever_it_separates,
    test_a_section_boundary_still_outranks_the_rule,
    test_a_trailing_rule_paints_inside_its_section,
    test_a_rule_after_a_section_stop_lies_between_the_boxes,
    test_a_gridded_rows_rules_stay_in_their_own_cells,
    test_a_spaced_dash_rule_is_still_a_rule,
    test_a_rule_written_as_a_list_item_is_still_a_rule,
    test_the_invisible_break_spellings_are_untouched,
    test_a_real_list_is_still_a_list,
    test_a_break_behind_a_list_marker_is_a_rule,
    test_a_uniform_run_keeps_its_own_spelling,
    test_a_marker_before_ordinary_text_is_still_a_list,
    test_a_tight_rule_divides_one_glued_block,
    test_a_spaced_rule_is_still_a_block_of_its_own,
    test_a_rule_beside_a_heading_still_cuts,
]

if __name__ == "__main__":
    print("Horizontal Rule Tests")
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
