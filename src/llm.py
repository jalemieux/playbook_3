import litellm

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_bash",
        "description": "Execute a bash command on the user's computer and return the output.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute.",
                }
            },
            "required": ["command"],
        },
    },
}


def chat_completion(messages: list[dict], model: str) -> dict:
    """Call LLM via LiteLLM with execute_bash tool.

    Returns dict with 'content' (str|None) and 'tool_calls' (list[dict]|None).
    """
    response = litellm.completion(
        model=model,
        messages=messages,
        tools=[TOOL_SCHEMA],
        timeout=60,
    )
    message = response.choices[0].message

    # Normalize tool_calls from litellm objects to plain dicts
    tool_calls = None
    if message.tool_calls:
        tool_calls = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ]

    return {
        "content": message.content,
        "tool_calls": tool_calls,
    }
