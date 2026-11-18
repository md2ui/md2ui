#!/usr/bin/env python3
"""Score an eval run from `scripts/eval_run.py`: what can be counted, before the look.

Each answer is grouped through the real pipeline (`session.load_grouping_kit()`, as
`show` does) and scored on:

- `check`: errors, warnings and notes against the condition's answer contract;
- displays: charts, line charts, bars, rings, day chips, tables and pictures, as
  the grouper flags them (whether the theme draws each one is the digest's to say);
- fidelity: the share of the task's numbers the answer keeps, and the numbers it
  shows that trace to none of them;
- links: the task's URLs used as a picture, as a link, or left out;
- effort, from the runner: tool calls, `guide` topics read, cost.

An answer whose md2ui server did not connect, or whose agent call failed, is skipped
and named, never scored.

An answer is **clean** when `check` gives it no error and no warning. Per task, the
rate is clean answers out of N, and clean^k says whether all N were: a reply is seen
once, so a task an agent gets right two times in three is not done.

Usage:
    uv run python scripts/eval_score.py <run-dir> [--sheet] [--ledger FILE]
        [--suite NAME --theme DIR]

`<run-dir>` holds one `<model>[-<condition>]/` folder per model, or is one. Writes
`<run-dir>/scores.md`, and `<task>-r<k>.digest.txt` beside each answer (`show`'s digest,
to read a section drawn as something the author did not mean). `--sheet` renders any
answer without a PNG and tiles each model's into `<model>-sheet.png`. `--ledger` appends
one dated row per model to a suite's `scores.md` (`evals/<suite>/scores.md`).

A folder with no `manifest.json` (an eval run by hand, before the runner) is scored with
`--suite`, and `--theme` when its condition was not the root theme.

Two limits on fidelity, both deliberate: numbers match by value within the precision
the answer shows (`$274.5B` keeps 274,515,000,000), at any thousands scale (a table headed
`$B` shows it as `416.2`), so a coincidence can count as kept;
and an untraced number is often derived (a growth rate), not invented — the count says
where to look, the transcript and the data decide.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from eval_run import EVALS, ROOT, render, split_tasks

_URL = re.compile(r"(?:https?|agent):[^\s)>`\]]+")
_NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?"
    r"\s?(trillion|billion|million|thousand|bn|[kKmMbBtT](?![a-zA-Z]))?"
)
_SCALE = {
    "k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6,
    "b": 1e9, "bn": 1e9, "billion": 1e9, "t": 1e12, "trillion": 1e12,
}  # fmt: skip
# Displays as the grouper flags them, by the noun a reader would use.
_DISPLAYS = {
    "line_chart": "line charts",
    "kv_percent_bar": "bars",
    "ratio_bar": "bars",
    "unit_ratio": "rings",
    "date_chip": "chips",
}


@dataclass(frozen=True)
class Number:
    """A number as shown: its value, and half a unit of its last shown digit."""

    value: float
    slack: float


def numbers(text: str) -> list[Number]:
    """Every number shown in *text*, URLs left out. Signs are dropped (`−0.7%` and
    `-0.7%` are the same figure written two ways), and so are the integers 0–9:
    as ordinals and counts they match anything."""
    found = []
    for match in _NUMBER.finditer(_URL.sub(" ", text)):
        whole, decimals, suffix = match.groups()
        scale = _SCALE.get((suffix or "").lower(), 1.0)
        value = float(whole.replace(",", "") + (f".{decimals}" if decimals else ""))
        if decimals is None and value < 10 and scale == 1.0:
            continue
        slack = 0.5 * 10 ** -len(decimals or "") * scale
        found.append(Number(value * scale, slack))
    return found


# A table headed `$B` shows 416,161,000,000 as `416.2`: the unit is in the header.
_IMPLIED = (1.0, 1e3, 1e6, 1e9, 1e12)


def _matches(shown: Number, values: list[Number]) -> bool:
    return any(
        abs(shown.value * k - v.value) <= shown.slack * k
        for v in values
        for k in _IMPLIED
    )


def fidelity(data: str, answer: str) -> tuple[float, int]:
    """The share of *data*'s distinct numbers *answer* keeps, and how many distinct
    numbers it shows that none of them rounds to."""
    given = list({n.value: n for n in numbers(data)}.values())
    shown = list({n.value: n for n in numbers(answer)}.values())
    kept = sum(1 for g in given if any(_matches(s, [g]) for s in shown))
    untraced = sum(1 for s in shown if not _matches(s, given))
    return (kept / len(given) if given else 1.0), untraced


def links(data: str, answer: str) -> dict[str, int]:
    """The task's http URLs, by how the answer used them."""
    urls = {u for u in _URL.findall(data) if u.startswith("http")}
    pictures = {u for u in urls if re.search(rf"!\[[^\]]*\]\({re.escape(u)}", answer)}
    linked = {u for u in urls - pictures if f"({u}" in answer}
    return {
        "pictures": len(pictures),
        "links": len(linked),
        "unused": len(urls - pictures - linked),
    }


def displays(node, into: dict[str, int] | None = None) -> dict[str, int]:
    """What the grouped answer draws, by noun."""
    into = into if into is not None else {}
    noun = "charts" if node.chart_group else _DISPLAYS.get(node.datapoint_display or "")
    noun = "line charts" if node.line_group else noun
    noun = noun or {"table_header": "tables", "image": "pictures"}.get(node.type)
    if noun:
        into[noun] = into.get(noun, 0) + 1
    for child in node.children:
        displays(child, into)
    return into


@dataclass
class Score:
    model: str
    task: str
    trial: str
    errors: int = 0
    warnings: int = 0
    notes: int = 0
    codes: list[str] = field(default_factory=list)
    drawn: dict[str, int] = field(default_factory=dict)
    kept: float = 1.0
    untraced: int = 0
    urls: dict[str, int] = field(default_factory=dict)
    calls: int | None = None
    guide: list[str] = field(default_factory=list)
    cost: float | None = None

    @property
    def clean(self) -> bool:
        return not self.errors and not self.warnings


def score(answer: Path, model: str, data: str, kit, contract, theme) -> Score:
    from md2ui import session
    from md2ui.check import check_grouped
    from md2ui.digest import digest

    text = answer.read_text()
    out = Score(model, *trial_of(answer))
    ast = session.group_markdown(text, kit)
    for issue in check_grouped(text, ast, contract):
        level = issue["level"]
        setattr(out, f"{level}s", getattr(out, f"{level}s") + 1)
        if level != "note":
            out.codes.append(issue["code"])
    if ast is not None:
        out.drawn = displays(ast)
        answer.with_suffix(".digest.txt").write_text(digest(ast, theme) + "\n")
    out.kept, out.untraced = fidelity(data, text)
    out.urls = links(data, text)
    spent = answer.with_suffix(".json")
    if spent.is_file():
        effort = json.loads(spent.read_text())
        out.calls = len(effort["tool_calls"])
        out.guide = effort["guide_topics"]
        revised = effort.get("after_advice", {})
        out.cost = (effort["cost_usd"] or 0) + (revised.get("cost_usd") or 0)
    return out


def unusable(answer: Path) -> str | None:
    """Why *answer* measures nothing, or None. An answer written without the md2ui
    server is the agent's guess at md2ui, not a measure of the notes; one whose
    agent call failed is the failure's text (a usage limit's 429), not an
    answer. Runs older than the runner's record of the server count as connected."""
    spent = answer.with_suffix(".json")
    if not spent.is_file():
        return None
    effort = json.loads(spent.read_text())
    if effort.get("server", "connected") != "connected":
        return f"the md2ui server was {effort['server']}"
    failed = [effort, effort.get("after_advice") or {}]
    if any(e.get("is_error") for e in failed):
        return "the agent's call failed"
    return None


_TRIAL = re.compile(r"(.+)-r(\d+)")


def trial_of(answer: Path) -> tuple[str, str]:
    """The task id and trial an answer is named for; a hand-run answer has no trial."""
    match = _TRIAL.fullmatch(answer.stem)
    return (match.group(1), match.group(2)) if match else (answer.stem, "1")


def _answers(run: Path) -> list[Path]:
    """The answers in *run*: every Markdown file but the scores written beside them
    and the replies `--show` kept from before the advice."""
    return sorted(
        p
        for p in run.glob("*.md")
        if p.name != "scores.md" and ".first" not in p.suffixes
    )


def _runs(root: Path) -> list[Path]:
    """The model folders under *root*, or *root* itself when it is one."""
    if _answers(root):
        return [root]
    return sorted(p for p in root.iterdir() if p.is_dir() and _answers(p))


def _drawn_words(drawn: dict[str, int]) -> str:
    return ", ".join(f"{n} {k}" for k, n in sorted(drawn.items())) or "-"


def _rows(scores: list[Score]) -> list[str]:
    head = [
        "| model | task | trial | clean | check | drawn | kept | untraced | urls p/l/- | calls | guide |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    return head + [
        f"| {s.model} | {s.task} | {s.trial} | {'yes' if s.clean else 'no'} "
        f"| {s.errors}e {s.warnings}w {s.notes}n {' '.join(s.codes)} "
        f"| {_drawn_words(s.drawn)} | {s.kept:.0%} | {s.untraced} "
        f"| {s.urls.get('pictures', 0)}/{s.urls.get('links', 0)}/{s.urls.get('unused', 0)} "
        f"| {'-' if s.calls is None else s.calls} | {', '.join(t or '()' for t in s.guide) or '-'} |"
        for s in scores
    ]


def _by_task(scores: list[Score]) -> dict[tuple[str, str], list[Score]]:
    groups: dict[tuple[str, str], list[Score]] = {}
    for s in scores:
        groups.setdefault((s.model, s.task), []).append(s)
    return groups


def _rates(scores: list[Score]) -> list[str]:
    head = [
        "| model | task | N | clean | clean^k | kept | untraced |",
        "|---|---|---|---|---|---|---|",
    ]
    rows = []
    for (model, task), group in _by_task(scores).items():
        clean = sum(s.clean for s in group)
        rows.append(
            f"| {model} | {task} | {len(group)} | {clean}/{len(group)} "
            f"| {'yes' if clean == len(group) else 'no'} "
            f"| {sum(s.kept for s in group) / len(group):.0%} "
            f"| {sum(s.untraced for s in group) / len(group):.1f} |"
        )
    return head + rows


LEDGER_HEAD = """# Scores

One row per model and condition per run, appended by `scripts/eval_score.py --ledger`.
Scores only: the answers are in `eval-runs/`, or in the finding that quotes them.

| date | commit | skills dirty | model | condition | N | tasks clean^k | answers clean | kept | untraced | calls | cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
"""


def ledger_row(manifest: dict, scores: list[Score]) -> str:
    groups = _by_task(scores)
    all_clean = sum(all(s.clean for s in g) for g in groups.values())
    calls = [s.calls for s in scores if s.calls is not None]
    cost = sum(s.cost or 0 for s in scores)
    return (
        f"| {manifest.get('date', datetime.date.today().isoformat())} "
        f"| {manifest.get('commit', '-')} | {manifest.get('skills_dirty', '-')} "
        f"| {manifest.get('model', scores[0].model)} | {manifest.get('condition', '-')}"
        f"{' +show' if manifest.get('show') else ''} "
        f"| {manifest.get('n', '-')} | {all_clean}/{len(groups)} "
        f"| {sum(s.clean for s in scores)}/{len(scores)} "
        f"| {sum(s.kept for s in scores) / len(scores):.0%} "
        f"| {sum(s.untraced for s in scores) / len(scores):.1f} "
        f"| {sum(calls) / len(calls) if calls else 0:.1f} | ${cost:.2f} |\n"
    )


def sheet(run: Path, theme_path: Path, out: Path) -> None:
    """Every answer's render in *run*, one row per task, one column per trial."""
    import skia

    from md2ui.utils.png import encode_png

    cell, cap, label = 384, 1400, 22
    pngs = []
    for answer in _answers(run):
        png = answer.with_suffix(".png")
        if not png.is_file():
            render(answer, theme_path)
        if png.is_file():
            pngs.append(png)
    if not pngs:
        return
    rows: dict[str, list[Path]] = {}
    for png in pngs:
        rows.setdefault(trial_of(png)[0], []).append(png)
    images = {p: skia.Image.open(str(p)) for p in pngs}

    def height(p: Path) -> int:
        image = images[p]
        return min(cap, round(image.height() * cell / image.width()))

    heights = [max(height(p) for p in row) + label for row in rows.values()]
    cols = max(len(row) for row in rows.values())
    surface = skia.Surface(cols * (cell + 8), sum(heights) + 8 * len(heights))
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorWHITE)
    font, ink = (
        skia.Font(skia.Typeface("Helvetica"), 14),
        skia.Paint(Color=skia.ColorBLACK),
    )
    y = 0
    for row, row_height in zip(rows.values(), heights, strict=True):
        for i, png in enumerate(row):
            x = i * (cell + 8)
            canvas.drawString(png.stem, x + 4, y + 16, font, ink)
            image = images[png]
            source = skia.Rect(0, 0, image.width(), height(png) * image.width() / cell)
            target = skia.Rect(x, y + label, x + cell, y + label + height(png))
            canvas.drawImageRect(image, source, target, skia.SamplingOptions())
        y += row_height + 8
    data = encode_png(surface.makeImageSnapshot())
    if data is not None:
        out.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("run", type=Path)
    parser.add_argument("--sheet", action="store_true")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--suite")
    parser.add_argument("--theme", type=Path)
    try:
        args = parser.parse_args()
    except SystemExit:
        print(__doc__)
        return 2

    from md2ui import session, theme_lint
    from md2ui.digest import theme_at

    kit = session.load_grouping_kit()
    root = args.run.resolve()
    everything: list[Score] = []
    for run in _runs(root):
        manifest_path = run / "manifest.json"
        manifest = (
            json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
        )
        suite = manifest.get("suite") or args.suite
        if suite is None:
            print(f"{run}: no manifest.json, and no --suite")
            return 2
        condition = manifest.get("condition", "root")
        theme_dir = args.theme or (ROOT if condition == "root" else ROOT / condition)
        theme_path = theme_dir.resolve() / "THEME.md"
        _, tasks = split_tasks((EVALS / suite / "tasks.md").read_text())
        contract, theme = theme_lint.answer_contract(theme_path), theme_at(theme_path)
        model = manifest.get("model") or run.name
        scores = []
        for answer in _answers(run):
            task = trial_of(answer)[0]
            if task not in tasks:
                print(f"  skipped {answer.name}: no task {task!r} in {suite}")
                continue
            if why := unusable(answer):
                print(f"  skipped {answer.name}: {why}")
                continue
            scores.append(score(answer, model, tasks[task], kit, contract, theme))
        everything += scores
        if args.sheet:
            sheet(run, theme_path, root / f"{run.name}-sheet.png")
        if args.ledger and scores:
            if not args.ledger.is_file():
                args.ledger.write_text(LEDGER_HEAD)
            with args.ledger.open("a") as ledger:
                ledger.write(ledger_row(manifest, scores))

    if not everything:
        print(f"no answers under {root}")
        return 1
    report = ["# Scores", "", *_rates(everything), "", *_rows(everything), ""]
    (root / "scores.md").write_text("\n".join(report))
    print("\n".join(_rates(everything)))
    print(f"\n{len(everything)} answers -> {root / 'scores.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
