"""The contract against the theme it is declared for (ADR-501).

``MEANINGS.md`` says what each spelling means; ``THEME.md`` draws it. Where the
two disagree the author of the theme has a gap, and an agent following the
contract cannot see it: its answer is correct and only looks wrong. This module
says so once, when the theme loads, never per answer:

* two declared spellings of one section that draw the same;
* a row's size that the drawn sizes contradict;
* a colour, a size or a measurement in a row's meaning or a theme pattern's
  description: the agent reads those, and the design is the theme's to draw;
* a row's slot outside ``meanings.SLOTS``, and buttons with no row for the main
  action inside a card or at a row's edge: the core note and the advice find
  rows by slot, so a missing one drops a row with no other sign;
* a ``## Fixed colors`` pin that no ``## Fixed colours`` row declares;
* a theme pattern whose example fails ``check``: it is not served;
* a font family a block names that the ``## Fonts`` list never loads;
* a shadow layer past ``SHADOW_MAX_PER_KIND`` of its kind in one block, which the
  parser drops without a word.

Which theme patterns are served decides what ``check`` holds an answer to: the
contract, with every spelling a served pattern declares (``answer_contract``).

What a spelling draws is read from the real pipeline, each declared spelling
rendered alone as a one-line document, so the lint sees what a user sees.

A shell module beside ``meanings`` and ``check``; the pipeline never imports it.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import io
import re
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from md2ui import check_placeholders, meanings, session
from md2ui.check import check_markdown
from md2ui.meanings import Contract, Row
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_render import load_background_images
from md2ui.pipeline.render_text import bare_glyph
from md2ui.pipeline.theme import SHADOW_MAX_PER_KIND, Theme
from md2ui.utils.font_loader import (
    load_custom_fonts,
    resolve_code_typeface,
    resolve_typeface,
)
from md2ui.utils.image_cache import ImageCache

# Every spelling is laid out at one width, so two renders differ only by what
# the theme draws. The preview's default width.
WIDTH = 767

# A row's size, smallest first; ``extra small`` is tried before ``small``. A
# row with none is not compared.
_SIZES = (
    (re.compile(r"\bextra[- ]small\b"), 0),
    (re.compile(r"\bsmall\b"), 1),
    (re.compile(r"\b(?:medium|standard)\b"), 2),
    (re.compile(r"\blarge\b"), 3),
)

# Where each element's look is written in THEME.md.
_THEME_SECTION = {
    "icon": "## Emoji styles",
    "chip": "## Inline Code",
    "button": "## Links",
    "icon button": "## Links",
}

# The button slots the core note and the advice cannot do without, and the
# place each names.
_NEEDED_BUTTON_SLOTS = {
    "card-main": "the main action inside a card",
    "row-main": "the main action at the edge of a row",
}

# What the theme draws, named where an agent would read it as a meaning.
_DESIGN_WORDS = re.compile(
    r"\b(?:red|green|blue|amber|yellow|orange|purple|pink|grey|gray|black|white"
    r"|extra[- ]small|small|medium|large|standard size|bold|rounded|shadow"
    r"|\d+(?:\.\d+)?\s?(?:px|pt|em|rem)|#[0-9a-f]{3,8})\b",
    re.IGNORECASE,
)

_CODE_SPANS = re.compile(r"(`+)\s?(.+?)\s?\1")
_FENCE = re.compile(r"^```(?:markdown|md)[ \t]*\n(.*?)^```", re.DOTALL | re.MULTILINE)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_FONT_NAME = re.compile(r"^(?:[-*]\s+)?font name\s*:\s*(.+?)\s*$", re.IGNORECASE)
_HEADING = re.compile(r"^(#{2,4})\s+(.+?)\s*$")


@dataclass(frozen=True)
class Lint:
    messages: tuple[str, ...]  # one line each, in the order found
    broken_patterns: frozenset[str]  # names of the patterns not served


_CACHE: dict[str, Lint] = {}


def _key(theme_path: Path) -> str:
    """The content of everything the lint reads: the theme, both contracts and
    the patterns, md2ui's and the theme's. A reload of the same files reuses the
    answer."""
    digest = hashlib.sha256()
    own = theme_path.resolve().parent / meanings.FILE_NAME
    patterns = [
        *meanings.skills_patterns(),
        *meanings.theme_patterns(theme_path).values(),
    ]
    for path in (theme_path, meanings.BASE, own, *patterns):
        digest.update(str(path).encode())
        digest.update(path.read_bytes() if path.is_file() else b"-")
    return digest.hexdigest()


def lint(theme_path: Path | None) -> Lint:
    """The theme at *theme_path* against its merged contract and its patterns.
    The pipeline's progress prints go to stderr: stdout may be a protocol."""
    if theme_path is None:
        return Lint((), frozenset())
    key = _key(theme_path)
    if key not in _CACHE:
        with contextlib.redirect_stdout(sys.stderr):
            _CACHE[key] = _lint(theme_path)
    return _CACHE[key]


def _lint(theme_path: Path) -> Lint:
    contract = meanings.load_contract(theme_path)
    kit = session.load_grouping_kit()
    messages: list[str] = _unloaded_families(theme_path)
    messages += check_placeholders.lint(session.load_theme(theme_path), contract)
    messages += check_placeholders.unknown_blocks(
        theme_path.read_text(encoding="utf-8")
    )
    messages += dropped_shadows(theme_path.read_text(encoding="utf-8"))
    if contract is not None:
        theme = session.load_theme(theme_path)
        drawn = _Drawn(theme, kit)
        for section in contract.sections:
            if section.heading.lower() in meanings.ELEMENT_SECTIONS:
                rows = [r for r in section.rows if meanings._code_span(r.write)]
                messages += _drawn_the_same(rows, drawn)
                messages += _sizes_out_of_order(rows, drawn)
        messages += _undeclared_pins(theme, contract)
        messages += _design_in_meanings(contract)
        messages += _unknown_slots(contract)
        messages += _missing_button_slots(contract)
    broken: set[str] = set()
    patterns = meanings.theme_patterns(theme_path)
    messages += _design_in_descriptions(patterns)
    # Each example is checked as an answer is, with what the patterns declare;
    # whether one is served turns on its errors, which declarations never raise.
    if contract is not None:
        every = [*meanings.skills_patterns(), *patterns.values()]
        contract = meanings.with_patterns(contract, every)
    for name, path in patterns.items():
        for block in _FENCE.findall(path.read_text(encoding="utf-8")):
            for issue in check_markdown(block, kit, contract):
                if issue["level"] == "error":
                    broken.add(name)
                    messages.append(
                        f"Pattern `{name}` is not served: its example fails "
                        f"`check`: {issue['message']}"
                    )
                elif issue["level"] == "warning":
                    messages.append(f"Pattern `{name}`: {issue['message']}")
    return Lint(tuple(messages), frozenset(broken))


def served_patterns(theme_path: Path | None) -> dict[str, Path]:
    """The theme's patterns an agent is offered: those whose examples pass."""
    broken = lint(theme_path).broken_patterns
    patterns = meanings.theme_patterns(theme_path).items()
    return {name: path for name, path in patterns if name not in broken}


def answer_contract(theme_path: Path | None) -> Contract | None:
    """What ``check`` holds an answer to: the theme's contract, with every
    spelling a served pattern declares (ADR-501)."""
    contract = meanings.load_contract(theme_path)
    if contract is None:
        return None
    own = served_patterns(theme_path) if meanings.theme_patterns(theme_path) else {}
    return meanings.with_patterns(
        contract, [*meanings.skills_patterns(), *own.values()]
    )


def log(theme_path: Path | None) -> None:
    """The lint in a host's log: stderr, one line each, never stdout."""
    for message in lint(theme_path).messages:
        print(f"[theme] {message}", file=sys.stderr, flush=True)


def _local_images(obj: Any) -> Any:
    """*obj* with every remote ``bg_image`` left out, at any depth of the theme;
    the parts holding none are the same objects."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        changes = {}
        for field in dataclasses.fields(obj):
            if not field.init:
                continue
            value = getattr(obj, field.name)
            if field.name == "bg_image" and str(value).startswith(_REMOTE):
                changes[field.name] = None
            elif (local := _local_images(value)) is not value:
                changes[field.name] = local
        return dataclasses.replace(obj, **changes) if changes else obj
    if isinstance(obj, dict):
        local = {k: _local_images(v) for k, v in obj.items()}
        return local if any(local[k] is not obj[k] for k in obj) else obj
    if isinstance(obj, list):
        local = [_local_images(v) for v in obj]
        return local if any(a is not b for a, b in zip(local, obj)) else obj
    return obj


_REMOTE = ("http://", "https://")


class _Drawn:
    """Each spelling rendered alone with the theme: ``(pixels hash, height)``.
    The height is the one-line document's laid-out height (the scene's,
    without the root padding): for a lone element, the element's own box."""

    def __init__(self, theme: Theme, kit: session.GroupingKit) -> None:
        self.theme, self.kit = theme, kit
        self.fonts = session.load_fonts(theme)
        # Never a download: the lint runs before a server answers its client,
        # and a background that does not answer would hold the connection. A
        # remote image draws as one never fetched.
        self.backgrounds = load_background_images(_local_images(theme))
        self._memo: dict[str, tuple[str, float]] = {}

    def __call__(self, spelling: str) -> tuple[str, float]:
        if spelling not in self._memo:
            ast = session.group_markdown(spelling + "\n", self.kit)
            if ast is None:
                self._memo[spelling] = ("", 0.0)
                return self._memo[spelling]
            root, index = session.prepare(ast, self.theme)
            scene = session.build_scene(
                LayoutGenerator(), root, index, self.theme, self.fonts, WIDTH
            )
            image = session.render_image(
                scene, index, self.theme, self.fonts, ImageCache(), self.backgrounds, 1
            )
            pixels = hashlib.sha256(image.tobytes()).hexdigest()
            self._memo[spelling] = (pixels, scene.height)
        return self._memo[spelling]


def _spelling(row: Row) -> str:
    return meanings._code_span(row.write) or ""


def _block(row: Row) -> str | None:
    """Where *row*'s look is written in THEME.md, e.g. ``## Links → ### Quinary``."""
    if row.selects is None or row.selects.variant == "quoted":
        return None
    section = _THEME_SECTION[row.selects.element]
    variant = row.selects.variant
    return section if variant == "primary" else f"{section} → ### {variant.title()}"


def _drawn_the_same(rows: list[Row], drawn: _Drawn) -> list[str]:
    found = []
    for first, second in combinations(rows, 2):
        if drawn(_spelling(first))[0] != drawn(_spelling(second))[0]:
            continue
        block = _block(second) or _block(first)
        fix = f"give `{block}` its own look" if block else "give one its own look"
        found.append(
            f"{second.write} and {first.write} draw the same with this theme: "
            f"{fix}, or remove {second.write} from MEANINGS.md."
        )
    return found


def _size(row: Row) -> int | None:
    size = row.size.lower()
    return next((rank for word, rank in _SIZES if word.search(size)), None)


def _size_word(row: Row) -> str:
    size = row.size.lower()
    return next(m.group(0) for word, _rank in _SIZES if (m := word.search(size)))


def _sizes_out_of_order(rows: list[Row], drawn: _Drawn) -> list[str]:
    sized = [(row, size) for row in rows if (size := _size(row)) is not None]
    found = []
    for (a, size_a), (b, size_b) in combinations(sized, 2):
        if size_a == size_b:
            continue
        small, large = (a, b) if size_a < size_b else (b, a)
        small_h, large_h = drawn(_spelling(small))[1], drawn(_spelling(large))[1]
        if small_h <= large_h:
            continue
        block = _block(small) or "its look"
        found.append(
            f"{small.write} is sized {_size_word(small)} but draws taller than "
            f"{large.write}, sized {_size_word(large)} "
            f"({small_h:.0f}px against {large_h:.0f}px): make `{block}` smaller, "
            f"or change its row in MEANINGS.md."
        )
    return found


def _design_in_meanings(contract: Contract) -> list[str]:
    return [
        f"{row.write} under `## {section.heading}` means `{row.means}`, which names "
        f"`{found.group(0)}`: say what it is for and where it goes; a size belongs "
        f"in the row's third column, and a colour in THEME.md."
        for section in contract.sections
        for row in section.rows
        if (found := _DESIGN_WORDS.search(row.means))
    ]


def _unknown_slots(contract: Contract) -> list[str]:
    known = ", ".join(f"`{slot}`" for slot in meanings.SLOTS)
    return [
        f"{row.write} under `## {section.heading}` names the slot `{slot}`, which "
        f"md2ui does not read: write one of {known}, or leave the cell empty."
        for section in contract.sections
        for row in section.rows
        for slot in row.slots
        if slot not in meanings.SLOTS
    ]


def _missing_button_slots(contract: Contract) -> list[str]:
    rows = [
        row
        for section in contract.sections
        if section.heading.lower() == "buttons"
        for row in section.rows
    ]
    return [
        f"`## Buttons` in MEANINGS.md has no row with the slot `{slot}`, "
        f"{place}: the core note never names its spelling. Add `{slot}` to that "
        f"row's *Slot* cell."
        for slot, place in _NEEDED_BUTTON_SLOTS.items()
        if rows and not any(slot in row.slots for row in rows)
    ]


def _design_in_descriptions(patterns: dict[str, Path]) -> list[str]:
    return [
        f"Pattern `{name}`'s description names `{found.group(0)}`: say what the "
        f"pattern is for, in the domain's words; its look is the theme's."
        for name, path in patterns.items()
        if (found := _DESIGN_WORDS.search(meanings.pattern_description(path)))
    ]


def _declared_tokens(contract: Contract) -> set[str]:
    """Every code span in the first cell of a ``## Fixed colours`` row: a row
    may name several tokens (`` `❌` `🛑` ``) and words around them (`` `⬆` in a
    chip ``, ``a button labelled `OK` ``). Read without variation selectors,
    as pins match."""
    tokens: set[str] = set()
    for section in contract.sections:
        if section.heading.lower() in ("fixed colours", "fixed colors"):
            for row in section.rows:
                tokens |= {bare_glyph(t) for _f, t in _CODE_SPANS.findall(row.write)}
    return tokens


def _undeclared_pins(theme: Theme, contract: Contract) -> list[str]:
    declared = _declared_tokens(contract)
    fixed = theme.fixed
    blocks = (
        ("### Emoji", fixed.emoji),
        ("### Emoji background", fixed.emoji_bg),
        ("### Badges", {**fixed.pill_exact, **fixed.pill_contains}),
        ("### Buttons", {**fixed.button_exact, **fixed.button_contains}),
        ("### Datapoints", fixed.datapoints),
    )
    return [
        f"The `{token}` pin under `## Fixed colors → {block}` has no row under "
        f"`## Fixed colours` in MEANINGS.md: add one saying what it means, or "
        f"remove the pin."
        for block, pins in blocks
        for token in pins
        if bare_glyph(token) not in declared
    ]


# The block a code font is named in, as `_font_name_lines` labels it.
_CODE_BLOCK = "Text Styles → Code Block"


_SHADOW_KEY = re.compile(r"(outer|inner)?\s*shadows?\s*:", re.IGNORECASE)


def dropped_shadows(text: str) -> list[str]:
    """Each block that declares more shadow layers of one kind than are painted.

    A block is a ``###`` or ``####`` heading, or a ``##`` section's own keys before
    its first ``###`` (``## Charts``). The parser keeps the first
    ``SHADOW_MAX_PER_KIND`` of each kind and drops the rest, bullets and all."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)  # as parse_theme does
    found: list[str] = []
    counts: dict[str, int] = {}
    block = ""

    def close() -> None:
        for kind, n in counts.items():
            if n > SHADOW_MAX_PER_KIND:
                found.append(
                    f"`{block}` declares {n} {kind} shadows; the first "
                    f"{SHADOW_MAX_PER_KIND} are painted and the rest are dropped."
                )
        counts.clear()

    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            close()
            level, _, title = line.partition(" ")
            if level == "##":
                section = title.strip()
                block = f"## {section}"
            elif level in ("###", "####"):
                block = f"## {section} > {level} {title.strip()}"
            continue
        if raw.startswith(("-", " ")) or not (match := _SHADOW_KEY.fullmatch(line)):
            continue
        kind = "inner" if (match.group(1) or "").lower() == "inner" else "outer"
        counts[kind] = counts.get(kind, 0) + 1
    close()
    return found


def _unloaded_families(theme_path: Path) -> list[str]:
    """A family a block names that no ``## Fonts`` file declares: the text falls
    back to whatever the platform answers for the name. The files are loaded
    and their own family names compared, as the renderer resolves them."""
    theme = session.parsed_theme(theme_path)
    read = {name.casefold() for name in _font_names(theme)}
    asked: dict[str, list[str]] = {}
    for name, block in _font_name_lines(theme_path.read_text(encoding="utf-8")):
        if name.casefold() in read and block not in asked.setdefault(name, []):
            asked[name].append(block)
    if not asked:
        return []
    with contextlib.redirect_stdout(io.StringIO()):  # the render prints its own
        custom = load_custom_fonts(theme.font_paths)
        loaded = {family for family, _w, _i in custom}
        missing = [n for n in asked if n.casefold() not in loaded]
        fallback = {n: resolve_typeface(n, 400, False, custom) for n in missing}
        code = {n: resolve_code_typeface(n, 400, False, custom) for n in missing}
    found = []
    for name in missing:
        blocks = ", ".join(asked[name])
        # A code block falls back to a monospaced face, every other block to the
        # platform's answer for the name (font_loader.resolve_code_typeface).
        in_code = [b == _CODE_BLOCK for b in asked[name]]
        face = (code if all(in_code) else fallback)[name].getFamilyName()
        code_face = code[name].getFamilyName()
        if any(in_code) and not all(in_code) and code_face != face:
            face = f"{face}` (code blocks in `{code_face}`)"
        else:
            face += "`"
        fix = (
            f"it renders only where `{name}` is installed, as it is here; add its "
            f"files to draw it everywhere."
            if face.casefold() == name.casefold() + "`"
            else f"add its files, or that text renders in `{face}."
        )
        found.append(f"`{name}` ({blocks}) is not loaded by `## Fonts`: {fix}")
    return found


def _font_names(node: object) -> set[str]:
    """Every family the parsed theme holds, wherever a style keeps one."""
    if isinstance(node, dict):
        return set().union(*map(_font_names, node.values()))
    if isinstance(node, (list, tuple)):
        return set().union(*map(_font_names, node))
    if not dataclasses.is_dataclass(node) or isinstance(node, type):
        return set()
    names: set[str] = set()
    for field in dataclasses.fields(node):
        value = getattr(node, field.name)
        if field.name == "font_name" and isinstance(value, str) and value:
            names.add(value)
        else:
            names |= _font_names(value)
    return names


def _font_name_lines(text: str) -> list[tuple[str, str]]:
    """Each ``Font name:`` in *text* with the block it is written in, named by
    its two innermost headings or labels (``Text Styles → Code Block``)."""
    found = []
    path: list[str] = []  # the ##, ###, #### headings, then a bare label
    for raw in _COMMENT.sub("", text).splitlines():
        line = raw.strip()
        if heading := _HEADING.match(line):
            path = path[: len(heading.group(1)) - 2] + [heading.group(2)]
            path += [""] * (3 - len(path))
        elif match := _FONT_NAME.match(line):
            found.append((match.group(1), " → ".join([p for p in path if p][-2:])))
        elif line and ":" not in line and not line.startswith(("-", "*", "#")):
            path = path[:3] + [line]
    return found
