"""
Unit tests for the four wrapper variants of EMOJIS and CHIPS (inline code):

    🔎  /  `code`          Primary
    *🔎*                   Secondary
    **🔎**                 Tertiary
    ***🔎***               Quaternary

A chip alone has three more, because it reads `_` as its own family:

    _`code`_               Quinary
    __`code`__             Senary
    ___`code`___           Septenary

The mapping is by wrapper LENGTH — one more marker is one more step of
hierarchy. Links use the same rule (see tests/link_variant_tests.py); the table
lives once, in markdown_grouper._ELEMENT_VARIANT_BY_LEN.

The markers are gone from a peeled node's content, so the variant is captured
at peel time and persisted as `emoji_variant` / `code_variant`.

Run with: uv run python tests/emoji_chip_variant_tests.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "tests")

import skia
from markdown_datapoint_split_tests import _processed, _processed_with_criteria

from md2ui.pipeline.markdown_grouper import MarkdownGroupNode, NodeType
from md2ui.pipeline.theme import Theme, parse_theme


def _leaves(node: MarkdownGroupNode) -> list[tuple[str, str, str | None]]:
    """[(type, content, variant)] for every leaf, in document order."""
    out: list[tuple[str, str, str | None]] = []
    if not node.children:
        out.append(
            (str(node.type), node.content, node.emoji_variant or node.code_variant)
        )
    for c in node.children:
        out.extend(_leaves(c))
    return out


def _theme_from(md: str) -> Theme:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "THEME.md"
        p.write_text(md)
        return parse_theme(p)


# ---------------------------------------------------------------------------
# Grouper: the wrapper survives as a variant
# ---------------------------------------------------------------------------


def test_emoji_variants_by_wrapper_length():
    for wrap, variant in (
        ("", None),
        ("*", "secondary"),
        ("**", "tertiary"),
        ("***", "quaternary"),
    ):
        src = f"{wrap}🔎{wrap}"
        assert _leaves(_processed(src)) == [(NodeType.EMOJI, "🔎", variant)], src
    print("  ✓  🔎 / *🔎* / **🔎** / ***🔎*** → Primary/Secondary/Tertiary/Quaternary")


def test_chip_variants_by_wrapper_length():
    for wrap, variant in (
        ("", None),
        ("*", "secondary"),
        ("**", "tertiary"),
        ("***", "quaternary"),
    ):
        src = f"{wrap}`Code text`{wrap}"
        assert _leaves(_processed(src)) == [
            (NodeType.INLINE_CODE, "Code text", variant)
        ], src
    print("  ✓  `code` and its three wrapped spellings map the same way")


def test_underscores_are_synonyms_for_emojis():
    # `_` is an exact CommonMark synonym for `*` — for an emoji both spellings
    # must produce byte-identical trees. Chips are the exception, below.
    for a, u in (
        ("*🔎*", "_🔎_"),
        ("**🔎**", "__🔎__"),
        ("***🔎***", "___🔎___"),
    ):
        assert _leaves(_processed(a)) == _leaves(_processed(u)), (a, u)
    print("  ✓  underscore spellings are identical to the asterisk ones")


def test_chip_underscores_are_their_own_family():
    """A chip has seven looks: `_` starts a second ladder instead of repeating
    the `*` one, so a calendar grid can tell more than four days apart."""
    for wrap, variant in (("_", "quinary"), ("__", "senary"), ("___", "septenary")):
        src = f"{wrap}`5`{wrap}"
        assert _leaves(_processed(src)) == [(NodeType.INLINE_CODE, "5", variant)], src
    cells = _leaves(_processed("| a | b |\n|---|---|\n| _`1`_ | *`2`* |\n"))
    assert (NodeType.INLINE_CODE, "1", "quinary") in cells, cells
    assert (NodeType.INLINE_CODE, "2", "secondary") in cells, cells
    print("  ✓  _`x`_ / __`x`__ / ___`x`___ → Quinary / Senary / Septenary")


def test_content_never_keeps_the_markers():
    for src in (
        "*🔎*",
        "**🔎**",
        "***🔎***",
        "_🔎_",
        "__🔎__",
        "___🔎___",
        "*`C`*",
        "**`C`**",
        "___`C`___",
    ):
        for _t, content, _v in _leaves(_processed(src)):
            assert "*" not in content and "_" not in content, (src, content)
    print("  ✓  no wrapper markers leak into the drawn content")


def test_wrapper_around_a_larger_run_is_not_a_variant():
    # The wrapper belongs to the LINE, not the element: with nothing separating it
    # the emoji is not peeled, and the markers ride on with the text they wrap.
    # The leaf is a TEXT child of the root, not the root: the root is a container
    # and never a leaf (Phase 6.04 / _LABEL_IS_A_ROLE): a childless root draws
    # nothing.
    assert _leaves(_processed("**🗓 Calendar**")) == [
        ("text", "**🗓 Calendar**", None),
    ]
    assert _leaves(_processed("***⭐ Popular***")) == [
        ("text", "***⭐ Popular***", None),
    ]
    # Two chips inside one wrapped line: same reasoning. (Sequenced, not
    # `**`a` and `b`**` — prose between the spans makes them markers, and a
    # marker has no variant to abstain from.)
    assert [v for _t, _c, v in _leaves(_processed("**`a` `b`**"))] == [None, None]
    print("  ✓  a wrapper spanning a larger run assigns no variant")


def test_plain_emoji_contexts_are_untouched():
    assert _leaves(_processed("🔑 - Add a passkey")) == [
        (NodeType.EMOJI, "🔑", None),
        (NodeType.SEGMENT, "Add a passkey", None),
    ]
    print("  ✓  an ordinary peeled emoji keeps no variant")


def test_variant_survives_the_round_trip():
    for src in ("**🔎**", "*`Code text`*"):
        ast = _processed(src)
        restored = MarkdownGroupNode.from_dict(ast.to_dict())
        assert _leaves(restored) == _leaves(ast), src
    print("  ✓  emoji_variant / code_variant survive to_dict/from_dict")


def test_a_legacy_emoji_kind_migrates_on_both_load_paths():
    """A persisted `peeled` must reach the GENERATOR and the DRAWER as the same
    kind, or one measures an inline glyph while the other paints a badge.

    Both `from_dict` and the renderer's node_index walk go through
    `normalize_emoji_kind`, so a legacy spelling in a stale grouping-ast.json
    reads the same on both.
    """
    from md2ui.pipeline import layout_render as LR
    from md2ui.pipeline.grouper_types import normalize_emoji_kind

    assert normalize_emoji_kind("peeled") == "text"
    for kind in ("text", "alone", "heading", None):
        assert normalize_emoji_kind(kind) == kind, kind

    d = _processed("⚠ - Heads up").to_dict()
    emojis = []

    def stamp(n):
        if n.get("type") == "emoji":
            n["emoji_kind"] = "peeled"  # write the legacy spelling back
            emojis.append(n)
        for c in n.get("children") or []:
            stamp(c)

    stamp(d)
    assert emojis, "fixture must contain a peeled emoji leaf"

    index: dict = {}
    LR._walk(d, index)  # the DRAWER's view
    restored = MarkdownGroupNode.from_dict(d)  # the GENERATOR's view

    def kinds(node):
        out = []
        if node.type == NodeType.EMOJI:
            out.append(node.emoji_kind)
        for c in node.children:
            out.extend(kinds(c))
        return out

    drawn = [n["emoji_kind"] for n in emojis]
    assert drawn == ["text"] * len(drawn), drawn
    assert kinds(restored) == drawn, (kinds(restored), drawn)
    print("  \u2713  a legacy emoji_kind migrates on BOTH load paths")


def test_criteria_path_agrees():
    assert _leaves(_processed_with_criteria("***🔎***")) == [
        (NodeType.EMOJI, "🔎", "quaternary")
    ]
    assert _leaves(_processed_with_criteria("**`Code text`**")) == [
        (NodeType.INLINE_CODE, "Code text", "tertiary")
    ]
    print("  ✓  the real (criteria) pipeline stamps the same variants")


def test_display_tiers_do_not_claim_the_wrapper():
    # `_x_` is the Muted tier for ordinary text, but for an emoji or a chip the
    # element's own variant owns the wrapper.
    # The tier is read off the LEAF: the root is a container and never a leaf
    # (Phase 6.04), and a tier is a leaf property, so it travels to the child
    # with the content rather than being left on the container.
    assert _processed("_Muted text_").children[0].text_style == "muted"
    for src in ("_🔎_", "__`C`__"):
        for leaf in _leaves(_processed(src)):
            assert leaf[2] is not None, src
    assert _processed("_🔎_").text_style is None
    print("  ✓  emoji/chip variants win over the text tiers for the same markers")


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


def test_emoji_variant_inherits_primary():
    t = _theme_from(
        "## Emoji styles\n"
        "### Primary\n"
        "Icon size: 32\n"
        "Padding: 8\n"
        "Shape: square\n"
        "Background colors:\n"
        "- #E8E6FB\n"
        "\n"
        "### Secondary\n"
        "Background colors:\n"
        "- #FFE8A3\n"
    )
    sec = t.emojis.resolved("secondary")
    # Stated key wins…
    assert sec.fill.bg_colors == [skia.ColorSetARGB(255, 0xFF, 0xE8, 0xA3)]
    # …and it REPLACES Primary's palette rather than extending it.
    assert len(sec.fill.bg_colors) == 1
    # Everything unstated is inherited.
    assert sec.icon_size == 32 and sec.shape == "square"
    assert sec.fill.padding.left == 8
    # An undeclared variant falls all the way back to Primary.
    assert t.emojis.resolved("quaternary") is t.emojis.primary
    assert t.emojis.resolved(None) is t.emojis.primary
    print("  ✓  an emoji variant inherits Primary and replaces list keys")


def test_emoji_variant_block_order_does_not_matter():
    t = _theme_from(
        "## Emoji styles\n### Secondary\nShape: circle\n\n### Primary\nIcon size: 40\n"
    )
    sec = t.emojis.resolved("secondary")
    assert sec.shape == "circle"
    assert sec.icon_size == 40, "inherits Primary even though Primary came after"
    print("  ✓  a variant block may precede Primary")


def test_chip_variants_and_flat_block_back_compat():
    t = _theme_from(
        "## Inline Code\n"
        "Corner radius: 16\n"
        "Padding: 4\n"
        "Fill color: #CCC4FB\n"
        "### Secondary\n"
        "Fill color: #FFE8A3\n"
    )
    # The subsection-less keys configure the base.
    assert t.inline_code.corner_radius == 16
    assert t.inline_code.fill_color == skia.ColorSetARGB(255, 0xCC, 0xC4, 0xFB)
    sec = t.inline_code.resolved("secondary")
    assert sec.fill_color == skia.ColorSetARGB(255, 0xFF, 0xE8, 0xA3)
    assert sec.corner_radius == 16 and sec.padding.left == 4, "inherits the base"
    assert t.inline_code.resolved("tertiary") is t.inline_code
    print("  ✓  chip variants inherit the flat base block")


def test_chip_variant_text_style():
    t = _theme_from(
        "## Text Styles\n"
        "Inline Code\n"
        "- Font size: 14\n"
        "\n"
        "Inline Code Secondary\n"
        "- Font color: #4B3F00\n"
        "\n"
        "## Inline Code\n"
        "Fill color: #CCC4FB\n"
        "### Secondary\n"
        "Fill color: #FFE8A3\n"
    )
    sec = t.inline_code.resolved("secondary")
    assert sec.fill_color == skia.ColorSetARGB(255, 0xFF, 0xE8, 0xA3)
    assert sec.text_style is not None
    assert sec.text_style.color == skia.ColorSetARGB(255, 0x4B, 0x3F, 0x00)
    print("  ✓  'Inline Code <Variant>' text styles reach their variant")


def test_chip_underscore_variants_inherit_the_base():
    t = _theme_from(
        "## Text Styles\n"
        "Inline Code Senary\n"
        "- Font size: 20\n"
        "\n"
        "## Inline Code\n"
        "Corner radius: 9\n"
        "Fill color: #111111\n"
        "### Quinary\n"
        "Fill color: #FF0000\n"
    )
    q = t.inline_code.resolved("quinary")
    assert q.fill_color == skia.ColorSetARGB(255, 0xFF, 0, 0)
    assert q.corner_radius == 9, "inherits the base"
    senary = t.inline_code.resolved("senary")
    assert senary.text_style is not None and senary.text_style.font_size == 20
    assert t.inline_code.resolved("septenary") is t.inline_code
    bare = Theme()
    for v in ("quinary", "senary", "septenary"):
        assert bare.inline_code.resolved(v) is bare.inline_code, v
    print("  ✓  Quinary/Senary/Septenary blocks inherit the base; absent ⇒ base")


def test_repo_theme_wires_all_four():
    # Deliberately asserts the WIRING, not the palette: the shipped colors and
    # sizes are the theme author's to tune, and pinning them here would break
    # the suite every time THEME.md is edited.
    t = parse_theme(Path("data/markdown/tests/THEME.md"))
    for v in ("secondary", "tertiary", "quaternary"):
        assert t.emojis.resolved(v) is not t.emojis.primary, v
        assert t.inline_code.resolved(v) is not t.inline_code, v
    # An undeclared variant must still resolve, falling back to the base.
    bare = Theme()
    for v in ("secondary", "tertiary", "quaternary"):
        assert bare.emojis.resolved(v) is bare.emojis.primary
        assert bare.inline_code.resolved(v) is bare.inline_code
    print("  ✓  THEME.md declares all four emoji and chip variants")


def test_wrapped_chip_run_peels_like_an_unwrapped_one():
    # A match covers `x` but not the emphasis around it, so the gap between two
    # matches is `* *` — not whitespace — and run detection must not stop at the
    # first chip. Each chip takes the
    # variant ITS OWN wrapper selects.
    assert _leaves(_processed("`A` `B` `C`")) == [
        (NodeType.INLINE_CODE, "A", None),
        (NodeType.INLINE_CODE, "B", None),
        (NodeType.INLINE_CODE, "C", None),
    ]
    for wrap, variant in (
        ("*", "secondary"),
        ("**", "tertiary"),
        ("***", "quaternary"),
        ("_", "quinary"),
        ("__", "senary"),
        ("___", "septenary"),
    ):
        src = " ".join(f"{wrap}`{c}`{wrap}" for c in "ABC")
        assert _leaves(_processed(src)) == [
            (NodeType.INLINE_CODE, "A", variant),
            (NodeType.INLINE_CODE, "B", variant),
            (NodeType.INLINE_CODE, "C", variant),
        ], src
    print("  ✓  a run of wrapped chips peels, each with its own variant")


def test_wrapped_chip_run_leaves_no_markers():
    for wrap in ("*", "**", "***", "_", "__", "___"):
        src = " ".join(f"{wrap}`{c}`{wrap}" for c in ("❤️", "Label"))
        for _t, content, _v in _leaves(_processed(src)):
            assert "*" not in content and "_" not in content and "`" not in content, (
                src,
                content,
            )
    print("  ✓  no wrapper or backtick survives into a run's chips")


def test_a_wrapper_spanning_the_whole_run_still_abstains():
    # `**`a` `b`**` wraps the LINE, not either chip.
    assert [v for _t, _c, v in _leaves(_processed("**`a` `b`**"))] == [None, None]
    print("  ✓  a wrapper spanning the whole line still assigns no variant")


# ---------------------------------------------------------------------------
# A chip variant's text style inherits the base `Inline Code` one, and its face
# is resolved from the result, in measurement and in paint alike (ADR-400).
# ---------------------------------------------------------------------------

_WORK_SANS = "\n".join(
    f"- {Path.cwd() / 'assets' / 'fonts' / f'WorkSans-{w}.ttf'}"
    for w in ("Regular", "Bold")
)


def _chip_kit(text_styles: str):
    """(theme, fonts) for a theme loaded through the real session path."""
    from md2ui import session

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "THEME.md"
        p.write_text(
            f"## Fonts\n{_WORK_SANS}\n## Text Styles\n"
            "Text\n- Font Name: Work Sans\n- Font size: 16\n\n"
            "Inline Code\n- Font Name: Work Sans\n- Font size: 18\n"
            "- Font color: #112233\n\n" + text_styles
        )
        theme = session.load_theme(p)
        return theme, session.load_fonts(theme)


def _chip_width(theme, fonts, variant: str | None) -> float:
    from md2ui.pipeline.render_measure import _leaf_natural_width

    nd = {"type": "inline_code", "content": "advice_code", "code_variant": variant}
    return _leaf_natural_width(nd, float("inf"), fonts, theme)


def test_chip_variant_stating_only_a_weight_keeps_the_base():
    from md2ui.pipeline.render_metrics import _code_font

    theme, fonts = _chip_kit("Inline Code Tertiary\n- Font weight: 700\n")
    ts = theme.inline_code.resolved("tertiary").text_style
    assert ts is not None
    assert ts.font_name == "Work Sans" and ts.font_size == 18, "inherits the base"
    assert ts.color == skia.ColorSetARGB(255, 0x11, 0x22, 0x33), "inherits the base"
    font, size = _code_font(theme, "tertiary", fonts.mono)
    face = font.getTypeface()
    assert size == 18
    assert face.getFamilyName() == "Work Sans", face.getFamilyName()
    assert face.fontStyle().weight() == 700, face.fontStyle().weight()
    assert fonts.mono.fontStyle().weight() == 400, "the base chip stays regular"
    print("  ✓  a variant stating only a weight keeps the base family, size, colour")


def test_chip_variant_family_and_weight_reach_the_measure():
    theme, fonts = _chip_kit(
        "Inline Code Quaternary\n- Font Name: Work Sans\n- Font weight: 700\n"
    )
    bold = _chip_width(theme, fonts, "quaternary")
    regular = _chip_width(theme, fonts, None)
    assert bold > regular, (bold, regular)
    print("  ✓  a bold variant is measured wider than the regular chip")


def test_chip_without_a_variant_text_style_is_unchanged():
    from md2ui.pipeline.render_metrics import _code_font
    from md2ui.pipeline.render_style import _code_size

    theme, fonts = _chip_kit("")
    for v in (None, "secondary", "septenary"):
        font, size = _code_font(theme, v, fonts.mono)
        assert font.getTypeface() is fonts.mono, v
        assert size == _code_size(theme, v) == 18, v
    assert _chip_width(theme, fonts, "secondary") == _chip_width(theme, fonts, None)
    print("  ✓  a chip with no variant text style keeps the base face and size")


def test_chip_variant_stating_only_a_colour_keeps_the_base_weight():
    from md2ui.pipeline.render_metrics import _code_font

    # The variant comes first in the file: the base it inherits is the final one.
    theme = _theme_from(
        "## Text Styles\n"
        "Inline Code Secondary\n- Font color: #FF0000\n\n"
        "Inline Code\n- Font size: 15\n- Font weight: 700\n"
    )
    ts = theme.inline_code.resolved("secondary").text_style
    assert ts is not None
    assert ts.color == skia.ColorSetARGB(255, 0xFF, 0, 0)
    assert ts.font_weight == "700", "inherits the base even when stated after it"
    assert ts.font_size == 15
    _theme, fonts = _chip_kit("Inline Code Secondary\n- Font color: #FF0000\n")
    font, _size = _code_font(_theme, "secondary", fonts.mono)
    assert font.getTypeface() is fonts.mono, "same family and weight as the base"
    print("  ✓  a variant stating only a colour keeps the base weight and face")


TESTS = [
    test_emoji_variants_by_wrapper_length,
    test_chip_variants_by_wrapper_length,
    test_wrapped_chip_run_peels_like_an_unwrapped_one,
    test_wrapped_chip_run_leaves_no_markers,
    test_a_wrapper_spanning_the_whole_run_still_abstains,
    test_underscores_are_synonyms_for_emojis,
    test_chip_underscores_are_their_own_family,
    test_content_never_keeps_the_markers,
    test_wrapper_around_a_larger_run_is_not_a_variant,
    test_plain_emoji_contexts_are_untouched,
    test_variant_survives_the_round_trip,
    test_a_legacy_emoji_kind_migrates_on_both_load_paths,
    test_criteria_path_agrees,
    test_display_tiers_do_not_claim_the_wrapper,
    test_emoji_variant_inherits_primary,
    test_emoji_variant_block_order_does_not_matter,
    test_chip_variants_and_flat_block_back_compat,
    test_chip_variant_text_style,
    test_chip_underscore_variants_inherit_the_base,
    test_repo_theme_wires_all_four,
    test_chip_variant_stating_only_a_weight_keeps_the_base,
    test_chip_variant_family_and_weight_reach_the_measure,
    test_chip_without_a_variant_text_style_is_unchanged,
    test_chip_variant_stating_only_a_colour_keeps_the_base_weight,
]

if __name__ == "__main__":
    print("Emoji / Chip Variant Tests")
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
