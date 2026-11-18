"""
Unit tests for the image download a first open makes:

  * it names itself — md2ui, its version and a project URL in ``User-Agent`` —
    because Wikimedia answers a burst from an anonymous ``Mozilla/5.0`` with
    ``429 Too many requests`` and a self-identified client with the pictures;
  * a ``429`` is retried once, after its ``Retry-After``; a second ``429`` fails;
  * the wait is capped, and a missing or unreadable ``Retry-After`` waits a short
    default instead;
  * only http(s) is fetched: a ``file://`` picture is refused before anything is
    read, and so is a redirect that leaves http(s).

Every request goes to a local HTTP server; nothing reaches the network.
Run with: uv run tests/image_fetch_tests.py
"""

import tempfile
import threading
import urllib.error
from pathlib import Path
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from md2ui.utils.image_cache import (
    _RETRY_AFTER_CAP,
    _RETRY_AFTER_DEFAULT,
    _USER_AGENT,
    _download,
    _retry_delay,
)

_BODY = b"\x89PNG not really"
_ELSEWHERE = "ftp://127.0.0.1/secret.png"  # where a 302 points


@contextmanager
def _server(statuses: list[int]) -> Iterator[tuple[str, list[dict[str, str]]]]:
    """Serve *statuses* in order, one per request; yield the URL and the headers seen."""
    seen: list[dict[str, str]] = []
    queue = list(statuses)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            seen.append(dict(self.headers))
            status = queue.pop(0) if queue else 500
            self.send_response(status)
            if status == 429:
                self.send_header("Retry-After", "0")
            if status == 302:
                self.send_header("Location", _ELSEWHERE)
            self.send_header("Content-Length", str(len(_BODY)))
            self.end_headers()
            self.wfile.write(_BODY)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/pic.png", seen
    finally:
        server.shutdown()
        server.server_close()


def test_download_names_md2ui_in_user_agent() -> None:
    with _server([200]) as (url, seen):
        assert _download(url) == _BODY
    agent = seen[0]["User-Agent"]
    assert agent == _USER_AGENT, agent
    assert agent.startswith("md2ui/"), agent
    assert "Mozilla" not in agent, agent
    assert "http" in agent, f"no project URL in {agent!r}"


def test_429_then_200_succeeds_after_one_retry() -> None:
    with _server([429, 200]) as (url, seen):
        assert _download(url) == _BODY
    assert len(seen) == 2, len(seen)


def test_429_twice_fails() -> None:
    with _server([429, 429, 200]) as (url, seen):
        try:
            _download(url)
        except urllib.error.HTTPError as exc:
            assert exc.code == 429, exc.code
        else:
            raise AssertionError("a second 429 must fail, not retry again")
    assert len(seen) == 2, len(seen)


def test_other_errors_are_not_retried() -> None:
    with _server([503, 200]) as (url, seen):
        try:
            _download(url)
        except urllib.error.HTTPError as exc:
            assert exc.code == 503, exc.code
        else:
            raise AssertionError("only a 429 is retried")
    assert len(seen) == 1, len(seen)


def test_retry_after_is_capped() -> None:
    assert _retry_delay("2") == 2.0
    assert _retry_delay("0") == 0.0
    assert _retry_delay("3600") == _RETRY_AFTER_CAP
    assert _RETRY_AFTER_CAP <= 10


def test_missing_or_unreadable_retry_after_waits_the_default() -> None:
    assert _retry_delay(None) == _RETRY_AFTER_DEFAULT
    assert _retry_delay("Wed, 21 Oct 2026 07:28:00 GMT") == _RETRY_AFTER_DEFAULT
    assert _retry_delay("-5") == _RETRY_AFTER_DEFAULT
    assert _retry_delay("nan") == _RETRY_AFTER_DEFAULT
    assert 0 < _RETRY_AFTER_DEFAULT <= _RETRY_AFTER_CAP


def test_only_http_pictures_are_fetched() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        secret = Path(tmp) / "secret.png"
        secret.write_bytes(_BODY)
        for url in (secret.as_uri(), secret.as_uri().upper(), "ftp://127.0.0.1/x.png"):
            try:
                _download(url)
                raise AssertionError(f"{url} was read")
            except ValueError as exc:
                assert "not an http(s) picture" in str(exc), exc
    with _server([302]) as (url, seen):
        try:
            _download(url)
            raise AssertionError("a redirect off http(s) was followed")
        except ValueError as exc:
            assert _ELSEWHERE in str(exc), exc
        assert len(seen) == 1, seen
    print("  ✓  only http(s) is fetched: file:// and a redirect off it are refused")


TESTS = [
    test_download_names_md2ui_in_user_agent,
    test_429_then_200_succeeds_after_one_retry,
    test_429_twice_fails,
    test_other_errors_are_not_retried,
    test_retry_after_is_capped,
    test_missing_or_unreadable_retry_after_waits_the_default,
    test_only_http_pictures_are_fetched,
]


if __name__ == "__main__":
    print("Image Fetch Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"  ✓  {test.__name__}")
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
