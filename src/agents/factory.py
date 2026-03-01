"""Agent factory: instantiate agents with system prompt, tools, and context."""

from pathlib import Path

from src.agents.agent_one import AgentOne, DEFAULT_TOOLS

# Named tool sets for convenience
TOOL_SETS: dict[str, list[dict]] = {
    "default": DEFAULT_TOOLS,
}

DEFAULT_SYSTEM_PROMPT = """
You are a personal assistant helping the user with their tasks. 

## Your context:
Your identity is in `{identity_file_path}`.
Who your user is in `{context_dir_path}/USER.md`.
Your memories are stored in `{context_dir_path}/MEMORY.md`.
Your tasks are in `{context_dir_path}/TASKS.md`.

## Response Protocol
- Before asking the user for information, ALWAYS search your context first.
- You have tools to accomplish tasks on the user's computer.
- If you don't have the information, ask the user for it.
- If the user greets you, say hello back.
- If you receive a system notification, let the user know.


Keep replies short and direct."""

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
    system_prompt = DEFAULT_SYSTEM_PROMPT.format(context_dir_path=context_dir_path, identity_file_path=identity_file_path)
    print(system_prompt)
    return AgentOne(
        model=model,
        max_iterations=max_iterations,
        system_prompt=system_prompt,
        tools=DEFAULT_TOOLS,
        name=name,
    )

