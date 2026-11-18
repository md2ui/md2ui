"""What a theme IS: the dataclasses a parsed THEME.md becomes.

The schema, and nothing that reads text. Every value the renderer asks the theme
for is a field here, with the default it takes when THEME.md is silent — which is
why an unthemed document still renders: the defaults ARE the design, and the file
only overrides them.

The three functions are model operations, not parsing: two merge a variant's
optional overrides onto the concrete Primary values, and one supplies Primary's
own defaults. They live with the fields they combine.

Reading a THEME.md into these is the other half, and stays in ``theme.py``. The
split is what a theme is, against how one is written down — the same pair
``AGENTS.md`` already names when it says "``theme.py`` parser + dataclass
default". Nothing here imports the parser, and nothing here imports a pipeline
stage: this is a leaf, like the node model beside it.
"""

import dataclasses

import skia

from md2ui.pipeline.theme_placeholders import ImagePlaceholder

_TEXT_COLOR = skia.ColorSetARGB(255, 60, 60, 60)

_BG_COLOR = skia.ColorSetARGB(255, 245, 245, 245)


_TRANSPARENT = skia.ColorSetARGB(0, 0, 0, 0)


_MUTED_TEXT_COLOR = skia.ColorSetARGB(255, 154, 154, 154)  # #9A9A9A

# The built-in paint: what an element draws in where THEME.md leaves it
# unstyled, grayscale only. A theme that wants colour states it.
GREY_INK = 0xFF222222  # fills, the main button, a ticked box, a line
GREY_TRACK = 0xFFE5E5E5  # tracks, an open box's ground, the tertiary button
GREY_MID = 0xFF8C8C8C  # handles, a second series
GREY_LIGHT = 0xFFBDBDBD  # an open box's ring, a third series
GREY_DARK = 0xFF5A5A5A  # a fourth series
GREY_WHITE = 0xFFFFFFFF


# The default mute: the opacity a muted element paints its own colours
# at when its theme states none of its ``Disabled …`` colours.
MUTED_OPACITY = 0.4


def muted_color(enabled: int | None, disabled: int | None, stated: bool) -> int | None:
    """One channel of an element's muted (``~~``) state.

    *stated* is whether the theme gave this element ANY ``Disabled …`` colour.
    If it did, it is taken at its word, as ``## Links`` always has been: a
    stated colour replaces the channel and an unstated one keeps *enabled*. If
    it gave none, the channel is *enabled* at ``MUTED_OPACITY``, so the state is
    never invisible. A channel the element does not paint (``None``) stays
    unpainted: muting recolours, it never adds a layer, so geometry never moves.
    """
    if enabled is None:
        return None
    if stated:
        return enabled if disabled is None else disabled
    alpha = round(((enabled >> 24) & 0xFF) * MUTED_OPACITY)
    return (alpha << 24) | (enabled & 0xFFFFFF)


def muted_gradient(
    gradient: "GradientTheme | None", stated: bool
) -> "GradientTheme | None":
    """A muted element's gradient: faded with the default mute, else as it is.

    Kept, never dropped, when the theme states its ``Disabled …`` colours, as a
    disabled button keeps its own: a badge with no other fill is sized by it.
    """
    if gradient is None or stated:
        return gradient
    faded = [muted_color(c, None, False) or 0 for c in gradient.colors]
    return dataclasses.replace(gradient, colors=faded)


def muted_shadows(shadows: "list[ShadowSpec]") -> "list[ShadowSpec]":
    """A muted element's shadows, always at ``MUTED_OPACITY``: no ``Disabled …``
    key names a shadow, so a theme's stated colours never decide it. Each keeps its
    side, offset and reach, so nothing moves."""
    return [
        dataclasses.replace(s, color=muted_color(s.color, None, False) or 0)
        for s in shadows
    ]


def inherit_shadows(
    base: "list[ShadowSpec]", own: "list[ShadowSpec]"
) -> "list[ShadowSpec]":
    """A button, chip or badge variant's shadows: its own of a kind REPLACE
    Primary's of that kind, as a variant's colour lists replace Primary's; a kind
    it declares none of is inherited whole. So a variant never holds more than
    ``SHADOW_MAX_PER_KIND`` of a kind, and a small badge does not also cast the
    large one's glow."""
    return [
        layer
        for inner in (False, True)
        for layer in (
            [s for s in own if s.inner == inner]
            or [s for s in base if s.inner == inner]
        )
    ]


LINE_ALIGN_DEFAULT = "baseline"


ORPHAN_ROW_DEFAULT = "left"


CONTENT_WIDTH_MAX = 1280.0


@dataclasses.dataclass
class TextStyle:
    font_name: str = "Arial"
    font_size: float = 13.0
    font_weight: str = ""  # "" = regular; reserved for future "bold" / "light" use
    color: int = dataclasses.field(default_factory=lambda: _TEXT_COLOR)
    # Every color key in THEME.md takes either one value or a bullet list; the
    # list is kept here and ``color`` is its first entry, so nothing that reads
    # a single color needs to know rotation exists. Two or more entries turn the
    # property into a cycling one, indexed by the node's ``rotation_index``.
    colors: list[int] = dataclasses.field(default_factory=list)
    # Marker paint for an inline ``code`` span that stayed INSIDE this style's
    # text (``This is a `marker` in a sentence``) — a standalone `code` element
    # is a pill instead (## Inline Code). A marker always keeps this style's own
    # font, size and weight; these two are the only things it may change, and
    # both being unset means the span draws as ordinary text (no paint).
    # ``marker_bg_color`` is a solid fill with no corner radius by design.
    marker_text_color: int | None = None
    marker_bg_color: int | None = None
    # The lists behind the two marker colors, so an in-text `code` span can
    # cycle with the card it sits on. The scalars stay the first entry.
    marker_text_colors: list[int] = dataclasses.field(default_factory=list)
    marker_bg_colors: list[int] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class TextStylePatch:
    """Only the text-style properties declared at one styling scope."""

    style: TextStyle = dataclasses.field(default_factory=TextStyle)
    declared: set[str] = dataclasses.field(default_factory=set)

    def apply(self, base: TextStyle) -> TextStyle:
        result = dataclasses.replace(
            base,
            colors=list(base.colors),
            marker_text_colors=list(base.marker_text_colors),
            marker_bg_colors=list(base.marker_bg_colors),
        )
        if "font_name" in self.declared:
            result.font_name = self.style.font_name
        if "font_size" in self.declared:
            result.font_size = self.style.font_size
        if "font_weight" in self.declared:
            result.font_weight = self.style.font_weight
        if "color" in self.declared:
            result.color = self.style.color
            result.colors = list(self.style.colors)
        if "marker_text_color" in self.declared:
            result.marker_text_color = self.style.marker_text_color
            result.marker_text_colors = list(self.style.marker_text_colors)
        if "marker_bg_color" in self.declared:
            result.marker_bg_color = self.style.marker_bg_color
            result.marker_bg_colors = list(self.style.marker_bg_colors)
        return result


@dataclasses.dataclass
class PaddingBox:
    """Per-side padding (TLRB). ``Padding: N`` sets all four; per-side keys override."""

    top: float = 0.0
    left: float = 0.0
    right: float = 0.0
    bottom: float = 0.0

    @property
    def x(self) -> float:
        """Total horizontal padding (left + right)."""
        return self.left + self.right

    @property
    def y(self) -> float:
        """Total vertical padding (top + bottom)."""
        return self.top + self.bottom

    def any(self) -> bool:
        return self.top > 0 or self.left > 0 or self.right > 0 or self.bottom > 0


@dataclasses.dataclass
class GradientTheme:
    type: str = "linear"  # "linear" | "radial"
    colors: list[int] = dataclasses.field(default_factory=list)
    ratios: list[float] = dataclasses.field(default_factory=list)
    start: tuple[float, float] = (0.0, 0.0)  # normalized 0–1
    end: tuple[float, float] = (0.0, 1.0)


# A shadow's blur is authored as a RADIUS, the distance the shadow reaches past
# the shape's edge. Skia blurs by a Gaussian sigma, and sigma = radius / 4 is
# the mapping that puts the falloff exactly at that distance: measured against
# the reference renders in data/markdown/tests-render/theme-tests/shadows/ it reproduces
# them to within 2/255 across the whole shadow field.
SHADOW_SIGMA_RATIO = 0.25
# The authored maximum. A larger radius is clamped, not rejected: a shadow is a
# look, and a document that asks for 400 should still render.
SHADOW_RADIUS_MAX = 250.0
# How many layers of EACH kind (inner, outer) one background may declare. Four:
# the corpus's deepest stack is one outer and two inner (clay), and an inner layer
# on a page-sized rounded rect still costs ~3 ms a frame (render_shadows), so the
# fifth is the one to measure before allowing.
SHADOW_MAX_PER_KIND = 4


@dataclasses.dataclass
class ShadowSpec:
    """One shadow layer cast by a background box.

    Shadows are a DRAWING LAYER on the shared background paint, not a property
    of any one element: every box that paints through the layered fill --
    root, heading sections, cards, image cards, lists, quotes, tables, buttons,
    inline-code chips, date chips, emoji badges, task controls, progress bars
    and their tracks, chart bars and their tracks -- gets them from the same
    three keys.

    ``inner`` picks which side of the shape the shadow falls on, and that
    decides the clip. The two are geometrically different, not mirror images:

    * an INNER shadow is clipped to the shape itself, and what is blurred is
      the region OUTSIDE the shape once it is moved by the offset -- so a
      positive offset darkens the top-left inside edge;
    * an OUTER shadow is clipped to the shape's bounds grown by ``radius`` (so
      ``radius / 2`` on each side) and moved by the offset, MINUS the shape --
      so it never paints under a translucent fill, and never spills past the
      distance the blur actually reaches.

    ``radius`` is that reach in pixels (0 = a hard-edged offset copy).
    """

    inner: bool = False
    offset_x: float = 0.0
    offset_y: float = 0.0
    # RGBA; a shadow with no color paints nothing, so 0 is the inert default.
    color: int = 0
    radius: float = 0.0

    def paints(self) -> bool:
        """True when this layer would put ink on the canvas."""
        return (self.color >> 24) & 0xFF > 0


@dataclasses.dataclass
class RootTheme:
    bg_color: int = dataclasses.field(default_factory=lambda: _BG_COLOR)
    bg_image: str | None = None
    # TLRB inset of the content box within the viewport (the root padding).
    padding: PaddingBox = dataclasses.field(default_factory=PaddingBox)
    box: bool = False  # draw a rounded-rect background behind cards
    box_fill_color: int = dataclasses.field(default_factory=lambda: _BG_COLOR)
    box_radius: float = 0.0
    gradient: GradientTheme | None = None
    # Shadow layers on the root background, in declared paint order. The root
    # fills the whole viewport, so an INNER shadow reads as a vignette around
    # the render area; an outer one has nothing outside the viewport to fall on
    # and is clipped away.
    shadows: list[ShadowSpec] = dataclasses.field(default_factory=list)
    align: str = "left"  # "left" (default) | "center"
    # ``Spacer small|medium|large`` (ADR-203): how many px a ``+++`` / ``++++``
    # / ``+++++`` in the document measures at this level, keyed by step, or by
    # "step row" / "step col" for one direction. Empty = this level states
    # nothing and the next one out decides.
    spacers: dict[str, float] = dataclasses.field(default_factory=dict)
    # Vertical alignment INSIDE a same-line row (one source line's pieces):
    # "baseline" (default) | "top" | "center" | "bottom".
    # The base of the cascade — a level that states nothing falls back here.
    line_align: str = LINE_ALIGN_DEFAULT
    # What a repeated-item grid's RAGGED final row does with the width its
    # missing cells would have used: "left" (default) | "center" | "stretch".
    # The base of the cascade — a level that states nothing falls back here.
    orphan_row: str = ORPHAN_ROW_DEFAULT
    # Cap on the layout's content width. The window may be wider; the layout
    # stops growing here. Floored at CONTENT_WIDTH_MIN. Note the model's
    # WIDE_BREAKPOINT is 768: a cap below that flips a whole document to the
    # narrow variant, which is a bigger change than it looks.
    max_width: float = CONTENT_WIDTH_MAX
    # Where the layout sits when the window is wider than ``max_width``:
    # centered (the default) or hard left. Window-only — a --screenshot sizes
    # its surface to the layout, so there is no slack to place it in.
    centered: bool = True
    layout: str = "default"  # "default" (stacked) | "bento" (mosaic) | "auto"
    # Whether UNIQUE sibling groups pack side by side instead of each taking the
    # whole width. Repeated siblings grid — equal things deserve equal sizing —
    # but a one-off group owes nothing to its neighbours, so it may take only the
    # width it wants and let the next one sit beside it. Looser than a grid: every
    # item keeps its own width, and when the line runs out the next item WRAPS
    # rather than being squeezed. On by default; `Stack sections: no` restores
    # the one-group-per-row stack.
    pack_unique: bool = True
    # Root-level section spacing (gap between root's child sections) per axis —
    # the top-level bands, and the boundary before the first heading. Root is a
    # level like any other here: a DECLARED value owns that gap, ``0`` included
    # (which is how two same-coloured bands are made flush), and unset falls
    # back to the Group spacing, then the element spacing, then 0 — the same
    # chain an unstyled heading level walks.
    #
    # Tri-state on purpose. A plain ``0.0`` default could not be told apart from
    # an authored ``Spacing: 0``; pointing the gap at the ENTERED heading's level
    # instead would let ``Heading 1 → Spacing`` own both the gap BETWEEN bands
    # and the rhythm INSIDE each one. ``None`` separates them.
    row_spacing: float | None = None
    col_spacing: float | None = None


@dataclasses.dataclass
class BentoTheme:
    """``## Content arrangement`` → ``### Bento``: how the mosaic is targeted.

    Only the targeting lives here; the mode itself is switched on by the root's
    ``Layout: Bento``.
    """

    # Heading level the mosaic tiles: its sections are the cells and whoever
    # holds them (the document root included) is the container. ``None`` = let
    # the generator pick the shallowest level with enough sections in a row.
    heading_level: int | None = None


# ``Stroke align`` values, and the aliases a theme may write for them.
STROKE_ALIGNS = {
    "center": "center",
    "centre": "center",
    "inside": "inside",
    "inner": "inside",
    "outside": "outside",
    "outer": "outside",
}


@dataclasses.dataclass
class SectionStyle:
    """Per-heading-level section background, mirroring the root's paint options.

    All paint parameters are null/zero by default, so a level paints nothing
    unless its values are defined under ``## Sections`` in THEME.md. ``padding``
    insets the section's content (like root padding): it reduces the subtree
    width and extends the section's reserved height by ``2 * padding``.
    """

    padding: PaddingBox = dataclasses.field(default_factory=PaddingBox)
    corner_radius: float = 0.0
    # Distinguishes an authored square (0) from this field's inactive default.
    # Task-control outer layers use it to override the family's fallback radius.
    corner_radius_authored: bool = False
    # Corner radius for IMAGE LEAVES inside this level (the level's own
    # ``corner_radius`` rounds its background, not the images in it). 0 = square,
    # the default.
    image_corner_radius: float = 0.0
    # Let an image inside this level run into the level's own ``padding``, so it
    # meets the card/section edge — the "fills start-to-end" look. Each edge the
    # image already TOUCHES moves out by that edge's padding, so a leading image
    # bleeds top/left/right, an aside bleeds top/left/bottom, and an image with a
    # sibling on some side never bleeds toward it. While bleeding, the level's
    # own ``corner_radius`` clips the image on the corners they now share, and
    # ``image_corner_radius`` is ignored. Off by default — nothing bleeds until a
    # level asks for it. Neither key counts toward is_active(): they must not
    # make an otherwise-blank level start painting a background.
    image_bleed: bool = False
    # Put a lone-emoji ICON in a gutter beside the whole group this level owns,
    # as ``row[ icon | col(rest) ]``, instead of leaving it on the group's first
    # line. Tri-state: None (the default) is "unset", so nothing changes until a
    # level asks. The setting reaches everything the level OWNS and stops at the
    # next heading boundary — a nested ``### Heading 3`` section answers to its
    # own key, not this one (see LayoutGenerator._theme_decision). A picture
    # goes beside text through a ``:::`` row the author writes; this key states
    # one rule for every icon a level owns instead.
    # Like image_bleed, it does NOT count toward is_active(): it must not make an
    # otherwise-blank level start painting a background.
    emoji_aside: bool | None = None
    # Horizontal alignment of the content this level owns — "left" | "center" |
    # "right". Tri-state: None (the default) is "unset", so the enclosing level's
    # value flows through and, at the top, ``RootTheme.align`` does.
    #
    # It INHERITS: a level's value reaches everything below it, including a
    # nested section, until a deeper level states its own — alignment already
    # cascades that way (layout_render._cascade_render), so this is seeded into
    # the same channel rather than resolved separately. On ``### Elements`` /
    # ``### Image Cards`` it aligns the content INSIDE the card, not the card
    # within its parent. A markdown ``...`` spring still wins over an inherited
    # value: its region carries its own content_align, and own beats inherited.
    # Like the other behavior keys it does NOT count toward is_active().
    align: str | None = None
    # VERTICAL alignment inside a same-line row (the pieces of ONE source line)
    # — "top" | "baseline" | "center" | "bottom". Tri-state like ``align``:
    # None (the default) is "unset", so the enclosing level's value flows
    # through and, at the top, ``RootTheme.line_align`` does. It INHERITS
    # through the same cascade channel for the same reason.
    #
    # It reaches ONLY rows the grouper marked as one source line: a card grid, a
    # gutter-marker row and an image aside keep top alignment and their own
    # per-cell content_valign, so no mode here can restack them. Under
    # ``baseline`` a leaf or a ``row`` cell shares the row's text baseline while
    # a ``col`` cell — which stacks, and so has no single line to offer —
    # centers on the row's text band. Like the other behavior keys it does NOT
    # count toward is_active().
    line_align: str | None = None
    # What a repeated-item grid's RAGGED final row (fewer cells than columns)
    # does with the width the missing cells would have used — "left" |
    # "center" | "stretch". Tri-state like ``align``: None (the default) is
    # "unset", so the enclosing level's value flows through and, at the top,
    # ``RootTheme.orphan_row`` does.
    #
    # ``left`` is the default, so an untouched theme is
    # inert. ``stretch`` is decided in the GENERATOR (a ragged batch is BUILT at
    # the wider width, so its card re-wraps); ``center`` is a pure placement
    # shift in the renderer. Like the other behavior keys it does NOT count
    # toward is_active().
    orphan_row: str | None = None
    # ``Spacer small|medium|large`` (ADR-203): how many px a ``+++`` / ``++++``
    # / ``+++++`` in the document measures at this level, keyed by step, or by
    # "step row" / "step col" for one direction. Empty = this level states
    # nothing and the next one out decides.
    spacers: dict[str, float] = dataclasses.field(default_factory=dict)
    # Optional gutter marker owned by this exact background level. The concrete
    # style matches the only marker kind the level can draw: bullets for
    # unordered/task lists, ordinals for numbered lists and Heading 1..6, and a
    # bar/character for quotes. Marker configuration is behavioural and does
    # not make an otherwise-empty background paint.
    marker: "BulletedListStyle | NumberedListStyle | QuoteStyle | None" = None
    # One or more fill colors; multiple colors cycle across the level's sibling
    # sections. Empty = no solid fill.
    bg_colors: list[int] = dataclasses.field(default_factory=list)
    bg_image: str | None = None
    gradient: GradientTheme | None = None
    # Shadow layers cast by this background, in declared paint order: outer
    # shadows paint under the fill, inner ones over it, each group in the order
    # it was written. Up to SHADOW_MAX_PER_KIND of each kind -- one shadow is
    # rarely enough to get a given depth, and the parser drops the extras.
    shadows: list[ShadowSpec] = dataclasses.field(default_factory=list)
    stroke_width: float = 0.0
    stroke_color: int | None = None
    # ``Stroke align``: where the line sits on the edge — "center" (straddles
    # it), "inside" or "outside" (render_shadows.stroke_shape).
    stroke_align: str = "center"
    # The full list behind ``stroke_color``, so a rotated card can carry a
    # rotated border. ``stroke_color`` stays its first entry.
    stroke_colors: list[int] = dataclasses.field(default_factory=list)
    # Per-channel color-rotation gates, from ``Rotate <kind> colors: yes|no``
    # on this heading level. Keys: background / card / emoji / link / chip /
    # heading. A missing key means "not stated here" — the renderer walks the
    # heading ancestors innermost-outermost and takes the first level that
    # states it, defaulting to enabled. Turning a channel off pins it to the
    # first color, which is how a level opts out of a cycle a parent enabled.
    rotate: dict[str, bool] = dataclasses.field(default_factory=dict)
    # ``Rotate colors: sync`` — this level SHARES its slot with everything
    # inside its sections, so a chip in the third card paints the third card's
    # color instead of counting among its fellow chips. Safe to state broadly:
    # a channel whose color list holds one color ignores the slot entirely.
    sync_slot: bool = False
    # Spacing this section applies between its OWN child sections, per axis (the
    # enclosing section owns the gap). None = inherit the root (content) value.
    # ``Spacing`` sets both; ``Row/Col spacing`` override one. Not part of is_active().
    row_spacing: float | None = None
    col_spacing: float | None = None
    # Group spacing: the gap for pairs involving a non-section group node (group↔leaf
    # or group↔group), per axis. Read only from ``theme.elements``. None = fall back to
    # the element (row/col) spacing. ``Group spacing`` sets both; ``Group row/col
    # spacing`` override one. Not part of is_active().
    group_row_spacing: float | None = None
    group_col_spacing: float | None = None
    # Image spacing: the gap between two adjacent image leaves (image↔image), per axis.
    # Read only from ``theme.elements``. None = 0 (images abut) by default. ``Image
    # spacing`` sets both; ``Image row/col spacing`` override one. Not part of is_active().
    image_row_spacing: float | None = None
    image_col_spacing: float | None = None
    # When 2+ same-level sections are grid'd into one row, merge_rows=True wraps
    # the whole row in a single background; False (default) gives each card its
    # own background. Behavior flag — not part of is_active().
    merge_rows: bool = False
    # A list level's `List card: yes`: the element card around a run of its items alone.
    list_card: bool = False

    def is_active(self) -> bool:
        """True when this section has anything to inset or paint."""
        return (
            self.padding.any()
            or bool(self.bg_colors)
            or self.bg_image is not None
            or self.gradient is not None
            or any(sh.paints() for sh in self.shadows)
            or (self.stroke_width > 0.0 and self.stroke_color is not None)
        )


@dataclasses.dataclass
class TableTheme:
    """Table drawing styles, populated from the ``## Tables`` block in THEME.md.

    ``table`` is the whole-table shell: its ``merge_rows`` flag switches between
    separated rows (each header/body row painted on its own) and merged mode
    (zero row gaps, one rounded background behind the whole table). Its
    ``row_spacing``/``col_spacing`` are the gaps between columns/rows.
    ``header``/``cells`` paint the header row and body rows; their ``padding``
    is the per-cell label padding and ``cells.bg_colors`` cycle across body
    rows (zebra striping). Text styles are None until configured so the
    renderer can fall back to the document defaults.
    """

    table: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    header: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    header_text: TextStyle | None = None
    cells: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    cells_text: TextStyle | None = None
    # Stacking-cards mode: when enabled and a table's minimum width does not
    # fit the available width, each body row renders as a vertical card whose
    # values are keyed by the header labels.
    stacking: bool = False
    # "title" = the row's first cell renders as the card title (no key label),
    # remaining cells as key/value pairs; "keys" = every cell gets a key label.
    card_layout: str = "title"
    # Key-label style for stacking-cards mode (distinct from header_text).
    keys_text: TextStyle | None = None
    # Gap between a key label and its value inside a card.
    key_spacing: float = 4.0

    def is_active(self) -> bool:
        """True when any table styling is configured in THEME.md."""
        return (
            self.table.is_active()
            or self.header.is_active()
            or self.cells.is_active()
            or self.header_text is not None
            or self.cells_text is not None
        )


@dataclasses.dataclass
class BarTheme:
    """One drawn progress-bar family (``## Datapoints`` → ``### Ratio Bars`` /
    ``### Of Bars`` / ``### Key Value Bars``).

    ``bar`` paints the filled portion with the shared background vocabulary.
    As with every background, ``corner_radius`` 0 means square.
    ``track`` paints the empty background behind it; its ``padding`` wraps the
    track around the bar thickness (the bar is inset by it on every side).
    """

    enabled: bool = True
    thickness: float = 10.0
    # Bar relative to its text (of/key-value bars): "above" | "below".
    position: str = "below"
    # Ratio text beside the bar (ratio/unit bars): "left" | "right".
    text_side: str = "right"
    # Key/value label visibility. Consumed only by Key Value Bars.
    show_key: bool = True
    show_value: bool = True
    track_enabled: bool = True
    bar: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    track: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    # The fill of a value below zero; None paints it in the bar's own colour.
    negative_color: int | None = None


@dataclasses.dataclass
class RingTheme:
    """Circular progress ring for unit ratios (``### Ring`` blocks).

    ``ring`` colors the value arc (first bg color / gradient), ``track`` the
    full-circle background arc. ``value_text``/``unit_text`` style the number
    and unit centered inside; None falls back to document text / labels.
    """

    thickness: float = 12.0
    diameter: float = 96.0
    # Gap between the centered value and unit leaves. Default 0 → they abut.
    spacing: float = 0.0
    ring: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    track: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    value_text: TextStyle | None = None
    unit_text: TextStyle | None = None


@dataclasses.dataclass
class DateChipTheme:
    """`Mon 15` / `Jun 15` chip (``### Dates`` / ``### Date Key`` /
    ``### Date Day``). ``chip`` is the outer card; key (weekday/month) and
    day number each get their own optional background + text style."""

    enabled: bool = True
    # "single" = one outer chip fill (``chip``); "split" = the chip is divided
    # into two stacked regions filled by ``key_bg`` (top) / ``day_bg`` (bottom),
    # sharing the outer rounded corners.
    fill: str = "single"
    # Gap between the key (weekday/month) and day-number leaves inside the chip.
    # Default 0 → they abut.
    spacing: float = 0.0
    chip: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    key_bg: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    day_bg: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    key_text: TextStyle | None = None
    day_text: TextStyle | None = None


@dataclasses.dataclass
class TaskControlsTheme:
    """List-scoped ``[ ]``/``[X]`` drawings under ``## Drawing elements``."""

    enabled: bool = True
    type: str = "checkbox"
    size: float | None = None
    padding: float = 4.0
    corner_radius: float | None = None
    space: float = 10.0
    checked_outer: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    checked_inner: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    unchecked_outer: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    unchecked_inner: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    # A glyph centred in each state's inner shape (``Symbol:`` / ``Symbol color:``
    # in its inner block); no symbol draws none, and no colour takes the outer fill.
    checked_symbol: str | None = None
    checked_symbol_color: int | None = None
    unchecked_symbol: str | None = None
    unchecked_symbol_color: int | None = None


@dataclasses.dataclass
class SliderTheme:
    """Interactive ``[65%]`` sliders under ``## Drawing elements``.

    Style chooses the handle vocabulary and the default track thickness:
    ``thick`` uses a short perpendicular drag bar in an 85px track; ``line``
    uses a 28px circle on a 10px track.  An authored thickness overrides the
    style default. Paint is carried by the same SectionStyle layers as bars.
    """

    enabled: bool = True
    style: str = "thick"  # "thick" | "line"
    axis: str = "horizontal"  # "horizontal" | "vertical"
    length: float = 240.0
    thickness: float | None = None
    corner_radius: float | None = None
    circle_diameter: float = 28.0
    drag_bar_length: float = 22.0
    drag_bar_thickness: float = 3.0
    drag_bar_gap: float = 5.0
    bar: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    track: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    handle: SectionStyle = dataclasses.field(default_factory=SectionStyle)


@dataclasses.dataclass
class CountTheme:
    """A count's round ➖/➕ buttons (``### Count Button`` under ``## Drawing
    elements``), one layer as a slider handle is. A ``button`` that paints
    nothing inherits the quieter button's paint; ``symbol_color`` None takes
    that paint's label colour."""

    button: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    symbol_color: int | None = None


@dataclasses.dataclass
class DatapointsTheme:
    """Drawn replacements from canonical ``## Drawing elements``.

    The former ``## Datapoints`` header remains a parser alias.

    ``unit_ratio_style`` picks how ratio-plus-unit datapoints render:
    "bar" (a ratio bar reusing ``ratio_bar``'s styling) or "ring".
    Every family defaults enabled — THEME.md opts out per family."""

    ratio_bar: BarTheme = dataclasses.field(default_factory=BarTheme)
    kv_bar: BarTheme = dataclasses.field(default_factory=BarTheme)
    unit_ratio_enabled: bool = True
    unit_ratio_style: str = "bar"  # "bar" | "ring"
    # Ratio text visibility shared by horizontal bars and rings. ``key`` is
    # either a K-V label (``Minutes``) or the trailing unit (``Kcal``/``g``);
    # ``total`` also applies to a bare ratio bar such as ``4/8``.
    unit_ratio_show_total: bool = True
    unit_ratio_show_key: bool = True
    ring: RingTheme = dataclasses.field(default_factory=RingTheme)
    date_chip: DateChipTheme = dataclasses.field(default_factory=DateChipTheme)
    task_controls: TaskControlsTheme = dataclasses.field(
        default_factory=TaskControlsTheme
    )
    sliders: SliderTheme = dataclasses.field(default_factory=SliderTheme)
    counts: CountTheme = dataclasses.field(default_factory=CountTheme)


@dataclasses.dataclass
class ChartGridTheme:
    """The scale and lines a vertical chart draws behind its bars
    (``### Chart Grid``). All off by default.

    ``ticks`` is about how many steps the scale is cut into; they land on
    round values, so the scale may stretch to the next one. The zero line of a
    chart holding a value below zero is always drawn, in this colour and width,
    and never dashed.
    """

    axis_labels: bool = False
    ticks: int = 4
    horizontal: bool = False
    vertical: bool = False
    color: int = 0xFFD0D0D0
    width: float = 1.0
    dash: list[float] = dataclasses.field(default_factory=list)
    text: TextStyle | None = None

    @property
    def scaled(self) -> bool:
        """Whether the chart is cut into ticks: something is drawn at them."""
        return self.axis_labels or self.horizontal


# `Value format:` under `## Charts`: bare (default), or where a declared unit goes.
VALUE_FORMATS = ("1", "1 unit", "1unit", "unit 1")


@dataclasses.dataclass
class LineChartTheme:
    """A value over time, ``Key: a → b → c``, drawn as a line (``### Line Chart``).

    On with no theme, like every display; ``Enabled: no`` turns it off. ``height`` is the line's area, tick
    labels below it extra; ``color`` None takes the first series colour.
    ``point_size`` is the diameter of the dot on each labelled point and the
    last one; 0 draws none. ``points`` says which points get one: "labelled"
    (each labelled point and the last) or "last" (each line's last only).
    ``group_height`` is the area of several lines on one axis; None takes
    ``height``. ``fill`` paints the area under each line, as a section's
    background keys do; its colours rotate across the lines of a group.
    """

    enabled: bool = True
    height: float = 48.0
    group_height: float | None = None
    width: float = 2.0
    color: int | None = None
    point_size: float = 6.0
    points: str = "labelled"
    fill: SectionStyle = dataclasses.field(default_factory=SectionStyle)


@dataclasses.dataclass
class ChartsTheme:
    """Bar charts for Key: value bullet runs in one unit (``## Charts``).

    ``mode`` is parsed for forward compatibility ("line" is accepted but the
    renderer falls back to bars until a line mode exists). ``bar``/``track``
    paint each bar and its background; ``series_colors`` cycle across series
    in multi-series charts (falling back to ``bar``'s fill for the first).
    """

    enabled: bool = True
    mode: str = "bar"  # "bar" | "line" (future)
    bar_thickness: float = 14.0
    bar_spacing: float = 8.0
    # "fixed" draws vertical bars at bar_thickness; "fill" widens them to share
    # the chart width, bar_spacing apart, with bar_thickness as their minimum.
    bar_width: str = "fixed"
    track_enabled: bool = True
    bar: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    track: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    series_colors: list[int] = dataclasses.field(default_factory=list)
    # The fill of a bar below zero; None paints it in its series colour.
    negative_color: int | None = None
    # "100": a percentage chart reads as progress against 100%; "peak": it
    # compares its rows against the largest, like every other unit.
    percent_scale: str = "100"
    # Where a declared unit shows on bare values, one of VALUE_FORMATS
    # (``value_format.with_unit``).
    value_format: str = "1"
    grid: ChartGridTheme = dataclasses.field(default_factory=ChartGridTheme)
    line: LineChartTheme = dataclasses.field(default_factory=LineChartTheme)
    label_text: TextStyle | None = None
    value_text: TextStyle | None = None


@dataclasses.dataclass(frozen=True)
class EmojiAxes:
    """`Emoji fill` / `Emoji grade` / `Emoji optical size`: where an icon font's
    FILL, GRAD and opsz axes are set for an element's emoji. ``None`` leaves an
    axis at the font's default; an optical size of ``"auto"`` is the size the
    glyph is drawn at."""

    fill: float | None = None
    grade: float | None = None
    optical_size: float | str | None = None

    def over(self, base: "EmojiAxes") -> "EmojiAxes":
        """These axes, each one unset taken from *base*."""
        mine, theirs = dataclasses.astuple(self), dataclasses.astuple(base)
        return EmojiAxes(*(a if a is not None else b for a, b in zip(mine, theirs)))

    def at(self, size: float) -> tuple[float | None, float | None, float | None]:
        """``(fill, grade, optical size)`` for a glyph drawn at *size*."""
        opsz = self.optical_size  # a str only as "auto", the one word it takes
        return self.fill, self.grade, size if isinstance(opsz, str) else opsz


@dataclasses.dataclass
class LinkStyle:
    """One button/link visual style.

    Every field is optional so THEME.md can leave a variant (Secondary/
    Tertiary/Pill) partially or entirely unset. ``None`` means "not
    configured" and is resolved against Primary's (always-concrete) values
    — see ``_resolve_link_style`` / ``LinksTheme.resolved``. There is no
    separate "emoji" style: a pure-emoji label instead forces *this same*
    variant's ``emoji_shape`` (circle/square) at render time.
    """

    corner_radius: float | None = None
    # Per-side padding between the pill edge and the label. ``Padding: N`` sets all
    # sides; ``Padding top|left|right|bottom: N`` overrides one.
    padding: "PaddingBox | None" = None
    fill_color: int | None = None
    text_style: TextStyle | None = None
    stroke_width: float | None = None
    stroke_color: int | None = None
    stroke_align: str | None = None  # see SectionStyle.stroke_align
    # The full lists behind ``fill_color`` / ``stroke_color`` — one THEME.md key
    # each, written inline for one color or as ``- #RRGGBB`` bullets for several.
    # The scalar above stays the first entry so every measurer, merge and paint
    # path is unchanged; only the rotation resolver reads these.
    fill_colors: list[int] = dataclasses.field(default_factory=list)
    stroke_colors: list[int] = dataclasses.field(default_factory=list)
    # Optional layers painted inside the button shape by the same background
    # painter as sections/cards. ``Fill color`` remains the solid base layer.
    bg_image: str | None = None
    gradient: GradientTheme | None = None
    shadows: list[ShadowSpec] = dataclasses.field(default_factory=list)
    # Shape forced ONLY when a link's label is pure emoji (otherwise this
    # variant always renders as its normal rect pill, using corner_radius as
    # configured). "circle" draws an oval; "square" forces a 1:1 aspect box
    # but keeps drawing a rounded rect at this same corner_radius (so a
    # small radius reads as a rounded square, not a sharp one).
    emoji_shape: str | None = None
    # Paint swapped in when the link is DISABLED (``~~[x](/y)~~`` — the ``~~``
    # is a state on the link, never a strikethrough rule). Only these three
    # change: geometry, padding and emoji shape stay the variant's own, so a
    # disabled button keeps its size and place in the layout. Each one unset
    # falls back to this variant's ordinary value; a variant with none of them
    # takes the default mute (``muted_color``), so the state is never invisible.
    disabled_fill_color: int | None = None
    disabled_text_color: int | None = None
    disabled_stroke_color: int | None = None
    # `Emoji gap`: the space between a leading or trailing emoji and the label's
    # words, in place of the spaces typed there. `Emoji weight`: the weight the
    # label's emoji draws in, resolved against the emoji font's family; `Emoji
    # fill` / `grade` / `optical size`: ``EmojiAxes``.
    emoji_gap: float | None = None
    emoji_weight: int | None = None
    emoji_axes: EmojiAxes = EmojiAxes()


@dataclasses.dataclass
class InlineLinkStyle:
    """A link left INSIDE a text run (``### Inline`` under ``## Links``).

    Not a button: these are the ``[label](url)`` links the grouper never peeled
    into their own LINK leaf, so they draw inside prose/headings like the
    ``bold``/``italic``/``strike`` span flags — same font, same size as the text
    around them. Only the paint changes: ``text_color`` (``None`` keeps the
    surrounding text's color) plus an optional underline.
    """

    text_color: int | None = None
    underline: bool = True


def _unpainted_link_style() -> "LinkStyle":
    """The base a theme that styles links starts from — unpainted.

    No fill and no stroke, with the ordinary body text color: under a theme's
    ``## Links`` block a link draws as plain text until that block asks for a
    background. A ``Text`` link always resolves against this; a button variant
    against Primary itself.
    """
    return LinkStyle(
        corner_radius=16.0,  # LINK_RADIUS
        padding=PaddingBox(top=10.0, left=10.0, right=10.0, bottom=10.0),
        fill_color=_TRANSPARENT,
        text_style=TextStyle(font_name=""),  # "" = the body family
        stroke_width=0.0,
        stroke_color=_TRANSPARENT,
        stroke_align="center",
        emoji_shape="circle",
    )


def _default_primary_link_style() -> "LinkStyle":
    """Primary as md2ui draws it while a theme leaves the Links family unstyled:
    a pill in the built-in greys, so a button reads as one with no theme too.
    A theme that styles links starts from ``_unpainted_link_style`` instead
    (``LinksTheme.take_over``)."""
    style = _unpainted_link_style()
    style.corner_radius = 999.0
    style.padding = PaddingBox(top=10.0, left=16.0, right=16.0, bottom=10.0)
    style.fill_color = GREY_INK
    style.text_style = TextStyle(font_name="", color=GREY_WHITE)
    return style


def _default_secondary_link_style() -> "LinkStyle":
    """``*…*`` while the theme leaves links unstyled: white, an ink outline."""
    return LinkStyle(
        fill_color=GREY_WHITE,
        stroke_width=1.5,
        stroke_color=GREY_INK,
        text_style=TextStyle(font_name="", color=GREY_INK),
    )


def _default_tertiary_link_style() -> "LinkStyle":
    """``**…**`` while the theme leaves links unstyled: a light-grey pill."""
    return LinkStyle(
        fill_color=GREY_TRACK, text_style=TextStyle(font_name="", color=GREY_INK)
    )


# The button variants that inherit from Primary, by wrapper: ``*`` ``**``
# ``***`` the asterisk ladder, ``_`` ``__`` ``___`` the small one
# (``grouper_types._LINK_VARIANT_WRAPPERS``). ``text`` is not among them.
LINK_BUTTON_VARIANTS = (
    "secondary",
    "tertiary",
    "quaternary",
    "quinary",
    "senary",
    "septenary",
)


@dataclasses.dataclass
class LinksTheme:
    """The seven button styles — primary and ``LINK_BUTTON_VARIANTS``, one per
    markdown wrapping — the ``text`` link, and ``inline``.

    ``text`` is the backtick-label link (``[`x`](/y)``): a plain text link with
    its own shape (``### Text``) and text style (``Links Text``), never a button
    variant. It inherits nothing from Primary; an unstated key takes the built-in
    default, so with no Text blocks it draws as bare plain text. ``quinary`` is
    the ``_[x](/y)`` small button, not an alias of ``text``.

    ``primary`` is always fully concrete. The others start as all-``None``
    overrides — call ``resolved(variant)`` for a concrete ``LinkStyle``. A button
    variant's missing block or field renders identically to Primary.

    ``inline`` is NOT one of those button variants and never merges onto
    Primary — it styles links drawn inside a text run (see ``InlineLinkStyle``).

    ``segmented`` (``Segmented: yes``) draws a choice run as one segmented
    control rather than separate pills (ADR-405, ``render_segmented``).
    """

    primary: LinkStyle = dataclasses.field(default_factory=_default_primary_link_style)
    secondary: LinkStyle = dataclasses.field(
        default_factory=_default_secondary_link_style
    )
    tertiary: LinkStyle = dataclasses.field(
        default_factory=_default_tertiary_link_style
    )
    quaternary: LinkStyle = dataclasses.field(default_factory=LinkStyle)
    quinary: LinkStyle = dataclasses.field(default_factory=LinkStyle)
    senary: LinkStyle = dataclasses.field(default_factory=LinkStyle)
    septenary: LinkStyle = dataclasses.field(default_factory=LinkStyle)
    text: LinkStyle = dataclasses.field(default_factory=LinkStyle)
    inline: InlineLinkStyle = dataclasses.field(default_factory=InlineLinkStyle)
    segmented: bool = False
    # Whether THEME.md has taken the Links family over (``take_over``).
    themed: bool = False

    def take_over(self) -> None:
        """A theme styles links: drop the built-in grey buttons for the
        unpainted base it builds on, once, before any of its own keys apply,
        so a theme's links resolve as they always have."""
        if not self.themed:
            self.themed = True
            self.primary = _unpainted_link_style()
            self.secondary = LinkStyle()
            self.tertiary = LinkStyle()

    def resolved(self, variant: str) -> LinkStyle:
        """Concrete LinkStyle for *variant*: a button onto Primary, Text onto defaults.

        Resolved lazily on every call (cheap — a handful of ``is not None``
        checks) rather than cached, so it's always correct regardless of
        when it's called relative to THEME.md parsing finishing, and works
        equally well for a bare ``Theme()`` default (bypassing
        ``parse_theme``) as for a fully parsed one.
        """
        if variant != "text" and variant not in LINK_BUTTON_VARIANTS:
            # "primary", "inline" (a text-run style, not a button) or anything
            # unrecognized → Primary's concrete style.
            return self.primary
        override = getattr(self, variant, None)
        if override is None:
            return self.primary
        base = _unpainted_link_style() if variant == "text" else self.primary
        return _resolve_link_style(override, base)


def _resolve_text_style(
    override: "TextStyle | None", base: "TextStyle | None"
) -> "TextStyle | None":
    """Merge an optional variant TextStyle onto Primary's, whole-object.

    A variant's ``## Text Styles`` subsection (e.g. ``Links Secondary``) is
    only materialized into a ``TextStyle`` the first time one of its bullet
    lines is parsed (see ``_apply_text_style_bullet``); ``None`` means that
    subsection was never seen at all, so Primary's TextStyle applies as-is.
    """
    return override if override is not None else base


def _resolve_link_style(override: "LinkStyle", base: "LinkStyle") -> "LinkStyle":
    """Merge a variant's THEME.md overrides onto Primary's concrete values.

    Called once per variant at the end of ``parse_theme`` — never at render
    time. Any field left ``None`` in ``override`` (i.e. never set under that
    variant's ``### `` block in THEME.md) falls back to Primary's value.
    """
    return LinkStyle(
        corner_radius=(
            override.corner_radius
            if override.corner_radius is not None
            else base.corner_radius
        ),
        padding=override.padding if override.padding is not None else base.padding,
        fill_color=(
            override.fill_color if override.fill_color is not None else base.fill_color
        ),
        text_style=_resolve_text_style(override.text_style, base.text_style),
        stroke_width=(
            override.stroke_width
            if override.stroke_width is not None
            else base.stroke_width
        ),
        stroke_align=override.stroke_align or base.stroke_align,
        stroke_color=(
            override.stroke_color
            if override.stroke_color is not None
            else base.stroke_color
        ),
        # A variant that lists no colors of its own inherits Primary's whole
        # list, so rotation configured once on Primary reaches every variant
        # that only overrides geometry.
        fill_colors=list(override.fill_colors or base.fill_colors),
        stroke_colors=list(override.stroke_colors or base.stroke_colors),
        bg_image=override.bg_image if override.bg_image is not None else base.bg_image,
        gradient=(
            override.gradient if override.gradient is not None else base.gradient
        ),
        # Like chip and emoji variants: a kind of shadow the variant declares
        # replaces Primary's of that kind; one it declares none of is inherited.
        shadows=inherit_shadows(base.shadows, override.shadows),
        emoji_shape=(
            override.emoji_shape
            if override.emoji_shape is not None
            else base.emoji_shape
        ),
        disabled_fill_color=(
            override.disabled_fill_color
            if override.disabled_fill_color is not None
            else base.disabled_fill_color
        ),
        disabled_text_color=(
            override.disabled_text_color
            if override.disabled_text_color is not None
            else base.disabled_text_color
        ),
        disabled_stroke_color=(
            override.disabled_stroke_color
            if override.disabled_stroke_color is not None
            else base.disabled_stroke_color
        ),
        emoji_gap=(
            override.emoji_gap if override.emoji_gap is not None else base.emoji_gap
        ),
        emoji_weight=override.emoji_weight or base.emoji_weight,
        emoji_axes=override.emoji_axes.over(base.emoji_axes),
    )


@dataclasses.dataclass
class EmojiBadgeStyle:
    """Full "badge" treatment for Primary emojis (heading + alone kinds).

    ``icon_size`` is the glyph size (independent of any surrounding text size).
    ``icon_colors`` is a color array cycled across sibling emojis (empty ⇒ fall
    back to the text color). ``fill`` reuses the same ``SectionStyle`` fill
    vocabulary as root/headings/cards (``bg_colors``/``gradient``/
    ``corner_radius``/``stroke_*``/``bg_image``/``padding``) — its ``padding`` is
    the gap between glyph and badge edge. ``shape`` (``circle``/``square``)
    forces a 1:1 box, honored ONLY when ``fill.is_active()`` (a bare glyph with
    no fill is never shaped).
    """

    icon_size: float = 20.0
    icon_colors: list[int] = dataclasses.field(default_factory=list)
    fill: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    shape: str | None = None
    # The muted badge's paint (``~~⭐~~``), named after this block's own
    # keys: ``Disabled background color`` / ``icon color`` / ``stroke color``.
    disabled_bg_color: int | None = None
    disabled_icon_color: int | None = None
    disabled_stroke_color: int | None = None
    # `Emoji weight`: the glyph's weight in the emoji font's family; None keeps
    # the font as loaded. `Emoji fill` / `grade` / `optical size`: ``EmojiAxes``.
    emoji_weight: int | None = None
    emoji_axes: EmojiAxes = EmojiAxes()
    # Marks the style ``muted`` hands a muted badge, so its background image is
    # painted faded where the picture is read (``render_placeholders``).
    is_muted: bool = False

    def muted(self, ink: int | None) -> "EmojiBadgeStyle":
        """This badge in its muted state: colours, shadows and background image
        faded, so it keeps its size, shape and place. *ink* is the glyph's
        colour when the badge states no icon colour of its own."""
        stated = any(
            c is not None
            for c in (
                self.disabled_bg_color,
                self.disabled_icon_color,
                self.disabled_stroke_color,
            )
        )
        f = self.fill
        bg = muted_color(
            f.bg_colors[0] if f.bg_colors else None, self.disabled_bg_color, stated
        )
        stroke = muted_color(
            f.stroke_colors[0] if f.stroke_colors else f.stroke_color,
            self.disabled_stroke_color,
            stated,
        )
        icon = muted_color(
            self.icon_colors[0] if self.icon_colors else ink,
            self.disabled_icon_color,
            stated,
        )
        fill = dataclasses.replace(
            f,
            bg_colors=[bg] if bg is not None else [],
            stroke_colors=[],
            stroke_color=stroke,
            gradient=muted_gradient(f.gradient, stated),
            shadows=muted_shadows(f.shadows),
        )
        return dataclasses.replace(
            self,
            fill=fill,
            icon_colors=[icon] if icon is not None else [],
            is_muted=True,
        )


@dataclasses.dataclass
class EmojiTextStyle:
    """Lightweight style for text-context emojis (Text/Link/Inline blocks).

    No background/padding/shape — the emoji reads as inline text. ``color`` (a
    single override, ``None`` ⇒ keep the surrounding text color) and
    ``font_path`` (a filled emoji font, ``None`` ⇒ the default emoji font).
    ``fixed_colors`` maps a specific emoji glyph → a forced color, overriding
    ``color`` for that glyph.
    """

    color: int | None = None
    font_path: str | None = None
    fixed_colors: dict[str, int] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class EmojisTheme:
    # Default/badge emoji font (``## Emoji styles`` top-level ``Font:``).
    font_path: str | None = None
    # ### Primary — heading + alone emoji badges.
    primary: EmojiBadgeStyle = dataclasses.field(default_factory=EmojiBadgeStyle)
    # ### Text — peeled emoji leaves + unsliced emojis in plain prose.
    text: EmojiTextStyle = dataclasses.field(default_factory=EmojiTextStyle)
    # ### Link — unsliced emojis inside link labels.
    link: EmojiTextStyle = dataclasses.field(default_factory=EmojiTextStyle)
    # ### Inline — unsliced emojis inside inline code.
    inline: EmojiTextStyle = dataclasses.field(default_factory=EmojiTextStyle)
    # Wrapper VARIANTS of the badge — a second axis from the context blocks
    # above. `*🔎*` Secondary | `**🔎**` Tertiary | `***🔎***` Quaternary, by
    # wrapper LENGTH (deliberately not the link order; see markdown_grouper's
    # _ELEMENT_VARIANT_WRAPPERS). Each is built by replaying its THEME.md block
    # onto a copy of ``primary``, so an unstated key inherits Primary's value
    # and an entirely absent block is ``None`` ⇒ Primary.
    secondary: EmojiBadgeStyle | None = None
    tertiary: EmojiBadgeStyle | None = None
    quaternary: EmojiBadgeStyle | None = None

    def resolved(
        self, variant: str | None, nd: dict | None = None, ink: int | None = None
    ) -> EmojiBadgeStyle:
        """The concrete badge style for *variant* (``None`` ⇒ Primary).

        With the leaf *nd* being drawn, its ``element_muted`` state picks the
        muted paint (``EmojiBadgeStyle.muted``, glyph *ink* as its fallback).
        Measurement passes no leaf: the state never changes a badge's size.
        """
        style = self.primary
        if variant:
            override = getattr(self, variant, None)
            if isinstance(override, EmojiBadgeStyle):
                style = override
        return style.muted(ink) if nd and nd.get("element_muted") else style


@dataclasses.dataclass
class InlineCodeTheme:
    corner_radius: float = 4.0
    # Per-side padding between the code background and the code text. ``Padding: N``
    # sets all sides; ``Padding top|left|right|bottom: N`` overrides one.
    padding: PaddingBox = dataclasses.field(
        default_factory=lambda: PaddingBox(top=2.0, left=2.0, right=2.0, bottom=2.0)
    )
    fill_color: int = dataclasses.field(
        default_factory=lambda: skia.ColorSetARGB(255, 230, 230, 230)
    )
    stroke_color: int = dataclasses.field(default_factory=lambda: _TRANSPARENT)
    stroke_width: float = 0.0
    stroke_align: str = "center"  # see SectionStyle.stroke_align
    # The full lists behind ``fill_color`` / ``stroke_color`` (see LinkStyle):
    # one THEME.md key, inline for one color or ``- #RRGGBB`` bullets for many.
    fill_colors: list[int] = dataclasses.field(default_factory=list)
    stroke_colors: list[int] = dataclasses.field(default_factory=list)
    # Optional layers painted inside the chip shape by the shared background
    # painter. ``fill_color`` remains the solid base layer.
    bg_image: str | None = None
    gradient: GradientTheme | None = None
    shadows: list[ShadowSpec] = dataclasses.field(default_factory=list)
    # `Emoji weight`: the weight an emoji in the chip draws in, resolved against
    # the emoji font's family; None keeps the font as loaded. `Emoji fill` /
    # `grade` / `optical size`: ``EmojiAxes``.
    emoji_weight: int | None = None
    emoji_axes: EmojiAxes = EmojiAxes()
    # Inline code's own TEXT style (font/size/weight/color), configured under
    # ## Text Styles as an "Inline Code" entry — like Text/Labels/Links. ``None``
    # until that entry appears; ``effective_text_style`` then defaults to the body
    # ``Text`` font at a fixed, slightly-smaller size (14). The default face is
    # the body font (resolved in layout_render.main), NOT a monospace one.
    text_style: "TextStyle | None" = None
    # The muted chip's paint (`` ~~`x`~~ ``), the keys ``## Links``
    # names. ``muted`` marks the style ``resolved`` hands a muted chip, so its
    # label is muted where its colour is read (``effective_text_style``), and
    # its background image where the picture is (``render_placeholders``).
    disabled_fill_color: int | None = None
    disabled_text_color: int | None = None
    disabled_stroke_color: int | None = None
    muted: bool = False
    # Wrapper variants; see ``resolved``. ``None`` ⇒ inherit this style.
    secondary: "InlineCodeTheme | None" = None
    tertiary: "InlineCodeTheme | None" = None
    quaternary: "InlineCodeTheme | None" = None
    # The chip-only underscore family: _`x`_ / __`x`__ / ___`x`___.
    quinary: "InlineCodeTheme | None" = None
    senary: "InlineCodeTheme | None" = None
    septenary: "InlineCodeTheme | None" = None

    def effective_text_style(self, body: "TextStyle") -> "TextStyle":
        """The inline-code text style to render with.

        If configured under ``## Text Styles > Inline Code`` use it verbatim
        (the user fully specifies it, like the other text styles); otherwise
        default to the body font/weight/color at a fixed 14px (slightly smaller
        than the 16px body).
        """
        ts = self.text_style
        if ts is None:
            ts = TextStyle(
                font_name=body.font_name,
                font_size=14.0,
                font_weight=body.font_weight,
                color=body.color,
            )
        if not self.muted:
            return ts
        color = muted_color(ts.color, self.disabled_text_color, self._stated())
        return dataclasses.replace(ts, color=color)

    def _stated(self) -> bool:
        """Whether the theme gave this chip any ``Disabled …`` colour."""
        return any(
            c is not None
            for c in (
                self.disabled_fill_color,
                self.disabled_text_color,
                self.disabled_stroke_color,
            )
        )

    def resolved(
        self, variant: str | None, nd: dict | None = None
    ) -> "InlineCodeTheme":
        """The concrete chip style for *variant* (``None`` ⇒ this one).

        A chip's wrapper picks a variant by LENGTH — `` *`x`* `` Secondary,
        `` **`x`** `` Tertiary, `` ***`x`*** `` Quaternary; underscores are their
        own family — `` _`x`_ `` Quinary, `` __`x`__ `` Senary, `` ___`x`___ ``
        Septenary. Each variant block is
        replayed onto a copy of the base (``### Primary``, or the flat
        no-subsection block), so an unstated key inherits and an absent block
        is ``None`` ⇒ the base.

        With the leaf *nd* being drawn, its ``element_muted`` state swaps in the
        muted paint (``muted_color``): colours, with the rotation lists emptied
        so a cycle cannot paint over the state, and the shadows and background
        image faded. Measurement passes no leaf, so a muted chip is exactly as
        big as an enabled one.
        """
        style = self
        if variant:
            override = getattr(self, variant, None)
            if isinstance(override, InlineCodeTheme):
                style = override
        if not (nd and nd.get("element_muted")):
            return style
        stated = style._stated()
        return dataclasses.replace(
            style,
            fill_color=muted_color(style.fill_color, style.disabled_fill_color, stated),
            stroke_color=muted_color(
                style.stroke_color, style.disabled_stroke_color, stated
            ),
            fill_colors=[],
            stroke_colors=[],
            gradient=muted_gradient(style.gradient, stated),
            shadows=muted_shadows(style.shadows),
            muted=True,
        )


@dataclasses.dataclass
class CodeBlockTheme:
    """Paint and typography for fenced and indented Markdown code blocks."""

    text_style: TextStyle = dataclasses.field(
        default_factory=lambda: TextStyle(font_name="monospace", font_size=13.0)
    )
    syntax_style: str = "bw"  # grayscale; a theme names a coloured Pygments style
    background_color: int = dataclasses.field(
        default_factory=lambda: skia.ColorSetARGB(255, 245, 245, 245)
    )
    corner_radius: float = 8.0
    padding: PaddingBox = dataclasses.field(
        default_factory=lambda: PaddingBox(top=12.0, left=12.0, right=12.0, bottom=12.0)
    )
    line_spacing: float = 4.0
    # The most a block asks the page for: a longer line clips instead of widening
    # it, and fades into the background at the cut unless ``fade`` is off.
    min_width: float = 320.0
    # The tallest a block draws, in whole lines; ``None`` shows every line.
    max_lines: int | None = 20
    fade: bool = True
    # ``### Copy Button``: the icon (``None`` removes the button and its strip),
    # its size, and a button variant's own style, painted by the same layers.
    copy_icon: str | None = "📋"
    copy_icon_size: float = 14.0
    copy_button: "LinkStyle" = dataclasses.field(
        default_factory=lambda: LinkStyle(
            corner_radius=6.0,
            padding=PaddingBox(top=4.0, left=4.0, right=4.0, bottom=4.0),
            fill_color=skia.ColorSetARGB(48, 128, 128, 128),
        )
    )


@dataclasses.dataclass
class ContentWeightTheme:
    """Defaults for the ``content_weight`` render hint.

    ``first``/``second`` scale a node's base font size up to emphasize it;
    ``less`` scales it down and recolors it with ``less_color``. Only ``less``
    changes color — ``first``/``second`` keep the node's normal color.
    """

    first_scale: float = 1.30
    second_scale: float = 1.15
    less_scale: float = 0.85
    less_color: int = dataclasses.field(default_factory=lambda: _MUTED_TEXT_COLOR)


@dataclasses.dataclass
class HorizontalRuleTheme:
    stroke_color: int = dataclasses.field(
        default_factory=lambda: skia.ColorSetARGB(255, 192, 192, 192)
    )
    stroke_width: float = 1.0


@dataclasses.dataclass
class HorizontalRulePatch:
    """Only the horizontal-rule paint properties authored at one scope."""

    stroke_color: int | None = None
    stroke_width: float | None = None

    def apply(self, base: HorizontalRuleTheme) -> HorizontalRuleTheme:
        return dataclasses.replace(
            base,
            stroke_color=(
                self.stroke_color
                if self.stroke_color is not None
                else base.stroke_color
            ),
            stroke_width=(
                self.stroke_width
                if self.stroke_width is not None
                else base.stroke_width
            ),
        )


@dataclasses.dataclass
class SeparatorsTheme:
    """Whether a consumed ROW separator is drawn back between the pieces.

    The split eats ` - ` / ` | ` and keeps only the segments, so these are pure
    display: the grouper records WHICH character split the line
    (``separator_char``) and the layout generator puts a cell back in the gap
    when the flag here is on. A dot is text since ADR-205, drawn as written.
    """

    dash: bool = False
    bar: bool = False


@dataclasses.dataclass
class VerticalRuleTheme:
    """The vertical twin of ``HorizontalRuleTheme``: ` | ` painted as a line.

    ``draw`` WINS over ``SeparatorsTheme.bar`` — "Bar: hide" + "Draw: yes" is
    the useful combination (no pipe character, just the line), so the rule is
    not gated on the glyph flag.
    """

    draw: bool = False
    stroke_color: int = dataclasses.field(
        default_factory=lambda: skia.ColorSetARGB(255, 192, 192, 192)
    )
    stroke_width: float = 1.0


@dataclasses.dataclass
class BulletedListStyle:
    """Opt-in marker for every bulleted-list item.

    ``shape`` (``circle``/``square``) draws a ``size``×``size`` filled glyph
    tinted by ``color``; set ``emoji`` instead to draw an emoji glyph tinted by
    the same color. ``space`` is the gap between the marker and the item
    content. ``aside`` chooses left gutter versus above-content placement;
    ``alignment`` positions an aside marker against the whole item body.
    Inactive (no shape and no emoji) ⇒ list items keep the plain ``•`` text
    bullet.
    """

    shape: str | None = None  # "circle" | "square" | None
    size: float = 8.0
    color: int | None = None  # tint for the shape (from "Color:")
    colors: list[int] = dataclasses.field(default_factory=list)
    emoji: str | None = None
    space: float = 10.0
    aside: bool = True
    alignment: str = "top"

    def is_active(self) -> bool:
        return self.shape is not None or self.emoji is not None


@dataclasses.dataclass
class NumberedListStyle:
    """Opt-in marker drawing each ordered item's running ordinal.

    ``text_style`` styles the number (font name/size/weight/color); ``None``
    means the block was never configured (marker off). ``number_format`` is a
    ``str.format`` template with an ``{n}`` placeholder — ``"{n}"`` prints a bare
    number (default), ``"{n}."``/``"{n})"``/``"({n})"`` add delimiters.
    ``space`` is the gap to the item content. ``aside`` chooses left gutter
    versus above-content placement; ``alignment`` positions an aside marker
    against the whole item body.
    """

    text_style: "TextStyle | None" = None
    number_format: str = "{n}"
    space: float = 10.0
    aside: bool = True
    alignment: str = "top"

    def is_active(self) -> bool:
        return self.text_style is not None


@dataclasses.dataclass
class QuoteStyle:
    """Opt-in single-level blockquote (``>``) marker.

    Two mutually-exclusive modes: BAR (``bar_width`` + ``bar_color`` → a thick
    vertical rule spanning the quote height) and CHAR (``quote_char`` styled by
    ``char_text_style``, the default style unless a font key is set). Without
    ``aside``, a bar is horizontal, ``bar_length`` long. Bar wins over char.
    ``space`` is the gap between marker and quote body; ``alignment`` positions
    an aside char against the body (an aside bar always stretches). Inactive ⇒
    blockquotes render with no marker (body only).
    """

    bar_width: float = 0.0
    # Length of a horizontal bar when the marker is stacked above the quote.
    bar_length: float = 50.0
    bar_color: int | None = None
    bar_colors: list[int] = dataclasses.field(default_factory=list)
    quote_char: str | None = None
    char_text_style: "TextStyle" = dataclasses.field(default_factory=TextStyle)
    space: float = 12.0
    aside: bool = True
    alignment: str = "top"

    def is_bar(self) -> bool:
        return self.bar_width > 0.0 and self.bar_color is not None

    def is_active(self) -> bool:
        return self.is_bar() or self.quote_char is not None


@dataclasses.dataclass
class FixedColors:
    """Colors that carry MEANING, and so outrank rotation and replacement.

    A ❤️ is red because red is what it means; a 📉 is amber because the number
    fell. Rotation deals colors out and replacement fixes the ones that land
    badly — a pin is neither, and survives both. The single exception is
    invisibility: a pin exactly equal to the background behind it is dropped, so
    a red 🔻 on the red card a rotation just dealt does not vanish.

    ``emoji`` maps a glyph to ``(color, scope)``. Scope is how far the color reaches:
    ``""`` the glyph only, ``"datapoints"`` also the datapoint leaves beside it,
    ``"line"`` the whole run it sits in, or the run's pieces by kind (``"chips text"``:
    ``text``, ``emojis``, ``buttons``, ``chips``); its words add up. ``pill_*`` matches
    chip labels and ``button_*`` button labels, exact or containing the key; each maps
    to a ``{role: color}`` dict using the same text/fill/stroke role names as
    ``## Color Replacements``. ``datapoints`` is keyed by detected type, plus
    ``"change up"`` / ``"change down"`` for a signed value.
    """

    emoji: dict[str, tuple[int, str]] = dataclasses.field(default_factory=dict)
    emoji_bg: dict[str, int] = dataclasses.field(default_factory=dict)
    pill_exact: dict[str, dict[str, int]] = dataclasses.field(default_factory=dict)
    pill_contains: dict[str, dict[str, int]] = dataclasses.field(default_factory=dict)
    button_exact: dict[str, dict[str, int]] = dataclasses.field(default_factory=dict)
    button_contains: dict[str, dict[str, int]] = dataclasses.field(default_factory=dict)
    datapoints: dict[str, int] = dataclasses.field(default_factory=dict)

    def is_active(self) -> bool:
        return bool(
            self.emoji
            or self.emoji_bg
            or self.pill_exact
            or self.pill_contains
            or self.button_exact
            or self.button_contains
            or self.datapoints
        )


@dataclasses.dataclass
class Theme:
    name: str = ""
    root: RootTheme = dataclasses.field(default_factory=RootTheme)
    # Bento (mosaic) targeting; see BentoTheme. Inert unless root.layout is
    # "bento" (or the CLI/interactive override forces the mode on).
    bento: BentoTheme = dataclasses.field(default_factory=BentoTheme)
    # Global card (element) padding wrapping glued content groups, and its row/col
    # spacing = the gap between leaves inside an end-group. One style for all
    # cards, holding layout keys only: a card is never painted (a box comes from
    # a heading style), so the parser drops every paint key from ``### Elements``.
    elements: SectionStyle = dataclasses.field(
        default_factory=lambda: SectionStyle(row_spacing=8.0, col_spacing=8.0)
    )
    # Cards whose background is a photo (``![ ## Title … ](hero.png)``). Its own
    # block so a photo card can carry a different radius, padding or overlay
    # from an ordinary element card; when the block is absent it falls back to
    # ``elements``, which insets the card and paints nothing but its photo.
    image_cards: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    # Per-item structural surfaces, independent of marker styling.
    unordered_lists: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    task_lists: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    numbered_lists: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    quotes: SectionStyle = dataclasses.field(default_factory=SectionStyle)
    # Heading levels 1–6; missing levels fall back to HEADING_SIZES/HEADING_COLORS
    headings: dict[int, TextStyle] = dataclasses.field(default_factory=dict)
    # Per-heading-level section backgrounds (levels 1–6); missing/empty levels
    # paint nothing. Populated from the ## Sections block in THEME.md.
    sections: dict[int, SectionStyle] = dataclasses.field(default_factory=dict)
    # Heading-section styles selected by a trailing Markdown ``{#kebab-name-N}``
    # id. The final numeric component is an instance id; the remaining key
    # selects one of these. By default each is a complete, standalone style.
    fixed_sections: dict[str, SectionStyle] = dataclasses.field(default_factory=dict)
    # ``Mode: override`` fixed styles, resolved per heading level: the fixed
    # block's own keys replayed onto a copy of that ``### Heading N`` style.
    fixed_section_levels: dict[tuple[str, int], SectionStyle] = dataclasses.field(
        default_factory=dict
    )
    text: TextStyle = dataclasses.field(default_factory=TextStyle)
    labels: TextStyle = dataclasses.field(
        default_factory=lambda: TextStyle(font_size=11.0)
    )
    # ``Key`` / ``Value`` under ``## Text Styles``: the two sides of a display's
    # `Key: value` pair (ADR-205), one decision for the whole document. Unset
    # means both are drawn in ``text``.
    key_style: TextStyle | None = None
    value_style: TextStyle | None = None
    # ---- Authored display tiers (## Text Styles) --------------------------
    # Set by wrapping a whole line — or a whole ``|``/``-`` segment — in
    # underscores: ``_x_`` → muted, ``__x__`` → lead, ``___x___`` → display.
    # Underscores are exact CommonMark synonyms for asterisks, so the markdown
    # still reads correctly (italic / bold / bold-italic) in a plain editor.
    # Sizes default off the body style so omitting a block still renders.
    muted: TextStyle | None = None
    lead: TextStyle | None = None
    display: TextStyle | None = None
    # Local overrides declared below a level in ``## Styling & Spacing``.
    # First key: structural scope (root, heading:2, fixed:featured,
    # image_cards, unordered_lists, task_lists, numbered_lists, quotes).
    # Second key: role (text, muted, lead, display, key, value).
    # Each patch contains only explicitly authored properties, allowing the
    # renderer to cascade Root -> heading/fixed -> structural surface.
    text_style_overrides: dict[str, dict[str, TextStylePatch]] = dataclasses.field(
        default_factory=dict
    )
    links: LinksTheme = dataclasses.field(default_factory=LinksTheme)
    emojis: EmojisTheme = dataclasses.field(default_factory=EmojisTheme)
    # Horizontal-rule paint has the same structural cascade as local text
    # roles, with an optional patch containing only the authored properties.
    horizontal_rule: HorizontalRuleTheme = dataclasses.field(
        default_factory=HorizontalRuleTheme
    )
    horizontal_rule_overrides: dict[str, HorizontalRulePatch] = dataclasses.field(
        default_factory=dict
    )
    separators: SeparatorsTheme = dataclasses.field(default_factory=SeparatorsTheme)
    vertical_rule: VerticalRuleTheme = dataclasses.field(
        default_factory=VerticalRuleTheme
    )
    inline_code: InlineCodeTheme = dataclasses.field(default_factory=InlineCodeTheme)
    code_blocks: CodeBlockTheme = dataclasses.field(default_factory=CodeBlockTheme)
    content_weight: ContentWeightTheme = dataclasses.field(
        default_factory=ContentWeightTheme
    )
    # Table drawing styles (## Tables). Inactive by default: tables keep the
    # generic card wrap until THEME.md configures them.
    tables: TableTheme = dataclasses.field(default_factory=TableTheme)
    # Drawn replacements (## Drawing elements; legacy ## Datapoints) and
    # Key: value bar
    # charts (## Charts). Enabled by default with built-in styling; THEME.md
    # opts out per family (`Enabled: no`) or restyles them.
    datapoints: DatapointsTheme = dataclasses.field(default_factory=DatapointsTheme)
    charts: ChartsTheme = dataclasses.field(default_factory=ChartsTheme)
    # Per-background color swaps (## Color Replacements), three keys deep:
    #   background -> role -> color to replace -> replacement
    # The background is an ARGB int, or the string "image" for a photo-backed
    # card. The role is "text" | "fill" | "stroke" — three independent channels,
    # so a card that only recolors text never blocks a stroke rule declared
    # further out. The innermost key is the color to replace, or None for
    # "every color this background's role does not name". Empty (the default) =
    # the feature is off and everything keeps the color its style gives it.
    #
    # This is keyed on the COLOR rather than on the element it belongs to, so a
    # legibility fix is one entry rather than one edit per block: two elements
    # that share a color share a role and flip together.
    # Meaning-bearing pins (## Fixed colors). Outrank rotation and replacement.
    fixed: FixedColors = dataclasses.field(default_factory=FixedColors)
    # Named image placeholders (## Images → ### Placeholders), by the name an image
    # writes in `?md2ui.placeholder=` (theme_placeholders, ADR-406).
    image_placeholders: dict[str, ImagePlaceholder] = dataclasses.field(
        default_factory=dict
    )
    # `#### Loading` / `Broken` / `Missing` under ### Placeholders: md2ui's own
    # placeholders, restyled by state, for every image that names none.
    image_placeholder_defaults: dict[str, ImagePlaceholder] = dataclasses.field(
        default_factory=dict
    )
    color_replacements: dict[int | str, dict[str, dict[int | None, int]]] = (
        dataclasses.field(default_factory=dict)
    )
    font_paths: list[str] = dataclasses.field(default_factory=list)
