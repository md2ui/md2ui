"""
Tests for the cost of the bento search (``LayoutGenerator._build_bento``).

The search is a guillotine DP with a Pareto beam of ``BENTO_BEAM`` per state. It
builds ``row`` nodes only for the candidates the beam keeps, not for every
candidate it scores, and memoises ``band()``. Pinned here:

* the mosaic is fixed: its exact shape (spans and nesting) on a synthetic 8-cell
  run at three widths;
* the node work stays small: the rows and bento cols the search builds are
  bounded by what the beam keeps, not by what it scores.

Byte-identity over the corpus is the render snapshot's job, not this module's.

Run with: uv run tests/layout_bento_search_tests.py
"""

import re
import sys

sys.path.insert(0, "tests")

from layout_bento_tests import _gen, _two_level_doc

from md2ui.pipeline import layout_generator
from md2ui.pipeline.layout_script_parser import LayoutNode

# The expected mosaics.
_SHAPES = {
    1280.0: "layout[1280,0](col[1,1](L row*[1,4](col*[1,1](col[1,1](L L) col[1,1](L L)) "
    "row*[2,2](col*[1,1](col[1,1](L L) row*[1,1](col[1,1](L L) col*[1,1](col[1,1](L L) "
    "col[1,1](L L)))) col*[1,1](col[1,1](L L) col[1,1](L L))))))",
    900.0: "layout[900,0](col[1,1](L row*[2,1](col*[1,1](row*[1,1](col[1,1](L L) "
    "col*[1,1](col[1,1](L L) col[1,1](L L))) row*[1,1](col[1,1](L L) col*[1,1](col[1,1](L L) "
    "col[1,1](L L)))) col*[1,1](col[1,1](L L) col[1,1](L L)))))",
    500.0: "layout[500,0](col[1,1](L col*[1,1](col[1,1](L L) row*[1,1](col*[1,1,1,1](col[1,1](L L) "
    "col[1,1](L L) col[1,1](L L) col[1,1](L L)) col*[1,1,1](col[1,1](L L) col[1,1](L L) "
    "col[1,1](L L))))))",
}

# Rows / cols built inside the search. Cols include the cells' own.
_BUILT = {1280.0: (189, 173), 900.0: (58, 88), 500.0: (28, 44)}


def _shape(n: LayoutNode) -> str:
    if n.type == "-":
        return "L"
    tag = n.type + ("*" if getattr(n, "bento", False) else "")
    ratios = ",".join(str(int(r)) if r == int(r) else str(r) for r in n.ratios)
    return f"{tag}[{ratios}](" + " ".join(_shape(c) for c in n.children) + ")"


def _content_sum(n: LayoutNode) -> int:
    total, stack = 0, [n]
    while stack:
        x = stack.pop()
        if x.content_id:
            total += sum(map(ord, x.content_id))
        stack.extend(x.children)
    return total


def _measure(sub: LayoutNode, width: float) -> float:
    """Deterministic, distinct per cell, and width-sensitive, so the search has
    real trade-offs to make and a changed tie-break would show."""
    return 40.0 + (_content_sum(sub) % 7) * 23.0 + 9000.0 / max(width, 1.0)


def _generate_counting(width: float) -> tuple[LayoutNode, dict]:
    built = {"row": 0, "col": 0}
    inside = [0]
    init = LayoutNode.__init__
    search = layout_generator.LayoutGenerator._build_bento

    def counting_init(self, *args, **kwargs):
        init(self, *args, **kwargs)
        if inside[0] and self.type in built:
            built[self.type] += 1

    def counting_search(self, *args, **kwargs):
        inside[0] += 1
        try:
            return search(self, *args, **kwargs)
        finally:
            inside[0] -= 1

    LayoutNode.__init__ = counting_init
    layout_generator.LayoutGenerator._build_bento = counting_search
    try:
        layout = _gen(_two_level_doc(8), width, bento=True, measure=_measure)
    finally:
        LayoutNode.__init__ = init
        layout_generator.LayoutGenerator._build_bento = search
    return layout, built


def test_the_mosaic_is_the_one_the_search_chose_before():
    for width, expected in _SHAPES.items():
        layout, _ = _generate_counting(width)
        got = re.sub(r"\s+", " ", _shape(layout))
        assert got == expected, f"{width}px:\n  got      {got}\n  expected {expected}"
    print("  ✓  the mosaic at 1280/900/500px is the one chosen before the change")


def test_the_search_builds_nodes_for_what_the_beam_keeps():
    for width, (rows, cols) in _BUILT.items():
        _, built = _generate_counting(width)
        assert built["row"] <= rows, (
            f"{width}px: {built['row']} rows built, pinned {rows}"
        )
        assert built["col"] <= cols, (
            f"{width}px: {built['col']} cols built, pinned {cols}"
        )
    print("  ✓  rows and cols built by the search stay at the beam's scale")


TESTS = [
    test_the_mosaic_is_the_one_the_search_chose_before,
    test_the_search_builds_nodes_for_what_the_beam_keeps,
]

if __name__ == "__main__":
    print("Bento Search Tests")
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
