"""Stateful multi-tool experimental agent."""
import json

from src.llm import chat_completion
from src.tools import execute_tool_call, get_schemas_for_config
from src.tools.utils import truncate

SYSTEM_PROMPT = """You are a personal assistant. Use your tools to accomplish tasks on the user's computer.

When you receive a message:
- If it requires action, use your tools to accomplish it.
- If it's conversational, just reply.
- If you're unsure what the user wants, ask.

## Your context: 

You can find your memories in ./MEMORY.md
Your identity is in ./IDENTITY.md
Your tasks are in ./TASKS.md

## Response Protocol

Before asking the user for information, ALWAYS search your context first.

Keep replies short and direct."""

# In-memory conversation store
conversations: dict[str, list[dict]] = {}


def clear_session(session_id: str) -> None:
    """Clear conversation history for a session."""
    conversations.pop(session_id, None)


def handler(text: str, reply_fn, config: dict, session_id: str = "default", status_fn=None) -> None:
    """Process a user message through the base agent."""
    model = config["base_model"]
    max_iter = config.get("base_max_iterations", 10)
    tools = get_schemas_for_config(config)
    if session_id not in conversations:
        conversations[session_id] = []
    history = conversations[session_id]

    history.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    for i in range(max_iter):
        if status_fn:
            status_fn("thinking", "")
        result = chat_completion(messages, model, tools=tools)
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

            if status_fn:
                status_fn("tool_call", f"{name}({json.dumps(args)[:120]})")

            output = execute_tool_call(name, args, config, status_fn)

            if status_fn:
                status_fn("tool_result", truncate(str(output).strip()))

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
