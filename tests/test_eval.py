import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml


def test_load_eval_config(tmp_path):
    """load_eval_config parses models and prompts from YAML."""
    config_file = tmp_path / "eval.yaml"
    config_file.write_text(yaml.dump({
        "models": [{"name": "test-model", "model": "test/model-1"}],
        "prompts": [{"name": "greeting", "text": "Hello"}],
    }))
    from eval import load_eval_config
    cfg = load_eval_config(config_file)
    assert len(cfg["models"]) == 1
    assert cfg["models"][0]["name"] == "test-model"
    assert len(cfg["prompts"]) == 1
    assert cfg["prompts"][0]["text"] == "Hello"


def test_build_agent_config():
    """build_agent_config merges model entry into base config."""
    from eval import build_agent_config
    base = {"bash_timeout": 30, "max_iterations": 10}
    model_entry = {"name": "test-model", "model": "test/model-1"}
    result = build_agent_config(model_entry, base)
    assert result["model"] == "test/model-1"
    assert result["bash_timeout"] == 30


def test_run_single():
    """run_single makes a single-shot LiteLLM call and returns structured result."""
    from eval import run_single, EVAL_SYSTEM_PROMPT

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "I'll do that."
    mock_response.choices[0].message.tool_calls = None

    with patch("eval.litellm.completion", return_value=mock_response) as mock_comp:
        result, elapsed = run_single("Hello", "test/model-1")

    assert result["content"] == "I'll do that."
    assert result["tool_calls"] is None
    assert elapsed >= 0
    # Verify it used the eval system prompt
    call_args = mock_comp.call_args
    messages = call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "Ubuntu" in messages[0]["content"]


def test_run_single_with_tool_calls():
    """run_single captures tool_calls from response."""
    from eval import run_single

    mock_tc = MagicMock()
    mock_tc.id = "call_1"
    mock_tc.type = "function"
    mock_tc.function.name = "execute_bash"
    mock_tc.function.arguments = '{"command": "ls"}'

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Let me check."
    mock_response.choices[0].message.tool_calls = [mock_tc]

    with patch("eval.litellm.completion", return_value=mock_response):
        result, elapsed = run_single("List files", "test/model-1")

    assert result["content"] == "Let me check."
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["function"]["name"] == "execute_bash"


def test_run_single_error():
    """run_single captures exceptions."""
    from eval import run_single

    with patch("eval.litellm.completion", side_effect=Exception("API down")):
        result, elapsed = run_single("Hello", "test/model-1")

    assert "ERROR" in result["content"]


def test_write_report(tmp_path):
    """write_report generates markdown with all results."""
    from eval import write_report
    results = [
        {
            "prompt_name": "greeting",
            "prompt_text": "Hello",
            "model_results": [
                {"model_name": "model-a", "response": "Hi there!", "elapsed": 1.5},
                {"model_name": "model-b", "response": "Hey!", "elapsed": 2.0},
            ],
        }
    ]
    output = tmp_path / "report.md"
    write_report(results, output)
    text = output.read_text()
    assert "# Eval Results" in text
    assert "Hello" in text
    assert "model-a" in text
    assert "Hi there!" in text
    assert "1.5s" in text


def test_format_response_text_only():
    """format_response returns content when no tool calls."""
    from eval import format_response
    result = {"content": "Hello there!", "tool_calls": None}
    assert format_response(result) == "Hello there!"


def test_format_response_with_tool_calls():
    """format_response includes tool call details."""
    from eval import format_response
    result = {
        "content": "I'll set that up for you.",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "execute_bash",
                    "arguments": '{"command": "crontab -e"}',
                },
            }
        ],
    }
    text = format_response(result)
    assert "I'll set that up for you." in text
    assert "execute_bash" in text
    assert "crontab -e" in text
