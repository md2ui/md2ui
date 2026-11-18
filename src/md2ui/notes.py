"""The ``skills/`` notes as sections an agent can read one at a time.

An agent that follows a pointer to one fact should not pay for the whole note
it sits in: ``elements.md`` is long, and most of its sections are short
(ADR-502). So every heading of a note is a topic of its own, ``<note>/<section>``,
named by its heading's text, and naming a section is the same act as writing
it: no markup, no index to keep in step.

No name is matched loosely. A name agents were seen asking for that no heading
has is an alias: it serves the section they were looking for.

A shell module beside ``meanings``; the pipeline never imports it.
"""

from __future__ import annotations

import re

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_WORD = re.compile(r"[a-z0-9]+")


def slug(heading: str) -> str:
    """A heading's text as a topic name: lower case, words joined by hyphens,
    with the Markdown markers and apostrophes dropped (``A link's label`` is
    ``a-links-label``)."""
    text = re.sub(r"[`*_\"'’]", "", heading.lower())
    return "-".join(_WORD.findall(text))


def sections(text: str) -> dict[str, str]:
    """Each heading's section of *text* by its slug: the heading and everything
    under it, up to the next heading of its level or above. A heading inside a
    code fence is an example, not a section; a repeated slug keeps the first."""
    lines = text.splitlines(keepends=True)
    heads: list[tuple[int, str, int]] = []
    fenced = False
    for i, line in enumerate(lines):
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and (found := _HEADING.match(line)):
            heads.append((len(found.group(1)), slug(found.group(2)), i))
    out: dict[str, str] = {}
    for n, (level, name, start) in enumerate(heads):
        end = next((i for lv, _, i in heads[n + 1 :] if lv <= level), len(lines))
        out.setdefault(name, "".join(lines[start:end]))
    return out


_FEED = "elements/a-value-a-process-changes-while-the-page-is-shown"

# Names asked for in eval transcripts, by the topic each serves: agents ask for
# the `feed` tool by its own name.
ALIASES = {"feed": _FEED, "elements/feed": _FEED}


def aliased(topics: dict[str, str]) -> dict[str, str]:
    """*topics* with each alias whose section is there; a real name wins."""
    found = {name: topics[to] for name, to in ALIASES.items() if to in topics}
    return found | topics
