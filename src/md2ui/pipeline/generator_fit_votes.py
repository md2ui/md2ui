"""One stacks, all stack: the members of a repeated grid run share their fit choices.

A key/value pair goes on one row when the key and the value both fit, and stacks
the key over the value when they do not. Decided member by member, one card of a
run can stack while its neighbours keep their rows, and the run stops reading as
a run. So inside a grid each member's answer is a VOTE, cast at its path inside
the member, and ``stack`` wins: when any member stacks at a path, every member
stacks there.

This is the run poll's second stage (ADR-301). ``_unify_run`` settles the
members' decisions before the grid has a column width; whether a pair fits can
only be asked at that width, while the member is built, so the grid settles
the votes after building its members and builds again only when they
disagreed. The pin is the poll's outcome and the builders read it; nothing
writes one member's result over the others'. A vote goes only to the run that
directly holds its pair: separate runs never outvote each other.

A plain ``Key: value`` pair, which the rules always stack, votes ``stack``
without being asked, so a bar tile among stat tiles stacks like them. Spelling
outranks that vote: a spring pair (``Key: ... value``) is the author asking for
one line, so it stacks only when it, or another pair of its run, really does
not fit.

A ``:::`` row votes the same way: cells that wrap onto separate lines have
moved from beside each other to above each other, so when one member's row
wraps its cells, every member's row puts one cell per line.

One wraps, all wrap: a line, or a weighted ``:::`` row, votes the pieces it wrapped
before, and every member's same line wraps before each of them. Text wrapping inside
a piece still casts nothing.

Sibling lines wrap together too: a run of same-kind lines
that stacks, one per row, opens a poll of its own over the lines, and it
carries only the wrap vote: a stacked line's ``Key: value`` pairs, ``:::``
rows and spacers stay with their grid run. A line inside a grid member votes
in both runs and obeys both pins; a cloud of chips or links wraps as words do
and casts nothing in either.

A run's spacers give way together: where one member's row is short of room
for its spacers, every member's spacers at that path leave their rows, and
where none is, every member keeps them. The renderer obeys the pin
(``render_properties["spacers"]``) instead of deciding card by card.

A stacked run of spring rows shares its column edges: where
every line of the run is one spring row of the same regions, each region takes
the widest ask any row makes for it, as a table column does, so a line chart or
a chip sits at one x down the list instead of moving with each row's name. The
share is the run's alone: sibling spring rows that are not one stacked run keep
their own asks.

The votes are per width: they live inside one ``generate()`` call and are cast
again at the next width.
"""

from __future__ import annotations

from md2ui.pipeline.grouper_types import MarkdownGroupNode, NodeType

# A pair drawn as a display is not counted among the pairs the rules always
# stack: a bar runs its own fit check (it votes when asked), and a line chart's
# key and value never stack.
_BAR_DISPLAYS = frozenset({"kv_percent_bar", "unit_ratio", "line_chart"})


class FitPoll:
    """The fit votes of one grid run, or the wrap votes of one run of sibling
    lines (*lines_only*), by member-relative path."""

    def __init__(self, run: list[MarkdownGroupNode], lines_only: bool = False) -> None:
        self.run = run
        self.lines_only = lines_only
        # {path: {member index: stacked}} from fit checks, the members whose
        # plain pair stands stacked at a path, and the pinned paths: True when
        # a real fit failure pinned it.
        self.votes: dict[str, dict[int, bool]] = {}
        self.seeds: dict[str, set[int]] = {}
        self.pinned: dict[str, bool] = {}
        # {(path, piece kinds): {member: indices of the pieces a new line
        # starts at}}, the union pinned where the members disagreed, and this
        # round's spacer rows as (member, path, row, short of room).
        self.wraps: dict[tuple, dict[int, frozenset[int]]] = {}
        self.wrap_pins: dict[tuple, frozenset[int]] = {}
        self.spacer_rows: list[tuple[int, str, object, bool]] = []
        self.rebuilt = False
        for i, member in enumerate(run if not lines_only else ()):
            for node in _subtree(member):
                if _always_stacks(node):
                    self.seeds.setdefault(_relative(node, member), set()).add(i)

    def locate(self, node: MarkdownGroupNode) -> tuple[int, str] | None:
        """``(member index, path inside it)`` for a node of this run, else None."""
        nid = node.node_id or ""
        for i, member in enumerate(self.run):
            mid = member.node_id or ""
            if mid and (nid == mid or nid.startswith(mid + ".")):
                return i, nid[len(mid) :]
        return None

    def cast(self, member: int, path: str, stacked: bool) -> None:
        """Record a member's answer at *path*; a member that stacked once stays stacked."""
        cast = self.votes.setdefault(path, {})
        cast[member] = cast.get(member, False) or stacked


def _subtree(node: MarkdownGroupNode):
    yield node
    for c in node.children:
        yield from _subtree(c)


def _relative(node: MarkdownGroupNode, member: MarkdownGroupNode) -> str:
    return (node.node_id or "")[len(member.node_id or "") :]


def _always_stacks(node: MarkdownGroupNode) -> bool:
    """A ``Key: value`` pair the rules stack: no bar display."""
    if node.type != NodeType.KEY_VALUE:
        return False
    if node.datapoint_display in _BAR_DISPLAYS:
        return False
    kinds = {c.type for c in node.children}
    return NodeType.KEY in kinds and NodeType.VALUE in kinds


def open_poll(
    polls: list[FitPoll], run: list[MarkdownGroupNode], lines_only: bool = False
) -> FitPoll:
    """Start collecting the fit votes of the grid run *run*, or only the wrap
    votes of the sibling lines *run* (*lines_only*)."""
    poll = FitPoll(run, lines_only)
    polls.append(poll)
    return poll


def stacked_lines(polls: list[FitPoll], run: list[MarkdownGroupNode], build) -> list:
    """*run*'s lines, one per row, each built by *build*: built again once,
    with the run's breaks pinned, when one line wrapped where a twin did not."""
    poll = open_poll(polls, run, lines_only=True)
    while True:
        built = [build(line) for line in run]
        if not settle(polls, poll):
            _share_spring_columns(built)
            return built


def _spring_row(built):
    """The spring row *built* draws as its whole line, through any wrapper of
    one child (a list item's); None when the line is anything else."""
    while built.type != "row" and len(built.children) == 1:
        built = built.children[0]
    return built if built.type == "row" and built.spring and built.ratios else None


def _share_spring_columns(built: list) -> None:
    """Give every row of a stacked run of spring rows the run's widest ask per
    region, when each line is one such row of the same region count."""
    found = [_spring_row(b) for b in built]
    rows = [r for r in found if r is not None]
    if len(rows) < 2 or len(rows) < len(found):
        return
    if len({len(r.ratios) for r in rows}) != 1:
        return
    shared = [max(asks) for asks in zip(*(r.ratios for r in rows))]
    for r in rows:
        r.ratios = list(shared)


def _holders(polls: list[FitPoll], node: MarkdownGroupNode):
    """The open runs whose fit votes *node* casts, as ``(poll, member, path)``:
    the innermost grid run that holds it, innermost first."""
    for poll in reversed(polls):
        if not poll.lines_only and (hit := poll.locate(node)) is not None:
            yield poll, *hit
            return


def _cast(polls: list[FitPoll], node: MarkdownGroupNode, stacked: bool) -> bool | None:
    """Cast *node*'s answer in the innermost open run that holds it; that run's
    pin at its path (True when a real fit failure set it), or None."""
    for poll, member, path in _holders(polls, node):
        poll.cast(member, path, stacked)
        return poll.pinned.get(path)
    return None


def vote(polls: list[FitPoll], node: MarkdownGroupNode, stacked: bool) -> bool:
    """Whether a key/value pair stacks: its own answer, unless its run pinned
    it to ``stack``."""
    pin = _cast(polls, node, stacked)  # cast first: a stacked member's vote counts
    return stacked or pin is not None


def row_stacks(polls: list[FitPoll], node: MarkdownGroupNode, rows: list) -> bool:
    """Whether a ``:::`` row, flowed into *rows*, must put one cell per line
    because its run stacked: it votes ``stack`` when it wrapped its cells."""
    return _cast(polls, node, len(rows) > 1) is True


def line_breaks(
    polls: list[FitPoll], node: MarkdownGroupNode, cells: list, lines: list
) -> set[int]:
    """The pieces *node*'s line must break before because its run wrapped
    there, as ids of *cells*; empty when it already breaks at all of them.
    *lines* are the pieces of each line as flowed; casting them is its vote.
    Only lines of the same pieces are the same line: a member whose line holds
    other kinds of piece is not asked to break where they do. A line votes in
    every run of sibling lines that holds it and in its innermost grid run,
    and breaks where any of them pinned; where one run made it wrap, it votes
    that wrap in the others, so a card's lines carry their wrap to its twins."""
    index = {id(c): k for k, c in enumerate(cells)}
    starts = (index.get(id(p)) for line in lines[1:] for p in line[:1])
    breaks = frozenset(k for k in starts if k is not None)
    kinds = tuple(str(c.type) for c in cells)
    held: list[tuple[FitPoll, int, tuple]] = []
    for poll in reversed(polls):
        if (hit := poll.locate(node)) is not None:
            held.append((poll, hit[0], (hit[1], kinds)))
            if not poll.lines_only:
                break
    pin = frozenset().union(*(p.wrap_pins.get(key, ()) for p, _, key in held))
    for poll, member, key in held:
        poll.wraps.setdefault(key, {})[member] = breaks | pin
    if pin <= breaks:
        return set()
    return {id(cells[k]) for k in pin if k < len(cells)}


def spacer_row(polls: list[FitPoll], node: MarkdownGroupNode, row, short: bool) -> None:
    """Enter *row*, which holds *node*'s spacers, in its run: *short* when the
    row has no room for them, which makes the whole run's give way."""
    for poll, member, path in _holders(polls, node):
        poll.spacer_rows.append((member, path, row, short))


def _pin_spacers(poll: FitPoll) -> None:
    """Pin each path's spacer rows together, where two members hold one."""
    paths: dict[str, list] = {}
    for member, path, row, short in poll.spacer_rows:
        paths.setdefault(path, []).append((member, row, short))
    for found in paths.values():
        if len({m for m, _, _ in found}) < 2:
            continue
        pin = "give_way" if any(s for _, _, s in found) else "keep"
        for _, row, _ in found:
            row.render_properties = {**(row.render_properties or {}), "spacers": pin}


def cell_per_line(width_of, available_width: float):
    """*width_of* for a row that stacks: every cell asks for the whole line, so
    each takes a line of its own; the gaps between them keep their width and
    drop where the row breaks."""
    return lambda c: width_of(c) if c.separator_kind else available_width


def settle(polls: list[FitPoll], poll: FitPoll) -> bool:
    """Close *poll*'s round: True when its members disagreed and must be built
    again with ``stack`` pinned where any of them stacked; False, and the poll
    is closed, once the run stands."""
    if not poll.rebuilt:
        for path, cast in poll.votes.items():
            seeds = poll.seeds.get(path, set())
            failed = any(cast.values())
            if (failed or seeds) and not all(cast.values()):
                if len(set(cast) | seeds) >= 2:
                    poll.pinned[path] = failed
        for key, wraps in poll.wraps.items():
            union = frozenset().union(*wraps.values())
            if len(wraps) >= 2 and any(w != union for w in wraps.values()):
                poll.wrap_pins[key] = union
        if poll.pinned or poll.wrap_pins:
            poll.rebuilt = True
            poll.spacer_rows.clear()
            return True
    _pin_spacers(poll)
    polls.remove(poll)
    return False
