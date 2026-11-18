"""The locked fonts: each font file md2ui's themes name, byte for byte as locked.

No font lives in the repository or in the package. `assets/fonts.lock` names
every font file the root `THEME.md` and the themes in the snapshot corpus use:
where it comes from (a pinned URL, and the member path when the URL is an
archive), its SHA-256 and its licence. Two callers share this one fetch:

* a checkout's `make assets` (`scripts/fetch_assets.py`) fills `assets/fonts/`;
* an installed md2ui, which ships no font, fetches a locked font the first time
  a theme names it, into the per-user cache (`cached_font`).

Either way a file whose bytes differ from the lock is refused and never written:
tests measure text with these fonts and the render snapshot compares pixels, so a
different version would move them for a reason no code change explains. Every
download is checked before it is written, and written atomically, so an
interrupted run leaves no partial font behind. Only http(s) sources are fetched.
"""

from __future__ import annotations

import hashlib
import io
import os
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path

from md2ui.utils.fetch_policy import POLICY

CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "md2ui/fonts"
"""Where an installed md2ui keeps the fonts it fetched, the theme URL fonts too:
``~/.cache/md2ui/fonts``, or under ``$XDG_CACHE_HOME`` when that is set."""


@dataclass(frozen=True)
class Locked:
    file: str
    sha256: str
    url: str
    member: str | None  # the path inside the archive *url* names, or None
    licence: str


def read_lock(path: Path) -> list[Locked]:
    entries = tomllib.loads(path.read_text(encoding="utf-8"))["font"]
    return [
        Locked(e["file"], e["sha256"], e["url"], e.get("member"), e["licence"])
        for e in entries
    ]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def problems(locked: list[Locked], fonts: Path) -> list[str]:
    """Each locked file that is missing or differs from its hash, as a line."""
    out = []
    for entry in locked:
        path = fonts / entry.file
        if not path.is_file():
            out.append(f"missing  {entry.file}")
        elif _sha256(path.read_bytes()) != entry.sha256:
            out.append(f"differs  {entry.file}")
    return out


def _get(url: str) -> bytes:
    if not url.startswith("https://") and not url.startswith("http://"):
        raise ValueError(f"not an http(s) source: {url}")
    import urllib.request  # here, as image_cache does: not on every start

    request = urllib.request.Request(url, headers={"User-Agent": "md2ui-fetch-assets"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch(locked: list[Locked], fonts: Path) -> list[str]:
    """Fetch every locked file that is missing or differs; the failures, as lines."""
    fonts.mkdir(parents=True, exist_ok=True)
    downloads: dict[str, bytes] = {}  # one download per URL: an archive serves many
    failures = []
    for entry in locked:
        path = fonts / entry.file
        if path.is_file() and _sha256(path.read_bytes()) == entry.sha256:
            continue
        try:
            if entry.url not in downloads:
                print(f"[assets] fetch  {entry.url}")
                downloads[entry.url] = _get(entry.url)
            data = downloads[entry.url]
            if entry.member is not None:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    data = archive.read(entry.member)
        except Exception as exc:
            failures.append(f"failed   {entry.file}: {exc}")
            continue
        if _sha256(data) != entry.sha256:
            failures.append(
                f"differs  {entry.file}: the source's bytes are not the locked ones"
            )
            continue
        partial = path.with_name(path.name + ".part")
        partial.write_bytes(data)
        partial.replace(path)
        print(f"[assets] ok     {entry.file}  ({entry.licence})")
    return failures


def cached_font(name: str, lock: Path, cache: Path = CACHE) -> Path | None:
    """The per-user copy of the locked font file *name*, fetched on first use.

    ``None`` when *lock* does not name it, or when it is not cached as locked and
    cannot be fetched: remote fetches are off (a server started without
    ``--fetch``, fetch_policy), or the source failed or served other bytes.
    """
    entry = next((e for e in read_lock(lock) if e.file == name), None)
    if entry is None:
        return None
    if problems([entry], cache):
        if not POLICY.remote:
            return None
        for line in fetch([entry], cache):
            print(f"[fonts] {line}")
        if problems([entry], cache):
            return None
    return cache / name
