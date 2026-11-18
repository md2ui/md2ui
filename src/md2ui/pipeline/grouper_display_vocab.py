"""The datapoint vocabulary the drawn displays and the charts are written in.

What kind a datapoint is, its scalar value, its unit, the datapoints under a
subtree, and clearing the display flags a wider display takes over. Read by
``grouper_displays`` (one node's display) and ``grouper_charts`` (a run's), so
neither imports the other for it.
"""

from md2ui.pipeline.grouper_types import MarkdownGroupNode


def _dp_kind(dp: dict) -> str:
    """Datapoint type as its plain string name ("ratio", "score", ...).

    In-pipeline entries carry the DataPointType enum in ``dp["type"]``."""
    t = dp.get("type")
    return getattr(t, "value", str(t))


def _dp_scalar(dp: dict) -> float | None:
    """The datapoint's magnitude as a float, whatever its value shape
    (plain number, or a dict keyed value/amount/score)."""
    v = dp.get("value")
    if isinstance(v, dict):
        for k in ("value", "amount", "score"):
            if k in v:
                v = v[k]
                break
        else:
            return None
    if v is None:
        return None
    try:
        return float(v)  # Decimal/int/float/str all coerce
    except (TypeError, ValueError):
        return None


def _dp_unit(dp: dict) -> str | None:
    v = dp.get("value")
    if isinstance(v, dict):
        u = v.get("unit") or v.get("currency")
        if u:
            return str(u)
    return None


def _bare_content(text: str) -> str:
    """Content with the preserved bold/italic/code markers stripped, for
    comparing against a datapoint's matched span."""
    return text.strip().strip("*_`").strip()


def _covering_dp(node: "MarkdownGroupNode") -> dict | None:
    """The node's single datapoint when it spans the whole content."""
    if node.children or len(node.data_points) != 1:
        return None
    dp = node.data_points[0]
    if _bare_content(node.content) == dp["matched"].strip():
        return dp
    return None


def _subtree_text(node: "MarkdownGroupNode") -> str:
    if node.content.strip():
        return node.content.strip()
    parts = [_subtree_text(c) for c in node.children]
    return " ".join(p for p in parts if p)


def _subtree_dps(node: "MarkdownGroupNode") -> list[dict]:
    out = list(node.data_points)
    for c in node.children:
        out.extend(_subtree_dps(c))
    return out


def _clear_datapoint_displays(node: "MarkdownGroupNode") -> None:
    node.datapoint_display = None
    node.datapoint_payload = None
    for c in node.children:
        _clear_datapoint_displays(c)
