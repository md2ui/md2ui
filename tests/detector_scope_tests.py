"""Unit tests for the detector's SCOPE — which types the pipeline scans for.

The rule these lock is ADR-102: a type is in ``_PIPELINE_TYPES`` because
something consumes it — a ``## Drawing elements`` family draws it, the grouper
turns it into a node, or it guards a span a shorter drawing pattern would
otherwise win. The two entry points are not interchangeable.

Run with: uv run tests/detector_scope_tests.py
"""

from md2ui.pipeline.data_point_detector import DataPointDetector
from md2ui.pipeline.data_point_types import DataPointType
from md2ui.pipeline.detector_scope import (
    _DRAWING_TYPES,
    _GUARD_TYPES,
    _PIPELINE_TYPES,
)


def test_the_two_halves_partition_the_scope():
    assert _PIPELINE_TYPES == _DRAWING_TYPES | _GUARD_TYPES
    assert not (_DRAWING_TYPES & _GUARD_TYPES), (
        "a type is drawn OR a guard; overlapping means one of the two reasons is wrong"
    )
    assert _PIPELINE_TYPES < set(DataPointType), "the scope must be a strict subset"
    print("  ✓  drawing and guard sets partition the pipeline scope")


def test_every_scope_member_is_a_real_type():
    for kind in _PIPELINE_TYPES:
        assert isinstance(kind, DataPointType), kind
    print("  ✓  every member is a DataPointType, not a string")


def test_the_drawing_set_matches_what_the_displays_consume():
    # The guard against silent drift. The five value types stay because
    # `## Fixed colors -> ### Datapoints` pins a color BY DETECTED TYPE
    # (`render_colors._dp_pin`), so each one is read on every leaf. Drop
    # one and a theme's pin on that name silently stops firing.
    drawn = {k.value for k in _DRAWING_TYPES}
    for needed in ("date", "ratio", "score", "percentage", "emoji", "link"):
        assert needed in drawn, f"{needed} is consumed downstream but out of scope"
    for pinned in ("currency", "number", "quantity", "file_size", "rate", "change"):
        assert pinned in drawn, (
            f"### Datapoints can pin {pinned}, so it must be scanned"
        )
    print("  ✓  the drawing set covers every type a display or a pin consumes")


def test_detect_pipeline_returns_only_scope_types():
    detector = DataPointDetector()
    line = "Invoice #4567 on Aug 12 for $50, 35 years old, 12% of 4/8 at 9:00 AM"
    assert all(m["type"] in _PIPELINE_TYPES for m in detector.detect_pipeline(line))
    print("  ✓  detect_pipeline never returns an out-of-scope type")


def test_detect_all_is_the_wider_view():
    detector = DataPointDetector()
    # `35 years old` is an AGE, which nothing draws and no guard needs.
    kinds = {m["type"] for m in detector.detect_all("35 years old")}
    assert DataPointType.AGE in kinds
    assert DataPointType.AGE not in _PIPELINE_TYPES
    assert not any(
        m["type"] is DataPointType.AGE for m in detector.detect_pipeline("35 years old")
    )
    print("  ✓  detect_all sees what the pipeline deliberately does not")


def test_a_guard_still_wins_its_span():
    # The reason guards are kept at all: _remove_overlaps keeps the LONGEST
    # match, so without TIME the clock would be read as a RATIO and drawn as a
    # progress bar. This is the behaviour scripts/audit_detector_scope.py sweeps.
    detector = DataPointDetector()
    spans = {(m["type"], m["matched"]) for m in detector.detect_pipeline("at 9:00 AM")}
    assert (DataPointType.TIME, "9:00 AM") in spans, spans
    assert not any(k is DataPointType.RATIO for k, _ in spans), (
        "9:00 must not read as a ratio — that would draw a bar for a clock"
    )
    print("  ✓  a guard type still wins its span from the drawing patterns")


def test_enum_values_are_unique_and_serializable():
    # to_dict() writes `dp_<value>`, and render_colors keys ## Fixed colors on
    # that string, so the values are a public surface.
    values = [k.value for k in DataPointType]
    assert len(values) == len(set(values))
    assert all(v == v.lower() and " " not in v for v in values), values
    print("  ✓  enum values are unique, lowercase and space-free")


TESTS = [
    test_the_two_halves_partition_the_scope,
    test_every_scope_member_is_a_real_type,
    test_the_drawing_set_matches_what_the_displays_consume,
    test_detect_pipeline_returns_only_scope_types,
    test_detect_all_is_the_wider_view,
    test_a_guard_still_wins_its_span,
    test_enum_values_are_unique_and_serializable,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
    print(f"\nAll {len(TESTS)} tests passed.")
