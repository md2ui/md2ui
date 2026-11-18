#!/usr/bin/env python3
"""The test gate. Runs every ``TESTS`` list under ``tests/`` and judges the result
against ``tests/BASELINE.txt``.

Why this exists: the suite is dozens of hand-run modules with a handful of
long-standing failures. Without a recorded baseline, "did I break this?" is
indistinguishable from "was it already broken?", and the answer gets re-derived
by hand every session.

Conventions it relies on (see AGENTS.md):
  * a test module is ``tests/*_tests.py`` and exposes a module-level ``TESTS`` list
    of zero-argument callables;
  * modules import their siblings by bare name, so ``tests/`` goes on ``sys.path``
    and the working directory is the repo root;
  * a test that cannot run where it is run -- one that drives AppKit, off macOS --
    raises ``unittest.SkipTest`` with the reason. A skip is listed, never counted
    as a pass, and is not a failure to baseline.

Aggregator modules that re-export a sibling's ``TESTS`` are handled without a
skip-list: tests are keyed by the module that *defines* them, so a re-export
collapses onto the original instead of running twice.

Run via ``make check``, or directly:  uv run python scripts/run_tests.py
"""

from __future__ import annotations

import argparse
import importlib
import sys
import traceback
import unittest
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests"
BASELINE = TESTS_DIR / "BASELINE.txt"

IMPORT_FAILURE = "<import>"


def _key(module: str, test: str) -> str:
    return f"{module}::{test}"


def load_baseline() -> set[str]:
    """Known failures, one ``module::test`` per line. ``#`` comments allowed."""
    if not BASELINE.exists():
        return set()
    entries = set()
    for raw in BASELINE.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            entries.add(line)
    return entries


def discover() -> list[str]:
    return sorted(p.stem for p in TESTS_DIR.glob("*_tests.py"))


def collect(
    module_names: list[str],
) -> tuple[dict[str, Callable[[], object]], list[str], list[str]]:
    """Import each module and gather its TESTS, keyed by the DEFINING module.

    Returns (tests_by_key, import_failure_keys, modules_without_a_TESTS_list).
    """
    tests: dict[str, Callable[[], object]] = {}
    import_failures: list[str] = []
    no_tests: list[str] = []

    for name in module_names:
        try:
            module = importlib.import_module(name)
        except BaseException:  # a module may SystemExit or segfault-adjacent on import
            import_failures.append(_key(name, IMPORT_FAILURE))
            print(f"  !  {name}: failed to import", file=sys.stderr)
            traceback.print_exc(limit=3, file=sys.stderr)
            continue

        if not hasattr(module, "TESTS"):
            # Not runnable by the gate. Silently collecting nothing here is how a
            # test module goes dead without anyone noticing, so say so out loud.
            no_tests.append(name)
            continue

        for func in module.TESTS:
            # Attribute to where it is defined, so aggregator re-exports dedupe.
            owner = getattr(func, "__module__", name)
            tests.setdefault(_key(owner, getattr(func, "__name__", repr(func))), func)

    return tests, import_failures, no_tests


def run(tests: dict[str, Callable[[], object]]) -> tuple[list[str], dict[str, str]]:
    """Run every test; return the failures and the skips with their reasons."""
    failures: list[str] = []
    skipped: dict[str, str] = {}
    for key in sorted(tests):
        try:
            tests[key]()
        except unittest.SkipTest as skip:
            skipped[key] = str(skip)
        except BaseException as exc:
            failures.append(key)
            print(f"  x  {key}: {type(exc).__name__}: {exc}")
    return failures, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="rewrite tests/BASELINE.txt from this run (human-approved action)",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(TESTS_DIR))
    sys.path.insert(0, str(ROOT))

    module_names = discover()
    print(f"Collecting from {len(module_names)} test modules...")
    tests, import_failures, no_tests = collect(module_names)
    print(f"Running {len(tests)} tests.")
    for name in no_tests:
        print(f"  ?  {name}: no TESTS list, nothing run.", file=sys.stderr)
    print()

    failures, skipped = run(tests)
    failed = set(failures) | set(import_failures)
    passed = set(tests) - failed - set(skipped)
    for key, reason in sorted(skipped.items()):
        print(f"  -  skipped {key}: {reason}")

    if args.write_baseline:
        write_baseline(sorted(failed))
        print(f"\nWrote {len(failed)} known failures to {BASELINE.relative_to(ROOT)}.")
        return 0

    baseline = load_baseline()
    regressions = sorted(failed - baseline)
    fixed = sorted(baseline & passed)
    stale = sorted(b for b in baseline if b not in tests and b not in failed)

    print(
        f"\n{len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped, "
        f"{len(baseline)} baselined."
    )

    if not (regressions or fixed or stale):
        print("Gate OK: failures match the baseline exactly.")
        return 0

    print("\nGate FAILED:\n", file=sys.stderr)
    for key in regressions:
        print(f"  - NEW failure, not in the baseline: {key}", file=sys.stderr)
    for key in fixed:
        print(
            f"  - {key} now PASSES. Delete it from tests/BASELINE.txt so the "
            "baseline cannot rot.",
            file=sys.stderr,
        )
    for key in stale:
        print(
            f"  - {key} is baselined but no longer exists. Delete it from "
            "tests/BASELINE.txt.",
            file=sys.stderr,
        )
    return 1


def write_baseline(failures: list[str]) -> None:
    header = (
        "# Known-failing tests, one `module::test` per line.\n"
        "#\n"
        "# This file is the difference between 'I broke it' and 'it was already\n"
        "# broken'. scripts/run_tests.py fails the gate on any failure NOT listed\n"
        "# here, and equally on any entry here that starts passing -- so the file\n"
        "# cannot silently rot.\n"
        "#\n"
        "# Removing a line is the normal way to record a fix. Adding one is a\n"
        "# deliberate act: it accepts a failure. Regenerate with\n"
        "#   uv run python scripts/run_tests.py --write-baseline\n"
        "\n"
    )
    BASELINE.write_text(header + "\n".join(failures) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
