"""The grouper's data model: the node every later stage reads.

``MarkdownGroupNode`` is the tree the whole pipeline is built around — the grouper
produces it, the layout generator consumes it, and the renderer measures and
paints it. ``NodeType`` is the closed set
of kinds a node can be.

Also here: the two classifications that are properties of a node's CONTENT rather
than of the grouping algorithm — ``_classify_link_content`` (which link variant a
piece of markup denotes) and ``normalize_emoji_kind``.

This module exists so that everything downstream can name the node type without
importing the grouper that builds it. It depends on nothing else in the
pipeline, which is what makes that possible.
"""

import re
from enum import Enum, StrEnum
from typing import NamedTuple

from md2ui.pipeline.data_point_detector import EMOJI_CHAR_PATTERN
from md2ui.pipeline.render_text import LINK_DESTINATION, LINK_LABEL, OVERFLOW_MARKS


class NodeType(StrEnum):
    TEXT = "text"
    KEY = "key"
    VALUE = "value"
    GROUP = "group"
    KEY_VALUE = "key-value"
    SEGMENT = "segment"
    IMAGE = "image"
    LINK = "link"
    EMOJI = "emoji"
    BOLD = "bold"
    ITALIC = "italic"
    STRIKETHROUGH = "strikethrough"
    INLINE_CODE = "inline_code"
    CODE_BLOCK = "code_block"
    LIST_ITEM = "list_item"
    ORDERED_ITEM = "ordered_item"
    TASK_OPEN = "task_open"
    TASK_DONE = "task_done"
    DRAWING_ELEMENT = "drawing_element"
    BLOCKQUOTE = "blockquote"
    BULLET_POINT = "bullet_point"
    TABLE_HEADER = "table_header"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    HORIZONTAL_RULE = "horizontal_rule"
    # A ``___`` line: splits a group in two and paints NOTHING. The
    # level-agnostic sibling of an empty ``# `` / ``## `` marker — those open a
    # section at their heading level (and take that level's card and spacing);
    # this one only cuts, which is what breaking up a repeated-element grid
    # needs.
    CONTENT_BREAK = "content_break"
    # A ``***`` line: closes the heading section holding it, so everything after
    # it is lifted out to the section's PARENT as its next sibling. Purely a
    # Phase 1 instruction — _apply_section_stops consumes every one of these, so
    # the type never reaches the finished tree and nothing downstream sees it.
    SECTION_STOP = "section_stop"
    # A ``:::`` line: cuts like ``___`` and paints nothing, but the runs either
    # side of it become CELLS OF ONE ROW instead of a stack. The block-level
    # twin of the same-line ` : ` column split. Carries an optional
    # ``column_weight`` (``:::2``) that proportions the cell ABOVE it. Purely a
    # Phase 1 instruction, like SECTION_STOP — _build_column_rows consumes every
    # one of these, so the type never reaches the finished tree.
    COLUMN_DIVIDER = "column_divider"
    # A line holding nothing but ``...``: the VERTICAL twin of the inline spring.
    # It pushes the blocks either side of it to the top and bottom of the space
    # the column was given, the way ``... `` pushes the pieces of one line to
    # opposite edges. Purely a Phase 1 instruction, like SECTION_STOP and
    # COLUMN_DIVIDER -- ``build_vertical_springs`` consumes every one of these,
    # so the type never reaches the finished tree.
    VERTICAL_SPRING = "vertical_spring"
    # A ``;;;`` line: closes a ``:::`` row WITHOUT ending the run, so rows that
    # repeat stay siblings and grid. ``___`` ends the run; this ends one row
    # inside it. A Phase 1 instruction -- ``build_column_rows`` consumes every one.
    ROW_CLOSER = "row_closer"
    # A line holding nothing but ``+++`` / ``++++`` / ``+++++``: blank space the
    # author asked for (ADR-203). ``grouper_spacers`` puts it into the tree
    # after every grouping decision, and the fingerprint silences it, so a
    # card with a spacer matches one without.
    SPACER = "spacer"
    DATAPOINT = "datapoint"
    # An image whose alt slot held markdown (``![ ## Title … ](hero.png)``):
    # a card whose children are that markdown and whose background is the
    # image. A distinct type, not a flag on GROUP, because _collapse_groups
    # would unwrap a single-child GROUP, _subgroup_content's absorb branch
    # would rewrite its type, and _build_fingerprint would hash it the same as
    # an ordinary group of the same children.
    IMAGE_CARD = "image_card"


# Node label of a heading, e.g. "heading2" → 2.
_HEADING_TYPE_RE = re.compile(r"^heading(\d)$")


def same_section_kind(outer: "MarkdownGroupNode", inner: "MarkdownGroupNode") -> bool:
    """False when *outer* and *inner* are two DIFFERENT painted containers.

    Two heading sections at different levels each take their fill, padding,
    radius and scrim from their own level in THEME.md, and an empty ``# ``
    marker is written precisely to open one around another. Dissolving either
    deletes styling the author asked for, so neither may absorb the other.
    A level is genuinely redundant only when the pair is the same KIND of
    container: the same heading level, or a pair in which at most one is a
    section at all.

    It lives here, in the shared node model, because TWO stages make the same
    mistake independently and must not disagree about it: ``_collapse_groups``
    in ``grouper_glue`` (three branches) and the transparent passthrough in
    ``layout_generator._decide_group``. Only a title-less wrapper can hold a
    section as its sole child, so the inner carries the real title; but
    title-less is not style-less, and dissolving the outer would also make the
    same markup paint differently depending on how many sections follow the
    marker.
    """
    if outer.heading_group and inner.heading_group:
        return outer.heading_level == inner.heading_level
    return True


# The three inline ELEMENT leaf kinds, in ONE place. `layout_generator` and
# `layout_render` import this rather than re-spelling the tuple, so EMOJI can
# never drop out of the element path its chips and links take. Plain strings so the layout side — which works on serialized nodes, not
# NodeType — can use it as-is (NodeType is a StrEnum, so they compare equal).
ELEMENT_LEAF_TYPES = ("link", "inline_code", "emoji", "drawing_element")

# Any list marker at the start of a line: unordered (- * +), ordered
# (1. 1)) and — via the [-*+] branch — task items (- [ ]). Gates indentation-aware
# continuation merging to list blocks, and lets a group link sit in an item.
_LIST_MARKER_RE = re.compile(r"^[-*+]\s|^\d+[.)]\s")

# The space a node records at its edges (ADR-203), each a spacer spelling.
_SPACER_EDGES = ("spacer_lead", "spacer_trail", "spacer_above", "spacer_below")

# Stands in for a `:::` or `...` line indented under a list item, from Phase 1 until the
# item's body is its own children (Phase 2.1): grouper_block_splits writes it,
# grouper_column_rows reads it. A private-use character, like the card
# sentinels: it cannot be typed by accident and matches no pattern.
ITEM_DIVIDER = "\ue130"

STRUCTURAL_BACKGROUND_KINDS: dict[str, str] = {
    NodeType.LIST_ITEM: "unordered_list",
    NodeType.TASK_OPEN: "task_list",
    NodeType.TASK_DONE: "task_list",
    NodeType.ORDERED_ITEM: "numbered_list",
    NodeType.BLOCKQUOTE: "quote",
}

_LINK_CONTENT_RE = re.compile(rf"^\[({LINK_LABEL})\]\({LINK_DESTINATION}\)$", re.DOTALL)
# ONE wrapper→variant rule for every element that has variants — links, emoji
# badges and chips. It reads by wrapper LENGTH, so each extra marker is one more
# step down the hierarchy, and ``_`` is a CommonMark synonym for ``*`` (chips
# and buttons excepted, below):
#
#   x        Primary        *x*      Secondary
#   **x**    Tertiary       ***x***  Quaternary
_ELEMENT_VARIANT_BY_LEN = {1: "secondary", 2: "tertiary", 3: "quaternary"}
# A CHIP and a BUTTON read ``_`` as their own family, the small ladder:
# `` _`x`_ `` / ``_[x](/y)_`` Quinary, ``__`` Senary, ``___`` Septenary. An emoji
# badge does not: its sizes are the asterisk ladder.
_CHIP_UNDERSCORE_VARIANT_BY_LEN = {1: "quinary", 2: "senary", 3: "septenary"}
# A button's two ladders by marker, and as (marker, variant) pairs, derived from
# the two tables above rather than repeated so they can never drift apart.
_LINK_LADDERS = {"*": _ELEMENT_VARIANT_BY_LEN, "_": _CHIP_UNDERSCORE_VARIANT_BY_LEN}
_LINK_VARIANT_WRAPPERS = tuple(
    (ch * n, by_len[n]) for n in (3, 2, 1) for ch, by_len in _LINK_LADDERS.items()
)


def _strip_wrap(s: str, marker: str) -> str | None:
    """*s* without a symmetric *marker* wrapper, or None if it isn't wrapped."""
    n = len(marker)
    if len(s) >= 2 * n + 1 and s.startswith(marker) and s.endswith(marker):
        return s[n:-n].strip()
    return None


# When a backtick label overrides the emphasis wrapper's variant, the emphasis
# would otherwise be discarded. It is kept as a face for the label instead —
# see _classify_link_content. Only the Text variant needs this: for the others
# the wrapper IS the variant, whose weight comes from ## Text Styles.
# Derived from the wrapper LENGTH, not hand-written per variant name: the face a
# displaced wrapper leaves behind follows the MARKER (`*` italic, `**` bold,
# `***` bold-italic), which is fixed by CommonMark — while which variant a given
# marker selects is this project's own choice.
_EMPHASIS_BY_LEN = {1: "italic", 2: "bold", 3: "bold_italic"}
_EMPHASIS_FROM_VARIANT = {
    by_len[n]: _EMPHASIS_BY_LEN[n]
    for n in (1, 2, 3)
    for by_len in _LINK_LADDERS.values()
}


def _classify_link_content(content: str) -> tuple[str, str, bool, bool, str | None]:
    """Classify a LINK node's raw content into
    (variant, display_label, is_emoji, is_disabled, emphasis).

    Detected once here (at AST build/serialize time) instead of at every
    layout_render.py measure/draw call site, so the renderer only ever does
    an O(1) lookup. ``variant`` is one per markdown wrapping — primary /
    secondary (``*``) / tertiary (``**``) / quaternary (``***``) / quinary
    (``_``) / senary (``__``) / septenary (``___``) / text (a backtick label).
    Underscores are the small ladder, as for chips, not synonyms of asterisks.

    ``~~`` around the whole thing is a STATE, not a variant and not a text
    decoration: ``~~**[x](/y)**~~`` is a Secondary button drawn in Secondary's
    disabled colors. It is peeled first so the variant underneath still shows
    through, exactly like ``is_emoji`` rides on top of a variant rather than
    replacing it. No strikethrough rule is ever drawn through a link.

    Precedence: an outer backtick wrap (Text) is checked after the emphasis
    wrap and overrides it, so ``[`❤️ x`](/link)`` is Text with is_emoji=False
    (mixed content) and ``[`❤️`](/link)`` is Text with is_emoji=True (forcing
    Text's own emoji shape) — never a different style.

    ``emphasis`` ("italic" / "bold" / "bold_italic") is the wrapper that the
    backtick override displaced, kept so ``**[`x`](/y)**`` can draw its label
    bold while staying the pure-text variant. It is set ONLY on that override:
    everywhere else the wrapper already became the variant, and forcing a face
    there would override the ``Font weight`` that variant configures.
    """
    s = content.strip()

    inner = _strip_wrap(s, "~~")
    is_disabled = inner is not None
    if inner is not None:
        s = inner

    variant = "primary"
    for marker, name in _LINK_VARIANT_WRAPPERS:
        inner = _strip_wrap(s, marker)
        if inner is not None:
            variant, s = name, inner
            break

    m = _LINK_CONTENT_RE.match(s)
    label = m.group(1) if m else s

    emphasis = None
    if label.startswith("`") and label.endswith("`") and len(label) >= 2:
        emphasis = _EMPHASIS_FROM_VARIANT.get(variant)
        variant, label = "text", label[1:-1].strip()

    stripped = label.replace("‍", "").replace(" ", "")  # ZWJ joiners
    is_emoji = stripped in OVERFLOW_MARKS or bool(
        stripped and EMOJI_CHAR_PATTERN.fullmatch(stripped)
    )
    return variant, label, is_emoji, is_disabled, emphasis


# A destination on its own, for a scanner that finds the parentheses itself.
LINK_DESTINATION_RE = re.compile(LINK_DESTINATION)
# The same shape as _LINK_CONTENT_RE, with the destination captured.
_LINK_DESTINATION_RE = re.compile(
    rf"^\[(?:{LINK_LABEL})\]\(({LINK_DESTINATION})\)$", re.DOTALL
)


def link_destination(content: str) -> str | None:
    """The destination of a LINK node's raw content, or None if it has none.

    Peels exactly what ``_classify_link_content`` peels — the ``~~`` state, then
    one emphasis wrapper — so the link grammar lives in one place. Returned raw:
    a CommonMark title, ``<…>`` brackets and the scheme are the reader's business
    (``render_actions.action_for``).
    """
    s = content.strip()
    inner = _strip_wrap(s, "~~")
    if inner is not None:
        s = inner
    for marker, _name in _LINK_VARIANT_WRAPPERS:
        inner = _strip_wrap(s, marker)
        if inner is not None:
            s = inner
            break
    m = _LINK_DESTINATION_RE.match(s)
    return m.group(1) if m else None


class _CardSpec(NamedTuple):
    """A block-content construct pulled out of the source by the scanner."""

    is_image: bool
    url: str
    inner: str  # the body markdown, already normalised
    raw: str  # the original construct, for the restore fallback


# A one-line link label that lays itself out (``_BracketConstruct.is_group_link``):
# a spaced ` ... ` spring between two words. An escaped mark is text, as on any line.
_ROW_LABEL_RE = re.compile(r"\S \.\.\. \S")
_ESCAPED_MARK_RE = re.compile(r"\\.")


class _BracketConstruct(NamedTuple):
    """A ``[label](url)`` / ``![alt](url)`` span located in raw markdown."""

    start: int  # index of the opening "[" (or of "!" for an image)
    end: int  # index just past the closing ")"
    is_image: bool
    inner: str  # raw text between the brackets
    url: str  # raw text between the parens
    raw: str  # the whole construct, verbatim

    def is_group_link(self, text: str) -> bool:
        """A link alone on its lines, or a list item's whole content, whose label
        holds two glued lines, or one line that lays itself out: a card of those
        lines, not a pill. A one-line label without layout stays a pill, an
        image's alt is metadata, and a link wrapped inside a sentence is prose.

        A one-line label lays itself out when it holds a spaced ` ... ` spring
        (``_ROW_LABEL_RE``). A pill is only as wide as its words, so a spring
        means nothing inside one; it can only mean a row. Inside the row every
        mark divides as on any line, ` - ` included. A ` - ` alone never makes
        a row: names carry one (`[Amazon - Echo Show 11](…)`)."""
        before = text[text.rfind("\n", 0, self.start) + 1 : self.start].lstrip()
        if m := _LIST_MARKER_RE.match(before):
            before = before[m.end() :]  # a list item's content is a line of its own
        after = text[self.end :].split("\n", 1)[0]
        lines = [line.strip() for line in self.inner.split("\n")]
        glued = any(a and b for a, b in zip(lines, lines[1:]))
        row = sum(1 for line in lines if line) == 1 and bool(
            _ROW_LABEL_RE.search(_ESCAPED_MARK_RE.sub("", self.inner))
        )
        return (
            (glued or row)
            and not self.is_image
            and not (before.strip() or after.strip())
        )


def normalize_emoji_kind(kind: str | None) -> str | None:
    """Migrate a persisted ``emoji_kind`` to the current spelling.

    ``peeled`` is an old name for ``text``; grouping AST files on disk can
    still carry it.

    Every path that loads a persisted AST must call this. Otherwise the
    generator can measure a ``text`` emoji while the drawer treats the same
    node as a badge, breaking the shared measure-and-paint contract.
    """
    return "text" if kind == "peeled" else kind


class MarkdownGroupNode:
    """A single node in the markdown heading AST.

    Complexity variables (shared with MarkdownGrouper):
        N = total characters in the input text
        K = number of nodes currently in the AST
    """

    def __init__(self, content: str = "", type: str = ""):
        self.content = content
        self.type = type
        self.glued_content_id: int | None = None
        # True when this group node IS a source-glued segment (a run of content
        # glued together in the markdown source). It is a property of a group
        # node — not a node type — and its direct children each carry the same
        # ``glued_content_id``. Set by _wrap_glued_content / _collapse_groups.
        self.glued_content_group: bool = False
        # True when this group node's direct children are the pieces of ONE
        # physical source line (separator segments, comma lists, datapoint
        # splits, boundary emoji/link peels, KV value sub-splits, inline-code
        # peels, image splits) — so the layout renders them aside (horizontal)
        # instead of stacking each on its own line. It is a DERIVED value:
        # _derive_line_split_groups (Phase 6.1) sets it purely from
        # ``source_line_id`` — a group qualifies iff it has >=2 content children
        # that all share one non-None source_line_id (gated off glued cards and
        # heading containers), never at the individual split sites.
        self.line_split_group: bool = False
        # True on a group whose children are the buttons of ONE choice divided
        # by ` | ` (ADR-405): segmented if the theme says. Stamped in Phase
        # 6.246 (grouper_choices.is_segmented_run); read by render_segmented.
        self.segmented_run: bool = False
        # The feed slots this node draws, each a range of content (grouper_feed_slots).
        self.feed_slots: tuple[dict, ...] = ()
        # True when this group node's children are the pieces of a spaced-colon
        # COLUMN split ("94% : Accuracy") — the authored way to stack same-line
        # content. Its children share a source line like any other same-line
        # split, so without this flag _derive_line_split_groups would flag them
        # line_split_group and flow them along the line, which is the exact
        # opposite of what the author asked for. Set by the colon split in
        # _separate_structured_content_walk; read (never re-derived) by the
        # generator.
        self.column_split_group: bool = False
        # The cell weight an author wrote on a ``:::N`` COLUMN_DIVIDER leaf. It
        # proportions the cell ABOVE the divider, which is why it rides the
        # divider rather than the cell: every cell but the last already has a
        # divider under it, so a weight always has somewhere to go without extra
        # syntax, and the last cell's divider is optional (an unweighted cell is
        # 1). Lives only until _build_column_rows folds it into the row's
        # ``column_weights``; nothing downstream of Phase 1 sees it.
        #
        # A float, because ratios are floats the whole way down; ``0`` means "no
        # share of the surplus", which the generator floors at the cell's own
        # minimum width rather than collapsing to nothing.
        self.column_weight: float | None = None
        # The divider's other two slots (``::: 1 1.5``, ``::: 1 <``): the weight
        # in WIDE space when a second number was written, and the space the cut
        # applies in — ``"narrow"``, ``"wide"``, or ``None`` for both. Folded
        # into the row with the weight.
        self.column_weight_wide: float | None = None
        self.column_when: str | None = None
        # True when this group node's children are the CELLS of a ``:::`` column
        # row — the authored way to arrange BLOCKS side by side, as
        # ``column_split_group`` is for the pieces of one line. Set by
        # ``build_column_rows`` in Phase 1, read (never re-derived) by the
        # generator, which turns it into a ``row`` whose ratios are
        # ``column_weights``.
        #
        # It is a plain structural wrapper: never glued, never a card. A ``:::``
        # is not a glue decision — glue never spans a cut, is untouched inside a
        # cell, and this node itself carries none.
        self.column_row_group: bool = False
        # One weight per cell, in document order, aligned with ``children``.
        # Each comes from the ``:::N`` divider that CLOSED its cell; ``None``
        # when no number was written (a bare ``:::``, or the last cell's
        # optional divider left out). A row with no number at all collapses and
        # wraps like a `` - `` line; in a row with one, ``None`` is an equal
        # share (1). A weight of ``0`` means "no share of the surplus" — the
        # generator floors that cell at its own content width instead.
        self.column_weights: tuple[float | None, ...] = ()
        # Aligned with ``column_weights``, from the same dividers, and empty
        # unless one of them wrote it: each cell's weight in WIDE space
        # (``None``: the same as ``column_weights``), and the space the cut
        # AFTER each cell applies in (``"narrow"``, ``"wide"``, ``None``: both).
        # The generator picks by the width the row is offered; where a cut does
        # not apply, the cells either side of it stack as one.
        self.column_weights_wide: tuple[float | None, ...] = ()
        self.column_cuts: tuple[str | None, ...] = ()
        # True when this node's children are the REGIONS of a ``...`` vertical
        # spring split — the authored way to push blocks to the top and bottom
        # of the height they were given. The exact twin of ``align_group`` on
        # the other axis. Each region carries its own ``authored_valign``.
        self.valign_group: bool = False
        # This node's AUTHORED vertical alignment ("top"/"center"/"bottom"), set
        # on a spring region by the split above. Positional, like its horizontal
        # twin: the first region goes to the top, the last to the bottom, and
        # anything between them centres.
        self.authored_valign: str | None = None
        # The AUTHORED vertical alignment of this node's ROW — the mode its
        # cells share — from an end-of-line ``@tp`` / ``@ct`` / ``@bs`` / ``@bm``
        # token. Deliberately NOT ``authored_valign``: that one places ONE node
        # inside the box it was given (a spring region, an aside's text column)
        # and reaches the renderer as the cell-local ``content_valign``, while
        # this is the row's own mode and reaches it as ``line_align``. The two
        # read the same four words and mean different things, so they stay two
        # fields rather than one that has to be told apart by where it landed.
        self.line_valign: str | None = None
        # True when this group node's children are the REGIONS of a spring split
        # ("A ... B"), the authored way to push same-line content toward
        # opposite edges. Each region carries its own ``authored_align``; this
        # flag exists so _derive_line_split_groups keeps the line flowing along
        # its row even when every region is a container (the same exception
        # ``column_split_group`` gets), since regions that stack would defeat
        # the whole point of pushing them apart.
        self.align_group: bool = False
        # This node's AUTHORED horizontal alignment ("left"/"center"/"right"),
        # set on a spring region by the split above. It is the markdown source's
        # own opinion, so the layout generator applies it over everything the
        # run pin / URL params had to say — but only ever on THIS
        # node, never voted across a repeated run.
        self.authored_align: str | None = None
        # On a KEY_VALUE pair: ``(type, text)`` of the line it was cut from, as
        # written. A pair exists only while a display reads it (ADR-205): a
        # pair no display or control draws becomes that line again
        # (``grouper_pairs``). Never serialized.
        self.pair_source: tuple[str, str] | None = None
        # On a line that was a pair no display read: that pair, so ``check`` can
        # say why the chart it was a row of did not draw. Never serialized.
        self.unpaired: "MarkdownGroupNode | None" = None
        # The ROW separator characters this node's children were split at
        # (` - ` / ` • ` / ` | `), one per GAP in document order — a line can mix
        # them ("A • B | C - D"), so a single character would misreport. The
        # split consumes them, so this is the only record they were ever there;
        # the layout generator draws them back between the pieces when
        # ## Separators says to. Display-only: it never changes the tree, which
        # is what keeps the grouper theme-independent.
        self.separator_chars: list[str] = []
        # A SPACER's side (ADR-203): "prev" when it closes what came before it,
        # "next" when it opens what follows. Between two cells of a row the
        # position alone cannot say which cell the space is in.
        self.spacer_binds: str | None = None
        # A spacer at the start / end of this LINE (`+++ B`, `B +++`): its
        # spelling. Not a cut — a separator needs a piece on both sides — so
        # it is recorded here and the line groups exactly as it would without.
        self.spacer_lead: str | None = None
        self.spacer_trail: str | None = None
        # Set when that edge space was a `:::` cell of its own beside this node:
        # it is beside the box the node paints for itself, never inside it.
        self.spacer_beside = False
        # A spacer written above / below a ROW that the plain grouping merged
        # with its card: space down, between the card's edge and the row.
        self.spacer_above: str | None = None
        self.spacer_below: str | None = None
        self.separator_kind: str | None = None
        # Per-PHYSICAL-source-line identity. Stamped once on every content leaf
        # by _assign_source_line_ids at the point in the pipeline where each
        # leaf is exactly one source line (after the newline/list-body/image
        # passes), then INHERITED (never re-minted) by the intra-line splits via
        # _inherit_glue — which never cross a line, so all pieces of one line
        # share its id. Distinct from ``glued_content_id`` (a whole
        # consecutive-line *block* segment), which must not be overloaded for
        # per-line grouping. A group's effective line id is the common non-None
        # id of its content children, else None. Serialized unconditionally so
        # the layout generator (run same-line gate) can consume it after
        # from_dict reconstruction.
        self.source_line_id: int | None = None
        # True when this group node IS a heading section container (the group the
        # grouper builds to own a heading + its nested content). ``heading_level`` is
        # the heading level (1-6). Set in to_ast; propagated through _collapse_groups.
        # The layout generator reads these to mark section backgrounds/padding/spacing,
        # instead of guessing from heading-typed leaves.
        self.heading_group: bool = False
        self.heading_level: int | None = None
        # What a GROUP's leaves all are, stamped once on the finished tree
        # (``_stamp_leaf_kinds``) so the generator never walks a subtree to ask:
        # ``pure_element`` — every leaf is a pill (``ELEMENT_LEAF_TYPES``);
        # ``key_side`` — every leaf is a KV ``key``. Both need ≥1 leaf.
        self.pure_element: bool = False
        self.key_side: bool = False
        # On the ROOT only: the shallowest heading-section level anywhere in the
        # document, its own top rank (a page of ``## `` bands has 2).
        self.top_heading_level: int | None = None
        # On a LEAF written as a heading inside another block (`- # Title`): the
        # ATX level, its `#` marker dropped from ``content`` (Phase 6.18). 0 when
        # the leaf is not one.
        self.atx_level: int = 0
        # A standard trailing heading attribute (``{#id}``) belongs to the
        # whole section, not its visible title leaf.  ``fixed_style_key`` is
        # the lowercase kebab id with its final positive numeric suffix removed;
        # it is only a candidate until the Theme resolves it.
        self.heading_id: str | None = None
        self.fixed_style_key: str | None = None
        # The nearest heading section's fixed-style candidate, reset by every
        # nested ordinary heading.  Generator/render consumers use it alongside
        # heading_level instead of re-parsing heading text.
        self.section_style_key: str | None = None
        # The heading level whose LINE this node was split out of, so every
        # piece of a split heading keeps that heading's text style. Nothing here
        # sets it: it is derived at render time from the node's own
        # heading{N}/source_line_id by layout_render._stamp_heading_ctx, and is
        # intentionally NOT serialized (declared here only so the attribute has
        # one documented home). Distinct from ``heading_level``, which marks the
        # heading content GROUP — a whole section, body lines included.
        self.heading_ctx: int = 0
        # True when this group node IS a table container (owns a contiguous
        # run of table_header/table_row children). Set in _flag_table_groups;
        # the layout generator reads it to build the deterministic table
        # layout instead of guessing from child types. ``table_role`` is set
        # only on TABLE_CELL leaves: "header" | "body", so the renderer maps
        # each cell straight to its THEME.md table style. ``table_align`` rides
        # the same leaves: the column's authored alignment from the markdown
        # delimiter row (":---" left / ":---:" center / "---:" right), or None
        # for a colon-less column, which is GFM's "no alignment specified" and
        # so inherits the theme / the enclosing section's cascade.
        self.table_group: bool = False
        self.table_role: str | None = None
        self.table_align: str | None = None
        # Which drawn datapoint element replaces this node's text rendering
        # (None = ordinary text). Set in Phase 6.06 (_annotate_datapoint_displays)
        # so the layout generator/renderer never re-derive the pattern:
        #   "ratio_bar"       bare `4/8` leaf → bar + ratio text beside it
        #   "unit_ratio"      ratio + one-word unit (`750/1800 Kcal`, `75/100g`,
        #                     `Minutes: 7/8`) → bar or circular ring
        #   "kv_percent_bar"  `Key: 50%` pair → key/value text + progress bar
        #   "line_chart"      `Key: $1 → $2 → $3` pair → key, last value + a line
        #   "date_chip"       `Mon 15` / `Jun 15` leaf → weekday/month day chip
        # ``datapoint_payload`` carries the self-contained numeric payload
        # (value/max/unit/percent/day/...) — data_points are NOT restored by
        # from_dict, so the payload must survive the JSON round-trip on its own.
        self.datapoint_display: str | None = None
        self.datapoint_payload: dict | None = None
        # A non-text visual authored in Markdown. ``kind`` selects the drawing
        # family and the remaining keys are its serialized semantic payload;
        # geometry and paint remain theme-owned. The first family is
        # ``{"kind": "task_control", "checked": bool}``.
        self.drawing_element: dict | None = None
        # Authored display tier: "muted" | "lead" | "display" (None = ordinary
        # text). Set in Phase 6.055 (_annotate_text_style_tiers) when a WHOLE
        # leaf was wrapped in underscores — `_x_` / `__x__` / `___x___` — and the
        # wrapper is stripped from ``content`` at the same time, the way
        # _split_elements consumes backticks when it retypes a node.
        # Underscores are CommonMark synonyms for asterisks, so mid-sentence
        # `__x__` still means plain bold and is deliberately NOT a tier: the
        # renderer re-parses those markers out of ``content``.
        self.text_style: str | None = None
        # True when this group node IS a chart container (a bullet run of
        # Key: value rows in one unit, single- or multi-series). Set in Phase 6.07
        # (_flag_chart_groups), mirroring table_group. ``chart_data`` is the
        # serialized series/rows payload:
        #   {"series": [name, ...] | None, "unit": "%" | "currency USD" | ...,
        #    "rows": [{"label": str, "values": [float, ...],
        #              "texts": [the values as written, ...]}, ...]}
        self.chart_group: bool = False
        self.chart_data: dict | None = None
        # True when this group node IS several lines on one axis: a bullet run
        # of ``Key: a → b → c`` items with the same number of points in one
        # unit (_flag_line_groups, ADR-204). Its own flag, never a kind of
        # chart_group, whose rows `mark` and `feed` move. ``line_data``:
        #   {"series": [{"name": str, "points": [point, ...]}, ...],
        #    "labels": [str | None, ...], "display_unit": str | None}
        # where a point is a line_chart payload's point.
        self.line_group: bool = False
        self.line_data: dict | None = None
        # Set only on LINK-typed nodes: which of the 5 button styles this link
        # renders as (primary/secondary/tertiary/quaternary/text), its
        # display label with the markdown markers (``*``/``_``/``~~``/`` ` ``)
        # already stripped, and two orthogonal booleans that ride ON TOP of the
        # variant rather than replacing it —
        #   ``link_is_emoji``  a pure-emoji label, which forces that same
        #                      variant's configured circle/square shape (there
        #                      is no separate "emoji" style)
        #   ``link_disabled``  a ``~~`` wrapper, which swaps in that same
        #                      variant's disabled colors. ``~~`` is a STATE on a
        #                      link, never a strikethrough rule.
        # Classified once here from ``content`` via _classify_link_content so
        # layout_render.py never has to re-parse markdown at render time.
        self.link_variant: str | None = None
        self.link_label: str | None = None
        self.link_is_emoji: bool = False
        self.link_disabled: bool = False
        # The emphasis wrapper a backtick label displaced ("italic" /
        # "bold" / "bold_italic"), drawn as the label's FACE so
        # ``**[`x`](/y)**`` stays the pure-text variant but reads bold.
        self.link_emphasis: str | None = None
        # Set on EMOJI / INLINE_CODE leaves whose WHOLE content was wrapped in
        # emphasis: "secondary" (*x*) | "tertiary" (**x**) | "quaternary"
        # (***x***), by wrapper LENGTH. Captured at peel time — the markers are
        # gone from ``content`` by then — and only when the wrapper contained
        # exactly this element, so ``**🗓 Calendar**`` leaves its emoji Primary.
        self.emoji_variant: str | None = None
        self.code_variant: str | None = None
        # The same leaves wrapped in ``~~``: muted, the ``link_disabled`` of a
        # badge or chip. A STATE, drawn in muted colours, never a strike.
        self.element_muted: bool = False
        # Authored info-string lexer alias on a fenced CODE_BLOCK. ``None`` for
        # an indented block or a fence with no language. The renderer consumes
        # this annotation; it never guesses a language from the source text.
        self.code_language: str | None = None
        # Set on IMAGE_CARD nodes: the URL painted as the card's background.
        # The card's children are the markdown that sat in the alt slot.
        self.card_bg_url: str | None = None
        # Set on any node that a block-content link wraps (``[ ## Title … ](/x)``).
        # Pure annotation — the renderer draws nothing for it; it marks the
        # subtree as clickable for a future renderer. A block-content link is
        # therefore an ordinary GROUP, not a type of its own, so it cannot
        # change fingerprints (and thus layout). _collapse_groups propagates it
        # the way it propagates glued_content_group, so collapsing the wrapper
        # away leaves the annotation on whatever survives.
        self.link_url: str | None = None
        # Set only on EMOJI-typed nodes: which render role this emoji plays —
        # "heading" (inside a heading section/leaf), "text" (its CONTAINER
        # styles it as text: a K-V key or a table cell) or "alone" (an element,
        # drawn as the Primary badge — the default, because an EMOJI node only
        # exists where the author separated it). Classified
        # once in Phase 6.2 (_stamp_finished_tree) from the final tree's
        # container context, so layout_render.py maps it straight to a
        # THEME.md emoji block (heading/alone → Primary, text → Text) without
        # re-deriving context per draw. ``emoji_index`` is the emoji's ordinal
        # among its EMOJI siblings, letting the renderer cycle a per-source
        # Icon color array across sibling emojis.
        self.emoji_kind: str | None = None
        self.emoji_index: int = 0
        # The node's slot in its COLOR ROTATION cycle: its ordinal among the
        # same-channel peers of the section that encloses it (nearest strict
        # ancestor heading_group, or the document root). A channel is what a
        # THEME.md color list cycles over — the heading level for a section, the
        # variant for an emoji/link/chip, "card" for a glued group — so one int
        # per node is enough (a node belongs to exactly one channel). The
        # renderer indexes every multi-color list with it; a single-color list
        # ignores it, so a theme that never lists two colors never rotates.
        # Stamped in Phase 6.25
        # (_annotate_rotation_indices); a heading section lends its own slot to
        # its title text, so `Background color:` on ### Heading 3 and `Font
        # color:` on Heading3 land on the same color.
        self.rotation_index: int = 0
        # Parallel slot among headings sharing one fixed-style candidate. The
        # normal rotation_index remains level-based so an unmatched authored ID
        # cannot perturb existing Heading N color rotation; the generator picks
        # this slot only when the loaded Theme contains the candidate key.
        self.fixed_rotation_index: int = 0
        # The heading levels of the sections enclosing this node, outermost
        # first — a node's OWN section level is not in it, since a level gates
        # what sits inside it, not itself. The renderer walks it innermost-out
        # to find the first level that states a ``Rotate <kind> colors`` gate.
        # Stamped by the same Phase 6.25 pass and serialized, so the layout
        # generator can hand it to a container's background box (which has no
        # content_id to look a node up with).
        self.rotation_chain: tuple[int | str, ...] = ()
        # Styling scopes enclosing this node, outermost first. Unlike
        # ``rotation_chain`` this includes named structural surfaces and always
        # begins with ``root``. The renderer consumes it for property-by-property
        # local text-role inheritance; it never re-infers ancestry from layout.
        self.text_style_chain: tuple[str, ...] = ()
        # The SLOT each of those ancestor sections took, aligned one-to-one with
        # ``rotation_chain``. It is what lets an element borrow its card's color
        # instead of its own: a chip in the third card counts 0,1,2 among its
        # fellow chips, but its path says the card it sits in drew slot 2. Read
        # by ``Rotate colors: sync``.
        self.rotation_path: tuple[int, ...] = ()
        # Set on an EMOJI leaf peeled from a K-V KEY (its direct parent is a
        # ``key`` node). The renderer styles it with the ``Keys`` text style
        # (size + color) so a key emoji matches its key text. Stamped in
        # Phase 6.2 (_stamp_finished_tree).
        self.in_key: bool = False
        # Set only on ORDERED_ITEM nodes: the ordinal to DRAW. A run seeds it
        # from the first item's ``list_number`` and counts up from there, so a
        # list written 1./1./1. still renders 1,2,3 while one written 3./4.
        # renders 3,4. Consumed by the layout generator's numbered gutter marker.
        self.list_ordinal: int | None = None
        # Set only on ORDERED_ITEM nodes: the number the AUTHOR wrote ("10." →
        # 10), captured by _split_all_lists before the marker is stripped.
        self.list_number: int | None = None
        # Set only on ORDERED_ITEM nodes split out of a heading (``## 1. Foo``):
        # that heading's level. The item's own heading flags are unset — the
        # section's heading_group/heading_level live two levels up — so this is
        # the annotation that lets the generator style a heading ordinal
        # differently from a plain list one, without guessing from the parent.
        self.list_heading_level: int | None = None
        # Transient: set on a blank-split multi-line piece (a paragraph segment
        # that is its own wrapper). Consumed by _wrap_glued_content; not
        # serialized.
        self._glue_root: bool = False
        self.node_id: str = ""
        self.children: list["MarkdownGroupNode"] = []
        self.fingerprint_hash: int | None = None
        # A *normalized* structural signature used only for "same-kind" grid
        # bucketing (repeated_children). Unlike fingerprint_hash it is order-
        # preserving but count- and split-depth-INSENSITIVE: consecutive
        # identical children fold to one, and inline micro-structure (segments,
        # datapoints, KV/value/list-item split detail) collapses to a single
        # leaf token. Node *types* are always preserved, so unrelated group
        # shapes never collide. Live-only (like repeated_children); NOT
        # serialized — the tree/fingerprint_hash are untouched. Computed by
        # _build_fingerprint. See ASTPatternAnalyzer._build_fingerprint.
        self.kind_hash: int | None = None
        # Shared id of the contiguous same-kind *run* this node belongs to
        # (>=2 members), assigned by _build_fingerprint's run segmentation. Two
        # cards share a run_key when they are exact-kind equal OR within the ±1
        # tolerance (see _KIND_TOLERANCE_*). This is the key the layout grid
        # buckets on; unique per parent+position so non-adjacent look-alikes
        # never share one. Live-only (like repeated_children); NOT serialized.
        self.run_key: int | None = None
        self.repeated_children: dict[int, list["MarkdownGroupNode"]] | None = None
        # True on a lone child that is the sole member of a repeated KIND its
        # sibling groups grid (e.g. the single product in `### Meat & Poultry`
        # when sibling `### ` sections grid multiple products of that kind). The
        # layout generator grids it at the siblings' card width instead of full
        # width. Set by ASTPatternAnalyzer._annotate_orphans. Live-only (like
        # repeated_children); NOT serialized.
        self.orphan_grid: bool = False
        self.data_points: list[dict] = []
        # Live-only split-criteria cache; deliberately omitted from to_dict().
        # Typed to the stdlib base rather than
        # Criterion so this shared leaf never imports a pipeline stage.
        self.applicable: frozenset[Enum] | None = None
        self.avg_word_count: float | None = None
        self.text_length_category: str | None = (
            None  # "one_word" | "very_short" | "short" | "medium"
            #     | "paragraph" | "long_paragraph"
        )
        # Per-node length from this node's OWN word count (leaves) or the MAX of
        # its descendants (groups = widest line). Same category vocabulary as
        # text_length_category, but per-node instead of fingerprint-cluster-average
        # — used by the layout generator's min-width so genuinely short elements
        # aren't held at the cluster's (larger) category.
        self.content_length_category: str | None = None
        self.child_types: list[str] = []
        self.child_type_counts: dict[str, int] = {}
        self.paren_quote_ranges: list[tuple[int, int]] = []

    def take_column_row(self, row: "MarkdownGroupNode") -> None:
        """Become the ``:::`` row *row* is, when its cells are lifted into this
        node: the flag and everything that describes those cells travel together.
        """
        self.column_row_group = row.column_row_group
        self.column_weights = row.column_weights
        self.column_weights_wide = row.column_weights_wide
        self.column_cuts = row.column_cuts

    def to_dict(self) -> dict:
        """Recursively convert the node tree to plain dicts.

        Time:  O(K + N) — visits every node, copies all content.
        Space: O(K + N) — one dict per node plus all content strings.
        """
        d = {
            "node_id": self.node_id,
            "content": self.content,
            "type": self.type,
            "fingerprint_hash": self.fingerprint_hash,
            "children": [c.to_dict() for c in self.children],
        }
        if self.glued_content_group:
            # The group node is flagged; each direct child carries the shared
            # segment id.
            d["glued_content_group"] = True
            for cd, c in zip(d["children"], self.children):
                if c.glued_content_id is not None:
                    cd["glued_content_id"] = c.glued_content_id
        if self.line_split_group:
            d["line_split_group"] = True
        if self.segmented_run:
            d["segmented_run"] = True
        if self.feed_slots:
            d["feed_slots"] = [dict(slot) for slot in self.feed_slots]
        if self.column_split_group:
            d["column_split_group"] = True
        if self.column_weight is not None:
            d["column_weight"] = self.column_weight
        if self.column_row_group:
            d["column_row_group"] = True
            d["column_weights"] = list(self.column_weights)
            if self.column_weights_wide:
                d["column_weights_wide"] = list(self.column_weights_wide)
            if self.column_cuts:
                d["column_cuts"] = list(self.column_cuts)
        if self.valign_group:
            d["valign_group"] = True
        if self.authored_valign is not None:
            d["authored_valign"] = self.authored_valign
        if self.line_valign is not None:
            d["line_valign"] = self.line_valign
        if self.align_group:
            d["align_group"] = True
        if self.authored_align is not None:
            d["authored_align"] = self.authored_align
        if self.separator_chars:
            d["separator_chars"] = list(self.separator_chars)
        if self.spacer_binds is not None:
            d["spacer_binds"] = self.spacer_binds
        for name in _SPACER_EDGES:
            if getattr(self, name) is not None:
                d[name] = getattr(self, name)
        if self.spacer_beside:
            d["spacer_beside"] = True
        # Unconditional (unlike glued_content_id, which only emits under a glued
        # parent): the generator's run same-line gate consults it on any node.
        if self.source_line_id is not None:
            d["source_line_id"] = self.source_line_id
        if self.heading_group:
            d["heading_group"] = True
            d["heading_level"] = self.heading_level
            if self.heading_id is not None:
                d["heading_id"] = self.heading_id
            if self.fixed_style_key is not None:
                d["fixed_style_key"] = self.fixed_style_key
        if self.pure_element:
            d["pure_element"] = True
        if self.key_side:
            d["key_side"] = True
        if self.top_heading_level is not None:
            d["top_heading_level"] = self.top_heading_level
        if self.atx_level:
            d["atx_level"] = self.atx_level
        if self.section_style_key is not None:
            d["section_style_key"] = self.section_style_key
        if self.table_group:
            d["table_group"] = True
        if self.table_role is not None:
            d["table_role"] = self.table_role
        if self.table_align is not None:
            d["table_align"] = self.table_align
        if self.datapoint_display is not None:
            d["datapoint_display"] = self.datapoint_display
        if self.datapoint_payload is not None:
            d["datapoint_payload"] = self.datapoint_payload
        if self.drawing_element is not None:
            d["drawing_element"] = self.drawing_element
        if self.text_style is not None:
            d["text_style"] = self.text_style
        if self.chart_group:
            d["chart_group"] = True
        if self.chart_data is not None:
            d["chart_data"] = self.chart_data
        if self.line_group:
            d["line_group"] = True
        if self.line_data is not None:
            d["line_data"] = self.line_data
        if self.card_bg_url is not None:
            d["card_bg_url"] = self.card_bg_url
        if self.link_url is not None:
            d["link_url"] = self.link_url
        # A card's content is empty by construction, so it must never take the
        # LINK branch below (which re-derives the variant from the markdown).
        if self.type == NodeType.LINK:
            (
                self.link_variant,
                self.link_label,
                self.link_is_emoji,
                self.link_disabled,
                self.link_emphasis,
            ) = _classify_link_content(self.content)
            d["link_variant"] = self.link_variant
            d["link_label"] = self.link_label
            if self.link_is_emoji:
                d["link_is_emoji"] = True
            if self.link_disabled:
                d["link_disabled"] = True
            if self.link_emphasis is not None:
                d["link_emphasis"] = self.link_emphasis
        if self.type == NodeType.EMOJI and self.emoji_kind is not None:
            d["emoji_kind"] = self.emoji_kind
        if self.type == NodeType.EMOJI and self.emoji_variant is not None:
            d["emoji_variant"] = self.emoji_variant
        if self.type == NodeType.INLINE_CODE and self.code_variant is not None:
            d["code_variant"] = self.code_variant
        if self.element_muted:
            d["element_muted"] = True
        if self.type == NodeType.CODE_BLOCK and self.code_language is not None:
            d["code_language"] = self.code_language
        if self.type == NodeType.EMOJI and self.in_key:
            d["in_key"] = True
        if self.emoji_index:
            d["emoji_index"] = self.emoji_index
        if self.rotation_index:
            d["rotation_index"] = self.rotation_index
        if self.fixed_rotation_index:
            d["fixed_rotation_index"] = self.fixed_rotation_index
        if self.rotation_chain:
            d["rotation_chain"] = list(self.rotation_chain)
        if self.text_style_chain:
            d["text_style_chain"] = list(self.text_style_chain)
        if self.rotation_path:
            d["rotation_path"] = list(self.rotation_path)
        if self.list_ordinal is not None:
            d["list_ordinal"] = self.list_ordinal
        if self.list_number is not None:
            d["list_number"] = self.list_number
        if self.list_heading_level is not None:
            d["list_heading_level"] = self.list_heading_level
        if self.avg_word_count is not None:
            d["avg_word_count"] = self.avg_word_count
        if self.text_length_category is not None:
            d["text_length_category"] = self.text_length_category
        if self.content_length_category is not None:
            d["content_length_category"] = self.content_length_category
        if self.child_types:
            d["child_types"] = self.child_types
        if self.child_type_counts:
            d["child_type_counts"] = self.child_type_counts
        if self.data_points:
            d["data_points"] = [
                {
                    "label": f"dp_{dp['type'].value}",
                    "matched": dp["matched"],
                    "value": self._serialize_dp_value(dp["value"]),
                    "start": dp["start"],
                    "end": dp["end"],
                }
                for dp in self.data_points
            ]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MarkdownGroupNode":
        """Reconstruct a node tree from a dict produced by to_dict()."""
        node = cls(content=d.get("content", ""), type=d.get("type", ""))
        node.node_id = d.get("node_id", "")
        node.fingerprint_hash = d.get("fingerprint_hash")
        node.glued_content_id = d.get("glued_content_id")
        node.glued_content_group = d.get("glued_content_group", False)
        node.line_split_group = d.get("line_split_group", False)
        node.segmented_run = d.get("segmented_run", False)
        node.feed_slots = tuple(d.get("feed_slots") or ())
        node.column_split_group = d.get("column_split_group", False)
        node.column_weight = d.get("column_weight")
        node.column_row_group = d.get("column_row_group", False)
        node.column_weights = tuple(d.get("column_weights") or ())
        node.column_weights_wide = tuple(d.get("column_weights_wide") or ())
        node.column_cuts = tuple(d.get("column_cuts") or ())
        node.valign_group = d.get("valign_group", False)
        node.authored_valign = d.get("authored_valign")
        node.line_valign = d.get("line_valign")
        node.align_group = d.get("align_group", False)
        node.authored_align = d.get("authored_align")
        node.separator_chars = list(d.get("separator_chars") or [])
        node.spacer_binds = d.get("spacer_binds")
        for name in _SPACER_EDGES:
            setattr(node, name, d.get(name))
        node.spacer_beside = d.get("spacer_beside", False)
        node.source_line_id = d.get("source_line_id")
        node.heading_group = d.get("heading_group", False)
        node.heading_level = d.get("heading_level")
        node.heading_id = d.get("heading_id")
        node.fixed_style_key = d.get("fixed_style_key")
        node.pure_element = d.get("pure_element", False)
        node.key_side = d.get("key_side", False)
        node.top_heading_level = d.get("top_heading_level")
        node.atx_level = d.get("atx_level", 0)
        node.section_style_key = d.get("section_style_key")
        node.table_group = d.get("table_group", False)
        node.table_role = d.get("table_role")
        node.table_align = d.get("table_align")
        node.datapoint_display = d.get("datapoint_display")
        node.datapoint_payload = d.get("datapoint_payload")
        node.drawing_element = d.get("drawing_element")
        node.text_style = d.get("text_style")
        node.chart_group = d.get("chart_group", False)
        node.chart_data = d.get("chart_data")
        node.line_group = d.get("line_group", False)
        node.line_data = d.get("line_data")
        node.card_bg_url = d.get("card_bg_url")
        node.link_url = d.get("link_url")
        node.link_variant = d.get("link_variant")
        node.link_label = d.get("link_label")
        node.link_is_emoji = d.get("link_is_emoji", False)
        node.link_disabled = d.get("link_disabled", False)
        node.link_emphasis = d.get("link_emphasis")
        node.emoji_variant = d.get("emoji_variant")
        node.code_variant = d.get("code_variant")
        node.element_muted = d.get("element_muted", False)
        node.code_language = d.get("code_language")
        node.emoji_kind = normalize_emoji_kind(d.get("emoji_kind"))
        node.in_key = d.get("in_key", False)
        node.emoji_index = d.get("emoji_index", 0)
        node.rotation_index = d.get("rotation_index", 0)
        node.fixed_rotation_index = d.get("fixed_rotation_index", 0)
        node.rotation_chain = tuple(d.get("rotation_chain") or ())
        node.text_style_chain = tuple(d.get("text_style_chain") or ())
        node.rotation_path = tuple(d.get("rotation_path") or ())
        node.list_ordinal = d.get("list_ordinal")
        node.list_number = d.get("list_number")
        node.list_heading_level = d.get("list_heading_level")
        node.avg_word_count = d.get("avg_word_count")
        node.text_length_category = d.get("text_length_category")
        node.content_length_category = d.get("content_length_category")
        node.child_types = d.get("child_types", [])
        node.child_type_counts = d.get("child_type_counts", {})
        node.children = [cls.from_dict(c) for c in d.get("children", [])]
        return node

    @staticmethod
    def _serialize_dp_value(value):
        """Recursively convert a data point value to a JSON-safe type.

        Handles Decimal, datetime, dict, list, and primitives.

        Time: O(V) where V = total size of value.
        """
        from datetime import datetime
        from decimal import Decimal

        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {
                k: MarkdownGroupNode._serialize_dp_value(v) for k, v in value.items()
            }
        if isinstance(value, list):
            return [MarkdownGroupNode._serialize_dp_value(v) for v in value]
        return value
