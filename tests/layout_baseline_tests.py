"""
Unit tests for vertical alignment inside a same-line row: the cells of one
source line share a text baseline instead of all hanging from the row's top
edge, so a big number and the small text beside it sit on the same line. A col
cell STACKS, so it has no single line to offer — it centers on the row's text
band instead. Rows that are NOT one source line (a grid of cards, a
gutter-marker row) keep top alignment, and an explicit content_valign still
wins. The THEME's `Line align` picks the mode: Top / Baseline / Center /
Bottom.
Run with: uv run python tests/layout_baseline_tests.py
"""

import dataclasses

import skia
from md2ui.pipeline.render_measure import LINE_SCALE, _layout_row, _leaf_natural_width
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.render_measure import (
    _leaf_first_baseline,
    _leaf_height,
    _row_valign_offsets,
    first_baseline,
)
from md2ui.pipeline.render_style import _code_size
from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.theme import Theme
from md2ui.utils.font_loader import make_font

IDX = {
    "t1": {"type": "text", "content": "some body text"},
    "t2": {"type": "text", "content": "and more body text"},
    "wrap": {"type": "text", "content": " ".join(["word"] * 40)},
    "dp": {"type": "datapoint", "content": "$412M"},
    "code": {"type": "inline_code", "content": "`npm run build`"},
    "img": {"type": "image", "content": "![a](u.png)"},
    "rule": {"type": "horizontal_rule", "content": "---"},
    "date": {"type": "text", "content": "Aug 12"},
}


def _fonts() -> FontSet:
    tf = skia.Typeface.MakeDefault()
    return FontSet(tf, tf, tf, tf, tf)


def _kv_theme() -> Theme:
    """A theme whose ``Value`` block is twice the body size.

    These tests need one cell taller than the one beside it; a K-V value is the
    cheapest way to get one from a render property alone. A bare ``Theme()``
    will not do it — with no ``Value`` block a value is ordinary body text, by
    design.
    """
    t = Theme()
    t.value_style = dataclasses.replace(
        t.text, font_size=t.text.font_size * 2.0, font_weight="bold"
    )
    return t


def _leaf(cid: str | None, **rp) -> LayoutNode:
    """A leaf cell. ``cid=None`` is a BAKED leaf — no markdown node behind it,
    everything it needs carried in its render properties (a switched-off date
    chip, a gutter marker)."""
    return LayoutNode(
        type="-",
        ratios=[],
        children=[],
        content_id=cid,
        render_properties=rp or None,
    )


def _row(*children: LayoutNode, line_split: bool = True, **rp) -> LayoutNode:
    n = LayoutNode(
        type="row",
        ratios=[1.0] * len(children),
        children=list(children),
        render_properties=rp or None,
    )
    n.line_split = line_split
    return n


def _group(kind: str, *children: LayoutNode) -> LayoutNode:
    """A GROUP cell — children, no content. ``col`` stacks, ``row`` flows."""
    return LayoutNode(type=kind, ratios=[1.0] * len(children), children=list(children))


def _place(row: LayoutNode, width: float = 600.0):
    return _layout_row(row, width, IDX, _fonts(), _kv_theme())


# ---------------------------------------------------------------------------
# _leaf_first_baseline — one per drawer
# ---------------------------------------------------------------------------


def test_text_baseline_is_the_font_size():
    """draw_styled_text_box draws at box.y + size (NOT at the ascent), so the
    baseline is the font size below the box top."""
    t = Theme()
    base = _leaf_first_baseline(IDX["t1"], _fonts(), t, None)
    assert base == t.text.font_size, base
    print(f"  ✓  body text baseline = font size ({base:.1f}px)")


def test_kv_value_baseline_follows_the_bigger_size():
    t = _kv_theme()
    plain = _leaf_first_baseline(IDX["dp"], _fonts(), t, None)
    valued = _leaf_first_baseline(IDX["dp"], _fonts(), t, {"kv_role": "value"})
    assert plain is not None
    assert valued is not None
    assert valued > plain, (plain, valued)
    print(f"  ✓  a Value leaf's baseline scales up ({plain:.1f} → {valued:.1f})")


def test_inline_code_baseline_includes_its_pill_padding():
    t = Theme()
    # Through _code_size, as the code under test measures: the base chip size is
    # a module global that loading a theme rewrites, so a copy imported by name
    # goes stale the moment another test loads a theme with its own chip size.
    m = make_font(_fonts().mono, _code_size(t, None)).getMetrics()
    base = _leaf_first_baseline(IDX["code"], _fonts(), t, None)
    assert abs(base - (t.inline_code.padding.top - m.fAscent)) < 1e-6, base
    print(f"  ✓  inline code baseline = pad.top + ascent ({base:.1f}px)")


def test_no_baseline_for_image_rule_or_bar():
    t, f = Theme(), _fonts()
    assert _leaf_first_baseline(IDX["img"], f, t, None) is None
    assert _leaf_first_baseline(IDX["rule"], f, t, None) is None
    assert _leaf_first_baseline(IDX["t1"], f, t, {"datapoint_bar": {}}) is None
    assert _leaf_first_baseline(None, f, t, {"list_marker": {}}) is None
    print("  ✓  image / rule / bar / marker have no baseline to align to")


def test_a_baked_date_leaf_measures_like_the_text_it_is():
    """`### Dates → Enabled: no` bakes a date back into ONE leaf that carries
    `date_text` and NO markdown node, so every leaf path has to resolve it
    through `_baked_date_node`, height and baseline included: the box is one
    LINE tall, not `font_size`, so the descender of `Aug 12` is not sheared."""
    t, f, rp = Theme(), _fonts(), {"date_text": "Aug 12"}
    for name, baked, real in (
        (
            "height",
            _leaf_height(None, 300.0, f, t, rp),
            _leaf_height(IDX["date"], 300.0, f, t, None),
        ),
        (
            "baseline",
            _leaf_first_baseline(None, f, t, rp),
            _leaf_first_baseline(IDX["date"], f, t, None),
        ),
        (
            "width",
            _leaf_natural_width(None, 300.0, f, t, rp),
            _leaf_natural_width(IDX["date"], 300.0, f, t, None),
        ),
    ):
        assert baked == real, (name, baked, real)
    # …and those values are the ordinary text ones, not a bare font size.
    assert _leaf_height(None, 300.0, f, t, rp) == t.text.font_size * LINE_SCALE
    assert _leaf_first_baseline(None, f, t, rp) == t.text.font_size
    print("  ✓  a baked date leaf measures like the text it is (h/base/width)")


def test_a_baked_date_shares_its_row_baseline():
    """The visible consequence: with a real baseline it sits on the line beside
    the text it was split from, instead of falling back to h / LINE_SCALE."""
    t, f = Theme(), _fonts()
    date = _leaf(None, date_text="Aug 12")
    row = _row(_leaf("t1"), date)
    placements, _h, _g = _place(row)
    bases = [dy + first_baseline(c, w, IDX, f, t) for c, _x, w, _eh, dy in placements]
    assert max(bases) - min(bases) < 1e-6, bases
    print("  ✓  a baked date leaf sits on its row's baseline")


def test_container_reports_its_first_child():
    col = LayoutNode(type="col", ratios=[1.0], children=[_leaf("t1")], content_id=None)
    assert first_baseline(col, 300.0, IDX, _fonts(), Theme()) == Theme().text.font_size
    print("  ✓  a container answers with its first child's baseline")


# ---------------------------------------------------------------------------
# Row placement
# ---------------------------------------------------------------------------


def _baselines(row: LayoutNode, width: float = 600.0):
    placements, row_h, _gaps = _place(row, width)
    out = []
    for child, _x, cw, _eh, dy in placements:
        base = first_baseline(child, cw, IDX, _fonts(), _kv_theme())
        if base is not None:
            out.append(base + dy)
    return out, row_h


def test_same_line_row_shares_one_baseline():
    """The headline case: a 2x-size emphasized number beside body text."""
    row = _row(_leaf("dp", kv_role="value"), _leaf("t1"))
    bases, _h = _baselines(row)
    assert max(bases) - min(bases) < 1e-6, bases
    # …and the small cell really did move (it is not a no-op).
    placements, _h, _g = _place(row)
    assert placements[1][4] > 0, placements[1][4]
    print(
        f"  ✓  same-line row: one baseline (small cell shifted "
        f"{placements[1][4]:.1f}px down)"
    )


def test_row_grows_to_fit_the_shift():
    """A wrapped cell pushed down needs the extra room, so row_h is the tallest
    (offset + height), not the tallest height."""
    row = _row(_leaf("dp", kv_role="value"), _leaf("wrap"))
    placements, row_h, _g = _place(row, 260.0)
    heights = [eh for *_r, eh, _dy in placements]
    shifted = max(dy + eh for *_r, eh, dy in placements)
    assert row_h >= shifted - 1e-6 and row_h > max(heights) - 1e-6, (
        row_h,
        heights,
        shifted,
    )
    print(f"  ✓  row height grows for the shift ({max(heights):.1f} → {row_h:.1f})")


def test_non_same_line_row_is_untouched():
    row = _row(_leaf("dp", kv_role="value"), _leaf("t1"), line_split=False)
    placements, _h, _g = _place(row)
    assert all(dy == 0.0 for *_r, dy in placements)
    print("  ✓  a row that is not one source line keeps top alignment")


def test_single_baseline_row_is_untouched():
    """Nothing to align to when only one cell has a baseline."""
    offsets = _row_valign_offsets(
        _row(_leaf("img"), _leaf("t1")),
        [_leaf("img"), _leaf("t1")],
        [300.0, 300.0],
        [200.0, 22.4],
        [False, False],
        IDX,
        _fonts(),
        _kv_theme(),
    )
    assert offsets == [0.0, 0.0], offsets
    print("  ✓  a lone baseline in the row shifts nothing")


def test_baseline_less_cell_falls_back_to_a_line_box():
    """A bar has no glyphs, but its box IS a body line box — it keeps sitting on
    the neighbouring text's line rather than pinning to the top."""
    t = _kv_theme()
    bar = _leaf("t1", datapoint_bar={"kind": "ratio", "value": 1, "max": 2})
    row = _row(_leaf("dp", kv_role="value"), bar)
    placements, _h, _g = _place(row)
    bar_dy = placements[1][4]
    bar_h = placements[1][3]
    assert (
        abs(
            bar_dy
            - (
                placements[0][4]
                + first_baseline(placements[0][0], 300.0, IDX, _fonts(), t)
                - bar_h / LINE_SCALE
            )
        )
        < 1e-6
    )
    print(f"  ✓  a bar aligns on its line box ({bar_dy:.1f}px down)")


# ---------------------------------------------------------------------------
# A col cell centers; a row cell keeps the baseline
# ---------------------------------------------------------------------------


def _centers(row: LayoutNode, width: float = 600.0):
    """(cell box center, cell height) per placement, in row coordinates."""
    placements, row_h, _g = _place(row, width)
    return [(dy + eh / 2.0, eh) for _c, _x, _w, eh, dy in placements], row_h


def test_a_col_cell_centers_on_the_line_box():
    """A stacked cell has no single line to put on the
    baseline, so it centers on the band the single-line cells define."""
    row = _row(_leaf("t1"), _group("col", _leaf("dp"), _leaf("t2")))
    (leaf_c, leaf_h), (col_c, col_h) = _centers(row)[0]
    assert abs(leaf_c - col_c) < 1e-6, (leaf_c, col_c)
    assert col_h > leaf_h, (col_h, leaf_h)
    # …and the leaf's baseline really is BELOW that shared center (text sits
    # above its baseline), which is what makes this the optical reading.
    placements, _h, _g = _place(row)
    leaf_dy = placements[0][4]
    base = leaf_dy + first_baseline(
        placements[0][0], placements[0][2], IDX, _fonts(), _kv_theme()
    )
    assert base > leaf_c, (base, leaf_c)
    print(
        f"  ✓  a col cell centers on the line box (center {col_c:.1f}px, "
        f"baseline {base:.1f}px)"
    )


def test_a_row_cell_keeps_the_baseline():
    """Only a col STACKS. A row cell is one line, so it still baseline-aligns
    (a group that flows must not be centered like a stacked one)."""
    t, f = _kv_theme(), _fonts()
    row = _row(_leaf("dp", kv_role="value"), _group("row", _leaf("t1")))
    placements, _h, _g = _place(row)
    bases = [dy + first_baseline(c, w, IDX, f, t) for c, _x, w, _eh, dy in placements]
    assert max(bases) - min(bases) < 1e-6, bases
    print("  ✓  a row group cell still shares the row's baseline")


def test_a_tall_col_pushes_the_whole_row_down():
    """A col taller than the text band wants to start ABOVE the row top; the
    row shifts down instead of clipping it — no cell ever gets a negative dy."""
    row = _row(
        _leaf("t1"),
        _group("col", _leaf("t1"), _leaf("t2"), _leaf("t1"), _leaf("t2")),
    )
    placements, row_h, _g = _place(row)
    dys = [dy for *_r, dy in placements]
    assert min(dys) >= 0.0, dys
    assert dys[0] > 0.0 and dys[1] == 0.0, dys
    assert row_h >= max(dy + eh for _c, _x, _w, eh, dy in placements) - 1e-6
    print(
        f"  ✓  a tall col shifts the row down instead of clipping (leaf {dys[0]:.1f}px)"
    )


def test_a_row_of_only_cols_centers_on_itself():
    """No single-line anchor to hang a band off — the stacked cells center on
    each other rather than snaking from the top."""
    row = _row(
        _group("col", _leaf("dp", kv_role="value"), _leaf("t1")),
        _group("col", _leaf("t1"), _leaf("t2")),
    )
    (a_c, a_h), (b_c, b_h) = _centers(row)[0]
    assert abs(a_c - b_c) < 1e-6, (a_c, b_c)
    assert a_h != b_h, (a_h, b_h)
    print("  ✓  a row of only cols centers its cells on each other")


# ---------------------------------------------------------------------------
# The themed modes
# ---------------------------------------------------------------------------


def _mode_row(mode: str | None) -> LayoutNode:
    cells = (
        _leaf("dp", kv_role="value"),
        _group("col", _leaf("t1"), _leaf("t2")),
    )
    return _row(*cells, line_align=mode) if mode else _row(*cells)


def test_top_mode_hangs_every_cell_from_the_row_top():
    placements, _h, _g = _place(_mode_row("top"))
    assert all(dy == 0.0 for *_r, dy in placements)
    print("  ✓  Line align: Top — every cell hangs from the row top")


def test_center_and_bottom_align_the_boxes():
    for mode, at in (("center", 0.5), ("bottom", 1.0)):
        placements, row_h, _g = _place(_mode_row(mode))
        for _c, _x, _w, eh, dy in placements:
            assert abs(dy - (row_h - eh) * at) < 1e-6, (mode, dy, eh, row_h)
    print("  ✓  Line align: Center / Bottom — uniform box alignment")


def test_the_default_mode_is_baseline():
    """No key anywhere == the root default, so an untouched theme is inert."""
    assert Theme().root.line_align == "baseline"
    unset, _h1, _g1 = _place(_mode_row(None))
    named, _h2, _g2 = _place(_mode_row("baseline"))
    assert [p[4] for p in unset] == [p[4] for p in named]
    print("  ✓  no Line align key == Baseline (the default is inert)")


def test_a_mode_never_reaches_a_row_that_is_not_one_line():
    """The themed key is same-line only: a card grid keeps top alignment."""
    for mode in ("top", "baseline", "center", "bottom"):
        row = _row(
            _leaf("dp", kv_role="value"),
            _group("col", _leaf("t1"), _leaf("t2")),
            line_split=False,
            line_align=mode,
        )
        placements, _h, _g = _place(row)
        assert all(dy == 0.0 for *_r, dy in placements), mode
    print("  ✓  no mode touches a row that is not one source line")


TESTS = [
    test_text_baseline_is_the_font_size,
    test_kv_value_baseline_follows_the_bigger_size,
    test_inline_code_baseline_includes_its_pill_padding,
    test_no_baseline_for_image_rule_or_bar,
    test_a_baked_date_leaf_measures_like_the_text_it_is,
    test_a_baked_date_shares_its_row_baseline,
    test_container_reports_its_first_child,
    test_same_line_row_shares_one_baseline,
    test_row_grows_to_fit_the_shift,
    test_non_same_line_row_is_untouched,
    test_single_baseline_row_is_untouched,
    test_baseline_less_cell_falls_back_to_a_line_box,
    test_a_col_cell_centers_on_the_line_box,
    test_a_row_cell_keeps_the_baseline,
    test_a_tall_col_pushes_the_whole_row_down,
    test_a_row_of_only_cols_centers_on_itself,
    test_top_mode_hangs_every_cell_from_the_row_top,
    test_center_and_bottom_align_the_boxes,
    test_the_default_mode_is_baseline,
    test_a_mode_never_reaches_a_row_that_is_not_one_line,
]

if __name__ == "__main__":
    print("Layout Baseline Tests")
    print("=" * 50)
    for test in TESTS:
        test()
    print("=" * 50)
    print(f"All {len(TESTS)} tests passed.")
