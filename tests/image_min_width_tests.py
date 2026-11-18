"""
Tests for an image's ``?md2ui.min_width`` — the floor twin of ``max_width``.

A ``:::`` weight proposes a width; an image's own limits decide it. Below its
``min_width`` an image is not given less: in a weighted row its cell is raised to
the floor and the other cells give up the difference, and when the floor and its
neighbours cannot fit the width at all, the row wraps — the natural flow still
wins. ``max_width`` is the ceiling and wins over the floor, so ``min == max`` is a
fixed size.

Through the real pipeline (grouping, measurement, placement), because the floor
lives in two stages: the generator's fit test counts it, and the renderer honours
it when it splits a row by weight.

Run with: uv run tests/image_min_width_tests.py
"""

from pathlib import Path

from md2ui import session
from md2ui.pipeline.render_hints import sanitize_url_props
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.render_metrics import image_floor

_THEME = Path("data/markdown/tests/THEME.md")
_KIT: list = []
_PHOTO = "https://example.com/photo.jpg"


def _scene(text: str, width: float):
    if not _KIT:
        theme = session.load_theme(_THEME)
        _KIT.extend([session.load_grouping_kit(), theme, session.load_fonts(theme)])
    kit, theme, fonts = _KIT
    grouped = session.group_markdown(text, kit)
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    return session.build_scene(LayoutGenerator(), root, index, theme, fonts, width)


def _doc(params: str, text_weight: int = 5) -> str:
    return (
        f"![Photo]({_PHOTO}?{params}&md2ui.aspect_ratio=1:1)\n"
        "::: 1\n"
        "Text beside a picture.\n"
        f":::{text_weight}\n"
    )


def _image_box(scene):
    boxes = [b for b in scene.boxes if (b.render_properties or {}).get("aspect_ratio")]
    assert len(boxes) == 1, boxes
    return boxes[0]


def test_min_width_is_an_authorable_param():
    props, warnings = sanitize_url_props({"min_width": "240"})
    assert props == {"min_width": 240} and not warnings, (props, warnings)
    _, warnings = sanitize_url_props({"min_width": "0"})
    assert warnings, "a floor of 0 says nothing"
    print("  ✓  min_width is an authorable param")


def test_the_ceiling_wins_over_the_floor():
    assert image_floor({"min_width": 240}) == 240
    assert image_floor({"min_width": 240, "max_width": 140}) == 140
    assert image_floor({"max_width": 140}) is None
    print("  ✓  the ceiling wins over the floor")


def test_a_weighted_share_below_the_floor_is_raised():
    # One share of six at 1024px is about 160px; the floor is 240.
    free = _image_box(_scene(_doc("md2ui.fit=cover"), 1024.0))
    floored = _image_box(_scene(_doc("md2ui.min_width=240"), 1024.0))
    assert free.width < 240 <= floored.width + 0.5, (free.width, floored.width)
    print("  ✓  a weighted share below the floor is raised")


def test_the_floor_counts_the_padding_around_the_image():
    # The heading takes the image into a card, whose padding sits between the
    # cell's edge and the picture: the floor is the picture's, not the cell's.
    doc = "## Card\n" + _doc("md2ui.min_width=240")
    assert _image_box(_scene(doc, 1024.0)).width >= 240 - 0.5
    print("  ✓  the floor counts the padding around the image")


def test_a_floor_that_cannot_fit_wraps_the_row():
    # 480px of image beside the text does not fit 600px: the row stacks, and
    # the image takes the width instead of overflowing it.
    image = _image_box(_scene(_doc("md2ui.min_width=480"), 600.0))
    beside = _image_box(_scene(_doc("md2ui.fit=cover"), 600.0))
    assert beside.width < 300 < image.width <= 600, (beside.width, image.width)
    print("  ✓  a floor that cannot fit wraps the row")


def test_a_grid_of_floored_cards_keeps_the_floor():
    # Five cards of one kind share a column count, chosen from the kind's widest
    # member: that width must count each image's floor, or five 400px-floored
    # pictures are gridded five across at about 190px each.
    doc = "# Cards\n\n" + "".join(
        f"## Card {i}\n\n![Photo {i}]({_PHOTO}?md2ui.min_width=400"
        f"&md2ui.aspect_ratio=1:1)\n\nShort text {i}.\n\n"
        for i in range(1, 6)
    )
    for width in (1280.0, 900.0):
        scene = _scene(doc, width)
        images = [
            b.width
            for b in scene.boxes
            if (b.render_properties or {}).get("aspect_ratio")
        ]
        assert len(images) == 5 and min(images) >= 400 - 0.5, (width, images)
    print("  ✓  a grid of floored cards keeps the floor")


def test_a_floor_below_the_default_lowers_it():
    """An authored floor replaces the default one (``IMAGE_MIN_WIDTH``, 96px)
    rather than only raising it: beside a chip that leaves the
    picture a little under 96px, a floor of 80 keeps the row, and with no floor
    written the default still stacks it."""

    def tops(params: str) -> list[float]:
        doc = f"![Photo]({_PHOTO}?{params})\n:::\n`{'x' * 33}`\n"
        return [b.y for b in _scene(doc, 320.0).boxes]

    lowered, default = tops("md2ui.min_width=80"), tops("md2ui.fit=cover")
    assert len(lowered) == 2 and lowered[0] == lowered[1], lowered
    assert len(default) == 2 and default[0] < default[1], default
    print("  ✓  a floor below the default lowers it; no floor keeps the default")


TESTS = [
    test_min_width_is_an_authorable_param,
    test_a_floor_below_the_default_lowers_it,
    test_the_ceiling_wins_over_the_floor,
    test_a_weighted_share_below_the_floor_is_raised,
    test_the_floor_counts_the_padding_around_the_image,
    test_a_floor_that_cannot_fit_wraps_the_row,
    test_a_grid_of_floored_cards_keeps_the_floor,
]

if __name__ == "__main__":
    print("Image Min Width Tests")
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
