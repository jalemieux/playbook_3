# Lightweight Eval Framework Design

**Date:** 2026-02-23
**Status:** Approved

## Goal

Test agentic capability (tool use, multi-step reasoning, task completion) across multiple models by running the same prompts through the full agent loop and comparing results manually.

## Architecture

```
eval.yaml                 eval.py                        results/
┌─────────────────┐      ┌─────────────────────┐        ┌──────────────────────┐
│ models:         │      │                     │        │ 2026-02-23T14-30.md  │
│   - name: claude│─────▶│ load_config()       │        │                      │
│     model: ...  │      │                     │        │ # Eval Results       │
│   - name: kimi  │      │ for model in models:│        │ ## Prompt 1          │
│     model: ...  │      │   for prompt:       │        │ ### claude           │
│                 │      │     handler(...)  ──┼──▶API  │ > response...        │
│ prompts:        │      │     collect reply   │        │ ### kimi             │
│   - name: ...   │      │                     │        │ > response...        │
│     text: ...   │      │ write_report()   ──┼───────▶│                      │
└─────────────────┘      └─────────────────────┘        └──────────────────────┘
```

## Config Format (eval.yaml)

```yaml
models:
  - name: claude-sonnet
    model: anthropic/claude-sonnet-4
  - name: kimi-k2
    model: moonshotai/kimi-k2

prompts:
  - name: list-files
    text: "List all Python files in the current directory"
  - name: disk-usage
    text: "What's the disk usage of /tmp?"
```

Models inherit `openrouter_api_key` and `provider` from the main `config.yaml`.

## Components (eval.py, ~80 LOC)

1. **load_eval_config(path)** — parse eval.yaml
2. **build_agent_config(model_entry, base_config)** — merge model entry with base config.yaml
3. **run_single(prompt, config)** → `(response_text, elapsed_seconds)` — wraps `handler()` with string collector
4. **run_all(models, prompts, base_config)** → results dict
5. **write_report(results, output_path)** — markdown generation

## CLI

```bash
python eval.py                    # defaults: eval.yaml → results/
python eval.py --config my.yaml   # custom eval config
python eval.py --output report.md # custom output path
```

## Report Format

```markdown
# Eval Results — 2026-02-23 14:30

## "List all Python files in the current directory"

### claude-sonnet (3.2s)
<response text>

### kimi-k2 (5.1s)
<response text>
```

## Non-Goals

- No scoring/grading — manual comparison only
- No parallelism — sequential execution
- No web UI — markdown output
- No mocking — real bash execution
