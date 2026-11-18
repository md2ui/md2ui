"""
The ``...`` VERTICAL spring — a line holding nothing but three dots.

Its inline twin (`` ... `` inside one line) pushes the pieces of that line toward
opposite edges. This one does the same on the other axis: it cuts a run of
BLOCKS into regions and pushes them to the top and bottom of the height their
column was given. Positional, exactly like the horizontal rule — first region
top, last bottom, anything between centred.

A spring needs SURPLUS, and a column only has surplus if something gave it a
height. A free-standing column's height IS its content, so a spring there is
inert by construction. The useful case is a ``:::`` row cell, where the row is
as tall as its tallest cell and a shorter one has room to give away.

Run with: uv run python tests/column_spring_tests.py
"""

from pathlib import Path

from md2ui import session
from md2ui.pipeline.grouper_block_splits import _break_node_type
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.markdown_grouper import (
    ASTPatternAnalyzer,
    MarkdownGrouper,
    MarkdownGroupNode,
    NodeType,
)


def ast(text: str) -> MarkdownGroupNode:
    g = MarkdownGrouper(text)
    g.to_ast()
    assert g.ast is not None
    return g.ast


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def valigns(text: str) -> list:
    """``authored_valign`` of every content node, in document order."""
    root = ast(text)
    return [n.authored_valign for n in walk(root) if n.content]


def layout(text: str, width: float = 900.0) -> LayoutNode:
    g = MarkdownGrouper(text)
    g.to_ast()
    assert g.ast is not None
    ASTPatternAnalyzer(g.ast).fingerprints(include_unique=True)
    return LayoutGenerator().generate(g.ast, width, None)


# ---------------------------------------------------------------------------
# 1 — the spelling
# ---------------------------------------------------------------------------


def test_a_line_of_three_dots_is_a_spring():
    assert _break_node_type("...") == NodeType.VERTICAL_SPRING
    assert _break_node_type("   ...   ") == NodeType.VERTICAL_SPRING


def test_four_dots_are_dots():
    # Exactly three, the same rule the inline spring keeps.
    assert _break_node_type("....") is None
    assert _break_node_type("..") is None


def test_an_inline_spring_is_not_a_block_one():
    # `... A` splits one LINE and is handled by the separator layer; only a line
    # holding nothing else partitions a run of blocks.
    assert _break_node_type("... A") is None
    assert _break_node_type("A ...") is None
    assert _break_node_type("Total ... $42") is None


# ---------------------------------------------------------------------------
# 2 — the regions, and their positions
# ---------------------------------------------------------------------------


def test_one_spring_reads_top_then_bottom():
    assert valigns("A\n...\nB\n") == ["top", "bottom"]


def test_two_springs_read_top_center_bottom():
    assert valigns("A\n...\nB\n...\nC\n") == ["top", "center", "bottom"]


def test_a_leading_spring_pushes_the_block_down():
    # An empty region keeps its slot without minting a node, so the position
    # rule stays a position rule — the same thing `... A` does on a line.
    assert valigns("...\nOnly\n") == ["bottom"]


def test_a_trailing_spring_pushes_the_block_up():
    assert valigns("Only\n...\n") == ["top"]


def test_the_container_is_flagged():
    root = ast("A\n...\nB\n")
    assert root.valign_group is True


def test_no_spring_node_survives():
    # A Phase 1 instruction, like `***` and `:::`.
    root = ast("A\n...\nB\n")
    assert [n for n in walk(root) if n.type == NodeType.VERTICAL_SPRING] == []


def test_a_document_without_a_spring_is_untouched():
    root = ast("A\nB\n")
    assert root.valign_group is False
    assert all(n.authored_valign is None for n in walk(root))


def test_the_regions_survive_the_json_round_trip():
    root = ast("A\n...\nB\n")
    back = MarkdownGroupNode.from_dict(root.to_dict())
    assert back.valign_group is True
    assert [n.authored_valign for n in walk(back) if n.content] == ["top", "bottom"]


# ---------------------------------------------------------------------------
# 3 — it reaches the layout
# ---------------------------------------------------------------------------


def test_the_col_is_flagged_so_it_claims_its_height():
    lay = layout("A\n...\nB\n")
    cols = [n for n in walk(lay) if getattr(n, "col_spring", False)]
    assert len(cols) == 1, [n.type for n in walk(lay)]
    assert cols[0].type == "col"


def test_each_region_carries_its_alignment_to_the_renderer():
    lay = layout("A\n...\nB\n")
    col = next(n for n in walk(lay) if getattr(n, "col_spring", False))
    got = [(c.render_properties or {}).get("content_valign") for c in col.children]
    assert got == ["top", "bottom"], got


def test_the_flag_is_not_serialized():
    # Runtime-only, like `column_row` / `grid` / `bento` / `spring`.
    lay = layout("A\n...\nB\n")
    col = next(n for n in walk(lay) if getattr(n, "col_spring", False))
    assert "col_spring" not in col.to_dict()


def test_a_spring_inside_a_column_row_cell_partitions_that_cell():
    # The useful case: the cell is the box with height to give away, so the
    # spring must land on the CELL, not on the row -- whether the row is
    # proportioned (`:::1`) or collapses like a line (`:::`).
    for divider in (":::1", ":::"):
        lay = layout(f"Left\n{divider}\nA\n...\nB\n")
        row = next(n for n in walk(lay) if n.type == "row" and len(n.children) == 2)
        springs = [n for n in walk(lay) if getattr(n, "col_spring", False)]
        assert len(springs) == 1, divider
        assert springs[0] is not row, divider
        assert springs[0] in row.children, divider


def test_a_spring_is_transparent_to_the_heading_peel():
    # The same rule `:::` needs, for the same reason: a spring says the blocks
    # either side of it share one box, and sharing a box means being SIBLINGS.
    # An image above a spring above a heading has to travel INTO that heading's
    # group, or it is stranded in the section before and the spring has nothing
    # to place.
    root = ast("![Logo](x.png)\n...\n## Heading\nText\n")
    (section,) = root.children
    assert section.heading_group, [c.type for c in root.children]
    contents = [n.content for n in walk(section) if n.content]
    assert "![Logo](x.png)" in contents, contents


def test_the_ending_breaks_still_bound_the_peel():
    # Only the two PARTITION tokens are transparent. `---` / `___` / `***` end a
    # run, and an image above one of those stays where it was written.
    for brk in ("---", "___", "***"):
        root = ast(f"![Logo](x.png)\n{brk}\n## Heading\nText\n")
        assert root.children[0].content == "![Logo](x.png)", (
            brk,
            root.children[0].type,
        )


# ---------------------------------------------------------------------------
# indented under a list item, a spring belongs to that item
# ---------------------------------------------------------------------------


def processed(text: str) -> MarkdownGroupNode:
    """The whole grouper: item rows and item springs are built in Phase 2.1."""
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=None)
    assert g.ast is not None
    return g.ast


def items(root: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    return [n for n in walk(root) if n.type == NodeType.LIST_ITEM]


def test_an_indented_spring_stays_inside_its_item():
    # Read at the document's level, the item would end at the first `...` and
    # the text after it fall out of the list.
    root = processed("- A\n  :::\n  ...\n  B\n  ...\n- C\n")
    first, second = items(root)
    assert [n.content for n in walk(first) if n.content] == ["A", "B"]
    assert [n.content for n in walk(second) if n.content] == ["C"]
    assert not root.valign_group


def test_an_indented_spring_partitions_its_items_cell():
    root = processed("- A\n  :::\n  ...\n  B\n  ...\n")
    (item,) = items(root)
    assert item.column_row_group
    b = next(n for n in walk(item) if n.content == "B")
    assert b.authored_valign == "center"


def test_an_indented_spring_without_a_row_partitions_the_item():
    root = processed("- Top\n  ...\n  Bottom\n")
    (item,) = items(root)
    assert item.valign_group
    assert [n.authored_valign for n in walk(item) if n.content] == ["top", "bottom"]


def test_a_cards_springs_survive_into_its_section():
    # A tappable card `[ … ](agent:…)` and a photo card `![ … ](url)` group their
    # body on its own, then dissolve into the section. The flag the springs left
    # must follow the regions, or a stretched card has no height to divide.
    for body in (
        "[\nTop\n\n...\n\nBottom\n](agent:open)",
        "![\nTop\n\n...\n\nBottom\n](https://example.com/p.jpg)",
    ):
        root = processed(f"## \n\n{body}\n")
        held = [n for n in walk(root) if n.valign_group]
        assert held, body
        assert [n.authored_valign for n in walk(held[0]) if n.content] == [
            "top",
            "bottom",
        ], body


def test_no_spring_survives_inside_an_item():
    root = processed("- A\n  :::\n  ...\n  B\n  ...\n")
    assert [n for n in walk(root) if n.type == NodeType.VERTICAL_SPRING] == []
    assert "..." not in [n.content for n in walk(root)]


# ---------------------------------------------------------------------------
# a region of several lines is placed as one block, weighted row or not
# ---------------------------------------------------------------------------

# Ten lines make the left cell the tall one, so the right cell has surplus.
_TALL = "\n".join(f"Left line {i}" for i in range(1, 11))
_KIT: list = []


def _kit():
    if not _KIT:
        theme = session.load_theme(Path("data/markdown/tests/THEME.md"))
        _KIT.extend([session.load_grouping_kit(), theme, session.load_fonts(theme)])
    return _KIT


def grouped(text: str) -> MarkdownGroupNode:
    """The real grouping: the stacked ``**Title** : Body`` split needs the kit."""
    root = session.group_markdown(text, _kit()[0])
    assert root is not None
    return root


def right_cell_offset(divider: str, body: str) -> float:
    """How far the springs' block sits from the middle of the tall left cell."""
    kit, theme, fonts = _kit()
    root, index = session.prepare(
        grouped(f"{_TALL}\n{divider}\n...\n{body}\n...\n"), theme
    )
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 1280.0)
    left, right = [], []
    for b in scene.boxes:
        text = (index.get(b.content_id) or {}).get("content") if b.content_id else None
        if text:
            (left if text.startswith("Left line") else right).append(b)
    assert left and right, (divider, body)

    def mid(boxes):
        return (min(b.y for b in boxes) + max(b.y + b.height for b in boxes)) / 2

    return mid(right) - mid(left)


_BODIES = ("Alpha", "Alpha\nBravo", "Alpha\nBravo\nCharlie", "**Alpha** : Bravo")


def test_every_line_of_a_region_keeps_its_place():
    # Splitting the region into its lines, or its one line into stacked pieces,
    # must not leave the pieces without the region's alignment.
    for body in _BODIES[1:]:
        root = grouped(f"{_TALL}\n::: 1\n...\n{body}\n...\n")
        got = [
            n.authored_valign
            for n in walk(root)
            if n.content and not n.content.startswith("Left line")
        ]
        assert got and set(got) == {"center"}, (body, got)


def test_springs_centre_any_number_of_lines_in_a_weighted_row():
    # The weights size the cells; the springs still centre.
    for divider in ("::: 1", "::: 1.5 >"):
        for body in _BODIES:
            off = right_cell_offset(divider, body)
            assert abs(off) < 0.5, (divider, body, off)


def test_springs_centre_once_in_an_unweighted_row():
    # The row that flows like a line centres its stacked cells on its own; the
    # springs' cell must not be shifted by that AND by its springs.
    for divider in (":::", "::: >"):
        for body in _BODIES:
            off = right_cell_offset(divider, body)
            assert abs(off) < 0.5, (divider, body, off)


# ---------------------------------------------------------------------------
# a spring inside a painted card keeps every region inside that card
# ---------------------------------------------------------------------------

_CARD = "## \n🎯\n__Title__\n...\n_Caption_\n"
_CARD_ROW = (
    "## \n🎯\n__Authorized transactions promptly__\n...\n"
    "_Contributing to a well-managed financial system_\n\n"
    "## \n🛡️\n__Secure__\n...\n_Short caption_\n\n"
    "## \n💳\n__Cards that work everywhere you shop__\n...\n"
    "_A caption that is a good deal longer than the others in this row_\n"
)


def captions_in_sections(text: str, width: float) -> list:
    """Each caption box with the ``##`` section it belongs to: the last one that
    opens above it in its column, since a caption that escaped is below its box."""
    kit, theme, fonts = _kit()
    root, index = session.prepare(grouped(text), theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, width)
    sections = [s for s in scene.sections if s.kind == "section" and s.level == 2]
    out = []
    for b in scene.boxes:
        node = (index.get(b.content_id) or {}) if b.content_id else {}
        if node.get("text_style") != "muted":
            continue
        cx = b.x + b.width / 2
        above = [s for s in sections if s.x <= cx <= s.x + s.width and s.y <= b.y]
        out.append((b, max(above, key=lambda s: s.y)))
    assert out, text
    return out


def test_the_bottom_region_stays_inside_its_card():
    # The region above the spring is a glued card of its own; measured without
    # its card padding, that padding would read as surplus and push the caption
    # below the `##` card's painted edge.
    for width in (767.0, 1280.0):
        for b, sec in captions_in_sections(_CARD, width):
            assert b.y + b.height <= sec.y + sec.height - sec.padding.bottom + 0.5, (
                width,
                b.y + b.height,
                sec.y + sec.height,
            )


def test_a_row_of_spring_cards_lines_its_captions_up_inside():
    for width in (767.0, 1280.0):
        got = captions_in_sections(_CARD_ROW, width)
        for b, sec in got:
            floor = sec.y + sec.height - sec.padding.bottom
            assert abs(b.y + b.height - floor) < 0.5, (width, b.y + b.height, floor)


def test_a_spring_keeps_the_card_one_glued_block():
    # A `...` divides the space inside one box, as `+++`
    # does, so the `##` body stays one glued card, not a panel around the
    # blocks above the spring.
    card = next(n for n in walk(grouped(_CARD)) if n.heading_group)
    assert card.glued_content_group and card.valign_group, card.to_dict()
    nested = [n for n in walk(card) if n is not card and n.glued_content_group]
    assert not nested, [n.to_dict() for n in nested]


def test_no_card_paints_inside_the_spring_card():
    kit, theme, fonts = _kit()
    for width in (767.0, 1280.0):
        root, index = session.prepare(grouped(_CARD), theme)
        scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, width)
        kinds = [s.kind for s in scene.sections]
        assert kinds == ["section"], (width, kinds)


TESTS = [
    test_a_cards_springs_survive_into_its_section,
    test_a_line_of_three_dots_is_a_spring,
    test_four_dots_are_dots,
    test_an_inline_spring_is_not_a_block_one,
    test_one_spring_reads_top_then_bottom,
    test_two_springs_read_top_center_bottom,
    test_a_leading_spring_pushes_the_block_down,
    test_a_trailing_spring_pushes_the_block_up,
    test_the_container_is_flagged,
    test_no_spring_node_survives,
    test_a_document_without_a_spring_is_untouched,
    test_the_regions_survive_the_json_round_trip,
    test_the_col_is_flagged_so_it_claims_its_height,
    test_each_region_carries_its_alignment_to_the_renderer,
    test_the_flag_is_not_serialized,
    test_a_spring_inside_a_column_row_cell_partitions_that_cell,
    test_a_spring_is_transparent_to_the_heading_peel,
    test_the_ending_breaks_still_bound_the_peel,
    test_an_indented_spring_stays_inside_its_item,
    test_an_indented_spring_partitions_its_items_cell,
    test_an_indented_spring_without_a_row_partitions_the_item,
    test_no_spring_survives_inside_an_item,
    test_every_line_of_a_region_keeps_its_place,
    test_springs_centre_any_number_of_lines_in_a_weighted_row,
    test_springs_centre_once_in_an_unweighted_row,
    test_the_bottom_region_stays_inside_its_card,
    test_a_row_of_spring_cards_lines_its_captions_up_inside,
    test_a_spring_keeps_the_card_one_glued_block,
    test_no_card_paints_inside_the_spring_card,
]

if __name__ == "__main__":
    print("Column Spring Tests")
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
