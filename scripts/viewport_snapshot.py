"""Hash window-sized frames of every snapshot document at several scroll offsets.

The render snapshot paints each page whole, unscrolled and without the chrome, so
a change to what the WINDOW draws (the replay, the chrome, scrolling, host state)
is invisible to it. This paints what the window paints: the recorded document
replayed through ``draw_scene`` into a 1340x800 window.

For every ``.md`` under ``data/markdown/tests`` and ``data/markdown/tests-render``,
at widths 767 and 1280, with the frame on and off: dpr 1 at scroll y = 0, 1/3,
2/3 and max (plus max x when the document is wider than the viewport), dpr 2 at
the first two offsets. One ``path|width|frame|dpr|x,y sha256[:16]`` line each.

Run it before and after a change and ``diff`` the two files: silent means the
window shows exactly the same pixels.

usage: uv run python scripts/viewport_snapshot.py OUT.txt
"""

import contextlib
import hashlib
import io
import sys
from pathlib import Path

import skia

from md2ui import session
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_render import (
    _viewport_metrics,
    draw_scene,
    load_background_images,
)
from md2ui.pipeline.render_picture import record_document
from md2ui.pipeline.render_settings import VIEW
from md2ui.utils.image_cache import ImageCache
from md2ui.utils.scroll_state import ScrollState

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ("data/markdown/tests", "data/markdown/tests-render")
WIDTHS = (767, 1280)
WIN_W, WIN_H = 1340, 800


def _offsets(scene, theme) -> list[tuple[float, float]]:
    """The scroll offsets at dpr 1: four down the page, one at the far right."""
    _, _, vp_w, vp_h = _viewport_metrics(WIN_W, WIN_H)
    la_w = max(0.0, vp_w - theme.root.padding.x)
    max_y = max(0.0, scene.height + theme.root.padding.y - vp_h)
    max_x = max(0.0, scene.width - la_w)
    offsets = [(0.0, max_y * f) for f in (0, 1 / 3, 2 / 3, 1)]
    if max_x > 0:
        offsets.append((max_x, max_y / 2))
    return offsets


def _frame_hash(picture, scene, theme, fonts, bg, sx, sy, dpr: float) -> str:
    surface = skia.Surface(int(WIN_W * dpr), int(WIN_H * dpr))
    scroll = ScrollState()
    scroll.x, scroll.y = sx, sy
    draw_scene(
        surface.getCanvas(),
        picture,
        scene.width,
        scene.height,
        "title",
        fonts.typeface,
        WIN_W,
        WIN_H,
        scroll,
        theme,
        dpr,
        bg,
    )
    return hashlib.sha256(surface.makeImageSnapshot().tobytes()).hexdigest()[:16]


def _document_lines(doc: str, kit) -> list[str]:
    path = ROOT / doc
    with contextlib.redirect_stdout(io.StringIO()):
        theme = session.load_theme(session.resolve_theme_path(path, None))
        fonts = session.load_fonts(theme)
        ast = session.group_markdown(path.read_text(), kit)
        if ast is None:
            return []
        root, node_index = session.prepare(ast, theme)
        bg = load_background_images(theme)
    image_cache = ImageCache()
    lines: list[str] = []
    for width in WIDTHS:
        with contextlib.redirect_stdout(io.StringIO()):
            scene = session.build_scene(
                LayoutGenerator(), root, node_index, theme, fonts, width
            )
        picture = record_document(
            scene.boxes,
            scene.sections,
            node_index,
            scene.width,
            scene.height,
            fonts,
            image_cache,
            theme,
            scene.layout,
            bg,
        )
        for show in (True, False):
            VIEW.show_frame = show
            offsets = _offsets(scene, theme)
            for dpr in (1.0, 2.0):
                for sx, sy in offsets if dpr == 1.0 else offsets[:2]:
                    h = _frame_hash(picture, scene, theme, fonts, bg, sx, sy, dpr)
                    lines.append(
                        f"{doc}|w{width}|frame={int(show)}|dpr{dpr:g}|{sx:.0f},{sy:.0f} {h}"
                    )
    return lines


def main(out: str) -> None:
    docs = sorted(
        str(p.relative_to(ROOT)) for d in CORPORA for p in (ROOT / d).rglob("*.md")
    )
    with contextlib.redirect_stdout(io.StringIO()):
        kit = session.load_grouping_kit()
        session.load_placeholders()
    lines: list[str] = []
    try:
        for doc in docs:
            lines.extend(_document_lines(doc, kit))
            print(f"{doc}: done", file=sys.stderr)
    finally:
        VIEW.show_frame = True
    Path(out).write_text("\n".join(lines) + "\n")
    print(f"{len(lines)} frames over {len(docs)} documents -> {out}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
