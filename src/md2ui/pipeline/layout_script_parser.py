"""
LayoutScript Parser - Python Implementation
A lightweight format for defining flexible grid layouts with ratios

Syntax:
  layout[width:height]  - Root container with viewport size
  row[1:2:3]           - Split horizontally in 1:2:3 ratio
  col[2:1]             - Split vertically in 2:1 ratio
  -                    - Explicit leaf box placeholder

Features:
  - Implicit leaf placeholders (missing children become leaves)
  - Nested subdivisions (rows inside cols inside rows)
  - Variable ratios per split
  - O(n) parsing and layout calculation
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


# ``slots=True``: the generator builds very many of these (trial builds
# dominate), and slots make generate() measurably faster. The cost is that every
# attribute must be a declared field below — assigning an undeclared one raises
# AttributeError instead of silently adding it.
@dataclass(slots=True)
class LayoutNode:
    """AST node representing a layout element"""

    type: str  # 'layout', 'row', 'col', '-'
    ratios: List[float]
    children: List["LayoutNode"]
    content_id: Optional[str] = (
        None  # set on '-' leaves; references MarkdownGroupNode.node_id
    )
    # Per-node rendering hints (image aspect/shape, text/content alignment,
    # content weight). Pure render guidance for
    # layout_render.py — it never affects this node's type/ratios/children.
    render_properties: Optional[dict] = None
    # Heading level that leads this node's subtree (1–6), or None when it
    # contains no heading. Baked during layout generation and read in O(1) by
    # layout_render.py to space same-level sibling sections apart. Runtime-only:
    # intentionally NOT serialized by to_dict/from_dict so exported layout ASTs
    # are unaffected (the render path always regenerates fresh).
    section_level: Optional[int] = None
    # Fixed heading-section style candidate selected by ``{#style-name-N}``.
    # Runtime-only, like section_level.
    section_style_key: Optional[str] = None
    # Full authored heading id, retained on the section owner for future
    # navigation. It is not rendered and is not part of layout serialization.
    heading_id: Optional[str] = None
    # The markdown node's color-rotation slot (``MarkdownGroupNode.rotation_index``),
    # carried here because a container LayoutNode has no ``content_id`` — the same
    # reason ``card_bg_url`` exists. It reaches the paint through SectionBox and
    # picks this section's / card's entry out of a multi-color background list.
    # None ⇒ no markdown node behind this box (e.g. a table row), so the renderer
    # keeps its positional counter. Runtime-only: NOT serialized, like is_card.
    rotation_index: Optional[int] = None
    # The heading levels enclosing the markdown node, outermost first
    # (``MarkdownGroupNode.rotation_chain``), for resolving the
    # ``Rotate <kind> colors`` gates. Runtime-only, like ``rotation_index``.
    rotation_chain: tuple[int | str, ...] = ()
    # The slot each of those ancestors took, aligned with rotation_chain, so a
    # box can borrow its card's color under ``Rotate colors: sync``.
    rotation_path: tuple[int, ...] = ()
    # True when this node was generated from a ``glued_content_group`` (a card /
    # end-group). Baked during generation, read in O(1) by layout_render.py to
    # wrap cards with the global element background+padding. Runtime-only:
    # intentionally NOT serialized by to_dict/from_dict.
    is_card: bool = False
    # Which themed style wraps this card: None → the global element style
    # (``theme.elements``); a name (e.g. "date_chip") → a dedicated block
    # (``theme.datapoints.date_chip.chip``). Only meaningful with is_card.
    # Runtime-only: NOT serialized, same as ``is_card``.
    card_kind: Optional[str] = None
    # Structural background owned by this node: ``unordered_list``,
    # ``numbered_list`` or ``quote``. Runtime-only, like ``is_card``; the
    # renderer maps it to the corresponding Background styles block.
    background_kind: Optional[str] = None
    # Background image for a ``card_kind == "image_card"`` card: the URL the
    # grouper put in the alt slot's construct (``![ ## Title … ](hero.png)``).
    # A container LayoutNode has no ``content_id``, so this is the only route
    # from the markdown node to the paint. Runtime-only: NOT serialized, same
    # as ``is_card``.
    card_bg_url: Optional[str] = None
    # A link card's destination (``[ …block… ](url)``, ``MarkdownGroupNode.link_url``)
    # and the markdown node it belongs to. A container has no ``content_id``, so
    # this is the only route from the grouper's annotation to a click — the same
    # reason ``card_bg_url`` exists. ``place_boxes`` notes where it lands for
    # ``render_actions``. Runtime-only: NOT serialized, same as ``is_card``.
    link_url: Optional[str] = None
    link_node_id: Optional[str] = None
    # True when this row is a repeated-unit grid row; ``grid_cols`` is the target
    # column count K. The renderer stretches cells to ``available/K`` (fill) and
    # draws only the real children — a ragged last row has fewer cells and is
    # grid-aligned left, with no empty placeholder cells. Runtime-only:
    # intentionally NOT serialized, so ``to_dict`` re-pads to K implicit leaves and
    # the layout signature is unaffected.
    grid: bool = False
    grid_cols: int = 0
    # True on rows/cols emitted by the bento (mosaic) builder. Bento row: ratios
    # are integer grid-span weights honored exactly (no content collapse) and
    # every cell stretches to the row height. Bento col: a column band whose
    # children stretch to fill the height allotted by the enclosing bento row
    # (surplus becomes bottom padding inside each cell's wrap box). Runtime-only:
    # intentionally NOT serialized, same as ``grid``.
    bento: bool = False
    # True on nodes emitted for a ``line_split_group`` (the pieces of ONE
    # source line, flowed by the generator): the rows, the wrapper col, and a
    # single-piece leaf. The renderer's _sibling_gap spaces any adjacency of a
    # flagged node with the ELEMENT gap — one line's content stays close to
    # its neighbors and its own wrapped rows. Runtime-only: NOT serialized,
    # same as ``grid``/``bento``.
    line_split: bool = False
    # Id of the flowed run this node was emitted by (0 = none): every node one
    # ``_flow_rows`` batch produces shares it, so the renderer can tell "the rows
    # ONE run wrapped onto" from "two separate blocks that happen to be
    # adjacent" — a pill run has no wrapper node to carry that (its rows are
    # spliced straight into the parent), so the relation lives on the siblings.
    # Read by ``_sibling_gap``. Runtime-only, NOT serialized.
    flow_run: int = 0
    # True on a ROW holding a markdown ``...`` spring — an authored expanding
    # gap that pushes its cells toward opposite edges. Such a row must claim the
    # width it is offered instead of collapsing to its content (``natural_width``
    # would otherwise hand it exactly the space its cells fill, leaving nothing
    # for the spring to open). Runtime-only, NOT serialized.
    spring: bool = False
    # True on a ROW an author wrote with ``:::`` dividers. Like ``spring``, it
    # claims the width it is offered instead of collapsing to its content — and
    # for a stronger reason: ``_layout_row`` ignores ``ratios`` ENTIRELY whenever
    # the content fits, so without this the authored weights would silently never
    # bind. It also puts a ratio of ``0`` in play, meaning "no share of the
    # surplus": that cell is reserved its own content width and the rest is split
    # among the weighted cells. Runtime-only, NOT serialized.
    column_row: bool = False
    # True on a COL an author partitioned with ``...`` lines. The vertical twin
    # of ``column_row``, and the same reason: a col collapsed to the sum of its
    # children's heights has no surplus left for a spring to open, so it claims
    # the height it is offered instead. Its children carry ``content_valign``
    # and are placed into top / center / bottom buckets.
    #
    # This is LayoutScript's ``col[2:1]`` half of the grammar, which the port
    # never implemented -- ``place_boxes`` reads no ratios at all. Runtime-only,
    # NOT serialized.
    col_spring: bool = False
    # True on a CONTAINER whose children sit inside one line block: the node is
    # itself ``line_split``, or it is a card nested in one. Only there do pill /
    # leaf adjacencies take the ELEMENT gap (``_sibling_gap``'s pure-pill rule);
    # outside, two pill blocks are separate elements and take the group gap.
    # Baked by ``bake_render_cascade`` — runtime-only, NOT serialized.
    gap_in_line: bool = False
    # True on the node a HEADING's own line flows into. Its pieces still flow
    # and baseline-align like any line (``line_split`` stays set), but toward
    # its NEIGHBORS it must space as a heading, not as a line: otherwise
    # `# 🔖 Emojis` would sit closer to the body under it than a plain
    # `# Emojis` does. Read only by _sibling_gap's _line_side. Runtime-only.
    heading_line: bool = False
    # True on a line whose every piece is a BLOCK (a colon column, a KV pair,
    # every cell of a ``:::`` row) rather than a word-ish leaf. Its pieces still flow and baseline-align like
    # any line (``line_split`` stays set), but toward its NEIGHBORS it is a group
    # of groups and takes the GROUP gap, not the leaf-ish element gap a line of
    # words wants — otherwise a row of stat blocks sits flush against the cards
    # above and below it. Read only by _sibling_gap's _line_side. Runtime-only.
    block_line: bool = False
    # Table layout (from a grouper ``table_group``): ``table`` marks the
    # container col; ``table_row`` ("header" | "body") marks each row node;
    # ``in_table`` carries the same role on cell leaves so _sibling_gap and
    # drawing can resolve the THEME.md table style in O(1). The renderer's
    # _table_plan overrides the generator's equal ratios with Skia-measured,
    # column-aligned widths. Runtime-only: NOT serialized, same as ``grid``.
    table: bool = False
    table_row: Optional[str] = None
    in_table: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dict with all implicit leaves made explicit."""
        d: dict = {"type": self.type}
        if self.ratios:
            d["ratios"] = self.ratios
        if self.content_id is not None:
            d["content_id"] = self.content_id
        if self.render_properties:
            d["render_properties"] = self.render_properties
        # Expand implicit leaves so every ratio slot has an explicit child
        children = list(self.children)
        if self.type in ("row", "col") and self.ratios:
            while len(children) < len(self.ratios):
                children.append(LayoutNode(type="-", ratios=[], children=[]))
        d["children"] = [c.to_dict() for c in children]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "LayoutNode":
        """Deserialize from a dict produced by to_dict()."""
        return cls(
            type=d["type"],
            ratios=d.get("ratios", []),
            children=[cls.from_dict(c) for c in d.get("children", [])],
            content_id=d.get("content_id"),
            render_properties=d.get("render_properties"),
        )


@dataclass
class LayoutBox:
    """A rendered box with position and dimensions"""

    x: float
    y: float
    width: float
    height: float
    content_id: Optional[str] = None  # from the leaf LayoutNode that produced this box
    # Effective per-node render hints for this box: the leaf LayoutNode's own
    # render_properties merged with values cascaded from ancestor groups
    # (content_weight / content_align). None when there is nothing to apply.
    render_properties: Optional[dict] = None
    # What is painted behind this box, innermost first: an ARGB int per layer,
    # or the string "image" for a photo. Filled during placement — the only
    # moment a box's whole enclosing layer stack is known — and read by
    # ## Text Color Replacements to keep text legible on a background it did
    # not choose. Paint-only: it never affects geometry, and LayoutBox is never
    # serialized (no to_dict; export_layout dumps the LayoutNode tree).
    bg_stack: tuple = ()


class LayoutScriptParser:
    """Fast recursive descent parser for LayoutScript"""

    def __init__(self):
        self.lines: List[Tuple[int, str]] = []
        self.index: int = 0

    def parse(self, text: str) -> Optional[LayoutNode]:
        """
        Parse LayoutScript text into an AST.

        Args:
            text: LayoutScript source code

        Returns:
            Root LayoutNode or None if parsing fails
        """
        # Preprocess lines: extract indentation and content
        self.lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                indent = len(line) - len(line.lstrip())
                self.lines.append((indent, stripped))

        self.index = 0
        return self._parse_node(-1)

    def _parse_node(self, min_indent: int) -> Optional[LayoutNode]:
        """Parse a single node and its children"""
        if self.index >= len(self.lines):
            return None

        indent, content = self.lines[self.index]
        if indent <= min_indent:
            return None

        # Match: layout[800:600] or row[1:2:3] or col[2:1] or -
        import re

        match = re.match(r"^(layout|row|col|-)(?:\[([^\]]+)\])?", content)

        if not match:
            self.index += 1
            return None

        type_name = match.group(1)
        ratios_str = match.group(2)

        # Parse ratios
        ratios = []
        if ratios_str:
            ratios = [float(r.strip()) for r in ratios_str.split(":")]

        node = LayoutNode(type=type_name, ratios=ratios, children=[])
        current_indent = indent
        self.index += 1

        # Parse children
        while (
            self.index < len(self.lines) and self.lines[self.index][0] > current_indent
        ):
            child = self._parse_node(current_indent)
            if child:
                node.children.append(child)

        return node

    def layout(
        self,
        ast: Optional[LayoutNode],
        default_width: float = 800,
        default_height: float = 600,
    ) -> Tuple[float, float, List[LayoutBox]]:
        """
        Convert AST to layout boxes with calculated dimensions.

        Args:
            ast: Parsed AST root node
            default_width: Default viewport width
            default_height: Default viewport height

        Returns:
            Tuple of (width, height, boxes)
        """
        if not ast:
            return default_width, default_height, []

        # Extract viewport size from layout node
        width = default_width
        height = default_height

        if ast.type == "layout" and len(ast.ratios) >= 2:
            width = ast.ratios[0]
            height = ast.ratios[1]

        boxes = self._layout_node(ast, 0, 0, width, height)
        return width, height, boxes

    def _layout_node(
        self, node: LayoutNode, x: float, y: float, w: float, h: float
    ) -> List[LayoutBox]:
        """Recursively calculate layout boxes"""
        box = LayoutBox(x=x, y=y, width=w, height=h)

        # Layout root - process children
        if node.type == "layout":
            results = []
            for child in node.children:
                results.extend(self._layout_node(child, x, y, w, h))
            return results

        # Leaf placeholder
        if node.type == "-":
            box.content_id = node.content_id
            return [box]

        # Row split (horizontal)
        if node.type == "row":
            # No children and no ratios = single leaf
            if not node.children and not node.ratios:
                return [box]

            # Has ratios but no children = create implicit leaves
            if not node.children and node.ratios:
                total = sum(node.ratios)
                widths = [(w * r) / total for r in node.ratios]
                current_x = x
                boxes = []
                for width in widths:
                    boxes.append(LayoutBox(x=current_x, y=y, width=width, height=h))
                    current_x += width
                return boxes

            # Split by ratios
            ratios = node.ratios if node.ratios else [1.0] * len(node.children)
            total = sum(ratios)
            widths = [(w * r) / total for r in ratios]

            # Pad children with implicit leaves
            children = list(node.children)
            while len(children) < len(ratios):
                children.append(LayoutNode(type="-", ratios=[], children=[]))

            current_x = x
            results = []
            for child, width in zip(children, widths):
                # Check if child is a leaf
                is_leaf = child.type == "-" or (not child.children and not child.ratios)

                if is_leaf:
                    results.append(
                        LayoutBox(
                            x=current_x,
                            y=y,
                            width=width,
                            height=h,
                            content_id=child.content_id,
                        )
                    )
                else:
                    results.extend(self._layout_node(child, current_x, y, width, h))

                current_x += width

            return results

        # Col split (vertical)
        if node.type == "col":
            # No children and no ratios = single leaf
            if not node.children and not node.ratios:
                return [box]

            # Has ratios but no children = create implicit leaves
            if not node.children and node.ratios:
                total = sum(node.ratios)
                heights = [(h * r) / total for r in node.ratios]
                current_y = y
                boxes = []
                for height in heights:
                    boxes.append(LayoutBox(x=x, y=current_y, width=w, height=height))
                    current_y += height
                return boxes

            # Split by ratios
            ratios = node.ratios if node.ratios else [1.0] * len(node.children)
            total = sum(ratios)
            heights = [(h * r) / total for r in ratios]

            # Pad children with implicit leaves
            children = list(node.children)
            while len(children) < len(ratios):
                children.append(LayoutNode(type="-", ratios=[], children=[]))

            current_y = y
            results = []
            for child, height in zip(children, heights):
                # Check if child is a leaf
                is_leaf = child.type == "-" or (not child.children and not child.ratios)

                if is_leaf:
                    results.append(
                        LayoutBox(
                            x=x,
                            y=current_y,
                            width=w,
                            height=height,
                            content_id=child.content_id,
                        )
                    )
                else:
                    results.extend(self._layout_node(child, x, current_y, w, height))

                current_y += height

            return results

        return [box]
