"""Replace one part of a page in the server's own copy (ADR-611):
a section by its name, or one target by its ordinal; or add whole sections beside
a named one, or remove one; or replace exact text on one line (ADR-611).

The agent still writes every word it changes. What it does not do is reproduce
the rest of the page to change one card, the way ``mark`` spares it re-sending a
page to tick one box: the server edits its copy, so nothing else can drift.

The edit is found, not computed, as ``mark_markdown`` and ``wire_bars`` find
theirs. The place is looked for in the source (``wire_sections`` for a section,
each one-line link for a target), the result is regrouped, and it is kept only
when nothing outside that part changed:

* a section: every word outside it, at the same depth of sections;
* an addition: every word of the page, at the same depth, around the new sections;
* a target: every other target, as it was, and target *x* changed.

A patch that would change more is refused, with what to send instead.
"""

from __future__ import annotations

from typing import Literal

from md2ui import session
from md2ui.pipeline.markdown_grouper import MarkdownGrouper
from md2ui.pipeline.render_actions import Target
from md2ui.wire import MessageLog
from md2ui.wire_edits import _LINK_TOKEN, _signature, _targets
from md2ui.wire_frames import FrameError
from md2ui.pipeline.grouper_block_splits import _break_node_type
from md2ui.pipeline.grouper_feed_slots import feed_slots
from md2ui.pipeline.grouper_types import NodeType
from md2ui.wire_sections import Section, _scan, _words, sections


def _outside(
    markdown: str, k: int, kit: session.GroupingKit, count: int = 1
) -> list[tuple] | None:
    """Every leaf outside heading sections *k* to *k* + *count*, with the depth of
    sections it sits at, in document order; None when the tree's sections are not
    the source's."""
    ast = session.group_shared(markdown, kit)
    tree = ast.to_dict() if ast is not None else {}
    found: list[tuple] = []
    seen = 0

    def walk(node: dict, depth: int, inside: bool) -> None:
        nonlocal seen
        if node.get("heading_group"):
            seen += 1
            inside = inside or k <= seen - 1 < k + count
            depth += 1
        children = node.get("children") or []
        if not children and not inside:
            found.append((str(node.get("type")), node.get("content", ""), depth))
        for child in children:
            walk(child, depth, inside)

    walk(tree, 0, False)
    return found if seen == len(sections(markdown)) else None


def _named(markdown: str, name: str) -> tuple[int, Section]:
    """The one section *name* addresses, by its ``{#id}`` or its heading's words."""
    wanted = {name.strip(), name.strip().strip("{}#"), _words(name.strip("# "))}
    found = sections(markdown)
    hits = [(k, s) for k, s in enumerate(found) if {s.name, s.title} & wanted - {""}]
    if not hits:
        names = ", ".join(repr(s.name) for s in found) or "none"
        raise FrameError("bad_target", f"no section {name!r}; sections: {names}")
    if len(hits) > 1:
        lines = ", ".join(str(s.line + 1) for _k, s in hits)
        raise FrameError(
            "bad_target",
            f"{name!r} names {len(hits)} sections (lines {lines}): give each its "
            "own {#id} and patch by that",
        )
    return hits[0]


def patch_section_markdown(
    markdown: str, name: str, replacement: str, kit: session.GroupingKit
) -> tuple[str, list[str]]:
    """*markdown* with section *name* replaced, and the names of the sections the
    replacement gave anew, whose clocks restart (``wire_records``).

    *replacement* is the whole section, its heading first at the same level, or
    only its body, and then the heading stays. Blank lines around it stay. A
    section its ``***`` closed stays closed: a closer the replacement writes takes
    that one's place, and a subsection it leaves open is closed before it. An
    empty *replacement* removes the section, its heading and its closer too."""
    k, section = _named(markdown, name)
    lines = markdown.split("\n")
    if not replacement.strip():
        candidate = _joined(markdown, lines[: section.start], [], lines[section.end :])
        if not candidate.strip():
            raise FrameError(
                "bad_target",
                f"removing {name!r} would leave the page empty: `show` what it "
                "should say instead",
            )
        before = _outside(markdown, k, kit)
        if before is None or before != _outside(candidate, 0, kit, count=0):
            raise FrameError(
                "bad_target",
                f"removing {name!r} would change the page outside it: `show` the "
                "whole page",
            )
        return candidate, []
    new = replacement.strip("\n").split("\n")
    heading = MarkdownGrouper.HEADING_PATTERN.match(new[0])
    whole = heading is not None
    if heading is not None and len(heading.group(1)) != section.level:
        raise FrameError(
            "bad_target",
            f"{name!r} is a level-{section.level} section: a patch keeps it where "
            f"it is, so its heading starts with {'#' * section.level}",
        )
    end, still = section.end, 1
    if section.closed:  # as many closers as it leaves open; the page's is last
        still = _still_open(new, section.level, whole)
        new += ["***"] * (still - 1) if still else []
        end -= bool(still)  # it wrote its own closer: that one replaces the page's
    while still and end > section.line + 1 and not lines[end - 1].strip():
        end -= 1
    if not whole and not section.closed and not _is_stop(new[-1]):
        # A `***` closing a subsection at the body's end is the page's shape,
        # not the body's words: it stays unless the new body writes its own.
        while end > section.line + 1 and (
            _is_stop(lines[end - 1]) or not lines[end - 1].strip()
        ):
            end -= 1
    start = section.start if whole else section.line + 1
    while not whole and start < end and not lines[start].strip():
        start += 1  # a blank line under the heading stays
    candidate = "\n".join(lines[:start] + new + lines[end:])
    before = _outside(markdown, k, kit)
    if before is None or before != _outside(candidate, k, kit):
        raise FrameError(
            "bad_target",
            f"replacing {name!r} would change the page outside it: send one "
            "section, with no heading of its level or above after its first "
            "line, or `show` the whole page",
        )
    given = sections(candidate)
    renewed = [s.name for s in given if start <= s.line < start + len(new)]
    return candidate, renewed + [section.name]


def insert_section_markdown(
    markdown: str,
    anchor: str,
    side: Literal["after", "before"],
    block: str,
    kit: session.GroupingKit,
) -> tuple[str, list[str]]:
    """*markdown* with *block*, one or more whole sections at *anchor*'s level,
    added *side* it, and the names of the sections it added, whose clocks start.

    After a section is past its subsections and its ``***`` closer, if it has
    one, and then the block is closed too, so the words after it stay where
    they were; before one is above its heading and any run glued to it.
    Every word of the page must come out unchanged, at the same depth: a block
    that would take in the words after it, or nest in the section above, is
    refused with the call that does what it meant."""
    if not sections(markdown):
        raise FrameError(
            "bad_target",
            f"this page has no headings, so no sections to add {side}: `show` "
            "the whole page with the new part",
        )
    _k, section = _named(markdown, anchor)
    if not block.strip():
        raise FrameError(
            "bad_target",
            f"{side} takes one or more sections to add; to remove {anchor!r}, "
            f'patch(section={anchor!r}, markdown="")',
        )
    new = block.strip("\n").split("\n")
    level, hashes = section.level, "#" * section.level
    headings, _breaks = _scan(new)
    if not headings or headings[0][0] != 0:
        raise FrameError(
            "bad_target",
            f"start the block with a level-{level} heading ({hashes} …), as "
            f"{anchor!r} is a level-{level} section: text before it would join the "
            "section above",
        )
    if headings[0][1] > level:
        raise FrameError(
            "bad_target",
            f"a level-{headings[0][1]} heading would nest in the section above: "
            f"to add inside {anchor!r}, patch it with patch(section={anchor!r}, …)",
        )
    taken = {s.name for s in sections(markdown)}
    for _line, deeper, text in headings:
        attr = MarkdownGrouper.HEADING_ID_PATTERN.search(text)
        if attr and attr.group(1) in taken:
            raise FrameError(
                "bad_target",
                f"{{#{attr.group(1)}}} is already on the page: patch that section "
                f"by patch(section={attr.group(1)!r}, …)",
            )
        if deeper < level:
            raise FrameError(
                "bad_target",
                f"a level-{deeper} heading would take in the sections after it: "
                f"add level-{level} sections, deeper ones inside them, or patch "
                "the section that holds them by patch(section=…)",
            )
    if side == "after" and section.closed:  # closed as the anchor is
        new += ["***"] * max(_still_open(new, level, False) - 1, 0)
    lines = markdown.split("\n")
    at = section.end if side == "after" else section.start
    candidate = _joined(markdown, lines[:at], new, lines[at:])
    first = sum(s.line < at for s in sections(markdown))
    before = _outside(markdown, 0, kit, count=0)
    if before is None or before != _outside(candidate, first, kit, len(headings)):
        raise FrameError(
            "bad_target",
            f"adding {side} {anchor!r} would change the page around it: send "
            f"only whole level-{level} sections, or `show` the whole page",
        )
    given = sections(candidate)
    return candidate, [s.name for s in given[first : first + len(headings)]]


def _joined(markdown: str, head: list[str], new: list[str], tail: list[str]) -> str:
    """*head*, *new* and *tail* one blank line apart, the page's last newline kept."""
    while head and not head[-1].strip():
        head = head[:-1]
    while tail and not tail[0].strip():
        tail = tail[1:]
    parts = ["\n".join(part) for part in (head, new, tail) if part]
    text = "\n\n".join(parts)
    return text + "\n" if markdown.endswith("\n") and not text.endswith("\n") else text


def _is_stop(line: str) -> bool:
    return _break_node_type(line) == NodeType.SECTION_STOP


def _still_open(new: list[str], level: int, whole: bool) -> int:
    """How many sections are open at the end of *new*: the patched one, unless
    the replacement closed it, and each subsection it opened and left open."""
    headings, breaks = _scan(new)
    levels = {line: lvl for line, lvl, _text in headings[1 if whole else 0 :]}
    open_levels = [level]
    for j in range(len(new)):
        if j in levels:
            while len(open_levels) > 1 and open_levels[-1] >= levels[j]:
                open_levels.pop()
            open_levels.append(levels[j])
        elif j in breaks and _is_stop(new[j]):
            open_levels.pop()
            if not open_levels:
                return 0
    return len(open_levels)


def replace_text_markdown(
    markdown: str, edits: list[tuple[str, str]], kit: session.GroupingKit
) -> tuple[str, list[str]]:
    """*markdown* with each ``(old, new)`` exact text replaced, all or none, and the
    names of the sections the edits fall in, whose clocks restart.

    The edit that ``section`` and ``x`` cannot reach: a picture's URL, one word in a
    long section, a section whose heading has no words
    (ADR-611). Each edit stays on one line and each *old*
    is on the page exactly once, so an edit names its place by its own text; the
    page's headings stay as they were, and every word outside the edited sections
    must come out unchanged, as for a section patch."""
    if not edits:
        raise FrameError("bad_target", "replace names no edit: give old and new")
    spans: list[tuple[int, int, str]] = []
    for old, new in edits:
        if not old or "\n" in old or "\n" in new:
            raise FrameError(
                "bad_target",
                "a replace edits text on one line: to change lines, patch the "
                "`section`",
            )
        count = markdown.count(old)
        if count != 1:
            where = (
                "is not on the page" if not count else f"is on the page {count} times"
            )
            raise FrameError(
                "bad_target",
                (not count and _fed_slot(markdown, old))
                or f"{old!r} {where}: replace text that appears once, with more of "
                "what is around it",
            )
        at = markdown.index(old)
        spans.append((at, at + len(old), new))
    spans.sort()
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        raise FrameError("bad_target", "two replace edits overlap: merge them into one")
    edited, last = [], 0
    for start, end, new in spans:
        edited += [markdown[last:start], new]
        last = end
    candidate = "".join(edited) + markdown[last:]
    before, after = sections(markdown), sections(candidate)
    if [s.level for s in before] != [s.level for s in after]:
        raise FrameError(
            "bad_target",
            "a replace may not add or remove a heading: patch the `section`",
        )
    lines = [markdown.count("\n", 0, start) for start, _end, _new in spans]
    # Each edit falls in its innermost section: the last one opened above it.
    hit = sorted(
        {
            max(
                (k for k, s in enumerate(before) if s.start <= line < s.end), default=-1
            )
            for line in lines
        }
        - {-1}
    )
    if hit:
        k, count = hit[0], hit[-1] - hit[0] + 1
        outside = _outside(markdown, k, kit, count)
        if outside is None or outside != _outside(candidate, k, kit, count):
            raise FrameError(
                "bad_target",
                "the replace would change the page outside the sections it edits: "
                "patch the `section`, or `show` the whole page",
            )
    return candidate, [after[k].name for k in hit]


def _fed_slot(markdown: str, old: str) -> str:
    """Why *old* is not on the page when it quotes a slot a feed has written since
    (ADR-608): the page holds the fed value, not the one the agent wrote."""
    quoted = {slot.name for slot in feed_slots(old)}
    for slot in feed_slots(markdown):
        if slot.name in quoted and slot.value not in old:
            now = markdown[slot.construct[0] : slot.construct[1]]
            return (
                f"{old!r} is not on the page: it quotes the slot {slot.name!r}, which "
                f"now holds {slot.value!r}, as its feed wrote it. Quote the slot as "
                f"the page holds it, {now}, or leave its value for the feed to change"
            )
    return ""


def _key(target: Target) -> tuple:
    return _signature(target), target.action.label if target.action else None


def patch_target_markdown(
    markdown: str, x: int, replacement: str, kit: session.GroupingKit
) -> str:
    """*markdown* with target *x*, a one-line link or button, replaced by
    *replacement*, and nothing else: ``[🤍](agent:like?id=3)`` becomes
    ``[❤️](agent:unlike?id=3)``."""
    before = _targets(markdown, kit)
    if not 0 <= x < len(before):
        raise FrameError("bad_target", f"no target {x}")
    new = replacement.strip()
    if not new or "\n" in new:
        raise FrameError(
            "bad_target", "x takes one line: a link or a button; patch its section"
        )
    action = before[x].action
    tokens = list(_LINK_TOKEN.finditer(markdown))
    if action is not None:  # its own spelling first: each try regroups the page
        tokens.sort(key=lambda m: (action.href or "") not in m.group(0))
    for m in tokens:
        if m.group(0) == new:
            continue
        candidate = markdown[: m.start()] + new + markdown[m.end() :]
        after = _targets(candidate, kit)
        if (
            len(after) == len(before)
            and all(
                _key(a) == _key(b)
                for i, (a, b) in enumerate(zip(after, before))
                if i != x
            )
            and _key(after[x]) != _key(before[x])
        ):
            return candidate
    if any(m.group(0) == new for m in tokens):
        return markdown  # already written so
    raise FrameError(
        "bad_target",
        f"no one-line link edit changes only target {x}: a task box, a slider or a "
        "card is patched by its section, and the replacement must stay one target",
    )


def patch_page(
    log: MessageLog,
    message_id: str,
    markdown: str,
    section: str | None,
    x: int | None,
    side: Literal["after", "before"] | None = None,
    replace: list[tuple[str, str]] | None = None,
) -> tuple[str, str, list[str]]:
    """``(page, edited, renewed)``: the message the patch applies to, its Markdown
    patched, and the sections whose clocks restart. A section patches the page's
    latest message, whichever id named it; with *side*, *section* is the one the
    new sections go beside. *x* is an ordinal of the message it was read on, so
    that one must still be the page's latest, as for ``mark``. *replace* edits
    exact text instead, on the page's latest message."""
    if x is None:
        mid = log.pages.latest(message_id)
    else:
        mid = log.head(message_id, through_server_only=True)
        latest = log.pages.latest(mid)
        if latest != mid:
            raise FrameError(
                "stale",
                f"x numbers the targets of {message_id}, and the page is now "
                f"{latest}: read its offers there (`showing`) and patch {latest}",
            )
    old = log.markdown(mid)
    if not old:
        raise FrameError("unknown_message", message_id)
    if x is not None:
        edited, renewed = patch_target_markdown(old, x, markdown, log.kit()), []
    elif replace is not None:
        edited, renewed = replace_text_markdown(old, replace, log.kit())
    elif side is not None:
        edited, renewed = insert_section_markdown(
            old, section or "", side, markdown, log.kit()
        )
    else:
        edited, renewed = patch_section_markdown(
            old, section or "", markdown, log.kit()
        )
    log.pages.includes.refuse(mid, old, edited)  # an include's lines (ADR-612)
    return mid, edited, renewed
