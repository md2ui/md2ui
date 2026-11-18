"""The font files the md2ui-ts layout replay loads, for `export_ts_fixtures.py`.

md2ui-ts lays text out with the browser's own measurement, answered from md2ui's
recorded font answers (`measure/`). Where it measures a piece of text md2ui never
measured, the answer has to come from the face md2ui would have used, or it comes
from whatever the browser's machine has. So every face md2ui measured with is
exported with the file it was read from:

* a file a theme names (`## Fonts`, an emoji `Font:`), or md2ui's default emoji
  font, copied from where the theme resolved it;
* a face a theme names by family only (`Arial`, `Georgia`), or a default family
  (a code block's `monospace`, which macOS answers with Courier), which md2ui
  resolved from the system, copied from the system's font folders. A face kept in
  a collection (`Courier.ttc`) is exported as a file of its own, its tables copied
  byte-exact: a browser `FontFace` loads one face per file;
* a face an `Emoji weight` reached in a sibling of a theme's file (a theme
  names `NotoEmoji-Regular.ttf`; weight 700 is `NotoEmoji-Bold.ttf` beside it),
  copied from the folder of the file the theme names;
* a face md2ui reached only as a per-glyph system fallback (`system_face`: a glyph
  no theme face has) is NOT a theme's font and is listed without a file;
* an instance of a variable font a theme names (`varied_face`: an `Emoji weight`,
  `Emoji fill`, `Emoji grade` or `Emoji optical size` set on an icon font's axes)
  is no file of its own: it is listed with its font's file, copied once, and the
  manifest's `axes` gives the coordinates to set on that file.

A variable instance is named by the PostScript name the system gives it, its font's
name followed by one `_<tag><value>` per axis in the font's order: the value is the
coordinate as a 16.16 fixed-point number in upper-case hex, as a 32-bit two's
complement (`wght1F40000` is 500, `GRADFFE70000` is -25), and empty at the axis's
default (`FILL`). Its weight is the instance's `wght`. An instance at one of the
font's named instances is named for it instead (`_Light`: `wght` 300, every other
axis at its default), and takes that instance's coordinates from the font. The
coordinates are kept only when an instance set to them is named the same.

The faces are read from the recordings themselves, so the list is exactly what
md2ui measured with. A face that should have a file and has none raises.

A family name a theme asks for that none of its files holds (a code block's
`monospace`) is answered by the system with a face of another family (Courier);
each theme's such names are listed with the family md2ui resolved them to.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import struct
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import skia  # type: ignore[import-untyped]
from fontTools.ttLib import TTFont

from md2ui.utils.font_loader import (
    load_custom_fonts,
    resolve_code_typeface,
    resolve_typeface,
)
from ts_fixture_layout import face_name

ROOT = Path(__file__).resolve().parent.parent
# md2ui's default emoji font, used when a theme names none (session.load_fonts).
DEFAULT_EMOJI = ROOT / "assets" / "fonts" / "OpenMoji-black-glyf.ttf"
# Where the system keeps the faces a theme names by family alone.
SYSTEM_FONT_DIRS = (
    Path("/System/Library/Fonts"),
    Path("/Library/Fonts"),
    Path.home() / "Library" / "Fonts",
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path.home() / ".local" / "share" / "fonts",
)
_FONT_SUFFIXES = {".ttf", ".otf"}
_COLLECTION_SUFFIXES = {".ttc", ".otc"}
_PATH_FIELDS = ("font_paths", "font_path")


def recorded_faces(records: list[dict]) -> tuple[set[str], set[str]]:
    """Every face in one `measure/` file, and those md2ui reached as a per-glyph
    system fallback (the answers of its `system_face` questions)."""
    faces: set[str] = set()
    fallbacks: set[str] = set()
    for r in records:
        for key in ("face", "like"):
            if isinstance(r.get(key), str):
                faces.add(r[key])
        if r["q"] == "system_face" and isinstance(r["a"], dict) and r["a"]["face"]:
            fallbacks.add(r["a"]["face"])
    return faces | fallbacks, fallbacks


def theme_font_files(resolved: Any) -> list[Path]:
    """Every font file a resolved theme names, found by field name as
    `theme_assets` finds them, in the order the theme names them."""
    found: list[Path] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for name, value in node.items():
                if name in _PATH_FIELDS:
                    paths = value if isinstance(value, list) else [value]
                    found.extend(ROOT / p for p in paths if isinstance(p, str) and p)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(resolved)
    return found


def _face_of_file(path: Path) -> str | None:
    """The face a font file holds, named as the recordings name it."""
    tf = skia.Typeface.MakeFromFile(str(path))
    return None if tf is None else face_name(tf)


def _collection_faces(data: bytes) -> list[bytes]:
    """Each face of a font collection (`ttcf`) as a file of its own: its offset
    table and table records rewritten, every table copied byte-exact."""
    (count,) = struct.unpack_from(">I", data, 8)
    faces = []
    for (start,) in struct.iter_unpack(">I", data[12 : 12 + 4 * count]):
        (tables,) = struct.unpack_from(">H", data, start + 4)
        header = bytearray(data[start : start + 12])
        body = bytearray()
        for i in range(tables):
            tag, checksum, at, length = struct.unpack_from(
                ">4sIII", data, start + 12 + 16 * i
            )
            offset = 12 + 16 * tables + len(body)
            header += struct.pack(">4sIII", tag, checksum, offset, length)
            body += data[at : at + length] + bytes(-length % 4)
        faces.append(bytes(header + body))
    return faces


# A face's file, and its index when the file is a collection.
Source = tuple[Path, int | None]


def _face_bytes(source: Source) -> bytes:
    """The bytes of a file holding the face alone."""
    path, index = source
    data = path.read_bytes()
    return data if index is None else _collection_faces(data)[index]


def _folder_files(folders: Iterable[Path]) -> dict[str, Source]:
    """Every face in *folders*, by face; the first file of a face wins."""
    files: dict[str, Source] = {}
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            suffix = path.suffix.lower()
            if suffix in _FONT_SUFFIXES:
                face = _face_of_file(path)
                if face is not None:
                    files.setdefault(face, (path, None))
            elif suffix in _COLLECTION_SUFFIXES:
                held = _collection_faces(path.read_bytes())
                for index, data in enumerate(held):
                    tf = skia.Typeface.MakeFromData(skia.Data.MakeWithCopy(data))
                    if tf is not None:
                        files.setdefault(face_name(tf), (path, index))
    return files


def _font_names(node: Any) -> set[str]:
    """Every family name a resolved theme asks for (its `font_name` fields)."""
    if isinstance(node, dict):
        names = {v for k, v in node.items() if k == "font_name" and isinstance(v, str)}
        return names.union(*(_font_names(v) for v in node.values())) - {""}
    if isinstance(node, list):
        return set().union(*(_font_names(v) for v in node))
    return set()


def family_aliases(theme: Any, resolved: Any) -> dict[str, str]:
    """Each family name *theme* asks for that md2ui's `resolve_typeface` answers
    with a face of another family, from the system, mapped to that family. The
    family a code block names is resolved as md2ui resolves code
    (`resolve_code_typeface`): one neither loaded nor installed is the
    platform's monospace, never the proportional default."""
    aliases: dict[str, str] = {}
    code = theme.code_blocks.text_style.font_name
    with contextlib.redirect_stdout(io.StringIO()):
        custom = load_custom_fonts(theme.font_paths)
        for name in sorted(_font_names(resolved)):
            resolve = resolve_code_typeface if name == code else resolve_typeface
            family = resolve(name, 400, False, custom).getFamilyName()
            if family.casefold() != name.casefold():
                aliases[name] = family
    return aliases


def _signed_fixed(hex_value: str) -> float:
    """A 16.16 fixed-point number written as 32-bit two's-complement hex."""
    value = int(hex_value, 16)
    return (value - (1 << 32) if value >= 1 << 31 else value) / 65536


def _instance(tf: skia.Typeface, coords: dict[str, float]) -> skia.Typeface:
    """``tf`` set to ``coords``, ``tag -> value``."""
    # Each object named: the position points into the coordinate list, and a
    # temporary freed before ``makeClone`` reads it leaves the default.
    coordinates = skia.FontArguments.VariationPosition.Coordinates(
        [
            skia.FontArguments.VariationPosition.Coordinate(
                int.from_bytes(tag.encode("latin-1"), "big"), value
            )
            for tag, value in coords.items()
        ]
    )
    position = skia.FontArguments.VariationPosition(coordinates)
    args = skia.FontArguments()
    args.setVariationDesignPosition(position)
    return tf.makeClone(args)


def _named_instances(path: Path) -> dict[str, dict[str, float]]:
    """The font's named instances (`fvar`) by subfamily name, ``Light`` -> its
    coordinates."""
    font = TTFont(path, lazy=True)
    if "fvar" not in font:
        return {}
    names = font["name"]
    return {
        str(names.getDebugName(i.subfamilyNameID)): dict(i.coordinates)
        for i in font["fvar"].instances
    }


def variable_instance(face: str, path: Path) -> dict[str, float] | None:
    """The axis coordinates that make *face* of the variable font at *path*, or
    None when *face* is no instance of it (see the module docstring)."""
    tf = skia.Typeface.MakeFromFile(str(path))
    if tf is None:
        return None
    family, postscript = face.split("|")[:2]
    prefix = tf.getPostScriptName() + "_"
    if tf.getFamilyName() != family or not postscript.startswith(prefix):
        return None
    try:
        axes = tf.getVariationDesignParameters()
    except RuntimeError:  # a static face has no parameters to get
        return None
    suffix = postscript[len(prefix) :]
    written = suffix.split("_")
    tags = [axis.tag.to_bytes(4, "big").decode("latin-1") for axis in axes]
    if len(written) == len(axes) and all(
        w.startswith(t) for w, t in zip(written, tags, strict=True)
    ):
        coords = {
            tag: _signed_fixed(w[4:]) if w[4:] else float(getattr(axis, "def"))
            for tag, w, axis in zip(tags, written, axes, strict=True)
        }
    elif (coords := _named_instances(path).get(suffix)) is None:
        return None
    if face_name(_instance(tf, coords)) != face:
        raise RuntimeError(f"{face} does not name the instance its name reads as")
    return coords


def _varied_files(
    faces: Iterable[str], sources: Iterable[Path]
) -> dict[str, tuple[Path, dict[str, float]]]:
    """Each of *faces* that is an instance of one of the font files *sources*:
    ``face -> (file, coordinates)``."""
    varied: dict[str, tuple[Path, dict[str, float]]] = {}
    for face in faces:
        for path in sources:
            coords = variable_instance(face, path)
            if coords is not None:
                varied[face] = (path, coords)
                break
    return varied


def export_fonts(
    out: Path, themes: dict[str, tuple[Any, Any]], doc_themes: dict[str, str]
) -> dict:
    """Copy every face's file under ``<out>/fonts`` and return the manifest entry.

    *themes* maps a theme key to the corpus theme, as md2ui loads it and in its
    resolved fixture form (``theme/``); *doc_themes* maps a document to its theme
    key. The recordings are read from ``<out>/measure``, so the layout stage must
    have run.
    """
    measure = out / "measure"
    if not measure.is_dir():
        raise RuntimeError("the fonts stage reads measure/: run the layout stage first")
    named: dict[str, Source] = {}
    theme_files = [p for _, t in themes.values() for p in theme_font_files(t)]
    for path in theme_files:
        if path.suffix.lower() in _FONT_SUFFIXES and path.is_file():
            face = _face_of_file(path)
            if face is not None:
                named.setdefault(face, (path, None))
    emoji = _face_of_file(DEFAULT_EMOJI)
    if emoji is None:
        raise RuntimeError(f"md2ui's default emoji font is missing: {DEFAULT_EMOJI}")
    named.setdefault(emoji, (DEFAULT_EMOJI, None))

    used: dict[str, set[str]] = {}
    fallbacks: set[str] = set()
    for path in sorted(measure.glob("*/*.jsonl")):
        records = [json.loads(line) for line in path.read_text().splitlines()]
        measured, reached = recorded_faces(records)
        used.setdefault(doc_themes[path.stem], set()).update(measured)
        fallbacks |= reached
    # A theme's own face keeps its file even where another document reached it
    # as a fallback.
    fallbacks -= named.keys()
    resolved = set().union(*used.values()) - fallbacks

    system = _folder_files(SYSTEM_FONT_DIRS) if resolved - named.keys() else {}
    # An instance of a variable font a theme names, from the font's file.
    file_faces = {source: face for face, source in named.items()}
    variable = sorted(path for path, index in file_faces if index is None)
    varied = _varied_files(sorted(resolved - named.keys() - system.keys()), variable)
    # Last, and only for a face none holds: an `Emoji weight`'s sibling file.
    folders = sorted({p.parent for p in theme_files if p.is_file()})
    unfiled = resolved - named.keys() - system.keys() - varied.keys()
    beside = _folder_files(folders) if unfiled else {}
    faces: dict[str, str | None] = dict.fromkeys(fallbacks)
    files: dict[str, dict] = {}
    axes: dict[str, dict[str, float]] = {}
    found: Source | None
    (out / "fonts").mkdir(parents=True, exist_ok=True)
    for face in sorted(resolved):
        held, found = face, None
        if face in varied:
            path, axes[face] = varied[face]
            # The file is listed under the face it holds, its default instance.
            found = (path, None)
            held = file_faces[found]
        else:
            found = named.get(face) or system.get(face) or beside.get(face)
        if found is None:
            raise RuntimeError(f"no font file for the face {face}")
        source, index = found
        data = _face_bytes(found)
        # A collection's face is named for its PostScript name, its suffix for
        # its outlines, and its source for the collection and the face's index.
        if index is None:
            name, origin = f"fonts/{source.name}", source
        else:
            suffix = ".otf" if data[:4] == b"OTTO" else ".ttf"
            name, origin = (
                f"fonts/{face.split('|')[1]}{suffix}",
                Path(f"{source}#{index}"),
            )
        known = files.get(name)
        if known is not None and known["face"] != held:
            raise RuntimeError(f"two faces export as {name}")
        (out / name).write_bytes(data)
        source_name = (
            str(origin.relative_to(ROOT))
            if origin.is_relative_to(ROOT)
            else str(origin)
        )
        files[name] = {
            "face": held,
            "sha256": hashlib.sha256(data).hexdigest(),
            "source": source_name,
        }
        faces[face] = name
    return {
        "faces": dict(sorted(faces.items())),
        "files": dict(sorted(files.items())),
        "themes": {key: sorted(used[key]) for key in sorted(used)},
        "families": {key: family_aliases(*themes[key]) for key in sorted(themes)},
        "axes": dict(sorted(axes.items())),
    }
