"""Starting an MCP server switches two process-wide settings: ``build_server``
turns remote fetching off and draws pictures as placeholders, as a real server
process should. Every test module runs in one process (``scripts/run_tests.py``),
so a test that starts a server and leaves them switched breaks whichever later
test needs a fetch or a real picture, and nothing else resets them.

``restores_server_policy`` wraps a test so both settings are put back as they were,
however the test ends. A module whose tests start a server wraps its TESTS list.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

from md2ui.pipeline.render_settings import VIEW
from md2ui.utils.fetch_policy import POLICY


def restores_server_policy(test: Callable[[], None]) -> Callable[[], None]:
    """*test*, leaving ``POLICY.remote`` and ``VIEW.placeholder_images`` as it found them."""

    @functools.wraps(test)
    def run() -> None:
        saved = POLICY.remote, VIEW.placeholder_images
        try:
            test()
        finally:
            POLICY.remote, VIEW.placeholder_images = saved

    return run
