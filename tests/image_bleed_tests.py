"""
Unit tests for per-level image bleed and image corner radius (THEME.md
``Image bleed`` / ``Image corner radius``, off by default):

  * an image expands over its level's padding on every inner edge it ALREADY
    touches — top image TLR, aside TLB/TRB, trailing LRB, middle LR;
  * while bleeding it takes the level's own corner radius, on just the corners
    the two rects now share;
  * a capped (max_width) image opts itself out, since it never fills its box;
  * a full-width or aside image that ends a stretched card's content runs
    down through the empty space below it, to the card's edge;
  * nothing at all happens until a level asks for it.
Run with: uv run image_bleed_tests.py
"""

from md2ui.pipeline.render_backgrounds import SectionBox
from md2ui.pipeline.render_place import bake_image_bleed
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.theme import PaddingBox, SectionStyle, Theme

PAD = 20.0
RADIUS = 24.0
# Card at (0,0) 300x400; its content is inset by PAD on every side.
CARD_X, CARD_Y, CARD_W, CARD_H = 0.0, 0.0, 300.0, 400.0
IN_L, IN_T = CARD_X + PAD, CARD_Y + PAD
IN_R, IN_B = CARD_X + CARD_W - PAD, CARD_Y + CARD_H - PAD


def _theme(bleed=True, radius=RADIUS, image_radius=0.0):
    t = Theme()
    t.sections[3] = SectionStyle(
        padding=PaddingBox(top=PAD, left=PAD, right=PAD, bottom=PAD),
        corner_radius=radius,
        image_bleed=bleed,
        image_corner_radius=image_radius,
        bg_colors=[0xFFEEEEEE],
    )
    return t


def _card(theme):
    return SectionBox(
        CARD_X, CARD_Y, CARD_W, CARD_H, 3, theme.sections[3].padding, "section"
    )


_INDEX = {"i": {"type": "image"}, "t": {"type": "text"}}


def _rest_of_card():
    """The card's last line: an image above it does not end the card's content."""
    return LayoutBox(
        x=IN_L, y=IN_B - 20.0, width=IN_R - IN_L, height=20.0, content_id="t"
    )


def _run(box, theme, *others):
    """*others* are the card's other boxes; by default, just its last line."""
    rest = others or (_rest_of_card(),)
    bake_image_bleed([box, *rest], [_card(theme)], _INDEX, theme)
    return box


def _rect(box):
    return (box.x, box.y, box.width, box.height)


def _radii(box):
    return (box.render_properties or {}).get("corner_radii")


def _img(x, y, w, h, **rp):
    return LayoutBox(
        x=x, y=y, width=w, height=h, content_id="i", render_properties=rp or None
    )


# ---------------------------------------------------------------------------
# Which edges bleed — "every inner edge it already touches"
# ---------------------------------------------------------------------------


def test_leading_image_bleeds_top_left_right():
    # Flush to the top of the card's content, full content width.
    box = _run(_img(IN_L, IN_T, IN_R - IN_L, 150.0), _theme())
    assert _rect(box) == (0.0, 0.0, 300.0, 170.0), _rect(box)
    print("  ✓  leading image bleeds TLR, not bottom")


def test_trailing_image_bleeds_left_right_bottom():
    box = _run(_img(IN_L, IN_B - 150.0, IN_R - IN_L, 150.0), _theme())
    assert _rect(box) == (0.0, 230.0, 300.0, 170.0), _rect(box)
    print("  ✓  trailing image bleeds LRB, not top")


def test_leading_aside_image_bleeds_top_left_bottom():
    # An aside cell: full content height, only part of the width.
    box = _run(_img(IN_L, IN_T, 100.0, IN_B - IN_T), _theme())
    assert _rect(box) == (0.0, 0.0, 120.0, 400.0), _rect(box)
    print("  ✓  leading aside bleeds TLB, not right")


def test_trailing_aside_image_bleeds_top_right_bottom():
    box = _run(_img(IN_R - 100.0, IN_T, 100.0, IN_B - IN_T), _theme())
    assert _rect(box) == (180.0, 0.0, 120.0, 400.0), _rect(box)
    print("  ✓  trailing aside bleeds TRB, not left")


def _text(x, y, w, h):
    return LayoutBox(x=x, y=y, width=w, height=h, content_id="t")


def test_middle_image_bleeds_left_right_only():
    # Siblings above AND below: the image touches neither, so neither bleeds —
    # the rule polices itself, an image can never bleed over a neighbour.
    below = _text(IN_L, 240.0, IN_R - IN_L, 40.0)
    box = _run(_img(IN_L, 120.0, IN_R - IN_L, 100.0), _theme(), below)
    assert _rect(box) == (0.0, 120.0, 300.0, 100.0), _rect(box)
    print("  ✓  middle image bleeds LR only — never over a sibling")


def test_image_touching_nothing_does_not_move():
    box = _img(IN_L + 30.0, 120.0, 100.0, 80.0)
    before = _rect(box)
    _run(box, _theme())
    assert _rect(box) == before, _rect(box)
    assert _radii(box) is None
    print("  ✓  an image touching no inner edge is left alone")


# ---------------------------------------------------------------------------
# A card stretched past its content (a bento band)
# ---------------------------------------------------------------------------


def test_image_ending_a_stretched_card_runs_to_its_bottom():
    # Text above, the image last, and the card taller than both: the space
    # below the image is the stretch, not a sibling, so the image fills it.
    above = _text(IN_L, IN_T, IN_R - IN_L, 40.0)
    box = _run(_img(IN_L, 80.0, IN_R - IN_L, 150.0), _theme(), above)
    assert _rect(box) == (0.0, 80.0, 300.0, 320.0), _rect(box)
    assert _radii(box) == (0.0, 0.0, RADIUS, RADIUS), _radii(box)
    print("  ✓  an image ending a stretched card reaches its bottom edge")


def test_aside_ending_a_stretched_card_runs_to_its_bottom():
    beside = _text(IN_L, IN_T, 160.0, 120.0)
    box = _run(_img(IN_R - 100.0, IN_T, 100.0, 200.0), _theme(), beside)
    assert _rect(box) == (180.0, 0.0, 120.0, 400.0), _rect(box)
    print("  ✓  an aside ending a stretched card bleeds TRB")


def test_aside_beside_a_longer_column_stays_short():
    # The text beside it reaches lower, so the image does not end the content.
    beside = _text(IN_L, IN_T, 160.0, 300.0)
    box = _run(_img(IN_R - 100.0, IN_T, 100.0, 200.0), _theme(), beside)
    assert _rect(box) == (180.0, 0.0, 120.0, 220.0), _rect(box)
    print("  ✓  an aside beside a longer column keeps its height")


def test_two_asides_ending_level_both_run_down():
    """Each is judged against where the other sat BEFORE bleeding, so the first
    to grow never blocks its twin."""
    theme = _theme()
    left = _img(IN_L, IN_T, 100.0, 200.0)
    right = _img(IN_R - 100.0, IN_T, 100.0, 200.0)
    bake_image_bleed([left, right], [_card(theme)], {"i": {"type": "image"}}, theme)
    assert _rect(left) == (0.0, 0.0, 120.0, 400.0), _rect(left)
    assert _rect(right) == (180.0, 0.0, 120.0, 400.0), _rect(right)
    print("  ✓  two asides ending together both run down")


def test_pictures_sharing_a_line_below_text_never_run_down():
    # Each touches one side only: neither full width nor an aside.
    theme = _theme()
    above = _text(IN_L, IN_T, IN_R - IN_L, 40.0)
    left = _img(IN_L, 80.0, 100.0, 100.0)
    right = _img(IN_R - 100.0, 80.0, 100.0, 100.0)
    bake_image_bleed([above, left, right], [_card(theme)], _INDEX, theme)
    assert _rect(left) == (0.0, 80.0, 120.0, 100.0), _rect(left)
    assert _rect(right) == (180.0, 80.0, 120.0, 100.0), _rect(right)
    print("  ✓  pictures sharing a line keep their height")


# ---------------------------------------------------------------------------
# Corner radii
# ---------------------------------------------------------------------------


def test_bleeding_image_takes_the_parents_radius_on_shared_corners_only():
    box = _run(_img(IN_L, IN_T, IN_R - IN_L, 150.0), _theme())
    # TL, TR shared with the card; BR, BL are mid-card and stay square.
    assert _radii(box) == (RADIUS, RADIUS, 0.0, 0.0), _radii(box)
    print("  ✓  bleeding TLR rounds the top pair only, at the card's radius")


def test_aside_rounds_the_two_corners_on_its_own_side():
    box = _run(_img(IN_L, IN_T, 100.0, IN_B - IN_T), _theme())
    assert _radii(box) == (RADIUS, 0.0, 0.0, RADIUS), _radii(box)
    print("  ✓  a left aside rounds TL and BL only")


def test_parent_radius_replaces_the_image_radius_while_bleeding():
    """The parent's shape wins, and the image's own is dropped —
    otherwise a top image would show rounded BOTTOM corners mid-card."""
    box = _run(_img(IN_L, IN_T, IN_R - IN_L, 150.0), _theme(image_radius=8.0))
    assert _radii(box) == (RADIUS, RADIUS, 0.0, 0.0), _radii(box)
    print("  ✓  while bleeding, image_corner_radius is ignored")


def test_image_corner_radius_applies_all_four_when_not_bleeding():
    box = _run(
        _img(IN_L, IN_T, IN_R - IN_L, 150.0), _theme(bleed=False, image_radius=8.0)
    )
    assert _rect(box) == (IN_L, IN_T, IN_R - IN_L, 150.0), "must not move"
    assert _radii(box) == (8.0, 8.0, 8.0, 8.0), _radii(box)
    print("  ✓  image_corner_radius rounds all four when not bleeding")


def test_bleeding_without_a_parent_radius_rounds_nothing():
    box = _run(_img(IN_L, IN_T, IN_R - IN_L, 150.0), _theme(radius=0.0))
    assert _rect(box) == (0.0, 0.0, 300.0, 170.0), "still bleeds"
    assert _radii(box) is None
    print("  ✓  a square card bleeds with no rounding")


# ---------------------------------------------------------------------------
# Opting out
# ---------------------------------------------------------------------------


def test_default_off_changes_nothing():
    theme = Theme()
    theme.sections[3] = SectionStyle(
        padding=PaddingBox(top=PAD, left=PAD, right=PAD, bottom=PAD),
        corner_radius=RADIUS,
        bg_colors=[0xFFEEEEEE],
    )  # neither key set
    box = _img(IN_L, IN_T, IN_R - IN_L, 150.0)
    before = _rect(box)
    bake_image_bleed([box], [_card(theme)], {"i": {"type": "image"}}, theme)
    assert _rect(box) == before and _radii(box) is None
    print("  ✓  a level that asked for neither key is untouched")


def test_capped_image_opts_itself_out():
    """max_width paints a small rect inside a big box, so bleeding would only
    shove the icon into the card's corner outside the rounded edge."""
    box = _run(_img(IN_L, IN_T, IN_R - IN_L, 150.0, max_width=56), _theme())
    assert _rect(box) == (IN_L, IN_T, IN_R - IN_L, 150.0), _rect(box)
    print("  ✓  a max_width-capped image never bleeds")


def test_non_image_boxes_are_ignored():
    box = LayoutBox(x=IN_L, y=IN_T, width=IN_R - IN_L, height=40.0, content_id="t")
    before = _rect(box)
    theme = _theme()
    bake_image_bleed([box], [_card(theme)], {"t": {"type": "text"}}, theme)
    assert _rect(box) == before and _radii(box) is None
    print("  ✓  only image leaves are touched")


def test_innermost_opted_in_level_wins_over_a_tighter_one():
    """The layers around an image nest, and the tightest is often a padding-free
    card. Letting that shadow the padded section that opted in would silently do
    nothing, so the innermost level that ASKED is the one that applies."""
    theme = _theme()
    theme.elements = SectionStyle(padding=PaddingBox())  # tighter, opted out
    inner_card = SectionBox(
        IN_L, IN_T, IN_R - IN_L, IN_B - IN_T, 0, theme.elements.padding, "card"
    )
    box = _img(IN_L, IN_T, IN_R - IN_L, 150.0)
    bake_image_bleed([box, _rest_of_card()], [_card(theme), inner_card], _INDEX, theme)
    assert _rect(box) == (0.0, 0.0, 300.0, 170.0), _rect(box)
    print("  ✓  a padding-free inner card does not shadow the level that opted in")


# ---------------------------------------------------------------------------
# Per-image overrides (?md2ui.bleed / ?md2ui.corner_radius)
# ---------------------------------------------------------------------------


def test_image_bleed_true_works_where_the_level_is_silent():
    """The param is self-sufficient: it falls back to the innermost ENCLOSING
    layer that has padding, so a one-off image bleeds with the theme silent."""
    theme = _theme(bleed=False, radius=RADIUS)  # level says nothing
    box = _run(_img(IN_L, IN_T, IN_R - IN_L, 150.0, bleed=True), theme)
    assert _rect(box) == (0.0, 0.0, 300.0, 170.0), _rect(box)
    assert _radii(box) == (RADIUS, RADIUS, 0.0, 0.0), _radii(box)
    print("  ✓  bleed=True bleeds a level that never opted in")


def test_image_bleed_false_opts_out_of_a_bleeding_level():
    box = _run(_img(IN_L, IN_T, IN_R - IN_L, 150.0, bleed=False), _theme())
    assert _rect(box) == (IN_L, IN_T, IN_R - IN_L, 150.0), _rect(box)
    print("  ✓  bleed=False excuses one image from a bleeding level")


def test_unset_bleed_falls_back_to_the_level():
    assert _rect(_run(_img(IN_L, IN_T, IN_R - IN_L, 150.0), _theme())) == (
        0.0,
        0.0,
        300.0,
        170.0,
    )
    assert _rect(_run(_img(IN_L, IN_T, IN_R - IN_L, 150.0), _theme(bleed=False))) == (
        IN_L,
        IN_T,
        IN_R - IN_L,
        150.0,
    )
    print("  ✓  an unset bleed defers to the level, both ways")


def test_image_corner_radius_beats_the_levels():
    box = _run(
        _img(IN_L, IN_T, IN_R - IN_L, 150.0, corner_radius=12),
        _theme(bleed=False, image_radius=8.0),
    )
    assert _radii(box) == (12, 12, 12, 12), _radii(box)
    print("  ✓  a per-image corner_radius overrides the level's")


def test_zero_corner_radius_squares_an_image_in_a_rounded_level():
    box = _run(
        _img(IN_L, IN_T, IN_R - IN_L, 150.0, corner_radius=0),
        _theme(bleed=False, image_radius=8.0),
    )
    assert _radii(box) is None, _radii(box)
    print("  ✓  corner_radius=0 is an explicit square, not 'unset'")


def test_per_image_radius_needs_no_opted_in_layer():
    """It eats no padding and changes no geometry, so it applies wherever it is
    authored — otherwise it could only round images the theme already rounds."""
    box = _run(
        _img(IN_L, IN_T, IN_R - IN_L, 150.0, corner_radius=10),
        _theme(bleed=False, radius=0.0),  # level mentions images not at all
    )
    assert _radii(box) == (10, 10, 10, 10), _radii(box)
    print("  ✓  a per-image radius works in a level that says nothing")


def test_parent_radius_still_wins_while_bleeding():
    box = _run(
        _img(IN_L, IN_T, IN_R - IN_L, 150.0, bleed=True, corner_radius=4),
        _theme(bleed=False),
    )
    assert _radii(box) == (RADIUS, RADIUS, 0.0, 0.0), _radii(box)
    print("  ✓  while bleeding, the parent's radius still beats the image's")


def test_bleed_never_escapes_into_a_sibling_section():
    """The containment guard. Candidates are enclosing layers only, so an image
    asking to bleed can never reach a level it is not inside."""
    theme = _theme(bleed=False)
    left = SectionBox(0, 0, 300, 400, 3, theme.sections[3].padding, "section")
    right = SectionBox(320, 0, 300, 400, 3, theme.sections[3].padding, "section")
    box = _img(IN_L, IN_T, IN_R - IN_L, 150.0, bleed=True)
    bake_image_bleed([box, _rest_of_card()], [left, right], _INDEX, theme)
    assert _rect(box) == (0.0, 0.0, 300.0, 170.0), _rect(box)
    assert box.x + box.width <= 300.0 + 1e-9, "bled past its own section"
    print("  ✓  a bleed stays inside its own section, never a sibling's")


def test_capped_image_still_opts_out_even_when_it_asks():
    box = _run(
        _img(IN_L, IN_T, IN_R - IN_L, 150.0, bleed=True, max_width=56),
        _theme(bleed=False),
    )
    assert _rect(box) == (IN_L, IN_T, IN_R - IN_L, 150.0), _rect(box)
    print("  ✓  max_width still wins over an explicit bleed=True")


TESTS = [
    test_leading_image_bleeds_top_left_right,
    test_trailing_image_bleeds_left_right_bottom,
    test_leading_aside_image_bleeds_top_left_bottom,
    test_trailing_aside_image_bleeds_top_right_bottom,
    test_middle_image_bleeds_left_right_only,
    test_image_touching_nothing_does_not_move,
    test_image_ending_a_stretched_card_runs_to_its_bottom,
    test_aside_ending_a_stretched_card_runs_to_its_bottom,
    test_aside_beside_a_longer_column_stays_short,
    test_two_asides_ending_level_both_run_down,
    test_pictures_sharing_a_line_below_text_never_run_down,
    test_bleeding_image_takes_the_parents_radius_on_shared_corners_only,
    test_aside_rounds_the_two_corners_on_its_own_side,
    test_parent_radius_replaces_the_image_radius_while_bleeding,
    test_image_corner_radius_applies_all_four_when_not_bleeding,
    test_bleeding_without_a_parent_radius_rounds_nothing,
    test_default_off_changes_nothing,
    test_capped_image_opts_itself_out,
    test_non_image_boxes_are_ignored,
    test_innermost_opted_in_level_wins_over_a_tighter_one,
    test_image_bleed_true_works_where_the_level_is_silent,
    test_image_bleed_false_opts_out_of_a_bleeding_level,
    test_unset_bleed_falls_back_to_the_level,
    test_image_corner_radius_beats_the_levels,
    test_zero_corner_radius_squares_an_image_in_a_rounded_level,
    test_per_image_radius_needs_no_opted_in_layer,
    test_parent_radius_still_wins_while_bleeding,
    test_bleed_never_escapes_into_a_sibling_section,
    test_capped_image_still_opts_out_even_when_it_asks,
]

if __name__ == "__main__":
    print("Image Bleed Tests")
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
