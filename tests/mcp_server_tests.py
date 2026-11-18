"""
Unit tests for the MCP shell (ADR-602) and the checks and fetch policy it rests on.

Pinned here:

  * the server offers exactly its six tools and the skills notes as resources;
  * ``guide`` reads a skills note by name and nothing outside ``skills/``, and
    every tool is annotated read-only and closed-world;
  * ``guide`` reads one section of a note as ``<note>/<section>``, named by its
    heading: it runs to the next heading of its level, and a heading inside a
    code fence is an example, not a section;
  * ``check`` names the authoring mistakes a render would not put into words, and
    stays quiet about what is fine (a disabled link is silent on purpose);
  * ``actions`` numbers the targets with the wire's ordinals (ADR-601);
  * ``preview`` returns a PNG while making no network request at all — the server
    turns ``fetch_policy`` off, and every fetch site obeys it;
  * a local install started with ``--fetch`` previews the picture itself;
  * a character no installed font has is named beside the preview, as a font gap;
  * a page too big for one bitmap is a tool error naming its size;
  * a real stdio session works end to end: the pipeline's prints never reach the
    protocol stream.

Run with: uv run python tests/mcp_server_tests.py
"""

from importlib.metadata import version
import asyncio
import base64
import contextlib
import dataclasses
import io
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

import skia

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

from md2ui import mcp_server, meanings, notes, session
from md2ui.check import check_markdown
from md2ui.pipeline.render_placeholders import theme_picture
from md2ui.pipeline.render_actions import action_targets
from md2ui.pipeline.render_settings import VIEW
from md2ui.utils import fetch_policy, font_loader, image_cache
from md2ui.utils.fetch_policy import POLICY, fetch_remote

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "data/markdown/tests/tests-link-actions.md"

_MODELS = None
_SERVER = None


def _kit():
    global _MODELS
    if _MODELS is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _MODELS = session.load_grouping_kit()
    return _MODELS


def _server():
    global _SERVER
    if _SERVER is None:
        _SERVER = mcp_server.build_server(None)
    return _SERVER


def _call(name: str, arguments: dict) -> Any:
    """A tool's CallToolResult. Typed Any: the SDK's return type also covers an
    input-required result, which none of these tools can produce."""
    with contextlib.redirect_stdout(io.StringIO()):
        return asyncio.run(_server().call_tool(name, arguments))


def _restore_app_policy() -> None:
    """build_server turns fetching off for the process; other test modules run in
    the same process, as an app would."""
    POLICY.remote = True
    VIEW.placeholder_images = False


def test_server_offers_its_tools_and_the_skills():
    try:
        tools = {t.name for t in asyncio.run(_server().list_tools())}
        assert tools == {"check", "actions", "outline", "layout", "preview", "guide"}
        uris = {str(r.uri) for r in asyncio.run(_server().list_resources())}
        assert "md2ui://skills/README.md" in uris, uris
        # The includes note is served only by a server with includes (ADR-612).
        notes = [p for p in mcp_server.SKILLS.glob("*.md") if p.stem != "includes"]
        notes += list(mcp_server.PATTERNS.glob("*.md"))
        assert len(uris) == len(notes), uris
        reported = _server().version
        assert reported == version("md2ui"), f"serverInfo.version is {reported!r}"
    finally:
        _restore_app_policy()
    print(f"  ✓  six tools, {len(uris)} skills notes as resources, version {reported}")


def _text(result: Any) -> str:
    if result.structured_content is not None:
        return result.structured_content.get("result", "")
    return " ".join(getattr(c, "text", "") for c in result.content)


def test_guide_reads_a_note_by_name_and_nothing_else():
    try:
        core = _text(_call("guide", {}))
        elements = _text(_call("guide", {"topic": "Elements"}))
        try:
            outside = _call("guide", {"topic": "../pyproject.toml"})
        except ToolError as exc:
            refused = str(exc)
        else:
            assert outside.is_error, outside
            refused = _text(outside)
        tools = asyncio.run(_server().list_tools())
    finally:
        _restore_app_policy()
    readme = (mcp_server.SKILLS / "README.md").read_text()
    # The core note ends with the placement table, then the placeholders (ADR-406).
    tail = meanings.placed_spellings(None) + meanings.placeholder_spellings(None)
    assert core == readme + tail, core[len(readme) :]
    assert elements == (mcp_server.SKILLS / "elements.md").read_text()
    assert "no note named" in refused and "elements" in refused, refused
    for tool in tools:
        hints = tool.annotations
        assert hints is not None and hints.read_only_hint, tool.name
        assert hints.open_world_hint is False, tool.name
    print("  ✓  guide reads skills/ notes by name, nothing else; all tools read-only")


def test_guide_reads_one_section_of_a_note():
    try:
        section = _text(_call("guide", {"topic": "elements/icon-buttons"}))
        nested = _text(_call("guide", {"topic": "Structure/adds-space"}))
    finally:
        _restore_app_policy()
    elements = (mcp_server.SKILLS / "elements.md").read_text()
    assert section.startswith("## Icon buttons\n"), section[:80]
    assert section in elements and len(section) < len(elements) / 10
    assert "## A link's label" not in section and "## An icon INSIDE" not in section
    assert nested.startswith("## `+++` adds space\n"), nested[:80]
    print("  ✓  guide reads one section of a note, named by its heading")


def test_guide_feed_reads_the_feed_section():
    try:
        feed = _text(_call("guide", {"topic": "feed"}))
        section = _text(
            _call(
                "guide",
                {"topic": "elements/a-value-a-process-changes-while-the-page-is-shown"},
            )
        )
    finally:
        _restore_app_policy()
    assert feed.startswith("## A value a process changes while the page is shown\n")
    assert feed == section
    print("  ✓  guide('feed'), the tool's own name, reads the feed section")


def test_sections_run_to_the_next_heading_of_their_level_outside_fences():
    text = (
        "# Note\n\nIntro.\n\n## A link's `label`\n\nOne.\n\n```md\n## Not a heading\n```\n\n"
        "### Deeper\n\nTwo.\n\n## Next\n\nThree.\n"
    )
    found = notes.sections(text)
    assert list(found) == ["note", "a-links-label", "deeper", "next"], list(found)
    assert found["a-links-label"].endswith("### Deeper\n\nTwo.\n\n"), found
    assert "## Not a heading" in found["a-links-label"]
    assert found["next"] == "## Next\n\nThree.\n"
    print(
        "  ✓  a section runs to the next heading of its level; a fenced one is an example"
    )


def test_guide_serves_patterns_and_the_pages_it_cites():
    try:
        index = _text(_call("guide", {"topic": "patterns"}))
        page = _text(_call("guide", {"topic": "pages/widget-board"}))
    finally:
        _restore_app_policy()
    patterns = sorted(mcp_server.PATTERNS.glob("*.md"))
    assert (index == "(no patterns yet)") == (not patterns), index
    for path in patterns:
        assert f"- {path.stem}: " in index, (path.stem, index)
    assert page == (mcp_server.PAGES / "widget-board.md").read_text()
    # Every page the index names ships beside it, and no page points into data/,
    # which the package does not ship.
    index_text = mcp_server.PAGES_INDEX.read_text()
    assert "data/" not in index_text
    notes = mcp_server.guide_notes()
    for kind in mcp_server.page_kinds(index_text).values():
        for name in re.findall(r"^\| [^|]+ \| `([^`]+)`", kind, re.M):
            assert f"pages/{name}" in notes, name
    kinds = mcp_server.page_kinds(mcp_server.PAGES_INDEX.read_text())
    weather = kinds["pages/weather"]
    assert "`hours-ahead`" in weather and "`places`" in weather, weather
    assert "| kind |" in weather and "`watchlist`" not in weather, weather
    assert "pages/---" not in kinds and "pages/cooking recipe" not in kinds, sorted(
        kinds
    )
    print(
        f"  ✓  guide: {len(patterns)} patterns indexed, every indexed page ships in skills/, "
        "a kind lists its pages"
    )


def test_check_names_the_mistakes():
    doc = (
        "# Page {#top}\n\nIntro.\n\n[Go]() [Up](#top) [Away](#nowhere)\n\n"
        "~~[Old](/old)~~\n\nAsk to [talk to sales](agent:contact-sales) today.\n"
    )
    with contextlib.redirect_stdout(io.StringIO()):
        codes = [(i["code"], i.get("x")) for i in check_markdown(doc, _kit())]
        lone = check_markdown("Just one paragraph.", _kit())
        empty = check_markdown("\n   \n", _kit())
        clean = check_markdown(FIXTURE.read_text(), _kit())
    assert ("reports-nothing", 0) in codes, codes
    assert ("anchor-missing", 2) in codes, codes
    assert any(c == "action-in-sentence" for c, _ in codes), codes
    assert not any(c == "reports-nothing" and x == 3 for c, x in codes), (
        "a disabled link is silent on purpose"
    )
    # A one-paragraph document DRAWS, so check is silent about it:
    # `renders-nothing` means an empty document.
    assert lone == [], lone
    assert [i["code"] for i in empty] == ["renders-nothing"], empty
    # The fixture's two plain boxes have no commit button: advice, not a mistake.
    assert [i["code"] for i in clean] == [
        "action-in-sentence",
        "boxes-without-commit",
    ], clean
    print("  ✓  check: dead targets, missing anchors, sentence actions, blank docs")


def test_check_warns_when_a_heading_splits():
    with contextlib.redirect_stdout(io.StringIO()):
        split = check_markdown("## Deploying - a guide\n", _kit())
        em_dash = check_markdown("## Deploying — a guide\n", _kit())
        plain = check_markdown("## Deploying guide\n", _kit())
    assert len(split) == 1 and split[0]["code"] == "split-heading", split
    assert split[0]["level"] == "warning", split
    message = split[0]["message"]
    assert "Deploying - a guide" in message, message
    assert "`\\-`" in message and "` — `" in message, message
    assert not any(issue["code"] == "split-heading" for issue in em_dash), em_dash
    assert not any(issue["code"] == "split-heading" for issue in plain), plain
    # A NUMBERED heading records the split on the ordered_item inside it, not
    # on the heading — the shape most real dash-split headings have.
    with contextlib.redirect_stdout(io.StringIO()):
        numbered = check_markdown("## 1. **Strobe** - Deadmau5\n", _kit())
    split_numbered = [i for i in numbered if i["code"] == "split-heading"]
    assert len(split_numbered) == 1, numbered
    assert "**Strobe** - Deadmau5" in split_numbered[0]["message"], split_numbered
    print("  ✓  check: split headings warn, numbered included; em-dash stays quiet")


def test_actions_use_the_wire_ordinals():
    try:
        result = _call("actions", {"markdown": FIXTURE.read_text()})
    finally:
        _restore_app_policy()
    rows = result.structured_content["result"]
    with contextlib.redirect_stdout(io.StringIO()):
        ast = session.group_markdown(FIXTURE.read_text(), _kit())
    assert ast is not None
    assert len(rows) == len(action_targets(ast.to_dict())), rows
    assert rows[0] == {
        "x": 0,
        "kind": "agent",
        "label": "Yes",
        "action": "generate-report",
        "params": {"format": "pdf", "year": "2026"},
        "sent": True,
    }, rows[0]
    assert rows[3] == {"x": 3, "kind": None, "disabled": True}, rows[3]
    assert rows[8]["kind"] == "link" and rows[8]["sent"] is False, rows[8]
    print(f"  ✓  actions: {len(rows)} targets under the wire's ordinals")


def test_preview_is_a_png_and_fetches_nothing():
    calls: list[str] = []
    real = urllib.request.urlopen

    def refuse(url, *args, **kwargs):
        calls.append(str(getattr(url, "full_url", url)))
        raise AssertionError("a server must not fetch")

    urllib.request.urlopen = refuse  # type: ignore[assignment]
    try:
        doc = "# Shot\n\n![A photo](https://example.com/photo.png)\n\nBelow it.\n"
        POLICY.remote = True  # as an app left it: the tool must switch it off itself
        result = _call("preview", {"markdown": doc, "width": 767})
        assert POLICY.remote, "the tool restores the policy it found"
        POLICY.remote = False  # now the sites themselves, as a server runs them
        assert fetch_remote("https://example.com/x.png") is None
        assert theme_picture("https://example.com/bg.png") is None
        assert font_loader._download("https://example.com/Font.ttf") is None
    finally:
        urllib.request.urlopen = real  # type: ignore[assignment]
        _restore_app_policy()
    images = [c for c in result.content if getattr(c, "type", "") == "image"]
    assert images and images[0].mime_type == "image/png", result.content
    assert not calls, calls
    assert fetch_policy.POLICY.remote, "the app policy is back"
    print("  ✓  preview: a PNG, and not one network request")

    def width_of(arguments: dict) -> int:
        result = _call("preview", {"markdown": "# Look\n\nA line.\n", **arguments})
        (image,) = [c for c in result.content if getattr(c, "type", "") == "image"]
        data = skia.Data.MakeWithCopy(base64.b64decode(image.data))
        return skia.Image.MakeFromEncoded(data).width()

    # An agent pays by area: a look is small unless it asks for more.
    assert width_of({}) == 480, width_of({})
    assert width_of({"picture_width": 0}) > 480
    print("  ✓  preview: 480 px wide unless asked, full size with picture_width 0")


def test_preview_names_a_glyph_no_font_has():
    """A box in the picture reads as a wrong spelling; the preview says it is a
    font gap. A symbol some installed font draws is not reported."""
    covered = _call("preview", {"markdown": "# G\n\nDone ✓ 日本\n"})
    assert [c.type for c in covered.content] == ["image"], covered.content
    gap = _call("preview", {"markdown": "# G\n\nOdd \u0378 here\n"})
    notes = [c.text for c in gap.content if c.type == "text"]
    assert len(notes) == 1 and "U+0378" in notes[0], gap.content
    print("  ✓  preview: a glyph no font has is named; a fallback glyph is not")


def _files_open_in(folder: str) -> list[str] | None:
    """The files under *folder* this process holds open; None where the platform
    cannot list them (Windows, which instead refuses to delete one)."""
    real = os.path.realpath(folder)
    if os.path.isdir("/proc/self/fd"):  # Linux
        paths = []
        for fd in os.listdir("/proc/self/fd"):
            with contextlib.suppress(OSError):
                paths.append(os.readlink(f"/proc/self/fd/{fd}"))
    elif sys.platform == "darwin":
        import fcntl

        paths = []
        for fd in os.listdir("/dev/fd"):
            with contextlib.suppress(OSError):
                raw = fcntl.fcntl(int(fd), fcntl.F_GETPATH, bytes(1024))
                paths.append(raw.rstrip(b"\0").decode())
    else:
        return None
    return sorted(p for p in paths if p.startswith(real + os.sep))


def test_a_local_install_previews_pictures():
    """``--fetch`` (a local plugin's launch): ``preview`` loads the picture, as the
    window on the same machine does, and says it reaches outside the process."""
    surface = skia.Surface(40, 30)
    surface.getCanvas().clear(skia.ColorRED)
    red = bytes(surface.makeImageSnapshot().encodeToData())
    url = "https://example.com/local-preview.png"
    calls: list[str] = []

    def download(asked: str) -> bytes:
        calls.append(asked)
        return red

    real_download, real_dir = image_cache._download, image_cache._CACHE_DIR
    with tempfile.TemporaryDirectory() as tmp:
        image_cache._download, image_cache._CACHE_DIR = download, Path(tmp)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                server = mcp_server.build_server(None, fetch=True)
                POLICY.remote = (
                    False  # as another server left it: the tool sets its own
                )
                tools = {t.name: t for t in asyncio.run(server.list_tools())}
                doc = f"# Shot\n\n![A photo]({url})\n\nBelow it.\n"
                arguments = {"markdown": doc, "picture_width": 0}
                result: Any = asyncio.run(server.call_tool("preview", arguments))
            assert not POLICY.remote, "the tool restores the policy it found"
            # Every thread's cache connection is closed once the preview is
            # done: Windows cannot delete the folder of an open cache file.
            held = _files_open_in(tmp)
            assert not held, held
        finally:
            image_cache._download, image_cache._CACHE_DIR = real_download, real_dir
            _restore_app_policy()
    assert calls == [url], calls
    (image,) = [c for c in result.content if getattr(c, "type", "") == "image"]
    data = skia.Data.MakeWithCopy(base64.b64decode(image.data))
    pixels = skia.Image.MakeFromEncoded(data).toarray(
        colorType=skia.kRGBA_8888_ColorType
    )
    reds = (
        (pixels[..., 0] > 200) & (pixels[..., 1] < 60) & (pixels[..., 2] < 60)
    ).sum()
    assert reds > 1000, f"the picture is drawn, not a placeholder ({reds} red pixels)"
    hints = tools["preview"].annotations
    assert hints is not None and hints.open_world_hint is True, hints
    assert "Pictures load here" in (tools["preview"].description or "")
    print("  ✓  --fetch: preview downloads the picture, draws it, and is open-world")


def test_oversize_markdown_is_refused():
    """Refused as a tool error the agent can read — not an unexpected crash."""
    try:
        result = _call("check", {"markdown": "x" * (300 * 1024)})
    except ToolError as exc:
        assert not isinstance(exc, UnexpectedToolError), repr(exc)
        assert "bytes" in str(exc), str(exc)
    else:
        assert result.is_error, result
    finally:
        _restore_app_policy()
    print("  ✓  markdown over the wire's cap is refused as a tool error")


def test_preview_refuses_a_page_past_the_bitmap_limit():
    """Even at the smallest scale a preview paints, a page can be too big for one
    bitmap: the agent reads that as a tool error naming the size, not a crash."""
    build = session.build_scene

    def huge(*args, **kwargs):
        return dataclasses.replace(
            build(*args, **kwargs), width=300_000, height=200_000
        )

    session.build_scene = huge
    try:
        result = _call("preview", {"markdown": "# Big\n\nA line.\n"})
    except ToolError as exc:
        assert not isinstance(exc, UnexpectedToolError), repr(exc)
        message = str(exc)
    else:
        assert result.is_error, result
        message = _text(result)
    finally:
        session.build_scene = build
        _restore_app_policy()
    assert " px" in message and "2 GiB" in message, message
    print("  ✓  preview: a page too big for one bitmap is a tool error with its size")


async def _stdio_session() -> tuple[set[str], str]:
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "md2ui.mcp_server"], cwd=str(ROOT)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            tools = {t.name for t in (await client.list_tools()).tools}
            result = await client.call_tool(
                "check", {"markdown": "# T {#t}\n\n[Top](#t) [Go]()\n"}
            )
            text = " ".join(getattr(c, "text", "") for c in result.content)
            return tools, text


def test_a_real_stdio_session_stays_clean():
    """The subprocess prints while it loads and groups; if one print
    reached stdout, the client would fail to parse the stream."""
    tools, text = asyncio.run(_stdio_session())
    assert "check" in tools and "preview" in tools, tools
    assert "reports-nothing" in text, text
    print("  ✓  a stdio session: initialize, list, call — the stream stays clean")


def test_check_names_a_divider_that_fell_back():
    with contextlib.redirect_stdout(io.StringIO()):
        bad = check_markdown("## A\n\nOne\n::: 1 1.5 >\nTwo\n", _kit())
        good = check_markdown("## A\n\nOne\n::: 1 <\nTwo\n", _kit())
        fenced = check_markdown("## A\n\n```\n::: < >\n```\n", _kit())
    fell = [i for i in bad if i["code"] == "divider-fallback"]
    assert len(fell) == 1 and "::: 1 1.5 >" in fell[0]["message"], bad
    assert not any(i["code"] == "divider-fallback" for i in good + fenced), good
    print("  ✓  check: a mistyped divider is named; valid and fenced ones are not")


def test_check_names_a_backslash_that_is_drawn():
    """md2ui escapes ASCII punctuation and its own separators, so a backslash
    before a long dash or an arrow is drawn. Every escape md2ui does read stays
    silent, as do code and a hard break."""
    probe = (
        "Best all-round value \\— a well-reviewed 4-star.\n\n"
        "A range \\– from Nov 4 to Nov 7.\n\n"
        "Best all-round value — a well-reviewed 4-star.\n"
    )
    with contextlib.redirect_stdout(io.StringIO()):
        drawn = check_markdown(probe, _kit())
        arrow = check_markdown("## A\n\nOne \\→ two\n", _kit())
        fine = check_markdown(
            "## A\n\nMon\\-15 \\. 4\\/8 Wait\\... \\+++ \\@ct\n\n"
            "`a \\— b` and \\\\— c\n\n"
            "Line one\\\nline two\n\n```\nx \\— y\n```\n\n"
            "<!-- a \\— b -->\n",
            _kit(),
        )
    found = [i for i in drawn if i["code"] == "drawn-backslash"]
    assert len(found) == 2, drawn
    assert "\\—" in found[0]["message"] and "\\–" in found[1]["message"]
    assert all(i["level"] == "warning" for i in found), found
    assert [i["code"] for i in arrow] == ["drawn-backslash"], arrow
    assert "\\→" in arrow[0]["message"], arrow
    assert not any(i["code"] == "drawn-backslash" for i in fine), fine
    print("  ✓  check: a backslash before a dash or arrow is named; escapes are not")


def test_check_names_an_image_param_the_renderer_refuses():
    """Retired and misspelt params, which change nothing on the page, reach
    ``check`` in the renderer's own words."""
    photo = "https://example.com/p.jpg?w=1200"
    retired = (
        f"![Everything you crave]({photo}&md2ui.arrangement=aside"
        "&md2ui.aside_ratio=1:1&md2ui.content_valign=center)\n"
        "## Everything you crave, delivered.\nYour favorite local restaurants.\n"
    )
    with contextlib.redirect_stdout(io.StringIO()):
        old = check_markdown(retired, _kit())
        typo = check_markdown(f"![Typo]({photo}&md2ui.aspec_ratio=4:3)\n", _kit())
        fine = check_markdown(f"![Fine]({photo}&md2ui.aspect_ratio=4:3)\n", _kit())
    params = [i for i in old if i["code"] == "image-param"]
    assert len(params) == 3 and all(i["level"] == "warning" for i in params), old
    for i, name in zip(params, ("arrangement", "aside_ratio", "content_valign")):
        assert i["message"].startswith(
            f"Image `Everything you crave`: 'md2ui.{name}' was removed — "
        ), i
    assert [i["message"] for i in typo] == [
        "Image `Typo`: unknown property 'md2ui.aspec_ratio'."
    ], typo
    assert not any(i["code"] == "image-param" for i in fine), fine
    print("  ✓  check: a refused image param is named, with its replacement")


def _covers(params: str = "", titles=("Squeal", "Bands", "Cool girl")) -> str:
    """Playlist cards, each a heading over a cover, with *params* on every cover."""
    return "\n".join(
        f"### {t}\n![{t}](https://example.com/{i}.jpg{params})\n_By someone_\n"
        for i, t in enumerate(titles)
    )


def test_check_names_a_repeated_run_of_pictures_without_a_ratio():
    """One warning per run, naming it; a chosen ratio, a circle, one annotated
    member (the run is polled together) or a lone picture raise none."""
    one = "?md2ui.aspect_ratio=1:1"
    first_only = _covers(titles=("Squeal",)).replace(".jpg", f".jpg{one}") + (
        "\n" + _covers(titles=("Bands", "Cool girl"))
    )
    with contextlib.redirect_stdout(io.StringIO()):
        bare = check_markdown(_covers(), _kit())
        clean = {
            "ratio": check_markdown(_covers(one), _kit()),
            "ladder": check_markdown(
                _covers("?md2ui.aspect_ratio=3:4,1:1@600"), _kit()
            ),
            "circle": check_markdown(_covers("?md2ui.shape=circle"), _kit()),
            "one annotated": check_markdown(first_only, _kit()),
            "lone": check_markdown(
                "## Today\n![Harbour](https://example.com/h.jpg)\nCalm seas.\n",
                _kit(),
            ),
        }
        sized = check_markdown(_covers("?md2ui.max_width=300"), _kit())
    ratio = [i for i in bare if i["code"] == "image-ratio"]
    assert len(ratio) == 1 and ratio[0]["level"] == "warning", bare
    assert ratio[0]["message"].startswith(
        "3 pictures in the repeated run at `Squeal` have no ratio — the default "
        "crops them to 3:2 (16:9 from 768px, 2.35:1 from 1024px)."
    ), ratio
    assert "skills/images.md, question 1" in ratio[0]["message"], ratio
    for name, issues in clean.items():
        assert not any(i["code"] == "image-ratio" for i in issues), (name, issues)
    # A param that is not a ratio leaves the default in place.
    assert [i["code"] for i in sized] == ["image-ratio"], sized
    print("  ✓  check: a repeated run of pictures at the default ratio is named once")


def test_a_server_with_no_theme_uses_the_working_directory_s_then_md2ui_s():
    """With no --theme, the MCP servers preview with the THEME.md in the working
    directory, else md2ui's default, never bare dataclass defaults; the demo hands
    the same path to its window."""
    import os

    here = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.chdir(tmp)
            assert session.default_theme_path() == session.resource_root() / "THEME.md"
            (Path(tmp) / "THEME.md").write_text("# Theme\n")
            assert session.default_theme_path() == Path.cwd() / "THEME.md"
        finally:
            os.chdir(here)
    print("  ✓  no --theme: the working directory's THEME.md, else md2ui's default")


TESTS = [
    test_a_server_with_no_theme_uses_the_working_directory_s_then_md2ui_s,
    test_server_offers_its_tools_and_the_skills,
    test_guide_reads_a_note_by_name_and_nothing_else,
    test_guide_reads_one_section_of_a_note,
    test_guide_feed_reads_the_feed_section,
    test_sections_run_to_the_next_heading_of_their_level_outside_fences,
    test_guide_serves_patterns_and_the_pages_it_cites,
    test_check_names_the_mistakes,
    test_check_warns_when_a_heading_splits,
    test_check_names_a_divider_that_fell_back,
    test_check_names_a_backslash_that_is_drawn,
    test_check_names_an_image_param_the_renderer_refuses,
    test_check_names_a_repeated_run_of_pictures_without_a_ratio,
    test_actions_use_the_wire_ordinals,
    test_preview_is_a_png_and_fetches_nothing,
    test_preview_names_a_glyph_no_font_has,
    test_a_local_install_previews_pictures,
    test_preview_refuses_a_page_past_the_bitmap_limit,
    test_oversize_markdown_is_refused,
    test_a_real_stdio_session_stays_clean,
]

if __name__ == "__main__":
    print("MCP Server Tests")
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
