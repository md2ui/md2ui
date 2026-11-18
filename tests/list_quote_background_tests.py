"""List-item and blockquote backgrounds use the shared section paint machinery.

Run with: uv run python tests/list_quote_background_tests.py
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from md2ui.pipeline import layout_render as LR
from md2ui.pipeline import render_backgrounds as RBG
from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.markdown_grouper import MarkdownGrouper
from md2ui.pipeline.theme import Theme, parse_theme


THEME = """# Structural surfaces
## Background styles and Spacing
### Unordered Lists
Background colors:
- #112233
- #445566
Padding: 11
Corner radius: 7
### Numbered Lists
Background color: #223344
Padding: 12
### Quotes
Background color: #334455
Padding: 13
"""


def _theme(text: str = THEME) -> Theme:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(text)
        path = Path(f.name)
    try:
        return parse_theme(path)
    finally:
        path.unlink()


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _layout(markdown: str, theme: Theme):
    grouper = MarkdownGrouper(markdown)
    grouper.process(criteria=None, detector=DataPointDetector())
    assert grouper.ast is not None
    return LayoutGenerator().generate(grouper.ast, 800.0, theme)


def test_background_blocks_parse_independently():
    theme = _theme()
    assert theme.unordered_lists.bg_colors == [0xFF112233, 0xFF445566]
    assert theme.unordered_lists.padding.left == 11
    assert theme.unordered_lists.corner_radius == 7
    assert theme.numbered_lists.bg_colors == [0xFF223344]
    assert theme.numbered_lists.padding.left == 12
    assert theme.quotes.bg_colors == [0xFF334455]
    assert theme.quotes.padding.left == 13
    print("  ✓  unordered, numbered and quote background blocks parse separately")


def test_each_markdown_kind_gets_its_own_surface():
    theme = _theme()
    layout = _layout("- bullet\n\n1. numbered\n\n> quoted", theme)
    kinds = [n.background_kind for n in _walk(layout) if n.background_kind]
    assert kinds == ["unordered_list", "numbered_list", "quote"], kinds
    for node in (n for n in _walk(layout) if n.background_kind):
        layers = RBG._wrap_layers(node, theme, frozenset())
        assert [kind for kind, _, _ in layers] == [node.background_kind]
    print("  ✓  each marked item emits its dedicated background layer")


def test_task_items_share_the_unordered_surface():
    theme = _theme()
    layout = _layout("- [ ] open\n- [x] done", theme)
    kinds = [n.background_kind for n in _walk(layout) if n.background_kind]
    assert kinds == ["task_list", "task_list"], kinds
    for node in (n for n in _walk(layout) if n.background_kind):
        assert RBG._wrap_layers(node, theme, frozenset())[0][2] is theme.unordered_lists
    print("  ✓  task-list items fall back to the unordered-list background")


def test_task_list_background_overrides_the_fallback():
    theme = _theme(THEME + "\n### Task Lists\nBackground color: #556677\nPadding: 17\n")
    layout = _layout("- [ ] open", theme)
    node = next(n for n in _walk(layout) if n.background_kind)
    kind, _, style = RBG._wrap_layers(node, theme, frozenset())[0]
    assert kind == "task_list"
    assert style is theme.task_lists
    assert style.padding.left == 17
    print("  ✓  an active Task Lists block overrides the unordered fallback")


def test_surface_moves_onto_an_active_marker_row():
    theme = _theme(
        THEME.replace("Padding: 11", "Padding: 11\n#### Marker\nShape: circle")
    )
    layout = _layout("- bullet", theme)
    surface = next(n for n in _walk(layout) if n.background_kind)
    assert surface.type == "row"
    assert surface.background_kind == "unordered_list"
    assert all(child.background_kind is None for child in surface.children)
    print("  ✓  the list surface wraps both an active marker and its content")


def test_background_color_cycles_restart_inside_each_section():
    theme = _theme()
    layout = _layout("## First\n\n- A\n- B\n\n## Second\n\n- C\n- D", theme)
    nodes = [n for n in _walk(layout) if n.background_kind == "unordered_list"]
    assert [n.rotation_index for n in nodes] == [0, 1, 0, 1]
    colors = [
        RBG._bg_selector(
            "unordered_list",
            0,
            None,
            n.rotation_index,
            n.rotation_chain,
            theme,
            n.rotation_path,
        )
        for n in nodes
    ]
    assert colors == [0xFF112233, 0xFF445566, 0xFF112233, 0xFF445566]
    print("  ✓  structural background-color cycles restart per heading section")


def test_paint_lookup_keeps_structural_styles_and_cache_keys():
    theme = _theme()
    expected = {
        "unordered_list": (theme.unordered_lists, -6),
        "task_list": (theme.unordered_lists, -6),
        "numbered_list": (theme.numbered_lists, -7),
        "quote": (theme.quotes, -8),
    }
    for kind, pair in expected.items():
        assert RBG._paint_style_for(kind, 0, theme) == pair
    print("  ✓  structural styles survive through the final paint lookup")


def test_structural_background_images_get_distinct_cache_slots():
    theme = _theme()
    theme.unordered_lists.bg_image = "unordered.png"
    theme.task_lists.bg_image = "tasks.png"
    theme.numbered_lists.bg_image = "numbered.png"
    theme.quotes.bg_image = "quote.png"
    decoded = {
        name: object()
        for name in ("unordered.png", "tasks.png", "numbered.png", "quote.png")
    }
    with patch.object(LR, "theme_picture", side_effect=decoded.get):
        images = LR.load_background_images(theme)
    assert images[-6] is decoded["unordered.png"]
    assert images[-9] is decoded["tasks.png"]
    assert images[-7] is decoded["numbered.png"]
    assert images[-8] is decoded["quote.png"]
    print("  ✓  structural background images use distinct paint cache slots")


def test_no_element_card_paints_inside_a_list_surface():
    # A multi-line item is glued, so the generator makes it a card; under a
    # painted list surface that card would compete with the item's own
    # background. The glue stays -- only the card is baked off.
    theme = _theme(THEME + "### Elements\nBackground color: #FF0000\nPadding: 9\n")
    layout = _layout("- Key: value\n  more\n\nA glued\ncard", theme)
    assert any(n.is_card for n in _walk(layout)), "the fixture must make cards"
    RBG.bake_list_cards(layout, theme)
    items = [n for n in _walk(layout) if n.background_kind == "unordered_list"]
    assert items and not any(n.is_card for i in items for n in _walk(i))
    assert any(n.is_card for n in _walk(layout)), "a card outside a list keeps it"
    print("  ✓  element cards stop at a painted list surface; others keep theirs")


MERGED = """# Merged list
## Styling & Spacing
### Unordered Lists
Merge rows: yes
Background color: #FFFFFF
Corner radius: 20
Padding: 14
#### Horizontal Rule
Stroke color: #112233
Stroke width: 2
"""

_ROWS = "- **Apple** ... 343.47\n- **Microsoft** ... 528.95\n- **NVIDIA** ... 214.14\n"


def _scene(markdown: str, theme: Theme):
    from md2ui import session

    grouper = MarkdownGrouper(markdown)
    grouper.process(criteria=None, detector=DataPointDetector())
    assert grouper.ast is not None
    root, index = session.prepare(grouper.ast, theme)
    fonts = session.load_fonts(theme)
    return session.build_scene(LayoutGenerator(), root, index, theme, fonts, 800.0)


def test_merged_list_paints_one_card_with_a_rule_between_rows():
    # The settings-menu / transaction-history shape: the level's surface once
    # behind the whole list, rows touching, the scoped rule at each edge they
    # share, inset by the row padding.
    scene = _scene(_ROWS, _theme(MERGED))
    shells = [b for b in scene.sections if b.kind == "unordered_list_shell"]
    rows = [b for b in scene.sections if b.kind == "list_row"]
    rules = [b for b in scene.sections if b.kind == "unordered_list_divider"]
    assert len(shells) == 1 and len(rows) == 3 and len(rules) == 2
    assert not [b for b in scene.sections if b.kind == "unordered_list"]
    shell = shells[0]
    assert (
        rows[0].y == shell.y and rows[-1].y + rows[-1].height == shell.y + shell.height
    )
    for upper, lower, rule in zip(rows, rows[1:], rules):
        assert upper.y + upper.height == lower.y, "merged rows meet with no gap"
        assert rule.height == 2 and rule.y + 1 == lower.y
        assert rule.x == shell.x + 14 and rule.width == shell.width - 28
    print("  ✓  Merge rows: one list card, rows touching, a rule between them")


def test_merged_list_rows_paint_nothing_of_their_own():
    theme = _theme(MERGED)
    st = RBG._paint_style_for("list_row", 0, theme)[0]
    assert st is None
    shell = RBG._paint_style_for("unordered_list_shell", 0, theme)[0]
    assert shell is not None and shell.bg_colors == [0xFFFFFFFF]
    rule = RBG._paint_style_for("unordered_list_divider", 0, theme)[0]
    assert rule is not None and rule.bg_colors == [0xFF112233]
    print("  ✓  a merged row paints nothing; the shell and the rule paint the level's")


def test_a_rule_of_no_width_leaves_merged_rows_undivided():
    theme = _theme(MERGED.replace("Stroke width: 2", "Stroke width: 0"))
    scene = _scene(_ROWS, theme)
    assert [b for b in scene.sections if b.kind == "unordered_list_shell"]
    assert not [b for b in scene.sections if b.kind.endswith("_divider")]
    print("  ✓  Stroke width: 0 under the list level draws no rule")


def test_without_merge_rows_each_item_keeps_its_card():
    scene = _scene(_ROWS, _theme(MERGED.replace("Merge rows: yes\n", "")))
    kinds = [b.kind for b in scene.sections]
    assert kinds.count("unordered_list") == 3
    assert not [
        k for k in kinds if k.endswith(("_shell", "_divider")) or k == "list_row"
    ]
    print("  ✓  without Merge rows every item paints its own surface")


def test_a_run_that_grids_keeps_a_card_per_tile():
    # Items a separator divides are groups, and their run grids as tiles: a
    # grid is separate cards by nature, so Merge rows leaves it alone.
    from md2ui.pipeline import render_list_surfaces as RLS

    tiles = "- **Wi-Fi** - Free\n- **Pool** - Heated\n- **Gym** - Open 24h\n"
    scene = _scene(tiles, _theme(MERGED))
    assert not any(RLS.is_row(n) for n in _walk(scene.layout))
    assert [b.kind for b in scene.sections].count("unordered_list") == 3
    print("  ✓  a run of list items that grids keeps one card per tile")


def test_the_shell_replaces_the_runs_element_card():
    # Where element cards draw, the run of items is glued into one: under a
    # merged list that card has the shell's extent and would paint over it.
    theme = _theme(MERGED + "### Elements\nBackground color: #FF0000\nPadding: 9\n")
    scene = _scene(_ROWS, theme)
    assert [b.kind for b in scene.sections].count("unordered_list_shell") == 1
    assert not [b for b in scene.sections if b.kind == "card"]
    print("  ✓  a merged list's shell replaces the element card around its run")


_LIST_CARD = """# List card
## Styling & Spacing
### Elements
Background color: #FF0000
Padding: 9
### Unordered Lists
Padding: 6
"""


def _cards(markdown: str, extra: str = "") -> int:
    scene = _scene(markdown, _theme(_LIST_CARD + extra))
    return [b.kind for b in scene.sections].count("card")


def test_a_list_alone_has_no_card_by_default():
    tight = "## Plans\n\n- Basic\n- Pro\n- Team\n"
    assert _cards(tight) == 0, "no card around a list alone by default"
    assert _cards(tight, "List card: yes\n") == 1
    grid = "## Plans\n\n- A - B\n- C - D\n- E - F\n"
    assert _cards(grid) == 0, "gridded or stacked alike"
    print("  ✓  a run of list items alone has no card unless `List card: yes`")


def test_a_line_glued_to_the_list_keeps_the_card():
    lead_in = "## Lead\n\nIngredients:\n- Flour\n- Sugar\n"
    assert _cards(lead_in) == 1
    print("  ✓  a lead-in glued to the list keeps the run's card")


def test_dropping_the_card_keeps_the_arrangement():
    doc = "## Plans\n\n- A - B\n- C - D\n- E - F\n- G - H\n"
    plain = _scene(doc, _theme(_LIST_CARD + "List card: yes\n"))
    off = _scene(doc, _theme(_LIST_CARD))

    def xs(scene):
        return sorted(
            {round(b.x) for b in scene.sections if b.kind == "unordered_list"}
        )

    assert len(xs(plain)) == len(xs(off)), (xs(plain), xs(off))
    print("  ✓  the items keep their arrangement; only the card goes")


TESTS = [
    test_merged_list_paints_one_card_with_a_rule_between_rows,
    test_the_shell_replaces_the_runs_element_card,
    test_a_run_that_grids_keeps_a_card_per_tile,
    test_merged_list_rows_paint_nothing_of_their_own,
    test_a_rule_of_no_width_leaves_merged_rows_undivided,
    test_without_merge_rows_each_item_keeps_its_card,
    test_background_blocks_parse_independently,
    test_each_markdown_kind_gets_its_own_surface,
    test_task_items_share_the_unordered_surface,
    test_task_list_background_overrides_the_fallback,
    test_surface_moves_onto_an_active_marker_row,
    test_background_color_cycles_restart_inside_each_section,
    test_paint_lookup_keeps_structural_styles_and_cache_keys,
    test_structural_background_images_get_distinct_cache_slots,
    test_no_element_card_paints_inside_a_list_surface,
    test_a_list_alone_has_no_card_by_default,
    test_a_line_glued_to_the_list_keeps_the_card,
    test_dropping_the_card_keeps_the_arrangement,
]


if __name__ == "__main__":
    print("List / Quote Background Tests")
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
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
