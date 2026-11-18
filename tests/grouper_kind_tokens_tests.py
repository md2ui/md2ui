"""Unit tests for the kind tokens (grouper_kinds.kind_signatures).

Two cards are the same KIND only when they were built the same way and draw the
same elements: a heading section, a glued card, a ``:::`` row and a source line
are different origins; an image's size params and a link's drawn shape (a
button against a Text link) make the cards that hold them different kinds. What
is styling stays out (ADR-201): a checked and an unchecked task are one kind, so
a checklist runs as one list. A glued block of two text lines is a PAIR, its own
kind: a weekday over its date never twins with a three-line agenda beside it,
while two pairs still run together.

How many chips a card carries is a fact about that card, not its kind: a line
of nothing but chips reads as one "chips" line to the tolerance whatever its
count, so one chip runs with two and a card with none still joins on the one
edit. Icon rows are not chips and keep their own kind.

An element's own tokens reach only its PARENT's kind: the element's own kind,
which its sibling elements run on, is unchanged, so a line of mixed buttons and
Text links still flows as one row.

Run with: uv run tests/grouper_kind_tokens_tests.py
"""

from markdown_datapoint_split_tests import _processed_with_criteria

from md2ui.pipeline.grouper_kinds import _tree_similar, kind_type
from md2ui.pipeline.markdown_grouper import MarkdownGroupNode, NodeType


def _image(url_params: str, name: str) -> str:
    return f"![{name}](https://example.com/{name}.jpg?{url_params})"


def _artist_rows(heading: str, params: str, names: tuple[str, ...]) -> str:
    """A section of ``:::`` rows, picture beside name, closed by ``;;;``."""
    rows = "".join(
        f"{_image(params, n.replace(' ', '-'))}\n:::\n**{n}**\n;;;\n" for n in names
    )
    return f"## {heading}\n;;;\n{rows}\n"


def _column_rows(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    out = [node] if node.column_row_group else []
    for c in node.children:
        out += _column_rows(c)
    return out


def _first(node: MarkdownGroupNode, type_: str) -> list[MarkdownGroupNode]:
    out = [node] if node.type == type_ else []
    for c in node.children:
        out += _first(c, type_)
    return out


_SMALL = "md2ui.max_width=48&md2ui.aspect_ratio=1:1"
_LARGE = "md2ui.max_width=80&md2ui.aspect_ratio=1:1"


def test_image_size_params_separate_two_row_kinds():
    ast = _processed_with_criteria(
        _artist_rows("Weeknd", _SMALL, ("The Weeknd", "Weeknd Two"))
        + _artist_rows("Artists", _LARGE, ("Bad Bunny", "Taylor Swift"))
    )
    a, b, c, d = _column_rows(ast)
    assert a.kind_hash == b.kind_hash and a.run_key == b.run_key is not None
    assert c.kind_hash == d.kind_hash and c.run_key == d.run_key is not None
    assert a.kind_hash != c.kind_hash, (
        "rows of 48px pictures and rows of 80px pictures must not share a kind"
    )


def test_same_image_params_share_a_kind():
    ast = _processed_with_criteria(
        _artist_rows("Weeknd", _SMALL, ("The Weeknd", "Weeknd Two"))
        + _artist_rows("Again", _SMALL, ("Bad Bunny", "Taylor Swift"))
    )
    rows = _column_rows(ast)
    assert len({r.kind_hash for r in rows}) == 1


def test_image_param_order_does_not_matter():
    flipped = "md2ui.aspect_ratio=1:1&md2ui.max_width=48"
    ast = _processed_with_criteria(
        _artist_rows("Weeknd", _SMALL, ("The Weeknd", "Weeknd Two"))
        + _artist_rows("Flipped", flipped, ("Bad Bunny", "Taylor Swift"))
    )
    rows = _column_rows(ast)
    assert len({r.kind_hash for r in rows}) == 1, "the params are compared by name"


def test_image_shape_separates_two_row_kinds():
    circle = _SMALL + "&md2ui.shape=circle"
    ast = _processed_with_criteria(
        _artist_rows("Square", _SMALL, ("The Weeknd", "Weeknd Two"))
        + _artist_rows("Round", circle, ("Bad Bunny", "Taylor Swift"))
    )
    a, _, c, _ = _column_rows(ast)
    assert a.kind_hash != c.kind_hash, "a circle crop is a different picture"


def test_image_height_separates_two_row_kinds():
    short = "md2ui.max_height=36&md2ui.aspect_ratio=1:1"
    tall = "md2ui.max_height=64&md2ui.aspect_ratio=1:1"
    ast = _processed_with_criteria(
        _artist_rows("Short", short, ("The Weeknd", "Weeknd Two"))
        + _artist_rows("Tall", tall, ("Bad Bunny", "Taylor Swift"))
    )
    a, _, c, _ = _column_rows(ast)
    assert a.kind_hash != c.kind_hash, "36px and 64px tall pictures differ in size"


def test_checklist_with_a_done_item_is_one_run():
    ast = _processed_with_criteria(
        "## Tasks\n\n- [x] Draft the report\n- [ ] Review the numbers\n"
        "- [ ] Send it to finance\n"
    )
    items = _first(ast, NodeType.TASK_DONE) + _first(ast, NodeType.TASK_OPEN)
    assert len(items) == 3
    assert len({i.kind_hash for i in items}) == 1, "checked is a state, not a kind"
    assert items[0].run_key is not None
    assert len({i.run_key for i in items}) == 1, "the checklist runs as one"


def test_text_link_card_is_not_a_button_card():
    ast = _processed_with_criteria(
        "### One\nShort note\n[Open](/a)\n\n"
        "### Two\nShort note\n**[Open](/b)**\n\n"
        "### Three\nShort note\n[`Open`](/c)\n"
    )
    one, two, three = ast.children
    assert one.kind_hash == two.kind_hash, "two button variants are one shape"
    assert one.kind_hash != three.kind_hash, "a Text link draws no button"


def test_one_line_of_mixed_links_stays_one_run():
    ast = _processed_with_criteria(
        "[Send](#send) *[Preview](#preview)* **[Save](#save)** [`History`](#history)\n"
    )
    links = _first(ast, NodeType.LINK)
    assert len(links) == 4
    assert links[0].run_key is not None
    assert len({link.run_key for link in links}) == 1, (
        "a link's shape reaches its card's kind, never its siblings' run"
    )


def test_a_flowing_row_is_its_line_and_a_weighted_row_is_not():
    flowing = _column_rows(_processed_with_criteria("Alpha beta\n:::\nGamma delta\n"))[
        0
    ]
    piped = _processed_with_criteria("Alpha beta | Gamma delta\n")
    line = next(n for n in _walk(piped) if n.line_split_group)
    assert flowing.kind_hash == line.kind_hash, "two spellings of one arrangement"
    weighted = _column_rows(
        _processed_with_criteria("Alpha beta\n:::1\nGamma delta\n:::2\n")
    )[0]
    assert weighted.kind_hash != flowing.kind_hash, "proportions are not a line"


_DATE_AND_AGENDA = (
    "## \n\n_FRI_\n___20___\n\n"
    "4:00 PM ... Finish packing\n6:00 PM ... Drop off keys\n"
    "6:30 PM ... Leave for airport\n"
)


def _glued(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    return [n for n in _walk(node) if n.glued_content_group]


def test_a_two_line_block_is_a_pair():
    date, agenda = _glued(_processed_with_criteria(_DATE_AND_AGENDA))
    assert kind_type(date) == "pair", "two glued text lines are a pair"
    assert kind_type(agenda) == NodeType.GROUP, "three lines are a plain block"


def test_a_pair_never_twins_with_a_three_line_block():
    date, agenda = _glued(_processed_with_criteria(_DATE_AND_AGENDA))
    assert date.kind_hash != agenda.kind_hash, "2 lines must not fold into 3"
    assert date.run_key is None and agenda.run_key is None, "no grid of twins"
    assert not _tree_similar(date, agenda), "the tolerance must not re-merge them"


def test_two_pairs_twin():
    ast = _processed_with_criteria("## \n\nAccuracy\n**94%**\n\nRecall\n**81%**\n")
    a, b = _glued(ast)
    assert kind_type(a) == kind_type(b) == "pair"
    assert a.kind_hash == b.kind_hash
    assert a.run_key is not None and a.run_key == b.run_key, "twin tiles still grid"


_METRIC_TILES = (
    "## \n\n"
    "... _Revenue_ ...\n... ___$129K___ ...\n\n"
    "... _Wealth Management_ ...\n... ___$412M___ ...\n\n"
    "... _Available balance_ ...\n... ___1,204___ - tems ...\n"
)


def test_a_split_value_line_is_one_line_of_a_pair():
    tiles = _glued(_processed_with_criteria(_METRIC_TILES))
    assert len(tiles) == 3, [t.content for t in tiles]
    assert [kind_type(t) for t in tiles] == ["pair"] * 3, "one source line, one line"
    keys = {t.run_key for t in tiles}
    assert len(keys) == 1 and None not in keys, "the three tiles run together"


def test_a_key_value_line_is_not_a_pair_line():
    """A pair a display reads (here a percentage bar) is not a text line, so a
    label over it is not a two-line pair."""
    ast = _processed_with_criteria(
        "## \n\nAccuracy\nScore: 94%\n\nRecall\nScore: 81%\n"
    )
    blocks = _glued(ast)
    assert blocks, "the label and its key-value line glue"
    assert all(kind_type(b) != "pair" for b in blocks), [str(b.type) for b in blocks]


def _walk(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    out = [node]
    for c in node.children:
        out += _walk(c)
    return out


_TASKS = (
    "## Tasks\n\n"
    "### Ship the release\n_Owner: Ana_\n`Open` `Urgent`\n\n"
    "### Update the docs\n_Owner: Ben_\n\n"
    "### Fix the login bug\n_Owner: Cleo_\n`Open` `Urgent` `Backend` `Blocked` `Q4`\n\n"
    "### Review the budget\n_Owner: Dev_\n`Done`\n\n"
    "### Plan the offsite\n_Owner: Eve_\n`Open` `Urgent`\n"
)


def _cards(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    """The ``###`` sections: the cards."""
    return [n for n in _walk(node) if n.heading_group and n.heading_level == 3]


def test_any_chip_count_runs_as_one():
    cards = _cards(_processed_with_criteria(_TASKS))
    assert len(cards) == 5, [c.content for c in cards]
    keys = [c.run_key for c in cards]
    assert keys[0] is not None and len(set(keys)) == 1, keys


def test_one_chip_runs_with_two():
    ast = _processed_with_criteria(
        "## Songs\n\n"
        "### Under Pressure\n_Queen, David Bowie_\n`Song` `Saved`\n\n"
        "### Bitter Sweet Symphony\n_The Verve_\n`Song` `Saved`\n\n"
        "### Just A Girl\n_No Doubt_\n`Song`\n"
    )
    cards = _cards(ast)
    assert len(cards) == 3
    assert cards[0].run_key is not None
    assert len({c.run_key for c in cards}) == 1, "one chip is still chips"


def test_one_icon_is_not_an_icon_row():
    ast = _processed_with_criteria(
        "## Picks\n\n"
        "### Alpha\n_Owner: Ana_\n⭐ 🚀\n\n"
        "### Beta\n_Owner: Ben_\n⭐ 🚀\n\n"
        "### Gamma\n_Owner: Cleo_\n⭐\n"
    )
    a, b, c = _cards(ast)
    assert a.run_key is not None and a.run_key == b.run_key
    assert c.run_key != a.run_key, "icon rows are not chips: the count still counts"


TESTS = [
    test_image_size_params_separate_two_row_kinds,
    test_same_image_params_share_a_kind,
    test_image_param_order_does_not_matter,
    test_image_shape_separates_two_row_kinds,
    test_image_height_separates_two_row_kinds,
    test_checklist_with_a_done_item_is_one_run,
    test_text_link_card_is_not_a_button_card,
    test_one_line_of_mixed_links_stays_one_run,
    test_a_flowing_row_is_its_line_and_a_weighted_row_is_not,
    test_a_two_line_block_is_a_pair,
    test_a_pair_never_twins_with_a_three_line_block,
    test_two_pairs_twin,
    test_a_split_value_line_is_one_line_of_a_pair,
    test_a_key_value_line_is_not_a_pair_line,
    test_any_chip_count_runs_as_one,
    test_one_chip_runs_with_two,
    test_one_icon_is_not_an_icon_row,
]

if __name__ == "__main__":
    print("Kind Token Tests")
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
