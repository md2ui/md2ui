"""What `check` and the theme lint say about named image placeholders (ADR-406).

A placeholder an agent may use is declared twice, and both halves must agree: THEME.md
draws it (`## Images` → `### Placeholders` → `#### Avatar`), and MEANINGS.md says what it
is for, in a row whose spelling names it (`?md2ui.placeholder=avatar:SZ`). A placeholder
with no row is invisible to agents, who write only declared spellings (ADR-501); a row
with no placeholder promises a look the theme does not draw.

`check` reads only the contract, as for every spelling: an image naming a placeholder
no row declares draws the default placeholder, so it is told. Its text is initials or
one emoji, so more than three characters is noted: it would not fit a circle.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator

from md2ui.meanings import Contract
from md2ui.pipeline.theme_model import Theme
from md2ui.utils.image_params import image_alt, placeholder_ref

# The most characters a placeholder's text holds: initials. One emoji is also fine.
MAX_TEXT = 3

_NAMED = re.compile(r"md2ui\.placeholder=([A-Za-z0-9-]+)")


def declared_names(contract: Contract) -> set[str]:
    """The placeholder names MEANINGS.md rows spell, in any section."""
    return {
        name.lower()
        for section in contract.sections
        for row in section.rows
        for name in _NAMED.findall(row.write)
    }


def _one_emoji(text: str) -> bool:
    """Whether *text* is a single emoji, joiners and variation selectors included."""
    marks = [c for c in text if unicodedata.category(c) not in ("Mn", "Cf")]
    return len(marks) == 1 and unicodedata.category(marks[0]) == "So"


def _images(node: dict) -> Iterator[dict]:
    if node.get("type") == "image" and node.get("content"):
        yield node
    for child in node.get("children", []):
        yield from _images(child)


def problems(tree: dict, contract: Contract | None) -> list[tuple[str, str, str]]:
    """``(level, code, message)`` for each image whose placeholder will not draw as
    written."""
    names = declared_names(contract) if contract is not None else None
    found: list[tuple[str, str, str]] = []
    for node in _images(tree):
        ref = placeholder_ref(str(node["content"]))
        if ref is None:
            continue
        name, text = ref
        picture = image_alt(str(node["content"]))
        if names is not None and name not in names:
            known = ", ".join(f"`{n}`" for n in sorted(names)) or "none"
            found.append(
                (
                    "warning",
                    "undeclared-placeholder",
                    f"Image `{picture}`: `{name}` is not a placeholder this theme "
                    f"declares, so the default one draws. Declared: {known}.",
                )
            )
        if len(text) > MAX_TEXT and not _one_emoji(text):
            found.append(
                (
                    "note",
                    "placeholder-text",
                    f"Image `{picture}`: `{text}` is more than {MAX_TEXT} characters; "
                    "a placeholder holds initials or one emoji.",
                )
            )
    return found


def lint(theme: Theme, contract: Contract | None) -> list[str]:
    """Placeholders THEME.md draws that no MEANINGS.md row offers, and the reverse."""
    drawn = set(theme.image_placeholders)
    if not drawn and contract is None:
        return []
    if contract is None:
        return [
            f"Placeholders {', '.join(sorted(drawn))} are drawn but this theme has no "
            "MEANINGS.md: agents cannot see them."
        ]
    offered = declared_names(contract)
    messages = [
        f"Placeholder `{name}` is drawn but no MEANINGS.md row offers it: agents "
        "cannot see it."
        for name in sorted(drawn - offered)
    ]
    messages += [
        f"MEANINGS.md offers placeholder `{name}`, but THEME.md declares no "
        f"`#### {name}` under `## Images` → `### Placeholders`."
        for name in sorted(offered - drawn)
    ]
    return messages


def unknown_blocks(text: str) -> list[str]:
    """The `###` blocks under `## Images` other than `### Placeholders`: the parser
    reads nothing in them, so a placeholder written there is dropped without a word."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)  # as parse_theme does
    found: list[str] = []
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            section = line[3:].strip().lower()
        elif section == "images" and line.startswith("### "):
            if line[4:].strip().lower() != "placeholders":
                found.append(
                    f"`{line}` under `## Images` is not a block md2ui reads: "
                    "everything in it is ignored. Placeholders, and the Loading, "
                    "Broken and Missing defaults, all go under `### Placeholders`."
                )
    return found
