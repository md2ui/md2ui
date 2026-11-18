"""
Consistency between the three inline ELEMENTS — chips, links and emojis.

Chips, separated links and separated emojis follow the same split / align /
spacing rules. The split is one grouper pass (`_split_elements`), so the run
shapes below come out identical; align and spacing come from the generator
flagging an element run `line_split` like any other one-line strip.

Also pinned:

  #3  a right-aligned document draws its buttons and chips flush RIGHT, as it
      does its emojis (``draw_link_box`` / ``draw_code_box`` and their
      ``_text_extent_rect`` twins are three-way).

  #6  the generator measures a leaf with every field the DRAW path reads back
      — ``code_variant``, ``emoji_variant``, ``in_key``, ``table_role``. The
      test is measure == draw; a hard-coded width would just re-encode
      whichever side was wrong.

Run with: uv run python tests/layout_element_consistency_tests.py
"""

import sys
from pathlib import Path

sys.path.insert(0, "tests")

from markdown_datapoint_split_tests import (
    _processed_with_criteria as _criteria_processed,
)

from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline import render_measure as RMS
from md2ui.pipeline import layout_render as LR
from md2ui.pipeline import render_spacing as RS
from md2ui.pipeline.layout_render import LayoutBox
from md2ui.pipeline.theme import parse_theme
from md2ui.utils.font_loader import (
    load_custom_fonts,
    resolve_typeface,
    weight_from_str,
)

TOL = 0.01


def _walk(node):
    yield node
    for c in node.children:
        yield from _walk(c)


def _themed(align: str | None = None):
    theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    if align is not None:
        theme.root.align = align
    custom = load_custom_fonts(theme.font_paths)
    name = theme.text.font_name or "Arial"
    bw = weight_from_str(theme.text.font_weight)

    def tf(w, i):
        return resolve_typeface(name, w, i, custom)

    return theme, FontSet(
        tf(bw, False),
        tf(700, False),
        tf(bw, True),
        tf(700, True),
        tf(bw, False),
        None,
        {},
    )


# ---------------------------------------------------------------------------
# #3 — right-align reaches links and chips, not just emojis
# ---------------------------------------------------------------------------


def _extent_x(nd: dict, align: str) -> tuple[float, float]:
    """(rect.left, box width) for a leaf in a wide box under *align*."""
    theme, fonts = _themed(align)
    box = LayoutBox(x=0.0, y=0.0, width=600.0, height=60.0)
    rect = RMS._text_extent_rect(box, nd, fonts, theme)
    assert rect is not None, nd
    return rect.left(), 600.0


def test_a_chip_honors_right_align():
    nd = {"type": "inline_code", "content": "Label"}
    left_x, _ = _extent_x(nd, "left")
    right_x, w = _extent_x(nd, "right")
    assert abs(left_x) < 20.0, left_x
    assert right_x > w / 2, (
        f"a right-aligned chip must sit in the right half, got x={right_x}"
    )
    print("  ✓  a chip honors Align: Right")


def test_a_link_honors_right_align():
    nd = {
        "type": "link",
        "content": "[Buy](/b)",
        "link_variant": "primary",
        "link_label": "Buy",
        "link_is_emoji": False,
        "link_disabled": False,
    }
    left_x, _ = _extent_x(nd, "left")
    right_x, w = _extent_x(nd, "right")
    assert abs(left_x) < 20.0, left_x
    assert right_x > w / 2, (
        f"a right-aligned link must sit in the right half, got x={right_x}"
    )
    print("  ✓  a link honors Align: Right")


def test_center_align_is_unchanged():
    """Left and center alignment are unaffected."""
    for nd in (
        {"type": "inline_code", "content": "Label"},
        {
            "type": "link",
            "content": "[Buy](/b)",
            "link_variant": "primary",
            "link_label": "Buy",
            "link_is_emoji": False,
            "link_disabled": False,
        },
    ):
        left_x, w = _extent_x(nd, "left")
        mid_x, _ = _extent_x(nd, "center")
        assert abs(left_x) < 20.0, (nd["type"], left_x)
        assert left_x < mid_x < w / 2 + 100, (nd["type"], mid_x)
    print("  ✓  left and center placement unchanged")


# ---------------------------------------------------------------------------
# #6 — the generator measures what the renderer draws
# ---------------------------------------------------------------------------

_DROPPED = ("code_variant", "emoji_variant", "in_key", "table_role")


def _measure_vs_draw(node_fields: dict) -> tuple[float | None, float]:
    """(generator width, renderer width) for one leaf."""
    theme, fonts = _themed()

    class _Node:
        children: list = []
        render_properties = None

        def __init__(self, d):
            self.type = d["type"]
            self.content = d["content"]
            self.link_variant = d.get("link_variant")
            self.link_label = d.get("link_label")
            self.link_is_emoji = d.get("link_is_emoji", False)
            self.link_disabled = d.get("link_disabled", False)
            for k in ("emoji_kind", "emoji_index", *_DROPPED):
                setattr(self, k, d.get(k))

    measured = LR.make_width_measurer(fonts, theme)(_Node(node_fields), None)
    drawn = RMS._leaf_natural_width(node_fields, float("inf"), fonts, theme, None)
    return measured, drawn


def test_the_generator_measures_what_the_renderer_draws():
    for label, nd in [
        (
            "quaternary chip",
            {"type": "inline_code", "content": "x", "code_variant": "quaternary"},
        ),
        (
            "secondary chip",
            {"type": "inline_code", "content": "x", "code_variant": "secondary"},
        ),
        (
            "quaternary badge",
            {
                "type": "emoji",
                "content": "🔎",
                "emoji_kind": "alone",
                "emoji_variant": "quaternary",
            },
        ),
        (
            "tertiary badge",
            {
                "type": "emoji",
                "content": "🔎",
                "emoji_kind": "alone",
                "emoji_variant": "tertiary",
            },
        ),
        (
            "key text-emoji",
            {"type": "emoji", "content": "⭐", "emoji_kind": "text", "in_key": True},
        ),
        (
            "table-role emoji",
            {
                "type": "emoji",
                "content": "⭐",
                "emoji_kind": "text",
                "table_role": "header",
            },
        ),
    ]:
        m, d = _measure_vs_draw(nd)
        assert m is not None, label
        assert abs(m - d) < TOL, f"{label}: measured {m}, drawn {d}"
    print("  ✓  measured width == drawn width for every element kind")


def test_the_dropped_fields_actually_move_the_width():
    """Without this the test above could pass on a fix that changed nothing.

    Only the fields that DO move a width in this theme are asserted:
    ``code_variant`` happens to share size and padding across the inline-code
    variants here, so it has no measurable effect — it is carried anyway,
    because the draw path reads it and the two must not diverge if the theme
    ever differentiates them.
    """
    theme, fonts = _themed()
    for label, nd in [
        (
            "quaternary badge",
            {
                "type": "emoji",
                "content": "🔎",
                "emoji_kind": "alone",
                "emoji_variant": "quaternary",
            },
        ),
        (
            "key text-emoji",
            {"type": "emoji", "content": "⭐", "emoji_kind": "text", "in_key": True},
        ),
    ]:
        stripped = {k: v for k, v in nd.items() if k not in _DROPPED}
        without = RMS._leaf_natural_width(stripped, float("inf"), fonts, theme, None)
        with_it = RMS._leaf_natural_width(nd, float("inf"), fonts, theme, None)
        assert abs(without - with_it) > 1.0, (
            f"{label}: dropping the field changed nothing ({without} vs {with_it}) "
            "— the regression this guards is not reproducible"
        )
    print("  ✓  dropping emoji_variant / in_key really does mis-measure")


# ---------------------------------------------------------------------------
# One rule: chips, links and emojis split, align and space the same way
# ---------------------------------------------------------------------------


def _leaves(node) -> list[tuple[str, str]]:
    """(type, content) for every leaf, in document order."""
    if not node.children:
        return [(str(node.type), node.content)] if node.content else []
    out: list[tuple[str, str]] = []
    for c in node.children:
        out.extend(_leaves(c))
    return out


def _one_run(src: str):
    """The single container a one-line element run collapses to."""
    ast = _criteria_processed(src)
    assert len(ast.children) == 1, (src, ast.to_dict())
    return ast.children[0]


def test_the_four_run_shapes_are_identical():
    """Pure chips, pure links, pure emojis and the three mixed: one shape.

    Each is a flat run of element leaves under ONE container flagged as the
    pieces of a single source line, so every run takes the same generator path.
    """
    for src, kinds in [
        ("`Sale` `New`", ["inline_code", "inline_code"]),
        ("[Buy](/b) [Info](/i)", ["link", "link"]),
        ("\u2b50 \U0001f680", ["emoji", "emoji"]),
        ("\u2b50 [Buy](/b) `Sale`", ["emoji", "link", "inline_code"]),
    ]:
        run = _one_run(src)
        assert run.line_split_group, f"{src}: run must flow as one line"
        assert [t for t, _ in _leaves(run)] == kinds, (src, _leaves(run))
        assert all(not c.children for c in run.children), (src, run.to_dict())
    print("  \u2713  pure chips / links / emojis and mixed share one shape")


def test_a_mixed_run_keeps_authored_order():
    """The link is where the author put it: `_apply_split_result` does not
    hoist LINKs out of the strip.
    """
    assert [t for t, _ in _leaves(_one_run("\u2b50 [Buy](/b) `Sale`"))] == [
        "emoji",
        "link",
        "inline_code",
    ]
    assert [t for t, _ in _leaves(_one_run("`Sale` [Buy](/b) \u2b50"))] == [
        "inline_code",
        "link",
        "emoji",
    ]
    print("  \u2713  a mixed run keeps authored order")


def test_separation_is_what_makes_an_element_for_all_three_kinds():
    """Run it into prose → inline. Separate it → an element. Same for all three.

    This is the authoring control: separation buys a backtick its chip, a link
    its button, and an emoji its `### Primary` style instead of `### Text`.
    """
    for inline_src, sep_src, kind in [
        ("This is the `Label`", "text - `Label`", "inline_code"),
        ("Read the [Buy](/b) here", "text - [Buy](/b)", "link"),
        ("\u2b50 Popular", "\u2b50 - Popular", "emoji"),
    ]:
        inline_leaves = _leaves(_criteria_processed(inline_src))
        # A one-line document's single leaf IS the root, so the label is
        # "root"; what matters is that the line did not split at all.
        assert len(inline_leaves) == 1 and inline_leaves[0][1] == inline_src, (
            f"{inline_src!r} must stay ONE leaf, got {inline_leaves}"
        )
        sep_leaves = _leaves(_criteria_processed(sep_src))
        assert kind in [t for t, _ in sep_leaves], (
            f"{sep_src!r} must yield a {kind}, got {sep_leaves}"
        )
    print("  \u2713  separation makes an element; adjacency keeps it inline")


def test_a_separated_emoji_is_a_badge_not_a_text_glyph():
    """`emoji_kind` follows the peel, not `line_split_group`.

    `alone` selects `## Emoji styles > ### Primary`; `text` selects `### Text`,
    which is reserved for an emoji whose CONTAINER styles it as text.
    """
    for src in ("\u2b50 - Popular", "\u2b50 \U0001f680", "\u2b50 `Popular`"):
        kinds = [
            n.emoji_kind
            for n in _walk(_criteria_processed(src))
            if str(n.type) == "emoji"
        ]
        assert kinds and set(kinds) == {"alone"}, (src, kinds)
    # A heading emoji is still a heading emoji.
    kinds = [
        n.emoji_kind
        for n in _walk(_criteria_processed("# \u2b50 - Heading"))
        if str(n.type) == "emoji"
    ]
    assert kinds == ["heading"], kinds
    print("  \u2713  a separated emoji is a Primary badge; headings unchanged")


def test_an_element_row_baseline_aligns():
    """A row of elements shares a baseline, whatever kinds it mixes.

    `_row_valign_offsets` returns zeros for a row that is not `line_split`, so
    the generator's element branch must pass the flag for any element kind.
    """
    idx = {
        "chip": {"type": "inline_code", "content": "Sale"},
        "link": {
            "type": "link",
            "content": "[Buy](/b)",
            "link_variant": "primary",
            "link_label": "Buy",
            "link_is_emoji": False,
            "link_disabled": False,
        },
        "emoji": {"type": "emoji", "content": "\u2b50", "emoji_kind": "alone"},
    }
    theme, fonts = _themed()
    row = LR.LayoutNode(
        type="row",
        ratios=[1.0, 1.0, 1.0],
        children=[
            LR.LayoutNode(type="-", ratios=[], children=[], content_id=c)
            for c in ("emoji", "link", "chip")
        ],
    )
    row.line_split = True
    # Pin the mode: this test is about BASELINE alignment, so it must not read
    # whatever `Line align` the repo THEME.md happens to carry (own beats root).
    row.render_properties = {"line_align": "baseline"}
    widths = [100.0, 100.0, 100.0]
    heights = [40.0, 40.0, 40.0]
    sections = [False, False, False]

    def offsets():
        return RMS._row_valign_offsets(
            row, row.children, widths, heights, sections, idx, fonts, theme
        )

    got = offsets()
    assert any(o > 0.0 for o in got), (
        f"a flagged element row must shift cells onto one baseline, got {got}"
    )
    row.line_split = False
    assert offsets() == [0.0, 0.0, 0.0], "an unflagged row stays top-aligned"
    print("  \u2713  an element row baseline-aligns; an unflagged row does not")


def test_element_spacing_reaches_a_group_of_emojis():
    """Pure-element predicates share the complete element-leaf vocabulary.

    A GROUP of peeled emojis gets the element gap, as a lone emoji LEAF does,
    not the wider group gap.
    """
    from md2ui.pipeline.generator_units import _is_pure_element_group
    from md2ui.pipeline.grouper_types import ELEMENT_LEAF_TYPES

    assert set(ELEMENT_LEAF_TYPES) == {
        "link",
        "inline_code",
        "emoji",
        "drawing_element",
    }
    for src in (
        "\u2b50 \U0001f680",
        "`a` `b`",
        "[a](/a) [b](/b)",
        "\u2b50 [a](/a) `b`",
    ):
        assert _is_pure_element_group(_one_run(src)), src
    # A run with a text piece in it is not a pure element group.
    assert not _is_pure_element_group(_one_run("\u2b50 - Popular"))

    idx = {
        "e1": {"type": "emoji", "content": "\u2b50", "emoji_kind": "alone"},
        "e2": {"type": "emoji", "content": "\U0001f680", "emoji_kind": "alone"},
    }
    block = LR.LayoutNode(
        type="row",
        ratios=[1.0, 1.0],
        children=[
            LR.LayoutNode(type="-", ratios=[], children=[], content_id=c)
            for c in ("e1", "e2")
        ],
    )
    assert RS._is_pure_element_block(block, idx), "a group of emojis is pill-y"
    print("  \u2713  element spacing reaches a group of emojis")


TESTS = [
    test_the_four_run_shapes_are_identical,
    test_a_mixed_run_keeps_authored_order,
    test_separation_is_what_makes_an_element_for_all_three_kinds,
    test_a_separated_emoji_is_a_badge_not_a_text_glyph,
    test_an_element_row_baseline_aligns,
    test_element_spacing_reaches_a_group_of_emojis,
    test_a_chip_honors_right_align,
    test_a_link_honors_right_align,
    test_center_align_is_unchanged,
    test_the_generator_measures_what_the_renderer_draws,
    test_the_dropped_fields_actually_move_the_width,
]


if __name__ == "__main__":
    print("Element consistency (align + measure/draw) tests")
    print("=" * 60)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 60)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
