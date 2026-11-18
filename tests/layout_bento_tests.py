"""
Unit tests for the bento (Mondrian mosaic) layout mode: LayoutGenerator packs
each contiguous run of TARGET-LEVEL heading sections into an order-preserving
guillotine grid (integer span ratios on `bento` rows). The target is one heading
level — the theme's `## Content arrangement` > `### Bento` > `Heading level`, or
the shallowest level with 3+ sections in a row; whoever holds the run (the root
included) is the container, and its other children — its own heading, a lead-in
paragraph — stay full width. Toggled by the theme's `Layout: bento` root key or
`LayoutGenerator.bento_override`.
Run with: uv run layout_bento_tests.py
"""

import os
import tempfile
from pathlib import Path

from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.grouper_annotate import _stamp_leaf_kinds
from md2ui.pipeline.grouper_split_criteria import SplitCriteria
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.markdown_grouper import (
    ASTPatternAnalyzer,
    MarkdownGroupNode,
    MarkdownGrouper,
)
from md2ui.pipeline.theme import RootTheme, Theme, parse_theme

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER_FIXTURE = os.path.join(REPO, "data/markdown/tests/tests-hierarchy.md")


# ---------------------------------------------------------------------------
# Fixture builders (synthetic grouped ASTs, mirroring the grouper's flags)
# ---------------------------------------------------------------------------

_ids = iter(range(10_000))


def _leaf(content: str = "some short text", cat: str = "short") -> dict:
    return {
        "node_id": f"n{next(_ids)}",
        "type": "text",
        "content": content,
        "content_length_category": cat,
        "text_length_category": cat,
    }


def _group(*children: dict, **flags) -> dict:
    d = {
        "node_id": f"n{next(_ids)}",
        "type": "group",
        "content": "",
        "children": list(children),
    }
    d.update(flags)
    return d


def _title(level: int) -> dict:
    """A section's own title leaf, as the grouper types it (`heading{N}`)."""
    d = _leaf(f"Heading level {level}", "very_short")
    d["type"] = f"heading{level}"
    return d


def _section(level: int, *children: dict) -> dict:
    return _group(
        _title(level),
        *children,
        heading_group=True,
        heading_level=level,
    )


def _ast(d: dict) -> MarkdownGroupNode:
    root = MarkdownGroupNode.from_dict(d)
    ASTPatternAnalyzer(root).fingerprints(include_unique=True)
    _stamp_leaf_kinds(root)
    return root


def _two_level_doc(n_cells: int = 6) -> MarkdownGroupNode:
    """One h1 section holding *n_cells* h2 sections (the typical corpus shape)."""
    cells = [_section(2, _leaf(f"cell body {i}", "medium")) for i in range(n_cells)]
    return _ast(_group(_section(1, *cells)))


def _single_level_doc(n_sections: int = 4) -> MarkdownGroupNode:
    """Root with several h1 sections and nothing deeper."""
    secs = [_section(1, _leaf(f"body {i}", "short")) for i in range(n_sections)]
    return _ast(_group(*secs))


# ---------------------------------------------------------------------------
# Tree inspection helpers
# ---------------------------------------------------------------------------


def _leaves(n: LayoutNode, out: list) -> list:
    if n.type == "-":
        out.append(n.content_id)
    for c in n.children:
        _leaves(c, out)
    return out


def _walk(n: LayoutNode):
    yield n
    for c in n.children:
        yield from _walk(c)


def _bento_rows(layout: LayoutNode) -> list[LayoutNode]:
    return [n for n in _walk(layout) if n.type == "row" and n.bento]


def _bento_nodes(layout: LayoutNode) -> list[LayoutNode]:
    return [n for n in _walk(layout) if n.bento]


def _gen(ast: MarkdownGroupNode, width: float, bento: bool, measure=None):
    gen = LayoutGenerator()
    gen.bento_override = bento
    return gen.generate(ast, width, measure=measure)


def _root_row_spans(layout: LayoutNode) -> list[float]:
    """Sum of span ratios for each bento row directly under the mosaic col."""
    sums = []
    for n in _walk(layout):
        if n.type == "row" and n.bento:
            sums.append(sum(n.ratios))
    return sums


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_theme_layout_key():
    assert RootTheme().layout == "default"
    src = "# T\n\n## Background styles and Spacing\n\n### Root\nLayout: Bento\n"
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        theme = parse_theme(Path(path))
    finally:
        os.unlink(path)
    assert theme.root.layout == "bento", theme.root.layout
    print("  ✓  theme root `Layout: Bento` parses; default is 'default'")


def test_order_preserved_all_leaves_once():
    grouper = MarkdownGrouper(Path(RENDER_FIXTURE).read_text())
    grouper.process(SplitCriteria(), DataPointDetector())
    assert grouper.ast is not None
    ast = _ast(grouper.ast.to_dict())
    for width in (400.0, 800.0, 1280.0):
        expected = _leaves(_gen(ast, width, bento=False), [])
        got = _leaves(_gen(ast, width, bento=True), [])
        assert got == expected, f"leaf order differs at {width}px"
        assert len(set(got)) == len(got), f"duplicate leaves at {width}px"
    print("  ✓  bento preserves document leaf order (400/800/1280px), no dupes")


def test_spans_are_integral_and_bounded():
    ast = _two_level_doc(8)
    for width, lo, hi in ((1280.0, 3, 5), (400.0, 1, 3)):
        layout = _gen(ast, width, bento=True)
        rows = _bento_rows(layout)
        if width >= 760.0:
            assert rows, f"no mosaic rows at {width}px"
        for row in rows:
            assert all(r == int(r) and r >= 1 for r in row.ratios), row.ratios
            assert lo <= sum(row.ratios) <= hi, (
                f"row spans {row.ratios} sum outside [{lo},{hi}] at {width}px"
            )
        # every row's span sum is at most the width-derived division count
    print("  ✓  bento row ratios are positive ints; sums within division bounds")


def test_divisions_by_width():
    ast = _two_level_doc(8)
    wide = max(_root_row_spans(_gen(ast, 1280.0, bento=True)), default=0)
    assert 3 <= wide <= 5, f"wide divisions {wide} outside [3,5]"
    narrow = max(_root_row_spans(_gen(ast, 400.0, bento=True)), default=0)
    assert narrow <= 3, f"narrow divisions {narrow} above 3"
    print("  ✓  divisions: 3–5 at 1280px, ≤3 at 400px")


def test_long_paragraph_full_width():
    # >100 words → long_paragraph (ASTPatternAnalyzer recomputes categories
    # from the real content, so the fixture needs genuinely long text).
    long_text = " ".join(f"word{i}" for i in range(120))
    cells = [_section(2, _leaf(f"c{i}", "short")) for i in range(5)]
    cells.insert(2, _section(2, _leaf(long_text, "long_paragraph")))
    ast = _ast(_group(_section(1, *cells)))
    layout = _gen(ast, 1280.0, bento=True)
    # Find the long-paragraph leaf and assert no bento-row ancestor.
    target = next(
        n.node_id
        for n in _walk_ast(ast)
        if n.content_length_category == "long_paragraph"
    )

    def contains(n: LayoutNode) -> bool:
        return any(c.content_id == target for c in _walk(n))

    for row in _bento_rows(layout):
        assert not contains(row), "long_paragraph cell placed inside a bento row"
    print("  ✓  long_paragraph cell never shares a bento row (full-width band)")


def _walk_ast(n: MarkdownGroupNode):
    yield n
    for c in n.children:
        yield from _walk_ast(c)


def test_fake_measurer_used():
    ast = _two_level_doc(6)
    calls: list[tuple[float, float]] = []

    def measure(_sub: LayoutNode, width: float) -> float:
        calls.append((width, 0.0))
        return 120.0

    layout = _gen(ast, 1280.0, bento=True, measure=measure)
    assert calls, "measure callback was never invoked"
    expected = _leaves(_gen(ast, 1280.0, bento=False), [])
    assert _leaves(layout, []) == expected
    print(f"  ✓  measure callback drives the search ({len(calls)} calls)")


def test_no_measurer_fallback():
    ast = _two_level_doc(6)
    layout = _gen(ast, 1280.0, bento=True, measure=None)
    assert _bento_nodes(layout), "no mosaic without a measurer"
    expected = _leaves(_gen(ast, 1280.0, bento=False), [])
    assert _leaves(layout, []) == expected
    print("  ✓  measure=None falls back to the height estimate, tree valid")


def test_default_mode_untouched():
    ast = _two_level_doc(6)
    gen = LayoutGenerator()
    before = gen.generate(ast, 1280.0).to_dict()
    # Run bento in between, then default again on the same generator: no
    # stale bento state may leak into the default output.
    gen.bento_override = True
    gen.generate(ast, 1280.0)
    gen.bento_override = False
    after = gen.generate(ast, 1280.0).to_dict()
    assert before == after, "bento state leaked into default mode"
    assert not _bento_nodes(gen.generate(ast, 1280.0)), "bento node in default"
    print("  ✓  default mode emits no bento nodes; no state leaks across calls")


def test_cell_selection_two_level():
    layout = _gen(_two_level_doc(6), 1280.0, bento=True)
    rows = _bento_rows(layout)
    assert rows, "no mosaic in a two-level doc"
    # Target is level 2 (level 1 has a run of one), so the cells are the h2
    # sections and the h1's own title is NOT one of them: the section builds as
    # col[title, mosaic].
    assert all(c.section_level in (None, 2) for row in rows for c in row.children), (
        "a non-h2 node became a cell"
    )
    section = next(n for n in _walk(layout) if n.type == "col" and n.section_level == 1)
    assert not section.bento, "the h1 section itself was tiled"
    assert section.children[0].content_id is not None, (
        "the h1 title is not the first stacked child"
    )
    assert any(c.bento for c in section.children), (
        "the mosaic is not a sibling of the title"
    )
    print("  ✓  two-level doc: h2 sections tile, the h1 title stays full width")


def test_root_container_without_wrapper():
    """A run of h2 sections at the ROOT tiles, with no h1 above them.

    The deeper h3s must NOT steal the target — they stack inside their tiles.
    """
    secs = [
        _section(2, _leaf(f"body {i}", "short"), _section(3, _leaf("deep")))
        for i in range(3)
    ]
    layout = _gen(_ast(_group(*secs)), 1280.0, bento=True)
    rows = _bento_rows(layout)
    assert rows, "root run of h2 sections did not tile"
    cells = [c for row in rows for c in row.children]
    assert any(c.section_level == 2 for c in cells), "h2 sections are not cells"
    assert all(c.section_level != 3 for c in cells), "an h3 became a cell"
    print("  ✓  root tiles its h2 run without a wrapping h1; h3s stay nested")


def test_heading_leaf_never_a_cell():
    """No heading-typed node is ever a direct child of a bento row."""
    for ast in (_two_level_doc(6), _single_level_doc(4)):
        layout = _gen(ast, 1280.0, bento=True)
        for row in _bento_rows(layout):
            for cell in row.children:
                assert cell.type != "-" or cell.section_level is not None, (
                    "a bare leaf (the orphaned heading) became a cell"
                )
    print("  ✓  heading leaves never tile — only sections do")


def test_lead_in_stays_full_width():
    """A non-section sibling before the run keeps its place, at full width."""
    ast = _ast(
        _group(
            _leaf("a lead-in paragraph", "paragraph"),
            *[_section(2, _leaf(f"body {i}", "short")) for i in range(3)],
        )
    )
    layout = _gen(ast, 1280.0, bento=True)
    rows = _bento_rows(layout)
    assert rows, "the h2 run did not tile"
    root = layout.children[0]
    assert root.type == "col" and not root.bento
    assert not root.children[0].bento, "the lead-in was swallowed by the mosaic"
    assert any(c.bento for c in root.children), "no mosaic beside the lead-in"
    print("  ✓  lead-in prose stacks full width above the mosaic")


def test_manual_level_overrides_auto():
    """The theme's `Heading level` wins over the automatic pick."""
    secs = [
        _section(2, *[_section(3, _leaf(f"d{i}{j}")) for j in range(3)])
        for i in range(3)
    ]
    ast = _ast(_group(*secs))
    auto = _bento_rows(_gen(ast, 1280.0, bento=True))
    assert any(c.section_level == 2 for row in auto for c in row.children), (
        "auto did not target level 2"
    )

    gen = LayoutGenerator()
    gen.bento_override = True
    theme = Theme()
    theme.bento.heading_level = 3
    manual = _bento_rows(gen.generate(_ast(_group(*secs)), 1280.0, theme=theme))
    cells = [c for row in manual for c in row.children]
    assert cells and all(c.section_level != 2 for c in cells), (
        "level 3 override still tiled the h2 sections"
    )
    assert any(c.section_level == 3 for c in cells), "h3 sections did not tile"
    print("  ✓  theme `Heading level` overrides the automatic target")


def test_manual_level_without_run_stacks():
    """A named level with no qualifying run stacks — it does not fall back."""
    gen = LayoutGenerator()
    gen.bento_override = True
    theme = Theme()
    theme.bento.heading_level = 5
    layout = gen.generate(_single_level_doc(4), 1280.0, theme=theme)
    assert not _bento_nodes(layout), "an unmatched level still built a mosaic"
    print("  ✓  a target level with no run → plain stack, no silent fallback")


def test_theme_bento_level_parses():
    src = (
        "# T\n\n## Background styles and Spacing\n\n### Root\nLayout: Bento\n"
        "\n## Content arrangement\n\n### Bento\nHeading level: 3\n"
    )
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "THEME.md"
        f.write_text(src)
        theme = parse_theme(f)
    assert theme.root.layout == "bento"
    assert theme.bento.heading_level == 3
    assert Theme().bento.heading_level is None, "default target is not None"
    print("  ✓  ## Content arrangement > ### Bento > Heading level parses")


def test_cell_selection_single_level():
    layout = _gen(_single_level_doc(4), 1280.0, bento=True)
    rows = _bento_rows(layout)
    assert rows, "no mosaic in a single-level doc"
    # Cells are the h1 sections themselves: some bento row child is level 1.
    assert any(c.section_level == 1 for row in rows for c in row.children), (
        "h1 sections are not the cells"
    )
    print("  ✓  single-level doc: the h1 sections themselves are the cells")


def test_too_few_cells_falls_back():
    # The h1 section's children are heading leaf + 1 subsection = 2 cells.
    ast = _ast(_group(_section(1, _section(2, _leaf()))))
    layout = _gen(ast, 1280.0, bento=True)
    assert not _bento_nodes(layout), "mosaic built with fewer than 3 cells"
    ast2 = _ast(_group(_leaf("no headings at all", "short")))
    layout2 = _gen(ast2, 1280.0, bento=True)
    assert not _bento_nodes(layout2), "mosaic built without headings"
    print("  ✓  <3 cells or no headings → default layout (no bento nodes)")


TESTS = [
    test_theme_layout_key,
    test_order_preserved_all_leaves_once,
    test_spans_are_integral_and_bounded,
    test_divisions_by_width,
    test_long_paragraph_full_width,
    test_fake_measurer_used,
    test_no_measurer_fallback,
    test_default_mode_untouched,
    test_cell_selection_two_level,
    test_cell_selection_single_level,
    test_too_few_cells_falls_back,
    test_root_container_without_wrapper,
    test_heading_leaf_never_a_cell,
    test_lead_in_stays_full_width,
    test_manual_level_overrides_auto,
    test_manual_level_without_run_stacks,
    test_theme_bento_level_parses,
]

if __name__ == "__main__":
    print("Bento Layout Tests")
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
