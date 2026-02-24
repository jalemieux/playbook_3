from unittest.mock import patch, MagicMock

from src.llm import chat_completion, TOOL_SCHEMA


def _mock_litellm_response(content=None, tool_calls=None):
    """Build a fake litellm response object."""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def test_chat_completion_text_response():
    mock_resp = _mock_litellm_response(content="Hello!")
    with patch("src.llm.litellm.completion", return_value=mock_resp) as mock_call:
        result = chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            model="anthropic/claude-sonnet-4",
        )
    assert result["content"] == "Hello!"
    assert result["tool_calls"] is None
    mock_call.assert_called_once()


def test_chat_completion_tool_call():
    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.type = "function"
    tool_call.function.name = "execute_bash"
    tool_call.function.arguments = '{"command": "ls"}'

    mock_resp = _mock_litellm_response(tool_calls=[tool_call])
    with patch("src.llm.litellm.completion", return_value=mock_resp):
        result = chat_completion(
            messages=[{"role": "user", "content": "List files"}],
            model="openai/gpt-4o",
        )
    assert result["tool_calls"] is not None
    assert result["tool_calls"][0]["function"]["name"] == "execute_bash"


def test_chat_completion_passes_model_and_tools():
    mock_resp = _mock_litellm_response(content="ok")
    with patch("src.llm.litellm.completion", return_value=mock_resp) as mock_call:
        chat_completion(
            messages=[{"role": "user", "content": "test"}],
            model="minimax/minimax-m1",
        )
    call_kwargs = mock_call.call_args
    assert call_kwargs.kwargs["model"] == "minimax/minimax-m1"
    assert len(call_kwargs.kwargs["tools"]) == 1
    assert call_kwargs.kwargs["tools"][0]["function"]["name"] == "execute_bash"


def test_tool_schema_has_execute_bash():
    assert TOOL_SCHEMA["function"]["name"] == "execute_bash"
    params = TOOL_SCHEMA["function"]["parameters"]
    assert "command" in params["properties"]
