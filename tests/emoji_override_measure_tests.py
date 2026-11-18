"""
An emoji ``Font:`` override under ``## Emoji styles`` -- ``### Text`` for prose,
``### Link`` for a link label, ``### Inline`` for an inline-code chip -- is the
face the glyph is measured in as well as painted in, so the box sized for a
text holds exactly what is drawn there (ADR-400).

The default emoji face is OpenMoji; the override is Poppins, which lacks these
glyphs, so they fall back to a system face where ``✈`` is about half as wide:
measuring in the wrong face is a visible error, not a rounding one.

Each leaf is checked as ``measured width - painted width``: its padding, the
same with and without the override. The painted width is read off the draw
calls themselves, in the font each one was handed.

Run with: uv run python tests/emoji_override_measure_tests.py
"""

import tempfile
from pathlib import Path

from md2ui import session
from md2ui.pipeline import layout_render
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.render_glyph_faces import runs_advance
from md2ui.pipeline.render_measure import _leaf_natural_width
from md2ui.utils.image_cache import ImageCache

_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
# One leaf per context; `Flight ⚔: 40%` is a bar whose key's `#### Key` names its
# own family, so the role swaps the leaf's fonts after the prose face is chosen.
_DOC = "Fly to Lisbon ✈\n\n[Write ✉](/b)\n\n`Settings ⚙`\n\nFlight ⚔: 40%\n"
_LEAVES = {
    "text": ("Fly to Lisbon ✈", None),
    "link": ("Write ✉", None),
    "inline_code": ("Settings ⚙", None),
    "key": ("Flight ⚔", {"kv_role": "key"}),
}
_KIT: list = []


def _theme(override: bool) -> str:
    face = f"Font: {_FONTS / 'Poppins-Regular.ttf'}\n" if override else ""
    return (
        f"## Fonts\n- {_FONTS / 'Inter_18pt-Regular.ttf'}\n"
        f"- {_FONTS / 'Inter_18pt-Bold.ttf'}\n"
        f"- {_FONTS / 'WorkSans-Regular.ttf'}\n"
        "\n## Styling & Spacing\n\n### Root\n\n#### Key\n- Font name: Work Sans\n"
        f"\n## Emoji styles\nFont: {_FONTS / 'OpenMoji-black-glyf.ttf'}\n"
        + "".join(f"\n### {ctx}\n{face}" for ctx in ("Text", "Link", "Inline"))
    )


def _widths(override: bool) -> dict[str, tuple[float, float]]:
    """``{leaf: (measured width, painted width)}`` for each leaf of ``_DOC``."""
    if not _KIT:
        _KIT.append(session.load_grouping_kit())
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(_theme(override))
        theme = session.load_theme(path)
    fonts = session.load_fonts(theme)
    root = session.group_markdown(_DOC, _KIT[0])
    assert root is not None
    root, index = session.prepare(root, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 600.0)

    drawn: list[tuple[str, float, float]] = []
    real = layout_render._draw_text_with_emoji

    def record(canvas, text, x, y, font, emoji_tf, size, *args, **kwargs):
        drawn.append((text, x, x + runs_advance(text, font, emoji_tf, size)))
        return real(canvas, text, x, y, font, emoji_tf, size, *args, **kwargs)

    layout_render._draw_text_with_emoji = record
    try:
        session.render_image(scene, index, theme, fonts, ImageCache(), {}, 1.0)
    finally:
        layout_render._draw_text_with_emoji = real

    def painted(label: str) -> float:
        # A pill draws its label whole; prose draws it word by word.
        hits = [d for d in drawn if d[0] == label] or [
            d for d in drawn if d[0] in label.split(" ")
        ]
        return max(h[2] for h in hits) - min(h[1] for h in hits)

    out = {}
    for nd in index.values():
        for name, (label, rp) in _LEAVES.items():
            content = nd.get("content", "")
            if content.strip("`") == label or f"[{label}]" in content:
                measured = _leaf_natural_width(nd, 600.0, fonts, theme, rp)
                out[name] = (measured, painted(label))
    assert set(out) == set(_LEAVES), sorted(out)
    return out


def test_override_is_measured_in_the_face_it_paints():
    plain, over = _widths(False), _widths(True)
    for name in _LEAVES:
        (m0, p0), (m1, p1) = plain[name], over[name]
        # Not vacuous: the override really draws the glyph at another width. How
        # much wider is the host's fallback face's business: about half on macOS,
        # 1.5px at 13px for ✉ in Linux's Noto Sans Symbols2 -- far above the
        # 0.01 the check below allows.
        assert abs(p1 - p0) > 1, (name, p0, p1)
        assert abs((m1 - p1) - (m0 - p0)) < 0.01, (name, m0 - p0, m1 - p1)
    assert over["text"][0] == over["text"][1], over["text"]
    print("  ✓  prose, key, link-label and inline emoji measure as they paint")


TESTS = [test_override_is_measured_in_the_face_it_paints]


if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"All {len(TESTS)} tests passed.")
