"""
Unit tests for the icon-aside builder and the renderer's content_valign:
a level's ``Emoji aside`` places a leading lone-emoji icon beside a col of the
rest (row[icon, col]); non-"alone" emoji kinds are ineligible; and
_valign_offset distributes a row cell's slack per its content_valign hint.
Run with: uv run layout_icon_aside_tests.py
"""

from layout_bento_tests import _ast, _group, _leaf
from md2ui.pipeline.render_measure import _valign_offset
from md2ui.pipeline.layout_generator import LayoutGenerator

_ids = iter(range(90_000, 99_000))


def _emoji(kind: str = "alone") -> dict:
    return {
        "node_id": f"e{next(_ids)}",
        "type": "emoji",
        "content": "⭐",
        "emoji_kind": kind,
    }


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def _doc(children):
    ast = _ast(_group(_group(*children, glued_content_group=True)))
    icon_id = next((n.node_id for n in _walk(ast) if n.type == "emoji"), None)
    return ast, icon_id


def _icon_theme(theme=None):
    """*theme* (else a blank one) with ``Emoji aside`` on ``### Elements``, the
    level the fixtures' content sits at."""
    if theme is None:
        theme = _theme_with("## Background styles and Spacing\n")
    theme.elements.emoji_aside = True
    return theme


def _icon_row(layout, icon_id):
    """The 2-cell row whose LEFT cell holds the icon (a left-gutter aside)."""
    return _side_row(layout, icon_id, 0)


def _side_row(layout, icon_id, cell: int):
    """The 2-cell row whose *cell* IS the icon's fixed gutter cell.

    Matched on ``aside_fixed`` — the property ``_build_icon_aside`` stamps on the
    icon cell so the renderer never scales it — rather than on "some 2-cell row
    with the icon under it", which would count any two-column arrangement holding
    the icon, such as a packed row of unique siblings.
    """
    for n in _walk(layout):
        if n.type == "row" and len(n.children) == 2:
            side = n.children[cell]
            if side.content_id == icon_id and (side.render_properties or {}).get(
                "aside_fixed"
            ):
                return n
    return None


def _gutter_side(layout, icon_id) -> str | None:
    """ "left" / "right" / None — which gutter the icon ended up in."""
    if _side_row(layout, icon_id, 0) is not None:
        return "left"
    if _side_row(layout, icon_id, 1) is not None:
        return "right"
    return None


def test_icon_aside_builds_row_icon_col():
    ast, icon_id = _doc(
        [_emoji(), _leaf("Starred feature title"), _leaf("Supporting text")]
    )
    layout = LayoutGenerator().generate(ast, 1280.0, theme=_icon_theme())
    row = _icon_row(layout, icon_id)
    assert row is not None, "icon_aside must build row[icon, rest]"
    rest = row.children[1]
    assert rest.type == "col" and len(rest.children) == 2, (
        "the rest must stack in a col beside the icon"
    )
    assert icon_id not in [x.content_id for x in _walk(rest)]
    print("  ✓  icon_aside → row[icon, col(rest)]")


def test_icon_cell_takes_its_own_width():
    """An icon is not flexible: the icon cell is its measured width and the content column gets the rest (never a 50/50 split)."""
    ast, icon_id = _doc(
        [_emoji(), _leaf("Starred feature title"), _leaf("Supporting text")]
    )
    layout = LayoutGenerator().generate(ast, 1280.0, theme=_icon_theme())
    row = _icon_row(layout, icon_id)
    assert row is not None
    icon_share = row.ratios[0] / sum(row.ratios)
    assert icon_share < 0.25, (
        f"icon cell took {icon_share:.0%} of the row — it should hug its own width"
    )
    print(f"  ✓  icon cell hugs its width ({icon_share:.0%} of the row)")


def test_non_alone_emoji_ineligible():
    ast, icon_id = _doc([_emoji(kind="peeled"), _leaf("Peeled emoji stays inline")])
    layout = LayoutGenerator().generate(ast, 1280.0, theme=_icon_theme())
    assert _icon_row(layout, icon_id) is None, (
        "a non-'alone' emoji must not build an icon aside"
    )
    print("  ✓  emoji_kind != 'alone' → ineligible (stacks)")


def test_position_picks_the_side():
    """First child → left gutter, last child → right gutter.

    A trailing icon builds ``row[col(rest), icon]``.
    """
    ast, icon_id = _doc([_emoji(), _leaf("Starred feature title")])
    layout = LayoutGenerator().generate(ast, 1280.0, theme=_icon_theme())
    assert _gutter_side(layout, icon_id) == "left", "a leading icon goes left"

    ast, icon_id = _doc([_leaf("Text before the emoji"), _emoji()])
    layout = LayoutGenerator().generate(ast, 1280.0, theme=_icon_theme())
    assert _gutter_side(layout, icon_id) == "right", "a trailing icon goes right"
    row = _side_row(layout, icon_id, 1)
    assert row is not None
    assert (row.children[1].render_properties or {}).get("aside_fixed"), (
        "the trailing icon cell must still be the FIXED one"
    )
    assert row.ratios[1] < row.ratios[0], (
        "the fixed cell's ratio must move with it, not stay on the left"
    )
    print("  ✓  position picks the gutter side (first → left, last → right)")


def test_a_middle_emoji_is_never_aside():
    """Only an edge child is eligible."""
    ast, icon_id = _doc([_leaf("Before"), _emoji(), _leaf("After")])
    layout = LayoutGenerator().generate(ast, 1280.0, theme=_icon_theme())
    assert _gutter_side(layout, icon_id) is None, (
        "an emoji between two siblings must not build a gutter"
    )
    print("  ✓  a middle emoji is never aside-eligible")


def _themed():
    """(theme, fonts, measurers) mirroring what the renderer hands the generator.

    The other cases in this module run theme-less and measurer-less, so they
    never exercise the icon cell's real width.
    """
    from pathlib import Path

    from md2ui.pipeline.layout_render import (
        FontSet,
        make_line_width_measurer,
        make_marker_measurer,
        make_width_measurer,
    )
    from md2ui.pipeline.theme import parse_theme
    from md2ui.utils.font_loader import (
        load_custom_fonts,
        resolve_typeface,
        weight_from_str,
    )

    theme = parse_theme(Path("data/markdown/tests/THEME.md"))
    custom = load_custom_fonts(theme.font_paths)
    name = theme.text.font_name or "Arial"
    base_w = weight_from_str(theme.text.font_weight)

    def tf(weight, italic):
        return resolve_typeface(name, weight, italic, custom)

    fonts = FontSet(
        tf(base_w, False),
        tf(700, False),
        tf(base_w, True),
        tf(700, True),
        tf(base_w, False),
    )
    return (
        theme,
        fonts,
        dict(
            measure_width=make_width_measurer(fonts, theme),
            measure_line=make_line_width_measurer(fonts, theme),
            measure_marker=make_marker_measurer(fonts, theme),
        ),
    )


def test_icon_cell_is_its_rendered_width():
    """The icon cell is the width the RENDERER draws the badge at — the theme's
    icon style — not a LEAF_WIDTH text category (80/100px for a ~53px glyph)."""
    from md2ui.pipeline.render_measure import _emoji_leaf_size

    theme, fonts, measurers = _themed()
    ast, icon_id = _doc([_emoji(), _leaf("Starred feature title")])
    layout = LayoutGenerator().generate(ast, 1280.0, _icon_theme(theme), **measurers)
    row = _icon_row(layout, icon_id)
    assert row is not None
    drawn = _emoji_leaf_size(
        {"type": "emoji", "content": "⭐", "emoji_kind": "alone"}, fonts, theme
    )[0]
    assert abs(row.ratios[0] - drawn) < 0.5, (
        f"icon cell is {row.ratios[0]:.1f}px but the renderer draws {drawn:.1f}px"
    )
    print(f"  ✓  icon cell == its rendered badge width ({drawn:.1f}px)")


def test_aside_split_reserves_the_gap():
    """cell + gap + cell must equal the row exactly. Splitting the FULL width
    and leaving the gap on top makes the renderer scale the cells back, so the
    content column ends up laid out at a width it never gets."""
    gen = LayoutGenerator()
    ratios, aside_w, rest_w = gen._aside_split(53.5, 1280.0, 24.0)
    assert aside_w == 53.5, f"fixed cell was resized to {aside_w}"
    assert abs(aside_w + 24.0 + rest_w - 1280.0) < 1e-9, (
        f"{aside_w} + 24 + {rest_w} != 1280"
    )
    assert abs(sum(ratios) - (aside_w + rest_w)) < 1e-9
    # Degenerate: a cell wider than the row is clamped, never negative rest.
    _r, a, rest = gen._aside_split(400.0, 100.0, 24.0)
    assert a == 76.0 and rest == 0.0, (a, rest)
    print("  ✓  _aside_split: cell + gap + rest == available (and clamps)")


def test_icon_cell_does_not_grow_with_the_row():
    """Fixed means fixed: doubling the row width must not widen the icon."""
    theme, _fonts, measurers = _themed()
    widths = []
    for available in (640.0, 1280.0):
        ast, icon_id = _doc([_emoji(), _leaf("Starred feature title")])
        layout = LayoutGenerator().generate(
            ast, available, _icon_theme(theme), **measurers
        )
        row = _icon_row(layout, icon_id)
        assert row is not None
        widths.append(row.ratios[0])
    assert abs(widths[0] - widths[1]) < 0.5, (
        f"icon cell grew with the row: {widths[0]:.1f} → {widths[1]:.1f}"
    )
    print(f"  ✓  icon cell is width-invariant ({widths[0]:.1f}px at 640 and 1280)")


def test_valign_offset():
    assert _valign_offset({"content_valign": "center"}, 40.0, 100.0) == 30.0
    assert _valign_offset({"content_valign": "bottom"}, 40.0, 100.0) == 60.0
    assert _valign_offset({"content_valign": "top"}, 40.0, 100.0) == 0.0
    assert _valign_offset(None, 40.0, 100.0) == 0.0
    # A cell stretched to the row height has no slack.
    assert _valign_offset({"content_valign": "center"}, 100.0, 100.0) == 0.0
    # Never negative, even if the cell measured taller than the row.
    assert _valign_offset({"content_valign": "bottom"}, 120.0, 100.0) == 0.0
    print("  ✓  _valign_offset slack math (center/bottom/top/stretched)")


# ---------------------------------------------------------------------------
# The THEME level default — `Emoji aside: yes`
# ---------------------------------------------------------------------------


def _theme_with(body: str):
    """Parse a THEME.md fragment from a temp file (never edit the repo theme)."""
    import tempfile
    from pathlib import Path

    from md2ui.pipeline.theme import parse_theme

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "THEME.md"
        path.write_text(body, encoding="utf-8")
        return parse_theme(path)


_ASIDE_H2 = """## Background styles and Spacing
### Heading 2
Emoji aside: yes
"""


def _section(level: int, *children: dict) -> dict:
    return _group(*children, heading_group=True, heading_level=level)


def _themed_run(doc: dict, theme, width: float = 1280.0):
    """(layout, [emoji node ids in document order]).

    The ids have to come off the BUILT tree: ``_ast`` renumbers through
    ``from_dict``, so the ids in the fixture dicts are not the content_ids the
    layout carries.
    """
    root = _ast(doc)
    ids = [n.node_id for n in _walk(root) if n.type == "emoji"]
    return LayoutGenerator().generate(root, width, theme=theme), ids


def test_the_key_parses_on_every_block_that_takes_it():
    t = _theme_with(
        "## Background styles and Spacing\n"
        "### Heading 2\nEmoji aside: yes\n"
        "### Heading 3\nEmoji aside: no\n"
        "### Elements\nEmoji aside: yes\n"
    )
    assert t.sections[2].emoji_aside is True
    assert t.sections[3].emoji_aside is False, "an explicit 'no' is not unset"
    assert t.elements.emoji_aside is True
    assert t.sections.get(4) is None or t.sections[4].emoji_aside is None
    print("  ✓  `Emoji aside` parses on heading levels and on Elements")


def test_the_key_does_not_make_a_blank_level_paint():
    """Same contract as image_bleed: a switch must not turn on a background."""
    t = _theme_with(
        "## Background styles and Spacing\n### Heading 2\nEmoji aside: yes\n"
    )
    assert not t.sections[2].is_active(), "Emoji aside must stay out of is_active()"
    print("  ✓  the key does not make an otherwise-blank level active")


def _section_doc():
    return _section(
        2,
        _group(_emoji(), _leaf("Title"), _leaf("Body"), glued_content_group=True),
    )


def test_a_level_asides_on_its_own():
    """The theme alone asks for the gutter — no params."""
    layout, (icon,) = _themed_run(_section_doc(), _theme_with(_ASIDE_H2))
    assert _gutter_side(layout, icon) == "left", layout.to_dict()
    print("  ✓  a level's `Emoji aside: yes` builds the gutter on its own")


def test_unset_changes_nothing():
    layout, (icon,) = _themed_run(
        _section_doc(), _theme_with("## Background styles and Spacing\n")
    )
    assert _gutter_side(layout, icon) is None, "with the key unset nothing may change"
    print("  ✓  unset → no gutter (the feature is inert by default)")


def test_the_level_stops_at_the_next_heading_boundary():
    """H2's key reaches its own glued groups but NOT a nested H3 section.

    This is `owner_level`: a heading_group resets it to its own level, anything
    else inherits — the same resolution `_cell_gap` uses.
    """
    doc = _section(
        2,
        _group(_emoji(), _leaf("Own body"), glued_content_group=True),
        _section(3, _group(_emoji(), _leaf("Nested body"), glued_content_group=True)),
    )
    layout, (own_icon, nested_icon) = _themed_run(doc, _theme_with(_ASIDE_H2))
    assert _gutter_side(layout, own_icon) == "left", (
        "a glued group the H2 owns must follow the H2 key"
    )
    assert _gutter_side(layout, nested_icon) is None, (
        "a nested H3 section answers to sections[3], not to the H2 above it"
    )
    print("  ✓  the level reaches what it owns and stops at the next heading")


def test_outside_any_section_falls_to_elements():
    def doc():
        return _group(_emoji(), _leaf("Title"), _leaf("Body"), glued_content_group=True)

    elements = _theme_with(
        "## Background styles and Spacing\n### Elements\nEmoji aside: yes\n"
    )
    layout, (icon,) = _themed_run(doc(), elements)
    assert _gutter_side(layout, icon) == "left"
    # ...and a heading level's key does NOT reach level-0 content.
    layout, (icon,) = _themed_run(doc(), _theme_with(_ASIDE_H2))
    assert _gutter_side(layout, icon) is None
    print("  ✓  level-0 content follows ### Elements, not a heading level")


def test_a_line_group_is_never_aside():
    """One SOURCE LINE keeps flowing — an aside would stack what follows.

    An aside puts the icon beside the WHOLE GROUP, which presupposes several
    lines. `_build_icon_aside` cols whatever is left, so `⭐ - text - 🚀` would
    come back as the star beside a COLUMN of "text" over the rocket — the
    opposite of the line the author wrote, which already flows its icon inline.
    """
    doc = _group(
        _emoji(),
        _leaf("This contains emoji before and after"),
        _emoji(),
        line_split_group=True,
    )
    layout, ids = _themed_run(
        doc,
        _theme_with(
            "## Background styles and Spacing\n### Elements\nEmoji aside: yes\n"
        ),
    )
    assert all(_gutter_side(layout, i) is None for i in ids), (
        "a line_split_group must keep flowing, not become row[icon | col]"
    )
    print("  ✓  a one-line group never becomes an icon aside")


def test_a_run_of_heading_sections_polls_its_own_level():
    """ADR-301: a run is laid out alike. A run of `### ` cards is built at
    level 3, so its poll asks level 3 for the gutter, not the level that holds
    the run; asked there, no card was pinned and the one with the longest
    caption stacked its icon alone."""
    from md2ui import session

    # sample-5's theme (tests-render, color rotation): DM Sans, padded cards.
    theme = _theme_with(
        "## Fonts\n"
        "- assets/fonts/DMSans_18pt-Regular.ttf\n"
        "- assets/fonts/DMSans_18pt-Medium.ttf\n"
        "## Styling & Spacing\n"
        "### Root\n"
        "Background color: #FFFFFF\n"
        "Padding: 23\n"
        "Spacing: 24\n"
        "### Elements\n"
        "Row spacing: 16\n"
        "Col spacing: 0\n"
        "Group spacing: 20\n"
        "### Heading 3\n"
        "Background color: #FAFAFA\n"
        "Corner radius: 16\n"
        "Padding: 16\n"
        "Spacing: 24\n"
        "Emoji aside: yes\n"
        "Vertical align: center\n"
        "Rotate colors: sync\n"
        "## Text Styles\n"
        "Text\n"
        "- Font Name: DM Sans 18pt\n"
        "- Font size: 16\n"
        "- Font weight: 400\n"
        "- Font color: #737373\n"
        "Lead\n"
        "- Font Name: DM Sans 18pt\n"
        "- Font size: 20\n"
        "- Font weight: 400\n"
        "- Font color: #09090B\n"
        "## Emoji styles\n"
        "Font: assets/icons/material-design-icons-md2ui.ttf\n"
        "### Primary\n"
        "Icon size: 20\n"
        "Padding: 12\n"
        "Corner radius: 8\n"
        "Shape: square\n"
        "Emoji weight: 400\n"
        "Background color:\n"
        "- #F5C242\n"
        "- #F094E8\n"
        "- #65DAB5\n"
        "- #4F85F7\n"
        "Icon color: #09090B\n"
    )
    cards = [
        ("↙️", "Tiny", "file format but mighty"),
        ("🖽", "Motion Tokens", "bind properties to real data"),
        ("⬚", "Interactive", "for delightful experiences"),
        ("❴", "Dev ready", "and easy to implement"),
    ]
    doc = "\n\n".join(f"### \n{e}\n__{t}__\n{c}" for e, t, c in cards)
    fonts = session.load_fonts(theme)
    grouped = session.group_markdown(doc, session.load_grouping_kit())
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    mixed = []
    for width in range(700, 1300, 20):
        scene = session.build_scene(
            LayoutGenerator(), root, index, theme, fonts, float(width)
        )
        emoji = [
            b
            for b in scene.boxes
            if (index.get(b.content_id) or {}).get("type") == "emoji"
        ]
        texts = [b for b in scene.boxes if b not in emoji]
        # Aside: text of the icon's OWN card starts to its right, level with it.
        cards = [c for c in scene.sections if c.width < width / 2]
        beside = []
        for e in emoji:
            card = next(c for c in cards if c.x <= e.x < c.x + c.width)
            own = [t for t in texts if card.x <= t.x < card.x + card.width]
            beside.append(
                any(t.x > e.x + e.width - 1 and abs(t.y - e.y) < e.height for t in own)
            )
        if len(set(beside)) > 1:
            mixed.append((width, beside))
    assert not mixed, f"the run's cards disagree on the gutter: {mixed[:3]}"
    print("  ✓  a run of heading sections polls the level its cards are built at")


TESTS = [
    test_a_run_of_heading_sections_polls_its_own_level,
    test_icon_aside_builds_row_icon_col,
    test_icon_cell_takes_its_own_width,
    test_icon_cell_is_its_rendered_width,
    test_aside_split_reserves_the_gap,
    test_icon_cell_does_not_grow_with_the_row,
    test_non_alone_emoji_ineligible,
    test_position_picks_the_side,
    test_a_middle_emoji_is_never_aside,
    test_valign_offset,
    test_the_key_parses_on_every_block_that_takes_it,
    test_the_key_does_not_make_a_blank_level_paint,
    test_a_level_asides_on_its_own,
    test_unset_changes_nothing,
    test_the_level_stops_at_the_next_heading_boundary,
    test_outside_any_section_falls_to_elements,
    test_a_line_group_is_never_aside,
]

if __name__ == "__main__":
    print("Layout Icon Aside Tests")
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
