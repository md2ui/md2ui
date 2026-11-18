"""Unit tests for generator-side datapoint display construction."""

from dataclasses import FrozenInstanceError

from md2ui.pipeline import generator_displays
from md2ui.pipeline.markdown_grouper import MarkdownGroupNode, NodeType
from md2ui.pipeline.theme import Theme


def _context(theme: Theme | None = None) -> generator_displays.GeneratorContext:
    return generator_displays.GeneratorContext(theme, None, None)


def test_context_is_frozen():
    ctx = _context()
    try:
        setattr(ctx, "theme", Theme())
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("GeneratorContext must be frozen")
    print("  ✓  the generator display context is immutable")


def test_display_family_is_gated_by_theme():
    node = MarkdownGroupNode(type=NodeType.DATAPOINT, content="50%")
    node.datapoint_display = "ratio_bar"
    assert not generator_displays._dp_display_enabled(_context(), node)

    theme = Theme()
    theme.datapoints.ratio_bar.enabled = True
    assert generator_displays._dp_display_enabled(_context(theme), node)
    print("  ✓  datapoint display families remain gated by the theme")


def test_chart_build_keeps_payload_and_identity():
    node = MarkdownGroupNode(type=NodeType.GROUP, content="")
    node.node_id = "chart-1"
    node.chart_data = {"kind": "bar", "values": [1, 2]}
    built = generator_displays._build_chart(_context(), node)
    assert built.content_id == "chart-1"
    assert built.render_properties == {"chart": node.chart_data}
    print("  ✓  chart construction preserves its payload and content id")


TESTS = [
    test_context_is_frozen,
    test_display_family_is_gated_by_theme,
    test_chart_build_keeps_payload_and_identity,
]
