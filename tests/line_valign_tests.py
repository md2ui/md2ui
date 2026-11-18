"""
Unit tests for the authored VERTICAL alignment of a same-line row:
`@tp` / `@ct` / `@bs` / `@bm` at the end of a source line.

Two halves. The token is consumed at Phase 2.165 and recorded against its
`source_line_id` — not left on the node, because the splits replace the leaf
that carried it — and applied at Phase 6.1 to whichever container turns out to
BE that line, as `line_valign`. The generator then carries it onto the row as
the `line_align` render property, which is the row's own mode and outranks
`Vertical align` on the level.

The escape is the other half, and it only works because `@` is a CONTROL escape
(`grouper_escapes`): `preprocess` does not resolve it, so `\\@ct` still carries
its backslash when the scan runs and is declined, and Phase 6.17 drops the
backslash so the line draws a literal `@ct`. A test here that `\\@ct` declines is
therefore also a test of that deferral.

Run with: uv run tests/line_valign_tests.py
"""

import pathlib

from markdown_datapoint_split_tests import _processed_with_criteria
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.theme import parse_theme

_ROW = "14:30 : LHR : London - **short**"


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _rows(markdown: str, theme=None, width: float = 900.0):
    ast = _processed_with_criteria(markdown)
    layout = LayoutGenerator().generate(ast, width, theme=theme)
    return [n for n in _walk(layout) if n.type == "row"]


def _text(markdown: str) -> str:
    return " ".join(
        n.content for n in _walk(_processed_with_criteria(markdown)) if n.content
    )


def test_each_spelling_stamps_its_value():
    for token, want in (
        ("@tp", "top"),
        ("@ct", "center"),
        ("@bs", "baseline"),
        ("@bm", "bottom"),
    ):
        rows = _rows(f"{_ROW} {token}")
        assert rows, f"{token}: no row"
        got = [(r.render_properties or {}).get("line_align") for r in rows]
        assert want in got, f"{token}: wanted {want}, row line_align {got}"
    print("  ✓  @tp / @ct / @bs / @bm each reach the row as line_align")


def test_no_token_leaves_the_row_alone():
    rows = _rows(_ROW)
    assert rows, "no row"
    assert all((r.render_properties or {}).get("line_align") is None for r in rows), (
        "an unannotated line must leave the slot empty for the theme"
    )
    print("  ✓  an unannotated line leaves the slot to the theme")


def test_the_token_outranks_the_level():
    """`bake_render_cascade` fills `line_align` only when it is EMPTY, so the
    token winning is a property of the generator writing it first."""
    theme = parse_theme(pathlib.Path("data/markdown/tests/THEME.md"))
    rows = _rows(f"{_ROW} @tp", theme=theme)
    got = [(r.render_properties or {}).get("line_align") for r in rows]
    assert "top" in got, f"the token must survive a themed render, got {got}"
    print("  ✓  the token is written before the level cascade can fill the slot")


def test_an_escaped_token_declines_and_draws():
    text = _text(rf"{_ROW} \@ct")
    assert "@ct" in text, f"an escaped token must draw literally, got {text!r}"
    assert "\\" not in text, f"the backslash must not survive, got {text!r}"
    rows = _rows(rf"{_ROW} \@ct")
    assert all((r.render_properties or {}).get("line_align") is None for r in rows), (
        "an escaped token must not align the row"
    )
    print("  ✓  \\@ct declines, keeps no backslash, and draws as text")


def test_a_token_is_consumed_even_with_no_row():
    """An authored layout is a request; one that cannot be honoured must still
    not be drawn as stray text."""
    text = _text("Just a sentence @ct")
    assert text.strip() == "Just a sentence", f"token not consumed: {text!r}"
    print("  ✓  a token on a line that is no row is eaten, not drawn")


def test_a_near_miss_is_ordinary_text():
    for text in ("@ce", "@t", "@ctx"):
        got = _text(f"{_ROW} {text}")
        assert text in got, f"{text!r} is not a token and must survive: {got!r}"
    assert "@ct" in _text("mail support@ct"), "a word ending in a token is not one"
    print("  ✓  @ce / @t / @ctx / support@ct are ordinary text")


def test_a_spring_reads_the_line_without_the_token():
    """The scan runs at 2.165, before the Phase 4+5 spring split, so a line
    ending `... @ct` hands the trailing-spring rule the line the author meant."""
    ast = _processed_with_criteria("... ⭐ - [Buy](/b) ... @ct")
    aligned = [n for n in _walk(ast) if n.authored_align]
    assert aligned, "the spring did not fire"
    assert aligned[0].authored_align == "center", (
        f"a trailing token must not shift the spring's regions, got "
        f"{aligned[0].authored_align}"
    )
    assert not [n for n in _walk(ast) if (n.content or "").strip() == "..."], (
        "a spring survived as a literal leaf"
    )
    print("  ✓  `... @ct` leaves the spring reading the line without the token")


def test_center_reaches_a_row_of_capped_images():
    """A capped image has an intrinsic height, so it has slack to align. Only
    an UNCAPPED image fills the row."""

    from md2ui.pipeline.render_measure import _is_width_capped

    ast = _processed_with_criteria(
        "![a](a.svg?md2ui.max_width=170&md2ui.aspect_ratio=5:2) "
        "![b](b.svg?md2ui.max_width=70&md2ui.aspect_ratio=5:2) @ct"
    )
    layout = LayoutGenerator().generate(ast, 700.0)
    row = next(n for n in _walk(layout) if n.type == "row")
    assert (row.render_properties or {}).get("line_align") == "center"
    cells = [c for c in row.children if c.content_id]
    assert len(cells) == 2, f"expected two image cells, got {len(cells)}"
    assert all(_is_width_capped(c) for c in cells), (
        "both images carry max_width, so both have slack to be aligned"
    )
    print("  ✓  a row of capped images is alignable (they are not stretched)")


TESTS = [
    test_each_spelling_stamps_its_value,
    test_no_token_leaves_the_row_alone,
    test_the_token_outranks_the_level,
    test_an_escaped_token_declines_and_draws,
    test_a_token_is_consumed_even_with_no_row,
    test_a_near_miss_is_ordinary_text,
    test_a_spring_reads_the_line_without_the_token,
    test_center_reaches_a_row_of_capped_images,
]

if __name__ == "__main__":
    print("Line Vertical-Align Token Tests")
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
