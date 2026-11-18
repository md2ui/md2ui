"""What a feed post may say (ADR-608): the values it carries, or why it is refused.

A post is ``name: value`` lines in the page's own spelling, or a JSON object of
strings and numbers, and the line ``end``. A bar's value is a figure the bar can
take (``40%``, ``4/10``, a chart row's ``$1,200``); a slot's is short text
``wire_texts.check_text`` lets in, and a chip slot's one of the values the agent
declared when it opened the feed. One unusable line refuses the whole post.

The text in a post comes from the agent's own process, so it may reach the page
(ADR-608), but never as Markdown, and what the agent hears quotes it as data:
each refusal below writes the posted value with ``!r``.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import TYPE_CHECKING

from md2ui.wire_bars import Figure, check_domain
from md2ui.wire_frames import FrameError
from md2ui.wire_texts import check_text

if TYPE_CHECKING:
    from md2ui.wire_feeds import Feed

# A bar's value: a percentage, or bare, or a ratio with any unit after it. Its
# sign is read too, so a negative value is refused as outside the bar.
_LINE = re.compile(
    r"^(?P<key>.+?):\s*(?P<value>-?\d+(?:\.\d+)?)\s*"
    r"(?:%|/\s*(?P<of>\d+(?:\.\d+)?)(?:\s*(?P<unit>[^\d\s/].*?))?)?$"
)
_KEYED = re.compile(r"^(?P<key>.+?):\s*(?P<value>.+)$")  # a chart row's or a text


def read_post(feed: Feed, body: str) -> tuple[dict[str, float | str], bool]:
    """A post's values, refused whole if any of it is unusable."""
    lines = body.splitlines()
    if body.lstrip().startswith("{"):
        try:
            data = json.loads(body)
        except ValueError:
            raise FrameError("bad_value", "the body is not a JSON object") from None
        if not isinstance(data, dict):
            raise FrameError("bad_value", "the body is not a JSON object")
        for k, v in data.items():  # a JSON string may hold what a line cannot
            if isinstance(v, bool) or not isinstance(v, (str, int, float)):
                raise FrameError("bad_value", f"{k!r}: a value is a string or a number")
            if any(unicodedata.category(ch) in ("Cc", "Zl", "Zp") for ch in k):
                raise FrameError("bad_value", f"{k!r} holds a line break")
            if isinstance(v, str):
                check_text(k, v)
        lines = [f"{k}: {v}" for k, v in data.items()]
    accepted: dict[str, float | str] = {}
    end = False
    for raw in lines:
        line = raw.strip()
        if line == "end":
            end = True
        elif line:
            key, value = _parse(feed, line)
            accepted[key] = value
    return accepted, end


def _parse(feed: Feed, line: str) -> tuple[str, float | str]:
    keyed = _KEYED.match(line)
    key = keyed["key"].strip().strip("*_`\"'").strip() if keyed else ""
    if keyed is not None and key in feed.slots:
        return key, _text(feed, key, keyed["value"].strip())
    figure = feed.figures.get(key)
    match = _LINE.match(line)
    if keyed is None or (match is None and figure is None):
        raise FrameError("bad_value", f"{line[:80]!r} is not `Key: value`")
    if key not in feed.ceilings:
        fed = ", ".join(feed.values)
        raise FrameError(
            "bad_target", f"{key!r} is not fed here; this feed moves {fed}"
        )
    ceiling = feed.ceilings[key]
    if figure is not None:  # the page's own spelling, its declared unit, or bare
        value = figure.read(keyed["value"])
        if value is None:
            spelled = feed.spelled(key)
            raise FrameError(
                "bad_value", f"{line[:80]!r}: {key!r} is written as {spelled}"
            )
        check_domain(key, value, ceiling)
        return key, value
    assert match is not None
    value, unit = float(match["value"]), feed.units[key]
    spelled = feed.spelled(key) + (unit and f" {unit}")
    if match["of"] is not None and (ceiling is None or float(match["of"]) != ceiling):
        raise FrameError(
            "bad_value",
            f"{line[:80]!r}: {key!r} is not out of {match['of']}; it is "
            f"written as {spelled}",
        )
    if match["unit"] not in (None, unit):
        raise FrameError("bad_value", f"{line[:80]!r}: {key!r} is written as {spelled}")
    check_domain(key, value, ceiling)
    return key, value


def _text(feed: Feed, key: str, value: str) -> str:
    """A slot's free text, or one of a chip slot's declared values."""
    check_text(key, value)
    declared = feed.slots[key]
    if declared is not None and value not in declared:
        said = ", ".join(repr(v) for v in declared)
        raise FrameError("bad_value", f"{key!r}: {value!r}; it takes only {said}")
    return value


def check_declared(
    kinds: dict[str, str], values: dict[str, list[str]]
) -> dict[str, tuple[str, ...]]:
    """Each chip slot's declared values, checked as a post's text is: a chip
    takes only these, so a post cannot write a word the agent never did."""
    out: dict[str, tuple[str, ...]] = {}
    for key, listed in values.items():
        name = key.strip()
        if name not in kinds:
            raise FrameError(
                "bad_target", f"values names {key!r}, not a slot of this feed"
            )
        if kinds[name] != "chip":
            raise FrameError(
                "bad_value", f"{key!r} is a {kinds[name]} slot: values is only a chip's"
            )
        for value in listed:
            check_text(name, value)
        out[name] = tuple(dict.fromkeys(listed))
    for name, kind in kinds.items():
        if kind == "chip" and not out.get(name):
            raise FrameError(
                "bad_value",
                f"{name!r} is a chip: declare its values, values={{{name!r}: [...]}}",
            )
    return out


def spelling(value: float, ceiling: float | None, figure: Figure | None) -> str:
    """A bar's value as the page writes it: ``40%``, ``4/10``, or a chart row's
    own spelling (``$1,200``)."""
    if figure is not None:
        return figure.spell(value)
    return f"{value:g}%" if ceiling is None else f"{value:g}/{ceiling:g}"
