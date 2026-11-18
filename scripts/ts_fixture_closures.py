"""The layout generator's closure answers, for `export_ts_fixtures.py`.

``LayoutGenerator.generate`` measures nothing itself: it asks the five closures
``session.build_scene`` hands it. md2ui-ts ports the generator's decisions apart
from its sizing, so it needs each closure's answers on their own, keyed by what
the port can compute from its own tree. Three of them are keyed by a leaf's
fields and are recorded in ``measure/`` (``TextMeasure`` notes them through
:func:`note_leaf_closures`); this module records, in ``measure-layout/``, the
two that are asked about a BUILT subtree, and the code-block plans:

* ``layout_height`` -- ``make_layout_measurer``'s closure: the rendered height
  of a built subtree in a cell *width* wide;
* ``block_width``   -- ``make_block_width_measurer``'s closure: the width below
  which a built block starts to collapse, asked with the width it is offered;
* ``code_block``    -- ``code_block_plan``: a code block's geometry
  (``CodeBlockPlan``'s measured fields and its ``line_count``), keyed by its
  ``language`` and ``content``; md2ui measures it as pygments token runs a
  TypeScript highlighter cannot reproduce.

``layout_height`` and ``block_width`` are keyed ``{q, subtree, width}``, the
width a float; a record also carries ``a`` (the answer), ``n`` (times asked)
and ``at`` (diagnosis only: the order first asked, the subtree's first
``content_id``), none of which is part of the key.

A subtree is keyed by :func:`subtree_digest`, defined over the fixture form of
a ``LayoutNode`` (the form of ``layout-generated/``), so both sides compute it::

    sha256(utf8(canonical(renumber_flow_runs(fixture_form(subtree)))))

* ``fixture_form`` -- every ``LayoutNode`` field, children included, as
  :func:`ts_fixture_capture.plain` writes it (non-finite floats as strings);
* ``renumber_flow_runs`` -- each non-zero ``flow_run`` replaced by its order of
  first appearance in a pre-order walk (1, 2, ...), so the key does not carry
  the generator's run counter, which the answers never read beyond equality;
* ``canonical`` -- ``JSON.stringify`` of the value with object keys sorted: no
  whitespace, strings as ``JSON.stringify`` escapes them, numbers in
  ECMAScript ``Number::toString`` form (``100.0`` is ``100``, ``1e-07`` is
  ``1e-7``), so an int and an equal float are one number.

Replay (:class:`ClosureLedger` with answers) answers all five closures and every
code-block plan from the recordings, and refuses any font question while the
generator runs, so a replay that reproduces the layout proves the recordings
alone decide it.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from typing import Any

from ts_fixture_capture import Hooks, dump_line, plain

# What the two leaf closures read off a node (layout_render.make_width_measurer,
# make_line_width_measurer): the key their answers are filed under. The
# generator also measures stand-in nodes it builds, so the id alone is not one.
_LEAF_INPUTS = tuple(
    (
        "node_id type content heading_ctx text_style text_style_chain "
        "code_variant code_language emoji_kind emoji_index emoji_variant "
        "in_key table_role link_variant link_label link_is_emoji "
        "link_disabled drawing_element"
    ).split()
)
# The closure answers measure/ holds; the rest of a measure/ file is fonts.
LEAF_KINDS = ("leaf_min_width", "leaf_line_width", "marker_width")
# What a code-block answer carries: CodeBlockPlan's measured fields.
_PLAN_FIELDS = ("width", "height", "line_height", "baseline", "full_height", "header")


def leaf_question(kind: str, node: Any, kv_role: str | None) -> dict:
    """A leaf closure's question: the leaf's fields and its K-V role."""
    inputs = {name: plain(getattr(node, name, None)) for name in _LEAF_INPUTS}
    return {"q": kind, "kv_role": kv_role, "node": inputs}


def marker_question(props: dict) -> dict:
    return {"q": "marker_width", "props": plain(props)}


def note_leaf_closures(hooks: Hooks, note: Callable[[dict, Any], None]) -> None:
    """Patch, through *hooks*, the generator's three leaf-keyed closures so each
    answer they give is passed to *note* with its question."""
    from md2ui import session

    def noting_leaf(factory: Callable, kind: str) -> Callable:
        def make(fonts: Any, theme: Any) -> Callable:
            inner = factory(fonts, theme)

            def measured(node: Any, kv_role: str | None = None) -> Any:
                answer = inner(node, kv_role)
                note(leaf_question(kind, node, kv_role), answer)
                return answer

            return measured

        return make

    for factory, kind in (
        ("make_width_measurer", "leaf_min_width"),
        ("make_line_width_measurer", "leaf_line_width"),
    ):
        hooks.patch(session, factory, noting_leaf(vars(session)[factory], kind))
    orig_marker = vars(session)["make_marker_measurer"]

    def make_marker_measurer(fonts: Any, theme: Any) -> Callable:
        inner = orig_marker(fonts, theme)

        def measure_marker(props: dict) -> float:
            answer = inner(props)
            note(marker_question(props), answer)
            return answer

        return measure_marker

    hooks.patch(session, "make_marker_measurer", make_marker_measurer)


# --- the subtree digest ---------------------------------------------------------


def js_number(x: float) -> str:
    """*x* as ECMAScript's ``Number::toString`` writes it (what ``JSON.stringify``
    writes): shortest round-trip digits, no ``.0``, an exponent only below 1e-6
    or from 1e21."""
    x = float(x)
    if not math.isfinite(x):
        raise ValueError(f"no JSON number for {x}")
    if x == 0:
        return "0"  # -0 too
    sign = "-" if x < 0 else ""
    mantissa, _, exp = repr(abs(x)).partition("e")
    whole, _, frac = mantissa.partition(".")
    digits = whole + frac
    point = len(whole) + int(exp or 0)
    stripped = digits.lstrip("0")
    point -= len(digits) - len(stripped)
    s = stripped.rstrip("0")
    k, n = len(s), point
    if k <= n <= 21:
        text = s + "0" * (n - k)
    elif 0 < n <= 21:
        text = f"{s[:n]}.{s[n:]}"
    elif -6 < n <= 0:
        text = "0." + "0" * -n + s
    else:
        e = n - 1
        text = f"{s[0]}{'.' + s[1:] if k > 1 else ''}e{'+' if e >= 0 else '-'}{abs(e)}"
    return sign + text


def canonical(value: Any) -> str:
    """*value* (fixture-form data) as ``JSON.stringify`` writes it, keys sorted."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return js_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(canonical(v) for v in value) + "]"
    if isinstance(value, dict):
        if not all(k.isascii() for k in value):
            # Code-point and UTF-16 order agree only on ASCII keys.
            raise ValueError(f"a non-ASCII key in {sorted(value)}")
        return (
            "{"
            + ",".join(f"{json.dumps(k)}:{canonical(value[k])}" for k in sorted(value))
            + "}"
        )
    raise TypeError(f"no canonical form for a {type(value).__name__}")


def subtree_digest(node: Any) -> str:
    """The key a built subtree's answers are filed under (module docstring)."""
    tree = plain(node)
    runs: dict[int, int] = {}

    def renumber(d: dict) -> None:
        if d["flow_run"]:
            d["flow_run"] = runs.setdefault(d["flow_run"], len(runs) + 1)
        for child in d["children"]:
            renumber(child)

    renumber(tree)
    return hashlib.sha256(canonical(tree).encode("utf-8")).hexdigest()


def _first_content_id(node: Any) -> str | None:
    if node.content_id:
        return node.content_id
    return next((cid for c in node.children if (cid := _first_content_id(c))), None)


def _unplain(answer: Any) -> Any:
    """A recorded answer as the closure gave it: the non-finite floats ``plain``
    wrote as strings are floats again."""
    if isinstance(answer, dict):
        return {k: _unplain(v) for k, v in answer.items()}
    if answer in ("Infinity", "-Infinity", "NaN"):
        return float(answer)
    return answer


# --- the ledger -----------------------------------------------------------------


class ClosureLedger(Hooks):
    """Records the closure answers above, or answers every closure from them.

    Recording, each distinct question is kept once as
    ``{...question, "a": answer, "n": times asked, "at": {...}}``; ``at`` is for
    diagnosis only (the order first asked, and for a subtree its first
    ``content_id``) and is no part of the key. Replaying, *answers* holds the
    leaf closures' answers from ``measure/`` and this module's from
    ``measure-layout/``, and *fonts* is the font ledger to close while the
    generator runs.
    """

    def __init__(
        self, answers: dict[str, Any] | None = None, fonts: Any | None = None
    ) -> None:
        super().__init__()
        self.replay = answers is not None
        self.answers: dict[str, Any] = answers if answers is not None else {}
        self.fonts = fonts
        self.records: dict[str, dict] = {}

    def ask(self, question: dict, answer_fn: Callable[[], Any], at: dict) -> Any:
        key = dump_line(question)
        if self.replay:
            if key not in self.answers:
                raise KeyError(f"closure replay has no answer for {key}")
            return _unplain(self.answers[key])
        answer = answer_fn()
        written = plain(answer)
        record = self.records.get(key)
        if record is None:
            at = {"seq": len(self.records), **at}
            self.records[key] = {**question, "a": written, "n": 1, "at": at}
        else:
            if record["a"] != written:
                raise RuntimeError(f"two answers to one question: {key}")
            record["n"] += 1
        return answer

    def install(self) -> None:
        from md2ui import session
        from md2ui.pipeline import layout_generator, layout_render, render_measure
        from md2ui.pipeline import render_code_blocks as rcb

        ledger = self
        orig_plan = vars(rcb)["code_block_plan"]

        def code_block_plan(
            content: str, language: str | None, typeface: Any, theme: Any
        ) -> Any:
            q = {"q": "code_block", "language": language, "content": content}
            made: list = []

            def measure() -> dict:
                plan = orig_plan(content, language, typeface, theme)
                made.append(plan)
                answer = {f: getattr(plan, f) for f in _PLAN_FIELDS}
                return {**answer, "line_count": len(plan.lines)}

            answer = ledger.ask(q, measure, {})
            if made:
                return made[0]
            # Replayed: the geometry, with as many (unpainted) lines.
            fields = {f: answer[f] for f in _PLAN_FIELDS}
            return rcb.CodeBlockPlan(lines=((),) * answer["line_count"], **fields)

        # Every module that calls code_block_plan, each through its own import.
        for module in (rcb, render_measure, layout_render):
            self.patch(module, "code_block_plan", code_block_plan)
        self._subtree_closure(session, "make_layout_measurer", "layout_height")
        self._subtree_closure(session, "make_block_width_measurer", "block_width")
        if self.replay:
            self._replay_leaves(session)
            self._close_fonts(session, layout_generator.LayoutGenerator)

    def _subtree_closure(self, session: Any, factory: str, kind: str) -> None:
        """*factory*'s closure, asked as a *kind* question about a subtree."""
        orig = vars(session)[factory]
        ledger = self

        def make(node_index: dict, fonts: Any, theme: Any) -> Callable:
            inner = None if ledger.replay else orig(node_index, fonts, theme)

            # The generator asks with a subtree and a width, and nothing else.
            def measured(cell: Any, width: float) -> float:
                q = {"q": kind, "subtree": subtree_digest(cell), "width": float(width)}
                at = {"content_id": _first_content_id(cell)}
                return ledger.ask(q, lambda: inner(cell, width), at)  # type: ignore[misc]

            return measured

        self.patch(session, factory, make)

    def _replay_leaves(self, session: Any) -> None:
        """The three leaf-keyed closures, answered from measure/'s records."""
        ledger = self

        def leaf(kind: str) -> Callable:
            # md2ui's factory inputs (fonts, theme): the answers are recorded.
            def make(*_args: Any) -> Callable:
                def measured(node: Any, kv_role: str | None = None) -> Any:
                    q = leaf_question(kind, node, kv_role)
                    return ledger.ask(q, lambda: None, {})

                return measured

            return make

        def make_marker_measurer(*_args: Any) -> Callable:
            def measure_marker(props: dict) -> float:
                return ledger.ask(marker_question(props), lambda: None, {})

            return measure_marker

        self.patch(session, "make_width_measurer", leaf("leaf_min_width"))
        self.patch(session, "make_line_width_measurer", leaf("leaf_line_width"))
        self.patch(session, "make_marker_measurer", make_marker_measurer)

    def _close_fonts(self, session: Any, generator: type) -> None:
        """No font question while the width clamp and the generator run: what
        they measure, they measure through the replayed closures."""
        fonts = self.fonts
        if fonts is None:
            raise ValueError("a closure replay needs the font ledger it closes")
        orig_effective = vars(session)["effective_width"]
        orig_generate = vars(generator)["generate"]

        def effective_width(
            root: Any, theme: Any, font_set: Any, asked_width: float
        ) -> float:
            fonts.closed = True
            try:
                return orig_effective(root, theme, font_set, asked_width)
            finally:
                fonts.closed = False

        def generate(
            gen: Any,
            ast_root: Any,
            available_width: float,
            theme: Any = None,
            measure: Any = None,
            measure_width: Any = None,
            measure_line: Any = None,
            measure_marker: Any = None,
            measure_block: Any = None,
        ) -> Any:
            fonts.closed = True
            try:
                return orig_generate(
                    gen,
                    ast_root,
                    available_width,
                    theme,
                    measure,
                    measure_width,
                    measure_line,
                    measure_marker,
                    measure_block,
                )
            finally:
                fonts.closed = False

        self.patch(session, "effective_width", effective_width)
        self.patch(generator, "generate", generate)
