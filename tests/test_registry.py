from src.agents import AGENT_NAMES, DEFAULT_AGENT, get_agent


def test_registry_has_expected_agents():
    assert "agent_one" in AGENT_NAMES


def test_default_agent():
    assert DEFAULT_AGENT == "agent_one"


def test_get_agent_returns_instance_with_handler_and_clear_session():
    agent = get_agent("agent_one")
    assert callable(agent.handler)
    assert callable(agent.clear_session)


def test_get_agent_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_agent("nonexistent")
