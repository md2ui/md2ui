"""
Unit tests for the content patterns in ``skills/patterns/``: short section
shapes an agent reads one at a time, through ``guide('patterns/<name>')``.

A pattern is a claim about what a construct renders as, so it must not go stale
silently. Pinned here:

  * every pattern has ``name`` and ``description`` frontmatter, its name is its
    file name, and it stays within its budget (1,600 bytes, about 400 tokens);
  * its snippet, the one ```markdown fence, raises no authoring issue from
    ``check`` against the root contract an agent meets, with only the
    spellings that pattern declares itself: a pattern must not teach something
    the check would flag, and gives a spelling a meaning in its own shape only
    (ADR-501);
  * both of its validated renders, at 767 and 420, are in
    ``skills/renders/patterns/``.

Run with: uv run python tests/skills_patterns_tests.py
"""

import contextlib
import io
import re
from pathlib import Path

from md2ui import meanings, session
from md2ui.check import check_markdown

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = ROOT / "skills" / "patterns"
RENDERS = ROOT / "skills" / "renders" / "patterns"
MAX_BYTES = 1600
FENCE = re.compile(r"^```markdown\n(.*?)^```$", re.DOTALL | re.MULTILINE)


def _patterns() -> list[Path]:
    return sorted(PATTERNS.glob("*.md"))


def _field(text: str, name: str) -> str:
    found = re.search(rf"^{name}:\s*(.+)$", text, re.MULTILINE)
    return found.group(1).strip() if found else ""


def test_every_pattern_is_well_formed():
    for path in _patterns():
        text = path.read_text()
        assert text.startswith("---\n"), f"{path.name}: no frontmatter"
        assert _field(text, "name") == path.stem, path.name
        assert _field(text, "description"), f"{path.name}: no description"
        size = len(text.encode())
        assert size <= MAX_BYTES, f"{path.name}: {size} bytes, budget {MAX_BYTES}"
        assert len(FENCE.findall(text)) == 1, f"{path.name}: not one snippet"
    print(f"  ✓  {len(_patterns())} patterns: frontmatter, one snippet, in budget")


def test_every_snippet_is_clean():
    with contextlib.redirect_stdout(io.StringIO()):
        kit = session.load_grouping_kit()
        # The default theme's contract: the patterns are written in its spellings.
        contract = meanings.load_contract(session.repo_root() / "THEME.md")
        assert contract is not None, "no root MEANINGS.md"
        found = {
            path.stem: check_markdown(
                FENCE.findall(path.read_text())[0],
                kit,
                meanings.with_patterns(contract, [path]),
            )
            for path in _patterns()
        }
    dirty = {name: issues for name, issues in found.items() if issues}
    assert not dirty, dirty
    print(f"  ✓  {len(found)} snippets raise no authoring issue")


def test_every_pattern_has_both_renders():
    missing = [
        f"{path.stem}-{width}.png"
        for path in _patterns()
        for width in (767, 420)
        if not (RENDERS / f"{path.stem}-{width}.png").is_file()
    ]
    assert not missing, missing
    print("  ✓  every pattern's render is saved at 767 and 420")


TESTS = [
    test_every_pattern_is_well_formed,
    test_every_snippet_is_clean,
    test_every_pattern_has_both_renders,
]

if __name__ == "__main__":
    print("Skills Patterns Tests")
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
