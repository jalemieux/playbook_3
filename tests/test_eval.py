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
    base = {"openrouter_api_key": "sk-test", "bash_timeout": 30, "max_iterations": 10}
    model_entry = {"name": "test-model", "model": "test/model-1"}
    result = build_agent_config(model_entry, base)
    assert result["model"] == "test/model-1"
    assert result["openrouter_api_key"] == "sk-test"
    assert result["bash_timeout"] == 30


def test_run_single():
    """run_single calls handler and returns (response, elapsed)."""
    from eval import run_single
    config = {"model": "test/model-1", "openrouter_api_key": "sk-test",
              "bash_timeout": 5, "max_iterations": 10}
    with patch("eval.handler") as mock_handler:
        def fake_handler(text, reply_fn, cfg, status_fn=None):
            reply_fn("test response")
        mock_handler.side_effect = fake_handler
        response, elapsed = run_single("Hello", config)
    assert response == "test response"
    assert elapsed >= 0


def test_run_single_error():
    """run_single captures exceptions as error text."""
    from eval import run_single
    config = {"model": "test/model-1", "openrouter_api_key": "sk-test",
              "bash_timeout": 5, "max_iterations": 10}
    with patch("eval.handler", side_effect=Exception("API down")):
        response, elapsed = run_single("Hello", config)
    assert "ERROR" in response
    assert "API down" in response


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
