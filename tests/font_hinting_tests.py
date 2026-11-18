"""Text measures the same on every platform: every font md2ui builds is slightly hinted.

At Skia's default (normal) hinting, FreeType (Linux) rounds an upright glyph's
advance to whole pixels, while CoreText (macOS) ignores hinting for advances: the
same text measured wider on Linux, wrapped differently, and a page laid out
differently than on macOS or in a browser. ``font_loader.make_font`` is the one
constructor every measurement and every painter builds its font with (ADR-400),
and it asks for slight hinting: FreeType then hints only vertically and keeps the
face's own advances, and macOS draws exactly as at the default.

So three things are checked: no ``skia.Font(...)`` is built anywhere in
``src/md2ui`` or ``tests/`` but inside ``make_font`` (an AST walk, so a new call
site fails here, not on a Linux machine later -- a test's reference font must be
the font md2ui would build, or it compares against another one); the font it
builds is slightly hinted; and so an upright word is as wide as its slanted self
on any host, since FreeType never rounded the slanted one.

A gutter marker (an ordinal, a quote character) is sized and placed by its ink,
and the rasterized ink is rounded out to whole pixels differently by CoreText
and FreeType (a 48px ``10.`` was 2-4 px taller on macOS). So a marker's ink is
read from the glyph outlines, which agree across platforms: checked here as
unrounded and equal to the outlines' bounds.
"""

import ast
import unittest
from pathlib import Path

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.render_metrics import _outline_ink, _text_ink
from md2ui.session import repo_root
from md2ui.utils.font_loader import make_font, styled_font

# The one place a skia.Font may be constructed: (file under the repo, function).
_CONSTRUCTOR = ("src/md2ui/utils/font_loader.py", "make_font")


def bare_font_calls(root: Path, dirs: tuple[str, ...]) -> list[str]:
    """Every ``skia.Font(...)`` call under ``root/<dir>`` outside ``make_font``."""
    found = []
    paths = sorted(p for d in dirs for p in (root / d).rglob("*.py"))
    for path in paths:
        rel = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        allowed: set[int] = set()
        for node in ast.walk(tree):
            if (rel, getattr(node, "name", None)) == _CONSTRUCTOR:
                allowed |= {id(n) for n in ast.walk(node)}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "Font"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "skia"
                and id(node) not in allowed
            ):
                found.append(f"{rel}:{node.lineno}")
    return found


def _face(name: str) -> skia.Typeface:
    face = skia.Typeface.MakeFromFile(str(repo_root() / "assets" / "fonts" / name))
    assert face is not None, f"{name} is missing: run `make assets`"
    return face


def test_no_font_is_built_outside_make_font():
    calls = bare_font_calls(repo_root(), ("src/md2ui", "tests"))
    assert not calls, (
        "build fonts with md2ui.utils.font_loader.make_font, not skia.Font: "
        + ", ".join(calls)
    )


def test_make_font_is_slightly_hinted():
    face = _face("GoogleSans-Regular.ttf")
    tc = unittest.TestCase()
    tc.assertEqual(make_font(face, 20.0).getHinting(), skia.FontHinting.kSlight)
    tc.assertEqual(make_font(face, 20.0, 0.5).getScaleX(), 0.5)
    slanted = styled_font(face, 20.0, True)
    tc.assertNotEqual(slanted.getSkewX(), 0.0)
    tc.assertEqual(slanted.getHinting(), skia.FontHinting.kSlight)


def test_upright_text_is_as_wide_as_slanted():
    # The finding's string: 134.76 on macOS both ways; 138.0 upright at normal
    # hinting on Linux.
    face = _face("GoogleSans-Regular.ttf")
    upright = make_font(face, 20.0).measureText("Weighted label")
    slanted = styled_font(face, 20.0, True).measureText("Weighted label")
    unittest.TestCase().assertAlmostEqual(upright, slanted, places=3)


def test_a_marker_is_measured_by_its_outlines():
    font = make_font(_face("Inter_18pt-Regular.ttf"), 48.0)
    ink_top, ink_height, advance = _text_ink("10.", font)
    outline_advance, ink = _outline_ink("10.", font)
    tc = unittest.TestCase()
    tc.assertEqual(
        (ink_top, ink_height, advance), (-ink.top(), ink.height(), outline_advance)
    )
    # Rasterized ink is whole pixels on every platform; the outline's is not.
    tc.assertGreater(abs(ink_top - round(ink_top)), 1e-3)
    tc.assertGreater(abs(ink_height - round(ink_height)), 1e-3)


TESTS = [
    test_no_font_is_built_outside_make_font,
    test_make_font_is_slightly_hinted,
    test_upright_text_is_as_wide_as_slanted,
    test_a_marker_is_measured_by_its_outlines,
]
