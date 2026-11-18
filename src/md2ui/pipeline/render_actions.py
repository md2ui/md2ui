"""A click becomes an action: the contract every host shares.

md2ui never acts on a click. It reports WHAT was clicked, as data, and the host
decides what happens — "actions are data", the rule md2ui-ts's framework-agnostic
core records, prototyped here first.
The Markdown the agent sends is the only source of truth for state: a click never
edits the document, and anything that should change arrives as the agent's next
response.

The kinds, by what the author wrote:

* ``link`` — ``https://…``, ``mailto:…``, ``/route``. The host routes it: a browser,
  a web view, or its own router.
* ``anchor`` — ``#heading-id``. md2ui scrolls to the heading itself (the grouper
  keeps ``{#id}`` as ``heading_id``); it is never forwarded to the host.
* ``agent`` — ``agent:<slug>?<args>``. The agent asked and the user answered. The
  slug is the agent's own readable word for the action; the host adds the id of
  the message the link came from and forwards the event. An ``agent:`` link never
  navigates, so a host that does not know md2ui safely ignores it.

* ``checkbox`` — a plain ``- [ ]`` / ``[ ]`` control. It reports the state the
  click asks for (``checked``), its ``index`` among the document's controls and
  its ``label``, the text of the item it starts. A linked ``[[ ]](agent:…)``
  control reports its link's action with the same three.

A ``~~disabled~~`` link, slider or task box, an empty destination and a bare
``agent:`` report nothing.

**The host's state is transient and moves no box.** A pending action, an
optimistic tick and a slider's in-progress value live in ``VIEW.node_states``
until the agent's next response, which replaces them: the LLM owns state.
:func:`with_node_states` shows them by swapping node dicts at recording time —
a link drawn disabled, a control's ``checked``, a slider's ``value``, a choice
option's ``choice_shown`` — and a
pending or disabled node reports nothing (:func:`hit_test`'s ``inert``). The
regions built per width therefore stay true.

**Where the rectangles come from (ADR-400: one normalization point).** A button's
region is the pill its drawer paints, from the same ``_link_pill_rect`` the drawer
calls. A link card's region is the rectangle placement gave it: ``place_boxes``
notes the slot a node is placed in and, for a wrapped card, the outer box its
background fills, and the two merge here by node id. Both are built once per width,
beside the scene (ADR-401's lifetimes), never per frame.

**A link inside a sentence is drawn by the text drawer, word by word,** so its
region comes from the same line layout (``render_measure._text_leaf_lines``) and
the same run walk its underline takes (``_flag_runs`` over the link's region
id): one region per line the link is drawn on. Its ``node_id`` is the text's
id plus ``#<k>``, the link's ordinal in the text, so a pending link mutes only
itself — though, drawn inside prose, it shows no disabled paint.

**The innermost target wins.** A button or link inside a link card takes its own
clicks, and the card takes the rest of its area: every target
:func:`action_targets` numbers is one a pointer can reach, as a keyboard can
(ADR-404). A pending card still holds what it contains.
"""

from __future__ import annotations

import dataclasses
import urllib.parse
from collections.abc import Collection, Mapping
from dataclasses import dataclass

from md2ui.pipeline.grouper_types import link_destination
from md2ui.pipeline.layout_render import _FLAG_LINK, _flag_runs, _link_pill_rect
from md2ui.pipeline.render_code_blocks import copied_text, copy_button_rect
from md2ui.pipeline.render_counts import count_rects
from md2ui.pipeline.render_card_label import card_label
from md2ui.pipeline.render_choices import held
from md2ui.pipeline.render_drawing_elements import slider_rect, task_control_rect
from md2ui.pipeline.render_measure import LINE_SCALE, _text_leaf_lines
from md2ui.pipeline.render_style import FontSet
from md2ui.pipeline.render_text import (
    inline_link_urls,
    parse_inline_spans,
    plain_link_label,
)
from md2ui.pipeline.theme import Theme
from md2ui.utils.image_params import destination_url, split_md2ui_params

AGENT_SCHEME = "agent:"

# Host states that leave a node drawn disabled and reporting nothing.
INERT_STATES = frozenset({"pending", "disabled"})
# Host states that are an optimistic tick on a task control.
TICK_STATES = frozenset({"checked", "unchecked"})

# Render properties that make ``draw_content_box`` draw something OTHER than the
# box's node (a gutter marker, a separator, a table key, a datapoint display). A
# box carrying one is never a button, whatever node it points at.
_DRAWN_INSTEAD = (
    "list_marker",
    "separator",
    "table_key",
    "datapoint_bar",
    "ring_role",
    "chart",
    "line_chart",
)


@dataclass(frozen=True, slots=True)
class Action:
    """What a click reports. Data, never behaviour."""

    kind: str  # "link" | "anchor" | "agent" | "checkbox" | "slider" | "copy"
    node_id: str
    label: str = ""
    href: str | None = None  # link, anchor
    action: str | None = None  # agent: the slug
    params: tuple[tuple[str, str], ...] = ()  # agent: the query, in order
    checked: bool | None = None  # a task control: the state the click asks for
    value: float | None = None  # a slider: the value currently shown, 0–100
    index: int | None = None  # a task control/slider ordinal in the document
    # A slider's AUTHORED domain: how precisely the value was written, what it
    # counts up to, and what it is measured in. `[65%]` is 0..100 of "%";
    # `[3/10]` is 0..10 of nothing. The server owns all three — the client sends
    # a bare number and this is what says what the number means.
    value_decimals: int | None = None
    value_max: float | None = None
    value_unit: str = ""
    count: bool = False  # a slider between ➖ and ➕: a whole number (render_choices)
    # `?md2ui.commit=1`: this button carries what the user adjusted. Authored,
    # because only the author knows which press means keep and which means
    # discard — a Cancel that committed the cart would be wrong.
    commit: bool = False
    text: str | None = None  # copy: the code block's whole source
    # The `md2ui.*` params the destination carried, split off: never reported,
    # and read only for `commit` on an `agent:` link. `check` names the rest.
    hints: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict:
        """The event as JSON-safe data, for a host to forward."""
        d: dict = {"kind": self.kind, "node_id": self.node_id, "label": self.label}
        if self.href is not None:
            d["href"] = self.href
        if self.action is not None:
            d["action"] = self.action
            d["params"] = dict(self.params)
        if self.checked is not None:
            d["checked"] = self.checked
        if self.value is not None:
            d["value"] = self.value
        if self.index is not None:
            d["index"] = self.index
        if self.commit:
            d["commit"] = True
        if self.text is not None:
            d["text"] = self.text
        return d


@dataclass(frozen=True, slots=True)
class HitRegion:
    """A rectangle in content coordinates, and what clicking it reports."""

    x: float
    y: float
    width: float
    height: float
    action: Action
    card: bool = False
    # A count's ➖ (-1) or ➕ (+1): a click steps the shown value (``stepped``).
    step: int = 0

    def contains(self, px: float, py: float) -> bool:
        return (
            self.x <= px < self.x + self.width and self.y <= py < self.y + self.height
        )


def action_for(url: str | None, label: str, node_id: str) -> Action | None:
    """Classify a link destination, or None when it reports nothing."""
    if url is None:
        return None
    # `md2ui.*` params are instructions to the CLIENT, never part of where a link
    # goes, so they are split off every destination exactly as an image's are:
    # the agent never sees its own plumbing quoted back in the sentence, and a
    # browser never sends it to a site.
    u, hints = split_md2ui_params(destination_url(url))
    if not u:
        return None
    seen = tuple(hints.items())
    if u.startswith("#"):
        return (
            Action("anchor", node_id, label, href=u, hints=seen) if len(u) > 1 else None
        )
    if u[: len(AGENT_SCHEME)].lower() == AGENT_SCHEME:
        slug, _, query = u[len(AGENT_SCHEME) :].partition("?")
        if not slug.strip():
            return None
        params = tuple(urllib.parse.parse_qsl(query, keep_blank_values=True))
        return Action(
            "agent",
            node_id,
            label,
            action=slug.strip(),
            params=params,
            commit=hints.get("commit", "").lower() not in ("", "0", "none", "false"),
            hints=seen,
        )
    return Action("link", node_id, label, href=u, hints=seen)


def commit_carries(action: Action, targets: Collection[Target]) -> bool:
    """True when a committing button in the same document will report *action*.

    A control whose value a ``?md2ui.commit=1`` press already carries need not
    report each settle on its own: the press says the same thing once, when the
    user has decided. Suppressing at the source rather than in the narration is
    what makes that reliable — folding the sentences only pays off if the agent
    leaves its wait closed while the form is filled, and agents do not. With the
    settles never sent, an agent may hold a wait open, which is its instinct, and
    the wait simply does not return until the press.

    A button reports itself and is always sent; only a target carrying a value or
    a checked state is a control. The whole regime is authored: a document with
    no committing button sends every adjustment to the agent as it happens,
    which is what an author wants when an adjustment should prompt something.
    """
    if action.value is None and action.checked is None:
        return False
    return any(t.action is not None and t.action.commit for t in targets)


def hit_region(
    regions: list[HitRegion], x: float, y: float, inert: Collection[str] = ()
) -> HitRegion | None:
    """The winning region at content point ``(x, y)``, or None.

    The innermost target wins: a button or link over the point, the one painted
    last when they overlap, as a later draw covers an earlier one; else the
    smallest link card. A linear scan: a document holds hundreds of regions, and
    a click or a cursor move asks once.

    A card whose node is *inert* (:func:`inert_nodes`) swallows every click
    inside it, so a pending card's buttons wait with it; an inert winner reports
    nothing.
    """
    card: HitRegion | None = None
    leaf: HitRegion | None = None
    for r in regions:
        if not r.contains(x, y):
            continue
        if r.card:
            if r.action.node_id in inert:
                return None
            if card is None or r.width * r.height < card.width * card.height:
                card = r
        else:
            leaf = r
    hit = leaf or card
    return None if hit is None or hit.action.node_id in inert else hit


def hit_test(
    regions: list[HitRegion], x: float, y: float, inert: Collection[str] = ()
) -> Action | None:
    """What a click at content point ``(x, y)`` reports, or None."""
    hit = hit_region(regions, x, y, inert)
    return hit.action if hit is not None else None


def inert_nodes(states: Mapping[str, str | float]) -> set[str]:
    """The node ids the host's *states* leave reporting nothing."""
    return {node_id for node_id, state in states.items() if state in INERT_STATES}


def requested(action: Action, states: Mapping[str, str | float]) -> Action:
    """*action* asking for the opposite of the tick the host shows, if it shows one.

    A control's region asks for the opposite of the DOCUMENT's state; after an
    optimistic tick the box shows the other one, and a second click must ask to
    undo what it sees.
    """
    shown = states.get(action.node_id)
    if action.checked is None or shown not in TICK_STATES:
        return action
    return dataclasses.replace(action, checked=shown == "unchecked")


def with_node_states(node_index: dict, states: Mapping[str, str | float]) -> dict:
    """*node_index* as the host shows it: node dicts swapped, never edited.

    No state returns *node_index* itself, so a document without host state is
    painted from exactly the dicts it always was. Colours only: a disabled link
    keeps its pill's box (``_disabled_link_style``), and ``checked`` moves no
    box (``draw_task_control``).
    """
    if not states:
        return node_index
    shown = dict(node_index)
    for node_id, state in states.items():
        nd = node_index.get(node_id)
        if nd is None:
            continue
        if state in INERT_STATES:
            shown[node_id] = {**nd, "link_disabled": True}
        elif state in TICK_STATES and nd.get("drawing_element"):
            payload = {**nd["drawing_element"], "checked": state == "checked"}
            shown[node_id] = {**nd, "drawing_element": payload}
        elif state in TICK_STATES and nd.get("type") == "link":  # a choice option
            shown[node_id] = {**nd, "choice_shown": state == "checked"}
        elif (
            isinstance(state, (int, float))
            and not isinstance(state, bool)
            and (nd.get("drawing_element") or {}).get("kind") == "slider"
        ):
            payload = {**nd["drawing_element"], "value": float(state)}
            shown[node_id] = {**nd, "drawing_element": payload}
    return shown


def _merge_marks(
    marks: list, node_index: Mapping[str, dict]
) -> tuple[list[HitRegion], dict[str, float]]:
    """Link-card regions and heading anchors from ``place_boxes``' notes.

    A node is noted once where it is placed and, when wrapped, once more with the
    outer box its background fills; their union is the rectangle the user sees.
    """
    spans: dict[tuple[str, str], list] = {}
    for kind, key, url, x, y, w, h in marks:
        span = spans.get((kind, key))
        if span is None:
            spans[(kind, key)] = [url, x, y, x + w, y + h]
        else:
            span[1], span[2] = min(span[1], x), min(span[2], y)
            span[3], span[4] = max(span[3], x + w), max(span[4], y + h)
    regions: list[HitRegion] = []
    anchors: dict[str, float] = {}
    for (kind, key), (url, x0, y0, x1, y1) in spans.items():
        if kind == "anchor":
            anchors[key] = y0
            continue
        action = action_for(url, card_label(node_index.get(key) or {}), key)
        if action is not None:
            regions.append(HitRegion(x0, y0, x1 - x0, y1 - y0, action, card=True))
    return regions, anchors


# Leaves painted by something other than the text drawer: no sentence, no links.
_NOT_PROSE = frozenset(
    {
        "emoji",
        "inline_code",
        "code_block",
        "image",
        "horizontal_rule",
        "content_break",
        "spacer",
        "bullet_point",
        "drawing_element",
    }
)


def _inline_regions(box, nd: dict, fonts: FontSet, theme: Theme) -> list[HitRegion]:
    """One region per link inside this text, per line it is drawn on."""
    content = nd.get("content", "")
    if nd.get("type") in _NOT_PROSE or ("](" not in content and "<" not in content):
        return []
    laid = _text_leaf_lines(box, nd, content, fonts, theme)
    if laid is None:
        return []
    text, lines, starts, eff_fonts, size = laid
    urls = inline_link_urls(text)
    labels: dict[int, list[str]] = {}
    for line in lines:
        for word in line:
            if word[_FLAG_LINK]:
                labels.setdefault(word[_FLAG_LINK], []).append(word[0])
    line_h = size * LINE_SCALE
    node_id = nd.get("node_id", "")
    regions: list[HitRegion] = []
    for line_i, (line, start) in enumerate(zip(lines, starts)):
        for x0, x1, first in _flag_runs(line, _FLAG_LINK, start, eff_fonts, size):
            link_id = line[first][_FLAG_LINK]
            url = urls[link_id - 1] if link_id <= len(urls) else None
            label = " ".join(labels[link_id])
            action = action_for(url, label, f"{node_id}#{link_id}")
            if action is not None:
                y = box.y + line_i * line_h
                regions.append(HitRegion(x0, y, x1 - x0, line_h, action))
    return regions


def _drawing_region(box, nd: dict, theme: Theme) -> HitRegion | list | None:
    """A task control or slider region, from the same geometry as its paint;
    none for one written ``~~`` (disabled)."""
    payload = nd.get("drawing_element") or {}
    if payload.get("disabled"):
        return None
    if payload.get("kind") == "slider":
        if not theme.datapoints.sliders.enabled:
            return None
        action = _slider_action(nd, payload)
        if action is None or action.count:
            return action and count_regions(box, payload, theme, action)
        return HitRegion(*slider_rect(box, theme), action)
    controls = theme.datapoints.task_controls
    if payload.get("kind") != "task_control" or not controls.enabled:
        return None
    action = _control_action(nd, payload)
    if action is None:
        return None
    return HitRegion(*task_control_rect(box, theme), action)


def count_regions(box, payload: dict, theme: Theme, action: Action) -> list:
    """A count's two regions, ➖ and ➕, at the buttons its drawer paints: one
    target, so both report its action, and each steps it one way."""
    minus, plus = count_rects(box, payload, theme)
    return [HitRegion(*minus, action, step=-1), HitRegion(*plus, action, step=1)]


def stepped(region: HitRegion, states: Mapping[str, str | float]) -> Action | None:
    """What a click on a count's button asks for: the value shown, one step on,
    inside 0..max; None when that step is outside it."""
    a = region.action
    shown = states.get(a.node_id, a.value)
    if not isinstance(shown, (int, float)) or isinstance(shown, bool):
        shown = a.value or 0.0
    value = float(shown) + region.step
    if not 0.0 <= value <= (a.value_max or 0.0):
        return None
    return dataclasses.replace(a, value=value)


def _slider_action(nd: dict, payload: dict) -> Action | None:
    node_id, label = nd.get("node_id", ""), payload.get("label", "")
    url = nd.get("link_url")
    action = (
        action_for(url, label, node_id)
        if url is not None
        else Action("slider", node_id, label)
    )
    if action is None:
        return None
    return held(
        dataclasses.replace(
            action,
            value=float(payload.get("value", 0.0)),
            index=payload.get("index"),
            value_decimals=payload.get("decimals"),
            value_max=payload.get("max"),
            value_unit=payload.get("unit", "%"),
        ),
        nd,
    )


def _control_action(nd: dict, payload: dict) -> Action | None:
    """What a task control reports: a plain one a ``checkbox``, a linked one its
    link's action — both with the state the click asks for, the control's index
    and its label, from the grouper's payload."""
    node_id, label = nd.get("node_id", ""), payload.get("label", "")
    url = nd.get("link_url")
    action = (
        action_for(url, label, node_id)
        if url is not None
        else Action("checkbox", node_id, label)
    )
    if action is None:
        return None
    return dataclasses.replace(
        action, checked=not payload.get("checked"), index=payload.get("index")
    )


def _copy_region(box, nd: dict, theme: Theme) -> HitRegion:
    """A code block's copy button, at the rectangle it is painted in."""
    x, y, w, h = copy_button_rect(box, theme.code_blocks)
    label = theme.code_blocks.copy_icon or ""
    text = copied_text(nd.get("content", ""))
    action = Action("copy", nd.get("node_id", ""), label, text=text)
    return HitRegion(x, y, w, h, action)


def _button_regions(
    boxes: list, node_index: dict, fonts: FontSet, theme: Theme
) -> list[HitRegion]:
    """One region per live button, at the pill its drawer paints, one per task
    control, at the control its drawer paints, and one per code block's copy
    button."""
    regions: list[HitRegion] = []
    for box in boxes:
        nd = node_index.get(box.content_id) if box.content_id else None
        if nd is None:
            continue
        rp = box.render_properties or {}
        if any(rp.get(key) is not None for key in _DRAWN_INSTEAD):
            continue
        if nd.get("type") == "code_block":
            if theme.code_blocks.copy_icon:
                regions.append(_copy_region(box, nd, theme))
            continue
        if nd.get("type") == "drawing_element":
            drawing = _drawing_region(box, nd, theme)
            if drawing is not None:
                regions.extend(drawing if isinstance(drawing, list) else [drawing])
            continue
        if nd.get("type") != "link":
            regions.extend(_inline_regions(box, nd, fonts, theme))
            continue
        if nd.get("link_disabled"):
            continue
        url = link_destination(nd.get("content", ""))
        action = held(action_for(url, plain_link_label(nd), nd.get("node_id", "")), nd)
        if action is None:
            continue
        x, y, w, h = _link_pill_rect(box, nd, fonts, theme)
        regions.append(HitRegion(x, y, w, h, action))
    return regions


@dataclass(frozen=True, slots=True)
class Target:
    """One actionable target of a document, at its place in document order."""

    key: str  # the node id; "<node id>#<k>" for the k-th link inside a text
    action: Action | None  # None: a slot that reports nothing (disabled, empty)
    disabled: bool = False  # written `~~…~~`: silent on purpose, not by mistake


def action_targets(tree: dict) -> list[Target]:
    """Every actionable target of a grouped document, in document order.

    A target's position in this list is its ORDINAL, what an event names on the
    wire (ADR-601): a link card before what it contains, then buttons, task
    controls and each link inside a text in the order it is written. A disabled
    target keeps its slot, reporting nothing, so ordinals do not shift when a
    re-send disables a choice.

    Reads the grouper's dict tree only — no theme, fonts, layout or width — so a
    server that knows the content and not the layout can index what a message
    offers. Every click region ``build_regions`` makes is one of these targets,
    under the same key (``tests/wire_tests.py`` checks it across the fixture).
    """
    targets: list[Target] = []

    def walk(nd: dict) -> None:
        node_id = nd.get("node_id", "")
        payload = nd.get("drawing_element") or {}
        if payload.get("disabled"):  # `~~[65%]~~`, `~~[ ]~~`: a control muted
            targets.append(Target(node_id, None, True))
        elif payload.get("kind") == "slider":
            targets.append(Target(node_id, _slider_action(nd, payload)))
        elif payload.get("kind") == "task_control":
            targets.append(Target(node_id, _control_action(nd, payload)))
        elif nd.get("type") == "link":
            action = None
            if not nd.get("link_disabled"):
                url = link_destination(nd.get("content", ""))
                action = held(action_for(url, plain_link_label(nd), node_id), nd)
            targets.append(Target(node_id, action, bool(nd.get("link_disabled"))))
        elif nd.get("link_url") is not None:
            label = card_label(nd)
            targets.append(Target(node_id, action_for(nd["link_url"], label, node_id)))
        elif nd.get("type") not in _NOT_PROSE:
            targets.extend(_inline_targets(nd.get("content", ""), node_id))
        for child in nd.get("children", []):
            walk(child)

    walk(tree)
    return targets


def _inline_targets(content: str, node_id: str) -> list[Target]:
    """The links inside one text, in the order written, keyed like their regions."""
    if "](" not in content and "<" not in content:
        return []
    labels: dict[int, list[str]] = {}
    for span in parse_inline_spans(content):
        if span[_FLAG_LINK]:
            labels.setdefault(span[_FLAG_LINK], []).append(span[0])
    targets: list[Target] = []
    for k, url in enumerate(inline_link_urls(content), 1):
        key = f"{node_id}#{k}"
        label = " ".join(" ".join(labels.get(k, [])).split())
        # A None destination is a `~~[…](…)~~` link (render_text): disabled.
        targets.append(Target(key, action_for(url, label, key), url is None))
    return targets


def build_regions(
    boxes: list, marks: list, node_index: dict, fonts: FontSet, theme: Theme
) -> tuple[list[HitRegion], dict[str, float]]:
    """Every clickable region of one placed scene, and its heading anchors."""
    cards, anchors = _merge_marks(marks, node_index)
    return cards + _button_regions(boxes, node_index, fonts, theme), anchors
