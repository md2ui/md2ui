from typing import List

import glfw  # type: ignore[import-untyped]
import skia  # type: ignore[import-untyped]

from md2ui.pipeline.layout_script_parser import LayoutBox, LayoutScriptParser

PADDING = 40
TITLE_HEIGHT = 30
HINT_HEIGHT = 25
BG_COLOR = skia.ColorWHITE
TEXT_COLOR = skia.ColorBLACK
BORDER_COLOR = skia.ColorBLACK
HINT_COLOR = skia.ColorSetARGB(255, 120, 120, 120)


def draw_layout(
    canvas: skia.Canvas,
    boxes: List[LayoutBox],
    width: float,
    height: float,
    title: str = "LayoutScript Visualization",
    show_dimensions: bool = True,
) -> None:
    """
    Draw layout boxes onto a skia Canvas.
    Clears the canvas first — safe to call repeatedly to update the view.
    """
    canvas.clear(BG_COLOR)

    typeface = skia.Typeface.MakeFromName("Arial", skia.FontStyle())
    title_font = skia.Font(typeface, 18)
    label_font = skia.Font(typeface, 13)
    hint_font = skia.Font(typeface, 12)
    text_paint = skia.Paint(Color=TEXT_COLOR, AntiAlias=True)
    hint_paint = skia.Paint(Color=HINT_COLOR, AntiAlias=True)

    info = f"{title}  |  Viewport: {int(width)}×{int(height)}  |  Boxes: {len(boxes)}"
    canvas.drawString(info, PADDING, TITLE_HEIGHT, title_font, text_paint)

    canvas.save()
    canvas.translate(PADDING, PADDING + TITLE_HEIGHT)

    for i, box in enumerate(boxes):
        rect = skia.Rect.MakeXYWH(box.x, box.y, box.width, box.height)

        canvas.drawRect(
            rect,
            skia.Paint(
                Color=skia.ColorSetARGB(255, 220, 220, 220),
                Style=skia.Paint.kFill_Style,
                AntiAlias=True,
            ),
        )
        canvas.drawRect(
            rect,
            skia.Paint(
                Color=BORDER_COLOR,
                Style=skia.Paint.kStroke_Style,
                StrokeWidth=2.0,
                AntiAlias=True,
            ),
        )

        if show_dimensions and box.width > 50 and box.height > 20:
            dim_text = f"{int(box.width)}×{int(box.height)}"
            text_w = label_font.measureText(dim_text)
            canvas.drawString(
                dim_text,
                box.x + (box.width - text_w) / 2,
                box.y + box.height / 2 + 5,
                label_font,
                text_paint,
            )

    canvas.restore()

    hint = "← → to navigate examples  |  ESC to quit"
    hint_w = hint_font.measureText(hint)
    total_w = int(width) + PADDING * 2
    total_h = int(height) + PADDING * 2 + TITLE_HEIGHT + HINT_HEIGHT
    canvas.drawString(
        hint,
        (total_w - hint_w) / 2,
        total_h - HINT_HEIGHT + 14,
        hint_font,
        hint_paint,
    )


def make_surface(context: skia.GrDirectContext, fb_w: int, fb_h: int) -> skia.Surface:
    """Create a skia GPU surface backed by the current GL framebuffer."""
    backend_render_target = skia.GrBackendRenderTarget(
        fb_w,
        fb_h,
        0,
        0,  # sampleCnt, stencilBits
        skia.GrGLFramebufferInfo(0, 0x8058),  # GL_RGBA8
    )
    surface = skia.Surface.MakeFromBackendRenderTarget(
        context,
        backend_render_target,
        skia.kBottomLeft_GrSurfaceOrigin,
        skia.kRGBA_8888_ColorType,
        skia.ColorSpace.MakeSRGB(),
    )
    assert surface is not None, "Failed to create skia GL surface"
    return surface


def main() -> None:
    layoutscript_simple = """
    layout[600:200]
     col[1:1]
      -
      row[1:1:1]
"""

    layoutscript_complex = """
layout[1920:1080]
  col[1:3:2]
    row[3:2:1]
      col
      col[2:1]
        row
        row
      row
    row[1:1]
    col[2:3]
      row[1:2:1]
        col
        col[3:1]
          row[1:1:1:1]
          row
        col
      col
"""

    layoutscript_mondrian = """
layout[1200:900]
  row[2:1]
    col[3:1]
      row[1:1:1]
    col[1:2]
      row[1:2]
"""

    parser = LayoutScriptParser()

    examples = [
        ("Example 1: Simple 2×2 Layout", layoutscript_simple),
        ("Example 2: Complex Nested Layout", layoutscript_complex),
        ("Example 3: Mondrian-style Layout", layoutscript_mondrian),
    ]

    parsed = []
    for title, script in examples:
        ast = parser.parse(script)
        w, h, boxes = parser.layout(ast)
        print(f"{title}: {int(w)}×{int(h)}, {len(boxes)} boxes")
        parsed.append((title, w, h, boxes))

    # --- glfw + skia GL setup ---
    if not glfw.init():
        raise RuntimeError("glfw.init() failed")

    glfw.window_hint(glfw.STENCIL_BITS, 8)

    title0, w0, h0, _ = parsed[0]
    init_w = int(w0) + PADDING * 2
    init_h = int(h0) + PADDING * 2 + TITLE_HEIGHT + HINT_HEIGHT

    window = glfw.create_window(init_w, init_h, f"LayoutScript — {title0}", None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError("glfw.create_window() failed")

    glfw.make_context_current(window)
    context = skia.GrDirectContext.MakeGL()

    fb_w, fb_h = glfw.get_framebuffer_size(window)
    surface = make_surface(context, fb_w, fb_h)
    current = 0

    def render() -> None:
        title, w, h, boxes = parsed[current]
        glfw.set_window_title(
            window, f"LayoutScript — {title}  ({current + 1}/{len(parsed)})"
        )
        with surface as canvas:
            draw_layout(canvas, boxes, w, h, title)
        surface.flushAndSubmit()
        glfw.swap_buffers(window)

    def framebuffer_size_callback(win, new_fb_w: int, new_fb_h: int) -> None:
        nonlocal surface, fb_w, fb_h
        fb_w, fb_h = new_fb_w, new_fb_h
        surface = make_surface(context, fb_w, fb_h)
        render()

    def key_callback(win, key, scancode, action, mods) -> None:
        nonlocal current
        if action == glfw.PRESS:
            if key in (glfw.KEY_RIGHT, glfw.KEY_SPACE):
                current = (current + 1) % len(parsed)
                render()
            elif key == glfw.KEY_LEFT:
                current = (current - 1) % len(parsed)
                render()
            elif key == glfw.KEY_ESCAPE:
                glfw.set_window_should_close(win, True)

    glfw.set_framebuffer_size_callback(window, framebuffer_size_callback)
    glfw.set_key_callback(window, key_callback)
    render()

    while not glfw.window_should_close(window):
        glfw.wait_events()  # Sleeps until an event — no busy loop

    context.abandonContext()
    glfw.terminate()


if __name__ == "__main__":
    main()
