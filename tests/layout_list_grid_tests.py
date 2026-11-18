"""
Unit tests for list items in a grid: a list is a run like any other.

A list item of two or more leaves is a group, and a run of same-shaped groups
grids whether or not each carries a list marker. That holds when the leaves
were split from ONE source line (``- img - **name**``), and when the item holds
an indented ``:::`` row. A one-leaf item is no group and still stacks; a task's
box is its marker, not a piece, so ``- [ ] text`` stacks too. A ``___`` between
items ends the run, as it does anywhere else. A run of spring
items (``- A ... B``) stacks like spring lines: a spring asks for the full width.
A spring that only centres one text (``- ... X ...``) is arrangement, so the item
is the one-piece item ``- X`` and its run stacks as that one does.
A run that stacks is no grid, so it never narrows a gridded run of its kind: four
ring items keep their own column count beside a list of one-leaf bullets.

Run with: uv run python tests/layout_list_grid_tests.py
"""

from pathlib import Path

from layout_column_row_tests import layout_processed, walk

from md2ui import session
from md2ui.pipeline.layout_generator import LayoutGenerator


def grids(doc: str) -> bool:
    return any(getattr(n, "grid", False) for n in walk(layout_processed(doc)))


def test_one_line_items_of_two_leaves_grid():
    assert grids("- ![a](x.png) - **One**\n- ![b](x.png) - **Two**\n")


def test_one_line_items_grid_without_a_separator():
    assert grids("- ![a](x.png) **One**\n- ![b](x.png) **Two**\n")


def test_ordered_items_grid_too():
    assert grids("1. **One** - first\n2. **Two** - second\n")


def test_row_items_grid():
    assert grids("- A\n  :::0\n  **One**\n- B\n  :::0\n  **Two**\n")


def test_one_leaf_items_still_stack():
    assert not grids("- Alpha\n- Beta\n- Gamma\n")


def test_one_piece_task_items_stack():
    # A task's box is its marker, as a bullet is: `- [ ] text` is a one-piece
    # item, and open and done items stay one run.
    assert not grids("- [ ] Buy milk\n- [ ] Call the bank\n- [x] Send it\n")
    assert not grids("- [[ ]](/a) Buy milk\n- [[x]](/b) Call the bank\n")


def test_task_items_of_two_pieces_still_grid():
    for doc in (
        "- [ ] Pay rent - $1,200\n- [ ] Pay power - $80\n- [x] Pay water - $40\n",
        "- [ ] Mute [40%] now\n- [ ] Dim [60%] now\n- [x] Hush [10%] now\n",
        "- [ ] [[x]](/u) b\n- [ ] [[ ]](/v) c\n- [x] [[x]](/w) d\n",
    ):
        assert grids(doc), doc


def test_a_content_break_between_items_stops_the_grid():
    assert not grids("- ![a](x.png) - **One**\n___\n- ![b](x.png) - **Two**\n")


def test_one_line_pieces_still_flow_on_their_line():
    # The exception is for items on DIFFERENT lines; a single item's own pieces
    # still flow beside each other rather than becoming a grid of one line.
    assert not grids("- ![a](x.png) - **One** - more\n")


def test_spring_items_stack():
    assert not grids("- Alpha ... Beta\n- Gamma ... Delta\n- Eta ... Theta\n")


def test_items_without_a_spring_still_grid():
    assert grids("- Alpha - Beta\n- Gamma - Delta\n- Eta - Theta\n")


def test_spring_lines_still_stack():
    assert not grids("Alpha ... Beta\nGamma ... Delta\nEta ... Theta\n")


def test_a_mixed_run_follows_its_majority():
    assert not grids("- Alpha ... Beta\n- Gamma - Delta\n- Eta ... Theta\n")
    assert grids("- Alpha - Beta\n- Gamma ... Delta\n- Eta - Theta\n")


def _arrangement(doc: str) -> list:
    return [
        (n.type, list(n.ratios or []), n.background_kind)
        for n in walk(layout_processed(doc))
        if n.type != "-"
    ]


def test_centred_items_arrange_like_plain_items():
    centred = "- ... Alpha ...\n- ... Gamma ...\n- ... Eta ...\n"
    assert not grids(centred)
    outer = _arrangement(centred)[:2]
    assert outer == _arrangement("- Alpha\n- Gamma\n- Eta\n")[:2]


def _item_tops(doc: str) -> list[float]:
    theme = session.load_theme(Path("data/markdown/tests/THEME.md"))
    ast = session.group_markdown(doc, session.load_grouping_kit())
    assert ast is not None
    root, index = session.prepare(ast, theme)
    scene = session.build_scene(
        LayoutGenerator(), root, index, theme, session.load_fonts(theme), 600
    )
    return [b.y for b in scene.boxes if b.content_id]


def test_centred_items_space_like_plain_items():
    centred = _item_tops("- ... Alpha ...\n- ... Gamma ...\n- ... Eta ...\n")
    assert centred == _item_tops("- Alpha\n- Gamma\n- Eta\n"), centred


def test_a_lone_centred_item_is_unchanged():
    assert not grids("- ... Alpha ...\n")


_RINGS = (
    "- Basic text answer: 2/10 difficulty\n- Structured cards and actions: 4/10\n"
    "- A polished interactive session: 7/10\n- Live data with reliable images: 8/10\n"
)
_NOTES = (
    "Clicks return as clear sentences, so actions are easy to interpret.\n\n"
    "Updating one control without rebuilding the page is a strong feature.\n"
)


def _grid_cols(doc: str) -> int:
    theme = session.load_theme(Path("data/markdown/tests/THEME.md"))
    ast = session.group_markdown(doc, session.load_grouping_kit())
    assert ast is not None
    root, index = session.prepare(ast, theme)
    scene = session.build_scene(
        LayoutGenerator(), root, index, theme, session.load_fonts(theme), 1280
    )
    return max(getattr(n, "grid_cols", 0) or 0 for n in walk(scene.layout))


def test_a_stacked_list_does_not_narrow_a_grid_of_its_kind():
    # The bullets share the rings' kind (every list item is one) but stack, so
    # the rings keep the count they have beside paragraphs.
    alone = _grid_cols(f"{_RINGS}\n\n## Notes\n\n{_NOTES}")
    bullets = "".join(f"- {line}\n" for line in _NOTES.split("\n\n"))
    assert alone == 4, alone
    assert _grid_cols(f"{_RINGS}\n\n## Notes\n\n{bullets}") == alone


TESTS = [
    test_one_line_items_of_two_leaves_grid,
    test_one_line_items_grid_without_a_separator,
    test_ordered_items_grid_too,
    test_row_items_grid,
    test_one_leaf_items_still_stack,
    test_one_piece_task_items_stack,
    test_task_items_of_two_pieces_still_grid,
    test_a_content_break_between_items_stops_the_grid,
    test_one_line_pieces_still_flow_on_their_line,
    test_spring_items_stack,
    test_items_without_a_spring_still_grid,
    test_spring_lines_still_stack,
    test_a_mixed_run_follows_its_majority,
    test_centred_items_arrange_like_plain_items,
    test_centred_items_space_like_plain_items,
    test_a_lone_centred_item_is_unchanged,
    test_a_stacked_list_does_not_narrow_a_grid_of_its_kind,
]


if __name__ == "__main__":
    print("List Grid Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓  {test.__name__}")
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
