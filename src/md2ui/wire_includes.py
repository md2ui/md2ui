"""Includes on the wire: expanded before a page is recorded, and drawn again when
a backend's handler answers a click by changing data (ADR-612), or shown as a new
page of the backend's includes when the click only chose one (ADR-614, proposed).

A click handler never edits Markdown. It changes the backend's data and names the
includes whose data changed; the server draws those includes' regions again on
the page shown and sends one replacement (``r``), as a feed's tick does
(ADR-608). The click is not queued for the agent: it is kept as one line of a
digest, handed over with the next thing the agent hears.

The agent's Markdown stays the state: what it wrote outside an include is never
touched, and the id it carries resolves through the replacement
(``MessageLog.head``), which the server made unasked.

A backend whose data changes with no click (an order moving on) names the
includes it touched (:func:`changed`), as a handler's answer does; the page shown
is drawn again the same way, and sent only when it draws differently. The agent
hears it as one :class:`Redrawn` line of the same digest.

A handler may instead return :class:`Show`: a page whose every line is an include
line. It is recorded as a new message and a new page (no ``r``), never as an edit
of the agent's page, which keeps its id and its row in ``history``. While that
page is shown, the agent's ``mark`` or ``patch`` of another page is refused
(:func:`refuse_left`): it would pull the user back from where the backend put them.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Collection
from dataclasses import dataclass, replace
from typing import Any

from md2ui.includes import Includes, expand, redraw
from md2ui.wire import MessageLog, Verified
from md2ui.wire_frames import FrameError


@dataclass(frozen=True, slots=True)
class Show:
    """A handler's answer that is another page: *page*'s every non-blank line is
    an include line naming a registered include (``{{menu category=sides}}``)."""

    page: str


class PageNotDrawn(ValueError):
    """A :class:`Show` the server could not draw whole: a line that is not an
    include, an unknown name, args that do not read, or an expander that failed."""


# fn(params) -> the names of the includes whose data changed, a page of includes
# to show instead, or None: not this handler's click, and the agent hears it.
Handler = Callable[[dict[str, str]], Collection[str] | Show | None]


def record(
    log: MessageLog, includes: Includes, message_id: str, markdown: str, **kw: Any
) -> list[dict]:
    """``MessageLog.record`` of *markdown* with its include lines expanded, the
    region each drew kept beside the page (``includes.Expansions``)."""
    expanded, fresh = expand(markdown, includes)
    frames = log.record(message_id, expanded, **kw)
    if fresh:
        log.pages.includes.add(message_id, expanded, fresh)
    return frames


@dataclass(frozen=True, slots=True)
class Handled:
    """A click a handler answered: the frames sent, and the line the agent is
    told. No frames: the handler failed, and the click is the agent's. *left* is
    the page the user left, when the answer was a new page (:class:`Show`)."""

    frames: list[dict]
    line: str
    left: str | None = None

    def ending(self, feeds: Collection[str]) -> Handled:
        """The line, naming the *feeds* that ended with the page left."""
        if not feeds:
            return self
        return replace(self, line=self.line + ", ending feed " + ", ".join(feeds))


def answer(
    log: MessageLog,
    includes: Includes,
    handler: Handler,
    press: Verified,
    shown: str,
    new_id: str,
) -> Handled | None:
    """Run *handler* for *press*; with the includes it names, draw them again on
    the page *shown* as the replacement *new_id*; with a :class:`Show`, show its
    page as the new message *new_id*. None when the handler declines: the agent
    then hears the click as before. When it fails, nothing is sent and the agent
    hears the click too, with a line saying so: the action and the error's class,
    never its text, which is the backend's."""
    try:
        changed = handler(dict(press.action.params))
        if isinstance(changed, Show):
            return _show(log, includes, changed, press, shown, new_id)
    except Exception as exc:  # noqa: BLE001 -- the agent answers instead
        print(
            f"[wire] handler for {press.action.action!r} failed: {exc!r}",
            file=sys.stderr,
        )
        failed = f"the backend failed on {press.action.action} ({type(exc).__name__})"
        return Handled([], f"{press.agent_text()}: {failed}; the click is yours")
    if changed is None:
        return None
    names = set(changed)
    shown = log.head(shown, through_server_only=True)  # past a commit just written
    regions = log.pages.includes.regions(shown)
    drawn, regions = redraw(log.markdown(shown), regions, includes, names)
    # Sent even when nothing changed: a replacement is what lets the same button
    # be pressed again (an `agent` target fires once per message).
    frames = log.record(new_id, drawn, replaces=shown, by_server=True)
    log.pages.includes.put(new_id, drawn, regions)
    redrawn = sorted({r.name for r in regions if r.name in names})
    line = f"{press.agent_text()}: the backend answered it"
    if redrawn:
        line += ", redrawing " + _named(redrawn)
    failed = {r.line: r.failed for r in regions if r.name in names}
    return Handled(frames, line + _failed(failed) + f" (now message {new_id})")


def _named(names: Collection[str]) -> str:
    return ", ".join(f"{{{{{n}}}}}" for n in names)


def _failed(failed: dict[str, str]) -> str:
    """The includes that drew their failure line or nothing, by include line: the
    user sees no figure there, so the agent may answer for it."""
    said = ", ".join(f"`{call}` ({why})" for call, why in sorted(failed.items()) if why)
    return f"; {said} could not be drawn" if said else ""


@dataclass(slots=True)
class Redrawn:
    """The backend's redraws of the page shown with no click (``changed``), one
    digest line until the agent hears it: what it reasons about moved, though not
    one of its words did. Consecutive ones are one line, naming the last page."""

    names: set[str]
    failed: dict[str, str]
    message_id: str

    def tell(self, digest: list[str | Redrawn]) -> None:
        """Add this to *digest*: one line with a redraw just before it."""
        last = digest[-1] if digest else None
        if not isinstance(last, Redrawn):
            digest.append(self)
            return
        digest[-1] = Redrawn(
            last.names | self.names, last.failed | self.failed, self.message_id
        )

    def __str__(self) -> str:
        return (
            f"the backend redrew {_named(sorted(self.names))} (data changed"
            f"{_failed(self.failed)}; now message {self.message_id})"
        )


def changed(
    log: MessageLog,
    includes: Includes,
    names: Collection[str],
    shown: str,
    new_id: Callable[[], str],
) -> tuple[list[dict], Redrawn] | None:
    """The includes *names* drawn again on the page *shown* from the backend's
    data now, as a handled click draws them, recorded as one replacement. None,
    recording nothing, when the page draws none of them or draws them as before:
    an identical replacement would clear the window's unanswered local state."""
    before = log.markdown(shown)
    regions = log.pages.includes.regions(shown)
    if not any(r.name in names for r in regions):
        return None
    drawn, after = redraw(before, regions, includes, set(names))
    if drawn == before:
        return None
    mid = new_id()
    frames = log.record(mid, drawn, replaces=shown, by_server=True)
    log.pages.includes.put(mid, drawn, after)
    old, new = before.split("\n"), drawn.split("\n")
    moved = [
        (r, a)
        for r, a in zip(regions, after, strict=True)
        if old[r.start : r.end] != new[a.start : a.end]
    ]
    return frames, Redrawn(
        {a.name for _r, a in moved}, {a.line: a.failed for _r, a in moved}, mid
    )


def _show(
    log: MessageLog,
    includes: Includes,
    show: Show,
    press: Verified,
    shown: str,
    new_id: str,
) -> Handled:
    """*show*'s page drawn whole and recorded as the new page *new_id*; or
    :class:`PageNotDrawn`, raised before anything is recorded."""
    lines = [line.strip() for line in show.page.split("\n") if line.strip()]
    expanded, fresh = expand("\n\n".join(lines), includes)
    if not lines or len(fresh) != len(lines) or any(r.failed for r in fresh):
        raise PageNotDrawn(f"drew {len(fresh)} of the include lines {lines}")
    frames = log.record(new_id, expanded, by_server=True)  # a page, not an edit
    log.pages.includes.add(new_id, expanded, fresh)
    showed = ", ".join(r.line for r in fresh)
    line = f"{press.agent_text()}: the backend showed {showed} (now message {new_id})"
    return Handled(frames, line, left=log.pages.latest(shown))


def refuse_left(log: MessageLog, message_id: str, shown: str | None) -> None:
    """Refuse an agent's edit of *message_id* while the page *shown* is one the
    backend showed and *message_id* names another: the edit would be sent as
    the page, pulling the user back from where the backend put them."""
    if shown is None or not log.pages.by_backend(shown):
        return
    page = log.pages.latest(message_id)
    if page != log.pages.latest(shown):
        raise FrameError(
            "bad_target",
            f"the user is on {shown}, a page the backend showed after they left "
            f"{page}: edit {shown}, or show(message_id={page!r}) to bring {page} back",
        )
