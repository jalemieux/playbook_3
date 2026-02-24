# Orchestrator Layer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a conversation-aware orchestrator layer that manages user dialogue and delegates task execution to the existing stateless agent loop.

**Architecture:** The orchestrator sits between channels and the agent loop. It maintains per-session conversation history, calls the agent loop via an `execute_task` tool, and can rephrase/retry if results are unsatisfactory. Channels are unaware of the change — same `handler` interface.

**Tech Stack:** Python, LiteLLM, pytest

---

### Task 1: Make `chat_completion` accept custom tools

**Files:**
- Modify: `src/llm.py:28-38`
- Modify: `tests/test_llm.py`

**Step 1: Write failing test for custom tools parameter**

Add to `tests/test_llm.py`:

```python
def test_chat_completion_custom_tools():
    """chat_completion accepts a custom tools list instead of default TOOL_SCHEMA."""
    custom_tool = {
        "type": "function",
        "function": {
            "name": "execute_task",
            "description": "Execute a task.",
            "parameters": {
                "type": "object",
                "properties": {"intent": {"type": "string"}},
                "required": ["intent"],
            },
        },
    }
    mock_resp = _mock_litellm_response(content="ok")
    with patch("src.llm.litellm.completion", return_value=mock_resp) as mock_call:
        chat_completion(
            messages=[{"role": "user", "content": "test"}],
            model="anthropic/claude-sonnet-4",
            tools=[custom_tool],
        )
    call_kwargs = mock_call.call_args
    assert call_kwargs.kwargs["tools"] == [custom_tool]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm.py::test_chat_completion_custom_tools -v`
Expected: FAIL — `chat_completion() got an unexpected keyword argument 'tools'`

**Step 3: Add optional `tools` parameter to `chat_completion`**

In `src/llm.py`, change the function signature and body:

```python
def chat_completion(messages: list[dict], model: str, tools: list[dict] | None = None) -> dict:
    """Call LLM via LiteLLM with tool-use support.

    Returns dict with 'content' (str|None) and 'tool_calls' (list[dict]|None).
    """
    if tools is None:
        tools = [TOOL_SCHEMA]

    response = litellm.completion(
        model=model,
        messages=messages,
        tools=tools,
        timeout=60,
    )
```

The rest of the function stays the same.

**Step 4: Run all tests to verify nothing breaks**

Run: `pytest tests/test_llm.py -v`
Expected: All PASS (existing tests still work because default is `[TOOL_SCHEMA]`)

**Step 5: Commit**

```bash
git add src/llm.py tests/test_llm.py
git commit -m "feat: allow custom tools in chat_completion"
```

---

### Task 2: Refactor agent `handler` to return string

**Files:**
- Modify: `src/agent.py:23-70`
- Modify: `tests/test_agent.py`

**Step 1: Write failing test for new `run()` function**

Add to `tests/test_agent.py`:

```python
from src.agent import run

def test_run_returns_text_response():
    """run() returns the LLM response as a string."""
    with patch("src.agent.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hello!", "tool_calls": None}
        result = run("Hi there", TEST_CONFIG)
    assert result == "Hello!"


def test_run_tool_then_text():
    """run() executes tools and returns final text."""
    with patch("src.agent.chat_completion") as mock_llm, \
         patch("src.agent.execute_bash", return_value="file1.txt\n"):
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
        result = run("List files", TEST_CONFIG)
    assert result == "Found file1.txt."
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_agent.py::test_run_returns_text_response tests/test_agent.py::test_run_tool_then_text -v`
Expected: FAIL — `cannot import name 'run' from 'src.agent'`

**Step 3: Add `run()` function and make `handler` delegate to it**

Replace the `handler` function in `src/agent.py` with:

```python
def run(text: str, config: dict, status_fn=None) -> str:
    """Execute a task through the agent loop. Returns the final response text."""
    model = config["model"]
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


def handler(text: str, reply_fn, config: dict, status_fn=None) -> None:
    """Process a user message through the agent loop."""
    reply_fn(run(text, config, status_fn))
```

**Step 4: Run all agent tests**

Run: `pytest tests/test_agent.py -v`
Expected: All PASS (old tests still work via `handler`, new tests work via `run`)

**Step 5: Commit**

```bash
git add src/agent.py tests/test_agent.py
git commit -m "refactor: extract agent run() that returns string"
```

---

### Task 3: Create the orchestrator

**Files:**
- Create: `src/orchestrator.py`
- Create: `tests/test_orchestrator.py`

**Step 1: Write failing tests for orchestrator**

Create `tests/test_orchestrator.py`:

```python
import json
from unittest.mock import patch, MagicMock

from src.orchestrator import handler, conversations, EXECUTE_TASK_SCHEMA

TEST_CONFIG = {
    "model": "anthropic/claude-sonnet-4",
    "orchestrator_model": "anthropic/claude-sonnet-4",
    "orchestrator_max_iterations": 5,
    "bash_timeout": 5,
    "max_iterations": 10,
}


def setup_function():
    """Clear conversation history between tests."""
    conversations.clear()


def test_orchestrator_text_response():
    """Orchestrator replies with text when no tool call needed."""
    replies = []
    with patch("src.orchestrator.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi there!", "tool_calls": None}
        handler("Hello", replies.append, TEST_CONFIG)
    assert replies == ["Hi there!"]


def test_orchestrator_calls_agent():
    """Orchestrator calls execute_task, gets agent result, replies."""
    replies = []
    with patch("src.orchestrator.chat_completion") as mock_llm, \
         patch("src.orchestrator.agent_run", return_value="file1.txt") as mock_agent:
        mock_llm.side_effect = [
            {
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "execute_task",
                        "arguments": json.dumps({"intent": "list files"}),
                    },
                }],
            },
            {"content": "You have file1.txt.", "tool_calls": None},
        ]
        handler("What files do I have?", replies.append, TEST_CONFIG)
    mock_agent.assert_called_once_with("list files", TEST_CONFIG, None)
    assert replies == ["You have file1.txt."]


def test_orchestrator_maintains_history():
    """Orchestrator maintains conversation history across calls."""
    with patch("src.orchestrator.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi!", "tool_calls": None}
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="test1")
        handler("How are you?", lambda x: None, TEST_CONFIG, session_id="test1")
    assert len(conversations["test1"]) == 4  # user, assistant, user, assistant


def test_orchestrator_separate_sessions():
    """Different session IDs maintain separate histories."""
    with patch("src.orchestrator.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi!", "tool_calls": None}
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="a")
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="b")
    assert len(conversations["a"]) == 2
    assert len(conversations["b"]) == 2


def test_orchestrator_max_iterations():
    """Orchestrator stops after max_iterations."""
    config = {**TEST_CONFIG, "orchestrator_max_iterations": 2}
    replies = []
    tool_response = {
        "content": None,
        "tool_calls": [{
            "id": "call_n",
            "type": "function",
            "function": {
                "name": "execute_task",
                "arguments": json.dumps({"intent": "do something"}),
            },
        }],
    }
    with patch("src.orchestrator.chat_completion", return_value=tool_response), \
         patch("src.orchestrator.agent_run", return_value="result"):
        handler("loop forever", replies.append, config)
    assert len(replies) == 1
    assert "limit" in replies[0].lower()


def test_orchestrator_clear_session():
    """clear_session removes history for a session."""
    from src.orchestrator import clear_session
    with patch("src.orchestrator.chat_completion") as mock_llm:
        mock_llm.return_value = {"content": "Hi!", "tool_calls": None}
        handler("Hello", lambda x: None, TEST_CONFIG, session_id="test")
    assert "test" in conversations
    clear_session("test")
    assert "test" not in conversations


def test_execute_task_schema_structure():
    """Tool schema has correct structure."""
    assert EXECUTE_TASK_SCHEMA["function"]["name"] == "execute_task"
    params = EXECUTE_TASK_SCHEMA["function"]["parameters"]
    assert "intent" in params["properties"]
    assert params["required"] == ["intent"]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_orchestrator.py -v`
Expected: FAIL — `No module named 'src.orchestrator'`

**Step 3: Implement the orchestrator**

Create `src/orchestrator.py`:

```python
import json

from src.llm import chat_completion
from src.agent import run as agent_run

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
    model = config.get("orchestrator_model", config["model"])
    max_iter = config.get("orchestrator_max_iterations", 5)

    # Get or create conversation history
    if session_id not in conversations:
        conversations[session_id] = []
    history = conversations[session_id]

    # Add user message to history
    history.append({"role": "user", "content": text})

    # Build messages: system + conversation history
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

        # Process tool calls
        assistant_msg = {"role": "assistant", "tool_calls": result["tool_calls"], "content": result.get("content")}
        history.append(assistant_msg)
        messages.append(assistant_msg)

        for tool_call in result["tool_calls"]:
            args = json.loads(tool_call["function"]["arguments"])
            intent = args["intent"]

            if status_fn:
                status_fn("tool_call", f'Task("{intent}")')

            task_result = agent_run(intent, config, status_fn)

            if status_fn:
                status_fn("tool_result", task_result[:200])

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

**Step 4: Run all orchestrator tests**

Run: `pytest tests/test_orchestrator.py -v`
Expected: All PASS

**Step 5: Run full test suite**

Run: `pytest -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add orchestrator with conversation history and execute_task tool"
```

---

### Task 4: Wire channels to orchestrator

**Files:**
- Modify: `src/channels/cli.py:1-7,104-123`
- Modify: `src/channels/telegram.py:5,28`
- Modify: `src/channels/gmail.py:12,92-95`

**Step 1: Update CLI channel**

In `src/channels/cli.py`, change import and add `/clear` support:

Change line 7:
```python
from src.orchestrator import handler, clear_session
```

Add `/clear` handling after the `/verbose` block (after line 121), and pass `session_id` to handler:

```python
        if stripped in ("/clear", "/reset"):
            clear_session("cli")
            print(f"  {DIM}conversation cleared{RESET}")
            print()
            continue

        handler(text, _reply, config, session_id="cli", status_fn=_make_status_fn())
```

Also update the help line (line 99) to mention `/clear`:
```python
    print(f"{BOLD}Agent CLI{RESET}  {DIM}ctrl+e: toggle tool output | /clear: reset | 'quit' to exit{RESET}")
```

**Step 2: Update Telegram channel**

In `src/channels/telegram.py`, change line 5:
```python
from src.orchestrator import handler
```

Change line 28 to pass `chat_id` as `session_id`:
```python
    await loop.run_in_executor(None, handler, text, reply_fn, config, str(update.message.chat_id))
```

**Step 3: Update Gmail channel**

In `src/channels/gmail.py`, change line 12:
```python
from src.orchestrator import handler
```

Change line 95 to pass `msg_id` as `session_id`:
```python
                handler(text, reply_fn, config, session_id=msg_id)
```

**Step 4: Run full test suite**

Run: `pytest -v`
Expected: All PASS (channel files aren't directly tested, but nothing should break)

**Step 5: Commit**

```bash
git add src/channels/cli.py src/channels/telegram.py src/channels/gmail.py
git commit -m "feat: wire channels to orchestrator"
```

---

### Task 5: Update config

**Files:**
- Modify: `config.yaml`

**Step 1: Add orchestrator config keys**

Add after line 1 in `config.yaml`:

```yaml
orchestrator_model: anthropic/claude-sonnet-4-6
orchestrator_max_iterations: 5
```

**Step 2: Commit**

```bash
git add config.yaml
git commit -m "chore: add orchestrator config keys"
```

---

### Task 6: Update documentation

**Files:**
- Modify: `docs/architecture.md`
- Modify: `README.md`

**Step 1: Update architecture.md**

Add the orchestrator to the component table, update the data flow diagram to show the orchestrator layer, add a changelog entry.

**Step 2: Update README.md**

Add orchestrator to features list, update the architecture description, note the conversation capability and `/clear` command.

**Step 3: Commit**

```bash
git add docs/architecture.md README.md
git commit -m "docs: update architecture and README for orchestrator layer"
```

---

### Task 7: Manual smoke test

**Step 1: Run CLI and test conversation**

Run: `python main.py --channel cli`

Test sequence:
1. Send "Hello" — should get conversational reply (no tool call)
2. Send "What files are in the current directory?" — should call execute_task → agent runs ls → reply
3. Send "How many were there?" — should answer from conversation context (proves history works)
4. Send "/clear" — should see "conversation cleared"
5. Send "What were we talking about?" — should not know (proves clear works)
