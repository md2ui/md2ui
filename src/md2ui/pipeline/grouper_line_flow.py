"""Same-line grouping: which siblings the author wrote on one physical line.

``source_line_id`` is stamped per physical source line while the tree is built.
This phase reads it back: a run of siblings sharing one id was typed on one
line, so it lays out as a ROW rather than a stack, and it is flagged
``line_split`` for the renderer to space and baseline-align as one.

``line_stacks`` is the veto — the shapes that were written on one line but must
still stack (a key-value, an image card, a heading among its siblings). The two
are read together, which is why they live together.

Runs over a FINISHED tree, and only from ``process``.
"""

import re

from md2ui.pipeline.grouper_column_rows import mark_row_pieces, row_flows
from md2ui.pipeline.grouper_glue import _clear_false_glue
from md2ui.pipeline.grouper_types import (
    MarkdownGroupNode,
    NodeType,
    _HEADING_TYPE_RE,
)


# Container types whose children share a source line but must still STACK,
# not flow aside: a Key: value pair renders the key above its value even
# though both sat on one source line.
# An image card stacks its body over the background image; it is a block,
# never a run of same-line pieces.
_NO_FLOW_CONTAINER_TYPES = (NodeType.KEY_VALUE, NodeType.IMAGE_CARD)


# The authored VERTICAL alignment of one source line's row, written at the END
# of the line. The four spellings are the four words ``Vertical align`` already
# takes (theme.py ``LINE_ALIGN_VALUES``) — one property, one vocabulary, so an
# author who wrote ``Vertical align: Bottom`` on a level can see that ``@bm``
# is the override for it. ``@bm`` and not ``@bt`` for bottom: ``@bs``/``@bt``
# is a confusable pair and baseline is the one you write to say "no, keep the
# default here".
_LINE_VALIGN = {"@tp": "top", "@ct": "center", "@bs": "baseline", "@bm": "bottom"}


# The token stands alone at the end of the line: ``(?<!\S)`` requires the start
# of the content or a space in front of it, so ``support@ct`` and any other
# word ending in one of the four is untouched.
#
# That one lookbehind is also what DECLINES the escape, because ``@`` is a
# CONTROL escape (grouper_escapes) and so ``\@ct`` still carries its backslash
# here — a non-space character in front of the token, exactly like the ``a`` in
# ``a@ct``. Phase 6.17 drops the backslash afterwards and the line draws a
# literal ``@ct``. Without that deferral this could not be spelled at all:
# ``preprocess`` would have resolved the escape long before this pass and left
# the two spellings identical.
_LINE_VALIGN_RE = re.compile(r"(?<!\S)(@tp|@ct|@bs|@bm)[ \t]*$")


def consume_line_valigns(node: "MarkdownGroupNode") -> dict[int, str]:
    """Strip every end-of-line valign token, returning ``{source_line_id: value}``.

    Runs at Phase 2.16, beside the authored text tiers and for the same two
    reasons: every content leaf is exactly one source line by then (Phase 2.15
    says so), and it is ahead of data-point detection, so the token never
    reaches the detector or the split criteria. It also settles the ordering
    against the spring for free — ``_split_align_regions`` reads ``content`` at
    Phase 4+5, by which time the token is gone, so a line ending ``... @ct``
    hands the trailing-spring rule exactly the line the author meant.

    The value is keyed on ``source_line_id`` rather than left on the node,
    because the node does not survive: the splits replace a line's leaf with
    its pieces, and ``_inherit_glue`` carries the glue id and the line id but
    NOT this. The line id is the identity that outlives every split, which is
    what it exists for — so the token is recorded against it here and applied
    to whichever container turns out to be that line, in
    :func:`_derive_line_split_groups`.

    A token is ALWAYS consumed, even on a line that turns out to be no row: an
    authored layout is a request, and a request that cannot be honoured must
    still not be drawn as stray text.

    Time: O(N), Space: O(lines carrying a token).
    """
    found: dict[int, str] = {}

    def walk(n: "MarkdownGroupNode") -> None:
        if n.content:
            match = _LINE_VALIGN_RE.search(n.content)
            if match:
                n.content = n.content[: match.start()].rstrip()
                if n.source_line_id is not None:
                    found[n.source_line_id] = _LINE_VALIGN[match.group(1)]
        for child in n.children:
            walk(child)

    walk(node)
    return found


def line_stacks(node: "MarkdownGroupNode") -> bool:
    """Whether *node* STACKS its children rather than laying them out along
    the line — the reason ``_derive_line_split_groups`` withholds
    ``line_split_group`` from it.

    A TITLED heading section holds the heading plus the body under it, never
    one source line (a heading TEXT node's children ARE that line's pieces,
    so they flow — and a bare-heading section collapses onto its heading
    node, which then carries ``heading_group`` itself, hence the type test
    first); a ``Key: value`` puts the value on its own line; a date chip
    stacks its key over its day and must GRID with sibling chips; a
    spaced-colon COLUMN split stacks because that is the whole point of the
    author writing " : ".

    An EMPTY marker (`# ` / `## ` / `### ` with nothing after it) is a
    grouping device, not a heading: its title leaf is contentless and gets
    pruned, so the section collapses onto the content under it and has no
    heading leaf left. Whatever it wrapped must render exactly as it would
    anywhere else, so a title-less section never vetoes the flow.

    The LAYOUT GENERATOR reads the answer through the flag this withholds: a
    piece without ``line_split_group`` stacks, so it is as wide as its widest
    child, not the sum of them (``_line_item_width``), which is what the
    renderer's ``natural_width`` does for a ``col``. Deriving it here rather
    than in the generator keeps ONE definition of "stacks".
    THEME-BLIND by construction — the grouper cannot measure and has no
    theme, so a caller that gates a family on the theme (date chips can be
    switched off, which bakes the pair back to a single leaf) must apply
    that gate itself.
    """
    titled_section = any(_HEADING_TYPE_RE.match(c.type) for c in node.children)
    return bool(
        (
            node.heading_group
            and not _HEADING_TYPE_RE.match(node.type)
            and titled_section
        )
        or node.type in _NO_FLOW_CONTAINER_TYPES
        or node.datapoint_display == "date_chip"
        or node.column_split_group
    )


def _derive_line_split_groups(
    node: "MarkdownGroupNode", valigns: dict[int, str] | None = None
) -> int | None:
    """Post-order: set ``line_split_group`` purely from ``source_line_id``
    and return this node's *effective* source-line id.

    A group flows its children aside (``line_split_group``) iff they are the pieces
    of ONE physical source line — i.e. it has >=2 content children that all
    share one non-None effective source-line id. A node's effective id is
    the common non-None id of its content children (else None); it is stored
    back onto ``source_line_id`` so the serialized tree carries it for the
    layout generator's run same-line gate.

    A peeled boundary LINK is a piece of its line like any other, so a title
    and the action links after it (``## Attendees (14) - [`See all`]``,
    ``## Dashboard [Create] [💬]``) flow together. Only the *arrangement* is
    affected — the peel already decided where the text was cut, and prose
    beside a link stays one intact text piece.

    A heading's own line flows like any other: ``### Title `code``` and
    ``## 1. **Name** - €180`` are single source lines and keep the alignment
    the author wrote. Only the heading *section container* (the heading plus
    the body under it) is gated out — that is never one line.

    Gated OUT (these stack, or flow via a different layout path, so the flag
    would only reroute them):
      * TITLED heading section containers and Key: value pairs — stack. A
        section opened by an EMPTY marker (`# ` / `## `) is not one of them:
        its title leaf is contentless and pruned, so the section is a pure
        grouping wrapper and whatever it holds must render exactly as it
        would outside it;
      * a run whose children are ALL containers — a repeated group run the
        generator grids/flows in place (_build_grouped). Colon COLUMNS are
        the exception: a repeated run is like cards drawn from DIFFERENT
        lines, and re-flowing one is fair game, but a row of columns is one
        line the author wrote and must keep the arrangement they wrote.
    A glued group is NOT gated out: the same-line test alone separates a
    single-line group (children share a line → flow) from a multi-line glued
    card (children differ → not flagged).

    The two flags are **mutually exclusive**, enforced by
    :meth:`_clear_false_glue` at the end of this pass: glue means
    consecutive source lines stuck together, and one line flowed aside has
    no lines to glue. A same-line split that *stacks* (``Key: value``) is
    gated out of ``line_split_group`` above and so keeps its glue.

    Time: O(K), Space: O(depth).
    """
    if not node.children:
        return node.source_line_id
    if node.column_row_group and row_flows(node):
        mark_row_pieces(node)
    child_ids = [_derive_line_split_groups(c, valigns) for c in node.children]
    real = [i for i in child_ids if i is not None]
    shared = real[0] if real and len(set(real)) == 1 else None
    kids = node.children
    # A colon COLUMN is a piece of this line, not a card in a repeated run,
    # so a line made only of them ("A : B - C : D") is still a line. Handing
    # it to the grid instead lets _balance_cols / _kind_cols re-flow it to a
    # single column and stack it.
    # A spring REGION is the same kind of piece for the same reason: the
    # author asked for these to be pushed apart ALONG the line, so gridding
    # them (or worse, re-flowing them to a single column) is the exact
    # opposite of what was written.
    all_containers = all(c.children for c in kids) and not any(
        c.column_split_group or c.authored_align for c in kids
    )
    # Content pieces on the shared line — links included (see docstring).
    n_strip = sum(1 for cid in child_ids if cid is not None)
    node.source_line_id = shared
    # The children are the pieces of ONE physical source line.
    same_line = shared is not None and n_strip >= 2
    # …and this node STACKS them rather than laying them out along the line.
    # See line_stacks for the rule and why each term is in
    # it; the layout generator reads the same helper to measure a stacking
    # piece as its widest child instead of the sum of them.
    stacks = line_stacks(node)
    node.line_split_group = bool(
        same_line
        and not stacks
        # A repeated GROUP run grids in place on its own generator path, so
        # the flag would only reroute it. Element runs are NOT excused: a run
        # of chips, links or emojis — pure or mixed — is the pieces of one
        # source line like any other, and takes the one line path, which
        # baseline-aligns it, element-spaces it and draws the themed
        # separators between its pieces, so chips, links and emojis share one
        # shape, alignment and spacing.
        and not all_containers
    )
    _clear_false_glue(node, same_line and not stacks)
    # …and the line's authored valign, if it wrote one. Applied HERE because
    # this is the pass that decides which container is the line: the token was
    # recorded against a ``source_line_id`` at Phase 2.16 precisely so it could
    # outlive the splits that replaced the leaf carrying it.
    #
    # Gated on ``same_line and not stacks`` rather than on ``line_split_group``,
    # the same condition ``_clear_false_glue`` takes: a repeated container run
    # lays out along the line by its own generator path and carries no flag,
    # but it is still the row the author is aligning. A line
    # that STACKS is excluded because there is no row to align — the request is
    # dropped in silence, the way an unhonoured request should be.
    if valigns and same_line and not stacks and shared in valigns:
        node.line_valign = valigns[shared]
    return shared
