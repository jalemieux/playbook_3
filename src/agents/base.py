"""Stateful multi-tool experimental agent."""
import json

from src.llm import chat_completion, TOOL_SCHEMA as BASH_SCHEMA
from src.bash import execute_bash

SYSTEM_PROMPT = """You are a personal assistant. Use your tools to accomplish tasks on the user's computer.

When you receive a message:
- If it requires action, use your tools to accomplish it.
- If it's conversational, just reply.
- If you're unsure what the user wants, ask.

Keep replies short and direct."""

# Tool registry — add new tool schemas here
TOOLS = [BASH_SCHEMA]


# Tool executors — map tool name to (executor_fn, arg_extractor_fn)
def _exec_bash(args, config, status_fn):
    command = args["command"]
    timeout = config.get("bash_timeout", 30)
    if status_fn:
        status_fn("tool_call", f'Bash("{command}")')
    try:
        output = execute_bash(command, timeout=timeout)
    except TimeoutError as e:
        output = f"Error: {e}"
    if status_fn:
        status_fn("tool_result", _truncate(output.strip()))
    return output


EXECUTORS = {
    "execute_bash": _exec_bash,
}

# In-memory conversation store
conversations: dict[str, list[dict]] = {}


def _truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n  … truncated ({len(text)} chars total)"


def clear_session(session_id: str) -> None:
    """Clear conversation history for a session."""
    conversations.pop(session_id, None)


def handler(text: str, reply_fn, config: dict, session_id: str = "default", status_fn=None) -> None:
    """Process a user message through the base agent."""
    model = config["agent_model"]
    max_iter = config.get("max_iterations", 10)

    if session_id not in conversations:
        conversations[session_id] = []
    history = conversations[session_id]

    history.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    for i in range(max_iter):
        if status_fn:
            status_fn("thinking", "")
        result = chat_completion(messages, model, tools=TOOLS)
        if status_fn:
            status_fn("done_thinking", "")

        if result["tool_calls"] is None:
            response = result["content"] or "[no response]"
            history.append({"role": "assistant", "content": response})
            reply_fn(response)
            return

        assistant_msg = {"role": "assistant", "tool_calls": result["tool_calls"], "content": result.get("content")}
        history.append(assistant_msg)
        messages.append(assistant_msg)

        for tool_call in result["tool_calls"]:
            name = tool_call["function"]["name"]
            args = json.loads(tool_call["function"]["arguments"])

            executor = EXECUTORS.get(name)
            if executor:
                output = executor(args, config, status_fn)
            else:
                output = f"Error: unknown tool '{name}'"

            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": output,
            }
            history.append(tool_msg)
            messages.append(tool_msg)

    fallback = "Stopped: reached maximum iteration limit."
    history.append({"role": "assistant", "content": fallback})
    reply_fn(fallback)
