"""Scrolling a clipped code block in the window: sideways past its right edge, and
down past its last shown line (``Max lines``).

The pipeline lists what may scroll (``Scene.scrollables``, ADR-404); the window
holds each block's offset and paints a scrolled block over the recorded document
every frame (``render_scroll_overlay``). The input rules — which one thing a
gesture drives, and how an event's deltas reach it — are pure, tested here
without a window, since they are where the platforms differ.

Run with: uv run python tests/code_block_scroll_tests.py
"""

import numpy as np
import skia

from md2ui.pipeline.render_fills import _paint_layered_fill
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_code_blocks import (
    Scrollable,
    code_block_plan,
    code_block_scrollables,
    draw_code_block,
)
from md2ui.pipeline.render_scroll_overlay import (
    clamp_offsets,
    paint_scrolled,
    scrollable_at,
)
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import Theme
from md2ui.utils.scroll_state import SCROLL_SPEED, ScrollLatch, split_scroll

_FACE = skia.Typeface.MakeDefault()
_FONTS = FontSet(_FACE, _FACE, _FACE, _FACE, _FACE)
# A run of solid glyphs, then enough spaces to run far past the block.
_SOURCE = "█" * 10 + " " * 400


def test_horizontal_input_over_a_block_pans_the_block():
    assert split_scroll(-1.0, 0.0, False, True) == (SCROLL_SPEED, 0.0, 0.0, 0.0)
    assert split_scroll(-1.0, 0.0, False, False) == (0.0, 0.0, SCROLL_SPEED, 0.0)
    print("  ✓  horizontal input pans the block under the pointer, else the page")


def test_an_event_a_block_drives_never_scrolls_the_page():
    """An event drives one thing. A block takes both axes (what its range cannot
    use is clamped away, never passed to the page), and the page ignores a
    gesture that started on a block."""
    assert split_scroll(0.0, -1.0, False, True) == (0.0, SCROLL_SPEED, 0.0, 0.0)
    assert split_scroll(-0.5, -1.0, False, True) == (
        SCROLL_SPEED / 2,
        SCROLL_SPEED,
        0.0,
        0.0,
    )
    assert split_scroll(-0.5, -1.0, False, False) == (
        0.0,
        0.0,
        SCROLL_SPEED / 2,
        SCROLL_SPEED,
    )
    print("  ✓  an event a block drives never scrolls the page, and vice versa")


def test_a_gesture_keeps_the_target_it_started_on():
    """A page scroll that passes over a block keeps scrolling the page; a block's
    gesture keeps the block after the pointer leaves it. A pause ends it."""
    latch = ScrollLatch(timeout=0.3)
    assert latch.target_for(None, 0.0) is None  # starts on the page
    assert latch.target_for("block", 0.1) is None  # passes over a block
    assert latch.target_for("block", 0.35) is None  # still inside the gesture
    assert latch.target_for("block", 1.0) == "block"  # a pause: a new gesture
    assert latch.target_for(None, 1.2) == "block"  # left the block mid-gesture
    assert latch.target_for(None, 2.0) is None
    print("  ✓  a gesture keeps the target it started on until it pauses")


def test_shift_turns_a_wheel_horizontal_only_once():
    """Windows and Linux send shift+wheel as vertical: it becomes horizontal.
    macOS already sends it horizontal: it is not turned a second time."""
    assert split_scroll(0.0, -1.0, True, True) == (SCROLL_SPEED, 0.0, 0.0, 0.0)
    assert split_scroll(-1.0, 0.0, True, True) == (SCROLL_SPEED, 0.0, 0.0, 0.0)
    print("  ✓  shift makes a vertical wheel horizontal, never twice")


def _scrollable(node_id: str = "n", width: float = 300.0) -> Scrollable:
    return Scrollable(node_id, "c", 10.0, 20.0, width, 60.0, 900.0)


def test_offsets_are_kept_within_what_can_still_scroll():
    """After a rebuild an offset is clamped to the block's new range, and a block
    that no longer scrolls forgets its offset."""
    wide = _scrollable(width=800.0)
    kept = clamp_offsets({"n": (500.0, 30.0), "gone": (40.0, 0.0)}, [wide])
    assert kept == {"n": (100.0, 0.0)}, kept  # it has no lines below to show
    assert clamp_offsets({"n": (-5.0, -5.0)}, [wide]) == {"n": (0.0, 0.0)}
    print("  ✓  offsets clamp to the new range; a block that cannot scroll forgets")


def test_the_block_under_the_pointer_is_found():
    s = _scrollable()
    assert scrollable_at([s], 15.0, 25.0) is s
    assert scrollable_at([s], 5.0, 25.0) is None
    print("  ✓  the scrollable under a content point is found")


def _theme() -> Theme:
    theme = Theme()
    block = theme.code_blocks
    block.background_color = 0xFFFFFFFF
    block.text_style.color = 0xFF000000
    block.copy_icon = None
    return theme


def _canvas(width: int, height: int) -> tuple[skia.Surface, skia.Canvas]:
    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    canvas.clear(0xFFEEEEEE)
    return surface, canvas


def _recorded(theme: Theme, box: LayoutBox, offset: float = 0.0):
    surface, canvas = _canvas(340, 90)
    draw_code_block(
        canvas,
        box,
        _SOURCE,
        None,
        _FACE,
        theme,
        paint_fill=_paint_layered_fill,
        offset=offset,
    )
    return surface, canvas


def _scrolled_at(theme: Theme, box: LayoutBox) -> Scrollable:
    plan = code_block_plan(_SOURCE, None, _FACE, theme.code_blocks)
    return Scrollable("n", "c", box.x, box.y, box.width, box.height, plan.width)


def test_nothing_scrolled_draws_nothing():
    """A frame with no offset and no pointer over a block is the recording alone."""
    theme = _theme()
    box = LayoutBox(x=10.0, y=10.0, width=300.0, height=60.0)
    surface, canvas = _recorded(theme, box)
    before = (
        surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType).copy()
    )
    index = {"c": {"content": _SOURCE}}
    paint_scrolled(canvas, [_scrolled_at(theme, box)], {}, None, index, _FONTS, theme)
    assert np.array_equal(
        before, surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    )
    print("  ✓  with nothing scrolled the frame is the recording, pixel for pixel")


def test_a_scrolled_block_moves_its_lines_left():
    """At an offset past the solid run, the run has left the block."""
    theme = _theme()
    block = theme.code_blocks
    box = LayoutBox(x=10.0, y=10.0, width=300.0, height=60.0)
    x = int(box.x + block.padding.left + 4)
    y = int(box.y + block.padding.top + block.text_style.font_size / 2)
    still, _c = _recorded(theme, box)
    moved, _c = _recorded(theme, box, offset=200.0)
    assert (
        still.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[y, x][0]
        < 60
    )
    assert (
        moved.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[y, x][0]
        > 200
    )
    print("  ✓  a scrolled block's lines move left by its offset")


def test_the_repaint_hides_the_recorded_copy():
    """Over the recorded block, the frame's repaint at an offset shows what a
    direct paint at that offset shows, inside the block."""
    theme = _theme()
    box = LayoutBox(x=10.0, y=10.0, width=300.0, height=60.0)
    direct, _c = _recorded(theme, box, offset=120.0)
    framed, canvas = _recorded(theme, box)
    index = {"c": {"content": _SOURCE}}
    s = _scrolled_at(theme, box)
    paint_scrolled(canvas, [s], {"n": (120.0, 0.0)}, None, index, _FONTS, theme)
    inside = np.s_[int(box.y) + 2 : int(box.y + box.height) - 10, 12:308]
    a = direct.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[inside]
    b = framed.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[inside]
    assert np.abs(a.astype(int) - b.astype(int)).max() <= 1
    print("  ✓  the repaint at an offset hides the recorded copy")


# A solid first line over twenty-nine blank ones: taller than ``Max lines`` (20).
_TALL = "█" * 10 + "\n" + "\n".join(" " for _ in range(29)) + "\n"


def _tall_box(theme: Theme) -> LayoutBox:
    plan = code_block_plan(_TALL, None, _FACE, theme.code_blocks)
    return LayoutBox(x=10.0, y=10.0, width=300.0, height=plan.height, content_id="c")


def _tall(theme: Theme, box: LayoutBox, offset_y: float = 0.0):
    surface, canvas = _canvas(340, int(box.y + box.height) + 10)
    draw_code_block(
        canvas,
        box,
        _TALL,
        None,
        _FACE,
        theme,
        paint_fill=_paint_layered_fill,
        offset_y=offset_y,
    )
    return surface, canvas


def test_a_block_cut_at_max_lines_scrolls_down():
    """A block taller than ``Max lines`` is listed as scrollable down, by exactly
    the lines it hides, and not across: its lines are short."""
    theme = _theme()
    box = _tall_box(theme)
    plan = code_block_plan(_TALL, None, _FACE, theme.code_blocks)
    index = {"c": {"type": "code_block", "content": _TALL, "node_id": "n"}}
    (s,) = code_block_scrollables([box], index, _FACE, theme.code_blocks)
    assert s.max_offset == 0.0, s.max_offset
    cap = theme.code_blocks.max_lines
    assert cap is not None, "the default theme cuts long blocks"
    hidden = len(plan.lines) - cap
    assert abs(s.max_offset_y - hidden * plan.line_height) < 0.5, s.max_offset_y
    print("  ✓  a block cut at Max lines scrolls down by the lines it hides")


def test_a_block_scrolled_down_moves_its_lines_up():
    """Scrolled past its first line, the solid line has left the block."""
    theme = _theme()
    block = theme.code_blocks
    box = _tall_box(theme)
    plan = code_block_plan(_TALL, None, _FACE, block)
    x = int(box.x + block.padding.left + 4)
    y = int(box.y + plan.baseline - block.text_style.font_size / 3)
    still, _c = _tall(theme, box)
    moved, _c = _tall(theme, box, offset_y=3 * plan.line_height)
    assert (
        still.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[y, x][0]
        < 60
    )
    assert (
        moved.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[y, x][0]
        > 200
    )
    print("  ✓  a block scrolled down moves its lines up")


def test_the_repaint_down_hides_the_recorded_copy():
    """Over the recorded block, the frame's repaint scrolled down shows what a
    direct paint at that offset shows, inside the block."""
    theme = _theme()
    box = _tall_box(theme)
    plan = code_block_plan(_TALL, None, _FACE, theme.code_blocks)
    down = 2 * plan.line_height
    direct, _c = _tall(theme, box, offset_y=down)
    framed, canvas = _tall(theme, box)
    index = {"c": {"type": "code_block", "content": _TALL, "node_id": "n"}}
    (s,) = code_block_scrollables([box], index, _FACE, theme.code_blocks)
    paint_scrolled(canvas, [s], {"n": (0.0, down)}, None, index, _FONTS, theme)
    inside = np.s_[int(box.y) + 2 : int(box.y + box.height) - 2, 12:290]
    a = direct.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[inside]
    b = framed.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[inside]
    assert np.abs(a.astype(int) - b.astype(int)).max() <= 1
    print("  ✓  the repaint scrolled down hides the recorded copy")


def test_offsets_down_are_kept_within_the_hidden_lines():
    theme = _theme()
    box = _tall_box(theme)
    index = {"c": {"type": "code_block", "content": _TALL, "node_id": "n"}}
    (s,) = code_block_scrollables([box], index, _FACE, theme.code_blocks)
    assert clamp_offsets({"n": (0.0, 1e6)}, [s]) == {"n": (0.0, s.max_offset_y)}
    print("  ✓  an offset down clamps to the hidden lines")


TESTS = [
    test_horizontal_input_over_a_block_pans_the_block,
    test_an_event_a_block_drives_never_scrolls_the_page,
    test_a_gesture_keeps_the_target_it_started_on,
    test_shift_turns_a_wheel_horizontal_only_once,
    test_offsets_are_kept_within_what_can_still_scroll,
    test_the_block_under_the_pointer_is_found,
    test_nothing_scrolled_draws_nothing,
    test_a_scrolled_block_moves_its_lines_left,
    test_the_repaint_hides_the_recorded_copy,
    test_a_block_cut_at_max_lines_scrolls_down,
    test_a_block_scrolled_down_moves_its_lines_up,
    test_the_repaint_down_hides_the_recorded_copy,
    test_offsets_down_are_kept_within_the_hidden_lines,
]


if __name__ == "__main__":
    print("Code Block Scroll Tests")
    print("=" * 50)
    for test in TESTS:
        test()
    print("=" * 50)
    print(f"All {len(TESTS)} tests passed.")
