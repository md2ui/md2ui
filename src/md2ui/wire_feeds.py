"""A feed: bars and slots on a shown page moved by a process the agent runs,
not by its turns (ADR-608).

The agent declares a feed once; a bar it wrote is the declaration, so a page with
one bar needs no keys. A slot is text its author marked (``wire_texts``):
``[3:53 PM](feed:arrives)``, a chip whose values are declared with the feed, or
a button's label. Anything the agent already runs -- a build, a test loop, a
bridge to a service it trusts -- then posts the page's own spelling
(``Elapsed: 40%``, ``arrives: 3:58 PM``) or a JSON object to the feed's URL
(``wire_feed_posts`` reads it). md2ui runs nothing and fetches nothing: the
producer runs under the host's permissions, and the feed trusts its token, never
its source.

A tick is an ordinary replacement message (ADR-601), so no frontend changes and a
bar without a feed is the same static bar. Posts coalesce: the latest value per
key goes out once per tick, all keys in one message. A post is checked when it
arrives by writing it into the page exactly as the tick will (:meth:`Feeds.post`),
and the tick writes that very text, so a post the tick would refuse is refused
to its process, never later by ending the feed.

Every timing is the server's, so the agent tunes nothing it cannot see:

* the tick follows what one costs -- ten times the last, between 0.25 s and 2 s --
  so a small page moves four times a second and no page takes over a core;
* the silence that ends a feed follows how often its process posts -- ten times
  the usual gap, between 1 and 15 minutes -- so a slow step is not a crash;
* a lifetime caps a feed nobody ended.

A feed ends itself and says what to do next: when its bars are full, when its
process falls silent, posts ``end`` or keeps posting what it cannot use, when
another page is shown without keeping it, when the window closes, or at its
lifetime. Afterwards a post is answered 410, so the process stops too.
"""

from __future__ import annotations

import asyncio
import collections
import secrets
import shlex
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from md2ui import session
from md2ui.check_feeds import barred, clashes, unfed
from md2ui.wire_bars import Figure, bars
from md2ui.wire_feed_posts import check_declared, read_post, spelling
from md2ui.wire_frames import FrameError
from md2ui.wire_texts import HOW, page_slots, set_fed_markdown

if TYPE_CHECKING:
    from md2ui.wire_server import Conversation

TICK = (0.25, 2.0)  # a tick regroups the page here and reloads it in the window
SILENCE = (60.0, 900.0)
LIFETIME = 6 * 3600.0
REFUSALS = 5  # unusable posts in a row before the agent is told
MAX_BODY_BYTES = 4096
MAX_POSTS_PER_SECOND = 50
UNTIL = ("full", "silence")

# Why a feed ended, and what the agent does about it. `replaced` and `closed` are
# not told: the agent showed the new page itself, and a closed window is its own
# event, which names the feeds it stopped.
_WHY = {
    "full": "Feed {id} is done: every bar it moves is full ({shown}). Answer with "
    "the result.",
    "end": "Feed {id} ended: its process posted `end`, at {shown}. Answer with the "
    "result.",
    "silence": "Feed {id} stopped: nothing was posted to it for {quiet} s, at "
    "{shown}. Check that the process posting to it is still running; open a new "
    "feed to resume.",
    "refused": "Feed {id} stopped: its process posted {refusals} times in a row "
    "what it could not use. The first: {detail}. Fix what it posts, then open a "
    "new feed.",
    "lifetime": "Feed {id} stopped after {hours} h, the longest a feed runs, at "
    "{shown}. Open a new feed to continue.",
    "lost": "Feed {id} stopped: its values could no longer be set ({detail}). Show "
    "the page again, then open a new feed.",
}
_UNTOLD = ("replaced", "closed")


@dataclass(frozen=True, slots=True)
class FeedEnded:
    """A feed stopped. Not a wire frame: the binding telling its own caller."""

    feed: str
    reason: str
    values: tuple[tuple[str, float | str], ...]
    text: str

    def heard(self) -> dict:
        return {
            "kind": "feed_ended",
            "feed": self.feed,
            "reason": self.reason,
            "values": dict(self.values),
            "text": self.text,
        }


@dataclass
class Feed:
    id: str
    token: str
    head: str  # the page it moves, as last replaced
    ceilings: dict[str, float | None]  # a bar's; None: a percentage; inf: a chart row
    figures: dict[str, Figure | None]  # a chart row's spelling
    units: dict[str, str]  # what a ratio writes after it (`GB`), else ""
    slots: dict[str, tuple[str, ...] | None]  # each slot's; a chip's declared values
    kinds: dict[str, str]  # each slot's: text, chip or label
    values: dict[str, float | str]  # every key's, in the order the agent named them
    until: str
    started: float
    last_post: float
    pending: dict[str, float | str] = field(default_factory=dict)
    # The server copy the pending values were checked on, and the page they make:
    # what the next tick writes, unless the copy changed under them.
    draft: tuple[str, str] | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)  # a post, or a tick
    posts: collections.deque[float] = field(default_factory=collections.deque)
    gaps: collections.deque[float] = field(
        default_factory=lambda: collections.deque(maxlen=20)
    )
    refused: int = 0  # unusable posts in a row
    first_refusal: str = ""
    ending: bool = False  # `end` was posted: the last values go out first
    moving: bool = False  # being carried to a new page by `show`
    ended: str | None = None

    def full(self) -> bool:
        """Every bar full: a slot is never full (ADR-608)."""
        return all(
            float(self.values[k]) >= (100.0 if c is None else c)
            for k, c in self.ceilings.items()
        )

    def spelled(self, key: str) -> str:
        """*key*'s value as a post writes it: a bar's own spelling, a text as is."""
        value = self.values[key]
        if isinstance(value, str):
            return value
        return spelling(value, self.ceilings[key], self.figures[key])

    def shown(self) -> str:
        """Every value, for what the agent hears: a text quoted, as data from the
        process, never an instruction."""
        return ", ".join(
            f"{k} {self.values[k]!r}" if k in self.slots else f"{k} {self.spelled(k)}"
            for k in self.values
        )

    def row(self) -> dict:
        return {"feed": self.id, "values": dict(self.values)}


def _drawn(
    markdown: str, kit: session.GroupingKit
) -> tuple[list, dict[str, str | None]]:
    """The page's bars, and each slot a bar draws with that bar's key."""
    ast = session.group_shared(markdown, kit)
    return bars(markdown, kit), dict(barred(ast.to_dict())) if ast else {}


class Feeds:
    """Every feed of one conversation. Runs on the conversation's event loop."""

    def __init__(
        self,
        conversation: Conversation,
        clock: Callable[[], float] = time.monotonic,
        tick: tuple[float, float] = TICK,
        silence: tuple[float, float] = SILENCE,
        lifetime: float = LIFETIME,
    ) -> None:
        self._conversation = conversation
        self._clock = clock
        self._tick_range = tick
        self._silence = silence
        self._lifetime = lifetime
        self._cost = 0.0  # what the last tick took, which paces the next
        self._by_token: dict[str, Feed] = {}
        self._count = 0
        self._ticking: asyncio.Task | None = None

    def live(self) -> list[Feed]:
        return [f for f in self._by_token.values() if f.ended is None]

    def listing(self) -> list[dict]:
        """The live feeds, for a result that says what is running."""
        return [f.row() for f in self.live()]

    def interval(self) -> float:
        low, high = self._tick_range
        return min(high, max(low, 10 * self._cost))

    def quiet(self, feed: Feed) -> float:
        """How long *feed* may go unposted: ten of its usual gaps, bounded. Before
        a second post there is no gap to go by, and a process may still start."""
        low, high = self._silence
        if not feed.gaps:
            return 2 * low
        return min(high, max(low, 10 * statistics.median(feed.gaps)))

    async def open(
        self,
        message_id: str,
        keys: list[str] | None,
        until: str | None,
        values: dict[str, list[str]] | None = None,
        slots: list[str] | None = None,
    ) -> Feed:
        """A feed of the bars under *keys* and the *slots* on the page
        *message_id* names; with neither, of the page's one bar. *values*
        declares each chip slot's values, the only ones a post may give it.
        *until* None is ``full`` when only bars are fed, else ``silence``: a slot
        is never full, so a feed that moves one runs on after its bars fill."""
        log = self._conversation.log
        head = log.head(message_id)
        if not log.markdown(head):
            raise FrameError("unknown_message", message_id)
        if head != self._conversation.latest:
            raise FrameError("stale", f"{message_id} is no longer the page shown")
        if until not in (*UNTIL, None):
            raise FrameError("bad_value", f"until is one of {', '.join(UNTIL)}")
        for old in self.live():  # a page no longer shown holds no bar
            if not old.moving and log.head(old.head) != head:
                self._end(old, "replaced")
        markdown = log.markdown(head)
        drawn, under = await asyncio.to_thread(_drawn, markdown, log.kit())
        single = [b for b in drawn if len(b[1]) == 1]
        if not keys and not slots:
            if len(single) != 1:
                here = ", ".join(b[0] for b in single) or "none"
                marked = ", ".join(page_slots(markdown)) or "none"
                raise FrameError(
                    "bad_target",
                    f"this page draws {len(single)} bars ({here}) and marks slots "
                    f"{marked}: name the keys or the slots. To {HOW}",
                )
            keys = [single[0][0]]
        ceilings = self._bars(keys or [], drawn, markdown)
        kinds, current = self._slots(slots or [], drawn, under, markdown)
        declared = check_declared(kinds, values or {})
        until = until or ("silence" if kinds else "full")
        if until == "full" and not ceilings:
            raise FrameError(
                "bad_value",
                'until="full" waits for a bar to fill and this feed moves no bar: '
                'use until="silence"',
            )
        names = list(dict.fromkeys([*ceilings, *kinds]))
        taken = [f for f in self.live() if set(f.values) & set(names)]
        if taken:
            fed = ", ".join(set(taken[0].values) & set(names))
            raise FrameError("bad_target", f"{fed} is already fed by {taken[0].id}")
        current |= {k: v for k, (_c, v, _f, _u) in ceilings.items()}
        self._count += 1
        now = self._clock()
        feed = Feed(
            id=f"f{self._count}",
            token=secrets.token_urlsafe(24),
            head=head,
            ceilings={k: c for k, (c, _v, _f, _u) in ceilings.items()},
            figures={k: f for k, (_c, _v, f, _u) in ceilings.items()},
            units={k: u for k, (_c, _v, _f, u) in ceilings.items()},
            slots={k: declared.get(k) for k in kinds},
            kinds=kinds,
            values={k: current[k] for k in names},
            until=until,
            started=now,
            last_post=now,
        )
        self._by_token[feed.token] = feed
        if self._ticking is None or self._ticking.done():
            self._ticking = asyncio.create_task(self._tick_loop())
        return feed

    @staticmethod
    def _bars(
        keys: list[str], drawn: list, markdown: str
    ) -> dict[str, tuple[float | None, float, Figure | None, str]]:
        """Each key's bar as ``(ceiling, value, figure, unit)``, or a refusal
        naming the bars the page draws."""
        found: dict[str, tuple[float | None, float, Figure | None, str]] = {}
        for key in keys:
            name = _bare(key)
            bar = [b for b in drawn if b[0] == name]
            if len(bar) != 1 or len(bar[0][1]) != 1:
                here = ", ".join(dict.fromkeys(b[0] for b in drawn)) or "none"
                why = "names no bar" if not bar else "does not name exactly one bar"
                hint = " It is a slot: pass it in slots." * (
                    name in page_slots(markdown)
                )
                raise FrameError(
                    "bad_target", f"{key!r} {why}; bars here: {here}.{hint}"
                )
            found[name] = (bar[0][2], bar[0][1][0], bar[0][3], bar[0][4])
        return found

    @staticmethod
    def _slots(
        names: list[str], drawn: list, under: dict[str, str | None], markdown: str
    ) -> tuple[dict[str, str], dict[str, float | str]]:
        """Each slot's kind and current value, or a refusal naming the slots the
        page marks and how to mark one. Refused as ``check`` tells them
        (``feed-bar``, ``feed-key``): a slot drawn by a bar, which no post can
        move, and a slot named as a bar's key in any case, which a post's
        ``name: value`` would not tell from the bar."""
        marked = page_slots(markdown)
        here = ", ".join(marked) or "none"
        keys = {b[0].casefold(): b[0] for b in drawn}
        kinds: dict[str, str] = {}
        current: dict[str, float | str] = {}
        for raw in names:
            name = raw.strip()
            if name in under:
                words = marked[name][0].value if marked.get(name) else ""
                raise FrameError("bad_target", unfed(name, words, under[name]))
            if name.casefold() in keys:
                raise FrameError("bad_target", clashes(name, keys[name.casefold()]))
            if len(marked.get(name, ())) != 1:
                why = "names more than one slot" if name in marked else "names no slot"
                raise FrameError(
                    "bad_target", f"{raw!r} {why}; slots here: {here}. To {HOW}"
                )
            kinds[name], current[name] = marked[name][0].kind, marked[name][0].value
        return kinds, current

    async def send(
        self, markdown: str, keep: list[str], continues: str | None = None
    ) -> str:
        """Show a new page, carrying the feeds in *keep* onto it: each still moves
        bars and slots the page has, written at the feed's latest values so a bar
        never steps back to what the agent last knew. The rest end with the old page.
        *continues* names the page it re-sends (``MessageLog.record``)."""
        conversation = self._conversation
        live = {f.id: f for f in self.live()}
        unknown = [i for i in keep if i not in live]
        if unknown:
            running = ", ".join(live) or "none"
            raise FrameError(
                "bad_target", f"no live feed {unknown[0]}; live: {running}"
            )
        carried = [live[i] for i in keep]
        if carried:
            kit = conversation.log.kit()
            drawn, under = await asyncio.to_thread(_drawn, markdown, kit)
            for feed in carried:
                found = self._bars(list(feed.ceilings), drawn, markdown)
                kinds, _ = self._slots(list(feed.slots), drawn, under, markdown)
                for key, (ceiling, _value, figure, unit) in found.items():
                    if ceiling != feed.ceilings[key]:
                        raise FrameError(
                            "bad_target", f"{key!r} is not the bar {feed.id} moves"
                        )
                    feed.figures[key] = figure
                    feed.units[key] = unit
                for key, kind in kinds.items():
                    if kind != feed.kinds[key]:
                        raise FrameError(
                            "bad_target", f"{key!r} is not the {kind} {feed.id} moves"
                        )
            for feed in carried:
                feed.values |= feed.pending
                feed.pending, feed.draft = {}, None
                markdown = await asyncio.to_thread(
                    set_fed_markdown, markdown, feed.values, kit
                )
        for feed in carried:
            feed.moving = True
        try:
            mid = await conversation.send(markdown, continues=continues)
        finally:
            for feed in carried:
                feed.moving = False
        for feed in carried:
            feed.head = mid
        return mid

    async def post(self, token: str, body: str) -> tuple[int, dict]:
        """Take one post: its status code and what to answer.

        A post is checked by writing it, with the values still pending, into
        the server's copy as the tick will (``wire_texts.set_fed_markdown``):
        refused, it is refused now; accepted, that text is what the tick writes,
        so the two cannot disagree. Each post costs a regroup per value it
        changes, run off the event loop, one post of a feed at a time."""
        feed = self._by_token.get(token)
        if feed is None:
            return 404, {"error": "no such feed"}
        now = self._clock()
        if feed.ended is None and not feed.ending:
            feed.posts.append(now)
            while feed.posts and now - feed.posts[0] > 1.0:
                feed.posts.popleft()
            if len(feed.posts) > MAX_POSTS_PER_SECOND:
                return 429, {"error": f"over {MAX_POSTS_PER_SECOND} posts a second"}
        async with feed.lock:
            if feed.ended is not None or feed.ending:
                return 410, {"error": f"feed {feed.id} ended", "reason": feed.ended}
            try:
                accepted, end = read_post(feed, body)
                if accepted:
                    feed.draft = await asyncio.to_thread(self._drafted, feed, accepted)
            except FrameError as exc:
                feed.refused += 1
                feed.first_refusal = feed.first_refusal or str(exc)
                if feed.refused >= REFUSALS:
                    self._end(feed, "refused", feed.first_refusal)
                return 400, {"error": str(exc)}
            feed.refused, feed.first_refusal = 0, ""
            feed.pending |= accepted
            feed.gaps.append(now - feed.last_post)
            feed.last_post = now
            feed.ending = end
            return 200, {"feed": feed.id, "accepted": accepted}

    def _drafted(self, feed: Feed, accepted: dict) -> tuple[str, str]:
        """*accepted* written into the page the pending values make, on the
        server's current copy: a copy changed since (``mark``, another feed's
        tick) takes the pending values again first."""
        log = self._conversation.log
        copy = log.markdown(log.head(feed.head))  # as the tick finds it
        base, draft = feed.draft or (copy, copy)
        if base != copy:
            base, draft = copy, set_fed_markdown(copy, feed.pending, log.kit())
        return base, set_fed_markdown(draft, accepted, log.kit())

    async def _tick_loop(self) -> None:
        while self.live():
            await asyncio.sleep(self.interval())
            for feed in self.live():
                if not feed.moving:
                    async with feed.lock:
                        await self._tick(feed)

    async def _tick(self, feed: Feed) -> None:
        conversation = self._conversation
        head = conversation.log.head(feed.head)
        if head != conversation.latest:
            return self._end(feed, "replaced")
        if conversation.watched_once and not conversation.watchers:
            return self._end(feed, "closed")
        changed = {k: v for k, v in feed.pending.items() if feed.values[k] != v}
        draft, feed.pending, feed.draft = feed.draft, {}, None

        def edit(markdown: str, kit: session.GroupingKit) -> str:
            # What the posts were checked against, unless the copy moved since.
            if draft is not None and draft[0] == markdown:
                return draft[1]
            return set_fed_markdown(markdown, changed, kit)

        if changed:
            started = time.perf_counter()
            try:
                feed.head = await conversation.apply_feed(head, edit)
            except FrameError as exc:
                return self._end(feed, "lost", str(exc))
            self._cost = time.perf_counter() - started
            feed.values |= changed
        now = self._clock()
        if feed.ending:
            self._end(feed, "end")
        elif changed and feed.until == "full" and feed.full():
            self._end(feed, "full")
        elif now - feed.last_post >= self.quiet(feed):
            self._end(feed, "silence")
        elif now - feed.started >= self._lifetime:
            self._end(feed, "lifetime")

    def end_all(self, reason: str, page: str | None = None) -> tuple[str, ...]:
        """End every live feed at once -- the window closed -- or those on the
        message *page* (a backend showed another, ADR-614), and name them."""
        log = self._conversation.log
        ended = [f for f in self.live() if page in (None, log.head(f.head))]
        for feed in ended:
            self._end(feed, reason)
        return tuple(f.id for f in ended)

    def _end(self, feed: Feed, reason: str, detail: str = "") -> None:
        quiet = f"{self.quiet(feed):.0f}"
        feed.ended = reason
        if reason in _UNTOLD:
            return
        text = _WHY[reason].format(
            id=feed.id,
            shown=feed.shown(),
            quiet=quiet,
            refusals=REFUSALS,
            hours=f"{self._lifetime / 3600:g}",
            detail=detail,
        )
        values = tuple(feed.values.items())
        self._conversation.events.put_nowait(FeedEnded(feed.id, reason, values, text))

    def stop(self) -> None:
        if self._ticking is not None:
            self._ticking.cancel()


def _bare(key: str) -> str:
    return key.strip().strip("*_`").strip()


def snippets(url: str, line: str) -> dict:
    """What the agent pastes: one post, and a loop that forwards a command's
    ``Key: value`` lines and stops when the feed is gone.

    The line carries a bar's key from the page, which may hold anything the
    Markdown did, so it is shell-quoted like the URL: a key is text, never code."""
    code = "%{http_code}"
    said, at = shlex.quote(line), shlex.quote(url)
    return {
        "post": f"curl -s --data-binary {said} {at}",
        "pipe": f"<command printing lines like {said}>"
        + " | while IFS= read -r line; do [ \"$(curl -s -o /dev/null -w '"
        + code
        + f'\' --data-binary "$line" {at})" = 410 ] && break; done',
    }


def route(feeds: Callable[[], Feeds]) -> Route:
    """``POST /feed/{token}``: one post, from a process on this machine.

    A request with an ``Origin`` is a browser's, and a web page has no business
    posting into a feed, so it is refused before its body is read."""

    async def endpoint(request: Request) -> JSONResponse:
        if "origin" in request.headers:
            return JSONResponse({"error": "browsers may not post to a feed"}, 403)
        length = request.headers.get("content-length")
        if length is not None and (
            not length.isdigit() or int(length) > MAX_BODY_BYTES
        ):
            return JSONResponse({"error": f"over {MAX_BODY_BYTES} bytes"}, 413)
        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            return JSONResponse({"error": f"over {MAX_BODY_BYTES} bytes"}, 413)
        try:
            text = body.decode()
        except UnicodeDecodeError:
            return JSONResponse({"error": "the body is not UTF-8 text"}, 400)
        status, answer = await feeds().post(request.path_params["token"], text)
        return JSONResponse(answer, status)

    return Route("/feed/{token}", endpoint, methods=["POST"])
