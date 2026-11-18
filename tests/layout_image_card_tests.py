"""
Unit tests for carrying an image card's background photo to the renderer.

A container LayoutNode has no ``content_id`` — that is only set on leaves — so
nothing on the render side can look the card's markdown node back up in the
node index. The background URL therefore has to be carried explicitly:

    grouper  image_card.card_bg_url
      -> generator  LayoutNode.card_bg_url        (_decide_group)
      -> renderer   SectionBox.bg_image_url       (_emit_wrap_boxes)
      -> paint      _paint_layered_fill

Every link in that chain fails silently — the card just renders as an ordinary
card with no photo — so each one is pinned here.

A photo that failed to load paints the broken placeholder in its place, as a
failed picture does; one still in flight paints the theme's background, and
one a server never fetched has not failed.

Run with: uv run python tests/layout_image_card_tests.py
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import skia  # type: ignore[import-untyped]

from md2ui import session

from md2ui.pipeline import render_backgrounds as RBG
from md2ui.pipeline import render_measure as RMS
from md2ui.pipeline import render_place as RPL
from md2ui.pipeline import render_placeholders as RPH
from md2ui.pipeline import layout_render as LR
from md2ui.pipeline import render_backgrounds as RB
from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.markdown_grouper import MarkdownGrouper
from md2ui.pipeline.render_settings import VIEW
from md2ui.pipeline.theme import Theme, parse_theme
from md2ui.pipeline.theme_model import SectionStyle
from md2ui.utils.fetch_policy import POLICY
from md2ui.utils.image_cache import ImageCache

HERO = "https://example.invalid/hero.png"

# The three shapes that reach the card-marking branch by different routes.
SHAPES = {
    "many children": f"![\n[🔖](/save)\n## Loft\nProse here.\n[Book](/b)\n]({HERO})",
    "two children": f"![\n## Payday\nGet paid early.\n]({HERO})",
    "single child": f"![\n## Only a heading\n]({HERO})",
    # No heading in the body, so nothing outranks the card and it stays one.
    "no heading": f"![\n[a](/x)\nJust prose here.\n]({HERO})",
    # Both nesting orders inside a list item. The first collapses to a single
    # group child, which sends it through _decide_group's transparent
    # passthrough, where the photo can drop silently.
    "link card in image card": (
        f"- ![\n  [\n\n  [`x`](/like)\n\n  ## Title\n\n  Body\n\n"
        f"  ](/link)\n\n  ]({HERO})"
    ),
    "image card in link card": (
        f"- [\n  ![\n\n  [`x`](/like)\n\n  ## Title\n\n  Body\n\n"
        f"  ]({HERO})\n  ](/link)"
    ),
}

_theme = None


def _theme_once():
    global _theme
    if _theme is None:
        _theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    return _theme


def _pipeline(md: str):
    """(layout root, node_index) for *md*, through the real generator."""
    g = MarkdownGrouper(md)
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    tmp = tempfile.mkdtemp(prefix="md2ui-card-test-")
    path = os.path.join(tmp, "grouping-ast.json")
    with open(path, "w") as fh:
        json.dump(g.ast.to_dict(), fh)
    node_index = LR.load_node_index(path)
    root = LR.load_grouping_ast_node(path)
    layout = LayoutGenerator().generate(root, 960.0, _theme_once())
    return layout, node_index


def _walk(n):
    yield n
    for c in getattr(n, "children", None) or []:
        yield from _walk(c)


def test_generator_carries_the_background_url():
    """Without this the URL never leaves the grouper.

    Carried whatever won the background — a heading that absorbed the card
    paints the photo as its section, so the URL is not tied to ``card_kind``.
    """
    for label, md in SHAPES.items():
        layout, _ = _pipeline(md)
        cards = [n for n in _walk(layout) if getattr(n, "card_bg_url", None)]
        assert len(cards) == 1, f"{label}: {len(cards)} nodes carry a URL"
        assert cards[0].card_bg_url == HERO, label
        # It must still paint *something*: either a section or a card layer.
        assert cards[0].is_card or cards[0].section_level is not None, label
    print(f"  ✓  the generator carries card_bg_url ({len(SHAPES)} shapes)")


def test_image_cache_requests_the_background():
    """fetch() must collect card backgrounds, not only `type == "image"` nodes."""
    _, node_index = _pipeline(SHAPES["two children"])
    urls = {
        url
        for node in node_index.values()
        for url in [
            LR.image_url(node.get("content", ""))
            if node.get("type") == "image"
            else node.get("card_bg_url")
        ]
        if url
    }
    assert HERO in urls, urls
    print("  ✓  the image cache would request the background URL")


def test_card_style_ignores_element_styling():
    """The photo IS the card, so it must not depend on element styling."""
    theme = _theme_once()
    layout, _ = _pipeline(SHAPES["two children"])
    card = next(n for n in _walk(layout) if getattr(n, "card_bg_url", None))
    assert RB._card_style_for(card, theme) is not None
    print("  ✓  an image card is styled whatever ### Elements holds")


def test_wrap_layer_kind_is_image_card():
    """A card with no heading in its body stays a card and paints as one."""
    theme = _theme_once()
    layout, _ = _pipeline(SHAPES["no heading"])
    card = next(n for n in _walk(layout) if getattr(n, "card_bg_url", None))
    kinds = [k for k, _, _ in RBG._wrap_layers(card, theme, frozenset())]
    assert kinds == ["image_card"], kinds
    print("  ✓  the wrap layer is emitted as kind='image_card'")


def test_image_card_style_survives_into_the_painter():
    """The paint lookup must not collapse an image card back to Elements."""
    theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    style, image_key = RBG._paint_style_for("image_card", 0, theme)
    assert style is theme.image_cards
    assert image_key == -5

    fallback_theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    fallback_theme.image_cards = SectionStyle()
    style, image_key = RBG._paint_style_for("image_card", 0, fallback_theme)
    assert style is fallback_theme.elements
    assert image_key == -1
    print("  ✓  image-card paint uses its own style, with Elements fallback")


def test_image_card_theme_background_is_loaded_for_its_painter():
    theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    theme.image_cards.bg_image = "image-card-theme.png"
    sentinel = object()
    with patch.object(
        LR,
        "theme_picture",
        side_effect=lambda src: sentinel if src == theme.image_cards.bg_image else None,
    ):
        images = LR.load_background_images(theme)
    assert images[-5] is sentinel
    print("  ✓  an Image Cards background image reaches its paint cache slot")


def test_exactly_one_background_layer():
    """Background precedence: never two full-extent rects on one node."""
    theme = _theme_once()
    for label, md in SHAPES.items():
        layout, _ = _pipeline(md)
        node = next(n for n in _walk(layout) if getattr(n, "card_bg_url", None))
        layers = RBG._wrap_layers(node, theme, frozenset())
        backgrounds = [
            k for k, _, _ in layers if k in ("section", "card", "image_card")
        ]
        assert len(backgrounds) == 1, f"{label}: {backgrounds}"
    print("  ✓  a node paints exactly one background layer")


def test_section_box_receives_the_url():
    """The box the paint loop reads must carry the photo.

    Whichever role won, the photo rides the outermost box — the one covering
    the node's whole extent.
    """
    theme = _theme_once()
    for label, md in SHAPES.items():
        layout, _ = _pipeline(md)
        node = next(n for n in _walk(layout) if getattr(n, "card_bg_url", None))
        boxes: list = []
        RBG._emit_wrap_boxes(
            boxes,
            0.0,
            0.0,
            400.0,
            200.0,
            RBG._wrap_layers(node, theme, frozenset()),
            bg_image_url=node.card_bg_url,
        )
        carrying = [b for b in boxes if b.bg_image_url]
        assert len(carrying) == 1, f"{label}: {[b.kind for b in boxes]}"
        assert carrying[0] is boxes[0], f"{label}: not the outermost box"
        assert carrying[0].bg_image_url == HERO, label
    print("  ✓  the outermost SectionBox carries the background URL")


def test_both_nesting_orders_render_alike():
    """A photo must survive whichever way the two cards nest.

    `link card in image card` leaves the list item with a single group child,
    so `_decide_group`'s transparent passthrough returns early and skips the
    card marking.
    """
    shapes = {}
    for label in ("link card in image card", "image card in link card"):
        layout, _ = _pipeline(SHAPES[label])
        holders = [
            (n.is_card, n.card_kind)
            for n in _walk(layout)
            if getattr(n, "card_bg_url", None)
        ]
        assert holders == [(True, "image_card")], f"{label}: {holders}"
        shapes[label] = holders
    assert len(set(map(str, shapes.values()))) == 1, shapes
    print("  ✓  both nesting orders keep the photo and match")


def test_merge_rows_skips_rows_with_different_photos():
    """`Merge rows` paints ONE background for a row of same-level sections.

    A section can carry its own photo, and merging would discard every card's
    image in favour of one shared background.

    Built from LayoutNodes directly: the layout rules do not readily grid cards
    into a row, and this branch is a pure decision about a shape.
    """
    from md2ui.pipeline.layout_script_parser import LayoutNode

    theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    theme.sections[2].merge_rows = True

    def _row(photos):
        row = LayoutNode(type="row", ratios=[], children=[])
        row.section_level = 2
        for photo in photos:
            cell = LayoutNode(type="col", ratios=[], children=[])
            cell.section_level = 2
            cell.is_card = bool(photo)
            cell.card_bg_url = photo
            row.children.append(cell)
        return row

    cases = {
        "no photos": ([None, None, None], True),
        "same photo": (["a.jpg", "a.jpg", "a.jpg"], True),
        "different photos": (["a.jpg", "b.jpg", "c.jpg"], False),
        "mixed photo and none": (["a.jpg", None, "a.jpg"], False),
    }
    for label, (photos, should_merge) in cases.items():
        row = _row(photos)
        merged = RB._section_style_for(row, theme, frozenset())[0] is not None
        assert merged is should_merge, f"{label}: merged={merged}"
        # The two functions mirror one decision — disagreeing would either
        # double-paint the row or paint nothing at all.
        assert RMS._is_transparent_container(row, theme) is not should_merge, (
            f"{label}: the two merge decisions disagree"
        )
    print("  ✓  merge_rows skips a row whose photos differ")


def test_a_merged_row_takes_the_shared_photo():
    """A merged row of identical image cards paints ONE photo.

    Merging suppresses each child's *section* wrap and, through the bake, its
    **card** wrap: the shared photo moves up and the children are cleared.
    """
    from md2ui.pipeline.layout_script_parser import LayoutNode

    theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    theme.sections[2].merge_rows = True

    def _row(photos):
        row = LayoutNode(type="row", ratios=[], children=[])
        row.section_level = 2
        for photo in photos:
            cell = LayoutNode(type="col", ratios=[], children=[])
            cell.section_level = 2
            cell.is_card = bool(photo)
            cell.card_kind = "image_card" if photo else None
            cell.card_bg_url = photo
            row.children.append(cell)
        return row

    shared = _row(["a.jpg", "a.jpg", "a.jpg"])
    RPL.bake_merged_row_cards(shared, theme)
    assert shared.card_bg_url == "a.jpg", shared.card_bg_url
    assert all(not c.is_card for c in shared.children), "children still cards"
    assert all(c.card_bg_url is None for c in shared.children)

    # A row that does not merge must keep every card exactly as it was.
    differing = _row(["a.jpg", "b.jpg", "c.jpg"])
    RPL.bake_merged_row_cards(differing, theme)
    assert differing.card_bg_url is None
    assert [c.card_bg_url for c in differing.children] == [
        "a.jpg",
        "b.jpg",
        "c.jpg",
    ]
    assert all(c.is_card for c in differing.children)
    print("  ✓  a merged row takes the shared photo, children stop painting")


def test_a_plain_card_carries_no_background():
    """An ordinary glued card must be unaffected."""
    layout, _ = _pipeline("## Title\n\nSome prose.\nMore prose.")
    assert not [n for n in _walk(layout) if getattr(n, "card_bg_url", None)]
    print("  ✓  a plain card carries no background URL")


# Sentinels the corpus never paints, standing in for the two placeholder assets
# so their pixels can be counted exactly.
_LOADING = (255, 0, 255)
_BROKEN = (0, 255, 255)

# A URL whose fetch fails at once with no network: nothing waits on DNS.
_MISSING = "file:///nonexistent/md2ui-missing.png"


def _sentinel(rgb: tuple[int, int, int]) -> skia.Image:
    pixels = np.zeros((8, 8, 4), dtype=np.uint8)
    pixels[:, :] = (*rgb, 255)
    return skia.Image.fromarray(pixels, colorType=skia.kRGBA_8888_ColorType)


def _paint(markdown: str, state: str, theme: Theme | None = None) -> np.ndarray:
    """Render *markdown* with its pictures in *state*, the placeholders swapped
    for the sentinels.

    ``fetched``: every fetch has landed or failed. ``loading``: nothing has
    arrived yet, as in the window before a fetch returns. ``skipped``: fetched
    with the network off, as a server does.
    """
    theme = theme or Theme()
    root = session.group_markdown(markdown, session.load_grouping_kit())
    assert root is not None
    root, index = session.prepare(root, theme)
    fonts = session.load_fonts(theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 400.0)
    cache = ImageCache()
    remote = POLICY.remote
    POLICY.remote = state != "skipped"
    try:
        if state != "loading":
            session.wait_for_images(cache, index)
    finally:
        POLICY.remote = remote
    saved = VIEW.placeholder_raster, VIEW.placeholder_broken
    VIEW.placeholder_raster = _sentinel(_LOADING)
    VIEW.placeholder_broken = _sentinel(_BROKEN)
    try:
        image = session.render_image(scene, index, theme, fonts, cache, {}, 1.0)
    finally:
        VIEW.placeholder_raster, VIEW.placeholder_broken = saved
    return image.toarray(colorType=skia.kRGBA_8888_ColorType)[:, :, :3].astype(int)


def _mask(rgb: np.ndarray, colour: tuple[int, int, int]) -> np.ndarray:
    return np.abs(rgb - np.array(colour)).sum(axis=2) < 6


def _card(state: str) -> tuple[int, int]:
    """Loading and broken placeholder pixels on a photo card in *state*."""
    rgb = _paint(f"![\n## Payday\nGet paid early.\n]({_MISSING})\n", state)
    return int(_mask(rgb, _LOADING).sum()), int(_mask(rgb, _BROKEN).sum())


def test_a_failed_photo_paints_the_broken_placeholder():
    """A photo card whose photo failed draws the broken placeholder as its
    background."""
    loading, broken = _card("fetched")
    assert broken > 2000, f"only {broken} broken placeholder pixels on the card"
    assert loading == 0, f"{loading} loading placeholder pixels on a failed card"
    print(f"  ✓  a failed card photo paints the broken placeholder ({broken} px)")


def test_a_photo_in_flight_paints_no_placeholder():
    """A photo that has not arrived yet is not failed: the window must not
    flash a placeholder before the fetch returns."""
    assert _card("loading") == (0, 0), "a placeholder while the photo loads"
    print("  ✓  a photo still in flight paints no placeholder")


def test_a_skipped_fetch_is_not_a_failure():
    """A server fetches nothing, so it has seen no failure: its previews never
    draw the broken placeholder."""
    assert _card("skipped") == (0, 0), "a placeholder for a fetch never made"
    rgb = _paint(f"![Photo]({_MISSING})\n", "skipped")
    assert not _mask(rgb, _BROKEN).any(), "a skipped image drew as broken"
    print("  ✓  a fetch the policy skipped is not a failure")


def test_a_failed_image_paints_the_broken_placeholder():
    """A content image draws the loading placeholder until its fetch fails,
    and the broken one after."""
    loading = _paint(f"![Photo]({_MISSING})\n", "loading")
    failed = _paint(f"![Photo]({_MISSING})\n", "fetched")
    assert _mask(loading, _LOADING).sum() > 2000 and not _mask(loading, _BROKEN).any()
    assert _mask(failed, _BROKEN).sum() > 2000 and not _mask(failed, _LOADING).any()
    print("  ✓  a failed content image paints the broken placeholder")


def test_a_failed_image_keeps_its_run():
    """A failed picture is a paint state, never a structural one: in a run of
    photo cards where half the photos fail, every card paints exactly where it
    does when all of them load, so failure can never break a same-kind run.
    The photo is a local file in the broken sentinel's
    colour and size, so a loaded card and a failed one paint alike."""
    theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    photo = Path(tempfile.gettempdir()) / "md2ui-run-photo.png"
    photo.write_bytes(bytes(_sentinel(_BROKEN).encodeToData()))
    ok = photo.as_uri()

    def run(urls: list[str]) -> np.ndarray:
        md = "".join(
            f"- ![\n  ### Card {i}\n  Body {i}.\n  ]({u})\n" for i, u in enumerate(urls)
        )
        return _paint(md, "fetched", theme)

    loaded = run([ok, ok, ok, ok])
    mixed = run([ok, f"{_MISSING}?1", ok, f"{_MISSING}?3"])
    assert _mask(loaded, _BROKEN).sum() > 4000, "the photos did not paint"
    # A decoded file and the in-memory sentinel sample a level or two apart on
    # anti-aliased edges; a card that moved would differ by hundreds.
    apart = int(np.abs(loaded - mixed).max())
    assert apart <= 2, f"the runs differ by {apart} levels"
    print("  ✓  a run with failed photos paints where the loaded run does")


def test_the_i_key_forces_the_loading_placeholder():
    """The I key shows every image as loading, a failed one included: it is a
    view of the layout, not a report on the fetches."""
    cache = ImageCache()
    node = {"type": "image", "content": f"![Photo]({_MISSING})"}
    session.wait_for_images(cache, {"n": node})
    assert cache.failed(_MISSING)
    saved = VIEW.placeholder_images, VIEW.placeholder_raster, VIEW.placeholder_broken
    VIEW.placeholder_raster, VIEW.placeholder_broken = (
        _sentinel(_LOADING),
        _sentinel(_BROKEN),
    )
    try:
        VIEW.placeholder_images = True
        assert RPH.image_picture(cache, _MISSING, False) is VIEW.placeholder_raster
        VIEW.placeholder_images = False
        assert RPH.image_picture(cache, _MISSING, False) is VIEW.placeholder_broken
    finally:
        VIEW.placeholder_images, VIEW.placeholder_raster, VIEW.placeholder_broken = (
            saved
        )
    print("  ✓  the I key forces the loading placeholder, failed or not")


# ---------------------------------------------------------------------------
# The card's own size params: the picture's ratio sizes the card, content wins
# ---------------------------------------------------------------------------


def _card_scene(md: str):
    """(the photo's box, the text leaves' boxes) of *md* laid out 400 wide."""
    g = MarkdownGrouper(md)
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    theme = _theme_once()
    root, index = session.prepare(g.ast, theme)
    fonts = session.load_fonts(theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 400.0)
    card = next(b for b in scene.sections if b.bg_image_url)
    return card, scene


def _sized_card(params: str, body: str = "#### Monstera\n_$33_") -> tuple:
    return _card_scene(f"![\n{body}\n]({HERO}{params})\n")


def test_a_cards_ratio_sizes_it():
    plain, _ = _sized_card("")
    square, _ = _sized_card("?md2ui.aspect_ratio=1:1")
    assert plain.height < plain.width, "no ratio: as tall as its content"
    assert abs(square.height - square.width) < 1.0, (square.width, square.height)
    capped, _ = _sized_card("?md2ui.aspect_ratio=1:1&md2ui.max_height=200")
    assert abs(capped.height - 200.0) < 1.0, capped.height
    print("  ✓  an image card's aspect_ratio sizes it, max_height caps it")


def test_content_that_needs_more_room_wins():
    long = "#### " + "A long title that wraps " * 6 + "\n_$33_"
    short, _ = _sized_card("?md2ui.aspect_ratio=8:1", long)
    content, _ = _sized_card("", long)
    assert abs(short.height - content.height) < 1.0, (short.height, content.height)
    print("  ✓  content taller than the ratio grows the card")


def test_the_spare_room_goes_above_the_words():
    card, scene = _sized_card(
        "?md2ui.aspect_ratio=1:1", "`New` ... [Save](agent:save)\n#### Monstera\n_$33_"
    )
    tops = sorted(b.y for b in scene.boxes if b.y >= card.y)
    assert tops[0] - card.y < 40, "the one-line row stays on top"
    assert card.y + card.height - tops[-1] < 60, "the last words sit at the bottom"
    print("  ✓  spare room goes above the words; a first one-line row stays on top")


def test_the_spare_room_grows_the_authored_spacer():
    card, scene = _sized_card(
        "?md2ui.aspect_ratio=1:1", "[Save](agent:save)\n+++++\n#### Monstera"
    )
    tops = sorted(b.y for b in scene.boxes if b.y >= card.y)
    assert tops[0] - card.y < 40, "what is written above the spacer stays on top"
    assert card.y + card.height - tops[-1] < 60, "what is below it sits at the bottom"
    print("  ✓  spare room grows the card's `+++++`, where its author put room")


def test_the_ratio_never_changes_the_columns():
    """The generator arranges a run from its cards' content; the ratio then
    sizes each card in the column it was given. The shape of
    tests-render/catalogs/food, whose 5:4 photos must not cost a column."""

    def columns(params: str) -> list[float]:
        cards = "\n\n".join(
            f"### \n![\n`New` ... *[🤍](agent:fav?id={i})*\n+++++\n]({HERO}{params})\n"
            f"__Dish {i}__ ... ___$14.50___\n_🕒 18 min_ - _🔥 Mild_\n---\n"
            f"**⭐ 4.9** ... [+ Add](agent:add?id={i})"
            for i in range(6)
        )
        g = MarkdownGrouper(cards)
        g.process(criteria=None, detector=DataPointDetector())
        assert g.ast is not None
        theme = _theme_once()
        root, index = session.prepare(g.ast, theme)
        fonts = session.load_fonts(theme)
        scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 767.0)
        return sorted({round(b.x) for b in scene.sections if b.bg_image_url})

    assert columns("?md2ui.aspect_ratio=5:4") == columns(""), "same columns"
    print("  ✓  a card's ratio never changes how many columns its run takes")


def test_a_photo_cards_overlay_holds_its_pills():
    # A chip and a button never wrap their label, so each is drawn whole. The
    # card's minimum width must count the ### Image Cards padding the overlay
    # sits inside, or the grid sets cards too narrow for the chip; and a line
    # with no room wraps its pieces rather than shrinking them below their pills.
    from md2ui.pipeline.render_measure import _leaf_natural_width

    cards = "\n\n".join(
        f"### \n![\n`Favorito entre huéspedes` ... _[🤍](agent:save?id={i})_\n"
        f"+++++\n]({HERO})\n**Departamento en Centro**\n_6–8 de nov_"
        for i in range(2)
    )
    theme = _theme_once()
    fonts = session.load_fonts(theme)
    grouped = session.group_markdown(cards, session.load_grouping_kit())
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    short = []
    for width in range(340, 1000, 20):
        scene = session.build_scene(
            LayoutGenerator(), root, index, theme, fonts, float(width)
        )
        for box in scene.boxes:
            nd = index.get(box.content_id)
            if nd and nd.get("type") in ("link", "inline_code"):
                pill = _leaf_natural_width(nd, 1e6, fonts, theme, box.render_properties)
                if pill > box.width + 0.5:
                    short.append((width, nd.get("type"), round(pill - box.width, 1)))
    assert not short, f"a pill is wider than its box: {short}"
    print("  ✓  a photo card's overlay holds its chip and button whole")


def test_the_first_cards_ratio_sets_the_run():
    # skills/images.md: one annotated picture sets the whole run. An image
    # card's picture is its background, not a child, so it must vote too.
    def shelf(first: str) -> list[float]:
        cards = "\n\n".join(
            f"### \n![\n... ***[🤍](agent:save?id={i})***\n]({HERO}{first if i == 0 else ''})\n"
            f"**Item {i}** ... $95"
            for i in range(3)
        )
        theme = _theme_once()
        grouped = session.group_markdown(cards, session.load_grouping_kit())
        assert grouped is not None
        root, index = session.prepare(grouped, theme)
        fonts = session.load_fonts(theme)
        scene = session.build_scene(
            LayoutGenerator(), root, index, theme, fonts, 1024.0
        )
        return [b.height / b.width for b in scene.sections if b.bg_image_url]

    ratios = shelf("?md2ui.aspect_ratio=3:4")
    assert len(ratios) == 3 and all(abs(r - 4 / 3) < 0.02 for r in ratios), ratios
    print("  ✓  the first image card's ratio sets the whole run")


TESTS = [
    test_the_first_cards_ratio_sets_the_run,
    test_a_photo_cards_overlay_holds_its_pills,
    test_generator_carries_the_background_url,
    test_image_cache_requests_the_background,
    test_card_style_ignores_element_styling,
    test_wrap_layer_kind_is_image_card,
    test_image_card_style_survives_into_the_painter,
    test_image_card_theme_background_is_loaded_for_its_painter,
    test_exactly_one_background_layer,
    test_section_box_receives_the_url,
    test_both_nesting_orders_render_alike,
    test_merge_rows_skips_rows_with_different_photos,
    test_a_merged_row_takes_the_shared_photo,
    test_a_plain_card_carries_no_background,
    test_a_failed_photo_paints_the_broken_placeholder,
    test_a_photo_in_flight_paints_no_placeholder,
    test_a_skipped_fetch_is_not_a_failure,
    test_a_failed_image_paints_the_broken_placeholder,
    test_a_failed_image_keeps_its_run,
    test_the_i_key_forces_the_loading_placeholder,
    test_a_cards_ratio_sizes_it,
    test_content_that_needs_more_room_wins,
    test_the_spare_room_goes_above_the_words,
    test_the_spare_room_grows_the_authored_spacer,
    test_the_ratio_never_changes_the_columns,
]

if __name__ == "__main__":
    print("Layout Image Card Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
