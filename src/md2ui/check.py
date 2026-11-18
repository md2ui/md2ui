"""Authoring checks on a Markdown response, before it is sent (ADR-602).

What an agent can get wrong that a render would not tell it in words: something
clickable that reports nothing, an anchor that scrolls nowhere, an action hidden in
a sentence, an image param that is ignored, repeated pictures left at the default
ratio, an escape that draws its backslash, a document that draws nothing at all,
an element spelling the theme's contract does not declare, and a chart or line
that a row's extra words or units kept from drawing (``check_charts``).
An issue's ``level`` is ``error`` or ``warning`` for a defect, and ``note`` for
advice: a fact of the tree an author may have meant — one offer shown twice, a
run whose cards are not all tappable, a sentence a spaced colon cut into a label,
a styled name cut at its dash, a main button whose one-line label widens its card,
task boxes no button commits —
which never holds a page back.
Each issue names the target's ordinal ``x`` — the number the wire uses (ADR-601) —
so the agent can find it. An issue with a mechanical fix also names its ``line``,
the ``text`` written there, and every ``replacements`` that fixes it, one per
meaning: the author picks one, and nothing is applied for them.

Grouping only, like the wire's index: no theme, fonts, layout or width, so it runs
anywhere the server runs. A shell module beside ``session``; the pipeline never
imports it.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from md2ui.pipeline.grouper_block_splits import INLINE_CODE_RE, divider_fell_back
from md2ui.pipeline.grouper_code_blocks import extract_code_blocks
from md2ui.pipeline.grouper_escapes import DEFERRED_ESCAPES, EARLY_ESCAPES
from md2ui.pipeline.grouper_inline_marks import INLINE_SPACERS
from md2ui import check_charts, check_choices, check_feeds, check_placeholders, session
from md2ui.meanings import Contract, undeclared
from md2ui.pipeline.render_hints import (
    poll_render,
    render_properties_from,
    sanitize_url_props,
)
from md2ui.pipeline.generator_units import shares_params
from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType
from md2ui.pipeline.markdown_grouper import MarkdownGrouper
from md2ui.pipeline.render_metrics import DEFAULT_IMAGE_RATIOS
from md2ui.pipeline.render_actions import Action, Target, action_targets
from md2ui.pipeline.render_text import plain_link_label
from md2ui.utils.image_params import (
    clean_image_url,
    image_alt,
    image_params,
    image_url,
)


def _issue(
    level: str,
    code: str,
    message: str,
    x: int | None = None,
    fix: tuple[int, str, list[str]] | None = None,
) -> dict:
    """An issue; *fix* is ``(line, text, replacements)`` for one the author can
    apply by hand. It is a suggestion, never applied: the author spells what
    they mean, so a spelling with two meanings offers both."""
    issue: dict = {"level": level, "code": code, "message": message}
    if x is not None:
        issue["x"] = x
    if fix is not None:
        issue["line"], issue["text"], issue["replacements"] = fix
    return issue


def _prose_lines(markdown: str) -> list[tuple[int, str]]:
    """``(line number, line)`` for each line outside fenced code, numbered from
    1 in the document as sent."""
    fence: str | None = None
    found = []
    for number, line in enumerate(markdown.splitlines(), 1):
        mark = line.lstrip()[:3]
        if mark in ("```", "~~~"):
            fence = None if fence == mark else fence or mark
        elif fence is None:
            found.append((number, line))
    return found


def _outside_code(line: str, rewrite: Callable[[str], str]) -> str:
    """*line* with *rewrite* applied to its text and not to its code spans,
    which draw as written."""
    out, at = [], 0
    for span in INLINE_CODE_RE.finditer(line):
        out += [rewrite(line[at : span.start()]), span.group()]
        at = span.end()
    return "".join(out) + rewrite(line[at:])


def _heading_ids(node: dict, into: set[str] | None = None) -> set[str]:
    ids = into if into is not None else set()
    if node.get("heading_id"):
        ids.add(node["heading_id"])
    for child in node.get("children", []):
        _heading_ids(child, ids)
    return ids


def _node_text(node: dict) -> str:
    content = str(node.get("content", ""))
    if content:
        return content
    pieces = [_node_text(child) for child in node.get("children", [])]
    pieces = [piece for piece in pieces if piece]
    # A gap can hold several separators (`A | +++ B`); an inline spacer is
    # recorded as a one-character mark and read back as the `+++` it was.
    separators = [
        " ".join(INLINE_SPACERS.get(ch, ch) for ch in str(gap))
        for gap in node.get("separator_chars", [])
    ]
    if len(separators) == len(pieces) - 1:
        text = pieces[0] if pieces else ""
        for separator, piece in zip(separators, pieces[1:], strict=True):
            text += f" {separator} {piece}"
        return text
    return " ".join(pieces)


def _divided_at_a_dash(node: dict) -> bool:
    """True when anything in this subtree divided its line at a ` - `.

    The whole SUBTREE, because a heading does not always carry the split
    itself: an ordinal puts it one level down, so `## 1. **Strobe** - Deadmau5`
    records it on the `ordered_item` inside the heading. Asking the heading
    node alone misses every numbered one — the shape an LLM writes most.
    """
    if any("-" in str(gap) for gap in node.get("separator_chars") or []):
        return True
    return any(_divided_at_a_dash(child) for child in node.get("children", []))


def _dash_split_headings(node: dict, into: list[str] | None = None) -> list[str]:
    headings = into if into is not None else []
    if str(node.get("type", "")).startswith("heading") and _divided_at_a_dash(node):
        headings.append(_node_text(node))
        return headings
    for child in node.get("children", []):
        _dash_split_headings(child, headings)
    return headings


# A heading line, and a dash standing alone between spaces: the spelling that
# divides a heading (`_divided_at_a_dash`).
_HEADING_LINE_RE = re.compile(r"^ {0,3}#{1,6}\s")
_LONE_DASH_RE = re.compile(r"(?<=\s)-(?=\s)")


def _letters(text: str) -> str:
    """*text* without its markers, escapes and spaces: what the AST's heading
    text and the line written for it still share."""
    return "".join(ch for ch in text if ch.isalnum())


def _heading_fixes(
    markdown: str, headings: list[str]
) -> list[tuple[int, str, list[str]] | None]:
    """For each split heading, in order, its line and the two spellings that
    keep it whole: the dash escaped, or an em dash for punctuation. The line is
    the next heading line holding the heading's letters and a dash to escape;
    ``None`` when there is none, and the issue keeps its message alone."""
    lines = [(n, ln) for n, ln in _prose_lines(markdown) if _HEADING_LINE_RE.match(ln)]
    at = 0
    fixes: list[tuple[int, str, list[str]] | None] = []
    for heading in headings:
        want = _letters(heading)
        fix = None
        for i in range(at, len(lines)):
            number, line = lines[i]
            escaped = _outside_code(line, lambda t: _LONE_DASH_RE.sub(r"\\-", t))
            if want not in _letters(line) or escaped == line:
                continue
            em = _outside_code(line, lambda t: _LONE_DASH_RE.sub("—", t))
            fix, at = (number, line, [escaped, em]), i + 1
            break
        fixes.append(fix)
    return fixes


# A span in any emphasis style (`*` `_` once to three times, `~~`), and one that
# is wholly a link (`**[Next](/n)**`).
_STYLED_SPAN_RE = re.compile(
    r"(?<![*_~\w])(\*{1,3}|_{1,3}|~~)(?![\s*_~])(.+?)(?<![\s*_~])\1(?![*_~\w])"
)
_LINK_SPAN_RE = re.compile(r"^\[.*\]\([^)]*\)$")


def _dash_divided(node: dict, into: list[str] | None = None) -> list[str]:
    """The letters of every node outside a heading that divided its line at a
    ` - `. Headings are `split-heading`'s."""
    found = into if into is not None else []
    if str(node.get("type", "")).startswith("heading"):
        return found
    if any("-" in str(gap) for gap in node.get("separator_chars") or []):
        found.append(_letters(_node_text(node)))
    for child in node.get("children", []):
        _dash_divided(child, found)
    return found


def _cut_styled_names(
    markdown: str, tree: dict
) -> list[tuple[str, tuple[int, str, list[str]]]]:
    """``(name, fix)`` for each styled name a spaced dash divided: a title copied
    from data (`**The Chain - 2004 Remaster**`) is cut as surely as one written
    to be: no emphasis style protects it (ADR-201), only quotes and parentheses
    do, and there the grouper does not divide. The fix is the span's dashes
    escaped, which keeps the name verbatim, an em dash, or each piece styled on
    its own for a split that was meant. A span whose piece
    before the dash is an emoji alone is the badge spelling, sized by its
    wrapper (`**⭐ - Popular**`), and is left alone."""
    divided = _dash_divided(tree)
    found: list[tuple[str, tuple[int, str, list[str]]]] = []
    for number, line in _prose_lines(markdown):
        if _HEADING_LINE_RE.match(line):
            continue
        bare = INLINE_CODE_RE.sub(lambda m: "x" * len(m.group()), line)
        for span in _STYLED_SPAN_RE.finditer(bare):
            inner = span.group(2).strip()
            if " - " not in inner or _LINK_SPAN_RE.match(inner):
                continue
            if not any(ch.isalnum() for ch in inner.split(" - ")[0]):
                continue
            written = line[span.start() : span.end()]
            if not any(_letters(written) in d for d in divided):
                continue
            head, tail = line[: span.start()], line[span.end() :]
            fixes = [
                head
                + _outside_code(written, lambda t: _LONE_DASH_RE.sub(dash, t))
                + tail
                for dash in (r"\\-", "—")
            ]
            # A split that was meant: each piece in the span's own wrapper.
            mark, inner = span.group(1), line[span.start(2) : span.end(2)]
            cut = _outside_code(inner, lambda t: _LONE_DASH_RE.sub("\0", t))
            pieces = (f"{mark}{piece.strip()}{mark}" for piece in cut.split("\0"))
            fixes.append(head + " - ".join(pieces) + tail)
            found.append((inner.strip(), (number, line, fixes)))
    return found


def _fallen_back_dividers(markdown: str) -> list[str]:
    """The `:::` lines read as a bare divider because their options are not a
    valid one. Read off the lines, not the tree — a divider is gone by then —
    skipping fenced code, where the line is only text."""
    return [
        line.strip() for _, line in _prose_lines(markdown) if divider_fell_back(line)
    ]


def _drawn_backslashes(markdown: str) -> list[tuple[str, str]]:
    """``(character, line)`` for each backslash an author meant as an escape
    that md2ui draws instead. md2ui escapes what CommonMark escapes, ASCII
    punctuation, and its own separators, so a backslash before a long dash or
    an arrow stays text. Only non-ASCII characters are named: a backslash
    before a letter or a digit is a path or a formula far more often than a
    failed escape. Code and comments draw nothing of the author's, and a
    backslash ending a line is a hard break."""
    text = MarkdownGrouper.HTML_COMMENT_RE.sub("", extract_code_blocks(markdown)[0])
    escapable = EARLY_ESCAPES + DEFERRED_ESCAPES
    found: list[tuple[str, str]] = []
    for line in text.splitlines():
        bare = INLINE_CODE_RE.sub("", line)
        i = bare.find("\\")
        while 0 <= i < len(bare) - 1:
            ch = bare[i + 1]
            if ch not in escapable and not ch.isascii():
                if (ch, line.strip()) not in found:
                    found.append((ch, line.strip()))
            i = bare.find("\\", i + 2)
    return found


def _backslash_fixes(
    markdown: str, ch: str, line: str
) -> list[tuple[int, str, list[str]]]:
    """Each line written as *line* (comments aside), with ``\\ch`` made bare
    outside its code spans."""
    return [
        (number, text, [_outside_code(text, lambda t: t.replace("\\" + ch, ch))])
        for number, text in _prose_lines(markdown)
        if MarkdownGrouper.HTML_COMMENT_RE.sub("", text).strip() == line
    ]


def _card_name(card: MarkdownGroupNode) -> str:
    """The card's first heading, else the start of its text."""
    stack = [card]
    while stack:
        n = stack.pop(0)
        if str(n.type).startswith("heading") and n.content.strip():
            return n.content.strip()
        stack.extend(n.children)
    text = " ".join(_node_text(card.to_dict()).split())
    return text if len(text) <= 40 else text[:39] + "…"


def button_count(node: MarkdownGroupNode) -> int | None:
    """How many buttons a line of buttons holds: one is a ``link`` leaf, more
    are the pieces of one line. ``None`` for anything else, links stacked on
    lines of their own included: that is a list of links, not a card's buttons."""
    if node.type == NodeType.LINK and not node.children:
        return 1
    if node.line_split_group and all(
        c.type == NodeType.LINK and not c.children for c in node.children
    ):
        return len(node.children)
    return None


def _cards(*nodes: MarkdownGroupNode) -> bool:
    """Whether every one of *nodes* is a card: a group, not a line of buttons."""
    return all(n.children and button_count(n) is None for n in nodes)


def _picture_name(content: str) -> str:
    """What an agent would search its answer for to find this picture."""
    alt = image_alt(content)
    return alt if alt and alt != "image" else str(clean_image_url(image_url(content)))


def _unread_link_params(action: Action) -> list[str]:
    """The ``md2ui.*`` params a link carried that nothing reads: every one but
    ``commit`` on an ``agent:`` link, and every one on any other (``choice`` is
    ``check_choices``' to judge, ``feed`` ``check_feeds'``). ``action_for`` has
    already split them off, so a refused one is never sent on, only lost."""
    read = (
        ("commit", "choice", "feed") if action.kind == "agent" else ("choice", "feed")
    )
    return [n for n, _ in action.hints if n not in read]


def _image_param_problems(node: dict, into: list[str] | None = None) -> list[str]:
    """What the renderer says about each picture's ``?md2ui.*`` params, in its
    own words, prefixed with the picture an agent would search for. A refused
    param changes nothing on the page, so without this the only trace of it is a
    terminal line an agent using these tools never reads."""
    found = into if into is not None else []
    content = str(node.get("content", ""))
    if node.get("type") == "image" and content:
        raw = image_params(content)
        if raw:
            name = _picture_name(content)
            found.extend(f"Image `{name}`: {w}" for w in sanitize_url_props(raw)[1])
    for child in node.get("children", []):
        _image_param_problems(child, found)
    return found


def _own_hints(picture: MarkdownGroupNode, wide: bool):
    """The render hints this picture's own params ask for, or ``None``."""
    entry = sanitize_url_props(image_params(picture.content))[0]
    return render_properties_from(entry, wide) if entry else None


def _places(run: list[MarkdownGroupNode]) -> list[list[MarkdownGroupNode]]:
    """The pictures a run's members share, one list per place in the members.
    A picture that only one member carries is a lone picture, not repeated."""
    places: dict[tuple[int, ...], list[MarkdownGroupNode]] = {}

    def collect(n: MarkdownGroupNode, path: tuple[int, ...]) -> None:
        if n.type == "image" and n.content:
            places.setdefault(path, []).append(n)
        for i, child in enumerate(n.children):
            collect(child, path + (i,))

    for member in run:
        collect(member, ())
    return [pics for pics in places.values() if len(pics) >= 2]


def _pin_runs(node: MarkdownGroupNode, pins: dict, wide: bool) -> dict:
    """The hints the renderer pins on each picture of a run that shares params
    (``shares_params``): its annotated pictures' vote at that place. A run
    inside another is polled after it, so the inner run's pin is the one drawn."""
    for run in (node.repeated_children or {}).values():
        for pics in _places(run) if shares_params(run) else []:
            if votes := [h for p in pics if (h := _own_hints(p, wide))]:
                pins.update((id(p), poll_render(votes)) for p in pics)
    for child in node.children:
        _pin_runs(child, pins, wide)
    return pins


def _default_cropped(root: MarkdownGroupNode) -> set[int]:
    """The pictures the render draws at the default ratio, at either width:
    neither their run's pin nor their own params choose a ratio or a circle."""
    cropped: set[int] = set()
    for wide in (False, True):
        pins = _pin_runs(root, {}, wide)
        stack = [root]
        while stack:
            n = stack.pop()
            stack.extend(n.children)
            if n.type == "image" and n.content:
                hints = pins.get(id(n)) or _own_hints(n, wide)
                if not hints or (not hints.aspect_ratio and hints.shape != "circle"):
                    cropped.add(id(n))
    return cropped


def _unratioed_runs(
    node: MarkdownGroupNode,
    into: list[tuple[str, int, int]] | None = None,
    seen: set[int] | None = None,
    cropped: set[int] | None = None,
) -> list[tuple[str, int, int]]:
    """Each repeated run whose pictures the render draws at the default ratio:
    ``(name, without, pictures)``. Runs are polled as the renderer polls them
    (skills/images.md, *Params apply to a whole run*), so one annotated member
    speaks for its run and a picture is named only where it really falls back.
    A run that shares a picture with a reported run is not reported again:
    choosing the outer run's ratio is the fix for both."""
    found = into if into is not None else []
    seen = seen if seen is not None else set()
    cropped = cropped if cropped is not None else _default_cropped(node)
    for run in (node.repeated_children or {}).values():
        repeated = _places(run)
        without = [p for pics in repeated for p in pics if id(p) in cropped]
        if without and not any(id(p) in seen for p in without):
            seen.update(id(p) for pics in repeated for p in pics)
            found.append(
                (
                    _run_name(run[0], without[0]),
                    len(without),
                    sum(len(pics) for pics in repeated),
                )
            )
    for child in node.children:
        _unratioed_runs(child, found, seen, cropped)
    return found


def _shape(node: MarkdownGroupNode) -> tuple:
    """What kind of item a node is, by its tree alone: its type and its
    children's shapes, never its words."""
    return (str(node.type), tuple(_shape(c) for c in node.children))


def _first_picture(node: MarkdownGroupNode) -> MarkdownGroupNode | None:
    stack = [node]
    while stack:
        n = stack.pop(0)
        if n.type == "image" and n.content:
            return n
        stack.extend(n.children)
    return None


def _pictures_after_a_break(
    node: MarkdownGroupNode,
    cropped: set[int],
    into: list[tuple[str, str]] | None = None,
) -> list[tuple[str, str]]:
    """``(picture, earlier picture)`` for each picture drawn at the default
    ratio because an item without one ended the run its params would have
    reached: an earlier sibling of the same shape chose a ratio or a circle, and
    a pictureless sibling stands between them. The items on either side are then
    two runs, or none, and share nothing. A picture in a repeated run is left to
    `image-ratio`, which already names that run: one fix clears both."""
    found = into if into is not None else []
    in_runs = {
        id(p)
        for run in (node.repeated_children or {}).values()
        for pics in _places(run)
        for p in pics
    }
    kids = node.children
    pictures = [_first_picture(k) for k in kids]
    for j, later in enumerate(pictures):
        # An item is a picture with something beside it; a bare picture
        # between cuts is a lone picture, never a run member.
        if later is None or id(later) not in cropped or not kids[j].children:
            continue
        if id(later) in in_runs:
            continue
        for i in range(j - 1, -1, -1):
            earlier = pictures[i]
            if earlier is None or _shape(kids[i]) != _shape(kids[j]):
                continue
            if id(earlier) in cropped:
                continue  # cut off too: look further back for the params
            between = pictures[i + 1 : j]
            if any(p is None for p in between):
                found.append(
                    (_picture_name(later.content), _picture_name(earlier.content))
                )
            break
    for kid in kids:
        _pictures_after_a_break(kid, cropped, found)
    return found


def _run_name(member: MarkdownGroupNode, picture: MarkdownGroupNode) -> str:
    """The first member's heading, else the first unratioed picture's name."""
    stack = [member]
    while stack:
        n = stack.pop(0)
        if str(n.type).startswith("heading"):
            text = _node_text(n.to_dict()).strip()
            if text:
                return text
        stack.extend(n.children)
    return _picture_name(picture.content)


def _default_ratio_words() -> str:
    """The default ratio ladder in words: ``3:2 (16:9 from 768px, ...)``."""
    first, *steps = DEFAULT_IMAGE_RATIOS.split(",")
    wider = [f"{ratio} from {px}px" for ratio, px in (s.split("@") for s in steps)]
    return f"{first} ({', '.join(wider)})" if wider else first


def _mixed_tappable_runs(
    node: MarkdownGroupNode, into: list[tuple[str, int, list[str]]] | None = None
) -> list[tuple[str, int, list[str]]]:
    """``(first card, members, the untappable)`` for each repeated run of cards
    where some members are tappable and some are not: they draw as one kind of
    card, so a reader expects each to answer a tap the way its neighbours do."""
    found = into if into is not None else []
    for run in (node.repeated_children or {}).values():
        tappable = [m for m in run if m.link_url is not None]
        if _cards(*run) and 0 < len(tappable) < len(run):
            plain = [_card_name(m) for m in run if m.link_url is None]
            found.append((_card_name(run[0]), len(run), plain))
    for child in node.children:
        _mixed_tappable_runs(child, found)
    return found


def _in_link_cards(node: dict, inside: bool = False, into: set | None = None) -> set:
    """The node ids drawn inside a link card. A button there repeating the
    card's target answers as the card does, so it is the card's own offer, not
    a second one."""
    found = into if into is not None else set()
    if inside:
        found.add(node.get("node_id"))
    for child in node.get("children", []):
        _in_link_cards(child, inside or node.get("link_url") is not None, found)
    return found


# A main button's label is measured whole, never wrapped (render_measure's
# `_leaf_natural_width`), so its card is at least as wide as the label. With the
# root THEME.md the pill takes about 9 px a character plus 48 px of padding, and
# a phone card leaves about 330 px inside it, so past 32 characters the label
# alone fills the card.
_MAIN_LABEL_CHARS = 32


def _long_main_label(node: dict) -> str | None:
    """A main button's label, when it is longer than ``_MAIN_LABEL_CHARS``."""
    if node.get("type") != "link" or node.get("link_variant") != "primary":
        return None
    label = plain_link_label(node).strip()
    return label if len(label) > _MAIN_LABEL_CHARS else None


def _nodes_by_id(node: dict, into: dict | None = None) -> dict[str, dict]:
    found = into if into is not None else {}
    found[node.get("node_id", "")] = node
    for child in node.get("children", []):
        _nodes_by_id(child, found)
    return found


def _spelled(action: Action) -> str:
    """An agent action as written in a link: ``agent:slug?k=v``."""
    query = "&".join(f"{k}={v}" for k, v in action.params)
    return f"agent:{action.action}" + (f"?{query}" if query else "")


def _task_box_keys(ast: MarkdownGroupNode) -> set[str]:
    """The node ids of the boxes that open a ``- [ ]`` / ``- [x]`` task item.

    A box written beside its label (``Wi-Fi ... [ ]``) is a toggle: a tick there
    is an action, worth its own event, so it is not here."""
    keys: set[str] = set()
    stack = [ast]
    while stack:
        n = stack.pop()
        if n.type in (NodeType.TASK_OPEN, NodeType.TASK_DONE):
            keys.update(c.node_id for c in n.children if c.node_id)
        stack.extend(n.children)
    return keys


def _lone_boxes(targets: list[Target], tasks: set[str]) -> tuple[int, int] | None:
    """The first plain task box and how many there are, when no button commits
    them: each tick is then an event of its own. A linked box names its own
    action, so its author chose that."""
    boxes = [
        x
        for x, t in enumerate(targets)
        if t.action is not None and t.action.kind == "checkbox" and t.key in tasks
    ]
    if not boxes or any(t.action is not None and t.action.commit for t in targets):
        return None
    return boxes[0], len(boxes)


def _boxes_words(first: int, count: int) -> str:
    if count == 1:
        return f"The task box at target {first} reaches"
    return f"The {count} task boxes from target {first} each reach"


def check_markdown(
    markdown: str, kit: session.GroupingKit, contract: Contract | None = None
) -> list[dict]:
    """Every authoring issue in *markdown*, most severe first within each target.
    With a *contract*, also each element spelling it does not declare."""
    return check_grouped(markdown, session.group_markdown(markdown, kit), contract)


def check_grouped(
    markdown: str, ast: MarkdownGroupNode | None, contract: Contract | None = None
) -> list[dict]:
    """``check_markdown`` on a page already grouped, for a caller that reads the
    same tree for something else and should not group it twice."""
    tree = ast.to_dict() if ast is not None else None
    if ast is None or tree is None or not tree.get("children"):
        return [
            _issue(
                "error",
                "renders-nothing",
                "The document groups to an empty tree and draws nothing: a lone "
                "paragraph does. Add a heading, or a second block.",
            )
        ]
    issues: list[dict] = []
    headings = _dash_split_headings(tree)
    for heading, fix in zip(headings, _heading_fixes(markdown, headings), strict=True):
        issues.append(
            _issue(
                "warning",
                "split-heading",
                f"Heading `{heading}` split into pieces. Escape the dash as `\\-`, "
                "or write an em dash (` — `) when it is punctuation.",
                fix=fix,
            )
        )
    for line in _fallen_back_dividers(markdown):
        issues.append(
            _issue(
                "warning",
                "divider-fallback",
                f"`{line}` is not a valid divider, so it is laid out as `:::`. "
                "Write one number, two numbers (narrow, wide), or a number and "
                "`<` / `>`.",
            )
        )
    for ch, line in _drawn_backslashes(markdown):
        message = (
            f"`\\{ch}` in `{line}` draws its backslash: Markdown escapes ASCII "
            f"punctuation only. Write `{ch}` bare; it never divides, so it needs "
            "no escape."
        )
        fixes = _backslash_fixes(markdown, ch, line)
        issues.extend(
            _issue("warning", "drawn-backslash", message, fix=fix)
            for fix in fixes or [None]
        )
    for problem in _image_param_problems(tree):
        issues.append(_issue("warning", "image-param", f"{problem}."))
    issues.extend(_issue(*p) for p in check_placeholders.problems(tree, contract))
    for name, without, pictures in _unratioed_runs(ast):
        count = f"{without}" if without == pictures else f"{without} of the {pictures}"
        issues.append(
            _issue(
                "warning",
                "image-ratio",
                f"{count} pictures in the repeated run at `{name}` have no ratio — "
                f"the default crops them to {_default_ratio_words()}. Write "
                "`?md2ui.aspect_ratio=W:H` on the first picture for what they show "
                "(skills/images.md, question 1); the run takes it.",
            )
        )
    for picture, earlier in _pictures_after_a_break(ast, _default_cropped(ast)):
        issues.append(
            _issue(
                "warning",
                "image-ratio-after-break",
                f"Picture `{picture}` falls back to the default crop, "
                f"{_default_ratio_words()}: the item without a picture before it ends "
                f"the run whose params `{earlier}` set. Repeat the params on it, "
                "move the pictureless item out of the run, or give the pictureless "
                "item an empty picture, `![Name]()`, so it keeps the run.",
            )
        )
    for message in undeclared(tree, contract) if contract is not None else []:
        issues.append(_issue("warning", "undeclared-spelling", message))
    for card, members, plain in _mixed_tappable_runs(ast):
        names = ", ".join(f"`{name}`" for name in plain)
        issues.append(
            _issue(
                "note",
                "mixed-tappable-run",
                f"The run of {members} cards at `{card}` repeats one kind of card, "
                f"but {names} cannot be tapped and the others can: wrap "
                f"{'it' if len(plain) == 1 else 'them'} as the others are, or "
                "write them as another kind.",
            )
        )
    for name, fix in _cut_styled_names(markdown, tree):
        issues.append(
            _issue(
                "note",
                "dash-in-styled-name",
                f"`{name.replace('`', '')}` is cut in two at its ` - `: styling does not "
                "keep a name whole. Escape the dash as `\\-` to keep the name as "
                "written, or write ` — ` when it is punctuation. To divide it on "
                "purpose, style each piece: `_A_ - _B_`.",
                fix=fix,
            )
        )
    for row, advice in check_charts.rows_left_out(ast):
        issues.append(
            _issue(
                "note",
                "chart-row-left-out",
                f"`{row}` is left out of the chart beside it: {advice}.",
            )
        )
    for first, last, advice in check_charts.runs_without_chart(ast):
        issues.append(
            _issue(
                "note",
                "chart-run-left-text",
                f"The rows from `{first}` to `{last}` draw no chart: {advice}.",
            )
        )
    for pair, advice in check_charts.lines_left_text(ast):
        issues.append(
            _issue("note", "line-left-text", f"`{pair}` draws no line: {advice}.")
        )
    for chain, why, fix in check_charts.chains_without_key(ast):
        issues.append(
            _issue(
                "note", "line-without-key", f"`{chain}` draws no line: {why}, {fix}."
            )
        )
    for unit, why in check_charts.units_not_read(ast):
        issues.append(
            _issue(
                "note",
                "unit-not-read",
                f"If `({unit})` is the unit of the rows below it, it is not read as "
                f"one and they draw as text: {why}, e.g. `Volume (M shares):`.",
            )
        )
    for header in check_charts.headers_apart(ast):
        issues.append(
            _issue(
                "note",
                "chart-header-apart",
                f"`{header}:` is kept from the list below it by a blank line, so "
                "the list draws no chart: a header declares only the rows right "
                "under it. Remove the blank line.",
            )
        )
    for first, last, advice in check_charts.lines_apart(ast):
        issues.append(
            _issue(
                "note",
                "lines-apart",
                f"The lines from `{first}` to `{last}` draw apart: {advice}.",
            )
        )
    heading_ids = _heading_ids(tree)
    offered: dict[tuple, int] = {}
    in_cards = _in_link_cards(tree)
    nodes = _nodes_by_id(tree)
    targets = action_targets(tree)
    issues.extend(_issue(*p) for p in check_choices.problems(tree, targets))
    issues.extend(_issue(*p) for p in check_feeds.problems(markdown, tree))
    for x, target in enumerate(targets):
        if label := _long_main_label(nodes.get(target.key, {})):
            issues.append(
                _issue(
                    "note",
                    "long-main-button",
                    f"Target {x}, `{label}`, is a main button of {len(label)} "
                    "characters, drawn on one line, so its card is at least as wide. "
                    "Name the action in a word or two and write the rest as text "
                    "beside it, or put the item's lines inside the link so they wrap: "
                    '`guide("elements/a-links-label-stays-on-one-line")`.',
                    x,
                )
            )
        action = target.action
        if action is None:
            if not target.disabled:
                issues.append(
                    _issue(
                        "warning",
                        "reports-nothing",
                        f"Target {x} reports nothing when clicked: an empty "
                        "destination, or a bare `agent:` with no action.",
                        x,
                    )
                )
            continue
        for name in _unread_link_params(action):
            reads = (
                "an `agent:` link reads `md2ui.commit` and `md2ui.choice` only"
                if action.kind == "agent"
                else "only an `agent:` link reads one"
            )
            issues.append(
                _issue(
                    "warning",
                    "link-param",
                    f"Target {x}, `{action.label}`: 'md2ui.{name}' does nothing — "
                    f"{reads}, and it is never sent on.",
                    x,
                )
            )
        if action.kind == "anchor" and (action.href or "#")[1:] not in heading_ids:
            issues.append(
                _issue(
                    "error",
                    "anchor-missing",
                    f"`{action.href}` scrolls nowhere: no heading is written "
                    f"`{{{action.href}}}`.",
                    x,
                )
            )
        in_card = target.key.split("#")[0] in in_cards
        if action.kind == "agent" and action.action and not in_card:
            first = offered.setdefault((action.action, action.params), x)
            if first != x:
                issues.append(
                    _issue(
                        "note",
                        "repeated-offer",
                        f"Target {x} offers `{_spelled(action)}` again, as target "
                        f"{first} does: one offer shown twice. Keep one, or give "
                        "each its own params if they do different things.",
                        x,
                    )
                )
        if action.kind == "agent" and "#" in target.key and action.checked is None:
            issues.append(
                _issue(
                    "note",
                    "action-in-sentence",
                    f"`agent:{action.action}` is inside a sentence, where it cannot "
                    "show it was answered. A button on its own line can.",
                    x,
                )
            )
    if boxes := _lone_boxes(targets, _task_box_keys(ast)):
        issues.append(
            _issue(
                "note",
                "boxes-without-commit",
                f"{_boxes_words(*boxes)} the agent alone when ticked, and the "
                "window waits for its answer before the next tick. To send the "
                "list at once, add a button that "
                "commits it, such as `[Save](agent:save?md2ui.commit=1)`; if the "
                "list is only for reading, write its rows without boxes.",
                boxes[0],
            )
        )
    return issues
