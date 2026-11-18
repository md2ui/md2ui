#!/usr/bin/env python3
"""Which types in `_PIPELINE_TYPES` are load-bearing, and which could go?

`_remove_overlaps` keeps the LONGEST match, so dropping a type does not simply
remove its annotations — it hands that span to a shorter DRAWING pattern, and
the pipeline then draws something wrong rather than nothing. This is what says
which types are guards and what each one prevents.

For every line of every corpus, compare the pipeline-typed results of
`detect_all` against `detect_pipeline`. A difference means the full scan had a
longer non-pipeline match covering the span; the report names the type that was
covering it and shows what the span became without it.

    uv run python scripts/audit_detector_scope.py

Clean output ("no dropped type changes a span") is the expected state. Run it
before removing anything from `_PIPELINE_TYPES` — and read ADR-102 first, which
records the standing caveat: a clean run proves nothing about content the corpora
do not contain. A type clean here can still mis-type such content (`35 years old`
-> `quantity`, which is emphasis-eligible).
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPORA = (
    "data/markdown/tests",
    "data/markdown/tests-render",
    "data/markdown/claude",
    "data/markdown/gemini",
    "data/markdown/gpt",
)


def main() -> int:
    from md2ui.pipeline.data_point_detector import DataPointDetector, _PIPELINE_TYPES

    detector = DataPointDetector()
    blame: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    lines = 0

    for corpus in CORPORA:
        for md in sorted((ROOT / corpus).rglob("*.md")):
            if md.name in ("README.md", "THEME.md"):
                continue
            for raw in md.read_text().splitlines():
                line = raw.strip()
                if not line:
                    continue
                lines += 1
                full = detector.detect_all(line)
                narrow = detector.detect_pipeline(line)
                wide = {
                    (m["type"], m["start"], m["end"])
                    for m in full
                    if m["type"] in _PIPELINE_TYPES
                }
                got = {(m["type"], m["start"], m["end"]) for m in narrow}
                if wide == got:
                    continue
                for kind, start, end in sorted(
                    got - wide, key=lambda x: (x[1], x[2], x[0].value)
                ):
                    culprit = next(
                        (
                            m["type"].value
                            for m in full
                            if m["type"] not in _PIPELINE_TYPES
                            and m["start"] <= start
                            and end <= m["end"]
                        ),
                        "(no cover — a genuinely new match)",
                    )
                    blame[culprit] += 1
                    if len(examples[culprit]) < 4:
                        examples[culprit].append(
                            f"{line[:58]!r}  ->  {kind.value} {line[start:end]!r}"
                        )

    print(f"{lines} non-blank lines across {len(CORPORA)} corpora\n")
    if not blame:
        print("No dropped type changes a span. The scope is self-consistent.")
        return 0
    print("dropped type acting as a guard       times   what the span became")
    for name, count in blame.most_common():
        print(f"  {name:<33} {count:>5}")
        for example in examples[name]:
            print(f"      {example}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
