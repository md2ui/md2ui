"""
Unit tests for COLOR ROTATION — a THEME.md color property that lists two or more
colors cycles across the elements it styles, instead of painting them all alike.

Three pieces, tested here in that order:

  1. the grouper stamps ``rotation_index`` (the node's ordinal among its
     same-channel peers inside the enclosing section) and ``rotation_chain``
     (the section levels above it), Phase 6.25;
  2. the theme parser reads ONE key per property that takes either an inline
     color or a bullet list, plus the ``Rotate <kind> colors`` gates;
  3. the renderer's ``_rotate_color`` picks the slot, and pins to color 0 for a
     one-color list or a gate turned off — so a theme of single colors never
     rotates.

Run with: uv run python tests/color_rotation_tests.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "tests")

from markdown_datapoint_split_tests import _processed_with_criteria

from md2ui.pipeline.layout_render import _rotated_code_style
from md2ui.pipeline.render_colors import (
    _rotate_color,
    _rotation_enabled,
    _synced_slot,
)
from md2ui.pipeline.markdown_grouper import MarkdownGroupNode
from md2ui.pipeline.theme import Theme, parse_theme

# The color-rotation samples live with their kind; sample-1 is a test sample.
SAMPLE_1 = Path("data/markdown/tests/color-rotation-five-sections")
SAMPLE_2 = Path("data/markdown/tests-render/landing-pages/d-studio-landing-page")
SAMPLE_3 = Path("data/markdown/tests-render/color-cycling/icons")
SAMPLE_4 = Path("data/markdown/tests-render/color-cycling/ulvin-omarov-meetup-app")
SAMPLE_7 = Path("data/markdown/tests/tests-card-section-stop.md")


def _theme(text: str) -> Theme:
    """parse_theme over an inline THEME.md body."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
        fh.write(text)
        path = Path(fh.name)
    try:
        return parse_theme(path)
    finally:
        path.unlink()


def _collect(node: MarkdownGroupNode, pred) -> list[MarkdownGroupNode]:
    """Every node satisfying *pred*, in document order."""
    found = [node] if pred(node) else []
    for child in node.children:
        found.extend(_collect(child, pred))
    return found


def _emoji_slots(ast: MarkdownGroupNode) -> list[int]:
    return [n.rotation_index for n in _collect(ast, lambda n: n.type == "emoji")]


def _section_slots(ast: MarkdownGroupNode, level: int) -> list[int]:
    return [
        n.rotation_index
        for n in _collect(ast, lambda n: n.heading_group and n.heading_level == level)
    ]


# ---------------------------------------------------------------------------
# 1. The grouper's annotation
# ---------------------------------------------------------------------------


def test_siblings_across_containers_share_one_cycle():
    """Six emojis in six sibling list items are ONE cycle, not six lone zeros."""
    ast = _processed_with_criteria((SAMPLE_3 / "content.md").read_text())
    assert _emoji_slots(ast) == [0, 1, 2, 3, 4, 5], _emoji_slots(ast)


def test_a_section_resets_the_cycle():
    """Each `## ` opens a fresh cycle for the elements it owns.

    sample-4 is the whole reason the scope is the section: three `### ` cards
    cycle under "Upcoming meetups", and the emoji badges under the NEXT `## `
    restart at 0 rather than continuing at 3.
    """
    ast = _processed_with_criteria((SAMPLE_4 / "content.md").read_text())
    assert _section_slots(ast, 3) == [0, 1, 2], _section_slots(ast, 3)
    # Upper cards: one emoji each, each alone in its own `### ` section.
    # Lower list: three emojis sharing the "Interested meetups" section.
    assert _emoji_slots(ast) == [0, 0, 0, 0, 1, 2], _emoji_slots(ast)


def test_sections_count_in_their_parent_scope():
    """A run of sibling sections cycles 0..N-1, whatever level it is written at.

    Driven by the sample's own structure rather than a hard-coded level: these
    fixtures get re-authored, and a card run moving from ``### `` to ``## ``
    changes nothing about the rule being tested.
    """
    for sample, expected_len in ((SAMPLE_1, 5), (SAMPLE_2, 4)):
        ast = _processed_with_criteria((sample / "content.md").read_text())
        runs = {lvl: _section_slots(ast, lvl) for lvl in range(1, 7)}
        card_lvl = max(runs, key=lambda k: len(runs[k]))
        got = runs[card_lvl]
        assert got == list(range(expected_len)), f"{sample} h{card_lvl}: {got}"


def test_a_section_lends_its_slot_to_its_title():
    """The title text takes the section's slot, never a count of its own.

    Without this the title would be alone in its section's scope and always land
    on color 0, so a rotated `### Heading 3` background and a rotated Heading3
    font color could never pick the same hue.
    """
    ast = _processed_with_criteria((SAMPLE_2 / "content.md").read_text())
    titles = _collect(ast, lambda n: n.type == "heading3")
    assert [t.rotation_index for t in titles] == [0, 1, 2, 3], [
        t.rotation_index for t in titles
    ]


def test_chain_is_ancestors_only():
    """A node's chain holds the sections ABOVE it — never its own level.

    A level's gate governs what sits inside that level, so a section must not
    appear in its own chain or it would gate its own content twice.
    """
    ast = _processed_with_criteria((SAMPLE_4 / "content.md").read_text())
    h3 = _collect(ast, lambda n: n.heading_group and n.heading_level == 3)
    assert h3, "sample-4 has ### sections"
    for sec in h3:
        assert sec.rotation_chain == (1, 2), sec.rotation_chain
        title = _collect(sec, lambda n: n.type == "heading3")[0]
        assert title.rotation_chain == (1, 2, 3), title.rotation_chain


def test_slot_survives_the_round_trip():
    """Both fields serialize, so the renderer sees what the grouper decided."""
    ast = _processed_with_criteria((SAMPLE_4 / "content.md").read_text())
    back = MarkdownGroupNode.from_dict(ast.to_dict())
    assert _emoji_slots(back) == _emoji_slots(ast)
    assert _section_slots(back, 3) == _section_slots(ast, 3)
    chains = [n.rotation_chain for n in _collect(back, lambda n: n.type == "emoji")]
    assert all(isinstance(c, tuple) for c in chains), chains


# ---------------------------------------------------------------------------
# 2. The theme parser — one key, one value or a list
# ---------------------------------------------------------------------------


def test_one_key_takes_a_single_color_or_a_list():
    """`Fill color:` is the same key either way — there is no plural twin."""
    single = _theme("# t\n## Links\n### Primary\nFill color: #112233\n")
    assert single.links.primary.fill_colors == [0xFF112233]
    assert single.links.primary.fill_color == 0xFF112233

    listed = _theme("# t\n## Links\n### Primary\nFill color:\n- #112233\n- #445566\n")
    assert listed.links.primary.fill_colors == [0xFF112233, 0xFF445566]
    # The scalar mirrors the FIRST entry, so every path that reads one color
    # (measurers, merges, the disabled swap) is unchanged by the list form.
    assert listed.links.primary.fill_color == 0xFF112233


def test_stroke_and_chip_and_heading_font_all_take_lists():
    t = _theme(
        "# t\n"
        "## Links\n### Primary\nStroke color:\n- #010101\n- #020202\n"
        "## Inline Code\nFill color:\n- #030303\n- #040404\n"
        "## Background styles and Spacing\n"
        "### Heading 2\nStroke color:\n- #050505\n- #060606\n"
        "## Text Styles\n"
        "Heading2\n- Font size: 20\n- Font color:\n  - #070707\n  - #080808\n"
    )
    assert t.links.primary.stroke_colors == [0xFF010101, 0xFF020202]
    assert t.inline_code.fill_colors == [0xFF030303, 0xFF040404]
    assert t.sections[2].stroke_colors == [0xFF050505, 0xFF060606]
    assert t.sections[2].stroke_color == 0xFF050505
    assert t.headings[2].colors == [0xFF070707, 0xFF080808]
    assert t.headings[2].color == 0xFF070707
    # A list must not eat the keys around it.
    assert t.headings[2].font_size == 20.0


def test_a_variant_replaces_the_inherited_list():
    """`### Secondary` states its own cycle — it never extends Primary's."""
    t = _theme(
        "# t\n## Inline Code\nFill color:\n- #111111\n- #222222\n"
        "### Secondary\nFill color:\n- #333333\n"
    )
    assert t.inline_code.fill_colors == [0xFF111111, 0xFF222222]
    assert t.inline_code.resolved("secondary").fill_colors == [0xFF333333]


def test_a_variant_that_lists_nothing_inherits_the_cycle():
    t = _theme(
        "# t\n## Links\n### Primary\nFill color:\n- #111111\n- #222222\n"
        "### Secondary\nCorner radius: 4\n"
    )
    assert t.links.resolved("secondary").fill_colors == [0xFF111111, 0xFF222222]


def test_an_unrecognised_key_closes_the_list():
    """A stray key between a list key and its bullets must not swallow them.

    Otherwise an unhandled key leaves the list above it open, and the next
    bullet is appended to the wrong property's colors.
    """
    t = _theme(
        "# t\n## Background styles and Spacing\n### Heading 2\n"
        "Background color:\n- #111111\n"
        "Some unknown key: whatever\n"
        "- #222222\n"
    )
    assert t.sections[2].bg_colors == [0xFF111111], t.sections[2].bg_colors


def test_gates_parse_and_read_leniently():
    t = _theme(
        "# t\n## Background styles and Spacing\n"
        "### Heading 1\nRotate link colors: no\n"
        "### Heading 2\nRotate links color: yes\nRotate chip colors: no\n"
        "Rotate buttons colors: yes\n"
    )
    assert t.sections[1].rotate == {"link": False}
    assert t.sections[2].rotate == {"link": True, "chip": False}


# ---------------------------------------------------------------------------
# 3. The renderer's resolver
# ---------------------------------------------------------------------------


def test_one_color_is_not_a_cycle():
    """The whole back-compat guarantee in one assertion."""
    t = Theme()
    for i in range(4):
        assert _rotate_color([0xFF00FF00], None, i, t, "link") == 0xFF00FF00


def test_an_empty_list_keeps_the_style_scalar():
    t = Theme()
    assert _rotate_color([], 0xFF123456, 3, t, "link") == 0xFF123456
    assert _rotate_color([], None, 3, t, "link") is None


def test_the_slot_wraps():
    t = Theme()
    colors = [1, 2, 3]
    assert [_rotate_color(colors, None, i, t, "link") for i in range(5)] == [
        1,
        2,
        3,
        1,
        2,
    ]


def test_the_innermost_stated_gate_wins():
    t = _theme(
        "# t\n## Background styles and Spacing\n"
        "### Heading 1\nRotate link colors: no\n"
        "### Heading 2\nRotate link colors: yes\n"
    )
    # h1 says no, h2 says yes — the innermost level that STATES it decides.
    assert _rotation_enabled(t, "link", (1, 2)) is True
    assert _rotation_enabled(t, "link", (1,)) is False
    # A level that stays silent defers outward.
    assert _rotation_enabled(t, "link", (1, 2, 3)) is True
    # A channel nobody gates cycles by default.
    assert _rotation_enabled(t, "emoji", (1, 2)) is True
    assert _rotation_enabled(t, "link", ()) is True


def test_a_disabled_gate_pins_to_the_first_color():
    t = _theme(
        "# t\n## Background styles and Spacing\n"
        "### Heading 2\nRotate emoji colors: no\n"
    )
    colors = [0xAA, 0xBB, 0xCC]
    assert [_rotate_color(colors, None, i, t, "emoji", (1, 2)) for i in range(3)] == [
        0xAA,
        0xAA,
        0xAA,
    ]
    # …and only that channel: the others still cycle.
    assert _rotate_color(colors, None, 1, t, "link", (1, 2)) == 0xBB


def test_a_transparent_chip_slot_stays_transparent():
    """A clear `#00000000` slot is a color, so that chip is outlined, not filled.

    Transparent is the integer 0; a slot of it must not fall back to the
    style's first color, for the fill or the stroke.
    """
    t = _theme(
        "# t\n## Inline Code\nFill color:\n- #FFCC00\n- #00000000\n"
        "Stroke color:\n- #333333\n- #00000000\nStroke width: 1\n"
    )
    first = _rotated_code_style(t.inline_code, {"rotation_index": 0}, t)
    second = _rotated_code_style(t.inline_code, {"rotation_index": 1}, t)
    assert (first.fill_color, first.stroke_color) == (0xFFFFCC00, 0xFF333333)
    assert (second.fill_color, second.stroke_color) == (0, 0)


# ---------------------------------------------------------------------------
# 4. `Rotate colors: sync` — borrowing the card's slot
# ---------------------------------------------------------------------------


def test_a_chip_can_name_its_card_not_just_itself():
    """The whole reason sync exists, on sample-7's real tree.

    A cycle is scoped to its enclosing section, so the chips of one card count
    among themselves and every card restarts at 0. Their `rotation_path` is
    what remembers which card they are in.

    The card is the empty ``## `` wrapper: sample-7 authors a ``***`` before
    each Explore row, so the tinted ``### `` section closes early and the row
    lands beside it inside the wrapper. That puts the chips one level deeper —
    path ``(0, slot, 0)`` — and the slot they borrow is still the card's.
    """
    ast = _processed_with_criteria(SAMPLE_7.read_text())
    cards = _collect(ast, lambda n: n.heading_group and n.heading_level == 2)
    assert [c.rotation_index for c in cards] == [0, 1, 2, 3]
    for slot, card in enumerate(cards):
        chips = _collect(card, lambda n: n.type == "inline_code")
        assert chips, "each card has chips"
        # Own slots count within the card…
        assert [c.rotation_index for c in chips] == list(range(len(chips)))
        # …while every path names the card itself.
        assert all(c.rotation_path == (0, slot, 0) for c in chips), (
            slot,
            [c.rotation_path for c in chips],
        )


def test_the_path_survives_the_round_trip():
    ast = _processed_with_criteria(SAMPLE_7.read_text())
    back = MarkdownGroupNode.from_dict(ast.to_dict())
    paths = [n.rotation_path for n in _collect(back, lambda n: n.type == "inline_code")]
    # Every chip names its card in slot 1 of the path, and the four cards
    # between them cover the whole cycle.
    assert paths and all(len(p) == 3 and p[0] == 0 and p[2] == 0 for p in paths), paths
    assert sorted({p[1] for p in paths}) == [0, 1, 2, 3], paths


def test_sync_parses_as_the_third_gate_value():
    t = _theme(
        "# t\n## Background styles and Spacing\n"
        "### Heading 2\nRotate colors: sync\n"
        "### Heading 3\nRotate colors: no\n"
    )
    assert t.sections[2].sync_slot is True
    assert t.sections[3].sync_slot is False
    # The blanket yes/no form gates every channel at once.
    assert t.sections[3].rotate.get("chip") is False
    assert t.sections[3].rotate.get("link") is False


def test_a_synced_ancestor_lends_its_slot():
    t = _theme(
        "# t\n## Background styles and Spacing\n### Heading 2\nRotate colors: sync\n"
    )
    # A chip that is 0th among its siblings, inside the third card.
    assert _synced_slot(0, (1, 2), (0, 2), t) == 2
    assert _synced_slot(1, (1, 2), (0, 3), t) == 3


def test_without_sync_a_node_keeps_its_own_slot():
    t = _theme("# t\n## Background styles and Spacing\n### Heading 2\nPadding: 0\n")
    assert _synced_slot(2, (1, 2), (0, 7), t) == 2
    # …and an empty ancestry is simply the node's own.
    assert _synced_slot(4, (), (), t) == 4


def test_a_section_never_syncs_to_itself():
    """The cards must keep the slots their own cycle dealt them.

    Their chain is their STRICT ancestry, so the level that shares its slot is
    not in it — otherwise every card would try to borrow from itself and they
    would all collapse onto one color.
    """
    t = _theme(
        "# t\n## Background styles and Spacing\n### Heading 2\nRotate colors: sync\n"
    )
    for own in range(4):
        assert _synced_slot(own, (1,), (0,), t) == own


def test_the_innermost_syncing_level_wins():
    t = _theme(
        "# t\n## Background styles and Spacing\n"
        "### Heading 1\nRotate colors: sync\n"
        "### Heading 2\nRotate colors: sync\n"
    )
    # chain (1, 2) with slots (5, 9): the nearer level 2 decides.
    assert _synced_slot(0, (1, 2), (5, 9), t) == 9


# ---------------------------------------------------------------------------
# 5. Text markers — the in-text `code` span
# ---------------------------------------------------------------------------


def test_marker_colors_take_a_list():
    t = _theme(
        "# t\n## Text Styles\nHeading2\n- Font size: 21\n"
        "- Marker text color:\n  - #0A3D2B\n  - #3A1F5E\n"
        "- Marker background color:\n  - #C7EFDA\n  - #DDCEF8\n"
    )
    h2 = t.headings[2]
    assert h2.marker_text_colors == [0xFF0A3D2B, 0xFF3A1F5E]
    assert h2.marker_bg_colors == [0xFFC7EFDA, 0xFFDDCEF8]
    # The scalars stay the first entry, so every existing reader is unchanged…
    assert h2.marker_text_color == 0xFF0A3D2B
    assert h2.marker_bg_color == 0xFFC7EFDA
    # …and the key between the two lists is not swallowed by either.
    assert h2.font_size == 21.0


def test_a_single_marker_color_is_still_a_list_of_one():
    t = _theme("# t\n## Text Styles\nText\n- Marker text color: #112233\n")
    assert t.text.marker_text_colors == [0xFF112233]
    assert t.text.marker_text_color == 0xFF112233


def test_a_marker_paints_its_cards_entry():
    """The whole point: `Ask Me` on card k takes entry k of each list."""
    from md2ui.pipeline.layout_render import _rotated_marker

    t = _theme(
        "# t\n## Text Styles\nText\n"
        "- Marker text color:\n  - #000001\n  - #000002\n  - #000003\n"
        "- Marker background color:\n  - #0000A1\n  - #0000A2\n  - #0000A3\n"
    )
    for slot in range(3):
        got = _rotated_marker(t.text, {"rotation_index": slot}, t)
        assert got.marker_text_color == 0xFF000001 + slot, slot
        assert got.marker_bg_color == 0xFF0000A1 + slot, slot


def test_markers_cycle_on_the_chip_channel():
    """A marker is the in-text form of a chip, so one gate covers both.

    Asserted rather than assumed: turning chips off must pin markers too, or a
    theme would have to learn a seventh channel name for the same idea.
    """
    from md2ui.pipeline.layout_render import _rotated_marker

    t = _theme(
        "# t\n## Background styles and Spacing\n"
        "### Heading 2\nRotate chip colors: no\n"
        "## Text Styles\nText\n"
        "- Marker text color:\n  - #000001\n  - #000002\n"
    )
    nd = {"rotation_index": 1, "rotation_chain": [1, 2]}
    assert _rotated_marker(t.text, nd, t).marker_text_color == 0xFF000001
    # …and with no gate it cycles as normal.
    assert (
        _rotated_marker(t.text, {"rotation_index": 1}, t).marker_text_color
        == 0xFF000002
    )


def test_one_marker_color_never_rotates():
    from md2ui.pipeline.layout_render import _rotated_marker

    t = _theme("# t\n## Text Styles\nText\n- Marker text color: #112233\n")
    for slot in range(3):
        got = _rotated_marker(t.text, {"rotation_index": slot}, t)
        assert got.marker_text_color == 0xFF112233


TESTS = [
    test_siblings_across_containers_share_one_cycle,
    test_a_section_resets_the_cycle,
    test_sections_count_in_their_parent_scope,
    test_a_section_lends_its_slot_to_its_title,
    test_chain_is_ancestors_only,
    test_slot_survives_the_round_trip,
    test_one_key_takes_a_single_color_or_a_list,
    test_stroke_and_chip_and_heading_font_all_take_lists,
    test_a_variant_replaces_the_inherited_list,
    test_a_variant_that_lists_nothing_inherits_the_cycle,
    test_an_unrecognised_key_closes_the_list,
    test_gates_parse_and_read_leniently,
    test_one_color_is_not_a_cycle,
    test_an_empty_list_keeps_the_style_scalar,
    test_the_slot_wraps,
    test_the_innermost_stated_gate_wins,
    test_a_disabled_gate_pins_to_the_first_color,
    test_a_transparent_chip_slot_stays_transparent,
    test_a_chip_can_name_its_card_not_just_itself,
    test_the_path_survives_the_round_trip,
    test_sync_parses_as_the_third_gate_value,
    test_a_synced_ancestor_lends_its_slot,
    test_without_sync_a_node_keeps_its_own_slot,
    test_a_section_never_syncs_to_itself,
    test_the_innermost_syncing_level_wins,
    test_marker_colors_take_a_list,
    test_a_single_marker_color_is_still_a_list_of_one,
    test_a_marker_paints_its_cards_entry,
    test_markers_cycle_on_the_chip_channel,
    test_one_marker_color_never_rotates,
]

if __name__ == "__main__":
    print("Color Rotation Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(
                f"  ✓  {test.__doc__.splitlines()[0] if test.__doc__ else test.__name__}"
            )
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
