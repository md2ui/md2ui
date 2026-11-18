"""Colour resolution for the renderer: which colour a thing is actually painted.

Owns the three rules that decide a final colour, in the order they apply:

  1. **rotation** -- a THEME.md key holding a list of colours cycles across the
     elements it styles; the slot comes from the node's ordinal within its
     section (``rotation_index``), optionally synced to an ancestor level;
  2. **fixed colours** -- ``## Fixed colors`` pins for emoji, pills, buttons
     and datapoints, which outrank rotation;
  3. **colour replacement** -- ``## Color Replacements``, keyed on the COLOUR and
     the channel (text / fill / stroke) against the stack of backgrounds behind
     the box, so one rule fixes every use of that colour.

Owns no drawing. Every function here is pure: it takes a theme, a node dict and
a background stack, and returns a colour. That is what makes this module
separable from the paint loop, and what keeps the rules testable without a
canvas.
"""

from typing import TYPE_CHECKING

from md2ui.pipeline.render_text import emoji_pin, parse_inline_spans, plain_link_label
from md2ui.pipeline.theme import BG_IMAGE

if TYPE_CHECKING:
    from md2ui.pipeline.theme import SectionStyle, Theme


def _chain_style(theme: "Theme", token: int | str) -> "SectionStyle | None":
    if isinstance(token, str) and token.startswith("fixed:"):
        key, *fallback = token.removeprefix("fixed:").split("|")
        fixed = theme.fixed_sections.get(key)
        if fixed is not None:
            if fallback and fallback[0].isdigit():
                return theme.fixed_section_levels.get((key, int(fallback[0])), fixed)
            return fixed
        if fallback:
            try:
                return theme.sections.get(int(fallback[0]))
            except ValueError:
                return None
    return theme.sections.get(token) if isinstance(token, int) else None


def _rotation_enabled(
    theme: "Theme",
    channel: str,
    chain: "tuple[int | str, ...] | list[int | str]",
) -> bool:
    """Whether *channel* may cycle inside the section ancestry *chain*.

    ``Rotate <kind> colors: yes|no`` on a heading level governs everything
    inside that level's sections. The innermost level that states the key wins,
    so ``## Heading 1: Rotate link colors: no`` is overridden by a ``yes`` on
    ``## Heading 2``; a level that stays silent defers outward, and a document
    that mentions none of it cycles wherever a list has two or more colors.
    """
    for lvl in reversed(tuple(chain or ())):
        st = _chain_style(theme, lvl)
        if st is not None and channel in st.rotate:
            return st.rotate[channel]
    return True


def _synced_slot(
    index: int,
    chain: "tuple[int | str, ...]",
    path: "tuple[int, ...]",
    theme: "Theme",
) -> int:
    """The slot to paint with: a card's own, when an ancestor shares it.

    ``Rotate colors: sync`` on a heading level hands that level's slot to
    everything inside its sections, which is the only way an element can say
    "the color of the card I am in" — its own cycle counts it among its
    siblings, so the chips of every card restart at 0.

    The chain is walked innermost-first, so the nearest sharing ancestor wins,
    and it is the node's STRICT ancestry: a level can never sync to itself, and
    the cards keep the slots their own cycle dealt them.
    """
    for i in range(min(len(chain), len(path)) - 1, -1, -1):
        st = _chain_style(theme, chain[i])
        if st is not None and st.sync_slot:
            token = chain[i]
            if isinstance(token, str) and token.startswith("fixed:"):
                key, *fallback = token.removeprefix("fixed:").split("|")
                if key in theme.fixed_sections and len(fallback) >= 2:
                    try:
                        return int(fallback[1])
                    except ValueError:
                        pass
            return path[i]
    return index


def _rotate_color(
    colors: "list[int]",
    fallback: "int | None",
    index: int,
    theme: "Theme",
    channel: str,
    chain: "tuple[int | str, ...] | list[int | str]" = (),
) -> "int | None":
    """Pick *index*'s color out of a THEME.md color list.

    The single entry point for every rotating property. An empty list keeps the
    style's own scalar (nothing was authored), and a one-color list or a gate
    turned off pins to the first entry — which is why a theme that never lists
    two colors renders exactly as it did before rotation existed.
    """
    if not colors:
        return fallback
    if len(colors) == 1 or not _rotation_enabled(theme, channel, chain):
        return colors[0]
    return colors[index % len(colors)]


def _table_background_color(
    style: "SectionStyle", row_index: int, theme: "Theme"
) -> "int | None":
    """The background actually painted for a header/body table row."""
    return _rotate_color(
        style.bg_colors,
        style.bg_colors[0] if style.bg_colors else None,
        row_index,
        theme,
        "background",
    )


def _rotation_slot(
    nd: dict, theme: "Theme | None" = None
) -> "tuple[int, tuple[int | str, ...]]":
    """A leaf's rotation slot and its section ancestry, both from the grouper.

    The slot is already resolved through ``Rotate colors: sync``, so every
    caller paints the card's color without knowing the mechanism exists.
    """
    chain = tuple(nd.get("rotation_chain") or ())
    fixed_key = nd.get("section_style_key")
    use_fixed = bool(
        theme is not None and fixed_key and fixed_key in theme.fixed_sections
    )
    index = int(
        nd.get("fixed_rotation_index" if use_fixed else "rotation_index", 0) or 0
    )
    if theme is not None:
        index = _synced_slot(index, chain, tuple(nd.get("rotation_path") or ()), theme)
    return index, chain


def painted_pins(pins: dict, style: object) -> dict:
    """The ``fixed_*`` pins of a button or chip that its variant can carry.

    One ``### Buttons`` / ``### Badges`` entry serves every variant of a label,
    so a pin recolors only the channels the variant already paints: a fill
    whose alpha is zero stays clear, and a stroke of no width stays undrawn (a
    width with a transparent color is still a stroke the pin may color). An
    outlined `*[Cancel](/x)*` therefore takes the entry's ``Stroke color`` and
    ignores its ``Fill color``. The label is painted by every variant, so its
    ``Text color`` always applies: pinned red on a red pill, it equals the fill
    behind it and ``_pin_or_replace`` hands it to ``## Color Replacements``,
    which is how one entry gives a red outline label and a white filled one.
    """
    fill = getattr(style, "fill_color", None) or 0
    has_fill = bool(fill >> 24) or bool(
        getattr(style, "bg_image", None) or getattr(style, "gradient", None)
    )
    has_stroke = (getattr(style, "stroke_width", None) or 0) > 0
    pinned_fill = pins.get("fixed_fill")
    out = {}
    if has_fill and pinned_fill is not None:
        out["fixed_fill"] = pinned_fill
    if has_stroke and pins.get("fixed_stroke") is not None:
        out["fixed_stroke"] = pins["fixed_stroke"]
    if pins.get("fixed_text") is not None:
        out["fixed_text"] = pins["fixed_text"]
    return out


def _pin_or_replace(
    color: int,
    pin: "int | None",
    stack: "tuple[int | str, ...]",
    theme: "Theme",
    role: str = "text",
) -> int:
    """A meaning-bearing pin wins over replacement — unless it would vanish.

    ``## Fixed colors`` outranks both rotation and replacement: a ❤️ is red
    because red is what it MEANS. The one exception is invisibility — a pin
    that, painted over what shows behind it, leaves exactly that color would
    erase the element, so it is dropped and ordinary replacement runs instead.
    What shows behind is the stack composited, so a 10% green fill over a
    green section is green, and a label pinned green on it is dropped too.
    Exact match only; no contrast threshold to tune. A clear pin is an
    authored "no fill", never a collision, and is always kept.
    """
    if pin is not None:
        behind = _backdrop(stack)
        if behind is None or not pin >> 24 or _over(pin, behind) != behind:
            return pin
    return _replace_color(color, stack, theme, role)


def _over(top: int, under: int) -> int:
    """ARGB *top* painted over *under* (source-over)."""
    ta, ua = (top >> 24) / 255.0, (under >> 24) / 255.0
    oa = ta + ua * (1 - ta)
    if oa <= 0:
        return 0
    out = round(oa * 255) << 24
    for sh in (16, 8, 0):
        t, u = (top >> sh) & 0xFF, (under >> sh) & 0xFF
        out |= round((t * ta + u * ua * (1 - ta)) / oa) << sh
    return out


def _backdrop(stack: "tuple[int | str, ...]") -> "int | None":
    """The color that shows behind: translucent layers composited down to the
    first opaque one. None when an image shows through, or nothing is there."""
    acc = None
    for c in stack:
        if not isinstance(c, int):
            return None
        acc = c if acc is None else _over(acc, c)
        if acc >> 24 == 0xFF:
            break
    return acc


def _label_pins(
    label: str,
    exact: "dict[str, dict[str, int]]",
    contains: "dict[str, dict[str, int]]",
) -> "dict[str, int] | None":
    """The fixed-color entry for a chip or button: exact, then contains.

    A label whose text varies can never be keyed literally, so a key appearing
    inside it matches too. Exact remains authoritative when both rules match.
    """
    hit = exact.get(label.strip())
    if hit is not None:
        return hit
    for key, roles in contains.items():
        if key in label:
            return roles
    return None


def _dp_pin_for(
    dp: dict, content: str, prev_content: "str | None", theme: "Theme"
) -> "int | None":
    """Resolve one annotation's datapoint pin, including directional keys."""
    table = theme.fixed.datapoints
    if not table:
        return None
    matched = (dp.get("matched") or "").strip()
    sign = (
        matched[:1]
        if matched[:1] in "+-"
        else (
            content.strip()[:1]
            if content.strip()[:1] in "+-"
            else (
                prev_content.strip()
                if prev_content and prev_content.strip() in "+-"
                else ""
            )
        )
    )
    kind = (dp.get("label") or "").replace("dp_", "")
    if kind == "emoji":
        return None
    if sign:
        direction = "up" if sign == "+" else "down"
        for key in (kind, "change"):
            hit = table.get(f"{key} {direction}")
            if hit is not None:
                return hit
    return table.get(kind)


def _dp_pin(nd: dict, prev_content: "str | None", theme: "Theme") -> "int | None":
    """The ``### Datapoints`` pin for a leaf, by detected type and direction.

    ``change up`` / ``change down`` key on the SIGN, because that is what the
    color means. The sign normally rides on the leaf — the no-orphan gate in
    the grouper does not cut between a number and an adjacent
    ``+`` / ``-``, so `+2,588` and `+$22,910` are both one signed leaf. The
    previous sibling is still consulted as a fallback: a sign can be detached by
    an authored separator (``+ | 2,588``), and a grey plus beside a green figure
    is the wrong reading of the same value.
    """
    table = theme.fixed.datapoints
    if not table:
        return None
    content = (nd.get("content") or "").strip()
    sign = (
        content[:1]
        if content[:1] in "+-"
        else (
            prev_content.strip()
            if prev_content and prev_content.strip() in "+-"
            else ""
        )
    )
    types = [
        (p.get("label") or "").replace("dp_", "") for p in (nd.get("data_points") or [])
    ]
    types = [t for t in types if t != "emoji"]
    if sign:
        direction = "up" if sign == "+" else "down"
        for kind in types + ["change"]:
            hit = table.get(f"{kind} {direction}")
            if hit is not None:
                return hit
    for kind in types:
        hit = table.get(kind)
        if hit is not None:
            return hit
    return None


def _stamp_dp_spans(
    nd: dict, pins: list[tuple[dict, int]], fallback_color: "int | None" = None
) -> None:
    """Stamp trusted annotation ranges, or conservatively pin the whole leaf.

    ``data_points`` offsets name the grouper's source content, while inline
    parsing removes Markdown markers before drawing. A range is paintable only
    when every slice still names its recorded match and parsing leaves the leaf
    byte-for-byte unchanged. Marker balancing and late escape removal can break
    either condition; the whole-leaf pin is safer than coloring the wrong
    characters, so it remains the fallback.
    """
    if not pins:
        return
    fallback = fallback_color if fallback_color is not None else pins[0][1]
    content = nd.get("content") or ""
    spans: list[dict] = []
    for dp, color in pins:
        start, end = dp.get("start"), dp.get("end")
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or not (0 <= start < end <= len(content))
            or content[start:end] != dp.get("matched")
        ):
            nd["fixed_text"] = fallback
            nd.pop("fixed_text_spans", None)
            return
        # A detector may leave a leading sign just outside a numeric match.
        # The existing whole-leaf pin colored it with the value; keep that
        # semantic unit intact when the pin becomes a range.
        paint_start = start
        if start and content[start - 1] in "+-" and not content[: start - 1].strip():
            paint_start -= 1
        spans.append({"start": paint_start, "end": end, "color": color})
    visible = "".join(span[0] for span in parse_inline_spans(content))
    if visible != content:
        nd["fixed_text"] = fallback
        nd.pop("fixed_text_spans", None)
        return
    spans.sort(key=lambda span: (span["start"], span["end"]))
    if any(left["end"] > right["start"] for left, right in zip(spans, spans[1:])):
        nd["fixed_text"] = fallback
        nd.pop("fixed_text_spans", None)
        return
    lo = len(content) - len(content.lstrip())
    hi = len(content.rstrip())
    if len(spans) == 1 and spans[0]["start"] == lo and spans[0]["end"] == hi:
        nd["fixed_text"] = spans[0]["color"]
        nd.pop("fixed_text_spans", None)
        return
    nd.pop("fixed_text", None)
    nd["fixed_text_spans"] = spans


def _datapoint_pins(
    nd: dict, prev_content: "str | None", theme: "Theme"
) -> tuple[list[tuple[dict, int]], "int | None"]:
    """Per-annotation pins, with an inline scoped emoji taking precedence.

    The scoped emoji reaches every other datapoint of the leaf, emojis among
    them; its own glyph already takes its pin where the run is painted."""
    content = nd.get("content") or ""
    dps = nd.get("data_points") or []
    pins = [
        (dp, pin)
        for dp in dps
        if (pin := _dp_pin_for(dp, content, prev_content, theme)) is not None
    ]
    scoped: int | None = None
    scoping: list[dict] = []
    for dp in dps:
        if (dp.get("label") or "") != "dp_emoji":
            continue
        hit = emoji_pin(theme.fixed.emoji, (dp.get("matched") or "").strip())
        if hit is not None and "datapoints" in hit[1].split():
            scoped = hit[0]
            scoping.append(dp)
    if scoped is not None:
        pins = [(dp, scoped) for dp in dps if not any(dp is s for s in scoping)]
    return pins, scoped if scoped is not None else _dp_pin(nd, prev_content, theme)


# The piece types an emoji pin names as ``text``: the words
# of a line, whatever datapoints they hold. A heading is text too.
_TEXT_PIECES = frozenset({"text", "segment", "datapoint", "key", "value"})
_ELEMENT_KINDS = {"emoji": "emojis", "link": "buttons", "inline_code": "chips"}


def _piece_kind(node: dict) -> "str | None":
    """The kind an emoji pin's scope names *node* by: ``text``, ``emojis``,
    ``buttons`` (a text link is a button variant) or ``chips``; ``None`` for a
    piece no kind names, such as a picture."""
    kind = node.get("type") or ""
    if kind in _TEXT_PIECES or kind.startswith("heading"):
        return "text"
    return _ELEMENT_KINDS.get(kind)


def _stamp_signed_chip(
    chip: dict, label: str, prev: "dict | None", theme: "Theme"
) -> None:
    """A chip that is one signed value colors by its direction, as the value
    does in text: the pin on its label, a light tint of the pin behind it."""
    pins, _ = _datapoint_pins(chip, prev.get("content") if prev else None, theme)
    if len(pins) == 1 and (pins[0][0].get("matched") or "").strip() == label:
        color = pins[0][1]
        chip["fixed_text"] = color
        chip["fixed_fill"] = (color & 0xFFFFFF) | 0x19000000


def stamp_fixed_colors(node: dict, theme: "Theme") -> None:
    """Resolve ``## Fixed colors`` onto the node tree, once, before painting.

    Stamps ``fixed_text`` / ``fixed_fill`` / ``fixed_stroke`` so every drawer
    reads one key instead of re-deriving the rules. It happens here rather than
    in a drawer because a pin can SPREAD to a leaf's siblings — an emoji scoped
    ``datapoints`` colors the values beside it (emojis and links among them),
    ``line`` colors the whole run, a kind (``chips``…) the pieces of that kind —
    and a drawer only ever sees one box.

    Order matters: datapoint, pill and button pins are applied first, then an
    emoji's spread overwrites them, because naming a glyph is more specific.
    """
    if not theme.fixed.is_active():
        return
    kids = node.get("children") or []

    for i, kid in enumerate(kids):
        content = kid.get("content") or ""
        if kid.get("element_muted"):
            continue  # muted paints its own state, never a pin, as a disabled link
        if kid.get("type") == "emoji":
            pin = emoji_pin(theme.fixed.emoji, content.strip())
            if pin is not None:
                kid["fixed_text"] = pin[0]
            bg = emoji_pin(theme.fixed.emoji_bg, content.strip())
            if bg is not None:
                kid["fixed_fill"] = bg
        elif kid.get("type") in ("inline_code", "link"):
            is_button = kid.get("type") == "link"
            label = plain_link_label(kid) if is_button else content.strip().strip("`")
            exact = theme.fixed.button_exact if is_button else theme.fixed.pill_exact
            contains = (
                theme.fixed.button_contains if is_button else theme.fixed.pill_contains
            )
            roles = _label_pins(label or content, exact, contains)
            if roles:
                for role, key in (
                    ("text", "fixed_text"),
                    ("fill", "fixed_fill"),
                    ("stroke", "fixed_stroke"),
                ):
                    if role in roles:
                        kid[key] = roles[role]
            elif not is_button:
                _stamp_signed_chip(kid, label, kids[i - 1] if i else None, theme)
        else:
            prev = kids[i - 1].get("content") if i else None
            pins, fallback = _datapoint_pins(kid, prev, theme)
            if pins:
                _stamp_dp_spans(kid, pins, fallback)
                # A lone sign belongs to the number it signs, so it takes the
                # color the leaf opens with — otherwise `+2,588` renders a grey
                # + and a green number.
                if i and (kids[i - 1].get("content") or "").strip() in ("+", "-"):
                    lead = kid.get("fixed_text")
                    if lead is None:
                        lead = kid["fixed_text_spans"][0]["color"]
                    kids[i - 1]["fixed_text"] = lead
                    kids[i - 1].pop("fixed_text_spans", None)

    # An emoji's scope reaches its siblings, so it is resolved per PARENT.
    for i, kid in enumerate(kids):
        if kid.get("type") != "emoji":
            continue
        pin = theme.fixed.emoji.get((kid.get("content") or "").strip())
        if pin is None or not pin[1]:
            continue
        color, words = pin[0], set(pin[1].split())
        for j, sib in enumerate(kids):
            if j == i or sib.get("children"):
                continue
            if "line" in words or _piece_kind(sib) in words:
                sib["fixed_text"] = color
                sib.pop("fixed_text_spans", None)
            elif "datapoints" in words:
                pins = [(p, color) for p in (sib.get("data_points") or [])]
                _stamp_dp_spans(sib, pins, color)

    for kid in kids:
        stamp_fixed_colors(kid, theme)


def _replace_color(
    color: int,
    stack: "tuple[int | str, ...]",
    theme: "Theme",
    role: str = "text",
) -> int:
    """*color*, swapped if a ``## Color Replacements`` rule covers it.

    The nearest visible background is the context — a fixed style's photo
    first by its own rules, else by the theme's ``image`` ones. It alone may
    replace the paint: a card fill must not let a root image recolor its contents merely
    because the card declares no rules. Within that context, roles remain
    independent and an exact entry beats that role's default.
    """
    table = theme.color_replacements
    if not table or not stack:
        return color
    rules = table.get(stack[0])
    if rules is None and str(stack[0]).startswith(f"{BG_IMAGE}:"):
        rules = table.get(BG_IMAGE)  # a style with no rules of its own
    group = (rules or {}).get(role)
    if not group:
        return color
    if color in group:
        return group[color]
    return group.get(None, color)
