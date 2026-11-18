"""Named image placeholders: what THEME.md declares under `## Images` → `### Placeholders`.

A placeholder stands in for a picture that is not there: left out, still loading or
failed. The default ones (render_placeholders) say only why there is no picture. A named
one is the author's: a fill, and centred in it the text the image names (`avatar:SZ`)
or the icon the placeholder declares (ADR-406).

    ## Images

    ### Placeholders

    #### Avatar
    Fill color:
    - #E8F0FE
    - #FDE7E9
    Text color: #1A56DB
    Text style: Lead
    Text size: 40%

    #### Media
    Fill color: #F2F2F2
    Icon: 🖼️
    Icon size: 30%

    #### Brand
    Image: assets/brand-pattern.png

    #### Broken
    Image: assets/broken.svg

The heading is the name an image writes (`?md2ui.placeholder=avatar:SZ`), lower-cased
and hyphenated as `### Fixed styles` names are. A colour key takes one colour, or a list
of `- #hex` bullets under it, which rotates like every other colour list. A size is a
share of the box's shorter side (`40%`) or pixels (`28`). An `Image:` (a path beside the
THEME.md, or an http(s) URL) is drawn cover-fitted over the fill, under the text or icon.

Three names are the defaults, in any order among the others: `#### Loading`, `#### Broken`
and `#### Missing` (the source left out) replace md2ui's own placeholders, in that state,
for every image that names none. An image cannot name them.
"""

from __future__ import annotations

import dataclasses
import re

# The share of the box's shorter side text and an icon take when the theme says nothing.
DEFAULT_TEXT_SIZE = (40.0, True)
DEFAULT_ICON_SIZE = (50.0, True)

_HEX = re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?")
_SIZE = re.compile(r"(\d+(?:\.\d+)?)\s*(%|px)?")


@dataclasses.dataclass
class ImagePlaceholder:
    """One named placeholder: its fill, and how the text or icon in it is drawn."""

    fill_colors: list[int] = dataclasses.field(default_factory=list)
    text_colors: list[int] = dataclasses.field(default_factory=list)
    text_style: str = "text"  # a text style THEME.md declares: Text, Lead, Heading 2…
    text_size: tuple[float, bool] = DEFAULT_TEXT_SIZE  # (value, is a percentage)
    icon: str = ""
    icon_size: tuple[float, bool] = DEFAULT_ICON_SIZE
    # `Image:`. Named bg_image so theme_assets resolves it beside the THEME.md.
    bg_image: str = ""


# The reserved placeholder names that restyle md2ui's own, by state: a picture still
# loading, one that failed, one whose source was left out.
DEFAULT_STATES = ("loading", "broken", "missing")


def placeholder_name(title: str) -> str:
    """The name an image writes for the placeholder headed *title*."""
    return re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")


def _color(text: str) -> int | None:
    """``#RRGGBB`` or ``#RRGGBBAA`` as a skia ARGB colour, as ``theme._hex_to_skia``
    reads it (that module imports this one, so it cannot be imported here)."""
    found = _HEX.fullmatch(text.strip())
    if not found:
        return None
    digits = found.group(0)[1:]
    rgb = int(digits[:6], 16)
    alpha = int(digits[6:8], 16) if len(digits) == 8 else 0xFF
    return (alpha << 24) | rgb


def _size(text: str) -> tuple[float, bool] | None:
    found = _SIZE.fullmatch(text.strip())
    return (float(found.group(1)), found.group(2) == "%") if found else None


class PlaceholderParser:
    """Reads the lines of `## Images` into ``placeholders``, one line at a time."""

    def __init__(
        self,
        placeholders: dict[str, ImagePlaceholder],
        defaults: dict[str, ImagePlaceholder],
    ) -> None:
        self.placeholders = placeholders
        self.defaults = defaults
        self._block = ""
        self._current: ImagePlaceholder | None = None
        self._list: list[int] | None = None

    def line(self, line: str) -> None:
        if line.startswith("### "):
            self._block = line[4:].strip().lower()
            self._current = self._list = None
            return
        if self._block != "placeholders":
            return
        if line.startswith("#### "):
            name = placeholder_name(line[5:])
            into = self.defaults if name in DEFAULT_STATES else self.placeholders
            self._current = into.setdefault(name, ImagePlaceholder())
            self._list = None
            return
        if self._current is None:
            return
        if line.startswith("- "):
            color = _color(line[2:])
            if color is not None and self._list is not None:
                self._list.append(color)
            return
        key, _, value = (part.strip() for part in line.partition(":"))
        self._key(self._current, key.lower(), value)

    def _key(self, ph: ImagePlaceholder, key: str, value: str) -> None:
        """One `Key: value` line; a colour key with no value opens a bullet list."""
        self._list = None
        if key in ("fill color", "fill colors", "text color", "text colors"):
            target = ph.fill_colors if key.startswith("fill") else ph.text_colors
            target.clear()
            color = _color(value)
            if color is not None:
                target.append(color)
            elif not value:
                self._list = target
        elif key == "text style" and value:
            ph.text_style = value.lower()
        elif key == "icon":
            ph.icon = value
        elif key == "image" and value:
            ph.bg_image = value
        elif key in ("text size", "icon size") and (size := _size(value)):
            if key == "text size":
                ph.text_size = size
            else:
                ph.icon_size = size
