"""Tests for `scripts/extract_module.py`, which moves code out of a big file.

**Why this file exists.** Each mistake below is easy to reintroduce and shows
only when the moved code runs, so every check in the tool has a fixture here
that violates it:

  * a `cls` written on the line BELOW the `def` — a surviving first parameter
    shifts every caller's arguments by one;
  * an aliased import, whose `as` a naive resolver drops, producing an import of
    a name that does not exist;
  * a call whose arguments contain nested parentheses, which a text search for
    call sites misses after a parameter is added.

Run with: uv run python scripts/run_tests.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import extract_module as em  # noqa: E402


# --- the first-parameter bug, in all three spellings it occurs in -----------

_ONE_LINE = """class G:
    @classmethod
    def f(cls, content: str) -> str:
        return cls._x(content)
"""

_NEXT_LINE = """class G:
    @staticmethod
    def f(
        self, node: str, classifier
    ) -> None:
        return None
"""

_OWN_LINE = """class G:
    @classmethod
    def f(
        cls,
        content: str,
        protected: list | None = None,
    ):
        return cls._y(content)
"""

_SOLE_PARAM = """class G:
    @classmethod
    def f(cls):
        return 1
"""


def _first_param(src: str) -> str | None:
    import ast

    fn = next(n for n in ast.parse(src).body if isinstance(n, (ast.FunctionDef,)))
    return fn.args.args[0].arg if fn.args.args else None


def test_first_param_on_the_def_line_is_dropped():
    out = em.extract(_ONE_LINE, ["f"], cls="G")
    assert _first_param(out) == "content"


def test_first_param_on_the_line_below_is_dropped():
    """`def f(\\n    self, node, clf\\n)`."""
    out = em.extract(_NEXT_LINE, ["f"], cls="G")
    assert _first_param(out) == "node"


def test_first_param_alone_on_its_own_line_is_dropped():
    out = em.extract(_OWN_LINE, ["f"], cls="G")
    assert _first_param(out) == "content"


def test_a_sole_first_param_leaves_an_empty_signature():
    out = em.extract(_SOLE_PARAM, ["f"], cls="G")
    assert _first_param(out) is None
    assert "def f()" in out


def test_prefixes_are_rewritten_in_the_moved_code():
    """Rewriting only the file left behind would leave the extraction naming a
    class it no longer has."""
    out = em.extract(_ONE_LINE, ["f"], cls="G")
    assert "cls." not in out and "G." not in out
    assert "return _x(content)" in out


# --- decorators, comments, and overlap -------------------------------------


def test_a_decorated_definition_takes_its_decorator_with_it():
    """`ast` reports a decorated node at its `def`, so a naive span leaves the
    decorator behind and it lands on the NEXT definition."""
    src = """import dataclasses


@dataclasses.dataclass
class Box:
    x: int
"""
    out = em.extract(src, ["Box"])
    assert out.startswith("@dataclasses.dataclass")


def test_a_constant_takes_the_comment_block_above_it():
    src = """# Why this constant exists,
# over two lines.
NAME = 1
"""
    out = em.extract(src, ["NAME"])
    assert out.count("#") == 2 and "NAME = 1" in out


def test_a_missing_name_is_an_error_not_a_silent_skip():
    try:
        em.extract("X = 1\n", ["Y"])
    except SystemExit:
        return
    raise AssertionError("extracting a name that does not exist must fail")


# --- the aliased-import bug ------------------------------------------------


def test_an_aliased_import_is_reported():
    """`from x import A as _B` recorded as "_B comes from x" emits
    `from x import _B`, which does not exist. Only running it finds that."""
    src = "from md2ui.pipeline.theme import Theme as _BASE_THEME\n"
    assert em.aliased_imports(src) == [("_BASE_THEME", "Theme", "md2ui.pipeline.theme")]


def test_an_unaliased_import_is_not_reported():
    assert em.aliased_imports("from x import y\nimport z\n") == []


def test_the_exact_import_statement_is_reported_not_inferred():
    """`from datetime import
    datetime` re-inferred as `import datetime` binds a name that IS defined and
    is the wrong object, so every linter stays clean and it fails at runtime."""
    stmts = em.import_statements("from datetime import datetime\n")
    assert stmts["datetime"] == "from datetime import datetime"


def test_a_plain_module_import_is_reported_as_such():
    stmts = em.import_statements("import datetime\n")
    assert stmts["datetime"] == "import datetime"


def test_the_two_datetime_shapes_are_distinguishable():
    """Both bind the name `datetime`; only the statement tells them apart."""
    a = em.import_statements("import datetime\n")["datetime"]
    b = em.import_statements("from datetime import datetime\n")["datetime"]
    assert a != b


def test_an_alias_is_carried_into_the_statement():
    stmts = em.import_statements("from x.y import A as _B\n")
    assert stmts["_B"] == "from x.y import A as _B"


def test_a_dotted_import_binds_its_root_name():
    stmts = em.import_statements("import os.path\n")
    assert stmts["os"] == "import os.path"


# --- the arity bug ---------------------------------------------------------


def _tmp(src: str) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
    f.write(src)
    f.close()
    return f.name


def test_a_call_with_nested_parens_is_still_counted():
    """The exact shape a text search misses:
    `f(seg, _protected(seg), clf)` reads as one call with parentheses in it."""
    path = _tmp("f(seg, _protected(seg), clf)\n")
    problems = em.check_arity([path], {"f": 4})
    assert len(problems) == 1 and "needs 4" in problems[0]


def test_a_correct_call_is_not_reported():
    path = _tmp("f(seg, _protected(seg), clf, ids)\n")
    assert em.check_arity([path], {"f": 4}) == []


def test_keyword_arguments_count():
    path = _tmp("f(a, b, c, ids=mint)\n")
    assert em.check_arity([path], {"f": 4}) == []


def test_calls_to_other_names_are_ignored():
    path = _tmp("other(1)\n")
    assert em.check_arity([path], {"f": 4}) == []


# --- module state ----------------------------------------------------------


def test_a_global_write_is_reported_with_its_writer():
    """Cross-module mutable state cannot survive a split, and no linter
    reports it — ruff reads `global`-then-assign as 'imported but unused'."""
    src = """FLAG = False


def setter():
    global FLAG
    FLAG = True
"""
    assert em.module_state(src) == {"FLAG": ["setter"]}


def test_a_module_with_no_global_writes_is_clean():
    assert em.module_state("X = 1\n\n\ndef f():\n    return X\n") == {}


TESTS = [
    test_first_param_on_the_def_line_is_dropped,
    test_first_param_on_the_line_below_is_dropped,
    test_first_param_alone_on_its_own_line_is_dropped,
    test_a_sole_first_param_leaves_an_empty_signature,
    test_prefixes_are_rewritten_in_the_moved_code,
    test_a_decorated_definition_takes_its_decorator_with_it,
    test_a_constant_takes_the_comment_block_above_it,
    test_a_missing_name_is_an_error_not_a_silent_skip,
    test_an_aliased_import_is_reported,
    test_an_unaliased_import_is_not_reported,
    test_the_exact_import_statement_is_reported_not_inferred,
    test_a_plain_module_import_is_reported_as_such,
    test_the_two_datetime_shapes_are_distinguishable,
    test_an_alias_is_carried_into_the_statement,
    test_a_dotted_import_binds_its_root_name,
    test_a_call_with_nested_parens_is_still_counted,
    test_a_correct_call_is_not_reported,
    test_keyword_arguments_count,
    test_calls_to_other_names_are_ignored,
    test_a_global_write_is_reported_with_its_writer,
    test_a_module_with_no_global_writes_is_clean,
]

if __name__ == "__main__":
    print("Extract Module Tests")
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
