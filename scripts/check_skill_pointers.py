#!/usr/bin/env python3
"""Every pointer in ``skills/`` to a note or a section must name one ``guide`` serves.

A section is a topic because its heading is (``notes.sections``), so renaming a
heading silently breaks every pointer to it: the agent that follows one gets
"no note named", or reads nothing. The notes name a topic in four ways, and
each is checked:

* a link to a note, with or without a section: ``[…](elements.md#icon-buttons)``;
* a topic in backticks, the label of such a link or on its own:
  ``elements/icon-buttons``, ``patterns/directory``;
* a ``guide("…")`` call written out;
* a note followed by a section's heading in italics, after a comma or an
  arrow: ``[`structure.md`](structure.md), *Escape a separator*``.

A name with a placeholder in it (``patterns/<name>``) names no topic. Nor does a
``theme/`` topic: those are the patterns of the theme a server runs with.

Pointers broken before this check existed are listed in ``KNOWN_BROKEN`` with
the date they were recorded. Fixing one changes ``skills/`` text, which is
measured with an eval before it ships, so the list only ever shrinks: a new
broken pointer fails, and so does a listed one that resolves -- delete its line,
which is how a fix is recorded. Same contract as ``tests/BASELINE.txt``.

Run via ``make check``, or directly:  uv run python scripts/check_skill_pointers.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from md2ui.mcp_server import PATTERNS, SKILLS, guide_notes, note_topics
from md2ui.notes import slug

# (note it is written in, topic it names) -> the date it was recorded broken.
# The comment above each says where it probably meant to point.
KNOWN_BROKEN: dict[tuple[str, str], str] = {
    # the escape paragraph is in `structure/the-whole-line-tools`
    # the heading is "A token grid: calendars, heatmaps, seat maps"
    ("skills/renders/README.md", "dashboards/a-token-grid"): "2026-10-20",
}

# Topics guide answers without a note of that name.
BUILT_IN = {"patterns", "theme"}

_LINK = re.compile(r"\]\(([^)\s#]+\.md)(?:#([^)\s]+))?\)")
_TICKED = re.compile(r"`([a-z][a-z0-9-]*/[a-z0-9-]+)`")
_GUIDE = re.compile(r"""guide\(["']([^"']+)["']\)""")
_ITALIC_AFTER = re.compile(
    r"(?:\]\(([^)\s#]+\.md)\)|`([a-z0-9-]+\.md)`)\s*[,→]\s*\*([^*]+)\*"
)


def served_topics() -> set[str]:
    """Every topic ``guide`` serves whatever the theme."""
    return set(note_topics(guide_notes())) | BUILT_IN


def _note_topic(path: Path) -> str | None:
    """The note at *path* as guide names it; None for a file outside the
    notes, which a link may name without naming a topic."""
    folder, name = path.resolve().parent, path.stem.lower()
    if folder == SKILLS.resolve():
        return name
    if folder == PATTERNS.resolve():
        return f"patterns/{name}"
    return None


def pointers(source: Path, text: str) -> list[tuple[int, str]]:
    """The topics *text*, the note at *source*, names, with their line numbers."""
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        for target, anchor in _LINK.findall(line):
            note = _note_topic(source.parent / target)
            if note is not None:
                found.append((number, f"{note}/{anchor}" if anchor else note))
        for topic in _TICKED.findall(line) + _GUIDE.findall(line):
            found.append((number, topic))
        for linked, ticked, heading in _ITALIC_AFTER.findall(line):
            note = _note_topic(source.parent / linked if linked else SKILLS / ticked)
            if note is not None:
                found.append((number, f"{note}/{slug(heading)}"))
    return [
        (n, t)
        for n, t in found
        if not re.search(r"[<>{}]", t) and not t.startswith("theme/")
    ]


def broken(served: set[str]) -> list[tuple[str, int, str]]:
    """Every pointer in ``skills/`` to a topic not in *served*."""
    out: list[tuple[str, int, str]] = []
    for path in sorted(SKILLS.rglob("*.md")):
        rel = str(path.relative_to(SKILLS.parent))
        for number, topic in pointers(path, path.read_text()):
            if topic.lower() not in served:
                out.append((rel, number, topic))
    return out


def main() -> int:
    found = broken(served_topics())
    errors = [
        f"{rel}:{number}: names `{topic}`, which guide does not serve."
        for rel, number, topic in found
        if (rel, topic) not in KNOWN_BROKEN
    ]
    still = {(rel, topic) for rel, _, topic in found}
    errors += [
        f"KNOWN_BROKEN lists {rel} -> `{topic}` (recorded {date}), which no longer "
        "breaks. Delete its line."
        for (rel, topic), date in sorted(KNOWN_BROKEN.items())
        if (rel, topic) not in still
    ]
    if errors:
        print("\nSkill pointer check FAILED:\n", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"Skill pointers OK ({len(KNOWN_BROKEN)} known broken)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
