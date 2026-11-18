"""Unit tests for LayoutGenerator._balance_kind_cols (per-kind column balancing).

The shared count in `_kind_cols` serves EVERY run of a kind at once, so the
one-run fill rule (`_balance_cols`) cannot be applied to it directly: the runs
have different lengths and would each want a different count. `_balance_kind_cols`
is the per-kind vote that generalizes it — keep the fit-max unless at least
ORPHAN_RUN_SHARE of the kind's runs would end on an under-half row, then step
down to a count where NO run of the kind does.

The property that keeps the two honest is here as a test: for a kind with a
single run the vote returns exactly what `_balance_cols` returns, so nothing
about the original rule is re-decided by the generalization.
"""

import math

from md2ui.pipeline.layout_generator import (
    LayoutGenerator,
    MIN_LAST_ROW_FILL,
    ORPHAN_RUN_SHARE,
)

_bkc = LayoutGenerator._balance_kind_cols
_bc = LayoutGenerator._balance_cols


def _fill(cols: int, n: int) -> float:
    """Last-row fill of an n-item run at *cols* columns (a short run is full)."""
    if n <= cols:
        return 1.0
    rows = math.ceil(n / cols)
    return (n - (rows - 1) * cols) / cols


def test_single_run_is_the_original_rule():
    # The generalization contains _balance_cols: one run -> identical answer.
    for fit in range(1, 10):
        for n in range(1, 26):
            assert _bkc(fit, [n]) == _bc(fit, n), (fit, n)


def test_minority_orphan_keeps_the_count():
    # weather-report's kind: 4 of 13 runs (the n=4s and the n=7) end under-half
    # at 3 columns -- below the vote share, so the density stays.
    runs = [2, 2, 3, 3, 3, 3, 4, 4, 4, 5, 5, 6, 7]
    assert _bkc(3, runs) == 3


def test_majority_orphan_steps_down():
    # ai-summit's kind: 1 of 2 runs orphans at the fit-max 4 (5 -> 4+1), which
    # meets the share -> 3, where neither run orphans (3 | 3+2).
    assert _bkc(4, [3, 5]) == 3
    # A kind whose only run orphans is the single-run case: 5 -> 4+1 -> 3+2.
    assert _bkc(4, [5]) == 3
    # trending-amazon: both runs orphan at 3 (4 -> 3+1, 5 -> 3+2 is fine) -> 2.
    assert _bkc(3, [4, 5]) == 2


def test_short_runs_are_not_orphans():
    # A run shorter than the count is ONE ragged row, not an orphaned last row --
    # the same passthrough _balance_cols makes for n <= cols. A kind of nothing
    # but short runs is therefore already right at the fit-max...
    assert _bkc(4, [2, 2, 3]) == 4
    # ...and they dilute the vote rather than joining it: one orphan in four runs
    # is below a third, so the count stands.
    assert _bkc(4, [2, 3, 3, 5]) == 4


def test_orphan_singletons_are_ignored():
    # `orphan_grid` members arrive as runs of one; a lone card held at its
    # siblings' width is deliberate, so it neither orphans nor votes.
    assert _bkc(4, [1, 1, 1]) == 4
    assert _bkc(4, [1, 5]) == _bkc(4, [5])


def test_no_runs_is_a_passthrough():
    assert _bkc(4, []) == 4
    assert _bkc(1, []) == 1


def test_never_increases_the_count():
    # Balancing only ever lowers the fit-max (the content-min fit is the ceiling).
    for fit in range(1, 9):
        for a in range(1, 12):
            for b in range(1, 12):
                assert _bkc(fit, [a, b]) <= fit


def test_result_is_clean_or_the_floor():
    # Whatever it returns is either the untouched fit-max, a count where no run
    # of the kind orphans, or the floor of 2.
    for fit in range(3, 9):
        for a in range(2, 14):
            for b in range(2, 14):
                runs = [a, b]
                k = _bkc(fit, runs)
                assert 2 <= k <= fit
                if k in (fit, 2):
                    continue
                assert all(_fill(k, n) >= MIN_LAST_ROW_FILL for n in runs)


def test_share_gate_is_a_share_of_runs():
    # The gate counts RUNS, not cells, and fires at exactly the share (>=).
    # Written against the constant so tuning it retunes the test with it.
    assert 0.0 <= ORPHAN_RUN_SHARE <= 1.0
    if ORPHAN_RUN_SHARE <= 0.5:
        assert _bkc(4, [3, 5]) < 4  # 1 of 2 orphans at 4
    if ORPHAN_RUN_SHARE > 1 / 3:
        assert _bkc(4, [3, 3, 5]) == 4  # 1 of 3 is below the share


def test_a_third_catches_one_bad_run_in_three():
    # The shape the default is named for, and the reason it is written as a
    # fraction: three sections of one kind, 2 + 2 + 4 cards, fitting three
    # across. Only the run of four orphans (3+1), which is exactly a third of
    # the runs -- a rounded 0.34 would let it stand.
    if ORPHAN_RUN_SHARE <= 1 / 3:
        assert _bkc(3, [2, 2, 4]) == 2


def test_zero_share_is_any_run_not_every_count():
    # A share of 0 has to read as "step down when ANY run orphans", never as
    # "step down always" -- a count nothing orphans at is already the answer.
    assert _bkc(4, [4, 8]) == 4
    assert _bkc(6, [6, 12]) == 6


TESTS = [
    test_single_run_is_the_original_rule,
    test_minority_orphan_keeps_the_count,
    test_majority_orphan_steps_down,
    test_short_runs_are_not_orphans,
    test_orphan_singletons_are_ignored,
    test_no_runs_is_a_passthrough,
    test_never_increases_the_count,
    test_result_is_clean_or_the_floor,
    test_share_gate_is_a_share_of_runs,
    test_a_third_catches_one_bad_run_in_three,
    test_zero_share_is_any_run_not_every_count,
]

if __name__ == "__main__":
    print("Balance-Kind-Cols (per-kind grid column balancing) Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  ✗  {test.__name__}: {exc}")
    if failed:
        raise SystemExit(f"{failed} test(s) failed.")
    print(f"All {len(TESTS)} tests passed.")
