"""
Unit tests for what the PyPI package holds (pyproject.toml's hatch build config).

A wheel holds ``src/md2ui`` plus the files md2ui reads at run time, copied into
``md2ui/shipped/`` laid out as in a checkout (``session.resource_root``). Nothing
fails at build time when one is left out: the installed package just cannot find
it. So:

  * every page ``skills/pages.md`` lists ships in ``skills/pages/``, or
    ``guide("pages/...")`` would name a page it cannot serve;
  * every file the runtime reads from the resource root is in the wheel;
  * the sdist holds everything the wheel is built from (``uv build`` builds the
    wheel from the sdist);
  * each console script names a function that exists.

Run with: uv run python tests/wheel_tests.py
"""

import importlib
import re
import tomllib

from md2ui import session

ROOT = session.repo_root()
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())
TARGETS = PYPROJECT["tool"]["hatch"]["build"]["targets"]
WHEEL = TARGETS["wheel"]
SDIST = TARGETS["sdist"]

# The files the runtime opens under ``session.resource_root()``, beside the
# ``skills/`` notes and patterns.
RUNTIME = [
    "THEME.md",
    "MEANINGS.md",
    "assets/fonts.lock",
    "assets/app/icon.png",
    "assets/demo/working.webp",
    "assets/icons/material-design-icons-md2ui.ttf",
    "data/images/image-placeholder.png",
    "data/images/image-broken-placeholder.png",
    "data/vectors/image-placeholder.svg",
    "skills/pages.md",
    "skills/patterns",
    "patterns",
]


def _in_wheel(path: str) -> bool:
    shipped = [*WHEEL["only-include"], *WHEEL.get("force-include", {})]
    return any(path == s or path.startswith(s + "/") for s in shipped)


def test_every_cited_page_is_in_the_wheel():
    index = (ROOT / "skills" / "pages.md").read_text()
    assert "data/" not in index, (
        "skills/pages.md points into data/, which does not ship"
    )
    names = re.findall(r"^\| [^|]+ \| `([^`]+)` \|", index.split("## Recipes")[0], re.M)
    assert names, "skills/pages.md lists no page"
    pages = [f"skills/pages/{name}.md" for name in names]
    missing = [p for p in pages if not (ROOT / p).is_file() or not _in_wheel(p)]
    assert not missing, f"listed by skills/pages.md, not in the wheel: {missing}"
    print(f"  ✓  all {len(pages)} pages skills/pages.md lists ship in skills/pages/")


def test_every_runtime_file_is_in_the_wheel():
    for path in RUNTIME:
        assert (ROOT / path).exists(), f"{path} is not in the checkout"
    missing = [p for p in RUNTIME if not _in_wheel(p)]
    assert not missing, f"read at run time, not in the wheel: {missing}"
    print("  ✓  every file the runtime reads is in the wheel")


def test_the_sdist_holds_what_the_wheel_is_built_from():
    sdist = set(SDIST["only-include"])
    wheel = {*WHEEL["only-include"], *WHEEL.get("force-include", {})}
    assert wheel <= sdist, f"in the wheel, not the sdist: {sorted(wheel - sdist)}"
    print("  ✓  the sdist holds everything the wheel is built from")


def test_every_console_script_names_a_function():
    scripts = PYPROJECT["project"]["scripts"]
    assert {"md2ui", "md2ui-app", "md2ui-mcp", "md2ui-mcp-demo"} <= set(scripts)
    for name, target in scripts.items():
        module, function = target.split(":")
        assert callable(getattr(importlib.import_module(module), function)), name
    print("  ✓  every console script names a function")


TESTS = [
    test_every_cited_page_is_in_the_wheel,
    test_every_runtime_file_is_in_the_wheel,
    test_the_sdist_holds_what_the_wheel_is_built_from,
    test_every_console_script_names_a_function,
]

if __name__ == "__main__":
    print("Wheel Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
