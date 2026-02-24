# Minimal Agent Architecture — Design Document

## Problem

playbook_2 has an inverse relationship between feature count and agent performance. As the system prompt grows and abstractions proliferate (routines, crontabs, prompts, skills), the model's decision-making degrades. The hypothesis: prompt bloat degrades cognition, and conceptual proliferation creates confusion.

## Validation Goal

Can a smart model, given clear intent and basic Unix tools, demonstrate genuine agency and make good decisions about which tools to invoke?

Secondary axis: how do different models (Opus, Kimi K2, Minimax, o3) handle intent extraction and tool selection under identical minimal conditions?

## Architecture

```
┌──────────┐   ┌──────────┐   ┌──────────┐
│ Telegram │   │  Gmail   │   │   CLI    │
│ Listener │   │  Poller  │   │ (test)   │
└────┬─────┘   └────┬─────┘   └────┬─────┘
     │              │              │
     ▼              ▼              ▼
┌──────────────────────────────────────────┐
│  handler(text: str, reply_fn: Callable)  │
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  Agent Loop                              │
│  ┌────────────────────────────────────┐  │
│  │ OpenRouter API (tool-use mode)     │  │
│  │ Single tool: execute_bash(command) │  │
│  └─────────────┬──────────────────────┘  │
│                │                         │
│        ┌───────▼────────┐                │
│        │ Tool call?     │                │
│        ├─ yes: run bash ├──┐ loop        │
│        │   return output│  │ (max 10)    │
│        ├─ no: done      │◄─┘             │
│        └────────────────┘                │
└──────────────────┬───────────────────────┘
                   ▼
          reply_fn(final_text)
          → routes back through originating channel
```

## Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Action model | Tool-use API with single tool | Supports multi-step reasoning (run → observe → run again). More structured than text-based command extraction. |
| Channels | Telegram + Gmail + CLI | Email (async/batched) and Telegram (real-time) test intent extraction across modalities. CLI enables testing without channel infra. |
| Model access | OpenRouter (thin client) | Single integration point for all models. LiteLLM as escape hatch if tool-use parsing breaks across models. |
| State | Stateless | Each message is independent. No memory, no history. Tests pure intent extraction. |
| System prompt | ~50 words | No channel awareness, no capability lists, no examples. The model decides what to do based on the message alone. |
| Language | Python | Consistent with playbook_2/playbook_crm ecosystem. |

## System Prompt

```
You are a personal assistant. You have one tool: execute_bash. Use it to
accomplish tasks on the user's computer. You are running on macOS.

When you receive a message:
- If it requires action, use bash to accomplish it.
- If it's conversational, just reply.
- If you're unsure what the user wants, ask.

Keep replies short and direct.
```

## Components

| File | ~Lines | Responsibility |
|------|--------|---------------|
| `main.py` | 30 | Wire channels to agent, start event loop, CLI arg parsing (`--channel`) |
| `src/agent.py` | 60 | Agentic loop: LLM call → tool exec → loop or return |
| `src/bash.py` | 15 | `execute_bash(command, timeout)` → stdout + stderr |
| `src/openrouter.py` | 50 | Thin HTTP client for OpenRouter chat completions + tool-use |
| `src/channels/telegram.py` | 40 | Telegram adapter → `handler(text, reply_fn)` |
| `src/channels/gmail.py` | 60 | Gmail polling + reply → `handler(text, reply_fn)` |
| `src/channels/cli.py` | 15 | stdin/stdout adapter for testing |
| `src/config.py` | 25 | YAML loader with env var interpolation |

~280 lines total.

## Project Structure

```
playbook_3/
├── config.yaml
├── main.py
├── src/
│   ├── agent.py
│   ├── bash.py
│   ├── openrouter.py
│   ├── channels/
│   │   ├── telegram.py
│   │   ├── gmail.py
│   │   └── cli.py
│   └── config.py
├── tests/
│   ├── test_agent.py
│   ├── test_bash.py
│   └── test_openrouter.py
├── requirements.txt
└── README.md
```

## Config

```yaml
model: "anthropic/claude-sonnet-4"
openrouter_api_key: ${OPENROUTER_API_KEY}
telegram_bot_token: ${TELEGRAM_BOT_TOKEN}
gmail_credentials_path: ./credentials.json
bash_timeout: 30
max_iterations: 10
```

## Error Handling

- **Bash:** Timeout (default 30s) prevents hangs. Combined stdout + stderr returned to model.
- **Agent loop:** `max_iterations` cap (default 10) prevents infinite loops.
- **Channels:** Log and continue on errors. Channels run independently — one crashing doesn't take down the other.

## What's Deliberately Excluded

- No bash allowlist/blocklist
- No confirmation prompts
- No output sanitization
- No memory/state
- No prompt procedures
- No sub-agents

Each of these is a future addition, gated on observed need during validation.

## Channel Usage

```bash
python main.py                    # starts telegram + gmail (default)
python main.py --channel cli      # interactive terminal mode
python main.py --channel telegram # just telegram
```

## Multi-Model Testing

Swap models by changing `config.yaml`:

```yaml
model: "anthropic/claude-sonnet-4"     # Claude
model: "moonshotai/kimi-k2"            # Kimi K2
model: "minimax/minimax-m1"            # Minimax
model: "openai/o3"                     # OpenAI o3
```

Same prompt, same tool, same channels. Compare decision quality across models.
