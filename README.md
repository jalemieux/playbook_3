# playbook_3 — Minimal Agent

A minimal agent that tests whether a smart model + clear intent + one tool = genuine agency.

## Hypothesis

Prompt bloat degrades cognition. This project strips agent architecture to first principles:
~50-word system prompt, one tool (`execute_bash`), no memory, no state.

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENROUTER_API_KEY=your-key-here
python main.py --channel cli
```

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
model: "anthropic/claude-sonnet-4"   # Claude
model: "moonshotai/kimi-k2"          # Kimi K2
model: "minimax/minimax-m1"          # Minimax
model: "openai/o3"                   # OpenAI o3
```

## Tests

```bash
pytest tests/ -v
```

14 tests across 4 modules (config, bash, openrouter, agent).

## Architecture

See [docs/plans/2026-02-23-minimal-agent-design.md](docs/plans/2026-02-23-minimal-agent-design.md) for the full design document.
