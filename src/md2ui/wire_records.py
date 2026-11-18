"""What the server remembers about the pages it sent, so the agent need not
(ADR-611).

A **page** is a message and every message that carried it on: a replacement
(``mark``, a feed's tick, a patch) or a re-send by id. Any id the page ever had
names its latest message, so a ``[Back](agent:back?page=c1)`` the agent wrote
before the page changed still finds it.

Each section keeps the time its data was last given: a new page gives all of it,
and a page carried on inherits each section's time, unless the carry *renewed*
that section. A section whose comment says ``fresh: 5m`` is **stale** once its
time is older than that. The server only reports it: it never re-reads, and
never refuses a page for it (ADR-608's line: the server acts for the agent only
where the agent wrote it down).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Collection

from md2ui.includes import Expansions
from md2ui.pipeline.render_actions import Target
from md2ui.wire_sections import Section, sections, target_sections, title


class Pages:
    """The pages of one conversation, keyed by every id each has had."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self.started = clock()
        self._page: dict[str, str] = {}  # message id -> its page's first id
        self._latest: dict[str, str] = {}  # page -> its latest message id
        self._sent: dict[str, float] = {}
        self._order: dict[str, int] = {}  # sends can share a clock reading
        self._sections: dict[str, list[Section]] = {}
        self._titles: dict[str, str] = {}
        self._holders: dict[str, list[str | None]] = {}  # message -> target -> section
        self._given: dict[str, dict[str, float]] = {}  # message -> section -> time
        self.includes = Expansions()  # the lines each include drew (ADR-612)
        self._backend: set[str] = set()  # pages a backend's handler showed (ADR-614)

    def sent(
        self,
        message_id: str,
        markdown: str,
        carries: str | None = None,
        renewed: Collection[str] = (),
        grouped: tuple[dict, list[Target]] = ({}, []),
        by_server: bool = False,
    ) -> None:
        """Record *message_id*; *carries* is the message it carries on, if any,
        and *grouped* its tree and targets, so a click can say its section. A
        new page the server sent unasked (*by_server*) is a backend's (ADR-614)."""
        now = self._clock()
        page = self._page.get(carries, message_id) if carries else message_id
        before = self._given.get(carries, {}) if carries else {}
        found = sections(markdown)
        self._page[message_id] = page
        if by_server and not carries:
            self._backend.add(page)
        self.includes.sent(message_id, markdown, carries)
        self._latest[page] = message_id
        self._sent[message_id] = now
        self._order[message_id] = len(self._order)
        self._sections[message_id] = found
        self._titles[message_id] = title(markdown)
        tree, targets = grouped
        keys = [t.key for t in targets]
        self._holders[message_id] = target_sections(markdown, tree, keys)
        self._given[message_id] = {
            s.name: before.get(s.name, now) if s.name not in renewed else now
            for s in found
        }

    def latest(self, message_id: str) -> str:
        """The message that now carries *message_id*'s page; itself if unknown."""
        page = self._page.get(message_id)
        return self._latest[page] if page is not None else message_id

    def by_backend(self, message_id: str) -> bool:
        """Whether *message_id*'s page is one a backend's handler showed."""
        return self._page.get(message_id) in self._backend

    def age(self, message_id: str) -> int | None:
        """Seconds since *message_id* was sent, when this conversation sent it."""
        sent = self._sent.get(message_id)
        return round(self._clock() - sent) if sent is not None else None

    def data_age(self, message_id: str) -> int | None:
        """Seconds since the oldest data on *message_id* was given: its oldest
        section's, else its page's first send. A re-send never makes it younger,
        where ``age`` is the send's own."""
        if message_id not in self._sent:
            return None
        given = self._given[message_id].values()
        oldest = min(given) if given else self._sent[self._page[message_id]]
        return round(self._clock() - oldest)

    def stale(self, message_id: str) -> list[str]:
        """The sections of *message_id* older than their ``fresh:``, by name."""
        now = self._clock()
        given = self._given.get(message_id, {})
        return [
            s.name
            for s in self._sections.get(message_id, [])
            if s.fresh_s is not None and now - given.get(s.name, now) > s.fresh_s
        ]

    def clicked(self, message_id: str, x: int) -> dict:
        """What a click on target *x* of *message_id* came from: its ``section``
        and that section's own ``section_age_s``, the page's ``data_age_s``, and
        ``stale`` when that section is."""
        holders = self._holders.get(message_id, [])
        name = holders[x] if 0 <= x < len(holders) else None
        out: dict = {"section": name} if name else {}
        given = self._given.get(message_id, {})
        if name and name in given:
            out["section_age_s"] = round(self._clock() - given[name])
        if message_id in self._sent:
            out["data_age_s"] = self.data_age(message_id)
        return out | (
            {"stale": True} if name and name in self.stale(message_id) else {}
        )

    def listing(self) -> list[dict]:
        """Each page once, by its latest message, the most recently sent first."""
        rows = []
        latest = sorted(self._latest.values(), key=self._order.__getitem__)
        for mid in reversed(latest):
            row: dict = {
                "message_id": mid,
                "title": self._titles[mid],
                "age_s": self.age(mid),
                "data_age_s": self.data_age(mid),
            }
            sources = {s.name: s.source for s in self._sections[mid] if s.source}
            row |= {"sources": sources} if sources else {}
            row |= {"shown_by": "backend"} if self.by_backend(mid) else {}
            stale = self.stale(mid)
            row |= {"stale": stale} if stale else {}
            rows.append(row)
        return rows
