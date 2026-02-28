"""Tool schema registry and profile selection."""

from __future__ import annotations

from typing import Any

from src.tools.bash_tool import BASH_SCHEMA, EXECUTE_BASH_SCHEMA
from src.tools.fs_tools import (
    EDIT_SCHEMA,
    GLOB_SCHEMA,
    GREP_SCHEMA,
    NOTEBOOK_EDIT_SCHEMA,
    READ_SCHEMA,
    WRITE_SCHEMA,
)
from src.tools.meta_tools import (
    ASK_USER_QUESTION_SCHEMA,
    ENTER_PLAN_MODE_SCHEMA,
    ENTER_WORKTREE_SCHEMA,
    EXIT_PLAN_MODE_SCHEMA,
    SKILL_SCHEMA,
)
from src.tools.task_tools import (
    TASK_CREATE_SCHEMA,
    TASK_GET_SCHEMA,
    TASK_LIST_SCHEMA,
    TASK_OUTPUT_SCHEMA,
    TASK_SCHEMA,
    TASK_STOP_SCHEMA,
    TASK_UPDATE_SCHEMA,
)
from src.tools.web_tools import WEB_FETCH_SCHEMA, WEB_SEARCH_SCHEMA

SCHEMAS_BY_NAME: dict[str, dict[str, Any]] = {
    "execute_bash": EXECUTE_BASH_SCHEMA,
    "Task": TASK_SCHEMA,
    "TaskOutput": TASK_OUTPUT_SCHEMA,
    "Bash": BASH_SCHEMA,
    "Glob": GLOB_SCHEMA,
    "Grep": GREP_SCHEMA,
    "Read": READ_SCHEMA,
    "Edit": EDIT_SCHEMA,
    "Write": WRITE_SCHEMA,
    "NotebookEdit": NOTEBOOK_EDIT_SCHEMA,
    "WebFetch": WEB_FETCH_SCHEMA,
    "WebSearch": WEB_SEARCH_SCHEMA,
    "AskUserQuestion": ASK_USER_QUESTION_SCHEMA,
    "TaskCreate": TASK_CREATE_SCHEMA,
    "TaskGet": TASK_GET_SCHEMA,
    "TaskUpdate": TASK_UPDATE_SCHEMA,
    "TaskList": TASK_LIST_SCHEMA,
    "TaskStop": TASK_STOP_SCHEMA,
    "Skill": SKILL_SCHEMA,
    "EnterPlanMode": ENTER_PLAN_MODE_SCHEMA,
    "ExitPlanMode": EXIT_PLAN_MODE_SCHEMA,
    "EnterWorktree": ENTER_WORKTREE_SCHEMA,
}

PROFILES: dict[str, list[str]] = {
    "bash_only": ["execute_bash"],
    "claude_code": [
        "Task",
        "TaskOutput",
        "Bash",
        "Glob",
        "Grep",
        "Read",
        "Edit",
        "Write",
        "NotebookEdit",
        "WebFetch",
        "WebSearch",
        "AskUserQuestion",
        "TaskCreate",
        "TaskGet",
        "TaskUpdate",
        "TaskList",
        "TaskStop",
        "Skill",
        "EnterPlanMode",
        "ExitPlanMode",
        "EnterWorktree",
    ],
}


def get_schemas_by_names(names: list[str]) -> list[dict[str, Any]]:
    """Resolve a list of tool names into LiteLLM schemas."""
    out = []
    for name in names:
        schema = SCHEMAS_BY_NAME.get(name)
        if schema:
            out.append(schema)
    return out


def get_schemas_for_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve configured tool set.

    Config options:
    - `agent_tools`: explicit list of tool names (highest priority)
    - `agent_tool_profile`: profile name in PROFILES (default: bash_only)
    """
    explicit = config.get("agent_tools")
    if isinstance(explicit, list) and explicit:
        return get_schemas_by_names(explicit)

    profile = config.get("agent_tool_profile", "bash_only")
    names = PROFILES.get(profile, PROFILES["bash_only"])
    return get_schemas_by_names(names)
