"""A data point's offsets name its node's CURRENT content.

A data point is recorded with ``start`` / ``end`` into its node's ``content`` and
``matched``, the text of that span. Several passes rewrite ``content`` after
detection: the display tier's underscores come off (6.055), the late escapes and
a declined element's quotes are consumed (6.17), an escaped task box and an
inline spacer are spelled again, an edge spacer is taken off its line. Every one
of them goes through ``grouper_content_edits.edit_content``, which re-bases the
data points onto the new text.

The invariant is checked on every node of every snapshot document, through the
real pipeline (``session.group_markdown``), so a new pass that edits content
without the helper fails here. ``data/markdown/tests/tests-datapoint-offsets.md``
holds one line per edit site.

Run with: uv run python tests/datapoint_offsets_tests.py
"""

from pathlib import Path

from md2ui import session
from md2ui.pipeline.grouper_content_edits import edit_content, keep_content
from md2ui.pipeline.grouper_types import MarkdownGroupNode

ROOT = Path(__file__).resolve().parent.parent
MARKDOWN = ROOT / "data" / "markdown"
SAMPLE = MARKDOWN / "tests" / "tests-datapoint-offsets.md"

_KIT = session.load_grouping_kit()


def _stale(node: MarkdownGroupNode) -> list[str]:
    """Every data point under *node* whose span is not its ``matched`` text."""
    out = []
    content = node.content or ""
    for dp in node.data_points or []:
        start, end = dp["start"], dp["end"]
        if (
            not (0 <= start < end <= len(content))
            or content[start:end] != dp["matched"]
        ):
            out.append(f"{content!r}[{start}:{end}] is not {dp['matched']!r}")
    for child in node.children:
        out.extend(_stale(child))
    return out


def _grouped(text: str) -> MarkdownGroupNode:
    ast = session.group_markdown(text, _KIT)
    assert ast is not None
    return ast


def _points(node: MarkdownGroupNode) -> list[tuple[str, int, int]]:
    """``(matched, start, end)`` of every data point under *node*, in order."""
    out = [(dp["matched"], dp["start"], dp["end"]) for dp in node.data_points or []]
    for child in node.children:
        out.extend(_points(child))
    return out


def test_every_corpus_data_point_names_its_content():
    paths = sorted(
        p for d in ("tests", "tests-render") for p in (MARKDOWN / d).rglob("*.md")
    )
    assert SAMPLE in paths, "the regression sample must be in the snapshot scope"
    failures = []
    for path in paths:
        for problem in _stale(_grouped(path.read_text())):
            failures.append(f"{path.relative_to(MARKDOWN)}: {problem}")
    assert not failures, f"{len(failures)} stale:\n" + "\n".join(failures[:20])
    print(f"  ✓  every data point in {len(paths)} documents names its own text")


def test_the_regression_sample_reaches_every_edit_site():
    """Each line of the sample is one edit site; name the values so
    a sample that silently stopped detecting them cannot pass by having none."""
    points = {m for m, _, _ in _points(_grouped(SAMPLE.read_text()))}
    for value in ("94%", "543", "Nov 17, 2:15 PM", "February 04, 9:17 PM", "11 AM",
                  "📞", "$5", "Jan 5, 2026", "50%", "27°C", "31"):  # fmt: skip
        assert value in points, f"{value!r} not detected; got {sorted(points)}"
    print("  ✓  the sample holds a value at every edit site")


def test_a_tier_wrapper_shifts_the_value():
    """A value cut from its key is unwrapped at 6.055, after detection; the
    pair is one a percentage bar reads, so it is kept."""
    assert _points(_grouped("Accuracy: ___94%___")) == [("94%", 0, 3)]
    print("  ✓  Accuracy: ___94%___ -> 94% at (0, 3)")


def test_an_escape_inside_a_value_leaves_matched():
    """The backslash is inside the span: the span shrinks, ``matched`` follows."""
    points = _points(_grouped("Due: February 04\\, 9:17 PM"))
    assert ("February 04, 9:17 PM", 5, 25) in points, points
    print("  ✓  an escape removed inside a value re-reads matched")


def test_edit_content_rebases_around_and_inside_a_span():
    node = MarkdownGroupNode(content='"x" a\\-b 12')
    node.data_points = [
        {"matched": "a\\-b", "start": 4, "end": 8},
        {"matched": "12", "start": 9, "end": 11},
        {"matched": '"', "start": 0, "end": 1},
    ]
    shared = node.data_points[1]
    edit_content(node, [(5, 6, ""), (0, 1, ""), (2, 3, "")])
    assert node.content == "x a-b 12", node.content
    assert [(d["matched"], d["start"], d["end"]) for d in node.data_points] == [
        ("a-b", 2, 5),
        ("12", 6, 8),
    ], node.data_points
    assert shared["start"] == 9, "a data point another node holds is not mutated"
    print("  ✓  edit_content shifts, shrinks, drops and copies")


def test_edit_content_follows_a_longer_replacement():
    node = MarkdownGroupNode(content=" costs 50%")
    node.data_points = [{"matched": "50%", "start": 8, "end": 11}]
    edit_content(node, [(0, 1, "+++")])
    assert node.content[node.data_points[0]["start"] :].startswith("50%")
    assert node.data_points[0]["matched"] == "50%"
    print("  ✓  a one-character mark spelled as three moves the value right")


def test_keep_content_narrows_to_a_piece():
    node = MarkdownGroupNode(content="  ___94%___ ")
    node.data_points = [{"matched": "94%", "start": 5, "end": 8}]
    keep_content(node, "94%")
    assert (node.content, node.data_points[0]["start"]) == ("94%", 0)
    print("  ✓  keep_content shifts by where the piece sits")


TESTS = [
    test_every_corpus_data_point_names_its_content,
    test_the_regression_sample_reaches_every_edit_site,
    test_a_tier_wrapper_shifts_the_value,
    test_an_escape_inside_a_value_leaves_matched,
    test_edit_content_rebases_around_and_inside_a_span,
    test_edit_content_follows_a_longer_replacement,
    test_keep_content_narrows_to_a_piece,
]

if __name__ == "__main__":
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:  # noqa: BLE001
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    if failed:
        raise SystemExit(f"{failed} test(s) FAILED.")
    print(f"All {len(TESTS)} tests passed.")
