"""Tests for the hooks `scripts/export_ts_fixtures.py` records md2ui through.

**Why this file exists.** The md2ui-ts fixtures are exported through hooks that
wrap md2ui from outside: nothing under `src/` knows it is being watched. When
md2ui renames or moves what a hook wraps, or changes the phases of
`MarkdownGrouper._process_once`, these tests fail in md2ui's own gate, so the
fixtures are regenerated instead of silently going stale.

Run with: uv run python scripts/run_tests.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import jsonschema  # noqa: E402
import ts_fixture_closures as closures  # noqa: E402
import ts_fixture_fonts as fonts  # noqa: E402
import ts_fixture_layout as layout  # noqa: E402
from ts_fixture_capture import (  # noqa: E402
    EXPECTED_PHASES,
    CallRecorder,
    PhaseRecorder,
    installed,
    read_phases,
)
from ts_fixture_schema import GROUPING_AST_SCHEMA  # noqa: E402

from md2ui import session  # noqa: E402
from md2ui.pipeline.layout_script_parser import LayoutNode  # noqa: E402
from md2ui.pipeline.markdown_grouper import MarkdownGrouper  # noqa: E402
from md2ui.utils.font_loader import varied_face  # noqa: E402

_DOC = "# Title\n\nKey: value\n\n- one\n- two\n\n[Go](https://example.com)\n"
_SPACER_DOC = "First paragraph.\n\n+++\n\nSecond paragraph.\n"
_SAMPLE = "data/markdown/tests-render/home-dashboards/kawsar-ahmed-macos-custom-widget/content.md"
_ICONS = "assets/icons/material-design-icons-md2ui.ttf"
_CHOICES = "data/markdown/tests/tests-choices-and-counts.md"
_FEED_SLOTS = "data/markdown/tests/tests-feed-slots.md"


def _group(text: str) -> MarkdownGrouper:
    grouper = MarkdownGrouper(text)
    grouper.process(*session.load_grouping_kit())
    return grouper


def _scene_texts(
    measure: layout.TextMeasure,
    ledger: closures.ClosureLedger | None = None,
    sample: str = _SAMPLE,
) -> dict:
    cwd = Path.cwd()
    os.chdir(ROOT)
    try:
        return layout._scene(sample, 767, [], measure, ledger)
    finally:
        os.chdir(cwd)


def _recorded(sample: str) -> tuple[layout.TextMeasure, closures.ClosureLedger, dict]:
    fonts, ledger = layout.TextMeasure(), closures.ClosureLedger()
    return fonts, ledger, _scene_texts(fonts, ledger, sample)


def _closure_replay(
    fonts: layout.TextMeasure, ledger: closures.ClosureLedger, drop: str = ""
) -> tuple[layout.TextMeasure, dict]:
    """A replaying font ledger, and the closure answers (less any *drop* kind)."""
    leaves = [r for r in fonts.records.values() if r["q"] in closures.LEAF_KINDS]
    answers = layout.replay_answers(
        r for r in [*leaves, *ledger.records.values()] if r["q"] != drop
    )
    return layout.TextMeasure(layout.replay_answers(fonts.records.values())), answers


def test_the_grouper_phases_are_the_exported_ones():
    names, _ = read_phases(MarkdownGrouper._process_once)
    assert names == list(EXPECTED_PHASES)


def test_every_phase_is_recorded_and_ends_at_the_final_tree():
    original = MarkdownGrouper.__dict__["_process_once"]
    calls, phases = CallRecorder(), PhaseRecorder()
    with installed(calls, phases):
        grouper = _group(_DOC)
    assert len(phases.passes) == 1
    assert len(phases.passes[0]) == len(EXPECTED_PHASES)
    assert grouper.ast is not None
    assert phases.passes[0][-1] == grouper.ast.to_dict()
    assert calls.criteria
    assert calls.detector
    assert MarkdownGrouper.__dict__["_process_once"] is original


def test_a_spacer_document_is_recorded_twice():
    phases = PhaseRecorder()
    with installed(phases):
        _group(_SPACER_DOC)
    assert len(phases.passes) == 2


def test_a_replay_reproduces_the_recording():
    recording = layout.TextMeasure()
    recorded = _scene_texts(recording)
    answers = layout.replay_answers(recording.records.values())
    assert _scene_texts(layout.TextMeasure(answers)) == recorded


def test_a_replay_refuses_an_unrecorded_question():
    try:
        _scene_texts(layout.TextMeasure({}))
    except KeyError:
        return
    raise AssertionError("an empty replay answered a question")


# Between them, every kind of closure question: heights and block widths
# (`Stack sections`), and code-block plans.
_BLOCKS_SAMPLE = (
    "data/markdown/tests-render/color-cycling/ulvin-omarov-meetup-app/content.md"
)
_CODE_SAMPLE = "data/markdown/tests/code-blocks.md"


def test_a_closure_replay_reproduces_the_recording():
    kinds = set()
    for sample in (_BLOCKS_SAMPLE, _CODE_SAMPLE):
        fonts, ledger, recorded = _recorded(sample)
        kinds |= {r["q"] for r in ledger.records.values()}
        replay_fonts, answers = _closure_replay(fonts, ledger)
        replay = closures.ClosureLedger(answers, replay_fonts)
        assert _scene_texts(replay_fonts, replay, sample) == recorded, sample
    assert kinds == {"layout_height", "block_width", "code_block"}, kinds


def test_a_closure_replay_refuses_an_unrecorded_subtree():
    fonts, ledger, _ = _recorded(_BLOCKS_SAMPLE)
    replay_fonts, answers = _closure_replay(fonts, ledger, drop="block_width")
    try:
        _scene_texts(
            replay_fonts, closures.ClosureLedger(answers, replay_fonts), _BLOCKS_SAMPLE
        )
    except KeyError as e:
        assert "block_width" in str(e)
        return
    raise AssertionError("a closure replay answered an unrecorded subtree")


class _LeavesMeasured(closures.ClosureLedger):
    """A closure replay whose leaf closures measure for real, with fonts."""

    def _replay_leaves(self, session: object) -> None:
        pass


def test_the_generator_may_not_ask_fonts_under_closure_replay():
    fonts, ledger, _ = _recorded(_SAMPLE)
    replay_fonts, answers = _closure_replay(fonts, ledger)
    try:
        _scene_texts(replay_fonts, _LeavesMeasured(answers, replay_fonts))
    except RuntimeError as e:
        assert "inside the generator" in str(e)
        return
    raise AssertionError("the generator measured a font under closure replay")


def test_the_subtree_digest_is_the_documented_one():
    # The example in ts_fixture_closures' docstring; flow_run 7 is renumbered 1.
    leaf = LayoutNode(type="-", ratios=[1.0], children=[], content_id="0.1", flow_run=7)
    row = LayoutNode(type="row", ratios=[0.5, 0.5], children=[leaf])
    assert closures.subtree_digest(row) == (
        "431d650af1d2cff1050ab153d7df4b0a2bc29927f5f31bb49a4bd458f189a312"
    )
    leaf.flow_run = 3
    assert closures.subtree_digest(row) == (
        "431d650af1d2cff1050ab153d7df4b0a2bc29927f5f31bb49a4bd458f189a312"
    )


def test_numbers_are_written_as_ecmascript_writes_them():
    cases = {
        100.0: "100",
        -0.0: "0",
        0.1: "0.1",
        1e-6: "0.000001",
        1e-07: "1e-7",
        1e20: "100000000000000000000",
        1e21: "1e+21",
        1 / 3: "0.3333333333333333",
        7: "7",
    }
    for value, text in cases.items():
        assert closures.js_number(value) == text, (value, closures.js_number(value))


def test_a_variable_instance_is_its_font_file_and_coordinates():
    """An `Emoji weight` / `fill` / `grade` / `optical size` instance has no file
    of its own: it exports as its font's file plus the axis coordinates."""
    if sys.platform != "darwin":
        raise unittest.SkipTest(
            "an instance's name is CoreText's; FreeType names it otherwise"
        )
    path = ROOT / _ICONS
    instance = layout.face_name(varied_face(str(path), 500, 0.5, -25, 20))
    base = fonts._face_of_file(path)
    assert base is not None
    assert fonts.variable_instance(base, path) is None
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / "measure" / "767").mkdir(parents=True)
        records = [{"q": "advance", "face": f, "size": 15.0} for f in (base, instance)]
        lines = "".join(json.dumps(r) + "\n" for r in records)
        (out / "measure" / "767" / "doc.jsonl").write_text(lines)
        code = SimpleNamespace(text_style=SimpleNamespace(font_name=None))
        plain = SimpleNamespace(font_paths=[], code_blocks=code)
        theme = (plain, {"font_path": _ICONS})
        manifest = fonts.export_fonts(out, {"t": theme}, {"doc": "t"})
    name = "fonts/material-design-icons-md2ui.ttf"
    assert manifest["faces"] == {base: name, instance: name}, manifest["faces"]
    assert list(manifest["files"]) == [name]
    assert manifest["files"][name]["face"] == base
    assert manifest["axes"] == {
        instance: {"FILL": 0.5, "GRAD": -25.0, "opsz": 20.0, "wght": 500.0}
    }, manifest["axes"]


def test_a_named_variable_instance_takes_its_coordinates_from_the_font():
    """At a named instance's coordinates the system names the face for it
    (`_Light`), not by its axes; the coordinates come from the font's `fvar`."""
    if sys.platform != "darwin":
        raise unittest.SkipTest(
            "an instance's name is CoreText's; FreeType names it otherwise"
        )
    path = ROOT / _ICONS
    light = layout.face_name(varied_face(str(path), 300, 0, 0, 24))
    assert light.split("|")[1].endswith("_Light"), light
    assert fonts.variable_instance(light, path) == {
        "FILL": 0.0,
        "GRAD": 0.0,
        "opsz": 24.0,
        "wght": 300.0,
    }


def test_an_auto_layout_records_the_tree_it_shows():
    """Under ``Layout: Auto`` a band builds both layouts and shows one: the tree
    recorded before the bakes is the shown one's, not the last one built."""
    sample = "data/markdown/tests-render/banking-financial/figma-ai-generated-banking-dashboard/content.md"
    load_theme = session.load_theme

    def auto_theme(path):
        theme = load_theme(path)
        theme.root.layout = "auto"
        return theme

    session.load_theme = auto_theme
    cwd = Path.cwd()
    os.chdir(ROOT)
    try:
        scene = layout._scene(sample, 1280, [], layout.TextMeasure())
    finally:
        os.chdir(cwd)
        session.load_theme = load_theme
    assert '"bento": true' in scene["layout"], "the sample no longer tiles at 1280"
    assert '"bento": true' in scene["layout-generated"]


def test_a_missing_code_family_is_recorded_as_the_monospace_md2ui_draws() -> None:
    """A code block's family neither loaded nor installed is drawn in the
    platform's monospace (`resolve_code_typeface`), so the alias says so; the
    same name in prose would be the proportional default."""
    missing = "No Such Code Font md2ui"
    code = SimpleNamespace(text_style=SimpleNamespace(font_name=missing))
    plain = SimpleNamespace(font_paths=[], code_blocks=code)
    resolved = {"code_blocks": {"text_style": {"font_name": missing}}}
    aliases = fonts.family_aliases(plain, resolved)
    mono = fonts.resolve_typeface("monospace", 400, False, {}).getFamilyName()
    assert aliases == {missing: mono}, aliases


def test_the_schema_holds_a_segmented_run_a_count_and_feed_slots():
    # The node object is closed: a key `to_dict` writes and the schema lacks
    # fails md2ui's own fixtures, and md2ui-ts cannot regenerate C1 from it.
    for doc, keys in (
        (_CHOICES, ('"segmented_run": true', '"count": true')),
        (_FEED_SLOTS, ('"feed_slots": [',)),
    ):
        tree = _group((ROOT / doc).read_text()).ast
        assert tree is not None
        d = tree.to_dict()
        flat = json.dumps(d)
        assert all(key in flat for key in keys), (doc, keys)
        jsonschema.validate(d, GROUPING_AST_SCHEMA)


_MARKERS = "data/markdown/tests/marker-background-options/content.md"


def test_a_list_marker_is_recorded_as_an_outline_question():
    """A list marker's ink comes from its glyph outlines (``_text_ink``), so the
    recording asks it as an ``outline`` question, as it asks a ring label's, and
    the replay answers it from there."""
    recording = layout.TextMeasure()
    recorded = _scene_texts(recording, sample=_MARKERS)
    outlined = {r["text"] for r in recording.records.values() if r["q"] == "outline"}
    assert {"1)", "2."} <= outlined, outlined
    answers = layout.replay_answers(recording.records.values())
    assert _scene_texts(layout.TextMeasure(answers), sample=_MARKERS) == recorded


TESTS = [
    test_the_grouper_phases_are_the_exported_ones,
    test_every_phase_is_recorded_and_ends_at_the_final_tree,
    test_a_spacer_document_is_recorded_twice,
    test_a_replay_reproduces_the_recording,
    test_a_replay_refuses_an_unrecorded_question,
    test_a_closure_replay_reproduces_the_recording,
    test_a_closure_replay_refuses_an_unrecorded_subtree,
    test_the_generator_may_not_ask_fonts_under_closure_replay,
    test_the_subtree_digest_is_the_documented_one,
    test_numbers_are_written_as_ecmascript_writes_them,
    test_a_variable_instance_is_its_font_file_and_coordinates,
    test_a_named_variable_instance_takes_its_coordinates_from_the_font,
    test_an_auto_layout_records_the_tree_it_shows,
    test_a_missing_code_family_is_recorded_as_the_monospace_md2ui_draws,
    test_the_schema_holds_a_segmented_run_a_count_and_feed_slots,
    test_a_list_marker_is_recorded_as_an_outline_question,
]


if __name__ == "__main__":
    print("TS Fixture Hook Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
