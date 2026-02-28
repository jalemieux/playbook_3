"""Filesystem-oriented tool schemas and executors."""

from __future__ import annotations

import glob as pyglob
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from src.tools.utils import resolve_path, to_json

GLOB_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "Glob",
        "description": (
            "Find files by path pattern (for example src/**/*.py). "
            "Use before Read when file locations are unknown."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files.",
                },
                "path": {
                    "type": "string",
                    "description": "Optional base directory for the glob search.",
                },
            },
            "required": ["pattern"],
        },
    },
}

GREP_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "Grep",
        "description": (
            "Search file contents by regex or keyword using ripgrep behavior. "
            "Use for locating symbols, strings, and implementation points."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex or literal-like pattern to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "Optional file or directory to search within.",
                },
                "glob": {
                    "type": "string",
                    "description": "Optional glob to filter target files (e.g. *.py).",
                },
                "type": {
                    "type": "string",
                    "description": "Optional language/file type filter (e.g. py, js).",
                },
                "output_mode": {
                    "type": "string",
                    "description": "Result format: files_with_matches, content, or count.",
                    "enum": ["files_with_matches", "content", "count"],
                },
                "-A": {
                    "type": "number",
                    "description": "Lines of trailing context after each match.",
                },
                "-B": {
                    "type": "number",
                    "description": "Lines of leading context before each match.",
                },
                "context": {
                    "type": "number",
                    "description": "Symmetric context lines before and after matches.",
                },
                "-i": {
                    "type": "boolean",
                    "description": "Case-insensitive search.",
                },
                "-n": {
                    "type": "boolean",
                    "description": "Include line numbers in content output.",
                },
                "multiline": {
                    "type": "boolean",
                    "description": "Allow pattern matches across line boundaries.",
                },
                "head_limit": {
                    "type": "number",
                    "description": "Limit number of returned entries.",
                },
                "offset": {
                    "type": "number",
                    "description": "Skip first N entries before applying head_limit.",
                },
            },
            "required": ["pattern"],
        },
    },
}

READ_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "Read",
        "description": (
            "Read file contents for inspection. Use this instead of Bash/cat for file reading. "
            "Supports offsets and limits for large files."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path of the file to read.",
                },
                "offset": {
                    "type": "number",
                    "description": "Starting line offset (0-based).",
                },
                "limit": {
                    "type": "number",
                    "description": "Maximum number of lines to return.",
                },
                "pages": {
                    "type": "string",
                    "description": "Optional page range for PDFs (e.g. 1-5).",
                },
            },
            "required": ["file_path"],
        },
    },
}

EDIT_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "Edit",
        "description": (
            "Apply exact in-file string replacement. Use for precise edits when old/new "
            "text can be specified directly."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path of file to modify.",
                },
                "old_string": {
                    "type": "string",
                    "description": "Exact text to replace.",
                },
                "new_string": {
                    "type": "string",
                    "description": "Replacement text.",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences instead of just one.",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    },
}

WRITE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "Write",
        "description": (
            "Write or overwrite full file contents. Use for creating new files or "
            "full rewrites; prefer Edit for partial changes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path of file to write.",
                },
                "content": {
                    "type": "string",
                    "description": "Complete new file content.",
                },
            },
            "required": ["file_path", "content"],
        },
    },
}

NOTEBOOK_EDIT_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "NotebookEdit",
        "description": (
            "Edit Jupyter notebook cells by replacing, inserting, or deleting a cell."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "notebook_path": {
                    "type": "string",
                    "description": "Path to .ipynb file.",
                },
                "new_source": {
                    "type": "string",
                    "description": "Cell source text used for replace/insert.",
                },
                "cell_id": {
                    "type": "string",
                    "description": "Optional target cell id.",
                },
                "cell_type": {
                    "type": "string",
                    "description": "Cell type for insert mode.",
                    "enum": ["code", "markdown"],
                },
                "edit_mode": {
                    "type": "string",
                    "description": "Edit operation to perform.",
                    "enum": ["replace", "insert", "delete"],
                },
            },
            "required": ["notebook_path", "new_source"],
        },
    },
}


def exec_glob(args: dict[str, Any], config: dict, status_fn=None) -> str:
    pattern = args["pattern"]
    base = args.get("path") or os.getcwd()
    matches = pyglob.glob(str(Path(base) / pattern), recursive=True)
    matches.sort(key=os.path.getmtime, reverse=True)
    return to_json(matches)


def exec_grep(args: dict[str, Any], config: dict, status_fn=None) -> str:
    cmd = ["rg", args["pattern"]]
    path = args.get("path")
    if args.get("glob"):
        cmd.extend(["--glob", args["glob"]])
    if args.get("type"):
        cmd.extend(["--type", args["type"]])

    output_mode = args.get("output_mode", "files_with_matches")
    if output_mode == "files_with_matches":
        cmd.append("-l")
    elif output_mode == "count":
        cmd.append("-c")
    if args.get("-A") is not None:
        cmd.extend(["-A", str(int(args["-A"]))])
    if args.get("-B") is not None:
        cmd.extend(["-B", str(int(args["-B"]))])
    if args.get("context") is not None:
        cmd.extend(["-C", str(int(args["context"]))])
    if args.get("-i"):
        cmd.append("-i")
    if args.get("-n", True) and output_mode == "content":
        cmd.append("-n")
    if args.get("multiline"):
        cmd.extend(["-U", "--multiline-dotall"])
    if path:
        cmd.append(path)

    try:
        cp = subprocess.run(cmd, capture_output=True, text=True)
        out = cp.stdout.strip()
    except FileNotFoundError:
        pat = re.compile(args["pattern"])
        base = Path(path or os.getcwd())
        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
        lines: list[str] = []
        hl = int(args.get("head_limit", 0))
        for fp in base.rglob("*"):
            if any(part in skip_dirs for part in fp.parts):
                continue
            if not fp.is_file() or fp.stat().st_size > 5 * 1024 * 1024:
                continue
            try:
                for i, line in enumerate(fp.open(errors="ignore"), start=1):
                    if pat.search(line):
                        lines.append(f"{fp}:{i}:{line.rstrip()}")
                        if hl and len(lines) >= hl:
                            break
            except OSError:
                continue
            if hl and len(lines) >= hl:
                break
        out = "\n".join(lines)

    entries = out.splitlines() if out else []
    offset = int(args.get("offset", 0))
    head_limit = int(args.get("head_limit", 0))
    if offset > 0:
        entries = entries[offset:]
    if head_limit > 0:
        entries = entries[:head_limit]
    return "\n".join(entries)


def exec_read(args: dict[str, Any], config: dict, status_fn=None) -> str:
    file_path = resolve_path(args["file_path"])
    if not file_path.exists():
        return f"Error: file not found: {file_path}"

    if file_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}:
        return f"Binary file: {file_path.name} ({file_path.stat().st_size} bytes)"

    lines = file_path.read_text(errors="replace").splitlines()
    offset = max(0, int(args.get("offset", 0)))
    limit = args.get("limit")
    if limit is not None:
        lines = lines[offset: offset + int(limit)]
        start = offset + 1
    else:
        start = 1

    return "\n".join(f"{i}\t{line}" for i, line in enumerate(lines, start=start))


def exec_edit(args: dict[str, Any], config: dict, status_fn=None) -> str:
    file_path = resolve_path(args["file_path"])
    if not file_path.exists():
        return f"Error: file not found: {file_path}"

    old_string = args["old_string"]
    new_string = args["new_string"]
    replace_all = bool(args.get("replace_all", False))

    text = file_path.read_text()
    count = text.count(old_string)
    if count == 0:
        return "Error: old_string not found"
    if not replace_all and count > 1:
        return "Error: old_string is not unique; set replace_all=true"

    new_text = text.replace(old_string, new_string, -1 if replace_all else 1)
    file_path.write_text(new_text)
    replaced = count if replace_all else 1
    return f"OK: replaced {replaced} occurrence(s)"


def exec_write(args: dict[str, Any], config: dict, status_fn=None) -> str:
    file_path = resolve_path(args["file_path"])
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(args["content"])
    return f"OK: wrote {file_path}"


def exec_notebook_edit(args: dict[str, Any], config: dict, status_fn=None) -> str:
    nb_path = resolve_path(args["notebook_path"])
    if not nb_path.exists():
        return f"Error: notebook not found: {nb_path}"

    raw = json.loads(nb_path.read_text())
    cells = raw.get("cells", [])
    mode = args.get("edit_mode", "replace")
    source = args["new_source"].splitlines(keepends=True)

    idx = 0
    cell_id = args.get("cell_id")
    if cell_id:
        for i, c in enumerate(cells):
            if c.get("id") == cell_id:
                idx = i
                break

    if mode == "delete":
        if not cells:
            return "Error: notebook has no cells"
        cells.pop(idx)
    elif mode == "insert":
        cell_type = args.get("cell_type", "code")
        cell = {"cell_type": cell_type, "metadata": {}, "source": source}
        if cell_type == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
        cells.insert(idx, cell)
    else:
        if not cells:
            return "Error: notebook has no cells"
        cells[idx]["source"] = source

    raw["cells"] = cells
    nb_path.write_text(json.dumps(raw, indent=2))
    return f"OK: notebook updated ({mode})"
