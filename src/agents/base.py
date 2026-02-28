"""Stateful multi-tool experimental agent. Tools TBD."""

conversations: dict[str, list[dict]] = {}


def clear_session(session_id: str) -> None:
    """Clear conversation history for a session."""
    conversations.pop(session_id, None)


def handler(text: str, reply_fn, config: dict, session_id: str = "default", status_fn=None) -> None:
    """Placeholder — replaced in Task 4."""
    reply_fn("[base agent not yet implemented]")
