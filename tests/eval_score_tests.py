"""Tests for the eval runner's and scorer's mechanical parts (`scripts/eval_run.py`,
`scripts/eval_score.py`).

A suite's `tasks.md` splits into an intro and `## <id>` tasks, maintainers' comments
left out. A reply wrapped whole in a fence is unwrapped. Fidelity reads numbers as
shown — a number keeps a data value when the data rounds to it at the precision it
shows, at any thousands scale, signs aside — and counts the shown numbers no data
value rounds to. A task's URLs are counted as pictures, links or unused. An answer's
name gives its task and trial.

Run with: uv run python scripts/run_tests.py
"""

import sys
from pathlib import Path, PureWindowsPath

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import eval_run  # noqa: E402
import eval_score  # noqa: E402


def test_tasks_split_on_their_ids_without_comments():
    intro, tasks = eval_run.split_tasks(
        "# Suite\n\nAnswer each.\n<!-- for maintainers -->\n\n"
        '## t1-events\n"How?" Data: 345.\n\n## t2-place\nOpen now.\n'
    )
    assert intro == "# Suite\n\nAnswer each.", intro
    assert list(tasks) == ["t1-events", "t2-place"], tasks
    assert tasks["t1-events"] == '## t1-events\n"How?" Data: 345.', tasks
    assert "maintainers" not in intro


def test_a_fenced_reply_is_unwrapped():
    assert eval_run.unwrap("```markdown\n## A\n\nb\n```\n") == "## A\n\nb\n"
    assert eval_run.unwrap("## A\n```\ncode\n```") == "## A\n```\ncode\n```\n"


def test_numbers_read_as_shown():
    shown = eval_score.numbers("$274.5B, −0.741%, 1,798 and 256k; step 3")
    assert [(n.value, n.slack) for n in shown] == [
        (274.5e9, 0.05e9),
        (0.741, 0.0005),
        (1798.0, 0.5),
        (256e3, 500.0),
    ], shown


def test_urls_hold_no_numbers():
    assert (
        eval_score.numbers("[x](https://a.co/track/2026) ![](agent:trend?range=12)")
        == []
    )


def test_a_rounded_value_is_kept():
    data = "sales 274,515,000,000; close 0.972%"
    kept, untraced = eval_score.fidelity(data, "Sales $274.5B, up 0.97%")
    assert (kept, untraced) == (1.0, 0), (kept, untraced)


def test_a_header_unit_is_implied():
    kept, untraced = eval_score.fidelity(
        "sales 416,161,000,000", "| $B |\n|---|\n| 416.2 |"
    )
    assert (kept, untraced) == (1.0, 0), (kept, untraced)


def test_a_number_from_nowhere_is_untraced():
    kept, untraced = eval_score.fidelity(
        "high 24, low 13", "High 24, low 13, feels like 31"
    )
    assert (kept, untraced) == (1.0, 1), (kept, untraced)


def test_a_dropped_value_is_not_kept():
    kept, _ = eval_score.fidelity("AAPL 341.27, MSFT 543.45", "AAPL 341.27")
    assert kept == 0.5, kept


def test_urls_by_use():
    data = "cover `https://i.co/a`, link `https://o.co/t`, cover `https://i.co/b`"
    answer = "![Cover](https://i.co/a) [Open](https://o.co/t)"
    assert eval_score.links(data, answer) == {"pictures": 1, "links": 1, "unused": 1}


def test_an_answer_names_its_task_and_trial():
    assert eval_score.trial_of(Path("c3-apple-revenue-r2.md")) == (
        "c3-apple-revenue",
        "2",
    )
    assert eval_score.trial_of(Path("c3-apple-revenue.md")) == ("c3-apple-revenue", "1")


def test_a_theme_outside_the_checkout_names_its_condition():
    # A project's theme lives in its own repository, outside the checkout.
    root = eval_run.ROOT
    assert eval_run.condition_of(root) == "root"
    assert eval_run.condition_of(root / "evals/emoji-roles/theme") == (
        "evals/emoji-roles/theme"
    )
    # Absolute on every platform: on Windows a path needs its drive to be.
    outside = Path(root.anchor) / "elsewhere" / "backend" / "md2ui_theme"
    assert eval_run.condition_of(outside) == outside.as_posix()
    # The scorer reads the folder back from the condition, inside or out.
    assert root / eval_run.condition_of(outside) == outside
    print("  ✓  a theme outside the checkout is named by its absolute path")


def test_a_condition_is_spelled_with_slashes_on_windows():
    saved = eval_run.ROOT
    eval_run.ROOT = PureWindowsPath("C:/repo")  # type: ignore[assignment]
    try:
        inside = eval_run.condition_of(PureWindowsPath("C:/repo/evals/x/theme"))
        outside = eval_run.condition_of(PureWindowsPath("D:/project/md2ui_theme"))
    finally:
        eval_run.ROOT = saved
    assert (inside, outside) == ("evals/x/theme", "D:/project/md2ui_theme")
    print("  ✓  a condition is spelled with / on Windows too")


TESTS = [
    test_a_theme_outside_the_checkout_names_its_condition,
    test_a_condition_is_spelled_with_slashes_on_windows,
    test_tasks_split_on_their_ids_without_comments,
    test_a_fenced_reply_is_unwrapped,
    test_numbers_read_as_shown,
    test_urls_hold_no_numbers,
    test_a_rounded_value_is_kept,
    test_a_header_unit_is_implied,
    test_a_number_from_nowhere_is_untraced,
    test_a_dropped_value_is_not_kept,
    test_urls_by_use,
    test_an_answer_names_its_task_and_trial,
]


if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"All {len(TESTS)} tests passed.")
