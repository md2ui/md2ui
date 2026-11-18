"""Where a THEME.md's local asset paths point: its own folder first.

A theme names files — `## Fonts` entries, emoji `Font:` keys, and every
`Background image:`. Resolved against the process's working directory, a
relative one would point into the checkout (`uv --directory`) for the CLI and
for a plugin or extension alike, wherever the user's THEME.md lives, so a theme
kept in its own folder would lose the fonts beside it.

`resolve_theme_assets` rewrites each relative path to the file beside the
THEME.md when that file exists, and leaves it untouched otherwise, so it
resolves against the working directory. That fallback is deliberate: a
theme outside the checkout can keep naming the fonts the checkout ships
(`assets/fonts/...`) without copying them.

URLs and absolute paths are never touched. The paths are found by FIELD NAME —
`font_paths`, `font_path`, `bg_image` — anywhere in the parsed model, so a style
added later under an existing name is covered without an edit here. A new key
that names a file under a different field name must be added to `_PATH_FIELDS`.

A font file still missing after that -- every one, in an installed md2ui, which
ships no font -- is offered to `replace_missing_fonts`, whose caller knows where
else a font can be had (the session: the locked fonts' per-user cache).

Runs once per theme load (`session.load_theme`), after parsing and before
anything opens a file, so every consumer reads the one resolved string.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path
from typing import Any

from md2ui.pipeline.theme_model import Theme

_PATH_FIELDS = frozenset({"font_paths", "font_path", "bg_image"})
_FONT_FIELDS = frozenset({"font_paths", "font_path"})


def resolve_asset(value: str, theme_dir: Path) -> str:
    """*value* as the file beside the theme, when it is a relative local path
    that exists there; otherwise *value* unchanged."""
    if value.startswith(("http://", "https://")) or Path(value).is_absolute():
        return value
    beside = theme_dir / value
    return str(beside) if beside.is_file() else value


def resolve_theme_assets(theme: Theme, theme_path: Path) -> Theme:
    """Rewrite, in place, every asset path *theme* names against the folder of
    *theme_path*. Returns *theme*."""
    _walk(theme, _PATH_FIELDS, lambda v: resolve_asset(v, theme_path.parent), set())
    return theme


def replace_missing_fonts(theme: Theme, find: Callable[[str], str | None]) -> None:
    """Rewrite, in place, each local font file *theme* names that is not there
    to what *find* answers for it; a ``None`` answer leaves it as written.

    Runs after :func:`resolve_theme_assets`: what is still missing then was in
    neither the theme's folder nor the working directory.
    """

    def fix(value: str) -> str:
        if value.startswith(("http://", "https://")) or Path(value).is_file():
            return value
        return find(value) or value

    _walk(theme, _FONT_FIELDS, fix, set())


def _walk(
    node: Any, fields: frozenset[str], fix: Callable[[str], str], seen: set[int]
) -> None:
    if id(node) in seen:
        return
    seen.add(id(node))
    if isinstance(node, dict):
        for child in node.values():
            _walk(child, fields, fix, seen)
    elif isinstance(node, list):
        for child in node:
            _walk(child, fields, fix, seen)
    elif dataclasses.is_dataclass(node) and not isinstance(node, type):
        for field in dataclasses.fields(node):
            value = getattr(node, field.name)
            if field.name in fields:
                _fix_field(node, field.name, value, fix)
            else:
                _walk(value, fields, fix, seen)


def _fix_field(node: Any, name: str, value: Any, fix: Callable[[str], str]) -> None:
    if isinstance(value, str) and value:
        setattr(node, name, fix(value))
    elif isinstance(value, list):
        value[:] = [fix(v) if isinstance(v, str) and v else v for v in value]
