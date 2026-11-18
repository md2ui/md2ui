"""
Unit tests for the digest ``show`` returns: how a page grouped, in a few lines.

Pinned here:

  * one line per section, named by its heading; a text beside the heading is its
    caption;
  * a repeated run collapses to a count of its shape with its first member
    quoted — a key–value item by its key and the start of its value;
  * a table gives its size, rows by columns, header aside;
  * buttons are only counted, never named;
  * a run of titled cards is one run, not as many sections;
  * a line after the last subsection is no longer that heading's, and takes a
    line of its own;
  * a value the theme draws is named by what it draws as — a bar, a ring, a day
    chip, a chart of its rows — and one the theme leaves as text is not;
  * a line gives its point count and its two ends, value and label, so a point
    left out shows; several lines give their names (the first four), their
    point count and the labels at the ends; a chart under its `(unit)` line is
    named, not folded into a card;
  * a label and its value draw as one unit and read as one pair, quoted
    label → value: a `label : value` column, or a muted `_label_` line over its
    value, a chip included, also when the two are tight to their heading and so
    in its section, unglued; a value over a muted line (as often a title over its
    subtitle), two lines of prose and three glued lines are still listed;
  * a quote keeps a chip or an emphasis whole: markers come off its ends only
    when one run wraps the whole text, so a heading ending in a chip keeps both
    its backticks;
  * no tree, no digest.

Run with: uv run python tests/digest_tests.py
"""

import contextlib
import dataclasses
import io
import sys
from pathlib import Path

from md2ui import session
from md2ui.digest import digest, theme_at

_MODELS = None


_THEME = Path(__file__).parent.parent / "data/markdown/tests/THEME.md"


def _digest(markdown: str, theme=None) -> str:
    global _MODELS
    with contextlib.redirect_stdout(io.StringIO()):
        if _MODELS is None:
            _MODELS = session.load_grouping_kit()
        return digest(session.group_markdown(markdown, _MODELS), theme)


def test_a_section_names_its_run_and_counts_its_buttons():
    doc = (
        "# Status\n\n## Last commits\n_on main_\n\n"
        "- Batch 22 closed: a picture slot keeps max_height and never votes\n"
        "- Batch 21 closed: a lone spring no longer ends the run\n"
        "- Batch 20 closed: five findings deleted\n\n"
        "[Plan](agent:plan) *[Check](agent:check)*\n"
    )
    assert _digest(doc) == ("Last commits: caption · 3 list items · 2 buttons"), (
        _digest(doc)
    )
    print(
        "  ✓  digest: a section is named, its run counted and quoted, buttons counted"
    )


def test_a_table_gives_its_size():
    doc = "## Findings\n\n| Finding | Type |\n|---|---|\n| A | code |\n| B | skills |\n"
    doc += "| C | code |\n"
    assert _digest(doc) == "Findings: table 3×2", _digest(doc)
    print("  ✓  digest: a table is its rows by its columns")


def test_titled_cards_are_one_run_and_a_trailing_row_its_own_line():
    card = "[\n### {0}\nShips in {1} days\n`Free`\n](agent:choose?o={0})\n\n"
    doc = "## Pick one\n\n" + "".join(
        card.format(n, d) for n, d in (("A", 3), ("B", 1))
    )
    assert _digest(doc) == 'Pick one: 2 tappable cards ("A")', _digest(doc)
    trailing = "# Page\n\n## One\n\nText here.\n\n***\n\n[A](agent:a) [B](agent:b)\n"
    lines = _digest(trailing).splitlines()
    assert lines[-1] == "row: 2 buttons", lines
    print(
        "  ✓  digest: titled cards are one run; a row after the sections stands alone"
    )


def test_a_drawn_value_is_named_by_what_it_draws_as():
    theme = theme_at(_THEME)
    drawn = {
        "## P\n\nElapsed: 45%\n": 'P: bar ("Elapsed" → "45%")',
        "## S\n\nDisk: 61/128 GB\n": 'S: ring ("Disk" → "61/128 GB")',
        "## D\n\nMon-15\n": 'D: day chip ("Mon 15")',
        "## C\n\n- Tech: 12%\n- Energy: 9%\n- Retail: 4%\n": (
            'C: chart of 3 rows ("Tech" → "12%")'
        ),
        "## L\n\nSPY: $710.14 (Apr 13) → $713.94 → $777.24 (Now)\n": (
            'L: line chart ("SPY", 3 points, $710.14 (Apr 13) → $777.24 (Now))'
        ),
        "## F\n\n- SPY: $1 (Apr) → $2 → $3 (Jun)\n- QQQ: $4 → $5 → $6\n": (
            'F: chart of 2 lines ("SPY", "QQQ"; 3 points, Apr → Jun)'
        ),
        "## M\n\n" + "".join(f"- S{n}: 1% → 2% → 3%\n" for n in range(6)): (
            'M: chart of 6 lines ("S0", "S1", "S2", "S3", …; 3 points)'
        ),
        "## U\n\nStorage (GB):\n- Photos: 61\n- Backups: 128\n- Mail: 4\n": (
            'U: text ("Storage (GB):") · chart of 3 rows ("Photos" → "61")'
        ),
        "## W\n\nBest week: wk of Aug 3, +3.51%\n": ('W: text ("Best week: wk of…")'),
    }
    for doc, said in drawn.items():
        assert _digest(doc, theme) == said, (_digest(doc, theme), said)
    # The grouper flags the bar either way; a theme that turns bars off draws text.
    off = dataclasses.replace(
        theme.datapoints,
        kv_bar=dataclasses.replace(theme.datapoints.kv_bar, enabled=False),
    )
    text = dataclasses.replace(theme, datapoints=off)
    said = _digest("## P\n\nElapsed: 45%\n", text)
    assert said == 'P: key–value item ("Elapsed" → "45%")', said
    print(
        "  ✓  digest: a drawn value is a bar, ring, chip, chart or line; text stays text"
    )


def test_a_label_over_its_value_is_one_pair():
    doc = (
        "## Tests\n_Coverage_ : 82%\n\n_Failing_\n3\n\n*[Rerun tests](agent:rerun)*\n\n"
        "## Monitoring\n_Error rate_ : 0.4%\n\n_p95 latency_ : 210 ms\n\n"
        "*[Open alerts](agent:open-alerts)*\n"
    )
    assert _digest(doc).splitlines() == [
        'Tests: pair ("Coverage" → "82%") · pair ("Failing" → "3") · button',
        'Monitoring: pair ("Error rate" → "0.4%") · pair ("p95 latency" → "210 ms")'
        " · button",
    ], _digest(doc)
    chip = "## Build\n\nIntro.\n\n_Status_\n`Passed`\n\nA\nB\nC\n"
    said = _digest(chip)
    assert (
        said == 'Build: text ("Intro.") · pair ("Status" → "Passed") · 3 texts ("A")'
    ), said
    # Tight to its heading the pair stays in the heading's section, unglued.
    tight = "## Build\n_Status_\n`Passed`\n"
    assert _digest(tight) == 'Build: pair ("Status" → "Passed")', _digest(tight)
    others = {
        "## Build\n_Status_\n`Passed`\nShipped.\n": (
            'Build: text ("Status") · chip · text ("Shipped.")'
        ),
        "## Done\n450\n_Projects done_\n": 'Done: 2 texts ("450")',
        # Blank lines part them, though the section collapsed them in.
        "### News\n\n_Market Wire_\n\nShares slipped.\n": 'News: 2 texts ("Market Wire")',
        "## Done\n\nIntro.\n\n450\n_Projects done_\n": (
            'Done: text ("Intro.") · 2 texts ("450")'
        ),
        "## Prose\n\nIntro.\n\nFirst line of prose.\nSecond line of prose.\n": (
            'Prose: text ("Intro.") · 2 texts ("First line of prose.")'
        ),
    }
    for doc, want in others.items():
        assert _digest(doc) == want, (_digest(doc), want)
    print(
        "  ✓  digest: a muted label over its value is one pair; a value over it,"
        " prose lines and three lines stay listed"
    )


def test_a_quote_trims_only_a_whole_wrap():
    said = {
        "# Release `Sample data`\n\nSome words.": (
            'Release `Sample data`: text ("Some words.")'
        ),
        "Para ending `chip`": 'page: text ("Para ending `chip`")',
        "**Note:** rest of it": 'page: text ("**Note:** rest of it")',
        "**Note**": 'page: text ("Note")',
    }
    for doc, want in said.items():
        assert _digest(doc) == want, (_digest(doc), want)
    print("  ✓  digest: a chip or emphasis at a quote's end keeps both its markers")


def test_no_tree_no_digest():
    assert digest(None) == ""
    print("  ✓  digest: nothing grouped, nothing said")


TESTS = [
    test_a_section_names_its_run_and_counts_its_buttons,
    test_a_table_gives_its_size,
    test_titled_cards_are_one_run_and_a_trailing_row_its_own_line,
    test_a_drawn_value_is_named_by_what_it_draws_as,
    test_a_label_over_its_value_is_one_pair,
    test_a_quote_trims_only_a_whole_wrap,
    test_no_tree_no_digest,
]

if __name__ == "__main__":
    print("Digest Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    sys.exit(1 if failed else 0)
