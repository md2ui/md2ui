"""
Tests for the per-rebuild ``natural_height`` memo (``render_measure.height_memo``).

``place_boxes`` asks ``natural_height`` for each child on its way down, and each
ask re-walks that child's subtree, so unmemoised one rebuild measures the same
subtree several times. ``session.build_scene`` opens
``height_memo()`` around the top-level measure and the placement, after the bakes,
so the layout cannot change while a height is remembered. Pinned here:

* a memoised height equals the unmemoised one;
* inside the scope a repeated ask is answered without measuring again;
* outside the scope, including after an exception, nothing is remembered, so
  the generator's trial builds, whose nodes the bakes edit later, never hit it.

Byte-identity over the corpus is the render snapshot's job, not this module's.

Run with: uv run tests/resize_height_memo_tests.py
"""

import sys

sys.path.insert(0, "tests")

from layout_align_tests import _themed

from md2ui.pipeline import render_measure
from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.render_measure import height_memo, natural_height


def _col() -> tuple[LayoutNode, dict]:
    leaves = [
        LayoutNode(
            type="-",
            ratios=[],
            children=[],
            content_id=cid,
            render_properties={"aspect_ratio": ratio},
        )
        for cid, ratio in (("a", "1:1"), ("b", "2:1"), ("c", "4:3"))
    ]
    inner = LayoutNode(type="col", ratios=[1.0, 1.0], children=leaves[:2])
    col = LayoutNode(type="col", ratios=[1.0, 1.0], children=[inner, leaves[2]])
    return col, {cid: {"type": "image"} for cid in "abc"}


def _counting():
    calls: list[LayoutNode] = []
    uncached = render_measure._natural_height_uncached

    def counted(node, *args):
        calls.append(node)
        return uncached(node, *args)

    return calls, uncached, counted


def test_a_memoised_height_equals_the_unmemoised_one():
    theme, fonts = _themed()
    col, index = _col()
    plain = natural_height(col, 400.0, index, fonts, theme)
    with height_memo():
        first = natural_height(col, 400.0, index, fonts, theme)
        again = natural_height(col, 400.0, index, fonts, theme)
    assert plain == first == again > 0.0, (plain, first, again)
    print("  ✓  a memoised height equals the unmemoised one")


def test_a_repeated_ask_inside_the_scope_is_not_measured_again():
    theme, fonts = _themed()
    col, index = _col()
    calls, uncached, counted = _counting()
    render_measure._natural_height_uncached = counted
    try:
        with height_memo():
            natural_height(col, 400.0, index, fonts, theme)
            walked = len(calls)
            natural_height(col, 400.0, index, fonts, theme)
            natural_height(col.children[0], 400.0, index, fonts, theme)
            assert len(calls) == walked, (walked, len(calls))
            natural_height(col, 300.0, index, fonts, theme)
            assert len(calls) > walked, "a new width must be measured"
    finally:
        render_measure._natural_height_uncached = uncached
    print("  ✓  inside the scope a repeated ask is answered from the memo")


def test_nothing_is_remembered_outside_the_scope():
    theme, fonts = _themed()
    col, index = _col()
    assert render_measure._HEIGHT_MEMO is None
    try:
        with height_memo():
            natural_height(col, 400.0, index, fonts, theme)
            raise RuntimeError("placement failed")
    except RuntimeError:
        pass
    assert render_measure._HEIGHT_MEMO is None
    calls, uncached, counted = _counting()
    render_measure._natural_height_uncached = counted
    try:
        natural_height(col, 400.0, index, fonts, theme)
        natural_height(col, 400.0, index, fonts, theme)
    finally:
        render_measure._natural_height_uncached = uncached
    assert calls.count(col) == 2, calls
    print("  ✓  outside the scope, even after an exception, every ask measures")


TESTS = [
    test_a_memoised_height_equals_the_unmemoised_one,
    test_a_repeated_ask_inside_the_scope_is_not_measured_again,
    test_nothing_is_remembered_outside_the_scope,
]

if __name__ == "__main__":
    print("Resize Height Memo Tests")
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
