# Intent-to-Action Eval Framework Design

**Date:** 2026-02-24
**Status:** Draft

## Goal

Measure how well different LLM models translate natural-language user intent into executable Linux actions (bash commands, scripts, cron jobs). We are **not** executing the actions — only judging the quality of the model's action plan.

## Architecture

```
eval.yaml                     eval.py
┌──────────────┐        ┌─────────────────────┐
│ judge:       │        │                     │
│   model: ... │        │ run_single()        │
│ models: [...]│───────▶│   litellm.completion│  ← single-shot, no agentic loop
│ prompts:     │        │                     │
│   - text     │        │ judge_single()      │
│     criteria │        │   litellm.completion│  ← judge model scores response
│              │        │                     │
│              │        │ write_report()      │
│              │        │   summary table +   │
│              │        │   per-prompt detail  │
└──────────────┘        └─────────────────────┘
```

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scoring method | LLM-as-judge | Flexible, handles nuance in action quality |
| Judge model | Configurable in eval.yaml | Default Claude Opus, but swappable |
| Eval mode | Single-shot | Measures raw intent-to-action translation; cheaper, simpler |
| Approach | Extend existing eval.py | Minimalist, ~100 new lines, builds on tested pipeline |
| Target OS | Ubuntu/Linux | System prompt says Ubuntu; criteria expect Linux tools |

## Models (7)

| Name | LiteLLM Model ID | Tier |
|------|-------------------|------|
| claude-sonnet-4 | `anthropic/claude-sonnet-4-6` | Top |
| gpt-4o | `openai/gpt-4o` | Top |
| gemini-2.5-flash | `gemini/gemini-2.5-flash` | Top |
| minimax-01 | `openrouter/minimax/minimax-01` | Top |
| kimi-k2 | `openrouter/moonshotai/kimi-k2` | Top |
| claude-haiku-4.5 | `anthropic/claude-haiku-4-5-20251001` | Budget |
| gpt-4o-mini | `openai/gpt-4o-mini` | Budget |

## Prompts & Criteria

### 1. schedule-reminder
**Prompt:** "Remind me to call the dentist every weekday at 9am"

| Criterion | Weight | Description |
|-----------|--------|-------------|
| uses-scheduler | 3 | Uses crontab or systemd timer |
| correct-schedule | 2 | Cron expression = weekdays at 9am (0 9 * * 1-5) |
| creates-script | 2 | Creates a shell script or command |
| notification-method | 1 | Uses notify-send, wall, zenity, or log |

### 2. send-email
**Prompt:** "Reach out to alice@example.com about the Q3 budget review"

| Criterion | Weight | Description |
|-----------|--------|-------------|
| email-tool | 3 | Uses sendmail, mail, msmtp, curl+SMTP, or python |
| correct-recipient | 2 | Addresses alice@example.com |
| relevant-subject | 2 | Subject/body relates to Q3 budget review |
| complete-message | 1 | Reasonable email body, not a stub |

### 3. research-topic
**Prompt:** "Research the current state of nuclear fusion energy and summarize key developments"

| Criterion | Weight | Description |
|-----------|--------|-------------|
| web-search | 3 | Uses curl, wget, lynx, w3m, or python requests |
| multiple-sources | 2 | Queries multiple sources or search terms |
| synthesis | 2 | Plans to synthesize findings, not dump raw output |
| structured-output | 1 | Organizes results readably |

### 4. morning-briefing
**Prompt:** "Set up a daily morning briefing at 7am that pulls news on AI policy, crypto regulation, and climate tech"

| Criterion | Weight | Description |
|-----------|--------|-------------|
| scheduler | 3 | Uses crontab or systemd timer for daily 7am |
| news-fetching | 3 | Script fetches news via curl/wget, RSS, newsapi, etc. |
| topic-coverage | 2 | Covers all three topics |
| aggregation | 1 | Aggregates into single briefing format |

### 5. file-backup
**Prompt:** "Back up my ~/Documents folder to an external drive at /mnt/backup every Sunday at midnight"

| Criterion | Weight | Description |
|-----------|--------|-------------|
| backup-tool | 3 | Uses rsync, cp -r, tar, or equivalent |
| correct-paths | 2 | Source ~/Documents, dest /mnt/backup |
| weekly-schedule | 2 | Cron = Sunday midnight (0 0 * * 0) |
| robustness | 1 | Handles edge cases (drive not mounted, error logging) |

## Scoring

Each criterion scored 0.0–1.0 by the judge model. Per-prompt score = weighted average:

```
score = Σ(criterion_score × weight) / Σ(weight)
```

Overall model score = average across all prompts.

## Judge Prompt

```
You are evaluating an AI assistant's ability to translate user intent into
executable Linux (Ubuntu) actions. The assistant has one tool: execute_bash.

You will be given:
1. The user's original request
2. The assistant's response (including any tool calls)
3. A list of criteria to evaluate

Score each criterion from 0.0 to 1.0:
- 1.0 = fully satisfied
- 0.5 = partially satisfied
- 0.0 = not addressed

Return ONLY valid JSON in this format:
{
  "criterion_name": {"score": 0.0, "reasoning": "..."},
  ...
}
```

## Report Format

```markdown
# Eval Results — 2026-02-24 15:23

## Summary

| Model           | schedule | email | research | briefing | backup | Avg  |
|-----------------|----------|-------|----------|----------|--------|------|
| claude-sonnet-4 | 0.92     | 0.88  | 0.75     | 0.85     | 0.95   | 0.87 |
| gpt-4o          | 0.88     | 0.90  | 0.80     | 0.82     | 0.90   | 0.86 |
| ...             |          |       |          |          |        |      |

## "Remind me to call the dentist every weekday at 9am"

### claude-sonnet-4 — Score: 0.92 (3.2s)

**Criteria:**
- uses-scheduler: 1.0 — Uses crontab correctly
- correct-schedule: 1.0 — Correct weekday 9am expression
- creates-script: 0.8 — Script exists but minimal
- notification-method: 0.7 — Uses echo, not notify-send

**Response:**
<full model response including tool_calls>

---
```

## Code Changes

### Modified files

**`eval.py`** — extend with:
- `judge_single(prompt, criteria, response, judge_model) → dict` — one LiteLLM call to judge model, parse JSON scores
- `judge_all(results, prompts, judge_model) → results_with_scores` — iterate and score all results
- `write_report()` — enhanced with summary table + per-criterion scores
- `run_single()` — change from `handler()` call to direct `litellm.completion()` (single-shot, no agentic loop)
- `format_response()` — format response + tool_calls into readable text for judge

**`eval.yaml`** — replace with new structure (judge, 7 models, 5 prompts with criteria)

**`src/agent.py`** — change system prompt from "macOS" to "Ubuntu"

**`tests/test_eval.py`** — update/add tests for new functions

### New function signatures

```python
def run_single(prompt_text: str, model: str, system_prompt: str) -> dict:
    """Single-shot LLM call. Returns raw response dict with content + tool_calls."""

def format_response(result: dict) -> str:
    """Format LLM response (content + tool_calls) as readable text for judging."""

def judge_single(prompt_text: str, response_text: str, criteria: list[dict], judge_model: str) -> dict:
    """Score one response. Returns {criterion_name: {score, reasoning}}."""

def judge_all(results: list[dict], prompts: list[dict], judge_model: str) -> list[dict]:
    """Score all results. Returns results enriched with scores."""
```

## Execution

35 model calls (7 models × 5 prompts) + 35 judge calls = 70 LLM calls total.
