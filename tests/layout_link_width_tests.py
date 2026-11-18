"""
Unit tests for button-aware minimum widths: when the renderer supplies a
``measure_width`` callback (single-line pill width for link / inline_code
leaves), the generator's fit decisions floor at the widest pill so a row/grid
cell is never narrower than the longest button it contains. Without the
callback, the floor is the category's alone.
Run with: uv run layout_link_width_tests.py
"""

from layout_bento_tests import _ast, _group, _leaf
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.generator_units import (
    LEAF_WIDTH,
    _length_category,
    _measured_min_width,
    _min_width,
)


def _link(label: str) -> dict:
    d = _leaf(f"[{label}](/p/{label.lower().replace(' ', '-')}/)", "very_short")
    d["type"] = "link"
    return d


def _cat_w(node) -> float:
    cat = _length_category(node)
    assert cat is not None, "fixture node lacks a length category"
    return LEAF_WIDTH[cat]


def _fake_measure_width(node):
    """Deterministic pill width: 10px per label char + 20px padding."""
    if node.type not in ("link", "inline_code"):
        return None
    label = node.content
    if label.startswith("["):
        label = label[1 : label.index("]")]
    return len(label) * 10.0 + 20.0


def _links_doc(labels_per_group: list[list[str]]):
    """Heading-11 replica: one h2 section with N repeated groups of links."""
    groups = [_group(*[_link(lbl) for lbl in labels]) for labels in labels_per_group]
    return _ast(
        _group(
            _group(
                _leaf("First level heading", "very_short"),
                _group(
                    _leaf("Second level heading", "very_short"),
                    *groups,
                    heading_group=True,
                    heading_level=2,
                ),
                heading_group=True,
                heading_level=1,
            )
        )
    )


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def _grid_rows(layout):
    return [n for n in _walk(layout) if n.type == "row" and n.grid]


def test_min_width_floors_at_pill():
    # NOTE: ASTPatternAnalyzer recomputes length categories from the real
    # content, so expectations derive from each node's actual category.
    ast = _links_doc([["Tiny", "A Very Long Button Label Indeed"]])
    links = [n for n in _walk(ast) if n.type == "link"]
    short, long_ = sorted(links, key=lambda n: len(n.content))
    short_cat = _cat_w(short)
    long_cat = _cat_w(long_)
    # Short label: pill (60) is below its category floor → category wins.
    assert _min_width(short, None, _fake_measure_width) == max(short_cat, 60.0)
    # Long label: pill (330) is above its category floor → pill wins.
    assert long_cat < 330.0, "fixture too short to exceed its category"
    assert _min_width(long_, None, _fake_measure_width) == 330.0
    # No measurer → category floor only.
    assert _min_width(long_) == long_cat
    print("  ✓  _min_width = max(category floor, measured pill); None → category")


def test_measured_min_width_walks_groups():
    ast = _links_doc([["Aa", "A Very Long Button Label Indeed", "Bb"]])
    group = next(n for n in _walk(ast) if n.children and n.children[0].type == "link")
    assert _measured_min_width(group, _fake_measure_width) == 330.0
    assert _measured_min_width(group, None) == 0.0
    print("  ✓  _measured_min_width = widest pill in subtree; 0 without measurer")


def test_grid_cols_respect_longest_pill():
    labels = ["Alpha", "Beta Gamma", "A Very Long Button Label Indeed"]
    ast = _links_doc([labels] * 4)
    longest = 330.0
    gen = LayoutGenerator()
    for width in (480.0, 700.0, 1280.0):
        with_mw = gen.generate(ast, width, measure_width=_fake_measure_width)
        for row in _grid_rows(with_mw):
            col_w = width / row.grid_cols  # no theme → gap 0
            assert col_w >= longest, (
                f"grid col {col_w:.0f} < longest pill {longest} at {width}px"
            )
        # Without the measurer, category-only cols (unit category is the
        # group's propagated max over its links). Only the *group*-run grid rows
        # count — pill (leaf) runs grid too, with their own column math.
        without = gen.generate(ast, width)
        cats_cols = [
            r.grid_cols
            for r in _grid_rows(without)
            if any(c.type != "-" for c in r.children)
        ]
        unit = next(
            n for n in _walk(ast) if n.children and n.children[0].type == "link"
        )
        # Fit-max, then balanced so a ragged last row fills >= 1/2 (the run has
        # 4 members, so at 700px 3+1 balances down to 2+2).
        fit_max = min(4, max(1, int(width / _cat_w(unit))))
        expected = LayoutGenerator._balance_cols(fit_max, 4)
        assert all(c == expected for c in cats_cols), (
            f"category-only cols changed at {width}px: {cats_cols} != {expected}"
        )
    print("  ✓  grid col width ≥ longest pill; measurer-less cols unchanged")


def _fake_word_measure(node):
    """Minimum-unbreakable-width fake: pills → full label width; text → longest
    word at 10px/char (markdown markers stripped); images → None."""
    if node.type == "image":
        return None
    if node.type in ("link", "inline_code"):
        return _fake_measure_width(node)
    words = (node.content or "").replace("*", "").replace("`", "").split()
    return max((len(w) * 10.0 for w in words), default=0.0) or None


def test_text_min_width_floors_at_longest_word():
    # 'Transportation' replica: a one-word bold key (14 chars → 140px fake)
    # whose category floor (one_word = 80) is far below the real word width.
    ast = _ast(_group(_group(_leaf("**Transportation**"), _leaf("$71.80"))))
    node = next(n for n in _walk(ast) if "Transportation" in (n.content or ""))
    assert _min_width(node, None, _fake_word_measure) == 140.0
    assert _min_width(node) == LEAF_WIDTH["one_word"]  # measurer-less floor
    print("  ✓  text _min_width floors at the longest unbreakable word")


def test_grid_cols_respect_longest_word():
    # Repeated key-value cards, one holding a wide single word — the grid's
    # column width must fit it, or the word clips.
    cards = [
        _group(
            _leaf("**Transportation**" if i == 5 else f"**Key{i}**"),
            _leaf(f"${i}.00"),
        )
        for i in range(8)
    ]
    ast = _ast(
        _group(
            _group(
                _leaf("Spending Categories", "very_short"),
                *cards,
                heading_group=True,
                heading_level=2,
            )
        )
    )
    gen = LayoutGenerator()
    for width in (613.0, 728.0):
        layout = gen.generate(ast, width, measure_width=_fake_word_measure)
        rows = _grid_rows(layout)
        assert rows, f"cards did not grid at {width}px"
        for r in rows:
            col_w = width / r.grid_cols  # no theme → gap 0
            assert col_w >= 140.0, (
                f"grid col {col_w:.0f} < longest word 140 at {width}px"
            )
    print("  ✓  card grid columns fit the widest single word (613/728px)")


def test_no_measurer_output_identical():
    ast = _links_doc([["Alpha", "A Very Long Button Label Indeed"]] * 4)
    fresh = LayoutGenerator().generate(ast, 900.0).to_dict()
    reused = LayoutGenerator()
    reused.generate(ast, 900.0, measure_width=_fake_measure_width)
    again = reused.generate(ast, 900.0).to_dict()  # measurer must not linger
    assert fresh == again, "measure_width state leaked across generate calls"
    print("  ✓  measure_width=None output identical (no state leaks)")


def test_bento_span_respects_pill():
    # 4 sibling h2 cells, one holding a long button — its bento span must be
    # wide enough for the pill.
    cells = [
        _group(
            _leaf(f"Second level heading {i}", "very_short"),
            _group(*[_link("Short")] * 2),
            heading_group=True,
            heading_level=2,
        )
        for i in range(3)
    ]
    cells.append(
        _group(
            _leaf("Second level heading L", "very_short"),
            _group(_link("A Very Long Button Label Indeed")),
            heading_group=True,
            heading_level=2,
        )
    )
    ast = _ast(
        _group(
            _group(
                _leaf("First level heading", "very_short"),
                *cells,
                heading_group=True,
                heading_level=1,
            )
        )
    )
    longest = 330.0
    long_id = next(
        n.node_id for n in _walk(ast) if n.type == "link" and "A Very Long" in n.content
    )
    gen = LayoutGenerator()
    gen.bento_override = True
    width = 1280.0
    layout = gen.generate(ast, width, measure_width=_fake_measure_width)
    bento_rows = [n for n in _walk(layout) if n.type == "row" and n.bento]
    assert bento_rows, "no mosaic built"
    # The band holding the long-button leaf must be allotted at least the pill
    # width (band width math mirrors _build_bento; no theme → gap 0).
    checked = False
    for row in bento_rows:
        total = sum(row.ratios)
        for band, span in zip(row.children, row.ratios):
            ids = {x.content_id for x in _walk(band) if x.type == "-"}
            if long_id in ids:
                band_w = width * span / total
                assert band_w >= longest, f"bento band {band_w:.0f} < pill {longest}"
                checked = True
    assert checked, "long-button cell not found inside any bento row"
    print("  ✓  bento span holding a long button is at least the pill width")


TESTS = [
    test_min_width_floors_at_pill,
    test_measured_min_width_walks_groups,
    test_text_min_width_floors_at_longest_word,
    test_grid_cols_respect_longest_word,
    test_grid_cols_respect_longest_pill,
    test_no_measurer_output_identical,
    test_bento_span_respects_pill,
]

if __name__ == "__main__":
    print("Layout Link-Width Tests")
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
