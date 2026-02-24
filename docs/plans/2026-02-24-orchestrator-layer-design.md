# Orchestrator Layer Design

**Date:** 2026-02-24
**Status:** Approved

## Overview

Add a conversation-aware orchestrator layer on top of the existing stateless agent loop. The orchestrator manages user conversations and calls the agent loop as a tool, evaluating results and retrying with rephrased intent if needed. No changes to the agent loop's core logic.

## Architecture

```
Channel (CLI/Telegram/Gmail)
    │
    │  handler(text, reply_fn, config, session_id, status_fn)
    │
    ▼
┌─────────────────────────────────────┐
│  Orchestrator  (src/orchestrator.py)│
│                                     │
│  • Maintains conversation history   │
│    per session (in-memory dict)     │
│  • Minimal system prompt (~50 words)│
│  • LLM with one tool: execute_task  │
│  • Evaluates sub-agent result       │
│  • Retries with rephrased intent    │
└──────────────┬──────────────────────┘
               │  execute_task(intent: str) → str
               ▼
┌─────────────────────────────────────┐
│  Agent Loop  (src/agent.py)         │
│         UNCHANGED                   │
│  • Stateless, single-shot           │
│  • LLM + execute_bash tool          │
│  • Returns final text response      │
└─────────────────────────────────────┘
```

## Key Decisions

- **Approach A chosen:** Orchestrator as new module, agent loop called as a Python function (not via LiteLLM tool schema or sub-agent registry)
- **Full chat history** persisted in-memory until user explicitly clears (`/clear` or `/reset`)
- **Independent LLM models** for orchestrator and agent, each configured separately
- **Rephrase & retry** on unsatisfactory responses (orchestrator LLM decides, no user involvement in retries)
- **Minimal system prompt** for orchestrator (~50 words), consistent with core hypothesis
- **Channels unaware** of orchestrator — same `handler` interface

## Conversation History Management

```
conversations: dict[str, list[dict]]
    key = session_id ("cli", telegram chat_id, gmail thread_id)
    value = message history [{role, content}, ...]
```

- In-memory dict, lost on restart (acceptable for now)
- Session ID passed by channels: CLI uses `"cli"`, Telegram uses `chat_id`, Gmail uses `thread_id`
- `/clear` or `/reset` commands handled at channel level, clear history for that session

## Orchestrator LLM & Tool

**System prompt:**
> You are a personal assistant. You have one tool: execute_task. Use it to accomplish tasks by describing what needs to be done. Evaluate results and retry with clearer instructions if needed. Keep replies short and direct.

**Tool schema:**
- `execute_task(intent: str) -> str` — single parameter, natural language intent
- Routes to `agent.run(intent, config, status_fn)` which returns the agent's final response

## Retry Logic

The orchestrator LLM loop (capped by `orchestrator_max_iterations`, default 5):
1. LLM sees conversation + user message
2. Decides: reply conversationally or call `execute_task`
3. If tool called → agent runs, result appended to orchestrator messages
4. LLM evaluates result → satisfied (reply to user) or unsatisfied (call again with rephrased intent)
5. Loop cap prevents runaway retries

## Config Changes

```yaml
model: anthropic/claude-sonnet-4-6              # agent loop model (unchanged)
orchestrator_model: anthropic/claude-sonnet-4-6  # orchestrator model (new)
orchestrator_max_iterations: 5                   # orchestrator loop cap (new)
bash_timeout: 30                                 # unchanged
max_iterations: 10                               # agent loop cap (unchanged)
```

## File Changes

| File | Change |
|------|--------|
| `src/orchestrator.py` | **NEW** ~80-100 lines — orchestrator handler, conversation store, execute_task tool |
| `src/agent.py` | **MINOR** — refactor `handler` → `run()` returning `str` instead of calling `reply_fn` |
| `src/llm.py` | **MINOR** — make `chat_completion` accept optional `tools` param |
| `config.yaml` | **MINOR** — add `orchestrator_model`, `orchestrator_max_iterations` |
| `main.py` | **UNCHANGED** |
| `src/channels/cli.py` | **MINOR** — import from orchestrator, pass `session_id`, add `/clear` |
| `src/channels/telegram.py` | **MINOR** — import from orchestrator, pass `chat_id` as `session_id` |
| `src/channels/gmail.py` | **MINOR** — import from orchestrator, pass `thread_id` as `session_id` |
