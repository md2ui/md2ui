"""Unit tests for LayoutGenerator._balance_cols (repeated-grid column balancing).

Pure arithmetic on (fit-max cols, run length) — no fonts, theme, or AST needed.
The rule: keep the fit-max column count unless its last (ragged) row fills less
than MIN_LAST_ROW_FILL (1/2); then step down to the count with the fewest rows
whose last row fills >= 1/2, tie-break most even then more columns; floor at 2.
"""

import math

from md2ui.pipeline.layout_generator import (
    LayoutGenerator,
    MIN_LAST_ROW_FILL,
)

_bc = LayoutGenerator._balance_cols


def _last_fill(cols: int, n: int) -> float:
    rows = math.ceil(n / cols)
    return (n - (rows - 1) * cols) / cols


def test_already_balanced_kept():
    # Last row already fills >= 1/2 -> untouched (soccer 6+4, mexican 3+3+2).
    assert _bc(6, 10) == 6  # 6+4, fill 4/6 = 0.67
    assert _bc(3, 8) == 3  # 3+3+2, fill 2/3 = 0.67
    assert _bc(3, 11) == 3  # 3+3+3+2, fill 2/3


def test_orphan_rebalanced_down():
    # Last row fills < 1/2 -> step down to fewest-rows acceptable, most even.
    assert _bc(5, 6) == 3  # 5+1 (0.20) -> 3+3
    assert _bc(4, 9) == 3  # 4+4+1 (0.25) -> 3+3+3
    assert _bc(3, 4) == 2  # 3+1 (0.33) -> 2+2
    assert _bc(3, 10) == 2  # 3+3+3+1 (0.33) -> 2+2+2+2+2 (only k=2 qualifies)


def test_prime_run_length():
    # n=7 prime, fit-max 6: 6+1 (0.17) -> among k in 2..5, fewest rows with
    # fill>=1/2 is k=4 (4+3, 2 rows, fill 0.75).
    assert _bc(6, 7) == 4
    # n=7, fit-max 5: 5+2 (0.40) < 1/2 -> k=4 (4+3) fewest rows.
    assert _bc(5, 7) == 4


def test_fewest_rows_then_most_even():
    # cols=5, n=6: k=4 (4+2, 2 rows, fill 0.5) and k=3 (3+3, 2 rows, fill 1.0)
    # both minimize rows; the more-even k=3 wins.
    assert _bc(5, 6) == 3


def test_low_cols_passthrough():
    # cols < 3 is never rebalanced: a 2-col lone last cell (1/2) is allowed.
    assert _bc(2, 5) == 2  # 2+2+1, fill 0.5
    assert _bc(2, 3) == 2  # 2+1
    assert _bc(1, 9) == 1


def test_single_full_row_passthrough():
    # n == cols: one full row, nothing ragged.
    assert _bc(4, 4) == 4
    assert _bc(6, 6) == 6


def test_never_increases_cols():
    # Balancing only ever lowers the count (content-min fit is the ceiling).
    for cols in range(1, 9):
        for n in range(cols, 20):
            assert _bc(cols, n) <= cols


def test_result_meets_fill_floor_or_is_two():
    # Every rebalanced result either clears the 1/2 fill floor or is the k=2 floor.
    for cols in range(3, 9):
        for n in range(cols + 1, 25):
            k = _bc(cols, n)
            assert 2 <= k <= cols
            assert k == 2 or _last_fill(k, n) >= MIN_LAST_ROW_FILL


TESTS = [
    test_already_balanced_kept,
    test_orphan_rebalanced_down,
    test_prime_run_length,
    test_fewest_rows_then_most_even,
    test_low_cols_passthrough,
    test_single_full_row_passthrough,
    test_never_increases_cols,
    test_result_meets_fill_floor_or_is_two,
]

if __name__ == "__main__":
    print("Balance-Cols (grid column balancing) Tests")
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
