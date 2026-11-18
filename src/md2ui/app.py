"""The app shell: the user's window, and the loop that keeps it in step with a document.

User-first. ``md2ui-app doc.md`` runs the whole pipeline in process — group, lay
out, place, paint — and hands the grouper's tree to the layout generator in
memory, so the document is the only thing it reads. It watches that document and
re-renders on every save, and holds the key bindings and the live toggles.

This is the ONLY module with a window or a watcher. The one-shot commands an
agent runs are ``md2ui.main`` (``md2ui group | layout | render``), and the
pipeline sequence both shells run is ``md2ui.session``, written once so the
window and a screenshot cannot disagree. Nothing in the pipeline calls back into
this module — the dependency runs one way, shell to pipeline, as the layer
diagram in ``AGENTS.md`` specifies.

``main`` sets display values that the painting code reads. They live on
``render_settings.VIEW``, one object, so a write here lands where a reader in
another module looks; that module's docstring says why a module-level global
would not.

Entry point: ``uv run md2ui-app <doc.md> [options]``, declared in
``pyproject.toml`` under ``[project.scripts]``.
"""

import argparse
import dataclasses
import json
import math
import os
import time
import webbrowser
from pathlib import Path

import glfw
import skia

from md2ui import session
from md2ui.app_capture import CaptureChannel, viewport_image
from md2ui.app_chrome import DEFAULT_ANIMATION, ChromeStyle, WorkingAnimation
from md2ui.app_icon import set_icon
from md2ui.app_native_field import attach as attach_native_field
from md2ui.app_prompt import PromptBar
from md2ui.app_surface import fitted, follow_backing
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_render import (
    HINT_H,
    PADDING,
    RESIZE_DEBOUNCE,
    RESIZE_REGEN_THROTTLE,
    TITLE_H,
    _layout_width,
    _toggle_state,
    _viewport_metrics,
    draw_scene,
    load_background_images,
    make_surface,
    window_to_content,
)
from md2ui.pipeline.render_actions import (
    Action,
    HitRegion,
    action_targets,
    commit_carries,
    hit_region,
    hit_test,
    inert_nodes,
    stepped,
)
from md2ui.pipeline.render_choices import settled_rows, show_locally
from md2ui.pipeline.render_drawing_elements import slider_value_in_rect
from md2ui.pipeline.render_picture import DocumentPicture
from md2ui.pipeline.render_scroll_overlay import (
    clamp_offsets,
    paint_scrolled,
    scrollable_at,
    scrolled_by,
)
from md2ui.pipeline.render_settings import VIEW
from md2ui.utils.image_cache import ImageCache
from md2ui.utils.scroll_state import (
    SCROLL_SPEED,
    ScrollLatch,
    ScrollState,
    split_scroll,
)
from md2ui.wire import MAX_SETTLED, FrameError
from md2ui.wire_client import (
    WIRE_BEARER,
    WireClient,
    carried_states,
    ordinal_of,
    released,
)

# The kinds a click sends to the agent; the rest (links, anchors, copy) are the host's.
SENT = ("agent", "checkbox", "slider")


def _screenshot_path(doc_path: Path, width: float) -> str:
    """Timestamped PNG path in the repo's ``screenshots/`` (git-ignored; installed,
    the working directory's), named after the document: never in a corpus folder."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    root = Path.cwd() if session.installed() else session.repo_root()
    folder = root / "screenshots"
    folder.mkdir(exist_ok=True)
    return str(folder / f"{doc_path.stem}-{int(width)}w-{ts}.png")


def _markdown_save_path(doc_path: Path) -> Path:
    """Timestamped Markdown path next to the document (mirrors the screenshot)."""
    ts = time.strftime("%Y%m%d-%H%M%S")
    return doc_path.resolve().parent / f"{doc_path.stem}-{ts}.md"


def _initial_window_size(
    content_w: int, content_h: int, max_w: int, max_h: int
) -> tuple[int, int]:
    """The size the window opens at: content-fit, never flatter than 16:9.

    A short document would otherwise open as a wide, flat strip. The floor
    comes from the width the window really gets, and the screen caps both.
    """
    w = min(content_w, max_w)
    return w, min(max(content_h, math.ceil(w * 9 / 16)), max_h)


def _mtime(path: Path) -> float:
    """mtime of *path*; 0.0 while it does not exist, so a file that reappears
    mid-session reads as a change."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open a Markdown document in the md2ui window, with live reload"
    )
    parser.add_argument("markdown", nargs="?", help="Path to the Markdown document")
    parser.add_argument(
        "--connect",
        metavar="URL",
        help="Show an md2ui wire server's messages (ws://…/ws) instead of a file; "
        "clicks go back to it as wire events (ADR-601)",
    )
    parser.add_argument(
        "--theme",
        default=None,
        help="Path to THEME.md (default: beside the document, else cwd)",
    )
    parser.add_argument(
        "--bento",
        action="store_true",
        help="Force the bento mosaic layout on, regardless of the theme's "
        "`Layout:` key (toggle on/off with G; T resyncs to the theme)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="Initial layout width in px (the window resizes it afterwards)",
    )
    parser.add_argument(
        "--wireframe",
        action="store_true",
        help="Draw the layout-AST wireframe overlay (toggle with W)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Draw the spacing-gap overlay (toggle with D); add --debug-padding for padding rings",
    )
    parser.add_argument(
        "--debug-padding",
        action="store_true",
        help="Draw the padding-ring overlay: root/section/card content padding (toggle with P)",
    )
    parser.add_argument(
        "--text-boxes",
        action="store_true",
        help="Draw each text's real (tight, full-extent) box (toggle with B)",
    )
    parser.add_argument(
        "--working-animation",
        metavar="PATH",
        help="An animated WebP or GIF played while the agent works, with --connect "
        "(default: assets/demo/working.webp)",
    )
    parser.add_argument(
        "--capture-requests",
        metavar="DIR",
        help="Answer screenshot requests written in DIR (app_capture), so the agent "
        "driving the wire can see what the user sees. The same capture as S",
    )
    args = parser.parse_args()

    VIEW.wireframe = args.wireframe
    VIEW.debug_spacing = args.debug
    VIEW.debug_padding = args.debug_padding
    VIEW.text_boxes = args.text_boxes

    # A wire client (--connect) shows the server's latest message instead of a
    # file; the loop below polls it where it would watch the file's mtime.
    client: WireClient | None = None
    wire_text: str | None = None
    wire_id: str | None = None
    if args.connect:
        # The server's secret comes in the environment, never argv, which any
        # local process can read; dropped so nothing the window starts inherits it.
        client = WireClient(args.connect, bearer=os.environ.pop(WIRE_BEARER, None))
        client.start()
        first = client.wait_first()
        if first is None:
            raise SystemExit(f"[wire] no message from {args.connect}")
        wire_text, wire_id = first.markdown, first.message_id
    elif not args.markdown:
        parser.error("give a Markdown document, or --connect URL")
    md_path = Path(args.markdown or "wire.md")
    if client is None and not md_path.is_file():
        parser.error(f"no such file: {md_path}")
    print(f"document: {args.connect or md_path}")

    theme_path = session.resolve_theme_path(md_path, args.theme)
    theme = session.load_theme(theme_path)
    if theme_path:
        print(f"[theme] loaded {theme_path}")
    # Typefaces are CPU-only — safe to create before GLFW init.
    fonts = session.load_fonts(theme)
    image_cache = ImageCache(background=True)  # photos decode off this thread
    session.load_placeholders()
    background_images = load_background_images(theme)
    # Built once: the watcher regroups on every save, and the kit's memos
    # carry over.
    kit = session.load_grouping_kit()

    # A connected window docks the prompt bar at its bottom edge (ADR-601): the
    # user's own field, and what the agent is doing. A file has no agent to ask.
    # Its look is the window's own, never the theme's; so is the animation played
    # while the agent works, which comes from a file anyone can replace.
    bar: PromptBar | None = None
    working: WorkingAnimation | None = None
    if client is not None:
        chrome = ChromeStyle()
        bar = PromptBar(fonts.typeface, chrome, typed=client.typing)
        VIEW.prompt_bar_h = chrome.bar_h
        VIEW.quit_key_hint = ""
        working = WorkingAnimation.load(
            Path(args.working_animation)
            if args.working_animation
            else DEFAULT_ANIMATION
        )

    # The agent's end of the screenshot: it cannot see this window, so it asks.
    capture = (
        CaptureChannel(Path(args.capture_requests)) if args.capture_requests else None
    )

    # The document's wire targets, so a click reports its ordinal (ADR-601).
    # What each target last SENT, so a settle that changes nothing never leaves.
    # An optimisation, not the rule: the server deduplicates too, because another
    # frontend may not do this and a client cannot be trusted with correctness.
    # Note what this does NOT do: it never withholds a settle the agent might
    # want. A settle a committing press will carry IS sent, and the server
    # records it and declines to deliver it (`wire.Recorded`) -- the client
    # reports, the server decides, so the server can answer `showing` about a
    # form the agent has not been woken for.
    sent_values: dict[int, float] = {}
    targets: list = []

    def load_document():
        """Group the document in memory → ``(root, node_index)``, or None if the
        grouper produced no tree (an empty file is a tree: a blank page)."""
        nonlocal targets
        text = wire_text if client is not None else md_path.read_text(encoding="utf-8")
        ast = session.group_markdown(text or "", kit)
        if ast is None:
            print(
                f"[reload] {md_path}: the grouper produced no tree, keeping the last render"
            )
            return None
        targets = action_targets(ast.to_dict())
        # Seed from the document, so the window's baseline is the server's. The
        # server refuses a settle equal to the last reported value, seeded from
        # the AUTHORED one -- and a duplicate is dropped without an answer, so an
        # event sent here and refused there leaves this window locked waiting for
        # a reply that is not coming. Matching the baselines is what stops that.
        sent_values.clear()
        sent_values.update(
            {
                i: t.action.value
                for i, t in enumerate(targets)
                if t.action is not None and t.action.value is not None
            }
        )
        return session.prepare(ast, theme)

    loaded = load_document()
    if loaded is None:
        raise SystemExit(1)
    ast_root, node_index = loaded
    _md_mtime: float = _mtime(md_path)
    # Which response of the document is on screen: each save is the agent's next
    # message, so an agent event names the one its link came from.
    load_count = 0

    _gen = LayoutGenerator()
    if args.bento:
        _gen.bento_override = True

    def _arrangement_status() -> str:
        """The BENTO/STACK segment of the title bar, refreshing the hint bar's
        K entry on the way past.

        Both halves of the stacking state — the title reading and the key it
        names — are hidden while bento is on. Bento tiles a container before the
        stacking flow is ever asked (see _decide_group_rules), so the state is
        not in force, and a frame that reports it invites a press that cannot
        change the picture. G brings both back.
        """
        bento = _gen.bento_requested
        VIEW.stack_key_hint = "" if bento else "  |  K stack"
        if bento:
            return "  |  BENTO: on"
        stack = _toggle_state(_gen.pack_unique_requested)
        return f"  |  BENTO: off  |  STACK: {stack}"

    # Boot layout at the asked width (or a 1024 estimate) — it only sizes the
    # window; the first real layout follows once the window exists.
    scene = session.build_scene(
        _gen, ast_root, node_index, theme, fonts, float(args.width or 1024)
    )
    # Once at startup; the resize/reload rebuilds below would only repeat it.
    session.report_url_params(_gen)
    # How far the user has scrolled each clipped code block, by node id, and the
    # one under the pointer: the host's, per frame (Scene.scrollables, ADR-404).
    block_offsets: dict[str, tuple[float, float]] = {}
    hovered_block: str | None = None
    latch = ScrollLatch()

    def _title() -> str:
        prefix = f"{theme.name}  |  " if theme.name else ""
        return (
            f"{prefix}{int(scene.width)}×{int(scene.height)} (content-fit)  |  "
            f"{len(scene.boxes)} boxes{_arrangement_status()}"
            f"\n{md_path}"
        )

    title = _title()
    print(f"{int(scene.width)}×{int(scene.height)}, {len(scene.boxes)} boxes")

    if not glfw.init():
        raise RuntimeError("glfw.init() failed")

    glfw.window_hint(glfw.STENCIL_BITS, 8)
    # A core context: macOS's default one is GL 2.1, whose GLSL 1.10 has no
    # `gl_VertexID`, so Skia's atlas path shader fails to compile and every
    # path it routes there -- a chart's lines, depending on their size on
    # screen -- silently does not draw. Without one, the default context.
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 2)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

    # Cap initial window size to the screen so oversized layouts still open
    monitor = glfw.get_primary_monitor()
    if monitor:
        vm = glfw.get_video_mode(monitor)
        max_win_w = vm.size.width - 80
        max_win_h = vm.size.height - 80
    else:
        max_win_w, max_win_h = 1400, 900

    # The frame's padding and bars count only when the window opens framed.
    frame_w = PADDING * 2 if VIEW.show_frame else 0
    frame_h = PADDING * 2 + TITLE_H + HINT_H if VIEW.show_frame else 0
    desired_w = int(scene.width) + frame_w
    desired_h = int(scene.height) + frame_h + int(VIEW.prompt_bar_h)
    size = _initial_window_size(desired_w, desired_h, max_win_w, max_win_h)
    window = glfw.create_window(*size, md_path.name, None, None)
    if not window:
        glfw.default_window_hints()
        glfw.window_hint(glfw.STENCIL_BITS, 8)
        window = glfw.create_window(*size, md_path.name, None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError("glfw.create_window() failed")
    set_icon(window)

    native = None  # on macOS, a native control edits the bar's text
    if bar is not None:
        bar.paste = lambda: glfw.get_clipboard_string(window)
        native = attach_native_field(
            window, bar, lambda: send_prompt(), lambda: render()
        )
    glfw.make_context_current(window)
    context = skia.GrDirectContext.MakeGL()
    surface = make_surface(context, *glfw.get_framebuffer_size(window))

    image_cache.fetch(node_index, on_image_ready=glfw.post_empty_event)
    scroll = ScrollState()

    _resize_pending: float | None = None
    _last_regen: float = 0.0

    def clamp_scroll() -> None:
        cur_win_w, cur_win_h = glfw.get_window_size(window)
        _, _, _, vp_h = _viewport_metrics(cur_win_w, cur_win_h)
        pad = theme.root.padding
        la_w = _layout_width(cur_win_w, cur_win_h, theme)
        # Y document grows by top+bottom padding; viewport is la_w × vp_h.
        scroll.clamp(scene.width, scene.height + pad.y, la_w, vp_h)

    def regenerate_layout() -> None:
        nonlocal scene, title, block_offsets
        cur_win_w, cur_win_h = glfw.get_window_size(window)
        # The document's own minimum is memoised by session.effective_width on
        # the IDENTITY of (root, theme, fonts), so reload / reload_theme / drop
        # re-measure by handing over new objects — nothing here invalidates it.
        scene = session.build_scene(
            _gen,
            ast_root,
            node_index,
            theme,
            fonts,
            _layout_width(cur_win_w, cur_win_h, theme),
        )
        block_offsets = clamp_offsets(block_offsets, scene.scrollables)
        title = _title()

    def layout_is_current() -> bool:
        """True when the window's width would build the scene already shown —
        so a height-only resize, or one above ``Max width``, rebuilds nothing."""
        cur_win_w, cur_win_h = glfw.get_window_size(window)
        asked = _layout_width(cur_win_w, cur_win_h, theme)
        return session.effective_width(ast_root, theme, fonts, asked) == scene.width

    def reload() -> None:
        """Regroup the document from disk (watcher / R / drop).

        A save is the agent's next response: it replaces whatever the host
        showed meanwhile, so the node states clear. The scroll stays — the agent
        re-sending its answer must not jump the page; only a drop resets it.
        """
        nonlocal ast_root, node_index, _md_mtime, load_count
        _md_mtime = _mtime(md_path)
        load_count += 1
        print("[reload] regrouping the document…")
        fresh = load_document()
        if fresh is None:
            return
        ast_root, node_index = fresh
        VIEW.node_states = {}
        image_cache.fetch(node_index, on_image_ready=glfw.post_empty_event)
        regenerate_layout()
        clamp_scroll()

    def export_layout() -> None:
        """Write the current generated layout AST to JSON next to the document
        (layout-dump-<width>.json) — a debug dump."""
        out_path = md_path.resolve().parent / f"layout-dump-{int(scene.width)}.json"
        out_path.write_text(
            json.dumps(scene.layout.to_dict(), indent=4), encoding="utf-8"
        )
        print(f"[export] saved layout to {out_path}")

    def reload_theme() -> None:
        nonlocal theme, background_images
        theme = session.load_theme(theme_path)
        background_images = load_background_images(theme)
        # The toggles are seeded from the theme, so a reload drops any override
        # and puts them back in step with the file — including a --bento given
        # on the command line, which is the same kind of seed.
        _gen.bento_override = None
        _gen.pack_unique_override = None
        print(
            f"[theme] reloaded {theme_path}"
            if theme_path
            else "[theme] no THEME.md found, using defaults"
        )

    # Recorded once per scene, replayed every frame (ADR-401): a scroll or a
    # resize replays it; a new scene, theme, image or document toggle records.
    document = DocumentPicture()
    image_generation = 0

    def drain_images() -> None:
        """Take any images that landed; one re-record per tick, however many."""
        nonlocal image_generation
        if image_cache.drain_pending(context):
            image_generation += 1

    def _draw(canvas, win_w: int, win_h: int, scroll_state, dpr: float) -> None:
        VIEW.pixel_ratio = dpr  # photos are decoded for the pixels they land on
        draw_scene(
            canvas,
            document.document(
                scene.boxes,
                scene.sections,
                node_index,
                scene.width,
                scene.height,
                fonts,
                image_cache,
                theme,
                scene.layout,
                background_images,
                image_generation,
            ),
            scene.width,
            scene.height,
            title,
            fonts.typeface,
            win_w,
            win_h,
            scroll_state,
            theme,
            dpr,
            background_images,
            overlay=lambda c: paint_scrolled(
                c,
                scene.scrollables,
                block_offsets,
                hovered_block,
                node_index,
                fonts,
                theme,
                background_images,
            ),
        )
        if bar is not None and VIEW.prompt_bar_h:
            bar.draw(canvas, win_w, win_h)
            if working is not None and bar.locked:
                vp_x, vp_y, vp_w, vp_h = _viewport_metrics(win_w, win_h)
                working.draw(
                    canvas,
                    vp_x + vp_w / 2,
                    vp_y + vp_h / 2,
                    bar.style.working_size,
                    time.monotonic(),
                )
                below = vp_y + vp_h / 2 + bar.style.working_size / 2 + 8
                bar.draw_step(canvas, vp_x + vp_w / 2, below, vp_w)

    def render() -> None:
        """Draw the current scene into the GL surface and swap buffers."""
        nonlocal surface
        drain_images()
        cur_fb_w, cur_fb_h = glfw.get_framebuffer_size(window)
        cur_win_w, cur_win_h = glfw.get_window_size(window)
        dpr = cur_fb_w / cur_win_w if cur_win_w > 0 else 1.0
        # Whichever GLFW event a display change sent, and in whatever order (app_surface).
        surface = fitted(
            surface, cur_fb_w, cur_fb_h, lambda w, h: make_surface(context, w, h)
        )
        if native is not None:
            native.sync(cur_win_w, cur_win_h)
        with surface as canvas:
            _draw(canvas, cur_win_w, cur_win_h, scroll, dpr)
        surface.flushAndSubmit()
        glfw.swap_buffers(window)

    def document_image() -> skia.Image | None:
        """The WHOLE layout (full content), not just the visible viewport.

        Renders the entire layout off-screen at the window's device-pixel ratio into a
        GPU render-target surface — so the already-uploaded GPU images draw correctly —
        with the chrome frame off and no scroll. Mirrors the headless ``md2ui render``
        output, and replays the same recorded document the window does. None when the
        surface would exceed the GPU limit.
        """
        drain_images()
        cur_win_w, _cur_win_h = glfw.get_window_size(window)
        cur_fb_w, _cur_fb_h = glfw.get_framebuffer_size(window)
        dpr = cur_fb_w / cur_win_w if cur_win_w > 0 else 1.0
        # Full content extent = layout + root padding (both axes), like headless.
        pad = theme.root.padding
        win_w_l = int(math.ceil(scene.width + pad.x))
        win_h_l = int(math.ceil(scene.height + pad.y))
        shot = skia.Surface.MakeRenderTarget(
            context,
            skia.Budgeted.kNo,
            skia.ImageInfo.MakeN32Premul(
                max(1, int(win_w_l * dpr)), max(1, int(win_h_l * dpr))
            ),
        )
        if shot is None:
            print(
                f"[screenshot] full-content surface {win_w_l}×{win_h_l}@{dpr:g}x "
                "exceeds the GPU limit; not saved"
            )
            return None
        prev_frame, prev_bar = VIEW.show_frame, VIEW.prompt_bar_h
        VIEW.show_frame = False  # layout fills the surface; no chrome/scrollbars
        VIEW.prompt_bar_h = 0.0  # nor the prompt bar
        try:
            with shot as canvas:
                _draw(canvas, win_w_l, win_h_l, ScrollState(), dpr)
            shot.flushAndSubmit()
            img = shot.makeImageSnapshot()
        finally:
            VIEW.show_frame, VIEW.prompt_bar_h = prev_frame, prev_bar
        render()  # repaint the on-screen (framed) view
        return img

    def save_screenshot() -> None:
        """What ``S`` saves: the whole layout, in ``screenshots/``."""
        session.save_png(document_image(), _screenshot_path(md_path, scene.width))

    def copy_markdown(save: bool) -> None:
        """What ``C`` copies, and ``Shift+C`` saves beside the document: the
        Markdown on screen — the file, or the agent's answer in a connected window."""
        text = (
            wire_text if client is not None else md_path.read_text(encoding="utf-8")
        ) or ""
        if save:
            path = _markdown_save_path(md_path)
            path.write_text(text, encoding="utf-8")
            print(f"[markdown] saved {path}")
        else:
            glfw.set_clipboard_string(window, text)
            print(f"[markdown] {len(text)} characters to the clipboard")

    def answer_capture(request) -> None:
        """What the agent asked for (``app_capture``): the window as the user has
        it, or the whole document — the same two captures, one of them shared
        with ``S``, so what the agent checks is what the user is looking at."""
        image = (
            viewport_image(context, window, _draw, scroll)
            if request.mode == "view"
            else document_image()
        )
        assert capture is not None
        capture.answer(request, image)

    def resized(*_event) -> None:
        """A framebuffer resize or a content-scale change: ``render`` fits the
        surface; the layout follows only a change of width in points."""
        nonlocal _resize_pending, _last_regen
        follow_backing()
        now = time.monotonic()
        _resize_pending = now
        clamp_scroll()
        if not layout_is_current() and now - _last_regen >= RESIZE_REGEN_THROTTLE:
            _last_regen = now
            regenerate_layout()
        render()

    def block_under(mx: float, my: float):
        point = content_point(mx, my)
        return scrollable_at(scene.scrollables, *point) if point else None

    def scroll_callback(_win, xoffset: float, yoffset: float) -> None:
        nonlocal block_offsets
        shift = any(
            glfw.get_key(window, key) == glfw.PRESS
            for key in (glfw.KEY_LEFT_SHIFT, glfw.KEY_RIGHT_SHIFT)
        )
        under = block_under(*glfw.get_cursor_pos(window))
        target = latch.target_for(under.node_id if under else None, time.monotonic())
        block = next((s for s in scene.scrollables if s.node_id == target), None)
        block_dx, block_dy, page_dx, page_dy = split_scroll(
            xoffset, yoffset, shift, block is not None
        )
        if block is not None and (block_dx or block_dy):
            block_offsets = scrolled_by(
                block_offsets, block.node_id, block_dx, block_dy, scene.scrollables
            )
        scroll.pan(page_dx, page_dy)
        clamp_scroll()
        render()

    def relayout() -> None:
        regenerate_layout()
        clamp_scroll()
        render()

    def send_prompt() -> None:
        """Enter or Send: the field's text goes to the agent, as the user's words."""
        if bar is None or client is None:
            return
        text = bar.submit()
        if not text:
            return
        try:
            client.send_prompt(text)
        except FrameError as exc:
            print(f"[prompt] not sent: {exc}")
            return
        bar.sent("message")
        print(f"[prompt] sent {len(text)} characters")

    def key_callback(_win, key, _scancode, action, _mods) -> None:
        if action not in (glfw.PRESS, glfw.REPEAT):
            return
        if bar is not None and bar.focused:
            if bar.on_key(key, _mods) == "send":
                send_prompt()
            render()
            return
        pressed = action == glfw.PRESS
        # A demo window is the user's side of a conversation: it closes on purpose.
        if key == glfw.KEY_ESCAPE and client is None:
            glfw.set_window_should_close(_win, True)
        elif key == glfw.KEY_R and pressed:
            reload()
            render()
        elif key == glfw.KEY_T and pressed:
            reload_theme()
            regenerate_layout()  # section padding/spacing may have changed
            render()
        elif key == glfw.KEY_E and pressed:
            export_layout()
        elif key == glfw.KEY_W and pressed:
            VIEW.wireframe = not VIEW.wireframe
            render()
        elif key == glfw.KEY_D and pressed:
            VIEW.debug_spacing = not VIEW.debug_spacing
            render()
        elif key == glfw.KEY_P and pressed:
            VIEW.debug_padding = not VIEW.debug_padding
            render()
        elif key == glfw.KEY_B and pressed:
            VIEW.text_boxes = not VIEW.text_boxes
            render()
        elif key == glfw.KEY_I and pressed:
            VIEW.placeholder_images = not VIEW.placeholder_images
            render()
        elif key == glfw.KEY_F and pressed:
            VIEW.show_frame = not VIEW.show_frame
            relayout()
        elif key == glfw.KEY_S and pressed:
            save_screenshot()
        elif key == glfw.KEY_C and pressed:
            copy_markdown(save=bool(_mods & glfw.MOD_SHIFT))
        elif key == glfw.KEY_G and pressed:
            # Flip whatever is in force. The theme seeds the state, so on/off is
            # the whole cycle; T puts it back in step with the file.
            _gen.bento_override = not _gen.bento_requested
            print(f"[bento] {_toggle_state(_gen.bento_requested)}")
            relayout()
        elif key == glfw.KEY_K and pressed:
            # Inert while bento is on, and it does not flip the state quietly
            # either: the frame hides stacking there, so a change nobody can see
            # would only surprise whoever turns bento back off with G.
            if _gen.bento_requested:
                print("[stack sections] bento tiles first — turn it off with G")
            else:
                _gen.pack_unique_override = not _gen.pack_unique_requested
                print(f"[stack sections] {_toggle_state(_gen.pack_unique_requested)}")
                relayout()
        elif key == glfw.KEY_UP:
            scroll.pan(0, -SCROLL_SPEED)
            clamp_scroll()
            render()
        elif key == glfw.KEY_DOWN:
            scroll.pan(0, SCROLL_SPEED)
            clamp_scroll()
            render()
        elif key == glfw.KEY_LEFT:
            scroll.pan(-SCROLL_SPEED, 0)
            clamp_scroll()
            render()
        elif key == glfw.KEY_RIGHT:
            scroll.pan(SCROLL_SPEED, 0)
            clamp_scroll()
            render()
        elif key == glfw.KEY_HOME and pressed:
            scroll.reset()
            render()
        elif key in (glfw.KEY_PAGE_UP, glfw.KEY_PAGE_DOWN):
            cur_win_w, cur_win_h = glfw.get_window_size(window)
            _, _, _, vp_h = _viewport_metrics(cur_win_w, cur_win_h)
            direction = -1 if key == glfw.KEY_PAGE_UP else 1
            scroll.pan(0, direction * vp_h * 0.9)
            clamp_scroll()
            render()

    def drop_callback(_win, paths: list) -> None:
        nonlocal md_path
        if paths and str(paths[0]).endswith(".md"):
            md_path = Path(paths[0])
            print(f"[drop] switched to {md_path}")
            reload()
            scroll.reset()
            render()

    # Clicks (render_actions): md2ui reports WHAT was clicked, and this window is
    # the host that acts on it. A web or mail link opens the browser, any other
    # link is logged for a host router, an anchor scrolls, and an agent action
    # is printed as JSON for whatever drives this window to forward. The agent's
    # next response — a new save of the document — decides what is shown.
    hand_cursor = glfw.create_standard_cursor(glfw.HAND_CURSOR)
    hovering = False
    dragging: HitRegion | None = None

    def content_point(mx: float, my: float) -> tuple[float, float] | None:
        cur_win_w, cur_win_h = glfw.get_window_size(window)
        return window_to_content(
            mx, my, cur_win_w, cur_win_h, scene.width, theme, scroll
        )

    def action_at(mx: float, my: float) -> Action | None:
        point = content_point(mx, my)
        if point is None:
            return None
        return hit_test(scene.regions, *point, inert=inert_nodes(VIEW.node_states))

    def region_at(mx: float, my: float) -> HitRegion | None:
        point = content_point(mx, my)
        if point is None:
            return None
        return hit_region(scene.regions, *point, inert=inert_nodes(VIEW.node_states))

    def drag_action(region: HitRegion, mx: float, my: float) -> Action:
        point = content_point(mx, my)
        value = region.action.value or 0.0
        if point is not None:
            value = slider_value_in_rect(
                (region.x, region.y, region.width, region.height),
                theme,
                *point,
                region.action.value_decimals,
                region.action.value_max or 100.0,
            )
        VIEW.node_states[region.action.node_id] = value
        return dataclasses.replace(region.action, value=value)

    def dispatch(action: Action) -> None:
        # The host's transient state: a tick or a choice shows at once, an agent
        # action waits drawn disabled. The agent's answer replaces them (reload, show).
        action = show_locally(action, targets, VIEW.node_states)
        event = action.to_dict()
        if action.kind == "anchor":
            y = scene.anchors.get((action.href or "#")[1:])
            if y is None:
                print(f"[anchor] no heading {action.href}")
                return
            scroll.y = y + theme.root.padding.top
            clamp_scroll()
            render()
        elif action.kind == "copy":
            # The host's own job, like an anchor: the agent is never told.
            glfw.set_clipboard_string(window, action.text or "")
            print(f"[copy] {len(action.text or '')} characters to the clipboard")
        elif action.kind in SENT:
            event["message_id"] = wire_id or f"{md_path.name}#{load_count}"
            x = ordinal_of(targets, action.node_id)
            if (
                action.value is not None
                and x is not None
                and sent_values.get(x) == action.value
            ):
                print(f"[{action.kind}] unchanged at {action.value:g}, not sent")
                return
            if client is not None and wire_id is not None and x is not None:
                if action.value is not None:
                    sent_values[x] = action.value
                event["wire"] = client.send_event(
                    wire_id,
                    x,
                    action.action,
                    action.checked,
                    action.value,
                    settled_values(x) if action.commit else None,
                )
                if bar is not None:  # a click a commit press reports waits for no one
                    bar.sent("click", x=None if commit_carries(action, targets) else x)
            print(f"[{action.kind}] {json.dumps(event)}")
        else:
            print(f"[link] {json.dumps(event)}")
            href = action.href or ""
            if href.lower().startswith(("http://", "https://", "mailto:")):
                webbrowser.open(href)
        if action.node_id in VIEW.node_states:
            render()

    def connected() -> bool:
        """False once a connected window's server is gone: nothing is sent, and a
        click changes nothing on the page, so what it shows stays true."""
        return client is None or client.connected

    def settled_values(fired: int) -> list[list] | None:
        """What the rest of the document is set to, for a button that commits it.

        Only a button the AUTHOR marked `?md2ui.commit=1` carries this. The
        client cannot tell a press that means "keep this" from one that means
        "discard it", and a Cancel that quietly carried the cart would be worse
        than the turn it saved. Only the numbers and the ticks travel; the
        server still owns every label and slug.
        """
        rows = settled_rows(targets, VIEW.node_states, fired)
        return rows[:MAX_SETTLED] or None

    def mouse_button_callback(_win, button: int, press: int, _mods) -> None:
        nonlocal dragging
        if button != glfw.MOUSE_BUTTON_LEFT:
            return
        mx, my = glfw.get_cursor_pos(window)
        if press == glfw.RELEASE and dragging is not None:
            action = drag_action(dragging, mx, my)
            dragging = None
            dispatch(action)
            return
        if press != glfw.PRESS:
            return
        if bar is not None:
            where = bar.hit(mx, my, *glfw.get_window_size(window))
            was = bar.focused
            bar.focused = where in ("field", "send")
            if native is not None and where != "send":
                native.focus() if where == "field" else native.blur()
            if where == "send":
                send_prompt()
            if where is not None or was != bar.focused:
                render()
            if where is not None or bar.locked:
                return  # the bar's, or the agent is working on the last input
        region = region_at(mx, my)
        if region is not None and region.action.kind in SENT and not connected():
            print(f"[{region.action.kind}] not sent: disconnected")  # the bar says so
            return
        if region is not None and region.step:  # a count's ➖ or ➕
            if (step := stepped(region, VIEW.node_states)) is not None:
                dispatch(step)
        elif region is not None and region.action.value is not None:
            dragging = region
            drag_action(region, mx, my)
            render()
        elif region is not None:
            dispatch(region.action)

    def char_callback(_win, codepoint: int) -> None:
        if bar is not None and bar.on_char(codepoint):
            render()

    def cursor_pos_callback(_win, mx: float, my: float) -> None:
        nonlocal hovering, hovered_block
        if dragging is not None:
            drag_action(dragging, mx, my)
            render()
            return
        block = block_under(mx, my)
        if (block.node_id if block else None) != hovered_block:
            hovered_block = block.node_id if block else None
            render()  # the block's thumb shows while the pointer is over it
        over = action_at(mx, my) is not None
        # Set again on every move over an action, not only when it starts: macOS
        # drops the hand when the window moves to another display.
        if over != hovering or over:
            hovering = over
            # None restores the default arrow (GLFW's NULL); glfw 2.11's stub omits it.
            glfw.set_cursor(window, hand_cursor if over else None)  # pyright: ignore[reportArgumentType]

    glfw.set_framebuffer_size_callback(window, resized)
    glfw.set_window_content_scale_callback(window, resized)
    glfw.set_mouse_button_callback(window, mouse_button_callback)
    glfw.set_cursor_pos_callback(window, cursor_pos_callback)
    glfw.set_scroll_callback(window, scroll_callback)
    glfw.set_key_callback(window, key_callback)
    glfw.set_char_callback(window, char_callback)
    # The wrapper calls back with (window, paths); glfw 2.11's stub types the raw C callback.
    glfw.set_drop_callback(window, drop_callback)  # pyright: ignore[reportArgumentType]

    def show(incoming) -> None:
        """A message from the wire: the agent's next response. A replacement
        (``r``) is the same view with its state changed, so the scroll stays,
        and so do the user's clicks the agent has not answered yet."""
        nonlocal wire_text, wire_id
        before, states, was = targets, VIEW.node_states, wire_text or ""
        wire_text, wire_id = incoming.markdown, incoming.message_id
        reload()
        if incoming.replaces is None:
            scroll.reset()
        else:
            VIEW.node_states = carried_states(
                before, targets, states, was, incoming.markdown
            )
        render()

    def resend_stale() -> None:
        """Clicks the agent's replacement overtook go again, to the message now
        on screen, while the window still shows them (ADR-601)."""
        assert client is not None and wire_id is not None
        for event in client.resend_stale(wire_id, targets, VIEW.node_states):
            if "v" in event:
                sent_values[event["x"]] = event["v"]
            print(f"[wire] re-sent {json.dumps(event)}")
            if bar is not None:
                bar.lock_for_reply()

    if client is not None:
        client.on_ready = glfw.post_empty_event

    # Regenerate with actual window width now that the window exists
    regenerate_layout()
    render()

    while not glfw.window_should_close(window):
        # While the agent works its animation plays, so the loop ticks at 60 Hz;
        # otherwise it waits for an event as before.
        animating = working is not None and bar is not None and bar.locked
        glfw.wait_events_timeout(1 / 60 if animating else 0.05)
        if bar is not None:
            bar.composing()

        # Debounced layout regeneration after resize (final settle)
        if (
            _resize_pending is not None
            and time.monotonic() - _resize_pending >= RESIZE_DEBOUNCE
        ):
            _resize_pending = None
            if not layout_is_current():
                _last_regen = time.monotonic()
                regenerate_layout()
                render()

        # Document watcher: regroup when the Markdown is saved, or when the wire
        # delivers a message. Shares this tick — the wire's thread only talks.
        if client is not None:
            for incoming in client.poll():
                show(incoming)
            answered = client.answered()  # the agent listens again: they are done
            if answered:
                VIEW.node_states = released(targets, VIEW.node_states, answered)
                if bar is not None:
                    bar.notice.release(answered)
                render()
            resend_stale()
            if bar is not None and bar.sync(
                client.state, client.state_seq, said=client.said
            ):
                render()
        elif _mtime(md_path) != _md_mtime:
            reload()
            render()

        # The agent asking what the user sees. Polled here rather than pushed,
        # because this loop already wakes at least every 50 ms.
        if capture is not None:
            request = capture.pending()
            if request is not None:
                answer_capture(request)

        if animating or image_cache.has_pending():
            render()

    image_cache.close()
    context.abandonContext()
    glfw.terminate()
