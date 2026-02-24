# LiteLLM Migration — Design Document

## Problem

OpenRouter is producing inconsistent performance. We need direct access to native provider APIs (Anthropic, OpenAI, Minimax) while keeping OpenRouter as an option for long-tail models.

## Decision

Replace the hand-rolled `httpx` OpenRouter client with LiteLLM library. LiteLLM provides a unified `completion()` interface that routes to the correct provider based on model prefix and returns OpenAI-compatible responses.

## Architecture

```
┌─────────────┐     ┌──────────┐     ┌─────────────────────────┐
│  agent.py   │────▶│  llm.py  │────▶│  litellm.completion()   │
│  (unchanged │     │  (~20 LOC│     │                         │
│   loop)     │     │  wrapper) │     │  anthropic/* → Anthropic│
│             │     │           │     │  openai/*    → OpenAI   │
└─────────────┘     └──────────┘     │  minimax/*   → Minimax  │
                                     │  openrouter/* → OpenRouter│
                                     └─────────────────────────┘
```

## Changes

| File | Action | Detail |
|---|---|---|
| `src/openrouter.py` | Delete | Replaced by llm.py |
| `src/llm.py` | Create | Thin wrapper: `chat_completion(messages, model, tools)` calling `litellm.completion()` |
| `src/agent.py` | Modify | Import from `llm` instead of `openrouter`, drop `api_key`/`provider` params |
| `config.yaml` | Modify | Remove `openrouter_api_key` and `provider` block |
| `.env` | Modify | Provider-specific keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `MINIMAX_API_KEY`, `OPENROUTER_API_KEY` |
| `requirements.txt` | Modify | Replace `httpx` with `litellm` |
| `tests/test_openrouter.py` | Modify → rename | Update to test `src/llm.py` |

## Config shape (after)

```yaml
model: anthropic/claude-opus-4-5
bash_timeout: 30
max_iterations: 10
telegram_bot_token: ${TELEGRAM_BOT_TOKEN}
gmail_credentials_path: ./credentials.json
```

Model prefix determines provider. API keys discovered from environment automatically by LiteLLM.

## API key management

LiteLLM auto-discovers keys from standard env vars:
- `ANTHROPIC_API_KEY` → Anthropic models
- `OPENAI_API_KEY` → OpenAI models
- `MINIMAX_API_KEY` → Minimax models
- `OPENROUTER_API_KEY` → OpenRouter models

No keys in config.yaml.

## What stays the same

- Agent loop logic (tool call parsing, message accumulation)
- Tool schema (execute_bash)
- Channel code (cli/telegram/gmail)
- Bash executor
- System prompt
- Docker setup (just add env vars to .env)

## Risks

- LiteLLM adds ~15MB dependency
- Provider-specific quirks may surface (tool call format differences) — LiteLLM should handle these but may lag behind API changes
- Minimax tool calling support in LiteLLM needs verification
