"""A shared pattern's example, served in the loaded project's spellings.

The patterns in ``skills/patterns/`` are shared by every project and written in
the default theme's spellings: ``listing``'s ``**[Reserve](…)**`` is that theme's
action a card is for. Another project may spell that place otherwise, or not at
all. ``guide("patterns/<name>")`` serves each wrapped spelling of the example as
the project writes the same place, found through the defaults' *Slot* column
(ADR-501); the default theme reads the file as written. A shell module beside
``meanings``; the pipeline never imports it.
"""

from __future__ import annotations

import re
from pathlib import Path

from md2ui.meanings import (
    _CHIP_WRAPPER,
    _FENCED,
    _WRAPPER,
    BASE,
    Contract,
    Selection,
    parse,
    pattern_spellings,
    resolve,
)
from md2ui.pipeline.grouper_types import (
    _LINK_VARIANT_WRAPPERS,
    _classify_link_content,
    link_destination,
)

# A spelling a shared pattern's example may wrap: a link (button or icon button), a
# chip, a lone emoji, each with its wrapper and an optional `~~` around it all.
_LINK_SPELLING = re.compile(
    r"(~~)?((?:[*_]{1,3})?)(\[(?:[^\[\]\n]|\[[^\]\n]*\])*\]\((?:[^()\s]|\([^)]*\))*\))\2(~~)?"
)
_CHIP_SPELLING = re.compile(r"(~~)?((?:[*_]{1,3})?)(`[^`\n]+`)\2(~~)?")
_ICON_SPELLING = re.compile(r"(~~)?([*_]{1,3})([^\s*_`\[\]()~]{1,12})\2(~~)?")
_FACE_WRAPPER = {"italic": "*", "bold": "**", "bold_italic": "***"}
# A button's wrapper by its variant, `*` and `_` ladders both: the grouper's own table.
_LINK_WRAPPER = {name: marker for marker, name in _LINK_VARIANT_WRAPPERS}


def respelled(pattern: Path, contract: Contract | None) -> str:
    """The shared pattern at *pattern*, its example's wrapped spellings written as
    the project whose *contract* is loaded writes them.

    The patterns are written in the default theme's spellings. Each wrapped one
    is mapped to its place through the defaults' *Slot* column, then written as
    the project's row for that slot spells it; a project that has no row for the
    slot keeps a spelling it declares, and otherwise gets the bare spelling, which
    every theme draws. What the pattern declares in its own table stays, as do
    bare, text-link and muted spellings. The default theme reads the file as
    written."""
    text = pattern.read_text(encoding="utf-8")
    defaults = parse(BASE.read_text(encoding="utf-8")) if BASE.is_file() else None
    if defaults is not None and contract is not None and contract == defaults:
        return text
    own = pattern_spellings(pattern)

    def example(fence: re.Match[str]) -> str:
        block, taken = fence.group(0), []
        for spelling in (_LINK_SPELLING, _CHIP_SPELLING, _ICON_SPELLING):
            for m in spelling.finditer(block):
                if any(a < m.end() and m.start() < b for a, b, _ in taken):
                    continue
                new = _respell(m.group(0), m.group(3), contract, defaults, own)
                taken.append((m.start(), m.end(), new))
        for start, end, new in sorted(taken, reverse=True):
            block = block[:start] + new + block[end:]
        return block

    return _FENCED.sub(example, text)


def _respell(
    written: str,
    core: str,
    contract: Contract | None,
    defaults: Contract | None,
    own: frozenset,
) -> str:
    """*written* (its element *core* unwrapped) as the project spells its place."""
    selects = resolve(written)
    if selects is None or selects.key in own:
        return written
    if selects.variant in ("primary", "text", "quoted") and selects.face is None:
        return written
    target = _target(selects, contract, defaults)
    if selects.element in ("button", "icon button"):
        _v, label, _e, _d, _f = _classify_link_content(core)
        destination = link_destination(core) or ""
        if target is not None and target.variant == "text":
            body = f"[`{label}`]({destination})"
            wrap = _FACE_WRAPPER.get(target.face or "", "")
        else:
            body = f"[{label}]({destination})"
            wrap = _LINK_WRAPPER.get(target.variant, "") if target else ""
    else:
        body = core
        table = _CHIP_WRAPPER if selects.element == "chip" else _WRAPPER
        wrap = table.get(target.variant, "") if target else ""
    respelled = f"{wrap}{body}{wrap}"
    return f"~~{respelled}~~" if selects.state == "muted" else respelled


def _target(
    selects: Selection, contract: Contract | None, defaults: Contract | None
) -> Selection | None:
    """What the project writes for *selects*'s place: its row for the slot the
    defaults give *selects*, else *selects* when it declares it, else None (bare)."""
    if contract is None:
        return None
    slots = {
        slot
        for row in (defaults.declared(selects.element) if defaults else [])
        if row.selects is not None and row.selects.key == selects.key
        for slot in row.slots
    }
    rows = [r for r in contract.declared(selects.element) if r.selects is not None]
    for row in rows:
        if slots.intersection(row.slots) and row.selects is not None:
            return row.selects
    if any(r.selects is not None and r.selects.key == selects.key for r in rows):
        return selects
    return None
