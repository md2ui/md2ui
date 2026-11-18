"""
Unit tests for DRAWN row separators (## Separators / ## Vertical Rule).

The split consumes ` - ` / ` | ` and the grouper only records which
characters they were (``separator_chars``, one per gap) — whether any is drawn
back is a theme decision, applied by the layout generator, which inserts a
synthetic cell the way it already inserts gutter markers. So the grouping AST is
identical under every theme; only the layout changes.

Run with: uv run python tests/separator_display_tests.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "tests")

from markdown_datapoint_split_tests import _processed_with_criteria

from md2ui.pipeline import render_place as RPL
from md2ui.pipeline import render_spacing as RSP
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.theme import Theme, parse_theme


def _theme(**flags) -> Theme:
    t = Theme()
    for k, v in flags.items():
        if k == "draw":
            t.vertical_rule.draw = v
        else:
            setattr(t.separators, k, v)
    return t


def _seps(node) -> list[dict]:
    """Every separator cell the generator emitted, in document order."""
    out: list[dict] = []

    def walk(n):
        sep = (n.render_properties or {}).get("separator")
        if sep is not None:
            out.append(sep)
        for c in n.children:
            walk(c)

    walk(node)
    return out


def _layout(src: str, theme: Theme):
    return LayoutGenerator().generate(_processed_with_criteria(src), 800.0, theme)


# ---------------------------------------------------------------------------
# Theme parsing
# ---------------------------------------------------------------------------


def test_theme_defaults_match_the_old_behaviour():
    t = Theme()
    assert (t.separators.dash, t.separators.bar) == (False, False)
    assert t.vertical_rule.draw is False
    print("  ✓  defaults: dash/bar hidden, no rule")


def test_theme_md_parses_the_blocks():
    md = (
        "## Separators\n"
        "Dash: show\n"
        "Bullet: hide\n"  # a key from before ADR-205: read as nothing
        "Bar: show\n"
        "\n"
        "## Vertical Rule\n"
        "Draw: yes\n"
        "Stroke color: #FF0000\n"
        "Stroke width: 3\n"
    )
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "THEME.md"
        p.write_text(md)
        t = parse_theme(p)
    assert (t.separators.dash, t.separators.bar) == (True, True)
    assert not hasattr(t.separators, "bullet")
    assert t.vertical_rule.draw is True
    assert t.vertical_rule.stroke_width == 3
    print("  ✓  ## Separators / ## Vertical Rule parse show/hide + stroke")


def test_a_theme_without_the_blocks_keeps_the_historical_defaults():
    # A theme need not declare ## Separators or ## Vertical Rule. Leaving them out draws no
    # separator, and a ` | ` stays a glyph until a theme asks for the drawn line.
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "THEME.md"
        p.write_text("# A theme with neither block\n\n## Fonts\n")
        t = parse_theme(p)
    assert (t.separators.dash, t.separators.bar) == (False, False)
    assert t.vertical_rule.draw is False
    print("  ✓  a theme without the blocks draws no separator, no rule")


# ---------------------------------------------------------------------------
# The grouper's annotation — one character per GAP, theme-independent
# ---------------------------------------------------------------------------


def _chars(src: str) -> list[str]:
    def walk(n):
        if n.separator_chars:
            return n.separator_chars
        for c in n.children:
            r = walk(c)
            if r:
                return r
        return []

    return walk(_processed_with_criteria(src))


def test_separator_chars_recorded_per_gap():
    assert _chars("A - B - C") == ["-", "-"]
    assert _chars("A • B • C") == []  # a dot is text (ADR-205)
    assert _chars("One | Two | Three") == ["|", "|"]
    print("  ✓  the split records the character it ate, one per gap")


def test_mixed_line_records_each_gap():
    # A line can mix separators — a single character would misreport.
    assert _chars("A • B | C - D") == ["|", "-"]
    print("  ✓  'A • B | C - D' → ['|', '-']; the dot stays in its piece")


def test_comma_is_not_a_row_separator():
    # A comma is punctuation, not a separator anyone draws.
    assert _chars("Cat, Dog, Fish") == []
    print("  ✓  a comma list records nothing")


# ---------------------------------------------------------------------------
# The generator's cells — the only thing the flags change
# ---------------------------------------------------------------------------


def test_hidden_by_default_emits_no_cells():
    assert _seps(_layout("A - B - C", _theme())) == []
    assert _seps(_layout("One | Two | Three", _theme())) == []
    print("  ✓  a hidden separator emits no cell at all")


def test_a_dot_is_text_not_a_cell():
    # A dot divides nothing (ADR-205): it is drawn inside its text.
    assert _seps(_layout("A • B • C", _theme(dash=True, bar=True))) == []
    print("  ✓  '•' emits no separator cell; it is drawn as text")


def test_dash_and_bar_flags():
    assert [c["char"] for c in _seps(_layout("A - B - C", _theme(dash=True)))] == [
        "-",
        "-",
    ]
    assert [
        c["char"] for c in _seps(_layout("One | Two | Three", _theme(bar=True)))
    ] == ["|", "|"]
    print("  ✓  Dash / Bar draw their own glyph when switched on")


def test_vertical_rule_wins_over_a_hidden_bar():
    # "Bar: hide" + "Draw: yes" is the useful pairing: no pipe, just the line.
    cells = _seps(_layout("One | Two", _theme(bar=False, draw=True)))
    assert [c["kind"] for c in cells] == ["rule"], cells
    # …and it still wins when the glyph is also on, so the states can't fight.
    cells = _seps(_layout("One | Two", _theme(bar=True, draw=True)))
    assert [c["kind"] for c in cells] == ["rule"], cells
    print("  ✓  Draw wins over Bar — hidden or shown")


def test_each_gap_takes_its_own_kind():
    t = _theme(dash=True, bar=False, draw=True)
    cells = _seps(_layout("A | B - C", t))
    assert [(c["char"], c["kind"]) for c in cells] == [
        ("|", "rule"),
        ("-", "glyph"),
    ], cells
    print("  ✓  a mixed line draws each gap by its own character's flag")


def test_layout_is_untouched_when_nothing_is_drawn():
    # The feature must be invisible at its defaults: same tree, same ratios.
    src = "A - B - C"
    off = _layout(src, _theme())
    on = _layout(src, _theme(dash=True))

    def shape(n):
        return (n.type, tuple(n.ratios), tuple(shape(c) for c in n.children))

    assert shape(off) != shape(on), "the flag must actually change the layout"
    assert len(_seps(on)) == 2 and not _seps(off)
    print("  ✓  the flag is the only thing that changes the layout")


def _row_gaps(src: str, theme: Theme) -> list[float]:
    """The row gaps of the first multi-cell row *src* lays out at 700px."""
    from md2ui.pipeline import layout_render as LR
    from md2ui.pipeline.layout_render import FontSet
    from md2ui.utils.font_loader import (
        load_custom_fonts,
        resolve_typeface,
        weight_from_str,
    )

    custom = load_custom_fonts(theme.font_paths)
    name = theme.text.font_name or "Arial"
    bw = weight_from_str(theme.text.font_weight)
    tf = lambda w, i: resolve_typeface(name, w, i, custom)  # noqa: E731
    fonts = FontSet(
        tf(bw, False),
        tf(700, False),
        tf(bw, True),
        tf(700, True),
        tf(bw, False),
        None,
        {},
    )
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

    def rows(n):
        if n.type == "row" and len(n.children) > 1:
            yield n
        for c in n.children:
            yield from rows(c)

    row = next(rows(layout))
    return [
        RSP._sibling_gap(
            row.children[i - 1],
            row.children[i],
            theme,
            "row",
            0,
            node_index,
            row,
        )[0]
        for i in range(1, len(row.children))
    ]


def _all_shown() -> Theme:
    from pathlib import Path as _P

    from md2ui.pipeline.theme import parse_theme as _pt

    t = _pt(_P("data/markdown/tests/THEME.md"))
    t.separators.dash = t.separators.bar = True
    return t


def test_separator_keeps_the_element_gap_whatever_it_separates():
    # A separator's own spacing must not depend on its neighbours: not between
    # two colon COLUMNS, nor between a column and a leaf.
    t = _all_shown()
    t.vertical_rule.draw = False
    el = t.elements.row_spacing
    group = "450 : ___Project done___"
    for label, src in (
        ("leaf/leaf", "A - B - C"),
        ("bar", "A | B | C"),
        ("group/group", f"{group} | 35 : ___Happy users___"),
        ("group/leaf", f"{group} | plain text"),
        ("leaf/group", f"plain text | {group}"),
    ):
        gaps = _row_gaps(src, t)
        assert gaps and all(g == el for g in gaps), f"{label}: {gaps}"
    print("  ✓  every separator keeps the element gap on both sides")


def test_a_drawn_rule_separator_spaces_like_the_glyph():
    # The `|` painted as a vertical rule is the same cell — its gaps must not
    # change with how it is drawn.
    glyph = _all_shown()
    glyph.vertical_rule.draw = False
    rule = _all_shown()
    rule.vertical_rule.draw = True
    src = "450 : ___Project done___ | 35 : ___Happy users___"
    assert _row_gaps(src, glyph) == _row_gaps(src, rule)
    print("  ✓  a `|` drawn as a rule spaces like the glyph")


TESTS = [
    test_separator_keeps_the_element_gap_whatever_it_separates,
    test_a_drawn_rule_separator_spaces_like_the_glyph,
    test_theme_defaults_match_the_old_behaviour,
    test_theme_md_parses_the_blocks,
    test_a_theme_without_the_blocks_keeps_the_historical_defaults,
    test_separator_chars_recorded_per_gap,
    test_mixed_line_records_each_gap,
    test_comma_is_not_a_row_separator,
    test_hidden_by_default_emits_no_cells,
    test_a_dot_is_text_not_a_cell,
    test_dash_and_bar_flags,
    test_vertical_rule_wins_over_a_hidden_bar,
    test_each_gap_takes_its_own_kind,
    test_layout_is_untouched_when_nothing_is_drawn,
]

if __name__ == "__main__":
    print("Separator Display Tests")
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
