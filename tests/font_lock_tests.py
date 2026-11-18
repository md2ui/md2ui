"""
Unit tests for md2ui.utils.font_lock, the fetch behind `make assets` and behind
an installed md2ui's first use of a locked font:

  * a locked font is fetched from a plain URL or from a member of a zip, and an
    archive serving several fonts is downloaded once;
  * a font already as locked is not fetched again;
  * bytes that differ from the lock are refused and never written, so a moved
    upstream cannot change what the tests measure with;
  * ``problems`` (``--check``) names each missing or differing font;
  * only http(s) sources are fetched;
  * ``cached_font`` fetches a locked font into the cache once, and with remote
    fetches off (a server without ``--fetch``) fetches nothing.

Every request goes to a local HTTP server; nothing reaches the network.
Run with: uv run python tests/font_lock_tests.py
"""

import hashlib
import io
import tempfile
import threading
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from md2ui.utils.fetch_policy import POLICY
from md2ui.utils.font_lock import Locked, cached_font, fetch, problems

PLAIN = b"plain font bytes"
ZIPPED = {
    "family/static/A-Regular.ttf": b"regular",
    "family/static/A-Bold.ttf": b"bold",
}


def _zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in ZIPPED.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@contextmanager
def _server() -> Iterator[tuple[str, list[str]]]:
    """Serve /plain.ttf and /family.zip; yield the base URL and the paths requested."""
    requested: list[str] = []
    bodies = {"/plain.ttf": PLAIN, "/family.zip": _zip()}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requested.append(self.path)
            body = bodies.get(self.path)
            self.send_response(200 if body is not None else 404)
            self.end_headers()
            self.wfile.write(body or b"")

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", requested
    finally:
        server.shutdown()
        server.server_close()


def _lock(base: str) -> list[Locked]:
    zip_url = f"{base}/family.zip"
    return [
        Locked("Plain.ttf", _sha(PLAIN), f"{base}/plain.ttf", None, "OFL-1.1"),
        Locked(
            "A-Regular.ttf",
            _sha(b"regular"),
            zip_url,
            "family/static/A-Regular.ttf",
            "OFL-1.1",
        ),
        Locked(
            "A-Bold.ttf", _sha(b"bold"), zip_url, "family/static/A-Bold.ttf", "OFL-1.1"
        ),
    ]


def test_fetches_plain_and_zipped_fonts_once():
    with _server() as (base, requested), tempfile.TemporaryDirectory() as tmp:
        fonts = Path(tmp)
        locked = _lock(base)
        assert [p.split()[0] for p in problems(locked, fonts)] == ["missing"] * 3
        assert fetch(locked, fonts) == []
        assert (fonts / "A-Bold.ttf").read_bytes() == b"bold"
        assert (fonts / "Plain.ttf").read_bytes() == PLAIN
        assert sorted(requested) == ["/family.zip", "/plain.ttf"], requested
        assert problems(locked, fonts) == []
        assert fetch(locked, fonts) == [] and len(requested) == 2, "fetched again"
    print("  ✓  plain and zipped fonts are fetched, an archive once, nothing twice")


def test_bytes_that_differ_from_the_lock_are_refused():
    with _server() as (base, _requested), tempfile.TemporaryDirectory() as tmp:
        fonts = Path(tmp)
        moved = Locked(
            "Plain.ttf", _sha(b"another version"), f"{base}/plain.ttf", None, "OFL-1.1"
        )
        (failure,) = fetch([moved], fonts)
        assert failure.startswith("differs  Plain.ttf"), failure
        assert not (fonts / "Plain.ttf").exists(), "a differing font was written"
        assert not list(fonts.iterdir()), "a partial file was left"
        (fonts / "Plain.ttf").write_bytes(b"tampered")
        assert problems(_lock(base)[:1], fonts) == ["differs  Plain.ttf"]
    print("  ✓  bytes that differ from the lock are refused and never written")


def test_only_http_sources_are_fetched():
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "font.ttf"
        source.write_bytes(PLAIN)
        local = Locked("Plain.ttf", _sha(PLAIN), source.as_uri(), None, "OFL-1.1")
        (failure,) = fetch([local], Path(tmp) / "fonts")
        assert "not an http(s) source" in failure, failure
    print("  ✓  only http(s) sources are fetched")


def _lock_file(folder: Path, base: str) -> Path:
    lock = folder / "fonts.lock"
    lock.write_text(
        f'[[font]]\nfile = "Plain.ttf"\nsha256 = "{_sha(PLAIN)}"\n'
        f'url = "{base}/plain.ttf"\nlicence = "OFL-1.1"\n'
    )
    return lock


def test_a_locked_font_is_fetched_into_the_cache_on_first_use():
    with _server() as (base, requested), tempfile.TemporaryDirectory() as tmp:
        lock, cache = _lock_file(Path(tmp), base), Path(tmp) / "cache"
        assert cached_font("Plain.ttf", lock, cache) == cache / "Plain.ttf"
        assert (cache / "Plain.ttf").read_bytes() == PLAIN
        assert cached_font("Plain.ttf", lock, cache) == cache / "Plain.ttf"
        assert requested == ["/plain.ttf"], f"fetched again: {requested}"
        assert cached_font("Other.ttf", lock, cache) is None, "not locked"
    print("  ✓  a locked font is fetched into the cache once, on first use")


def test_no_font_is_fetched_with_remote_fetches_off():
    with _server() as (base, requested), tempfile.TemporaryDirectory() as tmp:
        lock, cache = _lock_file(Path(tmp), base), Path(tmp) / "cache"
        POLICY.remote = False
        try:
            assert cached_font("Plain.ttf", lock, cache) is None
        finally:
            POLICY.remote = True
        assert requested == [] and not cache.exists(), "a server reached the network"
    print("  ✓  with remote fetches off, a missing locked font stays missing")


TESTS = [
    test_fetches_plain_and_zipped_fonts_once,
    test_bytes_that_differ_from_the_lock_are_refused,
    test_only_http_sources_are_fetched,
    test_a_locked_font_is_fetched_into_the_cache_on_first_use,
    test_no_font_is_fetched_with_remote_fetches_off,
]

if __name__ == "__main__":
    print("Font Lock Tests")
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
