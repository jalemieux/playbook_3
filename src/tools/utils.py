"""Shared utilities for tool executors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True)


def truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n  … truncated ({len(text)} chars total)"


def resolve_path(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    return p
