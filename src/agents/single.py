import json

from src.llm import chat_completion
from src.tools import execute_tool_call, get_schemas_for_config
from src.tools.utils import truncate


SYSTEM_PROMPT = """You are a personal assistant. Use your tools to accomplish tasks on the user's computer.

When you receive a message:
- If it requires action, use your tools to accomplish it.
- If it's conversational, just reply.
- If you're unsure what the user wants, ask.

Keep replies short and direct."""


def run(text: str, config: dict, status_fn=None) -> str:
    model = config["agent_model"]
    max_iter = config.get("max_iterations", 10)
    tools = get_schemas_for_config(config)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]

    for i in range(max_iter):
        if status_fn:
            status_fn("thinking", "")
        result = chat_completion(messages, model, tools=tools)
        if status_fn:
            status_fn("done_thinking", "")

        if result["tool_calls"] is None:
            return result["content"] or "[no response]"

        messages.append({"role": "assistant", "tool_calls": result["tool_calls"], "content": result.get("content")})

        for tool_call in result["tool_calls"]:
            name = tool_call["function"]["name"]
            args = json.loads(tool_call["function"]["arguments"])
            output = execute_tool_call(name, args, config, status_fn)

            if status_fn:
                status_fn("tool_result", truncate(str(output).strip()))

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": output,
            })

    return "Stopped: reached maximum iteration limit."


def clear_session(session_id: str) -> None:
    """No-op: single agent is stateless."""
    pass


def handler(text: str, reply_fn, config: dict, session_id: str = "default", status_fn=None) -> None:
    """Process a user message through the agent loop."""
    reply_fn(run(text, config, status_fn))
