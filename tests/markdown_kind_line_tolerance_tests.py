"""
Unit tests for the same-line normalization inside the same-kind tolerance
(``_line_kind_hash`` / ``_is_one_source_line_text`` in grouper_kinds.py).

One card writing its detail line as ``13:00-14:00 - Now`` while its siblings
write ``16:00-17:00`` turns a leaf into a container, which the tree-edit
tolerance can only pay for as delete+insert (2 edits, over budget) — so a
single same-line split would break a whole card run. The normalization makes
a same-line group of TEXT pieces — including the decoration that styling adds,
i.e. emphasis, inline code and emoji — compare as the one line it was written
as, while a line carrying a real element (link, image) stays distinct (one link
with chips or icons beside it keeps the link's kind instead), and a line of
nothing but decoration stays an icon row. It reads any node that IS one source
line, not just a GROUP wrapper: a heading that split inline is still the
same heading kind as a sibling card's unsplit one. A line of buttons reads
alike whatever its count, and a lone button costs nothing against it, so cards
that differ only by how many buttons they end in share a run.

The tolerance's edit distance (``_seq_edit_within``) is BANDED: only alignment
cells with |i - j| <= cap are computed, and lists whose lengths differ by more
than cap are rejected outright. That is exact because every insert/delete costs
at least 1 — and the last test here pins it against the full DP on thousands of
random child lists, so the argument is checked rather than trusted.
Run with: uv run tests/markdown_kind_line_tolerance_tests.py
"""

import random

from markdown_datapoint_split_tests import _processed_with_criteria

import md2ui.pipeline.grouper_kinds as kinds_module
from md2ui.pipeline.markdown_grouper import (
    ASTPatternAnalyzer,
    MarkdownGroupNode,
    NodeType,
)

_IMAGE = "![Teacher](https://images.unsplash.com/photo-1500648767791.jpg)\n"

_CARD = """{time}
### **{title}**
`{level}`

{img}**{who}**
Mentor
"""

_CARDS = [
    ("10:30-12:00", "Technical English", "Beginner", "Kristin Watson"),
    ("13:00-14:00", "English punctuation", "Advanced", "Cody Fisher"),
    ("16:00-17:00", "Technical Spanish", "Beginner", "Jacob Jones"),
]


def _schedule(
    middle_time: str | None = None,
    middle_img: str = _IMAGE,
    middle_title: str | None = None,
) -> str:
    """Three schedule cards; the middle one's time line / `###` title / image
    can each be overridden to isolate one difference."""
    cards = []
    for i, (time, title, level, who) in enumerate(_CARDS):
        mid = i == 1
        cards.append(
            _CARD.format(
                time=middle_time if mid and middle_time else time,
                title=middle_title if mid and middle_title else title,
                level=level,
                who=who,
                img=middle_img if mid else _IMAGE,
            )
        )
    return "## My schedule\n\n" + "\n".join(cards)


def _section(markdown: str) -> MarkdownGroupNode:
    """The ``## `` heading section of a processed+fingerprinted document."""
    ast = _processed_with_criteria(markdown)
    ASTPatternAnalyzer(ast).fingerprints()
    return ast.children[0]


def _run_sizes(section: MarkdownGroupNode) -> list[int]:
    return [len(members) for members in (section.repeated_children or {}).values()]


def test_unsplit_cards_run_together():
    # Baseline: with no split anywhere the three cards are exact-kind equal.
    section = _section(_schedule("13:00-14:00"))
    assert _run_sizes(section) == [3], f"Got {_run_sizes(section)}"
    print("  ✓  three unsplit cards → one run of 3")


def test_same_line_text_split_joins_the_run():
    # ' - Now' splits the middle time line into
    # group(datapoint, segment) — the same SOURCE line, so the run holds.
    section = _section(_schedule("13:00-14:00 - Now"))
    assert _run_sizes(section) == [3], f"Got {_run_sizes(section)}"
    cards = section.children[1:]
    keys = {c.run_key for c in cards}
    assert len(keys) == 1 and None not in keys, f"run_keys: {keys}"
    # The stored kind_hash is deliberately NOT normalized — only the tolerance
    # comparison is, so the split card still hashes differently.
    assert cards[0].kind_hash == cards[2].kind_hash
    assert cards[1].kind_hash != cards[0].kind_hash
    print("  ✓  '13:00-14:00 - Now' still runs with its sibling cards")


def test_styling_and_icons_keep_the_kind():
    # Styling a word — emphasis, inline code, a leading icon — decorates the
    # line without changing what kind of line it is, so the run must hold.
    for middle in (
        "13:00-14:00 - **Now**",
        "13:00-14:00 - *Now*",
        "13:00-14:00 - ~~Now~~",
        "13:00-14:00 - `Now`",
        "13:00-14:00 `Now`",
        "13:00-14:00 ⏱️ Now",
        "13:00-14:00 - ⏱️ `Now`",
    ):
        section = _section(_schedule(middle))
        assert _run_sizes(section) == [3], f"{middle!r} split: {_run_sizes(section)}"
    print("  ✓  emphasis / inline code / icons keep the three cards together")


def test_structural_line_pieces_stay_distinct():
    # A link or an image on the line is a real element, not styling: the line
    # must NOT read as a plain one and the cards must not merge. The authored
    # dash is what makes the element structural; TIME itself stays inline.
    for middle in (
        "13:00-14:00 - [Now](/now)",
        "13:00-14:00 - ![Now](https://example.com/now.png)",
    ):
        section = _section(_schedule(middle))
        assert _run_sizes(section) == [], f"{middle!r} merged: {_run_sizes(section)}"
    print("  ✓  link / image lines are not normalized")


def test_inline_split_heading_matches_unsplit_heading():
    # A heading that split inline — into segments, or into a text peel plus a
    # code pill — is still one heading line, so the cards keep running. Only a
    # GROUP wrapper reads as a plain TEXT line; a heading keeps its own kind.
    for middle_title in (
        "English punctuation | made easy",  # → heading3(segment, segment)
        "English punctuation `basics`",  # → heading3(heading3, inline_code)
    ):
        section = _section(_schedule(middle_title=middle_title))
        assert _run_sizes(section) == [3], (
            f"{middle_title!r} split the run: {_run_sizes(section)}"
        )
    print("  ✓  a heading that split inline still matches an unsplit one")


def test_heading_with_a_link_stays_distinct():
    # The piece-type guard must survive reading non-GROUP nodes: a link in the
    # heading is a real element, so that card is a different kind.
    #
    # Spelled with the ASCII `-`: the em dash is not a
    # separator (grouper_inline_marks._LINE_SEPARATORS), so the link would
    # stay inline in the heading text and the card would normalize with its
    # siblings — a fixture artefact, not the behaviour under test.
    section = _section(_schedule(middle_title="English punctuation - [enroll](/go)"))
    assert _run_sizes(section) == [], f"Got {_run_sizes(section)}"
    print("  ✓  a heading holding a link is not normalized")


def test_pure_icon_row_is_not_a_text_line():
    # A line of nothing but decoration is an icon row: it must keep its own
    # kind instead of joining the icon+label lines above it.
    section = _section(
        "## Icons\n\n⭐ Popular growth story here\n\n"
        "🚀 Faster science delivery now\n\n🎯 Sharper focus on results\n\n"
        "⭐ 🚀 ⚛️ 🍎\n"
    )
    assert _run_sizes(section) == [3], f"Got {_run_sizes(section)}"
    icon_row = section.children[-1]
    assert all(c.type == NodeType.EMOJI for c in icon_row.children), (
        f"fixture drift: {[c.type for c in icon_row.children]}"
    )
    assert icon_row.run_key is None, "an icon row must not join a text-line run"
    print("  ✓  a pure icon row keeps its own kind")


def test_missing_image_spends_the_whole_budget():
    # A missing picture is one edit (it is the card's content, not its kind),
    # so the normalized time line still costs nothing beside it; one more
    # difference — a card missing its picture AND its level chip — is over.
    section = _section(_schedule("13:00-14:00 - Now", middle_img=""))
    assert _run_sizes(section) == [3], f"Got {_run_sizes(section)}"
    no_chip = _schedule(middle_img="").replace("`Advanced`\n", "")
    assert _run_sizes(_section(no_chip)) == [], _run_sizes(_section(no_chip))
    print("  ✓  a missing picture is one edit, and only one")


def _albums(middle: str) -> str:
    """Three album cards; the middle one's
    picture line replaced by *middle* (empty: no picture at all)."""
    cards = [
        (
            "![Abbey Road](https://example.com/a.jpg?md2ui.aspect_ratio=1:1)\n",
            "Abbey Road",
            "The Beatles",
        ),
        (middle, "Blue", "Joni Mitchell"),
        (
            "![Kind of Blue](https://example.com/c.jpg?md2ui.aspect_ratio=1:1)\n",
            "Kind of Blue",
            "Miles Davis",
        ),
    ]
    body = "\n".join(f"### \n{pic}**{title}**\n{who}\n" for pic, title, who in cards)
    return "## Albums\n\n" + body


def test_card_without_its_picture_keeps_the_run():
    # The middle card has no picture. It is left with
    # two lines — a pair — and still runs with the cards that have one.
    section = _section(_albums(""))
    assert _run_sizes(section) == [3], f"Got {_run_sizes(section)}"
    print("  ✓  a card without its picture stays in its siblings' run")


def _images(node: MarkdownGroupNode) -> list[MarkdownGroupNode]:
    found = [node] if node.type == NodeType.IMAGE else []
    for c in node.children:
        found.extend(_images(c))
    return found


def test_card_without_its_picture_gets_none():
    # A picture that was not authored is never invented:
    # the card runs with its pictured siblings, and only theirs are drawn.
    cards = (
        "## Reading list\n\n"
        "### Streets\n![A street](https://example.com/s.jpg)\nBack to walkers.\n\n"
        "### Markets\n![A market](https://example.com/m.jpg)\nA short walk away.\n\n"
        "### Parking\nFree parking costs more than anyone pays for it.\n"
    )
    for doc in (_albums(""), cards):
        section = _section(doc)
        pictures = [n.content for n in _images(section)]
        assert len(pictures) == 2 and all("example.com" in p for p in pictures), (
            pictures
        )
    print("  ✓  a card without its picture gets no picture")


def test_rating_line_is_its_own_kind():
    # Like a chip line, a line of nothing but rating glyphs is its own kind:
    # five stars over a quote is not a name over its class year, so a review's
    # body never twins its pictured header.
    doc = (
        "![Sophia](https://example.com/sophia.jpg)\n**Sophia Rossi**\nClass of 2023\n\n"
        '⭐⭐⭐⭐⭐\n"This class was an absolute dream!"\n'
    )
    ast = _processed_with_criteria(doc)
    ASTPatternAnalyzer(ast).fingerprints()
    header, body = ast.children
    assert kinds_module._is_rating_line(body.children[0]), body.children[0].content
    assert not kinds_module._tree_similar(header, body, {})
    print("  ✓  a rating line keeps a review body from twinning its header")


def test_what_reads_as_a_rating_line():
    # Only rating glyphs, at least one, a half star at most; however the stars
    # were split (a `⭐️` with its selector splits into emoji pieces).
    def line(text: str) -> MarkdownGroupNode:
        ast = _processed_with_criteria(f"## R\n\n{text}\nA quote that runs on.\n")
        return ast.children[0].children[1].children[0]

    for text in ("⭐⭐⭐⭐⭐", "★★★★½", "★★★☆☆", "**★★★**", "⭐️⭐️⭐️"):
        assert kinds_module._is_rating_line(line(text)), text
    for text in ("⭐", "⭐ 4.8", "⭐⭐⭐⭐⭐ (120)", "Great ⭐⭐⭐", "🌟🌟🌟", "★½★"):
        assert not kinds_module._is_rating_line(line(text)), text
    a, b = line("⭐⭐⭐"), line("⭐️⭐️⭐️")
    assert kinds_module._line_kind_hash(a) == kinds_module._line_kind_hash(b)
    print("  ✓  rating glyphs alone, half star at most; a lone star stays an emoji")


def test_pair_still_never_twins_a_three_line_block():
    # The pair rule holds: with no picture anywhere, two glued lines and three
    # glued lines are different kinds, whatever the picture tolerance allows.
    edits = kinds_module._tree_edit_within
    doc = "## Days\n\n### \n_FRI_\n___20___\n\n### \nStandup\nReview\nRetro\n"
    a, b = _section(doc).children[1:]
    assert kinds_module.kind_type(a) == "pair", kinds_module.kind_type(a)
    assert edits(a, b, 1, {}) > 1
    print("  ✓  a pair never matches a three-line block")


def test_gallery_one_picture_short_is_another_kind():
    # A picture among pictures only is the item itself: a gallery missing one
    # is not one edit from the full one.
    pics = [
        f"![p{i}](https://example.com/{i}.jpg?md2ui.aspect_ratio={r})"
        for i, r in enumerate(("1:1", "16:9", "1:1"))
    ]
    full = MarkdownGroupNode(type=NodeType.GROUP)
    short = MarkdownGroupNode(type=NodeType.GROUP)
    full.children = [MarkdownGroupNode(content=p, type=NodeType.IMAGE) for p in pics]
    short.children = [
        MarkdownGroupNode(content=p, type=NodeType.IMAGE) for p in pics[:2]
    ]
    # The two 1:1 pictures share a kind; the 16:9 one between them does not.
    for n, kind in zip(full.children + short.children, (0, 1, 0, 0, 1)):
        n.kind_hash = kind
    full.kind_hash, short.kind_hash = 10, 11
    assert kinds_module._seq_edit_within(full.children, short.children, 1) > 1
    assert not kinds_module._tree_similar(full, short)
    print("  ✓  a gallery one picture short is a different gallery")


def test_tolerance_disabled_restores_exact_kinds():
    # EDITS=0 is the escape hatch back to exact kind_hash runs.
    original = kinds_module._KIND_TOLERANCE_EDITS
    kinds_module._KIND_TOLERANCE_EDITS = 0
    try:
        section = _section(_schedule("13:00-14:00 - Now"))
        assert _run_sizes(section) == [], f"Got {_run_sizes(section)}"
    finally:
        kinds_module._KIND_TOLERANCE_EDITS = original
    print("  ✓  _KIND_TOLERANCE_EDITS=0 → exact kind_hash behaviour")


def test_split_line_does_not_chain_into_plain_leaf_siblings():
    # Scope limit: the normalization lives in the tolerance, which the run
    # joiner only offers when BOTH sides are containers. A same-line group
    # beside plain text leaves must stay out of their run — collapsing there
    # would grid unrelated body lines together.
    section = _section(
        "## Notes\n\nPlain first line here\n\nAlpha | Beta | Gamma\n"
        "\nPlain third line here\n"
    )
    split = [c for c in section.children if c.line_split_group]
    assert len(split) == 1, f"Expected one same-line group, got {len(split)}"
    assert split[0].run_key is None, "same-line group must not join a text run"
    assert _run_sizes(section) == [], f"Got {_run_sizes(section)}"
    print("  ✓  a same-line group does not chain into plain text siblings")


# One-link-per-line footer columns (figma-landing-page): PRODUCT badges three of
# its links with a chip, the other columns do not, and the counts all differ.
_FOOTER_COLUMNS = [
    ("PRODUCT", ["Design", "Dev Mode", "Buzz` `BETA", "Sites` `BETA", "Make", "AI"]),
    ("USE CASES", ["UI design", "UX design", "Wireframing", "Diagramming"]),
    ("RESOURCES", ["Blog", "Colors", "Fonts", "Templates", "Developers"]),
    ("COMPANY", ["Events", "Careers", "Newsroom"]),
]


def _footer() -> str:
    lines = []
    for title, links in _FOOTER_COLUMNS:
        lines.append(f"###### {title}")
        for label in links:
            # "Buzz` `BETA" closes the link's code and opens a chip after it.
            name, _, chip = label.partition("` `")
            chip_md = f" `{chip}`" if chip else ""
            lines.append(f"[`{name}`](/{name.lower().replace(' ', '-')}){chip_md}")
    return "\n".join(lines) + "\n"


def test_link_columns_with_chips_match_plain_link_columns():
    # A chip beside a link badges it: PRODUCT is the same kind of column as
    # its siblings, so all four columns form one run.
    ast = _processed_with_criteria(_footer())
    ASTPatternAnalyzer(ast).fingerprints()
    columns = ast.children
    assert len(columns) == 4, f"fixture drift: {len(columns)} columns"
    assert len({c.kind_hash for c in columns}) == 1, "columns differ in kind"
    assert _run_sizes(ast) == [4], f"Got {_run_sizes(ast)}"
    print("  ✓  a link column with chips runs with plain link columns")


_LINK_CARD = "### {title}\n{line}\nA short description of it\n"


def _link_cards(middle_line: str) -> str:
    """Three cards whose second line is a bare link, the middle one's varied."""
    lines = ["[Docs](/docs)", middle_line, "[Docs](/docs)"]
    cards = [
        _LINK_CARD.format(title=title, line=line)
        for title, line in zip(("Alpha", "Beta", "Gamma"), lines)
    ]
    return "## Cards\n\n" + "\n".join(cards)


def test_decorated_link_line_matches_a_bare_link_line():
    # Chips and icons beside one link, on either side, are decoration.
    for middle in (
        "[Docs](/docs) `NEW`",
        "[Docs](/docs) 🚀",
        "🚀 [Docs](/docs)",
    ):
        section = _section(_link_cards(middle))
        line = section.children[2].children[1]
        assert line.type == NodeType.GROUP, f"fixture drift: {middle!r} → {line.type}"
        assert _run_sizes(section) == [3], f"{middle!r}: {_run_sizes(section)}"
    print("  ✓  a link with chips or icons reads as the link")


def test_decorated_link_guards_keep_their_own_kind():
    # Two links with a chip between them are a mixed line, decoration alone is
    # a pill or icon row, and an image is a layout anchor: none of them is one
    # decorated link. (Two bare links are a button line: see
    # test_button_count_never_splits_a_run.)
    for middle in (
        "[Docs](/docs) `NEW` [API](/api)",
        "`NEW` `BETA`",
        "![Docs](https://example.com/d.png) `NEW`",
    ):
        section = _section(_link_cards(middle))
        assert _run_sizes(section) == [], f"{middle!r} merged: {_run_sizes(section)}"
    print("  ✓  several links, decoration alone and images keep their own kind")


_SONG_CARD = """### {title}
_{detail}_

{last}
"""

_SAVE = "[💾 Save](agent:save)"


def _song_cards(middle_last: str, middle_extra: str = "") -> str:
    """Three song cards ending in a Save button; the middle one's last line (and
    an optional extra line before it) varied."""
    rows = [
        ("Starman", "David Bowie · 4:14", _SAVE),
        ("Under Pressure", "Queen · 4:08", middle_extra + middle_last),
        ("The Chain", "Fleetwood Mac · 4:29", _SAVE),
    ]
    cards = [_SONG_CARD.format(title=t, detail=d, last=last) for t, d, last in rows]
    return "## Songs\n\n" + "\n".join(cards)


def test_one_element_swap_keeps_the_run():
    # One card's state drawn by a chip or an icon where its siblings have a
    # button is the same card: swapping one element is one edit.
    for middle in ("`In your library`", "✅", "~~[💾 Saved](agent:save)~~"):
        section = _section(_song_cards(middle))
        assert _run_sizes(section) == [3], f"{middle!r}: {_run_sizes(section)}"
    print("  ✓  a button swapped for a chip, an icon or another button keeps the run")


def test_element_swap_spends_the_whole_budget():
    # The swap is the one edit: a card that also adds a line is a different card.
    section = _section(_song_cards("`In your library`", "Played 12 times\n\n"))
    assert _run_sizes(section) == [], f"Got {_run_sizes(section)}"
    print("  ✓  a swap plus one more difference is over budget")


def test_image_never_swaps_for_an_element():
    # An image is a layout anchor: it never stands in for a button.
    section = _section(_song_cards("![Cover](https://example.com/cover.jpg)"))
    assert _run_sizes(section) == [], f"Got {_run_sizes(section)}"
    print("  ✓  an image in a button's place keeps the cards apart")


def test_button_against_text_link_is_one_swap():
    # A Text link draws no button, so it is a different element: one edit,
    # where two button variants are the same element and cost nothing.
    edits = kinds_module._tree_edit_within
    button = _section(_song_cards("**[💾 Save](agent:save)**")).children
    text_link = _section(_song_cards("[`💾 Save`](agent:save)")).children
    assert edits(button[1], button[2], 5, {}) == 0, (
        "two button variants are one element"
    )
    assert edits(text_link[1], text_link[2], 5, {}) == 1, "a Text link is one swap away"
    print("  ✓  button variants cost nothing; a Text link costs one swap")


# Two cards alike but for how many buttons they end in.
_OFFER_AND_INVITE = """## Reduce your card payment with MSI

Pay your purchases in interest-free months.

[See MSI options](agent:open?item=msi) *[Dismiss](agent:dismiss?id=msi)*

## Invite a friend

Earn $8,888 for each friend who joins.

[Invite a friend](agent:invite)
"""


def test_button_count_never_splits_a_run():
    # How many buttons a card ends in is a fact about that card, not its kind:
    # one button runs with two, as a bare link does with
    # a row of two links.
    ast = _processed_with_criteria(_OFFER_AND_INVITE)
    ASTPatternAnalyzer(ast).fingerprints()
    assert _run_sizes(ast) == [2], f"offer + invite: {_run_sizes(ast)}"
    section = _section(_link_cards("[Docs](/docs) [API](/api)"))
    assert _run_sizes(section) == [3], f"link row: {_run_sizes(section)}"
    print("  ✓  cards differing only by their button count share a run")


def test_button_lines_read_alike_whatever_their_count():
    # Two and three buttons are one kind of line, and a lone button of any
    # variant costs nothing against either: the line is variant-free, as a
    # pill run is.
    two = _section(_song_cards("[▶ Play](agent:play) *[💾 Save](agent:save)*"))
    three = _section(
        _song_cards(
            "[▶ Play](agent:play) *[💾 Save](agent:save)* **[Share](agent:share)**"
        )
    )
    lone = _section(_song_cards("**[💾 Save](agent:save)**"))
    two_line = two.children[2].children[-1]
    three_line = three.children[2].children[-1]
    lone_link = lone.children[2].children[-1]
    for line in (two_line, three_line):
        assert line.line_split_group, f"fixture drift: {line.type}"
    assert lone_link.type == NodeType.LINK, f"fixture drift: {lone_link.type}"
    line_kind = kinds_module._line_kind_hash
    assert line_kind(two_line) == line_kind(three_line), "2 and 3 buttons differ"
    edits = kinds_module._tree_edit_within
    for line in (two_line, three_line):
        assert edits(lone_link, line, 5, {}) == 0, "a lone button against a line"
        assert edits(line, lone_link, 5, {}) == 0, "a line against a lone button"
    print("  ✓  a button line reads alike at any count, and a lone button with it")


_PILL_AND_BUTTON_LINES = """## Buttons

[Primary](/link) [❤️ Primary](/link) [❤️](/link)

**[Secondary](/link)** **[❤️ Secondary](/link)** **[❤️](/link)**

[`Pill`](/link) [`❤️ Pill`](/link) [`❤️`](/link)
"""


def test_text_link_line_runs_with_button_lines():
    # A line of Text links (`` [`Pill`](/x) ``) is a button line too: only the
    # "buttons" kind makes it
    # read as one with a line of plain buttons, whose link children hash apart
    # from its own, so the three lines are one run. At 1280 that run is what
    # sizes the card beside it (`tests-datapoint-layout-overrding`).
    section = _section(_PILL_AND_BUTTON_LINES)
    lines = [c for c in section.children if c.line_split_group]
    assert len(lines) == 3, f"fixture drift: {[c.type for c in section.children]}"
    line_kind = kinds_module._line_kind_hash
    assert line_kind(lines[2]) == line_kind(lines[0]), "a pill line is a button line"
    assert _run_sizes(section) == [3], f"Got {_run_sizes(section)}"
    print("  ✓  a line of Text links runs with lines of plain buttons")


# Two stay cards as `catalogs/airbnb` writes them: the save link sits in the
# picture's overlay beside a chip on one line, or above the chip on its own.
_OVERLAY_CARDS = """## Stays

###
![
`Guest favourite` ... _[🤍](agent:save?id=1)_
+++++
](https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800)
**Flat in the centre**
_6–8 Nov_

###
![
... _[🤍](agent:save?id=4)_
`Guest favourite`
+++++
](https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=800)
**Condo in Zazil Ha**
_23–25 Oct_
"""


def test_lone_link_keeps_its_kind_beside_a_chip():
    # A lone link is count-free only against a button line: against a chip
    # badging a link it is still that link, so the two overlays differ by the
    # chip's place alone, one edit, and the cards keep their run.
    section = _section(_OVERLAY_CARDS)
    a, b = section.children[1], section.children[2]
    assert kinds_module._tree_edit_within(a, b, 5, {}) == 1
    assert _run_sizes(section) == [2], f"Got {_run_sizes(section)}"
    print("  ✓  an overlay's lone link still matches a chip-badged link line")


def _offers(second: str) -> MarkdownGroupNode:
    """A processed document of two ``##`` cards: an offer ending in two
    buttons, then *second*'s card."""
    ast = _processed_with_criteria(
        "## Offer\n\nA short description of it.\n\n"
        "[Open](agent:open) *[Dismiss](agent:dismiss)*\n\n" + second
    )
    ASTPatternAnalyzer(ast).fingerprints()
    return ast


def test_missing_button_line_still_costs_an_edit():
    # The count is free; the line is not: a card with no buttons against one
    # ending in two pays its insert, and one more difference is over budget.
    plain = _offers("## Notice\n\nA short description of it.\n")
    a, b = plain.children
    assert len(a.children) == len(b.children) + 1, "fixture drift"
    assert kinds_module._tree_edit_within(a, b, 5, {}) == 1
    longer = _offers("## Notice\n\nA short description of it.\n\nAnd a footnote.\n")
    assert _run_sizes(longer) == [], f"Got {_run_sizes(longer)}"
    print("  ✓  a card without its button line still pays one edit")


# Four composed pairs,
# the last one's value split in two, with a spring row before or after them.
_PAIRS = """_RealFeel_ : 19°

_Wind_ : NNE 6 km/h

_Humidity_ : 49%

_UV_ : 1.4 low
"""
_SPRING = "Mostly cloudy ... Air quality poor\n"


def test_a_row_never_joins_a_run_of_column_lines():
    # A one-line colon column stacks label over value; a spring or split line
    # is a row, not a plain text line, so the row stays out of the pairs' run.
    for doc in (f"## Tokyo\n\n{_SPRING}\n{_PAIRS}", f"## Tokyo\n\n{_PAIRS}\n{_SPRING}"):
        section = _section(doc)
        assert _run_sizes(section) == [4], f"{_run_sizes(section)} in {doc!r}"
    print("  ✓  a spring row before or after four pairs stays out of their run")


def _random_children(rng: random.Random, depth: int) -> list[MarkdownGroupNode]:
    """0-6 random siblings: leaves of three types (IMAGE, whose insert/delete is
    forbidden among pictures only, included) and, above depth 0, nested groups. Kinds are drawn from
    a tiny range so equal-kind substitutions are common."""
    kids: list[MarkdownGroupNode] = []
    for _ in range(rng.randint(0, 6)):
        if depth > 0 and rng.random() < 0.3:
            node = MarkdownGroupNode(type=NodeType.GROUP)
            node.children = _random_children(rng, depth - 1)
        else:
            leaf_type = rng.choice([NodeType.TEXT, NodeType.SEGMENT, NodeType.IMAGE])
            node = MarkdownGroupNode(content="x", type=leaf_type)
        node.kind_hash = rng.randint(0, 3)
        kids.append(node)
    return kids


def _full_dp(A: list[MarkdownGroupNode], B: list[MarkdownGroupNode], cap: int) -> int:
    """The full DP, cell for cell: the reference the band must match."""
    m, n = len(A), len(B)
    over = cap + 1
    a_mixed = kinds_module._beside_content(A)
    b_mixed = kinds_module._beside_content(B)
    prev = [0] * (n + 1)
    for j in range(1, n + 1):
        prev[j] = min(
            over, prev[j - 1] + kinds_module._indel_cost(B[j - 1], cap, b_mixed)
        )
    for i in range(1, m + 1):
        cur = [min(over, prev[0] + kinds_module._indel_cost(A[i - 1], cap, a_mixed))]
        for j in range(1, n + 1):
            sub = prev[j - 1] + kinds_module._tree_edit_within(A[i - 1], B[j - 1], cap)
            dele = prev[j] + kinds_module._indel_cost(A[i - 1], cap, a_mixed)
            ins = cur[j - 1] + kinds_module._indel_cost(B[j - 1], cap, b_mixed)
            cur.append(min(over, sub, dele, ins))
        prev = cur
    return prev[n]


def test_banded_edit_distance_matches_the_full_dp():
    rng = random.Random(20260911)
    checked = 0
    for _ in range(3000):
        a, b = _random_children(rng, 2), _random_children(rng, 2)
        for cap in (0, 1, 2):
            got = kinds_module._seq_edit_within(a, b, cap)
            want = _full_dp(a, b, cap)
            assert got == want, f"cap={cap}: banded {got} != full {want}"
            checked += 1
    print(f"  ✓  banded edit distance equals the full DP on {checked} random pairs")


TESTS = [
    test_unsplit_cards_run_together,
    test_same_line_text_split_joins_the_run,
    test_styling_and_icons_keep_the_kind,
    test_structural_line_pieces_stay_distinct,
    test_inline_split_heading_matches_unsplit_heading,
    test_heading_with_a_link_stays_distinct,
    test_pure_icon_row_is_not_a_text_line,
    test_missing_image_spends_the_whole_budget,
    test_card_without_its_picture_keeps_the_run,
    test_card_without_its_picture_gets_none,
    test_rating_line_is_its_own_kind,
    test_what_reads_as_a_rating_line,
    test_pair_still_never_twins_a_three_line_block,
    test_gallery_one_picture_short_is_another_kind,
    test_tolerance_disabled_restores_exact_kinds,
    test_split_line_does_not_chain_into_plain_leaf_siblings,
    test_link_columns_with_chips_match_plain_link_columns,
    test_decorated_link_line_matches_a_bare_link_line,
    test_decorated_link_guards_keep_their_own_kind,
    test_one_element_swap_keeps_the_run,
    test_element_swap_spends_the_whole_budget,
    test_image_never_swaps_for_an_element,
    test_button_against_text_link_is_one_swap,
    test_button_count_never_splits_a_run,
    test_button_lines_read_alike_whatever_their_count,
    test_text_link_line_runs_with_button_lines,
    test_lone_link_keeps_its_kind_beside_a_chip,
    test_missing_button_line_still_costs_an_edit,
    test_a_row_never_joins_a_run_of_column_lines,
    test_banded_edit_distance_matches_the_full_dp,
]

if __name__ == "__main__":
    print("Same-Line Kind Tolerance Tests")
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
