"""Bash tool schemas and executors."""

from __future__ import annotations

import subprocess
from typing import Any

from src.tools.utils import truncate

EXECUTE_BASH_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "execute_bash",
        "description": (
            "Run a shell command for system actions (installing, building, running commands). "
            "Use this when the task requires command execution, not file search/read."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Exact shell command to execute.",
                }
            },
            "required": ["command"],
        },
    },
}

BASH_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "Bash",
        "description": (
            "Execute shell commands when real command execution is required. "
            "Prefer Glob/Grep/Read/Edit/Write for codebase inspection and edits."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute.",
                },
                "description": {
                    "type": "string",
                    "description": "Short explanation of intent of the command.",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in milliseconds for this command execution.",
                },
                "run_in_background": {
                    "type": "boolean",
                    "description": "Run asynchronously and return a task id immediately.",
                },
            },
            "required": ["command"],
        },
    },
}


def exec_bash(args: dict[str, Any], config: dict, status_fn=None) -> str:
    command = args["command"]
    timeout = int(args.get("timeout") or config.get("bash_timeout", 30))

    if status_fn:
        status_fn("tool_call", f'Bash("{command}")')

    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
    except TimeoutError as e:
        output = f"Error: {e}"

    if status_fn:
        status_fn("tool_result", truncate(output.strip()))
    return output
