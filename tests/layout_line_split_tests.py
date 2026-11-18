"""
Unit tests for line-split flow: a group flagged ``line_split_group`` (its
children are the pieces of ONE source line — separator segments,
items, peeled emojis, datapoint splits) flows its children into rows at their
full single-line widths, wrapping only when the line is genuinely too long.
Images are line pieces too, except on a line that mixes one with prose — see
tests/image_row_tests.py; a decision source cannot break a line group's flow.
Run with: uv run layout_line_split_tests.py
"""

from layout_bento_tests import _ast, _group, _leaf
from md2ui.pipeline import render_measure as RMS
from md2ui.pipeline import render_place as RPL
from md2ui.pipeline import render_spacing as RSP
from layout_decision_scope_tests import RecordingGenerator, aside_theme
from md2ui.pipeline.layout_generator import LayoutGenerator


def _themed_fonts():
    """(theme, FontSet) as the renderer builds them from THEME.md — a flow test
    needs the real padding/spacing to be meaningful."""
    from pathlib import Path

    from md2ui.pipeline.layout_render import FontSet
    from md2ui.pipeline.theme import parse_theme
    from md2ui.utils.font_loader import (
        load_custom_fonts,
        resolve_typeface,
        weight_from_str,
    )

    theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    custom = load_custom_fonts(theme.font_paths)
    name = theme.text.font_name or "Arial"
    base_w = weight_from_str(theme.text.font_weight)

    def tf(weight, italic):
        return resolve_typeface(name, weight, italic, custom)

    # (regular, italic, bold, bold_italic) — the bold pair is what **x** inside
    # a heading draws with, mirroring main()'s resolution.
    headings = {
        lvl: (
            tf(weight_from_str(ts.font_weight), False),
            tf(weight_from_str(ts.font_weight), True),
            tf(max(weight_from_str(ts.font_weight), 700), False),
            tf(max(weight_from_str(ts.font_weight), 700), True),
        )
        for lvl, ts in theme.headings.items()
    }
    return theme, FontSet(
        tf(base_w, False),
        tf(700, False),
        tf(base_w, True),
        tf(700, True),
        tf(base_w, False),
        None,
        headings,
    )


def _piece(content: str, type_: str) -> dict:
    d = _leaf(content, "one_word")
    d["type"] = type_
    return d


def _line_group(*pieces: dict, **flags) -> dict:
    d = _group(*pieces)
    d["line_split_group"] = True
    d.update(flags)
    return d


def _doc(*groups: dict):
    """One h2 section wrapping the given groups (mirrors fixture shape)."""
    return _ast(
        _group(
            _group(
                _leaf("Second level heading", "very_short"),
                *groups,
                heading_group=True,
                heading_level=2,
            )
        )
    )


def _fake_measure_line(node):
    """Full single-line width: 10px/char of content (markers stripped)."""
    if node.type in ("image", "horizontal_rule"):
        return None
    text = (node.content or "").replace("*", "").replace("`", "")
    return len(text) * 10.0 or None


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def _leaves(n):
    return [x.content_id for x in _walk(n) if x.type == "-"]


def _flow_rows_of(layout):
    return [
        n
        for n in _walk(layout)
        if n.type == "row"
        and not n.grid
        and not n.bento
        and n.children
        and all(c.type == "-" for c in n.children)
    ]


def _gen(ast, width, **kw):
    return LayoutGenerator().generate(ast, width, measure_line=_fake_measure_line, **kw)


def test_separator_split_flows_one_row():
    # Jan • Feb • Mar — text/bullet_point interleave (no repeated runs).
    g = _line_group(
        _piece("Jan", "text"),
        _piece("•", "bullet_point"),
        _piece("Feb", "text"),
        _piece("•", "bullet_point"),
        _piece("Mar", "text"),
    )
    layout = _gen(_doc(g), 1280.0)
    rows = _flow_rows_of(layout)
    assert len(rows) == 1 and len(rows[0].children) == 5, (
        f"expected one 5-piece row, got {[len(r.children) for r in rows]}"
    )
    print("  ✓  Jan • Feb • Mar flows as one row of 5 pieces")


def test_emoji_peel_flows():
    g = _line_group(_piece("🗓", "emoji"), _piece("**Calendar**", "text"))
    layout = _gen(_doc(g), 1280.0)
    rows = _flow_rows_of(layout)
    assert len(rows) == 1 and len(rows[0].children) == 2
    print("  ✓  peeled emoji + text share one row")


def test_uniform_segments_flow_despite_repeated_run():
    # Uniform segment leaves form a repeated run — line flow must win over
    # the _build_grouped stack/grid path.
    g = _line_group(*[_piece(w, "segment") for w in ("Cat", "Dog", "Fish", "Snake")])
    layout = _gen(_doc(g), 1280.0)
    rows = _flow_rows_of(layout)
    assert len(rows) == 1 and len(rows[0].children) == 4
    assert not any(n.grid for n in _walk(layout)), "line pieces must not grid"
    print("  ✓  uniform segments flow in one row (beats repeated-run handling)")


def test_datapoint_split_flows():
    g = _line_group(
        _piece("**9:00 AM - 9:15 AM**", "datapoint"),
        _piece("**Opening Remarks**", "segment"),
    )
    layout = _gen(_doc(g), 1280.0)
    rows = _flow_rows_of(layout)
    assert len(rows) == 1 and len(rows[0].children) == 2
    print("  ✓  datapoint + segment (pipe split) share one row")


def test_narrow_width_wraps_in_order():
    pieces = [_piece(f"Segment{i:02d}xxxx", "segment") for i in range(6)]  # 140px each
    g = _line_group(*pieces)
    ast = _doc(g)
    ids = [n.node_id for n in _walk(ast) if n.type == "segment"]
    layout = _gen(ast, 300.0)  # 2 per row at 140+gap0
    rows = _flow_rows_of(layout)
    assert len(rows) >= 2, "narrow width should wrap into multiple rows"
    got = [i for i in _leaves(layout) if i in set(ids)]
    assert got == ids, "piece order changed while wrapping"
    assert len(set(_leaves(layout))) == len(_leaves(layout))
    print(f"  ✓  narrow width wraps ({[len(r.children) for r in rows]}), order kept")


def test_image_line_group_flows():
    g = _line_group(_piece("![i](/img.png)", "image"), _piece("caption", "text"))
    layout = _gen(_doc(g), 1280.0)
    rows = _flow_rows_of(layout)
    assert rows, "an image line group must flow like any other line group"
    assert any(len(r.children) == 2 for r in rows), (
        f"image and caption must share one row, got {[len(r.children) for r in rows]}"
    )
    print("  ✓  line group containing an image flows as one row")


def _emoji_piece(emoji: str, label: str) -> dict:
    """An emoji-peeled pipe-split piece: segment sub-group [emoji, segment]."""
    d = _group(_piece(emoji, "emoji"), _piece(label, "segment"))
    d["type"] = "segment"
    d["line_split_group"] = True
    return d


def _tags_doc(labels: list[str]):
    """Replica of `⭐ Popular | 🚀 ... `: plain outer group (finalize cleared
    its flag) holding repeated line-split segment sub-groups."""
    outer = _group(*[_emoji_piece("⭐", lbl) for lbl in labels])
    return _doc(outer)


def test_line_group_run_flows_not_grids():
    ast = _tags_doc(["Popular", "enterpreunership", "science", "food", "life"])
    ids = [n.node_id for n in _walk(ast) if not n.children and n.content]
    layout = _gen(ast, 1280.0)
    assert not any(getattr(n, "grid", False) for n in _walk(layout)), (
        "line-split sub-group run must flow, not grid"
    )
    rows = [
        n
        for n in _walk(layout)
        if n.type == "row" and n.line_split and len(n.children) > 1
    ]
    assert rows, "pieces did not flow into rows"
    got = [i for i in _leaves(layout) if i in set(ids)]
    assert got == ids, "piece order changed"
    print("  ✓  run of line-split sub-groups flows at natural widths (no grid)")


def test_line_group_run_wraps_narrow():
    ast = _tags_doc([f"LongLabel{i:02d}xx" for i in range(6)])  # ~150px pieces
    layout = _gen(ast, 340.0)
    # Wrapped into multiple flow rows of piece sub-groups, never a grid.
    piece_rows = [
        n
        for n in _walk(layout)
        if n.type == "row" and n.line_split and any(c.children for c in n.children)
    ]
    assert len(piece_rows) >= 2, "expected the piece run to wrap"
    assert not any(getattr(n, "grid", False) for n in _walk(layout))
    ids = [n.node_id for n in _walk(ast) if not n.children and n.content]
    got = [i for i in _leaves(layout) if i in set(ids)]
    assert got == ids
    print("  ✓  narrow width wraps the piece run, order preserved")


def test_line_item_width_groups():
    from md2ui.pipeline.layout_generator import LayoutGenerator
    from md2ui.pipeline.theme import Theme

    gen = LayoutGenerator()
    t = Theme()
    t.elements.row_spacing = 8.0
    gen._theme = t
    gen._measure_line = _fake_measure_line
    ast = _tags_doc(["Popular"])
    piece = next(n for n in _walk(ast) if n.children and n.line_split_group)
    # emoji '⭐' (1 char → 10) + gap 8 + 'Popular' (7 chars → 70) = 88
    assert gen._line_item_width(piece) == 88.0
    print("  ✓  _line_item_width sums a group piece's children + gaps")


def test_line_item_width_reserves_the_pieces_own_padding():
    """A piece is rendered into exactly the width measured here, and a glued
    card then carves its padding out of it — so the padding has to be in the
    measurement, or the piece's own children come up short and wrap."""
    from md2ui.pipeline.layout_generator import LayoutGenerator
    from md2ui.pipeline.generator_units import _unit_padding_x
    from md2ui.pipeline.theme import Theme

    gen = LayoutGenerator()
    t = Theme()
    t.elements.row_spacing = 8.0
    t.elements.padding.left = t.elements.padding.right = 16.0
    gen._theme = t
    gen._measure_line = _fake_measure_line
    ast = _tags_doc(["Popular"])
    piece = next(n for n in _walk(ast) if n.children and n.line_split_group)
    piece.glued_content_group = True  # a card: it carves padding when rendered
    pad = _unit_padding_x(piece, t)
    assert pad > 0, "fixture must be a padded card for this to mean anything"
    assert gen._line_item_width(piece) == 88.0 + pad
    print(f"  ✓  _line_item_width includes the piece's own padding (+{pad:.0f})")


def test_line_item_width_maxes_a_stacking_piece():
    """A piece that STACKS is as wide as its widest child, not the sum.

    `14:30 : LHR : London` is a colon column — the renderer lays it out as a
    `col`, so `natural_width` gives it `max(children)`. A sum would wrap the
    line early and leave the card half empty.
    """
    from md2ui.pipeline.layout_generator import LayoutGenerator
    from md2ui.pipeline.theme import Theme

    gen = LayoutGenerator()
    t = Theme()
    t.elements.row_spacing = 8.0
    gen._theme = t
    gen._measure_line = _fake_measure_line
    ast = _tags_doc(["Popular"])
    piece = next(n for n in _walk(ast) if n.children and n.line_split_group)
    flowed = gen._line_item_width(piece)
    # The SAME piece, now a stacking one: same children, widest child only.
    piece.line_split_group = False
    piece.column_split_group = True
    stacked = gen._line_item_width(piece)
    assert stacked == 70.0, stacked  # max('⭐' 10, 'Popular' 70)
    assert flowed == 88.0 and stacked < flowed, (flowed, stacked)
    print(f"  ✓  _line_item_width maxes a stacking piece ({flowed} → {stacked})")


def test_line_item_width_survives_without_a_theme():
    """The measurer-less / theme-less path: the stacking branch must not need
    either (hand-built fixtures run this way)."""
    from md2ui.pipeline.layout_generator import LayoutGenerator

    gen = LayoutGenerator()
    ast = _tags_doc(["Popular"])
    piece = next(n for n in _walk(ast) if n.children and n.line_split_group)
    piece.line_split_group = False
    piece.column_split_group = True
    assert gen._line_item_width(piece) > 0
    print("  ✓  a stacking piece measures with no theme and no measurer")


def test_line_measurer_sees_the_authored_tier():
    """`make_line_width_measurer` must resolve `___x___` at its Display size.

    Without `text_style` on its synthetic node every tier measures at the BODY
    size, and a Display piece clips mid-word.
    """
    from md2ui.pipeline.layout_render import (
        make_line_width_measurer,
        make_width_measurer,
    )

    theme, fonts = _themed_fonts()
    measure_line = make_line_width_measurer(fonts, theme)
    measure_word = make_width_measurer(fonts, theme)

    def _dp(text_style):
        node = next(
            n
            for n in _walk(_ast(_group(_piece("300m", "datapoint"))))
            if n.type == "datapoint"
        )
        node.text_style = text_style
        return node

    plain, display = _dp(None), _dp("display")
    body_w, display_w = measure_line(plain), measure_line(display)
    word_w = measure_word(display)
    assert body_w and display_w and word_w, (body_w, display_w, word_w)
    assert display_w > body_w * 1.5, (body_w, display_w)
    # …and it agrees with the min-unbreakable measurer, which already threads
    # the tier — one word, so the two must land on the same number.
    assert abs(display_w - word_w) < 0.5, (display_w, word_w)
    print(f"  ✓  the line measurer sees the tier ({body_w:.1f} → {display_w:.1f})")


def test_glued_line_run_rows_not_stamped():
    # Run of glued+line_split card pieces (📂 Folder name / ↗️ +3 points):
    # the emitted run row must NOT carry line_split — it holds cards and
    # spaces like a card row (glued wins).
    pieces = []
    for lbl in ("Folder name", "points up", "third one"):
        d = _emoji_piece("📂", lbl)
        d["glued_content_group"] = True
        pieces.append(d)
    ast = _doc(_group(*pieces))
    layout = _gen(ast, 1280.0)
    run_rows = [
        n
        for n in _walk(layout)
        if n.type == "row" and any(c.children for c in n.children)
    ]
    assert run_rows, "carded pieces did not flow into a row"
    assert not any(n.line_split for n in run_rows), (
        "run row of cards must not be line_split-stamped"
    )
    print("  ✓  run rows of carded line pieces are not line_split (glued wins)")


def test_card_group_runs_still_grid():
    cards = [
        _group(_piece(f"**K{i}**", "key"), _piece(f"${i}", "datapoint"))
        for i in range(4)
    ]
    ast = _doc(*[c for c in cards])
    # cards are plain groups (no line_split flag) sharing a fingerprint
    layout = _gen(ast, 1280.0)
    assert any(getattr(n, "grid", False) for n in _walk(layout)), (
        "non-line-split group runs must keep gridding"
    )
    print("  ✓  ordinary repeated group runs still grid")


def test_line_group_flow_survives_an_aside_source():
    """A line_split_group is consulted like any other group, but the same-line
    flow must survive.

    Same-line arrangement is the author's, written in the source. The aside's
    own eligibility enforces it: an icon aside refuses a line group, so a run of
    text pieces falls back to the flow.
    """
    g = _line_group(
        _piece("Jan", "text"),
        _piece("•", "bullet_point"),
        _piece("Feb", "text"),
        glued_content_group=True,
    )
    gen = RecordingGenerator()
    layout = gen.generate(
        _doc(g), 1280.0, theme=aside_theme(), measure_line=_fake_measure_line
    )
    assert any(n.line_split_group for n in gen.consulted), (
        "line_split groups are consulted now"
    )
    rows = _flow_rows_of(layout)
    assert rows and len(rows[0].children) == 3, (
        f"same-line flow broken by an aside decision: {rows}"
    )
    print("  ✓  line_split group consulted, same-line flow intact")


def test_no_measure_line_fallback():
    g = _line_group(*[_piece(w, "segment") for w in ("Aa", "Bb", "Cc")])
    layout = LayoutGenerator().generate(_doc(g), 1280.0)  # category widths
    rows = _flow_rows_of(layout)
    assert rows and len(rows[0].children) == 3
    # And a plain (non-line) group of texts still stacks.
    plain = _group(_piece("one", "text"), _piece("two", "text"))
    layout2 = LayoutGenerator().generate(_doc(plain), 1280.0)
    assert not _flow_rows_of(layout2), "plain text group must keep stacking"
    print("  ✓  measure_line=None fallback flows; plain groups still stack")


def test_same_line_doc_renders_one_row_per_line():
    """End-to-end over the same-line regression doc: every source line
    lands on ONE visual row, except `Key: value` (which renders the key above
    its value by design) and a line too long for the page, which flows and
    wraps "only when the line is genuinely too long" (the footer's thirteen
    links). Asserts the rendered geometry, not the flag — a line can also flow
    via the pill or repeated-run path."""
    from markdown_datapoint_split_tests import _processed_with_criteria

    from md2ui.pipeline import layout_render as LR

    theme, fonts = _themed_fonts()
    ast = _processed_with_criteria(
        open("data/markdown/tests/tests-same-line-split.md").read()
    )
    node_index: dict = {}
    LR._walk(ast.to_dict(), node_index)
    width = LR._content_width(1024.0)
    layout = LayoutGenerator().generate(
        ast,
        width,
        theme,
        measure=LR.make_layout_measurer(node_index, fonts, theme),
        measure_width=LR.make_width_measurer(fonts, theme),
        measure_line=LR.make_line_width_measurer(fonts, theme),
        measure_marker=LR.make_marker_measurer(fonts, theme),
    )
    RPL.bake_render_cascade(layout)
    height = RMS.natural_height(layout, width, node_index, fonts, theme)
    lines: dict = {}
    for b in RPL.place_boxes(
        layout, 0, 0, width, height, node_index, fonts, theme, section_boxes=[]
    ):
        nd = node_index.get(b.content_id) if b.content_id else None
        if not nd or nd.get("source_line_id") is None:
            continue
        lines.setdefault(nd["source_line_id"], []).append(
            (b.y, b.y + b.height, (nd.get("content") or "")[:18], b.width)
        )

    def rows_of(pieces):
        # After baseline alignment, one row's cells no longer share a y — a
        # visual row is a set of vertically OVERLAPPING boxes.
        rows, cur = [], []
        for p in sorted(pieces):
            if cur and p[0] < max(c[1] for c in cur) - 1.0:
                cur.append(p)
            else:
                if cur:
                    rows.append(cur)
                cur = [p]
        if cur:
            rows.append(cur)
        return rows

    KV = (
        "Widths",
        "Balance",
        "Customers",
        "Server-side",
        "Monthly Budget",
        "Discovering Mexi",
        "Value heading",
    )

    # A spaced-colon COLUMN split stacks by design too — that is the whole point
    # of " : ". Collected structurally rather than by content: the flag is the
    # fact, a substring match would just be another allow-list to maintain.
    def stacked_line_ids(n, out=None):
        out = set() if out is None else out
        if n.column_split_group and n.source_line_id is not None:
            out.add(n.source_line_id)
        for c in n.children:
            stacked_line_ids(c, out)
        return out

    columned = stacked_line_ids(ast)
    broken = []
    for slid, pieces in sorted(lines.items()):
        if len(pieces) < 2 or slid in columned:
            continue
        label = " ".join(p[2] for p in pieces)
        if any(k in label for k in KV):
            continue  # Key: value stacks by design
        if sum(p[3] for p in pieces if p[2]) > width:
            continue  # wider than the page even without its gaps: it wraps
        n = len(rows_of(pieces))
        if n > 1:
            broken.append(f"{n} rows: {label[:46]}")
    assert not broken, "lines split across rows:\n   " + "\n   ".join(broken)
    print("  ✓  same-line doc: every line on one row (Key: value, overflow aside)")


def _doc_height(src: str) -> float:
    """Natural height of *src* laid out at 700px with the real THEME.md."""
    from markdown_datapoint_split_tests import _processed_with_criteria

    from md2ui.pipeline import layout_render as LR

    theme, fonts = _themed_fonts()
    ast = _processed_with_criteria(src)
    node_index: dict = {}
    LR._walk(ast.to_dict(), node_index)
    width = LR._content_width(700.0)
    layout = LayoutGenerator().generate(
        ast,
        width,
        theme,
        measure=LR.make_layout_measurer(node_index, fonts, theme),
        measure_width=LR.make_width_measurer(fonts, theme),
        measure_line=LR.make_line_width_measurer(fonts, theme),
        measure_marker=LR.make_marker_measurer(fonts, theme),
    )
    RPL.bake_render_cascade(layout)
    return RMS.natural_height(layout, width, node_index, fonts, theme)


def test_content_break_costs_no_vertical_space():
    # A `___` break is structural, not visual: it cuts the run of siblings but
    # the boundary keeps the ONE gap it would have had. A zero-height node
    # otherwise takes a gap on each side and the boundary is spaced twice.
    a, b = "key: one | key: one", "key: three | key: three"
    plain = _doc_height(f"{a}\n\n{b}")
    assert _doc_height(f"{a}\n\n___\n\n{b}") == plain
    # A RUN of breaks collapses to the same one boundary…
    assert _doc_height(f"{a}\n\n___\n\n___\n\n{b}") == plain
    # …and one that opens the document has nothing before it to space against.
    assert _doc_height(f"___\n\n{a}\n\n{b}") == plain
    print("  ✓  a '___' break adds no height, however many, wherever placed")


def test_painted_rule_still_takes_its_gaps():
    # The difference between the two break leaves: a visible rule wants the
    # breathing room, so it must NOT be collapsed the way `_` is.
    a, b = "key: one | key: one", "key: three | key: three"
    assert _doc_height(f"{a}\n\n---\n\n{b}") > _doc_height(f"{a}\n\n{b}")
    print("  ✓  a '---' rule keeps its gaps on both sides")


def _top_gaps(src: str, theme=None, fonts=None) -> list[float]:
    """The col gap at each top-level boundary of *src*, laid out at 700px."""
    from markdown_datapoint_split_tests import _processed_with_criteria

    from md2ui.pipeline import layout_render as LR

    if theme is None:
        theme, fonts = _themed_fonts()
    assert fonts is not None
    ast = _processed_with_criteria(src)
    node_index: dict = {}
    LR._walk(ast.to_dict(), node_index)
    width = LR._content_width(700.0)
    layout = LayoutGenerator().generate(
        ast,
        width,
        theme,
        measure=LR.make_layout_measurer(node_index, fonts, theme),
        measure_width=LR.make_width_measurer(fonts, theme),
        measure_line=LR.make_line_width_measurer(fonts, theme),
        measure_marker=LR.make_marker_measurer(fonts, theme),
    )
    RPL.bake_render_cascade(layout)
    col = layout.children[0]
    return [
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


_BLOCK_ROW_DOC = (
    "key : $10,000 | key : $10,000\n\n"
    "450 : ___Project done___ | 35 : ___Happy users___\n\n"
    "key : value 1 | key : value 2\n"
)


def test_a_line_of_blocks_takes_the_group_gap():
    # A `line_split` block element-spaces any adjacency because a line of WORDS
    # reads as one element. A line whose every piece is a colon column is a group
    # of groups instead, and must not sit flush against the cards around it.
    theme, _ = _themed_fonts()
    assert _top_gaps(_BLOCK_ROW_DOC) == [
        theme.elements.group_col_spacing,
        theme.elements.group_col_spacing,
    ]
    print("  ✓  a row of colon columns spaces as a group, not as a line")


def test_a_line_of_words_still_takes_the_element_gap():
    theme, _ = _themed_fonts()
    el = theme.elements.col_spacing
    # A leaf-ish line, and prose that merely CONTAINS a `Key: value` fragment —
    # both are still lines of words and must stay tight to their neighbours.
    assert _top_gaps("Intro line\n\n📂 Folder name\n\nOutro line") == [el, el]
    assert _top_gaps(
        "Intro line\n\nThis directly | Key: value | otherwise the\n\nOutro line"
    ) == [el, el]
    print("  ✓  a line of words keeps the element gap, KV fragment or not")


def test_block_line_spacing_does_not_depend_on_the_theme():
    # The test reads the GROUPER's pieces, never the laid-out row — that row also
    # holds the cells ## Separators inserts, so testing it would make the gap
    # depend on whether ` | ` is drawn.
    import copy

    drawn, fonts = _themed_fonts()
    plain = copy.deepcopy(drawn)
    plain.separators.bar = False
    plain.vertical_rule.draw = False
    drawn.separators.bar = True
    drawn.vertical_rule.draw = True
    assert _top_gaps(_BLOCK_ROW_DOC, plain, fonts) == _top_gaps(
        _BLOCK_ROW_DOC, drawn, fonts
    )
    print("  ✓  the block-line gap is the same drawn or hidden")


# A line nested in another line is built at exactly the width it asked for, so
# the ask has to be what the line's own flow needs, or the line wraps and its
# pieces stack.
_BADGE_LINE = "- *🛍️* - **Name** : Feb 04 ... `-$199.00` : Subscription\n"
_SPACER_LINE = (
    "___CONFIG___ +++++ Join Config June 24-25. Virtual is always free."
    " ... [Register](/r)\n"
)
_DRAWN_SEP_LINE = "- *🛍️* - Alpha | Beta | Gamma ... `-$199.00`\n"


def _built(src: str, width: float, bar: bool = False):
    """(generator, root, layout) for *src* through the real pipeline, with the
    fixture theme (drawing ` | ` when *bar*) — the generator keeps its
    measurers after generate()."""
    from pathlib import Path

    from md2ui import session

    theme = session.load_theme(Path("data/markdown/tests/THEME.md"))
    theme.separators.bar = bar
    fonts = session.load_fonts(theme)
    ast = session.group_markdown(src, session.load_grouping_kit())
    assert ast is not None
    root, idx = session.prepare(ast, theme)
    gen = LayoutGenerator()
    scene = session.build_scene(gen, root, idx, theme, fonts, width)
    return gen, root, scene.layout


def _nested_lines(root):
    """Every flowed line that is itself a piece of an enclosing line."""
    return [
        c
        for n in _walk(root)
        if n.line_split_group
        for c in n.children
        if c.children and c.line_split_group
    ]


def _fits_in_its_ask(gen, line) -> bool:
    """Whether *line*, handed exactly the width it asks for, flows on one row."""
    from md2ui.pipeline.generator_units import _unit_padding_x

    ask = gen._line_item_width(line) - _unit_padding_x(line, gen._theme)
    # More than one row comes back as a `col` of them.
    return gen._flow_line_group(line, ask).type != "col"


def _stacked_lines(layout) -> int:
    return sum(1 for n in _walk(layout) if n.type == "col" and n.line_split)


def test_line_ask_counts_the_group_gap_beside_a_block():
    # A badge beside a ` : ` stack: the renderer spaces a leaf and a block with
    # the GROUP gap, so the line must ask for it, not for the element gap.
    gen, root, layout = _built(_BADGE_LINE, 767)
    theme = gen._theme
    assert theme is not None
    group = theme.elements.group_row_spacing or 0.0
    assert group != theme.elements.row_spacing
    (line,) = _nested_lines(root)
    badge, block = line.children
    assert block.column_split_group and not badge.children
    expected = gen._line_item_width(badge) + group + gen._line_item_width(block)
    assert abs(gen._line_item_width(line) - expected) < 1e-6
    assert _fits_in_its_ask(gen, line)
    assert _stacked_lines(layout) == 0, "the badge stacked above its name"
    print("  ✓  a line asks for the group gap beside a block, and stays one row")


def test_line_ask_counts_an_inline_spacer():
    # `+++++` between two pieces is a cell of the flow; the ask must count it.
    gen, root, layout = _built(_SPACER_LINE, 900)
    (line,) = _nested_lines(root)
    pieces = gen._with_separators(line)
    spacers = [p for p in pieces if p.separator_kind == "spacer"]
    assert len(spacers) == 1 and len(pieces) == len(line.children) + 1
    assert gen._line_item_width(line) > sum(gen._line_item_width(c) for c in pieces)
    assert _fits_in_its_ask(gen, line)
    assert _stacked_lines(layout) == 0, "the text went under the spacer's left"
    print("  ✓  a line asks for its inline spacer, and stays one row")


def test_line_ask_counts_drawn_separators():
    # With `Bar: show` each ` | ` is drawn: each glyph is a cell of the flow,
    # with a gap on either side, and the ask must hold them all.
    gen, root, layout = _built(_DRAWN_SEP_LINE, 767, bar=True)
    theme = gen._theme
    assert theme is not None and theme.separators.bar
    line = next(ln for ln in _nested_lines(root) if ln.separator_chars)
    pieces = gen._with_separators(line)
    glyphs = [p for p in pieces if p.separator_kind == "glyph"]
    assert len(glyphs) == line.separator_chars.count("|") >= 2
    kids = line.children
    gap = theme.elements.row_spacing or 0.0
    flat = sum(gen._line_item_width(c) for c in kids) + gap * (len(kids) - 1)
    assert gen._line_item_width(line) > flat + sum(
        gen._line_item_width(g) for g in glyphs
    )
    assert _fits_in_its_ask(gen, line)
    assert _stacked_lines(layout) == 0
    print("  ✓  a line asks for its drawn separators, and stays one row")


def test_line_ask_equals_flow_need():
    # The invariant the three above are cases of: every nested line, handed its
    # own ask, flows on one row — whatever its pieces are.
    for src, width in ((_BADGE_LINE, 767), (_SPACER_LINE, 900), (_DRAWN_SEP_LINE, 767)):
        gen, root, _ = _built(src, width)
        lines = _nested_lines(root)
        assert lines, src
        for line in lines:
            assert _fits_in_its_ask(gen, line), src
    print("  ✓  a nested line fits on one row at exactly its own ask")


TESTS = [
    test_line_ask_counts_the_group_gap_beside_a_block,
    test_line_ask_counts_an_inline_spacer,
    test_line_ask_counts_drawn_separators,
    test_line_ask_equals_flow_need,
    test_a_line_of_blocks_takes_the_group_gap,
    test_a_line_of_words_still_takes_the_element_gap,
    test_block_line_spacing_does_not_depend_on_the_theme,
    test_content_break_costs_no_vertical_space,
    test_painted_rule_still_takes_its_gaps,
    test_separator_split_flows_one_row,
    test_emoji_peel_flows,
    test_uniform_segments_flow_despite_repeated_run,
    test_datapoint_split_flows,
    test_narrow_width_wraps_in_order,
    test_image_line_group_flows,
    test_line_group_run_flows_not_grids,
    test_line_group_run_wraps_narrow,
    test_line_item_width_groups,
    test_line_item_width_reserves_the_pieces_own_padding,
    test_line_item_width_maxes_a_stacking_piece,
    test_line_item_width_survives_without_a_theme,
    test_line_measurer_sees_the_authored_tier,
    test_glued_line_run_rows_not_stamped,
    test_card_group_runs_still_grid,
    test_line_group_flow_survives_an_aside_source,
    test_no_measure_line_fallback,
    test_same_line_doc_renders_one_row_per_line,
]

if __name__ == "__main__":
    print("Line-Split Flow Tests")
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
