"""Rule-based layout generator.

Converts a MarkdownGroupNode AST (after ASTPatternAnalyzer.fingerprints() has
been called) into a LayoutNode tree for a given available width.

Precondition: ASTPatternAnalyzer(ast).fingerprints(include_unique=True) must be
called before generate() so that node_id, fingerprint_hash, repeated_children,
text_length_category, avg_word_count, child_types, and child_type_counts are
all populated.
"""

import math

from md2ui.pipeline import generator_displays, generator_markers, generator_spacers
from md2ui.pipeline import generator_fit_votes, generator_spring_wrap
from md2ui.pipeline.layout_script_parser import LayoutNode

# The ``Orphan row`` vocabulary lives with the parser that validates it,
# so the generator and the theme can never disagree on the default.
from md2ui.pipeline.theme import ORPHAN_ROW_DEFAULT, resolve_section_style
from md2ui.pipeline.grouper_types import (
    ELEMENT_LEAF_TYPES,
    STRUCTURAL_BACKGROUND_KINDS,
    same_section_kind,
)
from md2ui.pipeline.markdown_grouper import (
    _HEADING_TYPE_RE,
    MarkdownGroupNode,
    NodeType,
)
from md2ui.pipeline.render_hints import (
    poll_render,
    render_properties_from,
    run_shared,
    sanitize_url_props,
)
from md2ui.pipeline.render_metrics import height_sized, image_floor, with_image_floors
from md2ui.utils.image_params import (
    image_params,
    url_layout_params,
    with_layout_params,
)
from md2ui.pipeline.generator_column_cuts import WIDE_BREAKPOINT, row_groups, stack_of
from md2ui.pipeline.generator_column_cuts import group_gaps
from md2ui.pipeline.grouper_inline_marks import INLINE_SPACERS
from md2ui.pipeline.generator_spacers import spacer_cell
from md2ui.pipeline.value_format import with_unit
from md2ui.pipeline.generator_units import (
    _is_pure_element_group,
    BENTO_MIN_CELLS,
    IMAGE_MIN_WIDTH,
    LEAF_WIDTH,
    _auto_bento_level,
    _batch_width,
    _bento_col,
    _cell_gap,
    _col_gap,
    _estimate_cell_height,
    _fill_container_levels,
    _flow_pair_gap,
    _is_group,
    _is_leaf,
    _length_category,
    _line_run,
    kv_role_map,
    _measured_min_width,
    _min_width,
    _row_pair_gap,
    _section_level,
    _unit_padding_x,
    shares_params,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


# A repeated-item grid's last (ragged) row must fill at least this fraction of the
# columns, else _balance_cols steps the column count down. A 2-col grid ending in
# a single cell is exactly 1/2 and stays allowed.
MIN_LAST_ROW_FILL: float = 0.5

# _kind_cols hands ONE column count to every run of a kind, so the fill rule above
# is a vote rather than a per-run answer: the shared count only steps down when at
# least this share of the kind's runs would end on an under-half row. A THIRD, and
# written as the fraction rather than a rounded decimal, because the commonest
# shape it has to catch is a kind of three runs with one bad one (a section of 2,
# a section of 2 and a section of 4 at three columns) -- 0.34 would miss exactly
# that. Raising it leaves more lonely last rows; lowering it to 0 means "step down
# when ANY run orphans". See _balance_kind_cols.
ORPHAN_RUN_SHARE: float = 1 / 3
# A share is a ratio of small integers and the constant is one too, so compare
# them with a tolerance: 1/3 must count as reaching a third however it was
# divided, and no share should miss its gate by one floating-point bit.
_SHARE_EPSILON: float = 1e-9

# Aspect-aware column capping (_aspect_cap): widen a repeated grid (fewer columns)
# while its tallest member is taller than TARGET_ASPECT * column_width — so cards
# don't render as tall-thin slivers. Because a unit's height-at-width is intrinsic
# to its shape (not the run length), same-kind runs converge on the same column
# count, giving document-wide visual consistency. HEIGHT_GROWTH_CAP guards the
# image-dominated case (where widening only makes a card TALLER, e.g. a stacked
# image list): never widen to a column count whose tallest member exceeds this
# multiple of its height at the fit-max column count — leaving such cards for a
# dedicated future task instead of exploding them.
TARGET_ASPECT: float = 1.5
HEIGHT_GROWTH_CAP: float = 1.3
# How much shorter (px) the tallest member must get for _aspect_cap to drop a
# column: heights are measured per CELL_HEIGHT_BUCKET, so a pixel of wobble is
# the same height, not a shorter one.
ASPECT_CAP_SHORTER_BY: float = 1.0
# The width step _cell_height measures at: every width in a bucket shares the
# height measured at the bucket's floor. 8px speeds generate() up and changes
# no layout; a much coarser bucket rearranges layouts (a card measured too
# narrow comes out taller, and the aspect cap drops a column). Keep it well
# under that cliff.
CELL_HEIGHT_BUCKET: int = 8
# A kind's shared column count (_kind_cols) is aspect-capped against EVERY member
# in the document at every width a trial build tries, which dominates measuring.
# So a large kind is checked on a SAMPLE first:
# its KIND_SWEEP_SAMPLE members the font-free estimate ranks tallest (at
# KIND_SWEEP_RANK_WIDTH, ranked once per kind). Only a sample whose tallest comes
# within KIND_SWEEP_FALLBACK of the aspect threshold pays for the full sweep, so
# every cap that fires is decided on every member. What remains approximate is a
# kind whose unsampled member is >30% taller than all five, which in practice
# does not change a column count.
KIND_SWEEP_SAMPLE: int = 5
KIND_SWEEP_FALLBACK: float = 0.3
KIND_SWEEP_RANK_WIDTH: float = 300.0

# Sentinel for "this generator has not been handed a theme yet", so the block-width
# cache below is built on the first generate() even when that theme is None.
_MISSING = object()


# ---------------------------------------------------------------------------
# Bento (Mondrian mosaic) mode — theme `Layout: bento`
# ---------------------------------------------------------------------------

BENTO_WIDE_WIDTH: float = 760.0  # >= → wide root: 3–5 divisions; else 1–3
BENTO_UNIT_TARGET: float = 260.0  # target px per grid column when picking divisions
BENTO_MAX_DEPTH: int = 3  # guillotine nesting depth (rows within bands)
BENTO_BEAM: int = 4  # Pareto candidates kept per memo state
BENTO_ASPECT_WEIGHT: float = 0.25  # aspect-penalty weight (area-scaled)
BENTO_DEV_STEPS: float = 1e9  # deviation grid: log() differs by platform (ADR-300)


# ---------------------------------------------------------------------------
# Node-type helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# LayoutGenerator
# ---------------------------------------------------------------------------


def _row_weights(
    node: MarkdownGroupNode, count: int, written: list | None = None
) -> list[float] | None:
    """One weight per cell of a ``:::`` row, ALWAYS ``count`` of them -- or
    ``None`` when the author wrote no number anywhere in the row.

    A row with no number is not proportioned at all: its cells collapse to their
    content and wrap like the pieces of a `` - `` line (``_build_column_row``).
    Once one number is written the row is proportions, and a cell whose divider
    carried none takes an equal share, 1.

    The weights are minted with the row in Phase 1, and a later pass can still
    change how many children it has -- the blank-line split cuts a cell that was
    one glued blob into two blocks, and the row then holds more cells than it
    holds weights. Every consumer here zips the two, so a short list would
    silently drop the surplus cells from the page. Padding is the conservative
    repair -- an unweighted cell takes the default share, which is what it would
    have had if the split had happened before the row was minted. Whether that
    cell should have been a cell at all is a Phase 1 question; losing the
    content is wrong either way.
    """
    written = list(node.column_weights or ()) if written is None else written
    if all(w is None for w in written):
        return None
    weights = [1.0 if w is None else w for w in written]
    if len(weights) < count:
        weights += [1.0] * (count - len(weights))
    return weights[:count]


class LayoutGenerator:
    """Per-group layout generator.  Safe to call generate() multiple times.

    The rules own stacking, gridding, flowing and tables. The theme's
    ``Emoji aside`` COMPLEMENTS them: the one arrangement it may impose is
    putting a lone-emoji icon in a gutter beside the rest of its group. An image
    goes beside text only through a ``:::`` row the author writes.
    """

    def __init__(self) -> None:
        # Repeated-run consistency, reset per generate(): the members of a run
        # whose theme asks for an icon gutter (id(node)), and each member's
        # majority-voted render hints (id(node) -> RenderProperties). Both are
        # set by _unify_run so every member of a run is laid out alike.
        self._pinned: set[int] = set()
        self._pinned_render = {}
        self._pinned_card: dict[int, str] = {}  # id(node) -> its polled photo url
        self._fit_polls: list[generator_fit_votes.FitPoll] = []
        # node_id -> "key" | "value": the theme's `Key` / `Value` text roles.
        # Rebuilt per generate(); empty here so a caller that reaches a width
        # helper without generate() (hand-built fixtures do) still finds it.
        self._kv_roles: dict[str, str] = {}
        # URL-authored render hints (``![alt](photo.jpg?md2ui.shape=circle)``),
        # collected per generate() by _collect_url_props: node_id -> the image's
        # own entry (render hints never hoist).
        self._url_props: dict[str, dict] = {}
        self._card_urls = False  # whether any photo card's url writes a param
        self._url_warnings: list[str] = []
        # Set per ``generate()`` call; None keeps the theme-free approximation
        # (padding/spacing budgets collapse to 0) for tests callers.
        self._theme = None
        # True while building the subtree of a marked item that already owns a
        # gutter marker, so nested same-type items (from the emoji peel) don't
        # draw a duplicate marker. Managed in ``_decide_group``.
        self._marker_suppressed = False
        # (owner level, fixed style key, inside a photo card) of the node whose
        # children are being built — what a spacer leaf is sized by. Managed
        # in ``_decide_group`` like ``_marker_suppressed``.
        self._spacer_scope: tuple[int, str | None, bool] = (0, None, False)
        # Whether this generate() made any spacer leaf; only then is there a
        # row to fold one out of.
        self._spacers_built = False
        # Height-for-width callback set per ``generate()`` call; None falls back
        # to the fonts-free ``_estimate_cell_height`` heuristic.
        self._measure = None
        # Minimum-unbreakable-width callback (whole pills, single words) set
        # per ``generate()`` call; None keeps the category-only min widths.
        self._measure_width = None
        # Full-single-line-width callback set per ``generate()`` call; the
        # line-split flow uses it to batch one line's pieces back into rows.
        self._measure_line = None
        self._ctx = generator_displays.GeneratorContext(None, None, None)
        # Gutter-marker glyph-width callback set per ``generate()`` call; None
        # falls back to the marker's em size as its width.
        self._measure_marker = None
        # Block no-collapse-width callback set per ``generate()`` call; None
        # falls back to ``_line_item_width`` (see _block_width).
        self._measure_block = None
        # _block_width's memo and the theme and document it was measured under.
        # It survives generate() (see there); ``_MISSING`` makes the first call build it.
        self._block_w_cache: dict[tuple[str, float], float] = {}
        self._block_w_theme = self._block_w_root = _MISSING
        # The document's shallowest heading level, set per ``generate()`` call;
        # see _packs_unique.
        self._top_heading_level: int | None = None
        # Per-generation counter for LayoutNode.flow_run ids.
        self._flow_seq = 0
        # Per-generate memo of baked marker props, keyed by id(node).
        self._marker_props_cache: dict[int, dict | None] = {}
        # `:::` cells that stand as one at this width (_column_stack), held for
        # the generate() so the id()-keyed memos above never see a freed id.
        self._column_stacks: dict[tuple, MarkdownGroupNode] = {}
        self._image_floors: dict[str, float] = {}
        self._stack_ids: set[int] = set()
        # Per-generate: each large kind's likely-tallest members, the sample
        # _kind_aspect_cap checks before sweeping the whole kind.
        self._kind_sample: dict[int, list[MarkdownGroupNode]] = {}
        # Per-generate memo for _measured_min_width, keyed by id(node) — the
        # bento search and grid math re-check the same subtrees many times.
        self._min_w_cache: dict[int, float] = {}
        # Bento (mosaic) mode: None follows the theme's ``Layout:`` key; True/False
        # force it on/off (CLI --bento / interactive toggle).
        self.bento_override: bool | None = None
        # Under ``Layout: Auto``: the session's choice for this width (layout_auto).
        self.bento_auto = False
        # Section stacking: None follows the theme's ``Stack sections`` key;
        # True/False force it on/off (interactive toggle).
        self.pack_unique_override: bool | None = None
        # Per-generate resolution of the above; see _packs_unique.
        self._pack_unique = True
        # Per-generate bento state: active flag and the single heading level the
        # mosaic tiles (theme `Bento > Heading level`, else auto).
        self._bento = False
        # Per-generate: does any THEME level ask for an icon gutter
        # (``Emoji aside``)? Baked in generate(); see _theme_icon_aside.
        self._theme_asides = False
        self._bento_level: int | None = None

    @property
    def bento_requested(self) -> bool:
        """Whether bento was ASKED for: the override when one is set, else the
        theme's ``Layout:`` key — under ``Auto``, the session's choice for the width.

        The request, deliberately, and not ``self._bento``: _setup_bento drops
        that back to False when no heading level qualifies, so a toggle reading
        the outcome would report off after being switched on and look stuck.
        """
        if self.bento_override is not None:
            return self.bento_override
        layout = getattr(self._theme.root, "layout", "default") if self._theme else ""
        return layout == "bento" or (layout == "auto" and self.bento_auto)

    @property
    def pack_unique_requested(self) -> bool:
        """Whether section stacking was asked for: the override when one is set,
        else the theme's ``Stack sections`` key (on by default)."""
        if self.pack_unique_override is not None:
            return self.pack_unique_override
        theme = self._theme
        return theme is None or bool(getattr(theme.root, "pack_unique", True))

    def generate(
        self,
        ast_root: MarkdownGroupNode,
        available_width: float,
        theme=None,
        measure=None,
        measure_width=None,
        measure_line=None,
        measure_marker=None,
        measure_block=None,
    ) -> LayoutNode:
        """Generate a layout for *ast_root* at *available_width*.

        *ast_root* is treated as a transparent container.
        Returns LayoutNode(type="layout", ratios=[available_width, 0.0], ...).

        *theme* (optional) lets the fit/column math budget each unit's own wrap
        padding and inter-column gaps; ``None`` keeps the theme-free approximation.

        *measure* (optional) is a ``Callable[[LayoutNode, float], float]`` giving
        the rendered height of a built layout subtree at an outer cell width
        (wrap padding included). Only the bento mode uses it, to score candidate
        mosaics; ``None`` falls back to ``_estimate_cell_height``.

        *measure_width* (optional) is a ``Callable[[MarkdownGroupNode],
        float | None]`` giving the uncapped single-line width of a pill-type
        leaf (link / inline_code) and ``None`` for anything else. Fit decisions
        floor at the widest pill so a cell is never narrower than its longest
        button; ``None`` keeps the category-only minimums.

        *measure_marker* (optional) is a ``Callable[[dict], float]`` giving the
        drawn width of a gutter marker's glyphs from its baked props. A marked
        item's content is laid out at ``width - gutter``, so the gutter must be
        the real one; ``None`` falls back to the marker's em size (``size``).
        """
        self._theme = theme
        self._measure = measure
        self._measure_width = measure_width
        self._measure_line = measure_line
        self._measure_block = measure_block
        # Unlike every other memo here, _block_width's SURVIVES generate(): a window
        # resize re-generates at a new width and must not pay to measure every
        # candidate again. Its key holds the width offered, so a layout still
        # depends only on the document, the theme and the width. Thrown away when
        # the THEME or the DOCUMENT object changes: a live theme reload hands in a
        # new theme, and spacing and padding are half the measurement; a reload
        # hands in a new tree, where a node_id — a position — can name another
        # block. Compared by identity and held, as
        # session.effective_width holds its root: a tree is replaced, never edited.
        # `_MISSING`, not None: a measurer-less caller generates with theme=None,
        # and `None is not None` would read as "unchanged" and never build these.
        if self._block_w_theme is not theme or self._block_w_root is not ast_root:
            self._block_w_cache = {}
            self._block_w_theme, self._block_w_root = theme, ast_root
        # The shallowest heading level the document uses — its chapters. A TITLED
        # section there keeps the whole line (see _packs_unique).
        self._top_heading_level = ast_root.top_heading_level
        self._ctx = generator_displays.GeneratorContext(
            theme, measure_line, measure_width
        )
        self._measure_marker = measure_marker
        self._min_w_cache = {}
        # {node_id: "key"|"value"} for every node the theme's `Key` / `Value`
        # text style covers — built ONCE per generate and read by both the width
        # measurers and _make_leaf, so the two agree (ADR-400). Empty unless the
        # theme authored those blocks, which is what keeps a theme that does not
        # use them measuring and painting exactly as before.
        self._kv_roles = kv_role_map(ast_root, theme)
        # Per-generate memo of a node's baked marker props (None = no marker),
        # so the gutter is measured once per marked item instead of at every
        # width-budget lookup. See _marker_props / _marker_width.
        self._marker_props_cache = {}
        self._column_stacks, self._stack_ids = {}, set()
        # Per-generate memo of measured cell height, keyed by (id(node), width
        # bucket — see CELL_HEIGHT_BUCKET), so _aspect_cap measures each (member,
        # candidate-width) at most once instead
        # of re-rendering per K-candidate (which recurses combinatorially).
        self._cell_h_cache = {}
        # Per-kind grid maps (built below) so every repeated run of a kind — and its
        # orphans — share ONE column count: widest member min-width, largest run size,
        # all members (for a per-kind aspect cap), and every run's length (for the
        # per-kind fill vote). See _kind_cols.
        self._kind_members = {}
        self._kind_sample = {}
        self._kind_min_width = {}
        self._kind_max_run = {}
        self._kind_occurrences = {}
        self._kind_run_lens = {}
        self._marker_suppressed = False
        self._spacer_scope = (0, None, False)
        self._spacers_built = False
        # Per-generation counter for LayoutNode.flow_run ids, so ids can't leak
        # between generations (a stale id would relate unrelated siblings).
        self._flow_seq = 0
        self._pinned = set()
        self._pinned_render = {}
        self._pinned_card = {}
        self._fit_polls = []
        self._collect_url_props(ast_root)

        # Each image's ``min_width`` floor (capped by its ``max_width``), which
        # the measurer then reports, so every fit test — the kind maps included —
        # counts it. A fit test has no space to read a ``_wide`` twin against, so
        # it counts the base value; the renderer honours the twin in a wide space.
        self._image_floors = {
            node_id: floor
            for node_id, props in self._url_props.items()
            if (
                floor := image_floor(
                    render_properties_from(props, False).to_render_dict()
                )
            )
        }
        if self._image_floors and self._measure_width is not None:
            self._measure_width = with_image_floors(
                self._measure_width, self._image_floors
            )
        self._build_kind_maps(ast_root)
        # Does ANY level ask for an icon gutter? Read once here so the run-poll
        # gate can open for a theme-only document (no params) without asking the
        # theme per candidate run.
        self._theme_asides = theme is not None and any(
            getattr(st, "emoji_aside", None)
            for st in (
                *theme.sections.values(),
                *theme.fixed_sections.values(),
                theme.elements,
            )
        )
        self._setup_bento(ast_root, theme)
        self._pack_unique = self.pack_unique_requested
        if not ast_root.children:
            return LayoutNode(type="layout", ratios=[available_width, 0.0], children=[])
        root_layout = self._decide_group(ast_root, available_width, None)
        # Heading sections are marked directly from the grouper's heading_group flag
        # (in _decide_group / _make_leaf). This only levels generator-made grid-row
        # containers of same-level sections, so the renderer can space them apart.
        _fill_container_levels(root_layout)
        # A spacer is never a cell of a row (ADR-203): fold each into its cell.
        if self._spacers_built:
            generator_spacers.fold_row_spacers(root_layout)
        return LayoutNode(
            type="layout",
            ratios=[available_width, 0.0],
            children=[root_layout],
        )

    # ------------------------------------------------------------------
    # Bento (Mondrian mosaic) mode
    # ------------------------------------------------------------------

    def _setup_bento(self, ast_root: MarkdownGroupNode, theme) -> None:
        """Resolve per-generate bento state: active flag + the target level.

        Bento tiles ONE heading level. Its sections are the cells and whoever
        holds them — the root included — is the container; every other child of
        that container (its own heading, a lead-in paragraph) stays full width.
        The theme may name the level (``## Content arrangement`` → ``### Bento``
        → ``Heading level``); otherwise ``_auto_bento_level`` picks the
        shallowest level with a long enough run. A named level is absolute: if
        nothing qualifies at it the document just stacks, rather than silently
        tiling some other level. No level at all → bento off.
        """
        self._bento = self.bento_requested
        self._bento_level = None
        if not self._bento:
            return
        manual = (
            getattr(getattr(theme, "bento", None), "heading_level", None)
            if theme is not None
            else None
        )
        self._bento_level = (
            manual if manual is not None else _auto_bento_level(ast_root)
        )
        if self._bento_level is None:
            self._bento = False

    def _bento_runs(self, node: MarkdownGroupNode) -> list[tuple[int, int]]:
        """Maximal contiguous ``[start, end)`` runs of target-level sections
        among *node*'s children, keeping only runs worth a mosaic.

        Contiguity mirrors the repeated-run grid: a run is tiled in place, and
        anything between two runs keeps its position in the stack.
        """
        if self._bento_level is None:
            return []
        runs: list[tuple[int, int]] = []
        start: int | None = None
        for i, child in enumerate(node.children):
            if _section_level(child) == self._bento_level:
                if start is None:
                    start = i
            elif start is not None:
                if i - start >= BENTO_MIN_CELLS:
                    runs.append((start, i))
                start = None
        if start is not None and len(node.children) - start >= BENTO_MIN_CELLS:
            runs.append((start, len(node.children)))
        return runs

    def _build_bento_runs(
        self,
        node: MarkdownGroupNode,
        runs: list[tuple[int, int]],
        available_width: float,
        in_glued: bool = False,
        owner_level: int = 0,
    ) -> LayoutNode | None:
        """Tile each run of *node*'s children in place; lay out the rest as if
        bento were off.

        Returns the mosaic itself when one run covers every child (the common
        shape — a section whose children are all target-level subsections), a
        col of the mosaics among the default layout of everything else when they
        do not — so two same-kind cards left after a break still grid, as they
        would without bento — and ``None`` when no run could be packed at this
        width, so the caller falls back to the default rules.
        """
        packed: dict[int, LayoutNode] = {}
        for start, end in runs:
            mosaic = self._build_bento(
                node,
                node.children[start:end],
                available_width,
                in_glued,
                owner_level,
            )
            if mosaic is not None:
                packed[start] = mosaic
        if not packed:
            return None
        run_end = {start: end for start, end in runs}
        if len(packed) == 1:
            start = next(iter(packed))
            if start == 0 and run_end[start] == len(node.children):
                return packed[start]
        return self._build_grouped(
            node,
            available_width,
            in_glued,
            owner_level,
            packed={start: (built, run_end[start]) for start, built in packed.items()},
        )

    def _build_bento(
        self,
        node: MarkdownGroupNode,
        cells: list[MarkdownGroupNode],
        available_width: float,
        in_glued: bool = False,
        owner_level: int = 0,
    ) -> LayoutNode | None:
        """Pack *cells* — a run of *node*'s children — into an order-preserving
        Mondrian mosaic.

        The width is divided into ``D`` grid columns (3–5 wide / 1–3 narrow) and
        the *ordered* cell list is recursively sliced into contiguous row/column
        bands (guillotine cuts), so in-order traversal equals document order.
        Candidates are scored by estimated whitespace area plus an aspect
        penalty pushing cells toward square / 2:1 / 1:2 shapes; per memo state a
        small Pareto beam (height × cost) is kept. Cell heights come from
        ``self._measure`` (renderer-supplied height-for-width) or the crude
        ``_estimate_cell_height`` fallback — either way the renderer re-measures
        at render time, and the ``bento`` flags keep edges aligned.

        Emits plain nested ``row``/``col`` nodes: bento rows carry integer
        grid-span weights as ``ratios`` (honored exactly by the renderer, no
        content collapse); bento cols are bands whose children stretch to the
        height allotted by the enclosing row. Returns ``None`` when infeasible
        at this width (→ caller falls back to the default rules).
        """
        theme = self._theme
        n = len(cells)
        w_total = available_width

        d = round(w_total / BENTO_UNIT_TARGET)
        d = min(5, max(3, d)) if w_total >= BENTO_WIDE_WIDTH else min(3, max(1, d))
        if d <= 1:
            return None
        g_x = max(
            (_cell_gap(c, theme, "row", owner_level, self._owner_key) for c in cells),
            default=0.0,
        )
        g_y = max(
            (_cell_gap(c, theme, "col", owner_level, self._owner_key) for c in cells),
            default=0.0,
        )
        unit = (w_total - (d - 1) * g_x) / d
        if unit <= 0:
            return None

        def span_w(s: int) -> float:
            return s * unit + (s - 1) * g_x

        # The d span widths, looked up in the inner loops: the same expression,
        # so the same floats, and the search's ties break exactly as before.
        sw = [0.0] + [span_w(k) for k in range(1, d + 1)]

        s_min = [
            next(
                (k for k in range(1, d + 1) if span_w(k) >= self._unit_min(c, theme)),
                d,
            )
            for c in cells
        ]

        # -- cell subtree + height, memoized per (index, span) --------------
        cell_cache: dict[tuple[int, int], tuple[LayoutNode, float]] = {}

        def cell_at(i: int, s: int) -> tuple[LayoutNode, float]:
            key = (i, s)
            if key not in cell_cache:
                sub = self._render_child(
                    cells[i], span_w(s), node, in_glued, owner_level
                )
                h = (
                    self._measure(sub, span_w(s))
                    if self._measure is not None
                    else _estimate_cell_height(cells[i], span_w(s))
                )
                cell_cache[key] = (sub, max(h, 1.0))
            return cell_cache[key]

        def leaf_cand(i: int, s: int) -> tuple[tuple[LayoutNode, ...], float, float]:
            """Cell *i* at span *s* as a (parts, height, cost) candidate; the
            cost is its aspect penalty toward square / 2:1 / 1:2 shapes."""
            sub, h = cell_at(i, s)
            wd = span_w(s)
            r = wd / h
            dev = min(abs(math.log(r)), abs(math.log(r / 2.0)), abs(math.log(2.0 * r)))
            dev = round(dev * BENTO_DEV_STEPS) / BENTO_DEV_STEPS
            pen = BENTO_ASPECT_WEIGHT * dev * wd * h
            if r > 4.0 or r < 0.25:  # sliver guard
                pen *= 2.0
            return ((sub,), h, pen)

        def pareto(cands: list, height_of, cost_of) -> list:
            """Keep the (height, cost) Pareto frontier, at most BENTO_BEAM."""
            cands = sorted(cands, key=lambda c: (cost_of(c), height_of(c)))
            kept: list = []
            best_h = float("inf")
            for c in cands:
                h = height_of(c)
                if h < best_h:
                    kept.append(c)
                    best_h = h
                    if len(kept) >= BENTO_BEAM:
                        break
            return kept

        # -- search: order-preserving guillotine over cells [i, j) ----------
        # pack_v candidates: (parts tuple, height, cost) — a vertical stack.
        # bands candidates: (bands tuple of (node, span, height), max_h, fill, cost)
        # where fill = Σ band_h · band_w, so whitespace = row_h·Σband_w − fill.
        memo_v: dict = {}
        memo_b: dict = {}
        memo_h: dict = {}

        def pack_v(i: int, j: int, s: int, depth: int) -> list:
            key = (i, j, s, depth)
            if key in memo_v:
                return memo_v[key]
            out: list = []
            if s >= s_min[i]:
                head_parts, head_h, head_c = leaf_cand(i, s)
                if i + 1 == j:
                    out.append((head_parts, head_h, head_c))
                else:
                    for parts, h, c in pack_v(i + 1, j, s, depth):
                        out.append((head_parts + parts, head_h + g_y + h, head_c + c))
            if depth < BENTO_MAX_DEPTH and s >= 2:
                for k in range(i + 2, j + 1):
                    for row_node, row_h, row_c in pack_h(i, k, s, depth + 1):
                        if k == j:
                            out.append(((row_node,), row_h, row_c))
                        else:
                            for parts, h, c in pack_v(k, j, s, depth):
                                out.append(
                                    (
                                        (row_node,) + parts,
                                        row_h + g_y + h,
                                        row_c + c,
                                    )
                                )
            out = pareto(out, lambda c: c[1], lambda c: c[2])
            memo_v[key] = out
            return out

        # Memoised like pack_v, whose result it wraps: sharing a band's nodes
        # between candidates is safe, as a mosaic holds each band once.
        memo_band: dict = {}

        def band(i: int, j: int, t: int, depth: int) -> list:
            """Column band of cells [i, j) at span *t* → (node, height, cost)."""
            key = (i, j, t, depth)
            if key in memo_band:
                return memo_band[key]
            if j - i == 1:
                out = []
                if t >= s_min[i]:
                    parts, h, c = leaf_cand(i, t)
                    out = [(parts[0], h, c)]
            else:
                out = [
                    (parts[0] if len(parts) == 1 else _bento_col(list(parts)), h, c)
                    for parts, h, c in pack_v(i, j, t, depth)
                ]
            memo_band[key] = out
            return out

        def bands(i: int, j: int, s: int, depth: int) -> list:
            key = (i, j, s, depth)
            if key in memo_b:
                return memo_b[key]
            out: list = []
            for bn, bh, bc in band(i, j, s, depth):
                out.append((((bn, s, bh),), bh, bh * sw[s], bc))
            for m in range(i + 1, j):
                head_min = max(s_min[i:m])
                rest_min = max(s_min[m:j])
                for t in range(head_min, s - rest_min + 1):
                    heads = band(i, m, t, depth)
                    if not heads:
                        continue
                    tails = bands(m, j, s - t, depth)
                    for hn, hh, hc in heads:
                        for tb, tmax, tfill, tc in tails:
                            out.append(
                                (
                                    ((hn, t, hh),) + tb,
                                    max(hh, tmax),
                                    hh * sw[t] + tfill,
                                    hc + tc,
                                )
                            )
            # Dominance on (max_h, cost − fill) is exact for any completion:
            # the finished row cost adds row_h·Σband_w − fill with row_h the
            # max over all bands, both monotone in these two keys.
            out = pareto(out, lambda c: c[1], lambda c: c[3] - c[2])
            memo_b[key] = out
            return out

        def pack_h(i: int, j: int, s: int, depth: int) -> list:
            key = (i, j, s, depth)
            if key in memo_h:
                return memo_h[key]
            out: list = []
            for m in range(i + 1, j):
                head_min = max(s_min[i:m])
                rest_min = max(s_min[m:j])
                for t in range(head_min, s - rest_min + 1):
                    for hn, hh, hc in band(i, m, t, depth):
                        for tb, tmax, tfill, tc in bands(m, j, s - t, depth):
                            all_bands = ((hn, t, hh),) + tb
                            row_h = max(hh, tmax)
                            fill = hh * sw[t] + tfill
                            waste = row_h * sum(sw[sp] for _, sp, _ in all_bands) - fill
                            out.append((all_bands, row_h, hc + tc + waste))
            # A row node only for the few candidates the beam keeps, not for the
            # thousands it scores: pareto is a stable sort on the same values.
            kept: list = []
            for all_bands, row_h, cost in pareto(out, lambda c: c[1], lambda c: c[2]):
                row = LayoutNode(
                    type="row",
                    ratios=[float(sp) for _, sp, _ in all_bands],
                    children=[bn for bn, _, _ in all_bands],
                )
                row.bento = True
                kept.append((row, row_h, cost))
            memo_h[key] = kept
            return kept

        best = None
        for parts, h, c in pack_v(0, n, d, 0):
            if best is None or (c, h) < (best[2], best[1]):
                best = (parts, h, c)
        if best is None:  # defensive: the full-width stack is always feasible
            return None
        parts = list(best[0])
        return parts[0] if len(parts) == 1 else _bento_col(parts)

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------

    def _decide_group(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        parent: MarkdownGroupNode | None,
        in_glued: bool = False,
        owner_level: int = 0,
    ) -> LayoutNode:
        """Classify *node* and delegate to the appropriate builder.

        A group reaches the icon aside (``_decide_group_icon_aside``) only when
        the theme asks for one; otherwise — and whenever the group cannot take
        one — the rules decide.
        """
        if _is_leaf(node):
            return self._make_leaf(node, parent, available_width)

        if node.repeated_children is None:
            raise RuntimeError(
                "Call ASTPatternAnalyzer.fingerprints() before LayoutGenerator.generate()"
            )

        glued = in_glued or node.glued_content_group

        # The level that owns this node's children (spacing/gap resolution):
        # a heading section owns its content; otherwise the inherited owner.
        # Mirrors the renderer's _child_owner_level.
        own = (
            node.heading_level
            if node.heading_group and node.heading_level is not None
            else owner_level
        )

        # This node's children render *inside* its own wrap (section/card
        # padding), so every downstream fit decision must see the padding-
        # reduced inner width — mirroring the renderer's _emit_wrap_boxes
        # inset. Without this, tight-fit units (e.g. grid columns floored at a
        # pill width) are decided at the outer width and overflow once the
        # wrap padding is carved out at render time.
        inner_width = max(0.0, available_width - _unit_padding_x(node, self._theme))

        # Only the OUTERMOST marked item owns a gutter marker. The boundary-emoji
        # peel can nest a same-type item arbitrarily deep (e.g.
        # ``list_item → group → list_item``), so suppress markers on this node's
        # whole subtree while it is being built if this node itself takes one.
        # ``_marker_suppressed`` reflects "an ancestor already owns a marker".
        prev_suppressed = self._marker_suppressed
        node_wraps = (not prev_suppressed) and (self._marker_props(node) is not None)
        self._marker_suppressed = prev_suppressed or node_wraps
        # Where a spacer among this node's children takes its size from:
        # the level that owns them, and whether they sit in a photo card.
        prev_spacer_scope = self._spacer_scope
        self._spacer_scope = (
            own,
            node.section_style_key
            if node.heading_group and node.heading_level is not None
            else prev_spacer_scope[1],
            prev_spacer_scope[2]
            or node.type == NodeType.IMAGE_CARD
            or node.card_bg_url is not None,
        )

        # A marked item renders as ``row[ marker | content ]`` — a fixed aside,
        # split by the same primitive the icon aside uses — so its content only
        # ever gets what is left of the gutter and its Space. Decide the
        # children against THAT width: arranging them at the full width
        # (side-by-side pairs, grid columns) and only then handing them the
        # narrower cell is what made the renderer fall back to ratio
        # distribution and clip glyphs. The row itself spans ``inner_width``.
        child_width = (
            self._marker_split(node, inner_width)[2] if node_wraps else inner_width
        )

        # Transparent passthrough: a group whose only child is itself a group
        # (incl. the root over a glued wrapper) adds no layout level — render the
        # child in place, carrying the glued flag down. A table container never
        # passes through (a single-row table's row is a group, but the table
        # identity lives on the container).
        # A spacer is silenced here as it is in the fingerprint (ADR-203): it
        # never keeps a group from passing through, and rides into the child.
        solid = (
            [c for c in node.children if c.type != NodeType.SPACER]
            if node.child_type_counts.get(NodeType.SPACER)
            else node.children
        )
        if (
            len(solid) == 1
            and _is_group(solid[0])
            and not node.table_group
            # ...unless the two are sections of different levels. The transfer
            # below declines to overwrite a child that already has a level, so
            # passing through would drop the outer section outright — the same
            # loss ``_collapse_groups`` makes in the grouper, one stage later.
            # ADR-100: the grouper already decided this; consume the flag.
            and same_section_kind(node, solid[0])
        ):
            result = self._decide_group(solid[0], child_width, node, glued, own)
            if len(node.children) > 1:
                result = self._ride_spacers(node, solid[0], result, child_width)
            # Carry a heading-section flag onto the collapsed child so the section
            # marking survives the passthrough (a heading node can also be glued —
            # both are independent).
            if (
                node.heading_group
                and node.heading_level is not None
                and result.section_level is None
            ):
                result.section_level = node.heading_level
                result.section_style_key = node.fixed_style_key
                result.heading_id = node.heading_id
                # The slot travels with the section: whichever node ends up
                # painting this background must use the same one, or a collapsed
                # card would fall back to a positional count and break the cycle.
                result.rotation_index = (
                    node.fixed_rotation_index
                    if self._theme is not None
                    and node.fixed_style_key
                    and node.fixed_style_key in self._theme.fixed_sections
                    else node.rotation_index
                )
                result.rotation_chain = node.rotation_chain
                result.rotation_path = node.rotation_path
            # Same for a background photo: the grouper only put it here because
            # the collapse was a FULL overlap, so the child covers the same rect
            # and can paint it — without this the photo is dropped outright
            # whenever a card's body collapses to a single group.
            if node.card_bg_url and result.card_bg_url is None:
                result.card_bg_url = self._pinned_card.get(id(node), node.card_bg_url)
                result.is_card = True
                result.card_kind = "image_card"
            # A link card's url, for the same reason: the child covers the card's
            # rect, so it is where a click lands. One rect holds one card url: the
            # one the author wrapped the content in wins over any the child carried.
            if node.link_url:
                result.link_url = node.link_url
                result.link_node_id = node.node_id
            # A K-V role riding a transparent container (a VALUE node collapsing
            # onto its single leaf) survives the passthrough as a render
            # property on the collapsed child.
            kv_role = self._kv_roles.get(node.node_id) if node.node_id else None
            if kv_role is not None:
                props = dict(result.render_properties or {})
                props["kv_role"] = kv_role
                result.render_properties = props
            # A marked item (e.g. a list item whose sole child is a group) still
            # needs its gutter marker even though this level is transparent.
            self._marker_suppressed = prev_suppressed
            self._spacer_scope = prev_spacer_scope
            return self._wrap_marker(node, result, inner_width)

        # Icon-aside placement is NODE-KIND AGNOSTIC: any group with a lone-emoji
        # icon at an edge can take one. What refuses: a chart / datapoint-display
        # group, which is DRAWN (bar, ring, date chip, chart) rather than laid
        # out, so arranging it is meaningless. Feasibility is
        # ``_decide_group_icon_aside``'s: the icon must be the first or last
        # child, and ``_aside_fits`` has to pass.
        # An authored `:::` row, decided before the theme is consulted. The
        # author wrote the arrangement; the theme gets no vote on it.
        #
        # It assigns `result` rather than returning, because everything after
        # the branch — the section level, the card flag, the heading id, the
        # rotation slot, `_attach_render` — is shared tail that a row needs just
        # as much. Returning early here is what made a `## Heading` + `:::` row
        # lose its section styling entirely: the node is BOTH a heading group
        # and a column row, and only the tail knows about the first half.
        if node.column_row_group:
            result = self._build_column_row(node, child_width, glued, own)
        elif (
            self._theme_asides
            and not generator_displays._drawn_chart(self._ctx, node)
            and not generator_displays._dp_display_enabled(self._ctx, node)
            # …and a bento container, for the same reason a heading section
            # never has its own arrangement decided: the mosaic IS the
            # structural layout of that node's children. Without this an icon
            # aside returns from _decide_group_icon_aside and the run never
            # reaches the bento branch in _decide_group_rules.
            and not (self._bento and self._bento_runs(node))
        ):
            result = self._decide_group_icon_aside(
                node, child_width, parent, glued, own
            )
        else:
            result = self._decide_group_rules(node, child_width, parent, glued, own)
        # Children are built; restore the ancestor suppression state so this
        # node's own marker decision (below) sees whether an ANCESTOR owns one.
        self._marker_suppressed = prev_suppressed
        self._spacer_scope = prev_spacer_scope
        # Decorate the layout node representing this group with its render
        # hints (run pin, URL params, an authored spring). Independent of the arrangement above — purely additive, so the
        # structural layout is unchanged.
        self._attach_render(result, node, child_width)
        # The markdown node's color-rotation slot — the only route from the
        # grouper's annotation to a container's background paint.
        if result.rotation_index is None:
            use_fixed = bool(
                self._theme is not None
                and node.section_style_key
                and node.section_style_key in self._theme.fixed_sections
            )
            result.rotation_index = (
                node.fixed_rotation_index if use_fixed else node.rotation_index
            )
            result.rotation_chain = node.rotation_chain
            result.rotation_path = node.rotation_path
        result.section_style_key = node.section_style_key
        if node.heading_group:
            result.heading_id = node.heading_id
        # Mark cards (glued content groups) so the renderer can wrap them with the
        # global element background+padding.
        if node.glued_content_group:
            result.is_card = True
        # An image card is a card whatever its glue: the grouper already decided
        # it is one, and its background URL has to reach the renderer somehow —
        # a container has no content_id, so carrying it here is the only route.
        # Carried regardless of type: a full-overlap collapse can hand the photo
        # to a heading group or a list item, which then paints it.
        result.card_bg_url = self._pinned_card.get(id(node), node.card_bg_url)
        # A link card's url reaches the click the same way: a container has no
        # content_id. Set only when this node has one, so an outer url a
        # passthrough already carried down is never cleared.
        if node.link_url:
            result.link_url = node.link_url
            result.link_node_id = node.node_id
        # A card showing a photo is an image card whichever node ended up
        # holding it, so it takes the ### Image Cards style rather than the
        # generic element one — that is what makes the two nesting orders
        # (link card in image card, and the reverse) render identically.
        if result.card_bg_url is not None:
            result.is_card = True
            result.card_kind = "image_card"
        # Mark heading sections directly from the grouper flag (independent of glued —
        # a heading with no internal separation is both a section AND a card, which the
        # renderer composes as section+card layers).
        if node.heading_group and node.heading_level is not None:
            result.section_level = node.heading_level
            result.section_style_key = node.fixed_style_key
            result.heading_id = node.heading_id
        # An authored `...` column: it claims the height it is offered so the
        # spring has surplus to open. Only a col can — a row's spare space is on
        # the other axis, and its cells already carry their own valign.
        if node.valign_group and result.type == "col":
            result.col_spring = True
        # A same-line chunk (peel / segment / datapoint split) is ONE line
        # element: carry the grouper's line_split_group onto the layout node so
        # the renderer's _line_side gives it the element gap (Gestalt proximity),
        # even when the node was replaced by a bar/display wrapper that the flow
        # builders (_flow_line_group / _flow_rows) don't produce. Spacing-only —
        # line_split is read solely by _line_side. Skip card-wrapping results:
        # a ring / date-chip builds row[col(is_card)]; _line_side ignores the
        # inner card but would still fire on the non-card wrapper row, tightening
        # the card inconsistently with unsplit siblings — cards space as cards.
        if node.line_split_group and not any(
            getattr(c, "is_card", False) for c in result.children
        ):
            result.line_split = True
        # …and the line's authored VERTICAL alignment, as ``line_align`` — the
        # row's own mode, which is what `_row_valign_offsets` reads. Set here,
        # on the one site every result for a node passes through, rather than in
        # `_flow_line_group`: a line also becomes a row by the pill path and the
        # repeated-run path, and those build their rows elsewhere.
        #
        # `bake_render_cascade` fills this slot from the theme level only when
        # it is EMPTY ("own beats inherited"), so writing it here is what makes
        # the token outrank `Vertical align` on the level — the precedence a
        # per-line override has to have to be worth writing.
        if node.line_valign:
            result.render_properties = {
                **(result.render_properties or {}),
                "line_align": node.line_valign,
            }
        # Wrap a marked item (blockquote / multi-line list item) in its gutter
        # marker row (no-op for other nodes and when the theme block is off),
        # then its edge spacers around that, as a leaf's are (`_make_leaf`).
        # Both live in this node's own wrap padding and span ``inner_width``.
        own_line = bool(node.line_split_group or node.column_row_group)
        result = self._wrap_marker(node, result, inner_width)
        return self._edge_spacers(node, result, inner_width, own_line)

    def _decide_group_rules(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        parent: MarkdownGroupNode | None,
        in_glued: bool = False,
        owner_level: int = 0,
    ) -> LayoutNode:
        """Rule-based layout: every group the theme's icon aside does not take."""
        # Table containers (grouper table_group flag): deterministic column-
        # aligned layout — never bento'd, flowed, or gridded.
        if node.table_group:
            return self._build_table(node, available_width, in_glued, owner_level)
        # Chart containers (grouper chart_group / line_group flag): one drawn
        # chart leaf, measured/oriented entirely by the renderer.
        if generator_displays._drawn_chart(self._ctx, node):
            return generator_displays._build_chart(self._ctx, node)
        # Drawn datapoint containers (grouper datapoint_display flag): bar/
        # ring replacements. Flagged LEAVES keep the normal leaf path — they
        # get their render properties in _make_leaf. Emphasis containers also
        # keep the normal path (only their children's text styles change).
        if node.datapoint_display in (
            "unit_ratio",
            "kv_percent_bar",
            "line_chart",
        ) and generator_displays._dp_display_enabled(self._ctx, node):
            return self._build_datapoint_display(
                node, available_width, in_glued, owner_level
            )
        # Date chips are grouper-built group(key, day) nodes → a themed card
        # over two text leaves. Repeated adjacent chips reach here via
        # _build_grouped and grid.
        if node.datapoint_display == "date_chip":
            if generator_displays._dp_display_enabled(self._ctx, node):
                return self._build_date_chip(
                    node, available_width, in_glued, owner_level
                )
            # Chips off. The grouper split `Aug 12` into key + day regardless —
            # it has no theme to gate on — and _derive_line_split_groups
            # withholds line_split_group from that group precisely BECAUSE a
            # chip stacks its key over its day, which is what put the halves on
            # two rows. Collapse to the single line the author wrote, baked from
            # the payload the way _build_ring bakes its value/unit.
            text = (node.datapoint_payload or {}).get("text")
            if text:
                return LayoutNode(
                    type="-",
                    ratios=[],
                    children=[],
                    content_id=None,
                    render_properties={
                        "date_text": text,
                        "text_style_chain": list(node.text_style_chain),
                    },
                )
        # Bento mode: each contiguous run of target-level sections among this
        # node's children (see _bento_runs) tiles as an order-preserving
        # Mondrian mosaic, and everything else — this node's own heading, a
        # lead-in paragraph — keeps its place in the stack at full width.
        # Infeasible (too few divisions at this width) → None → the rules below.
        if self._bento and (runs := self._bento_runs(node)):
            packed = self._build_bento_runs(
                node, runs, available_width, in_glued, owner_level
            )
            if packed is not None:
                return packed

        # Line-split groups: the children are the pieces of ONE source line —
        # flow them back into rows at full single-line widths. Checked before
        # full-width and repeated runs (comma-segment groups have repeated
        # runs but must flow, not grid/stack). An IMAGE is a line piece like
        # any other: cut out of prose because it cannot be drawn as text, it
        # leaves [text, image, text] pieces that flow as one line's row.
        if node.line_split_group:
            return self._flow_line_group(node, available_width, in_glued, owner_level)

        # Priority 3: full-width → col
        if self._is_full_width(node, parent):
            return self._build_col(node, available_width, in_glued, owner_level)

        # Priority 4: grid each contiguous run of repeated siblings, in place.
        # repeated_children holds the children that have an adjacent
        # same-fingerprint twin (built in markdown_grouper); _build_grouped
        # re-segments them into maximal contiguous runs and grids each run in
        # document order, leaving non-repeated siblings full-width. Also routed
        # here when a child is an ``orphan_grid`` member (a lone element of a kind
        # its siblings grid) so _build_grouped can card-width it.
        # ``Stack sections`` routes here too, and it has to: a node whose children
        # are ALL of different kinds has no repeated_children at all, and that is
        # exactly the document the packing is for. _build_grouped handles both
        # halves — repeated runs grid, unique runs pack — in document order.
        if (
            node.repeated_children
            or any(getattr(c, "orphan_grid", False) for c in node.children)
            or self._packs_any_unique(node)
        ):
            return self._build_grouped(node, available_width, in_glued, owner_level)

        # Default: full-width col
        return self._build_col(node, available_width, in_glued, owner_level)

    # ------------------------------------------------------------------
    # The theme's icon aside
    # ------------------------------------------------------------------

    def _decide_group_icon_aside(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        parent: MarkdownGroupNode | None,
        in_glued: bool = True,
        owner_level: int = 0,
    ) -> LayoutNode:
        """Put *node*'s lone-emoji icon in a gutter when its level asks for one.

        Only when it fits at min widths. Everything else — a level that is
        silent, a group with no icon at an edge, an icon it cannot afford —
        hands the group to the RULES, which keep authority over stacking,
        gridding, flowing and tables, and recurse each child back through here,
        so sub-content still gets its own aside.

        ``owner_level`` reaches the rules too: it selects the section whose
        padding and spacing apply.
        """
        if self._wants_icon_aside(node, owner_level) and self._icon_aside_candidate(
            node
        ):
            children = node.children
            icon = (
                children[0]
                if children[0].type == "emoji" and children[0].emoji_kind == "alone"
                else children[-1]
            )
            if self._aside_fits(icon, children, available_width, owner_level):
                return self._build_icon_aside(
                    node, available_width, in_glued, owner_level
                )
        return self._decide_group_rules(
            node, available_width, parent, in_glued, owner_level
        )

    def _collect_url_props(self, ast_root: MarkdownGroupNode) -> None:
        """Read ``?md2ui.*`` params off every image leaf into yaml-shaped entries.

        Params are author input, read into the entry shape
        ``render_properties_from`` resolves, ``_wide`` twins included.
        They only ever say how an image is drawn: putting one beside text is a
        ``:::`` row the author writes.
        """
        self._url_props = {}
        self._url_warnings = []
        self._card_urls = False

        def walk(node: MarkdownGroupNode) -> None:
            if node.card_bg_url and url_layout_params(node.card_bg_url):
                self._card_urls = True
            if node.type == "image" and node.content:
                raw = image_params(node.content)
                if raw:
                    props, warnings = sanitize_url_props(raw)
                    if props:
                        self._url_props[node.node_id] = props
                    self._url_warnings.extend(
                        f"{node.node_id or '<root>'}: {w}" for w in warnings
                    )
            for child in node.children:
                walk(child)

        walk(ast_root)

    def url_diagnostics(self) -> list[str]:
        """Problems with this generate()'s URL params — never blocking: invalid
        names and values from ``sanitize_url_props``, and conflicting hints
        inside one repeated run. A param that changes nothing must say so rather
        than leave the author guessing."""
        return list(self._url_warnings)

    def _url_render(self, node: MarkdownGroupNode, width: float = 0.0):
        """*node*'s URL-authored render hints, or None (its own node only).

        A ``_wide`` twin applies where the space *node* is laid out in is wide
        (``WIDE_BREAKPOINT`` and up) — the space, never the window, so the same
        image takes its narrow value in a small card on a large screen.
        """
        entry = self._url_props.get(node.node_id)
        if not entry:
            return None

        return render_properties_from(entry, width >= WIDE_BREAKPOINT)

    def _wants_icon_aside(self, node: MarkdownGroupNode, owner_level: int) -> bool:
        """Does *node* take an icon gutter: its run's pin, else its level?

        The pin serves a repeated run's unified answer (_unify_run), so every
        member of the run is laid out alike.
        """
        return id(node) in self._pinned or self._theme_icon_aside(node, owner_level)

    def _theme_icon_aside(self, node: MarkdownGroupNode, owner_level: int) -> bool:
        """Does ``Emoji aside`` on the level that OWNS *node* ask for its icon?

        The level's key reaches everything it owns and **stops at the next
        heading boundary**: ``owner_level`` is already derived that way in
        ``_decide_group`` ("Mirrors the renderer's _child_owner_level") — a
        heading_group resets it to its own level, everything else inherits — so
        a nested ``### Heading 3`` section answers to ``sections[3]``, not to the
        H2 that contains it. Glued groups inside the level DO answer to it.

        Resolution ladder: ``sections[owner_level]`` for levels 1-6, then
        ``elements`` for content outside any heading section (level 0), then
        unset = no opinion. ``### Image Cards`` needs no place here: an image
        card is its own node kind.

        Feasibility is deliberately NOT checked: ``_decide_group_icon_aside``
        gates the aside on ``_aside_fits`` and falls back to the rules, so a
        level that asks for a gutter it cannot afford degrades instead of
        clipping.
        """
        if self._theme is None:
            return False
        st = (
            resolve_section_style(self._theme, owner_level, node.section_style_key)
            if owner_level
            else self._theme.elements
        )
        if st is None or not getattr(st, "emoji_aside", None):
            return False
        return self._icon_aside_candidate(node)

    @staticmethod
    def _icon_aside_candidate(node: MarkdownGroupNode) -> bool:
        """Does *node* hold a lone-emoji icon at an edge, with content beside it?

        The same shape ``_decide_group_icon_aside`` and ``_unit_min_for``
        require, in one place so the three cannot drift: >= 2 children, and the
        FIRST or LAST of them an ``alone`` emoji. Position picks the side later;
        a middle emoji is never aside-eligible.

        A ``line_split_group`` is excluded. An aside puts the icon beside the
        WHOLE GROUP, which presupposes a group of several lines — but a line
        group is the pieces of ONE source line, and ``_build_icon_aside`` stacks
        whatever is left into a col, so ``⭐ - text - 🚀`` would come back as the
        star beside a COLUMN of "text" over the rocket. That is the opposite of
        what the author wrote, and the line already flows its icon inline.
        """
        kids = node.children
        if len(kids) < 2 or node.line_split_group:
            return False
        return any(
            c.type == "emoji" and c.emoji_kind == "alone" for c in (kids[0], kids[-1])
        )

    # ------------------------------------------------------------------
    # Repeated-run consistency (majority poll)
    # ------------------------------------------------------------------

    def _unify_run(
        self,
        run: list[MarkdownGroupNode],
        owner_level: int = 0,
        width: float = 0.0,
    ) -> bool:
        """Unify a repeated run's icon aside and render hints, and pin them.

        Every member of a contiguous repeated run must be laid out alike —
        design consistency across visually identical cards. When the theme asks
        any member for an icon gutter, every member is pinned to take one
        (``_wants_icon_aside`` serves the pin; a member without an icon at an
        edge still falls back to the rules). Render hints are unified per
        relative child-index path (``poll_render``); members missing a path
        (the run_key ±1 tolerance) don't vote and get no pin there.

        Returns whether the run takes an icon aside. No-op when the document has
        neither URL params nor a themed ``Emoji aside``.
        """
        if len(run) < 2 or not (
            self._url_props or self._theme_asides or self._card_urls
        ):
            return False

        # Ahead of the no-aside bail below: a run can carry render hints with
        # no aside at all, and those still need unifying.
        self._unify_run_render(run, width)

        if not any(self._theme_icon_aside(m, owner_level) for m in run):
            return False
        self._pinned.update(id(m) for m in run)
        return True

    def _unify_run_render(self, run: list[MarkdownGroupNode], width: float) -> None:
        """Majority-vote per-node render hints across run members, per
        relative child-index path, and pin them for ``_attach_render``.

        Per member the hints come from its URL params. Annotating ONE member of a
        repeated run is enough: the annotated member's opinion wins the poll and
        is pinned on every member of the run, so annotating one card of six
        styles all six identically instead of breaking the run's visual
        consistency.
        """
        paths: dict[tuple, list] = {}

        def collect(n, path):
            paths.setdefault(path, []).append(n)
            for i, c in enumerate(n.children):
                collect(c, path + (i,))

        for m in run:
            collect(m, ())

        for members in paths.values():
            if len(members) < 2:
                continue  # path missing in siblings (±1 tolerance): no pin
            # An image card's picture is its background, not a child: it votes
            # too, so one card's ratio sets the run (ADR-301).
            cards = [n for n in members if n.card_bg_url]
            if votes := [p for n in cards if (p := url_layout_params(n.card_bg_url))]:
                won = max(votes, key=votes.count)
                for n in cards:
                    self._pinned_card[id(n)] = with_layout_params(n.card_bg_url, won)
            if not self._url_props:
                continue
            # Only the URL-annotated members vote, so one authored card is not
            # outvoted by its unannotated siblings.
            url_hints = {id(n): h for n in members if (h := self._url_render(n, width))}
            if len({run_shared(h) for h in url_hints.values()}) > 1:
                ids = [n.node_id for n in members if id(n) in url_hints]
                self._url_warnings.append(
                    f"{', '.join(ids)}: conflicting md2ui render hints across "
                    "one repeated run — the majority wins and applies to every "
                    "member"
                )
            votes = [h for n in members if (h := url_hints.get(id(n))) is not None]
            if not votes:
                continue
            unified = poll_render(votes)
            for n in members:
                self._pinned_render[id(n)] = unified

    def _unit_min_for(
        self,
        run: list[MarkdownGroupNode],
        icon_aside: bool,
        owner_level: int = 0,
    ) -> float | None:
        """True per-unit min width of a repeated run that takes an icon aside,
        or ``None`` when the stacked measurement already holds.

        An aside unit is wider than its stacked self (icon cell + content min +
        column gap), so the grid must know BEFORE choosing the column count —
        poll → measure → grid. Maxes across members so every column can hold
        its widest unit.
        """
        if not icon_aside:
            return None
        mins = []
        for m in run:
            # Same eligibility the aside gate applies, via the shared
            # predicate — including a TRAILING icon, or a right-gutter run
            # would be measured as if it stacked and come out too narrow.
            if not self._icon_aside_candidate(m):
                continue
            icon = (
                m.children[0]
                if m.children[0].type == "emoji" and m.children[0].emoji_kind == "alone"
                else m.children[-1]
            )
            mins.append(self._aside_min_width(icon, m.children, owner_level))
        return max(mins) if mins else None

    @staticmethod
    def _aside_split(
        aside_w: float, available_width: float, gap: float
    ) -> tuple[list[float], float, float]:
        """``(ratios, aside_w, rest_w)`` for a ``row[ fixed aside | rest ]`` split.

        The aside cell keeps the width its own rendering gives it — an emoji
        icon's badge, a gutter marker's glyph — so it never grows with the row
        and never shrinks below its glyph. The gap between the cells is carved
        out FIRST, so cell + gap + cell fit *available_width* exactly and the
        renderer never has to scale them back down.

        Whether an aside is *affordable* is decided upstream: ``_aside_fits``
        for the icon; a gutter marker has no such question — it always draws.
        """
        usable = max(0.0, available_width - gap)
        aside_w = min(aside_w, usable)
        rest_w = usable - aside_w
        return [aside_w, max(1.0, rest_w)], aside_w, rest_w

    def _aside_cell_width(self, child: MarkdownGroupNode) -> float:
        """Rendered width of a cell placed aside.

        An icon is its measured glyph — the theme's emoji/icon style, the same
        number the renderer draws — NOT a ``LEAF_WIDTH`` text category, which
        would size a star by how many *words* it counts as (80/100px for a 53px
        badge, or ``inf`` with no category, which as a FIXED width would swallow
        the whole row). Without a measurer it falls back to the theme's own icon
        size, then to the narrowest leaf width — always finite, because a fixed
        cell is taken literally. Everything else keeps ``_min_width``.
        """
        if child.type != "emoji":
            return self._unit_min(child)
        measured = self._measured_min(child)
        if measured:
            return measured
        if self._theme is not None:
            return self._theme.emojis.primary.icon_size
        return LEAF_WIDTH["one_word"]

    def _aside_min_width(
        self,
        aside_child: MarkdownGroupNode,
        children: list[MarkdownGroupNode],
        owner_level: int = 0,
    ) -> float:
        """Minimum width of an aside arrangement: the aside cell + the widest
        rest-column child + the gap between the two columns.  The single
        source for both the aside feasibility check and the grid's per-unit
        width when a repeated unit takes an icon aside — so the
        two can never drift. The aside cell is sized by ``_aside_cell_width``,
        the same call the builder uses, so the gate and the build agree."""
        rest = [c for c in children if c is not aside_child]
        rest_min = max(
            (self._unit_min(c) for c in rest),
            default=0.0,
        )
        return (
            self._aside_cell_width(aside_child)
            + rest_min
            + _col_gap(aside_child, self._theme, owner_level, self._owner_key)
        )

    def _aside_fits(
        self,
        image: MarkdownGroupNode,
        children: list[MarkdownGroupNode],
        available_width: float,
        owner_level: int = 0,
    ) -> bool:
        """True if image + rest-column both meet their min width (plus the gap
        between the two columns)."""
        return self._aside_min_width(image, children, owner_level) <= available_width

    def _build_icon_aside(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        in_glued: bool = False,
        owner_level: int = 0,
    ) -> LayoutNode:
        """Place a lone-emoji icon in a gutter beside a col of the rest.

        Position picks the side: a FIRST-child icon takes the left gutter, a
        LAST-child icon the right one.
        Callers gate on that position (``_icon_aside_candidate``), so this only
        has to read which end the icon sits at.

        An icon is NOT flexible — it has its own rendered width
        (``_aside_cell_width``), so the cell never takes a proportional share:
        it is a fixed aside, split by
        ``_aside_split`` exactly like a gutter marker, with the content column
        taking what is left of the gap-reduced width.
        """
        kids = node.children
        leading = kids[0].type == "emoji" and kids[0].emoji_kind == "alone"
        icon = kids[0] if leading else kids[-1]
        rest = kids[1:] if leading else kids[:-1]

        ratios, icon_w, rest_w = self._aside_split(
            self._aside_cell_width(icon),
            available_width,
            _col_gap(icon, self._theme, owner_level, self._owner_key),
        )

        icon_cell = self._make_leaf(icon, node, icon_w)
        # Fixed cell: the renderer must not scale it with the row (see the
        # overflow branch of _layout_row), same contract as a marker leaf.
        icon_cell.render_properties = {
            **(icon_cell.render_properties or {}),
            "aside_fixed": True,
        }
        if len(rest) == 1:
            rest_cell = self._render_child(rest[0], rest_w, node, in_glued, owner_level)
        else:
            rest_children = [
                self._render_child(c, rest_w, node, in_glued, owner_level) for c in rest
            ]
            rest_cell = LayoutNode(
                type="col",
                ratios=[1.0] * len(rest_children),
                children=rest_children,
            )
        # A trailing icon mirrors the split: the fixed cell and its ratio both
        # move to the right end, so the gutter is on the side the author wrote
        # the icon on.
        cells = [icon_cell, rest_cell] if leading else [rest_cell, icon_cell]
        return LayoutNode(
            type="row",
            ratios=ratios if leading else list(reversed(ratios)),
            children=cells,
        )

    # ------------------------------------------------------------------
    # Predicates
    # ------------------------------------------------------------------

    def _is_full_width(
        self,
        node: MarkdownGroupNode,
        parent: MarkdownGroupNode | None,
    ) -> bool:
        """Return True if node should occupy full available width.

        The root takes the same rules as any other node and does not
        short-circuit to True, so Priority 4 can grid top-level repeated runs.
        """
        # Contains a long paragraph child.
        if any(_length_category(c) == "long_paragraph" for c in node.children):
            return True

        return False

    # ------------------------------------------------------------------
    # Measurement helpers
    # ------------------------------------------------------------------

    def _cols_for_unit(
        self,
        unit: MarkdownGroupNode,
        available_width: float,
        max_cols: int,
        run: list[MarkdownGroupNode] | None = None,
        owner_level: int = 0,
        unit_min: float | None = None,
    ) -> int:
        """Maximum columns for a repeated unit at *available_width*.

        Reads the unit's propagated ``text_length_category`` (set in
        ``markdown_grouper._annotate_text_lengths`` — group nodes inherit the
        max category of their descendants) and looks up the minimum per-column
        width in ``LEAF_WIDTH``.  When a theme is present, each column also
        reserves the unit's own wrap padding and the columns reserve the
        (cols-1) inter-column gaps, so the count matches what the renderer can
        honor.  Categories without a ``LEAF_WIDTH`` entry (``long_paragraph``,
        ``None``) collapse to 1 column.  With a width measurer, the per-column
        minimum also floors at the widest single-line pill across the whole
        *run* (every member shares a column width, and the longest button can
        sit anywhere in it), so a column is never narrower than the longest
        button it must hold.
        """
        min_w = generator_displays.column_floor(self._ctx, unit)
        if min_w is None or min_w < 0:
            return 1
        min_w = max(
            min_w,
            max(self._measured_min(u) for u in (run or [unit])),
            # The run's aside-aware unit width (an icon-aside unit spans
            # icon + content + gap) — threaded in by the caller, so this
            # fit rule itself stays aside-agnostic.
            unit_min or 0.0,
        )
        unit_w = (
            min_w
            + generator_displays.column_padding_x(self._ctx, unit)
            + generator_markers.marker_gutter_x(unit, self._theme)
        )
        gap = _col_gap(unit, self._theme, owner_level, self._owner_key)
        # Largest cols with cols*unit_w + (cols-1)*gap <= available_width.
        denom = unit_w + gap
        cols = int((available_width + gap) / denom) if denom > 0 else 1
        return min(max_cols, max(1, cols))

    @staticmethod
    def _balance_cols(cols: int, n: int) -> int:
        """Step a fit-max column count down so the last (ragged) grid row fills at
        least ``MIN_LAST_ROW_FILL`` — avoiding a lonely orphan cell.

        ``cols`` is the fit maximum from ``_cols_for_unit`` (already clamped to
        ``<= n``). This only ever *reduces* it (never below the content-min fit),
        floors at 2 (a 2-col grid ending in one cell is exactly 1/2 and stays), and
        leaves already-balanced runs untouched. Among the acceptable smaller counts
        it prefers the FEWEST rows, then the most even last row, then more columns.
        """
        if cols < 3 or n <= cols:
            return cols

        def rows(k: int) -> int:
            return math.ceil(n / k)

        def fill(k: int) -> float:
            return (n - (rows(k) - 1) * k) / k

        if fill(cols) >= MIN_LAST_ROW_FILL:
            return cols
        cands = [k for k in range(2, cols) if fill(k) >= MIN_LAST_ROW_FILL]
        if not cands:
            return 2
        cands.sort(key=lambda k: (rows(k), -fill(k), -k))
        return cands[0]

    @staticmethod
    def _balance_kind_cols(cols: int, run_lens: list[int]) -> int:
        """The same fill rule as ``_balance_cols``, decided once for a whole KIND.

        ``_kind_cols`` gives every run of a kind one shared column count, so the
        one-run rule cannot be applied to it directly — the runs have different
        lengths and would each ask for a different count, which is the consistency
        the shared count exists to provide. This votes instead: keep the fit-max
        unless at least ``ORPHAN_RUN_SHARE`` of the kind's runs would end on a row
        filling less than ``MIN_LAST_ROW_FILL``, then step down to a count where
        NO run of the kind does. Ordering among those matches ``_balance_cols`` —
        fewest rows (summed over the runs), then most even, then more columns —
        so for a kind with a SINGLE run this returns exactly what
        ``_balance_cols`` returns; the generalization re-decides nothing.

        ``run_lens`` is every grid run of the kind. Runs of one (an ``orphan_grid``
        member) neither orphan nor vote: a lone card held at its siblings' width is
        deliberate, and ``Orphan row`` in the theme is what governs its row.
        """
        runs = [n for n in run_lens if n >= 2]
        if cols < 3 or not runs:
            return cols

        def rows(k: int, n: int) -> int:
            return math.ceil(n / k)

        def fill(k: int, n: int) -> float:
            # A run shorter than the count is one ragged row, not an orphaned last
            # one — the same passthrough _balance_cols makes for ``n <= cols``.
            if n <= k:
                return 1.0
            return (n - (rows(k, n) - 1) * k) / k

        def orphan_share(k: int) -> float:
            return sum(1 for n in runs if fill(k, n) < MIN_LAST_ROW_FILL) / len(runs)

        share = orphan_share(cols)
        # A count nothing orphans at is already right — checked separately so that
        # an ORPHAN_RUN_SHARE of 0 reads as "step down when ANY run orphans" rather
        # than "step down always".
        if share == 0 or share < ORPHAN_RUN_SHARE - _SHARE_EPSILON:
            return cols
        cands = [k for k in range(2, cols) if orphan_share(k) == 0]
        if not cands:
            return 2
        cands.sort(
            key=lambda k: (
                sum(rows(k, n) for n in runs),
                -min(fill(k, n) for n in runs),
                -k,
            )
        )
        return cands[0]

    def _cell_height(
        self,
        unit: MarkdownGroupNode,
        width: float,
        parent: MarkdownGroupNode,
        owner_level: int,
    ) -> float:
        """Rendered height of *unit* at about *width*, memoized per
        ``(id(unit), width bucket)``.

        Uses the renderer's height-for-width closure (``self._measure``) on the
        unit's own rendered subtree — mirroring bento — and falls back to the
        font-less ``_estimate_cell_height`` when no measurer is present. The memo
        (``self._cell_h_cache``) keeps the ``_aspect_cap`` candidate sweep from
        re-rendering the same member at the same width, so the recursion stays
        bounded to O(nodes x distinct candidate widths).

        Widths share a measurement per ``CELL_HEIGHT_BUCKET`` px: the trial builds
        (bento scoring, each packed block built at its share of a line) ask at widths that almost
        never repeat to the pixel, and a card's height barely moves across a few.
        This is an approximation on purpose — the generator only decides the
        arrangement, and the renderer measures the real one.
        """
        if width <= 0:
            return 0.0
        bucket = int(width) // CELL_HEIGHT_BUCKET
        key = (id(unit), bucket)
        cached = self._cell_h_cache.get(key)
        if cached is not None:
            return cached
        # Measured at the bucket's FLOOR, so a card is never measured wider than
        # it is: a height from a narrower width errs taller, which leans the
        # aspect cap toward fewer columns rather than toward a tall-thin sliver.
        w = float(max(bucket * CELL_HEIGHT_BUCKET, 1))
        if self._measure is not None:
            sub = self._render_child(unit, w, parent, False, owner_level)
            h = self._measure(sub, w) or 0.0
        else:
            h = _estimate_cell_height(unit, w)
        self._cell_h_cache[key] = h
        return h

    def _aspect_cap(
        self,
        run: list[MarkdownGroupNode],
        cols: int,
        available_width: float,
        parent: MarkdownGroupNode,
        owner_level: int,
    ) -> int:
        """Widen a repeated grid (fewer columns) until its tallest member is no
        longer a tall-thin sliver — never below what content needs.

        Widening exists for cards of wrapping text, which get shorter as their
        column widens. A column is dropped only for that: a count is accepted
        only when it makes the run's tallest member shorter than at ``cols``
        Cards whose height does not follow their
        width — ring displays, link lists, fixed-height cards — keep their
        columns, since widening them would only lengthen the page.

        Walks down from ``cols`` and stops at the first ``k`` whose tallest
        member's aspect (``height / column_width``) is within ``TARGET_ASPECT``,
        landing on the smallest count walked that is shorter. Guards the
        image-dominated case with ``HEIGHT_GROWTH_CAP``: the walk stops at a
        ``k`` that makes the tallest member more than that multiple of its
        height at ``cols`` (widening a stacked-image card only makes it
        taller). Returns ``cols`` unchanged when already within target, when
        there is no measurer-or-estimate signal, or when no smaller ``k`` is
        shorter.
        """
        if cols < 2 or len(run) < 2:
            return cols
        gap = _col_gap(run[0], self._theme, owner_level, self._owner_key)

        def col_w(k: int) -> float:
            return (available_width - (k - 1) * gap) / k

        def max_h(k: int) -> float:
            w = col_w(k)
            if w <= 0:
                return float("inf")
            return max(self._cell_height(m, w, parent, owner_level) for m in run)

        base_h = max_h(cols)
        if base_h <= 0:
            return cols
        # Already acceptable at the current count -> leave it (and same-kind runs
        # converge here, since this test is width/shape-based, not run-length based).
        if base_h / col_w(cols) <= TARGET_ASPECT:
            return cols
        best = cols
        for k in range(cols - 1, 0, -1):
            w = col_w(k)
            if w <= 0:
                continue
            h = max_h(k)
            if h > base_h * HEIGHT_GROWTH_CAP:
                break  # image-dominated: widening only makes it taller -> stop
            if h < base_h - ASPECT_CAP_SHORTER_BY:
                best = k
            if h / w <= TARGET_ASPECT:
                break
        return best

    def _build_kind_maps(self, root: MarkdownGroupNode) -> None:
        """Precompute per-``kind_hash`` grid data so every repeated run of a kind —
        and its orphans — resolve to ONE shared column count (`_kind_cols`).

        Walks the AST once collecting, per kind, the grid *members* (nodes in a
        ``repeated_children`` bucket of groups + ``orphan_grid`` groups), the widest
        member min-width (the "longest value" that floors the shared card width),
        and the largest run size (so we never grid more columns than the biggest run
        holds).
        """
        members: dict[int, list[MarkdownGroupNode]] = self._kind_members
        max_run: dict[int, int] = self._kind_max_run
        # Every run's length, so the shared count can weigh the fill rule across all
        # of them at once (_balance_kind_cols) instead of against one run.
        run_lens: dict[int, list[int]] = self._kind_run_lens
        # Distinct grid occurrences of a kind (buckets + orphans). Consistency only
        # matters when >=2 exist; a lone run keeps its per-run fit+fill (below).
        occ: dict[int, int] = self._kind_occurrences

        def walk(node: MarkdownGroupNode) -> None:
            for bucket in (node.repeated_children or {}).values():
                # Leaves stack (only groups grid), so a leaf is no occurrence.
                k = bucket[0].kind_hash if bucket and _is_group(bucket[0]) else None
                if k is not None:
                    members.setdefault(k, []).extend(bucket)
                    max_run[k] = max(max_run.get(k, 0), len(bucket))
                    run_lens.setdefault(k, []).append(len(bucket))
                    occ[k] = occ.get(k, 0) + 1
            for c in node.children:
                if c.orphan_grid and c.kind_hash is not None and _is_group(c):
                    members.setdefault(c.kind_hash, []).append(c)
                    occ[c.kind_hash] = occ.get(c.kind_hash, 0) + 1
                walk(c)

        walk(root)
        for k, ms in members.items():
            mw = 0.0
            for m in ms:
                soft = generator_displays.column_floor(self._ctx, m) or 0.0
                meas = self._measured_min(m)
                mw = max(mw, soft, meas)
            self._kind_min_width[k] = mw
            # The width floor above is every member's; only the aspect check
            # samples (see KIND_SWEEP_SAMPLE).
            if len(ms) > KIND_SWEEP_SAMPLE:
                self._kind_sample[k] = sorted(
                    ms,
                    key=lambda m: _estimate_cell_height(m, KIND_SWEEP_RANK_WIDTH),
                    reverse=True,
                )[:KIND_SWEEP_SAMPLE]

    def _kind_cols(
        self,
        unit: MarkdownGroupNode,
        available_width: float,
        parent: MarkdownGroupNode,
        owner_level: int,
        unit_min: float | None = None,
    ) -> int | None:
        """Shared column count for every same-kind run at *available_width*.

        The natural fit from the kind's widest member min-width (no ``len(run)``
        cap — a small run just fills fewer cells), clamped to the largest run size,
        then the per-kind aspect cap (``_kind_aspect_cap``: seeded with ALL members
        whenever it can fire, so a tall-thin cap fires for every same-kind run
        together), and LAST the per-kind fill vote
        (``_balance_kind_cols``: the shared count owes the same last-row floor a
        per-run count does, weighed over every run of the kind at once — and it
        goes last because the aspect cap can itself stand a run's last row up as
        an orphan). ``unit_min`` (the run's
        aside-aware width, e.g. an icon-aside unit) floors the fit, same as
        ``_cols_for_unit``. Returns ``None`` when the kind isn't a tracked grid kind
        (→ caller keeps the per-run path), so singleton/non-repeated layouts are
        unaffected.
        """
        k = unit.kind_hash
        members = self._kind_members.get(k)
        min_w = self._kind_min_width.get(k)
        # Only enforce a shared count when the kind occurs >=2 times (multiple runs,
        # or a run + orphans). A lone run has no sibling to be consistent with, so the
        # caller keeps its per-run fit+fill+aspect.
        if (
            not members
            or not min_w
            or min_w <= 0
            or self._kind_occurrences.get(k, 0) < 2
        ):
            return None
        min_w = max(min_w, unit_min or 0.0)
        unit_w = (
            min_w
            + generator_displays.column_padding_x(self._ctx, unit)
            + generator_markers.marker_gutter_x(unit, self._theme)
        )
        gap = _col_gap(unit, self._theme, owner_level, self._owner_key)
        denom = unit_w + gap
        cols = int((available_width + gap) / denom) if denom > 0 else 1
        cols = min(self._kind_max_run.get(k, cols), max(1, cols))
        if cols > 1:
            cols = self._kind_aspect_cap(
                k, members, cols, available_width, parent, owner_level
            )
        # The fill vote has the LAST word on the count, because the aspect cap can
        # hand back a k that strands a run on a lonely last row: a 5-item run at 5
        # columns is one clean row until aspect widens the kind to 4, and then it
        # is 4+1. Nothing after this may lower the count again.
        return self._balance_kind_cols(cols, self._kind_run_lens.get(k, []))

    def _kind_aspect_cap(
        self,
        k: int | None,
        members: list[MarkdownGroupNode],
        cols: int,
        available_width: float,
        parent: MarkdownGroupNode,
        owner_level: int,
    ) -> int:
        """``_aspect_cap`` over a kind's members, checked on its sample first.

        A kind with a sample (see ``KIND_SWEEP_SAMPLE``) is measured on those
        few members at the fit's column width. When their tallest stays clearly
        under the threshold — below ``1 - KIND_SWEEP_FALLBACK`` of it — the cap
        cannot fire and the count stands. Anything closer, and every kind without
        a sample, takes the full sweep, so a cap that fires is always decided on
        every member.
        """
        sample = self._kind_sample.get(k) if k is not None else None
        if sample:
            gap = _col_gap(members[0], self._theme, owner_level, self._owner_key)
            w = (available_width - (cols - 1) * gap) / cols
            if w > 0:
                tallest = max(
                    self._cell_height(m, w, parent, owner_level) for m in sample
                )
                if tallest / w <= (1 - KIND_SWEEP_FALLBACK) * TARGET_ASPECT:
                    return cols
        return self._aspect_cap(members, cols, available_width, parent, owner_level)

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    @staticmethod
    def _deep_last(node: MarkdownGroupNode) -> MarkdownGroupNode:
        """The last descendant of *node*, following ``children[-1]`` down."""
        while node.children:
            node = node.children[-1]
        return node

    def _build_col(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        in_glued: bool = False,
        owner_level: int = 0,
    ) -> LayoutNode:
        """Full-width column: stack all children vertically.

        A ``---`` that ends a heading group stays that group's last child and
        paints inside it, where it was written; a rule between two groups is
        written after a ``***`` that closes the first.
        """
        children: list[LayoutNode] = []
        for child in node.children:
            if _is_group(child):
                built = self._decide_group(
                    child, available_width, node, in_glued, owner_level
                )
                children.append(built)
            else:
                children.append(self._make_leaf(child, node, available_width))
        return LayoutNode(
            type="col",
            ratios=[1.0] * len(children),
            children=children,
        )

    def _column_row_widths(
        self,
        cells: list[MarkdownGroupNode],
        weights: list[float],
        available_width: float,
        owner_level: int,
    ) -> list[float]:
        """Approximate width per weighted `:::` cell on one line of the row.

        The generator's half of the deal: it ESTIMATES, so each cell's subtree is
        decided against roughly the width it will get; the renderer measures for
        real and re-derives the widths from the weights.

        A weight of ``0`` is "no share of the SURPLUS", not "no width": the cell
        is reserved its own minimum first and the rest is split among the
        weighted cells. That is what makes ``:::0`` a shrink-to-fit cell instead
        of a collapsed one.
        """
        mins = [
            self._line_item_width(c) if c.separator_kind else self._unit_min(c)
            for c in cells
        ]
        gaps = sum(
            _row_pair_gap(
                cells[i - 1], cells[i], self._theme, owner_level, self._owner_key
            )
            for i in range(1, len(cells))
        )
        surplus = available_width - gaps
        reserved = sum(m for m, w in zip(mins, weights) if not w)
        share = max(0.0, surplus - reserved)
        total = sum(w for w in weights if w)
        return [
            m if not w else (share * w / total if total else share / len(cells))
            for m, w in zip(mins, weights)
        ]

    def _column_row_lines(
        self,
        items: list[MarkdownGroupNode],
        available_width: float,
        owner_level: int,
        weight_of: dict[int, float],
        breaks: set[int] | frozenset[int] = frozenset(),
    ) -> list[list[MarkdownGroupNode]]:
        """Which items of a weighted `:::` row share each line, in order.

        Greedy first-fit on each cell's ask plus the gaps between them. A cell
        that does not fit starts the next line, as a piece of a `` - `` line
        does, so one wide cell does not take its neighbours down with it. The row's
        gaps count where they stand and drop where it wraps, as a line's do
        (ADR-203).

        A line is drawn by its weights, so it is fitted by them: a cell joins
        it only if, at the shares the weights will draw them at, every cell on
        the line still gets its ask -- or a cell is drawn under its own minimum
        and its text overlaps the next one ("measure = flow", ADR-400).
        *breaks* (item ids) start a new line wherever they fall.
        """

        def fits(cells: list, asks: list[float], used: float) -> bool:
            # ``used`` is the asks plus the gaps. An unweighted cell (a gap
            # cell, a ``:::0``) keeps its ask, and so does one the renderer
            # raises to its image floor; the rest is shared by weight.
            weights = [weight_of.get(id(c), 0.0) for c in cells]
            room = available_width - (used - sum(asks))
            floors = [self._image_floor_of(c) for c in cells]
            held = {i: a for i, (a, w) in enumerate(zip(asks, weights)) if not w}
            while True:
                total = sum(w for i, w in enumerate(weights) if i not in held)
                share = room - sum(held.values())
                if not total:
                    return share >= 0
                drawn = {
                    i: share * w / total for i, w in enumerate(weights) if i not in held
                }
                raised = {i: floors[i] for i, d in drawn.items() if floors[i] > d}
                if not raised:
                    break
                held.update(raised)
            got = [drawn.get(i, held.get(i, 0.0)) for i in range(len(cells))]
            return all(g >= a - 1e-6 for g, a in zip(got, asks))

        batches: list[tuple[list, list]] = []
        used = 0.0
        for item in items:
            w = self._line_item_width(item, available_width)
            if item.separator_kind is None:
                # Short cells ask for their real content; prose at most its
                # wrapping floor.
                ask = generator_spacers.line_ask(
                    item, self._unit_min, self._row_spacer_px
                )
                w = min(w, ask)
            prev = batches[-1][0][-1] if batches else None
            gap = (
                _row_pair_gap(prev, item, self._theme, owner_level, self._owner_key)
                if prev
                else 0.0
            )
            if (
                batches
                and id(item) not in breaks
                and fits(batches[-1][0] + [item], batches[-1][1] + [w], used + gap + w)
            ):
                batches[-1][0].append(item)
                batches[-1][1].append(w)
                used += gap + w
            else:
                batches.append(([item], [w]))
                used = w
        return [b for b, _ in generator_spacers.trim_row_edges(batches)]

    def _image_floor_of(self, node: MarkdownGroupNode) -> float:
        """The least width the renderer raises a `:::` cell to so its images
        keep their ``min_width`` (``render_measure._cell_floor``): 0 for a cell
        holding no floored image."""
        if not self._image_floors:
            return 0.0
        if node.type == NodeType.IMAGE:
            inner = self._image_floors.get(node.node_id, 0.0)
        else:
            inner = max(map(self._image_floor_of, node.children), default=0.0)
        return inner + _unit_padding_x(node, self._theme) if inner else 0.0

    def _build_column_row(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        in_glued: bool = False,
        owner_level: int = 0,
    ) -> LayoutNode:
        """An authored ``:::`` row: one cell per division.

        It is a ROW like a `` - `` line is, and it wraps like one: when the cells
        do not fit, the ones that do not start the next line. Nothing here forces
        a row -- the author asked for one, and the content can still decline it
        one cell at a time, the contract ``_aside_fits`` and ``_kv_pair_node``
        keep all-or-nothing.

        * No number written anywhere: the cells collapse to their content and
          flow as a line's pieces do, through the one builder a `` - `` line
          uses (``_flow_line_group``) -- so the two spellings of "these side by
          side" lay out alike.
        * Any number written: the row is proportions. Each line of it is a
          ``column_row`` whose ratios are the weights of the cells on it, passed
          through as PROPORTIONS -- the renderer measures for real and re-derives
          the widths, including the zero-cell floor this only approximates.
        """
        groups, written = row_groups(node, len(node.children), available_width)
        cells = [self._column_stack(node, g) for g in groups]
        if len(cells) == 1:  # no cut applies at this width: the cells stack
            only = self._render_child(
                cells[0], available_width, node, in_glued, owner_level
            )
            return self._edge_spacers(node, only, available_width)
        gaps = group_gaps(node, groups)
        weights = _row_weights(node, len(cells), written)
        if weights is None:
            return self._flow_line_group(
                node, available_width, in_glued, owner_level, cells, gaps
            )

        # The row's gaps are cells of no weight: a line's, laid between its cells.
        items = self._with_separators(node, cells, gaps=gaps)
        weight_of = {id(c): w for c, w in zip(cells, weights)}
        lines: list[LayoutNode] = []
        split = self._column_row_lines(items, available_width, owner_level, weight_of)
        # One wraps, all wrap: the cells a row wrapped before are a vote in its run.
        if pin := generator_fit_votes.line_breaks(self._fit_polls, node, cells, split):
            split = self._column_row_lines(
                items, available_width, owner_level, weight_of, pin
            )
        for line_cells in split:
            if len(line_cells) == 1:
                lines.append(
                    self._render_child(
                        line_cells[0], available_width, node, in_glued, owner_level
                    )
                )
                continue
            line_weights = [weight_of.get(id(c), 0.0) for c in line_cells]
            widths = self._column_row_widths(
                line_cells, line_weights, available_width, owner_level
            )
            row = LayoutNode(
                type="row",
                ratios=line_weights,
                children=[
                    self._render_child(c, w, node, in_glued, owner_level)
                    for c, w in zip(line_cells, widths)
                ],
            )
            row.column_row = True
            self._vote_spacers(node, [row], [line_cells], available_width, line_weights)
            lines.append(row)
        if len(lines) == 1:
            return lines[0]
        return LayoutNode(type="col", ratios=[1.0] * len(lines), children=lines)

    def _column_stack(
        self, row: MarkdownGroupNode, group: list[int]
    ) -> MarkdownGroupNode:
        """The cells of one group as ONE cell: the cell itself when it is alone,
        else a wrapper ``_render_child`` stacks — never a group the rules may
        arrange, which could put the cells back side by side."""
        if len(group) == 1:
            return row.children[group[0]]
        key = (id(row), group[0], group[-1])
        stack = self._column_stacks.get(key)
        if stack is None:
            stack = self._column_stacks[key] = stack_of(row.children, group)
            self._stack_ids.add(id(stack))
        return stack

    def _build_table(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        in_glued: bool = False,
        owner_level: int = 0,
    ) -> LayoutNode:
        """Table container: a ``table``-flagged col of ``table_row`` rows.

        Every header/body row becomes a ``row`` of its cells with EQUAL ratios
        — an approximation only. The renderer's ``_table_plan`` re-measures all
        columns with Skia and overrides these widths so columns align across
        rows (render owns reflow). Stray non-table children (defensive; the
        grouper wraps pure runs) render through the normal paths.
        """
        rows: list[LayoutNode] = []
        for child in node.children:
            if child.type in (NodeType.TABLE_HEADER, NodeType.TABLE_ROW):
                role = "header" if child.type == NodeType.TABLE_HEADER else "body"
                n = max(1, len(child.children))
                cells: list[LayoutNode] = []
                for cell in child.children:
                    if _is_group(cell):
                        built = self._decide_group(
                            cell, available_width / n, child, in_glued, owner_level
                        )
                    else:
                        built = self._make_leaf(cell, child, available_width / n)
                    built.in_table = role
                    # The column's authored alignment (the markdown delimiter
                    # row's `:---` / `:---:` / `---:`). Merged AFTER _attach_render
                    # has written this node's props, for the same reason the
                    # `...` spring is applied last there: an authored alignment
                    # outranks any hint. One write
                    # covers both cell shapes: a leaf's box carries it directly,
                    # a group cell's children pick it up through _cascade_render.
                    if cell.table_align:
                        built.render_properties = {
                            **(built.render_properties or {}),
                            "content_align": cell.table_align,
                        }
                    cells.append(built)
                rows.append(
                    LayoutNode(
                        type="row",
                        ratios=[1.0] * len(cells),
                        children=cells,
                        table_row=role,
                    )
                )
            elif _is_group(child):
                rows.append(
                    self._decide_group(
                        child, available_width, node, in_glued, owner_level
                    )
                )
            else:
                rows.append(self._make_leaf(child, node, available_width))
        return LayoutNode(
            type="col",
            ratios=[1.0] * len(rows),
            children=rows,
            table=True,
        )

    # ------------------------------------------------------------------
    # Drawn datapoint displays (grouper datapoint_display / chart_group)
    # ------------------------------------------------------------------

    def _build_date_chip(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        in_glued: bool = False,
        owner_level: int = 0,
    ) -> LayoutNode:
        """A date chip (`Mon 15` / `Jun 15`) as a card wrapping two stacked
        text leaves — reusing the glued-card wrap pipeline (``card_kind`` picks
        the chip's own themed style).

        ``node`` is the grouper-built ``group(text[key], text[day])``. Its two
        real children render through the standard text path; a ``date_role``
        render property (key/day, by position) styles each with the ### Date
        Key / ### Date Day fonts (and uppercases the key). Because the chip is
        a group, repeated adjacent chips grid via ``_build_grouped``."""
        leaves: list[LayoutNode] = []
        for i, child in enumerate(node.children[:2]):
            leaf = self._make_leaf(child, node, available_width)
            leaf.render_properties = {
                **(leaf.render_properties or {}),
                "date_role": "key" if i == 0 else "day",
            }
            leaves.append(leaf)
        col = LayoutNode(
            type="col",
            ratios=[1.0] * len(leaves),
            children=leaves,
            content_id=node.node_id or None,
        )
        col.is_card = True
        col.card_kind = "date_chip"
        # A stacking col child fills its column; wrap the chip in a row so it
        # collapses to its own content width (hugging chip) and left-aligns,
        # rather than stretching a full-width card across the line/grid cell.
        return LayoutNode(type="row", ratios=[1.0], children=[col])

    def _build_datapoint_display(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        in_glued: bool = False,
        owner_level: int = 0,
    ) -> LayoutNode:
        """Container-level bar replacements, keeping the ORIGINAL text leaves
        (content_ids intact, rendered by the normal text pipeline) beside a
        synthetic stretch-bar leaf:

        - ``unit_ratio`` (Style: bar): row [bar | text pieces] on one line;
          Style: ring keeps the single drawn ring leaf.
        - ``kv_percent_bar`` / ``unit_ratio`` from a Key: ratio pair: col of
          [row [key left, value pushed right via content_align], bar].
        """
        d = node.datapoint_display
        p = dict(node.datapoint_payload or {})
        dpth = generator_displays._dp_theme(self._ctx)
        if d == "line_chart":
            return self._line_chart_col(node, available_width, in_glued, owner_level)
        if d == "unit_ratio":
            if generator_displays._unit_ratio_is_ring(self._ctx):
                return generator_displays._build_ring(self._ctx, node)
            if p.get("from_kv"):
                position = dpth.kv_bar.position if dpth is not None else "below"
                return self._unit_ratio_kv_col(
                    node,
                    p,
                    available_width,
                    in_glued,
                    owner_level,
                    position,
                )
            leaves = [
                self._render_child(c, available_width, node, in_glued, owner_level)
                for c in node.children
            ]
            widths = [
                generator_displays._text_leaf_w(self._ctx, c) for c in node.children
            ]
            if (
                dpth is not None
                and (not dpth.unit_ratio_show_total or not dpth.unit_ratio_show_key)
                and leaves
            ):
                value = float(p.get("value", 0.0))
                mx = float(p.get("max", 0.0))
                value_text = f"{value:g}"
                if dpth.unit_ratio_show_total:
                    value_text += f"/{mx:g}"
                generator_displays._with_text_override(self._ctx, leaves[0], value_text)
                widths[0] = generator_displays._text_override_w(
                    self._ctx, node.children[0], value_text
                )
                if not dpth.unit_ratio_show_key:
                    leaves = leaves[:1]
                    widths = widths[:1]
            return generator_displays._bar_text_row(
                self._ctx, p, "unit", leaves, widths, available_width
            )
        # kv_percent_bar
        position = dpth.kv_bar.position if dpth is not None else "below"
        return self._kv_bar_col(
            node, p, "percent", available_width, in_glued, owner_level, position
        )

    def _kv_pair_node(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        in_glued: bool,
        owner_level: int,
    ) -> LayoutNode | None:
        """``row[key, value]`` for a KEY_VALUE pair, or ``col`` when it can't fit.

        The key and value subtrees are the ORIGINAL nodes built normally
        (content_ids kept); the value is pushed to the row's right edge via the
        ``content_align`` render property — the row-level placement key the
        renderer's fit branch buckets on (``text_align`` would only align glyphs
        inside the already-collapsed box). A stacked value stays left-aligned
        under its key.

        Side-by-side only when key + value meet their min widths plus the
        inter-column gap; otherwise it collapses to a vertical stack, the same
        rule ``_decide_group_icon_aside`` applies to an aside that doesn't fit. That
        measurement is why the row-vs-stack call lives here and not in the
        grouper, which cannot measure anything.

        ``None`` when the node is not a well-formed pair, so the caller can fall
        back to its own build.
        """
        key = next((c for c in node.children if c.type == NodeType.KEY), None)
        value = next((c for c in node.children if c.type == NodeType.VALUE), None)
        if key is None or value is None:
            return None
        built_key = self._render_child(
            key, available_width, node, in_glued, owner_level
        )
        built_value = self._render_child(
            value, available_width, node, in_glued, owner_level
        )
        key_min = self._unit_min(key)
        value_min = self._unit_min(value)
        gap = _col_gap(key, self._theme, owner_level, self._owner_key)
        # One stacks, all stack: inside a grid the answer is a vote (ADR-301).
        fits = key_min + value_min + gap <= available_width
        if generator_fit_votes.vote(self._fit_polls, node, not fits):
            return LayoutNode(
                type="col", ratios=[1.0, 1.0], children=[built_key, built_value]
            )
        built_value.render_properties = {
            **(built_value.render_properties or {}),
            "content_align": "right",
        }
        return LayoutNode(
            type="row", ratios=[1.0, 1.0], children=[built_key, built_value]
        )

    def _kv_bar_col(
        self,
        node: MarkdownGroupNode,
        payload: dict,
        kind: str,
        available_width: float,
        in_glued: bool,
        owner_level: int,
        position: str,
    ) -> LayoutNode:
        """Key/value text selected by its bar theme, plus the full-width bar.

        The pair itself is :meth:`_kv_pair_node`'s job — the same row-or-stack
        this builds for an authored ``Key: ... Value``; only the bar below it is
        specific to a datapoint display."""
        dpth = generator_displays._dp_theme(self._ctx)
        show_key = dpth is None or kind != "percent" or dpth.kv_bar.show_key
        show_value = dpth is None or kind != "percent" or dpth.kv_bar.show_value
        inner = None
        if show_key and show_value:
            inner = self._kv_pair_node(node, available_width, in_glued, owner_level)
        else:
            key = next((c for c in node.children if c.type == NodeType.KEY), None)
            value = next((c for c in node.children if c.type == NodeType.VALUE), None)
            if key is not None and value is not None:
                visible = [
                    self._render_child(c, available_width, node, in_glued, owner_level)
                    for c, shown in ((key, show_key), (value, show_value))
                    if shown
                ]
                if not visible:
                    return LayoutNode(
                        type="col",
                        ratios=[1.0],
                        children=[
                            generator_displays._bar_leaf(self._ctx, payload, kind)
                        ],
                    )
                inner = visible[0]
        if inner is None:
            # Defensive: unexpected KV shape keeps the stacked build.
            inner = self._build_col(node, available_width, in_glued, owner_level)
        # The label/value text and its bar are ONE datapoint element: flag the
        # text part line_split so the renderer's _line_side exception spaces the
        # text↔bar gap with element (not group) spacing — matching
        # _bar_text_row.
        inner.line_split = True
        return generator_displays._bar_stack_col(
            self._ctx, inner, payload, kind, position
        )

    def _line_chart_col(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        in_glued: bool,
        owner_level: int,
    ) -> LayoutNode:
        """Key and last value over the drawn line of ``Key: a → b → c``.

        The pair always shares one row, key left and the last value as written
        pushed right: unlike a bar's, a line's text never stacks, so the line
        keeps its label beside its latest value at every width."""
        key = next((c for c in node.children if c.type == NodeType.KEY), None)
        value = next((c for c in node.children if c.type == NodeType.VALUE), None)
        if key is None or value is None:
            inner = self._build_col(node, available_width, in_glued, owner_level)
        else:
            built_key = self._render_child(
                key, available_width, node, in_glued, owner_level
            )
            built_value = self._render_child(
                value, available_width, node, in_glued, owner_level
            )
            payload = node.datapoint_payload or {}
            points = payload.get("points") or [{}]
            fmt = self._theme.charts.value_format if self._theme is not None else "1"
            last = with_unit(
                str(points[-1].get("text") or ""), payload.get("display_unit"), fmt
            )
            generator_displays._with_text_override(self._ctx, built_value, last)
            built_value.render_properties = {
                **(built_value.render_properties or {}),
                "content_align": "right",
            }
            inner = LayoutNode(
                type="row", ratios=[1.0, 1.0], children=[built_key, built_value]
            )
        inner.line_split = True
        line = generator_displays._line_leaf(node)
        return LayoutNode(type="col", ratios=[1.0, 1.0], children=[inner, line])

    def _unit_ratio_kv_col(
        self,
        node: MarkdownGroupNode,
        payload: dict,
        available_width: float,
        in_glued: bool,
        owner_level: int,
        position: str,
    ) -> LayoutNode:
        """Key/value ratio bar honoring Unit Ratios text visibility."""
        dpth = generator_displays._dp_theme(self._ctx)
        if dpth is None or (dpth.unit_ratio_show_total and dpth.unit_ratio_show_key):
            return self._kv_bar_col(
                node,
                payload,
                "kv_unit",
                available_width,
                in_glued,
                owner_level,
                position,
            )
        key = next((c for c in node.children if c.type == NodeType.KEY), None)
        value = next((c for c in node.children if c.type == NodeType.VALUE), None)
        if key is None or value is None:
            return self._kv_bar_col(
                node,
                payload,
                "kv_unit",
                available_width,
                in_glued,
                owner_level,
                position,
            )
        visible: list[LayoutNode] = []
        if dpth.unit_ratio_show_key:
            visible.append(
                self._render_child(key, available_width, node, in_glued, owner_level)
            )
        built_value = self._render_child(
            value, available_width, node, in_glued, owner_level
        )
        if not dpth.unit_ratio_show_total:
            generator_displays._with_text_override(
                self._ctx,
                built_value,
                f"{float(payload.get('value', 0.0)):g}",
            )
        visible.append(built_value)
        if len(visible) == 2:
            built_value.render_properties = {
                **(built_value.render_properties or {}),
                "content_align": "right",
            }
            text_part = LayoutNode(type="row", ratios=[1.0, 1.0], children=visible)
        else:
            text_part = visible[0]
        text_part.line_split = True
        return generator_displays._bar_stack_col(
            self._ctx, text_part, payload, "kv_unit", position
        )

    # --- image rule DISABLED ---
    # def _build_mosaic(
    #     self, node: MarkdownGroupNode, available_width: float
    # ) -> LayoutNode:
    #     """Grid of image-only children."""
    #     cols = min(
    #         len(node.children), max(1, int(available_width / IMAGE_MIN_WIDTH))
    #     )
    #     rows: list[LayoutNode] = []
    #     for i in range(0, len(node.children), cols):
    #         batch = node.children[i : i + cols]
    #         row = LayoutNode(
    #             type="row",
    #             ratios=[1.0] * len(batch),
    #             children=[self._make_leaf(img) for img in batch],
    #         )
    #         rows.append(row)
    #     return LayoutNode(
    #         type="col",
    #         ratios=[1.0] * len(rows),
    #         children=rows,
    #     )

    def _run_min_width(self, item: MarkdownGroupNode) -> float:
        """The width the widest same-kind RUN inside *item* needs to stay on one
        line: its member count times what one member needs, plus the gaps.

        The no-collapse walk reads the BUILT tree, where a run has already been
        split into grid rows of however many columns fitted — so it reports the
        width of one ROW of the grid, not of the run. That is the right number
        for a grid that is meant to wrap and the wrong one for a block being
        offered a width: measured that way a block asks for a third of what its
        run wants, is handed it, and the run re-columns.

        Asked of the MARKDOWN side, where the run is still a run (the grouper's
        ``repeated_children`` buckets), so the answer is about the run itself.
        """
        widest = 0.0
        stack = [item]
        while stack:
            node = stack.pop()
            for bucket in (node.repeated_children or {}).values():
                if len(bucket) < 2:
                    continue
                unit = max(
                    self._measured_min(m) + _unit_padding_x(m, self._theme)
                    for m in bucket
                )
                gap = _col_gap(bucket[0], self._theme, 0)
                widest = max(widest, len(bucket) * unit + (len(bucket) - 1) * gap)
            stack.extend(node.children)
        return widest

    @staticmethod
    def _is_titled_section(node: MarkdownGroupNode) -> bool:
        """Whether a heading group was written with a TITLE, rather than as a bare
        ``## `` marker used only to group what follows."""
        return any(
            _HEADING_TYPE_RE.match(c.type) and c.content.strip() for c in node.children
        )

    @staticmethod
    def _mark_fill(built: LayoutNode, fill: bool) -> LayoutNode:
        """Tell the renderer this cell keeps the width it was given.

        Stamped on every cell of a packed row, because the row was sized to fill
        its line: an unstamped cell collapses back to its content
        (``_row_desired_widths``) and puts the leftover hole straight back.
        """
        if fill:
            built.render_properties = {
                **(built.render_properties or {}),
                "fill_row": True,
            }
        return built

    def _block_width(
        self,
        item: MarkdownGroupNode,
        available_width: float,
        parent: MarkdownGroupNode,
        in_glued: bool,
        owner_level: int,
    ) -> float:
        """The width a packing candidate asks for: what its content needs so that
        nothing in it has to wrap.

        Built at the full width and handed to ``measure_block``, because the
        number the packing needs is a property of what the block BECOMES, not of
        the markdown it came from: a section holding a two-card grid needs both
        cards side by side, while its widest markdown CHILD is one card.

        The ask is the larger of two: the longest ROW inside the block, gaps and
        paddings included (text still wraps, so a long paragraph does not drag a
        block wide), and the widest same-kind RUN kept on one line. Measured at
        the width offered, which a block arranges by even when it fits in less.

        The ask is TRUSTED, not verified (ADR-302): rebuilding the block at that
        width and bisecting toward the narrowest width that kept the full-width
        arrangement would cost a large share of generate() time. Without that, a
        grid whose cards floor wider than their text (a card is sized by its length
        CATEGORY) can use one column
        fewer inside a packed block. Text never overflows: the ask already covers
        every text row.

        Falls back to ``_line_item_width`` with no measurer, which is what the
        hand-built fixtures and the measurer-less callers get.
        """
        if self._measure_block is None:
            return self._line_item_width(item, available_width)
        key = (item.node_id, available_width)
        hit = self._block_w_cache.get(key)
        if hit is not None:
            return hit
        built = self._render_child(item, available_width, parent, in_glued, owner_level)
        width = max(
            self._measure_block(built, available_width), self._run_min_width(item)
        )
        self._block_w_cache[key] = width
        return width

    def _packs_any_unique(self, node: MarkdownGroupNode) -> bool:
        """Whether *node* holds two adjacent children the ``Stack sections`` flow
        would put on one row — the routing test for ``_decide_group``.

        Without it a node whose children are all of DIFFERENT kinds never reaches
        ``_build_grouped`` at all (that route is gated on ``repeated_children``,
        which such a node has none of) — and a document of all-different blocks
        is precisely the one the packing exists for.
        """
        repeated_ids = {
            id(n) for grp in (node.repeated_children or {}).values() for n in grp
        }
        run = 0
        for child in node.children:
            run = run + 1 if self._packs_unique(child, repeated_ids) else 0
            if run >= 2:
                return True
        return False

    def _packs_unique(self, child: MarkdownGroupNode, repeated_ids: set[int]) -> bool:
        """Whether *child* may sit beside its neighbours instead of spanning the
        row — the eligibility test for the ``Stack sections`` flow.

        What packs is a ``## `` BAND: a heading group, titled or a bare marker.
        A leaf never does — a leaf is content with no children, so a section's own
        title, a horizontal rule and a content break are all excluded by that one
        rule, and excluding them is the point, since a title packed beside the
        body it introduces reads as two unrelated things. Neither does a deeper
        group, for the reason spelled out at the test below.

        What is left out beyond that is every child that already owns an
        arrangement of its own, or its own separation: a repeated member (it
        grids), an ``orphan_grid`` member (it is gridded at its siblings' card
        width), a table, an authored ``:::`` or same-line row, a list item — a
        list is a stack, and its items are a sequence rather than a set of
        independent blocks — a section ending in a ``---``, and a titled section
        at the document's top heading rank.
        """
        if not self._pack_unique:
            return False
        if id(child) in repeated_ids or not _is_group(child):
            return False
        # SECTIONS only. A deeper element group is content an author arranged on
        # purpose — the pieces of a card, the cells of a `:::` row — and putting
        # two of those side by side second-guesses a decision that was already
        # made, in the one place the `:::` syntax exists to let an author make.
        # A heading group is a band, and bands are what this packs.
        if not child.heading_group:
            return False
        if getattr(child, "orphan_grid", False):
            return False
        if child.type == NodeType.LIST_ITEM:
            return False
        # A section ENDING in a ``---`` is announcing a division from what comes
        # next, which is the opposite of "put me beside my neighbour".
        if child.heading_group and self._deep_last(child).type == (
            NodeType.HORIZONTAL_RULE
        ):
            return False
        # A TITLED section at the document's top rank is a chapter: it keeps the
        # whole line, and the packing happens INSIDE it. This is what bento does
        # with headings, and it is the difference between a page of `## ` bands —
        # bare markers grouping a few lines, which are exactly what should sit
        # beside each other — and a page of `# ` chapters, which should not.
        top = self._top_heading_level
        if (
            child.heading_group
            and top is not None
            and _section_level(child) == top
            and self._is_titled_section(child)
        ):
            return False
        return not (
            child.table_group or child.column_split_group or child.line_split_group
        )

    def _build_grouped(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        in_glued: bool = False,
        owner_level: int = 0,
        packed: dict[int, tuple[LayoutNode, int]] | None = None,
    ) -> LayoutNode:
        """Stack children in document order, gridding each contiguous run of
        repeated same-fingerprint siblings.

        A child is "repeated" iff it appears in ``node.repeated_children`` (the
        grouper records children that have an adjacent same-fingerprint twin).
        Consecutive repeated children sharing a ``fingerprint_hash`` form one
        run; a run that packs into more than one column becomes a grid,
        otherwise its children render full-width.  Non-repeated children render
        full-width.  Two runs of the same fingerprint separated by other content
        therefore each grid independently, in place.

        ``packed`` maps a child index to a layout already built for the children
        up to an end index — bento's mosaics — which takes their place; the
        children around it are laid out as if bento were off, so a leftover too
        short for a mosaic still grids.
        """
        repeated_ids = {
            id(n) for grp in (node.repeated_children or {}).values() for n in grp
        }
        packed = packed or {}
        sections: list[LayoutNode] = []
        kids = node.children
        i, n = 0, len(kids)
        while i < n:
            if i in packed:
                built, i = packed[i]
                sections.append(built)
                continue
            child = kids[i]
            if id(child) not in repeated_ids:
                # Orphaned repeated element: a lone child of a kind its sibling
                # groups grid (flagged by the grouper). Grid it at the SAME card
                # width its siblings use (the kind's natural fit at this width) —
                # one cell, left-aligned — instead of full width, for consistency.
                if getattr(child, "orphan_grid", False) and _is_group(child):
                    ocols = (
                        self._kind_cols(child, available_width, node, owner_level) or 1
                    )
                    if ocols > 1:
                        sections.extend(
                            self._grid_rows(
                                [child],
                                available_width,
                                ocols,
                                node,
                                in_glued,
                                owner_level,
                            )
                        )
                        i += 1
                        continue
                # A maximal run of consecutive UNIQUE groups packs side by side:
                # each at the width it wants, as many per row as fit, wrapping to
                # the next row when the line runs out. Repeated siblings grid
                # because equal things deserve equal sizing; a one-off group owes
                # its neighbours nothing, so making it span the page is width
                # spent on nothing. A run of one keeps the plain full-width path.
                j = i
                while (
                    j < n
                    and j not in packed
                    and self._packs_unique(kids[j], repeated_ids)
                ):
                    j += 1
                if j - i >= 2:
                    sections.extend(
                        self._flow_rows(
                            kids[i:j],
                            available_width,
                            node,
                            in_glued,
                            owner_level,
                            width_of=lambda c: self._block_width(
                                c, available_width, node, in_glued, owner_level
                            ),
                            one_run=False,
                            fill=True,
                            balance=True,
                        )
                    )
                    i = j
                    continue
                built = self._render_child(
                    child, available_width, node, in_glued, owner_level
                )
                sections.append(built)
                i += 1
                continue

            # Extend a maximal contiguous run of same-kind members. Runs are
            # keyed on run_key (the grouper's contiguous same-kind run id, which
            # folds in the ±1 tolerance) so visually-identical cards that differ
            # only in counts / inline split depth / a single optional element
            # still form one run and grid together.
            h = child.run_key
            j = i + 1
            while (
                j < n
                and j not in packed
                and id(kids[j]) in repeated_ids
                and kids[j].run_key == h
            ):
                j += 1
            run = kids[i:j]
            # Repeated *group* runs (e.g. repeated card groups) grid into
            # uniform columns. ELEMENT runs — chips, links, emojis — flow-wrap
            # instead: as many per row as fit at their measured single-line
            # widths, and the renderer packs them at natural width with element
            # spacing. Other repeated *leaf* runs (short texts that merely share
            # a fingerprint) stay stacked full-width.
            #
            # Elements flow aside only as the pieces of ONE source line
            # (``⭐ `Popular` | 🚀 `…```). A run spread over several lines is a
            # LIST of buttons and stacks — one per row — leaving any other
            # arrangement to the repeated same-kind logic below (leaf runs take
            # cols=1). Same test, and same ``{None}`` convention for hand-built
            # fixtures, as the line-split branch right after this one.
            #
            # Most element runs carry line_split_group and reach the branch
            # below instead; what arrives here is a run whose PARENT is not itself
            # one line, plus hand-built fixtures. It has to agree with that branch,
            # so it
            # passes the same two arguments: measure each piece as a full single
            # line, and stamp the rows line_split so they baseline-align
            # (_row_valign_offsets returns zeros for a row that is not flagged,
            # so an unflagged row of chips would sit top-aligned beside an
            # identical-looking emoji row).
            if run[0].type in ELEMENT_LEAF_TYPES:
                if len({m.source_line_id for m in run}) == 1:
                    sections.extend(
                        self._flow_rows(
                            run,
                            available_width,
                            node,
                            in_glued,
                            owner_level,
                            width_of=lambda c: self._line_item_width(
                                c, available_width
                            ),
                            line_split=True,
                        )
                    )
                    i = j
                    continue
            # Runs of line groups flow or stack as lines (_line_run).
            line_run = _line_run(run)
            if line_run is not None:
                if line_run == "flow":
                    sections.extend(
                        self._flow_rows(
                            run,
                            available_width,
                            node,
                            in_glued,
                            owner_level,
                            width_of=lambda c: self._line_item_width(
                                c, available_width
                            ),
                            # Glued wins: a run of carded line groups emits rows
                            # of cards — those rows space like cards, not line
                            # content (members share a fingerprint, glued is
                            # uniform).
                            line_split=not run[0].glued_content_group,
                        )
                    )
                else:
                    # List rows share their pictures' params like any run.
                    if shares_params(run):
                        self._unify_run_render(run, available_width)
                    # One wraps, all wrap (ADR-301): the lines poll their breaks.
                    sections.extend(
                        generator_fit_votes.stacked_lines(
                            self._fit_polls,
                            run,
                            lambda c: self._render_child(
                                c, available_width, node, in_glued, owner_level
                            ),
                        )
                    )
                i = j
                continue
            # Poll → measure → grid: unify the run FIRST (pinning its icon
            # aside on every member), then size the unit under it (an aside
            # unit is wider than its stacked self), and only then pick the
            # column count.
            if _is_group(run[0]):
                # Heading sections are built at their own level, so the poll
                # asks there; a run that mixes levels keeps its container's.
                levels = {m.heading_level if m.heading_group else None for m in run}
                built = levels.pop() if len(levels) == 1 else None
                icon_aside = self._unify_run(run, built or owner_level, available_width)
                unit_min = self._unit_min_for(run, icon_aside, built or owner_level)
                # Consistency: every same-kind run shares ONE column count (widest
                # member fit, per-kind aspect, per-kind fill vote) — the fill floor
                # is honoured there across all of the kind's runs at once. Falls
                # back to the per-run fit+aspect+fill path for untracked kinds.
                cols = self._kind_cols(
                    run[0], available_width, node, owner_level, unit_min=unit_min
                )
                if cols is None:
                    cols = self._cols_for_unit(
                        run[0],
                        available_width,
                        max_cols=len(run),
                        run=run,
                        owner_level=owner_level,
                        unit_min=unit_min,
                    )
                    if cols > 1:
                        cols = self._aspect_cap(
                            run, cols, available_width, node, owner_level
                        )
                    # Fill rule LAST, for the reason _kind_cols gives: the aspect
                    # cap can strand the row the fill rule just cleared — 10 items
                    # fit 4 as 4+4+2 and come back from aspect as 3+3+3+1.
                    cols = self._balance_cols(cols, len(run))
            else:
                cols = 1
            if cols > 1:
                sections.extend(
                    self._grid_rows(
                        run, available_width, cols, node, in_glued, owner_level
                    )
                )
            else:
                sections.extend(
                    self._render_child(c, available_width, node, in_glued, owner_level)
                    for c in run
                )
            i = j

        return LayoutNode(
            type="col",
            ratios=[1.0] * len(sections),
            children=sections,
        )

    def _render_child(
        self,
        child: MarkdownGroupNode,
        available_width: float,
        parent: MarkdownGroupNode,
        in_glued: bool = False,
        owner_level: int = 0,
    ) -> LayoutNode:
        """Render one child full-width: recurse into groups, leaf otherwise."""
        if id(child) in self._stack_ids:
            return LayoutNode(
                type="col",
                ratios=[1.0] * len(child.children),
                children=[
                    self._render_child(
                        c, available_width, parent, in_glued, owner_level
                    )
                    for c in child.children
                ],
            )
        sep = child.separator_kind
        if sep == "spacer":
            # An inline spacer (ADR-203): the leaf builder sizes it.
            return self._make_leaf(child, parent, available_width)
        if sep is not None:
            # A drawn row separator (## Separators): a synthetic cell with no
            # markdown node behind it, exactly like a gutter marker, so the
            # renderer draws it from render_properties instead of node_index.
            return LayoutNode(
                type="-",
                ratios=[],
                children=[],
                content_id=None,
                render_properties={"separator": {"char": child.content, "kind": sep}},
            )
        if _is_group(child):
            return self._decide_group(
                child, available_width, parent, in_glued, owner_level
            )
        return self._make_leaf(child, parent, available_width)

    def _flow_line_group(
        self,
        node: MarkdownGroupNode,
        available_width: float,
        in_glued: bool = False,
        owner_level: int = 0,
        cells: list[MarkdownGroupNode] | None = None,
        gaps: list[str] | None = None,
    ) -> LayoutNode:
        """Arrange pieces that sit side by side as flowed rows: the children of a
        ``line_split_group``, or *cells*, the cells of a `:::` row with no number
        and *gaps* between them.

        The children are the pieces of ONE source line (separator segments,
        comma-list items, peeled emojis, datapoint splits, kept ``•``
        separators), so each piece is measured at its **full single-line
        width** (``_line_item_width``; category fallback without fonts) and
        packed back into rows exactly like pill runs — as many pieces per row
        as fit with element spacing, wrapping to further rows only when the
        line is genuinely too long for the available width. A row's cells are
        such pieces too, so the two spellings of one row lay out alike.
        """
        line = cells is None
        cells = list(node.children) if cells is None else cells
        # One cell per piece: the row's gaps and edges are its line's.
        pieces = self._with_separators(node, cells, gaps=gaps)
        width_of = lambda c: self._line_item_width(c, available_width)  # noqa: E731
        flow = lambda **kw: self._flow_rows(  # noqa: E731
            pieces, available_width, node, in_glued, owner_level, **kw
        )
        lines: list = []
        rows = flow(width_of=width_of, lines=lines)
        # One wraps, all wrap: a line that wrapped its pieces votes in its run;
        # a cloud of chips or links wraps as words do, and casts nothing.
        polls = self._fit_polls
        votes = line and not _is_pure_element_group(node)
        if votes and (
            pin := generator_fit_votes.line_breaks(polls, node, cells, lines)
        ):
            lines = []
            rows = flow(width_of=width_of, breaks=pin, lines=lines)
        # A `:::` row that wraps its cells has stacked them: a vote in its run.
        if not line and generator_fit_votes.row_stacks(polls, node, rows):
            width_of = generator_fit_votes.cell_per_line(width_of, available_width)
            lines = []
            rows = flow(width_of=width_of, lines=lines)
        if line:  # where a spring line wrapped, its pieces settle (ADR-304)

            def reflow(order: list, breaks: frozenset) -> tuple[list, list]:
                nonlocal pieces
                pieces, flowed = self._with_separators(node, order), []
                return flow(width_of=width_of, breaks=breaks, lines=flowed), flowed

            rows, lines = generator_spring_wrap.rewrap(polls, node, rows, lines, reflow)
        self._vote_spacers(node, rows, lines, available_width)
        # Mark everything this line emits (rows and single-piece leaves) so
        # the renderer element-spaces any adjacency — between this line and
        # its neighbors, and between the line's own wrapped rows.
        for r in rows:
            r.line_split = True
        # A spring line's rows must claim the width they are offered rather than
        # collapse to their content, or there is no slack for the spring to open
        # and the regions sit flush against each other. Flagged off the GROUPER
        # node for the same reason ``block_line`` is: the laid-out row also holds
        # the cells ## Separators inserts.
        if node.align_group:
            for r in rows:
                r.spring = True
        result = rows[0]
        if len(rows) > 1:
            result = LayoutNode(type="col", ratios=[1.0] * len(rows), children=rows)
            result.line_split = True
        # A HEADING's line flows and baseline-aligns like any other line, but
        # toward its neighbors it must still space as a heading: without this a
        # split `# 🔖 Emojis` would sit closer to the body under it than a plain
        # `# Emojis` does. Its own wrapped rows keep the tight line spacing.
        if _HEADING_TYPE_RE.match(node.type):
            result.heading_line = True
        # …and a line whose every piece is a BLOCK (colon columns, KV pairs) is
        # not a line of words: internally it flows, but toward its neighbors it
        # is a group of groups and must take the group gap. Read off the GROUPER
        # node, never the laid-out row — that row also holds the cells
        # ## Separators inserts, so `[col, sep, col]` would test as "not all
        # blocks" and the spacing would silently depend on whether the theme
        # draws ` | `.
        result.block_line = bool(cells) and all(c.children for c in cells)
        return result

    def _with_separators(
        self,
        node: MarkdownGroupNode,
        items: list[MarkdownGroupNode] | None = None,
        gap_offset: int = 0,
        gaps: list[str] | None = None,
    ) -> list[MarkdownGroupNode]:
        """``node.children`` with the drawn row separators put back in the gaps.

        *items* flows a CONTIGUOUS SLICE of the line instead of the whole of it
        — the aside takes the image out and flows what is left — and
        *gap_offset* is the index of the slice's first gap in the line's own
        ``separator_chars``, so a leading image does not hand its own separator
        to the pieces after it. *gaps* are the gaps between *items* when they
        are a whole `:::` row read at one width (``group_gaps``).

        The split ate the ` - ` / ` • ` / ` | ` and the grouper only recorded
        which characters they were (``separator_chars``, one per gap) — whether
        any of them is drawn is a THEME decision, and this is the first place in
        the pipeline that has the theme. Returns the children unchanged when the
        line has no separators or the theme draws none of them, so the default
        layout is bit-identical to having no feature at all.

        The cells go through ``_flow_rows`` as ordinary items, so they are
        measured, packed and wrapped with everything else.
        """
        kids = list(node.children) if items is None else list(items)
        chars = getattr(node, "separator_chars", None) if gaps is None else gaps
        theme = self._theme
        if chars:
            chars = chars[gap_offset:]
        # A spacer at the line's own edge (`+++ B`, ADR-203) goes with the slice
        # that holds that edge; a spacer CELL beside the line is not the line's.
        whole, own = gaps is not None, not node.spacer_beside and node.children
        lead = (
            node.spacer_lead
            if kids and own and (whole or kids[0] is node.children[0])
            else None
        )
        trail = (
            node.spacer_trail
            if kids and own and (whole or kids[-1] is node.children[-1])
            else None
        )
        if not chars and not lead and not trail:
            return kids
        if len(kids) < 2:
            chars = []

        seps = theme.separators if theme is not None else None
        rule = theme.vertical_rule if theme is not None else None

        def cell(ch: str, i: int) -> MarkdownGroupNode | None:
            if seps is None or rule is None:
                return None
            if ch == "|":
                # `Draw` wins over `Bar` — "Bar: hide" + "Draw: yes" is the
                # useful pairing: no pipe character, just the line.
                if rule.draw:
                    kind = "rule"
                elif seps.bar:
                    kind = "glyph"
                else:
                    return None
            elif not seps.dash:
                return None
            else:
                kind = "glyph"
            n = MarkdownGroupNode(type=NodeType.TEXT, content=ch)
            n.separator_kind = kind
            return n

        def gap_cells(gap: str, i: int) -> list[MarkdownGroupNode]:
            # A gap holds every separator between two pieces, in order. Its
            # spacers merge into ONE, their sizes summed, and are made whatever
            # the theme draws (ADR-203); a drawn separator keeps its own cell.
            cells: list[MarkdownGroupNode] = []
            marks: list[str] = []
            for ch in gap:
                if ch in INLINE_SPACERS:
                    marks.append(INLINE_SPACERS[ch])
                    continue
                if marks:
                    cells.append(spacer_cell(" ".join(marks), kids[i - 1]))
                    marks = []
                c = cell(ch, i)
                if c is not None:
                    cells.append(c)
            if marks:
                cells.append(spacer_cell(" ".join(marks), kids[i - 1]))
            return cells

        out: list[MarkdownGroupNode] = (
            [spacer_cell(lead, kids[0], edge=True)] if lead else []
        )
        for i, child in enumerate(kids):
            if i and chars:
                # A line can mix separators, so each gap takes its own; a short
                # list (defensive) reuses the last known gap.
                out.extend(gap_cells(chars[min(i - 1, len(chars) - 1)], i))
            out.append(child)
        if trail:
            out.append(spacer_cell(trail, kids[-1], edge=True))
        return out

    def _piece_stacks(self, item: MarkdownGroupNode) -> bool:
        """Whether a flowed group piece will be laid out as a ``col``.

        Only a piece that is itself one line (``line_split_group``) flows. The
        grouper withholds that flag from every shape written on one line that
        must still stack (``line_stacks``), and a block -- a `:::` cell of
        several lines -- has no line to flow along, so there is ONE definition
        of "stacks" rather than a generator guess about structure.

        One thing the grouper cannot know: it has no theme, so it calls a date
        chip a stack unconditionally. With chips switched off
        ``_decide_group_rules`` bakes the key/day pair back into a single
        ``date_text`` leaf, and the widest half would under-measure the line the
        author actually wrote — so gate that family on the theme here.
        """
        if item.datapoint_display == "date_chip":
            return generator_displays._dp_display_enabled(self._ctx, item)
        return not item.line_split_group

    def _vote_spacers(self, node, rows, lines, width, weights=None) -> None:
        """Enter each of *node*'s *rows* holding spacers in its run, with
        whether it is short of room for them (a run's spacers give way together)."""
        if not self._fit_polls:
            return
        gap = _row_pair_gap if weights else _flow_pair_gap
        for row, items in zip(rows, lines):
            if len(items) > 1 and any(c.type == NodeType.SPACER for c in items):
                short = generator_spacers.short_of_room(
                    items,
                    width,
                    lambda c: self._beside_spacer(c, width, weights is not None),
                    lambda a, b: gap(a, b, self._theme),
                    weights,
                )
                generator_fit_votes.spacer_row(self._fit_polls, node, row, short)

    def _beside_spacer(self, piece, width: float, whole: bool) -> float:
        """What *piece* needs beside a spacer before the spacer gives way: its
        line, or a text's reading floor (``render_measure._beside_spacer_floor``)
        unless the *whole* line is asked (a weighted cell's share)."""
        w = self._line_item_width(piece, width)
        if whole or piece.type in (NodeType.IMAGE, NodeType.SPACER):
            return w
        if piece.children and not generator_spacers.holds(piece):
            return w  # a block its spacers do not hold asks its line
        return min(w, self._unit_min(piece))

    def _row_spacer_px(self, spelling: str) -> float:
        """A spacer across a line, sized at the surface being built."""
        props = generator_spacers.spacer_props
        return props(self._theme, spelling, "row", *self._spacer_scope)["size"]

    def _unit_min(self, node: MarkdownGroupNode, theme=None) -> float:
        """``_min_width`` with this generate()'s standing arguments.

        The measurer, the per-generate memo and the K-V role table travel
        together to every fit check; binding them here is what stops one call
        site being handed a different set from the next.
        """
        return _min_width(
            node,
            self._theme if theme is None else theme,
            self._measure_width,
            self._min_w_cache,
            self._kv_roles,
        )

    def _measured_min(self, node: MarkdownGroupNode) -> float:
        """``_measured_min_width`` with this generate()'s standing arguments."""
        return _measured_min_width(
            node,
            self._measure_width,
            self._theme,
            self._min_w_cache,
            self._kv_roles,
        )

    def _line_item_width(self, item: MarkdownGroupNode, width: float = 0.0) -> float:
        """Single-line width of a flowed piece.

        Leaves measure via ``measure_line`` (category fallback without fonts);
        a *group* piece is measured the way the renderer's ``natural_width``
        measures the node it will become:

        - a piece that FLOWS (an emoji-peeled segment sub-group) is the width
          its own flow needs on one line — a ``row``;
        - a piece that STACKS (a spaced-colon column, a Key: value, a titled
          heading section, a date chip, a `:::` cell of several lines) is as
          wide as its WIDEST child — a ``col``. Summing them made `14:30 : LHR : London` report 136px where
          it draws 45px, so the line "did not fit" and wrapped early, leaving a
          card full of empty space.

        Either way the piece's **own wrap padding** is added: a piece is
        rendered into exactly the width measured here, and a glued card then
        carves its padding out of that, so leaving the padding out left the
        piece's own children short by it and wrapped them onto a second row.
        Each child's own padding arrives through the recursion.

        A leaf the theme's ``Key`` / ``Value`` style covers is measured at that
        style's font: ``self._kv_roles`` already resolves the role for every
        node, however deep under its pair it sits, so nothing is threaded here.
        """
        if item.type == NodeType.SPACER:
            return self._row_spacer_px(item.content)
        sep = item.separator_kind
        if sep is not None:
            # A rule is its stroke; a glyph measures like the character it is.
            if sep == "rule":
                theme = self._theme
                return theme.vertical_rule.stroke_width if theme else 1.0
            if self._measure_line is not None:
                w = self._measure_line(item)
                if w is not None:
                    return w
            return LEAF_WIDTH.get("one_word", 100.0)
        if item.type == NodeType.IMAGE:
            # Neither measurer sizes an image — both return None for one — so
            # without this branch a photo would fall to the LEAF_WIDTH table
            # below and be measured by how many WORDS its alt text counts as.
            # An authored ``?md2ui.max_width`` is taken literally, because the
            # renderer pins a capped image to exactly that width and hands the
            # slack to its siblings (``_row_desired_widths``). Everything else
            # is stretchable and only needs a floor: its authored ``min_width``,
            # else the width below which an image beside content stops being
            # worth it — the same one ``_min_width`` gives it.
            hints = self._url_render(item, width)
            capped = (
                height_sized(hints.to_render_dict()).get("max_width") if hints else None
            )
            floor = self._image_floors.get(item.node_id, 0.0)
            base = float(capped) if capped else floor or IMAGE_MIN_WIDTH
            return base + _unit_padding_x(item, self._theme)
        role = self._kv_roles.get(item.node_id) if item.node_id else None
        if item.children:
            pad = _unit_padding_x(item, self._theme)
            if self._piece_stacks(item):
                ws = [self._line_item_width(c, width) for c in item.children]
                return max(ws, default=0.0) + pad
            # Ask for exactly what the flow packs, or it wraps the line (ADR-400).
            pieces = item.children
            if item.line_split_group:
                pieces = self._with_separators(item)
            ws = [self._line_item_width(c, width) for c in pieces]
            return _batch_width(pieces, ws, self._theme) + pad
        if self._measure_line is not None:
            w = (
                self._measure_line(item, role)
                if role is not None
                else self._measure_line(item)
            )
            if w is not None:
                return w
        # A caller may supply only the plain width measurer (hand-built
        # fixtures do, and element runs come through here). Falling straight to the
        # category table would make every leaf of a kind the same width and turn
        # width-driven wrapping
        # into fixed-size batches.
        if self._measure_width is not None:
            w = self._measure_width(item)
            if w is not None:
                return w
        return LEAF_WIDTH.get(_length_category(item) or "", 100.0)

    @staticmethod
    def _balance_batches(batches: list, available_width: float, theme) -> None:
        """Even out a flow's last two rows in place, so the tail is not a lone cell.

        Greedy first-fit fills every row as full as it can, which leaves whatever
        is left over on its own: four blocks that would sit 2 and 2 come out 3 and
        1. The same blemish the repeated grids avoid by stepping their column
        count down, and the same answer — move items back one at a time while the
        last row is more than one short of the row above it and the move still
        FITS. Widths never change, so a block that fitted still fits; only which
        row it sits on does.
        """
        if len(batches) < 2:
            return
        prev_items, prev_w = batches[-2]
        last_items, last_w = batches[-1]
        while len(last_items) < len(prev_items) - 1:
            moved, moved_w = prev_items[-1], prev_w[-1]
            trial = [moved] + last_items
            trial_w = [moved_w] + last_w
            if _batch_width(trial, trial_w, theme) > available_width:
                return
            prev_items.pop()
            prev_w.pop()
            last_items.insert(0, moved)
            last_w.insert(0, moved_w)

    def _flow_rows(
        self,
        items: list[MarkdownGroupNode],
        available_width: float,
        parent: MarkdownGroupNode,
        in_glued: bool = False,
        owner_level: int = 0,
        width_of=None,
        line_split: bool = False,
        one_run: bool = True,
        fill: bool = False,
        balance: bool = False,
        breaks: set[int] | frozenset[int] = frozenset(),
        lines: list | None = None,
    ) -> list[LayoutNode]:
        """Flow-wrap a run of same-line pieces: greedy first-fit batches in
        document order — as many items per row as fit at their measured
        single-line widths plus the gap the RENDERER will put between each
        pair (``_flow_pair_gap``: group or element, decided per adjacency).

        Used for pill runs (link / inline_code; the default ``width_of``
        measures the pill), for ``line_split_group`` children (the caller passes
        a full-single-line ``width_of``) and, with ``fill``, for the blocks
        ``Stack sections`` packs.

        Emits *plain* rows (no ``grid`` flag) so the renderer's ``_layout_row``
        packed branch collapses each pill back to the same measured width and
        packs with per-pair element gaps and ``content_align`` — shrinking the
        blank space — the batches are built with the very numbers it measures
        with. A batch of one (a pill wider than the row) renders full-width,
        stacked. The width-proportional ``ratios`` only matter in
        the renderer's overflow fallback (measurer-less themed renders), where
        they degrade gracefully.

        ``fill`` asks for the other ending: the row's leftover is shared across
        every piece in proportion to what it asked for, and each is stamped so
        the renderer keeps the width rather than collapsing it. A row of BLOCKS
        wants that — a card that stops at its minimum leaves a hole beside it,
        and the hole is what the packing exists to remove.

        *breaks* (piece ids) start a new row wherever they fall; *lines*
        receives the pieces of each row.
        """
        theme = self._theme

        def pill_w(item: MarkdownGroupNode) -> float:
            if self._measure_width is not None:
                w = self._measure_width(item)
                if w is not None:
                    return w
            return LEAF_WIDTH.get(_length_category(item) or "", 100.0)

        if width_of is None:
            width_of = pill_w

        rows: list[LayoutNode] = []
        batch: list[MarkdownGroupNode] = []
        widths: list[float] = []
        cur_w = 0.0

        def flush() -> None:
            if not batch:
                return
            if len(batch) == 1:
                rows.append(
                    self._render_child(
                        batch[0], available_width, parent, in_glued, owner_level
                    )
                )
            else:
                # Spend the leftover. The batch was measured at the width each
                # piece NEEDS, so a row of small blocks stops short of the edge
                # and leaves a hole — the whitespace the packing exists to
                # remove. ONE rule shares it out: every block grows by the same
                # FACTOR, in proportion to the width it asked for. So the row
                # spans its line, the blocks keep their relative sizes, and no
                # block is ever left under the width its own content was proven
                # at — which is what a per-block rule could not promise, because
                # the renderer normalises these numbers (``_row_desired_widths``)
                # and a cell inflated past the line divides every other cell down.
                cells = list(widths)
                if fill:
                    slack = available_width - _batch_width(batch, cells, theme)
                    base = sum(cells)
                    if slack > 0 and base > 0:
                        cells = [w + slack * w / base for w in cells]
                row = LayoutNode(
                    type="row",
                    ratios=cells,
                    children=[
                        self._mark_fill(
                            self._render_child(item, w, parent, in_glued, owner_level),
                            fill,
                        )
                        for item, w in zip(batch, cells)
                    ],
                )
                # Line-piece runs: the emitted rows are line content — stamp
                # them so the renderer element-spaces them (toward neighbors
                # and between wrapped rows of the same run).
                row.line_split = line_split
                rows.append(row)

        # Collected first, emitted last, so the batches can be BALANCED before any
        # of them is built. Greedy first-fit alone leaves the tail short — four
        # blocks that could sit 2 and 2 come out 3 and 1 — and a lonely last row
        # is the same blemish the repeated grids step their column count down to
        # avoid. Unbalanced output is byte-identical to before when nothing moves.
        batches: list[tuple[list[MarkdownGroupNode], list[float]]] = []

        def close() -> None:
            nonlocal batch, widths, cur_w
            if batch:
                batches.append((batch, widths))
            batch, widths, cur_w = [], [], 0.0

        for item in items:
            w = width_of(item)
            # The gap the RENDERER will insert between this piece and the one
            # before it — group or element, decided per pair. Batching with a
            # flat element gap made a line of blocks measure narrower than it
            # draws, so a batch that "fit" overflowed and got scaled down.
            pair_gap = _flow_pair_gap(batch[-1], item, theme) if batch else 0.0
            needed = w if not batch else cur_w + pair_gap + w
            if batch and (needed > available_width or id(item) in breaks):
                close()
                needed = w
            batch.append(item)
            widths.append(w)
            cur_w = needed
        close()
        if balance:
            self._balance_batches(batches, available_width, theme)
        # Where a line wraps, the gap it wrapped at goes with it: a separator or
        # a spacer between pieces only exists between neighbours (ADR-203).
        batches = generator_spacers.trim_row_edges(batches)
        if lines is not None:
            lines.extend(b for b, _ in batches)
        for batch, widths in batches:
            flush()
        # A run that wrapped onto several rows is still ONE unit. Pill runs are
        # spliced straight into the parent (no wrapper node), so the only way the
        # renderer can tell these rows apart from unrelated neighbours is this
        # shared id — ``_sibling_gap`` element-spaces two siblings that carry it,
        # keeping a wrapped run evenly spaced instead of split by group gaps.
        #
        # ``one_run=False`` declines that, and a run of BLOCKS wants it declined:
        # its members are whole groups that were already siblings before the flow
        # touched them, so the vertical rhythm between two wrapped rows is the
        # rhythm those groups always had — the group or section gap — not the
        # element gap a wrapped line of pills wants.
        if one_run and len(rows) > 1:
            self._flow_seq += 1
            for r in rows:
                r.flow_run = self._flow_seq
        return rows

    @property
    def _owner_key(self) -> str | None:
        """Fixed style of the section owning the gaps between units being built."""
        return self._spacer_scope[1]

    def _orphan_row_mode(
        self, owner_level: int = 0, fixed_style_key: str | None = None
    ) -> str:
        """The THEME's ``Orphan row`` for the level that owns this grid.

        ``left`` (the default) keeps a ragged final row's cells at one column's
        width, packed left; ``center`` centers them at that width; ``stretch``
        shares the whole row between the cells that are there.

        Resolved ``sections[owner_level]`` → ``root``, the two-step lookup
        ``_cell_gap`` already uses for section spacing: the generator has no
        render cascade to ride, and ``owner_level`` is the enclosing section,
        whose fixed style (``_owner_key``) replaces its level as it does there.
        """
        theme = self._theme
        if theme is None:
            return ORPHAN_ROW_DEFAULT
        st = resolve_section_style(theme, owner_level, fixed_style_key)
        mode = getattr(st, "orphan_row", None) if st is not None else None
        return mode or getattr(theme.root, "orphan_row", ORPHAN_ROW_DEFAULT)

    def _grid_rows(
        self,
        items: list[MarkdownGroupNode],
        available_width: float,
        cols: int,
        parent: MarkdownGroupNode,
        in_glued: bool = False,
        owner_level: int = 0,
    ) -> list[LayoutNode]:
        """Emit grid rows (batches of *cols*) for *items*, recursing each item at
        the per-column width.

        Each row is tagged ``grid``/``grid_cols`` so the renderer stretches its
        cells to ``available/cols`` (fill). The last (ragged) batch keeps only its
        real children — no ``content_id=None`` placeholder cells — but ``ratios``
        stays length *cols* so ``to_dict`` re-pads for serialization (signature
        unchanged); the renderer draws only the real cells, grid-aligned left.

        The THEME's ``Orphan row`` decides what that ragged row does with the
        width its missing cells would have used. ``stretch`` has to be settled
        HERE rather than in the renderer: a cell is *built* at ``child_width``,
        so its card, wrapping and nested grids are already arranged by the time
        the renderer sees it — painting a wide box around a narrow card's
        interior is not the same thing. ``center`` is a pure placement shift and
        is left to ``_layout_grid_row``; it only needs the mode, which is stamped
        on the row so it is resolved exactly once.
        """
        gap = _col_gap(items[0], self._theme, owner_level, self._owner_key)
        child_width = max(0.0, (available_width - (cols - 1) * gap) / cols)
        mode = self._orphan_row_mode(owner_level, self._owner_key)
        # One stacks, all stack (ADR-301): the members' fit choices are votes, and
        # a run whose members disagreed is built once more with the result pinned.
        poll = generator_fit_votes.open_poll(self._fit_polls, items)
        while True:
            rows: list[LayoutNode] = []
            for k in range(0, len(items), cols):
                batch = items[k : k + cols]
                ragged = len(batch) < cols
                n = len(batch)
                width = child_width
                row_cols = cols
                if ragged and mode == "stretch":
                    # Share the whole row between the cells that are really there,
                    # and tell the renderer to divide by the same count.
                    width = max(0.0, (available_width - (n - 1) * gap) / n)
                    row_cols = n
                row_children = [
                    self._render_child(item, width, parent, in_glued, owner_level)
                    for item in batch
                ]
                row = LayoutNode(
                    type="row",
                    # A stretched ragged row has no phantom cells left to re-pad.
                    ratios=[1.0] * row_cols,
                    children=row_children,
                )
                row.grid = True
                row.grid_cols = row_cols
                if ragged and mode == "center":
                    row.render_properties = {
                        **(row.render_properties or {}),
                        "orphan_row": mode,
                    }
                rows.append(row)
            if not generator_fit_votes.settle(self._fit_polls, poll):
                return rows

    def _marker_props(self, node: MarkdownGroupNode) -> dict | None:
        """Baked render props for *node*'s gutter marker, or None (memoised).

        Also bakes ``advance`` — the measured width of the marker's glyphs, via
        the ``measure_marker`` closure — so the gutter this node's content is
        laid out against is the one the renderer will actually reserve. Without
        a measurer it stays the em-size approximation (``size``).
        """
        key = id(node)
        if key in self._marker_props_cache:
            return self._marker_props_cache[key]
        props = (
            generator_markers.build_marker_props(node, self._theme)
            if self._theme is not None
            else None
        )
        if props is not None:
            props["advance"] = (
                self._measure_marker(props)
                if self._measure_marker is not None
                else float(props["size"])
            )
        self._marker_props_cache[key] = props
        return props

    def _marker_width(self, node: MarkdownGroupNode) -> float:
        """Width of *node*'s own gutter marker CELL — the glyph/shape alone —
        or 0.0 when it takes no marker. ``Space`` is not part of it: it is the
        gap between the two aside cells (see ``_marker_space``), exactly as
        THEME.md describes it ("the gap between the marker and the
        content")."""
        props = self._marker_props(node)
        if props is None:
            return 0.0
        return float(props["advance"])

    def _marker_space(self, node: MarkdownGroupNode) -> float:
        """The gap between *node*'s gutter marker and the content it labels."""
        props = self._marker_props(node)
        return 0.0 if props is None else float(props["space"])

    def _marker_split(
        self, node: MarkdownGroupNode, available_width: float
    ) -> tuple[list[float], float, float]:
        """``(ratios, marker_w, content_w)`` for *node*'s gutter marker row.

        The one place the marker's share of a row is decided: ``_decide_group``
        /``_make_leaf`` build the content at ``content_w`` and ``_wrap_marker``
        wraps it with these same ratios, so the content can never be arranged
        for a width the row will not hand it.
        """
        props = self._marker_props(node)
        if props is None or not props.get("aside", True):
            return [1.0], 0.0, available_width
        return self._aside_split(
            self._marker_width(node), available_width, self._marker_space(node)
        )

    def _wrap_marker(
        self,
        node: MarkdownGroupNode,
        content_layout: LayoutNode,
        available_width: float,
    ) -> LayoutNode:
        """Wrap a marked item as ``row[marker | content]`` or ``col[marker, content]``.

        No-op (returns *content_layout*) when the node has no active marker, or
        when an ancestor marked item already owns a marker (``_marker_suppressed``
        — the boundary-emoji peel can nest a same-type item arbitrarily deep, and
        only the outermost item draws a marker). The marker is a synthetic ``-``
        leaf with no content_id, carrying the baked ``list_marker`` render props
        the renderer draws from. ``Space`` becomes the sibling gap. When
        the content is itself a card, the card wrap moves onto the row so the
        element background wraps marker + content together (gutter inside the
        card). ``Alignment`` is carried by an aside row; an above marker is
        left-aligned by the column layout.
        """
        content_layout.background_kind = (
            STRUCTURAL_BACKGROUND_KINDS.get(node.type) or content_layout.background_kind
        )
        if self._marker_suppressed:
            return content_layout
        # A drawn datapoint replacement (ring/bar/chip/chart) IS the item's
        # content — a gutter bullet beside it would read as list noise.
        drawn = content_layout.render_properties or {}
        if getattr(content_layout, "card_kind", None) in (
            "date_chip",
            "ring",
        ) or any(
            k in drawn
            for k in (
                "datapoint_bar",
                "datapoint_ring",
                "date_chip",
                "chart",
                "line_chart",
            )
        ):
            return content_layout
        props = self._marker_props(node)
        if props is None:
            return content_layout
        marker = LayoutNode(
            type="-",
            ratios=[],
            children=[],
            content_id=None,
            render_properties={"list_marker": props},
        )
        if props.get("aside", True):
            ratios, _marker_w, _content_w = self._marker_split(node, available_width)
            wrapper = LayoutNode(
                type="row",
                ratios=ratios,
                children=[marker, content_layout],
                render_properties={"marker_align": props.get("alignment", "top")},
            )
        else:
            wrapper = LayoutNode(
                type="col", ratios=[1.0, 1.0], children=[marker, content_layout]
            )
        wrapper.background_kind, content_layout.background_kind = (
            content_layout.background_kind,
            None,
        )
        if getattr(content_layout, "is_card", False):
            wrapper.is_card = True
            content_layout.is_card = False
        return wrapper

    def _edge_spacers(
        self, node: MarkdownGroupNode, result: LayoutNode, width: float, own_line=False
    ) -> LayoutNode:
        row = generator_spacers.edge_spacers(
            node, result, lambda c: self._make_leaf(c, node, width), own_line
        )
        if row is not result and row.type == "row":  # space across, not down
            if generator_spacers.holds(node):
                floor = {"held_floor": self._unit_min(node)}  # the renderer's too
                result.render_properties = {**(result.render_properties or {}), **floor}
            ends = (node.spacer_lead, node, node.spacer_trail)
            items = [spacer_cell(e) if isinstance(e, str) else e for e in ends if e]
            self._vote_spacers(node, [row], [items], width)
        return row

    def _ride_spacers(
        self,
        node: MarkdownGroupNode,
        only: MarkdownGroupNode,
        result: LayoutNode,
        width: float,
    ) -> LayoutNode:
        return generator_spacers.ride_spacers(
            node, only, result, lambda c: self._make_leaf(c, node, width)
        )

    def _make_leaf(
        self,
        node: MarkdownGroupNode,
        parent: MarkdownGroupNode | None = None,
        available_width: float = 0.0,
    ) -> LayoutNode:
        """The layout of leaf *node*, with the spacers at its line's edges
        (`+++ B`, ADR-203) beside it — whichever builder asked for the leaf."""
        return self._edge_spacers(
            node, self._make_leaf_bare(node, parent, available_width), available_width
        )

    def _make_leaf_bare(
        self,
        node: MarkdownGroupNode,
        parent: MarkdownGroupNode | None = None,
        available_width: float = 0.0,
    ) -> LayoutNode:
        # A link card whose content is one text (`See [a [b] c](/x) now.`) or one
        # image is a leaf, with no container to carry its click. A control's url
        # is its own action, not a card's.
        card_url = None if node.drawing_element else node.link_url
        leaf = LayoutNode(
            type="-",
            ratios=[],
            children=[],
            content_id=node.node_id,
            # A bare-heading section collapses to its heading leaf; the grouper moves
            # the heading_group flag onto it, so mark the section from the flag (not
            # guessed from the node type).
            section_level=(node.heading_level if node.heading_group else None),
            section_style_key=node.section_style_key,
            heading_id=node.heading_id if node.heading_group else None,
            rotation_index=(
                node.fixed_rotation_index
                if self._theme is not None
                and node.section_style_key
                and node.section_style_key in self._theme.fixed_sections
                else node.rotation_index
            ),
            rotation_chain=node.rotation_chain,
            rotation_path=node.rotation_path,
            link_url=card_url,
            link_node_id=node.node_id if card_url else None,
        )
        self._attach_render(leaf, node, available_width)
        if node.type == NodeType.SPACER:
            self._spacers_built = True
            axis = "row" if node.separator_kind == "spacer" else "col"
            leaf.render_properties = {
                **(leaf.render_properties or {}),
                "spacer": generator_spacers.spacer_props(
                    self._theme,
                    node.content,
                    axis,
                    *self._spacer_scope,
                    binds=node.spacer_binds,
                ),
            }
        # The theme's `Key` / `Value` text style, for a leaf inside a pair,
        # carried as a render property on the SAME leaf — no structural change.
        # The map already answers for a leaf nested any number of levels under
        # its VALUE, so there is no parent to consult. (The drawn families —
        # bare ratio, date chip, unit ratio — build composite row/col layouts
        # instead; see generator_displays._build_datapoint_display.)
        kv_role = self._kv_roles.get(node.node_id) if node.node_id else None
        if kv_role is not None:
            leaf.render_properties = {
                **(leaf.render_properties or {}),
                "kv_role": kv_role,
            }
        # A leaf unit ratio (`25/100 progress`) with Style: ring is a circular
        # bar card, not a text leaf.
        if (
            node.datapoint_display == "unit_ratio"
            and generator_displays._dp_display_enabled(self._ctx, node)
            and generator_displays._unit_ratio_is_ring(self._ctx)
        ):
            ring = generator_displays._build_ring(self._ctx, node)
            # _attach_render put this node's render properties on `leaf`, and
            # this branch throws `leaf` away — so an authored `...` spring on a
            # ring leaf reached nothing and the card sat left. Carry the
            # alignment onto the row that positions the card, which is where
            # _layout_row reads it. Only content_align: everything else on the
            # leaf describes TEXT the ring does not draw.
            align = (leaf.render_properties or {}).get("content_align")
            if align is not None:
                ring.render_properties = {
                    **(ring.render_properties or {}),
                    "content_align": align,
                }
            return self._wrap_marker(node, ring, available_width)
        # Bar-family leaves (bare ratio / unit ratio / one-leaf `A of B`) keep
        # this text leaf untouched and wrap it in a row/col with a stretch
        # bar leaf beside/below it. A marked leaf renders as
        # ``row[ marker | content ]``, so the bar is sized against the width the
        # content actually gets — mirroring _decide_group's child_width.
        content_width = (
            available_width
            if self._marker_suppressed
            else self._marker_split(node, available_width)[2]
        )
        bar_layout = generator_displays._leaf_bar_display(
            self._ctx, node, leaf, content_width
        )
        if bar_layout is not None:
            return self._wrap_marker(node, bar_layout, available_width)
        return self._wrap_marker(node, leaf, available_width)

    def _attach_render(
        self, layout_node: LayoutNode, node: MarkdownGroupNode, width: float
    ) -> None:
        """Attach the URL's per-node render hints.

        No-op on the rule-only path (no params, nothing authored). Precedence:
        the run-unified pin, then the URL params, so an annotated image still
        shows its own hints. The pin stays FIRST so a repeated run keeps one uniform set of hints;
        params get their authority inside ``_unify_run_render``'s vote, not by
        overriding the pin. Only ever sets ``render_properties``; it never
        changes the node's type/ratios/children, so the structural layout is
        untouched.

        A markdown ``...`` spring is the one exception to all of it. It is the
        source document stating an alignment for THIS node, so it is applied
        last and it is deliberately NOT a voter in ``_unify_run_render``: the
        kind-hash tolerance already lets a repeated run differ by a piece its
        siblings do not have (a button, a chip label), and such a piece is
        exactly the one an author wants pushed somewhere else. Spreading it
        across the run would take that away.
        """
        spring_align = node.authored_align
        url_hints = self._url_render(node, width)
        pinned = self._pinned_render.get(id(node))
        # The pin is checked BEFORE bailing: on a param-only document the run's
        # other members carry no opinion of their own, and
        # returning early here would leave them unstyled while the annotated
        # member got its hints — the very divergence the poll exists to prevent.
        if (
            url_hints is None
            and pinned is None
            and spring_align is None
            # …and its vertical twin, for the same reason: a `...` column on a
            # document with no params has nothing else to carry
            # its alignment, so bailing here would drop the one thing the
            # author actually wrote.
            and node.authored_valign is None
        ):
            return
        if pinned is not None:
            # The run's unified hints, which ALREADY reflect this run's params
            # (they won the vote in _unify_run_render). Deliberately not merged
            # with this node's own params: doing so would let one member of a
            # repeated run diverge from its siblings, which is exactly what the
            # poll exists to prevent.
            props = pinned.to_render_dict()
        else:
            props = url_hints.to_render_dict() if url_hints is not None else {}
        own_ratio = url_hints.aspect_ratio if url_hints is not None else None
        props = height_sized(props, own_ratio)
        # The spring goes on last: a region is itself a container, and its
        # alignment is authored.
        if spring_align is not None:
            props = {**props, "content_align": spring_align}
        # The vertical twin, on the same terms: authored, so it outranks
        # anything the run pin / URL had to say about this node.
        if node.authored_valign is not None:
            props = {**props, "content_valign": node.authored_valign}
        if props:
            layout_node.render_properties = props
