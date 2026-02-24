import os
import tempfile
from pathlib import Path

from src.config import load_config


def test_load_config_reads_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("model: anthropic/claude-sonnet-4\nbash_timeout: 30\n")
    cfg = load_config(config_file)
    assert cfg["model"] == "anthropic/claude-sonnet-4"
    assert cfg["bash_timeout"] == 30


def test_load_config_interpolates_env_vars(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "sk-secret-123")
    config_file = tmp_path / "config.yaml"
    config_file.write_text("api_key: ${TEST_API_KEY}\n")
    cfg = load_config(config_file)
    assert cfg["api_key"] == "sk-secret-123"


def test_load_config_missing_env_var_raises(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("api_key: ${NONEXISTENT_VAR_12345}\n")
    try:
        load_config(config_file)
        assert False, "Should have raised"
    except ValueError as e:
        assert "NONEXISTENT_VAR_12345" in str(e)
