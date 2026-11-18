"""How a chart value shows the unit its author declared (``Value format``).

A value written in no chart unit is written bare and its unit declared once by
the data -- ``Temperature (°C):`` above a run, ``High (°C)`` as a line's key.
The unit is only shown, never read: the theme's ``Value format`` places it, the
way ``Number format`` places a list marker's punctuation. ``1`` (the default)
leaves values bare, the unit shown only where the author wrote it.
"""

import re

# A declared unit: words or symbols in the last parentheses, with no digit, so
# `Results (2025)` declares nothing. Units in words run long (`millions of
# shares`, `kilowatt-hours per day`); what keeps a sentence's last aside from
# reading as one is the short line that must carry it (`grouper_charts`).
MAX_UNIT = 32
_DECLARED = re.compile(rf"\(([^()\d]{{1,{MAX_UNIT}}})\)\s*:?\s*$")
_BRACKET = re.compile(r"\(([^()\d]+)\)\s*:?\s*$")
_BARE = re.compile(r"^[-+−]?[\d.,]+$")


def declared_unit(text: str) -> str | None:
    """The unit *text* ends by declaring, `High (°C)` -> `°C`; None if none."""
    m = _DECLARED.search(text.strip())
    return m.group(1).strip() or None if m else None


def last_bracket(text: str) -> str | None:
    """The words in the parentheses *text* ends with, whatever their length,
    `Volume (millions of shares)` -> `millions of shares`; None if none."""
    m = _BRACKET.search(text.strip())
    return m.group(1).strip() or None if m else None


def without_unit(text: str) -> str:
    """*text* without the unit it declares: `High, Low (°C)` -> `High, Low`."""
    return _DECLARED.sub("", text.strip()).strip()


def is_bare(text: str) -> bool:
    """Whether a value is written as a bare number, the form a declared unit
    labels."""
    return bool(_BARE.match(text.strip()))


def with_unit(text: str, unit: str | None, fmt: str) -> str:
    """*text*, a bare value, shown with *unit* as *fmt* places it."""
    if not unit or fmt == "1":
        return text
    return fmt.replace("unit", "\0").replace("1", text).replace("\0", unit)
