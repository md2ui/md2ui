"""
Unit tests for SVG rasterizing and the vector fit rule:

  * _rasterize_svg scales the CANVAS rather than the container, so a vector with
    intrinsic width/height is actually magnified instead of drawn at 1:1 in the
    top-left corner of a bigger surface;
  * _trim_to_ink crops the transparent padding so the artwork starts at (0,0);
  * draw_image_box fits a vector whole (contain) but still cover-crops a photo,
    and an explicit `fit` hint (?md2ui.fit=contain|cover) overrides that default.
Run with: uv run svg_raster_tests.py
"""

import numpy as np
import skia

from md2ui.utils.image_cache import _rasterize_svg, _trim_to_ink, decode_image
from md2ui.utils.font_loader import make_font

_SVG_RENDER_MAX = 512


# ---------------------------------------------------------------------------
# Fixtures — SVGs whose ink occupies a KNOWN sub-rect of their canvas
# ---------------------------------------------------------------------------


def _svg(width: int, height: int, rect: str, viewbox: str = "") -> bytes:
    vb = f' viewBox="{viewbox}"' if viewbox else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}"{vb}>{rect}</svg>'
    ).encode()


# A 100x100 canvas whose ink is the middle 50x50 (25..75 on both axes) — the
# real-world shape: play-console.svg paints inside ~35% of its own box.
CENTERED = _svg(100, 100, '<rect x="25" y="25" width="50" height="50" fill="#000"/>')
# Ink flush to the canvas edges: trimming must be a no-op on the bounds.
FULL_BLEED = _svg(100, 100, '<rect x="0" y="0" width="100" height="100" fill="#000"/>')
# Nothing drawn at all.
EMPTY = _svg(100, 100, "")
# Non-square, to check aspect survives.
WIDE = _svg(200, 100, '<rect x="0" y="0" width="200" height="100" fill="#000"/>')


def _alpha(img: skia.Image) -> np.ndarray:
    return img.toarray(colorType=skia.kRGBA_8888_ColorType)[:, :, 3]


def _coverage(img: skia.Image) -> float:
    a = _alpha(img)
    return 100.0 * np.count_nonzero(a) / a.size


# ---------------------------------------------------------------------------
# 1. Scale
# ---------------------------------------------------------------------------


def test_vector_is_magnified_not_drawn_at_1_to_1():
    """setContainerSize does not rescale an SVG with intrinsic width/height, so
    scaling the container alone leaves the art at 1:1 in the top-left corner."""
    img = _rasterize_svg(FULL_BLEED)
    assert img is not None
    # Full-bleed art fills its canvas, so after scaling it must fill the raster
    # at ~512px — not sit as a 100px square in the corner.
    assert img.width() >= _SVG_RENDER_MAX - 1, (
        f"vector not magnified: raster is {img.width()}px wide"
    )
    assert _coverage(img) > 99.0, f"coverage {_coverage(img):.1f}%"
    print("  ✓  a vector is magnified to the render size, not drawn at 1:1")


def test_aspect_ratio_is_preserved():
    img = _rasterize_svg(WIDE)
    assert img is not None
    assert abs(img.width() / img.height() - 2.0) < 0.02, (
        f"expected 2:1, got {img.width()}x{img.height()}"
    )
    print("  ✓  a non-square vector keeps its aspect through the scale")


# ---------------------------------------------------------------------------
# 2. Trim to ink — "transfer the vector to origin"
# ---------------------------------------------------------------------------


def test_trim_moves_the_art_to_the_origin():
    img = _rasterize_svg(CENTERED)
    assert img is not None
    a = _alpha(img)
    ys, xs = np.nonzero(a)
    assert xs.min() == 0 and ys.min() == 0, (
        f"art must start at (0,0), got ({xs.min()},{ys.min()})"
    )
    assert xs.max() == img.width() - 1 and ys.max() == img.height() - 1, (
        "art must extend to the far edge — no trailing padding"
    )
    # The source's ink was 50 of 100 units square, so the trimmed raster is
    # about half the render size and the art now fills it completely.
    assert abs(img.width() - _SVG_RENDER_MAX / 2) < 4, img.width()
    assert _coverage(img) > 99.0, f"coverage {_coverage(img):.1f}%"
    print("  ✓  transparent padding trimmed; the vector starts at the origin")


def test_full_bleed_art_is_unchanged_by_trimming():
    img = _rasterize_svg(FULL_BLEED)
    assert img is not None
    assert img.width() >= _SVG_RENDER_MAX - 1
    print("  ✓  art already flush to its bounds is not trimmed further")


def test_fully_transparent_svg_survives():
    """An empty bbox has no crop rect — the image must come back untouched
    rather than raising or collapsing to zero."""
    img = _rasterize_svg(EMPTY)
    assert img is not None, "an inkless SVG must still decode"
    assert img.width() > 0 and img.height() > 0
    # And the helper itself is safe on any blank surface.
    surface = skia.Surface(64, 64)
    surface.getCanvas().clear(skia.Color4f(0, 0, 0, 0))
    blank = surface.makeImageSnapshot()
    assert _trim_to_ink(blank).width() == 64
    print("  ✓  a fully transparent vector is returned untrimmed, not crashed")


def test_non_svg_bytes_still_return_none():
    assert _rasterize_svg(b"not an svg at all") is None
    assert decode_image(b"\x00\x01\x02") is None
    print("  ✓  non-SVG bytes still decode to None")


# ---------------------------------------------------------------------------
# 3. Fit: contain for vectors, cover for photos
# ---------------------------------------------------------------------------


def _fit(iw, ih, cw, ch, contain):
    """The two fit computations as draw_image_box performs them."""
    if contain:
        f = min(cw / iw, ch / ih)
        return iw * f, ih * f, 1.0  # whole source drawn
    scale = max(cw / iw, ch / ih)
    src_w, src_h = cw / scale, ch / scale
    return cw, ch, (src_w * src_h) / (iw * ih)  # fraction of source kept


def test_contain_never_crops_and_cover_still_does():
    # A 1:1 image in the width-conditioned default box (3:2 below 768px), where
    # cover would clip a square icon by a third of its height.
    cw, ch = 56.0, 56.0 / 1.5
    _, _, kept_cover = _fit(512, 512, cw, ch, contain=False)
    dw, dh, kept_contain = _fit(512, 512, cw, ch, contain=True)
    assert kept_cover < 0.7, f"cover should crop, kept {kept_cover:.0%}"
    assert kept_contain == 1.0, "contain must never crop"
    # And the fitted rect stays inside the box on both axes.
    assert dw <= cw + 1e-9 and dh <= ch + 1e-9, (dw, dh, cw, ch)
    print(
        f"  ✓  cover keeps {kept_cover:.0%} of a 1:1 image in a 3:2 box; "
        "contain keeps 100%"
    )


def test_contain_is_a_no_op_when_aspects_match():
    cw, ch = 200.0, 200.0
    dw, dh, _ = _fit(512, 512, cw, ch, contain=True)
    assert abs(dw - cw) < 1e-9 and abs(dh - ch) < 1e-9
    print("  ✓  contain fills the box exactly when the aspects already match")


# ---------------------------------------------------------------------------
# 4. The `fit` hint overrides the kind default (?md2ui.fit=)
# ---------------------------------------------------------------------------


def _painted_fraction(rp: dict, default_contain: bool) -> float:
    """Fraction of an 80x80 box actually painted, drawing a 2:1 opaque source.

    Contain letterboxes it to half the box; cover fills the whole box. Drawing
    for real (rather than recomputing the arithmetic) is the point — it is what
    catches a fit hint that never reaches the draw call.
    """
    from md2ui.pipeline.layout_render import draw_image_box
    from md2ui.pipeline.layout_script_parser import LayoutBox

    src = skia.Surface(100, 50)
    src.getCanvas().clear(skia.ColorSetARGB(255, 255, 0, 0))
    surface = skia.Surface(80, 80)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorWHITE)
    draw_image_box(
        canvas,
        LayoutBox(x=0, y=0, width=80, height=80),
        "![](x.svg)",
        make_font(skia.Typeface(""), 12),
        src.makeImageSnapshot(),
        rp,
        None,
        contain=default_contain,
    )
    a = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    red = (a[:, :, 0] > 200) & (a[:, :, 1] < 60)
    return np.count_nonzero(red) / red.size


def test_kind_default_contains_vectors_and_covers_photos():
    assert abs(_painted_fraction({}, True) - 0.5) < 0.02, "vector should letterbox"
    assert _painted_fraction({}, False) > 0.99, "photo should fill the box"
    print("  ✓  default by kind: a vector is contained, a photo covers")


def test_fit_hint_overrides_the_kind_default_both_ways():
    # A photo that must not be cropped...
    assert abs(_painted_fraction({"fit": "contain"}, False) - 0.5) < 0.02
    # ...and a vector meant to bleed to the edges.
    assert _painted_fraction({"fit": "cover"}, True) > 0.99
    print("  ✓  fit=contain / fit=cover override the kind default both ways")


def test_unknown_fit_value_falls_back_to_the_kind_default():
    """sanitize_url_props rejects a bad value before it gets here, but no other
    caller may produce a third behaviour."""
    assert abs(_painted_fraction({"fit": "bogus"}, True) - 0.5) < 0.02
    print("  ✓  an unrecognised fit value falls back to the kind default")


TESTS = [
    test_vector_is_magnified_not_drawn_at_1_to_1,
    test_aspect_ratio_is_preserved,
    test_trim_moves_the_art_to_the_origin,
    test_full_bleed_art_is_unchanged_by_trimming,
    test_fully_transparent_svg_survives,
    test_non_svg_bytes_still_return_none,
    test_contain_never_crops_and_cover_still_does,
    test_contain_is_a_no_op_when_aspects_match,
    test_kind_default_contains_vectors_and_covers_photos,
    test_fit_hint_overrides_the_kind_default_both_ways,
    test_unknown_fit_value_falls_back_to_the_kind_default,
]

if __name__ == "__main__":
    print("SVG Raster Tests")
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
