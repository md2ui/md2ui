"""
Unit tests for the element card: laid out, never painted.

A glued-content group is wrapped as a card, and ``### Elements`` decides how it
is laid out — its padding and the gaps between and inside cards. It paints
nothing: a box comes from a heading style, so the parser
reads no fill, outline, radius, shadow or colour rotation from that block, and
no level can switch the card on or off.

Run with: uv run python scripts/run_tests.py
"""

import tempfile
from pathlib import Path

from md2ui.pipeline.theme import Theme, parse_theme

_ELEMENTS = """## Styling & Spacing

### Elements
Padding: 12
Row spacing: 6
Col spacing: 4
Group spacing: 20
Background color: #FFFFFF
Background gradient:
- Type: Linear
- Colors:
  - #00000000
  - #000000FF
Corner radius: 16
Stroke width: 1
Stroke color: #222222
Outer shadow:
- Radius: 8
- Color: #00000040
Rotate colors: yes

### Heading 2
Background color: #EEEEEE
"""


def _theme(text: str) -> Theme:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "THEME.md"
        path.write_text(text)
        return parse_theme(path)


def test_elements_keep_their_layout_keys():
    el = _theme(_ELEMENTS).elements
    assert el.padding.top == 12.0 and el.padding.left == 12.0
    assert (el.row_spacing, el.col_spacing) == (6.0, 4.0)
    assert (el.group_row_spacing, el.group_col_spacing) == (20.0, 20.0)
    print("  ✓  padding and every spacing key are read on ### Elements")


def test_elements_read_no_paint():
    el = _theme(_ELEMENTS).elements
    assert el.bg_colors == [] and el.gradient is None and el.bg_image is None
    assert el.corner_radius == 0.0 and el.stroke_width == 0.0
    assert el.stroke_color is None and el.shadows == []
    assert el.rotate == {}
    print("  ✓  no fill, gradient, radius, stroke, shadow or rotation on a card")


def test_a_heading_level_still_paints():
    """The paint keys are dropped on ### Elements only, not everywhere."""
    theme = _theme(_ELEMENTS)
    assert theme.sections[2].bg_colors == [0xFFEEEEEE]
    print("  ✓  the block after ### Elements reads its paint as before")


TESTS = [
    test_elements_keep_their_layout_keys,
    test_elements_read_no_paint,
    test_a_heading_level_still_paints,
]
