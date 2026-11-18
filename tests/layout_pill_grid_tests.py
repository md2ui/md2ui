"""
Unit tests for pill-run flow-wrap: a repeated link / inline_code leaf run whose
members are the pieces of ONE source line packs into plain rows — as many pills
per row as fit at their measured single-line widths plus element spacing (the
renderer then packs them at natural width and shrinks the blanks). A run spread
over several lines is a LIST of buttons and stacks instead. Repeated groups keep
the strict grid; other repeated leaf runs (plain text) still stack. Fixtures that
set no source_line_id collapse to {None} = one line, so they flow.
Run with: uv run layout_pill_grid_tests.py
"""

from layout_bento_tests import _ast, _group, _leaf
from md2ui.pipeline.layout_generator import LayoutGenerator


def _link(label: str) -> dict:
    d = _leaf(f"[{label}](/p/{label.lower().replace(' ', '-')}/)", "very_short")
    d["type"] = "link"
    return d


def _code(label: str) -> dict:
    d = _leaf(f"`{label}`", "very_short")
    d["type"] = "inline_code"
    return d


def _fake_measure_width(node):
    """Deterministic pill width: 10px per label char + 20px padding."""
    if node.type not in ("link", "inline_code"):
        return None
    label = node.content
    if label.startswith("["):
        label = label[1 : label.index("]")]
    return len(label.strip("`")) * 10.0 + 20.0


def _pill_doc(pills: list[dict]):
    """One h2 section whose direct children are the pill leaves."""
    return _ast(
        _group(
            _group(
                _leaf("Second level heading", "very_short"),
                *pills,
                heading_group=True,
                heading_level=2,
            )
        )
    )


def _walk(n):
    yield n
    for c in n.children:
        yield from _walk(c)


def _pill_rows(layout):
    """Plain (non-grid) rows whose children are all leaves — the flow rows."""
    return [
        n
        for n in _walk(layout)
        if n.type == "row"
        and not n.grid
        and not n.bento
        and n.children
        and all(c.type == "-" for c in n.children)
    ]


def _leaves(layout):
    return [n.content_id for n in _walk(layout) if n.type == "-"]


def test_one_line_run_flows_multi_line_run_stacks():
    """Flowing aside is what ONE line's pieces do. A run spread over several
    lines is a list of buttons — it stacks, one per row."""
    labels = [f"Button {i}" for i in range(6)]

    def doc(line_ids):
        pills = []
        for lbl, lid in zip(labels, line_ids):
            p = _link(lbl)
            p["source_line_id"] = lid
            pills.append(p)
        return _pill_doc(pills)

    one_line = LayoutGenerator().generate(
        doc([7] * 6), 1280.0, measure_width=_fake_measure_width
    )
    assert any(len(r.children) > 1 for r in _pill_rows(one_line)), (
        "pills of ONE source line still flow"
    )

    per_line = LayoutGenerator().generate(
        doc(list(range(7, 13))), 1280.0, measure_width=_fake_measure_width
    )
    assert not [r for r in _pill_rows(per_line) if len(r.children) > 1], (
        "a button per line must stack, not flow aside"
    )
    # …and every button survives (the section heading leaf rides along).
    assert len(_leaves(per_line)) == len(labels) + 1
    print("  ✓  one line's pills flow; a button-per-line list stacks")


def test_link_run_flows():
    labels = [f"Button {i}" for i in range(9)]  # 100px pills
    ast = _pill_doc([_link(lbl) for lbl in labels])
    layout = LayoutGenerator().generate(ast, 1280.0, measure_width=_fake_measure_width)
    rows = _pill_rows(layout)
    assert rows, "repeated link run did not flow into rows"
    for row in rows:
        assert not row.grid, "flow rows must not carry the grid flag"
        # Batch fits: Σ measured widths (ratios hold them) ≤ available (gap 0
        # without a theme).
        assert sum(row.ratios) <= 1280.0
    assert any(len(r.children) > 1 for r in rows), "no multi-pill rows"
    print(f"  ✓  9-link run flows ({[len(r.children) for r in rows]} per row)")


def test_batches_are_width_driven():
    # Mixed widths, aperiodic: batching adapts per row instead of a fixed
    # column count. 31-char labels → 330px, 3-char labels → 50px.
    wide = "A Rather Long Button Label Here"
    pills = [_link(wide), _link(wide)]  # 330 + 330 = 660
    pills.extend(_link(f"B{i:02d}"[:3]) for i in range(6))  # 6 × 50 = 300
    pills.append(_link(wide))  # + 330 = 630
    pills.append(_link("End"))  # + 50 = 680
    ast = _pill_doc(pills)
    layout = LayoutGenerator().generate(ast, 700.0, measure_width=_fake_measure_width)
    rows = _pill_rows(layout)
    sizes = [len(r.children) for r in rows]
    assert len(set(sizes)) > 1, f"batches look fixed-size: {sizes}"
    for row in rows:
        assert sum(row.ratios) <= 700.0, "a flow row exceeds the available width"
    print(f"  ✓  batches adapt to pill widths (row sizes {sizes})")


def test_inline_code_run_flows():
    ast = _pill_doc([_code(f"snippet_{i}") for i in range(8)])
    layout = LayoutGenerator().generate(ast, 1280.0, measure_width=_fake_measure_width)
    rows = _pill_rows(layout)
    assert rows and any(len(r.children) > 1 for r in rows), (
        "inline_code run did not flow"
    )
    print("  ✓  inline_code run flows like a link run")


def test_text_leaf_run_still_stacks():
    ast = _pill_doc([_leaf(f"plain text {i}", "very_short") for i in range(8)])
    layout = LayoutGenerator().generate(ast, 1280.0, measure_width=_fake_measure_width)
    assert not _pill_rows(layout), "plain text leaf run must keep stacking"
    print("  ✓  repeated plain-text leaves still stack (no rows)")


def test_single_link_full_width():
    ast = _pill_doc([_leaf("some intro text"), _link("Lonely"), _leaf("closing text")])
    layout = LayoutGenerator().generate(ast, 1280.0, measure_width=_fake_measure_width)
    assert not _pill_rows(layout), "a single non-repeated link must not flow"
    print("  ✓  single non-repeated link stays full-width")


def test_order_and_uniqueness():
    labels = [f"Button {i}" for i in range(11)]
    ast = _pill_doc([_link(lbl) for lbl in labels])
    link_ids = [n.node_id for n in _walk(ast) if n.type == "link"]
    gen = LayoutGenerator()
    for width in (400.0, 1280.0):
        got = _leaves(gen.generate(ast, width, measure_width=_fake_measure_width))
        got_links = [i for i in got if i in set(link_ids)]
        assert got_links == link_ids, f"pill order changed at {width}px"
        assert len(set(got)) == len(got), f"duplicate leaves at {width}px"
    print("  ✓  document order preserved, every pill placed exactly once")


def test_narrow_width_stacks():
    pills = [_link("A Rather Wide Button Label") for _ in range(4)]  # 280px
    ast = _pill_doc(pills)
    layout = LayoutGenerator().generate(ast, 300.0, measure_width=_fake_measure_width)
    assert not _pill_rows(layout), "wide pills must stack when only one fits"
    print("  ✓  narrow width collapses pill run back to a stack")


def test_no_measurer_fallback_batches():
    ast = _pill_doc([_link(f"Button {i}") for i in range(9)])
    layout = LayoutGenerator().generate(ast, 1280.0)  # category widths (~100)
    rows = _pill_rows(layout)
    assert rows and any(len(r.children) > 1 for r in rows), (
        "measurer-less pill run did not batch"
    )
    got = [i for i in _leaves(layout) if i]
    assert len(set(got)) == len(got)
    print("  ✓  measurer-less fallback batches by category widths")


# ---------------------------------------------------------------------------
# Chip geometry: the corner radius must not widen the pill
# ---------------------------------------------------------------------------


def _chip(radius: float, pad: float = 4.0):
    from md2ui.pipeline.theme import InlineCodeTheme, PaddingBox

    return InlineCodeTheme(corner_radius=radius, padding=PaddingBox(pad, pad, pad, pad))


def test_a_radius_that_fits_is_measured_exactly_as_before():
    """A radius under the clamp keeps its width.

    The shipped chip is radius 16 on a ~25px-tall pill, so the inset is the
    radius itself.
    """
    from md2ui.pipeline.layout_render import _chip_metrics

    bg_w, bg_h, _r, _l, _rp = _chip_metrics(_chip(16.0), 100.0, 17.0)
    assert bg_h == 25.0
    assert bg_w == 100.0 + 8.0 + 16.0


def test_an_oversized_radius_is_a_stadium_not_a_wider_pill():
    """`Corner radius: 999` is the CSS "fully rounded" idiom.

    Unclamped it would add 999px to every chip, so a run of them could never
    share a row. Clamped,
    it means the same thing a big radius already means on a link button.
    """
    from md2ui.pipeline.layout_render import _chip_metrics

    huge = _chip_metrics(_chip(999.0, 10.0), 100.0, 17.0)
    at_height = _chip_metrics(_chip(37.0, 10.0), 100.0, 17.0)
    assert huge == at_height, (huge, at_height)
    bg_w, bg_h, radius, _l, _rp = huge
    # The widest a rounded end can need is one chip-height of room…
    assert bg_w == 100.0 + 20.0 + bg_h
    # …and the painted radius is a true half-height stadium.
    assert radius == bg_h / 2.0


def test_one_helper_sizes_every_chip():
    """The measurer, the drawer and the extent path must not drift apart.

    Repeating the same arithmetic three times is how a clamp applied to some
    of them would silently mis-measure.
    """
    import inspect

    from md2ui.pipeline import layout_render as LR
    from md2ui.pipeline import render_metrics as RM
    from md2ui.pipeline import render_style as RS

    # `_chip_metrics` lives in render_metrics with the other metrics; its callers
    # stay in the renderer, so the check spans the modules.
    from md2ui.pipeline import render_measure as RMS

    everywhere = "".join(inspect.getsource(m) for m in (LR, RS, RM, RMS))
    assert "code.corner_radius / 2" not in everywhere, (
        "a chip is being sized outside _chip_metrics"
    )
    assert "def _chip_metrics(" in inspect.getsource(RM), (
        "the one sizing helper is in render_metrics"
    )
    # measurer, drawer and extent path, across the renderer and the sizing
    # module, all calling the same helper.
    callers = everywhere.count("_chip_metrics(") - 1  # minus the definition
    assert callers >= 3, f"expected >=3 callers of _chip_metrics, found {callers}"


TESTS = [
    test_one_line_run_flows_multi_line_run_stacks,
    test_link_run_flows,
    test_batches_are_width_driven,
    test_inline_code_run_flows,
    test_text_leaf_run_still_stacks,
    test_single_link_full_width,
    test_order_and_uniqueness,
    test_narrow_width_stacks,
    test_no_measurer_fallback_batches,
    test_a_radius_that_fits_is_measured_exactly_as_before,
    test_an_oversized_radius_is_a_stadium_not_a_wider_pill,
    test_one_helper_sizes_every_chip,
]

if __name__ == "__main__":
    print("Pill Flow-Row Layout Tests")
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
