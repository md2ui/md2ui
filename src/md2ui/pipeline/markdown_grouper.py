import re
import textwrap

from md2ui.pipeline.grouper_types import (
    MarkdownGroupNode,
    NodeType,
    _HEADING_TYPE_RE,
    LINK_DESTINATION_RE,
    _BracketConstruct,
    _CardSpec,
    _LINK_CONTENT_RE,
)
from md2ui.pipeline.grouper_split_criteria import SplitCriteria
from md2ui.pipeline.grouper_spacers import (
    mark_inline_spacers,
    restore_inline_spacer_text,
    stamp_spacers,
    strip_spacer_lines,
)
from md2ui.pipeline.grouper_block_splits import (
    _BREAK_TYPES,
    _KEEP_WHEN_EMPTY,
    IMAGE_RE,
    INLINE_CODE_RE,
    _BLOCKQUOTE_LINE_RE,
    _LIST_MARKER_RE,
    _PARTITION_TYPES,
    _break_node_type,
    stamp_column_divider,
    _split_all_lists,
    _split_blank_lines,
    _split_blockquote,
    _split_images,
    _split_newlines,
    finish_lines,
    flat_label,
    glued_rules,
    glued_runs,
    scope_item_dividers,
)
from md2ui.pipeline.grouper_column_rows import (
    build_column_rows,
    build_item_rows,
    build_vertical_springs,
    hand_down_valign,
)
from md2ui.pipeline.grouper_code_blocks import (
    CodeBlockSpec,
    expand_code_blocks,
    extract_code_blocks,
    restore_code_blocks,
)
from md2ui.pipeline import grouper_charts, grouper_displays
from md2ui.pipeline.grouper_pairs import unpair_unread
from md2ui.pipeline.grouper_annotate import (
    _annotate_data_points_walk,
    _annotate_datapoint_displays,
    _annotate_rotation_indices,
    _detect_through_markers,
    _stamp_finished_tree,
    _stamp_leaf_kinds,
    _wrap_date_chip_groups,
)
from md2ui.pipeline.grouper_element_splits import (
    _split_elements,
    _split_emoji_clusters,
)
from md2ui.pipeline.grouper_drawing_elements import (
    protect_escaped_task_controls,
    restore_escaped_task_controls,
    split_task_controls,
    stamp_task_controls,
)
from md2ui.pipeline.grouper_sliders import (
    _SLIDER_RE,
    protect_escaped_sliders,
    restore_escaped_sliders,
    split_sliders,
    stamp_sliders,
)
from md2ui.pipeline.grouper_kinds import _fnv1a_64, _tree_similar, kind_signatures
from md2ui.pipeline.grouper_text_lengths import (
    _TEXT_LENGTH_CATEGORY_ORDER,
    _word_count_category,
    drawn_word_count,
)
from md2ui.pipeline.grouper_glue import (
    _collapse_groups,
    _is_datapoint_split_group,
    _wrap_glued_content,
    _wrap_lone_root_content,
)
from md2ui.pipeline.grouper_ids import IdMint, _inherit_glue
from md2ui.pipeline import grouper_feed_slots
from md2ui.pipeline.grouper_separate import _separate_structured_content_walk
from md2ui.pipeline.grouper_split_apply import (
    _apply_split_result,
    _flatten_empty_text,
    _hand_data_points,
    _partition_data_points,
)
from md2ui.pipeline.grouper_inline_marks import (
    _is_lone_emoji,
    _wrap_is_authored,
)
from md2ui.pipeline.grouper_escapes import (
    EARLY_ESCAPES,
    escapes_outside_code,
    row_cells,
)
from md2ui.pipeline.grouper_memo import memoized
from md2ui.pipeline.grouper_line_flow import (
    _derive_line_split_groups,
    consume_line_valigns,
)
from md2ui.pipeline.grouper_ranges import _is_intraword
from md2ui.pipeline.grouper_content_edits import keep_content
from md2ui.pipeline.data_point_detector import (
    DataPointDetector,
    DataPointType,
)
from md2ui.pipeline.detector_parsers import _parse_emoji
from md2ui.utils.image_params import destination_url


def _item_number(item: tuple) -> int | None:
    """The source ordinal a splitter attached to an item, or None.

    Splitters yield ``(label, text)``; ``_split_all_lists`` yields a third
    element for an ordered item — the number the author wrote — so it survives
    the ``1. `` marker being stripped off the text.
    """
    return item[2] if len(item) > 2 else None


# ----------------------------------------------------------------------
# Bracket-construct scanning (links / images, possibly multi-line)
# ----------------------------------------------------------------------

# A candidate that runs past either bound is abandoned. Without them a stray
# "[" scans to end-of-document before failing, making N stray brackets O(N^2).
_MAX_CONSTRUCT_LINES = 40
_MAX_CONSTRUCT_CHARS = 4000

# How many levels of *cards* may nest. An ordinary inline link inside a card is
# not a card and does not consume depth, so 2 covers the real shapes (a link
# card wrapping an image card). Past it a construct degrades to its label text.
_MAX_CARD_DEPTH = 2

# A block-content construct is swapped for this token while the document's
# block structure is built, so its own headings stay invisible to the
# document-level pass. Chosen to survive every line classifier: no leading
# "#"/"-"/"*"/"+"/digit-dot/">", no "|", never indented, not zero-width, and
# strip()-stable. It is expanded in Phase 2.13 and so never reaches the
# data-point detector.
_CARD_SENTINEL_FMT = "⟦md2ui-card-{}⟧"
_CARD_SENTINEL_RE = re.compile(r"⟦md2ui-card-(\d+)⟧")
_CARD_SENTINEL_MARK = "⟦"  # cheap "might contain one" pre-check


def _scan_bracket_constructs(text: str) -> list[_BracketConstruct]:
    """Find every *top-level* link / image construct in ``text``.

    A balanced scanner rather than a regex: the label may itself contain
    brackets (``[![](icon.svg)](/x)``), which ``\\[[^\\]]*\\]`` cannot count.
    Nested constructs are deliberately *not* returned — they live inside the
    enclosing construct's ``inner`` and are the caller's business.

    Backslash-escaped characters are skipped, so ``\\[not a link\\](x)`` is not
    reported. A construct may span lines inside its label; its destination is
    a link's (``LINK_DESTINATION``), so ``[card](/my file)`` is not one.

    Time: O(N) amortised — each candidate is bounded by _MAX_CONSTRUCT_CHARS /
    _MAX_CONSTRUCT_LINES, so a failed scan cannot walk the whole document.
    Space: O(number of constructs).
    """
    out: list[_BracketConstruct] = []
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        is_image = ch == "!" and i + 1 < n and text[i + 1] == "["
        if not is_image and ch != "[":
            i += 1
            continue

        open_idx = i
        bracket_idx = i + 1 if is_image else i
        limit = min(n, open_idx + _MAX_CONSTRUCT_CHARS)

        # Walk the label, counting nested brackets.
        j = bracket_idx + 1
        depth = 1
        lines = 0
        while j < limit:
            c = text[j]
            if c == "\\":
                j += 2
                continue
            if c == "\n":
                lines += 1
                if lines > _MAX_CONSTRUCT_LINES:
                    break
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        # "](" must be adjacent — a lone "[...]" is not a construct.
        if depth != 0 or j + 1 >= n or text[j] != "]" or text[j + 1] != "(":
            i += 1
            continue

        # Walk the URL, counting nested parens. A URL never spans lines.
        k = j + 2
        pdepth = 1
        while k < limit:
            c = text[k]
            if c == "\\":
                k += 2
                continue
            if c == "\n":
                break
            if c == "(":
                pdepth += 1
            elif c == ")":
                pdepth -= 1
                if pdepth == 0:
                    break
            k += 1
        if pdepth or k >= n or not LINK_DESTINATION_RE.fullmatch(text, j + 2, k):
            i += 1
            continue

        out.append(
            _BracketConstruct(
                start=open_idx,
                end=k + 1,
                is_image=is_image,
                inner=text[bracket_idx + 1 : j],
                url=text[j + 2 : k],
                raw=text[open_idx : k + 1],
            )
        )
        i = k + 1
    return out


class MarkdownGrouper:
    """Groups markdown text by heading levels and sub-criteria.

    Each subgroup method walks the AST and splits every node that still
    has raw ``content`` into new nodes.  When the split target is a
    non-leaf (already a ``group`` or a ``text`` with existing children),
    the new nodes are inserted *before* those existing children and the
    original node's content is cleared — document order is preserved.
    When the target is a leaf ``text`` node, the split pieces are
    spliced into the parent's children list in place of the original,
    avoiding a redundant wrapper group around the pieces.

    Typical usage::

        grouper = MarkdownGrouper(text)
        grouper.to_ast()
        grouper.subgroup_by_blank_lines()
        grouper.subgroup_by_all_lists()
        print(json.dumps(grouper.ast.to_dict(), indent=2))

    All ``subgroup_*`` methods return *self* so calls can be chained::

        ast = (MarkdownGrouper(text)
               .to_ast()
               .subgroup_by_blank_lines()
               .subgroup_by_all_lists()
               .ast)

    (The full pipeline is :meth:`process`; these are partial entry points.)

    Complexity variables used throughout this class:
        N = total characters in the input text
        L = total lines  (L <= N)
        H = number of headings  (H <= L)
        K = number of nodes currently in the AST (grows with subgroups)
        C = length of a single node's content string

    Key property: ``_subgroup_content`` moves text from ``content`` into
    new children — it never duplicates it.  Total content across all nodes
    is always <= N, so every subgroup pass stays O(N).  A full chain of S
    subgroup calls is O(S * N), effectively O(N) for a constant S.
    """

    HEADING_PATTERN = re.compile(r"^(#{1,6})\s")
    HEADING_ID_PATTERN = re.compile(r"(?:^|\s)\{#([^{}\s]+)\}\s*$")
    FIXED_STYLE_ID_PATTERN = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*)-([1-9][0-9]*)$")
    # Node labels produced by _split_all_lists / _split_blockquote, whose bodies
    # may be multi-line and need re-structuring like a mini-document.
    _LIST_ITEM_LABELS = frozenset(
        {
            NodeType.LIST_ITEM,
            NodeType.ORDERED_ITEM,
            NodeType.TASK_OPEN,
            NodeType.TASK_DONE,
            NodeType.BLOCKQUOTE,
        }
    )
    TABLE_BLOCK_RE = re.compile(
        r"(^\|.+\|\s*\n\|[\s:|-]+\|\s*\n(?:\|.+\|\s*\n?)+)",
        re.MULTILINE,
    )
    TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")

    def __init__(self, text: str):
        self.text = text
        self.ast: MarkdownGroupNode | None = None
        # The document's id counters, explicit rather than loose on self:
        # see grouper_ids.IdMint for why they are an object.
        self._ids = IdMint()
        # Block-content link/image bodies, keyed by sentinel id. Populated by
        # preprocess, consumed by Phase 2.13.
        self._card_specs: dict[int, _CardSpec] = {}
        # Each source line the Phase 2.16 tier pass left unstamped, by
        # source_line_id: what Phase 6.055 checks a piece's wrapper against.
        self._unwrapped_lines: dict[int, str] = {}
        # Opaque fenced/indented source, keyed by the sentinel planted during
        # preprocess and expanded after structural grouping has finished.
        self._code_specs: dict[int, CodeBlockSpec] = {}
        # Only process() plants sentinels: the partial subgroup_by_* entry
        # points call to_ast() but never reach Phase 2.13, so for them a
        # sentinel would leak into the AST.
        self._extract_cards = False

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> bool:
        """Return False if input is not a string or is empty/whitespace-only.

        Time: O(N), Space: O(1).
        """
        if not isinstance(self.text, str):
            return False
        if not self.text.strip():
            return False
        return True

    # ------------------------------------------------------------------
    # Preprocessing
    # ------------------------------------------------------------------

    FENCED_CODE_RE = re.compile(r"^(`{3,}|~{3,}).*\n[\s\S]*?^\1\s*$", re.MULTILINE)
    # A 4-space/tab indented run is a CommonMark indented code block only when it
    # is a genuine block start — at the document start or after a blank line. It
    # cannot interrupt a paragraph or a list item's continuation, so an indented
    # run that immediately follows a non-blank line (e.g. the sub-bullets of a
    # double-digit ordered item ``10. ...`` whose content aligns at 4 spaces) is
    # left intact for the list parser. ``lead`` (start-of-text or the blank line)
    # is preserved by the replacement so surrounding structure is untouched.
    INDENTED_CODE_RE = re.compile(
        r"(?P<lead>\A|\n[ \t]*\n)(?P<code>(?:(?: {4}|\t).+\n?)+)"
    )

    @staticmethod
    def _indented_code_sub(m: "re.Match[str]") -> str:
        """Replace an indented run with the code placeholder — unless it is a
        list item's body.

        A list item's continuation is indented to its *content column*, so
        ``-   `` legitimately puts it at 4 spaces, and a blank line between the
        marker and the body satisfies this pattern's ``lead``. Without this
        check that body reads as an indented code block and is destroyed —
        which silently ate any link/image card written inside such an item.

        To find what opened the block, walk back past blank lines *and* past
        further indented lines — an item's body can be several indented runs,
        and for all but the first the nearest non-blank line is the body
        itself. The first line at column zero is the one that decides.
        ``lead`` is preserved either way so surrounding structure is untouched.
        """
        placeholder = m.group("lead") + "[unsupported element (code block)]\n"
        for line in reversed(m.string[: m.start()].split("\n")):
            if not line.strip() or line[:1] in (" ", "\t"):
                continue
            return m.group(0) if _LIST_MARKER_RE.match(line) else placeholder
        return placeholder

    HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
    # CommonMark-style backslash escapes: \X where X is ASCII punctuation.
    # Includes \\ → \ (the backslash itself is in the escapable set).
    #
    # ``preprocess`` is the EARLIEST point in the pipeline, so every escape
    # resolved here is invisible to every later scan — which is why the
    # deferred sets exist at all: resolving ``/ % $`` here would make
    # ``12\/26`` indistinguishable from ``12/26``, since the detector would
    # see the same characters either way (see VALUE_ESCAPES).
    #
    # So the class is DERIVED, never typed: it is whatever CommonMark escapes
    # MINUS everything grouper_escapes defers. A hand-typed complement could
    # drift silently, resolving a deferred character here so its feature never
    # sees a mark the author declined.
    BACKSLASH_ESCAPE_RE = escapes_outside_code(EARLY_ESCAPES)
    ZERO_WIDTH_RE = re.compile("[\u200b\u200c\ufeff]")  # not U+200D, a joiner

    def preprocess(self) -> "MarkdownGrouper":
        """Take code blocks out of the text and resolve CommonMark backslash escapes.

        Fenced code blocks (``` or ~~~) and indented code blocks (4-space / tab)
        are swapped for sentinels expanded after grouping, or, on the partial
        entry points, for a placeholder line. Backslash escapes ``\\X`` are
        replaced by the literal character ``X`` for any ASCII-punctuation ``X``
        (the CommonMark-escapable set), and zero-width / BOM characters are
        stripped.

        Returns *self* for chaining.

        Time:  O(N) — each regex makes one pass over the text.
        Space: O(N) — produces a new string of at most the same length.
        """
        self.text, self._feed_slots = grouper_feed_slots.respell(self.text)
        if self._extract_cards:
            # Code is opaque: protect it before removing real document
            # comments, because source code may itself contain ``<!-- -->``.
            text, self._code_specs = extract_code_blocks(self.text)
            text = self.HTML_COMMENT_RE.sub("", text)
        else:
            # Partial-pipeline entry points never reach the expansion phase,
            # so they keep a visible placeholder.
            text = self.HTML_COMMENT_RE.sub("", self.text)
            text = self.FENCED_CODE_RE.sub("[unsupported element (code block)]\n", text)
            text = self.INDENTED_CODE_RE.sub(self._indented_code_sub, text)
        text = self.ZERO_WIDTH_RE.sub("", text)
        # A spacer inside a line becomes one separator character (ADR-203).
        # After code is taken out, before card bodies are, so an alt slot's
        # lines are marked like any others.
        text = mark_inline_spacers(text)
        text = protect_escaped_sliders(protect_escaped_task_controls(text))
        # Before the escape pass, so the scanner still sees "\[" as escaped,
        # and after the comment strip so card bodies carry no HTML comments.
        text = self._rewrite_constructs(text)
        # Before the escape pass, which would resolve ``\\`` to ``\`` and make
        # an escaped backslash look like a break.
        text = finish_lines(text, self.HEADING_PATTERN, self.BACKSLASH_ESCAPE_RE)
        self.text = text
        return self

    @classmethod
    def _construct_is_inline_only(cls, inner: str) -> bool:
        """True when a link/image label holds nothing but inline content.

        Inline-only labels can simply be flattened onto one line; anything
        block-level (a heading, a list, a quote, a rule, a table, or a nested
        link/image) needs a real sub-document and is left alone here.
        """
        # ``[[X]](/url)`` / ``[[ ]](/url)`` / ``[[65%]](/url)`` are the linked
        # control and slider spellings: the inner brackets are a token, not a
        # nested construct, so the link stays inline for the late control pass.
        if re.fullmatch(r"\[[ xX]\]", inner) or _SLIDER_RE.fullmatch(inner):
            return True
        if "[" in inner:  # a nested link or image
            return False
        if "\n" not in inner:
            # Every other block form is line-level, so a label that is already
            # one line cannot be one. Checking anyway would misread ordinary
            # button labels — "[>](/next)" is a chevron, not a blockquote.
            return True
        for line in inner.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if (
                cls.HEADING_PATTERN.match(stripped)
                or _LIST_MARKER_RE.match(stripped)
                or _BLOCKQUOTE_LINE_RE.match(line)
                or _break_node_type(line) is not None
                or "|" in stripped
            ):
                return False
        return True

    def _rewrite_constructs(
        self,
        text: str,
        depth: int = 0,
        in_link: bool = False,
        in_image: bool = False,
    ) -> str:
        """Normalise every link / image construct in *text*. One scan, three
        outcomes per construct.

        **Flatten** — a label holding only inline content but spread over
        several lines. Some generators emit ::

            [
            Preview
            ](/team-hub)

        Phase 1 splits on blank lines and then on newlines *before* anything
        looks for links, so this would reach the detector as three unrelated
        leaves ("[", "Preview", "](/team-hub)"). Collapsing it to
        ``[Preview](/team-hub)`` hands the pipeline a shape it already handles
        end to end — variants, emoji badges and pill sizing all keep working.
        (Deliberately divergent from CommonMark, where a blank line terminates
        link text so the example above is *not* a link. Generators emit it and
        the intent is unambiguous.)

        **Card** — a label holding block markdown (a heading, a list, a nested
        construct, a lone link's glued lines). It is replaced by a one-line
        sentinel and its body stashed in ``self._card_specs``; ``to_ast`` then
        sees an opaque, non-heading line, so the body's headings cannot nest
        into, close, or open anything in the surrounding document. Phase 2.13
        expands the sentinel back into a real subtree. Only when
        ``self._extract_cards`` is set — the partial ``subgroup_by_*`` entry
        points never reach Phase 2.13 and must not be left holding sentinels.

        **Discard** — a construct whose kind already encloses it. A link inside
        a link is not a link, so it degrades to its label text; an image inside
        an image card is dropped outright (alt text is metadata, not display
        text). Enforced by *ancestor*, not by parent, so a link nested through
        an intervening image card is still caught. The same degradation applies
        past ``_MAX_CARD_DEPTH``.

        Single-line content that needs none of the above is returned byte for
        byte unchanged.

        Time: O(N) — inner texts are disjoint, so the bounded recursion still
        visits each character a constant number of times. Space: O(N).
        """
        constructs = _scan_bracket_constructs(text)
        if not constructs:
            return text

        out: list[str] = []
        prev = 0
        for c in constructs:
            out.append(text[prev : c.start])
            prev = c.end

            same_kind = in_image if c.is_image else in_link
            block = not self._construct_is_inline_only(c.inner) or c.is_group_link(text)

            if (same_kind and block) or (block and depth >= _MAX_CARD_DEPTH):
                # Prohibited or too deep: keep a link's visible label, drop an
                # image entirely. The label may hold constructs of its own.
                # Only a same-kind *card* is prohibited. A plain one has no
                # block content, so it cannot nest any further — it passes
                # through below and becomes an ordinary LINK or IMAGE leaf: a
                # button drawn inside a link card, a photo inside an image
                # card. Such a button takes its own clicks and the card the
                # rest of its area (``render_actions.hit_region``, ADR-404).
                if not c.is_image:
                    out.append(
                        self._rewrite_constructs(c.inner, depth, in_link, in_image)
                    )
                continue

            if block:
                # Flattening block content would mangle it, so without card
                # extraction (the partial entry points) it is left verbatim.
                out.append(
                    self._plant_card(c, depth, in_link, in_image)
                    if self._extract_cards
                    else text[c.start : c.end]
                )
                continue

            if "\n" in text[c.start : c.end]:
                out.append(f"{'!' * c.is_image}[{flat_label(c.inner)}]({c.url})")
            else:
                out.append(text[c.start : c.end])

        out.append(text[prev:])
        return "".join(out)

    def _plant_card(
        self,
        c: "_BracketConstruct",
        depth: int,
        in_link: bool,
        in_image: bool,
    ) -> str:
        """Stash a block-content construct and return its sentinel.

        The body is normalised in the same way as the document (so nested
        constructs inside it are flattened, carded or discarded) with this
        construct's kind added to the enclosing set.
        """
        # Dedent first: a card written inside a list item carries that item's
        # continuation indent on every line, and an indented ``## Title`` does
        # not match HEADING_PATTERN — the body would parse as flat text. Only
        # the COMMON prefix goes, so nested indentation inside the card (a
        # sub-list, say) is preserved.
        inner = self._rewrite_constructs(
            textwrap.dedent(c.inner),
            depth + 1,
            in_link or not c.is_image,
            in_image or c.is_image,
        )
        inner = finish_lines(inner, self.HEADING_PATTERN, self.BACKSLASH_ESCAPE_RE)
        cid = len(self._card_specs)
        self._card_specs[cid] = _CardSpec(
            is_image=c.is_image, url=c.url, inner=inner, raw=c.raw
        )
        return _CARD_SENTINEL_FMT.format(cid)

    # ------------------------------------------------------------------
    # AST construction
    # ------------------------------------------------------------------

    def to_ast(self) -> "MarkdownGrouper":
        """Build the heading-level AST and store it as ``self.ast``.

        Automatically runs ``preprocess`` (code blocks, escapes) and converts
        each thematic break into its
        own leaf: ``---`` a ``horizontal_rule``, ``___`` a ``content_break``,
        ``***`` a ``section_stop`` (consumed before this method returns). The
        node's content is the marker line.

        Returns *self* for chaining.

        Time: O(N), Space: O(N).
        Scans L lines, builds H heading nodes.  Stack pops are amortized
        O(H) total (each heading pushed once, popped at most once).
        Join for content is O(N) total across all headings.
        """
        self.preprocess()

        if not self.validate():
            self.ast = MarkdownGroupNode(type="root")
            return self

        self.ast = self._build_block_ast(self.text)
        return self

    def _build_block_ast(self, text: str) -> "MarkdownGroupNode":
        """Build a heading-level AST for *text* and return its root.

        The block-structure core of :meth:`to_ast`, factored out so it can be
        applied to a *fragment* as its own little document — a card body (the
        markdown inside ``![ … ](url)`` / ``[ … ](url)``) is grouped by its own
        headings without those headings nesting into, closing, or opening
        anything in the surrounding document.

        Glued-segment ids come from ``self._ids`` either way, so ids
        stay unique across the document and every fragment in it.

        Multi-line raw text is deliberately left on the nodes; Phase 1's
        blank-line / newline splits (which walk the whole tree) break it up
        later, so a spliced fragment behaves exactly like top-level content.

        Time: O(N), Space: O(N) — see :meth:`to_ast`.
        """
        root = MarkdownGroupNode(type="root")
        if not text.strip():
            return root

        lines = scope_item_dividers(text.split("\n"))

        # Detect headings and BREAK lines. `hr_lines` holds all three kinds — a
        # painted `---` rule, an invisible `___` break and a `***` section stop
        # cut the document identically (they end a glued run and split the
        # body's children); they differ only in what they leave behind, which
        # _segment_lines_with_hrs decides by re-testing the line.
        headings = []
        hr_lines: set[int] = set()
        for i, line in enumerate(lines):
            if _break_node_type(line) is not None:
                hr_lines.add(i)
                continue
            m = self.HEADING_PATTERN.match(line)
            if m:
                headings.append((i, len(m.group(1)), line))
        # A `---` tight inside a run of lines divides that block rather than
        # cutting it: it stays a line of its text, minted by _split_newlines.
        hr_lines -= glued_rules(lines, hr_lines, {ln for ln, _, _ in headings})

        # Per-line glued content-segment ids: each glued run (two or more
        # lines, ``glued_runs``) shares one id; a lone line is not "glued" ->
        # None. Ids are minted in document order and shared with the
        # blank-line splitter's counter.
        line_seg_id: list[int | None] = [None] * len(lines)
        for run in glued_runs(lines, hr_lines):
            gid = self._ids.next_glued()
            for k in run:
                line_seg_id[k] = gid

        if not headings:
            if hr_lines:
                root.children = self._segment_lines_with_hrs(
                    lines, hr_lines, 0, len(lines), line_seg_id
                )
                # No section for a `***` to close, so it only ever cut.
                self._apply_section_stops(root)
                # ... and with no heading anywhere, a `:::` has nothing to lift
                # out of; it only partitions this one run.
                build_column_rows(root)
                build_vertical_springs(root)
            else:
                root.content = "\n".join(lines).strip()
            return root

        # A contiguous non-blank run sitting directly against a heading (no
        # blank line between them) is absorbed into that heading's group as
        # leading children, ahead of the heading node — e.g. a hero image on
        # the line immediately above its heading. The run is only absorbed
        # when it is bounded above by a blank line, a horizontal rule, or the
        # document start; a run that runs straight out of the *previous*
        # heading is that heading's body and stays there ("first heading
        # absorbs first").
        #
        # The PARTITION breaks — ``:::`` across and ``...`` down — are
        # TRANSPARENT to the peel, which the other three are not. Each says
        # "what is above me and what is below me share one box", and sharing a
        # box means being SIBLINGS — so an image written above one of them,
        # above a heading, has to travel INTO that heading's group, or it is
        # stranded in the previous section and the partition has nothing to
        # divide. The guard below still stops the walk at a real heading, so a
        # partition cannot drag a whole previous section along with it.
        heading_lines = {ln for ln, _, _ in headings}

        def peel_start(line_num: int) -> int:
            run_start = line_num
            j = line_num - 1
            while j >= 0 and lines[j].strip() and j not in heading_lines:
                if j in hr_lines and _break_node_type(lines[j]) not in _PARTITION_TYPES:
                    break
                run_start = j
                j -= 1
            if j >= 0 and j in heading_lines:
                return line_num
            return run_start

        peel_starts = [peel_start(ln) for ln, _, _ in headings]

        # Preamble before first heading → segmented TEXT/HR children in order
        # (excludes any run absorbed by the first heading below).
        root.children.extend(
            self._segment_lines_with_hrs(
                lines, hr_lines, 0, peel_starts[0], line_seg_id
            )
        )

        # Stack of (group_or_root, level)
        stack: list[tuple[MarkdownGroupNode, int]] = [(root, 0)]

        for idx, (line_num, level, heading_text) in enumerate(headings):
            # Body ends where the next heading's absorbed run begins, so peeled
            # lines belong to the next group rather than this one's body.
            content_end = (
                peel_starts[idx + 1] if idx + 1 < len(headings) else len(lines)
            )

            # Group node is the section container — flag it so the layout generator
            # can mark the heading section directly (bg/padding/spacing) instead of
            # guessing from heading-typed leaves (which breaks for style-split headings).
            group_node = MarkdownGroupNode(type=NodeType.GROUP)
            group_node.heading_group = True
            group_node.heading_level = level

            # Absorbed leading run (e.g. image glued above the heading)
            group_node.children.extend(
                self._segment_lines_with_hrs(
                    lines, hr_lines, peel_starts[idx], line_num, line_seg_id
                )
            )

            # Heading node is a leaf (text only, can be style-split later)
            visible_heading = heading_text.lstrip("# ")
            heading_id = None
            fixed_style_key = None
            attr = self.HEADING_ID_PATTERN.search(visible_heading)
            if attr is not None:
                heading_id = attr.group(1)
                visible_heading = visible_heading[: attr.start()].rstrip()
                style_match = self.FIXED_STYLE_ID_PATTERN.fullmatch(heading_id)
                if style_match is not None:
                    fixed_style_key = style_match.group(1)
            group_node.heading_id = heading_id
            group_node.fixed_style_key = fixed_style_key
            heading_node = MarkdownGroupNode(
                content=visible_heading, type=f"heading{level}"
            )
            heading_node.glued_content_id = line_seg_id[line_num]
            group_node.children.append(heading_node)

            # Body: ordered TEXT/HORIZONTAL_RULE children preserving source position
            group_node.children.extend(
                self._segment_lines_with_hrs(
                    lines, hr_lines, line_num + 1, content_end, line_seg_id
                )
            )

            while len(stack) > 1 and stack[-1][1] >= level:
                stack.pop()

            stack[-1][0].children.append(group_node)
            stack.append((group_node, level))

        self._apply_section_stops(root)
        # After the stops, so a `:::` lifts through a tree whose sections are
        # already final: both are Phase 1 instructions and neither type survives.
        build_column_rows(root)
        # After the rows, so a spring inside a `:::` cell partitions that CELL
        # rather than the row — the cell is the box with height to give away.
        build_vertical_springs(root)
        # Last, so it sees whatever shape the row build left behind.
        self._lift_trailing_content_breaks(root)
        return root

    @classmethod
    def _lift_trailing_content_breaks(cls, node: "MarkdownGroupNode") -> None:
        """Move a ``___`` that ends a heading section out as its next SIBLING.

        A heading swallows to the next heading, so a break written under a
        section's last line lands INSIDE that section — and a break inside one
        group cannot separate that group from the next. Which makes ``___``
        unable to do the one job it exists for: "it only cuts, which is what
        breaking up a repeated-element grid needs". Left inside, two identical
        ``## `` sections with a ``___`` between them would grid side by side,
        exactly as if it were not written.

        Only ``___``. ``---`` stays where it is on purpose: it is the spelling
        every markdown generator reaches for when it wants a visible divider, so
        a document written by someone who has never heard of this project is
        full of them, and lifting those would break up card boards nobody asked
        to break up. The rare, deliberate spelling is the one that may
        restructure.

        Children first, so a nested section hands its break up before its holder
        is examined and a break can travel out of several levels at once.

        Time: O(nodes), Space: O(width).
        """
        for child in node.children:
            cls._lift_trailing_content_breaks(child)
        out: list[MarkdownGroupNode] = []
        for child in node.children:
            out.append(child)
            while (
                child.heading_group
                and child.children
                and child.children[-1].type == NodeType.CONTENT_BREAK
            ):
                out.append(child.children.pop())
        node.children = out

    @classmethod
    def _apply_section_stops(cls, node: "MarkdownGroupNode") -> None:
        """Close every heading section at its ``***`` and lift the tail out.

        The second split, run once the headings' own split has built the tree:
        a ``***`` says "this section ends here", so everything after it inside
        that section is re-parented as the section's next SIBLING, keeping
        source order. That is the whole feature — a footer row that must sit
        beside the heading's box rather than inside it.

        A node closes its CHILDREN's sections, never its own — only the parent
        can hold what a section gives up. So a stop sitting directly under a
        heading section is deliberately left in place here and consumed one
        level up; that is also what makes stops compose. Lift a tail whose
        first item is another ``***`` and it becomes the parent's stop, closing
        the parent too, exactly as if it had been authored there.

        Consequences worth naming, all of them falling out of the walk:

        * A stop no heading section holds — at the root, or in a fragment with
          no headings — only ever cut. It is dropped and nothing moves.
        * A section that has been stopped cannot be re-entered: a later, deeper
          heading nested into it during the build sits after the stop, so it
          rides out with the rest of the tail.
        * Children first, so an inner section has already handed its tail up
          before its holder is examined.

        No ``SECTION_STOP`` survives the pass over the whole tree, so nothing
        downstream of Phase 1 ever sees the type.

        Time: O(nodes), Space: O(width) for the rebuilt child lists.
        """
        out: list[MarkdownGroupNode] = []
        for child in node.children:
            cls._apply_section_stops(child)
            out.append(child)
            if not child.heading_group:
                continue
            for i, grandchild in enumerate(child.children):
                if grandchild.type == NodeType.SECTION_STOP:
                    out.extend(child.children[i + 1 :])
                    del child.children[i:]  # drops the stop with the tail
                    break
        if node.heading_group:
            # Leave a stop of our own for the parent to consume.
            node.children = out
        else:
            node.children = [c for c in out if c.type != NodeType.SECTION_STOP]

    @staticmethod
    def _segment_lines_with_hrs(
        lines: list[str],
        hr_lines: set[int],
        start: int,
        end: int,
        line_seg_id: list[int | None] | None = None,
    ) -> list[MarkdownGroupNode]:
        """Build ordered TEXT/BREAK children from lines[start:end].

        Each contiguous non-HR run becomes one TEXT node; each HR line becomes
        one BREAK node of whatever kind ``_break_node_type`` says it is. Empty
        runs are dropped. This preserves the source order of breaks relative to
        surrounding content. A ``:::`` divider also carries its authored cell
        weight, the one break kind that has a number on it.

        When *line_seg_id* is given, each TEXT node is stamped with the glued
        content-segment id of its first non-blank source line (``None`` when
        that line is not part of a multi-line glued run).

        Time: O(N), Space: O(N).
        """
        out: list[MarkdownGroupNode] = []
        buf: list[str] = []
        first_idx: list[int | None] = [None]

        def flush() -> None:
            text = "\n".join(buf).strip()
            if text:
                node = MarkdownGroupNode(type=NodeType.TEXT, content=text)
                if line_seg_id is not None and first_idx[0] is not None:
                    node.glued_content_id = line_seg_id[first_idx[0]]
                out.append(node)
            buf.clear()
            first_idx[0] = None

        for i in range(start, end):
            if i in hr_lines:
                flush()
                # Never None: hr_lines was built from this very test.
                kind = _break_node_type(lines[i])
                assert kind is not None
                brk = MarkdownGroupNode(type=kind, content=lines[i].strip())
                if kind == NodeType.COLUMN_DIVIDER:
                    # ``:::2`` — the share the cell ABOVE this divider takes.
                    # Stamped here because this is the last point the raw line
                    # exists; _build_column_rows reads it off the node.
                    stamp_column_divider(brk, lines[i])
                out.append(brk)
            else:
                if first_idx[0] is None and lines[i].strip():
                    first_idx[0] = i
                buf.append(lines[i])
        flush()
        return out

    # ------------------------------------------------------------------
    # Generic tree walker used by every subgroup method
    # ------------------------------------------------------------------

    def _assign_source_line_ids(self, node: MarkdownGroupNode) -> None:
        """Stamp a fresh per-physical-source-line id on every single-line
        content leaf (post-order).

        Called at Phase 2.3, where each leaf is exactly one source line. A leaf
        whose content still spans multiple lines (embedded newline — e.g. a
        glued prose block) is deliberately left unstamped: its pieces, if an
        intra-line splitter later touches it, come from different lines and must
        stack, not flow. Groups get no id here — a group's effective line id is
        derived from its children (see _group_source_line_id)."""
        if node.children:
            for c in node.children:
                self._assign_source_line_ids(c)
            return
        stripped = node.content.strip()
        if stripped and "\n" not in stripped:
            node.source_line_id = self._ids.next_source_line()

    def _subgroup_content(
        self,
        node: MarkdownGroupNode,
        splitter,
        crosses_segments: bool = False,
        mints_segments: bool = False,
    ) -> list[MarkdownGroupNode] | None:
        """Depth-first: apply *splitter* to every node that has content.

        Returns ``None`` when *node* should stay in its parent's
        ``children`` list, or a list of replacement nodes for the parent
        to splice in place of *node*. Splicing kicks in when a leaf
        ``TEXT`` node is split into multiple parts — the parts replace
        the original node rather than nesting under a new wrapper
        ``GROUP``, which would add a redundant level.

        *crosses_segments* must be True only for the blank-line split, the one
        splitter that crosses glued content-segment boundaries: its first piece
        continues the parent's segment while each later multi-line piece starts a
        fresh segment. *mints_segments* must be True only for the newline split:
        once blank lines are gone, any node split into multiple single-newline
        lines is itself one glued segment, so an untagged node mints a shared id
        for its pieces (this catches a lone multi-line paragraph that the
        blank-line split never wrapped). Every other splitter stays within one
        segment, so children simply inherit the parent's ``glued_content_id``.

        Time: O(K + N), Space: O(N).
        """
        new_children: list[MarkdownGroupNode] = []
        for child in list(node.children):
            spliced = self._subgroup_content(
                child, splitter, crosses_segments, mints_segments
            )
            if spliced is None:
                new_children.append(child)
            else:
                new_children.extend(spliced)
        node.children = new_children
        _flatten_empty_text(node)

        if not node.content:
            return None

        # A BREAK leaf's content is the SPELLING the author wrote, never content
        # to be parsed — see the same guard in
        # :meth:`_subgroup_content_classified_multi`, where re-reading one is
        # what stops a spaced ``- - -`` painting. This walker takes arbitrary
        # splitters too, so it carries the invariant rather than leaving the
        # bug to come back through the other door.
        if node.type in _BREAK_TYPES:
            return None

        result = splitter(node.content)
        if result is None:
            return None

        if len(result) == 1 and not node.children:
            # Single result, no existing children — absorb into node. A heading
            # absorbing an ordered item (``## 1. Foo``) IS the heading ordinal,
            # so keep its level: the classified-multi consumer nests the item
            # under the heading node instead, and _stamp_list_ordinals reads the
            # parent there — both paths must annotate the same way.
            heading = _HEADING_TYPE_RE.match(node.type)
            node.type, node.content = result[0][0], result[0][1]
            node.list_number = _item_number(result[0])
            if heading and node.type == NodeType.ORDERED_ITEM:
                node.list_heading_level = int(heading.group(1))
            return None

        new_nodes = [
            MarkdownGroupNode(type=item[0], content=item[1]) for item in result
        ]
        for child, item in zip(new_nodes, result):
            child.list_number = _item_number(item)
        if crosses_segments:
            for i, text in enumerate(item[1] for item in result):
                if i == 0 and node.glued_content_id is not None:
                    # Continuation of the parent's segment (e.g. a heading-run
                    # body) — a member, not its own wrapper.
                    new_nodes[i].glued_content_id = node.glued_content_id
                elif "\n" in text:
                    # A fresh multi-line paragraph segment: it is its own wrapper.
                    new_nodes[i].glued_content_id = self._ids.next_glued()
                    new_nodes[i]._glue_root = True
        else:
            seg_id = node.glued_content_id
            if seg_id is None and mints_segments and len(new_nodes) >= 2:
                # A lone multi-line paragraph: one glued segment of its own.
                seg_id = self._ids.next_glued()
            if seg_id is not None:
                for child in new_nodes:
                    if child.glued_content_id is None:
                        child.glued_content_id = seg_id
        if node.data_points:
            partitioned = _partition_data_points(node.content, node.data_points, result)
            for child, dps in zip(new_nodes, partitioned):
                child.data_points = dps
            node.data_points = []

        # Leaf TEXT being split: splice pieces into parent instead of
        # promoting self to GROUP and nesting them one level deeper.
        if node.type == NodeType.TEXT and not node.children:
            hand_down_valign(node, new_nodes)  # a `...` region's place goes too
            return new_nodes

        # Content-derived children go before existing heading children
        if node.type == NodeType.TEXT:
            node.type = NodeType.GROUP
        node.children = new_nodes + node.children
        node.content = ""
        return None

    def _restructure_list_bodies(self, node: "MarkdownGroupNode") -> None:
        """Re-structure each list-item *body* like a mini-document.

        After Phase 2 extracts list items, an item's body is still raw
        multi-line text (blank lines preserved). Block structure was applied to
        the whole document in Phase 1, before the items existed, so the body
        never got it. Run the same passes scoped to each list-item subtree:
        blank-line split → paragraphs, then newline split (minting one glued
        segment per multi-line paragraph). Images are split later, in the
        Phase 5.5 element walk, so they land inside their paragraph's glued segment.

        Post-order so nested structure is handled before the item itself.
        Time: O(N) over list-item bodies, Space: O(N).
        """
        for child in list(node.children):
            self._restructure_list_bodies(child)
        if node.type in self._LIST_ITEM_LABELS and node.content:
            self._subgroup_content(node, _split_blank_lines, crosses_segments=True)
            self._subgroup_content(node, _split_newlines, mints_segments=True)
            build_item_rows(node, stamp_column_divider)

    def _expand_cards_walk(self, node: "MarkdownGroupNode") -> None:
        """Replace every card sentinel with the subtree for its body.

        Runs as Phase 2.13 — after the list splitters have stripped markers
        (so ``- ⟦md2ui-card-3⟧`` is an item whose *body* is the sentinel, and
        expanding cannot destroy the marker) and before
        ``_assign_source_line_ids`` / ``_split_images`` / the whole of Phase 3+,
        which then treat a card's children as ordinary nodes. That is the point
        of the placement: the body is walked, detected and classified exactly
        once, like any other content — a nested ``process()`` would run the
        three most expensive phases over it twice.

        The whole walk is skipped when the document has no cards, so the common
        case costs one dict check.

        Time: O(K + body sizes), Space: O(depth).
        """
        for child in list(node.children):
            self._expand_cards_walk(child)
        if node.content and _CARD_SENTINEL_MARK in node.content:
            self._expand_cards_in(node)

    def _expand_cards_in(self, node: "MarkdownGroupNode") -> None:
        """Expand the sentinels held in ``node.content`` in place.

        A sentinel usually owns the whole content (its own source line, or a
        list item's body). When it is embedded in prose the surrounding text
        is kept as TEXT siblings, mirroring ``_split_inline``.
        """
        pieces = _CARD_SENTINEL_RE.split(node.content)
        if len(pieces) == 1:
            return

        new_children: list["MarkdownGroupNode"] = []
        for i, piece in enumerate(pieces):
            if i % 2 == 0:
                if piece.strip():
                    new_children.append(
                        MarkdownGroupNode(type=NodeType.TEXT, content=piece.strip())
                    )
                continue
            spec = self._card_specs.get(int(piece))
            if spec is None:  # unknown id — keep the token visible, not silent
                new_children.append(
                    MarkdownGroupNode(type=NodeType.TEXT, content=piece)
                )
                continue
            new_children.append(self._build_card(spec))

        _inherit_glue(node, new_children, self._ids)
        if node.type == NodeType.TEXT:
            node.type = NodeType.GROUP
        node.content = ""
        node.children = new_children + node.children

    def _build_card(self, spec: _CardSpec) -> "MarkdownGroupNode":
        """Build the node for one card, body and all.

        The body is grouped as its own little document via
        :meth:`_build_block_ast`, so its headings never nest into, close, or
        open a section in the surrounding document, and is then given the same
        block passes Phase 1 + 2 + 2.1 give the top level — scoped to this
        subtree, so the cost is O(body) and bodies are disjoint.

        An image card keeps its URL as ``card_bg_url`` (the renderer paints it
        behind the body). A link card is a plain GROUP carrying ``link_url``,
        so it cannot alter fingerprints — the renderer draws nothing for it.
        """
        if spec.is_image:
            card = MarkdownGroupNode(type=NodeType.IMAGE_CARD)
            card.card_bg_url = destination_url(spec.url)
        else:
            card = MarkdownGroupNode(type=NodeType.GROUP)
            card.link_url = spec.url

        sub = self._build_block_ast(spec.inner)
        if sub.children:
            card.children, card.valign_group = sub.children, sub.valign_group
        elif sub.content:
            card.children = [MarkdownGroupNode(type=NodeType.TEXT, content=sub.content)]
        # A card never keeps content of its own: _subgroup_content's absorb
        # branch would otherwise rewrite its type from under it.
        card.content = ""

        self._subgroup_content(card, _split_blank_lines, crosses_segments=True)
        self._subgroup_tables_walk(card)
        self._subgroup_content(card, _split_newlines, mints_segments=True)
        self._subgroup_content_classified_multi(
            card,
            [_split_all_lists, _split_blockquote],
        )
        self._prune_empty(card)
        self._restructure_list_bodies(card)
        self._stamp_list_ordinals(card)
        # A body may itself hold a card (a link card wrapping an image card).
        self._expand_cards_walk(card)
        return card

    def _restore_unexpanded_sentinels(self, node: "MarkdownGroupNode") -> None:
        """Put the original markdown back wherever a sentinel survived.

        Nothing should reach here, but a scanner/expander mismatch must
        degrade to that construct's markdown rather than painting
        ``⟦md2ui-card-7⟧`` on the page.
        """
        if node.content and _CARD_SENTINEL_MARK in node.content:

            def sub(m: re.Match) -> str:
                spec = self._card_specs.get(int(m.group(1)))
                return spec.raw if spec else m.group(0)

            node.content = _CARD_SENTINEL_RE.sub(sub, node.content)
        for child in node.children:
            self._restore_unexpanded_sentinels(child)

    def _stamp_list_ordinals(self, node: "MarkdownGroupNode") -> None:
        """Stamp each ORDERED_ITEM with the ordinal to draw, and — for an item
        split out of a heading — that heading's level.

        A run is the contiguous ORDERED_ITEM siblings under one parent; any
        non-ordered sibling ends it. The run **starts at the number the author
        wrote** and counts up from there, so a list written 1./1./1. still
        renders 1,2,3 (CommonMark: only the first number counts) while one
        written 3./4. renders 3,4. A ``## 1. Foo`` heading splits into a lone
        ordered item under its own heading node — a run of one — so it keeps its
        own number instead of every heading in the document rendering "1".

        ``list_heading_level`` is stamped here because this is the only walk that
        sees an item's parent: the item carries no heading flags of its own (the
        section's live two levels up), and the generator must not guess.

        Time: O(K), Space: O(depth).
        """
        heading = _HEADING_TYPE_RE.match(node.type)
        counter = 0
        in_run = False
        for child in node.children:
            if child.type == NodeType.ORDERED_ITEM:
                if not in_run and child.list_number is not None:
                    counter = child.list_number
                else:
                    counter += 1
                in_run = True
                child.list_ordinal = counter
                if heading:
                    child.list_heading_level = int(heading.group(1))
            else:
                counter, in_run = 0, False
            self._stamp_list_ordinals(child)

    @staticmethod
    def _prune_empty(node: "MarkdownGroupNode") -> None:
        """Remove leaf children that have no content and no children.

        Horizontal-rule nodes are preserved unconditionally — they must
        survive to the renderer (they are kept even if ever contentless).

        Time: O(K), Space: O(1) (in-place).
        """
        for child in list(node.children):
            MarkdownGrouper._prune_empty(child)
        node.children = [
            c
            for c in node.children
            if c.content or c.children or c.type in _KEEP_WHEN_EMPTY
        ]

    # ------------------------------------------------------------------
    # Datapoint display annotation (Phases 6.06 / 6.07)
    # ------------------------------------------------------------------

    # Underscore run length -> authored display tier. Longest first, mirroring
    # _detect_dp_style_marker, so ``___x___`` is never read as ``_`` + ``__x__``.
    _TEXT_STYLE_TIERS = {3: "display", 2: "lead", 1: "muted"}
    _UNDERSCORE_RUN_ITER = re.compile(r"_+")
    # Leaf types an underscore wrap must not retype. Links and images own the
    # ``## Links`` variant scheme (``**[x](/y)**`` is already a button variant),
    # and a standalone `code` element is a pill whose own style wins.
    _NO_TIER_TYPES = frozenset(
        {
            NodeType.LINK,
            NodeType.IMAGE,
            NodeType.IMAGE_CARD,
            NodeType.INLINE_CODE,
        }
    )

    @staticmethod
    def _detect_underscore_wrap(content: str) -> tuple[str, str] | None:
        """``(tier, inner)`` when *content* is ENTIRELY wrapped in underscores.

        ``_x_`` → muted, ``__x__`` → lead, ``___x___`` → display. Returns None
        for anything else, including a mid-sentence span — the tier is a
        whole-leaf construct, so ``Text with a __bold__ word`` stays plain bold
        and the renderer keeps re-parsing those markers itself.

        Shares ``_detect_style_wrap``'s conservatism: matching runs at both ends
        are not enough, they must be the *same* span. ``_A_ _B_`` also starts and
        ends with a marker, and treating it as one wrap would strip a wrapper
        that was never there — so an interior run long enough to close the opener
        disqualifies it.
        """
        s = content.strip()
        n = len(s)
        lead = 0
        while lead < n and s[lead] == "_":
            lead += 1
        tier = MarkdownGrouper._TEXT_STYLE_TIERS.get(lead)
        if tier is None:
            return None
        trail = 0
        while trail < n and s[n - 1 - trail] == "_":
            trail += 1
        if lead != trail or n <= 2 * lead:
            return None
        middle = s[lead : n - lead]
        if any(
            len(run.group()) >= lead
            and not _is_intraword(middle, run.start(), run.end())
            for run in MarkdownGrouper._UNDERSCORE_RUN_ITER.finditer(middle)
        ):
            return None
        inner = middle.strip()
        return (tier, inner) if inner else None

    # One whole emphasis span — ``_x_`` / ``__x__`` / ``___x___`` or the same
    # shape spelled with asterisks — with no whitespace just inside the markers
    # (so ``_ x _`` is not a span) and a whitespace-or-end boundary after it.
    # SEPARATION must not depend on which emphasis family the author used; only
    # the painted style may.
    _EMPHASIS_SPAN_RE = re.compile(r"([*_]{1,3})(?!\s)(.+?)(?<!\s)\1(?=\s|$)")

    @staticmethod
    def _detect_underscore_span_run(
        content: str,
    ) -> list[tuple[str | None, str]] | None:
        """``[(tier, inner), …]`` when *content* is nothing but a run of >= 2
        whole underscore spans separated by whitespace, else ``None``.

        ``_High 78_ _Low 56_`` is two authored tiers sitting on one line, not
        one wrap — :meth:`_detect_underscore_wrap` rightly rejects it. Each span
        keeps its OWN run length, so ``_a_ __b__`` is muted then lead.

        Underscores only. ``*`` is not a tier, and an asterisk run of this
        shape is typically something that already owns its wrapper — a
        key/value (``**Price:** **$79.99**``) or a row of link / chip variants
        (``*[a](/x)* *[b](/y)*``). The guards below keep those out of reach even
        when they are spelled with underscores.
        """
        s = content.strip()
        pos = 0
        out: list[tuple[str | None, str]] = []
        while pos < len(s):
            m = MarkdownGrouper._EMPHASIS_SPAN_RE.match(s, pos)
            if not m:
                return None  # text outside a span: not a pure run
            marker = m.group(1)
            # `_` selects a TIER and its wrapper is consumed; `*` is ordinary
            # emphasis, so the piece keeps its markers for the renderer to
            # paint. Either way the line SPLITS the same, which is the point.
            if marker[0] == "_":
                tier = MarkdownGrouper._TEXT_STYLE_TIERS.get(len(marker))
                if tier is None:
                    return None
                out.append((tier, m.group(2).strip()))
            else:
                out.append((None, m.group(0).strip()))
            pos = m.end()
            while pos < len(s) and s[pos].isspace():
                pos += 1
        if len(out) < 2:
            return None
        for _, inner in out:
            # A tight colon means a key/value, which owns the line and must be
            # left for _split_kv_styled / _plain_colon_kv to claim.
            if not inner or ":" in inner:
                return None
            # Same opt-out as the whole-leaf pass below: for these the
            # underscores select the ELEMENT's variant, not a text tier.
            if (
                _LINK_CONTENT_RE.match(inner)
                or IMAGE_RE.fullmatch(inner)
                or INLINE_CODE_RE.fullmatch(inner)
                or _is_lone_emoji(inner)
            ):
                return None
        return out

    def _push_tier_down(self, node: "MarkdownGroupNode", tier: str) -> None:
        """Give *tier* to every descendant leaf that carries none."""
        for c in node.children:
            if c.children:
                self._push_tier_down(c, tier)
            elif (
                c.text_style is None
                and c.type not in MarkdownGrouper._NO_TIER_TYPES
                and c.type != NodeType.EMOJI
                and not c.type.startswith("heading")
            ):
                c.text_style = tier

    def _annotate_text_style_tiers(
        self, node: "MarkdownGroupNode", in_table: bool = False, record: bool = False
    ) -> None:
        """Phase 6.055 — stamp ``text_style`` and consume the underscore wrapper.

        Post-order, after Phase 6 collapse, so every leaf is already its final
        line-or-segment: "the wrapper spans the whole line" and "the wrapper
        spans the whole segment" are then the same check, and the separator
        splitter has long since run. Before Phase 6.06 so the datapoint pass can
        defer to an explicit tier.

        The Phase 2.16 run (*record*) keeps each line it does not stamp, so this
        run tiers only a wrapper the author wrote, not one a cut repaired.

        Table subtrees are skipped for the same reason ``_annotate_datapoint_displays``
        skips them — the table cell rendering owns their styling.

        Time: O(K), Space: O(depth).
        """
        in_table = in_table or node.table_group
        for c in node.children:
            self._annotate_text_style_tiers(c, in_table, record)
        if in_table:
            return
        if node.children:
            # A tier stamped on a WHOLE LINE in Phase 2.16 is stranded here once
            # the line has split: nothing pushes it down and the renderer reads
            # ``text_style`` per LEAF, so the tier paints nothing. Hand it to the
            # text-bearing leaves that carry none — element leaves own their own
            # variant scheme and a heading owns its own style.
            if node.text_style is not None:
                self._push_tier_down(node, node.text_style)
            return
        if node.type in MarkdownGrouper._NO_TIER_TYPES:
            return
        # A heading is a heading first — `# ___x___` keeps its markers and paints
        # bold-italic in the heading's own family, exactly as `# ***x***` does.
        # Stamping here would record a tier the renderer is required to ignore.
        if node.type.startswith("heading"):
            return
        hit = MarkdownGrouper._detect_underscore_wrap(node.content)
        if record and hit is None and node.source_line_id is not None:
            self._unwrapped_lines[node.source_line_id] = node.content
        if hit is None:
            # Not ONE wrap — but it may be a RUN of whole spans on one line
            # (``_High 78_ _Low 56_``), which becomes one tiered leaf per span.
            # The pieces inherit the parent's source_line_id via _inherit_glue,
            # so Phase 6.1 derives line_split_group for them; never set it here.
            run = MarkdownGrouper._detect_underscore_span_run(node.content)
            if run is None:
                return
            # The pieces are plain text; the node becomes their container and
            # keeps its own kind, so a LIST_ITEM stays one list item and a KV
            # VALUE stays one value rather than turning into several.
            children = [
                MarkdownGroupNode(type=NodeType.TEXT, content=inner) for _, inner in run
            ]
            for child, (tier, _) in zip(children, run):
                if tier is not None:
                    child.text_style = tier
            # Each piece takes the values inside it (tests/datapoint_offsets_tests.py).
            _hand_data_points(node, children, [inner for _, inner in run])
            _inherit_glue(node, children, self._ids)
            node.children = children
            node.content = ""
            # TEXT and SEGMENT have no container reading, and left as one a
            # later pass lifts the pieces out — which loses exactly the node
            # Phase 6.1 needs in order to see two children sharing one source
            # line and flow them ALONG it instead of stacking them.
            if node.type in (NodeType.TEXT, NodeType.SEGMENT):
                node.type = NodeType.GROUP
            return
        tier, inner = hit
        # An element whose own variant scheme owns the wrapper, still sitting
        # here as TEXT because it has not been peeled yet: a link or image
        # (``_[a](/b)_``), a chip (``__`code`__``) or a lone emoji (``_🔎_``).
        # For all of them the underscores select that element's variant, not a
        # text tier, so this pass must not consume them.
        if (
            _LINK_CONTENT_RE.match(inner)
            or IMAGE_RE.fullmatch(inner)
            or INLINE_CODE_RE.fullmatch(inner)
            or _is_lone_emoji(inner)
        ):
            return
        line_id = node.source_line_id
        line = None if line_id is None else self._unwrapped_lines.get(line_id)
        run_len = len(node.content.strip()) - len(node.content.strip().lstrip("_"))
        if line is not None and not _wrap_is_authored(line, run_len, inner):
            return
        node.text_style = tier
        keep_content(node, inner)

    # ------------------------------------------------------------------
    # Subgroup methods  (each returns self for chaining)
    # ------------------------------------------------------------------

    def _subgroup_tables_walk(self, node: MarkdownGroupNode) -> None:
        """Depth-first: find tables in content and replace with structured nodes.

        Time: O(K + N), Space: O(N).
        """
        for child in list(node.children):
            self._subgroup_tables_walk(child)

        if not node.content:
            return

        parts = self.TABLE_BLOCK_RE.split(node.content)
        if len(parts) == 1:
            return  # no tables found

        new_children: list[MarkdownGroupNode] = []
        for i, part in enumerate(parts):
            text = part.strip()
            if not text:
                continue
            # Odd indices are the captured table blocks
            if i % 2 == 1:
                new_children.extend(self._parse_table(text))
            else:
                new_children.append(MarkdownGroupNode(type=NodeType.TEXT, content=text))

        if len(new_children) == 1 and not node.children:
            # Single result, no existing children — absorb into node
            child = new_children[0]
            node.type = child.type
            node.content = child.content
            node.children = child.children
        else:
            node.children = new_children + node.children
            node.content = ""

    @staticmethod
    def _parse_row_cells(line: str) -> list[str]:
        """Extract cell values from a ``|``-delimited row; an escaped ``\\|``
        is not a delimiter (``grouper_escapes.row_cells``).

        Time: O(C) where C is line length. Space: O(C).
        """
        return row_cells(line)

    @staticmethod
    def _parse_col_aligns(sep_line: str) -> list[str | None]:
        """Per-column alignment from a table's delimiter row.

        ``:---`` left, ``:---:`` center, ``---:`` right, ``---`` None.

        None is GFM's "no alignment specified" — that column inherits the
        theme's ``Align`` / the enclosing section's cascade, rather than being
        forced left. (CommonMark itself has no tables; forcing a colon-less
        column left is a browser default-stylesheet artifact, not the spec.)

        Time: O(C) where C is line length. Space: O(C).
        """
        aligns: list[str | None] = []
        for cell in MarkdownGrouper._parse_row_cells(sep_line):
            left, right = cell.startswith(":"), cell.endswith(":")
            if left and right:
                aligns.append("center")
            elif left:
                aligns.append("left")
            elif right:
                aligns.append("right")
            else:
                aligns.append(None)
        return aligns

    def _parse_table(self, block: str) -> list[MarkdownGroupNode]:
        """Convert a raw table block into a list of header/row nodes.

        Returns a flat list of ``table_header`` and ``table_row`` nodes,
        each containing ``paragraph`` children for cells.

        Time: O(C) where C is block length. Space: O(C).
        """
        lines = [line for line in block.strip().split("\n") if line.strip()]
        rows: list[MarkdownGroupNode] = []
        # The separator is the SECOND line, but its alignments have to be known
        # before the FIRST row's cells are built (the header takes the column
        # alignment too, as GFM specifies) — so pre-scan for it rather than
        # discovering it mid-loop.
        aligns = next(
            (
                self._parse_col_aligns(ln)
                for ln in lines
                if self.TABLE_SEP_RE.match(ln.strip())
            ),
            [],
        )

        for idx, line in enumerate(lines):
            # Skip separator row (already read for its alignments, above)
            if self.TABLE_SEP_RE.match(line.strip()):
                continue
            cells = self._parse_row_cells(line)
            if idx == 0:
                row_node = MarkdownGroupNode(type=NodeType.TABLE_HEADER)
                role = "header"
            else:
                row_node = MarkdownGroupNode(type=NodeType.TABLE_ROW)
                role = "body"
            for col, cell_text in enumerate(cells):
                cell = MarkdownGroupNode(type=NodeType.TABLE_CELL, content=cell_text)
                cell.table_role = role
                # A short delimiter row leaves the extra columns unaligned
                # rather than raising.
                cell.table_align = aligns[col] if col < len(aligns) else None
                row_node.children.append(cell)
            rows.append(row_node)

        return rows

    def subgroup_by_blank_lines(self) -> "MarkdownGrouper":
        """Split every node's content by ``\\n\\n`` → *paragraph* children.

        Time: O(K + N), Space: O(N).
        """
        if self.ast is None:
            self.to_ast()
        assert self.ast is not None
        self._subgroup_content(self.ast, _split_blank_lines)
        return self

    def subgroup_by_all_lists(self) -> "MarkdownGrouper":
        """Detect any markdown list (unordered, ordered, task)
        and split into labeled children.

        Labels assigned per item:
          - ``list_item``    — unordered  (``- `` / ``* `` / ``+ ``)
          - ``ordered_item`` — ordered    (``1. `` / ``2) ``)
          - ``task_open``    — unchecked  (``- [ ] ``)
          - ``task_done``    — checked    (``- [x] `` / ``- [X] ``)

        Time: O(K + N), Space: O(N).
        Up to 3 regex attempts per line, still O(1) per char.
        """
        if self.ast is None:
            self.to_ast()
        assert self.ast is not None
        self._subgroup_content(self.ast, _split_all_lists)
        return self

    # ------------------------------------------------------------------
    # Multi-splitter subgroup methods
    # ------------------------------------------------------------------

    def _subgroup_content_classified_multi(
        self,
        node: MarkdownGroupNode,
        splitters: list,
    ) -> None:
        """Apply multiple authored splitters in a single tree walk.

        For each node, applies the first splitter. If it produces children, the
        remaining splitters are applied to those children via
        ``_apply_splitter_recursive``. This avoids redundant tree walks.

        Time: O(K + S*N), where S is the number of splitters.
        Space: O(N).
        """
        for child in list(node.children):
            self._subgroup_content_classified_multi(child, splitters)
        _flatten_empty_text(node)

        # A BREAK leaf joins IMAGE and LINK here for the same reason: its
        # content is the SPELLING the author wrote, not content to be parsed.
        # _segment_lines_with_hrs already claimed the line and minted the node,
        # and every dash spelling holding a space is also a list item to the
        # list splitter — ``- - -`` and ``- ---`` both are. Re-reading one lands
        # in the else-branch below (the absorb needs ``node.type == TEXT``, and
        # a rule is not TEXT), which empties the rule and nests the spelling
        # under it as a child. That costs the paint outright: a horizontal_rule
        # only draws when it reaches the renderer as a LEAF, so a rule with a
        # child renders its child's literal "---" as a line of text instead.
        # ``_ _ _`` was never hit only because no splitter matches underscores.
        if (
            not node.content
            or node.type in (NodeType.IMAGE, NodeType.LINK)
            or node.type in _BREAK_TYPES
        ):
            return

        for i, splitter in enumerate(splitters):
            if node.content:
                result = splitter(node.content)
                if result is None:
                    continue
                if self._apply_splitter_pieces(node, result):
                    # Apply remaining splitters to the newly created children
                    for remaining in splitters[i + 1 :]:
                        for child in list(node.children):
                            self._apply_splitter_recursive(child, remaining)
                    break

    def _apply_splitter_pieces(
        self, node: MarkdownGroupNode, result: list
    ) -> list[MarkdownGroupNode]:
        """Put a splitter's ``(label, text)`` *result* into *node*; return the
        children it nested, or ``[]`` when the one piece was absorbed.

        Shared by the two walks that apply such a splitter to a node's content
        — the multi-splitter walk above (lists, blockquotes) and the element
        walk (images, :meth:`_peel_boundary_dps_walk`) — so absorbing or
        nesting a split cannot come to mean two different things.
        """
        # A single whole-content piece is absorbed in place. TEXT and SEGMENT
        # only: those two are "a piece of a line", which is what a
        # whole-content split result replaces. Every other label is something
        # the node must stay -- a VALUE, a list item, a table cell, and above
        # all a heading, which would otherwise BECOME the image in
        # ``## ![logo](x)``. The image split runs after segments exist, and a
        # SEGMENT holding one image is that image, not a wrapper around it.
        if (
            len(result) == 1
            and not node.children
            and node.type in (NodeType.TEXT, NodeType.SEGMENT)
        ):
            node.type, node.content = result[0][0], result[0][1]
            node.list_number = _item_number(result[0])
            return []
        new_children = [
            MarkdownGroupNode(type=item[0], content=item[1]) for item in result
        ]
        for child, item in zip(new_children, result):
            child.list_number = _item_number(item)
        _inherit_glue(node, new_children, self._ids)
        if node.data_points:
            partitioned = _partition_data_points(node.content, node.data_points, result)
            for child, dps in zip(new_children, partitioned):
                child.data_points = dps
            node.data_points = []
        if node.type == NodeType.TEXT:
            node.type = NodeType.GROUP
        node.children = new_children + node.children
        node.content = ""
        node.applicable = None  # now an internal node; cache no longer needed
        return new_children

    def _apply_splitter_recursive(self, node: MarkdownGroupNode, splitter) -> None:
        """Apply a single splitter depth-first, ungated.

        Used internally by ``_subgroup_content_classified_multi`` to apply
        remaining splitters to children created by an earlier splitter.

        Time: O(K + C), Space: O(C).
        """
        for child in list(node.children):
            self._apply_splitter_recursive(child, splitter)
        _flatten_empty_text(node)

        if not node.content:
            return

        result = splitter(node.content)
        if result is None:
            return

        if len(result) == 1 and not node.children:
            node.type, node.content = result[0]
        else:
            new_children = [
                MarkdownGroupNode(type=label, content=text) for label, text in result
            ]
            _inherit_glue(node, new_children, self._ids)
            if node.data_points:
                partitioned = _partition_data_points(
                    node.content, node.data_points, result
                )
                for child, dps in zip(new_children, partitioned):
                    child.data_points = dps
                node.data_points = []
            if node.type == NodeType.TEXT:
                node.type = NodeType.GROUP
            node.children = new_children + node.children
            node.content = ""

    # ------------------------------------------------------------------
    # Data point annotation
    # ------------------------------------------------------------------

    _ANNOTATE_DEFAULT_LABELS: set[str] = {
        NodeType.TEXT,
        NodeType.KEY,
        NodeType.VALUE,
        NodeType.LIST_ITEM,
        NodeType.ORDERED_ITEM,
        NodeType.TASK_OPEN,
        NodeType.TASK_DONE,
        NodeType.BOLD,
        NodeType.ITALIC,
        NodeType.STRIKETHROUGH,
        NodeType.INLINE_CODE,
        NodeType.TABLE_CELL,
    }

    # ------------------------------------------------------------------
    # Optimised full pipeline
    # ------------------------------------------------------------------

    def process(
        self,
        criteria: SplitCriteria | None = None,
        detector: DataPointDetector | None = None,
    ) -> "MarkdownGrouper":
        """Group the document; see :meth:`_process_once` for the pipeline.

        A document with ``+++`` spacers is grouped without them, and a second
        grouping WITH them only says where each belongs (``grouper_spacers``,
        ADR-203): a spacer is blank space and must not change the tree.
        """
        plain = strip_spacer_lines(self.text)
        if plain is None:
            return self._process_once(criteria, detector)
        # One memo for both groupings: they ask the detector and criteria about
        # nearly the same text, so the second is mostly answered already.
        criteria, detector = memoized(criteria, detector)
        spaced = MarkdownGrouper(self.text)
        spaced._process_once(criteria, detector)
        self.text = plain
        self._process_once(criteria, detector)
        if (
            self.ast is None
            or spaced.ast is None
            or not stamp_spacers(self.ast, spaced.ast)
        ):
            self.ast = spaced.ast
        elif self.ast.children:
            # Node ids are positions, and the spacers took some: number the
            # tree again. Their hashes are silenced, so no fingerprint moves.
            ASTPatternAnalyzer(self.ast).fingerprints(include_unique=True)
            # The spacers are leaves, and a group's leaf kinds count them.
            _stamp_leaf_kinds(self.ast)
        return self

    def _process_once(
        self,
        criteria: SplitCriteria | None = None,
        detector: DataPointDetector | None = None,
    ) -> "MarkdownGrouper":
        """Run the complete parsing pipeline in the optimal order.

        Equivalent to calling every ``subgroup_by_*`` method individually, but
        sharing walks where the phases allow it — notably
        ``_separate_structured_content_walk``, one depth-first pass that
        annotates each leaf and then immediately applies KV detection,
        separator and emoji splits, sharing a single criteria call per node
        (styled key-value detection included), and
        ``_subgroup_content_classified_multi``, which applies several splitters
        per visit.

        The pipeline is many full-tree traversals, but **traversals are not what
        it costs**: detection dominates (Phases 3, 4+5 and 5.5 each re-detect
        per node), and each structural walk is cheap. So when adding a phase,
        the thing to keep down is how many times content reaches the detector
        and the split criteria — not the number of walks. That is why Phase
        2.13 splices card bodies in as raw structure to ride the shared passes
        once, rather than running a nested ``process()`` over them.

        Re-asking about the SAME text is free: both are memoized
        (``grouper_memo``), for one call or, with the grouping kit, across
        calls.

        Parameters
        ----------
        criteria :
            A ``SplitCriteria`` (rules only; needs ``.applicable(text)``).
        detector :
            A ``DataPointDetector`` instance.  A fresh one is created when
            *None* is passed.
        Returns *self* for chaining.
        """
        # A memo per call unless the caller brings the kit's (see grouper_memo):
        # most questions the phases ask the detector and criteria are repeats. Wrapping
        # here reaches every phase through the parameters it already takes.
        criteria, detector = memoized(criteria, detector)

        # Only this entry point runs Phase 2.13, so only this one may plant
        # card sentinels (see _rewrite_constructs).
        self._extract_cards = True

        # Phase 1 — block structure (order-sensitive)
        self.to_ast()
        assert self.ast is not None
        self._subgroup_content(self.ast, _split_blank_lines, crosses_segments=True)
        self._subgroup_tables_walk(self.ast)
        self._subgroup_content(self.ast, _split_newlines, mints_segments=True)

        # Phase 2 — list extraction only. Item bodies are kept raw (multi-line,
        # blank lines preserved) so the body-restructuring pass below can give
        # them their own paragraph / glued-segment structure. Images are split
        # much later (the Phase 5.5 element walk), not here, so an image inside a list body is
        # positioned inside its paragraph's glued segment rather than hoisted
        # out as a sibling.
        # Links are not split here; a boundary link is peeled later by
        # _peel_boundary_dps_walk (ADR-200), like a boundary emoji.
        self._subgroup_content_classified_multi(
            self.ast,
            [_split_all_lists, _split_blockquote],
        )
        self._prune_empty(self.ast)

        # Phase 2.1 — restructure each multi-line list-item / blockquote body
        # like a mini-document (blank-split → newline-split/mint), scoped to
        # those subtrees (via _LIST_ITEM_LABELS) so other content is untouched.
        self._restructure_list_bodies(self.ast)

        # Phase 2.1b — stamp each ordered item's 1-based running ordinal for the
        # numbered-list gutter marker (the source number is discarded upstream).
        self._stamp_list_ordinals(self.ast)

        # Phase 2.13 — expand block-content link/image cards. Placed here
        # because list markers are stripped by now (so a card that is a list
        # item's body cannot destroy the marker) and because everything below
        # — line ids, the image split, and all of Phase 3+ — then walks a
        # card's children as ordinary nodes, exactly once. Skipped entirely
        # when the document has no cards.
        if self._card_specs:
            self._expand_cards_walk(self.ast)
            self._prune_empty(self.ast)

        # Phase 2.15 — stamp per-physical-source-line ids. At this point every
        # content leaf is exactly one source line (Phase 1 newline split and
        # Phase 2.1 list-body restructure have run; the image split below is
        # intra-line and inherits each parent leaf's id via _inherit_glue). No
        # later pass mints a new line, so every same-line intra-line split
        # inherits one shared id.
        self._assign_source_line_ids(self.ast)

        # Phase 2.16 — authored display tiers, whole-LINE pass. Deliberately
        # here, before datapoint detection: ``_`` is a regex word character, so
        # a ``\b``-anchored pattern sees ``___$412M___`` differently from
        # ``***$412M***`` and matches only ``$412``, splitting the line and
        # leaving stray markers. Consuming the wrapper first hands the detector
        # clean content. Whole-SEGMENT wraps can't be seen yet (segments don't
        # exist until Phase 4+5), so Phase 6.055 runs the same pass again — it
        # is idempotent, the first pass having already stripped what it stamped.
        self._unwrapped_lines = {}
        self._annotate_text_style_tiers(self.ast, record=True)

        # Phase 2.165 — consume the end-of-line VERTICAL ALIGN tokens
        # (`@tp` / `@ct` / `@bs` / `@bm`), recorded against their source line
        # and applied at Phase 6.1 to whichever container turns out to BE that
        # line. Here for the same two reasons as the tiers just above: every
        # content leaf is one source line at this point, and the detector has
        # not run, so the token never reaches it or the split criteria. It also
        # settles the order against the spring — Phase 4+5 reads a line's
        # content after this, so `... @ct` hands the trailing-spring rule the
        # line the author meant rather than one ending in a token.
        line_valigns = consume_line_valigns(self.ast)

        # Safety net: nothing should still hold a sentinel, but if the scanner
        # and the expander ever disagree, put the original markdown back so the
        # construct degrades to its markdown instead of painting the
        # token. Must run before the detector sees any content.
        if self._card_specs:
            self._restore_unexpanded_sentinels(self.ast)

        # Phase 3 — data-point annotation before any inline splitting.
        # Gives Phase 4+5 access to protected ranges so data-point regions
        # (URLs, prices, …) are never split at a colon or separator.
        _annotate_data_points_walk(self.ast, detector)

        # Phase 4+5 — prune + annotate + separate (one walk). Structural only:
        # separators, KV, lists, and inner datapoints (criteria-gated).
        # Re-annotation here picks up nodes created after Phase 3
        # (key/value/segment/bold children) and refreshes indices on split nodes.
        _separate_structured_content_walk(
            self.ast, detector, criteria, self._ANNOTATE_DEFAULT_LABELS, self._ids
        )

        # Phase 5.5 — the element walk: images, then the boundary emoji / link /
        # chip peel, node by node in ONE post-order walk (see
        # _peel_boundary_dps_walk).
        #
        # Images come AFTER every pass that reads a line as one string: springs,
        # separators, key-values, colon columns, like every other element. An
        # image cut earlier would arrive at those passes having already cut the
        # line into pieces, stranding its ` - ` or its `...` in a text leaf that
        # nothing claims. Image pieces still share their line's id: an
        # intra-line split inherits its parent's id through `_inherit_glue`.
        #
        # Within each node the image split runs first, so `_split_elements`
        # sees a line whose images are already out of the way. The peel is ungated and runs after all
        # structural splitting, so every leaf's leading / trailing element run
        # is peeled uniformly (no pre-split hoisting, no pure-emoji-separator
        # special case).
        self._peel_boundary_dps_walk(self.ast, detector)

        # Phase 5.55 — drawing elements: sliders, then task controls (standard
        # task markers were stripped by the list pass). After every pass that
        # reads a line as one string, for the same reason as images at 5.5: cut
        # earlier, a control stranded its ` - ` or `...` in a text leaf nothing
        # claimed. Until then the DRAWING_ELEMENT guard (detector_scope) keeps
        # each token whole and away from PERCENTAGE.
        split_sliders(self.ast, self._ids)
        split_task_controls(self.ast, self._ids)
        restore_escaped_task_controls(self.ast)
        restore_escaped_sliders(self.ast)

        # Phase 5.6 — wrap source-glued content segments before collapsing.
        _wrap_glued_content(self.ast)

        # Phase 6 — collapse redundant group nodes (0 or 1 child)
        _collapse_groups(self.ast)

        # Phase 6.04 — the root is a CONTAINER, never a leaf. _build_block_ast
        # leaves a heading-less, break-less document's text on the root for the
        # Phase 1 splits to break up; in a document that is ONE leaf there is
        # nothing to break up, so the text stays on the root and the root gains
        # no child. Every other node means "a leaf to draw" by having content,
        # but the generator reads a childless root as an empty document — so
        # the shortest reply an agent can write, one sentence, would draw a
        # blank page.
        # Placed after the collapse because that is the last pass that can leave
        # a node childless, and before the annotation phases so the new child is
        # stamped like any other leaf.
        _wrap_lone_root_content(self.ast)

        # Phase 6.05 — flag table containers (table_group) on the collapsed
        # tree, before node_ids exist, so the layout generator consumes the
        # flag instead of guessing from child types.
        grouper_displays._flag_table_groups(self.ast)

        # Phase 6.055 — stamp authored display tiers (`_x_` / `__x__` /
        # `___x___`) and consume the underscore wrapper. After the collapse so
        # every leaf is its final line-or-segment (which is what makes the
        # whole-leaf scope check exact), and before 6.06 so an explicit tier
        # wins over an inferred stat tile.
        self._annotate_text_style_tiers(self.ast)

        # Phase 6.06 — stamp datapoint display replacements (ratio/unit bars,
        # kv percent bars, date chips) with their self-contained payloads,
        # while in-memory data_points are attached.
        # Unconditional: THEME.md toggles gate consumption, not the AST.
        _annotate_datapoint_displays(self.ast)

        # Phase 6.065 — turn each date-chip leaf into a group(text[key],
        # text[day]) so repeated adjacent chips form a distinct, uniform
        # fingerprint the rule layout grids (only GROUP runs grid; leaf runs
        # stack). Runs before fingerprints (6.5) and line-split (6.1).
        _wrap_date_chip_groups(self.ast)

        # Phase 6.07 — flag chart containers (chart_group, line_group) over bullet
        # runs of Key: value rows in one unit, mirroring the table wrap; a chart wins
        # over the per-row kv_percent_bar and line_chart flags inside it.
        grouper_charts._flag_charts(self.ast)

        # Phase 6.075 — a pair exists only while a display reads it (ADR-205):
        # every `Key: value` pair no display or chart took is its line again.
        unpair_unread(self.ast, detector)

        # Phase 6.08 — restore opaque code blocks only after every pass that
        # interprets Markdown content. Their sentinel established the block's
        # position; the exact source and language now become one CODE_BLOCK
        # leaf, so later stages consume structure rather than re-inferring it.
        if self._code_specs:
            expand_code_blocks(self.ast, self._code_specs, self._ids)
            restore_code_blocks(self.ast, self._code_specs)

        # Phase 6.1 — derive line_split_group from source_line_id: a container
        # flows its children aside iff they are the pieces of ONE physical
        # source line (>=2 content children sharing a source_line_id). Also
        # stores each group's effective source-line id for the generator.
        _derive_line_split_groups(self.ast, line_valigns)

        # Phases 6.15–6.245 — five stamps on the now-final structure, in ONE
        # pre-order walk (_stamp_finished_tree says why fusing them is exact):
        #   6.15  one glue per STACKED block (a Key: value pair, a colon
        #         column). Glue is minted per source LINE, so a line of several
        #         blocks gets one wrapper for the whole line, which 6.1 clears
        #         as a flowed line — leaving the blocks with no glue at all. Must follow 6.1: that pass is post-order, this one needs
        #         ancestor state that is only final once its clears have run.
        #   6.17  drop the separator backslashes; all the splitting is done, so
        #         from here they would only be drawn.
        #   6.2   tag each EMOJI leaf with its render role (heading / text /
        #         alone) and its sibling ordinal, from the now-final heading
        #         context, so the renderer never re-derives it.
        #   6.24  carry a fixed heading style through exactly the section it
        #         owns.
        #   6.245 stamp Root/heading/fixed/list/quote/image-card styling
        #         ancestry for local text-role inheritance.
        # Later stages consume these annotations; they never infer them from
        # text or layout.
        _stamp_finished_tree(self.ast)
        # Any inline spacer mark no separator consumed is the author's `+++`.
        restore_inline_spacer_text(self.ast)

        # Phase 6.246 — each task control's document ordinal and the label of
        # the item it starts, into its drawing_element payload: what a click on
        # it reports (render_actions). After 6.17, so a label is the drawn text.
        stamp_task_controls(self.ast)
        stamp_sliders(self.ast)
        grouper_feed_slots.stamp(self.ast, self._feed_slots)

        # Phase 6.25 — stamp each node's color-rotation slot. Needs the final
        # heading/glue structure (it counts per enclosing section) and the
        # emoji/code variants captured at peel time, so it runs after 6.2.
        _annotate_rotation_indices(self.ast)

        # Phase 6.26 — what each group's leaves all are (pills / keys) and the
        # document's top heading level: the generator reads them on every
        # layout instead of walking subtrees to ask.
        _stamp_leaf_kinds(self.ast)

        # Phase 6.5 — fingerprint & annotate text_length_category on the
        # final tree, so callers don't need a separate fingerprints() call to
        # get populated text_length_category off process().
        ASTPatternAnalyzer(self.ast).fingerprints(include_unique=True)

        return self

    def _peel_boundary_dps_walk(
        self, node: "MarkdownGroupNode", detector: DataPointDetector
    ) -> None:
        """Phase 5.5, the element walk: cut out images, then peel the boundary
        ELEMENT run — emoji, links and chips alike — from every leaf of the
        already-separated tree.

        ONE post-order walk does, at each node:

        1. unwrap contentless TEXT wrappers and drop empty leaves — exactly
           ``_flatten_empty_text`` and the ``_prune_empty`` predicate;
        2. cut out images (``_split_images``), absorbed or nested by the same
           :meth:`_apply_splitter_pieces` the multi-splitter walk uses;
        3. peel the pieces that cut produced, then the node itself
           (:meth:`_peel_elements`).

        Children are finished before their parent and each step touches only
        its own node. Neither step creates an empty leaf, which is why the
        prune can run per node instead of over the whole tree.

        Glued ids are minted in post-order, the image split's and the peel's
        interleaved. Nothing reads the value, only which nodes share one.
        """
        for child in list(node.children):
            self._peel_boundary_dps_walk(child, detector)
        _flatten_empty_text(node)
        node.children = [
            c
            for c in node.children
            if c.content or c.children or c.type in _KEEP_WHEN_EMPTY
        ]
        # A BREAK leaf's content is its spelling, and an image / link is already
        # an element: neither is a line to cut (see the same guard in
        # :meth:`_subgroup_content_classified_multi`).
        if (
            node.content
            and node.type not in (NodeType.IMAGE, NodeType.LINK)
            and node.type not in _BREAK_TYPES
        ):
            result = _split_images(node.content)
            if result is not None:
                for piece in self._apply_splitter_pieces(node, result):
                    self._peel_elements(piece, detector)
        self._peel_elements(node, detector)

    def _peel_elements(
        self, node: "MarkdownGroupNode", detector: DataPointDetector
    ) -> None:
        """Peel *node*'s boundary element run — the per-node half of the
        element walk.

        Not gated by the split criteria — a uniform finishing step run after all
        structural separation (separators, KV, inner datapoints).
        :meth:`_split_elements` handles all three element kinds — emoji, links
        and backtick spans — in ONE pass, so the whole leading/trailing run is
        peeled at once and there is no second pass to nest its leftovers. Data
        points inside a paren/quote range are skipped so protected spans like
        ``(↗️ emoji)`` stay intact.

        A split nests in place (via :meth:`_apply_split_result`) so same-line
        content stays grouped: the leaf becomes a container holding the peeled
        run and the remainder (TEXT promoted to GROUP, a heading{n} kept as its
        own container).

        Data points are **re-detected** on the leaf's current content rather than
        reused from the structural phase: marker re-balancing there can shift a
        boundary dp off its annotated offset (e.g. ``***💵 ~~$29.99~~***`` →
        the ``***💵***`` remainder), and fresh detection gives accurate
        positions for the peel and the child partition.
        """
        if not node.content or node.type in (
            NodeType.IMAGE,
            NodeType.LINK,
            NodeType.EMOJI,
            NodeType.DATAPOINT,
            NodeType.INLINE_CODE,  # literal code — never peel its contents
        ):
            return

        dps = _detect_through_markers(node.content, detector)
        # A backtick span is an element too and is NOT a data point (see
        # _element_hits), so a pure chip line — ``` `Sale` `New` ``` — carries no
        # dps at all and must still reach the splitter.
        if not dps and not INLINE_CODE_RE.search(node.content):
            return
        dps = [
            piece
            for dp in dps
            for piece in (
                self._expand_emoji_run_dp(node.content, dp, detector)
                if dp["type"] == DataPointType.EMOJI
                else [dp]
            )
        ]

        node_pq = node.paren_quote_ranges
        if node_pq:
            effective_dps = [
                dp
                for dp in dps
                if not any(ps <= dp["start"] and dp["end"] <= pe for ps, pe in node_pq)
            ]
        else:
            effective_dps = dps

        # Root remainder pieces are plain TEXT (see _apply_all_datapoints_to_node).
        piece_label = NodeType.TEXT if node.type == "root" else node.type
        result = _split_elements(node.content, piece_label, effective_dps)
        if result is None:
            return
        # Refresh node.data_points so the partition uses the accurate
        # (re-detected) positions.
        node.data_points = dps

        # Every split nests in place so same-line content stays grouped: the
        # whole leading/trailing boundary run plus the remainder become children
        # of one container in a single step (TEXT is promoted to GROUP; a
        # heading{n} keeps its label and holds the run inside it; VALUE /
        # SEGMENT / LIST_ITEM and the document root keep their identity too).
        # A single whole-content dp is relabelled in place. See
        # _apply_split_result.
        # Variants ride along on the pieces (_split_elements captures each
        # element's own wrapper before consuming it) and are stamped by
        # _build_split_children / _apply_split_result.
        _apply_split_result(node, result, node_pq, self._ids)

    @staticmethod
    def _expand_emoji_run_dp(
        content: str, dp: dict, detector: DataPointDetector
    ) -> list[dict]:
        """Expand a single EMOJI data point spanning multiple visual emoji
        into one data point per emoji, so :meth:`_split_elements` peels
        one node per emoji (mirroring LINK, which is already one dp per link).

        Reuses ``detector_parsers._parse_emoji`` to rebuild ``value`` for each piece
        so its shape (``emojis``/``count``/``text``) matches what detection
        would have produced for that piece alone. A single-cluster dp is
        returned unchanged.
        """
        span_text = content[dp["start"] : dp["end"]]
        clusters = _split_emoji_clusters(span_text)
        if len(clusters) <= 1:
            return [dp]
        expanded = []
        for start, end in clusters:
            cluster_text = span_text[start:end]
            expanded.append(
                {
                    "type": dp["type"],
                    "matched": cluster_text,
                    "value": _parse_emoji(cluster_text),
                    "start": dp["start"] + start,
                    "end": dp["start"] + end,
                    "is_approximate": False,
                }
            )
        return expanded


class ASTPatternAnalyzer:
    """Analyze repeated tree patterns in a MarkdownGroupNode AST.

    Does NOT modify the original tree.  Uses **node paths** — tuples of
    child indices like ``(0, 2, 1)`` — as stable references back to the
    AST.  Call ``node_at(path)`` to resolve any path to its node.

    Complexity variables:
        K = total nodes in the AST
        D = max depth of the tree

    Example::

        analyzer = ASTPatternAnalyzer(grouper.ast)
        for fp, paths in analyzer.fingerprints().items():
            nodes = [analyzer.node_at(p) for p in paths]
    """

    def __init__(self, root: MarkdownGroupNode):
        self.root = root
        self._index: dict[str, MarkdownGroupNode] = {}
        # hash -> [leaf word counts per instance]
        self._hash_word_counts: dict[int, list[int]] = {}
        # The _line_kind_hash cache, keyed by id(node): alive only for the
        # duration of one fingerprints() call (see there).
        self._line_kinds: dict[int, int | None] = {}

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    def node_at(self, path: tuple[int, ...]) -> MarkdownGroupNode:
        """Resolve a path to its MarkdownGroupNode in the original tree.

        Time: O(D), Space: O(1).

        Args:
            path: Tuple of child indices.  ``()`` = root, ``(0,)`` = first
                  child, ``(0, 2)`` = third child of first child, etc.
        """
        node = self.root
        for idx in path:
            node = node.children[idx]
        return node

    # ------------------------------------------------------------------
    # Approach 1 — Structural fingerprinting
    # ------------------------------------------------------------------

    def fingerprints(
        self, max_depth: int | None = None, include_unique: bool = False
    ) -> dict[str, list[tuple[int, ...]]]:
        """Map each structural fingerprint to the node paths that share it.

        Time: O(K), Space: O(K).

        A fingerprint encodes ``label(child_fps...)`` recursively, e.g.
        ``"heading(paragraph(),list_item(),list_item())"``.

        Args:
            max_depth: If set, truncate fingerprints below this depth
                       (nodes deeper than *max_depth* are recorded as
                       ``"label(...)"``)
            include_unique: If True, also return fingerprints that appear
                            only once.  Default False (2+ only).

        Returns:
            ``{fingerprint: [path, ...]}``
        """
        all_fps: dict[str, list[tuple[int, ...]]] = {}
        self._hash_word_counts = {}
        # The line-kind cache is keyed by id(node), and an id is only a
        # node's identity while that node is alive — so it lives exactly as
        # long as this call and is emptied on the way out, never carried to a
        # later call on a tree that may have changed.
        self._line_kinds = {}
        try:
            self._build_fingerprint(self.root, (), 0, max_depth, all_fps)
        finally:
            self._line_kinds = {}
        self._annotate_text_lengths()
        if include_unique:
            return all_fps
        return {fp: paths for fp, paths in all_fps.items() if len(paths) >= 2}

    def _annotate_orphans(self, node: MarkdownGroupNode) -> None:
        """Flag lone children that are single members of a KIND *node*'s sibling
        runs grid, so the layout can render them at the siblings' card width.

        For each contiguous same-kind run of *node*'s children (``repeated_children``),
        collect the kinds that appear as a repeated bucket inside any run member (i.e.
        kinds that DO grid somewhere in the run). Then, in any run member, a child
        whose ``kind_hash`` is one of those kinds and occurs exactly once among that
        member's children is an "orphaned repeated element" — mark it ``orphan_grid``.
        Strictly kind-gated, so unique content is never swept in.

        Operates on a SINGLE node: called from ``_build_fingerprint`` the moment
        ``node.repeated_children`` is assigned (its children's own buckets/kinds are
        already computed bottom-up), so no separate tree traversal is needed.
        """
        for run in (node.repeated_children or {}).values():
            repeated_kinds: set[int] = set()
            for m in run:
                for bucket in (m.repeated_children or {}).values():
                    if len(bucket) >= 2 and bucket[0].kind_hash is not None:
                        repeated_kinds.add(bucket[0].kind_hash)
            if not repeated_kinds:
                continue
            for m in run:
                counts: dict[int, int] = {}
                for c in m.children:
                    if c.kind_hash is not None:
                        counts[c.kind_hash] = counts.get(c.kind_hash, 0) + 1
                for c in m.children:
                    if c.kind_hash in repeated_kinds and counts.get(c.kind_hash) == 1:
                        c.orphan_grid = True

    def _build_fingerprint(
        self,
        node: MarkdownGroupNode,
        path: tuple[int, ...],
        depth: int,
        max_depth: int | None,
        out: dict[str, list[tuple[int, ...]]],
    ) -> tuple[str, int, str]:
        tag = node.type
        if max_depth is not None and depth >= max_depth:
            fp = tag + "(...)"
            leaf_wc = drawn_word_count(node)
            # Truncated: no recursion, so the kind signature is the bare type
            # (callers use max_depth=None, so this path is not exercised by the
            # grid bucketing below).
            kind_sig = kind_up = str(tag)
        else:
            child_results = [
                self._build_fingerprint(child, path + (i,), depth + 1, max_depth, out)
                for i, child in enumerate(node.children)
            ]
            # A spacer is blank space (ADR-203): indexed like any child, but
            # silenced — no part of what its parent matches.
            child_results = [
                r
                for r, c in zip(child_results, node.children)
                if c.type != NodeType.SPACER
            ]
            child_fps = [r[0] for r in child_results]
            child_wcs = [r[1] for r in child_results]
            child_kinds = [r[2] for r in child_results]

            # The "same-kind" signatures: what this node runs on, and what it
            # adds to its parent's (see kind_signatures).
            kind_sig, kind_up = kind_signatures(node, child_kinds)

            # Segment children into maximal contiguous "same-kind" RUNS, each
            # keyed by a unique run_key. A sibling extends the current run when it
            # is exact-kind equal to its predecessor OR — for multi-child groups
            # (cards) only — within the recursive tree-edit tolerance of the run's
            # SEED (_tree_similar). Anchoring every member to the seed (not the
            # previous member) bounds drift: A,B,C only co-run if each is within
            # budget of one reference card, so look-alikes can't chain apart.
            # Leaf/childless members (pills, KV lines, plain texts) only ever
            # match exactly. Runs stay contiguous and in document order — the layout
            # grid never pulls non-adjacent siblings together — and the generator
            # re-segments each run into columns at render time.
            # Spacers are silenced here too: a run reads straight past one.
            kids = [c for c in node.children if c.type != NodeType.SPACER]
            buckets: dict[int, list[MarkdownGroupNode]] = {}
            n_kids = len(kids)
            i = 0
            while i < n_kids:
                seed = kids[i]
                j = i + 1
                while j < n_kids:
                    cur = kids[j]
                    prev = kids[j - 1]
                    joined = (
                        cur.kind_hash is not None and cur.kind_hash == prev.kind_hash
                    ) or (
                        seed.children
                        and cur.children
                        and _tree_similar(seed, cur, self._line_kinds)
                    )
                    if not joined:
                        break
                    j += 1
                run = kids[i:j]
                if len(run) >= 2 and all(m.kind_hash is not None for m in run):
                    run_key = _fnv1a_64(run[0].node_id + "#run")
                    for m in run:
                        m.run_key = run_key
                    buckets[run_key] = list(run)
                i = j if j > i else i + 1
            node.repeated_children = buckets
            # Flag orphaned repeated elements now — children's buckets/kinds are
            # already computed (bottom-up), so no separate traversal is needed.
            self._annotate_orphans(node)

            # Cache the immediate children's type composition on the node so
            # consumers (e.g. layout rules) can ask "what types are here, and
            # how many of each?" in O(1) without re-walking children.
            node.child_types = [c.type for c in node.children]
            type_counts: dict[str, int] = {}
            for t in node.child_types:
                type_counts[t] = type_counts.get(t, 0) + 1
            node.child_type_counts = type_counts

            # Order- and count-preserving fingerprint: every child fingerprint
            # is included in document order, so [text, image, text] and
            # [image, text] produce distinct hashes.
            fp = tag + "(" + ",".join(child_fps) + ")"

            # Leaf word count: own content if leaf, else sum of children's counts
            if not node.children:
                leaf_wc = drawn_word_count(node)
            else:
                leaf_wc = sum(child_wcs)

            # A datapoint value fingerprints as plain TEXT so a stat block
            # matches structurally regardless of how the value ended up shaped:
            #   * a same-line datapoint SPLIT group (one value line shattered
            #     into datapoint/text pieces, e.g. "750/1800 Kcal", "75/100g"),
            #     which must collapse to a single TEXT leaf (not
            #     group(text(),text())) so it matches the unsplit value line; and
            #   * a pure DATAPOINT LEAF (a whole value like "$129,201.40" or
            #     "+$22,910"), so it matches a value that DID split (e.g.
            #     "+2,588" → text) — both read as "one value" for structure.
            # Only the emitted fingerprint changes; children still recurse above
            # (node_ids/index assigned) and the node type/data_points/rendering
            # are untouched.
            if _is_datapoint_split_group(node) or (
                not node.children and node.type == NodeType.DATAPOINT
            ):
                fp = NodeType.TEXT + "()"

        node.run_key, node.orphan_grid = None, False  # no earlier pass's run survives
        node.fingerprint_hash = _fnv1a_64(fp)
        node.kind_hash = _fnv1a_64(kind_sig)
        node.node_id = ".".join(str(i) for i in path)
        self._index[node.node_id] = node
        out.setdefault(fp, []).append(path)
        self._hash_word_counts.setdefault(node.fingerprint_hash, []).append(leaf_wc)
        return fp, leaf_wc, kind_up

    def _annotate_text_lengths(self) -> None:
        """Annotate every indexed node with avg_word_count and text_length_category.

        Called once after _build_fingerprint has populated _hash_word_counts.
        Each node receives the average leaf word count across all instances
        that share its fingerprint_hash.

        Time: O(K), Space: O(H) where H = distinct hashes.
        """
        avg_by_hash: dict[int, float] = {
            h: sum(counts) / len(counts) for h, counts in self._hash_word_counts.items()
        }
        for node in self._index.values():
            h = node.fingerprint_hash
            if h is None:
                continue
            avg = avg_by_hash.get(h)
            if avg is None:
                continue
            node.avg_word_count = round(avg, 2)
            node.text_length_category = _word_count_category(avg)

        # Per-node length: each leaf from its OWN word count (not the cluster
        # average), so a one-word leaf is one_word even when its fingerprint
        # cluster averages longer. Groups inherit the MAX below (widest line).
        for node in self._index.values():
            if node.content and not node.children:
                wc = drawn_word_count(node)
                node.content_length_category = _word_count_category(wc)

        def _propagate(node: MarkdownGroupNode) -> None:
            for c in node.children:
                _propagate(c)
            if not node.content and node.children:
                for attr in ("text_length_category", "content_length_category"):
                    cats = [
                        getattr(c, attr)
                        for c in node.children
                        if getattr(c, attr) is not None
                    ]
                    if cats:
                        setattr(
                            node,
                            attr,
                            max(
                                cats,
                                key=lambda cat: _TEXT_LENGTH_CATEGORY_ORDER.get(
                                    cat, -1
                                ),
                            ),
                        )

        _propagate(self.root)


if __name__ == "__main__":
    sample = """\
# Introduction

Welcome to the guide.
This is the intro paragraph.

More intro content here.

# Getting Started

## Prerequisites

You need Python 3.10+.

## Installation

Run pip install mypackage.

### From source

Clone the repo and run setup.py.

# Features

Key features:

- Fast parsing
- Recursive grouping
- Multiple split strategies

Ordered steps:

1. Install
2. Configure
3. Run

## TODO

- [x] Write parser
- [x] Add heading grouping
- [ ] Add table support
- [ ] Write documentation
"""
    grouper = MarkdownGrouper(sample)
    grouper.to_ast().subgroup_by_blank_lines().subgroup_by_all_lists()

    print("=== Pattern Analysis ===\n")
    assert grouper.ast is not None
    analyzer = ASTPatternAnalyzer(grouper.ast)

    print("--- Repeated structural fingerprints ---")
    for fp, paths in sorted(analyzer.fingerprints().items(), key=lambda x: -len(x[1])):
        print(f"  {len(paths)}x  {fp}")
        for p in paths:
            node = analyzer.node_at(p)
            tag = node.content[:40] or node.type
            print(f"       path={p}  → {tag!r}")
