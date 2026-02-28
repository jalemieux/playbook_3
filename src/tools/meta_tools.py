"""Meta and control tool schemas and executors."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from src.tools.utils import to_json

ASK_USER_QUESTION_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "AskUserQuestion",
        "description": (
            "Request structured user input when a decision is required and cannot be inferred."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "1-4 question objects with headers and options.",
                }
            },
            "required": ["questions"],
        },
    },
}

SKILL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "Skill",
        "description": "Invoke a named skill/slash-command workflow when applicable.",
        "parameters": {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": "Skill identifier, e.g. commit, review-pr, pdf.",
                },
                "args": {
                    "type": "string",
                    "description": "Optional raw arguments passed to the skill.",
                },
            },
            "required": ["skill"],
        },
    },
}

ENTER_PLAN_MODE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "EnterPlanMode",
        "description": (
            "Switch to planning-first workflow before implementing non-trivial changes."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}

EXIT_PLAN_MODE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "ExitPlanMode",
        "description": "Signal plan completion and request user approval to implement.",
        "parameters": {
            "type": "object",
            "properties": {
                "allowedPrompts": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Optional prompt-based permissions needed for implementation.",
                },
            },
        },
    },
}

ENTER_WORKTREE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "EnterWorktree",
        "description": (
            "Create and switch into an isolated git worktree. "
            "Use only when user explicitly requests worktree workflow."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Optional custom worktree name.",
                }
            },
        },
    },
}


def exec_ask_user_question(args: dict[str, Any], config: dict, status_fn=None) -> str:
    return to_json(
        {
            "status": "needs_user_input",
            "message": "AskUserQuestion requires UI integration in this runtime.",
            "questions": args.get("questions", []),
        }
    )


def exec_skill(args: dict[str, Any], config: dict, status_fn=None) -> str:
    return to_json(
        {
            "status": "not_supported",
            "message": f"Skill '{args.get('skill', '')}' is not installed.",
            "args": args.get("args", ""),
        }
    )


def exec_enter_plan_mode(args: dict[str, Any], config: dict, status_fn=None) -> str:
    return to_json({"status": "ok", "mode": "plan"})


def exec_exit_plan_mode(args: dict[str, Any], config: dict, status_fn=None) -> str:
    return to_json({"status": "ok", "mode": "default", "allowedPrompts": args.get("allowedPrompts", [])})


def exec_enter_worktree(args: dict[str, Any], config: dict, status_fn=None) -> str:
    root = Path.cwd()
    if not (root / ".git").exists():
        return to_json({"error": "Not a git repository"})

    name = args.get("name") or f"worktree-{int(time.time())}"
    target = root / ".worktrees" / name
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(["git", "worktree", "add", str(target)], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        return to_json({"error": e.stderr.strip() or str(e)})

    return to_json({"status": "ok", "path": str(target)})
