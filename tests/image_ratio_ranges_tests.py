"""
Tests for authored aspect-ratio ranges (``render_metrics.ratio_ranges``).

An image's ratio is authored, never inferred: ``md2ui.aspect_ratio=3:4`` draws
3:4 at every width, and ``3:4,1:1@600,16:9@960`` changes it as the image
widens — 3:4, then 1:1 from 600px, then 16:9 from 960px. The width is the
image's own drawn width. An image always fills that width: there is no height
limit and no automatic step, so a picture never leaves a gap beside it. An image
with no ratio uses the default, written in the same syntax
(``DEFAULT_IMAGE_RATIOS``). ``max_width`` is the author's way to keep a picture
smaller; a circle stays 1:1.

Through the real pipeline where it matters, because measuring, placing and
drawing all read the ratio through ``_image_aspect_ratio``.

Run with: uv run tests/image_ratio_ranges_tests.py
"""

from pathlib import Path

from md2ui import session
from md2ui.pipeline.render_hints import sanitize_url_props
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.render_metrics import default_image_ratio, ratio_at

_THEME = Path("data/markdown/tests/THEME.md")
_KIT: list = []
_URL = "https://example.com/map.jpg"


def _image(text: str, width: float = 1280.0):
    """The one image box of *text* laid out at *width*."""
    if not _KIT:
        theme = session.load_theme(_THEME)
        _KIT.extend([session.load_grouping_kit(), theme, session.load_fonts(theme)])
    kit, theme, fonts = _KIT
    grouped = session.group_markdown(text, kit)
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, width)
    boxes = [
        b for b in scene.boxes if index.get(b.content_id, {}).get("type") == "image"
    ]
    assert len(boxes) == 1, boxes
    return boxes[0]


def _alone(params: str, width: float = 1280.0):
    return _image(f"Some text.\n\n![Map]({_URL}?{params})\n", width)


def test_a_range_applies_from_its_width_up():
    spec = "3:4,1:1@600,16:9@960"
    want = {0: 3 / 4, 599: 3 / 4, 600: 1.0, 959: 1.0, 960: 16 / 9, 2000: 16 / 9}
    for width, ratio in want.items():
        assert ratio_at(spec, width) == ratio, (width, ratio_at(spec, width))
    assert ratio_at("1:1@600,3:4", 700) is None
    print("  ✓  each ratio holds from its width up; the first has no width")


def test_the_default_is_written_the_same_way():
    want = {767: 3 / 2, 768: 16 / 9, 1023: 16 / 9, 1024: 2.35}
    for width, ratio in want.items():
        assert default_image_ratio(width) == ratio, (width, default_image_ratio(width))
    print("  ✓  no ratio: 3:2, 16:9 from 768px, 2.35:1 from 1024px")


def test_the_url_accepts_ranges_and_reports_typos():
    props, warnings = sanitize_url_props({"aspect_ratio": "3:4,1:1@600"})
    assert props == {"aspect_ratio": "3:4,1:1@600"} and not warnings, props
    for typo in ("3:4,1:1", "3:4,1:0@600", "1:1@600"):
        props, warnings = sanitize_url_props({"aspect_ratio": typo})
        assert not props and warnings, (typo, props)
    print("  ✓  a range list passes the URL check; a malformed one is dropped")


def test_an_authored_ratio_is_drawn_as_written():
    box = _alone("md2ui.aspect_ratio=3:4")
    assert abs(box.height - box.width * 4 / 3) < 0.5, (box.width, box.height)
    print("  ✓  a 3:4 filling a wide page stays 3:4: the author chose it")


def test_the_image_width_picks_the_range():
    params = "md2ui.aspect_ratio=3:4,16:9@960"
    wide = _alone(params)
    assert abs(wide.width / wide.height - 16 / 9) < 0.01, (wide.width, wide.height)
    narrow = _alone(params, 700.0)
    assert abs(narrow.height - narrow.width * 4 / 3) < 0.5, narrow
    capped = _alone(params + "&md2ui.max_width=900")
    assert abs(capped.height - 900 * 4 / 3) < 0.5, (capped.width, capped.height)
    print("  ✓  the drawn width picks the ratio, max_width included")


def test_a_picture_in_a_weighted_row_fills_its_cell():
    # A height limit would narrow the photo and leave the rest of its cell empty.
    text = (
        f"![Plate]({_URL}?md2ui.aspect_ratio=4:3)\n::: 2 >\n"
        "**The tasting menu**\nBegin at any neighborhood taquería.\n"
    )
    box = _image(text)
    assert box.width > 700, box.width
    assert abs(box.width / box.height - 4 / 3) < 0.01, (box.width, box.height)
    print("  ✓  a 4:3 photo in a `::: 2 >` cell fills it at 4:3")


def test_a_circle_stays_square():
    box = _alone("md2ui.shape=circle&md2ui.aspect_ratio=3:4,16:9@960")
    assert abs(box.width - box.height) < 0.5, (box.width, box.height)
    print("  ✓  a circle is 1:1 whatever ratio is written")


TESTS = [
    test_a_range_applies_from_its_width_up,
    test_the_default_is_written_the_same_way,
    test_the_url_accepts_ranges_and_reports_typos,
    test_an_authored_ratio_is_drawn_as_written,
    test_the_image_width_picks_the_range,
    test_a_picture_in_a_weighted_row_fills_its_cell,
    test_a_circle_stays_square,
]

if __name__ == "__main__":
    print("Image Ratio Ranges Tests")
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
