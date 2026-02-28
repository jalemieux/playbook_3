import json
from unittest.mock import patch, MagicMock, call

from src.agent import handler, run

# Reusable config for tests
TEST_CONFIG = {
    "agent_model": "anthropic/claude-sonnet-4",
    "bash_timeout": 5,
    "max_iterations": 10,
}


def test_handler_text_response():
    """Model replies with text, no tool calls — single iteration."""
    replies = []
    with patch("src.agents.single.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hello!", "tool_calls": None}
        handler("Hi there", replies.append, TEST_CONFIG)
    assert replies == ["Hello!"]


def test_handler_tool_then_text():
    """Model calls bash, gets output, then replies with text."""
    replies = []
    with patch("src.agents.single.chat_completion") as mock_llm, \
         patch("src.agents.single.execute_bash", return_value="file1.txt\nfile2.txt\n") as mock_bash:
        mock_llm.side_effect = [
            {
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "execute_bash", "arguments": '{"command": "ls"}'},
                }],
            },
            {"content": "You have file1.txt and file2.txt.", "tool_calls": None},
        ]
        handler("What files do I have?", replies.append, TEST_CONFIG)
    mock_bash.assert_called_once_with("ls", timeout=5)
    assert replies == ["You have file1.txt and file2.txt."]


def test_handler_max_iterations():
    """Agent stops after max_iterations even if model keeps calling tools."""
    config = {**TEST_CONFIG, "max_iterations": 2}
    replies = []
    tool_response = {
        "content": None,
        "tool_calls": [{
            "id": "call_n",
            "type": "function",
            "function": {"name": "execute_bash", "arguments": '{"command": "echo loop"}'},
        }],
    }
    with patch("src.agents.single.chat_completion", return_value=tool_response), \
         patch("src.agents.single.execute_bash", return_value="loop\n"):
        handler("infinite loop", replies.append, config)
    assert len(replies) == 1
    assert "iteration" in replies[0].lower() or "limit" in replies[0].lower()


def test_handler_bash_timeout():
    """Bash timeout error is fed back to the model as tool result."""
    replies = []
    with patch("src.agents.single.chat_completion") as mock_llm, \
         patch("src.agents.single.execute_bash", side_effect=TimeoutError("timed out")):
        mock_llm.side_effect = [
            {
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "execute_bash", "arguments": '{"command": "sleep 999"}'},
                }],
            },
            {"content": "That command timed out.", "tool_calls": None},
        ]
        handler("run sleep 999", replies.append, TEST_CONFIG)
    assert replies == ["That command timed out."]


def test_run_returns_text_response():
    """run() returns the LLM response as a string."""
    with patch("src.agents.single.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hello!", "tool_calls": None}
        result = run("Hi there", TEST_CONFIG)
    assert result == "Hello!"


def test_run_tool_then_text():
    """run() executes tools and returns final text."""
    with patch("src.agents.single.chat_completion") as mock_llm, \
         patch("src.agents.single.execute_bash", return_value="file1.txt\n"):
        mock_llm.side_effect = [
            {
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "execute_bash", "arguments": '{"command": "ls"}'},
                }],
            },
            {"content": "Found file1.txt.", "tool_calls": None},
        ]
        result = run("List files", TEST_CONFIG)
    assert result == "Found file1.txt."
