"""Per-level text roles declared under ``## Styling & Spacing``.

The grouper stamps structural ancestry once; the theme stores partial patches;
measurement and paint resolve the same outer-to-inner role cascade.

Run with: uv run python tests/level_text_style_tests.py
"""

import tempfile
from pathlib import Path

import skia

from md2ui.pipeline.grouper_annotate import _stamp_finished_tree
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.render_colors import _replace_color
from md2ui.pipeline.render_style import (
    FontSet,
    _effective_text_fonts,
    _kv_role_style,
    scoped_text_style,
)
from md2ui.pipeline.render_text_scopes import _TEXT_TYPEFACES
from md2ui.pipeline.theme import Theme, parse_theme


def _theme(markdown: str) -> Theme:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "THEME.md"
        path.write_text(markdown)
        return parse_theme(path)


def _font_set() -> FontSet:
    face = skia.Typeface.MakeDefault()
    return FontSet(face, face, face, face, face)


def test_canonical_section_parses_partial_role_patches():
    theme = _theme(
        """## Styling & Spacing
### Root
#### Text
- Font size: 15
### Heading 2
#### Text
- Font size: 19
#### Display
- Font color: #8844CC
### Unordered Lists
#### Text
- Font weight: bold
"""
    )
    root = theme.text_style_overrides["root"]["text"]
    heading = theme.text_style_overrides["heading:2"]
    unordered = theme.text_style_overrides["unordered_lists"]["text"]
    assert root.declared == {"font_size"}
    assert heading["text"].declared == {"font_size"}
    assert heading["display"].style.color == 0xFF8844CC
    assert unordered.declared == {"font_weight"}
    print("  ✓  canonical section stores only explicitly declared properties")


def test_section_aliases_and_fixed_depth_parse():
    legacy = _theme(
        """## Background styles and Spacing
### Root
#### Muted
- Font size: 10
"""
    )
    words = _theme(
        """## Styling and Spacing
### Fixed styles
#### Featured
##### Lead
- Font name: Georgia
"""
    )
    assert legacy.text_style_overrides["root"]["muted"].style.font_size == 10
    patch = words.text_style_overrides["fixed:featured"]["lead"]
    assert patch.declared == {"font_name"}
    assert patch.style.font_name == "Georgia"
    print("  ✓  legacy/word aliases and fixed-style role depth parse")


def test_elements_is_not_a_typography_scope():
    theme = _theme(
        """## Styling & Spacing
### Elements
#### Text
- Font size: 99
"""
    )
    assert theme.text_style_overrides == {}
    print("  ✓  Elements remains paint-only and cannot declare text roles")


def test_property_cascade_is_outer_to_inner():
    theme = _theme(
        """## Text Styles
Text
- Font name: Arial
- Font size: 13
- Font weight: regular
- Font color: #111111
## Styling & Spacing
### Root
#### Text
- Font name: Georgia
- Font size: 15
### Heading 2
#### Text
- Font size: 19
### Unordered Lists
#### Text
- Font weight: bold
"""
    )
    style = scoped_text_style(theme, "text", ("root", "heading:2", "unordered_lists"))
    assert style.font_name == "Georgia"
    assert style.font_size == 19
    assert style.font_weight == "bold"
    assert style.color == 0xFF111111
    print("  ✓  Root -> heading -> surface cascades property by property")


def test_every_role_resolves_locally():
    blocks = []
    for index, role in enumerate(
        ("Text", "Muted", "Lead", "Display", "Key", "Value"), 20
    ):
        blocks.extend((f"#### {role}", f"- Font size: {index}"))
    theme = _theme("## Styling & Spacing\n### Quotes\n" + "\n".join(blocks))
    scopes = ("root", "quotes")
    assert scoped_text_style(theme, "text", scopes).font_size == 20
    assert scoped_text_style(theme, "muted", scopes).font_size == 21
    assert scoped_text_style(theme, "lead", scopes).font_size == 22
    assert scoped_text_style(theme, "display", scopes).font_size == 23
    assert _kv_role_style(theme, "key", scopes).font_size == 24
    assert _kv_role_style(theme, "value", scopes).font_size == 25
    print("  ✓  all six public roles resolve through a local scope")


def test_grouper_annotation_orders_heading_fixed_and_surfaces():
    root = MarkdownGroupNode(type=NodeType.GROUP)
    heading = MarkdownGroupNode(type=NodeType.GROUP)
    heading.heading_group = True
    heading.heading_level = 2
    heading.fixed_style_key = "featured"
    task = MarkdownGroupNode(type=NodeType.TASK_OPEN)
    quote = MarkdownGroupNode(type=NodeType.BLOCKQUOTE)
    leaf = MarkdownGroupNode(content="copy", type=NodeType.TEXT)
    root.children = [heading]
    heading.children = [task]
    task.children = [quote]
    quote.children = [leaf]
    _stamp_finished_tree(root)
    assert leaf.text_style_chain == (
        "root",
        "heading:2",
        "fixed:featured",
        "unordered_lists",
        "task_lists",
        "quotes",
    )
    restored = MarkdownGroupNode.from_dict(root.to_dict())
    restored_leaf = restored.children[0].children[0].children[0].children[0]
    assert restored_leaf.text_style_chain == leaf.text_style_chain
    print("  ✓  ancestry order and AST round-trip are stable")


def test_scoped_font_family_is_used_by_effective_measurement_style():
    theme = _theme(
        """## Styling & Spacing
### Heading 2
#### Text
- Font name: Georgia
- Font weight: bold
- Font size: 18
"""
    )
    base = _font_set()
    target = skia.Typeface.MakeFromName("serif", skia.FontStyle.Bold())
    assert target is not None
    old = dict(_TEXT_TYPEFACES)
    try:
        _TEXT_TYPEFACES.clear()
        _TEXT_TYPEFACES[("georgia", 700)] = (target, target, target, target)
        effective, size = _effective_text_fonts(
            "text", 0, base, theme, text_scopes=("root", "heading:2")
        )
        assert effective.typeface == target
        assert size == 18
    finally:
        _TEXT_TYPEFACES.clear()
        _TEXT_TYPEFACES.update(old)
    print("  ✓  a local Font name reaches the shared measure/draw resolver")


def test_local_colors_reach_background_replacements():
    theme = _theme(
        """## Styling & Spacing
### Quotes
#### Display
- Font color: #8844CC
## Color Replacements
On background color: #101010
- Text color: #8844CC, Replacement: #FFFFFF
"""
    )
    color = scoped_text_style(theme, "display", ("root", "quotes")).color
    assert _replace_color(color, (0xFF101010,), theme, "text") == 0xFFFFFFFF
    print("  ✓  local role colors flow through background color replacements")


TESTS = [
    test_canonical_section_parses_partial_role_patches,
    test_section_aliases_and_fixed_depth_parse,
    test_elements_is_not_a_typography_scope,
    test_property_cascade_is_outer_to_inner,
    test_every_role_resolves_locally,
    test_grouper_annotation_orders_heading_fixed_and_surfaces,
    test_scoped_font_family_is_used_by_effective_measurement_style,
    test_local_colors_reach_background_replacements,
]


if __name__ == "__main__":
    print("Level Text Style Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:
            print(f"  ✗  {test.__name__}: {exc}")
            failed += 1
    print("=" * 50)
    if failed:
        raise SystemExit(f"{failed} test(s) FAILED")
    print(f"All {len(TESTS)} tests passed.")
