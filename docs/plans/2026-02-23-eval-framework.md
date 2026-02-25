# Eval Framework Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run the same prompts through multiple models via the agent loop and generate a markdown comparison report.

**Architecture:** Single `eval.py` script reads `eval.yaml` (models + prompts), iterates model×prompt calling the existing `handler()`, collects responses with timing, and writes a timestamped markdown report to `results/`.

**Tech Stack:** Python, PyYAML (already a dependency), existing `src.agent.handler` and `src.config.load_config`

---

### Task 1: Create eval.yaml with sample config

**Files:**
- Create: `eval.yaml`

**Step 1: Create the eval config file**

```yaml
models:
  - name: claude-sonnet
    model: anthropic/claude-sonnet-4
  - name: kimi-k2
    model: moonshotai/kimi-k2

prompts:
  - name: list-python-files
    text: "List all Python files in the current directory"
  - name: word-count
    text: "Count the number of lines in main.py"
```

**Step 2: Commit**

```bash
git add eval.yaml
git commit -m "feat(eval): add eval.yaml with sample models and prompts"
```

---

### Task 2: Write failing tests for eval core functions

**Files:**
- Create: `tests/test_eval.py`

**Step 1: Write failing tests**

```python
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml


def test_load_eval_config(tmp_path):
    """load_eval_config parses models and prompts from YAML."""
    config_file = tmp_path / "eval.yaml"
    config_file.write_text(yaml.dump({
        "models": [{"name": "test-model", "model": "test/model-1"}],
        "prompts": [{"name": "greeting", "text": "Hello"}],
    }))
    from eval import load_eval_config
    cfg = load_eval_config(config_file)
    assert len(cfg["models"]) == 1
    assert cfg["models"][0]["name"] == "test-model"
    assert len(cfg["prompts"]) == 1
    assert cfg["prompts"][0]["text"] == "Hello"


def test_build_agent_config():
    """build_agent_config merges model entry into base config."""
    from eval import build_agent_config
    base = {"openrouter_api_key": "sk-test", "bash_timeout": 30, "max_iterations": 10}
    model_entry = {"name": "test-model", "model": "test/model-1"}
    result = build_agent_config(model_entry, base)
    assert result["model"] == "test/model-1"
    assert result["openrouter_api_key"] == "sk-test"
    assert result["bash_timeout"] == 30


def test_run_single():
    """run_single calls handler and returns (response, elapsed)."""
    from eval import run_single
    config = {"model": "test/model-1", "openrouter_api_key": "sk-test",
              "bash_timeout": 5, "max_iterations": 10}
    with patch("eval.handler") as mock_handler:
        def fake_handler(text, reply_fn, cfg, status_fn=None):
            reply_fn("test response")
        mock_handler.side_effect = fake_handler
        response, elapsed = run_single("Hello", config)
    assert response == "test response"
    assert elapsed >= 0


def test_run_single_error():
    """run_single captures exceptions as error text."""
    from eval import run_single
    config = {"model": "test/model-1", "openrouter_api_key": "sk-test",
              "bash_timeout": 5, "max_iterations": 10}
    with patch("eval.handler", side_effect=Exception("API down")):
        response, elapsed = run_single("Hello", config)
    assert "ERROR" in response
    assert "API down" in response


def test_write_report(tmp_path):
    """write_report generates markdown with all results."""
    from eval import write_report
    results = [
        {
            "prompt_name": "greeting",
            "prompt_text": "Hello",
            "model_results": [
                {"model_name": "model-a", "response": "Hi there!", "elapsed": 1.5},
                {"model_name": "model-b", "response": "Hey!", "elapsed": 2.0},
            ],
        }
    ]
    output = tmp_path / "report.md"
    write_report(results, output)
    text = output.read_text()
    assert "# Eval Results" in text
    assert "Hello" in text
    assert "model-a" in text
    assert "Hi there!" in text
    assert "1.5s" in text
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eval.py -v`
Expected: FAIL — `eval` module does not exist yet

**Step 3: Commit**

```bash
git add tests/test_eval.py
git commit -m "test(eval): add failing tests for eval core functions"
```

---

### Task 3: Implement eval.py core functions

**Files:**
- Create: `eval.py`

**Step 1: Implement all core functions**

```python
"""Lightweight eval framework — run prompts across models, compare results."""

import argparse
import time
from datetime import datetime
from pathlib import Path

import yaml

from src.agent import handler
from src.config import load_config


def load_eval_config(path: Path) -> dict:
    """Load eval YAML with models and prompts lists."""
    return yaml.safe_load(Path(path).read_text())


def build_agent_config(model_entry: dict, base_config: dict) -> dict:
    """Merge a model entry into the base config."""
    return {**base_config, "model": model_entry["model"]}


def run_single(prompt_text: str, config: dict) -> tuple[str, float]:
    """Run one prompt through the agent loop. Returns (response, elapsed_seconds)."""
    response = []

    def collect(text):
        response.append(text)

    start = time.time()
    try:
        handler(prompt_text, collect, config)
    except Exception as e:
        response.append(f"ERROR: {e}")
    elapsed = time.time() - start
    return response[0] if response else "[no response]", elapsed


def run_all(models: list[dict], prompts: list[dict], base_config: dict) -> list[dict]:
    """Run every prompt against every model. Returns structured results."""
    results = []
    for prompt in prompts:
        prompt_results = {
            "prompt_name": prompt["name"],
            "prompt_text": prompt["text"],
            "model_results": [],
        }
        for model in models:
            config = build_agent_config(model, base_config)
            print(f"  [{model['name']}] {prompt['name']}...", end=" ", flush=True)
            response, elapsed = run_single(prompt["text"], config)
            print(f"{elapsed:.1f}s")
            prompt_results["model_results"].append({
                "model_name": model["name"],
                "response": response,
                "elapsed": elapsed,
            })
        results.append(prompt_results)
    return results


def write_report(results: list[dict], output_path: Path) -> None:
    """Write a markdown comparison report."""
    lines = [f"# Eval Results — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    for entry in results:
        lines.append(f"## \"{entry['prompt_text']}\"\n")
        for mr in entry["model_results"]:
            lines.append(f"### {mr['model_name']} ({mr['elapsed']:.1f}s)\n")
            lines.append(f"{mr['response']}\n")
        lines.append("---\n")
    Path(output_path).write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Run eval across models")
    parser.add_argument("--config", default="eval.yaml", help="Eval config YAML")
    parser.add_argument("--output", default=None, help="Output markdown path")
    parser.add_argument("--base-config", default="config.yaml", help="Base agent config")
    args = parser.parse_args()

    eval_cfg = load_eval_config(Path(args.config))
    base_cfg = load_config(Path(args.base_config))

    output_path = args.output or f"results/{datetime.now().strftime('%Y-%m-%dT%H-%M')}.md"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(eval_cfg['prompts'])} prompts × {len(eval_cfg['models'])} models\n")
    results = run_all(eval_cfg["models"], eval_cfg["prompts"], base_cfg)

    write_report(results, Path(output_path))
    print(f"\nReport saved to {output_path}")


if __name__ == "__main__":
    main()
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/test_eval.py -v`
Expected: all 5 tests PASS

**Step 3: Commit**

```bash
git add eval.py
git commit -m "feat(eval): implement eval.py with run/report functions"
```

---

### Task 4: Add results/ to .gitignore and create sample eval run

**Files:**
- Modify: `.gitignore` (create if missing)

**Step 1: Add results/ to .gitignore**

Add this line to `.gitignore`:
```
results/
```

**Step 2: Verify it works end-to-end**

Run: `python eval.py --help`
Expected: Shows usage with --config, --output, --base-config flags

**Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: add results/ to .gitignore"
```

---

### Task 5: Run existing test suite to confirm nothing broke

**Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All 19 tests pass (14 existing + 5 new eval tests)

---

### Task 6: Update documentation

**Files:**
- Modify: `README.md` — add Eval section with usage examples
- Modify: `docs/architecture.md` — add eval component (if file exists)

**Step 1: Add eval section to README**

Add after the existing usage section:

```markdown
## Eval Framework

Compare model performance across prompts:

```bash
# Edit eval.yaml with your models and prompts, then:
python eval.py

# Custom config and output:
python eval.py --config my-eval.yaml --output my-report.md
```

Results are saved as timestamped markdown in `results/`.
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add eval framework usage to README"
```
