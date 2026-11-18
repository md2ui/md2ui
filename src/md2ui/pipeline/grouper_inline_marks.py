"""Markdown markers on a piece of a line.

Every inline splitter cuts a line somewhere, and a cut lands in the middle of
markup as easily as between words. This module is the vocabulary those cuts are
written in: which character runs are markers at all, how a piece is repaired
once a cut has stranded half a span, and which wrapper — if any — a span carries.

It answers questions about *markup*, never about structure: nothing here builds
a node, and nothing here decides where a cut goes. That is the layer above.
"""

import re
from functools import lru_cache

from md2ui.pipeline.data_point_detector import EMOJI_CHAR_PATTERN
from md2ui.pipeline.grouper_block_splits import INLINE_CODE_RE
from md2ui.pipeline.grouper_escapes import MARKUP_ESCAPES, escaped
from md2ui.pipeline.grouper_ranges import _element_wrapper_span
from md2ui.pipeline.grouper_types import (
    _CHIP_UNDERSCORE_VARIANT_BY_LEN,
    _ELEMENT_VARIANT_BY_LEN,
    _LINK_CONTENT_RE,
    _strip_wrap,
)


# Separator character sets — single source of truth for every separator
# decision (the splitter, the first-separator scan, and the pure-emoji
# separator guard). Here with the rest of the marker vocabulary, not in
# grouper_separator_splits, so a reader of the SET (generator_units) does not
# import the splitter. To add a new separator, edit only these sets.


# Line separators split content into flat SEGMENT siblings.
#
# ASCII `-` and `|` only. A separator has to be DECLINABLE, and the only way to
# decline one is to escape it (`ESCAPABLE_SEPARATORS`, `\-` `\|` `\:` `\,` `\.`)
# — which CommonMark allows for ASCII punctuation and nothing else. `\—` is not
# an escape in any Markdown tool; it renders as a literal backslash. So an em or
# en dash could split a line and the author had no way to say "not here",
# exactly the complaint that took the datapoint split apart (ADR-205).
#
# Most spaced ` — ` / ` – ` lines are prose sentences ("Let's start simple —
# I'll guide you"), which a dash split would shred; most of the rest are date
# ranges, which the DATE_RANGE datapoint already protects as one span.
_LINE_SEPARATORS = frozenset("|-")


# ` +++ ` / ` ++++ ` / ` +++++ ` inside a line: a row separator whose gap is
# blank space of that step (ADR-203). The scans here read one character per
# separator, so ``grouper_spacers`` swaps each spaced token for one of these
# private characters first — and swaps back any the scans left in the text.
INLINE_SPACERS = {"\ue140": "+++", "\ue141": "++++", "\ue142": "+++++"}


# All Pass-2 separators (space required on both sides). The dots `•` `·` `∙` `‧`
# are text, not separators (ADR-205).
_PASS2_SEPARATORS = _LINE_SEPARATORS | frozenset(INLINE_SPACERS)


# Markers longest-first, so ``***`` is never read as ``*`` + ``**``.
_ELEMENT_VARIANT_WRAPPERS = ("***", "___", "**", "__", "*", "_")


# Characters a link wrapper can be built from: emphasis (``*`` and its
# CommonMark synonym ``_``) plus the disabled state (``~~``).
_LINK_WRAPPER_CHARS = "*_~"


def _is_lone_emoji(s: str) -> bool:
    """True when *s* is nothing but emoji glyphs (the same test the link
    classifier uses for a pure-emoji label)."""
    stripped = s.replace("‍", "").replace(" ", "")  # ZWJ joiners
    return bool(stripped) and bool(EMOJI_CHAR_PATTERN.fullmatch(stripped))


def _is_lone_element(s: str) -> bool:
    """True when *s* is nothing but ONE inline element — emoji, chip or link."""
    t = s.strip()
    return bool(t) and bool(
        _is_lone_emoji(t) or INLINE_CODE_RE.fullmatch(t) or _LINK_CONTENT_RE.match(t)
    )


def _reapply_line_wrap(marker: str, piece: str) -> str:
    """Give *piece* the LINE's *marker*, unless *piece* is a lone element.

    Every splitter re-wraps the pieces it cuts so the surrounding style survives
    the cut. That is right for text and datapoints and wrong for a lone element:
    the wrapper belongs to the LINE, not to the element inside it, and the peel
    would read it as an authored variant nobody wrote —
    ``**💵 $29.99**`` would come out as a Tertiary 💵.

    A wrapper already CLOSED into the piece is stripped, not merely left alone:
    the separator splitter balances its slices (``***⭐`` -> ``***⭐***``) before
    this is reached, so a "don't add it" test would pass the manufactured
    wrapper straight through.
    """
    inner = piece.strip()
    if (
        inner.startswith(marker)
        and inner.endswith(marker)
        and len(inner) > 2 * len(marker)
    ):
        core = inner[len(marker) : -len(marker)]
        return core if _is_lone_element(core) else piece
    if _is_lone_element(inner):
        return piece
    return f"{marker}{piece}{marker}"


def _wrapped_element_variant(
    original: str, expected: str, chip: bool = False
) -> str | None:
    """The variant a whole-content emphasis wrapper selects, else ``None``.

    *original* is the leaf's content BEFORE the peel; *expected* is what the
    wrapper must contain for the wrapper to belong to this element — the glyph
    for an emoji, the backticked span for a chip. Requiring an exact match is
    the whole point: in ``**🗓 Calendar**`` the wrapper spans the line, not the
    emoji, so the emoji stays Primary and the markers ride on with the text.

    *chip* selects the chip-only underscore family (Quinary / Senary /
    Septenary); for every other element ``_`` stays a synonym of ``*``.
    """
    s = original.strip()
    want = expected.strip()
    for marker in _ELEMENT_VARIANT_WRAPPERS:
        inner = _strip_wrap(s, marker)
        if inner is not None and inner.strip() == want:
            if chip and marker[0] == "_":
                return _CHIP_UNDERSCORE_VARIANT_BY_LEN[len(marker)]
            return _ELEMENT_VARIANT_BY_LEN[len(marker)]
    return None


def _muted_element_wrap(original: str) -> tuple[str, bool]:
    """*original* without the ``~~`` that mutes an element, and whether it had one.

    ``~~`` is the one muted state of every element, never a strike
    drawn on it. It may sit outside the variant's wrapper or inside it —
    ``~~*⭐*~~`` and ``*~~⭐~~*`` are both a muted Secondary — exactly as a link
    reads ``~~*[x](/y)*~~``. What comes back still carries the variant's wrapper
    for :func:`_wrapped_element_variant` to read.
    """
    s = original.strip()
    inner = _strip_wrap(s, "~~")
    if inner is not None:
        return inner, True
    for marker in _ELEMENT_VARIANT_WRAPPERS:
        mid = _strip_wrap(s, marker)
        core = _strip_wrap(mid, "~~") if mid is not None else None
        if core is not None:
            return f"{marker}{core}{marker}", True
    return s, False


_MARKER_RUN_RE = re.compile(r"([*_~`])\1*")


def _marker_runs(s: str) -> list[tuple[int, str, int]]:
    """``(start, char, length)`` for every maximal marker run in *s*.

    Reading whole RUNS is what separates a standalone ``_`` from part of
    ``__`` / ``___`` — a substring test cannot, and would mint Display tiers
    out of ``__x_``.

    Three runs are not markers at all and never enter the pairing:

    * a ``~`` run that is not exactly two long — ``**~420 ppm**`` is a
      number, and cutting that line leaves a segment ending ``**~``;
    * an INTRAWORD ``_``, alphanumeric on both sides. CommonMark exempts
      exactly this so ``message_schemas`` and ``snake_case`` are identifiers,
      not emphasis. ``*`` has no such exemption (``a*b*c`` is emphasis), so
      the rule is asymmetric on purpose;
    * anything inside a COMPLETE inline-code span. Otherwise a chip whose
      text contains an asterisk leaves that star unpaired, the flanking rule
      reads it as a closer and prepends an opener, the piece stops being a
      whole-content span, and the backticks are drawn as text. Same principle, and
      the same pattern, as :meth:`_split_images`: markup inside a code span
      is literal text.

      COMPLETE is what keeps this safe. The balancer's real job is repairing
      a span a split CUT IN HALF — an opening backtick with no closer, or a
      closer with no opener — and neither half can match
      ``INLINE_CODE_RE``, so every one of those repairs is untouched.

    And one character is not a marker: an ESCAPED star (``MARKUP_ESCAPES``),
    whose backslash stays in the content for the drawer to resolve. A run behind
    an odd number of backslashes loses its first star, so ``\\*x\\*`` has no runs
    for the balancer to pair or repair, and ``\\**x**`` keeps a one-star run.
    """
    spans = [m.span() for m in INLINE_CODE_RE.finditer(s)] if "`" in s else []
    runs: list[tuple[int, str, int]] = []
    for m in _MARKER_RUN_RE.finditer(s):
        if any(a <= m.start() and m.end() <= b for a, b in spans):
            continue
        ch, start, length = m.group()[0], m.start(), m.end() - m.start()
        if ch in MARKUP_ESCAPES and escaped(s, start):
            start, length = start + 1, length - 1
            if not length:
                continue
        if ch == "~" and length != 2:
            continue
        if ch == "_":
            before = s[m.start() - 1] if m.start() else ""
            after = s[m.end()] if m.end() < len(s) else ""
            if before.isalnum() and after.isalnum():
                continue
        runs.append((start, ch, length))
    return runs


def _run_can_open_close(s: str, pos: int, ch: str, length: int) -> tuple[bool, bool]:
    """Whether the marker run at *pos* in *s* can open and whether it can close.

    CommonMark's delimiter flanking, ``_`` included: the text's edges count
    as whitespace, and a ``_`` that flanks both ways may open only after
    punctuation and close only before it. One answer for every reader, so
    pairing a whole line and repairing a cut piece cannot disagree about
    which side a run belongs to.
    """

    def kind(c: str) -> str:
        return "space" if not c or c.isspace() else "punct" if not c.isalnum() else ""

    before = kind(s[pos - 1] if pos else "")
    after = kind(s[pos + length] if pos + length < len(s) else "")
    left = after != "space" and (after != "punct" or before != "")
    right = before != "space" and (before != "punct" or after != "")
    if ch != "_":
        return left, right
    opens = left and (not right or before == "punct")
    closes = right and (not left or after == "punct")
    return opens, closes


@lru_cache(maxsize=256)
def _literal_runs(line: str) -> frozenset[int]:
    """Start offsets of the marker runs *line* leaves unpaired: plain text.

    A split must not change what a piece says, so a run that had no partner
    in the whole line (``nora.vasquez_@example.com``) is text in every piece cut
    from it. Pairing follows CommonMark's flanking rules, ``_`` included, so
    a run that cannot open or close stays out of the stack.
    """

    stacks: dict[str, list[int]] = {}
    literal: set[int] = set()
    for pos, ch, length in _marker_runs(line):
        opens, closes = _run_can_open_close(line, pos, ch, length)
        stack = stacks.setdefault(ch, [])
        if closes and stack:
            stack.pop()
        elif opens:
            stack.append(pos)
        else:
            literal.add(pos)
    for stack in stacks.values():
        literal.update(stack)
    return frozenset(literal)


def _one_marker_family(s: str) -> str:
    """*s* with every ``_`` marker run rewritten as the ``*`` of the same length.

    ``_x_`` and ``*x*`` are the SAME markup — CommonMark treats the two
    characters as exact synonyms — so nothing that reads a line's structure
    may answer differently for one than for the other (ADR-201: styling is
    not structure). The styled-key rules match the ``*Key:*`` spelling and
    would otherwise miss ``_Key:_``.

    Normalising, not stripping: the markers themselves carry signal (a bold
    key is a structural tell), and stripping every marker would read much
    styled prose as structured.

    Runs come from :meth:`_marker_runs`, so the intraword exemption holds and
    ``snake_case`` is untouched. Display-side only — this never reaches node
    content, which keeps the author's own characters.
    """
    if "_" not in s:
        return s
    out = list(s)
    for pos, ch, length in _marker_runs(s):
        if ch == "_":
            out[pos : pos + length] = "*" * length
    return "".join(out)


def _balance_markdown_markers(s: str, source: str | None = None, at: int = 0) -> str:
    """Repair the style markers on a piece a split cut out of a line.

    Run-aware, so ``***`` / ``___`` are first class and a standalone ``_``
    is never read as part of ``__``. THE PAIRING RULE LIVES HERE AND NOWHERE
    ELSE: runs of the same character pair up in order (0-1, 2-3, …) and
    **the opener is authoritative** — a closer of a different length is
    normalised to the opener's length rather than the other way round. That
    is what stops a mis-cut from minting a tier nobody wrote: ``__x_`` must
    not come out ``__x___``, a Display tier invented from a Lead one (see
    :meth:`_detect_underscore_wrap`).

    A leftover unpaired run is repaired according to how it *flanks*
    (:func:`_run_can_open_close`): one that can only close gets its opener
    prepended (``ppm (2024)**``, and ``Beta**.``, whose closer the cut
    stranded before punctuation); any other that can open gets its closer
    appended. A run that could do either, ``*`` between two letters, is read
    as an opener — CommonMark leaves that to the rest of the line, which the
    piece no longer has.

    A run with whitespace on both sides can flank in NEITHER direction, so
    CommonMark can never pair it and the renderer would draw the characters
    literally — cutting ``**$100 Milestone:** Crossed on…`` at the colon
    leaves the value ``** Crossed on…``, whose ``**`` is the key's closer
    stranded on the wrong side. That is dead text and is dropped, the
    leading-side mirror of :meth:`_drop_orphan_marker`. Only a run at the
    very START or END is dropped, and never one that is the whole piece: a
    bare ``___`` is a horizontal rule, a lone ``**`` is a split artifact its
    caller inspects, and a whitespace-flanked ``___`` in the MIDDLE is the
    rule that ``A | B : ___ : C | D`` draws between two stacked columns.

    *source* is the line *s* was cut from, found at or after *at*: a run it
    left unpaired is text, not a marker the cut broke (:func:`_literal_runs`).
    """
    runs = _marker_runs(s)
    offset = source.find(s, at) if source is not None else -1
    if offset >= 0:
        literal = _literal_runs(source)
        runs = [r for r in runs if offset + r[0] not in literal]
    if not runs:
        return s
    by_char: dict[str, list[tuple[int, str, int]]] = {}
    for run in runs:
        by_char.setdefault(run[1], []).append(run)

    edits: list[tuple[int, int, str]] = []
    prepend = append = ""
    for ch, lst in by_char.items():
        for i in range(0, len(lst) - 1, 2):
            (_, _, olen), (cpos, _, clen) = lst[i], lst[i + 1]
            if clen != olen:  # the opener wins
                edits.append((cpos, cpos + clen, ch * olen))
        if len(lst) % 2:
            pos, _, length = lst[-1]
            opens, closes = _run_can_open_close(s, pos, ch, length)
            if closes and not opens:
                prepend = ch * length + prepend  # a closer: open it
            elif opens:
                append += ch * length  # an opener, or either: close it
            elif length != len(s) and (pos == 0 or pos + length == len(s)):
                edits.append((pos, pos + length, ""))  # dead text: drop it
    for start, end, rep in sorted(edits, reverse=True):
        s = s[:start] + rep + s[end:]
    return (prepend + s.strip() + append) if edits else prepend + s + append


def _drop_orphan_marker(s: str) -> str:
    """Drop a trailing style marker left with no partner.

    Cutting a datapoint out of ``**Key** **94% say YES**`` leaves the text
    segment ``**Key** **`` — that final ``**`` opened the *second* bold
    span, whose closer went with the datapoint. ``_balance_markdown_markers``
    never repairs a run flanked by whitespace on its inner side, so it keeps
    the orphan and the renderer draws it.

    Two conditions identify a stray *opener*: an odd number of occurrences
    (a balanced segment always has an even count), and whitespace before
    the run. The second is what separates this from the mirror case — in
    ``ppm (2024)**`` the trailing ``**`` is a *closer* whose opener left
    with the datapoint, and balancing must restore the opener rather than
    have the closer stripped here.
    """
    for m in ("**", "__", "~~", "*", "_", "`"):
        if s.endswith(m):
            head = s[: -len(m)]
            if head and head[-1].isspace() and s.count(m) % 2 == 1:
                return head.rstrip()
            break
    return s


def _detect_dp_style_marker(
    content: str,
    dp_start: int,
    dp_end: int,
    lo: int,
    hi: int,
) -> str | None:
    """Return the markdown style marker immediately wrapping a single dp,
    or ``None``.

    Checks longer markers first (``___``, ``***``, ``**``, ``__``, ``~~``) so
    that ``**$50**`` matches ``**`` rather than ``*``.  Bounds-checked against
    ``[lo, hi]`` (the enclosing inner-content range) so a dp at the edge
    of the content cannot reach past it.

    A candidate must also be the WHOLE delimiter run on both sides, so
    ``___$12,480.55___`` reports ``___`` (the display tier) instead of
    peeling ``__`` off a three-underscore run and leaving a stray ``_`` for
    Phase 6.055 to read as a different tier.
    """
    for m in ("___", "***", "**", "__", "~~", "*", "_", "`"):
        ml = len(m)
        if dp_start - ml < lo or dp_end + ml > hi:
            continue
        if not (
            content[dp_start - ml : dp_start] == m
            and content[dp_end : dp_end + ml] == m
        ):
            continue
        ch = m[0]
        before = dp_start - ml - 1
        after = dp_end + ml
        if before >= lo and content[before] == ch:
            continue
        if after < hi and content[after] == ch:
            continue
        return m
    return None


# Run lengths that can OPEN a wrap, per marker character. ``*`` and ``_``
# carry the italic / bold / bold-italic ladder. ``~`` is a marker only when
# doubled — a lone ``~`` is "approximately" (``~420 ppm``) and ``~~~`` is
# nothing. A code span opens on ONE backtick: ``` ``x`` ``` is
# a legal span whose interior is opaque, and splitting inside it is never
# right.
_WRAP_RUN_LENGTHS = {"*": (1, 2, 3), "_": (1, 2, 3), "~": (2,), "`": (1,)}


# The marker set the STRUCTURAL splitter honours (_split_separators), which asks "is this whole line one span?". Wider
# than the ``"*_"`` used by the boundary-dp and inline-code passes, which ask
# a different question — which VARIANT does this wrapper select? — and for
# which a backtick wrap IS the element being peeled.
_SPLIT_WRAP_CHARS = "*_~`"


def _detect_style_wrap(
    content: str, lead_offset: int, trail_end: int, chars: str = "*"
) -> tuple[int, int, int] | None:
    """Detect if ``content[lead_offset:trail_end]`` is wrapped in style markers.

    Handles bold-italic (``***``), bold (``**``), and italic (``*``).
    Returns ``(marker_len, inner_start, inner_end)`` or ``None``.

    *chars* is the set of marker characters to consider; it defaults to
    ``"*"`` so every existing caller — notably the datapoint splitter — keeps
    its exact behaviour. Callers that also honour the CommonMark synonym
    pass ``"*_"``. Only ONE character can open a wrap: the closing run must
    be the same char as the opening one.

    Which run LENGTHS open a wrap is per character
    (:data:`_WRAP_RUN_LENGTHS`), not a flat 1-3: widening *chars* to ``~``
    and ``` ` ``` without that would read ``~420 - ~600`` as a strike wrap
    and split the interior of a ``` ``code span`` ```.

    Matching runs at both ends are not enough — the two runs must be the
    *same* span. A line that is a sequence of emphasis spans
    (``*A* *B*``, ``**Bold** and **more**``) also starts and ends with a
    marker, and treating it as one wrap shifts the effective boundaries
    inside the first and last marker: callers then strip a wrapper that was
    never there and re-wrap the leftover, doubling the markers. So an
    interior run of ``*`` long enough to close the opener disqualifies it.

    Deliberately conservative: ``*a *b* c*`` is one wrap under CommonMark
    (the interior delimiters pair with each other) but is rejected here.
    Getting that right needs full delimiter flanking; the cost of being
    wrong this way is only that content is left unwrapped.
    """
    inner = content[lead_offset:trail_end]
    n = len(inner)
    if not n or inner[0] not in chars:
        return None
    ch = inner[0]
    lead_stars = 0
    while lead_stars < n and inner[lead_stars] == ch:
        lead_stars += 1
    if lead_stars not in _WRAP_RUN_LENGTHS.get(ch, ()):
        return None
    trail_stars = 0
    while trail_stars < n and inner[n - 1 - trail_stars] == ch:
        trail_stars += 1
    if lead_stars != trail_stars or n <= 2 * lead_stars:
        return None
    middle = inner[lead_stars : n - lead_stars]
    if any(
        len(run.group()) >= lead_stars
        for run in re.finditer(re.escape(ch) + "+", middle)
    ):
        return None
    return (lead_stars, lead_offset + lead_stars, trail_end - lead_stars)


def _wrap_is_authored(line: str, run_len: int, inner: str) -> bool:
    """Whether the source *line* itself wraps *inner* in *run_len* underscores.

    A piece cut out of a span gets its wrapper back from the cut's repair, so
    by the time it reaches the tier pass it looks exactly like a span the
    author wrapped on its own. Only the unsplit line can tell them apart:
    ``_A_ | B`` wrote ``_A_``, ``_A | B_!`` did not, and styling must survive
    the split unchanged. A key's colon may sit inside its wrapper
    (``__Key:__ value`` is the key ``__Key__``).

    Matched by text, not position: in ``_A | B_ | _A_`` the repaired first
    piece still finds the authored ``_A_`` further along. Accepted — pieces
    carry no source offsets, and the line has to repeat itself to hit it.
    """
    run = "_" * run_len
    pattern = rf"(?<!_){run}\s*{re.escape(inner)}\s*:?\s*{run}(?!_)"
    return re.search(pattern, line) is not None


def _link_wrapper_span(
    content: str, start: int, end: int, lo: int, hi: int
) -> tuple[int, int]:
    """Widen a LINK span to include its own emphasis / state wrapper.

    The detector's LINK span covers ``[label](url)`` and never the markers
    around it, so a run of styled links (``*[a](/x)* *[b](/y)*``) reads to
    the boundary peel as links separated by non-whitespace and stops after
    the first. Counting the matching marker runs on each side turns
    ``*[a](/x)*`` into one unit, which both keeps the run going and lets
    :func:`_classify_link_content` see the wrapper and pick the variant.

    The marker set is ``*``, ``_`` (its CommonMark synonym) and ``~`` (the
    disabled state), and the two sides may mix them — ``~~***[a](/x)***~~``
    is a disabled Quaternary, which is why the cap is 5 rather than 3. What
    keeps this from over-consuming is ``k = min(left, right)``: the widening
    is only ever as long as the *shorter* side, so an unbalanced run can
    never swallow text that was not a wrapper.

    Clamped to ``[lo, hi]`` — the caller's style-wrap-adjusted bounds — so
    a genuine whole-content wrap is never consumed twice: there the markers
    sit outside ``lo``/``hi``, the span comes back unchanged, and the
    caller's own re-wrap handles it.
    """
    return _element_wrapper_span(content, start, end, lo, hi, _LINK_WRAPPER_CHARS, 5)


# The quote pairs that can carry the TEXT reading of an element. Exactly the
# pairs ``_bracket_quote_ranges`` already protects, which is what makes the
# construct cheap: a quoted element is never peeled, so only the quotes need
# consuming. Typographic ``“ ”`` are absent on purpose — they are not
# protection ranges, so admitting them here would change splitting for every
# curly-quoted line, not just for elements.
_QUOTE_CHARS = ('"', "'")

# What may sit between a quoted element and the edge of its line without costing
# it the boundary: whitespace, and the emphasis/strike markers. Not punctuation
# and not letters — those are prose, and prose keeps its own quotes.
_BOUNDARY_SKIP = " \t*_~"


def _element_text_span(content: str) -> tuple[int, int]:
    """The ``[lo, hi)`` the element pass works in: *content* stripped of
    surrounding whitespace and of every whole-content emphasis/tier wrapper.

    Mirrors the opening of :func:`_split_elements`, which needs the wrapper's
    length and character as well and so computes it inline. Kept separate rather
    than shared because this caller wants only the bounds, and threading two
    unused return values through the peel's hot path to save four lines is the
    wrong trade.

    The marker set adds ``~`` to the peel's ``*_``, so ``~~"[Docs](/d)"~~``
    reaches its quotes instead of drawing them. It loses nothing by doing so: a
    declined link is an inline span, and a struck inline link is already drawn as
    an ordinary one — the disabled paint belongs to the button. Only this
    function widens the set, and it only ever acts on a leaf that turns out to
    hold a quoted element, so nothing else sees the difference.
    """
    lo = len(content) - len(content.lstrip())
    hi = len(content.rstrip())
    # Peeled until nothing is left to peel, so a COMBINED wrapper reaches its
    # quotes too: ``~~**"📞"**~~`` is a strike around a bold around an element,
    # and _detect_style_wrap reads one wrapper per call. Each pass shrinks the
    # span by at least two, so this terminates on its own.
    while (wrap := _detect_style_wrap(content, lo, hi, "*_~")) is not None:
        _, lo, hi = wrap
    return lo, hi


def _quoted_element_spans(content: str) -> list[tuple[int, int]]:
    """Every ``(start, end)`` quote pair in *content* that wraps EXACTLY one bare
    element and sits at a BOUNDARY of the text.

    This is the author declining the element reading: ``"📞"`` is a glyph in the
    surrounding text rather than a badge, ``"[Docs](/d)"`` an inline link span
    rather than a button, ``"`code`"`` a marker rather than a chip. The style
    still comes from the context, so the ``*``/``_`` ladders keep their ordinary
    meanings around it — ``___"📞"___`` is a Display-tier glyph.

    Two conditions, and both are load-bearing:

    * **Exactly one bare element** (:func:`_is_lone_element`). ``"This is prose"``
      holds words, so its quotes are the author's and stay drawn.
    * **At a boundary** — nothing but whitespace and MARKERS between the pair and
      one end of the text. ``Press "📞" to dial`` quotes an emoji mid-sentence,
      where the quotes are punctuation the author typed; removing them would be
      reducing the document's content to improve its look (ADR-500).

      Markers are skipped because a wrapper that starts a line without spanning
      it is not caught by :func:`_element_text_span`, which reads whole-content
      wraps only. ``**"📞"** Call now`` is the emoji at the head of its line in
      bold, and testing whitespace alone would draw both quotes. What keeps
      this from swallowing the mid-sentence case is that ``Press`` is letters,
      not markers.

    The bounds come from :func:`_element_text_span`, never from the caller, and
    that is what keeps the two halves of this feature honest: the peel declines an
    element here, and Phase 6.17 consumes its quotes there, so both have to agree
    about where a boundary is. ``_split_elements`` reads only ``*_`` and only one
    wrapper deep, so its bounds would leave ``~~**"📞"**~~`` declined but never
    stripped.

    The single-quote guard is the one ``_bracket_quote_ranges`` uses: an opening
    ``'`` attached to a letter is an apostrophe, so ``don't`` and ``Alice's 📞``
    open no span.

    Returns the OUTER spans (the quote characters included), sorted.
    Time: O(C), Space: O(P) for the P pairs found.
    """
    # Every leaf that reaches the peel asks this, and almost none holds a quote.
    # Checked before _element_text_span, whose _detect_style_wrap loop is the
    # expensive half.
    if '"' not in content and "'" not in content:
        return []
    lo, hi = _element_text_span(content)
    # Every pair that wraps one bare element, BEFORE any boundary test: a pair's
    # neighbours decide whether it is at a boundary, so they all have to be known
    # first.
    found: list[tuple[int, int]] = []
    for quote in _QUOTE_CHARS:
        start = -1
        for i in range(lo, hi):
            if content[i] != quote:
                continue
            if start < 0:
                if quote == '"' or i == 0 or not content[i - 1].isalnum():
                    start = i
                continue
            if _is_lone_element(content[start + 1 : i]):
                found.append((start, i + 1))
            start = -1
    if not found:
        return []
    found.sort()
    # Blank every candidate out, so one quoted element counts as skippable when
    # the NEXT one asks whether it is at a boundary. That is what makes a RUN
    # work: in ``"⭐" "❤️" "💬"`` only the first has an empty prefix and only the
    # last an empty suffix, so testing the raw text would decline the middle of
    # every run and leave its quotes drawn.
    blanked = list(content)
    for start, end in found:
        blanked[start:end] = " " * (end - start)
    scratch = "".join(blanked)
    return [
        (start, end)
        for start, end in found
        if not scratch[lo:start].strip(_BOUNDARY_SKIP)
        or not scratch[end:hi].strip(_BOUNDARY_SKIP)
    ]


def quoted_element_edits(content: str) -> list[tuple[int, int, str]]:
    """Consume the quote pair around a boundary-quoted bare element — Phase 6.17.

    Runs with the separator backslashes, and for the same reason: the quotes had
    to stay visible through every splitting phase, because being inside a quote
    pair is exactly what kept the element from being peeled
    (``_peel_elements``/:func:`_element_hits`). Once nothing can split any more
    they are debris that would be drawn. Stripping them any EARLIER re-exposes a
    bare element to the peel, which is the badge the author just declined.

    Returned as edits for ``grouper_content_edits.edit_content``, so the node's
    data points follow the removed quotes.

    Time: O(C), Space: O(C).
    """
    return [
        edit
        for start, end in _quoted_element_spans(content)
        for edit in ((start, start + 1, ""), (end - 1, end, ""))
    ]
