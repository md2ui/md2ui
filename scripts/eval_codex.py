"""The codex runner of `scripts/eval_run.py` (`--runner codex`): one fresh `codex exec`
agent per answer, given md2ui and nothing else.

Isolation is by construction, as with claude. Each call gets an empty temp working
directory, outside any git repository, and a fresh `CODEX_HOME` holding only the
`config.toml` `codex_config` writes and a copy of the user's login: never the user's
config, AGENTS.md, memories, hooks, rules, plugins or skills. The config turns off
every feature that gives a tool (shell, web search, images, browser, computer use,
plugins, subagents, skills), keeps a read-only sandbox that never asks for approval,
and names md2ui as the one MCP server, `required`, so a server that cannot start
fails the call before the model sees the task. By default (`--codex-tools full`) md2ui
is shown directly: its instructions and tools in `exec`'s description, as claude
shows them; `--codex-tools stock` leaves Codex's own default, which defers them.
`--reasoning` sets the model's effort (`medium` by default). GPT-6-Astra is refused
under any spelling (`refused`). What codex keeps is code mode's
`exec` (JavaScript with no file system, network or shell) reaching md2ui's tools,
codex's own tools for md2ui's resources (its notes), a clock, and `apply_patch`,
which the sandbox refuses.

A login codex refreshes during a call is written back to the user's, unless that
changed meanwhile; the login is copied, never read or printed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

# Codex features that would give the agent a tool beyond md2ui's, or load something
# from outside the run (hooks, memories, plugins, skills). Each is turned off.
CODEX_FEATURES_OFF = (
    "shell_tool",
    "unified_exec",
    "view_image",
    "apps",
    "plugins",
    "image_generation",
    "browser_use",
    "browser_use_external",
    "in_app_browser",
    "computer_use",
    "hooks",
    "goals",
    "skill_search",
    "tool_suggest",
    "sleep_tool",
    "memories",
    "shell_snapshot",
)


def _toml(value) -> str:
    """*value* as a TOML value: JSON's strings and arrays of strings are TOML's."""
    return json.dumps(value) if not isinstance(value, bool) else str(value).lower()


# How md2ui's tools are shown: ``full`` puts its instructions and tools in
# `exec`'s description, as claude shows them; ``stock`` leaves Codex's default,
# which defers them (the instructions cut to a line, the tools found in ALL_TOOLS).
TOOL_VIEWS = ("full", "stock")
REASONING = ("low", "medium", "high")
DEFAULT_TOOLS, DEFAULT_REASONING = "full", "medium"


def refused(model: str) -> str | None:
    """Why *model* may not be run, or None. GPT-6-Astra is never measured, under
    any spelling of its name."""
    if "astra" in re.sub(r"[\s_.]+", "-", model.strip().lower()):
        return (
            f"--model {model}: GPT-6-Astra is never run in these evals; "
            "measure gpt-6-luna, gpt-6.1-terra or gpt-6.1-sol"
        )
    return None


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """`eval_run.py`'s options for codex runs: the tool view and the reasoning."""
    parser.add_argument("--codex-tools", choices=TOOL_VIEWS, default=DEFAULT_TOOLS)
    parser.add_argument("--reasoning", choices=REASONING, default=DEFAULT_REASONING)


def args_refused(args: argparse.Namespace) -> str | None:
    """Why `eval_run.py`'s *args* cannot make a run, as far as codex goes: a
    refused model, codex's options without codex, or `--show` with codex."""
    if why := refused(args.model):
        return why
    if args.runner != "codex":
        if (args.codex_tools, args.reasoning) != (DEFAULT_TOOLS, DEFAULT_REASONING):
            return "--codex-tools and --reasoning are for --runner codex"
        return None
    if args.show:
        return (
            "--show is not supported with --runner codex: it would resume the "
            "session with `codex exec resume`, which this runner does not do yet"
        )
    return None


def settings_name(
    tools: str = DEFAULT_TOOLS, reasoning: str = DEFAULT_REASONING
) -> str:
    """The run folder's part for codex's settings: ``-stock`` and the reasoning,
    each only when it is not the default."""
    off = [
        v for v, d in ((tools, DEFAULT_TOOLS), (reasoning, DEFAULT_REASONING)) if v != d
    ]
    return "".join(f"-{v}" for v in off)


def codex_config(
    model: str,
    server: dict,
    tools: str = DEFAULT_TOOLS,
    reasoning: str = DEFAULT_REASONING,
) -> str:
    """The `config.toml` of a fresh `CODEX_HOME` for one eval agent: *model* at
    *reasoning* effort, the md2ui *server* as its one MCP server shown as *tools*
    says, and nothing else to use or load."""
    if why := refused(model):
        raise ValueError(why)
    if tools not in TOOL_VIEWS or reasoning not in REASONING:
        raise ValueError(f"no such tool view or reasoning: {tools}, {reasoning}")
    lines = [
        f"model = {_toml(model)}",
        f"model_reasoning_effort = {_toml(reasoning)}",
        'sandbox_mode = "read-only"',
        'approval_policy = "never"',
        'web_search = "disabled"',
        "project_doc_max_bytes = 0",
        "",
        "[history]",
        'persistence = "none"',
        "",
        "[agents]",
        "enabled = false",
        "",
        "[skills]",
        "include_instructions = false",
        "",
        "[skills.bundled]",
        "enabled = false",
        "",
        "[tools.experimental_request_user_input]",
        "enabled = false",
        "",
        "[tools.update_plan]",
        "enabled = false",
        "",
        "[features]",
        *(f"{name} = false" for name in CODEX_FEATURES_OFF),
        "",
        "[mcp_servers.md2ui]",
        f"command = {_toml(server['command'])}",
        f"args = {_toml(server['args'])}",
        # Fail the call, before the model sees the task, when md2ui cannot start.
        "required = true",
        "startup_timeout_sec = 60",
    ]
    if tools == "full":
        # Not deferred: the agent reads md2ui's instructions and tools whole.
        lines.append('omit_tools_from = ["deferred"]')
    return "\n".join(lines) + "\n"


def codex_reply(events: list[dict]) -> str | None:
    """The agent's final message, from codex's `--json` events: its last."""
    texts = [
        e["item"].get("text", "")
        for e in events
        if e.get("type") == "item.completed"
        and e.get("item", {}).get("type") == "agent_message"
    ]
    return texts[-1] if texts else None


# Codex's own tools for any MCP server's resources: md2ui's are its notes, so
# reading one is reading the notes, as `guide` would.
CODEX_RESOURCE_TOOLS = (
    "list_mcp_resources",
    "list_mcp_resource_templates",
    "read_mcp_resource",
)
_REQUIRED_FAILED = "required MCP servers failed to initialize"


def codex_effort(
    events: list[dict],
    rollout: list[dict] | None = None,
    returncode: int = 0,
    stderr: str = "",
    duration_ms: int | None = None,
) -> dict:
    """What the agent did to get its answer, from codex's `--json` *events* and,
    when kept, its session *rollout*. md2ui's tools are named as claude's are,
    without their server; codex's own (`read_mcp_resource`) keep their name, and
    the md2ui resources the agent read are listed beside the `guide` topics.
    The server was connected whenever the session started: md2ui is `required`,
    so codex refuses to start a session without it. Codex on a ChatGPT login
    reports no cost."""
    calls = [
        {
            "name": item["tool"]
            if item.get("server") == "md2ui" or item["tool"] in CODEX_RESOURCE_TOOLS
            else f"{item.get('server')}.{item['tool']}",
            "input": item.get("arguments") or {},
        }
        for e in events
        if e.get("type") == "item.completed"
        for item in [e.get("item", {})]
        if item.get("type") == "mcp_tool_call"
    ]
    usage: dict = {}
    for e in events:
        if e.get("type") == "turn.completed":
            for key, n in e.get("usage", {}).items():
                usage[key] = usage.get(key, 0) + n
    started = any(e.get("type") == "turn.started" for e in events)
    completed = any(e.get("type") == "turn.completed" for e in events)
    failed = any(e.get("type") in ("turn.failed", "error") for e in events)
    server = (
        "failed"
        if _REQUIRED_FAILED in stderr
        else "connected"
        if started
        else "missing"
    )
    rollout = rollout or []
    return {
        "is_error": bool(returncode) or failed or not completed,
        "server": server,
        # One per model response, as claude counts its turns.
        "num_turns": sum(1 for r in rollout if r.get("type") == "token_usage_record")
        or None,
        "tool_calls": calls,
        "guide_topics": [
            c["input"].get("topic", "") for c in calls if c["name"] == "guide"
        ],
        "resources_read": [
            c["input"].get("uri", "") for c in calls if c["name"] == "read_mcp_resource"
        ],
        "exec_cells": sum(
            1
            for r in rollout
            if r.get("type") == "response_item"
            and r.get("payload", {}).get("type") == "custom_tool_call"
        ),
        # codex's input count includes the cached part, as claude's sum does.
        "input_tokens": usage.get("input_tokens", 0),
        "cached_input_tokens": usage.get("cached_input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "reasoning_output_tokens": usage.get("reasoning_output_tokens", 0),
        "cost_usd": None,
        "duration_ms": duration_ms,
        "warnings": [
            e["item"].get("message", "")
            for e in events
            if e.get("type") == "item.completed"
            and e.get("item", {}).get("type") == "error"
        ],
    }


def _private(value: Any) -> Any:
    """*value* without the account ids codex writes into a session."""
    if isinstance(value, dict):
        return {
            k: _private(v)
            for k, v in value.items()
            if not re.search(r"(user|account)_id|email", k)
        }
    if isinstance(value, list):
        return [_private(v) for v in value]
    return value


_AUTH_LOCK = threading.Lock()


def _codex_login() -> Path:
    """The user's codex login, copied into each fresh `CODEX_HOME`; never read
    here beyond copying, and never printed or logged."""
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "auth.json"


def run(
    prompt: str,
    model: str,
    server: dict,
    tools: str = DEFAULT_TOOLS,
    reasoning: str = DEFAULT_REASONING,
) -> tuple[str, dict, str]:
    """One `codex exec` call in a fresh `CODEX_HOME`: the final message (fenced
    as the agent sent it), its effort (with the session's rollout, account ids
    left out, under ``rollout``) and the raw `--json` events."""
    login = _codex_login()
    with tempfile.TemporaryDirectory(prefix="md2ui-eval-codex-") as tmp:
        home, cwd = Path(tmp) / "home", Path(tmp) / "work"
        home.mkdir()
        cwd.mkdir()
        (home / "config.toml").write_text(codex_config(model, server, tools, reasoning))
        auth = home / "auth.json"
        with _AUTH_LOCK:
            original = login.read_bytes() if login.is_file() else b""
        if original:
            auth.write_bytes(original)
            auth.chmod(0o600)
        start = time.monotonic()
        proc = subprocess.run(
            [
                "codex",
                "exec",
                "--json",
                "--skip-git-repo-check",
                "--ignore-rules",
                "--model",
                model,
                "--cd",
                str(cwd),
                "-",
            ],
            input=prompt,
            cwd=cwd,
            env={k: v for k, v in os.environ.items() if not k.startswith("CODEX_")}
            | {"CODEX_HOME": str(home)},
            capture_output=True,
            text=True,
            check=False,
        )
        duration = int((time.monotonic() - start) * 1000)
        # A login codex refreshed goes back where it came from, unless the user's
        # changed meanwhile: the refresh may have spent the old refresh token.
        if original and auth.is_file() and auth.read_bytes() != original:
            with _AUTH_LOCK:
                if login.read_bytes() == original:
                    fresh = login.with_suffix(".eval-tmp")
                    fd = os.open(fresh, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    with os.fdopen(fd, "wb") as out:
                        out.write(auth.read_bytes())
                    fresh.replace(login)
        rollout = [
            _private(json.loads(line))
            for path in sorted((home / "sessions").rglob("rollout-*.jsonl"))
            for line in path.read_text().splitlines()
            if line.startswith("{")
        ]
    events = [
        json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")
    ]
    spent = codex_effort(events, rollout, proc.returncode, proc.stderr, duration)
    reply = codex_reply(events)
    if reply is None:
        reply = f"<!-- no reply: {proc.stderr.strip()[-400:]} -->"
    spent["rollout"] = rollout
    return reply, spent, proc.stdout


def version() -> str:
    """The installed codex CLI's version, for the manifest."""
    proc = subprocess.run(
        ["codex", "--version"], capture_output=True, text=True, check=False
    )
    return proc.stdout.strip() or proc.stderr.strip()
