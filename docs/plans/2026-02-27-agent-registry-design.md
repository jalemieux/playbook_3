# Agent Registry + Multi-Tool Experimental Agent

**Date:** 2026-02-27
**Status:** Approved

## Problem

The CLI hardcodes the orchestrator as the only agent. We need a way to select
different agents at startup for experimentation, and a new stateful multi-tool
agent to experiment with.

## Design

### Agent Interface

Every agent exports:

```python
def handler(text: str, reply_fn, config: dict, session_id: str = "default", status_fn=None) -> None
def clear_session(session_id: str) -> None
```

### Directory Structure

```
src/
├── agents/
│   ├── __init__.py       # Registry + get_agent()
│   ├── orchestrator.py   # Moved from src/orchestrator.py
│   ├── single.py         # Moved from src/agent.py
│   └── base.py           # NEW: stateful multi-tool agent
├── llm.py
├── bash.py
├── config.py
└── channels/
    └── cli.py            # Uses get_agent() based on --agent flag
```

### Registry

```python
# src/agents/__init__.py
AGENTS = {
    "orchestrator": ...,
    "single": ...,
    "base": ...,
}
DEFAULT_AGENT = "orchestrator"
```

### Agent Selection

- `main.py` adds `--agent` flag (choices from `AGENTS.keys()`)
- Flag value stored in config dict as `config["agent"]`
- `cli.py` imports `get_agent(name)` to get the handler
- Only CLI supports `--agent` for now; Telegram/Gmail stay on orchestrator

### New `base` Agent

- Stateful: maintains conversation history per session_id
- Multi-tool: tools defined in a `TOOLS` list
- Starts with `execute_bash` as the only tool
- Adding tools = appending to `TOOLS` list + adding execution logic
- Same agentic loop pattern as existing agents

### What Changes

| File | Change |
|------|--------|
| `src/agent.py` | Moved to `src/agents/single.py`, add `session_id` param + `clear_session()` |
| `src/orchestrator.py` | Moved to `src/agents/orchestrator.py` |
| `src/agents/__init__.py` | New: registry |
| `src/agents/base.py` | New: stateful multi-tool agent |
| `src/channels/cli.py` | Import from registry, display active agent |
| `main.py` | Add `--agent` flag |
| Tests | Update imports |

### What Stays the Same

- `src/llm.py`, `src/bash.py`, `src/config.py` - untouched
- `config.yaml` - no changes
- Telegram/Gmail channels - still use orchestrator
- Agent loop logic - same pattern, just restructured
