"""Inline text parsing: turning marked-up text into spans and segments.

Owns two pure transformations the renderer needs before it can measure or draw
anything:

  * ``parse_inline_spans`` -- one ordered regex over a line of Markdown, producing
    the styled spans it contains (bold, italic, inline code, strikethrough,
    inline links, autolinks) with nesting resolved. Link alternatives are matched
    FIRST so a wrapped link is consumed whole;
  * emoji segmentation -- splitting text into emoji and non-emoji runs, and an
    emoji run into grapheme clusters, so each can be measured and drawn with the
    right typeface.

Owns no drawing and no measurement: every function takes text and returns text or
plain data. Emoji drawing lives in ``render_text_paint`` and typeface resolution
stays in the renderer, because both need concrete drawing resources.
"""

import re


# The link alternatives come FIRST so a wrapped link (``**[a](b)**``) is consumed
# whole — otherwise the bold/italic alternatives would eat the wrapper and leave
# the bare ``[a](b)`` markup behind. The wrapped forms mirror the variants
# markdown_grouper._classify_link_content recognizes on peeled LINK leaves, so an
# inline link and a peeled one read the same markup the same way. Only the label
# is drawn, and therefore only the label is measured; the URL (``…_h``) is kept
# for the click alone (``inline_link_urls``). The destination may be empty, which
# is how ``[↗️]()`` is written.
#
# A link's destination, the one definition every link, image and linked control
# pattern in the pipeline imports, so the grouper and the renderer agree on where
# a link ends. CommonMark allows balanced parentheses in it, so
# ``[x](https://en.wikipedia.org/wiki/POST_(HTTP))`` keeps its whole URL; one
# level is accepted. As in CommonMark, a bare destination holds no space: a
# space ends it, and only a title may follow (``"…"``, ``'…'`` or ``(…)``), so
# ``[a](/my file)`` is not a link and stays literal text. A destination that
# needs a space is written in angle brackets, ``[a](</my file>)``. A newline is
# never part of it, and it may be empty. Readers of the destination strip the
# title and the brackets themselves (``render_actions.action_for``). A site that
# needs a non-empty destination puts ``(?=[^)])`` in front of it.
# ``utils/image_params`` keeps a copy, since utils may not import the pipeline;
# a test pins the two equal.
LINK_DESTINATION = (
    r"[ \t]*(?:(?:<[^<>\n]*>|(?:[^\s()<]|\([^\s()]*\))(?:[^\s()]|\([^\s()]*\))*)"
    r"""(?:[ \t]+(?:"[^"\n]*"|'[^'\n]*'|\([^()\n]*\)))?[ \t]*)?"""
)
# An autolink's URI must carry a scheme (`https:`, `mailto:`, …): that colon is
# what keeps `<not-a-link>`, `<br>` and `<div class="x">` out of the link path.
_AUTOLINK_URI = r"[A-Za-z][A-Za-z0-9+.-]*:[^\s<>]+|[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+"
# A link's label, for every pattern that reads one. As in CommonMark, brackets
# inside it must balance, so ``[a] text [b](/c)`` is the link ``[b](/c)`` after
# the text ``[a] text``, never one link labelled ``a] text [b``; one level of
# nesting is accepted (``[a [nested] label](/c)``). An escaped bracket does not
# count.
LINK_LABEL = r"(?:\\.|[^\[\]\\]|\[(?:\\.|[^\[\]\\])*\])+"

# A "more" button's label: a link whose whole label is one of these is an icon
# button (md2ui's icon font draws them as more_horiz / more_vert), while the same
# character anywhere else stays text, as an ellipsis in a sentence must.
OVERFLOW_MARKS = frozenset("…⋯⋮")
# Inline, a nested pair may not open a destination of its own: a link inside a
# label is the link, and the outer brackets are text (``[a [b](/c) d](/e)``).
_LINK_LABEL = r"(?:\\.|[^\[\]\\]|\[(?:\\.|[^\[\]\\])*\](?!\())+"
# Named rather than positional: the alternation is ordered (longest wrapper
# first, links before bare emphasis); positional, an insertion would renumber
# every group and silently re-map the dispatch below. Names keep it local.
_INLINE_RE = re.compile(
    # An escaped star is the character, not markup (grouper_escapes.MARKUP_ESCAPES):
    # the one place its backslash is resolved, so measuring and painting agree.
    r"(?P<esc>\\\*)|"
    rf"(?P<bi_link>\*\*\*\[(?P<bi_link_t>{_LINK_LABEL})\]\((?P<bi_link_h>{LINK_DESTINATION})\))\*\*\*"
    rf"|(?P<b_link>\*\*\[(?P<b_link_t>{_LINK_LABEL})\]\((?P<b_link_h>{LINK_DESTINATION})\))\*\*"
    rf"|(?P<i_link>\*\[(?P<i_link_t>{_LINK_LABEL})\]\((?P<i_link_h>{LINK_DESTINATION})\))\*"
    # Underscore spellings — exact CommonMark synonyms of the three above.
    rf"|(?P<bi_link_u>___\[(?P<bi_link_u_t>{_LINK_LABEL})\]\((?P<bi_link_u_h>{LINK_DESTINATION})\))___"
    rf"|(?P<b_link_u>__\[(?P<b_link_u_t>{_LINK_LABEL})\]\((?P<b_link_u_h>{LINK_DESTINATION})\))__"
    rf"|(?P<i_link_u>_\[(?P<i_link_u_t>{_LINK_LABEL})\]\((?P<i_link_u_h>{LINK_DESTINATION})\))_"
    # Disabled link. The inner emphasis wrapper is optional and deliberately
    # discarded: inline disabled links draw as ordinary inline links until that
    # styling is decided, so all four spellings collapse to one plain link span
    # — no bold/italic, and no strike (`~~` on a link is a state, not a rule).
    rf"|~~(?:\*{{1,3}}|_{{1,3}})?\[(?P<d_link_t>{_LINK_LABEL})\]\({LINK_DESTINATION}\)(?:\*{{1,3}}|_{{1,3}})?~~"
    rf"|\[`(?P<code_link_t>{_LINK_LABEL})`\]\((?P<code_link_h>{LINK_DESTINATION})\)"  # backtick-label link
    rf"|(?<!!)\[(?P<link_t>{_LINK_LABEL})\]\((?P<link_h>{LINK_DESTINATION})\)"  # plain link ((?<!!) skips images)
    rf"|\*\*\*<(?P<bi_auto>{_AUTOLINK_URI})>\*\*\*"  # bold+italic autolink
    rf"|\*\*<(?P<b_auto>{_AUTOLINK_URI})>\*\*"  # bold-wrapped autolink
    rf"|\*<(?P<i_auto>{_AUTOLINK_URI})>\*"  # italic-wrapped autolink
    rf"|<(?P<auto>{_AUTOLINK_URI})>"  # autolink — URI drawn, brackets dropped
    # The `_` alternatives below are flanking-guarded and the `*` ones are not,
    # which is CommonMark, not an oversight: a `_` run between two alphanumerics
    # is INTRAWORD and can neither open nor close, so `snake_case_name` is
    # literal text and `_the user_id field_` emphasises the whole span with the
    # identifier intact. Intraword `*` really is emphasis, so it stays unguarded.
    # A closer is never an escaped star: `*a\*` draws `*a*`, not an italic `a`.
    r"|\*\*\*(?P<bi_a>.+?)(?<!\\)\*\*\*"  # bold+italic ***
    r"|(?<![0-9A-Za-z])___(?P<bi_u>.+?)___(?![0-9A-Za-z])"  # bold+italic ___
    r"|\*\*(?P<b_a>.+?)(?<!\\)\*\*"  # bold **
    r"|(?<![0-9A-Za-z])__(?P<b_u>.+?)__(?![0-9A-Za-z])"  # bold __
    r"|\*(?P<i_a>.+?)(?<!\\)\*"  # italic *
    r"|(?<![0-9A-Za-z])_(?P<i_u>.+?)_(?![0-9A-Za-z])"  # italic _
    r"|~~(?P<strike>.+?)~~"  # strikethrough
    r"|`(?P<code>.+?)`",  # inline code
    re.DOTALL,
)
# A label is drawn as written, not parsed again, so its escaped stars are resolved
# on their own; a backtick label is a code span and keeps them.
_ESCAPED_STAR = re.compile(r"\\\*")
# What may not follow an underscore span's closer: `_INLINE_RE`'s `[0-9A-Za-z]`.
_ASCII_ALNUM = frozenset(
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)
# Stands in for an underscore no closer follows while `_INLINE_RE` runs; never drawn.
# Latin-1, so a line holding it stays one byte a character and parses as fast, and
# neither a letter nor whitespace to the pattern, so a link destination keeps it.
_DEAD_UNDERSCORE = "\x7f"
# Below this many such underscores a line is parsed as written: each costs one scan.
_DEAD_LIMIT = 16
# Link alternatives, in match order: label group -> (destination group, bold,
# italic). Every one yields a link span; the flags are the emphasis its wrapper
# carried. A disabled link has no destination (it reports nothing), and an
# autolink's destination is its label.
_LINK_SPAN_GROUPS = (
    ("bi_link_t", "bi_link_h", True, True),
    ("b_link_t", "b_link_h", True, False),
    ("i_link_t", "i_link_h", False, True),
    ("bi_link_u_t", "bi_link_u_h", True, True),
    ("b_link_u_t", "b_link_u_h", True, False),
    ("i_link_u_t", "i_link_u_h", False, True),
    ("d_link_t", None, False, False),
    ("code_link_t", "code_link_h", False, False),
    ("link_t", "link_h", False, False),
    ("bi_auto", "bi_auto", True, True),
    ("b_auto", "b_auto", True, False),
    ("i_auto", "i_auto", False, True),
    ("auto", "auto", False, False),
)
# Non-link alternatives: group name -> (bold, italic, code, strike).
_STYLE_SPAN_GROUPS = (
    ("bi_a", True, True, False, False),
    ("bi_u", True, True, False, False),
    ("b_a", True, False, False, False),
    ("b_u", True, False, False, False),
    ("i_a", False, True, False, False),
    ("i_u", False, True, False, False),
    ("strike", False, False, False, True),
    ("code", False, False, True, False),
)


# Emoji outside the ranges below, from Unicode's emoji-test.txt (Emoji 16.0), kept
# in step with detector_vocabulary's copy: these are emoji on their own ...
_EMOJI_BY_DEFAULT = frozenset(
    "\U0001f004\U0001f0cf\U0001f18e\U0001f191\U0001f192\U0001f193\U0001f194"
    "\U0001f195\U0001f196\U0001f197\U0001f198\U0001f199\U0001f19a\U0001f201"
    "\U0001f21a\U0001f22f\U0001f232\U0001f233\U0001f234\U0001f235\U0001f236"
    "\U0001f238\U0001f239\U0001f23a\U0001f250\U0001f251"
)
# ... and these only with U+FE0F after them: bare, they are text (`© 2026`, `™`).
_EMOJI_WITH_SELECTOR = frozenset(
    "©®‼⁉™ℹⓂ⤴⤵〰〽㊗㊙\U0001f170\U0001f171\U0001f17e\U0001f17f\U0001f202\U0001f237"
)


def _is_emoji_char(c: str) -> bool:
    """Whether *c* is drawn in the emoji font: detector_vocabulary's set, whose
    extra symbol blocks are md2ui's icon vocabulary, not Unicode's emoji."""
    cp = ord(c)
    return (
        c in _EMOJI_BY_DEFAULT
        or 0xE0020 <= cp <= 0xE007F  # tags: England, Scotland and Wales are 🏴 + tags
        or 0x1F300 <= cp <= 0x1FAFF  # emoticons, symbols, transport …
        or 0x2190 <= cp <= 0x21FF  # arrows
        or 0x231A <= cp <= 0x231B  # watch / hourglass
        or cp in (0x2328, 0x23CF)  # keyboard / eject
        or 0x23E9 <= cp <= 0x23F3  # media controls
        or 0x23F8 <= cp <= 0x23FA  # media controls
        or 0x2580 <= cp <= 0x25FF  # blocks / geometric shapes
        or 0x2600 <= cp <= 0x27BF  # misc symbols / dingbats
        or 0x2B00 <= cp <= 0x2BFF  # misc symbols and arrows
        or 0x1F1E0 <= cp <= 0x1F1FF  # regional indicators (flags)
        or cp == 0x200D  # ZWJ (multi-part emoji sequences)
        or 0xFE00 <= cp <= 0xFE0F  # variation selectors
    )


# A keycap (1️⃣) is a digit, ``#`` or ``*`` its font draws as one emoji: the
# whole sequence belongs to the emoji run, though the digit alone is text.
_KEYCAP_RE = re.compile("[0-9#*]\ufe0f?\u20e3")


def _split_emoji_runs(text: str) -> list[tuple[str, bool]]:
    """Return [(run_text, is_emoji), …] preserving order."""
    if not text:
        return []
    # Every range _is_emoji_char accepts starts at U+2190 or above, so ASCII text
    # is one plain run. Most words are ASCII, and this is called for each word a
    # layout measures — at every width a trial build tries.
    if text.isascii():
        return [(text, False)]
    flags = [_is_emoji_char(c) for c in text]
    for i, c in enumerate(text[:-1]):
        if c in _EMOJI_WITH_SELECTOR and text[i + 1] == "\ufe0f":
            flags[i] = True
    for m in _KEYCAP_RE.finditer(text):
        flags[m.start() : m.end()] = [True] * (m.end() - m.start())
    runs: list[tuple[str, bool]] = []
    current = text[0]
    current_is_emoji = flags[0]
    for c, c_is_emoji in zip(text[1:], flags[1:]):
        if c_is_emoji == current_is_emoji:
            current += c
        else:
            runs.append((current, current_is_emoji))
            current = c
            current_is_emoji = c_is_emoji
    runs.append((current, current_is_emoji))
    return runs


def _emoji_clusters(run: str) -> list[str]:
    """Split an all-emoji run into visual clusters (one entry per rendered emoji).

    A base codepoint absorbs trailing variation selectors (FE0E/FE0F), skin-tone
    modifiers (1F3FB–1F3FF), a keycap mark, tag characters and ZWJ-joined
    sequences -- the clusters a font draws as one glyph; regional-indicator pairs
    form one flag. Approximate but sufficient for per-glyph ``Fixed colors``
    lookup, which ``emoji_pin`` matches with or without the selector."""
    clusters: list[str] = []
    i, n = 0, len(run)
    while i < n:
        j = i + 1
        while j < n:
            cp = ord(run[j])
            prev = ord(run[j - 1])
            if cp == 0x200D:  # ZWJ → also consume the next joined base
                j = min(j + 2, n)
                continue
            if (
                0xFE00 <= cp <= 0xFE0F
                or 0x1F3FB <= cp <= 0x1F3FF
                or cp == 0x20E3  # keycap
                or 0xE0020 <= cp <= 0xE007F  # tags: a region's flag
            ):
                j += 1
                continue
            if (
                j - i == 1 and 0x1F1E6 <= prev <= 0x1F1FF and 0x1F1E6 <= cp <= 0x1F1FF
            ):  # regional-indicator flag pair
                j += 1
                continue
            break
        clusters.append(run[i:j])
        i = j
    return clusters


def bare_glyph(text: str) -> str:
    """``text`` without its variation selectors (U+FE00-U+FE0F)."""
    return "".join(c for c in text if not 0xFE00 <= ord(c) <= 0xFE0F)


def emoji_pin[T](pins: dict[str, T], glyph: str, default: T | None = None) -> T | None:
    """The ``## Fixed colors`` entry for ``glyph``, written with or without its
    variation selector on either side: ``☀️`` and ``☀`` are one glyph to the
    author, as they are to a Pills pin. An entry spelled exactly as the document
    wins over one that differs only by its selector."""
    hit = pins.get(glyph)
    if hit is not None or not pins:
        return default if hit is None else hit
    bare = bare_glyph(glyph)
    return next((v for k, v in pins.items() if bare_glyph(k) == bare), default)


# How deep nested inline styles are parsed. Every level consumes its own
# delimiters, so the inner text is always strictly shorter and the recursion
# terminates on its own — this is only insurance against a pathological input.
_MAX_SPAN_DEPTH = 6


def parse_inline_spans(
    text: str,
    _depth: int = 0,
    _allow_links: bool = True,
    _code_id: int = 0,
    _strike_id: int = 0,
    _ids: dict | None = None,
) -> list:
    """Parse inline markdown styles into a list of
    ``(text, bold, italic, code, strike, link)``.

    ``code`` and ``strike`` are REGION IDS, not booleans: ``0`` when the flag is
    off, otherwise the 1-based index of the ``code`` / ``~~`` region this span
    came from, counted per flag within one top-level parse. Every consumer reads
    them for truthiness and is unaffected; the ids exist so ``_flag_runs`` can
    tell "the next word of THIS marker" from "the first word of the NEXT one" —
    ```a` `b``` are two markers with only a space between them, and their
    backgrounds must not merge into one.

    ``link`` marks a link that was left inside this text run — a
    ``[label](url)`` (the grouper only peels those at line boundaries) or an
    ``<https://…>`` autolink. It is a paint-only flag, like ``strike``: the span
    keeps the surrounding font and size, and only the span text — the label, or
    the autolink's URI without its brackets — reaches measurement and drawing.
    It is a REGION ID too, the 1-based ordinal of the link in this text, so one
    link is one underline and one click target however many words it has, and
    two links side by side stay two (``inline_link_urls`` gives the targets).

    **Nesting.** Each matched span is re-parsed and the outer style is merged
    into whatever comes back, so ``~~**bold**~~`` is one bold+struck span rather
    than a struck span containing literal asterisks. This runs in every
    direction (``**~~x~~**``, ``~~`c`~~``, ``~~***x***~~``) and at any depth,
    which is why it is a recursion rather than a set of nested alternations in
    ``_INLINE_RE`` — spelling out the combinations there is factorial.

    Recursion produces *more spans carrying the same six fields*, never a wider
    tuple, so every consumer (``_explode_words`` → ``_wrap_lines`` /
    ``_line_width`` → the two draw passes) is unaffected and measurement stays
    in lockstep with drawing. A nested span INHERITS the enclosing region's id
    rather than minting its own, which is what keeps ``~~**a** b~~`` one rule.

    A link inside a styled phrase is prose: ``**see [the docs](/d) for more**``
    draws the phrase bold with ``the docs`` as its inline link, clickable, as
    the same sentence unstyled does. Only inside a code span
    are links off, since code is literal. A link that is the whole phrase
    (``**[x](/y)**``, the disabled ``~~[x](/y)~~``) matches its own ``_INLINE_RE``
    alternative first, and a link the author separated stands alone as a
    button: that cut is the grouper's, not this parse's.
    """
    spans = []
    last = 0
    written = text
    if "_" in text:
        text = _hide_dead_underscores(text)
    # One counter per flag, shared down the recursion. Per-flag (rather than one
    # counter for both) so the first ``code`` region of a parse is always id 1 —
    # ids stay small, stable and independent of what else the line contains.
    ids = _ids if _ids is not None else {"code": 0, "strike": 0, "urls": []}

    def add(inner: str, bold: bool, italic: bool, code: bool, strike: bool):
        """Re-parse *inner* and merge this level's style into each nested span.

        A span that yields nothing but itself (no markers inside) appends
        exactly as it did before recursion existed.
        """
        # A flag turning on here starts a new painted region — unless an
        # enclosing one already owns it, in which case this level is part of
        # that region (``~~**a** b~~`` is ONE strike, not two).
        c_id, s_id = _code_id, _strike_id
        if code and not c_id:
            ids["code"] += 1
            c_id = ids["code"]
        if strike and not s_id:
            ids["strike"] += 1
            s_id = ids["strike"]
        if _depth >= _MAX_SPAN_DEPTH:
            spans.append((inner, bold, italic, c_id, s_id, False))
            return
        for t, b, i, c, s, ln in parse_inline_spans(
            inner,
            _depth + 1,
            _allow_links=_allow_links and not code,
            _code_id=c_id,
            _strike_id=s_id,
            _ids=ids,
        ):
            spans.append((t, b or bold, i or italic, c or c_id, s or s_id, ln))

    escapes: set[int] = set()
    for m in _INLINE_RE.finditer(text):
        if m.start() > last:
            spans.append((text[last : m.start()], False, False, False, False, False))
        gd = m.groupdict()
        if gd["esc"] is not None:
            # Inside a code span an escape is literal, as in CommonMark.
            star = gd["esc"] if _code_id else "*"
            spans.append((star, False, False, False, False, False))
            escapes.add(len(spans) - 1)
            last = m.end()
            continue
        hit = next(
            ((n, h, b, i) for n, h, b, i in _LINK_SPAN_GROUPS if gd[n] is not None),
            None,
        )
        if hit is not None:
            name, url_name, bold, italic = hit
            if _allow_links:
                # A backtick label is the Text variant's marker, not part of the
                # label: the bare `[`x`](/y)` alternative already captures it
                # without them, but the emphasis-wrapped ones capture `.+?`
                # between the brackets and keep them. Strip a whole surrounding
                # pair, exactly as _classify_link_content does for buttons, so
                # an interior `code` in a label is left alone.
                label = gd[name]
                if len(label) >= 3 and label.startswith("`") and label.endswith("`"):
                    label = label[1:-1].strip()
                elif name != "code_link_t":
                    label = _ESCAPED_STAR.sub("*", label)
                urls = ids["urls"]
                urls.append(_link_destination(gd, name, url_name))
                spans.append((label, bold, italic, False, False, len(urls)))
            else:
                # Nested inside another span: leave the raw markup as text.
                # `~~`-wrapped links are reserved for the disabled BUTTON work,
                # and the inline styling of a nested one is not settled.
                spans.append((m.group(0), False, False, False, False, False))
        else:
            for name, bold, italic, code, strike in _STYLE_SPAN_GROUPS:
                if gd[name] is not None:
                    add(gd[name], bold, italic, code, strike)
                    break
        last = m.end()
    if last < len(text):
        spans.append((text[last:], False, False, False, False, False))
    if text is not written:
        spans = [(s[0].replace(_DEAD_UNDERSCORE, "_"), *s[1:]) for s in spans]
        ids["urls"][:] = [u and u.replace(_DEAD_UNDERSCORE, "_") for u in ids["urls"]]
    return _join_escapes(spans, escapes) if escapes else spans


def _hide_dead_underscores(text: str) -> str:
    """*text* with every `_` after the last one that can close hidden.

    No underscore span opens after its last closer, yet `_INLINE_RE` tries each such
    opener to the end of the line before it fails, so a line of them was quadratic:
    96 KB of `_a ` took 16 s. Hidden, they cost nothing, and the spans are the same.
    A closer is a `_` no letter or digit follows, or any `_` of the run that closes a
    link form (`_[a](b)_`), which has no such guard. Read from the end, so a line
    whose last `_` closes costs one look. A few dead openers stay as written, and so
    does a line already holding the stand-in.
    """
    i = text.rfind("_")
    end = i
    while i >= 0:
        start = i
        while start and text[start - 1] == "_":
            start -= 1
        if text[i + 1 : i + 2] not in _ASCII_ALNUM or (
            start and text[start - 1] == ")"
        ):
            break
        i = text.rfind("_", 0, i)
    tail = text[i + 1 :]
    if i == end or tail.count("_") < _DEAD_LIMIT or _DEAD_UNDERSCORE in text:
        return text
    return text[: i + 1] + tail.replace("_", _DEAD_UNDERSCORE)


def _join_escapes(spans: list, escapes: set[int]) -> list:
    """*spans* with each escaped star (at an index in *escapes*) joined to the
    plain text on either side, so ``a\\*b`` is the one span ``a*b`` would be
    and its word is measured and wrapped whole."""
    out: list = []
    for i, span in enumerate(spans):
        joins = i in escapes or i - 1 in escapes
        if joins and out and not any(out[-1][1:]) and not any(span[1:]):
            out[-1] = (out[-1][0] + span[0], *out[-1][1:])
        else:
            out.append(span)
    return out


def _link_destination(gd: dict, name: str, url_name: str | None) -> str | None:
    """Where a matched inline link points: None for a disabled link, and an email
    autolink (``<me@x.com>``, no scheme) as ``mailto:``."""
    if url_name is None:
        return None
    url = gd[url_name]
    if url_name == name and ":" not in url:
        return "mailto:" + url
    return url


def inline_link_urls(text: str) -> list[str | None]:
    """The destination of each inline link in *text*, by region id: entry
    ``k - 1`` belongs to the spans whose ``link`` slot is ``k``.

    The same parse ``parse_inline_spans`` makes, so an id and its destination
    cannot drift apart. Only top-level links count, as only they are links.
    """
    ids: dict = {"code": 0, "strike": 0, "urls": []}
    parse_inline_spans(text, _ids=ids)
    return ids["urls"]


def link_label_spans(label: str, variant: str | None) -> list[tuple[str, bool, bool]]:
    """A button label as ``(text, bold, italic)`` pieces, its emphasis markers gone.

    Emphasis inside the brackets styles the label, as CommonMark reads it; it is
    never a text tier, so ``_x_`` is italic here and not Muted. Only emphasis is
    consumed: a code or strikethrough span keeps its markers as the text it was
    drawn as before, because a button label has no chip or rule to draw them with.
    A Text-variant label was a code span, whose markers CommonMark keeps literal.
    """
    if variant == "text" or ("*" not in label and "_" not in label):
        return [(label, False, False)]
    pieces = []
    for text, bold, italic, code, strike, _link in parse_inline_spans(
        label, _allow_links=False
    ):
        text = f"`{text}`" if code else text
        pieces.append((f"~~{text}~~" if strike else text, bold, italic))
    return pieces


def plain_link_label(nd: dict) -> str:
    """The words a button node's label shows, without its emphasis markers. An
    author's hard break (U+2028, whitespace to ``str.split``) reads as a space,
    as it does in a link card's words."""
    spans = link_label_spans(nd.get("link_label") or "", nd.get("link_variant"))
    return " ".join("".join(piece[0] for piece in spans).split())


def project_paint_spans(content: str, words: list, spans: list[dict]) -> list:
    """Append word-local paint ranges to the normalized inline word tuples.

    Link, code and strike regions already travel through these tuples as
    paint-only ids. Datapoint colors use the same path: an eighth field holds
    ``(start, end, color)`` slices local to the word. No font or size field is
    changed, and measurement reads only the existing fields, so adding a color
    cannot move or rewrap text (ADR-400).

    The caller admits only source ranges whose content survived inline parsing
    unchanged. If that invariant is nevertheless broken, color the whole leaf
    with its first resolved pin instead of risking a misplaced slice.
    """
    if not spans:
        return [(*word, ()) for word in words]

    def fallback() -> list:
        color = spans[0]["color"]
        return [(*word, ((0, len(word[0]), color),)) for word in words]

    projected = []
    cursor = 0
    for word in words:
        text = word[0]
        start = content.find(text, cursor)
        if start < 0:
            return fallback()
        end = start + len(text)
        local = tuple(
            (
                max(start, span["start"]) - start,
                min(end, span["end"]) - start,
                span["color"],
            )
            for span in spans
            if span["start"] < end and start < span["end"]
        )
        projected.append((*word, local))
        cursor = end
    return projected
