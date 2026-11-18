"""A feed: bars and slots on a shown page moved by a process the agent runs (ADR-608).

The agent opens a feed once, naming bars by the keys it wrote; a process posts
``Key: value`` lines to the feed's URL, and the server moves those bars in its
own copy and sends an ordinary replacement, so the window changes nothing.

  * posts coalesce: the latest value per key goes out once per interval, every
    key in one message, and a post that names nothing new sends nothing;
  * a post is the page's own spelling (``40``, ``40%``, ``4/10``); a key the feed
    was not given, a wrong denominator, a value outside the bar, or a line that is
    not ``Key: value`` refuses the WHOLE post, so a producer never half-applies;
  * the agent's ``post`` snippet shell-quotes its line, so a key runs nothing;
  * a browser may not post (403), a token names one feed (404), a flood is cut
    (429), and a feed that ended answers 410 so its producer can stop;
  * it ends itself -- full, silent, at ``end``, at its lifetime, on another page,
    when the window closes -- and the agent hears why, except for the page it
    replaced itself and a window whose closing is its own event;
  * the id the agent carries survives the feed's ticks, so ``mark`` still lands,
    but not a replacement the agent made: that one is stale;
  * a feed moves the slots its author marked, beside its bars: a text, a chip
    only to a value the agent declared, a button's label keeping its action;
    ``until="full"`` counts the bars, and what the agent hears quotes a text;
  * a slot drawn by a bar or a ratio is refused at open with the fix (feed the
    bar by its key), and so is a slot named as a bar's key in any case;
  * left out, ``until`` is ``silence`` whenever a slot is fed, so a slot is not
    stranded when the bars fill; ``full`` only for a feed of bars alone;
  * a post is checked by writing it as the tick will, so a post the tick would
    refuse is refused to its process, never by ending the feed.

Run with: uv run python tests/wire_feeds_tests.py
"""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

from websockets.sync.client import connect

from md2ui import session
from md2ui.wire import FrameError, Verified
from md2ui.wire_feed_posts import read_post
from md2ui.wire_feeds import FeedEnded, Feeds, snippets
from md2ui.wire_server import Presence, Served, Conversation

PAGE = "# Upload\n\nElapsed: 0%\n\nFiles: 0/10\n\nVolume: [65%]\n"
TICK = 0.1

_MODELS = None


def _kit():
    global _MODELS
    if _MODELS is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _MODELS = session.load_grouping_kit()
    return _MODELS


def _served(
    lifetime: float = 3600.0,
    quiet: float = 60.0,
    tick: float = TICK,
    clock=time.monotonic,
) -> tuple[Served, str]:
    served = Served(Conversation(_kit()))
    conversation = served.conversation
    conversation.feeds = Feeds(
        conversation,
        clock=clock,
        tick=(tick, tick),
        silence=(quiet, 900.0),
        lifetime=lifetime,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        mid = served.call(conversation.send(PAGE))
    return served, mid


def _open(served: Served, mid: str, keys, until="full", values=None, slots=None):
    opened = served.conversation.feeds.open(mid, keys, until, values, slots)
    return served.call(opened)


def _post(served: Served, token: str, body: str, origin: str | None = None):
    base = served.url.removesuffix("/ws").replace("ws://", "http://", 1)
    request = urllib.request.Request(
        f"{base}/feed/{token}", data=body.encode(), method="POST"
    )
    if origin is not None:
        request.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _shown(served: Served) -> str:
    conversation = served.conversation
    return conversation.log.markdown(conversation.latest or "")


def _until(holds, timeout: float = 5.0) -> bool:
    """Whether *holds* came true within *timeout*: a tick regroups the page, so
    under load it can take far longer than its interval, never a fixed sleep."""
    deadline = time.monotonic() + timeout
    while not holds() and time.monotonic() < deadline:
        time.sleep(0.02)
    return holds()


def _ended(served: Served, timeout: float = 5.0) -> FeedEnded:
    event = served.next_event(timeout)
    assert isinstance(event, FeedEnded), event
    return event


def test_posts_coalesce_into_one_replacement_per_tick():
    # The ticks are driven by hand: under load ten posts can take longer than
    # any wall-clock tick, and a tick between them would send twice.
    served, mid = _served(tick=3600.0)
    feeds = served.conversation.feeds

    async def tick(feed) -> None:
        async with feed.lock:
            await feeds._tick(feed)

    try:
        feed = _open(served, mid, ["Elapsed", "Files"])
        for n in range(1, 10):
            assert _post(served, feed.token, f"Elapsed: {n}%")[0] == 200
        status, answer = _post(served, feed.token, "Files: 4/10\nElapsed: 30")
        assert status == 200 and answer["accepted"] == {"Files": 4, "Elapsed": 30}
        assert served.conversation.latest == mid, "a post waits for the tick"
        served.call(tick(feed))
        latest = served.conversation.latest
        log = served.conversation.log
        assert log.head(mid) == latest and latest != mid, (mid, latest)
        assert _shown(served) == PAGE.replace("0%", "30%").replace("0/10", "4/10")
        assert latest == f"c{int(mid[1:]) + 1}", f"one message per tick: {latest}"
        _post(served, feed.token, "Elapsed: 30%")
        served.call(tick(feed))
        assert served.conversation.latest == latest, "a post that moves nothing sends"
    finally:
        served.stop()
    print("  ✓  posts coalesce: one replacement carries every key's latest value")


def test_a_post_is_refused_whole():
    # The feed's clock stands still unless the test moves it: under load sixty
    # round trips can outlast the limit's one-second window and never be cut.
    now = [0.0]
    served, mid = _served(clock=lambda: now[0])
    try:
        feed = _open(served, mid, ["Elapsed", "Files"])
        for body in (
            "Elapsed: 40%\nVolume: 30%",  # not given to this feed
            "Elapsed: 40%\nFiles: 4/12",  # not out of 10
            "Elapsed: 140%",
            "Files: 11",
            '{"Elapsed": 40, "Files": "4/12"}',
            "[40]",
            "Elapsed 40",
        ):
            status, answer = _post(served, feed.token, body)
            assert status == 400 and "error" in answer, (body, status, answer)
            if body == "Files: 11":  # a usable post between: no streak to tell
                assert _post(served, feed.token, '{"Elapsed": 0}')[0] == 200
        assert _post(served, "nope", "Elapsed: 1")[0] == 404
        status, _ = _post(served, feed.token, "Elapsed: 1", origin="http://localhost")
        assert status == 403, "a browser may not post into a feed"
        time.sleep(TICK * 3)
        assert served.conversation.latest == mid, "a refused post applied something"
        codes = [_post(served, feed.token, "Elapsed: 2")[0] for _ in range(60)]
        assert codes[0] == 200 and codes[-1] == 429, codes
        now[0] += 1.5
        assert _post(served, feed.token, "Elapsed: 2")[0] == 200, "a second later"
    finally:
        served.stop()
    print("  ✓  a bad line refuses the whole post; browser, token and flood refused")


def test_opening_names_bars_the_page_draws():
    served, mid = _served()
    try:
        for keys in (["Uptime"], ["Volume"], [], None):  # two bars: name one
            try:
                _open(served, mid, keys)
            except FrameError as exc:
                assert exc.code == "bad_target", exc
            else:
                raise AssertionError(f"opened a feed of {keys}")
        _open(served, mid, ["Elapsed"])
        try:
            _open(served, mid, ["Files", "Elapsed"])
        except FrameError as exc:
            assert "Elapsed is already fed by f1" in str(exc), exc
        else:
            raise AssertionError("two feeds of one bar")
        with contextlib.redirect_stdout(io.StringIO()):
            one = served.call(served.conversation.send("# Run\n\nElapsed: 5%\n"))
        assert list(_open(served, one, None).ceilings) == ["Elapsed"]
    finally:
        served.stop()
    print(
        "  ✓  a feed names bars the page draws, a lone bar needs no key, one feed a bar"
    )


def test_a_full_bar_ends_its_feed_and_the_agent_hears_it():
    served, mid = _served()
    try:
        feed = _open(served, mid, ["Elapsed", "Files"])
        _post(served, feed.token, "Elapsed: 100%")
        time.sleep(TICK * 3)
        assert feed.ended is None, "one full bar of two ends nothing"
        _post(served, feed.token, "Files: 10/10")
        ended = _ended(served)
        assert ended.reason == "full" and dict(ended.values) == {
            "Elapsed": 100,
            "Files": 10,
        }, ended
        assert "Elapsed 100%, Files 10/10" in ended.text, ended.text
        assert _post(served, feed.token, "Elapsed: 5")[0] == 410
    finally:
        served.stop()
    print("  ✓  full bars end the feed: the agent hears it, the producer gets 410")


def test_end_silence_and_lifetime_end_a_feed():
    served, mid = _served(quiet=0.15)
    try:
        feed = _open(served, mid, ["Elapsed"])
        _post(served, feed.token, "Elapsed: 70%\nend")
        ended = _ended(served)
        assert ended.reason == "end" and dict(ended.values) == {"Elapsed": 70}
        assert "Elapsed: 70%" in _shown(served), "the last values go out first"
        quiet = _open(served, served.conversation.latest or "", ["Files"])
        ended = _ended(served)  # no post yet: twice the shortest silence
        assert ended.reason == "silence" and quiet.ended == "silence"
        assert "Check that the process" in ended.text, ended.text
    finally:
        served.stop()
    served, mid = _served(lifetime=0.4)
    try:
        feed = _open(served, mid, ["Elapsed"], until="silence")
        _post(served, feed.token, "Elapsed: 100%")
        time.sleep(TICK * 3)
        assert feed.ended is None, 'until="silence" keeps a feed past full'
        assert _ended(served).reason == "lifetime"
    finally:
        served.stop()
    print("  ✓  `end`, silence and the lifetime each end a feed, and say which")


def test_another_page_or_a_closed_window_ends_it_untold():
    served, mid = _served()
    try:
        feed = _open(served, mid, ["Elapsed"])
        with contextlib.redirect_stdout(io.StringIO()):
            served.call(served.conversation.send("# Done\n"))
        assert _until(lambda: feed.ended == "replaced")
        assert served.next_event(0.3) is None
        assert _post(served, feed.token, "Elapsed: 1")[0] == 410
        latest = served.conversation.latest or ""
        with contextlib.redirect_stdout(io.StringIO()):
            latest = served.call(served.conversation.send(PAGE))
        with connect(served.url, compression=None) as ws:
            ws.send('{"t":"h","v":1}')
            ws.recv(timeout=5)
            watched = _open(served, latest, ["Elapsed"])
        closed = served.next_event(5)
        assert isinstance(closed, Presence) and closed.kind == "closed", closed
        assert closed.feeds == (watched.id,) and watched.ended == "closed", closed
        assert served.next_event(0.3) is None
    finally:
        served.stop()
    print("  ✓  another page ends a feed untold; a closed window names it, at once")


def test_the_agents_id_survives_the_ticks_and_only_them():
    served, mid = _served()
    try:
        feed = _open(served, mid, ["Elapsed"], until="silence")
        _post(served, feed.token, "Elapsed: 40%")
        assert _until(lambda: served.conversation.latest != mid)
        with contextlib.redirect_stdout(io.StringIO()):
            moved = served.call(served.conversation.set_bar(mid, "Files", 3))
        assert served.conversation.latest == moved
        assert "Elapsed: 40%" in _shown(served) and "Files: 3/10" in _shown(served)
        try:
            served.call(served.conversation.set_bar(mid, "Files", 4))
        except FrameError as exc:
            assert exc.code == "stale", exc
        else:
            raise AssertionError("an id the agent replaced itself resolved")
        _post(served, feed.token, "Elapsed: 50%")
        assert _until(lambda: "Elapsed: 50%" in _shown(served))
        assert "Files: 3/10" in _shown(served)
    finally:
        served.stop()
    print("  ✓  `mark` lands through the feed's ticks, and the feed follows `mark`")


def test_the_server_paces_and_the_process_sets_the_silence():
    served, _mid = _served()
    try:
        feeds = Feeds(served.conversation)
        for cost, interval in ((0.003, 0.25), (0.1, 1.0), (0.5, 2.0)):
            feeds._cost = cost
            assert feeds.interval() == interval, (cost, feeds.interval())
        feed = _open(served, _mid, ["Elapsed"], until="silence")
        live = served.conversation.feeds
        assert live.quiet(feed) == 120.0, "before a second post, twice the floor"
        for gap in (10.0, 30.0, 12.0):
            feed.gaps.append(gap)
        assert live.quiet(feed) == 120.0, "ten of the usual 12 s gap"
        feed.gaps.extend([200.0] * 5)
        assert live.quiet(feed) == 900.0, "never past fifteen minutes"
    finally:
        served.stop()
    print("  ✓  the tick follows its cost; the silence follows the process's pace")


def test_a_process_posting_junk_is_told_once():
    served, mid = _served()
    try:
        feed = _open(served, mid, ["Elapsed"])
        codes = [_post(served, feed.token, f"Compiling unit {n}")[0] for n in range(6)]
        assert codes == [400] * 5 + [410], codes
        ended = _ended(served)
        assert ended.reason == "refused" and "'Compiling unit 0'" in ended.text, ended
        assert served.next_event(0.3) is None, "told once, not per post"
    finally:
        served.stop()
    print("  ✓  five unusable posts in a row end the feed and tell the agent the first")


def test_show_can_keep_a_feed_at_its_latest_value():
    served, mid = _served()
    feeds = served.conversation.feeds
    try:
        feed = _open(served, mid, ["Elapsed"], until="silence")
        _post(served, feed.token, "Elapsed: 40%")
        assert _until(lambda: "Elapsed: 40%" in _shown(served))
        for page, why in (("# Other\n\nUptime: 5%\n", "names no bar"),):
            try:
                served.call(feeds.send(page, [feed.id]))
            except FrameError as exc:
                assert why in str(exc), exc
            else:
                raise AssertionError("kept a feed on a page without its bar")
        again = PAGE.replace("# Upload", "# Upload, step 2")  # the agent's 0% is old
        with contextlib.redirect_stdout(io.StringIO()):
            kept = served.call(feeds.send(again, [feed.id]))
        assert "Elapsed: 40%" in _shown(served) and "step 2" in _shown(served)
        time.sleep(TICK * 3)
        assert feed.ended is None and feed.head == kept
        _post(served, feed.token, "Elapsed: 60%")
        assert _until(lambda: "Elapsed: 60%" in _shown(served))
        assert "step 2" in _shown(served)
    finally:
        served.stop()
    print("  ✓  show keeps a feed when asked, writing its latest value in")


def test_a_feed_moves_a_chart_row_in_any_unit():
    """A chart row in a unit other than `%` is fed in the page's own spelling,
    in its chart's declared unit, or bare, and kept in the page's spelling; a
    unit that is not the row's own is refused, naming the spelling it takes."""
    served, mid = _served()
    try:
        chart = (
            "# Spend\n\n- Q1: $1,200\n- Q2: $980\n- Q3: $2,450\n\n"
            "Latency (ms):\n- API: 120\n- DB: 45\n- Cache: 3\n\n"
            "Users (count):\n- Mon: 1.2K\n- Tue: 900\n- Wed: 2K\n"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            mid = served.call(served.conversation.send(chart))
        feed = _open(served, mid, ["Q2", "API", "Mon"])
        assert feed.shown() == "Q2 $980, API 120, Mon 1.2K", feed.shown()
        for body in ("Q2: 340 ms", '{"Q2": -5}', "API: $5"):
            status, answer = _post(served, feed.token, body)
            assert status == 400, (body, answer)
        assert (
            "'Q2' is written as $980"
            in _post(served, feed.token, "Q2: 3 ms")[1]["error"]
        )
        assert _post(served, feed.token, "Q2: $1,500\nAPI: 340 ms\nMon: 1.5K")[0] == 200
        assert _until(lambda: "- Q2: $1,500" in _shown(served)), _shown(served)
        assert _shown(served) == chart.replace("$980", "$1,500").replace(
            "API: 120", "API: 340"
        ).replace("Mon: 1.2K", "Mon: 1.5K")
        assert feed.shown() == "Q2 $1,500, API 340, Mon 1.5K", feed.shown()
        assert _post(served, feed.token, "Q2: 2100\nMon: 1600")[0] == 200
        assert _until(lambda: "- Q2: $2,100" in _shown(served)), _shown(served)
        assert "- Mon: 1.6K" in _shown(served), _shown(served)
    finally:
        served.stop()
    print("  ✓  a feed moves chart rows in the page's spelling, its unit or bare")


def test_a_post_reads_the_sign_and_the_pages_unit():
    """A negative value is refused as outside its bar, by name, on a chart row,
    a percent bar and a ratio alike; a ratio is fed in the page's own spelling,
    its unit included, and a different denominator or unit is refused naming
    that spelling."""
    served, mid = _served()
    try:
        page = (
            "# Host\n\nDisk: 61/128 GB\n\nFiles: 3/10\n\nElapsed: 40%\n\n"
            "Latency (ms):\n- API: 120\n- DB: 80\n- Cache: 3\n"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            mid = served.call(served.conversation.send(page))
        feed = _open(served, mid, ["Disk", "Files", "Elapsed", "API"], "silence")

        def refused(body: str) -> str:
            status, answer = _post(served, feed.token, body)
            assert status == 400, (body, status, answer)
            assert _post(served, feed.token, "Elapsed: 40%")[0] == 200  # no streak
            return answer["error"]

        for body, domain in (
            ("API: -5", "0 or more"),
            ("Elapsed: -5%", "0 to 100"),
            ("Files: -4/10", "0 to 10"),
        ):
            key = body.split(":")[0]
            assert f"is outside the domain of `{key}`, {domain}" in refused(body), body
        assert refused("Disk: 101/100 GB").endswith(
            "'Disk' is not out of 100; it is written as 61/128 GB"
        )
        assert refused("Disk: 101/128 TB").endswith("'Disk' is written as 61/128 GB")
        status, answer = _post(served, feed.token, "Disk: 101/128 GB\nFiles: 4/10")
        assert status == 200 and answer["accepted"] == {"Disk": 101, "Files": 4}
        assert _until(lambda: "Disk: 101/128 GB" in _shown(served)), _shown(served)
        assert _shown(served) == page.replace("61/", "101/").replace("3/10", "4/10")
    finally:
        served.stop()
    print("  ✓  a post's sign reaches the domain; a ratio takes the page's unit")


def test_a_key_in_the_snippet_is_text_never_code():
    """The agent runs ``post`` in a shell, and its line carries a key from the
    page: run as given, a key built to break out of the quotes stays one argument
    and runs nothing. A stand-in ``curl`` records what it was handed."""
    with tempfile.TemporaryDirectory() as tmp:
        pwned = os.path.join(tmp, "pwned")
        line = f"Download';touch {pwned};echo ': 40% $(touch {pwned}) `touch {pwned}`"
        url = "http://127.0.0.1:9/feed/Ab-_9"
        curl = os.path.join(tmp, "curl")
        with open(curl, "w") as f:
            f.write('#!/bin/sh\nprintf "%s\\n" "$@" > "$(dirname "$0")/argv"\n')
        os.chmod(curl, 0o755)
        env = {**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}"}
        subprocess.run(["sh", "-c", snippets(url, line)["post"]], env=env, check=True)
        with open(os.path.join(tmp, "argv")) as f:
            handed = f.read().splitlines()
        assert not os.path.exists(pwned), "the key ran as a command"
        assert handed == ["-s", "--data-binary", line, url], handed
    print("  ✓  a key built to break out of the snippet's quotes runs nothing")


LABEL = "[Track · Received](agent:track?id=BS-1043&md2ui.feed=track)"
ORDER = (
    "# Order BS-1043\n\n_Arrives_\n___[3:53 PM](feed:arrives)___\n\n"
    "[`Received`](feed:status) : _Status_\n\nElapsed: 0%\n\nDue: 3:53 PM\n\n"
    f"{LABEL}\n"
)
STAGES = {"status": ["Received", "Preparing", "On the way"]}


def _order(served: Served, page: str = ORDER) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        return served.call(served.conversation.send(page))


def test_a_feed_moves_slots_beside_a_bar():
    served, _ = _served()
    try:
        mid = _order(served)
        feed = _open(
            served, mid, ["Elapsed"], values=STAGES, slots=["arrives", "status"]
        )
        assert feed.shown() == "Elapsed 0%, arrives '3:53 PM', status 'Received'"
        status, answer = _post(
            served, feed.token, "arrives: 3:58 PM\nstatus: Preparing"
        )
        assert status == 200, answer
        assert answer["accepted"] == {"arrives": "3:58 PM", "status": "Preparing"}
        assert _until(lambda: "[`Preparing`](feed:status)" in _shown(served))
        assert _shown(served) == ORDER.replace("[3:53 PM](feed", "[3:58 PM](feed")\
            .replace("`Received`", "`Preparing`")  # fmt: skip
        body = '{"status": "On the way", "arrives": "Soon", "Elapsed": 100}'
        assert _post(served, feed.token, body)[0] == 200
        ended = _ended(served)  # the one bar is full: the slots count not
        assert ended.reason == "full", ended
        assert dict(ended.values) == {
            "Elapsed": 100,
            "arrives": "Soon",
            "status": "On the way",
        }, ended
        assert "Elapsed 100%, arrives 'Soon', status 'On the way'" in ended.text
    finally:
        served.stop()
    print("  ✓  a feed moves text and chip slots beside a bar, ends on the bar")


def test_opening_names_slots_and_says_how_to_mark_one():
    served, _ = _served()
    try:
        mid = _order(served)
        for keys, slots, values, until, why in (
            (None, ["status"], None, "silence", "declare its values"),
            (None, ["arrives"], {"arrives": ["Soon"]}, "silence", "only a chip's"),
            (None, ["status"], {"status": ["Gone", "a\u200bb"]}, "silence", "U+200B"),
            (None, ["status"], {"Elapsed": ["x"]}, "silence", "not a slot"),
            (None, ["arrives"], None, "full", "no bar"),
            (None, ["Due"], None, "silence", "names no slot; slots here: arrives, "
             "status, track. To mark a value where it is drawn: [3:53 PM](feed:"),
            (["arrives"], None, None, "silence", "It is a slot: pass it in slots"),
        ):  # fmt: skip
            try:
                _open(served, mid, keys, until, values, slots)
            except FrameError as exc:
                assert why in str(exc), (slots, values, exc)
            else:
                raise AssertionError(f"opened {slots} {values} until={until}")
        clash = _order(served, "# Run\n\nElapsed: 5%\n\nStep [one](feed:elapsed)\n")
        for slots, why in ((["elapsed"], "named as the bar `Elapsed`"), (None, "")):
            try:
                feed = _open(served, clash, None, "silence", None, slots)
            except FrameError as exc:
                assert why and why in str(exc), exc
            else:
                assert not why and list(feed.values) == ["Elapsed"], feed.values
        bare = _order(served, "# Note\n\nArrives: 3:53 PM\n")
        try:
            _open(served, bare, None, "silence")
        except FrameError as exc:  # the moment of use: say how to mark a value
            assert "draws 0 bars (none) and marks slots none" in str(exc), exc
            assert "[`Preparing`](feed:status)" in str(exc), exc
        else:
            raise AssertionError("opened a feed of a page with nothing to feed")
    finally:
        served.stop()
    print("  ✓  a feed names the page's slots; a refusal says how to mark a value")


def test_a_post_the_tick_would_refuse_is_refused_when_posted():
    """A post is written into the page as the tick will write it: a value the
    tick would refuse is refused to the producer and the feed runs on, and one
    it accepts lands. Case 2c, `Soon` in a colon column, once answered 200 and
    ended the feed `lost`; it draws as written, so it is accepted and lands."""
    served, _ = _served()
    try:
        colon = "# Order BS-1043\n\n_Arrives_ : ___[3:53 PM](feed:arrives)___\n"
        mid = _order(served, colon)
        feed = _open(served, mid, None, "silence", None, ["arrives"])
        status, answer = _post(served, feed.token, "arrives: a | b")
        assert status == 400 and "beyond its slot" in answer["error"], answer
        time.sleep(TICK * 3)
        assert feed.ended is None and served.conversation.latest == mid
        assert _post(served, feed.token, "arrives: Soon")[0] == 200
        assert _until(lambda: "___[Soon](feed:arrives)___" in _shown(served))
        assert feed.ended is None and served.next_event(0.3) is None
    finally:
        served.stop()
    print("  ✓  a post the tick would refuse is refused at once; case 2c lands")


def test_until_follows_what_the_feed_moves():
    served, _ = _served()
    feeds = served.conversation.feeds
    try:
        mid = _order(served)
        slots = served.call(feeds.open(mid, None, None, STAGES, ["status"]))
        assert slots.until == "silence", "no bar to fill: it runs until quiet"
        bar = served.call(feeds.open(mid, ["Elapsed"], None))
        assert bar.until == "full", "bars alone: it ends when full"
        stages = {"status": [*STAGES["status"], "Delivered"]}
        again = _order(served)  # the shop's tracker: a bar and a stage
        mixed = served.call(feeds.open(again, ["Elapsed"], None, stages, ["status"]))
        assert mixed.until == "silence", "a slot is never full: it runs on"
        assert _post(served, mixed.token, "Elapsed: 100%")[0] == 200
        assert _until(lambda: "Elapsed: 100%" in _shown(served))
        status, answer = _post(served, mixed.token, "status: Delivered")
        assert status == 200, (status, answer)  # the stage after the bar fills
        assert _until(lambda: "[`Delivered`](feed:status)" in _shown(served))
        assert mixed.ended is None
    finally:
        served.stop()
    print("  ✓  until defaults to full for bars alone, else silence")


def test_a_slot_a_bar_draws_or_a_key_names_is_refused_at_open():
    served, _ = _served()
    try:
        for page, slot, why in (
            ("Elapsed: [45%](feed:e)", "e", 'feed it by its key: `keys=["Elapsed"]`'),
            ("Step: [3/10](feed:step)", "step", "`Step: 3/10`"),
            ("Progress: 40%\n\nStatus: [Preparing](feed:progress)", "progress",
             "named as the bar `Progress`"),
            ("Progress: 40%\n\n[Track · x](agent:t?md2ui.feed=PROGRESS)", "PROGRESS",
             "named as the bar `Progress`"),
        ):  # fmt: skip
            mid = _order(served, f"# Order\n\n{page}\n")
            try:
                _open(served, mid, None, "silence", None, [slot])
            except FrameError as exc:
                assert why in str(exc), (page, exc)
            else:
                raise AssertionError(f"opened {slot} on {page!r}")
        # Fed by its key, the bar a clashing slot sat beside moves.
        bar = _order(served, "# Order\n\nProgress: 40%\n")
        feed = _open(served, bar, ["Progress"], "silence")
        assert _post(served, feed.token, "Progress: 70%")[0] == 200
    finally:
        served.stop()
    print("  ✓  a slot a bar draws, or named as a bar in any case, is refused")


def test_a_slot_takes_plain_words_only():
    served, _ = _served()
    try:
        mid = _order(served)
        feed = _open(served, mid, None, "silence", STAGES, ["status", "arrives"])
        for body, why in (
            ("status: Delivered", "takes only 'Received', 'Preparing', 'On the way'"),
            ("arrives: a | b", "beyond its slot"),
            ("arrives: **late**", "would be styled"),
            ("arrives: Late \u202eMP 85:3", "U+202E"),
            ("arrives: " + "a " * 21, "over 40"),
            ("arrives: " + "W" * 25, "a word over 24"),
            ("arrives: Out for delivery right now", "not a sentence"),
            ('{"arrives": "x\\u0007"}', "U+0007"),
            ('{"arrives": ["Soon"]}', "a string or a number"),
            ('{"arrives": true}', "a string or a number"),
        ):
            status, answer = _post(served, feed.token, body)
            assert status == 400 and why in answer["error"], (body, answer)
            assert _post(served, feed.token, "status: Preparing")[0] == 200
        assert _post(served, feed.token, "arrives: 👩\u200d🍳 cooking")[0] == 200
        read = read_post(feed, '{"arrives": "Soon", "status": "Preparing"}')
        assert read == ({"arrives": "Soon", "status": "Preparing"}, False), read
        assert _post(served, feed.token, '{"arrives": 4}')[0] == 200
        assert _until(lambda: "___[4](feed:arrives)___" in _shown(served))
        for _ in range(5):
            _post(served, feed.token, "arrives: [Go](#top)")
        ended = _ended(served)
        assert ended.reason == "refused", ended
        said = "'arrives': '[Go](#top)' would change"  # quoted, as data
        assert said in ended.text, ended.text
    finally:
        served.stop()
    print("  ✓  a chip takes a declared value, a slot plain words; the rest refused")


def test_a_label_feed_keeps_the_button_and_a_press_says_the_new_label():
    served, _ = _served()
    log = served.conversation.log
    try:
        mid = _order(served)
        x = [t.action and t.action.action for t in log.targets(mid)].index("track")
        feed = _open(served, mid, None, "silence", None, ["track"])
        assert _post(served, feed.token, "track: Track · On the way")[0] == 200
        assert _until(lambda: served.conversation.latest != mid)
        new = served.conversation.latest or ""
        assert _shown(served) == ORDER.replace("Track · Received", "Track · On the way")
        action = log.targets(new)[x].action
        assert action is not None
        assert (action.action, action.params) == ("track", (("id", "BS-1043"),))
        pressed = log.verify({"t": "e", "m": new, "x": x, "q": 1})
        assert isinstance(pressed, Verified), pressed
        said = pressed.agent_text()
        assert said == (
            f'User chose "Track · On the way": track {{id: BS-1043}} (message {new})'
        ), said
        stale = log.verify({"t": "e", "m": mid, "x": x, "q": 2})
        assert getattr(stale, "code", None) == "stale", stale
    finally:
        served.stop()
    print("  ✓  a label feed keeps the button; a press is told the label now shown")


def test_show_keeps_a_slot_feed_at_its_latest_value():
    served, _ = _served()
    feeds = served.conversation.feeds
    try:
        mid = _order(served)
        feed = _open(served, mid, None, "silence", STAGES, ["status"])
        _post(served, feed.token, "status: Preparing")
        assert _until(lambda: "`Preparing`" in _shown(served))
        for page, why in (
            ("# Order\n\nStatus: `Received`\n", "names no slot"),
            ("# Order\n\n[Received](feed:status)\n", "is not the text"),
        ):
            try:
                served.call(feeds.send(page, [feed.id]))
            except FrameError as exc:
                assert why in str(exc), exc
            else:
                raise AssertionError(f"kept a chip's feed on {page!r}")
        again = ORDER.replace("# Order BS-1043", "# Order BS-1043, paid")
        with contextlib.redirect_stdout(io.StringIO()):
            served.call(feeds.send(again, [feed.id]))
        assert "[`Preparing`](feed:status)" in _shown(served), _shown(served)
        assert "paid" in _shown(served)
    finally:
        served.stop()
    print("  ✓  show keeps a slot's feed, writing its latest value in")


TESTS = [
    test_posts_coalesce_into_one_replacement_per_tick,
    test_a_post_is_refused_whole,
    test_opening_names_bars_the_page_draws,
    test_a_full_bar_ends_its_feed_and_the_agent_hears_it,
    test_end_silence_and_lifetime_end_a_feed,
    test_another_page_or_a_closed_window_ends_it_untold,
    test_the_agents_id_survives_the_ticks_and_only_them,
    test_the_server_paces_and_the_process_sets_the_silence,
    test_a_process_posting_junk_is_told_once,
    test_show_can_keep_a_feed_at_its_latest_value,
    test_a_feed_moves_a_chart_row_in_any_unit,
    test_a_post_reads_the_sign_and_the_pages_unit,
    test_a_key_in_the_snippet_is_text_never_code,
    test_a_feed_moves_slots_beside_a_bar,
    test_opening_names_slots_and_says_how_to_mark_one,
    test_a_post_the_tick_would_refuse_is_refused_when_posted,
    test_until_follows_what_the_feed_moves,
    test_a_slot_a_bar_draws_or_a_key_names_is_refused_at_open,
    test_a_slot_takes_plain_words_only,
    test_a_label_feed_keeps_the_button_and_a_press_says_the_new_label,
    test_show_keeps_a_slot_feed_at_its_latest_value,
]

if __name__ == "__main__":
    print("Wire Feeds Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
