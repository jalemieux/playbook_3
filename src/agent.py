import json

from src.llm import chat_completion
from src.bash import execute_bash

SYSTEM_PROMPT = """You are a personal assistant. You have one tool: execute_bash. Use it to accomplish tasks on the user's computer. You are running on Ubuntu.

When you receive a message:
- If it requires action, use bash to accomplish it.
- If it's conversational, just reply.
- If you're unsure what the user wants, ask.

Keep replies short and direct."""


def _truncate(text: str, max_len: int = 200) -> str:
    """Truncate text with ellipsis indicator."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n  … truncated ({len(text)} chars total)"


def run(text: str, config: dict, status_fn=None) -> str:
    """Execute a task through the agent loop. Returns the final response text."""
    model = config["agent_model"]
    timeout = config.get("bash_timeout", 30)
    max_iter = config.get("max_iterations", 10)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]

    for i in range(max_iter):
        if status_fn:
            status_fn("thinking", "")
        result = chat_completion(messages, model)
        if status_fn:
            status_fn("done_thinking", "")

        if result["tool_calls"] is None:
            return result["content"] or "[no response]"

        messages.append({"role": "assistant", "tool_calls": result["tool_calls"], "content": result.get("content")})

        for tool_call in result["tool_calls"]:
            args = json.loads(tool_call["function"]["arguments"])
            command = args["command"]

            if status_fn:
                status_fn("tool_call", f'Bash("{command}")')

            try:
                output = execute_bash(command, timeout=timeout)
            except TimeoutError as e:
                output = f"Error: {e}"

            if status_fn:
                status_fn("tool_result", _truncate(output.strip()))

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": output,
            })

    return "Stopped: reached maximum iteration limit."


def handler(text: str, reply_fn, config: dict, status_fn=None) -> None:
    """Process a user message through the agent loop."""
    reply_fn(run(text, config, status_fn))
