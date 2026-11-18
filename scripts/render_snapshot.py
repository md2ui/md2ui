#!/usr/bin/env python3
"""Render a fixed corpus to PNGs, for before/after comparison around a refactor.

A refactor of the renderer is only safe if the pixels do not move. `make check`
proves the tests still pass; this proves the *output* is unchanged, which is the
part tests cannot fully cover for a drawing program.

Usage:
    uv run python scripts/render_snapshot.py <out-dir>
    diff -rq <before-dir> <after-dir>     # must be silent

The corpus is two parts: the SAMPLES x WIDTHS grid, which covers layout and
painting, and VARIANTS, which covers display state the CLI can set — the overlay
flags. Without the second part a change to how that state reaches the painting
code moves no pixels at all, and the comparison silently proves nothing.

Any difference is either a bug or a deliberate change that must be explained in
the change itself (AGENTS.md, *Before finishing*).

**Every line is regenerated.** Each render is one `md2ui render <doc.md>`, which
groups the Markdown before laying it out, so the grouper runs and a grouper
change is visible in the pixels. Nothing renders from a committed
`grouping-ast.json`: those depend on nothing upstream of the layout stage, so a
grouper change cannot move them at all, and a green run of them proves the
renderer is unchanged and nothing more.

The corpus is every `.md` under `data/markdown/tests` and
`data/markdown/tests-render` — the same rule `grouper_snapshot.py` uses, so the
two oracles cover exactly the same fixture files. A document with a `THEME.md`
beside it renders with that theme; the rest fall back to the repo-root
`THEME.md` (the CLI resolves beside the document, then the working directory,
which is the repo root here). That fallback is stable within one before/after
pair.

The renders run in parallel, one subprocess each. Each writes only its own PNG,
so the set of files and their bytes are those of a one-at-a-time run; only the
wall time changes. The report is printed in the fixed corpus order.

It refuses to start unless every font in `assets/fonts.lock` is present and as
locked (`make assets`): a missing one would render in a fallback face.
"""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fetch_assets import FONTS, LOCK

from md2ui.utils.font_lock import problems, read_lock

ROOT = Path(__file__).resolve().parent.parent


def _samples() -> tuple[str, ...]:
    """Every `.md` under the two fixture directories, in a stable order.

    One rule, the same one `grouper_snapshot.py` uses: every Markdown file in
    `tests` and `tests-render` is rendered from its own Markdown. Every line is
    therefore regenerated -- the grouper ran, and a grouper change is visible in
    the pixels. The real-response and training corpora are outside this fixture
    snapshot by design.

    A narrower rule misses documents: a hand-listed corpus leaves samples out,
    and a change to them moves pixels with both oracles silent. Deriving the
    list means a new sample is covered the day it is added.

    A `THEME.md` renders as the ordinary Markdown it is, themed by itself.
    """
    markdown = ROOT / "data" / "markdown"
    roots = (markdown / "tests", markdown / "tests-render")
    return tuple(
        sorted(
            str(path.relative_to(ROOT)) for root in roots for path in root.rglob("*.md")
        )
    )


SAMPLES = _samples()
WIDTHS = (767, 1280)

# One render per DISPLAY-STATE flag the CLI can set. The plain corpus above
# renders with every one of them at its default, so a change to how that state
# reaches the painting code would not move a single pixel in it. These put the flags in their
# non-default position, so the state itself is under the byte comparison.
#
# `(name, document, width, extra CLI args)`. A variant that renders the same as
# the plain corpus proves nothing, so check that before adding one.
VARIANTS = (
    (
        "overlays",
        "data/markdown/tests-render/home-dashboards/kawsar-ahmed-macos-custom-widget/content.md",
        1280,
        ["--wireframe", "--debug", "--debug-padding", "--text-boxes"],
    ),
)


def _render(document: str, width: int, out: Path, extra: list[str]) -> str | None:
    """One `md2ui render`; returns its report line, or None when it landed."""
    proc = subprocess.run(
        [
            "uv",
            "run",
            "md2ui",
            "render",
            document,
            "--width",
            str(width),
            "--out",
            str(out),
            *extra,
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if proc.returncode != 0 or not out.exists():
        return f"  FAIL  {out.name}\n{proc.stderr[-500:]}"
    return None


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    # A font the themes name but this machine lacks renders in a fallback face:
    # the snapshot would differ from another machine's for no code change.
    fonts = problems(read_lock(LOCK), FONTS)
    if fonts:
        print("\n".join(fonts) + "\nrun `make assets` first", file=sys.stderr)
        return 1
    out_dir = Path(sys.argv[1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = [
        (sample, width, out_dir / f"{sample[:-3].replace('/', '_')}_{width}.png", [])
        for sample in SAMPLES
        for width in WIDTHS
    ] + [
        (document, width, out_dir / f"variant_{label}_{width}.png", extra)
        for label, document, width, extra in VARIANTS
    ]
    workers = max(1, (os.cpu_count() or 2) - 1)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda job: _render(*job), jobs))

    failures = [r for r in results if r is not None]
    for report in failures:
        print(report)
    print(f"\n{len(jobs)} jobs, {len(failures)} failed, in {out_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
