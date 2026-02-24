# LiteLLM Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the hand-rolled OpenRouter httpx client with LiteLLM to support native Anthropic, OpenAI, Minimax, and OpenRouter providers.

**Architecture:** `src/llm.py` wraps `litellm.completion()` with the same `chat_completion()` interface. Model prefix (e.g. `anthropic/`, `openai/`) determines provider routing. API keys auto-discovered from env vars.

**Tech Stack:** Python 3.14, LiteLLM, pytest

---

### Task 1: Update requirements.txt

**Files:**
- Modify: `requirements.txt`

**Step 1: Replace httpx with litellm**

```
litellm>=1.0
pyyaml>=6
python-telegram-bot>=21
google-api-python-client>=2.0
google-auth-oauthlib>=1.0
pytest>=8
pytest-asyncio>=0.23
```

Note: `litellm` depends on `httpx` internally, so existing httpx usage still works transitively if needed.

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: replace httpx with litellm in requirements"
```

---

### Task 2: Create src/llm.py with tests (TDD)

**Files:**
- Create: `src/llm.py`
- Create: `tests/test_llm.py`

**Step 1: Write the failing tests**

`tests/test_llm.py`:
```python
from unittest.mock import patch, MagicMock

from src.llm import chat_completion, TOOL_SCHEMA


def _mock_litellm_response(content=None, tool_calls=None):
    """Build a fake litellm response object."""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def test_chat_completion_text_response():
    mock_resp = _mock_litellm_response(content="Hello!")
    with patch("src.llm.litellm.completion", return_value=mock_resp) as mock_call:
        result = chat_completion(
            messages=[{"role": "user", "content": "Hi"}],
            model="anthropic/claude-sonnet-4",
        )
    assert result["content"] == "Hello!"
    assert result["tool_calls"] is None
    mock_call.assert_called_once()


def test_chat_completion_tool_call():
    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.type = "function"
    tool_call.function.name = "execute_bash"
    tool_call.function.arguments = '{"command": "ls"}'

    mock_resp = _mock_litellm_response(tool_calls=[tool_call])
    with patch("src.llm.litellm.completion", return_value=mock_resp):
        result = chat_completion(
            messages=[{"role": "user", "content": "List files"}],
            model="openai/gpt-4o",
        )
    assert result["tool_calls"] is not None
    assert result["tool_calls"][0]["function"]["name"] == "execute_bash"


def test_chat_completion_passes_model_and_tools():
    mock_resp = _mock_litellm_response(content="ok")
    with patch("src.llm.litellm.completion", return_value=mock_resp) as mock_call:
        chat_completion(
            messages=[{"role": "user", "content": "test"}],
            model="minimax/minimax-m1",
        )
    call_kwargs = mock_call.call_args
    assert call_kwargs.kwargs["model"] == "minimax/minimax-m1"
    assert len(call_kwargs.kwargs["tools"]) == 1
    assert call_kwargs.kwargs["tools"][0]["function"]["name"] == "execute_bash"


def test_tool_schema_has_execute_bash():
    assert TOOL_SCHEMA["function"]["name"] == "execute_bash"
    params = TOOL_SCHEMA["function"]["parameters"]
    assert "command" in params["properties"]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.llm'`

**Step 3: Write the implementation**

`src/llm.py`:
```python
import litellm

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_bash",
        "description": "Execute a bash command on the user's computer and return the output.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute.",
                }
            },
            "required": ["command"],
        },
    },
}


def chat_completion(messages: list[dict], model: str) -> dict:
    """Call LLM via LiteLLM with execute_bash tool.

    Returns dict with 'content' (str|None) and 'tool_calls' (list[dict]|None).
    """
    response = litellm.completion(
        model=model,
        messages=messages,
        tools=[TOOL_SCHEMA],
        timeout=60,
    )
    message = response.choices[0].message

    # Normalize tool_calls from litellm objects to plain dicts
    tool_calls = None
    if message.tool_calls:
        tool_calls = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ]

    return {
        "content": message.content,
        "tool_calls": tool_calls,
    }
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm.py -v`
Expected: All 4 PASS

**Step 5: Commit**

```bash
git add src/llm.py tests/test_llm.py
git commit -m "feat: add LiteLLM-based LLM client with tests"
```

---

### Task 3: Update agent.py to use src/llm.py

**Files:**
- Modify: `src/agent.py:1-4` (imports)
- Modify: `src/agent.py:23-39` (handler params and chat_completion call)
- Modify: `tests/test_agent.py` (remove api_key from TEST_CONFIG)

**Step 1: Update agent.py imports and handler**

In `src/agent.py`, change:
- Line 3: `from src.openrouter import chat_completion` → `from src.llm import chat_completion`
- Lines 26-27: Remove `api_key` and `provider` extraction from config
- Line 39: Change `chat_completion(messages, model, api_key, provider=provider)` → `chat_completion(messages, model)`

**Step 2: Update test config**

In `tests/test_agent.py`:
- Remove `"openrouter_api_key": "sk-test"` from `TEST_CONFIG`
- Change mock patch target from `"src.agent.chat_completion"` — this should still work since agent.py imports it

**Step 3: Run agent tests**

Run: `pytest tests/test_agent.py -v`
Expected: All 4 PASS

**Step 4: Run all tests**

Run: `pytest tests/ -v`
Expected: All pass (test_openrouter.py will fail — that's expected, handled next task)

**Step 5: Commit**

```bash
git add src/agent.py tests/test_agent.py
git commit -m "refactor: switch agent to LiteLLM client"
```

---

### Task 4: Remove old OpenRouter module and tests

**Files:**
- Delete: `src/openrouter.py`
- Delete: `tests/test_openrouter.py`

**Step 1: Delete files**

```bash
rm src/openrouter.py tests/test_openrouter.py
```

**Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: All pass (no remaining references to openrouter)

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: remove old OpenRouter client"
```

---

### Task 5: Update config.yaml and config tests

**Files:**
- Modify: `config.yaml`

**Step 1: Update config.yaml**

```yaml
model: anthropic/claude-opus-4-5
telegram_bot_token: ${TELEGRAM_BOT_TOKEN}
gmail_credentials_path: ./credentials.json
bash_timeout: 30
max_iterations: 10
```

Remove `openrouter_api_key` and `provider` block. API keys are now env vars consumed by LiteLLM directly.

**Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: All pass

**Step 3: Commit**

```bash
git add config.yaml
git commit -m "chore: simplify config, remove openrouter-specific fields"
```

---

### Task 6: Update Docker and docs

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-02-23-litellm-migration-design.md` (no changes needed, already accurate)

**Step 1: Update README**

In the Quick Start section, replace `export OPENROUTER_API_KEY=your-key-here` with:

```bash
# Set API key for your chosen provider
export ANTHROPIC_API_KEY=your-key    # for anthropic/* models
export OPENAI_API_KEY=your-key       # for openai/* models
export MINIMAX_API_KEY=your-key      # for minimax/* models
export OPENROUTER_API_KEY=your-key   # for openrouter/* models
```

Update the Multi-Model Testing section model examples to show provider prefixes.

**Step 2: Rebuild Docker image**

Run: `docker build -t playbook_3 .`
Expected: Builds successfully with litellm installed

**Step 3: Smoke test**

Run: `docker run --rm playbook_3 python -c "import litellm; print('litellm', litellm.__version__)"`
Expected: Prints litellm version

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update README for multi-provider LiteLLM setup"
```

---

### Task 7: End-to-end verification

**Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

**Step 2: Live smoke test (if API key available)**

```bash
python main.py --channel cli
```

Type a simple message and verify the model responds.

**Step 3: Final commit if any cleanup needed**
