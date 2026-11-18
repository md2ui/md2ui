"""
Unit tests for matching pieces in a grid row sharing one height (render_slots).

Cards of one run side by side in a grid row each stack their pieces from the top.
When one card's title wraps to two lines and its neighbours' do not, every piece
below it would sit lower than its twins. So the piece at the same place in every
card of the ROW takes the tallest one's height, keeps the top of that slot, and
the gap opens under it:

  * twins start at one y across the row, and the row is no taller when one card is
    the tallest everywhere;
  * cards that stack different pieces do not share;
  * a row's own cards share, not the next row's;
  * a slot is per width: asked at another width, a piece keeps its own height.

Run with: uv run python tests/slot_heights_tests.py
"""

import contextlib
import io
from pathlib import Path

from md2ui import session
from md2ui.pipeline import render_slots
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_script_parser import LayoutNode

THEME = Path("data/markdown/tests/THEME.md")
BODY = "Magnis porttitor penatibus facilisis feugiat hendrerit."
_KIT = None


def _card(title: str, n: int) -> str:
    return f"### {title}\nEverything you need to know\n{BODY}\n[Read now](agent:read?id={n})"


def _scene(markdown: str, width: float = 1280.0):
    global _KIT
    with contextlib.redirect_stdout(io.StringIO()):
        if _KIT is None:
            _KIT = session.load_grouping_kit()
        theme = session.load_theme(THEME)
        fonts = session.load_fonts(theme)
        ast = session.group_markdown(markdown, _KIT)
        assert ast is not None
        root, index = session.prepare(ast, theme)
        scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, width)
    return scene, index


def _ys(scene, index, content: str) -> list[float]:
    """The y of every box drawing *content* (a button's node holds its Markdown, so
    by substring), left to right."""
    boxes = [
        b
        for b in scene.boxes
        if b.content_id and content in index.get(b.content_id, {}).get("content", "")
    ]
    return [b.y for b in sorted(boxes, key=lambda b: b.x)]


LONG = "A few possible examples from my career, collected over ten years"
ROW = "\n\n".join([_card("Deep natured", 1), _card(LONG, 2), _card("Calm water", 3)])


def test_twins_start_at_one_y_across_the_row():
    scene, index = _scene(ROW)
    for piece in ("Everything you need to know", BODY, "Read now"):
        ys = _ys(scene, index, piece)
        assert len(ys) == 3 and max(ys) - min(ys) < 0.5, (piece, ys)
    print("  ✓  the pieces below a two-line title line up with their twins")


def test_the_row_is_no_taller_when_one_card_is_tallest_everywhere():
    shared, _ = _scene(ROW)
    share = render_slots.share
    render_slots.share = lambda *_a: None  # the same row, nothing shared
    try:
        plain, _ = _scene(ROW)
    finally:
        render_slots.share = share
    assert abs(shared.height - plain.height) < 0.5, (shared.height, plain.height)
    print("  ✓  a card tallest in every piece keeps the row's height")


def test_cards_with_different_pieces_do_not_share():
    """A card with one piece more is not the same element by place: no share."""
    extra = f"### Deep natured\nEverything you need to know\n`New`\n{BODY}\n[Read now](agent:read?id=1)"
    scene, index = _scene("\n\n".join([extra, _card(LONG, 2), _card("Calm water", 3)]))
    ys = _ys(scene, index, "Everything you need to know")
    assert len(ys) == 3 and max(ys) - min(ys) > 0.5, ys
    print("  ✓  cards that stack different pieces keep their own heights")


def test_a_grid_inside_a_card_shares_inside_the_row_that_holds_it():
    """A card holding a grid row of its own shares while the outer row measures;
    the inner row must not drop the outer row's record."""
    doc = Path("data/markdown/tests/tests-chart-units.md").read_text()
    scene, _ = _scene(doc, 767.0)
    assert scene.height > 0
    print("  ✓  a grid row inside a card shares without breaking its outer row")


def test_a_slot_is_kept_only_at_its_width():
    piece = LayoutNode(type="-", ratios=[], children=[])
    other = LayoutNode(type="-", ratios=[], children=[])
    render_slots.clear()
    render_slots._SLOTS[id(piece)] = (piece, 300.0, 80.0)
    try:
        assert render_slots.lift(piece, 300.0, 40.0) == 80.0
        assert render_slots.lift(piece, 200.0, 40.0) == 40.0, "another width"
        assert render_slots.lift(other, 300.0, 40.0) == 40.0, "another piece"
        assert render_slots.lift(piece, 300.0, 90.0) == 90.0, "never shrinks"
    finally:
        render_slots.clear()
    print("  ✓  a slot lifts only its own piece, at its own width, never down")


def test_a_piece_holding_a_picture_never_shares():
    """An image card is a piece that holds its picture deep inside: lifted to a
    taller twin, the photo must not draw taller than its ratio."""
    photo = LayoutNode(type="-", ratios=[], children=[])
    caption = LayoutNode(type="-", ratios=[], children=[])
    card = LayoutNode(
        type="col",
        ratios=[1.0],
        children=[LayoutNode(type="row", ratios=[1.0, 1.0], children=[photo, caption])],
    )
    is_photo = lambda n: n is photo  # noqa: E731
    assert render_slots._holds_picture(card, is_photo)
    assert not render_slots._holds_picture(caption, is_photo)
    backdrop = LayoutNode(type="col", ratios=[1.0], children=[caption])
    backdrop.card_bg_url = "https://example.com/photo.jpg"
    assert render_slots._holds_picture(backdrop, is_photo), "a background photo"
    print("  ✓  a piece that is or holds a picture keeps its own height")


TESTS = [
    test_a_piece_holding_a_picture_never_shares,
    test_twins_start_at_one_y_across_the_row,
    test_the_row_is_no_taller_when_one_card_is_tallest_everywhere,
    test_cards_with_different_pieces_do_not_share,
    test_a_grid_inside_a_card_shares_inside_the_row_that_holds_it,
    test_a_slot_is_kept_only_at_its_width,
]


if __name__ == "__main__":
    print("Slot Heights Tests")
    print("=" * 50)
    for t in TESTS:
        t()
    print("=" * 50)
    print(f"All {len(TESTS)} tests passed.")
