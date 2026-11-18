"""Cuts a line makes around a value.

The last of the three inline cuts. Where separator splitting divides at a typed
character and element splitting divides around a thing, this module divides a
line around the *key* that labels a value.

It does not divide around the value: a value stays in the leaf it was
written in, carrying a ``data_points`` annotation. The rule is annotate
always, split only when a display draws the split NODE, and none does. **A value never makes a line read as a
RUN**, so the elements beside one stay inline unless the author separated them:
``⭐ Q1 2026`` is one leaf, ``⭐ - Q1 2026`` is a badge and a value.

What remains is the key-value pass, and it keeps one hazard: a value carries its own emphasis, the line carries emphasis of its own, and a cut
must not hand one to the other.
"""

import re

from md2ui.pipeline.data_point_detector import DataPointType
from md2ui.pipeline.grouper_ranges import _colon_is_glued, _make_is_safe
from md2ui.pipeline.grouper_separator_splits import _drop_orphan_column_colon
from md2ui.pipeline.grouper_types import NodeType


# Key-value patterns, detected in the separation walk. The markers are kept in
# the key and value text.
_KV_BOLD_FULL_RE = re.compile(
    r"^\*\*([^*:]+):([^*]*)\*\*\s*$|^__([^_:]+):([^_]*)__\s*$"
)


_KV_BOLD_END_RE = re.compile(
    r"^\*\*([^*:]+):\*\*\s*(.+)$|^__([^_:]+):__\s*(.+)$", re.DOTALL
)


_KV_BOLD_ITALIC_END_RE = re.compile(r"^\*\*\*([^*:]+):\*\*\*\s*(.+)$", re.DOTALL)


_KV_ITALIC_RE = re.compile(r"^\*([^*:]+):\*\s*(.+)$|^_([^_:]+):_\s*(.+)$", re.DOTALL)


_KV_STRIKE_END_RE = re.compile(r"^~~([^~:]+):~~\s*(.+)$", re.DOTALL)


# Datapoint types this split leaves alone, because a LATER pass owns them.
#
# EMOJI and LINK are peeled only when they sit at the leading or trailing
# boundary of a node's (style-wrap-adjusted) inner content, by
# `_peel_boundary_dps_walk`; mid-text occurrences stay inline with a data_point
# annotation so paragraphs aren't fragmented. IMAGE is cut out by
# `_split_images`, in the same walk just ahead of that peel, and is detected at all only to PROTECT
# its span (see detector_scope) -- so extracting it here would both pre-empt
# that pass and give the node the wrong type. DRAWING_ELEMENT is the same: its
# node is made by grouper_sliders / grouper_drawing_elements after this pass.
#
# The other reader, `_boundary_trimmed_text`, hides these from the SPLIT
# CRITERIA for the matching reason: what sits at the edge of a line says little
# about the prose beside it. IMAGE changes nothing there, so the two questions
# share one list rather than growing a second.
_BOUNDARY_DP_TYPES = (
    DataPointType.EMOJI,
    DataPointType.LINK,
    DataPointType.IMAGE,
    DataPointType.DRAWING_ELEMENT,
)


# The value types this pass extracts into DATAPOINT nodes: none. Every value
# stays as a ``data_points`` annotation on its leaf; the boundary types above
# continue through their later structural passes. Detection alone is not an
# instruction to split: the rule is "annotate always, split only when a display
# draws the split NODE", and every display reads the leaf or the line instead:
#
# SCORE: `unit_ratio` needs the unit still beside the fraction
# (`750/1800 Kcal`), so it reads an UNSPLIT leaf.
#
# RATIO: `_try_leaf_display` reads any leaf carrying one slash-format ratio,
# and an unsplit `4/8` line is exactly that leaf.
#
# PERCENTAGE: its consumers read the line, not the piece -- `kv_percent_bar`
# sits on the KEY_VALUE, and a chart group is a run of `Key: n%` rows.
#
# A value never makes a line read as a RUN, so the elements beside one stay
# inline unless the AUTHOR separated them: `⭐ Q1 2026` is one leaf and
# `⭐ - Q1 2026` is a badge and a value.


def _split_kv_styled_scan(
    content: str,
    protected: list[tuple[int, int]] | None = None,
):
    """Detect markdown key-value patterns.

    Preserves the original markers in the output key and value text.

    *protected* is a list of ``(start, end)`` index ranges from annotated
    data points.  If the colon that would serve as the key/value separator
    falls inside one of these ranges (e.g. ``8:00 AM``), the match is
    rejected and ``None`` is returned.

    Handles (first match wins):
      ``***key:*** value``  →  key=``***key***``, value=``value``
      ``**key: value**``    →  key=``**key**``,   value=``**value**``
      ``**key:** value``    →  key=``**key**``,   value=``value``
      ``*key:* value``      →  key=``*key*``,     value=``value``
      Underscore variants of the above.

    Returns ``[(label, text)]`` or ``None``.

    Time: O(C + R log R), Space: O(C).
    """
    s = content.strip()
    offset = len(content) - len(content.lstrip())  # leading-whitespace shift

    sorted_prot = sorted(protected or [])

    _safe = _make_is_safe(sorted_prot, content)

    def colon_is_safe(colon_pos_in_s: int) -> bool:
        """True when the colon is outside every protected interval, not
        backslash-escaped — ``**Key\\:** value`` is a label, not a pair — and
        followed by a space: ``**H:25°**`` is text, as ``H:25°`` is."""
        return _safe(offset + colon_pos_in_s) and not _colon_is_glued(s, colon_pos_in_s)

    m = _KV_BOLD_FULL_RE.match(s)
    if m:
        key_grp = m.group(1) if m.group(1) is not None else m.group(3)
        val_raw = (m.group(2) if m.group(1) is not None else m.group(4)).strip()
        colon_pos = 2 + len(key_grp)  # after "**"/"__" + key text
        if val_raw and colon_is_safe(colon_pos):
            if m.group(1) is not None:
                key, val = f"**{m.group(1).strip()}**", f"**{val_raw}**"
            else:
                key, val = f"__{m.group(3).strip()}__", f"__{val_raw}__"
            if key:
                return [(NodeType.KEY, key), (NodeType.VALUE, val)]

    m = _KV_BOLD_ITALIC_END_RE.match(s)
    if m:
        key_grp = m.group(1)
        colon_pos = 3 + len(key_grp)  # after "***" + key text
        if colon_is_safe(colon_pos):
            key, val = f"***{m.group(1).strip()}***", m.group(2).strip()
            if key and val:
                return [(NodeType.KEY, key), (NodeType.VALUE, val)]

    m = _KV_BOLD_END_RE.match(s)
    if m:
        key_grp = m.group(1) if m.group(1) is not None else m.group(3)
        colon_pos = 2 + len(key_grp)
        if colon_is_safe(colon_pos):
            if m.group(1) is not None:
                key, val = f"**{m.group(1).strip()}**", m.group(2).strip()
            else:
                key, val = f"__{m.group(3).strip()}__", m.group(4).strip()
            if key and val:
                return [(NodeType.KEY, key), (NodeType.VALUE, val)]

    m = _KV_ITALIC_RE.match(s)
    if m:
        key_grp = m.group(1) if m.group(1) is not None else m.group(3)
        colon_pos = 1 + len(key_grp)  # after "*"/"_" + key text
        if colon_is_safe(colon_pos):
            if m.group(1) is not None:
                key, val = f"*{m.group(1).strip()}*", m.group(2).strip()
            else:
                key, val = f"_{m.group(3).strip()}_", m.group(4).strip()
            if key and val:
                return [(NodeType.KEY, key), (NodeType.VALUE, val)]

    m = _KV_STRIKE_END_RE.match(s)
    if m:
        colon_pos = 2 + len(m.group(1))  # after "~~" + key text
        if colon_is_safe(colon_pos):
            key, val = f"~~{m.group(1).strip()}~~", m.group(2).strip()
            if key and val:
                return [(NodeType.KEY, key), (NodeType.VALUE, val)]

    # Nested wrappers: ``~~**Key:**~~ value``. The colon sits inside the
    # inner emphasis, so _KV_STRIKE_END_RE's ``[^~:]+`` key group can never
    # match and the pair would fall through to the plain-colon path, which
    # splits mid-marker and leaves the re-balancer to scramble both sides.
    # Peel the strike wrapper, re-run every branch above on what is left,
    # then put the wrapper back — one branch covers ``~~*Key:*~~``,
    # ``~~**Key:**~~`` and ``~~***Key:***~~`` instead of a regex per
    # combination. Terminates because the re-entry string is always shorter.
    if s.startswith("~~"):
        close = s.find("~~", 2)
        if close > 2:
            whole = close + 2 == len(s)  # ~~**Key: value**~~
            inner_rest = s[2:close] + s[close + 2 :]
            # colon_is_safe resolves against the ORIGINAL content, and the
            # colon it tests always sits inside the key — i.e. before
            # ``close`` — so shifting every protected range by the leading
            # whitespace plus the two peeled tildes is exact over that span.
            shift = offset + 2
            nested = _split_kv_styled_scan(
                inner_rest, [(a - shift, b - shift) for a, b in sorted_prot]
            )
            if nested and len(nested) == 2:
                (_, k), (_, v) = nested
                return [
                    (NodeType.KEY, f"~~{k}~~"),
                    (NodeType.VALUE, f"~~{v}~~" if whole else v),
                ]

    return None


def _split_kv_styled(
    content: str,
    protected: list[tuple[int, int]] | None = None,
):
    """:meth:`_split_kv_styled_scan`, with a stranded column colon dropped.

    ``**Key:** : value`` holds both colon syntaxes: the key-value colon,
    tight to its key, and the spaced COLUMN separator. The key-value one
    cuts first and leaves the column colon leading the value, where nothing
    downstream can see it — the same strand :meth:`_plain_colon_kv` clears
    on the unstyled spelling. One wrapper rather than the strip repeated at
    each of the scanner's six returns.
    """
    pair = _split_kv_styled_scan(content, protected)
    if pair is None or len(pair) != 2:
        return pair
    (key_label, key), (value_label, value) = pair
    value = _drop_orphan_column_colon(value)
    return [(key_label, key), (value_label, value)] if value else None
