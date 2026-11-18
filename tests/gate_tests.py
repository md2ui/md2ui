"""Tests for the gate itself — `scripts/check_conventions.py`, `run_tests.py` and
`check_skill_pointers.py`.

**Why this file exists.** These scripts decide whether everything else passes,
and nothing else checks them. A false positive is loud, while a false negative
silently deletes a rule: a check that never fires is indistinguishable from a
check that passes. So every check has a fixture that violates it and an
assertion that it is reported; if you add a check, add its violating fixture
here in the same change.

Run with: uv run python scripts/run_tests.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_conventions as cc  # noqa: E402
import check_skill_pointers as sp  # noqa: E402


# --- the coverage check: imports, not mentions -------------------------------


def test_coverage_ignores_a_mention_in_a_comment():
    """A comment is not a test."""
    text = "# this file talks about md2ui.pipeline.theme but never imports it\n"
    assert cc._is_imported_by_tests("md2ui.pipeline.theme", text) is False


def test_coverage_accepts_all_three_import_spellings():
    for text in (
        "from md2ui.pipeline.theme import Theme\n",
        "import md2ui.pipeline.theme\n",
        "from md2ui.pipeline import theme\n",
    ):
        assert cc._is_imported_by_tests("md2ui.pipeline.theme", text) is True, text


def test_coverage_accepts_a_function_local_import():
    """Local imports are still imports; the check must not be column-anchored."""
    text = "def t():\n    from md2ui.pipeline.theme import Theme\n"
    assert cc._is_imported_by_tests("md2ui.pipeline.theme", text) is True


def test_coverage_is_not_fooled_by_a_prefix():
    """`theme` must not be satisfied by an import of `theme_extras`."""
    text = "from md2ui.pipeline import theme_extras\n"
    assert cc._is_imported_by_tests("md2ui.pipeline.theme", text) is False


# --- checks that read the tree ----------------------------------------------


def _sandbox(fn):
    """Run *fn(root)* with the checker pointed at a throwaway tree."""
    saved = (cc.ROOT, cc.SRC, cc.TESTS, cc.AGENTS_MD, cc.DECISIONS, cc.BUDGETS)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "src" / "md2ui").mkdir(parents=True)
        (root / "tests").mkdir()
        (root / "decisions").mkdir()
        cc.ROOT, cc.SRC, cc.TESTS = root, root / "src", root / "tests"
        cc.AGENTS_MD, cc.DECISIONS = root / "AGENTS.md", root / "decisions"
        cc.BUDGETS = root / "budgets.txt"
        cc._repo_files.cache_clear()
        try:
            return fn(root)
        finally:
            (cc.ROOT, cc.SRC, cc.TESTS, cc.AGENTS_MD, cc.DECISIONS, cc.BUDGETS) = saved
            cc._repo_files.cache_clear()


def test_budget_fails_when_a_file_exceeds_the_default():
    def body(root):
        (root / "src" / "md2ui" / "big.py").write_text(
            "x = 1\n" * (cc.DEFAULT_BUDGET + 5)
        )
        errors: list[str] = []
        cc.check_file_budgets(errors, [])
        return errors

    errors = _sandbox(body)
    assert errors and "budget is" in errors[0]


def test_budget_reports_slack_as_a_note_not_an_error():
    """Shrinking must never fail the gate -- line counts move on every edit."""

    def body(root):
        (root / "src" / "md2ui" / "s.py").write_text("x = 1\n" * 10)
        (root / "budgets.txt").write_text("src/md2ui/s.py = 100\n")
        errors: list[str] = []
        warnings: list[str] = []
        cc.check_file_budgets(errors, warnings)
        return errors, warnings

    errors, warnings = _sandbox(body)
    assert errors == [] and warnings and "Lower it" in warnings[0]


def test_untested_module_is_reported():
    def body(root):
        (root / "src" / "md2ui" / "lonely.py").write_text("x = 1\n")
        (root / "tests" / "a_tests.py").write_text("# nothing imports it\n")
        errors: list[str] = []
        cc.check_untested_modules(errors)
        return errors

    errors = _sandbox(body)
    assert errors and "lonely" in errors[0]


def test_a_module_that_became_covered_must_leave_the_untested_list():
    """The other direction: UNTESTED.txt cannot rot either."""

    def body(root):
        (root / "src" / "md2ui" / "m.py").write_text("x = 1\n")
        (root / "tests" / "a_tests.py").write_text("from md2ui.m import x\n")
        (root / "tests" / "UNTESTED.txt").write_text("md2ui.m\n")
        errors: list[str] = []
        cc.check_untested_modules(errors)
        return errors

    errors = _sandbox(body)
    assert errors and "now covered" in errors[0]


def test_drift_catches_a_missing_bare_filename():
    """A bare filename, with no slash, is a path too."""

    def body(root):
        cc.AGENTS_MD.write_text("See `NOTES.md` for details.\n")
        errors: list[str] = []
        cc.check_agents_md_drift(errors)
        return errors

    errors = _sandbox(body)
    assert errors and "NOTES.md" in errors[0]


def test_drift_accepts_a_glob_that_matches():
    def body(root):
        (root / "tests" / "a_tests.py").write_text("")
        cc.AGENTS_MD.write_text("Tests live in `tests/*_tests.py`.\n")
        errors: list[str] = []
        cc.check_agents_md_drift(errors)
        return errors

    assert _sandbox(body) == []


def test_drift_catches_a_glob_that_matches_nothing():
    def body(root):
        cc.AGENTS_MD.write_text("Specs live in `tests/*_specs.py`.\n")
        errors: list[str] = []
        cc.check_agents_md_drift(errors)
        return errors

    errors = _sandbox(body)
    assert errors and "_specs.py" in errors[0]


def test_drift_ignores_a_command_that_contains_a_slash():
    def body(root):
        cc.AGENTS_MD.write_text("Run `uv run python scripts/nope.py` to do it.\n")
        errors: list[str] = []
        cc.check_agents_md_drift(errors)
        return errors

    assert _sandbox(body) == []


def test_adr_pointer_must_resolve():
    def body(root):
        (root / "src" / "md2ui" / "m.py").write_text("# see ADR-042\n")
        cc.AGENTS_MD.write_text("")
        errors: list[str] = []
        cc.check_decision_pointers(errors)
        return errors

    errors = _sandbox(body)
    assert errors and "ADR-042" in errors[0]


def test_adr_pointer_in_prose_must_resolve():
    """The check reads the repo's own Markdown, not just source."""

    def body(root):
        (root / "findings").mkdir()
        (root / "findings" / "f.md").write_text("as recorded in ADR-042\n")
        cc.AGENTS_MD.write_text("")
        errors: list[str] = []
        cc.check_decision_pointers(errors)
        return errors

    errors = _sandbox(body)
    assert errors and "ADR-042" in errors[0]


def test_adr_pointer_satisfied_when_the_record_exists():
    def body(root):
        (root / "src" / "md2ui" / "m.py").write_text("# see ADR-042\n")
        (root / "decisions" / "ADR-042-something.md").write_text("# ADR-042\n")
        cc.AGENTS_MD.write_text("")
        errors: list[str] = []
        cc.check_decision_pointers(errors)
        return errors

    assert _sandbox(body) == []


def test_nested_projects_do_not_satisfy_a_bare_filename():
    """A vendored project's copy of a file is not this project's copy, or
    deleting this repo's copy would still pass the drift check."""

    def body(root):
        (root / "vendored").mkdir()
        (root / "vendored" / "pyproject.toml").write_text("")
        (root / "vendored" / "ONLY_THERE.md").write_text("")
        cc.AGENTS_MD.write_text("See `ONLY_THERE.md`.\n")
        errors: list[str] = []
        cc.check_agents_md_drift(errors)
        return errors

    errors = _sandbox(body)
    assert errors and "ONLY_THERE.md" in errors[0]


# --- the import contracts themselves ---------------------------------------
#
# Not check_conventions, but the same failure mode and the same file's remit: a
# rule that reads strictly and enforces nothing.
#
# A BARE package name in `forbidden_modules` does not catch an import whose
# SOURCE module is itself inside that package. That is precisely the shape of
# this repo's "leaf" contracts -- a source in md2ui.pipeline forbidding
# md2ui.pipeline. The `.*` twin closes the gap, and costs nothing where the
# bare name already works.


def _forbidden_lists() -> list[tuple[str, list[str]]]:
    """``(contract name, forbidden_modules)`` from pyproject.toml."""
    import tomllib

    repo = Path(__file__).resolve().parent.parent
    data = tomllib.loads((repo / "pyproject.toml").read_text())
    out = []
    for c in data["tool"]["importlinter"]["contracts"]:
        if "forbidden_modules" in c:
            out.append((c["name"], c["forbidden_modules"]))
    return out


def test_every_forbidden_package_also_forbids_its_submodules():
    """A package named in forbidden_modules must have its `.*` twin.

    Without it the entry forbids only `import md2ui.pipeline` itself, which no
    module ever writes -- so the contract passes unconditionally.
    """
    packages = {
        "md2ui.pipeline",
        "md2ui.utils",
        "md2ui.app",
        "md2ui.main",
        "md2ui.session",
    }
    missing = []
    for name, mods in _forbidden_lists():
        for pkg in packages & set(mods):
            if f"{pkg}.*" not in mods:
                missing.append(f"{name}: {pkg} without {pkg}.*")
    assert not missing, "contracts that enforce nothing: " + "; ".join(missing)


def test_the_submodule_rule_would_catch_a_bare_package_entry():
    """The fixture: a bare package entry, asserted to be caught by the rule
    above rather than trusted."""
    packages = {
        "md2ui.pipeline",
        "md2ui.utils",
        "md2ui.app",
        "md2ui.main",
        "md2ui.session",
    }
    broken = [("a leaf that leaks", ["md2ui.pipeline", "md2ui.utils.*"])]
    missing = [
        f"{name}: {pkg}"
        for name, mods in broken
        for pkg in packages & set(mods)
        if f"{pkg}.*" not in mods
    ]
    assert missing == ["a leaf that leaks: md2ui.pipeline"]


# --- skill pointers: every form the notes name a topic in --------------------


def _named(text: str, source: str = "text.md") -> list[str]:
    return [topic for _, topic in sp.pointers(sp.SKILLS / source, text)]


def test_skill_pointer_forms_each_name_a_topic():
    assert _named("[a](elements.md#icon-buttons) and [b](colour.md)") == [
        "elements/icon-buttons",
        "colour",
    ]
    assert _named("[`elements/icon-buttons`](elements.md#icon-buttons)") == [
        "elements/icon-buttons",
        "elements/icon-buttons",
    ]
    assert _named('read `patterns/split`, or guide("pages/menu")') == [
        "patterns/split",
        "pages/menu",
    ]
    assert _named("([`structure.md`](structure.md), *Escape a separator*)") == [
        "structure",
        "structure/escape-a-separator",
    ]
    assert _named("`images.md`, *Image-as-background cards*", "patterns/x.md") == [
        "images/image-as-background-cards"
    ]
    assert _named("[d](../dashboards.md) → *The mosaic*", "patterns/x.md") == [
        "dashboards",
        "dashboards/the-mosaic",
    ]


def test_skill_pointer_ignores_what_names_no_topic():
    """A placeholder, a theme's own pattern, and a file outside the notes."""
    text = 'guide("<note>/<section>") `theme/menu` [c](../data/x/content.md)'
    assert _named(text) == []


TESTS = [
    test_coverage_ignores_a_mention_in_a_comment,
    test_coverage_accepts_all_three_import_spellings,
    test_coverage_accepts_a_function_local_import,
    test_coverage_is_not_fooled_by_a_prefix,
    test_budget_fails_when_a_file_exceeds_the_default,
    test_budget_reports_slack_as_a_note_not_an_error,
    test_untested_module_is_reported,
    test_a_module_that_became_covered_must_leave_the_untested_list,
    test_drift_catches_a_missing_bare_filename,
    test_drift_accepts_a_glob_that_matches,
    test_drift_catches_a_glob_that_matches_nothing,
    test_drift_ignores_a_command_that_contains_a_slash,
    test_adr_pointer_must_resolve,
    test_adr_pointer_in_prose_must_resolve,
    test_adr_pointer_satisfied_when_the_record_exists,
    test_nested_projects_do_not_satisfy_a_bare_filename,
    test_every_forbidden_package_also_forbids_its_submodules,
    test_the_submodule_rule_would_catch_a_bare_package_entry,
    test_skill_pointer_forms_each_name_a_topic,
    test_skill_pointer_ignores_what_names_no_topic,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
    print(f"All {len(TESTS)} tests passed.")
