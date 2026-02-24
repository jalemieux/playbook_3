import json
from unittest.mock import patch, MagicMock

from src.orchestrator import handler, conversations, EXECUTE_TASK_SCHEMA

TEST_CONFIG = {
    "model": "anthropic/claude-sonnet-4",
    "orchestrator_model": "anthropic/claude-sonnet-4",
    "orchestrator_max_iterations": 5,
    "bash_timeout": 5,
    "max_iterations": 10,
}


def setup_function():
    """Clear conversation history between tests."""
    conversations.clear()


def test_orchestrator_text_response():
    """Orchestrator replies with text when no tool call needed."""
    replies = []
    with patch("src.orchestrator.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi there!", "tool_calls": None}
        handler("Hello", replies.append, TEST_CONFIG)
    assert replies == ["Hi there!"]


def test_orchestrator_calls_agent():
    """Orchestrator calls execute_task, gets agent result, replies."""
    replies = []
    with patch("src.orchestrator.chat_completion") as mock_llm, \
         patch("src.orchestrator.agent_run", return_value="file1.txt") as mock_agent:
        mock_llm.side_effect = [
            {
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "execute_task",
                        "arguments": json.dumps({"intent": "list files"}),
                    },
                }],
            },
            {"content": "You have file1.txt.", "tool_calls": None},
        ]
        handler("What files do I have?", replies.append, TEST_CONFIG)
    mock_agent.assert_called_once_with("list files", TEST_CONFIG, None)
    assert replies == ["You have file1.txt."]


def test_orchestrator_maintains_history():
    """Orchestrator maintains conversation history across calls."""
    with patch("src.orchestrator.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi!", "tool_calls": None}
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="test1")
        handler("How are you?", lambda x: None, TEST_CONFIG, session_id="test1")
    assert len(conversations["test1"]) == 4  # user, assistant, user, assistant


def test_orchestrator_separate_sessions():
    """Different session IDs maintain separate histories."""
    with patch("src.orchestrator.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi!", "tool_calls": None}
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="a")
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="b")
    assert len(conversations["a"]) == 2
    assert len(conversations["b"]) == 2


def test_orchestrator_max_iterations():
    """Orchestrator stops after max_iterations."""
    config = {**TEST_CONFIG, "orchestrator_max_iterations": 2}
    replies = []
    tool_response = {
        "content": None,
        "tool_calls": [{
            "id": "call_n",
            "type": "function",
            "function": {
                "name": "execute_task",
                "arguments": json.dumps({"intent": "do something"}),
            },
        }],
    }
    with patch("src.orchestrator.chat_completion", return_value=tool_response), \
         patch("src.orchestrator.agent_run", return_value="result"):
        handler("loop forever", replies.append, config)
    assert len(replies) == 1
    assert "limit" in replies[0].lower()


def test_orchestrator_clear_session():
    """clear_session removes history for a session."""
    from src.orchestrator import clear_session
    with patch("src.orchestrator.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi!", "tool_calls": None}
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="test")
    assert "test" in conversations
    clear_session("test")
    assert "test" not in conversations


def test_execute_task_schema_structure():
    """Tool schema has correct structure."""
    assert EXECUTE_TASK_SCHEMA["function"]["name"] == "execute_task"
    params = EXECUTE_TASK_SCHEMA["function"]["parameters"]
    assert "intent" in params["properties"]
    assert params["required"] == ["intent"]
