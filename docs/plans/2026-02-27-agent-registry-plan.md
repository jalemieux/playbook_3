# Agent Registry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable selecting different agents via `--agent` CLI flag and add a new stateful multi-tool experimental agent.

**Architecture:** Move `agent.py` and `orchestrator.py` into `src/agents/` package with a registry dict. CLI resolves agent by name. New `base` agent follows orchestrator's stateful pattern but with a configurable tools list.

**Tech Stack:** Python, pytest, existing LiteLLM/bash infrastructure.

---

### Task 1: Create agents package and move single agent

**Files:**
- Create: `src/agents/__init__.py`
- Create: `src/agents/single.py` (from `src/agent.py`)
- Modify: `src/agent.py` (keep as re-export shim)

**Step 1: Create `src/agents/` directory**

Run: `mkdir -p src/agents`

**Step 2: Copy agent.py to agents/single.py**

Copy `src/agent.py` to `src/agents/single.py`. Add `session_id` param to `handler` and add `clear_session` (no-op for stateless agent):

```python
import json

from src.llm import chat_completion
from src.bash import execute_bash


SYSTEM_PROMPT = """You are a personal assistant. You have one tool: execute_bash. Use it to accomplish tasks on the user's computer. You are running on Ubuntu.

When you receive a message:
- If it requires action, use bash to accomplish it.
- If it's conversational, just reply.
- If you're unsure what the user wants, ask.

Keep replies short and direct."""


def _truncate(text: str, max_len: int = 200) -> str:
    """Truncate text with ellipsis indicator."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n  … truncated ({len(text)} chars total)"


def run(text: str, config: dict, status_fn=None) -> str:
    """Execute a task through the agent loop. Returns the final response text."""
    model = config["agent_model"]
    timeout = config.get("bash_timeout", 30)
    max_iter = config.get("max_iterations", 10)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]

    for i in range(max_iter):
        if status_fn:
            status_fn("thinking", "")
        result = chat_completion(messages, model)
        if status_fn:
            status_fn("done_thinking", "")

        if result["tool_calls"] is None:
            return result["content"] or "[no response]"

        messages.append({"role": "assistant", "tool_calls": result["tool_calls"], "content": result.get("content")})

        for tool_call in result["tool_calls"]:
            args = json.loads(tool_call["function"]["arguments"])
            command = args["command"]

            if status_fn:
                status_fn("tool_call", f'Bash("{command}")')

            try:
                output = execute_bash(command, timeout=timeout)
            except TimeoutError as e:
                output = f"Error: {e}"

            if status_fn:
                status_fn("tool_result", _truncate(output.strip()))

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": output,
            })

    return "Stopped: reached maximum iteration limit."


def clear_session(session_id: str) -> None:
    """No-op: single agent is stateless."""
    pass


def handler(text: str, reply_fn, config: dict, session_id: str = "default", status_fn=None) -> None:
    """Process a user message through the agent loop."""
    reply_fn(run(text, config, status_fn))
```

**Step 3: Turn `src/agent.py` into a re-export shim**

Replace contents of `src/agent.py` with:

```python
"""Backward-compatible re-export. Real implementation in src/agents/single.py."""
from src.agents.single import handler, run, clear_session
```

This keeps `from src.agent import run` working for `orchestrator.py` and existing tests.

**Step 4: Run existing agent tests**

Run: `python -m pytest tests/test_agent.py -v`
Expected: All 6 tests PASS (imports still work via shim)

**Step 5: Commit**

```bash
git add src/agents/__init__.py src/agents/single.py src/agent.py
git commit -m "refactor: move agent to src/agents/single.py with re-export shim"
```

---

### Task 2: Move orchestrator into agents package

**Files:**
- Create: `src/agents/orchestrator.py` (from `src/orchestrator.py`)
- Modify: `src/orchestrator.py` (keep as re-export shim)

**Step 1: Copy orchestrator.py to agents/orchestrator.py**

Copy `src/orchestrator.py` to `src/agents/orchestrator.py`. Change the agent_run import to use the new location:

```python
import json

from src.llm import chat_completion
from src.agents.single import run as agent_run

SYSTEM_PROMPT = """You are a personal assistant. You have one tool: execute_task. Use it to accomplish tasks by describing what needs to be done. Evaluate results and retry with clearer instructions if needed. Keep replies short and direct."""

EXECUTE_TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_task",
        "description": "Execute a task on the user's computer. Describe the intent clearly.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "Clear description of what needs to be accomplished.",
                }
            },
            "required": ["intent"],
        },
    },
}

# In-memory conversation store: session_id -> list of messages
conversations: dict[str, list[dict]] = {}


def clear_session(session_id: str) -> None:
    """Clear conversation history for a session."""
    conversations.pop(session_id, None)


def handler(text: str, reply_fn, config: dict, session_id: str = "default", status_fn=None) -> None:
    """Process a user message through the orchestrator."""
    model = config.get("orchestrator_model", config["agent_model"])
    max_iter = config.get("orchestrator_max_iterations", 5)

    if session_id not in conversations:
        conversations[session_id] = []
    history = conversations[session_id]

    history.append({"role": "user", "content": text})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    for i in range(max_iter):
        if status_fn:
            status_fn("thinking", "")
        result = chat_completion(messages, model, tools=[EXECUTE_TASK_SCHEMA])
        if status_fn:
            status_fn("done_thinking", "")

        if result["tool_calls"] is None:
            response = result["content"] or "[no response]"
            history.append({"role": "assistant", "content": response})
            reply_fn(response)
            return

        assistant_msg = {"role": "assistant", "tool_calls": result["tool_calls"], "content": result.get("content")}
        history.append(assistant_msg)
        messages.append(assistant_msg)

        for tool_call in result["tool_calls"]:
            args = json.loads(tool_call["function"]["arguments"])
            intent = args["intent"]

            if status_fn:
                status_fn("sub_agent_call", intent)

            task_result = agent_run(intent, config, status_fn)

            if status_fn:
                status_fn("sub_agent_result", task_result[:200])

            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": task_result,
            }
            history.append(tool_msg)
            messages.append(tool_msg)

    fallback = "Stopped: reached orchestrator iteration limit."
    history.append({"role": "assistant", "content": fallback})
    reply_fn(fallback)
```

**Step 2: Turn `src/orchestrator.py` into a re-export shim**

```python
"""Backward-compatible re-export. Real implementation in src/agents/orchestrator.py."""
from src.agents.orchestrator import handler, clear_session, conversations, EXECUTE_TASK_SCHEMA
```

**Step 3: Run existing orchestrator tests**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: All 7 tests PASS

**Step 4: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/agents/orchestrator.py src/orchestrator.py
git commit -m "refactor: move orchestrator to src/agents/orchestrator.py with re-export shim"
```

---

### Task 3: Create the agent registry

**Files:**
- Modify: `src/agents/__init__.py`
- Create: `tests/test_registry.py`

**Step 1: Write the failing test**

Create `tests/test_registry.py`:

```python
from src.agents import AGENTS, DEFAULT_AGENT, get_agent


def test_registry_has_expected_agents():
    assert "orchestrator" in AGENTS
    assert "single" in AGENTS
    assert "base" in AGENTS


def test_default_agent():
    assert DEFAULT_AGENT == "orchestrator"


def test_get_agent_returns_handler():
    handler = get_agent("single")
    assert callable(handler)


def test_get_agent_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_agent("nonexistent")


def test_all_agents_have_clear_session():
    from src.agents import get_clear_session
    for name in AGENTS:
        assert callable(get_clear_session(name))
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_registry.py -v`
Expected: FAIL (imports don't exist yet)

**Step 3: Write the registry**

`src/agents/__init__.py`:

```python
from src.agents.orchestrator import handler as _orchestrator_handler, clear_session as _orchestrator_clear
from src.agents.single import handler as _single_handler, clear_session as _single_clear
from src.agents.base import handler as _base_handler, clear_session as _base_clear

AGENTS = {
    "orchestrator": _orchestrator_handler,
    "single": _single_handler,
    "base": _base_handler,
}

_CLEAR_SESSIONS = {
    "orchestrator": _orchestrator_clear,
    "single": _single_clear,
    "base": _base_clear,
}

DEFAULT_AGENT = "orchestrator"


def get_agent(name: str):
    """Get an agent handler by name. Raises KeyError if not found."""
    return AGENTS[name]


def get_clear_session(name: str):
    """Get a clear_session function by agent name. Raises KeyError if not found."""
    return _CLEAR_SESSIONS[name]
```

Note: This will fail until Task 4 creates `base.py`. We'll create a stub first.

**Step 4: Create base.py stub**

Create `src/agents/base.py` with minimal stub:

```python
"""Stateful multi-tool experimental agent. Tools TBD."""

conversations: dict[str, list[dict]] = {}


def clear_session(session_id: str) -> None:
    """Clear conversation history for a session."""
    conversations.pop(session_id, None)


def handler(text: str, reply_fn, config: dict, session_id: str = "default", status_fn=None) -> None:
    """Placeholder — replaced in Task 4."""
    reply_fn("[base agent not yet implemented]")
```

**Step 5: Run tests**

Run: `python -m pytest tests/test_registry.py -v`
Expected: All 5 tests PASS

**Step 6: Commit**

```bash
git add src/agents/__init__.py src/agents/base.py tests/test_registry.py
git commit -m "feat: add agent registry with get_agent/get_clear_session"
```

---

### Task 4: Implement base agent

**Files:**
- Modify: `src/agents/base.py`
- Create: `tests/test_base_agent.py`

**Step 1: Write the failing tests**

Create `tests/test_base_agent.py`:

```python
import json
from unittest.mock import patch

from src.agents.base import handler, clear_session, conversations, TOOLS

TEST_CONFIG = {
    "agent_model": "anthropic/claude-sonnet-4",
    "bash_timeout": 5,
    "max_iterations": 10,
}


def setup_function():
    conversations.clear()


def test_text_response():
    """Base agent replies with text when no tool call needed."""
    replies = []
    with patch("src.agents.base.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hello!", "tool_calls": None}
        handler("Hi", replies.append, TEST_CONFIG)
    assert replies == ["Hello!"]


def test_tool_then_text():
    """Base agent calls bash tool, gets output, then replies."""
    replies = []
    with patch("src.agents.base.chat_completion") as mock_llm, \
         patch("src.agents.base.execute_bash", return_value="file1.txt\n") as mock_bash:
        mock_llm.side_effect = [
            {
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "execute_bash", "arguments": '{"command": "ls"}'},
                }],
            },
            {"content": "Found file1.txt.", "tool_calls": None},
        ]
        handler("List files", replies.append, TEST_CONFIG)
    mock_bash.assert_called_once_with("ls", timeout=5)
    assert replies == ["Found file1.txt."]


def test_maintains_history():
    """Base agent maintains conversation history across calls."""
    with patch("src.agents.base.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi!", "tool_calls": None}
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="s1")
        handler("Again", lambda x: None, TEST_CONFIG, session_id="s1")
    assert len(conversations["s1"]) == 4  # user, assistant, user, assistant


def test_separate_sessions():
    """Different sessions have independent history."""
    with patch("src.agents.base.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi!", "tool_calls": None}
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="a")
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="b")
    assert len(conversations["a"]) == 2
    assert len(conversations["b"]) == 2


def test_clear_session():
    """clear_session removes history."""
    with patch("src.agents.base.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi!", "tool_calls": None}
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="x")
    assert "x" in conversations
    clear_session("x")
    assert "x" not in conversations


def test_max_iterations():
    """Base agent stops after max_iterations."""
    config = {**TEST_CONFIG, "max_iterations": 2}
    replies = []
    tool_response = {
        "content": None,
        "tool_calls": [{
            "id": "call_n",
            "type": "function",
            "function": {"name": "execute_bash", "arguments": '{"command": "echo loop"}'},
        }],
    }
    with patch("src.agents.base.chat_completion", return_value=tool_response), \
         patch("src.agents.base.execute_bash", return_value="loop\n"):
        handler("loop", replies.append, config)
    assert len(replies) == 1
    assert "limit" in replies[0].lower()


def test_tools_list_contains_bash():
    """TOOLS list includes bash schema."""
    names = [t["function"]["name"] for t in TOOLS]
    assert "execute_bash" in names


def test_passes_all_tools_to_llm():
    """All tools in TOOLS are passed to chat_completion."""
    with patch("src.agents.base.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Ok", "tool_calls": None}
        handler("Hi", lambda x: None, TEST_CONFIG)
    call_kwargs = mock_llm.call_args
    assert call_kwargs[1]["tools"] == TOOLS or call_kwargs[0][2] == TOOLS
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_base_agent.py -v`
Expected: FAIL (base.py is still a stub)

**Step 3: Implement base agent**

Replace `src/agents/base.py`:

```python
"""Stateful multi-tool experimental agent."""
import json

from src.llm import chat_completion, TOOL_SCHEMA as BASH_SCHEMA
from src.bash import execute_bash

SYSTEM_PROMPT = """You are a personal assistant. Use your tools to accomplish tasks on the user's computer.

When you receive a message:
- If it requires action, use your tools to accomplish it.
- If it's conversational, just reply.
- If you're unsure what the user wants, ask.

Keep replies short and direct."""

# Tool registry — add new tool schemas here
TOOLS = [BASH_SCHEMA]

# Tool executors — map tool name to (executor_fn, arg_extractor_fn)
def _exec_bash(args, config, status_fn):
    command = args["command"]
    timeout = config.get("bash_timeout", 30)
    if status_fn:
        status_fn("tool_call", f'Bash("{command}")')
    try:
        output = execute_bash(command, timeout=timeout)
    except TimeoutError as e:
        output = f"Error: {e}"
    if status_fn:
        status_fn("tool_result", _truncate(output.strip()))
    return output

EXECUTORS = {
    "execute_bash": _exec_bash,
}

# In-memory conversation store
conversations: dict[str, list[dict]] = {}


def _truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n  … truncated ({len(text)} chars total)"


def clear_session(session_id: str) -> None:
    """Clear conversation history for a session."""
    conversations.pop(session_id, None)


def handler(text: str, reply_fn, config: dict, session_id: str = "default", status_fn=None) -> None:
    """Process a user message through the base agent."""
    model = config["agent_model"]
    max_iter = config.get("max_iterations", 10)

    if session_id not in conversations:
        conversations[session_id] = []
    history = conversations[session_id]

    history.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    for i in range(max_iter):
        if status_fn:
            status_fn("thinking", "")
        result = chat_completion(messages, model, tools=TOOLS)
        if status_fn:
            status_fn("done_thinking", "")

        if result["tool_calls"] is None:
            response = result["content"] or "[no response]"
            history.append({"role": "assistant", "content": response})
            reply_fn(response)
            return

        assistant_msg = {"role": "assistant", "tool_calls": result["tool_calls"], "content": result.get("content")}
        history.append(assistant_msg)
        messages.append(assistant_msg)

        for tool_call in result["tool_calls"]:
            name = tool_call["function"]["name"]
            args = json.loads(tool_call["function"]["arguments"])

            executor = EXECUTORS.get(name)
            if executor:
                output = executor(args, config, status_fn)
            else:
                output = f"Error: unknown tool '{name}'"

            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": output,
            }
            history.append(tool_msg)
            messages.append(tool_msg)

    fallback = "Stopped: reached maximum iteration limit."
    history.append({"role": "assistant", "content": fallback})
    reply_fn(fallback)
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_base_agent.py -v`
Expected: All 9 tests PASS

**Step 5: Commit**

```bash
git add src/agents/base.py tests/test_base_agent.py
git commit -m "feat: implement stateful multi-tool base agent"
```

---

### Task 5: Wire CLI to use agent registry

**Files:**
- Modify: `main.py`
- Modify: `src/channels/cli.py`

**Step 1: Update main.py to accept --agent flag**

```python
import argparse
import logging
import os
from pathlib import Path

from src.config import load_config
from src.agents import AGENTS, DEFAULT_AGENT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description="Minimal agent")
    parser.add_argument("--channel", choices=["cli", "telegram", "gmail", "all"],
                        default=os.environ.get("CHANNEL", "all"))
    parser.add_argument("--agent", choices=list(AGENTS.keys()),
                        default=os.environ.get("AGENT", DEFAULT_AGENT))
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    config["agent"] = args.agent

    if args.channel == "cli":
        from src.channels.cli import run_cli
        run_cli(config)
    elif args.channel == "telegram":
        from src.channels.telegram import start_telegram
        start_telegram(config)
    elif args.channel == "gmail":
        from src.channels.gmail import start_gmail
        start_gmail(config)
    else:
        import threading
        from src.channels.telegram import start_telegram
        from src.channels.gmail import start_gmail
        gmail_thread = threading.Thread(target=start_gmail, args=(config,), daemon=True)
        gmail_thread.start()
        start_telegram(config)


if __name__ == "__main__":
    main()
```

**Step 2: Update cli.py to use registry**

Replace the import and routing in `src/channels/cli.py`:

Change `from src.orchestrator import handler, clear_session` to:

```python
from src.agents import get_agent, get_clear_session
```

Update `run_cli` to resolve the agent from config:

```python
def run_cli(config: dict) -> None:
    """Interactive CLI for testing the agent."""
    global _verbose

    agent_name = config.get("agent", "orchestrator")
    agent_handler = get_agent(agent_name)
    agent_clear = get_clear_session(agent_name)

    mode = f"{DIM}collapsed{RESET}" if not _verbose else f"{DIM}expanded{RESET}"
    print(f"{BOLD}Agent CLI{RESET}  {DIM}ctrl+e: toggle tool output | /clear: reset | 'quit' to exit{RESET}")
    print(f"  {DIM}agent:        {RESET}{agent_name}")
    print(f"  {DIM}model:        {RESET}{config.get('agent_model', 'unknown')}")
    print(f"  {DIM}tool output:  {RESET}{mode}")
    print()

    while True:
        try:
            text = input(f"{GREEN}> {RESET}")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        stripped = text.strip().lower()
        if stripped in ("quit", "exit"):
            break

        if stripped == "\x05" or stripped == "/verbose" or stripped == "/v":
            _verbose = not _verbose
            mode_label = "expanded" if _verbose else "collapsed"
            print(f"  {DIM}tool output: {mode_label}{RESET}")
            print()
            continue

        if stripped in ("/clear", "/reset"):
            agent_clear("cli")
            print(f"  {DIM}conversation cleared{RESET}")
            print()
            continue

        agent_handler(text, _reply, config, session_id="cli", status_fn=_make_status_fn())
```

**Step 3: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 4: Manual smoke test**

Run: `python main.py --channel cli --agent single`
Expected: CLI starts, shows `agent: single`, responds to messages using single agent loop (no orchestrator)

Run: `python main.py --channel cli --agent base`
Expected: CLI starts, shows `agent: base`, responds using base agent

**Step 5: Commit**

```bash
git add main.py src/channels/cli.py
git commit -m "feat: wire --agent flag to CLI via agent registry"
```

---

### Task 6: Clean up and delete shims

**Files:**
- Modify: `src/agent_one.py` (update import)
- Delete or update any stale references

**Step 1: Update agent_one.py**

Change `from src.agent import run as agent_run` to `from src.agents.single import run as agent_run`.

**Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add src/agent_one.py
git commit -m "refactor: update agent_one.py import to use agents package"
```

---

### Task 7: Update documentation

**Files:**
- Modify: `docs/architecture.md`
- Modify: `README.md`

**Step 1: Update architecture.md**

Add the agents registry to the component table and update the architecture diagram to show the registry layer.

**Step 2: Update README.md**

Add `--agent` flag to usage examples:

```
python main.py --channel cli --agent single       # Direct agent loop
python main.py --channel cli --agent base          # Multi-tool experimental agent
python main.py --channel cli --agent orchestrator  # Two-tier (default)
```

**Step 3: Commit**

```bash
git add docs/architecture.md README.md
git commit -m "docs: add agent registry and --agent flag documentation"
```
