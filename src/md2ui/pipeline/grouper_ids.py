"""Document-unique ids, and the two counters that mint them.

Two ids thread through a document and mean different things:

* ``glued_content_id`` — the run of sibling nodes the author wrote as one
  unbroken stretch of source. A run is what earns a card.
* ``source_line_id`` — one physical line of the source. A run of siblings
  sharing one is a ROW.

Minting either is the grouper's only piece of genuinely mutable state, and it
lives here, in :class:`IdMint`, rather than on the grouper — so a phase that
needs a fresh id can be an ordinary function that is handed one, instead of a
method that reaches for ``self``. That is what lets the phases live in their own
modules at all: a counter written through ``self`` cannot cross a module
boundary, and a counter written through a module-level ``global`` cannot either
(``render_settings``' docstring says why), so this counter is an object passed
as an argument.

Inheritance lives here too, next to the minting, because the two are one
decision: a split's pieces either inherit their parent's id or earn a fresh one,
and ``_inherit_glue`` is the single place that chooses.
"""

from md2ui.pipeline.grouper_types import MarkdownGroupNode


class IdMint:
    """The id counters of ONE document.

    Deliberately an object rather than two module-level integers: a grouper
    holds one, two groupers never share, and nothing can mint an id without
    naming the mint it came from.
    """

    __slots__ = ("_glued", "_source_line")

    def __init__(self) -> None:
        self._glued = 0
        # A separate counter, not a shared one: per-physical-source-line ids
        # have distinct semantics from the consecutive-line segment ids above.
        self._source_line = 0

    def next_glued(self) -> int:
        """Mint a fresh, document-unique glued-content segment id."""
        gid = self._glued
        self._glued += 1
        return gid

    def next_source_line(self) -> int:
        """Mint a fresh, document-unique per-physical-source-line id."""
        sid = self._source_line
        self._source_line += 1
        return sid


def _inherit_source_line_id(
    parent: MarkdownGroupNode, children: list[MarkdownGroupNode]
) -> None:
    """Copy *parent*'s ``source_line_id`` onto id-less *children*.

    Every intra-line split goes through this: all its pieces belong to the
    parent's one physical line. Only ``_inherit_glue`` calls it."""
    if parent.source_line_id is None:
        return
    for c in children:
        if c.source_line_id is None:
            c.source_line_id = parent.source_line_id


def _inherit_glue(
    parent: MarkdownGroupNode,
    children: list[MarkdownGroupNode],
    ids: IdMint,
) -> None:
    """Copy *parent*'s ``glued_content_id`` onto split *children* that lack
    one. Every splitter except the blank-line split stays within a single
    glued content-segment, so its children belong to the parent's segment.
    Non-overwrite: a child that already carries an id (set at an earlier
    origin) is left untouched.

    When *parent* has no id (a lone source line — never glued at the
    to_ast origin) and the split produced >= 2 pieces, a fresh segment id
    is minted for the pieces: content separated out of a single line is
    one glued segment of its own. The id goes on the children only, never
    the parent — _wrap_glued_content / _collapse_groups place the
    ``glued_content_group`` flag from there. Heading containers are
    excluded (a split standalone heading must not become a glued card).

    O(len(children))."""
    # Per-source-line id: an intra-line split never crosses a line, so every
    # id-less piece inherits the parent leaf's line id (pure inheritance, no
    # mint). No-op for splits that run before _assign_source_line_ids stamps
    # (parent id still None then); those leaves are stamped directly later.
    _inherit_source_line_id(parent, children)
    if parent.glued_content_id is None:
        if len(children) < 2 or parent.type.startswith("heading"):
            return
        gid = ids.next_glued()
        for c in children:
            if c.glued_content_id is None:
                c.glued_content_id = gid
        return
    for c in children:
        if c.glued_content_id is None:
            c.glued_content_id = parent.glued_content_id
