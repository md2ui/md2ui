"""Shadows: the clip each kind uses, and where its blur reaches.

The two kinds are not mirror images. An INNER shadow is clipped to the shape
and blurs everything outside the shape once it has been moved by the offset; an
OUTER one is clipped to the shape's bounds grown by ``radius`` and moved by the
offset, with the shape cut out. What follows checks the geometry that
distinguishes them — which side of the edge ink lands on, that the shape itself
is never darkened by its own outer shadow, and that the reach really is
``radius / 2`` — plus the THEME.md keys that declare them.

The sigma this uses (``radius / 4``) reproduces the reference renders in
``data/markdown/tests-render/theme-tests/shadows/``.
"""

from pathlib import Path
import sys
import tempfile

import numpy as np
import skia

sys.path.insert(0, "tests")

from color_replacement_tests import _pixel

from md2ui.pipeline.render_fills import _paint_layered_fill
from md2ui.theme_lint import dropped_shadows
from md2ui.pipeline.render_shadows import paint_shadows, shape_path
from md2ui.pipeline.theme import SHADOW_MAX_PER_KIND, ShadowSpec, parse_theme
from md2ui.pipeline.theme_model import SHADOW_SIGMA_RATIO

BLACK = 0xFF000000
WHITE = 0xFFFFFFFF

# A 200x200 canvas with the shape at (60,60)-(140,140), so there is 60px of
# clear ground on every side to look for the shadow in.
_SIZE = 200
_BOX = (60.0, 60.0, 80.0, 80.0)


def _render(
    shadows: list[ShadowSpec],
    *,
    corner_radius: float = 0.0,
    fill: "int | None" = WHITE,
) -> skia.Surface:
    surface = skia.Surface(_SIZE, _SIZE)
    surface.getCanvas().clear(WHITE)
    _paint_layered_fill(
        surface.getCanvas(),
        skia.Rect.MakeXYWH(*_BOX),
        bg_color=fill,
        image=None,
        gradient=None,
        corner_radius=corner_radius,
        shadows=shadows,
    )
    return surface


def _darkness(surface: skia.Surface, x: int, y: int) -> int:
    """How far this pixel is from white, on a white ground."""
    return 255 - _pixel(surface, x, y)[0]


def _outer(**kw) -> ShadowSpec:
    return ShadowSpec(inner=False, color=BLACK, **kw)


def _inner(**kw) -> ShadowSpec:
    return ShadowSpec(inner=True, color=BLACK, **kw)


def test_outer_shadow_falls_outside_the_shape_only():
    """The shape is cut out of an outer shadow's clip, so a translucent fill
    never has the shadow showing through it."""
    surface = _render([_outer(offset_x=20.0, offset_y=20.0, radius=20.0)], fill=None)
    assert _darkness(surface, 100, 100) == 0, "inside the shape stayed clean"
    assert _darkness(surface, 150, 150) > 0, "outside it, the offset copy landed"
    print("  ✓  an outer shadow paints outside the shape and never under it")


def test_outer_shadow_reach_is_half_the_radius():
    """``radius`` is the distance the blur travels past the edge — which is
    also where the clip box ends, so the two agree and nothing is cut."""
    surface = _render([_outer(radius=40.0)])
    right = int(_BOX[0] + _BOX[2])  # the shape's right edge
    assert _darkness(surface, right + 4, 100) > 0, "ink just past the edge"
    assert _darkness(surface, right + 12, 100) > 0, "still ink mid-reach"
    assert _darkness(surface, right + 24, 100) == 0, "nothing past radius / 2"
    print("  ✓  an outer shadow reaches radius / 2 past the edge and stops")


def test_inner_shadow_darkens_the_side_the_offset_came_from():
    """A positive offset moves the shape down-right, so what is left showing
    inside the clip is its top-left edge."""
    surface = _render([_inner(offset_x=12.0, offset_y=12.0, radius=10.0)])
    top_left = _darkness(surface, 64, 64)
    bottom_right = _darkness(surface, 136, 136)
    assert top_left > 0, "the top-left inside edge darkened"
    assert top_left > bottom_right, "and the opposite corner much less so"
    assert _darkness(surface, 160, 160) == 0, "nothing outside the shape"
    print("  ✓  an inner shadow darkens the edge the offset moved away from")


def test_inner_shadow_with_no_offset_rings_every_edge():
    surface = _render([_inner(radius=24.0)])
    edges = [
        _darkness(surface, 64, 100),
        _darkness(surface, 136, 100),
        _darkness(surface, 100, 64),
        _darkness(surface, 100, 136),
    ]
    assert all(e > 0 for e in edges), f"all four edges darkened: {edges}"
    assert _darkness(surface, 100, 100) < min(edges), "the middle stays lighter"
    print("  ✓  an unoffset inner shadow rings all four edges")


def test_a_shadow_paints_without_any_fill():
    """The silhouette is the shape, not the ink in it, so a box with shadows
    and no background still casts them."""
    surface = _render([_outer(offset_y=16.0, radius=16.0)], fill=None)
    assert _darkness(surface, 100, 150) > 0
    print("  ✓  a box with no fill still casts its shadow")


def test_a_transparent_shadow_paints_nothing():
    surface = _render([ShadowSpec(color=0x00000000, offset_y=16.0, radius=16.0)])
    assert _darkness(surface, 100, 150) == 0
    print("  ✓  a shadow with no alpha is inert")


def test_layers_accumulate_in_declared_order():
    one = _render([_outer(offset_y=14.0, radius=16.0)])
    two = _render(
        [_outer(offset_y=14.0, radius=16.0), _outer(offset_y=14.0, radius=16.0)]
    )
    assert _darkness(two, 100, 150) > _darkness(one, 100, 150)
    print("  ✓  two declared layers both paint")


def _theme_with(block: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "THEME.md"
        path.write_text(block)
        return parse_theme(path)


_ONE = """## Background styles and Spacing

### Image Cards

Background color: #FFFFFF

Outer shadow:
- Offset x: 2
- Offset y: 4
- Color: #12345680
- Radius: 30

Inner shadow:
- OffsetX: -1
- OffsetY: -2
- Color: #654321FF
- Radius: 400
"""


def test_theme_parses_both_kinds_and_clamps_the_radius():
    theme = _theme_with(_ONE)
    outer, inner = theme.image_cards.shadows
    assert (outer.inner, outer.offset_x, outer.offset_y, outer.radius) == (
        False,
        2.0,
        4.0,
        30.0,
    )
    assert outer.color == skia.ColorSetARGB(0x80, 0x12, 0x34, 0x56)
    assert (inner.inner, inner.offset_x, inner.offset_y) == (True, -1.0, -2.0)
    assert inner.radius == 250.0, "over the maximum, clamped rather than dropped"
    print("  ✓  both kinds parse, OffsetX/OffsetY too, and radius clamps at 250")


def test_a_shadow_block_does_not_capture_the_colour_lists():
    """A shadow's bullets look like a colour list's. The parser must not let
    them land in ``bg_colors``, nor the list keys reach into the shadow."""
    theme = _theme_with(
        """## Background styles and Spacing

### Image Cards

Outer shadow:
- Offset x: 3
- Color: #111111FF
- Radius: 8

Background color:
- #AAAAAA
- #BBBBBB
"""
    )
    assert [hex(c) for c in theme.image_cards.bg_colors] == ["0xffaaaaaa", "0xffbbbbbb"]
    (shadow,) = theme.image_cards.shadows
    assert shadow.offset_x == 3.0 and shadow.radius == 8.0
    print("  ✓  a shadow block and a colour list keep their own bullets")


def test_more_than_four_of_one_kind_are_dropped():
    block = "## Background styles and Spacing\n\n### Image Cards\n\n" + "".join(
        f"Outer shadow:\n- Radius: {i}\n- Color: #000000FF\n\n" for i in range(6)
    )
    theme = _theme_with(block)
    assert SHADOW_MAX_PER_KIND == 4
    assert [s.radius for s in theme.image_cards.shadows] == [0.0, 1.0, 2.0, 3.0]
    print("  ✓  a fifth shadow of one kind is dropped, keeping the first four")


def _layers(n: int, kind: str, first_radius: int) -> str:
    return "".join(
        f"{kind} shadow:\n- Radius: {first_radius + i}\n- Color: #000000FF\n"
        for i in range(n)
    )


def _radii(shadows, inner: bool) -> list[float]:
    return [s.radius for s in shadows if s.inner == inner]


def test_a_variant_replaces_primarys_shadows_kind_by_kind():
    """A variant's colour lists replace Primary's, and so do its shadows: a kind
    it declares replaces Primary's of that kind, a kind it declares none of is
    inherited. Buttons, chips and badges alike, so none ever holds more than the
    cap, and a small badge does not also cast the large one's glow."""
    primary = _layers(4, "Outer", 10) + _layers(1, "Inner", 50)
    own = _layers(2, "Outer", 20)
    theme = _theme_with(
        f"## Links\n### Primary\n{primary}### Secondary\n{own}"
        f"## Inline Code\n{primary}### Secondary\n{own}"
        f"## Emoji styles\n### Primary\n{primary}### Secondary\n{own}"
    )
    for name, shadows in (
        ("button", theme.links.resolved("secondary").shadows),
        ("chip", theme.inline_code.resolved("secondary").shadows),
        ("badge", theme.emojis.resolved("secondary").fill.shadows),
    ):
        assert _radii(shadows, False) == [20.0, 21.0], f"{name}: its own outer layers"
        assert _radii(shadows, True) == [50.0], f"{name}: Primary's inner, inherited"
    for name, shadows in (
        ("button", theme.links.resolved("primary").shadows),
        ("chip", theme.inline_code.shadows),
        ("badge", theme.emojis.primary.fill.shadows),
    ):
        assert _radii(shadows, False) == [10.0, 11.0, 12.0, 13.0], f"{name} Primary"
    print("  ✓  a variant's shadows replace Primary's of that kind, and keep the other")


def test_a_variant_may_declare_the_full_cap_of_its_own():
    """Primary's layers no longer count toward a variant's cap: replaced first,
    then the variant's own are counted."""
    primary = _layers(4, "Outer", 10)
    own = _layers(4, "Outer", 30)
    theme = _theme_with(
        f"## Inline Code\n{primary}### Secondary\n{own}"
        f"## Emoji styles\n### Primary\n{primary}### Secondary\n{own}"
    )
    for shadows in (
        theme.inline_code.resolved("secondary").shadows,
        theme.emojis.resolved("secondary").fill.shadows,
    ):
        assert _radii(shadows, False) == [30.0, 31.0, 32.0, 33.0]
    print("  ✓  a variant keeps all four of its own, whatever Primary declared")


def test_a_bare_shadow_key_is_the_outer_one():
    theme = _theme_with(
        "## Background styles and Spacing\n\n### Root\n\nShadow:\n- Radius: 12\n"
    )
    (shadow,) = theme.root.shadows
    assert shadow.inner is False and shadow.radius == 12.0
    print("  ✓  a bare `Shadow:` is the outer one, and Root takes it")


def test_the_shadow_shape_follows_the_corner_radius():
    """The fill's clip and the shadow's silhouette come from one helper, so a
    rounded box casts a rounded shadow rather than a square one."""
    rect = skia.Rect.MakeXYWH(*_BOX)
    assert shape_path(rect, 0.0).isRect(), "square by default"
    assert not shape_path(rect, 20.0).isRect(), "and rounded once asked"
    assert shape_path(rect, 0.0, dx=5.0).getBounds().left() == _BOX[0] + 5.0
    print("  ✓  the shadow silhouette is the shape the fill clips to")


def test_paint_shadows_ignores_the_other_kind():
    """The entry point is called twice per box — under the fill and over it —
    and each pass must leave the other pass's layers alone."""
    surface = skia.Surface(_SIZE, _SIZE)
    surface.getCanvas().clear(WHITE)
    paint_shadows(
        surface.getCanvas(),
        skia.Rect.MakeXYWH(*_BOX),
        0.0,
        [_outer(offset_y=20.0, radius=20.0)],
        inner=True,
    )
    assert _darkness(surface, 100, 150) == 0
    print("  ✓  the inner pass leaves the outer layers to the outer pass")


def _path_blur(canvas, rect, corner_radius, oval, sh) -> None:
    """The reference: every shadow as a blurred PATH, as all of them were drawn
    before rounded rects moved to Skia's rounded-rect blur. Outer: the moved
    shape, clipped to the grown box minus the shape. Inner: a field minus the
    moved shape, clipped to the shape."""
    paint = skia.Paint(Color=sh.color, AntiAlias=True)
    paint.setMaskFilter(
        skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sh.radius * SHADOW_SIGMA_RATIO)
    )
    shape = shape_path(rect, corner_radius, oval=oval)
    moved = shape_path(rect, corner_radius, oval=oval, dx=sh.offset_x, dy=sh.offset_y)
    canvas.save()
    if sh.inner:
        margin = sh.radius + abs(sh.offset_x) + abs(sh.offset_y) + 8.0
        field = skia.Path()
        field.addRect(rect.makeOutset(margin, margin))
        canvas.clipPath(shape, skia.ClipOp.kIntersect, True)
        canvas.drawPath(skia.Op(field, moved, skia.PathOp.kDifference_PathOp), paint)
    else:
        reach = sh.radius / 2.0
        box = skia.Path()
        box.addRect(rect.makeOutset(reach, reach).makeOffset(sh.offset_x, sh.offset_y))
        clip = skia.Op(box, shape, skia.PathOp.kDifference_PathOp)
        canvas.clipPath(clip, skia.ClipOp.kIntersect, True)
        canvas.drawPath(moved, paint)
    canvas.restore()


def _both_ways(sh: ShadowSpec, corner_radius: float, oval: bool = False):
    """(today's painter, the path-blur reference) for one layer, as pixel arrays."""
    rect = skia.Rect.MakeXYWH(*_BOX)
    out = []
    for draw in (
        lambda c: paint_shadows(
            c, rect, corner_radius, [sh], inner=sh.inner, oval=oval
        ),
        lambda c: _path_blur(c, rect, corner_radius, oval, sh),
    ):
        surface = skia.Surface(_SIZE, _SIZE)
        surface.getCanvas().clear(WHITE)
        draw(surface.getCanvas())
        out.append(
            surface.makeImageSnapshot()
            .toarray(colorType=skia.kRGBA_8888_ColorType)
            .astype(np.int16)
        )
    return out


_LAYERS = [
    _outer(offset_y=6.0, radius=6.0),
    _outer(offset_x=-8.0, offset_y=14.0, radius=40.0),
    _inner(offset_x=-4.0, offset_y=4.0, radius=6.0),
    _inner(offset_x=4.0, offset_y=-5.0, radius=10.0),
    _inner(radius=40.0),
]


def test_a_rounded_rect_shadow_matches_the_path_blur():
    """A rounded rect's shadow goes through Skia's rounded-rect blur, which
    renders one small corner tile and stretches it instead of blurring the whole
    area (30 ms against 0.2 ms for one layer on a page-sized panel). Its falloff
    is not the path blur's to the last bit; this pins how close it stays. The
    layers are opaque black, the harshest case: 18/255 at worst, on the rounded
    corners' antialiased rim, where a translucent shadow differs by less."""
    for sh in _LAYERS:
        today, reference = _both_ways(sh, corner_radius=16.0)
        worst = int(np.abs(today - reference).max())
        assert worst <= 24, f"{sh}: off the path blur by {worst}/255"
    print("  ✓  a rounded rect's shadow stays within 24/255 of the path blur")


def test_an_oval_and_a_square_inner_shadow_keep_the_path_blur():
    """Skia's raster backend has no fast blur for an oval, and already special-
    cases a plain rect's path: both keep the path, so they draw exactly as before."""
    for sh in _LAYERS:
        today, reference = _both_ways(sh, corner_radius=0.0, oval=True)
        assert (today == reference).all(), f"oval {sh} moved"
    for sh in (layer for layer in _LAYERS if layer.inner):
        today, reference = _both_ways(sh, corner_radius=0.0)
        assert (today == reference).all(), f"square inner {sh} moved"
    print("  ✓  ovals and square inner shadows keep the path blur, bit for bit")


def test_the_lint_names_a_block_whose_shadows_are_dropped():
    """The parser drops a fifth layer of a kind without a word; `check --theme`
    says which block, and how many of its layers paint. A commented layer is not
    read, so it is not counted."""
    four = "## Links\n### Secondary\n" + _layers(4, "Outer", 1) + _layers(4, "Inner", 1)
    assert dropped_shadows(four) == [], "four of each kind all paint"
    five = four + _layers(1, "Outer", 9)
    found = dropped_shadows(five)
    assert len(found) == 1, found
    assert "`## Links > ### Secondary`" in found[0] and "5 outer" in found[0], found
    commented = four + "<!--\n" + _layers(1, "Outer", 9) + "-->\n"
    assert dropped_shadows(commented) == []
    section_keys = "## Charts\n" + _layers(5, "Inner", 1) + "### Chart Grid\n"
    assert "`## Charts` declares 5 inner" in dropped_shadows(section_keys)[0]
    print("  ✓  the lint names a block with more shadows of a kind than are painted")


TESTS = [
    test_the_shadow_shape_follows_the_corner_radius,
    test_paint_shadows_ignores_the_other_kind,
    test_outer_shadow_falls_outside_the_shape_only,
    test_outer_shadow_reach_is_half_the_radius,
    test_inner_shadow_darkens_the_side_the_offset_came_from,
    test_inner_shadow_with_no_offset_rings_every_edge,
    test_a_shadow_paints_without_any_fill,
    test_a_transparent_shadow_paints_nothing,
    test_layers_accumulate_in_declared_order,
    test_a_rounded_rect_shadow_matches_the_path_blur,
    test_an_oval_and_a_square_inner_shadow_keep_the_path_blur,
    test_theme_parses_both_kinds_and_clamps_the_radius,
    test_a_shadow_block_does_not_capture_the_colour_lists,
    test_more_than_four_of_one_kind_are_dropped,
    test_a_variant_replaces_primarys_shadows_kind_by_kind,
    test_a_variant_may_declare_the_full_cap_of_its_own,
    test_the_lint_names_a_block_whose_shadows_are_dropped,
    test_a_bare_shadow_key_is_the_outer_one,
]
