"""The structural criteria the grouper asks about a line, answered by rules.

``Criterion`` names the independent questions (KEY_VALUE, ELEMENT). Each is
decided from characters so an author can predict it: the comma-list signals,
the styled-key prefixes and the prose shapes.
``SplitCriteria`` is the object the grouper passes around to ask them. Nothing
here is learned (ADR-701).
"""

import re
from enum import Enum, auto


class Criterion(Enum):
    """Independent structural questions the grouper can ask about text."""

    KEY_VALUE = auto()
    ELEMENT = auto()


def _seg_first_alpha(seg: str) -> str | None:
    """Return the first alphabetic character of a segment, or None."""
    for c in seg:
        if c.isalpha():
            return c
    return None


_PROSE_CONNECTORS = re.compile(r",\s+(and|or|but|nor|yet)\b", re.IGNORECASE)
# An internal sentence boundary: a full stop, whitespace, then a capital. One
# definition of "this text is more than one sentence", shared by
# CommaSignalRules rule 3 and by MarkdownGrouper's ``_multi_kv`` guard — a
# paragraph is neither a comma list nor a row of key-value pairs.
#
# The lookbehind is what stops a SPRING counting as a full stop. In
# ``Alpha ... Beta`` the last dot of the ``...`` plus " B" reads exactly like
# ". Capital", so without it an aligned line holding a comma would be judged
# two sentences, therefore prose, and the whole split gated off. A run of dots
# is an ellipsis or a spring; either way it is not a sentence boundary. Prose that genuinely ends
# on an ellipsis is still caught by the trailing-period tell (rule 6).
SENTENCE_BOUNDARY_RE = re.compile(r"(?<!\.)\.\s+[A-Z]")
_MONTH_NAMES = (
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December|Jan|Feb|Mar|Apr|"
    r"Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
)
_DATE_IN_SEG = re.compile(rf"^{_MONTH_NAMES}\s+\d+$", re.IGNORECASE)
_DAY_NAMES = (
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
    r"Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun)\.?"
)
# Spans whose commas are NOT list separators — the comma belongs to a date, a
# number, or something already bracketed off. ``Feb 28, 2020`` is one date, not
# two list items, so a line whose only commas look like this is not a comma list
# at all and must not be judged as one. See _shared_structural_rule.
#
# The date half of this DOES overlap DataPointDetector, which recognises dates
# better than these patterns do (it gets ``January 12-28, 2026`` and
# ``Wednesday, February 5, 2026``, which are missed here). The duplication is
# deliberate: ``detect_all`` costs an order of magnitude more per line than this
# pass, and it would only cover part of the job, since many of the commas masked
# here sit in parens or quotes, which are not datapoints at all (that is
# MarkdownGrouper._bracket_quote_ranges).
_NON_LIST_COMMA_SPAN = re.compile(
    r"\([^)]*\)|\[[^\]]*\]|\"[^\"]*\"|"
    rf"{_DAY_NAMES},\s+{_MONTH_NAMES}(?:\s+\d{{1,2}})?|"
    rf"{_MONTH_NAMES}\s+\d{{1,2}},\s*\d{{4}}|"
    r"\d,\d{3}",
    re.IGNORECASE,
)
# A separator that carries real structure. The spaced colon
# is included because the grouper splits on it too (it stacks its pieces into
# columns); spaces are required on BOTH sides, which is exactly what separates
# it from the tight ``Key:`` of a key-value. The ``...`` spring is included for
# the same reason — the grouper splits on it into aligned regions — but it may
# additionally open or close the line, since a spring against an edge is how
# "push everything the other way" is written.
_STRUCTURAL_SEPARATOR = re.compile(r"\S\s+[|\-–—•:]\s+\S|(?:^|\S\s)\.\.\.(?:\s\S|$)")


def _rule_applicable(
    text: str,
    *,
    element_has_regular_text: bool | None = None,
) -> frozenset[Criterion]:
    """Criteria decided by rules alone.

    ELEMENT owns the span-aware regular-text result supplied by its splitter;
    ``None`` means that question was not asked, so general callers omit the
    criterion.
    """
    criteria = set()
    if element_has_regular_text is False:
        criteria.add(Criterion.ELEMENT)
    return frozenset(criteria)


def _mask_non_list_commas(text: str) -> str:
    """Blank out every comma that sits inside a :data:`_NON_LIST_COMMA_SPAN`."""
    chars = list(text)
    for m in _NON_LIST_COMMA_SPAN.finditer(text):
        for i in range(m.start(), m.end()):
            if chars[i] == ",":
                chars[i] = " "
    return "".join(chars)


_PREPOSITIONS = re.compile(
    r"\b(in|at|on|from|for|with|until|after|before|about|"
    r"around|during|through|into|onto|upon)\b",
    re.IGNORECASE,
)


class CommaSignalRules:
    """Rule-based signal for texts that already have 2+ comma segments.

    Returns 0 for prose and 1 for structured content. The result helps gate
    key-value and datapoint splits; commas themselves are punctuation and are
    never split. Conservative bias: when uncertain, returns 0 (prose).
    """

    @staticmethod
    def has_prose_signal(text: str, segs: list[str]) -> bool:
        """True when one of the UNAMBIGUOUS prose tells is present.

        These are the rules that identify running English rather than merely
        failing to identify a list, so they hold whatever else the line looks
        like. :func:`_shared_structural_rule` consults them before it decides a
        line's commas are incidental — a sentence stays prose even when it
        happens to carry a dash.
        """
        # Rule 1: connector word before a segment ("and", "or", "but", …)
        if _PROSE_CONNECTORS.search(text):
            return True
        # Rule 2: trailing "etc." / "etc"
        if re.search(r",?\s*etc\.?$", text.rstrip(), re.IGNORECASE):
            return True
        # Rule 3: internal sentence boundary inside any segment (". Capital")
        if any(SENTENCE_BOUNDARY_RE.search(seg) for seg in segs):
            return True
        # Rule 5: apostrophe contraction ("we're", "one's", "don't", …)
        if re.search(r"[a-zA-Z]'[a-z]", text):
            return True
        # Rule 6: ends with period (complete sentence)
        if text.rstrip().endswith("."):
            return True
        return False

    def verdict(self, text: str, segs: list[str]) -> int:
        # Rules 1, 2, 3, 5, 6 — the unambiguous prose tells.
        if self.has_prose_signal(text, segs):
            return 0
        # Rule 4: any segment is a month+day date fragment ("March 8", "February 1")
        if any(_DATE_IN_SEG.match(seg) for seg in segs):
            return 0
        # Rule 7: first segment is an intro phrase (2+ words with a preposition)
        first = segs[0] if segs else ""
        if len(first.split()) >= 2 and _PREPOSITIONS.search(first):
            return 0
        # Fallback: uniform capitalization heuristic
        alpha_firsts = [c for seg in segs if (c := _seg_first_alpha(seg)) is not None]
        if alpha_firsts:
            if all(c.isupper() for c in alpha_firsts):
                return 1
            if all(c.islower() for c in alpha_firsts):
                return 1
        return 0  # mixed or unknown → default prose


_comma_signals = CommaSignalRules()

# Plain "Key: value" prefix candidate. Requires at least one letter before the
# colon (so '8:00 AM, ...' does not qualify) and content after. Mirrors the
# structural intent of grouper_node_reads._plain_colon_kv at the criteria level.
_KV_PREFIX_CANDIDATE = re.compile(r"^[^:\n]*[A-Za-z][^:\n]*:\s+\S")

# A short ``Label:`` opening the text or a sentence inside it.
_SENTENCE_LABEL = re.compile(r"(?:^|[.]\s+)[^:\n]{1,40}:\s+\S")


def _is_labelled_paragraph(text: str) -> bool:
    """True for a multi-sentence paragraph whose sentences open with labels.

    ``Top left: … . Bottom left: … . Top right: … .`` is a photo credit — four
    sentences that happen to start with a position label, not four key-value
    pairs. The KV escape below sees only the first ``Top left:`` and, without
    this check, calls the whole thing structured, after which the grouper cuts
    it into leaves with ``is in the [public domain](…). Bottom left`` as a KEY.

    Deliberately requires BOTH signals. One label plus one sentence break is an
    ordinary key with a prose value (``**Note**: These are simulated statistics
    … . For actual trading decisions, …``), which must keep pairing.
    """
    return bool(
        SENTENCE_BOUNDARY_RE.search(text) and len(_SENTENCE_LABEL.findall(text)) >= 2
    )


# Three prose shapes that could otherwise split. Decided from characters, so an
# author can predict them.
#
# A colon that opens a word instead of closing one is not a key-value colon:
# the citation debris GPT leaves after a sentence,
# `... tuning. :contentReference[oaicite:8]{index=8}`, which the key-value
# split cut at `oaicite:`. Only a DETACHED colon counts here: a glued
# `key:value` is never a key-value colon anyway (it needs a space after it),
# and a colon inside a link target (`agent:add`) belongs to the link.
_DETACHED_COLON = re.compile(r"(?:^|\s):[A-Za-z]")
# A mid-line spring inside a sentence is an ellipsis, a pause the author wrote:
# `He paused ... unsure what to say next.` The lowercase word after the dots
# and the full stop at the end are what a row never has.
_ELLIPSIS_PAUSE = re.compile(r"\S \.\.\. [a-z].*[.!?]$")
# A lone trailing `...` after one plain region is a truncation:
# `Loading your dashboard ...`. As a spring it would push the text to the
# edge it already sits at, so nothing is lost by reading it as punctuation.
_TRAILING_TRUNCATION = re.compile(r"^[^.]*\w \.\.\.$")


def _prose_shape(text: str) -> int | None:
    """0 when *text* is one of the prose shapes, else ``None``."""
    t = text.strip()
    if ": " not in t and _DETACHED_COLON.search(t):
        return 0
    if _ELLIPSIS_PAUSE.search(t):
        return 0
    if _TRAILING_TRUNCATION.match(t) and not _STRUCTURAL_SEPARATOR.search(t[:-4]):
        return 0
    return None


def _shared_structural_rule(text: str) -> int | None:
    """Answer the readable rules, or ``None`` when none of them applies.

    KEY_VALUE is the only criterion that reads this vocabulary.
    """
    # Bold/underline key-value prefix (**Key:** value or __Key:__ value)
    # is unambiguously structured regardless of prose/commas in the value.
    if re.match(r"^\*\*[^*:]+:\*\*\s+\S", text):
        return 1
    if re.match(r"^\*\*\*(?!\s)[^*:]+:\*\*\*\s+\S", text):
        return 1
    if re.match(r"^\*(?!\s)[^*:]+:\*\s+\S", text):
        return 1
    if re.match(r"^__[^_:]+:__\s+\S", text):
        return 1
    # A struck key is a disabled key-value, not prose.
    if re.match(r"^~~[^~:]+:~~\s+\S", text):
        return 1
    prose = _prose_shape(text)
    if prose is not None:
        return prose

    text_for_segs = re.sub(r"(\d),(\d{3})", r"\1\2", text)
    segs = [s.strip() for s in text_for_segs.split(",") if s.strip()]
    if len(segs) < 2:
        return None

    # Are those commas actually multiple content segments? In
    # ``🔴 - **User Research on Web** - Feb 28, 2020.7:00 pm`` the only
    # comma belongs to the date; the line's real structure is the dash.
    # Judging it by comma-segment rules answers the wrong question. When
    # masking incidental commas leaves fewer than two segments, a real
    # authored separator remains, and no unambiguous prose tell fires,
    # abstain: the caller reads an unanswered line as structured. The
    # separator itself is decided from characters, not this result.
    if (
        _STRUCTURAL_SEPARATOR.search(text)
        and len(
            [s for s in _mask_non_list_commas(text_for_segs).split(",") if s.strip()]
        )
        < 2
        and not _comma_signals.has_prose_signal(text, segs)
    ):
        return None

    verdict = _comma_signals.verdict(text, segs)
    # The comma-signal rules treat the text as one unit and don't know
    # about "Key:" prefixes — so 'Ingredients: foo, bar, baz.' is
    # rejected as prose because of the trailing period and the mixed
    # capitalization that the 'Ingredients:' first segment introduces.
    # When a clear Key: candidate is present, return structured so the
    # grouper peels the KV. The value is judged on its own at the
    # next gate; without the Key: prefix it falls through these same
    # rules naturally (and stays as a single VALUE if it looks prose-y).
    if (
        verdict == 0
        and _KV_PREFIX_CANDIDATE.match(text)
        # …unless the "key" is just how a paragraph's sentences open.
        # The comma-signal rules called this prose and they are right.
        and not _is_labelled_paragraph(text)
    ):
        return 1
    return verdict


def _key_value_rule(text: str) -> int | None:
    """Answer KEY_VALUE from its readable rules, or ``None`` when they abstain."""
    return _shared_structural_rule(text)


class SplitCriteria:
    """The structural criteria for a text, from rules alone.

    Where the rules abstain the text is structured: a value outside prose is
    structured by design.
    """

    def applicable(self, text: str) -> frozenset[Criterion]:
        """Return the structural criteria applicable to *text*.

        ELEMENT is omitted because this API has no detector spans; its
        splitter asks that rule directly.
        KEY_VALUE is answered by its rules; where they abstain, the text is
        structured.
        """
        criteria = set(_rule_applicable(text))
        if _key_value_rule(text) != 0:
            criteria.add(Criterion.KEY_VALUE)
        return frozenset(criteria)
