"""
Unit tests for ``Layout: Auto`` (``pipeline/layout_auto``): the engine picks bento
or stacking per document, by which leaves less of the page empty.

Pinned here:
  * ``Layout: Auto`` parses, beside ``Default`` and ``Bento``; anything else is
    ``Default``;
  * the width bands: under 768 narrow, then up to 1280, then wide;
  * under Auto, ``bento_requested`` is the session's choice for the width, and the
    window's override (``G``, ``--bento``) still wins;
  * a page of stat strips tiles in a wide window, and a forecast row that bento
    would spread into a sparse grid stays stacked;
  * a band is measured once per document: two builds on its first layout, one
    after, and one in a narrow window, which always stacks;
  * a document with nothing to tile is built once.

Run with: uv run python tests/layout_auto_tests.py
"""

import tempfile
from pathlib import Path

from md2ui import session
from md2ui.pipeline import layout_auto
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.theme import parse_theme

_THEME = Path("data/markdown/tests/THEME.md")
_STATS = Path("data/markdown/tests/auto-layout-stat-strips.md")
_FORECAST = Path("data/markdown/tests-render/weather/google/content.md")
_KIT: list = []


def _auto_theme():
    theme = session.load_theme(_THEME)
    theme.root.layout = "auto"
    return theme, session.load_fonts(theme)


def _laid_out(text: str, widths: list[float]) -> list[tuple[bool, int]]:
    """(tiles, builds) at each width in turn, for one document and one generator."""
    if not _KIT:
        _KIT.append(session.load_grouping_kit())
    theme, fonts = _auto_theme()
    ast = session.group_markdown(text, _KIT[0])
    assert ast is not None
    root, index = session.prepare(ast, theme)
    gen = LayoutGenerator()
    real, out = session._build_scene, []
    for width in widths:
        builds = [0]

        def counted(*args, **kwargs):
            builds[0] += 1
            return real(*args, **kwargs)

        session._build_scene = counted
        try:
            session.build_scene(gen, root, index, theme, fonts, width)
        finally:
            session._build_scene = real
        out.append((gen.bento_requested, builds[0]))
    return out


def test_auto_parses_beside_default_and_bento():
    for value, want in (("Auto", "auto"), ("Bento", "bento"), ("Mosaic", "default")):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write(f"# t\n## Styling & Spacing\n### Root\nLayout: {value}\n")
        try:
            assert parse_theme(Path(fh.name)).root.layout == want, value
        finally:
            Path(fh.name).unlink()
    print("  ✓  Layout: Auto parses; an unknown value is Default")


def test_the_width_bands():
    bands = [layout_auto.band(w) for w in (390, 767, 768, 1279, 1280, 1920)]
    assert bands == [0, 0, 1, 1, 2, 2], bands
    print("  ✓  bands: under 768, up to 1280, beyond")


def test_auto_follows_the_choice_and_the_override_wins():
    theme, _ = _auto_theme()
    gen = LayoutGenerator()
    gen._theme = theme
    assert not gen.bento_requested
    gen.bento_auto = True
    assert gen.bento_requested
    gen.bento_override = False
    assert not gen.bento_requested, "the window's G still forces a layout"
    print("  ✓  Auto reads the session's choice; an override wins")


def test_stat_strips_tile_and_a_forecast_row_stacks():
    assert _laid_out(_STATS.read_text(), [1280])[0][0], "stat strips tile"
    assert not _laid_out(_FORECAST.read_text(), [1280])[0][0], "the forecast stacks"
    print("  ✓  bento where it empties the page less, stacking where it would not")


def test_a_band_is_measured_once_and_narrow_never():
    got = _laid_out(_STATS.read_text(), [1280, 1440, 390, 600, 1300])
    assert got == [(True, 2), (True, 1), (False, 1), (False, 1), (True, 1)], got
    print("  ✓  two builds on a band's first layout, one after; narrow stacks")


def test_nothing_to_tile_builds_once():
    got = _laid_out("# Notes\n\nOne paragraph.\n", [1280])
    assert got == [(False, 1)], got
    print("  ✓  a document with no level to tile is built once")


TESTS = [
    test_auto_parses_beside_default_and_bento,
    test_the_width_bands,
    test_auto_follows_the_choice_and_the_override_wins,
    test_stat_strips_tile_and_a_forecast_row_stacks,
    test_a_band_is_measured_once_and_narrow_never,
    test_nothing_to_tile_builds_once,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
