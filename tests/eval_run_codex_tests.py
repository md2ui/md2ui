"""Tests for the eval runner's codex runner (`scripts/eval_codex.py`, `scripts/eval_run.py --runner codex`).

The runner defaults to claude and takes codex on request, always with a model named;
`--show` is refused with codex. A codex run's folder is named for its runner. The
fresh `CODEX_HOME`'s config is valid TOML giving md2ui as the one, required, MCP
server, shown directly rather than deferred, a read-only sandbox without approvals, and every tool-giving feature off.
The final message is codex's last agent message. Effort is read from codex's `--json`
events: md2ui's calls named as claude's are, `guide` topics and resources read,
tokens summed, and a server that failed to start told from a failed call.

Run with: uv run python scripts/run_tests.py
"""

import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import eval_codex  # noqa: E402
import eval_run  # noqa: E402


def _item(kind: str, **fields) -> dict:
    return {"type": "item.completed", "item": {"id": "i", "type": kind, **fields}}


EVENTS = [
    {"type": "thread.started", "thread_id": "t"},
    {"type": "turn.started"},
    _item("agent_message", text="I'll read the notes first."),
    _item(
        "mcp_tool_call",
        server="md2ui",
        tool="guide",
        arguments={"topic": "text"},
        status="completed",
    ),
    _item(
        "mcp_tool_call",
        server="codex",
        tool="read_mcp_resource",
        arguments={"server": "md2ui", "uri": "md2ui://skills/README.md"},
        status="completed",
    ),
    _item("mcp_tool_call", server="md2ui", tool="check", arguments={"markdown": "x"}),
    _item("mcp_tool_call", server="other", tool="search", arguments={}),
    _item("agent_message", text="```markdown\n## Reviews\n\nGood.\n```"),
    {
        "type": "turn.completed",
        "usage": {
            "input_tokens": 1000,
            "cached_input_tokens": 400,
            "output_tokens": 50,
            "reasoning_output_tokens": 5,
        },
    },
]


def _args(argv: list[str]):
    args = eval_run.parse_args(argv)
    assert not isinstance(args, str), args
    return args


def test_the_runner_is_claude_unless_codex_is_asked():
    args = _args(["suite", "--model", "haiku"])
    assert args.runner == "claude", args
    args = _args(["suite", "--runner", "codex", "--model", "gpt-6.1-sol"])
    assert (args.runner, args.model) == ("codex", "gpt-6.1-sol"), args


def test_codex_needs_a_model_and_refuses_show():
    assert isinstance(eval_run.parse_args(["suite", "--runner", "codex"]), str)
    why = eval_run.parse_args(
        ["suite", "--runner", "codex", "--model", "gpt-6-luna", "--show"]
    )
    assert isinstance(why, str) and "--show" in why, why
    assert isinstance(
        eval_run.parse_args(["s", "--runner", "gemini", "--model", "m"]), str
    )


def test_a_codex_run_is_named_for_its_runner():
    assert eval_run.run_name("claude", "haiku", "") == "haiku"
    assert eval_run.run_name("codex", "gpt-6.1-sol", "") == "codex-gpt-6.1-sol"
    assert (
        eval_run.run_name("codex", "gpt-6-luna", "-theme") == "codex-gpt-6-luna-theme"
    )


def test_the_tool_view_and_reasoning_default_to_full_and_medium():
    args = _args(["suite", "--runner", "codex", "--model", "gpt-6.1-sol"])
    assert (args.codex_tools, args.reasoning) == ("full", "medium"), args
    args = _args(
        ["s", "--runner", "codex", "--model", "gpt-6-luna", "--codex-tools", "stock"]
        + ["--reasoning", "high"]
    )
    assert (args.codex_tools, args.reasoning) == ("stock", "high"), args
    for bad in (["--codex-tools", "all"], ["--reasoning", "xhigh"]):
        argv = ["s", "--runner", "codex", "--model", "gpt-6-luna", *bad]
        assert isinstance(eval_run.parse_args(argv), str), bad
    assert isinstance(
        eval_run.parse_args(["s", "--model", "haiku", "--reasoning", "high"]), str
    )


def test_a_codex_run_names_a_view_and_reasoning_only_off_default():
    name = eval_run.run_name
    assert name("codex", "gpt-6.1-sol", "", "full", "medium") == "codex-gpt-6.1-sol"
    assert name("codex", "gpt-6.1-sol", "", "stock") == "codex-gpt-6.1-sol-stock"
    assert name("codex", "gpt-6-luna", "-shop", "stock", "high") == (
        "codex-gpt-6-luna-stock-high-shop"
    )
    assert name("codex", "gpt-6-luna", "", "full", "low") == "codex-gpt-6-luna-low"


def test_the_config_carries_the_view_and_reasoning():
    server = eval_run.md2ui_server(Path("/x/THEME.md"))
    full = tomllib.loads(eval_codex.codex_config("gpt-6.1-sol", server))
    assert full["model_reasoning_effort"] == "medium"
    assert full["mcp_servers"]["md2ui"]["omit_tools_from"] == ["deferred"]
    stock = tomllib.loads(
        eval_codex.codex_config("gpt-6.1-sol", server, "stock", "low")
    )
    assert stock["model_reasoning_effort"] == "low"
    assert "omit_tools_from" not in stock["mcp_servers"]["md2ui"], stock


def test_astra_is_refused_under_any_name():
    for model in ("gpt-6-astra", "GPT-6-Astra", " gpt_6_astra ", "GPT 6 Astra"):
        for runner in ("codex", "claude"):
            why = eval_run.parse_args(["s", "--runner", runner, "--model", model])
            assert isinstance(why, str) and "Astra" in why, (model, why)
    server = eval_run.md2ui_server(Path("/x/THEME.md"))
    try:
        eval_codex.codex_config("gpt-6-astra", server)
    except ValueError:
        pass
    else:
        raise AssertionError("a config for GPT-6-Astra was written")
    assert eval_codex.refused("gpt-6.1-sol") is None


def test_codex_is_given_md2ui_and_nothing_else():
    server = eval_run.md2ui_server(Path("/x/THEME.md"))
    config = tomllib.loads(eval_codex.codex_config("gpt-6.1-sol", server))
    assert config["model"] == "gpt-6.1-sol"
    assert list(config["mcp_servers"]) == ["md2ui"], config["mcp_servers"]
    md2ui = config["mcp_servers"]["md2ui"]
    assert md2ui["required"] is True and md2ui["args"][-1] == "/x/THEME.md", md2ui
    assert md2ui["omit_tools_from"] == ["deferred"], md2ui
    assert (config["sandbox_mode"], config["approval_policy"]) == ("read-only", "never")
    assert config["web_search"] == "disabled"
    assert config["features"]["shell_tool"] is False
    assert config["features"]["unified_exec"] is False
    assert not any(config["features"].values()), config["features"]
    assert config["skills"]["bundled"]["enabled"] is False
    assert config["agents"]["enabled"] is False
    assert config["project_doc_max_bytes"] == 0


def test_the_reply_is_codexs_last_message():
    assert eval_codex.codex_reply(EVENTS) == "```markdown\n## Reviews\n\nGood.\n```"
    assert (
        eval_run.unwrap(eval_codex.codex_reply(EVENTS) or "") == "## Reviews\n\nGood.\n"
    )
    assert eval_codex.codex_reply(EVENTS[:2]) is None


def test_codex_effort_reads_its_events():
    rollout = [{"type": "token_usage_record"}] * 3 + [
        {"type": "response_item", "payload": {"type": "custom_tool_call"}}
    ]
    spent = eval_codex.codex_effort(EVENTS, rollout, duration_ms=1200)
    assert [c["name"] for c in spent["tool_calls"]] == [
        "guide",
        "read_mcp_resource",
        "check",
        "other.search",
    ], spent["tool_calls"]
    assert spent["guide_topics"] == ["text"]
    assert spent["resources_read"] == ["md2ui://skills/README.md"]
    assert (spent["input_tokens"], spent["output_tokens"]) == (1000, 50)
    assert spent["cached_input_tokens"] == 400
    assert (spent["num_turns"], spent["exec_cells"]) == (3, 1)
    assert spent["server"] == "connected" and spent["is_error"] is False, spent
    assert spent["cost_usd"] is None and spent["duration_ms"] == 1200


def test_a_server_that_failed_is_told_from_a_failed_call():
    stderr = (
        "Error: Failed to initialize session: required MCP servers failed to "
        "initialize: md2ui: handshaking with MCP server failed"
    )
    spent = eval_codex.codex_effort([], returncode=1, stderr=stderr)
    assert (spent["server"], spent["is_error"]) == ("failed", True), spent
    cut = eval_codex.codex_effort(EVENTS[:4], returncode=1)
    assert (cut["server"], cut["is_error"]) == ("connected", True), cut


def test_account_ids_are_left_out_of_a_session():
    meta = {"payload": {"creator_user_id": "u", "creator_account_id": "a", "id": "s"}}
    assert eval_codex._private(meta) == {"payload": {"id": "s"}}


TESTS = [
    test_the_runner_is_claude_unless_codex_is_asked,
    test_codex_needs_a_model_and_refuses_show,
    test_a_codex_run_is_named_for_its_runner,
    test_the_tool_view_and_reasoning_default_to_full_and_medium,
    test_a_codex_run_names_a_view_and_reasoning_only_off_default,
    test_the_config_carries_the_view_and_reasoning,
    test_astra_is_refused_under_any_name,
    test_codex_is_given_md2ui_and_nothing_else,
    test_the_reply_is_codexs_last_message,
    test_codex_effort_reads_its_events,
    test_a_server_that_failed_is_told_from_a_failed_call,
    test_account_ids_are_left_out_of_a_session,
]


if __name__ == "__main__":
    for test in TESTS:
        test()
    print(f"All {len(TESTS)} tests passed.")
