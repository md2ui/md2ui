"""Datapoint displays inside the broader Drawing elements theme section.

A number in a document can stay text, or it can become a bar, a ring, a date chip,
or a line. This module owns that decision for one node. It inspects a node — and,
for tables, a whole group of them — and stamps the display kind the renderer will
later paint. It paints nothing and chooses no colours.

The two halves:

  * ``_try_*`` decide for a single leaf or its immediate container;
  * ``_flag_table_groups`` decides across a group, because "these rows are a
    table" is a property of the run, not of any row in it.

What a chart value is, and which runs draw as a chart or as several lines, is
``grouper_charts``. The ``_dp_*`` and ``_subtree_*`` vocabulary both are written
in is ``grouper_display_vocab``.
"""

from md2ui.pipeline.grouper_charts import _parse_line
from md2ui.pipeline.grouper_display_vocab import (
    _bare_content,
    _clear_datapoint_displays,
    _covering_dp,
    _dp_kind,
    _dp_scalar,
    _dp_unit,
    _subtree_dps,
    _subtree_text,
)
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.value_format import declared_unit, is_bare


def _stamp_table_role(node: "MarkdownGroupNode", role: str) -> None:
    """Stamp ``role`` onto every descendant that has no ``table_role`` yet.

    A datapoint-split cell becomes a group whose pieces are NEW nodes
    without a role; inheriting the cell's role lets the renderer draw
    every piece in the themed table cell font.
    """
    for child in node.children:
        if child.table_role is None:
            child.table_role = role
        _stamp_table_role(child, role)


def _flag_table_groups(node: "MarkdownGroupNode") -> None:
    """Post-order: mark table containers with ``table_group``.

    A table is a contiguous run of ``table_header``/``table_row`` children
    (a new run starts at each ``table_header``, so back-to-back tables in
    one container stay separate). When the run is ALL of a node's children
    the existing container is flagged in place; otherwise the run is
    wrapped in a new flagged ``group`` node. Runs before node_ids are
    assigned (``fingerprints()``), so inserting a wrapper is safe.

    Runs AFTER the Phase 5 datapoint separation, so cells split into
    pieces already exist here — each cell's ``table_role`` is propagated
    to its descendants (split pieces inherit the cell font).

    Time: O(K), Space: O(K) worst case (rebuilt child lists).
    """
    for child in node.children:
        _flag_table_groups(child)

    table_types = (NodeType.TABLE_HEADER, NodeType.TABLE_ROW)
    if not any(c.type in table_types for c in node.children):
        return

    # Propagate each cell's role into its (split) subtree, for every row
    # in this container — runs for both the flag-in-place and wrap paths.
    for row in node.children:
        if row.type not in table_types:
            continue
        for cell in row.children:
            if cell.table_role is not None and cell.children:
                _stamp_table_role(cell, cell.table_role)

    # Segment children into table runs (header starts a new run).
    runs: list[tuple[int, int]] = []  # [start, end) index ranges
    i = 0
    n = len(node.children)
    while i < n:
        if node.children[i].type not in table_types:
            i += 1
            continue
        j = i + 1
        while j < n and node.children[j].type == NodeType.TABLE_ROW:
            j += 1
        runs.append((i, j))
        i = j

    if len(runs) == 1 and runs[0] == (0, n) and not node.content:
        node.table_group = True
        return

    new_children: list[MarkdownGroupNode] = []
    pos = 0
    for start, end in runs:
        new_children.extend(node.children[pos:start])
        wrapper = MarkdownGroupNode(type=NodeType.GROUP)
        wrapper.table_group = True
        wrapper.children = node.children[start:end]
        new_children.append(wrapper)
        pos = end
    new_children.extend(node.children[pos:])
    node.children = new_children


# Star-rating labels on SCORE datapoints (`4/5 stars`); those ratios stay
# text — the starred-rating rendering owns them.
_STAR_SCORE_LABELS = ("stars", "star", "rating")


def _try_leaf_display(node: "MarkdownGroupNode", star_context: bool) -> None:
    dp = _covering_dp(node)
    if dp is not None:
        kind = _dp_kind(dp)
        v = dp.get("value")
        # `Mon-15` / `Jun-5` — weekday/month + day-of-month, no year, joined by
        # a DASH. The spaced spelling is the same date and is detected as one,
        # but it is also how every sentence writes a date ("Delivered Jun 5"),
        # so drawing it left an author no way to decline; the dash is the
        # authored request, and `Mon\-15` declines even that.
        if (
            kind == "date"
            and isinstance(v, dict)
            and v.get("subtype") in ("weekday_day", "partial")
            and v.get("connector") == "dash"
            and not v.get("has_year")
            and v.get("day") is not None
        ):
            node.datapoint_display = "date_chip"
            node.datapoint_payload = {
                "key": dp["matched"].split("-")[0].rstrip(". "),
                "day": int(v["day"]),
                "subtype": v["subtype"],
            }
            return
        # Bare `4/8`.
        if (
            kind == "ratio"
            and not star_context
            and isinstance(v, dict)
            and v.get("format") == "slash"
        ):
            node.datapoint_display = "ratio_bar"
            node.datapoint_payload = {
                "value": float(v["left"]),
                "max": float(v["right"]),
                "text": _bare_content(node.content),
            }
            return
    # `25/100 progress` — one SCORE fraction, remainder exactly one word.
    if len(node.data_points) == 1 and not star_context:
        dp = node.data_points[0]
        v = dp.get("value")
        if _dp_kind(dp) == "score" and isinstance(v, dict):
            label = str(v.get("label") or "")
            if label.lower() in _STAR_SCORE_LABELS:
                return
            content = _bare_content(node.content)
            matched = dp["matched"].strip()
            if content.startswith(matched):
                rest = content[len(matched) :].strip()
                unit = rest or label
                if unit and " " not in unit:
                    node.datapoint_display = "unit_ratio"
                    node.datapoint_payload = {
                        "value": float(v["score"]),
                        "max": float(v["max"]),
                        "unit": unit,
                    }
                    return
    # `75/100g` — TWO datapoints with a bare `/` between them, the second
    # carrying the unit. A value never divides a line (ADR-205), so the
    # construct stays one leaf. It must BE the leaf, wrappers aside, as the
    # SCORE fraction above must: a sentence that mentions `75/100g` stays text,
    # where a ring would draw the fraction and drop every word around it.
    if len(node.data_points) == 2 and not star_context:
        left, right = node.data_points
        between = node.content[left["end"] : right["start"]].strip()
        construct = node.content[left["start"] : right["end"]].strip()
        if between == "/" and _bare_content(node.content) == construct:
            value = _dp_scalar(left)
            mx = _dp_scalar(right)
            unit = _dp_unit(right)
            if value is not None and mx and unit:
                node.datapoint_display = "unit_ratio"
                node.datapoint_payload = {
                    "value": value,
                    "max": mx,
                    "unit": unit,
                }


def _try_container_display(node: "MarkdownGroupNode", star_context: bool) -> None:
    if node.type == NodeType.KEY_VALUE:
        _try_kv_display(node)
        return
    if star_context:
        return
    kids = node.children
    leaf_dps = [_covering_dp(c) for c in kids]
    texts = [_bare_content(c.content) for c in kids]
    plain = [not c.children and not c.data_points for c in kids]
    # `205 MB of 270 MB` draws no bar: a horizontal bar is spelled ONE way, as
    # the key-value percentage (`Elapsed: 45%`). "of" is a word, so it carries
    # no punctuation an author could escape to decline the drawing.
    # Reached only when the author cuts around a lone slash (`75 | / | 100g`):
    # [number, "/", quantity-with-unit]. A bare `75/100g` is one leaf, above.
    if (
        len(kids) == 3
        and leaf_dps[0] is not None
        and leaf_dps[2] is not None
        and plain[1]
        and texts[1] == "/"
    ):
        value = _dp_scalar(leaf_dps[0])
        mx = _dp_scalar(leaf_dps[2])
        unit = _dp_unit(leaf_dps[2])
        if value is not None and mx and unit:
            node.datapoint_display = "unit_ratio"
            node.datapoint_payload = {
                "value": value,
                "max": mx,
                "unit": unit,
            }
        return
    # `750/1800` + `Kcal` — SCORE fraction beside its one-word unit.
    if (
        len(kids) == 2
        and leaf_dps[0] is not None
        and plain[1]
        and texts[1]
        and " " not in texts[1]
        and _dp_kind(leaf_dps[0]) == "score"
    ):
        v = leaf_dps[0].get("value")
        if isinstance(v, dict) and str(v.get("label") or "").lower() not in (
            _STAR_SCORE_LABELS
        ):
            node.datapoint_display = "unit_ratio"
            node.datapoint_payload = {
                "value": float(v["score"]),
                "max": float(v["max"]),
                "unit": texts[1],
            }
            return
    # A bare datapoint beside a short worded label draws no stat tile: that
    # would be decided from the value's WORDS, not from punctuation the author
    # wrote, so no spelling could decline it. `## Text Styles` -> `Key` /
    # `Value` styles every pair the same way instead.


def _try_kv_display(node: "MarkdownGroupNode") -> None:
    key = next((c for c in node.children if c.type == NodeType.KEY), None)
    value = next((c for c in node.children if c.type == NodeType.VALUE), None)
    if key is None or value is None:
        return
    dps = _subtree_dps(value)
    # The whole-value paths (ratio ring, percent bar) need the value to be a
    # single datapoint covering the whole value text.
    if len(dps) == 1:
        dp = dps[0]
        kind = _dp_kind(dp)
        v = dp.get("value")
        vtext = _subtree_text(value)
        matched = dp["matched"].strip()
        covered = vtext.strip().strip("*_`").strip() == matched
        ratio = (
            kind == "ratio"
            and covered
            and isinstance(v, dict)
            and v.get("format") == "slash"
        )
        ends = (
            (float(v["left"]), float(v["right"]))
            if ratio and isinstance(v, dict)
            else None
        )
        # `Disk (GB): 61/128` — the key declares the unit, as a chart's does:
        # drawn as `Disk: 61/128 GB` is, the key above and the unit in the ring.
        shown = declared_unit(_subtree_text(key)) if ratio else None
        leaf = value
        while len(leaf.children) == 1:
            leaf = leaf.children[0]
        if ends and shown and not leaf.children:
            _clear_datapoint_displays(node)
            leaf.datapoint_display = "unit_ratio"
            leaf.datapoint_payload = {
                "value": ends[0],
                "max": ends[1],
                "unit": shown,
            }
            return
        # `Minutes: 7/8` — the key names the ratio's unit (ring/bar label).
        if ends:
            # The pair display owns the whole subtree (the ratio leaf may
            # already carry its own leaf-level flag from the value's walk).
            _clear_datapoint_displays(node)
            node.datapoint_display = "unit_ratio"
            node.datapoint_payload = {
                "value": ends[0],
                "max": ends[1],
                "unit": _subtree_text(key),
                "text": matched,
                "from_kv": True,
            }
            return
        # `GPT-5.5: 50%` / `Progress: 60% Complete` → key/value + bar.
        if (
            kind == "percentage"
            and vtext.startswith(matched)
            and len(vtext.split()) <= 3
        ):
            scalar = _dp_scalar(dp)
            if scalar is not None:
                _clear_datapoint_displays(node)
                node.datapoint_display = "kv_percent_bar"
                node.datapoint_payload = {
                    "percent": scalar,
                    "value_text": vtext,
                }
            return
    # `Price: $710 → $713 → $720` → key, last value and a line over the chain.
    shown = declared_unit(_subtree_text(key))
    points = _parse_line(value, declared=shown is not None)
    if isinstance(points, list):
        _clear_datapoint_displays(node)
        node.datapoint_display = "line_chart"
        node.datapoint_payload = {"points": points}
        # `High (°C): 24 → 23 → 21`: the key declares the unit bare values are in.
        if shown and all(is_bare(p["text"]) for p in points):
            node.datapoint_payload["display_unit"] = shown
        return
    # `Revenue: $129,201.40` draws no stat tile (see _try_container_display):
    # a pair is styled by the theme's `Key` / `Value` blocks, the same way
    # every time, rather than by what its value happens to say.
