import json
from unittest.mock import patch

from src.agents.base import handler, clear_session, conversations, TOOLS

TEST_CONFIG = {
    "agent_model": "anthropic/claude-sonnet-4",
    "bash_timeout": 5,
    "max_iterations": 10,
}


def setup_function():
    conversations.clear()


def test_text_response():
    """Base agent replies with text when no tool call needed."""
    replies = []
    with patch("src.agents.base.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hello!", "tool_calls": None}
        handler("Hi", replies.append, TEST_CONFIG)
    assert replies == ["Hello!"]


def test_tool_then_text():
    """Base agent calls tool via dispatcher, gets output, then replies."""
    replies = []
    with patch("src.agents.base.chat_completion") as mock_llm, \
         patch("src.agents.base.execute_tool_call", return_value="file1.txt\n") as mock_exec:
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
        handler("List files", replies.append, TEST_CONFIG)
    mock_exec.assert_called_once_with("execute_bash", {"command": "ls"}, TEST_CONFIG, None)
    assert replies == ["Found file1.txt."]


def test_maintains_history():
    """Base agent maintains conversation history across calls."""
    with patch("src.agents.base.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi!", "tool_calls": None}
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="s1")
        handler("Again", lambda x: None, TEST_CONFIG, session_id="s1")
    assert len(conversations["s1"]) == 4  # user, assistant, user, assistant


def test_separate_sessions():
    """Different sessions have independent history."""
    with patch("src.agents.base.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi!", "tool_calls": None}
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="a")
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="b")
    assert len(conversations["a"]) == 2
    assert len(conversations["b"]) == 2


def test_clear_session():
    """clear_session removes history."""
    with patch("src.agents.base.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi!", "tool_calls": None}
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="x")
    assert "x" in conversations
    clear_session("x")
    assert "x" not in conversations


def test_max_iterations():
    """Base agent stops after max_iterations."""
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
    with patch("src.agents.base.chat_completion", return_value=tool_response), \
         patch("src.agents.base.execute_tool_call", return_value="loop\n"):
        handler("loop", replies.append, config)
    assert len(replies) == 1
    assert "limit" in replies[0].lower()


def test_tools_list_contains_bash():
    """TOOLS list includes bash schema."""
    names = [t["function"]["name"] for t in TOOLS]
    assert "execute_bash" in names


def test_passes_tools_to_llm():
    """TOOLS list is passed to chat_completion."""
    with patch("src.agents.base.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Ok", "tool_calls": None}
        handler("Hi", lambda x: None, TEST_CONFIG)
    passed_tools = mock_llm.call_args[1]["tools"]
    assert passed_tools == TOOLS
