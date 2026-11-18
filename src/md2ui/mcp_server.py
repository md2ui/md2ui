"""The MCP shell: md2ui's authoring tools for an agent, over stdio (ADR-602).

A third shell beside the CLI and the app (ADR-600). Like the CLI, every request
runs once and returns: nothing here watches a file, loops over a document or opens
a window. Each tool is one of the CLI's one-shot paths through ``session``.

What it is for: a backend agent writes md2ui Markdown by
following ``skills/``, and the backend delivers that Markdown to its frontends,
which render it themselves (ADR-601). The agent uses these tools to check what it
wrote — never to deliver it:

* ``check``   — authoring mistakes a render would not put into words;
* ``actions`` — what the message offers, numbered by the wire's ordinal ``x``;
* ``outline`` — the grouped structure, compact;
* ``layout``  — the layout shape at a width, compact;
* ``preview`` — a PNG, for when the agent needs to look;
* ``guide``   — the ``skills/`` notes, by name, and the theme's own vocabulary:
  its declared meanings and its patterns. The theme is linted against them once,
  at start, into the log (``theme_lint``); a pattern that fails ``check`` is not
  served.

The rules of this shell:

* **It fetches nothing** (``utils.fetch_policy``): images draw as placeholders,
  and theme font and background URLs are skipped. Fonts are what the developer
  installed with the server; the theme is the one it was started with — the
  user's design system, never a path a model chose. A local install is the
  exception, started with ``--fetch`` by its packaging, never by a tool's
  argument: it runs on the user's machine beside a window that fetches the same
  pictures, so ``preview`` loads them as the window does. A hosted server never
  takes it (ADR-602).
* **stdout is the protocol.** The pipeline prints progress, so every call runs
  with stdout sent to stderr; one stray print would corrupt the stream.
* **Outputs are small**, because the agent pays for them in tokens: outlines, not
  the AST and layout dumps the CLI writes to disk.
* **The skills are read on demand,** through ``guide`` and as resources. A client
  may leave resources for the user to attach, so the tool is how an agent reads a
  note in any client. ``README.md`` is the index worth reading first; the rest
  are loaded when a question needs them.
* **A cold agent learns what md2ui is from the instructions and the tool
  descriptions,** the only text every client shows it: writing for md2ui is
  writing its reply, and Markdown is harmless by construction.

Run it: ``md2ui-mcp [--theme PATH]``.
"""

from __future__ import annotations

import argparse
import contextlib
import math
import sys
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import TypeVar

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from md2ui import includes as including, meanings, session, theme_lint
from md2ui.advice import Reading, reply_issues
from md2ui.includes import Includes, static_includes
from md2ui.notes import aliased, sections
from md2ui.pattern_respell import respelled
from md2ui.stale_code import StaleCode, noting
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_render import load_background_images
from md2ui.pipeline.render_actions import action_targets
from md2ui.pipeline.render_glyph_faces import missing_glyphs
from md2ui.pipeline.render_settings import VIEW
from md2ui.utils.fetch_policy import POLICY
from md2ui.utils.image_cache import ImageCache
from md2ui.utils.png import encode_png
from md2ui.wire import FORWARDED_KINDS, MAX_SERVER_FRAME_BYTES, escaped_bytes

MIN_WIDTH, MAX_WIDTH = 320, 1600
MAX_PREVIEW_PIXELS = 16_000_000
MAX_OUTLINE_LINES = 400
SKILLS = session.resource_root() / "skills"

# What md2ui is, for an agent that has never heard of it. Shared with the demo
# shell (ADR-602), which says what it adds after it.
ABOUT = (
    "md2ui renders a Markdown answer as UI for the user, so writing for it is "
    "writing your reply: plain Markdown, nothing else. That is harmless by "
    "construction: Markdown is text, nothing in it runs, and a link or an action "
    "does nothing until the user clicks it; a click comes back to you as a "
    "sentence, never as a command. Call `guide` for the authoring notes before "
    "your first answer, and `guide` with a note's name only when a question "
    "needs it."
)

INSTRUCTIONS = ABOUT + (
    " These tools check an answer before your backend delivers it: `check` "
    "finds authoring mistakes; `actions` lists what the answer offers the user; "
    "`outline` and `layout` show its structure; `preview` renders it."
)

# Every tool here reads the Markdown it is given and nothing else, and none
# reaches outside this process (MCP tool annotations; a client may use them to
# ask the user less) — but `preview` on a local install started with `--fetch`.
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

FETCH_HELP = (
    "load pictures, theme fonts and backgrounds as the window does: for a local "
    "install only, never a hosted server (ADR-602)"
)

PATTERNS = meanings.SKILLS_PATTERNS
PAGES = SKILLS / "pages"
PAGES_INDEX = SKILLS / "pages.md"


def guide_notes() -> dict[str, Path]:
    """Everything ``guide`` serves, by lower-cased name without ``.md``:
    the ``skills/`` notes; the section patterns as ``patterns/<name>``; and the
    whole example pages as ``pages/<name>``. All of it ships inside ``skills/``.
    Read on every call, since the notes are edited while a server runs."""
    notes = {p.stem.lower(): p for p in SKILLS.glob("*.md")}
    notes |= {f"patterns/{p.stem.lower()}": p for p in PATTERNS.glob("*.md")}
    notes |= {f"pages/{p.stem.lower()}": p for p in PAGES.glob("*.md")}
    return notes


def page_kinds(index: str) -> dict[str, str]:
    """``pages/<kind>`` for each kind ``skills/pages.md`` lists: the rows of the
    table under its header, and no later table's, so an agent that asks for the
    weather page by its kind gets the weather pages to choose from."""
    lines = index.splitlines()
    head = next(
        (i for i, line in enumerate(lines) if line.startswith("| kind |")), None
    )
    if head is None:
        return {}
    rows: dict[str, list[str]] = {}
    for line in lines[head + 2 :]:
        if not line.startswith("|"):
            break
        cells = line.split("|")
        if len(cells) > 2 and cells[1].strip():
            rows.setdefault(cells[1].strip().lower(), []).append(line)
    intro = 'Read one with `guide("pages/<name>")`: each says when it leads.\n\n'
    return {
        f"pages/{kind}": intro + "\n".join([*lines[head : head + 2], *kind_rows]) + "\n"
        for kind, kind_rows in rows.items()
    }


def note_topics(notes: dict[str, Path]) -> dict[str, str]:
    """Every topic *notes* serve, whatever the theme, with its text: each note
    whole, each ``skills/`` note's sections as ``<note>/<section>``, each kind of
    page the index lists, unless a page has that name, and the aliases."""
    topics = {name: path.read_text(encoding="utf-8") for name, path in notes.items()}
    for name, path in notes.items():
        if path.parent == SKILLS:
            found = sections(topics[name])
            topics |= {f"{name}/{section}": text for section, text in found.items()}
    if PAGES_INDEX.is_file():
        topics = page_kinds(PAGES_INDEX.read_text(encoding="utf-8")) | topics
    return aliased(topics)


def pattern_index(notes: dict[str, Path], theme: dict[str, Path] | None = None) -> str:
    """One line per pattern, from its frontmatter: the index costs a few hundred
    tokens, and the agent reads only the pattern it needs. The *theme*'s own
    follow under their own heading."""
    rows = [
        f"- {key.removeprefix('patterns/')}: {meanings.pattern_description(path)}"
        for key, path in sorted(notes.items())
        if key.startswith("patterns/")
    ]
    head = "References, not templates: your content decides the shape. Read one with "
    lines = [head + "guide('patterns/<name>'):", *rows] if rows else []
    if theme:
        lines += [
            "",
            "This theme's patterns, the better reference where your content has "
            "their shape. Read one with guide('theme/<name>'):",
            *(f"- {n}: {meanings.pattern_description(p)}" for n, p in theme.items()),
        ]
    return "\n".join(lines) if lines else "(no patterns yet)"


GUIDE_HELP = (
    "md2ui's authoring notes. With no topic, the core note (about 3k tokens): "
    "what md2ui is, what changes most answers, and what each element means. "
    "``lookup`` is a table from what you want to the Markdown that gives it. "
    'Name a note from its "Read next" table (``elements``, ``dashboards``…) to '
    "read only that one, or ``<note>/<section>`` for one of its sections, named "
    "by its heading (``elements/icon-buttons``). ``patterns`` lists short section "
    "patterns (read one as ``patterns/<name>``); ``pages`` lists whole example "
    "pages (``pages/<name>``). ``theme`` is what this theme's spellings mean and "
    "its own patterns (``theme/<name>``)."
)

T = TypeVar("T")


class _Shell:
    """What one server process loads once: the grouping kit, the theme and its fonts."""

    def __init__(self, theme_path: Path | None, fetch: bool) -> None:
        self.theme_path = theme_path
        self.fetch = fetch
        self._kit: session.GroupingKit | None = None
        self._look: tuple | None = None

    def run(self, work: Callable[[], T]) -> T:
        """Do *work* in server mode, with stdout sent to stderr (stdout carries
        the protocol). Server mode is set per call, not trusted from start-up:
        nothing else in the process can switch fetching back on under a tool."""
        remote, placeholders = POLICY.remote, VIEW.placeholder_images
        POLICY.remote, VIEW.placeholder_images = self.fetch, not self.fetch
        try:
            with contextlib.redirect_stdout(sys.stderr):
                return work()
        finally:
            POLICY.remote, VIEW.placeholder_images = remote, placeholders

    def kit(self) -> session.GroupingKit:
        if self._kit is None:
            self._kit = session.load_grouping_kit()
        return self._kit

    def look(self) -> tuple:
        """``(theme, fonts, background_images)``, loaded once per process."""
        if self._look is None:
            if self.fetch:  # a theme image fails only where it was fetched
                session.load_placeholders()
            theme = session.load_theme(self.theme_path)
            self._look = (
                theme,
                session.load_fonts(theme),
                load_background_images(theme),
            )
        return self._look


def _markdown(markdown: str) -> str:
    """*markdown*, or a ToolError the agent reads as an answer, not a crash."""
    if (size := escaped_bytes(markdown)) > MAX_SERVER_FRAME_BYTES:
        cap = MAX_SERVER_FRAME_BYTES
        raise ToolError(f"markdown is {size} bytes in a frame; the wire's cap is {cap}")
    return markdown


def _width(width: int) -> float:
    return float(min(MAX_WIDTH, max(MIN_WIDTH, int(width))))


def _clip(lines: list[str]) -> str:
    if len(lines) > MAX_OUTLINE_LINES:
        extra = len(lines) - MAX_OUTLINE_LINES
        lines = lines[:MAX_OUTLINE_LINES] + [f"… {extra} more lines"]
    return "\n".join(lines)


def _short(text: str | None, limit: int = 60) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


_OUTLINE_FLAGS = (
    "heading_group",
    "table_group",
    "chart_group",
    "line_group",
    "line_split_group",
)


def _outline_lines(node: dict, depth: int, lines: list[str]) -> None:
    flags = [f for f in _OUTLINE_FLAGS if node.get(f)]
    line = "  " * depth + f"{node.get('node_id') or 'root'} {node.get('type')}"
    if flags:
        line += f" [{', '.join(flags)}]"
    if node.get("content"):
        line += f" {_short(node['content'])!r}"
    lines.append(line)
    for child in node.get("children", []):
        _outline_lines(child, depth + 1, lines)


def _layout_lines(node: dict, index: dict, depth: int, lines: list[str]) -> None:
    line = "  " * depth + str(node.get("type"))
    if node.get("ratios"):
        line += f" {node['ratios']}"
    nd = index.get(node.get("content_id") or "")
    if nd is not None:
        line += f" ← {nd.get('type')} {_short(nd.get('content'), 40)!r}"
    lines.append(line)
    for child in node.get("children", []):
        _layout_lines(child, index, depth + 1, lines)


def build_server(
    theme_path: Path | None = None,
    instructions: str = INSTRUCTIONS,
    fetch: bool = False,
    reading: Reading | None = None,
    includes: Includes | None = None,
    note_stale: bool = False,
) -> MCPServer:
    """The server, with every tool and resource registered. Turns fetching off
    for the whole process first: a server fetches nothing (ADR-602), unless a
    local install asks for *fetch*. The demo shell (ADR-602) passes its own
    *instructions* and adds its delivery tools, and passes its *reading*, so the
    advice its ``show`` gives knows what this session's ``guide`` served.
    *includes* are the lines every tool expands before reading a page (ADR-612);
    by default, the static ones in an ``includes/`` folder beside the theme.
    *note_stale* has every tool say when md2ui's code changed since the start
    (``stale_code``): the demo plugin's, which a session keeps running."""
    POLICY.remote = fetch
    VIEW.placeholder_images = not fetch
    shell = _Shell(theme_path, fetch)
    reading = reading if reading is not None else Reading()
    includes = includes if includes is not None else static_includes(theme_path)

    def _page(markdown: str) -> str:
        """The page as the user would see it: *markdown*, its includes expanded."""
        return including.expand(_markdown(markdown), includes)[0]

    server = MCPServer(
        name="md2ui", version=version("md2ui"), instructions=instructions
    )
    if note_stale:
        server.tool = noting(server.tool, StaleCode())  # type: ignore[method-assign]

    @server.tool(annotations=READ_ONLY)
    def check(markdown: str) -> list[dict]:
        """Authoring issues in an md2ui response: something clickable that reports
        nothing, an anchor that scrolls nowhere, an action inside a sentence, an
        image param the renderer ignores, repeated pictures with no ratio, an
        escape that draws its backslash, a document that draws nothing, an
        element spelling neither this theme (``guide("theme")``) nor a pattern
        declares, a card whose number of buttons breaks its run. An issue with a mechanical fix carries its ``line``, the
        ``text`` there and its ``replacements``: pick one. A ``note`` is advice
        (one offer shown twice, a run whose cards are not all tappable), never a
        defect; an ``advice`` note names, under ``read``, the section of the notes
        that teaches something your answer used, with what to write. An empty
        list means none were found."""
        contract = shell.run(lambda: theme_lint.answer_contract(theme_path))

        def work() -> list[dict]:
            text, regions = including.expand(_markdown(markdown), includes)
            ast = session.group_shared(text, shell.kit())
            return reply_issues(text, ast, contract, reading, includes, regions)

        return shell.run(work)

    @server.tool(annotations=READ_ONLY)
    def actions(markdown: str) -> list[dict]:
        """What the response offers the user, in document order. ``x`` is the
        number a click reports; ``sent`` says whether the click comes back to you
        (agent actions and task boxes) or is handled by the app (links, anchors)."""

        def work() -> list[dict]:
            ast = session.group_shared(_page(markdown), shell.kit())
            out: list[dict] = []
            targets = action_targets(ast.to_dict()) if ast is not None else []
            for x, target in enumerate(targets):
                a = target.action
                if a is None:
                    out.append({"x": x, "kind": None, "disabled": target.disabled})
                    continue
                row: dict = {"x": x, "kind": a.kind, "label": a.label}
                row |= (
                    {"action": a.action, "params": dict(a.params)} if a.action else {}
                )
                row |= {"href": a.href} if a.href else {}
                row |= {"checked": a.checked} if a.checked is not None else {}
                row |= {"value": a.value} if a.value is not None else {}
                row |= {"commits": True} if a.commit else {}
                out.append(row | {"sent": a.kind in FORWARDED_KINDS})
            return out

        return shell.run(work)

    @server.tool(annotations=READ_ONLY)
    def outline(markdown: str) -> str:
        """The grouped structure, one node per line: id, type, flags and the first
        words of its text. Use it to see what md2ui groups together."""

        def work() -> str:
            ast = session.group_shared(_page(markdown), shell.kit())
            if ast is None:
                return "(nothing to group)"
            lines: list[str] = []
            _outline_lines(ast.to_dict(), 0, lines)
            return _clip(lines)

        return shell.run(work)

    @server.tool(annotations=READ_ONLY)
    def layout(markdown: str, width: int = 767) -> str:
        """The layout shape at *width* (320–1600): rows, columns and their ratios,
        and which text each box holds. The first line is the page size."""

        def work() -> str:
            theme, fonts, _bg = shell.look()
            ast = session.group_shared(_page(markdown), shell.kit())
            if ast is None:
                return "(nothing to lay out)"
            root, index = session.prepare(ast, theme)
            scene = session.build_scene(
                LayoutGenerator(), root, index, theme, fonts, _width(width)
            )
            lines = [f"page {int(scene.width)}×{int(scene.height)}"]
            _layout_lines(scene.layout.to_dict(), index, 0, lines)
            return _clip(lines)

        return shell.run(work)

    pictures = (
        "Pictures load here as in the user's window, so look at what each one shows."
        if fetch
        else "Images draw as placeholders here, since this server fetches nothing; "
        "the user's window loads them, so leave them in your answer."
    )

    @server.tool(
        annotations=ToolAnnotations(read_only_hint=True, open_world_hint=fetch),
        description=(
            "A PNG of the response laid out at *width* (320–1600), with the "
            "server's theme and fonts, before anyone sees it: a whole page, or just "
            f"the part you are unsure of. {pictures}\n\n``picture_width`` is the "
            "PNG's, not the layout's: 480 (a few hundred tokens) shows the grouping, "
            "the grid and the buttons; 0 is full size, for reading small text. A "
            "character no font here draws is named in a note beside the PNG, and so "
            "is the section of the notes that teaches something the response used, "
            "when you have not read it."
        ),
    )
    def preview(
        markdown: str, width: int = 767, picture_width: int = 480, scale: float = 1.0
    ) -> Image | list[Image | str]:
        def work() -> Image | list[Image | str]:
            theme, fonts, bg = shell.look()
            ast = session.group_shared(_page(markdown), shell.kit())
            if ast is None:
                raise ToolError("the markdown groups to nothing; run `check`")
            root, index = session.prepare(ast, theme)
            images = ImageCache()
            if shell.fetch:  # as the CLI renders: the pictures land, then the paint
                session.wait_for_images(images, index)
            scene = session.build_scene(
                LayoutGenerator(), root, index, theme, fonts, _width(width)
            )
            pad = theme.root.padding
            area = (scene.width + pad.x) * (scene.height + pad.y)
            safe = min(max(0.1, scale), math.sqrt(MAX_PREVIEW_PIXELS / max(area, 1.0)))
            if picture_width > 0:  # an agent pays by area: a look is small unless asked
                safe = min(safe, picture_width / max(scene.width + pad.x, 1.0))
            try:
                image = session.render_image(
                    scene, index, theme, fonts, images, bg, safe
                )
            except session.PageTooLarge as refused:
                raise ToolError(str(refused)) from None
            finally:
                images.close()  # a long-lived server keeps no cache file open
            data = encode_png(image)
            if data is None:
                raise ToolError("the picture could not be encoded as PNG")
            png = Image(data=data, format="png")
            # A box in the picture reads as a wrong spelling unless it is named.
            faces = [f for f in (fonts.typeface, fonts.mono, fonts.emoji) if f]
            missing = missing_glyphs(_page(markdown), faces)
            contract = theme_lint.answer_contract(theme_path)
            notes = [a["message"] for a in reading.advise(ast.to_dict(), contract)]
            if missing:
                named = ", ".join(f"{ch} (U+{ord(ch):04X})" for ch in missing)
                notes.insert(
                    0,
                    f"No font on this machine has {named}: each draws as a box "
                    "in this preview, not because of how it was written. The user's "
                    "window may have a font for it; if it must show, write another "
                    "character.",
                )
            return [png, *notes] if notes else png

        return shell.run(work)

    # `includes` is named only on a server that has some (ADR-612).
    guide_help = GUIDE_HELP + (including.GUIDE_HINT if includes else "")

    @server.tool(annotations=READ_ONLY, description=guide_help)
    def guide(topic: str = "README.md") -> str:
        notes = guide_notes()
        key = topic.strip().lower().removesuffix(".md")
        reading.read.add(key)
        theme = shell.run(lambda: theme_lint.served_patterns(theme_path))
        if key == "includes":
            return including.guide_text(includes, SKILLS / "includes.md")
        if key == "patterns":
            return pattern_index(notes, theme)
        if key == "theme":
            return meanings.digest(theme_path, theme)
        topics = note_topics(notes)
        themed = {n: path.read_text(encoding="utf-8") for n, path in theme.items()}
        topics |= {f"theme/{name}": text for name, text in themed.items()}
        # Asked for where the shared patterns are, a theme's pattern is served
        # too; a shared one by that name wins.
        topics = {f"patterns/{name}": text for name, text in themed.items()} | topics
        if key not in topics:
            names = ", ".join(sorted(notes))
            raise ToolError(f"no note named {topic!r}; the notes are: {names}")
        if key == "readme":
            own = meanings.own_spellings(theme_path, theme)
            return (
                topics[key]
                + own
                + meanings.placed_spellings(theme_path)
                + meanings.placeholder_spellings(theme_path)
                + (f"\n{including.GUIDE_HINT.strip()}\n" if includes else "")
            )
        if (
            key in notes
            and key.startswith("patterns/")
            and notes[key].parent == PATTERNS
        ):
            # A shared pattern is written in the default theme's spellings: its
            # example is served in this project's (byte-identical by default).
            return respelled(notes[key], meanings.load_contract(theme_path))
        return topics[key]

    for path in sorted(SKILLS.glob("*.md")):
        if path.stem != "includes" or includes:
            _text_resource(server, f"md2ui://skills/{path.name}", path)
    for path in sorted(PATTERNS.glob("*.md")):
        _text_resource(server, f"md2ui://skills/patterns/{path.name}", path)
    if theme_path is not None:
        _text_resource(server, "md2ui://theme", theme_path)
    return server


def _text_resource(server: MCPServer, uri: str, path: Path) -> None:
    @server.resource(uri, name=path.name, mime_type="text/markdown")
    def read() -> str:
        return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="md2ui-mcp", description="md2ui's authoring tools over MCP (stdio)"
    )
    parser.add_argument(
        "--theme", help="the THEME.md this server previews with (the user's own)"
    )
    parser.add_argument("--fetch", action="store_true", help=FETCH_HELP)
    args = parser.parse_args(argv)
    theme = Path(args.theme) if args.theme else session.default_theme_path()
    if theme is not None and not theme.is_file():
        parser.error(f"no such theme: {theme}")
    server = build_server(theme, fetch=args.fetch)
    theme_lint.log(theme)
    server.run("stdio")


if __name__ == "__main__":
    main()
