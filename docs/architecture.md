# Architecture

## Component Overview

| Component | File | Role |
|-----------|------|------|
| **Orchestrator** | `src/orchestrator.py` | Conversation-aware layer; maintains session history, delegates tasks to agent via `execute_task` tool |
| **Agent** | `src/agent.py` | Stateless task executor; takes a text intent, runs bash tools, returns result string |
| **LLM** | `src/llm.py` | LiteLLM wrapper; handles tool-use protocol, accepts custom tool schemas |
| **Bash** | `src/bash.py` | Sandboxed bash execution with timeout |
| **Config** | `src/config.py` | YAML config loader with env var interpolation |
| **CLI Channel** | `src/channels/cli.py` | Interactive terminal with spinner, verbose mode, `/clear` |
| **Telegram Channel** | `src/channels/telegram.py` | Telegram bot via python-telegram-bot; user whitelist support |
| **Gmail Channel** | `src/channels/gmail.py` | Gmail polling via Google API |
| **Eval** | `src/eval.py` | Multi-model evaluation with LLM-as-judge scoring |

## Data Flow

```
User Input
    │
    ▼
┌──────────┐
│ Channel   │  (CLI / Telegram / Gmail)
│           │  Same handler interface
└────┬──────┘
     │ handler(text, reply_fn, config, session_id)
     ▼
┌──────────────┐
│ Orchestrator  │  Maintains conversation history per session
│               │  LLM with execute_task tool
│               │  Can rephrase/retry if needed
└────┬─────────┘
     │ agent.run(intent, config)
     ▼
┌──────────┐
│ Agent     │  Stateless task loop
│           │  LLM with execute_bash tool
│           │  Returns result string
└────┬─────┘
     │ execute_bash(command)
     ▼
┌──────────┐
│ Bash      │  Sandboxed execution
└──────────┘
```

## Key Design Decisions

### ADR-1: Two-tier LLM architecture

The orchestrator and agent use separate LLM calls with different tools:
- **Orchestrator**: `execute_task` — high-level intent delegation
- **Agent**: `execute_bash` — low-level command execution

This separation allows the orchestrator to maintain conversation context while keeping the agent stateless and focused.

### ADR-2: In-memory conversation history

Conversation state is stored in a module-level dict (`conversations`). This is intentionally simple — no persistence, no database. Sessions are cleared on process restart or via `clear_session()`.

### ADR-3: Channels are unaware of orchestrator

Channels import `handler` from `src.orchestrator` (previously from `src.agent`). The interface is the same — channels don't know about the orchestrator layer. This made the migration a one-line import change per channel.

## Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `model` | — | Model for agent (task execution) |
| `orchestrator_model` | falls back to `model` | Model for orchestrator (conversation) |
| `orchestrator_max_iterations` | `5` | Max orchestrator tool-call loops |
| `bash_timeout` | `30` | Bash command timeout (seconds) |
| `max_iterations` | `10` | Max agent tool-call loops |
| `telegram_bot_token` | — | Telegram bot API token |
| `telegram_allowed_users` | `""` (allow all) | Comma-separated Telegram user IDs for whitelist |
| `gmail_credentials_path` | `./credentials.json` | Path to Gmail OAuth credentials |

---

## Changelog

- **2026-02-24**: Added orchestrator layer with conversation history, execute_task tool, session management
