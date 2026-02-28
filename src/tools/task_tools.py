"""Task and background-task tool schemas and executors."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from src.tools.utils import to_json

TASK_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "Task",
        "description": (
            "Delegate complex multi-step work to a specialized sub-agent. "
            "Use for open-ended tasks that benefit from autonomous execution."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed task instructions for the sub-agent.",
                },
                "description": {
                    "type": "string",
                    "description": "Short 3-5 word label for the task.",
                },
                "subagent_type": {
                    "type": "string",
                    "description": "Sub-agent type (e.g., general-purpose, Explore, Plan).",
                },
                "model": {
                    "type": "string",
                    "description": "Optional model override (haiku, sonnet, opus).",
                },
                "run_in_background": {
                    "type": "boolean",
                    "description": "Run asynchronously and return a task id immediately.",
                },
                "resume": {
                    "type": "string",
                    "description": "Existing agent/task id to resume.",
                },
                "isolation": {
                    "type": "string",
                    "description": "Optional isolation mode.",
                },
                "max_turns": {
                    "type": "integer",
                    "description": "Max internal reasoning turns for the sub-agent.",
                },
            },
            "required": ["prompt", "description", "subagent_type"],
        },
    },
}

TASK_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "TaskOutput",
        "description": "Retrieve status/output from a background task started earlier.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task identifier returned by a background run.",
                },
                "block": {
                    "type": "boolean",
                    "description": "Wait for completion before returning.",
                },
                "timeout": {
                    "type": "number",
                    "description": "Maximum wait time in milliseconds when block=true.",
                },
            },
            "required": ["task_id", "block", "timeout"],
        },
    },
}

TASK_CREATE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "TaskCreate",
        "description": "Create a structured task item for progress tracking.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Short imperative task title.",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed task requirements and scope.",
                },
                "activeForm": {
                    "type": "string",
                    "description": "Present-continuous spinner text (e.g., Running tests).",
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional structured metadata.",
                },
            },
            "required": ["subject", "description"],
        },
    },
}

TASK_GET_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "TaskGet",
        "description": "Get full details for one tracked task.",
        "parameters": {
            "type": "object",
            "properties": {
                "taskId": {
                    "type": "string",
                    "description": "Task identifier.",
                }
            },
            "required": ["taskId"],
        },
    },
}

TASK_UPDATE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "TaskUpdate",
        "description": "Update status/details/dependencies of an existing task.",
        "parameters": {
            "type": "object",
            "properties": {
                "taskId": {
                    "type": "string",
                    "description": "Task identifier.",
                },
                "status": {
                    "type": "string",
                    "description": "Task state transition.",
                    "enum": ["pending", "in_progress", "completed", "deleted"],
                },
                "subject": {"type": "string", "description": "Updated task title."},
                "description": {"type": "string", "description": "Updated details."},
                "activeForm": {"type": "string", "description": "Updated spinner text."},
                "owner": {"type": "string", "description": "Owner/agent id."},
                "metadata": {"type": "object", "description": "Metadata patch object."},
                "addBlocks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tasks blocked by this task.",
                },
                "addBlockedBy": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tasks this task depends on.",
                },
            },
            "required": ["taskId"],
        },
    },
}

TASK_LIST_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "TaskList",
        "description": "List tracked tasks to pick next work and inspect progress.",
        "parameters": {"type": "object", "properties": {}},
    },
}

TASK_STOP_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "TaskStop",
        "description": "Stop a running background task by id.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Primary background task identifier.",
                },
                "shell_id": {
                    "type": "string",
                    "description": "Deprecated alias for task_id.",
                },
            },
        },
    },
}


@dataclass
class BackgroundTask:
    task_id: str
    kind: str
    status: str = "running"
    output: str = ""
    error: str | None = None
    stop_requested: bool = False
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None


_BG_TASKS: dict[str, BackgroundTask] = {}
_BG_LOCK = threading.Lock()
_BG_COUNTER = 0

_TASKS: dict[str, dict[str, Any]] = {}
_TASK_LOCK = threading.Lock()
_TASK_COUNTER = 0


def _next_bg_id(prefix: str = "task") -> str:
    global _BG_COUNTER
    with _BG_LOCK:
        _BG_COUNTER += 1
        return f"{prefix}_{_BG_COUNTER}"


def _next_todo_id() -> str:
    global _TASK_COUNTER
    with _TASK_LOCK:
        _TASK_COUNTER += 1
        return str(_TASK_COUNTER)


def _start_background(kind: str, fn) -> str:
    task_id = _next_bg_id(kind)
    record = BackgroundTask(task_id=task_id, kind=kind)
    _BG_TASKS[task_id] = record

    def runner():
        try:
            record.output = str(fn())
            record.status = "stopped" if record.stop_requested else "completed"
        except Exception as e:  # pragma: no cover
            record.error = str(e)
            record.status = "failed"
        finally:
            record.finished_at = time.time()

    threading.Thread(target=runner, daemon=True).start()
    return task_id


def exec_task(args: dict[str, Any], config: dict, status_fn=None) -> str:
    prompt = args["prompt"]
    subagent_type = args.get("subagent_type", "general-purpose")
    if args.get("run_in_background"):
        task_id = _start_background("agent", lambda: f"[{subagent_type}] {prompt}")
        return to_json({"task_id": task_id, "status": "running"})
    return to_json({"status": "completed", "output": f"[{subagent_type}] {prompt}"})


def exec_task_output(args: dict[str, Any], config: dict, status_fn=None) -> str:
    task_id = args["task_id"]
    block = bool(args.get("block", True))
    timeout_ms = int(args.get("timeout", 30000))

    task = _BG_TASKS.get(task_id)
    if not task:
        return to_json({"error": f"Unknown task_id: {task_id}"})

    if block and task.status == "running":
        deadline = time.time() + timeout_ms / 1000.0
        while task.status == "running" and time.time() < deadline:
            time.sleep(0.02)

    return to_json({"task_id": task_id, "status": task.status, "output": task.output, "error": task.error})


def exec_task_create(args: dict[str, Any], config: dict, status_fn=None) -> str:
    task_id = _next_todo_id()
    task = {
        "id": task_id,
        "subject": args["subject"],
        "description": args["description"],
        "activeForm": args.get("activeForm", ""),
        "status": "pending",
        "owner": "",
        "metadata": args.get("metadata", {}),
        "blocks": [],
        "blockedBy": [],
    }
    _TASKS[task_id] = task
    return to_json(task)


def exec_task_get(args: dict[str, Any], config: dict, status_fn=None) -> str:
    task = _TASKS.get(args["taskId"])
    if not task:
        return to_json({"error": "task not found"})
    return to_json(task)


def exec_task_update(args: dict[str, Any], config: dict, status_fn=None) -> str:
    task = _TASKS.get(args["taskId"])
    if not task:
        return to_json({"error": "task not found"})

    if args.get("status") == "deleted":
        _TASKS.pop(args["taskId"], None)
        return to_json({"id": args["taskId"], "status": "deleted"})

    for key in ["status", "subject", "description", "activeForm", "owner"]:
        if key in args and args[key] is not None:
            task[key] = args[key]

    if isinstance(args.get("metadata"), dict):
        meta = task.get("metadata", {})
        for k, v in args["metadata"].items():
            if v is None:
                meta.pop(k, None)
            else:
                meta[k] = v
        task["metadata"] = meta

    if isinstance(args.get("addBlocks"), list):
        task["blocks"] = sorted(set(task.get("blocks", []) + args["addBlocks"]))
    if isinstance(args.get("addBlockedBy"), list):
        task["blockedBy"] = sorted(set(task.get("blockedBy", []) + args["addBlockedBy"]))

    return to_json(task)


def exec_task_list(args: dict[str, Any], config: dict, status_fn=None) -> str:
    rows = [
        {
            "id": t["id"],
            "subject": t["subject"],
            "status": t["status"],
            "owner": t["owner"],
            "blockedBy": t["blockedBy"],
        }
        for t in sorted(_TASKS.values(), key=lambda x: int(x["id"]))
    ]
    return to_json(rows)


def exec_task_stop(args: dict[str, Any], config: dict, status_fn=None) -> str:
    task_id = args.get("task_id") or args.get("shell_id")
    if not task_id:
        return to_json({"error": "task_id is required"})
    task = _BG_TASKS.get(task_id)
    if not task:
        return to_json({"error": "task not found"})

    task.stop_requested = True
    if task.status == "running":
        task.status = "stopped"
        task.finished_at = time.time()

    return to_json({"task_id": task_id, "status": task.status})
