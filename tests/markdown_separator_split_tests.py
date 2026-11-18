"""
Unit tests for grouper_separator_splits._split_separators.

Covers the line separators (` | `, ` - `), pins commas as punctuation, and pins
the dots (•, ·, ∙, ‧) as text per ADR-205.
Every separator is CONSUMED — whether it is drawn back is a theme decision
(## Separators), fed by `separator_chars`.

Run with: uv run tests/markdown_separator_split_tests.py
"""

import sys
from unittest.mock import patch

sys.path.insert(0, "tests")

from markdown_datapoint_split_tests import (
    _processed_with_criteria,
    assert_reads_as_escaped_twin,
)

from md2ui.pipeline.grouper_split_criteria import SplitCriteria
from md2ui.pipeline.data_point_types import DataPointType
from md2ui.pipeline.markdown_grouper import NodeType
from md2ui.pipeline.grouper_inline_marks import _balance_markdown_markers
from md2ui.pipeline.grouper_separator_splits import (
    _split_colon_columns,
    _split_separators,
)
from md2ui.pipeline.grouper_node_reads import _plain_colon_kv


def _split(content: str, protected=None):
    return _split_separators(content, protected or [])


def _tree(text: str):
    """(type, content, column_split_group) nested tuples for a processed line."""

    def walk(n):
        return (
            n.type,
            n.content,
            n.column_split_group,
            [walk(c) for c in n.children],
        )

    return walk(_processed_with_criteria(text))


def _leaf_contents(text: str) -> list[str]:
    out: list[str] = []

    def walk(n):
        if not n.children:
            out.append(n.content)
        for c in n.children:
            walk(c)

    walk(_processed_with_criteria(text))
    return out


def _find(node, type_):
    """First node of *type_* in a _tree() result, depth-first."""
    if node[0] == type_:
        return node
    for k in node[3]:
        hit = _find(k, type_)
        if hit is not None:
            return hit
    return None


# ---------------------------------------------------------------------------
# A dot is text (ADR-205)
#
# `•` `·` `∙` `‧` are text: a line of
# them stays whole and draws them as written, and the pieces a ` | ` or ` - `
# makes keep their dots. The separators are the ASCII ` | ` and ` - `.
# ---------------------------------------------------------------------------


def test_a_dot_never_splits():
    for dot in "•·∙‧":
        assert _split(f"Apples {dot} Pears {dot} Plums") is None, dot
        assert _split(f"{dot} Apples {dot} Pears") is None, dot
        assert _split(f"**A** {dot} **B** {dot} **C**") is None, dot
    print("  ✓  a dot never splits a line, alone or wrapped")


def test_a_dot_stays_in_the_piece_a_separator_makes():
    assert _split("A • B | C") == [
        (NodeType.SEGMENT, "A • B"),
        (NodeType.SEGMENT, "C"),
    ], _split("A • B | C")
    assert _split("A · B - C") == [
        (NodeType.SEGMENT, "A · B"),
        (NodeType.SEGMENT, "C"),
    ], _split("A · B - C")
    assert _split("A • B | C - D") == [
        (NodeType.SEGMENT, "A • B"),
        (NodeType.SEGMENT, "C"),
        (NodeType.SEGMENT, "D"),
    ], _split("A • B | C - D")
    print("  ✓  a dot stays inside the piece a ` | ` or ` - ` makes")


def test_pipe_only_unchanged():
    result = _split("A | B | C")
    assert result == [
        (NodeType.SEGMENT, "A"),
        (NodeType.SEGMENT, "B"),
        (NodeType.SEGMENT, "C"),
    ], f"Expected 3 SEGMENT siblings, got {result!r}"
    print("  ✓  pipe: 'A | B | C' → 3 SEGMENT siblings (unchanged)")


def test_em_dash_only_unchanged():
    # An em dash is NOT a separator. It cannot be escaped — CommonMark only
    # escapes ASCII punctuation, so `\—` renders a literal backslash — which
    # would leave an author no way to decline the cut. Most spaced em/en dashes
    # sit inside prose sentences.
    assert _split("A — B — C") is None, "an em dash must not split"
    assert _split("A – B – C") is None, "nor an en dash"
    assert _split("A - B - C") == [
        (NodeType.SEGMENT, "A"),
        (NodeType.SEGMENT, "B"),
        (NodeType.SEGMENT, "C"),
    ], "the ASCII hyphen is the spelling that separates"
    print("  ✓  em/en dashes do not separate; the ASCII `-` does")


def test_comma_never_splits():
    assert _split("A, B, C") is None
    assert _contents("A, B, C") == ["A, B, C"]
    print("  ✓  comma: 'A, B, C' stays one line")


def test_no_separator_returns_none():
    result = _split("Just plain prose")
    assert result is None, f"Expected None, got {result!r}"
    print("  ✓  no separator: plain text → None")


def _grouped_leaves(doc: str) -> list[str]:
    """Leaf contents the real pipeline makes of *doc*."""
    from md2ui import session

    root = session.group_markdown(doc, session.load_grouping_kit())
    assert root is not None
    out: list[str] = []

    def walk(n):
        if not n.children:
            out.append(n.content)
        for c in n.children:
            walk(c)

    walk(root)
    return out


def test_a_dot_line_is_one_text():
    # Through the real pipeline: the line is one text and draws its dots. A
    # dot is no Markdown escape, so a backslash before one stays, as it does
    # in any Markdown renderer.
    for dot in "•·∙‧":
        leaves = _grouped_leaves(f"Alpha beta {dot} Gamma delta\n")
        assert leaves == [f"Alpha beta {dot} Gamma delta"], (dot, leaves)
        leaves = _grouped_leaves(f"Alpha beta \\{dot} Gamma delta\n")
        assert leaves == [f"Alpha beta \\{dot} Gamma delta"], (dot, leaves)
    leaves = _grouped_leaves("**Concha y Toro · Vino tinto**\n")
    assert leaves == ["**Concha y Toro · Vino tinto**"], leaves
    print("  ✓  a dot line is one text; a backslash before a dot stays")


# ---------------------------------------------------------------------------
# Colon column split — the vertical counterpart of | and -
# ---------------------------------------------------------------------------


def test_colon_columns_split_on_spaced_colon():
    assert _split_colon_columns("A : B", []) == [
        (NodeType.SEGMENT, "A"),
        (NodeType.SEGMENT, "B"),
    ]
    assert _split_colon_columns("A : B : C", []) == [
        (NodeType.SEGMENT, "A"),
        (NodeType.SEGMENT, "B"),
        (NodeType.SEGMENT, "C"),
    ]
    print("  ✓  _split_colon_columns: 'A : B' → two stacked segments")


def test_colon_columns_need_a_space_on_both_sides():
    # A key-value colon is tight to its key, which is exactly what must NOT
    # split here; the lopsided spellings are neither.
    for src in ("Key: value", "Key:value", "Key :value", "A:B"):
        assert _split_colon_columns(src, []) is None, src
    print("  ✓  _split_colon_columns: needs a space on BOTH sides")


def test_colon_columns_protected_range():
    # The colon inside a time datapoint is untouchable (it also has no spaces).
    assert _split_colon_columns("8 : 00 AM", [(0, 9)]) is None
    print("  ✓  _split_colon_columns: a protected colon never splits")


def test_colon_columns_rule_piece():
    # `---` is a rule; `___` next to it would be a content break — the test runs BEFORE
    # _balance_markdown_markers, which would otherwise "repair" it to `_____`.
    assert _split_colon_columns("B : --- : C", []) == [
        (NodeType.SEGMENT, "B"),
        (NodeType.HORIZONTAL_RULE, "---"),
        (NodeType.SEGMENT, "C"),
    ]
    print("  ✓  _split_colon_columns: a lone `---` piece becomes a rule")


def test_colon_columns_single_piece_is_none():
    for src in (": B", "A :", "A B"):
        assert _split_colon_columns(src, []) is None, src
    print("  ✓  _split_colon_columns: fewer than two pieces → None")


def test_plain_colon_kv_rejects_a_spaced_colon():
    # The one-line change that frees the token for the column split.
    assert _plain_colon_kv("Key: value") == [
        (NodeType.KEY, "Key"),
        (NodeType.VALUE, "value"),
    ]
    assert _plain_colon_kv("Key : value") is None
    print("  ✓  _plain_colon_kv: a colon with a space before it is not a key")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Whole-line wrap propagation
#
# A line wrapped in ONE span hands that span to every segment it splits into.
# A line that merely BEGINS and ENDS with a marker, like `_A_ - _B_`, is not
# one wrap: _detect_style_wrap applies the same-span rule.
# ---------------------------------------------------------------------------


def test_bold_italic_wrap_reaches_every_segment():
    """`***` must not be read as `**` plus a stray `*`."""
    assert _split("***A | B | C***") == [
        (NodeType.SEGMENT, "***A***"),
        (NodeType.SEGMENT, "***B***"),
        (NodeType.SEGMENT, "***C***"),
    ], _split("***A | B | C***")
    print("  ✓  a *** wrap reaches every segment")


def test_strike_wrap_reaches_the_middle_segment_too():
    """`~~` propagates like the other wrap markers, not only to the first and
    last segment through balancing."""
    assert _split("~~A | B | C~~") == [
        (NodeType.SEGMENT, "~~A~~"),
        (NodeType.SEGMENT, "~~B~~"),
        (NodeType.SEGMENT, "~~C~~"),
    ], _split("~~A | B | C~~")
    print("  ✓  a ~~ wrap reaches the middle segment too")


def test_code_wrap_propagates_backticks():
    assert _split("`a | b`") == [
        (NodeType.SEGMENT, "`a`"),
        (NodeType.SEGMENT, "`b`"),
    ], _split("`a | b`")
    print("  ✓  a ` wrap propagates backticks")


def test_a_sequence_of_spans_is_not_a_wrap():
    """Segment 2 must not come back as `` _`x` : _vs last month__ ``."""
    assert _split("___1,293___ - `x` : _vs last month_") == [
        (NodeType.SEGMENT, "___1,293___"),
        (NodeType.SEGMENT, "`x` : _vs last month_"),
    ], _split("___1,293___ - `x` : _vs last month_")
    assert _split("*A* | **B** | ***C***") == [
        (NodeType.SEGMENT, "*A*"),
        (NodeType.SEGMENT, "**B**"),
        (NodeType.SEGMENT, "***C***"),
    ], _split("*A* | **B** | ***C***")
    print("  ✓  a sequence of spans is not a wrap")


def test_lone_tilde_is_not_a_wrap():
    """`~` is "approximately", so `~A | B~` carries no strike."""
    assert _split("~A | B~") == [
        (NodeType.SEGMENT, "~A"),
        (NodeType.SEGMENT, "B~"),
    ], _split("~A | B~")
    print("  ✓  a lone tilde is not a wrap")


# ---------------------------------------------------------------------------
# Colon columns beside a tight colon
#
# A spaced ` : ` stacks wherever it is; a tight `Key:` beside it is text
# (ADR-205) and stays in the piece it was written in.
# ---------------------------------------------------------------------------


def test_a_tight_colon_line_stacks_at_its_spaced_colon():
    """`K: A : B` — the spaced colon is the only structure the line has."""
    col = _find(_tree("K: A : B"), NodeType.GROUP)
    assert col is not None and col[2] is True, _tree("K: A : B")
    assert [k[1] for k in col[3]] == ["K: A", "B"], col
    assert_reads_as_escaped_twin("K: A : B")
    print("  ✓  a tight-colon line stacks at its spaced colon")


def test_a_separator_segment_stacks_at_its_colon():
    """`K: 1,293 - \\`x\\` : vs last month` — the separator splits the line, then
    the spaced colon binds tighter inside the second segment."""
    contents = _leaf_contents("K: 1,293 - `x` : vs last month")
    assert contents == ["K: 1,293", "x", "vs last month"], contents
    print("  ✓  a separator segment stacks at its colon")


def test_kv_value_colon_leaves_no_literal_colon():
    """`K: 92 : days - ⬇` emits no `': days'` leaf."""
    contents = _leaf_contents("K: 92 : days - ⬇")
    assert "days" in contents, contents
    assert not any(c.strip().startswith(":") for c in contents), contents
    print("  ✓  a KV value colon leaves no literal colon behind")


def test_a_tight_colon_is_text_and_a_spaced_one_is_columns():
    """ADR-205: tight to the key = text as written, spaced = columns."""
    assert _leaf_contents("Key: value") == ["Key: value"]
    assert _find(_tree("Key: value"), NodeType.KEY_VALUE) is None
    spaced = _tree("Key : value")
    assert _find(spaced, NodeType.KEY_VALUE) is None, spaced
    assert _leaf_contents("Key : value") == ["Key", "value"]
    print("  ✓  a tight colon is text, a spaced colon is still columns")


# ---------------------------------------------------------------------------
# A marker INSIDE a code span is that chip's text, not emphasis to balance
# ---------------------------------------------------------------------------


def _leaf_types(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def walk(n):
        if not n.children:
            out.append((n.type, n.content))
        for c in n.children:
            walk(c)

    walk(_processed_with_criteria(text))
    return out


def test_a_star_inside_a_code_span_keeps_its_chip():
    """The asterisk belongs to the chip's TEXT. Counted as emphasis it would be
    unpaired, the flanking rule would prepend an opener, and the piece would
    stay text and draw its backticks."""
    assert _leaf_types("`* New`") == [(NodeType.INLINE_CODE, "* New")]


def test_the_chip_survives_every_split_that_reaches_it():
    """Behind the separator and behind the spring alike: both hand their piece
    to the same balancer."""
    for src in (
        "**Home in Raito** - `* New`",
        "**Home in Raito** ... `* New`",
        "**Home in Raito** | `* New`",
    ):
        assert (NodeType.INLINE_CODE, "* New") in _leaf_types(src), src


def test_balancing_inside_a_complete_span_is_left_alone():
    for span in ("`* New`", "`A * B`", "`**x**`", "`***`", "`_y_`"):
        assert _balance_markdown_markers(span) == span, span


def test_a_span_cut_in_half_is_still_repaired():
    """The exemption is for COMPLETE spans only — repairing a piece a split cut
    out of one is the balancer's actual job and must not regress."""
    for cut, repaired in (
        ("`A", "`A`"),
        ("C`", "`C`"),
        ("`**A bold code**", "`**A bold code**`"),
        ("B code`", "`B code`"),
    ):
        assert _balance_markdown_markers(cut) == repaired, cut


def test_asterisk_balancing_without_a_span_is_untouched():
    """The whole point of scoping the exemption to code spans: ordinary marker
    repair, including the tier and flanking rules, is unaffected."""
    for src, want in (
        ("**Bold**", "**Bold**"),
        ("*italic", "*italic*"),
        ("ppm (2024)**", "**ppm (2024)**"),
        ("__x_", "__x__"),  # the opener wins; no Display tier invented
        ("** Crossed on", "Crossed on"),  # whitespace-flanked run is dead text
        ("**~420 ppm**", "**~420 ppm**"),
        ("a*b*c", "a*b*c"),
        ("snake_case", "snake_case"),
    ):
        assert _balance_markdown_markers(src) == want, src


# ---------------------------------------------------------------------------
# A backslash escape keeps a character literal instead of splitting on it
# ---------------------------------------------------------------------------


def _contents(text: str) -> list[str]:
    out: list[str] = []

    def walk(n):
        if not n.children and n.content:
            out.append(n.content)
        for c in n.children:
            walk(c)

    walk(_processed_with_criteria(text))
    return out


def test_each_escapable_separator_keeps_its_line_whole():
    """The five characters a split consumes that CommonMark can also escape.
    The backslash itself must not survive into the text."""
    for src, whole in (
        (r"Fri, Aug 14 \- Sun, Aug 16", "Fri, Aug 14 - Sun, Aug 16"),
        (r"A \| B", "A | B"),
        (r"Key\: value", "Key: value"),
        (r"A \... B", "A ... B"),
        (r"Cat\, Dog\, Fish", "Cat, Dog, Fish"),
    ):
        assert _contents(src) == [whole], (src, _contents(src))


def test_the_unescaped_twin_still_splits():
    """The escape must be the only difference — these are the same lines."""
    assert _contents("Fri, Aug 14 - Sun, Aug 16") == [
        "Fri, Aug 14",
        "Sun, Aug 16",
    ]
    assert _contents("A | B") == ["A", "B"]
    assert _contents("A ... B") == ["A", "B"]
    # A colon splits nothing (ADR-205), so its escape is the line as written.
    assert _contents("Key: value") == ["Key: value"]


def test_an_escape_does_not_cost_a_datapoint():
    """Detection runs on the escape-free text and the offsets are mapped back,
    so an escaped span is still read as a time range, date or price. Once 6.17
    consumes the backslash, the point names the text that is left."""
    leaves = []

    def walk(n):
        if not n.children and n.content:
            leaves.append(n)
        for c in n.children:
            walk(c)

    walk(_processed_with_criteria(r"8:00 AM \- 9:00 AM"))
    assert [(n.type, n.content) for n in leaves] == [
        (NodeType.TEXT, "8:00 AM - 9:00 AM")
    ]
    assert len(leaves[0].data_points) == 1
    point = leaves[0].data_points[0]
    assert point["type"] == DataPointType.TIME
    assert (point["matched"], point["start"], point["end"]) == (
        "8:00 AM - 9:00 AM",
        0,
        17,
    )


def test_an_escaped_list_marker_is_not_a_list():
    """A dash escaped at the start of a line is a paragraph, per CommonMark."""
    assert _contents(r"\- This is not a list") == ["- This is not a list"]
    assert _contents("- a real list") == ["a real list"]


def test_a_backslash_before_a_non_escapable_char_is_untouched():
    """A long dash splits nothing, so there is nothing to escape: the backslash
    stays literal text."""
    got = _contents("A \\— B")
    assert any("\\" in c for c in got), got


# ---------------------------------------------------------------------------
# Commas are punctuation
# ---------------------------------------------------------------------------


def _shape(text: str):
    """Nested (content-or-None, [children]) for a processed line, types dropped."""

    def walk(n):
        return n.content if not n.children else [walk(c) for c in n.children]

    return walk(_processed_with_criteria(text))


def test_comma_stays_inside_every_other_separator_piece():
    for line in ("Alpha | Beta, Gamma", "Alpha - Beta, Gamma", "Alpha : Beta, Gamma"):
        assert _shape(line) == [["Alpha", "Beta, Gamma"]], (line, _shape(line))
    print("  ✓  '|', '-' and ' : ' split; commas remain in their pieces")


def test_the_spaced_colon_keeps_its_whole_value():
    """A comma inside a column's value must not cut it."""
    col = _find(_tree("Alpha : Beta, Gamma"), NodeType.GROUP)
    assert col is not None and col[2], "expected a column_split container"
    assert [k[1] or [g[1] for g in k[3]] for k in col[3]] == [
        "Alpha",
        "Beta, Gamma",
    ], col
    print("  ✓  ' : ' keeps 'Beta, Gamma' whole as its second column")


def test_a_bare_comma_list_stays_whole():
    assert _shape("Beta, Gamma") == ["Beta, Gamma"]
    assert _contents("Cat, Dog, Fish") == ["Cat, Dog, Fish"]
    print("  ✓  a bare comma list stays whole")


def test_a_glued_colon_is_text():
    # A key-value colon has a space after it; glued, it is text like `10:30`.
    # A spaced first pair still owns the line.
    for line in (
        "key:value 1, key:value 2, key:value 3",
        "H:25° L:12°",
        "Friday 10:30",
        # Styled too: the emphasis is the value's, not a key's.
        "**H:25°**",
        "__H:25°__",
        "***H:25°***",
        "~~H:25°~~",
    ):
        kvs = [
            n
            for n in _walk_types(_processed_with_criteria(line))
            if n.type == NodeType.KEY_VALUE
        ]
        assert not kvs, (line, [k.to_dict() for k in kvs])
        # `__x__` is the Lead tier: its markers become the text's style.
        assert _contents(line) == [line[2:-2] if line[:2] == "__" else line], line
    # Spaced is text too (ADR-205), styled or not: the line as written.
    for line in ("key: value 1, key:value 2", "**Key:** value", "**Key: value**"):
        assert _contents(line) == [line], (line, _contents(line))
        assert_reads_as_escaped_twin(line)
    print("  ✓  a colon is text, glued or spaced")


def test_a_colon_line_keeps_its_commas():
    assert _shape("Alpha: Beta, Gamma") == ["Alpha: Beta, Gamma"]
    print("  ✓  a colon line keeps its commas")


def test_prose_keeps_its_commas():
    for line in (
        "Method: In a small bowl, whisk together flour, baking soda, and salt.",
        "Note - In a large bowl, beat the butter until creamy and fluffy.",
    ):
        leaves = _contents(line)
        assert any("," in c for c in leaves), (line, leaves)
    print("  ✓  a prose piece keeps its commas")


def test_commas_stay_whole_and_escapes_still_resolve():
    assert _contents("Total | $1,234,567.89") == ["Total", "$1,234,567.89"]
    assert _contents(r"One\, Two\, Three") == ["One, Two, Three"]
    assert _contents("Order : March 5, 3 PM") == ["Order", "March 5, 3 PM"]
    print("  ✓  numeric, escaped and timestamp commas stay whole")


def _walk_types(node):
    yield node
    for c in node.children:
        yield from _walk_types(c)


def test_a_spaced_dash_divides_a_sentence():
    # A spaced ` - ` divides wherever it is, like ` | `: whether a line ends as
    # a sentence does not decide it. Prose writes `—`, or escapes `\-`.
    for line in (
        "Delivery takes 3 days - order before 5 PM.",
        "The lamp is fantastic - bright and sleek.",
    ):
        got = _split(line)
        assert got is not None and len(got) == 2, (line, got)
    assert _leaf_contents("Alpha | Beta - Gamma.") == ["Alpha", "Beta", "Gamma."]
    assert _split("The lamp is fantastic \\- bright and sleek.") is None
    assert _split("The lamp is fantastic — bright and sleek.") is None
    print("  ✓  a spaced dash divides a sentence; an escape or an em dash does not")


def test_a_separator_outranks_a_tight_colon():
    # ADR-205: the colon makes no pair, so the separator divides the line and
    # the colon stays in the piece it was written in, as when it is escaped.
    for line, pieces in (
        ("Note: it crashed - really.", ["Note: it crashed", "really."]),
        ("Key: A | B", ["Key: A", "B"]),
    ):
        assert _leaf_contents(line) == pieces, (line, _leaf_contents(line))
        assert _find(_tree(line), NodeType.KEY_VALUE) is None, line
        assert_reads_as_escaped_twin(line)
    print("  ✓  a separator divides a colon line; the colon stays in its piece")


def test_rows_ending_in_a_stop_split():
    for line in (
        '"Love the quality and fast shipping!" - Sarah M.',
        "**Beagle** - Merry, friendly, and curious hound.",
        "🚶 - A little further.",
        "🚶 - __A little further.__",
        "⚡ - Charging...",
        "Wait 10 minutes - it is slow",
        "**Labrador Retriever** - Friendly, outgoing companion",
    ):
        got = _split(line)
        assert got is not None and len(got) == 2, (line, got)
    print("  ✓  attribution, element lead, ellipsis and unpunctuated rows split")


def test_separator_scans_never_ask_the_criteria():
    """A bomb in SplitCriteria.applicable pins both scans as character rules."""
    from md2ui.pipeline.grouper_node_reads import _row_separator_chars

    with (
        patch.object(
            SplitCriteria,
            "applicable",
            side_effect=AssertionError(
                "separator scan reached SplitCriteria.applicable"
            ),
        ),
    ):
        assert _split("Alpha | Beta - Gamma.") is not None
        assert _row_separator_chars("Alpha | Beta - Gamma.", []) == ["|", "-"]


TESTS = [
    test_comma_stays_inside_every_other_separator_piece,
    test_the_spaced_colon_keeps_its_whole_value,
    test_a_bare_comma_list_stays_whole,
    test_a_glued_colon_is_text,
    test_a_colon_line_keeps_its_commas,
    test_prose_keeps_its_commas,
    test_commas_stay_whole_and_escapes_still_resolve,
    test_a_tight_colon_line_stacks_at_its_spaced_colon,
    test_a_separator_segment_stacks_at_its_colon,
    test_kv_value_colon_leaves_no_literal_colon,
    test_a_tight_colon_is_text_and_a_spaced_one_is_columns,
    test_bold_italic_wrap_reaches_every_segment,
    test_strike_wrap_reaches_the_middle_segment_too,
    test_code_wrap_propagates_backticks,
    test_a_sequence_of_spans_is_not_a_wrap,
    test_lone_tilde_is_not_a_wrap,
    test_colon_columns_split_on_spaced_colon,
    test_colon_columns_need_a_space_on_both_sides,
    test_colon_columns_protected_range,
    test_colon_columns_rule_piece,
    test_colon_columns_single_piece_is_none,
    test_plain_colon_kv_rejects_a_spaced_colon,
    test_a_dot_never_splits,
    test_a_dot_stays_in_the_piece_a_separator_makes,
    test_a_dot_line_is_one_text,
    test_pipe_only_unchanged,
    test_em_dash_only_unchanged,
    test_comma_never_splits,
    test_no_separator_returns_none,
    test_a_star_inside_a_code_span_keeps_its_chip,
    test_the_chip_survives_every_split_that_reaches_it,
    test_balancing_inside_a_complete_span_is_left_alone,
    test_a_span_cut_in_half_is_still_repaired,
    test_asterisk_balancing_without_a_span_is_untouched,
    test_each_escapable_separator_keeps_its_line_whole,
    test_the_unescaped_twin_still_splits,
    test_an_escape_does_not_cost_a_datapoint,
    test_an_escaped_list_marker_is_not_a_list,
    test_a_backslash_before_a_non_escapable_char_is_untouched,
    test_a_spaced_dash_divides_a_sentence,
    test_a_separator_outranks_a_tight_colon,
    test_rows_ending_in_a_stop_split,
    test_separator_scans_never_ask_the_criteria,
]


if __name__ == "__main__":
    print("Separator Split Tests")
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
