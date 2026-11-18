"""
Tests for the line-width measurer's memo (``layout_render.make_line_width_measurer``).

One generate asks the line width of the same leaves at every trial build that
flows them, several times per leaf on line-split pages. The measurer remembers each answer for its own lifetime, keyed on every field it
measures from. Pinned here:

* a remembered answer equals a fresh measurer's;
* a repeated ask, about the same leaf or an equal one, is not measured again;
* a leaf edited between two asks, or asked under another K-V role, is measured
  afresh, so a caller that keeps one measurer across an edit stays correct.

Byte-identity over the corpus is the render snapshot's job, not this module's.

Run with: uv run tests/line_width_memo_tests.py
"""

import copy
import sys

sys.path.insert(0, "tests")

from layout_align_tests import _themed

from md2ui.pipeline import layout_render
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType


def _leaf(text: str = "Tuesday afternoon") -> MarkdownGroupNode:
    return MarkdownGroupNode(type=NodeType.TEXT, content=text)


def _counting():
    calls: list[dict] = []
    measure = layout_render._leaf_natural_width

    def counted(nd, *args):
        calls.append(nd)
        return measure(nd, *args)

    return calls, measure, counted


def test_a_remembered_answer_equals_a_fresh_one():
    theme, fonts = _themed()
    leaf = _leaf()
    kept = layout_render.make_line_width_measurer(fonts, theme)
    first, again = kept(leaf), kept(leaf)
    fresh = layout_render.make_line_width_measurer(fonts, theme)(leaf)
    assert fresh is not None and first == again == fresh > 0.0, (first, again, fresh)
    print("  ✓  a remembered answer equals a fresh measurer's")


def test_a_repeated_ask_is_not_measured_again():
    theme, fonts = _themed()
    leaf = _leaf()
    calls, measure, counted = _counting()
    layout_render._leaf_natural_width = counted
    try:
        measure_line = layout_render.make_line_width_measurer(fonts, theme)
        measure_line(leaf)
        measure_line(leaf)
        measure_line(copy.copy(leaf))
    finally:
        layout_render._leaf_natural_width = measure
    assert len(calls) == 1, len(calls)
    print("  ✓  a repeated ask, same leaf or an equal one, is answered from the memo")


def test_an_edited_leaf_or_another_role_is_measured_afresh():
    theme, fonts = _themed()
    leaf = _leaf()
    calls, measure, counted = _counting()
    layout_render._leaf_natural_width = counted
    try:
        measure_line = layout_render.make_line_width_measurer(fonts, theme)
        before = measure_line(leaf)
        leaf.content = "Tuesday afternoon, late"
        after = measure_line(leaf)
        measure_line(leaf, "key")
    finally:
        layout_render._leaf_natural_width = measure
    assert len(calls) == 3, len(calls)
    assert after is not None and before is not None and after > before
    print("  ✓  an edited leaf, or another K-V role, is measured afresh")


TESTS = [
    test_a_remembered_answer_equals_a_fresh_one,
    test_a_repeated_ask_is_not_measured_again,
    test_an_edited_leaf_or_another_role_is_measured_afresh,
]

if __name__ == "__main__":
    print("Line Width Memo Tests")
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
