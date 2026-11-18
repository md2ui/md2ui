"""The pipeline, start to end: one Markdown document in, a placed scene out.

Shared by the two shells, which differ in who they serve and in nothing else:

* ``md2ui.app`` — the user's window. It loops, watches the document, reloads.
* ``md2ui.main`` — the LLM's CLI. It runs once, writes one file, and exits.

Both need the same sequence — theme, typefaces, grouping, layout, placement —
and a sequence written out twice drifts, which is how a screenshot comes to
disagree with the window it claims to show. So it is written here once
and neither shell re-derives a step of it.

The grouper's tree reaches the generator IN MEMORY, never through a file — see
``prepare``. Nothing here opens a window or watches a file; the import contracts
in ``pyproject.toml`` forbid this module from importing ``md2ui.app``.
"""

from __future__ import annotations

import math
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import skia

from md2ui.pipeline.grouper_split_criteria import SplitCriteria
from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.grouper_memo import MemoDetector, MemoSplitCriteria
from md2ui.pipeline import layout_auto, render_slots
from md2ui.pipeline.generator_units import document_min_width
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_render import (
    _content_width,
    draw_scene,
    load_grouping_ast_node,
    load_node_index,
    make_block_width_measurer,
    make_layout_measurer,
    make_line_width_measurer,
    make_marker_measurer,
    make_width_measurer,
)
from md2ui.pipeline.markdown_grouper import MarkdownGrouper, MarkdownGroupNode
from md2ui.pipeline.render_backgrounds import bake_list_cards
from md2ui.pipeline.render_list_surfaces import bake_list_run_cards, bake_merged_lists
from md2ui.pipeline.render_metrics import bake_card_ratios
from md2ui.pipeline.render_code_blocks import code_block_scrollables
from md2ui.pipeline.render_measure import height_memo, natural_height
from md2ui.pipeline.render_actions import build_regions
from md2ui.pipeline.render_picture import record_document
from md2ui.pipeline.render_place import (
    bake_image_bleed,
    bake_merged_row_cards,
    bake_render_cascade,
    place_boxes,
)
from md2ui.pipeline.render_settings import VIEW
from md2ui.pipeline.render_style import (
    FontSet,
    _TABLE_TYPEFACES,
    _load_emoji_typeface,
    set_inline_code_size,
)
from md2ui.pipeline.render_text_scopes import emoji_paths, load_theme_font_context
from md2ui.pipeline.theme import Theme, parse_theme
from md2ui.pipeline.theme_assets import replace_missing_fonts, resolve_theme_assets
from md2ui.utils.font_lock import cached_font
from md2ui.utils.font_loader import (
    resolve_code_typeface,
    resolve_typeface,
    weight_from_str,
)
from md2ui.utils.image_cache import ImageCache, decode_image
from md2ui.utils.png import encode_png
from md2ui.utils.scroll_state import ScrollState

if TYPE_CHECKING:
    from md2ui.pipeline.layout_render import LayoutNode

GroupingKit = tuple[SplitCriteria, DataPointDetector]


def repo_root() -> Path:
    """The repository root, found by walking up to ``pyproject.toml``.

    NOT an index into ``Path(__file__).parents``. That depth is a property of
    where this file happens to live, and a move leaves the paths resolving to a
    directory with no assets in it: nothing static notices, and the emoji
    typeface silently fails to load. Anchoring on a file that marks the root
    makes the answer independent of this module's location.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("repo root not found: no pyproject.toml above session.py")


_SHIPPED = Path(__file__).resolve().parent / "shipped"


def installed() -> bool:
    """Whether this md2ui is an installed package rather than a checkout: only a
    wheel holds ``md2ui/shipped/`` (pyproject.toml's wheel sources put it there)."""
    return _SHIPPED.is_dir()


def resource_root() -> Path:
    """Where the files md2ui reads at run time are -- the ``skills/`` notes, the
    default ``THEME.md`` and ``MEANINGS.md``, the font lock, the placeholders,
    the window's pictures -- laid out as in a checkout: ``md2ui/shipped/`` in an
    installed package, else the checkout itself."""
    return _SHIPPED if installed() else repo_root()


# --- Resources ---------------------------------------------------------------


def resolve_theme_path(markdown: Path, explicit: str | None) -> Path | None:
    """The THEME.md a document renders with: the one asked for, else the one
    beside the document, else the one in the working directory, else md2ui's
    default (the checkout's root ``THEME.md``, shipped inside the package)."""
    candidates = [
        Path(explicit) if explicit else None,
        markdown.parent / "THEME.md",
        Path.cwd() / "THEME.md",
        resource_root() / "THEME.md",
    ]
    return next((p for p in candidates if p is not None and p.exists()), None)


def default_theme_path() -> Path | None:
    """The THEME.md a shell with no document uses when none is asked for: the one in
    the working directory, else md2ui's default. The MCP servers resolve it once at
    launch, so the demo's previews and its window draw the same theme."""
    candidates = (Path.cwd() / "THEME.md", resource_root() / "THEME.md")
    return next((p for p in candidates if p.exists()), None)


def load_theme(theme_path: Path | None) -> Theme:
    """Parse *theme_path* (defaults when None), resolve the asset paths it names
    against its own folder, and apply its one global side effect, the
    inline-code size shared by measurement and drawing."""
    theme = parsed_theme(theme_path) if theme_path else Theme()
    set_inline_code_size(theme.inline_code.effective_text_style(theme.text).font_size)
    return theme


def parsed_theme(theme_path: Path) -> Theme:
    """*theme_path* parsed, with every asset path it names resolved: against its
    own folder, and a font file found in neither that folder nor the working
    directory taken from md2ui's own files, else from the locked fonts (an
    installed md2ui ships only its icon font)."""
    theme = resolve_theme_assets(parse_theme(theme_path), theme_path)
    replace_missing_fonts(theme, own_font)
    return theme


def own_font(path: str) -> str | None:
    """The font file *path* names among md2ui's own files (the icon font, which
    a copied THEME.md still names as ``assets/icons/...``), else ``locked_font``."""
    own = resource_root() / path
    return str(own) if own.is_file() else locked_font(path)


def locked_font(path: str) -> str | None:
    """The per-user copy of the font file *path* names, when ``assets/fonts.lock``
    locks a file of that name: fetched on first use, verified, and ``None`` with
    remote fetches off (fetch_policy)."""
    found = cached_font(Path(path).name, resource_root() / "assets" / "fonts.lock")
    return str(found) if found else None


def load_fonts(theme: Theme) -> FontSet:
    """Resolve every typeface the theme names. CPU-only, so it needs no window.

    Also fills the ``_TABLE_TYPEFACES`` global (## Tables text styles), which
    measurement and drawing both read.
    """
    custom_fonts, font_name, base_weight = load_theme_font_context(theme)
    ic_style = theme.inline_code.effective_text_style(theme.text)
    heading_typefaces: dict[
        int, tuple[skia.Typeface, skia.Typeface, skia.Typeface, skia.Typeface]
    ] = {}
    for h_level, h_ts in theme.headings.items():
        h_w = weight_from_str(h_ts.font_weight)
        # The bold pair is what ``**x**`` inside this heading renders with: at
        # least 700 so a light/regular heading really emphasizes, and never
        # heavier than the heading itself already is (resolve_typeface picks the
        # nearest available weight, so an already-bold heading doesn't double up).
        h_bw = max(h_w, 700)
        h_name = h_ts.font_name or font_name
        heading_typefaces[h_level] = (
            resolve_typeface(h_name, h_w, False, custom_fonts),
            resolve_typeface(h_name, h_w, True, custom_fonts),
            resolve_typeface(h_name, h_bw, False, custom_fonts),
            resolve_typeface(h_name, h_bw, True, custom_fonts),
        )
    # Table cell/key typefaces (## Tables text styles): like headings these
    # honor each style's own font name.
    _TABLE_TYPEFACES.clear()
    for t_key, t_ts in (
        ("header", theme.tables.header_text),
        ("cells", theme.tables.cells_text),
        ("keys", theme.tables.keys_text),
    ):
        if t_ts is None:
            continue
        t_name = t_ts.font_name or font_name
        t_w = weight_from_str(t_ts.font_weight)
        _TABLE_TYPEFACES[t_key] = (
            resolve_typeface(t_name, t_w, False, custom_fonts),
            resolve_typeface(t_name, t_w, True, custom_fonts),
        )

    if theme.emojis.font_path and Path(theme.emojis.font_path).exists():
        emoji_tf = skia.Typeface.MakeFromFile(theme.emojis.font_path)
    else:
        emoji_path = resource_root() / "assets" / "fonts" / "OpenMoji-black-glyf.ttf"
        found = str(emoji_path) if emoji_path.exists() else locked_font(emoji_path.name)
        emoji_tf = None
        if found:
            emoji_tf = skia.Typeface.MakeFromFile(found)
        else:
            print(f"[emoji] {emoji_path} not found — emoji will use fallback glyph")

    fonts = FontSet(
        resolve_typeface(font_name, base_weight, False, custom_fonts),
        resolve_typeface(font_name, 700, False, custom_fonts),
        resolve_typeface(font_name, base_weight, True, custom_fonts),
        resolve_typeface(font_name, 700, True, custom_fonts),
        # Inline code renders in its own text style's font (default: body
        # font), not a monospace face.
        resolve_typeface(
            ic_style.font_name or font_name,
            weight_from_str(ic_style.font_weight) or base_weight,
            False,
            custom_fonts,
        ),
        emoji_tf,
        heading_typefaces,
        text_emoji=_load_emoji_typeface(theme.emojis.text.font_path, emoji_tf),
        link_emoji=_load_emoji_typeface(theme.emojis.link.font_path, emoji_tf),
        emoji_paths=emoji_paths(theme),
    )
    cb_style = theme.code_blocks.text_style
    fonts.code_block = resolve_code_typeface(
        cb_style.font_name or font_name,
        weight_from_str(cb_style.font_weight) or base_weight,
        False,
        custom_fonts,
    )
    return fonts


def load_placeholders() -> None:
    """Decode the image/vector placeholder assets onto :data:`VIEW` (once).

    Shown for images that are loading or forced to placeholders (``i``), and the
    broken one for images that failed. A missing file leaves the field ``None`` →
    draw_image_box's cross fallback.
    """
    root = resource_root()
    for attr, rel in (
        ("placeholder_raster", "data/images/image-placeholder.png"),
        ("placeholder_vector", "data/vectors/image-placeholder.svg"),
        ("placeholder_broken", "data/images/image-broken-placeholder.png"),
    ):
        p = root / rel
        img = None
        if p.exists():
            try:
                img = decode_image(p.read_bytes())
            except Exception as exc:  # noqa: BLE001 — non-fatal
                print(f"[placeholder] failed to load {p}: {exc}")
        else:
            print(f"[placeholder] not found: {p}")
        # *attr* is a string, invisible to ruff and pyright — renaming a
        # ViewSettings field would break this at runtime with no static
        # warning. The assert is what closes that.
        assert hasattr(VIEW, attr), f"ViewSettings has no field {attr!r}"
        setattr(VIEW, attr, img)


def load_grouping_kit() -> GroupingKit:
    """Construct what the grouper is handed — the split criteria and the data
    point detector — once, so a caller that regroups (the app's watcher)
    reuses them. Neither is a fitted model (ADR-701); hence "kit".

    The detector keeps its shipped scope (ADR-102). The split criteria are
    rules, so nothing is loaded from disk.

    Both come memoized for as long as the kit lives (ADR-103), so a regroup of
    a re-sent, patched or re-saved document only asks about the lines that
    changed.
    """
    return MemoSplitCriteria(SplitCriteria()), MemoDetector(DataPointDetector())


# --- The pipeline ------------------------------------------------------------


def group_markdown(text: str, kit: GroupingKit) -> MarkdownGroupNode | None:
    """Group *text*; ``None`` only if the grouper produces no tree at all.

    This is exactly the call both snapshot oracles make.

    Deliberately NOT gated on ``MarkdownGrouper.validate``: an empty document
    groups to an empty root and renders a blank page, as it always has in both
    snapshots (the corpus holds two empty files). Refusing it would make the
    shells disagree with the oracles about the one input they all share.
    """
    grouper = MarkdownGrouper(text)
    criteria, detector = kit
    grouper.process(criteria, detector)
    return grouper.ast


# The trees group_shared handed out last, oldest first: (id(kit), text) -> (kit, tree).
_SHARED: OrderedDict[tuple[int, str], tuple[GroupingKit, MarkdownGroupNode | None]] = (
    OrderedDict()
)
_SHARED_LOCK = threading.Lock()  # the demo groups on worker threads
SHARED_TREES = 8


def group_shared(text: str, kit: GroupingKit) -> MarkdownGroupNode | None:
    """``group_markdown`` for the servers, where one text is read several times
    over: ``show`` reads its issues from the message the conversation recorded,
    a ``mark`` or ``patch`` records the very candidate it just regrouped, and an
    agent checks a text, then previews it. Each of those groups it once.

    **The tree is shared, so it is read-only once returned.** Every server reader
    of it today only reads: ``to_dict`` and the walkers over that dict, the
    advice and the digest, ``prepare`` (which builds its own copies). A caller
    that must change a tree groups its own with ``group_markdown``.
    ``tests/serve_grouping_tests.py`` runs those readers over a shared tree and
    fails on any change. A copy per caller costs about half a grouping, which is
    why the contract, not a copy, keeps it safe.

    Kept per kit, holding the kit, so an id cannot be reused by another; the
    last ``SHARED_TREES`` texts across all kits.
    """
    key = (id(kit), text)
    with _SHARED_LOCK:
        hit = _SHARED.get(key)
        if hit is not None:
            _SHARED.move_to_end(key)
            return hit[1]
    ast = group_markdown(text, kit)
    with _SHARED_LOCK:
        _SHARED[key] = (kit, ast)
        while len(_SHARED) > SHARED_TREES:
            _SHARED.popitem(last=False)
    return ast


def prepare(ast: MarkdownGroupNode, theme: Theme) -> tuple[MarkdownGroupNode, dict]:
    """Hand the grouper's tree to the later stages: ``(root, node_index)``.

    In memory — no file, no JSON string — but through the grouper's DICT form,
    not its live tree. The live tree carries state the dict drops
    (``glued_content_id=0``, ``applicable``, ``paren_quote_ranges``, and
    ``data_points`` in enum form), and every render, snapshots included, is
    drawn from the tree rebuilt from the dict. Handing over the live one would
    move pixels. The drawers read ``node_index`` as dicts in any case.

    Two ``to_dict`` calls, not one shared dict: ``load_node_index`` mutates the
    dicts it indexes.
    """
    return load_grouping_ast_node(ast.to_dict()), load_node_index(ast.to_dict(), theme)


# [root, theme, fonts, minimum] for the document last measured; see effective_width.
_MIN_WIDTH_MEMO: list = []


def effective_width(
    root: MarkdownGroupNode, theme: Theme, fonts: FontSet, asked_width: float
) -> float:
    """The width a layout asked for at *asked_width* is really built at.

    ``_content_width`` clamps the ask between the document's own minimum (what
    its content needs) and the theme's ``Max width``. That minimum does not
    depend on the width, so it is measured once per ``(root, theme, fonts)``,
    compared by IDENTITY and held here: a reload, a theme reload or a dropped
    file each hands over new objects, so there is nothing to invalidate by hand.

    The window asks this on every resize event and rebuilds only when the
    answer moves — a height-only drag, or any drag above ``Max width``, rebuilds
    nothing — so the scene's width is always this function's answer.
    """
    memo = _MIN_WIDTH_MEMO
    if not memo or memo[0] is not root or memo[1] is not theme or memo[2] is not fonts:
        measured = document_min_width(root, theme, make_width_measurer(fonts, theme))
        memo[:] = [root, theme, fonts, measured]
    return _content_width(asked_width, theme, min_width=memo[3])


@dataclass
class Scene:
    """One generated, baked and placed layout — everything a painter needs."""

    layout: LayoutNode
    width: float
    height: float
    boxes: list
    sections: list
    # Where a click lands (render_actions): link cards and buttons, and each
    # heading anchor's y. Per width, like the boxes they are read off.
    regions: list = field(default_factory=list)
    anchors: dict = field(default_factory=dict)
    # What a host may scroll: code blocks clipped at their right edge.
    scrollables: list = field(default_factory=list)


def build_scene(
    gen: LayoutGenerator,
    root: MarkdownGroupNode,
    node_index: dict,
    theme: Theme,
    fonts: FontSet,
    asked_width: float,
) -> Scene:
    """The scene at *asked_width*; under ``Layout: Auto`` (and no override), the one
    ``layout_auto`` picks for the width's band."""

    def build() -> Scene:
        return _build_scene(gen, root, node_index, theme, fonts, asked_width)

    if gen.bento_override is not None or theme.root.layout != "auto":
        return build()
    width = effective_width(root, theme, fonts, asked_width)
    return layout_auto.choose(gen, root, theme, fonts, width, build)


def _build_scene(
    gen: LayoutGenerator,
    root: MarkdownGroupNode,
    node_index: dict,
    theme: Theme,
    fonts: FontSet,
    asked_width: float,
) -> Scene:
    """Generate, bake and place the layout at *asked_width*.

    One width rule for every caller: the layout stops shrinking at what its
    content needs. *asked_width* is the width ASKED for; a document that cannot
    render that narrow gets its own minimum (the window scrolls, the PNG grows).
    """
    render_slots.clear()  # the shared card-piece heights are per width (ADR-401)
    width = effective_width(root, theme, fonts, asked_width)
    layout = gen.generate(
        root,
        width,
        theme,
        measure=make_layout_measurer(node_index, fonts, theme),
        measure_width=make_width_measurer(fonts, theme),
        measure_line=make_line_width_measurer(fonts, theme),
        measure_marker=make_marker_measurer(fonts, theme),
        measure_block=make_block_width_measurer(node_index, fonts, theme),
    )
    bake_render_cascade(layout, theme=theme)
    bake_merged_row_cards(layout, theme)
    bake_list_cards(layout, theme)
    bake_merged_lists(layout, theme)
    bake_list_run_cards(layout, theme)
    bake_card_ratios(layout)
    # Placement re-asks the heights it just measured; the layout is baked, so
    # nothing in it changes until the scope closes.
    with height_memo():
        height = natural_height(layout, width, node_index, fonts, theme)
        sections: list = []
        marks: list = []
        boxes = place_boxes(
            layout,
            0,
            0,
            width,
            height,
            node_index,
            fonts,
            theme,
            section_boxes=sections,
            action_marks=marks,
        )
    bake_image_bleed(boxes, sections, node_index, theme)
    regions, anchors = build_regions(boxes, marks, node_index, fonts, theme)
    code_face = fonts.code_block or fonts.mono or fonts.typeface
    scrollables = code_block_scrollables(
        boxes, node_index, code_face, theme.code_blocks
    )
    return Scene(layout, width, height, boxes, sections, regions, anchors, scrollables)


def report_url_params(gen: LayoutGenerator) -> list[str]:
    """Echo the last generation's ``?md2ui.*`` params and return their diagnostics.

    URL params are document content, so they take effect with no yaml, and a
    typo'd property is silently dropped unless the author is told.
    """
    n = len(gen._url_props)
    if n:
        print(f"[url] {n} md2ui param entr{'y' if n == 1 else 'ies'}")
    diagnostics = gen.url_diagnostics()
    for line in diagnostics:
        print(f"[url] {line}")
    return diagnostics


# --- Headless output ---------------------------------------------------------


def wait_for_images(
    image_cache: ImageCache, node_index: dict, timeout: float = 15.0
) -> None:
    """Fetch every image and block until they land (or *timeout* passes).

    Grouping and layout are synchronous; images are the only async step, so a
    one-shot render waits for them instead of drawing placeholders.
    """
    image_cache.fetch(node_index)
    image_cache.wait(timeout)
    image_cache.drain_pending_cpu()


def save_png(image: skia.Image | None, path: str) -> bool:
    """Encode a skia.Image to PNG and write it to *path*; False if it could not."""
    data = encode_png(image) if image is not None else None
    if data is None:
        print(f"[screenshot] encode failed, not saved: {path}")
        return False
    with open(path, "wb") as f:
        f.write(data)
    print(f"[screenshot] saved {path}")
    return True


# skia allocates no raster bitmap of 2 GiB or more (one byte under 2**31 is
# created at any width, 2**31 is refused).
MAX_BITMAP_BYTES = 2**31 - 1


class PageTooLarge(ValueError):
    """The page is too big for one bitmap, so there is nothing to paint into.
    Its message names the page's size, for the shell to print as it stands."""


def render_png(
    scene: Scene,
    node_index: dict,
    theme: Theme,
    fonts: FontSet,
    image_cache: ImageCache,
    background_images: dict,
    scale: float,
    out: str,
) -> bool:
    """Paint *scene* off-screen — no window, no GL — and write it to *out*."""
    image = render_image(
        scene, node_index, theme, fonts, image_cache, background_images, scale
    )
    return save_png(image, out)


def render_image(
    scene: Scene,
    node_index: dict,
    theme: Theme,
    fonts: FontSet,
    image_cache: ImageCache,
    background_images: dict,
    scale: float,
) -> skia.Image:
    """Paint *scene* off-screen — no window, no GL — into an image. The PNG the
    CLI writes and the preview the MCP shell returns are both this one paint."""
    scale = max(0.1, scale)
    # Grow by the root padding on both axes so the inset layout and its TLRB
    # background margins are captured. Ceil so the last px isn't clipped.
    pad = theme.root.padding
    win_w = int(math.ceil(scene.width + pad.x))
    win_h = int(math.ceil(scene.height + pad.y))
    px_w, px_h = max(1, int(win_w * scale)), max(1, int(win_h * scale))
    if px_w * px_h * 4 > MAX_BITMAP_BYTES:
        raise PageTooLarge(
            f"the page is {px_w:,} × {px_h:,} px at scale {scale:g}, "
            f"{px_w * px_h * 4 / 2**30:.2f} GiB as a bitmap; "
            "one bitmap must stay under 2 GiB, so it cannot be painted"
        )
    surf = skia.Surface(px_w, px_h)
    VIEW.show_frame = False  # layout fills the surface; no chrome/scrollbars
    VIEW.pixel_ratio = scale  # photos are decoded for the pixels they land on
    # Recorded and replayed, exactly as the window paints it — so this PNG, and
    # the render snapshot built from it, exercise the window's path.
    document = record_document(
        scene.boxes,
        scene.sections,
        node_index,
        scene.width,
        scene.height,
        fonts,
        image_cache,
        theme,
        scene.layout,
        background_images,
    )
    draw_scene(
        surf.getCanvas(),
        document,
        scene.width,
        scene.height,
        "",
        fonts.typeface,
        win_w,
        win_h,
        ScrollState(),
        theme,
        scale,
        background_images,
    )
    return surf.makeImageSnapshot()
