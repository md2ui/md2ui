"""What makes two siblings the same KIND: the normalized signature's hash and
vocabulary, and the bounded tree difference two cards may still share a kind
across.

The grouper's fingerprint pass (``ASTPatternAnalyzer._build_fingerprint``)
builds each node's ``kind_hash`` with these and cuts contiguous same-kind runs
with ``_tree_similar``; the layout generator only consumes the result.
"""

import functools
import re

from md2ui.pipeline.grouper_column_rows import row_flows
from md2ui.pipeline.grouper_glue import _is_datapoint_split_group
from md2ui.pipeline.grouper_types import (
    MarkdownGroupNode,
    NodeType,
    _classify_link_content,
)
from md2ui.utils.image_params import image_params


@functools.lru_cache(maxsize=1 << 16)
def _fnv1a_64(s: str) -> int:
    """Deterministic 64-bit FNV-1a hash of a string — stable across runs.

    Cached: a pure function of *s*, so a cached answer is the answer. Within
    one document most calls repeat a string (the same fingerprint / kind
    signature recurs across repeated cards), and the byte loop below is pure
    Python.
    """
    h = 14695981039346656037  # FNV offset basis
    for c in s.encode():
        h ^= c
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF  # FNV prime, keep 64-bit
    return h - (1 << 64) if h >= (1 << 63) else h  # convert to signed


# Node types whose *inline micro-structure* is collapsed away when building the
# normalized "same-kind" signature (kind_hash): an attribute/value/list line and
# all of its split detail (segments, nested datapoints, split-vs-unsplit shape)
# reduce to a single bare type token. The node's TYPE is still preserved, so a
# `key-value` line never matches a `list_item` line — only counts and split depth
# stop mattering; a task item reads as task whether it is checked or not.
# See kind_signatures.
_KIND_COLLAPSE_TYPES = frozenset(
    {
        NodeType.KEY,
        NodeType.VALUE,
        NodeType.KEY_VALUE,
        NodeType.SEGMENT,
        NodeType.LIST_ITEM,
        NodeType.ORDERED_ITEM,
        NodeType.TASK_OPEN,
        NodeType.TASK_DONE,
    }
)


# --- same-kind tolerance (recursive tree-edit) ----
# Two adjacent multi-child groups (e.g. cards) merge into one grid run when they
# are the same kind except for a bounded TREE difference: at most
# _KIND_TOLERANCE_EDITS insert/delete edits *anywhere in the subtree* (an
# optional callout / footnote / label, or a whole missing detail line nested one
# level down inside a wrapper), while still sharing at least
# _KIND_TOLERANCE_MIN_CORE nodes of common structure. A picture beside other
# content is one such piece: the card's content, not its kind, so a card
# missing it stays in its siblings' run (an emoji in its place is not it: that
# card is another kind). A picture among pictures only is the item itself, so a
# gallery one picture short is never within tolerance (_indel_cost).
# Recursion (vs a flat direct-child compare) is what lets e.g. a session card
# `group(group(heading,location,bullet), rule)` match one whose bullet is absent
# `group(group(heading,location), rule)` — the ±1 sits under the wrapper.
# A same-line split is normalized away BEFORE the edits are counted (see
# _line_kind_hash), so one card writing `13:00-14:00 - Now` where its siblings
# write `16:00-17:00` costs nothing — it is the same source line either way.
# Set EDITS=0 to disable tolerance (reverts to exact kind_hash runs); MIN_CORE is
# the floor that stops trivially-small groups from merging.
_KIND_TOLERANCE_EDITS = 1


_KIND_TOLERANCE_MIN_CORE = 3


# The inline elements the element pass draws in a line (buttons and links,
# chips, emoji, checkbox and slider controls). One swapped for another in the
# same place is ONE edit: a card that ends in a status chip
# where its siblings end in a button is still the same card, its state changed.
# A picture is not here: it is never swapped for an element.
_SWAP_ELEMENT_TYPES = frozenset(
    {NodeType.LINK, NodeType.INLINE_CODE, NodeType.EMOJI, NodeType.DRAWING_ELEMENT}
)


# Piece types a one-source-line node may hold and still read as ONE text line.
# Inline code and emoji are DECORATION on the line — the same intent as
# `**bold**` / `*italic*`, which do not even mint a node type (their markers
# ride on the TEXT/SEGMENT content) — so they must not change what KIND of line
# it is. Anything else on the line (an image, link, bullet glyph, or a
# key/value / list marker) is a distinct element, not styling: it must keep the
# line distinct, since normalizing those away would merge unlike cards — though
# one link with only decoration beside it stays that link (_is_decorated_link_line).
_SAME_LINE_TEXT_TYPES = frozenset(
    {
        NodeType.TEXT,
        NodeType.SEGMENT,
        NodeType.DATAPOINT,
        NodeType.INLINE_CODE,
        NodeType.EMOJI,
    }
)


# ...of which at least one must be present: a line made of nothing BUT
# decoration is an icon row (`⭐ 🚀 ⚛️ 🍎`) or a pill run, not a text line. An
# icon row keeps its own kind; every pill run reads alike to the tolerance,
# whatever its count (_is_chip_line).
_SAME_LINE_CORE_TYPES = frozenset({NodeType.TEXT, NodeType.SEGMENT, NodeType.DATAPOINT})


# The kind every chip-only line reads as to the tolerance (_is_chip_line).
_CHIP_LINE_KIND = _fnv1a_64("chips")
# The kind every line of buttons reads as to the tolerance (_is_button_line).
_BUTTON_LINE_KIND = _fnv1a_64("buttons")


# A rating as written: full stars, at most one half star, then empty stars, at
# least one glyph (`⭐⭐⭐⭐⭐`, `★★★★½`, `★★★☆☆`). Nothing else may share the
# line — `⭐ 4.8` or `⭐⭐⭐⭐⭐ (120)` stay text — so a star used as an icon
# beside words is never read as one (_is_rating_line).
_RATING_RE = re.compile(r"[⭐★]*[½⯨⯪]?☆*")
# The kind of a rating line, to the signature and the tolerance alike.
_RATING_KIND = "rating"
_RATING_LINE_KIND = _fnv1a_64(_RATING_KIND)
# What a rating line is written as: one text leaf holding the glyphs, or a line
# of star emoji, one leaf each (a selector-bearing `⭐️` splits that way).
_RATING_TEXT_TYPES = frozenset({NodeType.TEXT, NodeType.DATAPOINT})


# The kind every plain text line already hashes to (a TEXT leaf, a DATAPOINT
# leaf and a datapoint-split group all fold to this in _build_fingerprint).
_TEXT_LINE_KIND = _fnv1a_64(str(NodeType.TEXT))
# The kind of a one-line colon column (`_Wind_ : NNE 6 km/h`): it stacks label
# over value, so it never reads as the row a plain or split line lays out as.
_COLUMN_LINE_KIND = _fnv1a_64("column-line")


# What may sit beside a link without changing what kind of line it is.
_LINK_DECORATION_TYPES = frozenset({NodeType.INLINE_CODE, NodeType.EMOJI})


def _is_decorated_link_line(n: "MarkdownGroupNode") -> bool:
    """True when *n* is one source line holding ONE link and only decoration
    (chips, icons) beside it, on either side.

    A chip or an icon badges a link the way it styles a text line, so the line
    keeps the link's kind: a ``[Buzz](/buzz) `BETA` `` line belongs with the bare
    link lines around it. Several links (a link row), decoration alone (a pill
    or icon row) and a link beside text or a value are different lines, and
    keep their own kind.
    """
    if n.type != NodeType.GROUP or not n.children or n.source_line_id is None:
        return False
    links = decorations = 0
    stack = list(n.children)
    while stack:
        c = stack.pop()
        if c.children:
            stack.extend(c.children)
        elif c.type == NodeType.LINK:
            links += 1
        elif c.type in _LINK_DECORATION_TYPES:
            decorations += 1
        else:
            return False
    return links == 1 and decorations > 0


def _is_one_source_line_text(n: "MarkdownGroupNode") -> bool:
    """True when *n*'s whole subtree is ONE physical source line whose pieces
    all read as text (see _SAME_LINE_TEXT_TYPES), at least one of them a real
    text piece rather than pure decoration (_SAME_LINE_CORE_TYPES).

    ``source_line_id`` — not the ``line_split_group`` flag — is the test: the
    flag is gated off heading containers (they stack, see
    _derive_line_split_groups) and would miss a heading that split inline,
    ``### **A title, with a comma**``. It is also the weaker condition, since a
    node only carries a non-None id when its whole subtree shares one line.

    Depth-insensitive on purpose: a nested bold/segment peel under the line is
    still the same *written* line. A piece of *n*'s OWN type counts as text for
    the same reason — a peel keeps the parent's label on the text it split off,
    so ``### Title `code` `` is ``heading3(heading3, inline_code)``.
    """
    if not n.children or n.source_line_id is None:
        return False
    saw_core = False
    stack = list(n.children)
    while stack:
        c = stack.pop()
        if c.children:
            stack.extend(c.children)
            continue
        if c.type == n.type or c.type in _SAME_LINE_CORE_TYPES:
            saw_core = True
        elif c.type not in _SAME_LINE_TEXT_TYPES:
            return False
    return saw_core


def _is_chip_line(n: "MarkdownGroupNode") -> bool:
    """True when *n* is one source line of nothing but chips: a lone chip, or a
    line group whose every piece is one.

    Chips are labels and states (`Open`, `Done`, a genre), and how many a card
    carries is a fact about that card, not its kind: one chip must read like a
    pill run of any length, or a card leaves its run for having fewer labels
    than its neighbour. Icon rows are not chips and keep
    their own kind; a chip beside a link is that link's line
    (_is_decorated_link_line).
    """
    if not n.children:
        return n.type == NodeType.INLINE_CODE
    if n.type != NodeType.GROUP or n.source_line_id is None:
        return False
    stack = list(n.children)
    while stack:
        c = stack.pop()
        if c.children:
            stack.extend(c.children)
        elif c.type != NodeType.INLINE_CODE:
            return False
    return True


def _is_button_line(n: "MarkdownGroupNode") -> bool:
    """True when *n* is a line of two or more links and nothing else.

    How many buttons a card ends in is a fact about that card, not its kind:
    an offer with a main and a quieter button is the same card as an invite
    with one. Like a pill run, the line is variant-free, so
    a Primary and a Secondary button read like a lone Tertiary one. A lone
    link is not a button line: it keeps its own kind, so it still matches a
    link badged by a chip (_is_decorated_link_line), and only costs nothing
    against a button line (_tree_edit_within).
    """
    return (
        n.line_split_group
        and len(n.children) >= 2
        and all(c.type == NodeType.LINK and not c.children for c in n.children)
    )


def _is_lone_link(n: "MarkdownGroupNode") -> bool:
    return n.type == NodeType.LINK and not n.children


def _is_rating_line(n: "MarkdownGroupNode") -> bool:
    """True when *n* is one source line of nothing but rating glyphs
    (_RATING_RE): a text leaf, or a line group of two or more star emoji.

    A rating is a card's score, like a chip its label: its own kind of line,
    so five stars over a quote never read as a name over
    its class year. A lone star emoji is not one: it is how an icon or a badge
    is written, as a line or as a piece of one, and it keeps the emoji's kind.
    Emphasis markers and the emoji presentation selector are spelling, not
    glyphs.
    """
    if not n.children:
        if n.type not in _RATING_TEXT_TYPES:
            return False
        pieces = [n]
    elif n.type != NodeType.GROUP or n.source_line_id is None:
        return False
    else:
        pieces = _leaves(n)
        if len(pieces) < 2 or any(p.type != NodeType.EMOJI for p in pieces):
            return False
    text = "".join(p.content for p in pieces).replace("\ufe0f", "")
    text = text.strip().strip("*_").strip()
    return bool(text) and _RATING_RE.fullmatch(text) is not None


def _line_kind_hash(
    n: "MarkdownGroupNode", memo: dict[int, int | None] | None = None
) -> int | None:
    """``kind_hash`` seen through the SOURCE structure, for the tolerance only.

    A node that IS one source line reads as the leaf it would have been had it
    never split, so a line that happened to split compares equal to a sibling
    card's line that did not:

      * a GROUP is only a holder for the pieces — unsplit it is a plain text
        line, so ``13:00-14:00 - Now`` (group of datapoint+segment) matches a
        bare ``16:00-17:00`` datapoint leaf (whose kind already folds to
        ``text``);
      * except a colon COLUMN, which stacks its pieces: it reads as a column
        line, matching another however its cells split, and never a row such
        as ``Mostly cloudy ... Air quality poor``;
      * a TYPED node keeps its own identity — ``### **A title, with a comma**``
        (heading3 of segments) matches a sibling card's unsplit ``heading3``,
        never a plain text line. ``_fnv1a_64(kind_type(n))`` is exactly the
        own signature a childless node of that type gets in kind_signatures
        (a no-op for the _KIND_COLLAPSE_TYPES, which hash that way already);
      * a CHIP line reads as "chips" (_is_chip_line), so a lone chip matches a
        pill run of any length: the count never costs an edit, while a card
        with no chip line still pays its one insert;
      * a BUTTON line reads as "buttons" (_is_button_line), so two buttons
        match three;
      * a RATING line reads as "rating" (_is_rating_line), however its stars
        were split: a text of glyphs matches a line of star emoji.

    Without this the split turns a LEAF into a CONTAINER, which
    _tree_edit_within can only pay for as delete+insert — two edits, over
    budget — so one stray same-line split breaks a whole card run.

    Deliberately NOT used for the stored ``kind_hash``: plain adjacent ``text``
    leaves already share a kind, so collapsing there would chain every split
    line into them and grid unrelated body lines together.

    *memo* caches the answer per node (``id(n)``) for ONE ``fingerprints()``
    call — the analyzer owns it and empties it when the call returns. The
    answer cannot go stale inside that call: it reads only ``n.kind_hash``
    (set once, bottom-up, and never rewritten; this is only asked of children
    and descendants of the node being built, which are finished) and *n*'s
    children and line id, which fingerprinting does not touch. Most calls
    repeat a node: every edit-distance step asks it of both sides.
    """
    if memo is not None and id(n) in memo:
        return memo[id(n)]
    if _is_chip_line(n):
        kind = _CHIP_LINE_KIND
    elif _is_button_line(n):
        kind = _BUTTON_LINE_KIND
    elif _is_rating_line(n):
        kind = _RATING_LINE_KIND
    elif not _is_one_source_line_text(n):
        kind = n.kind_hash
    elif n.type == NodeType.GROUP:
        kind = _COLUMN_LINE_KIND if n.column_split_group else _TEXT_LINE_KIND
    else:
        kind = _fnv1a_64(kind_type(n))
    if memo is not None:
        memo[id(n)] = kind
    return kind


def _subtree_size(n: "MarkdownGroupNode") -> int:
    """Total node count of the subtree rooted at *n* (self + all descendants)."""
    return 1 + sum(_subtree_size(c) for c in n.children)


def _tree_edit_within(
    a: "MarkdownGroupNode",
    b: "MarkdownGroupNode",
    cap: int,
    memo: dict[int, int | None] | None = None,
) -> int:
    """Min insert/delete edits to turn subtree *a* into *b*, clamped to cap+1.

    A cheap top-down tree edit distance keyed on ``kind_hash`` (so counts /
    split-depth already fold away, and a same-line text group reads as the one
    line it was written as — see _line_kind_hash): equal-kind subtrees cost 0,
    as does a lone link against a line of buttons (_is_button_line);
    one inline element swapped for a different one costs 1 (_is_element_swap);
    any other nodes of a different *type* can't be substituted (forces delete+insert),
    except a pair against the same card with its picture
    (_is_pair_and_picture); a picture costs what _indel_cost says. Returns
    cap+1 as soon
    as the cost provably exceeds cap, which keeps the recursion shallow when
    cap is small (=1). *memo* is the per-call ``_line_kind_hash`` cache,
    threaded through.
    """
    if _is_element_swap(a, b):
        return 1
    if (_is_lone_link(a) and _is_button_line(b)) or (
        _is_lone_link(b) and _is_button_line(a)
    ):
        return 0
    if _line_kind_hash(a, memo) == _line_kind_hash(b, memo):
        return 0
    if cap <= 0 or (kind_type(a) != kind_type(b) and not _is_pair_and_picture(a, b)):
        return cap + 1
    return _seq_edit_within(a.children, b.children, cap, memo)


def _is_element_swap(a: "MarkdownGroupNode", b: "MarkdownGroupNode") -> bool:
    """True when *a* and *b* are both inline elements and draw differently.

    A button against a Text link is a swap too: the kind already tells the two
    apart (_element_token), so the tolerance charges for it like any other
    element swapped in the same place.
    """
    if a.type not in _SWAP_ELEMENT_TYPES or b.type not in _SWAP_ELEMENT_TYPES:
        return False
    return (a.type, _element_token(a)) != (b.type, _element_token(b))


# What reads as a picture on the page: an image card is one too.
_PICTURE_TYPES = frozenset({NodeType.IMAGE, NodeType.IMAGE_CARD})


def _is_pair_and_picture(a: "MarkdownGroupNode", b: "MarkdownGroupNode") -> bool:
    """True when one of *a* and *b* is a pair (_is_pair) and the other is a
    glued block of the same type holding two lines and one picture.

    A card whose picture is missing is left with two lines, which is a pair,
    and a pair is its own kind; against the same card with its picture it is
    compared piece by piece, so only the picture is counted, and a two-line
    block still never matches a three-line one.
    """
    if a.type != b.type:
        return False
    for pair, card in ((a, b), (b, a)):
        if kind_type(pair) == _PAIR_KIND and kind_type(card) != _PAIR_KIND:
            solid = [c for c in card.children if c.type != NodeType.SPACER]
            pictures = [c for c in solid if c.type in _PICTURE_TYPES]
            return card.glued_content_group and len(solid) == 3 and len(pictures) == 1
    return False


def _beside_content(nodes: list["MarkdownGroupNode"]) -> bool:
    """True when *nodes* hold something other than pictures, so a picture among
    them is a card's content rather than the item of a gallery."""
    return any(
        c.type not in _PICTURE_TYPES and c.type != NodeType.SPACER for c in nodes
    )


def _indel_cost(n: "MarkdownGroupNode", cap: int, beside_content: bool) -> int:
    """Cost to insert/delete node *n* from a child list: 1, except a picture in
    a list of pictures only (*beside_content* False), which is forbidden
    (cap+1) — a gallery one picture short is a different gallery."""
    if n.type in _PICTURE_TYPES and not beside_content:
        return cap + 1
    return 1


def _seq_edit_within(
    A: list["MarkdownGroupNode"],
    B: list["MarkdownGroupNode"],
    cap: int,
    memo: dict[int, int | None] | None = None,
) -> int:
    """Min edits aligning two child lists (order-preserving), clamped to cap+1.

    Substitution recurses via ``_tree_edit_within``; insert/delete via
    ``_indel_cost`` (a picture among pictures only is forbidden).

    Banded, and exact. Every insert/delete costs at least 1, so reaching
    alignment cell (i, j) costs at least |i - j|: a cell outside the band
    |i - j| <= cap is already over the cap, which the full DP clamps to cap+1
    anyway. So only the band is computed, and two lists whose lengths differ
    by more than cap are rejected before any work. O(len * (2*cap + 1)) rather
    than O(len(A) * len(B)), so a long sibling list never costs the product of
    its lengths. ``tests/markdown_kind_line_tolerance_tests.py`` pins it to the
    full DP.
    """
    m, n = len(A), len(B)
    over = cap + 1
    if abs(m - n) > cap:
        return over
    a_mixed, b_mixed = _beside_content(A), _beside_content(B)
    prev = [over] * (n + 1)
    prev[0] = 0
    for j in range(1, min(n, cap) + 1):
        prev[j] = min(over, prev[j - 1] + _indel_cost(B[j - 1], cap, b_mixed))
    for i in range(1, m + 1):
        cur = [over] * (n + 1)
        if i <= cap:
            cur[0] = min(over, prev[0] + _indel_cost(A[i - 1], cap, a_mixed))
        for j in range(max(1, i - cap), min(n, i + cap) + 1):
            sub = prev[j - 1] + _tree_edit_within(A[i - 1], B[j - 1], cap, memo)
            dele = prev[j] + _indel_cost(A[i - 1], cap, a_mixed)
            ins = cur[j - 1] + _indel_cost(B[j - 1], cap, b_mixed)
            cur[j] = min(over, sub, dele, ins)
        prev = cur
    return prev[n]


def _tree_similar(
    a: "MarkdownGroupNode",
    b: "MarkdownGroupNode",
    memo: dict[int, int | None] | None = None,
) -> bool:
    """Whether two card subtrees are the same kind within the tolerance budget.

    True iff they differ by ≤ _KIND_TOLERANCE_EDITS tree edits (see
    _indel_cost for what a picture costs) AND the smaller subtree has ≥ _KIND_TOLERANCE_MIN_CORE nodes
    (a floor so near-empty groups don't merge on a single edit). *memo* is the
    per-call ``_line_kind_hash`` cache (see that function). Spacer cells on
    different sides (``_beside``) are no tolerated difference: the exact kind
    decides, as it would between the leaf cells they stand for.
    """
    if _KIND_TOLERANCE_EDITS <= 0 or _beside(a) != _beside(b):
        return a.kind_hash == b.kind_hash
    if min(_subtree_size(a), _subtree_size(b)) < _KIND_TOLERANCE_MIN_CORE:
        return False
    edits = _tree_edit_within(a, b, _KIND_TOLERANCE_EDITS, memo)
    return edits <= _KIND_TOLERANCE_EDITS


# A checked and an unchecked task are one kind: the check is the item's STATE,
# drawn by its control, not what kind of item it is (ADR-201), so a checklist
# with a done item still runs as one list. Unordered, ordered and task items
# stay three kinds.
_TASK_TYPES = frozenset({NodeType.TASK_OPEN, NodeType.TASK_DONE})
_TASK_KIND = "task"

# How a container came to be, as a token in its kind: two containers built
# differently are different kinds even when their children match. A heading
# section is written by level (``h3``), below.
_ORIGIN_FLAGS = (
    ("glued_content_group", "glue"),
    ("column_row_group", "row"),
    ("line_split_group", "line"),
    ("column_split_group", "cols"),
    ("align_group", "spring"),
    ("valign_group", "vspring"),
    ("table_group", "table"),
    ("chart_group", "chart"),
    ("line_group", "lines"),
)

# The ``?md2ui.*`` params that size or shape an image, compared as written (a
# ``_wide`` twin counts too). ``fit`` only crops inside the same box, so it is
# not part of the kind.
_IMAGE_KIND_PARAMS = ("max_width", "min_width", "max_height", "aspect_ratio", "shape")


# A glued block of two text lines: its own kind, never a plain group's. A date over its weekday and a three-line agenda both fold to
# group(text){glue}, so without this they twin as cards in one grid.
_PAIR_KIND = "pair"
_PAIR_LEAF_TYPES = frozenset({NodeType.TEXT, NodeType.DATAPOINT})
# What one text line may split into and still be one line of a pair: a value and its unit (``___1,204___ - tems``) are still one line.
_PAIR_PIECE_TYPES = _PAIR_LEAF_TYPES | {NodeType.SEGMENT}


def _is_pair(n: "MarkdownGroupNode") -> bool:
    """True when *n* is a glued block of exactly two text lines, written on two
    different source lines.

    A line is a text leaf, or a plain group of the text pieces one source line
    split into, so a label over a split value is a pair like its unsplit
    neighbours and the tiles still run together. A key-value line or a list
    item is not a text line.

    The shape alone decides: no word count, value or styling tier, so a run of
    identical-looking two-line tiles stays one run. A spacer is blank space
    (ADR-203), so it is no line.
    """
    if not n.glued_content_group:
        return False
    lines = [c for c in n.children if c.type != NodeType.SPACER]
    if len(lines) != 2:
        return False
    a, b = (_pair_line(c) for c in lines)
    return a is not None and b is not None and a != b


def _pair_line(n: "MarkdownGroupNode") -> int | None:
    """The source line *n* is, when it is one text line of a pair; else None."""
    if not n.children:
        return n.source_line_id if n.type in _PAIR_LEAF_TYPES else None
    if n.type != NodeType.GROUP:
        return None
    pieces = _leaves(n)
    if any(p.type not in _PAIR_PIECE_TYPES for p in pieces):
        return None
    lines = {p.source_line_id for p in pieces}
    return lines.pop() if len(lines) == 1 else None


def kind_type(n: "MarkdownGroupNode") -> str:
    """*n*'s type as the kind reads it: a task is a task, checked or not, a
    rating line is a rating (_is_rating_line), and a two-line glued block is a
    pair (_is_pair)."""
    if n.type in _TASK_TYPES:
        return _TASK_KIND
    if _is_rating_line(n):
        return _RATING_KIND
    return _PAIR_KIND if _is_pair(n) else n.type


def _origin_token(n: "MarkdownGroupNode") -> str:
    tokens = [f"h{n.heading_level}"] if n.heading_group else []
    for flag, token in _ORIGIN_FLAGS:
        if not getattr(n, flag):
            continue
        # A flowing ::: row IS a line (one builder, one measurer): the spellings
        # of one arrangement are one kind.
        if token == "row" and row_flows(n):
            token = "line"
        if token not in tokens:
            tokens.append(token)
    return ",".join(tokens)


def _link_shape(n: "MarkdownGroupNode") -> str:
    """A Text link is drawn as text; every other variant draws a button."""
    return "txt" if _classify_link_content(n.content)[0] == "text" else "btn"


def _element_token(n: "MarkdownGroupNode") -> str:
    """What an image or a link adds to the kind of the card that holds it."""
    if n.type == NodeType.IMAGE:
        params = image_params(n.content)
        return ",".join(
            f"{key}={params[key]}"
            for name in _IMAGE_KIND_PARAMS
            for key in (name, name + "_wide")
            if key in params
        )
    if n.type == NodeType.LINK:
        return _link_shape(n)
    return ""


def _beside(n: "MarkdownGroupNode") -> str:
    """Which sides of *n* a spacer CELL stands beside among its siblings
    (``spacer_beside``). A section's cell is inside its card, beside its
    content: it is no cell among the cards."""
    if not n.spacer_beside or n.heading_group:
        return ""
    return "|" + "".join(
        s for s, e in (("<", n.spacer_lead), (">", n.spacer_trail)) if e
    )


def kind_signatures(
    node: "MarkdownGroupNode", child_kinds: list[str]
) -> tuple[str, str]:
    """*node*'s same-kind signature (``_kind_signatures``), with the sides a
    spacer cell stands beside it on.

    A spacer cell is placed as the leaf cell it stands for: two items with a cell on different sides are two kinds among
    their siblings, as they would be with a text cell there, and with a cell
    on the same side they run. Only the node's own kind: what it adds to its
    parent is unchanged, so a card with a spacer cell still twins one without.
    """
    own, up = _kind_signatures(node, child_kinds)
    return own + _beside(node), up


def _kind_signatures(
    node: "MarkdownGroupNode", child_kinds: list[str]
) -> tuple[str, str]:
    """*node*'s normalized "same-kind" signature: ``(own, for_parent)``.

    Order-preserving like the fingerprint, but count- and split-depth-
    insensitive:
      * a DATAPOINT leaf OR a datapoint-SPLIT group -> "text", exactly
        mirroring the fingerprint's collapse (:_is_datapoint_split_group) so a
        value that split into group(text,datapoint) reads the same as a bare
        datapoint leaf — about a value's shape, kind_hash must never be
        less tolerant than fingerprint_hash (a pair's lines included). It
        may be stricter elsewhere: the origin token, the rating and the pair, below;
      * one link with only chips / icons beside it -> "link", the kind of the
        bare link line it was written as (_is_decorated_link_line);
      * an inline micro-structure container (value/segment/list line, see
        _KIND_COLLAPSE_TYPES) -> its bare type token, discarding all split
        detail so a split value == an unsplit one and 4 vs 6
        colours/segments/bullets read the same; a task, checked or not, is
        ``task``;
      * a line of nothing but rating glyphs (_is_rating_line) -> "rating",
        its own kind, however its stars were split;
      * a glued block of two text lines (_is_pair) -> pair(kind1,kind2),
        NOT folded, so two lines never read as the three of a plain glued
        block, and kind_type makes the tolerance refuse to match the two. A
        line split into pieces of one source line (a value and its unit) is
        still one text line; a key-value line or list item is none;
      * otherwise tag(child_kinds...) with CONSECUTIVE identical child kinds
        folded to one, so N repeated children == 1, and the container's
        origin appended (``{h3,row}``, see _ORIGIN_FLAGS).
    Node types are always kept, so unrelated group shapes never merge.

    An image's size params and a link's drawn shape go only into the
    signature handed to the PARENT: they make two cards different kinds, but
    the element's own kind — which its sibling elements run on — is unchanged,
    so a line of mixed buttons and Text links still flows as one row.
    """
    if _is_rating_line(node):
        return _RATING_KIND, _RATING_KIND
    if node.type == NodeType.DATAPOINT or _is_datapoint_split_group(node):
        return str(NodeType.TEXT), str(NodeType.TEXT)
    if _is_decorated_link_line(node):
        link = next(c for c in _leaves(node) if c.type == NodeType.LINK)
        return str(NodeType.LINK), f"{NodeType.LINK}{{{_link_shape(link)}}}"
    if node.type in _KIND_COLLAPSE_TYPES:
        own = kind_type(node)
        return own, own
    if not node.children:
        own = str(node.type)
    elif _is_pair(node):
        own = _PAIR_KIND + "(" + ",".join(child_kinds) + ")"
    else:
        folded: list[str] = []
        for k in child_kinds:
            if not folded or folded[-1] != k:
                folded.append(k)
        own = node.type + "(" + ",".join(folded) + ")"
        origin = _origin_token(node)
        if origin:
            own += "{" + origin + "}"
    element = _element_token(node)
    return own, (own + "{" + element + "}" if element else own)


def _leaves(n: "MarkdownGroupNode") -> list["MarkdownGroupNode"]:
    out: list[MarkdownGroupNode] = []
    stack = list(n.children)
    while stack:
        c = stack.pop()
        if c.children:
            stack.extend(c.children)
        else:
            out.append(c)
    return out
