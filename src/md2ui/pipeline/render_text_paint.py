"""Paint mixed text and emoji runs with one background-aware color path.

The pure segmentation lives in :mod:`render_text`; this module owns the canvas
operation that consumes it. Keeping the pin resolver here makes prose, links,
and inline-code labels share the same fixed-color precedence.
"""

import skia  # type: ignore[import-untyped]

from md2ui.pipeline.render_colors import _pin_or_replace
from md2ui.pipeline.render_glyph_faces import font_runs, glyph_runs, runs_advance
from md2ui.pipeline.render_shaping import draw_run
from md2ui.pipeline.render_text import _emoji_clusters, bare_glyph, emoji_pin
from md2ui.pipeline.theme import Theme


def _text_advance(
    text: str, text_font: "skia.Font", emoji_tf: "skia.Typeface | None", size: float
) -> float:
    """Width of *text* using the same run faces as the painter below."""
    return runs_advance(text, text_font, emoji_tf, size)


# The pin table of one ``fixed_colors`` dict, keyed by its id. Every dict passed
# here belongs to a theme -- built while THEME.md is parsed, never edited after,
# and replaced by a reload -- and the table only depends on it, so it is built
# once per theme instead of once per text run. The entry keeps its dict alive, so no
# other dict can reuse the id. Emptied when full, which bounds a long app session's
# theme reloads.
_PIN_TABLES: dict[int, tuple[dict[str, int], dict[str, int], list[str]]] = {}
_PIN_TABLES_MAX = 64


def _pin_table(fixed_colors: dict[str, int]) -> tuple[dict[str, int], list[str]]:
    """Every pin keyed without its variation selector, and those keys longest
    first. A text run holds no variation selector, so a key is matched without
    its own (``⏷️`` pins ``⏷``); a key written bare wins over one that differs
    by it."""
    hit = _PIN_TABLES.get(id(fixed_colors))
    if hit is None:
        pins = {bare_glyph(k): v for k, v in fixed_colors.items()}
        pins.update((k, v) for k, v in fixed_colors.items() if bare_glyph(k) == k)
        # sorted() is stable, so the keys a run holds, filtered from this list,
        # come in the order sorting only those keys would give.
        keys = sorted((k for k in pins if k), key=len, reverse=True)
        if len(_PIN_TABLES) >= _PIN_TABLES_MAX:
            _PIN_TABLES.clear()
        hit = _PIN_TABLES[id(fixed_colors)] = (fixed_colors, pins, keys)
    return hit[1], hit[2]


def _pinned_pieces(
    run: str, fixed_colors: dict[str, int]
) -> list[tuple[int, int, int | None]]:
    """``run`` cut at every pinned key it holds, as ``(start, end, pin)``;
    empty when it holds none, so an unpinned run is drawn exactly as before."""
    pins, all_keys = _pin_table(fixed_colors)
    keys = [k for k in all_keys if k in run]
    if not keys:
        return []
    pieces: list[tuple[int, int, int | None]] = []
    plain = i = 0
    while i < len(run):
        key = next((k for k in keys if run.startswith(k, i)), None)
        if key is None:
            i += 1
            continue
        if plain < i:
            pieces.append((plain, i, None))
        pieces.append((i, i + len(key), pins[key]))
        i = plain = i + len(key)
    if plain < len(run):
        pieces.append((plain, len(run), None))
    return pieces


def _draw_runs(
    canvas: "skia.Canvas",
    text: str,
    x: float,
    y: float,
    text_font: "skia.Font",
    emoji_tf: "skia.Typeface | None",
    size: float,
    text_paint: "skia.Paint",
    emoji_color: int | None,
    fixed_colors: dict[str, int] | None,
    bg_stack: tuple[int | str, ...],
    theme: "Theme | None",
) -> float:
    """Draw the already-normalized text/emoji runs and return their advance."""
    run_x = x
    for run, ef, is_emoji in font_runs(text, text_font, emoji_tf, size):
        if not is_emoji:
            pieces = _pinned_pieces(run, fixed_colors) if fixed_colors else ()
            if not pieces:
                canvas.drawString(run, run_x, y, ef, text_paint)
            # A pin names a character, not an emoji, so a symbol drawn in the
            # text slot takes it too. Each piece is placed at its offset in the
            # whole run, so colour never changes an advance (ADR-400).
            for start, end, pin in pieces:
                paint = text_paint
                if pin is not None:
                    base = text_paint.getColor()
                    if theme is not None:
                        pin = _pin_or_replace(base, pin, bg_stack, theme)
                    paint = skia.Paint(Color=pin, AntiAlias=True)
                piece_x = run_x + ef.measureText(run[:start])
                canvas.drawString(run[start:end], piece_x, y, ef, paint)
            run_x += ef.measureText(run)
            continue
        if fixed_colors:
            for cluster in _emoji_clusters(run):
                fallback = (
                    emoji_color if emoji_color is not None else text_paint.getColor()
                )
                pin = emoji_pin(fixed_colors, cluster)
                color = (
                    _pin_or_replace(fallback, pin, bg_stack, theme)
                    if theme is not None
                    else (pin if pin is not None else fallback)
                )
                paint = skia.Paint(Color=color, AntiAlias=True)
                run_x += draw_run(canvas, cluster, run_x, y, ef, paint, True)
        else:
            paint = (
                skia.Paint(Color=emoji_color, AntiAlias=True)
                if emoji_color is not None
                else text_paint
            )
            run_x += draw_run(canvas, run, run_x, y, ef, paint, True)
    return run_x - x


def _draw_text_with_emoji(
    canvas: "skia.Canvas",
    text: str,
    x: float,
    y: float,
    text_font: "skia.Font",
    emoji_tf: "skia.Typeface | None",
    size: float,
    text_paint: "skia.Paint",
    *,
    emoji_color: int | None = None,
    fixed_colors: dict[str, int] | None = None,
    fixed_spans: tuple[tuple[int, int, int], ...] = (),
    bg_stack: tuple[int | str, ...] = (),
    theme: "Theme | None" = None,
) -> float:
    """Draw text at ``(x, y)``, routing emoji runs through their typeface.

    A fixed glyph color normally wins over its contextual tint. When it exactly
    matches the nearest background, the shared invisibility veto drops the pin
    and ordinary background-aware replacement runs instead.
    """
    advance = _draw_runs(
        canvas,
        text,
        x,
        y,
        text_font,
        emoji_tf,
        size,
        text_paint,
        emoji_color,
        fixed_colors,
        bg_stack,
        theme,
    )
    # Range pins are a paint-only overlay on the SAME normalized word at the
    # SAME origin. They never participate in measurement, so color cannot move
    # a glyph or change wrapping (ADR-400).
    metrics = text_font.getMetrics()
    for start, end, pin in fixed_spans:
        color = (
            _pin_or_replace(text_paint.getColor(), pin, bg_stack, theme)
            if theme is not None
            else pin
        )
        left = x + _text_advance(text[:start], text_font, emoji_tf, size)
        right = x + _text_advance(text[:end], text_font, emoji_tf, size)
        canvas.save()
        canvas.clipRect(
            skia.Rect.MakeLTRB(left, y + metrics.fAscent, right, y + metrics.fDescent)
        )
        _draw_runs(
            canvas,
            text,
            x,
            y,
            text_font,
            emoji_tf,
            size,
            skia.Paint(Color=color, AntiAlias=True),
            color,
            fixed_colors,
            bg_stack,
            theme,
        )
        canvas.restore()
    return advance


def draw_glyph_runs(
    canvas: "skia.Canvas",
    text: str,
    x: float,
    y: float,
    emoji_tf: "skia.Typeface | None",
    fallback_tf: "skia.Typeface",
    size: float,
    paint: "skia.Paint",
) -> float:
    """Draw a glyph on its own in ``glyph_runs``' fonts -- the faces
    ``glyph_advance`` measured it in -- and return its advance."""
    run_x = x
    for run, font in glyph_runs(text, emoji_tf, fallback_tf, size):
        run_x += draw_run(canvas, run, run_x, y, font, paint, emoji_tf is not None)
    return run_x - x
