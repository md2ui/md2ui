"""
Unit tests for where a ``...`` SPRING actually puts its regions.

The grouper's job is to say which piece is aligned how; these tests check the
other end — that the renderer's packed branch puts the left region flush at 0,
the right region flush against the available width, and a middle region in the
centre. They assert PLACEMENTS rather than properties, because the alignment is
only worth anything if it moves the box.

Run with: uv run python tests/layout_align_tests.py
"""

import sys
from pathlib import Path

sys.path.insert(0, "tests")

from markdown_datapoint_split_tests import _processed_with_criteria

from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline import render_measure as RMS
from md2ui.pipeline import render_place as RPL
from md2ui.pipeline import layout_render as LR
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.theme import Theme, parse_theme
from md2ui.pipeline.theme_model import SectionStyle
from md2ui.utils.font_loader import (
    load_custom_fonts,
    resolve_typeface,
    weight_from_str,
)

TOL = 1.5  # px — sub-pixel text metrics


def _themed(theme: Theme | None = None):
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


def _boxes(src: str, width: float = 900.0):
    """``(boxes, node_index, content_width, layout)`` for *src*."""
    theme, fonts = _themed()
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
    boxes = RPL.place_boxes(
        layout, 0, 0, w, h, node_index, fonts, theme, section_boxes=[]
    )
    return boxes, node_index, w, layout


def _box_for(boxes, node_index, content: str):
    """The single box whose node carries *content*."""
    hits = [
        b
        for b in boxes
        if b.content_id and node_index.get(b.content_id, {}).get("content") == content
    ]
    assert len(hits) == 1, f"{content!r}: expected 1 box, got {len(hits)}"
    return hits[0]


def _left_edge(boxes, node_index, content: str) -> float:
    return _box_for(boxes, node_index, content).x


def _right_edge(boxes, node_index, content: str) -> float:
    b = _box_for(boxes, node_index, content)
    return b.x + b.width


# ---------------------------------------------------------------------------
# The three edges
# ---------------------------------------------------------------------------


def test_one_spring_pushes_the_halves_to_opposite_edges():
    boxes, idx, w, _ = _boxes("Subtotal ... $42.50")
    assert abs(_left_edge(boxes, idx, "Subtotal")) < TOL
    assert abs(_right_edge(boxes, idx, "$42.50") - w) < TOL


def test_the_right_region_keeps_its_pieces_together():
    """``A ... B - C``: B and C both go right, in document order."""
    boxes, idx, w, _ = _boxes("A ... B - C")
    assert abs(_left_edge(boxes, idx, "A")) < TOL
    assert abs(_right_edge(boxes, idx, "C") - w) < TOL
    assert _left_edge(boxes, idx, "B") < _left_edge(boxes, idx, "C")


def test_springs_on_both_ends_centre_the_content():
    boxes, idx, w, _ = _boxes("... Centred ...")
    b = _box_for(boxes, idx, "Centred")
    assert abs((b.x + b.width / 2) - w / 2) < TOL


def test_a_leading_spring_puts_the_whole_line_right():
    boxes, idx, w, _ = _boxes("... Read more")
    assert abs(_right_edge(boxes, idx, "Read more") - w) < TOL


def test_a_trailing_spring_puts_the_whole_line_left():
    """``Read more ...`` is deliberately NOT this case — a lone phrase closing
    on dots reads as a truncation and is kept whole. A line with structure of
    its own is the trailing-spring case."""
    boxes, idx, _w, _ = _boxes("Terms - Privacy - Cookies ...")
    assert abs(_left_edge(boxes, idx, "Terms")) < TOL
    assert _left_edge(boxes, idx, "Cookies") < _w / 2


def test_two_springs_give_left_centre_right():
    boxes, idx, w, _ = _boxes("Home ... About ... Contact")
    assert abs(_left_edge(boxes, idx, "Home")) < TOL
    about = _box_for(boxes, idx, "About")
    assert abs((about.x + about.width / 2) - w / 2) < TOL
    assert abs(_right_edge(boxes, idx, "Contact") - w) < TOL


def test_a_centred_region_gives_way_to_a_long_left_region():
    """The centre is a preference, not a place: when centring would lay the
    middle region over a long left one, it starts one gap after it instead."""
    boxes, idx, _w, _ = _boxes(
        "A long left label that runs on and on ... Middle ... End", 500
    )
    room = _left_edge(boxes, idx, "Middle") - _right_edge(
        boxes, idx, "A long left label that runs on and on"
    )
    assert room > TOL, f"Middle starts {-room:.1f}px inside the left region"
    assert _right_edge(boxes, idx, "Middle") < _left_edge(boxes, idx, "End")


def test_a_centred_region_gives_way_to_a_long_right_region():
    """The mirror case, and the gap kept is the same one on either side."""
    long_right = "A long right label that runs on and on"
    boxes, idx, _w, _ = _boxes(f"Start ... Middle ... {long_right}", 500)
    room = _left_edge(boxes, idx, long_right) - _right_edge(boxes, idx, "Middle")
    assert room > TOL, f"Middle ends {-room:.1f}px inside the right region"
    assert _left_edge(boxes, idx, "Middle") > _right_edge(boxes, idx, "Start")
    boxes, idx, _w, _ = _boxes(
        "A long left label that runs on and on ... Middle ... End", 500
    )
    left_room = _left_edge(boxes, idx, "Middle") - _right_edge(
        boxes, idx, "A long left label that runs on and on"
    )
    assert abs(room - left_room) < TOL


# ---------------------------------------------------------------------------
# Regions that are containers
# ---------------------------------------------------------------------------


def test_colon_columns_are_pushed_apart_as_units():
    """Both leaves of each stacked column go with it, via the cascade.

    A colon column is a card, so each one is inset by its card padding —
    flush-left and flush-right means SYMMETRIC insets, not x == 0.
    """
    boxes, idx, w, _ = _boxes("450 : Projects ... 35 : Users")
    inset = _left_edge(boxes, idx, "450")
    assert _left_edge(boxes, idx, "Projects") == inset
    for right in ("35", "Users"):
        assert abs(_right_edge(boxes, idx, right) - (w - inset)) < TOL
    # …and they really are apart, not merely inset.
    assert _left_edge(boxes, idx, "35") > w / 2


def test_a_spring_row_claims_the_width_it_is_offered():
    """Without this the row collapses to its content and the spring has no
    slack to open — the regions would sit flush against each other."""
    _boxes_, _idx, w, layout = _boxes("A ... B")

    def find_spring(n):
        if getattr(n, "spring", False):
            return n
        for c in n.children:
            hit = find_spring(c)
            if hit is not None:
                return hit
        return None

    row = find_spring(layout)
    assert row is not None, "no spring row emitted"
    theme, fonts = _themed()
    assert RMS.natural_width(row, w, {}, fonts, theme) == w, (
        "a spring row must stretch, like a grid row"
    )


# ---------------------------------------------------------------------------
# Inside a heading line
# ---------------------------------------------------------------------------


def test_a_heading_button_is_placed_at_the_right_edge():
    """A title left, an action button right — the shape springs were built for.

    With the built-in defaults, where no heading level carries a surface: a level
    with a section background insets its row by that section's padding, so its
    edges are not 0 / w — which is a theme's choice, not what this pins.
    """
    theme, fonts = _themed(Theme())
    for level in (1, 3):
        src = f"{'#' * level} Transaction History ... [`…`](/more)"
        boxes, idx, w = _boxes_themed(src, theme, fonts)
        assert abs(_left_edge(boxes, idx, "Transaction History")) < TOL, src
        assert abs(_right_edge(boxes, idx, "[`…`](/more)") - w) < TOL, src


def test_a_split_heading_keeps_its_typography():
    """The regions are plain TEXT, so the heading font can only come from
    ``heading_ctx`` — the split must not quietly demote the title to body text."""
    boxes, idx, _w, _ = _boxes("### Transaction History ... [`…`](/more)")
    title = _box_for(boxes, idx, "Transaction History")
    assert idx[title.content_id].get("heading_ctx") == 3
    plain, _pidx, _pw, _ = _boxes("Transaction History ... [`…`](/more)")
    assert title.width > _box_for(plain, _pidx, "Transaction History").width


# ---------------------------------------------------------------------------
# Key: ... Value — an ordinary spring row whose left text keeps its colon
# ---------------------------------------------------------------------------


def test_kv_spring_puts_the_pair_on_one_row():
    boxes, idx, w, _ = _boxes("Order ID: ... ORD-2026-02-04-78923")
    key = _box_for(boxes, idx, "Order ID:")
    value = _box_for(boxes, idx, "ORD-2026-02-04-78923")
    # Same ROW, not same y: the cells baseline-align, so a larger value sits at
    # its own top. Vertical overlap is what "one row" actually means here.
    assert key.y < value.y + value.height and value.y < key.y + key.height, (
        "key and value must share a row"
    )
    assert abs(key.x) < TOL
    assert abs((value.x + value.width) - w) < TOL


def test_kv_spring_stacks_when_the_row_cannot_fit():
    """The same feasibility rule an aside gets: measure, then decide."""
    boxes, idx, _w, _ = _boxes(
        "A considerably long key that fills the line: ... "
        "and a value quite as long as the key beside it",
        width=260.0,
    )
    key = _box_for(boxes, idx, "A considerably long key that fills the line:")
    value = _box_for(boxes, idx, "and a value quite as long as the key beside it")
    assert value.y > key.y, "the pair should have stacked"


# ---------------------------------------------------------------------------
# Nothing else moves
# ---------------------------------------------------------------------------


def test_a_line_without_a_spring_is_untouched():
    boxes, idx, _w, layout = _boxes("A - B - C")

    def any_spring(n):
        return getattr(n, "spring", False) or any(any_spring(c) for c in n.children)

    assert not any_spring(layout)
    assert abs(_left_edge(boxes, idx, "A")) < TOL
    assert _left_edge(boxes, idx, "B") < _left_edge(boxes, idx, "C")


# ---------------------------------------------------------------------------
# Per-level `Horizontal align` — THEME.md, Root / Heading N / Elements / Image Cards
# ---------------------------------------------------------------------------


def _theme_with(_key: str = "Horizontal align", **blocks: str):
    """The repo THEME.md with *_key* injected into the named `###` blocks.

    Keys are block names as they appear in THEME.md (`Root`, `Heading 2`,
    `Elements`, …); values are the alignment. Starting from the real theme keeps
    fonts and paddings realistic, which matters because these assert placements.
    ``_key`` picks the axis: `Horizontal align` or `Vertical align`. Those are
    the spellings the repo THEME.md ships, which is what the replace below
    matches on — `Align` / `Line align` also PARSE, but they are not what is
    written in the file being edited here.
    """
    import tempfile

    src = Path("data/markdown/tests/THEME.md").read_text(encoding="utf-8")
    pre = f"{_key.lower()}:"
    for block, align in blocks.items():
        marker = f"### {block}\n"
        assert marker in src, block
        start = src.index(marker) + len(marker)
        nxt = src.find("\n### ", start)
        end = len(src) if nxt < 0 else nxt
        body = src[start:end]
        # REPLACE an existing key in the block — `### Root` already ships both
        # (`Horizontal align: …`, `Vertical align: …`), and merely inserting
        # above one would be overwritten by the later line.
        lines = [
            f"{_key}: {align}" if ln.lower().startswith(pre) else ln
            for ln in body.split("\n")
        ]
        if not any(ln.lower().startswith(pre) for ln in body.split("\n")):
            lines.insert(0, f"{_key}: {align}")
        src = src[:start] + "\n".join(lines) + src[end:]
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(src, encoding="utf-8")
        theme = parse_theme(path)
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


def _boxes_themed(src: str, theme, fonts, width: float = 900.0):
    """`_boxes`, but with a caller-supplied theme threaded into the bake too."""
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
    RPL.bake_render_cascade(layout, theme=theme)
    h = RMS.natural_height(layout, w, node_index, fonts, theme)
    boxes = RPL.place_boxes(
        layout, 0, 0, w, h, node_index, fonts, theme, section_boxes=[]
    )
    return boxes, node_index, w


def _centre_of(boxes, node_index, content: str) -> float:
    b = _box_for(boxes, node_index, content)
    return b.x + b.width / 2.0


def test_align_parses_on_levels_and_cards():
    theme, _ = _theme_with(**{"Heading 2": "Center", "Elements": "Right"})
    assert theme.sections[2].align == "center"
    assert theme.elements.align == "right"
    assert theme.sections.get(3) is None or theme.sections[3].align is None

    # ...and on a BLANK level it must not start a background. (The repo theme's
    # own levels paint for unrelated reasons, so this needs a bare one.)
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(
            "## Background styles and Spacing\n### Heading 4\nHorizontal align: Center\n",
            encoding="utf-8",
        )
        bare = parse_theme(path)
    assert bare.sections[4].align == "center"
    assert not bare.sections[4].is_active(), (
        "Align must stay out of is_active() — it cannot make a level paint"
    )
    print("  \u2713  `Align` parses per level and stays out of is_active()")


def test_right_is_reachable_from_a_theme_at_last():
    """`Align: Right` written in THEME.md reaches the layout, not just a Theme
    built in Python."""
    theme, _ = _theme_with(Root="Right")
    assert theme.root.align == "right", theme.root.align
    theme, _ = _theme_with(Root="Center")
    assert theme.root.align == "center"
    theme, _ = _theme_with(Root="Default")
    assert theme.root.align == "left", "Default is Root's own default"
    print("  \u2713  Align: Right finally survives the theme parser")


def test_a_level_centres_the_content_it_owns():
    theme, fonts = _theme_with(**{"Heading 2": "Center"})
    src = "## Centered section\n\nA short body line\n"
    boxes, idx, w = _boxes_themed(src, theme, fonts)
    assert abs(_centre_of(boxes, idx, "A short body line") - w / 2) < 30.0, (
        "a level's Align: Center must move its content to the middle"
    )
    print("  \u2713  a level centres the content it owns")


def test_a_level_inherits_into_a_nested_section_until_overridden():
    """The agreed semantic: inherit, and a deeper level overrides."""
    theme, fonts = _theme_with(**{"Heading 2": "Center"})
    src = "## Outer\n\nOuter body line\n\n### Inner\n\nInner body line\n"
    boxes, idx, w = _boxes_themed(src, theme, fonts)
    assert abs(_centre_of(boxes, idx, "Inner body line") - w / 2) < 30.0, (
        "a nested section must inherit the level above it"
    )

    theme, fonts = _theme_with(**{"Heading 2": "Center", "Heading 3": "Left"})
    boxes, idx, w = _boxes_themed(src, theme, fonts)
    assert _box_for(boxes, idx, "Inner body line").x < w / 4, (
        "a deeper level's own Align must override the one it inherited"
    )
    assert abs(_centre_of(boxes, idx, "Outer body line") - w / 2) < 30.0, (
        "...without disturbing the level above it"
    )
    print("  \u2713  a level inherits into a nested section, until it overrides")


def test_a_spring_beats_an_inherited_level():
    """Own beats inherited, twice over."""
    theme, fonts = _theme_with(**{"Heading 2": "Center"})
    src = "## Centered\n\nSubtotal ... $42.50\n"
    boxes, idx, w = _boxes_themed(src, theme, fonts)
    left = _box_for(boxes, idx, "Subtotal")
    right = _box_for(boxes, idx, "$42.50")
    assert left.x < w / 4, f"the spring's left region must stay left, got {left.x}"
    assert right.x + right.width > w * 0.75, (
        "the spring's right region must stay right, not be pulled to the centre"
    )
    print("  \u2713  a spring still reaches the edges inside a centered level")


def test_a_card_aligns_its_content_not_itself():
    """`### Elements / Align: Center` centres text INSIDE the card.

    The card keeps the width the layout gave it — this is content alignment, the
    same thing `### Root`'s Align means, not block placement.
    """
    theme, fonts = _theme_with(Elements="Center")
    src = "## Section\n\nFirst body line\nSecond body line\n"
    boxes, idx, w = _boxes_themed(src, theme, fonts)
    for line in ("First body line", "Second body line"):
        assert abs(_centre_of(boxes, idx, line) - w / 2) < 30.0, (
            f"{line!r} should be centred inside its card"
        )
    print("  \u2713  a card's Align centres its content, card width untouched")


def test_a_section_card_takes_its_levels_alignment_first():
    """One node may be section AND glued card."""
    theme = Theme()
    theme.sections[2] = SectionStyle(align="center", line_align="bottom")
    theme.elements.align = "right"
    theme.elements.line_align = "top"
    leaf = LayoutNode(type="-", ratios=[], children=[], content_id="greeting")
    dual = LayoutNode(type="col", ratios=[1.0], children=[leaf], section_level=2)
    dual.is_card = True
    root = LayoutNode(type="layout", ratios=[1.0], children=[dual])

    RPL.bake_render_cascade(root, theme=theme)

    assert (dual.render_properties or {})["content_align"] == "center"
    assert (leaf.render_properties or {})["content_align"] == "center"
    assert (dual.render_properties or {})["line_align"] == "bottom"
    print("  \u2713  a section-card takes its level's alignment before Elements")


def test_a_centered_level_moves_its_elements_too():
    """Pills, chips and badges follow a cascaded align, not just Root: they
    resolve through `_resolve_h_align`, the same tier order text uses."""
    theme, fonts = _theme_with(**{"Heading 2": "Center"})
    src = "## Centered\n\n[Buy now](/b)\n\n`Some chip`\n"
    boxes, idx, w = _boxes_themed(src, theme, fonts)
    for content, label in (("[Buy now](/b)", "button"), ("Some chip", "chip")):
        b = _box_for(boxes, idx, content)
        rp = LR._walk and (idx.get(b.content_id) or {})
        assert rp, content
        assert (b.render_properties or {}).get("content_align") == "center", (
            f"the {label} must receive the level's centered alignment"
        )
    print("  \u2713  a centered level reaches its buttons and chips")


# ---------------------------------------------------------------------------
# Per-level `Line align` — the VERTICAL axis, same blocks as `Align`
# ---------------------------------------------------------------------------

# One source line whose pieces are a STACKED cell (`92 : days`) and a leaf.
_STACKED_LINE = "Discount - 92 : days - 41%"


def _stacked_row_boxes(theme, fonts, heading: str = ""):
    src = f"{heading}\n\n{_STACKED_LINE}" if heading else _STACKED_LINE
    boxes, idx, _w = _boxes_themed(src, theme, fonts)
    return (
        _box_for(boxes, idx, "92"),
        _box_for(boxes, idx, "days"),
        _box_for(boxes, idx, "41%"),
    )


def test_line_align_parses_on_levels_and_cards():
    theme, _ = _theme_with(
        "Vertical align", **{"Heading 2": "Bottom", "Elements": "Center"}
    )
    assert theme.sections[2].line_align == "bottom"
    assert theme.elements.line_align == "center"
    assert theme.sections[3] is None or theme.sections[3].line_align is None
    # Root is the base of the cascade: Default resolves to its OWN default
    # rather than to "inherit". (Asserted through the parser, not off the live
    # THEME.md, so an authored `Line align:` there cannot flip this test.)
    assert Theme().root.line_align == "baseline"
    assert _theme_with("Vertical align", Root="Default")[0].root.line_align == (
        "baseline"
    )
    assert _theme_with("Vertical align", Root="Center")[0].root.line_align == ("center")

    import tempfile

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(
            "## Background styles and Spacing\n### Heading 4\nLine align: Bottom\n",
            encoding="utf-8",
        )
        bare = parse_theme(path)
    assert bare.sections[4].line_align == "bottom"
    assert not bare.sections[4].is_active(), (
        "Line align must stay out of is_active() — it cannot make a level paint"
    )
    # Garbage / Default on a LEVEL reads as "unset, inherit".
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(
            "## Background styles and Spacing\n### Heading 4\nLine align: Sideways\n",
            encoding="utf-8",
        )
        assert parse_theme(path).sections[4].line_align is None
    print("  \u2713  `Line align` parses per level and stays out of is_active()")


def test_the_default_line_align_centres_a_stacked_cell():
    """End to end: `92 : days` stacks, so it centres on the line box
    of the `41%` beside it instead of putting `92` on its baseline.

    Pinned to Baseline rather than read off the live THEME.md — this asserts
    what the DEFAULT mode does, and the repo theme is free to author another.
    """
    theme, fonts = _theme_with("Vertical align", Root="Baseline")
    top, bottom, leaf = _stacked_row_boxes(theme, fonts)
    col_mid = (top.y + bottom.y + bottom.height) / 2.0
    leaf_mid = leaf.y + leaf.height / 2.0
    assert abs(col_mid - leaf_mid) < TOL, (col_mid, leaf_mid)
    assert top.y < leaf.y, (top.y, leaf.y)
    print("  \u2713  a stacked cell centres on the line beside it by default")


def test_line_align_moves_the_row_it_owns():
    """Top / Baseline / Bottom really are three different placements."""
    ys = {}
    for mode in ("Top", "Baseline", "Bottom"):
        theme, fonts = _theme_with("Vertical align", Root=mode)
        top, _bottom, leaf = _stacked_row_boxes(theme, fonts)
        ys[mode] = leaf.y - top.y
    assert ys["Top"] < ys["Baseline"] < ys["Bottom"], ys
    assert abs(ys["Top"]) < TOL, ys  # top: both cells hang from the row top
    print(f"  \u2713  Top / Baseline / Bottom place the leaf differently ({ys})")


def test_a_level_line_align_beats_the_root():
    """`Line align` inherits per level exactly like `Align`."""
    root_only, fonts_a = _theme_with("Vertical align", Root="Top")
    per_level, fonts_b = _theme_with(
        "Vertical align", Root="Top", **{"Heading 2": "Bottom"}
    )
    _t, _b, leaf_root = _stacked_row_boxes(root_only, fonts_a, "## Section")
    _t2, _b2, leaf_lvl = _stacked_row_boxes(per_level, fonts_b, "## Section")
    assert leaf_lvl.y > leaf_root.y, (leaf_root.y, leaf_lvl.y)
    print("  \u2713  a level's `Line align` overrides the root's")


# ---------------------------------------------------------------------------
# Per-level `Orphan row` — what a grid's RAGGED final row does
# ---------------------------------------------------------------------------


def test_orphan_row_parses_on_levels_and_cards():
    theme, _ = _theme_with(
        "Orphan row", **{"Heading 2": "Stretch", "Elements": "Center"}
    )
    assert theme.sections[2].orphan_row == "stretch"
    assert theme.elements.orphan_row == "center"
    assert theme.sections[3] is None or theme.sections[3].orphan_row is None
    # Root is the base of the cascade: Default resolves to its OWN default,
    # `left`, so an untouched theme is inert.
    assert Theme().root.orphan_row == "left"
    assert _theme_with("Orphan row", Root="Default")[0].root.orphan_row == "left"
    assert _theme_with("Orphan row", Root="Stretch")[0].root.orphan_row == ("stretch")

    import tempfile

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(
            "## Background styles and Spacing\n### Heading 4\nOrphan row: Center\n",
            encoding="utf-8",
        )
        bare = parse_theme(path)
    assert bare.sections[4].orphan_row == "center"
    assert not bare.sections[4].is_active(), (
        "Orphan row must stay out of is_active() — it cannot make a level paint"
    )
    # Garbage / Default on a LEVEL reads as "unset, inherit".
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(
            "## Background styles and Spacing\n### Heading 4\nOrphan row: Sideways\n",
            encoding="utf-8",
        )
        assert parse_theme(path).sections[4].orphan_row is None
    print("  \u2713  `Orphan row` parses per level and stays out of is_active()")


# ---------------------------------------------------------------------------
# Root-only `Max width` / `Centered` — the draw area
# ---------------------------------------------------------------------------


def test_max_width_parses_and_caps():
    from md2ui.pipeline.theme import CONTENT_WIDTH_MAX, CONTENT_WIDTH_MIN

    assert Theme().root.max_width == CONTENT_WIDTH_MAX
    assert _theme_with("Max width", Root="1600")[0].root.max_width == 1600.0
    # A malformed value keeps the current one rather than resetting the layout.
    assert _theme_with("Max width", Root="wide")[0].root.max_width == (
        CONTENT_WIDTH_MAX
    )
    # …and a value under the sanity floor clamps up instead of collapsing.
    assert _theme_with("Max width", Root="10")[0].root.max_width == (CONTENT_WIDTH_MIN)

    # The cap is what _content_width applies.
    assert LR._content_width(2000.0) == CONTENT_WIDTH_MAX, "no theme = default"
    theme, _ = _theme_with("Max width", Root="1600")
    assert LR._content_width(2000.0, theme) == 1600.0
    print("  \u2713  `Max width` caps the layout")


def test_centered_parses_and_places_the_layout():
    assert Theme().root.centered is True, "centred is the default"
    assert _theme_with("Centered", Root="no")[0].root.centered is False
    assert _theme_with("Centered", Root="yes")[0].root.centered is True
    # A yes-default boolean must survive a typo — the plain `in (...)` idiom
    # would silently turn it off.
    assert _theme_with("Centered", Root="mabye")[0].root.centered is True

    # The placement itself: half the slack when centred, hard left when not.
    pad, vp_x = 32.0, 0.0
    centred = LR._content_origin_x(vp_x, 1536.0, 1280.0, pad, True)
    left = LR._content_origin_x(vp_x, 1536.0, 1280.0, pad, False)
    assert left == vp_x + pad
    assert centred == vp_x + pad + (1536.0 - 1280.0) / 2.0
    # No slack (the usual case — the window opens sized to the layout): no move.
    assert LR._content_origin_x(vp_x, 1280.0, 1280.0, pad, True) == vp_x + pad
    print("  \u2713  `Centered` places the layout; no slack means no move")


TESTS = [
    test_align_parses_on_levels_and_cards,
    test_right_is_reachable_from_a_theme_at_last,
    test_a_level_centres_the_content_it_owns,
    test_a_level_inherits_into_a_nested_section_until_overridden,
    test_a_spring_beats_an_inherited_level,
    test_a_card_aligns_its_content_not_itself,
    test_a_section_card_takes_its_levels_alignment_first,
    test_a_centered_level_moves_its_elements_too,
    test_one_spring_pushes_the_halves_to_opposite_edges,
    test_the_right_region_keeps_its_pieces_together,
    test_springs_on_both_ends_centre_the_content,
    test_a_leading_spring_puts_the_whole_line_right,
    test_a_trailing_spring_puts_the_whole_line_left,
    test_two_springs_give_left_centre_right,
    test_a_centred_region_gives_way_to_a_long_left_region,
    test_a_centred_region_gives_way_to_a_long_right_region,
    test_colon_columns_are_pushed_apart_as_units,
    test_a_spring_row_claims_the_width_it_is_offered,
    test_a_heading_button_is_placed_at_the_right_edge,
    test_a_split_heading_keeps_its_typography,
    test_kv_spring_puts_the_pair_on_one_row,
    test_kv_spring_stacks_when_the_row_cannot_fit,
    test_a_line_without_a_spring_is_untouched,
    test_line_align_parses_on_levels_and_cards,
    test_the_default_line_align_centres_a_stacked_cell,
    test_line_align_moves_the_row_it_owns,
    test_a_level_line_align_beats_the_root,
    test_orphan_row_parses_on_levels_and_cards,
    test_max_width_parses_and_caps,
    test_centered_parses_and_places_the_layout,
]


if __name__ == "__main__":
    print("Layout Align (spring) Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓  {test.__name__}")
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
