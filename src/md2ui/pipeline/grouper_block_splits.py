"""Block-level splitting: where a document divides into blocks.

The coarsest cut the grouper makes, and the first: blank lines end a block, a
newline inside one does not, a list is a run of markers, a blockquote is a run of
``>`` lines, an image on its own line is its own block.

A thematic break is here for the same reason: ``---`` / ``___`` / ``***`` are
whole lines that mint a node, and ``_break_node_type`` is the single place that
maps a break's spelling to its meaning.

Everything here works on **whole lines**. The finer cuts — separators, colon
columns, key-values, inline elements — happen afterwards, inside a block, and
live elsewhere. That order is the dependency: block splitting knows nothing about
inline splitting, and this module has no import from it.
"""

import re

from md2ui.pipeline.grouper_escapes import HARD_BREAK, resolve_escape
from md2ui.pipeline.grouper_types import _LIST_MARKER_RE, ITEM_DIVIDER, NodeType
from md2ui.pipeline.render_text import LINK_DESTINATION

# Separator chars that can be orphaned at the boundary of a text part after
# an inline split (e.g. bold split leaves "About 60 cookies |" or "- Lala ...").
_ORPHAN_SEP_TRAIL = re.compile(r"\s*[|—–]\s*$|\s+-\s*$")
_ORPHAN_SEP_LEAD = re.compile(r"^\s*[|—–]\s*|^-\s+")

# A single blockquote line (leading '>' after optional indent). Used to glue
# a run of '>' lines into one piece in _split_newlines so _split_blockquote
# sees the whole quote, and to detect the start of a quote block.
_BLOCKQUOTE_LINE_RE = re.compile(r"^[ \t]*>")
# A task item's box, plain `[ ]` or linked `[[ ]](url)`, then its label.
_TASK_ITEM_RE = re.compile(
    rf"^[-*+]\s+(\[([ xX])\]|\[\[([ xX])\]\]\((?=[^)]){LINK_DESTINATION}\))(?:\s+(.*)|$)"
)
# A box opening a task's label, after its marker: `[ ]`, or `[[ ]](url)` — not
# `[x](url)`, which is a link.
_LABEL_BOX_RE = re.compile(
    rf"\[\[[ xX]\]\]\((?=[^)]){LINK_DESTINATION}\)|\[[ xX]\](?!\()"
)

# An image; `![alt]()`, an empty source, is one with no picture.
IMAGE_RE = re.compile(rf"(!\[[^\]]*\]\({LINK_DESTINATION}\))")

INLINE_CODE_RE = re.compile(r"(`[^`]+`)")


def _is_list_continuation(line: str) -> bool:
    """True when an indented line under a list item is plain continuation
    text, not a nested structural element. Nested sub-lists (their own
    marker) and indented tables (``|`` rows) are out of scope and must be
    left for their own handling rather than slurped into the item text.
    """
    s = line.strip()
    return not (_LIST_MARKER_RE.match(s) or s.startswith("|"))


def mark_hard_breaks(text: str, heading_re: "re.Pattern[str]") -> str:
    r"""*text* with each hard-breaking line end turned into HARD_BREAK and the
    next line joined on, so the two are one text.

    As in CommonMark, ``\\`` at a line end is a literal backslash, and a break
    only continues a text: where the next line is blank or starts a block of its
    own, or the line is one by definition, the backslash is drawn as written.
    A heading is not one: it continues as a text does, and its joined lines are
    one heading of its level.
    The lines are joined here rather than marked, because ``str.strip`` counts
    HARD_BREAK as whitespace and would delete one left at a line end.
    """

    def one_line_block(line: str) -> bool:
        return bool(line.lstrip().startswith("|") or _break_node_type(line) is not None)

    def starts_a_block(line: str) -> bool:
        return bool(
            heading_re.match(line)
            or one_line_block(line)
            or _BLOCKQUOTE_LINE_RE.match(line)
            or _LIST_MARKER_RE.match(line.strip())
        )

    out: list[str] = []
    for line in text.split("\n"):
        if out:
            prev = out[-1]
            run = len(prev) - len(prev.rstrip("\\"))
            if (
                run % 2 == 1
                and line.strip()
                and not one_line_block(prev)
                and not starts_a_block(line)
            ):
                out[-1] = prev[:-1] + HARD_BREAK + line.lstrip()
                continue
        out.append(line)
    return "\n".join(out)


def flat_label(inner: str) -> str:
    r"""A link or image label written over several lines, as one line.

    Its lines are joined by a space, as CommonMark joins a soft break, except
    where one ends in a hard break, by the rule :func:`mark_hard_breaks` reads:
    an odd run of backslashes, followed by a line that is not blank. Link text
    is inline content, so the break holds inside it, and the label keeps
    HARD_BREAK where the backslash was. Without this, ``[a\`` / ``b](/x)``
    would draw ``a\ b`` on one line.
    """
    out, blank = "", False
    for raw in inner.split("\n"):
        line = " ".join(raw.split())
        if not line:
            blank = bool(out)
            continue
        run = len(out) - len(out.rstrip("\\"))
        if not out:
            out = line
        elif run % 2 and not blank:
            out = out[:-1] + HARD_BREAK + line
        else:
            out = f"{out} {line}"
        blank = False
    return out


def finish_lines(
    text: str, heading_re: "re.Pattern[str]", escape_re: "re.Pattern[str]"
) -> str:
    """*text* with its hard breaks joined, then its early escapes resolved — in
    that order, so an escaped backslash never reads as a break. Run on the
    document and on every card body alike: a body is stashed before the
    document gets here, and would otherwise keep its ``\\`` line ends and
    ``\\*`` escapes as written."""
    return escape_re.sub(resolve_escape, mark_hard_breaks(text, heading_re))


def _split_blank_lines(content: str):
    # An indented part that follows a list block is a "loose" list
    # continuation (a second paragraph of the last item), not its own
    # paragraph — merge it back before the blank-line split would strip
    # away its indentation. The blank line is preserved (joined with "\n\n")
    # so the later body-restructuring pass can re-split the item into its
    # paragraphs. Gated to list-preceded parts.
    raw = re.split(r"\n{2,}", content)
    merged: list[str] = []
    for part in raw:
        if (
            merged
            and part[:1].isspace()
            and _LIST_MARKER_RE.match(merged[-1].lstrip().split("\n", 1)[0])
            and _is_list_continuation(part.split("\n", 1)[0])
        ):
            merged[-1] = merged[-1] + "\n\n" + part
        else:
            merged.append(part)
    parts = [p.strip() for p in merged if p.strip()]
    if len(parts) <= 1:
        return None
    return [(NodeType.GROUP if "\n" in p else NodeType.TEXT, p) for p in parts]


def _split_newlines(content: str):
    # Indentation-aware, gated to list blocks: a line that begins with
    # whitespace continues the current piece (joined with "\n") only when
    # that piece starts with a list marker, so a multi-line list item stays
    # one piece (preserving its glued segment) while _split_all_lists later
    # collects the continuation lines. A blank line inside such a list piece
    # is preserved (as "\n") so the item body keeps its paragraph break for
    # the later body-restructuring pass. Non-list / prose input is split per
    # line (blank lines dropped).
    pieces: list[str] = []
    for line in content.split("\n"):
        in_list_piece = bool(
            pieces and _LIST_MARKER_RE.match(pieces[-1].split("\n", 1)[0])
        )
        # A piece that starts with '>' is a blockquote run; subsequent '>'
        # lines (and interior blank lines) are glued in so _split_blockquote
        # receives the whole quote as one node rather than one node per line.
        in_quote_piece = bool(
            pieces and _BLOCKQUOTE_LINE_RE.match(pieces[-1].split("\n", 1)[0])
        )
        if not line.strip():
            if in_list_piece or in_quote_piece:
                pieces[-1] = pieces[-1] + "\n"
            continue
        if in_quote_piece and _BLOCKQUOTE_LINE_RE.match(line):
            pieces[-1] = pieces[-1] + "\n" + line
        elif in_list_piece and line[:1].isspace() and _is_list_continuation(line):
            pieces[-1] = pieces[-1] + "\n" + line.strip()
        else:
            pieces.append(line.strip())
    pieces = [p for p in (p.strip("\n") for p in pieces) if p]
    if len(pieces) <= 1:
        return None
    # A `---` that ``glued_rules`` left inside the block is its divider.
    return [
        (NodeType.HORIZONTAL_RULE if HORIZONTAL_RULE_RE.match(p) else NodeType.TEXT, p)
        for p in pieces
    ]


def _split_all_lists(content: str):
    lines = content.split("\n")
    first = lines[0]
    # First line must be some kind of list marker
    if not (re.match(r"^[-*+]\s", first) or re.match(r"^\d+[.)]\s", first)):
        return None

    # An item is ``(label, text)``, or ``(label, text, source_number)`` for an
    # ordered one: the number the author wrote, kept so it survives the marker
    # being stripped off the text (see _stamp_list_ordinals). This is the only
    # splitter that emits a third element; the consumers tolerate both shapes.
    items: list[tuple] = []
    current: list[str] = []
    current_label: str = ""
    current_number: int | None = None
    box = ""  # a task's linked box, `[[ ]](url)`, which its text keeps
    written = ""  # a task's box as written, linked or not

    def flush() -> None:
        nonlocal current_label
        text = "\n".join(current).strip("\n")
        if not text.strip() and current_label in (
            NodeType.TASK_OPEN,
            NodeType.TASK_DONE,
        ):
            # A bare `- [ ]` with no label on or under it: a bullet holding the
            # box -- an empty task item would be pruned, box and all.
            text = box or ("[x]" if current_label == NodeType.TASK_DONE else "[ ]")
            current_label = NodeType.LIST_ITEM
        elif current_label in (NodeType.TASK_OPEN, NodeType.TASK_DONE) and (
            box or _LABEL_BOX_RE.match(text)
        ):
            # The text keeps its marker box where the box is linked, or where
            # the label opens with a box of its own: then the label's box is a
            # second control, and the marker has to be told apart from it
            # (grouper_drawing_elements).
            text = f"{written} {text}"
        items.append(
            (current_label, text, current_number)
            if current_number is not None
            else (current_label, text)
        )

    for line in lines:
        # Task item  — check before unordered (same bullet prefix)
        # `- [ ]` ending its line is a task too -- its label may be the
        # indented line under it, as any item's can. `- [[ ]](url)` is the
        # same task, its box linked (grouper_drawing_elements).
        m = _TASK_ITEM_RE.match(line)
        if m:
            if current:
                flush()
            ticked = (m.group(2) or m.group(3)).lower() == "x"
            current_label = NodeType.TASK_DONE if ticked else NodeType.TASK_OPEN
            box, written = m.group(1) if m.group(3) else "", m.group(1)
            current, current_number = [m.group(4) or ""], None
            continue

        # Ordered item
        m = re.match(r"^(\d+)[.)]\s+(.*)", line)
        if m:
            if current:
                flush()
            current_label = NodeType.ORDERED_ITEM
            current, current_number = [m.group(2)], int(m.group(1))
            continue

        # Unordered item
        m = re.match(r"^[-*+]\s+(.*)", line)
        if m:
            if current:
                flush()
            current_label = NodeType.LIST_ITEM
            current, current_number = [m.group(1)], None
            continue

        # Continuation line — keep blank lines (as "") so the item body
        # retains its paragraph breaks for the body-restructuring pass.
        # (The first line is guaranteed to be a marker, so an item is
        # always active here.)
        if current_label:
            current.append(line.strip())

    if current:
        flush()

    return items or None


def _split_blockquote(content: str):
    """Single-level blockquote splitter.

    Peels exactly ONE leading ``> `` from each line (nested ``>`` stays as
    literal body text — no nested-quote support) and returns the whole run
    as one BLOCKQUOTE node. A multi-line/multi-paragraph body is later given
    paragraph/glued structure by ``_restructure_list_bodies`` (BLOCKQUOTE is
    in ``_LIST_ITEM_LABELS``). Returns None when the first line isn't a
    blockquote line, so it's a no-op on every non-quote node.
    """
    lines = content.split("\n")
    if not _BLOCKQUOTE_LINE_RE.match(lines[0]):
        return None
    peeled: list[str] = []
    for line in lines:
        m = re.match(r"^[ \t]*>[ ]?(.*)$", line)
        peeled.append(m.group(1) if m else line)
    body = "\n".join(peeled).strip("\n")
    return [(NodeType.BLOCKQUOTE, body)]


def _split_inline(
    content: str,
    pattern: re.Pattern,
    label: str,
    unwrap: int = 0,
    protected: list[tuple[int, int]] | None = None,
):
    """Generic inline splitter: split content by a regex pattern.

    Matched segments get the given label; surrounding text gets 'text'.
    When *unwrap* > 0, that many characters are stripped from both ends of
    each matched segment — used to remove markdown delimiters (``**``, ``~~``,
    etc.) whose meaning is already encoded in the node label.
    Returns list of (label, text) tuples, or None if no match.

    *protected* is a list of ``(start, end)`` ranges a match may not overlap
    — markup inside a code span is literal text, not markup. It only changes
    WHICH matches count; the assembly below is shared, so a protected split
    and a plain one produce identically shaped output. Left unset, plain
    ``pattern.split`` runs.

    Time: O(C·P) with P protected ranges (P is tiny), Space: O(C).
    """
    if protected:
        parts, last = [], 0
        for m in pattern.finditer(content):
            if any(s < m.end() and m.start() < e for s, e in protected):
                continue
            parts.extend([content[last : m.start()], m.group(0)])
            last = m.end()
        parts.append(content[last:])
    else:
        parts = pattern.split(content)
    # Also the "every match was protected" exit: nothing to split on.
    if len(parts) == 1:
        return None
    result: list[tuple[str, str]] = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            inner = (
                part[unwrap : len(part) - unwrap].strip() if unwrap else part.strip()
            )
            if inner:
                result.append((label, inner))
        else:
            text = part.strip()
            text = _ORPHAN_SEP_TRAIL.sub("", text).strip()
            text = _ORPHAN_SEP_LEAD.sub("", text).strip()
            if text:
                result.append((NodeType.TEXT, text))
    return result or None


def _split_images(content: str):
    """Split out ``![alt](url)`` → *image* nodes.

    Image markup inside a code span (`` `![alt](photo.jpg)` ``) is literal
    text and never becomes an image. This runs in the element walk just ahead
    of the peel that claims backticks, and ``INLINE_CODE_RE`` is the pattern
    that peel uses, so both agree on where a code span starts and ends without
    depending on the two staying adjacent.

    Time: O(C), Space: O(C).
    """
    code = [m.span() for m in INLINE_CODE_RE.finditer(content)]
    return _split_inline(content, IMAGE_RE, NodeType.IMAGE, protected=code or None)


# The whole-line BREAK spellings, each given its own job. All are whole-line
# and content-free (interior spaces allowed, as CommonMark does: ``- - -``),
# three characters or more, and every one of them cuts a glued run
# identically — they differ only in what they leave behind — except a ``---``
# written tight inside a run, which divides it instead (``glued_rules``). A
# content-free line can never be an emphasis wrapper, and Phase 1 consumes it
# long before any ``*``/``_`` styling runs, so ``***`` and ``___`` are
# unambiguous here.
#
# Markdown gives us three of these; ``:::`` is md2ui's own fourth. It is not
# a CommonMark spelling at all, which is exactly why it was free to take:
# every dash-bearing candidate (``:---``, ``:-:``, ``|---``) is a legal GFM
# table delimiter row and is already read as one (``table_align``).
#
#   ``---``  a painted rule (## Horizontal Rule). The common spelling gets
#            the common meaning: every markdown author, human or LLM,
#            reaches for dashes when it wants a visible divider,
#            so a document written without knowing this syntax still reads
#            the way its author meant it to
#   ``___``  an invisible break: it only cuts, which is what breaking up a
#            repeated-element grid needs. Rare on purpose — you have to mean
#            it
#   ``***``  a section stop: it closes the heading section holding it
#   ``:::``  a COLUMN DIVIDER: it cuts like ``___`` and paints nothing, but
#            the runs either side of it become CELLS OF ONE ROW rather than a
#            stack. The block-level twin of the same-line ` : ` column
#            separator: one colon cuts a line into stacked columns, three cut
#            a block into side-by-side cells. An optional number
#            (``:::2``) weights the cell ABOVE the divider, and an optional
#            condition limits the cut to narrow or wide space
HORIZONTAL_RULE_RE = re.compile(r"^[ \t]*-(?:[ \t]*-){2,}[ \t]*$")


CONTENT_BREAK_RE = re.compile(r"^[ \t]*_(?:[ \t]*_){2,}[ \t]*$")


SECTION_STOP_RE = re.compile(r"^[ \t]*\*(?:[ \t]*\*){2,}[ \t]*$")


# The column divider, with its optional cell weight. Same uniform-run shape as
# the three above so ``: : :`` is spelled the way ``- - -`` is, plus a trailing
# number the others have no use for: ``:::2`` says the cell ABOVE this divider
# takes 2 shares.
#
# The number is a WEIGHT, not a column count, so it is a decimal: ratios reach
# the renderer as floats (``LayoutNode.ratios``), so ``:::0.5``
# costs nothing to accept and says "half of what its neighbour gets" without
# making the author rescale every other cell to keep the numbers whole.
#
# ``0`` is a real weight with its own meaning: no share of the SURPLUS. The cell
# still gets what its content needs — a zero cell is floored at its minimum
# width and pinned there — so ``:::0`` is how an author writes a shrink-to-fit
# cell beside a flexible one. That is the gutter aside, spelled in the same
# syntax as everything else.
#
# A leading digit is required (``0.5``, not ``.5``) so the trailing token is
# always unmistakably a number; ``:::.5`` is not a weight (see the fallback
# below).
#
# After the weight, ONE of two optional things says what the divider does at
# each width (narrow is under ``WIDE_BREAKPOINT``, measured on the space the row
# is offered):
#
#   ``::: 1 1.5``  a second number: the weight in WIDE space, the first being
#                  the weight in narrow space — small to large
#   ``::: 1 <``    a condition: the divider cuts in narrow space only; in wide
#   ``::: 1 >``    space (or narrow, for ``>``) the two sides stack
#
# The condition may stand alone (``::: <``, weight 1, as a bare ``:::``).
COLUMN_DIVIDER_RE = re.compile(
    r"^[ \t]*:(?:[ \t]*:){2,}[ \t]*(\d+(?:\.\d+)?)?"
    r"(?:[ \t]+(\d+(?:\.\d+)?)|[ \t]*([<>]))?[ \t]*$"
)
# The FALLBACK: a line made only of the divider's own characters that is not one
# of the shapes above — a pair and a condition (``::: 1 1.5 >``), two conditions,
# a third number, ``:::.5`` — is still plainly a divider with its options
# mistyped, so it is read as a bare ``:::`` rather than drawn as a line of
# symbols; ``md2ui check`` names it. Anything with other characters on it
# (``::: note``, Pandoc's container syntax, or ``:::2px``) stays text: reading
# those as dividers would turn a note and what follows into cells nobody asked for.
DIVIDER_SHAPED_RE = re.compile(r"^[ \t]*:(?:[ \t]*:){2,}[ \t\d.<>]*$")


def divider_fell_back(line: str) -> bool:
    """Whether *line* is read as a bare ``:::`` because its options are not a
    valid divider — what ``md2ui check`` reports."""
    return bool(DIVIDER_SHAPED_RE.match(line)) and not COLUMN_DIVIDER_RE.match(line)


# What a divider's condition character means: the space it cuts in.
_DIVIDER_WHEN = {"<": "narrow", ">": "wide"}


# The VERTICAL SPRING: a line holding nothing but ``...``. Its inline twin
# pushes the pieces of one line toward opposite edges; this one does the same on
# the other axis, pushing the blocks either side of it to the top and bottom of
# the space they were given.
#
# Exactly three dots, and nothing else on the line. ``....`` is an author
# writing dots, and ``... A`` is the inline spring, which splits a line rather
# than a run of blocks -- ``_split_align_regions`` already returns None for a
# line that is nothing but springs ("`...` alone says nothing about content that
# is not there"), so this token claims a spelling that otherwise means nothing.
VERTICAL_SPRING_RE = re.compile(r"^[ \t]*\.\.\.[ \t]*$")


# The ROW CLOSER: ``;;;`` ends a ``:::`` row and leaves the run going, where
# ``___`` ends both. A semicolon ends a clause and the sentence continues.
ROW_CLOSER_RE = re.compile(r"^[ \t]*;(?:[ \t]*;){2,}[ \t]*$")


# The SPACER: three to five ``+`` and nothing else — small, medium, large
# (ADR-203). Unspaced only: ``+ + +`` is a nested list in CommonMark, and a
# run of ``+`` has no prose reading, so ``\+`` is all an author needs to keep
# one as text. Several on a line with nothing else are ONE spacer down the page,
# their steps summed, as the same marks on stacked lines would be; beside
# content they are inline spacers instead (``grouper_spacers``).
SPACER_RE = re.compile(r"^[ \t]*\+{3,5}(?:[ \t]+\+{3,5})*[ \t]*$")


def _column_divider_weight(line: str) -> float | None:
    """The cell weight written on a ``:::N`` divider, or ``None`` for a bare one.

    Split out from the match so the callers that need the number do not each
    re-spell the regex, and so ``_break_node_type`` stays a pure line -> type
    map. Returns ``None`` for a line that is not a divider at all, which is the
    same answer as "a divider carrying no weight" — both mean "nothing to
    stamp", and no caller can reach here with a non-divider.

    An integral weight comes back as an ``int``. Only so the serialized AST
    reads ``"column_weight": 2`` rather than ``2.0``: the value is a float
    everywhere it is consumed, and Python compares the two the same.

    Time: O(len(line)), Space: O(1).
    """
    m = COLUMN_DIVIDER_RE.match(line)
    return None if m is None else _weight(m.group(1))


def _weight(text: str | None) -> float | None:
    """A written weight as a number; ``None`` when none was written."""
    if text is None:
        return None
    weight = float(text)
    return int(weight) if weight.is_integer() else weight


def stamp_column_divider(node, line: str) -> None:
    """Record what the divider *line* says on its node: the weight of the cell
    above, its weight in wide space when two were written, and the space the
    divider cuts in (``None``: both).

    Stamped where the raw line still exists; ``build_column_rows`` folds all
    three into the row, and nothing downstream sees the divider itself.
    """
    m = COLUMN_DIVIDER_RE.match(line)
    if m is None:  # the fallback: a bare divider
        return
    node.column_weight = _weight(m.group(1))
    node.column_weight_wide = _weight(m.group(2))
    node.column_when = _DIVIDER_WHEN.get(m.group(3) or "")


_ITEM_MARKER_RE = re.compile(r"^([ \t]*)(?:[-*+]|\d+[.)])(?:[ \t]|$)")


def scope_item_dividers(lines: list[str]) -> list[str]:
    """Hand every `:::` and `...` indented under a list item to that item.

    A top-level `:::` partitions the run it sits in -- the section, heading
    included (``## Title`` + ``:::`` + body is "title beside its text"). One
    indented under an item is written at the ITEM's level, and cutting it at
    the document's would make the item's continuation lines, the next item and
    the heading above all cells of one row. So it is not a break line here: it
    is rewritten to ``ITEM_DIVIDER``, the item stays one piece of text through
    the list split, and ``grouper_column_rows.build_item_rows`` restores it
    once the item's lines are its own children.

    An item's scope is its marker line and every line after it indented past
    the marker, blank lines included -- the continuation rule
    ``_split_newlines`` and ``_split_blank_lines`` already follow.

    Time: O(lines), Space: O(lines).
    """
    out: list[str] = []
    item_indent: int | None = None
    for line in lines:
        indent = len(line) - len(line.lstrip(" \t"))
        marker = _ITEM_MARKER_RE.match(line)
        if marker:
            item_indent = len(marker.group(1))
        elif line.strip() and (item_indent is None or indent <= item_indent):
            item_indent = None
        elif item_indent is not None and (
            DIVIDER_SHAPED_RE.match(line) or VERTICAL_SPRING_RE.match(line)
        ):
            line = line[:indent] + ITEM_DIVIDER + line.strip()
        out.append(line)
    return out


# A thematic break carried by a LIST MARKER. CommonMark's rule is "three or
# more MATCHING characters", and it outranks a list item — so a uniform run
# is a break however much it looks like a bullet (`* ***` and `- ---` are
# breaks, not marked ones), while a marker followed by a DIFFERENT break
# character is a list item holding a break (`* ---`, `- ___`, `1. ***`).
# This matches only the second shape, because it is tested LAST, after the
# three uniform patterns above have had their turn.
LIST_MARKER_BREAK_RE = re.compile(
    r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+"
    r"(?:-(?:[ \t]*-){2,}|_(?:[ \t]*_){2,}|\*(?:[ \t]*\*){2,})[ \t]*$"
)


def _break_node_type(line: str) -> str | None:
    """The BREAK node *line* mints, or ``None`` when it is ordinary text.

    The single place that maps a break spelling to its meaning: ``---`` a
    painted rule, ``___`` an invisible break, ``***`` a section stop, ``:::``
    a column divider, ``;;;`` a row closer, ``...`` a vertical spring, ``+++`` a spacer. Every caller that needs to know "is this line
    structural?" asks here rather than testing the regexes itself.

    ``:::`` is tested with the other three and not behind a flag, because
    everything a caller does with the answer — suppress heading detection on
    the line, end the glued run, stop the heading peel, refuse to re-parse the
    leaf — is what a column divider wants too. Phase 1 of the grouper is where
    it earns all of that for free.

    Behind a LIST MARKER all three collapse to a painted rule: the three
    tools are a top-level distinction, and inside a list what is wanted is a
    divider. That test comes LAST so CommonMark's precedence holds — a
    uniform run of one character is a break however much it looks like a
    bullet, so ``* ***`` stays a section stop and ``- ---`` a rule, while
    ``* ---`` and ``- ___`` (marker, then a DIFFERENT character) are the
    marked shape and become rules.

    Indentation carries no meaning here, matching CommonMark, which treats
    up to three spaces as insignificant — a lone ``***`` is a section stop
    at any indent. Four or more spaces is a code block, already consumed by
    ``INDENTED_CODE_RE`` in :meth:`preprocess`.

    Time: O(len(line)), Space: O(1).
    """
    if HORIZONTAL_RULE_RE.match(line):
        return NodeType.HORIZONTAL_RULE
    if CONTENT_BREAK_RE.match(line):
        return NodeType.CONTENT_BREAK
    if SECTION_STOP_RE.match(line):
        return NodeType.SECTION_STOP
    if DIVIDER_SHAPED_RE.match(line):
        return NodeType.COLUMN_DIVIDER
    if VERTICAL_SPRING_RE.match(line):
        return NodeType.VERTICAL_SPRING
    if ROW_CLOSER_RE.match(line):
        return NodeType.ROW_CLOSER
    if SPACER_RE.match(line):
        return NodeType.SPACER
    if LIST_MARKER_BREAK_RE.match(line):
        return NodeType.HORIZONTAL_RULE
    return None


def glued_rules(lines: list[str], breaks: set[int], headings: set[int]) -> set[int]:
    """The ``---`` lines that divide a glued block rather than cut it.

    ``---`` paints and ``___`` cuts. A rule written tight between two lines,
    with no blank line on either side, is a divider under the line above, so
    the run of lines it divides stays one block — one card, one ``:::`` cell —
    the way ``- ---`` divides the items of one list. A rule with a blank line on
    either side is a block of its own.

    Only between two lines of the same block: a heading, another break, a list
    item, a quote or a table line on either side keeps the rule a cut, so a
    list's own ``- ---`` dividers and a rule closing a section stay cuts.

    The rule is left out of the break lines, so it stays a line of the block's
    text and ``_split_newlines`` mints it there, inside the block's glue.

    Time: O(len(breaks)), Space: O(len(breaks)).
    """

    def body_line(j: int) -> bool:
        line = lines[j] if 0 <= j < len(lines) else ""
        return bool(
            line.strip()
            and j not in breaks
            and j not in headings
            and not _LIST_MARKER_RE.match(line.lstrip())
            and not _BLOCKQUOTE_LINE_RE.match(line)
            and not line.lstrip().startswith("|")
        )

    return {
        i
        for i in breaks
        if _break_node_type(lines[i]) == NodeType.HORIZONTAL_RULE
        and body_line(i - 1)
        and body_line(i + 1)
    }


def glued_runs(lines: list[str], breaks: set[int]) -> list[list[int]]:
    """The lines of each glued block: a run of two or more non-blank lines
    with no blank line and no break between them.

    A lone ``...`` written tight between two such lines does not end the run:
    it divides the space inside that one box, the way a ``+++`` does, so the
    box stays one card with its regions pushed apart inside it. With a blank
    line or another break beside it, it ends the run like any break. The spring
    itself is not a member; it is minted as a break all the same.

    Time: O(len(lines)), Space: O(len(lines)).
    """

    def body(j: int) -> bool:
        return 0 <= j < len(lines) and j not in breaks and bool(lines[j].strip())

    runs: list[list[int]] = []
    run: list[int] = []
    for i in range(len(lines) + 1):
        if body(i):
            run.append(i)
        elif not (
            i in breaks
            and _break_node_type(lines[i]) == NodeType.VERTICAL_SPRING
            and body(i - 1)
            and body(i + 1)
        ):
            if len(run) >= 2:
                runs.append(run)
            run = []
    return runs


# The BREAK leaves: a painted `---` rule, an invisible `___` break, the `***`
# section stop that only lives between _segment_lines_with_hrs and
# _apply_section_stops, and the `:::` column divider that lives between
# _segment_lines_with_hrs and _build_column_rows. All are kept by every prune
# (they carry structure, not content) and all cut a run of siblings the same
# way — only what they leave behind differs.
# The breaks that PARTITION a box rather than ending a run. Both say "what is
# above me and what is below me share one box" -- `:::` across, `...` down --
# and sharing a box means being SIBLINGS. So both are transparent to the heading
# peel: an image written above one of them, above a heading, has to travel into
# that heading's group, or it is stranded in the section before and the
# partition has nothing to divide. The other breaks end a run and bound the
# peel.
_PARTITION_TYPES = (
    NodeType.COLUMN_DIVIDER,
    NodeType.VERTICAL_SPRING,
)


_BREAK_TYPES = (
    NodeType.HORIZONTAL_RULE,
    NodeType.CONTENT_BREAK,
    NodeType.SECTION_STOP,
    NodeType.COLUMN_DIVIDER,
    NodeType.VERTICAL_SPRING,
    NodeType.ROW_CLOSER,
    # Listed for what the breaks share: a spelling no splitter may read, a
    # leaf every prune keeps, and its own line in the text around it. It does
    # NOT cut a run of matching siblings — it is outside every fingerprint.
    NodeType.SPACER,
)


# The types the empty-leaf prune must NOT delete. Three passes drop a childless,
# contentless child (``_prune_empty``, the boundary-peel walk, and the separation
# walk's inline copy); they share this list so an exception cannot be added to one
# and forgotten in the other two.
#
# A BREAK is kept because its spelling IS its content. A TABLE_CELL is kept for a
# different reason: **its position is its meaning**. An empty cell is not an absent
# cell, it is a column with nothing in it, and a row is laid out by cell order — so
# dropping one would renumber every column after it: `|  | A | B |` would put its
# headers, and their alignment (_parse_table assigns ``table_align`` by index),
# over the wrong columns.
_KEEP_WHEN_EMPTY = _BREAK_TYPES + (NodeType.TABLE_CELL,)
