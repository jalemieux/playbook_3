from unittest.mock import patch

from src.agents.single import run
from src.tools import execute_tool_call, get_schemas_for_config


def _names(schemas):
    return [s["function"]["name"] for s in schemas]


def test_get_schemas_default_profile_is_bash_only():
    schemas = get_schemas_for_config({})
    assert _names(schemas) == ["execute_bash"]


def test_get_schemas_profile_claude_code():
    schemas = get_schemas_for_config({"agent_tool_profile": "claude_code"})
    names = _names(schemas)
    assert "Bash" in names
    assert "Task" in names
    assert "WebSearch" in names


def test_get_schemas_explicit_agent_tools_overrides_profile():
    config = {
        "agent_tool_profile": "claude_code",
        "agent_tools": ["Read", "Write"],
    }
    schemas = get_schemas_for_config(config)
    assert _names(schemas) == ["Read", "Write"]


def test_execute_tool_call_unknown():
    out = execute_tool_call("Nope", {}, {})
    assert "unknown tool" in out.lower()


def test_single_run_passes_configured_tools_to_llm():
    config = {
        "agent_model": "anthropic/claude-sonnet-4",
        "agent_tool_profile": "claude_code",
        "max_iterations": 1,
        "bash_timeout": 3,
    }

    with patch("src.agents.single.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "ok", "tool_calls": None}
        out = run("hello", config)

    assert out == "ok"
    passed_tools = mock_llm.call_args.kwargs["tools"]
    names = _names(passed_tools)
    assert "Task" in names
    assert "Bash" in names
