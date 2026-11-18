"""
Unit tests for the ## Drawing elements (alias: Datapoints) and ## Charts blocks
(DatapointsTheme / ChartsTheme parsing in theme.py).

Run with: uv run tests/datapoint_theme_tests.py
"""

import tempfile
from pathlib import Path

from md2ui.pipeline.theme import Theme, parse_theme, tier_style

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(text: str) -> Theme:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(text)
        path = Path(f.name)
    try:
        return parse_theme(path)
    finally:
        path.unlink()


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_defaults_when_sections_absent():
    t = _parse("# Empty theme\n")
    dp, ct = t.datapoints, t.charts
    assert dp.ratio_bar.enabled and dp.kv_bar.enabled
    assert dp.unit_ratio_enabled and dp.date_chip.enabled
    assert ct.enabled
    assert dp.unit_ratio_style == "bar"
    assert dp.unit_ratio_show_total and dp.unit_ratio_show_key
    assert dp.kv_bar.show_key and dp.kv_bar.show_value
    assert dp.ratio_bar.position == "below"
    assert dp.ratio_bar.text_side == "right"
    assert ct.mode == "bar"
    assert dp.ring.value_text is None and ct.label_text is None
    assert not dp.ratio_bar.bar.bg_colors


def test_per_family_disable():
    t = _parse(
        """
## Datapoints
### Ratio Bars
Enabled: no
### Key Value Bars
Enabled: no
### Unit Ratios
Enabled: no
### Dates
Enabled: no
### Emphasis
Enabled: no

## Charts
Enabled: no
"""
    )
    dp, ct = t.datapoints, t.charts
    assert not dp.ratio_bar.enabled
    assert not dp.kv_bar.enabled
    assert not dp.unit_ratio_enabled
    assert not dp.date_chip.enabled
    assert not ct.enabled


# ---------------------------------------------------------------------------
# Bars
# ---------------------------------------------------------------------------


def test_bar_styles():
    t = _parse(
        """
## Datapoints
### Ratio Bars
Thickness: 12
Text side: left
Corner radius: 4
Background color: #112233
Stroke width: 1
Stroke color: #445566
### Ratio Bar Track
Enabled: no
Background color: #EEEEEE
Padding: 3
### Key Value Bars
Position: above
Show key: no
Show value: no
Negative color: #B4B4BB
"""
    )
    bar = t.datapoints.ratio_bar
    assert bar.thickness == 12.0
    assert bar.text_side == "left"
    assert bar.bar.corner_radius == 4.0
    assert bar.bar.bg_colors == [0xFF112233]
    assert bar.bar.stroke_width == 1.0
    assert bar.bar.stroke_color == 0xFF445566
    assert bar.track.bg_colors == [0xFFEEEEEE]
    assert bar.track.padding.top == 3.0
    assert not bar.track_enabled
    assert t.datapoints.kv_bar.position == "above"
    assert not t.datapoints.kv_bar.show_key
    assert not t.datapoints.kv_bar.show_value
    assert t.datapoints.kv_bar.negative_color == 0xFFB4B4BB
    assert bar.negative_color is None


def test_bar_gradient():
    t = _parse(
        """
## Datapoints
### Ratio Bars
Background gradient:
- Colors:
  - #FF0000
  - #00FF00
- Ratios:
  - 0.0
  - 1.0
"""
    )
    g = t.datapoints.ratio_bar.bar.gradient
    assert g is not None
    assert g.colors == [0xFFFF0000, 0xFF00FF00]
    assert g.ratios == [0.0, 1.0]


def test_invalid_enums_keep_defaults():
    t = _parse(
        """
## Datapoints
### Ratio Bars
Text side: middle
### Key Value Bars
Position: sideways
### Unit Ratios
Style: sparkline

## Charts
Mode: scatter
"""
    )
    assert t.datapoints.ratio_bar.text_side == "right"
    assert t.datapoints.kv_bar.position == "below"
    assert t.datapoints.unit_ratio_style == "bar"
    assert t.charts.mode == "bar"


def test_unit_ratio_text_visibility():
    t = _parse(
        """
## Datapoints
### Unit Ratios
Show total: no
Show key: no
"""
    )
    assert not t.datapoints.unit_ratio_show_total
    assert not t.datapoints.unit_ratio_show_key


# ---------------------------------------------------------------------------
# Ring / dates / key-value styles
# ---------------------------------------------------------------------------


def test_ring_styles():
    t = _parse(
        """
## Datapoints
### Unit Ratios
Style: ring
### Ring
Thickness: 16
Diameter: 120
Background color: #5B4FC4
- Font size: 30
- Font weight: bold
### Ring Unit
- Font size: 10
- Font color: #999999
### Ring Track
Background color: #DDDDDD
"""
    )
    dp = t.datapoints
    assert dp.unit_ratio_style == "ring"
    assert dp.ring.thickness == 16.0
    assert dp.ring.diameter == 120.0
    assert dp.ring.ring.bg_colors == [0xFF5B4FC4]
    assert dp.ring.value_text is not None
    assert dp.ring.value_text.font_size == 30.0
    assert dp.ring.value_text.font_weight == "bold"
    assert dp.ring.unit_text is not None
    assert dp.ring.unit_text.font_size == 10.0
    assert dp.ring.track.bg_colors == [0xFFDDDDDD]


def test_date_chip_styles():
    t = _parse(
        """
## Datapoints
### Dates
Background color: #FBEFFB
Corner radius: 14
Padding: 10
### Date Key
Background color: #EEDDEE
Corner radius: 6
- Font size: 11
- Font color: #8A87A0
### Date Day
- Font size: 22
- Font weight: bold
"""
    )
    chip = t.datapoints.date_chip
    assert chip.fill == "single"  # default
    assert chip.chip.bg_colors == [0xFFFBEFFB]
    assert chip.chip.corner_radius == 14.0
    assert chip.chip.padding.left == 10.0
    assert chip.key_bg.bg_colors == [0xFFEEDDEE]
    assert chip.key_bg.corner_radius == 6.0
    assert chip.key_text is not None and chip.key_text.font_size == 11.0
    assert chip.day_text is not None
    assert chip.day_text.font_size == 22.0
    assert chip.day_text.font_weight == "bold"


def test_date_chip_fill_split():
    t = _parse(
        """
## Datapoints
### Dates
Fill: split
### Date Key
Background color: #E4C9F0
### Date Day
Background color: #FBEFFB
"""
    )
    chip = t.datapoints.date_chip
    assert chip.fill == "split"
    assert chip.key_bg.bg_colors == [0xFFE4C9F0]
    assert chip.day_bg.bg_colors == [0xFFFBEFFB]


def test_date_chip_fill_invalid_keeps_default():
    t = _parse("## Datapoints\n### Dates\nFill: diagonal\n")
    assert t.datapoints.date_chip.fill == "single"


def test_date_chip_spacing():
    assert Theme().datapoints.date_chip.spacing == 0.0  # default
    t = _parse("## Datapoints\n### Dates\nSpacing: 6\n")
    assert t.datapoints.date_chip.spacing == 6.0


def test_ring_spacing():
    assert Theme().datapoints.ring.spacing == 0.0  # default
    t = _parse("## Datapoints\n### Ring\nSpacing: 4\nDiameter: 130\n")
    assert t.datapoints.ring.spacing == 4.0
    assert t.datapoints.ring.diameter == 130.0


def test_key_value_styles():
    t = _parse(
        """
## Text Styles
Value
- Font size: 28
- Font weight: bold
- Marker background color: #FFF3CD
Key
- Font size: 12
- Font color: #8A87A0
"""
    )
    assert t.value_style is not None and t.value_style.font_size == 28.0
    assert t.value_style.font_weight == "bold"
    assert t.value_style.marker_bg_color == 0xFFFFF3CD
    assert t.key_style is not None and t.key_style.color == 0xFF8A87A0
    assert tier_style("display", t).font_size != 28.0


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


def test_chart_styles():
    t = _parse(
        """
## Charts
Mode: line
Bar thickness: 20
Bar spacing: 10
Corner radius: 5
Background color: #123456
Negative color: #E5484D
### Chart Track
Enabled: no
Background color: #F0F0F0
Padding: 3
### Chart Series Colors
- #111111
- #222222
### Chart Grid
Line color: #ABCDEF
Line width: 2
### Chart Labels
- Font size: 10
### Chart Values
- Font weight: semibold
"""
    )
    ct = t.charts
    assert ct.mode == "line"  # parsed; renderer falls back to bars
    assert ct.bar_thickness == 20.0
    assert ct.bar_spacing == 10.0
    assert ct.bar.corner_radius == 5.0
    assert ct.bar.bg_colors == [0xFF123456]
    assert ct.negative_color == 0xFFE5484D
    assert (ct.grid.color, ct.grid.width) == (0xFFABCDEF, 2.0)
    assert ct.track.bg_colors == [0xFFF0F0F0]
    assert not ct.track_enabled and ct.track.padding.top == 3.0
    assert ct.series_colors == [0xFF111111, 0xFF222222]
    assert ct.label_text is not None and ct.label_text.font_size == 10.0
    assert ct.value_text is not None and ct.value_text.font_weight == "semibold"


def test_repo_theme_parses():
    t = parse_theme(Path("data/markdown/tests/THEME.md"))
    assert t.datapoints.ratio_bar.bar.bg_colors, "repo THEME.md ratio bar fill"
    assert t.charts.bar.bg_colors, "repo THEME.md chart bar fill"
    assert t.datapoints.unit_ratio_style in ("bar", "ring")


# ---------------------------------------------------------------------------

TESTS = [
    test_defaults_when_sections_absent,
    test_per_family_disable,
    test_bar_styles,
    test_bar_gradient,
    test_invalid_enums_keep_defaults,
    test_unit_ratio_text_visibility,
    test_ring_styles,
    test_date_chip_styles,
    test_date_chip_fill_split,
    test_date_chip_fill_invalid_keeps_default,
    test_date_chip_spacing,
    test_ring_spacing,
    test_key_value_styles,
    test_chart_styles,
    test_repo_theme_parses,
]

if __name__ == "__main__":
    print("Datapoint Theme Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓ {test.__name__}")
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} of {len(TESTS)} tests FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
