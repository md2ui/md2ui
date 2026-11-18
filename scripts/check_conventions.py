#!/usr/bin/env python3
"""Mechanical checks for the conventions in AGENTS.md.

A rule that is not enforced decays, so every convention the project claims should
be checkable here. To change a convention, change it here first.

The device it leans on is the **ratchet**. Several tools report long-standing
problems (unformatted files, lint errors, type errors). Fixing them all at once
would bury real work in an unreviewable diff; leaving them unchecked lets them
grow. So the current counts are recorded as ceilings in ``ratchets.txt``:

  * exceeding a ceiling fails the gate -- the decay is stopped at the moment it
    happens, in the session that caused it;
  * beating a ceiling ALSO fails, asking you to lower it -- so progress is
    locked in and the ceiling can only travel one way.

This is the same contract as ``tests/BASELINE.txt``, applied to counts instead of
named tests.

``budgets.txt`` applies the same idea to file size -- but the line count is a
PROXY, never the point. What it is really watching for is code concentrating in
one file for no reason. A file that is genuinely one concept may exceed it; the
check exists to make that a stated decision rather than a drift. Splitting a
coherent file to satisfy a number erodes the code to protect the metric, which is
the failure this is meant to prevent.

A file may shrink freely (line counts move on every edit, so failing on an improvement
would make the gate unusable). Exceeding a budget fails; dropping well under one
is reported as an invitation to lower it.

Run via ``make check``, or directly:  uv run python scripts/check_conventions.py
"""

from __future__ import annotations

import argparse
import ast
import functools
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RATCHETS = ROOT / "ratchets.txt"
BUDGETS = ROOT / "budgets.txt"
AGENTS_MD = ROOT / "AGENTS.md"
DECISIONS = ROOT / "decisions"
SRC = ROOT / "src"
TESTS = ROOT / "tests"
TEST_THEME = ROOT / "data" / "markdown" / "tests" / "THEME.md"

DEFAULT_BUDGET = 500
BUDGET_SLACK = 0.10  # report when a file sits this far under its ceiling
MAX_DIRS_TOUCHED = 4  # advisory: scattered changes correlate with failure

BACKTICKED = re.compile(r"`([^`\n]+)`")
ADR_REF = re.compile(r"\bADR-(\d{3})\b")
PATH_SUFFIXES = (".md", ".py", ".txt", ".json", ".yaml", ".yml", ".toml", ".png")

# Seam guidance, so a budget failure gives direction instead of just refusal.
SEAMS = {
    "src/md2ui/pipeline/layout_render.py": (
        "colour resolution / section backgrounds / text+inline spans / "
        "measurement / painting"
    ),
    "src/md2ui/pipeline/markdown_grouper.py": (
        "block AST / splitters / fingerprints / annotation phases"
    ),
}

TARGETS = ("src", "tests", "scripts")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, check=False)


def count_ruff_errors() -> int:
    """Lint violations. `ruff check --output-format=json` is stable to parse."""
    proc = _run(["uv", "run", "ruff", "check", "--output-format=json", *TARGETS])
    try:
        return len(json.loads(proc.stdout or "[]"))
    except json.JSONDecodeError:
        print(proc.stdout[-2000:], file=sys.stderr)
        raise SystemExit("check_conventions: could not parse ruff output")


def count_ruff_unformatted() -> int:
    """Files `ruff format` would rewrite. Drops to 0 when the repo is formatted."""
    proc = _run(["uv", "run", "ruff", "format", "--check", *TARGETS])
    return sum(
        1 for line in proc.stdout.splitlines() if line.startswith("Would reformat:")
    )


def count_pyright_errors() -> int:
    proc = _run(["uv", "run", "pyright", "--outputjson"])
    try:
        report = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        print(proc.stdout[-2000:], file=sys.stderr)
        raise SystemExit("check_conventions: could not parse pyright output")
    return int(report.get("summary", {}).get("errorCount", 0))


@functools.cache
def _repo_files() -> dict[str, list[Path]]:
    """Filename -> paths, for resolving bare filenames. Skips vendored trees."""
    skip = {".venv", "__pycache__", ".git", "node_modules"}
    # A NESTED PROJECT is not this project. Any directory with its own
    # pyproject.toml (a vendored template, an example app) is excluded, so a bare
    # filename cannot be satisfied by someone else's copy of it. A list of named
    # directories would go stale the moment one was renamed; this rule cannot.
    nested = {
        q.parent
        for q in ROOT.rglob("pyproject.toml")
        if q.parent != ROOT and not skip & set(q.parts)
    }
    index: dict[str, list[Path]] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file() or skip & set(path.parts):
            continue
        if any(n in path.parents for n in nested):
            continue
        index.setdefault(path.name, []).append(path)
    return index


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def src_modules() -> list[Path]:
    return sorted(
        p
        for p in SRC.rglob("*.py")
        if p.name != "__init__.py" and "__pycache__" not in p.parts
    )


def check_file_budgets(errors: list[str], warnings: list[str]) -> None:
    """Big files make edits unreliable and force whole-file reads. Cap them.

    Pre-existing large files carry their current size as a ceiling; everything
    else gets DEFAULT_BUDGET. A ceiling may only be lowered.
    """
    budgets = load_pairs(BUDGETS)
    for path in sorted(SRC.rglob("*.py")) + sorted((ROOT / "scripts").glob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = _rel(path)
        lines = len(path.read_text().splitlines())
        ceiling = budgets.get(rel, DEFAULT_BUDGET)
        if lines > ceiling:
            hint = SEAMS.get(rel)
            hint = f" Seams: {hint}." if hint else ""
            errors.append(
                f"{rel}: {lines} lines, budget is {ceiling}. This is a prompt, "
                f"not a verdict: split it if it holds more than one concept, or "
                f"raise the number here with a reason if it does not.{hint}"
            )
        elif rel in budgets and lines < ceiling * (1 - BUDGET_SLACK):
            warnings.append(
                f"{rel}: {lines} lines, budget still {ceiling}. Lower it in "
                "budgets.txt to lock the improvement in."
            )
    for rel in sorted(set(budgets) - {_rel(p) for p in ROOT.rglob("*.py")}):
        errors.append(f"budgets.txt names {rel}, which is not on disk. Remove it.")


def check_untested_modules(errors: list[str]) -> None:
    """The set of modules no test mentions may not grow."""
    accepted = {line for line in load_list(TESTS / "UNTESTED.txt")}
    test_text = "\n".join(p.read_text() for p in TESTS.glob("*_tests.py"))
    untested = set()
    for path in src_modules():
        module = ".".join(path.relative_to(SRC).with_suffix("").parts)
        if not _is_imported_by_tests(module, test_text):
            untested.add(module)

    for module in sorted(untested - accepted):
        errors.append(
            f"{module}: no test module mentions it, and it is not in "
            "tests/UNTESTED.txt. Add a test, or accept it deliberately."
        )
    for module in sorted(accepted - untested):
        errors.append(
            f"{module}: now covered by tests. Delete it from tests/UNTESTED.txt."
        )


def check_test_theme_isolation(errors: list[str]) -> None:
    """Tests use their stable fixture, never the hand-edited root default."""
    if not TEST_THEME.is_file():
        errors.append(f"missing test theme: {_rel(TEST_THEME)}")
        return
    for path in TESTS.glob("*_tests.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            direct = (
                isinstance(node, ast.Call)
                and bool(node.args)
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "THEME.md"
            )
            root_default = (
                path.name != "packaging_tests.py"
                and isinstance(node, ast.BinOp)
                and isinstance(node.op, ast.Div)
                and isinstance(node.left, ast.Name)
                and node.left.id == "ROOT"
                and isinstance(node.right, ast.Constant)
                and node.right.value == "THEME.md"
            )
            if direct or root_default:
                errors.append(
                    f"{_rel(path)}:{getattr(node, 'lineno', 0)}: tests use "
                    f"data/markdown/tests/THEME.md, not the root default"
                )


def _is_imported_by_tests(module: str, test_text: str) -> bool:
    """True only if a test actually IMPORTS *module*.

    A substring search ("does this name appear anywhere") is far too loose: a
    module named once in a comment or a docstring then reads as covered, which
    turns a coverage check into decoration. Match real import statements
    instead, in all three spellings:

        from pkg.mod import x
        import pkg.mod
        from pkg import mod

    Function-local imports count, so this is deliberately not column-anchored.
    """
    parent, _, leaf = module.rpartition(".")
    patterns = [
        rf"^\s*from\s+{re.escape(module)}\b",
        rf"^\s*import\s+{re.escape(module)}\b",
    ]
    if parent:
        patterns.append(
            rf"^\s*from\s+{re.escape(parent)}\s+import\s+[^\n]*\b{re.escape(leaf)}\b"
        )
    return any(re.search(p, test_text, re.MULTILINE) for p in patterns)


def check_agents_md_drift(errors: list[str]) -> None:
    """Anything AGENTS.md names in backticks must still resolve.

    A token is a path if it contains '/' or ends in a known file extension --
    the routing table is mostly bare filenames (``THEME_GUIDE.md``), and those
    are exactly the references worth protecting. ``*`` is a glob and ``<name>``
    a placeholder: AGENTS.md legitimately writes ``tests/*_tests.py``, which is
    the clearest way to state the convention. Command lines contain slashes but
    are not paths.

    Scoped to AGENTS.md on purpose, and NOT extended over ``decisions/``: every
    hit there is a false positive. An ADR is narrative and legitimately names
    things that do not exist -- rejected ideas, naming patterns, paths that once
    did. AGENTS.md is a routing table, where every path must resolve.
    """
    if not AGENTS_MD.exists():
        errors.append("AGENTS.md: missing")
        return
    seen: set[str] = set()
    for token in BACKTICKED.findall(AGENTS_MD.read_text()):
        token = token.strip()
        if token in seen:
            continue
        seen.add(token)
        if token.startswith(("http", "-", "$")):
            continue
        token = token.split()[0]
        if token.startswith(("uv", "make", "python")):
            continue
        if "/" not in token and not token.endswith(PATH_SUFFIXES):
            continue
        raw = re.sub(r"<[^>]+>", "*", token)
        pattern = raw.rstrip("/")
        if "*" in pattern:
            found = bool(list(ROOT.glob(pattern)))
        elif (ROOT / pattern).exists():
            found = True
        elif "/" in raw:
            found = False
        else:
            # A bare filename: the routing table names modules without their
            # directory, which reads better. Resolve it anywhere in the repo --
            # that still catches the case this check exists for, a rename or a
            # deletion leaving AGENTS.md pointing at nothing.
            found = any(_repo_files().get(pattern, ()))
        if not found:
            errors.append(f"AGENTS.md refers to `{token}`, which is not on disk.")


def check_decision_pointers(errors: list[str]) -> None:
    """Every ADR-nnn mentioned in code or prose must resolve to a record.

    Scope is source, scripts and the repo's own Markdown. Two exclusions, both
    on principle rather than convenience:

    * ``tests/`` — a test legitimately contains deliberately invalid input, and
      ``gate_tests.py`` names a nonexistent ADR on purpose to prove this check
      fires. Scanning tests would make the gate fail on its own fixture.
    * ``data/`` — corpora, not repository prose.
    """
    docs = (
        [q for q in ROOT.glob("*.md") if q.name != "AGENTS.md"]
        + sorted(DECISIONS.glob("*.md"))
        + sorted((ROOT / "findings").glob("*.md"))
    )
    for path in (
        list(SRC.rglob("*.py"))
        + sorted((ROOT / "scripts").glob("*.py"))
        + [AGENTS_MD]
        + docs
    ):
        if "__pycache__" in path.parts or not path.exists():
            continue
        for number in sorted(set(ADR_REF.findall(path.read_text()))):
            if not list(DECISIONS.glob(f"ADR-{number}-*.md")):
                errors.append(
                    f"{_rel(path)}: refers to ADR-{number}, which does not exist."
                )


def load_pairs(path: Path) -> dict[str, int]:
    """`key = int` lines, `#` comments allowed."""
    if not path.exists():
        return {}
    out: dict[str, int] = {}
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = int(value.strip())
    return out


def load_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line
        for raw in path.read_text().splitlines()
        if (line := raw.split("#", 1)[0].strip())
    ]


CHECKS = {
    "ruff_errors": count_ruff_errors,
    "ruff_unformatted_files": count_ruff_unformatted,
    "pyright_errors": count_pyright_errors,
}

HEADER = """\
# Ratchet ceilings: the most of each problem this repo is allowed to contain.
#
# Going OVER a ceiling fails the gate. Going UNDER it also fails, asking you to
# lower the number -- so an improvement is locked in and a ceiling only ever
# travels downward. Same contract as tests/BASELINE.txt, applied to counts.
#
# These are pre-existing, not a standard being set. The goal is 0 everywhere.
# Regenerate with:  uv run python scripts/check_conventions.py --write-ratchets

"""

LINE = re.compile(r"^(?P<name>[a-z_]+)\s*=\s*(?P<value>\d+)$")


def load_ratchets() -> dict[str, int]:
    if not RATCHETS.exists():
        return {}
    out: dict[str, int] = {}
    for raw in RATCHETS.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = LINE.match(line)
        if not match:
            raise SystemExit(f"ratchets.txt: cannot parse {raw!r}")
        out[match["name"]] = int(match["value"])
    return out


def write_ratchets(counts: dict[str, int]) -> None:
    body = "\n".join(f"{name} = {counts[name]}" for name in sorted(counts))
    RATCHETS.write_text(HEADER + body + "\n")


def lower_ratchets(counts: dict[str, int]) -> int:
    """Lower every ceiling the code now beats. Never raises one.

    The strict ratchet fails when a count IMPROVES, which is what locks the gain
    in. But hand-editing a file to record "I fixed three lint errors" is the
    friction that turns into skipping the gate. This makes compliance one command,
    and it is safe at any time because it is monotonic: a ceiling can only travel
    down, so it can never mask a regression.
    """
    ceilings = load_ratchets()
    lowered = {k: v for k, v in counts.items() if k in ceilings and v < ceilings[k]}
    if not lowered:
        print("Nothing to lower: no ceiling is being beaten.")
        return 0
    write_ratchets({**ceilings, **lowered})
    for name in sorted(lowered):
        print(f"  lowered  {name}: {ceilings[name]} -> {lowered[name]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="skip the slow counters (type checking). Inner loop only: "
        "`make check` is still the gate.",
    )
    parser.add_argument(
        "--lower-ratchets",
        action="store_true",
        help="lower any ceiling the code now beats, and change nothing else. "
        "Safe: it can only move a ceiling DOWN.",
    )
    parser.add_argument(
        "--write-ratchets",
        action="store_true",
        help="rewrite ratchets.txt from the current counts (human-approved action)",
    )
    args = parser.parse_args()

    slow = {"pyright_errors"}
    active = {k: v for k, v in CHECKS.items() if not (args.fast and k in slow)}
    counts = {name: fn() for name, fn in active.items()}

    if args.lower_ratchets:
        return lower_ratchets(counts)

    if args.write_ratchets and args.fast:
        raise SystemExit(
            "--write-ratchets cannot be combined with --fast: it would drop the "
            "ceilings the fast run skipped."
        )

    if args.write_ratchets:
        write_ratchets(counts)
        print(f"Wrote {len(counts)} ceilings to {RATCHETS.relative_to(ROOT)}:")
        for name in sorted(counts):
            print(f"  {name} = {counts[name]}")
        return 0

    ceilings = load_ratchets()
    if args.fast:
        ceilings = {k: v for k, v in ceilings.items() if k in counts}
        print("  ..  fast mode: type checking skipped (`make check` still runs it)")
    errors: list[str] = []
    warnings: list[str] = []

    check_file_budgets(errors, warnings)
    check_untested_modules(errors)
    check_test_theme_isolation(errors)
    check_agents_md_drift(errors)
    check_decision_pointers(errors)

    for name in sorted(counts):
        actual = counts[name]
        if name not in ceilings:
            errors.append(f"{name}: no ceiling recorded (actual {actual}).")
            continue
        ceiling = ceilings[name]
        if actual > ceiling:
            errors.append(
                f"{name}: {actual}, ceiling is {ceiling}. "
                f"You added {actual - ceiling}. Fix them, or say why the ceiling moves."
            )
        elif actual < ceiling:
            errors.append(
                f"{name}: {actual}, ceiling is {ceiling}. Improved -- lower the "
                f"ceiling to {actual} with `make ratchets-lower`."
            )
        else:
            print(f"  ok  {name} = {actual}")

    for name in sorted(set(ceilings) - set(counts)):
        errors.append(f"{name}: ceiling recorded but nothing measures it. Remove it.")

    for warning in warnings:
        print(f"  note  {warning}", file=sys.stderr)

    if errors:
        print("\nConvention check FAILED:\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("Conventions OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
