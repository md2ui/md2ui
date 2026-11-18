"""Layout and placement fixtures for `export_ts_fixtures.py`, under recorded text.

md2ui-ts measures text with a different engine, so its layout is compared with
md2ui's under REPLAYED measurements: every question md2ui asks of a font while it
lays out and places one document at one width is recorded with its answer, and
the port answers the same questions with md2ui's answers.

The questions are recorded at the bottom, where they reach Skia (see
:class:`TextMeasure`), because that is the one boundary every measuring path
crosses: the five closures the generator is handed, ``natural_height`` and
``place_boxes``, and the helpers in ``render_metrics`` / ``render_measure`` /
``render_glyph_faces`` all end in a ``skia.Font`` or a glyph lookup. Three closure
answers are recorded beside them as well, for the measurer interface the port
designs; replay never reads those.

Each ``(document, width)`` runs in a fresh process, as the render snapshot does:
md2ui memoizes word widths, wraps and glyph faces per process, and a question a
memo answered is a question the recording never sees. A fresh process asks every
question its layout needs, and so does its replay.

The generator's own closure answers (heights and block widths of built
subtrees, code-block plans) are recorded beside the text in ``measure-layout/``
by :class:`ts_fixture_closures.ClosureLedger`; a second replay answers the
generator from those alone.

Run as a worker by ``run_jobs``:
    python ts_fixture_layout.py record|replay|replay-closures <out> <doc> <width> <label> [flags]
"""

from __future__ import annotations

import collections
import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import skia  # type: ignore[import-untyped]

from ts_fixture_capture import Hooks, dump_json, dump_line, installed, plain
from ts_fixture_closures import LEAF_KINDS, ClosureLedger, note_leaf_closures

ROOT = Path(__file__).resolve().parent.parent
_SKIA_FONT = skia.Font
# Font methods that measure and are not hooked. The layout path does not call
# them at this commit; if it starts to, the recording would be incomplete, so
# they raise.
_UNHOOKED = tuple(
    (
        "getWidths getWidthsBounds getBounds getPos getXPos getPath getPaths "
        "textToGlyphs countText unicharToGlyph unicharsToGlyphs getSpacing"
    ).split()
)
_METRICS = tuple(
    (
        "fAscent fAvgCharWidth fBottom fCapHeight fDescent fFlags fLeading "
        "fMaxCharWidth fStrikeoutPosition fStrikeoutThickness fTop "
        "fUnderlinePosition fUnderlineThickness fXHeight fXMax fXMin"
    ).split()
)


class StandIn:
    """A system face during replay: a name, never a font."""

    def __init__(self, name: str) -> None:
        self.name = name


def face_name(tf: Any) -> str:
    """A face's stable name: family | PostScript name | weight | width | slant."""
    if isinstance(tf, StandIn):
        return tf.name
    if tf is None:
        return "default"
    style = tf.fontStyle()
    return "|".join(
        (
            tf.getFamilyName(),
            tf.getPostScriptName(),
            str(style.weight()),
            str(style.width()),
            str(int(style.slant())),
        )
    )


class TextMeasure(Hooks):
    """Records every text question, or answers each one from a recording.

    The questions, each keyed by everything its answer depends on:

    * ``advance``: ``Font(face, size).measureText(text)``, the advance width;
    * ``ink``: the same call with a bounds rect, the advance plus the ink box;
    * ``metrics``: ``Font(face, size).getMetrics()``, every field;
    * ``outline``: the advance plus the exact ink box of the glyph outlines
      (``render_metrics._outline_ink``: a ring label's fit, and through
      ``_text_ink`` a list marker's or quote character's ink), unrounded;
    * ``has_glyph``: does ``face`` map code point ``cp`` to a glyph
      (``render_glyph_faces._has_glyph``);
    * ``system_face``: the platform face that draws ``cp`` in ``like``'s style,
      or none (``render_glyph_faces._system_face``).

    A font stretched horizontally keys its ``advance``, ``ink`` and ``metrics``
    questions with ``scale_x`` as well; an unstretched one has no such field. An
    emoji run HarfBuzz shapes (``render_shaping``) is one ``advance`` question
    marked ``shaped``: its width, as md2ui's ``run_advance`` gives it.

    In replay mode a question missing from the recording raises, so a replay
    that finishes was answered entirely from it. Recording also notes three
    closure answers for reference (:meth:`note`); replay never reads them.
    """

    def __init__(self, answers: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.replay = answers is not None
        self.answers: dict[str, Any] = answers if answers is not None else {}
        self.records: dict[str, dict] = {}
        self.callers: collections.Counter = collections.Counter()
        self._faces: dict[str, Any] = {}  # name -> the one object it names
        # Set while the generator runs under closure replay: it may measure
        # only through its closures, so a font question then is an escape.
        self.closed = False

    # -- the ledger --------------------------------------------------------
    def ask(self, question: dict, answer_fn: Callable[[], Any]) -> Any:
        key = dump_line(question)
        if self.closed:
            raise RuntimeError(f"a font question inside the generator: {key}")
        if self.replay:
            if key not in self.answers:
                raise KeyError(f"replay has no answer for {key}")
            return self.answers[key]
        answer = answer_fn()
        record = self.records.get(key)
        if record is None:
            self.records[key] = {**question, "a": answer, "n": 1}
            # Who asked: the md2ui function two frames up (hook, then caller).
            frame = sys._getframe(2)
            module = frame.f_globals.get("__name__", "?").rsplit(".", 1)[-1]
            self.callers[(question["q"], f"{module}.{frame.f_code.co_name}")] += 1
        else:
            if record["a"] != answer:
                raise RuntimeError(f"two answers to one question: {key}")
            record["n"] += 1
        return answer

    def note(self, question: dict, answer: Any) -> None:
        """A closure's answer, recorded for reference; replay never reads it."""
        key = dump_line(question)
        record = self.records.setdefault(key, {**question, "a": plain(answer), "n": 0})
        if record["a"] != plain(answer):
            raise RuntimeError(f"two answers to one question: {key}")
        record["n"] += 1

    def _face(self, name: str) -> Any:
        """The one object system face *name* is: the real face once recorded, a
        stand-in made on first use in replay."""
        return self._faces.setdefault(name, StandIn(name))

    # -- the hooks ----------------------------------------------------------
    def install(self) -> None:
        from md2ui.pipeline import render_glyph_faces as rgf
        from md2ui.pipeline import render_metrics as rm
        from md2ui.pipeline import render_ring_text as rr
        from md2ui.pipeline import render_shaping as rs

        self.patch(skia, "Font", self._font_class())
        orig_has = vars(rgf)["_has_glyph"]
        orig_system = vars(rgf)["_system_face"]
        orig_run_advance = vars(rgf)["run_advance"]
        orig_outline = vars(rm)["_outline_ink"]
        ledger = self

        def _has_glyph(face: Any, ch: str) -> bool:
            q = {"q": "has_glyph", "face": face_name(face), "cp": ord(ch)}
            return ledger.ask(q, lambda: orig_has(face, ch))

        def _system_face(ch: str, like: Any) -> Any:
            q = {"q": "system_face", "like": face_name(like), "cp": ord(ch)}
            found: list = []

            def measure() -> dict | None:
                face = orig_system(ch, like)
                found.append(face)
                if face is None:
                    return None
                name = face_name(face)
                if face is not like and name == face_name(like):
                    raise RuntimeError("a system face indistinguishable from its like")
                if ledger._faces.setdefault(name, face) is not face:
                    raise RuntimeError(f"two face objects share the name {name!r}")
                return {"face": name, "is_like": face is like}

            answer = ledger.ask(q, measure)
            if found:
                return found[0]
            # Replayed, or a repeat answered from the ledger: the face it named.
            if answer is None:
                return None
            return like if answer["is_like"] else ledger._face(answer["face"])

        def run_advance(run: str, font: Any, shape: bool) -> float:
            # The run HarfBuzz shapes is the run render_shaping's own test
            # finds a sequence in; every other run is measured by measureText,
            # which asks its own question.
            if not (shape and rs._SEQUENCE.search(run)):
                return orig_run_advance(run, font, shape)
            q = {**font.question("advance"), "text": run, "shaped": True}

            def measure() -> float:
                # The shaped glyphs' widths, from a font no hook stands in for.
                real = _SKIA_FONT(font.getTypeface(), font.getSize(), font.scale_x, 0.0)
                return orig_run_advance(run, real, shape)

            return ledger.ask(q, measure)

        self.patch(rgf, "_has_glyph", _has_glyph)
        self.patch(rgf, "_system_face", _system_face)

        def _outline_ink(text: str, font: Any) -> tuple[float, Any]:
            def measure() -> list:
                # The outlines of a real font at the asked face, size and hinting.
                real = _SKIA_FONT(font.getTypeface(), font.getSize(), font.scale_x, 0.0)
                real.setHinting(font.getHinting())
                width, box = orig_outline(text, real)
                return [width, box.left(), box.top(), box.right(), box.bottom()]

            width, *ltrb = ledger.ask(
                {**font.question("outline"), "text": text}, measure
            )
            return width, skia.Rect.MakeLTRB(*ltrb)

        self.patch(rgf, "run_advance", run_advance)
        # One question, wherever it is read: render_metrics' own callers
        # (_text_ink) and render_ring_text's imported name.
        for owner in (rm, rr):
            self.patch(owner, "_outline_ink", _outline_ink)
        if not self.replay:
            self._note_closures()

    def _font_class(self) -> type:
        ledger = self

        class Font(_SKIA_FONT):
            def __init__(
                self,
                typeface: Any = None,
                size: float = 12.0,
                scaleX: float = 1.0,
                skewX: float = 0.0,
            ) -> None:
                if skewX != 0:
                    raise TypeError("Font: a skew at construction is not hooked")
                real = None if isinstance(typeface, StandIn) else typeface
                # A replayed font is a real font of the WRONG face and size:
                # anything that measures with it without asking the ledger
                # gets a different answer, and the replay comparison fails.
                super().__init__(
                    *((None, 1.0) if ledger.replay else (real, size, scaleX, skewX))
                )
                self._tf = typeface
                self._size = float(size)
                self.scale_x = float(scaleX)
                if typeface is None:
                    self._tf = _SKIA_FONT(None, size).getTypeface()
                self._name = face_name(self._tf)

            def getTypeface(self) -> Any:
                return self._tf

            def getSize(self) -> float:
                return self._size

            def question(self, q: str) -> dict:
                """A question about this font: its face and size, and its
                stretch only when it has one, so an unstretched font asks
                what it asked before stretching was hooked."""
                asked = {"q": q, "face": self._name, "size": self._size}
                if self.scale_x != 1:
                    asked["scale_x"] = self.scale_x
                return asked

            def measureText(
                self,
                text: str,
                encoding: Any = skia.TextEncoding.kUTF8,
                bounds: Any = None,
                paint: Any = None,
            ) -> float:
                if (
                    not isinstance(text, str)
                    or encoding != skia.TextEncoding.kUTF8
                    or paint is not None
                ):
                    raise TypeError("measureText: only UTF-8 str, no paint, is hooked")
                kind = "advance" if bounds is None else "ink"
                q = {**self.question(kind), "text": text}
                if bounds is None:
                    return ledger.ask(q, lambda: _SKIA_FONT.measureText(self, text))

                def measure() -> list:
                    box = skia.Rect()
                    width = _SKIA_FONT.measureText(self, text, encoding, box)
                    return [width, box.left(), box.top(), box.right(), box.bottom()]

                width, *ltrb = ledger.ask(q, measure)
                bounds.setLTRB(*ltrb)
                return width

            def getMetrics(self) -> Any:
                q = self.question("metrics")

                def measure() -> dict:
                    m = _SKIA_FONT.getMetrics(self)
                    return {f: getattr(m, f) for f in _METRICS}

                return _Metrics(ledger.ask(q, measure))

        # Calling a measuring method that is not hooked raises TypeError
        # ('NoneType' object is not callable) instead of measuring unrecorded.
        for name in _UNHOOKED:
            setattr(Font, name, None)
        return Font

    def _note_closures(self) -> None:
        """Note the generator's three node-keyed closures' answers, for reference."""
        note_leaf_closures(self, self.note)


class _Metrics:
    """``skia.FontMetrics``' fields, from a recorded answer."""

    def __init__(self, fields: dict) -> None:
        self.__dict__.update(fields)


# --- one job ------------------------------------------------------------------


class _PreBake(Hooks):
    """Each generated tree, serialized before the bakes edit it in place.

    ``Layout: Auto`` builds a band's two layouts and shows one, so the tree kept for a
    scene is the one baked into it, not the last one built.
    """

    def __init__(self) -> None:
        super().__init__()
        # (the baked root, its tree before the bakes); the root is held, so its id
        # cannot be reused while it is looked up.
        self.trees: list[tuple[Any, str]] = []

    def install(self) -> None:
        from md2ui import session

        orig = vars(session)["bake_render_cascade"]

        def bake_render_cascade(node: Any, theme: Any) -> Any:
            self.trees.append((node, dump_json(plain(node))))
            return orig(node, theme=theme)

        self.patch(session, "bake_render_cascade", bake_render_cascade)

    def tree_of(self, layout: Any) -> str:
        """The tree *layout* was before its bakes."""
        return next(tree for node, tree in self.trees if node is layout)


def _scene(
    doc: str,
    width: int,
    flags: list[str],
    ledger: TextMeasure,
    closures: ClosureLedger | None = None,
) -> dict:
    """Lay out and place *doc* at *width* exactly as `md2ui render` does."""
    from md2ui import session
    from md2ui.main import _parser
    from md2ui.pipeline.layout_generator import LayoutGenerator
    from md2ui.pipeline.render_settings import VIEW

    md = ROOT / doc
    args = _parser().parse_args(["render", doc, *flags])
    pre_bake = _PreBake()
    hooks = (ledger, pre_bake) if closures is None else (ledger, closures, pre_bake)
    with installed(*hooks):
        theme = session.load_theme(session.resolve_theme_path(md, None))
        fonts = session.load_fonts(theme)
        ast = session.group_markdown(md.read_text(), session.load_grouping_kit())
        if ast is None:
            raise RuntimeError(f"{doc}: the grouper made no tree")
        root, node_index = session.prepare(ast, theme)
        VIEW.wireframe = args.wireframe
        VIEW.debug_spacing = args.debug
        VIEW.debug_padding = args.debug_padding
        VIEW.text_boxes = args.text_boxes
        scene = session.build_scene(
            LayoutGenerator(), root, node_index, theme, fonts, width
        )
    boxes = {
        "asked_width": width,
        "width": scene.width,
        "height": scene.height,
        "boxes": scene.boxes,
        "sections": scene.sections,
        "regions": scene.regions,
        "anchors": scene.anchors,
        "scrollables": scene.scrollables,
    }
    return {
        "layout": dump_json(plain(scene.layout)),
        "layout-generated": pre_bake.tree_of(scene.layout),
        "boxes": dump_json(plain(boxes)),
    }


def replay_answers(records: Iterable[dict]) -> dict[str, Any]:
    """The answers a replaying :class:`TextMeasure` is built with, from recorded
    question records: each question's key, without its answer, its count and
    its diagnosis (``at``)."""
    return {
        dump_line({k: v for k, v in record.items() if k not in ("a", "n", "at")}): (
            record["a"]
        )
        for record in records
    }


def _read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().split("\n")[:-1]]


def _write_records(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{dump_line(r)}\n" for r in records))


def _counts(records: Iterable[dict]) -> dict:
    """Distinct questions and times asked, by kind."""
    distinct: collections.Counter = collections.Counter()
    asked: collections.Counter = collections.Counter()
    for r in records:
        distinct[r["q"]] += 1
        asked[r["q"]] += r["n"]
    return {"distinct": distinct, "asked": asked}


def worker(argv: list[str]) -> int:
    mode, out, doc, width, label, *flags = argv
    os.chdir(ROOT)
    out_dir = Path(out)
    key = str(Path(doc).relative_to("data/markdown").with_suffix("")).replace("/", "__")
    measure_file = out_dir / "measure" / label / f"{key}.jsonl"
    closure_file = out_dir / "measure-layout" / label / f"{key}.jsonl"
    if mode == "record":
        ledger, closures = TextMeasure(), ClosureLedger()
        files = _scene(doc, int(width), flags, ledger, closures)
        _write_records(measure_file, ledger.records.values())
        _write_records(closure_file, closures.records.values())
        for name, text in files.items():
            path = out_dir / name / label / f"{key}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        callers = [[q, c, n] for (q, c), n in ledger.callers.items()]
        counts = _counts(ledger.records.values())
        closure_counts = _counts(closures.records.values())
        print(json.dumps({**counts, "callers": callers, "closures": closure_counts}))
        return 0
    measured = _read_records(measure_file)
    if mode == "replay":
        files = _scene(doc, int(width), flags, TextMeasure(replay_answers(measured)))
    else:  # replay-closures: the generator answered from the closure records only
        fonts = TextMeasure(replay_answers(measured))
        leaves = [r for r in measured if r["q"] in LEAF_KINDS]
        answers = replay_answers([*leaves, *_read_records(closure_file)])
        files = _scene(doc, int(width), flags, fonts, ClosureLedger(answers, fonts))
    for name, text in files.items():
        if (out_dir / name / label / f"{key}.json").read_text() != text:
            print(json.dumps({"mismatch": name}))
            return 1
    print(json.dumps({"replayed": len(files)}))
    return 0


# --- every job ----------------------------------------------------------------

Job = tuple[str, int, str, list[str]]  # document, width, label, CLI flags


def _run(mode: str, out: Path, job: Job) -> dict:
    doc, width, label, flags = job
    proc = subprocess.run(
        [sys.executable, __file__, mode, str(out), doc, str(width), label, *flags],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    last = proc.stdout.strip().splitlines()[-1:]
    if proc.returncode != 0 or not last:
        return {"error": f"{mode} {label} {doc}: {proc.stderr[-800:]}{''.join(last)}"}
    return json.loads(last[0])


def run_jobs(out: Path, jobs: list[Job]) -> dict:
    """Record every job, then replay every job against its recording twice:
    with the font answers alone, and with the generator's closures answered
    from their records (``replay-closures``).

    Returns per-label, per-document question counts; raises if any job failed
    to record, or replayed to anything but what it recorded.
    """
    workers = max(1, (os.cpu_count() or 2) - 1)
    replays = [(mode, job) for job in jobs for mode in ("replay", "replay-closures")]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        recorded = list(pool.map(lambda job: _run("record", out, job), jobs))
        replayed = list(pool.map(lambda mj: _run(mj[0], out, mj[1]), replays))
    stats: dict = {}
    callers: collections.Counter = collections.Counter()
    errors = [
        json.dumps(result)
        for result in recorded + replayed
        if "error" in result or "mismatch" in result
    ]
    for job, rec in zip(jobs, recorded):
        if "distinct" in rec:
            doc, label = job[0], job[2]
            counts = {
                "distinct": rec["distinct"],
                "asked": rec["asked"],
                "measure_layout": rec["closures"],
            }
            stats.setdefault(label, {})[doc] = counts
            for q, caller, n in rec["callers"]:
                callers[(q, caller)] += n
    table = [
        {"q": q, "caller": c, "distinct": n} for (q, c), n in sorted(callers.items())
    ]
    (out / "measure" / "callers.json").write_text(dump_json(table))
    for line in errors:
        print(f"  FAIL  {line}")
    if errors:
        raise RuntimeError(f"{len(errors)} layout jobs failed to record or replay")
    return stats


if __name__ == "__main__":
    raise SystemExit(worker(sys.argv[1:]))
