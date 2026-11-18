"""
Unit tests for a spring line that wraps (generator_spring_wrap).

While a ``...`` line fits, its pieces sit where they were written: left edge, centre,
right edge (``layout_align_tests``). When it wraps:

  * a right piece that wrapped onto a line of its own starts at the left;
  * a centred piece stays centred;
  * in ``A ... B ... C`` the end wraps first, to the left, and A and B keep one line; B
    takes its own line, centred, only when A and B cannot share one: each piece a
    line of its own in the order written;
  * a run's lines wrap together, so they realign together.

Each assertion reads the placed box: its ``y`` says which line the piece is on, and
its ``content_align`` is what the painter aligns the text by.

Run with: uv run python tests/spring_wrap_tests.py
"""

import sys

sys.path.insert(0, "tests")

from layout_align_tests import _box_for, _boxes

from md2ui.pipeline.generator_spring_wrap import left_when_alone
from md2ui.pipeline.layout_script_parser import LayoutNode

# Too long to share a 320 px line with a price.
LONG = "A charred double smash burger with fries"


def _align(boxes, idx, content: str) -> str | None:
    return (_box_for(boxes, idx, content).render_properties or {}).get("content_align")


def _y(boxes, idx, content: str) -> float:
    return _box_for(boxes, idx, content).y


def test_a_wrapped_right_piece_goes_left():
    boxes, idx, _w, _ = _boxes(f"{LONG} ... $14.50", 320)
    assert _y(boxes, idx, "$14.50") > _y(boxes, idx, LONG), "the price wraps"
    assert _align(boxes, idx, "$14.50") == "left"
    print("  ✓  a right piece that wraps onto its own line starts at the left")


def test_a_line_that_fits_keeps_its_spring():
    boxes, idx, _w, _ = _boxes(f"{LONG} ... $14.50", 900)
    assert _y(boxes, idx, "$14.50") == _y(boxes, idx, LONG)
    assert _align(boxes, idx, "$14.50") == "right"
    print("  ✓  a line that fits keeps every piece where it was written")


def test_a_centred_piece_stays_centred():
    boxes, idx, _w, _ = _boxes(f"{LONG} ... $14.50 ...", 320)
    assert _y(boxes, idx, "$14.50") > _y(boxes, idx, LONG)
    assert _align(boxes, idx, "$14.50") == "center"
    boxes, idx, _w, _ = _boxes(f"... {LONG} ... $14.50", 320)
    assert _align(boxes, idx, LONG) == "center"
    assert _align(boxes, idx, "$14.50") == "left"
    print("  ✓  a centred piece stays centred; the right one after it goes left")


def test_the_end_wraps_first():
    src = "Charred Double Smash ... Lisbon, Portugal ... $14.50"
    boxes, idx, _w, _ = _boxes(src, 320)
    first = _y(boxes, idx, "Charred Double Smash")
    assert _y(boxes, idx, "Lisbon, Portugal") == first, "A and B keep one line"
    assert _y(boxes, idx, "$14.50") > first, "the end wraps"
    assert _align(boxes, idx, "Lisbon, Portugal") == "center"
    assert _align(boxes, idx, "$14.50") == "left"
    print("  ✓  in A ... B ... C the end wraps first, to the left")


def test_edges_apart_take_a_line_each_as_written():
    boxes, idx, _w, _ = _boxes(f"{LONG} ... Lisbon ... $14.50", 320)
    ys = [_y(boxes, idx, c) for c in (LONG, "Lisbon", "$14.50")]
    assert ys == sorted(ys) and len(set(ys)) == 3, ys
    assert _align(boxes, idx, "Lisbon") == "center"
    assert _align(boxes, idx, "$14.50") == "left"
    print("  ✓  when A and C cannot share a line, each piece takes one, in order")


def test_a_run_realigns_together():
    """One wraps, all wrap: the short member wraps with its twin, and both prices
    start at the left."""
    boxes, idx, _w, _ = _boxes(f"- {LONG} ... $14.50\n- Fries ... $3.00", 320)
    assert _y(boxes, idx, "$3.00") > _y(boxes, idx, "Fries"), "the twin wraps too"
    assert _align(boxes, idx, "$14.50") == "left"
    assert _align(boxes, idx, "$3.00") == "left"
    print("  ✓  a run's lines wrap together and realign together")


def test_only_a_right_piece_alone_on_a_later_line_moves():
    """The first line is the spring's own, and a right piece that shares its line
    still has a neighbour to be pushed from: neither moves."""

    def piece(align: str) -> LayoutNode:
        node = LayoutNode(type="-", ratios=[], children=[])
        node.render_properties = {"content_align": align}
        return node

    first, alone, shared = piece("right"), piece("right"), piece("right")
    left_when_alone([first, alone, shared], [["a"], ["b"], ["c", "d"]])
    assert first.render_properties == {"content_align": "right"}
    assert alone.render_properties == {"content_align": "left"}
    assert shared.render_properties == {"content_align": "right"}
    print("  ✓  only a right piece alone on a later line moves left")


TESTS = [
    test_only_a_right_piece_alone_on_a_later_line_moves,
    test_a_wrapped_right_piece_goes_left,
    test_a_line_that_fits_keeps_its_spring,
    test_a_centred_piece_stays_centred,
    test_the_end_wraps_first,
    test_edges_apart_take_a_line_each_as_written,
    test_a_run_realigns_together,
]


if __name__ == "__main__":
    print("Spring Wrap Tests")
    print("=" * 50)
    for t in TESTS:
        t()
    print("=" * 50)
    print(f"All {len(TESTS)} tests passed.")
