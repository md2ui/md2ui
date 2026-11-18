"""
Unit tests for the layout's minimum width: the floor is what the DOCUMENT's
content needs, not the flat ``CONTENT_WIDTH_MIN`` sanity value.

``generator_units.document_min_width`` measures the widest unbreakable unit in
a document — a whole pill, a single word at its effective font, a table's summed
per-column minima — and the app shell hands it to ``_content_width`` as a floor.
Past that width the layout stops shrinking and the window scrolls horizontally,
rather than being handed a width its content cannot render in.

A table under ``Stacking cards: yes`` is the exception, and the last three tests
are about it: down there the table is not a grid at all, every row is a card, so
the floor is what a CARD needs and the page keeps shrinking to reach it. Only
the page floor works that way — the grid packer's own measurement still reserves
the table's full grid width.

Run with: uv run tests/root_min_width_tests.py
"""

from types import SimpleNamespace

import skia

from layout_bento_tests import _ast, _group, _leaf
from md2ui.pipeline import layout_render as LR
from md2ui.pipeline.generator_units import _measured_min_width, document_min_width
from md2ui.pipeline.layout_render import make_width_measurer
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import (
    CONTENT_WIDTH_MAX,
    CONTENT_WIDTH_MIN,
    TABLE_KEY_COL_MAX_SHARE,
    Theme,
)
from md2ui.utils.font_loader import make_font

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fonts() -> FontSet:
    tf = skia.Typeface.MakeDefault()
    return FontSet(tf, tf, tf, tf, tf)


def _chip(label: str) -> dict:
    """An inline-code leaf — a pill, which never wraps at any width."""
    d = _leaf(label, "one_word")
    d["type"] = "inline_code"
    return d


def _wide_theme() -> Theme:
    """Chips with enough padding that one is unmistakably wider than a word."""
    t = Theme()
    t.inline_code.padding.left = 60.0
    t.inline_code.padding.right = 60.0
    t.inline_code.corner_radius = 0.0
    return t


def _cell(text: str, role: str) -> dict:
    """One table cell: a chip, so its width is indivisible at any container
    width and the floor is about the table's shape, not about wrapping."""
    d = _chip(text)
    d["table_role"] = role
    return d


def _row(kind: str, labels: tuple[str, ...]) -> dict:
    d = _group(
        *[_cell(t, "header" if kind == "table_header" else "body") for t in labels]
    )
    d["type"] = kind
    return d


def _table(header: tuple[str, ...], *body: tuple[str, ...]) -> dict:
    """A table group as the grouper flags it: a `table_group` container of one
    `table_header` row and N `table_row` rows."""
    return _group(
        _row("table_header", header),
        *[_row("table_row", r) for r in body],
        table_group=True,
    )


# ---------------------------------------------------------------------------
# _content_width
# ---------------------------------------------------------------------------


def test_no_floor_leaves_content_width_untouched():
    """The default ``min_width=0.0`` adds no floor, so every measurer-less
    caller (and every other test module) gets the flat minimum."""
    assert LR._content_width(2000.0) == CONTENT_WIDTH_MAX
    assert LR._content_width(800.0) == 800.0
    assert LR._content_width(10.0) == CONTENT_WIDTH_MIN
    assert LR._content_width(10.0, min_width=0.0) == CONTENT_WIDTH_MIN
    print("  ✓  with no floor, _content_width is unchanged")


def test_a_floor_under_the_sanity_minimum_changes_nothing():
    """A document narrower than 320 keeps the 320 floor — the flat minimum is
    still the lower bound, just not the ONLY bound."""
    for m in (0.0, 100.0, CONTENT_WIDTH_MIN):
        assert LR._content_width(50.0, min_width=m) == CONTENT_WIDTH_MIN, m
    print(
        f"  ✓  a floor under {CONTENT_WIDTH_MIN:.0f} leaves the sanity minimum in place"
    )


def test_a_floor_over_the_sanity_minimum_stops_the_shrink():
    """The regression this exists for: a 485px document in a 300px window is
    laid out at 485, not squeezed to 320."""
    assert LR._content_width(300.0, min_width=484.8) == 484.8
    assert LR._content_width(1000.0, min_width=484.8) == 1000.0, (
        "a floor must never NARROW a layout that already fits"
    )
    print("  ✓  a content floor over the minimum stops the shrink")


def test_the_floor_outranks_max_width():
    """Content is incompressible, so the floor wins over the cap. ``Max width``
    limits GROWTH; it cannot cut below what the content needs."""
    theme = Theme()
    theme.root.max_width = 400.0
    assert LR._content_width(2000.0, theme) == 400.0, "cap still caps growth"
    assert LR._content_width(2000.0, theme, min_width=900.0) == 900.0
    print("  ✓  the content floor outranks Max width")


# ---------------------------------------------------------------------------
# document_min_width
# ---------------------------------------------------------------------------


def test_document_min_width_needs_a_measurer():
    """No measurer, no floor — a script or test calling without fonts must get
    0.0 rather than a guess."""
    doc = _ast(_group(_leaf("some short text")))
    assert document_min_width(doc) == 0.0
    assert document_min_width(doc, Theme()) == 0.0
    print("  ✓  document_min_width returns no floor without a measurer")


def test_document_min_width_is_the_widest_unbreakable_leaf():
    """The document's minimum is its widest indivisible thing — here a padded
    chip, which is wider than any of the words around it."""
    theme = _wide_theme()
    measure = make_width_measurer(_fonts(), theme)

    text_only = _ast(_group(_leaf("alpha beta"), _leaf("gamma")))
    with_chip = _ast(_group(_leaf("alpha beta"), _chip("PIN"), _leaf("gamma")))

    bare = document_min_width(text_only, theme, measure)
    chipped = document_min_width(with_chip, theme, measure)
    chip_alone = document_min_width(_ast(_group(_chip("PIN"))), theme, measure)

    assert chipped > bare, (chipped, bare)
    assert abs(chipped - chip_alone) < 0.01, (
        f"the widest leaf sets the floor: {chipped:.1f} != {chip_alone:.1f}"
    )
    assert chipped > theme.inline_code.padding.x, chipped
    print(f"  ✓  the widest unbreakable leaf sets the floor ({chipped:.1f}px)")


def test_document_min_width_reaches_through_nesting():
    """The floor is the whole subtree's, not the root's own children's — a chip
    buried in a section still raises it."""
    theme = _wide_theme()
    measure = make_width_measurer(_fonts(), theme)
    flat = _ast(_group(_chip("PIN")))
    nested = _ast(_group(_group(_group(_chip("PIN")))))
    assert (
        abs(
            document_min_width(nested, theme, measure)
            - document_min_width(flat, theme, measure)
        )
        < 0.01
    )
    print("  ✓  the floor reaches through nested groups")


def _table_doc():
    """Three columns of chips — a table whose grid minimum is a real sum."""
    return _ast(
        _group(
            _table(
                ("Item", "Quantity", "Price"),
                ("Espresso", "12", "$40.00"),
                ("Cortado", "7", "$21.50"),
            )
        )
    )


def test_stacking_cards_lets_the_page_shrink_to_a_card():
    """The regression this exists for: with ``Stacking cards: yes`` the page may
    keep shrinking past the grid's own width, because down there the table is no
    longer a grid — every row is a card, and a card's floor is its widest single
    cell, not the sum of the columns."""
    theme = _wide_theme()
    measure = make_width_measurer(_fonts(), theme)
    doc = _table_doc()

    theme.tables.stacking = False
    grid = document_min_width(doc, theme, measure)
    theme.tables.stacking = True
    stacked = document_min_width(doc, theme, measure)

    chip = document_min_width(_ast(_group(_chip("Espresso"))), theme, measure)
    assert stacked < grid, (stacked, grid)
    assert grid - stacked > chip, (
        f"stacking must drop a whole column's worth: {grid:.0f} -> {stacked:.0f}"
    )
    assert stacked >= chip, "a card still cannot go under its widest single cell"
    print(f"  ✓  stacking drops the floor {grid:.0f} -> {stacked:.0f}px")


def test_the_stacked_floor_leaves_room_for_the_key_column():
    """A stacked value shares its card with the key label beside it, which the
    renderer caps at ``TABLE_KEY_COL_MAX_SHARE`` of the card. The floor has to
    solve that same constraint or the keys are drawn over their values."""
    theme = _wide_theme()
    theme.tables.stacking = True
    measure = make_width_measurer(_fonts(), theme)
    stacked = document_min_width(_table_doc(), theme, measure)

    inner = stacked - theme.tables.cells.padding.x
    widest_value = document_min_width(_ast(_group(_chip("$40.00"))), theme, measure)
    room = inner - TABLE_KEY_COL_MAX_SHARE * inner - theme.tables.key_spacing
    assert room >= widest_value - 0.01, (room, widest_value)
    print(f"  ✓  the stacked floor keeps {room:.0f}px for the widest value")


def test_a_table_in_a_grid_still_reserves_its_full_width():
    """Scope guard. Only the PAGE floor stacks: the same measurement without
    ``stacked_tables`` — the one the grid packer uses for column fitting — still
    sums the columns, so a grid can never hand a table less than the renderer's
    stacking threshold and set grid/cards oscillating."""
    theme = _wide_theme()
    theme.tables.stacking = True
    measure = make_width_measurer(_fonts(), theme)
    doc = _table_doc()

    packer = _measured_min_width(doc, measure, theme, {})
    theme.tables.stacking = False
    off = _measured_min_width(doc, measure, theme, {})
    assert abs(packer - off) < 0.01, (
        f"grid fitting must not see the stacking key: {packer:.1f} != {off:.1f}"
    )
    assert document_min_width(doc, theme, measure) == off, (
        "and with the key off, the page floor is the grid sum, unchanged"
    )
    print("  ✓  grid fitting still reserves the table's full grid width")


# ---------------------------------------------------------------------------
# make_width_measurer: the floor is the widest unit the wrap keeps whole
# ---------------------------------------------------------------------------

_LONG = "Pneumonoultramicroscopicsilicovolcanoconiosis" * 2


def _floor(content: str) -> float:
    """The measurer's floor for one text leaf at the body font."""
    floor = make_width_measurer(_fonts(), Theme())(
        SimpleNamespace(type="text", content=content)
    )
    assert floor is not None, content
    return floor


def _wrap_needs(content: str) -> float:
    """What one line must hold for ``content`` at the body font: the widest
    unit the wrapper refuses to break, measured the way the wrap measures it."""
    from md2ui.pipeline.render_measure import _explode_words
    from md2ui.pipeline.render_metrics import _measure_word, _wrap_units

    fonts, size = _fonts(), Theme().text.font_size
    return max(
        sum(_measure_word(w[0], w[1], w[2], fonts, size) for w in unit)
        for unit in _wrap_units(_explode_words(content))
    )


def test_the_floor_counts_punctuation_attached_across_a_span():
    """``(**Word**)`` is three words to the exploder (a span boundary falls on
    each side of the bold) but one unit to the wrap, which never breaks where no
    space was written. A floor taken over the words would be short by the
    brackets, and at the page minimum the ``)`` and the last letter would clip."""
    for content in (f"(**{_LONG}**)", "**Settings**.", "Open **Settings**..."):
        floor = _floor(content)
        needs = _wrap_needs(content)
        assert abs(floor - needs) < 0.01, (content, floor, needs)
    bare = _floor(f"**{_LONG}**")
    assert _floor(f"(**{_LONG}**)") > bare + 1.0
    print("  ✓  the width floor is the widest unit the wrap keeps whole")


def test_the_floor_of_a_plain_word_is_unchanged():
    """The control: with nothing attached, unit and word are the same thing."""
    content = f"**{_LONG}**"
    floor = _floor(content)
    assert abs(floor - _wrap_needs(content)) < 0.01
    font = make_font(_fonts().bold, Theme().text.font_size)
    assert abs(floor - font.measureText(_LONG)) < 0.5, floor
    print("  ✓  a plain word's floor is still the word")


TESTS = [
    test_no_floor_leaves_content_width_untouched,
    test_a_floor_under_the_sanity_minimum_changes_nothing,
    test_a_floor_over_the_sanity_minimum_stops_the_shrink,
    test_the_floor_outranks_max_width,
    test_document_min_width_needs_a_measurer,
    test_document_min_width_is_the_widest_unbreakable_leaf,
    test_document_min_width_reaches_through_nesting,
    test_stacking_cards_lets_the_page_shrink_to_a_card,
    test_the_stacked_floor_leaves_room_for_the_key_column,
    test_a_table_in_a_grid_still_reserves_its_full_width,
    test_the_floor_counts_punctuation_attached_across_a_span,
    test_the_floor_of_a_plain_word_is_unchanged,
]


if __name__ == "__main__":
    for t in TESTS:
        t()
    print(f"\n{len(TESTS)} tests passed")
