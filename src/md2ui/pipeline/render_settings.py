"""Display state the app shell sets and the painting code reads.

Ten values that answer "how is this window currently being shown" — the
overlay toggles, the chrome, the placeholder images. They are not
layout, not theme and not content: the same document renders differently
through them, and every one of them is set from OUTSIDE the drawing code, by
``main`` or a key handler.

**Why they are an object and not module-level names.** A module-level name
works only while the writer and every reader are in one module. Once a reader
moves out, ``from layout_render import WIREFRAME`` binds the VALUE at import
time and never sees another write — silently, because rebinding a name is not
an error. No test and no import contract sees that; only the byte comparison of
renders does. On one object, importers bind the object, mutations are attribute
writes, and every reader sees them however the modules are divided.

**The placeholder images are here for a sharper version of the same reason.**
Writing them into another module's namespace through ``globals()[attr] = img``
is a DYNAMIC write that no static check can see (not ruff, not pyright). The
loader belongs to the app shell, so such a write would land in the shell's
namespace and every painting call would read ``None``, drawing the fallback
cross instead of the placeholder — invisibly to the render snapshot, because
placeholders only appear for an image that is loading, failed, or forced.
"""

from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass
class ViewSettings:
    """How the current window is being shown. One instance: :data:`VIEW`."""

    # --- overlays, all toggled by a key and by a CLI flag ------------------
    wireframe: bool = False
    """Draw original BOX_FILL + BOX_STROKE on leaf boxes (visual comparison)."""

    debug_spacing: bool = False
    """The spacing-gap overlay: element/group/image + section gaps. Key D."""

    debug_padding: bool = False
    """The padding-ring overlay: root/section/card content padding. Key P."""

    text_boxes: bool = False
    """The real (tight, full-extent) text box of each text leaf. Key B."""

    placeholder_images: bool = False
    """Force ALL images to their placeholder. Key I."""

    pixel_ratio: float = 1.0
    """Device pixels per layout pixel the document is shown at. A photo is held
    decoded at the size it lands on the device, so the recording reads it."""

    # --- window chrome ----------------------------------------------------
    show_frame: bool = False
    """Draw the title/path and hint bars; off by default, so a window opens on the
    document alone. Off = the layout fills the window,
    which is what a headless screenshot always wants. Key F."""

    stack_key_hint: str = "  |  K stack"
    """The `Stack sections` entry in the hint bar, emptied while bento is on —
    bento tiles a container before the stacking flow is ever asked, so the key
    is not offered when pressing it could not change the picture."""

    quit_key_hint: str = "  |  ESC quit"
    """The quit entry in the hint bar, emptied in a connected window, where Esc
    does not close it: that window closes only on purpose (ADR-602)."""

    prompt_bar_h: float = 0.0
    """Height of the prompt bar a connected window docks at its bottom edge
    (ADR-601); 0 without one. The viewport ends above it, so the document and its
    scroll never run under the bar. Not part of a recording: it changes the
    viewport's height, never the document."""

    # --- placeholder images, decoded once by session.load_placeholders -----
    placeholder_raster: Any = None
    """The raster image drawn for an image that is loading, or forced to a
    placeholder by the I key. A ``skia.Image`` or None (typed loosely so this
    module stays free of the drawing library); None falls back to
    ``draw_image_box``'s cross."""

    placeholder_vector: Any = None
    """The vector placeholder, same rules as :attr:`placeholder_raster`."""

    placeholder_broken: Any = None
    """The image drawn for an image that failed to load, content image or photo
    card alike; same rules as :attr:`placeholder_raster`."""

    # --- host state, set by the window's click handling --------------------
    node_states: dict[str, str | float] = dataclasses.field(default_factory=dict)
    """What the host shows for a node until the agent's next response, by node id:
    ``"pending"`` / ``"disabled"`` draw a link disabled and make it report
    nothing; ``"checked"`` / ``"unchecked"`` are an optimistic tick; a float
    is a slider's optimistic 0–100 value. None changes its box
    (render_actions.with_node_states). A reload clears it: the re-sent Markdown
    is the state from then on. A replacement keeps what it left unanswered
    (wire_client.carried_states)."""


VIEW = ViewSettings()
"""The one instance. Import the OBJECT (``from ... import VIEW``) and read
through it; never copy a field out into a module-level name, which reintroduces
exactly the stale-binding bug this module exists to prevent."""
