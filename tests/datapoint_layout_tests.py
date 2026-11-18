"""
Unit tests for the layout generator's drawn datapoint displays: flagged
leaves carry ``datapoint_bar`` / ``datapoint_ring`` / ``date_chip`` /
``kv_role`` render properties, container families collapse to synthetic
leaves (of/unit/chart) or gain a bar sibling (kv percent), and the THEME.md
toggles gate everything (no theme / disabled family = pre-feature layout).

Run with: uv run tests/datapoint_layout_tests.py
"""

import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from layout_decision_scope_tests import RecordingGenerator, aside_theme
from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.grouper_types import NodeType
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.markdown_grouper import (
    MarkdownGrouper,
    MarkdownGroupNode,
)
from md2ui.pipeline.theme import Theme

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ast(text: str) -> MarkdownGroupNode:
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    return g.ast


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def _props(layout, key: str) -> list:
    """All render_properties values under *key* across the layout tree."""
    out = []
    for n in _walk(layout):
        rp = getattr(n, "render_properties", None)
        if rp and key in rp:
            out.append((n, rp[key]))
    return out


def _generate(text: str, theme=None, width: float = 800.0):
    return LayoutGenerator().generate(_ast(text), width, theme=theme)


# ---------------------------------------------------------------------------
# Leaf families
# ---------------------------------------------------------------------------


def _bar_row(layout):
    """The row holding a datapoint_bar leaf beside text leaves."""
    for n in _walk(layout):
        if n.type == "row" and any(
            "datapoint_bar" in (getattr(c, "render_properties", None) or {})
            for c in n.children
        ):
            return n
    raise AssertionError("no bar row found")


def test_ratio_bar_row_keeps_text_leaf():
    # Two blocks: a single-line document collapses to a childless root, which
    # generate() renders as empty.
    layout = _generate("some text\n\n4/8", Theme())
    row = _bar_row(layout)
    assert row.line_split, "bar row flows like same-line content"
    assert len(row.children) == 2
    bar, text = row.children  # default Text side: right → bar first
    p = (bar.render_properties or {})["datapoint_bar"]
    assert p["kind"] == "ratio" and p["value"] == 4.0 and p["max"] == 8.0
    assert bar.content_id is None, "bar leaf is synthetic"
    assert text.content_id, "the 4/8 text stays a real leaf"
    assert "datapoint_bar" not in (text.render_properties or {})
    assert len(row.ratios) == 2 and row.ratios[1] < row.ratios[0], (
        "text gets its measured ratio, bar the remainder"
    )


def test_ratio_bar_text_side_left():
    t = Theme()
    t.datapoints.ratio_bar.text_side = "left"
    layout = _generate("some text\n\n4/8", t)
    row = _bar_row(layout)
    text, bar = row.children
    assert "datapoint_bar" in (bar.render_properties or {})
    assert text.content_id


def test_date_chip_builds_card_col():
    layout = _generate("some text\n\nMon-15", Theme())
    chips = [n for n in _walk(layout) if getattr(n, "card_kind", None) == "date_chip"]
    assert len(chips) == 1
    col = chips[0]
    assert col.type == "col" and col.is_card and len(col.children) == 2
    key_leaf, day_leaf = col.children
    # The chip's two leaves are REAL text nodes (content_ids) carrying a
    # date_role, styled/uppercased by the renderer.
    assert (key_leaf.render_properties or {}).get("date_role") == "key"
    assert (day_leaf.render_properties or {}).get("date_role") == "day"
    assert key_leaf.content_id and day_leaf.content_id
    assert not _props(layout, "date_chip")
    assert not _props(layout, "date_chip_text")


def test_date_chips_grid_when_repeated():
    # Adjacent repeated chips grid into a row (group runs grid; leaf runs don't).
    layout = _generate("Jun-5\nJun-6\nJun-7\nJun-8", Theme(), width=800.0)
    grid_rows = [n for n in _walk(layout) if getattr(n, "grid", False)]
    assert grid_rows, "repeated date chips should produce a grid row"
    assert any(n.grid_cols > 1 for n in grid_rows)
    chips = [n for n in _walk(layout) if getattr(n, "card_kind", None) == "date_chip"]
    assert len(chips) == 4


def test_date_chip_columns_are_chip_wide():
    # A chip column is the chip's text plus its `### Dates` card padding, not
    # LEAF_WIDTH's one-word 80px: 8 chips of 28px text + 24px padding need
    # 8*52 + 7*gap, which fits 652px in one row.
    from md2ui.pipeline.theme_model import PaddingBox

    t = Theme()
    t.datapoints.date_chip.chip.padding = PaddingBox(12, 12, 12, 12)
    text = " - ".join(f"Jun-{d}" for d in range(5, 13))
    layout = LayoutGenerator().generate(
        _ast(text), 652.0, theme=t, measure_width=lambda _n: 28.0
    )
    cols = [n.grid_cols for n in _walk(layout) if getattr(n, "grid", False)]
    assert cols == [8], f"8 chips should share one row at 652px, got grid cols {cols}"


def test_date_chip_kind_columns_match_one_run():
    # Two runs of one kind share a column count (_kind_cols). That count must
    # be the one a lone run gets: chip-wide columns plus the `### Dates` card
    # padding — not LEAF_WIDTH's 80px (too wide), nor the chip text alone
    # (too narrow: 8 columns at 450px squeezed every chip).
    from md2ui.pipeline.theme_model import PaddingBox

    t = Theme()
    t.datapoints.date_chip.chip.padding = PaddingBox(12, 12, 12, 12)
    run = " - ".join(f"Jun-{d}" for d in range(5, 13))
    for width in (450.0, 652.0):
        one, two = (
            [
                n.grid_cols
                for n in _walk(
                    LayoutGenerator().generate(
                        _ast(doc), width, theme=t, measure_width=lambda _n: 28.0
                    )
                )
                if getattr(n, "grid", False)
            ]
            for doc in (run, f"{run}\n\nBetween the runs.\n\n{run}")
        )
        assert two == one * 2, (width, one, two)


def test_date_chip_disabled_stays_text():
    t = Theme()
    t.datapoints.date_chip.enabled = False
    layout = _generate("some text\n\nMon-15", t)
    assert not [
        n for n in _walk(layout) if getattr(n, "card_kind", None) == "date_chip"
    ]
    base = _generate("some text\n\nMon-15", None)
    assert layout.to_dict() == base.to_dict()


def test_date_chip_card_style_and_fonts():
    # The chip col resolves to its OWN themed style (not theme.elements), and
    # the two roles resolve their text styles with sensible fallbacks.
    from md2ui.pipeline.layout_render import _date_chip_text_style
    from md2ui.pipeline.render_backgrounds import _card_style_for

    t = Theme()
    t.datapoints.date_chip.chip.bg_colors = [0xFFFBEFFB]
    layout = _generate("some text\n\nMon-15", t)
    col = next(n for n in _walk(layout) if getattr(n, "card_kind", None) == "date_chip")
    assert _card_style_for(col, t) is t.datapoints.date_chip.chip
    # key falls back to labels; day to a bold ~1.5x default.
    assert _date_chip_text_style(t, "key") is t.labels
    day = _date_chip_text_style(t, "day")
    assert day.font_weight == "bold" and day.font_size > t.text.font_size


def test_unit_ratio_style_bar_vs_ring():
    t = Theme()
    assert t.datapoints.unit_ratio_style == "bar"
    # Two blocks, for the reason test_ratio_bar_row_keeps_text_leaf gives: a
    # single-line document collapses to a childless root and renders empty.
    # `750/1800 Kcal` is one LEAF rather than a [dp, unit] container
    # (ADR-205), so this also covers the leaf side of the bar family.
    layout = _generate("some text\n\n750/1800 Kcal", t)
    row = _bar_row(layout)
    assert row.line_split
    bar = row.children[0]  # Text side: right → bar first
    assert (bar.render_properties or {})["datapoint_bar"]["kind"] == "unit"
    text_leaves = [c for c in row.children[1:] if c.content_id]
    assert text_leaves, "the 750/1800 / Kcal pieces stay real leaves"
    assert not _props(layout, "datapoint_ring")

    t.datapoints.unit_ratio_style = "ring"
    layout = _generate("some text\n\n750/1800 Kcal", t)
    rings = [n for n in _walk(layout) if getattr(n, "card_kind", None) == "ring"]
    assert len(rings) == 1
    col = rings[0]
    assert col.type == "col" and col.is_card
    assert (col.render_properties or {})["ring"] == {
        "value": 750.0,
        "max": 1800.0,
    }
    value_leaf, unit_leaf = col.children
    vp = value_leaf.render_properties or {}
    up = unit_leaf.render_properties or {}
    assert vp["ring_role"] == "value" and vp["ring_text"] == "750/1800"
    assert up["ring_role"] == "unit" and up["ring_text"] == "Kcal"
    assert not _props(layout, "datapoint_bar")


def test_ring_ratio_text_visibility_combinations():
    expected = {
        (True, True): ("7/8", "Minutes"),
        (False, True): ("7", "Minutes"),
        (True, False): ("7/8",),
        (False, False): ("7",),
    }
    for (show_total, show_key), texts in expected.items():
        t = Theme()
        t.datapoints.unit_ratio_style = "ring"
        t.datapoints.unit_ratio_show_total = show_total
        t.datapoints.unit_ratio_show_key = show_key
        layout = _generate("some text\n\nMinutes: 7/8", t)
        ring = next(n for n in _walk(layout) if getattr(n, "card_kind", None) == "ring")
        assert (
            tuple((c.render_properties or {}).get("ring_text") for c in ring.children)
            == texts
        )
        assert (ring.render_properties or {})["ring"] == {
            "value": 7.0,
            "max": 8.0,
        }


def test_bar_ratio_text_visibility_combinations():
    expected = {
        (True, True): (2, []),
        (False, True): (2, ["7"]),
        (True, False): (1, []),
        (False, False): (1, ["7"]),
    }
    for (show_total, show_key), (content_count, overrides) in expected.items():
        t = Theme()
        t.datapoints.unit_ratio_show_total = show_total
        t.datapoints.unit_ratio_show_key = show_key
        layout = _generate("some text\n\nMinutes: 7/8", t)
        col = _kv_bar_col(layout)
        text_part = next(
            c
            for c in col.children
            if "datapoint_bar" not in (c.render_properties or {})
        )
        assert len([n for n in _walk(text_part) if n.content_id]) == content_count
        assert [p for _, p in _props(text_part, "text_override")] == overrides


def test_compact_unit_ratio_can_hide_total_and_key():
    t = Theme()
    t.datapoints.unit_ratio_show_total = False
    t.datapoints.unit_ratio_show_key = False
    layout = _generate("some text\n\n75/100g", t)
    assert [p for _, p in _props(layout, "text_override")] == ["75"]


def test_bare_ratio_can_hide_total():
    t = Theme()
    t.datapoints.unit_ratio_show_total = False
    layout = _generate("some text\n\n4/8", t)
    assert [p for _, p in _props(layout, "text_override")] == ["4"]


def test_ring_reserves_diameter():
    from md2ui.pipeline.layout_render import FontSet, natural_height
    import skia

    t = Theme()
    t.datapoints.unit_ratio_style = "ring"
    t.datapoints.ring.diameter = 120.0
    layout = _generate("some text\n\n750/1800 Kcal", t)
    col = next(n for n in _walk(layout) if getattr(n, "card_kind", None) == "ring")
    tf = skia.Typeface.MakeDefault()
    fonts = FontSet(tf, tf, tf, tf, tf)
    assert natural_height(col, 400.0, {}, fonts, t) == 120.0


# Four rings; only the first member's key is long enough to be `short` (a
# 200px LEAF_WIDTH floor). Every ring draws 96px wide.
_RINGS = [
    "Live data with reliable images: 8/10",
    "Basic text answer: 2/10 difficulty",
    "Structured cards and actions: 4/10",
    "A polished interactive session: 7/10",
]


def _ring_grid_cols(items: list[str], twice: bool = False) -> list[int]:
    t = Theme()
    t.datapoints.unit_ratio_style = "ring"
    doc = "\n".join(f"- {i}" for i in items)
    if twice:
        doc = f"{doc}\n\nBetween the runs.\n\n{doc}"
    layout = LayoutGenerator().generate(
        _ast(doc), 600.0, theme=t, measure_width=lambda _n: 30.0
    )
    return [n.grid_cols for n in _walk(layout) if getattr(n, "grid", False)]


def test_ring_columns_are_ring_wide_whatever_the_order():
    # A ring's column starts at the ring, not at its key's word count, so four
    # rings that fit one row at 600px draw four across whichever key is first.
    long_first = _ring_grid_cols(_RINGS)
    short_first = _ring_grid_cols([_RINGS[1], _RINGS[0], *_RINGS[2:]])
    assert long_first == short_first == [4], (long_first, short_first)


def test_ring_kind_columns_are_ring_wide():
    # Two runs of one kind share a column count floored by every member
    # (_kind_cols); a ring member must floor it at the ring, not its words.
    cols = _ring_grid_cols(_RINGS, twice=True)
    assert cols == [4, 4], cols


def _kv_bar_col(layout):
    """The col holding [kv, bar] (or [bar, kv])."""
    for n in _walk(layout):
        if n.type == "col" and any(
            getattr(c, "render_properties", None)
            and "datapoint_bar" in (c.render_properties or {})
            for c in n.children
        ):
            return n
    raise AssertionError("no kv bar col found")


def test_kv_percent_bar_below_by_default():
    layout = _generate("GPT-5.5: 50%", Theme())
    col = _kv_bar_col(layout)
    assert len(col.children) == 2
    kv_row, bar = col.children
    assert "datapoint_bar" in (bar.render_properties or {})
    assert (bar.render_properties or {})["datapoint_bar"]["percent"] == 50.0
    # Key and value share ONE row; the value is pushed to the right edge via
    # content_align (the row-placement property the renderer buckets on).
    assert kv_row.type == "row" and len(kv_row.children) == 2
    key_part, value_part = kv_row.children
    assert (value_part.render_properties or {}).get("content_align") == "right"
    assert (key_part.render_properties or {}).get("content_align") != "right"
    ids = [n.content_id for n in _walk(kv_row) if n.content_id]
    assert len(ids) >= 2, "key and value keep their real leaves"


def test_kv_ratio_bar_style_uses_kv_row():
    # `Minutes: 7/8` with Style: bar renders like a kv bar (key left, ratio
    # right, bar below) themed by Key Value Bars.
    t = Theme()
    assert t.datapoints.unit_ratio_style == "bar"
    layout = _generate("Minutes: 7/8", t)
    col = _kv_bar_col(layout)
    kv_row, bar = col.children
    p = (bar.render_properties or {})["datapoint_bar"]
    assert p["kind"] == "kv_unit" and p["value"] == 7.0 and p["max"] == 8.0
    assert kv_row.type == "row"
    value_part = kv_row.children[1]
    assert (value_part.render_properties or {}).get("content_align") == "right"


def test_kv_percent_bar_position_above():
    t = Theme()
    t.datapoints.kv_bar.position = "above"
    layout = _generate("GPT-5.5: 50%", t)
    col = _kv_bar_col(layout)
    bar = col.children[0]
    assert "datapoint_bar" in (bar.render_properties or {})


def test_kv_percent_bar_text_visibility_combinations():
    expected = {
        (True, True): ("0.0", "0.1.0"),
        (True, False): ("0.0",),
        (False, True): ("0.1.0",),
        (False, False): (),
    }
    for (show_key, show_value), visible_text in expected.items():
        t = Theme()
        t.datapoints.kv_bar.show_key = show_key
        t.datapoints.kv_bar.show_value = show_value
        layout = _generate("GPT-5.5: 50%", t)
        col = _kv_bar_col(layout)
        content_ids = tuple(n.content_id for n in _walk(col) if n.content_id)
        assert content_ids == visible_text, (show_key, show_value, content_ids)
        assert len(_props(col, "datapoint_bar")) == 1


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

_SINGLE_SERIES = "- Return on Equity: 14.2%\n- Net Interest Margin: 3.8%\n- Efficiency Ratio: 58.3%\n"


def test_chart_leaf_props():
    layout = _generate(_SINGLE_SERIES, Theme())
    charts = _props(layout, "chart")
    assert len(charts) == 1
    node, data = charts[0]
    assert not node.children and node.type == "-"
    assert [r["label"] for r in data["rows"]] == [
        "Return on Equity",
        "Net Interest Margin",
        "Efficiency Ratio",
    ]
    # The chart replaces its rows entirely — no kv bars inside.
    assert not _props(layout, "datapoint_bar")


def test_chart_disabled_falls_back_to_kv_bars():
    t = Theme()
    t.charts.enabled = False
    layout = _generate(_SINGLE_SERIES, t)
    assert not _props(layout, "chart")
    # Chart-cleared rows render as their normal text (kv bars were cleared by
    # the grouper's chart-wins rule), with the same structure as no-theme.
    base = _generate(_SINGLE_SERIES, None)
    assert layout.to_dict() == base.to_dict()


# ---------------------------------------------------------------------------
# Toggles / gates
# ---------------------------------------------------------------------------

_ALL_FAMILIES = (
    "4/8\n\nMon-15\n\nGPT-5.5: 50%\n\n"
    "750/1800 Kcal\n\nRevenue: $129,201.40\n\n" + _SINGLE_SERIES
)


def _arrangement(node: dict):
    """A layout's SHAPE: node types, the content each cell holds, and the nesting
    — everything except the generator's width approximation.

    ``ratios`` are left out on purpose. They are an estimate the renderer
    re-measures (``_layout_row`` collapses every cell to its own natural width),
    and since ``Stack sections`` a unique run's estimate includes each piece's own
    wrap padding — so a themed run and a theme-less one report the same
    arrangement at honestly different numbers. What this test guards is that
    switching every datapoint family off changes no ARRANGEMENT, and that is what
    this compares.
    """
    return (
        node.get("type"),
        node.get("content_id"),
        [_arrangement(c) for c in node.get("children", [])],
    )


def test_no_theme_keeps_pre_feature_layout():
    layout = _generate(_ALL_FAMILIES, None)
    for key in ("datapoint_bar", "datapoint_ring", "date_chip", "chart", "kv_role"):
        assert not _props(layout, key), key


def test_all_families_disabled_keeps_pre_feature_layout():
    t = Theme()
    t.datapoints.ratio_bar.enabled = False
    t.datapoints.kv_bar.enabled = False
    t.datapoints.unit_ratio_enabled = False
    t.datapoints.date_chip.enabled = False
    t.charts.enabled = False
    layout = _generate(_ALL_FAMILIES, t)
    base = _generate(_ALL_FAMILIES, None)
    assert _arrangement(layout.to_dict()) == _arrangement(base.to_dict())


# ---------------------------------------------------------------------------
# Key / Value text roles
# ---------------------------------------------------------------------------


def _kv_theme() -> Theme:
    """A theme that states both blocks — the only thing that turns them on."""
    t = Theme()
    t.key_style = dataclasses.replace(t.text, font_size=11.0)
    t.value_style = dataclasses.replace(t.text, font_size=30.0, font_weight="bold")
    return t


def test_kv_roles_reach_both_sides_of_every_pair():
    # Uniform across displays: a pair is a display's (ADR-205), and every
    # display that draws its value as text hands both roles down alike.
    layout = _generate("CPU: 40%\nMemory: 60%\nPrice: $1 → $2 → $3", _kv_theme())
    roles = sorted(p for _, p in _props(layout, "kv_role"))
    assert roles == ["key", "key", "key", "value", "value", "value"], roles


def test_kv_role_reaches_a_value_nested_below_its_pair():
    # A VALUE that wraps its text one or two levels down still hands the role
    # all the way to the leaf — the map resolves the nearest KEY/VALUE
    # ancestor, not just the immediate parent. A bar's value holds its text.
    ast = _ast("Progress: 60%")
    nested = next(n.node_id for n in _walk(ast) if n.content == "60%")
    assert nested.count(".") == 2, nested
    layout = LayoutGenerator().generate(ast, 800.0, theme=_kv_theme())
    assert (nested, "value") in [
        (n.content_id, p) for n, p in _props(layout, "kv_role")
    ]


def test_kv_roles_are_absent_until_the_theme_states_a_block():
    # The inertness gate: a theme with neither block leaves every pair
    # unstyled by Key/Value.
    layout = _generate("Revenue: 40%", Theme())
    assert _props(layout, "kv_role") == []


def test_kv_role_skips_a_drawing_element_inside_a_value():
    # A control keeps its own styling; the value role never reaches it.
    ast = _ast("Volume: [[62%]]")
    control = next(n.node_id for n in _walk(ast) if n.type == NodeType.DRAWING_ELEMENT)
    layout = LayoutGenerator().generate(ast, 800.0, theme=_kv_theme())
    styled = {n.content_id: p for n, p in _props(layout, "kv_role")}
    assert "key" in styled.values() and control not in styled, styled


def test_the_aside_is_not_consulted_on_display_nodes():
    gen = RecordingGenerator()
    ast = _ast("GPT-5.5: 50%\n\nMon-15\n\n" + _SINGLE_SERIES)
    gen.generate(ast, 800.0, theme=aside_theme(Theme()))
    for node in gen.consulted:
        assert node.datapoint_display is None, node.datapoint_display
        assert not node.chart_group


# ---------------------------------------------------------------------------

TESTS = [
    test_ratio_bar_row_keeps_text_leaf,
    test_ratio_bar_text_side_left,
    test_date_chip_builds_card_col,
    test_date_chips_grid_when_repeated,
    test_date_chip_columns_are_chip_wide,
    test_date_chip_kind_columns_match_one_run,
    test_date_chip_disabled_stays_text,
    test_date_chip_card_style_and_fonts,
    test_unit_ratio_style_bar_vs_ring,
    test_ring_ratio_text_visibility_combinations,
    test_bar_ratio_text_visibility_combinations,
    test_compact_unit_ratio_can_hide_total_and_key,
    test_bare_ratio_can_hide_total,
    test_ring_reserves_diameter,
    test_ring_columns_are_ring_wide_whatever_the_order,
    test_ring_kind_columns_are_ring_wide,
    test_kv_percent_bar_below_by_default,
    test_kv_ratio_bar_style_uses_kv_row,
    test_kv_percent_bar_position_above,
    test_kv_percent_bar_text_visibility_combinations,
    test_chart_leaf_props,
    test_chart_disabled_falls_back_to_kv_bars,
    test_no_theme_keeps_pre_feature_layout,
    test_all_families_disabled_keeps_pre_feature_layout,
    test_kv_roles_reach_both_sides_of_every_pair,
    test_kv_role_reaches_a_value_nested_below_its_pair,
    test_kv_roles_are_absent_until_the_theme_states_a_block,
    test_kv_role_skips_a_drawing_element_inside_a_value,
    test_the_aside_is_not_consulted_on_display_nodes,
]

if __name__ == "__main__":
    print("Datapoint Layout Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓ {test.__name__}")
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} of {len(TESTS)} tests FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
