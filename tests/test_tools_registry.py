from unittest.mock import patch

from src.agents.single import run, TOOLS
from src.tools import execute_tool_call


def test_execute_tool_call_unknown():
    out = execute_tool_call("Nope", {}, {})
    assert "unknown tool" in out.lower()


def test_single_tools_contain_bash():
    names = [t["function"]["name"] for t in TOOLS]
    assert "execute_bash" in names


def test_single_run_passes_tools_to_llm():
    config = {
        "agent_model": "anthropic/claude-sonnet-4",
        "max_iterations": 1,
    }

    with patch("src.agents.single.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "ok", "tool_calls": None}
        out = run("hello", config)

    assert out == "ok"
    passed_tools = mock_llm.call_args.kwargs["tools"]
    assert passed_tools == TOOLS
