"""Which detector patterns can match a text at all, decided before any of them runs.

The detector runs ~100 patterns over every text the grouper asks about, and most
of them cannot match most texts: most need a digit, and many texts hold none.
A pattern is skipped only when the text
lacks a character that EVERY match of it must contain -- proven from the
pattern's own syntax tree, never guessed from samples -- so skipping it cannot
change what the detector finds.

A pattern whose tree cannot be read gets no guard and always runs.
"""

from __future__ import annotations

import importlib
import re
from typing import Any

# The syntax tree comes from the stdlib's own regex parser, which is private
# (typeshed carries no stubs for it, hence the import by name).
_P = importlib.import_module("re._parser")
_C = importlib.import_module("re._constants")

_DIGIT = re.compile(r"\d")
_DIGITS = frozenset("0123456789")
_NEEDS_DIGIT = "DIGIT"

Pattern = tuple[re.Pattern[str], Any, Any]  # (regex, data_type, parser)


def required(regex: re.Pattern[str]) -> frozenset[str]:
    """What every match of *regex* contains: ``"DIGIT"`` for a ``\\d``
    character, and each single character it must consume literally.

    Empty -- no guard -- whenever the tree cannot be read.
    """
    try:
        tree = _P.parse(regex.pattern, regex.flags)
        return frozenset(_seq(tree, regex.flags))
    except Exception:  # an unreadable tree only costs the skip
        return frozenset()


def _seq(items: Any, flags: int) -> set[str]:
    # Every item of a sequence is consumed, so their requirements add up.
    out: set[str] = set()
    for op, av in items:
        out |= _item(op, av, flags)
    return out


def _item(op: Any, av: Any, flags: int) -> set[str]:
    if op is _C.LITERAL:
        ch = chr(av)
        if ch in _DIGITS:
            return {_NEEDS_DIGIT}
        if flags & re.IGNORECASE and (ch.lower() != ch or ch.upper() != ch):
            return set()  # a cased letter matches more than itself
        return {ch}
    if op is _C.IN:
        return {_NEEDS_DIGIT} if _only_digits(av) else set()
    if op is _C.SUBPATTERN:
        _group, add, delete, sub = av
        return _seq(sub, (flags | add) & ~delete)
    if op in (_C.MAX_REPEAT, _C.MIN_REPEAT, _C.POSSESSIVE_REPEAT):
        low, _high, sub = av
        return _seq(sub, flags) if low >= 1 else set()
    if op is _C.BRANCH:
        _, branches = av
        common = _seq(branches[0], flags)
        for branch in branches[1:]:
            common &= _seq(branch, flags)
        return common
    if op is _C.ATOMIC_GROUP:
        return _seq(av, flags)
    # Lookarounds and anchors consume nothing; any other item consumes a
    # character no single guard describes.
    return set()


def _only_digits(members: Any) -> bool:
    for op, av in members:
        if op is _C.CATEGORY:
            if av is not _C.CATEGORY_DIGIT:
                return False
        elif op is _C.LITERAL:
            if chr(av) not in _DIGITS:
                return False
        elif op is _C.RANGE:
            low, high = av
            if not (ord("0") <= low and high <= ord("9")):
                return False
        else:  # a negation, or a class wider than digits
            return False
    return True


class PatternGuards:
    """The patterns of one list that can match a given text, in list order.

    The order is kept because overlap resolution reads it. Which patterns can
    match depends only on which guard characters the text holds, so the answer
    is kept per combination: a handful of combinations cover a whole document.
    """

    def __init__(self, patterns: list[Pattern]) -> None:
        guarded = [(entry, required(entry[0])) for entry in patterns]
        self._chars = tuple(
            sorted({c for _, need in guarded for c in need} - {_NEEDS_DIGIT})
        )
        self._guarded = guarded
        self._live: dict[tuple[bool, ...], list[Pattern]] = {}

    def live(self, text: str) -> list[Pattern]:
        key = (_DIGIT.search(text) is not None, *(c in text for c in self._chars))
        hit = self._live.get(key)
        if hit is None:
            present = {c for c, there in zip(self._chars, key[1:]) if there}
            if key[0]:
                present.add(_NEEDS_DIGIT)
            hit = self._live[key] = [
                entry for entry, need in self._guarded if need <= present
            ]
        return hit
