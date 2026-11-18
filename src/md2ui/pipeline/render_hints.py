"""Per-node render hints: how one image (or region) is drawn.

An author writes them on an image URL — ``![alt](photo.jpg?md2ui.shape=circle)``
— and ``sanitize_url_props`` turns the params into an entry with optional
``<prop>_wide`` twins; ``render_properties_from`` resolves that entry at a width.
A repeated run's members vote (``poll_render``) so the run is drawn alike. Hints
never change the structural layout, only how a node is rendered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


def _mode(values: list):
    """Most frequent value; ties break toward the earliest occurrence."""
    counts: dict = {}
    for i, v in enumerate(values):
        entry = counts.setdefault(v, [0, i])
        entry[0] += 1
    return max(counts.items(), key=lambda kv: (kv[1][0], -kv[1][1]))[0]


# Base property name -> RenderProperties field (drives _wide resolution).
_RENDER_FIELDS: tuple[str, ...] = (
    "aspect_ratio",
    "max_width",
    "min_width",
    "max_height",
    "shape",
    "fit",
    "corner_radius",
    "bleed",
    "content_align",
)


@dataclass
class RenderProperties:
    """One node's rendering hints (3 kinds: image / text / group).

    Each field is optional; ``None`` means "no hint".
    """

    aspect_ratio: str | None = None  # image:  "W:H"
    max_width: int | None = None  # image:  pixels
    min_width: int | None = None  # image:  pixels; below max_width
    max_height: int | None = None  # image:  pixels; excludes the two widths
    shape: str | None = None  # image:  "circle"
    fit: str | None = None  # image:  contain|cover (None = by kind)
    corner_radius: int | None = None  # image:  px (0 = explicitly square)
    bleed: bool | None = None  # image:  run over the level's padding
    content_align: str | None = None  # group/leaf/root: left|center|right

    def to_render_dict(self) -> dict:
        """Plain dict (``None`` fields dropped) to attach to a ``LayoutNode``."""
        out: dict = {}
        for field in _RENDER_FIELDS:
            val = getattr(self, field)
            if val is not None:
                out[field] = val
        return out


def render_properties_from(props: dict, wide: bool) -> RenderProperties:
    """Resolve one node's hint entry to RenderProperties.

    ``props`` is the per-node mapping (may carry ``<prop>`` and a ``<prop>_wide``
    twin). When *wide* is True each property takes its ``_wide`` value if present
    (``default`` -> dropped), otherwise inherits the base value; when False only
    base values are used. An absent property stays ``None``.
    """

    def resolve(field: str):
        val = props.get(field)
        twin = f"{field}_wide"
        if wide and twin in props:
            wv = props[twin]
            val = None if wv == "default" else wv
        return val

    mw = resolve("max_width")
    mn = resolve("min_width")
    mh = resolve("max_height")
    cr = resolve("corner_radius")
    return RenderProperties(
        aspect_ratio=resolve("aspect_ratio"),
        max_width=int(mw) if mw is not None else None,
        min_width=int(mn) if mn is not None else None,
        max_height=int(mh) if mh is not None else None,
        shape=resolve("shape"),
        fit=resolve("fit"),
        corner_radius=int(cr) if cr is not None else None,
        bleed=resolve("bleed"),
        content_align=resolve("content_align"),
    )


# ---------------------------------------------------------------------------
# URL-authored properties (``![alt](photo.jpg?md2ui.shape=circle)``)
# ---------------------------------------------------------------------------

# Value spaces. :func:`sanitize_url_props` validates every param against them
# — a typo in a document must never reach the page.
#
# The ratio pattern requires non-zero parts: a ``0:0`` reaching
# ``_parse_ratio`` is degenerate and no author means it. Any ``W:H`` is
# accepted, since the renderer's ``_parse_ratio`` takes an arbitrary one. It may
# go on with ``,W:H@px`` ranges — the ratio from that image width up
# (``render_metrics.ratio_ranges``).
_RATIO = r"(?!0+(\.0+)?:)[0-9]+(\.[0-9]+)?:(?!0+(\.0+)?(,|@|$))[0-9]+(\.[0-9]+)?"
_ASPECT_RE = re.compile(rf"^{_RATIO}(,{_RATIO}@[0-9]+)*$")
_ALIGN_VALUES = ("left", "center", "right")
_SHAPE_VALUES = ("circle",)
# How the image is scaled into its box. Absent means "by kind": a vector is
# contained (a drawing has meaningful bounds) and a photograph is covered (a
# texture should fill the frame). See draw_image_box.
_FIT_VALUES = ("contain", "cover")


class _NonNegInt:
    """Marker: an integer >= 0. ``corner_radius`` needs 0 to mean an explicit
    square, so it cannot reuse ``max_width``'s >= 1 rule."""


class _Bool:
    """Marker: a boolean written the way a URL can carry one."""

    TRUE = ("yes", "true", "1")
    FALSE = ("no", "false", "0")


# Base property -> validator. Keys not listed here are rejected outright.
_URL_VALIDATORS: dict[str, object] = {
    "aspect_ratio": _ASPECT_RE,
    "max_width": int,
    "min_width": int,
    "max_height": int,
    "shape": _SHAPE_VALUES,
    "fit": _FIT_VALUES,
    "corner_radius": _NonNegInt,
    "bleed": _Bool,
    "content_align": _ALIGN_VALUES,
}

# Params that were real once and are rejected now, each with what an author
# writes instead, so an answer written against older notes can be repaired by
# whoever reads the diagnostic — a typo still reads as unknown. A picture goes
# beside text through a ``:::`` row (skills/images.md, *Text beside an image*).
_REMOVED_URL_PARAMS: dict[str, str] = {
    "arrangement": "put the picture and its text in two cells of a `:::` row",
    "arrangement_wide": "put the picture and its text in a `::: 1 >` row, "
    "side by side only in wide space",
    "aside_ratio": "weight the cells of its `:::` row: `:::1` under the picture "
    "and `:::2` under the text give the picture a third",
    "content_valign": "in its `:::` row, a `...` line above the text pushes it "
    "down, and one above and one below centre it",
}


def sanitize_url_props(params: dict[str, str]) -> tuple[dict, list[str]]:
    """Validate URL-authored params into a hint entry.

    Returns ``(props, warnings)``. *props* holds render hints only, so it
    feeds :func:`render_properties_from` unchanged — including the ``_wide`` twin convention, which needs no extra
    work here. Unknown names and out-of-range values are dropped (never
    guessed) and reported, so a typo degrades to "no opinion" rather than to a
    wrong layout; a param that was removed names what to write instead.
    """
    props: dict = {}
    warnings: list[str] = []
    for name, raw in params.items():
        base = name[: -len("_wide")] if name.endswith("_wide") else name
        rule = _URL_VALIDATORS.get(base)
        instead = _REMOVED_URL_PARAMS.get(name) or _REMOVED_URL_PARAMS.get(base)
        if instead is not None:
            warnings.append(f"'md2ui.{name}' was removed — {instead}")
            continue
        if rule is None:
            warnings.append(f"unknown property 'md2ui.{name}'")
            continue
        # Only a twin may say "default" (revert to the base / no opinion).
        if raw == "default":
            if base == name:
                warnings.append(f"'md2ui.{name}=default' is only valid on a _wide twin")
                continue
            props[name] = raw
            continue
        if rule is int or rule is _NonNegInt:
            floor = 0 if rule is _NonNegInt else 1
            try:
                value: object = int(raw)
            except ValueError:
                warnings.append(f"'md2ui.{name}={raw}' is not an integer")
                continue
            if value < floor:  # type: ignore[operator]
                warnings.append(f"'md2ui.{name}={raw}' must be >= {floor}")
                continue
        elif rule is _Bool:
            low = raw.lower()
            if low in _Bool.TRUE:
                value = True
            elif low in _Bool.FALSE:
                value = False
            else:
                warnings.append(
                    f"'md2ui.{name}={raw}' is not one of "
                    f"{'|'.join(_Bool.TRUE + _Bool.FALSE)}"
                )
                continue
        elif isinstance(rule, re.Pattern):
            if not rule.match(raw):
                warnings.append(f"'md2ui.{name}={raw}' is not a valid ratio")
                continue
            value = raw
        else:
            assert isinstance(rule, tuple)
            if raw not in rule:
                warnings.append(f"'md2ui.{name}={raw}' is not one of {'|'.join(rule)}")
                continue
            value = raw
        props[name] = value
    return props, _drop_unsound_heights(props, warnings)


def _drop_unsound_heights(props: dict, warnings: list[str]) -> list[str]:
    """Drop a ``max_height`` its own image cannot honour, per variant, and say why.

    A height sizes the picture only through ONE ratio of its own, so it cannot
    share an image with a width that sizes it too, nor with ratio steps chosen
    by the very width it would produce. Dropping it leaves
    the width behaviour the image would have had without it.
    """
    for wide in (False, True):
        rp = render_properties_from(props, wide)
        if rp.max_height is None:
            continue
        name = "max_height"
        if wide:
            name = f"{name}_wide" if f"{name}_wide" in props else f"{name} (wide)"
        if rp.max_width is not None or rp.min_width is not None:
            why = "cannot be used with max_width or min_width"
        elif rp.aspect_ratio is None or "," in rp.aspect_ratio:
            why = "needs one aspect_ratio, without width steps"
        else:
            continue
        warnings.append(f"'md2ui.{name}' {why} — it was dropped")
        if wide:
            props["max_height_wide"] = "default"
        else:
            props.pop("max_height", None)
    return warnings


def poll_render(props: list[RenderProperties]) -> RenderProperties:
    """Majority-vote per-node render hints across a repeated run's members.

    Each field votes independently; an absent hint (``None``) counts as a
    vote, so a run where most members carry no ``aspect_ratio`` stays
    hint-free even if one member's hint differs. Ties break toward the
    earliest member (document order).
    """
    if not props:
        raise ValueError("poll_render needs at least one RenderProperties")
    return RenderProperties(
        **{f: _mode([getattr(p, f) for p in props]) for f in _RENDER_FIELDS}
    )


def run_shared(hints: RenderProperties) -> tuple:
    """What a repeated run's members must agree on: every hint, but a picture
    sized by its height keeps its own ratio, so logos of different shapes stand
    at one height."""
    shared = hints.to_render_dict()
    if hints.max_height is not None:
        shared.pop("aspect_ratio", None)
    return tuple(sorted(shared.items()))
