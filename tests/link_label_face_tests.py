"""
A link label draws in its own text style's face: the variant's ``## Text Styles``
block (``Links``, ``Links Secondary`` ... ``Links Text``) sets the label's family
and weight as well as its size, and a block that names neither keeps the body's
face. Measurement, paint and the click target resolve that face in one place
(``render_text_scopes.link_faces``, ADR-400), so a wider bold label still fits
the pill measured for it.

Run with: uv run python tests/link_label_face_tests.py
"""

import tempfile
from pathlib import Path

import skia
from md2ui import session
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.render_measure import _leaf_natural_width
from md2ui.utils.image_cache import ImageCache

_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FILL = (0xFF, 0xE9, 0xA8)  # the pill's fill, below
_KIT: list = []


def _theme(links_lines: str) -> str:
    return (
        "## Fonts\n"
        + "".join(
            f"- {_FONTS / f}.ttf\n"
            for f in ("GoogleSans-Regular", "GoogleSans-Bold", "WorkSans-Regular")
        )
        + "\n## Links\n\n### Primary\nFill color: #FFE9A8\nPadding: 10\n"
        + "\n## Text Styles\n\nText\n- Font Name: Google Sans\n- Font size: 20\n"
        + f"\nLinks\n- Font size: 20\n- Font color: #000000\n{links_lines}"
    )


def _render(links_lines: str, markdown: str = "[Weighted label](/x)"):
    """(measured pill width, painted image) of the one button *markdown* holds."""
    if not _KIT:
        _KIT.append(session.load_grouping_kit())
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(_theme(links_lines))
        theme = session.load_theme(path)
    fonts = session.load_fonts(theme)
    root = session.group_markdown(markdown + "\n", _KIT[0])
    assert root is not None
    root, index = session.prepare(root, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 400.0)
    link = next(n for n in index.values() if n.get("type") == "link")
    width = _leaf_natural_width(link, 400.0, fonts, theme)
    image = session.render_image(scene, index, theme, fonts, ImageCache(), {}, 1.0)
    return width, image


def _boxes(image: skia.Image):
    """Bounding boxes ``(x0, y0, x1, y1)`` of the pill fill and the dark ink."""
    arr = image.toarray(colorType=skia.kRGBA_8888_ColorType)  # RGBA rows
    fill, ink = [], []
    for y in range(arr.shape[0]):
        for x in range(arr.shape[1]):
            r, g, b = (int(v) for v in arr[y, x][:3])
            if (r, g, b) == _FILL:
                fill.append((x, y))
            elif r + g + b < 200:
                ink.append((x, y))

    def box(pts):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    return box(fill), box(ink), len(ink)


def _inside(inner, outer) -> bool:
    return (
        outer[0] < inner[0]
        and inner[2] < outer[2]
        and outer[1] < inner[1]
        and inner[3] < outer[3]
    )


def test_weight_is_measured_and_painted():
    w400, img400 = _render("- Font weight: 400\n")
    w700, img700 = _render("- Font weight: 700\n")
    assert w700 > w400 + 2, f"bold label measured no wider: {w400} vs {w700}"
    pill, ink, n700 = _boxes(img700)
    _p, _i, n400 = _boxes(img400)
    assert n700 > n400 * 1.15, f"bold label painted no heavier: {n400} vs {n700}"
    assert _inside(ink, pill), f"bold label overflows its pill: {ink} vs {pill}"
    assert abs((pill[2] - pill[0] + 1) - w700) <= 2, (pill, w700)
    print("  ✓  Links 'Font weight' sets the label's measured and painted weight")


def test_font_name_is_measured_and_painted():
    w_body, img_body = _render("")
    w_named, img_named = _render("- Font Name: Work Sans\n")
    assert abs(w_named - w_body) > 2, f"named face measured alike: {w_body}"
    pill, ink, _n = _boxes(img_named)
    assert _inside(ink, pill), f"named-face label overflows: {ink} vs {pill}"
    assert abs((pill[2] - pill[0] + 1) - w_named) <= 2, (pill, w_named)
    assert img_named.tobytes() != img_body.tobytes()
    print("  ✓  Links 'Font Name' sets the label's measured and painted family")


def test_no_font_keys_keeps_the_body_face():
    w_none, img_none = _render("")
    w_body, img_body = _render("- Font Name: Google Sans\n- Font weight: 400\n")
    assert w_none == w_body
    assert img_none.tobytes() == img_body.tobytes()
    print("  ✓  a Links block naming no family or weight keeps the body face")


_REGULAR, _BOLD = "- Font weight: 400\n", "- Font weight: 700\n"


def test_bold_label_is_the_links_own_bold_without_markers():
    """`[**x**](u)` is the label in its variant's bold: the same pixels as a
    `Links` block that sets weight 700, so no marker is drawn and the face is
    the link's own family, not the body's bold."""
    w_marked, img_marked = _render(_REGULAR, "[**Weighted label**](/x)")
    w_bold, img_bold = _render(_BOLD)
    assert w_marked == w_bold, f"bold label measured {w_marked}, not {w_bold}"
    assert img_marked.tobytes() == img_bold.tobytes()
    print("  ✓  [**x**](u) draws the link's own bold face, markers gone")


def test_italic_label_is_italic_not_the_muted_tier():
    """`[_x_](u)` keeps the label's size and colour: only the slant changes, so
    it measures exactly as the plain label (a slant moves no advance)."""
    w_plain, img_plain = _render(_REGULAR)
    w_italic, img_italic = _render(_REGULAR, "[_Weighted label_](/x)")
    assert w_italic == w_plain, f"italic label measured {w_italic}, not {w_plain}"
    assert img_italic.tobytes() != img_plain.tobytes(), "italic label drew upright"
    pill, ink, _n = _boxes(img_italic)
    assert _inside(ink, pill), f"italic label overflows: {ink} vs {pill}"
    print("  ✓  [_x_](u) is italic in the link's face, not the Muted tier")


def test_partial_emphasis_styles_only_its_span():
    w_plain, _img = _render(_REGULAR)
    w_bold, _img = _render(_BOLD)
    w_part, img_part = _render(_REGULAR, "[**Weighted** label](/x)")
    assert w_plain < w_part < w_bold, (w_plain, w_part, w_bold)
    pill, ink, _n = _boxes(img_part)
    assert _inside(ink, pill), f"partly bold label overflows: {ink} vs {pill}"
    assert abs((pill[2] - pill[0] + 1) - w_part) <= 2, (pill, w_part)
    print("  ✓  [**x** y](u) bolds only its span, measured as painted")


def test_emphasis_around_the_link_still_picks_the_variant():
    """`*[**x**](u)*`: the outer wrapper is the Secondary variant, the inner one
    styles the label in Secondary's bold; neither is drawn."""
    w_bold, img_bold = _render(_BOLD, "*[Weighted label](/x)*")
    w_marked, img_marked = _render(_REGULAR, "*[**Weighted label**](/x)*")
    assert w_marked == w_bold, f"bold label measured {w_marked}, not {w_bold}"
    assert img_marked.tobytes() == img_bold.tobytes()
    print("  ✓  *[**x**](u)* is Secondary with a bold label")


def test_label_spans_consume_only_emphasis():
    from md2ui.pipeline.render_text import link_label_spans, plain_link_label

    assert link_label_spans("**Got a Tip?** The Times", "primary") == [
        ("Got a Tip?", True, False),
        (" The Times", False, False),
    ]
    label = {"link_label": "___x___ `c` ~~s~~", "link_variant": "primary"}
    assert plain_link_label(label) == "x `c` ~~s~~"
    # A Text-variant label is a code span: its markers are literal.
    assert plain_link_label({"link_label": "**x**", "link_variant": "text"}) == "**x**"
    print("  ✓  a label loses its emphasis markers and keeps every other one")


TESTS = [
    test_weight_is_measured_and_painted,
    test_font_name_is_measured_and_painted,
    test_no_font_keys_keeps_the_body_face,
    test_bold_label_is_the_links_own_bold_without_markers,
    test_italic_label_is_italic_not_the_muted_tier,
    test_partial_emphasis_styles_only_its_span,
    test_emphasis_around_the_link_still_picks_the_variant,
    test_label_spans_consume_only_emphasis,
]


if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"All {len(TESTS)} tests passed.")
