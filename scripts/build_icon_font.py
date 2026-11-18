"""Build md2ui's icon font: every emoji drawn as the Material Symbols icon a table names.

Reads ``assets/icons/material-design-icons-md2ui.md`` (its Codepoints and Icon columns) and
writes ``assets/icons/material-design-icons-md2ui.ttf``, a subset of Material Symbols
Outlined whose icons answer to emoji codepoints and sit on md2ui's emoji box. A theme uses
it by naming it as its emoji ``Font:``. The rules the table does not spell out (flags, skin
tones, invisible components, unlisted emoji) are in the table's own header.

The source font is not committed: the script checks it against a pinned hash and, when it
is missing or different, says where to download it. Building twice writes the same bytes.

    uv run python scripts/build_icon_font.py
"""

# fontTools fills a table's fields in as it reads them, so they are invisible to the
# type checker; every attribute this script sets on a table is one of those.
# pyright: reportAttributeAccessIssue=false

import hashlib
import sys
from pathlib import Path

from fontTools import subset
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent, GlyphCoordinates
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.varLib import builder as var_builder
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "assets" / "icons"
TABLE = ICONS / "material-design-icons-md2ui.md"
OUT = ICONS / "material-design-icons-md2ui.ttf"
EMOJI_TEST = ICONS / "source" / "emoji-test.txt"
SOURCE = ICONS / "source" / "MaterialSymbolsOutlined[FILL,GRAD,opsz,wght].ttf"
CODEPOINTS = SOURCE.with_suffix(".codepoints")
# google/material-design-icons, pinned to the commit in SOURCE_URL.
SOURCE_SHA256 = "77ff1c20896afc6f1abf7d57fc408234dfd021ab050b63e0442e71d6c9f0d6b8"
SOURCE_URL = (
    "https://raw.githubusercontent.com/google/material-design-icons/"
    "49d4db35df873165d6bd6ba09b063c7dafbac2f4/variablefont/"
    "MaterialSymbolsOutlined%5BFILL,GRAD,opsz,wght%5D.ttf"
)

FAMILY = "Material Design Icons md2ui"
POSTSCRIPT = "MaterialDesignIconsmd2ui"

# md2ui's emoji box: the canvas of OpenMoji, the emoji font md2ui was laid out with. At
# 1024 units per em it is a 1320-unit square from the descent (-275) to the ascent (1045),
# and every icon fills it, so a theme can swap fonts without moving any layout.
BOX_UPEM = 1024
BOX_SIZE = 1320
BOX_DESCENT = -275
BOX_ASCENT = BOX_SIZE + BOX_DESCENT

FLAG = "flag"
SQUARE = "square"
PINS = {"filled": 1, "outlined": 0}  # an icon's suffix -> the FILL it is pinned to
MIRRORED = "mirrored"  # a suffix that draws the icon flipped left to right
VS16 = 0xFE0F
# Components that only shape a sequence: the joiner, VS16, the keycap mark, tag characters.
INVISIBLE = (0x200D, VS16, 0x20E3, *range(0xE0020, 0xE0080))
TONES = range(0x1F3FB, 0x1F400)
REGIONAL_INDICATORS = range(0x1F1E6, 0x1F200)
CANCEL_TAG = 0xE007F
BLACK_FLAG = 0x1F3F4

Seq = tuple[int, ...]


def check_source() -> None:
    """Stop with the download address unless the pinned source font is in place."""
    found = SOURCE.is_file() and (
        hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA256
    )
    if not found:
        sys.exit(
            f"{SOURCE.relative_to(ROOT)} is missing or is not the pinned file "
            f"(sha256 {SOURCE_SHA256}). Download it to that path from:\n  {SOURCE_URL}"
        )


def read_table(path: Path) -> dict[Seq, str]:
    """``{codepoints: icon}`` from the table's rows, in any order."""
    rows: dict[Seq, str] = {}
    seen: dict[Seq, int] = {}  # the same character, with or without VS16
    columns: list[str] | None = None
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if columns is None:
            columns = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        row = dict(zip(columns, cells))
        try:
            seq = tuple(int(cp, 16) for cp in row["Codepoints"].split())
        except ValueError:
            sys.exit(f"{path.name}:{number}: Codepoints must be hex: {line}")
        if not seq:
            sys.exit(f"{path.name}:{number}: a row needs its Codepoints: {line}")
        key = strip_vs16(seq)
        if key in seen:
            sys.exit(f"{path.name}:{number}: the same character as line {seen[key]}")
        seen[key] = number
        rows[seq] = row["Icon"]
    return rows


def read_emoji_test(path: Path) -> list[tuple[Seq, str]]:
    """``[(codepoints, status), ...]`` from Unicode's ``emoji-test.txt``."""
    out = []
    for line in path.read_text().splitlines():
        data = line.split("#", 1)[0]
        if ";" in data:
            cps, status = data.split(";")
            out.append((tuple(int(cp, 16) for cp in cps.split()), status.strip()))
    return out


def strip_vs16(seq: Seq) -> Seq:
    return tuple(cp for cp in seq if cp != VS16)


def plan(table: dict[Seq, str], emoji: list[tuple[Seq, str]]):
    """Which icon each character draws (``singles``) and each sequence ligates to
    (``ligatures``): the table's rows, then the rules the table header lists."""
    singles: dict[int, str] = {}
    ligatures: dict[Seq, str] = {}
    by_character = {strip_vs16(seq): icon for seq, icon in table.items()}
    for seq, icon in table.items():
        if len(strip_vs16(seq)) == 1:
            singles[strip_vs16(seq)[0]] = icon
        if len(seq) > 1:
            ligatures[seq] = icon
    for cp in REGIONAL_INDICATORS:
        singles.setdefault(cp, FLAG)
    for cp in TONES:
        singles.setdefault(cp, SQUARE)
    rgi = [seq for seq, status in emoji if status == "fully-qualified"]
    unlisted = list(
        dict.fromkeys(
            char[0]
            for seq, status in emoji
            if status in ("fully-qualified", "component")
            and len(char := strip_vs16(seq)) == 1
            and char[0] not in singles
        )
    )
    for cp in unlisted:
        singles[cp] = SQUARE
    for seq in rgi:
        is_flag = (len(seq) == 2 and all(cp in REGIONAL_INDICATORS for cp in seq)) or (
            seq[0] == BLACK_FLAG and seq[-1] == CANCEL_TAG
        )
        if is_flag:
            ligatures.setdefault(seq, FLAG)
    for seq in rgi:
        if len(seq) > 1 and any(cp in TONES for cp in seq):
            base = strip_vs16(tuple(cp for cp in seq if cp not in TONES))
            icon = singles.get(base[0]) if len(base) == 1 else by_character.get(base)
            if icon is not None:
                ligatures.setdefault(seq, icon)
    # The safety net for sequences, as ``unlisted`` is for characters: a sequence
    # nothing above covers draws as its first character, never as its parts.
    unjoined = [
        seq
        for seq in rgi
        if len(strip_vs16(seq)) > 1
        and seq not in ligatures
        and strip_vs16(seq) not in by_character
    ]
    for seq in unjoined:
        ligatures[seq] = singles.get(seq[0], SQUARE)
    for seq, icon in list(ligatures.items()):
        if len(strip_vs16(seq)) > 1:
            ligatures.setdefault(strip_vs16(seq), icon)
    # A character only a sequence uses (a keycap's digit) still needs a glyph to ligate.
    parts = {cp for seq in ligatures for cp in seq} - set(INVISIBLE) - set(singles)
    for cp in parts:
        singles[cp] = SQUARE
    print(f"{len(unlisted)} emoji the table does not list draw as {SQUARE}")
    print(
        f"{len(unjoined)} sequences the table does not list draw as their first emoji"
    )
    return singles, ligatures


def source_glyphs(font: TTFont, icons: set[str]) -> dict[str, str]:
    """``{icon name: source glyph name}``, stopping on a name Material does not have."""
    names = dict(line.split() for line in CODEPOINTS.read_text().splitlines())
    cmap = font.getBestCmap() or {}
    missing = sorted(icon for icon in icons if icon not in names)
    if missing:
        sys.exit(f"Not Material Symbols names: {', '.join(missing)}")
    return {icon: cmap[int(names[icon], 16)] for icon in sorted(icons)}


def subset_to(font: TTFont, glyphs: list[str]) -> None:
    """Keep ``glyphs`` with every axis, and no layout features. Material's name
    ligatures go, and so does its swap to a ``.fill`` glyph at FILL 1: a bare icon
    draws its own outline at every FILL, and only ``pinned_glyphs`` takes ``.fill``."""
    options = subset.Options()
    options.layout_features = []
    options.name_IDs = ["*"]
    options.notdef_outline = True
    options.glyph_names = True
    subsetter = subset.Subsetter(options)
    subsetter.populate(glyphs=glyphs)
    subsetter.subset(font)


def pinned_glyphs(glyph_of: dict[str, str], pins: set[tuple[str, str]]):
    """``{(icon, pin): (glyph, advance, variations)}``: each icon with its FILL pinned
    and the other axes still variable. Material draws a filled icon as its own
    ``.fill`` glyph, which its GSUB swaps in at FILL 1; a pin takes that glyph."""
    out = {}
    for pin, fill in PINS.items():
        icons = sorted(icon for icon, p in pins if p == pin)
        if not icons:
            continue
        font = TTFont(SOURCE, recalcTimestamp=False)
        order = set(font.getGlyphOrder())
        drawn = {
            icon: glyph_of[icon] + ".fill"
            if fill and glyph_of[icon] + ".fill" in order
            else glyph_of[icon]
            for icon in icons
        }
        subset_to(font, sorted(set(drawn.values())))
        instancer.instantiateVariableFont(font, {"FILL": fill}, inplace=True)
        for icon, name in drawn.items():
            glyph = font["glyf"][name]
            if glyph.isComposite():
                sys.exit(f"{name}: a composite glyph cannot be pinned on its own")
            out[icon, pin] = (glyph, font["hmtx"][name], font["gvar"].variations[name])
    return out


def add_glyphs(font: TTFont, glyphs: dict[str, tuple]) -> None:
    """Append ``{name: (glyph, (advance, lsb), variations)}`` to ``font``."""
    font.setGlyphOrder(font.getGlyphOrder() + list(glyphs))
    for name, (glyph, metrics, variations) in glyphs.items():
        font["glyf"][name] = glyph
        font["hmtx"][name] = metrics
        font["gvar"].variations[name] = variations


def alias(target: str) -> Glyph:
    """A glyph that draws ``target``: a character a sequence holds needs its own glyph,
    or two characters drawing one icon would be one sequence to the ligatures."""
    component = GlyphComponent()
    component.glyphName, component.x, component.y, component.flags = target, 0, 0, 0
    glyph = Glyph()
    glyph.numberOfContours, glyph.components = -1, [component]
    return glyph


def mirrored(source: tuple) -> tuple:
    """``(glyph, metrics, variations)``, as ``source`` holds them, facing the other way: its
    own outline, each point flipped inside the same advance once, here, and every
    axis's deltas with it. Material has no reverse of ``play_arrow``, and ``◀️`` is
    one; an icon Material draws facing the right way is never flipped.

    Each contour's points run in reverse after the flip, so its direction, and the
    fill the direction decides, stays what it was; a delta follows its point."""
    glyph, metrics, variations = source
    if glyph.isComposite():
        sys.exit("a composite glyph cannot be mirrored")
    advance = metrics[0]
    order: list[int] = []
    start = 0
    for end in glyph.endPtsOfContours:
        # The contour keeps its start point and runs the rest backwards.
        order += [start, *range(end, start, -1)]
        start = end + 1
    out = Glyph()
    out.numberOfContours = glyph.numberOfContours
    out.endPtsOfContours = list(glyph.endPtsOfContours)
    out.coordinates = GlyphCoordinates(
        [(advance - glyph.coordinates[k][0], glyph.coordinates[k][1]) for k in order]
    )
    out.flags = bytearray(glyph.flags[k] for k in order)
    out.program = glyph.program
    flipped = []
    for variation in variations:
        deltas = variation.coordinates
        points = [None if (d := deltas[k]) is None else (-d[0], d[1]) for k in order]
        phantoms = deltas[len(order) :]  # the advance's own, which never varies
        flipped.append(TupleVariation(dict(variation.axes), points + phantoms))
    lsb = min((advance - x for x, _y in glyph.coordinates), default=0)
    return out, (advance, lsb), flipped


def parse_spec(spec: str) -> tuple[str, str | None, bool]:
    """``(icon, pin, mirrored)`` from a table's Icon cell, ``play_arrow:filled:mirrored``."""
    icon, *suffixes = spec.split(":")
    mirrored = MIRRORED in suffixes
    rest = [s for s in suffixes if s != MIRRORED]
    if len(rest) > 1 or (rest and rest[0] not in PINS) or suffixes.count(MIRRORED) > 1:
        sys.exit(f"{spec}: a suffix is :{' or :'.join(PINS)}, then :{MIRRORED}")
    return icon, (rest[0] if rest else None), mirrored


def constant_hvar(font: TTFont) -> None:
    """An HVAR saying no advance varies. Material's never does (every icon is 960 wide
    at every axis position), and the rebuilt map covers the glyphs added here."""
    store = font["HVAR"].table.VarStore
    assert all(not any(row) for data in store.VarData for row in data.Item)
    axes = [axis.axisTag for axis in font["fvar"].axes]
    hvar = ot.HVAR()
    hvar.Version = 0x00010000
    hvar.VarStore = var_builder.buildVarStore(
        var_builder.buildVarRegionList([], axes),
        [var_builder.buildVarData([], [[]], optimize=False)],
    )
    hvar.AdvWidthMap = var_builder.buildVarIdxMap(
        [0] * len(font.getGlyphOrder()), font.getGlyphOrder()
    )
    hvar.LsbMap = hvar.RsbMap = None
    font["HVAR"].table = hvar


def set_cmap(font: TTFont, glyph_of_cp: dict[int, str]) -> None:
    """Format 4 for the BMP and format 12 for everything: format 4 alone cannot reach
    an emoji above U+FFFF, which is most of them."""
    bmp = CmapSubtable.newSubtable(4)
    bmp.platformID, bmp.platEncID, bmp.language = 3, 1, 0
    bmp.cmap = {cp: g for cp, g in glyph_of_cp.items() if cp <= 0xFFFF}
    full = CmapSubtable.newSubtable(12)
    full.platformID, full.platEncID, full.language = 3, 10, 0
    full.cmap = dict(glyph_of_cp)
    font["cmap"].tables = [bmp, full]


# A backslash before a glyph name lets feature syntax take any name, ``10k`` included.
ESCAPE = "\\"


def set_ligatures(font: TTFont, ligatures: dict[tuple[str, ...], str]) -> None:
    """The sequences, in ``ccmp``: shapers apply it by default and browsers cannot turn
    it off."""
    rules = "".join(
        f"  sub {' '.join(ESCAPE + g for g in parts)} by {ESCAPE}{target};\n"
        for parts, target in sorted(ligatures.items())
    )
    if "GSUB" in font:
        del font["GSUB"]
    fea = f"languagesystem DFLT dflt;\nfeature ccmp {{\n{rules}}} ccmp;\n"
    addOpenTypeFeaturesFromString(font, fea, tables=["GSUB"])


def place_on_box(font: TTFont) -> None:
    """Material's 1-em icon square becomes md2ui's emoji box. ``scale_upem`` scales the
    outlines, their deltas and the advances together, so every axis keeps its shape."""
    scale_upem(font, BOX_SIZE)
    font["head"].unitsPerEm = BOX_UPEM
    glyf = font["glyf"]
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        if glyph.numberOfContours > 0:  # a composite moves with its component
            glyph.coordinates.translate((0, BOX_DESCENT))
            glyph.recalcBounds(glyf)
    font["hhea"].ascent = font["OS/2"].sTypoAscender = BOX_ASCENT
    font["hhea"].descent = font["OS/2"].sTypoDescender = BOX_DESCENT
    font["OS/2"].usWinAscent, font["OS/2"].usWinDescent = BOX_ASCENT, -BOX_DESCENT
    font["hhea"].lineGap = font["OS/2"].sTypoLineGap = 0


def rename(font: TTFont) -> None:
    """Its own family, so it is never taken for Google's; the copyright stays."""
    name = font["name"]
    for record in name.names:
        if record.nameID in (1, 3, 4, 6, 16, 21):
            record.string = (
                record.toUnicode()
                .replace("Material Symbols Outlined", FAMILY)
                .replace("MaterialSymbolsOutlined", POSTSCRIPT)
            )
    name.setName(
        "Modified from Material Symbols Outlined by md2ui's build_icon_font.py: "
        "subset, rescaled and remapped to emoji codepoints. Apache License 2.0.",
        10,
        3,
        1,
        0x409,
    )


def build() -> TTFont:
    """The font the table describes, in memory."""
    singles, ligatures = plan(read_table(TABLE), read_emoji_test(EMOJI_TEST))
    font = TTFont(SOURCE, recalcTimestamp=False)
    specs = set(singles.values()) | set(ligatures.values())
    parsed = {spec: parse_spec(spec) for spec in specs}
    glyph_of = source_glyphs(font, {icon for icon, _pin, _m in parsed.values()})
    pins = {(icon, pin) for icon, pin, _m in parsed.values() if pin}
    pinned = pinned_glyphs(glyph_of, pins)
    bare = sorted({glyph_of[icon] for icon, pin, _m in parsed.values() if not pin})
    subset_to(font, bare)

    unmirrored = {
        spec: f"{glyph_of[icon]}.{pin}" if pin else glyph_of[icon]
        for spec, (icon, pin, _m) in parsed.items()
    }
    glyph_of_spec = {
        spec: unmirrored[spec] + (f".{MIRRORED}" if parsed[spec][2] else "")
        for spec in specs
    }
    in_sequences = {cp for seq in ligatures for cp in seq}
    new: dict[str, tuple] = {}
    for (icon, pin), drawn in sorted(pinned.items()):
        new[f"{glyph_of[icon]}.{pin}"] = drawn
    for spec in sorted(s for s in specs if parsed[s][2]):
        target = unmirrored[spec]
        if target in new:
            source = new[target]
        else:
            glyph = font["glyf"][target]
            source = (glyph, font["hmtx"][target], font["gvar"].variations[target])
        new[glyph_of_spec[spec]] = mirrored(source)
    glyph_of_cp = {}
    for cp in sorted(singles):
        target = glyph_of_spec[singles[cp]]
        if cp in in_sequences:
            advance = new[target][1] if target in new else font["hmtx"][target]
            new[f"u{cp:04X}"] = (alias(target), advance, [])
            target = f"u{cp:04X}"
        glyph_of_cp[cp] = target
    for cp in INVISIBLE:
        new[f"u{cp:04X}"] = (Glyph(), (0, 0), [])
        glyph_of_cp[cp] = f"u{cp:04X}"
    add_glyphs(font, new)
    constant_hvar(font)

    set_cmap(font, glyph_of_cp)
    set_ligatures(
        font,
        {
            tuple(glyph_of_cp[cp] for cp in seq): glyph_of_spec[icon]
            for seq, icon in ligatures.items()
        },
    )
    place_on_box(font)
    rename(font)
    print(
        f"{len(font.getGlyphOrder())} glyphs, {len(glyph_of_cp)} characters, "
        f"{len(ligatures)} sequences"
    )
    return font


def main() -> None:
    check_source()
    font = build()
    font.save(OUT)
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
