"""
The ``+++`` spacer — blank space the author writes, sized by the theme (ADR-203).

``+++`` / ``++++`` / ``+++++`` on a line of their own are a small / medium /
large VERTICAL spacer. The Markdown names a step and nothing else; THEME.md's
``Spacer small|medium|large`` (with ``row`` / ``col`` variants) gives
it a size in px at the level that holds it.

Three properties carry the design, and each has tests below:

* the spelling is exact — three to five ``+`` alone on a line, nothing else;
* a spacer is INVISIBLE to structure: a document groups exactly as its twin
  without spacers does — same nodes, fingerprints, kind_hash and runs — with
  SPACER leaves added where they were written. The grouper gets this by
  grouping the document without them and inserting each afterwards
  (``grouper_spacers``); the fingerprint silences them;
* a spacer is spaced like any element: the gap applies on EACH side of it,
  element beside a leaf and group beside a block, and it adds its own size.

Run with: uv run python tests/spacer_tests.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

import skia

from md2ui import session
from md2ui.pipeline import generator_spacers
from md2ui.pipeline.grouper_block_splits import _break_node_type
from md2ui.pipeline.grouper_spacers import strip_spacer_lines
from md2ui.pipeline.layout_generator import LayoutGenerator, LayoutNode
from md2ui.pipeline.layout_render import load_grouping_ast_node
from md2ui.pipeline.markdown_grouper import ASTPatternAnalyzer, NodeType
from md2ui.pipeline.render_measure import _leaf_height
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import Theme, parse_theme

_T = Theme()
_FACE = skia.Typeface.MakeDefault()
_FONTS = FontSet(_FACE, _FACE, _FACE, _FACE, _FACE)
_KIT = session.load_grouping_kit()


def group(text: str):
    root = session.group_markdown(text, _KIT)
    assert root is not None
    ASTPatternAnalyzer(root).fingerprints(include_unique=True)
    return root


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def theme_from(text: str) -> Theme:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "THEME.md"
        p.write_text(text)
        return parse_theme(p)


def spacer_leaves(layout):
    out = []

    def rec(n):
        if (n.render_properties or {}).get("spacer") is not None:
            out.append(n.render_properties["spacer"])
        for c in n.children:
            rec(c)

    rec(layout)
    return out


# ---------------------------------------------------------------------------
# 1 — the spelling
# ---------------------------------------------------------------------------


def test_three_to_five_plus_signs_are_a_spacer():
    for s in ("+++", "++++", "+++++", "  +++  "):
        assert _break_node_type(s) == NodeType.SPACER, s


def test_other_counts_and_shapes_are_text():
    # `+ + +` is a nested list in CommonMark, so the spaced form is not taken.
    for s in ("++", "++++++", "+ + +", "+++ A", "C+++", "A +++"):
        assert _break_node_type(s) != NodeType.SPACER, s


def test_only_spacer_lines_are_taken_out_for_the_plain_grouping():
    assert strip_spacer_lines("A\n+++\nB\n") == "A\nB\n"
    assert strip_spacer_lines("- One\n    +++\n  more\n") == "- One\n  more\n"
    # Nothing to take: no spacer, a code block, a fenced block, an escape.
    for text in (
        "A\nB\n",
        "    +++\n",
        "```\n+++\n```\n",
        "~~~md\n+++\n~~~\n",
        "\\+++\n",
    ):
        assert strip_spacer_lines(text) is None, text


def test_an_escaped_spacer_is_text():
    root = group("A\n\n\\+++\n\nB\n")
    assert not [n for n in walk(root) if n.type == NodeType.SPACER]


def test_the_spacer_survives_as_a_leaf_with_its_spelling():
    root = group("A\n\n++++\n\nB\n")
    spacers = [n for n in walk(root) if n.type == NodeType.SPACER]
    assert [s.content for s in spacers] == ["++++"]
    assert not spacers[0].children


def test_an_indented_spacer_stays_inside_its_list_item():
    """Written under an item it is space INSIDE that item — the list stays one
    list, as it does for an indented `:::`."""
    for doc in (
        "- One\n  +++\n  more\n- Two\n",
        "1. One\n\n   ++++\n\n   more\n2. Two\n",
    ):
        root = group(doc)
        items = [
            n
            for n in walk(root)
            if n.type in (NodeType.LIST_ITEM, NodeType.ORDERED_ITEM)
        ]
        assert len(items) == 2, doc
        assert [c.type for c in items[0].children] == [
            NodeType.TEXT,
            NodeType.SPACER,
            NodeType.TEXT,
        ], doc


def test_an_item_with_a_spacer_matches_one_without():
    spaced = [
        n for n in walk(group("- One\n  +++\n  more\n")) if n.type == NodeType.LIST_ITEM
    ]
    plain = [n for n in walk(group("- One\n  more\n")) if n.type == NodeType.LIST_ITEM]
    assert spaced[0].fingerprint_hash == plain[0].fingerprint_hash
    assert spaced[0].kind_hash == plain[0].kind_hash


# ---------------------------------------------------------------------------
# 2 — a spacer never changes what matches
# ---------------------------------------------------------------------------


def test_a_spacer_does_not_change_a_cards_signature():
    plain = group("## Card\n\nBody text here.\n")
    spaced = group("## Card\n\n+++++\n\nBody text here.\n")
    a, b = plain.children[0], spaced.children[0]
    assert a.fingerprint_hash == b.fingerprint_hash
    assert a.kind_hash == b.kind_hash


def test_cards_with_and_without_a_spacer_still_grid():
    doc = "## One\n\n+++\n\nBody.\n\n## Two\n\nBody.\n\n## Three\n\nBody.\n"
    root = group(doc)
    runs = [r for r in (root.repeated_children or {}).values() if len(r) >= 2]
    assert runs and len(runs[0]) == 3


# Every pair is one document written twice: with spacers, and without.
_TWINS = {
    "a spacer closing a card's body": (
        "## A\nBody.\n\n## B\nBody.\n\n+++++\n\n## C\nBody.\n\n## D\nBody.\n",
        "## A\nBody.\n\n## B\nBody.\n\n## C\nBody.\n\n## D\nBody.\n",
    ),
    "a spacer tight under a card's body": (
        "## A\nBody.\n\n## B\nBody.\n+++++\n\n## C\nBody.\n",
        "## A\nBody.\n\n## B\nBody.\n\n## C\nBody.\n",
    ),
    "a spacer between glued lines": ("A line\n+++\nB line\n", "A line\nB line\n"),
    "a spacer in a glued card": (
        "**Title**\nFirst line\n+++\nSecond line\n\nAfter\n",
        "**Title**\nFirst line\nSecond line\n\nAfter\n",
    ),
    "a spacer after a bare heading": (
        "## A\n\n+++\n\n## B\n",
        "## A\n\n## B\n",
    ),
    "a spacer opening the document": ("+++\n\nText\n", "Text\n"),
    "a spacer inside a list item": ("- One\n  +++\n  more\n", "- One\n  more\n"),
    "a spacer between list items' lines": (
        "- One\n  +++\n  more\n- Two\n",
        "- One\n  more\n- Two\n",
    ),
    "a spacer above a photo card's heading": (
        "![\n+++++\n## Card\nBody.\n[Go](/go)\n](https://example.com/a.jpg)\n",
        "![\n## Card\nBody.\n[Go](/go)\n](https://example.com/a.jpg)\n",
    ),
    "a spacer above a loose photo card's heading": (
        "![\n+++++\n\n## Card\n\nBody.\n\n](https://example.com/a.jpg)\n",
        "![\n\n## Card\n\nBody.\n\n](https://example.com/a.jpg)\n",
    ),
}


def _shape(node):
    """What a node IS for matching and layout, spacers removed: no ids, which
    count positions, only the structure and the hashes computed from it."""
    return (
        node.type,
        node.content,
        node.heading_group,
        node.glued_content_group,
        node.fingerprint_hash,
        node.kind_hash,
        node.run_key is not None,
        tuple(_shape(c) for c in node.children if c.type != NodeType.SPACER),
    )


def test_a_spacer_is_invisible_to_structure():
    """The guarantee, stated once (ADR-203): group a document with spacers,
    delete the spacers, and the tree is the one its unspaced twin groups to —
    the same nodes, fingerprints, kind_hash and runs."""
    bad = [
        name
        for name, (spaced, plain) in _TWINS.items()
        if _shape(group(spaced)) != _shape(group(plain))
    ]
    assert not bad, bad


def test_the_spaced_tree_keeps_no_run_from_the_first_analysis():
    """The spaced tree is analyzed a second time once its spacers are in. Its
    runs and orphans must be the ones a single analysis of that tree finds —
    the tree rebuilt from its dict, as layout gets it — so a consumer of the
    live tree never sees a run that no longer exists."""
    text = "___\nLeft cell\n:::\n+++++\nRight cell, pushed down\n:::\nThird cell\n___\n"
    live = session.group_markdown(text, _KIT)
    assert live is not None
    rebuilt = load_grouping_ast_node(live.to_dict())
    ASTPatternAnalyzer(rebuilt).fingerprints(include_unique=True)
    marks = [
        [(n.content, n.run_key, n.orphan_grid) for n in walk(t)]
        for t in (live, rebuilt)
    ]
    assert marks[0] == marks[1], marks


# ---------------------------------------------------------------------------
# 3 — the theme keys
# ---------------------------------------------------------------------------


_THEME = """# T
## Styling & Spacing
### Root
Spacer large: 48
Spacer small row: 12
### Heading 2
Spacer large: 64
### Image Cards
Spacer medium: 200
"""


def test_the_keys_parse_per_level():
    t = theme_from(_THEME)
    assert t.root.spacers == {"large": 48.0, "small row": 12.0}
    assert t.sections[2].spacers == {"large": 64.0}
    assert t.image_cards.spacers == {"medium": 200.0}


def test_an_unusable_value_is_ignored():
    # A spacer is px along one direction: a ratio is not a size it takes.
    for bad in ("wide", "3:2", "-4"):
        t = theme_from(f"# T\n## Styling & Spacing\n### Root\nSpacer small: {bad}\n")
        assert t.root.spacers == {}, bad


def test_defaults_double_per_step():
    for step, px in (("small", 8.0), ("medium", 16.0), ("large", 32.0)):
        assert generator_spacers.spacer_size(None, step, "col", 0) == px


def test_defaults_follow_the_group_gap_along_their_direction():
    """Unstated, a spacer is a multiple of the GROUP gap, so even the small one
    reads as more than a group gap — down 1x/2x/4x, across 1x/1.5x/2x."""
    t = theme_from(
        "# T\n## Styling & Spacing\n### Elements\nRow spacing: 10\n"
        "Col spacing: 10\nGroup row spacing: 20\nGroup col spacing: 16\n"
    )
    size = generator_spacers.spacer_size
    assert [size(t, s, "col", 0) for s in ("small", "medium", "large")] == [
        16.0,
        32.0,
        64.0,
    ]
    assert [size(t, s, "row", 0) for s in ("small", "medium", "large")] == [
        20.0,
        30.0,
        40.0,
    ]
    stated = theme_from(_THEME + "### Elements\nGroup spacing: 20\n")
    assert size(stated, "small", "row", 0) == 12.0  # an explicit key still wins


def test_an_unstated_spacer_never_measures_less_than_its_floor():
    """A theme whose gaps are 0 still draws a written spacer: unstated, it is
    at least 8/16/32 down and 8/12/16 across; a wider gap still scales it."""
    t = theme_from(
        "# T\n## Styling & Spacing\n### Root\nSpacing: 0\n"
        "### Elements\nRow spacing: 0\nCol spacing: 0\nGroup spacing: 0\n"
    )
    size = generator_spacers.spacer_size
    assert [size(t, s, "col", 0) for s in ("small", "medium", "large")] == [
        8.0,
        16.0,
        32.0,
    ]
    assert [size(t, s, "row", 0) for s in ("small", "medium", "large")] == [
        8.0,
        12.0,
        16.0,
    ]
    wide = theme_from("# T\n## Styling & Spacing\n### Elements\nGroup spacing: 18\n")
    assert size(wide, "large", "col", 0) == 72.0  # above the floor: unchanged
    stated = theme_from("# T\n## Styling & Spacing\n### Root\nSpacer small: 0\n")
    assert size(stated, "small", "col", 0) == 0.0  # a stated size is the author's


def test_the_nearest_level_wins_then_root_then_default():
    t = theme_from(_THEME)
    size = generator_spacers.spacer_size
    assert size(t, "large", "col", 2) == 64.0  # Heading 2
    assert size(t, "large", "col", 3) == 48.0  # no Heading 3 -> Root
    assert size(t, "medium", "col", 2) == 16.0  # unstated -> default
    assert size(t, "medium", "col", 2, in_image_card=True) == 200.0


def test_an_axis_override_beats_the_plain_key_on_its_axis_only():
    t = theme_from(_THEME)
    size = generator_spacers.spacer_size
    assert size(t, "small", "row", 0) == 12.0
    assert size(t, "small", "col", 0) == 8.0


# ---------------------------------------------------------------------------
# 4 — the generator hands the resolved size to the leaf
# ---------------------------------------------------------------------------


def test_the_generator_resolves_the_step_at_its_level():
    t = theme_from(_THEME)
    root = group("+++++\n\n## Card\n\n+++++\n\nBody.\n")
    layout = LayoutGenerator().generate(root, 900.0, t)
    sizes = [(s["axis"], s["size"]) for s in spacer_leaves(layout)]
    assert sizes == [("col", 48.0), ("col", 64.0)], sizes


def test_both_image_card_spellings_get_their_spacer():
    """The two ways to write one photo card reach the generator in one shape,
    so both get their space."""
    t = theme_from("# T\n## Styling & Spacing\n### Image Cards\nSpacer large: 200\n")
    tight = "![\n+++++\n## Card\nBody.\n[Go](/go)\n](https://example.com/a.jpg)\n"
    loose = "![\n+++++\n\n## Card\n\nBody.\n\n[Go](/go)\n](https://example.com/a.jpg)\n"
    for doc in (tight, loose):
        layout = LayoutGenerator().generate(group(doc), 900.0, t)
        assert [s["size"] for s in spacer_leaves(layout)] == [200.0], doc


def test_every_layout_leaf_names_a_node_of_the_tree():
    """Spacers go in after the grouper numbered its nodes, so it numbers them
    again. A stale id survives the dict round trip every render takes and
    points a layout leaf at the wrong node, or at none."""
    t = theme_from("# T\n## Styling & Spacing\n### Image Cards\nSpacer large: 200\n")
    for doc in (
        "![\n+++++\n\n## Card\n\nBody.\n\n](https://example.com/a.jpg)\n",
        "+++\n\n## A\nBody.\n+++\n\n## B\nBody.\n",
    ):
        # As every real caller groups: no fingerprint pass of our own, which
        # would number the tree again and hide exactly this.
        grouped = session.group_markdown(doc, _KIT)
        assert grouped is not None
        root, index = session.prepare(grouped, t)
        layout = LayoutGenerator().generate(root, 900.0, t)
        stack, leaves = [layout], []
        while stack:
            n = stack.pop()
            if n.content_id:
                leaves.append(n)
            stack.extend(n.children)
        assert leaves and all(n.content_id in index for n in leaves), doc
        for n in leaves:
            is_spacer = index[n.content_id].get("type") == "spacer"
            assert is_spacer == ("spacer" in (n.render_properties or {})), doc


# ---------------------------------------------------------------------------
# 5 — measurement
# ---------------------------------------------------------------------------


def _h(size, width=300.0, axis="col"):
    return _leaf_height(
        None, width, _FONTS, _T, {"spacer": {"axis": axis, "size": size}}
    )


def test_a_spacer_is_its_px_at_any_width():
    assert _h(24.0, 100.0) == 24.0
    assert _h(24.0, 900.0) == 24.0


def test_a_row_spacer_adds_no_height():
    assert _h(24.0, axis="row") == 0.0


# ---------------------------------------------------------------------------
# 6 — a spacer inside a line
# ---------------------------------------------------------------------------


def _line(text):
    """The node that holds a one-line document's pieces."""
    root = group(text)
    return root.children[0] if root.children else root


def test_an_inline_spacer_groups_like_a_separator():
    """`A +++ B` is a cut like `A | B`: the same pieces, the same hashes — only
    what the gap holds differs (ADR-203)."""
    spaced, piped = _line("Alpha +++ Bravo\n"), _line("Alpha | Bravo\n")
    assert [c.content for c in spaced.children] == ["Alpha", "Bravo"]
    assert spaced.fingerprint_hash == piped.fingerprint_hash
    assert spaced.kind_hash == piped.kind_hash
    assert (
        len(spaced.separator_chars) == 1
        and spaced.separator_chars != piped.separator_chars
    )


def test_a_spacer_at_a_line_edge_is_space_not_a_cut():
    for text, lead, trail in (
        ("+++ Bravo\n", "+++", None),
        ("Bravo ++++\n", None, "++++"),
    ):
        root = group(text)
        line = next(n for n in walk(root) if n.content == "Bravo")
        assert (line.spacer_lead, line.spacer_trail) == (lead, trail), text
        assert line.fingerprint_hash == group("Bravo\n").children[0].fingerprint_hash


def test_inline_spacers_that_are_not_are_text():
    for text, drawn in (
        ("Use `a +++ b` here\n", "Use `a +++ b` here"),
        ("\\+++ text\n", "+++ text"),
        ("C+++ and more\n", "C+++ and more"),
        ("A ++++++ B\n", "A ++++++ B"),
    ):
        root = group(text)
        assert [n.content for n in walk(root) if not n.children] == [drawn], text


def _boxes(text, theme, width=700.0):
    grouped = session.group_markdown(text, _KIT)
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    return session.build_scene(
        LayoutGenerator(), root, index, theme, _FONTS, width
    ).boxes


def test_an_inline_spacer_is_spaced_like_an_element_on_each_side():
    """A spacer is an element of its own width: the gap applies before it and
    after it, as between any two leaves (ADR-203)."""
    t = theme_from(
        "# T\n## Styling & Spacing\n### Elements\nRow spacing: 10\nGroup spacing: 20\n"
    )

    def gap(text):
        leaves = [b for b in _boxes(text, t) if b.content_id]
        return round(leaves[1].x - (leaves[0].x + leaves[0].width), 3)

    element = gap("Alpha | Bravo\n")
    assert element == 10.0
    assert gap("Alpha +++ Bravo\n") == element + 20.0 + element
    assert gap("Alpha +++++ Bravo\n") == element + 40.0 + element


def test_a_trailing_spacer_holds_a_pushed_piece_off_the_edge():
    t = theme_from("# T\n## Styling & Spacing\n### Elements\nGroup spacing: 20\n")

    def right_edge(text):
        return max(b.x + b.width for b in _boxes(text, t) if b.content_id)

    # The spacer's width plus the element gap before it (8 by default).
    assert (
        round(
            right_edge("Title ... [Act](/act)\n")
            - right_edge("Title ... [Act](/act) +++\n"),
            3,
        )
        == 28.0
    )


def _flowed_rows(text, theme, width):
    """Each laid-out row of a flowed line as a string: x piece, | separator,
    _ spacer."""
    grouped = session.group_markdown(text, _KIT)
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    layout = LayoutGenerator().generate(root, width, theme)
    out = []

    def rec(n):
        if n.type == "row":
            out.append(
                "".join(
                    "|"
                    if (c.render_properties or {}).get("separator")
                    else "_"
                    if (c.render_properties or {}).get("spacer")
                    else "x"
                    for c in n.children
                )
            )
        for c in n.children:
            rec(c)

    rec(layout)
    return out


_WRAP_THEME = "# T\n## Styling & Spacing\n### Elements\nGroup spacing: 20\n## Separators\nBar: show\n"
_WORDS = [
    "`Alpha`",
    "`Bravo`",
    "`Charlie`",
    "`Delta`",
    "`Echo`",
    "`Foxtrot`",
    "`Golf`",
    "`Hotel`",
]


def test_a_wrapped_line_drops_the_gap_it_wrapped_at():
    """A separator or spacer between pieces exists only between neighbours:
    no wrapped row starts or ends on one — the dangling `|` included."""
    t = theme_from(_WRAP_THEME)
    for sep in ("|", "+++"):
        rows = _flowed_rows(f" {sep} ".join(_WORDS * 2) + "\n", t, 420.0)
        assert len(rows) > 1, sep
        for r in rows:
            assert r[0] == "x" and r[-1] == "x", (sep, rows)


def test_a_lines_own_edge_spacers_stay_at_its_ends():
    t = theme_from(_WRAP_THEME)
    rows = _flowed_rows("+++ " + " ".join(_WORDS * 2) + " +++\n", t, 420.0)
    assert len(rows) > 1
    assert rows[0][0] == "_" and rows[-1][-1] == "_", rows
    assert all(r[0] == "x" for r in rows[1:]) and all(r[-1] == "x" for r in rows[:-1])


def test_trim_keeps_a_row_that_holds_content():
    from md2ui.pipeline.generator_spacers import spacer_cell, trim_row_edges
    from md2ui.pipeline.markdown_grouper import MarkdownGroupNode

    word = MarkdownGroupNode(type=NodeType.TEXT, content="w")
    gap, edge = spacer_cell("+++"), spacer_cell("+++", edge=True)
    rows = trim_row_edges(
        [([gap, word, gap], [1, 2, 3]), ([gap], [1]), ([edge, word], [4, 5])]
    )
    assert [(b, w) for b, w in rows] == [([word], [2]), ([edge, word], [4, 5])]


def test_consecutive_spacers_are_one_spacer_of_their_summed_size():
    """Every mark counts and no gap opens between two blanks: spacers that sit
    together merge, down a column (blank lines between them included) and
    across a line alike."""
    t = theme_from("# T\n## Styling & Spacing\n### Elements\nGroup spacing: 20\n")

    def spacers(text):
        grouped = session.group_markdown(text, _KIT)
        assert grouped is not None
        root, _index = session.prepare(grouped, t)
        layout = LayoutGenerator().generate(root, 700.0, t)
        return [sp["size"] for sp in spacer_leaves(layout)]

    assert spacers("A\n+++\n+++\nB\n") == [40.0]  # 20 + 20 down
    assert spacers("A\n+++\n\n++++\nB\n") == [60.0]  # 20 + 40
    assert spacers("A +++ +++ B\n") == [40.0]  # 20 + 20 across
    assert spacers("A +++ ++++ B\n") == [50.0]  # 20 + 30
    # …and at a line's edges, where each run is the line's own space.
    assert spacers("+++ +++ A\n") == [40.0]
    assert spacers("A ++++ +++\n") == [50.0]
    text = next(n for n in walk(group("+++ +++ A ++++ +++\n")) if n.content == "A")
    assert (text.spacer_lead, text.spacer_trail) == ("+++ +++", "++++ +++"), text


def test_spacers_alone_on_a_line_are_one_spacer_down_the_page():
    """With nothing else on the line, several spacers are ONE vertical spacer of
    their summed size — the same as the marks on stacked lines. Beside content
    they stay inline spacers across the line."""
    t = theme_from("# T\n## Styling & Spacing\n### Elements\nGroup spacing: 20\n")
    one_line = group("A\n\n+++ +++ ++++\n\nB\n")
    stacked = group("A\n\n+++\n\n+++\n\n++++\n\nB\n")
    assert [(n.type, n.content) for n in one_line.children] == [
        (n.type, n.content) for n in stacked.children
    ], [(n.type, n.content) for n in one_line.children]
    grouped = session.group_markdown("A\n\n+++ +++ ++++\n\nB\n", _KIT)
    assert grouped is not None
    root, _index = session.prepare(grouped, t)
    layout = LayoutGenerator().generate(root, 700.0, t)
    assert [(sp["axis"], sp["size"]) for sp in spacer_leaves(layout)] == [("col", 80.0)]
    beside = next(n for n in walk(group("+++ +++ A\n")) if n.content == "A")
    assert beside.spacer_lead == "+++ +++", beside.spacer_lead


def test_merged_marks_keep_their_written_order():
    root = group("A\n+++\n\n++++\nB\n")
    assert [n.content for n in walk(root) if n.type == NodeType.SPACER] == ["+++ ++++"]


def test_a_gap_keeps_every_separator_it_holds():
    """The empty piece between two separators is dropped, not the separators:
    `A | | B` draws both bars, and `A | +++ B` the bar and then the space."""
    t = theme_from(_WRAP_THEME)
    assert _flowed_rows("`A` | | `B`\n", t, 700.0) == ["x||x"]
    assert _flowed_rows("`A` | +++ `B`\n", t, 700.0) == ["x|_x"]
    assert _flowed_rows("`A` +++ | +++ `B`\n", t, 700.0) == ["x_|_x"]


def test_a_key_values_gaps_are_kept_like_a_lines():
    """A value is a line of its own pieces: a spacer (or a drawn separator)
    between them is put back, as on any line."""
    t = theme_from(_WRAP_THEME)
    rows = _flowed_rows("Key: `A` +++ `B` | `C`\n", t, 900.0)
    assert "x_x|x" in rows, rows


def _chip_and_spacer(text, theme, width):
    grouped = session.group_markdown(text, _KIT)
    assert grouped is not None
    root, index = session.prepare(grouped, theme)
    boxes = session.build_scene(
        LayoutGenerator(), root, index, theme, _FONTS, width
    ).boxes
    chips = [
        b.width
        for b in boxes
        if index.get(b.content_id, {}).get("type") == "inline_code"
    ]
    spacers = [b.width for b in boxes if (b.render_properties or {}).get("spacer")]
    return chips, spacers


def test_a_spacer_never_widens_or_squeezes_a_row():
    """Short of room, a row gives up its spacers first: they shrink, then leave
    the row with their gap — and the content keeps its width."""
    t = theme_from(
        "# T\n## Styling & Spacing\n### Elements\nRow spacing: 10\nGroup spacing: 20\n"
    )
    chip = "`Identifier_Wide_Chip_Name_Longer_Still_Now_And_Longer_Again`"
    (natural,), _ = _chip_and_spacer(f"{chip} +++ x\n", t, 1400.0)
    grouped = session.group_markdown(f"+++++ {chip}\n", _KIT)
    assert grouped is not None
    root, _index = session.prepare(grouped, t)
    floor = session.effective_width(root, t, _FONTS, 10.0)
    assert round(floor, 1) == round(max(natural, 320.0), 1)  # no spacer in it
    for text in (f"+++++ {chip}\n", f"{chip} +++++\n"):
        chips, spacers = _chip_and_spacer(text, t, floor)
        assert chips == [natural] and spacers == [], (text, chips, spacers)
        # 20px short of chip + gap + 40px spacer: the spacer alone gives 20.
        chips, spacers = _chip_and_spacer(text, t, natural + 10.0 + 20.0)
        assert chips == [natural] and [round(w, 3) for w in spacers] == [20.0], (
            text,
            chips,
            spacers,
        )


def test_a_spacer_beside_a_paragraph_keeps_its_space():
    """Prose wraps, so a paragraph with the room its length needs (a 41–100
    word paragraph's 580px floor) is not "short of room": the spacers at its
    edges keep their full width, like a separator, and the text wraps between
    them."""
    t = theme_from(
        "# T\n## Styling & Spacing\n### Elements\nRow spacing: 10\nGroup spacing: 20\n"
    )
    prose = (
        "A paragraph of plain words that runs on well past the width of the row. " * 4
    )
    boxes = _boxes(f"+++++ {prose}+++++\n", t, 700.0)
    spacers = [b.width for b in boxes if (b.render_properties or {}).get("spacer")]
    assert [round(w, 3) for w in spacers] == [40.0, 40.0], spacers  # full size
    text = next(b for b in boxes if not (b.render_properties or {}).get("spacer"))
    assert text.x >= 40.0 and text.x + text.width <= 700.0 - 40.0 + 0.5, text


def _prose_and_spacers(text, theme, width):
    boxes = _boxes(text, theme, width)
    spacers = [b.width for b in boxes if (b.render_properties or {}).get("spacer")]
    prose = next(b for b in boxes if not (b.render_properties or {}).get("spacer"))
    return prose, spacers


def test_a_spacer_gives_way_before_a_paragraph_is_squeezed():
    """Below a paragraph's floor the spacers beside it give way before the
    prose wraps any narrower: at 520px a 56-word paragraph (580px floor) cannot
    keep its floor even alone, so its spacers leave and it takes the row."""
    t = theme_from(
        "# T\n## Styling & Spacing\n### Elements\nRow spacing: 10\nGroup spacing: 20\n"
    )
    prose = (
        "A paragraph of plain words that runs on well past the width of the row. " * 4
    )
    text, spacers = _prose_and_spacers(f"+++++ {prose}+++++\n", t, 520.0)
    assert spacers == [], spacers
    assert text.x <= 0.5 and text.width >= 520.0 - 0.5, text


def test_a_spacer_shrinks_to_a_medium_texts_floor():
    """A 10–40 word text's floor is 320px: at 400px its spacers shrink, equally,
    only as far as that floor needs, and keep the rest of their space."""
    t = theme_from(
        "# T\n## Styling & Spacing\n### Elements\nRow spacing: 10\nGroup spacing: 20\n"
    )
    prose = "A sentence of plain words that runs on past the width of the row. " * 2
    text, spacers = _prose_and_spacers(f"+++++ {prose}+++++\n", t, 400.0)
    assert len(spacers) == 2 and 0.0 < spacers[0] < 40.0, spacers
    assert round(spacers[0], 3) == round(spacers[1], 3), spacers
    assert text.width >= 320.0 - 0.5, text


def test_a_column_row_wraps_before_its_spacers_give_way():
    """A `:::` cell asks for its line with its spacers at full size: where the
    padded paragraph cannot sit beside the label, it takes a line of its own,
    and only there do its spacers shrink — never beside the label."""
    t = theme_from(
        "# T\n## Styling & Spacing\n### Elements\nRow spacing: 10\nGroup spacing: 20\n"
    )
    prose = "A sentence of plain words that runs on past the width of the row. " * 2
    doc = f"Label\n:::0\n+++++ +++++ {prose}+++++ +++++\n:::2\n___\n"
    grouped = session.group_markdown(doc, _KIT)
    assert grouped is not None
    root, index = session.prepare(grouped, t)

    def box(boxes, start):
        text = lambda b: index.get(b.content_id, {}).get("content") or ""  # noqa: E731
        return next(b for b in boxes if text(b).startswith(start))

    for width, stacked in ((500.0, True), (900.0, False)):
        boxes = session.build_scene(LayoutGenerator(), root, index, t, _FONTS, width)
        label, body = box(boxes.boxes, "Label"), box(boxes.boxes, "A sentence")
        assert (body.y >= label.y + label.height) == stacked, (width, label, body)


def test_a_spacer_in_a_column_row_is_a_leaf_of_its_cell():
    """A `:::` row holds cells, never a spacer: one written under a cell's
    content stays in that cell, stacked, and the row keeps its two cells and
    their weights — it does not become a third cell beside them."""
    root = group("- PROGRESS\n\n+++++\n\n:::0\n\nText beside it.\n\n:::2\n")
    row = next(n for n in walk(root) if n.column_row_group)
    assert row.column_weights == (0, 2), row.column_weights
    assert len(row.children) == 2, [c.type for c in row.children]
    cell = row.children[0]
    assert [c.type for c in cell.children] == [NodeType.LIST_ITEM, NodeType.SPACER]


def test_a_spacer_down_a_column_asks_for_no_width():
    """A vertical spacer is height only, so a fit-to-content (`:::0`) cell or a
    packed card that holds one stays as wide as its content; across a line a
    spacer is exactly its size."""
    from md2ui.pipeline.render_measure import _leaf_natural_width

    down = {"spacer": {"axis": "col", "size": 56.0}}
    across = {"spacer": {"axis": "row", "size": 56.0}}
    assert _leaf_natural_width(None, 500.0, _FONTS, Theme(), down) == 0.0
    assert _leaf_natural_width(None, 500.0, _FONTS, Theme(), across) == 56.0


# ---------------------------------------------------------------------------
# 7 — a `:::` row that flows records its spacers the way a line does
# ---------------------------------------------------------------------------

_MARK = "\ue140"  # the gap mark a `+++` leaves in `separator_chars`


def _row(text):
    return next(n for n in walk(group(text)) if n.column_row_group)


def test_a_spacer_between_two_dividers_is_a_gap():
    """`+++` alone between two `:::` is space between the cells, as
    `A +++ B` is between pieces: no third cell, no spacer down the page."""
    row = _row("Alpha beta gamma\n\n:::\n\n+++\n\n:::\n\nDelta epsilon\n")
    assert [c.content for c in row.children] == ["Alpha beta gamma", "Delta epsilon"]
    assert row.separator_chars == [_MARK], row.separator_chars
    assert not any(n.type == NodeType.SPACER for n in walk(row))
    assert row.kind_hash == _line("Alpha beta gamma +++ Delta epsilon\n").kind_hash


def test_a_spacer_cell_is_kept_for_the_row_build():
    """A spacer that is all of a `:::` cell stays in the plain grouping's text,
    so its row is decided as written; one beside a cell's content goes."""
    doc = "## \n\nText\n\n:::\n\n++++\n\n## \n\nNext\n"
    assert strip_spacer_lines(doc) is None
    # A comment is not a neighbour: the grouping never sees it.
    commented = doc.replace("## \n\nNext", "<!-- the next one\n-->\n## \n\nNext")
    assert strip_spacer_lines(commented) is None
    beside = "Text\n\n++++\n\n:::\n\nB\n"
    assert strip_spacer_lines(beside) == "Text\n\n\n:::\n\nB\n"


def test_a_spacer_cell_does_not_close_its_section():
    """`Text` `:::` `++++` is a row inside its section — Text with space after
    it — never a section closed by its last `:::` that takes the next section
    in as a second cell."""
    root = group("## \n\nText\n\n:::\n\n++++\n\n## \n\nNext section\n")
    assert not any(n.column_row_group for n in walk(root))
    text = next(n for n in walk(root) if n.content == "Text")
    assert (text.spacer_lead, text.spacer_trail) == (None, "++++")
    assert not any(n.type == NodeType.SPACER for n in walk(root))


def test_a_leading_spacer_cell_is_space_before_the_cell():
    """`++++` `:::` `Text`: the spacer cell is not dropped as empty; it is the
    space before Text, as `++++ Text` is."""
    root = group("## \n\n++++\n\n:::\n\nText\n")
    text = next(n for n in walk(root) if n.content == "Text")
    assert (text.spacer_lead, text.spacer_trail) == ("++++", None)
    assert not any(n.type == NodeType.SPACER for n in walk(root))


def test_spacer_cells_on_both_sides_hold_the_cell():
    """A cell between two spacer cells is held between them, as a paragraph is
    by `+++++ text +++++`: the space is the block's own, across, never space
    down the page above and below it."""
    pairs = "Key: ... value\nKey: ... value\nKey: ... value\n"
    root = group(f"## \n\n++++\n\n:::\n\n{pairs}\n:::\n\n++++\n")
    held = [n for n in walk(root) if n.spacer_lead or n.spacer_trail]
    assert len(held) == 1, held
    assert (held[0].spacer_lead, held[0].spacer_trail) == ("++++", "++++")
    assert len(held[0].children) == 3, [c.type for c in held[0].children]
    assert not any(n.type == NodeType.SPACER for n in walk(root))


def test_a_spacer_cell_twins_the_card_without_it():
    """A spacer cell is blank space, never structure: a card that has one and
    a card that does not are the same kind and still run together."""
    for doc in (
        "## \n\nText one\n\n:::\n\n++++\n\n## \n\nText two\n",
        "## \n\n++++\n\n:::\n\nKey: ... a\nKey: ... b\n\n:::\n\n++++\n\n"
        "## \n\nKey: ... a\nKey: ... b\n",
    ):
        first, second = group(doc).children
        assert first.fingerprint_hash == second.fingerprint_hash, doc
        assert first.kind_hash == second.kind_hash, doc


def _surfaces(layout):
    if layout.section_level is not None or layout.is_card:
        yield layout
    for child in layout.children:
        yield from _surfaces(child)


def test_a_cards_edge_spacers_are_inside_it():
    """The space a card's edge spacers make is inside the card, between its
    edge and its content: the card keeps the width it has without them."""
    for doc in ("## \n\n++++\n\n:::\n\nText\n", "## \n\n++++ Text\n"):
        surfaces = list(_surfaces(_layout(doc, Theme(), 700.0)))
        assert len(surfaces) == 1, (doc, surfaces)
        assert surfaces[0].type == "row", doc
        assert spacer_leaves(surfaces[0]), doc


def test_a_held_block_floors_at_its_own_minimum():
    """A block held between two spacer cells keeps them while it has its own
    minimum width beside them, as a paragraph keeps them while it has its
    reading width; on a narrow screen they give way before it is squeezed."""
    t = theme_from(
        "# T\n## Styling & Spacing\n### Elements\nRow spacing: 10\nGroup spacing: 20\n"
    )
    # Words too long to wrap, so the block's minimum is wide.
    pairs = "Supercalifragilistic: ... Pneumonoultramicroscopic\nOwed: ... 1,234.00\n"
    doc = f"## \n\n+++++ +++++\n\n:::\n\n{pairs}\n:::\n\n+++++ +++++\n"
    sizes = {}
    for width in (767.0, 320.0):
        boxes = _boxes(doc, t, width)
        sizes[width] = [
            b.width for b in boxes if (b.render_properties or {}).get("spacer")
        ]
    assert len(sizes[767.0]) == 2 and sizes[767.0][0] > 50.0, sizes
    assert len(sizes[320.0]) < 2 or sizes[320.0][0] < sizes[767.0][0], sizes


def test_spacer_cells_at_a_rows_ends_are_the_rows():
    """With two cells left, spacer cells at the ends are the row's own edges,
    as `+++ A | B +++` puts them on the line."""
    row = _row("++++\n\n:::\n\nAlpha\n\n:::\n\nBravo\n\n:::\n\n+++\n")
    assert [c.content for c in row.children] == ["Alpha", "Bravo"]
    assert (row.spacer_lead, row.spacer_trail) == ("++++", "+++")
    assert not row.separator_chars
    both = "++++\n\n:::\n\nAlpha\n\n:::\n\n+++\n\n:::\n\nBravo\n\n:::\n\n+++\n"
    row = _row(both)
    assert [c.content for c in row.children] == ["Alpha", "Bravo"]
    assert (row.spacer_lead, row.spacer_trail) == ("++++", "+++")
    assert row.separator_chars == [_MARK], row.separator_chars


def test_a_spacer_at_a_cells_inner_edge_is_a_gap():
    for text in (
        "Alpha beta\n:::\n+++ Gamma delta\n",
        "Alpha beta +++\n:::\nGamma delta\n",
    ):
        row = _row(text)
        assert row.separator_chars == [_MARK], (text, row.separator_chars)
        assert not any(n.spacer_lead or n.spacer_trail for n in walk(row)), text


def test_a_spacer_at_a_rows_outer_edge_is_the_rows():
    """The row is the line, so space at its ends is the row's own, as
    `+++ A | B` puts it on the line."""
    lead = _row("+++ Alpha beta\n:::\nGamma delta\n")
    trail = _row("Alpha beta\n:::\nGamma delta +++\n")
    assert (lead.spacer_lead, lead.spacer_trail) == ("+++", None)
    assert (trail.spacer_lead, trail.spacer_trail) == (None, "+++")
    assert not lead.separator_chars and not trail.separator_chars
    for row in (lead, trail):
        assert not any(c.spacer_lead or c.spacer_trail for c in row.children)


def test_a_weighted_rows_spacers_are_its_gaps():
    """A number or a `<` / `>` changes how a row shares its width, not where
    its space is: its gaps and edges are recorded as a line's are."""
    for text in (
        "Alpha beta\n:::1\n+++ Gamma delta\n:::1\n",
        "Alpha beta\n\n:::1\n\n+++\n\n:::1\n\nGamma delta\n",
        "Alpha beta\n::: <\n+++ Gamma delta\n",
    ):
        row = _row(text)
        assert row.separator_chars == [_MARK], (text, row.separator_chars)
        assert not any(n.type == NodeType.SPACER for n in walk(row)), text
        assert not any(n.spacer_lead or n.spacer_trail for n in walk(row)), text
    edges = _row("+++ Alpha beta\n:::2\nGamma delta +++\n")
    assert (edges.spacer_lead, edges.spacer_trail) == ("+++", "+++")


def test_a_flowing_rows_gap_is_laid_between_its_cells():
    """The generator puts a row's gap between its cells, as it does a line's,
    whether the row flows or is weighted."""
    t = theme_from(_WRAP_THEME)
    gap = "Alpha beta\n\n:::\n\n+++\n\n:::\n\nGamma delta\n"
    assert _flowed_rows(gap, t, 700.0) == ["x_x"], _flowed_rows(gap, t, 700.0)
    edge = "Alpha beta\n:::\n+++ Gamma delta\n"
    assert _flowed_rows(edge, t, 700.0) == ["x_x"], _flowed_rows(edge, t, 700.0)
    weighted = "Alpha beta\n:::1\n+++ Gamma delta\n:::1\n"
    assert _flowed_rows(weighted, t, 700.0) == ["x_x"], _flowed_rows(weighted, t, 700.0)


def _layout(text, theme, width):
    grouped = session.group_markdown(text, _KIT)
    assert grouped is not None
    root, _ = session.prepare(grouped, theme)
    return LayoutGenerator().generate(root, width, theme)


def test_a_weighted_rows_gap_is_a_cell_of_no_weight():
    """The gap takes no share of the row's width: the cells keep their
    weights and the spacer between them is pinned to its own size."""
    t = theme_from(_WRAP_THEME)
    layout = _layout("Alpha beta\n:::1\n+++++ Gamma delta\n:::3\n", t, 700.0)
    rows = [n for n in walk(layout) if getattr(n, "column_row", False)]
    assert len(rows) == 1 and rows[0].ratios == [1, 0.0, 3], [r.ratios for r in rows]


def test_a_weighted_row_wraps_before_its_gap_gives_way():
    """Case G of tests-spacer-edges.md: where the two cells and the gap
    between them do not fit, the row wraps and the gap drops, as a line's
    does — the second cell does not take its spacer onto a line of its own."""
    t = theme_from(_WRAP_THEME)
    text = "Alpha beta gamma\n:::1\n+++++ Delta epsilon zeta theta\n:::1\n"
    assert _flowed_rows(text, t, 700.0) == ["x_x"], _flowed_rows(text, t, 700.0)
    narrow = _layout(text, t, 220.0)
    assert _flowed_rows(text, t, 220.0) == [], _flowed_rows(text, t, 220.0)
    assert spacer_leaves(narrow) == [], spacer_leaves(narrow)


def test_a_weighted_rows_spacer_gives_way_before_a_cell_is_narrowed():
    """Case G of tests-spacer-edges.md: where the weighted
    shares would wrap a cell's text, the spacer between the cells gives way
    first, as in a plain line; with room for both it keeps its size."""
    if sys.platform != "darwin":
        raise unittest.SkipTest("its sizes are measured in macOS's default face")
    t = theme_from(
        "# T\n## Styling & Spacing\n### Elements\nRow spacing: 10\nGroup spacing: 20\n"
    )
    text = "Alpha beta gamma\n:::1\n+++++ Delta epsilon zeta theta\n:::1\n"
    for width, size in ((320.0, 28.3), (700.0, 40.0)):
        boxes = _boxes(text, t, width)
        spacers = [b.width for b in boxes if (b.render_properties or {}).get("spacer")]
        assert [round(w, 1) for w in spacers] == [size], (width, spacers)
        cells = [b for b in boxes if b.content_id]
        assert all(b.height < 30.0 for b in cells), (width, cells)  # one line each


def test_a_held_cell_keeps_its_spacers():
    """A cell with a spacer on BOTH edges is held to a narrower column, in a
    weighted row or one that flows: the spacers stay the cell's own and its
    text wraps between them, rather than the row taking them as gaps."""
    t = theme_from(
        "# T\n## Styling & Spacing\n### Elements\nRow spacing: 10\nGroup spacing: 20\n"
    )
    prose = "A sentence of plain words that runs on past the width of the row. " * 2
    for divider in (":::0", ":::"):
        doc = f"Label\n{divider}\n+++++ +++++ {prose}+++++ +++++\n___\n"
        row = _row(doc)
        cell = row.children[1]
        assert (cell.spacer_lead, cell.spacer_trail) == ("+++++ +++++",) * 2
        assert not row.separator_chars and not row.spacer_trail, divider
        grouped = session.group_markdown(doc, _KIT)
        assert grouped is not None
        root, index = session.prepare(grouped, t)
        boxes = session.build_scene(LayoutGenerator(), root, index, t, _FONTS, 500.0)
        text = lambda b: index.get(b.content_id, {}).get("content") or ""  # noqa: E731
        body = next(b for b in boxes.boxes if text(b).startswith("A sentence"))
        assert body.height > 30.0, (divider, body)  # it wraps
        assert body.x >= 40.0 and body.x + body.width <= 500.0 - 40.0, (divider, body)


def test_a_cut_rows_gaps_stand_between_what_stands_apart():
    """A `<` / `>` row keeps the gap after each group of cells that stands as
    one; a gap between two cells that stack falls where they stack."""
    t = theme_from(_WRAP_THEME)
    for divider in ("::: <", "::: 1 <"):
        text = f"Alpha\n{divider}\n+++++ Delta\n:::\n+++ Zeta\n"
        row = _row(text)
        assert row.separator_chars == ["\ue142", _MARK], row.separator_chars
        assert _flowed_rows(text, t, 500.0) == ["x_x_x"], (divider, "narrow")
        wide = _layout(text, t, 900.0)
        assert _flowed_rows(text, t, 900.0) == ["x_x"], (divider, "wide")
        assert len(spacer_leaves(wide)) == 1, spacer_leaves(wide)


# ``fold_row_spacers`` on hand-built rows: no document reaches its spacer branch
# today (the grouper moves a spacer written in a `:::` cell into that cell), so
# these rows are built directly.


def _fold_spacer(binds=None):
    return LayoutNode(
        type="-",
        ratios=[],
        children=[],
        render_properties={"spacer": {"axis": "col", "size": 20.0, "binds": binds}},
    )


def _fold_leaf(name):
    return LayoutNode(
        type="leaf", ratios=[], children=[], render_properties={"t": name}
    )


def _fold_names(node):
    if node.type == "-":
        return "-"
    if node.children:
        return [_fold_names(c) for c in node.children]
    return node.render_properties["t"]


def test_a_spacer_that_binds_back_stacks_under_the_cell_before_it():
    row = LayoutNode(
        type="row",
        ratios=[1.0, 1.0, 1.0],
        children=[_fold_leaf("A"), _fold_spacer("prev"), _fold_leaf("B")],
    )
    generator_spacers.fold_row_spacers(row)
    assert _fold_names(row) == [["A", "-"], "B"], _fold_names(row)
    assert row.ratios == [1.0, 1.0], row.ratios


def test_a_row_of_spacers_alone_keeps_them():
    spacers = [_fold_spacer(), _fold_spacer()]
    row = LayoutNode(type="row", ratios=[1.0, 1.0], children=list(spacers))
    generator_spacers.fold_row_spacers(row)
    assert row.children == spacers, row.children
    assert row.ratios == [1.0, 1.0], row.ratios


def test_a_row_short_of_ratios_keeps_every_cell():
    row = LayoutNode(
        type="row",
        ratios=[1.0, 2.0],
        children=[_fold_leaf("A"), _fold_spacer(), _fold_leaf("B"), _fold_leaf("C")],
    )
    generator_spacers.fold_row_spacers(row)
    assert _fold_names(row) == ["A", ["-", "B"], "C"], _fold_names(row)
    assert row.ratios == [1.0, 1.0, 1.0], row.ratios


def _down_around_the_row(doc):
    """The card's layout and the merged node of a card holding only a row."""
    row = next(n for n in walk(group(doc)) if n.line_split_group or n.column_row_group)
    (card,) = _surfaces(_layout(doc, Theme(), 600.0))
    return row, card


def test_spacers_beside_a_cards_only_line_are_above_and_below_it():
    """A card holding a spacer, one split line and a spacer is merged with its
    line by the plain grouping; the spacers are space above and below the
    line inside the card, never cells of the line."""
    row, card = _down_around_the_row("#### \n\n+++++\n\nAlpha - Bravo\n\n+++++\n")
    assert (row.spacer_above, row.spacer_below) == ("+++++", "+++++")
    assert not any(n.type == NodeType.SPACER for n in walk(row))
    assert [c.type for c in card.children] == ["-", "row", "-"], card.children
    axes = [
        (c.render_properties or {}).get("spacer", {}).get("axis") for c in card.children
    ]
    assert axes == ["col", None, "col"], axes
    assert not spacer_leaves(card.children[1])
    round_trip = type(row).from_dict(row.to_dict())
    assert (round_trip.spacer_above, round_trip.spacer_below) == ("+++++", "+++++")


def test_spacers_beside_a_cards_only_column_row_are_above_and_below_it():
    """The same with a `;;;`-closed `:::` row: the spacers are outside the
    row, not at the start of its first cell and the end of its last."""
    doc = "#### \n\n+++++\n\n;;;\n\nAlpha\n\n:::\n\nBravo\n\n;;;\n\n+++++\n"
    row, card = _down_around_the_row(doc)
    assert row.column_row_group
    assert (row.spacer_above, row.spacer_below) == ("+++++", "+++++")
    assert [c.content for c in row.children] == ["Alpha", "Bravo"]
    assert [c.type for c in card.children] == ["-", "row", "-"], card.children
    assert not spacer_leaves(card.children[1])


def _boxes_holding_spacers(layout):
    """For each spacer leaf, whether a list item's own box encloses it."""
    out = []

    def rec(n, boxed):
        boxed = boxed or n.background_kind is not None
        if (n.render_properties or {}).get("spacer") is not None:
            out.append(boxed)
        for c in n.children:
            rec(c, boxed)

    rec(layout, False)
    return out


def test_a_spacer_cell_beside_a_list_item_is_outside_its_box():
    """A spacer-only `:::` cell beside a list item is a cell beside it: its
    space is outside the box the item paints."""
    cells = "+++++ +++++"
    doc = f"#### T\n\n;;;\n\n{cells}\n\n:::\n\n- Item\n\n;;;\n\n- Item\n\n:::\n\n{cells}\n\n;;;\n"
    items = [n for n in walk(group(doc)) if n.type == NodeType.LIST_ITEM]
    assert [(n.spacer_lead, n.spacer_trail) for n in items] == [
        (cells, None),
        (None, cells),
    ]
    assert all(n.spacer_beside for n in items)
    assert _boxes_holding_spacers(_layout(doc, Theme(), 600.0)) == [False, False]
    many = f"#### T\n\n;;;\n\n{cells}\n\n:::\n\n- Item\n  more\n\n;;;\n"
    assert _boxes_holding_spacers(_layout(many, Theme(), 600.0)) == [False]


def _spaced_items(first: str, second: str) -> str:
    """Two `:::` rows, each a spacer cell beside a list item that splits on
    ` - `; *first* / *second* say which side each row's spacer is on."""
    cell, item = "+++++ +++++", "- List item - [Link](/x)"

    def row(side):
        cells = [cell, item] if side == "lead" else [item, cell]
        return "\n\n:::\n\n".join(cells)

    return f"#### T\n\n;;;\n\n{row(first)}\n\n;;;\n\n{row(second)}\n\n;;;\n"


def test_a_spacer_cell_beside_a_split_list_item_is_outside_its_box():
    """The same when the item splits into a line: the line keeps the item's
    box and the space stands beside it, as a cell would."""
    doc = _spaced_items("lead", "trail")
    items = [n for n in walk(group(doc)) if n.type == NodeType.LIST_ITEM]
    assert all(n.line_split_group and n.spacer_beside for n in items)
    assert _boxes_holding_spacers(_layout(doc, Theme(), 600.0)) == [False, False]


def test_a_spacer_cell_holds_the_item_beside_it():
    """The item beside a spacer cell narrows to its minimum before the space
    gives way, as it would beside a leaf cell: a pushed line (`...`) asks the
    whole width, and its floor is still its own minimum."""
    doc = _spaced_items("lead", "trail").replace("(/x)", "(/x) ... ***➡️***")
    floors = [
        (n.render_properties or {}).get("held_floor")
        for n in walk(_layout(doc, Theme(), 600.0))
        if n.background_kind is not None
    ]
    assert len(floors) == 2 and all(f is not None and f < 300 for f in floors), floors


def test_spacer_cells_run_as_the_leaf_cells_they_stand_for():
    """A spacer cell beside an item is where a leaf cell would be, and the
    items run as they would with that leaf beside them: a cell on different
    sides keeps two rows apart (they stack), on the same side they run. The card holding them still twins one without them."""
    apart = [n for n in walk(group(_spaced_items("lead", "trail"))) if n.spacer_beside]
    assert [n.run_key for n in apart] == [None, None], apart
    together = [
        n for n in walk(group(_spaced_items("lead", "lead"))) if n.spacer_beside
    ]
    assert len(together) == 2 and together[0].run_key is not None
    assert together[0].run_key == together[1].run_key


def test_a_spacer_inside_a_list_items_line_is_inside_its_box():
    """`- +++ Item` writes the space inside the item's own line: it stays
    inside the item's box."""
    doc = "#### T\n\n- +++++ Item\n- Item +++++\n"
    items = [n for n in walk(group(doc)) if n.type == NodeType.LIST_ITEM]
    assert not any(n.spacer_beside for n in items)
    assert _boxes_holding_spacers(_layout(doc, Theme(), 600.0)) == [True, True]


TESTS = [
    test_three_to_five_plus_signs_are_a_spacer,
    test_other_counts_and_shapes_are_text,
    test_only_spacer_lines_are_taken_out_for_the_plain_grouping,
    test_an_escaped_spacer_is_text,
    test_the_spacer_survives_as_a_leaf_with_its_spelling,
    test_an_indented_spacer_stays_inside_its_list_item,
    test_an_item_with_a_spacer_matches_one_without,
    test_a_spacer_does_not_change_a_cards_signature,
    test_cards_with_and_without_a_spacer_still_grid,
    test_a_spacer_is_invisible_to_structure,
    test_the_spaced_tree_keeps_no_run_from_the_first_analysis,
    test_the_keys_parse_per_level,
    test_an_unusable_value_is_ignored,
    test_defaults_double_per_step,
    test_defaults_follow_the_group_gap_along_their_direction,
    test_an_unstated_spacer_never_measures_less_than_its_floor,
    test_the_nearest_level_wins_then_root_then_default,
    test_an_axis_override_beats_the_plain_key_on_its_axis_only,
    test_the_generator_resolves_the_step_at_its_level,
    test_both_image_card_spellings_get_their_spacer,
    test_every_layout_leaf_names_a_node_of_the_tree,
    test_a_spacer_is_its_px_at_any_width,
    test_a_row_spacer_adds_no_height,
    test_an_inline_spacer_groups_like_a_separator,
    test_a_spacer_at_a_line_edge_is_space_not_a_cut,
    test_inline_spacers_that_are_not_are_text,
    test_an_inline_spacer_is_spaced_like_an_element_on_each_side,
    test_a_trailing_spacer_holds_a_pushed_piece_off_the_edge,
    test_a_wrapped_line_drops_the_gap_it_wrapped_at,
    test_a_lines_own_edge_spacers_stay_at_its_ends,
    test_trim_keeps_a_row_that_holds_content,
    test_consecutive_spacers_are_one_spacer_of_their_summed_size,
    test_spacers_alone_on_a_line_are_one_spacer_down_the_page,
    test_merged_marks_keep_their_written_order,
    test_a_gap_keeps_every_separator_it_holds,
    test_a_key_values_gaps_are_kept_like_a_lines,
    test_a_spacer_never_widens_or_squeezes_a_row,
    test_a_spacer_beside_a_paragraph_keeps_its_space,
    test_a_spacer_gives_way_before_a_paragraph_is_squeezed,
    test_a_spacer_shrinks_to_a_medium_texts_floor,
    test_a_column_row_wraps_before_its_spacers_give_way,
    test_a_spacer_in_a_column_row_is_a_leaf_of_its_cell,
    test_a_spacer_down_a_column_asks_for_no_width,
    test_a_spacer_between_two_dividers_is_a_gap,
    test_a_spacer_cell_is_kept_for_the_row_build,
    test_a_spacer_cell_does_not_close_its_section,
    test_a_leading_spacer_cell_is_space_before_the_cell,
    test_spacer_cells_on_both_sides_hold_the_cell,
    test_spacer_cells_at_a_rows_ends_are_the_rows,
    test_a_spacer_cell_twins_the_card_without_it,
    test_a_cards_edge_spacers_are_inside_it,
    test_a_held_block_floors_at_its_own_minimum,
    test_a_spacer_at_a_cells_inner_edge_is_a_gap,
    test_a_spacer_at_a_rows_outer_edge_is_the_rows,
    test_a_weighted_rows_spacers_are_its_gaps,
    test_a_flowing_rows_gap_is_laid_between_its_cells,
    test_a_weighted_rows_gap_is_a_cell_of_no_weight,
    test_a_weighted_row_wraps_before_its_gap_gives_way,
    test_a_weighted_rows_spacer_gives_way_before_a_cell_is_narrowed,
    test_a_held_cell_keeps_its_spacers,
    test_a_cut_rows_gaps_stand_between_what_stands_apart,
    test_a_spacer_that_binds_back_stacks_under_the_cell_before_it,
    test_a_row_of_spacers_alone_keeps_them,
    test_a_row_short_of_ratios_keeps_every_cell,
    test_spacers_beside_a_cards_only_line_are_above_and_below_it,
    test_spacers_beside_a_cards_only_column_row_are_above_and_below_it,
    test_a_spacer_cell_beside_a_list_item_is_outside_its_box,
    test_a_spacer_cell_beside_a_split_list_item_is_outside_its_box,
    test_a_spacer_cell_holds_the_item_beside_it,
    test_spacer_cells_run_as_the_leaf_cells_they_stand_for,
    test_a_spacer_inside_a_list_items_line_is_inside_its_box,
]

if __name__ == "__main__":
    print("Spacer Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓  {test.__name__}")
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
