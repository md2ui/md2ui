"""
Tests that an image's wide/narrow choices follow its SPACE, never the window.

A ``?md2ui.<prop>_wide`` twin applies where the space the image is laid out in is
``WIDE_BREAKPOINT`` or wider. So on a wide page an image in a narrow ``:::`` cell takes its narrow values, while
the same image filling the page takes its wide ones — the rule the ``:::``
divider conditions follow too. There is no window breakpoint.

Through the real pipeline, as the window lays a document out.

Run with: uv run tests/image_space_twins_tests.py
"""

from pathlib import Path

from md2ui import session
from md2ui.pipeline.layout_generator import LayoutGenerator

_THEME = Path("data/markdown/tests/THEME.md")
_KIT: list = []
_MAP = "![Map](https://example.com/map.jpg?md2ui.aspect_ratio=3:4{})"


def _image(text: str, width: float = 1280.0):
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


def _in_a_narrow_cell(twin: str = "") -> str:
    return (
        _MAP.format(twin) + "\n:::1\nText beside the map, three shares of four.\n:::3\n"
    )


def test_a_twin_follows_the_space_not_the_window():
    wide = "&md2ui.aspect_ratio_wide=3:2"
    full = _image("Some text.\n\n" + _MAP.format(wide) + "\n")
    cell = _image(_in_a_narrow_cell(wide))
    assert full.render_properties["aspect_ratio"] == "3:2", full.render_properties
    assert cell.render_properties["aspect_ratio"] == "3:4", cell.render_properties
    print("  ✓  on a 1280px page the map filling it is wide, the one in a cell narrow")


def test_a_ratio_range_follows_the_image_not_the_window():
    ranged = _MAP.replace("3:4", "3:4,16:9@600")
    full = _image("Some text.\n\n" + ranged.format("") + "\n")
    cell = _image(_in_a_narrow_cell().replace(_MAP.format(""), ranged.format("")))
    assert cell.width < 600 <= full.width, (cell.width, full.width)
    assert abs(full.width / full.height - 16 / 9) < 0.01, (full.width, full.height)
    assert abs(cell.height - cell.width * 4 / 3) < 0.5, (cell.width, cell.height)
    print("  ✓  on a 1280px page the map filling it is 16:9, the one in a cell 3:4")


TESTS = [
    test_a_twin_follows_the_space_not_the_window,
    test_a_ratio_range_follows_the_image_not_the_window,
]

if __name__ == "__main__":
    print("Image Space Twins Tests")
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
