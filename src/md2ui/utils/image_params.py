"""An image literal's URL and its ``?md2ui.*`` params, read as plain text.

Pure string work, kept apart from the image cache so a stage that only needs
to READ a param (the grouper's kind tokens, the generator) never imports the
cache's skia, numpy and diskcache.
"""

import re
import urllib.parse

# ---------------------------------------------------------------------------
# md2ui image annotations (``?md2ui.<property>=<value>``)
# ---------------------------------------------------------------------------

# Namespace for author-supplied layout/render hints carried in an image URL's
# query string. The parsed dict feeds ``render_hints.render_properties_from``
# unchanged.
MD2UI_PREFIX = "md2ui."

# One query segment, INCLUDING its leading separator, so removal is textual and
# the surviving segments keep their original bytes: re-encoding a query (via
# parse_qsl + urlencode) rewrites ``+`` / ``%20`` / ``:`` and would invalidate a
# signed CDN URL whose signature covers the exact query string. Both ``?`` and
# ``&`` separate, so a param pasted onto a URL that already has a query works
# whichever one the author typed.
_QUERY_SEG_RE = re.compile(r"[?&][^?&]*")

_WHITESPACE_RE = re.compile(r"\s")


def split_md2ui_params(url: str) -> tuple[str, dict[str, str]]:
    """Split *url* into ``(url_without_md2ui_params, params)``.

    The returned URL is what gets fetched and cached, so a ``md2ui.*`` hint
    never reaches the network and never changes the cache key: the same photo
    annotated two different ways is downloaded and decoded once.

    Everything that is not a ``md2ui.`` param survives byte-for-byte — the
    segments are excised with their separators rather than re-encoded, and the
    first surviving separator is normalised back to ``?``. A URL with no
    ``md2ui.`` param (and any ``data:`` URI, whose payload may itself contain a
    ``?``) is returned unchanged.

    Values must not contain whitespace: ``_build_fingerprint`` counts words in a
    leaf's content, so a space inside a param would shift the node's length
    category. Whitespace-bearing values are dropped here rather than honoured.
    """
    if not url or MD2UI_PREFIX not in url:
        return url, {}
    if url[:5].lower() == "data:":
        return url, {}
    # The fragment is split off first so an SVG sprite id (``…#icon-name``)
    # survives untouched and is never scanned for params.
    head, frag_sep, frag = url.partition("#")
    qpos = head.find("?")
    if qpos < 0:
        return url, {}
    base, query = head[:qpos], head[qpos:]

    params: dict[str, str] = {}
    kept: list[str] = []
    for match in _QUERY_SEG_RE.finditer(query):
        segment = match.group(0)
        key, eq, val = segment[1:].partition("=")
        if not key.lower().startswith(MD2UI_PREFIX):
            kept.append(segment)
            continue
        name = key[len(MD2UI_PREFIX) :].lower()
        value = urllib.parse.unquote(val) if eq else ""
        if name and value and not _WHITESPACE_RE.search(value):
            params[name] = value

    if not params:
        # ``md2ui.`` appeared only in the path or the fragment.
        return url, {}
    if kept:
        kept[0] = "?" + kept[0][1:]
    return base + "".join(kept) + frag_sep + frag, params


# A copy of ``render_text.LINK_DESTINATION`` (utils may not import the pipeline);
# ``tests/layout_inline_link_tests.py`` pins the two equal.
_LINK_DESTINATION = (
    r"[ \t]*(?:(?:<[^<>\n]*>|(?:[^\s()<]|\([^\s()]*\))(?:[^\s()]|\([^\s()]*\))*)"
    r"""(?:[ \t]+(?:"[^"\n]*"|'[^'\n]*'|\([^()\n]*\)))?[ \t]*)?"""
)


def clean_image_url(url: str | None) -> str | None:
    """*url* with any ``md2ui.*`` params removed — the fetch / cache identity."""
    return None if url is None else split_md2ui_params(url)[0]


def destination_url(destination: str) -> str:
    """The url a link or image destination names: its CommonMark title and
    ``<…>`` brackets are spelling, not part of the address."""
    u = destination.strip()
    if u.startswith("<"):
        end = u.find(">")
        return u[1:end].strip() if end > 0 else ""
    return u.split(maxsplit=1)[0] if u else ""


def image_url(content: str) -> str | None:
    """The url of an ``![alt](url)`` literal, ``md2ui.*`` params included.

    Callers may pass this straight to :class:`ImageCache`, which strips the
    params itself; keeping them here is what lets the generator read them.
    An image with no picture, ``![alt]()``, has an empty one.
    """
    m = re.match(rf"!\[[^\]]*\]\(({_LINK_DESTINATION})\)", content)
    return destination_url(m.group(1)) if m else None


# Params only paint reads: not layout vocabulary, and not part of a picture's kind,
# so a run of pictures stays one run whichever placeholder each names.
PAINT_PARAMS = frozenset({"placeholder"})


def image_params(content: str) -> dict[str, str]:
    """The layout ``md2ui.*`` params of an ``![alt](url)`` literal, prefix stripped."""
    raw = image_url(content)
    params = split_md2ui_params(raw)[1] if raw else {}
    return {k: v for k, v in params.items() if k not in PAINT_PARAMS}


def url_layout_params(url: str) -> dict[str, str]:
    """The layout ``md2ui.*`` params of a bare *url*, prefix stripped."""
    params = split_md2ui_params(url)[1]
    return {k: v for k, v in params.items() if k not in PAINT_PARAMS}


def with_layout_params(url: str, params: dict[str, str]) -> str:
    """*url* carrying *params* as its layout ``md2ui.*`` params, in place of
    its own; its paint params and everything else are kept. How a run's polled
    params reach each member's own picture."""
    if url[:5].lower() == "data:":
        return url
    clean, own = split_md2ui_params(url)
    keep = {k: v for k, v in own.items() if k in PAINT_PARAMS} | params
    if not keep:
        return clean
    head, sep, frag = clean.partition("#")
    query = "&".join(
        f"{MD2UI_PREFIX}{k}={urllib.parse.quote(v, safe=':,@.')}"
        for k, v in keep.items()
    )
    return f"{head}{'&' if '?' in head else '?'}{query}{sep}{frag}"


def placeholder_ref(content: str) -> tuple[str, str] | None:
    """``(name, text)`` of an image's ``md2ui.placeholder=<name>`` or
    ``<name>:<text>``; the name as ``### Placeholders`` headings are named."""
    raw = image_url(content)
    value = split_md2ui_params(raw)[1].get("placeholder") if raw else None
    name, _, text = (value or "").partition(":")
    name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (name, text) if name else None


def image_alt(content: str) -> str:
    m = re.match(r"!\[([^\]]*)\]", content)
    return m.group(1) if m else "image"
