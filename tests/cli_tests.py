"""
Tests for the LLM CLI (``md2ui.main``): four verbs, each runs once and exits.

The guarantees pinned here are the ones that make the CLI usable by an agent,
unattended:

* every verb takes the Markdown and returns an exit status — no watcher, no
  prompt, no window;
* ``group`` writes exactly the grouper's tree (the snapshot corpus's format);
* ``check`` prints the MCP ``check`` tool's issues and exits 1 on an error;
  with only ``--theme`` it prints the theme lint and exits 0;
* importing the CLI never imports ``glfw``, so it runs where no display does;
* a page whose bitmap is too big to allocate is refused with its pixel size,
  printed as one line and exit 1, never a traceback.

The rendered pixels themselves are the render snapshot's job
(``scripts/render_snapshot.py`` drives ``md2ui render``), not this module's.

Run with: uv run tests/cli_tests.py
"""

import contextlib
import dataclasses
import io
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

from md2ui import session
from md2ui.main import main
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.utils.image_cache import ImageCache

_DOC = "# Title\n\nA short paragraph.\n\n- one\n- two\n"


def _doc(tmp: str, text: str = _DOC) -> Path:
    md = Path(tmp) / "content.md"
    md.write_text(text)
    return md


def test_group_writes_the_grouper_s_tree_beside_the_document():
    with tempfile.TemporaryDirectory() as tmp:
        md = _doc(tmp)
        assert main(["group", str(md)]) == 0
        written = json.loads((md.parent / "grouping-ast.json").read_text())
        ast = session.group_markdown(_DOC, session.load_grouping_kit())
        assert ast is not None
        assert written == json.loads(json.dumps(ast.to_dict()))


def test_an_empty_document_groups_to_the_empty_root_and_renders():
    """As both snapshot oracles do — the corpus holds two empty files, and a
    CLI that refused them would disagree with the oracles about them."""
    with tempfile.TemporaryDirectory() as tmp:
        md = _doc(tmp, "")
        assert main(["group", str(md)]) == 0
        root = json.loads((md.parent / "grouping-ast.json").read_text())
        assert root["type"] == "root" and root["children"] == []
        out = Path(tmp) / "empty.png"
        assert main(["render", str(md), "--out", str(out)]) == 0
        assert out.exists()


def test_layout_writes_the_layout_dump():
    with tempfile.TemporaryDirectory() as tmp:
        md = _doc(tmp)
        out = Path(tmp) / "layout.json"
        assert main(["layout", str(md), "--width", "800", "--out", str(out)]) == 0
        dump = json.loads(out.read_text())
        assert isinstance(dump, dict) and dump


def test_render_writes_a_png_and_returns():
    with tempfile.TemporaryDirectory() as tmp:
        md = _doc(tmp)
        out = Path(tmp) / "out.png"
        assert main(["render", str(md), "--width", "600", "--out", str(out)]) == 0
        assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def _run(argv: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(argv)
    return code, out.getvalue()


def test_check_prints_a_document_s_issues_and_fails_on_an_error():
    with tempfile.TemporaryDirectory() as tmp:
        md = _doc(tmp, "## A\n\n[Go](#nowhere)\n\n`26` ___`27`___\n")
        code, out = _run(["check", str(md)])
        assert code == 1, out
        lines = out.splitlines()
        assert any(line.startswith("error anchor-missing: ") for line in lines), out
        assert any(line.startswith("warning undeclared-spelling: ") for line in lines)
        code, out = _run(["check", str(_doc(tmp))])
        assert code == 0 and "no issues" in out, out


def test_check_with_only_a_theme_prints_its_lint():
    with tempfile.TemporaryDirectory() as tmp:
        theme = Path(tmp) / "THEME.md"
        theme.write_text("## Fixed colors\n### Emoji\n- 🦄 #9170D6\n")
        # A theme's pins are linted against its meanings: it keeps the defaults.
        (Path(tmp) / "MEANINGS.md").write_text("Extends: defaults\n")
        code, out = _run(["check", "--theme", str(theme)])
        assert code == 0, out
        lines = out.splitlines()
        assert lines and all(line.startswith("[theme] ") for line in lines), out
        assert any("The `🦄` pin under `## Fixed colors" in line for line in lines)


@contextlib.contextmanager
def _pages_of(width: float, height: float):
    """Every scene the CLI builds comes out *width* × *height*: a page too big
    to paint, without laying out one that size."""
    build = session.build_scene

    def huge(*args, **kwargs):
        return dataclasses.replace(build(*args, **kwargs), width=width, height=height)

    session.build_scene = huge
    try:
        yield
    finally:
        session.build_scene = build


def test_a_page_past_the_bitmap_limit_is_refused_with_its_size():
    """Refused before skia is asked, so nothing that size is allocated."""
    theme = session.load_theme(None)
    fonts = session.load_fonts(theme)
    ast = session.group_markdown(_DOC, session.load_grouping_kit())
    assert ast is not None
    root, index = session.prepare(ast, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 600)
    scene = dataclasses.replace(scene, width=20_000, height=30_000)
    try:
        session.render_image(scene, index, theme, fonts, ImageCache(), {}, 1)
    except session.PageTooLarge as exc:
        message = str(exc)
    else:
        raise AssertionError("a 2.2 GiB bitmap was not refused")
    pad = theme.root.padding
    size = f"{math.ceil(20_000 + pad.x):,} × {math.ceil(30_000 + pad.y):,} px"
    assert size in message and "2 GiB" in message, message


def test_render_prints_the_refusal_and_exits_1():
    with tempfile.TemporaryDirectory() as tmp:
        md = _doc(tmp)
        out = Path(tmp) / "out.png"
        err = io.StringIO()
        with _pages_of(20_000, 30_000), contextlib.redirect_stderr(err):
            code, _ = _run(["render", str(md), "--out", str(out)])
        assert code == 1 and not out.exists()
        assert err.getvalue().startswith("[render] ") and "2 GiB" in err.getvalue()
        assert "Traceback" not in err.getvalue(), err.getvalue()


def test_the_cli_never_imports_the_window_library():
    """In a fresh interpreter: this process may already hold glfw from the app
    shell's tests."""
    probe = "import sys, md2ui.main; print('glfw' in sys.modules)"
    proc = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert proc.stdout.strip() == "False", proc.stdout + proc.stderr


TESTS = [
    test_group_writes_the_grouper_s_tree_beside_the_document,
    test_an_empty_document_groups_to_the_empty_root_and_renders,
    test_layout_writes_the_layout_dump,
    test_render_writes_a_png_and_returns,
    test_check_prints_a_document_s_issues_and_fails_on_an_error,
    test_check_with_only_a_theme_prints_its_lint,
    test_a_page_past_the_bitmap_limit_is_refused_with_its_size,
    test_render_prints_the_refusal_and_exits_1,
    test_the_cli_never_imports_the_window_library,
]

if __name__ == "__main__":
    print("CLI Tests")
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
