import json
from unittest.mock import patch, MagicMock

from src.openrouter import chat_completion, TOOL_SCHEMA


def _mock_response(content=None, tool_calls=None):
    """Build a fake httpx response matching OpenRouter format."""
    message = {}
    if content:
        message["content"] = content
    if tool_calls:
        message["tool_calls"] = tool_calls
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"choices": [{"message": message}]}
    resp.raise_for_status = MagicMock()
    return resp


def test_chat_completion_text_response():
    with patch("src.openrouter.httpx.post", return_value=_mock_response(content="Hello!")):
        result = chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            model="anthropic/claude-sonnet-4",
            api_key="sk-test",
        )
    assert result["content"] == "Hello!"
    assert result["tool_calls"] is None


def test_chat_completion_tool_call():
    tool_calls = [{
        "id": "call_1",
        "type": "function",
        "function": {"name": "execute_bash", "arguments": '{"command": "ls"}'},
    }]
    with patch("src.openrouter.httpx.post", return_value=_mock_response(tool_calls=tool_calls)):
        result = chat_completion(
            messages=[{"role": "user", "content": "List files"}],
            model="anthropic/claude-sonnet-4",
            api_key="sk-test",
        )
    assert result["tool_calls"] is not None
    assert result["tool_calls"][0]["function"]["name"] == "execute_bash"


def test_tool_schema_has_execute_bash():
    assert TOOL_SCHEMA["function"]["name"] == "execute_bash"
    params = TOOL_SCHEMA["function"]["parameters"]
    assert "command" in params["properties"]
