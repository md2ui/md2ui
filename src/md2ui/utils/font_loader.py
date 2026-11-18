"""font_loader.py — load custom fonts from paths or URLs into a skia typeface map."""

from __future__ import annotations

from pathlib import Path

import skia  # type: ignore[import-untyped]

from md2ui.utils.fetch_policy import POLICY
from md2ui.utils.font_lock import CACHE as _CACHE_DIR

_SUPPORTED_EXT = {".ttf", ".otf"}

# Maps (family_lower, weight, is_italic) → skia.Typeface
CustomFontMap = dict[tuple[str, int, bool], skia.Typeface]

_FONT_MGR = skia.FontMgr.RefDefault()


def _download(url: str) -> Path | None:
    """Download a font URL to cache; return local path or None on failure."""
    if not POLICY.remote:
        # A server loads only the fonts its developer installed (fetch_policy).
        print(f"[fonts] remote fonts are off here, skipping {url}")
        return None
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Use last URL segment as filename
    name = url.rstrip("/").split("/")[-1].split("?")[0]
    if Path(name).suffix.lower() not in _SUPPORTED_EXT:
        print(f"[fonts] skipping unsupported format: {name}")
        return None
    dest = _CACHE_DIR / name
    if not dest.exists():
        import urllib.request  # here, as image_cache does: not on every start

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "md2ui/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                dest.write_bytes(r.read())
            print(f"[fonts] downloaded {name}")
        except Exception as e:
            print(f"[fonts] failed to download {url}: {e}")
            return None
    return dest


_WEIGHT_NAMES: dict[str, int] = {
    "thin": 100,
    "extralight": 200,
    "extra light": 200,
    "ultra light": 200,
    "light": 300,
    "regular": 400,
    "normal": 400,
    "": 400,
    "medium": 500,
    "semibold": 600,
    "semi bold": 600,
    "demibold": 600,
    "bold": 700,
    "extrabold": 800,
    "extra bold": 800,
    "ultrabold": 800,
    "black": 900,
    "heavy": 900,
}


def weight_from_str(s: str) -> int:
    """Convert a font weight string (name or number) to a numeric weight."""
    s = s.strip().lower()
    if s.isdigit():
        return int(s)
    return _WEIGHT_NAMES.get(s, 400)


def load_custom_fonts(font_paths: list[str]) -> CustomFontMap:
    """
    Load each entry in font_paths (local file or URL) with skia.Typeface.MakeFromFile().
    Returns a dict keyed by (family_name_lower, weight, is_italic).
    Weight is the numeric font weight (400 = regular, 700 = bold).
    """
    result: CustomFontMap = {}
    for entry in font_paths:
        entry = entry.strip()
        if not entry:
            continue
        if entry.startswith("http://") or entry.startswith("https://"):
            local = _download(entry)
        else:
            local = Path(entry)

        if local is None or not local.exists():
            print(f"[fonts] not found: {entry}")
            continue
        if local.suffix.lower() not in _SUPPORTED_EXT:
            print(f"[fonts] skipping unsupported format: {local.name}")
            continue

        tf = skia.Typeface.MakeFromFile(str(local))
        if tf is None:
            print(f"[fonts] failed to load: {local.name}")
            continue

        fs = tf.fontStyle()
        key = (
            tf.getFamilyName().lower(),
            fs.weight(),
            fs.slant() != skia.FontStyle.kUpright_Slant,
        )
        result[key] = tf
        print(
            f"[fonts] loaded '{tf.getFamilyName()}' w={fs.weight()} from {local.name}"
        )

    return result


def resolve_typeface(
    font_name: str,
    weight: int,
    italic: bool,
    custom: CustomFontMap,
) -> skia.Typeface:
    """
    Return the best custom typeface for (font_name, weight, italic),
    or fall back to the system's face of that family.
    Tries exact match first, then nearest weight in the same style, then the
    nearest weight in the family's other style: a family with no italic file
    keeps the requested weight, and ``styled_font`` slants it as a browser does.
    A system family lacking the weight takes the one CSS font matching would,
    so a page draws the face a browser draws; a family the system does not
    know takes the system's own default face.
    """
    name_lower = font_name.lower()
    # Exact match
    key = (name_lower, weight, italic)
    if key in custom:
        return custom[key]
    # Same family, same italic, nearest weight
    candidates = [
        (k, v) for k, v in custom.items() if k[0] == name_lower and k[2] == italic
    ]
    if candidates:
        best = min(candidates, key=lambda x: abs(x[0][1] - weight))
        return best[1]
    # Same family, other style, nearest weight
    candidates = [(k, v) for k, v in custom.items() if k[0] == name_lower]
    if candidates:
        best = min(candidates, key=lambda x: abs(x[0][1] - weight))
        return best[1]
    # System fallback
    if custom:
        loaded = sorted({k[0] for k in custom})
        print(
            f"[fonts] no match for '{font_name}' (w={weight}, italic={italic}); loaded families: {loaded}"
        )
    slant = skia.FontStyle.Italic() if italic else skia.FontStyle.Normal()
    weight = _system_weight(font_name, weight, italic)
    style = skia.FontStyle(weight, skia.FontStyle.Normal().width(), slant.slant())
    return skia.Typeface.MakeFromName(font_name, style)


# Where a code font comes from when the theme's own family is neither loaded nor
# installed: the generic name, which the platform answers with its own monospaced
# face (Courier on macOS) — the face a theme naming no code font already gets.
MONOSPACE = "monospace"


def resolve_code_typeface(
    font_name: str, weight: int, italic: bool, custom: CustomFontMap
) -> skia.Typeface:
    """``resolve_typeface`` for code: a family the theme names but neither loads
    nor finds installed falls back to a monospaced face, never the proportional
    default a code block would lose its columns in."""
    loaded = any(k[0] == font_name.lower() for k in custom)
    if loaded or _FONT_MGR.matchFamily(font_name).count():
        return resolve_typeface(font_name, weight, italic, custom)
    return resolve_typeface(MONOSPACE, weight, italic, custom)


def _system_weight(font_name: str, weight: int, italic: bool) -> int:
    """The weight of ``font_name`` CSS would draw for ``weight``, among the
    system's faces in the requested style (any style when it has none);
    ``weight`` itself when the system does not know the family."""
    styles = _FONT_MGR.matchFamily(font_name)
    faces = [styles.getStyle(i)[0] for i in range(styles.count())]
    upright = skia.FontStyle.kUpright_Slant
    same = [f.weight() for f in faces if (f.slant() != upright) == italic]
    available = same or [f.weight() for f in faces]
    return css_matched_weight(weight, available) if available else weight


def css_matched_weight(desired: int, available: list[int]) -> int:
    """The weight CSS font matching picks for ``desired`` from ``available``
    (CSS Fonts, font-weight matching)."""
    if desired in available:
        return desired
    ascending = sorted(set(available))
    lighter = [w for w in reversed(ascending) if w < desired]
    heavier = [w for w in ascending if w > desired]
    if 400 <= desired <= 500:
        order = (
            [w for w in heavier if w <= 500] + lighter + [w for w in heavier if w > 500]
        )
    elif desired < 400:
        order = lighter + heavier
    else:
        order = heavier + lighter
    return order[0]


# The slant a browser synthesises for italic text in a face with no italic.
SYNTHETIC_OBLIQUE_SKEW = -0.25


def make_font(typeface: skia.Typeface, size: float, scale_x: float = 1.0) -> skia.Font:
    """The font every text in md2ui is measured and drawn with (ADR-400).

    Slight hinting, so a glyph advances by the face's own width on every
    platform, as in a browser: at Skia's default (normal) hinting FreeType
    (Linux) rounds an upright advance to whole pixels, so the same text measured
    wider there than on macOS and wrapped differently. Slight hints only
    vertically on FreeType, and on macOS draws exactly as the default does; no
    hinting at all would also turn off CoreText's glyph smoothing and lighten
    every text there. No ``skia.Font`` is built anywhere else
    (``tests/font_hinting_tests.py``).
    """
    font = skia.Font(typeface, size, scale_x, 0.0)
    font.setHinting(skia.FontHinting.kSlight)
    return font


def styled_font(typeface: skia.Typeface, size: float, italic: bool) -> skia.Font:
    """The font that draws text in ``typeface``, italic when asked.

    Italic asked of an upright face — a family loaded without its italic
    file — is synthesised as an oblique, never dropped. A skew leaves every
    advance unchanged, so measuring with or without it agrees; it is applied
    here so that every caller that knows the text is italic gets the same font.
    """
    font = make_font(typeface, size)
    if italic and typeface.fontStyle().slant() == skia.FontStyle.kUpright_Slant:
        font.setSkewX(SYNTHETIC_OBLIQUE_SKEW)
    return font


# ``varied_face`` answers, keyed by what was asked: an ``auto`` optical size asks
# once per drawn size. Each clone is held in ``_CLONES`` under the coordinates it
# was set to, so two asks that clamp to the same place share one face. Every face
# is held here, so a face another cache keys by ``id()`` stays alive and its id is
# never reused.
_ASKED: dict[tuple, skia.Typeface | None] = {}
_CLONES: dict[tuple, skia.Typeface] = {}
# The variation axes the emoji keys set: `Emoji weight` and an icon font's
# `Emoji fill`, `Emoji grade` and `Emoji optical size`.
_WGHT, _FILL, _GRAD, _OPSZ = (
    int.from_bytes(tag, "big") for tag in (b"wght", b"FILL", b"GRAD", b"opsz")
)


def _axis_ranges(tf: skia.Typeface) -> dict[int, tuple[float, float]]:
    """``tf``'s variation axes, ``tag -> (min, max)``; empty for a static face."""
    try:
        axes = tf.getVariationDesignParameters()
    except RuntimeError:  # a static face has no parameters to get
        return {}
    return {a.tag: (a.min, a.max) for a in axes}


def varied_face(
    path: str,
    weight: int | None,
    fill: float | None = None,
    grade: float | None = None,
    opsz: float | None = None,
) -> skia.Typeface | None:
    """The face of the font at ``path`` set where the emoji keys ask.

    Each value is clamped to the font's range on its axis, and one the font has
    no axis for is left out. A weight a static font cannot set is matched
    against the sibling files of its family beside it (``Family-Light.ttf``,
    ``Family-Bold.ttf`` ...), nearest weight first, the lighter of two equally
    near. ``None`` when nothing asked changes the font, or it does not load:
    the caller keeps the face it already has.
    """
    asked = (path, weight, fill, grade, opsz)
    if asked not in _ASKED:
        _ASKED[asked] = _vary(
            Path(path), weight, {_FILL: fill, _GRAD: grade, _OPSZ: opsz}
        )
    return _ASKED[asked]


def _vary(
    path: Path, weight: int | None, axes: dict[int, float | None]
) -> skia.Typeface | None:
    base = skia.Typeface.MakeFromFile(str(path)) if path.is_file() else None
    if base is None:
        return None
    face = base
    if weight and _WGHT in _axis_ranges(base):
        axes[_WGHT] = weight
    elif weight:
        face = _nearest_weight(path, base, weight)
    ranges = _axis_ranges(face)
    coords = tuple(
        (tag, min(max(float(value), ranges[tag][0]), ranges[tag][1]))
        for tag, value in sorted(axes.items())
        if value is not None and tag in ranges
    )
    if not coords:
        return None if face is base else face
    key = (str(path), weight if face is not base else None, coords)
    if key not in _CLONES:
        # Each object named: the position points into the coordinate list, and
        # a temporary freed before ``makeClone`` reads it leaves the default.
        coordinates = skia.FontArguments.VariationPosition.Coordinates(
            [skia.FontArguments.VariationPosition.Coordinate(t, v) for t, v in coords]
        )
        position = skia.FontArguments.VariationPosition(coordinates)
        args = skia.FontArguments()
        args.setVariationDesignPosition(position)
        _CLONES[key] = face.makeClone(args)
    return _CLONES[key]


def _nearest_weight(path: Path, base: skia.Typeface, weight: int) -> skia.Typeface:
    """The static face of ``base``'s family, beside it, nearest ``weight``."""
    family = base.getFamilyName()
    faces = [base]
    for sibling in sorted(path.parent.glob(f"{path.stem.rsplit('-', 1)[0]}-*")):
        if (
            sibling == path
            or sibling.suffix.lower() not in _SUPPORTED_EXT
            or "italic" in sibling.stem.lower()
        ):
            continue
        tf = skia.Typeface.MakeFromFile(str(sibling))
        if (
            tf is not None
            and tf.getFamilyName() == family
            and _WGHT not in _axis_ranges(tf)
        ):
            faces.append(tf)
    return min(
        faces,
        key=lambda f: (abs(f.fontStyle().weight() - weight), f.fontStyle().weight()),
    )
