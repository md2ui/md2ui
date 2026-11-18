"""
Unit tests for link handling: a click becomes an action (render_actions).

md2ui reports WHAT was clicked, as data, and the host decides. Pinned here:

  * the classification of a destination: ``https://…`` / ``mailto:`` / ``/route``
    are links for the host to route, ``#id`` is an anchor md2ui scrolls to itself,
    ``agent:<slug>?<args>`` is the agent's own action; an empty destination, a bare
    ``agent:`` and a ``~~disabled~~`` link report nothing;
  * the priority rule: the innermost target wins, so a button inside a link card
    reports itself and the card's body reports the card (ADR-404);
  * the geometry: every region is where its ink is. A button's region is the pill
    its drawer paints, and ``window_to_content`` inverts exactly the transform
    ``draw_scene`` paints with — checked by comparing pixels, not arithmetic.

Run with: uv run python tests/link_actions_tests.py
"""

import contextlib
import io
from pathlib import Path

import numpy as np
import skia

from md2ui import session
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_render import (
    _viewport_metrics,
    draw_scene,
    window_to_content,
)
from md2ui.pipeline.render_card_label import card_label
from md2ui.pipeline.render_actions import (
    Action,
    HitRegion,
    action_for,
    action_targets,
    commit_carries,
    hit_test,
    inert_nodes,
    requested,
    with_node_states,
)
from md2ui.pipeline.render_picture import record_document
from md2ui.pipeline.render_settings import VIEW
from md2ui.pipeline.render_text import inline_link_urls, parse_inline_spans
from md2ui.utils.image_cache import ImageCache
from md2ui.utils.scroll_state import ScrollState

ROOT = Path(__file__).resolve().parent.parent

_DOC = """# Actions {#top}

Want me to generate the quarterly report?

[Yes](agent:generate-report?format=pdf&year=2026) [No](agent:cancel)

**[Docs](https://example.com/docs)** ~~[Old](/old)~~

## Pricing {#pricing}

[
### Plan A
Everything you need.

[Choose](/checkout?plan=a)
](agent:choose-plan?plan=a)

[Back to top](#top)
"""

_MODELS = None


def _kit():
    global _MODELS
    if _MODELS is None:
        with contextlib.redirect_stdout(io.StringIO()):
            _MODELS = session.load_grouping_kit()
    return _MODELS


def _scene(markdown: str, width: float = 900.0, theme_path: Path | None = None):
    with contextlib.redirect_stdout(io.StringIO()):
        theme = session.load_theme(theme_path)
        fonts = session.load_fonts(theme)
        ast = session.group_markdown(markdown, _kit())
        assert ast is not None
        root, node_index = session.prepare(ast, theme)
        scene = session.build_scene(
            LayoutGenerator(), root, node_index, theme, fonts, width
        )
    return scene, node_index, theme, fonts


def _targets(markdown: str) -> list:
    with contextlib.redirect_stdout(io.StringIO()):
        ast = session.group_markdown(markdown, _kit())
    assert ast is not None
    return action_targets(ast.to_dict())


def _centre(r: HitRegion) -> tuple[float, float]:
    return r.x + r.width / 2, r.y + r.height / 2


def test_destinations_classify():
    cases = {
        "https://example.com/a?b=1": ("link", "https://example.com/a?b=1"),
        "mailto:me@example.com": ("link", "mailto:me@example.com"),
        "/pricing": ("link", "/pricing"),
        '/pricing "Our prices"': ("link", "/pricing"),
        "#pricing": ("anchor", "#pricing"),
        "<https://example.com/a b>": ("link", "https://example.com/a b"),
    }
    for url, (kind, href) in cases.items():
        a = action_for(url, "x", "n")
        assert a is not None and (a.kind, a.href) == (kind, href), (url, a)
    agent = action_for("agent:generate-report?format=pdf&year=2026", "Yes", "n")
    assert agent is not None and agent.kind == "agent"
    assert agent.action == "generate-report"
    assert agent.to_dict()["params"] == {"format": "pdf", "year": "2026"}
    assert action_for("AGENT:Cancel", "No", "n").action == "Cancel"  # type: ignore[union-attr]
    for silent in (None, "", "   ", "#", "agent:", "agent:?x=1", "<>"):
        assert action_for(silent, "x", "n") is None, silent

    # `md2ui.*` is addressed to the CLIENT, so it never reaches the agent's own
    # args — the same split an image's `?md2ui.max_width` takes.
    commits = action_for("agent:buy?id=7&md2ui.commit=1", "Proceed", "n")
    assert commits is not None and commits.commit is True, commits
    assert commits.params == (("id", "7"),), commits.params
    assert "md2ui" not in str(commits.to_dict()), commits.to_dict()
    for quiet in ("agent:buy?id=7", "agent:buy?md2ui.commit=none"):
        action = action_for(quiet, "Cancel", "n")
        assert action is not None and action.commit is False, quiet
    print("  ✓  destinations classify as link / anchor / agent, or report nothing")


def test_md2ui_params_never_leave_a_link():
    """``md2ui.*`` params instruct the client, so they are split off every
    destination, whatever its scheme, and kept only as the hints ``check`` reads;
    ``commit`` is read on an ``agent:`` link alone."""
    link = action_for("https://example.com/d?md2ui.commit=1&q=a", "Docs", "n")
    assert link is not None and link.href == "https://example.com/d?q=a", link
    assert link.hints == (("commit", "1"),) and not link.commit, link
    mail = action_for("mailto:a@b.co?md2ui.x=1", "Mail", "n")
    assert mail is not None and mail.href == "mailto:a@b.co", mail
    agent = action_for("agent:keep?id=7&md2ui.commit=1", "Keep", "n")
    assert agent is not None and agent.commit and agent.params == (("id", "7"),)
    assert "hints" not in agent.to_dict(), agent.to_dict()
    print("  ✓  md2ui params never leave a link; commit is read on agent: only")


def test_innermost_target_wins_then_last_painted():
    card = Action("agent", "c", action="outer")
    inner_card = Action("agent", "i", action="inner")
    button = Action("link", "b", href="/b")
    later = Action("link", "l", href="/l")
    regions = [
        HitRegion(0, 0, 100, 100, card, card=True),
        HitRegion(10, 10, 50, 50, inner_card, card=True),
        HitRegion(20, 20, 10, 10, button),
    ]
    assert hit_test(regions, 25, 25) is button
    assert hit_test(regions, 15, 15) is inner_card
    assert hit_test(regions, 5, 5) is card
    assert (
        hit_test(
            [HitRegion(0, 0, 10, 10, button), HitRegion(0, 0, 10, 10, later)], 5, 5
        )
        is later
    )
    assert hit_test(regions, 150, 150) is None
    print("  ✓  the innermost target wins; among overlapping ones, the last painted")


def test_every_region_reports_its_action():
    scene, _ni, _t, _f = _scene(_DOC)
    by_kind: dict[str, list[Action]] = {}
    for r in scene.regions:
        by_kind.setdefault(r.action.kind, []).append(r.action)
        got = hit_test(scene.regions, *_centre(r))
        over = [c for c in scene.regions if not c.card and c.contains(*_centre(r))]
        want = over[-1].action if over else r.action
        assert got is want, (r.action, got)
    slugs = sorted(a.action for a in by_kind.get("agent", []) if a.action)
    assert slugs == ["cancel", "choose-plan", "generate-report"], slugs
    hrefs = sorted(a.href for a in by_kind.get("link", []) if a.href)
    assert hrefs == ["/checkout?plan=a", "https://example.com/docs"], hrefs
    assert [a.href for a in by_kind.get("anchor", [])] == ["#top"]
    assert all(a.label != "Old" for acts in by_kind.values() for a in acts), (
        "a disabled link reports nothing"
    )
    print("  ✓  every region's centre reports its own action (or a button's over it)")


def test_a_button_inside_a_card_reports_itself():
    """A heart or a ➕ on a product card must not open the product: the button
    reports itself, and the card's body, away from the button, still reports the
    card."""
    scene, _ni, _t, _f = _scene(_DOC)
    choose = next(r for r in scene.regions if r.action.href == "/checkout?plan=a")
    card = next(r for r in scene.regions if r.card)
    got = hit_test(scene.regions, *_centre(choose))
    assert got is choose.action, got
    body = hit_test(scene.regions, card.x + 2, card.y + 2)
    assert body is not None and body.action == "choose-plan", body
    print("  ✓  a button inside a link card reports itself; the card's body, the card")


_CARDS = (
    ("See [a [nested] label](/c) now.", "/c", "a [nested] label"),
    (
        "[![](https://upload.wikimedia.org/wikipedia/commons/e/e3/Che_ne_saj.jpg)"
        " Caption\non two lines](/x)",
        "/x",
        "Caption on two lines",
    ),
    ("[## Card title\nBody text](/card)", "/card", "Card title"),
)


def test_a_link_card_reports_its_visible_text():
    """A link card is named by what it shows, as a plain link is by its label:
    its title when it has a heading, else its words. The
    window's region and the server's target say the same."""
    drawn = 0
    for markdown, href, label in _CARDS:
        targets = [t.action for t in _targets(markdown) if t.action]
        assert [(a.href, a.label) for a in targets] == [(href, label)], targets
        with contextlib.redirect_stdout(io.StringIO()):
            ast = session.group_markdown(markdown, _kit())
        assert ast is not None
        stack, wrapped = [ast.to_dict()], []
        while stack:
            nd = stack.pop()
            wrapped += [nd] if nd.get("link_url") else []
            stack.extend(nd.get("children", []))
        assert [card_label(nd) for nd in wrapped] == [label], wrapped
        scene, _ni, _t, _f = _scene(markdown)
        cards = [r.action for r in scene.regions if r.card]
        assert all((a.href, a.label) == (href, label) for a in cards), cards
        drawn += len(cards)
    assert drawn == len(_CARDS), drawn
    print("  ✓  a link card reports its visible text, window and server alike")


def test_a_card_inside_a_sentence_is_clickable():
    """A card that wraps one text is a leaf with no container to carry its
    click; its region covers the box its words are drawn in."""
    markdown = "See [a [nested] label](/c) now."
    scene, node_index, _t, _f = _scene(markdown)
    key = next(t.key for t in _targets(markdown) if t.action)
    box = next(b for b in scene.boxes if b.content_id == key)
    cards = [r for r in scene.regions if r.card and r.action.href == "/c"]
    assert len(cards) == 1, scene.regions
    r = cards[0]
    assert r.x <= box.x and r.y <= box.y, (r, box)
    assert r.x + r.width >= box.x + box.width, (r, box)
    assert r.y + r.height >= box.y + box.height, (r, box)
    got = hit_test(scene.regions, box.x + 4, box.y + box.height / 2)
    assert got is not None and (got.href, got.label) == ("/c", "a [nested] label")
    assert node_index[key].get("link_url") == "/c", node_index[key]
    print("  ✓  a link card inside a sentence is clickable where it is drawn")


def test_a_card_inside_a_table_cell_is_clickable():
    """A table places its cells itself; a card inside a cell still clicks where
    it is drawn, as it does outside the table."""
    markdown = (
        "| Plan | Details |\n| --- | --- |\n"
        "| A | See [a [nested] label](/c) now. |\n| B | plain |\n"
    )
    scene, node_index, _t, _f = _scene(markdown)
    key = next(k for k, nd in node_index.items() if nd.get("link_url") == "/c")
    box = next(b for b in scene.boxes if b.content_id == key)
    cards = [r for r in scene.regions if r.card and r.action.href == "/c"]
    assert len(cards) == 1, scene.regions
    r = cards[0]
    rect = (r.x, r.y, r.width, r.height)
    want = (box.x, box.y, box.width, box.height)
    assert all(abs(a - b) < 1e-6 for a, b in zip(rect, want)), (r, box)
    got = hit_test(scene.regions, box.x + 4, box.y + box.height / 2)
    assert got is not None and (got.href, got.label) == ("/c", "a [nested] label")
    print("  ✓  a link card inside a table cell is clickable where it is drawn")


def test_anchors_point_at_their_headings():
    scene, _ni, _t, _f = _scene(_DOC)
    assert set(scene.anchors) >= {"top", "pricing"}, scene.anchors
    assert 0 <= scene.anchors["top"] < scene.anchors["pricing"] < scene.height
    print("  ✓  heading anchors are recorded in document order")


_FENCED = """Before [Real](agent:real)

```markdown
[Docs](https://example.com) and [Go](agent:go)
```

After `[x](agent:inline)` here.
"""


def test_a_link_inside_a_styled_phrase_is_a_target():
    """A link inside a bold phrase is prose's inline link: offered to the agent as a
    target, with a region the window can click, under the same key."""
    doc = "Please **read [the terms](https://ex.com/t) first** before you pay.\n"
    targets = _targets(doc)
    assert [(t.action.kind, t.action.label, t.action.href) for t in targets] == [
        ("link", "the terms", "https://ex.com/t")
    ], targets
    regions = {r.action.node_id for r in _scene(doc)[0].regions}
    assert regions == {t.key for t in targets}, (regions, targets)
    print("  ✓  a link inside a styled phrase is a target with its region")


def test_a_link_in_a_code_block_is_not_a_target():
    """A code block is literal text: a link written in it draws no region, so it is
    not a target either. Targets and regions agree in both directions, or the agent
    is offered a button the user cannot press."""
    targets = _targets(_FENCED)
    assert [(t.action.kind, t.action.action) for t in targets] == [("agent", "real")], (
        targets
    )
    for width in (767.0, 1280.0):
        scene = _scene(_FENCED, width)[0]
        regions = {r.action.node_id for r in scene.regions if r.action.kind != "copy"}
        assert regions == {t.key for t in targets}, (width, regions, targets)
    print("  ✓  a link in a code block is not a target; targets match regions")


def _read(surface: skia.Surface, x: float, y: float) -> int:
    info = skia.ImageInfo.MakeN32Premul(1, 1)
    buf = bytearray(4)
    assert surface.readPixels(info, buf, 4, int(x), int(y))
    return int.from_bytes(buf, "little")


def test_window_to_content_inverts_the_paint():
    """A button's pixel in a painted window frame equals the same button's pixel
    in the document drawn alone, at the point ``window_to_content`` maps to.

    Sampled on each pill's flat FILL, just inside its left edge at mid-height:
    a label's anti-aliased glyphs would differ with the sub-pixel offset, a flat
    fill does not. Needs a theme that fills its buttons, so it uses the corpus's
    links document with the theme that document renders with.
    """
    path = ROOT / "data/markdown/tests/tests-links.md"
    scene, node_index, theme, fonts = _scene(
        path.read_text(), 900.0, session.resolve_theme_path(path, None)
    )
    picture = record_document(
        scene.boxes,
        scene.sections,
        node_index,
        scene.width,
        scene.height,
        fonts,
        ImageCache(),
        theme,
        scene.layout,
        {},
    )
    # Buttons only: a link inside a sentence (``<node>#<k>``) sits on glyphs, not
    # on a flat fill, and its anti-aliasing moves with the sub-pixel offset.
    fills = [
        (r.x + 3.0, r.y + r.height / 2)
        for r in scene.regions
        if not r.card and "#" not in r.action.node_id
    ]
    prev = VIEW.show_frame
    try:
        for dpr in (1.0, 2.0):
            doc = skia.Surface(
                int((scene.width + 1) * dpr), int((scene.height + 1) * dpr)
            )
            canvas = doc.getCanvas()
            canvas.clear(theme.root.bg_color)
            canvas.scale(dpr, dpr)
            canvas.drawPicture(picture)
            opaque = [
                (x, y) for x, y in fills if _read(doc, x * dpr, y * dpr) >> 24 == 0xFF
            ]
            assert opaque, "the theme should fill its buttons"
            for show_frame in (True, False):
                VIEW.show_frame = show_frame
                win_w, win_h = 1000, 600
                vp_x, vp_y, vp_w, vp_h = _viewport_metrics(win_w, win_h)
                for scroll_y in (0.0, scene.height / 3):
                    scroll = ScrollState()
                    scroll.y = scroll_y
                    # window_to_content is a translation: read it off one point.
                    probe = window_to_content(
                        vp_x + 1, vp_y + 1, win_w, win_h, scene.width, theme, scroll
                    )
                    assert probe is not None
                    dx, dy = probe[0] - (vp_x + 1), probe[1] - (vp_y + 1)
                    outside = window_to_content(
                        vp_x - 5, vp_y + 1, win_w, win_h, scene.width, theme, scroll
                    )
                    assert outside is None
                    frame = skia.Surface(int(win_w * dpr), int(win_h * dpr))
                    draw_scene(
                        frame.getCanvas(),
                        picture,
                        scene.width,
                        scene.height,
                        "",
                        fonts.typeface,
                        win_w,
                        win_h,
                        scroll,
                        theme,
                        dpr,
                        {},
                    )
                    checked = 0
                    for cx, cy in opaque:
                        mx, my = cx - dx, cy - dy
                        inside = vp_x + 2 <= mx < vp_x + vp_w - 2
                        if not (inside and vp_y + 2 <= my < vp_y + vp_h - 2):
                            continue
                        want = _read(doc, cx * dpr, cy * dpr)
                        got = _read(frame, mx * dpr, my * dpr)
                        assert got == want, (show_frame, scroll_y, dpr, cx, cy)
                        checked += 1
                    assert checked, (show_frame, scroll_y, dpr)
    finally:
        VIEW.show_frame = prev
    print("  ✓  window_to_content maps a click onto the pixel the paint put there")


def test_corpus_regions_report_themselves():
    for rel in (
        "data/markdown/tests/tests-links.md",
        "data/markdown/tests-render/home-dashboards/kawsar-ahmed-macos-custom-widget/content.md",
        "data/markdown/tests/tests-row-syntax-advanced.md",
    ):
        path = ROOT / rel
        theme_path = session.resolve_theme_path(path, None)
        for width in (767.0, 1280.0):
            scene, _ni, _t, _f = _scene(path.read_text(), width, theme_path)
            for r in scene.regions:
                got = hit_test(scene.regions, *_centre(r))
                outer = [c for c in scene.regions if c.card and c.contains(*_centre(r))]
                want = (
                    max(outer, key=lambda c: c.width * c.height).action
                    if outer
                    else r.action
                )
                assert got is want, (rel, width, r.action, got)
    print("  ✓  in three corpus documents every region's centre reports its action")


# Checkboxes, and the host's transient state per node.
_TASKS = """## Tasks

- [x] Draft the report
- [ ] Review the numbers
- [[ ]](agent:toggle-task?id=3) Send it to finance

[Yes](agent:generate-report) [No](agent:cancel)
"""


def _controls(scene) -> list[Action]:
    return sorted(
        (r.action for r in scene.regions if r.action.index is not None),
        key=lambda a: a.index or 0,
    )


def test_checkboxes_report_index_and_label():
    scene, _ni, _t, _f = _scene(_TASKS)
    got = [(a.kind, a.index, a.label, a.checked, a.action) for a in _controls(scene)]
    assert got == [
        ("checkbox", 0, "Draft the report", False, None),
        ("checkbox", 1, "Review the numbers", True, None),
        ("agent", 2, "Send it to finance", True, "toggle-task"),
    ], got
    linked = _controls(scene)[2].to_dict()
    assert linked["params"] == {"id": "3"}, linked
    assert (linked["checked"], linked["index"]) == (True, 2), linked
    for r in scene.regions:
        if r.action.index is not None:
            assert hit_test(scene.regions, *_centre(r)) is r.action
    print("  ✓  a checkbox reports its index, its label and the state it asks for")


_LINKED_TASK = """- [ ] Pack the kitchen
- [[ ]](agent:toggle-task?id=1) Transfer the utilities
"""


def test_a_linked_task_click_reports_its_agent_action():
    # `- [[ ]](agent:…)` is the same task item as `- [ ]`; only where the click
    # goes differs. It reports the agent action with its args, the state it asks
    # for, and the index and label a plain box reports, and it is sent.
    scene, _ni, _t, _f = _scene(_LINKED_TASK)
    plain, linked = _controls(scene)
    assert (plain.kind, plain.label) == ("checkbox", "Pack the kitchen"), plain
    got = linked.to_dict()
    assert got["kind"] == "agent" and got["action"] == "toggle-task", got
    assert got["params"] == {"id": "1"}, got
    assert (got["checked"], got["index"]) == (True, 1), got
    assert got["label"] == "Transfer the utilities", got
    sent = not commit_carries(linked, _targets(_LINKED_TASK))
    assert sent, "a linked task click with no committing button is sent"
    region = next(r for r in scene.regions if r.action is linked)
    assert hit_test(scene.regions, *_centre(region)) is linked
    print("  ✓  a linked task reports its agent action, index and label")


def test_a_second_click_asks_for_the_opposite():
    review = _controls(_scene(_TASKS)[0])[1]
    assert requested(review, {}).checked is True
    assert requested(review, {review.node_id: "checked"}).checked is False
    assert requested(review, {review.node_id: "unchecked"}).checked is True
    print("  ✓  the requested state follows the host's optimistic tick")


def test_inert_nodes_report_nothing():
    card = Action("agent", "c", action="outer")
    button = Action("link", "b", href="/b")
    regions = [
        HitRegion(0, 0, 100, 100, card, card=True),
        HitRegion(20, 20, 10, 10, button),
    ]
    assert hit_test(regions, 25, 25, inert={"c"}) is None, "an inert card swallows"
    assert hit_test(regions, 25, 25, inert={"b"}) is None, "never falls to the card"
    assert hit_test(regions, 5, 5, inert={"b"}) is card
    assert hit_test(regions[1:], 25, 25, inert={"b"}) is None
    states = {"a": "pending", "b": "disabled", "c": "checked", "d": "unchecked"}
    assert inert_nodes(states) == {"a", "b"}
    print("  ✓  a pending or disabled node reports nothing, and blocks what it holds")


def _raster(picture: skia.Picture, width: float, height: float) -> np.ndarray:
    surface = skia.Surface(int(width) + 1, int(height) + 1)
    canvas = surface.getCanvas()
    canvas.clear(0xFFFFFFFF)
    canvas.drawPicture(picture)
    return surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)


def test_host_state_changes_colours_only():
    """A pending button and an optimistic tick move no box, and the pixels they
    change all lie inside those two nodes' own regions."""
    theme_path = ROOT / "data/markdown/tests/THEME.md"
    scene, node_index, theme, fonts = _scene(_TASKS, 900.0, theme_path)
    yes = next(r for r in scene.regions if r.action.action == "generate-report")
    tick = next(r for r in scene.regions if r.action.index == 1)
    states: dict[str, str | float] = {
        yes.action.node_id: "pending",
        tick.action.node_id: "checked",
    }
    assert with_node_states(node_index, {}) is node_index
    shown = with_node_states(node_index, states)
    assert shown[yes.action.node_id]["link_disabled"] is True
    assert not node_index[yes.action.node_id].get("link_disabled"), "not mutated"
    assert shown[tick.action.node_id]["drawing_element"]["checked"] is True
    assert node_index[tick.action.node_id]["drawing_element"]["checked"] is False

    def recorded() -> np.ndarray:
        picture = record_document(
            scene.boxes,
            scene.sections,
            node_index,
            scene.width,
            scene.height,
            fonts,
            ImageCache(),
            theme,
            scene.layout,
            {},
        )
        return _raster(picture, scene.width, scene.height)

    plain = recorded()
    prev = VIEW.node_states
    VIEW.node_states = states
    try:
        again, _n, _t, _f = _scene(_TASKS, 900.0, theme_path)
        assert again.boxes == scene.boxes, "host state must not move a box"
        marked = recorded()
    finally:
        VIEW.node_states = prev
    ys, xs = np.nonzero((plain != marked).any(axis=2))

    # A pending button is muted, and a muted button's shadow fades with it, so its
    # own paint reaches past its region by the theme's shadow: offset 2 and radius 6
    # in the tests THEME, rounded up.
    reach = 9

    def inside(r: HitRegion, x, y):
        return (
            (r.x - reach <= x)
            & (x <= r.x + r.width + reach)
            & (r.y - reach <= y)
            & (y <= r.y + r.height + reach)
        )

    for r in (yes, tick):
        assert inside(r, xs, ys).any(), f"{r.action.label} must change colour"
    stray = ~(inside(yes, xs, ys) | inside(tick, xs, ys))
    assert not stray.any(), list(zip(xs[stray][:5], ys[stray][:5]))
    print("  ✓  host state changes colours only, and only inside its own nodes")


def _grouped(markdown: str) -> dict:
    with contextlib.redirect_stdout(io.StringIO()):
        ast = session.group_markdown(markdown, _kit())
    assert ast is not None
    return ast.to_dict()


def _payloads(tree: dict) -> list[tuple[str, dict]]:
    found = (
        [(tree["node_id"], tree["drawing_element"])]
        if "drawing_element" in tree
        else []
    )
    for child in tree.get("children", []):
        found += _payloads(child)
    return found


def _skeleton(tree: dict) -> tuple:
    return (tree["node_id"], [_skeleton(c) for c in tree.get("children", [])])


def _types(tree: dict) -> dict[str, str]:
    found = {tree["node_id"]: tree["type"]}
    for child in tree.get("children", []):
        found |= _types(child)
    return found


def test_a_resend_moves_only_the_tick():
    """The agent answers a tick by sending the same Markdown with ``[ ]`` -> ``[x]``.

    Every node keeps its id and place, so host state keyed by id stays meaningful,
    and every control keeps its index and label. What moves is the tick and the
    item's type (``task_open`` -> ``task_done``, read off the marker), plus the
    statistics derived from those: fingerprints and word counts.
    """
    before = _grouped(_TASKS)
    after = _grouped(_TASKS.replace("- [ ] Review", "- [x] Review"))
    assert _skeleton(before) == _skeleton(after), "a tick must not move a node"
    old, new = _payloads(before), _payloads(after)
    assert [(i, p["index"], p["label"]) for i, p in old] == [
        (i, p["index"], p["label"]) for i, p in new
    ], (old, new)
    assert [p["checked"] for _i, p in new] == [True, True, False], new
    t0, t1 = _types(before), _types(after)
    moved = {i: (t0[i], t1[i]) for i in t0 if t0[i] != t1[i]}
    item = old[1][0].rsplit(".", 1)[0]  # the ticked control's list item
    assert moved == {item: ("task_open", "task_done")}, moved
    print("  ✓  a re-send keeps every id, index and label; only the tick moves")


# Links inside a sentence. The heading matters: a document
# of one paragraph and nothing else is grouped to an empty tree and draws nothing.
# The first link is long enough to wrap at the 320px page floor.
_LONG_LABEL = (
    "complete pricing notes, the fine print and every one of the extra "
    "conditions that apply to your plan"
)
_PROSE = (
    f"# Plans\n\nRead the [{_LONG_LABEL}](#plans) before you choose, or ask to "
    "[talk to sales](agent:contact-sales?team=west). Skip the ~~[old notes](/old)~~ "
    "page."
)


def test_inline_links_keep_their_destinations():
    """The link slot of a word is a region id, and the destinations come back in
    region order from the same parse; a disabled link keeps its id, reports None."""
    text = (
        "See [a](/x), <https://y.dev> or <me@x.com> ~~[d](/z)~~ **[b](agent:go?k=1)**"
    )
    assert inline_link_urls(text) == [
        "/x",
        "https://y.dev",
        "mailto:me@x.com",
        None,
        "agent:go?k=1",
    ], inline_link_urls(text)
    assert [s[5] for s in parse_inline_spans(text) if s[5]] == [1, 2, 3, 4, 5]
    print("  ✓  each inline link's destination comes back under its region id")


def test_a_wrapped_inline_link_is_one_link_on_every_line():
    scene, _ni, _t, _f = _scene(_PROSE, 300.0)
    plans = [r for r in scene.regions if r.action.href == "#plans"]
    assert len(plans) >= 2, [r.action for r in scene.regions]
    assert len({r.y for r in plans}) == len(plans), "one region per line"
    assert len({r.action.node_id for r in plans}) == 1, "one link, one id"
    assert {r.action.label for r in plans} == {_LONG_LABEL}, "the WHOLE label"
    sales = [r for r in scene.regions if r.action.action == "contact-sales"]
    assert len(sales) == 1 and sales[0].action.label == "talk to sales", sales
    assert sales[0].action.to_dict()["params"] == {"team": "west"}
    assert plans[0].action.node_id != sales[0].action.node_id
    assert not [r for r in scene.regions if r.action.label == "old notes"], (
        "a disabled inline link reports nothing"
    )
    for r in plans + sales:
        assert hit_test(scene.regions, *_centre(r)) is r.action
    print("  ✓  a wrapped inline link is one region per line, all of one link")


def test_a_committing_button_carries_its_documents_controls():
    """Whether a settle needs sending at all is a property of the DOCUMENT: if a
    press will report the control, the control need not report itself."""
    live = _targets("A: [30%]\n\n- [ ] Wrap it\n\n[Go](agent:go)")
    batched = _targets("A: [30%]\n\n- [ ] Wrap it\n\n[Go](agent:go?md2ui.commit=1)")

    # No committing button: every adjustment reaches the agent.
    assert not any(commit_carries(t.action, live) for t in live if t.action)

    kinds = {t.action.kind: t.action for t in batched if t.action is not None}
    assert commit_carries(kinds["slider"], batched), "the slider is carried"
    assert commit_carries(kinds["checkbox"], batched), "so is the task box"
    assert not commit_carries(kinds["agent"], batched), "the press reports itself"
    print("  ✓  a committing press carries its controls, so their settles stay home")


def _nodes(tree: dict, kind: str) -> list[str]:
    found = [tree.get("content", "")] if tree.get("type") == kind else []
    for child in tree.get("children", []):
        found += _nodes(child, kind)
    return found


def test_grouped_destinations_keep_their_parentheses():
    """The grouper and the renderer read one destination pattern
    (``render_text.LINK_DESTINATION``), so a URL with ``(…)`` reaches the click
    whole whether the link was peeled into a button or stayed in its prose."""
    url = "https://en.wikipedia.org/wiki/POST_(HTTP)#Use"

    def links(md: str) -> list[tuple[str, str | None]]:
        return [(t.action.label, t.action.href) for t in _targets(md) if t.action]

    assert links(f"Accepts [form-encoded]({url}) request bodies.") == [
        ("form-encoded", url)
    ]
    assert links(f"[Open]({url})") == [("Open", url)]
    assert links(f"**[Bold]({url})**") == [("Bold", url)]
    assert links(f"[`code`]({url})") == [("code", url)]
    assert links(f"[a]({url}) and [b](/plain)") == [("a", url), ("b", "/plain")]
    slider = [t.action for t in _targets("[[35%]](agent:set?x=(a))") if t.action]
    assert [(a.action, a.params) for a in slider] == [("set", (("x", "(a)"),))]
    task = [t.action for t in _targets("- [[ ]](agent:t?id=(1)) Pack") if t.action]
    assert [(a.label, a.action, a.params) for a in task] == [
        ("Pack", "t", (("id", "(1)"),))
    ]
    image = "![alt](https://img.org/a_(b).png)"
    assert _nodes(_grouped(image), "image") == [image]
    # An empty destination keeps its meaning: an inline link that reports nothing.
    assert [t.action for t in _targets("Go [↗️]() now ~~[x]()~~")] == [None, None]
    print("  ✓  peeled and inline links, sliders, tasks and images keep (…) URLs")


def test_destinations_follow_commonmark():
    """A bare destination ends at a space, as in CommonMark, so
    ``[Open](/my file)`` is not a link: it stays literal text, and no click
    region reports a truncated ``/my``. Angle brackets carry a space, a title
    after the destination is dropped, and the grouper, the renderer and the
    click all read the same span."""

    def links(md: str) -> list[tuple[str, str | None]]:
        return [(t.action.label, t.action.href) for t in _targets(md) if t.action]

    assert links("[Open](/my file)") == []
    assert _nodes(_grouped("[Open](/my file)"), "link") == []
    spans = parse_inline_spans("[Open](/my file)")
    assert spans == [("[Open](/my file)", False, False, False, False, False)], spans
    # The rejected link's label must not run on into the next link's.
    assert links("See [a](/my file) and [b](/c).") == [("b", "/c")]
    assert links("[Open](</my file>)") == [("Open", "/my file")]
    for title in ('"Title"', "'Title'", "(Title)"):
        assert links(f"[Open](/x {title})") == [("Open", "/x")], title
        assert links(f"Read [it](/x {title}) now.") == [("it", "/x")], title
    assert links("[a](/x(1))") == [("a", "/x(1)")]
    image = '![alt](https://img.org/a.png "A title")'
    assert _nodes(_grouped(image), "image") == [image]
    print("  ✓  a spaced destination is text; <…>, titles and (…) are links")


def test_a_label_balances_its_brackets():
    """As in CommonMark, brackets inside a label must balance: in
    ``[a] text [b](/c)`` the link is ``[b](/c)`` and ``[a] text`` stays text,
    never one link labelled ``a] text [b``. A balanced pair inside the label is
    part of it, and a link inside a label is the link."""

    def links(md: str) -> list[tuple[str, str | None]]:
        return [(t.action.label, t.action.href) for t in _targets(md) if t.action]

    assert inline_link_urls("Read [a] text [b](/c) here.") == ["/c"]
    spans = parse_inline_spans("Read [a] text [b](/c) here.")
    assert [s[0] for s in spans] == ["Read [a] text ", "b", " here."], spans
    assert links("Read [a] text [b](/c) here.") == [("b", "/c")]
    assert [s[0] for s in parse_inline_spans("[a [nested] label](/c)")] == [
        "a [nested] label"
    ]
    assert inline_link_urls("[a [b](/c) d](/e)") == ["/c"]
    # The grouper makes a bracketed label a link card, which reports no label.
    assert [h for _, h in links("See [a [nested] label](/c) now.")] == ["/c"]
    print("  ✓  a label balances its brackets; one nested pair is part of it")


TESTS = [
    test_md2ui_params_never_leave_a_link,
    test_a_label_balances_its_brackets,
    test_a_link_card_reports_its_visible_text,
    test_a_card_inside_a_sentence_is_clickable,
    test_a_card_inside_a_table_cell_is_clickable,
    test_destinations_follow_commonmark,
    test_grouped_destinations_keep_their_parentheses,
    test_a_committing_button_carries_its_documents_controls,
    test_destinations_classify,
    test_innermost_target_wins_then_last_painted,
    test_every_region_reports_its_action,
    test_a_button_inside_a_card_reports_itself,
    test_anchors_point_at_their_headings,
    test_a_link_in_a_code_block_is_not_a_target,
    test_a_link_inside_a_styled_phrase_is_a_target,
    test_window_to_content_inverts_the_paint,
    test_corpus_regions_report_themselves,
    test_checkboxes_report_index_and_label,
    test_a_linked_task_click_reports_its_agent_action,
    test_a_second_click_asks_for_the_opposite,
    test_inert_nodes_report_nothing,
    test_host_state_changes_colours_only,
    test_a_resend_moves_only_the_tick,
    test_inline_links_keep_their_destinations,
    test_a_wrapped_inline_link_is_one_link_on_every_line,
]

if __name__ == "__main__":
    print("Link Actions Tests")
    print("=" * 50)
    failed = 0
    for test in TESTS:
        try:
            test()
        except Exception as e:
            print(f"  ✗  {test.__name__}: {e!r}")
            failed += 1
    print("=" * 50)
    if failed:
        print(f"{failed} test(s) FAILED.")
        raise SystemExit(1)
    print(f"All {len(TESTS)} tests passed.")
