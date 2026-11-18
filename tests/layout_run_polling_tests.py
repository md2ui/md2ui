"""
Unit tests for repeated-run consistency: _unify_run pins one icon-aside answer
on every member of a contiguous repeated run, and the grid's column count is
measured under it (an aside unit is wider than its stacked self — poll →
measure → grid). Render hints spread across a run through URL params; that half
is covered in image_url_params_tests.
Run with: uv run layout_run_polling_tests.py
"""

from layout_bento_tests import _ast, _group, _leaf
from layout_decision_scope_tests import aside_theme
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.theme import Theme

_ids = iter(range(70_000, 80_000))


def _emoji() -> dict:
    return {
        "node_id": f"e{next(_ids)}",
        "type": "emoji",
        "content": "⭐",
        "emoji_kind": "alone",
    }


def _card() -> dict:
    # 5-9 words → "short" (LEAF_WIDTH 200); the analyzer recomputes length
    # categories from content, so the words themselves carry the category.
    return _group(
        _emoji(),
        _leaf("Product title of several words here"),
        _leaf("Another supporting line of body text"),
        glued_content_group=True,
    )


def _run_doc(n: int):
    return _ast(_group(_group(*[_card() for _ in range(n)])))


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def _aside_rows(layout):
    """Rows whose fixed cell is an icon gutter (built icon asides)."""
    return [
        n
        for n in _walk(layout)
        if n.type == "row"
        and len(n.children) == 2
        and any((c.render_properties or {}).get("aside_fixed") for c in n.children)
    ]


def test_every_member_of_a_run_takes_the_aside():
    ast = _run_doc(3)
    layout = LayoutGenerator().generate(ast, 1280.0, theme=aside_theme())
    assert len(_aside_rows(layout)) == 3, layout.to_dict()
    print("  ✓  a themed run lays every member out with its icon aside")


def test_aside_units_shrink_column_count():
    width = 440.0
    stack_layout = LayoutGenerator().generate(_run_doc(2), width, theme=Theme())
    assert any(getattr(n, "grid", False) for n in _walk(stack_layout)), (
        "stacked units should still grid 2-up at this width"
    )
    aside_layout = LayoutGenerator().generate(_run_doc(2), width, theme=aside_theme())
    assert not any(getattr(n, "grid", False) for n in _walk(aside_layout)), (
        "aside units must be measured aside-wide → no 2-up grid at this width"
    )
    assert len(_aside_rows(aside_layout)) == 2, (
        "both members should still build their aside full-width"
    )
    print("  ✓  poll → measure → grid: aside units yield fewer columns")


TESTS = [
    test_every_member_of_a_run_takes_the_aside,
    test_aside_units_shrink_column_count,
]

if __name__ == "__main__":
    print("Layout Run Polling Tests")
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
