import httpx

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

API_URL = "https://openrouter.ai/api/v1/chat/completions"


def chat_completion(
    messages: list[dict],
    model: str,
    api_key: str,
) -> dict:
    """Call OpenRouter chat completions with execute_bash tool.

    Returns dict with 'content' (str|None) and 'tool_calls' (list|None).
    """
    resp = httpx.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "tools": [TOOL_SCHEMA],
        },
        timeout=60,
    )
    resp.raise_for_status()
    message = resp.json()["choices"][0]["message"]
    return {
        "content": message.get("content"),
        "tool_calls": message.get("tool_calls"),
    }
