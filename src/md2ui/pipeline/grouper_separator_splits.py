"""Cuts a line makes at a separator the author typed.

The second cut, after block splitting: within one block, the ``|`` and ``-``
separators, the inline spacers, the spaced ``:`` column and the ``...`` spring
divide a line into pieces. The separator sets live in ``grouper_inline_marks``.

Precedence is the point of keeping these together: a colon column binds tighter
than a separator.

What a piece *is* — an element, a value, a key — is decided afterwards and
elsewhere; this module only knows where the line divides.
"""

from md2ui.pipeline.grouper_block_splits import _break_node_type
from md2ui.pipeline.grouper_inline_marks import (
    _PASS2_SEPARATORS,
    _ELEMENT_VARIANT_WRAPPERS,
    _SPLIT_WRAP_CHARS,
    _balance_markdown_markers,
    _detect_style_wrap,
    _is_lone_element,
    _reapply_line_wrap,
)
from md2ui.pipeline.grouper_ranges import _make_is_safe
from md2ui.pipeline.grouper_types import NodeType


def _spring_positions(
    content: str, sorted_protected: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    """``(start, end)`` of every SPRING in *content*, in document order.

    A spring is the authored expanding gap ``...`` — three ASCII dots that
    push what is on either side of them toward opposite edges. The spacing
    rule is the ``lenient`` one the row separators already use: a space on
    both sides mid-line, with the start and the end of the string counting
    as boundaries, so a leading ``... A`` and a trailing ``A ...`` are both
    springs while a tight ``wait...what`` is not. Exactly three dots — a
    fourth on either side is an author writing dots, not a spring.

    ``is_safe`` is the same protected-range guard the separator split uses,
    so a spring inside a datapoint, a quote, a paren or a backtick span is
    invisible here exactly as a ``-`` is, and so is an escaped ``\\...``: the
    author's way to write literal dots.

    O(C log R).
    """
    is_safe = _make_is_safe(sorted_protected, content)
    n = len(content)
    out: list[tuple[int, int]] = []
    i = content.find("...")
    while i != -1:
        end = i + 3
        if (
            is_safe(i)
            and not (i > 0 and content[i - 1] == ".")
            and not (end < n and content[end] == ".")
            and (i == 0 or content[i - 1] == " ")
            and (end == n or content[end] == " ")
        ):
            out.append((i, end))
            i = content.find("...", end)
        else:
            i = content.find("...", i + 1)
    return out


def _split_align_regions(
    content: str,
    sorted_protected: list[tuple[int, int]],
) -> list[tuple[str, str]] | None:
    """Split *content* at its springs into ``(region_text, align)`` pairs.

    A spring cuts a line into REGIONS, and a region's position among them is
    its alignment: the first is pushed left, the last right, and anything
    between them centres. One spring therefore reads "left | right", two
    read "left | center | right", and a spring at either end leaves an EMPTY
    region on that side — which is how ``... A ...`` centres and
    ``... A - B`` goes right. Empty regions are dropped as children but
    still take their slot, so the position rule stays a position rule.

    Returns ``None`` when there is no spring, or when the line is nothing
    but springs (``...`` alone says nothing about content that is not
    there). A single non-empty region IS a result — ``... A - B - C`` is one
    region pushed right — which is why this has no "at least two pieces"
    rule of the kind :meth:`_split_separators` needs.

    O(C log R).
    """
    springs = _spring_positions(content, sorted_protected)
    if not springs:
        return None
    bounds = [0] + [e for _, e in springs]
    ends = [s for s, _ in springs] + [len(content)]
    regions = [content[a:b].strip() for a, b in zip(bounds, ends)]
    n = len(regions)
    out: list[tuple[str, str]] = []
    for i, text in enumerate(regions):
        if not text:
            continue  # empty region: it keeps its slot, not a child
        if i == 0:
            align = "left"
        elif i == n - 1:
            align = "right"
        else:
            align = "center"
        out.append((_balance_markdown_markers(text, content, bounds[i]), align))
    return out or None


def _split_separators(
    content: str,
    sorted_protected: list[tuple[int, int]],
) -> list[tuple[str, str]] | None:
    """Split *content* at separators outside *sorted_protected* (caller-sorted).

    One linear pass finds each safe separator, a pipe or a hyphen (or an
    inline spacer) with a space on both sides, and cuts there into flat
    SEGMENT siblings.

    Returns ``(label, text)`` pairs, or ``None`` when fewer than two safe
    segments result. O(C log R).
    """
    is_safe = _make_is_safe(sorted_protected, content)
    n = len(content)

    split_positions = [
        i
        for i, ch in enumerate(content)
        if ch in _PASS2_SEPARATORS
        and is_safe(i)
        and 0 < i < n - 1
        and content[i - 1] == " "
        and content[i + 1] == " "
    ]
    return _emit_split_segments(content, split_positions)


def _drop_orphan_column_colon(piece: str) -> str:
    r"""*piece* without a leading COLUMN colon that has lost its left cell.

    The mirror of the unconditional TRAILING-colon strip in the separation
    walk (``Panelists:`` -> ``Panelists``). A colon with a space on both
    sides is the column separator (:meth:`_split_colon_columns`); when the
    text on its left is consumed by something that cut first, the colon is
    left leading a finished piece, where no scan can see it any more —
    ``_split_colon_columns`` needs a space on the LEFT, and a piece starts
    at index 0. It would then survive into the tree as literal text:

        Status - : Active    segment ': Active'

    (``_Expires:_ : 12/26`` does not reach here: the column separator wins
    over the key-value colon, as ADR-205 says.)

    An empty column cell is nothing, so the separator that named it goes
    too. Applied where PIECES are minted rather than at one call site, so
    every route that can strand a colon is covered by the one rule.

    Only ``": "`` at the start, and a piece that is nothing but a colon.
    A tight ``:value`` is a key-value colon's own business, and an escaped
    ``\:`` never starts a piece with the colon itself.
    """
    s = piece.lstrip()
    if s == ":":
        return ""
    if s.startswith(": "):
        return s[1:].lstrip()
    return piece


def _emit_split_segments(
    content: str,
    split_positions: list[int],
) -> list[tuple[str, str]] | None:
    """Cut *content* at *split_positions* into SEGMENT pieces.

    Marker balancing and whole-line wrap propagation live here so every
    separator route applies them identically.
    """
    if split_positions:
        # Detect a wrapping style on the whole content (e.g. **A | B | C | D**)
        # — used below to propagate the surrounding style onto segments that
        # lack it. Matching runs at both ends are NOT enough: ``_A_ - _B_``
        # and ``___1,293___ - `x` : _vs last month_`` also begin and end with
        # a marker, and re-wrapping their segments doubles markers and mints
        # tiers nobody wrote. :meth:`_detect_style_wrap` applies the
        # same-span rule. The wrap is re-applied with the
        # ACTUAL character (as :meth:`_split_elements` does at its own
        # call), never normalised to ``*``.
        wrap_marker: str | None = None
        wrap_lead = len(content) - len(content.lstrip())
        style_wrap = _detect_style_wrap(
            content,
            wrap_lead,
            len(content.rstrip()),
            _SPLIT_WRAP_CHARS,
        )
        if style_wrap is not None:
            wrap_marker = content[wrap_lead] * style_wrap[0]

        def _segment(raw: str) -> str:
            """Balance a slice's markers, but never CLOSE one around a lone
            element.

            Balancing exists so a slice cut out of ``***a - b***`` keeps its
            style. On a slice that is nothing but an element it invents a
            wrapper the author never wrote — ``***⭐`` becomes ``***⭐***``,
            which the peel then reads as an authored variant. The wrapper
            belongs to the LINE; only a marker already present on BOTH sides
            of the raw slice is the element's own.
            """
            raw = _drop_orphan_column_colon(raw.strip())
            balanced = _balance_markdown_markers(raw, content, prev)
            if balanced == raw:
                return balanced
            for marker in _ELEMENT_VARIANT_WRAPPERS:
                if (
                    balanced.startswith(marker)
                    and balanced.endswith(marker)
                    and len(balanced) > 2 * len(marker)
                ):
                    core = balanced[len(marker) : -len(marker)]
                    if _is_lone_element(core):
                        return core.strip()
                    break
            return balanced

        parts: list[tuple[str, str]] = []
        prev = 0
        for pos in split_positions:
            seg = _segment(content[prev:pos])
            if seg:
                parts.append((NodeType.SEGMENT, seg))
            prev = pos + 1
        last = _segment(content[prev:])
        if last:
            parts.append((NodeType.SEGMENT, last))

        # Propagate wrap style to segments that lack it. A plain
        # ``startswith`` is sufficient *because* the detector applied the
        # same-span rule: a wrap of run length L was rejected if any
        # interior run of that char reached L, so no middle segment can open
        # with L of them. Only the first and last segment — the ones that
        # genuinely carry the wrap — can match.
        if wrap_marker:
            parts = [
                (
                    lbl,
                    _reapply_line_wrap(wrap_marker, seg),
                )
                for lbl, seg in parts
            ]

        if len(parts) >= 2:
            return parts

    return None


def _split_colon_columns(
    content: str,
    sorted_protected: list[tuple[int, int]],
) -> list[tuple[str, str]] | None:
    """Split *content* at spaced colons into STACKED segments.

    ``A : B`` is the authored way to say "these pieces stack" — the vertical
    counterpart of ``|`` / ``-``, which lay their segments out ALONG the
    line. It binds tighter: ``92 : days - ⬇`` is two columns, the first of
    which stacks.

    That precedence is not enforced here but by the callers, all of which go
    through :meth:`_promote_colon_columns` and run AFTER the separator split
    has had its chance, in ``_separate_structured_content_walk``:

    * per segment of a separator split — the tighter-binding case above;
    * on a line no separator and no key-value colon claimed (``A : B``);
    * on a key-value VALUE, both when it split into segments
      (``K: 1,293 - `x` : vs last month``) and when it did not (``K: A : B``).

    A space is required on **both** sides — that is what separates it from a
    key-value colon, which is tight to its key (:meth:`_plain_colon_kv`) —
    and the same protected-range guard applies, so the colon in ``08:30 AM``
    is untouchable on top of already failing the spacing test.

    A piece that is nothing but a rule (``___``) becomes a real
    HORIZONTAL_RULE, the same node a whole ``___`` line mints, so a stack can
    carry a divider between its rows.

    Returns ``(label, text)`` pairs, or ``None`` below two pieces. O(C log R).
    """
    is_safe = _make_is_safe(sorted_protected, content)
    n = len(content)
    positions = [
        i
        for i, ch in enumerate(content)
        if ch == ":"
        and is_safe(i)
        and i > 0
        and content[i - 1] == " "
        and i < n - 1
        and content[i + 1] == " "
    ]
    if not positions:
        return None

    parts: list[tuple[str, str]] = []
    prev = 0
    for pos in positions + [n]:
        start, prev = prev, pos + 1
        raw = _drop_orphan_column_colon(content[start:pos].strip())
        # The break test goes FIRST, on the raw piece, so ``___`` is never
        # "repaired" into ``_____`` as unmatched emphasis markers before it
        # is recognised. The run-aware balancer leaves a piece that is
        # nothing but one marker run alone, so this ordering is
        # belt-and-braces rather than load-bearing — keep it, and its test.
        #
        # Asked through _break_node_type so a stacked column cell means the
        # same thing it would on its own line. A ``***`` stop and a ``;;;``
        # closer are the exceptions: Phase 1 instructions whose passes ran
        # long ago, so here they are only text — minting one now would leak
        # the type into the finished tree.
        kind = _break_node_type(raw) if raw else None
        if kind is not None and kind not in (
            NodeType.SECTION_STOP,
            NodeType.ROW_CLOSER,
        ):
            parts.append((kind, raw))
            continue
        piece = _balance_markdown_markers(raw, content, start)
        if piece:
            parts.append((NodeType.SEGMENT, piece))
    return parts if len(parts) >= 2 else None
