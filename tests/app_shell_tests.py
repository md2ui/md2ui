"""
Unit tests for the shells' pure helpers (``md2ui.app``, ``md2ui.session``).

The app is a GLFW window, so almost all of it is only meaningfully exercised by
actually running it; the headless path it shares with the CLI is exercised by
the render snapshot through ``md2ui render``. What IS unit-testable is the
handful of pure helpers:

``repo_root`` walks up to a marker instead of indexing ``Path(__file__).parents``,
so moving the module cannot silently point asset paths at an empty directory
(the emoji typeface and image placeholders would fail to load without error).

``effective_width`` is the width a resize would build at; the
window rebuilds only when it moves. It measures the document's minimum once per
``(root, theme, fonts)`` by IDENTITY, so a new document or theme re-measures and
nothing is invalidated by hand, and every ask above ``Max width`` lands on the
same width — which is why a drag up there rebuilds nothing.

``_initial_window_size`` is the size the window opens at. Width is content-fit;
height is content-fit too but never less than width x 9/16, so a one-line
document does not open as a flat strip, and the screen caps both.

``fitted`` keeps the window's GL surface the framebuffer's size. The frame
checks the surface against the framebuffer itself, so a window moved to a
display of another scale draws at the right size whichever GLFW callback fires,
in whatever order.

Run with: uv run tests/app_shell_tests.py
"""

import os
from pathlib import Path
from typing import Any

from md2ui import session
from md2ui.app import _initial_window_size, _screenshot_path
from md2ui.app_surface import fitted
from md2ui.pipeline.theme import CONTENT_WIDTH_MAX, Theme
from md2ui.session import repo_root


def test_repo_root_is_the_directory_holding_pyproject():
    root = repo_root()
    assert (root / "pyproject.toml").exists()


def test_repo_root_finds_the_assets_the_shell_loads():
    """Both asset paths are resolved from the root, so if the
    root is wrong they resolve to somewhere plausible and empty — which is
    exactly why this asserts the FILES exist, not just the directory."""
    root = repo_root()
    assert (root / "assets" / "fonts" / "OpenMoji-black-glyf.ttf").exists(), (
        "emoji typeface"
    )
    assert (root / "data" / "images" / "image-placeholder.png").exists(), (
        "raster placeholder"
    )
    assert (root / "data" / "vectors" / "image-placeholder.svg").exists(), (
        "vector placeholder"
    )


def test_repo_root_does_not_depend_on_this_module_s_depth():
    """The point of walking up to a marker rather than indexing ``parents``:
    the answer must not be a fixed number of levels above ``session.py``."""
    here = Path(repo_root())
    module_dir = Path(__import__("md2ui.session", fromlist=["session"]).__file__).parent
    assert here in module_dir.parents or here == module_dir.parent


def test_screenshot_path_lands_in_the_screenshots_folder():
    # Captures go to the repo's git-ignored screenshots/,
    # never beside the document (a corpus folder).
    out = _screenshot_path(Path("data/markdown/tests-render/content.md"), 1280)
    assert Path(out).parent == session.repo_root() / "screenshots"
    assert os.path.basename(out).startswith("content-1280w-")
    assert out.endswith(".png")


def _opaque() -> Any:
    """A stand-in document root or font set: only its IDENTITY is ever read,
    because ``document_min_width`` is stubbed."""
    return object()


def _with_min_width(value: float, test) -> list:
    """Run *test* with ``document_min_width`` stubbed to *value*; the calls made."""
    calls: list = []
    real = session.document_min_width
    session.document_min_width = lambda root, theme, measure: calls.append(1) or value
    session._MIN_WIDTH_MEMO.clear()
    try:
        test()
    finally:
        session.document_min_width = real
        session._MIN_WIDTH_MEMO.clear()
    return calls


def test_effective_width_measures_the_minimum_once_per_document():
    root, theme, fonts = _opaque(), Theme(), _opaque()
    results: list = []

    def run():
        results.append(session.effective_width(root, theme, fonts, 500.0))
        results.append(session.effective_width(root, theme, fonts, 700.0))
        session.effective_width(_opaque(), theme, fonts, 700.0)  # a reloaded document
        session.effective_width(root, Theme(), fonts, 700.0)  # a reloaded theme

    calls = _with_min_width(900.0, run)
    assert results == [900.0, 900.0], "the document's minimum outranks the ask"
    assert len(calls) == 3, f"measured {len(calls)}x; once per document or theme"


def test_every_ask_above_max_width_builds_the_same_width():
    theme = Theme()
    cap = theme.root.max_width or CONTENT_WIDTH_MAX
    root, fonts = _opaque(), _opaque()
    widths: list = []

    def run():
        widths.extend(
            session.effective_width(root, theme, fonts, w)
            for w in (cap + 1, cap + 300, cap * 3)
        )

    _with_min_width(0.0, run)
    assert widths == [cap] * 3, f"asks above Max width built {widths}"


def test_a_short_document_opens_at_16_9():
    assert _initial_window_size(1024, 120, 1840, 1000) == (1024, 576)


def test_a_tall_document_keeps_its_own_height():
    assert _initial_window_size(800, 700, 1840, 1000) == (800, 700)


def test_the_screen_caps_the_width_and_the_floor_follows_it():
    # 3000 wide caps to 1600, so the floor is 900, not 1688.
    assert _initial_window_size(3000, 100, 1600, 1000) == (1600, 900)


def test_the_screen_caps_the_height_over_the_floor():
    assert _initial_window_size(1600, 100, 1600, 700) == (1600, 700)
    assert _initial_window_size(800, 5000, 1840, 1000) == (800, 1000)


class _Surface:
    """A stand-in GL surface: only its size is read."""

    def __init__(self, w: int, h: int) -> None:
        self.w, self.h = w, h

    def width(self) -> int:
        return self.w

    def height(self) -> int:
        return self.h


def test_a_surface_the_framebuffer_size_is_kept():
    surface = _Surface(2400, 1600)
    made: list = []
    kept = fitted(
        surface, 2400, 1600, lambda w, h: made.append((w, h)) or _Surface(w, h)
    )
    assert kept is surface and made == [], "a matching surface is not rebuilt"


def test_a_display_change_rebuilds_the_surface_at_the_new_size():
    # Retina to 1x and back: the same 1200x800 window's framebuffer halves, then doubles.
    for old, new in (((2400, 1600), (1200, 800)), ((1200, 800), (2400, 1600))):
        made = fitted(_Surface(*old), *new, lambda w, h: _Surface(w, h))
        assert (made.width(), made.height()) == new, f"{old} -> {new}"


TESTS = [
    test_repo_root_is_the_directory_holding_pyproject,
    test_repo_root_finds_the_assets_the_shell_loads,
    test_repo_root_does_not_depend_on_this_module_s_depth,
    test_screenshot_path_lands_in_the_screenshots_folder,
    test_effective_width_measures_the_minimum_once_per_document,
    test_every_ask_above_max_width_builds_the_same_width,
    test_a_short_document_opens_at_16_9,
    test_a_tall_document_keeps_its_own_height,
    test_the_screen_caps_the_width_and_the_floor_follows_it,
    test_the_screen_caps_the_height_over_the_floor,
    test_a_surface_the_framebuffer_size_is_kept,
    test_a_display_change_rebuilds_the_surface_at_the_new_size,
]

if __name__ == "__main__":
    print("App Shell Tests")
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
