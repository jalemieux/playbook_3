"""Tool call dispatcher."""

from __future__ import annotations

from typing import Any

from src.tools.bash_tool import exec_bash
from src.tools.fs_tools import exec_edit, exec_glob, exec_grep, exec_notebook_edit, exec_read, exec_write
from src.tools.meta_tools import (
    exec_ask_user_question,
    exec_enter_plan_mode,
    exec_enter_worktree,
    exec_exit_plan_mode,
    exec_skill,
)
from src.tools.task_tools import (
    exec_task,
    exec_task_create,
    exec_task_get,
    exec_task_list,
    exec_task_output,
    exec_task_stop,
    exec_task_update,
)
from src.tools.web_tools import exec_web_fetch, exec_web_search

EXECUTORS: dict[str, Any] = {
    "execute_bash": exec_bash,
    "bash": exec_bash,
    "task": exec_task,
    "taskoutput": exec_task_output,
    "glob": exec_glob,
    "grep": exec_grep,
    "read": exec_read,
    "edit": exec_edit,
    "write": exec_write,
    "notebookedit": exec_notebook_edit,
    "webfetch": exec_web_fetch,
    "websearch": exec_web_search,
    "askuserquestion": exec_ask_user_question,
    "taskcreate": exec_task_create,
    "taskget": exec_task_get,
    "taskupdate": exec_task_update,
    "tasklist": exec_task_list,
    "taskstop": exec_task_stop,
    "skill": exec_skill,
    "enterplanmode": exec_enter_plan_mode,
    "exitplanmode": exec_exit_plan_mode,
    "enterworktree": exec_enter_worktree,
}


def execute_tool_call(name: str, args: dict[str, Any], config: dict, status_fn=None) -> str:
    executor = EXECUTORS.get(name.lower())
    if not executor:
        return f"Error: unknown tool '{name}'"
    try:
        return executor(args, config, status_fn)
    except Exception as e:
        return f"Error running tool '{name}': {e}"
