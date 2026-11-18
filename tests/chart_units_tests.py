"""
A chart value is a number; any other unit is declared (ADR-204).

A run of three or more ``- Key: value`` bullets charts when every value is the
value alone, in one kind: a percentage, a currency (`$220.06`, `200 EUR`), or
numbers with or without a magnitude (`5K`). A run holding a plain number charts
only under a line declaring its unit (`Temperature (°C):`) -- undeclared, plain
numbers are ports, years and versions. Every other unit (`61 GB`, `12 kg`) is
written bare and declared the same way; written inline it keeps the run a
list, and ``check`` says how to declare it. A word beside a value keeps the
row out, because the chart would drop it. A ring takes a declared unit too:
``Disk (GB): 61/128`` draws as ``Disk: 61/128 GB`` does. The
row's label and its value are drawn as the author wrote them, and tick labels
take the values' unit. ``Percent scale: peak`` lets a percentage chart compare
its rows instead of reading as progress against 100%. ``md2ui check`` notes a
row left out of the chart beside it, a run in mixed units, an arrow chain of
values that draws no line, and a ``(unit)`` or ``Name, Name:`` line that a
blank line keeps from the list it would chart. A unit is at most 32 characters and its
line at most six words; ``check`` names one that is not read over plain-number rows.

Run with: uv run tests/chart_units_tests.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from datapoint_layout_tests import _ast, _walk
from md2ui import check_charts
from md2ui.pipeline.render_chart import _chart_scale, _chart_tick_label
from md2ui.pipeline.value_format import declared_unit, with_unit


def _charts(text: str) -> list[dict]:
    return [n.chart_data or {} for n in _walk(_ast(text)) if n.chart_group]


SPEND = "- Groceries: $220.06\n- Subscriptions: $29.97\n- Shopping: $297.26\n"


def test_a_run_in_one_currency_charts_as_written():
    (chart,) = _charts(SPEND)
    assert chart["unit"] == "currency USD"
    assert [r["texts"] for r in chart["rows"]] == [["$220.06"], ["$29.97"], ["$297.26"]]


def test_magnitudes_chart_as_written():
    (chart,) = _charts("- A: 5K\n- B: 1.2K\n- C: 9K\n")
    assert chart["unit"] == "magnitude"


def test_sizes_and_measurements_are_declared_not_written():
    assert not _charts("- A: 61 GB\n- B: 64 GB\n- C: 70 GB\n")
    assert not _charts("- A: 12 kg\n- B: 14 kg\n- C: 9 kg\n")
    (chart,) = _charts("Storage (GB):\n- A: 61\n- B: 64\n- C: 70\n")
    assert chart["display_unit"] == "GB"


def test_check_says_how_to_declare_a_refused_unit():
    ast = _ast("- A: 61 GB\n- B: 64 GB\n- C: 70 GB\n")
    ((_, _, advice),) = check_charts.runs_without_chart(ast)
    assert "declare the unit" in advice and "`Storage (GB):`" in advice


def test_plain_numbers_and_magnitudes_are_one_kind_under_a_declared_unit():
    assert not _charts("- A: 900\n- B: 1.2K\n- C: 5K\n")
    (chart,) = _charts("Users (count):\n- A: 900\n- B: 1.2K\n- C: 5K\n")
    assert chart["unit"] == "" and chart["display_unit"] == "count"


def test_check_is_quiet_on_the_rows_of_a_declared_chart():
    ast = _ast("Followers (count):\n- Video: 12K\n- Photos: 4,800\n- Posts: 900K\n")
    assert (
        len(
            _charts(
                "Followers (count):\n- Video: 12K\n- Photos: 4,800\n- Posts: 900K\n"
            )
        )
        == 1
    )
    assert not check_charts.rows_left_out(ast)


def test_a_ring_takes_a_declared_unit():
    def rings(text: str) -> list[dict]:
        return [
            n.datapoint_payload or {}
            for n in _walk(_ast(text))
            if n.datapoint_display == "unit_ratio"
        ]

    ((declared,), (inline,)) = rings("Disk (GB): 61/128\n"), rings("Disk: 61/128 GB\n")
    assert (declared["value"], declared["max"], declared["unit"]) == (61.0, 128.0, "GB")
    assert declared == inline


def test_percentages_keep_their_spelling():
    (chart,) = _charts("- Mon: 2.10%\n- Tue: −1.55%\n- Wed: 40%\n")
    assert [r["texts"][0] for r in chart["rows"]] == ["2.10%", "−1.55%", "40%"]


def test_plain_numbers_chart_only_under_a_declared_unit():
    assert not _charts("- HTTP: 80\n- HTTPS: 443\n- SSH: 22\n")


def test_mixed_units_draw_no_chart():
    assert not _charts("- Food: $220\n- Rent: 900 EUR\n- Fun: $50\n")


def test_a_word_beside_a_value_keeps_the_row_out():
    text = "- Mon: 90%\n- Tue: 85%\n- Wed: 60% (holiday)\n- Thu: 12%\n- Fri: 30%\n- Sat: 5%\n"
    (chart,) = _charts(text)
    assert [r["label"] for r in chart["rows"]] == ["Thu", "Fri", "Sat"]


def test_tick_labels_take_the_values_unit():
    assert _chart_tick_label(50.0, "%") == "50%"
    assert _chart_tick_label(200.0, "currency USD", "$220.06") == "$200"
    assert _chart_tick_label(-5.0, "currency USD", "$220.06") == "-$5"
    assert _chart_tick_label(200.0, "currency EUR", "200 EUR") == "200 EUR"
    assert _chart_tick_label(5000.0, "magnitude", "5K") == "5K"
    assert _chart_tick_label(1500000.0, "currency USD", "$1.2M") == "$1.5M"
    assert _chart_tick_label(1200000.0, "currency USD", "$990") == "$1200000"


def test_percent_scale_peak_compares_the_rows():
    small = [[1.2], [2.4], [3.1]]
    assert _chart_scale(small, "%") == (0.0, 100.0), "progress by default"
    assert _chart_scale(small, "%", "peak") == (0.0, 3.1)
    assert _chart_scale([[220.0], [30.0]], "currency USD") == (0.0, 220.0)


def test_check_notes_a_row_left_out_of_a_chart():
    ast = _ast("- Mon: 90%\n- Tue: 85%\n- Wed: 60% (holiday)\n- Thu: 12%\n")
    ((row, _),) = check_charts.rows_left_out(ast)
    assert row == "Wed: 60% (holiday)"


def test_check_notes_a_header_a_blank_line_keeps_from_its_list():
    unit = "Volume (M shares):\n\n- NVDA: 90.3\n- INTC: 82.3\n- MU: 24.7\n"
    assert check_charts.headers_apart(_ast(unit)) == ["Volume (M shares)"]
    series = "Intro.\nSales, Net income:\n\n- FY20: $1B, $2B\n- FY21: $3B, $4B\n"
    assert check_charts.headers_apart(_ast(series)) == ["Sales, Net income"]
    lines = "Price (USD):\n\n- SPY: 718 → 756 → 767\n- DIA: 496 → 510 → 513\n"
    assert check_charts.headers_apart(_ast(lines)) == ["Price (USD)"]
    touching = unit.replace(":\n\n", ":\n")
    assert not check_charts.headers_apart(_ast(touching)), "it charts: no note"
    ports = "Ports (tcp):\n\n- HTTP: Apache\n- SSH: OpenSSH\n- FTP: none\n"
    assert not check_charts.headers_apart(_ast(ports)), "no chart either way"
    drawn = "Usage (%):\n\n- CPU: 40%\n- RAM: 70%\n- Swap: 20%\n"
    assert not check_charts.headers_apart(_ast(drawn)), "the list charts anyway"


def test_check_is_quiet_on_lists_that_never_meant_a_chart():
    ast = _ast("- HTTP: 80\n- HTTPS: 443\n- SSH: 22\n\nChange: $702 → $720\n")
    assert not check_charts.rows_left_out(ast)
    assert not check_charts.runs_without_chart(ast)
    assert not check_charts.lines_left_text(ast)


def test_check_notes_mixed_units_and_a_stalled_line():
    ast = _ast(
        "- Food: $220\n- Rent: 900 EUR\n- Fun: $50\n\n"
        "Revenue: $412M (49%) → $430M → $450M\n"
    )
    ((first, last, advice),) = check_charts.runs_without_chart(ast)
    assert (first, last) == ("Food: $220", "Fun: $50") and "one unit" in advice
    ((pair, advice),) = check_charts.lines_left_text(ast)
    assert pair.startswith("Revenue: $412M") and "label" in advice


def test_check_names_the_chart_units_when_a_value_is_in_none():
    ast = _ast(
        "- Wed: 24°\n- Thu: 22°\n- Fri: 20°\n\n"
        "High: 24° (Wed) → 23° (Thu) → 21° (Fri)\n"
    )
    ((first, last, advice),) = check_charts.runs_without_chart(ast)
    assert (first, last) == ("Wed: 24°", "Fri: 20°") and "no chart unit" in advice
    ((pair, line_advice),) = check_charts.lines_left_text(ast)
    # A line's unit goes in its key; "declare it above" serves only rows.
    assert pair.startswith("High: 24°") and "name the unit in the key" in line_advice
    assert line_advice.endswith("`High (°): 24 (Wed) → 23 (Thu) → 21 (Fri)`")
    assert not _charts("- Wed: 24°\n- Thu: 22°\n- Fri: 20°\n"), "° stays text"


def test_a_plus_sign_keeps_a_value_in_its_unit():
    (chart,) = _charts("- Apr: +9.90%\n- May: +5.26%\n- Jun: -1.28%\n")
    assert chart["unit"] == "%"
    assert [r["values"][0] for r in chart["rows"]] == [9.9, 5.26, -1.28]
    assert [r["texts"][0] for r in chart["rows"]] == ["+9.90%", "+5.26%", "-1.28%"]
    (money,) = _charts("- AAPL: +$0.30\n- MSFT: +$2.30\n- TSLA: -$2.80\n")
    assert money["unit"] == "currency USD"
    assert [r["values"][0] for r in money["rows"]] == [0.3, 2.3, -2.8]


def test_a_unit_is_declared_in_parentheses_without_digits():
    assert declared_unit("Temperature (°C)") == "°C"
    assert declared_unit("High, Low (°C):") == "°C"
    assert declared_unit("Heart rate (bpm)") == "bpm"
    assert declared_unit("Results (2025)") is None
    assert declared_unit("Temperature") is None


def test_value_format_places_the_declared_unit():
    assert with_unit("24", "°C", "1") == "24"
    assert with_unit("24", "°C", "1unit") == "24°C"
    assert with_unit("24", "°C", "1 unit") == "24 °C"
    assert with_unit("24", "$", "unit 1") == "$ 24"
    assert with_unit("24", None, "1 unit") == "24"


def test_a_declared_unit_lets_bare_numbers_chart():
    (chart,) = _charts("Temperature (°C):\n- Wed: 24\n- Thu: 23\n- Fri: 21\n")
    assert chart["display_unit"] == "°C" and chart["unit"] == ""
    assert [r["texts"][0] for r in chart["rows"]] == ["24", "23", "21"]
    texts = [
        n.content
        for n in _walk(_ast("Temperature (°C):\n- Wed: 24\n- Thu: 23\n- Fri: 21\n"))
    ]
    assert "Temperature (°C):" in texts, "the header stays as written"


def test_a_series_header_declares_the_unit_too():
    (chart,) = _charts("High, Low (°C):\n- Wed: 24, 13\n- Thu: 23, 13\n")
    assert chart["series"] == ["High", "Low"] and chart["display_unit"] == "°C"


def test_without_a_declaration_bare_numbers_stay_a_list():
    assert not _charts("Results (2025):\n- Wed: 24\n- Thu: 23\n- Fri: 21\n")
    assert not _charts("- Wed: 24\n- Thu: 23\n- Fri: 21\n")


def test_a_line_key_declares_its_unit():
    ast = _ast("High (°C): 24 (Wed) → 23 (Thu) → 21 (Fri)\n")
    (payload,) = [
        n.datapoint_payload or {}
        for n in _walk(ast)
        if n.datapoint_display == "line_chart"
    ]
    assert payload["display_unit"] == "°C"
    ast = _ast("Price ($): $710 → $713 → $720\n")
    (payload,) = [
        n.datapoint_payload or {}
        for n in _walk(ast)
        if n.datapoint_display == "line_chart"
    ]
    assert "display_unit" not in payload, "values that carry a unit keep their own"


def test_a_unit_in_words_declares_and_one_too_long_is_named():
    long = "Average daily volume (millions of shares):\n- Apple: 52\n- Microsoft: 21\n- Nvidia: 310\n"
    (chart,) = _charts(long)
    assert chart["display_unit"] == "millions of shares"
    assert check_charts.units_not_read(_ast(long)) == []
    too_long = (
        "Volume (millions of shares, rounded to the nearest whole):\n"
        "- Apple: 52\n- Microsoft: 21\n- Nvidia: 310\n"
    )
    assert not _charts(too_long)
    (only,) = check_charts.units_not_read(_ast(too_long))
    assert only[0].startswith("millions of shares") and "32 characters" in only[1]
    wordy = (
        "The average daily trading volume per company (millions of shares):\n"
        "- Apple: 52\n- Microsoft: 21\n- Nvidia: 310\n"
    )
    assert not _charts(wordy)
    assert "six words" in check_charts.units_not_read(_ast(wordy))[0][1]
    # A bracket over rows that already chart, or over no plain numbers, says nothing.
    assert (
        check_charts.units_not_read(
            _ast("Temperature (°C):\n- Wed: 24\n- Thu: 23\n- Fri: 21\n")
        )
        == []
    )
    assert (
        check_charts.units_not_read(_ast("A note (see below):\n- one\n- two\n")) == []
    )
    print(
        "  ✓  a unit in words declares, and one too long or on too long a line is named"
    )


TESTS = [
    test_a_unit_in_words_declares_and_one_too_long_is_named,
    test_a_run_in_one_currency_charts_as_written,
    test_magnitudes_chart_as_written,
    test_sizes_and_measurements_are_declared_not_written,
    test_check_says_how_to_declare_a_refused_unit,
    test_plain_numbers_and_magnitudes_are_one_kind_under_a_declared_unit,
    test_check_is_quiet_on_the_rows_of_a_declared_chart,
    test_a_ring_takes_a_declared_unit,
    test_percentages_keep_their_spelling,
    test_plain_numbers_chart_only_under_a_declared_unit,
    test_mixed_units_draw_no_chart,
    test_a_word_beside_a_value_keeps_the_row_out,
    test_tick_labels_take_the_values_unit,
    test_percent_scale_peak_compares_the_rows,
    test_check_notes_a_row_left_out_of_a_chart,
    test_check_notes_a_header_a_blank_line_keeps_from_its_list,
    test_check_is_quiet_on_lists_that_never_meant_a_chart,
    test_check_notes_mixed_units_and_a_stalled_line,
    test_check_names_the_chart_units_when_a_value_is_in_none,
    test_a_plus_sign_keeps_a_value_in_its_unit,
    test_a_unit_is_declared_in_parentheses_without_digits,
    test_value_format_places_the_declared_unit,
    test_a_declared_unit_lets_bare_numbers_chart,
    test_a_series_header_declares_the_unit_too,
    test_without_a_declaration_bare_numbers_stay_a_list,
    test_a_line_key_declares_its_unit,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
        print(f"  ✓ {t.__name__}")
    print(f"{len(TESTS)} passed")
