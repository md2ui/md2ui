#!/usr/bin/env python3
"""Snapshot the grouper's output over a fixed corpus, for before/after diffing.

The renderer has a pixel snapshot; the grouper has this. A grouper change is only
safe if the AST it produces is unchanged, and the tests cannot cover that on their
own -- they assert on specific shapes, not on every document in the corpus.

The ritual, followed exactly:

    process() over every `.md` under data/markdown/tests and
      data/markdown/tests-render
      with the SplitCriteria + DataPointDetector
    dump ast.to_dict() to JSON per file, named by its path under data/markdown
    and the runs beside it (`.runs.json`): `to_dict()` leaves out which siblings
    run together, so a run change otherwise reaches only the render snapshot,
    and only where it draws

Usage:
    uv run python scripts/grouper_snapshot.py <out-dir>
    diff -rq <before-dir> <after-dir>     # must be silent

Two traps, both avoided here: take both snapshots against the
source you mean to compare (not one from memory), and diff the node tree
separately from the flags if a difference shows up.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from md2ui.pipeline.grouper_types import MarkdownGroupNode

ROOT = Path(__file__).resolve().parent.parent
MARKDOWN = ROOT / "data" / "markdown"


def _corpus() -> list[Path]:
    """Every `.md` under the two fixture directories, in a stable order.

    The snapshot scope is the regression corpus in `tests` and the adversarial
    render corpus in `tests-render`. The rule is recursive and includes every
    Markdown source beside a sample, including its `THEME.md`; it deliberately
    excludes the real-response and training corpora.

    Only `.md` sources are read. The `grouping-ast.json` / `layout-ast-*.json`
    beside some of them are stale artifacts of an older format.
    """
    roots = (MARKDOWN / "tests", MARKDOWN / "tests-render")
    return sorted(path for root in roots for path in root.rglob("*.md"))


CORPUS = _corpus()


def _runs(node: MarkdownGroupNode, path: str = "root") -> dict:
    """Each run by its parent's path and its members' positions, and each
    orphan gridded at its siblings' width: the run facts `to_dict()` leaves
    live-only. Positions, not `run_key`, which hashes a node id."""
    runs, orphans = [], []
    for run in (node.repeated_children or {}).values():
        if len(run) > 1:
            at = [i for i, c in enumerate(node.children) if any(c is m for m in run)]
            runs.append({"parent": path, "children": at})
    for i, child in enumerate(node.children):
        here = f"{path}/{i}"
        if child.orphan_grid:
            orphans.append(here)
        below = _runs(child, here)
        runs += below["runs"]
        orphans += below["orphan_grid"]
    return {"runs": runs, "orphan_grid": orphans}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out_dir = Path(sys.argv[1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    from md2ui.pipeline.grouper_split_criteria import SplitCriteria
    from md2ui.pipeline.data_point_detector import DataPointDetector
    from md2ui.pipeline.markdown_grouper import MarkdownGrouper

    criteria = SplitCriteria()
    detector = DataPointDetector()

    failures = 0
    for path in CORPUS:
        try:
            grouper = MarkdownGrouper(path.read_text())
            grouper.process(criteria, detector)
            assert grouper.ast is not None
            payload = json.dumps(grouper.ast.to_dict(), indent=2, sort_keys=True)
            runs = json.dumps(_runs(grouper.ast), indent=2)
        except Exception as exc:  # noqa: BLE001 — a failure is a result worth recording
            failures += 1
            payload = json.dumps({"error": f"{type(exc).__name__}: {exc}"}, indent=2)
            runs = payload
            print(f"  FAIL  {path.relative_to(MARKDOWN)}: {type(exc).__name__}: {exc}")
        # Named by path, not stem: 24 of these documents are called `content.md`.
        rel = path.relative_to(MARKDOWN).with_suffix(".json")
        name = str(rel).replace("/", "__")
        (out_dir / name).write_text(payload)
        (out_dir / name).with_suffix(".runs.json").write_text(runs)

    print(
        f"\n{len(CORPUS)} documents -> {out_dir}"
        + (f"  ({failures} failed)" if failures else "")
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
