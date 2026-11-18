"""Heading IDs select named section styles: standalone by default, or with
``Mode: override`` layered over the heading level, whose keys they win.

Run with: uv run python tests/fixed_section_style_tests.py
"""

import tempfile
from pathlib import Path

from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.markdown_grouper import MarkdownGrouper
from md2ui.pipeline.grouper_types import MarkdownGroupNode
from md2ui.pipeline.render_spacing import _resolve_group_spacing, _sibling_gap
from md2ui.pipeline.render_backgrounds import (
    _bg_selector,
    _paint_style_for,
    _wrap_layers,
)
from md2ui.pipeline.theme import parse_theme, resolve_section_style


THEME = """# Fixed styles
## Background styles and Spacing
### Heading 2
Background color: #AA0000
Padding: 99
Align: right

### Fixed styles
#### This is another fixed style
Background colors:
- #112233
- #445566
Corner radius: 17
Padding: 7
Align: center
"""


def _theme(text: str = THEME):
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "THEME.md"
        path.write_text(text)
        return parse_theme(path)


def _ast(markdown: str):
    grouper = MarkdownGrouper(markdown)
    grouper.process(criteria=None, detector=DataPointDetector())
    assert grouper.ast is not None
    return grouper.ast


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def test_fixed_style_declaration_uses_full_title_slug():
    theme = _theme()
    assert set(theme.fixed_sections) == {"this-is-another-fixed-style"}
    style = theme.fixed_sections["this-is-another-fixed-style"]
    assert style.bg_colors == [0xFF112233, 0xFF445566]
    assert style.padding.left == 7 and style.corner_radius == 17
    print("  ✓  a #### title becomes its complete kebab-case fixed-style key")


def test_heading_attribute_is_metadata_not_visible_text():
    ast = _ast(
        "## Visible title {#this-is-another-fixed-style-1}\n\nBody\n\n"
        "## {#this-is-another-fixed-style-2}\n\nBody two"
    )
    sections = [n for n in _walk(ast) if n.heading_group]
    assert [n.heading_id for n in sections] == [
        "this-is-another-fixed-style-1",
        "this-is-another-fixed-style-2",
    ]
    assert all(n.fixed_style_key == "this-is-another-fixed-style" for n in sections)
    visible = [n.content for n in _walk(ast) if n.type == "heading2"]
    assert visible == ["Visible title"], visible
    assert not any("{#" in n.content for n in _walk(ast))
    restored = MarkdownGroupNode.from_dict(ast.to_dict())
    restored_sections = [n for n in _walk(restored) if n.heading_group]
    assert [n.heading_id for n in restored_sections] == [n.heading_id for n in sections]
    assert all(
        n.section_style_key == "this-is-another-fixed-style" for n in restored_sections
    )
    print("  ✓  text and ID-only headings retain metadata without drawing the ID")


def test_only_numbered_kebab_ids_select_a_style():
    ast = _ast(
        "## A {#this-is-another-fixed-style}\n\n"
        "## B {#This-is-another-fixed-style-1}\n\n"
        "## C {plain-braces}\n"
    )
    sections = [n for n in _walk(ast) if n.heading_group]
    assert sections[0].heading_id == "this-is-another-fixed-style"
    assert sections[0].fixed_style_key is None
    assert sections[1].heading_id == "This-is-another-fixed-style-1"
    assert sections[1].fixed_style_key is None
    assert any("{plain-braces}" in n.content for n in _walk(ast))
    print("  ✓  only lowercase kebab IDs with a positive numeric suffix match")


def test_fixed_style_is_a_standalone_heading_replacement():
    theme = _theme(THEME.replace("Padding: 7\nAlign: center", "Align: center"))
    fixed = resolve_section_style(theme, 2, "this-is-another-fixed-style")
    ordinary = resolve_section_style(theme, 2, None)
    assert fixed is not None and ordinary is not None
    assert fixed is theme.fixed_sections["this-is-another-fixed-style"]
    assert fixed.padding.left == 0 and fixed.align == "center"
    assert ordinary is theme.sections[2]
    assert ordinary.padding.left == 99 and ordinary.align == "right"
    assert resolve_section_style(theme, 2, "unknown") is ordinary
    print("  ✓  a match replaces Heading N; an unknown ID keeps Heading N")


OVERRIDE = """# Override
## Background styles and Spacing
### Heading 2
Background colors:
- #AA0000
- #BB0000
Corner radius: 8
Padding: 99
Background image: level.png
Outer shadow:
- Offset y: 2
- Color: #00000022

### Fixed styles
#### Featured
Mode: override
Background color: #101010
Corner radius: 24
"""


def test_override_wins_its_keys_and_keeps_the_level():
    theme = _theme(OVERRIDE)
    st = resolve_section_style(theme, 2, "featured")
    assert st is not None and st is not theme.fixed_sections["featured"]
    assert st.bg_colors == [0xFF101010], "a stated list replaces the level's whole"
    assert st.corner_radius == 24
    assert st.padding.left == 99 and len(st.shadows) == 1 and st.bg_image == "level.png"
    level = theme.sections[2]
    assert level.bg_colors == [0xFFAA0000, 0xFFBB0000] and level.corner_radius == 8
    # A level with no style of its own has nothing to inherit.
    assert (
        resolve_section_style(theme, 3, "featured") is theme.fixed_sections["featured"]
    )
    print("  ✓  Mode: override wins the keys it states and keeps the level's rest")


def test_replace_stays_the_default():
    theme = _theme(OVERRIDE.replace("Mode: override\n", ""))
    st = theme.fixed_sections["featured"]
    assert resolve_section_style(theme, 2, "featured") is st
    assert st.padding.left == 0 and not st.shadows and st.bg_image is None
    replaced = _theme(OVERRIDE.replace("Mode: override", "Mode: replace"))
    assert not replaced.fixed_section_levels
    print("  ✓  no Mode (or Mode: replace) keeps the standalone replacement")


def test_override_paints_the_merged_style_and_the_level_image():
    theme = _theme(OVERRIDE)
    st, img_key = _paint_style_for("section", 2, theme, "featured")
    assert st is resolve_section_style(theme, 2, "featured")
    assert img_key == 2, "an inherited image is the level's decoded image"
    own = _theme(OVERRIDE.replace("Corner radius: 24", "Background image: own.png"))
    assert _paint_style_for("section", 2, own, "featured")[1] == "fixed:featured"
    color = _bg_selector("section", 2, None, 0, (), theme, (), "featured")
    # The inherited photo is what content sits on, named by the style that
    # paints it, so `On background color: image Featured` can reach it.
    assert color == "image:featured", color
    print("  ✓  paint reads the merged style; an inherited image keeps its key")


def test_unmatched_numbered_id_keeps_heading_rotation():
    theme = _theme()
    ast = _ast("## First\n\nA\n\n## Unknown {#not-declared-1}\n\nB\n\n## Last\n\nC")
    sections = [n for n in _walk(ast) if n.heading_group]
    assert [n.rotation_index for n in sections] == [0, 1, 2]
    layout = LayoutGenerator().generate(ast, 900.0, theme)
    unknown = next(n for n in _walk(layout) if n.heading_id == "not-declared-1")
    assert unknown.rotation_index == 1
    assert (
        resolve_section_style(theme, 2, unknown.section_style_key) is theme.sections[2]
    )
    print("  ✓  an unmatched numbered ID leaves Heading N rotation unchanged")


def test_layout_and_paint_use_the_fixed_style_and_its_own_cycle():
    theme = _theme()
    ast = _ast(
        "## A {#this-is-another-fixed-style-1}\n\nOne\n\n"
        "## Ordinary\n\nTwo\n\n"
        "## B {#this-is-another-fixed-style-2}\n\nThree"
    )
    fixed_ast = [n for n in _walk(ast) if n.fixed_style_key]
    assert [n.fixed_rotation_index for n in fixed_ast] == [0, 1]
    assert all(n.rotation_chain == () for n in fixed_ast)

    layout = LayoutGenerator().generate(ast, 900.0, theme)
    fixed_layout = [
        n
        for n in _walk(layout)
        if n.section_level == 2 and n.section_style_key == "this-is-another-fixed-style"
    ]
    assert len(fixed_layout) == 2
    colors = []
    for node in fixed_layout:
        layers = _wrap_layers(node, theme, frozenset())
        assert layers[0][2] is theme.fixed_sections["this-is-another-fixed-style"]
        colors.append(
            _bg_selector(
                "section",
                2,
                None,
                node.rotation_index,
                node.rotation_chain,
                theme,
                node.rotation_path,
                node.section_style_key,
            )
        )
    assert colors == [0xFF112233, 0xFF445566]
    print("  ✓  fixed instances measure and paint from an independent color cycle")


BAND = "# {#band-1}\n\n## One\nTwo short lines.\n\n## Two\nTwo short lines.\n"
BAND_THEME = """## Styling & Spacing
### Heading 1
Spacing: 12
### Heading 2
Padding: 16
### Fixed styles
#### Band
%s
"""


def _grid_gap(band_style: str, width: float = 600.0) -> float | None:
    """The column gap between the band's two gridded cards, or None when the
    generator stacked them instead."""
    theme = _theme(BAND_THEME % band_style)
    layout = LayoutGenerator().generate(_ast(BAND), width, theme)
    row = next((n for n in _walk(layout) if n.grid), None)
    if row is None:
        return None
    return _sibling_gap(row.children[0], row.children[1], theme, "row", 1, {}, row)[0]


def test_gridded_child_sections_take_the_enclosing_fixed_style_gap():
    """A fixed style's ``Spacing`` is the gap between its child sections on both
    axes: gridded side by side they space as they do stacked, not at the
    heading level the style replaces (THEME_GUIDE §3)."""
    assert _grid_gap("Spacing: 40") == 40
    assert _grid_gap("Row spacing: 40\nCol spacing: 2") == 40
    # The generator reads the same gap: one the cards cannot fit beside stacks them.
    assert _grid_gap("Row spacing: 500") is None
    # Override keeps the level's gap when it states none; replace has no level.
    assert _grid_gap("Mode: override\nPadding: 3") == 12
    replaced = _theme(BAND_THEME % "Padding: 3")
    assert _grid_gap("Padding: 3") == _resolve_group_spacing("row", replaced)
    print("  ✓  gridded child sections take the enclosing fixed style's gap")


TESTS = [
    test_fixed_style_declaration_uses_full_title_slug,
    test_heading_attribute_is_metadata_not_visible_text,
    test_only_numbered_kebab_ids_select_a_style,
    test_fixed_style_is_a_standalone_heading_replacement,
    test_override_wins_its_keys_and_keeps_the_level,
    test_replace_stays_the_default,
    test_override_paints_the_merged_style_and_the_level_image,
    test_unmatched_numbered_id_keeps_heading_rotation,
    test_layout_and_paint_use_the_fixed_style_and_its_own_cycle,
    test_gridded_child_sections_take_the_enclosing_fixed_style_gap,
]


if __name__ == "__main__":
    print("Fixed Section Style Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:
            failed += 1
            print(f"  ✗  {test.__name__}: {type(exc).__name__}: {exc}")
    print("=" * 50)
    if failed:
        raise SystemExit(f"{failed} test(s) FAILED")
    print(f"All {len(TESTS)} tests passed.")
