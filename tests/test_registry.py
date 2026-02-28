from src.agents import AGENTS, DEFAULT_AGENT, get_agent


def test_registry_has_expected_agents():
    assert "orchestrator" in AGENTS
    assert "single" in AGENTS
    assert "base" in AGENTS


def test_default_agent():
    assert DEFAULT_AGENT == "orchestrator"


def test_get_agent_returns_handler():
    handler = get_agent("single")
    assert callable(handler)


def test_get_agent_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_agent("nonexistent")


def test_all_agents_have_clear_session():
    from src.agents import get_clear_session
    for name in AGENTS:
        assert callable(get_clear_session(name))
