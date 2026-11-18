"""
Unit tests for FIXED COLORS — colors that carry MEANING and so outrank both
rotation and replacement.

A ❤️ is red because red is what it means; a 📉 is amber because the number fell.
Rotation deals colors out, replacement fixes the ones that land badly, and a pin
is neither. The single exception is invisibility: a pin exactly equal to the
background behind it is dropped, so a red 🔻 on the red card a rotation just
dealt does not vanish.

The three emoji samples in data/markdown/tests/fixed-colors differ in
exactly one thing — how far a pin reaches — which is why scope is per entry:

    ☀️  glyph only        `75°` beside it stays black
    📈  datapoints        the 5.1% beside it goes green too
    ↗️  line              all of "32k increase" goes green

Run with: uv run python tests/fixed_color_tests.py
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import skia

sys.path.insert(0, "tests")

from markdown_datapoint_split_tests import _processed_with_criteria

from md2ui.pipeline import layout_render as LR
from md2ui.pipeline import render_pill_paint as PP
from md2ui.pipeline.layout_script_parser import LayoutBox
from md2ui.pipeline.render_colors import (
    _label_pins,
    _pin_or_replace,
    painted_pins,
    stamp_fixed_colors,
)
from md2ui.pipeline.render_measure import _explode_words
from md2ui.pipeline.render_text import project_paint_spans
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.theme import BG_IMAGE, LinkStyle, Theme, parse_theme
from md2ui.utils.font_loader import make_font

SAMPLES = Path("data/markdown/tests/fixed-colors")

AMBER = 0xFFF0A93B
GREEN = 0xFF22C55E
RED = 0xFFE5484D
_FACE = skia.Typeface.MakeDefault()
_FONTS = FontSet(_FACE, _FACE, _FACE, _FACE, _FACE)

_FIXED = """# t
## Fixed colors
### Emoji
- ☀️ #F0A93B
- 📈 #22C55E datapoints
- ↗️ #10B981 line
### Emoji background
- 📈 #E9F9EF
### Badges
#### Exact
- Sold out: Text color: #991B1B, Fill color: #FEE2E2
#### Contains
- ⬇: Text color: #E5484D, Fill color: #FDEDEC, Stroke color: #F7C8C5
### Buttons
#### Exact
- Cancel: Text color: #26262B, Fill color: #E5E7EB
#### Contains
- Delete: Text color: #FFFFFF, Fill color: #DC2626, Stroke color: #991B1B
### Datapoints
- change up: #16A34A
- change down: #E5484D
"""


def _theme(text: str = _FIXED) -> Theme:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
        fh.write(text)
        path = Path(fh.name)
    try:
        return parse_theme(path)
    finally:
        path.unlink()


def _stamped(sample: str, theme: Theme) -> list[tuple[str, dict]]:
    """(content, pins) for every leaf of a sample, in document order."""
    return _stamped_markdown((SAMPLES / sample / "content.md").read_text(), theme)


def _stamped_markdown(markdown: str, theme: Theme) -> list[tuple[str, dict]]:
    """(content, pins) for every leaf of *markdown*, in document order."""
    ast = _processed_with_criteria(markdown)
    d = ast.to_dict()
    stamp_fixed_colors(d, theme)
    out: list[tuple[str, dict]] = []

    def walk(n: dict) -> None:
        if not n.get("children"):
            out.append(
                (
                    (n.get("content") or "").strip(),
                    {
                        k: n[k]
                        for k in (
                            "fixed_text",
                            "fixed_fill",
                            "fixed_stroke",
                            "fixed_text_spans",
                        )
                        if k in n
                    },
                )
            )
        for c in n.get("children", []):
            walk(c)

    walk(d)
    return out


def _pin(leaves, content, key="fixed_text"):
    for c, pins in leaves:
        if c == content:
            return pins.get(key)
    raise AssertionError(f"no leaf {content!r} in {[c for c, _ in leaves]}")


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------


def test_the_five_blocks_parse():
    f = _theme().fixed
    assert f.emoji["☀️"] == (AMBER, "")
    assert f.emoji["📈"] == (GREEN, "datapoints")
    assert f.emoji_bg["📈"] == 0xFFE9F9EF
    assert f.pill_exact["Sold out"]["fill"] == 0xFFFEE2E2
    assert f.pill_contains["⬇"]["stroke"] == 0xFFF7C8C5
    assert f.button_exact["Cancel"]["fill"] == 0xFFE5E7EB
    assert f.button_contains["Delete"]["stroke"] == 0xFF991B1B
    assert f.datapoints["change up"] == 0xFF16A34A


def test_a_pin_reaches_emoji_inside_plain_text():
    """A pin is about the GLYPH, so it must not depend on the node holding it.

    An emoji that is its own node is pinned by `stamp_fixed_colors`, but one
    sitting inside a prose line or a heading is drawn as an inline glyph run,
    which reads its colours from the text-context styles. Those are seeded from
    the pin table so a single `## Fixed colors > ### Emoji` entry covers both and
    the same ☀️ cannot come out amber in one line and grey in the next.
    """
    e = _theme().emojis
    assert e.text.fixed_colors["☀️"] == AMBER
    assert e.link.fixed_colors["☀️"] == AMBER
    assert e.inline.fixed_colors["☀️"] == AMBER


def test_an_explicit_text_entry_outranks_the_seeded_pin():
    """`### Text > Fixed colors` is a per-context override, so it still wins."""
    t = _theme(_FIXED + "## Emoji styles\n### Text\nFixed colors:\n- ☀️ #FF0000\n")
    assert t.emojis.text.fixed_colors["☀️"] == 0xFFFF0000, "explicit entry wins"
    # …and a glyph the override does not mention is still seeded from the pins.
    assert t.emojis.text.fixed_colors["📈"] == GREEN
    # The override is per context: link/inline still take the pin.
    assert t.emojis.link.fixed_colors["☀️"] == AMBER


def test_seeding_drops_the_scope():
    """Scope governs how far a pin spreads to sibling NODES; inside a text run
    there is only the one glyph, so the colour is seeded and the scope is not."""
    f = _theme().fixed
    assert f.emoji["↗️"] == (0xFF10B981, "line"), "a scoped pin"
    assert _theme().emojis.text.fixed_colors["↗️"] == 0xFF10B981


def test_scope_defaults_to_the_glyph():
    """An entry written without a scope word is glyph-scoped."""
    assert _theme().fixed.emoji["☀️"][1] == ""


def test_an_absent_section_is_inert():
    assert not Theme().fixed.is_active()


# ---------------------------------------------------------------------------
# Scope — the three samples, each proving one reach
# ---------------------------------------------------------------------------


def test_glyph_scope_stops_at_the_glyph():
    """`☀️` over `___75°___` — the sun is amber, the temperature stays as it was.

    The temperature is one leaf: a bare degree is part of its number, not an
    orphan split off beside it (a value never divides a line, ADR-205).
    """
    leaves = _stamped("emoji", _theme())
    assert _pin(leaves, "☀️") == AMBER
    assert _pin(leaves, "75°") is None


def test_datapoints_scope_reaches_the_value_beside_it():
    """📈 colors the 5.1% next to it — but not the words after it."""
    leaves = _stamped("metrics-3-emoji-datapoint", _theme())
    # PERCENTAGE is annotation-only, so `📈 5.1%` is ONE leaf and the scope
    # lands as a span over the value instead of a pin on a separate DATAPOINT
    # leaf. The reach is what this guards.
    assert _pin(leaves, "📈 5.1%", "fixed_text_spans") == [
        {"start": 2, "end": 6, "color": GREEN}
    ]
    assert _pin(leaves, "from last month") is None
    # …and the plain paragraph the sample exists to protect.
    assert _pin(leaves, "This plain-text should not be painted in green.") is None


def test_line_scope_needs_a_peeled_emoji():
    """`line` scope keys on an EMOJI NODE, so the emoji has to be peeled.

    `32k increase - ↗️` peels at its separator, so the ↗️ becomes an EMOJI node
    and `line` scope spreads its green across the whole run.
    """
    leaves = _stamped("metrics", _theme())
    assert _pin(leaves, "↗️") == 0xFF10B981, "the peeled emoji carries the pin"
    assert _pin(leaves, "32k increase") == 0xFF10B981, (
        "line scope reaches the emoji's whole run"
    )
    # …and stops before the value on the line above. Named as the tree holds
    # it: per ADR-205 that `Key: value` line is one text, written as is.
    assert _pin(leaves, "Unique views: ___192.1k___") is None


# ---------------------------------------------------------------------------
# Scope by kind — the pieces of a run an emoji pin names
# ---------------------------------------------------------------------------

# Every kind on one run, cut into pieces so each is the emoji's sibling.
_EVERY_KIND = (
    "🔥 - Hot deal - ⭐ - `Chip` - [Button](agent:buy) - "
    "[`Text link`](agent:more) - 42%\n"
)
_PIECES = (
    "Hot deal",
    "⭐",
    "Chip",
    "[Button](agent:buy)",
    "[`Text link`](agent:more)",
    "42%",
)


def _painted(leaves, content) -> "int | None":
    """The pin color a leaf is painted with, whole or as its one span."""
    pins = dict(leaves)[content]
    if "fixed_text" in pins:
        return pins["fixed_text"]
    spans = pins.get("fixed_text_spans") or []
    return spans[0]["color"] if spans else None


def _reached(scope: str) -> set[str]:
    theme = _theme(f"# t\n## Fixed colors\n### Emoji\n- 🔥 #E5484D {scope}\n")
    leaves = _stamped_markdown(_EVERY_KIND, theme)
    assert _painted(leaves, "🔥") == RED, "the pin always colors its own glyph"
    return {c for c in _PIECES if _painted(leaves, c) == RED}


def test_kind_words_parse_and_add_up():
    """Kind words follow the color as scope words do, and add up into one
    scope; a word the parser does not know still drops the entry."""
    f = _theme(
        "# t\n## Fixed colors\n### Emoji\n- 🔥 #E5484D text chips\n"
        "- ⭐ #E5484D chips datapoint glyph\n- 🌙 #E5484D chip\n"
    ).fixed
    assert f.emoji["🔥"] == (RED, "chips text")
    assert f.emoji["⭐"] == (RED, "chips datapoints"), "aliases fold, glyph is none"
    assert "🌙" not in f.emoji, "an unknown word drops the entry, as before"
    print("  ✓  kind words parse and add up into one scope")


def test_a_kind_scope_paints_only_its_kinds():
    """A pin naming kinds colors those pieces of its run and no others: words
    (a number among them), emojis, buttons (a text link is one), chips."""
    assert _reached("chips") == {"Chip"}
    assert _reached("emojis") == {"⭐"}
    assert _reached("buttons") == {"[Button](agent:buy)", "[`Text link`](agent:more)"}
    assert _reached("text") == {"Hot deal", "42%"}
    assert _reached("text chips") == {"Hot deal", "42%", "Chip"}
    assert _reached("line") == set(_PIECES), "line is still every kind"
    assert _reached("") == set(), "no word is still the glyph alone"
    print("  ✓  a kind scope paints only the pieces of its kinds")


def test_datapoints_scope_reaches_every_datapoint():
    """Links and emojis are datapoints, so `datapoints` reaches them; words and
    chips hold none here."""
    assert _reached("datapoints") == {
        "⭐",
        "[Button](agent:buy)",
        "[`Text link`](agent:more)",
        "42%",
    }
    assert _reached("chips datapoints") == _reached("datapoints") | {"Chip"}
    print("  ✓  datapoints reaches values, links and emojis; kinds add to it")


def test_an_inline_datapoints_pin_reaches_an_emoji_in_its_sentence():
    """Inside one sentence the scoped glyph colors the sentence's datapoints,
    another emoji among them."""
    theme = _theme("# t\n## Fixed colors\n### Emoji\n- 📈 #22C55E datapoints\n")
    leaf = _stamped_inline_leaf("📈 5.1% from last month ⭐\n", theme)
    starts = {span["start"] for span in leaf["fixed_text_spans"]}
    star = leaf["content"].index("⭐")
    assert star in starts, leaf["fixed_text_spans"]
    print("  ✓  an inline datapoints pin reaches an emoji in its sentence")


# ---------------------------------------------------------------------------
# Datapoints keyed by direction
# ---------------------------------------------------------------------------


def test_a_signed_value_colors_by_direction():
    """`+$22,910` is one `change` leaf and keys directly."""
    leaves = _stamped("metrics-2-datapoint", _theme())
    assert _pin(leaves, "+$22,910") == 0xFF16A34A
    assert _pin(leaves, "$129,201.40") is None


def test_a_sign_stays_with_its_number():
    """`+2,588` keeps its sign, so the whole value is colored as one thing.

    The grouper does not cut between sign and
    number, so `+2,588` and `+$22,910` are each one signed leaf and key on
    their own sign; a split would draw a grey plus beside a green figure.
    """
    leaves = _stamped("metrics-2-datapoint", _theme())
    assert _pin(leaves, "+2,588") == 0xFF16A34A
    assert _pin(leaves, "24,104") is None


def _after(prev: dict, content: str, data_points: list[dict], theme_tail: str):
    """Stamp a pinned datapoint leaf after *prev*; return both."""
    leaf = {"type": "text", "content": content, "data_points": data_points}
    root = {"type": "root", "children": [prev, leaf]}
    stamp_fixed_colors(
        root, _theme("# t\n## Fixed colors\n### Datapoints\n" + theme_tail)
    )
    return prev, leaf


_PCT = {"label": "dp_percentage", "matched": "5%", "start": 0, "end": 2}


def test_only_a_lone_sign_takes_its_numbers_pin():
    """A container before a pinned value is not a sign, and neither is `+-`:
    a substring test against `"+-"` would let an empty-content group take the
    value's color."""
    for prev in (
        {"type": "group", "children": [{"type": "text", "content": "a"}]},
        {"type": "text", "content": "+-"},
    ):
        before, _ = _after(prev, "5%", [_PCT], "- percentage: #22C55E\n")
        assert "fixed_text" not in before, prev
    sign, _ = _after(
        {"type": "text", "content": "+"}, "5%", [_PCT], "- percentage: #22C55E\n"
    )
    assert sign["fixed_text"] == GREEN


def test_a_lone_sign_takes_the_color_its_number_is_painted():
    """The sign matches the leaf's leading ink, not the first annotation listed."""
    tail = "- percentage: #22C55E\n- currency: #E5484D\n"
    dps = [
        {"label": "dp_currency", "matched": "$3", "start": 9, "end": 11},
        {"label": "dp_percentage", "matched": "5%", "start": 0, "end": 2},
    ]
    stale = {
        "type": "text",
        "content": "+",
        "fixed_text_spans": [{"start": 0, "end": 1, "color": RED}],
    }
    sign, leaf = _after(stale, "5% and   $3", dps, tail)
    assert leaf["fixed_text_spans"][0]["color"] == GREEN
    assert sign["fixed_text"] == GREEN
    assert "fixed_text_spans" not in sign, "one pin per leaf: a span would outrank it"


# ---------------------------------------------------------------------------
# Datapoint ranges inside text leaves
# ---------------------------------------------------------------------------


def _range_node(content: str, data_points: list[dict]) -> dict:
    leaf = {"type": "text", "content": content, "data_points": data_points}
    root = {"type": "root", "children": [leaf]}
    stamp_fixed_colors(
        root,
        _theme(_FIXED + "- percentage: #22C55E\n- currency: #E5484D\n"),
    )
    return leaf


def test_a_datapoint_pin_colors_one_span_inside_a_longer_leaf():
    leaf = _range_node(
        "Revenue 5.1% today",
        [{"label": "dp_percentage", "matched": "5.1%", "start": 8, "end": 12}],
    )
    assert "fixed_text" not in leaf, "the surrounding prose must stay unpinned"
    assert leaf["fixed_text_spans"] == [{"start": 8, "end": 12, "color": GREEN}]
    words = project_paint_spans(
        leaf["content"], _explode_words(leaf["content"]), leaf["fixed_text_spans"]
    )
    assert [w[0] for w in words if w[7]] == ["5.1%"]
    assert words[1][7] == ((0, 4, GREEN),)


def test_two_datapoint_pins_keep_two_regions_in_one_leaf():
    leaf = _range_node(
        "5.1% and $20",
        [
            {"label": "dp_percentage", "matched": "5.1%", "start": 0, "end": 4},
            {"label": "dp_currency", "matched": "$20", "start": 9, "end": 12},
        ],
    )
    assert leaf["fixed_text_spans"] == [
        {"start": 0, "end": 4, "color": GREEN},
        {"start": 9, "end": 12, "color": RED},
    ]
    words = project_paint_spans(
        leaf["content"], _explode_words(leaf["content"]), leaf["fixed_text_spans"]
    )
    assert [(w[0], w[7]) for w in words if w[7]] == [
        ("5.1%", ((0, 4, GREEN),)),
        ("$20", ((0, 3, RED),)),
    ]


def test_an_annotate_only_dimension_still_reaches_its_pin():
    content = "Photo 1920 x 1080 ready"
    leaf = {
        "type": "text",
        "content": content,
        "data_points": [
            {
                "label": "dp_dimension",
                "matched": "1920 x 1080",
                "start": 6,
                "end": 17,
            }
        ],
    }
    stamp_fixed_colors(
        {"type": "root", "children": [leaf]},
        _theme(_FIXED + "- dimension: #22C55E\n"),
    )
    assert "fixed_text" not in leaf, "the surrounding prose must stay unpinned"
    assert leaf["fixed_text_spans"] == [{"start": 6, "end": 17, "color": GREEN}]


def test_an_annotate_only_duration_still_reaches_its_pin():
    content = "Waited 4 hours 35 minutes today"
    leaf = {
        "type": "text",
        "content": content,
        "data_points": [
            {
                "label": "dp_duration",
                "matched": "4 hours 35 minutes",
                "start": 7,
                "end": 25,
            }
        ],
    }
    stamp_fixed_colors(
        {"type": "root", "children": [leaf]},
        _theme(_FIXED + "- duration: #22C55E\n"),
    )
    assert "fixed_text" not in leaf, "the surrounding prose must stay unpinned"
    assert leaf["fixed_text_spans"] == [{"start": 7, "end": 25, "color": GREEN}]


def test_an_annotate_only_version_still_reaches_its_pin():
    content = "Release v1.2.3 ready"
    leaf = {
        "type": "text",
        "content": content,
        "data_points": [
            {
                "label": "dp_version",
                "matched": "v1.2.3",
                "start": 8,
                "end": 14,
            }
        ],
    }
    stamp_fixed_colors(
        {"type": "root", "children": [leaf]},
        _theme(_FIXED + "- version: #22C55E\n"),
    )
    assert "fixed_text" not in leaf, "the surrounding prose must stay unpinned"
    assert leaf["fixed_text_spans"] == [{"start": 8, "end": 14, "color": GREEN}]


def test_an_annotate_only_rate_still_reaches_its_pin():
    content = "Rate $50/hour ready"
    leaf = {
        "type": "text",
        "content": content,
        "data_points": [
            {
                "label": "dp_rate",
                "matched": "$50/hour",
                "start": 5,
                "end": 13,
            }
        ],
    }
    stamp_fixed_colors(
        {"type": "root", "children": [leaf]},
        _theme(_FIXED + "- rate: #22C55E\n"),
    )
    assert "fixed_text" not in leaf, "the surrounding prose must stay unpinned"
    assert leaf["fixed_text_spans"] == [{"start": 5, "end": 13, "color": GREEN}]


def test_an_annotate_only_date_range_still_reaches_its_pin():
    content = "Dates Jan 12-28, 2026 ready"
    leaf = {
        "type": "text",
        "content": content,
        "data_points": [
            {
                "label": "dp_date_range",
                "matched": "Jan 12-28, 2026",
                "start": 6,
                "end": 21,
            }
        ],
    }
    stamp_fixed_colors(
        {"type": "root", "children": [leaf]},
        _theme(_FIXED + "- date_range: #22C55E\n"),
    )
    assert "fixed_text" not in leaf, "the surrounding prose must stay unpinned"
    assert leaf["fixed_text_spans"] == [{"start": 6, "end": 21, "color": GREEN}]


def _assert_annotate_only_span_reaches_its_pin(
    content: str, label: str, matched: str, start: int
):
    end = start + len(matched)
    leaf = {
        "type": "text",
        "content": content,
        "data_points": [
            {"label": f"dp_{label}", "matched": matched, "start": start, "end": end}
        ],
    }
    stamp_fixed_colors(
        {"type": "root", "children": [leaf]},
        _theme(_FIXED + f"- {label}: #22C55E\n"),
    )
    assert "fixed_text" not in leaf, "the surrounding prose must stay unpinned"
    assert leaf["fixed_text_spans"] == [{"start": start, "end": end, "color": GREEN}]


def test_an_annotate_only_file_size_still_reaches_its_pin():
    _assert_annotate_only_span_reaches_its_pin(
        "File 500 MB ready", "file_size", "500 MB", 5
    )


def test_an_annotate_only_phone_still_reaches_its_pin():
    _assert_annotate_only_span_reaches_its_pin(
        "Call (555) 123-4567 now", "phone", "(555) 123-4567", 5
    )


def test_an_annotate_only_url_still_reaches_its_pin():
    _assert_annotate_only_span_reaches_its_pin(
        "Visit https://example.com now", "url", "https://example.com", 6
    )


def test_an_annotate_only_date_still_reaches_its_pin():
    _assert_annotate_only_span_reaches_its_pin(
        "Date May 2017 ready", "date", "May 2017", 5
    )


def test_an_annotate_only_range_still_reaches_its_pin():
    _assert_annotate_only_span_reaches_its_pin(
        "Value €180-200M now", "range", "€180-200M", 6
    )


def test_an_annotate_only_quantity_still_reaches_its_pin():
    _assert_annotate_only_span_reaches_its_pin(
        "Wait 5 days now", "quantity", "5 days", 5
    )


def test_an_annotate_only_time_still_reaches_its_pin():
    _assert_annotate_only_span_reaches_its_pin("Meet at 3 PM today", "time", "3 PM", 8)


def _stamped_inline_leaf(content: str, theme: Theme | None = None) -> dict:
    tree = _processed_with_criteria(content).to_dict()
    stamp_fixed_colors(tree, theme or _theme())
    leaves = []

    def walk(node: dict) -> None:
        if not node.get("children") and node.get("content"):
            leaves.append(node)
        for child in node.get("children", []):
            walk(child)

    walk(tree)
    assert len(leaves) == 1, [
        (leaf.get("type"), leaf.get("content")) for leaf in leaves
    ]
    return leaves[0]


def test_annotate_only_changes_keep_directional_span_pins():
    # Use unscoped emoji here: the configured 📈 ``datapoints`` scope
    # deliberately outranks the directional pin and is covered separately.
    up = _stamped_inline_leaf("+2.58% 🔥")
    assert up["type"] == "text"
    assert up["fixed_text_spans"] == [{"start": 0, "end": 6, "color": 0xFF16A34A}]

    down = _stamped_inline_leaf("-$36.10 ✨")
    assert down["type"] == "text"
    assert down["fixed_text_spans"] == [{"start": 0, "end": 7, "color": RED}]


def test_annotate_only_currency_keeps_its_span_pin():
    leaf = _stamped_inline_leaf("Pay $20 now", _theme(_FIXED + "- currency: #E5484D\n"))
    assert leaf["type"] == "text"
    assert leaf["fixed_text_spans"] == [{"start": 4, "end": 7, "color": RED}]


def test_annotate_only_ranking_keeps_its_span_pin():
    leaf = _stamped_inline_leaf(
        "Ranked #1 today", _theme(_FIXED + "- ranking: #E5484D\n")
    )
    assert leaf["type"] == "text"
    assert leaf["fixed_text_spans"] == [{"start": 7, "end": 9, "color": RED}]


def test_annotate_only_measurement_keeps_its_span_pin():
    leaf = _stamped_inline_leaf(
        "Set to 75° now", _theme(_FIXED + "- measurement: #E5484D\n")
    )
    assert leaf["type"] == "text"
    assert leaf["fixed_text_spans"] == [{"start": 7, "end": 10, "color": RED}]


def test_annotate_only_score_keeps_its_span_pin():
    leaf = _stamped_inline_leaf(
        "Rated 4.8/5.0 today", _theme(_FIXED + "- score: #E5484D\n")
    )
    assert leaf["type"] == "text"
    assert leaf["fixed_text_spans"] == [{"start": 6, "end": 13, "color": RED}]


def test_annotate_only_ratio_keeps_its_span_pin():
    # A colon ratio, not `4/8`: with a word either side the slash form is read
    # as a SCORE, which has its own pin test above.
    leaf = _stamped_inline_leaf(
        "Aspect 3:2 here", _theme(_FIXED + "- ratio: #E5484D\n")
    )
    assert leaf["type"] == "text"
    assert leaf["fixed_text_spans"] == [{"start": 7, "end": 10, "color": RED}]


def test_annotate_only_number_keeps_its_span_pin():
    # `Count 42 today`, not a thousands number followed by a noun: `1,293 items`
    # is read as a QUANTITY, which is a different pin.
    leaf = _stamped_inline_leaf(
        "Count 42 today", _theme(_FIXED + "- number: #E5484D\n")
    )
    assert leaf["type"] == "text"
    assert leaf["fixed_text_spans"] == [{"start": 6, "end": 8, "color": RED}]


def test_invalidated_datapoint_offsets_fall_back_to_the_whole_leaf():
    leaf = _range_node(
        "Gain 5.1% today",
        # The recorded offset predates a one-character rewrite: it no longer
        # selects `matched`, so painting it as a range would color the wrong ink.
        [{"label": "dp_percentage", "matched": "5.1%", "start": 4, "end": 8}],
    )
    assert leaf["fixed_text"] == GREEN
    assert "fixed_text_spans" not in leaf


# ---------------------------------------------------------------------------
# Pills
# ---------------------------------------------------------------------------


def test_a_contains_key_matches_a_label_that_varies():
    """`⬇ +36.8%` can never be keyed literally — the number changes."""
    t = _theme()
    changing = _label_pins("⬇ +36.8%", t.fixed.pill_exact, t.fixed.pill_contains)
    assert changing is not None
    assert changing["text"] == RED
    integer = _label_pins("⬇ 12", t.fixed.pill_exact, t.fixed.pill_contains)
    assert integer is not None
    assert integer["text"] == RED
    assert _label_pins("+36.8%", t.fixed.pill_exact, t.fixed.pill_contains) is None


def test_an_exact_key_matches_only_the_whole_label():
    t = _theme()
    sold_out = _label_pins("Sold out", t.fixed.pill_exact, t.fixed.pill_contains)
    assert sold_out is not None
    assert sold_out["fill"] == 0xFFFEE2E2
    assert (
        _label_pins("Sold out soon", t.fixed.pill_exact, t.fixed.pill_contains) is None
    )


def test_a_pill_gets_all_three_roles():
    leaves = _stamped("metrics-4-pills", _theme())
    for key, want in (
        ("fixed_text", RED),
        ("fixed_fill", 0xFFFDEDEC),
        ("fixed_stroke", 0xFFF7C8C5),
    ):
        assert _pin(leaves, "⬇ +36.8%", key) == want, key


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------


def _stamped_button(label: str, theme: Theme) -> dict:
    button = {
        "type": "link",
        "content": f"[{label}](/action)",
        "link_label": label,
        "link_variant": "primary",
        "children": [],
    }
    stamp_fixed_colors({"type": "root", "children": [button]}, theme)
    return button


def test_button_exact_and_contains_are_independent_from_pills():
    t = _theme()
    cancel = _stamped_button("Cancel", t)
    delete = _stamped_button("Delete account", t)
    sold_out = _stamped_button("Sold out", t)
    assert cancel["fixed_fill"] == 0xFFE5E7EB
    assert delete["fixed_fill"] == 0xFFDC2626
    assert delete["fixed_stroke"] == 0xFF991B1B
    assert "fixed_fill" not in sold_out, "a Pills rule leaked into Buttons"
    chip_match = _label_pins(
        "Delete account", t.fixed.pill_exact, t.fixed.pill_contains
    )
    assert chip_match is None, "a Buttons rule leaked into Pills"


def test_button_rules_alone_activate_fixed_color_stamping():
    t = _theme(
        "## Fixed colors\n### Buttons\n#### Contains\n- Delete: Fill color: #DC2626\n"
    )
    assert t.fixed.is_active()
    assert _stamped_button("Delete account", t)["fixed_fill"] == 0xFFDC2626


def _filled(t: Theme) -> Theme:
    """A primary button with a fill to pin: an unthemed link paints none."""
    t.links.primary.fill_color = 0xFF26262B
    return t


def test_button_pins_reach_fill_and_label_paint():
    t = _filled(_theme())
    button = _stamped_button("Delete account", t)
    box = LayoutBox(0, 0, 120, 40, bg_stack=(0xFFFFFFFF,))
    surface = skia.Surface(120, 40)
    with (
        patch.object(PP, "_paint_layered_fill") as paint_fill,
        patch.object(LR, "_draw_text_with_emoji") as paint_text,
    ):
        LR.draw_link_box(surface.getCanvas(), box, button, _FONTS, t)
    assert paint_fill.call_args.kwargs["bg_color"] == 0xFFDC2626
    assert paint_text.call_args.args[7].getColor() == 0xFFFFFFFF


def _outlined(t: Theme) -> Theme:
    """The primary variant drawn as an outline: clear fill, 2px dark stroke."""
    t.links.primary.fill_color = 0x001F1F1F
    t.links.primary.stroke_width = 2.0
    t.links.primary.stroke_color = 0xFF26262B
    return t


def test_an_outlined_button_takes_the_stroke_pin_and_not_the_fill():
    """`*[Delete](/x)*` is an outline, so the entry's red fill must not fill it."""
    t = _outlined(_theme())
    button = _stamped_button("Delete account", t)
    style = LR._resolve_link(button, t)[3]
    assert painted_pins(button, style) == {
        "fixed_stroke": 0xFF991B1B,
        "fixed_text": 0xFFFFFFFF,
    }
    box = LayoutBox(0, 0, 120, 40, bg_stack=(0xFFFFFFFF,))
    surface = skia.Surface(120, 40)
    with (
        patch.object(PP, "_paint_layered_fill") as paint_fill,
        patch.object(LR, "_draw_text_with_emoji"),
    ):
        LR.draw_link_box(surface.getCanvas(), box, button, _FONTS, t)
    assert paint_fill.call_args.kwargs["bg_color"] is None


def test_a_label_pin_on_its_own_fill_falls_to_replacement():
    """One entry, two looks: a red label on the outline, a white one on red.

    `Cancel: Text color: #FA3C4F, Fill color: #FA3C4F`. On the filled variant
    the label equals the surface behind it, so the pin is dropped and the
    `On background color: #FA3C4F` rule answers; the outline keeps the red.
    """
    t = _theme(
        "## Fixed colors\n### Buttons\n#### Exact\n"
        "- Cancel: Text color: #FA3C4F, Fill color: #FA3C4F, Stroke color: #FA3C4F\n"
        "## Color Replacements\nOn background color: #FA3C4F\n- Replacement: #FFFFFF\n"
    )

    def label(theme: Theme) -> int:
        button = _stamped_button("Cancel", theme)
        box = LayoutBox(0, 0, 120, 40, bg_stack=(0xFFFFFFFF,))
        surface = skia.Surface(120, 40)
        with patch.object(LR, "_draw_text_with_emoji") as paint_text:
            LR.draw_link_box(surface.getCanvas(), box, button, _FONTS, theme)
        return paint_text.call_args.args[7].getColor()

    assert label(_filled(t)) == 0xFFFFFFFF
    t.links.primary.fill_color = 0x001F1F1F
    t.links.primary.stroke_width = 2.0
    assert label(t) == 0xFFFA3C4F


def test_a_filled_button_ignores_a_stroke_it_does_not_draw():
    t = _filled(_theme())
    t.links.primary.stroke_width = 0.0
    button = _stamped_button("Delete account", t)
    style = LR._resolve_link(button, t)[3]
    assert painted_pins(button, style) == {
        "fixed_fill": 0xFFDC2626,
        "fixed_text": 0xFFFFFFFF,
    }


def test_a_text_only_pin_reaches_an_outlined_label():
    t = _outlined(
        _theme(
            "## Fixed colors\n### Buttons\n#### Exact\n- Cancel: Text color: #E5484D\n"
        )
    )
    button = _stamped_button("Cancel", t)
    style = LR._resolve_link(button, t)[3]
    assert painted_pins(button, style) == {"fixed_text": RED}


def test_an_unpinned_stroke_keeps_its_variant_color():
    t = _outlined(_theme())
    button = _stamped_button("Cancel", t)
    style = LR._resolve_link(button, t)[3]
    assert painted_pins(button, style) == {"fixed_text": 0xFF26262B}


def test_a_transparent_pinned_fill_still_colors_the_label():
    """`+$8,450.00: Text color: #00BE8B, Fill color: #00000000` on a clear chip."""
    style = LinkStyle(fill_color=0x00000000)
    pins = {"fixed_text": GREEN, "fixed_fill": 0x00000000}
    assert painted_pins(pins, style) == {"fixed_text": GREEN}


def test_a_stroke_width_without_a_color_takes_the_stroke_pin():
    """A theme may declare only `Stroke width` and let the pin supply the color."""
    style = LinkStyle(fill_color=0xFFFDEDEC, stroke_width=1.0)
    pins = {"fixed_fill": 0xFFFDEDEC, "fixed_stroke": 0xFFF7C8C5}
    assert painted_pins(pins, style) == pins


def test_disabled_button_state_outranks_its_label_pin():
    t = _theme()
    t.links.primary.disabled_fill_color = 0xFF9A97AD
    button = _stamped_button("Delete account", t)
    button["link_disabled"] = True
    box = LayoutBox(0, 0, 120, 40, bg_stack=(0xFFFFFFFF,))
    surface = skia.Surface(120, 40)
    with patch.object(PP, "_paint_layered_fill") as paint_fill:
        LR.draw_link_box(surface.getCanvas(), box, button, _FONTS, t)
    assert paint_fill.call_args.kwargs["bg_color"] == 0xFF9A97AD


# ---------------------------------------------------------------------------
# Precedence
# ---------------------------------------------------------------------------


def test_a_pin_outranks_replacement():
    t = _theme(
        _FIXED
        + """
## Color Replacements
On background color: #101010
- Text color: #F0A93B, Replacement: #FFFFFF
"""
    )
    # Replacement would turn the amber white on that card; the pin wins.
    assert _pin_or_replace(AMBER, AMBER, (0xFF101010,), t) == AMBER
    # Without a pin the replacement applies as normal.
    assert _pin_or_replace(AMBER, None, (0xFF101010,), t) == 0xFFFFFFFF


def test_a_pin_equal_to_its_background_is_dropped():
    """The invisibility exception: a red 🔻 on the red card the rotation dealt.

    Exact match only — no contrast threshold to tune — and once dropped the
    ordinary replacement runs, so the element is still legible rather than just
    unpinned.
    """
    t = _theme(
        _FIXED
        + """
## Color Replacements
On background color: #E5484D
- Text color: #E5484D, Replacement: #FFFFFF
"""
    )
    assert _pin_or_replace(RED, RED, (RED,), t) == 0xFFFFFFFF
    # A near-miss is NOT dropped: only an exact collision counts.
    assert _pin_or_replace(RED, RED, (0xFFE5484E,), t) == RED


def test_a_translucent_pin_is_judged_on_what_shows_behind_it():
    """A 10% green fill over a green section paints green: it would vanish.

    So would a label pinned green on that fill, since the fill is see-through
    to the green below. Both are dropped. A clear pin is an authored "no fill"
    and is kept, and so is any pin over a picture, whose colour is unknown.
    """
    t = Theme()
    green, tint = 0xFF00E700, 0x1900E700
    assert _pin_or_replace(0xFF1A1A1A, tint, (green,), t, "fill") == 0xFF1A1A1A
    assert _pin_or_replace(0xFF26262B, green, (tint, green), t) == 0xFF26262B
    # The same tint over white shows, and a green label on it shows too.
    assert _pin_or_replace(0xFF1A1A1A, tint, (0xFFFFFFFF,), t, "fill") == tint
    assert _pin_or_replace(0xFF26262B, green, (tint, 0xFFFFFFFF), t) == green
    assert _pin_or_replace(0xFF1A1A1A, 0x0000E700, (green,), t, "fill") == 0x0000E700
    assert _pin_or_replace(0xFF1A1A1A, tint, (BG_IMAGE, green), t, "fill") == tint


def test_a_translucent_fill_pin_on_its_own_colour_leaves_a_legible_button():
    """The link-pill path: fill pin dropped, its own fill paints, label kept."""
    t = _theme(
        "## Fixed colors\n### Buttons\n#### Contains\n"
        "- ▲: Text color: #00E700, Fill color: #00E70019\n"
    )
    t = _filled(t)
    button = _stamped_button("▲ 6%", t)
    box = LayoutBox(0, 0, 120, 40, bg_stack=(0xFF00E700,))
    surface = skia.Surface(120, 40)
    with (
        patch.object(PP, "_paint_layered_fill") as paint_fill,
        patch.object(LR, "_draw_text_with_emoji") as paint_text,
    ):
        LR.draw_link_box(surface.getCanvas(), box, button, _FONTS, t)
    assert paint_fill.call_args.kwargs["bg_color"] == 0xFF26262B
    assert paint_text.call_args.args[7].getColor() == 0xFF00E700


def test_no_pins_means_no_stamping():
    """An unconfigured theme must leave every node exactly as it was."""
    leaves = _stamped("metrics-3-emoji-datapoint", Theme())
    assert all(not pins for _c, pins in leaves)


def _line_font() -> skia.Font:
    """A locked text face, which has neither symbol: both are drawn in a face the
    platform falls back to, whose advance only the painter's own measure knows."""
    return make_font(
        skia.Typeface.MakeFromFile("assets/fonts/Inter_18pt-Regular.ttf"), 20
    )


def _paint_line(text: str, fixed: dict[str, int] | None) -> tuple[float, np.ndarray]:
    """``text`` drawn black on white through the shared run painter, with no
    emoji face so every character takes the text slot."""
    from md2ui.pipeline.render_text_paint import _draw_text_with_emoji

    surface = skia.Surface(240, 40)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorWHITE)
    font = _line_font()
    paint = skia.Paint(Color=skia.ColorBLACK, AntiAlias=True)
    advance = _draw_text_with_emoji(
        canvas, text, 4, 28, font, None, 20, paint, fixed_colors=fixed
    )
    return advance, surface.makeImageSnapshot().toarray(
        colorType=skia.kRGBA_8888_ColorType
    )


def test_a_pin_colors_a_symbol_drawn_in_the_text_slot():
    """A pin names a character, not an emoji: ⏷ in a text run takes its colour."""
    plain_adv, plain = _paint_line("Sort ⏷ by ▸", None)
    pinned_adv, pinned = _paint_line("Sort ⏷ by ▸", {"⏷": RED})
    assert pinned_adv == plain_adv
    changed = (plain != pinned).any(-1)
    assert changed.any(), "the pinned ⏷ kept the text colour"
    cols = changed.nonzero()[1]
    from md2ui.pipeline.render_text_paint import _text_advance

    font = _line_font()
    left = 4 + _text_advance("Sort ", font, None, 20)
    right = 4 + _text_advance("Sort ⏷", font, None, 20)
    # Only the pinned glyph changes: the words and the unpinned ▸ are untouched.
    assert cols.min() >= int(left) - 1 and cols.max() <= int(right) + 1
    reds = pinned[changed]
    assert (reds[:, 0] > reds[:, 1] + 40).any()


def test_a_text_run_without_a_pinned_character_is_unchanged():
    """Pins on other characters leave a run pixel-identical."""
    _a, plain = _paint_line("Sort ▸ by name", None)
    _b, pinned = _paint_line("Sort ▸ by name", {"⏷": RED, "❤️": RED})
    assert (plain == pinned).all()


def test_an_emoji_pin_matches_with_or_without_its_selector():
    """``- ☀️ #…`` pins a bare ``☀`` too, and ``- ☀ #…`` pins ``☀️``: one glyph
    to the author, as for a Pills pin. Covers the badge (``stamp_fixed_colors``),
    an inline run (``_draw_text_with_emoji``) and a text-slot symbol."""
    from md2ui.pipeline.render_text_paint import _draw_text_with_emoji

    for pin, glyph in (("☀\ufe0f", "☀"), ("☀", "☀\ufe0f")):
        t = _theme(f"# t\n## Fixed colors\n### Emoji\n- {pin} #E5484D\n")
        root = {"children": [{"type": "emoji", "content": glyph}]}
        stamp_fixed_colors(root, t)
        assert root["children"][0].get("fixed_text") == RED, (pin, glyph)

        surface = skia.Surface(80, 60)
        surface.getCanvas().clear(skia.ColorWHITE)
        emoji = skia.Typeface.MakeFromFile("assets/fonts/OpenMoji-black-glyf.ttf")
        _draw_text_with_emoji(
            surface.getCanvas(),
            glyph,
            4,
            44,
            make_font(_FACE, 40),
            emoji,
            40,
            skia.Paint(Color=skia.ColorBLACK, AntiAlias=True),
            fixed_colors=t.emojis.text.fixed_colors,
        )
        px = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
        ink = px[(px[..., :3] < 250).any(-1)].astype(int)
        assert (ink[:, 0] > ink[:, 1] + 40).any(), f"{glyph!r} not red under {pin!r}"
        assert not (ink[:, 0] < 60).all(), "drawn black"
    _a, plain = _paint_line("Sort ⏷ by", None)
    _b, pinned = _paint_line("Sort ⏷ by", {"⏷\ufe0f": RED})
    assert (plain != pinned).any(), "a text-slot key with a selector missed"
    print("  ✓  an emoji pin matches its glyph with or without U+FE0F")


def test_a_pin_table_is_built_once_per_theme():
    """The pins of one theme are read for every text run of a recording, so the
    table is built once per ``fixed_colors`` dict and the cuts are what building
    it per run gave: the longest key first, a key written bare beating one that
    differs by its selector."""
    from md2ui.pipeline import render_text_paint as RTP

    pins = {"\u23f7\ufe0f": GREEN, "\u23f7": RED, "ab": AMBER, "a": GREEN}
    calls = []
    real = RTP.bare_glyph

    def counted(text: str) -> str:
        calls.append(text)
        return real(text)

    with patch.object(RTP, "bare_glyph", counted):
        first = RTP._pinned_pieces("xab\u23f7a", pins)
        built = len(calls)
        again = RTP._pinned_pieces("a\u23f7", pins)
    assert built > 0 and len(calls) == built, "the table was rebuilt for a run"
    assert first == [(0, 1, None), (1, 3, AMBER), (3, 4, RED), (4, 5, GREEN)]
    assert again == [(0, 1, GREEN), (1, 2, RED)]
    assert RTP._pinned_pieces("xyz", pins) == []
    print("  ✓  a pin table is built once per theme")


def test_a_chip_of_one_signed_value_takes_its_direction():
    """A chip whose label is one signed value colors by its direction, as the
    same value in text does: the pin on its label, a light tint of it behind.
    A Pills pin that matches still wins; a chip that is more than one value
    keeps the chip's own paint."""
    leaves = _stamped_markdown(
        "`-2.01%`\n\n`+0.39%`\n\n`-2.01% today`\n\n`⬇ +36.8%`\n", _theme()
    )
    assert _pin(leaves, "-2.01%") == RED
    assert _pin(leaves, "-2.01%", "fixed_fill") == (RED & 0xFFFFFF) | 0x19000000
    assert _pin(leaves, "+0.39%") == 0xFF16A34A
    assert _pin(leaves, "-2.01% today") is None, "not one value"
    assert _pin(leaves, "⬇ +36.8%") == RED, "the pill pin wins"
    assert _pin(leaves, "⬇ +36.8%", "fixed_fill") == 0xFFFDEDEC
    print("  ✓  a chip of one signed value takes its direction")


TESTS = [
    test_a_chip_of_one_signed_value_takes_its_direction,
    test_an_emoji_pin_matches_with_or_without_its_selector,
    test_a_pin_table_is_built_once_per_theme,
    test_the_five_blocks_parse,
    test_a_pin_reaches_emoji_inside_plain_text,
    test_an_explicit_text_entry_outranks_the_seeded_pin,
    test_seeding_drops_the_scope,
    test_scope_defaults_to_the_glyph,
    test_an_absent_section_is_inert,
    test_glyph_scope_stops_at_the_glyph,
    test_datapoints_scope_reaches_the_value_beside_it,
    test_line_scope_needs_a_peeled_emoji,
    test_kind_words_parse_and_add_up,
    test_a_kind_scope_paints_only_its_kinds,
    test_datapoints_scope_reaches_every_datapoint,
    test_an_inline_datapoints_pin_reaches_an_emoji_in_its_sentence,
    test_a_signed_value_colors_by_direction,
    test_a_sign_stays_with_its_number,
    test_only_a_lone_sign_takes_its_numbers_pin,
    test_a_lone_sign_takes_the_color_its_number_is_painted,
    test_a_datapoint_pin_colors_one_span_inside_a_longer_leaf,
    test_two_datapoint_pins_keep_two_regions_in_one_leaf,
    test_an_annotate_only_dimension_still_reaches_its_pin,
    test_an_annotate_only_duration_still_reaches_its_pin,
    test_an_annotate_only_version_still_reaches_its_pin,
    test_an_annotate_only_rate_still_reaches_its_pin,
    test_an_annotate_only_date_range_still_reaches_its_pin,
    test_an_annotate_only_file_size_still_reaches_its_pin,
    test_an_annotate_only_phone_still_reaches_its_pin,
    test_an_annotate_only_url_still_reaches_its_pin,
    test_an_annotate_only_date_still_reaches_its_pin,
    test_an_annotate_only_range_still_reaches_its_pin,
    test_an_annotate_only_quantity_still_reaches_its_pin,
    test_an_annotate_only_time_still_reaches_its_pin,
    test_annotate_only_changes_keep_directional_span_pins,
    test_annotate_only_currency_keeps_its_span_pin,
    test_annotate_only_ranking_keeps_its_span_pin,
    test_annotate_only_measurement_keeps_its_span_pin,
    test_annotate_only_score_keeps_its_span_pin,
    test_annotate_only_ratio_keeps_its_span_pin,
    test_annotate_only_number_keeps_its_span_pin,
    test_invalidated_datapoint_offsets_fall_back_to_the_whole_leaf,
    test_a_contains_key_matches_a_label_that_varies,
    test_an_exact_key_matches_only_the_whole_label,
    test_a_pill_gets_all_three_roles,
    test_button_exact_and_contains_are_independent_from_pills,
    test_button_rules_alone_activate_fixed_color_stamping,
    test_button_pins_reach_fill_and_label_paint,
    test_an_outlined_button_takes_the_stroke_pin_and_not_the_fill,
    test_a_label_pin_on_its_own_fill_falls_to_replacement,
    test_a_filled_button_ignores_a_stroke_it_does_not_draw,
    test_a_text_only_pin_reaches_an_outlined_label,
    test_an_unpinned_stroke_keeps_its_variant_color,
    test_a_transparent_pinned_fill_still_colors_the_label,
    test_a_stroke_width_without_a_color_takes_the_stroke_pin,
    test_disabled_button_state_outranks_its_label_pin,
    test_a_pin_outranks_replacement,
    test_a_pin_equal_to_its_background_is_dropped,
    test_a_translucent_pin_is_judged_on_what_shows_behind_it,
    test_a_translucent_fill_pin_on_its_own_colour_leaves_a_legible_button,
    test_no_pins_means_no_stamping,
    test_a_pin_colors_a_symbol_drawn_in_the_text_slot,
    test_a_text_run_without_a_pinned_character_is_unchanged,
]

if __name__ == "__main__":
    print("Fixed Color Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            doc = test.__doc__.splitlines()[0] if test.__doc__ else test.__name__
            print(f"  ✓  {doc}")
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
