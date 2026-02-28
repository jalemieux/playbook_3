from src.agents.orchestrator import handler as _orchestrator_handler, clear_session as _orchestrator_clear
from src.agents.single import handler as _single_handler, clear_session as _single_clear
from src.agents.base import handler as _base_handler, clear_session as _base_clear

AGENTS = {
    "orchestrator": _orchestrator_handler,
    "single": _single_handler,
    "base": _base_handler,
}

_CLEAR_SESSIONS = {
    "orchestrator": _orchestrator_clear,
    "single": _single_clear,
    "base": _base_clear,
}

DEFAULT_AGENT = "orchestrator"


def get_agent(name: str):
    """Get an agent handler by name. Raises KeyError if not found."""
    return AGENTS[name]


def get_clear_session(name: str):
    """Get a clear_session function by agent name. Raises KeyError if not found."""
    return _CLEAR_SESSIONS[name]
