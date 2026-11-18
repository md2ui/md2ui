"""
Several lines on one axis: a run of ``- Key: a → b → c`` items.

The grouper stamps ``line_group`` on two or more consecutive list items, each a
chain that draws as a line, with the same number of points in one unit kind
(ADR-204). The keys name the series; a short line ending in ``(unit)`` right
above the run declares the unit of bare numbers for every row, as it does for a
bar chart, and a key may declare its own. A label on any line names that
position for all of them. A run draws whole or not at all: one line with a
different point count, or two labels for one position, keeps every line of the
run apart, and ``check`` says which. Chains written as plain lines and lines in
two units are separate lines by intent, and no note. The
generator draws the group as one leaf; the renderer puts the lines on one shared
axis under a legend of each name and its last value as written (with the
declared unit, as ``Value format`` shows it), wrapped between entries when they
do not fit the width. ``Group height`` under ``### Line Chart`` sizes the
shared area; unset, it is ``Height``. ``check`` reads the rows under the
run's declaration, the summary ``show`` returns names the lines, and ``mark``
never takes a series key: a line is no bar.

Run with: uv run python tests/line_group_tests.py
"""

import contextlib
import io
import sys
from pathlib import Path

import skia  # type: ignore[import-untyped]

sys.path.insert(0, str(Path(__file__).parent))

from datapoint_layout_tests import _ast, _generate, _props, _walk
from md2ui import check_charts, session
from md2ui.pipeline import grouper_charts
from md2ui.digest import digest, theme_at
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_line_chart import (
    _legend_rows,
    draw_line_chart,
    line_chart_height,
)
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import Theme, parse_theme
from md2ui.wire_bars import set_bar_markdown
from md2ui.wire_frames import FrameError

FUNDS = (
    "- SPY: $718.66 (Apr) → $756.48 → $767.87 (Now)\n"
    "- QQQ: $667.74 → $738.31 → $728.08\n"
    "- DIA: $496.65 → $510.78 → $513.86\n"
)
DECLARED = "Price (USD):\n- SPY: 718 → 756 → 767\n- DIA: 496 → 510 → 513\n"


def _groups(text: str) -> list:
    return [n for n in _walk(_ast(text)) if n.line_group]


def _line_theme() -> Theme:
    t = Theme()
    t.charts.line.enabled = True
    return t


# ---------------------------------------------------------------------------
# What draws several lines (grouper)
# ---------------------------------------------------------------------------


def test_a_list_of_chains_is_one_group():
    (group,) = _groups(FUNDS)
    data = group.line_data
    assert [s["name"] for s in data["series"]] == ["SPY", "QQQ", "DIA"]
    assert data["labels"] == ["Apr", None, "Now"], "a label names its position for all"
    assert [p["value"] for p in data["series"][2]["points"]] == [496.65, 510.78, 513.86]
    assert not any(n.datapoint_display for n in _walk(group)), "the rows' lines clear"


def test_a_declared_unit_carries_down_the_run():
    (group,) = _groups(DECLARED)
    assert len(group.line_data["series"]) == 2
    assert group.line_data["display_unit"] == "USD"
    assert not _groups(DECLARED.replace("Price (USD):", "Price:")), "bare numbers"


def test_what_stays_separate_lines():
    plain = FUNDS.replace("- ", "")
    assert not _groups(plain.replace("\n", "\n\n")), "plain lines, not list items"
    counts = FUNDS.replace(" → $510.78", "")
    assert not _groups(counts.split("\n", 1)[1] + "- X: $1 → $2\n")
    clash = FUNDS.replace("$738.31", "$738.31 (May)").replace(
        "$756.48", "$756.48 (Jun)"
    )
    assert not _groups(clash), "two labels for one position"
    mixed = "- A: 10% → 20% → 30%\n- B: $1 → $2 → $3\n"
    assert not _groups(mixed), "two units"
    assert not _groups("- SPY: $1 → $2 → $3\n"), "one line is a line"


# ---------------------------------------------------------------------------
# Layout (generator)
# ---------------------------------------------------------------------------


def test_a_run_draws_whole_or_not_at_all():
    short = FUNDS.replace("$756.48 →", "$756.48 → $760.00 →")
    assert not _groups(short), "one line a point longer keeps every line apart"
    ((_, _, rows),) = [
        run for n in _walk(_ast(short)) for run in grouper_charts._line_runs(n)
    ]
    assert grouper_charts.line_run_failure(rows) == grouper_charts.LINES_COUNT
    two = "- High (°C): 27 → 26 → 27\n- Wind (km/h): 15 → 6 → 6\n"
    assert not _groups(two), "two declared units are two axes"
    (group,) = _groups("- High (°C): 27 → 26 → 27\n- Low (°C): 16 → 15 → 15\n")
    assert group.line_data["display_unit"] == "°C", "a unit each key declares"


def test_beside_bar_charts():
    header = "SPY, QQQ:\n- SPY: $1 → $2 → $3\n- QQQ: $4 → $5 → $6\n"
    ast = _ast(header)
    assert len(_groups(header)) == 1, "a comma line is no series header for lines"
    assert not any(n.chart_group for n in _walk(ast))
    mixed = (
        "- A: $1 → $2 → $3\n- B: $4 → $5 → $6\n- CPU: 40%\n- RAM: 50%\n- Swap: 60%\n"
    )
    ast = _ast(mixed)
    assert sum(n.line_group for n in _walk(ast)) == 1
    assert sum(n.chart_group for n in _walk(ast)) == 1, "the bar rows stay a chart"


def test_the_group_is_one_drawn_leaf():
    lines = _props(_generate(FUNDS, _line_theme()), "line_chart")
    assert len(lines) == 1
    _, data = lines[0]
    assert len(data["series"]) == 3
    # With no theme it draws the same, as every display does.
    assert len(_props(_generate(FUNDS, Theme()), "line_chart")) == 1


# ---------------------------------------------------------------------------
# Drawing (renderer)
# ---------------------------------------------------------------------------


def _fonts() -> FontSet:
    face = skia.Typeface.MakeDefault()
    return FontSet(face, face, face, face, face)


def test_group_height_sizes_several_lines():
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write("## Charts\n### Line Chart\nHeight: 40\nGroup height: 120\n")
    t = parse_theme(Path(f.name))
    assert t.charts.line.group_height == 120.0
    assert Theme().charts.line.group_height is None, "unset: Height"
    (group,) = _groups(FUNDS)
    single = {"points": group.line_data["series"][0]["points"]}
    fonts = _fonts()
    grown = line_chart_height(group.line_data, 800.0, fonts, t)
    assert grown - line_chart_height(single, 800.0, fonts, t) > 80.0
    t.charts.line.group_height = None
    same = line_chart_height(group.line_data, 800.0, fonts, t)
    assert abs(grown - same - 80.0) < 1e-6, "Group height replaces Height for a group"


def test_lines_paint_at_every_width():
    doc = "SPY: $1 → $3 → $2\n\n" + FUNDS
    wide = _props(_generate(doc, _line_theme(), 1280.0), "line_chart")
    narrow = _props(_generate(doc, _line_theme(), 320.0), "line_chart")
    assert len(wide) == len(narrow) == 2, "a narrow page keeps every line"
    t, fonts = _line_theme(), _fonts()
    (group,) = _groups(FUNDS)
    h = int(line_chart_height(group.line_data, 24.0, fonts, t)) + 1
    surface = skia.Surface(24, h)
    surface.getCanvas().clear(skia.ColorWHITE)
    box = LayoutBox(x=0.0, y=0.0, width=24.0, height=float(h))
    draw_line_chart(surface.getCanvas(), box, group.line_data, fonts, t)
    rgba = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    assert (rgba[..., :3] != 255).any(), "a 24 px box still draws its lines"


def test_the_legend_shows_the_declared_unit():
    (group,) = _groups(DECLARED)
    t, fonts = _line_theme(), _fonts()
    t.charts.value_format = "1 unit"
    labels = [
        e[1] for row in _legend_rows(group.line_data, 800.0, fonts, t) for e in row
    ]
    assert labels == ["SPY  767 USD", "DIA  513 USD"], labels


def test_the_legend_wraps_between_entries():
    (group,) = _groups(FUNDS)
    data, t, fonts = group.line_data, _line_theme(), _fonts()
    assert len(_legend_rows(data, 800.0, fonts, t)) == 1
    narrow = _legend_rows(data, 120.0, fonts, t)
    assert [len(r) for r in narrow] == [1, 1, 1], "one entry a row, never split"
    assert all(r[0][2] == 0.0 for r in narrow), "each row starts at the left"
    wide_h = line_chart_height(data, 800.0, fonts, t)
    assert line_chart_height(data, 120.0, fonts, t) > wide_h, "rows add height"
    single = {"points": data["series"][0]["points"]}
    assert _legend_rows(single, 800.0, fonts, t) == [], "a single line has none"


# ---------------------------------------------------------------------------
# What reads the flag: check, the digest, mark
# ---------------------------------------------------------------------------


def test_check_reads_the_rows_under_the_declaration():
    ast = _ast(DECLARED)
    assert not check_charts.lines_left_text(ast)
    assert not check_charts.rows_left_out(ast)
    assert not check_charts.lines_apart(ast)


def test_check_says_why_lines_draw_apart():
    longer = FUNDS.replace("$756.48 →", "$756.48 → $760.00 →")
    ((first, last, advice),) = check_charts.lines_apart(_ast(longer))
    assert first.startswith("SPY: $718.66 (Apr)"), first
    assert last == "DIA: $496.65 → $510.78 → $513.86", last
    assert "same number of points" in advice
    clash = FUNDS.replace("$667.74", "$667.74 (April)")
    ((_, _, advice),) = check_charts.lines_apart(_ast(clash))
    assert "Label each position once" in advice
    plain = "- SPY: $1 → $2 → $3\n\nText.\n\n- QQQ: $1 → $2\n"
    assert not check_charts.lines_apart(_ast(plain)), "lines apart by intent"


_MODELS = None


def _kit():
    global _MODELS
    with contextlib.redirect_stdout(io.StringIO()):
        if _MODELS is None:
            _MODELS = session.load_grouping_kit()
    return _MODELS


def test_the_digest_names_the_lines():
    theme = theme_at(Path(__file__).parent.parent / "data/markdown/tests/THEME.md")
    with contextlib.redirect_stdout(io.StringIO()):
        said = digest(session.group_markdown("## F\n\n" + FUNDS, _kit()), theme)
    assert said == 'F: chart of 3 lines ("SPY", "QQQ", "DIA"; 3 points, Apr → Now)', (
        said
    )


def test_mark_never_takes_a_series_key():
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            set_bar_markdown(FUNDS, "SPY", 50, _kit())
    except FrameError as exc:
        assert exc.code == "bad_target", exc
        return
    raise AssertionError("a series key was taken as a bar")


TESTS = [
    test_a_list_of_chains_is_one_group,
    test_a_declared_unit_carries_down_the_run,
    test_what_stays_separate_lines,
    test_a_run_draws_whole_or_not_at_all,
    test_beside_bar_charts,
    test_the_group_is_one_drawn_leaf,
    test_group_height_sizes_several_lines,
    test_lines_paint_at_every_width,
    test_the_legend_shows_the_declared_unit,
    test_the_legend_wraps_between_entries,
    test_check_reads_the_rows_under_the_declaration,
    test_check_says_why_lines_draw_apart,
    test_the_digest_names_the_lines,
    test_mark_never_takes_a_series_key,
]


if __name__ == "__main__":
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓  {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ✗  {test.__name__}: {exc!r}")
    sys.exit(1 if failed else 0)
