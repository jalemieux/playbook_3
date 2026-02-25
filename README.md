# playbook_3 — Minimal Agent

A minimal agent that tests whether a smart model + clear intent + one tool = genuine agency.

## Hypothesis

Prompt bloat degrades cognition. This project strips agent architecture to first principles:
~50-word system prompt, one tool (`execute_bash`), no memory, no state.

## Features

- **Orchestrator layer** — conversation-aware; maintains session history, delegates tasks to a stateless agent
- **Stateless agent** — executes tasks via bash, returns results
- **Multi-channel** — CLI, Telegram (with user whitelist), Gmail with identical interface
- **Multi-model** — swap models via config (Anthropic, OpenAI, Minimax, etc.)
- **Eval framework** — compare model performance across prompts
- **Session management** — `/clear` to reset conversation in CLI

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Set API key for your chosen provider
export ANTHROPIC_API_KEY=your-key    # for anthropic/* models
export OPENAI_API_KEY=your-key       # for openai/* models
export MINIMAX_API_KEY=your-key      # for minimax/* models
export OPENROUTER_API_KEY=your-key   # for openrouter/* models
python main.py --channel cli
```

### Docker

```bash
# Build and run with CLI channel (default)
docker build -t playbook_3 .
docker run -it --env-file .env playbook_3

# Run with a specific channel
docker run -it --env-file .env -e CHANNEL=telegram playbook_3

# Via docker compose
docker compose run agent
```

The `CHANNEL` env var controls which channel starts (`cli`, `telegram`, `gmail`, `all`). The `--channel` flag takes precedence if provided.

## Channels

```bash
python main.py --channel cli        # Interactive terminal
python main.py --channel telegram   # Telegram bot (needs TELEGRAM_BOT_TOKEN)
python main.py --channel gmail      # Gmail polling (needs credentials.json)
python main.py                      # Telegram + Gmail together
```

## Multi-Model Testing

Edit `config.yaml` to swap models:

```yaml
agent_model: "anthropic/claude-sonnet-4"   # Claude
agent_model: "moonshotai/kimi-k2"          # Kimi K2
agent_model: "minimax/minimax-m1"          # Minimax
agent_model: "openai/o3"                   # OpenAI o3
```

## Eval Framework

Compare model performance across prompts with LLM-as-judge scoring:

```bash
# Run eval with default config (7 models × 5 prompts):
python eval.py

# Custom config and output:
python eval.py --config my-eval.yaml --output my-report.md
```

### How it works

1. Each prompt is sent to every model as a **single-shot** LiteLLM call (no agentic loop)
2. A **judge model** scores each response against weighted criteria
3. Results are written as markdown with a **summary leaderboard** and per-prompt detail

### eval.yaml format

```yaml
judge:
  model: anthropic/claude-sonnet-4-6

models:
  - name: claude-sonnet-4
    model: anthropic/claude-sonnet-4-6

prompts:
  - name: schedule-reminder
    text: "Remind me to call the dentist every weekday at 9am"
    criteria:
      - name: uses-scheduler
        weight: 3
        description: Uses crontab or systemd timer
```

Results are saved as timestamped markdown in `results/`.

## Tests

```bash
pytest tests/ -v
```

36 tests across 6 modules (config, bash, llm, agent, orchestrator, eval).

## Architecture

See [docs/architecture.md](docs/architecture.md) for component overview, data flow, and design decisions.

See [docs/plans/2026-02-23-minimal-agent-design.md](docs/plans/2026-02-23-minimal-agent-design.md) for the original design document.
