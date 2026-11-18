#!/usr/bin/env python3
"""Fetch the fonts the themes name into assets/fonts/, byte for byte as locked.

No font lives in the repository. `assets/fonts.lock` names every font file the
themes in the snapshot corpus use; `md2ui.utils.font_lock` fetches them, checks
every hash and refuses a file whose bytes differ -- the same fetch an installed
md2ui makes into its per-user cache. A font Skia cannot find is not an error to
it -- it falls back to another face -- so a missing one has to stop the run here
instead.

Usage:
    uv run python scripts/fetch_assets.py           fetch what is missing (`make assets`)
    uv run python scripts/fetch_assets.py --check   fetch nothing; exit 1 if any is missing or differs
"""

from __future__ import annotations

import sys
from pathlib import Path

from md2ui.utils.font_lock import fetch, problems, read_lock

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "assets" / "fonts.lock"
FONTS = ROOT / "assets" / "fonts"


def main(argv: list[str]) -> int:
    locked = read_lock(LOCK)
    if argv == ["--check"]:
        found = problems(locked, FONTS)
        for line in found:
            print(f"[assets] {line}")
        if found:
            print(
                f"[assets] {len(found)} of {len(locked)} fonts are not as locked: run `make assets`"
            )
            return 1
        return 0
    if argv:
        print(__doc__)
        return 2
    failures = fetch(locked, FONTS)
    for line in failures:
        print(f"[assets] {line}")
    if failures:
        return 1
    print(f"[assets] {len(locked)} fonts as locked in {FONTS.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
