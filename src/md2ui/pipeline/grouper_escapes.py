r"""The escape vocabulary: which characters an author can decline, and what
declining one MEANS.

Markdown carries four escapes here, and they say different things:

    \-  \|  \:  \,  \.   do not SPLIT here     — detection still sees through
    \/  \%  \$              this token is TEXT   — detection stops
    \@  \+  \#  \>           not a CONTROL mark   — detection never cared
    \*                       not MARKUP           — drawn as the character

Every character that splits a line can be declined. They are ASCII, CommonMark
escapes, so no other renderer draws their backslash. A non-ASCII character (a
long dash, an arrow, a dot) splits nothing, so there is nothing to decline.

The distinction is by character, and by POSITION for the separators: one with a
space on each side is separating, and one sitting tight inside a token is not,
so the only thing left for it to decline there is the reading (Mon\-15).

The first three are resolved LATE, and the fourth never by the grouper: its
backslash reaches the node's content and the drawer resolves it. This module says
so once: ``EARLY_ESCAPES`` is the complement of the others, derived from the sets,
so the pattern that resolves escapes in ``preprocess`` and the ones that resolve
them later cannot disagree about which is which.

This is a leaf: a small vocabulary the grouper and the drawer read — the
detection pass in grouper_annotate, the late resolution in grouper_node_reads /
markdown_grouper, the marker runs in grouper_inline_marks and the inline parse
in render_text — and it depends on nothing outside the standard library.
"""

import re
import string


# The characters a SPLIT can consume, each of which an author can decline.
# Escaping one of these is the author saying "this is text, not structure",
# so the backslash is KEPT through the splitting phases (every scan tests
# for it) and stripped at the end, by Phase 6.17. The ASCII ones are the
# CommonMark escapes. The long dashes and the dots (ADR-205) split nothing and
# are deliberately absent: an escape before them is not Markdown, so its
# backslash is drawn, as any other renderer draws it.
ESCAPABLE_SEPARATORS = "-|:,."


# The characters a VALUE is read through, escapable for the opposite reason.
# Escaping one of these says "this token is TEXT" — so detection stops at it
# and the token yields no data point, and therefore no bar, ring, chip, chart
# point or stat tile. That is the mirror of the set above, where the escape
# declines a SPLIT and detection deliberately still sees through it
# (``February 04\, 9:17 PM`` stays one datapoint precisely because it does).
#
# Two escapes, two meanings, told apart by which character carries them —
# rather than one escape whose meaning depends on where it lands, which would
# make the comma case above impossible to spell.
#
# The set is the punctuation the drawn families actually read: ``/`` for the
# ratios (``4\/8``, ``750\/1800 Kcal``), ``%`` for the percentage bar and the
# chart rows built from one (``Elapsed: 45\%``), ``$`` for the currency stat
# tile (``\$412M``). All three are ASCII punctuation, so CommonMark escapes
# them and no other renderer draws the backslash. They are resolved late, by
# Phase 6.17 (``_stamp_finished_tree``), once every scan that needs to see them
# has run; resolved in ``preprocess``, ``12\/26`` would change nothing.
VALUE_ESCAPES = "/%$"


# The characters a later scan consumes as a CONTROL MARK, escapable for a third
# reason again: the escape says "this is not a control mark, it is text".
# Detection never had an opinion about these — a bare ``@ct`` yields no data
# point at all — so neither of the two sets above fits. Joining one of them
# would be actively wrong: ``_declines_the_reading`` reads both, so an escaped
# ``@`` would start suppressing data points in the token around it, which is a
# meaning nobody asked for.
#
# What it shares with the two above, and the only thing this set is read for, is
# WHEN the backslash is resolved: late, by Phase 6.17, so the scan
# that consumes the mark can still see that the author declined it.
#
# ``+`` is the ``+++`` spacer (ADR-203): ``\+++`` is three plus signs of text.
# ``#`` is the heading marker, read twice: by the block parse and, for a heading
# written inside another block (``- # Title``), by Phase 6.18 — so ``\# x`` is
# text that starts with a hash, in a paragraph and in a list item alike.
# ``>`` is the blockquote marker, read by the block parse: ``\> x`` is text that
# starts with an angle, not a quote.
CONTROL_ESCAPES = "@+#>"


# The characters the DRAWER reads as markup, escapable so they are drawn as
# themselves: ``\*`` is a star, not emphasis and not a list marker. Unlike the
# three sets above, the grouper never resolves these: the emphasis is parsed
# again when the text is measured and painted (``render_text.parse_inline_spans``),
# so a backslash removed anywhere before that would hand the drawer a bare marker.
# The backslash stays in the node's content, as the author wrote it, and the
# drawer's parse is the one place it is resolved — measurement and painting
# share it (ADR-400). Every grouper scan that reads a ``*`` as a marker skips one
# behind a backslash (``grouper_inline_marks._marker_runs``).
MARKUP_ESCAPES = "*"


# The escapes resolved LATE (the first three sets), the ones never resolved by
# the grouper (MARKUP_ESCAPES), and the ones preprocess may still resolve early
# (everything else CommonMark escapes).
#
# These two are complements, and they are DERIVED for that reason: a
# hand-typed copy fails silently — add a character to a set here, forget it
# there, and preprocess resolves the escape before the scan that needs it, so
# the feature never sees a declined mark.
#
# CommonMark escapes ASCII punctuation and nothing else, which is what
# ``string.punctuation`` is.
DEFERRED_ESCAPES = ESCAPABLE_SEPARATORS + VALUE_ESCAPES + CONTROL_ESCAPES


EARLY_ESCAPES = "".join(
    sorted(set(string.punctuation) - set(DEFERRED_ESCAPES) - set(MARKUP_ESCAPES))
)


# A code span is literal, as in CommonMark: no backslash escape works inside
# one, so `` `\` `` is a backslash in code and `` `a\-b` `` keeps its backslash.
# A span opens on a whole backtick run and closes on the next run of the same
# length, on the same line, since every source line is its own text here.
_CODE_SPAN = r"(?<!`)(?P<ticks>`++)[^\n]*?[^`\n](?P=ticks)(?!`)"


def escapes_outside_code(chars: str) -> "re.Pattern[str]":
    """A pattern matching each backslash escape of one of *chars*, and each code
    span whole, for :func:`resolve_escape` to keep. One scan, left to right, so
    an escaped backtick (``\\```) never opens a span, as in CommonMark."""
    return re.compile(rf"(?P<code>{_CODE_SPAN})|\\(?P<ch>[{re.escape(chars)}])")


def resolve_escape(m: "re.Match[str]") -> str:
    """What a match of :func:`escapes_outside_code` reads as: the escaped
    character, or the code span unchanged."""
    return m[0] if m["code"] else m["ch"]


def escaped(s: str, i: int) -> bool:
    """True when the character at *i* in *s* is escaped: an odd run of
    backslashes sits right before it, so ``\\*`` is escaped and ``\\\\*`` is a
    backslash and then a star."""
    j = i
    while j and s[j - 1] == "\\":
        j -= 1
    return (i - j) % 2 == 1


def row_cells(line: str) -> list[str]:
    """A table row's cells: its text cut at each pipe that is not escaped.

    GFM keeps an escaped ``\\|`` in its cell as a literal pipe, in a code span
    too, where it is the pipe alone. Anywhere else its backslash stays, a
    declined separator like ``a \\| b`` outside a table, for Phase 6.17 to drop.
    O(C).
    """
    row = line.strip()
    cuts = [i for i, ch in enumerate(row) if ch == "|" and not escaped(row, i)]
    bounds = [-1, *cuts, len(row)]
    cells = [row[a + 1 : b] for a, b in zip(bounds, bounds[1:])]
    if row.startswith("|"):
        cells = cells[1:]
    if len(cells) > 1 and cuts and cuts[-1] == len(row) - 1:
        cells = cells[:-1]
    in_code = re.compile(_CODE_SPAN)
    return [in_code.sub(lambda m: m[0].replace("\\|", "|"), c).strip() for c in cells]


# A backslash at the END of a line is CommonMark's hard break: the one way to
# break a line INSIDE a text (an address, a two-line caption) without splitting
# it, since every source line is its own text. Not a plain
# "\n": that is already the grouper's boundary between texts. Two trailing
# spaces, the other CommonMark spelling, stay ignored: LLMs put them on hundreds
# of stacked `Key: value` rows, which must stay separate lines.
HARD_BREAK = " "


def _declines_the_reading(content: str, backslash: int) -> bool:
    """True when the escape at *backslash* declines its TOKEN's reading rather
    than a split: a value escape anywhere, or a separator escape sitting tight
    between two non-spaces. See :meth:`_value_escape_spans`.
    """
    ch = content[backslash + 1]
    if ch in VALUE_ESCAPES:
        return True
    if ch not in ESCAPABLE_SEPARATORS:
        return False
    before = content[backslash - 1] if backslash else " "
    after = content[backslash + 2] if backslash + 2 < len(content) else " "
    return not before.isspace() and not after.isspace()


def _value_escape_spans(content: str) -> list[tuple[int, int]]:
    """``(start, end)`` of every whitespace-delimited TOKEN holding a value
    escape (:data:`VALUE_ESCAPES`).

    The escape declines the whole token, not just the character it precedes.
    Keeping the backslash in the text the detector reads is enough to stop the
    pattern that spans it — ``12\\/26`` is no longer a ratio — but the halves
    left behind can still match something smaller on their own, and an author
    who declined a bar did not ask for two numbers instead. So the token is
    the unit: a data point overlapping one is dropped.

    A separator escape counts too when it is TIGHT — no space on either side of
    it. That is the same rule read positionally rather than by character: a
    separator only separates with a space around it, so an escape with none is
    not declining a split, and the only thing left for it to decline is the
    reading. It is what spells the day chip's opt-out, ``Mon\\-15``, and it
    leaves every documented separator escape alone, because each of those sits
    against a space: ``Fri, Aug 14 \\- Sun, Aug 16``, ``Cat\\, Dog``,
    ``Key\\: value``, ``\\- not a list``. ``8:00 AM \\- 9:00 AM`` keeps its
    range for exactly that reason.

    A token is delimited by whitespace because that is what an author can see.
    O(C).
    """
    spans: list[tuple[int, int]] = []
    n = len(content)
    i = 0
    while i < n:
        if content[i] == "\\" and i + 1 < n and _declines_the_reading(content, i):
            start = i
            while start > 0 and not content[start - 1].isspace():
                start -= 1
            end = i + 2
            while end < n and not content[end].isspace():
                end += 1
            if spans and spans[-1][0] == start:
                spans[-1] = (start, end)
            else:
                spans.append((start, end))
            i = end
            continue
        i += 1
    return spans
