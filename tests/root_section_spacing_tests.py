"""
Unit tests for SECTION-GAP OWNERSHIP: a level's `Spacing` is the gap between its
own child sections, at every level including the root.

`### Root → Spacing` therefore owns the gap between the top-level `# ` bands, and
`### Heading 1 → Spacing` owns the rhythm between the `## ` sections inside one,
so closing the gap between two bands leaves the rhythm inside them alone.

Root is tri-state (`float | None`), so a declared value — `0` included —
wins, and an unset root walks the same fallback chain a heading level walks:
group spacing, then element spacing, then 0.

Also pins the generator/renderer mirror: `generator_units._cell_gap` calls the
renderer's `_resolve_section_spacing` rather than keeping a second copy of the
rule, so the two cannot disagree about a top-level gap.

Run with: uv run root_section_spacing_tests.py
"""

from layout_bento_tests import _ast, _group, _section
from md2ui.pipeline.generator_units import _cell_gap
from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.render_spacing import _sibling_gap
from md2ui.pipeline.theme import SectionStyle, Theme

ELEMENT_ROW, ELEMENT_COL = 8.0, 4.0
GROUP = 16.0
H1, H2 = 32.0, 20.0
ROOT = 60.0

IDX: dict = {}


def _theme(root_spacing: float | None = None) -> Theme:
    """The shipped shape: element < group < heading spacing, with the root's own
    value passed in (None = the key was never written)."""
    t = Theme()
    t.elements.row_spacing = ELEMENT_ROW
    t.elements.col_spacing = ELEMENT_COL
    t.elements.group_row_spacing = GROUP
    t.elements.group_col_spacing = GROUP
    t.sections[1] = SectionStyle(row_spacing=H1, col_spacing=H1)
    t.sections[2] = SectionStyle(row_spacing=H2, col_spacing=H2)
    t.root.row_spacing = root_spacing
    t.root.col_spacing = root_spacing
    return t


def _band(level: int) -> LayoutNode:
    """A section-owner group: the node `_opens_section` keys on."""
    n = LayoutNode(type="col", ratios=[], children=[])
    n.section_level = level
    return n


def _gap(a: LayoutNode, b: LayoutNode, theme: Theme, axis="col", owner=0) -> float:
    return _sibling_gap(a, b, theme, axis, owner, IDX, None)[0]


def _is_section(a: LayoutNode, b: LayoutNode, theme: Theme, owner=0) -> bool:
    return _sibling_gap(a, b, theme, "col", owner, IDX, None)[1]


def test_root_spacing_owns_the_gap_between_bands():
    """The headline: `Root → Spacing: 0` butts two `# ` bands together while
    `Heading 1 → Spacing` keeps the rhythm inside each of them."""
    t = _theme(root_spacing=0.0)
    assert _gap(_band(1), _band(1), t, owner=0) == 0.0
    # …and the H2s inside a band are untouched by that 0.
    assert _gap(_band(2), _band(2), t, owner=1) == H1
    print("  ✓  Root Spacing: 0 makes bands flush; H1 keeps the in-band rhythm")


def test_root_spacing_is_not_the_entered_heading_level():
    """The gap between two `# ` bands is Root's number, not Heading 1's."""
    t = _theme(root_spacing=ROOT)
    assert _gap(_band(1), _band(1), t, owner=0) == ROOT
    assert ROOT != H1  # the test would prove nothing if they matched
    print("  ✓  band ↔ band reads Root → Spacing, not Heading 1 → Spacing")


def test_declared_root_values_differ():
    """`Spacing: 0` and `Spacing: 60` on Root give different gaps."""
    zero = _gap(_band(1), _band(1), _theme(root_spacing=0.0), owner=0)
    sixty = _gap(_band(1), _band(1), _theme(root_spacing=ROOT), owner=0)
    assert zero != sixty, "Root → Spacing is inert again"
    assert (zero, sixty) == (0.0, ROOT)
    print("  ✓  Root Spacing 0 vs 60 resolve to different gaps")


def test_unset_root_falls_back_to_group_spacing():
    """An unwritten `Root → Spacing` walks the same chain a heading level walks —
    group, then element — rather than collapsing to 0 or borrowing Heading 1."""
    t = _theme(root_spacing=None)
    assert _gap(_band(1), _band(1), t, owner=0) == GROUP
    print("  ✓  unset Root falls back to the group gap")


def test_unset_root_and_unset_group_falls_back_to_element():
    t = _theme(root_spacing=None)
    t.elements.group_row_spacing = None
    t.elements.group_col_spacing = None
    assert _gap(_band(1), _band(1), t, "col", owner=0) == ELEMENT_COL
    assert _gap(_band(1), _band(1), t, "row", owner=0) == ELEMENT_ROW
    print("  ✓  unset Root + unset Group falls through to the element gap")


def test_nested_ownership_unchanged():
    """The enclosing level owns the gap at every depth."""
    t = _theme(root_spacing=ROOT)
    assert _gap(_band(2), _band(2), t, owner=1) == H1  # H2s inside an H1
    assert _gap(_band(3), _band(3), t, owner=2) == H2  # H3s inside an H2
    print("  ✓  nested section gaps still come from the enclosing level")


def test_unstyled_enclosing_level_still_falls_back_to_group():
    """A heading level that declares no Spacing falls to the group gap, whatever
    the root declares."""
    t = _theme(root_spacing=ROOT)
    del t.sections[2]
    assert _gap(_band(3), _band(3), t, owner=2) == GROUP
    print("  ✓  an unstyled heading level still falls back to the group gap")


def test_root_spacing_is_per_axis():
    """`Row spacing` (horizontal, the gutter between gridded bands) and
    `Col spacing` (vertical rhythm) resolve independently."""
    t = _theme()
    t.root.row_spacing = 24.0
    t.root.col_spacing = 96.0
    assert _gap(_band(1), _band(1), t, "row", owner=0) == 24.0
    assert _gap(_band(1), _band(1), t, "col", owner=0) == 96.0
    print("  ✓  Root Row/Col spacing resolve independently")


def test_root_owned_boundary_is_still_flagged_a_section():
    """The `is_section` half of the return drives the debug overlay; a top-level
    boundary is still a section boundary, whoever owns its number."""
    t = _theme(root_spacing=0.0)
    assert _is_section(_band(1), _band(1), t, owner=0) is True
    print("  ✓  a root-owned band boundary still reports is_section")


def test_content_before_the_first_heading():
    """A leaf followed by the document's first section is a root-owned boundary
    too — one side opens a section, and nothing encloses the pair."""
    leaf = LayoutNode(type="-", ratios=[], children=[], content_id="c1")
    t = _theme(root_spacing=ROOT)
    assert _gap(leaf, _band(1), t, owner=0) == ROOT
    print("  ✓  content ↔ first section is owned by Root")


def _unit(level: int):
    """A grouper-side heading unit, as `_cell_gap` expects one."""
    return _ast(_group(_section(level))).children[0]


def test_generator_mirrors_the_renderer_at_the_root():
    """`_cell_gap` and `_sibling_gap` both read Root for a top-level heading
    unit."""
    for root_spacing in (0.0, ROOT, None):
        t = _theme(root_spacing=root_spacing)
        for axis in ("row", "col"):
            assert (
                _cell_gap(_unit(1), t, axis, owner_level=0)
                == _sibling_gap(_band(1), _band(1), t, axis, 0, IDX, None)[0]
            ), f"mirror broken at Root Spacing {root_spacing} on {axis}"
    print("  ✓  generator _cell_gap mirrors _sibling_gap at the root")


def test_generator_mirrors_the_renderer_when_nested():
    t = _theme(root_spacing=ROOT)
    for owner in (1, 2):
        for axis in ("row", "col"):
            assert (
                _cell_gap(_unit(owner + 1), t, axis, owner_level=owner)
                == (
                    _sibling_gap(
                        _band(owner + 1), _band(owner + 1), t, axis, owner, IDX, None
                    )[0]
                )
            )
    print("  ✓  generator _cell_gap mirrors _sibling_gap at nested levels")


def test_default_theme_gap_is_unchanged():
    """A bare `Theme()` (no THEME.md) declares nothing anywhere, so the chain
    lands on the element spacing default."""
    t = Theme()
    assert t.root.col_spacing is None
    assert _gap(_band(1), _band(1), t, "col", owner=0) == t.elements.col_spacing
    assert _gap(_band(1), _band(1), t, "row", owner=0) == t.elements.row_spacing
    print("  ✓  the default Theme() spaces top-level bands as before")


TESTS = [
    test_root_spacing_owns_the_gap_between_bands,
    test_root_spacing_is_not_the_entered_heading_level,
    test_declared_root_values_differ,
    test_unset_root_falls_back_to_group_spacing,
    test_unset_root_and_unset_group_falls_back_to_element,
    test_nested_ownership_unchanged,
    test_unstyled_enclosing_level_still_falls_back_to_group,
    test_root_spacing_is_per_axis,
    test_root_owned_boundary_is_still_flagged_a_section,
    test_content_before_the_first_heading,
    test_generator_mirrors_the_renderer_at_the_root,
    test_generator_mirrors_the_renderer_when_nested,
    test_default_theme_gap_is_unchanged,
]

if __name__ == "__main__":
    print("Root Section Spacing Tests")
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
