"""Agent factory: instantiate agents with system prompt, tools, and context."""

from pathlib import Path

from src.agents.agent_one import AgentOne, DEFAULT_SYSTEM_PROMPT, DEFAULT_TOOLS

# Named tool sets for convenience
TOOL_SETS: dict[str, list[dict]] = {
    "default": DEFAULT_TOOLS,
}


def create_agent_one(
    *,
    model: str,
    max_iterations: int,
    context_dir_path: str,
    identity_file_path: str,
    name: str
) -> AgentOne:
    """Create an AgentOne with the given system prompt, tools, and context.

    - system_prompt: Full system prompt (or None for default).
    - tools: List of tool schemas (or None for default).
    - context: Extra context prepended to the system prompt (e.g. project notes).
    - name: Agent name for logging/registry.
    """
    identity_prompt = Path(identity_file_path).read_text()
    
    return AgentOne(
        model=model,
        max_iterations=max_iterations,
        system_prompt=identity_prompt + DEFAULT_SYSTEM_PROMPT.format(context_dir_path=context_dir_path),
        tools=DEFAULT_TOOLS,
        name=name,
    )

