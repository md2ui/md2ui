"""Tests for ``md2ui.max_width`` constraining image boxes.

The cap belongs to the leaf box itself, so a small capped bitmap is not left in
a wide, tall row/grid allocation that separates it from adjacent content.
"""

import sys

sys.path.insert(0, "tests")

from layout_align_tests import _themed

from md2ui.pipeline.layout_script_parser import LayoutNode
from md2ui.pipeline.render_measure import _layout_bento_row
from md2ui.pipeline.render_place import place_boxes


def _leaf(cid: str, **render_properties) -> LayoutNode:
    return LayoutNode(
        type="-",
        ratios=[],
        children=[],
        content_id=cid,
        render_properties=render_properties or None,
    )


def _row() -> tuple[LayoutNode, dict]:
    capped = _leaf("capped", max_width=56, aspect_ratio="1:1", shape="circle")
    fill = _leaf("fill", aspect_ratio="1:1")
    row = LayoutNode(type="row", ratios=[1.0, 1.0], children=[capped, fill])
    row.bento = True
    return row, {"capped": {"type": "image"}, "fill": {"type": "image"}}


def test_capped_bento_image_releases_its_unused_width():
    theme, fonts = _themed()
    row, index = _row()
    placements, _height, _gaps = _layout_bento_row(row, 400.0, index, fonts, theme)
    capped, following = placements
    assert capped[2] == 56.0, capped
    assert following[1] < 100.0, following
    print("  ✓  a capped image box releases its unused bento span")


def test_capped_image_box_hugs_height_and_stays_at_top():
    theme, fonts = _themed()
    row, index = _row()
    boxes = place_boxes(
        row, 0.0, 20.0, 400.0, 400.0, index, fonts, theme, section_boxes=[]
    )
    capped = next(box for box in boxes if box.content_id == "capped")
    assert (capped.y, capped.width, capped.height) == (20.0, 56.0, 56.0), capped
    print("  ✓  a capped image box hugs its image and remains top-aligned")


TESTS = [
    test_capped_bento_image_releases_its_unused_width,
    test_capped_image_box_hugs_height_and_stays_at_top,
]
