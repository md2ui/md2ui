"""Whether md2ui may reach the network for assets: one switch for every fetch.

The app and the CLI fetch what a document and its theme name — content images,
theme backgrounds, theme fonts. A server must not (ADR-602): it knows the content,
not the look, and a URL written into Markdown by a model must never become a request
from inside the server's network. Fonts and
images a server's previews need are installed with it, by its developer.

So every fetch site asks this module: ``fetch_remote`` for the plain GETs, and
``POLICY.remote`` where a site keeps its own request. A server turns it off once,
at start, before anything is rendered or cached. Local files named by the THEME.md
the server was configured with are unaffected — that theme is the user's own
design system, not model input.
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class FetchPolicy:
    remote: bool = True
    """http(s) fetches for images, theme backgrounds and theme fonts."""


POLICY = FetchPolicy()
"""The one instance. Read through the object, never copy the field out."""


def fetch_remote(url: str, timeout: float = 10.0) -> bytes | None:
    """GET an http(s) URL; None when the policy forbids it or the URL is not one.

    Network errors propagate to the caller.
    """
    if not POLICY.remote or not url.startswith(("http://", "https://")):
        return None
    # Imported here, as image_cache does: the HTTP client slows every start, and
    # most documents fetch nothing.
    import urllib.request

    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()
