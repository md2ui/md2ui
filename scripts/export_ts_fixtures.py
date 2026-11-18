#!/usr/bin/env python3
"""Export the fixtures md2ui-ts is checked against: md2ui as the oracle.

md2ui-ts, the TypeScript client library md2ui is the reference implementation for,
ports the pipeline stage by stage and must reproduce md2ui's structure exactly. This writes what it
compares, for every `.md` under `data/markdown/tests` and `data/markdown/tests-render`
(the snapshot corpus, `grouper_snapshot.py`'s rule):

    manifest.json                      commit, dirty flag, date, corpus, phases, widths
    input/<path>                       every Markdown and THEME file read, byte-exact
    grouper/final/<doc>.json           ast.to_dict(), byte-identical to grouper_snapshot.py
    grouper/phases/<NN-phase-id>/<doc>.json   the tree after every phase of process()
    grouper/phases-spaced/…            the first of the two groupings a `+++` document gets
    split_criteria/calls.jsonl         every criteria question asked while grouping
    detector/calls.jsonl               every detector question asked while grouping
    targets/<doc>.json                 every action target, with its wire ordinal
    schema/grouping-ast.schema.json    the grouping AST's JSON Schema (contract C1)
    theme/<path>.json                  every THEME file of the corpus, resolved
    measure/<width>/<doc>.jsonl        every text question layout and placement ask
    measure-layout/<width>/<doc>.jsonl the generator's subtree heights and block
                                       widths, and every code-block plan
    layout/<width>/<doc>.json          the full LayoutNode tree, every field
    layout-generated/<width>/<doc>.json   the same tree before the bakes
    boxes/<width>/<doc>.json           every placed box, section, region and anchor
    fonts/<file>                       every font file md2ui measured with, copied
                                       byte-exact (a collection's face as a file of
                                       its own); the manifest's `fonts` maps each
                                       face and theme to its file (ts_fixture_fonts)

`<doc>` is the path under `data/markdown`, `/` written `__`, as the grouper
snapshot names it. Widths are the render snapshot's; its variants are exported
like widths, under `<width>-<variant>`. Floats are repr-exact; the three
non-finite floats are written as the strings "Infinity", "-Infinity", "NaN".
String offsets count code points (Python `str` indices).

A `measure/` question is keyed by every field but its answer `a` and count `n`.
Two fields appear only where they apply, so a question without them is asked
as before: `scale_x`, the horizontal stretch of a font that has one (an `Emoji
gap` is a space stretched to the gap), and `"shaped": true` on the `advance` of
an emoji run holding a sequence its font joins into one glyph (a joined emoji,
a flag, a skin tone, a keycap): the whole run's width as drawn, which is not
the sum of its characters'.

A question's `face` is md2ui's face key, `family|PostScript name|weight|width|slant`.
An instance of a variable font (an icon font's `Emoji weight`, `fill`, `grade`,
`optical size`) is keyed by the PostScript name the system gives the instance:
the font's own, then `_<tag><value>` per axis in the font's order, the value the
coordinate as upper-case 16.16 fixed-point hex (32-bit two's complement), empty at
the axis's default; its weight is its `wght`. So `wght` 500 and `opsz` 20 of
`MaterialDesignIconsmd2ui-Regular` is
`MaterialDesignIconsmd2ui-Regular_FILL_GRAD_opsz140000_wght1F40000|500`. The
manifest's `fonts.axes` gives each such key's file and coordinates.

Usage:
    uv run python scripts/export_ts_fixtures.py <out> [input] [grouping] [theme] [layout] [fonts]

With no stage named, all five run. A stage rewrites only its own directories.
`fonts` reads what `layout` recorded, so it runs after it.
Two runs differ only in the manifest's `date`.
"""

from __future__ import annotations

import datetime
import shutil
import subprocess
import sys
import time
from pathlib import Path

from grouper_snapshot import CORPUS, MARKDOWN
from render_snapshot import VARIANTS, WIDTHS
from ts_fixture_fonts import export_fonts
from ts_fixture_layout import run_jobs
from ts_fixture_capture import (
    CallRecorder,
    PhaseRecorder,
    dump_json,
    dump_line,
    installed,
    phase_dir,
    plain,
)

ROOT = Path(__file__).resolve().parent.parent
# 2: the font files, `fonts/` and the manifest's `fonts`.
# 3: `fonts.families`, the family names md2ui resolves to another family's face.
# 4: `scale_x` and `shaped` on a text question (see the module docstring);
# later, additively, `fonts.axes`: the coordinates of a variable font's instance.
FORMAT_VERSION = 4
STAGES = ("input", "grouping", "theme", "layout", "fonts")
STAGE_DIRS = {
    "input": ("input",),
    "grouping": (
        "grouper",
        "split_criteria",
        "detector",
        "targets",
        "schema",
    ),
    "theme": ("theme",),
    "layout": ("measure", "measure-layout", "layout", "layout-generated", "boxes"),
    "fonts": ("fonts",),
}


def doc_key(path: Path) -> str:
    """A document's fixture name: its path under data/markdown, `/` as `__`."""
    return str(path.relative_to(MARKDOWN).with_suffix("")).replace("/", "__")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


# --- grouping -----------------------------------------------------------------


def export_grouping(out: Path) -> dict[str, dict]:
    """Final trees, per-phase trees, criteria and detector calls and action targets."""
    from md2ui.pipeline.data_point_detector import DataPointDetector
    from md2ui.pipeline.grouper_split_criteria import SplitCriteria
    from md2ui.pipeline.render_actions import action_targets
    from md2ui.pipeline.markdown_grouper import MarkdownGrouper
    from ts_fixture_schema import GROUPING_AST_SCHEMA

    # Bare criteria and detector, as grouper_snapshot.py hands them: `process` then memoizes
    # per call, so a recorded `memo_hit` means a repeat within the document,
    # not one answered from an earlier document (the kit's memo is shared).
    criteria, detector = SplitCriteria(), DataPointDetector()
    criteria_lines: list[str] = []
    detector_lines: list[str] = []
    info: dict[str, dict] = {}
    for path in CORPUS:
        key = doc_key(path)
        text = path.read_text()
        # The final tree exactly as grouper_snapshot.py makes it: no hooks.
        grouper = MarkdownGrouper(text)
        grouper.process(criteria, detector)
        assert grouper.ast is not None
        final = grouper.ast.to_dict()
        _write(out / "grouper" / "final" / f"{key}.json", dump_json(final))

        # Again with every hook on; it must arrive at the same tree.
        calls, phases = CallRecorder(), PhaseRecorder()
        with installed(calls, phases):
            hooked = MarkdownGrouper(text)
            hooked.process(criteria, detector)
        assert hooked.ast is not None
        if hooked.ast.to_dict() != final:
            raise RuntimeError(f"{key}: recording the grouper changed its output")
        # A `+++` document is grouped twice, with its spacers and then without;
        # the second pass is the one its final tree comes from.
        for folder, trees in zip(("phases-spaced", "phases"), phases.passes[-2:]):
            if len(phases.passes) == 1:
                folder = "phases"
            for index, (name, tree) in enumerate(zip(phases.names, trees)):
                _write(
                    out / "grouper" / folder / phase_dir(index, name) / f"{key}.json",
                    dump_json(tree),
                )
        for seq, call in enumerate(calls.criteria):
            criteria_lines.append(dump_line({"doc": key, "seq": seq, **call}))
        for seq, call in enumerate(calls.detector):
            detector_lines.append(dump_line({"doc": key, "seq": seq, **call}))

        targets = [
            {
                "ordinal": ordinal,
                "key": t.key,
                "node_id": t.key.split("#", 1)[0],
                "inline_link": int(t.key.split("#", 1)[1]) if "#" in t.key else None,
                "disabled": t.disabled,
                "action": plain(t.action),
            }
            for ordinal, t in enumerate(action_targets(final))
        ]
        _write(out / "targets" / f"{key}.json", dump_json(targets))
        info[key] = {
            "criteria_calls": len(calls.criteria),
            "detector_calls": len(calls.detector),
            "passes": len(phases.passes),
            "targets": len(targets),
        }

    _write(out / "split_criteria" / "calls.jsonl", "\n".join(criteria_lines) + "\n")
    _write(out / "detector" / "calls.jsonl", "\n".join(detector_lines) + "\n")
    _write(out / "schema" / "grouping-ast.schema.json", dump_json(GROUPING_AST_SCHEMA))
    return info


# --- inputs -----------------------------------------------------------------


def input_path(path: Path) -> str:
    """Where a source file is copied under ``<out>``: ``input/`` and its path
    under data/markdown, or under the repo for the root THEME.md."""
    path = path.resolve()
    base = MARKDOWN if path.is_relative_to(MARKDOWN) else ROOT
    return f"input/{path.relative_to(base)}"


def export_inputs(out: Path) -> int:
    """Every file the other stages read, copied byte-exact, so the fixtures
    hold their own inputs at the commit they were made from."""
    sources = sorted(set(CORPUS) | set(theme_files()))
    for path in sources:
        target = out / input_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return len(sources)


# --- themes -------------------------------------------------------------------


def theme_files() -> list[Path]:
    """Every THEME file a corpus document can render with: the corpus's own, and
    the repo-root default the CLI falls back to (resolve_theme_path)."""
    own = sorted(
        p
        for root in (MARKDOWN / "tests", MARKDOWN / "tests-render")
        for p in root.rglob("THEME*.md")
    )
    return [ROOT / "THEME.md", *own]


def theme_key(path: Path | None) -> str:
    """A theme's fixture name: its repo path, `/` as `__`; `_defaults` for none."""
    if path is None:
        return "_defaults"
    return str(path.resolve().relative_to(ROOT).with_suffix("")).replace("/", "__")


def export_themes(out: Path) -> list[str]:
    """The resolved theme of every THEME file, and the parser's defaults."""
    from md2ui import session

    rel_root = str(ROOT) + "/"
    keys = []
    for path in [None, *theme_files()]:
        theme = session.load_theme(path)
        key = theme_key(path)
        _write(out / "theme" / f"{key}.json", dump_json(plain(theme, rel_root)))
        keys.append(key)
    return keys


def export_theme_fonts(out: Path) -> dict:
    """The font files every face md2ui measured with in ``measure/`` comes from,
    and the manifest's ``fonts`` entry (ts_fixture_fonts)."""
    from md2ui import session

    rel_root = str(ROOT) + "/"
    loaded = {theme_key(path): session.load_theme(path) for path in theme_files()}
    themes = {key: (theme, plain(theme, rel_root)) for key, theme in loaded.items()}
    doc_themes = {
        doc_key(path): theme_key(session.resolve_theme_path(path, None))
        for path in CORPUS
    }
    return export_fonts(out, themes, doc_themes)


# --- layout -------------------------------------------------------------------


def layout_jobs() -> list[tuple[str, int, str, list[str]]]:
    """``(document, width, label, flags)``: the corpus at every width, then the
    render snapshot's variants, each labelled ``<width>-<name>``."""
    jobs = [
        (str(path.relative_to(ROOT)), width, str(width), [])
        for path in CORPUS
        for width in WIDTHS
    ]
    for name, document, width, flags in VARIANTS:
        jobs.append((document, width, f"{width}-{name}", flags))
    return jobs


# --- the manifest -------------------------------------------------------------


def manifest(stages: list[str], stats: dict, fonts: dict | None) -> dict:
    from md2ui import session
    from ts_fixture_capture import EXPECTED_PHASES

    def theme_entry(path: Path | None) -> dict:
        """A theme's key, repo path and input path; all but the key are None
        for the parser's defaults."""
        return {
            "theme": theme_key(path),
            "theme_path": None
            if path is None
            else str(path.resolve().relative_to(ROOT)),
            "theme_input": None if path is None else input_path(path),
        }

    return {
        "format_version": FORMAT_VERSION,
        "md2ui_commit": _git("rev-parse", "HEAD"),
        "md2ui_dirty": bool(_git("status", "--porcelain", "--", "src", "scripts")),
        "date": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "stages": stages,
        "corpus": [
            {
                "doc": doc_key(path),
                "path": str(path.relative_to(ROOT)),
                "input": input_path(path),
                **theme_entry(session.resolve_theme_path(path, None)),
            }
            for path in CORPUS
        ],
        "themes": [theme_entry(path) for path in [None, *theme_files()]],
        "phases": [
            {"dir": phase_dir(i, name), "phase": name}
            for i, name in enumerate(EXPECTED_PHASES)
        ],
        "widths": list(WIDTHS),
        "variants": [
            {"name": name, "doc": document, "width": width, "flags": flags}
            for name, document, width, flags in VARIANTS
        ],
        "string_offsets": "code points",
        # How measure-layout/ is keyed; ts_fixture_closures' docstring defines
        # the subtree digest.
        "measure_layout": {
            "layout_height": ["subtree", "width"],
            "block_width": ["subtree", "width"],
            "code_block": ["language", "content"],
            "subtree": "sha256 of the canonical fixture form, flow_run renumbered",
        },
        "non_finite_floats": ["Infinity", "-Infinity", "NaN"],
        # `faces`: face key -> its file under fonts/, or null for a face md2ui
        # reached only as a per-glyph system fallback; `files`: each file's face,
        # sha256 and source; `themes`: theme key -> the faces its documents used;
        # `families`: theme key -> each family name md2ui resolves by name to a
        # face of another family (`monospace` -> `Courier`); `axes`: face key ->
        # `{tag: coordinate}` for an instance of a variable font, whose `faces`
        # entry is the font's own file (ts_fixture_fonts).
        "fonts": fonts,
        "stats": stats,
    }


def main() -> int:
    if len(sys.argv) < 2 or any(a not in STAGES for a in sys.argv[2:]):
        print(__doc__)
        return 2
    out = Path(sys.argv[1]).resolve()
    # In STAGES order whatever the order named: `fonts` reads what `layout` wrote.
    stages = [s for s in STAGES if s in sys.argv[2:]] or list(STAGES)
    # The CLI resolves a document's theme beside it, then in the working
    # directory: the repo root, as for the render snapshot.
    import os

    os.chdir(ROOT)
    stats: dict = {}
    fonts: dict | None = None
    for stage in stages:
        for name in STAGE_DIRS[stage]:
            shutil.rmtree(out / name, ignore_errors=True)
        began = time.perf_counter()
        if stage == "input":
            stats["input"] = export_inputs(out)
        elif stage == "grouping":
            stats["grouping"] = export_grouping(out)
        elif stage == "theme":
            stats["theme"] = export_themes(out)
        elif stage == "layout":
            stats["layout"] = run_jobs(out, layout_jobs())
        else:
            fonts = export_theme_fonts(out)
        print(f"{stage}: {time.perf_counter() - began:.1f}s")
    previous = out / "manifest.json"
    if previous.exists():
        import json

        old = json.loads(previous.read_text())
        stats = {**old.get("stats", {}), **stats}
        fonts = fonts if "fonts" in stages else old.get("fonts")
        stages = [s for s in STAGES if s in stages or s in old.get("stages", [])]
    _write(previous, dump_json(manifest(stages, stats, fonts)))
    print(f"{len(CORPUS)} documents -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
