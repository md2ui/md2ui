#!/usr/bin/env python3
"""Run an eval suite under `evals/`: fresh agents answer each task from `guide` alone.

Each task in `<suite>/tasks.md` (a `## <id>` section, after the suite's intro) goes to a
fresh `claude -p` agent, N times. The agent is isolated by construction, not by
instruction:

- it runs in a new temp directory outside the repo, so no CLAUDE.md or memory is found;
- `--tools ""` removes every built-in tool, so it cannot read `src/` or the corpus;
- `--strict-mcp-config` and `--setting-sources ""` leave only the md2ui authoring server
  (`md2ui.mcp_server`) serving this checkout's `skills/` and the condition's theme;
- `--disable-slash-commands` leaves out installed skills, including md2ui's own plugin.

`--runner codex` puts the same task to a fresh `codex exec` agent instead, isolated
the same way; `scripts/eval_codex.py` says how. `--model` then takes a Codex model id
(`gpt-6.1-sol`): the runner never relies on Codex's default model, and refuses
GPT-6-Astra. `--codex-tools stock` leaves Codex's deferred view of md2ui's tools
(`full`, as claude sees them, by default); `--reasoning low|medium|high` sets the
effort (`medium` by default). Both go in the manifest, and in the run's folder when
not the default.

Usage:
    uv run python scripts/eval_run.py <suite> --model M [--runner claude|codex]
        [--codex-tools full|stock] [--reasoning low|medium|high] [--theme DIR]
        [--n 3] [--task ID ...] [--jobs 4] [--out DIR] [--no-render]
        [--show [--every]]

`<suite>` is a folder name under `evals/`, or a suite folder's path (the private suites
live in md2ui-private). `--theme` is a condition: a folder holding the THEME.md (and
MEANINGS.md, patterns/, includes/) the server serves; the root THEME.md when omitted.
A condition's `includes/` reaches the server with its theme (`md2ui.includes`), and the
answer is rendered and advised with its includes expanded, as `show` would send it.
`--out` defaults to `eval-runs/<suite folder's name>/<date>/`, gitignored like
`screenshots/`.

`--show` mirrors the demo, where every reply goes through `show` and comes back with
the advice it set off (`md2ui.advice`). After the agent's reply, the runner works out
the advice the server would give that session, leaving out what the agent read and
what its own `check` calls already advised. If any fires, it resumes the same session
with it, as `show`'s result, and keeps the agent's revised reply. The reply before
the advice is kept beside it, so each advised answer is its own before and after.
`--every` sends back every issue `show` returns (`check`'s errors, warnings and notes
too), to measure a `check` rule as agents meet it.

`--show` works with `--runner claude` only.

Writes `<out>/<model>[-<condition>]/`
(`codex-<model>[-stock][-<reasoning>][-<condition>]/` with codex):
    manifest.json          suite, condition, runner, model (and codex's version,
                           tool view and reasoning),
                           skills commit, date, N, prompt hash
    <task>-r<k>.md         the agent's final reply: the document it would show
    <task>-r<k>.first.md   with `--show`, the reply before the advice, when it fired
    <task>-r<k>.json       effort: the md2ui server's status, turns, tool calls,
                           guide topics, tokens, cost; with `--show`, the advice
                           given and the revision's effort
    <task>-r<k>.jsonl      the transcript, claude's stream-json events or codex's
                           `--json` events: read it to tell an agent's mistake from
                           a task's. Codex's events show each md2ui call, not the
                           `exec` code around it; `<task>-r<k>.rollout.jsonl`
                           holds codex's full session, the code included
    <task>-r<k>.png        the answer rendered at RENDER_WIDTH with the condition's theme

Renders run on their own workers while the agents go on to the next trial, so they
cost the run almost nothing; `--no-render` skips them, and `eval_score.py --sheet`
fills in any that are missing. A failed render writes `<task>-r<k>.render-error.txt`
and never loses the answer.

Score a run with `scripts/eval_score.py`. Three traps: a run measures `skills/` as it
stands in the working tree, so the manifest records the commit AND whether `skills/`
was dirty; a render reads `src/` as it is when it runs, so do not edit `src/` during a
run; and runs cost money — try one task with `--n 1` first.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePath

import eval_codex

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
# The width every answer is rendered at, so renders of different runs compare.
RENDER_WIDTH = 767

# Appended to every task, so the reply can be taken as the document unchanged.
REPLY_RULE = (
    "\n\nYour final message is the document itself: plain Markdown, nothing before "
    "or after it."
)


def split_tasks(text: str) -> tuple[str, dict[str, str]]:
    """The suite's intro and its tasks by id, in order. HTML comments are notes for
    the suite's maintainers, not for the agent."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    parts = re.split(r"^## +(\S+)[^\n]*\n", text, flags=re.M)
    intro = parts[0].strip()
    tasks = {
        parts[i]: f"## {parts[i]}\n{parts[i + 1].strip()}"
        for i in range(1, len(parts), 2)
    }
    return intro, tasks


def unwrap(reply: str) -> str:
    """The reply without a fence wrapped around all of it."""
    match = re.fullmatch(r"\s*```(?:markdown|md)?\n(.*?)\n```\s*", reply, flags=re.S)
    return (match.group(1) if match else reply.strip()) + "\n"


def effort(events: list[dict]) -> dict:
    """What the agent did to get its answer, from claude's stream-json events."""
    calls = [
        {"name": block["name"].removeprefix("mcp__md2ui__"), "input": block["input"]}
        for event in events
        if event.get("type") == "assistant"
        for block in event["message"]["content"]
        if block.get("type") == "tool_use"
    ]
    result = next((e for e in events if e.get("type") == "result"), {})
    usage = result.get("usage", {})
    # A server that failed to start and an agent that chose not to call it both
    # leave no md2ui calls; only the session's init event tells them apart.
    init = next((e for e in events if e.get("subtype") == "init"), {})
    server = next(
        (s["status"] for s in init.get("mcp_servers", []) if s["name"] == "md2ui"),
        "missing",
    )
    return {
        "is_error": result.get("is_error", True),
        "server": server,
        "num_turns": result.get("num_turns"),
        "tool_calls": calls,
        "guide_topics": [
            c["input"].get("topic", "") for c in calls if c["name"] == "guide"
        ],
        "input_tokens": usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cost_usd": result.get("total_cost_usd"),
        "duration_ms": result.get("duration_ms"),
    }


def expanded(reply: str, theme: Path) -> str:
    """*reply* as the server would send it: the condition's includes expanded."""
    from md2ui.includes import expand, static_includes

    return expand(reply, static_includes(theme))[0]


def render(answer: Path, theme: Path) -> None:
    """*answer* drawn beside it as a PNG; a failure is written beside it instead.
    With includes, the page drawn is ``<answer>.expanded.md``, written beside it."""
    page = answer
    drawn = expanded(answer.read_text(), theme)
    if drawn != answer.read_text():
        page = answer.with_suffix(".expanded.md")
        page.write_text(drawn)
    proc = subprocess.run(
        [
            str(Path(sys.executable).parent / "md2ui"),
            "render",
            str(page),
            "--theme",
            str(theme),
            "--width",
            str(RENDER_WIDTH),
            "--out",
            str(answer.with_suffix(".png")),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode:
        answer.with_suffix(".render-error.txt").write_text(proc.stdout + proc.stderr)


# What `show` would return, sent back to the agent with `--show`.
SHOW_RESULT = (
    "md2ui showed your answer to the user, and `show` returned this advice:\n\n"
    "{advice}\n\nIf it applies, send the document again with it applied."
)
_ADVISED = re.compile(r'read\\*"\s*:\s*\\*"([a-z0-9/_.-]+)')


def md2ui_server(theme: Path) -> dict:
    """The md2ui authoring server an agent is given: this checkout's `skills/`, the
    condition's *theme* (its THEME.md)."""
    return {
        "command": "uv",
        "args": [
            "--directory",
            str(ROOT),
            "run",
            "python",
            "-m",
            "md2ui.mcp_server",
            "--theme",
            str(theme),
        ],
    }


def run_one(
    prompt: str,
    model: str,
    theme: Path,
    show: bool = False,
    every: bool = False,
    runner: str = "claude",
    codex_tools: str = eval_codex.DEFAULT_TOOLS,
    reasoning: str = eval_codex.DEFAULT_REASONING,
) -> tuple[str, dict, str, str | None]:
    """One fresh agent's reply, effort and transcript; with *show*, also its
    reply before the advice, when advice fired; with *every*, every issue `show`
    returns counts as its advice. With *runner* ``codex``, the transcript's
    full session comes back in the effort's ``rollout`` key, for the caller to
    write beside it."""
    server = md2ui_server(theme)
    if runner == "codex":
        reply, spent, transcript = eval_codex.run(
            prompt, model, server, codex_tools, reasoning
        )
        return unwrap(reply), spent, transcript, None
    with tempfile.TemporaryDirectory(prefix="md2ui-eval-") as cwd:
        config = Path(cwd) / "mcp.json"
        config.write_text(json.dumps({"mcpServers": {"md2ui": server}}))
        reply, events, transcript = _claude(prompt, model, config, cwd, persist=show)
        spent = effort(events)
        advice = _show_advice(reply, spent, transcript, theme, every) if show else []
        first = None
        if advice:
            session_id = events[0].get("session_id", "")
            follow = SHOW_RESULT.format(advice="\n".join(f"- {a}" for a in advice))
            first = reply
            reply, events, more = _claude(
                follow + REPLY_RULE, model, config, cwd, resume=session_id
            )
            transcript += more
            spent |= {"advice": advice, "after_advice": effort(events)}
        if show:
            _forget_session(events)
    return reply, spent, transcript, first


def _claude(
    prompt: str,
    model: str,
    config: Path,
    cwd: str,
    persist: bool = False,
    resume: str | None = None,
) -> tuple[str, list[dict], str]:
    """One `claude -p` call: the reply, its stream-json events and the raw stream."""
    keep = (
        ["--resume", resume]
        if resume
        else []
        if persist
        else ["--no-session-persistence"]
    )
    proc = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--model",
            model,
            "--tools",
            "",
            "--strict-mcp-config",
            "--mcp-config",
            str(config),
            "--setting-sources",
            "",
            "--disable-slash-commands",
            *keep,
            "--allowedTools",
            "mcp__md2ui__*",
            "--output-format",
            "stream-json",
            "--verbose",
        ],
        cwd=cwd,
        # A busy machine slows a server's start past the CLI's 30 s default and the
        # answer runs without md2ui.
        env=os.environ | {"MCP_TIMEOUT": "60000"},
        capture_output=True,
        text=True,
        check=False,
    )
    events = [
        json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")
    ]
    result = next((e for e in events if e.get("type") == "result"), {})
    reply = result.get("result") or f"<!-- no reply: {proc.stderr.strip()[-400:]} -->"
    return unwrap(reply), events, proc.stdout


_KIT_LOCK = threading.Lock()
_KIT: list = []


def _show_advice(
    reply: str, spent: dict, transcript: str, theme: Path, every: bool = False
) -> list[str]:
    """The advice `show` would return for *reply* in this session: nothing the
    agent read through `guide`, nothing its own `check` calls already advised.
    Read from `reply_issues`, the function a backend's send tool calls, so the
    run measures that code; only its advice is sent back, so the run measures
    the advice and not the other issues, unless *every* asks for all of them,
    as `show` returns them."""
    from md2ui import session, theme_lint
    from md2ui.advice import Reading, reply_issues
    from md2ui.includes import expand, static_includes

    reply, regions = expand(reply, static_includes(theme))
    with _KIT_LOCK:
        if not _KIT:
            _KIT.append(session.load_grouping_kit())
        ast = session.group_markdown(reply, _KIT[0])
    read = {t.strip().lower().removesuffix(".md") for t in spent["guide_topics"]}
    reading = Reading(read=read, advised=set(_ADVISED.findall(transcript)))
    contract = theme_lint.answer_contract(theme)
    issues = reply_issues(reply, ast, contract, reading, regions=regions)
    return [i["message"] for i in issues if every or i["code"] == "advice"]


def _forget_session(events: list[dict]) -> None:
    """Delete the session `--show` had to keep for its resume: claude stores it under
    a folder named for the working directory, which was a temp directory."""
    cwd = next((e.get("cwd") for e in events if e.get("cwd")), None)
    if cwd:
        folder = (
            Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", cwd)
        )
        shutil.rmtree(folder, ignore_errors=True)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()


def condition_of(theme_dir: PurePath) -> str:
    """The manifest's name for the theme a run used: ``root`` for the checkout's,
    its path under the checkout, or its absolute path for a project's theme in its
    own repository (ADR-501), in ``/`` everywhere. ``eval_score.py`` reads it back."""
    if theme_dir == ROOT:
        return "root"
    if theme_dir.is_relative_to(ROOT):
        return theme_dir.relative_to(ROOT).as_posix()
    return theme_dir.as_posix()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace | str:
    """The run's arguments, or why they cannot make a run."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("suite")
    parser.add_argument("--model", required=True)
    parser.add_argument("--runner", choices=("claude", "codex"), default="claude")
    eval_codex.add_arguments(parser)
    parser.add_argument("--theme", type=Path)
    parser.add_argument("--n", type=int, default=3)
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--every", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return __doc__ or ""
    if why := eval_codex.args_refused(args):
        return why
    return args


def run_name(runner: str, model: str, condition: str, *codex: str) -> str:
    """The run's folder: the model, after its runner when that is not claude and
    before codex's settings off their default (`eval_codex.settings_name`), then
    the condition's folder, if any (``-<name>``)."""
    if runner == "claude":
        return f"{model}{condition}"
    return f"{runner}-{model}{eval_codex.settings_name(*codex)}{condition}"


def main() -> int:
    args = parse_args()
    if isinstance(args, str):
        print(args)
        return 2

    suite = EVALS / args.suite if (EVALS / args.suite).is_dir() else Path(args.suite)
    intro, tasks = split_tasks((suite / "tasks.md").read_text())
    unknown = set(args.task) - set(tasks)
    if unknown:
        print(
            f"no such task: {', '.join(sorted(unknown))}; the suite has {', '.join(tasks)}"
        )
        return 2
    chosen = {k: v for k, v in tasks.items() if not args.task or k in args.task}
    theme_dir = (args.theme or ROOT).resolve()
    theme = theme_dir / "THEME.md"
    if not theme.is_file():
        print(f"no THEME.md in {theme_dir}")
        return 2
    condition = "" if args.theme is None else f"-{theme_dir.name}"
    today = datetime.date.today().isoformat()
    out = (args.out or ROOT / "eval-runs" / suite.name / today).resolve()
    run_dir = out / run_name(
        args.runner, args.model, condition, args.codex_tools, args.reasoning
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    prompts = {task: f"{intro}\n\n{body}{REPLY_RULE}" for task, body in chosen.items()}
    manifest = {
        "suite": args.suite,
        "show": args.show,
        "every": args.every,
        "condition": condition_of(theme_dir),
        "runner": args.runner,
        "model": args.model,
        "date": today,
        "n": args.n,
        "tasks": list(chosen),
        "commit": _git("rev-parse", "--short", "HEAD"),
        "skills_dirty": bool(_git("status", "--porcelain", "--", "skills")),
        "prompt_sha256": hashlib.sha256(
            "\n".join(prompts.values()).encode()
        ).hexdigest()[:16],
    }
    if args.runner == "codex":
        manifest["codex_version"] = eval_codex.version()
        manifest["codex_tools"] = args.codex_tools
        manifest["reasoning"] = args.reasoning
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    # Two render workers: each starts Python and loads fonts, beside the agents' servers.
    renders = ThreadPoolExecutor(max_workers=2)

    def job(item: tuple[str, int]) -> str:
        task, k = item
        reply, spent, transcript, first = run_one(
            prompts[task],
            args.model,
            theme,
            args.show,
            args.every,
            args.runner,
            args.codex_tools,
            args.reasoning,
        )
        answer = run_dir / f"{task}-r{k}.md"
        answer.write_text(reply)
        rollout = spent.pop("rollout", None)
        if rollout:
            answer.with_suffix(".rollout.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rollout)
            )
        if first is not None:
            answer.with_suffix(".first.md").write_text(first)
        answer.with_suffix(".json").write_text(json.dumps(spent, indent=2) + "\n")
        answer.with_suffix(".jsonl").write_text(transcript)
        if not args.no_render:
            renders.submit(render, answer, theme)
        flag = "  ERROR" if spent["is_error"] else ""
        if spent["server"] != "connected":
            flag += f"  SERVER {spent['server']}"
        return f"  {task}-r{k}: {len(spent['tool_calls'])} calls{flag}"

    work = [(task, k) for task in chosen for k in range(1, args.n + 1)]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for line in pool.map(job, work):
            print(line)
    renders.shutdown(wait=True)
    print(f"\n{len(work)} answers -> {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
