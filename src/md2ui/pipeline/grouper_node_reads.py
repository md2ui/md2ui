"""Questions asked about a node's content, before anything cuts it.

The separation walk decides what to do with a line by asking a series of
questions about it: is this the head of a spring key-value, which separator
comes first, which offsets are protected, what does this content look like once
its data points are taken out. This module is those questions.

Everything here is READ-ONLY. Nothing takes a node and returns nothing; nothing
mints an id; nothing touches ``children``. That is the line, and it is what makes
the module safe to call from anywhere: an answer cannot leave the tree in a
half-changed state. The functions that act on the answers live above.
"""

from md2ui.pipeline.grouper_escapes import (
    DEFERRED_ESCAPES,
    escapes_outside_code,
    resolve_escape,
)
from md2ui.pipeline.grouper_inline_marks import (
    _SPLIT_WRAP_CHARS,
    _balance_markdown_markers,
    _detect_style_wrap,
    _one_marker_family,
)
from md2ui.pipeline.grouper_ranges import _colon_is_glued, _make_is_safe
from md2ui.pipeline.grouper_separator_splits import (
    _PASS2_SEPARATORS,
    _drop_orphan_column_colon,
    _spring_positions,
)
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.grouper_value_splits import _BOUNDARY_DP_TYPES


# Every escape that is resolved LATE, after each scan that needs to read it:
# the separator escapes (``\-`` "do not split here") and the value escapes
# (``\/`` "this token is text"). Built from the two sets so the vocabulary has
# one home; the meanings differ, the point at which the backslash stops being
# markup does not.
LATE_ESCAPE_RE = escapes_outside_code(DEFERRED_ESCAPES)


def late_escape_edits(node: MarkdownGroupNode) -> list[tuple[int, int, str]]:
    """The edits that resolve *node*'s late escapes. Code is literal, a block or
    a span alike, so it keeps every backslash."""
    if node.type in (NodeType.CODE_BLOCK, NodeType.INLINE_CODE):
        return []
    found = LATE_ESCAPE_RE.finditer(node.content)
    return [(m.start(), m.end(), m["ch"]) for m in found if m["ch"]]


def _extract_key_from_prefix(text: str) -> str | None:
    """Return the key string if *text* looks like a bare key prefix (e.g.
    ``"**Cover:**"``, ``"*Label:*"``, ``"Key:"``), otherwise ``None``.

    Handles bold/italic/strikethrough markers that wrap the trailing colon:
      ``"**Cover:**"``         →  ``"**Cover**"``
      ``"*Label:*"``           →  ``"*Label*"``
      ``"~~Strikethrough:~~"`` →  ``"~~Strikethrough~~"``
      ``"Key:"``               →  ``"Key"``

    An escaped colon is the author keeping it: ``"Key\\:"`` and
    ``"**Cover\\:**"`` are not bare keys.
    """
    s = text.strip()
    for m in ("***", "___", "~~", "**", "__", "*", "_"):
        if s.endswith(m) and len(s) > len(m):
            inner = s[: -len(m)]
            if inner.endswith(":"):
                if inner.endswith("\\:"):
                    return None
                candidate = inner[:-1].rstrip() + m
                key = _balance_markdown_markers(candidate)
                return key or None
    if s.endswith(":"):
        if s.endswith("\\:"):
            return None
        key = _balance_markdown_markers(s[:-1].rstrip())
        return key or None
    return None


def _row_separator_chars(
    content: str, sorted_protected: list[tuple[int, int]]
) -> list[str]:
    """The ROW separators :meth:`_split_separators` split at, in gap order.

    Mirrors that scan exactly — a separator needs a space on both sides — so
    the characters reported are the ones the split actually consumed,
    positionally aligned with the gaps between the pieces it produced.

    An entry is every separator in its GAP, in order: `A | +++ B` has one gap
    holding both, since the empty piece between them is dropped. Separators
    before the first piece or after the last belong to no gap. So `A +++ +++ B`
    keeps both spacers, which then add up (ADR-203).

    Display-only (``separator_chars`` ▸ ## Separators). O(C log R).
    """
    is_safe = _make_is_safe(sorted_protected, content)
    n = len(content)
    strict: list[str] = []
    at: list[int] = []
    for i, ch in enumerate(content):
        if not is_safe(i) or ch not in _PASS2_SEPARATORS:
            continue
        if i > 0 and content[i - 1] == " " and i < n - 1 and content[i + 1] == " ":
            strict.append(ch)
            at.append(i)
    # Group the separators by the gap they sit in: a piece that is empty (only
    # spaces, or the column colon the split drops) is no piece at all.
    gaps: list[str] = []
    pending, seen = "", False
    bounds = [-1, *at, n]
    for k in range(len(bounds) - 1):
        piece = content[bounds[k] + 1 : bounds[k + 1]].strip()
        if piece and piece != ":":
            if seen:
                gaps.append(pending)
            seen, pending = True, ""
        if k < len(strict) and seen:
            pending += strict[k]
    return gaps


def _protected_ranges(
    node: "MarkdownGroupNode",
) -> list[tuple[int, int]]:
    """Non-overlapping protected ranges for *node*, in its own coordinates.

    A datapoint range that sits entirely inside a paren/quote range is
    dropped: it is already covered, and keeping both would produce
    overlapping intervals, which breaks the binary search in
    :meth:`_make_is_safe`'s ``is_safe``.
    """
    pq = node.paren_quote_ranges
    dp_ranges = [(dp["start"], dp["end"]) for dp in node.data_points]
    if not pq:
        return dp_ranges
    return [
        r for r in dp_ranges if not any(ps <= r[0] and r[1] <= pe for ps, pe in pq)
    ] + pq


def _classification_text(content: str, data_points: list[dict]) -> str:
    """The text the split criteria judge: :meth:`_boundary_trimmed_text`
    with the separator escapes resolved.

    A backslash is markup, not content, and every other stage is escape-blind
    (:meth:`_detect_through_markers` strips it before the detector matches,
    :meth:`_make_is_safe` honours it in each separator scan). Left visible, a
    trailing ``\\`` breaks the month+day tell in the comma-signal rules, so
    ``February 04\\, 9:17 PM`` and its plain twin would get two verdicts, and
    therefore two different node types.

    Resolved on the RESULT rather than up front: the trim below indexes
    ``data_points`` offsets against the original content, and dropping
    characters first would shift every one of them.

    The two emphasis families are then folded into one
    (:meth:`_one_marker_family`) for the same reason the wrap is dropped
    below: which of ``_`` and ``*`` an author reached for is styling, and
    styling does not decide structure. Without it ``_Expires:_ 12/26`` would
    be judged prose and returned from the gate whole, while its ``**`` and
    unmarked twins split into a key and a value.
    """
    text = LATE_ESCAPE_RE.sub(
        resolve_escape,
        _boundary_trimmed_text(content, data_points),
    )
    # A whole-content emphasis wrap is MARKUP, not content — exactly the
    # class of thing the escape strip above removes for the same reason.
    # Phase 2.16 consumes an underscore wrap before this gate ever sees it,
    # so `___75°___` arrives as `75°` and is judged structured, while
    # `***75°***` arrives with its markers and is judged prose. The same
    # line then comes out as two different trees depending on which
    # emphasis family the author used.
    stripped = text.strip()
    wrap = _detect_style_wrap(stripped, 0, len(stripped), _SPLIT_WRAP_CHARS)
    if wrap is not None:
        _, lo, hi = wrap
        inner = stripped[lo:hi].strip()
        if inner:
            return _one_marker_family(inner)
    return _one_marker_family(text)


def _boundary_trimmed_text(content: str, data_points: list[dict]) -> str:
    """Return *content* with the leading/trailing boundary **runs**
    (EMOJI / LINK, consecutive dps separated only by whitespace) trimmed
    off, for a stable split-criteria signal — the same run rule the final
    peel (:meth:`_split_elements`) uses.

    Boundary emoji/link are peeled in the final pass, so the structural
    gate would otherwise see emoji-prefixed strings — and the criteria
    flip many prose lines (``"…heading 1…"``, ``"+3 points"``) to
    structured when an emoji leads, fragmenting titles. Trimming a whole
    run (not just the outermost dp) keeps the gate and the peel agreeing
    on what is decoration: ``"prose [a](u) [b](u)"`` must classify as
    ``"prose"``, not as ``"prose [a](u)"`` (which reads as structured and
    unlocks inner-datapoint splits that cut the prose). Dps joined by
    non-whitespace (`` | ``, `` - ``) break the run, so separator strips
    keep their pills for classification — and that holds at the run's OUTER
    edge too, not only between two dps: a boundary dp the author explicitly
    separated (``days - ⬇``) is a segment, and trimming it would leave the
    separator dangling, which is what reads as prose. Style-wrap (``*``/``**``/``***``)
    is unwrapped first so a wrapped leading emoji is still detected.
    Falls back to *content* if trimming leaves nothing.
    """
    if not data_points:
        return content
    lead = len(content) - len(content.lstrip())
    trail = len(content.rstrip())
    style = _detect_style_wrap(content, lead, trail)
    if style is not None:
        marker_len, lo, hi = style
    else:
        marker_len, lo, hi = 0, lead, trail
    boundary = _BOUNDARY_DP_TYPES
    n = len(data_points)
    # Leading run: boundary dps anchored at the inner start, each gap
    # whitespace-only.
    i = 0
    pos = lo
    while (
        i < n and data_points[i]["type"] in boundary and data_points[i]["start"] == pos
    ):
        pos = data_points[i]["end"]
        while pos < hi and content[pos].isspace():
            pos += 1
        i += 1
    new_lo = data_points[i - 1]["end"] if i else lo
    # Trailing run: symmetric, never consuming a dp already taken above.
    j = n - 1
    pos = hi
    while (
        j >= i and data_points[j]["type"] in boundary and data_points[j]["end"] == pos
    ):
        pos = data_points[j]["start"]
        while pos > new_lo and content[pos - 1].isspace():
            pos -= 1
        j -= 1
    new_hi = data_points[j + 1]["start"] if j < n - 1 else hi
    if new_lo == lo and new_hi == hi:
        return content  # no boundary dp trimmed → classify content as-is
    inner = content[new_lo:new_hi].strip()
    if not inner:
        return content
    # A trailing boundary run right after a key colon is the KV *value*,
    # not decoration ("Key: [link] [link]") — classify the full content so
    # the KV path stays gated on the real shape instead of a bare "Key:".
    if new_hi != hi and inner.rstrip("*").rstrip().endswith(":"):
        return content
    # …and a run behind an explicit SEPARATOR is a segment, not decoration.
    # Trimming it stands the separator up on its own ("days - ⬇" ▸ "days -"),
    # and that dangling "-" is exactly what reads as prose — so the gate skips
    # the very split that would have consumed it, and the peel then leaves the
    # separator stranded in the text. Classify the line whole and let the
    # splitter decide. Same set the splitter uses, so the two agree on what a
    # separator is.
    core = inner.strip("*").strip()
    if core and (core[0] in _PASS2_SEPARATORS or core[-1] in _PASS2_SEPARATORS):
        return content
    # …and so is a run the author pushed away with a SPRING. Trimming it
    # stands the "..." up at the edge ("Transaction History ... [`…`](/more)"
    # ▸ "Transaction History ..."), which reads as a prose truncation — a
    # verdict about a line the spring has already cut in two. (A spring
    # springs on prose too, so this does not decide whether the line
    # splits; it keeps the criteria judging the line the author wrote.)
    # Read with the splitter's own
    # helper, so the two agree on what a spring is (three dots, spaced); an
    # edge-anchored match needs no protected ranges, since a spring inside a
    # quote or a datapoint can never touch an edge of the stripped text.
    edge_springs = _spring_positions(inner, [])
    if edge_springs and (edge_springs[0][0] == 0 or edge_springs[-1][1] == len(inner)):
        return content
    return f"{'*' * marker_len}{inner}{'*' * marker_len}" if marker_len else inner


def _plain_colon_kv(
    content: str,
    protected: list[tuple[int, int]] | None = None,
) -> list[tuple[str, str]] | None:
    """Split *content* at the first safe colon into KEY / VALUE.

    Uses the same binary-search guard as ``_split_kv_styled`` so colons
    inside data-point ranges (e.g. ``08:30 AM``) are never used as the
    split point.

    A key-value colon is **tight to its key**, so a colon with a space
    before it is not one — it is the column separator
    (:meth:`_split_colon_columns`), and this pass must leave it alone or the
    column split can never see it. It is also followed by a space: a glued
    ``key:value`` is text like ``10:30``, ``H:25°`` and ``3:1``. So ``Key: value`` splits here; ``Key : value`` falls
    through to the column split, and ``Key:value`` and ``Key :value`` are
    neither.

    Returns ``[(NodeType.KEY, left), (NodeType.VALUE, right)]`` or ``None``.
    """
    # The shared predicate rather than a private copy, so an escaped
    # ``Key\: value`` is not a pair for the same reason it is not a split.
    is_safe = _make_is_safe(sorted(protected or []), content)

    for i, ch in enumerate(content):
        if ch == ":" and is_safe(i) and not (i > 0 and content[i - 1] == " "):
            if _colon_is_glued(content, i):
                break  # glued to what follows: text, not a key's colon
            left = _balance_markdown_markers(content[:i].strip(), content)
            # A COLUMN colon the key-value cut has just stranded at the head
            # of the value (``Key: : v``) is dropped here rather than left
            # for the column split, which cannot see a colon at index 0.
            right = _balance_markdown_markers(
                _drop_orphan_column_colon(content[i + 1 :].strip()), content, i + 1
            )
            if left and right and right.strip("*_`"):
                return [(NodeType.KEY, left), (NodeType.VALUE, right)]
            break  # safe colon found but one side empty (or only markers) — no split
    return None
