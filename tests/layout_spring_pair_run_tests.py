"""
Unit tests for a run of spring pairs: ``Key: ... value`` lines are written one
pair to a line, so a run of them stacks as a column, exactly as a run of spring
lines (``Key ... value``) does, and each pair keeps its key left, colon drawn,
and its value right across the full width. A plain ``Key: value`` line is one
text (ADR-205), so a run of them is prose, not tiles.

Run with: uv run tests/layout_spring_pair_run_tests.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.markdown_grouper import MarkdownGrouper, MarkdownGroupNode

_SPRING_PAIRS = "Key: ... value\n\nKey: ... value\n\nKey: ... value\n"
_PLAIN_PAIRS = "Key: value\n\nKey: value\n\nKey: value\n"

# One section per spelling.
_SECTIONS = {
    "Plain": _PLAIN_PAIRS,
    "Short springs": _SPRING_PAIRS,
    "Long springs": "\n\n".join(["More long key: ... More long value"] * 3),
    "Spring lines": "\n\n".join(["More long key ... More long value"] * 3),
    "Long values": "\n\n".join(
        ["Key: Lorem ipsum dolor sit amet, consectetur adipiscing elit."] * 3
    ),
}


def _ast(text: str) -> MarkdownGroupNode:
    g = MarkdownGrouper(text)
    g.process(criteria=None, detector=DataPointDetector())
    assert g.ast is not None
    return g.ast


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def _generate(text: str, width: float = 1280.0):
    ast = _ast(text)
    return ast, LayoutGenerator().generate(ast, width)


def _gridded_ids(layout) -> set:
    """Every content id drawn inside a grid row."""
    return {
        x.content_id
        for n in _walk(layout)
        if getattr(n, "grid", False)
        for x in _walk(n)
        if x.content_id
    }


def _ids(node) -> set:
    return {x.node_id for x in _walk(node)}


def _lines(ast) -> list:
    """The document's lines: the top-level nodes, one per paragraph here."""
    return list(ast.children)


def _row_of(layout, line):
    """The smallest layout node drawing both halves of the spring *line*."""
    left, right = (_ids(c) for c in line.children)
    best = None
    for n in _walk(layout):
        drawn = {x.content_id for x in _walk(n) if x.content_id}
        if drawn & left and drawn & right:
            best = n
    return best


def test_a_run_of_spring_pairs_stacks_as_a_column():
    ast, layout = _generate(_SPRING_PAIRS)
    lines = _lines(ast)
    assert len(lines) == 3
    assert all([c.content for c in n.children] == ["Key:", "value"] for n in lines)
    assert not _gridded_ids(layout), "no pair is a tile"


def test_each_spring_pair_keeps_key_left_and_value_right():
    ast, layout = _generate(_SPRING_PAIRS)
    for line in _lines(ast):
        row = _row_of(layout, line)
        assert row is not None and row.type == "row"
        value = row.children[1]
        assert (value.render_properties or {}).get("content_align") == "right"


def test_plain_pairs_are_one_text_each():
    ast, layout = _generate(_PLAIN_PAIRS)
    assert [(n.content, n.children) for n in _lines(ast)] == [("Key: value", [])] * 3
    assert not _gridded_ids(layout), "a line of prose is not a tile"


def test_each_spelling_keeps_its_run_shape():
    text = "\n\n".join(f"## {t}\n\n{body}\n\n___" for t, body in _SECTIONS.items())
    ast, layout = _generate(text)
    drawn = _gridded_ids(layout)
    sections = [n for n in ast.children if n.heading_group]
    grids = {}
    for section in sections:
        title = section.children[0].content
        body = [c for c in section.children[1:] if c.content or c.children]
        grids[title] = [bool(_ids(c) & drawn) for c in body]
    assert grids == {title: [False] * 3 for title in _SECTIONS}


TESTS = [
    test_a_run_of_spring_pairs_stacks_as_a_column,
    test_each_spring_pair_keeps_key_left_and_value_right,
    test_plain_pairs_are_one_text_each,
    test_each_spelling_keeps_its_run_shape,
]


if __name__ == "__main__":
    failed = 0
    for t in TESTS:
        try:
            t()
            print(f"  ok    {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  FAIL  {t.__name__}: {e!r}")
    sys.exit(1 if failed else 0)
