"""
The MARKUP escape: ``\\*`` is a star, not emphasis and not a list marker.

CommonMark escapes every ASCII punctuation character, and md2ui resolves most of
them in ``preprocess``. That is too early for ``*``: the emphasis is parsed again
when a text is measured and painted, so a backslash removed by the grouper hands
the drawer a bare ``*x*`` that it draws in italics. So an escaped star keeps its
backslash in the node's content, as the author wrote it, every grouper scan that
reads a star as a marker skips it, and the drawer's inline parse is the one place
it becomes the character (``grouper_escapes.MARKUP_ESCAPES``).

The exercise is ``data/markdown/tests/tests-escaping-markup.md`` ("Escapes that
keep a character literal") and ``tests-lists.md`` (``\\* This is not a list
either``).

Run with: uv run python tests/markup_escape_tests.py
"""

import contextlib
import io

from md2ui import session
from md2ui.pipeline.grouper_inline_marks import _marker_runs
from md2ui.pipeline.render_measure import _explode_words
from md2ui.pipeline.render_text import parse_inline_spans

_KIT = None


def _leaves(markdown: str) -> list[tuple[str, str]]:
    """``(type, content)`` of every leaf, through the real grouping pipeline."""
    global _KIT
    with contextlib.redirect_stdout(io.StringIO()):
        if _KIT is None:
            _KIT = session.load_grouping_kit()
        ast = session.group_markdown(markdown, _KIT)
    assert ast is not None
    out: list[tuple[str, str]] = []

    def walk(node) -> None:
        if node.content and not node.children:
            out.append((str(node.type), node.content))
        for child in node.children:
            walk(child)

    walk(ast)
    return out


def _drawn(content: str) -> list[tuple[str, bool, bool]]:
    """``(text, bold, italic)`` of each span the drawer paints."""
    return [(s[0], bool(s[1]), bool(s[2])) for s in parse_inline_spans(content)]


def test_an_escaped_star_starts_no_list_item():
    leaves = _leaves("\\* This is not a list\n")
    assert leaves == [("text", "\\* This is not a list")], leaves
    assert _drawn(leaves[0][1]) == [("* This is not a list", False, False)]
    # ...and its unescaped twin still is one.
    assert _leaves("* This is a list\n") == [("list_item", "This is a list")]
    print("  ✓  `\\* x` is a text drawn with its star; `* x` is a list item")


def test_escaped_stars_draw_as_written_in_a_sentence():
    line = "Price is \\*not emphasis\\* and \\*\\*not bold\\*\\* here"
    leaves = _leaves(line + "\n")
    assert leaves == [("text", line)], leaves
    assert _drawn(line) == [
        ("Price is *not emphasis* and **not bold** here", False, False)
    ], _drawn(line)
    print("  ✓  escaped stars in a sentence are drawn as stars, not emphasis")


def test_escaped_stars_are_no_thematic_break():
    assert _leaves("\\*\\*\\*\n") == [("text", "\\*\\*\\*")]
    assert _drawn("\\*\\*\\*") == [("***", False, False)]
    print("  ✓  `\\*\\*\\*` is three stars of text, not a section stop")


def test_an_escaped_star_never_closes_emphasis():
    """CommonMark: an escaped star can neither open nor close a span."""
    assert _drawn("*a\\*") == [("*a*", False, False)]
    assert _drawn("*a\\* b*") == [("a* b", False, True)]
    assert _drawn("**Total\\***") == [("Total*", True, False)]
    assert _drawn("*real* \\*") == [("real", False, True), (" *", False, False)]
    print("  ✓  an escaped star neither opens nor closes; a real span keeps it")


def test_a_code_span_keeps_its_backslash():
    assert parse_inline_spans("`a\\*b`")[0][0] == "a\\*b"
    assert parse_inline_spans("[`x\\*`](/u)")[0][0] == "x\\*"
    print("  ✓  inside a code span or a code label, `\\*` is literal")


def test_a_link_label_draws_its_escaped_star():
    spans = parse_inline_spans("see [a \\*b\\*](/u) now")
    assert [s[0] for s in spans] == ["see ", "a *b*", " now"], spans
    print("  ✓  an inline link's label draws its escaped stars as stars")


def test_the_balancer_leaves_an_escaped_star_alone():
    """A split piece holding an escaped star is not a half-cut span: no partner
    is invented for it, and its backslash survives the cut."""
    assert _marker_runs("\\*x\\*") == []
    assert _marker_runs("\\**x**") == [(2, "*", 1), (4, "*", 2)]
    leaves = _leaves("Note \\*important - details\n")
    assert [c for _t, c in leaves] == ["Note \\*important", "details"], leaves
    print("  ✓  marker runs skip an escaped star; a cut piece keeps it as written")


def test_an_escaped_star_is_measured_inside_its_word():
    words = [w[0] for w in _explode_words("a\\*b and c")]
    assert words == ["a*b", "and", "c"], words
    print("  ✓  `a\\*b` is one word, measured and wrapped whole")


TESTS = [
    test_an_escaped_star_starts_no_list_item,
    test_escaped_stars_draw_as_written_in_a_sentence,
    test_escaped_stars_are_no_thematic_break,
    test_an_escaped_star_never_closes_emphasis,
    test_a_code_span_keeps_its_backslash,
    test_a_link_label_draws_its_escaped_star,
    test_the_balancer_leaves_an_escaped_star_alone,
    test_an_escaped_star_is_measured_inside_its_word,
]

if __name__ == "__main__":
    print("Markup Escape Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
