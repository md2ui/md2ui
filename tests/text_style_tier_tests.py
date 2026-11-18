"""
Unit tests for the authored display tiers: a WHOLE leaf wrapped in underscores
picks a ## Text Styles block — `_x_` muted, `__x__` lead, `___x___` display.
Underscores are CommonMark synonyms for asterisks, so the same markdown still
reads as italic / bold / bold-italic in an editor that doesn't know the tiers,
and mid-sentence underscores keep meaning exactly that.

Also covers the `Key` / `Value` styles of a display's pair (ADR-205) and the
consolidation of ### Emphasis's value font into the shared Display tier.

Run with: uv run python tests/text_style_tier_tests.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "tests")

import skia
from markdown_datapoint_split_tests import _processed, _processed_with_criteria

from md2ui.pipeline.data_point_detector import DataPointType
from md2ui.pipeline.render_style import (
    FontSet,
    _effective_text_fonts,
)
from md2ui.pipeline.layout_render import (
    _marker_style,
)
from md2ui.pipeline.render_style import _kv_role_style
from md2ui.pipeline.markdown_grouper import (
    MarkdownGroupNode,
    MarkdownGrouper,
    NodeType,
)
from md2ui.pipeline.theme import Theme, parse_theme, tier_style
from md2ui import session
from md2ui.pipeline import layout_render
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.utils.image_cache import ImageCache
from md2ui.utils.font_loader import family_name


def _fonts() -> FontSet:
    tf = skia.Typeface.MakeDefault()
    return FontSet(tf, tf, tf, tf, tf)


def _tiers(node: MarkdownGroupNode) -> list[tuple[str, str]]:
    """Every (tier, content) stamped on a LEAF of the subtree, in document order.

    Leaves only, because that is what the renderer reads: Phase 6.055 pushes a
    container's whole-line tier down to its text-bearing leaves and leaves its own
    copy in place, where it paints nothing; collecting containers would count it
    twice.
    """
    out: list[tuple[str, str]] = []
    if node.text_style and not node.children:
        out.append((node.text_style, node.content))
    for c in node.children:
        out.extend(_tiers(c))
    return out


def _only_leaf(node: MarkdownGroupNode) -> MarkdownGroupNode:
    """The single leaf of a one-leaf document.

    The ROOT is a container and never a leaf (Phase 6.04), so a test that reads
    ``content`` or ``type`` off the result of ``_processed`` on a one-line
    document reads it here instead.
    """
    while node.children:
        assert len(node.children) == 1, f"not a one-leaf document: {node.to_dict()}"
        node = node.children[0]
    return node


def _theme_from(md: str) -> Theme:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "THEME.md"
        p.write_text(md)
        return parse_theme(p)


# ---------------------------------------------------------------------------
# _detect_underscore_wrap (pure)
# ---------------------------------------------------------------------------


def test_wrap_maps_run_length_to_tier():
    det = MarkdownGrouper._detect_underscore_wrap
    assert det("_a_") == ("muted", "a")
    assert det("__a__") == ("lead", "a")
    assert det("___a___") == ("display", "a")
    print("  ✓  1/2/3 underscores -> muted / lead / display")


def test_wrap_rejects_partial_and_unbalanced():
    det = MarkdownGrouper._detect_underscore_wrap
    assert det("plain text") is None
    assert det("Text with a __bold__ word") is None, "mid-sentence is not a tier"
    assert det("__a_") is None, "unbalanced runs"
    assert det("____a____") is None, "4 underscores is not a tier"
    assert det("__") is None and det("____") is None, "no inner content"
    print("  ✓  partial, unbalanced and empty wraps are rejected")


def test_wrap_rejects_two_separate_spans():
    # `_A_ _B_` starts and ends with a marker but is NOT one wrap: treating it
    # as one would strip a wrapper that was never there. Same guard as
    # _detect_style_wrap uses for the asterisk family.
    det = MarkdownGrouper._detect_underscore_wrap
    assert det("_A_ _B_") is None
    assert det("__A__ and __B__") is None
    print("  ✓  a run of separate spans is not one wrap")


# ---------------------------------------------------------------------------
# _detect_underscore_span_run (pure)
#
# `_A_ _B_` is not ONE wrap — but it IS a run of two whole spans on one line,
# and each takes its own tier.
# ---------------------------------------------------------------------------


def test_run_gives_each_span_its_own_tier():
    det = MarkdownGrouper._detect_underscore_span_run
    assert det("_High 78_ _Low 56_") == [
        ("muted", "High 78"),
        ("muted", "Low 56"),
    ]
    assert det("_A_ _B_ _C_") == [
        ("muted", "A"),
        ("muted", "B"),
        ("muted", "C"),
    ]
    print("  ✓  each span in a run takes its own tier")


def test_run_may_mix_tiers():
    det = MarkdownGrouper._detect_underscore_span_run
    assert det("_High 78_ __Low 56__") == [
        ("muted", "High 78"),
        ("lead", "Low 56"),
    ]
    print("  ✓  a run may mix tiers")


def test_run_needs_at_least_two_whole_spans():
    det = MarkdownGrouper._detect_underscore_span_run
    assert det("_only one_") is None, "one span is the whole-wrap case"
    assert det("Text with a _italic_ word") is None, "text outside a span"
    assert det("_A_ - _B_") is None, "a separator splits it, not this"
    assert det("_a_b_c_") is None
    print("  ✓  a run needs >= 2 whole spans and nothing else")


def test_run_defers_to_key_value_and_element_variants():
    """A tight colon means key-value; a link / chip / emoji wrapper selects
    that ELEMENT's variant, not a text tier. All own the line already."""
    det = MarkdownGrouper._detect_underscore_span_run
    assert det("__Key:__ __value__") is None
    assert det("_`a`_ _`b`_") is None
    assert det("_[Muted link](/x)_ _[Other](/y)_") is None
    print("  ✓  a run defers to key-value and element variants")


def test_run_splits_the_same_in_both_families():
    """Separation does not depend on the emphasis family; only the style does.

    Both spellings are a run of two whole spans and both split into two leaves.
    `_` selects a TIER and its wrapper is consumed; `*` is ordinary emphasis, so
    the piece keeps its markers for the renderer to paint. That is the ONLY
    difference.

    A tight colon and link / image / chip / emoji content each still bail out
    (see the two tests below and
    test_run_defers_to_key_value_and_element_variants).
    """
    underscores = _processed_with_criteria("_High 78_ _Low 56_")
    asterisks = _processed_with_criteria("*High 78* *Low 56*")

    def leaves(node):
        if not node.children:
            return [node]
        return [leaf for c in node.children for leaf in leaves(c)]

    assert len(leaves(underscores)) == len(leaves(asterisks)) == 2, [
        n.content for n in leaves(asterisks)
    ]
    assert _tiers(underscores) == [("muted", "High 78"), ("muted", "Low 56")]
    # The asterisk pieces take no tier — their markers ride on and are painted.
    assert _tiers(asterisks) == []
    assert [n.content for n in leaves(asterisks)] == ["*High 78*", "*Low 56*"]
    print("  ✓  both families split the same; only the styling differs")


def test_run_splits_into_sibling_leaves():
    """End to end: data/markdown/tests-render/theme-tests/fixed-colors/emoji/content.md:2.

    Measured with the real SplitCriteria, as the pipeline runs. Without the gate,
    `High 78` splits further into text + datapoint (each half still correctly
    tiered), which says nothing about this pass.
    """
    tiers = _tiers(_processed_with_criteria("_High 78_ _Low 56_"))
    assert tiers == [("muted", "High 78"), ("muted", "Low 56")], tiers
    assert not any("_" in c for _, c in tiers)
    print("  ✓  a run becomes one tiered leaf per span")


# ---------------------------------------------------------------------------
# Grouper annotation
# ---------------------------------------------------------------------------


def test_whole_line_is_stamped_and_stripped():
    ast = _processed("_Muted text_")
    assert _tiers(ast) == [("muted", "Muted text")]
    print("  ✓  a whole line is stamped and the wrapper consumed")


def test_mid_sentence_is_not_a_tier():
    ast = _processed("Text with a __bold__ word in the middle")
    assert _tiers(ast) == []
    # The markers stay on the content for the renderer's span parser.
    assert "__bold__" in _only_leaf(ast).content
    print("  ✓  mid-sentence underscores stay plain bold, markers preserved")


def test_each_segment_takes_its_own_tier():
    ast = _processed("__Total__ | __$412M__ | __+12%__")
    tiers = _tiers(ast)
    assert tiers, "segments should be stamped"
    assert {t for t, _ in tiers} == {"lead"}
    assert any(c == "Total" for _, c in tiers)
    print("  ✓  each whole segment takes its own tier")


def test_tier_survives_datapoint_detection():
    # `_` is a regex word character, so a \b-anchored currency pattern sees
    # ``___$412M___`` differently from ``***$412M***``. The whole-line pass runs
    # BEFORE detection so the detector gets clean content and `$412M` stays one
    # currency annotation instead of splitting into `$412` + a stray remainder.
    ast = _processed("___$412M___")
    assert _tiers(ast) == [("display", "$412M")]
    leaf = _only_leaf(ast)
    assert leaf.type == NodeType.TEXT
    assert leaf.data_points[0]["type"] == DataPointType.CURRENCY
    assert leaf.data_points[0]["matched"] == "$412M"
    print("  ✓  the wrapper is consumed before datapoint detection")


def test_tier_on_a_key_beats_the_key_style():
    # A pair is a display's (ADR-205): this one holds a ratio bar.
    ast = _processed("__Minutes:__ 7/8")
    assert ("lead", "Minutes") in _tiers(ast)
    print("  ✓  a tier on a K-V key is stamped (it outranks Key)")


def _leaf_contents(node: MarkdownGroupNode) -> list[str]:
    if not node.children:
        return [node.content]
    return [c for ch in node.children for c in _leaf_contents(ch)]


def test_a_cut_keeps_the_style_the_unsplit_line_had():
    """Styling survives splits: each piece keeps the style its text had in the
    unsplit line. A span that is NOT the whole line (`!` sits outside) is
    inline emphasis, so neither half of it becomes a tier."""
    for line in (
        "_Alpha | Beta_!",
        "__Alpha | Beta__!",
        "___Alpha | Beta___!",
        "_Alpha • Beta_!",
        "_Alpha ... Beta_!",
        "_Key: value here_!",
    ):
        ast = _processed_with_criteria(line)
        assert _tiers(ast) == [], (line, _tiers(ast))
        assert all("_" in c for c in _leaf_contents(ast)), (line, _leaf_contents(ast))
    for line, tier in (
        ("_Alpha | Beta_", "muted"),
        ("__Alpha | Beta__", "lead"),
        ("___Alpha | Beta___", "display"),
        ("_Alpha ... Beta_", "muted"),
    ):
        tiers = _tiers(_processed_with_criteria(line))
        assert tiers == [(tier, "Alpha"), (tier, "Beta")], (line, tiers)
    # A piece wrapped on its own in the source keeps its own tier.
    assert _tiers(_processed_with_criteria("_A_ | B")) == [("muted", "A")]
    print("  ✓  a cut never changes which tier a piece's text gets")


def test_wrap_is_authored_reads_the_source_line():
    from md2ui.pipeline.grouper_inline_marks import _wrap_is_authored

    assert _wrap_is_authored("_A_ | B", 1, "A")
    assert not _wrap_is_authored("_A | B_!", 1, "A")
    assert _wrap_is_authored("__Key:__ value", 2, "Key")
    # Run length must match exactly: `_A_` is not inside `__A__`.
    assert not _wrap_is_authored("__A__ | B", 1, "A")
    # Accepted gap: matched by text, so a repeated span still counts.
    assert _wrap_is_authored("_A | B_ | _A_", 1, "A")
    print("  ✓  an authored wrapper is found on the source line")


def test_heading_keeps_its_markers():
    # A heading is a heading first: `# ___x___` behaves like `# ***x***`, which
    # keeps the markers and paints bold-italic in the heading's own family.
    ast = _processed("# ___Big heading___")
    assert _tiers(ast) == []
    assert "___Big heading___" in ast.children[0].content
    print("  ✓  headings keep their markers and take no tier")


def test_link_and_pill_leaves_take_no_tier():
    # Link variants own the `*` wrapper scheme; a standalone `code` element is
    # an ## Inline Code pill whose own style wins.
    assert _tiers(_processed("_[Muted link](/link)_")) == []
    assert _tiers(_processed("`_Code text_`")) == []
    print("  ✓  links and inline-code pills are left alone")


def test_round_trip_through_to_dict():
    ast = _processed("___$12,480.55___")
    restored = MarkdownGroupNode.from_dict(ast.to_dict())
    assert _tiers(restored) == _tiers(ast) == [("display", "$12,480.55")]
    print("  ✓  text_style survives the to_dict/from_dict round trip")


def test_criteria_path_agrees():
    # The real pipeline runs with SplitCriteria; bare process() skips the gate
    # inside _separate_structured_content_walk.
    ast = _processed_with_criteria("_Available balance_\n\n___$12,480.55___")
    assert _tiers(ast) == [
        ("muted", "Available balance"),
        ("display", "$12,480.55"),
    ]
    print("  ✓  the criteria path stamps the same tiers")


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


def test_tier_blocks_parse():
    t = _theme_from(
        "## Text Styles\n"
        "Text\n"
        "- Font size: 16\n"
        "\n"
        "Muted\n"
        "- Font size: 13\n"
        "- Font color: #8A87A0\n"
        "\n"
        "Lead\n"
        "- Font size: 20\n"
        "\n"
        "Display\n"
        "- Font size: 26\n"
        "- Font weight: bold\n"
    )
    assert tier_style("muted", t).font_size == 13
    assert tier_style("muted", t).color == skia.ColorSetARGB(255, 0x8A, 0x87, 0xA0)
    assert tier_style("lead", t).font_size == 20
    assert tier_style("display", t).font_size == 26
    assert tier_style("display", t).font_weight == "bold"
    print("  ✓  Muted / Lead / Display blocks parse")


def test_unset_tiers_derive_from_the_body_style():
    t = _theme_from("## Text Styles\nText\n- Font size: 20\n")
    assert t.muted is None and t.lead is None and t.display is None
    assert tier_style("muted", t).font_size == 20 * 0.85
    assert tier_style("lead", t).font_size == 20 * 1.25
    assert tier_style("display", t).font_size == 20 * 2.0
    assert tier_style("display", t).font_weight == "bold"
    print("  ✓  an omitted tier derives from Text")


def test_tier_block_order_does_not_matter():
    # Display states only a colour; its size must still be the body-derived
    # 2.0x even though Text is parsed AFTER it.
    t = _theme_from(
        "## Text Styles\nDisplay\n- Font color: #1A1A22\n\nText\n- Font size: 20\n"
    )
    assert tier_style("display", t).font_size == 40
    assert tier_style("display", t).color == skia.ColorSetARGB(255, 0x1A, 0x1A, 0x22)
    print("  ✓  a partial tier block is body-derived regardless of order")


def test_key_value_styles_are_independent_from_display():
    t = _theme_from(
        "## Text Styles\nText\n- Font size: 16\n\n"
        "Display\n- Font size: 26\n- Font weight: bold\n"
        "Key\n- Font size: 11\nValue\n- Font size: 30\n"
    )
    assert _kv_role_style(t, "value").font_size == 30
    assert _kv_role_style(t, "key").font_size == 11
    assert tier_style("display", t).font_size == 26
    print("  ✓  K-V pairs use independent Key/Value text styles")


def test_unset_key_value_fall_back_to_text():
    # A theme that states neither draws both sides of a display's pair in body
    # text; a `Text Overline` block styles nothing (ADR-205).
    t = _theme_from(
        "## Text Styles\nText\n- Font size: 16\nText Overline\n- Font size: 9\n"
    )
    assert t.key_style is None and t.value_style is None
    assert _kv_role_style(t, "key").font_size == 16
    assert _kv_role_style(t, "value").font_size == 16
    print("  ✓  unset Key/Value fall back to Text")


def test_repo_theme_wires_independent_key_value_blocks():
    t = parse_theme(Path("data/markdown/tests/THEME.md"))
    assert t.display is not None, "THEME.md should state a Display block"
    assert t.value_style is not None
    assert t.key_style is not None
    print("  ✓  THEME.md wires independent Key/Value blocks")


# ---------------------------------------------------------------------------
# Renderer resolution
# ---------------------------------------------------------------------------


def test_a_tier_beats_the_value_style():
    # An explicit instruction outranks the theme's uniform default, so an
    # authored tier on a value keeps its own size rather than taking `Value`.
    t = _theme_from(
        "## Text Styles\nText\n- Font size: 16\n\n"
        "Display\n- Font size: 26\nValue\n- Font size: 30\n"
    )
    _, valued = _effective_text_fonts("text", 0, _fonts(), t)
    _, tiered = _effective_text_fonts("text", 0, _fonts(), t, text_style="display")
    assert valued == 16 and tiered == 26
    print("  ✓  an authored tier keeps its size against Value")


def test_effective_fonts_use_the_tier_size():
    t = _theme_from(
        "## Text Styles\nText\n- Font size: 16\n\nDisplay\n- Font size: 26\n"
    )
    _, plain = _effective_text_fonts("text", 0, _fonts(), t)
    _, big = _effective_text_fonts("text", 0, _fonts(), t, text_style="display")
    assert plain == 16 and big == 26
    print("  ✓  a tiered leaf measures and draws at the tier's size")


def test_tier_beats_the_key_style_but_loses_to_a_heading():
    t = _theme_from(
        "## Text Styles\n"
        "Text\n- Font size: 16\n\n"
        "Key\n- Font size: 12\n\n"
        "Heading2\n- Font size: 32\n\n"
        "Display\n- Font size: 26\n"
    )
    _, key_size = _effective_text_fonts("key", 0, _fonts(), t)
    assert key_size == 12
    _, tiered_key = _effective_text_fonts("key", 0, _fonts(), t, text_style="display")
    assert tiered_key == 26, "an explicit tier outranks the Key default"
    _, heading = _effective_text_fonts("heading2", 0, _fonts(), t, text_style="display")
    assert heading == 32, "a heading is a heading first"
    print("  ✓  tier beats Key, heading beats tier")


def test_marker_style_mirrors_the_font_branch_order():
    t = _theme_from(
        "## Text Styles\n"
        "Text\n- Font size: 16\n- Marker background color: #FFF3CD\n\n"
        "Display\n- Font size: 26\n- Marker background color: #FFE8A3\n"
    )
    assert _marker_style(t, "text", 0).marker_bg_color == skia.ColorSetARGB(
        255, 0xFF, 0xF3, 0xCD
    )
    tiered = _marker_style(t, "text", 0, None, "display")
    assert tiered.marker_bg_color == skia.ColorSetARGB(255, 0xFF, 0xE8, 0xA3)
    print("  ✓  a marker inside a tiered leaf is painted by that tier")


_PURPLE = skia.ColorSetARGB(255, 0x88, 0x70, 0xC1)


def _glyph_tints(md: str, theme_md: str) -> dict[str, int | None]:
    """``{the word after the glyph: the tint the glyph was painted with}``, read
    off the prose drawer's calls through the real pipeline."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(theme_md)
        theme = session.load_theme(path)
    fonts = session.load_fonts(theme)
    root = session.group_markdown(md, session.load_grouping_kit())
    assert root is not None
    root, index = session.prepare(root, theme)
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 500.0)
    drawn: list[tuple[str, int | None]] = []
    real = layout_render._draw_text_with_emoji

    def record(canvas, text, *args, **kwargs):
        drawn.append((text, kwargs.get("emoji_color")))
        return real(canvas, text, *args, **kwargs)

    layout_render._draw_text_with_emoji = record
    try:
        session.render_image(scene, index, theme, fonts, ImageCache(), {}, 1.0)
    finally:
        layout_render._draw_text_with_emoji = real
    words = [w for w, _ in drawn]
    return {words[i + 1]: tint for i, (w, tint) in enumerate(drawn[:-1]) if "❤️" in w}


def test_a_glyph_follows_any_tier_even_one_inked_like_body_text():
    # The default theme's Lead shares body Text's ink: "is this text styled?"
    # cannot be read off the colour.
    tints = _glyph_tints(
        '"❤️" Plain\n\n_"❤️" Muted_\n\n__"❤️" Lead__\n\n___"❤️" Display___\n',
        "## Text Styles\n"
        "Text\n- Font color: #26262B\n\n"
        "Muted\n- Font color: #7C7C84\n\n"
        "Lead\n- Font color: #26262B\n\n"
        "Display\n- Font color: #202025\n\n"
        "## Emoji styles\n\n### Text\nColor: #8870C1\n",
    )
    assert tints == {
        "Plain": _PURPLE,
        "Muted": None,
        "Lead": None,
        "Display": None,
    }, tints
    print("  ✓  a glyph follows every tier's ink; plain text keeps the emoji tint")


def _key_paints(md: str, theme_md: str) -> dict[str, tuple[float, str, int]]:
    """``{key text: (size, typeface family+weight, ink)}`` for every K-V key the
    prose drawer painted, through the real pipeline."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(theme_md)
        theme = session.load_theme(path)
    fonts = session.load_fonts(theme)
    root = session.group_markdown(md, session.load_grouping_kit())
    assert root is not None
    root, index = session.prepare(root, theme)
    keys = {n.get("content") for n in index.values() if n.get("type") == "key"}
    scene = session.build_scene(LayoutGenerator(), root, index, theme, fonts, 500.0)
    painted: dict[str, tuple[float, str, int]] = {}
    real = layout_render.draw_styled_text_box

    def record(canvas, box, content, eff_fonts, size, color, *args, **kwargs):
        if content in keys:
            tf = eff_fonts.typeface
            painted[content] = (
                size,
                f"{tf.getFamilyName()}/{tf.fontStyle().weight()}",
                color,
            )
        return real(canvas, box, content, eff_fonts, size, color, *args, **kwargs)

    layout_render.draw_styled_text_box = record
    try:
        session.render_image(scene, index, theme, fonts, ImageCache(), {}, 1.0)
    finally:
        layout_render.draw_styled_text_box = real
    return painted


_BODY_THEME = "## Text Styles\nText\n- Font size: 15\n- Font color: #8A8F98\n"
_MUTED_KEY_THEME = (
    _BODY_THEME + "\nKey\n- Font size: 22\n- Font weight: 700\n- Font color: #0A0A0A\n"
)


def test_a_muted_key_keeps_the_key_style_and_takes_the_muted_ink():
    # On a key the Muted tier is a state, not a size, so a selected and an
    # unselected card line up. With no Muted block the ink is the tier's default
    # colour.
    md = "Customers: 7/8\n\n_Balance_: 7/8\n"
    paints = _key_paints(md, _MUTED_KEY_THEME)
    default_muted = tier_style("muted", Theme()).color
    (k_size, k_face, k_ink), (m_size, m_face, m_ink) = (
        paints["Customers"],
        paints["Balance"],
    )
    assert (m_size, m_face) == (k_size, k_face) and k_size == 22, paints
    assert k_ink == skia.ColorSetARGB(255, 0x0A, 0x0A, 0x0A), paints
    assert m_ink == default_muted, paints
    # A declared Muted block lends its colour — and only its colour.
    paints = _key_paints(
        md, _MUTED_KEY_THEME + "\nMuted\n- Font size: 11\n- Font color: #C0392B\n"
    )
    assert paints["Balance"] == (
        22,
        paints["Customers"][1],
        skia.ColorSetARGB(255, 0xC0, 0x39, 0x2B),
    ), paints
    # With no `Key` block a key is body text: still the same size, inked muted.
    paints = _key_paints(md, _BODY_THEME + "\nMuted\n- Font color: #C0392B\n")
    assert paints["Customers"][0] == paints["Balance"][0] == 15, paints
    assert paints["Balance"][2] == skia.ColorSetARGB(255, 0xC0, 0x39, 0x2B), paints
    print("  ✓  a muted key keeps its key style's size and weight, inked muted")


def test_a_global_tier_draws_its_own_family_and_weight():
    """A tier block under ## Text Styles names its family, or a weight between
    the body's regular and bold: it is drawn in that face, not the body's. Only
    a local role block (`#### Lead` under a level) used to reach it."""
    from md2ui import session

    theme = _theme_from(
        "## Fonts\n- assets/fonts/EBGaramond-Regular.ttf\n"
        "- assets/fonts/Inter_18pt-Regular.ttf\n- assets/fonts/Inter_18pt-SemiBold.ttf\n"
        "## Text Styles\nText\n- Font Name: Inter 18pt\n- Font weight: 400\n"
        "Lead\n- Font Name: EB Garamond\n- Font weight: 400\n"
        "Display\n- Font Name: Inter 18pt\n- Font weight: 600\n"
    )
    fonts = session.load_fonts(theme)
    grouped = session.group_markdown(
        "__Lead line__\n\n___Display line___\n", session.load_grouping_kit()
    )
    assert grouped is not None
    _, index = session.prepare(grouped, theme)
    faces = {}
    for nd in index.values():
        if nd.get("text_style") in ("lead", "display"):
            got, _ = _effective_text_fonts(nd["type"], 0, fonts, theme, node=nd)
            style = got.typeface.fontStyle()
            faces[nd["text_style"]] = (family_name(got.typeface), style.weight())
    assert faces["lead"][0] == "EB Garamond", faces
    assert faces["display"] == ("Inter 18pt", 600), faces
    print("  ✓  a global tier block draws its own family and weight")


TESTS = [
    test_a_global_tier_draws_its_own_family_and_weight,
    test_wrap_maps_run_length_to_tier,
    test_wrap_rejects_partial_and_unbalanced,
    test_wrap_rejects_two_separate_spans,
    test_run_gives_each_span_its_own_tier,
    test_run_may_mix_tiers,
    test_run_needs_at_least_two_whole_spans,
    test_run_defers_to_key_value_and_element_variants,
    test_run_splits_the_same_in_both_families,
    test_run_splits_into_sibling_leaves,
    test_whole_line_is_stamped_and_stripped,
    test_mid_sentence_is_not_a_tier,
    test_each_segment_takes_its_own_tier,
    test_tier_survives_datapoint_detection,
    test_tier_on_a_key_beats_the_key_style,
    test_a_cut_keeps_the_style_the_unsplit_line_had,
    test_wrap_is_authored_reads_the_source_line,
    test_heading_keeps_its_markers,
    test_link_and_pill_leaves_take_no_tier,
    test_round_trip_through_to_dict,
    test_criteria_path_agrees,
    test_tier_blocks_parse,
    test_unset_tiers_derive_from_the_body_style,
    test_tier_block_order_does_not_matter,
    test_key_value_styles_are_independent_from_display,
    test_unset_key_value_fall_back_to_text,
    test_repo_theme_wires_independent_key_value_blocks,
    test_a_tier_beats_the_value_style,
    test_effective_fonts_use_the_tier_size,
    test_tier_beats_the_key_style_but_loses_to_a_heading,
    test_marker_style_mirrors_the_font_branch_order,
    test_a_glyph_follows_any_tier_even_one_inked_like_body_text,
    test_a_muted_key_keeps_the_key_style_and_takes_the_muted_ink,
]

if __name__ == "__main__":
    print("Text Style Tier Tests")
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
