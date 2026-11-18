"""Cuts a line makes because part of it IS an element.

Where separator splitting divides a line at a character the author typed
between pieces, this module divides it around pieces that are *themselves*
something: an emoji, a link, a backticked chip, or a run of emphasis.

The element pass is deliberately ONE pass. Emoji, links and chips are the same
kind of thing — an inline element with its own wrapper and variant — and asking
the question once is what stops the three from drifting apart. Its
``Criterion.ELEMENT`` gate receives one piece of evidence,
``_has_regular_text``: any regular text outside the elements makes the whole
line prose and nothing peels.
"""

from md2ui.pipeline.grouper_split_criteria import Criterion, _rule_applicable
from md2ui.pipeline.data_point_detector import DataPointType
from md2ui.pipeline.grouper_block_splits import INLINE_CODE_RE
from md2ui.pipeline.grouper_inline_marks import (
    _detect_style_wrap,
    _link_wrapper_span,
    _muted_element_wrap,
    _quoted_element_spans,
    _wrapped_element_variant,
)
from md2ui.pipeline.grouper_ranges import (
    _element_wrapper_span,
    _make_is_safe,
    _merge_ranges,
)
from md2ui.pipeline.grouper_separator_splits import _PASS2_SEPARATORS
from md2ui.pipeline.grouper_types import NodeType


def _split_emoji_clusters(text: str) -> list[tuple[int, int]]:
    """Split *text* (an EMOJI data point's matched run) into per-visual-emoji
    ``(start, end)`` spans, so each becomes its own node instead of the
    whole run staying one node.

    The EMOJI regex matches a maximal run of consecutive emoji-range
    characters with no separator required (unlike LINK, which always
    matches one ``[label](url)`` at a time), so a run needs re-splitting
    here to get one piece per emoji. A cluster is one visual emoji: two
    consecutive regional-indicator symbols pair into a flag, and a base
    char absorbs any trailing skin-tone modifier / variation selector
    (``️`` in ``↗️``), keycap mark or tag rather than becoming its own node, and a
    joiner takes the emoji after it into the one before (``👨‍💻``). Every
    character in *text* belongs to exactly one cluster — no gaps, no overlaps.
    """
    clusters: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        cp = ord(text[i])
        if 0x1F1E6 <= cp <= 0x1F1FF and i + 1 < n:
            cp2 = ord(text[i + 1])
            if 0x1F1E6 <= cp2 <= 0x1F1FF:
                clusters.append((i, i + 2))
                i += 2
                continue
        start = i
        i += 1
        while i < n and (
            0x1F3FB <= ord(text[i]) <= 0x1F3FF
            or 0xE0020 <= ord(text[i]) <= 0xE007F  # tags: 🏴 + tags is a region's flag
            or ord(text[i]) in (0xFE0E, 0xFE0F, 0x20E3, 0x200D)
        ):
            i += 2 if ord(text[i]) == 0x200D else 1
        i = min(i, n)
        clusters.append((start, i))
    return clusters


def _has_regular_text(content: str, spans: list[tuple[int, int]]) -> bool:
    """Is there REGULAR TEXT on this line, outside every element *span*?

    The whole gate in one question: **any regular text makes the whole line
    prose.** Cut every element occurrence — emoji,
    link, backtick span — out of the line; if anything but whitespace
    survives, the author wrote a sentence that happens to contain elements,
    so nothing peels and each element stays inline (a text-emoji, a
    text-marker, a recolored word run). If nothing survives, the author
    wrote a RUN of elements and a plain space between two of them is
    separation enough — no separator character required. A backtick span is
    an ELEMENT, so ``⭐ `Popular``` has no regular text and is a run.

    An explicitly SEPARATED run still peels out of a prose line — see the
    facing-edge test in :meth:`_split_elements`. That is the authoring
    control: run an element into your prose to keep it inline, separate it
    to make it a badge / chip / button.
    """
    bare = content
    for start, end in reversed(_merge_ranges(spans)):
        bare = bare[:start] + bare[end:]
    return bool(bare.strip())


def _element_applicable(content: str, spans: list[tuple[int, int]]) -> bool:
    """Ask the rule API whether *content* is an element run."""
    return Criterion.ELEMENT in _rule_applicable(
        content,
        element_has_regular_text=_has_regular_text(content, spans),
    )


_ELEMENT_WRAPPER_CHARS = "*_"


def _wrapped_hit(
    content: str,
    start: int,
    end: int,
    lo: int,
    hi: int,
    expected: str,
    chip: bool = False,
) -> tuple[tuple[int, int], str | None, bool]:
    """An emoji's or chip's outer span, its variant, and whether it is muted.

    The span widens over the wrapper that hugs the element, ``~~`` included, so
    ``~~⭐~~`` is one muted badge rather than a strike around a glyph.
    A tilde the muted peel cannot account for (``~⭐~``) is not a wrapper, and
    the span falls back to emphasis alone, as it read before ``~~`` was a state.
    """
    span = _element_wrapper_span(content, start, end, lo, hi, "*_~", 5)
    peeled, muted = _muted_element_wrap(content[span[0] : span[1]])
    if "~" in peeled.replace(expected.strip(), "", 1):
        span = _element_wrapper_span(
            content, start, end, lo, hi, _ELEMENT_WRAPPER_CHARS, 3
        )
        peeled, muted = content[span[0] : span[1]], False
    return span, _wrapped_element_variant(peeled, expected, chip=chip), muted


def _element_hits(
    content: str,
    data_points: list[dict],
    lo: int,
    hi: int,
) -> list[dict]:
    """Every inline ELEMENT occurrence in *content*, in authored order.

    ONE list covering all three kinds — EMOJI, LINK, INLINE_CODE — which is
    what lets a single pass see a mixed run (``⭐ [Buy](/b) `Sale```) as one
    run. Each hit carries

    * ``label``   — the ``NodeType`` the piece becomes;
    * ``start`` / ``end`` — the OUTER span, widened over an emphasis
      wrapper that HUGS this element (:meth:`_element_wrapper_span`), so a
      run of wrapped elements does not stop at the first marker;
    * ``text``    — the piece's node content;
    * ``variant`` — the wrapper's variant, by length, via
      :func:`_wrapped_element_variant`. A LINK carries its wrapper in its
      own content instead (``_classify_link_content`` reads it later).

    Backticks are matched here rather than being a ``DataPointType``
    because a value split would peel mid-text occurrences
    too, and a mid-text span has to stay an inline marker.

    A hit fully inside another — a chip or emoji in a link label,
    ``[`➕`](/x)`` — is dropped: the outer element owns its label. So is a hit
    the author QUOTED (:func:`_quoted_element_spans`), which is how an element is
    declined and read as text instead.
    """
    hits: list[dict] = []
    for dp in data_points:
        kind = dp["type"]
        if kind == DataPointType.LINK:
            span = _link_wrapper_span(content, dp["start"], dp["end"], lo, hi)
            hits.append(
                {
                    "label": NodeType.LINK,
                    "start": span[0],
                    "end": span[1],
                    "text": content[span[0] : span[1]].strip(),
                    "variant": None,
                }
            )
        elif kind == DataPointType.EMOJI:
            glyph = content[dp["start"] : dp["end"]].strip()
            span, variant, muted = _wrapped_hit(
                content, dp["start"], dp["end"], lo, hi, glyph
            )
            hits.append(
                {
                    "label": NodeType.EMOJI,
                    "start": span[0],
                    "end": span[1],
                    "text": glyph,
                    "variant": variant,
                    "muted": muted,
                }
            )
    # Cheap guard: most leaves hold no backtick at all, and this pass sees
    # every leaf in the tree.
    for m in INLINE_CODE_RE.finditer(content) if "`" in content else ():
        span, variant, muted = _wrapped_hit(
            content, m.start(), m.end(), lo, hi, m.group(), chip=True
        )
        hits.append(
            {
                "label": NodeType.INLINE_CODE,
                "start": span[0],
                "end": span[1],
                "text": content[m.start() + 1 : m.end() - 1].strip(),
                "variant": variant,
                "muted": muted,
            }
        )
    # A QUOTED element is the author declining the element reading, so it never
    # becomes a hit — ``"📞"`` is a glyph in the text, ``"[Docs](/d)"`` an inline
    # span, ``"`code`"`` a marker. Filtering here rather than in
    # ``_peel_elements`` is what makes the three agree: that filter only sees
    # DATA POINTS, so a backtick span (matched above, never a data point) would
    # slip past it. It also re-scans the leaf's CURRENT content, where
    # ``node.paren_quote_ranges`` was computed before Phase 6.055 consumed the
    # tier underscores and shifted every offset.
    #
    # The test is "wrapped by a quote PAIR", never "inside a protected range":
    # ``_bracket_quote_ranges`` counts ``(...)`` and a backtick span as ranges of
    # their own, so the looser test would suppress every chip in the document.
    quoted = _quoted_element_spans(content)
    if quoted:
        hits = [
            h
            for h in hits
            if not any(s < h["start"] and h["end"] < e for s, e in quoted)
        ]
    hits.sort(key=lambda h: (h["start"], -h["end"]))
    out: list[dict] = []
    for h in hits:
        if out and h["start"] >= out[-1]["start"] and h["end"] <= out[-1]["end"]:
            continue
        out.append(h)
    return out


def _piece(hit: dict) -> tuple[str, str, str | None, bool]:
    """The split piece an element *hit* becomes: its muted state rides along."""
    return hit["label"], hit["text"], hit["variant"], hit.get("muted", False)


def _split_elements(
    content: str,
    node_label: str,
    data_points: list[dict],
) -> list[tuple] | None:
    """Split *content* into inline ELEMENTS and the text around them.

    The single element pass, over emoji + links + backtick spans at once
    (:meth:`_element_hits`). Separate passes per kind would nest each other's
    leftovers, so ``⭐ [Buy](/b) `Sale``` would come out flat or nested by
    pass order; one pass has no order to get wrong.

    Two outcomes, from one ``Criterion.ELEMENT`` question, whose evidence is
    :meth:`_has_regular_text`:

    * **Run.** No regular text on the line, so every element is a peer and a
      plain space between two of them is separation enough. ``⭐ 🚀``,
      ``[a](/a) [b](/b)``, ``` `a` `b` ``` and ``⭐ [Buy](/b) `Sale``` all
      emit the same flat shape, in authored order.
    * **Prose.** Regular text is present, so the line is a sentence and its
      elements stay inline — UNLESS a boundary run is EXPLICITLY SEPARATED
      from the prose by a ``_PASS2_SEPARATORS`` character on the middle's
      facing edge. That escape is the authoring control this rule exists
      for: run an element into your prose to keep it inline, separate it to
      make it a badge / chip / button. Each side is tested independently, so
      one line may separate its leading run and run straight into its
      trailing one. A comma is prose punctuation and deliberately does not
      count.

    Style wraps are unwrapped first (``***⭐ Popular***``) so an element at
    the start of the INNER text is still at a boundary, and the remainder is
    re-wrapped with the same marker characters — never normalised to ``*``.

    Returns ``(label, text, variant)`` pieces in authored order, an element's
    with its muted state fourth (:func:`_piece`), or ``None`` when nothing peels.
    """
    lead_offset = len(content) - len(content.lstrip())
    trail_end = len(content.rstrip())
    style_wrap = _detect_style_wrap(content, lead_offset, trail_end, "*_")
    if style_wrap is not None:
        marker_len, inner_lead, inner_trail = style_wrap
    else:
        marker_len, inner_lead, inner_trail = 0, lead_offset, trail_end
    marker_char = content[lead_offset] if marker_len else "*"

    hits = [
        h
        for h in _element_hits(content, data_points, inner_lead, inner_trail)
        if h["start"] >= inner_lead and h["end"] <= inner_trail
    ]
    if not hits:
        return None

    def wrapped(text: str) -> str:
        m = marker_char * marker_len
        return f"{m}{text}{m}" if marker_len else text

    # One element IS the whole content → relabel in place. A LINK keeps its
    # style wrap (an italic link stays styled); an emoji or chip consumes
    # it, so the wrap it just swallowed becomes the element's variant.
    if (
        len(hits) == 1
        and hits[0]["start"] == inner_lead
        and hits[0]["end"] == inner_trail
    ):
        hit = hits[0]
        if hit["label"] == NodeType.LINK:
            return [(hit["label"], wrapped(hit["text"]), None)]
        variant = hit["variant"] or (
            _wrapped_element_variant(
                content[lead_offset:trail_end],
                content[inner_lead:inner_trail],
                chip=hit["label"] == NodeType.INLINE_CODE,
            )
            if marker_len
            else None
        )
        return [(hit["label"], hit["text"], variant, hit.get("muted", False))]

    spans = [(h["start"], h["end"]) for h in hits]
    inner = content[inner_lead:inner_trail]
    if _element_applicable(inner, [(a - inner_lead, b - inner_lead) for a, b in spans]):
        # A RUN: emit every element, plus any non-whitespace gap between
        # them (a lone separator the upstream split left in place) as text.
        result: list[tuple] = []
        cursor = inner_lead
        for hit in hits:
            gap = content[cursor : hit["start"]].strip()
            if gap:
                result.append((node_label, wrapped(gap), None))
            result.append(_piece(hit))
            cursor = hit["end"]
        tail = content[cursor:inner_trail].strip()
        if tail:
            result.append((node_label, wrapped(tail), None))
        return result if len(result) > 1 else None

    # PROSE. Only an explicitly separated boundary run peels out of it.
    n = len(hits)
    leading: list[dict] = []
    cursor = inner_lead
    i = 0
    while i < n and hits[i]["start"] == cursor:
        leading.append(hits[i])
        cursor = hits[i]["end"]
        while cursor < inner_trail and content[cursor].isspace():
            cursor += 1
        i += 1

    trailing: list[dict] = []
    tcursor = inner_trail
    j = n - 1
    while j >= i and hits[j]["end"] == tcursor:
        trailing.append(hits[j])
        tcursor = hits[j]["start"]
        while tcursor > inner_lead and content[tcursor - 1].isspace():
            tcursor -= 1
        j -= 1
    trailing.reverse()

    if not leading and not trailing:
        return None

    mid_start = leading[-1]["end"] if leading else inner_lead
    mid_end = trailing[0]["start"] if trailing else inner_trail
    middle = content[mid_start:mid_end].strip()
    seps = _PASS2_SEPARATORS
    # An escaped separator (``\-``) declines the division, read through the
    # same predicate every separator scan uses.
    is_safe = _make_is_safe([], content)
    raw = content[mid_start:mid_end]
    first = mid_start + len(raw) - len(raw.lstrip())
    last = mid_start + len(raw.rstrip()) - 1
    if not middle or middle[0] not in seps or not is_safe(first):
        leading = []
    if not middle or middle[-1] not in seps or not is_safe(last):
        trailing = []
    if not leading and not trailing:
        return None
    mid_start = leading[-1]["end"] if leading else inner_lead
    mid_end = trailing[0]["start"] if trailing else inner_trail
    middle = content[mid_start:mid_end].strip()

    result = [_piece(h) for h in leading]
    if middle:
        result.append((node_label, wrapped(middle), None))
    result += [_piece(h) for h in trailing]
    return result if result else None
