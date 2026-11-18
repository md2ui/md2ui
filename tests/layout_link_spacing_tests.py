"""
Unit tests for pure-pill-group spacing: INSIDE one line block (a `line_split`
container, or a card nested in one — `bake_render_cascade` bakes `gap_in_line`),
a container whose entire leaf content is pills (links / inline_code) spaces with
ELEMENT gaps toward adjacent leaves and other pure-pill blocks, so a line's pills
stay evenly spaced after the flow wraps them. OUTSIDE such a container two pill
blocks are separate elements and keep the group gap. Mixed groups, sections and
images keep their own gap kinds. The generator's `_cell_gap` mirrors the
kinds but not the containment test — it is only asked about gaps within a run.
Run with: uv run layout_link_spacing_tests.py
"""

from layout_bento_tests import _ast, _group, _leaf
from md2ui.pipeline.render_place import bake_render_cascade
from md2ui.pipeline.generator_units import _cell_gap, _is_pure_element_group
from md2ui.pipeline.render_spacing import _is_pure_element_block, _sibling_gap
from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.theme import SectionStyle, Theme

ELEMENT_ROW, ELEMENT_COL = 8.0, 4.0
GROUP = 16.0
SECTION = 32.0


def _theme() -> Theme:
    t = Theme()
    t.elements.row_spacing = ELEMENT_ROW
    t.elements.col_spacing = ELEMENT_COL
    t.elements.group_row_spacing = GROUP
    t.elements.group_col_spacing = GROUP
    t.sections[2] = SectionStyle(row_spacing=SECTION, col_spacing=SECTION)
    return t


def _leaf_node(cid: str) -> LayoutNode:
    return LayoutNode(type="-", ratios=[], children=[], content_id=cid)


def _row(*children: LayoutNode, level=None) -> LayoutNode:
    n = LayoutNode(type="row", ratios=[1.0] * len(children), children=list(children))
    n.section_level = level
    return n


def _col(*children: LayoutNode, level=None) -> LayoutNode:
    n = LayoutNode(type="col", ratios=[1.0] * len(children), children=list(children))
    n.section_level = level
    return n


# node_index: l* are links, t* are texts, i* are images
IDX = {
    "l1": {"type": "link"},
    "l2": {"type": "link"},
    "l3": {"type": "link"},
    "t1": {"type": "text"},
    "t2": {"type": "text"},
    "i1": {"type": "image"},
    "c1": {"type": "inline_code"},
    "c2": {"type": "inline_code"},
    "k1": {"type": "key"},
    "v1": {"type": "value"},
    "s1": {"type": "segment"},
    "s2": {"type": "segment"},
    "e1": {"type": "emoji"},
}

LINK_ROW = _row(_leaf_node("l1"), _leaf_node("l2"))
LINK_ROW2 = _row(_leaf_node("l3"), _leaf_node("l1"))
MIXED_ROW = _row(_leaf_node("l1"), _leaf_node("t1"))
TEXT_ROW = _row(_leaf_node("t1"), _leaf_node("t2"))
TEXT_LEAF = _leaf_node("t1")
CODE_ROW = _row(_leaf_node("c1"), _leaf_node("c2"))
CODE_LINK_ROW = _row(_leaf_node("c1"), _leaf_node("l1"))
KEY_LEAF = _leaf_node("k1")
VALUE_GROUP = _row(_leaf_node("s1"), _leaf_node("s2"))
KEY_GROUP = _row(_leaf_node("k1"))  # e.g. key wrapper after splits


def _line_row(*cids: str) -> LayoutNode:
    n = _row(*[_leaf_node(c) for c in cids])
    n.line_split = True
    return n


def _in_line(*children: LayoutNode) -> LayoutNode:
    """A container holding one line block's content — the only place the
    pure-pill exception applies (``bake_render_cascade`` bakes ``gap_in_line``)."""
    n = _col(*children)
    n.line_split = True
    n.gap_in_line = True
    return n


IN_LINE = _in_line()  # container identity is all _sibling_gap reads
OUTSIDE = _col()  # a plain container: pill blocks there are separate elements


def _gap(a, b, axis="col", owner=0, container=IN_LINE):
    return _sibling_gap(a, b, _theme(), axis, owner, IDX, container)[0]


def test_leaf_vs_link_group():
    assert _gap(TEXT_LEAF, LINK_ROW, "col") == ELEMENT_COL
    assert _gap(LINK_ROW, TEXT_LEAF, "col") == ELEMENT_COL
    assert _gap(TEXT_LEAF, LINK_ROW, "row") == ELEMENT_ROW
    print("  ✓  leaf ↔ pure-link group → element spacing (both axes)")


def test_link_group_vs_link_group():
    assert _gap(LINK_ROW, LINK_ROW2, "col") == ELEMENT_COL
    assert _gap(LINK_ROW, LINK_ROW2, "row") == ELEMENT_ROW
    print("  ✓  pure-link group ↔ pure-link group → element spacing")


def test_pill_blocks_outside_a_line_block():
    # The same pairs, one line block away: two pill blocks that are separate
    # elements (two cards, a card and a heading leaf) keep them apart.
    assert _gap(LINK_ROW, LINK_ROW2, "col", container=OUTSIDE) == GROUP
    assert _gap(TEXT_LEAF, LINK_ROW, "col", container=OUTSIDE) == GROUP
    assert _gap(CODE_ROW, LINK_ROW, "row", container=OUTSIDE) == GROUP
    # No container at all (an unbaked caller) behaves like outside.
    assert _sibling_gap(LINK_ROW, LINK_ROW2, _theme(), "col", 0, IDX)[0] == GROUP
    print("  ✓  pill blocks outside a line block keep the group spacing")


def test_card_inside_a_line_block_counts_as_inside():
    # bake_render_cascade resolves the container flag: a line block, and a card
    # nested in one, hold "one line's content"; a plain col and a standalone
    # card do not.
    card_in_line = _col(LINK_ROW, LINK_ROW2)
    card_in_line.is_card = True
    line = _col(card_in_line)
    line.line_split = True
    lone_card = _col(LINK_ROW, LINK_ROW2)
    lone_card.is_card = True
    root = _col(line, lone_card, TEXT_LEAF)
    bake_render_cascade(root)
    assert root.gap_in_line is False
    assert line.gap_in_line is True
    assert card_in_line.gap_in_line is True, "card nested in a line block"
    assert lone_card.gap_in_line is False, "a card on its own is an element"
    assert _gap(LINK_ROW, LINK_ROW2, "col", container=card_in_line) == ELEMENT_COL
    assert _gap(LINK_ROW, LINK_ROW2, "col", container=lone_card) == GROUP
    print("  ✓  bake marks line blocks and cards inside them, nothing else")


def _run_row(run_id: int, *cids: str, card: bool = False) -> LayoutNode:
    n = _row(*[_leaf_node(c) for c in cids])
    n.flow_run = run_id
    n.is_card = card
    return n


def test_same_flow_run_rows_stay_together():
    # The rows ONE run wrapped onto: a pill run is spliced straight into the
    # parent (no wrapper), so only the shared id relates them.
    a, b = _run_row(1, "l1", "l2"), _run_row(1, "l3", "l1")
    assert _gap(a, b, "col", container=OUTSIDE) == ELEMENT_COL
    assert _gap(a, b, "row", container=OUTSIDE) == ELEMENT_ROW
    # Different runs, and a run row next to something with no id, stay apart.
    assert _gap(a, _run_row(2, "l3", "l1"), "col", container=OUTSIDE) == GROUP
    assert _gap(a, LINK_ROW, "col", container=OUTSIDE) == GROUP
    assert _gap(TEXT_LEAF, a, "col", container=OUTSIDE) == GROUP
    print("  ✓  rows of one flowed run keep the element gap; other runs don't")


def test_flow_run_cards_space_as_cards():
    # Glued wins, as for line blocks: a run of carded pieces keeps card spacing.
    a = _run_row(4, "l1", "l2", card=True)
    b = _run_row(4, "l3", "l1", card=True)
    assert _gap(a, b, "col", container=OUTSIDE) == GROUP
    assert _gap(a, _run_row(4, "l3", "l1"), "col", container=OUTSIDE) == GROUP
    print("  ✓  same-run CARDS still space as cards (glued wins)")


def test_generator_stamps_one_id_per_flowed_run():
    from md2ui.pipeline.layout_generator import LayoutGenerator

    def pill(label):
        d = _leaf(label, "one_word")
        d["type"] = "link"
        return d

    # Two separate pill runs, each long enough to wrap at 300px.
    run_a = [pill(f"AAAA{i:02d}") for i in range(6)]
    run_b = [pill(f"BBBB{i:02d}") for i in range(6)]
    ast = _ast(_group(_group(*run_a), _group(*run_b)))

    def measure_width(node, _emphasis=None):
        return len(node.content or "") * 10.0 or None

    layout = LayoutGenerator().generate(ast, 300.0, measure_width=measure_width)

    def walk(n):
        yield n
        for c in n.children:
            yield from walk(c)

    ids = [n.flow_run for n in walk(layout) if n.flow_run]
    assert ids, "wrapped pill rows must carry a run id"
    groups = {i: ids.count(i) for i in set(ids)}
    assert all(c >= 2 for c in groups.values()), groups
    assert len(groups) >= 2, f"each run gets its own id, got {groups}"
    # A run that fits on one row relates to nothing, so it stays unstamped.
    wide = LayoutGenerator().generate(ast, 4000.0, measure_width=measure_width)
    assert not [n for n in walk(wide) if n.flow_run], "single-row run unstamped"
    print("  ✓  generator stamps one id per flowed run, none when it fits")


def test_mixed_and_text_groups_unchanged():
    assert _gap(TEXT_LEAF, MIXED_ROW, "col") == GROUP
    assert _gap(MIXED_ROW, LINK_ROW, "col") == GROUP
    assert _gap(TEXT_ROW, TEXT_ROW, "col") == GROUP
    assert _gap(TEXT_LEAF, TEXT_ROW, "row") == GROUP
    print("  ✓  mixed / text groups keep the group spacing")


def test_nested_purity_and_empty():
    nested = _col(LINK_ROW, LINK_ROW2)  # col of link rows
    assert _is_pure_element_block(nested, IDX)
    assert _gap(TEXT_LEAF, nested, "col") == ELEMENT_COL
    empty = _row()
    assert not _is_pure_element_block(empty, IDX)
    assert _gap(TEXT_LEAF, empty, "col") == GROUP
    print("  ✓  nested link cols count as pure; empty containers do not")


def test_section_priority_intact():
    sec = _col(_leaf_node("t1"), level=2)
    assert _sibling_gap(sec, LINK_ROW, _theme(), "col", 2, IDX) == (
        SECTION,
        True,
    )
    print("  ✓  section boundaries still take section spacing")


def test_image_leaf_pairs_unchanged():
    # leaf↔leaf image logic is only reachable without a group side.
    g = _gap(_leaf_node("i1"), _leaf_node("t1"), "col")
    assert g == ELEMENT_COL  # an image beside text takes the element gap
    print("  ✓  image leaf pair logic untouched")


def test_key_vs_value_group():
    assert _gap(KEY_LEAF, VALUE_GROUP, "col") == ELEMENT_COL
    assert _gap(KEY_LEAF, VALUE_GROUP, "row") == ELEMENT_ROW
    assert _gap(KEY_GROUP, VALUE_GROUP, "col") == ELEMENT_COL
    # key ↔ value leaf stays element (leaf↔leaf path)
    assert _gap(KEY_LEAF, _leaf_node("v1"), "col") == ELEMENT_COL
    print("  ✓  key (leaf or all-key group) ↔ value → element spacing")


def test_value_group_without_key_unchanged():
    assert _gap(TEXT_LEAF, VALUE_GROUP, "col") == GROUP
    assert _gap(VALUE_GROUP, VALUE_GROUP, "col") == GROUP
    print("  ✓  value groups without a key side keep group spacing")


def _link_dict(label):
    d = _leaf(f"[{label}](/x)", "one_word")
    d["type"] = "link"
    return d


def test_inline_code_groups_count_as_pills():
    assert _gap(TEXT_LEAF, CODE_ROW, "col") == ELEMENT_COL
    assert _gap(CODE_ROW, LINK_ROW, "col") == ELEMENT_COL
    assert _gap(CODE_LINK_ROW, CODE_ROW, "row") == ELEMENT_ROW
    print("  ✓  inline_code / mixed-pill groups space like link groups")


def _code_dict(label):
    d = _leaf(f"`{label}`", "one_word")
    d["type"] = "inline_code"
    return d


def _key_dict(label):
    d = _leaf(f"**{label}**", "one_word")
    d["type"] = "key"
    return d


def test_generator_cell_gap_mirror():
    ast = _ast(
        _group(
            _group(*[_link_dict(f"L{i}") for i in range(3)]),
            _group(_link_dict("A"), _leaf("text", "one_word")),
            _group(_code_dict("x"), _code_dict("yy")),
        )
    )
    pure, mixed, codes = ast.children
    assert _is_pure_element_group(pure) and not _is_pure_element_group(mixed)
    assert _is_pure_element_group(codes)
    t = _theme()
    assert _cell_gap(pure, t, "row") == ELEMENT_ROW
    assert _cell_gap(pure, t, "col") == ELEMENT_COL
    assert _cell_gap(mixed, t, "row") == GROUP
    assert _cell_gap(codes, t, "col") == ELEMENT_COL
    print("  ✓  generator _cell_gap mirrors: pure-pill unit → element gap")


def test_line_split_any_adjacency():
    line = _line_row("s1", "s2")
    # one-sided: even a plain text GROUP neighbor gets the element gap
    assert _gap(line, TEXT_ROW, "col") == ELEMENT_COL
    assert _gap(TEXT_LEAF, line, "col") == ELEMENT_COL
    assert _gap(line, _line_row("t1", "s1"), "row") == ELEMENT_ROW
    print("  ✓  line_split blocks element-space ANY adjacency (one-sided)")


def test_carded_line_split_spaces_as_card():
    # glued wins: a line block that is also a card keeps GROUP spacing.
    card_line = _line_row("s1", "s2")
    card_line.is_card = True
    assert _gap(card_line, TEXT_LEAF, "col") == GROUP
    assert _gap(TEXT_LEAF, card_line, "col") == GROUP
    other_card = _line_row("t1", "s1")
    other_card.is_card = True
    assert _gap(card_line, other_card, "col") == GROUP
    # non-card line blocks still element-space one-sided
    assert _gap(_line_row("s1", "s2"), TEXT_ROW, "col") == ELEMENT_COL
    print("  ✓  carded line blocks keep card (group) spacing — glued wins")


def test_generator_glued_line_unit_mirror():
    def seg(label):
        d = _leaf(label, "one_word")
        d["type"] = "segment"
        return d

    glued_line = _group(seg("a"), seg("b"))
    glued_line["line_split_group"] = True
    glued_line["glued_content_group"] = True
    plain_line = _group(seg("c"), seg("d"))
    plain_line["line_split_group"] = True
    ast = _ast(_group(glued_line, plain_line))
    glued_unit, line_unit = ast.children
    t = _theme()
    assert _cell_gap(glued_unit, t, "col") == GROUP
    assert _cell_gap(line_unit, t, "col") == ELEMENT_COL
    print("  ✓  generator mirror: glued+line unit → group; plain line → element")


def test_generator_line_split_flagging():
    from md2ui.pipeline.layout_generator import LayoutGenerator

    def seg(label, type_="segment"):
        d = _leaf(label, "one_word")
        d["type"] = type_
        return d

    g = _group(*[seg(f"Piece{i:02d}xxxx") for i in range(6)])
    g["line_split_group"] = True
    ast = _ast(_group(g))

    def measure_line(node):
        return len((node.content or "")) * 10.0 or None

    gen = LayoutGenerator()
    wide = gen.generate(ast, 1280.0, measure_line=measure_line)
    narrow = gen.generate(ast, 300.0, measure_line=measure_line)

    def walk(n):
        yield n
        for c in n.children:
            yield from walk(c)

    wide_rows = [n for n in walk(wide) if n.line_split]
    assert wide_rows and all(n.type == "row" for n in wide_rows)
    narrow_flagged = [n for n in walk(narrow) if n.line_split]
    narrow_rows = [n for n in narrow_flagged if n.type == "row"]
    assert len(narrow_rows) >= 2, "wrapped line rows must all be flagged"
    assert any(n.type == "col" for n in narrow_flagged), "wrapper col flagged"
    # generator gap mirror on the AST unit
    assert _cell_gap(ast.children[0], _theme(), "col") == ELEMENT_COL
    print("  ✓  generator stamps line_split on rows/wrapper; _cell_gap mirrors")


def test_generator_key_unit_mirror():
    from md2ui.pipeline.generator_units import _is_key_unit

    ast = _ast(
        _group(
            _group(_key_dict("Colors"), _leaf("plain", "one_word")),
        )
    )
    kv = ast.children[0]
    key_leaf, value_leaf = kv.children
    t = _theme()
    assert _is_key_unit(key_leaf) and not _is_key_unit(value_leaf)
    assert _cell_gap(key_leaf, t, "col") == ELEMENT_COL
    assert _cell_gap(kv, t, "col") == GROUP  # mixed kv wrapper unchanged
    print("  ✓  generator _cell_gap mirrors: key unit → element gap")


TESTS = [
    test_leaf_vs_link_group,
    test_link_group_vs_link_group,
    test_pill_blocks_outside_a_line_block,
    test_card_inside_a_line_block_counts_as_inside,
    test_same_flow_run_rows_stay_together,
    test_flow_run_cards_space_as_cards,
    test_generator_stamps_one_id_per_flowed_run,
    test_mixed_and_text_groups_unchanged,
    test_nested_purity_and_empty,
    test_section_priority_intact,
    test_inline_code_groups_count_as_pills,
    test_key_vs_value_group,
    test_value_group_without_key_unchanged,
    test_line_split_any_adjacency,
    test_carded_line_split_spaces_as_card,
    test_generator_glued_line_unit_mirror,
    test_generator_line_split_flagging,
    test_generator_key_unit_mirror,
    test_image_leaf_pairs_unchanged,
    test_generator_cell_gap_mirror,
]

if __name__ == "__main__":
    print("Pure-Link-Group Spacing Tests")
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
