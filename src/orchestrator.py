import json

from src.llm import chat_completion
from src.agent import run as agent_run

SYSTEM_PROMPT = """You are a personal assistant. You have one tool: execute_task. Use it to accomplish tasks by describing what needs to be done. Evaluate results and retry with clearer instructions if needed. Keep replies short and direct."""

EXECUTE_TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_task",
        "description": "Execute a task on the user's computer. Describe the intent clearly.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "Clear description of what needs to be accomplished.",
                }
            },
            "required": ["intent"],
        },
    },
}

# In-memory conversation store: session_id -> list of messages
conversations: dict[str, list[dict]] = {}


def clear_session(session_id: str) -> None:
    """Clear conversation history for a session."""
    conversations.pop(session_id, None)


def handler(text: str, reply_fn, config: dict, session_id: str = "default", status_fn=None) -> None:
    """Process a user message through the orchestrator."""
    model = config.get("orchestrator_model", config["model"])
    max_iter = config.get("orchestrator_max_iterations", 5)

    # Get or create conversation history
    if session_id not in conversations:
        conversations[session_id] = []
    history = conversations[session_id]

    # Add user message to history
    history.append({"role": "user", "content": text})

    # Build messages: system + conversation history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    for i in range(max_iter):
        if status_fn:
            status_fn("thinking", "")
        result = chat_completion(messages, model, tools=[EXECUTE_TASK_SCHEMA])
        if status_fn:
            status_fn("done_thinking", "")

        if result["tool_calls"] is None:
            response = result["content"] or "[no response]"
            history.append({"role": "assistant", "content": response})
            reply_fn(response)
            return

        # Process tool calls
        assistant_msg = {"role": "assistant", "tool_calls": result["tool_calls"], "content": result.get("content")}
        history.append(assistant_msg)
        messages.append(assistant_msg)

        for tool_call in result["tool_calls"]:
            args = json.loads(tool_call["function"]["arguments"])
            intent = args["intent"]

            if status_fn:
                status_fn("tool_call", f'Task("{intent}")')

            task_result = agent_run(intent, config, status_fn)

            if status_fn:
                status_fn("tool_result", task_result[:200])

            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": task_result,
            }
            history.append(tool_msg)
            messages.append(tool_msg)

    fallback = "Stopped: reached orchestrator iteration limit."
    history.append({"role": "assistant", "content": fallback})
    reply_fn(fallback)
