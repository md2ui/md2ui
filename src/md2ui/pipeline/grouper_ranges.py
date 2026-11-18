"""Character-range arithmetic: which parts of a line may not be cut.

Every splitter in the grouper asks the same question before it cuts a line: is
this offset inside something that must stay whole? A bracketed link target, a
quoted phrase, an emphasis wrapper, the middle of a word. This module owns that
question and nothing else.

``_bracket_quote_ranges`` finds the protected spans, ``_merge_ranges`` /
``_merge_pq`` combine them, and ``_make_is_safe`` turns the result into the
predicate the splitters actually call.

**Pure text arithmetic: no AST, no nodes, no grouper state.** That boundary is
enforced by a contract in pyproject.toml, and it is why ``_protected_ranges``,
which takes a ``MarkdownGroupNode``, lives in ``grouper_node_reads`` instead.
"""

import re


_BRACKET_QUOTE_CHARS = re.compile(r"[()\"`']")


def _is_intraword(text: str, start: int, end: int) -> bool:
    """True when the run at ``[start, end)`` sits BETWEEN two alphanumerics.

    CommonMark: an underscore run flanked by word characters can neither
    open nor close emphasis. That is why ``snake_case_name`` is literal text
    rather than ``snake case name``, and why ``_the user_id field_`` is one
    muted span with the identifier intact. Such a run is not a marker, so it
    must not disqualify a whole-leaf wrap.

    Deliberately NOT extended to ``*``: intraword asterisks really do open
    and close emphasis, so only the underscore family gets this test.
    """
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return before.isalnum() and after.isalnum()


def _partition_ranges(
    parent_content: str,
    ranges: list[tuple[int, int]],
    result: list[tuple],
) -> list[list[tuple[int, int]]]:
    """Partition (start, end) spans to per-child lists with adjusted offsets.

    Mirrors :meth:`_partition_data_points` for plain range tuples.  Each
    range is assigned to the first child whose text span fully contains it;
    start/end are remapped to child-local coordinates.  Ranges spanning a
    split boundary are silently dropped.

    Time: O(C + P) where C = len(parent_content), P = len(ranges).
    """
    if not ranges:
        return [[] for _ in result]

    child_ranges: list[tuple[int, int] | None] = []
    search_from = 0
    for _label, text in result:
        if not text:
            child_ranges.append(None)
            continue
        idx = parent_content.find(text, search_from)
        if idx == -1:
            stripped = text.strip()
            idx = parent_content.find(stripped, search_from)
            length = len(stripped)
        else:
            length = len(text)
        if idx >= 0:
            child_ranges.append((idx, idx + length))
            search_from = idx + length
        else:
            child_ranges.append(None)

    partitioned: list[list[tuple[int, int]]] = [[] for _ in result]
    for ps, pe in ranges:
        for i, cr in enumerate(child_ranges):
            if cr is None:
                continue
            cs, ce = cr
            if ps >= cs and pe <= ce:
                partitioned[i].append((ps - cs, pe - cs))
                break

    return partitioned


def _merge_pq(
    ranges: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Merge overlapping (start, end) intervals in *ranges*.

    Used to normalise paren/quote ranges so they are non-overlapping
    (e.g. ``("quoted")`` produces a paren span and a quote span that
    overlap and must be merged into a single span).

    Time: O(P log P) where P = len(ranges).
    """
    if not ranges:
        return ranges
    merged = [sorted(ranges)[0]]
    for s, e in sorted(ranges)[1:]:
        ms, me = merged[-1]
        if s <= me:
            merged[-1] = (ms, max(me, e))
        else:
            merged.append((s, e))
    return merged


def _bracket_quote_ranges(
    content: str,
    dp_protected: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Return (start, exclusive_end) spans for balanced ``()``, ``"..."``,
    `` `...` ``, and ``'...'`` groups.

    Characters at positions inside *dp_protected* are skipped so that
    parens/quotes that are already part of a data-point span (e.g. a
    markdown link URL ``[text](url)`` detected as a LINK data point) do
    not produce false protection ranges.

    Call :meth:`_merge_pq` on the result to collapse any nested overlaps
    (e.g. ``("quoted")`` yields both a paren span and a quote span).

    Single quotes are recognised only when the opening ``'`` is **not**
    immediately preceded by an alphanumeric character, which excludes
    apostrophes in contractions (``don't``) and possessives (``Alice's``).
    """
    sorted_dp = sorted(dp_protected)

    def in_dp(pos: int) -> bool:
        lo, hi = 0, len(sorted_dp) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            s, e = sorted_dp[mid]
            if s <= pos:
                if e > pos:
                    return True
                lo = mid + 1
            else:
                hi = mid - 1
        return False

    ranges: list[tuple[int, int]] = []
    # Every node's content passes through here, often more than once, and most
    # of it holds none of the five characters, so only their positions are
    # visited -- one pass, not one per kind. Parentheses nest; each quote kind
    # pairs with the next one of its kind.
    depth = 0
    paren_start = -1
    quote_start = {'"': -1, "`": -1, "'": -1}
    for match in _BRACKET_QUOTE_CHARS.finditer(content):
        i = match.start()
        if sorted_dp and in_dp(i):
            continue
        ch = content[i]
        if ch == "(":
            if depth == 0:
                paren_start = i
            depth += 1
        elif ch == ")":
            if depth > 0:
                depth -= 1
                if depth == 0:
                    ranges.append((paren_start, i + 1))
        elif quote_start[ch] >= 0:
            ranges.append((quote_start[ch], i + 1))
            quote_start[ch] = -1
        # An opening ' preceded by an alphanumeric is an apostrophe (don't,
        # Alice's), never a quote.
        elif ch != "'" or i == 0 or not content[i - 1].isalnum():
            quote_start[ch] = i

    return sorted(ranges)


def _make_is_safe(sorted_protected: list[tuple[int, int]], content: str = ""):
    """Return a predicate ``is_safe(pos)`` — True when *pos* lies outside
    every protected interval. Binary search over the already-sorted,
    non-overlapping intervals: O(log R) per call. The caller sorts once and
    shares the predicate across scans.

    A BACKSLASH-ESCAPED character is unsafe too. ``\\-`` is the author
    saying "this dash is text, not structure", and this is the one place
    that has to know it: every scan that decides whether a character
    separates goes through here, so the escape reaches all of them —
    the separator split, the spring, the colon column, the key-value colon
    and the tie-break — without each growing its own test. The backslash
    itself is stripped later, by Phase 6.17 (``_stamp_finished_tree``).
    """

    def is_safe(pos: int) -> bool:
        if pos > 0 and content[pos - 1 : pos] == "\\":
            return False
        lo, hi = 0, len(sorted_protected) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            s, e = sorted_protected[mid]
            if s <= pos:
                if e > pos:
                    return False  # inside this interval
                lo = mid + 1
            else:
                hi = mid - 1
        return True

    return is_safe


def _colon_is_glued(content: str, i: int) -> bool:
    """True when the colon at *i* runs straight into the next word.

    A key's closing markers may sit between them: ``**Key:** value`` is
    spaced, ``H:25°`` is glued.
    """
    j = i + 1
    while j < len(content) and content[j] in "*_~`":
        j += 1
    return j < len(content) and not content[j].isspace()


def _element_wrapper_span(
    content: str,
    start: int,
    end: int,
    lo: int,
    hi: int,
    chars: str,
    cap: int,
) -> tuple[int, int]:
    """Widen an element span over the emphasis wrapper that HUGS it.

    One helper for all three element kinds — a link (``~~***[a](/x)***~~``,
    five marker chars deep), an emoji (``*⭐*``) and a chip (``*`a`*``) —
    so a run of wrapped elements is one run rather than stopping at the
    first marker, and every kind reads its variant off the same span.

    ``k = min(left, right)`` is what keeps this from over-consuming: the
    widening is only ever as long as the SHORTER side, so a wrapper that
    spans the whole LINE (``**⭐ Popular**``) is not mistaken for one
    hugging the element. Clamped to ``[lo, hi]`` — the caller's
    style-wrap-adjusted bounds — so a genuine whole-content wrap is never
    consumed twice.
    """
    left = 0
    while left < cap and start - left - 1 >= lo and content[start - left - 1] in chars:
        left += 1
    right = 0
    while right < cap and end + right < hi and content[end + right] in chars:
        right += 1
    k = min(left, right)
    return (start - k, end + k) if k else (start, end)


def _merge_ranges(
    ranges: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Overlapping/adjacent spans merged into disjoint ones, left to right.

    Cutting spans out of a string one by one only stays sound while they do
    not overlap — an emoji inside a quoted region would otherwise shift the
    indices of the cut that follows it.
    """
    out: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out
