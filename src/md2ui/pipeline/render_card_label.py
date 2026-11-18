"""The name a link card's click reports, from the words it shows.

A card is the one target whose label is not written as a label: it is read off
the card's own words (its first heading, or all of its text). Split from
``render_actions``, which numbers the card and reports the name.
"""

from __future__ import annotations

from md2ui.pipeline.render_text import parse_inline_spans, plain_link_label


# Leaves a link card's name never reads: they draw no words.
_NOT_WORDS = frozenset(
    {"image", "horizontal_rule", "content_break", "spacer", "bullet_point"}
    | {"drawing_element", "code_block"}
)


def card_label(nd: dict) -> str:
    """The name a link card's click reports, from the words it shows.

    A card is named by its title when it has one — its first heading, the name a
    reader would give it, kept short where a body would run on — and otherwise by
    all of its text, as a plain link is named by its label: a caption, or the
    words the link wraps. Images and controls show no words and add none.
    """
    heading = _first_heading(nd)
    words: list[str] = []
    _card_words(heading if heading is not None else nd, words)
    return " ".join("".join(words).split())


def _first_heading(nd: dict) -> dict | None:
    for child in nd.get("children", []):
        if str(child.get("type", "")).startswith("heading"):
            return child
        found = _first_heading(child)
        if found is not None:
            return found
    return None


def _card_words(nd: dict, words: list[str]) -> None:
    if nd.get("type") in _NOT_WORDS:
        return
    children = nd.get("children", [])
    if not children:
        if nd.get("type") == "link":
            words.append(plain_link_label(nd))
        else:
            words.extend(span[0] for span in parse_inline_spans(nd.get("content", "")))
    for child in children:
        _card_words(child, words)
    words.append(" ")
