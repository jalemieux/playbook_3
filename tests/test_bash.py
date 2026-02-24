import pytest
from src.bash import execute_bash


def test_execute_bash_returns_stdout():
    result = execute_bash("echo hello")
    assert result.strip() == "hello"


def test_execute_bash_returns_stderr():
    result = execute_bash("echo error >&2")
    assert "error" in result


def test_execute_bash_timeout():
    with pytest.raises(TimeoutError):
        execute_bash("sleep 10", timeout=1)


def test_execute_bash_nonzero_exit():
    result = execute_bash("exit 1")
    # Should return output (empty), not raise — the model needs to see errors
    assert isinstance(result, str)
