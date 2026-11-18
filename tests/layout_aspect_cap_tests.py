"""Unit tests for LayoutGenerator._aspect_cap (aspect-aware column widening).

Drives the method with a controlled height-for-width function (overriding
``_cell_height``) so no fonts/AST are needed. Rules under test:
  * widen (fewer cols) while the tallest member's aspect (h / col_w) > TARGET_ASPECT;
  * never below what content needs (returns cols when already acceptable);
  * HEIGHT_GROWTH_CAP guard: don't widen when it makes the tallest member grow past
    that multiple (image-dominated cards stay put);
  * a column is dropped only when that makes the tallest member SHORTER:
    flat-height content (rings, link lists) keeps its columns;
  * ``_cell_height`` itself shares one measurement per ``CELL_HEIGHT_BUCKET`` of
    width, taken at the bucket's floor (an approximation).
"""

from md2ui.pipeline.markdown_grouper import MarkdownGroupNode
from md2ui.pipeline.layout_generator import (
    CELL_HEIGHT_BUCKET,
    KIND_SWEEP_FALLBACK,
    KIND_SWEEP_SAMPLE,
    LayoutGenerator,
    TARGET_ASPECT,
)


def _gen_with_height(height_of):
    """A LayoutGenerator whose _cell_height is `height_of(width)` (gap-free)."""
    g = LayoutGenerator()
    g._theme = None  # -> _col_gap == 0
    g._measure = None
    g._cell_h_cache = {}
    g._cell_height = lambda unit, w, parent, ol: height_of(w)  # type: ignore
    return g


def _run(n):
    return [MarkdownGroupNode("", "group") for _ in range(n)]


def _cap(height_of, cols, n=6, width=1216.0):
    g = _gen_with_height(height_of)
    return g._aspect_cap(_run(n), cols, width, MarkdownGroupNode("", "group"), 0)


def test_already_acceptable_kept():
    # Flat short cards: aspect well under target at the fit-max -> untouched.
    assert _cap(lambda w: 300.0, cols=4) == 4


def _wrapping(width):
    # Wrapping text: a constant area, so a wider column is a shorter card.
    return 300000.0 / width


def test_tall_thin_widens_to_target():
    # Wrapping cards: widen until the chosen column width brings aspect within
    # TARGET_ASPECT (or all the way to 1).
    k = _cap(_wrapping, cols=4)
    assert k < 4
    assert _wrapping(1216.0 / k) / (1216.0 / k) <= TARGET_ASPECT or k == 1


def test_flat_height_keeps_cols():
    # Tall but width-invariant (ring cards, link columns): widening would not
    # make any card shorter, only the page longer -> keep the columns.
    assert _cap(lambda w: 1400.0, cols=3) == 3
    # A pixel of measurement wobble is the same height, not a shorter one.
    assert _cap(lambda w: 1400.0 - (1216.0 - w) / 1216.0, cols=3) == 3


def test_lands_on_the_last_shorter_count():
    # Shorter than at 4 columns only at 3; at 2 and 1 as tall as at 4 again (1
    # reaching the target). Shorter is judged against the original count, so the
    # cap lands on 3 and never on a count that is merely as tall.
    def h(width):
        return 900.0 if 1216.0 / 3.5 < width < 500.0 else 1300.0

    assert _cap(h, cols=4) == 3


def test_image_growth_guard_blocks():
    # Image-dominated: height scales with width (aspect ~constant, always > target).
    # Widening only makes it taller past HEIGHT_GROWTH_CAP -> stay at cols.
    def h(width):
        return 3.0 * width

    assert _cap(h, cols=2, n=2, width=800.0) == 2


def test_never_increases_cols():
    for hf in (lambda w: 300.0, lambda w: 1200.0, lambda w: 3.0 * w):
        for cols in range(1, 6):
            assert _cap(hf, cols=cols, n=6) <= cols


def test_single_or_zero_gap_math():
    # Sanity: with the tall-thin case, the chosen col_w keeps aspect <= target.
    width = 1216.0

    k = _cap(_wrapping, cols=5, width=width)
    col_w = width / k
    assert _wrapping(col_w) / col_w <= TARGET_ASPECT or k == 1


def test_kind_cols_shared_and_gated():
    # _kind_cols is a pure function of the KIND (not the run), so two runs of the
    # same kind get the same count; it clamps to the largest run and only engages
    # when the kind occurs >= 2 times (else None -> caller keeps per-run fill).
    g = LayoutGenerator()
    g._theme = None
    g._measure = None
    g._cell_h_cache = {}
    g._min_w_cache = {}
    K = 740878
    members = [MarkdownGroupNode("", "group") for _ in range(4)]
    for m in members:
        m.kind_hash = K
    g._kind_members = {K: members}
    g._kind_min_width = {K: 200.0}
    g._kind_max_run = {K: 4}
    g._kind_occurrences = {K: 3}
    # What _build_kind_maps records for the fill vote: one run of 4, which the
    # vote leaves alone (a full row orphans nothing).
    g._kind_run_lens = {K: [4]}
    unit = MarkdownGroupNode("", "group")
    unit.kind_hash = K
    c1 = g._kind_cols(unit, 850.0, unit, 0)
    c2 = g._kind_cols(unit, 850.0, unit, 0)
    assert c1 == c2 and c1 and c1 >= 1  # shared across runs
    g._kind_max_run = {K: 2}
    assert (g._kind_cols(unit, 850.0, unit, 0) or 0) <= 2  # clamp to largest run
    g._kind_max_run = {K: 4}
    g._kind_occurrences = {K: 1}
    assert g._kind_cols(unit, 850.0, unit, 0) is None  # lone kind -> fallback


def test_cell_height_shares_one_measurement_per_bucket():
    # Trial widths a few px apart must cost ONE measurement, taken at the
    # bucket's floor (never wider than the card really is).
    g = LayoutGenerator()
    g._cell_h_cache = {}
    asked = []
    g._render_child = lambda *a, **k: None  # type: ignore
    g._measure = lambda sub, w: asked.append(w) or 10.0 * w  # type: ignore
    unit = MarkdownGroupNode("", "group")
    floor = 40 * CELL_HEIGHT_BUCKET
    first = g._cell_height(unit, floor + 0.5, unit, 0)
    second = g._cell_height(unit, floor + CELL_HEIGHT_BUCKET - 0.5, unit, 0)
    assert asked == [float(floor)], asked
    assert first == second == 10.0 * floor
    g._cell_height(unit, floor + CELL_HEIGHT_BUCKET, unit, 0)  # the next bucket
    assert asked == [float(floor), float(floor + CELL_HEIGHT_BUCKET)], asked
    assert g._cell_height(unit, 0.0, unit, 0) == 0.0


def test_kind_sweep_samples_then_falls_back():
    # A large kind is checked on its sample first. Clearly under the threshold,
    # only the sample is measured; near it, every member is — so a tall member
    # outside the sample still decides a cap that can fire.
    g = LayoutGenerator()
    g._theme = None  # -> _col_gap == 0
    g._measure = None
    g._cell_h_cache = {}
    members = [MarkdownGroupNode("", "group") for _ in range(KIND_SWEEP_SAMPLE + 4)]
    sample = members[:KIND_SWEEP_SAMPLE]
    heights: dict[int, float] = {}
    asked = []

    def height(unit, w, parent, ol):
        asked.append(unit)
        return heights[id(unit)]

    g._cell_height = height  # type: ignore
    g._kind_sample = {7: sample}
    width, cols = 1000.0, 4  # col_w 250
    heights.update({id(m): 10.0 for m in members})
    assert g._kind_aspect_cap(7, members, cols, width, members[0], 0) == cols
    assert asked and all(u in sample for u in asked), "measured beyond the sample"

    near = (1 - KIND_SWEEP_FALLBACK / 2) * TARGET_ASPECT * 250.0
    heights.update({id(m): near for m in members})
    heights[id(members[-1])] = 5 * 250.0  # tall, and NOT in the sample
    asked.clear()
    got = g._kind_aspect_cap(7, members, cols, width, members[0], 0)
    assert members[-1] in asked, "a near-threshold sample must sweep every member"
    assert got == g._aspect_cap(members, cols, width, members[0], 0)


TESTS = [
    test_kind_cols_shared_and_gated,
    test_already_acceptable_kept,
    test_tall_thin_widens_to_target,
    test_flat_height_keeps_cols,
    test_lands_on_the_last_shorter_count,
    test_image_growth_guard_blocks,
    test_never_increases_cols,
    test_single_or_zero_gap_math,
    test_cell_height_shares_one_measurement_per_bucket,
    test_kind_sweep_samples_then_falls_back,
]

if __name__ == "__main__":
    print("Aspect-Cap (column widening) Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓  {test.__name__}")
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
